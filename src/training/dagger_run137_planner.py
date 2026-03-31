"""
DAgger run137 planner — sample replay DAgger with 5000-correction ring buffer, anti-forgetting via high-value correction replay, continual learning across task portfolio.
FastAPI service — OCI Robot Cloud
Port: 10086
"""
from __future__ import annotations
import json, math, random, time, collections
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10086
BUFFER_CAPACITY = 5000

# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

class CorrectionEntry:
    """Single DAgger correction stored in the ring buffer."""
    __slots__ = ("task_id", "state", "correction", "gradient_magnitude", "timestamp", "value_score")

    def __init__(self, task_id: str, state: Dict, correction: Dict, gradient_magnitude: float):
        self.task_id = task_id
        self.state = state
        self.correction = correction
        self.gradient_magnitude = gradient_magnitude
        self.timestamp = time.time()
        # Value score: combination of gradient magnitude (informativeness) and recency
        self.value_score = gradient_magnitude


class SampleReplayBuffer:
    """Ring buffer with high-value correction retention for anti-forgetting."""

    def __init__(self, capacity: int = BUFFER_CAPACITY, high_value_fraction: float = 0.2):
        self.capacity = capacity
        self.high_value_fraction = high_value_fraction
        self._ring: collections.deque = collections.deque(maxlen=int(capacity * (1 - high_value_fraction)))
        self._high_value: List[CorrectionEntry] = []  # kept sorted by value_score desc
        self._high_value_cap = int(capacity * high_value_fraction)
        self._total_added = 0
        self._task_sr: Dict[str, List[float]] = {}  # per-task success rates

    def add(self, entry: CorrectionEntry) -> None:
        """Add correction to appropriate partition."""
        self._total_added += 1
        # Decide partition by gradient magnitude threshold (top 20%)
        if len(self._high_value) < self._high_value_cap:
            self._high_value.append(entry)
            self._high_value.sort(key=lambda e: e.value_score, reverse=True)
        else:
            min_hv = self._high_value[-1].value_score if self._high_value else 0.0
            if entry.value_score > min_hv:
                # Evict lowest high-value entry to ring buffer
                evicted = self._high_value.pop()
                self._ring.append(evicted)
                self._high_value.append(entry)
                self._high_value.sort(key=lambda e: e.value_score, reverse=True)
            else:
                self._ring.append(entry)

    def sample(self, n: int = 32) -> List[CorrectionEntry]:
        """Sample mixing ring buffer and high-value partition."""
        all_entries = list(self._ring) + self._high_value
        if not all_entries:
            return []
        return random.choices(all_entries, k=min(n, len(all_entries)))

    @property
    def size(self) -> int:
        return len(self._ring) + len(self._high_value)

    @property
    def replay_ratio(self) -> float:
        """Fraction of buffer that is high-value corrections."""
        if self.size == 0:
            return 0.0
        return len(self._high_value) / self.size

    def record_sr(self, task_id: str, success: bool) -> None:
        self._task_sr.setdefault(task_id, [])
        self._task_sr[task_id].append(1.0 if success else 0.0)
        # Keep rolling window of 100
        if len(self._task_sr[task_id]) > 100:
            self._task_sr[task_id] = self._task_sr[task_id][-100:]

    def sr_per_task(self) -> Dict[str, float]:
        return {
            tid: round(sum(vals) / len(vals), 4)
            for tid, vals in self._task_sr.items()
            if vals
        }

    def forgetting_rate(self) -> float:
        """Proxy: std-dev of per-task SR (high spread → high forgetting)."""
        srs = list(self.sr_per_task().values())
        if len(srs) < 2:
            return 0.0
        mu = sum(srs) / len(srs)
        variance = sum((s - mu) ** 2 for s in srs) / len(srs)
        return round(math.sqrt(variance), 4)


# Global buffer instance
_buffer = SampleReplayBuffer(capacity=BUFFER_CAPACITY)

# Simulated task portfolio
TASK_PORTFOLIO = [
    "lift_cube", "stack_blocks", "open_drawer", "pour_liquid",
    "assemble_gear", "wipe_surface", "pick_and_place", "fold_cloth",
]


def _simulate_correction(state: Dict, task_id: str) -> Dict:
    """Produce a simulated expert correction given robot state."""
    joint_pos = state.get("joint_positions", [0.0] * 7)
    target = state.get("target_position", {"x": 0.5, "y": 0.0, "z": 0.8})
    # Proportional controller residual as correction signal
    delta = {
        "joint_deltas": [round(random.gauss(0, 0.05), 4) for _ in range(len(joint_pos))],
        "gripper_action": random.choice(["open", "close", "hold"]),
        "cartesian_target": {
            "x": round(target.get("x", 0.5) + random.gauss(0, 0.01), 4),
            "y": round(target.get("y", 0.0) + random.gauss(0, 0.01), 4),
            "z": round(target.get("z", 0.8) + random.gauss(0, 0.01), 4),
        },
        "correction_confidence": round(random.uniform(0.7, 1.0), 3),
    }
    return delta


def _estimate_gradient_magnitude(state: Dict, task_id: str) -> float:
    """Estimate gradient magnitude as proxy for sample informativeness."""
    joint_pos = state.get("joint_positions", [0.0] * 7)
    # Higher magnitude near singularities or high-velocity states
    velocity_norm = math.sqrt(sum(v ** 2 for v in state.get("joint_velocities", [0.0] * 7)))
    base = 0.3 + 0.4 * min(velocity_norm / 5.0, 1.0)
    noise = random.gauss(0, 0.05)
    return round(max(0.01, min(1.0, base + noise)), 4)


def _compute_replay_weight(gradient_magnitude: float, buffer_size: int) -> float:
    """Replay weight: high-gradient corrections weighted more heavily during training."""
    base_weight = 1.0 + 2.0 * gradient_magnitude
    # Scale down slightly as buffer fills (curriculum effect)
    fill_penalty = max(0.5, 1.0 - (buffer_size / BUFFER_CAPACITY) * 0.3)
    return round(base_weight * fill_penalty, 4)


# ---------------------------------------------------------------------------
# FastAPI / fallback server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run137 Planner", version="1.0.0")

    class PlanRequest(BaseModel):
        state: Dict[str, Any]
        task_id: str
        record_outcome: Optional[bool] = False
        outcome_success: Optional[bool] = None

    @app.post("/dagger/run137/plan")
    def plan(req: PlanRequest):
        """
        Given robot state and task_id, produce an expert correction.
        Stores correction in ring buffer with computed gradient magnitude and replay weight.
        """
        if req.task_id not in TASK_PORTFOLIO:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown task_id '{req.task_id}'. Valid: {TASK_PORTFOLIO}"}
            )

        grad_mag = _estimate_gradient_magnitude(req.state, req.task_id)
        correction = _simulate_correction(req.state, req.task_id)
        replay_weight = _compute_replay_weight(grad_mag, _buffer.size)

        entry = CorrectionEntry(
            task_id=req.task_id,
            state=req.state,
            correction=correction,
            gradient_magnitude=grad_mag,
        )
        _buffer.add(entry)

        if req.record_outcome and req.outcome_success is not None:
            _buffer.record_sr(req.task_id, req.outcome_success)

        # Sample a replay batch to accompany the correction (for on-device training)
        replay_batch = _buffer.sample(n=16)
        replay_task_ids = [e.task_id for e in replay_batch]

        return {
            "task_id": req.task_id,
            "correction": correction,
            "gradient_magnitude": grad_mag,
            "replay_weight": replay_weight,
            "replay_batch_size": len(replay_batch),
            "replay_task_distribution": {
                tid: replay_task_ids.count(tid)
                for tid in set(replay_task_ids)
            },
            "buffer_size": _buffer.size,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/dagger/run137/status")
    def status():
        """Return buffer health, replay ratio, forgetting rate, and per-task SR."""
        return {
            "buffer_size": _buffer.size,
            "buffer_capacity": BUFFER_CAPACITY,
            "fill_pct": round(_buffer.size / BUFFER_CAPACITY * 100, 2),
            "replay_ratio": _buffer.replay_ratio,
            "forgetting_rate": _buffer.forgetting_rate(),
            "sr_per_task": _buffer.sr_per_task(),
            "total_corrections_added": _buffer._total_added,
            "high_value_slots": len(_buffer._high_value),
            "ring_slots": len(_buffer._ring),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "dagger_run137_planner",
            "port": PORT,
            "buffer_size": _buffer.size,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>DAgger Run137 Planner</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>DAgger Run137 Planner</h1><p>OCI Robot Cloud · Port 10086</p>
<p>Sample replay DAgger with 5000-correction ring buffer and anti-forgetting correction replay.</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/dagger/run137/status">Buffer Status</a></p>
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
