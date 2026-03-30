"""
OCI Robot Cloud — Inference Gateway
====================================
Unified load-balancing gateway for all GR00T model endpoints.
Routes design-partner /predict requests to the least-loaded backend,
handles failover, circuit breaking, rate limiting, and metrics.

Architecture:
  Client → POST /predict → gateway → GR00T server :8001 or :8002
                        ↘ round-robin / least-connections / latency-weighted
  GET  /metrics  → per-backend stats (latency, success rate, load)
  GET  /health   → overall gateway health
  GET  /         → HTML dashboard (dark theme, live-updating)
  POST /config   → update routing strategy or backend list

Usage (local mock mode — backends simulated, no real GR00T needed):
  MOCK=1 uvicorn src.api.inference_gateway:app --port 8034

Usage (production, forwarding to real GR00T servers):
  uvicorn src.api.inference_gateway:app --host 0.0.0.0 --port 8034

Environment variables:
  BACKENDS      comma-separated URLs  (default: http://138.1.153.110:8001,http://138.1.153.110:8002)
  STRATEGY      round-robin | least-connections | latency-weighted  (default: least-connections)
  MOCK          1 to simulate backends  (default: 0)
  RATE_LIMIT    requests/minute per API key  (default: 100)
  DB_PATH       SQLite path  (default: /tmp/gateway.db)

SQLite schema:
  requests(id, ts, backend, latency_ms, success, api_key_hash)
"""

import asyncio
import hashlib
import json
import os
import random
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URLS: List[str] = [
    u.strip()
    for u in os.environ.get(
        "BACKENDS",
        "http://138.1.153.110:8001,http://138.1.153.110:8002",
    ).split(",")
    if u.strip()
]
STRATEGY: str = os.environ.get("STRATEGY", "least-connections")
MOCK_MODE: bool = os.environ.get("MOCK", "0") == "1"
RATE_LIMIT: int = int(os.environ.get("RATE_LIMIT", "100"))
DB_PATH: str = os.environ.get("DB_PATH", "/tmp/gateway.db")

HEALTH_INTERVAL_S: float = 30.0
CIRCUIT_OPEN_THRESHOLD: int = 5      # consecutive errors before opening
CIRCUIT_HALF_OPEN_AFTER_S: float = 60.0
HEALTH_FAIL_OFFLINE_COUNT: int = 3   # consecutive health-check failures → offline
LATENCY_WINDOW: int = 20             # rolling window size per backend

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class BackendState:
    def __init__(self, url: str):
        self.url = url
        self.current_load: int = 0          # in-flight requests
        self.health: str = "healthy"        # healthy | degraded | offline
        self.last_latency_ms: float = 0.0
        self.latency_history: deque = deque(maxlen=LATENCY_WINDOW)
        self.total_requests: int = 0
        self.total_success: int = 0
        self.consecutive_errors: int = 0
        self.circuit_state: str = "closed"  # closed | open | half-open
        self.circuit_opened_at: float = 0.0
        self.health_fail_streak: int = 0
        self._rr_index: int = 0             # unused — global index used

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.total_success / self.total_requests

    def circuit_is_open(self) -> bool:
        if self.circuit_state == "closed":
            return False
        if self.circuit_state == "open":
            if time.time() - self.circuit_opened_at >= CIRCUIT_HALF_OPEN_AFTER_S:
                self.circuit_state = "half-open"
                return False
            return True
        # half-open: allow one probe
        return False

    def record_success(self, latency_ms: float):
        self.consecutive_errors = 0
        self.last_latency_ms = latency_ms
        self.latency_history.append(latency_ms)
        self.total_requests += 1
        self.total_success += 1
        if self.circuit_state == "half-open":
            self.circuit_state = "closed"
        if self.health == "degraded":
            self.health = "healthy"

    def record_error(self):
        self.consecutive_errors += 1
        self.total_requests += 1
        if self.consecutive_errors >= CIRCUIT_OPEN_THRESHOLD:
            self.circuit_state = "open"
            self.circuit_opened_at = time.time()
            self.health = "degraded"


# Global backend pool
backends: List[BackendState] = []
_rr_counter: int = 0

# Rate-limiting: api_key_hash → deque of timestamps (sliding window)
rate_buckets: Dict[str, deque] = defaultdict(lambda: deque())


# ---------------------------------------------------------------------------
# SQLite setup
# ---------------------------------------------------------------------------

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS requests (
            id          TEXT PRIMARY KEY,
            ts          REAL,
            backend     TEXT,
            latency_ms  REAL,
            success     INTEGER,
            api_key_hash TEXT
        )"""
    )
    con.commit()
    con.close()


def log_request(req_id: str, backend_url: str, latency_ms: float, success: bool, api_key_hash: str):
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO requests VALUES (?,?,?,?,?,?)",
            (req_id, time.time(), backend_url, latency_ms, int(success), api_key_hash),
        )
        con.commit()
        con.close()
    except Exception:
        pass  # non-fatal


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def select_backend(strategy: str) -> Optional[BackendState]:
    global _rr_counter
    available = [
        b for b in backends
        if b.health != "offline" and not b.circuit_is_open()
    ]
    if not available:
        return None

    if strategy == "round-robin":
        b = available[_rr_counter % len(available)]
        _rr_counter += 1
        return b

    if strategy == "least-connections":
        return min(available, key=lambda b: b.current_load)

    if strategy == "latency-weighted":
        # Lower avg latency → higher weight
        scores = []
        for b in available:
            lat = b.avg_latency_ms if b.avg_latency_ms > 0 else 1.0
            scores.append(1.0 / lat)
        total = sum(scores)
        r = random.random() * total
        cumulative = 0.0
        for b, s in zip(available, scores):
            cumulative += s
            if r <= cumulative:
                return b
        return available[-1]

    # fallback
    return available[0]


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit(api_key_hash: str) -> bool:
    """Return True if request is allowed, False if over limit."""
    now = time.time()
    window_start = now - 60.0
    bucket = rate_buckets[api_key_hash]
    # Evict old entries
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    return True


# ---------------------------------------------------------------------------
# Health check loop
# ---------------------------------------------------------------------------

async def health_check_loop():
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            await asyncio.sleep(HEALTH_INTERVAL_S)
            for b in backends:
                if MOCK_MODE:
                    # Simulated: always healthy
                    b.health_fail_streak = 0
                    if b.health == "offline":
                        b.health = "healthy"
                    continue
                try:
                    url = b.url.rstrip("/") + "/health"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        b.health_fail_streak = 0
                        if b.health == "offline":
                            b.health = "healthy"
                    else:
                        b.health_fail_streak += 1
                except Exception:
                    b.health_fail_streak += 1

                if b.health_fail_streak >= HEALTH_FAIL_OFFLINE_COUNT:
                    b.health = "offline"


# ---------------------------------------------------------------------------
# Mock prediction
# ---------------------------------------------------------------------------

async def mock_predict(obs: Dict[str, Any]) -> Dict[str, Any]:
    latency = random.uniform(180, 280)
    await asyncio.sleep(latency / 1000.0)
    if random.random() < 0.05:
        raise RuntimeError("mock error: backend simulated failure")
    return {
        "actions": [[round(random.gauss(0, 0.1), 4) for _ in range(7)]],
        "mock": True,
    }


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init
    init_db()
    for url in BACKEND_URLS:
        backends.append(BackendState(url))
    app.state.strategy = STRATEGY
    task = asyncio.create_task(health_check_loop())
    yield
    task.cancel()


app = FastAPI(
    title="OCI Robot Cloud — Inference Gateway",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Observation(BaseModel):
    joint_states: List[float]
    image: Optional[str] = None          # base64-encoded PNG/JPEG
    extra: Optional[Dict[str, Any]] = None


class PredictResponse(BaseModel):
    actions: List[List[float]]
    backend_used: str
    latency_ms: float
    cache_hit: bool
    request_id: str


class ConfigUpdate(BaseModel):
    strategy: Optional[str] = None       # round-robin | least-connections | latency-weighted
    backends: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/predict", response_model=PredictResponse)
async def predict(
    obs: Observation,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
):
    # Rate limiting
    raw_key = x_api_key or request.client.host or "anonymous"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
    if not check_rate_limit(key_hash):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (100 req/min)")

    backend = select_backend(app.state.strategy)
    if backend is None:
        raise HTTPException(status_code=503, detail="No healthy backends available")

    req_id = str(uuid.uuid4())[:8]
    backend.current_load += 1
    t0 = time.perf_counter()
    success = False
    result: Dict[str, Any] = {}

    try:
        if MOCK_MODE:
            result = await mock_predict(obs.model_dump())
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    backend.url.rstrip("/") + "/predict",
                    json=obs.model_dump(),
                    headers={"x-api-key": raw_key} if x_api_key else {},
                )
                resp.raise_for_status()
                result = resp.json()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        backend.record_success(latency_ms)
        success = True
        asyncio.create_task(
            asyncio.to_thread(log_request, req_id, backend.url, latency_ms, True, key_hash)
        )
        return PredictResponse(
            actions=result.get("actions", [[]]),
            backend_used=backend.url,
            latency_ms=round(latency_ms, 2),
            cache_hit=result.get("cache_hit", False),
            request_id=req_id,
        )

    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        backend.record_error()
        asyncio.create_task(
            asyncio.to_thread(log_request, req_id, backend.url, latency_ms, False, key_hash)
        )
        raise HTTPException(status_code=502, detail=f"Backend error: {exc}") from exc

    finally:
        backend.current_load = max(0, backend.current_load - 1)


@app.get("/health")
async def health():
    healthy_count = sum(1 for b in backends if b.health != "offline")
    status = "healthy" if healthy_count >= 1 else "unhealthy"
    return {
        "status": status,
        "backends_total": len(backends),
        "backends_healthy": healthy_count,
        "strategy": app.state.strategy,
        "mock_mode": MOCK_MODE,
    }


@app.get("/metrics")
async def metrics():
    data = []
    for b in backends:
        data.append({
            "url": b.url,
            "health": b.health,
            "circuit_state": b.circuit_state,
            "current_load": b.current_load,
            "total_requests": b.total_requests,
            "success_rate": round(b.success_rate, 4),
            "avg_latency_ms": round(b.avg_latency_ms, 2),
            "last_latency_ms": round(b.last_latency_ms, 2),
            "latency_history": list(b.latency_history),
        })
    total_req = sum(b.total_requests for b in backends)
    total_ok = sum(b.total_success for b in backends)
    return {
        "backends": data,
        "gateway": {
            "total_requests": total_req,
            "total_success": total_ok,
            "overall_success_rate": round(total_ok / total_req, 4) if total_req else 1.0,
            "strategy": app.state.strategy,
        },
    }


@app.post("/config")
async def update_config(cfg: ConfigUpdate):
    if cfg.strategy is not None:
        allowed = {"round-robin", "least-connections", "latency-weighted"}
        if cfg.strategy not in allowed:
            raise HTTPException(status_code=400, detail=f"strategy must be one of {allowed}")
        app.state.strategy = cfg.strategy

    if cfg.backends is not None:
        existing_urls = {b.url for b in backends}
        for url in cfg.backends:
            if url not in existing_urls:
                backends.append(BackendState(url))
        # Mark removed backends offline
        new_set = set(cfg.backends)
        for b in backends:
            if b.url not in new_set:
                b.health = "offline"

    return {"ok": True, "strategy": app.state.strategy, "backends": [b.url for b in backends]}


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Inference Gateway</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #64748b;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --blue: #3b82f6;
    --accent: #6366f1;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; font-size: 14px; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; }
  header .sub { color: var(--muted); font-size: 12px; }
  .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
  .badge.healthy  { background: #14532d; color: var(--green); }
  .badge.degraded { background: #713f12; color: var(--yellow); }
  .badge.offline  { background: #450a0a; color: var(--red); }
  .badge.open     { background: #450a0a; color: var(--red); }
  .badge.half-open{ background: #713f12; color: var(--yellow); }
  .badge.closed   { background: #14532d; color: var(--green); }
  main { padding: 24px; max-width: 1200px; margin: 0 auto; }
  .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .stat-card .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
  .stat-card .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
  .backends-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
  .backend-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
  .backend-card .url { font-size: 12px; color: var(--muted); font-family: monospace; word-break: break-all; margin-bottom: 12px; }
  .backend-card .row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .backend-card .row .key { color: var(--muted); font-size: 12px; }
  .load-bar-wrap { background: var(--border); border-radius: 4px; height: 6px; margin: 10px 0; overflow: hidden; }
  .load-bar { height: 100%; background: var(--accent); border-radius: 4px; transition: width .4s; }
  .sparkline-wrap { margin-top: 12px; }
  .sparkline-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
  canvas.sparkline { width: 100%; height: 40px; display: block; }
  section h2 { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
  .section { margin-bottom: 28px; }
  .strategy-bar { display: flex; gap: 8px; margin-bottom: 24px; align-items: center; }
  .strategy-btn { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; transition: background .2s; }
  .strategy-btn.active { background: var(--accent); border-color: var(--accent); }
  .strategy-btn:hover:not(.active) { background: var(--border); }
  .throughput { color: var(--accent); }
  .ts { color: var(--muted); font-size: 11px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>OCI Robot Cloud &mdash; Inference Gateway</h1>
    <div class="sub">Port 8034 &bull; <span id="mode-badge"></span> &bull; Updated <span id="last-updated">—</span></div>
  </div>
</header>
<main>
  <div class="stats-row">
    <div class="stat-card">
      <div class="label">Total Requests</div>
      <div class="value throughput" id="total-req">—</div>
    </div>
    <div class="stat-card">
      <div class="label">Success Rate</div>
      <div class="value" id="success-rate">—</div>
    </div>
    <div class="stat-card">
      <div class="label">Backends Up</div>
      <div class="value" id="backends-up">—</div>
    </div>
    <div class="stat-card">
      <div class="label">Strategy</div>
      <div class="value" id="strategy-val" style="font-size:16px;margin-top:8px;">—</div>
    </div>
  </div>

  <div class="strategy-bar">
    <span style="color:var(--muted);font-size:12px;margin-right:4px;">Routing:</span>
    <button class="strategy-btn" onclick="setStrategy('round-robin')">Round Robin</button>
    <button class="strategy-btn" onclick="setStrategy('least-connections')">Least Connections</button>
    <button class="strategy-btn" onclick="setStrategy('latency-weighted')">Latency Weighted</button>
  </div>

  <div class="section">
    <h2>Backends</h2>
    <div class="backends-grid" id="backends-grid"></div>
  </div>
</main>

<script>
let metricsCache = null;

function cls(val) {
  const v = String(val).toLowerCase();
  return v;
}

function renderSparkline(canvas, data) {
  const ctx = canvas.getContext('2d');
  const w = canvas.offsetWidth || 300;
  const h = 40;
  canvas.width = w;
  canvas.height = h;
  ctx.clearRect(0, 0, w, h);
  if (!data || data.length < 2) return;
  const min = Math.min(...data);
  const max = Math.max(...data) || 1;
  const pad = 4;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - 2*pad);
    const y = h - pad - ((v - min) / (max - min + 1)) * (h - 2*pad);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = '#6366f1';
  ctx.lineWidth = 1.5;
  ctx.stroke();
  // Fill area
  ctx.lineTo(pad + (data.length-1)/(data.length-1)*(w-2*pad), h-pad);
  ctx.lineTo(pad, h-pad);
  ctx.closePath();
  ctx.fillStyle = 'rgba(99,102,241,0.12)';
  ctx.fill();
}

function renderBackends(backends) {
  const grid = document.getElementById('backends-grid');
  grid.innerHTML = '';
  backends.forEach(b => {
    const loadPct = Math.min(100, b.current_load * 20); // scale: 5 in-flight = 100%
    const srPct = (b.success_rate * 100).toFixed(1);
    const id = btoa(b.url).replace(/[^a-z0-9]/gi,'').slice(0,8);
    const card = document.createElement('div');
    card.className = 'backend-card';
    card.innerHTML = `
      <div class="url">${b.url}</div>
      <div class="row">
        <span class="key">Health</span>
        <span class="badge ${cls(b.health)}">${b.health}</span>
      </div>
      <div class="row">
        <span class="key">Circuit</span>
        <span class="badge ${cls(b.circuit_state)}">${b.circuit_state}</span>
      </div>
      <div class="row"><span class="key">In-flight</span><span>${b.current_load}</span></div>
      <div class="load-bar-wrap"><div class="load-bar" style="width:${loadPct}%"></div></div>
      <div class="row"><span class="key">Avg latency</span><span>${b.avg_latency_ms} ms</span></div>
      <div class="row"><span class="key">Last latency</span><span>${b.last_latency_ms} ms</span></div>
      <div class="row"><span class="key">Success rate</span><span>${srPct}%</span></div>
      <div class="row"><span class="key">Total requests</span><span>${b.total_requests}</span></div>
      <div class="sparkline-wrap">
        <div class="sparkline-label">Latency (last ${b.latency_history.length} requests)</div>
        <canvas class="sparkline" id="spark-${id}"></canvas>
      </div>`;
    grid.appendChild(card);
    // Render sparkline after DOM attach
    setTimeout(() => {
      const c = document.getElementById('spark-' + id);
      if (c) renderSparkline(c, b.latency_history);
    }, 0);
  });
}

async function fetchMetrics() {
  try {
    const r = await fetch('/metrics');
    const data = await r.json();
    metricsCache = data;
    const g = data.gateway;
    document.getElementById('total-req').textContent = g.total_requests.toLocaleString();
    document.getElementById('success-rate').textContent = (g.overall_success_rate*100).toFixed(1) + '%';
    const up = data.backends.filter(b => b.health !== 'offline').length;
    document.getElementById('backends-up').textContent = up + ' / ' + data.backends.length;
    document.getElementById('strategy-val').textContent = g.strategy;
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

    // Highlight active strategy button
    document.querySelectorAll('.strategy-btn').forEach(btn => {
      btn.classList.toggle('active', btn.textContent.toLowerCase().replace(' ','-') === g.strategy ||
        btn.textContent.toLowerCase().replace(/\s+/g,'-') === g.strategy);
    });

    renderBackends(data.backends);
  } catch(e) { console.error(e); }
}

async function fetchHealth() {
  try {
    const r = await fetch('/health');
    const d = await r.json();
    document.getElementById('mode-badge').textContent = d.mock_mode ? 'MOCK MODE' : 'LIVE';
  } catch(e) {}
}

async function setStrategy(s) {
  await fetch('/config', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({strategy: s})
  });
  fetchMetrics();
}

fetchHealth();
fetchMetrics();
setInterval(fetchMetrics, 3000);
setInterval(fetchHealth, 15000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# Entry point hint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.inference_gateway:app", host="0.0.0.0", port=8034, reload=False)
