#!/usr/bin/env python3
"""
policy_stress_benchmarker.py — FastAPI port 8097
Stress benchmarks GR00T N1.6 policy under adversarial and edge-case conditions.
Measures robustness across 10 stress categories.
Oracle Confidential
"""

import json
import math
import random
import datetime
from typing import Dict, List, Optional

BASELINE_SR = 0.71
BASELINE_MODEL = "dagger_run9_v2.2"
TOTAL_TRIALS = 100

STRESS_CATEGORIES = {
    "camera_noise": {"label": "Camera Noise", "description": "Gaussian noise sigma=0.05 on input images",
        "sr": 0.62, "defense": "Data augmentation: add Gaussian noise during fine-tuning (sigma=0.02-0.08 schedule)", "priority": 2},
    "joint_perturbation": {"label": "Joint Perturbation", "description": "±5% random noise on all joint states",
        "sr": 0.67, "defense": "Proprioception calibration: tighten encoder tolerances; add Kalman state filter", "priority": 3},
    "latency_injection": {"label": "Latency Injection", "description": "Artificial 50ms added latency on inference",
        "sr": 0.69, "defense": "Edge caching: deploy policy on Jetson NX for local inference fallback", "priority": 4},
    "occlusion_40pct": {"label": "40% Occlusion", "description": "40% of image pixels randomly masked (black)",
        "sr": 0.44, "defense": "Multi-view redundancy: add second camera; train with random erasing augmentation", "priority": 1},
    "lighting_dark": {"label": "Lighting Dark", "description": "Image brightness reduced 60% (gamma=0.4)",
        "sr": 0.51, "defense": "Photometric augmentation: fine-tune with brightness/contrast jitter; IR supplement", "priority": 1},
    "cube_edge": {"label": "Cube Edge Placement", "description": "Cube at workspace boundary (challenging grasp geometry)",
        "sr": 0.58, "defense": "Curriculum SDG: increase edge-placement demos to >=20% of fine-tune dataset", "priority": 2},
    "rapid_succession": {"label": "Rapid Succession", "description": "3 tasks in 10s — no reset time between episodes",
        "sr": 0.61, "defense": "Episode timeout tuning: reduce reset threshold; add fast-reset trajectory to SDG", "priority": 2},
    "temperature_scaling": {"label": "Temperature Scaling", "description": "Action logit temperature x2.0 (increases stochasticity)",
        "sr": 0.55, "defense": "Temperature calibration: sweep T in [0.5, 2.0] on held-out eval; lock optimal T", "priority": 3},
    "adversarial_obs": {"label": "Adversarial Observation", "description": "FGSM-like gradient perturbation on image observation",
        "sr": 0.38, "defense": "Adversarial training: include FGSM examples (eps=0.01) in 10% of fine-tune batches", "priority": 1},
    "combined_attack": {"label": "Combined Attack", "description": "Simultaneous: camera_noise + joint_perturbation + latency_injection",
        "sr": 0.29, "defense": "Defense-in-depth: pipeline all three defenses; add anomaly detector for corrupt obs", "priority": 1},
}

GRADE_THRESHOLDS = {"A": 0.80, "B": 0.60, "C": 0.40}


def robustness_grade(sr: float, baseline: float = BASELINE_SR) -> str:
    retained = sr / baseline if baseline > 0 else 0
    if retained >= GRADE_THRESHOLDS["A"]: return "A"
    if retained >= GRADE_THRESHOLDS["B"]: return "B"
    if retained >= GRADE_THRESHOLDS["C"]: return "C"
    return "D"


def grade_color(grade: str) -> str:
    return {"A": "#22c55e", "B": "#84cc16", "C": "#f59e0b", "D": "#ef4444"}.get(grade, "#e2e8f0")


def simulate_trial_outcomes(category: str) -> Dict:
    target_sr = STRESS_CATEGORIES[category]["sr"]
    rng = random.Random(hash(category + "trials") & 0xFFFFFFFF)
    outcomes = [1 if rng.random() < target_sr else 0 for _ in range(TOTAL_TRIALS)]
    successes = sum(outcomes)
    measured_sr = successes / TOTAL_TRIALS
    failures = [i + 1 for i, o in enumerate(outcomes) if o == 0][:5]
    return {
        "category": category, "trials": TOTAL_TRIALS, "successes": successes,
        "failures_total": TOTAL_TRIALS - successes, "measured_sr": round(measured_sr, 4),
        "baseline_sr": BASELINE_SR, "retained_pct": round(measured_sr / BASELINE_SR * 100, 1),
        "grade": robustness_grade(measured_sr), "example_failure_trials": failures,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }


def full_benchmark() -> Dict:
    results = {cat: simulate_trial_outcomes(cat) for cat in STRESS_CATEGORIES}
    overall_sr = sum(r["measured_sr"] for r in results.values()) / len(results)
    return {"model": BASELINE_MODEL, "baseline_sr": BASELINE_SR,
            "overall_mean_sr": round(overall_sr, 4), "overall_grade": robustness_grade(overall_sr),
            "categories": results, "generated_at": datetime.datetime.utcnow().isoformat() + "Z"}


def radar_chart_svg(results: Dict) -> str:
    cats = list(STRESS_CATEGORIES.keys())
    n = len(cats)
    cx, cy, r_max = 260, 260, 200
    step = r_max / 5

    def polar(angle_deg, radius):
        rad = math.radians(angle_deg - 90)
        return cx + radius * math.cos(rad), cy + radius * math.sin(rad)

    rings = ""
    for i in range(1, 6):
        pts = " ".join(f"{polar(j*360/n, i*step)[0]:.1f},{polar(j*360/n, i*step)[1]:.1f}" for j in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
        lx, ly = polar(0, i * step)
        rings += f'<text x="{lx+4:.1f}" y="{ly:.1f}" fill="#475569" font-size="9">{i*20}%</text>'
    axes = ""
    labels = ""
    for i, cat in enumerate(cats):
        angle = i * 360 / n
        ex, ey = polar(angle, r_max)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        lx, ly = polar(angle, r_max + 24)
        short = STRESS_CATEGORIES[cat]["label"].split()[0]
        labels += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{short}</text>'
    base_pts = " ".join(f"{polar(i*360/n, BASELINE_SR*r_max)[0]:.1f},{polar(i*360/n, BASELINE_SR*r_max)[1]:.1f}" for i in range(n))
    stress_vals = [results["categories"][cat]["measured_sr"] for cat in cats]
    stress_pts = " ".join(f"{polar(i*360/n, stress_vals[i]*r_max)[0]:.1f},{polar(i*360/n, stress_vals[i]*r_max)[1]:.1f}" for i in range(n))
    dots = ""
    for i, cat in enumerate(cats):
        v = results["categories"][cat]["measured_sr"]
        px, py = polar(i * 360 / n, v * r_max)
        g = grade_color(results["categories"][cat]["grade"])
        dots += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{g}" stroke="#0f172a" stroke-width="1.5"/>'
    return (f'<svg viewBox="0 0 520 520" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:520px;background:#0f172a;border-radius:12px">'
            f'{rings}{axes}'
            f'<polygon points="{base_pts}" fill="rgba(56,189,248,0.08)" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3"/>'
            f'<polygon points="{stress_pts}" fill="rgba(199,70,52,0.15)" stroke="#C74634" stroke-width="2"/>'
            f'{dots}{labels}'
            f'<text x="260" y="30" fill="#94a3b8" font-size="11" text-anchor="middle">Stress SR Radar — GR00T N1.6</text>'
            f'<rect x="30" y="470" width="12" height="12" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
            f'<text x="48" y="481" fill="#94a3b8" font-size="10">Baseline 71%</text>'
            f'<rect x="130" y="470" width="12" height="12" fill="rgba(199,70,52,0.3)" stroke="#C74634" stroke-width="1.5"/>'
            f'<text x="148" y="481" fill="#94a3b8" font-size="10">Stress SR</text></svg>')


def build_report() -> str:
    data = full_benchmark()
    results = data["categories"]
    table_rows = ""
    priority_items = []
    for cat, info in STRESS_CATEGORIES.items():
        r = results[cat]
        grade = r["grade"]
        gc = grade_color(grade)
        table_rows += (f'<tr><td style="padding:10px 12px;color:#e2e8f0">{info["label"]}</td>'
                       f'<td style="padding:10px 12px;color:#94a3b8;font-size:12px">{info["description"]}</td>'
                       f'<td style="padding:10px 12px;text-align:center;color:#38bdf8">{r["measured_sr"]*100:.1f}%</td>'
                       f'<td style="padding:10px 12px;text-align:center;color:#94a3b8">{r["retained_pct"]}%</td>'
                       f'<td style="padding:10px 12px;text-align:center"><span style="color:{gc};font-weight:700;font-size:15px">{grade}</span></td>'
                       f'<td style="padding:10px 12px;color:#64748b;font-size:12px">{info["defense"]}</td></tr>')
        if info["priority"] == 1:
            priority_items.append((cat, info, r))
    priority_html = ""
    for i, (cat, info, r) in enumerate(sorted(priority_items, key=lambda x: x[2]["measured_sr"]), 1):
        priority_html += (f'<div style="background:#1e293b;border-left:4px solid #C74634;padding:12px 16px;margin:8px 0;border-radius:4px">'
                          f'<b style="color:#C74634">P{i} — {info["label"]}</b>'
                          f'<span style="color:#94a3b8;font-size:12px;margin-left:10px">SR: {r["measured_sr"]*100:.0f}% | Grade: {r["grade"]}</span>'
                          f'<p style="color:#cbd5e1;font-size:13px;margin:6px 0 0">{info["defense"]}</p></div>')
    radar = radar_chart_svg(data)
    overall_gc = grade_color(data["overall_grade"])
    ts = data["generated_at"]
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Policy Stress Benchmarker</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}} h2{{color:#38bdf8;font-size:16px;margin:24px 0 10px}}
table{{width:100%;border-collapse:collapse}} thead tr{{background:#1e293b;border-bottom:2px solid #334155}}
tbody tr:nth-child(even){{background:#0d1b2a}} tbody tr:hover{{background:#1e293b}}
th{{padding:10px 12px;text-align:left;color:#64748b;font-size:12px;font-weight:600}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:40px;border-top:1px solid #1e293b;padding-top:12px}}
.stat-box{{background:#1e293b;border-radius:10px;padding:16px 24px;display:inline-block;margin-right:16px;margin-bottom:12px}}</style></head>
<body><h1>OCI Robot Cloud — Policy Stress Benchmarker</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 20px">Port 8097 | Model: <b style="color:#e2e8f0">{BASELINE_MODEL}</b> | Generated: {ts}</p>
<div>
  <div class="stat-box"><div style="color:#64748b;font-size:12px">Baseline SR</div>
    <div style="color:#38bdf8;font-size:28px;font-weight:700">{BASELINE_SR*100:.0f}%</div></div>
  <div class="stat-box"><div style="color:#64748b;font-size:12px">Mean Stress SR</div>
    <div style="color:#C74634;font-size:28px;font-weight:700">{data["overall_mean_sr"]*100:.1f}%</div></div>
  <div class="stat-box"><div style="color:#64748b;font-size:12px">Overall Grade</div>
    <div style="color:{overall_gc};font-size:28px;font-weight:700">{data["overall_grade"]}</div></div>
  <div class="stat-box"><div style="color:#64748b;font-size:12px">Categories Tested</div>
    <div style="color:#e2e8f0;font-size:28px;font-weight:700">10</div></div>
</div>
<h2>Radar Chart — Stress SR vs Baseline</h2>
<div style="max-width:540px">{radar}</div>
<h2>Stress Test Results</h2>
<div style="background:#0d1b2a;border-radius:10px;overflow:hidden">
<table><thead><tr><th>Category</th><th>Stress Condition</th><th>SR</th><th>Retained</th><th>Grade</th><th>Defense Recommendation</th></tr></thead>
<tbody>{table_rows}</tbody></table></div>
<h2>Grading Scale</h2>
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px">
  <div style="background:#1e293b;border-radius:8px;padding:10px 18px"><span style="color:#22c55e;font-weight:700">A</span><span style="color:#94a3b8;font-size:13px;margin-left:8px">>=80% SR retained</span></div>
  <div style="background:#1e293b;border-radius:8px;padding:10px 18px"><span style="color:#84cc16;font-weight:700">B</span><span style="color:#94a3b8;font-size:13px;margin-left:8px">60-80% retained</span></div>
  <div style="background:#1e293b;border-radius:8px;padding:10px 18px"><span style="color:#f59e0b;font-weight:700">C</span><span style="color:#94a3b8;font-size:13px;margin-left:8px">40-60% retained</span></div>
  <div style="background:#1e293b;border-radius:8px;padding:10px 18px"><span style="color:#ef4444;font-weight:700">D</span><span style="color:#94a3b8;font-size:13px;margin-left:8px">&lt;40% retained</span></div>
</div>
<h2>Priority Hardening Plan</h2>{priority_html}
<div class="footer">Oracle Confidential — OCI Robot Cloud Evaluation | policy_stress_benchmarker.py | Port 8097</div>
</body></html>'''


try:
    from fastapi import FastAPI, HTTPException, Response
    import uvicorn
    app = FastAPI(title="OCI Policy Stress Benchmarker", version="1.0.0")

    @app.get("/", response_class=Response)
    def report(): return Response(content=build_report(), media_type="text/html")

    @app.get("/results")
    def results(): return full_benchmark()

    @app.get("/results/{category}")
    def category_result(category: str):
        if category not in STRESS_CATEGORIES:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
        r = simulate_trial_outcomes(category)
        r["category_info"] = STRESS_CATEGORIES[category]
        return r

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    app = None


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn
        print("Starting OCI Policy Stress Benchmarker on http://0.0.0.0:8097")
        uvicorn.run(app, host="0.0.0.0", port=8097, log_level="info")
    else:
        print("FastAPI not available — running CLI benchmark report\n")
        data = full_benchmark()
        print(f"Model: {data['model']}")
        print(f"Baseline SR: {data['baseline_sr']*100:.0f}%")
        print(f"Mean Stress SR: {data['overall_mean_sr']*100:.1f}%")
        print(f"Overall Grade: {data['overall_grade']}\n")
        for cat, r in data["categories"].items():
            label = STRESS_CATEGORIES[cat]["label"]
            print(f"{label:<22} {r['measured_sr']*100:>5.1f}%  retained {r['retained_pct']:>5.1f}%  grade {r['grade']}")
        out = "/tmp/policy_stress_report.html"
        with open(out, "w") as f: f.write(build_report())
        print(f"\nHTML report saved to {out}")
