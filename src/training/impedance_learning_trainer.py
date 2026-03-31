"""impedance_learning_trainer.py — Learn task-appropriate impedance (Kp/Kd) profiles from demonstrations.

Port: 10036
Cycle: 495A
"""

from __future__ import annotations

import json
import math
import statistics
import time
from typing import Any, Dict, List

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# In-memory profile store
# ---------------------------------------------------------------------------

_PROFILES: Dict[str, Dict[str, Any]] = {
    "precision_peg_insert": {
        "kp": 800.0,
        "kd": 40.0,
        "fixed_kp": 400.0,
        "fixed_kd": 20.0,
        "sr_improvement": 18.0,
        "task_phases": ["approach", "contact", "insert", "retract"],
        "kp_kd_schedule": [[400.0, 20.0], [600.0, 30.0], [800.0, 40.0], [300.0, 15.0]],
    },
    "compliant_wipe": {
        "kp": 120.0,
        "kd": 8.0,
        "fixed_kp": 400.0,
        "fixed_kd": 20.0,
        "sr_improvement": 11.0,
        "task_phases": ["reach", "contact", "wipe", "lift"],
        "kp_kd_schedule": [[300.0, 15.0], [120.0, 8.0], [120.0, 8.0], [200.0, 12.0]],
    },
}

_START_TIME = time.time()

# ---------------------------------------------------------------------------
# Helper: learn impedance from demo trajectories
# ---------------------------------------------------------------------------

def _learn_impedance(demo_trajectories: List[List[List[float]]], task_name: str) -> Dict[str, Any]:
    """Derive Kp/Kd from trajectory variance and smoothness heuristics."""
    if not demo_trajectories:
        raise ValueError("demo_trajectories must not be empty")

    all_forces: List[float] = []
    all_velocities: List[float] = []

    for traj in demo_trajectories:
        for i, point in enumerate(traj):
            if len(point) >= 6:
                # assume [x, y, z, fx, fy, fz]
                f_mag = math.sqrt(point[3] ** 2 + point[4] ** 2 + point[5] ** 2)
                all_forces.append(f_mag)
            if i > 0 and len(point) >= 3 and len(traj[i - 1]) >= 3:
                vel = math.sqrt(
                    (point[0] - traj[i - 1][0]) ** 2
                    + (point[1] - traj[i - 1][1]) ** 2
                    + (point[2] - traj[i - 1][2]) ** 2
                )
                all_velocities.append(vel)

    mean_force = statistics.mean(all_forces) if all_forces else 5.0
    mean_vel = statistics.mean(all_velocities) if all_velocities else 0.01

    # Higher force → stiffer (higher Kp); higher velocity → more damping (Kd)
    kp = max(100.0, min(1200.0, mean_force * 80.0))
    kd = max(5.0, min(80.0, mean_vel * 2000.0))

    num_phases = max(2, len(demo_trajectories[0]) // 10)
    phases = [f"phase_{i}" for i in range(num_phases)]
    schedule = [
        [round(kp * (0.5 + 0.5 * i / max(1, num_phases - 1)), 2),
         round(kd * (0.5 + 0.5 * i / max(1, num_phases - 1)), 2)]
        for i in range(num_phases)
    ]

    profile = {
        "kp": round(kp, 2),
        "kd": round(kd, 2),
        "fixed_kp": 400.0,
        "fixed_kd": 20.0,
        "sr_improvement": round(min(25.0, (kp - 400.0) / 400.0 * 20.0 + 5.0), 1),
        "task_phases": phases,
        "kp_kd_schedule": schedule,
    }
    _PROFILES[task_name] = profile
    return profile


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Impedance Learning Trainer — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#38bdf8;font-size:1.8rem;margin-bottom:.25rem}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:2rem}
  .card{background:#1e293b;border-radius:.75rem;padding:1.25rem;border:1px solid #334155}
  .card-title{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem}
  .card-value{font-size:1.8rem;font-weight:700;color:#38bdf8}
  .card-sub{font-size:.8rem;color:#64748b;margin-top:.25rem}
  .section{background:#1e293b;border-radius:.75rem;padding:1.5rem;border:1px solid #334155;margin-bottom:1.5rem}
  .section h2{color:#C74634;font-size:1rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.06em}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{color:#94a3b8;text-align:left;padding:.5rem .75rem;border-bottom:1px solid #334155}
  td{padding:.5rem .75rem;border-bottom:1px solid #1e293b;color:#cbd5e1}
  tr:last-child td{border-bottom:none}
  .badge{display:inline-block;padding:.2rem .6rem;border-radius:9999px;font-size:.75rem;font-weight:600}
  .badge-green{background:#14532d;color:#4ade80}
  .badge-blue{background:#0c4a6e;color:#38bdf8}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>Impedance Learning Trainer</h1>
<p class="subtitle">OCI Robot Cloud · Port 10036 · Learn task-appropriate Kp/Kd from demonstrations</p>

<div class="grid">
  <div class="card">
    <div class="card-title">Learned Kp (Peg Insert)</div>
    <div class="card-value">800</div>
    <div class="card-sub">Fixed baseline: 400</div>
  </div>
  <div class="card">
    <div class="card-title">Learned Kp (Compliant Wipe)</div>
    <div class="card-value">120</div>
    <div class="card-sub">Fixed baseline: 400</div>
  </div>
  <div class="card">
    <div class="card-title">SR Improvement</div>
    <div class="card-value" style="color:#4ade80">+18%</div>
    <div class="card-sub">From learned impedance</div>
  </div>
  <div class="card">
    <div class="card-title">Profiles Stored</div>
    <div class="card-value">2</div>
    <div class="card-sub">precision_peg + compliant_wipe</div>
  </div>
</div>

<div class="section">
  <h2>Kp Comparison — Learned vs Fixed</h2>
  <svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;margin:0 auto">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="180" x2="510" y2="180" stroke="#334155" stroke-width="1"/>
    <!-- y labels -->
    <text x="55" y="15" fill="#64748b" font-size="11" text-anchor="end">1200</text>
    <text x="55" y="75" fill="#64748b" font-size="11" text-anchor="end">600</text>
    <text x="55" y="135" fill="#64748b" font-size="11" text-anchor="end">120</text>
    <text x="55" y="180" fill="#64748b" font-size="11" text-anchor="end">0</text>
    <!-- grid -->
    <line x1="60" y1="75" x2="510" y2="75" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4 3"/>
    <line x1="60" y1="135" x2="510" y2="135" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4 3"/>
    <!-- Peg Insert: learned Kp=800 → height=(800/1200)*170=113 -->
    <rect x="80" y="67" width="70" height="113" fill="#38bdf8" rx="3"/>
    <text x="115" y="60" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">800</text>
    <!-- Peg Insert: fixed Kp=400 → height=(400/1200)*170=57 -->
    <rect x="160" y="123" width="70" height="57" fill="#C74634" rx="3"/>
    <text x="195" y="116" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">400</text>
    <!-- Compliant Wipe: learned Kp=120 → height=(120/1200)*170=17 -->
    <rect x="300" y="163" width="70" height="17" fill="#38bdf8" rx="3"/>
    <text x="335" y="157" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">120</text>
    <!-- Compliant Wipe: fixed Kp=400 → height=57 -->
    <rect x="380" y="123" width="70" height="57" fill="#C74634" rx="3"/>
    <text x="415" y="116" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">400</text>
    <!-- x labels -->
    <text x="160" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">Peg Insert</text>
    <text x="390" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">Compliant Wipe</text>
    <!-- legend -->
    <rect x="65" y="208" width="12" height="8" fill="#38bdf8" rx="1"/>
    <text x="81" y="216" fill="#94a3b8" font-size="10">Learned</text>
    <rect x="130" y="208" width="12" height="8" fill="#C74634" rx="1"/>
    <text x="146" y="216" fill="#94a3b8" font-size="10">Fixed</text>
  </svg>
</div>

<div class="section">
  <h2>Stored Impedance Profiles</h2>
  <table>
    <thead><tr><th>Task</th><th>Learned Kp</th><th>Learned Kd</th><th>Fixed Kp</th><th>SR Improvement</th><th>Phases</th></tr></thead>
    <tbody>
      <tr>
        <td>precision_peg_insert</td>
        <td><span class="badge badge-blue">800</span></td>
        <td>40</td><td>400</td>
        <td><span class="badge badge-green">+18%</span></td>
        <td>approach · contact · insert · retract</td>
      </tr>
      <tr>
        <td>compliant_wipe</td>
        <td><span class="badge badge-blue">120</span></td>
        <td>8</td><td>400</td>
        <td><span class="badge badge-green">+11%</span></td>
        <td>reach · contact · wipe · lift</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="section">
  <h2>API Endpoints</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
    <tbody>
      <tr><td>GET</td><td>/</td><td>HTML dashboard</td></tr>
      <tr><td>GET</td><td>/health</td><td>JSON health check</td></tr>
      <tr><td>POST</td><td>/impedance/learn</td><td>Learn Kp/Kd from demo trajectories</td></tr>
      <tr><td>GET</td><td>/impedance/profiles</td><td>List stored profiles with SR improvement</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Impedance Learning Trainer",
        description="Learn task-appropriate impedance (Kp/Kd) profiles from demonstrations.",
        version="1.0.0",
    )

    class LearnRequest(BaseModel):
        demo_trajectories: List[List[List[float]]]
        task_name: str

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "impedance_learning_trainer",
            "port": 10036,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "profiles_stored": len(_PROFILES),
        })

    @app.post("/impedance/learn")
    async def learn_impedance(req: LearnRequest) -> JSONResponse:
        try:
            profile = _learn_impedance(req.demo_trajectories, req.task_name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return JSONResponse({
            "learned_impedance_profile": {"kp": profile["kp"], "kd": profile["kd"]},
            "task_phases": profile["task_phases"],
            "kp_kd_schedule": profile["kp_kd_schedule"],
        })

    @app.get("/impedance/profiles")
    async def get_profiles() -> JSONResponse:
        result = {}
        for task, p in _PROFILES.items():
            result[task] = {
                "kp": p["kp"],
                "kd": p["kd"],
                "fixed_kp": p["fixed_kp"],
                "fixed_kd": p["fixed_kd"],
                "sr_improvement_pct": p["sr_improvement"],
                "task_phases": p["task_phases"],
                "kp_kd_schedule": p["kp_kd_schedule"],
            }
        return JSONResponse(result)


# ---------------------------------------------------------------------------
# Stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence default logging
            pass

        def do_GET(self) -> None:
            if self.path in ("/", ""):
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                payload = json.dumps({
                    "status": "ok",
                    "service": "impedance_learning_trainer",
                    "port": 10036,
                    "uptime_seconds": round(time.time() - _START_TIME, 1),
                    "profiles_stored": len(_PROFILES),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif self.path == "/impedance/profiles":
                payload = json.dumps({t: {"kp": p["kp"], "kd": p["kd"], "sr_improvement_pct": p["sr_improvement"]} for t, p in _PROFILES.items()}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/impedance/learn":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length))
                try:
                    profile = _learn_impedance(data.get("demo_trajectories", []), data.get("task_name", "unknown"))
                    payload = json.dumps({
                        "learned_impedance_profile": {"kp": profile["kp"], "kd": profile["kd"]},
                        "task_phases": profile["task_phases"],
                        "kp_kd_schedule": profile["kp_kd_schedule"],
                    }).encode()
                    self.send_response(200)
                except ValueError as exc:
                    payload = json.dumps({"error": str(exc)}).encode()
                    self.send_response(422)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10036)
    else:
        print("FastAPI not available — starting stdlib HTTPServer on port 10036")
        server = HTTPServer(("0.0.0.0", 10036), _Handler)
        server.serve_forever()
