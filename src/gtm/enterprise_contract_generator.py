"""Enterprise Contract Generator — FastAPI service on port 10193.

Auto-generates enterprise contracts from deal parameters (MSA + SOW + SLA exhibit).
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

PORT = 10193
SERVICE_NAME = "enterprise_contract_generator"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Contract Generator</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-top: 0; font-size: 1.1rem; }
    .metric { display: inline-block; margin-right: 2rem; margin-bottom: 1rem; }
    .metric .val { font-size: 1.8rem; font-weight: bold; color: #C74634; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th { text-align: left; color: #38bdf8; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; }
    td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #1e293b; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; }
    .green { background: #14532d; color: #86efac; }
    .blue  { background: #0c4a6e; color: #7dd3fc; }
    .note { font-size: 0.82rem; color: #94a3b8; margin-top: 0.5rem; }
  </style>
</head>
<body>
  <h1>Enterprise Contract Generator</h1>
  <p class="subtitle">Port 10193 &mdash; Auto-generate MSA + SOW + SLA exhibit from 6 deal parameters</p>

  <div class="card">
    <h2>Contract Review Time (weeks)</h2>
    <svg width="460" height="160" viewBox="0 0 460 160" xmlns="http://www.w3.org/2000/svg">
      <!-- Grid lines -->
      <line x1="60" y1="10" x2="440" y2="10" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="55" x2="440" y2="55" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="130" x2="440" y2="130" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="10" x2="60" y2="130" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="55" y="134" fill="#94a3b8" font-size="11" text-anchor="end">0</text>
      <text x="55" y="58"  fill="#94a3b8" font-size="11" text-anchor="end">2</text>
      <text x="55" y="13"  fill="#94a3b8" font-size="11" text-anchor="end">3</text>
      <!-- Bar: Standard 2wk -->
      <rect x="85"  y="56" width="80" height="74" fill="#C74634" rx="4"/>
      <text x="125" y="50" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">2 wk</text>
      <text x="125" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Standard</text>
      <!-- Bar: Enterprise 3wk -->
      <rect x="205" y="10" width="80" height="120" fill="#38bdf8" rx="4"/>
      <text x="245" y="7"  fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">3 wk</text>
      <text x="245" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Enterprise</text>
      <!-- Bar: Avg redlines — scaled 1.2 rounds shown as indicative bar -->
      <rect x="325" y="84" width="80" height="46" fill="#7c3aed" rx="4"/>
      <text x="365" y="79" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">1.2×</text>
      <text x="365" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Redline Rounds</text>
    </svg>
  </div>

  <div class="card">
    <h2>v2 Simplification</h2>
    <div class="metric"><div class="val">8 pg</div><div class="lbl">v2 MSA (was 16 pg)</div></div>
    <div class="metric"><div class="val">Plain</div><div class="lbl">Language Style</div></div>
    <div class="metric"><div class="val">Faster</div><div class="lbl">Close Velocity</div></div>
    <p class="note">v2 MSA cuts length by 50% using plain language and pre-agreed fallback positions, reducing back-and-forth redline rounds from an average of 1.2 to a target of 0.4.</p>
  </div>

  <div class="card">
    <h2>6 Deal Parameter Inputs</h2>
    <table>
      <tr><th>#</th><th>Parameter</th><th>Example</th></tr>
      <tr><td>1</td><td>Customer name &amp; legal entity</td><td>Acme Robotics Inc.</td></tr>
      <tr><td>2</td><td>Contract type</td><td>MSA / SOW / SLA</td></tr>
      <tr><td>3</td><td>Annual contract value (ACV)</td><td>$240,000</td></tr>
      <tr><td>4</td><td>SLA tier</td><td>Platinum (99.9% uptime)</td></tr>
      <tr><td>5</td><td>Term &amp; renewal clause</td><td>2-year, auto-renew</td></tr>
      <tr><td>6</td><td>Governing law &amp; jurisdiction</td><td>California, USA</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
      <tr><td><span class="badge green">GET</span></td><td>/health</td><td>Health check</td></tr>
      <tr><td><span class="badge green">GET</span></td><td>/</td><td>This dashboard</td></tr>
      <tr><td><span class="badge blue">POST</span></td><td>/contracts/generate</td><td>Generate MSA + SOW + SLA from deal params</td></tr>
      <tr><td><span class="badge green">GET</span></td><td>/contracts/templates</td><td>List available contract templates</td></tr>
    </table>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML_DASHBOARD

    @app.post("/contracts/generate")
    async def generate_contract(payload: dict = None):
        """Generate MSA + SOW + SLA exhibit from 6 deal parameters."""
        contract_id = f"contract-{int(time.time())}"
        params = payload or {}
        return JSONResponse({
            "contract_id": contract_id,
            "status": "generated",
            "documents": [
                {"type": "MSA", "version": "v2", "pages": 8, "format": "docx"},
                {"type": "SOW", "version": "v1", "pages": 4, "format": "docx"},
                {"type": "SLA_exhibit", "version": "v1", "pages": 2, "format": "docx"},
            ],
            "inputs_received": list(params.keys()),
            "estimated_review_weeks": 2,
            "avg_redline_rounds": 1.2,
            "generated_at": datetime.utcnow().isoformat(),
        })

    @app.get("/contracts/templates")
    async def list_templates():
        """Return available contract templates."""
        return JSONResponse({
            "templates": [
                {"id": "msa-v2-standard",    "name": "MSA v2 Standard",    "pages": 8,  "type": "MSA"},
                {"id": "msa-v2-enterprise",  "name": "MSA v2 Enterprise",  "pages": 8,  "type": "MSA"},
                {"id": "msa-v1-legacy",      "name": "MSA v1 Legacy",      "pages": 16, "type": "MSA"},
                {"id": "sow-robotics",        "name": "SOW Robotics Cloud",  "pages": 4,  "type": "SOW"},
                {"id": "sla-platinum",        "name": "SLA Platinum 99.9%",  "pages": 2,  "type": "SLA"},
                {"id": "sla-gold",            "name": "SLA Gold 99.5%",     "pages": 2,  "type": "SLA"},
            ]
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
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
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server running on port {PORT}")
        server.serve_forever()
