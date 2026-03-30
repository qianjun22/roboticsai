#!/usr/bin/env python3
"""
experiment_planner.py — Experiment planning portal for OCI Robot Cloud.

Helps design partners plan fine-tuning experiments: given a robot type and
goal success rate, recommends the optimal training strategy (BC vs DAgger,
number of demos, steps, and budget).

Usage:
    python src/api/experiment_planner.py --port 8041
    python src/api/experiment_planner.py --host 0.0.0.0 --port 8041

Endpoints:
    GET  /                  HTML form: robot type, current SR, target SR, budget
    POST /plan              Form submit → runs plan_experiment() → redirect to /plan/{id}
    GET  /plan/{plan_id}    HTML plan page: method callout, milestone roadmap, cost, rationale
    GET  /api/plan          JSON plan (query params: robot_type, current_sr, target_sr, budget_usd)
    GET  /health            Health check
"""

import argparse
import math
import random
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, Form, Query
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    print("pip install fastapi uvicorn")
    raise

# ── Constants ──────────────────────────────────────────────────────────────────

OCI_USD_PER_HR = 3.06
OCI_THROUGHPUT_ITS = 2.35      # steps/sec on A100
GPU_UTIL = 0.77                # parallel efficiency
MAX_PROJECTED_SR = 0.75        # honest cap on projected success rate

DESIGN_PARTNER_PORTAL_URL = "http://localhost:8006"

ROBOT_TYPES = ["franka", "ur5e", "xarm7", "kinova", "custom"]

# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class ExperimentPlan:
    plan_id: str
    robot_type: str
    current_success_rate: float
    target_success_rate: float
    recommended_method: str
    n_demos_needed: int
    n_steps: int
    estimated_cost_usd: float
    estimated_gpu_hours: float
    expected_success_rate: float
    dagger_iters: int
    rationale: str
    milestones: List[dict]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    budget_usd: float = 10.0

# ── In-memory plan history ─────────────────────────────────────────────────────

plan_history: List[ExperimentPlan] = []
_plans_by_id: dict = {}

# ── Cost helpers ───────────────────────────────────────────────────────────────

def _compute_cost(n_steps: int) -> tuple[float, float]:
    """Return (estimated_cost_usd, estimated_gpu_hours)."""
    effective_its = OCI_THROUGHPUT_ITS * GPU_UTIL
    gpu_hours = round(n_steps / effective_its / 3600, 3)
    cost_usd = round(gpu_hours * OCI_USD_PER_HR, 4)
    return cost_usd, gpu_hours


def _clamp_sr(sr: float) -> float:
    return min(round(sr, 3), MAX_PROJECTED_SR)

# ── Core planning logic ────────────────────────────────────────────────────────

def plan_experiment(
    robot_type: str,
    current_sr: float,
    target_sr: float,
    budget_usd: float = 10.0,
) -> ExperimentPlan:
    """
    Select optimal training strategy and produce an ExperimentPlan.

    Strategy rules (evaluated top-to-bottom, first match wins):
      1. budget_usd < 1.00  → distilled student + BC only (budget-forced)
      2. current_sr == 0 and target_sr <= 0.20  → BC 500 demos, 5 000 steps
      3. current_sr <= 0.10 and target_sr <= 0.50 → DAgger 3 iters × 30 eps from 1000-demo base
      4. current_sr in (0.10, 0.40)  → curriculum DAgger 4 levels × 10 eps
      5. current_sr >= 0.40 and target_sr <= 0.65 → online DAgger (continuous flywheel)
      6. fallback → BC 1000 demos, 10 000 steps
    """
    plan_id = uuid.uuid4().hex[:8]

    # Rule 1: budget guard
    if budget_usd < 1.00:
        method = "Distilled Student + BC"
        n_demos = 200
        n_steps = 2000
        dagger_iters = 0
        expected_sr = _clamp_sr(current_sr + 0.08)
        rationale = (
            f"Budget ${budget_usd:.2f} is below the $1.00 minimum for DAgger runs. "
            "Using knowledge distillation from the base GR00T checkpoint into a compact "
            "student policy, followed by BC on a small demo set. "
            "Throughput is higher (student is 2× smaller) but accuracy gains are modest."
        )
        milestones = [
            {"step": 1, "label": "Distill student policy from GR00T base", "expected_sr": round(current_sr, 2)},
            {"step": 2, "label": f"BC on {n_demos} demos ({n_steps // 2} steps)", "expected_sr": _clamp_sr(current_sr + 0.04)},
            {"step": 3, "label": f"Full BC ({n_steps} steps)", "expected_sr": expected_sr},
        ]

    # Rule 2: cold start, low target
    elif current_sr == 0.0 and target_sr <= 0.20:
        method = "Behavioral Cloning (BC)"
        n_demos = 500
        n_steps = 5000
        dagger_iters = 0
        expected_sr = _clamp_sr(0.15 + random.uniform(-0.02, 0.03))
        rationale = (
            f"Starting from scratch (0% success) with a modest target of {target_sr*100:.0f}%. "
            "Pure Behavioral Cloning on 500 human demonstrations is the most data-efficient "
            "approach at this stage. No need for expensive DAgger rollouts until the policy "
            "can perform at least 10% of tasks autonomously."
        )
        milestones = [
            {"step": 1, "label": "Collect 500 teleoperation demos", "expected_sr": 0.0},
            {"step": 2, "label": "BC training 2 500 steps (half-way)", "expected_sr": _clamp_sr(0.06)},
            {"step": 3, "label": "BC training 5 000 steps (full)", "expected_sr": expected_sr},
            {"step": 4, "label": "Eval on 20-episode held-out set", "expected_sr": expected_sr},
        ]

    # Rule 3: low SR, medium target → DAgger 3 iters
    elif current_sr <= 0.10 and target_sr <= 0.50:
        method = "DAgger (3 iters × 30 episodes)"
        n_demos = 1000
        n_steps = 15000   # ~5 000 per DAgger iter
        dagger_iters = 3
        expected_sr = _clamp_sr(0.38 + random.uniform(-0.03, 0.05))
        rationale = (
            f"Current success rate is low ({current_sr*100:.0f}%) but target "
            f"({target_sr*100:.0f}%) requires interactive improvement. "
            "Starting from a 1 000-demo BC base checkpoint, 3 DAgger iterations "
            "each add 30 on-policy correction episodes and fine-tune for 5 000 steps. "
            "This closed-loop loop reliably closes the covariate shift gap."
        )
        milestones = [
            {"step": 1, "label": "BC base: 1 000 demos, 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.08)},
            {"step": 2, "label": "DAgger iter 1: 30 episodes + 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.15)},
            {"step": 3, "label": "DAgger iter 2: 30 episodes + 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.25)},
            {"step": 4, "label": "DAgger iter 3: 30 episodes + 5 000 steps", "expected_sr": expected_sr},
            {"step": 5, "label": "Eval on 20-episode held-out set", "expected_sr": expected_sr},
        ]

    # Rule 4: medium SR → curriculum DAgger
    elif 0.10 < current_sr < 0.40:
        method = "Curriculum DAgger (4 levels × 10 episodes)"
        n_demos = 600
        n_steps = 20000
        dagger_iters = 4
        expected_sr = _clamp_sr(current_sr + 0.28 + random.uniform(-0.03, 0.04))
        rationale = (
            f"Current success rate ({current_sr*100:.0f}%) indicates the policy already "
            "grasps basic task structure. Curriculum DAgger progressively increases task "
            "difficulty across 4 levels (easy → medium → hard → OOD), collecting 10 "
            "correction episodes per level. This prevents policy collapse on harder variants "
            "while reinforcing existing skills."
        )
        milestones = [
            {"step": 1, "label": "Level 1 (easy): 10 eps + 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.07)},
            {"step": 2, "label": "Level 2 (medium): 10 eps + 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.14)},
            {"step": 3, "label": "Level 3 (hard): 10 eps + 5 000 steps", "expected_sr": _clamp_sr(current_sr + 0.21)},
            {"step": 4, "label": "Level 4 (OOD): 10 eps + 5 000 steps", "expected_sr": expected_sr},
            {"step": 5, "label": "Full eval suite (20 eps per level)", "expected_sr": expected_sr},
        ]

    # Rule 5: strong baseline → online DAgger flywheel
    elif current_sr >= 0.40 and target_sr <= 0.65:
        method = "Online DAgger (Continuous Flywheel)"
        n_demos = 300
        n_steps = 10000
        dagger_iters = 0   # continuous, not counted as discrete iters
        expected_sr = _clamp_sr(current_sr + 0.18 + random.uniform(-0.02, 0.05))
        rationale = (
            f"Policy is already performing at {current_sr*100:.0f}% — in the regime where "
            "batch DAgger yields diminishing returns. Online DAgger (continuous flywheel) "
            "streams on-policy data to the training loop in real time, triggering incremental "
            "fine-tune cycles automatically. 300 targeted correction demos + 10 000 online "
            "steps is the sweet spot for pushing past 60% without catastrophic forgetting."
        )
        milestones = [
            {"step": 1, "label": "Warm-up: 100 correction demos", "expected_sr": _clamp_sr(current_sr + 0.04)},
            {"step": 2, "label": "Online flywheel: 5 000 steps live", "expected_sr": _clamp_sr(current_sr + 0.10)},
            {"step": 3, "label": "Flywheel complete: 10 000 steps", "expected_sr": expected_sr},
            {"step": 4, "label": "Eval on unseen object poses", "expected_sr": expected_sr},
        ]

    # Rule 6: fallback
    else:
        method = "Behavioral Cloning (BC) — Extended"
        n_demos = 1000
        n_steps = 10000
        dagger_iters = 0
        expected_sr = _clamp_sr(current_sr + 0.20 + random.uniform(-0.02, 0.03))
        rationale = (
            f"General-purpose BC recipe for {robot_type}. "
            "1 000 demonstrations with 10 000 training steps covers most manipulation tasks "
            "where on-policy rollouts are not yet available."
        )
        milestones = [
            {"step": 1, "label": "Collect 1 000 teleoperation demos", "expected_sr": current_sr},
            {"step": 2, "label": "BC training 5 000 steps (half-way)", "expected_sr": _clamp_sr(current_sr + 0.10)},
            {"step": 3, "label": "BC training 10 000 steps (full)", "expected_sr": expected_sr},
        ]

    cost_usd, gpu_hours = _compute_cost(n_steps)

    plan = ExperimentPlan(
        plan_id=plan_id,
        robot_type=robot_type,
        current_success_rate=current_sr,
        target_success_rate=target_sr,
        recommended_method=method,
        n_demos_needed=n_demos,
        n_steps=n_steps,
        estimated_cost_usd=cost_usd,
        estimated_gpu_hours=gpu_hours,
        expected_success_rate=expected_sr,
        dagger_iters=dagger_iters,
        rationale=rationale,
        milestones=milestones,
        budget_usd=budget_usd,
    )

    plan_history.append(plan)
    _plans_by_id[plan_id] = plan
    return plan

# ── Seed example plans ─────────────────────────────────────────────────────────

def _seed_examples() -> None:
    examples = [
        ("franka",  0.0,  0.15,  5.00),
        ("ur5e",    0.05, 0.40,  20.00),
        ("xarm7",   0.25, 0.55,  50.00),
        ("kinova",  0.45, 0.65,  30.00),
        ("custom",  0.0,  0.20,  0.50),   # budget-forced
    ]
    for robot, csr, tsr, budget in examples:
        plan_experiment(robot, csr, tsr, budget)

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud — Experiment Planner", version="1.0.0")

# ── HTML helpers ───────────────────────────────────────────────────────────────

_DARK_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; padding: 24px; }
h1 { color: #38bdf8; font-size: 1.6rem; margin-bottom: 4px; }
h2 { color: #7dd3fc; font-size: 1.1rem; margin: 20px 0 10px; }
h3 { color: #bae6fd; font-size: 0.95rem; margin: 12px 0 6px; }
p  { color: #94a3b8; font-size: 0.88rem; line-height: 1.5; }
a  { color: #38bdf8; text-decoration: none; }
a:hover { text-decoration: underline; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.badge { display: inline-block; background: #0369a1; color: #e0f2fe; border-radius: 6px;
         padding: 2px 10px; font-size: 0.78rem; font-weight: 600; margin-bottom: 8px; }
.badge-green  { background: #14532d; color: #86efac; }
.badge-yellow { background: #713f12; color: #fde68a; }
.badge-purple { background: #3b0764; color: #e9d5ff; }
label { font-size: 0.85rem; color: #94a3b8; display: block; margin-bottom: 4px; }
input, select {
  background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
  border-radius: 6px; padding: 8px 12px; width: 100%; font-size: 0.9rem; margin-bottom: 14px;
}
button, .btn {
  background: #0369a1; color: #fff; border: none; border-radius: 8px;
  padding: 10px 22px; font-size: 0.9rem; cursor: pointer; font-weight: 600;
  display: inline-block; margin-top: 6px;
}
button:hover, .btn:hover { background: #0284c7; }
.btn-green { background: #15803d; }
.btn-green:hover { background: #16a34a; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
th { text-align: left; color: #64748b; padding: 6px 10px; border-bottom: 1px solid #1e293b; }
td { padding: 7px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
tr:hover td { background: #1e293b; }
.milestone { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 14px; }
.ms-num { background: #0369a1; color: #fff; border-radius: 50%; width: 28px; height: 28px;
          display: flex; align-items: center; justify-content: center; font-size: 0.8rem;
          font-weight: 700; flex-shrink: 0; }
.ms-label { font-size: 0.88rem; color: #e2e8f0; }
.ms-sr { font-size: 0.78rem; color: #38bdf8; margin-top: 2px; }
.method-box { border-radius: 10px; padding: 18px 22px; margin-bottom: 20px; }
.method-bc      { background: #1c3256; border: 1px solid #2563eb; }
.method-dagger  { background: #1a2e1a; border: 1px solid #16a34a; }
.method-online  { background: #2d1b4e; border: 1px solid #7c3aed; }
.method-student { background: #2d1a00; border: 1px solid #d97706; }
.method-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 4px; }
.kpi-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
.kpi { background: #1e293b; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 120px; }
.kpi-val { font-size: 1.4rem; font-weight: 700; color: #38bdf8; }
.kpi-label { font-size: 0.75rem; color: #64748b; margin-top: 2px; }
"""

def _method_css_class(method: str) -> str:
    m = method.lower()
    if "student" in m or "distill" in m:
        return "method-student"
    if "online" in m or "flywheel" in m:
        return "method-online"
    if "dagger" in m:
        return "method-dagger"
    return "method-bc"

def _badge_class(method: str) -> str:
    m = method.lower()
    if "student" in m:
        return "badge badge-yellow"
    if "dagger" in m or "online" in m:
        return "badge badge-green"
    return "badge"

def _sr_pct(v: float) -> str:
    return f"{v*100:.1f}%"

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    rows = ""
    for p in reversed(plan_history[-20:]):
        rows += (
            f"<tr>"
            f"<td><a href='/plan/{p.plan_id}'>{p.plan_id}</a></td>"
            f"<td>{p.robot_type}</td>"
            f"<td>{_sr_pct(p.current_success_rate)} → {_sr_pct(p.target_success_rate)}</td>"
            f"<td>{p.recommended_method}</td>"
            f"<td>{p.n_demos_needed}</td>"
            f"<td>{p.n_steps:,}</td>"
            f"<td>${p.estimated_cost_usd:.4f}</td>"
            f"<td>{_sr_pct(p.expected_success_rate)}</td>"
            f"</tr>"
        )
    robot_opts = "".join(f"<option value='{r}'>{r}</option>" for r in ROBOT_TYPES)
    html = f"""<!DOCTYPE html><html><head><title>Experiment Planner — OCI Robot Cloud</title>
<style>{_DARK_CSS}</style></head><body>
<h1>OCI Robot Cloud — Experiment Planner</h1>
<p style='margin-bottom:20px'>Design optimal fine-tuning experiments for your robot policy.</p>

<div class='card' style='max-width:560px'>
<h2 style='margin-top:0'>Plan Your Training</h2>
<form method='POST' action='/plan'>
  <label>Robot Type</label>
  <select name='robot_type'>{robot_opts}</select>
  <label>Current Success Rate (%)</label>
  <input type='number' name='current_sr' min='0' max='100' step='1' value='0' required>
  <label>Target Success Rate (%)</label>
  <input type='number' name='target_sr' min='1' max='100' step='1' value='40' required>
  <label>Budget (USD)</label>
  <input type='number' name='budget_usd' min='0' step='0.5' value='10.00' required>
  <button type='submit'>Generate Plan</button>
</form>
</div>

<h2>Past Plans ({len(plan_history)} total)</h2>
<div class='card'>
<table>
<tr><th>Plan ID</th><th>Robot</th><th>SR Range</th><th>Method</th>
    <th>Demos</th><th>Steps</th><th>Cost</th><th>Expected SR</th></tr>
{rows if rows else '<tr><td colspan="8" style="color:#475569">No plans yet.</td></tr>'}
</table>
</div>
</body></html>"""
    return HTMLResponse(html)


@app.post("/plan")
async def create_plan_form(
    robot_type: str = Form(...),
    current_sr: float = Form(...),
    target_sr: float = Form(...),
    budget_usd: float = Form(10.0),
):
    # form sends percentages 0-100
    plan = plan_experiment(robot_type, current_sr / 100, target_sr / 100, budget_usd)
    return RedirectResponse(url=f"/plan/{plan.plan_id}", status_code=303)


@app.get("/plan/{plan_id}", response_class=HTMLResponse)
async def view_plan(plan_id: str):
    plan = _plans_by_id.get(plan_id)
    if plan is None:
        return HTMLResponse("<h1>Plan not found</h1>", status_code=404)

    method_class = _method_css_class(plan.recommended_method)
    badge_class  = _badge_class(plan.recommended_method)

    milestones_html = ""
    for ms in plan.milestones:
        milestones_html += f"""
<div class='milestone'>
  <div class='ms-num'>{ms['step']}</div>
  <div>
    <div class='ms-label'>{ms['label']}</div>
    <div class='ms-sr'>Expected SR after this step: {_sr_pct(ms['expected_sr'])}</div>
  </div>
</div>"""

    dagger_line = (
        f"<div class='kpi'><div class='kpi-val'>{plan.dagger_iters}</div>"
        f"<div class='kpi-label'>DAgger Iterations</div></div>"
        if plan.dagger_iters > 0 else ""
    )

    html = f"""<!DOCTYPE html><html><head><title>Plan {plan.plan_id} — OCI Robot Cloud</title>
<style>{_DARK_CSS}</style></head><body>
<p><a href='/'>← Back to Planner</a></p>
<h1 style='margin-top:12px'>Experiment Plan <span style='color:#64748b;font-size:1rem'>#{plan.plan_id}</span></h1>
<p style='margin-bottom:18px'>{plan.robot_type} &nbsp;|&nbsp; Created {plan.created_at[:19].replace('T',' ')} UTC</p>

<div class='method-box {method_class}'>
  <span class='{badge_class}'>Recommended Method</span>
  <div class='method-title'>{plan.recommended_method}</div>
  <p style='margin-top:6px;color:#94a3b8'>{plan.rationale}</p>
</div>

<div class='kpi-row'>
  <div class='kpi'><div class='kpi-val'>{_sr_pct(plan.current_success_rate)}</div><div class='kpi-label'>Current SR</div></div>
  <div class='kpi'><div class='kpi-val'>{_sr_pct(plan.target_success_rate)}</div><div class='kpi-label'>Target SR</div></div>
  <div class='kpi'><div class='kpi-val'>{_sr_pct(plan.expected_success_rate)}</div><div class='kpi-label'>Projected SR</div></div>
  <div class='kpi'><div class='kpi-val'>{plan.n_demos_needed}</div><div class='kpi-label'>Demos Needed</div></div>
  <div class='kpi'><div class='kpi-val'>{plan.n_steps:,}</div><div class='kpi-label'>Training Steps</div></div>
  {dagger_line}
</div>

<div class='card'>
<h2 style='margin-top:0'>Cost Breakdown</h2>
<div class='kpi-row'>
  <div class='kpi'><div class='kpi-val'>${plan.estimated_cost_usd:.4f}</div><div class='kpi-label'>Estimated Cost (USD)</div></div>
  <div class='kpi'><div class='kpi-val'>{plan.estimated_gpu_hours:.3f}h</div><div class='kpi-label'>GPU Hours (A100)</div></div>
  <div class='kpi'><div class='kpi-val'>${plan.budget_usd:.2f}</div><div class='kpi-label'>Your Budget</div></div>
</div>
{'<p style="color:#fbbf24">⚠ Estimated cost exceeds budget. Consider reducing steps or using distillation.</p>' if plan.estimated_cost_usd > plan.budget_usd else '<p style="color:#4ade80">Budget check: OK</p>'}
</div>

<div class='card'>
<h2 style='margin-top:0'>Milestone Roadmap</h2>
{milestones_html}
</div>

<a href='{DESIGN_PARTNER_PORTAL_URL}' class='btn btn-green'>Start Training in Design Partner Portal</a>
</body></html>"""
    return HTMLResponse(html)


@app.get("/api/plan")
async def api_plan(
    robot_type: str = Query("franka"),
    current_sr: float = Query(0.0),
    target_sr: float = Query(0.40),
    budget_usd: float = Query(10.0),
):
    plan = plan_experiment(robot_type, current_sr, target_sr, budget_usd)
    return JSONResponse(asdict(plan))


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "experiment_planner", "port": 8041})

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Experiment Planner")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8041, help="Port (default: 8041)")
    args = parser.parse_args()

    _seed_examples()

    import uvicorn as _uv
    print(f"Experiment Planner running at http://{args.host}:{args.port}")
    _uv.run(app, host=args.host, port=args.port)
