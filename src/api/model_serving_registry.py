"""Model Serving Registry — FastAPI service on port 8300.

Registry for all deployed model endpoints with health, version, and routing metadata.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ENDPOINTS = [
    {"id": "ep-001", "name": "dagger_run9_v2.2", "port": 8001, "version": "v2.2", "status": "ACTIVE",   "role": "PRODUCTION", "traffic_pct": 71, "latency_p50": 227, "sr": 0.87, "healthy": True},
    {"id": "ep-002", "name": "groot_v2",         "port": 8002, "version": "v2.0", "status": "ACTIVE",   "role": "CANARY",     "traffic_pct": 12, "latency_p50": 243, "sr": 0.89, "healthy": True},
    {"id": "ep-003", "name": "groot_v3",         "port": 8003, "version": "v3.0", "status": "STAGING",  "role": "EVAL",       "traffic_pct": 10, "latency_p50": 259, "sr": 0.91, "healthy": True},
    {"id": "ep-004", "name": "ashburn_shadow",   "port": 8004, "version": "v2.2", "status": "ACTIVE",   "role": "SHADOW",     "traffic_pct":  7, "latency_p50": 231, "sr": 0.87, "healthy": True},
    {"id": "ep-005", "name": "bc_baseline_v1",   "port": 8010, "version": "v1.0", "status": "ACTIVE",   "role": "STAGING",    "traffic_pct":  0, "latency_p50": 188, "sr": 0.72, "healthy": True},
    {"id": "ep-006", "name": "dagger_run5_v1.8", "port": 8011, "version": "v1.8", "status": "ACTIVE",   "role": "STAGING",    "traffic_pct":  0, "latency_p50": 214, "sr": 0.81, "healthy": True},
    {"id": "ep-007", "name": "groot_v2_asha",    "port": 8012, "version": "v2.0", "status": "STAGING",  "role": "STAGING",    "traffic_pct":  0, "latency_p50": 247, "sr": 0.88, "healthy": True},
    {"id": "ep-008", "name": "openvla_v1",       "port": 8080, "version": "v1.0", "status": "DEPRECATED", "role": "DEPRECATED", "traffic_pct":  0, "latency_p50": 412, "sr": 0.51, "healthy": False},
]

active_count   = sum(1 for e in ENDPOINTS if e["status"] != "DEPRECATED")
production_pct = next(e["traffic_pct"] for e in ENDPOINTS if e["role"] == "PRODUCTION")
prod_lat       = next(e["latency_p50"] for e in ENDPOINTS if e["role"] == "PRODUCTION")
stage_lat      = int(sum(e["latency_p50"] for e in ENDPOINTS if e["role"] == "STAGING" and e["traffic_pct"] == 0 and e["status"] != "DEPRECATED") / max(1, sum(1 for e in ENDPOINTS if e["role"] == "STAGING" and e["traffic_pct"] == 0 and e["status"] != "DEPRECATED")))
deprecated_cnt = sum(1 for e in ENDPOINTS if e["status"] == "DEPRECATED")

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _status_color(status: str) -> str:
    return {"ACTIVE": "#22c55e", "STAGING": "#f59e0b", "DEPRECATED": "#ef4444"}.get(status, "#94a3b8")

def _role_row_bg(role: str) -> str:
    return {
        "PRODUCTION": "#1e3a2e", "CANARY": "#1e2e3a", "EVAL": "#2a2a1a",
        "SHADOW": "#1e1a2e", "STAGING": "#1a1a2a", "DEPRECATED": "#2a1a1a",
    }.get(role, "#1e293b")

def svg_endpoint_table() -> str:
    rows = ""
    for i, ep in enumerate(ENDPOINTS):
        y = 60 + i * 38
        bg = _role_row_bg(ep["role"])
        sc = _status_color(ep["status"])
        health_sym = "●" if ep["healthy"] else "○"
        health_col = "#22c55e" if ep["healthy"] else "#ef4444"
        rows += f"""
  <rect x="10" y="{y}" width="980" height="34" fill="{bg}" rx="3"/>
  <text x="30"  y="{y+22}" fill="#e2e8f0" font-size="12" font-family="monospace">{ep['name'][:22]:<22}</text>
  <text x="240" y="{y+22}" fill="#94a3b8" font-size="12" font-family="monospace">{ep['version']}</text>
  <text x="310" y="{y+22}" fill="#94a3b8" font-size="12" font-family="monospace">{ep['port']}</text>
  <text x="380" y="{y+22}" fill="#38bdf8" font-size="12" font-family="monospace">{ep['sr']:.2f}</text>
  <text x="450" y="{y+22}" fill="#f8fafc" font-size="12" font-family="monospace">{ep['latency_p50']} ms</text>
  <rect x="530" y="{y+8}" width="90" height="18" fill="{sc}22" rx="9"/>
  <text x="575" y="{y+21}" fill="{sc}" font-size="11" font-family="monospace" text-anchor="middle">{ep['status']}</text>
  <text x="660" y="{y+22}" fill="#cbd5e1" font-size="12" font-family="monospace">{ep['role']}</text>
  <text x="800" y="{y+22}" fill="#38bdf8" font-size="12" font-family="monospace">{ep['traffic_pct']}%</text>
  <text x="900" y="{y+22}" fill="{health_col}" font-size="14" font-family="monospace">{health_sym}</text>
"""

    header_bg = "#0f172a"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{60 + len(ENDPOINTS)*38 + 20}" style="background:#0f172a;border-radius:8px">
  <!-- header -->
  <rect x="10" y="10" width="980" height="36" fill="#1e293b" rx="4"/>
  <text x="30"  y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">ENDPOINT NAME</text>
  <text x="240" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">VERSION</text>
  <text x="310" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">PORT</text>
  <text x="380" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">SR</text>
  <text x="450" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">LAT P50</text>
  <text x="530" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">STATUS</text>
  <text x="660" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">ROLE</text>
  <text x="800" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">TRAFFIC</text>
  <text x="900" y="33" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">HEALTH</text>
  {rows}
</svg>"""


def svg_traffic_donut() -> str:
    # segments: PRODUCTION 71%, CANARY 12%, EVAL 10%, SHADOW 7%
    segments = [
        {"label": "PRODUCTION",   "model": "dagger_run9 v2.2", "pct": 71, "color": "#C74634"},
        {"label": "CANARY",       "model": "groot v2.0",       "pct": 12, "color": "#38bdf8"},
        {"label": "EVAL",         "model": "groot v3.0",       "pct": 10, "color": "#f59e0b"},
        {"label": "SHADOW",       "model": "ashburn v2.2",     "pct":  7, "color": "#a78bfa"},
    ]
    cx, cy, ro, ri = 250, 220, 150, 80
    total = sum(s["pct"] for s in segments)
    paths = ""
    legend = ""
    angle = -math.pi / 2
    for i, seg in enumerate(segments):
        sweep = 2 * math.pi * seg["pct"] / total
        x1o = cx + ro * math.cos(angle)
        y1o = cy + ro * math.sin(angle)
        x1i = cx + ri * math.cos(angle)
        y1i = cy + ri * math.sin(angle)
        angle += sweep
        x2o = cx + ro * math.cos(angle)
        y2o = cy + ro * math.sin(angle)
        x2i = cx + ri * math.cos(angle)
        y2i = cy + ri * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        mid_a = angle - sweep / 2
        lx = cx + (ro + 30) * math.cos(mid_a)
        ly = cy + (ro + 30) * math.sin(mid_a)
        path = f"M {x1o:.1f} {y1o:.1f} A {ro} {ro} 0 {large} 1 {x2o:.1f} {y2o:.1f} L {x2i:.1f} {y2i:.1f} A {ri} {ri} 0 {large} 0 {x1i:.1f} {y1i:.1f} Z"
        paths += f'  <path d="{path}" fill="{seg["color"]}" stroke="#0f172a" stroke-width="2"/>\n'
        paths += f'  <text x="{lx:.0f}" y="{ly:.0f}" fill="#f8fafc" font-size="11" font-family="monospace" text-anchor="middle">{seg["pct"]}%</text>\n'
        # legend
        ly2 = 80 + i * 36
        legend += f'  <rect x="540" y="{ly2}" width="14" height="14" fill="{seg["color"]}" rx="2"/>\n'
        legend += f'  <text x="562" y="{ly2+11}" fill="#e2e8f0" font-size="12" font-family="monospace">{seg["label"]}</text>\n'
        legend += f'  <text x="562" y="{ly2+25}" fill="#94a3b8" font-size="10" font-family="monospace">{seg["model"]} · {seg["pct"]}%</text>\n'

    center_label = f'  <text x="{cx}" y="{cy-10}" fill="#f8fafc" font-size="22" font-family="monospace" text-anchor="middle" font-weight="bold">100%</text>\n'
    center_label += f'  <text x="{cx}" y="{cy+14}" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">TRAFFIC</text>\n'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="760" height="440" style="background:#0f172a;border-radius:8px">
  <text x="380" y="30" fill="#f8fafc" font-size="15" font-family="monospace" text-anchor="middle" font-weight="bold">Traffic Distribution by Endpoint Role</text>
{paths}{center_label}{legend}</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    table_svg   = svg_endpoint_table()
    donut_svg   = svg_traffic_donut()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Model Serving Registry — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#f8fafc;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .subtitle{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
    .kpi-row{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 24px;min-width:180px}}
    .kpi .val{{font-size:28px;font-weight:bold;color:#38bdf8}}
    .kpi .lbl{{font-size:11px;color:#94a3b8;margin-top:4px}}
    .section{{margin-bottom:32px}}
    .section h2{{color:#38bdf8;font-size:14px;margin-bottom:12px;text-transform:uppercase;letter-spacing:.08em}}
    .svg-wrap{{overflow-x:auto;background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px}}
    .charts-row{{display:flex;gap:24px;flex-wrap:wrap}}
    footer{{color:#475569;font-size:11px;margin-top:32px;text-align:center}}
  </style>
</head>
<body>
  <h1>Model Serving Registry</h1>
  <div class="subtitle">OCI Robot Cloud · Port 8300 · {ts}</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val">{active_count}</div><div class="lbl">Active Endpoints</div></div>
    <div class="kpi"><div class="val">{production_pct}%</div><div class="lbl">Production Traffic</div></div>
    <div class="kpi"><div class="val">{prod_lat} ms</div><div class="lbl">Production Latency P50</div></div>
    <div class="kpi"><div class="val">{stage_lat} ms</div><div class="lbl">Staging Latency P50</div></div>
    <div class="kpi"><div class="val">{deprecated_cnt}</div><div class="lbl">Deprecated (pending cleanup)</div></div>
  </div>

  <div class="section">
    <h2>Endpoint Registry</h2>
    <div class="svg-wrap">{table_svg}</div>
  </div>

  <div class="section">
    <h2>Traffic Distribution</h2>
    <div class="svg-wrap">{donut_svg}</div>
  </div>

  <footer>OCI Robot Cloud · Model Serving Registry · cycle-60A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(title="Model Serving Registry", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "model_serving_registry", "port": 8300}

    @app.get("/api/endpoints")
    def api_endpoints():
        return {"endpoints": ENDPOINTS, "active_count": active_count, "production_pct": production_pct}

    @app.get("/api/metrics")
    def api_metrics():
        return {
            "active_endpoints": active_count,
            "production_traffic_pct": production_pct,
            "prod_latency_p50_ms": prod_lat,
            "staging_latency_p50_ms": stage_lat,
            "deprecated_count": deprecated_cnt,
        }

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8300}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):  # suppress default logging
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8300)
    else:
        print("[model_serving_registry] FastAPI not available — using stdlib http.server on port 8300")
        server = HTTPServer(("0.0.0.0", 8300), _Handler)
        server.serve_forever()
