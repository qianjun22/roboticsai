"""
Real-time inference monitoring dashboard for GR00T API.
Tracks RPS, latency, and success rates per partner. Port 8074.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InferenceRequest:
    request_id: str
    timestamp: float          # Unix epoch seconds
    partner_id: str
    task_name: str
    chunk_size: int
    latency_ms: float
    success: bool
    confidence: float
    action_norm: float


@dataclass
class WindowStats:
    window_s: int
    n_requests: int
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    success_rate: float
    avg_confidence: float


@dataclass
class MonitorState:
    uptime_s: float
    total_requests: int
    window_1m: WindowStats
    window_5m: WindowStats
    top_partners: List[dict]
    recent_requests: List[dict]


# ---------------------------------------------------------------------------
# In-memory ring buffer (shared across both modes)
# ---------------------------------------------------------------------------

MAX_HISTORY = 10_000
_start_time: float = time.time()
_requests: deque = deque(maxlen=MAX_HISTORY)


def _window_stats(window_s: int) -> WindowStats:
    now = time.time()
    cutoff = now - window_s
    subset = [r for r in _requests if r.timestamp >= cutoff]
    n = len(subset)
    if n == 0:
        return WindowStats(window_s=window_s, n_requests=0, rps=0.0,
                           p50_ms=0.0, p95_ms=0.0, p99_ms=0.0,
                           success_rate=0.0, avg_confidence=0.0)
    latencies = sorted(r.latency_ms for r in subset)
    def pct(data, p):
        idx = int(math.ceil(p / 100.0 * len(data))) - 1
        return data[max(0, idx)]
    successes = sum(1 for r in subset if r.success)
    return WindowStats(
        window_s=window_s,
        n_requests=n,
        rps=round(n / window_s, 3),
        p50_ms=round(pct(latencies, 50), 1),
        p95_ms=round(pct(latencies, 95), 1),
        p99_ms=round(pct(latencies, 99), 1),
        success_rate=round(successes / n, 4),
        avg_confidence=round(statistics.mean(r.confidence for r in subset), 4),
    )


def _top_partners(top_n: int = 5) -> List[dict]:
    counts: dict = {}
    for r in _requests:
        counts.setdefault(r.partner_id, {"requests": 0, "success": 0, "latencies": []})
        counts[r.partner_id]["requests"] += 1
        if r.success:
            counts[r.partner_id]["success"] += 1
        counts[r.partner_id]["latencies"].append(r.latency_ms)
    result = []
    for pid, data in sorted(counts.items(), key=lambda x: -x[1]["requests"])[:top_n]:
        lat = sorted(data["latencies"])
        p95 = lat[int(math.ceil(0.95 * len(lat))) - 1] if lat else 0
        result.append({
            "partner_id": pid,
            "requests": data["requests"],
            "success_rate": round(data["success"] / data["requests"], 4),
            "p95_ms": round(p95, 1),
        })
    return result


def _recent_requests(n: int = 10) -> List[dict]:
    items = list(_requests)[-n:]
    items.reverse()
    out = []
    for r in items:
        out.append({
            "request_id": r.request_id,
            "partner_id": r.partner_id,
            "task_name": r.task_name,
            "latency_ms": round(r.latency_ms, 1),
            "success": r.success,
            "confidence": round(r.confidence, 3),
            "ts": datetime.fromtimestamp(r.timestamp, tz=timezone.utc).strftime("%H:%M:%S"),
        })
    return out


def _monitor_state() -> MonitorState:
    return MonitorState(
        uptime_s=round(time.time() - _start_time, 1),
        total_requests=len(_requests),
        window_1m=_window_stats(60),
        window_5m=_window_stats(300),
        top_partners=_top_partners(),
        recent_requests=_recent_requests(),
    )


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

PARTNERS = ["partner_alpha", "partner_beta", "partner_gamma"]
TASKS = [
    "pick_and_place", "stack_blocks", "open_drawer",
    "push_object", "grasp_cup", "door_handle",
]

def _random_request(ts_offset: float = 0.0) -> InferenceRequest:
    rid = f"req_{random.randint(100000, 999999)}"
    latency = max(50.0, random.gauss(230, 25))
    return InferenceRequest(
        request_id=rid,
        timestamp=time.time() - ts_offset,
        partner_id=random.choice(PARTNERS),
        task_name=random.choice(TASKS),
        chunk_size=random.choice([16, 32, 64]),
        latency_ms=round(latency, 2),
        success=random.random() < 0.78,
        confidence=round(random.uniform(0.60, 0.98), 4),
        action_norm=round(random.uniform(0.5, 1.5), 4),
    )


def seed_mock_requests(n: int = 50) -> None:
    """Inject n random requests spread across the last 5 minutes."""
    for i in range(n):
        offset = random.uniform(0, 300)
        _requests.append(_random_request(ts_offset=offset))


# ---------------------------------------------------------------------------
# Dashboard HTML template
# ---------------------------------------------------------------------------

def _build_html(state: MonitorState) -> str:
    state_json = json.dumps(asdict(state), indent=2)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>GR00T Inference Monitor — OCI Robot Cloud</title>
<style>
  :root {{
    --bg: #1e293b;
    --panel: #0f172a;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --red: #C74634;
    --green: #22c55e;
    --yellow: #eab308;
    --blue: #38bdf8;
    --accent: #C74634;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: var(--red); font-size: 1.5rem; letter-spacing: 0.04em; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px; }}
  .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .panel h2 {{ color: var(--red); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }}
  .stat-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.88rem; }}
  .stat-row:last-child {{ border-bottom: none; }}
  .val {{ color: var(--blue); font-weight: 600; font-variant-numeric: tabular-nums; }}
  /* Gauge */
  .gauge-wrap {{ display: flex; flex-direction: column; align-items: center; }}
  svg.gauge {{ overflow: visible; }}
  /* Sparkline */
  svg.spark {{ width: 100%; height: 60px; }}
  /* Badges */
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }}
  .badge-ok {{ background: #14532d; color: var(--green); }}
  .badge-fail {{ background: #7f1d1d; color: #fca5a5; }}
  /* Recent table */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  th {{ color: var(--muted); text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); font-weight: 500; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b88; }}
  .partner-tag {{ background: #1e3a5f; color: var(--blue); padding: 1px 6px; border-radius: 3px; font-size: 0.78rem; }}
  .uptime-bar {{ color: var(--muted); font-size: 0.82rem; margin-bottom: 20px; }}
  .uptime-bar span {{ color: var(--text); font-weight: 600; }}
</style>
</head>
<body>
<h1>GR00T Inference Monitor</h1>
<p class="subtitle">OCI Robot Cloud &mdash; Port 8074 &mdash; Real-time policy inference telemetry</p>

<div class="uptime-bar" id="uptimeBar">
  Uptime: <span id="uptime">—</span> &nbsp;|&nbsp;
  Total requests: <span id="totalReq">—</span> &nbsp;|&nbsp;
  Last refreshed: <span id="lastRefresh">—</span>
</div>

<div class="grid">
  <!-- Latency Gauge -->
  <div class="panel">
    <h2>Latency Gauge (p50, 1-min)</h2>
    <div class="gauge-wrap">
      <svg class="gauge" width="220" height="130" viewBox="0 0 220 130">
        <!-- track arc 0-500ms mapped to -180° to 0° (left to right semicircle) -->
        <path d="M 20 110 A 90 90 0 0 1 200 110" fill="none" stroke="#334155" stroke-width="16" stroke-linecap="round"/>
        <path id="gaugeArc" d="M 20 110 A 90 90 0 0 1 200 110" fill="none" stroke="#C74634" stroke-width="16"
              stroke-linecap="round" stroke-dasharray="283" stroke-dashoffset="283" style="transition:stroke-dashoffset 0.8s ease"/>
        <!-- tick marks -->
        <text x="14" y="126" fill="#64748b" font-size="10">0</text>
        <text x="98" y="24" fill="#64748b" font-size="10" text-anchor="middle">250ms</text>
        <text x="196" y="126" fill="#64748b" font-size="10" text-anchor="end">500</text>
        <!-- needle -->
        <line id="gaugeNeedle" x1="110" y1="110" x2="110" y2="30"
              stroke="#f8fafc" stroke-width="2" stroke-linecap="round"
              style="transform-origin:110px 110px; transform:rotate(-90deg); transition:transform 0.8s ease"/>
        <circle cx="110" cy="110" r="5" fill="#C74634"/>
        <!-- value text -->
        <text id="gaugeVal" x="110" y="100" fill="#e2e8f0" font-size="18" font-weight="bold" text-anchor="middle">—</text>
        <text x="110" y="118" fill="#94a3b8" font-size="10" text-anchor="middle">ms p50</text>
      </svg>
    </div>
  </div>

  <!-- Sparkline -->
  <div class="panel">
    <h2>RPS Sparkline (60 ticks × 3s)</h2>
    <svg class="spark" id="sparkSvg" viewBox="0 0 300 60" preserveAspectRatio="none">
      <polyline id="sparkLine" points="" fill="none" stroke="#C74634" stroke-width="2"/>
      <line x1="0" y1="59" x2="300" y2="59" stroke="#334155" stroke-width="1"/>
    </svg>
    <div style="color:var(--muted);font-size:0.82rem;margin-top:8px;">
      Current RPS (1-min): <span id="rps1m" style="color:var(--blue);font-weight:600;">—</span>
      &nbsp;&nbsp; 5-min: <span id="rps5m" style="color:var(--blue);font-weight:600;">—</span>
    </div>
  </div>
</div>

<!-- Stats Table -->
<div class="panel" style="margin-bottom:16px;">
  <h2>Window Statistics</h2>
  <table>
    <thead>
      <tr>
        <th>Window</th>
        <th>Requests</th>
        <th>RPS</th>
        <th>p50 ms</th>
        <th>p95 ms</th>
        <th>p99 ms</th>
        <th>Success %</th>
        <th>Avg Conf</th>
      </tr>
    </thead>
    <tbody id="statsBody">
      <tr><td colspan="8" style="color:var(--muted);text-align:center;">Loading…</td></tr>
    </tbody>
  </table>
</div>

<!-- Top Partners -->
<div class="panel" style="margin-bottom:16px;">
  <h2>Top Partners</h2>
  <table>
    <thead>
      <tr><th>Partner</th><th>Requests</th><th>Success %</th><th>p95 ms</th></tr>
    </thead>
    <tbody id="partnersBody">
      <tr><td colspan="4" style="color:var(--muted);text-align:center;">Loading…</td></tr>
    </tbody>
  </table>
</div>

<!-- Recent Requests -->
<div class="panel">
  <h2>Recent Requests (last 10)</h2>
  <table>
    <thead>
      <tr><th>Time</th><th>Request ID</th><th>Partner</th><th>Task</th><th>Latency</th><th>Confidence</th><th>Status</th></tr>
    </thead>
    <tbody id="recentBody">
      <tr><td colspan="7" style="color:var(--muted);text-align:center;">Loading…</td></tr>
    </tbody>
  </table>
</div>

<script>
// Inject initial snapshot for static report
const INITIAL_STATE = {state_json};

const MAX_SPARK = 60;
let sparkHistory = [];
let initialized = false;

function pct(v) {{ return (v * 100).toFixed(1) + '%'; }}
function ms(v)  {{ return v.toFixed(1) + ' ms'; }}

function updateGauge(p50) {{
  const max = 500;
  const ratio = Math.min(p50 / max, 1);
  // arc: total perimeter of semicircle arc ≈ π*r = π*90 ≈ 283
  const arc = 283;
  const offset = arc - ratio * arc;
  document.getElementById('gaugeArc').style.strokeDashoffset = offset;
  // needle: -90deg = 0ms, 0deg = 250ms, +90deg = 500ms
  const deg = -90 + ratio * 180;
  document.getElementById('gaugeNeedle').style.transform = `rotate(${{deg}}deg)`;
  document.getElementById('gaugeVal').textContent = p50.toFixed(0);
}}

function updateSpark(rps) {{
  sparkHistory.push(rps);
  if (sparkHistory.length > MAX_SPARK) sparkHistory.shift();
  const svg = document.getElementById('sparkSvg');
  const W = 300, H = 60;
  const maxV = Math.max(...sparkHistory, 0.1);
  const pts = sparkHistory.map((v, i) => {{
    const x = (i / (MAX_SPARK - 1)) * W;
    const y = H - 4 - (v / maxV) * (H - 8);
    return `${{x.toFixed(1)}},${{y.toFixed(1)}}`;
  }}).join(' ');
  document.getElementById('sparkLine').setAttribute('points', pts);
}}

function renderStats(state) {{
  const w1 = state.window_1m, w5 = state.window_5m;
  document.getElementById('uptime').textContent = state.uptime_s.toFixed(0) + 's';
  document.getElementById('totalReq').textContent = state.total_requests;
  document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
  document.getElementById('rps1m').textContent = w1.rps.toFixed(3);
  document.getElementById('rps5m').textContent = w5.rps.toFixed(3);

  updateGauge(w1.p50_ms || 0);
  updateSpark(w1.rps);

  document.getElementById('statsBody').innerHTML = [w1, w5].map(w => `
    <tr>
      <td>${{w.window_s === 60 ? '1 min' : '5 min'}}</td>
      <td class="val">${{w.n_requests}}</td>
      <td class="val">${{w.rps.toFixed(3)}}</td>
      <td class="val">${{ms(w.p50_ms)}}</td>
      <td class="val">${{ms(w.p95_ms)}}</td>
      <td class="val">${{ms(w.p99_ms)}}</td>
      <td class="val">${{pct(w.success_rate)}}</td>
      <td class="val">${{w.avg_confidence.toFixed(3)}}</td>
    </tr>`).join('');

  document.getElementById('partnersBody').innerHTML = state.top_partners.map(p => `
    <tr>
      <td><span class="partner-tag">${{p.partner_id}}</span></td>
      <td class="val">${{p.requests}}</td>
      <td class="val">${{pct(p.success_rate)}}</td>
      <td class="val">${{ms(p.p95_ms)}}</td>
    </tr>`).join('');

  document.getElementById('recentBody').innerHTML = state.recent_requests.map(r => `
    <tr>
      <td style="color:var(--muted)">${{r.ts}}</td>
      <td style="font-family:monospace;font-size:0.8rem">${{r.request_id}}</td>
      <td><span class="partner-tag">${{r.partner_id}}</span></td>
      <td>${{r.task_name}}</td>
      <td class="val">${{r.latency_ms.toFixed(1)}} ms</td>
      <td style="color:var(--muted)">${{r.confidence.toFixed(3)}}</td>
      <td><span class="badge ${{r.success ? 'badge-ok' : 'badge-fail'}}">${{r.success ? 'OK' : 'FAIL'}}</span></td>
    </tr>`).join('');
}}

// Initial render from embedded snapshot
renderStats(INITIAL_STATE);

// Live refresh (only effective when server is running)
async function refresh() {{
  try {{
    const resp = await fetch('/api/stats');
    if (resp.ok) renderStats(await resp.json());
  }} catch (e) {{ /* server not running — static report */ }}
}}
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app (imported lazily so stdlib-only mock mode works)
# ---------------------------------------------------------------------------

def _build_fastapi_app():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="GR00T Inference Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        state = _monitor_state()
        return _build_html(state)

    @app.get("/api/stats")
    async def api_stats():
        return JSONResponse(asdict(_monitor_state()))

    @app.post("/api/inject")
    async def api_inject(count: int = 1):
        """Inject mock request events for testing."""
        for _ in range(count):
            _requests.append(_random_request(ts_offset=0.0))
        return {"injected": count, "total": len(_requests)}

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="GR00T Real-time Inference Monitor — port 8074"
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Seed mock data (default: True)")
    parser.add_argument("--serve", action="store_true", default=False,
                        help="Start FastAPI server instead of writing static HTML")
    parser.add_argument("--port", type=int, default=8074,
                        help="Server port (default: 8074)")
    parser.add_argument("--output", default="/tmp/realtime_inference_monitor.html",
                        help="Output path for static HTML report")
    parser.add_argument("--seed", type=int, default=50,
                        help="Number of mock requests to seed (default: 50)")
    args = parser.parse_args()

    # Always seed mock data
    random.seed(42)
    seed_mock_requests(args.seed)

    if args.serve:
        try:
            import uvicorn
        except ImportError:
            print("ERROR: uvicorn is required for --serve mode. Install with: pip install uvicorn fastapi")
            raise SystemExit(1)
        app = _build_fastapi_app()
        print(f"[GR00T Monitor] Starting server on http://0.0.0.0:{args.port}")
        print(f"[GR00T Monitor] Dashboard: http://localhost:{args.port}/")
        print(f"[GR00T Monitor] Stats API: http://localhost:{args.port}/api/stats")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    else:
        # Static mock report — stdlib only
        state = _monitor_state()
        html = _build_html(state)
        output_path = args.output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[GR00T Monitor] Static report written to: {output_path}")
        print(f"[GR00T Monitor] Seeded {args.seed} mock requests")
        w1 = state.window_1m
        w5 = state.window_5m
        print(f"[GR00T Monitor] 1-min window: {w1.n_requests} reqs, "
              f"RPS={w1.rps:.3f}, p50={w1.p50_ms:.1f}ms, "
              f"p95={w1.p95_ms:.1f}ms, success={w1.success_rate*100:.1f}%")
        print(f"[GR00T Monitor] 5-min window: {w5.n_requests} reqs, "
              f"RPS={w5.rps:.3f}, p50={w5.p50_ms:.1f}ms, "
              f"p95={w5.p95_ms:.1f}ms, success={w5.success_rate*100:.1f}%")
        print(f"[GR00T Monitor] To start live server: python {__file__} --serve --port {args.port}")


if __name__ == "__main__":
    main()
