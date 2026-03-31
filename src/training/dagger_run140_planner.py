"""
DAgger run140 planner — BC warm-start DAgger starting from 85% SR baseline.
FastAPI service — OCI Robot Cloud
Port: 10098
"""
from __future__ import annotations
import json, math, random, time
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

PORT = 10098

# ── Domain constants ──────────────────────────────────────────────────────────
BASELINE_SR         = 0.85   # warm-start checkpoint SR
TARGET_SR           = 0.97   # run140 target SR
COLD_START_CORR     = 2400   # corrections cold-start needs to reach 97%
WARM_CORR_RATIO     = 0.60   # warm-start needs 40% fewer corrections
WARM_START_CORR     = int(COLD_START_CORR * WARM_CORR_RATIO)  # 1440

# Simulated live state (in a real deployment this would be persisted / Redis)
_state = {
    "run_id":          "run140",
    "started_at":      datetime.utcnow().isoformat(),
    "correction_count": 0,
    "current_sr":      BASELINE_SR,
    "warmstart_checkpoint": "gr00t_bc_85pct_v3.pt",
}


def _project_sr(corrections: int) -> float:
    """Sigmoid-shaped SR curve calibrated to warm-start data."""
    if corrections <= 0:
        return BASELINE_SR
    # logistic: SR = target - (target - baseline) / (1 + exp(k*(x - midpoint)))
    k         = 0.006
    midpoint  = WARM_START_CORR / 2  # 720 corrections → inflection
    delta     = TARGET_SR - BASELINE_SR
    sr = TARGET_SR - delta / (1 + math.exp(k * (corrections - midpoint)))
    return round(min(TARGET_SR, max(BASELINE_SR, sr)), 4)


def _efficiency_vs_coldstart(corrections: int) -> dict:
    """How many corrections saved relative to a cold-start at the same SR."""
    current_sr    = _project_sr(corrections)
    # For a cold-start to reach the same SR the curve is stretched by 1/0.60
    coldstart_eq  = int(corrections / WARM_CORR_RATIO)
    saved         = coldstart_eq - corrections
    pct_saved     = round(saved / max(coldstart_eq, 1) * 100, 1)
    return {
        "corrections_used":          corrections,
        "coldstart_equivalent":      coldstart_eq,
        "corrections_saved":         saved,
        "efficiency_gain_pct":       pct_saved,
        "projected_total_to_target": WARM_START_CORR,
        "coldstart_total_to_target": COLD_START_CORR,
    }


if USE_FASTAPI:
    app = FastAPI(title="DAgger Run140 Planner", version="1.0.0")

    # ── Request / response models ─────────────────────────────────────────────
    class PlanRequest(BaseModel):
        state: dict                          # robot observation state dict
        warmstart_checkpoint: Optional[str] = None
        n_corrections_so_far: Optional[int] = None

    class PlanResponse(BaseModel):
        correction: dict
        sr_projection: dict
        efficiency_vs_coldstart: dict
        run_id: str
        ts: str

    # ── Endpoints ─────────────────────────────────────────────────────────────
    @app.post("/dagger/run140/plan", response_model=PlanResponse)
    def plan(req: PlanRequest):
        """Given current state, return a DAgger correction + SR/efficiency projections."""
        checkpoint = req.warmstart_checkpoint or _state["warmstart_checkpoint"]
        corrections_so_far = req.n_corrections_so_far
        if corrections_so_far is None:
            corrections_so_far = _state["correction_count"]

        # Simulate correction generation (delta actions from teacher policy)
        obs = req.state
        base_action = [round(random.gauss(0, 0.02), 4) for _ in range(7)]
        correction = {
            "source":      "teacher_policy",
            "checkpoint":  checkpoint,
            "delta_action": base_action,
            "confidence":  round(random.uniform(0.82, 0.99), 3),
            "latency_ms":  round(random.uniform(18, 35), 1),
        }

        # Increment global correction counter
        _state["correction_count"] += 1
        new_count = _state["correction_count"]
        new_sr    = _project_sr(new_count)
        _state["current_sr"] = new_sr

        sr_projection = {
            "current_sr":             new_sr,
            "baseline_sr":            BASELINE_SR,
            "target_sr":              TARGET_SR,
            "corrections_to_target":  max(0, WARM_START_CORR - new_count),
            "pct_complete":           round(new_count / WARM_START_CORR * 100, 1),
        }

        return PlanResponse(
            correction=correction,
            sr_projection=sr_projection,
            efficiency_vs_coldstart=_efficiency_vs_coldstart(new_count),
            run_id=_state["run_id"],
            ts=datetime.utcnow().isoformat(),
        )

    @app.get("/dagger/run140/status")
    def status():
        """Return live run140 state: current SR, correction count, warmstart gain."""
        corr  = _state["correction_count"]
        sr    = _state["current_sr"]
        # Gain = SR above cold-start baseline at same correction count
        cold_sr_at_same_corr = BASELINE_SR + (TARGET_SR - BASELINE_SR) * (
            1 / (1 + math.exp(-0.006 * (int(corr / WARM_CORR_RATIO) - COLD_START_CORR / 2)))
        ) - (TARGET_SR - BASELINE_SR) / 2
        warmstart_gain_pct = round((sr - max(BASELINE_SR, cold_sr_at_same_corr)) * 100, 2)
        return {
            "run_id":               _state["run_id"],
            "current_sr":           sr,
            "baseline_sr":          BASELINE_SR,
            "target_sr":            TARGET_SR,
            "correction_count":     corr,
            "corrections_remaining": max(0, WARM_START_CORR - corr),
            "warmstart_checkpoint": _state["warmstart_checkpoint"],
            "warmstart_gain_pct":   warmstart_gain_pct,
            "efficiency_summary":   _efficiency_vs_coldstart(corr),
            "started_at":           _state["started_at"],
            "ts":                   datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dagger_run140_planner", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>DAgger Run140 Planner</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>DAgger Run140 Planner</h1><p>OCI Robot Cloud · Port 10098</p>
<p>BC warm-start from <strong>85% SR</strong> → target <strong>97% SR</strong> with 40% fewer corrections than cold-start.</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/dagger/run140/status">Live Status</a></p>
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
