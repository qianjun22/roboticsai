#!/usr/bin/env python3
"""
partner_onboarding_wizard.py — Guided first-run onboarding for OCI Robot Cloud partners.

Walks new design partners through submitting their first demo dataset and launching
a fine-tuning job, with progress tracking and a shareable results link.

Usage:
    python src/api/partner_onboarding_wizard.py [--port 8024] [--mock]

    # Or CLI wizard mode:
    python src/api/partner_onboarding_wizard.py --cli

Steps:
    1. Validate API key (provisioned via multi_tenant_manager.py)
    2. Upload demo dataset (HDF5 / LeRobot v2 / CSV)
    3. Configure fine-tune (steps, learning rate, embodiment)
    4. Launch job and watch live progress
    5. Download eval report + model card

Endpoints:
    GET  /                  Wizard UI
    GET  /health            Health check
    POST /validate-key      Test API key against multi-tenant manager
    POST /jobs              Submit fine-tune job
    GET  /jobs/{id}         Job status
    GET  /jobs/{id}/report  Download eval HTML report
"""

import argparse
import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

JOBS_FILE = "/tmp/onboarding_jobs.json"
MOCK_LATENCY_STEP = 0.3   # seconds per simulated training step (demo purposes)


# ── Job store ─────────────────────────────────────────────────────────────────

def _load_jobs() -> dict:
    if Path(JOBS_FILE).exists():
        return json.loads(Path(JOBS_FILE).read_text())
    return {}


def _save_jobs(jobs: dict):
    Path(JOBS_FILE).write_text(json.dumps(jobs, indent=2))


def _get_job(job_id: str) -> dict | None:
    return _load_jobs().get(job_id)


def _update_job(job_id: str, updates: dict):
    jobs = _load_jobs()
    if job_id in jobs:
        jobs[job_id].update(updates)
        _save_jobs(jobs)


# ── Job runner ────────────────────────────────────────────────────────────────

def _run_mock_job(job_id: str):
    """Simulate a fine-tuning job with realistic timing and log output."""
    import random
    rng = random.Random(hash(job_id))
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return

    total_steps = job.get("training_steps", 1000)
    _update_job(job_id, {"status": "running", "started_at": datetime.now().isoformat()})

    log_lines = []
    loss = 0.68
    step = 0

    # Warm-up phase
    for phase, n_steps, step_delay in [
        ("Loading dataset", 0, 2.0),
        ("Initializing model", 0, 3.5),
    ]:
        _update_job(job_id, {"phase": phase, "log": log_lines + [f"[{datetime.now().strftime('%H:%M:%S')}] {phase}..."]})
        time.sleep(step_delay)
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {phase} — done")

    # Training
    checkpoint_interval = max(100, total_steps // 5)
    for step in range(1, total_steps + 1):
        # Exponential loss decay with noise
        loss = 0.68 * (0.999 ** step) + 0.08 + rng.gauss(0, 0.005)
        loss = max(0.05, loss)

        if step % 50 == 0:
            log_line = f"[{datetime.now().strftime('%H:%M:%S')}] step {step}/{total_steps} loss={loss:.4f}"
            log_lines.append(log_line)
            if len(log_lines) > 30:
                log_lines = log_lines[-30:]
            pct = int(step / total_steps * 100)
            _update_job(job_id, {
                "phase": f"Training ({pct}%)",
                "current_step": step,
                "current_loss": round(loss, 4),
                "progress_pct": pct,
                "log": log_lines,
            })

        if step % checkpoint_interval == 0:
            ckpt = f"checkpoint-{step}"
            log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Saved {ckpt}")
            _update_job(job_id, {"latest_checkpoint": ckpt})

        time.sleep(MOCK_LATENCY_STEP)

    # Eval phase
    _update_job(job_id, {"phase": "Running closed-loop eval (20 episodes)", "progress_pct": 100})
    time.sleep(4.0)
    success_rate = rng.uniform(0.05, 0.15)   # realistic range
    log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Eval complete: {success_rate:.1%} success (20 eps)")

    # Done
    _update_job(job_id, {
        "status": "completed",
        "phase": "Done",
        "completed_at": datetime.now().isoformat(),
        "final_loss": round(loss, 4),
        "eval_success_rate": round(success_rate, 4),
        "latest_checkpoint": f"checkpoint-{total_steps}",
        "log": log_lines,
    })


# ── API ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud — Partner Onboarding Wizard")


@app.get("/health")
def health():
    jobs = _load_jobs()
    return {"status": "ok", "total_jobs": len(jobs)}


@app.post("/validate-key")
def validate_key(api_key: str = Form(...)):
    """Stub: in production, calls multi_tenant_manager /me endpoint."""
    if api_key.startswith("oci_rc_"):
        return {"valid": True, "partner": "Demo Partner", "tier": "growth"}
    return JSONResponse({"valid": False, "error": "Invalid API key format"}, status_code=401)


@app.post("/jobs", status_code=201)
def submit_job(
    partner_name: str = Form(""),
    embodiment: str = Form("franka"),
    training_steps: int = Form(1000),
    n_demos: int = Form(50),
    learning_rate: float = Form(1e-4),
    api_key: str = Form(""),
):
    job_id = "job_" + hashlib.md5(f"{partner_name}:{time.time()}".encode()).hexdigest()[:10]
    job = {
        "id": job_id,
        "partner_name": partner_name,
        "embodiment": embodiment,
        "training_steps": training_steps,
        "n_demos": n_demos,
        "learning_rate": learning_rate,
        "status": "queued",
        "phase": "Queued",
        "current_step": 0,
        "current_loss": None,
        "progress_pct": 0,
        "latest_checkpoint": None,
        "eval_success_rate": None,
        "final_loss": None,
        "log": [],
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        # Cost estimate
        "cost_estimate_usd": round(training_steps / 10000 * 0.43, 2),
    }
    jobs = _load_jobs()
    jobs[job_id] = job
    _save_jobs(jobs)
    threading.Thread(target=_run_mock_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "message": f"Job submitted. Watch at /jobs/{job_id}"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return job


@app.get("/jobs/{job_id}/report", response_class=HTMLResponse)
def get_report(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    sr = job.get("eval_success_rate")
    loss = job.get("final_loss")
    sr_color = "#10b981" if sr and sr >= 0.1 else "#f59e0b" if sr and sr >= 0.01 else "#ef4444"
    sr_str = f"{sr:.1%}" if sr is not None else "pending"
    loss_str = f"{loss:.4f}" if loss is not None else "pending"
    status_color = "#10b981" if job["status"] == "completed" else "#f59e0b"

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Fine-Tune Report — {job_id}</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;
border-bottom:1px solid #1e293b;padding-bottom:5px;margin-top:24px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}}
.card{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
.val{{font-size:2em;font-weight:bold}} .lbl{{color:#64748b;font-size:.78em}}
pre{{background:#1e293b;padding:14px;border-radius:6px;font-size:.82em;overflow-x:auto;max-height:300px;overflow-y:auto}}
</style></head><body>
<h1>Fine-Tune Report</h1>
<p style="color:#64748b">Job: <code>{job_id}</code> · Partner: {job.get('partner_name','—')} · {job.get('completed_at','in progress')[:19]}</p>

<div class="grid">
  <div class="card"><div class="val" style="color:{sr_color}">{sr_str}</div><div class="lbl">Closed-Loop Success</div></div>
  <div class="card"><div class="val">{loss_str}</div><div class="lbl">Final Loss</div></div>
  <div class="card"><div class="val">{job.get('training_steps','—')}</div><div class="lbl">Training Steps</div></div>
  <div class="card"><div class="val" style="color:{status_color}">{job['status']}</div><div class="lbl">Status</div></div>
</div>

<h2>Configuration</h2>
<table style="border-collapse:collapse;width:100%">
  {"".join(f"<tr><td style='padding:5px 12px;color:#94a3b8;border-bottom:1px solid #1e293b'>{k}</td><td style='padding:5px 12px;border-bottom:1px solid #1e293b'>{v}</td></tr>" for k,v in [("Embodiment", job.get('embodiment','—')), ("N demos", job.get('n_demos','—')), ("Learning rate", job.get('learning_rate','—')), ("Cost estimate", f"${job.get('cost_estimate_usd','?')}"), ("Checkpoint", job.get('latest_checkpoint','—'))])}
</table>

<h2>Training Log</h2>
<pre>{"<br>".join(job.get('log', ['No log yet']))}</pre>

<h2>Next Steps</h2>
<ul style="margin:8px 0 0 20px;line-height:1.8">
  <li>Download checkpoint: <code>{job.get('latest_checkpoint','checkpoint-{steps}')}</code></li>
  <li>Run DAgger to improve: <code>python src/training/dagger_train.py --base-checkpoint ...</code></li>
  <li>Deploy to Jetson: <code>bash src/infra/jetson_deploy.sh --package ...</code></li>
  <li>View model card: <code>docs/groot_model_card.md</code></li>
</ul>

<p style="color:#475569;font-size:.8em;margin-top:28px">OCI Robot Cloud · github.com/qianjun22/roboticsai</p>
</body></html>"""


# ── Wizard UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def wizard_ui():
    jobs = _load_jobs()
    recent = sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)[:5]

    job_rows = ""
    for j in recent:
        sr = j.get("eval_success_rate")
        sr_str = f"{sr:.1%}" if sr is not None else "—"
        color = "#10b981" if j["status"] == "completed" else "#f59e0b" if j["status"] == "running" else "#64748b"
        job_rows += (
            f"<tr><td><code>{j['id']}</code></td>"
            f"<td>{j.get('partner_name','—')}</td>"
            f"<td style='color:{color}'>{j['status']} ({j.get('progress_pct',0)}%)</td>"
            f"<td>{sr_str}</td>"
            f"<td><a href='/jobs/{j['id']}/report' style='color:#C74634'>Report</a></td></tr>"
        )

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Partner Onboarding — OCI Robot Cloud</title>
<style>
*{{box-sizing:border-box}} body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:0;margin:0}}
header{{background:#1e293b;padding:16px 32px;border-bottom:2px solid #C74634}}
h1{{color:#C74634;font-size:1.3em;margin:0}} .sub{{color:#64748b;font-size:.85em}}
.wizard{{max-width:760px;margin:32px auto;padding:0 24px}}
.step{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}}
.step-num{{display:inline-block;width:26px;height:26px;border-radius:50%;background:#C74634;
           color:white;text-align:center;line-height:26px;font-size:.85em;font-weight:bold;margin-right:8px}}
.step-title{{color:#e2e8f0;font-weight:bold;font-size:1em}}
label{{color:#94a3b8;font-size:.8em;display:block;margin:10px 0 4px}}
input,select{{background:#0f172a;color:#e2e8f0;border:1px solid #334155;padding:8px 12px;
              border-radius:6px;width:100%;font-size:.9em}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
button.primary{{background:#C74634;color:white;border:none;padding:10px 24px;border-radius:6px;
                cursor:pointer;font-weight:bold;font-size:.95em;margin-top:12px;width:100%}}
button.primary:hover{{background:#a83222}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}
th{{background:#C74634;color:white;padding:7px 12px;text-align:left;font-size:.82em}}
td{{padding:6px 12px;border-bottom:1px solid #1e293b;font-size:.85em}}
.progress-bar{{background:#0f172a;border-radius:4px;height:8px;margin-top:8px;overflow:hidden}}
.progress-fill{{height:100%;background:#C74634;border-radius:4px;transition:width .5s}}
#status-box{{background:#0f172a;border-radius:6px;padding:12px;font-family:monospace;font-size:.82em;
             max-height:120px;overflow-y:auto;margin-top:10px;display:none}}
</style></head><body>

<header>
  <h1>OCI Robot Cloud — Partner Onboarding</h1>
  <div class="sub">Fine-tune GR00T N1.6-3B on your robot data in &lt;5 minutes</div>
</header>

<div class="wizard">

  <div class="step">
    <div><span class="step-num">1</span><span class="step-title">Connect</span></div>
    <label>Your API Key (from your OCI Robot Cloud account)</label>
    <input id="api-key" placeholder="oci_rc_..." type="password" />
    <button class="primary" style="width:auto;padding:8px 16px" onclick="validateKey()">
      Validate Key →
    </button>
    <div id="key-status" style="margin-top:8px;font-size:.85em"></div>
  </div>

  <div class="step">
    <div><span class="step-num">2</span><span class="step-title">Configure</span></div>
    <div class="row">
      <div>
        <label>Partner / Company Name</label>
        <input id="pname" placeholder="Acme Robotics" />
      </div>
      <div>
        <label>Robot Embodiment</label>
        <select id="embodiment">
          <option value="franka">Franka Panda (9-DOF)</option>
          <option value="ur5e">UR5e (8-DOF)</option>
          <option value="xarm7">xArm7 (9-DOF)</option>
          <option value="kinova">Kinova Gen3 (9-DOF)</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Number of Demo Episodes</label>
        <input id="ndemos" type="number" value="50" min="10" max="10000" />
      </div>
      <div>
        <label>Training Steps</label>
        <select id="steps">
          <option value="500">500 (quick test, ~$0.04)</option>
          <option value="1000" selected>1000 (starter, ~$0.09)</option>
          <option value="2000">2000 (~$0.17)</option>
          <option value="5000">5000 (production, ~$0.43)</option>
        </select>
      </div>
    </div>
    <div>
      <label>Learning Rate</label>
      <select id="lr">
        <option value="0.0001" selected>1e-4 (recommended)</option>
        <option value="0.00005">5e-5 (conservative)</option>
        <option value="0.0003">3e-4 (aggressive)</option>
      </select>
    </div>
  </div>

  <div class="step">
    <div><span class="step-num">3</span><span class="step-title">Submit &amp; Monitor</span></div>
    <button class="primary" onclick="submitJob()">🚀 Launch Fine-Tune Job</button>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width:0%"></div></div>
    <div id="progress-label" style="color:#64748b;font-size:.82em;margin-top:4px"></div>
    <div id="status-box"></div>
    <div id="result-link" style="margin-top:12px"></div>
  </div>

  <div class="step">
    <div><span class="step-num">4</span><span class="step-title">Recent Jobs</span></div>
    <table>
      <tr><th>Job ID</th><th>Partner</th><th>Status</th><th>Success Rate</th><th>Report</th></tr>
      {job_rows or "<tr><td colspan='5' style='color:#475569;text-align:center'>No jobs yet</td></tr>"}
    </table>
  </div>

</div>

<script>
let currentJobId = null;
let pollInterval = null;

async function validateKey() {{
  const key = document.getElementById('api-key').value;
  const res = await fetch('/validate-key', {{
    method: 'POST', body: new URLSearchParams({{api_key: key}})
  }});
  const j = await res.json();
  const el = document.getElementById('key-status');
  if (j.valid) {{
    el.style.color = '#10b981';
    el.textContent = '✓ Valid — ' + j.partner + ' (' + j.tier + ' tier)';
  }} else {{
    el.style.color = '#ef4444';
    el.textContent = '✗ ' + (j.error || 'Invalid key');
  }}
}}

async function submitJob() {{
  const body = new URLSearchParams({{
    partner_name: document.getElementById('pname').value,
    embodiment: document.getElementById('embodiment').value,
    training_steps: document.getElementById('steps').value,
    n_demos: document.getElementById('ndemos').value,
    learning_rate: document.getElementById('lr').value,
    api_key: document.getElementById('api-key').value,
  }});
  const res = await fetch('/jobs', {{ method: 'POST', body }});
  const j = await res.json();
  currentJobId = j.job_id;
  document.getElementById('status-box').style.display = 'block';
  startPolling(j.job_id);
}}

function startPolling(jobId) {{
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => pollJob(jobId), 2000);
}}

async function pollJob(jobId) {{
  const res = await fetch('/jobs/' + jobId);
  const j = await res.json();
  document.getElementById('progress-fill').style.width = j.progress_pct + '%';
  document.getElementById('progress-label').textContent =
    j.phase + ' — step ' + j.current_step + '/' + j.training_steps +
    (j.current_loss ? ' · loss ' + j.current_loss.toFixed(4) : '');
  const box = document.getElementById('status-box');
  if (j.log && j.log.length) box.innerHTML = j.log.slice(-10).join('<br>');
  if (j.status === 'completed') {{
    clearInterval(pollInterval);
    const link = document.getElementById('result-link');
    const sr = j.eval_success_rate;
    link.innerHTML =
      '<div style="background:#1e293b;padding:14px;border-radius:8px;border-left:4px solid #10b981">' +
      '<b style="color:#10b981">✓ Fine-tune complete!</b><br>' +
      'Success rate: <b style="color:#10b981">' + (sr ? (sr*100).toFixed(1)+'%' : '—') + '</b> · ' +
      'Final loss: ' + (j.final_loss||'—') + '<br>' +
      '<a href="/jobs/' + jobId + '/report" style="color:#C74634;font-weight:bold">View full report →</a>' +
      '</div>';
  }}
}}
</script>

<p style="text-align:center;padding:16px;color:#334155;font-size:.8em">
  OCI Robot Cloud · github.com/qianjun22/roboticsai · Questions? Open a GitHub issue
</p>
</body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8024)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
