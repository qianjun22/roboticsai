#!/usr/bin/env python3
"""
roi_calculator.py — ROI / business case calculator for OCI Robot Cloud prospects (port 8042).

Helps prospective customers understand the financial case for training on OCI vs alternatives.
Inputs: robot type, task, # of demos, current success rate.
Outputs: cost comparison, projected ROI, payback period, production value at scale.

Usage:
    python src/api/roi_calculator.py --port 8042 --mock
    # → http://localhost:8042
"""

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

try:
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Pricing constants ─────────────────────────────────────────────────────────

OCI_A100_HOURLY   = 4.20      # per GPU-hour
AWS_P4D_HOURLY    = 40.48     # per GPU-hour
DGX_CLOUD_HOURLY  = 19.50     # per GPU-hour
LAMBDA_HOURLY     = 8.00
ON_PREM_CAPEX     = 300_000   # $300k DGX H100 amortized over 3 years → ~$100k/yr
ON_PREM_HOURLY    = ON_PREM_CAPEX / (3 * 365 * 24 * 0.6)  # 60% utilization

THROUGHPUT_IT_S   = 2.35      # OCI A100 measured
STEPS_PER_HOUR    = THROUGHPUT_IT_S * 3600

# ── ROI model ─────────────────────────────────────────────────────────────────

@dataclass
class ROIInputs:
    robot_type: str              # "franka" / "ur5e" / "xarm7" / "kinova" / "custom"
    task: str                    # "pick-and-lift" / "bin-picking" / "assembly" / "inspection"
    n_robots_in_fleet: int       # how many robots to deploy
    demos_available: int         # demos customer has
    current_success_rate: float  # current / baseline success rate (0-1)
    target_success_rate: float   # desired success rate
    robot_idle_cost_per_hour: float  # cost when robot fails ($)
    hours_per_day_operating: float   # robot operating hours/day
    business_days_per_year: int  # typically 250


@dataclass
class ROIOutputs:
    # Training cost comparison
    oci_training_cost:   float
    aws_training_cost:   float
    dgx_training_cost:   float
    lambda_training_cost: float
    savings_vs_aws:      float   # $
    savings_pct_vs_aws:  float   # %

    # Training config
    n_steps_recommended: int
    n_dagger_iters:      int
    gpu_hours_needed:    float
    expected_success_rate: float

    # Business impact
    failures_per_day_before: float
    failures_per_day_after:  float
    failure_reduction_pct:   float
    annual_cost_before:      float  # failures × idle cost × days
    annual_cost_after:       float
    annual_savings:          float
    payback_period_days:     float  # training_cost / daily_savings

    # Notes
    recommendation: str
    key_assumptions: list[str]


def compute_roi(inp: ROIInputs) -> ROIOutputs:
    # Training config recommendation
    if inp.current_success_rate < 0.10 and inp.target_success_rate <= 0.30:
        n_steps = 5000
        n_dagger = 3
        expected_sr = min(inp.target_success_rate, 0.65)
    elif inp.current_success_rate < 0.30:
        n_steps = 5000
        n_dagger = 5
        expected_sr = min(inp.target_success_rate, 0.70)
    else:
        n_steps = 3000
        n_dagger = 3
        expected_sr = min(inp.target_success_rate, 0.75)

    total_steps = n_steps * (1 + n_dagger * 0.6)
    gpu_hours = total_steps / STEPS_PER_HOUR

    oci_cost   = gpu_hours * OCI_A100_HOURLY
    aws_cost   = gpu_hours * AWS_P4D_HOURLY
    dgx_cost   = gpu_hours * DGX_CLOUD_HOURLY
    lambda_cost= gpu_hours * LAMBDA_HOURLY

    savings_vs_aws = aws_cost - oci_cost
    savings_pct    = savings_vs_aws / aws_cost * 100

    # Business impact
    cycles_per_day = inp.hours_per_day_operating * 3600 / 60  # assume 1 task/minute
    total_tasks_per_day = cycles_per_day * inp.n_robots_in_fleet

    failures_before = total_tasks_per_day * (1 - inp.current_success_rate)
    failures_after  = total_tasks_per_day * (1 - expected_sr)
    failure_reduction = (failures_before - failures_after) / max(failures_before, 1) * 100

    idle_time_per_failure_h = 5 / 60  # 5 min recovery per failure
    annual_cost_before = failures_before * inp.business_days_per_year * idle_time_per_failure_h * inp.robot_idle_cost_per_hour
    annual_cost_after  = failures_after  * inp.business_days_per_year * idle_time_per_failure_h * inp.robot_idle_cost_per_hour
    annual_savings = annual_cost_before - annual_cost_after

    daily_savings = annual_savings / inp.business_days_per_year
    payback_days  = oci_cost / max(daily_savings, 0.01)

    # Recommendation text
    if payback_days < 30:
        rec = f"Exceptional ROI: training pays back in {payback_days:.0f} days. Immediate action recommended."
    elif payback_days < 90:
        rec = f"Strong ROI: {payback_days:.0f}-day payback period. Start with 1-robot pilot to validate."
    elif payback_days < 365:
        rec = f"Solid ROI: {payback_days:.0f}-day payback. Consider starting with a subset of fleet."
    else:
        rec = f"Long payback ({payback_days:.0f} days). Revisit if robot fleet grows or task complexity increases."

    assumptions = [
        f"Training throughput: {THROUGHPUT_IT_S:.2f} it/s on OCI A100 (measured)",
        f"OCI price: ${OCI_A100_HOURLY:.2f}/GPU-hr vs AWS ${AWS_P4D_HOURLY:.2f}/GPU-hr",
        f"5-min recovery time per failed task",
        f"Expected success rate after training: {expected_sr:.0%} (conservative estimate)",
        f"Robot fleet: {inp.n_robots_in_fleet} × {inp.hours_per_day_operating:.0f}h/day × {inp.business_days_per_year} days/year",
    ]

    return ROIOutputs(
        oci_training_cost=round(oci_cost, 2),
        aws_training_cost=round(aws_cost, 2),
        dgx_training_cost=round(dgx_cost, 2),
        lambda_training_cost=round(lambda_cost, 2),
        savings_vs_aws=round(savings_vs_aws, 2),
        savings_pct_vs_aws=round(savings_pct, 1),
        n_steps_recommended=int(total_steps),
        n_dagger_iters=n_dagger,
        gpu_hours_needed=round(gpu_hours, 2),
        expected_success_rate=round(expected_sr, 3),
        failures_per_day_before=round(failures_before, 1),
        failures_per_day_after=round(failures_after, 1),
        failure_reduction_pct=round(failure_reduction, 1),
        annual_cost_before=round(annual_cost_before, 0),
        annual_cost_after=round(annual_cost_after, 0),
        annual_savings=round(annual_savings, 0),
        payback_period_days=round(payback_days, 1),
        recommendation=rec,
        key_assumptions=assumptions,
    )


# ── HTML rendering ─────────────────────────────────────────────────────────────

PRESET_SCENARIOS = [
    {"name": "Series A Warehouse (Franka fleet)", "robot_type": "franka", "task": "pick-and-lift",
     "n_robots": 5, "demos": 500, "current_sr": 0.05, "target_sr": 0.60, "idle_cost": 150, "hours": 16},
    {"name": "Manufacturing QC (UR5e)", "robot_type": "ur5e", "task": "inspection",
     "n_robots": 10, "demos": 1000, "current_sr": 0.0, "target_sr": 0.70, "idle_cost": 500, "hours": 20},
    {"name": "Logistics Startup (xArm7 pilot)", "robot_type": "xarm7", "task": "bin-picking",
     "n_robots": 1, "demos": 200, "current_sr": 0.10, "target_sr": 0.50, "idle_cost": 80, "hours": 8},
]


def render_calculator(result: Optional[ROIOutputs] = None,
                      inp: Optional[ROIInputs] = None) -> str:
    result_html = ""
    if result and inp:
        payback_color = "#22c55e" if result.payback_period_days < 90 else "#f59e0b" if result.payback_period_days < 365 else "#ef4444"
        assumptions_html = "".join(f"<li style='margin-bottom:4px'>{a}</li>" for a in result.key_assumptions)
        result_html = f"""
<div class="card" style="border:1px solid #22c55e22">
  <h2 style="color:#22c55e;font-size:16px;margin-top:0">ROI Analysis</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:8px">Training Cost Comparison</div>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:5px 8px;font-size:13px">OCI A100 (recommended)</td><td style="padding:5px 8px;font-weight:700;color:#22c55e">${result.oci_training_cost:.2f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px;color:#64748b">Lambda Labs</td><td style="padding:5px 8px;color:#64748b">${result.lambda_training_cost:.2f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px;color:#64748b">DGX Cloud</td><td style="padding:5px 8px;color:#64748b">${result.dgx_training_cost:.2f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px;color:#64748b">AWS p4d.24xlarge</td><td style="padding:5px 8px;color:#ef4444">${result.aws_training_cost:.2f}</td></tr>
      </table>
      <div style="margin-top:8px;background:#0f172a;border-radius:6px;padding:10px">
        <div style="color:#22c55e;font-weight:700;font-size:18px">{result.savings_pct_vs_aws:.0f}% cheaper than AWS</div>
        <div style="color:#64748b;font-size:12px">Save ${result.savings_vs_aws:.2f} on this training run</div>
      </div>
    </div>
    <div>
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:8px">Business Impact ({inp.n_robots_in_fleet} robots)</div>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:5px 8px;font-size:13px">Failures/day before</td><td style="padding:5px 8px;font-weight:700;color:#ef4444">{result.failures_per_day_before:.0f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px">Failures/day after</td><td style="padding:5px 8px;font-weight:700;color:#22c55e">{result.failures_per_day_after:.0f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px">Annual cost before</td><td style="padding:5px 8px;color:#ef4444">${result.annual_cost_before:,.0f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px">Annual cost after</td><td style="padding:5px 8px;color:#22c55e">${result.annual_cost_after:,.0f}</td></tr>
        <tr><td style="padding:5px 8px;font-size:13px;font-weight:600">Annual savings</td><td style="padding:5px 8px;font-weight:700;color:#22c55e;font-size:16px">${result.annual_savings:,.0f}</td></tr>
      </table>
    </div>
  </div>
  <div style="margin-top:12px;display:flex;align-items:center;gap:16px">
    <div style="background:#0f172a;border-radius:8px;padding:12px 20px">
      <div style="font-size:28px;font-weight:700;color:{payback_color}">{result.payback_period_days:.0f} days</div>
      <div style="font-size:11px;color:#64748b">Payback period</div>
    </div>
    <div style="flex:1;font-size:13px;color:#94a3b8">{result.recommendation}</div>
  </div>
  <div style="margin-top:12px;font-size:12px;color:#475569">
    <div style="margin-bottom:4px;color:#64748b">Key assumptions:</div>
    <ul style="margin:0;padding-left:16px">{assumptions_html}</ul>
  </div>
</div>"""

    preset_opts = "".join(
        f'<option value="{i}">{p["name"]}</option>'
        for i, p in enumerate(PRESET_SCENARIOS)
    )
    preset_js = json.dumps([{
        "n_robots": p["n_robots"], "demos": p["demos"], "current_sr": p["current_sr"],
        "target_sr": p["target_sr"], "idle_cost": p["idle_cost"], "hours": p["hours"],
        "robot_type": p["robot_type"], "task": p["task"]
    } for p in PRESET_SCENARIOS])

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>OCI Robot Cloud — ROI Calculator</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:28px;max-width:860px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}}
  label{{display:block;font-size:12px;color:#94a3b8;margin-bottom:3px;text-transform:uppercase}}
  input,select{{background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:7px 10px;border-radius:6px;font-size:13px;width:100%;box-sizing:border-box}}
  button{{background:#3b82f6;color:white;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;margin-top:4px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}
</style>
</head>
<body>
<h1>OCI Robot Cloud — ROI Calculator</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 20px">Estimate training cost + business impact of improving robot success rate</p>

<div class="card">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
    <label style="margin:0">Load preset:</label>
    <select id="preset" onchange="loadPreset()" style="width:auto;flex:1">{preset_opts}</select>
  </div>

  <form method="POST" action="/calculate">
    <div class="grid">
      <div><label>Robot Type</label>
        <select name="robot_type" id="rt">
          <option value="franka">Franka Panda</option>
          <option value="ur5e">UR5e</option>
          <option value="xarm7">xArm7</option>
          <option value="kinova">Kinova Gen3</option>
          <option value="custom">Custom</option>
        </select></div>
      <div><label>Task</label>
        <select name="task">
          <option>pick-and-lift</option><option>bin-picking</option>
          <option>assembly</option><option>inspection</option>
        </select></div>
      <div><label>Robots in Fleet</label><input name="n_robots" id="nr" type="number" value="5" min="1"></div>
    </div>
    <div class="grid" style="margin-top:12px">
      <div><label>Demos Available</label><input name="demos" id="dm" type="number" value="500"></div>
      <div><label>Current Success Rate (%)</label><input name="current_sr" id="cs" type="number" value="5" min="0" max="100"></div>
      <div><label>Target Success Rate (%)</label><input name="target_sr" id="ts" type="number" value="65" min="0" max="100"></div>
    </div>
    <div class="grid" style="margin-top:12px">
      <div><label>Robot Idle Cost ($/hr)</label><input name="idle_cost" id="ic" type="number" value="150"></div>
      <div><label>Operating Hours/Day</label><input name="hours" id="hr" type="number" value="16" min="1" max="24"></div>
      <div><label>Business Days/Year</label><input name="bdays" type="number" value="250"></div>
    </div>
    <button type="submit" style="margin-top:16px">Calculate ROI</button>
  </form>
</div>

{result_html}

<script>
const presets = {preset_js};
function loadPreset() {{
  const p = presets[document.getElementById('preset').value];
  document.getElementById('nr').value = p.n_robots;
  document.getElementById('dm').value = p.demos;
  document.getElementById('cs').value = Math.round(p.current_sr * 100);
  document.getElementById('ts').value = Math.round(p.target_sr * 100);
  document.getElementById('ic').value = p.idle_cost;
  document.getElementById('hr').value = p.hours;
  document.getElementById('rt').value = p.robot_type;
}}
</script>
</body>
</html>"""


# ── FastAPI app ────────────────────────────────────────────────────────────────

def create_app() -> "FastAPI":
    app = FastAPI(title="ROI Calculator", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return render_calculator()

    @app.post("/calculate", response_class=HTMLResponse)
    async def calculate(
        robot_type: str = Form("franka"),
        task: str = Form("pick-and-lift"),
        n_robots: int = Form(5),
        demos: int = Form(500),
        current_sr: float = Form(5.0),
        target_sr: float = Form(65.0),
        idle_cost: float = Form(150.0),
        hours: float = Form(16.0),
        bdays: int = Form(250),
    ):
        inp = ROIInputs(
            robot_type=robot_type, task=task,
            n_robots_in_fleet=n_robots, demos_available=demos,
            current_success_rate=current_sr / 100,
            target_success_rate=target_sr / 100,
            robot_idle_cost_per_hour=idle_cost,
            hours_per_day_operating=hours,
            business_days_per_year=bdays,
        )
        result = compute_roi(inp)
        return render_calculator(result, inp)

    @app.get("/api/calculate")
    async def api_calculate(
        robot_type: str = "franka", task: str = "pick-and-lift",
        n_robots: int = 5, demos: int = 500,
        current_sr: float = 5.0, target_sr: float = 65.0,
        idle_cost: float = 150.0, hours: float = 16.0, bdays: int = 250,
    ):
        inp = ROIInputs(
            robot_type=robot_type, task=task,
            n_robots_in_fleet=n_robots, demos_available=demos,
            current_success_rate=current_sr / 100,
            target_success_rate=target_sr / 100,
            robot_idle_cost_per_hour=idle_cost,
            hours_per_day_operating=hours,
            business_days_per_year=bdays,
        )
        result = compute_roi(inp)
        return result.__dict__

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "roi_calculator", "port": 8042}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ROI calculator (port 8042)")
    parser.add_argument("--port", type=int, default=8042)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--cli",  action="store_true", help="Run CLI demo")
    args = parser.parse_args()

    if args.cli:
        for preset in PRESET_SCENARIOS:
            inp = ROIInputs(
                robot_type=preset["robot_type"], task=preset["task"],
                n_robots_in_fleet=preset["n_robots"], demos_available=preset["demos"],
                current_success_rate=preset["current_sr"],
                target_success_rate=preset["target_sr"],
                robot_idle_cost_per_hour=preset["idle_cost"],
                hours_per_day_operating=preset["hours"],
                business_days_per_year=250,
            )
            result = compute_roi(inp)
            print(f"\n{preset['name']}")
            print(f"  OCI cost: ${result.oci_training_cost:.2f}  (vs AWS ${result.aws_training_cost:.2f})")
            print(f"  Annual savings: ${result.annual_savings:,.0f}")
            print(f"  Payback: {result.payback_period_days:.0f} days")
    else:
        if not HAS_FASTAPI:
            print("pip install fastapi uvicorn")
            exit(1)
        app = create_app()
        print(f"ROI Calculator → http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
