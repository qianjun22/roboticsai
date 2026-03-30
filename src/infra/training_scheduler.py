"""
training_scheduler.py — OCI Training Job Scheduler

Optimizes when to run GPU training jobs on OCI A100 instances to minimize cost.
Schedules jobs during off-peak hours, handles conceptual preemption, and tracks
savings vs naive (FIFO) scheduling.

Usage
-----
# Dry-run with 20 mock jobs, output HTML report:
    python src/infra/training_scheduler.py --mock --n-jobs 20 --output /tmp/training_schedule.html

# Use a specific strategy:
    python src/infra/training_scheduler.py --mock --n-jobs 20 --strategy cost-optimal

# All strategies comparison:
    python src/infra/training_scheduler.py --mock --n-jobs 20 --strategy all --output /tmp/training_schedule.html

# Add a real job to the queue:
    python src/infra/training_scheduler.py --add-job \
        --job-id finetune_run7 --gpu-hours 4.5 --priority 2 \
        --deadline "2026-03-30T18:00:00"

# List queued jobs:
    python src/infra/training_scheduler.py --list-jobs

# Show schedule for queued jobs:
    python src/infra/training_scheduler.py --schedule --strategy cost-optimal --output /tmp/out.html

Environment
-----------
    SCHEDULER_DB_PATH  — path to SQLite DB (default: /tmp/training_scheduler.db)

Cost Model
----------
    OCI A100 flat rate: $4.20/hr
    Off-peak hours (18:00–08:00): 20% notional cost reduction (mock)
    On-peak hours  (08:00–18:00): base rate

No external dependencies — stdlib only (sqlite3, argparse, json, math, html,
datetime, pathlib, random, uuid).
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import os
import random
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OCI_A100_RATE_PER_HR: float = 4.20          # USD
OFF_PEAK_DISCOUNT: float = 0.20             # 20 % notional saving
OFF_PEAK_START_HOUR: int = 18               # 18:00 local
OFF_PEAK_END_HOUR: int = 8                  # 08:00 local
BATCH_COALESCE_THRESHOLD_HR: float = 0.5   # jobs shorter than this get batched
SETUP_OVERHEAD_HR: float = 0.05            # ~3 min per job batch

DB_PATH_DEFAULT = os.environ.get("SCHEDULER_DB_PATH", "/tmp/training_scheduler.db")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrainingJob:
    job_id: str
    gpu_hours: float
    priority: int                       # 1 = highest, 5 = lowest
    earliest_start: datetime
    deadline: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"             # pending | scheduled | running | done

    @property
    def slack_hours(self) -> float:
        """Slack = how many hours between earliest start and deadline minus job duration."""
        window = (self.deadline - self.earliest_start).total_seconds() / 3600
        return max(0.0, window - self.gpu_hours)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("earliest_start", "deadline", "created_at"):
            d[k] = d[k].isoformat() if isinstance(d[k], datetime) else d[k]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingJob":
        for k in ("earliest_start", "deadline", "created_at"):
            if isinstance(d.get(k), str):
                d[k] = datetime.fromisoformat(d[k])
        return cls(**d)


@dataclass
class ScheduledJob:
    job: TrainingJob
    start_time: datetime
    end_time: datetime
    strategy: str
    cost_usd: float
    is_off_peak: bool  # True if majority of job falls in off-peak window


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

class JobQueue:
    """SQLite-backed persistent job queue."""

    def __init__(self, db_path: str = DB_PATH_DEFAULT):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id       TEXT PRIMARY KEY,
                    gpu_hours    REAL NOT NULL,
                    priority     INTEGER NOT NULL DEFAULT 3,
                    earliest_start TEXT NOT NULL,
                    deadline     TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending'
                )
            """)
            conn.commit()

    def add(self, job: TrainingJob) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs
                  (job_id, gpu_hours, priority, earliest_start, deadline, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.gpu_hours,
                job.priority,
                job.earliest_start.isoformat(),
                job.deadline.isoformat(),
                job.created_at.isoformat(),
                job.status,
            ))
            conn.commit()

    def list_pending(self) -> List[TrainingJob]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='pending' ORDER BY created_at"
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def list_all(self) -> List[TrainingJob]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        return [self._row_to_job(r) for r in rows]

    def update_status(self, job_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, job_id))
            conn.commit()

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()

    @staticmethod
    def _row_to_job(row: tuple) -> TrainingJob:
        job_id, gpu_hours, priority, earliest_start, deadline, created_at, status = row
        return TrainingJob(
            job_id=job_id,
            gpu_hours=gpu_hours,
            priority=priority,
            earliest_start=datetime.fromisoformat(earliest_start),
            deadline=datetime.fromisoformat(deadline),
            created_at=datetime.fromisoformat(created_at),
            status=status,
        )


# ---------------------------------------------------------------------------
# Utilization forecast (mock)
# ---------------------------------------------------------------------------

def mock_utilization_curve(hour: int) -> float:
    """
    Returns estimated GPU cluster utilization (0-1) for a given hour of day.
    Based on a plausible enterprise workload pattern.
    """
    # Gaussian-ish peak around 14:00 (2pm), low overnight
    if 0 <= hour < 6:
        return 0.10 + 0.02 * math.sin(math.pi * hour / 6)
    elif 6 <= hour < 9:
        # ramp up
        return 0.10 + 0.70 * ((hour - 6) / 3)
    elif 9 <= hour <= 17:
        # busy core hours
        peak = 0.90 - 0.15 * math.cos(math.pi * (hour - 9) / 8)
        return min(0.95, peak)
    elif 17 < hour <= 20:
        # ramp down
        return 0.80 - 0.50 * ((hour - 17) / 3)
    else:
        # late evening
        return 0.25 - 0.10 * ((hour - 20) / 4)


def effective_rate(start: datetime, gpu_hours: float) -> float:
    """
    Compute effective cost rate for a job given its start time and duration.
    Off-peak hours get a 20% notional discount.
    Returns total cost in USD.
    """
    cost = 0.0
    dt = start
    remaining = gpu_hours
    while remaining > 0:
        chunk = min(1.0, remaining)
        h = dt.hour
        is_off = h >= OFF_PEAK_START_HOUR or h < OFF_PEAK_END_HOUR
        rate = OCI_A100_RATE_PER_HR * (1 - OFF_PEAK_DISCOUNT if is_off else 1.0)
        cost += chunk * rate
        remaining -= chunk
        dt = dt + timedelta(hours=chunk)
    return cost


def is_mostly_off_peak(start: datetime, gpu_hours: float) -> bool:
    """Returns True if more than half the job runs in off-peak hours."""
    off_peak_hours = 0.0
    dt = start
    remaining = gpu_hours
    while remaining > 0:
        chunk = min(1.0, remaining)
        h = dt.hour
        if h >= OFF_PEAK_START_HOUR or h < OFF_PEAK_END_HOUR:
            off_peak_hours += chunk
        remaining -= chunk
        dt = dt + timedelta(hours=chunk)
    return off_peak_hours > gpu_hours / 2


# ---------------------------------------------------------------------------
# Batch coalescing
# ---------------------------------------------------------------------------

def coalesce_batches(jobs: List[TrainingJob]) -> List[List[TrainingJob]]:
    """
    Groups jobs shorter than BATCH_COALESCE_THRESHOLD_HR into batches.
    Large jobs are each their own batch. Returns list-of-lists.
    """
    batches: List[List[TrainingJob]] = []
    current_batch: List[TrainingJob] = []
    current_batch_hours = 0.0

    for job in jobs:
        if job.gpu_hours >= BATCH_COALESCE_THRESHOLD_HR:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_batch_hours = 0.0
            batches.append([job])
        else:
            current_batch.append(job)
            current_batch_hours += job.gpu_hours
            # flush batch when accumulated > 2h or batch count >= 10
            if current_batch_hours >= 2.0 or len(current_batch) >= 10:
                batches.append(current_batch)
                current_batch = []
                current_batch_hours = 0.0

    if current_batch:
        batches.append(current_batch)

    return batches


def batch_gpu_hours(batch: List[TrainingJob]) -> float:
    """Total GPU hours for a batch, including setup overhead if >1 job."""
    total = sum(j.gpu_hours for j in batch)
    if len(batch) > 1:
        total += SETUP_OVERHEAD_HR
    return total


# ---------------------------------------------------------------------------
# Scheduling strategies
# ---------------------------------------------------------------------------

Strategy = str  # "fifo" | "priority" | "deadline" | "cost-optimal"


def schedule_fifo(jobs: List[TrainingJob], now: datetime) -> List[ScheduledJob]:
    """FIFO: process in queue arrival order, start immediately after previous job."""
    ordered = sorted(jobs, key=lambda j: j.created_at)
    return _schedule_sequential(ordered, now, "fifo")


def schedule_priority(jobs: List[TrainingJob], now: datetime) -> List[ScheduledJob]:
    """Priority: highest priority (lowest number) first."""
    ordered = sorted(jobs, key=lambda j: (j.priority, j.created_at))
    return _schedule_sequential(ordered, now, "priority")


def schedule_deadline(jobs: List[TrainingJob], now: datetime) -> List[ScheduledJob]:
    """Earliest-Deadline-First with slack-based tie-breaking."""
    ordered = sorted(jobs, key=lambda j: (j.deadline, j.slack_hours))
    return _schedule_sequential(ordered, now, "deadline")


def schedule_cost_optimal(jobs: List[TrainingJob], now: datetime) -> List[ScheduledJob]:
    """
    Cost-optimal: schedule each job at the earliest off-peak window that satisfies
    its earliest_start and deadline constraints, falling back to cheapest on-peak slot.
    Uses batch coalescing for small jobs.
    """
    batches = coalesce_batches(sorted(jobs, key=lambda j: j.deadline))
    results: List[ScheduledJob] = []
    cursor = now

    for batch in batches:
        # Constraints from batch members
        earliest = max(cursor, max(j.earliest_start for j in batch))
        latest_deadline = min(j.deadline for j in batch)
        hours_needed = batch_gpu_hours(batch)

        # Find best start: prefer off-peak, must finish before deadline
        best_start = _find_off_peak_slot(earliest, latest_deadline, hours_needed, cursor)

        for job in batch:
            end = best_start + timedelta(hours=job.gpu_hours)
            cost = effective_rate(best_start, job.gpu_hours)
            results.append(ScheduledJob(
                job=job,
                start_time=best_start,
                end_time=end,
                strategy="cost-optimal",
                cost_usd=cost,
                is_off_peak=is_mostly_off_peak(best_start, job.gpu_hours),
            ))
            best_start = end  # next job in batch starts immediately after

        cursor = best_start

    return results


def _find_off_peak_slot(
    earliest: datetime,
    deadline: datetime,
    hours_needed: float,
    wall_now: datetime,
) -> datetime:
    """
    Scan forward from earliest in 30-minute steps looking for an off-peak window
    where the job fits before the deadline. Falls back to earliest if none found.
    """
    candidate = earliest
    step = timedelta(minutes=30)
    max_scan = timedelta(days=7)
    scan_end = earliest + max_scan

    while candidate + timedelta(hours=hours_needed) <= deadline and candidate <= scan_end:
        h = candidate.hour
        if h >= OFF_PEAK_START_HOUR or h < OFF_PEAK_END_HOUR:
            return candidate
        candidate += step

    # Fallback: just return earliest valid start
    return max(earliest, wall_now)


def _schedule_sequential(
    jobs: List[TrainingJob],
    now: datetime,
    strategy: str,
) -> List[ScheduledJob]:
    """Helper: schedule jobs back-to-back starting from now."""
    results: List[ScheduledJob] = []
    cursor = now
    for job in jobs:
        start = max(cursor, job.earliest_start)
        end = start + timedelta(hours=job.gpu_hours)
        cost = effective_rate(start, job.gpu_hours)
        results.append(ScheduledJob(
            job=job,
            start_time=start,
            end_time=end,
            strategy=strategy,
            cost_usd=cost,
            is_off_peak=is_mostly_off_peak(start, job.gpu_hours),
        ))
        cursor = end
    return results


STRATEGIES: Dict[str, callable] = {
    "fifo": schedule_fifo,
    "priority": schedule_priority,
    "deadline": schedule_deadline,
    "cost-optimal": schedule_cost_optimal,
}


def run_strategy(strategy: str, jobs: List[TrainingJob], now: datetime) -> List[ScheduledJob]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{strategy}'. Choose from: {list(STRATEGIES)}")
    return STRATEGIES[strategy](jobs, now)


# ---------------------------------------------------------------------------
# Savings report
# ---------------------------------------------------------------------------

@dataclass
class SavingsReport:
    strategy_a: str
    strategy_b: str
    cost_a: float
    cost_b: float
    savings_usd: float
    savings_pct: float
    n_jobs: int
    n_off_peak_b: int

    def __str__(self) -> str:
        lines = [
            f"  Strategy A ({self.strategy_a}):   ${self.cost_a:.2f}",
            f"  Strategy B ({self.strategy_b}): ${self.cost_b:.2f}",
            f"  Savings:                ${self.savings_usd:.2f} ({self.savings_pct:.1f}%)",
            f"  Jobs:                   {self.n_jobs} total, {self.n_off_peak_b} off-peak in B",
        ]
        return "\n".join(lines)


def compute_savings(
    jobs: List[TrainingJob],
    strategy_a: str,
    strategy_b: str,
    now: datetime,
) -> SavingsReport:
    sched_a = run_strategy(strategy_a, jobs, now)
    sched_b = run_strategy(strategy_b, jobs, now)
    cost_a = sum(s.cost_usd for s in sched_a)
    cost_b = sum(s.cost_usd for s in sched_b)
    savings = cost_a - cost_b
    pct = savings / cost_a * 100 if cost_a > 0 else 0.0
    n_off = sum(1 for s in sched_b if s.is_off_peak)
    return SavingsReport(
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        cost_a=cost_a,
        cost_b=cost_b,
        savings_usd=savings,
        savings_pct=pct,
        n_jobs=len(jobs),
        n_off_peak_b=n_off,
    )


# ---------------------------------------------------------------------------
# Mock job generator
# ---------------------------------------------------------------------------

JOB_NAME_PREFIXES = [
    "finetune", "pretrain", "eval", "distill", "dagger", "sdg",
    "sweep", "rl_train", "bc_train", "curriculum",
]

def generate_mock_jobs(n: int, seed: int = 42, now: Optional[datetime] = None) -> List[TrainingJob]:
    """Generate n realistic mock training jobs spread over a week."""
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    jobs = []
    for i in range(n):
        offset_h = rng.uniform(0, 168)  # up to 7 days out
        earliest = now + timedelta(hours=offset_h)
        gpu_hours = rng.choice([
            rng.uniform(0.1, 0.4),   # small (batchable)
            rng.uniform(0.1, 0.4),
            rng.uniform(1.0, 4.0),   # medium
            rng.uniform(4.0, 12.0),  # large
            rng.uniform(0.5, 2.0),
        ])
        slack_mult = rng.uniform(1.5, 6.0)
        deadline = earliest + timedelta(hours=gpu_hours * slack_mult + rng.uniform(1, 8))
        prefix = rng.choice(JOB_NAME_PREFIXES)
        job_id = f"{prefix}_{i:03d}_{uuid.uuid4().hex[:6]}"
        jobs.append(TrainingJob(
            job_id=job_id,
            gpu_hours=round(gpu_hours, 2),
            priority=rng.randint(1, 5),
            earliest_start=earliest,
            deadline=deadline,
            created_at=now + timedelta(minutes=i * rng.uniform(0.5, 5)),
        ))
    return jobs


# ---------------------------------------------------------------------------
# HTML / SVG report
# ---------------------------------------------------------------------------

_DARK_COLORS = {
    "fifo":         "#6366f1",  # indigo
    "priority":     "#f59e0b",  # amber
    "deadline":     "#10b981",  # emerald
    "cost-optimal": "#06b6d4",  # cyan
}

_BG = "#0f172a"
_SURFACE = "#1e293b"
_SURFACE2 = "#334155"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ACCENT = "#06b6d4"


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%m/%d %H:%M")


def _svg_gantt(
    all_schedules: Dict[str, List[ScheduledJob]],
    width: int = 900,
) -> str:
    """Build SVG Gantt chart for one or more strategies."""
    if not all_schedules:
        return "<p style='color:#94a3b8'>No schedule data.</p>"

    # Find global time range
    all_jobs_flat = [s for sched in all_schedules.values() for s in sched]
    if not all_jobs_flat:
        return ""

    t_min = min(s.start_time for s in all_jobs_flat)
    t_max = max(s.end_time for s in all_jobs_flat)
    total_secs = max((t_max - t_min).total_seconds(), 1)

    row_h = 22
    label_w = 130
    bar_area_w = width - label_w - 20
    strategies = list(all_schedules.keys())
    n_strategies = len(strategies)

    # Determine rows: group by strategy, then by job within strategy
    rows: List[Tuple[str, ScheduledJob]] = []
    for strat in strategies:
        for sj in all_schedules[strat]:
            rows.append((strat, sj))

    chart_h = len(rows) * row_h + 60  # header + rows

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{chart_h}" '
        f'style="background:{_SURFACE};border-radius:8px;font-family:monospace">',
    ]

    # Header: time axis labels
    n_ticks = 8
    for i in range(n_ticks + 1):
        frac = i / n_ticks
        x = label_w + int(frac * bar_area_w)
        t_label = t_min + timedelta(seconds=frac * total_secs)
        label = t_label.strftime("%m/%d\n%H:%M")
        lines = label.split("\n")
        svg_lines.append(
            f'<line x1="{x}" y1="0" x2="{x}" y2="{chart_h}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        for li, ln in enumerate(lines):
            svg_lines.append(
                f'<text x="{x}" y="{12 + li*11}" text-anchor="middle" '
                f'font-size="8" fill="{_TEXT_DIM}">{html_lib.escape(ln)}</text>'
            )

    # Rows
    prev_strat = None
    y = 40
    for strat, sj in rows:
        color = _DARK_COLORS.get(strat, "#7c3aed")

        # Strategy label on first row
        if strat != prev_strat:
            svg_lines.append(
                f'<text x="4" y="{y + row_h//2 + 4}" font-size="9" '
                f'fill="{color}" font-weight="bold">{html_lib.escape(strat)}</text>'
            )
            prev_strat = strat

        # Job label
        short_id = sj.job.job_id[:14] + ("…" if len(sj.job.job_id) > 14 else "")
        svg_lines.append(
            f'<text x="{label_w - 4}" y="{y + row_h//2 + 4}" '
            f'font-size="8" fill="{_TEXT_DIM}" text-anchor="end">'
            f'{html_lib.escape(short_id)}</text>'
        )

        # Bar
        x_start_frac = (sj.start_time - t_min).total_seconds() / total_secs
        duration_frac = (sj.end_time - sj.start_time).total_seconds() / total_secs
        bx = label_w + int(x_start_frac * bar_area_w)
        bw = max(2, int(duration_frac * bar_area_w))
        opacity = "0.95" if sj.is_off_peak else "0.65"
        title = (
            f"{sj.job.job_id} | {sj.job.gpu_hours:.2f}h | "
            f"${sj.cost_usd:.2f} | {'off-peak' if sj.is_off_peak else 'on-peak'}"
        )
        svg_lines.append(
            f'<rect x="{bx}" y="{y + 2}" width="{bw}" height="{row_h - 4}" '
            f'rx="3" fill="{color}" opacity="{opacity}">'
            f'<title>{html_lib.escape(title)}</title></rect>'
        )
        y += row_h

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def _svg_utilization_curve(width: int = 900) -> str:
    """SVG line chart of the 24h mock utilization curve."""
    height = 120
    pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    hours = list(range(25))
    utils = [mock_utilization_curve(h % 24) for h in hours]

    def px(h: int, u: float):
        x = pad_l + int(h / 24 * plot_w)
        y = pad_t + int((1 - u) * plot_h)
        return x, y

    points = " ".join(f"{px(h, u)[0]},{px(h, u)[1]}" for h, u in zip(hours, utils))

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_SURFACE};border-radius:8px;font-family:monospace">',
        # Off-peak shading (18:00-24:00 and 0:00-8:00)
        f'<rect x="{pad_l + int(18/24*plot_w)}" y="{pad_t}" '
        f'width="{int(6/24*plot_w)}" height="{plot_h}" fill="#1e3a5f" opacity="0.5"/>',
        f'<rect x="{pad_l}" y="{pad_t}" '
        f'width="{int(8/24*plot_w)}" height="{plot_h}" fill="#1e3a5f" opacity="0.5"/>',
        # Axes
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
        f'stroke="{_SURFACE2}" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
        f'stroke="{_SURFACE2}" stroke-width="1"/>',
        # Line
        f'<polyline points="{points}" fill="none" stroke="{_ACCENT}" stroke-width="2"/>',
        # Y labels
        f'<text x="2" y="{pad_t+4}" font-size="8" fill="{_TEXT_DIM}">100%</text>',
        f'<text x="2" y="{pad_t+plot_h//2+4}" font-size="8" fill="{_TEXT_DIM}">50%</text>',
        f'<text x="2" y="{pad_t+plot_h+4}" font-size="8" fill="{_TEXT_DIM}">0%</text>',
    ]

    # Hour labels
    for h in range(0, 25, 3):
        x, _ = px(h, 0)
        svg_lines.append(
            f'<text x="{x}" y="{height - 4}" text-anchor="middle" '
            f'font-size="8" fill="{_TEXT_DIM}">{h:02d}:00</text>'
        )

    svg_lines.append(
        f'<text x="{pad_l + plot_w//2}" y="{pad_t - 2}" text-anchor="middle" '
        f'font-size="9" fill="{_TEXT_DIM}">24h GPU Utilization Forecast (mock) — blue = off-peak</text>'
    )
    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def build_html_report(
    jobs: List[TrainingJob],
    all_schedules: Dict[str, List[ScheduledJob]],
    savings: Optional[SavingsReport] = None,
    now: Optional[datetime] = None,
) -> str:
    """Build the full dark-theme HTML report."""
    now = now or datetime.now(timezone.utc)
    gantt_svg = _svg_gantt(all_schedules)
    util_svg = _svg_utilization_curve()

    # Summary table
    def sched_summary(strat: str, sched: List[ScheduledJob]) -> str:
        total_cost = sum(s.cost_usd for s in sched)
        n_off = sum(1 for s in sched if s.is_off_peak)
        color = _DARK_COLORS.get(strat, "#7c3aed")
        return (
            f'<tr>'
            f'<td style="color:{color};font-weight:bold">{html_lib.escape(strat)}</td>'
            f'<td>{len(sched)}</td>'
            f'<td>${total_cost:.2f}</td>'
            f'<td>{n_off}</td>'
            f'<td>{n_off/max(len(sched),1)*100:.0f}%</td>'
            f'</tr>'
        )

    summary_rows = "".join(sched_summary(k, v) for k, v in all_schedules.items())

    # Job table
    def job_row(j: TrainingJob) -> str:
        return (
            f'<tr>'
            f'<td style="font-family:monospace;font-size:11px">{html_lib.escape(j.job_id[:20])}</td>'
            f'<td>{j.gpu_hours:.2f}h</td>'
            f'<td>P{j.priority}</td>'
            f'<td>{_fmt_dt(j.earliest_start)}</td>'
            f'<td>{_fmt_dt(j.deadline)}</td>'
            f'<td>{j.slack_hours:.1f}h</td>'
            f'</tr>'
        )

    job_rows = "".join(job_row(j) for j in sorted(jobs, key=lambda x: x.created_at))

    savings_html = ""
    if savings:
        pct_class = "color:#10b981" if savings.savings_pct >= 15 else "color:#f59e0b"
        savings_html = f"""
        <section>
          <h2>Savings Report: {html_lib.escape(savings.strategy_a)} vs {html_lib.escape(savings.strategy_b)}</h2>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:12px">
            <div class="card">
              <div class="metric-label">FIFO Total Cost</div>
              <div class="metric-value" style="color:#f87171">${savings.cost_a:.2f}</div>
            </div>
            <div class="card">
              <div class="metric-label">Cost-Optimal Total</div>
              <div class="metric-value" style="color:#34d399">${savings.cost_b:.2f}</div>
            </div>
            <div class="card">
              <div class="metric-label">Savings (USD)</div>
              <div class="metric-value" style="{pct_class}">${savings.savings_usd:.2f}</div>
            </div>
            <div class="card">
              <div class="metric-label">Savings (%)</div>
              <div class="metric-value" style="{pct_class}">{savings.savings_pct:.1f}%</div>
            </div>
          </div>
          <p style="color:{_TEXT_DIM};margin-top:8px;font-size:13px">
            {savings.n_off_peak_b} of {savings.n_jobs} jobs scheduled off-peak in cost-optimal strategy.
            Off-peak discount: {OFF_PEAK_DISCOUNT*100:.0f}% (notional mock).
            OCI A100 base rate: ${OCI_A100_RATE_PER_HR}/hr.
          </p>
        </section>
        """

    ts = now.strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Training Scheduler — {html_lib.escape(ts)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {_BG}; color: {_TEXT}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; font-weight: 700; color: {_ACCENT}; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; font-weight: 600; color: {_TEXT}; margin: 24px 0 12px; border-bottom: 1px solid {_SURFACE2}; padding-bottom: 6px; }}
  section {{ margin-bottom: 32px; }}
  .meta {{ color: {_TEXT_DIM}; font-size: 12px; margin-bottom: 24px; }}
  .card {{ background: {_SURFACE}; border: 1px solid {_SURFACE2}; border-radius: 8px; padding: 16px; }}
  .metric-label {{ font-size: 11px; color: {_TEXT_DIM}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }}
  .metric-value {{ font-size: 24px; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: {_SURFACE2}; color: {_TEXT_DIM}; padding: 6px 10px; text-align: left; font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid {_SURFACE2}; color: {_TEXT}; }}
  tr:hover td {{ background: {_SURFACE2}; }}
  .tag-off {{ background: #0c4a6e; color: #38bdf8; border-radius: 3px; padding: 1px 5px; font-size: 10px; }}
  .tag-on  {{ background: #3b1c1c; color: #fca5a5; border-radius: 3px; padding: 1px 5px; font-size: 10px; }}
  .overflow-x {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>OCI Training Scheduler</h1>
<p class="meta">Generated: {html_lib.escape(ts)} &nbsp;|&nbsp; {len(jobs)} jobs &nbsp;|&nbsp;
A100 @ ${OCI_A100_RATE_PER_HR}/hr &nbsp;|&nbsp;
Off-peak (18:00–08:00): {OFF_PEAK_DISCOUNT*100:.0f}% discount</p>

{savings_html}

<section>
  <h2>Utilization Forecast</h2>
  <div class="overflow-x">{util_svg}</div>
</section>

<section>
  <h2>Schedule Gantt (all strategies)</h2>
  <div class="overflow-x">{gantt_svg}</div>
  <p style="color:{_TEXT_DIM};font-size:11px;margin-top:6px">
    Brighter bars = off-peak. Hover for job details.
  </p>
</section>

<section>
  <h2>Strategy Summary</h2>
  <table>
    <thead><tr>
      <th>Strategy</th><th>Jobs</th><th>Total Cost</th>
      <th>Off-Peak Jobs</th><th>Off-Peak %</th>
    </tr></thead>
    <tbody>{summary_rows}</tbody>
  </table>
</section>

<section>
  <h2>Job Queue ({len(jobs)} jobs)</h2>
  <table>
    <thead><tr>
      <th>Job ID</th><th>GPU Hours</th><th>Priority</th>
      <th>Earliest Start</th><th>Deadline</th><th>Slack</th>
    </tr></thead>
    <tbody>{job_rows}</tbody>
  </table>
</section>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------

def print_schedule(scheduled: List[ScheduledJob], strategy: str) -> None:
    total = sum(s.cost_usd for s in scheduled)
    n_off = sum(1 for s in scheduled if s.is_off_peak)
    print(f"\n{'='*60}")
    print(f"Strategy: {strategy.upper()}   Jobs: {len(scheduled)}   Total: ${total:.2f}")
    print(f"Off-peak: {n_off}/{len(scheduled)}")
    print(f"{'='*60}")
    print(f"{'JOB ID':<22} {'GPU-HRS':>8}  {'START':<16}  {'END':<16}  {'COST':>7}  PEAK")
    print("-" * 80)
    for s in sorted(scheduled, key=lambda x: x.start_time):
        peak = "off" if s.is_off_peak else "ON "
        print(
            f"{s.job.job_id[:22]:<22} {s.job.gpu_hours:>8.2f}  "
            f"{_fmt_dt(s.start_time):<16}  {_fmt_dt(s.end_time):<16}  "
            f"${s.cost_usd:>6.2f}  {peak}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true",
                      help="Generate and schedule mock jobs (no DB)")
    mode.add_argument("--schedule", action="store_true",
                      help="Schedule jobs currently in the DB queue")
    mode.add_argument("--add-job", action="store_true",
                      help="Add a job to the DB queue")
    mode.add_argument("--list-jobs", action="store_true",
                      help="List all jobs in the DB queue")
    mode.add_argument("--clear-queue", action="store_true",
                      help="Delete all jobs from the DB queue")

    # Mock options
    p.add_argument("--n-jobs", type=int, default=20,
                   help="Number of mock jobs (default: 20)")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for mock generation (default: 42)")

    # Strategy
    p.add_argument("--strategy", default="all",
                   choices=["fifo", "priority", "deadline", "cost-optimal", "all"],
                   help="Scheduling strategy (default: all)")

    # Output
    p.add_argument("--output", metavar="PATH",
                   help="Write HTML report to this path")
    p.add_argument("--dry-run", action="store_true",
                   help="Print schedule to stdout without modifying DB")

    # Job fields (for --add-job)
    p.add_argument("--job-id", help="Job identifier")
    p.add_argument("--gpu-hours", type=float, help="Estimated GPU hours")
    p.add_argument("--priority", type=int, default=3, choices=range(1, 6),
                   help="Priority 1 (high) - 5 (low), default 3")
    p.add_argument("--earliest-start", default=None,
                   help="ISO datetime, default: now")
    p.add_argument("--deadline", default=None,
                   help="ISO datetime, default: now + 24h")

    # DB
    p.add_argument("--db", default=DB_PATH_DEFAULT,
                   help=f"SQLite DB path (default: {DB_PATH_DEFAULT})")

    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc)
    queue = JobQueue(db_path=args.db)

    # ---- Add job ----
    if args.add_job:
        if not args.job_id or not args.gpu_hours:
            print("ERROR: --add-job requires --job-id and --gpu-hours")
            return
        earliest = datetime.fromisoformat(args.earliest_start) if args.earliest_start else now
        deadline = datetime.fromisoformat(args.deadline) if args.deadline else now + timedelta(hours=24)
        job = TrainingJob(
            job_id=args.job_id,
            gpu_hours=args.gpu_hours,
            priority=args.priority,
            earliest_start=earliest,
            deadline=deadline,
        )
        queue.add(job)
        print(f"Added job: {job.job_id}  {job.gpu_hours}h  P{job.priority}  deadline={_fmt_dt(job.deadline)}")
        return

    # ---- List jobs ----
    if args.list_jobs:
        jobs = queue.list_all()
        if not jobs:
            print("Queue is empty.")
            return
        print(f"{'JOB ID':<30} {'GPU-HRS':>8}  {'PRI':>3}  {'STATUS':<10}  {'DEADLINE'}")
        print("-" * 75)
        for j in jobs:
            print(f"{j.job_id[:30]:<30} {j.gpu_hours:>8.2f}  P{j.priority}  {j.status:<10}  {_fmt_dt(j.deadline)}")
        return

    # ---- Clear queue ----
    if args.clear_queue:
        queue.clear()
        print("Queue cleared.")
        return

    # ---- Determine jobs to schedule ----
    if args.mock:
        jobs = generate_mock_jobs(n=args.n_jobs, seed=args.seed, now=now)
        print(f"Generated {len(jobs)} mock jobs.")
    elif args.schedule:
        jobs = queue.list_pending()
        if not jobs:
            print("No pending jobs in queue. Use --add-job or --mock.")
            return
        print(f"Scheduling {len(jobs)} pending jobs from DB.")
    else:
        # Default: mock if no mode given
        jobs = generate_mock_jobs(n=args.n_jobs, seed=args.seed, now=now)
        print(f"Generated {len(jobs)} mock jobs (default mode).")

    # ---- Run strategies ----
    strategies_to_run: List[str]
    if args.strategy == "all":
        strategies_to_run = list(STRATEGIES.keys())
    else:
        strategies_to_run = [args.strategy]

    all_schedules: Dict[str, List[ScheduledJob]] = {}
    for strat in strategies_to_run:
        sched = run_strategy(strat, jobs, now)
        all_schedules[strat] = sched
        print_schedule(sched, strat)

    # ---- Savings report ----
    savings: Optional[SavingsReport] = None
    if "fifo" in all_schedules and "cost-optimal" in all_schedules:
        savings = compute_savings(jobs, "fifo", "cost-optimal", now)
        print(f"\n{'='*60}")
        print("SAVINGS SUMMARY")
        print(str(savings))

    # ---- HTML output ----
    if args.output:
        html = build_html_report(jobs, all_schedules, savings, now)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"\nHTML report written to: {out_path}")

    # ---- Mark as scheduled in DB (unless dry-run) ----
    if args.schedule and not args.dry_run:
        for strat in strategies_to_run:
            for sj in all_schedules[strat]:
                queue.update_status(sj.job.job_id, "scheduled")
        print(f"Marked {len(jobs)} jobs as scheduled in DB.")


if __name__ == "__main__":
    main()
