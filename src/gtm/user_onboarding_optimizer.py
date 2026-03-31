"""A/B test onboarding flows — 4 variants (docs-first 52% / quickstart-first 78% / guided-tour 71% / video-first 67%). Activation = first eval SR>50%. Tracks time-to-activate (quickstart: 3.2 days best).
FastAPI service — OCI Robot Cloud
Port: 10115"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI, Body
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10115

_VARIANTS = {
    "docs-first": {
        "activation_rate": 0.52,
        "time_to_activate_days": 5.1,
        "dropoff_points": ["api-reference", "sdk-install", "first-eval"],
        "recommended_improvements": [
            "Add interactive code snippets to docs",
            "Surface quickstart link earlier",
            "Add progress indicator",
        ],
    },
    "quickstart-first": {
        "activation_rate": 0.78,
        "time_to_activate_days": 3.2,
        "dropoff_points": ["env-setup", "first-eval"],
        "recommended_improvements": [
            "Pre-warm demo environment to cut env-setup drop",
            "Add one-click Colab link",
        ],
    },
    "guided-tour": {
        "activation_rate": 0.71,
        "time_to_activate_days": 4.0,
        "dropoff_points": ["step-3-config", "first-eval"],
        "recommended_improvements": [
            "Shorten tour to 5 steps max",
            "Allow skipping config step",
        ],
    },
    "video-first": {
        "activation_rate": 0.67,
        "time_to_activate_days": 4.5,
        "dropoff_points": ["post-video-cta", "sdk-install", "first-eval"],
        "recommended_improvements": [
            "Add in-video code copy buttons",
            "Send follow-up email 24h after video watch",
        ],
    },
}

_FUNNEL_STAGES = ["signup", "docs-or-video", "sdk-install", "env-setup", "first-eval", "activated"]

_USER_EVENTS: dict[str, list[dict]] = {}

def _next_step(current_stage: str) -> str:
    try:
        idx = _FUNNEL_STAGES.index(current_stage)
        return _FUNNEL_STAGES[min(idx + 1, len(_FUNNEL_STAGES) - 1)]
    except ValueError:
        return _FUNNEL_STAGES[0]

if USE_FASTAPI:
    app = FastAPI(title="User Onboarding Optimizer", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>User Onboarding Optimizer</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>User Onboarding Optimizer</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p></body></html>""")

    @app.get("/onboarding/optimizer")
    def optimizer(variant: str = "quickstart-first"):
        """
        Return activation metrics and recommendations for a given onboarding variant.
        variant: docs-first | quickstart-first | guided-tour | video-first
        """
        data = _VARIANTS.get(variant)
        if data is None:
            return JSONResponse(status_code=404, content={"error": f"Unknown variant '{variant}'. Choose from: {list(_VARIANTS.keys())}"})
        return JSONResponse(content={
            "variant": variant,
            "activation_rate": data["activation_rate"],
            "time_to_activate_days": data["time_to_activate_days"],
            "dropoff_points": data["dropoff_points"],
            "recommended_improvements": data["recommended_improvements"],
            "best_variant": "quickstart-first",
            "ts": datetime.utcnow().isoformat(),
        })

    @app.post("/onboarding/track")
    def track(payload: dict = Body(...)):
        """
        Track a user onboarding event.
        Input: {user_id: str, event: str}
        Output: funnel_position, next_recommended_step
        """
        user_id = payload.get("user_id", "unknown")
        event = payload.get("event", "signup")
        record = {"event": event, "ts": datetime.utcnow().isoformat()}
        _USER_EVENTS.setdefault(user_id, []).append(record)
        funnel_position = event if event in _FUNNEL_STAGES else _FUNNEL_STAGES[0]
        next_step = _next_step(funnel_position)
        return JSONResponse(content={
            "user_id": user_id,
            "event_recorded": event,
            "funnel_position": funnel_position,
            "next_recommended_step": next_step,
            "total_events_for_user": len(_USER_EVENTS[user_id]),
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
