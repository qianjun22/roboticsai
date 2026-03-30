"""Policy Deployment Monitor — OCI Robot Cloud (port 8669)

Monitors GR00T policy deployment slots: production, staging, canary, shadow.
Dark theme dashboard with SVG visualizations.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_deployment_slots() -> str:
    """4 rows: production/staging/canary/shadow with status badge + SR/latency/error metrics."""
    slots = [
        {
            "name": "production",
            "model": "groot_v1.9",
            "status": "LIVE",
            "status_color": "#C74634",
            "sr": "0.71",
            "latency": "231ms",
            "errors": "0.4%",
        },
        {
            "name": "staging",
            "model": "groot_v2.0",
            "status": "READY TO PROMOTE",
            "status_color": "#22c55e",
            "sr": "0.78",
            "latency": "218ms",
            "errors": "0.1%",
        },
        {
            "name": "canary",
            "model": "groot_v2.0-rc3",
            "status": "IN TEST",
            "status_color": "#38bdf8",
            "sr": "0.76",
            "latency": "224ms",
            "errors": "0.0%",
        },
        {
            "name": "shadow",
            "model": "groot_v2.1-dev",
            "status": "SHADOW",
            "status_color": "#94a3b8",
            "sr": "0.69",
            "latency": "245ms",
            "errors": "0.8%",
        },
    ]

    row_h = 54
    w = 560
    h = 30 + len(slots) * row_h + 10
    pad_l = 12

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#1e293b" rx="8"/>',
        f'<text x="{w//2}" y="22" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">Deployment Slot Status</text>',
    ]

    for i, slot in enumerate(slots):
        y = 30 + i * row_h
        # Row background (alternating)
        row_fill = "#243447" if i % 2 == 0 else "#1e293b"
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{w - pad_l*2}" height="{row_h - 4}" fill="{row_fill}" rx="5"/>')

        # Slot name
        parts.append(f'<text x="{pad_l + 10}" y="{y + 20}" fill="#e2e8f0" font-size="12" font-family="monospace" font-weight="bold">{slot["name"].upper()}</text>')
        parts.append(f'<text x="{pad_l + 10}" y="{y + 34}" fill="#64748b" font-size="9" font-family="monospace">{slot["model"]}</text>')

        # Status badge
        badge_x = 148
        badge_w = max(len(slot["status"]) * 7 + 14, 80)
        parts.append(f'<rect x="{badge_x}" y="{y + 8}" width="{badge_w}" height="20" fill="{slot["status_color"]}22" rx="10" stroke="{slot["status_color"]}" stroke-width="1"/>')
        parts.append(f'<text x="{badge_x + badge_w//2}" y="{y + 22}" fill="{slot["status_color"]}" font-size="8" font-family="monospace" text-anchor="middle" font-weight="bold">{slot["status"]}</text>')

        # Metrics
        metrics = [("SR", slot["sr"]), ("Latency", slot["latency"]), ("Errors", slot["errors"])]
        mx_start = 380
        for j, (lbl, val) in enumerate(metrics):
            mx = mx_start + j * 62
            parts.append(f'<text x="{mx}" y="{y + 18}" fill="#94a3b8" font-size="8" font-family="monospace" text-anchor="middle">{lbl}</text>')
            parts.append(f'<text x="{mx}" y="{y + 32}" fill="#e2e8f0" font-size="11" font-family="monospace" text-anchor="middle" font-weight="bold">{val}</text>')

    parts.append('</svg>')
    return ''.join(parts)


def svg_traffic_pie() -> str:
    """Pie chart: production 90% (Oracle red), canary 8% (blue), shadow 2% (slate)."""
    slices = [
        ("production", 0.90, "#C74634"),
        ("canary", 0.08, "#38bdf8"),
        ("shadow", 0.02, "#64748b"),
    ]
    w, h = 300, 240
    cx, cy, r = 130, 120, 95

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#1e293b" rx="8"/>',
        f'<text x="{w//2}" y="22" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">Traffic Distribution</text>',
    ]

    start = -math.pi / 2  # top
    for label, pct, color in slices:
        end = start + 2 * math.pi * pct
        x1 = cx + r * math.cos(start)
        y1 = cy + r * math.sin(start)
        x2 = cx + r * math.cos(end)
        y2 = cy + r * math.sin(end)
        large = 1 if pct > 0.5 else 0
        parts.append(
            f'<path d="M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z" '
            f'fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        )
        # Label at midpoint
        mid = start + math.pi * pct
        lx = cx + (r * 0.65) * math.cos(mid)
        ly = cy + (r * 0.65) * math.sin(mid)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#fff" font-size="9" font-family="monospace" text-anchor="middle" font-weight="bold">{int(pct*100)}%</text>'
        )
        start = end

    # Legend
    legend_x, legend_y = 240, 80
    for i, (label, pct, color) in enumerate(slices):
        ly = legend_y + i * 22
        parts.append(f'<rect x="{legend_x}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{legend_x + 16}" y="{ly + 10}" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')

    parts.append('</svg>')
    return ''.join(parts)


def svg_event_timeline() -> str:
    """30-day deployment event timeline with event dots: promote=green, rollback=red, config=yellow."""
    # Events: (day 1-30, type)
    events = [
        (2, "config_change"),
        (5, "promote"),
        (8, "config_change"),
        (11, "promote"),
        (14, "config_change"),
        (18, "promote"),
        (21, "config_change"),
        (25, "promote"),
        (28, "config_change"),
        (30, "promote"),
    ]
    event_colors = {"promote": "#22c55e", "rollback": "#C74634", "config_change": "#f59e0b"}

    w, h = 560, 140
    pad_l, pad_r = 30, 20
    pad_t, pad_b = 40, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    cy = pad_t + chart_h // 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#1e293b" rx="8"/>',
        f'<text x="{w//2}" y="22" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">Deployment Event Timeline (30 days · 0 rollbacks)</text>',
        # Baseline
        f'<line x1="{pad_l}" y1="{cy}" x2="{w - pad_r}" y2="{cy}" stroke="#334155" stroke-width="2"/>',
    ]

    # Day tick marks
    for day in range(1, 31, 5):
        x = pad_l + (day - 1) / 29 * chart_w
        parts.append(f'<line x1="{x:.1f}" y1="{cy - 4}" x2="{x:.1f}" y2="{cy + 4}" stroke="#475569" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{cy + 18}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">D{day}</text>')

    # Events
    for day, etype in events:
        x = pad_l + (day - 1) / 29 * chart_w
        color = event_colors[etype]
        # Vertical line
        parts.append(f'<line x1="{x:.1f}" y1="{cy - 20}" x2="{x:.1f}" y2="{cy}" stroke="{color}" stroke-width="1.5" stroke-dasharray="3,2"/>')
        # Dot
        parts.append(f'<circle cx="{x:.1f}" cy="{cy - 22}" r="5" fill="{color}"/>')

    # Legend
    legend_items = [("promote", "#22c55e"), ("config change", "#f59e0b"), ("rollback", "#C74634")]
    lx = pad_l
    for label, color in legend_items:
        parts.append(f'<circle cx="{lx + 6}" cy="{h - 12}" r="5" fill="{color}"/>')
        parts.append(f'<text x="{lx + 15}" y="{h - 8}" fill="#64748b" font-size="8" font-family="monospace">{label}</text>')
        lx += len(label) * 6 + 24

    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    slots_svg = svg_deployment_slots()
    pie_svg = svg_traffic_pie()
    timeline_svg = svg_event_timeline()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Policy Deployment Monitor — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.3rem; color: #f8fafc; }}
  header .badge {{ background: #C74634; color: #fff; font-size: 0.7rem; padding: 3px 10px; border-radius: 12px; }}
  header .port {{ color: #38bdf8; font-size: 0.85rem; }}
  .metrics {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 20px 32px; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px 20px; min-width: 160px; }}
  .metric-card .val {{ font-size: 1.5rem; font-weight: bold; color: #38bdf8; }}
  .metric-card .val.green {{ color: #34d399; }}
  .metric-card .val.red {{ color: #C74634; }}
  .metric-card .lbl {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
  .promote-banner {{ margin: 0 32px 16px; background: #14532d; border: 1px solid #22c55e; border-radius: 8px; padding: 12px 20px; color: #86efac; font-size: 0.85rem; }}
  .promote-banner strong {{ color: #22c55e; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 0 32px; }}
  .charts .wide {{ grid-column: 1 / -1; }}
  .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 12px; }}
  .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px; }}
  .chart-box svg {{ width: 100%; height: auto; display: block; }}
  footer {{ text-align: center; padding: 16px; color: #334155; font-size: 0.7rem; border-top: 1px solid #1e293b; margin-top: 24px; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Policy Deployment Monitor</h1>
    <span class="port">:8669 — Deployment Service</span>
  </div>
  <span class="badge">OCI Robot Cloud</span>
</header>

<div class="metrics">
  <div class="metric-card"><div class="val red">0.71</div><div class="lbl">Production SR (groot_v1.9)</div></div>
  <div class="metric-card"><div class="val green">0.78</div><div class="lbl">Staging SR (groot_v2.0)</div></div>
  <div class="metric-card"><div class="val green">+9.9%</div><div class="lbl">SR Improvement (staging vs prod)</div></div>
  <div class="metric-card"><div class="val">0</div><div class="lbl">Canary Anomalies (24hr)</div></div>
  <div class="metric-card"><div class="val green">0</div><div class="lbl">Rollbacks (30 days)</div></div>
</div>

<div class="promote-banner">
  <strong>Scheduled Promotion:</strong> groot_v2.0 staging → production on <strong>Apr 5, 2026</strong> &nbsp;|&nbsp; Canary 24hr clean — 0 anomalies detected
</div>

<div class="charts">
  <div class="chart-box wide">
    <h2>Deployment Slot Status</h2>
    {slots_svg}
  </div>
  <div class="chart-box">
    <h2>Traffic Distribution</h2>
    {pie_svg}
  </div>
  <div class="chart-box">
    <h2>Deployment Event Timeline (30 days)</h2>
    {timeline_svg}
  </div>
</div>

<footer>OCI Robot Cloud · Policy Deployment Monitor · Port 8669</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Policy Deployment Monitor",
        description="Monitors GR00T policy deployment slots across production, staging, canary, and shadow.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "policy_deployment_monitor", "port": 8669})

    @app.get("/slots")
    def slots():
        return JSONResponse({
            "production": {"model": "groot_v1.9", "sr": 0.71, "latency_ms": 231, "error_pct": 0.4, "status": "LIVE"},
            "staging": {"model": "groot_v2.0", "sr": 0.78, "latency_ms": 218, "error_pct": 0.1, "status": "READY_TO_PROMOTE"},
            "canary": {"model": "groot_v2.0-rc3", "sr": 0.76, "latency_ms": 224, "error_pct": 0.0, "status": "IN_TEST", "anomalies_24hr": 0},
            "shadow": {"model": "groot_v2.1-dev", "sr": 0.69, "latency_ms": 245, "error_pct": 0.8, "status": "SHADOW"},
            "promote_scheduled": "2026-04-05",
            "rollbacks_30d": 0,
        })

else:
    # Stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "policy_deployment_monitor", "port": 8669}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8669)
    else:
        print("FastAPI not found — starting stdlib HTTP server on port 8669")
        HTTPServer(("0.0.0.0", 8669), _Handler).serve_forever()
