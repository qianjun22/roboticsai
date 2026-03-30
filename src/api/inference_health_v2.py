"""inference_health_v2.py — Enhanced inference health monitoring with anomaly detection
and auto-remediation. FastAPI service on port 8250.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

def _generate_48h_series():
    """Generate 48 hours of 1-hour resolution mock metrics."""
    base_time = datetime(2026, 3, 29, 0, 0, 0)
    series = []
    for h in range(48):
        ts = base_time + timedelta(hours=h)
        # Normal baseline
        latency_p50 = 85 + 15 * math.sin(h * math.pi / 12) + random.gauss(0, 5)
        latency_p95 = latency_p50 * 1.6 + random.gauss(0, 8)
        error_rate = max(0.0, 0.003 + 0.001 * math.sin(h * math.pi / 8) + random.gauss(0, 0.001))
        throughput = 420 + 80 * math.sin(h * math.pi / 12) + random.gauss(0, 20)
        gpu_temp = 68 + 6 * math.sin(h * math.pi / 12) + random.gauss(0, 1.5)

        # Anomaly 1: latency spike at day1 hour14 (index 14)
        if 13 <= h <= 15:
            spike = max(0, (14.5 - abs(h - 14)) / 0.5)
            latency_p50 += spike * 700
            latency_p95 += spike * 900
            error_rate += spike * 0.04
            throughput -= spike * 150

        # Anomaly 2: GPU temp spike at day2 around hour 34-36 (index 34-36)
        if 33 <= h <= 37:
            spike = max(0, (2.5 - abs(h - 35)) / 2.5)
            gpu_temp += spike * 22
            latency_p50 += spike * 40
            latency_p95 += spike * 60

        series.append({
            "hour": h,
            "ts": ts.strftime("%m-%d %H:00"),
            "latency_p50": round(max(10, latency_p50), 1),
            "latency_p95": round(max(20, latency_p95), 1),
            "error_rate": round(max(0, error_rate) * 100, 3),
            "throughput": round(max(50, throughput), 1),
            "gpu_temp": round(min(92, max(55, gpu_temp)), 1),
        })
    return series


SERIES = _generate_48h_series()

ANOMALY_EVENTS = [
    {
        "id": "ANO-001",
        "metric": "latency_p95",
        "start_hour": 13,
        "end_hour": 15,
        "peak": "891ms",
        "detected_at": "2026-03-29 13:04",
        "action": "auto-restart",
        "resolved_in": "3 min",
        "severity": "HIGH",
    },
    {
        "id": "ANO-002",
        "metric": "gpu_temp",
        "start_hour": 33,
        "end_hour": 37,
        "peak": "87°C",
        "detected_at": "2026-03-30 09:12",
        "action": "throttle",
        "resolved_in": "8 min",
        "severity": "MEDIUM",
    },
]

SUMMARY = {
    "uptime_pct": 99.72,
    "mttr_min": 5.5,
    "detection_latency_sec": 48,
    "auto_remediation_success_rate": 100.0,
    "false_positive_rate": 1.2,
    "total_anomalies_48h": 2,
    "current_latency_p50": SERIES[-1]["latency_p50"],
    "current_latency_p95": SERIES[-1]["latency_p95"],
    "current_gpu_temp": SERIES[-1]["gpu_temp"],
    "current_error_rate": SERIES[-1]["error_rate"],
    "current_throughput": SERIES[-1]["throughput"],
}


# ---------------------------------------------------------------------------
# SVG generation helpers
# ---------------------------------------------------------------------------

def _svg_time_series() -> str:
    """48h multi-metric time series with anomaly bands."""
    W, H = 900, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 30, 50
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B
    N = len(SERIES)

    def sx(h): return PAD_L + (h / (N - 1)) * PLOT_W
    def sy_lat(v, lo=0, hi=950):
        return PAD_T + PLOT_H - ((v - lo) / (hi - lo)) * PLOT_H

    # Polyline for p50
    p50_pts = " ".join(f"{sx(d['hour']):.1f},{sy_lat(d['latency_p50']):.1f}" for d in SERIES)
    p95_pts = " ".join(f"{sx(d['hour']):.1f},{sy_lat(d['latency_p95']):.1f}" for d in SERIES)

    # Anomaly bands
    bands = ""
    for ev in ANOMALY_EVENTS:
        x1 = sx(ev["start_hour"])
        x2 = sx(ev["end_hour"])
        bands += f'<rect x="{x1:.1f}" y="{PAD_T}" width="{x2-x1:.1f}" height="{PLOT_H}" fill="rgba(239,68,68,0.15)" />'

    # X-axis ticks every 6h
    x_ticks = ""
    for h in range(0, 49, 6):
        x = sx(h)
        label = f"D{h//24+1} {(h%24):02d}h"
        x_ticks += f'<line x1="{x:.1f}" y1="{PAD_T+PLOT_H}" x2="{x:.1f}" y2="{PAD_T+PLOT_H+5}" stroke="#475569" />'
        x_ticks += f'<text x="{x:.1f}" y="{PAD_T+PLOT_H+18}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'

    # Y-axis labels
    y_labels = ""
    for v in [0, 200, 400, 600, 800]:
        y = sy_lat(v)
        y_labels += f'<line x1="{PAD_L-4}" y1="{y:.1f}" x2="{PAD_L+PLOT_W}" y2="{y:.1f}" stroke="#1e293b" stroke-dasharray="4,4" />'
        y_labels += f'<text x="{PAD_L-8}" y="{y+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{v}</text>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="width:100%;background:#1e293b;border-radius:8px">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  <text x="{W//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">48h Inference Metrics — Latency p50/p95 with Anomaly Windows</text>
  {bands}
  {y_labels}
  {x_ticks}
  <polyline points="{p50_pts}" fill="none" stroke="#38bdf8" stroke-width="1.8"/>
  <polyline points="{p95_pts}" fill="none" stroke="#f97316" stroke-width="1.8" stroke-dasharray="6,2"/>
  <!-- Anomaly markers -->
  <rect x="{sx(13):.1f}" y="{PAD_T+2}" width="8" height="8" fill="#ef4444" rx="2"/>
  <text x="{sx(13)+12:.1f}" y="{PAD_T+11}" fill="#ef4444" font-size="9">ANO-001 restart</text>
  <rect x="{sx(33):.1f}" y="{PAD_T+2}" width="8" height="8" fill="#f59e0b" rx="2"/>
  <text x="{sx(33)+12:.1f}" y="{PAD_T+11}" fill="#f59e0b" font-size="9">ANO-002 throttle</text>
  <!-- Legend -->
  <line x1="{PAD_L}" y1="{H-10}" x2="{PAD_L+20}" y2="{H-10}" stroke="#38bdf8" stroke-width="2"/>
  <text x="{PAD_L+24}" y="{H-6}" fill="#94a3b8" font-size="9">p50 latency (ms)</text>
  <line x1="{PAD_L+140}" y1="{H-10}" x2="{PAD_L+160}" y2="{H-10}" stroke="#f97316" stroke-width="2" stroke-dasharray="6,2"/>
  <text x="{PAD_L+164}" y="{H-6}" fill="#94a3b8" font-size="9">p95 latency (ms)</text>
  <rect x="{PAD_L+300}" y="{H-16}" width="10" height="10" fill="rgba(239,68,68,0.3)"/>
  <text x="{PAD_L+314}" y="{H-6}" fill="#94a3b8" font-size="9">anomaly window</text>
  <!-- Axes -->
  <line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <line x1="{PAD_L}" y1="{PAD_T+PLOT_H}" x2="{PAD_L+PLOT_W}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <text x="{PAD_L-35}" y="{PAD_T+PLOT_H//2}" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90,{PAD_L-35},{PAD_T+PLOT_H//2})">Latency (ms)</text>
</svg>"""
    return svg


def _svg_anomaly_timeline() -> str:
    """Horizontal lane timeline showing anomaly events and remediation actions."""
    W, H = 900, 260
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 20, 40, 40
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B
    TOTAL_HOURS = 48
    LANES = ["latency_p50", "latency_p95", "error_rate", "gpu_temp", "throughput"]
    LANE_H = PLOT_H // len(LANES)

    def tx(h): return PAD_L + (h / TOTAL_HOURS) * PLOT_W

    lane_svgs = ""
    for i, lane in enumerate(LANES):
        y_center = PAD_T + i * LANE_H + LANE_H // 2
        lane_svgs += f'<line x1="{PAD_L}" y1="{y_center}" x2="{PAD_L+PLOT_W}" y2="{y_center}" stroke="#1e3a5f" stroke-dasharray="3,5"/>'
        lane_svgs += f'<text x="{PAD_L-8}" y="{y_center+4}" fill="#94a3b8" font-size="9" text-anchor="end">{lane}</text>'

    events_svg = ""
    # ANO-001: latency_p95 spike
    ev1_lane = 1  # latency_p95
    ev1_y = PAD_T + ev1_lane * LANE_H + LANE_H // 2
    ev1_x1 = tx(13); ev1_x2 = tx(15)
    events_svg += f'<rect x="{ev1_x1:.1f}" y="{ev1_y-10}" width="{ev1_x2-ev1_x1:.1f}" height="20" fill="#ef4444" rx="3" opacity="0.8"/>'
    events_svg += f'<text x="{(ev1_x1+ev1_x2)/2:.1f}" y="{ev1_y+4}" fill="white" font-size="8" text-anchor="middle" font-weight="bold">891ms peak</text>'
    # Remediation: restart at h=15
    rem1_x = tx(15.05)
    events_svg += f'<polygon points="{rem1_x},{ev1_y-14} {rem1_x+8},{ev1_y-6} {rem1_x-8},{ev1_y-6}" fill="#22c55e"/>'
    events_svg += f'<text x="{rem1_x+12}" y="{ev1_y-8}" fill="#22c55e" font-size="8">restart +3min</text>'

    # ANO-002: gpu_temp spike
    ev2_lane = 3  # gpu_temp
    ev2_y = PAD_T + ev2_lane * LANE_H + LANE_H // 2
    ev2_x1 = tx(33); ev2_x2 = tx(37)
    events_svg += f'<rect x="{ev2_x1:.1f}" y="{ev2_y-10}" width="{ev2_x2-ev2_x1:.1f}" height="20" fill="#f59e0b" rx="3" opacity="0.8"/>'
    events_svg += f'<text x="{(ev2_x1+ev2_x2)/2:.1f}" y="{ev2_y+4}" fill="white" font-size="8" text-anchor="middle" font-weight="bold">87°C peak</text>'
    # Remediation: throttle at h=37
    rem2_x = tx(37.05)
    events_svg += f'<polygon points="{rem2_x},{ev2_y-14} {rem2_x+8},{ev2_y-6} {rem2_x-8},{ev2_y-6}" fill="#38bdf8"/>'
    events_svg += f'<text x="{rem2_x+12}" y="{ev2_y-8}" fill="#38bdf8" font-size="8">throttle +8min</text>'

    # Normal heartbeats on each lane (small dots)
    dots = ""
    for i, lane in enumerate(LANES):
        y_center = PAD_T + i * LANE_H + LANE_H // 2
        for h in range(0, 49, 2):
            anomaly = (lane == "latency_p95" and 13 <= h <= 15) or (lane == "gpu_temp" and 33 <= h <= 37)
            if not anomaly:
                dots += f'<circle cx="{tx(h):.1f}" cy="{y_center}" r="2" fill="#38bdf8" opacity="0.4"/>'

    # X ticks
    x_ticks = ""
    for h in range(0, 49, 6):
        x = tx(h)
        label = f"D{h//24+1}/{(h%24):02d}h"
        x_ticks += f'<line x1="{x:.1f}" y1="{PAD_T+PLOT_H}" x2="{x:.1f}" y2="{PAD_T+PLOT_H+5}" stroke="#475569"/>'
        x_ticks += f'<text x="{x:.1f}" y="{PAD_T+PLOT_H+18}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="width:100%;background:#1e293b;border-radius:8px">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  <text x="{W//2}" y="20" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Anomaly Event Timeline — Detection &amp; Auto-Remediation</text>
  {lane_svgs}
  {dots}
  {events_svg}
  {x_ticks}
  <!-- Axes -->
  <line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <line x1="{PAD_L}" y1="{PAD_T+PLOT_H}" x2="{PAD_L+PLOT_W}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <!-- Legend -->
  <rect x="{PAD_L}" y="{H-18}" width="10" height="10" fill="#ef4444" rx="2"/>
  <text x="{PAD_L+14}" y="{H-8}" fill="#94a3b8" font-size="9">HIGH anomaly</text>
  <rect x="{PAD_L+110}" y="{H-18}" width="10" height="10" fill="#f59e0b" rx="2"/>
  <text x="{PAD_L+124}" y="{H-8}" fill="#94a3b8" font-size="9">MEDIUM anomaly</text>
  <polygon points="{PAD_L+240},{H-18} {PAD_L+248},{H-10} {PAD_L+232},{H-10}" fill="#22c55e"/>
  <text x="{PAD_L+254}" y="{H-8}" fill="#94a3b8" font-size="9">auto-remediation</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg1 = _svg_time_series()
    svg2 = _svg_anomaly_timeline()
    s = SUMMARY
    anomaly_rows = ""
    for ev in ANOMALY_EVENTS:
        sev_color = "#ef4444" if ev["severity"] == "HIGH" else "#f59e0b"
        anomaly_rows += f"""<tr>
          <td style='padding:8px;color:#38bdf8'>{ev['id']}</td>
          <td style='padding:8px;color:#e2e8f0'>{ev['metric']}</td>
          <td style='padding:8px;color:{sev_color};font-weight:bold'>{ev['severity']}</td>
          <td style='padding:8px;color:#ef4444'>{ev['peak']}</td>
          <td style='padding:8px;color:#94a3b8'>{ev['detected_at']}</td>
          <td style='padding:8px;color:#22c55e'>{ev['action']}</td>
          <td style='padding:8px;color:#a3e635'>{ev['resolved_in']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inference Health v2 — Port 8250</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  .header {{ background: linear-gradient(135deg, #C74634 0%, #7c1e0e 100%); padding: 20px 32px; display:flex; align-items:center; gap:16px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; }}
  .header .badge {{ background: rgba(255,255,255,0.15); padding: 3px 10px; border-radius: 99px; font-size: 12px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; }}
  .kpi .label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing:.05em; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; margin: 6px 0 2px; }}
  .kpi .sub {{ font-size: 11px; color: #94a3b8; }}
  .chart-card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 20px; border: 1px solid #334155; }}
  .chart-card h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead tr {{ background: #0f172a; }}
  th {{ padding: 10px 8px; text-align: left; color: #64748b; font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  tbody tr:hover {{ background: #263248; }}
  tbody tr {{ border-bottom: 1px solid #1e293b; }}
  .status-ok {{ color: #22c55e; font-weight: 700; }}
  .footer {{ text-align: center; color: #475569; font-size: 11px; padding: 20px; }}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="badge">Port 8250</div>
    <h1>Inference Health v2</h1>
    <div style="font-size:13px;color:rgba(255,255,255,0.7);margin-top:4px">Enhanced monitoring · Anomaly detection · Auto-remediation</div>
  </div>
  <div style="margin-left:auto;text-align:right">
    <div style="font-size:28px;font-weight:800;color:#a3e635">{s['uptime_pct']}%</div>
    <div style="font-size:11px;color:rgba(255,255,255,0.6)">48h uptime</div>
  </div>
</div>
<div class="container">
  <div class="kpi-grid">
    <div class="kpi"><div class="label">Anomalies (48h)</div><div class="value" style="color:#ef4444">{s['total_anomalies_48h']}</div><div class="sub">detected</div></div>
    <div class="kpi"><div class="label">MTTR</div><div class="value" style="color:#38bdf8">{s['mttr_min']}m</div><div class="sub">mean time to resolve</div></div>
    <div class="kpi"><div class="label">Detection Latency</div><div class="value" style="color:#a78bfa">{s['detection_latency_sec']}s</div><div class="sub">avg anomaly lag</div></div>
    <div class="kpi"><div class="label">Auto-Remediation</div><div class="value" style="color:#22c55e">{s['auto_remediation_success_rate']}%</div><div class="sub">success rate</div></div>
    <div class="kpi"><div class="label">False Positives</div><div class="value" style="color:#f59e0b">{s['false_positive_rate']}%</div><div class="sub">rate</div></div>
    <div class="kpi"><div class="label">Current p95</div><div class="value" style="color:#f97316">{s['current_latency_p95']}ms</div><div class="sub">inference latency</div></div>
    <div class="kpi"><div class="label">GPU Temp</div><div class="value" style="color:#38bdf8">{s['current_gpu_temp']}°C</div><div class="sub">current</div></div>
    <div class="kpi"><div class="label">Throughput</div><div class="value" style="color:#a3e635">{s['current_throughput']:.0f}</div><div class="sub">req/min</div></div>
  </div>

  <div class="chart-card">
    <h2>48h Multi-Metric Time Series (1h resolution) — Anomaly Windows Highlighted</h2>
    {svg1}
  </div>

  <div class="chart-card">
    <h2>Anomaly Event Timeline — Per-Metric Lanes with Auto-Remediation Actions</h2>
    {svg2}
  </div>

  <div class="chart-card">
    <h2>Anomaly Event Log</h2>
    <table>
      <thead><tr><th>ID</th><th>Metric</th><th>Severity</th><th>Peak</th><th>Detected At</th><th>Action</th><th>Resolved In</th></tr></thead>
      <tbody>{anomaly_rows}</tbody>
    </table>
  </div>
</div>
<div class="footer">OCI Robot Cloud · Inference Health v2 · Port 8250 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Inference Health v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "inference_health_v2", "port": 8250}

    @app.get("/metrics")
    def metrics():
        return SUMMARY

    @app.get("/anomalies")
    def anomalies():
        return {"anomaly_events": ANOMALY_EVENTS, "total": len(ANOMALY_EVENTS)}

    @app.get("/series")
    def series():
        return {"series": SERIES, "hours": len(SERIES)}

else:
    # Stdlib fallback
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", ""):
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8250}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/metrics":
                body = json.dumps(SUMMARY).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass

    def _run_stdlib():
        with socketserver.TCPServer(("", 8250), _Handler) as httpd:
            print("inference_health_v2 (stdlib fallback) listening on port 8250")
            httpd.serve_forever()


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8250)
    else:
        _run_stdlib()
