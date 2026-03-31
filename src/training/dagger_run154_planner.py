"""DAgger run154 — correction quality scoring (gradient magnitude + task relevance + novelty + feasibility)
FastAPI service — OCI Robot Cloud
Port: 10154"""
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

PORT = 10154

# Simulated state
_state = {
    "corrections_submitted": 350,
    "corrections_accepted": 228,  # 35% rejection rate => 65% accepted
    "rejection_rate": 0.35,
    "quality_threshold": 0.62,
    "filtered_sr": 0.95,
    "unfiltered_sr": 0.93,
    "quality_scoring_overhead_ms": 2,
}

def _score_correction(state: dict, candidate_correction: dict) -> dict:
    """Score a candidate correction on 4 axes and decide accept/reject."""
    gradient_magnitude = candidate_correction.get("gradient_magnitude", random.uniform(0.3, 1.0))
    task_relevance    = candidate_correction.get("task_relevance",    random.uniform(0.4, 1.0))
    novelty           = candidate_correction.get("novelty",           random.uniform(0.2, 1.0))
    feasibility       = candidate_correction.get("feasibility",       random.uniform(0.5, 1.0))

    quality_score = (
        0.30 * gradient_magnitude +
        0.30 * task_relevance +
        0.20 * novelty +
        0.20 * feasibility
    )
    accept = quality_score >= _state["quality_threshold"]
    filtered_correction = candidate_correction if accept else None
    expected_sr_gain = round((quality_score - 0.5) * 0.04, 4) if accept else 0.0

    return {
        "quality_score": round(quality_score, 4),
        "gradient_magnitude": round(gradient_magnitude, 4),
        "task_relevance": round(task_relevance, 4),
        "novelty": round(novelty, 4),
        "feasibility": round(feasibility, 4),
        "accept_reject": "accept" if accept else "reject",
        "filtered_correction": filtered_correction,
        "expected_sr_gain": expected_sr_gain,
        "scoring_overhead_ms": _state["quality_scoring_overhead_ms"],
    }

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run154 Planner", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>DAgger Run154 Planner</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>DAgger Run154 Planner</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>Correction quality scoring: gradient magnitude + task relevance + novelty + feasibility</p>"
            f"<p>35% rejection rate · 95% SR from 200 high-quality corrections vs 93% from 350 unfiltered</p>"
            f"<p>Quality scoring overhead: 2ms</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.post("/dagger/run154/plan")
    def plan(payload: dict = Body(...)):
        """Score a candidate correction and decide accept/reject.
        
        Body: {state: {...}, candidate_correction: {gradient_magnitude, task_relevance, novelty, feasibility}}
        Returns: quality_score, accept_reject, filtered_correction, expected_sr_gain
        """
        state = payload.get("state", {})
        candidate = payload.get("candidate_correction", {})
        result = _score_correction(state, candidate)
        return JSONResponse(result)

    @app.get("/dagger/run154/status")
    def status():
        """Return current run154 quality filtering stats."""
        return {
            "filtered_sr": _state["filtered_sr"],
            "unfiltered_sr": _state["unfiltered_sr"],
            "sr_improvement": round(_state["filtered_sr"] - _state["unfiltered_sr"], 4),
            "rejection_rate": _state["rejection_rate"],
            "quality_threshold": _state["quality_threshold"],
            "corrections_submitted": _state["corrections_submitted"],
            "corrections_accepted": _state["corrections_accepted"],
            "quality_scoring_overhead_ms": _state["quality_scoring_overhead_ms"],
            "note": "95% SR from 200 high-quality corrections vs 93% SR from 350 unfiltered",
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
