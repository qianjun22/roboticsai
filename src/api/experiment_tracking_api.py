"""
experiment_tracking_api.py — OCI Robot Cloud Experiment Tracking Service
Port: 8081

Tracks GR00T fine-tuning experiments, runs, hyperparameters, and metrics.
"""

import math
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PORT = 8081
A100_COST_PER_HOUR = 4.10
BASE_MODEL = "GR00T-N1.6-3B"
QUARTER = "Q1 2026"


@dataclass
class ExperimentRecord:
    id: str
    name: str
    description: str
    model_base: str
    created_at: str
    tags: List[str] = field(default_factory=list)


@dataclass
class RunRecord:
    id: str
    experiment_id: str
    status: str
    hyperparams: Dict[str, Any]
    started_at: str
    ended_at: Optional[str]
    metrics_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricPoint:
    run_id: str
    step: int
    metric_name: str
    value: float
    timestamp: str


_experiments: Dict[str, ExperimentRecord] = {}
_runs: Dict[str, RunRecord] = {}
_metrics: List[MetricPoint] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ts(date_str: str) -> str:
    return date_str + "T00:00:00+00:00"


def _seed_metric_series(run_id, metric_name, steps, start_val, end_val, decay="exp", stride=10):
    base_ts = datetime.now(timezone.utc).isoformat()
    sample_steps = list(range(stride, steps + 1, stride))
    n = len(sample_steps)
    for i, step in enumerate(sample_steps):
        t = i / max(n - 1, 1)
        if decay == "exp":
            val = start_val * math.exp(-t * math.log(start_val / end_val)) if start_val > 0 and end_val > 0 else start_val + (end_val - start_val) * t
        else:
            val = start_val + (end_val - start_val) * math.log1p(t * (math.e - 1))
        _metrics.append(MetricPoint(run_id=run_id, step=step, metric_name=metric_name, value=round(val, 6), timestamp=base_ts))


def _seed_data() -> None:
    exp_bc = ExperimentRecord(id="bc_baseline", name="bc_baseline",
        description="Behavioral cloning baseline — 100 demo episodes, standard GR00T fine-tune",
        model_base=BASE_MODEL, created_at=_ts("2026-01-10"), tags=["bc", "baseline", "gr00t"])
    _experiments[exp_bc.id] = exp_bc
    run_001 = RunRecord(id="run_001", experiment_id="bc_baseline", status="completed",
        hyperparams={"num_episodes": 100, "train_steps": 500, "learning_rate": 1e-4, "batch_size": 32, "model": BASE_MODEL},
        started_at=_ts("2026-01-10"), ended_at=_ts("2026-01-10"),
        metrics_summary={"success_rate": 0.05, "mae": 0.103, "num_episodes": 100, "train_steps": 500})
    _runs[run_001.id] = run_001
    _seed_metric_series("run_001", "mae", 500, 0.103, 0.016, "exp", 10)

    exp_dv1 = ExperimentRecord(id="dagger_v1", name="dagger_v1",
        description="DAgger iteration 1 — 1000 demos, 5000 steps",
        model_base=BASE_MODEL, created_at=_ts("2026-02-01"), tags=["dagger", "v1", "gr00t"])
    _experiments[exp_dv1.id] = exp_dv1
    run_005 = RunRecord(id="run_005", experiment_id="dagger_v1", status="completed",
        hyperparams={"num_episodes": 1000, "train_steps": 5000, "learning_rate": 1e-4, "batch_size": 64, "dagger_beta": 0.5, "model": BASE_MODEL},
        started_at=_ts("2026-02-01"), ended_at=_ts("2026-02-03"),
        metrics_summary={"success_rate": 0.05, "mae": 0.016, "num_episodes": 1000, "train_steps": 5000})
    _runs[run_005.id] = run_005
    run_006 = RunRecord(id="run_006", experiment_id="dagger_v1", status="running",
        hyperparams={"num_episodes": 1000, "train_steps": 8000, "learning_rate": 5e-5, "batch_size": 64, "dagger_beta": 0.3, "model": BASE_MODEL},
        started_at=_ts("2026-02-10"), ended_at=None,
        metrics_summary={"success_rate": "TBD", "mae": "TBD"})
    _runs[run_006.id] = run_006

    exp_dv2 = ExperimentRecord(id="dagger_v2", name="dagger_v2",
        description="DAgger iteration 2 — 1000 demos, 10000 steps; IK motion-planned SDG",
        model_base=BASE_MODEL, created_at=_ts("2026-03-01"), tags=["dagger", "v2", "gr00t", "ik-sdg"])
    _experiments[exp_dv2.id] = exp_dv2
    run_009 = RunRecord(id="run_009", experiment_id="dagger_v2", status="completed",
        hyperparams={"num_episodes": 1000, "train_steps": 10000, "learning_rate": 5e-5, "batch_size": 64, "dagger_beta": 0.2, "use_ik_sdg": True, "model": BASE_MODEL},
        started_at=_ts("2026-03-01"), ended_at=_ts("2026-03-05"),
        metrics_summary={"success_rate": 0.71, "mae": 0.018, "num_episodes": 1000, "train_steps": 10000, "p99_latency_ms": 227})
    _runs[run_009.id] = run_009
    _seed_metric_series("run_009", "mae", 10000, 0.095, 0.018, "exp", 100)
    _seed_metric_series("run_009", "success_rate", 10000, 0.05, 0.71, "log", 100)


try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="OCI Robot Cloud — Experiment Tracking API", version="1.0.0")

    @app.get("/experiments")
    def list_experiments(): return [asdict(e) for e in _experiments.values()]

    @app.post("/experiments", status_code=201)
    def create_experiment(body: dict):
        exp_id = body.get("id") or str(uuid.uuid4())[:8]
        if exp_id in _experiments: raise HTTPException(status_code=409, detail=f"Experiment '{exp_id}' already exists")
        exp = ExperimentRecord(id=exp_id, name=body.get("name", exp_id), description=body.get("description", ""),
                               model_base=body.get("model_base", BASE_MODEL), created_at=_now(), tags=body.get("tags", []))
        _experiments[exp_id] = exp
        return asdict(exp)

    @app.get("/experiments/{experiment_id}")
    def get_experiment(experiment_id: str):
        if experiment_id not in _experiments: raise HTTPException(status_code=404, detail="Experiment not found")
        return asdict(_experiments[experiment_id])

    @app.get("/experiments/{experiment_id}/runs")
    def list_runs_for_experiment(experiment_id: str):
        if experiment_id not in _experiments: raise HTTPException(status_code=404, detail="Experiment not found")
        return [asdict(r) for r in _runs.values() if r.experiment_id == experiment_id]

    @app.post("/experiments/{experiment_id}/runs", status_code=201)
    def create_run(experiment_id: str, body: dict):
        if experiment_id not in _experiments: raise HTTPException(status_code=404, detail="Experiment not found")
        run_id = body.get("id") or "run_" + str(uuid.uuid4())[:6]
        if run_id in _runs: raise HTTPException(status_code=409, detail=f"Run '{run_id}' already exists")
        run = RunRecord(id=run_id, experiment_id=experiment_id, status=body.get("status", "running"),
                        hyperparams=body.get("hyperparams", {}), started_at=_now(), ended_at=None,
                        metrics_summary=body.get("metrics_summary", {}))
        _runs[run_id] = run
        return asdict(run)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        if run_id not in _runs: raise HTTPException(status_code=404, detail="Run not found")
        return asdict(_runs[run_id])

    @app.get("/runs/{run_id}/metrics")
    def get_metrics(run_id: str, metric_name: Optional[str] = Query(default=None)):
        if run_id not in _runs: raise HTTPException(status_code=404, detail="Run not found")
        points = [asdict(m) for m in _metrics if m.run_id == run_id]
        if metric_name: points = [p for p in points if p["metric_name"] == metric_name]
        return points

    @app.post("/runs/{run_id}/metrics/batch", status_code=201)
    def log_metrics_batch(run_id: str, body: list):
        if run_id not in _runs: raise HTTPException(status_code=404, detail="Run not found")
        ts = _now()
        added = 0
        for item in body:
            _metrics.append(MetricPoint(run_id=run_id, step=item.get("step", 0),
                metric_name=item.get("metric_name", "unknown"), value=float(item.get("value", 0.0)),
                timestamp=item.get("timestamp", ts)))
            added += 1
        return {"added": added}

    @app.get("/compare")
    def compare_runs(run_ids: str = Query(..., description="Comma-separated run IDs")):
        ids = [r.strip() for r in run_ids.split(",") if r.strip()]
        return [{"run_id": rid, "error": "not found"} if rid not in _runs
                else {"run_id": rid, "experiment_id": _runs[rid].experiment_id, "status": _runs[rid].status,
                      "hyperparams": _runs[rid].hyperparams, "metrics_summary": _runs[rid].metrics_summary,
                      "started_at": _runs[rid].started_at, "ended_at": _runs[rid].ended_at}
                for rid in ids]

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        rows = ""
        for run in _runs.values():
            exp = _experiments.get(run.experiment_id)
            ms = run.metrics_summary
            sc = {"completed": "#16a34a", "running": "#2563eb", "failed": "#dc2626"}.get(run.status, "#6b7280")
            rows += (f"<tr><td>{run.id}</td><td>{exp.name if exp else run.experiment_id}</td>"
                     f"<td style='color:{sc};font-weight:600'>{run.status}</td>"
                     f"<td>{run.hyperparams.get('train_steps','—')}</td><td>{run.hyperparams.get('num_episodes','—')}</td>"
                     f"<td>{ms.get('mae','—')}</td><td>{ms.get('success_rate','—')}</td>"
                     f"<td>{ms.get('p99_latency_ms','—')}</td><td>{run.started_at[:10]}</td></tr>\n")
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<title>OCI Robot Cloud — Experiment Tracker</title>
<style>body{{font-family:sans-serif;margin:0;background:#f8fafc;color:#1e293b}}
header{{background:#C74634;color:white;padding:18px 32px}}
header h1{{margin:0;font-size:1.4rem}}header p{{margin:4px 0 0;opacity:.85;font-size:.85rem}}
.content{{padding:28px 32px}}.kpi-row{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
.kpi{{background:white;border-radius:8px;padding:18px 24px;box-shadow:0 1px 4px rgba(0,0,0,.08);min-width:140px}}
.kpi .label{{font-size:.75rem;color:#64748b;text-transform:uppercase;margin-bottom:6px}}
.kpi .value{{font-size:1.6rem;font-weight:700;color:#C74634}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
th{{background:#C74634;color:white;padding:11px 14px;text-align:left;font-size:.8rem}}
td{{padding:10px 14px;border-bottom:1px solid #e2e8f0;font-size:.88rem}}
footer{{text-align:center;padding:20px;color:#94a3b8;font-size:.75rem}}</style>
</head><body>
<header><h1>OCI Robot Cloud — Experiment Tracking</h1>
<p>Base model: {BASE_MODEL} | A100: ${A100_COST_PER_HOUR}/hr | {QUARTER}</p></header>
<div class="content">
<div class="kpi-row">
<div class="kpi"><div class="label">Experiments</div><div class="value">{len(_experiments)}</div></div>
<div class="kpi"><div class="label">Total Runs</div><div class="value">{len(_runs)}</div></div>
<div class="kpi"><div class="label">Best SR</div><div class="value">71%</div></div>
<div class="kpi"><div class="label">Best MAE</div><div class="value">0.016</div></div>
<div class="kpi"><div class="label">Metric Points</div><div class="value">{len(_metrics)}</div></div>
</div>
<table><thead><tr><th>Run ID</th><th>Experiment</th><th>Status</th><th>Steps</th>
<th>Episodes</th><th>MAE</th><th>SR</th><th>P99 (ms)</th><th>Started</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<footer>OCI Robot Cloud Experiment Tracker — Port {PORT}</footer>
</body></html>"""


def _print_startup_summary() -> None:
    print("=" * 64)
    print(f"  OCI Robot Cloud — Experiment Tracking API  (port {PORT})")
    print("=" * 64)
    for exp in _experiments.values():
        runs = [r for r in _runs.values() if r.experiment_id == exp.id]
        print(f"\n  Experiment : {exp.name}")
        for r in runs:
            ms = r.metrics_summary
            print(f"    Run {r.id:12s}  status={r.status:10s}  SR={str(ms.get('success_rate','\u2014')):>5}  MAE={str(ms.get('mae','\u2014')):>6}  steps={ms.get('train_steps', r.hyperparams.get('train_steps','\u2014'))}")
    print(f"\n  Metric points seeded: {len(_metrics)}")
    print("=" * 64)


_seed_data()


def main() -> None:
    _print_startup_summary()
    if not _FASTAPI_AVAILABLE:
        print("[WARN] fastapi/uvicorn not installed. Install with: pip install fastapi uvicorn")
        return
    uvicorn.run("experiment_tracking_api:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    main()
