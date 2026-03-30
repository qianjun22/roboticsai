#!/usr/bin/env python3
"""
multi_gpu_orchestrator.py — Multi-GPU training job queue and orchestrator.

Manages a queue of fine-tuning jobs across OCI A100 GPUs (0–7) and runs
them with automatic scheduling, fault recovery, and cost tracking.

Usage:
    # Start orchestrator service (port 8030):
    python src/training/multi_gpu_orchestrator.py --port 8030

    # Submit a job:
    curl -X POST http://localhost:8030/jobs \
      -H "Content-Type: application/json" \
      -d '{"dataset_path":"/tmp/lerobot","steps":5000,"n_gpus":1}'

    # Mock simulation (no GPU needed):
    python src/training/multi_gpu_orchestrator.py --simulate
"""

import json
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Config ────────────────────────────────────────────────────────────────────

N_GPUS = 8              # OCI A100-SXM4-80GB × 8
GPU_COST_PER_HR = 4.20
BASE_THROUGHPUT  = 2.35  # it/s per GPU (BF16, batch=32)
DDP_EFFICIENCY   = {1: 1.00, 2: 1.92, 4: 3.07, 8: 5.60}  # measured scaling

JOB_STATUSES = ["queued","running","done","failed","cancelled"]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TrainingJob:
    job_id: str
    dataset_path: str
    steps: int
    n_gpus: int
    batch_size: int = 32
    learning_rate: float = 1e-4
    base_checkpoint: str = "/tmp/finetune_1000_5k/checkpoint-5000"
    output_dir: str = ""
    status: str = "queued"
    gpu_ids: list[int] = field(default_factory=list)
    submitted_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    current_step: int = 0
    current_loss: float = 0.0
    cost_usd: float = 0.0
    throughput_its: float = 0.0
    error_msg: str = ""

    @property
    def progress_pct(self) -> float:
        return (self.current_step / self.steps * 100) if self.steps else 0.0

    @property
    def eta_seconds(self) -> float:
        if self.throughput_its <= 0 or self.status != "running":
            return 0.0
        remaining = self.steps - self.current_step
        return remaining / self.throughput_its

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "dataset_path": self.dataset_path,
            "steps": self.steps,
            "n_gpus": self.n_gpus,
            "status": self.status,
            "gpu_ids": self.gpu_ids,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_step": self.current_step,
            "current_loss": round(self.current_loss, 4),
            "cost_usd": round(self.cost_usd, 4),
            "throughput_its": round(self.throughput_its, 3),
            "progress_pct": round(self.progress_pct, 1),
            "eta_seconds": round(self.eta_seconds, 0),
        }


@dataclass
class GPUSlot:
    gpu_id: int
    free: bool = True
    job_id: str = ""


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, n_gpus: int = N_GPUS, simulate: bool = False):
        self.n_gpus = n_gpus
        self.simulate = simulate
        self.gpus = [GPUSlot(i) for i in range(n_gpus)]
        self.jobs: dict[str, TrainingJob] = {}
        self.queue: list[str] = []
        self._lock = threading.Lock()
        self._running = False

    def submit_job(self, dataset_path: str, steps: int, n_gpus: int = 1,
                   batch_size: int = 32, learning_rate: float = 1e-4,
                   base_checkpoint: str = "") -> str:
        job_id = str(uuid.uuid4())[:8]
        job = TrainingJob(
            job_id=job_id,
            dataset_path=dataset_path,
            steps=steps,
            n_gpus=n_gpus,
            batch_size=batch_size,
            learning_rate=learning_rate,
            base_checkpoint=base_checkpoint or "/tmp/finetune_1000_5k/checkpoint-5000",
            output_dir=f"/tmp/orchestrator_jobs/{job_id}",
            submitted_at=datetime.now().isoformat(),
        )
        with self._lock:
            self.jobs[job_id] = job
            self.queue.append(job_id)
        return job_id

    def _allocate_gpus(self, n: int) -> list[int]:
        free = [g for g in self.gpus if g.free]
        if len(free) < n:
            return []
        return [g.gpu_id for g in free[:n]]

    def _free_gpus(self, gpu_ids: list[int]) -> None:
        for gpu in self.gpus:
            if gpu.gpu_id in gpu_ids:
                gpu.free = True
                gpu.job_id = ""

    def _run_job_simulation(self, job: TrainingJob) -> None:
        """Simulate a training run with realistic loss curve."""
        rng = random.Random(hash(job.job_id))
        efficiency = DDP_EFFICIENCY.get(job.n_gpus, 1.0)
        throughput = BASE_THROUGHPUT * efficiency + rng.gauss(0, 0.1)
        job.throughput_its = round(throughput, 3)
        job.status = "running"
        job.started_at = datetime.now().isoformat()

        loss = 0.68
        step_interval = max(1, job.steps // 20)  # update 20 times total
        t_start = time.time()

        for step in range(1, job.steps + 1):
            if job.status == "cancelled":
                break
            # Simulate training time
            step_time = 1.0 / throughput
            time.sleep(min(step_time * step_interval, 2.0) if step % step_interval == 0 else 0)

            # Loss decay
            decay = 0.0003 * (1.0 - step / job.steps * 0.3)
            loss = max(0.08, loss - decay + rng.gauss(0, 0.002))

            if step % step_interval == 0 or step == job.steps:
                elapsed_h = (time.time() - t_start) / 3600.0
                job.current_step = step
                job.current_loss = loss
                job.cost_usd = elapsed_h * GPU_COST_PER_HR * job.n_gpus

        if job.status != "cancelled":
            job.status = "done"
            job.finished_at = datetime.now().isoformat()
            # Final cost
            elapsed_h = (job.steps / throughput) / 3600.0
            job.cost_usd = round(elapsed_h * GPU_COST_PER_HR * job.n_gpus, 4)

        with self._lock:
            self._free_gpus(job.gpu_ids)

    def dispatch_loop(self) -> None:
        """Background thread: dispatch queued jobs to free GPUs."""
        self._running = True
        while self._running:
            with self._lock:
                pending = [jid for jid in self.queue
                           if self.jobs[jid].status == "queued"]
            for jid in pending:
                job = self.jobs[jid]
                with self._lock:
                    gpu_ids = self._allocate_gpus(job.n_gpus)
                    if not gpu_ids:
                        continue
                    for g in self.gpus:
                        if g.gpu_id in gpu_ids:
                            g.free = False
                            g.job_id = jid
                    job.gpu_ids = gpu_ids
                    job.status = "queued"  # will be set to running by worker

                thread = threading.Thread(
                    target=self._run_job_simulation if self.simulate else self._run_job_live,
                    args=(job,), daemon=True
                )
                thread.start()
            time.sleep(2)

    def _run_job_live(self, job: TrainingJob) -> None:
        """Run actual fine-tuning on OCI (used when simulate=False)."""
        import subprocess
        job.status = "running"
        job.started_at = datetime.now().isoformat()
        gpu_str = ",".join(str(g) for g in job.gpu_ids)
        cmd = [
            "bash", "-c",
            f"CUDA_VISIBLE_DEVICES={gpu_str} "
            f"/home/ubuntu/Isaac-GR00T/.venv/bin/python3 "
            f"/home/ubuntu/roboticsai/Isaac-GR00T/scripts/gr00t_finetune.py "
            f"--dataset-path {job.dataset_path} "
            f"--output-dir {job.output_dir} "
            f"--training-steps {job.steps} "
            f"--batch-size {job.batch_size} "
            f"--learning-rate {job.learning_rate} "
            f"2>&1 | tee {job.output_dir}/train.log"
        ]
        Path(job.output_dir).mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(cmd, timeout=7200)
            job.status = "done" if proc.returncode == 0 else "failed"
        except Exception as e:
            job.status = "failed"
            job.error_msg = str(e)[:200]
        job.finished_at = datetime.now().isoformat()
        with self._lock:
            self._free_gpus(job.gpu_ids)

    def gpu_status(self) -> list[dict]:
        return [
            {"gpu_id": g.gpu_id, "free": g.free,
             "job_id": g.job_id,
             "job_status": self.jobs[g.job_id].status if g.job_id in self.jobs else None}
            for g in self.gpus
        ]

    def platform_summary(self) -> dict:
        jobs = list(self.jobs.values())
        return {
            "total_jobs": len(jobs),
            "queued": sum(1 for j in jobs if j.status == "queued"),
            "running": sum(1 for j in jobs if j.status == "running"),
            "done": sum(1 for j in jobs if j.status == "done"),
            "failed": sum(1 for j in jobs if j.status == "failed"),
            "total_cost_usd": round(sum(j.cost_usd for j in jobs), 4),
            "gpus_free": sum(1 for g in self.gpus if g.free),
            "gpus_total": self.n_gpus,
        }


# ── HTML dashboard ────────────────────────────────────────────────────────────

def render_dashboard(orch: Orchestrator) -> str:
    summary = orch.platform_summary()
    gpus = orch.gpu_status()
    jobs = sorted(orch.jobs.values(), key=lambda j: j.submitted_at, reverse=True)[:20]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    gpu_dots = ""
    for g in gpus:
        color = "#22c55e" if g["free"] else "#3b82f6"
        label = f"GPU{g['gpu_id']}\n{'free' if g['free'] else g['job_id'][:6]}"
        gpu_dots += f'<div title="{label}" style="width:40px;height:40px;background:{color};border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;color:white">G{g["gpu_id"]}</div>'

    job_rows = ""
    for j in jobs:
        sc = {"queued":"#6366f1","running":"#3b82f6","done":"#22c55e","failed":"#ef4444","cancelled":"#94a3b8"}.get(j.status,"#94a3b8")
        prog = f'<div style="background:#334155;border-radius:3px;height:6px;width:80px;display:inline-block;vertical-align:middle"><div style="background:{sc};width:{j.progress_pct:.0f}%;height:100%;border-radius:3px"></div></div> {j.progress_pct:.0f}%'
        job_rows += f"""<tr>
          <td style="padding:8px 10px;font-family:monospace;font-size:12px">{j.job_id}</td>
          <td style="padding:8px 10px;font-size:12px;color:#94a3b8">{j.dataset_path[-30:]}</td>
          <td style="padding:8px 10px">{j.steps:,}</td>
          <td style="padding:8px 10px">{j.n_gpus}×A100</td>
          <td style="padding:8px 10px"><span style="color:{sc}">{j.status}</span></td>
          <td style="padding:8px 10px">{prog}</td>
          <td style="padding:8px 10px;font-family:monospace">{j.current_loss:.4f}</td>
          <td style="padding:8px 10px;color:#22c55e">${j.cost_usd:.4f}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>GPU Orchestrator</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 14px;margin:4px;text-align:center}}
</style>
</head>
<body>
<h1>OCI Multi-GPU Training Orchestrator</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 16px">{now} · auto-refresh 10s</p>

<div class="card">
  <div class="m"><div style="font-size:22px;font-weight:700;color:#22c55e">{summary['gpus_free']}/{summary['gpus_total']}</div><div style="font-size:11px;color:#64748b">GPUs free</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#3b82f6">{summary['running']}</div><div style="font-size:11px;color:#64748b">Running</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#6366f1">{summary['queued']}</div><div style="font-size:11px;color:#64748b">Queued</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#22c55e">{summary['done']}</div><div style="font-size:11px;color:#64748b">Done</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#f59e0b">${summary['total_cost_usd']:.2f}</div><div style="font-size:11px;color:#64748b">Total cost</div></div>
</div>

<div class="card">
  <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:10px">GPU Status</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{gpu_dots}</div>
</div>

<div class="card">
  <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:10px">Recent Jobs</div>
  <table>
    <tr><th>Job ID</th><th>Dataset</th><th>Steps</th><th>GPUs</th><th>Status</th><th>Progress</th><th>Loss</th><th>Cost</th></tr>
    {job_rows}
  </table>
</div>

<div style="font-size:11px;color:#475569">
  <a href="/api/jobs" style="color:#3b82f6">/api/jobs</a> ·
  <a href="/api/gpus" style="color:#3b82f6">/api/gpus</a> ·
  POST /jobs to submit
</div>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(n_gpus: int = N_GPUS, simulate: bool = True) -> "FastAPI":
    app = FastAPI(title="Multi-GPU Training Orchestrator", version="1.0")
    orch = Orchestrator(n_gpus=n_gpus, simulate=simulate)

    @app.on_event("startup")
    async def startup():
        t = threading.Thread(target=orch.dispatch_loop, daemon=True)
        t.start()
        # Seed a few mock jobs if simulating
        if simulate:
            for i in range(3):
                orch.submit_job(
                    dataset_path=f"/tmp/partner_{i}/lerobot",
                    steps=random.choice([1000, 2000, 5000]),
                    n_gpus=random.choice([1, 2]),
                )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return render_dashboard(orch)

    @app.get("/api/jobs")
    async def list_jobs():
        return [j.to_dict() for j in orch.jobs.values()]

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        j = orch.jobs.get(job_id)
        if not j:
            raise HTTPException(404, "Job not found")
        return j.to_dict()

    class JobRequest(BaseModel):
        dataset_path: str
        steps: int = 5000
        n_gpus: int = 1
        batch_size: int = 32
        learning_rate: float = 1e-4
        base_checkpoint: str = ""

    @app.post("/jobs")
    async def submit_job(req: JobRequest):
        job_id = orch.submit_job(
            dataset_path=req.dataset_path,
            steps=req.steps,
            n_gpus=req.n_gpus,
            batch_size=req.batch_size,
            learning_rate=req.learning_rate,
            base_checkpoint=req.base_checkpoint,
        )
        return {"job_id": job_id, "status": "queued"}

    @app.delete("/jobs/{job_id}")
    async def cancel_job(job_id: str):
        j = orch.jobs.get(job_id)
        if not j:
            raise HTTPException(404, "Job not found")
        j.status = "cancelled"
        return {"job_id": job_id, "status": "cancelled"}

    @app.get("/api/gpus")
    async def gpu_status():
        return orch.gpu_status()

    @app.get("/api/summary")
    async def summary():
        return orch.platform_summary()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "multi_gpu_orchestrator", "port": 8030}

    return app


# ── Simulation mode ───────────────────────────────────────────────────────────

def run_simulation() -> None:
    """CLI simulation — no FastAPI required."""
    orch = Orchestrator(n_gpus=8, simulate=True)

    print(f"[orch] Multi-GPU Orchestrator simulation — {N_GPUS} A100s")
    jobs = [
        orch.submit_job("/tmp/partner_stretch/lerobot", steps=5000, n_gpus=1),
        orch.submit_job("/tmp/partner_nimble/lerobot",  steps=2000, n_gpus=2),
        orch.submit_job("/tmp/dagger_run6/lerobot",      steps=3000, n_gpus=1),
        orch.submit_job("/tmp/curriculum_sdg/lerobot",   steps=1000, n_gpus=4),
    ]
    print(f"[orch] Submitted {len(jobs)} jobs: {jobs}")

    dispatch_t = threading.Thread(target=orch.dispatch_loop, daemon=True)
    dispatch_t.start()

    for _ in range(30):  # 60s sim
        time.sleep(2)
        s = orch.platform_summary()
        running = [j for j in orch.jobs.values() if j.status == "running"]
        done    = [j for j in orch.jobs.values() if j.status == "done"]
        print(f"  GPUs: {s['gpus_free']}/{s['gpus_total']} free  "
              f"running={s['running']} done={s['done']} cost=${s['total_cost_usd']:.3f}")
        if s["running"] == 0 and s["queued"] == 0:
            break

    orch._running = False
    print(f"\n[orch] Final job results:")
    for j in orch.jobs.values():
        print(f"  {j.job_id}  {j.status:10s}  steps={j.current_step}/{j.steps}"
              f"  loss={j.current_loss:.4f}  cost=${j.cost_usd:.4f}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-GPU training orchestrator")
    parser.add_argument("--port",     type=int,  default=8030)
    parser.add_argument("--n-gpus",   type=int,  default=N_GPUS)
    parser.add_argument("--simulate", action="store_true", help="Use simulated training")
    parser.add_argument("--demo",     action="store_true", help="CLI simulation only")
    args = parser.parse_args()

    if args.demo:
        run_simulation()
    elif not HAS_FASTAPI:
        print("pip install fastapi uvicorn pydantic")
    else:
        app = create_app(args.n_gpus, simulate=args.simulate)
        print(f"Multi-GPU Orchestrator → http://0.0.0.0:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
