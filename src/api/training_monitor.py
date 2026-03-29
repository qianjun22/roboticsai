"""
Real-time training monitor for OCI Robot Cloud.

FastAPI server that streams live training metrics to a browser dashboard.
Design partners can watch their fine-tuning runs in real-time without SSH.

Features:
  - Server-Sent Events (SSE) for live loss/MAE streaming
  - HTML dashboard at /dashboard (auto-refreshes every 2s)
  - REST endpoints for job status, metrics history, ETA
  - Integrates with run_full_pipeline.sh log files
  - Mock mode for testing without a running training job

Usage:
    # Start monitor (watches a training log file)
    python3 training_monitor.py --log /tmp/finetune_500_5k.log --port 8004

    # Open dashboard in browser
    open http://localhost:8004/dashboard

    # Stream metrics as JSON
    curl -N http://localhost:8004/stream

Endpoints:
    GET /dashboard          — HTML live dashboard
    GET /stream             — SSE stream of metrics (text/event-stream)
    GET /status             — Current job status JSON
    GET /metrics            — Full metrics history JSON
    GET /health             — Health check
"""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    import uvicorn
except ImportError:
    print("[Monitor] Install dependencies: pip install fastapi uvicorn")
    raise

app = FastAPI(title="OCI Robot Cloud Training Monitor", version="1.0.0")

# Global state
_log_path: Optional[Path] = None
_metrics_history: list = []
_job_start_time: Optional[float] = None
_mock_mode: bool = False


# ── Log parser ────────────────────────────────────────────────────────────────

def parse_log_line(line: str) -> Optional[dict]:
    """
    Parse a training log line into a metrics dict.

    Handles formats from GR00T fine-tuning and generic torch training:
      Step 500/2000: loss=0.412 | 2.35 it/s | GPU: 87% | VRAM: 36.8GB
      {'loss': 0.412, 'grad_norm': 1.23, 'learning_rate': 1e-4, 'step': 500}
    """
    line = line.strip()
    if not line:
        return None

    # Format 1: "Step N/M: loss=X | Y it/s | GPU: Z% | VRAM: Wgb"
    m = re.match(
        r"Step\s+(\d+)/(\d+):\s*loss=([\d.]+)"
        r"(?:\s*\|\s*([\d.]+)\s*it/s)?"
        r"(?:\s*\|\s*GPU:\s*([\d.]+)%)?"
        r"(?:\s*\|\s*VRAM:\s*([\d.]+)GB)?",
        line, re.IGNORECASE
    )
    if m:
        step, total, loss = int(m.group(1)), int(m.group(2)), float(m.group(3))
        d = {"step": step, "total_steps": total, "loss": loss, "ts": time.time()}
        if m.group(4): d["throughput"] = float(m.group(4))
        if m.group(5): d["gpu_util"] = float(m.group(5))
        if m.group(6): d["vram_gb"] = float(m.group(6))
        return d

    # Format 2: JSON-like dict from HuggingFace Trainer
    if line.startswith("{") and "loss" in line:
        try:
            d = json.loads(line.replace("'", '"'))
            d["ts"] = time.time()
            if "step" not in d and "epoch" in d:
                d["step"] = int(d.get("epoch", 0) * 100)
            return d
        except (json.JSONDecodeError, ValueError):
            pass

    # Format 3: "loss=X step=N"
    m2 = re.search(r"loss[=:\s]+([\d.]+).*?step[=:\s]+(\d+)", line, re.IGNORECASE)
    if m2:
        return {"loss": float(m2.group(1)), "step": int(m2.group(2)), "ts": time.time()}

    return None


def compute_eta(metrics: list) -> Optional[float]:
    """Estimate seconds remaining based on recent throughput."""
    if len(metrics) < 2:
        return None
    last = metrics[-1]
    total = last.get("total_steps")
    step = last.get("step")
    if not total or not step:
        return None
    remaining = total - step
    if "throughput" in last and last["throughput"] > 0:
        return remaining / last["throughput"]
    # Estimate from wall time
    if _job_start_time and step > 0:
        elapsed = time.time() - _job_start_time
        rate = step / elapsed  # steps/sec
        if rate > 0:
            return remaining / rate
    return None


# ── Mock metric generator (for testing) ───────────────────────────────────────

async def mock_metric_stream():
    """Generate realistic synthetic training metrics for testing."""
    total = 2000
    for step in range(1, total + 1, 50):
        loss = 0.68 * (0.92 ** (step / 100))  # exponential decay
        yield {
            "step": step,
            "total_steps": total,
            "loss": round(loss, 4),
            "throughput": 2.35 + 0.1 * (0.5 - abs(0.5 - step / total)),
            "gpu_util": 85 + 5 * (step / total),
            "vram_gb": 36.8,
            "ts": time.time(),
        }
        await asyncio.sleep(0.5)


# ── Log tail reader ────────────────────────────────────────────────────────────

async def tail_log_file(log_path: Path) -> AsyncGenerator[dict, None]:
    """Tail a log file and yield parsed metric dicts."""
    # First pass: read existing lines
    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                m = parse_log_line(line)
                if m:
                    yield m

    # Second pass: follow new lines
    with open(log_path) as f:
        f.seek(0, 2)  # seek to end
        while True:
            line = f.readline()
            if line:
                m = parse_log_line(line)
                if m:
                    yield m
            else:
                await asyncio.sleep(1.0)


# ── SSE stream endpoint ───────────────────────────────────────────────────────

@app.get("/stream")
async def stream_metrics():
    """Server-Sent Events stream of live training metrics."""
    async def event_generator():
        global _metrics_history, _job_start_time

        if _job_start_time is None:
            _job_start_time = time.time()

        if _mock_mode:
            source = mock_metric_stream()
        else:
            source = tail_log_file(_log_path)

        async for metric in source:
            _metrics_history.append(metric)

            eta = compute_eta(_metrics_history)
            metric["eta_sec"] = round(eta) if eta else None

            progress = 0
            if metric.get("total_steps") and metric.get("step"):
                progress = metric["step"] / metric["total_steps"]
            metric["progress"] = round(progress, 4)

            data = json.dumps(metric)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    """Current job status summary."""
    if not _metrics_history:
        return JSONResponse({"status": "waiting", "message": "No metrics yet"})

    last = _metrics_history[-1]
    total = last.get("total_steps", 0)
    step = last.get("step", 0)
    progress = step / total if total else 0
    eta = compute_eta(_metrics_history)

    status = "running"
    if total and step >= total:
        status = "complete"

    return JSONResponse({
        "status": status,
        "step": step,
        "total_steps": total,
        "progress": round(progress, 4),
        "loss": last.get("loss"),
        "throughput_its": last.get("throughput"),
        "gpu_util_pct": last.get("gpu_util"),
        "vram_gb": last.get("vram_gb"),
        "eta_sec": round(eta) if eta else None,
        "elapsed_sec": round(time.time() - _job_start_time) if _job_start_time else None,
    })


@app.get("/metrics")
def get_metrics():
    """Full metrics history."""
    return JSONResponse(_metrics_history)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


# ── HTML dashboard ────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Robot Cloud — Training Monitor</title>
<style>
  :root {
    --bg: #0d0d0d; --card: #1a1a1a; --border: #2a2a2a;
    --red: #c74634; --green: #22c55e; --amber: #f59e0b;
    --blue: #3b82f6; --gray: #6b7280; --text: #e5e7eb;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; }
  header {
    background: #111; border-bottom: 2px solid var(--red);
    padding: 12px 24px; display: flex; align-items: center; gap: 16px;
  }
  header h1 { font-size: 20px; color: var(--red); letter-spacing: 1px; }
  header span { color: var(--gray); font-size: 13px; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .dot-running { background: var(--green); animation: pulse 1.5s infinite; }
  .dot-waiting { background: var(--amber); }
  .dot-complete { background: var(--blue); }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 20px 24px; }
  .metric-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px; text-align: center;
  }
  .metric-card .label { color: var(--gray); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .metric-card .value { font-size: 32px; font-weight: bold; margin-top: 8px; color: var(--text); }
  .metric-card .unit { font-size: 12px; color: var(--gray); margin-top: 4px; }
  .progress-section { padding: 0 24px 20px; }
  .progress-bar-bg { background: var(--card); border: 1px solid var(--border); border-radius: 8px; height: 24px; overflow: hidden; }
  .progress-bar-fill { background: linear-gradient(90deg, var(--red), #e05d4a); height: 100%; transition: width 0.5s ease; border-radius: 8px; }
  .progress-label { display: flex; justify-content: space-between; font-size: 12px; color: var(--gray); margin-top: 6px; }
  .log-section { padding: 0 24px 20px; }
  .log-section h2 { font-size: 13px; color: var(--gray); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .log-box {
    background: #111; border: 1px solid var(--border); border-radius: 6px;
    height: 200px; overflow-y: auto; padding: 12px;
    font-size: 12px; line-height: 1.6; color: #9ca3af;
  }
  .log-entry { border-left: 2px solid var(--border); padding-left: 8px; margin-bottom: 4px; }
  .log-entry.success { border-color: var(--green); }
  .log-entry.warn { border-color: var(--amber); }
  .footer { text-align: center; color: var(--gray); font-size: 11px; padding: 12px; border-top: 1px solid var(--border); }
</style>
</head>
<body>
<header>
  <span class="status-dot dot-waiting" id="status-dot"></span>
  <h1>OCI ROBOT CLOUD — TRAINING MONITOR</h1>
  <span id="status-text">Connecting...</span>
</header>

<div class="grid">
  <div class="metric-card">
    <div class="label">Loss</div>
    <div class="value" id="val-loss">—</div>
    <div class="unit">current</div>
  </div>
  <div class="metric-card">
    <div class="label">Throughput</div>
    <div class="value" id="val-throughput">—</div>
    <div class="unit">it/s</div>
  </div>
  <div class="metric-card">
    <div class="label">GPU Util</div>
    <div class="value" id="val-gpu">—</div>
    <div class="unit">%</div>
  </div>
  <div class="metric-card">
    <div class="label">ETA</div>
    <div class="value" id="val-eta">—</div>
    <div class="unit">remaining</div>
  </div>
</div>

<div class="progress-section">
  <div class="progress-bar-bg">
    <div class="progress-bar-fill" id="progress-fill" style="width:0%"></div>
  </div>
  <div class="progress-label">
    <span id="progress-steps">Step 0 / —</span>
    <span id="progress-pct">0%</span>
  </div>
</div>

<div class="log-section">
  <h2>Live Metrics Log</h2>
  <div class="log-box" id="log-box"></div>
</div>

<div class="footer">OCI Robot Cloud · Oracle Cloud Infrastructure × NVIDIA · <span id="time"></span></div>

<script>
function fmtEta(sec) {
  if (!sec) return '—';
  if (sec < 60) return sec + 's';
  if (sec < 3600) return Math.round(sec/60) + 'm';
  return Math.round(sec/3600*10)/10 + 'h';
}
function fmtLoss(v) { return v !== null && v !== undefined ? v.toFixed(4) : '—'; }
function fmtNum(v, dec=1) { return v !== null && v !== undefined ? v.toFixed(dec) : '—'; }

const dot = document.getElementById('status-dot');
const statusTxt = document.getElementById('status-text');
const logBox = document.getElementById('log-box');

const es = new EventSource('/stream');
es.onopen = () => {
  dot.className = 'status-dot dot-running';
  statusTxt.textContent = 'Connected — streaming live metrics';
};
es.onerror = () => {
  dot.className = 'status-dot dot-waiting';
  statusTxt.textContent = 'Disconnected — retrying...';
};
es.onmessage = (e) => {
  const m = JSON.parse(e.data);
  document.getElementById('val-loss').textContent = fmtLoss(m.loss);
  document.getElementById('val-throughput').textContent = fmtNum(m.throughput);
  document.getElementById('val-gpu').textContent = m.gpu_util ? Math.round(m.gpu_util) : '—';
  document.getElementById('val-eta').textContent = fmtEta(m.eta_sec);

  const pct = Math.round((m.progress || 0) * 100);
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-steps').textContent =
    `Step ${m.step || 0} / ${m.total_steps || '—'}`;
  document.getElementById('progress-pct').textContent = pct + '%';

  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.textContent = `[${new Date().toLocaleTimeString()}] step=${m.step} loss=${fmtLoss(m.loss)} ${m.throughput ? m.throughput.toFixed(2)+'it/s' : ''} ${m.gpu_util ? 'GPU='+Math.round(m.gpu_util)+'%' : ''}`;
  logBox.appendChild(entry);
  logBox.scrollTop = logBox.scrollHeight;
  while (logBox.children.length > 100) logBox.removeChild(logBox.firstChild);
};

setInterval(() => {
  document.getElementById('time').textContent = new Date().toLocaleTimeString();
}, 1000);
</script>
</body>
</html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _log_path, _mock_mode

    parser = argparse.ArgumentParser(description="OCI Robot Cloud Training Monitor")
    parser.add_argument("--log", default=None,
                        help="Training log file to monitor (default: mock mode)")
    parser.add_argument("--port", type=int, default=8004)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true",
                        help="Use synthetic mock metrics (no real log needed)")
    args = parser.parse_args()

    if args.mock or args.log is None:
        _mock_mode = True
        print("[Monitor] Running in mock mode (synthetic metrics)")
    else:
        _log_path = Path(args.log)
        print(f"[Monitor] Watching log: {_log_path}")

    print(f"[Monitor] Dashboard: http://localhost:{args.port}/dashboard")
    print(f"[Monitor] SSE stream: http://localhost:{args.port}/stream")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
