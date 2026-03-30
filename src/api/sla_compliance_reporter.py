#!/usr/bin/env python3
"""
sla_compliance_reporter.py — SLA compliance tracking for OCI Robot Cloud API services.

Measures uptime, latency p99, error rates, and throughput against committed SLA tiers
(Pilot: 99.0%, Growth: 99.5%, Enterprise: 99.9%). Generates compliance scorecards.

Usage:
    python src/api/sla_compliance_reporter.py --mock --output /tmp/sla_compliance_reporter.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Config ──────────────────────────────────────────────────────────────────

SLA_TIERS = {
    "pilot":      {"uptime_pct": 99.0,  "latency_p99_ms": 500, "error_rate_pct": 2.0},
    "growth":     {"uptime_pct": 99.5,  "latency_p99_ms": 350, "error_rate_pct": 1.0},
    "enterprise": {"uptime_pct": 99.9,  "latency_p99_ms": 250, "error_rate_pct": 0.5},
}

SERVICES = [
    # (name, port, tier, base_uptime, base_latency_p99, base_error_rate)
    ("inference",          8001, "enterprise", 99.94, 226,  0.3),
    ("fine_tune",          8010, "enterprise", 99.87, 180,  0.6),
    ("data_collection",    8003, "growth",     99.61, 290,  0.8),
    ("eval_harness",       8020, "growth",     99.72, 310,  0.7),
    ("dagger_controller",  8050, "pilot",      99.15, 420,  1.4),
    ("checkpoint_mgr",     8060, "pilot",      99.42, 380,  1.1),
    ("telemetry_stream",   8070, "growth",     99.55, 260,  0.9),
    ("online_learning",    8072, "enterprise", 99.91, 240,  0.4),
]

N_DAYS = 30  # reporting window


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class DailyMetric:
    day: int
    uptime_pct: float
    latency_p99_ms: float
    error_rate_pct: float
    incidents: int


@dataclass
class ServiceSLA:
    service_name: str
    port: int
    tier: str
    # SLA targets
    uptime_target: float
    latency_target_ms: float
    error_target_pct: float
    # Actuals
    uptime_actual: float
    latency_p99_actual: float
    error_rate_actual: float
    # Compliance
    uptime_compliant: bool
    latency_compliant: bool
    error_compliant: bool
    overall_compliant: bool
    sla_score: float          # 0–100
    incidents_30d: int
    downtime_minutes: float
    daily: list[DailyMetric] = field(default_factory=list)


@dataclass
class SLAReport:
    window_days: int
    fully_compliant: int
    partial_compliant: int
    non_compliant: int
    overall_compliance_pct: float
    best_service: str
    worst_service: str
    total_incidents: int
    services: list[ServiceSLA] = field(default_factory=list)


# ── Simulation ───────────────────────────────────────────────────────────────

def simulate_sla(seed: int = 42) -> SLAReport:
    rng = random.Random(seed)
    results: list[ServiceSLA] = []

    for svc, port, tier, base_up, base_lat, base_err in SERVICES:
        target = SLA_TIERS[tier]
        daily: list[DailyMetric] = []

        for d in range(N_DAYS):
            # Inject occasional incidents
            incident = rng.random() < 0.08
            uptime = base_up - (rng.uniform(0.3, 1.5) if incident else rng.gauss(0, 0.05))
            uptime = max(95.0, min(100.0, uptime))
            lat = base_lat + rng.gauss(0, 15) + (rng.uniform(50, 120) if incident else 0)
            lat = max(100.0, lat)
            err = base_err + rng.gauss(0, 0.1) + (rng.uniform(0.5, 2.0) if incident else 0)
            err = max(0.0, min(5.0, err))
            daily.append(DailyMetric(
                day=d + 1,
                uptime_pct=round(uptime, 3),
                latency_p99_ms=round(lat, 1),
                error_rate_pct=round(err, 3),
                incidents=1 if incident else 0,
            ))

        # Aggregate
        avg_up  = sum(d.uptime_pct for d in daily) / N_DAYS
        avg_lat = sum(d.latency_p99_ms for d in daily) / N_DAYS
        avg_err = sum(d.error_rate_pct for d in daily) / N_DAYS
        incidents = sum(d.incidents for d in daily)
        downtime = (100 - avg_up) / 100 * N_DAYS * 24 * 60  # minutes

        up_ok  = avg_up  >= target["uptime_pct"]
        lat_ok = avg_lat <= target["latency_p99_ms"]
        err_ok = avg_err <= target["error_rate_pct"]
        overall = up_ok and lat_ok and err_ok

        # SLA score: weighted average of compliance margins
        up_score  = min(100, (avg_up / target["uptime_pct"]) * 100)
        lat_score = min(100, (target["latency_p99_ms"] / avg_lat) * 100)
        err_score = min(100, (target["error_rate_pct"] / max(avg_err, 0.01)) * 100)
        score = round((up_score * 0.5 + lat_score * 0.3 + err_score * 0.2), 1)

        results.append(ServiceSLA(
            service_name=svc, port=port, tier=tier,
            uptime_target=target["uptime_pct"],
            latency_target_ms=target["latency_p99_ms"],
            error_target_pct=target["error_rate_pct"],
            uptime_actual=round(avg_up, 3),
            latency_p99_actual=round(avg_lat, 1),
            error_rate_actual=round(avg_err, 3),
            uptime_compliant=up_ok,
            latency_compliant=lat_ok,
            error_compliant=err_ok,
            overall_compliant=overall,
            sla_score=score,
            incidents_30d=incidents,
            downtime_minutes=round(downtime, 1),
            daily=daily,
        ))

    fully   = sum(1 for r in results if r.overall_compliant)
    partial = sum(1 for r in results if not r.overall_compliant and
                  (r.uptime_compliant or r.latency_compliant or r.error_compliant))
    non     = len(results) - fully - partial
    best  = max(results, key=lambda r: r.sla_score).service_name
    worst = min(results, key=lambda r: r.sla_score).service_name
    total_incidents = sum(r.incidents_30d for r in results)

    return SLAReport(
        window_days=N_DAYS,
        fully_compliant=fully,
        partial_compliant=partial,
        non_compliant=non,
        overall_compliance_pct=round(fully / len(results) * 100, 1),
        best_service=best,
        worst_service=worst,
        total_incidents=total_incidents,
        services=results,
    )


# ── HTML ─────────────────────────────────────────────────────────────────────

def render_html(report: SLAReport) -> str:
    TIER_COLORS = {"pilot": "#f59e0b", "growth": "#3b82f6", "enterprise": "#22c55e"}

    # SVG: uptime compliance bar chart
    w, h, margin = 580, 220, 50
    inner_w = w - 2 * margin
    bar_h = 18
    gap = 8

    svg_uptime = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    # Axis
    svg_uptime += f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{h-margin}" stroke="#475569"/>'
    svg_uptime += f'<line x1="{margin}" y1="{h-margin}" x2="{w-margin}" y2="{h-margin}" stroke="#475569"/>'

    for i, svc in enumerate(report.services):
        y = margin + i * (bar_h + gap)
        # target line (% → x)
        tgt_x = margin + (svc.uptime_target - 95) / 5 * inner_w
        act_x = margin + (svc.uptime_actual - 95) / 5 * inner_w
        act_x = max(margin + 2, min(w - margin, act_x))

        col = "#22c55e" if svc.uptime_compliant else "#ef4444"
        svg_uptime += (f'<rect x="{margin}" y="{y}" width="{act_x - margin:.1f}" '
                       f'height="{bar_h}" fill="{col}" opacity="0.7"/>')
        # target dashed line
        svg_uptime += (f'<line x1="{tgt_x:.1f}" y1="{y}" x2="{tgt_x:.1f}" '
                       f'y2="{y + bar_h}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3,2"/>')
        svg_uptime += (f'<text x="{margin - 4}" y="{y + bar_h - 4}" fill="#94a3b8" '
                       f'font-size="8.5" text-anchor="end">{svc.service_name[:14]}</text>')
        svg_uptime += (f'<text x="{act_x + 3:.1f}" y="{y + bar_h - 4}" fill="{col}" '
                       f'font-size="8">{svc.uptime_actual:.2f}%</text>')

    # X-axis labels (95–100%)
    for v in range(6):
        pct = 95 + v
        x = margin + v / 5 * inner_w
        svg_uptime += (f'<text x="{x:.1f}" y="{h - margin + 12}" fill="#64748b" '
                       f'font-size="8" text-anchor="middle">{pct}%</text>')

    svg_uptime += f'<text x="{w//2}" y="{margin-8}" fill="#94a3b8" font-size="9" text-anchor="middle">Uptime % (30-day avg) — dashed = SLA target</text>'
    svg_uptime += '</svg>'

    # SVG: SLA score radar-style spider (use horizontal bar sorted by score)
    sw, sh, sm = 380, 220, 45
    inner_sw = sw - 2 * sm
    sbar_h = 18
    sorted_svcs = sorted(report.services, key=lambda r: r.sla_score, reverse=True)

    svg_score = f'<svg width="{sw}" height="{sh}" style="background:#0f172a;border-radius:8px">'
    svg_score += f'<line x1="{sm}" y1="{sm}" x2="{sm}" y2="{sh-sm}" stroke="#475569"/>'
    svg_score += f'<line x1="{sm}" y1="{sh-sm}" x2="{sw-sm}" y2="{sh-sm}" stroke="#475569"/>'

    for i, svc in enumerate(sorted_svcs):
        y = sm + i * (sbar_h + gap)
        bar_w = (svc.sla_score / 100) * inner_sw
        col = TIER_COLORS.get(svc.tier, "#64748b")
        svg_score += (f'<rect x="{sm}" y="{y}" width="{bar_w:.1f}" '
                      f'height="{sbar_h}" fill="{col}" opacity="0.75" rx="2"/>')
        svg_score += (f'<text x="{sm - 4}" y="{y + sbar_h - 4}" fill="#94a3b8" '
                      f'font-size="8.5" text-anchor="end">{svc.service_name[:14]}</text>')
        svg_score += (f'<text x="{sm + bar_w + 3:.1f}" y="{y + sbar_h - 4}" fill="{col}" '
                      f'font-size="8.5">{svc.sla_score}</text>')

    # Scale marks 0/25/50/75/100
    for v in [0, 25, 50, 75, 100]:
        x = sm + v / 100 * inner_sw
        svg_score += (f'<line x1="{x:.1f}" y1="{sm}" x2="{x:.1f}" y2="{sh-sm}" '
                      f'stroke="#1e293b" stroke-width="1"/>')
        svg_score += (f'<text x="{x:.1f}" y="{sh-sm+12}" fill="#64748b" '
                      f'font-size="8" text-anchor="middle">{v}</text>')

    svg_score += f'<text x="{sw//2}" y="{sm-8}" fill="#94a3b8" font-size="9" text-anchor="middle">SLA Score (0–100) by tier color</text>'
    svg_score += '</svg>'

    # Table rows
    def status_badge(ok: bool) -> str:
        return ('<span style="color:#22c55e">✓</span>' if ok
                else '<span style="color:#ef4444">✗</span>')

    rows = ""
    for svc in report.services:
        tier_col = TIER_COLORS.get(svc.tier, "#64748b")
        overall_col = "#22c55e" if svc.overall_compliant else "#ef4444"
        rows += (f'<tr>'
                 f'<td style="color:#e2e8f0;font-weight:bold">{svc.service_name}</td>'
                 f'<td style="color:{tier_col}">{svc.tier}</td>'
                 f'<td>{svc.uptime_actual:.3f}% {status_badge(svc.uptime_compliant)}</td>'
                 f'<td>{svc.latency_p99_actual:.0f}ms {status_badge(svc.latency_compliant)}</td>'
                 f'<td>{svc.error_rate_actual:.3f}% {status_badge(svc.error_compliant)}</td>'
                 f'<td style="color:{overall_col};font-weight:bold">{svc.sla_score}</td>'
                 f'<td style="color:#64748b">{svc.incidents_30d}</td>'
                 f'<td style="color:#94a3b8">{svc.downtime_minutes:.1f}m</td>'
                 f'</tr>')

    best_svc  = next(s for s in report.services if s.service_name == report.best_service)
    worst_svc = next(s for s in report.services if s.service_name == report.worst_service)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SLA Compliance Report</title>
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
<h1>SLA Compliance Report</h1>
<div class="meta">
  {len(SERVICES)} services · {N_DAYS}-day window · 3 tiers (pilot / growth / enterprise)
</div>

<div class="grid">
  <div class="card"><h3>Fully Compliant</h3>
    <div class="big" style="color:#22c55e">{report.fully_compliant}/{len(SERVICES)}</div>
    <div style="color:#64748b;font-size:10px">{report.overall_compliance_pct}% services</div>
  </div>
  <div class="card"><h3>Best Service</h3>
    <div style="color:#22c55e;font-size:14px;font-weight:bold">{report.best_service}</div>
    <div class="big" style="color:#22c55e">{best_svc.sla_score}</div>
  </div>
  <div class="card"><h3>Most Incidents</h3>
    <div style="color:#ef4444;font-size:14px;font-weight:bold">{report.worst_service}</div>
    <div class="big" style="color:#ef4444">{worst_svc.incidents_30d}</div>
  </div>
  <div class="card"><h3>Total Incidents (30d)</h3>
    <div class="big" style="color:#f59e0b">{report.total_incidents}</div>
    <div style="color:#64748b;font-size:10px">across all services</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Uptime Compliance (30-day avg)</h3>
    {svg_uptime}
  </div>
  <div>
    <h3 class="sec">SLA Score by Service</h3>
    {svg_score}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      <span style="color:#22c55e">■</span> enterprise &nbsp;
      <span style="color:#3b82f6">■</span> growth &nbsp;
      <span style="color:#f59e0b">■</span> pilot
    </div>
  </div>
</div>

<h3 class="sec">Service SLA Detail</h3>
<table>
  <tr><th>Service</th><th>Tier</th><th>Uptime</th><th>Latency p99</th>
      <th>Error Rate</th><th>Score</th><th>Incidents</th><th>Downtime</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:6px">SLA TIER TARGETS</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
    <div><div style="color:#f59e0b;font-weight:bold">PILOT</div>
      <div style="color:#64748b">Uptime: 99.0% | Latency: ≤500ms | Errors: ≤2.0%</div></div>
    <div><div style="color:#3b82f6;font-weight:bold">GROWTH</div>
      <div style="color:#64748b">Uptime: 99.5% | Latency: ≤350ms | Errors: ≤1.0%</div></div>
    <div><div style="color:#22c55e;font-weight:bold">ENTERPRISE</div>
      <div style="color:#64748b">Uptime: 99.9% | Latency: ≤250ms | Errors: ≤0.5%</div></div>
  </div>
</div>

<div style="color:#64748b;font-size:11px;margin-top:10px">
  Inference (port 8001) and online_learning (8072) meet enterprise SLA targets.<br>
  dagger_controller and checkpoint_mgr on pilot tier — upgrade path: reduce incident rate via health monitor auto-restart.<br>
  Recommended: promote growth services to enterprise SLA for Series B customers.
</div>
</body></html>"""


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SLA compliance reporter for OCI Robot Cloud")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/sla_compliance_reporter.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[sla] {len(SERVICES)} services · {N_DAYS}-day window · 3 SLA tiers")
    t0 = time.time()

    report = simulate_sla(args.seed)

    print(f"\n  {'Service':<22} {'Tier':<12} {'Uptime':>8} {'Latency':>10} {'Errors':>8} {'Score':>7}  Status")
    print(f"  {'─'*22} {'─'*12} {'─'*8} {'─'*10} {'─'*8} {'─'*7}  {'─'*6}")
    for s in report.services:
        status = "OK" if s.overall_compliant else "BREACH"
        col = "✓" if s.overall_compliant else "✗"
        print(f"  {s.service_name:<22} {s.tier:<12} {s.uptime_actual:>7.3f}% "
              f"{s.latency_p99_actual:>8.0f}ms {s.error_rate_actual:>6.3f}%  "
              f"{s.sla_score:>6}  {col} {status}")

    print(f"\n  Compliant: {report.fully_compliant}/{len(SERVICES)} ({report.overall_compliance_pct}%)")
    print(f"  Best: {report.best_service}  |  Worst: {report.worst_service}")
    print(f"  Total incidents (30d): {report.total_incidents}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "window_days": report.window_days,
        "fully_compliant": report.fully_compliant,
        "overall_compliance_pct": report.overall_compliance_pct,
        "best_service": report.best_service,
        "worst_service": report.worst_service,
        "total_incidents": report.total_incidents,
        "services": [{
            "name": s.service_name, "tier": s.tier,
            "uptime_actual": s.uptime_actual, "sla_score": s.sla_score,
            "overall_compliant": s.overall_compliant,
        } for s in report.services],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
