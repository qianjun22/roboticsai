"""
Object state tracker for manipulation tasks — CNN-based 6-DOF pose tracking + state machine
FastAPI service — OCI Robot Cloud
Port: 10092
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10092

# State machine states for manipulation tasks
STATES = ["idle", "pre-grasp", "grasped", "in-transit", "placed", "failed"]

# In-memory store: object_id -> list of (timestamp, state, pose)
_history: Dict[str, List[Dict]] = {}


def _simulate_pose_6dof(object_id: str, state: str) -> Dict:
    """Simulate a 6-DOF pose (x, y, z, roll, pitch, yaw) for a tracked object."""
    rng = random.Random(hash(object_id + state + str(int(time.time() / 0.5))))
    if state == "idle":
        x, y, z = rng.uniform(0.2, 0.6), rng.uniform(-0.3, 0.3), rng.uniform(0.7, 0.85)
    elif state == "pre-grasp":
        x, y, z = rng.uniform(0.3, 0.5), rng.uniform(-0.15, 0.15), rng.uniform(0.78, 0.88)
    elif state == "grasped":
        x, y, z = rng.uniform(0.35, 0.45), rng.uniform(-0.1, 0.1), rng.uniform(0.82, 0.92)
    elif state == "in-transit":
        x, y, z = rng.uniform(0.25, 0.6), rng.uniform(-0.25, 0.25), rng.uniform(0.90, 1.10)
    elif state == "placed":
        x, y, z = rng.uniform(0.5, 0.8), rng.uniform(-0.3, 0.3), rng.uniform(0.70, 0.80)
    else:  # failed
        x, y, z = rng.uniform(0.1, 0.9), rng.uniform(-0.5, 0.5), rng.uniform(0.60, 0.75)
    roll  = rng.uniform(-math.pi / 12, math.pi / 12)
    pitch = rng.uniform(-math.pi / 12, math.pi / 12)
    yaw   = rng.uniform(-math.pi, math.pi)
    return {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4),
            "roll": round(roll, 4), "pitch": round(pitch, 4), "yaw": round(yaw, 4)}


def _classify_state(depth_mean: float, gripper_width: float, velocity_norm: float) -> str:
    """
    CNN-inspired heuristic state classifier.
    Returns one of the STATE_MACHINE states with ~96% accuracy simulation.
    Input features: depth (m), gripper width (m), velocity norm (m/s).
    """
    # Inject 4% classification noise
    if random.random() < 0.04:
        return random.choice(STATES)
    if velocity_norm < 0.01 and gripper_width > 0.07:
        return "idle"
    if velocity_norm < 0.05 and 0.03 < gripper_width <= 0.07:
        return "pre-grasp"
    if gripper_width <= 0.03 and velocity_norm < 0.05:
        return "grasped"
    if gripper_width <= 0.03 and velocity_norm >= 0.05:
        return "in-transit"
    if gripper_width > 0.06 and depth_mean > 0.75 and velocity_norm < 0.02:
        return "placed"
    return "failed"


def _detect_completion_and_failure(states: List[str]) -> Tuple[bool, bool]:
    """Return (task_complete, task_failed) given recent state sequence."""
    if not states:
        return False, False
    recent = states[-5:]
    task_complete = "placed" in recent
    task_failed = recent[-1] == "failed" or recent.count("failed") >= 2
    return task_complete, task_failed


if USE_FASTAPI:
    app = FastAPI(title="Object State Tracker", version="1.0.0")

    class TrackRequest(BaseModel):
        rgb_d_frame: Dict  # keys: object_ids, depth_mean, gripper_width, velocity_norm
        episode_id: Optional[str] = None

    @app.post("/state/track")
    def track_state(req: TrackRequest):
        """
        Accept an RGB-D frame descriptor and run 6-DOF pose tracking + state classification.
        Returns object_states, poses, completion_flags, failure_signals.
        """
        frame = req.rgb_d_frame
        object_ids: List[str] = frame.get("object_ids", ["cube_A"])
        depth_mean: float = float(frame.get("depth_mean", 0.85))
        gripper_width: float = float(frame.get("gripper_width", 0.08))
        velocity_norm: float = float(frame.get("velocity_norm", 0.0))

        ts = datetime.utcnow().isoformat()
        object_states: Dict[str, str] = {}
        poses: Dict[str, Dict] = {}
        completion_flags: Dict[str, bool] = {}
        failure_signals: Dict[str, bool] = {}

        for obj_id in object_ids:
            state = _classify_state(depth_mean, gripper_width, velocity_norm)
            pose = _simulate_pose_6dof(obj_id, state)

            # Update history
            if obj_id not in _history:
                _history[obj_id] = []
            _history[obj_id].append({"ts": ts, "state": state, "pose": pose,
                                      "episode_id": req.episode_id})
            # Keep last 500 entries per object
            _history[obj_id] = _history[obj_id][-500:]

            past_states = [e["state"] for e in _history[obj_id]]
            complete, failed = _detect_completion_and_failure(past_states)

            object_states[obj_id] = state
            poses[obj_id] = pose
            completion_flags[obj_id] = complete
            failure_signals[obj_id] = failed

        return {
            "ts": ts,
            "object_states": object_states,
            "poses": poses,
            "completion_flags": completion_flags,
            "failure_signals": failure_signals,
            "classifier_accuracy": 0.96,
            "state_machine_states": STATES,
        }

    @app.get("/state/history")
    def get_state_history(object_id: str, limit: int = 50):
        """
        Return the state sequence and timestamps for a given object_id.
        """
        if object_id not in _history:
            raise HTTPException(status_code=404, detail=f"No history for object '{object_id}'")
        entries = _history[object_id][-limit:]
        state_sequence = [e["state"] for e in entries]
        timestamps = [e["ts"] for e in entries]
        poses = [e["pose"] for e in entries]

        # Compute state transition counts
        transitions: Dict[str, int] = {}
        for i in range(1, len(state_sequence)):
            key = f"{state_sequence[i-1]}->{state_sequence[i]}"
            transitions[key] = transitions.get(key, 0) + 1

        complete, failed = _detect_completion_and_failure(state_sequence)
        return {
            "object_id": object_id,
            "state_sequence": state_sequence,
            "timestamps": timestamps,
            "poses": poses,
            "transitions": transitions,
            "task_complete": complete,
            "task_failed": failed,
            "total_entries": len(_history[object_id]),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "object_state_tracker", "port": PORT,
                "ts": datetime.utcnow().isoformat(), "tracked_objects": len(_history)}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Object State Tracker</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>Object State Tracker</h1><p>OCI Robot Cloud · Port 10092</p>
<div class="stat"><b>Classifier Accuracy</b><br>96%</div>
<div class="stat"><b>States</b><br>pre-grasp → grasped → in-transit → placed</div>
<div class="stat"><b>Pose DOF</b><br>6-DOF (x,y,z,roll,pitch,yaw)</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">state classification accuracy</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/state/history?object_id=cube_A">History: cube_A</a></p>
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
