"""dagger_run127_planner.py — Continual DAgger run-127 planner (port 10046).

Cycle-497B | OCI Robot Cloud

Ring buffer (capacity 5000, FIFO eviction) tracks corrections across an
never-ending correction loop.  SR trajectory: month1=85 → month2=89 →
month3=92 → month6=95 → plateau=97.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from typing import Deque, Dict, Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse as _urlparse

# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------
BUFFER_CAPACITY = 5000

class _RingBuffer:
    """Fixed-capacity FIFO ring buffer for DAgger corrections."""

    def __init__(self, capacity: int) -> None:
        self._buf: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self.capacity = capacity
        self.total_added = 0
        self.total_evicted = 0

    def push(self, item: Dict[str, Any]) -> None:
        if len(self._buf) == self.capacity:
            self.total_evicted += 1
        self._buf.append(item)
        self.total_added += 1

    @property
    def size(self) -> int:
        return len(self._buf)

    @property
    def fill_pct(self) -> float:
        return round(self.size / self.capacity * 100, 2)


_ring = _RingBuffer(BUFFER_CAPACITY)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_state: Dict[str, Any] = {
    "run_id": "run127",
    "mode": "continual",
    "day": 0,
    "month1_sr": 85.0,
    "month2_sr": 89.0,
    "month3_sr": 92.0,
    "month6_sr": 95.0,
    "plateau_sr": 97.0,
    "current_sr": 85.0,
    "started_at": time.time(),
}

DAILY_IMPROVEMENT = 0.3  # %/day
FINETUNE_THRESHOLD = 500  # trigger fine-tune when buffer grows by this many
_last_finetune_buffer = 0


def _compute_sr(day: int) -> float:
    """Smooth SR curve: logistic ramp clamped to plateau."""
    # Approximately: day 30→85%, day 60→89%, day 90→92%, day 180→95%, plateau 97%
    base = 85.0
    asymptote = 97.0
    k = 0.018
    sr = base + (asymptote - base) * (1 - math.exp(-k * day))
    return round(min(sr, asymptote), 2)


def _next_finetune_trigger() -> str:
    gap = FINETUNE_THRESHOLD - (_ring.size % FINETUNE_THRESHOLD)
    return f"{gap} more corrections"


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run-127 Continual Planner</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }}
    .subtitle {{ color: #38bdf8; font-size: 0.9rem; margin-bottom: 2rem; }}
    .cards {{ display: flex; gap: 1.2rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; flex: 1; min-width: 180px; }}
    .card h3 {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
    .card .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .card .sub {{ font-size: 0.75rem; color: #64748b; margin-top: 0.3rem; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
    .section h2 {{ color: #C74634; font-size: 1rem; margin-bottom: 1rem; }}
    svg text {{ font-family: 'Segoe UI', sans-serif; }}
    .bar-label {{ fill: #94a3b8; font-size: 11px; }}
    .bar-val {{ fill: #e2e8f0; font-size: 11px; font-weight: 600; }}
    .ring-track {{ background: #0f172a; border-radius: 8px; height: 14px; width: 100%; overflow: hidden; }}
    .ring-fill {{ height: 14px; border-radius: 8px; background: linear-gradient(90deg, #C74634, #38bdf8); transition: width 0.4s; }}
    .endpoints {{ display: flex; gap: 0.6rem; flex-wrap: wrap; }}
    .ep {{ background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 0.4rem 0.8rem; font-size: 0.78rem; color: #38bdf8; }}
    .ep span {{ color: #C74634; font-weight: 600; }}
    footer {{ color: #475569; font-size: 0.72rem; margin-top: 2rem; }}
  </style>
</head>
<body>
  <h1>DAgger Run-127 Continual Planner</h1>
  <p class="subtitle">OCI Robot Cloud · Cycle-497B · Port 10046 · Continual correction loop with 5000-slot ring buffer</p>

  <div class="cards">
    <div class="card"><h3>Current SR</h3><div class="val" id="cur_sr">85.0%</div><div class="sub">live estimate</div></div>
    <div class="card"><h3>Buffer Used</h3><div class="val" id="buf_sz">0</div><div class="sub">/ 5000 slots</div></div>
    <div class="card"><h3>Daily Improvement</h3><div class="val">0.3%</div><div class="sub">per day</div></div>
    <div class="card"><h3>Plateau SR</h3><div class="val">97.0%</div><div class="sub">asymptote</div></div>
  </div>

  <div class="section">
    <h2>SR Trajectory (Month 1 → Month 6)</h2>
    <svg width="100%" viewBox="0 0 560 200" preserveAspectRatio="xMidYMid meet">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="165" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="165" x2="545" y2="165" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="50" y="168" text-anchor="end" class="bar-label">80%</text>
      <text x="50" y="128" text-anchor="end" class="bar-label">85%</text>
      <text x="50" y="88"  text-anchor="end" class="bar-label">90%</text>
      <text x="50" y="48"  text-anchor="end" class="bar-label">95%</text>
      <text x="50" y="18"  text-anchor="end" class="bar-label">100%</text>
      <!-- gridlines -->
      <line x1="60" y1="128" x2="545" y2="128" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="88"  x2="545" y2="88"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="48"  x2="545" y2="48"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <!-- data points: month1=85(y128) month2=89(y96.8) month3=92(y73.6) month6=95(y48) -->
      <!-- bar width=80, gap=15, start x=75 -->
      <rect x="75"  y="128" width="80" height="37"  fill="#C74634" rx="4"/>
      <rect x="170" y="96"  width="80" height="69"  fill="#C74634" rx="4" opacity="0.85"/>
      <rect x="265" y="73"  width="80" height="92"  fill="#38bdf8" rx="4" opacity="0.9"/>
      <rect x="360" y="48"  width="80" height="117" fill="#38bdf8" rx="4"/>
      <!-- x labels -->
      <text x="115"  y="182" text-anchor="middle" class="bar-label">Month 1</text>
      <text x="210"  y="182" text-anchor="middle" class="bar-label">Month 2</text>
      <text x="305"  y="182" text-anchor="middle" class="bar-label">Month 3</text>
      <text x="400"  y="182" text-anchor="middle" class="bar-label">Month 6</text>
      <!-- value labels -->
      <text x="115"  y="124" text-anchor="middle" class="bar-val">85%</text>
      <text x="210"  y="92"  text-anchor="middle" class="bar-val">89%</text>
      <text x="305"  y="69"  text-anchor="middle" class="bar-val">92%</text>
      <text x="400"  y="44"  text-anchor="middle" class="bar-val">95%</text>
    </svg>
  </div>

  <div class="section">
    <h2>Ring Buffer Utilization</h2>
    <div style="margin-bottom:0.6rem;color:#94a3b8;font-size:0.82rem;">Slots used: <span id="rbuf">0</span> / 5000 &nbsp;·&nbsp; Fill: <span id="rfill">0.0</span>%</div>
    <div class="ring-track"><div class="ring-fill" id="rfill-bar" style="width:0%"></div></div>
    <div style="margin-top:0.6rem;color:#64748b;font-size:0.78rem;">FIFO eviction engaged when buffer is full. Fine-tune trigger every 500 new corrections.</div>
  </div>

  <div class="section">
    <h2>API Endpoints</h2>
    <div class="endpoints">
      <div class="ep"><span>GET</span> /health</div>
      <div class="ep"><span>GET</span> /dagger/run127/status</div>
      <div class="ep"><span>POST</span> /dagger/run127/continual_step</div>
    </div>
  </div>

  <footer>OCI Robot Cloud · DAgger Run-127 · Cycle-497B · Never-ending correction loop</footer>

  <script>
    async function refresh() {{
      try {{
        const r = await fetch('/dagger/run127/status');
        const d = await r.json();
        document.getElementById('cur_sr').textContent = d.current_sr + '%';
      }} catch(e) {{}}
      try {{
        const r2 = await fetch('/health');
        const d2 = await r2.json();
        const sz = d2.buffer_size || 0;
        const fill = (sz / 5000 * 100).toFixed(1);
        document.getElementById('buf_sz').textContent = sz;
        document.getElementById('rbuf').textContent = sz;
        document.getElementById('rfill').textContent = fill;
        document.getElementById('rfill-bar').style.width = fill + '%';
      }} catch(e) {{}}
    }}
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="DAgger Run-127 Continual Planner",
        description="Continual DAgger correction loop with ring buffer (5000 slots, FIFO eviction)",
        version="1.0.0",
    )

    class ContinualStepRequest(BaseModel):
        day: int
        new_corrections: int

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Dark-background HTML dashboard."""
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        """JSON health check."""
        return JSONResponse({
            "status": "ok",
            "service": "dagger_run127_planner",
            "port": 10046,
            "buffer_size": _ring.size,
            "buffer_capacity": BUFFER_CAPACITY,
            "buffer_fill_pct": _ring.fill_pct,
            "total_added": _ring.total_added,
            "total_evicted": _ring.total_evicted,
            "uptime_s": round(time.time() - _state["started_at"], 1),
        })

    @app.post("/dagger/run127/continual_step")
    async def continual_step(req: ContinualStepRequest):
        """Accept a daily correction batch and advance the planner state."""
        if req.day < 0:
            raise HTTPException(status_code=400, detail="day must be >= 0")
        if req.new_corrections < 0:
            raise HTTPException(status_code=400, detail="new_corrections must be >= 0")

        # Push corrections into ring buffer
        for i in range(req.new_corrections):
            _ring.push({"day": req.day, "idx": i, "ts": time.time()})

        _state["day"] = req.day
        _state["current_sr"] = _compute_sr(req.day)

        return JSONResponse({
            "buffer_size": _ring.size,
            "current_sr": _state["current_sr"],
            "daily_improvement": DAILY_IMPROVEMENT,
            "next_finetune_trigger": _next_finetune_trigger(),
        })

    @app.get("/dagger/run127/status")
    async def status():
        """Return run-127 status and SR trajectory milestones."""
        return JSONResponse({
            "run_id": _state["run_id"],
            "mode": _state["mode"],
            "month1_sr": _state["month1_sr"],
            "month2_sr": _state["month2_sr"],
            "month3_sr": _state["month3_sr"],
            "month6_sr": _state["month6_sr"],
            "plateau_sr": _state["plateau_sr"],
            "current_sr": _state["current_sr"],
            "day": _state["day"],
            "buffer_size": _ring.size,
            "next_finetune_trigger": _next_finetune_trigger(),
        })

# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------
else:  # pragma: no cover
    import json as _json

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code: int, content_type: str, body: str | bytes) -> None:
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, "text/html", _DASHBOARD_HTML)
            elif path == "/health":
                body = _json.dumps({"status": "ok", "service": "dagger_run127_planner", "port": 10046})
                self._send(200, "application/json", body)
            elif path == "/dagger/run127/status":
                body = _json.dumps(_state)
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", '{"detail":"not found"}')

        def do_POST(self):
            path = self.path.split("?")[0]
            if path == "/dagger/run127/continual_step":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    req = _json.loads(raw)
                except Exception:
                    self._send(400, "application/json", '{"detail":"invalid JSON"}')
                    return
                day = req.get("day", 0)
                nc = req.get("new_corrections", 0)
                for i in range(nc):
                    _ring.push({"day": day, "idx": i})
                _state["day"] = day
                _state["current_sr"] = _compute_sr(day)
                body = _json.dumps({
                    "buffer_size": _ring.size,
                    "current_sr": _state["current_sr"],
                    "daily_improvement": DAILY_IMPROVEMENT,
                    "next_finetune_trigger": _next_finetune_trigger(),
                })
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", '{"detail":"not found"}')


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10046)
    else:  # pragma: no cover
        server = HTTPServer(("0.0.0.0", 10046), _Handler)
        print("Serving on http://0.0.0.0:10046 (stdlib fallback)")
        server.serve_forever()
