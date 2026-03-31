"""AI World Readiness Tracker — port 10021

AI World September 2026 launch readiness tracker with checklist and countdown.
Part of OCI Robot Cloud cycle-491A.
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10021

# AI World 2026 is September 29, 2026 (unix timestamp)
_AI_WORLD_TS = 1759104000  # 2026-09-29 00:00:00 UTC

READINESS_PCT = 72
DAYS_REMAINING = 183  # approx from 2026-03-30

CURRENT_DEMO_SR = 85   # % success rate in demo conditions
TARGET_DEMO_SR = 92    # % target for AI World

CRITICAL_PATH_ITEMS: List[str] = [
    "Achieve 92% demo success rate (currently 85% — 7pp gap)",
    "Confirm booth design and AV setup with Oracle Events team",
    "Finalize partner MOU with 2 design partners for live demo",
    "Complete billing and metering integration for OCI Robot Cloud",
    "Submit PR package and media kit to Oracle Corp Comms (6 wk lead)",
]

BLOCKING_ITEMS: List[str] = [
    "Demo SR below 92% target — requires 2 more fine-tune cycles",
    "Contract template not yet reviewed by Oracle Legal",
]

CHECKLIST: List[Dict[str, Any]] = [
    {"id": "demo_sr",          "item": "Demo success rate ≥ 92%",                    "status": "IN_PROGRESS", "owner": "ML Eng",       "due": "2026-08-15", "notes": f"Currently {CURRENT_DEMO_SR}% — {TARGET_DEMO_SR - CURRENT_DEMO_SR}pp gap"},
    {"id": "booth_design",     "item": "Booth design approved by Oracle Events",      "status": "IN_PROGRESS", "owner": "Events",       "due": "2026-07-01", "notes": "Initial concept submitted; awaiting sign-off"},
    {"id": "partner_confirmed","item": "2 design partners confirmed for live demo",    "status": "IN_PROGRESS", "owner": "Biz Dev",      "due": "2026-07-15", "notes": "Partner A verbal yes; Partner B in evaluation"},
    {"id": "pr_draft",         "item": "PR draft submitted to Corp Comms",            "status": "NOT_STARTED", "owner": "PMM",          "due": "2026-08-01", "notes": "Need product GA confirmation first"},
    {"id": "contract_template","item": "Contract template reviewed by Legal",         "status": "BLOCKING",    "owner": "Legal / PMM",  "due": "2026-06-30", "notes": "Submitted 2026-03-15 — no response yet"},
    {"id": "billing_live",     "item": "OCI billing + metering live in prod",          "status": "IN_PROGRESS", "owner": "Eng",          "due": "2026-08-30", "notes": "Metering API integrated; OCI billing config pending"},
    {"id": "sdk_published",    "item": "oci-robot-cloud SDK published to PyPI",        "status": "DONE",        "owner": "Eng",          "due": "2026-03-01", "notes": "v0.9.0 released"},
    {"id": "corl_paper",       "item": "CoRL paper submitted",                         "status": "DONE",        "owner": "Research",    "due": "2026-02-15", "notes": "Submitted; under review"},
    {"id": "gtc_deck",         "item": "GTC 2026 slide deck finalized",                "status": "DONE",        "owner": "PMM / Eng",   "due": "2026-03-10", "notes": "12-slide deck QA'd and presented"},
    {"id": "safety_monitor",   "item": "Safety monitor service validated",             "status": "DONE",        "owner": "Eng",          "due": "2026-03-20", "notes": "Passed 500-episode stress test"},
    {"id": "load_test",        "item": "Load test: 50 concurrent inference requests",  "status": "DONE",        "owner": "Eng",          "due": "2026-03-25", "notes": "P95 latency 312ms at 50 RPS"},
    {"id": "multi_region",     "item": "Multi-region failover (99.94% uptime SLA)",   "status": "IN_PROGRESS", "owner": "Infra",        "due": "2026-09-01", "notes": "US-East done; EU-Frankfurt in progress"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _days_remaining() -> int:
    remaining = _AI_WORLD_TS - int(time.time())
    return max(0, remaining // 86400)


def _readiness_summary() -> Dict[str, Any]:
    return {
        "readiness_pct": READINESS_PCT,
        "days_remaining": _days_remaining(),
        "ai_world_date": "2026-09-29",
        "critical_path_items": CRITICAL_PATH_ITEMS,
        "blocking_items": BLOCKING_ITEMS,
        "demo_gap": {
            "current_sr_pct": CURRENT_DEMO_SR,
            "target_sr_pct": TARGET_DEMO_SR,
            "gap_pp": TARGET_DEMO_SR - CURRENT_DEMO_SR,
        },
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_checklist_rows() -> str:
    status_classes = {
        "DONE":        ("badge-green",  "DONE"),
        "IN_PROGRESS": ("badge-blue",   "IN PROGRESS"),
        "NOT_STARTED": ("badge-gray",   "NOT STARTED"),
        "BLOCKING":    ("badge-red",    "BLOCKING"),
    }
    rows = []
    for item in CHECKLIST:
        cls, label = status_classes.get(item["status"], ("badge-gray", item["status"]))
        rows.append(
            f'<tr>'
            f'<td><span class="badge {cls}">{label}</span></td>'
            f'<td>{item["item"]}</td>'
            f'<td>{item["owner"]}</td>'
            f'<td>{item["due"]}</td>'
            f'<td style="color:#94a3b8;font-size:0.82rem">{item["notes"]}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _build_dashboard() -> str:
    days = _days_remaining()
    checklist_rows = _build_checklist_rows()

    # Readiness bar width
    bar_done = int(READINESS_PCT * 3.2)   # 320px total width
    bar_remaining = 320 - bar_done

    # Demo SR bar widths (scale: 0-100 => 0-240px)
    demo_current_w = int(CURRENT_DEMO_SR * 2.4)
    demo_target_w = int(TARGET_DEMO_SR * 2.4)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI World Readiness Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }}
  .cards {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; flex: 1; min-width: 180px; border: 1px solid #334155; }}
  .card-label {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
  .card-value {{ font-size: 2.2rem; font-weight: 700; }}
  .green {{ color: #4ade80; }}
  .blue {{ color: #38bdf8; }}
  .red {{ color: #C74634; }}
  .yellow {{ color: #fbbf24; }}
  .section {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }}
  .section h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }}
  .checklist-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  .checklist-table th {{ text-align: left; padding: 0.6rem 1rem; background: #0f172a; color: #94a3b8; font-weight: 600; }}
  .checklist-table td {{ padding: 0.6rem 1rem; border-top: 1px solid #334155; vertical-align: top; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.76rem; font-weight: 600; white-space: nowrap; }}
  .badge-green {{ background: #166534; color: #4ade80; }}
  .badge-blue  {{ background: #1e3a5f; color: #38bdf8; }}
  .badge-gray  {{ background: #1e293b; color: #94a3b8; border: 1px solid #475569; }}
  .badge-red   {{ background: #7f1d1d; color: #f87171; }}
  .progress-bar {{ height: 18px; border-radius: 9px; overflow: hidden; background: #0f172a; display: flex; margin-top: 0.5rem; }}
  .progress-fill-green {{ background: #4ade80; border-radius: 9px 0 0 9px; }}
  .progress-fill-remaining {{ background: #334155; }}
  .critical-list {{ list-style: none; }}
  .critical-list li {{ padding: 0.4rem 0; border-top: 1px solid #334155; font-size: 0.88rem; }}
  .critical-list li:first-child {{ border-top: none; }}
  .critical-list li::before {{ content: '\2192  '; color: #C74634; }}
  .blocking-list {{ list-style: none; }}
  .blocking-list li {{ padding: 0.4rem 0; border-top: 1px solid #334155; font-size: 0.88rem; color: #f87171; }}
  .blocking-list li:first-child {{ border-top: none; }}
  .blocking-list li::before {{ content: '\26A0  '; }}
  .endpoint {{ font-family: monospace; background: #0f172a; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.82rem; color: #38bdf8; }}
  .footer {{ color: #475569; font-size: 0.78rem; margin-top: 2rem; text-align: center; }}
  .two-col {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .two-col .section {{ flex: 1; min-width: 260px; margin-bottom: 0; }}
</style>
</head>
<body>
<h1>AI World Readiness Tracker</h1>
<p class="subtitle">September 29 2026 launch readiness — OCI Robot Cloud cycle-491A — port 10021</p>

<div class="cards">
  <div class="card">
    <div class="card-label">Overall Readiness</div>
    <div class="card-value blue">{READINESS_PCT}%</div>
  </div>
  <div class="card">
    <div class="card-label">Days Remaining</div>
    <div class="card-value yellow">{days}</div>
  </div>
  <div class="card">
    <div class="card-label">Demo SR (Current)</div>
    <div class="card-value red">{CURRENT_DEMO_SR}%</div>
  </div>
  <div class="card">
    <div class="card-label">Demo SR (Target)</div>
    <div class="card-value green">{TARGET_DEMO_SR}%</div>
  </div>
  <div class="card">
    <div class="card-label">Demo Gap</div>
    <div class="card-value red">-{TARGET_DEMO_SR - CURRENT_DEMO_SR}pp</div>
  </div>
</div>

<!-- SVG Bar Chart: readiness breakdown + demo SR -->
<div class="section">
  <h2>Launch Readiness &amp; Demo Success Rate</h2>
  <svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;">
    <!-- Grid -->
    <line x1="70" y1="20" x2="70" y2="170" stroke="#334155" stroke-width="1"/>
    <line x1="70" y1="170" x2="480" y2="170" stroke="#334155" stroke-width="1"/>
    <line x1="70" y1="120" x2="480" y2="120" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="70" y1="70" x2="480" y2="70" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
    <!-- Y axis labels -->
    <text x="60" y="173" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
    <text x="60" y="123" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
    <text x="60" y="73" fill="#94a3b8" font-size="11" text-anchor="end">100%</text>
    <!-- Bar: Readiness 72% => 100.8px, top = 170-100.8 = 69.2 -->
    <rect x="100" y="69" width="70" height="101" fill="#38bdf8" rx="4"/>
    <text x="135" y="62" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">{READINESS_PCT}%</text>
    <text x="135" y="188" fill="#94a3b8" font-size="11" text-anchor="middle">Readiness</text>
    <!-- Bar: Demo Current 85% => 119px, top = 170-119 = 51 -->
    <rect x="230" y="51" width="70" height="119" fill="#fbbf24" rx="4"/>
    <text x="265" y="44" fill="#fbbf24" font-size="12" text-anchor="middle" font-weight="600">{CURRENT_DEMO_SR}%</text>
    <text x="265" y="188" fill="#94a3b8" font-size="11" text-anchor="middle">Demo Now</text>
    <!-- Bar: Demo Target 92% => 128.8px, top = 170-128.8 = 41.2 -->
    <rect x="360" y="41" width="70" height="129" fill="#4ade80" rx="4"/>
    <text x="395" y="34" fill="#4ade80" font-size="12" text-anchor="middle" font-weight="600">{TARGET_DEMO_SR}%</text>
    <text x="395" y="188" fill="#94a3b8" font-size="11" text-anchor="middle">Demo Target</text>
    <!-- Gap annotation -->
    <line x1="265" y1="51" x2="395" y2="41" stroke="#C74634" stroke-width="1" stroke-dasharray="3,3"/>
    <text x="478" y="48" fill="#C74634" font-size="11" text-anchor="end" font-weight="600">-{TARGET_DEMO_SR - CURRENT_DEMO_SR}pp gap</text>
  </svg>
</div>

<div class="two-col">
  <!-- Critical Path -->
  <div class="section">
    <h2>Critical Path Items</h2>
    <ul class="critical-list">
      {''.join(f'<li>{i}</li>' for i in CRITICAL_PATH_ITEMS)}
    </ul>
  </div>
  <!-- Blocking -->
  <div class="section">
    <h2>Blocking Items</h2>
    <ul class="blocking-list">
      {''.join(f'<li>{i}</li>' for i in BLOCKING_ITEMS)}
    </ul>
  </div>
</div>

<!-- Checklist -->
<div class="section">
  <h2>Full Launch Checklist</h2>
  <table class="checklist-table">
    <thead>
      <tr><th>Status</th><th>Item</th><th>Owner</th><th>Due</th><th>Notes</th></tr>
    </thead>
    <tbody>
      {checklist_rows}
    </tbody>
  </table>
</div>

<!-- Endpoints -->
<div class="section">
  <h2>API Endpoints</h2>
  <p style="margin-bottom:0.8rem;"><span class="endpoint">GET /milestones/ai_world</span> — Readiness summary: pct, days remaining, critical path, blocking items</p>
  <p style="margin-bottom:0.8rem;"><span class="endpoint">GET /milestones/checklist</span> — Full checklist with per-item status</p>
  <p><span class="endpoint">GET /health</span> — Service health check</p>
</div>

<div class="footer">OCI Robot Cloud &mdash; Cycle 491A &mdash; AI World Readiness Tracker &mdash; Port 10021</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="AI World Readiness Tracker",
        description="AI World September 2026 launch readiness tracker with checklist and countdown",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_build_dashboard())

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "ai_world_readiness_tracker",
            "port": PORT,
            "timestamp": time.time(),
        })

    @app.get("/milestones/ai_world")
    async def milestones_ai_world() -> JSONResponse:
        return JSONResponse(_readiness_summary())

    @app.get("/milestones/checklist")
    async def milestones_checklist() -> JSONResponse:
        return JSONResponse({
            "total_items": len(CHECKLIST),
            "done": sum(1 for c in CHECKLIST if c["status"] == "DONE"),
            "in_progress": sum(1 for c in CHECKLIST if c["status"] == "IN_PROGRESS"),
            "not_started": sum(1 for c in CHECKLIST if c["status"] == "NOT_STARTED"),
            "blocking": sum(1 for c in CHECKLIST if c["status"] == "BLOCKING"),
            "items": CHECKLIST,
        })


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"status": "ok", "service": "ai_world_readiness_tracker", "port": PORT}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/milestones/ai_world":
            body = json.dumps(_readiness_summary()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/milestones/checklist":
            payload = {
                "total_items": len(CHECKLIST),
                "done": sum(1 for c in CHECKLIST if c["status"] == "DONE"),
                "in_progress": sum(1 for c in CHECKLIST if c["status"] == "IN_PROGRESS"),
                "not_started": sum(1 for c in CHECKLIST if c["status"] == "NOT_STARTED"),
                "blocking": sum(1 for c in CHECKLIST if c["status"] == "BLOCKING"),
                "items": CHECKLIST,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = _build_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[ai_world_readiness_tracker] FastAPI not available — falling back to HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _FallbackHandler)
        print(f"[ai_world_readiness_tracker] Serving on http://0.0.0.0:{PORT}")
        server.serve_forever()
