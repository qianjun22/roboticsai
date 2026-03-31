"""market_expansion_analyzer.py — Adjacent vertical market analysis (port 10035).

Analyzes expansion from manufacturing into logistics, healthcare, and
construction. Provides TAM data, readiness scores, GTM motions, and
sequenced expansion milestones.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10035

VERTICALS: dict[str, dict[str, Any]] = {
    "manufacturing": {
        "vertical": "manufacturing",
        "tam_usd": 2_300_000_000,
        "readiness": "GA",
        "gtm_motion": "Direct enterprise + OCI Marketplace",
        "timeline": "Now (Q1 2026)",
    },
    "logistics": {
        "vertical": "logistics",
        "tam_usd": 1_800_000_000,
        "readiness": "Beta",
        "gtm_motion": "3PL partnerships + system integrators",
        "timeline": "Q3 2026",
    },
    "healthcare": {
        "vertical": "healthcare",
        "tam_usd": 940_000_000,
        "readiness": "Alpha",
        "gtm_motion": "Hospital networks + FDA-cleared device channels",
        "timeline": "Q1 2027",
    },
    "construction": {
        "vertical": "construction",
        "tam_usd": 670_000_000,
        "readiness": "Research",
        "gtm_motion": "General contractor pilots + OEM agreements",
        "timeline": "Q3 2027",
    },
}

EXPANSION_SEQUENCE = {
    "current_vertical": "manufacturing",
    "next_vertical": "logistics",
    "sequence": ["manufacturing", "logistics", "healthcare", "construction"],
    "trigger_milestones": [
        {"from": "manufacturing", "to": "logistics", "trigger": "10 manufacturing customers, $5M ARR, 95%+ uptime SLA"},
        {"from": "logistics", "to": "healthcare", "trigger": "3PL pilot with Tier-1 3PL, autonomous cycle time <4s"},
        {"from": "healthcare", "to": "construction", "trigger": "FDA 510(k) clearance, 2 hospital network contracts"},
    ],
}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Expansion Analyzer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 1.25rem 1.5rem; border: 1px solid #334155; }}
  .card-label {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }}
  .card-value {{ font-size: 1.7rem; font-weight: 700; }}
  .card-sub {{ color: #64748b; font-size: 0.8rem; margin-top: 0.3rem; }}
  .red {{ color: #C74634; }}
  .blue {{ color: #38bdf8; }}
  .green {{ color: #34d399; }}
  .yellow {{ color: #fbbf24; }}
  .purple {{ color: #a78bfa; }}
  .section-title {{ color: #38bdf8; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }}
  .chart-container {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
  .badge-ga {{ background: #064e3b; color: #34d399; }}
  .badge-beta {{ background: #0c4a6e; color: #38bdf8; }}
  .badge-alpha {{ background: #451a03; color: #fbbf24; }}
  .badge-research {{ background: #1e1b4b; color: #a78bfa; }}
  .timeline {{ list-style: none; position: relative; padding-left: 1.5rem; }}
  .timeline::before {{ content: ''; position: absolute; left: 0.45rem; top: 0; bottom: 0; width: 2px; background: #334155; }}
  .timeline li {{ position: relative; margin-bottom: 1.25rem; padding-left: 1rem; }}
  .timeline li::before {{ content: ''; position: absolute; left: -1.1rem; top: 0.35rem; width: 10px; height: 10px; border-radius: 50%; background: #38bdf8; border: 2px solid #0f172a; }}
  .timeline li.active::before {{ background: #C74634; }}
  .timeline .tl-title {{ font-weight: 600; font-size: 0.95rem; }}
  .timeline .tl-trigger {{ color: #94a3b8; font-size: 0.8rem; margin-top: 0.2rem; }}
  .info-table {{ width: 100%; border-collapse: collapse; }}
  .info-table th {{ text-align: left; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; }}
  .info-table td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }}
  .info-table tr:last-child td {{ border-bottom: none; }}
  footer {{ color: #475569; font-size: 0.75rem; margin-top: 2rem; text-align: center; }}
</style>
</head>
<body>
<h1>Market Expansion Analyzer</h1>
<p class="subtitle">Adjacent vertical expansion: Manufacturing &rarr; Logistics &rarr; Healthcare &rarr; Construction &mdash; Port {PORT}</p>

<div class="grid">
  <div class="card">
    <div class="card-label">Manufacturing TAM</div>
    <div class="card-value red">$2.3B</div>
    <div class="card-sub"><span class="badge badge-ga">GA</span> &nbsp; Now (Q1 2026)</div>
  </div>
  <div class="card">
    <div class="card-label">Logistics TAM</div>
    <div class="card-value blue">$1.8B</div>
    <div class="card-sub"><span class="badge badge-beta">Beta</span> &nbsp; Q3 2026</div>
  </div>
  <div class="card">
    <div class="card-label">Healthcare TAM</div>
    <div class="card-value yellow">$940M</div>
    <div class="card-sub"><span class="badge badge-alpha">Alpha</span> &nbsp; Q1 2027</div>
  </div>
  <div class="card">
    <div class="card-label">Construction TAM</div>
    <div class="card-value purple">$670M</div>
    <div class="card-sub"><span class="badge badge-research">Research</span> &nbsp; Q3 2027</div>
  </div>
  <div class="card">
    <div class="card-label">Total Addressable Market</div>
    <div class="card-value green">$5.71B</div>
    <div class="card-sub">Across 4 verticals</div>
  </div>
  <div class="card">
    <div class="card-label">Current Focus</div>
    <div class="card-value">Mfg</div>
    <div class="card-sub">Next: Logistics</div>
  </div>
</div>

<div class="chart-container">
  <div class="section-title">TAM by Vertical (USD)</div>
  <svg viewBox="0 0 600 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px;display:block;margin:0 auto;">
    <!-- Y-axis -->
    <line x1="70" y1="20" x2="70" y2="185" stroke="#334155" stroke-width="1"/>
    <!-- X-axis -->
    <line x1="70" y1="185" x2="570" y2="185" stroke="#334155" stroke-width="1"/>
    <!-- Y grid + labels -->
    <line x1="70" y1="185" x2="570" y2="185" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="70" y1="143" x2="570" y2="143" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="70" y1="101" x2="570" y2="101" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="70" y1="59" x2="570" y2="59" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="70" y1="20" x2="570" y2="20" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <text x="62" y="189" fill="#64748b" font-size="11" text-anchor="end">$0</text>
    <text x="62" y="147" fill="#64748b" font-size="11" text-anchor="end">$0.5B</text>
    <text x="62" y="105" fill="#64748b" font-size="11" text-anchor="end">$1.0B</text>
    <text x="62" y="63" fill="#64748b" font-size="11" text-anchor="end">$1.5B</text>
    <text x="62" y="24" fill="#64748b" font-size="11" text-anchor="end">$2.0B+</text>
    <!-- Manufacturing: $2.3B => max, height = 165 (full bar) -->
    <rect x="90" y="20" width="90" height="165" fill="#C74634" rx="4"/>
    <text x="135" y="14" fill="#C74634" font-size="12" font-weight="700" text-anchor="middle">$2.3B</text>
    <text x="135" y="205" fill="#94a3b8" font-size="11" text-anchor="middle">Manufacturing</text>
    <!-- Logistics: $1.8B => 1.8/2.3*165 = 129 -->
    <rect x="210" y="56" width="90" height="129" fill="#38bdf8" rx="4"/>
    <text x="255" y="50" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">$1.8B</text>
    <text x="255" y="205" fill="#94a3b8" font-size="11" text-anchor="middle">Logistics</text>
    <!-- Healthcare: $940M => 0.94/2.3*165 = 67.4 -->
    <rect x="330" y="118" width="90" height="67" fill="#fbbf24" rx="4"/>
    <text x="375" y="112" fill="#fbbf24" font-size="12" font-weight="700" text-anchor="middle">$940M</text>
    <text x="375" y="205" fill="#94a3b8" font-size="11" text-anchor="middle">Healthcare</text>
    <!-- Construction: $670M => 0.67/2.3*165 = 48 -->
    <rect x="450" y="137" width="90" height="48" fill="#a78bfa" rx="4"/>
    <text x="495" y="131" fill="#a78bfa" font-size="12" font-weight="700" text-anchor="middle">$670M</text>
    <text x="495" y="205" fill="#94a3b8" font-size="11" text-anchor="middle">Construction</text>
    <!-- Total label -->
    <text x="560" y="14" fill="#34d399" font-size="11" text-anchor="end">Total: $5.71B</text>
  </svg>
</div>

<div class="chart-container">
  <div class="section-title">Expansion Timeline &amp; Trigger Milestones</div>
  <ul class="timeline">
    <li class="active">
      <div class="tl-title" style="color:#C74634;">Manufacturing &mdash; GA &mdash; Now (Q1 2026)</div>
      <div class="tl-trigger">GTM: Direct enterprise + OCI Marketplace</div>
      <div class="tl-trigger">Trigger to next: 10 customers, $5M ARR, 95%+ uptime SLA</div>
    </li>
    <li>
      <div class="tl-title" style="color:#38bdf8;">Logistics &mdash; Beta &mdash; Q3 2026</div>
      <div class="tl-trigger">GTM: 3PL partnerships + system integrators</div>
      <div class="tl-trigger">Trigger to next: Tier-1 3PL pilot, autonomous cycle time &lt;4s</div>
    </li>
    <li>
      <div class="tl-title" style="color:#fbbf24;">Healthcare &mdash; Alpha &mdash; Q1 2027</div>
      <div class="tl-trigger">GTM: Hospital networks + FDA-cleared device channels</div>
      <div class="tl-trigger">Trigger to next: FDA 510(k) clearance, 2 hospital network contracts</div>
    </li>
    <li>
      <div class="tl-title" style="color:#a78bfa;">Construction &mdash; Research &mdash; Q3 2027</div>
      <div class="tl-trigger">GTM: General contractor pilots + OEM agreements</div>
    </li>
  </ul>
</div>

<div class="chart-container">
  <div class="section-title">Channel Strategy by Vertical</div>
  <table class="info-table">
    <thead><tr><th>Vertical</th><th>TAM</th><th>Stage</th><th>GTM Motion</th><th>Timeline</th></tr></thead>
    <tbody>
      <tr><td class="red">Manufacturing</td><td>$2.3B</td><td><span class="badge badge-ga">GA</span></td><td>Direct enterprise + OCI Marketplace</td><td>Q1 2026</td></tr>
      <tr><td class="blue">Logistics</td><td>$1.8B</td><td><span class="badge badge-beta">Beta</span></td><td>3PL partnerships + system integrators</td><td>Q3 2026</td></tr>
      <tr><td class="yellow">Healthcare</td><td>$940M</td><td><span class="badge badge-alpha">Alpha</span></td><td>Hospital networks + FDA-cleared device channels</td><td>Q1 2027</td></tr>
      <tr><td class="purple">Construction</td><td>$670M</td><td><span class="badge badge-research">Research</span></td><td>General contractor pilots + OEM agreements</td><td>Q3 2027</td></tr>
    </tbody>
  </table>
</div>

<footer>OCI Robot Cloud &mdash; Market Expansion Analyzer &mdash; Port {PORT}</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Market Expansion Analyzer",
        description="Adjacent vertical market analysis: manufacturing → logistics → healthcare → construction",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "market_expansion_analyzer", "port": PORT})

    @app.get("/market/verticals")
    async def get_vertical(vertical: str = Query(default="manufacturing")):
        key = vertical.lower().strip()
        if key not in VERTICALS:
            return JSONResponse(
                {"error": f"Unknown vertical '{vertical}'. Valid: {list(VERTICALS.keys())}"},
                status_code=404,
            )
        return JSONResponse(VERTICALS[key])

    @app.get("/market/expansion_sequence")
    async def expansion_sequence():
        return JSONResponse(EXPANSION_SEQUENCE)

# ---------------------------------------------------------------------------
# stdlib fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, ctype: str, body: str | bytes):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "market_expansion_analyzer", "port": PORT}))
            elif path == "/market/verticals":
                vertical = params.get("vertical", ["manufacturing"])[0].lower().strip()
                if vertical not in VERTICALS:
                    self._send(404, "application/json",
                               json.dumps({"error": f"Unknown vertical '{vertical}'"}))
                else:
                    self._send(200, "application/json", json.dumps(VERTICALS[vertical]))
            elif path == "/market/expansion_sequence":
                self._send(200, "application/json", json.dumps(EXPANSION_SEQUENCE))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

    def _run_stdlib():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[stdlib] market_expansion_analyzer listening on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib()
