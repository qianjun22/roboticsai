#!/usr/bin/env python3
"""
oci_compute_scheduler.py — OCI compute job scheduler for Robot Cloud workloads.

Manages GPU job queuing, spot instance bidding, preemption handling, and
priority-based scheduling across fine-tune / DAgger / eval / inference job types.
Simulates the OCI A100 GPU4 fleet with spot vs on-demand allocation.

Usage:
    python src/infra/oci_compute_scheduler.py --mock --output /tmp/oci_scheduler.html
    python src/infra/oci_compute_scheduler.py --jobs 20 --seed 7
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────────

GPU_TYPES = {
    "A100-80G": {"vram_gb": 80, "on_demand_hr": 4.20, "spot_hr": 1.47, "count": 4},
    "A10-24G":  {"vram_gb": 24, "on_demand_hr": 1.20, "spot_hr": 0.42, "count": 8},
    "V100-16G": {"vram_gb": 16, "on_demand_hr": 0.90, "spot_hr": 0.31, "count": 4},
}

JOB_TYPES = {
    "finetune":   {"priority": 3, "min_vram_gb": 20, "preferred_gpu": "A100-80G", "avg_hours": 2.5},
    "dagger":     {"priority": 4, "min_vram_gb": 24, "preferred_gpu": "A100-80G", "avg_hours": 8.0},
    "eval":       {"priority": 2, "min_vram_gb": 8,  "preferred_gpu": "A10-24G",  "avg_hours": 0.5},
    "inference":  {"priority": 5, "min_vram_gb": 8,  "preferred_gpu": "A10-24G",  "avg_hours": 0.25},
    "sdg":        {"priority": 1, "min_vram_gb": 16, "preferred_gpu": "V100-16G", "avg_hours": 4.0},
}

STATUSES = ["queued", "running", "completed", "preempted", "failed"]

PARTNERS = ["agility", "figure", "boston_dynamics", "internal"]


@dataclass
class ComputeJob:
    job_id: str
    partner: str
    job_type: str
    gpu_type: str
    gpu_count: int
    spot: bool
    priority: int
    vram_required_gb: float
    estimated_hours: float
    actual_hours: float
    status: str
    cost_usd: float
    queued_at: int       # minute offset from sim start
    started_at: int
    ended_at: int
    preempt_count: int


@dataclass
class SchedulerState:
    total_jobs: int
    completed: int
    preempted: int
    failed: int
    total_cost: float
    spot_savings: float
    avg_queue_wait_min: float
    gpu_utilization: dict[str, float]   # gpu_type -> utilization %
    jobs: list[ComputeJob] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_scheduler(n_jobs: int = 20, seed: int = 42) -> SchedulerState:
    rng = random.Random(seed)
    jobs = []

    # Simulate 24h window in 1-minute ticks
    sim_minutes = 1440
    gpu_busy_until: dict[str, list[int]] = {
        "A100-80G": [0] * GPU_TYPES["A100-80G"]["count"],
        "A10-24G":  [0] * GPU_TYPES["A10-24G"]["count"],
        "V100-16G": [0] * GPU_TYPES["V100-16G"]["count"],
    }

    for i in range(n_jobs):
        job_type = rng.choice(list(JOB_TYPES.keys()))
        jcfg = JOB_TYPES[job_type]
        partner = rng.choice(PARTNERS)

        # Spot preference by job type
        use_spot = job_type in ("sdg", "finetune") and rng.random() < 0.65

        gpu_type = jcfg["preferred_gpu"]
        gcfg = GPU_TYPES[gpu_type]
        gpu_count = 1 if job_type in ("eval", "inference") else (
            rng.choice([1, 2, 4]) if job_type == "dagger" else 1
        )

        queued_at = rng.randint(0, sim_minutes - 60)

        # Find first available GPU slot
        available = sorted(enumerate(gpu_busy_until[gpu_type]), key=lambda x: x[1])
        slot_idx, slot_free = available[0]
        started_at = max(queued_at + rng.randint(1, 15), slot_free)

        actual_hours = max(0.1, jcfg["avg_hours"] * rng.uniform(0.7, 1.4))
        ended_at = started_at + int(actual_hours * 60)

        # Preemption: spot jobs can get preempted
        preempt_count = 0
        status = "completed"
        if use_spot and rng.random() < 0.12:
            status = "preempted"
            preempt_count = rng.randint(1, 3)
            actual_hours *= 0.4  # only partial completion

        if rng.random() < 0.03:
            status = "failed"
            actual_hours *= 0.1

        # Mark GPU busy
        gpu_busy_until[gpu_type][slot_idx] = ended_at

        rate = gcfg["spot_hr"] if use_spot else gcfg["on_demand_hr"]
        cost = actual_hours * rate * gpu_count
        spot_savings = actual_hours * (gcfg["on_demand_hr"] - gcfg["spot_hr"]) * gpu_count if use_spot else 0.0

        jobs.append(ComputeJob(
            job_id=f"job-{i+1:04d}",
            partner=partner,
            job_type=job_type,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            spot=use_spot,
            priority=jcfg["priority"],
            vram_required_gb=jcfg["min_vram_gb"],
            estimated_hours=jcfg["avg_hours"],
            actual_hours=round(actual_hours, 2),
            status=status,
            cost_usd=round(cost, 4),
            queued_at=queued_at,
            started_at=started_at,
            ended_at=min(ended_at, sim_minutes),
            preempt_count=preempt_count,
        ))

    completed = [j for j in jobs if j.status == "completed"]
    preempted = [j for j in jobs if j.status == "preempted"]
    failed = [j for j in jobs if j.status == "failed"]

    total_cost = sum(j.cost_usd for j in jobs)
    spot_savings = sum(
        j.actual_hours * (GPU_TYPES[j.gpu_type]["on_demand_hr"] - GPU_TYPES[j.gpu_type]["spot_hr"]) * j.gpu_count
        for j in jobs if j.spot
    )
    avg_wait = sum(j.started_at - j.queued_at for j in jobs) / len(jobs)

    # GPU utilization
    gpu_util = {}
    for gtype in GPU_TYPES:
        gpu_minutes = sum(j.actual_hours * 60 * j.gpu_count for j in jobs if j.gpu_type == gtype)
        available_minutes = sim_minutes * GPU_TYPES[gtype]["count"]
        gpu_util[gtype] = round(min(100.0, gpu_minutes / available_minutes * 100), 1)

    return SchedulerState(
        total_jobs=len(jobs),
        completed=len(completed),
        preempted=len(preempted),
        failed=len(failed),
        total_cost=round(total_cost, 2),
        spot_savings=round(spot_savings, 2),
        avg_queue_wait_min=round(avg_wait, 1),
        gpu_utilization=gpu_util,
        jobs=jobs,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(state: SchedulerState) -> str:
    # SVG: job type distribution stacked bar
    type_counts = {}
    for jt in JOB_TYPES:
        type_counts[jt] = sum(1 for j in state.jobs if j.job_type == jt)

    TYPE_COLORS = {
        "finetune": "#3b82f6", "dagger": "#C74634", "eval": "#22c55e",
        "inference": "#a855f7", "sdg": "#f59e0b"
    }

    w_dist, h_dist = 460, 60
    total = state.total_jobs
    svg_dist = f'<svg width="{w_dist}" height="{h_dist}" style="background:#0f172a;border-radius:8px">'
    x_off = 10
    for jt, cnt in type_counts.items():
        bw = (cnt / total) * (w_dist - 20)
        col = TYPE_COLORS[jt]
        svg_dist += (f'<rect x="{x_off:.1f}" y="10" width="{bw:.1f}" height="25" '
                     f'fill="{col}" rx="2" opacity="0.85"/>')
        if bw > 30:
            svg_dist += (f'<text x="{x_off+bw/2:.1f}" y="27" fill="#fff" font-size="9" '
                         f'text-anchor="middle">{jt} ({cnt})</text>')
        x_off += bw

    # Legend
    lx = 10
    for jt, col in TYPE_COLORS.items():
        if type_counts.get(jt, 0) > 0:
            svg_dist += (f'<rect x="{lx}" y="42" width="8" height="8" fill="{col}"/>')
            svg_dist += (f'<text x="{lx+10}" y="50" fill="#94a3b8" font-size="8">{jt}</text>')
            lx += 65

    svg_dist += '</svg>'

    # GPU util bars
    w_gpu, h_gpu = 280, 90
    svg_gpu = f'<svg width="{w_gpu}" height="{h_gpu}" style="background:#0f172a;border-radius:8px">'
    for i, (gtype, util) in enumerate(state.gpu_utilization.items()):
        y = 12 + i * 25
        bw = util / 100 * (w_gpu - 100)
        col = "#22c55e" if util > 60 else "#f59e0b" if util > 30 else "#ef4444"
        svg_gpu += (f'<rect x="90" y="{y}" width="{bw:.1f}" height="16" fill="{col}" rx="2" opacity="0.85"/>')
        svg_gpu += (f'<text x="88" y="{y+12}" fill="#94a3b8" font-size="9" text-anchor="end">{gtype}</text>')
        svg_gpu += (f'<text x="{93+bw:.1f}" y="{y+12}" fill="{col}" font-size="9">{util:.1f}%</text>')
    svg_gpu += '</svg>'

    # Job table (last 20)
    rows = ""
    for j in sorted(state.jobs, key=lambda x: x.queued_at)[-20:]:
        st_col = {"completed": "#22c55e", "preempted": "#f59e0b",
                  "failed": "#ef4444", "running": "#3b82f6", "queued": "#64748b"}.get(j.status, "#94a3b8")
        spot_badge = (' <span style="background:#0f4c81;color:#93c5fd;padding:1px 4px;'
                      'border-radius:3px;font-size:9px">SPOT</span>') if j.spot else ""
        rows += (f'<tr>'
                 f'<td style="color:#94a3b8">{j.job_id}</td>'
                 f'<td style="color:#e2e8f0">{j.partner}</td>'
                 f'<td style="color:{TYPE_COLORS.get(j.job_type,"#94a3b8")}">{j.job_type}</td>'
                 f'<td style="color:#64748b">{j.gpu_type} ×{j.gpu_count}{spot_badge}</td>'
                 f'<td style="color:#e2e8f0">{j.actual_hours:.2f}h</td>'
                 f'<td style="color:#3b82f6">${j.cost_usd:.3f}</td>'
                 f'<td style="color:{st_col}">{j.status}</td>'
                 f'</tr>')

    success_rate = round(state.completed / state.total_jobs * 100, 1)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>OCI Compute Scheduler</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>OCI Compute Scheduler</h1>
<div class="meta">
  24h simulation · {state.total_jobs} jobs · A100-80G ×{GPU_TYPES["A100-80G"]["count"]} + A10-24G ×{GPU_TYPES["A10-24G"]["count"]} + V100-16G ×{GPU_TYPES["V100-16G"]["count"]}
</div>

<div class="grid">
  <div class="card"><h3>Success Rate</h3>
    <div class="big" style="color:{'#22c55e' if success_rate > 90 else '#f59e0b'}">{success_rate}%</div>
    <div style="color:#64748b;font-size:11px">{state.completed} / {state.total_jobs} completed</div>
  </div>
  <div class="card"><h3>Total Compute Cost</h3>
    <div class="big" style="color:#3b82f6">${state.total_cost:.2f}</div>
    <div style="color:#64748b;font-size:11px">24h window</div>
  </div>
  <div class="card"><h3>Spot Savings</h3>
    <div class="big" style="color:#22c55e">${state.spot_savings:.2f}</div>
    <div style="color:#64748b;font-size:11px">vs on-demand pricing</div>
  </div>
  <div class="card"><h3>Avg Queue Wait</h3>
    <div class="big" style="color:#a855f7">{state.avg_queue_wait_min:.1f}m</div>
    <div style="color:#64748b;font-size:11px">preempted: {state.preempted} · failed: {state.failed}</div>
  </div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      Job Type Distribution
    </h3>
    {svg_dist}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      GPU Utilization
    </h3>
    {svg_gpu}
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Recent Jobs (last 20)
</h3>
<table>
  <tr><th>Job ID</th><th>Partner</th><th>Type</th><th>GPU</th><th>Duration</th><th>Cost</th><th>Status</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Spot instances: 65% of finetune/SDG jobs use spot pricing (3× cheaper) with &lt;12% preemption rate.<br>
  DAgger jobs run on-demand only (preemption would waste expensive rollout data).<br>
  A100-80G reserved for DAgger + large fine-tune; A10-24G for eval + inference serving.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OCI compute scheduler simulation")
    parser.add_argument("--mock",    action="store_true", default=True)
    parser.add_argument("--jobs",    type=int, default=20)
    parser.add_argument("--seed",    type=int, default=42)
    parser.add_argument("--output",  default="/tmp/oci_scheduler.html")
    args = parser.parse_args()

    print(f"[oci-scheduler] Simulating {args.jobs} jobs over 24h")
    t0 = time.time()

    state = simulate_scheduler(args.jobs, args.seed)

    print(f"\n  Jobs: {state.total_jobs}  Completed: {state.completed}  "
          f"Preempted: {state.preempted}  Failed: {state.failed}")
    print(f"  Total cost: ${state.total_cost:.2f}  Spot savings: ${state.spot_savings:.2f}")
    print(f"  Avg queue wait: {state.avg_queue_wait_min:.1f} min")
    print(f"\n  GPU Utilization:")
    for gtype, util in state.gpu_utilization.items():
        bar = "█" * int(util / 5) + "░" * (20 - int(util / 5))
        print(f"    {gtype:<12} {bar} {util:.1f}%")
    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(state)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "summary": {
            "total_jobs": state.total_jobs,
            "completed": state.completed,
            "preempted": state.preempted,
            "failed": state.failed,
            "total_cost_usd": state.total_cost,
            "spot_savings_usd": state.spot_savings,
            "avg_queue_wait_min": state.avg_queue_wait_min,
            "gpu_utilization": state.gpu_utilization,
        }
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
