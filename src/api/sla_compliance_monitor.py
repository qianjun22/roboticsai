#!/usr/bin/env python3
"""
SLA Compliance Monitor — Port 8068
Monitors OCI Robot Cloud SLA compliance per partner.
Tracks uptime, latency, training job completion SLAs, and generates compliance reports.
Usage: python sla_compliance_monitor.py [--mock] [--port 8068] [--output /tmp/sla_compliance_monitor.html]
"""
import argparse
import http.server
import json
import math
import random
import socketserver
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sys
import os

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SLAContract:
    partner: str
    tier: str                     # pilot / growth / enterprise
    uptime_sla_pct: float         # 99.0 / 99.5 / 99.9
    latency_sla_ms: int           # 500  / 300  / 200
    training_sla_hr: int          # 48   / 24   / 12
    support_response_hr: int      # 72   / 24   / 4

@dataclass
class SLAEvent:
    event_id: str
    partner: str
    event_type: str               # outage / latency_breach / training_delay / support_ticket
    started_at: datetime
    resolved_at: datetime
    duration_min: float
    severity: str                 # P1 / P2 / P3
    breach: bool                  # violated SLA?

# ---------------------------------------------------------------------------
# Tier defaults
# ---------------------------------------------------------------------------

TIER_DEFAULTS = {
    "pilot":      dict(uptime_sla_pct=99.0, latency_sla_ms=500, training_sla_hr=48, support_response_hr=72),
    "growth":     dict(uptime_sla_pct=99.5, latency_sla_ms=300, training_sla_hr=24, support_response_hr=24),
    "enterprise": dict(uptime_sla_pct=99.9, latency_sla_ms=200, training_sla_hr=12, support_response_hr=4),
}

CREDIT_TABLE = {"P1": 500, "P2": 200, "P3": 0}

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def generate_sla_data(seed: int = 42):
    rng = random.Random(seed)
    base_time = datetime.now() - timedelta(days=30)

    partners_config = [
        ("AcmeCorp",       "enterprise"),
        ("RoboStartup",    "pilot"),
        ("ManufactureCo",  "growth"),
        ("LogisticsPlus",  "enterprise"),
    ]

    contracts: List[SLAContract] = []
    for name, tier in partners_config:
        d = TIER_DEFAULTS[tier]
        contracts.append(SLAContract(partner=name, tier=tier, **d))

    events: List[SLAEvent] = []
    eid = 0

    for contract in contracts:
        # Outages: 2-4 per month
        outage_count = rng.randint(2, 4)
        for _ in range(outage_count):
            eid += 1
            offset_min = rng.uniform(0, 30 * 24 * 60)
            duration = rng.uniform(2, 15)
            started = base_time + timedelta(minutes=offset_min)
            resolved = started + timedelta(minutes=duration)
            # Breach if contribution to downtime pushes uptime below SLA
            breach = duration > 5 or contract.tier in ("enterprise", "growth")
            severity = "P1" if duration > 10 else "P2"
            events.append(SLAEvent(
                event_id=f"EVT-{eid:04d}", partner=contract.partner,
                event_type="outage", started_at=started, resolved_at=resolved,
                duration_min=round(duration, 2), severity=severity, breach=breach,
            ))

        # Latency breaches: 4-8 per month
        latency_count = rng.randint(4, 8)
        for _ in range(latency_count):
            eid += 1
            offset_min = rng.uniform(0, 30 * 24 * 60)
            duration = rng.uniform(0.5, 5)
            started = base_time + timedelta(minutes=offset_min)
            resolved = started + timedelta(minutes=duration)
            actual_ms = rng.randint(contract.latency_sla_ms + 10,
                                    contract.latency_sla_ms + 300)
            breach = actual_ms > contract.latency_sla_ms
            severity = "P2" if actual_ms > contract.latency_sla_ms * 1.5 else "P3"
            events.append(SLAEvent(
                event_id=f"EVT-{eid:04d}", partner=contract.partner,
                event_type="latency_breach", started_at=started, resolved_at=resolved,
                duration_min=round(duration, 2), severity=severity, breach=breach,
            ))

        # Training delays: 1-2 per month
        train_count = rng.randint(1, 2)
        for _ in range(train_count):
            eid += 1
            offset_min = rng.uniform(0, 30 * 24 * 60)
            delay_hr = rng.uniform(1, contract.training_sla_hr * 1.5)
            started = base_time + timedelta(minutes=offset_min)
            resolved = started + timedelta(hours=delay_hr)
            breach = delay_hr > contract.training_sla_hr
            severity = "P1" if breach and delay_hr > contract.training_sla_hr * 1.2 else "P2"
            events.append(SLAEvent(
                event_id=f"EVT-{eid:04d}", partner=contract.partner,
                event_type="training_delay", started_at=started, resolved_at=resolved,
                duration_min=round(delay_hr * 60, 1), severity=severity, breach=breach,
            ))

        # Support tickets: 3-6 per month
        ticket_count = rng.randint(3, 6)
        for _ in range(ticket_count):
            eid += 1
            offset_min = rng.uniform(0, 30 * 24 * 60)
            sev = rng.choice(["P1", "P2", "P3"])
            sla_hr = contract.support_response_hr
            response_hr = rng.uniform(sla_hr * 0.5, sla_hr * 2.0)
            started = base_time + timedelta(minutes=offset_min)
            resolved = started + timedelta(hours=response_hr)
            breach = response_hr > sla_hr
            events.append(SLAEvent(
                event_id=f"EVT-{eid:04d}", partner=contract.partner,
                event_type="support_ticket", started_at=started, resolved_at=resolved,
                duration_min=round(response_hr * 60, 1), severity=sev, breach=breach,
            ))

    events.sort(key=lambda e: e.started_at)
    return contracts, events

# ---------------------------------------------------------------------------
# Compliance computation
# ---------------------------------------------------------------------------

def compute_compliance(contracts: List[SLAContract], events: List[SLAEvent]) -> Dict:
    window_min = 30 * 24 * 60  # 30 days in minutes
    results = {}

    for contract in contracts:
        p_events = [e for e in events if e.partner == contract.partner]

        # Uptime
        outage_min = sum(e.duration_min for e in p_events if e.event_type == "outage")
        actual_uptime = round(100.0 * (1 - outage_min / window_min), 4)
        uptime_breach = actual_uptime < contract.uptime_sla_pct

        # p95 latency (simulate from latency breach events)
        lat_events = [e for e in p_events if e.event_type == "latency_breach"]
        if lat_events:
            samples = sorted([contract.latency_sla_ms + int(e.duration_min * 30) for e in lat_events])
            p95_idx = max(0, int(math.ceil(len(samples) * 0.95)) - 1)
            p95_latency = samples[p95_idx]
        else:
            p95_latency = int(contract.latency_sla_ms * 0.85)
        latency_breach = p95_latency > contract.latency_sla_ms

        # Training on-time %
        train_events = [e for e in p_events if e.event_type == "training_delay"]
        on_time = sum(1 for e in train_events if not e.breach)
        train_pct = round(100.0 * on_time / len(train_events), 1) if train_events else 100.0

        # Credits
        credits = sum(
            CREDIT_TABLE.get(e.severity, 0)
            for e in p_events
            if e.breach and e.event_type != "support_ticket"
        )

        # Grade
        score = 100
        if uptime_breach:
            score -= 30
        if latency_breach:
            score -= 20
        if train_pct < 90:
            score -= 15
        if credits > 1000:
            score -= 20
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"

        results[contract.partner] = {
            "contract": contract,
            "actual_uptime": actual_uptime,
            "uptime_breach": uptime_breach,
            "p95_latency": p95_latency,
            "latency_breach": latency_breach,
            "train_pct": train_pct,
            "credits": credits,
            "grade": grade,
            "breach_events": [e for e in p_events if e.breach],
        }

    return results

# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _grade_color(grade: str) -> str:
    return {"A": "#22c55e", "B": "#84cc16", "C": "#f59e0b", "D": "#ef4444"}.get(grade, "#94a3b8")

def build_uptime_svg(compliance: Dict) -> str:
    partners = list(compliance.keys())
    bar_h = 36
    gap = 12
    margin_left = 110
    margin_top = 20
    w = 540
    h = margin_top + len(partners) * (bar_h + gap) + 30
    max_val = 100.0
    min_val = 98.5

    lines = [f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">']
    bar_w = w - margin_left - 20

    for i, partner in enumerate(partners):
        d = compliance[partner]
        contract: SLAContract = d["contract"]
        y = margin_top + i * (bar_h + gap)
        uptime = d["actual_uptime"]
        sla = contract.uptime_sla_pct
        fill = "#22c55e" if uptime >= sla else "#ef4444"
        pct = max(0, (uptime - min_val) / (max_val - min_val))
        pct_sla = max(0, (sla - min_val) / (max_val - min_val))
        bw = int(pct * bar_w)
        sla_x = margin_left + int(pct_sla * bar_w)

        lines.append(f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_h}" fill="#334155" rx="4"/>')
        lines.append(f'<rect x="{margin_left}" y="{y}" width="{bw}" height="{bar_h}" fill="{fill}" rx="4"/>')
        lines.append(f'<line x1="{sla_x}" y1="{y-4}" x2="{sla_x}" y2="{y+bar_h+4}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{margin_left - 6}" y="{y + bar_h//2 + 5}" text-anchor="end" fill="#cbd5e1" font-size="12" font-family="monospace">{partner}</text>')
        lines.append(f'<text x="{margin_left + bw + 6}" y="{y + bar_h//2 + 5}" fill="{fill}" font-size="11" font-family="monospace">{uptime:.3f}%</text>')

    # Axis label
    lines.append(f'<text x="{margin_left + bar_w//2}" y="{h - 5}" text-anchor="middle" fill="#64748b" font-size="10" font-family="sans-serif">Uptime % (dashed = SLA threshold)</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def build_heatmap_svg(compliance: Dict, events: List[SLAEvent]) -> str:
    partners = list(compliance.keys())
    days = 30
    cell_w, cell_h = 16, 28
    margin_left = 110
    margin_top = 24
    w = margin_left + days * cell_w + 20
    h = margin_top + len(partners) * (cell_h + 4) + 30

    base_date = (datetime.now() - timedelta(days=30)).date()

    # Build lookup: (partner, day_offset) -> worst severity
    severity_rank = {"P1": 3, "P2": 2, "P3": 1}
    cell_data: Dict = {}
    for e in events:
        if not e.breach:
            continue
        day_idx = (e.started_at.date() - base_date).days
        if 0 <= day_idx < days:
            key = (e.partner, day_idx)
            existing = cell_data.get(key, 0)
            cell_data[key] = max(existing, severity_rank.get(e.severity, 0))

    sev_color = {3: "#ef4444", 2: "#f59e0b", 1: "#84cc16", 0: "#1e3a5f"}

    lines = [f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">']

    for i, partner in enumerate(partners):
        y = margin_top + i * (cell_h + 4)
        lines.append(f'<text x="{margin_left - 6}" y="{y + cell_h//2 + 5}" text-anchor="end" fill="#cbd5e1" font-size="12" font-family="monospace">{partner}</text>')
        for d in range(days):
            x = margin_left + d * cell_w
            rank = cell_data.get((partner, d), 0)
            color = sev_color[rank]
            lines.append(f'<rect x="{x+1}" y="{y}" width="{cell_w-2}" height="{cell_h}" fill="{color}" rx="2"/>')

    # Day labels every 5
    for d in range(0, days, 5):
        x = margin_left + d * cell_w + cell_w // 2
        lines.append(f'<text x="{x}" y="{h - 6}" text-anchor="middle" fill="#64748b" font-size="9" font-family="sans-serif">D{d+1}</text>')

    # Legend
    lx = margin_left
    ly = h - 18
    for label, color in [("P1 breach", "#ef4444"), ("P2 breach", "#f59e0b"), ("P3 breach", "#84cc16"), ("clean", "#1e3a5f")]:
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+15}" y="{ly+10}" fill="#94a3b8" font-size="9" font-family="sans-serif">{label}</text>')
        lx += 80

    lines.append('</svg>')
    return "\n".join(lines)


def build_html(contracts: List[SLAContract], events: List[SLAEvent]) -> str:
    compliance = compute_compliance(contracts, events)

    total_partners = len(compliance)
    all_green = sum(1 for d in compliance.values() if d["grade"] == "A")
    total_credits = sum(d["credits"] for d in compliance.values())
    worst = max(compliance.items(), key=lambda x: x[1]["credits"])[0]
    best_uptime = max(compliance.items(), key=lambda x: x[1]["actual_uptime"])[0]

    uptime_svg = build_uptime_svg(compliance)
    heatmap_svg = build_heatmap_svg(compliance, events)

    # Compliance table rows
    table_rows = ""
    for partner, d in compliance.items():
        c: SLAContract = d["contract"]
        uptime_color = "#22c55e" if not d["uptime_breach"] else "#ef4444"
        lat_color = "#22c55e" if not d["latency_breach"] else "#ef4444"
        grade_c = _grade_color(d["grade"])
        table_rows += f"""
        <tr>
          <td>{partner}</td>
          <td><span class="badge badge-{c.tier}">{c.tier}</span></td>
          <td>{c.uptime_sla_pct}% / <span style="color:{uptime_color}">{d['actual_uptime']:.3f}%</span></td>
          <td>{c.latency_sla_ms}ms / <span style="color:{lat_color}">{d['p95_latency']}ms</span></td>
          <td>{d['train_pct']:.0f}%</td>
          <td style="color:#f59e0b">${d['credits']:,}</td>
          <td style="color:{grade_c};font-weight:700">{d["grade"]}</td>
        </tr>"""

    # Breach events table (latest 15)
    breach_events = sorted([e for e in events if e.breach], key=lambda e: e.started_at, reverse=True)[:15]
    event_rows = ""
    sev_cls = {"P1": "color:#ef4444;font-weight:700", "P2": "color:#f59e0b;font-weight:700", "P3": "color:#84cc16"}
    for e in breach_events:
        event_rows += f"""
        <tr>
          <td>{e.event_id}</td>
          <td>{e.partner}</td>
          <td>{e.event_type.replace('_', ' ').title()}</td>
          <td>{e.started_at.strftime('%m-%d %H:%M')}</td>
          <td>{e.duration_min:.1f}</td>
          <td style="{sev_cls.get(e.severity, '')}">{e.severity}</td>
          <td style="color:#ef4444">YES</td>
        </tr>"""

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — SLA Compliance Monitor</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }}
  .topbar {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 14px 28px; display: flex; align-items: center; gap: 16px; }}
  .topbar h1 {{ font-size: 1.25rem; color: #C74634; font-weight: 700; letter-spacing: 0.03em; }}
  .topbar .sub {{ color: #94a3b8; font-size: 0.8rem; margin-left: auto; }}
  .container {{ max-width: 1120px; margin: 0 auto; padding: 24px 20px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
  .kpi .label {{ font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }}
  .kpi .value {{ font-size: 1.8rem; font-weight: 700; color: #f1f5f9; line-height: 1; }}
  .kpi .value.red {{ color: #C74634; }}
  .kpi .value.green {{ color: #22c55e; }}
  .kpi .value.amber {{ color: #f59e0b; }}
  section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  section h2 {{ font-size: 0.95rem; color: #C74634; font-weight: 600; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.05em; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  .charts section {{ margin-bottom: 0; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; padding: 8px 12px; border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; font-size: 0.85rem; }}
  tr:hover td {{ background: #0f172a; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; }}
  .badge-pilot {{ background: #1e3a5f; color: #93c5fd; }}
  .badge-growth {{ background: #1c3a2a; color: #86efac; }}
  .badge-enterprise {{ background: #3a1a1a; color: #fca5a5; }}
  .footer {{ text-align: center; color: #334155; font-size: 0.75rem; padding: 20px 0 8px; }}
</style>
</head>
<body>
<div class="topbar">
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="28" height="28" rx="6" fill="#C74634"/>
    <path d="M8 14 L14 8 L20 14 L14 20 Z" fill="white"/>
  </svg>
  <h1>OCI Robot Cloud — SLA Compliance Monitor</h1>
  <span class="sub">30-day window &nbsp;|&nbsp; Generated: {generated_at}</span>
</div>

<div class="container">

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">Partners Monitored</div>
      <div class="value">{total_partners}</div>
    </div>
    <div class="kpi">
      <div class="label">All-Green (Grade A)</div>
      <div class="value {'green' if all_green == total_partners else 'amber'}">{all_green}</div>
    </div>
    <div class="kpi">
      <div class="label">Total SLA Credits Owed</div>
      <div class="value {'red' if total_credits > 1000 else 'amber'}">${total_credits:,}</div>
    </div>
    <div class="kpi">
      <div class="label">Worst Partner</div>
      <div class="value red" style="font-size:1.1rem;padding-top:6px">{worst}</div>
    </div>
    <div class="kpi">
      <div class="label">Best Uptime</div>
      <div class="value green" style="font-size:1.1rem;padding-top:6px">{best_uptime}</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts">
    <section>
      <h2>Uptime % by Partner (vs SLA threshold)</h2>
      {uptime_svg}
    </section>
    <section>
      <h2>Event Severity Heatmap (30 days)</h2>
      {heatmap_svg}
    </section>
  </div>

  <!-- Compliance Table -->
  <section>
    <h2>Compliance Summary</h2>
    <table>
      <thead>
        <tr>
          <th>Partner</th><th>Tier</th><th>Uptime SLA / Actual</th>
          <th>Latency SLA / p95</th><th>Training On-Time</th>
          <th>Credits Owed</th><th>Grade</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>

  <!-- Recent Breach Events -->
  <section>
    <h2>Recent Breach Events (latest 15)</h2>
    <table>
      <thead>
        <tr>
          <th>Event ID</th><th>Partner</th><th>Type</th>
          <th>Started</th><th>Duration (min)</th><th>Severity</th><th>Breach</th>
        </tr>
      </thead>
      <tbody>{event_rows}</tbody>
    </table>
  </section>

</div>
<div class="footer">OCI Robot Cloud &copy; Oracle Corporation &nbsp;|&nbsp; Confidential</div>
</body>
</html>"""
    return html

# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

_html_cache: str = ""

class SLAHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = _html_cache.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, fmt, *args):  # suppress default logging
        pass

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SLA Compliance Monitor")
    parser.add_argument("--mock", action="store_true", default=True, help="Use generated mock data (default)")
    parser.add_argument("--port", type=int, default=8068)
    parser.add_argument("--output", type=str, default="", help="Write HTML to file and exit")
    args = parser.parse_args()

    print("[SLA Compliance Monitor] Generating mock data...", flush=True)
    contracts, events = generate_sla_data(seed=42)

    print(f"[SLA Compliance Monitor] Generated {len(contracts)} contracts, {len(events)} events", flush=True)
    html = build_html(contracts, events)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[SLA Compliance Monitor] Report written to {args.output}", flush=True)
        return

    global _html_cache
    _html_cache = html

    print(f"[SLA Compliance Monitor] Listening on http://0.0.0.0:{args.port}/", flush=True)
    with socketserver.TCPServer(("", args.port), SLAHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[SLA Compliance Monitor] Shutting down.", flush=True)

if __name__ == "__main__":
    main()
