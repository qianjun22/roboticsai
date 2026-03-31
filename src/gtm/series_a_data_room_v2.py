"""Series A Data Room v2 — fully populated, investor-ready.

Port 10211. 7 sections: legal, financial, product, technical, customers,
team, IP. Overall completeness 87%. v2 additions: Machina case study,
Q1 actuals, PRODUCTION.md, security audit, cap table v3.
"""

PORT = 10211
SERVICE_NAME = "series_a_data_room_v2"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    SECTION_DATA = [
        {"name": "Technical",  "pct": 96},
        {"name": "Legal",      "pct": 94},
        {"name": "Product",    "pct": 91},
        {"name": "Customers",  "pct": 89},
        {"name": "Financial",  "pct": 87},
        {"name": "IP",         "pct": 83},
        {"name": "Team",       "pct": 72},
    ]

    DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Series A Data Room v2</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
    header { background: #C74634; padding: 1.2rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { margin: 0; font-size: 1.5rem; color: #fff; }
    header span { font-size: 0.85rem; color: #fde8e4; }
    main { padding: 2rem; max-width: 900px; margin: auto; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { margin-top: 0; color: #38bdf8; font-size: 1.1rem; }
    .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.78rem; margin-left: 8px; }
    .badge-green { display: inline-block; background: #059669; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.78rem; margin-left: 8px; }
    .metric { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #334155; }
    .metric:last-child { border-bottom: none; }
    .metric .val { color: #38bdf8; font-weight: bold; }
    svg text { font-family: 'Segoe UI', sans-serif; }
    footer { text-align: center; padding: 1.5rem; color: #475569; font-size: 0.8rem; }
  </style>
</head>
<body>
  <header>
    <h1>Series A Data Room v2</h1>
    <span>Investor-Ready &mdash; 7 Sections &mdash; Port 10211</span>
  </header>
  <main>
    <div class="card">
      <h2>Section Completeness <span class="badge-green">87% Overall</span></h2>
      <svg width="100%" viewBox="0 0 520 240" xmlns="http://www.w3.org/2000/svg">
        <!-- axes -->
        <line x1="70" y1="10" x2="70" y2="180" stroke="#475569" stroke-width="1.5"/>
        <line x1="70" y1="180" x2="510" y2="180" stroke="#475569" stroke-width="1.5"/>
        <!-- y-axis labels (0,25,50,75,100) -->
        <text x="62" y="184" text-anchor="end" fill="#94a3b8" font-size="10">0</text>
        <text x="62" y="139" text-anchor="end" fill="#94a3b8" font-size="10">25</text>
        <text x="62" y="94" text-anchor="end" fill="#94a3b8" font-size="10">50</text>
        <text x="62" y="49" text-anchor="end" fill="#94a3b8" font-size="10">75</text>
        <text x="62" y="14" text-anchor="end" fill="#94a3b8" font-size="10">100</text>
        <!-- grid -->
        <line x1="70" y1="135" x2="510" y2="135" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
        <line x1="70" y1="90" x2="510" y2="90" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
        <line x1="70" y1="45" x2="510" y2="45" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
        <line x1="70" y1="10" x2="510" y2="10" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
        <!-- Technical 96% height=96/100*170=163.2 y=180-163=17 -->
        <rect x="80"  y="17"  width="45" height="163" fill="#38bdf8" rx="3"/>
        <text x="103" y="12" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">96%</text>
        <text x="103" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Technical</text>
        <!-- Legal 94% height=159.8 y=20 -->
        <rect x="140" y="20"  width="45" height="160" fill="#38bdf8" rx="3"/>
        <text x="163" y="15" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">94%</text>
        <text x="163" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Legal</text>
        <!-- Product 91% height=154.7 y=25 -->
        <rect x="200" y="25"  width="45" height="155" fill="#38bdf8" rx="3"/>
        <text x="223" y="20" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">91%</text>
        <text x="223" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Product</text>
        <!-- Customers 89% height=151.3 y=29 -->
        <rect x="260" y="29"  width="45" height="151" fill="#38bdf8" rx="3"/>
        <text x="283" y="24" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">89%</text>
        <text x="283" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Customers</text>
        <!-- Financial 87% height=147.9 y=32 -->
        <rect x="320" y="32"  width="45" height="148" fill="#38bdf8" rx="3"/>
        <text x="343" y="27" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">87%</text>
        <text x="343" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Financial</text>
        <!-- IP 83% height=141.1 y=39 -->
        <rect x="380" y="39"  width="45" height="141" fill="#C74634" rx="3"/>
        <text x="403" y="34" text-anchor="middle" fill="#fca5a5" font-size="10" font-weight="bold">83%</text>
        <text x="403" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">IP</text>
        <!-- Team 72% height=122.4 y=58 -->
        <rect x="440" y="58"  width="45" height="122" fill="#C74634" rx="3"/>
        <text x="463" y="53" text-anchor="middle" fill="#fca5a5" font-size="10" font-weight="bold">72%</text>
        <text x="463" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">Team</text>
        <!-- y-axis title -->
        <text x="14" y="100" text-anchor="middle" fill="#64748b" font-size="10" transform="rotate(-90 14 100)">Completeness %</text>
      </svg>
    </div>
    <div class="card">
      <h2>v2 Additions <span class="badge">New</span></h2>
      <div class="metric"><span>Machina Labs case study</span><span class="val">Customers +4%</span></div>
      <div class="metric"><span>Q1 actuals (revenue + burn)</span><span class="val">Financial +5%</span></div>
      <div class="metric"><span>PRODUCTION.md (deployment runbook)</span><span class="val">Technical +2%</span></div>
      <div class="metric"><span>Security audit report (SOC 2 prep)</span><span class="val">Technical +1%</span></div>
      <div class="metric"><span>Cap table v3 (post-seed round)</span><span class="val">Legal +3%</span></div>
    </div>
    <div class="card">
      <h2>Gaps Remaining</h2>
      <div class="metric"><span>Team: VP Sales hire in progress</span><span class="val">-28%</span></div>
      <div class="metric"><span>IP: Patent filings pending (3)</span><span class="val">-17%</span></div>
      <div class="metric"><span>Financial: 3-year model needs revision</span><span class="val">-13%</span></div>
    </div>
    <div class="card">
      <h2>Endpoints</h2>
      <div class="metric"><span>GET /health</span><span class="val">Service health</span></div>
      <div class="metric"><span>GET /fundraise/data_room/v2</span><span class="val">Full data room index</span></div>
      <div class="metric"><span>GET /fundraise/data_room/v2/gaps</span><span class="val">Remaining gaps</span></div>
    </div>
  </main>
  <footer>OCI Robot Cloud &mdash; Series A Data Room v2 &mdash; Port 10211</footer>
</body>
</html>
"""

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/fundraise/data_room/v2")
    async def data_room_v2():
        return JSONResponse({
            "version": "v2",
            "overall_completeness_pct": 87,
            "sections": [
                {"name": "legal",     "completeness_pct": 94},
                {"name": "financial", "completeness_pct": 87},
                {"name": "product",   "completeness_pct": 91},
                {"name": "technical", "completeness_pct": 96},
                {"name": "customers", "completeness_pct": 89},
                {"name": "team",      "completeness_pct": 72},
                {"name": "ip",        "completeness_pct": 83}
            ],
            "v2_additions": [
                "Machina Labs case study",
                "Q1 actuals",
                "PRODUCTION.md",
                "Security audit report",
                "Cap table v3"
            ],
            "investor_ready": True
        })

    @app.get("/fundraise/data_room/v2/gaps")
    async def data_room_v2_gaps():
        return JSONResponse({
            "version": "v2",
            "gaps": [
                {"section": "team",      "gap": "VP Sales hire in progress",           "impact_pct": 28},
                {"section": "ip",        "gap": "3 patent filings pending",             "impact_pct": 17},
                {"section": "financial", "gap": "3-year model needs revision",          "impact_pct": 13},
                {"section": "customers", "gap": "2 more reference customers needed",   "impact_pct": 11},
                {"section": "legal",     "gap": "GDPR DPA agreements outstanding",      "impact_pct":  6}
            ],
            "overall_gap_pct": 13
        })

else:
    # Fallback: stdlib HTTPServer
    import http.server
    import json
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        import socketserver
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving on port {PORT} (stdlib fallback)")
            httpd.serve_forever()
