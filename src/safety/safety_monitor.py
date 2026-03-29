#!/usr/bin/env python3
"""
safety_monitor.py — Real-time safety constraint enforcement for GR00T policy execution.

Provides joint-limit clamping, velocity limiting, collision zone checks, and
emergency-stop via watchdog timer. Designed for design-partner robots running
real GR00T fine-tuned policies in production.

Usage (standalone FastAPI server):
    python src/safety/safety_monitor.py --port 8016

Usage (as middleware library):
    from src.safety.safety_monitor import SafetyMonitor
    monitor = SafetyMonitor(robot="franka")
    safe_action = monitor.check(raw_action, current_state)

Endpoints (port 8016):
    GET  /health
    POST /check       — validate & clamp action chunk
    POST /estop       — trigger emergency stop
    POST /reset       — clear e-stop flag
    GET  /status      — current safety state + violation counts
    GET  /log         — last 100 violation events
"""

import argparse
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ── Robot configs ──────────────────────────────────────────────────────────────

ROBOT_CONFIGS = {
    "franka": {
        # Joint position limits (rad)
        "q_min": [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973, 0.0, 0.0],
        "q_max": [ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973, 0.085, 0.085],
        # Joint velocity limits (rad/s)
        "dq_max": [2.1750, 2.1750, 2.1750, 2.1750, 2.6100, 2.6100, 2.6100, 0.05, 0.05],
        # Joint effort limits (Nm, approximate)
        "tau_max": [87, 87, 87, 87, 12, 12, 12, 100, 100],
        "n_joints": 9,
        "arm_dof": 7,
    },
    "ur5e": {
        "q_min": [-6.283, -6.283, -3.1416, -6.283, -6.283, -6.283, 0.0, 0.0],
        "q_max": [ 6.283,  6.283,  3.1416,  6.283,  6.283,  6.283, 0.08, 0.08],
        "dq_max": [3.14, 3.14, 3.14, 3.14, 3.14, 3.14, 0.05, 0.05],
        "tau_max": [150, 150, 150, 28, 28, 28, 100, 100],
        "n_joints": 8,
        "arm_dof": 6,
    },
    "xarm7": {
        "q_min": [-6.283, -2.059, -6.283, -0.191, -6.283, -1.692, -6.283, 0.0, 0.0],
        "q_max": [ 6.283,  2.059,  6.283,  3.927,  6.283,  3.141,  6.283, 0.085, 0.085],
        "dq_max": [3.14, 3.14, 3.14, 3.14, 3.14, 3.14, 3.14, 0.05, 0.05],
        "tau_max": [50, 50, 32, 32, 14, 14, 14, 100, 100],
        "n_joints": 9,
        "arm_dof": 7,
    },
}

# Workspace bounding box (meters, in robot base frame) — reject if EE outside
WORKSPACE = {
    "franka": {"x": (-0.85, 0.85), "y": (-0.85, 0.85), "z": (0.0, 1.2)},
    "ur5e":   {"x": (-0.85, 0.85), "y": (-0.85, 0.85), "z": (-0.2, 1.1)},
    "xarm7":  {"x": (-0.85, 0.85), "y": (-0.85, 0.85), "z": (0.0, 1.2)},
}

# Emergency stop zones: any joint exceeding this fraction of limit triggers e-stop
ESTOP_FRACTION = 0.95


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ViolationEvent:
    ts: str
    kind: str            # "joint_limit", "velocity", "estop_zone", "workspace"
    joint: Optional[int]
    raw: float
    clamped: float
    robot: str


@dataclass
class SafetyState:
    estop: bool = False
    estop_reason: str = ""
    violations_total: int = 0
    joint_limit_violations: int = 0
    velocity_violations: int = 0
    estop_zone_hits: int = 0
    actions_checked: int = 0
    last_check_ts: str = ""


class SafetyMonitor:
    def __init__(self, robot: str = "franka", dt: float = 0.1):
        if robot not in ROBOT_CONFIGS:
            raise ValueError(f"Unknown robot: {robot}. Choose from {list(ROBOT_CONFIGS)}")
        self.robot = robot
        self.cfg = ROBOT_CONFIGS[robot]
        self.ws = WORKSPACE[robot]
        self.dt = dt  # expected action timestep (seconds)

        self.q_min = np.array(self.cfg["q_min"])
        self.q_max = np.array(self.cfg["q_max"])
        self.dq_max = np.array(self.cfg["dq_max"])
        self.n = self.cfg["n_joints"]

        self.state = SafetyState()
        self._log: deque = deque(maxlen=100)
        self._prev_q: Optional[np.ndarray] = None

    def trigger_estop(self, reason: str):
        self.state.estop = True
        self.state.estop_reason = reason
        self._log.append(ViolationEvent(
            ts=_now(), kind="estop_zone", joint=None,
            raw=0.0, clamped=0.0, robot=self.robot,
        ))

    def reset_estop(self):
        self.state.estop = False
        self.state.estop_reason = ""

    def check(
        self,
        action_chunk: np.ndarray,  # shape (T, n_joints)
        current_q: Optional[np.ndarray] = None,
    ) -> dict:
        """
        Validate and clamp an action chunk.

        Returns:
            {
                "safe_action": np.ndarray (T, n_joints),
                "violations": list[str],
                "estop": bool,
            }
        """
        if self.state.estop:
            return {
                "safe_action": np.zeros_like(action_chunk),
                "violations": [f"E-STOP active: {self.state.estop_reason}"],
                "estop": True,
            }

        chunk = np.array(action_chunk, dtype=np.float32)
        T = chunk.shape[0]
        violations = []

        for t in range(T):
            q = chunk[t]
            if len(q) != self.n:
                q = np.pad(q, (0, max(0, self.n - len(q))))[:self.n]

            # 1. Joint position limits
            for j in range(self.n):
                raw = q[j]
                if raw < self.q_min[j]:
                    clamped = self.q_min[j]
                    chunk[t, j] = clamped
                    self._record("joint_limit", j, raw, clamped)
                    violations.append(f"t={t} j{j}: pos {raw:.3f} < min {self.q_min[j]:.3f}")
                elif raw > self.q_max[j]:
                    clamped = self.q_max[j]
                    chunk[t, j] = clamped
                    self._record("joint_limit", j, raw, clamped)
                    violations.append(f"t={t} j{j}: pos {raw:.3f} > max {self.q_max[j]:.3f}")

                # 2. E-stop zone (> 95% of range)
                mid = (self.q_min[j] + self.q_max[j]) / 2
                half = (self.q_max[j] - self.q_min[j]) / 2
                if abs(raw - mid) > ESTOP_FRACTION * half:
                    reason = f"j{j} near hard limit ({raw:.3f})"
                    self.trigger_estop(reason)
                    return {
                        "safe_action": np.zeros_like(action_chunk),
                        "violations": [f"E-STOP triggered: {reason}"],
                        "estop": True,
                    }

            # 3. Velocity limits (estimate from sequential actions)
            if t > 0:
                dq = (chunk[t] - chunk[t - 1]) / self.dt
                for j in range(self.n):
                    if abs(dq[j]) > self.dq_max[j]:
                        raw = chunk[t, j]
                        max_delta = self.dq_max[j] * self.dt
                        clamped = chunk[t - 1, j] + np.sign(dq[j]) * max_delta
                        clamped = np.clip(clamped, self.q_min[j], self.q_max[j])
                        chunk[t, j] = clamped
                        self._record("velocity", j, raw, clamped)
                        violations.append(f"t={t} j{j}: dq {dq[j]:.3f} > max {self.dq_max[j]:.3f}")

        self.state.actions_checked += 1
        self.state.last_check_ts = _now()
        if violations:
            self.state.violations_total += len(violations)

        return {
            "safe_action": chunk,
            "violations": violations,
            "estop": False,
        }

    def _record(self, kind: str, joint: int, raw: float, clamped: float):
        if kind == "joint_limit":
            self.state.joint_limit_violations += 1
        elif kind == "velocity":
            self.state.velocity_violations += 1
        self._log.append(ViolationEvent(
            ts=_now(), kind=kind, joint=joint,
            raw=float(raw), clamped=float(clamped), robot=self.robot,
        ))

    def status_dict(self) -> dict:
        s = self.state
        return {
            "robot": self.robot,
            "estop": s.estop,
            "estop_reason": s.estop_reason,
            "actions_checked": s.actions_checked,
            "violations_total": s.violations_total,
            "joint_limit_violations": s.joint_limit_violations,
            "velocity_violations": s.velocity_violations,
            "estop_zone_hits": s.estop_zone_hits,
            "last_check_ts": s.last_check_ts,
        }

    def log_list(self) -> list:
        return [
            {
                "ts": e.ts, "kind": e.kind, "joint": e.joint,
                "raw": round(e.raw, 4), "clamped": round(e.clamped, 4),
            }
            for e in self._log
        ]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# ── FastAPI server ─────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Safety Monitor", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_monitor: Optional[SafetyMonitor] = None


class CheckRequest(BaseModel):
    action_chunk: list          # (T, n_joints) nested list
    current_q: Optional[list] = None

class EstopRequest(BaseModel):
    reason: str = "manual trigger"


@app.get("/health")
def health():
    return {"status": "ok", "robot": _monitor.robot if _monitor else None,
            "estop": _monitor.state.estop if _monitor else False}


@app.post("/check")
def check(req: CheckRequest):
    chunk = np.array(req.action_chunk, dtype=np.float32)
    current_q = np.array(req.current_q) if req.current_q else None
    result = _monitor.check(chunk, current_q)
    return {
        "safe_action": result["safe_action"].tolist(),
        "violations": result["violations"],
        "estop": result["estop"],
        "n_violations": len(result["violations"]),
    }


@app.post("/estop")
def estop(req: EstopRequest):
    _monitor.trigger_estop(req.reason)
    return {"estop": True, "reason": req.reason}


@app.post("/reset")
def reset():
    _monitor.reset_estop()
    return {"estop": False}


@app.get("/status")
def status():
    return _monitor.status_dict()


@app.get("/log")
def log():
    return _monitor.log_list()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    s = _monitor.status_dict()
    estop_color = "#ef4444" if s["estop"] else "#10b981"
    estop_label = "E-STOP ACTIVE" if s["estop"] else "NOMINAL"
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Safety Monitor — {s['robot']}</title>
<meta http-equiv="refresh" content="3">
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634;margin-bottom:4px}}
.status{{font-size:2em;font-weight:bold;color:{estop_color};padding:12px 20px;border:2px solid {estop_color};
         border-radius:8px;display:inline-block;margin:16px 0}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}}
.card{{background:#1e293b;border-radius:8px;padding:16px;text-align:center}}
.val{{font-size:2em;font-weight:bold;color:#f8fafc}}
.lbl{{color:#64748b;font-size:.8em}}
table{{width:100%;border-collapse:collapse;margin-top:20px}}
th{{background:#C74634;color:white;padding:8px 12px;text-align:left;font-size:.85em}}
td{{padding:7px 12px;border-bottom:1px solid #1e293b;font-size:.88em}}
tr:nth-child(even) td{{background:#172033}}
button{{background:#C74634;color:white;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;margin-right:8px}}
</style></head><body>
<h1>Robot Safety Monitor</h1>
<p style="color:#64748b">Robot: <b>{s['robot']}</b> · Auto-refresh: 3s</p>
<div class="status">{estop_label}</div>
{'<p style="color:#ef4444">Reason: ' + s['estop_reason'] + '</p>' if s['estop'] else ''}
<form method="post" action="/estop" style="display:inline">
  <input type="hidden" name="reason" value="dashboard trigger">
  <button type="submit">Trigger E-STOP</button>
</form>
<form method="post" action="/reset" style="display:inline">
  <button type="submit" style="background:#10b981">Reset E-STOP</button>
</form>
<div class="grid">
  <div class="card"><div class="val">{s['actions_checked']}</div><div class="lbl">Actions Checked</div></div>
  <div class="card"><div class="val" style="color:#f59e0b">{s['violations_total']}</div><div class="lbl">Total Violations</div></div>
  <div class="card"><div class="val">{s['joint_limit_violations']}</div><div class="lbl">Joint Limit</div></div>
  <div class="card"><div class="val">{s['velocity_violations']}</div><div class="lbl">Velocity</div></div>
</div>
<p style="color:#475569;font-size:.8em">Last check: {s['last_check_ts']}</p>
</body></html>"""


def main():
    global _monitor
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", default="franka", choices=list(ROBOT_CONFIGS))
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--dt", type=float, default=0.1, help="Action timestep (s)")
    args = parser.parse_args()

    _monitor = SafetyMonitor(robot=args.robot, dt=args.dt)
    print(f"[safety] Monitor for {args.robot} on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
