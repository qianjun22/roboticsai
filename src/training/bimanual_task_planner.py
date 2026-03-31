"""
Two-arm coordinated task planner — symmetric/asymmetric/handoff task types.
FastAPI service — OCI Robot Cloud
Port: 10100
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10100

# ── Domain constants ──────────────────────────────────────────────────────────
TASK_CATALOG: Dict[str, Dict] = {
    "symmetric_lift": {
        "coordination_type": "symmetric",
        "sr": 0.82,
        "arm_config": "mirror",
        "description": "Both arms apply equal force to lift heavy objects",
        "sync_window_ms": 20,
        "force_tolerance_n": 2.0,
    },
    "asymmetric_assemble": {
        "coordination_type": "asymmetric",
        "sr": 0.76,
        "arm_config": "dominant_assist",
        "description": "Right arm manipulates, left arm stabilises workpiece",
        "sync_window_ms": 50,
        "force_tolerance_n": 5.0,
    },
    "handoff": {
        "coordination_type": "handoff",
        "sr": 0.71,
        "arm_config": "sequential",
        "description": "Object transferred from arm-1 grasp to arm-2 grasp mid-task",
        "sync_window_ms": 15,
        "force_tolerance_n": 1.5,
    },
    "peg_in_hole_bimanual": {
        "coordination_type": "asymmetric",
        "sr": 0.79,
        "arm_config": "dominant_assist",
        "description": "One arm holds board, other inserts peg with precision",
        "sync_window_ms": 30,
        "force_tolerance_n": 3.0,
    },
    "cloth_fold": {
        "coordination_type": "symmetric",
        "sr": 0.68,
        "arm_config": "mirror",
        "description": "Both arms fold flexible cloth in synchrony",
        "sync_window_ms": 25,
        "force_tolerance_n": 0.8,
    },
    "pour_and_hold": {
        "coordination_type": "asymmetric",
        "sr": 0.74,
        "arm_config": "dominant_assist",
        "description": "Left arm holds cup steady, right arm pours from pitcher",
        "sync_window_ms": 40,
        "force_tolerance_n": 2.5,
    },
}

AVG_SR = sum(v["sr"] for v in TASK_CATALOG.values()) / len(TASK_CATALOG)  # ~0.75


def _generate_trajectory(arm_id: str, n_waypoints: int = 8) -> List[Dict]:
    """Generate a plausible Cartesian + joint-space trajectory."""
    rng = random.Random(hash(arm_id + str(time.time())))
    wps = []
    x, y, z = (0.3 if arm_id == "arm1" else -0.3), 0.0, 0.4
    for i in range(n_waypoints):
        x += rng.uniform(-0.04, 0.06)
        y += rng.uniform(-0.03, 0.03)
        z += rng.uniform(-0.02, 0.04) if i < n_waypoints // 2 else rng.uniform(-0.05, 0.01)
        z = max(0.05, min(0.8, z))
        joints = [round(rng.uniform(-1.5, 1.5), 4) for _ in range(7)]
        wps.append({
            "t_ms": i * 150,
            "pose": {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4),
                     "roll": round(rng.uniform(-0.3, 0.3), 4),
                     "pitch": round(rng.uniform(-0.3, 0.3), 4),
                     "yaw": round(rng.uniform(-0.3, 0.3), 4)},
            "joints_rad": joints,
            "gripper": round(rng.uniform(0.0, 1.0), 2),
        })
    return wps


def _check_collision(traj1: List[Dict], traj2: List[Dict]) -> Dict:
    """Simple bounding-sphere collision check between arm trajectories."""
    min_dist = float("inf")
    worst_t = 0
    for wp1, wp2 in zip(traj1, traj2):
        p1, p2 = wp1["pose"], wp2["pose"]
        dist = math.sqrt(
            (p1["x"] - p2["x"]) ** 2
            + (p1["y"] - p2["y"]) ** 2
            + (p1["z"] - p2["z"]) ** 2
        )
        if dist < min_dist:
            min_dist = dist
            worst_t = wp1["t_ms"]
    safe_threshold = 0.18  # 18 cm
    collision_free = min_dist > safe_threshold
    return {
        "collision_free": collision_free,
        "min_clearance_m": round(min_dist, 4),
        "worst_t_ms": worst_t,
        "safe_threshold_m": safe_threshold,
    }


def _build_sync_constraints(task_type: str) -> List[Dict]:
    meta = TASK_CATALOG.get(task_type, TASK_CATALOG["asymmetric_assemble"])
    constraints = [
        {
            "constraint_type": "temporal_sync",
            "window_ms": meta["sync_window_ms"],
            "description": "Arms must reach sync waypoints within the allowed window",
        },
        {
            "constraint_type": "force_balance",
            "tolerance_n": meta["force_tolerance_n"],
            "description": "Force imbalance between arms must not exceed tolerance",
        },
    ]
    if meta["coordination_type"] == "handoff":
        constraints.append({
            "constraint_type": "grasp_overlap",
            "overlap_ms": 80,
            "description": "Both grippers must hold object simultaneously during transfer",
        })
    return constraints


# ── FastAPI app ───────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Bimanual Task Planner", version="1.0.0")

    class PlanRequest(BaseModel):
        task_description: str = Field(
            ..., example="lift heavy box with both arms"
        )
        object_states: Dict[str, Any] = Field(
            default_factory=dict,
            example={"box": {"pos": [0.5, 0.0, 0.1], "mass_kg": 3.2}},
        )
        task_type: Optional[str] = Field(
            None, example="symmetric_lift"
        )
        n_waypoints: int = Field(8, ge=4, le=24)

    @app.post("/bimanual/plan")
    def plan_bimanual(req: PlanRequest):
        """Generate coordinated trajectories for both arms."""
        task_type = req.task_type
        if task_type is None:
            # Infer task type from description keywords
            desc_lower = req.task_description.lower()
            if "handoff" in desc_lower or "transfer" in desc_lower:
                task_type = "handoff"
            elif "fold" in desc_lower or "cloth" in desc_lower:
                task_type = "cloth_fold"
            elif "pour" in desc_lower:
                task_type = "pour_and_hold"
            elif "peg" in desc_lower or "insert" in desc_lower:
                task_type = "peg_in_hole_bimanual"
            elif any(w in desc_lower for w in ["lift", "carry", "heavy"]):
                task_type = "symmetric_lift"
            else:
                task_type = "asymmetric_assemble"

        meta = TASK_CATALOG.get(task_type)
        if meta is None:
            raise HTTPException(status_code=400, detail=f"Unknown task_type: {task_type}")

        traj1 = _generate_trajectory("arm1", req.n_waypoints)
        traj2 = _generate_trajectory("arm2", req.n_waypoints)
        collision_info = _check_collision(traj1, traj2)

        # If collision detected, push arm2 further apart on y-axis
        if not collision_info["collision_free"]:
            for wp in traj2:
                wp["pose"]["y"] -= 0.15
            collision_info = _check_collision(traj1, traj2)

        sync_constraints = _build_sync_constraints(task_type)

        return {
            "task_type": task_type,
            "coordination_type": meta["coordination_type"],
            "arm_config": meta["arm_config"],
            "estimated_sr": meta["sr"],
            "arm1_trajectory": traj1,
            "arm2_trajectory": traj2,
            "sync_constraints": sync_constraints,
            "collision_analysis": collision_info,
            "plan_latency_ms": round(random.uniform(18, 42), 1),
            "planned_at": datetime.utcnow().isoformat(),
        }

    @app.get("/bimanual/capabilities")
    def get_capabilities(
        task_type: Optional[str] = Query(None, description="Filter by task type")
    ):
        """Return SR and coordination metadata for supported task types."""
        catalog = TASK_CATALOG
        if task_type:
            if task_type not in catalog:
                raise HTTPException(status_code=404, detail=f"Task type '{task_type}' not found")
            catalog = {task_type: catalog[task_type]}

        result = {
            "tasks": {
                k: {
                    "sr": v["sr"],
                    "coordination_type": v["coordination_type"],
                    "arm_config": v["arm_config"],
                    "description": v["description"],
                    "sync_window_ms": v["sync_window_ms"],
                    "force_tolerance_n": v["force_tolerance_n"],
                }
                for k, v in catalog.items()
            },
            "avg_sr": round(AVG_SR, 4),
            "supported_coordination_types": ["symmetric", "asymmetric", "handoff"],
        }
        return result

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "bimanual_task_planner",
            "port": PORT,
            "avg_sr": round(AVG_SR, 4),
            "task_types_supported": len(TASK_CATALOG),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""
<!DOCTYPE html><html><head><title>Bimanual Task Planner</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
table{border-collapse:collapse;margin-top:1rem}td,th{border:1px solid #334155;padding:.5rem 1rem;text-align:left}
th{background:#1e293b}</style></head><body>
<h1>Bimanual Task Planner</h1>
<p>OCI Robot Cloud &middot; Port 10100</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/bimanual/capabilities">Capabilities</a></p>
<div class="stat">Avg SR: <strong>74%</strong></div>
<div class="stat">Task types: <strong>6</strong></div>
<div class="stat">Arms: <strong>2 (7-DoF each)</strong></div>
<h2>Supported Task Types</h2>
<table><tr><th>Type</th><th>Coordination</th><th>SR</th></tr>
<tr><td>symmetric_lift</td><td>symmetric</td><td>82%</td></tr>
<tr><td>asymmetric_assemble</td><td>asymmetric</td><td>76%</td></tr>
<tr><td>handoff</td><td>handoff</td><td>71%</td></tr>
<tr><td>peg_in_hole_bimanual</td><td>asymmetric</td><td>79%</td></tr>
<tr><td>cloth_fold</td><td>symmetric</td><td>68%</td></tr>
<tr><td>pour_and_hold</td><td>asymmetric</td><td>74%</td></tr>
</table>
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
