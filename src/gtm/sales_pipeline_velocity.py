"""Sales Pipeline Velocity Service (port 10195).

Tracks pipeline velocity = deals × win_rate × ACV / sales_cycle and
provides lever analysis for accelerating revenue throughput.
"""

import json
import datetime
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10195
SERVICE_NAME = "sales_pipeline_velocity"

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sales Pipeline Velocity</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    h2 { color: #38bdf8; font-size: 1.1rem; margin: 1.6rem 0 0.6rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.4rem; margin-bottom: 1.2rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
    .metric { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 1rem; text-align: center; }
    .metric .value { font-size: 1.8rem; font-weight: bold; color: #38bdf8; }
    .metric .label { font-size: 0.78rem; color: #94a3b8; margin-top: 0.3rem; }
    .badge { display: inline-block; background: #C74634; color: #fff; font-size: 0.7rem;
             border-radius: 4px; padding: 0.15rem 0.5rem; margin-left: 0.5rem; vertical-align: middle; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { background: #0f172a; color: #38bdf8; text-align: left; padding: 0.5rem 0.8rem; border-bottom: 1px solid #334155; }
    td { padding: 0.5rem 0.8rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    tr:hover td { background: #1e293b; }
    .highlight { color: #38bdf8; font-weight: 600; }
    .warn { color: #C74634; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Sales Pipeline Velocity <span class="badge">port 10195</span></h1>
  <p class="subtitle">velocity = deals &times; win_rate &times; ACV &divide; sales_cycle &nbsp;|&nbsp; Current: <strong style="color:#38bdf8">$48.3K/month</strong></p>

  <div class="card">
    <h2>Velocity Snapshot</h2>
    <div class="metric-grid">
      <div class="metric"><div class="value">$48.3K</div><div class="label">Pipeline velocity ($/month)</div></div>
      <div class="metric"><div class="value">67d</div><div class="label">Total sales cycle (prospect→close)</div></div>
      <div class="metric"><div class="value">31%</div><div class="label">Overall win rate</div></div>
      <div class="metric"><div class="value">$142K</div><div class="label">Average contract value (ACV)</div></div>
      <div class="metric"><div class="value">+$7.2K</div><div class="label">Cycle compression uplift per -10 days</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Stage Duration (days)</h2>
    <!-- SVG bar chart: stage times -->
    <svg viewBox="0 0 560 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px;display:block;margin:0 auto">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="180" stroke="#475569" stroke-width="1"/>
      <line x1="70" y1="180" x2="540" y2="180" stroke="#475569" stroke-width="1"/>
      <!-- y-axis labels (max 30d) -->
      <text x="65" y="183" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
      <text x="65" y="123" fill="#94a3b8" font-size="10" text-anchor="end">10</text>
      <text x="65" y="63" fill="#94a3b8" font-size="10" text-anchor="end">20</text>
      <text x="65" y="13" fill="#94a3b8" font-size="10" text-anchor="end">30</text>
      <!-- gridlines -->
      <line x1="70" y1="120" x2="540" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="60" x2="540" y2="60" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="10" x2="540" y2="10" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- bar scale: 30d -> 170px  so 1d = 5.67px -->
      <!-- Prospect→SQL: 18d -> height=102 -->
      <rect x="105" y="78" width="90" height="102" fill="#38bdf8" rx="3"/>
      <text x="150" y="73" fill="#38bdf8" font-size="11" text-anchor="middle">18d</text>
      <text x="150" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">Prospect</text>
      <text x="150" y="208" fill="#94a3b8" font-size="9" text-anchor="middle">→SQL</text>
      <!-- SQL→Trial: 22d -> height=125 -->
      <rect x="235" y="55" width="90" height="125" fill="#C74634" rx="3"/>
      <text x="280" y="50" fill="#C74634" font-size="11" text-anchor="middle">22d</text>
      <text x="280" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">SQL</text>
      <text x="280" y="208" fill="#94a3b8" font-size="9" text-anchor="middle">→Trial</text>
      <!-- Trial→Close: 27d -> height=153 -->
      <rect x="365" y="27" width="90" height="153" fill="#7c3aed" rx="3"/>
      <text x="410" y="22" fill="#c4b5fd" font-size="11" text-anchor="middle">27d</text>
      <text x="410" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">Trial</text>
      <text x="410" y="208" fill="#94a3b8" font-size="9" text-anchor="middle">→Close</text>
      <!-- axis title -->
      <text x="305" y="222" fill="#64748b" font-size="9" text-anchor="middle">Stage duration (days) — total cycle 67 days</text>
    </svg>
  </div>

  <div class="card">
    <h2>Lever Analysis — Revenue Impact</h2>
    <table>
      <thead><tr><th>Lever</th><th>Change</th><th>Velocity Uplift</th><th>ROI Rank</th></tr></thead>
      <tbody>
        <tr><td>Cycle compression</td><td>-10 days</td><td class="highlight">+$7.2K/mo</td><td class="highlight">1 (highest)</td></tr>
        <tr><td>Win rate improvement</td><td>+5 pp</td><td class="highlight">+$5.8K/mo</td><td>2</td></tr>
        <tr><td>ACV expansion</td><td>+10%</td><td>+$4.8K/mo</td><td>3</td></tr>
        <tr><td>Deal volume increase</td><td>+2 deals/mo</td><td>+$4.5K/mo</td><td>4</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>API Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td>GET</td><td>/health</td><td>Service health + status</td></tr>
        <tr><td>GET</td><td>/</td><td>This dashboard</td></tr>
        <tr><td>GET</td><td>/sales/pipeline_velocity</td><td>Current velocity metrics</td></tr>
        <tr><td>GET</td><td>/sales/velocity_forecast</td><td>90-day velocity forecast</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def _make_app() -> "FastAPI":
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/sales/pipeline_velocity")
    async def pipeline_velocity() -> Dict[str, Any]:
        return {
            "velocity_usd_per_month": 48300,
            "sales_cycle_days": 67,
            "win_rate": 0.31,
            "acv_usd": 142000,
            "stage_days": {
                "prospect_to_sql": 18,
                "sql_to_trial": 22,
                "trial_to_close": 27,
            },
            "top_lever": "cycle_compression",
            "cycle_compression_uplift_per_10d": 7200,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/sales/velocity_forecast")
    async def velocity_forecast() -> Dict[str, Any]:
        base = 48300
        return {
            "forecast_horizon_days": 90,
            "current_velocity_usd_per_month": base,
            "forecast": [
                {"month": 1, "velocity": base},
                {"month": 2, "velocity": round(base * 1.08)},
                {"month": 3, "velocity": round(base * 1.17)},
            ],
            "assumptions": [
                "Cycle compression lever applied in month 2 (-10 days)",
                "Win rate held constant at 31%",
                "ACV growth 4% per month",
            ],
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

    return app


if _FASTAPI_AVAILABLE:
    app = _make_app()


def _fallback_server() -> None:
    """Minimal fallback using stdlib http.server."""
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                ct = "application/json"
            else:
                body = DASHBOARD_HTML.encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[{SERVICE_NAME}] fallback server on port {PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _fallback_server()
