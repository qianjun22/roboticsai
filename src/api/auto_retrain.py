"""
Automated re-training trigger for OCI Robot Cloud.

Watches the design-partner data upload directory and automatically queues
a fine-tuning job when new episodes arrive. Integrates with the robot_cloud_api.py
job queue and training monitor.

Trigger conditions (configurable):
  - N new episodes uploaded (default: 10)
  - Time-based: every 24h if any new data
  - Quality threshold: only trigger if median episode length > min_steps

Workflow:
  1. Design partner uploads demos via data_collection_api.py (port 8003)
  2. auto_retrain.py watches the upload dir for new episodes
  3. When trigger fires: validate quality → convert → launch fine-tune
  4. Notify via webhook (Slack/email) when training starts and completes
  5. Auto-restart GR00T server with new checkpoint

Usage:
    python3 auto_retrain.py \\
        --watch-dir /tmp/uploads \\
        --output-dir /tmp/auto_finetune \\
        --trigger-episodes 10 \\
        --webhook-url https://hooks.slack.com/... \\
        --gpu-id 4

For production on OCI:
    nohup python3 auto_retrain.py --watch-dir /data/uploads &
"""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


# ── State tracking ────────────────────────────────────────────────────────────

class RetrainState:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._load()

    def _load(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                d = json.load(f)
        else:
            d = {}
        self.last_trigger_time = d.get("last_trigger_time", 0)
        self.last_trigger_episode_count = d.get("last_trigger_episode_count", 0)
        self.total_jobs_run = d.get("total_jobs_run", 0)
        self.last_checkpoint = d.get("last_checkpoint", None)

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump({
                "last_trigger_time": self.last_trigger_time,
                "last_trigger_episode_count": self.last_trigger_episode_count,
                "total_jobs_run": self.total_jobs_run,
                "last_checkpoint": self.last_checkpoint,
            }, f, indent=2)


# ── Episode counter ────────────────────────────────────────────────────────────

def count_episodes(watch_dir: Path) -> int:
    """Count valid episode directories in the upload dir."""
    count = 0
    if not watch_dir.exists():
        return 0
    for d in watch_dir.iterdir():
        if d.is_dir():
            has_data = (
                (d / "data.hdf5").exists()
                or (d / "frames.npy").exists()
                or any(d.rglob("*.jpg"))
                or any(d.rglob("*.png"))
            )
            if has_data:
                count += 1
    return count


def validate_episodes(watch_dir: Path, min_steps: int = 30) -> dict:
    """
    Check episode quality. Returns dict with:
      valid_count, invalid_count, median_length, quality_ok
    """
    try:
        import h5py
        HDF5_OK = True
    except ImportError:
        HDF5_OK = False

    lengths = []
    invalid = 0

    for ep_dir in watch_dir.iterdir():
        if not ep_dir.is_dir():
            continue
        hdf5 = ep_dir / "data.hdf5"
        if hdf5.exists() and HDF5_OK:
            try:
                import h5py
                with h5py.File(hdf5) as f:
                    n = f["action"].shape[0] if "action" in f else 0
                    if n >= min_steps:
                        lengths.append(n)
                    else:
                        invalid += 1
            except Exception:
                invalid += 1
        else:
            # Count frames as proxy
            frames = list(ep_dir.rglob("*.jpg")) + list(ep_dir.rglob("*.png"))
            n = len(frames)
            if n >= min_steps:
                lengths.append(n)
            elif n > 0:
                invalid += 1

    if not lengths:
        return {"valid_count": 0, "invalid_count": invalid, "median_length": 0, "quality_ok": False}

    import statistics
    median = statistics.median(lengths)
    return {
        "valid_count": len(lengths),
        "invalid_count": invalid,
        "median_length": median,
        "quality_ok": median >= min_steps and len(lengths) >= 3,
    }


# ── Webhook notification ───────────────────────────────────────────────────────

def send_webhook(webhook_url: Optional[str], message: str):
    if not webhook_url or not REQUESTS_OK:
        return
    try:
        requests.post(webhook_url, json={"text": f"[OCI Robot Cloud] {message}"}, timeout=5)
    except Exception:
        pass


# ── Fine-tune launcher ────────────────────────────────────────────────────────

def launch_finetune(
    watch_dir: Path,
    output_dir: Path,
    job_id: str,
    steps: int,
    gpu_id: int,
    log_file: Path,
    base_model: str = "/tmp/finetune_500_5k/checkpoint-5000",
) -> subprocess.Popen:
    """Launch fine-tuning subprocess. Returns Popen handle."""
    lerobot_dir = output_dir / job_id / "lerobot"
    ckpt_dir = output_dir / job_id / "checkpoint"
    lerobot_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Resolve script paths relative to this file's location
    _here = Path(__file__).resolve().parent
    genesis_to_lerobot = _here.parent / "training" / "genesis_to_lerobot.py"
    groot_repo = Path(os.environ.get("GROOT_REPO", "/home/ubuntu/Isaac-GR00T"))
    launch_finetune_script = groot_repo / "gr00t" / "experiment" / "launch_finetune.py"
    python_bin = groot_repo / ".venv" / "bin" / "python3"
    if not python_bin.exists():
        python_bin = Path("python3")
    franka_cfg = _here.parent / "training" / "franka_config.py"

    # Convert to LeRobot v2 first
    convert_cmd = [
        str(python_bin), str(genesis_to_lerobot),
        "--input", str(watch_dir),
        "--output", str(lerobot_dir),
        "--fps", "20",
    ]
    print(f"[AutoRetrain] Converting episodes to LeRobot v2...")
    result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[AutoRetrain] Convert warning: {result.stderr[:300]}")

    finetune_cmd = [
        str(python_bin), str(launch_finetune_script),
        "--base-model-path", base_model,
        "--dataset-path", str(lerobot_dir),
        "--embodiment-tag", "NEW_EMBODIMENT",
        "--modality-config-path", str(franka_cfg),
        "--max-steps", str(steps),
        "--global-batch-size", "16",
        "--output-dir", str(ckpt_dir),
    ]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    log_f = open(log_file, "w")
    proc = subprocess.Popen(
        finetune_cmd, env=env, stdout=log_f, stderr=subprocess.STDOUT
    )
    print(f"[AutoRetrain] Fine-tune PID {proc.pid} | log: {log_file}")
    return proc


def restart_groot_server(checkpoint_dir: Path, port: int = 8002, gpu_id: int = 4):
    """Kill and restart the GR00T server with new checkpoint."""
    ckpt = sorted(checkpoint_dir.glob("checkpoint-*"))
    if not ckpt:
        print("[AutoRetrain] No checkpoint found — skipping server restart")
        return

    latest = str(ckpt[-1])
    print(f"[AutoRetrain] Restarting GR00T server with {latest}")

    # Kill existing server on port
    subprocess.run(["pkill", "-f", f"groot_franka_server.py.*{port}"], capture_output=True)
    time.sleep(3)

    cmd = [
        "python3", "groot_franka_server.py",
        "--checkpoint", latest,
        "--port", str(port),
    ]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[AutoRetrain] GR00T server restarted on port {port}")


# ── Main watch loop ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud auto re-training trigger")
    parser.add_argument("--watch-dir", required=True, help="Upload directory to watch")
    parser.add_argument("--output-dir", default="/tmp/auto_finetune")
    parser.add_argument("--trigger-episodes", type=int, default=10,
                        help="Trigger fine-tune when N new episodes arrive")
    parser.add_argument("--trigger-interval-hours", type=float, default=24.0,
                        help="Also trigger every N hours if any new data")
    parser.add_argument("--finetune-steps", type=int, default=2000)
    parser.add_argument("--min-episode-steps", type=int, default=30)
    parser.add_argument("--gpu-id", type=int, default=4)
    parser.add_argument("--groot-port", type=int, default=8002)
    parser.add_argument("--webhook-url", default=None,
                        help="Slack/Teams webhook for notifications")
    parser.add_argument("--check-interval-sec", type=int, default=60,
                        help="How often to check for new episodes (seconds)")
    args = parser.parse_args()

    watch_dir = Path(args.watch_dir)
    output_dir = Path(args.output_dir)
    watch_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    state = RetrainState(output_dir / "retrain_state.json")

    print(f"\n[AutoRetrain] OCI Robot Cloud Auto Re-Training Trigger")
    print(f"[AutoRetrain] Watching: {watch_dir}")
    print(f"[AutoRetrain] Trigger: {args.trigger_episodes} new episodes OR every {args.trigger_interval_hours}h")
    print(f"[AutoRetrain] Fine-tune: {args.finetune_steps} steps on GPU {args.gpu_id}")
    print(f"[AutoRetrain] Check interval: {args.check_interval_sec}s\n")

    active_job: Optional[subprocess.Popen] = None

    while True:
        try:
            now = time.time()
            ep_count = count_episodes(watch_dir)
            new_eps = ep_count - state.last_trigger_episode_count
            time_since_trigger = now - state.last_trigger_time
            hours_since_trigger = time_since_trigger / 3600

            # Check if active job is done
            if active_job is not None:
                ret = active_job.poll()
                if ret is not None:
                    status = "succeeded" if ret == 0 else f"failed (code {ret})"
                    print(f"[AutoRetrain] {datetime.now():%H:%M} Job {status}")
                    send_webhook(args.webhook_url, f"Fine-tuning {status}.")
                    if ret == 0:
                        # Restart GR00T server with new checkpoint
                        last_job_dir = output_dir / f"job_{state.total_jobs_run:03d}" / "checkpoint"
                        if last_job_dir.exists():
                            restart_groot_server(last_job_dir, args.groot_port, args.gpu_id)
                    active_job = None

            # Decide whether to trigger
            should_trigger = False
            trigger_reason = ""

            if active_job is not None:
                pass  # job running, don't queue another
            elif new_eps >= args.trigger_episodes:
                should_trigger = True
                trigger_reason = f"{new_eps} new episodes"
            elif (new_eps > 0 and
                  hours_since_trigger >= args.trigger_interval_hours):
                should_trigger = True
                trigger_reason = f"time-based ({hours_since_trigger:.1f}h elapsed, {new_eps} new eps)"

            if should_trigger:
                print(f"\n[AutoRetrain] {datetime.now():%H:%M} Trigger: {trigger_reason}")
                print(f"[AutoRetrain] Total episodes: {ep_count}")

                # Validate quality
                quality = validate_episodes(watch_dir, args.min_episode_steps)
                print(f"[AutoRetrain] Quality: {quality['valid_count']} valid, "
                      f"{quality['invalid_count']} invalid, "
                      f"median={quality['median_length']:.0f} steps")

                if not quality["quality_ok"]:
                    print(f"[AutoRetrain] Quality check failed — skipping (need ≥3 valid eps, median≥{args.min_episode_steps} steps)")
                    send_webhook(args.webhook_url,
                                 f"Upload detected but quality insufficient: {quality}. Add more episodes.")
                else:
                    job_id = f"job_{state.total_jobs_run + 1:03d}"
                    log_file = output_dir / f"{job_id}.log"

                    send_webhook(args.webhook_url,
                                 f"Starting fine-tuning {job_id}: {args.finetune_steps} steps "
                                 f"on {quality['valid_count']} episodes.")

                    active_job = launch_finetune(
                        watch_dir, output_dir, job_id,
                        args.finetune_steps, args.gpu_id, log_file
                    )

                    state.last_trigger_time = now
                    state.last_trigger_episode_count = ep_count
                    state.total_jobs_run += 1
                    state.save()

            else:
                ts = datetime.now().strftime("%H:%M")
                job_status = f"job running (PID {active_job.pid})" if active_job else "idle"
                print(f"[AutoRetrain] {ts} | {ep_count} eps total | +{new_eps} new | {job_status}")

        except KeyboardInterrupt:
            print("\n[AutoRetrain] Shutting down.")
            break
        except Exception as e:
            print(f"[AutoRetrain] Error: {e}")

        time.sleep(args.check_interval_sec)


if __name__ == "__main__":
    main()
