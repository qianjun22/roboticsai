"""
OCI Robot Cloud API Service
============================
Customer-facing REST API for the OCI Robot Cloud platform.
Wraps the GR00T fine-tuning pipeline for design-partner use.

Architecture:
  Customer → POST /jobs/train → queued job → OCI A100 fine-tune
             GET  /jobs/{id}/status → {pending|running|done|failed}
             GET  /jobs/{id}/results → MAE, loss, checkpoint URL
             POST /jobs/{id}/deploy → Jetson-ready tarball

Usage (local dev):
  pip install fastapi uvicorn python-multipart aiofiles
  uvicorn src.api.robot_cloud_api:app --reload --port 8080

Usage (OCI A100):
  GPU_ID=4 OUTPUT_BASE=/tmp/robot_cloud uvicorn \
      src.api.robot_cloud_api:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Config ─────────────────────────────────────────────────────────────────
GPU_ID = os.environ.get("GPU_ID", "4")
OUTPUT_BASE = Path(os.environ.get("OUTPUT_BASE", "/tmp/robot_cloud"))
REPO_DIR = Path(os.environ.get("REPO_DIR", Path.home() / "roboticsai"))
MODEL_PATH = Path(os.environ.get("MODEL_PATH", Path.home() / "models/GR00T-N1.6-3B"))
MODALITY_CFG = REPO_DIR / "src/training/franka_config.py"
OCI_COST_PER_GPU_HR = 3.60  # USD

OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

# In-memory job store (production: use Redis or OCI Streaming)
_jobs: dict[str, dict] = {}

# ── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="OCI Robot Cloud API",
    description="Synthetic data generation + GR00T fine-tuning on OCI A100s",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ─────────────────────────────────────────────────────────────────
class TrainRequest(BaseModel):
    task_description: str = Field(
        default="pick up the red cube from the table",
        description="Natural language task description (used as GR00T instruction)",
    )
    num_demos: int = Field(default=100, ge=10, le=1000, description="Number of synthetic demos to generate")
    train_steps: int = Field(default=2000, ge=100, le=20000, description="GR00T fine-tuning steps")
    batch_size: int = Field(default=32, ge=8, le=128)
    num_gpus: int = Field(default=1, ge=1, le=4, description="A100 count (1=single, 4=DDP)")
    dataset_url: Optional[str] = Field(
        default=None,
        description="OCI Object Storage URL for pre-existing LeRobot v2 dataset (skips SDG)",
    )


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending | running | done | failed
    created_at: float
    updated_at: float
    task_description: str
    num_demos: int
    train_steps: int
    progress: Optional[str] = None
    error: Optional[str] = None


class JobResults(BaseModel):
    job_id: str
    status: str
    metrics: Optional[dict] = None
    checkpoint_path: Optional[str] = None
    checkpoint_url: Optional[str] = None
    cost_usd: Optional[float] = None
    wall_time_sec: Optional[int] = None


# ── Background training runner ───────────────────────────────────────────────
def _run_pipeline(job_id: str, req: TrainRequest):
    """Runs in a background thread — executes the full pipeline script."""
    job = _jobs[job_id]
    job_dir = OUTPUT_BASE / job_id

    try:
        job["status"] = "running"
        job["updated_at"] = time.time()

        genesis_out = job_dir / "genesis_sdg"
        lerobot_dir = job_dir / "lerobot_dataset"
        finetune_dir = job_dir / "finetune"
        benchmark_json = job_dir / "benchmark.json"

        job_dir.mkdir(parents=True, exist_ok=True)

        env = {**os.environ, "CUDA_VISIBLE_DEVICES": GPU_ID}

        # ── Step 1: SDG (skip if dataset provided) ──────────────────────────
        if req.dataset_url:
            job["progress"] = "Downloading dataset from OCI..."
            result = subprocess.run(
                ["oci", "os", "object", "get",
                 "--bucket-name", "roboticsai-datasets",
                 "--name", req.dataset_url,
                 "--file", str(lerobot_dir)],
                capture_output=True, text=True, env=env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Dataset download failed: {result.stderr}")
        else:
            job["progress"] = f"Genesis SDG: {req.num_demos} demos..."
            t0 = time.time()
            result = subprocess.run(
                ["python3", str(REPO_DIR / "src/simulation/genesis_sdg_planned.py"),
                 "--num-demos", str(req.num_demos),
                 "--output", str(genesis_out)],
                capture_output=True, text=True, env=env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"SDG failed: {result.stderr[-500:]}")
            sdg_time = int(time.time() - t0)
            job["sdg_time_sec"] = sdg_time

            # Convert to LeRobot v2
            job["progress"] = "Converting to LeRobot v2 format..."
            result = subprocess.run(
                ["python3", str(REPO_DIR / "src/training/genesis_to_lerobot.py"),
                 "--input", str(genesis_out),
                 "--output", str(lerobot_dir),
                 "--task", req.task_description,
                 "--fps", "20"],
                capture_output=True, text=True, env=env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Conversion failed: {result.stderr[-500:]}")

        # ── Step 2: GR00T Fine-Tuning ────────────────────────────────────────
        job["progress"] = f"GR00T fine-tuning: {req.train_steps} steps..."
        t0 = time.time()

        if req.num_gpus > 1:
            # Multi-GPU DDP
            gpu_list = ",".join(str(GPU_ID + i) for i in range(req.num_gpus))
            env["CUDA_VISIBLE_DEVICES"] = gpu_list
            train_cmd = [
                "torchrun", f"--nproc_per_node={req.num_gpus}", "--master_port=29502",
                "gr00t/experiment/launch_finetune.py",
            ]
        else:
            train_cmd = ["python3", "gr00t/experiment/launch_finetune.py"]

        train_cmd += [
            "--base-model-path", str(MODEL_PATH),
            "--dataset-path", str(lerobot_dir),
            "--embodiment-tag", "NEW_EMBODIMENT",
            "--modality-config-path", str(MODALITY_CFG),
            "--num-gpus", str(req.num_gpus),
            "--output-dir", str(finetune_dir),
            "--save-total-limit", "2",
            "--save-steps", str(req.train_steps),
            "--max-steps", str(req.train_steps),
            "--global-batch-size", str(req.batch_size),
            "--dataloader-num-workers", "4",
        ]

        isaac_groot_dir = Path.home() / "Isaac-GR00T"
        result = subprocess.run(
            train_cmd, capture_output=True, text=True, env=env,
            cwd=str(isaac_groot_dir),
        )
        if result.returncode != 0:
            raise RuntimeError(f"Fine-tuning failed: {result.stderr[-500:]}")

        finetune_time = int(time.time() - t0)
        steps_per_sec = round(req.train_steps / max(finetune_time, 1), 2)

        # ── Step 3: Open-Loop Evaluation ────────────────────────────────────
        job["progress"] = "Evaluating checkpoint (open-loop MAE)..."
        checkpoint_path = finetune_dir / f"checkpoint-{req.train_steps}"
        eval_result = subprocess.run(
            ["python3", str(REPO_DIR / "src/training/open_loop_eval.py"),
             "--checkpoint", str(checkpoint_path),
             "--dataset", str(lerobot_dir),
             "--modality-config", str(MODALITY_CFG),
             "--n-trajectories", "5"],
            capture_output=True, text=True, env=env,
        )

        mae = None
        mse = None
        for line in eval_result.stdout.splitlines():
            if "MAE" in line:
                try:
                    mae = float(line.split("MAE")[-1].strip().split()[0])
                except ValueError:
                    pass
            if "MSE" in line:
                try:
                    mse = float(line.split("MSE")[-1].strip().split()[0])
                except ValueError:
                    pass

        # ── Step 4: Benchmark JSON ────────────────────────────────────────────
        samples_per_sec = round(steps_per_sec * req.batch_size, 1)
        cost_usd = round(finetune_time / 3600 * OCI_COST_PER_GPU_HR * req.num_gpus, 4)
        cost_per_10k = round(10000 / max(steps_per_sec, 0.001) / 3600 * OCI_COST_PER_GPU_HR, 4)

        metrics = {
            "mae": mae,
            "mse": mse,
            "steps_per_sec": steps_per_sec,
            "samples_per_sec": samples_per_sec,
            "finetune_wall_time_sec": finetune_time,
            "cost_usd": cost_usd,
            "cost_per_10k_steps_usd": cost_per_10k,
            "num_gpus": req.num_gpus,
            "train_steps": req.train_steps,
            "num_demos": req.num_demos,
            "model": "GR00T-N1.6-3B",
            "hardware": f"OCI A100-SXM4-80GB × {req.num_gpus}",
        }

        with open(benchmark_json, "w") as f:
            json.dump(metrics, f, indent=2)

        job.update({
            "status": "done",
            "updated_at": time.time(),
            "progress": "Complete",
            "metrics": metrics,
            "checkpoint_path": str(checkpoint_path),
            "wall_time_sec": finetune_time,
            "cost_usd": cost_usd,
        })

    except Exception as e:
        job.update({
            "status": "failed",
            "updated_at": time.time(),
            "error": str(e),
        })


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "OCI Robot Cloud API",
        "version": "1.0.0",
        "model": "GR00T-N1.6-3B",
        "hardware": "OCI A100-SXM4-80GB",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "active_jobs": sum(1 for j in _jobs.values() if j["status"] == "running")}


@app.post("/jobs/train", response_model=JobStatus)
async def submit_training_job(req: TrainRequest, background_tasks: BackgroundTasks):
    """Submit a GR00T fine-tuning job. Returns job_id for polling."""
    job_id = str(uuid.uuid4())[:8]
    now = time.time()
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "task_description": req.task_description,
        "num_demos": req.num_demos,
        "train_steps": req.train_steps,
        "progress": "Queued",
        "error": None,
    }
    background_tasks.add_task(_run_pipeline, job_id, req)
    return _jobs[job_id]


@app.get("/jobs/{job_id}/status", response_model=JobStatus)
def get_job_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _jobs[job_id]


@app.get("/jobs/{job_id}/results", response_model=JobResults)
def get_job_results(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    job = _jobs[job_id]
    if job["status"] not in ("done", "failed"):
        raise HTTPException(status_code=202, detail=f"Job {job_id} still {job['status']}")

    return JobResults(
        job_id=job_id,
        status=job["status"],
        metrics=job.get("metrics"),
        checkpoint_path=job.get("checkpoint_path"),
        cost_usd=job.get("cost_usd"),
        wall_time_sec=job.get("wall_time_sec"),
    )


@app.post("/jobs/{job_id}/deploy")
def package_for_jetson(job_id: str):
    """Package the fine-tuned checkpoint for Jetson AGX Orin deployment."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    job = _jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail=f"Job must be 'done', got '{job['status']}'")

    checkpoint = job.get("checkpoint_path")
    if not checkpoint or not Path(checkpoint).exists():
        raise HTTPException(status_code=404, detail="Checkpoint not found on disk")

    package_name = f"groot-{job_id}-jetson.tar.gz"
    package_path = f"/tmp/{package_name}"

    env = {**os.environ, "CHECKPOINT": checkpoint}
    result = subprocess.run(
        ["bash", str(REPO_DIR / "src/inference/jetson_deploy.sh"), "--package"],
        capture_output=True, text=True, env=env,
    )

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Packaging failed: {result.stderr[-500:]}")

    return {
        "job_id": job_id,
        "package_path": package_path,
        "message": "Jetson package ready. Copy to Jetson AGX Orin and run: bash jetson_deploy.sh --install",
        "expected_latency_ms": "400-600",
        "target_hardware": "Jetson AGX Orin (JetPack 6.x)",
    }


@app.get("/jobs")
def list_jobs(limit: int = 20):
    """List recent training jobs."""
    jobs = sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
    return {"jobs": jobs, "total": len(_jobs)}


@app.get("/pricing")
def pricing():
    """OCI Robot Cloud cost calculator."""
    return {
        "oci_a100_per_gpu_hr_usd": OCI_COST_PER_GPU_HR,
        "example_jobs": [
            {
                "description": "Quick pilot (100 demos, 2000 steps, 1 GPU)",
                "estimated_time_min": 15,
                "estimated_cost_usd": round(15 / 60 * OCI_COST_PER_GPU_HR, 4),
                "expected_mae": "~0.013 (8.7× vs random)",
            },
            {
                "description": "Scale run (500 demos, 10k steps, 4 GPU DDP)",
                "estimated_time_min": 45,
                "estimated_cost_usd": round(45 / 60 * OCI_COST_PER_GPU_HR * 4, 4),
                "expected_mae": "~0.008 (estimated)",
            },
        ],
        "vs_dgx": {
                "oci": "$0.0043/10k steps, zero CapEx, burst 1→32 GPU",
                "dgx": "~$0.0045/10k steps (amortized), ~$200k CapEx, fixed 8 GPU",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
