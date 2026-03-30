"""GR00T visual attention and feature importance analysis. Identifies what the policy attends to during manipulation tasks."""

import argparse
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AttentionRegion:
    region_name: str
    attention_weight: float
    spatial_x: float
    spatial_y: float
    semantic_label: str


@dataclass
class LayerAttention:
    layer_name: str
    head_idx: int
    max_attention: float
    object_attended: str
    spread: float


@dataclass
class InterpretabilityResult:
    policy_name: str
    task_name: str
    episode_id: int
    top_attention_regions: list
    layer_breakdown: list
    action_feature_importance: dict
    success: bool


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

POLICIES = ["dagger_run9", "dagger_run5", "bc_baseline"]
TASKS = ["pick_and_place", "stack_blocks", "drawer_open"]
REGIONS = ["target_object", "gripper", "workspace_center", "background", "robot_arm"]
LAYERS = ["early_visual", "mid_visual", "semantic", "decision"]

# Spatial positions for each region (normalized 0-1 grid)
REGION_POSITIONS = {
    "target_object":    (0.45, 0.55),
    "gripper":          (0.50, 0.35),
    "workspace_center": (0.50, 0.50),
    "background":       (0.20, 0.20),
    "robot_arm":        (0.60, 0.30),
}

# Base attention weights per policy
POLICY_BASE_ATTENTION = {
    "dagger_run9": {
        "target_object":    0.62,
        "gripper":          0.24,
        "workspace_center": 0.08,
        "background":       0.03,
        "robot_arm":        0.03,
    },
    "dagger_run5": {
        "target_object":    0.50,
        "gripper":          0.26,
        "workspace_center": 0.12,
        "background":       0.07,
        "robot_arm":        0.05,
    },
    "bc_baseline": {
        "target_object":    0.38,
        "gripper":          0.21,
        "workspace_center": 0.15,
        "background":       0.18,
        "robot_arm":        0.08,
    },
}

# Layer focus profile: what each layer primarily attends to and its spread
LAYER_PROFILE = {
    "early_visual": {"object_attended": "background",      "base_attention": 0.55, "spread": 0.82},
    "mid_visual":   {"object_attended": "workspace_center","base_attention": 0.60, "spread": 0.65},
    "semantic":     {"object_attended": "target_object",   "base_attention": 0.72, "spread": 0.45},
    "decision":     {"object_attended": "target_object",   "base_attention": 0.85, "spread": 0.28},
}

# Feature importance for best policy
FEATURE_IMPORTANCE_BEST = {
    "target_position": 0.41,
    "gripper_state":   0.28,
    "joint_angles":    0.18,
    "wrist_image":     0.08,
    "background":      0.05,
}

# Success rates per policy × task
SUCCESS_RATES = {
    ("dagger_run9", "pick_and_place"):  0.85,
    ("dagger_run9", "stack_blocks"):    0.80,
    ("dagger_run9", "drawer_open"):     0.90,
    ("dagger_run5", "pick_and_place"):  0.65,
    ("dagger_run5", "stack_blocks"):    0.60,
    ("dagger_run5", "drawer_open"):     0.70,
    ("bc_baseline", "pick_and_place"):  0.35,
    ("bc_baseline", "stack_blocks"):    0.30,
    ("bc_baseline", "drawer_open"):     0.40,
}


def simulate_attention(policy: str, task: str, episode_id: int, rng: random.Random) -> InterpretabilityResult:
    base = POLICY_BASE_ATTENTION[policy]
    noise_scale = 0.03

    # Jitter weights and renormalize
    raw = {r: max(0.01, base[r] + rng.gauss(0, noise_scale)) for r in REGIONS}
    total = sum(raw.values())
    weights = {r: raw[r] / total for r in REGIONS}

    regions = []
    for r in REGIONS:
        sx, sy = REGION_POSITIONS[r]
        sx += rng.gauss(0, 0.02)
        sy += rng.gauss(0, 0.02)
        regions.append(AttentionRegion(
            region_name=r,
            attention_weight=round(weights[r], 4),
            spatial_x=round(sx, 3),
            spatial_y=round(sy, 3),
            semantic_label=r.replace("_", " ").title(),
        ))
    regions.sort(key=lambda x: x.attention_weight, reverse=True)

    # Layer breakdown
    layers = []
    for head_idx, layer_name in enumerate(LAYERS):
        prof = LAYER_PROFILE[layer_name]
        att = round(min(0.99, max(0.01, prof["base_attention"] + rng.gauss(0, 0.04))), 4)
        sp = round(min(0.99, max(0.01, prof["spread"] + rng.gauss(0, 0.03))), 4)
        layers.append(LayerAttention(
            layer_name=layer_name,
            head_idx=head_idx,
            max_attention=att,
            object_attended=prof["object_attended"],
            spread=sp,
        ))

    # Feature importance (perturb slightly per episode)
    fi = {}
    for k, v in FEATURE_IMPORTANCE_BEST.items():
        fi[k] = round(max(0.01, v + rng.gauss(0, 0.015)), 4)
    fi_total = sum(fi.values())
    fi = {k: round(v / fi_total, 4) for k, v in fi.items()}

    sr = SUCCESS_RATES.get((policy, task), 0.5)
    success = rng.random() < sr

    return InterpretabilityResult(
        policy_name=policy,
        task_name=task,
        episode_id=episode_id,
        top_attention_regions=regions,
        layer_breakdown=layers,
        action_feature_importance=fi,
        success=success,
    )


def run_mock_analysis(seed: int = 42) -> list:
    rng = random.Random(seed)
    results = []
    for policy in POLICIES:
        for task in TASKS:
            for ep in range(10):
                results.append(simulate_attention(policy, task, ep, rng))
    return results


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def aggregate(results: list) -> dict:
    from collections import defaultdict

    policy_stats = defaultdict(lambda: {
        "target_attention": [],
        "background_attention": [],
        "success": [],
    })

    for r in results:
        weights = {ar.region_name: ar.attention_weight for ar in r.top_attention_regions}
        policy_stats[r.policy_name]["target_attention"].append(weights.get("target_object", 0))
        policy_stats[r.policy_name]["background_attention"].append(weights.get("background", 0))
        policy_stats[r.policy_name]["success"].append(int(r.success))

    summary = {}
    for p, s in policy_stats.items():
        ta = sum(s["target_attention"]) / len(s["target_attention"])
        bg = sum(s["background_attention"]) / len(s["background_attention"])
        sr = sum(s["success"]) / len(s["success"])
        summary[p] = {
            "target_attention": round(ta, 4),
            "background_attention": round(bg, 4),
            "focus_ratio": round(ta / bg, 2) if bg > 0 else 99.0,
            "success_rate": round(sr, 4),
        }

    # Per-layer averages (first result representative — all same structure)
    layer_summary = {}
    for r in results:
        for la in r.layer_breakdown:
            if la.layer_name not in layer_summary:
                layer_summary[la.layer_name] = {"max_attention": [], "spread": [], "object_attended": la.object_attended}
            layer_summary[la.layer_name]["max_attention"].append(la.max_attention)
            layer_summary[la.layer_name]["spread"].append(la.spread)
    for ln, v in layer_summary.items():
        v["avg_attention"] = round(sum(v["max_attention"]) / len(v["max_attention"]), 4)
        v["avg_spread"] = round(sum(v["spread"]) / len(v["spread"]), 4)

    # Feature importance average
    fi_agg = {}
    for r in results:
        for k, v in r.action_feature_importance.items():
            fi_agg.setdefault(k, []).append(v)
    fi_avg = {k: round(sum(v) / len(v), 4) for k, v in fi_agg.items()}
    fi_avg = dict(sorted(fi_avg.items(), key=lambda x: x[1], reverse=True))

    return {"policy_summary": summary, "layer_summary": layer_summary, "feature_importance": fi_avg}


# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------

def _bar_svg(policy_data: dict) -> str:
    """Attention heatmap: 3 policies × 5 regions as colored bars."""
    width, height = 620, 260
    bar_h = 22
    gap = 6
    left = 120
    right_pad = 20
    chart_w = width - left - right_pad
    top_pad = 30

    region_colors = {
        "target_object":    "#C74634",
        "gripper":          "#3b82f6",
        "workspace_center": "#10b981",
        "background":       "#6b7280",
        "robot_arm":        "#f59e0b",
    }

    svg = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px">']
    svg.append('<rect width="100%" height="100%" fill="#0f172a" rx="8"/>')
    svg.append(f'<text x="{width//2}" y="18" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Attention Weight by Region &amp; Policy</text>')

    for pi, (policy, regions) in enumerate(policy_data.items()):
        y_base = top_pad + pi * (len(REGIONS) * (bar_h + gap) + 20)
        svg.append(f'<text x="4" y="{y_base + 10}" fill="#e2e8f0" font-size="11" font-family="monospace">{policy}</text>')
        for ri, region in enumerate(REGIONS):
            y = y_base + 18 + ri * (bar_h + gap)
            w = int(regions.get(region, 0) * chart_w)
            color = region_colors.get(region, "#888")
            svg.append(f'<rect x="{left}" y="{y}" width="{w}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>')
            svg.append(f'<text x="{left - 4}" y="{y + bar_h - 6}" fill="#94a3b8" font-size="9" text-anchor="end" font-family="monospace">{region[:12]}</text>')
            svg.append(f'<text x="{left + w + 4}" y="{y + bar_h - 6}" fill="#e2e8f0" font-size="9" font-family="monospace">{regions.get(region, 0):.2f}</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def _layer_svg(layer_summary: dict) -> str:
    """Layer-by-layer max attention and spread."""
    width, height = 540, 200
    layers = list(layer_summary.keys())
    n = len(layers)
    left, right_pad, top_pad, bot_pad = 90, 20, 30, 40
    chart_w = width - left - right_pad
    chart_h = height - top_pad - bot_pad
    bar_w = chart_w // n - 10

    svg = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px">']
    svg.append('<rect width="100%" height="100%" fill="#0f172a" rx="8"/>')
    svg.append(f'<text x="{width//2}" y="18" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Layer-by-Layer Attention Shift</text>')

    # Y axis labels
    for pct in [0, 0.25, 0.5, 0.75, 1.0]:
        y = top_pad + chart_h - int(pct * chart_h)
        svg.append(f'<line x1="{left}" y1="{y}" x2="{width - right_pad}" y2="{y}" stroke="#1e3a5f" stroke-width="1"/>')
        svg.append(f'<text x="{left - 4}" y="{y + 4}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{pct:.2f}</text>')

    for i, layer_name in enumerate(layers):
        v = layer_summary[layer_name]
        att = v["avg_attention"]
        spread = v["avg_spread"]
        x = left + i * (chart_w // n) + 5
        bar_h = int(att * chart_h)
        y = top_pad + chart_h - bar_h
        svg.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="#C74634" rx="3" opacity="0.8"/>')
        # spread as overlay
        sp_h = int(spread * chart_h)
        sp_y = top_pad + chart_h - sp_h
        svg.append(f'<rect x="{x}" y="{sp_y}" width="{bar_w}" height="{sp_h}" fill="#3b82f6" rx="3" opacity="0.3"/>')
        svg.append(f'<text x="{x + bar_w//2}" y="{height - 22}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{layer_name[:10]}</text>')
        svg.append(f'<text x="{x + bar_w//2}" y="{height - 10}" fill="#64748b" font-size="8" text-anchor="middle" font-family="monospace">{v["object_attended"][:8]}</text>')

    # Legend
    svg.append(f'<rect x="{left}" y="{top_pad + 4}" width="10" height="10" fill="#C74634" rx="2"/>')
    svg.append(f'<text x="{left + 14}" y="{top_pad + 13}" fill="#94a3b8" font-size="9" font-family="monospace">max attention</text>')
    svg.append(f'<rect x="{left + 100}" y="{top_pad + 4}" width="10" height="10" fill="#3b82f6" rx="2" opacity="0.5"/>')
    svg.append(f'<text x="{left + 114}" y="{top_pad + 13}" fill="#94a3b8" font-size="9" font-family="monospace">spread</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def _feature_svg(fi: dict) -> str:
    """Horizontal bar chart for feature importance."""
    items = list(fi.items())
    width, height = 500, 40 + len(items) * 38
    left, right_pad = 140, 60
    chart_w = width - left - right_pad

    colors = ["#C74634", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]

    svg = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px">']
    svg.append('<rect width="100%" height="100%" fill="#0f172a" rx="8"/>')
    svg.append(f'<text x="{width//2}" y="18" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Feature Importance — Action Prediction</text>')

    for i, (feat, val) in enumerate(items):
        y = 30 + i * 38
        bar_w = int(val * chart_w)
        color = colors[i % len(colors)]
        svg.append(f'<rect x="{left}" y="{y}" width="{bar_w}" height="22" fill="{color}" rx="3" opacity="0.85"/>')
        svg.append(f'<text x="{left - 6}" y="{y + 15}" fill="#cbd5e1" font-size="10" text-anchor="end" font-family="monospace">{feat}</text>')
        svg.append(f'<text x="{left + bar_w + 6}" y="{y + 15}" fill="#e2e8f0" font-size="10" font-family="monospace">{val:.3f}</text>')
        pct = val * 100
        svg.append(f'<text x="{left + bar_w//2}" y="{y + 15}" fill="white" font-size="9" text-anchor="middle" font-family="monospace">{pct:.1f}%</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def build_html(results: list, agg: dict, output_path: str) -> None:
    ps = agg["policy_summary"]
    ls = agg["layer_summary"]
    fi = agg["feature_importance"]

    # Stat card values
    best_focus_policy = max(ps, key=lambda p: ps[p]["target_attention"])
    best_focus_val = ps[best_focus_policy]["target_attention"]
    worst_bg_policy = max(ps, key=lambda p: ps[p]["background_attention"])
    worst_bg_val = ps[worst_bg_policy]["background_attention"]
    most_interp_layer = max(ls, key=lambda l: ls[l]["avg_attention"])
    top_feature = list(fi.keys())[0]
    top_feature_val = list(fi.values())[0]

    # SVG data for heatmap (mean per policy)
    from collections import defaultdict
    policy_region_means = {p: defaultdict(list) for p in POLICIES}
    for r in results:
        for ar in r.top_attention_regions:
            policy_region_means[r.policy_name][ar.region_name].append(ar.attention_weight)
    policy_region_avg = {
        p: {reg: round(sum(v) / len(v), 3) for reg, v in regmap.items()}
        for p, regmap in policy_region_means.items()
    }

    bar_svg = _bar_svg(policy_region_avg)
    layer_svg = _layer_svg(ls)
    feat_svg = _feature_svg(fi)

    # Table rows
    table_rows = ""
    for p in POLICIES:
        s = ps[p]
        sr_pct = f"{s['success_rate']*100:.1f}%"
        table_rows += f"""
        <tr>
          <td style="color:#e2e8f0;font-weight:600">{p}</td>
          <td style="color:#C74634">{s['target_attention']:.3f}</td>
          <td style="color:#f59e0b">{s['background_attention']:.3f}</td>
          <td style="color:#10b981">{s['focus_ratio']:.1f}×</td>
          <td style="color:#3b82f6">{sr_pct}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>GR00T Model Interpretability Analysis</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; color: #f8fafc; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #0f172a; border: 1px solid #1e3a5f; border-radius: 10px; padding: 18px 20px; }}
  .card-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .card-value {{ font-size: 28px; font-weight: 700; color: #C74634; }}
  .card-sub {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
  .section {{ background: #0f172a; border: 1px solid #1e3a5f; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  .section h2 {{ font-size: 15px; color: #cbd5e1; margin-bottom: 16px; border-bottom: 1px solid #1e3a5f; padding-bottom: 8px; }}
  .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #0f172a; color: #94a3b8; text-align: left; padding: 10px 14px; font-weight: 500; border-bottom: 1px solid #1e3a5f; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #1a2744; }}
  tr:hover td {{ background: #162032; }}
  .insight {{ background: #162032; border-left: 3px solid #C74634; padding: 14px 18px; border-radius: 6px; color: #94a3b8; font-size: 13px; line-height: 1.7; margin-top: 20px; }}
  .insight strong {{ color: #e2e8f0; }}
  @media (max-width: 900px) {{ .cards {{ grid-template-columns: repeat(2,1fr); }} .charts-row {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>GR00T Model Interpretability Analysis</h1>
<p class="subtitle">Visual attention maps, saliency scores, and feature importance for action prediction — 3 policies × 3 tasks × 10 episodes = 90 samples</p>

<div class="cards">
  <div class="card">
    <div class="card-label">Best Focus Policy</div>
    <div class="card-value">{best_focus_val:.2f}</div>
    <div class="card-sub">target attention — {best_focus_policy}</div>
  </div>
  <div class="card">
    <div class="card-label">Background Attention (worst)</div>
    <div class="card-value" style="color:#f59e0b">{worst_bg_val:.2f}</div>
    <div class="card-sub">wasted capacity — {worst_bg_policy}</div>
  </div>
  <div class="card">
    <div class="card-label">Most Interpretable Layer</div>
    <div class="card-value" style="color:#10b981;font-size:20px">{most_interp_layer}</div>
    <div class="card-sub">highest avg attention: {ls[most_interp_layer]['avg_attention']:.3f}</div>
  </div>
  <div class="card">
    <div class="card-label">Top Feature</div>
    <div class="card-value" style="color:#3b82f6;font-size:18px">{top_feature}</div>
    <div class="card-sub">importance: {top_feature_val:.3f} ({top_feature_val*100:.1f}%)</div>
  </div>
</div>

<div class="section">
  <h2>Attention Weight Heatmap — Policies vs. Regions</h2>
  {bar_svg}
</div>

<div class="charts-row">
  <div class="section">
    <h2>Layer-by-Layer Attention Shift</h2>
    {layer_svg}
  </div>
  <div class="section">
    <h2>Feature Importance (Action Prediction)</h2>
    {feat_svg}
  </div>
</div>

<div class="section">
  <h2>Policy Attention Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Policy</th>
        <th>Target Attention</th>
        <th>Background Attention</th>
        <th>Focus Ratio (target/bg)</th>
        <th>Success Rate</th>
      </tr>
    </thead>
    <tbody>{table_rows}
    </tbody>
  </table>

  <div class="insight">
    <strong>Key Insight:</strong> Higher <em>target_attention</em> strongly correlates with task success rate.
    <strong>dagger_run9</strong> concentrates {best_focus_val:.0%} of attention on the target object versus
    only {ps['bc_baseline']['target_attention']:.0%} for bc_baseline — a {best_focus_val/ps['bc_baseline']['target_attention']:.1f}× difference.
    <strong>Background attention is wasted capacity</strong>: bc_baseline allocates {ps['bc_baseline']['background_attention']:.0%} to background
    (vs {ps['dagger_run9']['background_attention']:.0%} for dagger_run9), explaining its lower success rate of
    {ps['bc_baseline']['success_rate']*100:.0f}% vs {ps['dagger_run9']['success_rate']*100:.0f}%.
    The <em>decision</em> layer shows the highest focused attention ({ls['decision']['avg_attention']:.3f}),
    confirming that late transformer layers are most responsible for action-relevant feature extraction.
    Top action predictor: <em>{top_feature}</em> at {top_feature_val*100:.1f}% importance.
  </div>
</div>

</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(agg: dict) -> None:
    ps = agg["policy_summary"]
    fi = agg["feature_importance"]
    ls = agg["layer_summary"]

    print("\n" + "=" * 60)
    print("  GR00T Model Interpretability — Attention Summary")
    print("=" * 60)
    print(f"\n{'Policy':<18} {'TargetAttn':>10} {'BgAttn':>8} {'FocusRatio':>12} {'SuccessRate':>12}")
    print("-" * 60)
    for p in POLICIES:
        s = ps[p]
        print(f"{p:<18} {s['target_attention']:>10.3f} {s['background_attention']:>8.3f} {s['focus_ratio']:>11.1f}x {s['success_rate']*100:>10.1f}%")

    print("\n  Layer Breakdown:")
    print(f"  {'Layer':<18} {'AvgAttention':>13} {'AvgSpread':>10} {'PrimaryObject':<16}")
    print("  " + "-" * 58)
    for ln, v in ls.items():
        print(f"  {ln:<18} {v['avg_attention']:>13.3f} {v['avg_spread']:>10.3f} {v['object_attended']:<16}")

    print("\n  Feature Importance (Action Prediction):")
    for feat, val in fi.items():
        bar = "█" * int(val * 40)
        print(f"  {feat:<20} {val:.3f}  {bar}")

    best = max(ps, key=lambda p: ps[p]["target_attention"])
    worst = max(ps, key=lambda p: ps[p]["background_attention"])
    print(f"\n  Best focus policy : {best} (target_attention={ps[best]['target_attention']:.3f})")
    print(f"  Most distracted   : {worst} (background={ps[worst]['background_attention']:.3f})")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="GR00T visual attention and feature importance analyzer"
    )
    parser.add_argument("--mock", action="store_true", help="Run with simulated data (no GPU required)")
    parser.add_argument("--output", default="/tmp/model_interpretability_analyzer.html", help="Output HTML path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for simulation")
    args = parser.parse_args()

    if not args.mock:
        print("[INFO] No live inference mode implemented yet. Re-run with --mock to use simulated data.")
        return

    print(f"[INFO] Running mock attention analysis (seed={args.seed}) ...")
    results = run_mock_analysis(seed=args.seed)
    print(f"[INFO] Generated {len(results)} InterpretabilityResult samples "
          f"({len(POLICIES)} policies × {len(TASKS)} tasks × 10 episodes)")

    agg = aggregate(results)
    print_summary(agg)

    print(f"[INFO] Building HTML report -> {args.output}")
    build_html(results, agg, args.output)
    print(f"[INFO] Report saved: {args.output}")


if __name__ == "__main__":
    main()
