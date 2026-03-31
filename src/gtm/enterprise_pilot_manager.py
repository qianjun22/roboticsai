"""30-day enterprise pilot manager — week-by-week milestones (W1: first eval / W2: baseline SR / W3: fine-tune / W4: production readiness).
FastAPI service — OCI Robot Cloud
Port: 10147"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10147

# Pilot outcome thresholds
CONVERT_THRESHOLD = 0.65    # >65% SR → convert to production
EXTEND_THRESHOLD = 0.50     # 50-65% SR → extend pilot
# <50% SR at W3 → cancel

PILOT_ROI = 16.6  # 16.6× ROI for converted pilots

WEEK_MILESTONES = {
    1: "First eval run — baseline measurement, environment setup, integration check",
    2: "Baseline SR established — task success rate across 20 episodes, gap analysis",
    3: "Fine-tune complete — custom dataset collected, GR00T fine-tune finished, SR re-evaluated",
    4: "Production readiness — load test, latency SLA verified, go/no-go decision",
}

# In-memory pilot registry
_pilots: dict[str, dict] = {}

def _make_pilot(customer_id: str) -> dict:
    start = datetime.utcnow()
    return {
        "pilot_id": f"pilot-{customer_id}-{int(start.timestamp())}",
        "customer_id": customer_id,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=30)).isoformat(),
        "week": 1,
        "milestones": WEEK_MILESTONES,
        "current_sr": None,
        "outcome_projection": "pending",
        "w3_decision": None,
        "roi_estimate": PILOT_ROI,
    }

def _project_outcome(sr: float | None, week: int) -> str:
    if sr is None:
        return "pending"
    if week >= 3:
        if sr > CONVERT_THRESHOLD:
            return "convert"
        elif sr >= EXTEND_THRESHOLD:
            return "extend"
        else:
            return "cancel"
    # Early weeks: optimistic projection based on trajectory
    if sr > 0.60:
        return "likely_convert"
    elif sr > 0.45:
        return "likely_extend"
    return "at_risk"

if USE_FASTAPI:
    app = FastAPI(title="Enterprise Pilot Manager", version="1.0.0")

    class KickoffRequest(BaseModel):
        customer_id: str

    class StatusRequest(BaseModel):
        pilot_id: str
        current_sr: float | None = None

    @app.get("/pilots/status")
    def pilot_status(pilot_id: str, current_sr: float | None = None):
        if pilot_id not in _pilots:
            raise HTTPException(status_code=404, detail=f"Pilot {pilot_id!r} not found")
        p = _pilots[pilot_id]
        # Update SR if provided
        if current_sr is not None:
            p["current_sr"] = round(current_sr, 4)
        # Compute elapsed week
        start = datetime.fromisoformat(p["start_date"])
        elapsed_days = (datetime.utcnow() - start).days
        p["week"] = min(4, max(1, (elapsed_days // 7) + 1))
        p["outcome_projection"] = _project_outcome(p["current_sr"], p["week"])
        # W3 decision
        if p["week"] >= 3 and p["current_sr"] is not None:
            if p["current_sr"] > CONVERT_THRESHOLD:
                p["w3_decision"] = "convert — SR exceeds 65% threshold"
            elif p["current_sr"] >= EXTEND_THRESHOLD:
                p["w3_decision"] = "extend — SR between 50-65%; continue 2 more weeks"
            else:
                p["w3_decision"] = "cancel — SR below 50% at W3"
        return {
            "pilot_id": p["pilot_id"],
            "customer_id": p["customer_id"],
            "week": p["week"],
            "milestones": WEEK_MILESTONES,
            "current_sr": p["current_sr"],
            "outcome_projection": p["outcome_projection"],
            "w3_decision": p["w3_decision"],
            "roi_estimate": PILOT_ROI,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.post("/pilots/kickoff")
    def kickoff(req: KickoffRequest):
        pilot = _make_pilot(req.customer_id)
        _pilots[pilot["pilot_id"]] = pilot
        return {
            "pilot_id": pilot["pilot_id"],
            "pilot_plan": {
                "duration_days": 30,
                "weeks": WEEK_MILESTONES,
                "convert_threshold_sr": CONVERT_THRESHOLD,
                "extend_threshold_sr": EXTEND_THRESHOLD,
                "cancel_condition": "SR < 50% at end of W3",
            },
            "success_criteria": {
                "primary": f"SR > {CONVERT_THRESHOLD:.0%} by W4",
                "secondary": "Latency < 300ms p95, uptime > 99.5%",
                "roi_target": f"{PILOT_ROI}× ROI on fine-tuning investment",
            },
            "timeline": {
                "start": pilot["start_date"],
                "w1_end": (datetime.fromisoformat(pilot["start_date"]) + timedelta(days=7)).isoformat(),
                "w2_end": (datetime.fromisoformat(pilot["start_date"]) + timedelta(days=14)).isoformat(),
                "w3_end": (datetime.fromisoformat(pilot["start_date"]) + timedelta(days=21)).isoformat(),
                "w4_end": pilot["end_date"],
            },
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Enterprise Pilot Manager</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Enterprise Pilot Manager</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>30-day pilot · Convert &gt;65% SR · Extend 50-65% · Cancel &lt;50% at W3 · ROI 16.6×</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

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
