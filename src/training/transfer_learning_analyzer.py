#!/usr/bin/env python3
"""
transfer_learning_analyzer.py — Analyzes transfer learning efficiency across robot embodiments.

Measures how well GR00T fine-tuned on one robot/task transfers to unseen robots and tasks.
Reports zero-shot transfer, few-shot adaptation curves, and negative transfer detection.

Usage:
    python src/training/transfer_learning_analyzer.py --mock --output /tmp/transfer_learning_analyzer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


SOURCE_ROBOTS  = ["franka_panda", "ur5e", "kinova_gen3"]
TARGET_ROBOTS  = ["xarm7", "sawyer", "iiwa7", "jaco2"]
SHOT_COUNTS    = [0, 5, 10, 20, 50, 100]   # demos for few-shot adaptation
SOURCE_TASKS   = ["pick_and_place", "stack_blocks", "door_opening"]
TARGET_TASKS   = ["drawer_pull", "tool_use", "pouring", "button_press"]


@dataclass
class FewShotCurve:
    target_robot: str
    source_robot: str
    shots: list[int]
    success_rates: list[float]   # SR at each shot count
    zero_shot_sr: float
    plateau_sr: float
    shots_to_plateau: int        # how many demos to reach 90% of plateau


@dataclass
class TransferMatrix:
    """Cross-task transfer: source_task → target_task zero-shot SR"""
    source_task: str
    target_task: str
    transfer_sr: float
    baseline_sr: float          # training from scratch with 0 demos
    transfer_gain: float        # transfer_sr - baseline_sr (can be negative)


@dataclass
class TransferReport:
    best_source_robot: str       # most transferable source
    best_source_task: str
    negative_transfer_pairs: list[tuple[str, str]]
    avg_zero_shot_sr: float
    avg_few_shot_100_sr: float
    few_shot_curves: list[FewShotCurve] = field(default_factory=list)
    task_transfer_matrix: list[TransferMatrix] = field(default_factory=list)


def simulate_transfer(seed: int = 42) -> TransferReport:
    rng = random.Random(seed)

    # Robot transfer similarity matrix (higher = more transferable)
    robot_similarity = {
        ("franka_panda", "xarm7"):   0.82,
        ("franka_panda", "sawyer"):  0.71,
        ("franka_panda", "iiwa7"):   0.88,
        ("franka_panda", "jaco2"):   0.64,
        ("ur5e",         "xarm7"):   0.75,
        ("ur5e",         "sawyer"):  0.68,
        ("ur5e",         "iiwa7"):   0.72,
        ("ur5e",         "jaco2"):   0.79,
        ("kinova_gen3",  "xarm7"):   0.70,
        ("kinova_gen3",  "sawyer"):  0.65,
        ("kinova_gen3",  "iiwa7"):   0.74,
        ("kinova_gen3",  "jaco2"):   0.85,
    }

    few_shot_curves: list[FewShotCurve] = []
    for src in SOURCE_ROBOTS:
        for tgt in TARGET_ROBOTS:
            sim = robot_similarity.get((src, tgt), 0.65)
            zero_sr = sim * 0.55 + rng.gauss(0, 0.04)
            zero_sr = max(0.1, min(0.8, zero_sr))
            plateau = min(0.92, zero_sr + 0.25 + rng.gauss(0, 0.03))

            shots_vals: list[float] = []
            for k in SHOT_COUNTS:
                if k == 0:
                    shots_vals.append(round(zero_sr, 3))
                else:
                    # Logarithmic saturation curve
                    gain = (plateau - zero_sr) * (1 - math.exp(-k / 20))
                    sr = zero_sr + gain + rng.gauss(0, 0.015)
                    sr = max(zero_sr - 0.02, min(plateau + 0.02, sr))
                    shots_vals.append(round(sr, 3))

            # Shots to plateau (90% of plateau gain)
            target_sr = zero_sr + 0.9 * (plateau - zero_sr)
            shots_to_plateau = 100  # default
            for k, sr in zip(SHOT_COUNTS, shots_vals):
                if sr >= target_sr:
                    shots_to_plateau = k
                    break

            few_shot_curves.append(FewShotCurve(
                target_robot=tgt, source_robot=src,
                shots=SHOT_COUNTS,
                success_rates=shots_vals,
                zero_shot_sr=round(zero_sr, 3),
                plateau_sr=round(plateau, 3),
                shots_to_plateau=shots_to_plateau,
            ))

    # Task transfer matrix
    task_similarity = {
        ("pick_and_place", "drawer_pull"):    (0.72, 0.40),
        ("pick_and_place", "tool_use"):       (0.58, 0.35),
        ("pick_and_place", "pouring"):        (0.61, 0.32),
        ("pick_and_place", "button_press"):   (0.68, 0.38),
        ("stack_blocks",   "drawer_pull"):    (0.65, 0.40),
        ("stack_blocks",   "tool_use"):       (0.44, 0.35),  # negative transfer candidate
        ("stack_blocks",   "pouring"):        (0.41, 0.32),  # negative transfer
        ("stack_blocks",   "button_press"):   (0.70, 0.38),
        ("door_opening",   "drawer_pull"):    (0.81, 0.40),
        ("door_opening",   "tool_use"):       (0.69, 0.35),
        ("door_opening",   "pouring"):        (0.52, 0.32),
        ("door_opening",   "button_press"):   (0.75, 0.38),
    }

    task_transfer: list[TransferMatrix] = []
    negative_pairs: list[tuple[str, str]] = []

    for (src_task, tgt_task), (transfer_sr_base, baseline_base) in task_similarity.items():
        t_sr = transfer_sr_base + rng.gauss(0, 0.03)
        b_sr = baseline_base + rng.gauss(0, 0.02)
        gain = t_sr - b_sr
        if gain < 0:
            negative_pairs.append((src_task, tgt_task))
        task_transfer.append(TransferMatrix(
            source_task=src_task, target_task=tgt_task,
            transfer_sr=round(max(0.1, t_sr), 3),
            baseline_sr=round(max(0.05, b_sr), 3),
            transfer_gain=round(gain, 3),
        ))

    # Find best source robot (highest avg zero-shot)
    src_zero = {}
    for src in SOURCE_ROBOTS:
        curves = [c for c in few_shot_curves if c.source_robot == src]
        src_zero[src] = sum(c.zero_shot_sr for c in curves) / len(curves)
    best_src_robot = max(src_zero, key=src_zero.get)

    # Best source task (highest avg transfer gain)
    task_gain = {}
    for src_task in SOURCE_TASKS:
        entries = [m for m in task_transfer if m.source_task == src_task]
        task_gain[src_task] = sum(m.transfer_gain for m in entries) / len(entries)
    best_src_task = max(task_gain, key=task_gain.get)

    all_zero = [c.zero_shot_sr for c in few_shot_curves]
    all_100 = [c.success_rates[-1] for c in few_shot_curves]

    return TransferReport(
        best_source_robot=best_src_robot,
        best_source_task=best_src_task,
        negative_transfer_pairs=negative_pairs,
        avg_zero_shot_sr=round(sum(all_zero) / len(all_zero), 3),
        avg_few_shot_100_sr=round(sum(all_100) / len(all_100), 3),
        few_shot_curves=few_shot_curves,
        task_transfer_matrix=task_transfer,
    )


def render_html(report: TransferReport) -> str:
    SOURCE_COLORS = {"franka_panda": "#22c55e", "ur5e": "#3b82f6", "kinova_gen3": "#f59e0b"}
    GAIN_COLORS   = lambda g: "#22c55e" if g > 0.1 else "#f59e0b" if g > 0 else "#ef4444"

    # SVG: few-shot curves (average across target robots, per source robot)
    w, h, ml, mr, mt, mb = 480, 240, 55, 20, 20, 40
    inner_w = w - ml - mr
    inner_h = h - mt - mb

    svg_fs = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_fs += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_fs += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'

    for v in [0.25, 0.50, 0.75, 1.0]:
        y = h - mb - v * inner_h
        svg_fs += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                   f'stroke="#1e293b" stroke-width="1"/>')
        svg_fs += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                   f'font-size="8" text-anchor="end">{v:.0%}</text>')

    x_positions = [ml + i / (len(SHOT_COUNTS) - 1) * inner_w for i in range(len(SHOT_COUNTS))]
    for x, k in zip(x_positions, SHOT_COUNTS):
        svg_fs += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                   f'font-size="8" text-anchor="middle">{k}</text>')
    svg_fs += (f'<text x="{ml + inner_w/2:.1f}" y="{h-mb+24}" fill="#64748b" '
               f'font-size="8" text-anchor="middle">Adaptation demos (shots)</text>')

    for src in SOURCE_ROBOTS:
        col = SOURCE_COLORS[src]
        curves = [c for c in report.few_shot_curves if c.source_robot == src]
        # Average SR at each shot count
        avg_sr = [sum(c.success_rates[i] for c in curves) / len(curves)
                  for i in range(len(SHOT_COUNTS))]
        pts = [(x_positions[i], h - mb - avg_sr[i] * inner_h) for i in range(len(SHOT_COUNTS))]
        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_fs += (f'<polyline points="{pstr}" fill="none" stroke="{col}" '
                   f'stroke-width="2" opacity="0.9"/>')
        for x, y in pts:
            svg_fs += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{col}"/>'

    # Legend
    for i, (src, col) in enumerate(SOURCE_COLORS.items()):
        svg_fs += (f'<rect x="{ml}" y="{mt+2+i*13}" width="8" height="2" fill="{col}"/>'
                   f'<text x="{ml+11}" y="{mt+10+i*13}" fill="#94a3b8" font-size="8">{src}</text>')

    svg_fs += '</svg>'

    # SVG: task transfer heatmap (source_task × target_task, color = transfer_gain)
    th_w, th_h = 380, 200
    th_ml, th_mt = 100, 40
    cell_w = (th_w - th_ml - 20) / len(TARGET_TASKS)
    cell_h = (th_h - th_mt - 20) / len(SOURCE_TASKS)

    svg_heat = f'<svg width="{th_w}" height="{th_h}" style="background:#0f172a;border-radius:8px">'

    # Header labels
    for j, tgt in enumerate(TARGET_TASKS):
        x = th_ml + j * cell_w + cell_w / 2
        svg_heat += (f'<text x="{x:.1f}" y="{th_mt - 6}" fill="#94a3b8" '
                     f'font-size="7.5" text-anchor="middle">{tgt.replace("_", " ")}</text>')

    for i, src in enumerate(SOURCE_TASKS):
        y = th_mt + i * cell_h + cell_h / 2
        svg_heat += (f'<text x="{th_ml - 4}" y="{y + 4:.1f}" fill="#94a3b8" '
                     f'font-size="8" text-anchor="end">{src.replace("_", " ")}</text>')
        for j, tgt in enumerate(TARGET_TASKS):
            m = next((m for m in report.task_transfer_matrix
                      if m.source_task == src and m.target_task == tgt), None)
            if m:
                gain = m.transfer_gain
                if gain > 0.15:
                    fill = "#14532d"
                elif gain > 0.05:
                    fill = "#166534"
                elif gain > 0:
                    fill = "#1a4731"
                else:
                    fill = "#7f1d1d"  # red for negative transfer

                cx = th_ml + j * cell_w
                cy = th_mt + i * cell_h
                svg_heat += (f'<rect x="{cx:.1f}" y="{cy:.1f}" '
                             f'width="{cell_w - 2:.1f}" height="{cell_h - 2:.1f}" fill="{fill}" rx="2"/>')
                txt_col = "#86efac" if gain > 0 else "#fca5a5"
                svg_heat += (f'<text x="{cx + cell_w/2:.1f}" y="{cy + cell_h/2 + 4:.1f}" '
                             f'fill="{txt_col}" font-size="8.5" text-anchor="middle">'
                             f'{m.transfer_sr:.0%}</text>')

    svg_heat += '</svg>'

    # Table
    rows = ""
    for m in sorted(report.task_transfer_matrix, key=lambda x: x.transfer_gain, reverse=True):
        gc = GAIN_COLORS(m.transfer_gain)
        rows += (f'<tr>'
                 f'<td style="color:#94a3b8">{m.source_task}</td>'
                 f'<td style="color:#94a3b8">{m.target_task}</td>'
                 f'<td style="color:#e2e8f0">{m.transfer_sr:.1%}</td>'
                 f'<td style="color:#64748b">{m.baseline_sr:.1%}</td>'
                 f'<td style="color:{gc};font-weight:bold">{m.transfer_gain:+.3f}</td>'
                 f'</tr>')

    neg_str = "; ".join(f"{s}→{t}" for s, t in report.negative_transfer_pairs)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Transfer Learning Analyzer</title>
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
<h1>Transfer Learning Analyzer</h1>
<div class="meta">
  {len(SOURCE_ROBOTS)} source robots · {len(TARGET_ROBOTS)} target robots · {len(SOURCE_TASKS)} source tasks · {len(TARGET_TASKS)} target tasks
</div>

<div class="grid">
  <div class="card"><h3>Best Source Robot</h3>
    <div style="color:#22c55e;font-size:13px;font-weight:bold">{report.best_source_robot}</div>
    <div class="big" style="color:#22c55e">{report.avg_zero_shot_sr:.1%}</div>
    <div style="color:#64748b;font-size:10px">avg zero-shot SR</div>
  </div>
  <div class="card"><h3>100-shot SR (avg)</h3>
    <div class="big" style="color:#3b82f6">{report.avg_few_shot_100_sr:.1%}</div>
    <div style="color:#64748b;font-size:10px">few-shot adaptation</div>
  </div>
  <div class="card"><h3>Best Source Task</h3>
    <div style="color:#f59e0b;font-size:13px;font-weight:bold">{report.best_source_task}</div>
    <div style="color:#64748b;font-size:10px">highest avg transfer gain</div>
  </div>
  <div class="card"><h3>Negative Transfer</h3>
    <div class="big" style="color:#ef4444">{len(report.negative_transfer_pairs)}</div>
    <div style="color:#64748b;font-size:10px">task pairs harmed by transfer</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Few-Shot Adaptation Curves (avg across {len(TARGET_ROBOTS)} target robots)</h3>
    {svg_fs}
  </div>
  <div>
    <h3 class="sec">Task Transfer Matrix (zero-shot SR)</h3>
    {svg_heat}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      <span style="color:#86efac">■</span> positive transfer &nbsp;
      <span style="color:#fca5a5">■</span> negative transfer
    </div>
  </div>
</div>

<h3 class="sec">Task Transfer Detail</h3>
<table>
  <tr><th>Source Task</th><th>Target Task</th><th>Transfer SR</th>
      <th>Baseline SR</th><th>Transfer Gain</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">TRANSFER INSIGHTS</div>
  <div style="color:#22c55e">door_opening → drawer_pull: highest transfer (0.81 SR, 0.41 gain) — shared hinge dynamics</div>
  <div style="color:#f59e0b">franka_panda → iiwa7: best robot transfer (similar kinematics, 0.88 similarity score)</div>
  <div style="color:#ef4444">Negative transfer: {neg_str} — dissimilar action spaces; train from scratch</div>
  <div style="color:#64748b;margin-top:4px">GR00T universal embodiment encoder reduces robot-specific adaptation to ~20 demos</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Transfer learning analyzer for GR00T policies")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/transfer_learning_analyzer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[transfer] {len(SOURCE_ROBOTS)} src robots × {len(TARGET_ROBOTS)} tgt robots "
          f"× {len(SOURCE_TASKS)} src tasks × {len(TARGET_TASKS)} tgt tasks")
    t0 = time.time()

    report = simulate_transfer(args.seed)

    print(f"\n  Task Transfer Matrix (transfer_sr / gain):")
    print(f"  {'Source':<18} {'Target':<16} {'Transfer SR':>12} {'Baseline':>10} {'Gain':>8}")
    print(f"  {'─'*18} {'─'*16} {'─'*12} {'─'*10} {'─'*8}")
    for m in sorted(report.task_transfer_matrix, key=lambda x: x.transfer_gain, reverse=True):
        flag = " ✗" if m.transfer_gain < 0 else ""
        print(f"  {m.source_task:<18} {m.target_task:<16} {m.transfer_sr:>11.1%} "
              f"{m.baseline_sr:>9.1%} {m.transfer_gain:>+7.3f}{flag}")

    print(f"\n  Best source robot: {report.best_source_robot} (avg zero-shot {report.avg_zero_shot_sr:.1%})")
    print(f"  Negative transfer pairs: {report.negative_transfer_pairs}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "best_source_robot": report.best_source_robot,
        "best_source_task": report.best_source_task,
        "avg_zero_shot_sr": report.avg_zero_shot_sr,
        "negative_transfer_pairs": [list(p) for p in report.negative_transfer_pairs],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
