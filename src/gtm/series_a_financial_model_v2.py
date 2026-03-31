"""Series A Financial Model v2 — Q1 actuals + AI World scenario + 36-month projection (port 10259).

Q1 actuals: $250K vs $220K plan (+14% beat).
3-year ARR projection: Year 1 $430K | Year 2 $1.8M | Year 3 $6.2M (43% CAGR).
Use of funds: ML engineers $680K + infra $420K + marketing $300K.
"""

PORT = 10259
SERVICE_NAME = "series_a_financial_model_v2"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Series A Financial Model v2", version="2.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/finance/series_a_model_v2")
    def model_v2():
        return JSONResponse({
            "model_version": "v2",
            "q1_actuals_usd": 250000,
            "q1_plan_usd": 220000,
            "q1_beat_pct": 13.64,
            "arr_year1_usd": 430000,
            "arr_year2_usd": 1800000,
            "arr_year3_usd": 6200000,
            "cagr_pct": 43,
            "use_of_funds": {
                "ml_engineers_usd": 680000,
                "infra_usd": 420000,
                "marketing_usd": 300000
            },
            "scenario": "AI World + base"
        })

    @app.get("/finance/series_a_model_v2/sensitivity")
    def sensitivity():
        return JSONResponse({
            "model_version": "v2",
            "scenarios": [
                {"name": "bear",  "arr_year3_usd": 3800000, "cagr_pct": 30},
                {"name": "base",  "arr_year3_usd": 6200000, "cagr_pct": 43},
                {"name": "bull",  "arr_year3_usd": 9500000, "cagr_pct": 57}
            ],
            "key_drivers": ["design_partner_conversion", "ai_world_pipeline", "infra_margin"]
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html_dashboard())

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Series A Financial Model v2</title>
  <style>
    body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
    header { background: #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { margin: 0; font-size: 1.5rem; letter-spacing: .5px; }
    .badge { background: #38bdf8; color: #0f172a; padding: 3px 10px; border-radius: 12px; font-size: .8rem; font-weight: 700; }
    .container { max-width: 900px; margin: 40px auto; padding: 0 24px; }
    .card { background: #1e293b; border-radius: 12px; padding: 28px; margin-bottom: 28px; }
    .card h2 { margin: 0 0 8px; color: #38bdf8; font-size: 1.1rem; }
    .meta { font-size: .85rem; color: #94a3b8; margin-bottom: 20px; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
    .stat { background: #0f172a; border-radius: 8px; padding: 14px; text-align: center; }
    .stat .val { font-size: 1.6rem; font-weight: 700; color: #C74634; }
    .stat .lbl { font-size: .72rem; color: #94a3b8; margin-top: 4px; }
    .funds { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
    .fund { background: #0f172a; border-radius: 8px; padding: 14px; text-align: center; }
    .fund .val { font-size: 1.3rem; font-weight: 700; color: #38bdf8; }
    .fund .lbl { font-size: .72rem; color: #94a3b8; margin-top: 4px; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <header>
    <h1>Series A Financial Model v2</h1>
    <span class="badge">port 10259</span>
    <span class="badge" style="background:#1e293b;color:#38bdf8;">Q1 Actuals + 36-mo Projection</span>
  </header>
  <div class="container">
    <div class="card">
      <h2>ARR 3-Year Projection (43% CAGR)</h2>
      <p class="meta">Q1 actuals: $250K vs $220K plan (+14% beat) &mdash; AI World scenario + base pipeline.</p>
      <div class="stats">
        <div class="stat"><div class="val">$250K</div><div class="lbl">Q1 Actuals</div></div>
        <div class="stat"><div class="val">$430K</div><div class="lbl">Year 1 ARR</div></div>
        <div class="stat"><div class="val">$1.8M</div><div class="lbl">Year 2 ARR</div></div>
        <div class="stat"><div class="val">$6.2M</div><div class="lbl">Year 3 ARR</div></div>
      </div>
      <!-- SVG bar chart -->
      <svg width="100%" viewBox="0 0 420 210" xmlns="http://www.w3.org/2000/svg">
        <rect width="420" height="210" fill="#0f172a" rx="8"/>
        <!-- axes -->
        <line x1="70" y1="20" x2="70" y2="165" stroke="#334155" stroke-width="1"/>
        <line x1="70" y1="165" x2="400" y2="165" stroke="#334155" stroke-width="1"/>
        <!-- gridlines -->
        <line x1="70" y1="115" x2="400" y2="115" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="70" y1="65" x2="400" y2="65" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
        <!-- y-axis labels -->
        <text x="62" y="169" fill="#94a3b8" font-size="10" text-anchor="end">$0</text>
        <text x="62" y="119" fill="#94a3b8" font-size="10" text-anchor="end">$3M</text>
        <text x="62" y="69" fill="#94a3b8" font-size="10" text-anchor="end">$6M</text>
        <!-- Year 1: $430K → height=11 (430/6200 * 145) -->
        <rect x="95"  y="155" width="55" height="10" fill="#38bdf8" rx="3"/>
        <text x="122" y="150" fill="#38bdf8" font-size="11" text-anchor="middle">$430K</text>
        <text x="122" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Year 1</text>
        <!-- Year 2: $1.8M → height=42 -->
        <rect x="185" y="123" width="55" height="42" fill="#C74634" rx="3"/>
        <text x="212" y="118" fill="#C74634" font-size="11" text-anchor="middle">$1.8M</text>
        <text x="212" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Year 2</text>
        <!-- Year 3: $6.2M → height=145 -->
        <rect x="275" y="20" width="55" height="145" fill="#C74634" rx="3" opacity="0.85"/>
        <text x="302" y="15" fill="#C74634" font-size="11" text-anchor="middle">$6.2M</text>
        <text x="302" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Year 3</text>
        <!-- CAGR label -->
        <text x="210" y="200" fill="#64748b" font-size="10" text-anchor="middle">43% CAGR &mdash; AI World + Base Scenario</text>
      </svg>
    </div>
    <div class="card">
      <h2>Use of Funds</h2>
      <div class="funds">
        <div class="fund"><div class="val">$680K</div><div class="lbl">ML Engineers</div></div>
        <div class="fund"><div class="val">$420K</div><div class="lbl">Infrastructure</div></div>
        <div class="fund"><div class="val">$300K</div><div class="lbl">Marketing</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Endpoints</h2>
      <p class="meta">GET <code>/health</code> &nbsp;&bull;&nbsp; GET <code>/finance/series_a_model_v2</code> &nbsp;&bull;&nbsp; GET <code>/finance/series_a_model_v2/sensitivity</code></p>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

if not _FASTAPI_AVAILABLE:
    import http.server
    import json

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        import http.server
        srv = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback server on port {PORT}")
        srv.serve_forever()
