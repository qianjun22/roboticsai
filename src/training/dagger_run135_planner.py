"""
DAgger run135 planner — language-conditioned DAgger with natural language correction labels.
FastAPI service — OCI Robot Cloud
Port: 10078
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10078

# ---------------------------------------------------------------------------
# In-memory state (demo / simulation)
# ---------------------------------------------------------------------------

# Instruction vocabulary accumulated across DAgger iterations
_INITIAL_VOCAB = [
    "pick up the red cube",
    "place object on left shelf",
    "move gripper forward slowly",
    "grasp and lift",
    "rotate wrist clockwise",
    "release gently",
    "push block to center",
    "align with target marker",
]

_state: Dict[str, Any] = {
    "run_id": "run135",
    "iteration": 0,
    "vocab": list(_INITIAL_VOCAB),
    "correction_log": [],          # list of {ts, instruction, label, delta_norm}
    "policy_update_count": 0,
    "generalization_score": 0.61,  # starts at baseline; improves with updates
    "instruction_coverage": 0.74,  # fraction of test instructions seen in training
    "novel_generalization_hits": 0,
    "novel_generalization_total": 0,
}


def _embed_similarity(a: str, b: str) -> float:
    """Toy cosine-like similarity based on word overlap."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / math.sqrt(len(wa) * len(wb))


def _find_best_label(instruction: str) -> str:
    """Return the closest vocab entry as the language label, or add it if novel."""
    scores = [(_embed_similarity(instruction, v), v) for v in _state["vocab"]]
    best_score, best_label = max(scores, key=lambda x: x[0])
    if best_score < 0.25:
        # Novel instruction — add to vocab
        _state["vocab"].append(instruction)
        _state["novel_generalization_total"] += 1
        if random.random() < 0.68:   # simulated generalization hit rate
            _state["novel_generalization_hits"] += 1
        return instruction
    return best_label


def _compute_correction(state_vec: List[float], label: str) -> Dict[str, Any]:
    """Simulate a language-conditioned correction action."""
    dim = len(state_vec) if state_vec else 7
    # Deterministic perturbation seeded by label hash so same label → similar correction
    rng = random.Random(hash(label) & 0xFFFFFFFF)
    delta = [rng.gauss(0, 0.05) for _ in range(dim)]
    correction = [s + d for s, d in zip(state_vec[:dim], delta)] if state_vec else delta
    delta_norm = math.sqrt(sum(d ** 2 for d in delta))
    return {"action": correction, "delta_norm": round(delta_norm, 5)}


def _update_policy_stats(delta_norm: float) -> None:
    """Update running statistics after a correction is applied."""
    _state["policy_update_count"] += 1
    _state["iteration"] += 1
    # Generalization score improves logarithmically with updates
    n = _state["policy_update_count"]
    _state["generalization_score"] = round(
        min(0.99, 0.61 + 0.18 * math.log1p(n / 20.0)), 4
    )
    # Instruction coverage increases as vocab grows
    vocab_size = len(_state["vocab"])
    _state["instruction_coverage"] = round(
        min(0.99, 0.74 + 0.015 * math.log1p(vocab_size - len(_INITIAL_VOCAB))), 4
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="DAgger Run135 Planner",
        version="1.0.0",
        description="Language-conditioned DAgger planner with natural language correction labeling.",
    )

    # --- Request / Response schemas ---

    class PlanRequest(BaseModel):
        instruction: str
        state: Optional[List[float]] = None   # joint/end-effector state vector
        expert_override: Optional[bool] = False

    class PlanResponse(BaseModel):
        run_id: str
        iteration: int
        instruction: str
        language_label: str
        correction: List[float]
        delta_norm: float
        policy_update: bool
        generalization_score: float
        vocab_size: int
        ts: str

    # --- Endpoints ---

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "dagger_run135_planner",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.post("/dagger/run135/plan", response_model=PlanResponse)
    def plan(req: PlanRequest):
        """Receive an instruction + robot state, return a language-labeled correction and trigger a policy update."""
        if not req.instruction.strip():
            raise HTTPException(status_code=422, detail="instruction must not be empty")

        label = _find_best_label(req.instruction.strip())
        corr_data = _compute_correction(req.state or [], label)
        _update_policy_stats(corr_data["delta_norm"])

        log_entry = {
            "ts": datetime.utcnow().isoformat(),
            "instruction": req.instruction,
            "label": label,
            "delta_norm": corr_data["delta_norm"],
        }
        _state["correction_log"].append(log_entry)
        # Keep log bounded
        if len(_state["correction_log"]) > 1000:
            _state["correction_log"] = _state["correction_log"][-1000:]

        return PlanResponse(
            run_id=_state["run_id"],
            iteration=_state["iteration"],
            instruction=req.instruction,
            language_label=label,
            correction=corr_data["action"],
            delta_norm=corr_data["delta_norm"],
            policy_update=True,
            generalization_score=_state["generalization_score"],
            vocab_size=len(_state["vocab"]),
            ts=datetime.utcnow().isoformat(),
        )

    @app.get("/dagger/run135/status")
    def status():
        """Return current run statistics: generalization score, vocab size, instruction coverage."""
        novel_rate = (
            round(_state["novel_generalization_hits"] / _state["novel_generalization_total"], 4)
            if _state["novel_generalization_total"] > 0
            else None
        )
        return {
            "run_id": _state["run_id"],
            "iteration": _state["iteration"],
            "policy_update_count": _state["policy_update_count"],
            "generalization_score": _state["generalization_score"],
            "vocab_size": len(_state["vocab"]),
            "instruction_coverage": _state["instruction_coverage"],
            "novel_generalization_rate": novel_rate,
            "novel_instructions_seen": _state["novel_generalization_total"],
            "novel_instructions_generalized": _state["novel_generalization_hits"],
            "recent_corrections": _state["correction_log"][-5:],
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/dagger/run135/vocab")
    def vocab():
        """Return the full instruction vocabulary accumulated so far."""
        return {
            "run_id": _state["run_id"],
            "vocab_size": len(_state["vocab"]),
            "vocab": _state["vocab"],
            "ts": datetime.utcnow().isoformat(),
        }

    @app.delete("/dagger/run135/reset")
    def reset():
        """Reset run135 state (dev/testing only)."""
        _state.update({
            "iteration": 0,
            "vocab": list(_INITIAL_VOCAB),
            "correction_log": [],
            "policy_update_count": 0,
            "generalization_score": 0.61,
            "instruction_coverage": 0.74,
            "novel_generalization_hits": 0,
            "novel_generalization_total": 0,
        })
        return {"status": "reset", "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>DAgger Run135 Planner</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>DAgger Run135 Planner</h1><p>OCI Robot Cloud · Port 10078</p>
<div class="stat"><b>Status</b><br>Online</div>
<div class="stat"><b>Mode</b><br>Language-Conditioned DAgger</div>
<div class="stat"><b>Run</b><br>run135</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">correction delta / iteration</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/dagger/run135/status">Status</a> | <a href="/dagger/run135/vocab">Vocab</a></p>
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
        def do_POST(self):
            self.do_GET()
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
