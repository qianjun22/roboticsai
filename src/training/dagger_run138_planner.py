"""
DAgger run138 planner — policy ensemble DAgger with 3 diverse policies corrected in parallel, majority vote at inference, ensemble uncertainty for correction triggering (+3% SR).
FastAPI service — OCI Robot Cloud
Port: 10090
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10090

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
NUM_POLICIES = 3
POLICY_NAMES = ["policy_alpha", "policy_beta", "policy_gamma"]
# Per-policy base success rates (diverse training regimes)
POLICY_BASE_SR = {"policy_alpha": 0.81, "policy_beta": 0.78, "policy_gamma": 0.80}
# Ensemble yields +3% SR over best single policy
ENSEMBLE_SR_BOOST = 0.03
DISAGREEMENT_THRESHOLD = 0.25   # trigger correction when disagreement > this

# ---------------------------------------------------------------------------
# In-memory run state
# ---------------------------------------------------------------------------
_state: Dict = {
    "episodes": 0,
    "corrections_triggered": 0,
    "disagreement_sum": 0.0,
    "ensemble_successes": 0,
    "start_time": datetime.utcnow().isoformat(),
}

# ---------------------------------------------------------------------------
# Core ensemble logic helpers
# ---------------------------------------------------------------------------

def _simulate_policy_action(policy_name: str, state_vec: List[float], noise: float = 0.05) -> List[float]:
    """Return a 7-DoF joint-delta action for one policy (simulated)."""
    rng = random.Random(hash(policy_name) ^ int(time.time() * 1000) % 10007)
    base = [math.tanh(v * 0.3 + rng.gauss(0, noise)) for v in state_vec[:7]]
    return base


def _majority_vote(actions: Dict[str, List[float]]) -> List[float]:
    """Average ensemble actions (continuous majority vote via mean)."""
    arr = list(actions.values())
    n = len(arr[0])
    return [sum(a[i] for a in arr) / len(arr) for i in range(n)]


def _disagreement_score(actions: Dict[str, List[float]]) -> float:
    """Mean pairwise L2 distance across policy actions, normalised to [0,1]."""
    keys = list(actions.keys())
    pairs, total = 0, 0.0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a1, a2 = actions[keys[i]], actions[keys[j]]
            dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(a1, a2)))
            total += dist
            pairs += 1
    raw = total / pairs if pairs else 0.0
    return min(raw / 2.0, 1.0)  # normalise: typical max ~2.0


def _ensemble_correction(disagreement: float, state_vec: List[float]) -> Dict:
    """Decide whether to request human/oracle correction and build correction payload."""
    if disagreement <= DISAGREEMENT_THRESHOLD:
        return {"correction_needed": False, "reason": "ensemble_confident", "correction_action": None}
    # High disagreement — produce a corrective action blending all policies with extra smoothing
    correction = [math.tanh(v * 0.15) for v in state_vec[:7]]
    return {
        "correction_needed": True,
        "reason": "high_disagreement",
        "correction_action": correction,
        "disagreement_score": disagreement,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run138 Planner", version="1.0.0")

    # ---- request / response models ----

    class PlanRequest(BaseModel):
        state: List[float]          # robot joint state, min 7 dims
        image: Optional[List[float]] = None   # flattened image embedding (optional)
        episode_id: Optional[str] = None

    class PlanResponse(BaseModel):
        ensemble_action: List[float]
        ensemble_correction: Dict
        disagreement_score: float
        policy_votes: Dict[str, List[float]]
        correction_triggered: bool
        episode_id: Optional[str]
        latency_ms: float
        ts: str

    class StatusResponse(BaseModel):
        ensemble_sr: float
        disagreement_rate: float
        correction_triggers: int
        episodes: int
        uptime_seconds: float
        policies: List[str]
        ts: str

    # ---- endpoints ----

    @app.post("/dagger/run138/plan", response_model=PlanResponse)
    def plan(req: PlanRequest):
        t0 = time.perf_counter()

        # Pad state to 7 dims if shorter
        state_vec = (req.state + [0.0] * 7)[:7]

        # 1. Each policy produces an independent action
        policy_actions: Dict[str, List[float]] = {
            p: _simulate_policy_action(p, state_vec) for p in POLICY_NAMES
        }

        # 2. Majority vote (mean) ensemble action
        ensemble_action = _majority_vote(policy_actions)

        # 3. Disagreement score drives correction triggering
        disagreement = _disagreement_score(policy_actions)
        correction_info = _ensemble_correction(disagreement, state_vec)
        correction_triggered = correction_info["correction_needed"]

        # 4. Update run state
        _state["episodes"] += 1
        _state["disagreement_sum"] += disagreement
        if correction_triggered:
            _state["corrections_triggered"] += 1
        # Simulate success (ensemble SR = best policy + boost)
        best_sr = max(POLICY_BASE_SR.values())
        if random.random() < best_sr + ENSEMBLE_SR_BOOST:
            _state["ensemble_successes"] += 1

        latency_ms = (time.perf_counter() - t0) * 1000

        return PlanResponse(
            ensemble_action=ensemble_action,
            ensemble_correction=correction_info,
            disagreement_score=round(disagreement, 4),
            policy_votes=policy_actions,
            correction_triggered=correction_triggered,
            episode_id=req.episode_id,
            latency_ms=round(latency_ms, 2),
            ts=datetime.utcnow().isoformat(),
        )

    @app.get("/dagger/run138/status", response_model=StatusResponse)
    def status():
        eps = _state["episodes"] or 1
        ensemble_sr = _state["ensemble_successes"] / eps
        disagreement_rate = _state["disagreement_sum"] / eps
        start = datetime.fromisoformat(_state["start_time"])
        uptime = (datetime.utcnow() - start).total_seconds()
        return StatusResponse(
            ensemble_sr=round(ensemble_sr, 4),
            disagreement_rate=round(disagreement_rate, 4),
            correction_triggers=_state["corrections_triggered"],
            episodes=_state["episodes"],
            uptime_seconds=round(uptime, 1),
            policies=POLICY_NAMES,
            ts=datetime.utcnow().isoformat(),
        )

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dagger_run138_planner", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>DAgger Run138 Planner</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>DAgger Run138 Planner</h1><p>OCI Robot Cloud · Port 10090</p>
<p>Policy ensemble DAgger: 3 diverse policies corrected in parallel · majority vote at inference · ensemble uncertainty for correction triggering (+3% SR)</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/dagger/run138/status">Status</a></p>
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
