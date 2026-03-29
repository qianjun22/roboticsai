#!/usr/bin/env python3
"""
continuous_learning.py — Autonomous continuous learning loop for OCI Robot Cloud.

Monitors deployed GR00T checkpoints for performance drift, accumulates new
demonstrations (real robot or sim), and triggers incremental fine-tuning when
thresholds are met. Implements a data flywheel: deploy → monitor → collect → retrain.

Usage:
    python src/training/continuous_learning.py --port 8018 [--mock]

Endpoints (port 8018):
    GET  /health
    GET  /           — loop state dashboard
    GET  /state      — JSON loop state
    POST /trigger    — manual retrain trigger
    POST /checkpoint — register a newly deployed checkpoint
    POST /eval_result — push eval result (updates drift detector)

Loop lifecycle:
    1. Monitor: poll /eval every N minutes → track rolling success rate
    2. Drift detect: if 7-day avg drops >10pp below peak → flag drift
    3. Collect: accumulate new demos (via data_collection_api or DAgger)
    4. Retrain: launch fine-tune when either:
       a. drift detected, OR
       b. N_ACCUMULATE new episodes collected
    5. Validate: run 10-ep eval on new checkpoint, compare vs deployed
    6. Promote: if new > deployed by PROMOTE_THRESHOLD → swap checkpoint
    7. Goto 1
"""

import argparse
import json
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ── Config ────────────────────────────────────────────────────────────────────

POLL_INTERVAL_S = 300        # eval poll every 5 min
DRIFT_THRESHOLD_PP = 0.10    # 10 percentage-point drop → drift
ACCUMULATE_TRIGGER = 50      # retrain after 50 new demos
PROMOTE_THRESHOLD = 0.05     # new must be >5pp better to promote
EVAL_WINDOW = 20             # rolling window for success rate
FINETUNE_STEPS = 3000        # steps for incremental fine-tune
REPLAYFRAC = 0.3             # fraction of old data to replay (catastrophic forgetting prevention)

STATE_PATH = Path("/tmp/cl_state.json")


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class LoopState:
    phase: str = "idle"        # idle / monitoring / drifted / collecting / retraining / validating
    deployed_ckpt: str = ""
    deployed_rate: float = 0.0
    peak_rate: float = 0.0
    rolling_rates: list = field(default_factory=list)  # last EVAL_WINDOW eval results
    n_new_demos: int = 0
    n_retrains: int = 0
    last_eval_ts: str = ""
    last_retrain_ts: str = ""
    drift_detected: bool = False
    drift_reason: str = ""
    events: list = field(default_factory=list)  # ring of last 50 events
    candidate_ckpt: str = ""   # checkpoint being validated
    candidate_rate: float = 0.0


_state = LoopState()
_lock = threading.Lock()


def _log_event(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        _state.events = ([{"ts": ts, "msg": msg}] + _state.events)[:50]
    print(f"[CL] {ts}  {msg}")


def _save_state():
    STATE_PATH.write_text(json.dumps(asdict(_state), indent=2))


# ── Drift detection ───────────────────────────────────────────────────────────

def _update_drift(new_rate: float):
    with _lock:
        _state.rolling_rates.append(new_rate)
        if len(_state.rolling_rates) > EVAL_WINDOW:
            _state.rolling_rates.pop(0)
        if new_rate > _state.peak_rate:
            _state.peak_rate = new_rate
        avg = sum(_state.rolling_rates) / len(_state.rolling_rates)
        if _state.peak_rate - avg >= DRIFT_THRESHOLD_PP and len(_state.rolling_rates) >= 5:
            if not _state.drift_detected:
                _state.drift_detected = True
                _state.drift_reason = (
                    f"Rolling avg {avg:.1%} dropped >10pp below peak {_state.peak_rate:.1%}"
                )
                _state.phase = "drifted"
                _log_event(f"DRIFT DETECTED: {_state.drift_reason}")


# ── Mock eval (no GPU) ────────────────────────────────────────────────────────

def _mock_eval_rate() -> float:
    """Simulate gradual drift then recovery after retrain."""
    n = len(_state.rolling_rates)
    base = _state.peak_rate if _state.peak_rate > 0 else 0.25
    # Simulate drift over time, then recovery after retrain
    drift = min(0.0, -0.02 * max(0, n - 5)) if not _state.drift_detected else 0.0
    recovery = 0.15 if _state.n_retrains > 0 else 0.0
    noise = (hash(str(n) + str(_state.n_retrains)) % 100 - 50) / 1000
    return max(0.0, min(1.0, base + drift + recovery + noise))


def _run_eval(server_url: str, n_eps: int = 5, mock: bool = False) -> float:
    """Run eval and return success rate."""
    if mock:
        rate = _mock_eval_rate()
        _log_event(f"[mock eval] server={server_url} rate={rate:.1%}")
        return rate
    try:
        import requests
        result = requests.post(
            f"{server_url}/eval",
            json={"n_episodes": n_eps},
            timeout=n_eps * 30,
        ).json()
        return float(result.get("success_rate", 0.0))
    except Exception as e:
        _log_event(f"Eval failed: {e}")
        return _state.deployed_rate


# ── Retrain ───────────────────────────────────────────────────────────────────

def _launch_retrain(mock: bool = False):
    _log_event(f"Launching incremental fine-tune ({_state.n_new_demos} new demos, {FINETUNE_STEPS} steps)")
    with _lock:
        _state.phase = "retraining"
        _state.last_retrain_ts = datetime.now().isoformat()

    if mock:
        time.sleep(2)
        candidate_ckpt = f"/tmp/cl_run{_state.n_retrains+1}/checkpoint-{FINETUNE_STEPS}"
        candidate_rate = min(1.0, _state.deployed_rate + 0.12 + 0.05 * _state.n_retrains)
        _on_retrain_complete(candidate_ckpt, candidate_rate)
        return

    try:
        proc = subprocess.run(
            [
                "python3", "src/training/finetune.py",
                "--base-model", _state.deployed_ckpt,
                "--steps", str(FINETUNE_STEPS),
                "--output", f"/tmp/cl_run{_state.n_retrains+1}",
            ],
            capture_output=True, text=True, timeout=7200,
        )
        if proc.returncode == 0:
            ckpt = f"/tmp/cl_run{_state.n_retrains+1}/checkpoint-{FINETUNE_STEPS}"
            _log_event(f"Fine-tune complete: {ckpt}")
            _on_retrain_complete(ckpt, None)
        else:
            _log_event(f"Fine-tune failed: {proc.stderr[-200:]}")
            with _lock:
                _state.phase = "monitoring"
    except subprocess.TimeoutExpired:
        _log_event("Fine-tune timed out")
        with _lock:
            _state.phase = "monitoring"


def _on_retrain_complete(ckpt: str, mock_rate: Optional[float]):
    with _lock:
        _state.candidate_ckpt = ckpt
        _state.phase = "validating"
        _state.n_retrains += 1
    _log_event(f"Validating candidate: {ckpt}")
    if mock_rate is not None:
        candidate_rate = mock_rate
    else:
        candidate_rate = _run_eval("http://localhost:8020", n_eps=10)
    with _lock:
        _state.candidate_rate = candidate_rate
    _log_event(f"Candidate rate: {candidate_rate:.1%} vs deployed {_state.deployed_rate:.1%}")
    if candidate_rate >= _state.deployed_rate + PROMOTE_THRESHOLD:
        _promote(ckpt, candidate_rate)
    else:
        _log_event(f"Candidate not promoted (diff {candidate_rate - _state.deployed_rate:+.1%} < {PROMOTE_THRESHOLD:.0%})")
        with _lock:
            _state.phase = "monitoring"
            _state.drift_detected = False


def _promote(ckpt: str, rate: float):
    with _lock:
        old = _state.deployed_ckpt
        _state.deployed_ckpt = ckpt
        _state.deployed_rate = rate
        _state.peak_rate = max(_state.peak_rate, rate)
        _state.drift_detected = False
        _state.drift_reason = ""
        _state.n_new_demos = 0
        _state.phase = "monitoring"
    _log_event(f"PROMOTED: {ckpt} ({rate:.1%}) replaced {old}")


# ── Monitor loop ──────────────────────────────────────────────────────────────

def _monitor_loop(server_url: str, mock: bool):
    _log_event(f"Monitor loop started (poll={POLL_INTERVAL_S}s, drift={DRIFT_THRESHOLD_PP:.0%}, accumulate={ACCUMULATE_TRIGGER})")
    with _lock:
        _state.phase = "monitoring"
        if not _state.deployed_ckpt:
            _state.deployed_ckpt = "/tmp/finetune_1000_5k/checkpoint-5000"
            _state.deployed_rate = 0.05
            _state.peak_rate = 0.05

    while True:
        time.sleep(POLL_INTERVAL_S if not mock else 5)
        with _lock:
            phase = _state.phase

        if phase in ("monitoring", "drifted"):
            rate = _run_eval(server_url, n_eps=10, mock=mock)
            with _lock:
                _state.deployed_rate = rate
                _state.last_eval_ts = datetime.now().isoformat()
            _update_drift(rate)
            _save_state()

            # Check triggers
            with _lock:
                drift = _state.drift_detected
                demos = _state.n_new_demos
                cur_phase = _state.phase

            if drift or demos >= ACCUMULATE_TRIGGER:
                reason = f"drift={drift}" if drift else f"accumulated {demos} demos"
                _log_event(f"Retrain triggered ({reason})")
                t = threading.Thread(target=_launch_retrain, args=(mock,), daemon=True)
                t.start()


# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Continuous Learning Loop", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class EvalResult(BaseModel):
    success_rate: float
    n_episodes: int = 10
    timestamp: str = ""

class CheckpointRegister(BaseModel):
    checkpoint_path: str
    initial_rate: float = 0.05


@app.get("/health")
def health():
    return {"status": "ok", "phase": _state.phase}

@app.get("/state")
def get_state():
    return asdict(_state)

@app.post("/eval_result")
def push_eval(ev: EvalResult):
    with _lock:
        _state.deployed_rate = ev.success_rate
        _state.last_eval_ts = ev.timestamp or datetime.now().isoformat()
    _update_drift(ev.success_rate)
    _log_event(f"Eval pushed: {ev.success_rate:.1%} over {ev.n_episodes} eps")
    return {"phase": _state.phase, "drift": _state.drift_detected}

@app.post("/checkpoint")
def register_checkpoint(req: CheckpointRegister):
    _promote(req.checkpoint_path, req.initial_rate)
    return {"status": "registered", "deployed_ckpt": _state.deployed_ckpt}

@app.post("/trigger")
def manual_trigger():
    if _state.phase in ("retraining", "validating"):
        return {"status": "already_running", "phase": _state.phase}
    _log_event("Manual retrain trigger")
    t = threading.Thread(target=_launch_retrain, args=(True,), daemon=True)
    t.start()
    return {"status": "triggered"}

@app.post("/demo_collected")
def demo_collected(n: int = 1):
    with _lock:
        _state.n_new_demos += n
    _log_event(f"Demo collected: total={_state.n_new_demos}")
    return {"n_new_demos": _state.n_new_demos}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    s = _state
    phase_color = {
        "idle": "#64748b", "monitoring": "#3b82f6", "drifted": "#f59e0b",
        "collecting": "#8b5cf6", "retraining": "#f59e0b", "validating": "#06b6d4",
    }.get(s.phase, "#64748b")

    events_html = "".join(
        f"<tr><td>{e['ts']}</td><td>{e['msg']}</td></tr>"
        for e in s.events[:15]
    )
    rates_js = "[" + ",".join(f"{r:.3f}" for r in s.rolling_rates) + "]"

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Continuous Learning Loop</title>
<meta http-equiv="refresh" content="10">
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} .phase{{font-size:1.4em;font-weight:bold;color:{phase_color};padding:8px 16px;
border:2px solid {phase_color};border-radius:6px;display:inline-block;margin:12px 0}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}}
.card{{background:#1e293b;border-radius:8px;padding:16px;text-align:center}}
.val{{font-size:2em;font-weight:bold}} .lbl{{color:#64748b;font-size:.8em}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}
th{{background:#C74634;color:white;padding:6px 10px;text-align:left;font-size:.82em}}
td{{padding:5px 10px;border-bottom:1px solid #1e293b;font-size:.84em}}
canvas{{background:#1e293b;border-radius:8px;margin-top:16px}}
</style></head><body>
<h1>Continuous Learning Loop</h1>
<p style="color:#64748b">OCI Robot Cloud · Data Flywheel · Auto-refresh: 10s</p>
<div class="phase">{s.phase.upper()}</div>
{'<p style="color:#f59e0b">⚠ ' + s.drift_reason + '</p>' if s.drift_detected else ''}

<div class="grid">
  <div class="card"><div class="val" style="color:#10b981">{s.deployed_rate:.0%}</div><div class="lbl">Current Rate</div></div>
  <div class="card"><div class="val" style="color:#3b82f6">{s.peak_rate:.0%}</div><div class="lbl">Peak Rate</div></div>
  <div class="card"><div class="val">{s.n_new_demos}</div><div class="lbl">New Demos ({ACCUMULATE_TRIGGER} → retrain)</div></div>
  <div class="card"><div class="val">{s.n_retrains}</div><div class="lbl">Retrains Done</div></div>
</div>

<p style="color:#94a3b8;font-size:.85em">Deployed: <code>{s.deployed_ckpt or 'none'}</code></p>
{'<p style="color:#06b6d4;font-size:.85em">Validating: <code>' + s.candidate_ckpt + '</code> (' + f"{s.candidate_rate:.0%}" + ')</p>' if s.candidate_ckpt and s.phase == 'validating' else ''}

<canvas id="chart" width="600" height="120"></canvas>
<script>
const rates = {rates_js};
const canvas = document.getElementById('chart');
if (canvas && rates.length > 1) {{
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height, pad = 16;
  const max = Math.max(...rates, 0.3);
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
  ctx.beginPath();
  rates.forEach((r, i) => {{
    const x = pad + (i / (rates.length - 1)) * (w - 2*pad);
    const y = h - pad - (r / max) * (h - 2*pad);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.stroke();
  // drift line
  ctx.strokeStyle = '#f59e0b'; ctx.setLineDash([4,4]);
  ctx.beginPath();
  const threshold = {s.peak_rate:.3f} - {DRIFT_THRESHOLD_PP};
  const ty = h - pad - (threshold / max) * (h - 2*pad);
  ctx.moveTo(pad, ty); ctx.lineTo(w - pad, ty); ctx.stroke();
}}
</script>

<h2 style="color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;margin-top:24px">Recent Events</h2>
<table><tr><th>Timestamp</th><th>Event</th></tr>
{events_html if events_html else '<tr><td colspan="2" style="color:#475569">No events yet</td></tr>'}
</table>
</body></html>"""


def main():
    global _mock
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--server-url", default="http://localhost:8002")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    _log_event(f"Starting continuous learning loop (mock={args.mock})")
    t = threading.Thread(target=_monitor_loop, args=(args.server_url, args.mock), daemon=True)
    t.start()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
