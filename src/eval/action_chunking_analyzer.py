#!/usr/bin/env python3
"""
action_chunking_analyzer.py — Analyzes the effect of action chunk size on GR00T policy performance.

GR00T uses action chunking (predicting K steps ahead). This script sweeps chunk sizes
1→32 and measures success rate, latency, smoothness, and error compounding.

Usage:
    python src/eval/action_chunking_analyzer.py --mock --output /tmp/action_chunking_analyzer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


CHUNK_SIZES = [1, 2, 4, 8, 16, 32]
POLICIES = ["bc_baseline", "dagger_run5", "dagger_run9"]
N_EPISODES = 40


@dataclass
class ChunkResult:
    chunk_size: int
    policy_name: str
    success_rate: float
    avg_latency_ms: float       # inference per decision point
    smoothness_score: float     # jerk metric (higher = smoother)
    error_compound_rate: float  # error accumulation over chunk (lower = better)
    replanning_freq: float      # decisions per second (1/chunk_duration)
    total_steps: int            # total env steps across all episodes


@dataclass
class ChunkingReport:
    best_chunk_per_policy: dict[str, int]
    optimal_chunk_size: int    # cross-policy consensus
    results: list[ChunkResult] = field(default_factory=list)


POLICY_BASE = {
    # (base_sr at chunk=8, latency_base_ms)
    "bc_baseline":  (0.53, 226),
    "dagger_run5":  (0.67, 229),
    "dagger_run9":  (0.78, 231),
}

# How each chunk size modifies success rate
CHUNK_SR_MODIFIER = {1: -0.12, 2: -0.06, 4: -0.02, 8: 0.0, 16: +0.03, 32: +0.01}
CHUNK_SMOOTH_BASE  = {1: 0.55, 2: 0.63, 4: 0.74, 8: 0.82, 16: 0.88, 32: 0.85}
CHUNK_ERROR_COMP   = {1: 0.02, 2: 0.04, 4: 0.07, 8: 0.12, 16: 0.19, 32: 0.28}


def simulate_chunking(seed: int = 42) -> ChunkingReport:
    rng = random.Random(seed)
    results: list[ChunkResult] = []

    for policy in POLICIES:
        base_sr, lat_base = POLICY_BASE[policy]
        for chunk in CHUNK_SIZES:
            sr = base_sr + CHUNK_SR_MODIFIER[chunk] + rng.gauss(0, 0.02)
            sr = max(0.05, min(0.97, sr))

            # Latency: larger chunks = slightly faster per step (batched), but longer per call
            lat = lat_base + chunk * 4 + rng.gauss(0, 8)
            lat = max(50, lat)

            smooth = CHUNK_SMOOTH_BASE[chunk] + rng.gauss(0, 0.03)
            smooth = max(0.3, min(1.0, smooth))

            err_comp = CHUNK_ERROR_COMP[chunk] + rng.gauss(0, 0.01)
            err_comp = max(0.01, err_comp)

            # Replanning frequency: decisions per second
            # Each chunk covers chunk × 0.05s (20Hz control), so 1 decision per chunk×0.05s
            replan = 1.0 / (chunk * 0.05)
            total_steps = N_EPISODES * 100  # 100 env steps per ep

            results.append(ChunkResult(
                chunk_size=chunk, policy_name=policy,
                success_rate=round(sr, 4),
                avg_latency_ms=round(lat, 1),
                smoothness_score=round(smooth, 4),
                error_compound_rate=round(err_comp, 4),
                replanning_freq=round(replan, 2),
                total_steps=total_steps,
            ))

    # Best chunk per policy = highest success rate
    best_chunk_per_policy: dict[str, int] = {}
    for policy in POLICIES:
        policy_results = [r for r in results if r.policy_name == policy]
        best = max(policy_results, key=lambda r: r.success_rate)
        best_chunk_per_policy[policy] = best.chunk_size

    # Consensus optimal: most common best chunk
    from collections import Counter
    cnt = Counter(best_chunk_per_policy.values())
    optimal = cnt.most_common(1)[0][0]

    return ChunkingReport(
        best_chunk_per_policy=best_chunk_per_policy,
        optimal_chunk_size=optimal,
        results=results,
    )


def render_html(report: ChunkingReport) -> str:
    POLICY_COLORS = {
        "bc_baseline": "#64748b",
        "dagger_run5": "#f59e0b",
        "dagger_run9": "#22c55e",
    }
    CHUNK_X = {c: i for i, c in enumerate(CHUNK_SIZES)}

    # SVG: SR vs chunk size (line chart per policy)
    w, h, ml, mr, mt, mb = 500, 240, 50, 20, 20, 40
    inner_w = w - ml - mr
    inner_h = h - mt - mb
    n_chunks = len(CHUNK_SIZES)

    svg_sr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_sr += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_sr += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'

    # Y grid
    for v in [0.25, 0.50, 0.75, 1.0]:
        y = h - mb - v * inner_h
        svg_sr += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                   f'stroke="#1e293b" stroke-width="1"/>')
        svg_sr += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                   f'font-size="8" text-anchor="end">{v:.0%}</text>')

    # X labels
    for i, c in enumerate(CHUNK_SIZES):
        x = ml + i / (n_chunks - 1) * inner_w
        svg_sr += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                   f'font-size="8" text-anchor="middle">K={c}</text>')

    for policy in POLICIES:
        col = POLICY_COLORS[policy]
        policy_res = {r.chunk_size: r for r in report.results if r.policy_name == policy}
        pts = []
        for i, c in enumerate(CHUNK_SIZES):
            r = policy_res[c]
            x = ml + i / (n_chunks - 1) * inner_w
            y = h - mb - r.success_rate * inner_h
            pts.append((x, y))

        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_sr += (f'<polyline points="{pstr}" fill="none" stroke="{col}" '
                   f'stroke-width="2" opacity="0.9"/>')
        for x, y in pts:
            svg_sr += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{col}"/>'

    # Mark optimal chunk
    opt_x = ml + CHUNK_X[report.optimal_chunk_size] / (n_chunks - 1) * inner_w
    svg_sr += (f'<line x1="{opt_x:.1f}" y1="{mt}" x2="{opt_x:.1f}" y2="{h-mb}" '
               f'stroke="#C74634" stroke-width="1" stroke-dasharray="4,3"/>')
    svg_sr += (f'<text x="{opt_x+4:.1f}" y="{mt+12}" fill="#C74634" '
               f'font-size="8">optimal K={report.optimal_chunk_size}</text>')

    # Legend
    for i, (p, col) in enumerate(POLICY_COLORS.items()):
        svg_sr += (f'<rect x="{ml}" y="{mt+2+i*13}" width="8" height="2" fill="{col}"/>'
                   f'<text x="{ml+10}" y="{mt+9+i*13}" fill="#94a3b8" font-size="8">{p}</text>')

    svg_sr += '</svg>'

    # SVG: smoothness vs error compound (tradeoff by chunk size)
    sw, sh, sm = 340, 220, 45
    svg_tradeoff = f'<svg width="{sw}" height="{sh}" style="background:#0f172a;border-radius:8px">'
    svg_tradeoff += f'<line x1="{sm}" y1="{sm}" x2="{sm}" y2="{sh-sm}" stroke="#475569"/>'
    svg_tradeoff += f'<line x1="{sm}" y1="{sh-sm}" x2="{sw-sm}" y2="{sh-sm}" stroke="#475569"/>'

    # Axes: x=error_compound, y=smoothness — use dagger_run9 as representative
    run9 = {r.chunk_size: r for r in report.results if r.policy_name == "dagger_run9"}
    max_err = max(r.error_compound_rate for r in run9.values())
    min_err = min(r.error_compound_rate for r in run9.values())
    err_range = max_err - min_err + 0.02
    smooth_range = 1.0 - 0.3 + 0.02

    for c in CHUNK_SIZES:
        r = run9[c]
        cx = sm + (r.error_compound_rate - min_err) / err_range * (sw - 2 * sm)
        cy = sh - sm - (r.smoothness_score - 0.3) / smooth_range * (sh - 2 * sm)
        is_opt = c == report.optimal_chunk_size
        col = "#C74634" if is_opt else "#3b82f6"
        svg_tradeoff += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{6 if is_opt else 4}" '
                         f'fill="{col}" opacity="0.85"/>')
        svg_tradeoff += (f'<text x="{cx+7:.1f}" y="{cy+4:.1f}" fill="{col}" '
                         f'font-size="8">K={c}</text>')

    svg_tradeoff += (f'<text x="{sw//2}" y="{sh-sm+14}" fill="#64748b" '
                     f'font-size="8" text-anchor="middle">Error Compounding Rate →</text>')
    svg_tradeoff += (f'<text x="{sm-10}" y="{sh//2}" fill="#64748b" font-size="8" '
                     f'text-anchor="middle" transform="rotate(-90,{sm-10},{sh//2})">Smoothness ↑</text>')
    svg_tradeoff += '</svg>'

    # Table rows (only dagger_run9 for conciseness, all policies in full table)
    rows = ""
    for r in sorted(report.results, key=lambda x: (x.policy_name, x.chunk_size)):
        col = POLICY_COLORS[r.policy_name]
        is_best = (r.chunk_size == report.best_chunk_per_policy.get(r.policy_name))
        is_opt = r.chunk_size == report.optimal_chunk_size
        sr_col = "#22c55e" if is_best else "#e2e8f0"
        rows += (f'<tr>'
                 f'<td style="color:{col}">{r.policy_name}</td>'
                 f'<td style="text-align:center">{"★ " if is_opt else ""}{r.chunk_size}</td>'
                 f'<td style="color:{sr_col}">{r.success_rate:.1%}</td>'
                 f'<td style="color:#94a3b8">{r.avg_latency_ms:.0f}ms</td>'
                 f'<td style="color:#3b82f6">{r.smoothness_score:.3f}</td>'
                 f'<td style="color:#f59e0b">{r.error_compound_rate:.3f}</td>'
                 f'<td style="color:#64748b">{r.replanning_freq:.1f}Hz</td>'
                 f'</tr>')

    best_per_policy_str = "; ".join(
        f"{p}: K={c}" for p, c in report.best_chunk_per_policy.items()
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Action Chunking Analyzer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Action Chunking Analyzer</h1>
<div class="meta">
  {len(CHUNK_SIZES)} chunk sizes × {len(POLICIES)} policies · {N_EPISODES} episodes each · GR00T 20Hz control
</div>

<div class="grid">
  <div class="card"><h3>Optimal Chunk Size</h3>
    <div class="big" style="color:#C74634">K={report.optimal_chunk_size}</div>
    <div style="color:#64748b;font-size:10px">consensus across policies</div>
  </div>
  <div class="card"><h3>Best SR (dagger_run9)</h3>
    <div class="big" style="color:#22c55e">
      {max(r.success_rate for r in report.results if r.policy_name=="dagger_run9"):.1%}
    </div>
    <div style="color:#64748b;font-size:10px">K={report.best_chunk_per_policy.get("dagger_run9")}</div>
  </div>
  <div class="card"><h3>Smoothness (K={report.optimal_chunk_size})</h3>
    <div class="big" style="color:#3b82f6">
      {next(r.smoothness_score for r in report.results if r.policy_name=="dagger_run9" and r.chunk_size==report.optimal_chunk_size):.3f}
    </div>
    <div style="color:#64748b;font-size:10px">jerk minimization</div>
  </div>
  <div class="card"><h3>Error Compound (K=32)</h3>
    <div class="big" style="color:#ef4444">
      {max(r.error_compound_rate for r in report.results if r.policy_name=="dagger_run9"):.3f}
    </div>
    <div style="color:#64748b;font-size:10px">worst case chunk=32</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Success Rate vs Chunk Size</h3>
    {svg_sr}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Red dashed = optimal K={report.optimal_chunk_size} · Best per policy: {best_per_policy_str}
    </div>
  </div>
  <div>
    <h3 class="sec">Smoothness vs Error Tradeoff (dagger_run9)</h3>
    {svg_tradeoff}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Top-left = best (high smoothness + low error).<br>
      Red dot = optimal K={report.optimal_chunk_size}
    </div>
  </div>
</div>

<h3 class="sec">Full Results</h3>
<table>
  <tr><th>Policy</th><th>Chunk K</th><th>SR</th><th>Latency</th>
      <th>Smoothness</th><th>Error Comp.</th><th>Replan Hz</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">CHUNKING GUIDELINES</div>
  <div style="color:#22c55e">K=16: best for high-SR tasks with stable trajectories (stack_blocks, pick_and_place)</div>
  <div style="color:#3b82f6">K=8: balanced default — 82% smoothness, 12% error compound, 2.5Hz replanning</div>
  <div style="color:#f59e0b">K=4: reactive tasks (door_opening, pouring) — lower error compound at cost of smoothness</div>
  <div style="color:#ef4444">K=32: avoid — 28% error compound; trajectory drift causes late-episode failures</div>
  <div style="color:#64748b;margin-top:4px">GR00T default K=16; DAgger run9 trained with K=16; match eval chunk to training chunk</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Action chunking analyzer for GR00T policies")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/action_chunking_analyzer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[chunking] {len(CHUNK_SIZES)} chunk sizes · {len(POLICIES)} policies · {N_EPISODES} eps")
    t0 = time.time()

    report = simulate_chunking(args.seed)

    print(f"\n  {'Policy':<22} {'Chunk':>6} {'SR':>8} {'Smooth':>8} {'ErrComp':>9}")
    print(f"  {'─'*22} {'─'*6} {'─'*8} {'─'*8} {'─'*9}")
    for r in sorted(report.results, key=lambda x: (x.policy_name, x.chunk_size)):
        flag = " ← best" if r.chunk_size == report.best_chunk_per_policy.get(r.policy_name) else ""
        print(f"  {r.policy_name:<22} K={r.chunk_size:<4} {r.success_rate:>7.1%} "
              f"{r.smoothness_score:>8.3f} {r.error_compound_rate:>9.3f}{flag}")

    print(f"\n  Optimal chunk size: K={report.optimal_chunk_size}")
    print(f"  Best per policy: {report.best_chunk_per_policy}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "optimal_chunk_size": report.optimal_chunk_size,
        "best_chunk_per_policy": report.best_chunk_per_policy,
        "results": [{"policy": r.policy_name, "chunk": r.chunk_size,
                     "sr": r.success_rate, "smoothness": r.smoothness_score} for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
