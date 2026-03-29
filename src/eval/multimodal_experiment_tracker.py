#!/usr/bin/env python3
"""
multimodal_experiment_tracker.py — MLflow-compatible experiment tracker for GR00T runs.

Tracks all training runs, hyperparameters, eval metrics, and artifacts in a
single lightweight SQLite-backed store. Generates comparison dashboards and
provides REST API for CI/CD integration.

Usage:
    python src/eval/multimodal_experiment_tracker.py --port 8019 [--db /tmp/experiments.db]

Endpoints (port 8019):
    GET  /health
    GET  /           — experiment browser (dark theme)
    POST /runs       — create a new run
    PATCH /runs/{id} — update run (add metrics/params/tags)
    GET  /runs/{id}  — get run details
    GET  /runs       — list runs (filterable)
    POST /runs/{id}/log_metric  — log (key, value, step)
    POST /runs/{id}/log_param   — log hyperparameter
    POST /runs/{id}/finish      — mark run complete
    GET  /compare    — side-by-side comparison of 2+ runs
    GET  /leaderboard — sorted by success_rate desc
"""

import argparse
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_PATH = Path("/tmp/experiments.db")


# ── Database ──────────────────────────────────────────────────────────────────

def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(path: Path = DB_PATH):
    conn = get_db(path)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        name TEXT,
        experiment TEXT DEFAULT 'default',
        status TEXT DEFAULT 'running',
        tags TEXT DEFAULT '{}',
        created_at TEXT,
        finished_at TEXT,
        notes TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS metrics (
        run_id TEXT,
        key TEXT,
        value REAL,
        step INTEGER DEFAULT 0,
        ts TEXT
    );
    CREATE TABLE IF NOT EXISTS params (
        run_id TEXT,
        key TEXT,
        value TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_metrics_run ON metrics(run_id, key);
    CREATE INDEX IF NOT EXISTS idx_params_run ON params(run_id);
    """)
    conn.commit()
    conn.close()


def _now():
    return datetime.now().isoformat()


# ── Pydantic models ───────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    name: str
    experiment: str = "default"
    tags: dict = {}
    notes: str = ""
    params: dict = {}

class MetricLog(BaseModel):
    key: str
    value: float
    step: int = 0

class ParamLog(BaseModel):
    key: str
    value: str

class RunUpdate(BaseModel):
    tags: Optional[dict] = None
    notes: Optional[str] = None
    status: Optional[str] = None


# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Experiment Tracker", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_db_path = DB_PATH


def _db():
    return get_db(_db_path)


@app.on_event("startup")
def startup():
    init_db(_db_path)


@app.get("/health")
def health():
    db = _db()
    n = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    return {"status": "ok", "n_runs": n}


@app.post("/runs")
def create_run(req: RunCreate):
    run_id = str(uuid.uuid4())[:8]
    db = _db()
    db.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
        (run_id, req.name, req.experiment, "running",
         json.dumps(req.tags), _now(), None, req.notes),
    )
    for k, v in req.params.items():
        db.execute("INSERT INTO params VALUES (?,?,?)", (run_id, k, str(v)))
    db.commit()
    return {"run_id": run_id, "name": req.name, "status": "running"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    db = _db()
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    run = dict(row)
    run["tags"] = json.loads(run["tags"])

    # Latest metric values
    metrics = {}
    for m in db.execute(
        "SELECT key, value, step FROM metrics WHERE run_id=? ORDER BY step",
        (run_id,)
    ).fetchall():
        metrics[m["key"]] = {"value": m["value"], "step": m["step"]}
    run["metrics"] = metrics

    # Params
    params = {p["key"]: p["value"] for p in
               db.execute("SELECT key,value FROM params WHERE run_id=?", (run_id,)).fetchall()}
    run["params"] = params

    return run


@app.get("/runs")
def list_runs(experiment: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    db = _db()
    q = "SELECT * FROM runs"
    conds, vals = [], []
    if experiment:
        conds.append("experiment=?"); vals.append(experiment)
    if status:
        conds.append("status=?"); vals.append(status)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY created_at DESC LIMIT ?"
    vals.append(limit)
    rows = db.execute(q, vals).fetchall()

    result = []
    for row in rows:
        r = dict(row)
        r["tags"] = json.loads(r["tags"])
        # Attach key metrics
        m = db.execute(
            "SELECT key, value FROM metrics WHERE run_id=? GROUP BY key HAVING MAX(step)",
            (r["id"],)
        ).fetchall()
        r["metrics"] = {x["key"]: x["value"] for x in m}
        result.append(r)
    return result


@app.post("/runs/{run_id}/log_metric")
def log_metric(run_id: str, req: MetricLog):
    db = _db()
    db.execute(
        "INSERT INTO metrics VALUES (?,?,?,?,?)",
        (run_id, req.key, req.value, req.step, _now())
    )
    db.commit()
    return {"status": "ok"}


@app.post("/runs/{run_id}/log_param")
def log_param(run_id: str, req: ParamLog):
    db = _db()
    # Upsert
    db.execute("DELETE FROM params WHERE run_id=? AND key=?", (run_id, req.key))
    db.execute("INSERT INTO params VALUES (?,?,?)", (run_id, req.key, req.value))
    db.commit()
    return {"status": "ok"}


@app.post("/runs/{run_id}/finish")
def finish_run(run_id: str, success: bool = True):
    db = _db()
    status = "completed" if success else "failed"
    db.execute("UPDATE runs SET status=?, finished_at=? WHERE id=?", (status, _now(), run_id))
    db.commit()
    return {"run_id": run_id, "status": status}


@app.patch("/runs/{run_id}")
def update_run(run_id: str, req: RunUpdate):
    db = _db()
    if req.tags is not None:
        db.execute("UPDATE runs SET tags=? WHERE id=?", (json.dumps(req.tags), run_id))
    if req.notes is not None:
        db.execute("UPDATE runs SET notes=? WHERE id=?", (req.notes, run_id))
    if req.status is not None:
        db.execute("UPDATE runs SET status=? WHERE id=?", (req.status, run_id))
    db.commit()
    return get_run(run_id)


@app.get("/leaderboard")
def leaderboard(metric: str = "success_rate", limit: int = 20):
    db = _db()
    rows = db.execute(
        """
        SELECT r.id, r.name, r.experiment, r.status, m.value as metric_val
        FROM runs r
        JOIN (
          SELECT run_id, MAX(value) as value
          FROM metrics WHERE key=?
          GROUP BY run_id
        ) m ON r.id = m.run_id
        ORDER BY m.value DESC LIMIT ?
        """,
        (metric, limit),
    ).fetchall()
    result = [dict(r) for r in rows]
    # attach params
    for r in result:
        params = db.execute("SELECT key,value FROM params WHERE run_id=?", (r["id"],)).fetchall()
        r["params"] = {p["key"]: p["value"] for p in params}
    return result


@app.get("/compare", response_class=HTMLResponse)
def compare(run_ids: str = ""):
    ids = [x.strip() for x in run_ids.split(",") if x.strip()]
    if not ids:
        return HTMLResponse("<p>Pass ?run_ids=id1,id2</p>")
    runs = [get_run(rid) for rid in ids if _run_exists(rid)]
    if not runs:
        return HTMLResponse("<p>No valid run IDs</p>")

    # Collect all param/metric keys
    all_params = sorted({k for r in runs for k in r.get("params", {})})
    all_metrics = sorted({k for r in runs for k in r.get("metrics", {})})

    param_rows = ""
    for k in all_params:
        cells = "".join(f"<td>{r.get('params',{}).get(k,'—')}</td>" for r in runs)
        param_rows += f"<tr><td><b>{k}</b></td>{cells}</tr>"

    metric_rows = ""
    for k in all_metrics:
        cells = ""
        vals = [r.get("metrics", {}).get(k, {}).get("value") for r in runs]
        max_v = max((v for v in vals if v is not None), default=None)
        for v in vals:
            if v is None:
                cells += "<td>—</td>"
            elif v == max_v:
                cells += f"<td style='color:#10b981;font-weight:bold'>{v:.4f} ★</td>"
            else:
                cells += f"<td>{v:.4f}</td>"
        metric_rows += f"<tr><td><b>{k}</b></td>{cells}</tr>"

    headers = "".join(
        f"<th>{r['name']}<br><span style='font-weight:normal;font-size:.8em'>{r['status']}</span></th>"
        for r in runs
    )

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Run Comparison</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}
th{{background:#C74634;color:white;padding:8px 12px;text-align:left;font-size:.85em}}
td{{padding:7px 12px;border-bottom:1px solid #1e293b;font-size:.9em}}
tr:nth-child(even) td{{background:#172033}}
</style></head><body>
<h1>Run Comparison</h1>
<p style="color:#64748b">{len(runs)} runs · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<h2>Hyperparameters</h2>
<table><tr><th>Parameter</th>{headers}</tr>{param_rows or '<tr><td colspan="99" style="color:#475569">No params logged</td></tr>'}</table>
<h2>Metrics (best highlighted)</h2>
<table><tr><th>Metric</th>{headers}</tr>{metric_rows or '<tr><td colspan="99" style="color:#475569">No metrics logged</td></tr>'}</table>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def ui():
    runs = list_runs(limit=30)
    lb = leaderboard(limit=5)

    run_rows = ""
    for r in runs:
        sr = r.get("metrics", {}).get("success_rate", "—")
        if isinstance(sr, float):
            sr_str = f"{sr:.1%}"
            sr_color = "#10b981" if sr >= 0.3 else "#f59e0b" if sr >= 0.1 else "#ef4444"
        else:
            sr_str, sr_color = "—", "#64748b"
        loss = r.get("metrics", {}).get("train_loss", "—")
        loss_str = f"{loss:.4f}" if isinstance(loss, float) else "—"
        status_color = {"completed": "#10b981", "running": "#3b82f6", "failed": "#ef4444"}.get(r["status"], "#64748b")
        run_rows += (
            f"<tr><td><code>{r['id']}</code></td><td>{r['name']}</td>"
            f"<td>{r['experiment']}</td>"
            f"<td style='color:{sr_color}'>{sr_str}</td>"
            f"<td>{loss_str}</td>"
            f"<td style='color:{status_color}'>{r['status']}</td>"
            f"<td>{r['created_at'][:16]}</td>"
            f"<td><a href='/runs/{r['id']}' style='color:#3b82f6'>View</a></td></tr>"
        )

    lb_rows = ""
    for i, r in enumerate(lb):
        lb_rows += f"<tr><td>#{i+1}</td><td>{r['name']}</td><td>{r['metric_val']:.1%}</td></tr>"

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Experiment Tracker</title>
<meta http-equiv="refresh" content="15">
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #1e293b;padding-bottom:6px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}}
table{{width:100%;border-collapse:collapse;margin:8px 0}}
th{{background:#C74634;color:white;padding:7px 12px;text-align:left;font-size:.82em}}
td{{padding:6px 12px;border-bottom:1px solid #1e293b;font-size:.85em}}
tr:nth-child(even) td{{background:#172033}}
</style></head><body>
<h1>Experiment Tracker</h1>
<p style="color:#64748b">OCI Robot Cloud · GR00T Fine-tuning Runs · Auto-refresh: 15s</p>

<div class="grid">
  <div>
    <h2>Leaderboard (success_rate)</h2>
    <table><tr><th>Rank</th><th>Run</th><th>Success Rate</th></tr>
    {lb_rows or '<tr><td colspan="3" style="color:#475569">No completed runs</td></tr>'}
    </table>
  </div>
  <div>
    <h2>Quick Actions</h2>
    <p style="color:#64748b;font-size:.85em">
      POST /runs — create run<br>
      POST /runs/{{id}}/log_metric — track metrics<br>
      GET /leaderboard — best models<br>
      GET /compare?run_ids=a,b — side by side
    </p>
  </div>
</div>

<h2>All Runs ({len(runs)})</h2>
<table>
  <tr><th>ID</th><th>Name</th><th>Experiment</th><th>Success Rate</th><th>Loss</th><th>Status</th><th>Created</th><th></th></tr>
  {run_rows or '<tr><td colspan="8" style="color:#475569;text-align:center">No runs yet</td></tr>'}
</table>
<p style="color:#475569;font-size:.8em;margin-top:24px">OCI Robot Cloud · github.com/qianjun22/roboticsai</p>
</body></html>"""


def _run_exists(run_id: str) -> bool:
    db = _db()
    return db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is not None


def main():
    global _db_path
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8019)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()
    _db_path = Path(args.db)
    init_db(_db_path)
    print(f"[tracker] Experiment tracker on port {args.port}, db={_db_path}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
