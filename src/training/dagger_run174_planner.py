"""DAgger Run 174 Planner — batch active DAgger scheduling service."""

import json
import datetime

PORT = 10234
SERVICE_NAME = "dagger_run174_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _has_fastapi = True
except ImportError:
    _has_fastapi = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run 174 Planner</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    h2 { color: #38bdf8; margin-top: 2rem; }
    .badge { display: inline-block; background: #1e293b; border: 1px solid #38bdf8; color: #38bdf8;
             border-radius: 4px; padding: 0.2rem 0.6rem; font-size: 0.8rem; margin-left: 0.5rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem 1.5rem; margin: 1rem 0; }
    .metric { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.25rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
    .endpoint { background: #0f172a; border-left: 3px solid #C74634; padding: 0.5rem 1rem;
                font-family: monospace; font-size: 0.9rem; margin: 0.4rem 0; border-radius: 0 4px 4px 0; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>DAgger Run 174 Planner <span class="badge">port 10234</span></h1>
  <p style="color:#94a3b8;">Batch active DAgger — schedule 1 hr expert session per week, 20 queries per batch.</p>

  <h2>Success Rate Comparison</h2>
  <div class="card">
    <svg width="480" height="220" viewBox="0 0 480 220" xmlns="http://www.w3.org/2000/svg">
      <!-- Y-axis -->
      <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- X-axis -->
      <line x1="60" y1="180" x2="450" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="55" y="180" text-anchor="end" fill="#94a3b8" font-size="11">0%</text>
      <text x="55" y="135" text-anchor="end" fill="#94a3b8" font-size="11">25%</text>
      <text x="55" y="90" text-anchor="end" fill="#94a3b8" font-size="11">50%</text>
      <text x="55" y="45" text-anchor="end" fill="#94a3b8" font-size="11">75%</text>
      <text x="55" y="12" text-anchor="end" fill="#94a3b8" font-size="11">100%</text>
      <!-- Gridlines -->
      <line x1="60" y1="135" x2="450" y2="135" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="90" x2="450" y2="90" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="45" x2="450" y2="45" stroke="#1e293b" stroke-width="1"/>
      <!-- Bar: Batch Active DAgger 93% -->
      <rect x="110" y="{ba_y}" width="100" height="{ba_h}" fill="#38bdf8" rx="3"/>
      <text x="160" y="{ba_label}" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="bold">93%</text>
      <text x="160" y="200" text-anchor="middle" fill="#94a3b8" font-size="11">Batch Active</text>
      <text x="160" y="213" text-anchor="middle" fill="#64748b" font-size="10">(5 sessions × 20)</text>
      <!-- Bar: Continuous DAgger 91% -->
      <rect x="270" y="{co_y}" width="100" height="{co_h}" fill="#C74634" rx="3"/>
      <text x="320" y="{co_label}" text-anchor="middle" fill="#C74634" font-size="12" font-weight="bold">91%</text>
      <text x="320" y="200" text-anchor="middle" fill="#94a3b8" font-size="11">Continuous</text>
      <text x="320" y="213" text-anchor="middle" fill="#64748b" font-size="10">(100 queries)</text>
    </svg>
  </div>

  <h2>Key Metrics</h2>
  <div class="grid">
    <div class="card">
      <div class="metric">93%</div>
      <div class="label">Batch Active SR (run174)</div>
    </div>
    <div class="card">
      <div class="metric">1 hr/wk</div>
      <div class="label">Scheduled expert load</div>
    </div>
    <div class="card">
      <div class="metric">20</div>
      <div class="label">Queries per batch</div>
    </div>
    <div class="card">
      <div class="metric">5</div>
      <div class="label">Expert sessions (total)</div>
    </div>
  </div>

  <h2>API Endpoints</h2>
  <div class="card">
    <div class="endpoint">GET /health</div>
    <div class="endpoint">GET /dagger/run174/plan</div>
    <div class="endpoint">GET /dagger/run174/status</div>
  </div>
</body>
</html>
""".replace("{ba_y}", str(180 - int(170 * 0.93))).replace("{ba_h}", str(int(170 * 0.93))) \
   .replace("{ba_label}", str(180 - int(170 * 0.93) - 5)) \
   .replace("{co_y}", str(180 - int(170 * 0.91))).replace("{co_h}", str(int(170 * 0.91))) \
   .replace("{co_label}", str(180 - int(170 * 0.91) - 5))


if _has_fastapi:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/dagger/run174/plan")
    async def get_plan():
        return JSONResponse({
            "run_id": "run174",
            "strategy": "batch_active",
            "batch_size": 20,
            "schedule": "weekly",
            "session_duration_hr": 1,
            "total_sessions": 5,
            "total_corrections": 100,
            "next_session": "2026-04-06T14:00:00Z",
            "cadence": "Every Monday 14:00 UTC",
        })

    @app.get("/dagger/run174/status")
    async def get_status():
        return JSONResponse({
            "run_id": "run174",
            "status": "active",
            "sessions_completed": 5,
            "success_rate_batch_active": 0.93,
            "success_rate_continuous_baseline": 0.91,
            "improvement_pct": 2.2,
            "last_session": "2026-03-30T14:00:00Z",
            "expert_load_hr_per_week": 1,
        })

else:
    # Fallback: stdlib HTTP server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if _has_fastapi:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
