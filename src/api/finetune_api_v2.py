"""
GR00T Fine-tune API v2 — Production-grade REST API for fine-tuning job management.
Port 8048. Replaces robot_cloud_api.py with async job tracking, SQLite persistence,
background simulation, cost accounting, and a dark-theme HTML dashboard.
"""

import argparse
import json
import math
import random
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DB_PATH = "/tmp/finetune_jobs.db"
OCI_A100_PRICE_PER_GPU_HR = 4.20   # USD
SIMULATION_STEP_INTERVAL = 2.0     # seconds between background updates
SIMULATION_TOTAL_DURATION = 30.0   # seconds to "complete" a job


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class FinetuneJob:
    job_id: str
    name: str
    dataset_path: str
    base_model: str
    n_steps: int
    batch_size: int
    lr: float
    precision: str          # "bf16" | "fp16" | "fp32"
    n_gpus: int
    lora_rank: int          # 0 = full fine-tune
    dagger_iters: int
    status: str             # "queued" | "running" | "done" | "failed" | "cancelled"
    progress_pct: float     # 0–100
    current_loss: Optional[float]
    current_step: int
    total_steps: int
    checkpoint_path: Optional[str]
    cost_usd: float
    started_at: Optional[str]       # ISO-8601
    completed_at: Optional[str]     # ISO-8601
    error: Optional[str]
    logs_url: str

    @classmethod
    def new(cls, name, dataset_path, base_model, n_steps, batch_size, lr,
            precision, n_gpus, lora_rank, dagger_iters):
        job_id = str(uuid.uuid4())
        return cls(
            job_id=job_id,
            name=name,
            dataset_path=dataset_path,
            base_model=base_model,
            n_steps=n_steps,
            batch_size=batch_size,
            lr=lr,
            precision=precision,
            n_gpus=n_gpus,
            lora_rank=lora_rank,
            dagger_iters=dagger_iters,
            status="queued",
            progress_pct=0.0,
            current_loss=None,
            current_step=0,
            total_steps=n_steps,
            checkpoint_path=None,
            cost_usd=0.0,
            started_at=None,
            completed_at=None,
            error=None,
            logs_url=f"/jobs/{job_id}/logs",
        )


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                data   TEXT NOT NULL
            )
        """)
        c.commit()


def save_job(job: FinetuneJob):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO jobs (job_id, data) VALUES (?, ?)",
            (job.job_id, json.dumps(asdict(job))),
        )
        c.commit()


def load_job(job_id: str) -> Optional[FinetuneJob]:
    with _conn() as c:
        row = c.execute("SELECT data FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return None
    return FinetuneJob(**json.loads(row["data"]))


def list_jobs(status_filter: Optional[str] = None, limit: int = 100) -> List[FinetuneJob]:
    with _conn() as c:
        rows = c.execute("SELECT data FROM jobs").fetchall()
    jobs = [FinetuneJob(**json.loads(r["data"])) for r in rows]
    if status_filter:
        jobs = [j for j in jobs if j.status == status_filter]
    # newest first (by started_at or job_id as tiebreak)
    jobs.sort(key=lambda j: (j.started_at or "", j.job_id), reverse=True)
    return jobs[:limit]


# ---------------------------------------------------------------------------
# Background simulation
# ---------------------------------------------------------------------------
_sim_lock = threading.Lock()


def _simulate_job(job: FinetuneJob):
    """Runs in a daemon thread; updates job progress every SIMULATION_STEP_INTERVAL."""
    n_ticks = int(SIMULATION_TOTAL_DURATION / SIMULATION_STEP_INTERVAL)
    initial_loss = 2.5 + random.uniform(-0.3, 0.3)

    # Mark running
    with _sim_lock:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        save_job(job)

    for tick in range(1, n_ticks + 1):
        time.sleep(SIMULATION_STEP_INTERVAL)
        with _sim_lock:
            # re-load in case of external cancel
            fresh = load_job(job.job_id)
            if fresh is None or fresh.status == "cancelled":
                return

        pct = (tick / n_ticks) * 100.0
        step = int((tick / n_ticks) * job.total_steps)
        # Exponential decay loss with noise
        decay = math.exp(-3.0 * tick / n_ticks)
        loss = 0.08 + (initial_loss - 0.08) * decay + random.uniform(-0.01, 0.01)
        elapsed_hr = (tick * SIMULATION_STEP_INTERVAL) / 3600.0
        cost = elapsed_hr * job.n_gpus * OCI_A100_PRICE_PER_GPU_HR

        with _sim_lock:
            job.progress_pct = round(pct, 1)
            job.current_step = step
            job.current_loss = round(loss, 4)
            job.cost_usd = round(cost, 4)
            save_job(job)

    # Completion
    with _sim_lock:
        fresh = load_job(job.job_id)
        if fresh is None or fresh.status == "cancelled":
            return
        total_hr = SIMULATION_TOTAL_DURATION / 3600.0
        job.status = "done"
        job.progress_pct = 100.0
        job.current_step = job.total_steps
        job.current_loss = round(0.08 + random.uniform(-0.005, 0.005), 4)
        job.cost_usd = round(total_hr * job.n_gpus * OCI_A100_PRICE_PER_GPU_HR, 4)
        job.checkpoint_path = f"/checkpoints/{job.job_id}/step_{job.total_steps}"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        save_job(job)


def launch_simulation(job: FinetuneJob):
    t = threading.Thread(target=_simulate_job, args=(job,), daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
def _make_completed_job(name, dataset, model, n_steps, n_gpus, lora_rank,
                        loss, cost, started_offset_hr, duration_hr):
    job = FinetuneJob.new(name, dataset, model, n_steps, 16, 1e-4, "bf16",
                          n_gpus, lora_rank, 0)
    now = datetime.now(timezone.utc).timestamp()
    started = now - started_offset_hr * 3600
    completed = started + duration_hr * 3600
    job.status = "done"
    job.progress_pct = 100.0
    job.current_step = n_steps
    job.total_steps = n_steps
    job.current_loss = loss
    job.cost_usd = cost
    job.started_at = datetime.fromtimestamp(started, tz=timezone.utc).isoformat()
    job.completed_at = datetime.fromtimestamp(completed, tz=timezone.utc).isoformat()
    job.checkpoint_path = f"/checkpoints/{job.job_id}/step_{n_steps}"
    return job


def seed_jobs():
    existing = list_jobs()
    if len(existing) >= 4:
        return  # already seeded

    completed1 = _make_completed_job(
        "lerobot-baseline-v1", "/data/lerobot_v1", "gr00t-n1.6",
        5000, 1, 16, 0.0991, 0.0058, 72, 0.50)
    completed2 = _make_completed_job(
        "lerobot-1000demo-v2", "/data/lerobot_1000demo", "gr00t-n1.6",
        5000, 4, 0, 0.0994, 0.0233, 48, 0.47)
    completed3 = _make_completed_job(
        "dagger-run5-finetune", "/data/dagger_run5", "gr00t-n1.6",
        2000, 4, 0, 0.1030, 0.0196, 24, 0.46)

    running = FinetuneJob.new(
        "lerobot-2000demo-v3", "/data/lerobot_2000demo", "gr00t-n1.6",
        10000, 4, 0, 0, "bf16", 4, 0, 3)
    running.status = "running"
    running.started_at = datetime.now(timezone.utc).isoformat()
    running.progress_pct = 42.0
    running.current_step = 4200
    running.current_loss = 0.1512
    running.cost_usd = round(0.35 * 4 * OCI_A100_PRICE_PER_GPU_HR, 4)

    for j in [completed1, completed2, completed3, running]:
        save_job(j)


# ---------------------------------------------------------------------------
# Log simulation
# ---------------------------------------------------------------------------
def generate_logs(job: FinetuneJob) -> List[str]:
    lines = [
        f"[INFO] Job {job.job_id} — {job.name}",
        f"[INFO] Base model: {job.base_model}  LoRA rank: {job.lora_rank}",
        f"[INFO] Dataset: {job.dataset_path}",
        f"[INFO] Steps: {job.total_steps}  GPUs: {job.n_gpus}  Precision: {job.precision}",
        "[INFO] Loading dataset ...",
        "[INFO] Initializing model weights ...",
        "[INFO] Optimizer: AdamW  LR: {:.2e}".format(job.lr),
    ]
    n_logged = max(1, int(job.progress_pct / 10))
    for i in range(n_logged):
        step = int((i + 1) / 10 * job.total_steps)
        pct = (i + 1) * 10
        decay = math.exp(-3.0 * pct / 100)
        loss = round(0.08 + 2.3 * decay, 4)
        lines.append(f"[TRAIN] step={step:6d}  loss={loss:.4f}  lr={job.lr:.2e}")
    if job.status == "done":
        lines.append(f"[INFO] Checkpoint saved → {job.checkpoint_path}")
        lines.append(f"[INFO] Final loss: {job.current_loss}  Cost: ${job.cost_usd:.4f}")
        lines.append("[INFO] Job complete.")
    elif job.status == "failed":
        lines.append(f"[ERROR] {job.error or 'Unknown error'}")
    elif job.status == "cancelled":
        lines.append("[WARN] Job cancelled by user.")
    return lines


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GR00T Fine-tune API v2</title>
<style>
  :root { --bg:#0f1117; --card:#1a1d27; --border:#2d3147; --accent:#6c63ff;
          --green:#22c55e; --yellow:#f59e0b; --red:#ef4444; --gray:#6b7280;
          --text:#e2e8f0; --sub:#94a3b8; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'Segoe UI',sans-serif; padding:2rem; }
  h1 { font-size:1.6rem; margin-bottom:.25rem; }
  .subtitle { color:var(--sub); font-size:.85rem; margin-bottom:2rem; }
  h2 { font-size:1.1rem; margin:1.5rem 0 .75rem; color:var(--sub); text-transform:uppercase;
       letter-spacing:.05em; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1.25rem; margin-bottom:1rem; }
  .badge { display:inline-block; padding:.2rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
  .badge-running  { background:#1d4ed8; color:#93c5fd; }
  .badge-done     { background:#14532d; color:#86efac; }
  .badge-queued   { background:#78350f; color:#fde68a; }
  .badge-failed   { background:#7f1d1d; color:#fca5a5; }
  .badge-cancelled{ background:#374151; color:#d1d5db; }
  .progress-wrap  { background:#1e2235; border-radius:999px; height:8px; margin:.5rem 0; }
  .progress-bar   { height:8px; border-radius:999px; background:var(--accent);
                    transition:width .4s ease; }
  .job-meta { display:flex; flex-wrap:wrap; gap:.5rem 1.5rem; font-size:.82rem; color:var(--sub); margin-top:.5rem; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th { text-align:left; color:var(--sub); padding:.5rem .75rem; border-bottom:1px solid var(--border); }
  td { padding:.5rem .75rem; border-bottom:1px solid var(--border); }
  tr:last-child td { border-bottom:none; }
  .form-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:.75rem; }
  label { display:block; font-size:.8rem; color:var(--sub); margin-bottom:.25rem; }
  input,select { width:100%; background:#0f1117; border:1px solid var(--border); color:var(--text);
                 padding:.45rem .65rem; border-radius:6px; font-size:.9rem; }
  input:focus,select:focus { outline:none; border-color:var(--accent); }
  button { background:var(--accent); color:#fff; border:none; padding:.6rem 1.4rem;
           border-radius:6px; font-size:.9rem; cursor:pointer; margin-top:.75rem; }
  button:hover { opacity:.85; }
  .cost-box { display:flex; gap:1.5rem; flex-wrap:wrap; }
  .cost-item { background:var(--card); border:1px solid var(--border); border-radius:8px;
               padding:.75rem 1.25rem; text-align:center; }
  .cost-item .val { font-size:1.5rem; font-weight:700; color:var(--accent); }
  .cost-item .lbl { font-size:.78rem; color:var(--sub); margin-top:.2rem; }
  #submitResult { margin-top:.75rem; font-size:.85rem; }
</style>
</head>
<body>
<h1>GR00T Fine-tune API v2</h1>
<p class="subtitle">OCI Robot Cloud · Port 8048 · A100 $4.20/GPU-hr</p>

<div id="costs-section">
  <h2>Cost This Month</h2>
  <div class="cost-box" id="cost-box">Loading...</div>
</div>

<h2>Active Jobs</h2>
<div id="active-jobs">Loading...</div>

<h2>Completed Jobs</h2>
<div class="card" style="padding:0;overflow:hidden">
  <table id="completed-table">
    <thead><tr>
      <th>Name</th><th>Model</th><th>Steps</th><th>LoRA</th>
      <th>GPUs</th><th>Loss</th><th>Cost</th><th>Status</th><th>Completed</th>
    </tr></thead>
    <tbody id="completed-body"><tr><td colspan="9">Loading...</td></tr></tbody>
  </table>
</div>

<h2>Submit Fine-tune Job</h2>
<div class="card">
  <form id="submit-form">
    <div class="form-grid">
      <div><label>Job Name</label><input name="name" value="my-finetune-run" required></div>
      <div><label>Dataset Path</label><input name="dataset_path" value="/data/lerobot_v2" required></div>
      <div><label>Base Model</label>
        <select name="base_model">
          <option>gr00t-n1.6</option><option>gr00t-n1</option><option>openVLA-7b</option>
        </select>
      </div>
      <div><label>Steps</label><input name="n_steps" type="number" value="5000" required></div>
      <div><label>Batch Size</label><input name="batch_size" type="number" value="16"></div>
      <div><label>Learning Rate</label><input name="lr" type="number" step="any" value="0.0001"></div>
      <div><label>Precision</label>
        <select name="precision"><option>bf16</option><option>fp16</option><option>fp32</option></select>
      </div>
      <div><label>GPUs</label><input name="n_gpus" type="number" value="4"></div>
      <div><label>LoRA Rank (0=full)</label><input name="lora_rank" type="number" value="16"></div>
      <div><label>DAgger Iterations</label><input name="dagger_iters" type="number" value="0"></div>
    </div>
    <button type="submit">Submit Job</button>
    <div id="submitResult"></div>
  </form>
</div>

<script>
const fmt = (v) => v !== null && v !== undefined ? v : '—';
const fmtDate = (s) => s ? new Date(s).toLocaleString() : '—';
const badge = (s) => `<span class="badge badge-${s}">${s}</span>`;

async function loadDashboard() {
  const [jobsRes, costsRes] = await Promise.all([
    fetch('/jobs?limit=100'), fetch('/api/costs')
  ]);
  const jobs = await jobsRes.json();
  const costs = await costsRes.json();

  // Cost box
  document.getElementById('cost-box').innerHTML = `
    <div class="cost-item"><div class="val">$${costs.total_cost_usd.toFixed(2)}</div><div class="lbl">Total This Month</div></div>
    <div class="cost-item"><div class="val">${costs.total_jobs}</div><div class="lbl">Jobs Submitted</div></div>
    <div class="cost-item"><div class="val">${costs.gpu_hours_total.toFixed(2)}h</div><div class="lbl">GPU Hours</div></div>
  `;

  // Active jobs
  const active = jobs.filter(j => j.status === 'running' || j.status === 'queued');
  const activeDiv = document.getElementById('active-jobs');
  if (!active.length) {
    activeDiv.innerHTML = '<p style="color:var(--sub);font-size:.9rem">No active jobs.</p>';
  } else {
    activeDiv.innerHTML = active.map(j => `
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <strong>${j.name}</strong> ${badge(j.status)}
          <button onclick="cancelJob('${j.job_id}')" style="background:var(--red);padding:.3rem .8rem;font-size:.78rem">Cancel</button>
        </div>
        <div class="progress-wrap"><div class="progress-bar" style="width:${j.progress_pct}%"></div></div>
        <div class="job-meta">
          <span>${j.progress_pct.toFixed(1)}% · step ${j.current_step}/${j.total_steps}</span>
          <span>Loss: ${fmt(j.current_loss)}</span>
          <span>GPUs: ${j.n_gpus}</span>
          <span>Cost: $${j.cost_usd.toFixed(4)}</span>
          <span>Started: ${fmtDate(j.started_at)}</span>
          <span><a href="/jobs/${j.job_id}/logs" style="color:var(--accent)">Logs</a></span>
        </div>
      </div>`).join('');
  }

  // Completed / failed / cancelled
  const done = jobs.filter(j => !['running','queued'].includes(j.status));
  const tbody = document.getElementById('completed-body');
  if (!done.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="color:var(--sub)">No completed jobs.</td></tr>';
  } else {
    tbody.innerHTML = done.map(j => `<tr>
      <td><a href="/jobs/${j.job_id}" style="color:var(--accent)">${j.name}</a></td>
      <td>${j.base_model}</td><td>${j.total_steps}</td>
      <td>${j.lora_rank === 0 ? 'Full' : j.lora_rank}</td>
      <td>${j.n_gpus}</td><td>${fmt(j.current_loss)}</td>
      <td>$${j.cost_usd.toFixed(4)}</td>
      <td>${badge(j.status)}</td><td>${fmtDate(j.completed_at)}</td>
    </tr>`).join('');
  }
}

async function cancelJob(jobId) {
  if (!confirm('Cancel job ' + jobId + '?')) return;
  const r = await fetch('/jobs/' + jobId, {method:'DELETE'});
  const d = await r.json();
  alert(d.message || JSON.stringify(d));
  loadDashboard();
}

document.getElementById('submit-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  // coerce numbers
  ['n_steps','batch_size','n_gpus','lora_rank','dagger_iters'].forEach(k => body[k] = parseInt(body[k]));
  body.lr = parseFloat(body.lr);
  const r = await fetch('/jobs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const d = await r.json();
  const res = document.getElementById('submitResult');
  if (r.ok) {
    res.innerHTML = '<span style="color:var(--green)">Job created: ' + d.job_id + '</span>';
    loadDashboard();
  } else {
    res.innerHTML = '<span style="color:var(--red)">Error: ' + JSON.stringify(d.detail) + '</span>';
  }
});

loadDashboard();
setInterval(loadDashboard, 5000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if HAS_FASTAPI:
    app = FastAPI(title="GR00T Fine-tune API v2", version="2.0.0")

    @app.on_event("startup")
    async def _startup():
        init_db()
        seed_jobs()
        # Re-launch simulation for any jobs stuck in "running" from a previous seed
        for job in list_jobs(status_filter="running"):
            launch_simulation(job)

    # ---- Dashboard ----
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    # ---- Health ----
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "finetune_api_v2", "port": 8048}

    # ---- Create job ----
    @app.post("/jobs", status_code=201)
    async def create_job(body: dict):
        required = ["name", "dataset_path", "base_model", "n_steps"]
        for field_name in required:
            if field_name not in body:
                raise HTTPException(status_code=422, detail=f"Missing required field: {field_name}")
        job = FinetuneJob.new(
            name=body["name"],
            dataset_path=body["dataset_path"],
            base_model=body.get("base_model", "gr00t-n1.6"),
            n_steps=int(body.get("n_steps", 5000)),
            batch_size=int(body.get("batch_size", 16)),
            lr=float(body.get("lr", 1e-4)),
            precision=body.get("precision", "bf16"),
            n_gpus=int(body.get("n_gpus", 4)),
            lora_rank=int(body.get("lora_rank", 0)),
            dagger_iters=int(body.get("dagger_iters", 0)),
        )
        save_job(job)
        launch_simulation(job)
        return {"job_id": job.job_id, "status": job.status}

    # ---- Get job ----
    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = load_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(job)

    # ---- Cancel job ----
    @app.delete("/jobs/{job_id}")
    async def cancel_job(job_id: str):
        job = load_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status not in ("queued", "running"):
            raise HTTPException(status_code=409, detail=f"Cannot cancel job in state: {job.status}")
        with _sim_lock:
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            save_job(job)
        return {"message": f"Job {job_id} cancelled"}

    # ---- List jobs ----
    @app.get("/jobs")
    async def list_jobs_endpoint(
        status: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=200),
    ):
        return [asdict(j) for j in list_jobs(status_filter=status, limit=limit)]

    # ---- Logs ----
    @app.get("/jobs/{job_id}/logs")
    async def get_logs(job_id: str):
        job = load_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        lines = generate_logs(job)
        return {"job_id": job_id, "lines": lines}

    # ---- Costs ----
    @app.get("/api/costs")
    async def get_costs():
        all_jobs = list_jobs()
        total_cost = sum(j.cost_usd for j in all_jobs)
        # Approximate GPU hours: cost / (n_gpus * price_per_hr)
        total_gpu_hr = sum(
            j.cost_usd / (j.n_gpus * OCI_A100_PRICE_PER_GPU_HR)
            for j in all_jobs if j.n_gpus > 0
        )
        breakdown = [
            {
                "job_id": j.job_id,
                "name": j.name,
                "status": j.status,
                "cost_usd": j.cost_usd,
                "n_gpus": j.n_gpus,
            }
            for j in all_jobs
        ]
        return {
            "total_cost_usd": round(total_cost, 4),
            "total_jobs": len(all_jobs),
            "gpu_hours_total": round(total_gpu_hr, 4),
            "price_per_gpu_hr": OCI_A100_PRICE_PER_GPU_HR,
            "per_job": breakdown,
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GR00T Fine-tune API v2")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8048)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: FastAPI not installed. Run: pip install fastapi uvicorn")
        raise SystemExit(1)

    print(f"Starting GR00T Fine-tune API v2 on http://{args.host}:{args.port}")
    uvicorn.run(
        "finetune_api_v2:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
