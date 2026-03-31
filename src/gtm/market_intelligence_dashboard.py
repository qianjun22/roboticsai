"""Market Intelligence Dashboard — robotics AI TAM, competitive, funding, regulatory.

Port 10243
"""

PORT = 10243
SERVICE_NAME = "market_intelligence_dashboard"

import json
import datetime

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
  <title>Market Intelligence Dashboard — OCI Robot Cloud</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    h2 { color: #38bdf8; font-size: 1rem; font-weight: 400; margin-top: 0; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin: 1.5rem 0; }
    .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px;
             padding: 2px 10px; font-size: 0.8rem; margin-right: 6px; }
    .badge-blue { background: #38bdf8; color: #0f172a; }
    .badge-green { background: #4ade80; color: #0f172a; }
    .metric { display: inline-block; margin: 0.5rem 1rem 0.5rem 0; }
    .metric .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .metric .lbl { font-size: 0.78rem; color: #94a3b8; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th { color: #38bdf8; text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }
    td { padding: 6px 8px; border-bottom: 1px solid #1e293b; }
    .footer { color: #64748b; font-size: 0.78rem; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Market Intelligence Dashboard</h1>
  <h2>Robotics AI — TAM &bull; Competitive &bull; Funding &bull; Regulatory</h2>

  <div class="card">
    <span class="badge">Port 10243</span>
    <span class="badge badge-blue">Live Intel</span>
    <span class="badge badge-green">First-Mover OCI</span>
    <div style="margin-top:1rem">
      <div class="metric"><div class="val">$2.3B</div><div class="lbl">TAM 2025</div></div>
      <div class="metric"><div class="val">42%</div><div class="lbl">CAGR</div></div>
      <div class="metric"><div class="val">$7.8B</div><div class="lbl">TAM 2030</div></div>
      <div class="metric"><div class="val">$340M</div><div class="lbl">H2 2025 Funding</div></div>
    </div>
  </div>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Competitive Funding Landscape</h3>
    <svg viewBox="0 0 540 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:540px">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="185" stroke="#475569" stroke-width="1"/>
      <line x1="70" y1="185" x2="520" y2="185" stroke="#475569" stroke-width="1"/>
      <!-- y-axis labels (max ~$200M) -->
      <text x="60" y="189" fill="#94a3b8" font-size="11" text-anchor="end">$0</text>
      <text x="60" y="154" fill="#94a3b8" font-size="11" text-anchor="end">$50M</text>
      <text x="60" y="119" fill="#94a3b8" font-size="11" text-anchor="end">$100M</text>
      <text x="60" y="84" fill="#94a3b8" font-size="11" text-anchor="end">$150M</text>
      <text x="60" y="44" fill="#94a3b8" font-size="11" text-anchor="end">$200M</text>
      <!-- gridlines -->
      <line x1="70" y1="154" x2="520" y2="154" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="70" y1="119" x2="520" y2="119" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="70" y1="84" x2="520" y2="84" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="70" y1="44" x2="520" y2="44" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <!-- Covariant $167M: height = (167/200)*175 = 146.1, y = 185-146 = 39 -->
      <rect x="90" y="39" width="75" height="146" fill="#C74634" rx="3"/>
      <text x="127" y="34" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">$167M</text>
      <text x="127" y="202" fill="#e2e8f0" font-size="11" text-anchor="middle">Covariant</text>
      <!-- PI Research $80M: height = (80/200)*175 = 70, y = 185-70 = 115 -->
      <rect x="195" y="115" width="75" height="70" fill="#C74634" rx="3" opacity="0.75"/>
      <text x="232" y="110" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">$80M</text>
      <text x="232" y="202" fill="#e2e8f0" font-size="11" text-anchor="middle">PI Research</text>
      <!-- AWS $0 dedicated: height = 0, show minimal bar -->
      <rect x="300" y="181" width="75" height="4" fill="#64748b" rx="2"/>
      <text x="337" y="176" fill="#64748b" font-size="12" text-anchor="middle" font-weight="bold">$0</text>
      <text x="337" y="202" fill="#e2e8f0" font-size="11" text-anchor="middle">AWS</text>
      <!-- OCI first-mover: annotated differently -->
      <rect x="405" y="80" width="75" height="105" fill="#38bdf8" rx="3"/>
      <text x="442" y="75" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">First</text>
      <text x="442" y="88" fill="#0f172a" font-size="10" text-anchor="middle">Mover</text>
      <text x="442" y="202" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">OCI</text>
      <!-- legend -->
      <rect x="90" y="215" width="12" height="12" fill="#C74634" rx="2"/>
      <text x="106" y="226" fill="#94a3b8" font-size="11">Competitor funding</text>
      <rect x="260" y="215" width="12" height="12" fill="#38bdf8" rx="2"/>
      <text x="276" y="226" fill="#94a3b8" font-size="11">OCI (strategic position)</text>
    </svg>

    <table>
      <tr><th>Company</th><th>Funding</th><th>Focus</th><th>OCI Advantage</th></tr>
      <tr><td>Covariant</td><td style="color:#C74634">$167M</td><td>Warehouse pick &amp; place</td><td>Broader multi-task fine-tune</td></tr>
      <tr><td>PI Research</td><td style="color:#C74634">$80M</td><td>Humanoid manipulation</td><td>Cloud-scale SDG + EWC</td></tr>
      <tr><td>AWS</td><td style="color:#64748b">$0 dedicated</td><td>Generic ML infra</td><td>Robotics-first pipeline</td></tr>
      <tr><td style="color:#38bdf8">OCI Robot Cloud</td><td style="color:#38bdf8">First-mover</td><td>Full fine-tune + deploy stack</td><td style="color:#4ade80">Unique position</td></tr>
    </table>
  </div>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Market Signals — H2 2025</h3>
    <ul style="line-height:1.9">
      <li><strong style="color:#38bdf8">$340M</strong> total robotics AI funding in H2 2025 — fastest half-year on record</li>
      <li>TAM growing from <strong style="color:#38bdf8">$2.3B (2025)</strong> to <strong style="color:#38bdf8">$7.8B (2030)</strong> at 42% CAGR</li>
      <li>EU AI Act robotics provisions take effect Q3 2026 — OCI audit trail ready</li>
      <li>NIST robotics safety framework adoption accelerating among Fortune 500</li>
      <li>China export controls on humanoid components create Western cloud opportunity</li>
    </ul>
  </div>

  <div class="footer">OCI Robot Cloud &mdash; Market Intelligence Dashboard &mdash; Port 10243</div>
</body>
</html>
"""


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/market/intelligence")
    def market_intelligence():
        """Return mock robotics AI market intelligence snapshot."""
        return JSONResponse({
            "tam_2025_usd": 2_300_000_000,
            "tam_2030_usd": 7_800_000_000,
            "cagr_pct": 42.0,
            "h2_2025_funding_usd": 340_000_000,
            "competitors": [
                {"name": "Covariant", "funding_usd": 167_000_000, "focus": "warehouse pick & place"},
                {"name": "PI Research", "funding_usd": 80_000_000, "focus": "humanoid manipulation"},
                {"name": "AWS", "funding_usd": 0, "focus": "generic ML infra"},
            ],
            "oci_position": "first-mover",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/market/intelligence/alerts")
    def market_intelligence_alerts():
        """Return mock market intelligence alerts."""
        return JSONResponse({
            "alerts": [
                {"severity": "high", "category": "funding",
                 "message": "Covariant Series C rumored — potential $200M+ round Q2 2026"},
                {"severity": "medium", "category": "regulatory",
                 "message": "EU AI Act robotics provisions effective Q3 2026 — prepare audit trail"},
                {"severity": "medium", "category": "competitive",
                 "message": "AWS announced robotics ML templates — no fine-tune pipeline yet"},
                {"severity": "low", "category": "market",
                 "message": "Fortune 500 NIST robotics safety framework RFPs increasing 3x YoY"},
            ],
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
        })

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] stdlib fallback on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
