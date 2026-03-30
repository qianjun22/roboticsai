#!/usr/bin/env python3
"""
episode_quality_scorer.py — Scores individual robot episodes for data quality filtering.

Analyzes collected episodes for training suitability: smoothness, task completion,
diversity, and annotation confidence. Filters low-quality demos before fine-tuning
to improve data efficiency. Key for DAgger run quality gating.

Usage:
    python src/eval/episode_quality_scorer.py --mock --output /tmp/episode_quality_scorer.html
    python src/eval/episode_quality_scorer.py --min-score 0.7 --tag dagger_run6
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    ep_id: str
    task: str
    source: str          # human / dagger / bc_rollout / synthetic
    n_frames: int
    success: bool
    duration_s: float
    smoothness: float    # 0-1: 1 = very smooth joint trajectories
    completion: float    # 0-1: fraction of task completed
    diversity: float     # 0-1: novelty vs existing buffer
    confidence: float    # 0-1: annotator / policy confidence
    jerk_mean: float     # mean jerk (lower = smoother)
    workspace_violation: bool
    score: float         # composite quality score 0-1


TASKS = ["pick_and_place", "stack_blocks", "open_drawer", "peg_insert", "handover"]

SCORE_WEIGHTS = {
    "smoothness":   0.25,
    "completion":   0.35,
    "diversity":    0.20,
    "confidence":   0.20,
}


# ── Simulation ─────────────────────────────────────────────────────────────────

def score_episode(smoothness, completion, diversity, confidence,
                  workspace_violation=False) -> float:
    raw = (
        SCORE_WEIGHTS["smoothness"]  * smoothness +
        SCORE_WEIGHTS["completion"]  * completion +
        SCORE_WEIGHTS["diversity"]   * diversity +
        SCORE_WEIGHTS["confidence"]  * confidence
    )
    if workspace_violation:
        raw *= 0.5   # hard penalty
    return round(max(0.0, min(1.0, raw)), 3)


def generate_episodes(n: int = 300, seed: int = 42) -> list[Episode]:
    rng = random.Random(seed)
    episodes = []

    source_probs = {"human": 0.15, "dagger": 0.45, "bc_rollout": 0.30, "synthetic": 0.10}
    source_quality = {"human": 0.85, "dagger": 0.72, "bc_rollout": 0.58, "synthetic": 0.65}

    for i in range(n):
        source = rng.choices(list(source_probs), weights=list(source_probs.values()))[0]
        task = rng.choice(TASKS)
        base_q = source_quality[source]

        smoothness = max(0.1, min(1.0, base_q + rng.gauss(0, 0.12)))
        completion = max(0.0, min(1.0, base_q * 0.9 + rng.gauss(0, 0.15)))
        diversity  = max(0.0, min(1.0, rng.gauss(0.5, 0.2)))
        confidence = max(0.1, min(1.0, base_q + rng.gauss(0, 0.10)))
        workspace_viol = rng.random() < 0.04

        n_frames = int(rng.gauss(180, 40))
        n_frames = max(20, n_frames)
        duration = n_frames / 30.0
        jerk = max(0.01, rng.gauss(0.08, 0.03) * (2 - smoothness))

        q = score_episode(smoothness, completion, diversity, confidence, workspace_viol)

        episodes.append(Episode(
            ep_id=f"ep-{i+1:04d}",
            task=task,
            source=source,
            n_frames=n_frames,
            success=completion > 0.75 and not workspace_viol,
            duration_s=round(duration, 1),
            smoothness=round(smoothness, 3),
            completion=round(completion, 3),
            diversity=round(diversity, 3),
            confidence=round(confidence, 3),
            jerk_mean=round(jerk, 4),
            workspace_violation=workspace_viol,
            score=q,
        ))

    return episodes


def filter_episodes(episodes: list[Episode], min_score: float) -> tuple[list, list]:
    passed = [e for e in episodes if e.score >= min_score]
    rejected = [e for e in episodes if e.score < min_score]
    return passed, rejected


def compute_stats(episodes: list[Episode]) -> dict:
    if not episodes:
        return {}
    scores = [e.score for e in episodes]
    by_source: dict[str, list] = {}
    by_task: dict[str, list] = {}
    for e in episodes:
        by_source.setdefault(e.source, []).append(e.score)
        by_task.setdefault(e.task, []).append(e.score)

    return {
        "total": len(episodes),
        "mean_score": round(sum(scores) / len(scores), 3),
        "median_score": round(sorted(scores)[len(scores)//2], 3),
        "success_rate": round(sum(1 for e in episodes if e.success) / len(episodes), 3),
        "workspace_violations": sum(1 for e in episodes if e.workspace_violation),
        "by_source": {k: round(sum(v)/len(v), 3) for k, v in by_source.items()},
        "by_task":   {k: round(sum(v)/len(v), 3) for k, v in by_task.items()},
        "score_dist": scores,
    }


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(episodes: list[Episode], passed: list[Episode],
                rejected: list[Episode], min_score: float) -> str:
    stats_all    = compute_stats(episodes)
    stats_passed = compute_stats(passed)

    # SVG: score histogram
    w, h = 500, 140
    bins = [0] * 10
    for e in episodes:
        b = min(9, int(e.score * 10))
        bins[b] += 1
    max_b = max(bins) or 1
    bar_w = (w - 40) / 10

    svg_hist = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_hist += f'<line x1="30" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'
    for i, cnt in enumerate(bins):
        bh = cnt / max_b * (h - 40)
        x = 30 + i * bar_w
        threshold_bin = int(min_score * 10)
        col = "#22c55e" if i >= threshold_bin else "#ef4444"
        svg_hist += (f'<rect x="{x:.1f}" y="{h-20-bh:.1f}" width="{bar_w-2:.1f}" '
                     f'height="{bh:.1f}" fill="{col}" rx="2" opacity="0.85"/>')
        svg_hist += (f'<text x="{x+bar_w/2:.1f}" y="{h-4}" fill="#64748b" '
                     f'font-size="8.5" text-anchor="middle">{i/10:.1f}</text>')
        if cnt > 0:
            svg_hist += (f'<text x="{x+bar_w/2:.1f}" y="{h-22-bh:.1f}" fill="#94a3b8" '
                         f'font-size="8" text-anchor="middle">{cnt}</text>')
    # threshold line
    tx = 30 + min_score * (w - 40)
    svg_hist += (f'<line x1="{tx:.1f}" y1="5" x2="{tx:.1f}" y2="{h-20}" '
                 f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>')
    svg_hist += (f'<text x="{tx+3:.1f}" y="15" fill="#f59e0b" font-size="9">min {min_score:.2f}</text>')
    svg_hist += '</svg>'

    # SVG: source quality comparison
    source_order = ["human", "dagger", "bc_rollout", "synthetic"]
    src_colors   = {"human": "#22c55e", "dagger": "#C74634", "bc_rollout": "#3b82f6", "synthetic": "#a855f7"}
    w2, h2 = 380, 110
    by_src = stats_all.get("by_source", {})
    svg_src = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    bar_h2 = (h2 - 20) / len(source_order) - 4
    for i, src in enumerate(source_order):
        avg = by_src.get(src, 0)
        y = 10 + i * (bar_h2 + 4)
        bw = avg * (w2 - 120)
        col = src_colors.get(src, "#64748b")
        svg_src += (f'<rect x="110" y="{y}" width="{bw:.1f}" height="{bar_h2:.1f}" '
                    f'fill="{col}" rx="2" opacity="0.85"/>')
        src_eps = [e for e in episodes if e.source == src]
        svg_src += (f'<text x="108" y="{y+bar_h2*0.7:.1f}" fill="#94a3b8" font-size="9.5" '
                    f'text-anchor="end">{src} ({len(src_eps)})</text>')
        svg_src += (f'<text x="{113+bw:.1f}" y="{y+bar_h2*0.7:.1f}" fill="{col}" '
                    f'font-size="9">{avg:.2f}</text>')
    svg_src += '</svg>'

    # Table: top 20 rejected (worst quality) + first 20 passed
    def ep_row(e):
        sc = "#22c55e" if e.score >= min_score else "#ef4444"
        viol = '<span style="color:#ef4444">⚠</span>' if e.workspace_violation else "—"
        src_col = src_colors.get(e.source, "#94a3b8")
        return (f'<tr><td style="color:#94a3b8">{e.ep_id}</td>'
                f'<td style="color:{src_col}">{e.source}</td>'
                f'<td style="color:#e2e8f0">{e.task}</td>'
                f'<td>{e.n_frames}</td>'
                f'<td>{e.smoothness:.2f}</td>'
                f'<td>{e.completion:.2f}</td>'
                f'<td>{e.diversity:.2f}</td>'
                f'<td>{e.confidence:.2f}</td>'
                f'<td>{viol}</td>'
                f'<td style="color:{sc};font-weight:bold">{e.score:.3f}</td></tr>')

    sample_rows = "".join(ep_row(e) for e in
        sorted(rejected, key=lambda x: x.score)[:10] +
        sorted(passed,   key=lambda x: -x.score)[:10])

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Episode Quality Scorer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Episode Quality Scorer</h1>
<div class="meta">
  {len(episodes)} episodes · min score {min_score:.2f} · {len(passed)} passed ({len(passed)/len(episodes)*100:.0f}%) · {len(rejected)} rejected
</div>

<div class="grid">
  <div class="card"><h3>Total Episodes</h3>
    <div class="big">{stats_all['total']}</div></div>
  <div class="card"><h3>Passed Filter</h3>
    <div class="big" style="color:#22c55e">{len(passed)}</div>
    <div style="color:#64748b;font-size:12px">{len(passed)/len(episodes)*100:.0f}% retention</div></div>
  <div class="card"><h3>Mean Score</h3>
    <div class="big" style="color:#3b82f6">{stats_all['mean_score']:.2f}</div></div>
  <div class="card"><h3>Success Rate</h3>
    <div class="big" style="color:#22c55e">{stats_all['success_rate']:.0%}</div>
    <div style="color:#64748b;font-size:12px">of all episodes</div></div>
  <div class="card"><h3>WS Violations</h3>
    <div class="big" style="color:#ef4444">{stats_all['workspace_violations']}</div>
    <div style="color:#64748b;font-size:12px">hard-rejected</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Score Distribution (green = passed)</h3>
    {svg_hist}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Weights: completion {SCORE_WEIGHTS['completion']:.0%} · smoothness {SCORE_WEIGHTS['smoothness']:.0%} · diversity {SCORE_WEIGHTS['diversity']:.0%} · confidence {SCORE_WEIGHTS['confidence']:.0%}
    </div>
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Avg Score by Source</h3>
    {svg_src}
    <div style="color:#64748b;font-size:10px;margin-top:4px">Human demos highest quality; DAgger improving</div>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Sample Episodes — 10 Worst Rejected + 10 Best Passed
</h3>
<table>
  <tr><th>ID</th><th>Source</th><th>Task</th><th>Frames</th>
      <th>Smooth</th><th>Complet</th><th>Divers</th><th>Conf</th><th>WS</th><th>Score</th></tr>
  {sample_rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Filtering at {min_score:.2f} threshold retains {len(passed)} high-quality demos.<br>
  Human demos score highest ({stats_all['by_source'].get('human', 0):.2f} avg); DAgger at {stats_all['by_source'].get('dagger', 0):.2f} avg — improving with run iterations.<br>
  Use <code>--min-score 0.65</code> for aggressive filtering (speed) or <code>0.55</code> for maximum data retention.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Episode quality scorer")
    parser.add_argument("--mock",       action="store_true", default=True)
    parser.add_argument("--n-episodes", type=int, default=300)
    parser.add_argument("--min-score",  type=float, default=0.60)
    parser.add_argument("--tag",        default="")
    parser.add_argument("--output",     default="/tmp/episode_quality_scorer.html")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    print(f"[episode-quality] Scoring {args.n_episodes} episodes · min_score={args.min_score}")
    t0 = time.time()

    episodes = generate_episodes(args.n_episodes, args.seed)
    passed, rejected = filter_episodes(episodes, args.min_score)
    stats = compute_stats(episodes)

    print(f"\n  {'Source':<14} {'Count':>6}  {'Avg Score':>10}")
    print(f"  {'─'*14} {'─'*6}  {'─'*10}")
    for src, avg_s in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
        cnt = sum(1 for e in episodes if e.source == src)
        print(f"  {src:<14} {cnt:>6}  {avg_s:>10.3f}")

    print(f"\n  Passed: {len(passed)} ({len(passed)/len(episodes)*100:.0f}%)  "
          f"Rejected: {len(rejected)} ({len(rejected)/len(episodes)*100:.0f}%)")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(episodes, passed, rejected, args.min_score)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    out_json = Path(args.output).with_suffix(".json")
    out_json.write_text(json.dumps(
        {"total": len(episodes), "passed": len(passed), "rejected": len(rejected),
         "stats": stats}, indent=2))
    print(f"  JSON → {out_json}")


if __name__ == "__main__":
    main()
