"""
Data collection schedule manager for GR00T fine-tuning.
Coordinates SDG, teleoperation, and DAgger sessions across GPU resources.
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CollectionJob:
    job_id: str
    job_type: str          # sdg | teleoperation | dagger
    task_name: str
    target_demos: int
    collected_demos: int
    scheduled_start: float  # unix timestamp; 0.0 = unscheduled
    estimated_duration_h: float
    gpu_required: str       # A100 | A10 | none
    status: str             # scheduled | running | done | failed
    depends_on: Optional[str] = None  # job_id of prerequisite


@dataclass
class ScheduleWindow:
    date_str: str            # YYYY-MM-DD
    available_gpu_h: float
    jobs_scheduled: List[CollectionJob] = field(default_factory=list)
    utilization_pct: float = 0.0


@dataclass
class ScheduleReport:
    total_target_demos: int
    total_scheduled: int
    completion_pct: float
    bottleneck: str
    schedule: List[ScheduleWindow]


# ---------------------------------------------------------------------------
# GPU resource constants
# ---------------------------------------------------------------------------

GPU_CAPACITY = {
    "A100": 1,   # 1 unit available
    "A10":  2,   # 2 units available
    "none": 999, # human operator — unlimited GPU slots
}

# Available GPU-hours per day per type (units × 24h)
GPU_HOURS_PER_DAY = {k: v * 24 for k, v in GPU_CAPACITY.items()}


# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

def make_jobs() -> List[CollectionJob]:
    return [
        CollectionJob(
            job_id="sdg_batch_1",
            job_type="sdg",
            task_name="pick_and_place_v1",
            target_demos=500,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=4.0,
            gpu_required="A10",
            status="scheduled",
        ),
        CollectionJob(
            job_id="sdg_batch_2",
            job_type="sdg",
            task_name="pick_and_place_v2",
            target_demos=500,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=4.0,
            gpu_required="A10",
            status="scheduled",
        ),
        CollectionJob(
            job_id="teleoperation_alpha",
            job_type="teleoperation",
            task_name="stack_cubes_alpha",
            target_demos=50,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=8.0,
            gpu_required="none",
            status="scheduled",
        ),
        CollectionJob(
            job_id="teleoperation_beta",
            job_type="teleoperation",
            task_name="stack_cubes_beta",
            target_demos=50,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=8.0,
            gpu_required="none",
            status="scheduled",
        ),
        CollectionJob(
            job_id="dagger_round1",
            job_type="dagger",
            task_name="pick_and_place_dagger",
            target_demos=200,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=6.0,
            gpu_required="A100",
            status="scheduled",
        ),
        CollectionJob(
            job_id="dagger_round2",
            job_type="dagger",
            task_name="pick_and_place_dagger",
            target_demos=200,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=6.0,
            gpu_required="A100",
            status="scheduled",
            depends_on="dagger_round1",
        ),
        CollectionJob(
            job_id="sdg_hard_cases",
            job_type="sdg",
            task_name="hard_case_recovery",
            target_demos=300,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=3.0,
            gpu_required="A10",
            status="scheduled",
        ),
        CollectionJob(
            job_id="teleoperation_edge",
            job_type="teleoperation",
            task_name="edge_scenario_collection",
            target_demos=30,
            collected_demos=0,
            scheduled_start=0.0,
            estimated_duration_h=5.0,
            gpu_required="none",
            status="scheduled",
        ),
    ]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def schedule_jobs(jobs: List[CollectionJob], start_date: datetime, num_days: int = 14, rng: random.Random = None) -> List[ScheduleWindow]:
    """
    Greedy list-scheduling across 14 days.
    Per day: A100 has 24h capacity, A10 has 48h capacity (2 units), human ops
    have 16h (realistic working hours for teleoperation).
    Respects depends_on ordering.
    """
    if rng is None:
        rng = random.Random(42)

    windows: List[ScheduleWindow] = []
    for d in range(num_days):
        date = start_date + timedelta(days=d)
        windows.append(ScheduleWindow(
            date_str=date.strftime("%Y-%m-%d"),
            available_gpu_h=24.0,  # total GPU-hours reference for utilization calc
        ))

    # Track remaining hours per day per GPU type
    day_remaining = {}
    for d in range(num_days):
        day_remaining[d] = {
            "A100": 1 * 24.0,       # 1 unit × 24h
            "A10":  2 * 24.0,       # 2 units × 24h
            "none": 16.0,           # human operator: 16 working hours/day
        }

    scheduled_job_ids: set = set()
    unscheduled = list(jobs)

    # Topological pass — iterate until all jobs placed or no progress
    max_passes = num_days * len(jobs)
    pass_count = 0

    while unscheduled and pass_count < max_passes:
        pass_count += 1
        progress = False
        still_unscheduled = []

        for job in unscheduled:
            # Check dependency
            if job.depends_on and job.depends_on not in scheduled_job_ids:
                still_unscheduled.append(job)
                continue

            # Find earliest day with enough capacity
            placed = False
            for d in range(num_days):
                gpu = job.gpu_required
                if day_remaining[d].get(gpu, 0) >= job.estimated_duration_h:
                    # Schedule it
                    day_ts = (start_date + timedelta(days=d)).timestamp()
                    # Offset within day based on already-used hours
                    used_h = ({
                        "A100": 24.0,
                        "A10":  48.0,
                        "none": 16.0,
                    }.get(gpu, 24.0)) - day_remaining[d][gpu]
                    job.scheduled_start = day_ts + used_h * 3600
                    job.status = "scheduled"
                    # Simulate collected demos (mock: 85–100% of target)
                    completion_rate = rng.uniform(0.85, 1.0)
                    job.collected_demos = min(job.target_demos, int(job.target_demos * completion_rate))
                    job.status = "done" if job.collected_demos >= job.target_demos else "scheduled"

                    day_remaining[d][gpu] -= job.estimated_duration_h
                    windows[d].jobs_scheduled.append(job)
                    scheduled_job_ids.add(job.job_id)
                    placed = True
                    progress = True
                    break

            if not placed:
                still_unscheduled.append(job)

        unscheduled = still_unscheduled
        if not progress:
            break

    # Mark truly unscheduled jobs as failed
    for job in unscheduled:
        job.status = "failed"

    # Compute utilization per window
    for d, window in enumerate(windows):
        total_gpu_h_used = 0.0
        for job in window.jobs_scheduled:
            gpu = job.gpu_required
            weight = {"A100": 24.0, "A10": 24.0, "none": 0.0}.get(gpu, 0.0)
            total_gpu_h_used += job.estimated_duration_h * (1.0 if gpu != "none" else 0.0)
        # Normalize against total available GPU-hours (A100+A10 = 72h/day)
        total_avail = 1 * 24.0 + 2 * 24.0  # 72
        window.utilization_pct = min(100.0, round(total_gpu_h_used / total_avail * 100, 1))

    return windows


def build_report(jobs: List[CollectionJob], windows: List[ScheduleWindow]) -> ScheduleReport:
    total_target = sum(j.target_demos for j in jobs)
    total_scheduled = sum(j.collected_demos for j in jobs)
    completion_pct = round(total_scheduled / total_target * 100, 1) if total_target else 0.0

    # Find bottleneck: GPU type with most overloaded days
    gpu_demand: dict = {"A100": 0.0, "A10": 0.0, "none": 0.0}
    for job in jobs:
        gpu_demand[job.gpu_required] = gpu_demand.get(job.gpu_required, 0.0) + job.estimated_duration_h
    bottleneck = max(gpu_demand, key=lambda k: gpu_demand[k])
    bottleneck_label = {"A100": "A100 GPU (single unit — DAgger serialized)", "A10": "A10 GPU fleet (SDG parallel)", "none": "Human operator time (teleoperation)"}
    bottleneck = bottleneck_label.get(bottleneck, bottleneck)

    return ScheduleReport(
        total_target_demos=total_target,
        total_scheduled=total_scheduled,
        completion_pct=completion_pct,
        bottleneck=bottleneck,
        schedule=windows,
    )


# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "done":      "#22c55e",
    "scheduled": "#60a5fa",
    "running":   "#f59e0b",
    "failed":    "#ef4444",
}

JOB_TYPE_COLORS = {
    "sdg":           "#3b82f6",  # blue
    "teleoperation": "#22c55e",  # green
    "dagger":        "#f97316",  # orange
}

DAY_PX = 52      # pixels per day column
ROW_H  = 28      # pixels per job row
HEADER_H = 40    # Gantt header height


def _gantt_svg(jobs: List[CollectionJob], windows: List[ScheduleWindow], num_days: int = 14) -> str:
    """Build an SVG Gantt chart."""
    start_date = datetime.strptime(windows[0].date_str, "%Y-%m-%d")
    chart_w = DAY_PX * num_days + 160  # left label area = 160px
    chart_h = HEADER_H + len(jobs) * ROW_H + 20

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{chart_w}" height="{chart_h}" '
        f'style="background:#0f172a;font-family:monospace;">',
    ]

    # Day header labels
    for d in range(num_days):
        x = 160 + d * DAY_PX
        date = start_date + timedelta(days=d)
        label = date.strftime("%m/%d")
        lines.append(
            f'<text x="{x + DAY_PX//2}" y="20" text-anchor="middle" '
            f'fill="#94a3b8" font-size="10">{label}</text>'
        )
        # Vertical grid line
        lines.append(
            f'<line x1="{x}" y1="{HEADER_H}" x2="{x}" y2="{chart_h - 10}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )

    # Jobs
    for i, job in enumerate(jobs):
        y = HEADER_H + i * ROW_H
        mid_y = y + ROW_H // 2

        # Label
        lines.append(
            f'<text x="155" y="{mid_y + 4}" text-anchor="end" '
            f'fill="#cbd5e1" font-size="11">{job.job_id}</text>'
        )

        if job.scheduled_start > 0.0:
            job_dt = datetime.fromtimestamp(job.scheduled_start)
            day_offset = (job_dt - start_date).total_seconds() / 86400
            bar_x = 160 + day_offset * DAY_PX
            bar_w = max(6.0, job.estimated_duration_h / 24.0 * DAY_PX)
            color = JOB_TYPE_COLORS.get(job.job_type, "#94a3b8")
            bar_h = ROW_H - 6

            lines.append(
                f'<rect x="{bar_x:.1f}" y="{y + 3}" width="{bar_w:.1f}" height="{bar_h}" '
                f'rx="3" fill="{color}" opacity="0.85"/>'
            )
            # Demo count label inside bar if wide enough
            if bar_w > 30:
                lines.append(
                    f'<text x="{bar_x + bar_w/2:.1f}" y="{mid_y + 4}" '
                    f'text-anchor="middle" fill="#fff" font-size="9">{job.target_demos}</text>'
                )

            # Status dot
            dot_color = STATUS_COLORS.get(job.status, "#94a3b8")
            lines.append(
                f'<circle cx="{bar_x + bar_w + 8:.1f}" cy="{mid_y}" r="4" fill="{dot_color}"/>'
            )
        else:
            lines.append(
                f'<text x="165" y="{mid_y + 4}" fill="#ef4444" font-size="10">unscheduled</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


def _utilization_svg(windows: List[ScheduleWindow]) -> str:
    """Build a daily GPU-utilization bar chart SVG."""
    chart_w = len(windows) * 44 + 60
    chart_h = 140
    max_pct = 100.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{chart_w}" height="{chart_h}" '
        f'style="background:#0f172a;font-family:monospace;">',
    ]

    # Y-axis labels
    for pct in [0, 25, 50, 75, 100]:
        y = 100 - int(pct * 0.9)
        lines.append(
            f'<text x="30" y="{y + 4}" text-anchor="end" fill="#64748b" font-size="9">{pct}%</text>'
        )
        lines.append(
            f'<line x1="35" y1="{y}" x2="{chart_w}" y2="{y}" stroke="#1e293b" stroke-width="0.5"/>'
        )

    for d, window in enumerate(windows):
        x = 40 + d * 44
        bar_h = int(window.utilization_pct * 0.9)
        bar_y = 100 - bar_h

        # Color gradient by utilization
        if window.utilization_pct >= 80:
            color = "#C74634"
        elif window.utilization_pct >= 50:
            color = "#f97316"
        else:
            color = "#3b82f6"

        lines.append(
            f'<rect x="{x}" y="{bar_y}" width="32" height="{bar_h}" rx="2" fill="{color}" opacity="0.85"/>'
        )
        # Pct label
        if bar_h > 12:
            lines.append(
                f'<text x="{x + 16}" y="{bar_y - 3}" text-anchor="middle" '
                f'fill="#e2e8f0" font-size="9">{window.utilization_pct:.0f}%</text>'
            )
        # Day label
        short_date = window.date_str[5:]  # MM-DD
        lines.append(
            f'<text x="{x + 16}" y="118" text-anchor="middle" '
            f'fill="#64748b" font-size="8" transform="rotate(-30 {x+16} 118)">{short_date}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def generate_html(report: ScheduleReport, jobs: List[CollectionJob], windows: List[ScheduleWindow]) -> str:
    # Compute days to target: first day when cumulative collected_demos >= target
    # Approximate: last scheduled job's day + 1
    scheduled_jobs = [j for j in jobs if j.scheduled_start > 0.0]
    if scheduled_jobs:
        last_ts = max(j.scheduled_start + j.estimated_duration_h * 3600 for j in scheduled_jobs)
        first_ts = min(j.scheduled_start for j in scheduled_jobs)
        days_to_target = math.ceil((last_ts - first_ts) / 86400) + 1
    else:
        days_to_target = "N/A"

    gantt_svg = _gantt_svg(jobs, windows)
    util_svg  = _utilization_svg(windows)

    # Build jobs table rows
    table_rows = []
    for job in jobs:
        if job.scheduled_start > 0.0:
            start_str = datetime.fromtimestamp(job.scheduled_start).strftime("%Y-%m-%d %H:%M")
        else:
            start_str = "—"
        status_color = STATUS_COLORS.get(job.status, "#94a3b8")
        type_color = JOB_TYPE_COLORS.get(job.job_type, "#94a3b8")
        table_rows.append(f"""
        <tr>
          <td style="font-family:monospace;font-size:12px;">{job.job_id}</td>
          <td><span style="background:{type_color}22;color:{type_color};padding:2px 8px;border-radius:4px;font-size:11px;">{job.job_type}</span></td>
          <td style="font-size:12px;">{job.task_name}</td>
          <td style="text-align:right;">{job.target_demos}</td>
          <td style="text-align:right;">{job.collected_demos}</td>
          <td><span style="background:{status_color}22;color:{status_color};padding:2px 8px;border-radius:4px;font-size:11px;">{job.status}</span></td>
          <td style="font-size:11px;font-family:monospace;">{start_str}</td>
          <td style="text-align:right;">{job.estimated_duration_h:.1f}h</td>
          <td style="font-family:monospace;font-size:11px;">{job.gpu_required}</td>
        </tr>""")

    table_html = "\n".join(table_rows)

    completion_color = "#22c55e" if report.completion_pct >= 90 else "#f97316" if report.completion_pct >= 60 else "#ef4444"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Data Collection Scheduler — GR00T Fine-Tuning</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #1e293b;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      padding: 24px;
    }}
    header {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 28px;
      border-bottom: 2px solid #C74634;
      padding-bottom: 16px;
    }}
    .oracle-logo {{
      background: #C74634;
      color: #fff;
      font-size: 13px;
      font-weight: 700;
      padding: 6px 14px;
      border-radius: 4px;
      letter-spacing: 1px;
    }}
    h1 {{ font-size: 20px; color: #f1f5f9; font-weight: 600; }}
    .subtitle {{ font-size: 13px; color: #94a3b8; margin-top: 2px; }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .card {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 18px 20px;
    }}
    .card-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
    .card-value {{ font-size: 26px; font-weight: 700; color: #f1f5f9; }}
    .card-value.green  {{ color: #22c55e; }}
    .card-value.orange {{ color: #f97316; }}
    .card-value.red    {{ color: #C74634; }}
    .card-sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}

    .section {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    .section-title {{
      font-size: 14px;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 16px;
    }}

    .gantt-scroll {{ overflow-x: auto; }}

    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{
      background: #1e293b;
      color: #64748b;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid #334155;
    }}
    td {{
      padding: 9px 12px;
      border-bottom: 1px solid #1e293b;
      color: #cbd5e1;
      vertical-align: middle;
    }}
    tr:hover td {{ background: #1a2744; }}

    .legend {{ display: flex; gap: 20px; margin-bottom: 12px; flex-wrap: wrap; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8; }}
    .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
  </style>
</head>
<body>
  <header>
    <span class="oracle-logo">ORACLE</span>
    <div>
      <h1>Data Collection Scheduler</h1>
      <div class="subtitle">GR00T Fine-Tuning Pipeline — 2-Week Sprint Plan</div>
    </div>
  </header>

  <!-- Stat Cards -->
  <div class="cards">
    <div class="card">
      <div class="card-label">Total Demos Scheduled</div>
      <div class="card-value">{report.total_scheduled:,}</div>
      <div class="card-sub">of {report.total_target_demos:,} target</div>
    </div>
    <div class="card">
      <div class="card-label">Completion %</div>
      <div class="card-value" style="color:{completion_color};">{report.completion_pct:.1f}%</div>
      <div class="card-sub">across all job types</div>
    </div>
    <div class="card">
      <div class="card-label">Bottleneck</div>
      <div class="card-value orange" style="font-size:13px;margin-top:4px;">{report.bottleneck}</div>
      <div class="card-sub">primary constraint</div>
    </div>
    <div class="card">
      <div class="card-label">Days to Target</div>
      <div class="card-value">{days_to_target}</div>
      <div class="card-sub">calendar days (2-week window)</div>
    </div>
  </div>

  <!-- Gantt Chart -->
  <div class="section">
    <div class="section-title">Gantt Chart — Job Schedule</div>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#3b82f6;"></div> SDG</div>
      <div class="legend-item"><div class="legend-dot" style="background:#22c55e;"></div> Teleoperation</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f97316;"></div> DAgger</div>
      <div class="legend-item"><div class="legend-dot" style="background:#22c55e;"></div> Done</div>
      <div class="legend-item"><div class="legend-dot" style="background:#60a5fa;"></div> Scheduled</div>
      <div class="legend-item"><div class="legend-dot" style="background:#ef4444;"></div> Failed</div>
    </div>
    <div class="gantt-scroll">
      {gantt_svg}
    </div>
  </div>

  <!-- Daily Utilization -->
  <div class="section">
    <div class="section-title">Daily GPU Utilization</div>
    <div style="overflow-x:auto;">
      {util_svg}
    </div>
  </div>

  <!-- Jobs Table -->
  <div class="section">
    <div class="section-title">Job Details</div>
    <table>
      <thead>
        <tr>
          <th>Job ID</th>
          <th>Type</th>
          <th>Task</th>
          <th style="text-align:right;">Target</th>
          <th style="text-align:right;">Collected</th>
          <th>Status</th>
          <th>Scheduled Start</th>
          <th style="text-align:right;">Est. Duration</th>
          <th>GPU</th>
        </tr>
      </thead>
      <tbody>
        {table_html}
      </tbody>
    </table>
  </div>

  <footer style="text-align:center;color:#334155;font-size:11px;margin-top:16px;">
    Generated by data_collection_scheduler.py — OCI Robot Cloud | GR00T Fine-Tuning Infrastructure
  </footer>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Stdout summary
# ---------------------------------------------------------------------------

def print_summary(report: ScheduleReport, jobs: List[CollectionJob]) -> None:
    print("=" * 64)
    print("  Data Collection Scheduler — 2-Week Sprint Summary")
    print("=" * 64)
    print(f"  Total target demos  : {report.total_target_demos:,}")
    print(f"  Total scheduled     : {report.total_scheduled:,}")
    print(f"  Completion          : {report.completion_pct:.1f}%")
    print(f"  Bottleneck          : {report.bottleneck}")
    print()
    print(f"  {'Job ID':<26} {'Type':<14} {'Target':>7} {'Collected':>10} {'Status':<12} {'GPU':<8}")
    print(f"  {'-'*26} {'-'*14} {'-'*7} {'-'*10} {'-'*12} {'-'*8}")
    for job in jobs:
        start_str = (
            datetime.fromtimestamp(job.scheduled_start).strftime("%m/%d %H:%M")
            if job.scheduled_start > 0.0
            else "—"
        )
        print(
            f"  {job.job_id:<26} {job.job_type:<14} {job.target_demos:>7} "
            f"{job.collected_demos:>10} {job.status:<12} {job.gpu_required:<8}"
        )
    print()
    print("  Schedule Windows:")
    print(f"  {'Date':<12} {'Jobs':>4} {'Utilization':>12}")
    print(f"  {'-'*12} {'-'*4} {'-'*12}")
    for w in report.schedule:
        n = len(w.jobs_scheduled)
        print(f"  {w.date_str:<12} {n:>4}   {w.utilization_pct:>6.1f}%")
    print("=" * 64)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Data Collection Scheduler for GR00T fine-tuning pipeline."
    )
    parser.add_argument("--mock",   action="store_true", help="Use mock data (default behavior)")
    parser.add_argument("--output", default="/tmp/data_collection_scheduler.html",
                        help="Output HTML path (default: /tmp/data_collection_scheduler.html)")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed for mock data")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Base date: today (or fixed for reproducibility with seed)
    start_date = datetime(2026, 3, 30, 8, 0, 0)  # Monday 08:00

    jobs = make_jobs()
    windows = schedule_jobs(jobs, start_date, num_days=14, rng=rng)
    report  = build_report(jobs, windows)

    print_summary(report, jobs)

    html = generate_html(report, jobs, windows)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"\n  HTML report written to: {args.output}")


if __name__ == "__main__":
    main()
