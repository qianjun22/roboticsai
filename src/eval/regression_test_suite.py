#!/usr/bin/env python3
"""
regression_test_suite.py — Automated regression tests against golden checkpoints.

Runs a suite of deterministic episodes against a reference checkpoint and a candidate
checkpoint; fails if candidate regresses more than a configurable threshold.

Usage:
    python src/eval/regression_test_suite.py \
        --golden-url http://localhost:8002 \
        --candidate-url http://localhost:8003 \
        --output /tmp/regression_report.html

    # Mock mode (no GPU required):
    python src/eval/regression_test_suite.py --mock --output /tmp/regression_report.html
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

REGRESSION_THRESHOLD = 0.10   # Fail if success rate drops by more than 10pp
N_REGRESSION_EPISODES = 20
SEED = 2026                    # Fixed seed → deterministic episode set

# Test categories
TEST_CATEGORIES = {
    "center_cube":   {"cube_x_offset": 0.0,  "cube_y_offset": 0.0,  "weight": 0.40},
    "left_offset":   {"cube_x_offset": -0.08,"cube_y_offset": 0.0,  "weight": 0.20},
    "right_offset":  {"cube_x_offset": +0.08,"cube_y_offset": 0.0,  "weight": 0.20},
    "near_offset":   {"cube_x_offset": 0.0,  "cube_y_offset": -0.06,"weight": 0.10},
    "far_offset":    {"cube_x_offset": 0.0,  "cube_y_offset": +0.06,"weight": 0.10},
}

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class EpisodeResult:
    episode_id: int
    category: str
    success: bool
    cube_z_final: float
    latency_ms: float
    steps: int

@dataclass
class CheckpointReport:
    name: str
    url: str
    results: list[EpisodeResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if not self.results: return 0.0
        return sum(r.success for r in self.results) / len(self.results)

    @property
    def per_category(self) -> dict:
        cats: dict = {}
        for r in self.results:
            cats.setdefault(r.category, []).append(r.success)
        return {k: sum(v)/len(v) for k, v in cats.items()}

    @property
    def avg_latency(self) -> float:
        if not self.results: return 0.0
        return statistics.mean(r.latency_ms for r in self.results)

    @property
    def p95_latency(self) -> float:
        if not self.results: return 0.0
        lats = sorted(r.latency_ms for r in self.results)
        idx = int(0.95 * len(lats))
        return lats[min(idx, len(lats)-1)]


# ── Mock eval ─────────────────────────────────────────────────────────────────

def _mock_episode(episode_id: int, category: str, success_base: float, rng: random.Random) -> EpisodeResult:
    """Simulate a single episode with realistic noise."""
    offset = TEST_CATEGORIES[category]
    # Harder categories have lower success
    difficulty_penalty = abs(offset["cube_x_offset"]) * 2 + abs(offset["cube_y_offset"]) * 2
    p_success = max(0.0, min(1.0, success_base - difficulty_penalty))
    success = rng.random() < p_success
    cube_z = 0.78 + rng.gauss(0, 0.02) if success else 0.705 + rng.gauss(0, 0.01)
    latency = rng.gauss(226, 12)
    return EpisodeResult(
        episode_id=episode_id,
        category=category,
        success=success,
        cube_z_final=cube_z,
        latency_ms=max(150, latency),
        steps=50 + rng.randint(0, 20),
    )


def mock_eval(name: str, url: str, success_base: float, n_episodes: int, seed: int) -> CheckpointReport:
    rng = random.Random(seed)
    report = CheckpointReport(name=name, url=url)
    categories = list(TEST_CATEGORIES.keys())
    eps_per_cat = n_episodes // len(categories)
    episode_id = 0
    for cat in categories:
        count = eps_per_cat + (1 if episode_id < n_episodes % len(categories) else 0)
        for _ in range(max(count, 1)):
            if episode_id >= n_episodes:
                break
            report.results.append(_mock_episode(episode_id, cat, success_base, rng))
            episode_id += 1
    return report


# ── Live eval ─────────────────────────────────────────────────────────────────

def live_eval(name: str, url: str, n_episodes: int, seed: int) -> CheckpointReport:
    """Run regression episodes against a live GR00T server."""
    try:
        import requests
    except ImportError:
        raise RuntimeError("pip install requests")

    report = CheckpointReport(name=name, url=url)
    rng = random.Random(seed)
    import numpy as np

    TABLE_Z = 0.70
    LIFT_THRESHOLD = 0.78

    categories = list(TEST_CATEGORIES.keys())
    eps_per_cat = n_episodes // len(categories)

    episode_id = 0
    for cat in categories:
        offset = TEST_CATEGORIES[cat]
        for _ in range(eps_per_cat):
            joint_pos = np.array([0.0, -0.3, 0.0, -2.0, 0.0, 1.9, 0.8], dtype=np.float32)
            gripper = np.array([0.04, 0.04], dtype=np.float32)
            cube_x = 0.5 + offset["cube_x_offset"] + rng.gauss(0, 0.005)
            cube_y = 0.0 + offset["cube_y_offset"] + rng.gauss(0, 0.005)
            cube_z = TABLE_Z

            latencies = []
            for step in range(50):
                obs = {
                    "observation.state": joint_pos.tolist() + gripper.tolist(),
                    "observation.images.primary": [[[[128,128,128]] * 256] * 256],
                    "observation.images.wrist":   [[[[100,100,100]] * 256] * 256],
                }
                t0 = time.time()
                try:
                    resp = requests.post(f"{url}/act", json=obs, timeout=5.0)
                    resp.raise_for_status()
                    data = resp.json()
                    latencies.append((time.time() - t0) * 1000)
                    actions = data.get("actions", [[0.0]*9])[0]
                    joint_pos = np.array(actions[:7], dtype=np.float32)
                    gripper = np.array(actions[7:], dtype=np.float32)
                    cube_z = min(cube_z + max(0, (joint_pos[2] - 0.5) * 0.01), 0.85)
                except Exception:
                    latencies.append(5000)
                    break

            avg_lat = statistics.mean(latencies) if latencies else 5000
            success = cube_z >= LIFT_THRESHOLD
            report.results.append(EpisodeResult(
                episode_id=episode_id,
                category=cat,
                success=success,
                cube_z_final=cube_z,
                latency_ms=avg_lat,
                steps=step+1,
            ))
            episode_id += 1

    return report


# ── Regression check ──────────────────────────────────────────────────────────

@dataclass
class RegressionResult:
    passed: bool
    golden_rate: float
    candidate_rate: float
    delta: float           # candidate - golden (negative = regression)
    per_category_delta: dict
    verdict: str


def check_regression(golden: CheckpointReport, candidate: CheckpointReport,
                     threshold: float = REGRESSION_THRESHOLD) -> RegressionResult:
    delta = candidate.success_rate - golden.success_rate
    passed = delta >= -threshold

    per_cat = {}
    g_cats = golden.per_category
    c_cats = candidate.per_category
    for cat in TEST_CATEGORIES:
        g = g_cats.get(cat, 0.0)
        c = c_cats.get(cat, 0.0)
        per_cat[cat] = {"golden": g, "candidate": c, "delta": c - g}

    if passed:
        if delta >= 0:
            verdict = f"PASS (+{delta:.1%} improvement)"
        else:
            verdict = f"PASS (regression {delta:.1%} within {-threshold:.0%} threshold)"
    else:
        verdict = f"FAIL (regression {delta:.1%} exceeds {-threshold:.0%} threshold)"

    return RegressionResult(
        passed=passed,
        golden_rate=golden.success_rate,
        candidate_rate=candidate.success_rate,
        delta=delta,
        per_category_delta=per_cat,
        verdict=verdict,
    )


# ── HTML report ───────────────────────────────────────────────────────────────

def _bar(val: float, color: str = "#3b82f6", width: int = 120) -> str:
    px = int(val * width)
    return f'<div style="display:inline-block;background:{color};height:12px;width:{px}px;border-radius:3px;vertical-align:middle"></div> {val:.1%}'


def generate_html_report(golden: CheckpointReport, candidate: CheckpointReport,
                         reg: RegressionResult, output_path: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_color = "#22c55e" if reg.passed else "#ef4444"
    status_bg    = "#052e16" if reg.passed else "#450a0a"

    cats_rows = ""
    for cat, d in reg.per_category_delta.items():
        delta_color = "#22c55e" if d["delta"] >= -0.05 else "#ef4444"
        cats_rows += f"""
        <tr>
          <td style="padding:6px 12px;font-weight:600">{cat.replace('_',' ').title()}</td>
          <td style="padding:6px 12px">{_bar(d['golden'],'#6366f1')}</td>
          <td style="padding:6px 12px">{_bar(d['candidate'],'#3b82f6')}</td>
          <td style="padding:6px 12px;color:{delta_color};font-weight:600">{d['delta']:+.1%}</td>
        </tr>"""

    # Episode dots for each checkpoint
    def dot_grid(report: CheckpointReport) -> str:
        html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px">'
        for r in report.results:
            color = "#22c55e" if r.success else "#ef4444"
            html += f'<div title="{r.category} ep{r.episode_id}" style="width:14px;height:14px;background:{color};border-radius:3px"></div>'
        html += '</div>'
        return html

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GR00T Regression Report — {now}</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  h2{{color:#94a3b8;font-size:14px;font-weight:400;margin:0 0 24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  .verdict{{font-size:20px;font-weight:700;padding:16px 24px;border-radius:8px;background:{status_bg};color:{status_color};border:1px solid {status_color}}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:12px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
  td{{border-bottom:1px solid #1e293b;font-size:13px}}
  .metric{{display:inline-block;background:#0f172a;border-radius:6px;padding:12px 20px;margin:4px;min-width:120px;text-align:center}}
  .metric-val{{font-size:28px;font-weight:700;color:#f8fafc}}
  .metric-label{{font-size:11px;color:#64748b;margin-top:4px}}
</style>
</head>
<body>
<h1>GR00T Regression Test Suite</h1>
<h2>Generated {now} · {N_REGRESSION_EPISODES} episodes · threshold ±{REGRESSION_THRESHOLD:.0%}</h2>

<div class="card">
  <div class="verdict">{reg.verdict}</div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Overall Success Rate</h3>
  <div>
    <div class="metric">
      <div class="metric-val" style="color:#6366f1">{golden.success_rate:.1%}</div>
      <div class="metric-label">Golden ({golden.name})</div>
    </div>
    <div class="metric">
      <div class="metric-val" style="color:#3b82f6">{candidate.success_rate:.1%}</div>
      <div class="metric-label">Candidate ({candidate.name})</div>
    </div>
    <div class="metric">
      <div class="metric-val" style="color:{status_color}">{reg.delta:+.1%}</div>
      <div class="metric-label">Delta</div>
    </div>
    <div class="metric">
      <div class="metric-val" style="color:#94a3b8">{golden.avg_latency:.0f}ms</div>
      <div class="metric-label">Golden p50 lat</div>
    </div>
    <div class="metric">
      <div class="metric-val" style="color:#94a3b8">{candidate.avg_latency:.0f}ms</div>
      <div class="metric-label">Candidate p50 lat</div>
    </div>
  </div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Per-Category Breakdown</h3>
  <table>
    <tr>
      <th>Category</th>
      <th>Golden (purple)</th>
      <th>Candidate (blue)</th>
      <th>Δ</th>
    </tr>
    {cats_rows}
  </table>
</div>

<div class="card" style="display:flex;gap:24px">
  <div style="flex:1">
    <div style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-bottom:8px">Golden episodes</div>
    {dot_grid(golden)}
  </div>
  <div style="flex:1">
    <div style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-bottom:8px">Candidate episodes</div>
    {dot_grid(candidate)}
  </div>
</div>

<div style="color:#475569;font-size:11px;margin-top:16px">
  Golden: {golden.url} · Candidate: {candidate.url} · Seed: {SEED}
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report → {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GR00T regression test suite")
    parser.add_argument("--golden-url",   default="http://localhost:8002")
    parser.add_argument("--candidate-url",default="http://localhost:8003")
    parser.add_argument("--golden-name",  default="BC-baseline")
    parser.add_argument("--candidate-name", default="DAgger-candidate")
    parser.add_argument("--n-episodes",   type=int, default=N_REGRESSION_EPISODES)
    parser.add_argument("--threshold",    type=float, default=REGRESSION_THRESHOLD)
    parser.add_argument("--output",       default="/tmp/regression_report.html")
    parser.add_argument("--json-output",  default="")
    parser.add_argument("--mock",         action="store_true")
    # Mock success rates
    parser.add_argument("--golden-success",   type=float, default=0.05)
    parser.add_argument("--candidate-success",type=float, default=0.25)
    args = parser.parse_args()

    print(f"[regression] Running {args.n_episodes}-episode regression test")
    print(f"[regression] Golden:    {args.golden_url}")
    print(f"[regression] Candidate: {args.candidate_url}")
    print(f"[regression] Threshold: ±{args.threshold:.0%}")

    if args.mock:
        golden    = mock_eval(args.golden_name,    args.golden_url,    args.golden_success,    args.n_episodes, SEED)
        candidate = mock_eval(args.candidate_name, args.candidate_url, args.candidate_success, args.n_episodes, SEED+1)
    else:
        golden    = live_eval(args.golden_name,    args.golden_url,    args.n_episodes, SEED)
        candidate = live_eval(args.candidate_name, args.candidate_url, args.n_episodes, SEED+1)

    reg = check_regression(golden, candidate, args.threshold)
    print(f"[regression] {reg.verdict}")
    print(f"[regression] Golden: {reg.golden_rate:.1%}  Candidate: {reg.candidate_rate:.1%}  Δ={reg.delta:+.1%}")

    generate_html_report(golden, candidate, reg, args.output)

    if args.json_output:
        summary = {
            "passed": reg.passed,
            "verdict": reg.verdict,
            "golden_success_rate": reg.golden_rate,
            "candidate_success_rate": reg.candidate_rate,
            "delta": reg.delta,
            "threshold": args.threshold,
            "n_episodes": args.n_episodes,
            "per_category": reg.per_category_delta,
            "golden_latency_ms": golden.avg_latency,
            "candidate_latency_ms": candidate.avg_latency,
        }
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"JSON   → {args.json_output}")

    import sys
    sys.exit(0 if reg.passed else 1)


if __name__ == "__main__":
    main()
