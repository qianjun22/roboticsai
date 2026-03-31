"""AI World September 14 2026 countdown — 168 days from 2026-03-30, critical path tracking
FastAPI service — OCI Robot Cloud
Port: 10155"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, date
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10155
EVENT_DATE = date(2026, 9, 14)
BASELINE_DATE = date(2026, 3, 30)
BASELINE_DAYS = (EVENT_DATE - BASELINE_DATE).days  # 168

# Critical path milestones
CRITICAL_PATH = [
    {
        "id": "nvidia_intro",
        "name": "NVIDIA Intro / Partnership Confirmed",
        "deadline": "2026-04-30",
        "status": "in_progress",
        "owner": "BD",
        "risk": "high",
        "days_to_deadline": (date(2026, 4, 30) - BASELINE_DATE).days,
    },
    {
        "id": "data_room",
        "name": "Data Room Ready for NVIDIA Review",
        "deadline": "2026-05-15",
        "status": "not_started",
        "owner": "Engineering + PM",
        "risk": "medium",
        "days_to_deadline": (date(2026, 5, 15) - BASELINE_DATE).days,
    },
    {
        "id": "demo_video",
        "name": "Demo Video (2-min highlight reel)",
        "deadline": "2026-07-01",
        "status": "not_started",
        "owner": "Marketing + Engineering",
        "risk": "medium",
        "days_to_deadline": (date(2026, 7, 1) - BASELINE_DATE).days,
    },
    {
        "id": "press_kit",
        "name": "Press Kit + Analyst Brief",
        "deadline": "2026-08-01",
        "status": "not_started",
        "owner": "Marketing",
        "risk": "low",
        "days_to_deadline": (date(2026, 8, 1) - BASELINE_DATE).days,
    },
    {
        "id": "booth",
        "name": "Booth Design + Hardware Shipped",
        "deadline": "2026-08-15",
        "status": "not_started",
        "owner": "Events",
        "risk": "medium",
        "days_to_deadline": (date(2026, 8, 15) - BASELINE_DATE).days,
    },
]

def _days_remaining() -> int:
    today = date.today()
    delta = (EVENT_DATE - today).days
    return max(delta, 0)

def _at_risk_milestones(today: date) -> list:
    at_risk = []
    for m in CRITICAL_PATH:
        deadline = date.fromisoformat(m["deadline"])
        days_left = (deadline - today).days
        if m["status"] != "done" and (days_left < 21 or m["risk"] == "high"):
            at_risk.append({
                "id": m["id"],
                "name": m["name"],
                "days_to_deadline": days_left,
                "risk": m["risk"],
                "status": m["status"],
            })
    return at_risk

def _readiness_score(today: date) -> float:
    done = sum(1 for m in CRITICAL_PATH if m["status"] == "done")
    in_progress = sum(1 for m in CRITICAL_PATH if m["status"] == "in_progress")
    total = len(CRITICAL_PATH)
    base = (done + 0.4 * in_progress) / total
    # Time pressure penalty: if <60 days remain, penalize
    days_left = (EVENT_DATE - today).days
    time_factor = min(days_left / 60.0, 1.0)
    return round(min(base * time_factor + base * 0.3, 1.0), 3)

def _blockers(today: date) -> list:
    blockers = []
    for m in CRITICAL_PATH:
        deadline = date.fromisoformat(m["deadline"])
        days_left = (deadline - today).days
        if m["status"] == "not_started" and days_left < 45:
            blockers.append(f"{m['name']} not started with {days_left}d to deadline")
        elif m["risk"] == "high" and m["status"] != "done":
            blockers.append(f"{m['name']} is HIGH RISK and not yet complete")
    return blockers

def _next_actions(today: date) -> list:
    actions = []
    for m in sorted(CRITICAL_PATH, key=lambda x: x["deadline"]):
        if m["status"] != "done":
            actions.append({
                "milestone": m["name"],
                "action": f"Advance '{m['id']}' from '{m['status']}' → next stage",
                "owner": m["owner"],
                "deadline": m["deadline"],
            })
        if len(actions) >= 3:
            break
    return actions

if USE_FASTAPI:
    app = FastAPI(title="AI World Countdown Tracker", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        days_left = _days_remaining()
        return HTMLResponse(
            f"<html><head><title>AI World Countdown Tracker</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}.days{{font-size:3rem;font-weight:bold;color:#38bdf8}}</style></head>"
            f"<body><h1>AI World Countdown Tracker</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<div class='days'>{days_left} days</div>"
            f"<p>until AI World — September 14, 2026</p>"
            f"<p><a href='/docs'>API Docs</a> · "
            f"<a href='/events/ai_world/countdown'>Countdown</a> · "
            f"<a href='/events/ai_world/readiness'>Readiness</a></p></body></html>"
        )

    @app.get("/events/ai_world/countdown")
    def countdown():
        """Days remaining, critical path status, at-risk milestones, next actions."""
        today = date.today()
        days_left = _days_remaining()
        return {
            "event": "AI World",
            "event_date": str(EVENT_DATE),
            "days_remaining": days_left,
            "baseline_days": BASELINE_DAYS,
            "pct_elapsed": round(1 - days_left / BASELINE_DAYS, 3) if BASELINE_DAYS > 0 else 1.0,
            "critical_path_status": CRITICAL_PATH,
            "at_risk_milestones": _at_risk_milestones(today),
            "next_actions": _next_actions(today),
        }

    @app.get("/events/ai_world/readiness")
    def readiness():
        """Readiness score, blockers, and confidence of launch."""
        today = date.today()
        score = _readiness_score(today)
        blockers = _blockers(today)
        confidence = "high" if score >= 0.75 else ("medium" if score >= 0.45 else "low")
        return {
            "event": "AI World",
            "event_date": str(EVENT_DATE),
            "days_remaining": _days_remaining(),
            "readiness_score": score,
            "readiness_pct": f"{round(score * 100, 1)}%",
            "blockers": blockers,
            "confidence_of_launch": confidence,
            "milestones_done": sum(1 for m in CRITICAL_PATH if m["status"] == "done"),
            "milestones_total": len(CRITICAL_PATH),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a):
            pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
