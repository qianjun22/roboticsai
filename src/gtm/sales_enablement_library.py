"""Sales Enablement Library — OCI Robot Cloud (port 10253)

Centralized sales enablement content: battle cards, ROI calculators,
demo scripts, objection handling guides, and case studies.
30 assets total. Reps with enablement: 73% win rate vs 58% without (+15%).
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

PORT = 10253
SERVICE_NAME = "sales_enablement_library"

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sales Enablement Library — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .metrics { display: flex; gap: 1.5rem; flex-wrap: wrap; }
    .metric { background: #0f172a; border-radius: 0.5rem; padding: 1rem 1.5rem; min-width: 140px; text-align: center; }
    .metric .val { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .assets { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .asset-badge { background: #0f172a; border: 1px solid #334155; border-radius: 0.4rem; padding: 0.4rem 0.8rem; font-size: 0.85rem; color: #38bdf8; }
    .asset-badge span { color: #C74634; font-weight: bold; margin-right: 0.3rem; }
    .endpoints { list-style: none; }
    .endpoints li { padding: 0.4rem 0; border-bottom: 1px solid #334155; font-size: 0.9rem; }
    .endpoints li:last-child { border-bottom: none; }
    .method { display: inline-block; width: 52px; color: #38bdf8; font-weight: bold; font-size: 0.8rem; }
    .footer { color: #475569; font-size: 0.8rem; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Sales Enablement Library</h1>
  <div class="subtitle">OCI Robot Cloud &mdash; Port 10253 &mdash; Battle cards, ROI calculators, demo scripts &amp; objection handling</div>

  <div class="card">
    <h2>Enablement Impact: Win Rate Comparison</h2>
    <svg width="420" height="180" viewBox="0 0 420 180" xmlns="http://www.w3.org/2000/svg">
      <!-- Y-axis label -->
      <text x="12" y="95" fill="#94a3b8" font-size="11" transform="rotate(-90 12 95)">Win Rate %</text>
      <!-- Grid lines -->
      <line x1="50" y1="20" x2="50" y2="140" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="140" x2="400" y2="140" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="60" x2="400" y2="60" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="50" y1="100" x2="400" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Y labels -->
      <text x="44" y="144" fill="#94a3b8" font-size="10" text-anchor="end">0%</text>
      <text x="44" y="104" fill="#94a3b8" font-size="10" text-anchor="end">50%</text>
      <text x="44" y="64" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
      <!-- Bar: with enablement 73% -->
      <rect x="90" y="53" width="80" height="87" fill="#C74634" rx="4"/>
      <text x="130" y="47" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">73%</text>
      <text x="130" y="158" fill="#94a3b8" font-size="11" text-anchor="middle">With Enablement</text>
      <!-- Bar: without enablement 58% -->
      <rect x="230" y="70" width="80" height="70" fill="#38bdf8" rx="4"/>
      <text x="270" y="64" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">58%</text>
      <text x="270" y="158" fill="#94a3b8" font-size="11" text-anchor="middle">Without Enablement</text>
      <!-- Delta annotation -->
      <text x="355" y="95" fill="#C74634" font-size="13" font-weight="bold">+15%</text>
    </svg>
  </div>

  <div class="card">
    <h2>Library Overview</h2>
    <div class="metrics">
      <div class="metric"><div class="val">30</div><div class="lbl">Total Assets</div></div>
      <div class="metric"><div class="val">73%</div><div class="lbl">Win Rate<br/>(enabled reps)</div></div>
      <div class="metric"><div class="val">+15pp</div><div class="lbl">Win Rate Lift</div></div>
    </div>
    <div class="assets" style="margin-top:1.2rem">
      <div class="asset-badge"><span>12</span>Battle Cards</div>
      <div class="asset-badge"><span>3</span>ROI Calculators</div>
      <div class="asset-badge"><span>5</span>Demo Scripts</div>
      <div class="asset-badge"><span>8</span>Objection Guides</div>
      <div class="asset-badge"><span>2</span>Case Studies</div>
    </div>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <ul class="endpoints">
      <li><span class="method">GET</span> /health &mdash; Service health and metadata</li>
      <li><span class="method">GET</span> / &mdash; This dashboard</li>
      <li><span class="method">GET</span> /sales/enablement/content &mdash; List all enablement assets</li>
      <li><span class="method">GET</span> /sales/enablement/usage &mdash; Asset usage and engagement stats</li>
    </ul>
  </div>

  <div class="footer">Oracle Confidential &mdash; OCI Robot Cloud &mdash; sales_enablement_library &mdash; port 10253</div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/sales/enablement/content")
    def enablement_content():
        """Stub: list all enablement assets in the library."""
        return JSONResponse({
            "total_assets": 30,
            "assets": [
                {"type": "battle_card", "count": 12, "latest": "OCI Robot Cloud vs AWS RoboMaker"},
                {"type": "roi_calculator", "count": 3, "latest": "Manufacturing ROI v2"},
                {"type": "demo_script", "count": 5, "latest": "GR00T Fine-Tuning Live Demo"},
                {"type": "objection_guide", "count": 8, "latest": "Why not open-source only?"},
                {"type": "case_study", "count": 2, "latest": "Foxconn Assembly Line Pilot"},
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/sales/enablement/usage")
    def enablement_usage():
        """Stub: asset usage and engagement statistics."""
        return JSONResponse({
            "win_rate_with_enablement": 0.73,
            "win_rate_without_enablement": 0.58,
            "win_rate_lift_pp": 15,
            "total_rep_sessions": 342,
            "most_used_asset": "OCI Robot Cloud vs AWS RoboMaker",
            "asset_views_30d": 1287,
            "avg_assets_used_per_deal": 4.2,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

else:
    # Fallback: stdlib http.server
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
