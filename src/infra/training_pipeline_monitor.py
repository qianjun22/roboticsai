"""
training_pipeline_monitor.py -- FastAPI server (port 8075) for real-time GR00T
fine-tuning pipeline monitoring: stage health, throughput, queue depths, alerts.

Usage:
    python training_pipeline_monitor.py [--mock] [--port 8075] [--host 0.0.0.0]
"""

from __future__ import annotations

import argparse
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError as _e:
    raise SystemExit(f"Missing dependency: {_e}\nInstall with: pip install fastapi uvicorn") from _e

random.seed(42)
_rng = random.Random(42)

STAGES: List[str] = ["data_ingestion", "preprocessing", "sdg_generation", "fine_tuning", "evaluation", "checkpoint_save", "deployment"]
STATUS_RUNNING = "running"
STATUS_IDLE    = "idle"
STATUS_ERROR   = "error"
STATUS_QUEUED  = "queued"


@dataclass
class StageState:
    name: str
    status: str = STATUS_IDLE
    throughput: float = 0.0
    queue_depth: int = 0
    last_updated: float = field(default_factory=time.time)
    error_count: int = 0
    gpu_util: float = 0.0
    loss: float = 0.0
    step: int = 0
    total_steps: int = 5000
    throughput_history: Deque[float] = field(default_factory=lambda: deque(maxlen=20))


@dataclass
class Alert:
    stage: str
    kind: str
    message: str
    ts: float = field(default_factory=time.time)


@dataclass
class PipelineSnapshot:
    ts: float
    stages: Dict[str, Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    gpu_util: float
    loss: float
    step: int
    total_steps: int


_stages: Dict[str, StageState] = {n: StageState(name=n) for n in STAGES}
_history: Deque[PipelineSnapshot] = deque(maxlen=100)
_mock_mode: bool = True
_walk: Dict[str, float] = {n: _rng.uniform(0.3, 0.8) for n in STAGES}
_STEP_COUNTER = {"v": 5000}


def _smooth_walk(key: str, lo: float, hi: float, step: float = 0.05) -> float:
    v = _walk.get(key, (lo + hi) / 2)
    v += _rng.uniform(-step, step)
    v = max(lo, min(hi, v))
    _walk[key] = v
    return v


def simulate_pipeline_state() -> None:
    now = time.time()
    di = _stages["data_ingestion"]
    di.status = STATUS_RUNNING
    di.throughput = round(_smooth_walk("data_ingestion", 180, 260, 8), 1)
    di.queue_depth = _rng.randint(0, 120)
    di.last_updated = now
    pp = _stages["preprocessing"]
    pp.status = STATUS_RUNNING
    pp.throughput = round(_smooth_walk("preprocessing", 300, 420, 12), 1)
    pp.queue_depth = _rng.randint(0, 80)
    pp.last_updated = now
    sg = _stages["sdg_generation"]
    sg.status = STATUS_QUEUED
    sg.throughput = round(_smooth_walk("sdg_generation", 20, 60, 4), 1)
    sg.queue_depth = _rng.randint(200, 800)
    sg.last_updated = now
    ft = _stages["fine_tuning"]
    ft.status = STATUS_RUNNING
    ft.throughput = round(_smooth_walk("fine_tuning", 2.1, 2.6, 0.04), 3)
    _walk.setdefault("fine_tuning_gpu", 87.0)
    ft.gpu_util = round(_smooth_walk("fine_tuning_gpu", 84, 90, 0.5), 1)
    ft.loss = round(_smooth_walk("fine_tuning_loss", 0.092, 0.108, 0.002), 4)
    _walk.setdefault("fine_tuning_loss", 0.099)
    ft.step = _STEP_COUNTER["v"]
    ft.total_steps = 5000
    ft.queue_depth = 0
    ft.last_updated = now
    ev = _stages["evaluation"]
    ev.status = STATUS_RUNNING if _rng.random() > 0.7 else STATUS_IDLE
    ev.throughput = round(_smooth_walk("evaluation", 0.5, 3.0, 0.2), 2) if ev.status == STATUS_RUNNING else 0.0
    ev.queue_depth = _rng.randint(0, 10)
    ev.last_updated = now
    cs = _stages["checkpoint_save"]
    cs.status = STATUS_RUNNING if _rng.random() > 0.8 else STATUS_IDLE
    cs.throughput = round(_rng.uniform(10, 40), 1) if cs.status == STATUS_RUNNING else 0.0
    cs.queue_depth = _rng.randint(0, 5)
    cs.last_updated = now
    dp = _stages["deployment"]
    dp.status = STATUS_IDLE
    dp.throughput = 0.0
    dp.queue_depth = 0
    dp.last_updated = now
    for s in _stages.values():
        s.throughput_history.append(s.throughput)


def collect_alerts() -> List[Alert]:
    alerts: List[Alert] = []
    now = time.time()
    for s in _stages.values():
        if s.queue_depth > 1000:
            alerts.append(Alert(s.name, "queue_depth", f"{s.name}: queue_depth={s.queue_depth} > 1000"))
        if s.error_count > 5:
            alerts.append(Alert(s.name, "error_count", f"{s.name}: error_count={s.error_count} > 5"))
        if s.status == STATUS_RUNNING and (now - s.last_updated) > 600:
            alerts.append(Alert(s.name, "stuck", f"{s.name}: running but no update for {int(now - s.last_updated)}s"))
    return alerts


def take_snapshot() -> PipelineSnapshot:
    if _mock_mode:
        simulate_pipeline_state()
    alerts = collect_alerts()
    ft = _stages["fine_tuning"]
    snap = PipelineSnapshot(
        ts=time.time(),
        stages={n: {"status": s.status, "throughput": s.throughput, "queue_depth": s.queue_depth,
                    "last_updated": s.last_updated, "error_count": s.error_count,
                    "throughput_history": list(s.throughput_history),
                    "gpu_util": s.gpu_util if n == "fine_tuning" else None,
                    "loss": s.loss if n == "fine_tuning" else None,
                    "step": s.step if n == "fine_tuning" else None,
                    "total_steps": s.total_steps if n == "fine_tuning" else None}
                for n, s in _stages.items()},
        alerts=[{"stage": a.stage, "kind": a.kind, "message": a.message, "ts": a.ts} for a in alerts],
        gpu_util=ft.gpu_util, loss=ft.loss, step=ft.step, total_steps=ft.total_steps,
    )
    _history.append(snap)
    return snap


def sparkline_svg(values: List[float], width: int = 80, height: int = 28) -> str:
    if not values:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    n = len(values)
    step_x = width / max(n - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step_x
        y = height - ((v - lo) / span) * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<svg width="{width}" height="{height}" style="display:block">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="#C74634" stroke-width="1.5"/>'
            f'</svg>')


STATUS_COLORS = {STATUS_RUNNING: "#22c55e", STATUS_IDLE: "#94a3b8", STATUS_ERROR: "#ef4444", STATUS_QUEUED: "#f59e0b"}


def _stage_card(name: str, data: Dict[str, Any]) -> str:
    status = data["status"]
    color = STATUS_COLORS.get(status, "#94a3b8")
    th = data["throughput"]
    qd = data["queue_depth"]
    ec = data["error_count"]
    spark = sparkline_svg(data.get("throughput_history", []))
    th_unit = "it/s" if name == "fine_tuning" else "items/min"
    extra = ""
    if name == "fine_tuning":
        gpu = data.get("gpu_util") or 0
        loss = data.get("loss") or 0
        step = data.get("step") or 0
        total = data.get("total_steps") or 5000
        pct = step / total * 100 if total else 0
        extra = (f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-top:4px;color:#94a3b8">'
                 f'<span>GPU util</span><span style="color:#f8fafc;font-weight:600">{gpu:.1f}%</span></div>'
                 f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-top:4px;color:#94a3b8">'
                 f'<span>Loss</span><span style="color:#f8fafc;font-weight:600">{loss:.4f}</span></div>'
                 f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-top:4px;color:#94a3b8">'
                 f'<span>Steps</span><span style="color:#f8fafc;font-weight:600">{step}/{total}</span></div>'
                 f'<div style="background:#334155;border-radius:4px;height:6px;margin-top:8px">'
                 f'<div style="background:#C74634;border-radius:4px;height:6px;width:{pct:.1f}%"></div></div>')
    return (f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
            f'<span style="font-weight:600;font-size:0.9rem">{name.replace("_"," ").title()}</span>'
            f'<span style="font-size:0.7rem;padding:2px 8px;border-radius:9999px;color:#0f172a;font-weight:700;background:{color}">{status}</span></div>'
            f'<div style="display:flex;gap:16px;margin-bottom:8px">'
            f'<div style="flex:1;text-align:center"><div style="font-size:1.1rem;font-weight:700;color:#f8fafc">{th:.2f}</div><div style="font-size:0.65rem;color:#64748b">{th_unit}</div></div>'
            f'<div style="flex:1;text-align:center"><div style="font-size:1.1rem;font-weight:700;color:#f8fafc">{qd}</div><div style="font-size:0.65rem;color:#64748b">queue</div></div>'
            f'<div style="flex:1;text-align:center"><div style="font-size:1.1rem;font-weight:700;color:#f8fafc">{ec}</div><div style="font-size:0.65rem;color:#64748b">errors</div></div></div>'
            f'{extra}<div style="margin-top:10px">{spark}</div></div>')


def render_html_dashboard(snap: PipelineSnapshot) -> str:
    ts_str = datetime.fromtimestamp(snap.ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cards_html = "\n".join(_stage_card(name, data) for name, data in snap.stages.items())
    alerts_html = ""
    if snap.alerts:
        rows = "".join(f'<div style="font-size:0.8rem;color:#fca5a5;margin-top:6px"><span style="background:#7f1d1d;color:#fca5a5;font-size:0.65rem;padding:1px 6px;border-radius:4px;margin-right:6px">{a["kind"]}</span>{a["message"]}</div>' for a in snap.alerts)
        alerts_html = f'<div style="margin-top:24px;background:#1e293b;border:1px solid #7f1d1d;border-radius:8px;padding:16px"><h3 style="font-size:0.9rem;margin-bottom:8px">Active Alerts ({len(snap.alerts)})</h3>{rows}</div>'
    else:
        alerts_html = '<div style="margin-top:24px;background:#1e293b;border:1px solid #166534;border-radius:8px;padding:16px"><h3 style="font-size:0.9rem">No Active Alerts</h3></div>'
    ft = snap.stages.get("fine_tuning", {})
    hero_gpu = ft.get("gpu_util") or 0
    hero_loss = ft.get("loss") or 0
    hero_th = ft.get("throughput") or 0
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta http-equiv="refresh" content="5"><title>GR00T Pipeline Monitor</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
header{{background:#1e293b;border-bottom:2px solid #C74634;padding:16px 32px;display:flex;justify-content:space-between;align-items:center}}
header h1{{font-size:1.25rem;color:#f8fafc}}header h1 span{{color:#C74634}}
.hero-bar{{background:#1e293b;display:flex;gap:32px;padding:12px 32px;border-bottom:1px solid #334155}}
.hero-metric{{display:flex;flex-direction:column;align-items:center}}
.hero-value{{font-size:1.6rem;font-weight:700;color:#C74634}}.hero-label{{font-size:0.7rem;color:#94a3b8;text-transform:uppercase}}
.main{{padding:24px 32px}}.stages-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
footer{{text-align:center;padding:16px;font-size:0.7rem;color:#475569;border-top:1px solid #1e293b;margin-top:32px}}</style></head>
<body><header><h1>OCI Robot Cloud \u2014 <span>GR00T Pipeline Monitor</span></h1><span style="font-size:0.75rem;color:#64748b">Last updated: {ts_str} | auto-refresh 5s</span></header>
<div class="hero-bar">
  <div class="hero-metric"><span class="hero-value">{hero_th:.2f}</span><span class="hero-label">it/s (fine-tune)</span></div>
  <div class="hero-metric"><span class="hero-value">{hero_gpu:.1f}%</span><span class="hero-label">GPU util</span></div>
  <div class="hero-metric"><span class="hero-value">{hero_loss:.4f}</span><span class="hero-label">Loss</span></div>
  <div class="hero-metric"><span class="hero-value">{len(snap.alerts)}</span><span class="hero-label">Alerts</span></div>
</div>
<div class="main"><div class="stages-grid">{cards_html}</div>{alerts_html}</div>
<footer>OCI Robot Cloud \u2014 Training Pipeline Monitor | port 8075 | oracle.com</footer></body></html>"""


app = FastAPI(title="GR00T Training Pipeline Monitor", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=render_html_dashboard(take_snapshot()))


@app.get("/api/status")
async def api_status():
    snap = take_snapshot()
    return JSONResponse({"ts": snap.ts, "mock": _mock_mode, "stages": snap.stages, "alerts": snap.alerts,
                         "summary": {"gpu_util": snap.gpu_util, "loss": snap.loss, "step": snap.step,
                                     "total_steps": snap.total_steps, "alert_count": len(snap.alerts)}})


@app.get("/api/history")
async def api_history():
    return JSONResponse([{"ts": s.ts, "stages": s.stages, "alerts": s.alerts,
                          "gpu_util": s.gpu_util, "loss": s.loss, "step": s.step} for s in _history])


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "ts": time.time(), "mock": _mock_mode, "history_len": len(_history)})


def main() -> None:
    global _mock_mode
    parser = argparse.ArgumentParser(description="GR00T Training Pipeline Monitor")
    parser.add_argument("--mock", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--port", type=int, default=8075)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    _mock_mode = args.mock
    print(f"[pipeline-monitor] Starting on http://{args.host}:{args.port}  mock={_mock_mode}")
    take_snapshot()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
