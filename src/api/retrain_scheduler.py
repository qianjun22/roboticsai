#!/usr/bin/env python3
"""
retrain_scheduler.py — Autonomous retraining scheduler for production robot deployments.

Monitors deployed robot fleet performance and automatically triggers fine-tuning
when degradation is detected or sufficient new data has accumulated.

Trigger conditions:
  1. Success rate drops below threshold (default: 60%) for 2 consecutive eval windows
  2. New demo count >= min_demos (default: 50) AND time_since_last_retrain >= min_interval (24h)
  3. Scheduled retrain (e.g., weekly refresh with all accumulated data)

Actions on trigger:
  1. Download new data from OCI Object Storage (or local upload dir)
  2. Merge with existing training set
  3. Launch fine-tuning job (calls robot_cloud_api.py or local finetune)
  4. Monitor training completion
  5. Evaluate new checkpoint
  6. Promote to production if improved, rollback if worse

Notifications:
  - Slack webhook: trigger event, training progress, result
  - Email: weekly summary

Usage:
    python src/api/retrain_scheduler.py --serve --port 8014
    python src/api/retrain_scheduler.py --mock  # simulate degradation event
"""

import argparse
import asyncio
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = Path(os.environ.get("OUTPUT_BASE", "/tmp/robot_cloud"))
DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/robot_uploads"))
DEFAULT_EVAL_DIR = Path(os.environ.get("EVAL_DIR", "/tmp/robot_eval"))
REPO_DIR = Path(os.environ.get("REPO_DIR", Path.home() / "roboticsai"))
STATE_FILE = DEFAULT_OUTPUT_DIR / "retrain_scheduler_state.json"

# ── Enums and Dataclasses ─────────────────────────────────────────────────────

class RetrainTrigger(str, Enum):
    MANUAL = "manual"
    PERFORMANCE_DROP = "performance_drop"
    DATA_ACCUMULATION = "data_accumulation"
    SCHEDULED = "scheduled"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RetrainJob:
    job_id: str
    trigger: RetrainTrigger
    trigger_details: str
    new_data_count: int
    status: JobStatus = JobStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    before_success_rate: Optional[float] = None
    after_success_rate: Optional[float] = None
    checkpoint_promoted: bool = False
    log_lines: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trigger"] = self.trigger.value
        d["status"] = self.status.value
        return d


@dataclass
class SchedulerConfig:
    success_threshold: float = 0.60          # trigger if below this
    consecutive_failures: int = 2            # windows below threshold before trigger
    min_new_demos: int = 50                  # minimum new demos for data trigger
    retrain_interval_hours: float = 24.0     # minimum hours between retrains
    slack_webhook_url: Optional[str] = None  # Slack incoming webhook URL
    eval_interval_minutes: float = 5.0       # how often to poll eval output
    max_concurrent_jobs: int = 1             # only one retrain at a time
    finetune_steps: int = 500                # training steps for auto-retrain
    gpu_id: str = "0"
    base_dataset_dir: Optional[str] = None  # existing training data
    new_data_dir: str = str(DEFAULT_DATA_DIR)
    eval_dir: str = str(DEFAULT_EVAL_DIR)
    output_dir: str = str(DEFAULT_OUTPUT_DIR)
    scheduled_retrain_hours: Optional[float] = None  # e.g. 168 for weekly


# ── In-memory state ───────────────────────────────────────────────────────────

_jobs: Dict[str, RetrainJob] = {}
_eval_history: List[Tuple[datetime, float]] = []   # (timestamp, success_rate)
_last_retrain_time: Optional[datetime] = None
_consecutive_fail_count: int = 0
_scheduler_running: bool = False


# ── Trigger detection ─────────────────────────────────────────────────────────

def check_performance_trigger(
    eval_history: List[Tuple[datetime, float]],
    config: SchedulerConfig,
) -> Tuple[bool, str]:
    """
    Examine recent eval windows and determine if a performance-drop retrain
    should be triggered.

    Returns (should_trigger, reason_string).
    Triggers when the last `consecutive_failures` readings are all below
    `success_threshold`.
    """
    if len(eval_history) < config.consecutive_failures:
        return False, f"not enough eval history ({len(eval_history)} < {config.consecutive_failures})"

    recent = eval_history[-config.consecutive_failures:]
    rates = [r for _, r in recent]
    all_below = all(r < config.success_threshold for r in rates)

    if all_below:
        avg = sum(rates) / len(rates)
        worst = min(rates)
        reason = (
            f"success rate below {config.success_threshold:.0%} for "
            f"{config.consecutive_failures} consecutive windows "
            f"(avg={avg:.1%}, worst={worst:.1%})"
        )
        return True, reason

    return False, (
        f"performance OK — last {len(recent)} rates: "
        + ", ".join(f"{r:.1%}" for r in rates)
    )


def check_data_trigger(
    data_dir: Path,
    last_retrain_time: Optional[datetime],
    config: SchedulerConfig,
) -> Tuple[bool, int]:
    """
    Count new demo files in data_dir that arrived after last_retrain_time.
    Returns (should_trigger, new_demo_count).

    A demo episode is any .hdf5 or directory whose mtime is after last_retrain_time.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return False, 0

    cutoff = last_retrain_time or datetime.min
    new_count = 0

    for entry in data_dir.iterdir():
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime > cutoff and (entry.suffix == ".hdf5" or entry.is_dir()):
            new_count += 1

    if new_count < config.min_new_demos:
        return False, new_count

    if last_retrain_time is None:
        return True, new_count

    hours_since = (datetime.now() - last_retrain_time).total_seconds() / 3600
    if hours_since < config.retrain_interval_hours:
        return False, new_count

    return True, new_count


def check_scheduled_trigger(
    last_retrain_time: Optional[datetime],
    config: SchedulerConfig,
) -> Tuple[bool, str]:
    """Return True if the scheduled interval has elapsed since last retrain."""
    if config.scheduled_retrain_hours is None:
        return False, "no scheduled interval configured"

    if last_retrain_time is None:
        return True, "no previous retrain on record — running initial scheduled retrain"

    elapsed = (datetime.now() - last_retrain_time).total_seconds() / 3600
    if elapsed >= config.scheduled_retrain_hours:
        return True, f"scheduled interval {config.scheduled_retrain_hours}h elapsed ({elapsed:.1f}h since last retrain)"
    return False, f"scheduled interval not yet reached ({elapsed:.1f}h / {config.scheduled_retrain_hours}h)"


# ── Slack notifications ───────────────────────────────────────────────────────

def send_slack_notification(
    webhook_url: Optional[str],
    message: str,
    emoji: str = "🤖",
) -> bool:
    """
    Post a message to Slack via incoming webhook.
    Returns True on success; logs warning and returns False on any failure
    so the scheduler is never blocked by notification errors.
    """
    if not webhook_url:
        print(f"[notify] (no webhook) {emoji} {message}")
        return False

    if not REQUESTS_OK:
        print(f"[notify] requests not installed — skipping Slack: {message}")
        return False

    payload = {"text": f"{emoji} *OCI Robot Cloud Scheduler*\n{message}"}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[notify] Slack webhook failed (non-fatal): {exc}")
        return False


# ── Data merging helpers ──────────────────────────────────────────────────────

def merge_datasets(
    base_dir: Optional[Path],
    new_dir: Path,
    merged_dir: Path,
) -> int:
    """
    Copy/symlink new demo episodes into merged_dir alongside base episodes.
    Returns total episode count in merged_dir.
    """
    merged_dir.mkdir(parents=True, exist_ok=True)

    total = 0

    if base_dir and base_dir.exists():
        for ep in base_dir.iterdir():
            dst = merged_dir / ep.name
            if not dst.exists():
                dst.symlink_to(ep.resolve())
            total += 1

    if new_dir.exists():
        for ep in new_dir.iterdir():
            if ep.suffix == ".hdf5" or ep.is_dir():
                dst = merged_dir / ep.name
                if not dst.exists():
                    dst.symlink_to(ep.resolve())
                total += 1

    return total


# ── Fine-tune subprocess ──────────────────────────────────────────────────────

def _poll_log_for_progress(log_path: Path, job: RetrainJob, timeout_s: int = 3600) -> bool:
    """
    Tail a fine-tune log file until training completes or times out.
    Returns True if training finished successfully.
    """
    start = time.time()
    last_size = 0

    while time.time() - start < timeout_s:
        if log_path.exists():
            with open(log_path) as f:
                content = f.read()
            if len(content) > last_size:
                new_text = content[last_size:]
                last_size = len(content)
                for line in new_text.splitlines():
                    job.log_lines.append(line)
                    if "training complete" in line.lower() or "finished" in line.lower():
                        return True
                    if "error" in line.lower() or "traceback" in line.lower():
                        job.error = line
                        return False
        time.sleep(10)

    job.error = "training timed out"
    return False


def _find_latest_checkpoint(output_dir: Path) -> Optional[Path]:
    """Return the most recently modified checkpoint directory."""
    checkpoints = list(output_dir.glob("checkpoint-*"))
    if not checkpoints:
        return None
    return max(checkpoints, key=lambda p: p.stat().st_mtime)


def _run_eval(checkpoint: Path, eval_dir: Path, gpu_id: str) -> Optional[float]:
    """
    Run the closed-loop eval script against a checkpoint.
    Returns success rate (0–1) or None on failure.
    """
    eval_script = REPO_DIR / "src" / "eval" / "closed_loop_eval.py"
    if not eval_script.exists():
        # Fallback: return a synthetic result for environments without eval
        print(f"[eval] eval script not found at {eval_script}, using mock result")
        return None

    result_path = eval_dir / f"eval_{checkpoint.name}_result.json"
    cmd = [
        "python3", str(eval_script),
        "--checkpoint", str(checkpoint),
        "--output", str(result_path),
        "--gpu-id", gpu_id,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            print(f"[eval] eval failed: {proc.stderr[:200]}")
            return None
        if result_path.exists():
            with open(result_path) as f:
                data = json.load(f)
            return float(data.get("success_rate", 0.0))
    except Exception as exc:
        print(f"[eval] exception during eval: {exc}")
    return None


# ── Full retrain orchestration ────────────────────────────────────────────────

def run_retrain_job(job: RetrainJob, config: SchedulerConfig) -> RetrainJob:
    """
    Orchestrate a complete retrain cycle:
      1. Merge new data with base dataset
      2. Launch fine-tune subprocess
      3. Monitor progress via log polling
      4. Run eval on new checkpoint
      5. Compare before/after success rate
      6. Promote if improved, log rollback decision if worse

    Mutates and returns the job object.
    """
    global _last_retrain_time

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now().isoformat()

    output_dir = Path(config.output_dir) / f"retrain_{job.job_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_dir = output_dir / "merged_data"
    log_path = output_dir / "finetune.log"
    eval_dir = Path(config.eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    print(f"[scheduler] job {job.job_id}: merging datasets into {merged_dir}")
    send_slack_notification(
        config.slack_webhook_url,
        f"Retrain job `{job.job_id}` started.\n"
        f"Trigger: {job.trigger.value} — {job.trigger_details}\n"
        f"New demos: {job.new_data_count}",
    )

    base_dir = Path(config.base_dataset_dir) if config.base_dataset_dir else None
    total_eps = merge_datasets(base_dir, Path(config.new_data_dir), merged_dir)
    job.log_lines.append(f"merged {total_eps} total episodes into {merged_dir}")
    print(f"[scheduler] job {job.job_id}: {total_eps} episodes merged")

    # Build fine-tune command
    finetune_script = REPO_DIR / "src" / "training" / "finetune_groot.py"
    cmd = [
        "python3", str(finetune_script),
        "--dataset-dir", str(merged_dir),
        "--output-dir", str(output_dir),
        "--num-steps", str(config.finetune_steps),
        "--gpu-id", config.gpu_id,
    ]

    job.log_lines.append(f"launching: {' '.join(cmd)}")
    print(f"[scheduler] job {job.job_id}: launching fine-tune")

    try:
        with open(log_path, "w") as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )

        success = _poll_log_for_progress(log_path, job)

        if proc.poll() is None:
            proc.wait(timeout=60)

        if not success or proc.returncode not in (0, None):
            job.status = JobStatus.FAILED
            job.error = job.error or f"fine-tune exited with code {proc.returncode}"
            job.completed_at = datetime.now().isoformat()
            send_slack_notification(
                config.slack_webhook_url,
                f"Retrain job `{job.job_id}` FAILED: {job.error}",
                emoji="❌",
            )
            return job

    except FileNotFoundError:
        # finetune script not present — log and continue with eval stub
        job.log_lines.append("finetune script not found; skipping actual training (dev mode)")
        print(f"[scheduler] job {job.job_id}: finetune script not found, continuing in dev mode")

    # Evaluate new checkpoint
    job.status = JobStatus.EVALUATING
    print(f"[scheduler] job {job.job_id}: evaluating checkpoint")

    checkpoint = _find_latest_checkpoint(output_dir)
    if checkpoint:
        job.log_lines.append(f"evaluating checkpoint: {checkpoint}")
        after_rate = _run_eval(checkpoint, eval_dir, config.gpu_id)
    else:
        job.log_lines.append("no checkpoint found; skipping eval")
        after_rate = None

    job.after_success_rate = after_rate

    # Promote or roll back
    job.status = JobStatus.PROMOTING
    before = job.before_success_rate or 0.0
    after = after_rate or 0.0

    if after_rate is None:
        job.log_lines.append("eval unavailable — checkpoint retained but not auto-promoted")
        job.checkpoint_promoted = False
        result_msg = f"Retrain `{job.job_id}` complete. Eval unavailable; manual review required."
        result_emoji = "⚠️"
    elif after >= before:
        job.checkpoint_promoted = True
        job.log_lines.append(
            f"promoting checkpoint: {before:.1%} → {after:.1%} (+{after - before:.1%})"
        )
        result_msg = (
            f"Retrain `{job.job_id}` PROMOTED.\n"
            f"Success rate: {before:.1%} → {after:.1%} (+{after - before:.1%})"
        )
        result_emoji = "✅"
    else:
        job.checkpoint_promoted = False
        job.status = JobStatus.ROLLED_BACK
        job.log_lines.append(
            f"rolling back: new checkpoint {after:.1%} < baseline {before:.1%}; keeping previous"
        )
        result_msg = (
            f"Retrain `{job.job_id}` ROLLED BACK.\n"
            f"New checkpoint ({after:.1%}) worse than baseline ({before:.1%}); keeping previous."
        )
        result_emoji = "↩️"

    if job.status != JobStatus.ROLLED_BACK:
        job.status = JobStatus.COMPLETED

    job.completed_at = datetime.now().isoformat()
    _last_retrain_time = datetime.now()

    send_slack_notification(config.slack_webhook_url, result_msg, emoji=result_emoji)
    print(f"[scheduler] job {job.job_id}: {job.status.value}")
    return job


# ── Scheduler daemon loop ─────────────────────────────────────────────────────

def _read_latest_eval(eval_dir: Path) -> Optional[float]:
    """
    Scan eval_dir for the most recently written result JSON and return the
    success_rate field.  Returns None if nothing found.
    """
    results = list(Path(eval_dir).glob("*.json")) if Path(eval_dir).exists() else []
    if not results:
        return None
    latest = max(results, key=lambda p: p.stat().st_mtime)
    try:
        with open(latest) as f:
            data = json.load(f)
        return float(data.get("success_rate", data.get("sr", 0.0)))
    except Exception:
        return None


def scheduler_loop(config: SchedulerConfig) -> None:
    """
    Main daemon loop.  Runs forever (or until _scheduler_running is set False).

    Every eval_interval_minutes:
      - Read latest eval output
      - Check performance trigger
      - Check data-accumulation trigger
      - Check scheduled trigger
      - If any trigger fires and no job is running: create and run RetrainJob
    """
    global _eval_history, _last_retrain_time, _consecutive_fail_count, _scheduler_running

    _scheduler_running = True
    interval_s = config.eval_interval_minutes * 60
    print(f"[scheduler] daemon started (poll every {config.eval_interval_minutes} min)")

    send_slack_notification(
        config.slack_webhook_url,
        "Retrain scheduler started.",
        emoji="🚀",
    )

    active_jobs = [j for j in _jobs.values() if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]

    while _scheduler_running:
        now = datetime.now()

        # --- read latest eval ---
        sr = _read_latest_eval(Path(config.eval_dir))
        if sr is not None:
            _eval_history.append((now, sr))
            # Keep only last 20 readings
            if len(_eval_history) > 20:
                _eval_history = _eval_history[-20:]
            print(f"[scheduler] eval success_rate={sr:.1%} at {now.strftime('%H:%M:%S')}")

        # --- count active jobs ---
        active_jobs = [
            j for j in _jobs.values()
            if j.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.EVALUATING, JobStatus.PROMOTING)
        ]
        if len(active_jobs) >= config.max_concurrent_jobs:
            print(f"[scheduler] {len(active_jobs)} job(s) already active; skipping trigger check")
            time.sleep(interval_s)
            continue

        # --- check triggers ---
        trigger: Optional[RetrainTrigger] = None
        trigger_details = ""
        new_data_count = 0

        should_perf, perf_reason = check_performance_trigger(_eval_history, config)
        if should_perf:
            trigger = RetrainTrigger.PERFORMANCE_DROP
            trigger_details = perf_reason

        if trigger is None:
            should_data, new_data_count = check_data_trigger(
                Path(config.new_data_dir), _last_retrain_time, config
            )
            if should_data:
                trigger = RetrainTrigger.DATA_ACCUMULATION
                trigger_details = f"{new_data_count} new demos accumulated"

        if trigger is None:
            should_sched, sched_reason = check_scheduled_trigger(_last_retrain_time, config)
            if should_sched:
                trigger = RetrainTrigger.SCHEDULED
                trigger_details = sched_reason

        if trigger is not None:
            print(f"[scheduler] trigger={trigger.value}: {trigger_details}")
            current_sr = _eval_history[-1][1] if _eval_history else None

            job = RetrainJob(
                job_id=uuid.uuid4().hex[:8],
                trigger=trigger,
                trigger_details=trigger_details,
                new_data_count=new_data_count,
                before_success_rate=current_sr,
            )
            _jobs[job.job_id] = job
            run_retrain_job(job, config)

        time.sleep(interval_s)

    print("[scheduler] daemon stopped")


# ── Mock simulation ───────────────────────────────────────────────────────────

def run_mock_simulation(config: SchedulerConfig) -> str:
    """
    Simulate a 6-hour production timeline (time-compressed):
      - Hours 0-3: success rate ~70% (normal)
      - Hour 4: success rate drops to 45% (trigger fires)
      - Retrain takes ~20 min (simulated fast)
      - New checkpoint: 72% success

    Returns an HTML timeline report.
    """
    global _eval_history, _last_retrain_time, _jobs

    print("[mock] Starting 6h simulation (time-compressed)...")

    timeline_events = []
    base_time = datetime.now() - timedelta(hours=6)

    def ts(h: float) -> datetime:
        return base_time + timedelta(hours=h)

    # Simulate eval readings
    mock_evals = [
        (0.0, 0.71), (0.5, 0.69), (1.0, 0.72), (1.5, 0.70),
        (2.0, 0.68), (2.5, 0.71), (3.0, 0.70),
        # Degradation
        (3.5, 0.58), (4.0, 0.45), (4.5, 0.44),
    ]

    for h, sr in mock_evals:
        _eval_history.append((ts(h), sr))
        status = "normal" if sr >= config.success_threshold else "DEGRADED"
        timeline_events.append({
            "time": ts(h).strftime("%H:%M"),
            "hour": h,
            "event": f"Eval window: success_rate={sr:.1%}",
            "status": status,
            "sr": sr,
        })

    # Check trigger (should fire after 2 consecutive failures at hours 4.0 and 4.5)
    should_trigger, reason = check_performance_trigger(_eval_history, config)
    trigger_time = ts(4.5)
    timeline_events.append({
        "time": trigger_time.strftime("%H:%M"),
        "hour": 4.5,
        "event": f"TRIGGER FIRED: {reason}",
        "status": "trigger",
        "sr": None,
    })

    print(f"[mock] trigger check: {should_trigger} — {reason}")

    # Simulate retrain job
    job = RetrainJob(
        job_id="mock0001",
        trigger=RetrainTrigger.PERFORMANCE_DROP,
        trigger_details=reason,
        new_data_count=63,
        before_success_rate=0.44,
        status=JobStatus.RUNNING,
        started_at=trigger_time.isoformat(),
    )
    _jobs[job.job_id] = job

    retrain_end = ts(4.5 + 20 / 60)
    timeline_events.append({
        "time": (trigger_time + timedelta(minutes=1)).strftime("%H:%M"),
        "hour": 4.5 + 1 / 60,
        "event": "Retrain job started — merging 63 new demos, launching fine-tune (500 steps)",
        "status": "retrain",
        "sr": None,
    })

    timeline_events.append({
        "time": retrain_end.strftime("%H:%M"),
        "hour": 4.5 + 20 / 60,
        "event": "Fine-tune complete — evaluating new checkpoint",
        "status": "retrain",
        "sr": None,
    })

    # New checkpoint eval
    after_sr = 0.72
    job.after_success_rate = after_sr
    job.checkpoint_promoted = True
    job.status = JobStatus.COMPLETED
    job.completed_at = retrain_end.isoformat()

    timeline_events.append({
        "time": retrain_end.strftime("%H:%M"),
        "hour": 4.5 + 22 / 60,
        "event": f"New checkpoint PROMOTED: {job.before_success_rate:.1%} → {after_sr:.1%} (+{after_sr - job.before_success_rate:.1%})",
        "status": "promoted",
        "sr": after_sr,
    })

    # Hours 5-6: recovered
    for h, sr in [(5.0, 0.71), (5.5, 0.72), (6.0, 0.73)]:
        _eval_history.append((ts(h), sr))
        timeline_events.append({
            "time": ts(h).strftime("%H:%M"),
            "hour": h,
            "event": f"Eval window: success_rate={sr:.1%} (post-retrain)",
            "status": "recovered",
            "sr": sr,
        })

    _last_retrain_time = retrain_end

    # Build HTML report
    html = _build_html_report(timeline_events, job, config)

    report_path = Path(config.output_dir) / "mock_timeline_report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(html)

    print(f"[mock] Simulation complete. Report saved to {report_path}")
    return html


def _build_html_report(events: list, job: RetrainJob, config: SchedulerConfig) -> str:
    status_colors = {
        "normal": "#22c55e",
        "DEGRADED": "#ef4444",
        "trigger": "#f97316",
        "retrain": "#3b82f6",
        "promoted": "#8b5cf6",
        "recovered": "#10b981",
    }

    rows = ""
    for ev in events:
        color = status_colors.get(ev["status"], "#6b7280")
        sr_cell = f"{ev['sr']:.1%}" if ev.get("sr") is not None else "—"
        rows += (
            f"<tr>"
            f"<td style='padding:6px 12px;font-family:monospace'>{ev['time']}</td>"
            f"<td style='padding:6px 12px;color:{color};font-weight:bold'>{ev['status'].upper()}</td>"
            f"<td style='padding:6px 12px'>{ev['event']}</td>"
            f"<td style='padding:6px 12px;text-align:right;font-family:monospace'>{sr_cell}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>OCI Robot Cloud — Retrain Scheduler Mock Timeline</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; }}
    h1 {{ color: #7c3aed; margin-bottom: 4px; }}
    h2 {{ color: #94a3b8; font-weight: 400; margin-top: 0; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
    th {{ background: #1e293b; padding: 8px 12px; text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    tr:nth-child(even) {{ background: #1e293b40; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 99px; font-size: 12px; font-weight: 600; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 16px 24px; margin: 12px 0; }}
    .metric {{ font-size: 32px; font-weight: 700; color: #7c3aed; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Retrain Scheduler</h1>
  <h2>Mock 6h Timeline Simulation</h2>
  <div style="display:flex;gap:16px;flex-wrap:wrap">
    <div class="card">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase">Trigger</div>
      <div class="metric">{job.trigger.value.replace("_", " ").title()}</div>
      <div style="color:#94a3b8;font-size:13px;margin-top:4px">{job.trigger_details}</div>
    </div>
    <div class="card">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase">Success Rate</div>
      <div class="metric">{job.before_success_rate:.0%} → {job.after_success_rate:.0%}</div>
      <div style="color:#22c55e;font-size:13px;margin-top:4px">+{(job.after_success_rate or 0) - (job.before_success_rate or 0):.0%} improvement</div>
    </div>
    <div class="card">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase">New Demos</div>
      <div class="metric">{job.new_data_count}</div>
      <div style="color:#94a3b8;font-size:13px;margin-top:4px">merged into training set</div>
    </div>
    <div class="card">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase">Outcome</div>
      <div class="metric" style="color:#22c55e">Promoted</div>
      <div style="color:#94a3b8;font-size:13px;margin-top:4px">new checkpoint active</div>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Time</th><th>Status</th><th>Event</th><th>Success Rate</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#475569;font-size:12px;margin-top:32px">
    Generated by OCI Robot Cloud retrain_scheduler.py — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  </p>
</body>
</html>"""


# ── FastAPI service ───────────────────────────────────────────────────────────

def _build_app(config: SchedulerConfig) -> "FastAPI":
    app = FastAPI(
        title="OCI Robot Cloud — Retrain Scheduler",
        description="Autonomous retraining scheduler for production robot deployments",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ManualTriggerRequest(BaseModel):
        reason: str = "manual trigger"
        new_data_count: int = 0

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "scheduler_running": _scheduler_running,
            "jobs_total": len(_jobs),
            "jobs_active": sum(
                1 for j in _jobs.values()
                if j.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.EVALUATING, JobStatus.PROMOTING)
            ),
            "last_retrain": _last_retrain_time.isoformat() if _last_retrain_time else None,
            "eval_history_points": len(_eval_history),
        }

    @app.get("/config")
    def get_config():
        return asdict(config)

    @app.get("/jobs")
    def list_jobs():
        return [j.to_dict() for j in sorted(_jobs.values(), key=lambda j: j.started_at or "", reverse=True)]

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
        return job.to_dict()

    @app.post("/jobs")
    def create_job(req: ManualTriggerRequest, background_tasks: BackgroundTasks):
        current_sr = _eval_history[-1][1] if _eval_history else None
        job = RetrainJob(
            job_id=uuid.uuid4().hex[:8],
            trigger=RetrainTrigger.MANUAL,
            trigger_details=req.reason,
            new_data_count=req.new_data_count,
            before_success_rate=current_sr,
        )
        _jobs[job.job_id] = job
        background_tasks.add_task(run_retrain_job, job, config)
        return {"job_id": job.job_id, "status": job.status.value}

    @app.get("/mock-report", response_class=HTMLResponse)
    def mock_report():
        html = run_mock_simulation(config)
        return HTMLResponse(content=html)

    return app


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Retrain Scheduler")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument("--port", type=int, default=8014, help="API server port")
    parser.add_argument("--mock", action="store_true", help="Run mock simulation and print report path")
    parser.add_argument("--daemon", action="store_true", help="Run scheduler daemon (blocking)")

    # Config overrides
    parser.add_argument("--success-threshold", type=float, default=0.60)
    parser.add_argument("--consecutive-failures", type=int, default=2)
    parser.add_argument("--min-new-demos", type=int, default=50)
    parser.add_argument("--retrain-interval-hours", type=float, default=24.0)
    parser.add_argument("--eval-interval-minutes", type=float, default=5.0)
    parser.add_argument("--slack-webhook", type=str, default=None)
    parser.add_argument("--new-data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--eval-dir", type=str, default=str(DEFAULT_EVAL_DIR))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-dataset-dir", type=str, default=None)
    parser.add_argument("--finetune-steps", type=int, default=500)
    parser.add_argument("--gpu-id", type=str, default="0")
    parser.add_argument("--scheduled-retrain-hours", type=float, default=None)

    args = parser.parse_args()

    config = SchedulerConfig(
        success_threshold=args.success_threshold,
        consecutive_failures=args.consecutive_failures,
        min_new_demos=args.min_new_demos,
        retrain_interval_hours=args.retrain_interval_hours,
        eval_interval_minutes=args.eval_interval_minutes,
        slack_webhook_url=args.slack_webhook,
        new_data_dir=args.new_data_dir,
        eval_dir=args.eval_dir,
        output_dir=args.output_dir,
        base_dataset_dir=args.base_dataset_dir,
        finetune_steps=args.finetune_steps,
        gpu_id=args.gpu_id,
        scheduled_retrain_hours=args.scheduled_retrain_hours,
    )

    if args.mock:
        html = run_mock_simulation(config)
        report_path = Path(config.output_dir) / "mock_timeline_report.html"
        print(f"\nMock simulation complete.")
        print(f"HTML report: {report_path}")
        print(f"Jobs: {[j.to_dict() for j in _jobs.values()]}")
        return

    if args.daemon:
        scheduler_loop(config)
        return

    if args.serve:
        if not FASTAPI_OK:
            print("ERROR: fastapi/uvicorn not installed. Run: pip install fastapi uvicorn")
            return
        app = _build_app(config)
        import uvicorn as _uv
        # Start scheduler loop in background thread
        import threading
        t = threading.Thread(target=scheduler_loop, args=(config,), daemon=True)
        t.start()
        _uv.run(app, host="0.0.0.0", port=args.port)
        return

    # Default: print status
    parser.print_help()


if __name__ == "__main__":
    main()
