"""
Real-Time Policy Visualization Dashboard
Streams GR00T's current action predictions as a live browser dashboard via SSE.
Useful during closed-loop eval to watch the policy in real time.

Usage:
    python realtime_policy_viz.py --mock
    python realtime_policy_viz.py --host 0.0.0.0 --port 8047
"""

import argparse
import asyncio
import json
import math
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PolicyState:
    step: int = 0
    joint_positions: list = field(default_factory=lambda: [0.0] * 9)
    joint_predictions: list = field(default_factory=lambda: [[0.0] * 9 for _ in range(16)])
    cube_z: float = 0.70
    ee_pos: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    gripper_width: float = 0.08
    phase: str = "approach"
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_policy(state: PolicyState, rng: random.Random) -> None:
    """Background thread: updates PolicyState every 200ms simulating a robot episode."""
    PHASE_STEPS = {"approach": 40, "grasp": 20, "lift": 30, "hold": 10}
    phase_order = ["approach", "grasp", "lift", "hold"]
    phase_idx = 0
    phase_step = 0
    episode = 0

    # Joint home positions (radians) for a 7-DOF arm + 2 gripper
    home_joints = [0.0, -0.3, 0.0, -1.8, 0.0, 1.5, 0.8, 0.04, 0.04]
    cube_z_start = 0.70
    cube_z_target = 0.82

    while True:
        phase = phase_order[phase_idx]
        total_phase_steps = PHASE_STEPS[phase]
        t = phase_step / max(total_phase_steps - 1, 1)  # [0, 1]

        # Simulate latency (180-280ms with occasional spikes)
        latency = rng.gauss(230, 25)
        if rng.random() < 0.05:
            latency += rng.uniform(50, 150)
        latency = max(150.0, latency)

        # Joint positions evolve smoothly per phase
        joints = list(state.joint_positions)
        if phase == "approach":
            # Move arm toward cube
            target = [0.3, -0.5, 0.1, -1.6, 0.05, 1.3, 0.9, 0.04, 0.04]
            for i in range(9):
                joints[i] = home_joints[i] + (target[i] - home_joints[i]) * t
            cube_z = cube_z_start
            ee_pos = [0.3 * t, 0.0, 0.15 - 0.05 * t]
            gripper_width = 0.08
        elif phase == "grasp":
            # Close gripper
            target = [0.3, -0.5, 0.1, -1.6, 0.05, 1.3, 0.9, 0.0, 0.0]
            for i in range(9):
                joints[i] = joints[i] + rng.gauss(0, 0.002)
            joints[7] = 0.08 * (1.0 - t)
            joints[8] = 0.08 * (1.0 - t)
            cube_z = cube_z_start
            ee_pos = [0.3, 0.0, 0.10]
            gripper_width = 0.08 * (1.0 - t)
        elif phase == "lift":
            # Lift the cube
            for i in range(9):
                joints[i] = joints[i] + rng.gauss(0, 0.003)
            joints[1] = -0.5 + 0.3 * t
            joints[3] = -1.6 + 0.4 * t
            cube_z = cube_z_start + (cube_z_target - cube_z_start) * t
            ee_pos = [0.3, 0.0, 0.10 + 0.12 * t]
            gripper_width = 0.0
        else:  # hold
            for i in range(9):
                joints[i] = joints[i] + rng.gauss(0, 0.001)
            cube_z = cube_z_target - rng.gauss(0, 0.002)
            ee_pos = [0.3, 0.0, 0.22]
            gripper_width = 0.0

        # Generate 16-step action chunk predictions (small perturbations ahead)
        predictions = []
        for chunk_t in range(16):
            chunk_joints = []
            for j in range(9):
                delta = rng.gauss(0, 0.015) * (1 + chunk_t * 0.05)
                chunk_joints.append(joints[j] + delta)
            predictions.append(chunk_joints)

        # Update shared state (thread-safe via GIL for simple assignments)
        state.step = episode * sum(PHASE_STEPS.values()) + sum(
            PHASE_STEPS[phase_order[k]] for k in range(phase_idx)
        ) + phase_step
        state.joint_positions = joints
        state.joint_predictions = predictions
        state.cube_z = float(cube_z)
        state.ee_pos = list(ee_pos)
        state.gripper_width = float(gripper_width)
        state.phase = phase
        state.latency_ms = round(latency, 1)
        state.timestamp = datetime.now(timezone.utc).isoformat()

        phase_step += 1
        if phase_step >= total_phase_steps:
            phase_step = 0
            phase_idx = (phase_idx + 1) % len(phase_order)
            if phase_idx == 0:
                episode += 1

        time.sleep(0.2)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GR00T Real-Time Policy Viz — Port 8047</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f1117; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 16px; }
  h1 { font-size: 1.3rem; color: #a78bfa; margin-bottom: 4px; }
  .subtitle { font-size: 0.8rem; color: #64748b; margin-bottom: 16px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
  .card { background: #1e2130; border-radius: 10px; padding: 16px; }
  .card h2 { font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  /* Phase badge */
  #phase-badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-weight: 600; font-size: 0.9rem; }
  .phase-approach { background: #1e3a5f; color: #60a5fa; }
  .phase-grasp    { background: #451a03; color: #fbbf24; }
  .phase-lift     { background: #2e1065; color: #c084fc; }
  .phase-hold     { background: #052e16; color: #4ade80; }
  /* Joint bars */
  .joint-row { display: flex; align-items: center; margin-bottom: 6px; gap: 8px; }
  .joint-label { width: 24px; font-size: 0.75rem; color: #64748b; text-align: right; }
  .bar-bg { flex: 1; background: #2d3748; border-radius: 4px; height: 14px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.18s ease; }
  .bar-val { width: 52px; font-size: 0.72rem; color: #94a3b8; text-align: right; font-family: monospace; }
  /* Heatmap */
  #heatmap { display: grid; grid-template-columns: repeat(9, 1fr); gap: 2px; }
  .hm-cell { height: 18px; border-radius: 2px; transition: background 0.18s ease; }
  .hm-axis-row { display: grid; grid-template-columns: repeat(9, 1fr); gap: 2px; margin-top: 4px; }
  .hm-axis-cell { text-align: center; font-size: 0.62rem; color: #4a5568; }
  /* Cube Z gauge */
  .gauge-wrap { display: flex; gap: 12px; align-items: flex-start; }
  .gauge-bar-outer { width: 28px; height: 160px; background: #2d3748; border-radius: 4px; position: relative; overflow: hidden; }
  .gauge-bar-fill { position: absolute; bottom: 0; width: 100%; border-radius: 4px; transition: height 0.18s ease; background: linear-gradient(to top, #4ade80, #a78bfa); }
  .gauge-target { position: absolute; left: 0; right: 0; height: 2px; background: #fbbf24; }
  .gauge-labels { display: flex; flex-direction: column; justify-content: space-between; height: 160px; font-size: 0.7rem; color: #64748b; }
  .gauge-info { flex: 1; }
  .gauge-val { font-size: 1.4rem; font-weight: 700; color: #a78bfa; font-family: monospace; }
  .gauge-unit { font-size: 0.75rem; color: #64748b; }
  /* Stats */
  .stat-row { display: flex; justify-content: space-between; margin-bottom: 8px; }
  .stat-label { font-size: 0.8rem; color: #64748b; }
  .stat-val { font-size: 0.85rem; font-family: monospace; color: #e2e8f0; }
  /* Latency */
  .latency-val { font-size: 2rem; font-weight: 700; font-family: monospace; }
  .latency-ok    { color: #4ade80; }
  .latency-warn  { color: #fbbf24; }
  .latency-slow  { color: #f87171; }
  .latency-hist  { display: flex; align-items: flex-end; gap: 2px; height: 40px; margin-top: 8px; }
  .latency-bar   { flex: 1; border-radius: 2px 2px 0 0; min-width: 6px; background: #4ade80; transition: height 0.18s ease; }
  /* Status dot */
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot-green { background: #4ade80; animation: pulse 1.2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  #conn-status { font-size: 0.78rem; color: #64748b; margin-bottom: 12px; }
</style>
</head>
<body>
<h1>GR00T Real-Time Policy Visualization</h1>
<p class="subtitle">Live action predictions from inference server — port 8047</p>
<div id="conn-status"><span class="dot dot-green" id="conn-dot"></span><span id="conn-text">Connecting…</span></div>

<div class="grid">

  <!-- Card 1: Phase + Stats -->
  <div class="card">
    <h2>Episode State</h2>
    <div style="margin-bottom:14px;">
      <span id="phase-badge" class="phase-approach">approach</span>
    </div>
    <div class="stat-row"><span class="stat-label">Step</span><span class="stat-val" id="stat-step">0</span></div>
    <div class="stat-row"><span class="stat-label">EE X</span><span class="stat-val" id="stat-ee-x">0.000</span></div>
    <div class="stat-row"><span class="stat-label">EE Y</span><span class="stat-val" id="stat-ee-y">0.000</span></div>
    <div class="stat-row"><span class="stat-label">EE Z</span><span class="stat-val" id="stat-ee-z">0.000</span></div>
    <div class="stat-row"><span class="stat-label">Gripper</span><span class="stat-val" id="stat-gripper">0.080</span></div>
    <div class="stat-row"><span class="stat-label">Timestamp</span><span class="stat-val" id="stat-ts" style="font-size:0.7rem;">—</span></div>
  </div>

  <!-- Card 2: Joint Positions -->
  <div class="card">
    <h2>Joint Positions (current)</h2>
    <div id="joint-bars"></div>
  </div>

  <!-- Card 3: Latency -->
  <div class="card">
    <h2>Inference Latency</h2>
    <div class="latency-val latency-ok" id="latency-val">—</div>
    <div style="font-size:0.75rem;color:#64748b;margin-top:2px;">ms  &nbsp; <span id="latency-avg" style="color:#94a3b8;"></span></div>
    <div class="latency-hist" id="latency-hist"></div>
  </div>

  <!-- Card 4: Cube Z Gauge (spans 1 col) -->
  <div class="card">
    <h2>Cube Z Height</h2>
    <div class="gauge-wrap">
      <div class="gauge-labels">
        <span>0.82m</span>
        <span>0.78m ★</span>
        <span>0.74m</span>
        <span>0.70m</span>
      </div>
      <div class="gauge-bar-outer" id="gauge-outer">
        <div class="gauge-bar-fill" id="gauge-fill" style="height:0%"></div>
        <div class="gauge-target" id="gauge-target" style="bottom:66.7%"></div>
      </div>
      <div class="gauge-info">
        <div class="gauge-val" id="gauge-val">0.700</div>
        <div class="gauge-unit">meters</div>
        <div style="margin-top:12px;font-size:0.75rem;color:#64748b;">
          Target: <span style="color:#fbbf24;">0.780m</span><br>
          Range: 0.70 – 0.82
        </div>
      </div>
    </div>
  </div>

  <!-- Card 5: Action Prediction Heatmap (spans 2 cols) -->
  <div class="card" style="grid-column: span 2;">
    <h2>Action Prediction Heatmap &nbsp;<span style="font-size:0.7rem;color:#4a5568;">(16 chunks × 9 joints)</span></h2>
    <div id="heatmap"></div>
    <div class="hm-axis-row" id="hm-axis"></div>
  </div>

</div>

<script>
// ---- Joint bars init ----
const jointNames = ['J1','J2','J3','J4','J5','J6','J7','G-L','G-R'];
const jointColors = ['#60a5fa','#34d399','#a78bfa','#f472b6','#fbbf24','#38bdf8','#fb7185','#94a3b8','#94a3b8'];
const barsDiv = document.getElementById('joint-bars');
jointNames.forEach((name, i) => {
  barsDiv.innerHTML += `<div class="joint-row">
    <span class="joint-label">${name}</span>
    <div class="bar-bg"><div class="bar-fill" id="jbar-${i}" style="width:50%;background:${jointColors[i]}"></div></div>
    <span class="bar-val" id="jval-${i}">0.000</span>
  </div>`;
});

// ---- Heatmap init ----
const heatmap = document.getElementById('heatmap');
const hmAxis = document.getElementById('hm-axis');
for (let t = 0; t < 16; t++) {
  for (let j = 0; j < 9; j++) {
    const cell = document.createElement('div');
    cell.className = 'hm-cell';
    cell.id = `hm-${t}-${j}`;
    heatmap.appendChild(cell);
  }
}
jointNames.forEach(n => { hmAxis.innerHTML += `<div class="hm-axis-cell">${n}</div>`; });

// ---- Latency history ----
const latencyHist = new Array(20).fill(0);
const latencyHistDiv = document.getElementById('latency-hist');
for (let i = 0; i < 20; i++) {
  latencyHistDiv.innerHTML += `<div class="latency-bar" id="lbar-${i}" style="height:0%"></div>`;
}

// ---- Helpers ----
function valToColor(v, minV, maxV) {
  const t = Math.max(0, Math.min(1, (v - minV) / (maxV - minV)));
  const r = Math.round(30 + t * 180);
  const g = Math.round(30 + (1 - Math.abs(t - 0.5) * 2) * 120);
  const b = Math.round(180 - t * 140);
  return `rgb(${r},${g},${b})`;
}

function jointToPercent(v) {
  // Map roughly [-pi, pi] to [0, 100]
  return Math.max(2, Math.min(98, (v / (2 * Math.PI) + 0.5) * 100));
}

// ---- State update ----
function applyState(s) {
  // Phase badge
  const badge = document.getElementById('phase-badge');
  badge.textContent = s.phase;
  badge.className = 'phase-' + s.phase;

  // Stats
  document.getElementById('stat-step').textContent = s.step;
  document.getElementById('stat-ee-x').textContent = s.ee_pos[0].toFixed(3);
  document.getElementById('stat-ee-y').textContent = s.ee_pos[1].toFixed(3);
  document.getElementById('stat-ee-z').textContent = s.ee_pos[2].toFixed(3);
  document.getElementById('stat-gripper').textContent = s.gripper_width.toFixed(3);
  document.getElementById('stat-ts').textContent = s.timestamp.slice(11, 23) + 'Z';

  // Joint bars
  s.joint_positions.forEach((v, i) => {
    const pct = jointToPercent(v);
    document.getElementById(`jbar-${i}`).style.width = pct + '%';
    document.getElementById(`jval-${i}`).textContent = v.toFixed(3);
  });

  // Heatmap
  const allVals = s.joint_predictions.flat();
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  for (let t = 0; t < 16; t++) {
    for (let j = 0; j < 9; j++) {
      const cell = document.getElementById(`hm-${t}-${j}`);
      if (cell) cell.style.background = valToColor(s.joint_predictions[t][j], minV, maxV);
    }
  }

  // Cube Z gauge
  const zMin = 0.70, zMax = 0.82, zTarget = 0.78;
  const pct = ((s.cube_z - zMin) / (zMax - zMin)) * 100;
  const targetPct = ((zTarget - zMin) / (zMax - zMin)) * 100;
  document.getElementById('gauge-fill').style.height = Math.max(0, Math.min(100, pct)) + '%';
  document.getElementById('gauge-target').style.bottom = targetPct + '%';
  document.getElementById('gauge-val').textContent = s.cube_z.toFixed(3);

  // Latency
  const lat = s.latency_ms;
  latencyHist.push(lat);
  latencyHist.shift();
  const latVal = document.getElementById('latency-val');
  latVal.textContent = lat.toFixed(0);
  latVal.className = 'latency-val ' + (lat < 250 ? 'latency-ok' : lat < 350 ? 'latency-warn' : 'latency-slow');
  const avg = latencyHist.reduce((a, b) => a + b, 0) / latencyHist.filter(x => x > 0).length || 0;
  document.getElementById('latency-avg').textContent = `avg ${avg.toFixed(0)}ms`;
  const maxLat = Math.max(...latencyHist, 1);
  latencyHist.forEach((v, i) => {
    const bar = document.getElementById(`lbar-${i}`);
    if (bar) bar.style.height = Math.max(2, (v / maxLat) * 100) + '%';
  });
}

// ---- SSE client with auto-reconnect ----
let evtSource = null;
let reconnectDelay = 1000;

function connect() {
  document.getElementById('conn-text').textContent = 'Connecting…';
  document.getElementById('conn-dot').style.background = '#fbbf24';

  evtSource = new EventSource('/api/stream');

  evtSource.onopen = () => {
    document.getElementById('conn-text').textContent = 'Connected — live';
    document.getElementById('conn-dot').style.background = '#4ade80';
    reconnectDelay = 1000;
  };

  evtSource.onmessage = (event) => {
    try {
      const state = JSON.parse(event.data);
      applyState(state);
    } catch (e) { console.warn('Parse error', e); }
  };

  evtSource.onerror = () => {
    document.getElementById('conn-text').textContent = `Reconnecting in ${reconnectDelay / 1000}s…`;
    document.getElementById('conn-dot').style.background = '#f87171';
    evtSource.close();
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 15000);
  };
}

connect();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

def create_app(mock: bool = True):
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(title="GR00T Real-Time Policy Visualization", version="1.0.0")

    # Shared state + RNG
    state = PolicyState()
    rng = random.Random()

    # Start background simulation thread
    sim_thread = threading.Thread(target=simulate_policy, args=(state, rng), daemon=True)
    sim_thread.start()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/api/stream")
    async def sse_stream():
        async def event_generator():
            while True:
                data = json.dumps(asdict(state))
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.2)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/state")
    async def get_state():
        return JSONResponse(content=asdict(state))

    @app.get("/health")
    async def health():
        return JSONResponse(content={"status": "ok", "service": "realtime_policy_viz", "port": 8047})

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GR00T Real-Time Policy Visualization Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8047, help="Port to listen on (default: 8047)")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated policy data (default: True)")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: FastAPI/uvicorn not installed.")
        print("Install with: pip install fastapi uvicorn")
        return

    print(f"Starting GR00T Real-Time Policy Viz on http://{args.host}:{args.port}")
    print(f"  Dashboard : http://localhost:{args.port}/")
    print(f"  SSE stream: http://localhost:{args.port}/api/stream")
    print(f"  REST poll : http://localhost:{args.port}/api/state")
    print(f"  Health    : http://localhost:{args.port}/health")

    app = create_app(mock=args.mock)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
