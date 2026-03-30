#!/usr/bin/env python3
"""
embodiment_transfer_benchmark.py

Benchmarks how well a GR00T-based policy trained on one robot embodiment
transfers to other robot embodiments.  Covers zero-shot and few-shot (10 / 50
demo) transfer across a 5x5 source/target robot matrix.

Usage:
    python embodiment_transfer_benchmark.py --mock --output /tmp/embodiment_transfer_benchmark.html --seed 42
"""

import argparse
import json
import math
import os
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


ROBOTS: List[str] = [
    "franka_panda",
    "kinova_gen3",
    "ur10",
    "xarm7",
    "widowx",
]

TRANSFER_MODES: List[str] = ["zero_shot", "few_shot_10demo", "few_shot_50demo"]

_SIM_MATRIX: Dict[Tuple[str, str], float] = {
    ("franka_panda",  "franka_panda"):  1.00,
    ("franka_panda",  "kinova_gen3"):   0.81,
    ("franka_panda",  "ur10"):          0.68,
    ("franka_panda",  "xarm7"):         0.85,
    ("franka_panda",  "widowx"):        0.42,
    ("kinova_gen3",   "franka_panda"):  0.79,
    ("kinova_gen3",   "kinova_gen3"):   1.00,
    ("kinova_gen3",   "ur10"):          0.72,
    ("kinova_gen3",   "xarm7"):         0.83,
    ("kinova_gen3",   "widowx"):        0.45,
    ("ur10",          "franka_panda"):  0.65,
    ("ur10",          "kinova_gen3"):   0.70,
    ("ur10",          "ur10"):          1.00,
    ("ur10",          "xarm7"):         0.73,
    ("ur10",          "widowx"):        0.30,
    ("xarm7",         "franka_panda"):  0.84,
    ("xarm7",         "kinova_gen3"):   0.80,
    ("xarm7",         "ur10"):          0.74,
    ("xarm7",         "xarm7"):         1.00,
    ("xarm7",         "widowx"):        0.44,
    ("widowx",        "franka_panda"):  0.40,
    ("widowx",        "kinova_gen3"):   0.43,
    ("widowx",        "ur10"):          0.28,
    ("widowx",        "xarm7"):         0.41,
    ("widowx",        "widowx"):        1.00,
}

_RANDOM_BASELINE: Dict[str, float] = {
    "franka_panda": 0.24,
    "kinova_gen3":  0.22,
    "ur10":         0.20,
    "xarm7":        0.22,
    "widowx":       0.22,
}

_SOURCE_SELF_SR: Dict[str, float] = {
    "franka_panda": 0.78,
    "kinova_gen3":  0.74,
    "ur10":         0.71,
    "xarm7":        0.76,
    "widowx":       0.65,
}


@dataclass
class TransferResult:
    source: str
    target: str
    mode: str
    sr: float
    mae: float
    adaptation_cost_steps: int
    negative_transfer: bool
    notes: str = ""


@dataclass
class BenchmarkSummary:
    generated_at: str
    seed: int
    robots: List[str]
    modes: List[str]
    results: List[TransferResult]
    random_baselines: Dict[str, float]
    source_self_sr: Dict[str, float]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def simulate_transfer_results(seed: int = 42) -> List[TransferResult]:
    results: List[TransferResult] = []
    for src in ROBOTS:
        for tgt in ROBOTS:
            rng = random.Random(seed + abs(hash(f"{src}_{tgt}")) % 100_000)

            def noise(scale: float = 0.03) -> float:
                return rng.gauss(0, scale)

            sim = _SIM_MATRIX[(src, tgt)]
            src_sr = _SOURCE_SELF_SR[src]
            rand_baseline = _RANDOM_BASELINE[tgt]

            if src == tgt:
                zs_sr = src_sr + noise(0.01)
            elif (src, tgt) == ("franka_panda", "kinova_gen3"):
                zs_sr = 0.31 + noise(0.005)
            elif (src, tgt) == ("ur10", "widowx"):
                zs_sr = rand_baseline - 0.08 + noise(0.005)
            else:
                zs_sr = _clamp(src_sr * sim * 0.60 + noise(0.03))

            zs_sr = round(_clamp(zs_sr, lo=-0.05), 4)
            zs_mae = round(_clamp(0.28 - 0.22 * max(zs_sr, 0) + abs(noise(0.02)), lo=0.04, hi=0.48), 4)

            results.append(TransferResult(
                source=src, target=tgt, mode="zero_shot",
                sr=zs_sr, mae=zs_mae, adaptation_cost_steps=0,
                negative_transfer=(zs_sr < rand_baseline and src != tgt),
                notes=("negative transfer" if (src, tgt) == ("ur10", "widowx") else ""),
            ))

            if src == tgt:
                fs10_sr = src_sr + noise(0.01)
            else:
                delta = _clamp(0.10 + sim * 0.12 + noise(0.02), lo=0.0, hi=0.20)
                fs10_sr = _clamp(max(zs_sr, 0) + delta + noise(0.02))

            fs10_sr = round(_clamp(fs10_sr), 4)
            fs10_mae = round(_clamp(zs_mae - 0.06 * sim + noise(0.015), lo=0.03), 4)
            fs10_steps = int(rng.randint(200, 600))

            results.append(TransferResult(
                source=src, target=tgt, mode="few_shot_10demo",
                sr=fs10_sr, mae=fs10_mae, adaptation_cost_steps=fs10_steps,
                negative_transfer=False,
            ))

            if src == tgt:
                fs50_sr = _clamp(src_sr + 0.02 + noise(0.01))
            else:
                target_sr = _clamp(0.65 + (sim - 0.75) * 0.18 + noise(0.025))
                fs50_sr = _clamp(fs10_sr * 0.35 + target_sr * 0.65 + noise(0.02))

            fs50_sr = round(_clamp(fs50_sr), 4)
            fs50_mae = round(_clamp(fs10_mae - 0.07 * sim + noise(0.012), lo=0.02), 4)
            fs50_steps = int(rng.randint(800, 2500))

            results.append(TransferResult(
                source=src, target=tgt, mode="few_shot_50demo",
                sr=fs50_sr, mae=fs50_mae, adaptation_cost_steps=fs50_steps,
                negative_transfer=False,
            ))

    return results


def build_summary(results: List[TransferResult], seed: int) -> BenchmarkSummary:
    return BenchmarkSummary(
        generated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        seed=seed, robots=ROBOTS, modes=TRANSFER_MODES, results=results,
        random_baselines=_RANDOM_BASELINE, source_self_sr=_SOURCE_SELF_SR,
    )


def _heatmap_svg(results: List[TransferResult], mode: str, width: int = 400) -> str:
    cell_size = 64
    label_pad = 80
    title_h = 30
    legend_h = 28
    n = len(ROBOTS)
    W = label_pad + n * cell_size + 10
    H = title_h + label_pad + n * cell_size + legend_h + 10

    sr_map: Dict[Tuple[str, str], float] = {}
    neg_map: Dict[Tuple[str, str], bool] = {}
    for r in results:
        if r.mode == mode:
            sr_map[(r.source, r.target)] = r.sr
            neg_map[(r.source, r.target)] = r.negative_transfer

    def cell_color(sr: float, negative: bool) -> str:
        if negative:
            return "#7c2d12"
        t = _clamp(sr)
        r_lo, g_lo, b_lo = 0x33, 0x41, 0x55
        r_hi, g_hi, b_hi = 0xC7, 0x46, 0x34
        ri = int(r_lo + (r_hi - r_lo) * t)
        gi = int(g_lo + (g_hi - g_lo) * t)
        bi = int(b_lo + (b_hi - b_lo) * t)
        return f"#{ri:02x}{gi:02x}{bi:02x}"

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;font-family:monospace">')
    mode_label = mode.replace("_", " ").title()
    lines.append(f'<text x="{W // 2}" y="20" text-anchor="middle" fill="#C74634" font-size="13" font-weight="bold">{mode_label}</text>')

    ox = label_pad
    oy = title_h + label_pad

    for j, tgt in enumerate(ROBOTS):
        cx = ox + j * cell_size + cell_size // 2
        parts = tgt.split("_")
        lines.append(f'<text x="{cx}" y="{oy - 36}" text-anchor="middle" fill="#94a3b8" font-size="9">{parts[0]}</text>')
        if len(parts) > 1:
            lines.append(f'<text x="{cx}" y="{oy - 24}" text-anchor="middle" fill="#94a3b8" font-size="9">{parts[1]}</text>')
        lines.append(f'<text x="{cx}" y="{oy - 10}" text-anchor="middle" fill="#64748b" font-size="8">target</text>')

    for i, src in enumerate(ROBOTS):
        cy_center = oy + i * cell_size + cell_size // 2
        parts = src.split("_")
        lines.append(f'<text x="{ox - 6}" y="{cy_center - 6}" text-anchor="end" fill="#94a3b8" font-size="9">{parts[0]}</text>')
        if len(parts) > 1:
            lines.append(f'<text x="{ox - 6}" y="{cy_center + 6}" text-anchor="end" fill="#94a3b8" font-size="9">{parts[1]}</text>')
        for j, tgt in enumerate(ROBOTS):
            sr = sr_map.get((src, tgt), 0.0)
            negative = neg_map.get((src, tgt), False)
            color = cell_color(sr, negative)
            cx = ox + j * cell_size
            cy = oy + i * cell_size
            border = ' stroke="#C74634" stroke-width="2"' if src == tgt else ' stroke="#0f172a" stroke-width="1"'
            lines.append(f'<rect x="{cx}" y="{cy}" width="{cell_size}" height="{cell_size}" fill="{color}"{border}/>')
            text_color = "#f8fafc" if sr > 0.35 else "#94a3b8"
            lines.append(f'<text x="{cx + cell_size // 2}" y="{cy + cell_size // 2 + 5}" text-anchor="middle" fill="{text_color}" font-size="11" font-weight="bold">{sr:.2f}</text>')
            if negative:
                lines.append(f'<text x="{cx + cell_size // 2}" y="{cy + cell_size // 2 + 17}" text-anchor="middle" fill="#fca5a5" font-size="8">neg</text>')

    mid_x = ox + (n * cell_size) // 2
    lines.append(f'<text x="{mid_x}" y="{H - 4}" text-anchor="middle" fill="#475569" font-size="9">Target Robot \u2192</text>')
    mid_y = oy + (n * cell_size) // 2
    lines.append(f'<text x="10" y="{mid_y}" text-anchor="middle" fill="#475569" font-size="9" transform="rotate(-90,10,{mid_y})">Source \u2192</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def _bar_chart_svg(results: List[TransferResult]) -> str:
    W, H = 780, 300
    pad_l, pad_b, pad_t, pad_r = 50, 60, 30, 20
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_b - pad_t
    n = len(ROBOTS)
    group_w = chart_w / n
    bar_gap = 6
    bar_w = (group_w - bar_gap * 3) / 2

    def avg_sr(tgt: str, mode: str) -> float:
        vals = [r.sr for r in results if r.target == tgt and r.mode == mode and r.source != tgt]
        return sum(vals) / len(vals) if vals else 0.0

    zero_vals = {tgt: avg_sr(tgt, "zero_shot") for tgt in ROBOTS}
    fs50_vals = {tgt: avg_sr(tgt, "few_shot_50demo") for tgt in ROBOTS}
    max_val = max(max(zero_vals.values()), max(fs50_vals.values()), 0.01)
    y_scale = chart_h / (max_val * 1.1)

    def bar_y(v):
        return pad_t + chart_h - v * y_scale

    def bar_h(v):
        return v * y_scale

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;font-family:sans-serif">')

    for tick in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        if tick > max_val * 1.1:
            break
        ty = bar_y(tick)
        lines.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{W - pad_r}" y2="{ty:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{pad_l - 4}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{tick:.1f}</text>')

    for i, tgt in enumerate(ROBOTS):
        gx = pad_l + i * group_w + bar_gap
        zs = zero_vals[tgt]
        fs50 = fs50_vals[tgt]
        by_zs = bar_y(zs)
        bh_zs = bar_h(zs)
        lines.append(f'<rect x="{gx:.1f}" y="{by_zs:.1f}" width="{bar_w:.1f}" height="{bh_zs:.1f}" fill="#3b82f6" rx="2"/>')
        lines.append(f'<text x="{gx + bar_w / 2:.1f}" y="{by_zs - 4:.1f}" text-anchor="middle" fill="#93c5fd" font-size="9">{zs:.2f}</text>')
        bx2 = gx + bar_w + bar_gap
        by_fs = bar_y(fs50)
        bh_fs = bar_h(fs50)
        lines.append(f'<rect x="{bx2:.1f}" y="{by_fs:.1f}" width="{bar_w:.1f}" height="{bh_fs:.1f}" fill="#C74634" rx="2"/>')
        lines.append(f'<text x="{bx2 + bar_w / 2:.1f}" y="{by_fs - 4:.1f}" text-anchor="middle" fill="#fca5a5" font-size="9">{fs50:.2f}</text>')
        delta = fs50 - zs
        mid_x = gx + bar_w + bar_gap / 2
        arrow_y = min(by_zs, by_fs) - 10
        lines.append(f'<text x="{mid_x + bar_w / 2:.1f}" y="{arrow_y:.1f}" text-anchor="middle" fill="#4ade80" font-size="8">+{delta:.2f}</text>')
        parts = tgt.split("_")
        label_y = H - pad_b + 14
        cx = gx + bar_w + bar_gap / 2
        lines.append(f'<text x="{cx:.1f}" y="{label_y}" text-anchor="middle" fill="#94a3b8" font-size="10">{parts[0]}</text>')
        if len(parts) > 1:
            lines.append(f'<text x="{cx:.1f}" y="{label_y + 12}" text-anchor="middle" fill="#94a3b8" font-size="10">{parts[1]}</text>')

    legend_x = W - pad_r - 200
    legend_y = pad_t
    for lx, color, label in [(legend_x, "#3b82f6", "Zero-shot"), (legend_x + 100, "#C74634", "Few-shot 50demo")]:
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{legend_y + 10}" fill="#94a3b8" font-size="10">{label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def render_html(summary: BenchmarkSummary) -> str:
    results = summary.results
    heatmaps = {mode: _heatmap_svg(results, mode) for mode in TRANSFER_MODES}
    bar_svg = _bar_chart_svg(results)

    spotlights = [r for r in results
        if (r.source == "franka_panda" and r.target == "kinova_gen3" and r.mode == "zero_shot")
        or (r.source == "franka_panda" and r.target == "franka_panda" and r.mode == "zero_shot")
        or (r.source == "ur10" and r.target == "widowx" and r.mode == "zero_shot")
        or (r.source == "franka_panda" and r.target == "kinova_gen3" and r.mode == "few_shot_50demo")]

    def _spotlight_row(r):
        sr_color = "#4ade80" if r.sr >= 0.6 else "#f59e0b" if r.sr >= 0.35 else "#f87171"
        neg_cell = '<span style="color:#fca5a5">&lt; random baseline</span>' if r.negative_transfer else ""
        return (f'<tr style="background:#0f2233"><td><b>{r.source}</b></td><td><b>{r.target}</b></td>'
                f'<td style="color:#94a3b8;font-size:11px">{r.mode.replace("_"," ")}</td>'
                f'<td style="font-weight:bold;color:{sr_color}">{r.sr:.3f}</td>'
                f'<td>{r.mae:.3f}</td><td>{r.adaptation_cost_steps:,}</td><td>{neg_cell}</td></tr>')

    spotlight_rows_html = "".join(_spotlight_row(r) for r in spotlights)

    hm_tabs = ""
    hm_panels = ""
    for idx, mode in enumerate(TRANSFER_MODES):
        display = "block" if idx == 0 else "none"
        tab_active = "background:#C74634;color:#fff" if idx == 0 else "background:#1e3a5f;color:#94a3b8"
        hm_tabs += (f'<button onclick="showHeatmap(\'{mode}\')" id="tab_{mode}" '
                    f'style="{tab_active};border:none;padding:6px 14px;cursor:pointer;border-radius:4px;font-size:12px;margin-right:6px">'
                    f'{mode.replace("_"," ").title()}</button>')
        hm_panels += f'<div id="hm_{mode}" style="display:{display};margin-top:12px">{heatmaps[mode]}</div>'

    js_hide = "; ".join(f'document.getElementById("hm_{m}").style.display="none"' for m in TRANSFER_MODES)
    js_reset = "; ".join(f'document.getElementById("tab_{m}").style.background="#1e3a5f"; document.getElementById("tab_{m}").style.color="#94a3b8"' for m in TRANSFER_MODES)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>Embodiment Transfer Benchmark</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;font-size:22px;margin-bottom:4px}}h2{{color:#C74634;font-size:15px;margin:28px 0 10px}}
.meta{{color:#64748b;font-size:12px;margin-bottom:20px}}.card{{background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;padding:18px;margin-bottom:22px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}th{{background:#1e3a5f;color:#94a3b8;text-align:left;padding:7px 10px;font-weight:600;font-size:11px}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b;vertical-align:middle}}tr:hover td{{background:#172033}}</style></head>
<body><h1>Embodiment Transfer Benchmark</h1>
<div class="meta">GR00T policy \u00b7 5-robot matrix \u00b7 3 transfer modes \u00b7 Generated {summary.generated_at} \u00b7 seed={summary.seed}</div>
<h2>Spotlight Results</h2><div class="card"><table><thead><tr><th>Source</th><th>Target</th><th>Mode</th><th>SR</th><th>MAE</th><th>Adapt Steps</th><th>Flags</th></tr></thead><tbody>{spotlight_rows_html}</tbody></table></div>
<h2>Transfer Heatmaps (5x5 SR Matrix)</h2><div class="card"><div>{hm_tabs}</div>{hm_panels}</div>
<h2>Zero-Shot vs Few-Shot 50-Demo SR per Target Robot</h2><div class="card">{bar_svg}</div>
<script>function showHeatmap(mode){{{js_hide}; document.getElementById("hm_"+mode).style.display="block";
{js_reset}; document.getElementById("tab_"+mode).style.background="#C74634"; document.getElementById("tab_"+mode).style.color="#fff";}}</script>
<footer style="margin-top:32px;color:#334155;font-size:11px;text-align:center">OCI Robot Cloud \u00b7 GR00T Embodiment Transfer Benchmark</footer></body></html>"""


def to_json(summary: BenchmarkSummary) -> str:
    d = {"generated_at": summary.generated_at, "seed": summary.seed, "robots": summary.robots,
         "modes": summary.modes, "random_baselines": summary.random_baselines,
         "source_self_sr": summary.source_self_sr, "results": [asdict(r) for r in summary.results]}
    return json.dumps(d, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embodiment transfer benchmark for GR00T-based policies.")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--no-mock", dest="mock", action="store_false")
    parser.add_argument("--output", default="/tmp/embodiment_transfer_benchmark.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"[embodiment_transfer_benchmark] Running mock benchmark (seed={args.seed}) ...")
    results = simulate_transfer_results(seed=args.seed)
    summary = build_summary(results, seed=args.seed)
    html = render_html(summary)
    json_str = to_json(summary)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[embodiment_transfer_benchmark] HTML report saved \u2192 {args.output}")

    json_path = os.path.splitext(args.output)[0] + ".json"
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(json_str)
    print(f"[embodiment_transfer_benchmark] JSON sidecar saved  \u2192 {json_path}")

    print(f"\n{'Source':<16} {'Target':<16} {'Mode':<20} {'SR':>6} {'MAE':>6} {'Steps':>8}")
    print("-" * 80)
    for r in sorted(results, key=lambda x: (x.source, x.target, TRANSFER_MODES.index(x.mode))):
        flag = " [NEG]" if r.negative_transfer else ""
        print(f"{r.source:<16} {r.target:<16} {r.mode:<20} {r.sr:>6.3f} {r.mae:>6.3f} {r.adaptation_cost_steps:>8,}{flag}")


if __name__ == "__main__":
    main()
