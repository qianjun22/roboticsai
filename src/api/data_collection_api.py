#!/usr/bin/env python3
"""
Online Data Collection API — OCI Robot Cloud.

REST API for design partners to upload robot demonstrations directly to OCI
for automated pipeline processing (validate → convert → fine-tune → deploy).

Endpoints:
  POST /datasets/{name}/episodes   — upload a single robot episode (multipart)
  GET  /datasets                   — list all datasets
  GET  /datasets/{name}            — dataset status (episode count, quality score)
  POST /datasets/{name}/finetune   — trigger fine-tuning job on uploaded data
  GET  /datasets/{name}/quality    — run dataset quality inspector
  DELETE /datasets/{name}          — delete dataset and all episodes

Episode upload format (multipart/form-data):
  - rgb_frames: .npy file (T, 256, 256, 3) uint8
  - joint_states: .npy file (T, 9) float32
  - instruction: string (task description)
  - robot: string (franka|ur5e|kinova_gen3|xarm7)

Usage:
    uvicorn data_collection_api:app --host 0.0.0.0 --port 8003

OCI start command:
    CUDA_VISIBLE_DEVICES=4 uvicorn src.api.data_collection_api:app --host 0.0.0.0 --port 8003
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import JSONResponse, HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("[data-api] fastapi not available — install with: pip install fastapi uvicorn")

STORAGE_ROOT = Path(os.environ.get("DATA_STORAGE_ROOT", "/tmp/oci_robot_data"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

SUPPORTED_ROBOTS = {"franka", "ur5e", "kinova_gen3", "xarm7"}

# ── Quality checks ────────────────────────────────────────────────────────────

def quick_quality_check(rgb: np.ndarray, joints: np.ndarray) -> dict:
    """Fast quality assessment for an uploaded episode."""
    issues = []
    T = len(rgb)

    # Length check
    if T < 20:
        issues.append(f"Episode too short: {T} frames (min 20)")
    if T > 500:
        issues.append(f"Episode too long: {T} frames (max 500)")

    # Frame size check
    if rgb.shape[1:3] != (256, 256):
        issues.append(f"Wrong frame size: {rgb.shape[1:3]} (expected 256×256)")

    # Joint range check (Franka limits)
    arm = joints[:, :7]
    LIMITS = [(-2.9, 2.9), (-1.8, 1.8), (-2.9, 2.9), (-3.1, -0.07),
              (-2.9, 2.9), (-0.02, 3.75), (-2.9, 2.9)]
    for j, (lo, hi) in enumerate(LIMITS):
        if np.any(arm[:, j] < lo) or np.any(arm[:, j] > hi):
            issues.append(f"Joint {j+1} out of Franka limits")

    # Diversity check (not all frames identical)
    if rgb.std() < 5.0:
        issues.append("Images appear nearly identical — low diversity")

    # Motion check (at least some arm movement)
    arm_range = arm.max(axis=0) - arm.min(axis=0)
    if arm_range.max() < 0.05:
        issues.append("Minimal arm motion detected — static episode?")

    score = max(0, 100 - len(issues) * 25)
    return {
        "frames": T,
        "quality_score": score,
        "issues": issues,
        "passed": len(issues) == 0,
    }


def dataset_summary(dataset_dir: Path) -> dict:
    """Summarize a dataset from its episode directories."""
    episodes = sorted(dataset_dir.glob("episode_*/metadata.json"))
    if not episodes:
        return {"episode_count": 0, "status": "empty"}

    metas = [json.loads(p.read_text()) for p in episodes]
    quality_scores = [m.get("quality_score", 0) for m in metas]

    return {
        "episode_count": len(episodes),
        "avg_quality_score": round(np.mean(quality_scores), 1),
        "min_quality_score": min(quality_scores),
        "robot": metas[0].get("robot", "unknown"),
        "instruction": metas[0].get("instruction", ""),
        "total_frames": sum(m.get("frames", 0) for m in metas),
        "created_at": metas[0].get("uploaded_at", ""),
        "last_updated": metas[-1].get("uploaded_at", ""),
        "ready_for_finetune": all(m.get("quality_score", 0) >= 50 for m in metas),
    }


# ── FastAPI app ───────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Data Collection API",
        description="Upload robot demonstrations for automated GR00T fine-tuning on OCI A100",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        datasets = list_all_datasets()
        rows = "\n".join(
            f"<tr><td>{d['name']}</td><td>{d['episode_count']}</td>"
            f"<td>{d['avg_quality_score']}</td><td>{d['robot']}</td></tr>"
            for d in datasets
        )
        return f"""<!DOCTYPE html>
<html>
<head><title>OCI Robot Cloud — Data Collection</title>
<style>body{{font-family:monospace;background:#0f0f0f;color:#e5e7eb;padding:32px}}
h1{{color:#C74634}}table{{border-collapse:collapse;width:100%}}
th{{background:#1a1a1a;padding:8px 12px;text-align:left;color:#9CA3AF}}
td{{padding:8px 12px;border-top:1px solid #1f1f1f}}</style></head>
<body>
<h1>OCI Robot Cloud — Data Collection API</h1>
<p>Upload robot demonstrations for automated GR00T fine-tuning.</p>
<h2>Datasets ({len(datasets)} total)</h2>
<table><thead><tr><th>Name</th><th>Episodes</th><th>Avg Quality</th><th>Robot</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan=4>No datasets yet</td></tr>'}</tbody></table>
<p style="color:#6B7280;margin-top:24px">API docs: <a href="/docs" style="color:#C74634">/docs</a></p>
</body></html>"""

    def list_all_datasets() -> list:
        result = []
        for d in sorted(STORAGE_ROOT.iterdir()):
            if d.is_dir():
                s = dataset_summary(d)
                s["name"] = d.name
                result.append(s)
        return result

    @app.get("/datasets")
    async def get_datasets():
        """List all datasets with episode counts and quality scores."""
        return {"datasets": list_all_datasets(), "storage_root": str(STORAGE_ROOT)}

    @app.get("/datasets/{dataset_name}")
    async def get_dataset(dataset_name: str):
        """Get status and metadata for a specific dataset."""
        dataset_dir = STORAGE_ROOT / dataset_name
        if not dataset_dir.exists():
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found")
        summary = dataset_summary(dataset_dir)
        summary["name"] = dataset_name
        return summary

    @app.post("/datasets/{dataset_name}/episodes")
    async def upload_episode(
        dataset_name: str,
        rgb_frames: UploadFile = File(..., description="RGB frames (T, 256, 256, 3) uint8 as .npy"),
        joint_states: UploadFile = File(..., description="Joint states (T, 9) float32 as .npy"),
        instruction: str = Form(..., description="Task instruction string"),
        robot: str = Form("franka", description="Robot type: franka|ur5e|kinova_gen3|xarm7"),
    ):
        """
        Upload a single robot demonstration episode.

        Returns quality assessment and episode ID.
        """
        if robot not in SUPPORTED_ROBOTS:
            raise HTTPException(status_code=400, detail=f"Unsupported robot: {robot}. Use: {SUPPORTED_ROBOTS}")

        # Load uploaded arrays
        try:
            rgb_bytes = await rgb_frames.read()
            jnt_bytes = await joint_states.read()
            rgb = np.frombuffer(rgb_bytes, dtype=np.uint8)
            jnt = np.frombuffer(jnt_bytes, dtype=np.float32)

            # Reshape: try to infer T from size
            if len(rgb) % (256 * 256 * 3) != 0:
                raise ValueError(f"RGB size {len(rgb)} not divisible by 256*256*3")
            T = len(rgb) // (256 * 256 * 3)
            rgb = rgb.reshape(T, 256, 256, 3)

            arm_dof = {"franka": 7, "ur5e": 6, "kinova_gen3": 7, "xarm7": 7}[robot]
            expected_jnt = T * (arm_dof + 2)
            if len(jnt) != expected_jnt:
                raise ValueError(f"Joint states size {len(jnt)} != expected {expected_jnt} (T={T}, dof={arm_dof+2})")
            jnt = jnt.reshape(T, arm_dof + 2)

            # Pad UR5e from 8 to 9 DOF for Franka compatibility
            if arm_dof == 6:
                jnt = np.concatenate([jnt, np.zeros((T, 1), dtype=np.float32)], axis=-1)

        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid data format: {e}")

        # Quality check
        quality = quick_quality_check(rgb, jnt)

        # Save episode
        dataset_dir = STORAGE_ROOT / dataset_name
        n_existing = len(list(dataset_dir.glob("episode_*")))
        episode_id = n_existing
        ep_dir = dataset_dir / f"episode_{episode_id:06d}"
        ep_dir.mkdir(parents=True, exist_ok=True)

        np.save(ep_dir / "rgb.npy", rgb)
        np.save(ep_dir / "joint_states.npy", jnt)
        np.save(ep_dir / "arm_states.npy", jnt[:, :7])
        np.save(ep_dir / "gripper_states.npy", jnt[:, 7:9])

        meta = {
            "episode_id": episode_id,
            "dataset": dataset_name,
            "robot": robot,
            "instruction": instruction,
            "frames": T,
            "quality_score": quality["quality_score"],
            "quality_issues": quality["issues"],
            "uploaded_at": datetime.now().isoformat(),
        }
        (ep_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

        return {
            "episode_id": episode_id,
            "dataset": dataset_name,
            "frames": T,
            "quality": quality,
            "message": (
                "Episode uploaded. Trigger fine-tuning with POST /datasets/{name}/finetune"
                if n_existing + 1 >= 10 else
                f"Episode saved. Need {10 - n_existing - 1} more episodes before fine-tuning."
            ),
        }

    @app.post("/datasets/{dataset_name}/finetune")
    async def trigger_finetune(
        dataset_name: str,
        max_steps: int = Form(2000, description="Fine-tuning steps"),
        gpu_id: int = Form(0, description="GPU device index"),
    ):
        """Trigger GR00T fine-tuning on this dataset via the Robot Cloud API."""
        import subprocess

        dataset_dir = STORAGE_ROOT / dataset_name
        if not dataset_dir.exists():
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found")

        summary = dataset_summary(dataset_dir)
        if summary["episode_count"] < 5:
            raise HTTPException(
                status_code=400,
                detail=f"Too few episodes: {summary['episode_count']} (min 5)"
            )
        if not summary["ready_for_finetune"]:
            raise HTTPException(
                status_code=400,
                detail="Some episodes have quality score < 50. Check /datasets/{name}/quality"
            )

        # Convert to LeRobot v2 format and submit to fine-tuning
        converted_dir = Path(f"/tmp/lerobot_{dataset_name}")
        output_checkpoint = Path(f"/tmp/finetune_{dataset_name}")
        job_id = f"finetune_{dataset_name}_{int(time.time())}"

        # Background subprocess — non-blocking
        cmd = [
            "bash", "-c",
            f"python3 {Path(__file__).parents[1]}/training/genesis_to_lerobot.py "
            f"--input {dataset_dir} --output {converted_dir} --fps 20 && "
            f"CUDA_VISIBLE_DEVICES={gpu_id} python3 {Path(__file__).parents[1]}/training/launch_finetune.py "
            f"--dataset {converted_dir} --output-dir {output_checkpoint} "
            f"--max-steps {max_steps} > /tmp/{job_id}.log 2>&1"
        ]
        proc = subprocess.Popen(cmd, start_new_session=True)

        return {
            "job_id": job_id,
            "status": "started",
            "pid": proc.pid,
            "dataset": dataset_name,
            "episodes": summary["episode_count"],
            "max_steps": max_steps,
            "log": f"/tmp/{job_id}.log",
            "checkpoint_output": str(output_checkpoint),
            "message": "Fine-tuning started. Poll /datasets/{name} for status.",
        }

    @app.get("/datasets/{dataset_name}/quality")
    async def dataset_quality_report(dataset_name: str):
        """Run full quality analysis on all episodes in dataset."""
        dataset_dir = STORAGE_ROOT / dataset_name
        if not dataset_dir.exists():
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found")

        episodes = sorted(dataset_dir.glob("episode_*/metadata.json"))
        per_episode = [json.loads(p.read_text()) for p in episodes]

        scores = [m.get("quality_score", 0) for m in per_episode]
        all_issues: list = []
        for m in per_episode:
            all_issues.extend(m.get("quality_issues", []))

        from collections import Counter
        issue_counts = dict(Counter(all_issues).most_common(10))

        return {
            "dataset": dataset_name,
            "episode_count": len(per_episode),
            "avg_quality_score": round(np.mean(scores), 1) if scores else 0,
            "episodes_passing": sum(1 for s in scores if s >= 75),
            "episodes_warning": sum(1 for s in scores if 50 <= s < 75),
            "episodes_failing": sum(1 for s in scores if s < 50),
            "common_issues": issue_counts,
            "recommendation": (
                "Ready for fine-tuning" if all(s >= 50 for s in scores) else
                "Fix failing episodes before fine-tuning"
            ),
        }

    @app.delete("/datasets/{dataset_name}")
    async def delete_dataset(dataset_name: str, confirm: bool = Form(False)):
        """Delete a dataset and all its episodes (requires confirm=true)."""
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="Pass confirm=true to delete a dataset. This is irreversible."
            )
        dataset_dir = STORAGE_ROOT / dataset_name
        if not dataset_dir.exists():
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found")

        n_episodes = len(list(dataset_dir.glob("episode_*")))
        shutil.rmtree(dataset_dir)
        return {"deleted": dataset_name, "episodes_removed": n_episodes}


# ── Standalone server ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_FASTAPI:
        print("Install: pip install fastapi uvicorn")
        import sys; sys.exit(1)

    import uvicorn
    print("[data-api] OCI Robot Cloud Data Collection API")
    print(f"[data-api] Storage: {STORAGE_ROOT}")
    print("[data-api] Docs: http://localhost:8003/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8003)
