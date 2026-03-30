#!/usr/bin/env python3
"""
telemetry_collector.py — Lightweight telemetry aggregator for OCI Robot Cloud (port 8045).

Collects structured telemetry events from all services and provides a unified
query interface. Events flow in from: training jobs, eval runs, DAgger iters,
API calls, and system health. Powers anomaly detection and usage analytics.

Usage:
    python src/api/telemetry_collector.py --port 8045 --mock
    # → http://localhost:8045
"""

import json
import random
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/telemetry.db"

# ── Event schema ──────────────────────────────────────────────────────────────

EVENT_TYPES = {
    "training.started":    "Training job began",
    "training.completed":  "Training job finished",
    "training.failed":     "Training job failed",
    "eval.started":        "Eval run began",
    "eval.completed":      "Eval completed with results",
    "dagger.iter_done":    "DAgger iteration completed",
    "server.started":      "GR00T server started",
    "server.crashed":      "GR00T server crashed",
    "infer.request":       "Inference request handled",
    "infer.timeout":       "Inference request timed out",
    "checkpoint.promoted": "Checkpoint promoted to production",
    "partner.upload":      "Partner uploaded demo data",
    "alert.triggered":     "Monitoring alert triggered",
    "system.oom":          "Out-of-memory event",
}


@dataclass
class TelemetryEvent:
    event_id: str
    event_type: str
    service: str
    partner_id: str
    timestamp: str
    payload: str          # JSON string
    severity: str         # "info" / "warning" / "error"
    duration_ms: float    # for timed events, 0 otherwise


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            event_id    TEXT PRIMARY KEY,
            event_type  TEXT,
            service     TEXT,
            partner_id  TEXT,
            timestamp   TEXT,
            payload     TEXT,
            severity    TEXT,
            duration_ms REAL
        );
        CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_ts   ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_svc  ON events(service);
        """)


@contextmanager
def get_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def ingest_event(evt: TelemetryEvent, db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)",
            (evt.event_id, evt.event_type, evt.service, evt.partner_id,
             evt.timestamp, evt.payload, evt.severity, evt.duration_ms)
        )


def seed_mock_events(db_path: str = DB_PATH, n_days: int = 7) -> None:
    rng = random.Random(55)
    services = ["training_monitor", "groot_franka_server", "dagger_train",
                "closed_loop_eval", "data_collection_api", "continuous_learning"]
    partners = ["stretch", "nimble", "auton", "grasptech", "verity"]

    event_templates = [
        ("training.started",    "info",    0,     "training_monitor"),
        ("training.completed",  "info",    3600,  "training_monitor"),
        ("eval.completed",      "info",    120,   "closed_loop_eval"),
        ("dagger.iter_done",    "info",    180,   "dagger_train"),
        ("infer.request",       "info",    0.23,  "groot_franka_server"),
        ("server.started",      "info",    0,     "groot_franka_server"),
        ("partner.upload",      "info",    0,     "data_collection_api"),
        ("checkpoint.promoted", "info",    0,     "continuous_learning"),
        ("infer.timeout",       "warning", 0.32,  "groot_franka_server"),
        ("system.oom",          "error",   0,     "training_monitor"),
        ("alert.triggered",     "warning", 0,     "model_monitoring"),
    ]

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM events")
        evt_i = 0
        for day in range(n_days):
            base_ts = datetime.now() - timedelta(days=n_days - day)
            n_events = rng.randint(20, 60)
            for _ in range(n_events):
                et, sev, dur, svc = rng.choice(event_templates)
                ts = base_ts + timedelta(
                    hours=rng.randint(0, 23),
                    minutes=rng.randint(0, 59),
                    seconds=rng.randint(0, 59)
                )
                pid = rng.choice(partners)
                payload = json.dumps({"partner": pid, "step": rng.randint(100, 5000)})
                conn.execute(
                    "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)",
                    (f"evt_{evt_i:06d}", et, svc, pid,
                     ts.isoformat(), payload, sev,
                     dur + rng.gauss(0, dur * 0.1) if dur > 0 else 0.0)
                )
                evt_i += 1


# ── Query helpers ─────────────────────────────────────────────────────────────

def query_events(event_type: Optional[str] = None,
                 service: Optional[str] = None,
                 partner_id: Optional[str] = None,
                 since_hours: int = 24,
                 limit: int = 100,
                 db_path: str = DB_PATH) -> list[dict]:
    since = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    conditions = ["timestamp >= ?"]
    params: list = [since]
    if event_type:
        conditions.append("event_type=?")
        params.append(event_type)
    if service:
        conditions.append("service=?")
        params.append(service)
    if partner_id:
        conditions.append("partner_id=?")
        params.append(partner_id)
    where = " AND ".join(conditions)
    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM events WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit]
        ).fetchall()
    return [dict(r) for r in rows]


def event_counts(since_hours: int = 24, db_path: str = DB_PATH) -> dict:
    since = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT event_type, severity, COUNT(*) as n FROM events WHERE timestamp>=? GROUP BY event_type, severity",
            (since,)
        ).fetchall()
    counts = {}
    for r in rows:
        counts[f"{r['event_type']}.{r['severity']}"] = r["n"]
    return counts


def hourly_volume(since_hours: int = 24, db_path: str = DB_PATH) -> list[dict]:
    """Events per hour for sparkline."""
    since = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT substr(timestamp,1,13) as hour, COUNT(*) as n FROM events WHERE timestamp>=? GROUP BY hour ORDER BY hour",
            (since,)
        ).fetchall()
    return [{"hour": r["hour"], "n": r["n"]} for r in rows]


# ── HTML dashboard ─────────────────────────────────────────────────────────────

def render_dashboard(db_path: str = DB_PATH) -> str:
    counts = event_counts(168, db_path)  # 7 days
    recent = query_events(since_hours=1, limit=25, db_path=db_path)
    errors = query_events(since_hours=24, db_path=db_path)
    n_errors = sum(1 for e in errors if e["severity"] == "error")
    n_warnings = sum(1 for e in errors if e["severity"] == "warning")
    n_total_24h = len(errors)

    vol = hourly_volume(24, db_path)
    max_vol = max((h["n"] for h in vol), default=1)
    sparkline_pts = " ".join(
        f"{i * 10},{30 - h['n'] / max_vol * 26}"
        for i, h in enumerate(vol[-24:])
    )

    event_rows = ""
    for e in recent:
        sev_color = {"error": "#ef4444", "warning": "#f59e0b", "info": "#64748b"}.get(e["severity"], "#94a3b8")
        event_rows += f"""<tr>
          <td style="padding:6px 10px;font-size:11px;color:#475569;font-family:monospace">{e['timestamp'][11:19]}</td>
          <td style="padding:6px 10px;font-size:12px;font-family:monospace">{e['event_type']}</td>
          <td style="padding:6px 10px;font-size:12px;color:#94a3b8">{e['service']}</td>
          <td style="padding:6px 10px;font-size:12px;color:#6366f1">{e['partner_id']}</td>
          <td style="padding:6px 10px"><span style="color:{sev_color};font-size:11px;font-weight:600">{e['severity']}</span></td>
        </tr>"""

    # Top event types (7 days)
    type_counts = {}
    for k, v in counts.items():
        et = k.rsplit(".", 1)[0]
        type_counts[et] = type_counts.get(et, 0) + v
    top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:6]
    top_rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e293b">'
        f'<span style="font-size:12px;font-family:monospace">{et}</span>'
        f'<span style="font-size:12px;font-weight:700;color:#3b82f6">{n}</span></div>'
        for et, n in top_types
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta http-equiv="refresh" content="30"><title>Telemetry Collector</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px;margin-bottom:14px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:6px 10px;text-align:left;border-bottom:1px solid #334155}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:9px 14px;margin:3px;text-align:center}}
</style>
</head>
<body>
<h1>Telemetry Collector</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 14px">All services · {datetime.now().strftime('%H:%M:%S')} · auto-refresh 30s</p>

<div class="card">
  <div class="m"><div style="font-size:22px;font-weight:700;color:#3b82f6">{n_total_24h}</div><div style="font-size:11px;color:#64748b">Events (24h)</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#ef4444">{n_errors}</div><div style="font-size:11px;color:#64748b">Errors (24h)</div></div>
  <div class="m"><div style="font-size:22px;font-weight:700;color:#f59e0b">{n_warnings}</div><div style="font-size:11px;color:#64748b">Warnings (24h)</div></div>
  <div style="display:inline-block;vertical-align:middle;margin-left:16px">
    <svg width="{len(vol)*10}" height="30" style="background:#0f172a;border-radius:4px">
      <polyline points="{sparkline_pts}" fill="none" stroke="#3b82f6" stroke-width="2"/>
    </svg>
    <div style="font-size:10px;color:#475569">event volume (24h)</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1.5fr;gap:14px">
  <div class="card">
    <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:10px">Top Event Types (7d)</div>
    {top_rows}
  </div>
  <div class="card">
    <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:8px">Recent Events (last 1h)</div>
    <table>
      <tr><th>Time</th><th>Type</th><th>Service</th><th>Partner</th><th>Severity</th></tr>
      {event_rows}
    </table>
  </div>
</div>

<div style="color:#334155;font-size:11px;margin-top:8px">
  <a href="/api/events?limit=100" style="color:#3b82f6">/api/events</a> ·
  <a href="/api/counts" style="color:#3b82f6">/api/counts</a> ·
  <a href="/health" style="color:#3b82f6">/health</a>
</div>
</body>
</html>"""


# ── FastAPI app ────────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH, mock: bool = True) -> "FastAPI":
    app = FastAPI(title="Telemetry Collector", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        if mock:
            seed_mock_events(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return render_dashboard(db_path)

    @app.post("/api/ingest")
    async def ingest(body: dict):
        import uuid
        evt = TelemetryEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=body.get("event_type", "unknown"),
            service=body.get("service", "unknown"),
            partner_id=body.get("partner_id", ""),
            timestamp=datetime.now().isoformat(),
            payload=json.dumps(body.get("payload", {})),
            severity=body.get("severity", "info"),
            duration_ms=float(body.get("duration_ms", 0)),
        )
        ingest_event(evt, db_path)
        return {"event_id": evt.event_id, "status": "ingested"}

    @app.get("/api/events")
    async def api_events(
        event_type: Optional[str] = None,
        service: Optional[str] = None,
        partner_id: Optional[str] = None,
        since_hours: int = 24,
        limit: int = 100,
    ):
        return query_events(event_type, service, partner_id, since_hours, limit, db_path)

    @app.get("/api/counts")
    async def api_counts(since_hours: int = 24):
        return event_counts(since_hours, db_path)

    @app.get("/api/volume")
    async def api_volume(since_hours: int = 24):
        return hourly_volume(since_hours, db_path)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "telemetry_collector", "port": 8045}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Telemetry collector (port 8045)")
    parser.add_argument("--port", type=int, default=8045)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(db_path=args.db, mock=args.mock)
    print(f"Telemetry Collector → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
