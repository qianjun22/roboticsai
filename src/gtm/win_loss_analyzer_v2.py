"""Win/Loss Analyzer v2 — port 10209

Systematic win/loss interview analysis with ML-based pattern extraction.
Identifies deal-winning factors and loss patterns across the sales pipeline.
"""

import json
from datetime import datetime

PORT = 10209
SERVICE_NAME = "win_loss_analyzer_v2"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Win/Loss Analyzer v2 — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #C74634; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 1.6rem; font-weight: bold; color: #f1f5f9; }
    .card .unit { font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem; }
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }
    @media (max-width: 700px) { .charts { grid-template-columns: 1fr; } }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .chart-section h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.05rem; }
    .endpoints { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .endpoints h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .endpoint { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .endpoint:last-child { border-bottom: none; }
    .method { background: #0369a1; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; min-width: 45px; text-align: center; }
    .path { color: #38bdf8; font-family: monospace; font-size: 0.85rem; }
    .desc { color: #94a3b8; font-size: 0.85rem; margin-left: auto; }
  </style>
</head>
<body>
  <h1>Win / Loss Analyzer v2</h1>
  <p class="subtitle">OCI Robot Cloud — Port 10209 &nbsp;|&nbsp; ML-based pattern extraction from deal interviews</p>

  <div class="grid">
    <div class="card">
      <h3>Top Win Factor</h3>
      <div class="value">Price</div>
      <div class="unit">87% of win interviews</div>
    </div>
    <div class="card">
      <h3>Win Rate</h3>
      <div class="value">61%</div>
      <div class="unit">deals closed YTD</div>
    </div>
    <div class="card">
      <h3>Top Loss Reason</h3>
      <div class="value">Cases</div>
      <div class="unit">45% cite missing case studies</div>
    </div>
    <div class="card">
      <h3>Interviews Analyzed</h3>
      <div class="value">148</div>
      <div class="unit">Q1 2026 pipeline</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-section">
      <h2>Win Factors</h2>
      <svg viewBox="0 0 280 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
        <!-- Y gridlines + labels -->
        <text x="36" y="16" fill="#94a3b8" font-size="9" text-anchor="end">100%</text>
        <text x="36" y="52" fill="#94a3b8" font-size="9" text-anchor="end">75%</text>
        <text x="36" y="88" fill="#94a3b8" font-size="9" text-anchor="end">50%</text>
        <text x="36" y="124" fill="#94a3b8" font-size="9" text-anchor="end">25%</text>
        <line x1="40" y1="12" x2="270" y2="12" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="48" x2="270" y2="48" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="84" x2="270" y2="84" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="120" x2="270" y2="120" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="156" x2="270" y2="156" stroke="#475569" stroke-width="1.5" />
        <!-- Price 87% => h=133 -->
        <rect x="50" y="23" width="50" height="133" fill="#C74634" rx="2" />
        <text x="75" y="17" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">87%</text>
        <text x="75" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Price</text>
        <!-- NVIDIA-native 73% => h=111 -->
        <rect x="120" y="45" width="50" height="111" fill="#0369a1" rx="2" />
        <text x="145" y="39" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">73%</text>
        <text x="145" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">NVIDIA-native</text>
        <!-- Jun responsiveness 61% => h=93 -->
        <rect x="190" y="63" width="50" height="93" fill="#38bdf8" rx="2" />
        <text x="215" y="57" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">61%</text>
        <text x="215" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Jun resp.</text>
      </svg>
    </div>

    <div class="chart-section">
      <h2>Loss Patterns</h2>
      <svg viewBox="0 0 280 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
        <!-- Y gridlines + labels -->
        <text x="36" y="16" fill="#94a3b8" font-size="9" text-anchor="end">50%</text>
        <text x="36" y="52" fill="#94a3b8" font-size="9" text-anchor="end">37%</text>
        <text x="36" y="88" fill="#94a3b8" font-size="9" text-anchor="end">25%</text>
        <text x="36" y="124" fill="#94a3b8" font-size="9" text-anchor="end">12%</text>
        <line x1="40" y1="12" x2="270" y2="12" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="48" x2="270" y2="48" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="84" x2="270" y2="84" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="120" x2="270" y2="120" stroke="#334155" stroke-width="1" />
        <line x1="40" y1="156" x2="270" y2="156" stroke="#475569" stroke-width="1.5" />
        <!-- Case studies 45% => scale: 156px=50%, h=139 -->
        <rect x="45" y="17" width="38" height="139" fill="#7c3aed" rx="2" />
        <text x="64" y="11" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">45%</text>
        <text x="64" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Cases</text>
        <!-- Need on-prem 38% => h=117 -->
        <rect x="100" y="39" width="38" height="117" fill="#C74634" rx="2" />
        <text x="119" y="33" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">38%</text>
        <text x="119" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">On-prem</text>
        <!-- Contract complexity 31% => h=95 -->
        <rect x="155" y="61" width="38" height="95" fill="#0369a1" rx="2" />
        <text x="174" y="55" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">31%</text>
        <text x="174" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Contract</text>
        <!-- Team size 27% => h=83 -->
        <rect x="210" y="73" width="38" height="83" fill="#38bdf8" rx="2" />
        <text x="229" y="67" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="bold">27%</text>
        <text x="229" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Team size</text>
      </svg>
    </div>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="endpoint">
      <span class="method">GET</span>
      <span class="path">/health</span>
      <span class="desc">Service health + status</span>
    </div>
    <div class="endpoint">
      <span class="method">GET</span>
      <span class="path">/</span>
      <span class="desc">This dashboard</span>
    </div>
    <div class="endpoint">
      <span class="method">GET</span>
      <span class="path">/sales/win_loss/v2/analysis</span>
      <span class="desc">Aggregated win/loss analysis report</span>
    </div>
    <div class="endpoint">
      <span class="method">GET</span>
      <span class="path">/sales/win_loss/v2/patterns</span>
      <span class="desc">ML-extracted win and loss patterns</span>
    </div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title=SERVICE_NAME,
        description="Win/loss interview analysis with ML-based pattern extraction",
        version="2.0.0",
    )

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
        return HTML_DASHBOARD

    @app.get("/sales/win_loss/v2/analysis")
    def win_loss_analysis(quarter: str = "Q1-2026"):
        """Return aggregated win/loss analysis report (stub)."""
        return JSONResponse({
            "quarter": quarter,
            "interviews_analyzed": 148,
            "win_rate": 0.61,
            "deals_won": 90,
            "deals_lost": 58,
            "top_win_factor": "price",
            "top_loss_factor": "missing_case_studies",
            "win_factors": [
                {"factor": "price", "frequency": 0.87},
                {"factor": "nvidia_native_integration", "frequency": 0.73},
                {"factor": "jun_responsiveness", "frequency": 0.61},
            ],
            "loss_patterns": [
                {"pattern": "missing_case_studies", "frequency": 0.45},
                {"pattern": "need_on_premise", "frequency": 0.38},
                {"pattern": "contract_complexity", "frequency": 0.31},
                {"pattern": "team_size_concerns", "frequency": 0.27},
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/sales/win_loss/v2/patterns")
    def win_loss_patterns(min_frequency: float = 0.0):
        """Return ML-extracted patterns above threshold (stub)."""
        patterns = [
            {"type": "win", "pattern": "price", "frequency": 0.87, "confidence": 0.92},
            {"type": "win", "pattern": "nvidia_native_integration", "frequency": 0.73, "confidence": 0.88},
            {"type": "win", "pattern": "jun_responsiveness", "frequency": 0.61, "confidence": 0.84},
            {"type": "loss", "pattern": "missing_case_studies", "frequency": 0.45, "confidence": 0.91},
            {"type": "loss", "pattern": "need_on_premise", "frequency": 0.38, "confidence": 0.87},
            {"type": "loss", "pattern": "contract_complexity", "frequency": 0.31, "confidence": 0.79},
            {"type": "loss", "pattern": "team_size_concerns", "frequency": 0.27, "confidence": 0.75},
        ]
        filtered = [p for p in patterns if p["frequency"] >= min_frequency]
        return JSONResponse({
            "patterns": filtered,
            "count": len(filtered),
            "min_frequency_filter": min_frequency,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
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
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
            httpd.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
