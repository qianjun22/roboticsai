"""Product Analytics Platform — feature adoption, API patterns, activation funnel (port 10031).

Tracks fine-tune, eval, DAgger, sim, and data-collection API adoption across cohorts.
Provides activation funnel analysis from signup through production usage.
"""

from __future__ import annotations

import json
from datetime import datetime

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

PORT = 10031

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Product Analytics Platform — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 3px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f1f5f9; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 9999px; }
    .container { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }
    .kpi .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .kpi .value { font-size: 2rem; font-weight: 700; }
    .kpi .value.red { color: #C74634; }
    .kpi .value.blue { color: #38bdf8; }
    .kpi .value.green { color: #4ade80; }
    .kpi .value.amber { color: #fbbf24; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { font-size: 1rem; color: #38bdf8; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .funnel { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.5rem; }
    .funnel-step { display: flex; align-items: center; gap: 1rem; }
    .funnel-bar-wrap { flex: 1; background: #0f172a; border-radius: 4px; height: 28px; overflow: hidden; }
    .funnel-bar { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 0.5rem; font-size: 0.75rem; font-weight: 600; color: #0f172a; white-space: nowrap; }
    .funnel-label { width: 160px; font-size: 0.8rem; color: #94a3b8; text-align: right; }
    .funnel-pct { width: 44px; font-size: 0.85rem; font-weight: 700; color: #f1f5f9; }
    .usage-row { display: flex; gap: 0.4rem; margin-top: 0.5rem; align-items: flex-end; }
    .usage-day { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex: 1; }
    .usage-day .bar { width: 100%; border-radius: 3px 3px 0 0; }
    .usage-day .day-label { font-size: 0.65rem; color: #64748b; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem; }
  </style>
</head>
<body>
  <header>
    <h1>Product Analytics Platform</h1>
    <span class="badge">Port 10031</span>
    <span class="badge" style="background:#38bdf8;color:#0f172a;">GTM Analytics</span>
  </header>
  <div class="container">
    <div class="kpi-row">
      <div class="kpi">
        <div class="label">Fine-Tune API Adoption</div>
        <div class="value blue">94%</div>
      </div>
      <div class="kpi">
        <div class="label">Product NPS</div>
        <div class="value green">72</div>
      </div>
      <div class="kpi">
        <div class="label">Activation to Production</div>
        <div class="value amber">38%</div>
      </div>
      <div class="kpi">
        <div class="label">Peak Usage Days</div>
        <div class="value red">Mon–Wed</div>
      </div>
    </div>

    <!-- Feature adoption bar chart -->
    <div class="section">
      <h2>Feature Adoption Rates</h2>
      <svg viewBox="0 0 700 240" width="100%" xmlns="http://www.w3.org/2000/svg">
        <line x1="160" y1="20" x2="160" y2="190" stroke="#475569" stroke-width="1"/>
        <line x1="160" y1="190" x2="680" y2="190" stroke="#475569" stroke-width="1"/>
        <!-- grid lines -->
        <line x1="160" y1="160" x2="680" y2="160" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
        <line x1="160" y1="130" x2="680" y2="130" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
        <line x1="160" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
        <line x1="160" y1="70" x2="680" y2="70" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
        <line x1="160" y1="40" x2="680" y2="40" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
        <!-- y labels -->
        <text x="155" y="194" fill="#64748b" font-size="9" text-anchor="end">0%</text>
        <text x="155" y="164" fill="#64748b" font-size="9" text-anchor="end">25%</text>
        <text x="155" y="134" fill="#64748b" font-size="9" text-anchor="end">50%</text>
        <text x="155" y="104" fill="#64748b" font-size="9" text-anchor="end">75%</text>
        <text x="155" y="44" fill="#64748b" font-size="9" text-anchor="end">100%</text>
        <!-- bars: each feature, height proportional to adoption (170px = 100%) -->
        <!-- fine_tune_api: 94% → height=160 -->
        <rect x="185" y="30" width="60" height="160" fill="#38bdf8" rx="4"/>
        <text x="215" y="25" fill="#38bdf8" font-size="10" text-anchor="middle">94%</text>
        <!-- eval_api: 87% → height=148 -->
        <rect x="285" y="42" width="60" height="148" fill="#38bdf8" rx="4" opacity="0.85"/>
        <text x="315" y="37" fill="#38bdf8" font-size="10" text-anchor="middle">87%</text>
        <!-- dagger_api: 72% → height=122 -->
        <rect x="385" y="68" width="60" height="122" fill="#C74634" rx="4"/>
        <text x="415" y="63" fill="#C74634" font-size="10" text-anchor="middle">72%</text>
        <!-- sim_api: 61% → height=104 -->
        <rect x="485" y="86" width="60" height="104" fill="#C74634" rx="4" opacity="0.8"/>
        <text x="515" y="81" fill="#C74634" font-size="10" text-anchor="middle">61%</text>
        <!-- data_collection: 45% → height=77 -->
        <rect x="585" y="113" width="60" height="77" fill="#fbbf24" rx="4"/>
        <text x="615" y="108" fill="#fbbf24" font-size="10" text-anchor="middle">45%</text>
        <!-- x labels -->
        <text x="215" y="207" fill="#94a3b8" font-size="9" text-anchor="middle">Fine-Tune API</text>
        <text x="315" y="207" fill="#94a3b8" font-size="9" text-anchor="middle">Eval API</text>
        <text x="415" y="207" fill="#94a3b8" font-size="9" text-anchor="middle">DAgger API</text>
        <text x="515" y="207" fill="#94a3b8" font-size="9" text-anchor="middle">Sim API</text>
        <text x="615" y="207" fill="#94a3b8" font-size="9" text-anchor="middle">Data Collect</text>
      </svg>
    </div>

    <!-- Activation funnel -->
    <div class="section">
      <h2>Activation Funnel — Signup to Production</h2>
      <div class="funnel">
        <div class="funnel-step">
          <div class="funnel-label">Signed Up</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:100%;background:#38bdf8;">100%</div></div>
          <div class="funnel-pct">100%</div>
        </div>
        <div class="funnel-step">
          <div class="funnel-label">API Key Created</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:78%;background:#38bdf8;">78%</div></div>
          <div class="funnel-pct">78%</div>
        </div>
        <div class="funnel-step">
          <div class="funnel-label">First Fine-Tune</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:62%;background:#38bdf8;">62%</div></div>
          <div class="funnel-pct">62%</div>
        </div>
        <div class="funnel-step">
          <div class="funnel-label">First Eval Run</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:54%;background:#fbbf24;">54%</div></div>
          <div class="funnel-pct">54%</div>
        </div>
        <div class="funnel-step">
          <div class="funnel-label">DAgger Iteration</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:47%;background:#fbbf24;">47%</div></div>
          <div class="funnel-pct">47%</div>
        </div>
        <div class="funnel-step">
          <div class="funnel-label">Production Deploy</div>
          <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:38%;background:#C74634;">38%</div></div>
          <div class="funnel-pct">38%</div>
        </div>
      </div>
    </div>

    <!-- Weekly usage pattern -->
    <div class="section">
      <h2>API Usage Pattern — Day of Week (normalized)</h2>
      <div class="usage-row">
        <div class="usage-day">
          <div class="bar" style="height:90px;background:#38bdf8;"></div>
          <div class="day-label">Mon</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:85px;background:#38bdf8;"></div>
          <div class="day-label">Tue</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:80px;background:#38bdf8;"></div>
          <div class="day-label">Wed</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:60px;background:#C74634;"></div>
          <div class="day-label">Thu</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:50px;background:#C74634;"></div>
          <div class="day-label">Fri</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:20px;background:#475569;"></div>
          <div class="day-label">Sat</div>
        </div>
        <div class="usage-day">
          <div class="bar" style="height:15px;background:#475569;"></div>
          <div class="day-label">Sun</div>
        </div>
      </div>
    </div>
  </div>
  <footer>OCI Robot Cloud &mdash; Product Analytics Platform &mdash; Port 10031 &mdash; Feature Adoption &amp; Funnel Analytics</footer>
</body>
</html>
"""


_ADOPTION_RATES = {
    "fine_tune_api": 0.94,
    "eval_api": 0.87,
    "dagger_api": 0.72,
    "sim_api": 0.61,
    "data_collection": 0.45,
}

_FUNNEL_STAGES = [
    {"stage": "signed_up",         "rate": 1.00, "label": "Signed Up"},
    {"stage": "api_key_created",    "rate": 0.78, "label": "API Key Created"},
    {"stage": "first_fine_tune",    "rate": 0.62, "label": "First Fine-Tune"},
    {"stage": "first_eval_run",     "rate": 0.54, "label": "First Eval Run"},
    {"stage": "dagger_iteration",   "rate": 0.47, "label": "DAgger Iteration"},
    {"stage": "production_deploy",  "rate": 0.38, "label": "Production Deploy"},
]


def _adoption_response(timerange: str) -> dict:
    trend_map = {
        "7d": "up +2% WoW",
        "30d": "up +8% MoM",
        "90d": "up +21% QoQ",
    }
    trend = trend_map.get(timerange, "stable")
    return {"adoption_rates": _ADOPTION_RATES, "trend": trend, "timerange": timerange}


def _funnel_response(cohort: str) -> dict:
    dropoff_points = [
        {"from": s["label"], "to": _FUNNEL_STAGES[i + 1]["label"],
         "dropoff_pct": round((s["rate"] - _FUNNEL_STAGES[i + 1]["rate"]) / s["rate"] * 100, 1)}
        for i, s in enumerate(_FUNNEL_STAGES[:-1])
    ]
    return {
        "cohort": cohort,
        "stages": _FUNNEL_STAGES,
        "production_activation_rate": 0.38,
        "top_dropoff": max(dropoff_points, key=lambda x: x["dropoff_pct"]),
        "dropoff_points": dropoff_points,
    }


if _FASTAPI:
    app = FastAPI(
        title="Product Analytics Platform",
        description="Feature adoption rates, API usage patterns, and activation funnel for OCI Robot Cloud.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the HTML dashboard."""
        return HTML_DASHBOARD

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "product_analytics_platform",
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/analytics/feature_adoption")
    async def feature_adoption(timerange: str = Query(default="30d", description="Time range: 7d, 30d, 90d")):
        """Return feature adoption rates across all major APIs."""
        return _adoption_response(timerange)

    @app.get("/analytics/funnel")
    async def funnel(cohort: str = Query(default="all", description="Cohort name or 'all'")):
        """Return activation funnel rates and dropoff analysis."""
        return _funnel_response(cohort)

else:
    # stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, data: dict, status: int = 200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str):
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            if path == "/":
                self._send_html(HTML_DASHBOARD)
            elif path == "/health":
                self._send_json({"status": "ok", "service": "product_analytics_platform", "port": PORT})
            elif path == "/analytics/feature_adoption":
                timerange = qs.get("timerange", ["30d"])[0]
                self._send_json(_adoption_response(timerange))
            elif path == "/analytics/funnel":
                cohort = qs.get("cohort", ["all"])[0]
                self._send_json(_funnel_response(cohort))
            else:
                self._send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[product_analytics_platform] stdlib fallback — listening on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
