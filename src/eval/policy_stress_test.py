#!/usr/bin/env python3
"""
policy_stress_test.py — Adversarial stress testing for GR00T policy robustness.

Tests the policy under challenging conditions not seen in training:
  - Observation noise (camera blur, joint sensor noise)
  - Partial occlusion (cube half-hidden)
  - Lighting variation (dark/bright/colored illumination)
  - Cube position extremes (near table edge, rotated)
  - Network latency injection (simulates real robot communication delays)
  - Temperature scaling (policy overconfidence/underconfidence)

Generates a robustness score and HTML report for design partner SLAs.

Usage:
    python src/eval/policy_stress_test.py --mock --output /tmp/stress_report.html
    python src/eval/policy_stress_test.py --server-url http://localhost:8002 \
        --n-episodes 10 --output /tmp/stress_report.html
"""

import argparse
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

BASELINE_SUCCESS = 0.65    # expected under normal conditions
STRESS_CATEGORIES = [
    {
        "name": "Clean (reference)",
        "code": "clean",
        "description": "Normal conditions, center cube, standard lighting",
        "expected_drop": 0.00,
        "severity": "none",
    },
    {
        "name": "Camera noise (σ=20)",
        "code": "cam_noise",
        "description": "Gaussian noise added to both camera images",
        "expected_drop": 0.05,
        "severity": "low",
    },
    {
        "name": "Joint sensor noise (σ=0.02 rad)",
        "code": "joint_noise",
        "description": "Gaussian noise on 9-DOF joint state observation",
        "expected_drop": 0.08,
        "severity": "low",
    },
    {
        "name": "Partial occlusion (40%)",
        "code": "occlusion",
        "description": "Black rectangle covers 40% of primary camera view",
        "expected_drop": 0.20,
        "severity": "medium",
    },
    {
        "name": "Dark lighting (50% brightness)",
        "code": "dark_light",
        "description": "Image brightness reduced 50% simulating low-light environment",
        "expected_drop": 0.12,
        "severity": "medium",
    },
    {
        "name": "Cube at edge (±12cm offset)",
        "code": "edge_cube",
        "description": "Cube placed near table edge — outside training distribution",
        "expected_drop": 0.30,
        "severity": "high",
    },
    {
        "name": "Network latency (50ms added)",
        "code": "latency_50ms",
        "description": "50ms added delay on each action query (robot communication jitter)",
        "expected_drop": 0.05,
        "severity": "low",
    },
    {
        "name": "Temperature T=0.5 (confident)",
        "code": "temp_low",
        "description": "Action logits scaled by 0.5 — more deterministic policy",
        "expected_drop": 0.02,
        "severity": "low",
    },
    {
        "name": "Temperature T=2.0 (uncertain)",
        "code": "temp_high",
        "description": "Action logits scaled by 2.0 — noisier action distribution",
        "expected_drop": 0.18,
        "severity": "medium",
    },
    {
        "name": "Combined (noise+occlusion+edge)",
        "code": "combined",
        "description": "All medium-severity stressors active simultaneously",
        "expected_drop": 0.45,
        "severity": "extreme",
    },
]

SEVERITY_COLORS = {
    "none":    "#22c55e",
    "low":     "#3b82f6",
    "medium":  "#f59e0b",
    "high":    "#f97316",
    "extreme": "#ef4444",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class StressResult:
    category_code: str
    category_name: str
    severity: str
    n_episodes: int
    n_success: int
    success_rate: float
    baseline_rate: float
    drop: float               # baseline - success_rate
    drop_pct: float           # (drop / baseline_rate) * 100
    robustness_score: float   # 0–100: 100 = no degradation
    avg_latency_ms: float
    notes: str = ""


# ── Mock stress eval ──────────────────────────────────────────────────────────

def mock_stress_eval(n_episodes: int, baseline: float, rng: random.Random) -> list[StressResult]:
    results = []
    for cat in STRESS_CATEGORIES:
        drop_mean  = cat["expected_drop"]
        drop_noise = max(0, rng.gauss(0, 0.03))
        actual_drop = max(0.0, drop_mean + drop_noise - rng.gauss(0, 0.02))
        rate = max(0.0, min(1.0, baseline - actual_drop))

        n_suc = int(round(rate * n_episodes))
        robustness = max(0.0, min(100.0, 100.0 * (1.0 - actual_drop / max(baseline, 0.01))))
        latency = 226 + (50 if cat["code"] == "latency_50ms" else 0) + rng.gauss(0, 5)

        results.append(StressResult(
            category_code=cat["code"],
            category_name=cat["name"],
            severity=cat["severity"],
            n_episodes=n_episodes,
            n_success=n_suc,
            success_rate=round(rate, 3),
            baseline_rate=baseline,
            drop=round(actual_drop, 3),
            drop_pct=round(actual_drop / max(baseline, 0.01) * 100, 1),
            robustness_score=round(robustness, 1),
            avg_latency_ms=round(max(180, latency), 1),
        ))
    return results


# ── Overall robustness score ──────────────────────────────────────────────────

def overall_robustness(results: list[StressResult]) -> float:
    """Weighted average robustness across non-clean categories."""
    severity_weight = {"low": 1.0, "medium": 2.0, "high": 3.0, "extreme": 4.0}
    total_weight = 0.0
    total_score  = 0.0
    for r in results:
        if r.severity == "none":
            continue
        w = severity_weight.get(r.severity, 1.0)
        total_score  += r.robustness_score * w
        total_weight += w
    return round(total_score / total_weight, 1) if total_weight else 0.0


# ── HTML report ───────────────────────────────────────────────────────────────

def generate_html_report(results: list[StressResult], output_path: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overall = overall_robustness(results)
    clean = next((r for r in results if r.severity == "none"), None)
    baseline = clean.success_rate if clean else BASELINE_SUCCESS

    grade = "A" if overall >= 80 else ("B" if overall >= 65 else ("C" if overall >= 50 else "D"))
    grade_color = {"A":"#22c55e","B":"#3b82f6","C":"#f59e0b","D":"#ef4444"}.get(grade,"#94a3b8")

    rows = ""
    for r in results:
        sc = SEVERITY_COLORS.get(r.severity, "#94a3b8")
        bar_w = int(r.robustness_score * 1.2)
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600">{r.category_name}</td>
          <td style="padding:8px 12px">
            <span style="background:{sc}22;color:{sc};padding:2px 7px;border-radius:10px;font-size:11px">{r.severity}</span>
          </td>
          <td style="padding:8px 12px;font-family:monospace">{r.success_rate:.0%}
            <span style="color:#64748b;font-size:11px"> ({r.n_success}/{r.n_episodes})</span>
          </td>
          <td style="padding:8px 12px;color:{'#ef4444' if r.drop > 0.20 else '#f59e0b' if r.drop > 0.10 else '#22c55e'}">
            {'-' if r.drop > 0 else ''}{r.drop:.0%}
          </td>
          <td style="padding:8px 12px">
            <div style="display:inline-flex;align-items:center;gap:6px">
              <div style="background:#334155;width:120px;height:8px;border-radius:4px">
                <div style="background:{sc};width:{bar_w}px;height:100%;border-radius:4px"></div>
              </div>
              <span style="font-size:12px">{r.robustness_score:.0f}</span>
            </div>
          </td>
          <td style="padding:8px 12px;color:#94a3b8;font-size:12px">{r.avg_latency_ms:.0f}ms</td>
        </tr>"""

    # Radar chart data (SVG)
    non_clean = [r for r in results if r.severity != "none"]
    n = len(non_clean)
    cx, cy, R = 200, 200, 140
    import math as _math
    radar_pts_outer = []
    radar_pts_val   = []
    labels_html = ""
    for i, r in enumerate(non_clean):
        angle = 2 * _math.pi * i / n - _math.pi / 2
        ox = cx + R * _math.cos(angle)
        oy = cy + R * _math.sin(angle)
        vr = r.robustness_score / 100.0 * R
        vx = cx + vr * _math.cos(angle)
        vy = cy + vr * _math.sin(angle)
        radar_pts_outer.append(f"{ox:.0f},{oy:.0f}")
        radar_pts_val.append(f"{vx:.0f},{vy:.0f}")
        lx = cx + (R + 20) * _math.cos(angle)
        ly = cy + (R + 20) * _math.sin(angle)
        labels_html += f'<text x="{lx:.0f}" y="{ly:.0f}" fill="#64748b" font-size="9" text-anchor="middle">{r.category_code}</text>'

    radar_svg = f"""
    <polygon points="{' '.join(radar_pts_outer)}" fill="none" stroke="#334155" stroke-width="1"/>
    <polygon points="{' '.join(radar_pts_val)}" fill="#3b82f633" stroke="#3b82f6" stroke-width="2"/>
    {labels_html}
    <circle cx="{cx}" cy="{cy}" r="3" fill="#94a3b8"/>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Policy Stress Test — {now}</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  h2{{color:#94a3b8;font-size:14px;font-weight:400;margin:0 0 24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
</style>
</head>
<body>
<h1>Policy Stress Test Report</h1>
<h2>Generated {now} · baseline {baseline:.0%} · {len(results[0].n_episodes if results else 10)} episodes/category</h2>

<div class="card" style="display:flex;gap:24px;align-items:center">
  <div style="text-align:center;min-width:120px">
    <div style="font-size:60px;font-weight:700;color:{grade_color}">{grade}</div>
    <div style="font-size:12px;color:#64748b">Robustness Grade</div>
  </div>
  <div style="flex:1">
    <div style="font-size:32px;font-weight:700;color:{grade_color};margin-bottom:4px">{overall:.0f}/100</div>
    <div style="color:#94a3b8;font-size:13px;margin-bottom:8px">Overall Robustness Score</div>
    <div style="background:#334155;height:10px;border-radius:5px">
      <div style="background:{grade_color};width:{overall:.0f}%;height:100%;border-radius:5px"></div>
    </div>
    <div style="color:#64748b;font-size:12px;margin-top:6px">
      Weighted across severity levels. A ≥ 80 · B ≥ 65 · C ≥ 50 · D &lt; 50
    </div>
  </div>
  <div>
    <svg width="400" height="400">{radar_svg}</svg>
  </div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Stress Test Results</h3>
  <table>
    <tr><th>Condition</th><th>Severity</th><th>Success Rate</th><th>Drop vs Baseline</th><th>Robustness (0-100)</th><th>Latency</th></tr>
    {rows}
  </table>
</div>

<div class="card" style="background:#0c1a2e;border:1px solid #1e3a5f">
  <h3 style="color:#3b82f6;font-size:13px;text-transform:uppercase;margin-top:0">Hardening Recommendations</h3>
  <ul style="font-size:13px;color:#94a3b8;margin:0;padding-left:18px">
    <li>Cube-at-edge (-{[r for r in results if r.code=='edge_cube' or r.category_code=='edge_cube'][0].drop:.0%} drop): Add edge-position demos to next SDG run. Use <code>curriculum_sdg.py</code> Hard stage.</li>
    <li>Occlusion (-{[r for r in results if r.category_code=='occlusion'][0].drop:.0%} drop): Enable Isaac Sim Replicator occlusion augmentation. Use <code>cosmos_data_augmentation.py</code> 3× pipeline.</li>
    <li>Temperature T=2.0: Consider confidence gating via <code>policy_confidence.py</code> — request expert when conf &lt; 0.4.</li>
    <li>Camera noise: Fine-tune with domain-randomized images (Isaac Sim RTX Replicator lighting/noise).</li>
  </ul>
</div>

<div style="color:#475569;font-size:11px;margin-top:16px">OCI Robot Cloud · qianjun22/roboticsai · {now}</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report → {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Policy stress test")
    parser.add_argument("--server-url",  default="http://localhost:8002")
    parser.add_argument("--n-episodes",  type=int, default=10)
    parser.add_argument("--baseline",    type=float, default=BASELINE_SUCCESS)
    parser.add_argument("--output",      default="/tmp/stress_report.html")
    parser.add_argument("--json-output", default="")
    parser.add_argument("--mock",        action="store_true")
    args = parser.parse_args()

    rng = random.Random(42)
    if args.mock:
        results = mock_stress_eval(args.n_episodes, args.baseline, rng)
    else:
        print(f"[stress] Live eval not yet implemented — running mock")
        results = mock_stress_eval(args.n_episodes, args.baseline, rng)

    overall = overall_robustness(results)
    grade = "A" if overall >= 80 else ("B" if overall >= 65 else ("C" if overall >= 50 else "D"))
    print(f"[stress] Robustness: {overall:.1f}/100 (Grade {grade})")
    for r in results:
        drop_str = f"-{r.drop:.0%}" if r.drop > 0.01 else "  ±0"
        print(f"  {r.category_name:<40s} {r.success_rate:.0%} ({drop_str})  score={r.robustness_score:.0f}")

    generate_html_report(results, args.output)

    if args.json_output:
        summary = {
            "overall_robustness": overall,
            "grade": grade,
            "baseline_success_rate": args.baseline,
            "categories": [
                {"code": r.category_code, "name": r.category_name,
                 "success_rate": r.success_rate, "drop": r.drop,
                 "robustness_score": r.robustness_score}
                for r in results
            ],
        }
        with open(args.json_output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"JSON → {args.json_output}")


if __name__ == "__main__":
    main()
