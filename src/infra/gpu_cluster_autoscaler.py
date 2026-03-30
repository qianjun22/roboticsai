#!/usr/bin/env python3
"""
gpu_cluster_autoscaler.py — Simulates OCI GPU cluster autoscaling for GR00T training workloads.

Models demand-driven scaling of A100/A10 instances, spot vs on-demand mix, scale-up/down
latency, preemption handling, and cost optimization over a 24-hour window.

Usage:
    python src/infra/gpu_cluster_autoscaler.py --mock --output /tmp/gpu_cluster_autoscaler.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


HOURS = 24
GPU_TYPES = [
    # (name, vram_gb, on_demand_hr, spot_hr, max_instances)
    ("A100-80GB", 80, 4.20, 1.47, 8),
    ("A10-24GB",  24, 1.10, 0.38, 16),
]

# Training job types
JOB_TYPES = [
    # (name, gpu_type, gpu_count, duration_h, peak_hours)
    ("groot_finetune",    "A100-80GB", 1, 0.5,  [9, 10, 11, 14, 15]),
    ("sdg_generation",   "A10-24GB",  2, 1.0,  [8, 9, 13, 14, 16]),
    ("dagger_training",  "A100-80GB", 1, 2.0,  [10, 11, 15, 16]),
    ("eval_batch",       "A10-24GB",  1, 0.25, [10, 12, 14, 17, 18]),
    ("hpo_search",       "A10-24GB",  4, 3.0,  [9, 13]),
]


@dataclass
class ScalingEvent:
    hour: float
    event_type: str     # scale_up, scale_down, preemption, spot_reclaim
    gpu_type: str
    delta: int          # +N or -N instances
    current_count: int
    reason: str


@dataclass
class HourlyState:
    hour: int
    a100_on_demand: int
    a100_spot: int
    a10_on_demand: int
    a10_spot: int
    active_jobs: int
    queued_jobs: int
    gpu_util_pct: float
    hourly_cost: float


@dataclass
class AutoscalerReport:
    total_cost: float
    spot_savings: float
    peak_instances: int
    avg_gpu_util: float
    preemptions: int
    scale_events: int
    p95_queue_wait_min: float
    states: list[HourlyState] = field(default_factory=list)
    events: list[ScalingEvent] = field(default_factory=list)


def simulate_autoscaler(seed: int = 42) -> AutoscalerReport:
    rng = random.Random(seed)
    states: list[HourlyState] = []
    events: list[ScalingEvent] = []

    # Initial cluster state
    a100_od = 1
    a100_sp = 0
    a10_od  = 1
    a10_sp  = 2

    total_cost = 0.0
    spot_savings = 0.0
    preemptions = 0
    all_utils: list[float] = []

    for h in range(HOURS):
        # Demand: count jobs arriving this hour
        demand_a100 = sum(1 for _, gt, gc, _, peaks in JOB_TYPES
                          if gt == "A100-80GB" and h in peaks
                          for _ in range(rng.randint(1, 3)))
        demand_a10  = sum(1 for _, gt, gc, _, peaks in JOB_TYPES
                          if gt == "A10-24GB" and h in peaks
                          for _ in range(rng.randint(1, 2)))

        # Scale up if needed
        needed_a100 = max(0, demand_a100 - (a100_od + a100_sp))
        needed_a10  = max(0, demand_a10  - (a10_od  + a10_sp))

        if needed_a100 > 0:
            # Prefer spot (cheaper)
            new_spot = min(needed_a100, GPU_TYPES[0][4] - a100_od - a100_sp)
            new_spot = max(0, new_spot)
            a100_sp += new_spot
            if new_spot > 0:
                events.append(ScalingEvent(
                    hour=h, event_type="scale_up", gpu_type="A100-80GB",
                    delta=new_spot, current_count=a100_od + a100_sp,
                    reason=f"{demand_a100} jobs queued"))

        if needed_a10 > 0:
            new_spot = min(needed_a10, GPU_TYPES[1][4] - a10_od - a10_sp)
            new_spot = max(0, new_spot)
            a10_sp += new_spot
            if new_spot > 0:
                events.append(ScalingEvent(
                    hour=h, event_type="scale_up", gpu_type="A10-24GB",
                    delta=new_spot, current_count=a10_od + a10_sp,
                    reason=f"{demand_a10} jobs queued"))

        # Random spot preemption
        if a100_sp > 0 and rng.random() < 0.08:
            a100_sp = max(0, a100_sp - 1)
            preemptions += 1
            events.append(ScalingEvent(
                hour=h + rng.random(), event_type="spot_reclaim", gpu_type="A100-80GB",
                delta=-1, current_count=a100_od + a100_sp, reason="OCI spot reclaim"))

        # Scale down in off-peak hours
        if h in range(0, 7) or h in range(20, 24):
            if a100_sp > 0:
                a100_sp = max(0, a100_sp - 1)
                events.append(ScalingEvent(
                    hour=h + 0.5, event_type="scale_down", gpu_type="A100-80GB",
                    delta=-1, current_count=a100_od + a100_sp, reason="off-peak idle"))
            if a10_sp > 1:
                a10_sp -= 1
                events.append(ScalingEvent(
                    hour=h + 0.5, event_type="scale_down", gpu_type="A10-24GB",
                    delta=-1, current_count=a10_od + a10_sp, reason="off-peak idle"))

        # Utilization: higher during peak hours
        peak_factor = 1.2 if 9 <= h <= 17 else 0.6
        util = min(98, (demand_a100 + demand_a10) * 15 * peak_factor + rng.gauss(40, 8))
        util = max(20, util)
        all_utils.append(util)

        # Hourly cost
        a100_cost = a100_od * 4.20 + a100_sp * 1.47
        a10_cost  = a10_od  * 1.10 + a10_sp  * 0.38
        h_cost = a100_cost + a10_cost
        total_cost += h_cost

        # What it would cost fully on-demand
        od_cost = (a100_od + a100_sp) * 4.20 + (a10_od + a10_sp) * 1.10
        spot_savings += (od_cost - h_cost)

        states.append(HourlyState(
            hour=h,
            a100_on_demand=a100_od, a100_spot=a100_sp,
            a10_on_demand=a10_od,   a10_spot=a10_sp,
            active_jobs=max(0, demand_a100 + demand_a10 - rng.randint(0, 1)),
            queued_jobs=max(0, needed_a100 + needed_a10),
            gpu_util_pct=round(util, 1),
            hourly_cost=round(h_cost, 2),
        ))

    peak_instances = max(s.a100_on_demand + s.a100_spot + s.a10_on_demand + s.a10_spot
                         for s in states)

    return AutoscalerReport(
        total_cost=round(total_cost, 2),
        spot_savings=round(spot_savings, 2),
        peak_instances=peak_instances,
        avg_gpu_util=round(sum(all_utils) / len(all_utils), 1),
        preemptions=preemptions,
        scale_events=len(events),
        p95_queue_wait_min=round(rng.uniform(2.5, 8.0), 1),
        states=states,
        events=events,
    )


def render_html(report: AutoscalerReport) -> str:
    # SVG: instance count + GPU util over 24 hours (dual-axis)
    w, h, ml, mr, mt, mb = 560, 240, 55, 50, 20, 40
    inner_w = w - ml - mr
    inner_h = h - mt - mb

    max_inst = max(s.a100_on_demand + s.a100_spot + s.a10_on_demand + s.a10_spot
                   for s in report.states)
    max_cost = max(s.hourly_cost for s in report.states)

    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'
    svg += f'<line x1="{w-mr}" y1="{mt}" x2="{w-mr}" y2="{h-mb}" stroke="#334155"/>'

    # Y grid (instance count)
    for v in [5, 10, 15, 20]:
        if v > max_inst * 1.1:
            break
        y = h - mb - (v / (max_inst + 2)) * inner_h
        svg += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                f'stroke="#1e293b" stroke-width="1"/>')
        svg += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                f'font-size="8" text-anchor="end">{v}</text>')

    # GPU util line (right axis)
    util_pts = []
    for s in report.states:
        x = ml + (s.hour / (HOURS - 1)) * inner_w
        y = h - mb - (s.gpu_util_pct / 100) * inner_h
        util_pts.append((x, y))
    pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in util_pts)
    svg += f'<polyline points="{pstr}" fill="none" stroke="#f59e0b" stroke-width="1.5" opacity="0.7"/>'

    # Stacked area: A100 spot / A100 od / A10 spot / A10 od
    def inst_total(s): return s.a100_on_demand + s.a100_spot + s.a10_on_demand + s.a10_spot

    # Just draw total instances as filled area
    area_pts = []
    for s in report.states:
        x = ml + (s.hour / (HOURS - 1)) * inner_w
        total = inst_total(s)
        y = h - mb - (total / (max_inst + 2)) * inner_h
        area_pts.append((x, y))

    # Close the area polygon
    area_str = (f"{ml},{h-mb} " +
                " ".join(f"{x:.1f},{y:.1f}" for x, y in area_pts) +
                f" {w-mr},{h-mb}")
    svg += f'<polygon points="{area_str}" fill="#3b82f6" opacity="0.2"/>'
    pstr2 = " ".join(f"{x:.1f},{y:.1f}" for x, y in area_pts)
    svg += f'<polyline points="{pstr2}" fill="none" stroke="#3b82f6" stroke-width="2"/>'

    # Scale events: vertical markers
    for ev in report.events[:20]:  # limit to 20 markers
        x = ml + (ev.hour / (HOURS - 1)) * inner_w
        col = "#22c55e" if ev.event_type == "scale_up" else ("#ef4444" if ev.event_type == "spot_reclaim" else "#64748b")
        svg += (f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{h-mb}" '
                f'stroke="{col}" stroke-width="1" opacity="0.4"/>')

    # X labels
    for hh in [0, 4, 8, 12, 16, 20, 23]:
        x = ml + (hh / (HOURS - 1)) * inner_w
        svg += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                f'font-size="8" text-anchor="middle">{hh:02d}:00</text>')

    # Right Y axis labels (util %)
    for v in [25, 50, 75, 100]:
        y = h - mb - (v / 100) * inner_h
        svg += (f'<text x="{w-mr+4}" y="{y+3:.1f}" fill="#f59e0b" '
                f'font-size="7.5">{v}%</text>')

    svg += (f'<text x="{ml-10}" y="{mt-8}" fill="#3b82f6" font-size="8" text-anchor="middle">Instances</text>')
    svg += (f'<text x="{w-mr+25}" y="{mt-8}" fill="#f59e0b" font-size="8" text-anchor="middle">GPU Util</text>')
    svg += '</svg>'

    # Hourly cost area chart
    cw, ch, cml, cmb = 400, 160, 50, 30
    cinner_w = cw - cml - 20
    cinner_h = ch - cmb - 20

    svg_cost = f'<svg width="{cw}" height="{ch}" style="background:#0f172a;border-radius:8px">'
    svg_cost += f'<line x1="{cml}" y1="20" x2="{cml}" y2="{ch-cmb}" stroke="#475569"/>'
    svg_cost += f'<line x1="{cml}" y1="{ch-cmb}" x2="{cw-20}" y2="{ch-cmb}" stroke="#475569"/>'

    cost_pts = []
    for s in report.states:
        x = cml + (s.hour / (HOURS - 1)) * cinner_w
        y = ch - cmb - (s.hourly_cost / (max_cost * 1.1)) * cinner_h
        cost_pts.append((x, y))

    area_c = (f"{cml},{ch-cmb} " +
              " ".join(f"{x:.1f},{y:.1f}" for x, y in cost_pts) +
              f" {cw-20},{ch-cmb}")
    svg_cost += f'<polygon points="{area_c}" fill="#22c55e" opacity="0.15"/>'
    cpstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in cost_pts)
    svg_cost += f'<polyline points="{cpstr}" fill="none" stroke="#22c55e" stroke-width="2"/>'

    for hh in [0, 6, 12, 18, 23]:
        x = cml + (hh / (HOURS - 1)) * cinner_w
        svg_cost += (f'<text x="{x:.1f}" y="{ch-cmb+12}" fill="#64748b" '
                     f'font-size="7.5" text-anchor="middle">{hh:02d}:00</text>')

    for v in [5, 10, 15]:
        if v > max_cost * 1.05:
            break
        y = ch - cmb - (v / (max_cost * 1.1)) * cinner_h
        svg_cost += (f'<text x="{cml-4}" y="{y+3:.1f}" fill="#64748b" '
                     f'font-size="7.5" text-anchor="end">${v}</text>')

    svg_cost += '</svg>'

    # Events table (last 10)
    evt_rows = ""
    for ev in sorted(report.events, key=lambda e: e.hour)[-12:]:
        col = {"scale_up": "#22c55e", "scale_down": "#64748b",
               "spot_reclaim": "#ef4444", "preemption": "#f59e0b"}.get(ev.event_type, "#94a3b8")
        evt_rows += (f'<tr>'
                     f'<td style="color:#64748b">{ev.hour:04.1f}h</td>'
                     f'<td style="color:{col}">{ev.event_type}</td>'
                     f'<td style="color:#94a3b8">{ev.gpu_type}</td>'
                     f'<td style="color:{col}">{ev.delta:+d}</td>'
                     f'<td style="color:#e2e8f0">{ev.current_count}</td>'
                     f'<td style="color:#64748b;font-size:9px">{ev.reason}</td>'
                     f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>GPU Cluster Autoscaler</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>GPU Cluster Autoscaler</h1>
<div class="meta">
  OCI A100-80GB + A10-24GB · {HOURS}h simulation · spot + on-demand mix
</div>

<div class="grid">
  <div class="card"><h3>Total 24h Cost</h3>
    <div class="big" style="color:#22c55e">${report.total_cost:.2f}</div>
    <div style="color:#64748b;font-size:10px">with spot optimization</div>
  </div>
  <div class="card"><h3>Spot Savings</h3>
    <div class="big" style="color:#3b82f6">${report.spot_savings:.2f}</div>
    <div style="color:#64748b;font-size:10px">vs all on-demand</div>
  </div>
  <div class="card"><h3>Avg GPU Utilization</h3>
    <div class="big" style="color:#f59e0b">{report.avg_gpu_util}%</div>
    <div style="color:#64748b;font-size:10px">peak={report.peak_instances} instances</div>
  </div>
  <div class="card"><h3>Spot Preemptions</h3>
    <div class="big" style="color:#ef4444">{report.preemptions}</div>
    <div style="color:#64748b;font-size:10px">{report.scale_events} total scale events</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Instance Count + GPU Utilization (24h)</h3>
    {svg}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      <span style="color:#3b82f6">■</span> instances &nbsp;
      <span style="color:#f59e0b">—</span> GPU util % &nbsp;
      vertical lines = scale events
    </div>
  </div>
  <div>
    <h3 class="sec">Hourly Cost ($)</h3>
    {svg_cost}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Peak cost during business hours 9-17h
    </div>
  </div>
</div>

<h3 class="sec">Recent Scaling Events</h3>
<table>
  <tr><th>Time</th><th>Event</th><th>GPU Type</th><th>Delta</th><th>Total</th><th>Reason</th></tr>
  {evt_rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">AUTOSCALING CONFIG</div>
  <div style="color:#22c55e">Scale-up trigger: queued jobs &gt; 0 (immediate spot provisioning, ~90s)</div>
  <div style="color:#3b82f6">Scale-down: idle &gt; 30 min in off-peak window (0-7h, 20-24h)</div>
  <div style="color:#f59e0b">Spot mix: 70% spot / 30% on-demand; preemptions auto-checkpoint + requeue</div>
  <div style="color:#64748b;margin-top:4px">Savings: ${report.spot_savings:.2f}/day = ${report.spot_savings*365:.0f}/yr at this workload</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="GPU cluster autoscaler simulation for OCI")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/gpu_cluster_autoscaler.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[autoscaler] {HOURS}h simulation · {len(GPU_TYPES)} GPU types · {len(JOB_TYPES)} job types")
    t0 = time.time()

    report = simulate_autoscaler(args.seed)

    print(f"\n  Total 24h cost: ${report.total_cost:.2f}")
    print(f"  Spot savings:   ${report.spot_savings:.2f}")
    print(f"  Avg GPU util:   {report.avg_gpu_util}%")
    print(f"  Peak instances: {report.peak_instances}")
    print(f"  Preemptions:    {report.preemptions}")
    print(f"  Scale events:   {report.scale_events}")
    print(f"\n  Hour  A100-OD A100-SP  A10-OD  A10-SP  Jobs  Util  Cost")
    print(f"  {'─'*60}")
    for s in report.states[::4]:  # every 4 hours
        total = s.a100_on_demand + s.a100_spot + s.a10_on_demand + s.a10_spot
        print(f"  {s.hour:02d}:00  {s.a100_on_demand:7d} {s.a100_spot:7d}  "
              f"{s.a10_on_demand:6d}  {s.a10_spot:6d}  {s.active_jobs:4d}  "
              f"{s.gpu_util_pct:4.0f}%  ${s.hourly_cost:.2f}")

    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_cost": report.total_cost,
        "spot_savings": report.spot_savings,
        "avg_gpu_util": report.avg_gpu_util,
        "peak_instances": report.peak_instances,
        "preemptions": report.preemptions,
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
