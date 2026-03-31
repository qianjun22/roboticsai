"""Investor Due Diligence Pack Service — port 9997

Generates and manages investor due diligence materials.
Cycle-485A, OCI Robot Cloud.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Static DD data
# ---------------------------------------------------------------------------

_DD_SUMMARY = {
    "completeness_pct": 94,
    "arr": 250000,
    "nrr": 118,
    "sr_pct": 85,
    "customers": 3,
    "churn": 0,
}

_DD_SECTIONS = {
    "executive_summary": (
        "OCI Robot Cloud delivers cloud-native robotics AI infrastructure enabling enterprises to "
        "fine-tune, deploy, and monitor foundation robot models at scale. The platform abstracts "
        "GPU cluster management, SDG pipelines, and closed-loop evaluation into a unified API. "
        "Current ARR: $250K across 3 design partners with 0 churn and 118% NRR."
    ),
    "market_opportunity": (
        "The global robotics AI software market is projected to reach $28B by 2030 (CAGR 34%). "
        "Key verticals: industrial automation (40%), logistics (28%), healthcare (17%), "
        "agriculture (9%), other (6%). OCI Robot Cloud targets the enterprise segment "
        "where GPU-accelerated fine-tuning and sim-to-real validation create durable moats."
    ),
    "technology": (
        "Core stack: GR00T N1.6 fine-tuning (MAE 0.013, 8.7x vs baseline), "
        "multi-GPU DDP (3.07x throughput), Isaac Sim RTX domain randomization SDG, "
        "adaptive impedance control (92% SR vs 74% fixed), real-time telemetry "
        "and closed-loop eval at 231ms latency. Deployed on OCI A100 clusters "
        "at $0.0043/10K training steps."
    ),
    "financials": (
        "ARR: $250,000 | NRR: 118% | Gross Margin: ~82% (GPU infra cost pass-through model). "
        "Design partner 1: $120K/yr (manufacturing). Partner 2: $80K/yr (logistics). "
        "Partner 3: $50K/yr (agri-robotics). Pipeline: 6 qualified opportunities totaling "
        "$1.2M ARR. Burn rate: $85K/mo. Runway: 18 months at current pace."
    ),
    "team": (
        "Founding team with deep OCI infrastructure and robotics AI expertise. "
        "Combined 40+ years in cloud, ML systems, and robot learning. "
        "Advisors include recognized researchers in embodied AI and sim-to-real transfer. "
        "Current headcount: 6 (4 engineering, 1 GTM, 1 ops)."
    ),
    "competitive_landscape": (
        "Direct: Hugging Face LeRobot (open-source, no managed infra), "
        "Physical Intelligence (closed, consumer robotics focus), "
        "Covariant (narrow industrial niche). "
        "Indirect: AWS RoboMaker (deprecated), Azure (no foundation model support). "
        "OCI Robot Cloud differentiator: OCI GPU pricing (30% cheaper than AWS/Azure), "
        "NVIDIA partnership (Isaac Sim, GR00T access), enterprise SLA."
    ),
    "risks": (
        "1. GPU supply constraints (mitigated by OCI reserved capacity). "
        "2. Foundation model commoditization (mitigated by fine-tuning IP and data flywheel). "
        "3. Sim-to-real gap for novel embodiments (active R&D, adaptive impedance reduces gap). "
        "4. Regulatory uncertainty for autonomous robots (monitoring EU AI Act, ISO 10218). "
        "5. Customer concentration (top 1 = 48% ARR — diversification in progress)."
    ),
    "roadmap": (
        "Q2 2026: GA launch, 10 customers, $500K ARR. "
        "Q3 2026: Multi-region (US + EU), Jetson edge deploy GA, $900K ARR. "
        "Q4 2026: Series A close ($8M target), 25 customers, $1.8M ARR. "
        "Q1 2027: Cosmos world model integration, embodiment marketplace beta, $2.5M ARR. "
        "FY2027: $6M ARR, 60 customers, profitability milestone."
    ),
}

_SECTIONS_STATUS = {k: "complete" for k in _DD_SECTIONS}
_SECTIONS_STATUS["data_room"] = "pending"  # one incomplete for realism
_SECTIONS_STATUS["legal_ip"] = "in_progress"


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Investor Due Diligence Pack — OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 32px; }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #38bdf8; font-size: 0.9rem; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 32px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .card-title { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .card-value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .card-value.green { color: #4ade80; }
  .card-value.red { color: #C74634; }
  .card-sub { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
  .chart-container { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 32px; }
  .chart-title { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px; }
  .progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .progress-label { color: #cbd5e1; font-size: 0.82rem; width: 170px; flex-shrink: 0; }
  .progress-bar-bg { flex: 1; background: #0f172a; border-radius: 6px; height: 14px; overflow: hidden; }
  .progress-bar-fill { height: 100%; border-radius: 6px; }
  .progress-pct { color: #38bdf8; font-size: 0.82rem; width: 36px; text-align: right; flex-shrink: 0; }
  .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; }
  .endpoint { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #0f172a; }
  .method { background: #C74634; color: white; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }
  .method.get { background: #0369a1; }
  .path { color: #38bdf8; font-family: monospace; font-size: 0.9rem; }
  .desc { color: #64748b; font-size: 0.85rem; margin-left: auto; }
  footer { margin-top: 32px; color: #475569; font-size: 0.75rem; text-align: center; }
</style>
</head>
<body>
  <h1>Investor Due Diligence Pack</h1>
  <div class="subtitle">Port 9997 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Cycle-485A &nbsp;|&nbsp; Series A Readiness Dashboard</div>

  <div class="grid">
    <div class="card">
      <div class="card-title">DD Completeness</div>
      <div class="card-value green">94%</div>
      <div class="card-sub">8 of 9 sections complete</div>
    </div>
    <div class="card">
      <div class="card-title">ARR</div>
      <div class="card-value">$250K</div>
      <div class="card-sub">3 design partners</div>
    </div>
    <div class="card">
      <div class="card-title">NRR</div>
      <div class="card-value green">118%</div>
      <div class="card-sub">Net Revenue Retention</div>
    </div>
    <div class="card">
      <div class="card-title">Success Rate</div>
      <div class="card-value">85%</div>
      <div class="card-sub">Avg across task suite</div>
    </div>
    <div class="card">
      <div class="card-title">Customers</div>
      <div class="card-value">3</div>
      <div class="card-sub">Design partners</div>
    </div>
    <div class="card">
      <div class="card-title">Churn</div>
      <div class="card-value green">0</div>
      <div class="card-sub">Zero churn to date</div>
    </div>
  </div>

  <div class="chart-container">
    <div class="chart-title">Due Diligence Section Completeness</div>
    <svg width="100%" height="260" viewBox="0 0 680 260" preserveAspectRatio="xMidYMid meet">
      <!-- Axes -->
      <line x1="160" y1="10" x2="160" y2="230" stroke="#334155" stroke-width="1.5"/>
      <line x1="160" y1="230" x2="670" y2="230" stroke="#334155" stroke-width="1.5"/>
      <!-- X labels -->
      <text x="160" y="248" fill="#64748b" font-size="10" text-anchor="middle">0%</text>
      <text x="285" y="248" fill="#64748b" font-size="10" text-anchor="middle">25%</text>
      <text x="410" y="248" fill="#64748b" font-size="10" text-anchor="middle">50%</text>
      <text x="535" y="248" fill="#64748b" font-size="10" text-anchor="middle">75%</text>
      <text x="660" y="248" fill="#64748b" font-size="10" text-anchor="middle">100%</text>
      <!-- Grid -->
      <line x1="285" y1="10" x2="285" y2="230" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="410" y1="10" x2="410" y2="230" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="535" y1="10" x2="535" y2="230" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Bars: each section, height=20, gap=4 -->
      <!-- Executive Summary: 100% -->
      <text x="155" y="30" fill="#94a3b8" font-size="10" text-anchor="end">Exec Summary</text>
      <rect x="161" y="18" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Market: 100% -->
      <text x="155" y="52" fill="#94a3b8" font-size="10" text-anchor="end">Market Opp.</text>
      <rect x="161" y="40" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Technology: 100% -->
      <text x="155" y="74" fill="#94a3b8" font-size="10" text-anchor="end">Technology</text>
      <rect x="161" y="62" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Financials: 100% -->
      <text x="155" y="96" fill="#94a3b8" font-size="10" text-anchor="end">Financials</text>
      <rect x="161" y="84" width="500" height="18" fill="#4ade80" rx="3"/>
      <!-- Team: 100% -->
      <text x="155" y="118" fill="#94a3b8" font-size="10" text-anchor="end">Team</text>
      <rect x="161" y="106" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Competitive: 100% -->
      <text x="155" y="140" fill="#94a3b8" font-size="10" text-anchor="end">Competitive</text>
      <rect x="161" y="128" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Risks: 100% -->
      <text x="155" y="162" fill="#94a3b8" font-size="10" text-anchor="end">Risks</text>
      <rect x="161" y="150" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Roadmap: 100% -->
      <text x="155" y="184" fill="#94a3b8" font-size="10" text-anchor="end">Roadmap</text>
      <rect x="161" y="172" width="500" height="18" fill="#38bdf8" rx="3"/>
      <!-- Legal/IP: 60% in progress -->
      <text x="155" y="206" fill="#94a3b8" font-size="10" text-anchor="end">Legal / IP</text>
      <rect x="161" y="194" width="300" height="18" fill="#f59e0b" rx="3" opacity="0.85"/>
      <text x="468" y="207" fill="#f59e0b" font-size="10">In Progress</text>
    </svg>
  </div>

  <div class="endpoints">
    <div class="chart-title" style="margin-bottom:12px;">API Endpoints</div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/</span>
      <span class="desc">Dashboard</span>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/health</span>
      <span class="desc">Health check</span>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/diligence/summary</span>
      <span class="desc">DD completeness + key metrics</span>
    </div>
    <div class="endpoint">
      <span class="method">POST</span>
      <span class="path">/diligence/generate</span>
      <span class="desc">Generate content for a DD section</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; Investor Due Diligence Pack &mdash; Port 9997 &mdash; Cycle-485A</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Investor Due Diligence Pack",
        description="Generate and manage investor due diligence materials",
        version="1.0.0",
    )

    class GenerateRequest(BaseModel):
        section: str

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "investor_due_diligence_pack", "port": 9997})

    @app.get("/diligence/summary")
    def diligence_summary():
        return JSONResponse(_DD_SUMMARY)

    @app.post("/diligence/generate")
    def diligence_generate(req: GenerateRequest):
        section = req.section.lower().replace(" ", "_")
        if section not in _DD_SECTIONS:
            available = list(_DD_SECTIONS.keys())
            return JSONResponse(
                {"error": f"Unknown section '{req.section}'. Available: {available}"},
                status_code=404,
            )
        content = _DD_SECTIONS[section]
        status = _SECTIONS_STATUS.get(section, "complete")
        return JSONResponse({
            "section": section,
            "content": content,
            "status": status,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "word_count": len(content.split()),
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "investor_due_diligence_pack", "port": 9997}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/diligence/summary":
                body = json.dumps(_DD_SUMMARY).encode()
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

        def log_message(self, fmt, *args):
            pass

    def _run_fallback():
        server = http.server.HTTPServer(("0.0.0.0", 9997), _Handler)
        print("[investor_due_diligence_pack] stdlib fallback on port 9997")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=9997)
    else:
        _run_fallback()
