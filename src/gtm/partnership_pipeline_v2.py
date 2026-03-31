"""Partnership Pipeline v2 — port 10019.

Structured partner pipeline with 5 stages:
  prospecting → qualification → proposal → contract → active
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

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

PORT = 10019

STAGES = ["prospecting", "qualification", "proposal", "contract", "active"]

PIPELINE: Dict[str, List[dict]] = {
    "prospecting": [
        {"company": "Agility Robotics", "series": "C", "nvidia_ecosystem": True,  "estimated_acv": 180000, "next_steps": "Schedule intro call with BD lead"},
        {"company": "Figure AI",        "series": "B", "nvidia_ecosystem": True,  "estimated_acv": 250000, "next_steps": "Send OCI Robot Cloud brief"},
        {"company": "1X Technologies",  "series": "B", "nvidia_ecosystem": False, "estimated_acv": 120000, "next_steps": "Research tech stack fit"},
        {"company": "Apptronik",        "series": "A", "nvidia_ecosystem": True,  "estimated_acv": 95000,  "next_steps": "Connect via NVIDIA partner channel"},
        {"company": "Wandercraft",      "series": "A", "nvidia_ecosystem": False, "estimated_acv": 80000,  "next_steps": "Initial outreach email"},
        {"company": "Enchanted Tools",  "series": "A", "nvidia_ecosystem": False, "estimated_acv": 75000,  "next_steps": "Identify champion contact"},
        {"company": "Myomo",            "series": "B", "nvidia_ecosystem": False, "estimated_acv": 60000,  "next_steps": "Qualify use case"},
        {"company": "Robotics Plus",    "series": "A", "nvidia_ecosystem": True,  "estimated_acv": 90000,  "next_steps": "Demo request sent"},
        {"company": "Formant",          "series": "B", "nvidia_ecosystem": True,  "estimated_acv": 110000, "next_steps": "Platform integration discussion"},
        {"company": "RightHand Robotics","series": "B", "nvidia_ecosystem": True, "estimated_acv": 140000, "next_steps": "Technical evaluation kickoff"},
        {"company": "Covariant",        "series": "C", "nvidia_ecosystem": True,  "estimated_acv": 200000, "next_steps": "Executive briefing scheduled"},
        {"company": "Nuro",             "series": "D", "nvidia_ecosystem": True,  "estimated_acv": 320000, "next_steps": "AV robotics use-case scoping"},
    ],
    "qualification": [
        {"company": "Dexterity",    "series": "B", "nvidia_ecosystem": True,  "estimated_acv": 195000, "next_steps": "Technical deep-dive booked for next week"},
        {"company": "Pickle Robot", "series": "A", "nvidia_ecosystem": False, "estimated_acv": 88000,  "next_steps": "IQ scoring review with solutions architect"},
        {"company": "Robust AI",    "series": "B", "nvidia_ecosystem": True,  "estimated_acv": 160000, "next_steps": "POC proposal in draft"},
        {"company": "Dusty Robotics","series":"B", "nvidia_ecosystem": False, "estimated_acv": 105000, "next_steps": "Construction vertical fit assessment"},
    ],
    "proposal": [
        {"company": "Viam",     "series": "C", "nvidia_ecosystem": True,  "estimated_acv": 275000, "next_steps": "Legal review of MSA; close targeted Q2"},
        {"company": "Sanctuary AI", "series": "C", "nvidia_ecosystem": True, "estimated_acv": 310000, "next_steps": "Procurement approval pending; exec sponsor engaged"},
    ],
    "contract": [
        {"company": "Machina Labs", "series": "B", "nvidia_ecosystem": True, "estimated_acv": 230000, "next_steps": "Final redlines; signature expected this week"},
    ],
    "active": [
        {"company": "Machina",  "series": "C", "nvidia_ecosystem": True,  "estimated_acv": 420000, "next_steps": "QBR scheduled; upsell fine-tuning tier"},
        {"company": "Verdant Robotics", "series": "B", "nvidia_ecosystem": True, "estimated_acv": 185000, "next_steps": "Multi-region expansion discussion"},
        {"company": "Helix",   "series": "B", "nvidia_ecosystem": False, "estimated_acv": 150000, "next_steps": "Renewal in 60 days; identify expansion use case"},
    ],
}

# IQ scoring weights
_SERIES_SCORE = {"A": 15, "B": 25, "C": 35, "D": 45}

def compute_iq(company: str, series: str, nvidia_ecosystem: bool, estimated_acv: float) -> dict:
    base = _SERIES_SCORE.get(series.upper(), 10)
    nvidia_bonus = 20 if nvidia_ecosystem else 0
    acv_score = min(estimated_acv / 10000, 30)  # max 30 pts from ACV
    iq = round(base + nvidia_bonus + acv_score, 1)

    if iq >= 60:
        action = "Fast-track to proposal"
        fit = f"{company} is a strong fit — NVIDIA ecosystem alignment and high ACV potential justify priority outreach."
    elif iq >= 40:
        action = "Advance to qualification"
        fit = f"{company} shows moderate fit. Validate technical requirements and budget authority before proposal."
    else:
        action = "Continue nurture"
        fit = f"{company} is early-stage. Monitor for series raise or ecosystem signals before investing BD cycles."

    return {"iq_score": iq, "recommended_action": action, "fit_notes": fit}

# ---------------------------------------------------------------------------
# Aggregated stats helper
# ---------------------------------------------------------------------------

def pipeline_summary() -> dict:
    return {
        stage: {
            "count": len(partners),
            "total_acv": sum(p["estimated_acv"] for p in partners),
            "companies": [p["company"] for p in partners],
        }
        for stage, partners in PIPELINE.items()
    }

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Partnership Pipeline v2</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    /* Funnel cards */
    .funnel { display: flex; gap: 0.75rem; margin-bottom: 2rem; flex-wrap: wrap; }
    .stage-card { flex: 1; min-width: 120px; background: #1e293b; border-radius: 10px; padding: 1rem; border-top: 4px solid #38bdf8; text-align: center; }
    .stage-card.active-stage { border-top-color: #4ade80; }
    .stage-card.contract-stage { border-top-color: #C74634; }
    .stage-card h3 { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .stage-card .count { font-size: 2.2rem; font-weight: 800; color: #38bdf8; }
    .stage-card.active-stage .count { color: #4ade80; }
    .stage-card.contract-stage .count { color: #C74634; }
    .stage-card .acv { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }
    /* chart */
    .chart-section { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1.25rem; }
    /* partner list */
    .partners-section { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .partners-section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .partner-row { display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0; border-bottom: 1px solid #0f172a; }
    .partner-row:last-child { border-bottom: none; }
    .partner-name { font-weight: 600; color: #e2e8f0; }
    .partner-meta { font-size: 0.78rem; color: #94a3b8; }
    .badge { font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 9999px; font-weight: 600; }
    .badge.active { background: #166534; color: #4ade80; }
    .badge.proposal { background: #1e3a5f; color: #38bdf8; }
    .badge.contract { background: #5c1a1a; color: #C74634; }
    /* endpoints */
    .endpoints { background: #1e293b; border-radius: 10px; padding: 1.5rem; }
    .endpoints h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .endpoint { font-family: monospace; font-size: 0.85rem; padding: 0.5rem 0.75rem; background: #0f172a; border-radius: 6px; margin-bottom: 0.5rem; color: #e2e8f0; }
    .method { color: #C74634; font-weight: 700; margin-right: 0.5rem; }
    footer { margin-top: 2rem; text-align: center; font-size: 0.75rem; color: #334155; }
  </style>
</head>
<body>
  <h1>Partnership Pipeline v2</h1>
  <p class="subtitle">OCI Robot Cloud &mdash; Port 10019 &mdash; 5-stage partner qualification &amp; tracking</p>

  <!-- Funnel overview -->
  <div class="funnel">
    <div class="stage-card">
      <h3>Prospecting</h3>
      <div class="count">12</div>
      <div class="acv">$1.73M potential</div>
    </div>
    <div class="stage-card">
      <h3>Qualification</h3>
      <div class="count">4</div>
      <div class="acv">$548K potential</div>
    </div>
    <div class="stage-card proposal-stage">
      <h3>Proposal</h3>
      <div class="count" style="color:#38bdf8">2</div>
      <div class="acv">$585K potential</div>
    </div>
    <div class="stage-card contract-stage">
      <h3>Contract</h3>
      <div class="count">1</div>
      <div class="acv">$230K potential</div>
    </div>
    <div class="stage-card active-stage">
      <h3>Active</h3>
      <div class="count">3</div>
      <div class="acv">$755K ARR</div>
    </div>
  </div>

  <!-- SVG bar chart: deal count per stage -->
  <div class="chart-section">
    <h2>Pipeline Deal Count by Stage</h2>
    <svg width="100%" height="220" viewBox="0 0 620 220" xmlns="http://www.w3.org/2000/svg">
      <rect width="620" height="220" fill="#1e293b" rx="8"/>
      <!-- grid -->
      <line x1="70" y1="20" x2="600" y2="20" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="56.7" x2="600" y2="56.7" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="93.3" x2="600" y2="93.3" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="130" x2="600" y2="130" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels -->
      <text x="60" y="24" fill="#64748b" font-size="11" text-anchor="end">12</text>
      <text x="60" y="60" fill="#64748b" font-size="11" text-anchor="end">9</text>
      <text x="60" y="97" fill="#64748b" font-size="11" text-anchor="end">6</text>
      <text x="60" y="134" fill="#64748b" font-size="11" text-anchor="end">3</text>
      <!-- bar height scale: 12 deals = 130px total bar area (130 to 20) -->
      <!-- prospecting: 12 -->
      <rect x="90"  y="20"  width="70" height="130" fill="#38bdf8" rx="4"/>
      <text x="125" y="165" fill="#94a3b8" font-size="11" text-anchor="middle">Prospecting</text>
      <text x="125" y="15"  fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">12</text>
      <!-- qualification: 4 -->
      <rect x="190" y="86.7" width="70" height="63.3" fill="#38bdf8" rx="4"/>
      <text x="225" y="165" fill="#94a3b8" font-size="11" text-anchor="middle">Qualification</text>
      <text x="225" y="81"  fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">4</text>
      <!-- proposal: 2 -->
      <rect x="290" y="108.3" width="70" height="41.7" fill="#0ea5e9" rx="4"/>
      <text x="325" y="165" fill="#94a3b8" font-size="11" text-anchor="middle">Proposal</text>
      <text x="325" y="103" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">2</text>
      <!-- contract: 1 -->
      <rect x="390" y="119.2" width="70" height="30.8" fill="#C74634" rx="4"/>
      <text x="425" y="165" fill="#94a3b8" font-size="11" text-anchor="middle">Contract</text>
      <text x="425" y="114" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">1</text>
      <!-- active: 3 -->
      <rect x="490" y="97.5" width="70" height="52.5" fill="#4ade80" rx="4"/>
      <text x="525" y="165" fill="#94a3b8" font-size="11" text-anchor="middle">Active</text>
      <text x="525" y="92"  fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">3</text>
      <!-- legend -->
      <rect x="90"  y="185" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="106" y="195" fill="#94a3b8" font-size="11">In-flight</text>
      <rect x="220" y="185" width="12" height="10" fill="#C74634" rx="2"/>
      <text x="236" y="195" fill="#94a3b8" font-size="11">Contract</text>
      <rect x="350" y="185" width="12" height="10" fill="#4ade80" rx="2"/>
      <text x="366" y="195" fill="#94a3b8" font-size="11">Active</text>
    </svg>
  </div>

  <!-- Named partners highlight -->
  <div class="partners-section">
    <h2>Highlighted Partners</h2>
    <div class="partner-row">
      <div>
        <div class="partner-name">Machina</div>
        <div class="partner-meta">Series C &bull; NVIDIA ecosystem &bull; $420K ARR</div>
      </div>
      <span class="badge active">Active</span>
    </div>
    <div class="partner-row">
      <div>
        <div class="partner-name">Verdant Robotics</div>
        <div class="partner-meta">Series B &bull; NVIDIA ecosystem &bull; $185K ARR</div>
      </div>
      <span class="badge active">Active</span>
    </div>
    <div class="partner-row">
      <div>
        <div class="partner-name">Helix</div>
        <div class="partner-meta">Series B &bull; $150K ARR &bull; Renewal in 60 days</div>
      </div>
      <span class="badge active">Active</span>
    </div>
    <div class="partner-row">
      <div>
        <div class="partner-name">Viam</div>
        <div class="partner-meta">Series C &bull; NVIDIA ecosystem &bull; $275K ACV &bull; Legal review</div>
      </div>
      <span class="badge proposal">Proposal</span>
    </div>
    <div class="partner-row">
      <div>
        <div class="partner-name">Sanctuary AI</div>
        <div class="partner-meta">Series C &bull; NVIDIA ecosystem &bull; $310K ACV &bull; Procurement pending</div>
      </div>
      <span class="badge proposal">Proposal</span>
    </div>
    <div class="partner-row">
      <div>
        <div class="partner-name">Machina Labs</div>
        <div class="partner-meta">Series B &bull; NVIDIA ecosystem &bull; $230K ACV &bull; Final redlines</div>
      </div>
      <span class="badge contract">Contract</span>
    </div>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="endpoint"><span class="method">GET</span>/health &mdash; Health check</div>
    <div class="endpoint"><span class="method">GET</span>/partners/pipeline?stage=&lt;stage&gt; &mdash; Partners in stage</div>
    <div class="endpoint"><span class="method">POST</span>/partners/qualify &mdash; IQ scoring for new partner</div>
    <div class="endpoint"><span class="method">GET</span>/partners/summary &mdash; Full pipeline summary</div>
  </div>

  <footer>OCI Robot Cloud &bull; Partnership Pipeline v2 &bull; Port 10019</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    from fastapi import FastAPI, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    app = FastAPI(title="Partnership Pipeline v2", version="2.0.0")

    class QualifyRequest(BaseModel):
        company: str
        series: str
        nvidia_ecosystem: bool
        estimated_acv: float

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "partnership_pipeline_v2", "port": PORT})

    @app.get("/partners/pipeline")
    async def get_pipeline(stage: Optional[str] = Query(default=None)):
        if stage:
            stage_lower = stage.lower()
            if stage_lower not in PIPELINE:
                return JSONResponse({"error": f"Unknown stage '{stage}'. Valid: {STAGES}"}, status_code=400)
            return JSONResponse({"stage": stage_lower, "partners": PIPELINE[stage_lower]})
        return JSONResponse({"pipeline": PIPELINE, "stages": STAGES})

    @app.get("/partners/summary")
    async def summary():
        return JSONResponse(pipeline_summary())

    @app.post("/partners/qualify")
    async def qualify(req: QualifyRequest):
        result = compute_iq(req.company, req.series, req.nvidia_ecosystem, req.estimated_acv)
        return JSONResponse(result)

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, content_type: str, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path == "/":
                self._send(200, "text/html; charset=utf-8", HTML.encode())
            elif path == "/health":
                body = json.dumps({"status": "ok", "service": "partnership_pipeline_v2", "port": PORT}).encode()
                self._send(200, "application/json", body)
            elif path == "/partners/pipeline":
                stage = params.get("stage", [None])[0]
                if stage:
                    stage_lower = stage.lower()
                    if stage_lower not in PIPELINE:
                        body = json.dumps({"error": f"Unknown stage '{stage}'", "valid": STAGES}).encode()
                        self._send(400, "application/json", body)
                        return
                    body = json.dumps({"stage": stage_lower, "partners": PIPELINE[stage_lower]}).encode()
                else:
                    body = json.dumps({"pipeline": PIPELINE, "stages": STAGES}).encode()
                self._send(200, "application/json", body)
            elif path == "/partners/summary":
                body = json.dumps(pipeline_summary()).encode()
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

        def do_POST(self):
            if self.path == "/partners/qualify":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw)
                    result = compute_iq(
                        data.get("company", "Unknown"),
                        data.get("series", "A"),
                        bool(data.get("nvidia_ecosystem", False)),
                        float(data.get("estimated_acv", 0)),
                    )
                    body = json.dumps(result).encode()
                    self._send(200, "application/json", body)
                except Exception as exc:
                    body = json.dumps({"error": str(exc)}).encode()
                    self._send(400, "application/json", body)
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

    def _serve():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Partnership Pipeline v2 (stdlib) listening on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
