"""Competitive Win Rate Optimizer — optimize win rates against specific competitors.

FastAPI service on port 10239.
Tracks win rate by competitor and models the impact of improvement levers
(NVIDIA badge, customer case studies, TCO calculator).
"""

PORT = 10239
SERVICE_NAME = "competitive_win_rate_optimizer"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Competitive Win Rate Optimizer</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1   { color: #C74634; margin-bottom: 0.25rem; }
    h2   { color: #38bdf8; font-size: 1rem; font-weight: 400; margin-top: 0; }
    .card { background: #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin: 1rem 0; }
    .badge { display: inline-block; background: #C74634; color: #fff;
             border-radius: 0.4rem; padding: 0.15rem 0.6rem; font-size: 0.8rem; }
    table  { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; font-size: 0.9rem; }
    th     { color: #38bdf8; }
    .bar-label { font-size: 0.75rem; fill: #94a3b8; }
    .bar-val   { font-size: 0.78rem; fill: #e2e8f0; font-weight: bold; }
    .lever     { font-size: 0.78rem; fill: #38bdf8; font-weight: bold; }
  </style>
</head>
<body>
  <h1>Competitive Win Rate Optimizer</h1>
  <h2>Win rate analysis &amp; improvement levers &mdash; port 10239 &nbsp;<span class="badge">LIVE</span></h2>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Win Rate by Competitor</h3>
    <svg viewBox="0 0 480 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px">
      <!-- grid lines -->
      <line x1="60" y1="20" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="180" x2="460" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- y-axis ticks -->
      <text x="52" y="184" text-anchor="end" class="bar-label">0%</text>
      <text x="52" y="137" text-anchor="end" class="bar-label">50%</text>
      <text x="52" y="90"  text-anchor="end" class="bar-label">75%</text>
      <text x="52" y="43"  text-anchor="end" class="bar-label">100%</text>
      <line x1="60" y1="136" x2="460" y2="136" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="88"  x2="460" y2="88"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- bar 1: vs AWS 81%, height = 81/100 * 160 = 129.6 -->
      <rect x="80"  y="50.4" width="80" height="129.6" rx="4" fill="#38bdf8"/>
      <text x="120" y="44"   text-anchor="middle" class="bar-val">81%</text>
      <text x="120" y="197"  text-anchor="middle" class="bar-label">vs AWS</text>
      <!-- bar 2: vs Covariant 74%, height = 118.4 -->
      <rect x="195" y="61.6" width="80" height="118.4" rx="4" fill="#C74634" opacity="0.90"/>
      <text x="235" y="56"   text-anchor="middle" class="bar-val">74%</text>
      <text x="235" y="197"  text-anchor="middle" class="bar-label">vs Covariant</text>
      <!-- bar 3: vs PI Research 68%, height = 108.8 -->
      <rect x="310" y="71.2" width="80" height="108.8" rx="4" fill="#C74634" opacity="0.75"/>
      <text x="350" y="65"   text-anchor="middle" class="bar-val">68%</text>
      <text x="350" y="197"  text-anchor="middle" class="bar-label">vs PI Research</text>
    </svg>
  </div>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Win Rate Improvement Levers</h3>
    <svg viewBox="0 0 480 140" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px">
      <!-- horizontal bar chart -->
      <!-- label column -->
      <text x="130" y="40"  text-anchor="end" class="bar-label">NVIDIA Badge</text>
      <text x="130" y="80"  text-anchor="end" class="bar-label">Case Study</text>
      <text x="130" y="120" text-anchor="end" class="bar-label">TCO Calculator</text>
      <!-- bars: scale 1px = 2% lift, max lever = 12% -->
      <!-- NVIDIA badge +12% -->
      <rect x="140" y="24" width="120" height="22" rx="3" fill="#38bdf8"/>
      <text x="268" y="39" class="lever">+12%</text>
      <!-- Case study +9% -->
      <rect x="140" y="64" width="90"  height="22" rx="3" fill="#38bdf8" opacity="0.85"/>
      <text x="238" y="79" class="lever">+9%</text>
      <!-- TCO calculator +7% -->
      <rect x="140" y="104" width="70" height="22" rx="3" fill="#C74634" opacity="0.90"/>
      <text x="218" y="119" class="lever">+7%</text>
    </svg>
  </div>

  <div class="card" style="font-size:0.85rem;color:#64748b">
    Endpoints: <code>GET /health</code> &nbsp;
    <code>GET /sales/win_rate/by_competitor</code> &nbsp;
    <code>GET /sales/win_rate/forecast</code>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

def _mock_by_competitor():
    return {
        "as_of": "2026-Q1",
        "competitors": [
            {"name": "AWS",         "win_rate": 0.81, "deals_tracked": 142},
            {"name": "Covariant",   "win_rate": 0.74, "deals_tracked": 87},
            {"name": "PI Research", "win_rate": 0.68, "deals_tracked": 53},
        ],
        "levers": [
            {"name": "NVIDIA badge",   "win_rate_lift": 0.12},
            {"name": "Case study",     "win_rate_lift": 0.09},
            {"name": "TCO calculator", "win_rate_lift": 0.07},
        ],
    }


def _mock_forecast():
    return {
        "quarter": "2026-Q2",
        "baseline_win_rate": 0.74,
        "forecast_win_rate_all_levers": 0.86,
        "levers_applied": ["NVIDIA badge", "Case study", "TCO calculator"],
        "confidence": "medium",
        "assumptions": [
            "Levers assumed independent; actual uplift may vary.",
            "Based on 282 historical deals across 3 competitors.",
        ],
    }


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _HTML

    @app.get("/sales/win_rate/by_competitor")
    def win_rate_by_competitor():
        return JSONResponse(_mock_by_competitor())

    @app.get("/sales/win_rate/forecast")
    def win_rate_forecast():
        return JSONResponse(_mock_forecast())

else:
    # ---------------------------------------------------------------------------
    # Stdlib fallback
    # ---------------------------------------------------------------------------
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code, body, content_type="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
            elif self.path == "/":
                self._send(200, _HTML, "text/html; charset=utf-8")
            elif self.path == "/sales/win_rate/by_competitor":
                self._send(200, json.dumps(_mock_by_competitor()))
            elif self.path == "/sales/win_rate/forecast":
                self._send(200, json.dumps(_mock_forecast()))
            else:
                self._send(404, json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] fastapi not found — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
