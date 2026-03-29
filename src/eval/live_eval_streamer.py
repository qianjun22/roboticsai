#!/usr/bin/env python3
"""
live_eval_streamer.py — Real-time evaluation streamer for GTC live demo.

Streams per-episode results to a browser dashboard as evaluations complete.
The audience sees a live success counter update after each of the 20 episodes.

Features:
  - Dark-theme browser dashboard (opens automatically)
  - Per-episode timeline: episode number, result (✓/✗), cube_z, latency
  - Running success rate with animated counter
  - Phase attribution (approach/grasp/lift/knocked_off) for failed episodes
  - Side-by-side comparison panel: BC baseline vs current run

Usage:
    # Start streaming eval (opens browser at http://localhost:8011)
    python src/eval/live_eval_streamer.py \\
        --server-url http://localhost:8002 \\
        --n-episodes 20 \\
        --label "DAgger Run5 Final"

    # Mock mode (demo-safe, pre-recorded results)
    python src/eval/live_eval_streamer.py --mock --n-episodes 20

    # Comparison mode (BC vs DAgger side by side)
    python src/eval/live_eval_streamer.py \\
        --compare-labels "1000-demo BC" "DAgger Run5" \\
        --compare-success-rates 0.05 0.35
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass, field
from typing import AsyncGenerator, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EpisodeResult:
    episode_n: int
    success: bool
    cube_z: float        # metres — height of cube at end of episode
    latency_ms: float    # inference latency
    phase: str           # phase at termination: approach/grasp/lift/knocked_off/success
    steps: int           # number of environment steps taken


@dataclass
class EvalSession:
    label: str
    n_episodes: int
    results: List[EpisodeResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    completed: bool = False

    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return self.success_count() / len(self.results)

    def to_dict(self) -> dict:
        d = {
            "label": self.label,
            "n_episodes": self.n_episodes,
            "results": [asdict(r) for r in self.results],
            "start_time": self.start_time,
            "completed": self.completed,
            "success_count": self.success_count(),
            "success_rate": round(self.success_rate(), 4),
            "elapsed_s": round(time.time() - self.start_time, 1),
        }
        return d


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

app = FastAPI(title="OCI Robot Cloud — Live Eval Streamer")

_session: Optional[EvalSession] = None
_session_lock = threading.Lock()
_sse_queues: List[asyncio.Queue] = []
_sse_queues_lock = threading.Lock()

# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def _sse_event(data: dict) -> str:
    """Format a single SSE message."""
    return f"data: {json.dumps(data)}\n\n"


def _broadcast(result: EpisodeResult) -> None:
    """Thread-safe push to all live SSE queues (called from eval thread)."""
    payload = asdict(result)
    with _session_lock:
        session_snapshot = _session.to_dict() if _session else {}
    payload["session"] = session_snapshot

    with _sse_queues_lock:
        queues = list(_sse_queues)

    loop = None
    # Find any running event loop to schedule coroutines
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        pass

    for q in queues:
        try:
            # put_nowait is safe to call from any thread once the loop is running
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Live Eval</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --blue: #58a6ff;
    --yellow: #d29922;
    --orange: #db6d28;
    --pill-bg: #21262d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Consolas', 'Menlo', monospace;
    font-size: 14px;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    gap: 24px;
  }
  .logo { font-size: 18px; font-weight: 700; color: var(--blue); letter-spacing: -0.5px; }
  .label-badge {
    background: var(--pill-bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    color: var(--muted);
  }
  .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  main { flex: 1; display: grid; grid-template-columns: 320px 1fr; gap: 0; }
  .sidebar {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    gap: 28px;
  }
  .counter-block { text-align: center; }
  .counter-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .counter-value {
    font-size: 72px;
    font-weight: 800;
    color: var(--green);
    line-height: 1;
    transition: transform 0.15s ease, color 0.3s;
  }
  .counter-value.bump { transform: scale(1.15); }
  .counter-denom { font-size: 28px; color: var(--muted); font-weight: 400; }
  /* Arc gauge */
  .gauge-wrap { display: flex; justify-content: center; }
  svg.gauge { width: 180px; height: 100px; }
  .gauge-track { fill: none; stroke: var(--border); stroke-width: 14; stroke-linecap: round; }
  .gauge-arc { fill: none; stroke: var(--green); stroke-width: 14; stroke-linecap: round; transition: stroke-dashoffset 0.6s ease; }
  .gauge-pct { fill: var(--text); font-size: 22px; font-weight: 700; text-anchor: middle; dominant-baseline: middle; }
  .gauge-sub { fill: var(--muted); font-size: 11px; text-anchor: middle; }
  /* Stats */
  .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .stat-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
  }
  .stat-card .sk { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .stat-card .sv { font-size: 20px; font-weight: 700; }
  /* Content area */
  .content { padding: 24px 28px; display: flex; flex-direction: column; gap: 20px; overflow-y: auto; }
  h2 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
  /* Episode table */
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; font-size: 11px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border); padding: 6px 10px;
  }
  td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr.new-row td { animation: rowSlide 0.3s ease; }
  @keyframes rowSlide { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
  .ep-num { color: var(--muted); font-size: 13px; width: 40px; }
  .badge {
    display: inline-block; border-radius: 4px;
    padding: 2px 8px; font-size: 13px; font-weight: 700;
  }
  .badge.success { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge.fail { background: rgba(248,81,73,0.15); color: var(--red); }
  /* Cube_z bar */
  .z-bar-wrap { width: 120px; background: var(--border); border-radius: 3px; height: 8px; position: relative; }
  .z-bar { height: 8px; border-radius: 3px; background: var(--blue); transition: width 0.4s; }
  .z-val { margin-left: 8px; font-size: 12px; color: var(--muted); white-space: nowrap; }
  /* Latency pill */
  .lat-pill {
    display: inline-block; background: var(--pill-bg);
    border: 1px solid var(--border); border-radius: 20px;
    padding: 2px 10px; font-size: 12px; color: var(--blue);
  }
  /* Phase tag */
  .phase-tag { font-size: 11px; color: var(--muted); }
  .phase-tag.knocked_off { color: var(--orange); }
  .phase-tag.failed_grasp { color: var(--yellow); }
  .phase-tag.failed_approach { color: var(--red); }
  .phase-tag.success { color: var(--green); }
  /* Log */
  #log {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    height: 160px;
    overflow-y: auto;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.6;
  }
  #log .ts { color: var(--border); margin-right: 8px; }
  #log .ok { color: var(--green); }
  #log .fail { color: var(--red); }
  #log .info { color: var(--blue); }
  footer {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 10px 32px;
    font-size: 11px;
    color: var(--muted);
    display: flex; gap: 24px;
  }
</style>
</head>
<body>
<header>
  <span class="logo">OCI Robot Cloud</span>
  <span class="label-badge" id="run-label">Loading…</span>
  <span class="status-dot" id="status-dot"></span>
  <span style="color:var(--muted);font-size:12px" id="status-text">Connecting…</span>
</header>
<main>
  <aside class="sidebar">
    <div class="counter-block">
      <div class="counter-label">Episodes Succeeded</div>
      <div class="counter-value" id="counter">
        <span id="cnt-num">0</span><span class="counter-denom"> / <span id="cnt-total">—</span></span>
      </div>
    </div>
    <div class="gauge-wrap">
      <svg class="gauge" viewBox="0 0 180 100">
        <!-- half-circle arc: cx=90 cy=90 r=70, start=180°, sweep=180° -->
        <path class="gauge-track" d="M 20 90 A 70 70 0 0 1 160 90"/>
        <path class="gauge-arc" id="gauge-arc" d="M 20 90 A 70 70 0 0 1 160 90"
              stroke-dasharray="220" stroke-dashoffset="220"/>
        <text class="gauge-pct" id="gauge-pct" x="90" y="78">0%</text>
        <text class="gauge-sub" x="90" y="95">Success Rate</text>
      </svg>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><div class="sk">Episodes</div><div class="sv" id="stat-done">0</div></div>
      <div class="stat-card"><div class="sk">Remaining</div><div class="sv" id="stat-rem">—</div></div>
      <div class="stat-card"><div class="sk">Avg Latency</div><div class="sv" id="stat-lat">—</div></div>
      <div class="stat-card"><div class="sk">Elapsed</div><div class="sv" id="stat-elapsed">0s</div></div>
    </div>
  </aside>
  <section class="content">
    <div>
      <h2>Episode Timeline</h2>
      <table>
        <thead>
          <tr>
            <th>#</th><th>Result</th><th>Cube Z</th><th>Latency</th><th>Steps</th><th>Phase</th>
          </tr>
        </thead>
        <tbody id="episode-tbody"></tbody>
      </table>
    </div>
    <div>
      <h2>Live Log</h2>
      <div id="log"></div>
    </div>
  </section>
</main>
<footer>
  <span>OCI Robot Cloud · GTC 2027 Live Demo</span>
  <span id="footer-url">http://localhost:8011</span>
  <span id="footer-time"></span>
</footer>
<script>
const Z_MAX = 0.9;  // cube_z normalisation ceiling (metres)

let totalEpisodes = 20;
let latencies = [];

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', {hour12: false});
}

function logLine(cls, msg) {
  const log = document.getElementById('log');
  const now = new Date().toLocaleTimeString('en-US', {hour12:false});
  const el = document.createElement('div');
  el.innerHTML = `<span class="ts">[${now}]</span><span class="${cls}">${msg}</span>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

function updateGauge(rate) {
  const arc = document.getElementById('gauge-arc');
  const pct = document.getElementById('gauge-pct');
  const arcLen = 220;
  const offset = arcLen * (1 - rate);
  arc.setAttribute('stroke-dashoffset', offset.toFixed(1));
  pct.textContent = (rate * 100).toFixed(0) + '%';
  // colour shift: red→yellow→green
  const r = rate < 0.5 ? 248 : Math.round(248 - (rate-0.5)*2*(248-63)) ;
  const g = rate < 0.5 ? Math.round(81 + rate*2*(185-81)) : 185;
  arc.style.stroke = `rgb(${r},${g},80)`;
}

function bumpCounter(val) {
  const el = document.getElementById('counter');
  el.classList.remove('bump');
  void el.offsetWidth;  // reflow
  el.classList.add('bump');
  setTimeout(() => el.classList.remove('bump'), 200);
  document.getElementById('cnt-num').textContent = val;
}

function addEpisodeRow(ep) {
  const tbody = document.getElementById('episode-tbody');
  const tr = document.createElement('tr');
  tr.classList.add('new-row');

  const zPct = Math.min(100, (ep.cube_z / Z_MAX) * 100).toFixed(0);
  const phaseClass = ep.phase.replace(/[^a-z_]/g,'');
  const icon = ep.success ? '✓' : '✗';
  const badgeClass = ep.success ? 'success' : 'fail';

  tr.innerHTML = `
    <td class="ep-num">${ep.episode_n}</td>
    <td><span class="badge ${badgeClass}">${icon}</span></td>
    <td style="display:flex;align-items:center;gap:0">
      <div class="z-bar-wrap"><div class="z-bar" style="width:${zPct}%"></div></div>
      <span class="z-val">${ep.cube_z.toFixed(3)}m</span>
    </td>
    <td><span class="lat-pill">${ep.latency_ms.toFixed(0)}ms</span></td>
    <td style="color:var(--muted)">${ep.steps}</td>
    <td><span class="phase-tag ${phaseClass}">${ep.phase}</span></td>
  `;
  tbody.prepend(tr);  // newest at top
}

function updateStats(session) {
  totalEpisodes = session.n_episodes;
  const done = session.results.length;
  const rem = session.n_episodes - done;
  document.getElementById('cnt-total').textContent = session.n_episodes;
  document.getElementById('stat-done').textContent = done;
  document.getElementById('stat-rem').textContent = rem;
  document.getElementById('stat-elapsed').textContent = session.elapsed_s + 's';
  if (latencies.length > 0) {
    const avg = latencies.reduce((a,b)=>a+b,0)/latencies.length;
    document.getElementById('stat-lat').textContent = avg.toFixed(0) + 'ms';
  }
  document.getElementById('run-label').textContent = session.label || 'Unnamed Run';
  bumpCounter(session.success_count);
  updateGauge(session.success_rate);
}

// SSE connection
const evtSrc = new EventSource('/stream');

evtSrc.onopen = () => {
  document.getElementById('status-text').textContent = 'Connected — waiting for episodes…';
  document.getElementById('status-dot').style.background = 'var(--green)';
  logLine('info', 'SSE stream connected');
};

evtSrc.onerror = () => {
  document.getElementById('status-text').textContent = 'Stream error — retrying…';
  document.getElementById('status-dot').style.background = 'var(--red)';
  logLine('fail', 'SSE connection error');
};

evtSrc.onmessage = (evt) => {
  const data = JSON.parse(evt.data);

  // heartbeat
  if (data.type === 'heartbeat') {
    document.getElementById('footer-time').textContent = 'Heartbeat ' + new Date().toLocaleTimeString();
    return;
  }
  if (data.type === 'session_start') {
    logLine('info', 'Session started: ' + data.label + ' (' + data.n_episodes + ' episodes)');
    document.getElementById('run-label').textContent = data.label;
    document.getElementById('cnt-total').textContent = data.n_episodes;
    document.getElementById('stat-rem').textContent = data.n_episodes;
    return;
  }
  if (data.type === 'session_complete') {
    document.getElementById('status-text').textContent = 'Evaluation complete';
    document.getElementById('status-dot').style.animation = 'none';
    document.getElementById('status-dot').style.background = 'var(--blue)';
    logLine('info', 'Session complete — final rate: ' + (data.success_rate * 100).toFixed(0) + '%');
    return;
  }

  // EpisodeResult event
  const ep = data;
  latencies.push(ep.latency_ms);
  addEpisodeRow(ep);
  if (ep.session) updateStats(ep.session);

  const icon = ep.success ? '✓' : '✗';
  const cls = ep.success ? 'ok' : 'fail';
  const detail = ep.success ? '' : ` [${ep.phase}]`;
  logLine(cls, `Ep ${ep.episode_n}: ${icon} cube_z=${ep.cube_z.toFixed(3)}m  ${ep.latency_ms.toFixed(0)}ms${detail}`);
};

// Clock
setInterval(() => {
  document.getElementById('footer-time').textContent = new Date().toLocaleTimeString();
}, 1000);

// Init: fetch current session
fetch('/session').then(r=>r.json()).then(s => {
  if (s && s.results && s.results.length > 0) {
    logLine('info', 'Restoring ' + s.results.length + ' existing episodes');
    s.results.forEach(ep => { latencies.push(ep.latency_ms); addEpisodeRow(ep); });
    updateStats(s);
  }
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Comparison HTML page
# ---------------------------------------------------------------------------

COMPARE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Robot Cloud — Comparison</title>
<style>
  :root {{ --bg:#0d1117; --surface:#161b22; --border:#30363d; --text:#e6edf3; --muted:#8b949e;
           --green:#3fb950; --red:#f85149; --blue:#58a6ff; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'SF Mono',monospace; font-size:14px; padding:40px; }}
  h1 {{ font-size:22px; color:var(--blue); margin-bottom:32px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:28px; }}
  .card-label {{ font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; }}
  .big-rate {{ font-size:64px; font-weight:800; line-height:1; margin-bottom:8px; }}
  .green {{ color:var(--green); }}
  .red {{ color:var(--red); }}
  .bar-wrap {{ background:var(--border); border-radius:4px; height:16px; margin-top:16px; }}
  .bar {{ height:16px; border-radius:4px; transition:width 1s ease; }}
  .sublabel {{ font-size:12px; color:var(--muted); margin-top:8px; }}
  .delta {{
    text-align:center; background:var(--surface); border:1px solid var(--border);
    border-radius:12px; padding:28px; margin-top:24px;
    font-size:32px; font-weight:700; color:var(--green);
  }}
  .delta span {{ font-size:13px; color:var(--muted); display:block; margin-top:8px; font-weight:400; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Policy Comparison</h1>
<div class="grid">
  {cards}
</div>
<div class="delta">
  +{delta_pct:.0f}% &nbsp; improvement
  <span>{label_a} → {label_b}</span>
</div>
</body>
</html>
"""


def _build_compare_html(labels: List[str], rates: List[float]) -> str:
    cards_html = ""
    colors = ["red", "green"]
    for i, (label, rate) in enumerate(zip(labels, rates)):
        pct = rate * 100
        bar_color = "#3fb950" if rate >= 0.25 else "#f85149"
        cls = colors[min(i, len(colors) - 1)]
        cards_html += f"""
        <div class="card">
          <div class="card-label">{label}</div>
          <div class="big-rate {cls}">{pct:.0f}%</div>
          <div class="sublabel">Success Rate</div>
          <div class="bar-wrap">
            <div class="bar" style="width:{pct:.1f}%; background:{bar_color}"></div>
          </div>
        </div>"""

    delta = (rates[-1] - rates[0]) * 100 if len(rates) >= 2 else 0.0
    label_a = labels[0] if labels else "Baseline"
    label_b = labels[-1] if len(labels) > 1 else "Current"

    return COMPARE_HTML_TEMPLATE.format(
        cards=cards_html,
        delta_pct=delta,
        label_a=label_a,
        label_b=label_b,
    )


# ---------------------------------------------------------------------------
# FastAPI routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/compare", response_class=HTMLResponse)
async def compare_page(
    labels: str = "1000-demo BC,DAgger Run5",
    rates: str = "0.05,0.35",
) -> HTMLResponse:
    label_list = [l.strip() for l in labels.split(",")]
    rate_list = [float(r.strip()) for r in rates.split(",")]
    return HTMLResponse(content=_build_compare_html(label_list, rate_list))


@app.post("/start")
async def start_session(body: dict) -> dict:
    global _session
    label = body.get("label", "Unnamed Run")
    n_episodes = int(body.get("n_episodes", 20))
    with _session_lock:
        _session = EvalSession(label=label, n_episodes=n_episodes)
    # notify all SSE subscribers
    _push_to_queues({"type": "session_start", "label": label, "n_episodes": n_episodes})
    return {"status": "started", "label": label, "n_episodes": n_episodes}


@app.get("/session")
async def get_session() -> dict:
    with _session_lock:
        if _session is None:
            return {}
        return _session.to_dict()


async def _sse_generator() -> AsyncGenerator[str, None]:
    """One SSE generator per connected client."""
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    with _sse_queues_lock:
        _sse_queues.append(q)

    # Send initial heartbeat
    yield await _sse_event({"type": "heartbeat"})

    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=15.0)
                yield await _sse_event(payload)
            except asyncio.TimeoutError:
                yield await _sse_event({"type": "heartbeat"})
    except asyncio.CancelledError:
        pass
    finally:
        with _sse_queues_lock:
            try:
                _sse_queues.remove(q)
            except ValueError:
                pass


@app.get("/stream")
async def stream_events() -> StreamingResponse:
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Queue push helper (thread-safe, from non-async threads)
# ---------------------------------------------------------------------------

def _push_to_queues(payload: dict) -> None:
    with _sse_queues_lock:
        queues = list(_sse_queues)
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Mock eval thread
# ---------------------------------------------------------------------------

FAIL_PHASES = ["knocked_off"] * 7 + ["failed_grasp"] * 15 + ["failed_approach"] * 15


def _mock_eval_thread(n_episodes: int, label: str, seed: int = 42) -> None:
    """Run a fake eval with realistic timing and ~35% success rate."""
    rng = random.Random(seed)
    time.sleep(1.5)  # brief pause before starting

    # Notify session start
    _push_to_queues({"type": "session_start", "label": label, "n_episodes": n_episodes})

    global _session
    with _session_lock:
        _session = EvalSession(label=label, n_episodes=n_episodes)

    successes = 0
    target_successes = round(n_episodes * 0.35)  # ~7/20

    for i in range(1, n_episodes + 1):
        # Decide success/fail deterministically to hit target rate
        remaining = n_episodes - i + 1
        remaining_needed = target_successes - successes
        # Force success if we need all remaining, force fail if already at target
        if remaining_needed <= 0:
            success = False
        elif remaining_needed >= remaining:
            success = True
        else:
            success = rng.random() < 0.35

        if success:
            successes += 1
            cube_z = rng.uniform(0.78, 0.88)   # lifted
            phase = "success"
            steps = rng.randint(38, 55)
        else:
            cube_z = rng.uniform(0.02, 0.25)   # on table or barely moved
            phase = rng.choice(FAIL_PHASES)
            steps = rng.randint(12, 42)

        latency_ms = rng.uniform(225, 280)
        episode_delay = rng.uniform(2.0, 5.0)

        time.sleep(episode_delay)

        result = EpisodeResult(
            episode_n=i,
            success=success,
            cube_z=round(cube_z, 4),
            latency_ms=round(latency_ms, 2),
            phase=phase,
            steps=steps,
        )

        with _session_lock:
            _session.results.append(result)
            session_dict = _session.to_dict()

        payload = asdict(result)
        payload["session"] = session_dict
        _push_to_queues(payload)

    # Mark complete
    with _session_lock:
        _session.completed = True
        final_rate = _session.success_rate()

    _push_to_queues({
        "type": "session_complete",
        "label": label,
        "success_rate": round(final_rate, 4),
        "n_episodes": n_episodes,
    })


# ---------------------------------------------------------------------------
# Live eval thread (calls real inference server)
# ---------------------------------------------------------------------------

def _live_eval_thread(server_url: str, n_episodes: int, label: str) -> None:
    """Poll the inference server for each episode result."""
    global _session
    time.sleep(1.0)

    _push_to_queues({"type": "session_start", "label": label, "n_episodes": n_episodes})

    with _session_lock:
        _session = EvalSession(label=label, n_episodes=n_episodes)

    with httpx.Client(timeout=30.0) as client:
        # Kick off eval on the server
        try:
            resp = client.post(
                f"{server_url}/eval/start",
                json={"n_episodes": n_episodes, "label": label},
            )
            resp.raise_for_status()
        except Exception as exc:
            _push_to_queues({"type": "error", "message": str(exc)})
            return

        # Poll for results
        seen = 0
        max_wait = n_episodes * 60  # generous timeout
        deadline = time.time() + max_wait

        while seen < n_episodes and time.time() < deadline:
            time.sleep(1.0)
            try:
                r = client.get(f"{server_url}/eval/results")
                r.raise_for_status()
                all_results = r.json().get("results", [])
            except Exception:
                continue

            for raw in all_results[seen:]:
                result = EpisodeResult(
                    episode_n=raw["episode_n"],
                    success=raw["success"],
                    cube_z=float(raw.get("cube_z", 0.0)),
                    latency_ms=float(raw.get("latency_ms", 0.0)),
                    phase=raw.get("phase", "unknown"),
                    steps=int(raw.get("steps", 0)),
                )
                with _session_lock:
                    _session.results.append(result)
                    session_dict = _session.to_dict()

                payload = asdict(result)
                payload["session"] = session_dict
                _push_to_queues(payload)
                seen += 1

    with _session_lock:
        _session.completed = True
        final_rate = _session.success_rate()

    _push_to_queues({
        "type": "session_complete",
        "label": label,
        "success_rate": round(final_rate, 4),
        "n_episodes": n_episodes,
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live eval streamer for GTC 2027 demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--server-url", default="http://localhost:8002",
                        help="OCI Robot Cloud inference server URL")
    parser.add_argument("--n-episodes", type=int, default=20,
                        help="Number of episodes to evaluate")
    parser.add_argument("--port", type=int, default=8011,
                        help="Dashboard HTTP port (default: 8011)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Dashboard bind host")
    parser.add_argument("--mock", action="store_true",
                        help="Use pre-recorded mock episodes (demo-safe)")
    parser.add_argument("--label", default="DAgger Run5 Final",
                        help="Human-readable label for this run")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for mock mode")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not auto-open browser")
    parser.add_argument("--compare-labels", nargs="+", metavar="LABEL",
                        help="Labels for comparison page (--compare mode)")
    parser.add_argument("--compare-success-rates", nargs="+", type=float, metavar="RATE",
                        help="Success rates (0.0-1.0) for comparison page")
    args = parser.parse_args()

    dashboard_url = f"http://localhost:{args.port}"

    # If comparison mode, just open the compare page
    if args.compare_labels and args.compare_success_rates:
        labels_str = ",".join(args.compare_labels)
        rates_str = ",".join(str(r) for r in args.compare_success_rates)
        compare_url = f"{dashboard_url}/compare?labels={labels_str}&rates={rates_str}"
        print(f"[live_eval_streamer] Comparison mode — {compare_url}")
        if not args.no_browser:
            threading.Timer(1.5, lambda: webbrowser.open(compare_url)).start()

    # Start eval thread
    if args.mock:
        print(f"[live_eval_streamer] Mock mode — {args.n_episodes} episodes, seed={args.seed}")
        t = threading.Thread(
            target=_mock_eval_thread,
            args=(args.n_episodes, args.label, args.seed),
            daemon=True,
        )
    else:
        print(f"[live_eval_streamer] Live mode — server={args.server_url}")
        t = threading.Thread(
            target=_live_eval_thread,
            args=(args.server_url, args.n_episodes, args.label),
            daemon=True,
        )
    t.start()

    # Open browser
    if not args.no_browser:
        threading.Timer(1.8, lambda: webbrowser.open(dashboard_url)).start()

    print(f"[live_eval_streamer] Dashboard at {dashboard_url}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
