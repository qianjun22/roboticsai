"""Customer Success Metrics v3 — health + NPS + expansion + retention."""

PORT = 10229
SERVICE_NAME = "customer_success_metrics_v3"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME)

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(_html())

    @app.get("/cs/v3/metrics")
    def cs_metrics():
        return JSONResponse({
            "status": "ok",
            "nps": {
                "overall": 68,
                "target": 75,
                "by_customer": {
                    "Machina": 74,
                    "Verdant": 65,
                    "Helix": 66
                }
            },
            "retention": {
                "logo_retention_pct": 100,
                "dollar_retention_pct": 118
            },
            "expansion": {
                "in_progress": 1,
                "value_usd": 41000
            },
            "health": {
                "accounts_green": 3,
                "accounts_yellow": 0,
                "accounts_red": 0
            }
        })

    @app.get("/cs/v3/dashboard")
    def cs_dashboard_data():
        return JSONResponse({
            "status": "ok",
            "summary": {
                "total_accounts": 3,
                "arr_usd": 180000,
                "nrr_pct": 118,
                "nps_overall": 68,
                "open_expansions": 1,
                "expansion_pipeline_usd": 41000
            },
            "customers": [
                {"name": "Machina", "nps": 74, "health": "green", "arr": 80000},
                {"name": "Verdant", "nps": 65, "health": "green", "arr": 60000},
                {"name": "Helix",   "nps": 66, "health": "green", "arr": 40000}
            ]
        })

else:
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
                body = _html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args):
            pass


def _html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Customer Success Metrics v3 — Port 10229</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
  h1 { color: #C74634; margin-bottom: 0.25rem; }
  h2 { color: #38bdf8; margin-top: 2rem; }
  .badge { display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 4px; padding: 0.2rem 0.6rem; font-size: 0.8rem; margin-right: 0.4rem; }
  .port { color: #38bdf8; font-weight: bold; }
  .green { color: #4ade80; }
  table { border-collapse: collapse; margin-top: 1rem; width: 100%; max-width: 560px; }
  th { text-align: left; color: #94a3b8; padding: 0.4rem 0.8rem; border-bottom: 1px solid #334155; }
  td { padding: 0.4rem 0.8rem; border-bottom: 1px solid #1e293b; }
  .val { color: #38bdf8; }
  .highlight { color: #C74634; font-weight: bold; }
</style>
</head>
<body>
<h1>Customer Success Metrics v3</h1>
<p><span class="badge">Port <span class="port">10229</span></span>
   <span class="badge">Health + NPS + Expansion + Retention</span>
   <span class="badge">Logo Retention 100%</span>
   <span class="badge">NRR 118%</span></p>

<h2>NPS by Customer</h2>
<svg viewBox="0 0 480 160" xmlns="http://www.w3.org/2000/svg" style="max-width:480px;display:block;margin-top:0.5rem">
  <!-- Y axis -->
  <line x1="60" y1="10" x2="60" y2="130" stroke="#334155" stroke-width="1"/>
  <!-- X axis -->
  <line x1="60" y1="130" x2="460" y2="130" stroke="#334155" stroke-width="1"/>
  <!-- Y labels (0-100) -->
  <text x="55" y="14" fill="#94a3b8" font-size="10" text-anchor="end">100</text>
  <text x="55" y="73" fill="#94a3b8" font-size="10" text-anchor="end">50</text>
  <text x="55" y="131" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
  <!-- Grid -->
  <line x1="60" y1="70" x2="460" y2="70" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
  <!-- Target line NPS 75 -->
  <line x1="60" y1="35" x2="460" y2="35" stroke="#C74634" stroke-width="1" stroke-dasharray="6,3"/>
  <text x="462" y="38" fill="#C74634" font-size="9">target 75</text>
  <!-- Bar: Machina NPS 74 -->
  <rect x="80" y="37" width="65" height="93" fill="#C74634" rx="3"/>
  <text x="112" y="32" fill="#e2e8f0" font-size="11" text-anchor="middle">74</text>
  <text x="112" y="145" fill="#94a3b8" font-size="10" text-anchor="middle">Machina</text>
  <!-- Bar: Verdant NPS 65 -->
  <rect x="185" y="48" width="65" height="82" fill="#38bdf8" rx="3"/>
  <text x="217" y="43" fill="#e2e8f0" font-size="11" text-anchor="middle">65</text>
  <text x="217" y="145" fill="#94a3b8" font-size="10" text-anchor="middle">Verdant</text>
  <!-- Bar: Helix NPS 66 -->
  <rect x="290" y="47" width="65" height="83" fill="#38bdf8" rx="3"/>
  <text x="322" y="42" fill="#e2e8f0" font-size="11" text-anchor="middle">66</text>
  <text x="322" y="145" fill="#94a3b8" font-size="10" text-anchor="middle">Helix</text>
  <!-- Bar: Overall NPS 68 -->
  <rect x="395" y="44" width="50" height="86" fill="#475569" rx="3"/>
  <text x="420" y="39" fill="#e2e8f0" font-size="11" text-anchor="middle">68</text>
  <text x="420" y="145" fill="#94a3b8" font-size="10" text-anchor="middle">Overall</text>
</svg>

<h2>Retention &amp; Expansion</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Logo Retention</td><td class="val green">100%</td></tr>
  <tr><td>Dollar Retention (NRR)</td><td class="val green">118%</td></tr>
  <tr><td>Expansions in Progress</td><td class="val">1</td></tr>
  <tr><td>Expansion Pipeline</td><td class="val highlight">$41K</td></tr>
  <tr><td>NPS Overall</td><td class="val">68 (target 75)</td></tr>
</table>

<h2>Account Health</h2>
<table>
  <tr><th>Customer</th><th>NPS</th><th>Health</th><th>ARR</th></tr>
  <tr><td>Machina</td><td class="val">74</td><td class="green">Green</td><td class="val">$80K</td></tr>
  <tr><td>Verdant</td><td class="val">65</td><td class="green">Green</td><td class="val">$60K</td></tr>
  <tr><td>Helix</td><td class="val">66</td><td class="green">Green</td><td class="val">$40K</td></tr>
</table>

<h2>Endpoints</h2>
<table>
  <tr><th>Method</th><th>Path</th><th>Description</th></tr>
  <tr><td>GET</td><td>/health</td><td>Health check</td></tr>
  <tr><td>GET</td><td>/</td><td>This dashboard</td></tr>
  <tr><td>GET</td><td>/cs/v3/metrics</td><td>Full CS metrics payload</td></tr>
  <tr><td>GET</td><td>/cs/v3/dashboard</td><td>Dashboard summary + customer list</td></tr>
</table>
</body>
</html>
"""


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"{SERVICE_NAME} fallback HTTP server running on port {PORT}")
        server.serve_forever()
