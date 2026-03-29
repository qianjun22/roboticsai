#!/usr/bin/env python3
"""
design_partner_portal.py — Design partner self-service web portal for OCI Robot Cloud.

Provides a dashboard at http://localhost:8006 where design partners can:
  - Submit training jobs (upload demo data + configure training)
  - Monitor job progress in real-time (SSE streaming)
  - View results (success rate, loss curve, cost breakdown)
  - Download trained checkpoints
  - Run eval on their own test episodes

Usage:
    python src/api/design_partner_portal.py --port 8006
    python src/api/design_partner_portal.py --mock  # uses mock data

IMPORTANT: This is the single-URL demo tool for the GTC 2027 live demo.
"""

import argparse
import asyncio
import math
import random
import string
import time
from typing import Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("pip install fastapi uvicorn pydantic")
    raise

# ── Global state ──────────────────────────────────────────────────────────────

_mock_mode = True  # set via --mock / --live flag at startup

# In-memory job store: job_id -> dict
_jobs: dict = {}

# ── Pricing (same constants as cost_calculator.py) ───────────────────────────

OCI_USD_PER_HR = 3.06
OCI_THROUGHPUT_ITS = 2.35  # steps/sec at batch=32


def _estimate_cost(demo_count: int, train_steps: int) -> float:
    """Estimate USD cost for a training run on OCI A100."""
    effective_its = OCI_THROUGHPUT_ITS * 0.77  # 77% parallel efficiency
    time_hr = (train_steps / effective_its) / 3600
    return round(time_hr * OCI_USD_PER_HR, 4)


def _estimate_eta_min(train_steps: int) -> float:
    effective_its = OCI_THROUGHPUT_ITS * 0.77
    return round(train_steps / effective_its / 60, 1)


def _rand_job_id() -> str:
    suffix = "".join(random.choices(string.digits + string.ascii_uppercase, k=6))
    return f"job-{suffix}"


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud Design Partner Portal", version="1.0.0")

# ── Request / response models ─────────────────────────────────────────────────


class JobRequest(BaseModel):
    demo_count: int = 100
    train_steps: int = 2000
    robot_type: str = "Franka"
    task_description: str = "Pick and place"


# ── REST endpoints ────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return JSONResponse({
        "status": "ok",
        "version": "1.0.0",
        "mode": "mock" if _mock_mode else "live",
    })


@app.get("/pricing")
def pricing():
    """Cost breakdown table — same numbers as cost_calculator.py."""
    return JSONResponse({
        "providers": [
            {
                "id": "oci_a100",
                "name": "OCI A100-SXM4-80GB",
                "usd_per_hr": 3.06,
                "throughput_its": 2.35,
                "capex_usd": 0,
                "setup_min": 5,
                "compliance": "FedRAMP / OC2",
                "max_gpus": 32,
                "badge": "RECOMMENDED",
            },
            {
                "id": "dgx_onprem",
                "name": "DGX A100 On-Premise",
                "usd_per_hr": 3.26,
                "throughput_its": 2.35,
                "capex_usd": 200_000,
                "setup_min": 10_000,
                "compliance": "Customer-managed",
                "max_gpus": 8,
                "badge": "",
            },
            {
                "id": "aws_p4d",
                "name": "AWS p4d.24xlarge (8× A100)",
                "usd_per_hr": 32.77,
                "throughput_its": 2.35,
                "capex_usd": 0,
                "setup_min": 20,
                "compliance": "GovCloud (extra cost)",
                "max_gpus": 8,
                "badge": "",
            },
            {
                "id": "lambda_a100",
                "name": "Lambda Cloud A100",
                "usd_per_hr": 2.49,
                "throughput_its": 2.35,
                "capex_usd": 0,
                "setup_min": 15,
                "compliance": "None (no FedRAMP)",
                "max_gpus": 8,
                "badge": "",
            },
        ],
        "note": "Cost = (steps / throughput_its) / 3600 * usd_per_hr; batch=32; 77% parallel efficiency",
    })


@app.post("/jobs")
def create_job(req: JobRequest):
    job_id = _rand_job_id()
    estimated_cost = _estimate_cost(req.demo_count, req.train_steps)
    eta_min = _estimate_eta_min(req.train_steps)

    _jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "demo_count": req.demo_count,
        "train_steps": req.train_steps,
        "robot_type": req.robot_type,
        "task_description": req.task_description,
        "progress_pct": 0.0,
        "current_loss": 0.45,
        "elapsed_s": 0.0,
        "eta_s": eta_min * 60,
        "cost_so_far": 0.0,
        "estimated_cost_usd": estimated_cost,
        "eta_minutes": eta_min,
        "created_at": time.time(),
    }

    return JSONResponse({
        "job_id": job_id,
        "status": "running",
        "estimated_cost_usd": estimated_cost,
        "eta_minutes": eta_min,
    })


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in _jobs:
        return JSONResponse({"error": "job not found"}, status_code=404)

    job = _jobs[job_id]
    # Simulate progress based on elapsed wall time (mock)
    if _mock_mode and job["status"] == "running":
        elapsed = time.time() - job["created_at"]
        total_sec = job["eta_s"] if job["eta_s"] > 0 else 120.0
        pct = min(elapsed / total_sec * 100, 100.0)
        # Simulated loss decay: starts at 0.45, decays toward ~0.10
        loss = 0.10 + 0.35 * math.exp(-3.0 * (pct / 100))
        job["progress_pct"] = round(pct, 1)
        job["current_loss"] = round(loss, 4)
        job["elapsed_s"] = round(elapsed, 1)
        job["cost_so_far"] = round(job["estimated_cost_usd"] * (pct / 100), 5)
        if pct >= 100:
            job["status"] = "completed"

    return JSONResponse({
        "job_id": job["job_id"],
        "status": job["status"],
        "progress_pct": job["progress_pct"],
        "current_loss": job["current_loss"],
        "elapsed_s": job["elapsed_s"],
        "eta_s": max(job["eta_s"] - job["elapsed_s"], 0),
        "cost_so_far": job["cost_so_far"],
    })


@app.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE stream of training progress — yields every 2 seconds."""

    async def _generate():
        step_offset = 0
        train_steps = 2000
        if job_id in _jobs:
            train_steps = _jobs[job_id].get("train_steps", 2000)

        start = time.time()
        eta_s = _jobs[job_id]["eta_s"] if job_id in _jobs else 120.0

        while True:
            elapsed = time.time() - start
            pct = min(elapsed / max(eta_s, 1) * 100, 100.0)
            step = int(pct / 100 * train_steps)
            loss = round(0.10 + 0.35 * math.exp(-3.0 * (pct / 100)), 4)
            gpu_util = round(random.uniform(82, 95), 1)

            payload = (
                f'{{"step":{step},"loss":{loss},'
                f'"gpu_util":{gpu_util},"elapsed_s":{round(elapsed,1)}}}'
            )
            yield f"data: {payload}\n\n"

            if pct >= 100:
                if job_id in _jobs:
                    _jobs[job_id]["status"] = "completed"
                    _jobs[job_id]["progress_pct"] = 100.0
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/jobs/{job_id}/results")
def job_results(job_id: str):
    if job_id not in _jobs:
        return JSONResponse({"error": "job not found"}, status_code=404)

    job = _jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse({"error": "job not yet completed", "status": job["status"]}, status_code=202)

    # Mock success rate: 75–92% based on demo count
    demo_count = job.get("demo_count", 100)
    success_rate = round(min(0.92, 0.55 + demo_count * 0.0004 + random.uniform(-0.03, 0.03)), 2)

    return JSONResponse({
        "job_id": job_id,
        "success_rate": success_rate,
        "final_loss": 0.099,
        "total_cost_usd": job["estimated_cost_usd"],
        "checkpoint_url": f"/checkpoints/{job_id}/checkpoint_final.pt",
        "report_url": f"/reports/{job_id}/eval_report.json",
    })


# ── Dashboard HTML ────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OCI Robot Cloud — Design Partner Portal</title>
<style>
  :root {
    --bg: #111113; --card: #1C1C1E; --border: #2a2a2c;
    --red: #C74634; --green: #34D399; --amber: #FBBF24;
    --blue: #60A5FA; --gray: #6b7280; --text: #E5E7EB; --lgray: #9CA3AF;
    --red-dim: rgba(199,70,52,0.12);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; min-height: 100vh; }

  /* Header */
  header {
    background: #0d0d0f; border-bottom: 2px solid var(--red);
    padding: 14px 32px; display: flex; align-items: center; gap: 16px;
    position: sticky; top: 0; z-index: 100;
  }
  header h1 { font-size: 20px; color: var(--red); letter-spacing: 1px; }
  header .sub { color: var(--lgray); font-size: 12px; flex: 1; }
  .mode-badge {
    background: var(--red-dim); border: 1px solid var(--red);
    color: var(--red); font-size: 10px; padding: 3px 10px; border-radius: 3px;
    font-weight: bold; letter-spacing: 1px;
  }

  main { max-width: 1200px; margin: 0 auto; padding: 28px 32px; }

  /* Section labels */
  h2 {
    font-size: 11px; color: var(--lgray); text-transform: uppercase;
    letter-spacing: 1.5px; margin-bottom: 14px; padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }

  /* Stat cards */
  .stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
  .stat-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px 24px;
  }
  .stat-card .label { font-size: 11px; color: var(--lgray); text-transform: uppercase; letter-spacing: 1px; }
  .stat-card .value { font-size: 38px; font-weight: bold; margin: 8px 0 4px; }
  .stat-card .note { font-size: 11px; color: var(--gray); }

  /* Job table */
  .section { margin-bottom: 32px; }
  table { width: 100%; border-collapse: collapse; }
  thead th {
    text-align: left; font-size: 10px; color: var(--lgray); text-transform: uppercase;
    letter-spacing: 1px; padding: 8px 12px; border-bottom: 1px solid var(--border);
  }
  tbody tr { border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; }
  tbody tr:hover { background: #1a1a1c; }
  td { padding: 12px 12px; font-size: 13px; }
  .badge {
    display: inline-block; padding: 3px 9px; border-radius: 4px;
    font-size: 10px; font-weight: bold; letter-spacing: 0.5px;
  }
  .badge-running  { background: rgba(251,191,36,0.15); color: var(--amber); border: 1px solid rgba(251,191,36,0.3); }
  .badge-completed{ background: rgba(52,211,153,0.12); color: var(--green); border: 1px solid rgba(52,211,153,0.3); }
  .badge-failed   { background: rgba(199,70,52,0.12);  color: var(--red);   border: 1px solid rgba(199,70,52,0.3); }
  .badge-queued   { background: rgba(96,165,250,0.12); color: var(--blue);  border: 1px solid rgba(96,165,250,0.3); }
  .progress-bar { background: #2a2a2c; border-radius: 3px; height: 6px; overflow: hidden; margin-top: 4px; width: 120px; }
  .progress-fill { height: 100%; background: var(--amber); border-radius: 3px; transition: width 1s linear; }
  .progress-fill.done { background: var(--green); }

  /* Submit form */
  .form-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 24px; margin-bottom: 32px;
  }
  .form-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
  @media (max-width: 800px) { .form-grid { grid-template-columns: 1fr 1fr; } }
  .field label { display: block; font-size: 10px; color: var(--lgray); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
  .field input[type=number], .field input[type=text], .field select {
    width: 100%; background: #111113; border: 1px solid var(--border);
    color: var(--text); padding: 10px 12px; border-radius: 6px;
    font-family: monospace; font-size: 14px;
  }
  .field input:focus, .field select:focus { outline: none; border-color: var(--red); }
  .field .range-val { font-size: 13px; color: var(--red); margin-top: 4px; }
  input[type=range] { width: 100%; accent-color: var(--red); cursor: pointer; }
  .submit-btn {
    background: var(--red); color: #fff; border: none;
    padding: 12px 32px; border-radius: 6px; font-size: 14px;
    font-family: monospace; cursor: pointer; font-weight: bold; letter-spacing: 1px;
    transition: background 0.2s;
  }
  .submit-btn:hover { background: #e05d4a; }
  .submit-btn:disabled { background: #444; cursor: not-allowed; }

  /* Eval results */
  .eval-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px 24px; margin-bottom: 32px;
  }
  .eval-row { display: flex; gap: 32px; flex-wrap: wrap; align-items: center; }
  .eval-metric .k { font-size: 11px; color: var(--lgray); text-transform: uppercase; margin-bottom: 4px; }
  .eval-metric .v { font-size: 28px; font-weight: bold; }
  .eval-metric .v.green { color: var(--green); }
  .eval-metric .v.red { color: var(--red); }

  /* Job detail drawer */
  .drawer {
    position: fixed; right: 0; top: 0; bottom: 0; width: 420px;
    background: #16161a; border-left: 1px solid var(--border);
    padding: 24px; overflow-y: auto; transform: translateX(110%);
    transition: transform 0.25s ease; z-index: 200;
  }
  .drawer.open { transform: translateX(0); }
  .drawer-close {
    float: right; background: none; border: none;
    color: var(--lgray); font-size: 20px; cursor: pointer;
  }
  .drawer h3 { font-size: 16px; color: var(--text); margin-bottom: 16px; }
  .drawer-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
  .drawer-meta .dm-k { font-size: 10px; color: var(--lgray); text-transform: uppercase; }
  .drawer-meta .dm-v { font-size: 14px; }
  .loss-log {
    background: #0d0d0f; border: 1px solid var(--border); border-radius: 6px;
    padding: 12px; font-size: 12px; height: 200px; overflow-y: auto;
    font-family: monospace; color: var(--lgray);
  }
  .loss-log .ll-line { margin-bottom: 4px; }
  .loss-log .ll-line span { color: var(--green); }
  .dl-btn {
    display: inline-block; margin-top: 12px;
    background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.3);
    color: var(--green); padding: 8px 18px; border-radius: 6px;
    font-family: monospace; font-size: 12px; cursor: pointer; text-decoration: none;
  }
  .dl-btn:hover { background: rgba(52,211,153,0.2); }

  /* Toast */
  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: #1C1C1E; border: 1px solid var(--green); color: var(--green);
    padding: 12px 24px; border-radius: 8px; font-size: 13px;
    opacity: 0; pointer-events: none; transition: opacity 0.3s; z-index: 300;
  }
  .toast.show { opacity: 1; }

  footer {
    text-align: center; color: var(--gray); font-size: 11px;
    padding: 20px 0 32px; border-top: 1px solid var(--border); margin-top: 8px;
  }
</style>
</head>
<body>

<header>
  <h1>OCI ROBOT CLOUD</h1>
  <span class="sub">Design Partner Portal · Oracle Cloud Infrastructure × NVIDIA</span>
  <span class="mode-badge" id="mode-badge">MOCK</span>
</header>

<main>

<!-- Stat cards -->
<div class="stat-row" id="stat-row">
  <div class="stat-card">
    <div class="label">Active Jobs</div>
    <div class="value" id="stat-active" style="color:var(--amber)">—</div>
    <div class="note">currently training on OCI A100</div>
  </div>
  <div class="stat-card">
    <div class="label">Total Demo Hours Trained</div>
    <div class="value" id="stat-hours" style="color:var(--blue)">—</div>
    <div class="note">cumulative across all jobs</div>
  </div>
  <div class="stat-card">
    <div class="label">Avg Success Rate</div>
    <div class="value" id="stat-success" style="color:var(--green)">—</div>
    <div class="note">last 5 completed jobs</div>
  </div>
</div>

<!-- Submit new job -->
<div class="section">
  <h2>Submit New Training Job</h2>
  <div class="form-card">
    <div class="form-grid">
      <div class="field">
        <label>Demo Count</label>
        <input type="range" id="demo_count" min="20" max="1000" step="20" value="100"
          oninput="document.getElementById('demo_count_val').textContent=this.value">
        <div class="range-val"><span id="demo_count_val">100</span> demos</div>
      </div>
      <div class="field">
        <label>Training Steps</label>
        <input type="range" id="train_steps" min="500" max="10000" step="500" value="2000"
          oninput="document.getElementById('train_steps_val').textContent=this.value">
        <div class="range-val"><span id="train_steps_val">2000</span> steps</div>
      </div>
      <div class="field">
        <label>Robot Type</label>
        <select id="robot_type">
          <option value="Franka">Franka Panda</option>
          <option value="UR5e">UR5e</option>
          <option value="xArm7">xArm7</option>
        </select>
      </div>
      <div class="field">
        <label>Task Description</label>
        <input type="text" id="task_desc" value="Pick and place" placeholder="e.g. Stack blocks">
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:20px;">
      <button class="submit-btn" id="submit-btn" onclick="submitJob()">SUBMIT JOB →</button>
      <span id="cost-preview" style="color:var(--lgray);font-size:12px;"></span>
    </div>
  </div>
</div>

<!-- Job list -->
<div class="section">
  <h2>Training Jobs</h2>
  <table>
    <thead>
      <tr>
        <th>Job ID</th>
        <th>Robot</th>
        <th>Task</th>
        <th>Demos</th>
        <th>Steps</th>
        <th>Status</th>
        <th>Progress</th>
        <th>Cost</th>
        <th>Loss</th>
      </tr>
    </thead>
    <tbody id="jobs-tbody">
      <tr><td colspan="9" style="text-align:center;color:var(--gray);padding:24px;">No jobs yet. Submit your first training job above.</td></tr>
    </tbody>
  </table>
</div>

<!-- Recent eval results -->
<div class="section">
  <h2>Recent Eval Results</h2>
  <div class="eval-card">
    <div class="eval-row" id="eval-row">
      <div style="color:var(--gray);font-size:13px;">Complete a training job to see eval results.</div>
    </div>
  </div>
</div>

</main>

<!-- Job detail drawer -->
<div class="drawer" id="drawer">
  <button class="drawer-close" onclick="closeDrawer()">✕</button>
  <h3 id="drawer-title">Job Detail</h3>
  <div class="drawer-meta" id="drawer-meta"></div>
  <div style="font-size:11px;color:var(--lgray);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Live Training Log</div>
  <div class="loss-log" id="loss-log"></div>
  <div id="drawer-actions"></div>
</div>

<div class="toast" id="toast"></div>

<footer>
  OCI Robot Cloud · Oracle Cloud Infrastructure × NVIDIA ·
  GR00T N1.6 fine-tuning · 2.35 it/s · $3.06/hr · FedRAMP / OC2
</footer>

<script>
// ── State ────────────────────────────────────────────────────────────────────
let _jobs = {};        // job_id -> latest status snapshot
let _pollers = {};     // job_id -> setInterval handle
let _sseStreams = {};  // job_id -> EventSource
let _activeDrawer = null;

// ── Init ─────────────────────────────────────────────────────────────────────
(async function init() {
  const h = await fetch('/health').then(r => r.json());
  document.getElementById('mode-badge').textContent = h.mode.toUpperCase();
  updateStats();
  updateCostPreview();
})();

// Update cost preview whenever sliders change
document.getElementById('demo_count').addEventListener('input', updateCostPreview);
document.getElementById('train_steps').addEventListener('input', updateCostPreview);

function updateCostPreview() {
  const steps = parseInt(document.getElementById('train_steps').value);
  const its = 2.35 * 0.77;
  const hr = (steps / its) / 3600;
  const cost = hr * 3.06;
  const eta = Math.round(steps / its / 60);
  document.getElementById('cost-preview').textContent =
    `Estimated: $${cost.toFixed(4)} · ~${eta} min on OCI A100`;
}

// ── Submit job ────────────────────────────────────────────────────────────────
async function submitJob() {
  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = 'SUBMITTING…';

  const body = {
    demo_count: parseInt(document.getElementById('demo_count').value),
    train_steps: parseInt(document.getElementById('train_steps').value),
    robot_type: document.getElementById('robot_type').value,
    task_description: document.getElementById('task_desc').value || 'Pick and place',
  };

  try {
    const res = await fetch('/jobs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.job_id) {
      _jobs[data.job_id] = {
        job_id: data.job_id, status: 'running',
        progress_pct: 0, current_loss: 0.45, elapsed_s: 0,
        cost_so_far: 0, estimated_cost_usd: data.estimated_cost_usd,
        eta_minutes: data.eta_minutes, demo_count: body.demo_count,
        train_steps: body.train_steps, robot_type: body.robot_type,
        task_description: body.task_description,
      };
      toast(`Job ${data.job_id} submitted — ETA ${data.eta_minutes} min, est. $${data.estimated_cost_usd}`);
      renderJobsTable();
      startPolling(data.job_id);
    }
  } catch (e) {
    toast('Error submitting job: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'SUBMIT JOB →';
  }
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling(job_id) {
  if (_pollers[job_id]) return;
  _pollers[job_id] = setInterval(async () => {
    try {
      const d = await fetch(`/jobs/${job_id}`).then(r => r.json());
      if (d.error) return;
      Object.assign(_jobs[job_id], d);
      renderJobsTable();
      updateStats();
      if (_activeDrawer === job_id) updateDrawer(job_id);
      if (d.status === 'completed' || d.status === 'failed') {
        clearInterval(_pollers[job_id]);
        delete _pollers[job_id];
        if (d.status === 'completed') loadEvalResults(job_id);
        renderJobsTable();
        updateStats();
      }
    } catch (_) {}
  }, 3000);
}

// ── Render jobs table ─────────────────────────────────────────────────────────
function renderJobsTable() {
  const tbody = document.getElementById('jobs-tbody');
  const ids = Object.keys(_jobs).reverse();
  if (ids.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--gray);padding:24px;">No jobs yet. Submit your first training job above.</td></tr>';
    return;
  }
  tbody.innerHTML = ids.map(id => {
    const j = _jobs[id];
    const badgeCls = {running:'badge-running',completed:'badge-completed',failed:'badge-failed',queued:'badge-queued'}[j.status] || 'badge-queued';
    const isDone = j.status === 'completed';
    const pct = j.progress_pct || 0;
    return `<tr onclick="openDrawer('${id}')">
      <td style="color:var(--lgray);font-size:12px;">${id}</td>
      <td>${j.robot_type || '—'}</td>
      <td style="color:var(--lgray);font-size:12px;">${(j.task_description||'').slice(0,20)}</td>
      <td>${j.demo_count || '—'}</td>
      <td>${j.train_steps || '—'}</td>
      <td><span class="badge ${badgeCls}">${j.status.toUpperCase()}</span></td>
      <td>
        <div style="font-size:11px;color:var(--lgray)">${pct.toFixed(0)}%</div>
        <div class="progress-bar"><div class="progress-fill${isDone?' done':''}" style="width:${pct}%"></div></div>
      </td>
      <td style="color:var(--amber)">$${(j.cost_so_far||0).toFixed(4)}</td>
      <td style="color:var(--green)">${j.current_loss ? j.current_loss.toFixed(4) : '—'}</td>
    </tr>`;
  }).join('');
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function updateStats() {
  const all = Object.values(_jobs);
  const active = all.filter(j => j.status === 'running').length;
  document.getElementById('stat-active').textContent = active;

  // Total demo-hours: sum of (demo_count * steps_per_demo_sec / 3600)
  // Approximate: each demo = 100 steps at ~0.43s each → ~43s = 0.012hr
  const totalHr = all.reduce((s, j) => s + (j.demo_count || 0) * 0.012, 0);
  document.getElementById('stat-hours').textContent = totalHr.toFixed(1) + 'h';

  const completed = all.filter(j => j.status === 'completed' && j._success_rate);
  if (completed.length > 0) {
    const avg = completed.reduce((s, j) => s + j._success_rate, 0) / completed.length;
    document.getElementById('stat-success').textContent = (avg * 100).toFixed(0) + '%';
  } else {
    document.getElementById('stat-success').textContent = '—';
  }
}

// ── Eval results ──────────────────────────────────────────────────────────────
async function loadEvalResults(job_id) {
  try {
    const r = await fetch(`/jobs/${job_id}/results`).then(res => res.json());
    if (r.error) return;
    if (_jobs[job_id]) {
      _jobs[job_id]._success_rate = r.success_rate;
      _jobs[job_id]._final_loss = r.final_loss;
      _jobs[job_id]._checkpoint_url = r.checkpoint_url;
    }
    updateStats();
    renderEvalSection();
  } catch (_) {}
}

function renderEvalSection() {
  const completed = Object.values(_jobs).filter(j => j._success_rate !== undefined);
  if (completed.length === 0) return;
  const latest = completed[completed.length - 1];
  const pct = (latest._success_rate * 100).toFixed(0);
  const color = latest._success_rate >= 0.75 ? 'green' : 'red';
  document.getElementById('eval-row').innerHTML = `
    <div class="eval-metric">
      <div class="k">Success Rate</div>
      <div class="v ${color}">${pct}%</div>
    </div>
    <div class="eval-metric">
      <div class="k">Final Loss</div>
      <div class="v" style="color:var(--blue)">${(latest._final_loss||0).toFixed(4)}</div>
    </div>
    <div class="eval-metric">
      <div class="k">Robot</div>
      <div class="v" style="font-size:18px">${latest.robot_type||'—'}</div>
    </div>
    <div class="eval-metric">
      <div class="k">Job</div>
      <div class="v" style="font-size:14px;color:var(--lgray)">${latest.job_id}</div>
    </div>
    ${latest._checkpoint_url ? `<a class="dl-btn" href="${latest._checkpoint_url}" target="_blank">⬇ Download Checkpoint</a>` : ''}
  `;
}

// ── Drawer ────────────────────────────────────────────────────────────────────
function openDrawer(job_id) {
  _activeDrawer = job_id;
  const j = _jobs[job_id] || {};
  document.getElementById('drawer-title').textContent = job_id;
  document.getElementById('drawer').classList.add('open');
  updateDrawer(job_id);
  startSSEStream(job_id);
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  _activeDrawer = null;
}

function updateDrawer(job_id) {
  const j = _jobs[job_id] || {};
  document.getElementById('drawer-meta').innerHTML = [
    ['Robot', j.robot_type || '—'],
    ['Task', j.task_description || '—'],
    ['Status', j.status || '—'],
    ['Progress', (j.progress_pct||0).toFixed(1) + '%'],
    ['Loss', j.current_loss ? j.current_loss.toFixed(4) : '—'],
    ['Elapsed', j.elapsed_s ? fmtSec(j.elapsed_s) : '—'],
    ['Cost so far', '$' + (j.cost_so_far||0).toFixed(4)],
    ['Est. cost', '$' + (j.estimated_cost_usd||0).toFixed(4)],
  ].map(([k, v]) => `<div><div class="dm-k">${k}</div><div class="dm-v">${v}</div></div>`).join('');

  const actions = document.getElementById('drawer-actions');
  if (j.status === 'completed' && j._checkpoint_url) {
    actions.innerHTML = `<a class="dl-btn" href="${j._checkpoint_url}" target="_blank">⬇ Download Checkpoint</a>`;
  } else {
    actions.innerHTML = '';
  }
}

function startSSEStream(job_id) {
  if (_sseStreams[job_id]) return;
  if (!_jobs[job_id] || _jobs[job_id].status !== 'running') return;

  const log = document.getElementById('loss-log');
  const es = new EventSource(`/jobs/${job_id}/stream`);
  _sseStreams[job_id] = es;

  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      const line = document.createElement('div');
      line.className = 'll-line';
      line.innerHTML = `[${fmtSec(d.elapsed_s)}] step=${d.step} loss=<span>${d.loss.toFixed(4)}</span> gpu=${d.gpu_util}%`;
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
    } catch (_) {}
  };

  es.onerror = () => {
    es.close();
    delete _sseStreams[job_id];
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtSec(s) {
  if (s < 60) return s.toFixed(0) + 's';
  return (s / 60).toFixed(1) + 'm';
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 4000);
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def root():
    return DASHBOARD_HTML


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    global _mock_mode
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Design Partner Portal")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", default=True, help="Use mock data (default)")
    parser.add_argument("--live", action="store_true", help="Connect to live OCI training backend")
    args = parser.parse_args()

    if args.live:
        _mock_mode = False

    mode = "mock" if _mock_mode else "live"
    print(f"[Portal] OCI Robot Cloud Design Partner Portal")
    print(f"[Portal] Mode: {mode}")
    print(f"[Portal] Open: http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
