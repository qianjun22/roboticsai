"""CS playbook v2 — lifecycle playbooks for onboarding (day 0-30, SR>65% milestone), growth (day 30-90, expansion proposal), expansion (day 90+, renewal prep), quarterly EBR.
FastAPI service — OCI Robot Cloud
Port: 10143"""
from __future__ import annotations
import json, random, time
from datetime import datetime
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10143

PHASES = {
    "onboarding": {"day_range": [0, 30], "milestone": "SR>65%", "plays": ["setup_call", "first_task_config", "sr_checkpoint"]},
    "growth": {"day_range": [30, 90], "milestone": "expansion_proposal", "plays": ["qbr_prep", "upsell_discovery", "sr_review"]},
    "expansion": {"day_range": [90, 365], "milestone": "renewal_prep", "plays": ["renewal_90d_out", "ebr_scheduling", "roi_report"]},
}

SAMPLE_CUSTOMERS = [
    {"id": "c001", "name": "Acme Robotics", "day": 15, "sr": 0.58, "status": "at_risk"},
    {"id": "c002", "name": "BetaBot Inc", "day": 45, "sr": 0.78, "status": "on_track"},
    {"id": "c003", "name": "Gamma Automation", "day": 120, "sr": 0.89, "status": "on_track"},
    {"id": "c004", "name": "Delta Systems", "day": 22, "sr": 0.62, "status": "at_risk"},
]

def get_phase(day: int) -> str:
    for phase, info in PHASES.items():
        lo, hi = info["day_range"]
        if lo <= day < hi:
            return phase
    return "expansion"

def get_risk_flags(day: int, sr: float) -> list:
    flags = []
    phase = get_phase(day)
    if phase == "onboarding" and sr < 0.65:
        flags.append("SR below 65% milestone — escalate to CSM")
    if phase == "growth" and sr < 0.70:
        flags.append("SR lagging growth phase target — review task config")
    if day > 270 and sr < 0.80:
        flags.append("Renewal risk — SR below retention threshold")
    return flags

if USE_FASTAPI:
    app = FastAPI(title="Customer Success Playbook v2", version="2.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Customer Success Playbook v2</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Customer Success Playbook v2</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/cs/playbook")
    def playbook(customer_id: str, day_in_lifecycle: int, sr: float = 0.75):
        phase = get_phase(day_in_lifecycle)
        info = PHASES[phase]
        next_phase_day = info["day_range"][1]
        days_to_next = max(0, next_phase_day - day_in_lifecycle)
        risk_flags = get_risk_flags(day_in_lifecycle, sr)
        return JSONResponse({
            "customer_id": customer_id,
            "day_in_lifecycle": day_in_lifecycle,
            "current_phase": phase,
            "active_plays": info["plays"],
            "next_milestone": info["milestone"],
            "days_to_next_phase": days_to_next,
            "risk_flags": risk_flags,
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/cs/health_summary")
    def health_summary():
        at_risk = [c for c in SAMPLE_CUSTOMERS if c["status"] == "at_risk"]
        on_track = [c for c in SAMPLE_CUSTOMERS if c["status"] == "on_track"]
        milestone_status = [
            {
                "id": c["id"],
                "name": c["name"],
                "phase": get_phase(c["day"]),
                "milestone": PHASES[get_phase(c["day"])]["milestone"],
                "sr": c["sr"],
                "risk_flags": get_risk_flags(c["day"], c["sr"]),
            }
            for c in SAMPLE_CUSTOMERS
        ]
        return JSONResponse({
            "total_customers": len(SAMPLE_CUSTOMERS),
            "at_risk_count": len(at_risk),
            "on_track_count": len(on_track),
            "at_risk": [{"id": c["id"], "name": c["name"]} for c in at_risk],
            "milestone_status": milestone_status,
            "ts": datetime.utcnow().isoformat(),
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
