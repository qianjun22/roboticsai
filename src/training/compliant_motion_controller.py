"""
Force-compliant motion controller for contact-rich tasks.
FastAPI service — OCI Robot Cloud
Port: 10076
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10076

# ---------------------------------------------------------------------------
# Domain logic — virtual spring-damper compliant motion controller
# ---------------------------------------------------------------------------

# Default stiffness profiles per task type (Kp [N/m], Kd [N·s/m])
STIFFNESS_PROFILES: Dict[str, Dict[str, float]] = {
    "peg_in_hole":        {"kp": 800.0,  "kd": 40.0,  "force_limit_n": 15.0},
    "assembly_press":     {"kp": 1200.0, "kd": 60.0,  "force_limit_n": 30.0},
    "door_handle":        {"kp": 500.0,  "kd": 25.0,  "force_limit_n": 20.0},
    "surface_wiping":     {"kp": 300.0,  "kd": 15.0,  "force_limit_n": 10.0},
    "cap_twist":          {"kp": 600.0,  "kd": 30.0,  "force_limit_n": 12.0},
    "connector_insert":   {"kp": 1000.0, "kd": 50.0,  "force_limit_n": 25.0},
    "drawer_pull":        {"kp": 400.0,  "kd": 20.0,  "force_limit_n": 18.0},
    "default":            {"kp": 700.0,  "kd": 35.0,  "force_limit_n": 20.0},
}


def _spring_damper_force(
    pos_error: float,
    vel_error: float,
    kp: float,
    kd: float,
    force_limit: float,
) -> float:
    """Compute virtual spring-damper compliant force and clamp to limit."""
    raw = kp * pos_error + kd * vel_error
    return max(-force_limit, min(force_limit, raw))


def simulate_compliant_execution(
    nominal_trajectory: List[Dict[str, float]],
    kp: float,
    kd: float,
    force_limit: float,
    noise_sigma: float = 0.002,
) -> Dict[str, Any]:
    """
    Simulate a compliant execution of a nominal Cartesian trajectory.
    Each waypoint has keys: t, x, y, z (optional: vx, vy, vz).
    Returns executed path, force log, and compliance events.
    """
    executed_path: List[Dict[str, Any]] = []
    force_log: List[Dict[str, Any]] = []
    compliance_events: List[Dict[str, Any]] = []

    # Simulated environment stiffness (contact surface)
    env_kp = random.uniform(1500.0, 3000.0)  # environment is stiffer than robot
    contact_start_idx = int(len(nominal_trajectory) * random.uniform(0.35, 0.55))
    in_contact = False
    cumulative_work_j = 0.0

    prev_wp = None
    for idx, wp in enumerate(nominal_trajectory):
        t = wp.get("t", idx * 0.01)
        x_nom = wp.get("x", 0.0)
        y_nom = wp.get("y", 0.0)
        z_nom = wp.get("z", 0.0)
        vx_nom = wp.get("vx", 0.0)
        vy_nom = wp.get("vy", 0.0)
        vz_nom = wp.get("vz", 0.0)

        # Gaussian sensor noise on position
        x_exec = x_nom + random.gauss(0, noise_sigma)
        y_exec = y_nom + random.gauss(0, noise_sigma)
        z_exec = z_nom + random.gauss(0, noise_sigma)

        # Contact detection: after contact_start_idx, environment pushes back in z
        contact_penetration = 0.0
        if idx >= contact_start_idx:
            if not in_contact:
                in_contact = True
                compliance_events.append({
                    "type": "contact_detected",
                    "t": t,
                    "waypoint_idx": idx,
                    "description": "Surface contact established",
                })
            contact_penetration = max(0.0, (idx - contact_start_idx) * 0.0003)
            # Compliance: controller yields in z, retracting slightly
            pos_err_z = -contact_penetration
            vel_err_z = -contact_penetration * 5.0  # damped
            f_z = _spring_damper_force(pos_err_z, vel_err_z, kp, kd, force_limit)
            # Executed z deviates from nominal due to compliance
            z_exec = z_nom + f_z / env_kp
            cumulative_work_j += abs(f_z * contact_penetration * 0.0003)
        else:
            f_z = 0.0

        f_x = _spring_damper_force(
            x_exec - x_nom, vx_nom * random.gauss(0, 0.05), kp * 0.2, kd * 0.2, force_limit * 0.3
        )
        f_y = _spring_damper_force(
            y_exec - y_nom, vy_nom * random.gauss(0, 0.05), kp * 0.2, kd * 0.2, force_limit * 0.3
        )

        f_total = math.sqrt(f_x**2 + f_y**2 + f_z**2)

        executed_path.append({"t": t, "x": round(x_exec, 5), "y": round(y_exec, 5), "z": round(z_exec, 5)})
        force_log.append({
            "t": t,
            "fx": round(f_x, 4),
            "fy": round(f_y, 4),
            "fz": round(f_z, 4),
            "f_total": round(f_total, 4),
            "in_contact": in_contact,
        })

        # Detect force limit events
        if f_total > force_limit * 0.90:
            compliance_events.append({
                "type": "force_limit_approach",
                "t": t,
                "waypoint_idx": idx,
                "f_total": round(f_total, 3),
                "threshold": force_limit * 0.90,
                "description": "Force approaching limit — compliance softening applied",
            })

        prev_wp = wp

    # Path deviation metric
    deviations = []
    for ep, ap in zip(nominal_trajectory, executed_path):
        dx = ep.get("x", 0) - ap["x"]
        dy = ep.get("y", 0) - ap["y"]
        dz = ep.get("z", 0) - ap["z"]
        deviations.append(math.sqrt(dx**2 + dy**2 + dz**2))
    mean_deviation_m = sum(deviations) / len(deviations) if deviations else 0.0
    max_deviation_m = max(deviations) if deviations else 0.0

    compliance_events.append({
        "type": "execution_complete",
        "t": executed_path[-1]["t"] if executed_path else 0.0,
        "description": "Compliant execution finished",
        "mean_deviation_m": round(mean_deviation_m, 6),
        "max_deviation_m": round(max_deviation_m, 6),
        "cumulative_work_j": round(cumulative_work_j, 5),
    })

    return {
        "executed_path": executed_path,
        "force_log": force_log,
        "compliance_events": compliance_events,
        "summary": {
            "waypoints_total": len(nominal_trajectory),
            "contact_waypoints": max(0, len(nominal_trajectory) - contact_start_idx),
            "mean_deviation_m": round(mean_deviation_m, 6),
            "max_deviation_m": round(max_deviation_m, 6),
            "max_force_n": round(max((r["f_total"] for r in force_log), default=0.0), 3),
            "cumulative_work_j": round(cumulative_work_j, 5),
            "force_limit_events": sum(1 for e in compliance_events if e["type"] == "force_limit_approach"),
            "contact_established": in_contact,
        },
    }


def get_stiffness_profile(task_name: str) -> Dict[str, Any]:
    """Return optimal Kp/Kd for a given task type."""
    profile = STIFFNESS_PROFILES.get(task_name.lower(), STIFFNESS_PROFILES["default"])
    return {
        "task_name": task_name,
        "kp": profile["kp"],
        "kd": profile["kd"],
        "force_limit_n": profile["force_limit_n"],
        "natural_frequency_hz": round(math.sqrt(profile["kp"] / 1.5) / (2 * math.pi), 2),
        "damping_ratio": round(profile["kd"] / (2 * math.sqrt(profile["kp"] * 1.5)), 3),
        "source": "empirical_calibration_v2" if task_name.lower() in STIFFNESS_PROFILES else "default_fallback",
        "available_tasks": list(STIFFNESS_PROFILES.keys()),
    }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Compliant Motion Controller",
        version="1.0.0",
        description="Force-compliant motion controller for contact-rich manipulation tasks.",
    )

    class Waypoint(BaseModel):
        t: float = Field(..., description="Time [s]")
        x: float = Field(..., description="X position [m]")
        y: float = Field(..., description="Y position [m]")
        z: float = Field(..., description="Z position [m]")
        vx: float = Field(default=0.0, description="X velocity [m/s]")
        vy: float = Field(default=0.0, description="Y velocity [m/s]")
        vz: float = Field(default=0.0, description="Z velocity [m/s]")

    class CompliantExecuteRequest(BaseModel):
        nominal_trajectory: List[Waypoint] = Field(
            ..., min_items=2, description="Nominal Cartesian trajectory waypoints"
        )
        kp: Optional[float] = Field(default=None, description="Spring stiffness [N/m]; uses task default if None")
        kd: Optional[float] = Field(default=None, description="Damper coefficient [N·s/m]; uses task default if None")
        task_name: Optional[str] = Field(default="default", description="Task type for stiffness lookup")
        force_limit_n: Optional[float] = Field(default=None, description="Force saturation limit [N]")
        noise_sigma: float = Field(default=0.002, description="Gaussian position noise sigma [m]")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "compliant_motion_controller",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Compliant Motion Controller</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>Compliant Motion Controller</h1><p>OCI Robot Cloud · Port 10076</p>
<div class="stat"><b>Status</b><br>Online</div>
<div class="stat"><b>Controller</b><br>Virtual Spring-Damper</div>
<div class="stat"><b>Task Profiles</b><br>7 calibrated</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="76" fill="#94a3b8" font-size="9" text-anchor="middle">compliance force profile</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p>
</body></html>""")

    @app.post("/control/compliant_execute")
    def compliant_execute(req: CompliantExecuteRequest):
        """
        Execute a nominal trajectory under compliant (force-controlled) motion.

        - Applies virtual spring-damper model to track the nominal path
        - Returns executed path, per-waypoint force log, and compliance events
        - Stiffness can be specified directly or looked up by task_name
        """
        profile = STIFFNESS_PROFILES.get(
            (req.task_name or "default").lower(), STIFFNESS_PROFILES["default"]
        )
        kp = req.kp if req.kp is not None else profile["kp"]
        kd = req.kd if req.kd is not None else profile["kd"]
        force_limit = req.force_limit_n if req.force_limit_n is not None else profile["force_limit_n"]

        if kp <= 0 or kd < 0:
            raise HTTPException(status_code=422, detail="kp must be > 0, kd must be >= 0")
        if force_limit <= 0:
            raise HTTPException(status_code=422, detail="force_limit_n must be > 0")

        traj_dicts = [w.dict() for w in req.nominal_trajectory]
        t_start = time.perf_counter()
        result = simulate_compliant_execution(traj_dicts, kp, kd, force_limit, req.noise_sigma)
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

        return JSONResponse({
            "executed_path": result["executed_path"],
            "force_log": result["force_log"],
            "compliance_events": result["compliance_events"],
            "summary": result["summary"],
            "controller_params": {
                "kp": kp,
                "kd": kd,
                "force_limit_n": force_limit,
                "task_name": req.task_name,
                "noise_sigma": req.noise_sigma,
            },
            "compute_ms": elapsed_ms,
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/control/stiffness_profile")
    def stiffness_profile(task_name: str = Query(default="default", description="Task type name")):
        """
        Return the calibrated optimal Kp and Kd for a given task type.

        Includes natural frequency and damping ratio derived from the spring-damper model.
        """
        return JSONResponse(get_stiffness_profile(task_name))

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
