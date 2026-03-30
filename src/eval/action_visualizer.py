"""
GR00T Action Chunk Visualizer
Analyzes and visualizes 16-step action chunks produced by GR00T inference.
Supports BC vs DAgger distribution comparison.

Usage:
    python action_visualizer.py --mock --n-chunks 50 --output /tmp/action_viz.html
    python action_visualizer.py --mock --compare-bc-dagger --output /tmp/action_compare.html
"""

import argparse
import math
import random
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ActionChunk:
    chunk_id: str
    episode_id: str
    step: int
    n_joints: int                         # 7 arm + 2 gripper = 9
    actions: list[list[float]]            # shape [16, 9]
    predicted_at: str                     # ISO timestamp
    latency_ms: float
    success_flag: Optional[bool] = None


@dataclass
class ActionStats:
    chunk_id: str
    joint_means: list[float]              # length 9
    joint_stds: list[float]               # length 9
    joint_ranges: list[float]             # length 9  (max-min)
    smoothness_score: float               # lower jerk = smoother
    gripper_sequence: list[float]         # 16 gripper width values (joint index 7)
    direction_changes: list[int]          # per joint, # of sign flips in velocity
    dominant_motion_joints: list[int]     # top-3 most active joint indices


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def compute_stats(chunk: ActionChunk) -> ActionStats:
    """Compute per-joint statistics for a single action chunk."""
    n_steps = len(chunk.actions)          # 16
    n_j = chunk.n_joints                  # 9

    # Transpose: per-joint time series
    per_joint = [[chunk.actions[t][j] for t in range(n_steps)] for j in range(n_j)]

    joint_means = [_mean(per_joint[j]) for j in range(n_j)]
    joint_stds  = [_std(per_joint[j])  for j in range(n_j)]
    joint_ranges = [max(per_joint[j]) - min(per_joint[j]) for j in range(n_j)]

    # Smoothness: mean absolute jerk (3rd derivative proxy via 2nd diff of actions)
    total_jerk = 0.0
    jerk_count = 0
    for j in range(n_j):
        ts = per_joint[j]
        vel  = [ts[t+1] - ts[t]   for t in range(len(ts)-1)]
        acc  = [vel[t+1] - vel[t] for t in range(len(vel)-1)]
        jerk = [abs(acc[t+1] - acc[t]) for t in range(len(acc)-1)]
        total_jerk += sum(jerk)
        jerk_count += len(jerk)
    smoothness_score = (total_jerk / jerk_count) if jerk_count > 0 else 0.0

    # Gripper sequence (joint index 7, primary gripper)
    gripper_sequence = [chunk.actions[t][7] for t in range(n_steps)]

    # Direction changes per joint
    direction_changes = []
    for j in range(n_j):
        ts = per_joint[j]
        vel = [ts[t+1] - ts[t] for t in range(len(ts)-1)]
        changes = sum(
            1 for t in range(len(vel)-1)
            if vel[t] * vel[t+1] < 0
        )
        direction_changes.append(changes)

    # Dominant motion joints: top-3 by range
    ranked = sorted(range(n_j), key=lambda j: joint_ranges[j], reverse=True)
    dominant_motion_joints = ranked[:3]

    return ActionStats(
        chunk_id=chunk.chunk_id,
        joint_means=joint_means,
        joint_stds=joint_stds,
        joint_ranges=joint_ranges,
        smoothness_score=smoothness_score,
        gripper_sequence=gripper_sequence,
        direction_changes=direction_changes,
        dominant_motion_joints=dominant_motion_joints,
    )


# ---------------------------------------------------------------------------
# Distribution comparison
# ---------------------------------------------------------------------------

def compare_distributions(
    bc_chunks: list[ActionChunk],
    dagger_chunks: list[ActionChunk],
) -> dict:
    """
    Compare BC vs DAgger action distributions.
    Returns per-joint variance difference (KL proxy) and overall shift score.
    """
    def collect_per_joint_vals(chunks):
        n_j = 9
        per_joint = [[] for _ in range(n_j)]
        for chunk in chunks:
            for step in chunk.actions:
                for j, val in enumerate(step):
                    per_joint[j].append(val)
        return per_joint

    bc_pj   = collect_per_joint_vals(bc_chunks)
    dag_pj  = collect_per_joint_vals(dagger_chunks)

    result = {"per_joint": [], "overall_shift_score": 0.0}
    shift_total = 0.0

    for j in range(9):
        bc_var  = _std(bc_pj[j])  ** 2
        dag_var = _std(dag_pj[j]) ** 2
        bc_mean  = _mean(bc_pj[j])
        dag_mean = _mean(dag_pj[j])

        # Gaussian KL divergence proxy: KL(BC||DAgger)
        eps = 1e-8
        kl = math.log((dag_var + eps) / (bc_var + eps)) + \
             (bc_var + (bc_mean - dag_mean) ** 2) / (2 * (dag_var + eps)) - 0.5

        result["per_joint"].append({
            "joint": j,
            "bc_variance": round(bc_var, 6),
            "dagger_variance": round(dag_var, 6),
            "mean_shift": round(abs(dag_mean - bc_mean), 6),
            "kl_divergence": round(max(kl, 0.0), 6),
        })
        shift_total += abs(dag_mean - bc_mean)

    result["overall_shift_score"] = round(shift_total / 9, 6)
    return result


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def generate_mock_chunks(
    n_chunks: int,
    success_rate: float = 0.6,
    source: str = "BC",
    seed: int = 42,
) -> list[ActionChunk]:
    """
    Generate realistic mock action chunks.
    DAgger chunks have smoother trajectories and better gripper timing than BC.
    """
    rng = random.Random(seed)
    chunks = []

    is_dagger = source.upper() == "DAGGER"
    noise_scale   = 0.04 if is_dagger else 0.12   # DAgger smoother
    drift_scale   = 0.02 if is_dagger else 0.06
    gripper_noise = 0.02 if is_dagger else 0.10   # DAgger cleaner open/close

    # Nominal arm joint positions (resting pose)
    nominal = [0.0, -0.3, 0.0, -1.5, 0.0, 1.2, 0.0, 0.5, 0.5]

    for i in range(n_chunks):
        ep_id = f"ep{i // 5:03d}"
        step  = (i % 5) * 16
        success = rng.random() < success_rate

        # Build 16-step action sequence
        pos = [nominal[j] + rng.gauss(0, 0.1) for j in range(9)]
        actions = []
        for t in range(16):
            # Smooth drift + small noise
            pos = [
                pos[j] + rng.gauss(0, drift_scale) + rng.gauss(0, noise_scale) * 0.5
                for j in range(7)
            ] + [
                # Gripper: DAgger snaps cleanly, BC is noisy
                max(0.0, min(1.0,
                    (0.0 if t >= 8 else 1.0) +
                    rng.gauss(0, gripper_noise) +
                    (0.0 if is_dagger else rng.gauss(0, 0.08))
                )),
                max(0.0, min(1.0,
                    (0.0 if t >= 8 else 1.0) +
                    rng.gauss(0, gripper_noise)
                )),
            ]
            actions.append([round(v, 5) for v in pos])

        chunks.append(ActionChunk(
            chunk_id=f"{source.lower()}_{i:04d}",
            episode_id=ep_id,
            step=step,
            n_joints=9,
            actions=actions,
            predicted_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=round(rng.gauss(227, 30 if is_dagger else 60), 1),
            success_flag=success,
        ))

    return chunks


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

JOINT_LABELS = [f"J{i+1}" for i in range(7)] + ["G1", "G2"]


def _bar_chart_svg(stats_list: list[ActionStats], title: str, width=700, height=220) -> str:
    """Per-joint mean ± std bar chart across all chunks."""
    n_j = 9
    # Aggregate across chunks
    all_means = [[s.joint_means[j] for s in stats_list] for j in range(n_j)]
    all_stds  = [[s.joint_stds[j]  for s in stats_list] for j in range(n_j)]

    agg_means = [_mean(all_means[j]) for j in range(n_j)]
    agg_stds  = [_mean(all_stds[j])  for j in range(n_j)]

    pad_l, pad_r, pad_t, pad_b = 50, 20, 40, 40
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    all_vals = [abs(agg_means[j]) + agg_stds[j] for j in range(n_j)]
    y_max = max(all_vals) * 1.2 or 1.0

    bar_w = chart_w / n_j * 0.6
    bar_gap = chart_w / n_j

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" font-size="13" font-weight="bold" fill="#333">{title}</text>')

    # Axes
    x0, y0 = pad_l, pad_t + chart_h
    lines.append(f'<line x1="{x0}" y1="{pad_t}" x2="{x0}" y2="{y0}" stroke="#999" stroke-width="1"/>')
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0+chart_w}" y2="{y0}" stroke="#999" stroke-width="1"/>')

    for j in range(n_j):
        cx = pad_l + bar_gap * j + bar_gap * 0.5
        mean_v = agg_means[j]
        std_v  = agg_stds[j]
        bar_h  = max(2, chart_h * abs(mean_v) / y_max)
        bar_y  = y0 - bar_h
        color  = "#4A90D9" if j < 7 else "#E8704A"

        lines.append(f'<rect x="{cx - bar_w/2:.1f}" y="{bar_y:.1f}" '
                     f'width="{bar_w:.1f}" height="{bar_h:.1f}" '
                     f'fill="{color}" opacity="0.8" rx="2"/>')

        # Error bar
        err_h = chart_h * std_v / y_max
        lines.append(f'<line x1="{cx:.1f}" y1="{bar_y - err_h:.1f}" '
                     f'x2="{cx:.1f}" y2="{bar_y + err_h:.1f}" '
                     f'stroke="#333" stroke-width="1.5"/>')
        lines.append(f'<line x1="{cx-4:.1f}" y1="{bar_y - err_h:.1f}" '
                     f'x2="{cx+4:.1f}" y2="{bar_y - err_h:.1f}" '
                     f'stroke="#333" stroke-width="1.5"/>')

        # Label
        lines.append(f'<text x="{cx:.1f}" y="{y0+14}" text-anchor="middle" '
                     f'font-size="11" fill="#555">{JOINT_LABELS[j]}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _gripper_heatmap_svg(chunks: list[ActionChunk], title: str,
                          max_chunks=40, width=700, height=None) -> str:
    """Heatmap: rows = chunks, cols = 16 steps, color = gripper width."""
    display = chunks[:max_chunks]
    n_rows = len(display)
    cell_h = 14
    pad_l, pad_r, pad_t, pad_b = 60, 20, 35, 25
    cell_w = max(12, (width - pad_l - pad_r) // 16)
    total_h = pad_t + n_rows * cell_h + pad_b if height is None else height

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}">']
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" '
                 f'font-size="13" font-weight="bold" fill="#333">{title}</text>')

    def gripper_color(val: float) -> str:
        # 0=open(blue) → 1=closed(red)
        v = max(0.0, min(1.0, val))
        r = int(60  + 195 * v)
        g = int(120 - 80  * v)
        b = int(220 - 180 * v)
        return f"rgb({r},{g},{b})"

    for row, chunk in enumerate(display):
        y = pad_t + row * cell_h
        label = chunk.chunk_id[-6:]
        lines.append(f'<text x="{pad_l-4}" y="{y + cell_h - 3}" '
                     f'text-anchor="end" font-size="8" fill="#777">{label}</text>')
        for col in range(16):
            gval = chunk.actions[col][7]
            cx = pad_l + col * cell_w
            color = gripper_color(gval)
            lines.append(f'<rect x="{cx}" y="{y}" width="{cell_w-1}" '
                         f'height="{cell_h-1}" fill="{color}" rx="1"/>')

    # Step labels
    for col in range(0, 16, 4):
        cx = pad_l + col * cell_w + cell_w // 2
        lines.append(f'<text x="{cx}" y="{total_h - 8}" '
                     f'text-anchor="middle" font-size="9" fill="#999">t{col}</text>')

    # Legend
    lx = width - pad_r - 80
    ly = 4
    lines.append(f'<text x="{lx}" y="{ly+10}" font-size="9" fill="#777">open</text>')
    for i in range(20):
        lines.append(f'<rect x="{lx+28+i*3}" y="{ly+2}" width="3" height="9" '
                     f'fill="{gripper_color(i/19)}" />')
    lines.append(f'<text x="{lx+93}" y="{ly+10}" font-size="9" fill="#777">closed</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def _comparison_table_html(cmp: dict, bc_stats: list[ActionStats],
                             dag_stats: list[ActionStats]) -> str:
    bc_smooth  = round(_mean([s.smoothness_score for s in bc_stats]), 5)
    dag_smooth = round(_mean([s.smoothness_score for s in dag_stats]), 5)

    rows = []
    for item in cmp["per_joint"]:
        j = item["joint"]
        label = JOINT_LABELS[j]
        better_var = "dagger" if item["dagger_variance"] < item["bc_variance"] else "bc"
        better_cls = 'class="better"' if better_var == "dagger" else ""
        rows.append(
            f"<tr>"
            f"<td>{label}</td>"
            f"<td>{item['bc_variance']:.5f}</td>"
            f"<td>{item['dagger_variance']:.5f}</td>"
            f"<td {better_cls}>{item['kl_divergence']:.5f}</td>"
            f"<td>{item['mean_shift']:.5f}</td>"
            f"</tr>"
        )

    smooth_cls  = 'class="better"' if dag_smooth < bc_smooth else ""
    smooth_text = "DAgger smoother" if dag_smooth < bc_smooth else "BC smoother"
    smooth_row = (
        f"<tr style='background:#f8f8f8'>"
        f"<td><b>Smoothness</b></td>"
        f"<td>{bc_smooth}</td><td>{dag_smooth}</td>"
        f"<td {smooth_cls}>{smooth_text}</td>"
        f"<td>—</td></tr>"
    )

    return f"""
<table>
  <thead>
    <tr>
      <th>Joint</th>
      <th>BC Variance</th>
      <th>DAgger Variance</th>
      <th>KL Divergence</th>
      <th>Mean Shift</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
    {smooth_row}
  </tbody>
</table>
<p><b>Overall distribution shift score:</b> {cmp['overall_shift_score']:.5f}</p>
"""


def _insights_html(all_stats: list[ActionStats],
                   chunks: list[ActionChunk],
                   cmp: dict | None = None) -> str:
    # Most variable joints
    agg_ranges = [_mean([s.joint_ranges[j] for s in all_stats]) for j in range(9)]
    top3 = sorted(range(9), key=lambda j: agg_ranges[j], reverse=True)[:3]

    # Gripper-success correlation
    success_data = [(c.success_flag, c.actions) for c in chunks if c.success_flag is not None]
    if len(success_data) >= 4:
        succ_grip  = [_mean([a[8][7] for a in [c.actions]]) for flag, c in zip(
            [x[0] for x in success_data], chunks) if flag]
        fail_grip  = [_mean([a[8][7] for a in [c.actions]]) for flag, c in zip(
            [x[0] for x in success_data], chunks) if not flag]
        grip_corr  = (
            f"Successful episodes show mean gripper val "
            f"{_mean([c.actions[8][7] for c, (flag, _) in zip(chunks, success_data) if flag]):.3f} "
            f"vs {_mean([c.actions[8][7] for c, (flag, _) in zip(chunks, success_data) if not flag]):.3f} "
            f"for failures — {'gripper timing correlates with success' if succ_grip else 'insufficient data'}."
        )
    else:
        grip_corr = "Insufficient labeled data to compute gripper-success correlation."

    kl_note = ""
    if cmp:
        max_kl = max(cmp["per_joint"], key=lambda x: x["kl_divergence"])
        kl_note = (f"<li>Largest distribution shift between BC and DAgger is at "
                   f"<b>{JOINT_LABELS[max_kl['joint']]}</b> "
                   f"(KL={max_kl['kl_divergence']:.4f}).</li>")

    return f"""
<ul>
  <li>Most variable joints: <b>{', '.join(JOINT_LABELS[j] for j in top3)}</b>
      (ranges: {', '.join(f'{agg_ranges[j]:.3f}' for j in top3)}).</li>
  <li>{grip_corr}</li>
  {kl_note}
  <li>Smoothness score (lower = smoother): mean={_mean([s.smoothness_score for s in all_stats]):.5f}.
      High jerk often indicates BC policy uncertainty at transition points.</li>
</ul>
"""


CSS = """
body { font-family: 'Segoe UI', sans-serif; margin: 32px; background: #fafafa; color: #333; }
h1   { color: #1a1a2e; font-size: 1.6em; margin-bottom: 4px; }
h2   { color: #16213e; font-size: 1.2em; border-bottom: 2px solid #4A90D9; padding-bottom: 4px; }
h3   { color: #444; font-size: 1em; }
.meta  { color: #888; font-size: 0.85em; margin-bottom: 24px; }
.card  { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
         padding: 20px; margin-bottom: 24px; }
table  { border-collapse: collapse; width: 100%; font-size: 0.9em; }
th,td  { padding: 7px 12px; text-align: right; border-bottom: 1px solid #eee; }
th     { background: #f0f4fa; text-align: center; font-weight: 600; }
td:first-child, th:first-child { text-align: left; }
.better { color: #2e7d32; font-weight: 600; }
ul     { line-height: 1.8; }
"""


def build_report(chunks: list[ActionChunk], title: str,
                  bc_chunks: list[ActionChunk] | None = None,
                  dagger_chunks: list[ActionChunk] | None = None) -> str:
    all_stats = [compute_stats(c) for c in chunks]
    n_success = sum(1 for c in chunks if c.success_flag is True)
    n_labeled = sum(1 for c in chunks if c.success_flag is not None)
    success_str = f"{n_success}/{n_labeled}" if n_labeled else "N/A"

    bar_svg      = _bar_chart_svg(all_stats, "Per-Joint Action Range (mean ± std)")
    heatmap_svg  = _gripper_heatmap_svg(chunks, "Gripper Timeline (blue=open, red=closed)")

    cmp_html = ""
    cmp_dict = None
    if bc_chunks and dagger_chunks:
        cmp_dict = compare_distributions(bc_chunks, dagger_chunks)
        bc_stats  = [compute_stats(c) for c in bc_chunks]
        dag_stats = [compute_stats(c) for c in dagger_chunks]
        cmp_html  = f"""
<div class="card">
  <h2>BC vs DAgger Comparison</h2>
  {_comparison_table_html(cmp_dict, bc_stats, dag_stats)}
</div>"""

    insight_html = _insights_html(all_stats, chunks, cmp_dict)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>{title}</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>GR00T Action Chunk Visualizer</h1>
  <p class="meta">
    Report: <b>{title}</b> &nbsp;|&nbsp;
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
    Chunks: {len(chunks)} &nbsp;|&nbsp; Success rate: {success_str}
  </p>

  <div class="card">
    <h2>Per-Joint Action Range</h2>
    <p style="color:#666;font-size:0.85em">
      Blue bars = arm joints J1-J7; orange = gripper joints G1/G2.
      Error bars show mean std across all chunks.
    </p>
    {bar_svg}
  </div>

  <div class="card">
    <h2>Gripper Timeline Heatmap</h2>
    <p style="color:#666;font-size:0.85em">
      Each row = one chunk (up to 40 shown). Columns = 16 action steps.
      Blue = open, red = closed.
    </p>
    {heatmap_svg}
  </div>

  {cmp_html}

  <div class="card">
    <h2>Insights</h2>
    {insight_html}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="GR00T Action Chunk Visualizer — analyze 16-step action chunks from inference."
    )
    parser.add_argument("--mock", action="store_true",
                        help="Generate mock data instead of loading real chunks.")
    parser.add_argument("--n-chunks", type=int, default=50,
                        help="Number of mock chunks to generate (default: 50).")
    parser.add_argument("--compare-bc-dagger", action="store_true",
                        help="Generate BC vs DAgger comparison report.")
    parser.add_argument("--success-rate", type=float, default=0.6,
                        help="Mock success rate (default: 0.6).")
    parser.add_argument("--output", type=str, default="/tmp/action_viz.html",
                        help="Output HTML file path.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for mock data (default: 42).")
    args = parser.parse_args()

    if not args.mock:
        parser.error("Only --mock mode is supported in this standalone script.")

    if args.compare_bc_dagger:
        print(f"Generating BC vs DAgger comparison ({args.n_chunks} chunks each)...")
        bc_chunks     = generate_mock_chunks(args.n_chunks, args.success_rate, "BC",     args.seed)
        dagger_chunks = generate_mock_chunks(args.n_chunks, args.success_rate, "DAgger", args.seed + 1)
        all_chunks    = bc_chunks + dagger_chunks
        html = build_report(
            all_chunks,
            title="BC vs DAgger Comparison",
            bc_chunks=bc_chunks,
            dagger_chunks=dagger_chunks,
        )
        print(f"  BC chunks:     {len(bc_chunks)}")
        print(f"  DAgger chunks: {len(dagger_chunks)}")
    else:
        print(f"Generating {args.n_chunks} mock BC chunks...")
        chunks = generate_mock_chunks(args.n_chunks, args.success_rate, "BC", args.seed)
        html   = build_report(chunks, title=f"BC Policy — {args.n_chunks} Chunks")
        print(f"  Chunks: {len(chunks)}")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written to: {args.output}")
    size_kb = len(html.encode()) / 1024
    print(f"File size: {size_kb:.1f} KB")

    # Quick stats summary
    cmp = compare_distributions(bc_chunks, dagger_chunks) if args.compare_bc_dagger else None
    if cmp:
        print("\nBC vs DAgger — per-joint KL divergence:")
        for item in cmp["per_joint"]:
            print(f"  {JOINT_LABELS[item['joint']]}: KL={item['kl_divergence']:.4f}  "
                  f"BC_var={item['bc_variance']:.5f}  DAgger_var={item['dagger_variance']:.5f}")
        print(f"  Overall shift score: {cmp['overall_shift_score']:.5f}")


if __name__ == "__main__":
    main()
