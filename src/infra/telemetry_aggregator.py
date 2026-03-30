"""telemetry_aggregator.py — OCI Robot Cloud Telemetry Aggregator Service (port 8252)

Aggregates telemetry from all OCI Robot Cloud services into a unified metrics stream.
Provides real-time health matrix, event volume trends, and anomaly detection.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generators
# ---------------------------------------------------------------------------

SERVICES = [
    "inference", "fine_tune", "eval", "dagger", "sdg_pipeline",
    "monitor", "data_collector", "checkpoint_mgr", "registry",
    "scheduler", "cost_tracker", "safety_monitor", "telemetry",
    "api_gateway", "auth_service"
]

# Seed for reproducibility
random.seed(42)


def generate_health_matrix():
    """24h x 15 services health matrix (0-100 score)."""
    matrix = []
    for hour in range(24):
        row = []
        for svc in SERVICES:
            base = 99.0
            # sdg_pipeline had 2h degradation on current day around hours 10-11
            if svc == "sdg_pipeline" and hour in (10, 11):
                score = random.uniform(42, 58)
            # inference generally excellent
            elif svc == "inference":
                score = random.uniform(99.5, 100.0)
            # slight noise elsewhere
            else:
                score = random.uniform(96, 100)
            row.append(round(score, 1))
        matrix.append(row)
    return matrix


def generate_event_volume_7d():
    """Hourly event volume over 7 days (168 data points)."""
    volumes = []
    for day in range(7):
        for hour in range(24):
            base = 5000  # ~127k/day normal = ~5292/hr
            # Daily sinusoidal pattern (peak at hour 14)
            daily_pattern = 1.0 + 0.35 * math.sin(math.pi * (hour - 6) / 12)
            # Day 4 DAgger run10 spike
            if day == 3 and 8 <= hour <= 16:
                spike_factor = 2.7 + random.uniform(-0.2, 0.4)
            else:
                spike_factor = 1.0
            noise = random.uniform(0.92, 1.08)
            vol = int(base * daily_pattern * spike_factor * noise)
            volumes.append(vol)
    return volumes


HEALTH_MATRIX = generate_health_matrix()
EVENT_VOLUMES = generate_event_volume_7d()

# Aggregated KPIs
TOTAL_EVENTS_TODAY = 127_341
SPIKE_DAY4 = 341_027
INFERENCE_SLA = 99.8
ANOMALY_COUNT = 7
DATA_COMPLETENESS = 98.6
INGESTION_RATE = 1473  # events/sec peak


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def build_health_heatmap_svg():
    """SVG heatmap: rows=hours(0-23), cols=15 services."""
    cell_w, cell_h = 36, 18
    left_margin = 28
    top_margin = 90
    width = left_margin + cell_w * len(SERVICES) + 20
    height = top_margin + cell_h * 24 + 30

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    parts.append(f'<rect width="{width}" height="{height}" fill="#0f172a"/>')
    parts.append(f'<text x="{width//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Service Health Matrix — Last 24 Hours</text>')
    parts.append(f'<text x="{width//2}" y="40" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">rows = hour (0–23 UTC)  |  cols = 15 OCI Robot Cloud services</text>')

    # Color legend
    legend_items = [("#22c55e", "Healthy (95-100)"), ("#f59e0b", "Degraded (70-95)"), ("#ef4444", "Critical (<70)")]
    lx = left_margin
    for color, label in legend_items:
        parts.append(f'<rect x="{lx}" y="52" width="12" height="10" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{lx+16}" y="61" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')
        lx += 145

    # Column headers (abbreviated)
    abbrevs = [s[:6] for s in SERVICES]
    for ci, abbr in enumerate(abbrevs):
        x = left_margin + ci * cell_w + cell_w // 2
        y = top_margin - 6
        parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" fill="#94a3b8" font-size="7.5" font-family="monospace" transform="rotate(-45 {x} {y})">{abbr}</text>')

    # Cells
    for row_i, row in enumerate(HEALTH_MATRIX):
        # Hour label
        lbl_y = top_margin + row_i * cell_h + cell_h // 2 + 4
        parts.append(f'<text x="{left_margin-4}" y="{lbl_y}" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">{row_i:02d}</text>')
        for col_i, score in enumerate(row):
            x = left_margin + col_i * cell_w
            y = top_margin + row_i * cell_h
            if score >= 95:
                fill = f'rgba(34,197,94,{0.4 + 0.6*(score-95)/5:.2f})'
            elif score >= 70:
                t = (score - 70) / 25
                fill = f'rgba(245,158,11,{0.5 + 0.4*t:.2f})'
            else:
                fill = f'rgba(239,68,68,{0.7 + 0.3*(1-(score/70)):.2f})'
            parts.append(f'<rect x="{x+1}" y="{y+1}" width="{cell_w-2}" height="{cell_h-2}" fill="{fill}" rx="1"/>')

    parts.append('</svg>')
    return '\n'.join(parts)


def build_event_volume_svg():
    """SVG line chart: hourly event volume over 7 days with anomaly flag."""
    w, h = 820, 260
    pad_l, pad_r, pad_t, pad_b = 55, 30, 40, 45
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n = len(EVENT_VOLUMES)
    max_v = max(EVENT_VOLUMES) * 1.05
    min_v = 0

    def sx(i): return pad_l + i * chart_w / (n - 1)
    def sy(v): return pad_t + chart_h - (v - min_v) / (max_v - min_v) * chart_h

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">']
    parts.append(f'<rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>')
    parts.append(f'<text x="{w//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Telemetry Event Volume — 7-Day Trend (Hourly)</text>')

    # Gridlines + y-axis labels
    y_ticks = [0, 5000, 10000, 15000, 20000]
    for v in y_ticks:
        yp = sy(v)
        parts.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{w-pad_r}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-6}" y="{yp+4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v//1000}k</text>')

    # Day separators + labels
    days = ["Mon", "Tue", "Wed", "Thu(D4)", "Fri", "Sat", "Sun"]
    for d in range(7):
        xp = sx(d * 24)
        parts.append(f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lbl_color = "#ef4444" if d == 3 else "#64748b"
        parts.append(f'<text x="{xp+3:.1f}" y="{h-6}" fill="{lbl_color}" font-size="9" font-family="monospace">{days[d]}</text>')

    # Area fill
    area_pts = f'{sx(0):.1f},{pad_t+chart_h} ' + ' '.join(f'{sx(i):.1f},{sy(v):.1f}' for i, v in enumerate(EVENT_VOLUMES)) + f' {sx(n-1):.1f},{pad_t+chart_h}'
    parts.append(f'<polygon points="{area_pts}" fill="rgba(56,189,248,0.10)"/>')

    # Line
    polyline_pts = ' '.join(f'{sx(i):.1f},{sy(v):.1f}' for i, v in enumerate(EVENT_VOLUMES))
    parts.append(f'<polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="1.8"/>')

    # Anomaly flag on day 4 peak (index ~3*24+12 = 84)
    peak_idx = max(range(n), key=lambda i: EVENT_VOLUMES[i])
    px, py = sx(peak_idx), sy(EVENT_VOLUMES[peak_idx])
    parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#ef4444" stroke="#fca5a5" stroke-width="1.5"/>')
    parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{py-28:.1f}" stroke="#ef4444" stroke-width="1.2"/>')
    parts.append(f'<rect x="{px-38:.1f}" y="{py-44:.1f}" width="78" height="14" fill="#7f1d1d" rx="3"/>')
    parts.append(f'<text x="{px:.1f}" y="{py-33:.1f}" text-anchor="middle" fill="#fca5a5" font-size="9" font-family="monospace">DAgger run10 spike</text>')

    # Normal band annotation
    parts.append(f'<text x="{pad_l+4}" y="{sy(5292)+12:.1f}" fill="#22c55e" font-size="9" font-family="monospace">normal ~127k/day</text>')

    # Axes
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1"/>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{w-pad_r}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1"/>')

    parts.append('</svg>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def render_dashboard():
    heatmap_svg = build_health_heatmap_svg()
    volume_svg = build_event_volume_svg()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Telemetry Aggregator</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
    .kpi-row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 18px;min-width:170px}}
    .kpi .label{{color:#94a3b8;font-size:10px;text-transform:uppercase;letter-spacing:.05em}}
    .kpi .value{{color:#38bdf8;font-size:26px;font-weight:bold;margin-top:4px}}
    .kpi .sub2{{color:#64748b;font-size:10px;margin-top:2px}}
    .kpi.alert .value{{color:#ef4444}}
    .kpi.good .value{{color:#22c55e}}
    .section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:18px;margin-bottom:20px}}
    .section h2{{color:#C74634;font-size:14px;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
    .chart-wrap{{overflow-x:auto}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:bold}}
    .badge.red{{background:#7f1d1d;color:#fca5a5}}
    .badge.green{{background:#14532d;color:#86efac}}
    .badge.amber{{background:#78350f;color:#fcd34d}}
    .svc-list{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}
    .svc-item{{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:6px 10px;font-size:11px}}
    .svc-item .name{{color:#94a3b8}}
    .svc-item .score{{color:#22c55e;font-weight:bold}}
    .svc-item.warn .score{{color:#f59e0b}}
    footer{{margin-top:20px;color:#334155;font-size:10px;text-align:center}}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Telemetry Aggregator</h1>
  <div class="sub">Port 8252 &nbsp;|&nbsp; Last refreshed: {now_str} &nbsp;|&nbsp; Aggregating 15 services</div>

  <div class="kpi-row">
    <div class="kpi good">
      <div class="label">Inference SLA</div>
      <div class="value">{INFERENCE_SLA}%</div>
      <div class="sub2">30-day rolling average</div>
    </div>
    <div class="kpi">
      <div class="label">Events Today</div>
      <div class="value">{TOTAL_EVENTS_TODAY:,}</div>
      <div class="sub2">normal baseline</div>
    </div>
    <div class="kpi alert">
      <div class="label">Day-4 Spike</div>
      <div class="value">{SPIKE_DAY4:,}</div>
      <div class="sub2">DAgger run10 launch</div>
    </div>
    <div class="kpi">
      <div class="label">Ingestion Rate</div>
      <div class="value">{INGESTION_RATE:,}/s</div>
      <div class="sub2">peak throughput</div>
    </div>
    <div class="kpi alert">
      <div class="label">Anomaly Events</div>
      <div class="value">{ANOMALY_COUNT}</div>
      <div class="sub2">last 7 days</div>
    </div>
    <div class="kpi good">
      <div class="label">Data Completeness</div>
      <div class="value">{DATA_COMPLETENESS}%</div>
      <div class="sub2">no data gaps detected</div>
    </div>
  </div>

  <div class="section">
    <h2>Service Health Matrix (24h &times; 15 Services)</h2>
    <div class="chart-wrap">{heatmap_svg}</div>
    <div class="svc-list" style="margin-top:12px">
      <div class="svc-item"><span class="name">inference</span> <span class="score">99.8%</span></div>
      <div class="svc-item warn"><span class="name">sdg_pipeline</span> <span class="score">2h deg</span></div>
      <div class="svc-item"><span class="name">fine_tune</span> <span class="score">99.1%</span></div>
      <div class="svc-item"><span class="name">eval</span> <span class="score">98.7%</span></div>
      <div class="svc-item"><span class="name">dagger</span> <span class="score">99.2%</span></div>
      <div class="svc-item"><span class="name">monitor</span> <span class="score">100%</span></div>
    </div>
  </div>

  <div class="section">
    <h2>Telemetry Event Volume — 7-Day Trend</h2>
    <div class="chart-wrap">{volume_svg}</div>
    <p style="color:#64748b;font-size:11px;margin-top:8px">
      Day 4 anomaly: <span class="badge red">341,027 events</span> — DAgger run10 triggered mass telemetry from concurrent training workers.
      All other days within normal band (~127k/day). sdg_pipeline degradation visible Thu hours 10–11.
    </p>
  </div>

  <footer>OCI Robot Cloud Telemetry Aggregator &nbsp;|&nbsp; port 8252 &nbsp;|&nbsp; cycle-48A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Telemetry Aggregator",
        description="Unified telemetry metrics stream for all OCI Robot Cloud services",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return render_dashboard()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "telemetry_aggregator", "port": 8252}

    @app.get("/metrics")
    async def metrics():
        return {
            "events_today": TOTAL_EVENTS_TODAY,
            "day4_spike": SPIKE_DAY4,
            "inference_sla_pct": INFERENCE_SLA,
            "anomaly_count": ANOMALY_COUNT,
            "data_completeness_pct": DATA_COMPLETENESS,
            "ingestion_rate_per_sec": INGESTION_RATE,
            "services_monitored": len(SERVICES),
            "services": SERVICES,
        }

    @app.get("/api/health-matrix")
    async def health_matrix_api():
        return {
            "hours": list(range(24)),
            "services": SERVICES,
            "matrix": HEALTH_MATRIX,
        }

    @app.get("/api/event-volume")
    async def event_volume_api():
        return {
            "interval": "hourly",
            "days": 7,
            "points": len(EVENT_VOLUMES),
            "volumes": EVENT_VOLUMES,
        }

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = render_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8252)
    else:
        PORT = 8252
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Telemetry Aggregator running on http://0.0.0.0:{PORT} (stdlib fallback)")
            httpd.serve_forever()
