"""Series A Readiness Tracker — port 10173

Tracks and visualises Series A fundraise readiness across 7 key categories.
Overall readiness: 71%, target 100% by Series A close.
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

PORT = 10173
SERVICE_NAME = "series_a_readiness_tracker"

_START_TIME = time.time()

# 7-category readiness data
_READINESS_DATA = [
    {"label": "ARR",     "score": 65, "detail": "$2.1M ARR; target $3M"},
    {"label": "NRR",     "score": 82, "detail": "Net revenue retention 118%"},
    {"label": "Growth",  "score": 75, "detail": "MoM 8%; target 12%"},
    {"label": "Team",    "score": 60, "detail": "Need VP Sales + CFO"},
    {"label": "Product", "score": 90, "detail": "GR00T fine-tune + OCI infra"},
    {"label": "Market",  "score": 80, "detail": "$38B TAM, NVIDIA tailwind"},
    {"label": "Data Room","score": 94, "detail": "Cap table, IP, financials ready"},
]
_OVERALL_SCORE = 71

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Series A Readiness Tracker — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card h3 { color: #38bdf8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .val { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
    .card .unit { font-size: 0.8rem; color: #94a3b8; }
    .chart-container { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-container h2 { color: #f1f5f9; font-size: 1.1rem; margin-bottom: 1.25rem; }
    .table { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .table h2 { color: #f1f5f9; font-size: 1.1rem; margin-bottom: 0.75rem; }
    table { width: 100%; border-collapse: collapse; }
    th { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #334155; }
    td { color: #cbd5e1; font-size: 0.88rem; padding: 0.45rem 0.5rem; border-bottom: 1px solid #1e293b; }
    tr:last-child td { border-bottom: none; }
    .score-high { color: #38bdf8; font-weight: 600; }
    .score-mid  { color: #fbbf24; font-weight: 600; }
    .score-low  { color: #C74634; font-weight: 600; }
    .progress-bar { background: #0f172a; border-radius: 4px; height: 8px; margin-top: 0.3rem; }
    .progress-fill { height: 8px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Series A Readiness Tracker</h1>
  <p class="subtitle">7-category fundraise readiness dashboard &mdash; Port {PORT}</p>

  <div class="grid">
    <div class="card">
      <h3>Overall Readiness</h3>
      <div class="val">71%</div>
      <div class="unit">target 100% at close</div>
    </div>
    <div class="card">
      <h3>Target Close</h3>
      <div class="val">Q3 2026</div>
      <div class="unit">Series A round</div>
    </div>
    <div class="card">
      <h3>Top Category</h3>
      <div class="val">Data Room</div>
      <div class="unit">94% ready</div>
    </div>
    <div class="card">
      <h3>Gap Category</h3>
      <div class="val">Team</div>
      <div class="unit">60% — need VP Sales + CFO</div>
    </div>
  </div>

  <div class="chart-container">
    <h2>Readiness by Category</h2>
    <svg viewBox="0 0 640 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:640px;display:block;">
      <!-- Y axis -->
      <line x1="72" y1="10" x2="72" y2="185" stroke="#334155" stroke-width="1"/>
      <!-- X axis -->
      <line x1="72" y1="185" x2="630" y2="185" stroke="#334155" stroke-width="1"/>

      <!-- Grid lines (25%, 50%, 75%, 100%) -->
      <line x1="72" y1="10"  x2="630" y2="10"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="72" y1="53"  x2="630" y2="53"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="72" y1="97"  x2="630" y2="97"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="72" y1="141" x2="630" y2="141" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>

      <!-- Y labels -->
      <text x="68" y="188" fill="#64748b" font-size="10" text-anchor="end">0%</text>
      <text x="68" y="144" fill="#64748b" font-size="10" text-anchor="end">25%</text>
      <text x="68" y="100" fill="#64748b" font-size="10" text-anchor="end">50%</text>
      <text x="68" y="56"  fill="#64748b" font-size="10" text-anchor="end">75%</text>
      <text x="68" y="14"  fill="#64748b" font-size="10" text-anchor="end">100%</text>

      <!-- Bars: each bar width=52, gap=10, start x=82 -->
      <!-- scale: height = score/100 * 175 -->

      <!-- ARR 65% → 113.75 -->
      <rect x="82"  y="71"  width="52" height="114" fill="#fbbf24" rx="3"/>
      <text x="108" y="67"  fill="#fbbf24" font-size="10" text-anchor="middle">65%</text>
      <text x="108" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">ARR</text>

      <!-- NRR 82% → 143.5 -->
      <rect x="144" y="41"  width="52" height="144" fill="#38bdf8" rx="3"/>
      <text x="170" y="37"  fill="#38bdf8" font-size="10" text-anchor="middle">82%</text>
      <text x="170" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">NRR</text>

      <!-- Growth 75% → 131.25 -->
      <rect x="206" y="54"  width="52" height="131" fill="#fbbf24" rx="3"/>
      <text x="232" y="50"  fill="#fbbf24" font-size="10" text-anchor="middle">75%</text>
      <text x="232" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">Growth</text>

      <!-- Team 60% → 105 -->
      <rect x="268" y="80"  width="52" height="105" fill="#C74634" rx="3"/>
      <text x="294" y="76"  fill="#C74634" font-size="10" text-anchor="middle">60%</text>
      <text x="294" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">Team</text>

      <!-- Product 90% → 157.5 -->
      <rect x="330" y="27"  width="52" height="158" fill="#38bdf8" rx="3"/>
      <text x="356" y="23"  fill="#38bdf8" font-size="10" text-anchor="middle">90%</text>
      <text x="356" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">Product</text>

      <!-- Market 80% → 140 -->
      <rect x="392" y="45"  width="52" height="140" fill="#38bdf8" rx="3"/>
      <text x="418" y="41"  fill="#38bdf8" font-size="10" text-anchor="middle">80%</text>
      <text x="418" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">Market</text>

      <!-- Data Room 94% → 164.5 -->
      <rect x="454" y="20"  width="52" height="165" fill="#38bdf8" rx="3"/>
      <text x="480" y="16"  fill="#38bdf8" font-size="10" text-anchor="middle">94%</text>
      <text x="480" y="202" fill="#94a3b8" font-size="9"  text-anchor="middle">Data Room</text>
    </svg>
  </div>

  <div class="table">
    <h2>Category Details</h2>
    <table>
      <thead>
        <tr><th>Category</th><th>Score</th><th>Detail</th></tr>
      </thead>
      <tbody>
        <tr><td>ARR</td><td class="score-mid">65%</td><td>$2.1M ARR; target $3M</td></tr>
        <tr><td>NRR</td><td class="score-high">82%</td><td>Net revenue retention 118%</td></tr>
        <tr><td>Growth</td><td class="score-mid">75%</td><td>MoM 8%; target 12%</td></tr>
        <tr><td>Team</td><td class="score-low">60%</td><td>Need VP Sales + CFO</td></tr>
        <tr><td>Product</td><td class="score-high">90%</td><td>GR00T fine-tune + OCI infra</td></tr>
        <tr><td>Market</td><td class="score-high">80%</td><td>$38B TAM, NVIDIA tailwind</td></tr>
        <tr><td>Data Room</td><td class="score-high">94%</td><td>Cap table, IP, financials ready</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Series A Readiness Tracker",
        description="Series A fundraise readiness tracking across 7 categories",
        version="1.0.0",
    )

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/fundraise/series_a_readiness")
    async def series_a_readiness():
        """Return current Series A readiness scores for all 7 categories."""
        return JSONResponse({
            "status": "ok",
            "overall_score_pct": _OVERALL_SCORE,
            "target_pct": 100,
            "target_close": "Q3 2026",
            "categories": _READINESS_DATA,
            "gap_to_target_pct": 100 - _OVERALL_SCORE,
            "mock": True,
        })

    @app.post("/fundraise/update_metric")
    async def update_metric(payload: dict = None):
        """Update a readiness metric for a given category."""
        category = (payload or {}).get("category", "unknown")
        score = (payload or {}).get("score", None)
        return JSONResponse({
            "status": "ok",
            "updated_category": category,
            "new_score": score,
            "message": f"Metric '{category}' acknowledged (mock — no persistence).",
            "mock": True,
        })

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # suppress default logs
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({
                    "status": "ok",
                    "port": PORT,
                    "service": SERVICE_NAME,
                    "uptime_seconds": round(time.time() - _START_TIME, 1),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        import socketserver
        print(f"[{SERVICE_NAME}] FastAPI not available — using stdlib HTTP server on port {PORT}")
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            httpd.serve_forever()
