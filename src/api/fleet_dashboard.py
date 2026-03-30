"""
Fleet Dashboard — OCI Robot Cloud
Real-time fleet monitoring for customers managing multiple deployed robots.
Port 8065. Dark theme, fully self-contained, no external dependencies.
"""

import argparse
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RobotUnit:
    unit_id: str
    name: str
    model: str          # franka / ur5e / xarm7 / kinova
    location: str
    customer: str
    status: str         # active / idle / error / charging
    battery_pct: int
    current_task: str
    tasks_today: int
    sr_today: float
    uptime_hr: float
    last_heartbeat: str


@dataclass
class FleetAlert:
    alert_id: str
    unit_id: str
    severity: str       # critical / warning / info
    message: str
    timestamp: str


# ---------------------------------------------------------------------------
# Mock data generators
# ---------------------------------------------------------------------------

CUSTOMERS = ["Agility Robotics", "Figure AI", "Boston Dynamics"]
LOCATIONS = ["San Jose DC-1", "Austin DC-2", "Seattle DC-3", "Chicago DC-4"]
MODELS = ["franka", "ur5e", "xarm7", "kinova"]
TASKS = [
    "Pick-and-place bin A→B", "Assembly line QA", "Pallet stacking",
    "Door handle navigation", "Object sorting", "Shelf restocking",
    "Payload transfer", "Vision calibration sweep", "Maintenance self-check",
]
STATUS_WEIGHTS = ["active"] * 14 + ["idle"] * 3 + ["charging"] * 2 + ["error"] * 1
SR_BY_MODEL = {"franka": (0.70, 0.85), "ur5e": (0.65, 0.80), "xarm7": (0.55, 0.75), "kinova": (0.45, 0.70)}


def generate_mock_fleet(n_robots: int = 20, seed: int = 42) -> List[RobotUnit]:
    rng = random.Random(seed)
    robots: List[RobotUnit] = []
    now = datetime.utcnow()

    for i in range(n_robots):
        model = rng.choice(MODELS)
        status = rng.choice(STATUS_WEIGHTS)
        sr_lo, sr_hi = SR_BY_MODEL[model]
        sr = round(rng.uniform(sr_lo, sr_hi), 3) if status == "active" else round(rng.uniform(sr_lo * 0.7, sr_lo), 3)
        battery = rng.randint(5, 100) if status != "charging" else rng.randint(15, 75)
        tasks = rng.randint(8, 42) if status == "active" else rng.randint(0, 8)
        hb_delta = rng.randint(2, 120) if status != "error" else rng.randint(300, 3600)
        hb_time = now - timedelta(seconds=hb_delta)
        uptime = round(rng.uniform(0.5, 23.9) if status != "error" else rng.uniform(0.1, 4.0), 1)
        customer = CUSTOMERS[i % len(CUSTOMERS)]
        loc = LOCATIONS[i % len(LOCATIONS)]
        current = rng.choice(TASKS) if status == "active" else ("—" if status == "error" else "Standby")

        robots.append(RobotUnit(
            unit_id=f"RBT-{1000 + i:04d}",
            name=f"{model.upper()}-{i+1:02d}",
            model=model,
            location=loc,
            customer=customer,
            status=status,
            battery_pct=battery,
            current_task=current,
            tasks_today=tasks,
            sr_today=sr,
            uptime_hr=uptime,
            last_heartbeat=hb_time.strftime("%H:%M:%S UTC"),
        ))

    return robots


def generate_alerts(robots: List[RobotUnit], seed: int = 42) -> List[FleetAlert]:
    rng = random.Random(seed + 1)
    alerts: List[FleetAlert] = []
    now = datetime.utcnow()
    aid = 1

    error_robots = [r for r in robots if r.status == "error"]
    low_batt = [r for r in robots if r.battery_pct < 20 and r.status != "charging"]
    high_sr = [r for r in robots if r.sr_today >= 0.80 and r.status == "active"]

    for r in error_robots:
        delta = timedelta(minutes=rng.randint(1, 60))
        alerts.append(FleetAlert(
            alert_id=f"ALT-{aid:03d}", unit_id=r.unit_id, severity="critical",
            message=f"Unit {r.name} unresponsive — last heartbeat {r.last_heartbeat}",
            timestamp=(now - delta).strftime("%Y-%m-%d %H:%M UTC"),
        ))
        aid += 1

    for r in low_batt[:4]:
        delta = timedelta(minutes=rng.randint(5, 30))
        alerts.append(FleetAlert(
            alert_id=f"ALT-{aid:03d}", unit_id=r.unit_id, severity="warning",
            message=f"Low battery on {r.name}: {r.battery_pct}% — consider charging",
            timestamp=(now - delta).strftime("%Y-%m-%d %H:%M UTC"),
        ))
        aid += 1

    for r in high_sr[:max(2, 12 - len(error_robots) - min(len(low_batt), 4))]:
        delta = timedelta(minutes=rng.randint(10, 120))
        alerts.append(FleetAlert(
            alert_id=f"ALT-{aid:03d}", unit_id=r.unit_id, severity="info",
            message=f"{r.name} achieved top SR {r.sr_today:.1%} today ({r.tasks_today} tasks)",
            timestamp=(now - delta).strftime("%Y-%m-%d %H:%M UTC"),
        ))
        aid += 1

    # Pad to 8-12 if needed
    while len(alerts) < 8:
        r = rng.choice(robots)
        delta = timedelta(minutes=rng.randint(15, 180))
        alerts.append(FleetAlert(
            alert_id=f"ALT-{aid:03d}", unit_id=r.unit_id, severity="info",
            message=f"Scheduled maintenance window for {r.name} at {r.location}",
            timestamp=(now - delta).strftime("%Y-%m-%d %H:%M UTC"),
        ))
        aid += 1

    return alerts[:12]


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _svg_donut(robots: List[RobotUnit]) -> str:
    counts = {"active": 0, "idle": 0, "charging": 0, "error": 0}
    for r in robots:
        counts[r.status] = counts.get(r.status, 0) + 1
    total = sum(counts.values())
    colors = {"active": "#22c55e", "idle": "#94a3b8", "charging": "#60a5fa", "error": "#ef4444"}
    labels_order = ["active", "idle", "charging", "error"]

    cx, cy, r_out, r_in = 110, 110, 90, 52
    paths = []
    start_angle = -math.pi / 2

    for status in labels_order:
        cnt = counts[status]
        if cnt == 0:
            continue
        sweep = 2 * math.pi * cnt / total
        end_angle = start_angle + sweep
        lx = cx + (r_out + r_in) / 2 * math.cos(start_angle + sweep / 2)
        ly = cy + (r_out + r_in) / 2 * math.sin(start_angle + sweep / 2)
        x1, y1 = cx + r_out * math.cos(start_angle), cy + r_out * math.sin(start_angle)
        x2, y2 = cx + r_out * math.cos(end_angle), cy + r_out * math.sin(end_angle)
        ix1, iy1 = cx + r_in * math.cos(end_angle), cy + r_in * math.sin(end_angle)
        ix2, iy2 = cx + r_in * math.cos(start_angle), cy + r_in * math.sin(start_angle)
        large = 1 if sweep > math.pi else 0
        d = (f"M {x1:.1f} {y1:.1f} A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} "
             f"L {ix1:.1f} {iy1:.1f} A {r_in} {r_in} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z")
        paths.append(f'<path d="{d}" fill="{colors[status]}" />')
        paths.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dy="0.35em" '
                     f'fill="#fff" font-size="12" font-weight="bold">{cnt}</text>')
        start_angle = end_angle

    paths.append(f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" fill="#e2e8f0" font-size="13">Total</text>')
    paths.append(f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" fill="#e2e8f0" font-size="20" font-weight="bold">{total}</text>')

    legend = ""
    lx_start, ly_start = 220, 60
    for i, status in enumerate(labels_order):
        ly = ly_start + i * 28
        legend += (f'<rect x="{lx_start}" y="{ly}" width="14" height="14" rx="3" fill="{colors[status]}" />'
                   f'<text x="{lx_start + 20}" y="{ly + 11}" fill="#cbd5e1" font-size="13">'
                   f'{status.capitalize()} ({counts[status]})</text>')

    return (f'<svg width="340" height="220" xmlns="http://www.w3.org/2000/svg">'
            f'{"".join(paths)}{legend}</svg>')


def _svg_sr_histogram(robots: List[RobotUnit]) -> str:
    active = [r.sr_today for r in robots if r.status == "active"]
    bins = [0] * 10
    edges = [0.3 + i * 0.06 for i in range(11)]
    for v in active:
        idx = min(int((v - 0.3) / 0.06), 9)
        if 0 <= idx < 10:
            bins[idx] += 1
    max_bin = max(bins) if bins else 1

    W, H, pad_l, pad_b = 340, 200, 40, 30
    bar_w = (W - pad_l - 10) / 10
    bars = []
    for i, cnt in enumerate(bins):
        bh = (cnt / max_bin) * (H - pad_b - 20) if max_bin else 0
        bx = pad_l + i * bar_w
        by = H - pad_b - bh
        bars.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 2:.1f}" height="{bh:.1f}" '
                    f'fill="#C74634" rx="2" />')
        if cnt:
            bars.append(f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" text-anchor="middle" '
                        f'fill="#e2e8f0" font-size="11">{cnt}</text>')
        label = f"{edges[i]:.2f}"
        bars.append(f'<text x="{bx + bar_w/2:.1f}" y="{H - pad_b + 14:.1f}" text-anchor="middle" '
                    f'fill="#94a3b8" font-size="10">{label}</text>')

    bars.append(f'<line x1="{pad_l}" y1="{H - pad_b}" x2="{W - 10}" y2="{H - pad_b}" '
                f'stroke="#475569" stroke-width="1"/>')
    bars.append(f'<text x="{W/2}" y="{H}" text-anchor="middle" fill="#94a3b8" font-size="11">SR Rate (active robots)</text>')

    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def _svg_customer_bar(robots: List[RobotUnit]) -> str:
    colors = {"franka": "#C74634", "ur5e": "#3b82f6", "xarm7": "#a855f7", "kinova": "#f59e0b"}
    data: dict = {c: {"franka": 0, "ur5e": 0, "xarm7": 0, "kinova": 0} for c in CUSTOMERS}
    for r in robots:
        data[r.customer][r.model] += 1

    W, H, pad_l, pad_b = 380, 200, 110, 30
    max_total = max(sum(data[c].values()) for c in CUSTOMERS)
    bar_h = (H - pad_b - 20) / len(CUSTOMERS)
    elems = []

    for ci, cust in enumerate(CUSTOMERS):
        by = 20 + ci * bar_h
        elems.append(f'<text x="{pad_l - 6}" y="{by + bar_h/2 + 4:.1f}" text-anchor="end" '
                     f'fill="#cbd5e1" font-size="11">{cust}</text>')
        x_off = pad_l
        for model in MODELS:
            cnt = data[cust][model]
            if cnt == 0:
                continue
            bw = (cnt / max_total) * (W - pad_l - 20)
            elems.append(f'<rect x="{x_off:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bar_h - 4:.1f}" '
                         f'fill="{colors[model]}" rx="2" />')
            if bw > 20:
                elems.append(f'<text x="{x_off + bw/2:.1f}" y="{by + bar_h/2:.1f}" text-anchor="middle" '
                              f'dy="0.35em" fill="#fff" font-size="10">{cnt}</text>')
            x_off += bw

    # Legend
    lx, ly = pad_l, H - pad_b + 4
    for i, model in enumerate(MODELS):
        lxi = lx + i * 82
        elems.append(f'<rect x="{lxi}" y="{ly}" width="12" height="12" rx="2" fill="{colors[model]}" />')
        elems.append(f'<text x="{lxi + 15}" y="{ly + 10}" fill="#94a3b8" font-size="11">{model}</text>')

    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">{"".join(elems)}</svg>'


# ---------------------------------------------------------------------------
# HTML report builder
# ---------------------------------------------------------------------------

def build_html(robots: List[RobotUnit], alerts: List[FleetAlert]) -> str:
    active_robots = [r for r in robots if r.status == "active"]
    avg_sr = sum(r.sr_today for r in active_robots) / len(active_robots) if active_robots else 0
    critical_cnt = sum(1 for a in alerts if a.severity == "critical")
    avg_uptime = sum(r.uptime_hr for r in robots) / len(robots) if robots else 0
    active_cnt = sum(1 for r in robots if r.status == "active")
    gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    sev_colors = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
    status_colors = {"active": "#22c55e", "idle": "#94a3b8", "charging": "#60a5fa", "error": "#ef4444"}

    kpi_cards = f"""
    <div class="kpi-row">
      <div class="kpi-card"><div class="kpi-val">{len(robots)}</div><div class="kpi-label">Total Fleet</div></div>
      <div class="kpi-card"><div class="kpi-val" style="color:#22c55e">{active_cnt}</div><div class="kpi-label">Active Now</div></div>
      <div class="kpi-card"><div class="kpi-val" style="color:#C74634">{avg_sr:.1%}</div><div class="kpi-label">Avg SR Today</div></div>
      <div class="kpi-card"><div class="kpi-val" style="color:#ef4444">{critical_cnt}</div><div class="kpi-label">Critical Alerts</div></div>
      <div class="kpi-card"><div class="kpi-val">{avg_uptime:.1f}h</div><div class="kpi-label">Avg Uptime</div></div>
    </div>"""

    alert_rows = ""
    for a in alerts:
        col = sev_colors.get(a.severity, "#94a3b8")
        alert_rows += (f'<tr><td><span class="badge" style="background:{col}">{a.severity}</span></td>'
                       f'<td>{a.unit_id}</td><td>{a.message}</td><td>{a.timestamp}</td></tr>')

    robot_rows = ""
    for r in robots:
        sc = status_colors.get(r.status, "#94a3b8")
        batt_color = "#ef4444" if r.battery_pct < 20 else "#22c55e" if r.battery_pct > 60 else "#f59e0b"
        batt_bar = (f'<div style="background:#334155;border-radius:4px;width:60px;height:10px;display:inline-block;vertical-align:middle">'
                    f'<div style="background:{batt_color};width:{r.battery_pct}%;height:100%;border-radius:4px"></div></div>'
                    f' <span style="font-size:11px">{r.battery_pct}%</span>')
        robot_rows += (f'<tr>'
                       f'<td><span style="color:{sc}">&#9679;</span> {r.unit_id}</td>'
                       f'<td>{r.name}</td><td>{r.model}</td><td>{r.customer}</td>'
                       f'<td>{r.location}</td>'
                       f'<td><span class="badge" style="background:{sc}">{r.status}</span></td>'
                       f'<td>{r.sr_today:.1%}</td><td>{r.tasks_today}</td>'
                       f'<td>{batt_bar}</td>'
                       f'<td>{r.uptime_hr}h</td>'
                       f'<td style="font-size:11px;color:#94a3b8">{r.last_heartbeat}</td>'
                       f'</tr>')

    donut_svg = _svg_donut(robots)
    hist_svg = _svg_sr_histogram(robots)
    cust_svg = _svg_customer_bar(robots)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta http-equiv="refresh" content="15"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Fleet Dashboard</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;padding:24px}}
  h1{{color:#C74634;font-size:24px;margin-bottom:4px}}
  h2{{color:#C74634;font-size:16px;margin:24px 0 12px}}
  .subtitle{{color:#94a3b8;font-size:12px;margin-bottom:24px}}
  .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
  .kpi-card{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:18px 24px;min-width:130px;flex:1}}
  .kpi-val{{font-size:28px;font-weight:700;color:#e2e8f0}}
  .kpi-label{{color:#94a3b8;font-size:12px;margin-top:4px}}
  .charts-row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:28px}}
  .chart-box{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:16px;flex:1;min-width:280px}}
  .chart-title{{color:#94a3b8;font-size:12px;margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse;background:#0f172a;border-radius:10px;overflow:hidden}}
  th{{background:#1e293b;color:#94a3b8;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left}}
  td{{padding:9px 12px;border-top:1px solid #1e293b;font-size:13px;color:#cbd5e1}}
  tr:hover td{{background:#1a2940}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;color:#fff}}
  .section{{margin-bottom:28px}}
  .table-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #334155}}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Fleet Dashboard</h1>
<p class="subtitle">Generated {gen_time} &bull; Auto-refreshes every 15s &bull; {len(robots)} units across {len(CUSTOMERS)} customers</p>

{kpi_cards}

<div class="charts-row">
  <div class="chart-box">
    <div class="chart-title">Fleet Status Distribution</div>
    {donut_svg}
  </div>
  <div class="chart-box">
    <div class="chart-title">SR Rate Distribution (Active Robots)</div>
    {hist_svg}
  </div>
  <div class="chart-box">
    <div class="chart-title">Robots per Customer by Model</div>
    {cust_svg}
  </div>
</div>

<div class="section">
  <h2>Active Alerts</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Severity</th><th>Unit ID</th><th>Message</th><th>Timestamp</th></tr></thead>
      <tbody>{alert_rows}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <h2>All Robot Units</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Unit ID</th><th>Name</th><th>Model</th><th>Customer</th><th>Location</th>
        <th>Status</th><th>SR Today</th><th>Tasks</th><th>Battery</th><th>Uptime</th><th>Last HB</th></tr></thead>
      <tbody>{robot_rows}</tbody>
    </table>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

_robots: List[RobotUnit] = []
_alerts: List[FleetAlert] = []


class FleetHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[fleet] {self.address_string()} {fmt % args}")

    def do_GET(self):
        if self.path == "/api/fleet":
            payload = json.dumps({
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "robots": [asdict(r) for r in _robots],
                "alerts": [asdict(a) for a in _alerts],
            }, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path in ("/", "/index.html"):
            html = build_html(_robots, _alerts).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Fleet Dashboard")
    parser.add_argument("--mock", action="store_true", default=True, help="Use mock data (default)")
    parser.add_argument("--port", type=int, default=8065, help="HTTP port (default: 8065)")
    parser.add_argument("--output", type=str, default="", help="Save HTML to file and exit")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--n-robots", type=int, default=20, help="Number of mock robots")
    args = parser.parse_args()

    global _robots, _alerts
    _robots = generate_mock_fleet(n_robots=args.n_robots, seed=args.seed)
    _alerts = generate_alerts(_robots, seed=args.seed)

    if args.output:
        html = build_html(_robots, _alerts)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"[fleet] Dashboard saved to {args.output}")
        return

    server = HTTPServer(("0.0.0.0", args.port), FleetHandler)
    print(f"[fleet] Dashboard running at http://localhost:{args.port}/")
    print(f"[fleet] JSON API at http://localhost:{args.port}/api/fleet")
    print(f"[fleet] Fleet: {len(_robots)} robots | Alerts: {len(_alerts)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[fleet] Shutting down.")


if __name__ == "__main__":
    main()
