#!/usr/bin/env python3
"""
Safety Envelope Monitor — port 8221
Monitors robot workspace safety boundaries and compliance.
Cycle-40A | OCI Robot Cloud
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

random.seed(42)

# ---------------------------------------------------------------------------
# Mock data — safety compliance metrics
# ---------------------------------------------------------------------------

WORKSPACE_CONFIG = {
    "arm_reach_mm": 850,
    "safe_zone_mm": 650,          # green: 0-650mm
    "caution_zone_mm": 790,       # yellow: 650-790mm
    "boundary_mm": 790,           # workspace boundary (red beyond)
    "episodes_total": 1000,
    "episodes_yellow_pct": 4.2,   # episodes reaching yellow zone
    "episodes_red_pct": 0.8,      # episodes reaching red zone
    "e_stop_events_march": 3,
    "compliance_rate_pct": 95.0,
}

# Generate 100 episode endpoint scatter (polar -> cartesian, clamp to arm reach)
random.seed(7)
_endpoints = []
for _ in range(1000):
    angle = random.uniform(0, 2 * math.pi)
    r_norm = random.betavariate(2.5, 1.2)  # skew toward center
    r_mm = r_norm * WORKSPACE_CONFIG["arm_reach_mm"]
    x = r_mm * math.cos(angle)
    y = r_mm * math.sin(angle)
    _endpoints.append((x, y, r_mm))

# 30-day daily violation counts
random.seed(13)
DAILY_VIOLATIONS = []
base_date = datetime(2026, 3, 1)
for i in range(30):
    d = base_date + timedelta(days=i)
    # mild upward trend, noisy
    count = max(0, int(random.gauss(8 + i * 0.15, 3)))
    DAILily_v = {"date": d.strftime("%m/%d"), "count": count, "day": i}
    DAILY_VIOLATIONS.append(DAILily_v)

# 3 incident markers (e-stop days)
INCIDENT_DAYS = [4, 11, 22]  # day indices

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_workspace_svg() -> str:
    """2D top-down workspace map with safety zones and episode endpoint scatter."""
    W, H = 680, 480
    cx, cy = W // 2, H // 2 + 20
    scale = 0.28  # px per mm

    reach_r = int(WORKSPACE_CONFIG["arm_reach_mm"] * scale)
    caution_r = int(WORKSPACE_CONFIG["caution_zone_mm"] * scale)
    safe_r = int(WORKSPACE_CONFIG["safe_zone_mm"] * scale)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Franka Workspace — Safety Zone Map (Top-Down View)</text>')

    # Safety zones (outermost first for layering)
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{reach_r}" fill="#4a1a14" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.5"/>')
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{caution_r}" fill="#3d3000" stroke="#fbbf24" stroke-width="1.5" opacity="0.6"/>')
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{safe_r}" fill="#0f2d1f" stroke="#34d399" stroke-width="1.5" opacity="0.7"/>')

    # Episode endpoint scatter
    for (x_mm, y_mm, r_mm) in _endpoints:
        px_ = cx + x_mm * scale
        py_ = cy - y_mm * scale  # flip y
        boundary = WORKSPACE_CONFIG["boundary_mm"]
        caution = WORKSPACE_CONFIG["caution_zone_mm"]
        safe = WORKSPACE_CONFIG["safe_zone_mm"]
        if r_mm > boundary:
            col, op, r_pt = "#C74634", "0.9", 3
        elif r_mm > caution:
            col, op, r_pt = "#C74634", "0.7", 2
        elif r_mm > safe:
            col, op, r_pt = "#fbbf24", "0.7", 2
        else:
            col, op, r_pt = "#34d399", "0.5", 1
        lines.append(f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="{r_pt}" fill="{col}" opacity="{op}"/>')

    # Arm base
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="#38bdf8" stroke="#0f172a" stroke-width="2"/>')
    lines.append(f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="monospace">Franka Base</text>')

    # Zone labels
    lines.append(f'<text x="{cx + safe_r - 28}" y="{cy - 6}" fill="#34d399" font-size="9" font-family="monospace">Safe</text>')
    lines.append(f'<text x="{cx + caution_r - 36}" y="{cy - 6}" fill="#fbbf24" font-size="9" font-family="monospace">Caution</text>')
    lines.append(f'<text x="{cx + reach_r - 38}" y="{cy - 6}" fill="#C74634" font-size="9" font-family="monospace">Boundary</text>')

    # Dimension annotations
    lines.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + safe_r}" y2="{cy}" stroke="#34d399" stroke-width="0.8" stroke-dasharray="3,2"/>')
    lines.append(f'<text x="{cx + safe_r//2}" y="{cy + 12}" text-anchor="middle" fill="#34d399" font-size="8" font-family="monospace">650mm</text>')
    lines.append(f'<line x1="{cx + safe_r}" y1="{cy}" x2="{cx + caution_r}" y2="{cy}" stroke="#fbbf24" stroke-width="0.8" stroke-dasharray="3,2"/>')
    lines.append(f'<text x="{cx + safe_r + (caution_r - safe_r)//2}" y="{cy + 12}" text-anchor="middle" fill="#fbbf24" font-size="8" font-family="monospace">790mm</text>')

    # Legend
    lx = 20
    for i, (col, label) in enumerate([("#34d399", "Safe zone (95.0%)"), ("#fbbf24", "Caution zone (4.2%)"), ("#C74634", "Red zone (0.8%)")]):
        ly2 = H - 50 + i * 16
        lines.append(f'<circle cx="{lx + 6}" cy="{ly2}" r="4" fill="{col}"/>')
        lines.append(f'<text x="{lx + 16}" y="{ly2 + 4}" fill="#cbd5e1" font-size="9" font-family="monospace">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def build_timeseries_svg() -> str:
    """30-day violation trend line chart with incident markers."""
    W, H = 680, 280
    pad_l, pad_r, pad_t, pad_b = 55, 30, 36, 55
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    counts = [v["count"] for v in DAILY_VIOLATIONS]
    max_count = max(counts) + 2
    threshold = 14  # violation threshold line

    def px(day_idx):
        return pad_l + (day_idx / (len(DAILY_VIOLATIONS) - 1)) * chart_w

    def py(count):
        return pad_t + chart_h - (count / max_count) * chart_h

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Daily Safety Zone Violations — March 2026</text>')

    # Grid
    for v in [5, 10, 15, 20]:
        yy = py(v)
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l + chart_w}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{v}</text>')

    # Threshold line
    ty = py(threshold)
    lines.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + chart_w}" y2="{ty:.1f}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="8,4"/>')
    lines.append(f'<text x="{pad_l + chart_w + 4}" y="{ty + 4:.1f}" fill="#C74634" font-size="9" font-family="monospace">threshold</text>')

    # Filled area under line
    pts_area = f"{pad_l},{pad_t + chart_h} "
    pts_area += " ".join(f"{px(i):.1f},{py(c):.1f}" for i, c in enumerate(counts))
    pts_area += f" {pad_l + chart_w},{pad_t + chart_h}"
    lines.append(f'<polygon points="{pts_area}" fill="#38bdf8" opacity="0.08"/>')

    # Line
    pts_line = " ".join(f"{px(i):.1f},{py(c):.1f}" for i, c in enumerate(counts))
    lines.append(f'<polyline points="{pts_line}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # Data points
    for i, c in enumerate(counts):
        col = "#C74634" if c > threshold else "#38bdf8"
        lines.append(f'<circle cx="{px(i):.1f}" cy="{py(c):.1f}" r="2.5" fill="{col}"/>')

    # Incident markers (e-stop)
    for day_idx in INCIDENT_DAYS:
        ix = px(day_idx)
        iy = py(counts[day_idx])
        lines.append(f'<polygon points="{ix:.1f},{iy - 14} {ix - 6:.1f},{iy - 4} {ix + 6:.1f},{iy - 4}" fill="#C74634" opacity="0.9"/>')
        lines.append(f'<text x="{ix:.1f}" y="{iy - 17:.1f}" text-anchor="middle" fill="#C74634" font-size="8" font-family="monospace">E-STOP</text>')

    # X-axis labels (every 5 days)
    for i in range(0, 30, 5):
        xx = px(i)
        lines.append(f'<text x="{xx:.1f}" y="{pad_t + chart_h + 16}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{DAILY_VIOLATIONS[i]["date"]}</text>')

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')

    # Axis label
    lines.append(f'<text x="14" y="{pad_t + chart_h//2}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90 14 {pad_t + chart_h//2})">Violations/day</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    ws_svg = build_workspace_svg()
    ts_svg = build_timeseries_svg()
    cfg = WORKSPACE_CONFIG

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Safety Envelope Monitor | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-label {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ color: #38bdf8; font-size: 1.6rem; font-weight: bold; margin: 4px 0; }}
    .card-value.warn {{ color: #fbbf24; }}
    .card-value.danger {{ color: #C74634; }}
    .card-sub {{ color: #64748b; font-size: 0.75rem; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 16px; }}
    svg {{ max-width: 100%; height: auto; }}
    .rec-box {{ background: #0f2d1f; border: 1px solid #34d399; border-radius: 6px; padding: 12px 16px; margin-top: 16px; }}
    .rec-box h3 {{ color: #34d399; font-size: 0.85rem; margin-bottom: 8px; }}
    .rec-box ul {{ color: #94a3b8; font-size: 0.8rem; padding-left: 18px; line-height: 1.8; }}
    .ts {{ color: #475569; font-size: 0.72rem; margin-top: 8px; }}
  </style>
</head>
<body>
  <h1>Safety Envelope Monitor</h1>
  <p class="subtitle">Robot workspace safety boundary compliance &mdash; OCI Robot Cloud &bull; Port 8221</p>

  <div class="grid">
    <div class="card">
      <div class="card-label">Compliance Rate</div>
      <div class="card-value">{cfg['compliance_rate_pct']}%</div>
      <div class="card-sub">{cfg['episodes_total']} episodes evaluated</div>
    </div>
    <div class="card">
      <div class="card-label">Caution Zone Hits</div>
      <div class="card-value warn">{cfg['episodes_yellow_pct']}%</div>
      <div class="card-sub">650–790mm radius</div>
    </div>
    <div class="card">
      <div class="card-label">Red Zone Hits</div>
      <div class="card-value danger">{cfg['episodes_red_pct']}%</div>
      <div class="card-sub">&gt;790mm — boundary breach</div>
    </div>
    <div class="card">
      <div class="card-label">E-Stop Events (Mar)</div>
      <div class="card-value danger">{cfg['e_stop_events_march']}</div>
      <div class="card-sub">Days 5, 12, 23</div>
    </div>
  </div>

  <div class="section">
    <h2>Workspace Map — Episode Endpoint Distribution</h2>
    {ws_svg}
  </div>

  <div class="section">
    <h2>Daily Safety Violations — 30-Day Trend</h2>
    {ts_svg}

    <div class="rec-box">
      <h3>Recommended Actions</h3>
      <ul>
        <li>Reduce workspace boundary from 790mm to 750mm to lower red zone hits from 0.8% to &lt;0.2%</li>
        <li>Add joint-space velocity damping at 85% of reach limit to prevent caution zone overshoot</li>
        <li>Review 3 e-stop events: all occurred during pick-and-place at max horizontal extension</li>
        <li>Re-run IK planner with new boundary config — estimated 2h fine-tune required</li>
      </ul>
    </div>
  </div>

  <p class="ts">Updated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} UTC &bull; OCI Robot Cloud cycle-40A</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Safety Envelope Monitor",
        description="Robot workspace safety boundary monitoring and compliance tracking",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/config")
    async def get_config():
        return WORKSPACE_CONFIG

    @app.get("/api/violations")
    async def get_violations():
        return {"daily": DAILY_VIOLATIONS, "incidents": INCIDENT_DAYS, "threshold": 14}

    @app.get("/api/compliance")
    async def get_compliance():
        return {
            "compliance_rate_pct": WORKSPACE_CONFIG["compliance_rate_pct"],
            "yellow_zone_pct": WORKSPACE_CONFIG["episodes_yellow_pct"],
            "red_zone_pct": WORKSPACE_CONFIG["episodes_red_pct"],
            "e_stop_count": WORKSPACE_CONFIG["e_stop_events_march"],
            "recommended_boundary_mm": 750,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "safety_envelope_monitor", "port": 8221}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8221)
    else:
        server = HTTPServer(("0.0.0.0", 8221), Handler)
        print("[safety_envelope_monitor] stdlib fallback running on :8221")
        server.serve_forever()
