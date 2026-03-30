"""Unified Observability Hub — aggregates metrics from all OCI Robot Cloud services.
Port 8180
"""
import math
import json
from datetime import datetime, timezone

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Static service data
# ---------------------------------------------------------------------------
SERVICES = [
    # inference
    {"name": "groot_inference",  "port": 8001, "category": "inference", "status": "HEALTHY",  "metric": "226ms"},
    {"name": "data_collection",  "port": 8003, "category": "inference", "status": "HEALTHY",  "metric": "98.7%"},
    {"name": "pipeline_orch",    "port": 8004, "category": "inference", "status": "HEALTHY",  "metric": "3 runs"},
    # training
    {"name": "finetune_server",  "port": 8002, "category": "training",  "status": "HEALTHY",  "metric": "1420 steps"},
    {"name": "training_monitor", "port": 8132, "category": "training",  "status": "HEALTHY",  "metric": "3 runs"},
    {"name": "curriculum",       "port": 8123, "category": "training",  "status": "HEALTHY",  "metric": "stage3"},
    # eval
    {"name": "sim_eval",         "port": 8121, "category": "eval",      "status": "HEALTHY",  "metric": "78% SR"},
    {"name": "policy_bench",     "port": 8130, "category": "eval",      "status": "HEALTHY",  "metric": "82% SR"},
    {"name": "robustness",       "port": 8143, "category": "eval",      "status": "HEALTHY",  "metric": "67/100"},
    # infra
    {"name": "fleet_health",     "port": 8122, "category": "infra",     "status": "DEGRADED", "metric": "98.7%"},
    {"name": "gpu_tracker",      "port": 8125, "category": "infra",     "status": "DEGRADED", "metric": "ashburn-shadow"},
    {"name": "autoscaler",       "port": 8135, "category": "infra",     "status": "HEALTHY",  "metric": "58.8%"},
    # api
    {"name": "model_registry",   "port": 8117, "category": "api",       "status": "HEALTHY",  "metric": "6 models"},
    {"name": "billing",          "port": 8147, "category": "api",       "status": "HEALTHY",  "metric": "$3182"},
    {"name": "partner",          "port": 8136, "category": "api",       "status": "HEALTHY",  "metric": "5 partners"},
]

ALERTS = [
    {"id": "ALT-001", "service": "gpu_tracker",  "severity": "CRITICAL", "message": "ashburn-shadow-1 GPU unreachable",    "ts": "2026-03-30T09:14:00Z"},
    {"id": "ALT-002", "service": "fleet_health", "severity": "WARNING",  "message": "fleet_sync LAG >500ms on 2 nodes",   "ts": "2026-03-30T11:42:00Z"},
    {"id": "ALT-003", "service": "finetune_server", "severity": "WARNING", "message": "dagger_step p99 latency spike 340ms", "ts": "2026-03-30T14:05:00Z"},
]

METRICS_24H = {
    "total_api_calls":        47821,
    "training_steps_completed": 1420,
    "eval_episodes":          40,
    "active_alerts":          3,
}


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------
def _status_color(status: str) -> tuple:
    """Returns (fill, text) hex colors for a status."""
    if status == "HEALTHY":
        return "#14532d", "#86efac"   # dark-green fill, light-green text
    if status == "DEGRADED":
        return "#713f12", "#fde68a"   # amber fill, amber text
    return "#7f1d1d", "#fca5a5"       # red fill, red text


def build_services_grid_svg(width: int = 680, height: int = 280) -> str:
    """3-column x 5-row grid of service tiles."""
    cols, rows = 3, 5
    pad = 8
    tile_w = (width - pad * (cols + 1)) // cols
    tile_h = (height - pad * (rows + 1)) // rows

    rects = []
    for i, svc in enumerate(SERVICES):
        col = i % cols
        row = i // cols
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + pad)
        fill, txt_col = _status_color(svc["status"])

        rects.append(
            f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" '
            f'rx="6" fill="{fill}" stroke="#1e293b" stroke-width="1"/>'
        )
        # service name
        rects.append(
            f'<text x="{x + tile_w // 2}" y="{y + 18}" '
            f'font-family="monospace" font-size="9" fill="{txt_col}" '
            f'text-anchor="middle" font-weight="bold">{svc["name"]}</text>'
        )
        # port
        rects.append(
            f'<text x="{x + tile_w // 2}" y="{y + 31}" '
            f'font-family="monospace" font-size="8" fill="#94a3b8" '
            f'text-anchor="middle">:{svc["port"]}</text>'
        )
        # metric
        rects.append(
            f'<text x="{x + tile_w // 2}" y="{y + 44}" '
            f'font-family="monospace" font-size="9" fill="#38bdf8" '
            f'text-anchor="middle">{svc["metric"]}</text>'
        )

    body = "\n".join(rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        f'{body}</svg>'
    )


def build_metric_timeline_svg(width: int = 680, height: int = 160) -> str:
    """24-hour sparklines for 3 key metrics (normalized 0-1)."""
    import math
    hours = list(range(25))  # 0..24

    # Synthetic but plausible 24h data
    def api_calls(h):
        base = 1200 + 800 * math.sin(math.pi * h / 12)
        return max(0, base + 200 * math.sin(h * 1.3))

    def train_steps(h):
        return 40 + 20 * (1 - math.exp(-h / 8)) + 10 * math.sin(h * 0.8)

    def gpu_util(h):
        return 0.55 + 0.25 * math.sin(math.pi * h / 10) + 0.05 * math.cos(h * 2)

    series = [
        ("API calls/h",    "#38bdf8", [api_calls(h) for h in hours]),
        ("Train steps/h",  "#C74634", [train_steps(h) for h in hours]),
        ("GPU util",       "#86efac", [gpu_util(h) for h in hours]),
    ]

    pad_l, pad_r, pad_t, pad_b = 8, 8, 24, 20
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    lines = []
    for label, color, values in series:
        mn, mx = min(values), max(values)
        rng = mx - mn if mx != mn else 1
        pts = []
        for i, v in enumerate(values):
            px = pad_l + i * chart_w / (len(values) - 1)
            py = pad_t + chart_h - (v - mn) / rng * chart_h
            pts.append(f"{px:.1f},{py:.1f}")
        polyline = f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" opacity="0.85"/>'
        lines.append(polyline)

    # Legend
    legend_items = []
    for idx, (label, color, _) in enumerate(series):
        lx = pad_l + idx * 210
        legend_items.append(
            f'<rect x="{lx}" y="4" width="10" height="4" rx="1" fill="{color}"/>'
            f'<text x="{lx + 14}" y="11" font-family="sans-serif" font-size="9" fill="#94a3b8">{label}</text>'
        )

    body = "\n".join(legend_items + lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def build_dashboard_html() -> str:
    grid_svg     = build_services_grid_svg()
    timeline_svg = build_metric_timeline_svg()

    healthy  = sum(1 for s in SERVICES if s["status"] == "HEALTHY")
    degraded = sum(1 for s in SERVICES if s["status"] == "DEGRADED")
    critical_count = sum(1 for a in ALERTS if a["severity"] == "CRITICAL")

    alert_rows = []
    for a in ALERTS:
        badge_color = "#C74634" if a["severity"] == "CRITICAL" else "#d97706"
        alert_rows.append(
            f'<tr><td><span style="background:{badge_color};color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:11px">{a["severity"]}</span></td>'
            f'<td style="color:#38bdf8;font-family:monospace">{a["service"]}</td>'
            f'<td style="color:#e2e8f0">{a["message"]}</td>'
            f'<td style="color:#64748b;font-size:11px">{a["ts"]}</td></tr>'
        )

    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Observability Hub</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .stat-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 24px; min-width: 150px; }}
  .stat-val {{ font-size: 28px; font-weight: bold; color: #38bdf8; }}
  .stat-val.warn {{ color: #C74634; }}
  .stat-lbl {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  h2 {{ color: #38bdf8; font-size: 15px; margin: 24px 0 10px; text-transform: uppercase; letter-spacing: 1px; }}
  .svg-wrap {{ background: #0f172a; border-radius: 8px; overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th {{ text-align: left; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 6px 10px; }}
  td {{ padding: 8px 10px; border-top: 1px solid #1e293b; font-size: 13px; }}
  .footer {{ margin-top: 32px; color: #334155; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Observability Hub</h1>
<p class="subtitle">Port 8180 &nbsp;|&nbsp; {ts_now} &nbsp;|&nbsp; 15 services monitored</p>

<div class="stat-row">
  <div class="stat"><div class="stat-val">{METRICS_24H['total_api_calls']:,}</div><div class="stat-lbl">Total API Calls (24h)</div></div>
  <div class="stat"><div class="stat-val">{METRICS_24H['training_steps_completed']:,}</div><div class="stat-lbl">Training Steps (24h)</div></div>
  <div class="stat"><div class="stat-val">{METRICS_24H['eval_episodes']}</div><div class="stat-lbl">Eval Episodes (24h)</div></div>
  <div class="stat"><div class="stat-val">{healthy}</div><div class="stat-lbl">Healthy Services</div></div>
  <div class="stat"><div class="stat-val warn">{degraded}</div><div class="stat-lbl">Degraded Services</div></div>
  <div class="stat"><div class="stat-val warn">{METRICS_24H['active_alerts']}</div><div class="stat-lbl">Active Alerts</div></div>
</div>

<h2>Service Grid</h2>
<div class="svg-wrap">{grid_svg}</div>

<h2>Active Alerts ({critical_count} critical)</h2>
<table>
  <thead><tr><th>Severity</th><th>Service</th><th>Message</th><th>Timestamp</th></tr></thead>
  <tbody>{''.join(alert_rows)}</tbody>
</table>

<h2>24h Metric Pulse</h2>
<div class="svg-wrap">{timeline_svg}</div>

<div class="footer">OCI Robot Cloud Observability Hub &copy; 2026 Oracle Corporation</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud Observability Hub",
        description="Unified metrics aggregator for all Robot Cloud services",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_dashboard_html()

    @app.get("/services")
    async def get_services():
        return JSONResponse(content={"services": SERVICES, "total": len(SERVICES)})

    @app.get("/alerts")
    async def get_alerts():
        return JSONResponse(content={"alerts": ALERTS, "total": len(ALERTS)})

    @app.get("/metrics/24h")
    async def get_metrics_24h():
        return JSONResponse(content={"metrics": METRICS_24H, "timestamp": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run("observability_hub:app", host="0.0.0.0", port=8180, reload=False)
    except ImportError:
        print("[observability_hub] uvicorn not installed — cannot start server")
