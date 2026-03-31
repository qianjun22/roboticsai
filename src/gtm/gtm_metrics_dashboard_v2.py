"""GTM Metrics Dashboard v2 — unified funnel + revenue + product + CS view (port 10215).

Consolidates all go-to-market KPIs: ARR, NRR, CAC, LTV/CAC, magic number,
funnel metrics (MQLs → SQLs → trials → closed), and pipeline velocity.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10215
SERVICE_NAME = "gtm_metrics_dashboard_v2"

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GTM Metrics Dashboard v2 — Port 10215</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 2rem;
    }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }
    .badge {
      display: inline-block;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 0.2rem 0.7rem;
      font-size: 0.8rem;
      color: #38bdf8;
      margin-right: 0.5rem;
      margin-bottom: 1.5rem;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.2rem;
    }
    .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { color: #38bdf8; font-size: 1.6rem; font-weight: 700; margin-top: 0.3rem; }
    .card .note { color: #64748b; font-size: 0.75rem; margin-top: 0.2rem; }
    .card.highlight .value { color: #C74634; }
    .section-title {
      color: #C74634;
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 1rem;
    }
    .chart-wrap {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.5rem;
      margin-bottom: 2rem;
    }
    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
      margin-bottom: 2rem;
    }
    @media (max-width: 700px) { .two-col { grid-template-columns: 1fr; } }
    .panel {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.2rem;
    }
    .funnel-item {
      display: flex;
      justify-content: space-between;
      padding: 0.45rem 0;
      border-bottom: 1px solid #334155;
      font-size: 0.9rem;
    }
    .funnel-item:last-child { border-bottom: none; }
    .funnel-label { color: #94a3b8; }
    .funnel-val { color: #38bdf8; font-weight: 600; }
    .endpoint-list {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.2rem;
    }
    .endpoint-list li {
      list-style: none;
      padding: 0.4rem 0;
      border-bottom: 1px solid #334155;
      font-family: monospace;
      font-size: 0.9rem;
    }
    .endpoint-list li:last-child { border-bottom: none; }
    .method { color: #38bdf8; margin-right: 0.5rem; }
    .path { color: #e2e8f0; }
    .desc { color: #94a3b8; font-size: 0.8rem; margin-left: 0.5rem; }
  </style>
</head>
<body>
  <h1>GTM Metrics Dashboard v2</h1>
  <p class="subtitle">Unified funnel + revenue + product + CS view — all go-to-market KPIs in one place</p>
  <span class="badge">port 10215</span>
  <span class="badge">cycle-539B</span>
  <span class="badge">OCI Robot Cloud</span>

  <div class="cards">
    <div class="card">
      <div class="label">ARR</div>
      <div class="value">$250K</div>
      <div class="note">annual recurring revenue</div>
    </div>
    <div class="card highlight">
      <div class="label">NRR</div>
      <div class="value">118%</div>
      <div class="note">net revenue retention</div>
    </div>
    <div class="card">
      <div class="label">CAC</div>
      <div class="value">$10.2K</div>
      <div class="note">customer acquisition cost</div>
    </div>
    <div class="card">
      <div class="label">LTV / CAC</div>
      <div class="value">40.7×</div>
      <div class="note">lifetime value ratio</div>
    </div>
    <div class="card">
      <div class="label">Magic Number</div>
      <div class="value">1.3</div>
      <div class="note">sales efficiency</div>
    </div>
    <div class="card">
      <div class="label">Pipeline Velocity</div>
      <div class="value">$48.3K</div>
      <div class="note">per month</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">GTM KPIs — Indexed Bar Chart</div>
    <svg viewBox="0 0 540 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:540px;display:block;">
      <!-- grid -->
      <line x1="60" y1="20" x2="520" y2="20" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="60" x2="520" y2="60" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="100" x2="520" y2="100" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="140" x2="520" y2="140" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="170" x2="520" y2="170" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="50" y="174" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="50" y="144" fill="#64748b" font-size="10" text-anchor="end">25</text>
      <text x="50" y="104" fill="#64748b" font-size="10" text-anchor="end">50</text>
      <text x="50" y="64" fill="#64748b" font-size="10" text-anchor="end">75</text>
      <text x="50" y="24" fill="#64748b" font-size="10" text-anchor="end">100</text>
      <!-- NRR 118 → capped at 100 visually, shown as full bar -->
      <rect x="70" y="20" width="52" height="150" rx="3" fill="#38bdf8"/>
      <text x="96" y="15" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="700">118%</text>
      <text x="96" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">NRR</text>
      <!-- Magic Number 1.3 → 1.3/2 * 150 = 97.5 -->
      <rect x="140" y="73" width="52" height="97" rx="3" fill="#C74634"/>
      <text x="166" y="67" fill="#C74634" font-size="10" text-anchor="middle" font-weight="700">1.3</text>
      <text x="166" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">Magic#</text>
      <!-- MQLs 24/mo → 24/50*150 = 72 -->
      <rect x="210" y="98" width="52" height="72" rx="3" fill="#38bdf8"/>
      <text x="236" y="92" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="700">24</text>
      <text x="236" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">MQLs/mo</text>
      <!-- SQLs 14/mo → 14/50*150 = 42 -->
      <rect x="280" y="128" width="52" height="42" rx="3" fill="#C74634"/>
      <text x="306" y="122" fill="#C74634" font-size="10" text-anchor="middle" font-weight="700">14</text>
      <text x="306" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">SQLs/mo</text>
      <!-- trials 6/mo → 6/50*150 = 18 -->
      <rect x="350" y="152" width="52" height="18" rx="3" fill="#38bdf8"/>
      <text x="376" y="146" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="700">6</text>
      <text x="376" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">Trials/mo</text>
      <!-- closed 1.2/mo → 1.2/50*150 = 3.6 -> show min 8 for visibility -->
      <rect x="420" y="162" width="52" height="8" rx="3" fill="#C74634"/>
      <text x="446" y="156" fill="#C74634" font-size="10" text-anchor="middle" font-weight="700">1.2</text>
      <text x="446" y="188" fill="#94a3b8" font-size="10" text-anchor="middle">Closed/mo</text>
    </svg>
  </div>

  <div class="two-col">
    <div class="panel">
      <div class="section-title">Funnel</div>
      <div class="funnel-item"><span class="funnel-label">MQLs</span><span class="funnel-val">24 / mo</span></div>
      <div class="funnel-item"><span class="funnel-label">SQLs</span><span class="funnel-val">14 / mo</span></div>
      <div class="funnel-item"><span class="funnel-label">Trials</span><span class="funnel-val">6 / mo</span></div>
      <div class="funnel-item"><span class="funnel-label">Closed</span><span class="funnel-val">1.2 / mo</span></div>
      <div class="funnel-item"><span class="funnel-label">MQL→SQL</span><span class="funnel-val">58%</span></div>
      <div class="funnel-item"><span class="funnel-label">SQL→Trial</span><span class="funnel-val">43%</span></div>
      <div class="funnel-item"><span class="funnel-label">Trial→Closed</span><span class="funnel-val">20%</span></div>
    </div>
    <div class="panel">
      <div class="section-title">Revenue Metrics</div>
      <div class="funnel-item"><span class="funnel-label">ARR</span><span class="funnel-val">$250K</span></div>
      <div class="funnel-item"><span class="funnel-label">NRR</span><span class="funnel-val">118%</span></div>
      <div class="funnel-item"><span class="funnel-label">CAC</span><span class="funnel-val">$10.2K</span></div>
      <div class="funnel-item"><span class="funnel-label">LTV / CAC</span><span class="funnel-val">40.7×</span></div>
      <div class="funnel-item"><span class="funnel-label">Magic Number</span><span class="funnel-val">1.3</span></div>
      <div class="funnel-item"><span class="funnel-label">Pipeline Velocity</span><span class="funnel-val">$48.3K / mo</span></div>
    </div>
  </div>

  <div class="endpoint-list">
    <div class="section-title">Endpoints</div>
    <ul>
      <li><span class="method">GET</span><span class="path">/health</span><span class="desc">— service health + port</span></li>
      <li><span class="method">GET</span><span class="path">/</span><span class="desc">— this unified dashboard</span></li>
      <li><span class="method">GET</span><span class="path">/gtm/v2/dashboard</span><span class="desc">— full KPI payload</span></li>
      <li><span class="method">GET</span><span class="path">/gtm/v2/alerts</span><span class="desc">— active GTM alerts</span></li>
    </ul>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="GTM Metrics Dashboard v2",
        description="Unified GTM metrics: funnel + revenue + product + CS in one view",
        version="2.0.0",
    )

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/gtm/v2/dashboard")
    async def gtm_v2_dashboard():
        """Return full unified GTM KPI payload (mock)."""
        return JSONResponse({
            "version": 2,
            "as_of": datetime.utcnow().isoformat() + "Z",
            "revenue": {
                "arr_usd": 250_000,
                "nrr_pct": 118,
                "cac_usd": 10_200,
                "ltv_cac_ratio": 40.7,
                "magic_number": 1.3,
                "pipeline_velocity_usd_mo": 48_300,
            },
            "funnel": {
                "mqls_per_mo": 24,
                "sqls_per_mo": 14,
                "trials_per_mo": 6,
                "closed_per_mo": 1.2,
                "mql_to_sql_pct": 58,
                "sql_to_trial_pct": 43,
                "trial_to_closed_pct": 20,
            },
            "cs": {
                "nps": 62,
                "churn_rate_pct": 2.1,
                "expansion_arr_usd": 18_000,
            },
            "product": {
                "dau_wau": 0.41,
                "activation_rate_pct": 67,
                "time_to_value_days": 3.2,
            },
        })

    @app.get("/gtm/v2/alerts")
    async def gtm_v2_alerts():
        """Return active GTM alerts (mock)."""
        return JSONResponse({
            "alerts": [
                {
                    "id": "alert-001",
                    "severity": "info",
                    "metric": "mqls_per_mo",
                    "message": "MQLs trending +12% WoW — pipeline healthy",
                    "triggered_at": datetime.utcnow().isoformat() + "Z",
                },
                {
                    "id": "alert-002",
                    "severity": "warning",
                    "metric": "trial_to_closed_pct",
                    "message": "Trial→Closed conversion at 20% — below 25% target",
                    "triggered_at": datetime.utcnow().isoformat() + "Z",
                },
            ],
            "total": 2,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

# ---------------------------------------------------------------------------
# Fallback HTTP server (stdlib)
# ---------------------------------------------------------------------------

def _run_stdlib_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib_server()
