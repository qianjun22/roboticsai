"""
OCI Robot Cloud — Python client
================================
High-level interface for training jobs, monitoring, and Jetson deployment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class TrainJob:
    job_id: str
    task: str
    robot: str
    status: str = "submitted"
    created_at: str = ""


@dataclass
class TrainResult:
    job_id: str
    status: str
    metrics: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    checkpoint_url: str = ""
    report_url: str = ""


@dataclass
class JetsonPackage:
    job_id: str
    download_url: str
    size_mb: float
    instructions: str = ""


@dataclass
class PricingInfo:
    cost_per_hour: float
    cost_per_10k_steps: float
    gpu: str
    region: str = "us-chicago-1"


# ── Client ─────────────────────────────────────────────────────────────────────

class RobotCloudClient:
    """
    Client for the OCI Robot Cloud API.

    Parameters
    ----------
    endpoint : str
        API base URL (e.g. "https://robotcloud.oci.oraclecloud.com").
    api_key : str
        Your OCI Robot Cloud API key.
    timeout : int
        HTTP timeout in seconds (default 60).
    """

    SUPPORTED_ROBOTS = ("franka", "ur5e", "kinova_gen3", "xarm7")

    def __init__(
        self,
        endpoint: str = "http://localhost:8080",
        api_key: str = "",
        timeout: int = 60,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["X-API-Key"] = api_key

    # ── Internal ────────────────────────────────────────────────────────────────

    def _get(self, path: str) -> dict:
        r = self._session.get(f"{self.endpoint}{path}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, **kwargs) -> dict:
        r = self._session.post(f"{self.endpoint}{path}", timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r.json()

    # ── Public API ─────────────────────────────────────────────────────────────

    def pricing(self) -> PricingInfo:
        """Return current pricing for OCI Robot Cloud compute."""
        data = self._get("/pricing")
        return PricingInfo(**data)

    def train(
        self,
        task: str,
        robot: str = "franka",
        data_path: Optional[str] = None,
        num_demos: int = 100,
        max_steps: int = 2000,
    ) -> TrainJob:
        """
        Submit a fine-tuning job.

        Parameters
        ----------
        task : str
            Natural language task description.
        robot : str
            Robot embodiment: "franka", "ur5e", "kinova_gen3", or "xarm7".
        data_path : str, optional
            Local directory containing episode subdirectories. If provided,
            episodes are uploaded before training starts.
        num_demos : int
            Number of demonstration episodes to use.
        max_steps : int
            Training steps (2000 = ~14 min on single A100).
        """
        if robot not in self.SUPPORTED_ROBOTS:
            raise ValueError(f"Unsupported robot '{robot}'. Choose from: {self.SUPPORTED_ROBOTS}")

        if data_path is not None:
            self._upload_episodes(data_path, task, robot)

        payload = {
            "task": task,
            "robot": robot,
            "num_demos": num_demos,
            "max_steps": max_steps,
        }
        data = self._post("/jobs/train", json=payload)
        return TrainJob(
            job_id=data["job_id"],
            task=task,
            robot=robot,
            status=data.get("status", "submitted"),
            created_at=data.get("created_at", ""),
        )

    def status(self, job_id: str) -> dict:
        """Return current status dict for a job."""
        return self._get(f"/jobs/{job_id}/status")

    def wait(
        self,
        job_id: str,
        poll_interval: int = 30,
        timeout_minutes: int = 60,
    ) -> TrainResult:
        """
        Block until job completes or fails.

        Parameters
        ----------
        poll_interval : int
            Seconds between status polls (default 30).
        timeout_minutes : int
            Maximum wait time (default 60 min).
        """
        deadline = time.time() + timeout_minutes * 60
        while time.time() < deadline:
            s = self.status(job_id)
            st = s.get("status", "")
            if st == "completed":
                return TrainResult(
                    job_id=job_id,
                    status="completed",
                    metrics=s.get("metrics", {}),
                    cost_usd=s.get("cost_usd", 0.0),
                    checkpoint_url=s.get("checkpoint_url", ""),
                    report_url=s.get("report_url", ""),
                )
            if st in ("failed", "error"):
                raise RuntimeError(f"Job {job_id} failed: {s.get('error', 'unknown error')}")
            print(f"[{job_id}] status={st} step={s.get('step', '?')}/{s.get('max_steps', '?')} "
                  f"loss={s.get('loss', '?')}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout_minutes} minutes")

    def deploy_to_jetson(self, job_id: str) -> JetsonPackage:
        """
        Package a trained checkpoint for Jetson AGX Orin deployment.

        Returns a signed OCI Object Storage download URL.
        """
        data = self._post(f"/jobs/{job_id}/deploy")
        return JetsonPackage(
            job_id=job_id,
            download_url=data["download_url"],
            size_mb=data.get("size_mb", 0.0),
            instructions=data.get("instructions", ""),
        )

    def results(self, job_id: str) -> TrainResult:
        """Fetch final results for a completed job."""
        data = self._get(f"/jobs/{job_id}/results")
        return TrainResult(
            job_id=job_id,
            status=data.get("status", "completed"),
            metrics=data.get("metrics", {}),
            cost_usd=data.get("cost_usd", 0.0),
            checkpoint_url=data.get("checkpoint_url", ""),
            report_url=data.get("report_url", ""),
        )

    # ── Data upload ─────────────────────────────────────────────────────────────

    def _upload_episodes(self, data_path: str, task: str, robot: str) -> int:
        """Upload episodes from local directory. Returns number of episodes uploaded."""
        root = Path(data_path)
        episodes = sorted(root.glob("episode_*"))
        if not episodes:
            raise FileNotFoundError(f"No episode_* directories found in {data_path}")

        print(f"[upload] Uploading {len(episodes)} episodes from {data_path}...")
        uploaded = 0
        for ep_dir in episodes:
            rgb_file = ep_dir / "rgb.npy"
            joints_file = ep_dir / "joint_states.npy"
            if not rgb_file.exists() or not joints_file.exists():
                print(f"[upload] Skipping {ep_dir.name} — missing rgb.npy or joint_states.npy")
                continue
            with rgb_file.open("rb") as rf, joints_file.open("rb") as jf:
                self._post(
                    f"/datasets/{task}/episodes",
                    files={
                        "rgb_frames": (rgb_file.name, rf, "application/octet-stream"),
                        "joint_states": (joints_file.name, jf, "application/octet-stream"),
                    },
                    data={"instruction": task, "robot": robot},
                )
            uploaded += 1

        print(f"[upload] Done — {uploaded}/{len(episodes)} episodes uploaded")
        return uploaded
