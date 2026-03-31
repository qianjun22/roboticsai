"""series_a_investor_tracker.py — Series A VC Relationship CRM (port 10027)

Cycle-492B service: track 15 target investors through pipeline stages toward Series A close.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

PORT = 10027
TODAY = date(2026, 3, 30)

# Stage ordering for pipeline progression
STAGE_ORDER = ["identified", "contacted", "first_call", "partner_meeting", "dd", "term_sheet", "closed"]

INVESTORS: List[Dict[str, Any]] = [
    {"id": "a16z_bio",        "name": "a16z Bio + Health",     "firm": "Andreessen Horowitz", "fit_score": 9.4, "stage": "partner_meeting", "last_contact": "2026-03-18", "next_step": "Partner presentation Mar 31",     "focus": "AI + robotics"},
    {"id": "sequoia_ent",     "name": "Sequoia Enterprise",    "firm": "Sequoia Capital",      "fit_score": 9.1, "stage": "partner_meeting", "last_contact": "2026-03-20", "next_step": "Follow-up deck by Apr 2",        "focus": "infrastructure AI"},
    {"id": "gv_lead",         "name": "GV (Google Ventures)",  "firm": "GV",                  "fit_score": 8.9, "stage": "first_call",     "last_contact": "2026-03-15", "next_step": "Technical deep-dive Apr 5",     "focus": "robotics cloud"},
    {"id": "nea_tech",        "name": "NEA Tech Growth",       "firm": "New Enterprise Assoc", "fit_score": 8.7, "stage": "first_call",     "last_contact": "2026-03-12", "next_step": "Send benchmark results",       "focus": "enterprise SaaS"},
    {"id": "accel_cloud",     "name": "Accel Cloud Fund",      "firm": "Accel",               "fit_score": 8.6, "stage": "first_call",     "last_contact": "2026-03-22", "next_step": "Schedule partner meeting",    "focus": "cloud infrastructure"},
    {"id": "lightspeed_ai",   "name": "Lightspeed AI",         "firm": "Lightspeed VP",       "fit_score": 8.4, "stage": "contacted",     "last_contact": "2026-03-08", "next_step": "Nudge for intro call",        "focus": "AI infrastructure"},
    {"id": "ins_capital",     "name": "Insight Partners",      "firm": "Insight Partners",    "fit_score": 8.2, "stage": "contacted",     "last_contact": "2026-03-10", "next_step": "Send one-pager",             "focus": "growth B2B"},
    {"id": "nvda_ventures",   "name": "NVentures (NVIDIA)",    "firm": "NVIDIA Ventures",     "fit_score": 8.1, "stage": "contacted",     "last_contact": "2026-03-05", "next_step": "Follow up after GTC",       "focus": "robotics AI chips"},
    {"id": "oci_ventures",    "name": "OCI Strategic",         "firm": "Oracle Ventures",     "fit_score": 7.9, "stage": "contacted",     "last_contact": "2026-03-01", "next_step": "Internal alignment needed",  "focus": "cloud AI"},
    {"id": "felicis_ai",      "name": "Felicis AI Fund",       "firm": "Felicis Ventures",    "fit_score": 7.8, "stage": "contacted",     "last_contact": "2026-02-28", "next_step": "Re-engage post product demo","focus": "AI-first startups"},
    {"id": "bmark_tech",      "name": "Benchmark Technology",  "firm": "Benchmark",           "fit_score": 7.5, "stage": "identified",   "last_contact": "2026-02-15", "next_step": "Get warm intro via network", "focus": "developer tools"},
    {"id": "greylock_ml",     "name": "Greylock ML Fund",      "firm": "Greylock",            "fit_score": 7.4, "stage": "identified",   "last_contact": "2026-02-10", "next_step": "Research GP fit",           "focus": "ML systems"},
    {"id": "redpoint_infra",  "name": "Redpoint Infra",        "firm": "Redpoint",            "fit_score": 7.2, "stage": "identified",   "last_contact": "2026-01-30", "next_step": "Attend their portfolio day","focus": "cloud infra"},
    {"id": "index_deep",      "name": "Index Deep Tech",       "firm": "Index Ventures",      "fit_score": 7.1, "stage": "identified",   "last_contact": "2026-01-25", "next_step": "Cold outreach via LinkedIn", "focus": "deep tech"},
    {"id": "coatue_ai",       "name": "Coatue AI Crossover",   "firm": "Coatue Management",   "fit_score": 6.9, "stage": "identified",   "last_contact": "2026-01-20", "next_step": "Monitor for interest signals","focus": "AI crossover"},
]

# In-memory activity log
ACTIVITY_LOG: List[Dict[str, Any]] = []

STAGE_NEXT_ACTION: Dict[str, str] = {
    "identified":     "Research GP fit and get warm intro",
    "contacted":      "Follow up and schedule intro call",
    "first_call":     "Send materials and schedule partner meeting",
    "partner_meeting":"Prepare detailed deck and anticipate DD questions",
    "dd":             "Provide data room access and respond to diligence",
    "term_sheet":     "Negotiate terms and run competitive process",
    "closed":         "Onboard investor and plan quarterly updates",
}


def days_since(date_str: str) -> int:
    d = date.fromisoformat(date_str)
    return (TODAY - d).days


def get_investors_by_stage(stage: Optional[str]) -> List[Dict[str, Any]]:
    pool = INVESTORS if not stage else [i for i in INVESTORS if i["stage"] == stage]
    return [
        {**inv, "days_since_contact": days_since(inv["last_contact"])}
        for inv in pool
    ]


def log_activity(investor_id: str, activity_type: str, notes: str) -> Dict[str, Any]:
    inv = next((i for i in INVESTORS if i["id"] == investor_id), None)
    if inv is None:
        return {"error": f"investor '{investor_id}' not found"}
    # Advance stage on key activity types
    advance_on = {"first_call", "partner_meeting", "term_sheet", "signed"}
    current_idx = STAGE_ORDER.index(inv["stage"])
    if activity_type in advance_on and current_idx < len(STAGE_ORDER) - 1:
        inv["stage"] = STAGE_ORDER[current_idx + 1]
    inv["last_contact"] = TODAY.isoformat()
    ACTIVITY_LOG.append({
        "investor_id": investor_id,
        "activity_type": activity_type,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "updated_stage": inv["stage"],
        "next_recommended_action": STAGE_NEXT_ACTION.get(inv["stage"], "TBD"),
        "days_since_contact": 0,
    }


HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Series A Investor Tracker</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card-label { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card-value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; }
    .card-value.red { color: #C74634; }
    .card-value.green { color: #4ade80; }
    .card-value.yellow { color: #fbbf24; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th { color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; font-weight: 500; }
    td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; vertical-align: top; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; white-space: nowrap; }
    .s-identified    { background: #1e293b; color: #64748b; border: 1px solid #475569; }
    .s-contacted     { background: #172554; color: #93c5fd; }
    .s-first_call    { background: #0c4a6e; color: #38bdf8; }
    .s-partner_meeting { background: #431407; color: #fdba74; }
    .s-dd            { background: #3b0764; color: #d8b4fe; }
    .s-term_sheet    { background: #052e16; color: #4ade80; }
    .s-closed        { background: #064e3b; color: #6ee7b7; }
    .timeline { display: flex; gap: 0; margin-top: 0.5rem; }
    .tl-item { flex: 1; text-align: center; }
    .tl-dot { width: 12px; height: 12px; border-radius: 50%; margin: 0 auto 4px; }
    .tl-dot.done { background: #4ade80; }
    .tl-dot.active { background: #C74634; }
    .tl-dot.future { background: #334155; }
    .tl-line { height: 2px; background: #334155; margin-top: -8px; }
    .tl-label { font-size: 0.68rem; color: #64748b; margin-top: 2px; }
    .tl-date { font-size: 0.65rem; color: #94a3b8; }
    .fit-bar { display: inline-block; height: 6px; border-radius: 3px; background: #38bdf8; vertical-align: middle; margin-left: 4px; }
  </style>
</head>
<body>
  <h1>Series A Investor Tracker</h1>
  <p class="subtitle">OCI Robot Cloud &nbsp;|&nbsp; Target: $15M Series A &nbsp;|&nbsp; Timeline: Mar 2026 → Close Jan 2027 &nbsp;|&nbsp; Port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="card-label">Total Targets</div><div class="card-value">15</div></div>
    <div class="card"><div class="card-label">Contacted</div><div class="card-value">5</div></div>
    <div class="card"><div class="card-label">First Call</div><div class="card-value yellow">3</div></div>
    <div class="card"><div class="card-label">Partner Meeting</div><div class="card-value red">2</div></div>
    <div class="card"><div class="card-label">Term Sheet</div><div class="card-value green">0</div></div>
    <div class="card"><div class="card-label">Target Close</div><div class="card-value" style="font-size:1.1rem">Jan 2027</div></div>
  </div>

  <div class="section">
    <h2>Pipeline Stage Distribution (SVG Bar Chart)</h2>
    <svg viewBox="0 0 620 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:620px;display:block;">
      <!-- axes -->
      <line x1="50" y1="10" x2="50" y2="165" stroke="#475569" stroke-width="1"/>
      <line x1="50" y1="165" x2="600" y2="165" stroke="#475569" stroke-width="1"/>
      <!-- y grid -->
      <text x="45" y="165" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="45" y="125" fill="#64748b" font-size="10" text-anchor="end">2</text>
      <line x1="50" y1="125" x2="600" y2="125" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
      <text x="45" y="85" fill="#64748b" font-size="10" text-anchor="end">4</text>
      <line x1="50" y1="85" x2="600" y2="85" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
      <text x="45" y="45" fill="#64748b" font-size="10" text-anchor="end">6</text>
      <line x1="50" y1="45" x2="600" y2="45" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
      <!-- bars: scale 1 unit = 20px, bar width=60, spacing=80 -->
      <!-- identified: 5 → height=100, top=65 -->
      <rect x="60" y="65" width="60" height="100" fill="#475569" rx="3"/>
      <text x="90" y="60" fill="#94a3b8" font-size="11" text-anchor="middle">5</text>
      <text x="90" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">Identified</text>
      <!-- contacted: 5 → height=100 -->
      <rect x="140" y="65" width="60" height="100" fill="#3b82f6" rx="3"/>
      <text x="170" y="60" fill="#93c5fd" font-size="11" text-anchor="middle">5</text>
      <text x="170" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">Contacted</text>
      <!-- first_call: 3 → height=60, top=105 -->
      <rect x="220" y="105" width="60" height="60" fill="#38bdf8" rx="3"/>
      <text x="250" y="100" fill="#7dd3fc" font-size="11" text-anchor="middle">3</text>
      <text x="250" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">First Call</text>
      <!-- partner_meeting: 2 → height=40, top=125 -->
      <rect x="300" y="125" width="60" height="40" fill="#fb923c" rx="3"/>
      <text x="330" y="120" fill="#fdba74" font-size="11" text-anchor="middle">2</text>
      <text x="330" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">Partner Mtg</text>
      <!-- dd: 0 -->
      <rect x="380" y="165" width="60" height="0" fill="#a855f7" rx="3"/>
      <text x="410" y="160" fill="#d8b4fe" font-size="11" text-anchor="middle">0</text>
      <text x="410" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">DD</text>
      <!-- term_sheet: 0 -->
      <rect x="460" y="165" width="60" height="0" fill="#4ade80" rx="3"/>
      <text x="490" y="160" fill="#86efac" font-size="11" text-anchor="middle">0</text>
      <text x="490" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">Term Sheet</text>
      <!-- closed: 0 -->
      <rect x="530" y="165" width="60" height="0" fill="#6ee7b7" rx="3"/>
      <text x="560" y="160" fill="#6ee7b7" font-size="11" text-anchor="middle">0</text>
      <text x="560" y="183" fill="#94a3b8" font-size="10" text-anchor="middle">Closed</text>
    </svg>
  </div>

  <div class="section">
    <h2>Series A Timeline</h2>
    <div style="display:flex;align-items:flex-start;gap:0;margin-top:0.5rem;">
      <div style="flex:1;text-align:center">
        <div style="width:14px;height:14px;border-radius:50%;background:#4ade80;margin:0 auto 4px;"></div>
        <div style="font-size:0.72rem;color:#4ade80;font-weight:600;">Mar 2026</div>
        <div style="font-size:0.65rem;color:#94a3b8;">Outreach begins</div>
      </div>
      <div style="flex:1;height:2px;background:#334155;margin-top:6px;"></div>
      <div style="flex:1;text-align:center">
        <div style="width:14px;height:14px;border-radius:50%;background:#C74634;margin:0 auto 4px;"></div>
        <div style="font-size:0.72rem;color:#C74634;font-weight:600;">May 2026</div>
        <div style="font-size:0.65rem;color:#94a3b8;">Partner meetings</div>
      </div>
      <div style="flex:1;height:2px;background:#334155;margin-top:6px;"></div>
      <div style="flex:1;text-align:center">
        <div style="width:14px;height:14px;border-radius:50%;background:#475569;margin:0 auto 4px;"></div>
        <div style="font-size:0.72rem;color:#94a3b8;font-weight:600;">Jul 2026</div>
        <div style="font-size:0.65rem;color:#94a3b8;">DD + term sheets</div>
      </div>
      <div style="flex:1;height:2px;background:#334155;margin-top:6px;"></div>
      <div style="flex:1;text-align:center">
        <div style="width:14px;height:14px;border-radius:50%;background:#475569;margin:0 auto 4px;"></div>
        <div style="font-size:0.72rem;color:#94a3b8;font-weight:600;">Oct 2026</div>
        <div style="font-size:0.65rem;color:#94a3b8;">Negotiate &amp; finalize</div>
      </div>
      <div style="flex:1;height:2px;background:#334155;margin-top:6px;"></div>
      <div style="flex:1;text-align:center">
        <div style="width:14px;height:14px;border-radius:50%;background:#475569;margin:0 auto 4px;"></div>
        <div style="font-size:0.72rem;color:#94a3b8;font-weight:600;">Jan 2027</div>
        <div style="font-size:0.65rem;color:#94a3b8;">Close $15M</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Top 15 Target Investors — by Fit Score</h2>
    <table>
      <thead><tr><th>#</th><th>Investor / Firm</th><th>Fit Score</th><th>Stage</th><th>Last Contact</th><th>Next Step</th></tr></thead>
      <tbody>
        <tr><td>1</td><td><strong>a16z Bio + Health</strong><br><span style="color:#64748b;font-size:0.75rem;">Andreessen Horowitz</span></td><td>9.4 <span class="fit-bar" style="width:94px"></span></td><td><span class="badge s-partner_meeting">partner meeting</span></td><td>Mar 18</td><td>Partner presentation Mar 31</td></tr>
        <tr><td>2</td><td><strong>Sequoia Enterprise</strong><br><span style="color:#64748b;font-size:0.75rem;">Sequoia Capital</span></td><td>9.1 <span class="fit-bar" style="width:91px"></span></td><td><span class="badge s-partner_meeting">partner meeting</span></td><td>Mar 20</td><td>Follow-up deck by Apr 2</td></tr>
        <tr><td>3</td><td><strong>GV (Google Ventures)</strong><br><span style="color:#64748b;font-size:0.75rem;">GV</span></td><td>8.9 <span class="fit-bar" style="width:89px"></span></td><td><span class="badge s-first_call">first call</span></td><td>Mar 15</td><td>Technical deep-dive Apr 5</td></tr>
        <tr><td>4</td><td><strong>NEA Tech Growth</strong><br><span style="color:#64748b;font-size:0.75rem;">New Enterprise Assoc</span></td><td>8.7 <span class="fit-bar" style="width:87px"></span></td><td><span class="badge s-first_call">first call</span></td><td>Mar 12</td><td>Send benchmark results</td></tr>
        <tr><td>5</td><td><strong>Accel Cloud Fund</strong><br><span style="color:#64748b;font-size:0.75rem;">Accel</span></td><td>8.6 <span class="fit-bar" style="width:86px"></span></td><td><span class="badge s-first_call">first call</span></td><td>Mar 22</td><td>Schedule partner meeting</td></tr>
        <tr><td>6</td><td><strong>Lightspeed AI</strong><br><span style="color:#64748b;font-size:0.75rem;">Lightspeed VP</span></td><td>8.4 <span class="fit-bar" style="width:84px"></span></td><td><span class="badge s-contacted">contacted</span></td><td>Mar 8</td><td>Nudge for intro call</td></tr>
        <tr><td>7</td><td><strong>Insight Partners</strong><br><span style="color:#64748b;font-size:0.75rem;">Insight Partners</span></td><td>8.2 <span class="fit-bar" style="width:82px"></span></td><td><span class="badge s-contacted">contacted</span></td><td>Mar 10</td><td>Send one-pager</td></tr>
        <tr><td>8</td><td><strong>NVentures (NVIDIA)</strong><br><span style="color:#64748b;font-size:0.75rem;">NVIDIA Ventures</span></td><td>8.1 <span class="fit-bar" style="width:81px"></span></td><td><span class="badge s-contacted">contacted</span></td><td>Mar 5</td><td>Follow up after GTC</td></tr>
        <tr><td>9</td><td><strong>OCI Strategic</strong><br><span style="color:#64748b;font-size:0.75rem;">Oracle Ventures</span></td><td>7.9 <span class="fit-bar" style="width:79px"></span></td><td><span class="badge s-contacted">contacted</span></td><td>Mar 1</td><td>Internal alignment needed</td></tr>
        <tr><td>10</td><td><strong>Felicis AI Fund</strong><br><span style="color:#64748b;font-size:0.75rem;">Felicis Ventures</span></td><td>7.8 <span class="fit-bar" style="width:78px"></span></td><td><span class="badge s-contacted">contacted</span></td><td>Feb 28</td><td>Re-engage post product demo</td></tr>
        <tr><td>11</td><td><strong>Benchmark Technology</strong><br><span style="color:#64748b;font-size:0.75rem;">Benchmark</span></td><td>7.5 <span class="fit-bar" style="width:75px"></span></td><td><span class="badge s-identified">identified</span></td><td>Feb 15</td><td>Get warm intro via network</td></tr>
        <tr><td>12</td><td><strong>Greylock ML Fund</strong><br><span style="color:#64748b;font-size:0.75rem;">Greylock</span></td><td>7.4 <span class="fit-bar" style="width:74px"></span></td><td><span class="badge s-identified">identified</span></td><td>Feb 10</td><td>Research GP fit</td></tr>
        <tr><td>13</td><td><strong>Redpoint Infra</strong><br><span style="color:#64748b;font-size:0.75rem;">Redpoint</span></td><td>7.2 <span class="fit-bar" style="width:72px"></span></td><td><span class="badge s-identified">identified</span></td><td>Jan 30</td><td>Attend their portfolio day</td></tr>
        <tr><td>14</td><td><strong>Index Deep Tech</strong><br><span style="color:#64748b;font-size:0.75rem;">Index Ventures</span></td><td>7.1 <span class="fit-bar" style="width:71px"></span></td><td><span class="badge s-identified">identified</span></td><td>Jan 25</td><td>Cold outreach via LinkedIn</td></tr>
        <tr><td>15</td><td><strong>Coatue AI Crossover</strong><br><span style="color:#64748b;font-size:0.75rem;">Coatue Management</span></td><td>6.9 <span class="fit-bar" style="width:69px"></span></td><td><span class="badge s-identified">identified</span></td><td>Jan 20</td><td>Monitor for interest signals</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><span class="badge" style="background:#0c4a6e;color:#38bdf8;">GET</span></td><td>/</td><td>This dashboard</td></tr>
        <tr><td><span class="badge" style="background:#0c4a6e;color:#38bdf8;">GET</span></td><td>/health</td><td>Health check JSON</td></tr>
        <tr><td><span class="badge" style="background:#0c4a6e;color:#38bdf8;">GET</span></td><td>/investors/pipeline?stage=&lt;stage&gt;</td><td>Investors at pipeline stage</td></tr>
        <tr><td><span class="badge" style="background:#450a0a;color:#fca5a5;">POST</span></td><td>/investors/log_activity</td><td>Log investor touchpoint &amp; advance stage</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _USE_FASTAPI:
    app = FastAPI(
        title="Series A Investor Tracker",
        description="VC relationship CRM — 15 target investors, Series A pipeline",
        version="1.0.0",
    )

    class LogActivityRequest(BaseModel):
        investor_id: str
        activity_type: str
        notes: str

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML_DASHBOARD

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "service": "series_a_investor_tracker",
            "port": PORT,
            "investors_tracked": len(INVESTORS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.get("/investors/pipeline")
    async def pipeline(stage: Optional[str] = Query(default=None)):
        if stage and stage not in STAGE_ORDER:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid stage. Must be one of: {', '.join(STAGE_ORDER)}",
            )
        return JSONResponse({"investors": get_investors_by_stage(stage), "stage_filter": stage})

    @app.post("/investors/log_activity")
    async def log_activity_endpoint(req: LogActivityRequest):
        result = log_activity(req.investor_id, req.activity_type, req.notes)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(result)

else:
    # stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, content_type: str, body: str):
            encoded = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                self._send(200, "application/json", json.dumps(
                    {"status": "ok", "service": "series_a_investor_tracker", "port": PORT}
                ))
            elif path == "/investors/pipeline":
                stage = params.get("stage", [None])[0]
                self._send(200, "application/json", json.dumps(
                    {"investors": get_investors_by_stage(stage), "stage_filter": stage}
                ))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/investors/log_activity":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length))
                result = log_activity(
                    data.get("investor_id", ""),
                    data.get("activity_type", ""),
                    data.get("notes", ""),
                )
                code = 404 if "error" in result else 200
                self._send(code, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — falling back to stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
