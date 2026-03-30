"""deployment_gateway.py
OCI Robot Cloud — API gateway and deployment management dashboard.

Routes incoming inference requests to the correct model version (prod / canary /
staging), tracks per-route traffic, and serves a dark-theme HTML dashboard with
SVG charts.

Usage:
    pip install fastapi uvicorn
    python src/api/deployment_gateway.py

Port: 8128
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

PORT = 8128
SERVICE_NAME = "Deployment Gateway"

ROUTES: list[dict[str, Any]] = [
    {"path": "/v1/infer", "backend": "groot-prod-ashburn", "weight_pct": 90, "status": "ACTIVE", "region": "us-ashburn-1", "req_24h": 3_458},
    {"path": "/v1/infer-canary", "backend": "groot-canary-ashburn", "weight_pct": 10, "status": "ACTIVE", "region": "us-ashburn-1", "req_24h": 384},
    {"path": "/v1/infer-staging", "backend": "groot-staging-frankfurt", "weight_pct": 0, "status": "STANDBY", "region": "eu-frankfurt-1", "req_24h": 0},
    {"path": "/v2/infer", "backend": "dagger-run10-ashburn", "weight_pct": 0, "status": "PENDING", "region": "us-ashburn-1", "req_24h": 0},
    {"path": "/health", "backend": "health-aggregator", "weight_pct": None, "status": "ACTIVE", "region": "global", "req_24h": None},
]

STATS: dict[str, Any] = {
    "total_requests": 3_842, "successful": 3_801, "failed": 41,
    "success_rate_pct": 98.9, "avg_latency_ms": 228,
    "peak_hour": "14:00–15:00 UTC", "peak_rate_req_hr": 312, "window": "last 24h",
}

HOURLY_TRAFFIC: list[int] = [
    82, 71, 58, 45, 38, 42, 67, 134,
    198, 245, 278, 261, 290, 312, 287, 265,
    243, 218, 187, 165, 142, 128, 108, 83,
]


def _svg_traffic_line() -> str:
    W, H = 700, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 48, 20, 20, 36
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    max_val = max(HOURLY_TRAFFIC)
    n = len(HOURLY_TRAFFIC)

    def cx(i): return PAD_L + i * chart_w / (n - 1)
    def cy(v): return PAD_T + chart_h - (v / max_val) * chart_h

    pts = " ".join(f"{cx(i):.1f},{cy(v):.1f}" for i, v in enumerate(HOURLY_TRAFFIC))
    fill_pts = pts + f" {cx(n-1):.1f},{PAD_T+chart_h:.1f} {cx(0):.1f},{PAD_T+chart_h:.1f}"
    x_labels = "".join(f'<text x="{cx(i):.1f}" y="{PAD_T+chart_h+16}" fill="#94a3b8" font-size="11" text-anchor="middle">{i:02d}:00</text>' for i in range(0, n, 6))
    y_labels = "".join(f'<text x="{PAD_L-6}" y="{cy(v)+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text><line x1="{PAD_L}" y1="{cy(v):.1f}" x2="{PAD_L+chart_w}" y2="{cy(v):.1f}" stroke="#1e293b" stroke-width="1"/>' for v in [0, 150, 300])
    peak_idx = HOURLY_TRAFFIC.index(max_val)
    px_coord, py_coord = cx(peak_idx), cy(max_val)
    peak_dot = f'<circle cx="{px_coord:.1f}" cy="{py_coord:.1f}" r="5" fill="#C74634"/><text x="{px_coord:.1f}" y="{py_coord-9:.1f}" fill="#C74634" font-size="10" text-anchor="middle">{max_val}</text>'
    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <defs><linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.35"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0.03"/></linearGradient></defs>
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {y_labels}
  <polygon points="{fill_pts}" fill="url(#trafficGrad)"/>
  <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linejoin="round"/>
  {x_labels}
  {peak_dot}
  <text x="{PAD_L}" y="14" fill="#94a3b8" font-size="11">req/hr</text>
</svg>"""


def _svg_route_donut() -> str:
    W, H = 700, 200
    cx, cy = W // 2, H // 2
    R_outer, R_inner = 80, 50
    slices = [("groot-prod-ashburn", 90, "#38bdf8"), ("groot-canary-ashburn", 10, "#C74634")]

    def arc_path(start_deg, end_deg, ro, ri):
        def pt(deg, r):
            rad = math.radians(deg - 90)
            return cx + r * math.cos(rad), cy + r * math.sin(rad)
        x1o, y1o = pt(start_deg, ro)
        x2o, y2o = pt(end_deg, ro)
        x1i, y1i = pt(end_deg, ri)
        x2i, y2i = pt(start_deg, ri)
        large = 1 if (end_deg - start_deg) > 180 else 0
        return f"M {x1o:.2f} {y1o:.2f} A {ro} {ro} 0 {large} 1 {x2o:.2f} {y2o:.2f} L {x1i:.2f} {y1i:.2f} A {ri} {ri} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z"

    paths = ""
    angle = 0.0
    for label, pct, color in slices:
        sweep = pct * 360 / 100
        paths += f'<path d="{arc_path(angle, angle + sweep, R_outer, R_inner)}" fill="{color}"/>'
        angle += sweep

    legend = ""
    legend_x = cx + R_outer + 30
    for idx, (label, pct, color) in enumerate(slices):
        ly = cy - 12 + idx * 24
        legend += f'<rect x="{legend_x}" y="{ly}" width="14" height="14" fill="{color}" rx="3"/><text x="{legend_x+20}" y="{ly+11}" fill="#cbd5e1" font-size="13">{label} ({pct}%)</text>'

    center = f'<text x="{cx}" y="{cy-8}" fill="#f1f5f9" font-size="13" text-anchor="middle" font-weight="600">3,842</text><text x="{cx}" y="{cy+10}" fill="#94a3b8" font-size="11" text-anchor="middle">req / 24h</text>'
    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {paths}{center}{legend}
</svg>"""


def _status_badge(status: str) -> str:
    colors = {"ACTIVE": ("#22c55e", "#052e16"), "STANDBY": ("#f59e0b", "#1c1407"), "PENDING": ("#94a3b8", "#1e293b")}
    fg, bg = colors.get(status, ("#94a3b8", "#1e293b"))
    return f'<span style="background:{bg};color:{fg};border:1px solid {fg};padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;letter-spacing:.5px">{status}</span>'


def _build_html() -> str:
    stat_cards = [("Total Requests", f"{STATS['total_requests']:,}", "#38bdf8"), ("Success Rate", f"{STATS['success_rate_pct']}%", "#22c55e"), ("Avg Latency", f"{STATS['avg_latency_ms']} ms", "#f59e0b"), ("Peak Rate", f"{STATS['peak_rate_req_hr']} req/hr", "#C74634")]
    cards_html = "".join(f'<div style="background:#1e293b;border-radius:10px;padding:20px 24px;border-left:4px solid {accent};flex:1;min-width:160px"><div style="color:#94a3b8;font-size:13px;margin-bottom:6px">{title}</div><div style="color:{accent};font-size:28px;font-weight:700">{value}</div></div>' for title, value, accent in stat_cards)
    rows_html = "".join(f'<tr style="border-bottom:1px solid #334155"><td style="padding:12px 16px;color:#38bdf8;font-family:monospace">{r["path"]}</td><td style="padding:12px 16px;color:#e2e8f0">{r["backend"]}</td><td style="padding:12px 16px;color:#94a3b8;text-align:center">{f"{r[\"weight_pct\"]}%" if r["weight_pct"] is not None else "—"}</td><td style="padding:12px 16px;text-align:center">{_status_badge(r["status"])}</td><td style="padding:12px 16px;color:#94a3b8;text-align:right">{f"{r[\"req_24h\"]:,}" if r["req_24h"] is not None else "—"}</td><td style="padding:12px 16px;color:#64748b;font-size:12px">{r["region"]}</td></tr>' for r in ROUTES)
    traffic_svg = _svg_traffic_line()
    donut_svg = _svg_route_donut()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — {SERVICE_NAME}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
    table{{border-collapse:collapse;width:100%}}
    th{{background:#0f172a;color:#64748b;font-size:12px;letter-spacing:.8px;text-transform:uppercase;padding:10px 16px;text-align:left}}
    tr:hover td{{background:#263348}}
    .section{{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:24px}}
    .section-title{{color:#f1f5f9;font-size:16px;font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .dot{{width:8px;height:8px;border-radius:50%;background:#C74634;display:inline-block}}
  </style>
</head>
<body>
<div style="max-width:980px;margin:0 auto;padding:32px 20px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">
    <div style="display:flex;align-items:center;gap:12px">
      <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px">G</div>
      <div>
        <div style="font-size:22px;font-weight:700;color:#f1f5f9">OCI Robot Cloud <span style="color:#C74634">{SERVICE_NAME}</span></div>
        <div style="color:#64748b;font-size:13px;margin-top:2px">GR00T N1.6-3B · A100 · Ashburn / Frankfurt · Port {PORT}</div>
      </div>
    </div>
    <div style="text-align:right"><div style="color:#22c55e;font-size:13px;font-weight:600">● LIVE</div><div style="color:#64748b;font-size:12px;margin-top:2px">{now_utc}</div></div>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">{cards_html}</div>
  <div class="section"><div class="section-title"><span class="dot"></span>Route Configuration</div><div style="overflow-x:auto"><table><thead><tr><th>Path</th><th>Backend</th><th style="text-align:center">Weight</th><th style="text-align:center">Status</th><th style="text-align:right">24h Requests</th><th>Region</th></tr></thead><tbody>{rows_html}</tbody></table></div></div>
  <div class="section"><div class="section-title"><span class="dot"></span>24-Hour Traffic (req/hr)</div><div style="overflow-x:auto">{traffic_svg}</div><div style="color:#64748b;font-size:12px;margin-top:8px;text-align:right">Peak: {STATS['peak_hour']} — {STATS['peak_rate_req_hr']} req/hr</div></div>
  <div class="section"><div class="section-title"><span class="dot"></span>Route Traffic Distribution</div><div style="overflow-x:auto">{donut_svg}</div></div>
  <div style="text-align:center;color:#334155;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b">Oracle Confidential | OCI Robot Cloud {SERVICE_NAME} | Port {PORT}</div>
</div>
</body>
</html>"""


app = FastAPI(title=f"OCI Robot Cloud — {SERVICE_NAME}", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_build_html())


@app.get("/routes")
def get_routes() -> JSONResponse:
    return JSONResponse(content={"routes": ROUTES, "total": len(ROUTES)})


@app.get("/stats")
def get_stats() -> JSONResponse:
    return JSONResponse(content=STATS)


@app.get("/traffic")
def get_traffic() -> JSONResponse:
    hourly = [{"hour_utc": i, "requests": v} for i, v in enumerate(HOURLY_TRAFFIC)]
    return JSONResponse(content={"hourly": hourly, "peak_hour": HOURLY_TRAFFIC.index(max(HOURLY_TRAFFIC)), "peak_value": max(HOURLY_TRAFFIC), "total": sum(HOURLY_TRAFFIC)})


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "service": SERVICE_NAME, "port": PORT, "active_routes": sum(1 for r in ROUTES if r["status"] == "ACTIVE"), "timestamp": datetime.now(timezone.utc).isoformat()})


def main() -> None:
    uvicorn.run("deployment_gateway:app", host="0.0.0.0", port=PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()
