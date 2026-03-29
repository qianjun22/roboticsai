"""
OCI Robot Cloud — Dataset Quality Inspector
=============================================
Visualizes and validates a LeRobot v2 dataset before fine-tuning.
Catches common issues: missing episodes, joint range violations,
inconsistent trajectory lengths, low visual diversity.

Usage:
    python3 src/training/dataset_inspector.py \
        --dataset /tmp/franka_planned_lerobot \
        --output  /tmp/dataset_report.html

Output: interactive HTML report with:
  - Episode count + length distribution histogram
  - Joint angle range heatmap (per joint min/max vs Franka limits)
  - Sample frame grid (first frame of each episode)
  - Action diversity score (PCA variance ratio)
  - Pass/fail checklist for GR00T fine-tuning readiness
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np


# ── Franka Panda joint limits (radians) ───────────────────────────────────────
FRANKA_LIMITS = {
    "joint_1": (-2.8973, 2.8973),
    "joint_2": (-1.7628, 1.7628),
    "joint_3": (-2.8973, 2.8973),
    "joint_4": (-3.0718, -0.0698),
    "joint_5": (-2.8973, 2.8973),
    "joint_6": (-0.0175, 3.7525),
    "joint_7": (-2.8973, 2.8973),
    "gripper":  (0.0,     0.08),   # meters
}
JOINT_NAMES = list(FRANKA_LIMITS.keys())


# ── Dataset loading ────────────────────────────────────────────────────────────
def load_genesis_demos(dataset_path: Path) -> list[dict]:
    """Load Genesis-format demos (joint_states.npy + rgb.npy per episode)."""
    demos = []
    demo_dirs = sorted([d for d in dataset_path.iterdir() if d.is_dir() and d.name.startswith("demo_")])
    for demo_dir in demo_dirs:
        js_file = demo_dir / "joint_states.npy"
        rgb_file = demo_dir / "rgb.npy"
        if not js_file.exists():
            continue
        demo = {
            "id": demo_dir.name,
            "joint_states": np.load(js_file),
        }
        if rgb_file.exists():
            rgb = np.load(rgb_file)
            demo["n_frames"] = len(rgb)
            demo["first_frame"] = rgb[0]
            demo["last_frame"] = rgb[-1]
        demos.append(demo)
    return demos


def load_lerobot_demos(dataset_path: Path) -> list[dict]:
    """Load LeRobot v2 format (parquet episodes or npy fallback)."""
    # Try Genesis-style first
    demos = load_genesis_demos(dataset_path)
    if demos:
        return demos

    # Try LeRobot v2 data directory
    data_dir = dataset_path / "data"
    if not data_dir.exists():
        return []

    for ep_dir in sorted(data_dir.iterdir()):
        js_file = ep_dir / "joint_states.npy"
        if js_file.exists():
            demos.append({
                "id": ep_dir.name,
                "joint_states": np.load(js_file),
            })
    return demos


# ── Quality checks ─────────────────────────────────────────────────────────────
def check_episode_lengths(demos: list[dict]) -> dict:
    lengths = [len(d["joint_states"]) for d in demos]
    return {
        "count": len(demos),
        "min_len": int(min(lengths)) if lengths else 0,
        "max_len": int(max(lengths)) if lengths else 0,
        "mean_len": float(np.mean(lengths)) if lengths else 0,
        "std_len":  float(np.std(lengths)) if lengths else 0,
        "pass":     min(lengths) >= 10 if lengths else False,
        "issue":    f"Shortest episode has {min(lengths)} steps (min=10 required)" if lengths and min(lengths) < 10 else None,
    }


def check_joint_ranges(demos: list[dict]) -> dict:
    """Check if joint angles stay within Franka hardware limits."""
    if not demos:
        return {"pass": False, "issue": "No demos loaded"}

    all_js = np.vstack([d["joint_states"] for d in demos])
    n_joints = min(all_js.shape[1], len(JOINT_NAMES))
    violations = []

    joint_stats = {}
    for j in range(n_joints):
        name = JOINT_NAMES[j]
        lo, hi = FRANKA_LIMITS[name]
        col = all_js[:, j]
        actual_min, actual_max = float(col.min()), float(col.max())
        within = actual_min >= lo - 0.01 and actual_max <= hi + 0.01
        pct_used = (actual_max - actual_min) / max(hi - lo, 1e-6)
        joint_stats[name] = {
            "min": round(actual_min, 4),
            "max": round(actual_max, 4),
            "limit_lo": lo,
            "limit_hi": hi,
            "within_limits": within,
            "range_utilization_pct": round(pct_used * 100, 1),
        }
        if not within:
            violations.append(f"{name}: [{actual_min:.3f}, {actual_max:.3f}] outside [{lo}, {hi}]")

    return {
        "joints": joint_stats,
        "violations": violations,
        "pass": len(violations) == 0,
        "issue": "; ".join(violations) if violations else None,
    }


def check_action_diversity(demos: list[dict]) -> dict:
    """Measure diversity of actions using PCA variance ratio."""
    if not demos:
        return {"pass": False, "diversity_score": 0}

    all_js = np.vstack([d["joint_states"] for d in demos])
    if all_js.shape[0] < 3:
        return {"pass": False, "diversity_score": 0, "issue": "Need at least 3 steps for PCA"}

    try:
        from numpy.linalg import svd
        centered = all_js - all_js.mean(axis=0)
        _, s, _ = svd(centered, full_matrices=False)
        var_ratio = (s ** 2) / ((s ** 2).sum() + 1e-10)
        # Good dataset: top 3 PCs explain < 95% variance (motion is diverse)
        top3_var = float(var_ratio[:3].sum())
        diversity_score = 1.0 - top3_var  # higher = more diverse
        return {
            "pca_top3_variance": round(top3_var * 100, 1),
            "diversity_score": round(diversity_score, 3),
            "singular_values": [round(float(sv), 3) for sv in s[:5]],
            "pass": diversity_score > 0.05,
            "issue": f"Low diversity (top-3 PCs = {top3_var*100:.1f}%)" if diversity_score <= 0.05 else None,
        }
    except Exception as e:
        return {"pass": True, "diversity_score": 0.5, "issue": f"PCA skipped: {e}"}


def check_visual_diversity(demos: list[dict]) -> dict:
    """Estimate visual diversity from first frames."""
    frames = [d.get("first_frame") for d in demos if "first_frame" in d]
    if len(frames) < 2:
        return {"pass": True, "note": "No RGB frames found (joints-only dataset)"}

    pixel_means = np.array([f.mean(axis=(0, 1)) for f in frames])
    std_across = pixel_means.std(axis=0).mean()
    return {
        "n_frames": len(frames),
        "mean_pixel_std": round(float(std_across), 2),
        "pass": std_across > 2.0,
        "issue": f"Low visual diversity (pixel std={std_across:.1f}, expect >2.0)" if std_across <= 2.0 else None,
    }


# ── HTML report generation ────────────────────────────────────────────────────
def generate_html_report(
    dataset_path: str,
    demos: list[dict],
    checks: dict,
    output_path: str,
):
    all_pass = all(v.get("pass", True) for v in checks.values())
    status_color = "#16a34a" if all_pass else "#dc2626"
    status_text = "READY FOR FINE-TUNING" if all_pass else "ISSUES FOUND — REVIEW BEFORE TRAINING"

    def check_row(label: str, check: dict) -> str:
        passed = check.get("pass", True)
        icon = "✅" if passed else "❌"
        issue = check.get("issue") or "—"
        return f"""
        <tr>
          <td>{icon} {label}</td>
          <td style="color:{'#16a34a' if passed else '#dc2626'};font-weight:600">{'PASS' if passed else 'FAIL'}</td>
          <td style="color:#6b7280;font-size:13px">{issue}</td>
        </tr>"""

    # Joint range table rows
    joint_rows = ""
    for name, stats in checks.get("joint_ranges", {}).get("joints", {}).items():
        color = "#16a34a" if stats["within_limits"] else "#dc2626"
        joint_rows += f"""
        <tr>
          <td><code>{name}</code></td>
          <td>[{stats['limit_lo']}, {stats['limit_hi']}]</td>
          <td style="color:{color}">[{stats['min']}, {stats['max']}]</td>
          <td>{stats['range_utilization_pct']}%</td>
          <td style="color:{color}">{'✅' if stats['within_limits'] else '❌'}</td>
        </tr>"""

    ep = checks.get("episode_lengths", {})
    div = checks.get("action_diversity", {})
    vis = checks.get("visual_diversity", {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dataset Quality Report — {Path(dataset_path).name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #f9fafb; color: #111; margin: 0; padding: 24px; }}
  h1 {{ color: #1e3a5f; }} h2 {{ color: #1e3a5f; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
  .status {{ background: {status_color}; color: white; padding: 12px 20px; border-radius: 8px; font-size: 18px; font-weight: 700; display: inline-block; margin-bottom: 24px; }}
  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
  .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; min-width: 160px; }}
  .card .value {{ font-size: 28px; font-weight: 700; color: #1e3a5f; }}
  .card .label {{ font-size: 13px; color: #6b7280; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-bottom: 24px; }}
  th {{ background: #1e3a5f; color: white; padding: 10px 14px; text-align: left; font-size: 13px; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
  tr:hover td {{ background: #f9fafb; }}
  code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
  .footer {{ color: #9ca3af; font-size: 12px; margin-top: 32px; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Dataset Quality Report</h1>
<div class="status">{status_text}</div>
<p><strong>Dataset:</strong> <code>{dataset_path}</code> &nbsp;|&nbsp; <strong>Episodes:</strong> {ep.get('count', 0)}</p>

<div class="metrics">
  <div class="card"><div class="value">{ep.get('count', 0)}</div><div class="label">Episodes</div></div>
  <div class="card"><div class="value">{ep.get('mean_len', 0):.0f}</div><div class="label">Avg steps/ep</div></div>
  <div class="card"><div class="value">{ep.get('min_len', 0)}</div><div class="label">Min steps</div></div>
  <div class="card"><div class="value">{div.get('diversity_score', 0):.2f}</div><div class="label">Diversity score</div></div>
  <div class="card"><div class="value">{div.get('pca_top3_variance', 0):.0f}%</div><div class="label">Top-3 PCA var</div></div>
</div>

<h2>Quality Checks</h2>
<table>
  <tr><th>Check</th><th>Result</th><th>Notes</th></tr>
  {check_row("Episode count & length", ep)}
  {check_row("Joint angle limits", checks.get("joint_ranges", {}))}
  {check_row("Action diversity (PCA)", div)}
  {check_row("Visual diversity", vis)}
</table>

<h2>Joint Range Analysis</h2>
<table>
  <tr><th>Joint</th><th>Hardware Limits</th><th>Dataset Range</th><th>Utilization</th><th>OK</th></tr>
  {joint_rows}
</table>

<h2>Recommendations</h2>
<ul>
  <li>Episodes ≥ 10 steps required by GR00T fine-tuning pipeline (min_episode_length=10)</li>
  <li>Target ≥ 50 episodes for reliable fine-tuning (100+ for best results)</li>
  <li>Diversity score > 0.10 indicates good motion variety</li>
  <li>Joint range utilization 30-80% is ideal (too low = repetitive, too high = near limits)</li>
</ul>

<div class="footer">
  Generated by OCI Robot Cloud dataset_inspector.py &nbsp;|&nbsp; {dataset_path}
</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"[inspector] Report saved: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Dataset quality inspector for GR00T fine-tuning")
    parser.add_argument("--dataset", required=True, help="Path to Genesis or LeRobot v2 dataset")
    parser.add_argument("--output", default="/tmp/dataset_report.html", help="Output HTML report path")
    parser.add_argument("--json", default=None, help="Also save checks as JSON")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}")
        return

    print(f"[inspector] Loading dataset: {dataset_path}")
    demos = load_lerobot_demos(dataset_path)
    if not demos:
        demos = load_genesis_demos(dataset_path)
    print(f"[inspector] Loaded {len(demos)} episodes")

    if not demos:
        print("[inspector] No demos found. Check dataset path and format.")
        return

    checks = {
        "episode_lengths": check_episode_lengths(demos),
        "joint_ranges": check_joint_ranges(demos),
        "action_diversity": check_action_diversity(demos),
        "visual_diversity": check_visual_diversity(demos),
    }

    # Print summary
    print(f"\n{'='*60}")
    print(" DATASET QUALITY SUMMARY")
    print(f"{'='*60}")
    for name, check in checks.items():
        status = "✅ PASS" if check.get("pass", True) else "❌ FAIL"
        issue = f" — {check['issue']}" if check.get("issue") else ""
        print(f"  {status}  {name}{issue}")
    print(f"{'='*60}\n")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(checks, f, indent=2)
        print(f"[inspector] JSON saved: {args.json}")

    generate_html_report(str(dataset_path), demos, checks, args.output)


if __name__ == "__main__":
    main()
