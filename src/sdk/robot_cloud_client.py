"""
OCI Robot Cloud — Python Client SDK
=====================================
Simple client for the OCI Robot Cloud API.
Design-partner customers use this to submit training jobs and retrieve results.

Usage:
    pip install requests
    from src.sdk.robot_cloud_client import RobotCloudClient

    client = RobotCloudClient("https://robot-cloud.oci.example.com")

    # Submit a training job
    job = client.train(
        task_description="pick up the red cube from the table",
        num_demos=100,
        train_steps=2000,
    )

    # Poll until complete
    results = client.wait(job["job_id"])
    print(f"MAE: {results['metrics']['mae']:.4f}")
    print(f"Cost: ${results['cost_usd']:.4f}")

    # Package for Jetson
    deploy_info = client.deploy_to_jetson(job["job_id"])
    print(deploy_info["message"])
"""

import time
import requests
from typing import Optional


class RobotCloudClient:
    """Client for OCI Robot Cloud training API."""

    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self._check_health()

    def _check_health(self):
        try:
            r = requests.get(f"{self.base}/health", timeout=5)
            r.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Cannot reach OCI Robot Cloud API at {self.base}: {e}")

    def train(
        self,
        task_description: str = "pick up the red cube from the table",
        num_demos: int = 100,
        train_steps: int = 2000,
        batch_size: int = 32,
        num_gpus: int = 1,
        dataset_url: Optional[str] = None,
    ) -> dict:
        """Submit a fine-tuning job. Returns job dict with job_id."""
        payload = {
            "task_description": task_description,
            "num_demos": num_demos,
            "train_steps": train_steps,
            "batch_size": batch_size,
            "num_gpus": num_gpus,
        }
        if dataset_url:
            payload["dataset_url"] = dataset_url

        r = requests.post(f"{self.base}/jobs/train", json=payload, timeout=self.timeout)
        r.raise_for_status()
        job = r.json()
        print(f"[RobotCloud] Job submitted: {job['job_id']} — {num_demos} demos, {train_steps} steps")
        return job

    def status(self, job_id: str) -> dict:
        """Get current job status."""
        r = requests.get(f"{self.base}/jobs/{job_id}/status", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def results(self, job_id: str) -> dict:
        """Get job results (must be done)."""
        r = requests.get(f"{self.base}/jobs/{job_id}/results", timeout=self.timeout)
        if r.status_code == 202:
            raise RuntimeError(f"Job {job_id} not yet complete")
        r.raise_for_status()
        return r.json()

    def wait(self, job_id: str, poll_interval: int = 15, max_wait_min: int = 60) -> dict:
        """Poll until job is done or failed. Returns results dict."""
        deadline = time.time() + max_wait_min * 60
        while time.time() < deadline:
            s = self.status(job_id)
            print(f"  [{s['status'].upper()}] {s.get('progress', '')}  ({int(time.time() - s['created_at'])}s elapsed)")
            if s["status"] == "done":
                return self.results(job_id)
            if s["status"] == "failed":
                raise RuntimeError(f"Job {job_id} failed: {s.get('error')}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not complete within {max_wait_min} min")

    def deploy_to_jetson(self, job_id: str) -> dict:
        """Package the checkpoint for Jetson AGX Orin deployment."""
        r = requests.post(f"{self.base}/jobs/{job_id}/deploy", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def list_jobs(self, limit: int = 10) -> list:
        """List recent jobs."""
        r = requests.get(f"{self.base}/jobs", params={"limit": limit}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["jobs"]

    def pricing(self) -> dict:
        """Get current OCI pricing info and examples."""
        r = requests.get(f"{self.base}/pricing", timeout=self.timeout)
        r.raise_for_status()
        return r.json()


# ── Example usage ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCI Robot Cloud Client Example")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--task", default="pick up the red cube from the table")
    parser.add_argument("--demos", type=int, default=50)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--gpus", type=int, default=1)
    parser.add_argument("--deploy", action="store_true", help="Package for Jetson after training")
    args = parser.parse_args()

    client = RobotCloudClient(args.url)

    # Show pricing
    pricing = client.pricing()
    print("\n=== OCI Robot Cloud Pricing ===")
    for ex in pricing["example_jobs"]:
        print(f"  {ex['description']}")
        print(f"    ~{ex['estimated_time_min']} min, ${ex['estimated_cost_usd']:.4f}, {ex['expected_mae']}")
    print()

    # Submit training
    job = client.train(
        task_description=args.task,
        num_demos=args.demos,
        train_steps=args.steps,
        num_gpus=args.gpus,
    )

    # Wait for completion
    print(f"\n=== Waiting for job {job['job_id']} ===")
    try:
        results = client.wait(job["job_id"], poll_interval=10, max_wait_min=90)
        m = results.get("metrics", {})
        print(f"\n=== Results ===")
        print(f"  MAE:          {m.get('mae', 'n/a')}")
        print(f"  Steps/sec:    {m.get('steps_per_sec', 'n/a')}")
        print(f"  Samples/sec:  {m.get('samples_per_sec', 'n/a')}")
        print(f"  Cost:         ${results.get('cost_usd', 0):.4f}")
        print(f"  Checkpoint:   {results.get('checkpoint_path', 'n/a')}")

        if args.deploy:
            print("\n=== Packaging for Jetson ===")
            deploy = client.deploy_to_jetson(job["job_id"])
            print(f"  {deploy['message']}")
            print(f"  Package: {deploy['package_path']}")
            print(f"  Expected latency: {deploy['expected_latency_ms']}ms on {deploy['target_hardware']}")

    except Exception as e:
        print(f"\nERROR: {e}")
