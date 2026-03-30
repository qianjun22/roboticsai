"""
GR00T Attention Visualizer
Visualizes what GR00T's transformer attends to in its input observations —
which joints and image patch regions most influence each action DOF prediction.

Architecture modeled:
  - 12 transformer layers
  - 9 joint tokens  (7 arm + 2 gripper)
  - 196 image patch tokens (14×14 ViT patches from a 224×224 frame)
  - 9 action output DOFs

Usage:
    # Single phase report
    python src/eval/attention_visualizer.py --mock --phase lift \
        --output /tmp/attention_viz.html

    # All phases + JSON export
    python src/eval/attention_visualizer.py --mock --all-phases \
        --output /tmp/attention_all.html \
        --json /tmp/attention_analysis.json

    # BC vs DAgger comparison
    python src/eval/attention_visualizer.py --mock --compare \
        --output /tmp/attention_compare.html

Output:
    Dark-theme HTML with inline SVG heatmaps (no matplotlib / no external deps).
    Optional JSON with all numerical scores for paper supplementary material.
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

N_LAYERS = 12
N_JOINTS = 9
JOINT_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
    "ee_x", "ee_y", "gripper"
]
ACTION_DOF_NAMES = [
    "Δshoulder_pan", "Δshoulder_lift", "Δelbow",
    "Δwrist_1", "Δwrist_2", "Δwrist_3",
    "Δee_x", "Δee_y", "Δgripper"
]
N_PATCHES = 196  # 14×14
PATCH_GRID = 14

PHASES = ["approach", "grasp", "lift"]
POLICIES = ["bc", "dagger"]

# Phase color accents (for HTML)
PHASE_COLORS = {
    "approach": "#60a5fa",   # blue-400
    "grasp":    "#f59e0b",   # amber-400
    "lift":     "#34d399",   # emerald-400
}
POLICY_COLORS = {
    "bc":     "#a78bfa",  # violet-400
    "dagger": "#fb923c",  # orange-400
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AttentionSnapshot:
    """Full attention data for one (phase, policy) combination."""
    phase: str
    policy: str
    # layer_joint_attn[layer][dof] = attention score over each joint (len 9)
    layer_joint_attn: list[list[list[float]]]     # [12][9][9]
    # layer_patch_attn[layer][dof] = attention score over each patch (len 196)
    layer_patch_attn: list[list[list[float]]]     # [12][9][196]

    # Aggregated (last-layer, averaged over DOFs)
    joint_attn_agg: list[float] = field(default_factory=list)    # [9]
    patch_attn_agg: list[float] = field(default_factory=list)    # [196]

    # Per-DOF joint attention (last layer)
    per_dof_joint: list[list[float]] = field(default_factory=list)  # [9][9]


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _softmax(vals: list[float]) -> list[float]:
    mx = max(vals)
    exps = [math.exp(v - mx) for v in vals]
    s = sum(exps)
    return [e / s for e in exps]


def _make_patch_weights(phase: str, policy: str, seed_offset: int = 0) -> list[float]:
    """
    Generate a 14×14 patch attention distribution shaped by phase semantics.

    Approach  → attention near upper-center (cube far, in upper FOV)
    Grasp     → attention near center (cube close, mid-frame)
    Lift      → attention at center + slight upward shift
    DAgger    → same pattern but sharper (higher peak / lower entropy)
    """
    rng = random.Random(42 + seed_offset)
    weights = []

    if phase == "approach":
        cx, cy = 6.5, 4.5   # upper-center
    elif phase == "grasp":
        cx, cy = 7.0, 7.0   # center
    else:  # lift
        cx, cy = 7.0, 5.5   # center-upper

    sharpness = 4.0 if policy == "dagger" else 2.5

    for row in range(PATCH_GRID):
        for col in range(PATCH_GRID):
            dist2 = (col - cx) ** 2 + (row - cy) ** 2
            base = math.exp(-dist2 / sharpness)
            noise = rng.gauss(0, 0.05)
            weights.append(max(0.0, base + noise))

    return _softmax(weights)


def _make_joint_weights(phase: str, policy: str, dof_idx: int, seed_offset: int = 0) -> list[float]:
    """
    Generate joint attention weights for a given phase/policy/output-DOF.

    Lift phase:
      - Gripper DOF (8) → strong attention on gripper joint (8) and wrist (5)
      - Other DOFs       → moderate spread across arm joints
    Approach phase:
      - Shoulder DOFs (0,1) get higher attention
    Grasp:
      - Wrist + gripper joints highlighted
    DAgger sharpens the dominant joint.
    """
    rng = random.Random(100 + dof_idx * 13 + seed_offset)

    base = [rng.uniform(0.3, 0.7) for _ in range(N_JOINTS)]

    if phase == "approach":
        base[0] += 1.2  # shoulder_pan
        base[1] += 1.0  # shoulder_lift
    elif phase == "grasp":
        base[5] += 1.0  # wrist_3
        base[8] += 1.5  # gripper
    else:  # lift
        base[8] += 2.0  # gripper
        base[5] += 1.0  # wrist_3
        if dof_idx == 8:  # gripper action → very focused
            base[8] += 2.0

    if policy == "dagger":
        # Sharpen: amplify the dominant joint
        mx_idx = base.index(max(base))
        base[mx_idx] += 1.5

    return _softmax(base)


def generate_attention_snapshot(phase: str, policy: str) -> AttentionSnapshot:
    """Build a full 12-layer attention snapshot with mock but plausible data."""
    rng = random.Random(hash(phase + policy) & 0xFFFF)

    layer_joint_attn: list[list[list[float]]] = []
    layer_patch_attn: list[list[list[float]]] = []

    for layer in range(N_LAYERS):
        # Early layers: diffuse; late layers: task-specific
        layer_weight = layer / (N_LAYERS - 1)   # 0.0 → 1.0
        seed_off = layer * 7 + rng.randint(0, 50)

        dof_joints = []
        dof_patches = []
        for dof in range(N_JOINTS):
            # Mix between uniform (early) and focused (late)
            focused_j = _make_joint_weights(phase, policy, dof, seed_off + dof)
            uniform_j = [1.0 / N_JOINTS] * N_JOINTS
            blended_j = [
                layer_weight * fj + (1 - layer_weight) * uj
                for fj, uj in zip(focused_j, uniform_j)
            ]
            dof_joints.append(_softmax(blended_j))

            focused_p = _make_patch_weights(phase, policy, seed_off + dof)
            uniform_p = [1.0 / N_PATCHES] * N_PATCHES
            blended_p = [
                layer_weight * fp + (1 - layer_weight) * up
                for fp, up in zip(focused_p, uniform_p)
            ]
            dof_patches.append(_softmax(blended_p))

        layer_joint_attn.append(dof_joints)
        layer_patch_attn.append(dof_patches)

    # Aggregate last-layer attention (mean over DOFs)
    last_j = layer_joint_attn[-1]
    joint_agg = [sum(last_j[d][j] for d in range(N_JOINTS)) / N_JOINTS for j in range(N_JOINTS)]
    last_p = layer_patch_attn[-1]
    patch_agg = [sum(last_p[d][p] for d in range(N_JOINTS)) / N_JOINTS for p in range(N_PATCHES)]

    return AttentionSnapshot(
        phase=phase,
        policy=policy,
        layer_joint_attn=layer_joint_attn,
        layer_patch_attn=layer_patch_attn,
        joint_attn_agg=joint_agg,
        patch_attn_agg=patch_agg,
        per_dof_joint=last_j,
    )


# ---------------------------------------------------------------------------
# SVG rendering helpers
# ---------------------------------------------------------------------------

def _lerp_color(t: float, low: tuple, high: tuple) -> str:
    """Interpolate between two RGB tuples and return hex color."""
    r = int(low[0] + t * (high[0] - low[0]))
    g = int(low[1] + t * (high[1] - low[1]))
    b = int(low[2] + t * (high[2] - low[2]))
    return f"#{r:02x}{g:02x}{b:02x}"


# Dark teal-to-yellow heatmap palette
HEAT_LOW  = (15, 23, 42)    # slate-900
HEAT_MID  = (6, 182, 212)   # cyan-500
HEAT_HIGH = (250, 204, 21)  # yellow-400


def _heat_color(val: float) -> str:
    """Map [0,1] to a dark→cyan→yellow heatmap color."""
    if val < 0.5:
        return _lerp_color(val * 2, HEAT_LOW, HEAT_MID)
    return _lerp_color((val - 0.5) * 2, HEAT_MID, HEAT_HIGH)


def svg_patch_heatmap(patch_weights: list[float], title: str,
                       width: int = 280, height: int = 280) -> str:
    """Render a 14×14 patch attention grid as an SVG heatmap."""
    cell_w = width / PATCH_GRID
    cell_h = height / PATCH_GRID
    mx = max(patch_weights) or 1e-9

    rects = []
    for idx, w in enumerate(patch_weights):
        row = idx // PATCH_GRID
        col = idx % PATCH_GRID
        x = col * cell_w
        y = row * cell_h
        norm = w / mx
        color = _heat_color(norm)
        opacity = 0.3 + 0.7 * norm
        rects.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
            f'fill="{color}" opacity="{opacity:.2f}"/>'
        )

    # Grid overlay (subtle)
    lines = []
    for i in range(1, PATCH_GRID):
        xp = i * cell_w
        lines.append(f'<line x1="{xp:.1f}" y1="0" x2="{xp:.1f}" y2="{height}" '
                     f'stroke="#1e293b" stroke-width="0.5"/>')
        yp = i * cell_h
        lines.append(f'<line x1="0" y1="{yp:.1f}" x2="{width}" y2="{yp:.1f}" '
                     f'stroke="#1e293b" stroke-width="0.5"/>')

    svg = (
        f'<figure style="margin:0;text-align:center">'
        f'<svg width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px;display:block;margin:0 auto">'
        + "".join(rects)
        + "".join(lines)
        + f'</svg>'
        f'<figcaption style="color:#94a3b8;font-size:12px;margin-top:6px">{title}</figcaption>'
        f'</figure>'
    )
    return svg


def svg_joint_bars(joint_weights: list[float], title: str,
                   bar_color: str = "#60a5fa",
                   width: int = 320, bar_height: int = 22,
                   gap: int = 4) -> str:
    """Render horizontal bar chart of joint attention weights."""
    mx = max(joint_weights) or 1e-9
    bar_area_w = width - 110   # label width = 110

    bars = []
    total_h = N_JOINTS * (bar_height + gap) + 8
    bars.append(
        f'<svg width="{width}" height="{total_h}" '
        f'style="background:#0f172a;border-radius:8px;overflow:visible">'
    )

    for i, (name, w) in enumerate(zip(JOINT_NAMES, joint_weights)):
        norm = w / mx
        bw = norm * bar_area_w
        y = i * (bar_height + gap)

        # Label
        bars.append(
            f'<text x="105" y="{y + bar_height - 6}" '
            f'text-anchor="end" font-size="11" fill="#94a3b8" font-family="monospace">'
            f'{name}</text>'
        )
        # Background track
        bars.append(
            f'<rect x="110" y="{y + 2}" width="{bar_area_w}" height="{bar_height - 4}" '
            f'rx="3" fill="#1e293b"/>'
        )
        # Filled bar
        if bw > 2:
            bars.append(
                f'<rect x="110" y="{y + 2}" width="{bw:.1f}" height="{bar_height - 4}" '
                f'rx="3" fill="{bar_color}" opacity="0.85"/>'
            )
        # Value label
        bars.append(
            f'<text x="{110 + bw + 4:.1f}" y="{y + bar_height - 6}" '
            f'font-size="10" fill="#64748b" font-family="monospace">'
            f'{w:.3f}</text>'
        )

    bars.append("</svg>")

    return (
        f'<figure style="margin:0">'
        + "".join(bars)
        + f'<figcaption style="color:#94a3b8;font-size:12px;margin-top:6px;text-align:center">'
        + title
        + "</figcaption></figure>"
    )


def svg_layer_evolution(layer_joint_attn: list[list[list[float]]],
                         joint_idx: int, title: str,
                         width: int = 440, height: int = 120) -> str:
    """
    Line chart of how a single joint's mean attention (across DOFs) evolves
    from layer 1 to layer 12.
    """
    # Mean attention on joint_idx across all output DOFs, per layer
    vals = []
    for layer in range(N_LAYERS):
        mean_attn = sum(layer_joint_attn[layer][d][joint_idx]
                        for d in range(N_JOINTS)) / N_JOINTS
        vals.append(mean_attn)

    mx = max(vals) or 1e-9
    mn = min(vals)
    rng_v = mx - mn or 1e-9

    pad_l, pad_r, pad_t, pad_b = 40, 16, 16, 28
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    def px(layer_i: int) -> float:
        return pad_l + layer_i / (N_LAYERS - 1) * inner_w

    def py(val: float) -> float:
        return pad_t + (1 - (val - mn) / rng_v) * inner_h

    points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))

    # Y-axis ticks
    y_ticks = ""
    for tick in [mn, (mn + mx) / 2, mx]:
        yp = py(tick)
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="#475569" stroke-width="1"/>'
            f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#64748b">{tick:.3f}</text>'
        )

    # X-axis labels
    x_labels = ""
    for i in range(N_LAYERS):
        if i % 3 == 0 or i == N_LAYERS - 1:
            x_labels += (
                f'<text x="{px(i):.1f}" y="{height - 4}" text-anchor="middle" '
                f'font-size="9" fill="#64748b">L{i+1}</text>'
            )

    svg = (
        f'<figure style="margin:0">'
        f'<svg width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        # Grid
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + inner_h}" '
        f'stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{pad_l + inner_w}" '
        f'y2="{pad_t + inner_h}" stroke="#334155" stroke-width="1"/>'
        + y_ticks + x_labels
        + f'<polyline points="{points}" fill="none" stroke="#60a5fa" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        # Dots
        + "".join(
            f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" fill="#60a5fa"/>'
            for i, v in enumerate(vals)
        )
        + "</svg>"
        f'<figcaption style="color:#94a3b8;font-size:12px;margin-top:6px;text-align:center">'
        + title
        + "</figcaption></figure>"
    )
    return svg


def svg_dof_joint_matrix(per_dof_joint: list[list[float]], title: str,
                          width: int = 340, height: int = 340) -> str:
    """
    9×9 heatmap matrix: rows = output action DOFs, cols = input joints.
    """
    cell_w = (width - 110) / N_JOINTS
    cell_h = (height - 60) / N_JOINTS
    all_vals = [v for row in per_dof_joint for v in row]
    mx = max(all_vals) or 1e-9

    cells = []
    for dof, row_weights in enumerate(per_dof_joint):
        for j, w in enumerate(row_weights):
            cx = 110 + j * cell_w
            cy = 30 + dof * cell_h
            norm = w / mx
            color = _heat_color(norm)
            cells.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="{color}" opacity="0.9"/>'
            )
            if cell_w > 20:
                cells.append(
                    f'<text x="{cx + cell_w/2:.1f}" y="{cy + cell_h/2 + 4:.1f}" '
                    f'text-anchor="middle" font-size="8" fill="#0f172a">'
                    f'{w:.2f}</text>'
                )

    # Col headers (joint names, rotated)
    col_headers = []
    for j, name in enumerate(JOINT_NAMES):
        cx = 110 + j * cell_w + cell_w / 2
        short = name.split("_")[0][:4]
        col_headers.append(
            f'<text x="{cx:.1f}" y="20" text-anchor="middle" '
            f'font-size="9" fill="#94a3b8" font-family="monospace">{short}</text>'
        )

    # Row headers (DOF names)
    row_headers = []
    for d, name in enumerate(ACTION_DOF_NAMES):
        cy = 30 + d * cell_h + cell_h / 2 + 4
        row_headers.append(
            f'<text x="105" y="{cy:.1f}" text-anchor="end" '
            f'font-size="9" fill="#94a3b8" font-family="monospace">'
            + name[1:6] + "</text>"
        )

    svg = (
        f'<figure style="margin:0">'
        f'<svg width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        + "".join(col_headers)
        + "".join(row_headers)
        + "".join(cells)
        + "</svg>"
        f'<figcaption style="color:#94a3b8;font-size:12px;margin-top:6px;text-align:center">'
        + title
        + "</figcaption></figure>"
    )
    return svg


# ---------------------------------------------------------------------------
# HTML report builders
# ---------------------------------------------------------------------------

_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GR00T Attention Visualizer</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#020617;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;
       padding:32px 24px;line-height:1.6}
  h1{font-size:1.7rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}
  h2{font-size:1.2rem;font-weight:600;color:#cbd5e1;margin:28px 0 12px}
  h3{font-size:1rem;font-weight:600;color:#94a3b8;margin:18px 0 8px}
  .subtitle{color:#64748b;font-size:.9rem;margin-bottom:32px}
  .tag{display:inline-block;padding:2px 10px;border-radius:999px;
       font-size:.75rem;font-weight:600;letter-spacing:.04em;margin-right:6px}
  .section{background:#0f172a;border:1px solid #1e293b;border-radius:12px;
            padding:24px;margin-bottom:24px}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
  .grid-4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:20px}
  .card{background:#1e293b;border-radius:8px;padding:16px}
  .stat{font-size:1.4rem;font-weight:700;color:#f1f5f9}
  .stat-label{font-size:.78rem;color:#64748b;margin-top:2px}
  .divider{border:none;border-top:1px solid #1e293b;margin:20px 0}
  .insight{background:#1e293b;border-left:3px solid #60a5fa;
            padding:10px 14px;border-radius:0 6px 6px 0;
            font-size:.85rem;color:#94a3b8;margin:8px 0}
  .phase-approach{border-left-color:#60a5fa}
  .phase-grasp{border-left-color:#f59e0b}
  .phase-lift{border-left-color:#34d399}
  footer{color:#334155;font-size:.78rem;text-align:center;margin-top:40px}
  @media(max-width:900px){.grid-3,.grid-4{grid-template-columns:1fr 1fr}
  .grid-2{grid-template-columns:1fr}}
</style>
</head>
<body>
"""

_HTML_FOOT = """
<footer>
  GR00T Attention Visualizer &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp;
  Generated {ts} &nbsp;|&nbsp; Mock data (12 layers × 9 DOF × 205 tokens)
</footer>
</body></html>
"""


def _phase_tag(phase: str) -> str:
    color = PHASE_COLORS.get(phase, "#94a3b8")
    return (f'<span class="tag" style="background:{color}22;color:{color};'
            f'border:1px solid {color}44">{phase.upper()}</span>')


def _policy_tag(policy: str) -> str:
    color = POLICY_COLORS.get(policy, "#94a3b8")
    label = "BC (Baseline)" if policy == "bc" else "DAgger (Fine-tuned)"
    return (f'<span class="tag" style="background:{color}22;color:{color};'
            f'border:1px solid {color}44">{label}</span>')


def _top_joints(weights: list[float], n: int = 3) -> str:
    ranked = sorted(enumerate(weights), key=lambda x: -x[1])[:n]
    parts = [f"<strong style='color:#f1f5f9'>{JOINT_NAMES[i]}</strong> ({w:.3f})"
             for i, w in ranked]
    return ", ".join(parts)


def _top_patch_region(weights: list[float]) -> str:
    """Describe the dominant image region in human-readable terms."""
    # Find centroid of top-5% patches
    thresh = sorted(weights, reverse=True)[int(len(weights) * 0.05)]
    cx_sum = cy_sum = count = 0
    for idx, w in enumerate(weights):
        if w >= thresh:
            cy_sum += idx // PATCH_GRID
            cx_sum += idx % PATCH_GRID
            count += 1
    if count == 0:
        return "unknown"
    cx = cx_sum / count / PATCH_GRID   # 0–1
    cy = cy_sum / count / PATCH_GRID   # 0–1
    hpos = "left" if cx < 0.4 else ("right" if cx > 0.6 else "center")
    vpos = "upper" if cy < 0.4 else ("lower" if cy > 0.6 else "middle")
    return f"{vpos}-{hpos} of frame"


def render_phase_section(snap: AttentionSnapshot) -> str:
    """Build HTML section for a single phase."""
    phase = snap.phase
    policy = snap.policy
    accent = PHASE_COLORS.get(phase, "#60a5fa")
    pol_accent = POLICY_COLORS.get(policy, "#a78bfa")

    patch_svg = svg_patch_heatmap(
        snap.patch_attn_agg,
        f"Image Patch Attention — last layer, DOF-mean",
        width=280, height=280,
    )
    joint_svg = svg_joint_bars(
        snap.joint_attn_agg,
        f"Joint Attention — last layer, DOF-mean",
        bar_color=accent,
        width=340,
    )
    dof_matrix_svg = svg_dof_joint_matrix(
        snap.per_dof_joint,
        f"Per-DOF × Joint Matrix (last layer)",
        width=340, height=300,
    )
    # Layer evolution for top 2 joints
    top2 = sorted(range(N_JOINTS), key=lambda j: -snap.joint_attn_agg[j])[:2]
    layer_svgs = []
    for j in top2:
        layer_svgs.append(svg_layer_evolution(
            snap.layer_joint_attn, j,
            f"Layer evolution — {JOINT_NAMES[j]}",
            width=400, height=110,
        ))

    top_joint_str = _top_joints(snap.joint_attn_agg)
    region_str = _top_patch_region(snap.patch_attn_agg)

    entropy = -sum(w * math.log(w + 1e-12) for w in snap.joint_attn_agg)
    max_entropy = math.log(N_JOINTS)
    focus_pct = (1 - entropy / max_entropy) * 100

    html = f"""
<div class="section">
  <h2>{_phase_tag(phase)} {_policy_tag(policy)} &nbsp; Phase Analysis</h2>
  <div class="grid-4" style="margin-bottom:18px">
    <div class="card">
      <div class="stat">{focus_pct:.0f}%</div>
      <div class="stat-label">Joint Focus Score</div>
    </div>
    <div class="card">
      <div class="stat">{JOINT_NAMES[snap.joint_attn_agg.index(max(snap.joint_attn_agg))]}</div>
      <div class="stat-label">Top Attended Joint</div>
    </div>
    <div class="card">
      <div class="stat" style="font-size:1rem">{region_str}</div>
      <div class="stat-label">Dominant Image Region</div>
    </div>
    <div class="card">
      <div class="stat">{entropy:.3f}</div>
      <div class="stat-label">Attention Entropy (nats)</div>
    </div>
  </div>
  <div class="insight phase-{phase}">
    Top attended joints: {top_joint_str} &nbsp;|&nbsp; Image focus: <strong style="color:#f1f5f9">{region_str}</strong>
  </div>
  <hr class="divider">
  <div class="grid-2">
    <div>{patch_svg}</div>
    <div>{joint_svg}</div>
  </div>
  <hr class="divider">
  <h3>DOF × Joint Attention Matrix &amp; Layer Evolution</h3>
  <div class="grid-2">
    <div>{dof_matrix_svg}</div>
    <div style="display:flex;flex-direction:column;gap:16px">
      {"".join(layer_svgs)}
    </div>
  </div>
</div>
"""
    return html


def render_comparison_section(bc_snap: AttentionSnapshot, dagger_snap: AttentionSnapshot) -> str:
    """Side-by-side BC vs DAgger attention for a given phase."""
    phase = bc_snap.phase
    accent = PHASE_COLORS.get(phase, "#60a5fa")

    bc_patch  = svg_patch_heatmap(bc_snap.patch_attn_agg, "BC — image attention", 260, 260)
    dag_patch = svg_patch_heatmap(dagger_snap.patch_attn_agg, "DAgger — image attention", 260, 260)
    bc_joint  = svg_joint_bars(bc_snap.joint_attn_agg, "BC joint attention",
                                bar_color=POLICY_COLORS["bc"], width=320)
    dag_joint = svg_joint_bars(dagger_snap.joint_attn_agg, "DAgger joint attention",
                                bar_color=POLICY_COLORS["dagger"], width=320)

    # Focus scores
    def focus(snap):
        e = -sum(w * math.log(w + 1e-12) for w in snap.joint_attn_agg)
        return (1 - e / math.log(N_JOINTS)) * 100

    bc_f   = focus(bc_snap)
    dag_f  = focus(dagger_snap)
    delta  = dag_f - bc_f

    html = f"""
<div class="section">
  <h2>{_phase_tag(phase)} BC vs DAgger Attention Comparison</h2>
  <div class="grid-4" style="margin-bottom:18px">
    <div class="card"><div class="stat">{bc_f:.0f}%</div>
      <div class="stat-label">BC Focus Score</div></div>
    <div class="card"><div class="stat">{dag_f:.0f}%</div>
      <div class="stat-label">DAgger Focus Score</div></div>
    <div class="card">
      <div class="stat" style="color:{'#34d399' if delta>0 else '#f87171'}">
        {'+' if delta>=0 else ''}{delta:.1f}%
      </div>
      <div class="stat-label">DAgger Δ Focus</div>
    </div>
    <div class="card">
      <div class="stat">{JOINT_NAMES[dagger_snap.joint_attn_agg.index(max(dagger_snap.joint_attn_agg))]}</div>
      <div class="stat-label">DAgger Top Joint</div>
    </div>
  </div>
  <div class="insight" style="border-left-color:#a78bfa">
    DAgger fine-tuning {"sharpens" if delta > 0 else "diffuses"} attention focus by
    <strong style="color:#f1f5f9">{abs(delta):.1f}%</strong> compared to BC baseline.
    DAgger top joint: <strong style="color:#f1f5f9">
    {JOINT_NAMES[dagger_snap.joint_attn_agg.index(max(dagger_snap.joint_attn_agg))]}</strong>.
  </div>
  <hr class="divider">
  <div class="grid-2">
    <div><h3>Image Patch Attention</h3>
      <div class="grid-2">{bc_patch}{dag_patch}</div></div>
    <div><h3>Joint Attention</h3>{bc_joint}{dag_joint}</div>
  </div>
</div>
"""
    return html


def build_html_report(snapshots: list[AttentionSnapshot],
                       compare: bool = False,
                       run_ts: str = "") -> str:
    ts = run_ts or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = _HTML_HEAD

    # Header
    phases_shown = sorted({s.phase for s in snapshots}, key=PHASES.index)
    policies_shown = sorted({s.policy for s in snapshots})
    phase_tags = "".join(_phase_tag(p) for p in phases_shown)
    policy_tags = "".join(_policy_tag(p) for p in policies_shown)

    body += f"""
<h1>GR00T Attention Visualizer</h1>
<p class="subtitle">
  Transformer layer-by-layer attention analysis &nbsp;·&nbsp;
  {phase_tags}{policy_tags}
  &nbsp;·&nbsp; {ts}
</p>

<div class="section">
  <h2>Architecture Overview</h2>
  <div class="grid-4">
    <div class="card"><div class="stat">{N_LAYERS}</div>
      <div class="stat-label">Transformer Layers</div></div>
    <div class="card"><div class="stat">{N_JOINTS}</div>
      <div class="stat-label">Joint Tokens (9 DOF)</div></div>
    <div class="card"><div class="stat">{N_PATCHES}</div>
      <div class="stat-label">Image Patch Tokens (14×14)</div></div>
    <div class="card"><div class="stat">{N_JOINTS}</div>
      <div class="stat-label">Output Action DOFs</div></div>
  </div>
  <div class="insight" style="margin-top:14px">
    GR00T processes joint-state tokens and ViT image patch tokens jointly through
    {N_LAYERS} transformer layers. This tool shows how attention weights shift from
    diffuse (early layers) to task-specific (late layers), and which joints / image
    regions dominate for each manipulation phase.
  </div>
</div>
"""

    if compare:
        # Group by phase
        snap_map: dict[tuple[str,str], AttentionSnapshot] = {
            (s.phase, s.policy): s for s in snapshots
        }
        for phase in phases_shown:
            if ("bc", phase) not in {(s.policy, s.phase) for s in snapshots}:
                continue
            bc_s   = snap_map.get((phase, "bc"))
            dag_s  = snap_map.get((phase, "dagger"))
            if bc_s and dag_s:
                body += render_comparison_section(bc_s, dag_s)
    else:
        for snap in snapshots:
            body += render_phase_section(snap)

    body += _HTML_FOOT.format(ts=ts)
    return body


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def build_json_export(snapshots: list[AttentionSnapshot]) -> dict:
    """Build a JSON-serialisable dict with all numerical attention scores."""
    out = {
        "metadata": {
            "tool": "GR00T Attention Visualizer",
            "n_layers": N_LAYERS,
            "n_joints": N_JOINTS,
            "n_patches": N_PATCHES,
            "joint_names": JOINT_NAMES,
            "action_dof_names": ACTION_DOF_NAMES,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "snapshots": []
    }

    for snap in snapshots:
        # Focus score
        e = -sum(w * math.log(w + 1e-12) for w in snap.joint_attn_agg)
        focus = (1 - e / math.log(N_JOINTS)) * 100

        # Top-3 joints (last layer, aggregated)
        top3 = sorted(range(N_JOINTS), key=lambda j: -snap.joint_attn_agg[j])[:3]

        entry = {
            "phase": snap.phase,
            "policy": snap.policy,
            "joint_focus_score_pct": round(focus, 2),
            "joint_attention_entropy": round(e, 4),
            "top_joints": [
                {"joint": JOINT_NAMES[j], "weight": round(snap.joint_attn_agg[j], 4)}
                for j in top3
            ],
            "dominant_image_region": _top_patch_region(snap.patch_attn_agg),
            "joint_attn_agg": [round(v, 4) for v in snap.joint_attn_agg],
            "patch_attn_agg": [round(v, 6) for v in snap.patch_attn_agg],
            "per_dof_joint_attn_last_layer": [
                [round(v, 4) for v in row] for row in snap.per_dof_joint
            ],
            "layer_mean_joint_attn": [
                [
                    round(
                        sum(snap.layer_joint_attn[layer][d][j]
                            for d in range(N_JOINTS)) / N_JOINTS,
                        4
                    )
                    for j in range(N_JOINTS)
                ]
                for layer in range(N_LAYERS)
            ],
        }
        out["snapshots"].append(entry)

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GR00T Attention Visualizer — analyze transformer attention patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single lift-phase HTML report
  python src/eval/attention_visualizer.py --mock --phase lift \\
      --output /tmp/attention_viz.html

  # All three phases (approach / grasp / lift)
  python src/eval/attention_visualizer.py --mock --all-phases \\
      --output /tmp/attention_all.html \\
      --json /tmp/attention_analysis.json

  # BC vs DAgger comparison (all phases)
  python src/eval/attention_visualizer.py --mock --compare \\
      --output /tmp/attention_compare.html
""",
    )
    p.add_argument("--mock", action="store_true",
                   help="Use mock/simulated attention data (required until live model is wired)")
    p.add_argument("--phase", choices=PHASES, default=None,
                   help="Single phase to visualise (approach | grasp | lift)")
    p.add_argument("--all-phases", action="store_true",
                   help="Render all three phases in one report")
    p.add_argument("--compare", action="store_true",
                   help="BC vs DAgger comparison view (renders all phases × both policies)")
    p.add_argument("--policy", choices=POLICIES, default="bc",
                   help="Policy to analyse for single-phase view (default: bc)")
    p.add_argument("--output", default="/tmp/attention_viz.html",
                   help="Output HTML path (default: /tmp/attention_viz.html)")
    p.add_argument("--json", default=None,
                   help="Optional JSON output path for paper supplementary data")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for mock data (default: 42)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    if not args.mock:
        print("[attention_visualizer] Only --mock mode is supported in this release.")
        print("  Live GR00T model hook is a TODO — patch src/eval/attention_visualizer.py")
        print("  function generate_attention_snapshot() with real forward-pass hook data.")
        return

    # Collect which (phase, policy) pairs to render
    pairs: list[tuple[str, str]] = []
    if args.compare:
        for ph in PHASES:
            for pol in POLICIES:
                pairs.append((ph, pol))
    elif args.all_phases:
        for ph in PHASES:
            pairs.append((ph, args.policy))
    else:
        phase = args.phase or "lift"
        pairs.append((phase, args.policy))

    print(f"[attention_visualizer] Generating {len(pairs)} snapshot(s)...")
    snapshots: list[AttentionSnapshot] = []
    for phase, policy in pairs:
        print(f"  • phase={phase:<8}  policy={policy}")
        snap = generate_attention_snapshot(phase, policy)
        snapshots.append(snap)

    # HTML
    compare_mode = args.compare
    html = build_html_report(snapshots, compare=compare_mode)
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[attention_visualizer] HTML report saved → {output_path}")

    # JSON
    if args.json:
        data = build_json_export(snapshots)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[attention_visualizer] JSON data saved  → {args.json}")

    # Print quick summary table
    print()
    print("─" * 60)
    print(f"{'Phase':<10} {'Policy':<8} {'Top Joint':<16} {'Focus%':<8} {'Region'}")
    print("─" * 60)
    for snap in snapshots:
        top_j = JOINT_NAMES[snap.joint_attn_agg.index(max(snap.joint_attn_agg))]
        e = -sum(w * math.log(w + 1e-12) for w in snap.joint_attn_agg)
        focus = (1 - e / math.log(N_JOINTS)) * 100
        region = _top_patch_region(snap.patch_attn_agg)
        print(f"{snap.phase:<10} {snap.policy:<8} {top_j:<16} {focus:>6.1f}%  {region}")
    print("─" * 60)


if __name__ == "__main__":
    main()
