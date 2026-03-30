"""
OCI Multi-Region Failover System for GR00T Inference
=====================================================
Monitors OCI regions, detects failures, routes traffic to healthy regions,
and generates HTML failover reports with SVG charts.

Standalone — stdlib + numpy only.
"""

from __future__ import annotations

import math
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

@dataclass
class RegionStatus:
    region_id: str
    display_name: str
    gpu_type: str
    endpoint: str
    latency_ms: float
    capacity_pct: float
    healthy: bool
    last_check: datetime
    active_requests: int
    error_rate_pct: float


@dataclass
class FailoverEvent:
    event_id: str
    timestamp: datetime
    from_region: str
    to_region: str
    reason: str
    requests_migrated: int
    recovery_time_s: float


@dataclass
class TrafficAllocation:
    region_id: str
    traffic_pct: float
    request_count_last_hour: int


REGIONS: List[Dict] = [
    {"region_id": "us-ashburn-1", "display_name": "US East (Ashburn)", "gpu_type": "A100 80GB",
     "endpoint": "138.1.153.110", "base_latency_ms": 226.0, "capacity_pct": 100.0, "priority": 0},
    {"region_id": "us-phoenix-1", "display_name": "US West (Phoenix)", "gpu_type": "A100 40GB",
     "endpoint": "152.67.82.44", "base_latency_ms": 241.0, "capacity_pct": 60.0, "priority": 1},
    {"region_id": "eu-frankfurt-1", "display_name": "EU Central (Frankfurt)", "gpu_type": "A10 GPU",
     "endpoint": "130.61.48.72", "base_latency_ms": 312.0, "capacity_pct": 40.0, "priority": 2},
    {"region_id": "ap-tokyo-1", "display_name": "AP East (Tokyo)", "gpu_type": "Not provisioned",
     "endpoint": "N/A", "base_latency_ms": 0.0, "capacity_pct": 0.0, "priority": 3},
]

SIM_START = datetime(2026, 3, 15, 0, 0, 0)
SIM_HOURS = 72
CHECK_INTERVAL_MIN = 5

FAILURE_EVENTS = [
    ("us-ashburn-1", 2.0, 23, "down"),
    ("us-phoenix-1", 5 * 24 + 14.5, 8, "down"),
    ("eu-frankfurt-1", 10 * 24 + 9.0, 45, "brownout"),
]


def make_initial_status(rdef: Dict, t: datetime) -> RegionStatus:
    rng = random.Random(rdef["region_id"])
    return RegionStatus(
        region_id=rdef["region_id"], display_name=rdef["display_name"],
        gpu_type=rdef["gpu_type"], endpoint=rdef["endpoint"],
        latency_ms=rdef["base_latency_ms"] + rng.uniform(-5, 5),
        capacity_pct=rdef["capacity_pct"],
        healthy=rdef["capacity_pct"] > 0,
        last_check=t,
        active_requests=int(rdef["capacity_pct"] * 0.4),
        error_rate_pct=0.5 if rdef["capacity_pct"] > 0 else 100.0,
    )


def is_in_failure(region_id: str, t: datetime) -> Tuple[bool, str]:
    for fid, start_h, dur_min, ftype in FAILURE_EVENTS:
        if fid != region_id:
            continue
        fs = SIM_START + timedelta(hours=start_h)
        fe = fs + timedelta(minutes=dur_min)
        if fs <= t < fe:
            return True, ftype
    return False, ""


def simulate() -> Tuple[List[Dict], List[FailoverEvent], List[TrafficAllocation]]:
    total_checks = (SIM_HOURS * 60) // CHECK_INTERVAL_MIN
    rng = random.Random(42)
    status: Dict[str, RegionStatus] = {}
    for rdef in REGIONS:
        status[rdef["region_id"]] = make_initial_status(rdef, SIM_START)
    consec_healthy: Dict[str, int] = {r["region_id"]: 3 for r in REGIONS}
    timeline: List[Dict] = []
    failover_events: List[FailoverEvent] = []
    current_primary = "us-ashburn-1"
    region_priority = [r["region_id"] for r in sorted(REGIONS, key=lambda x: x["priority"]) if r["capacity_pct"] > 0]
    total_rpm = 120
    traffic_counts: Dict[str, int] = {r["region_id"]: 0 for r in REGIONS}

    for check_idx in range(total_checks):
        t = SIM_START + timedelta(minutes=check_idx * CHECK_INTERVAL_MIN)
        for rdef in REGIONS:
            rid = rdef["region_id"]
            if rdef["capacity_pct"] == 0:
                status[rid].healthy = False
                status[rid].error_rate_pct = 100.0
                timeline.append({"time": t, "region_id": rid, "healthy": False, "error_rate": 100.0, "latency": 0.0, "degraded": False})
                continue
            in_fail, ftype = is_in_failure(rid, t)
            if in_fail and ftype == "down":
                status[rid].healthy = False
                status[rid].error_rate_pct = 100.0
                status[rid].latency_ms = 9999.0
                consec_healthy[rid] = 0
                degraded = False
            elif in_fail and ftype == "brownout":
                status[rid].healthy = False
                status[rid].error_rate_pct = 40.0
                status[rid].latency_ms = rdef["base_latency_ms"] * 1.8
                consec_healthy[rid] = 0
                degraded = True
            else:
                consec_healthy[rid] += 1
                if consec_healthy[rid] >= 3:
                    status[rid].healthy = True
                status[rid].error_rate_pct = max(0.0, rng.gauss(0.5, 0.2))
                status[rid].latency_ms = rdef["base_latency_ms"] + rng.gauss(0, 4)
                degraded = False
            timeline.append({"time": t, "region_id": rid, "healthy": status[rid].healthy,
                             "error_rate": status[rid].error_rate_pct, "latency": status[rid].latency_ms, "degraded": degraded})

        best_region = None
        for rid in region_priority:
            if status[rid].healthy:
                best_region = rid
                break
        if best_region is None:
            best_region = "eu-frankfurt-1"

        if best_region != current_primary:
            old_region = current_primary
            reqs_migrated = int(rng.uniform(40, 80))
            recovery_time_s = rng.uniform(12, 25)
            failover_events.append(FailoverEvent(
                event_id=str(uuid.uuid4())[:8], timestamp=t,
                from_region=old_region, to_region=best_region,
                reason=_failover_reason(old_region, status[old_region]),
                requests_migrated=reqs_migrated, recovery_time_s=recovery_time_s,
            ))
            current_primary = best_region
        traffic_counts[best_region] += total_rpm * CHECK_INTERVAL_MIN

    total_traffic = sum(traffic_counts.values()) or 1
    allocations = [TrafficAllocation(region_id=r["region_id"],
                   traffic_pct=round(traffic_counts[r["region_id"]] / total_traffic * 100, 1),
                   request_count_last_hour=traffic_counts[r["region_id"]] // SIM_HOURS)
                   for r in REGIONS]
    return timeline, failover_events, allocations


def _failover_reason(region_id: str, st: RegionStatus) -> str:
    if st.error_rate_pct >= 100:
        return f"{region_id} unreachable (health check timeout)"
    elif st.error_rate_pct >= 30:
        return f"{region_id} brownout (error_rate={st.error_rate_pct:.0f}%)"
    else:
        return f"{region_id} recovered — traffic shifted back"


def compute_sla_metrics(timeline: List[Dict], failover_events: List[FailoverEvent]) -> Dict:
    region_ids = list({r["region_id"] for r in timeline})
    metrics: Dict[str, Dict] = {}
    for rid in region_ids:
        entries = [e for e in timeline if e["region_id"] == rid]
        total = len(entries)
        if total == 0:
            continue
        healthy_count = sum(1 for e in entries if e["healthy"])
        metrics[rid] = {
            "uptime_pct": round(healthy_count / total * 100, 3),
            "downtime_min": (total - healthy_count) * CHECK_INTERVAL_MIN,
            "total_checks": total,
        }
    primary_metrics = metrics.get("us-ashburn-1", {})
    recovery_times = [e.recovery_time_s for e in failover_events if e.recovery_time_s > 0]
    mttr_s = np.mean(recovery_times) if recovery_times else 0.0
    all_times = sorted(set(e["time"] for e in timeline))
    healthy_windows = sum(1 for t in all_times if any(e["healthy"] for e in timeline if e["time"] == t))
    overall_uptime = healthy_windows / len(all_times) * 100 if all_times else 100.0
    return {
        "overall_uptime_pct": round(overall_uptime, 3),
        "primary_uptime_pct": primary_metrics.get("uptime_pct", 100.0),
        "downtime_min": primary_metrics.get("downtime_min", 0),
        "mttr_s": round(float(mttr_s), 1),
        "mttr_min": round(float(mttr_s) / 60, 1),
        "failover_count": len(failover_events),
        "zero_data_loss_events": 0,
        "rto_target_s": 30,
        "rto_achieved_avg_s": round(float(np.mean([e.recovery_time_s for e in failover_events])) if failover_events else 18.0, 1),
        "per_region": metrics,
    }


def _color_for_state(healthy: bool, degraded: bool) -> str:
    if degraded: return "#F59E0B"
    if healthy: return "#10B981"
    return "#EF4444"


def generate_health_heatmap_svg(timeline: List[Dict]) -> str:
    regions = ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "ap-tokyo-1"]
    region_labels = {"us-ashburn-1": "Ashburn (Primary)", "us-phoenix-1": "Phoenix (Secondary)",
                     "eu-frankfurt-1": "Frankfurt (DR)", "ap-tokyo-1": "Tokyo (Future)"}
    lookup: Dict = {}
    for e in timeline:
        lookup[(e["region_id"], e["time"])] = (e["healthy"], e.get("degraded", False))
    times = sorted(set(e["time"] for e in timeline))
    n_times = len(times)
    cell_w = max(1, int(900 / n_times))
    cell_h = 30
    label_w = 180
    header_h = 40
    padding = 20
    svg_w = label_w + n_times * cell_w + padding * 2
    svg_h = header_h + len(regions) * (cell_h + 4) + padding * 2 + 30
    cells = []
    for row_i, rid in enumerate(regions):
        y = header_h + padding + row_i * (cell_h + 4)
        cells.append(f'<text x="{label_w - 8}" y="{y + cell_h // 2 + 5}" font-size="11" text-anchor="end" fill="#374151">{region_labels[rid]}</text>')
        for col_i, t in enumerate(times):
            healthy, degraded = lookup.get((rid, t), (True, False))
            color = _color_for_state(healthy, degraded)
            x = label_w + padding + col_i * cell_w
            cells.append(f'<rect x="{x}" y="{y}" width="{max(cell_w - 1, 1)}" height="{cell_h}" fill="{color}" opacity="0.85"/>')
    x_labels = []
    for col_i, t in enumerate(times):
        if t.hour % 12 == 0 and t.minute == 0:
            x = label_w + padding + col_i * cell_w
            x_labels.append(f'<text x="{x}" y="{svg_h - 8}" font-size="9" text-anchor="middle" fill="#6B7280">{t.strftime("%m/%d %H:%M")}</text>')
    legend_items = [("#10B981", "Healthy"), ("#F59E0B", "Degraded"), ("#EF4444", "Down")]
    legend_svg = []
    lx = label_w + padding
    ly = padding + 8
    for color, label in legend_items:
        legend_svg.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{color}"/><text x="{lx + 18}" y="{ly + 11}" font-size="11" fill="#374151">{label}</text>')
        lx += 90
    title = f'<text x="{svg_w // 2}" y="22" font-size="14" font-weight="bold" text-anchor="middle" fill="#111827">72-Hour Region Health Heatmap</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" style="background:#F9FAFB;border-radius:8px;">' + title + "".join(legend_svg) + "".join(cells) + "".join(x_labels) + "</svg>"


def generate_traffic_pie_svg(allocations: List[TrafficAllocation]) -> str:
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#9CA3AF"]
    labels = {"us-ashburn-1": "Ashburn", "us-phoenix-1": "Phoenix", "eu-frankfurt-1": "Frankfurt", "ap-tokyo-1": "Tokyo"}
    cx, cy, r = 200, 160, 120
    svg_w, svg_h = 480, 340
    slices = []
    start_angle = -math.pi / 2
    for i, alloc in enumerate(allocations):
        pct = alloc.traffic_pct / 100.0
        if pct <= 0: continue
        end_angle = start_angle + 2 * math.pi * pct
        x1 = cx + r * math.cos(start_angle)
        y1 = cy + r * math.sin(start_angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy + r * math.sin(end_angle)
        large_arc = 1 if pct > 0.5 else 0
        path = f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z"
        slices.append(f'<path d="{path}" fill="{colors[i % len(colors)]}" stroke="white" stroke-width="2"/>')
        mid_angle = (start_angle + end_angle) / 2
        lx = cx + (r * 0.65) * math.cos(mid_angle)
        ly = cy + (r * 0.65) * math.sin(mid_angle)
        if pct > 0.05:
            slices.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" text-anchor="middle" fill="white" font-weight="bold">{alloc.traffic_pct:.1f}%</text>')
        start_angle = end_angle
    legend = []
    lx0 = 350
    for i, alloc in enumerate(allocations):
        if alloc.traffic_pct <= 0: continue
        ly = 80 + i * 24
        legend.append(f'<rect x="{lx0}" y="{ly}" width="14" height="14" fill="{colors[i % len(colors)]}"/><text x="{lx0 + 20}" y="{ly + 11}" font-size="11" fill="#374151">{labels.get(alloc.region_id, alloc.region_id)} ({alloc.traffic_pct:.1f}%)</text>')
    title = f'<text x="{svg_w // 2}" y="28" font-size="14" font-weight="bold" text-anchor="middle" fill="#111827">Traffic Distribution by Region</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" style="background:#F9FAFB;border-radius:8px;">' + title + "".join(slices) + "".join(legend) + "</svg>"


def generate_html_report(timeline, failover_events, allocations, metrics, output_path):
    heatmap_svg = generate_health_heatmap_svg(timeline)
    pie_svg = generate_traffic_pie_svg(allocations)
    event_rows = "".join(f'<tr><td>{ev.timestamp.strftime("%Y-%m-%d %H:%M")}</td><td>{ev.from_region}</td><td>{ev.to_region}</td><td>{ev.reason}</td><td>{ev.requests_migrated}</td><td>{ev.recovery_time_s:.1f}s</td></tr>' for ev in failover_events)
    region_rows = "".join(f'<tr><td><strong>{rdef["display_name"]}</strong><br/><small>{rdef["region_id"]}</small></td><td>{rdef["gpu_type"]}</td><td>{rdef["base_latency_ms"]}ms</td><td>{rdef["capacity_pct"]}%</td><td>{metrics["per_region"].get(rdef["region_id"], {}).get("uptime_pct", 100):.3f}%</td><td>{metrics["per_region"].get(rdef["region_id"], {}).get("downtime_min", 0)} min</td></tr>' for rdef in REGIONS)
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/><title>OCI Multi-Region Failover Report</title>
<style>body{{font-family:sans-serif;background:#F3F4F6;padding:32px;color:#111827}}.card{{background:white;border-radius:12px;padding:24px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}}.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}}.kpi{{background:white;border-radius:10px;padding:20px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08);border-top:4px solid #3B82F6}}.kpi-value{{font-size:32px;font-weight:700;color:#1F2937;margin-bottom:4px}}.kpi-label{{font-size:12px;color:#6B7280;text-transform:uppercase}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{background:#F9FAFB;padding:10px 14px;text-align:left;font-weight:600;border-bottom:2px solid #E5E7EB}}td{{padding:10px 14px;border-bottom:1px solid #F3F4F6}}</style></head><body>
<h1>OCI Multi-Region Failover Report</h1>
<div class="kpi-grid">
<div class="kpi"><div class="kpi-value">{metrics['overall_uptime_pct']:.2f}%</div><div class="kpi-label">Overall Uptime</div></div>
<div class="kpi"><div class="kpi-value">{metrics['mttr_min']:.1f} min</div><div class="kpi-label">Avg MTTR</div></div>
<div class="kpi"><div class="kpi-value">{metrics['rto_achieved_avg_s']:.1f}s</div><div class="kpi-label">Avg RTO</div></div>
<div class="kpi"><div class="kpi-value">{metrics['failover_count']}</div><div class="kpi-label">Failover Events</div></div>
<div class="kpi"><div class="kpi-value">{metrics['zero_data_loss_events']}</div><div class="kpi-label">Data Loss Events</div></div>
<div class="kpi"><div class="kpi-value">{metrics['downtime_min']} min</div><div class="kpi-label">Primary Downtime</div></div>
</div>
<div class="card">{heatmap_svg}</div>
<div class="card">{pie_svg}</div>
<div class="card"><h2>Region Status</h2><table><thead><tr><th>Region</th><th>GPU</th><th>Latency</th><th>Capacity</th><th>Uptime</th><th>Downtime</th></tr></thead><tbody>{region_rows}</tbody></table></div>
<div class="card"><h2>Failover Events</h2><table><thead><tr><th>Time</th><th>From</th><th>To</th><th>Reason</th><th>Requests</th><th>Recovery</th></tr></thead><tbody>{event_rows}</tbody></table></div>
<footer style="color:#9CA3AF;font-size:12px;text-align:center;margin-top:32px">OCI Robot Cloud Multi-Region Failover | Ashburn primary + Phoenix + Frankfurt DR | RTO target 30s</footer>
</body></html>"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)


def main() -> None:
    print("=" * 60)
    print("OCI Multi-Region Failover Simulation")
    print("=" * 60)
    print(f"Simulation period : {SIM_START} → {SIM_START + timedelta(hours=SIM_HOURS)}")
    print(f"Health check interval : every {CHECK_INTERVAL_MIN} minutes")
    print(f"Total checks per region : {(SIM_HOURS * 60) // CHECK_INTERVAL_MIN}")
    print()
    print("Running simulation...")
    timeline, failover_events, allocations = simulate()
    print(f"  Timeline entries generated : {len(timeline)}")
    print(f"  Failover events detected   : {len(failover_events)}")
    metrics = compute_sla_metrics(timeline, failover_events)
    print()
    print("-" * 60)
    print("SLA METRICS SUMMARY")
    print("-" * 60)
    print(f"  Overall uptime         : {metrics['overall_uptime_pct']:.3f}%")
    print(f"  Primary (Ashburn) uptime: {metrics['primary_uptime_pct']:.3f}%")
    print(f"  Total downtime (primary): {metrics['downtime_min']} minutes")
    print(f"  MTTR                   : {metrics['mttr_min']:.1f} minutes ({metrics['mttr_s']:.0f}s)")
    print(f"  RTO target             : {metrics['rto_target_s']}s")
    print(f"  RTO achieved (avg)     : {metrics['rto_achieved_avg_s']:.1f}s")
    print(f"  Data loss events       : {metrics['zero_data_loss_events']}")
    print(f"  Failover events        : {metrics['failover_count']}")
    print()
    print("-" * 60)
    print("FAILOVER EVENT LOG")
    print("-" * 60)
    if failover_events:
        for ev in failover_events:
            print(f"  [{ev.timestamp.strftime('%Y-%m-%d %H:%M')}]  {ev.from_region} → {ev.to_region}  |  {ev.requests_migrated} reqs migrated  |  Recovery: {ev.recovery_time_s:.1f}s")
            print(f"    Reason: {ev.reason}")
    else:
        print("  No failover events.")
    print()
    print("-" * 60)
    print("TRAFFIC ALLOCATION")
    print("-" * 60)
    for alloc in allocations:
        bar = "#" * int(alloc.traffic_pct / 2)
        print(f"  {alloc.region_id:<20} {alloc.traffic_pct:5.1f}%  {bar}")
    output_path = "/tmp/multi_region_failover_report.html"
    generate_html_report(timeline, failover_events, allocations, metrics, output_path)
    print(f"HTML report saved to: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
