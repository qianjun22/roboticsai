"""
A/B test onboarding flows — 4 variants (docs-first 52% / quickstart 78% /
guided tour 71% / video-first 67%), time-to-activation tracking
(quickstart wins at 3.2 days), activation defined as first eval SR>50%.
FastAPI service — OCI Robot Cloud
Port: 10115
"""
from __future__ import annotations
import json, random, time
from datetime import datetime
from typing import Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10115

# Onboarding variant definitions
_VARIANTS = {
    "docs-first": {
        "activation_rate": 0.52,
        "time_to_activate_days": 5.8,
        "dropoff_points": ["api_reference_page", "auth_setup", "first_run"],
        "recommended_improvements": [
            "Add interactive code playground to docs",
            "Shorten auth setup to OAuth one-click",
            "Add progress indicator to first-run flow",
        ],
    },
    "quickstart": {
        "activation_rate": 0.78,
        "time_to_activate_days": 3.2,
        "dropoff_points": ["dependency_install", "model_download"],
        "recommended_improvements": [
            "Pre-bundle common dependencies in Docker image",
            "Stream model download with progress bar",
        ],
    },
    "guided-tour": {
        "activation_rate": 0.71,
        "time_to_activate_days": 4.1,
        "dropoff_points": ["step3_environment_config", "step7_first_eval"],
        "recommended_improvements": [
            "Reduce guided tour from 12 steps to 7",
            "Auto-fill environment config from detected hardware",
        ],
    },
    "video-first": {
        "activation_rate": 0.67,
        "time_to_activate_days": 4.7,
        "dropoff_points": ["post_video_handoff", "cli_setup"],
        "recommended_improvements": [
            "Embed interactive terminal after video",
            "Auto-detect OS and show platform-specific CLI commands",
        ],
    },
}

# Funnel positions per variant
_FUNNEL = [
    "signup",
    "email_verified",
    "onboarding_started",
    "first_api_call",
    "first_model_loaded",
    "first_eval_run",
    "activated",  # SR > 50%
]

# In-memory user tracking (ephemeral)
_user_sessions: dict[str, dict] = {}

if USE_FASTAPI:
    app = FastAPI(title="User Onboarding Optimizer", version="1.0.0")

    class TrackRequest(BaseModel):
        user_id: str
        event: str
        variant: Optional[str] = None
        metadata: Optional[dict] = None

    @app.get("/onboarding/optimizer")
    def optimizer(variant: str = Query(..., description="One of: docs-first, quickstart, guided-tour, video-first")):
        if variant not in _VARIANTS:
            return JSONResponse(
                {"error": f"Unknown variant '{variant}'. Valid: {list(_VARIANTS.keys())}"},
                status_code=400
            )
        v = _VARIANTS[variant]
        return JSONResponse({
            "variant": variant,
            "activation_rate": v["activation_rate"],
            "time_to_activate_days": v["time_to_activate_days"],
            "dropoff_points": v["dropoff_points"],
            "recommended_improvements": v["recommended_improvements"],
            "winner": variant == "quickstart",
            "winner_note": "quickstart wins: 78% activation at 3.2 days avg" if variant == "quickstart" else None,
            "activation_definition": "first eval SR > 50%",
            "ts": datetime.utcnow().isoformat(),
        })

    @app.post("/onboarding/track")
    def track(req: TrackRequest):
        uid = req.user_id
        if uid not in _user_sessions:
            assigned_variant = req.variant or random.choice(list(_VARIANTS.keys()))
            _user_sessions[uid] = {
                "variant": assigned_variant,
                "funnel_position": 0,
                "events": [],
                "started_at": datetime.utcnow().isoformat(),
            }
        session = _user_sessions[uid]
        session["events"].append({
            "event": req.event,
            "ts": datetime.utcnow().isoformat(),
            "metadata": req.metadata or {},
        })

        # Advance funnel position if event matches next step
        current_pos = session["funnel_position"]
        if current_pos < len(_FUNNEL) - 1:
            next_step = _FUNNEL[current_pos + 1]
            if req.event == next_step or req.event.lower().replace(" ", "_") == next_step:
                session["funnel_position"] = current_pos + 1
                current_pos = session["funnel_position"]

        variant_data = _VARIANTS[session["variant"]]
        funnel_label = _FUNNEL[current_pos]
        next_step_label = _FUNNEL[current_pos + 1] if current_pos < len(_FUNNEL) - 1 else None

        return JSONResponse({
            "user_id": uid,
            "variant": session["variant"],
            "funnel_position": funnel_label,
            "funnel_step_index": current_pos,
            "funnel_total_steps": len(_FUNNEL),
            "next_recommended_step": next_step_label,
            "activated": funnel_label == "activated",
            "estimated_days_to_activation": variant_data["time_to_activate_days"],
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/onboarding/summary")
    def summary():
        return JSONResponse({
            "variants": {
                name: {
                    "activation_rate": v["activation_rate"],
                    "time_to_activate_days": v["time_to_activate_days"],
                }
                for name, v in _VARIANTS.items()
            },
            "winner": "quickstart",
            "winner_activation_rate": 0.78,
            "winner_time_to_activate_days": 3.2,
            "activation_definition": "first eval SR > 50%",
            "active_tracked_users": len(_user_sessions),
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>User Onboarding Optimizer</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}
table{border-collapse:collapse;margin-top:1rem}td,th{border:1px solid #334155;padding:.5rem 1rem}
th{background:#1e293b}.winner{color:#4ade80;font-weight:bold}</style></head><body>
<h1>User Onboarding Optimizer</h1>
<p>OCI Robot Cloud &middot; Port 10115</p>
<table>
  <tr><th>Variant</th><th>Activation Rate</th><th>Days to Activate</th></tr>
  <tr><td>docs-first</td><td>52%</td><td>5.8</td></tr>
  <tr class="winner"><td>quickstart &#9733;</td><td>78%</td><td>3.2</td></tr>
  <tr><td>guided-tour</td><td>71%</td><td>4.1</td></tr>
  <tr><td>video-first</td><td>67%</td><td>4.7</td></tr>
</table>
<p><small>Activation = first eval SR &gt; 50%</small></p>
<p><a href="/docs">API Docs</a> | <a href="/onboarding/summary">Summary</a> | <a href="/health">Health</a></p>
</body></html>""")

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
