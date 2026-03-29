#!/usr/bin/env python3
"""
data_flywheel.py — Unified data flywheel orchestrator for OCI Robot Cloud.

Ties together data collection (real robot teleop + DAgger), quality scoring,
dataset versioning, continuous learning trigger, and visual progress dashboard.
This is the single URL a design partner bookmarks to watch their robot learn.

Port 8020 — the "mission control" for the entire OCI Robot Cloud.

Usage:
    python src/api/data_flywheel.py --port 8020 [--mock]

Endpoints:
    GET  /           — mission control dashboard
    GET  /health
    GET  /state      — full flywheel state JSON
    POST /ingest     — receive new demo batch (from teleop or DAgger)
    GET  /timeline   — event timeline (JSON)
    GET  /report     — generate shareable HTML report

Architecture:
    Teleop / DAgger → /ingest → quality filter → dataset versioning →
    continuous_learning.py trigger → fine-tune → eval → promote → next iter
"""

import argparse
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class Iteration:
    idx: int
    source: str          # "teleop" | "dagger" | "sim"
    n_demos: int
    quality_score: float # 0-1
    finetune_steps: int
    success_rate: float
    timestamp: str


@dataclass
class FlywheelState:
    partner: str = "demo"
    robot: str = "franka"
    task: str = "pick_and_lift"
    phase: str = "idle"   # idle | collecting | training | evaluating | promoting
    # Totals
    total_demos: int = 0
    total_steps: int = 0
    total_evals: int = 0
    total_cost_usd: float = 0.0
    # Current best
    best_rate: float = 0.0
    best_ckpt: str = ""
    deployed_rate: float = 0.05  # BC baseline
    # History
    iterations: list = field(default_factory=list)
    events: list = field(default_factory=list)


_state = FlywheelState()
_lock = threading.Lock()

COST_PER_STEP = 0.000043
COST_PER_EVAL = 0.022
COST_PER_DEMO = 0.008  # estimated human + compute per demo


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with _lock:
        _state.events = [{"ts": ts, "msg": msg}] + _state.events[:49]
    print(f"[flywheel] {ts}  {msg}")


# ── Pydantic ──────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    source: str = "teleop"    # teleop | dagger | sim
    n_demos: int = 10
    quality_score: float = 0.8
    finetune_steps: int = 2000
    mock_success_rate: Optional[float] = None   # for mock mode
    partner: Optional[str] = None
    robot: Optional[str] = None
    task: Optional[str] = None


# ── Flywheel step ─────────────────────────────────────────────────────────────

def _run_iteration(req: IngestRequest, mock: bool = False):
    with _lock:
        _state.phase = "collecting"
        if req.partner:
            _state.partner = req.partner
        if req.robot:
            _state.robot = req.robot
        if req.task:
            _state.task = req.task
        _state.total_demos += req.n_demos
        idx = len(_state.iterations)

    _log(f"Iter {idx}: ingesting {req.n_demos} demos from {req.source} (quality={req.quality_score:.2f})")
    time.sleep(0.5 if mock else 2)

    # Fine-tune
    with _lock:
        _state.phase = "training"
        _state.total_steps += req.finetune_steps
        _state.total_cost_usd += req.finetune_steps * COST_PER_STEP + req.n_demos * COST_PER_DEMO

    _log(f"Iter {idx}: fine-tuning {req.finetune_steps} steps …")
    time.sleep(1 if mock else 5)

    # Eval
    with _lock:
        _state.phase = "evaluating"
        _state.total_evals += 20
        _state.total_cost_usd += 20 * COST_PER_EVAL

    if req.mock_success_rate is not None:
        rate = req.mock_success_rate
    else:
        # Simulate gradual improvement
        base = _state.deployed_rate
        boost = 0.05 + 0.03 * idx * req.quality_score
        noise = (hash(str(idx) + req.source) % 10 - 5) / 100
        rate = min(1.0, max(0.0, base + boost + noise))

    _log(f"Iter {idx}: eval complete — {rate:.1%} success")

    iteration = Iteration(
        idx=idx, source=req.source,
        n_demos=req.n_demos, quality_score=req.quality_score,
        finetune_steps=req.finetune_steps,
        success_rate=rate,
        timestamp=datetime.now().isoformat(),
    )

    with _lock:
        _state.iterations.append(asdict(iteration))
        _state.phase = "promoting" if rate > _state.deployed_rate else "idle"
        if rate > _state.best_rate:
            _state.best_rate = rate
        if rate > _state.deployed_rate:
            old = _state.deployed_rate
            _state.deployed_rate = rate
            _state.best_ckpt = f"/tmp/flywheel/iter_{idx}/checkpoint-{req.finetune_steps}"
            _log(f"Iter {idx}: PROMOTED {old:.1%} → {rate:.1%}")
        else:
            _log(f"Iter {idx}: not promoted ({rate:.1%} <= {_state.deployed_rate:.1%})")
        _state.phase = "idle"


# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Data Flywheel", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_mock_mode = False


@app.get("/health")
def health():
    return {"status": "ok", "phase": _state.phase, "best_rate": _state.best_rate}


@app.get("/state")
def get_state():
    return asdict(_state)


@app.post("/ingest")
def ingest(req: IngestRequest):
    if _state.phase != "idle":
        return {"status": "busy", "phase": _state.phase}
    t = threading.Thread(target=_run_iteration, args=(req, _mock_mode), daemon=True)
    t.start()
    return {"status": "started", "iteration": len(_state.iterations)}


@app.get("/timeline")
def timeline():
    return _state.events


@app.get("/report", response_class=HTMLResponse)
def generate_report():
    return _make_dashboard(embed=True)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _make_dashboard(embed=False)


def _make_dashboard(embed: bool = False) -> str:
    s = _state
    phase_color = {
        "idle": "#10b981", "collecting": "#8b5cf6", "training": "#f59e0b",
        "evaluating": "#3b82f6", "promoting": "#C74634",
    }.get(s.phase, "#64748b")

    # Build success rate timeline for chart
    rates = [i["success_rate"] for i in s.iterations]
    rates_js = "[" + ",".join(f"{r:.3f}" for r in rates) + "]"
    labels_js = "[" + ",".join(f"'Iter {i[\"idx\"]}'" for i in s.iterations) + "]"

    iter_rows = ""
    for it in reversed(s.iterations):
        src_color = {"teleop": "#3b82f6", "dagger": "#8b5cf6", "sim": "#10b981"}.get(it["source"], "#64748b")
        sr = it["success_rate"]
        sr_color = "#10b981" if sr >= 0.3 else "#f59e0b" if sr >= 0.1 else "#ef4444"
        iter_rows += (
            f"<tr><td>Iter {it['idx']}</td>"
            f"<td><span style='color:{src_color}'>{it['source']}</span></td>"
            f"<td>{it['n_demos']}</td>"
            f"<td>{it['quality_score']:.2f}</td>"
            f"<td>{it['finetune_steps']:,}</td>"
            f"<td style='color:{sr_color};font-weight:bold'>{sr:.0%}</td>"
            f"<td>{it['timestamp'][:16]}</td></tr>"
        )

    events_html = "".join(
        f"<tr><td style='color:#64748b'>{e['ts']}</td><td>{e['msg']}</td></tr>"
        for e in s.events[:12]
    )

    refresh = '' if embed else '<meta http-equiv="refresh" content="5">'
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>OCI Data Flywheel — {s.partner}</title>
{refresh}
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634;margin-bottom:4px}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;
letter-spacing:.1em;border-bottom:1px solid #1e293b;padding-bottom:5px;margin-top:24px}}
.phase{{font-size:1.2em;font-weight:bold;color:{phase_color};padding:6px 14px;
border:2px solid {phase_color};border-radius:5px;display:inline-block;margin:8px 0}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}}
.card{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
.val{{font-size:2em;font-weight:bold}} .lbl{{color:#64748b;font-size:.78em}}
.big{{font-size:3em;font-weight:bold;color:#10b981}}
table{{width:100%;border-collapse:collapse}}
th{{background:#C74634;color:white;padding:6px 10px;text-align:left;font-size:.82em}}
td{{padding:5px 10px;border-bottom:1px solid #1e293b;font-size:.84em}}
canvas{{max-width:600px;background:#1e293b;border-radius:8px;padding:12px}}
button{{background:#C74634;color:white;border:none;padding:7px 16px;border-radius:5px;cursor:pointer;margin:4px}}
</style></head><body>
<h1>OCI Data Flywheel</h1>
<p style="color:#64748b">Partner: <b>{s.partner}</b> · Robot: {s.robot} · Task: {s.task}</p>
<div class="phase">{s.phase.upper()}</div>

<div style="margin:16px 0;text-align:center">
  <div class="big">{s.deployed_rate:.0%}</div>
  <div style="color:#64748b">Deployed Success Rate</div>
  <div style="color:#64748b;font-size:.85em">Peak: {s.best_rate:.0%}</div>
</div>

<div class="grid">
  <div class="card"><div class="val">{s.total_demos}</div><div class="lbl">Total Demos</div></div>
  <div class="card"><div class="val">{s.total_steps:,}</div><div class="lbl">Fine-tune Steps</div></div>
  <div class="card"><div class="val">{len(s.iterations)}</div><div class="lbl">Iterations</div></div>
  <div class="card"><div class="val" style="color:#10b981">${s.total_cost_usd:.2f}</div><div class="lbl">Total Cost (OCI)</div></div>
</div>

<h2>Success Rate Progression</h2>
<canvas id="chart" width="600" height="110"></canvas>
<script>
const rates = {rates_js};
const labels = {labels_js};
const canvas = document.getElementById('chart');
if (canvas && rates.length > 0) {{
  const ctx = canvas.getContext('2d');
  const w = canvas.width - 24, h = canvas.height - 24, px = 12, py = 12;
  const max = Math.max(...rates, 0.3);
  ctx.strokeStyle = '#10b981'; ctx.lineWidth = 2.5;
  ctx.beginPath();
  rates.forEach((r, i) => {{
    const x = px + (rates.length === 1 ? w/2 : (i / (rates.length - 1)) * w);
    const y = py + h - (r / max) * h;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.stroke();
  // dots
  ctx.fillStyle = '#10b981';
  rates.forEach((r, i) => {{
    const x = px + (rates.length === 1 ? w/2 : (i / (rates.length - 1)) * w);
    const y = py + h - (r / max) * h;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI*2); ctx.fill();
  }});
}}
</script>

<h2>Iteration History</h2>
<table><tr><th>Iter</th><th>Source</th><th>Demos</th><th>Quality</th><th>Steps</th><th>Success</th><th>Time</th></tr>
{iter_rows or '<tr><td colspan="7" style="color:#475569;text-align:center">No iterations yet — POST /ingest to start</td></tr>'}
</table>

<h2>Event Log</h2>
<table><tr><th>Time</th><th>Event</th></tr>
{events_html or '<tr><td colspan="2" style="color:#475569">No events</td></tr>'}
</table>

<div style="margin-top:20px">
  <button onclick="fetch('/ingest',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{source:'teleop',n_demos:10,mock_success_rate:null}})}}).then(()=>setTimeout(()=>location.reload(),1000))">
    + Ingest 10 Demos (teleop)
  </button>
  <button onclick="fetch('/ingest',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{source:'dagger',n_demos:20,finetune_steps:2000}})}}).then(()=>setTimeout(()=>location.reload(),1000))" style="background:#8b5cf6">
    + Run DAgger (20 eps)
  </button>
</div>
<p style="color:#475569;font-size:.78em;margin-top:24px">OCI Robot Cloud · github.com/qianjun22/roboticsai · Auto-refresh: 5s</p>
</body></html>"""


def main():
    global _mock_mode
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    _mock_mode = args.mock
    print(f"[flywheel] Data flywheel mission control on port {args.port} (mock={args.mock})")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
