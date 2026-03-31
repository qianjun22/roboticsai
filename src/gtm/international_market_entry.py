"""International Market Entry Service — APAC + EU expansion planning (port 10015).

Provides TAM sizing, entry timelines, compliance posture, and OCI infrastructure
advantages for Japan, South Korea, Germany, and Singapore.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10015

MARKET_DATA: dict[str, dict[str, Any]] = {
    "japan": {
        "region": "Japan",
        "tam_usd": 890_000_000,
        "entry_timeline": "Q3 2026",
        "barriers": [
            "Language localisation required",
            "Strong incumbent robotics vendors (Fanuc, Yaskawa)",
            "Complex regulatory approval (METI certification)",
            "Cultural preference for domestic suppliers",
        ],
        "oci_advantage": "OCI Tokyo + Osaka regions provide sub-5ms latency and data residency compliance; NVIDIA A100 bare-metal available",
    },
    "south_korea": {
        "region": "South Korea",
        "tam_usd": 540_000_000,
        "entry_timeline": "Q4 2026",
        "barriers": [
            "Dominated by Hyundai Robotics and Samsung affiliates",
            "K-ISMS security certification required for cloud",
            "Government preference for domestic cloud",
        ],
        "oci_advantage": "OCI Seoul region; existing Oracle ERP footprint in conglomerates; FedRAMP-equivalent audit posture",
    },
    "germany": {
        "region": "Germany",
        "tam_usd": 1_200_000_000,
        "entry_timeline": "Q2 2026",
        "barriers": [
            "GDPR and AI Act compliance mandatory",
            "Works council approval for AI-assisted automation",
            "KUKA / Siemens incumbent advantage",
            "Strict data sovereignty requirements (GAIA-X)",
        ],
        "oci_advantage": "OCI Frankfurt + Amsterdam for EU data residency; Sovereign Cloud offering; GDPR-ready DPA",
    },
    "singapore": {
        "region": "Singapore",
        "tam_usd": 310_000_000,
        "entry_timeline": "Q1 2026",
        "barriers": [
            "Small domestic market — ASEAN hub strategy needed",
            "MAS TRM and PDPA compliance",
            "Limited local robotics talent",
        ],
        "oci_advantage": "OCI Singapore region; Strategic hub for ASEAN expansion; Oracle partnership with EDB Singapore",
    },
}

COMPLIANCE_DATA: dict[str, dict[str, Any]] = {
    "japan": {
        "region": "Japan",
        "gdpr_applicable": False,
        "data_residency": {"required": True, "oci_regions": ["ap-tokyo-1", "ap-osaka-1"], "status": "compliant"},
        "export_controls": {"regime": "FEFTA", "robotics_classification": "controlled", "oci_status": "license available"},
        "local_certifications": ["METI Robot Safety Standard", "JEITA IoT Guidelines"],
        "overall": "ready",
    },
    "south_korea": {
        "region": "South Korea",
        "gdpr_applicable": False,
        "data_residency": {"required": True, "oci_regions": ["ap-seoul-1"], "status": "compliant"},
        "export_controls": {"regime": "KITA", "robotics_classification": "dual-use review", "oci_status": "in progress"},
        "local_certifications": ["K-ISMS", "ISMS-P"],
        "overall": "in_progress",
    },
    "germany": {
        "region": "Germany",
        "gdpr_applicable": True,
        "data_residency": {"required": True, "oci_regions": ["eu-frankfurt-1", "eu-amsterdam-1"], "status": "compliant"},
        "export_controls": {"regime": "EU Dual-Use Regulation", "robotics_classification": "controlled", "oci_status": "compliant"},
        "local_certifications": ["ISO 27001", "C5 (BSI)", "GAIA-X alignment"],
        "overall": "ready",
    },
    "singapore": {
        "region": "Singapore",
        "gdpr_applicable": False,
        "data_residency": {"required": False, "oci_regions": ["ap-singapore-1"], "status": "compliant"},
        "export_controls": {"regime": "Strategic Goods Control Act", "robotics_classification": "standard", "oci_status": "compliant"},
        "local_certifications": ["MAS TRM", "PDPA", "CSA CYBER ESSENTIALS"],
        "overall": "ready",
    },
}


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>International Market Entry — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      padding: 2rem;
    }
    header {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 2rem;
      border-bottom: 2px solid #C74634;
      padding-bottom: 1rem;
    }
    header h1 { font-size: 1.6rem; color: #f8fafc; }
    header span.badge {
      background: #C74634;
      color: #fff;
      font-size: 0.75rem;
      padding: 0.2rem 0.6rem;
      border-radius: 999px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2.5rem; }
    .section-title {
      font-size: 1.1rem;
      font-weight: 600;
      color: #38bdf8;
      margin-bottom: 1rem;
      border-left: 3px solid #38bdf8;
      padding-left: 0.75rem;
    }
    .chart-card, .market-grid, .compliance-grid {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 2rem;
    }
    .market-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.25rem; }
    .market-card {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.25rem;
    }
    .market-card h3 { color: #f8fafc; margin-bottom: 0.5rem; font-size: 1rem; }
    .market-card .tam { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .market-card .timeline { font-size: 0.8rem; color: #94a3b8; margin: 0.4rem 0; }
    .market-card .oci { font-size: 0.78rem; color: #4ade80; margin-top: 0.5rem; }
    .compliance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
    .comp-card {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1rem;
    }
    .comp-card h4 { color: #f8fafc; font-size: 0.9rem; margin-bottom: 0.5rem; }
    .status-badge {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.15rem 0.55rem;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .status-badge.ready { background: #14532d; color: #4ade80; }
    .status-badge.in-progress { background: #92400e; color: #fcd34d; }
    .endpoints {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 1.5rem;
    }
    .endpoint-row {
      display: flex;
      align-items: baseline;
      gap: 0.75rem;
      padding: 0.6rem 0;
      border-bottom: 1px solid #0f172a;
    }
    .endpoint-row:last-child { border-bottom: none; }
    .method {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      min-width: 44px;
      text-align: center;
    }
    .method.get { background: #1d4ed8; color: #bfdbfe; }
    .path { font-family: monospace; font-size: 0.9rem; color: #f1f5f9; }
    .desc { font-size: 0.8rem; color: #94a3b8; }
    footer {
      margin-top: 3rem;
      text-align: center;
      font-size: 0.75rem;
      color: #475569;
    }
  </style>
</head>
<body>
  <header>
    <h1>International Market Entry</h1>
    <span class="badge">APAC + EU</span>
    <span class="badge" style="background:#1e40af;">Port 10015</span>
  </header>
  <p class="subtitle">OCI Robot Cloud global expansion — TAM sizing, compliance posture, and OCI regional infrastructure advantages.</p>

  <!-- TAM Bar Chart -->
  <div class="section-title">Total Addressable Market (USD)</div>
  <div class="chart-card">
    <svg viewBox="0 0 600 230" width="100%" role="img" aria-label="TAM bar chart">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="185" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="185" x2="580" y2="185" stroke="#334155" stroke-width="1"/>
      <!-- y grid lines (max scale $1.4B) -->
      <line x1="70" y1="185" x2="580" y2="185" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="70" y1="132" x2="580" y2="132" stroke="#334155" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="70" y1="79"  x2="580" y2="79"  stroke="#334155" stroke-width="1" stroke-dasharray="4 4"/>
      <line x1="70" y1="26"  x2="580" y2="26"  stroke="#334155" stroke-width="1" stroke-dasharray="4 4"/>
      <!-- y labels -->
      <text x="62" y="189" text-anchor="end" fill="#94a3b8" font-size="10">$0</text>
      <text x="62" y="136" text-anchor="end" fill="#94a3b8" font-size="10">$500M</text>
      <text x="62" y="83"  text-anchor="end" fill="#94a3b8" font-size="10">$1.0B</text>
      <text x="62" y="30"  text-anchor="end" fill="#94a3b8" font-size="10">$1.4B</text>
      <!-- Japan: $890M → (890/1400)*175 = 111.25 -->
      <rect x="95"  y="73.75" width="80" height="111.25" rx="4" fill="#38bdf8"/>
      <text x="135" y="68"   text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="700">$890M</text>
      <text x="135" y="205" text-anchor="middle" fill="#94a3b8" font-size="11">Japan</text>
      <!-- South Korea: $540M → (540/1400)*175 = 67.5 -->
      <rect x="215" y="117.5" width="80" height="67.5" rx="4" fill="#818cf8"/>
      <text x="255" y="112"  text-anchor="middle" fill="#818cf8" font-size="12" font-weight="700">$540M</text>
      <text x="255" y="205" text-anchor="middle" fill="#94a3b8" font-size="11">S. Korea</text>
      <!-- Germany: $1.2B → (1200/1400)*175 = 150 -->
      <rect x="335" y="35"   width="80" height="150" rx="4" fill="#C74634"/>
      <text x="375" y="29"   text-anchor="middle" fill="#C74634" font-size="12" font-weight="700">$1.2B</text>
      <text x="375" y="205" text-anchor="middle" fill="#94a3b8" font-size="11">Germany</text>
      <!-- Singapore: $310M → (310/1400)*175 = 38.75 -->
      <rect x="455" y="146.25" width="80" height="38.75" rx="4" fill="#4ade80"/>
      <text x="495" y="140"  text-anchor="middle" fill="#4ade80" font-size="12" font-weight="700">$310M</text>
      <text x="495" y="205" text-anchor="middle" fill="#94a3b8" font-size="11">Singapore</text>
    </svg>
  </div>

  <!-- Market cards -->
  <div class="section-title">Market Overview</div>
  <div class="market-grid">
    <div class="market-card">
      <h3>Japan</h3>
      <div class="tam">$890M</div>
      <div class="timeline">Entry: Q3 2026</div>
      <div class="oci">OCI Tokyo + Osaka — sub-5ms, data residency compliant</div>
    </div>
    <div class="market-card">
      <h3>Germany</h3>
      <div class="tam" style="color:#C74634;">$1.2B</div>
      <div class="timeline">Entry: Q2 2026</div>
      <div class="oci">OCI Frankfurt + Amsterdam — GDPR Sovereign Cloud</div>
    </div>
    <div class="market-card">
      <h3>South Korea</h3>
      <div class="tam" style="color:#818cf8;">$540M</div>
      <div class="timeline">Entry: Q4 2026</div>
      <div class="oci">OCI Seoul — existing Oracle ERP enterprise footprint</div>
    </div>
    <div class="market-card">
      <h3>Singapore</h3>
      <div class="tam" style="color:#4ade80;">$310M</div>
      <div class="timeline">Entry: Q1 2026 (earliest)</div>
      <div class="oci">OCI Singapore — ASEAN expansion hub, EDB partnership</div>
    </div>
  </div>

  <!-- Compliance posture -->
  <div class="section-title">Compliance Posture</div>
  <div class="compliance-grid">
    <div class="comp-card">
      <h4>Japan</h4>
      <span class="status-badge ready">Ready</span>
      <p style="font-size:0.78rem;color:#94a3b8;margin-top:0.5rem;">METI certified &bull; Data residency compliant &bull; FEFTA license available</p>
    </div>
    <div class="comp-card">
      <h4>Germany</h4>
      <span class="status-badge ready">Ready</span>
      <p style="font-size:0.78rem;color:#94a3b8;margin-top:0.5rem;">GDPR + AI Act &bull; ISO 27001 &bull; C5 (BSI) &bull; GAIA-X aligned</p>
    </div>
    <div class="comp-card">
      <h4>Singapore</h4>
      <span class="status-badge ready">Ready</span>
      <p style="font-size:0.78rem;color:#94a3b8;margin-top:0.5rem;">MAS TRM &bull; PDPA &bull; CSA Cyber Essentials</p>
    </div>
    <div class="comp-card">
      <h4>South Korea</h4>
      <span class="status-badge in-progress">In Progress</span>
      <p style="font-size:0.78rem;color:#94a3b8;margin-top:0.5rem;">K-ISMS in review &bull; ISMS-P &bull; Dual-use export controls pending</p>
    </div>
  </div>

  <!-- Endpoints -->
  <div class="section-title">API Endpoints</div>
  <div class="endpoints">
    <div class="endpoint-row">
      <span class="method get">GET</span>
      <span class="path">/</span>
      <span class="desc">This dashboard</span>
    </div>
    <div class="endpoint-row">
      <span class="method get">GET</span>
      <span class="path">/health</span>
      <span class="desc">JSON health check</span>
    </div>
    <div class="endpoint-row">
      <span class="method get">GET</span>
      <span class="path">/international/market_sizing?region=japan</span>
      <span class="desc">TAM, entry timeline, barriers, OCI advantage</span>
    </div>
    <div class="endpoint-row">
      <span class="method get">GET</span>
      <span class="path">/international/compliance?region=germany</span>
      <span class="desc">GDPR, data residency, export controls status</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; International Market Entry &mdash; Port 10015 &mdash; Oracle Confidential</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="International Market Entry",
        description="APAC + EU market expansion planning service for OCI Robot Cloud.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, summary="Dashboard")
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health", summary="Health check")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "international_market_entry", "port": PORT})

    @app.get("/international/market_sizing", summary="Market sizing by region")
    async def market_sizing(
        region: str = Query(..., description="Region: japan | south_korea | germany | singapore")
    ) -> JSONResponse:
        key = region.lower()
        if key not in MARKET_DATA:
            return JSONResponse({"error": f"Unknown region '{region}'. Valid: {list(MARKET_DATA)}."}, status_code=404)
        return JSONResponse(MARKET_DATA[key])

    @app.get("/international/compliance", summary="Compliance status by region")
    async def compliance(
        region: str = Query(..., description="Region: japan | south_korea | germany | singapore")
    ) -> JSONResponse:
        key = region.lower()
        if key not in COMPLIANCE_DATA:
            return JSONResponse({"error": f"Unknown region '{region}'. Valid: {list(COMPLIANCE_DATA)}."}, status_code=404)
        return JSONResponse(COMPLIANCE_DATA[key])


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send(self, code: int, content_type: str, body: str | bytes) -> None:
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
        elif path == "/health":
            self._send(200, "application/json",
                       json.dumps({"status": "ok", "service": "international_market_entry", "port": PORT}))
        elif path == "/international/market_sizing":
            region = (params.get("region", [""])[0]).lower()
            if region in MARKET_DATA:
                self._send(200, "application/json", json.dumps(MARKET_DATA[region]))
            else:
                self._send(404, "application/json",
                           json.dumps({"error": f"Unknown region '{region}'."}))
        elif path == "/international/compliance":
            region = (params.get("region", [""])[0]).lower()
            if region in COMPLIANCE_DATA:
                self._send(200, "application/json", json.dumps(COMPLIANCE_DATA[region]))
            else:
                self._send(404, "application/json",
                           json.dumps({"error": f"Unknown region '{region}'."}))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _FallbackHandler)
        server.serve_forever()
