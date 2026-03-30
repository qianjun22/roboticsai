#!/usr/bin/env python3
"""
model_monitoring.py — Production model monitoring service for deployed GR00T checkpoints.

Watches checkpoints for performance degradation and triggers alerts.
Like "MLflow + Datadog" for robot policies.

Usage:
    python src/api/model_monitoring.py [--port 8043] [--host 0.0.0.0] [--mock]

Endpoints:
    GET  /                              Dark-theme HTML dashboard
    POST /api/ingest                    Ingest a metric sample
    POST /api/alerts/{alert_id}/acknowledge  Acknowledge an alert
    GET  /api/alerts                    List alerts (?active_only=true)
    GET  /api/metrics/{checkpoint_id}   Time series data (?days=7)
    GET  /health                        Health check
"""

import argparse
import json
import random
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional

DB_PATH = "/tmp/model_monitoring.db"

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MonitoringAlert:
    alert_id: str
    severity: str          # "critical" / "warning" / "info"
    metric: str
    threshold: float
    current_value: float
    message: str
    triggered_at: str      # ISO-8601
    acknowledged: bool


@dataclass
class ModelMetricSample:
    checkpoint_id: str
    timestamp: str         # ISO-8601
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    n_episodes: int
    source: str            # "live" / "eval" / "synthetic"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_samples (
                checkpoint_id TEXT,
                timestamp     TEXT,
                success_rate  REAL,
                avg_latency_ms REAL,
                p95_latency_ms REAL,
                n_episodes    INTEGER,
                source        TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id      TEXT PRIMARY KEY,
                severity      TEXT,
                metric        TEXT,
                threshold     REAL,
                current_value REAL,
                message       TEXT,
                triggered_at  TEXT,
                acknowledged  INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thresholds (
                checkpoint_id        TEXT,
                metric               TEXT,
                warning_threshold    REAL,
                critical_threshold   REAL,
                PRIMARY KEY (checkpoint_id, metric)
            )
        """)
        conn.commit()


def insert_sample(sample: ModelMetricSample):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO metric_samples VALUES (?,?,?,?,?,?,?)",
            (sample.checkpoint_id, sample.timestamp, sample.success_rate,
             sample.avg_latency_ms, sample.p95_latency_ms, sample.n_episodes,
             sample.source)
        )
        conn.commit()


def insert_alert(alert: MonitoringAlert):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO alerts VALUES (?,?,?,?,?,?,?,?)",
            (alert.alert_id, alert.severity, alert.metric, alert.threshold,
             alert.current_value, alert.message, alert.triggered_at,
             1 if alert.acknowledged else 0)
        )
        conn.commit()


def get_moving_avg(checkpoint_id: str, metric: str, days: int = 7) -> Optional[float]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT AVG({metric}) FROM metric_samples WHERE checkpoint_id=? AND timestamp>=?",
            (checkpoint_id, cutoff)
        ).fetchone()
    return row[0] if row and row[0] is not None else None


# ---------------------------------------------------------------------------
# Threshold checking
# ---------------------------------------------------------------------------

def check_thresholds(checkpoint_id: str, sample: ModelMetricSample) -> List[MonitoringAlert]:
    alerts: List[MonitoringAlert] = []
    now = datetime.utcnow().isoformat()

    def make_alert(severity, metric, threshold, current_value, message):
        return MonitoringAlert(
            alert_id=str(uuid.uuid4()),
            severity=severity,
            metric=metric,
            threshold=threshold,
            current_value=current_value,
            message=message,
            triggered_at=now,
            acknowledged=False,
        )

    # Success rate absolute thresholds
    sr = sample.success_rate
    if sr < 0.30:
        alerts.append(make_alert("critical", "success_rate", 0.30, sr,
                                 f"[{checkpoint_id}] Success rate critically low: {sr:.1%}"))
    elif sr < 0.50:
        alerts.append(make_alert("warning", "success_rate", 0.50, sr,
                                 f"[{checkpoint_id}] Success rate below target: {sr:.1%}"))

    # Latency thresholds
    lat = sample.avg_latency_ms
    if lat > 350:
        alerts.append(make_alert("critical", "avg_latency_ms", 350, lat,
                                 f"[{checkpoint_id}] Inference latency critical: {lat:.0f}ms"))
    elif lat > 280:
        alerts.append(make_alert("warning", "avg_latency_ms", 280, lat,
                                 f"[{checkpoint_id}] Inference latency elevated: {lat:.0f}ms"))

    # Regression vs 7-day moving average
    moving_avg = get_moving_avg(checkpoint_id, "success_rate", days=7)
    if moving_avg is not None:
        drop_pp = moving_avg - sr
        if drop_pp > 0.10:
            alerts.append(make_alert("critical", "success_rate_regression", moving_avg, sr,
                                     f"[{checkpoint_id}] Performance regression detected: "
                                     f"{drop_pp:.1%} drop from 7-day avg ({moving_avg:.1%})"))

    return alerts


# ---------------------------------------------------------------------------
# Mock data seeding
# ---------------------------------------------------------------------------

CHECKPOINTS = ["ckpt-v1.0", "ckpt-v1.1", "ckpt-v2.0"]


def seed_mock_data():
    """Seed 30 days of metric samples for 3 checkpoints with 2 degradation events."""
    rng = random.Random(42)
    now = datetime.utcnow()

    for ckpt in CHECKPOINTS:
        base_sr = rng.uniform(0.70, 0.85)
        base_lat = rng.uniform(200, 240)

        for day_offset in range(30, 0, -1):
            ts = (now - timedelta(days=day_offset, hours=rng.uniform(0, 23))).isoformat()

            sr = min(1.0, max(0.0, base_sr + rng.gauss(0, 0.03)))
            lat = max(100, base_lat + rng.gauss(0, 10))
            p95 = lat * rng.uniform(1.2, 1.5)
            n_ep = rng.randint(15, 25)

            # Degradation event 1: latency spike for ckpt-v1.0 around day 5 ago
            if ckpt == "ckpt-v1.0" and 4 <= day_offset <= 6:
                lat = rng.uniform(310, 370)   # triggers warning/critical
                p95 = lat * 1.4

            # Degradation event 2: success rate drop for ckpt-v1.1 around day 3 ago
            if ckpt == "ckpt-v1.1" and 2 <= day_offset <= 4:
                sr = rng.uniform(0.20, 0.35)  # triggers critical + regression

            sample = ModelMetricSample(
                checkpoint_id=ckpt,
                timestamp=ts,
                success_rate=sr,
                avg_latency_ms=lat,
                p95_latency_ms=p95,
                n_episodes=n_ep,
                source="synthetic",
            )
            insert_sample(sample)
            triggered = check_thresholds(ckpt, sample)
            for alert in triggered:
                insert_alert(alert)


def _maybe_seed():
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM metric_samples").fetchone()[0]
    if count == 0:
        seed_mock_data()


# ---------------------------------------------------------------------------
# Background simulation
# ---------------------------------------------------------------------------

def simulate_monitoring(state: dict, rng: random.Random):
    """Background thread: add a new sample every 10 seconds."""
    while state.get("running", True):
        time.sleep(10)
        ckpt = rng.choice(CHECKPOINTS)
        sr = min(1.0, max(0.0, rng.uniform(0.55, 0.90)))
        lat = max(100, rng.gauss(230, 20))
        p95 = lat * rng.uniform(1.2, 1.5)
        n_ep = rng.randint(10, 30)
        sample = ModelMetricSample(
            checkpoint_id=ckpt,
            timestamp=datetime.utcnow().isoformat(),
            success_rate=sr,
            avg_latency_ms=lat,
            p95_latency_ms=p95,
            n_episodes=n_ep,
            source="live",
        )
        insert_sample(sample)
        for alert in check_thresholds(ckpt, sample):
            insert_alert(alert)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def build_sparkline_svg(values: list, width=120, height=40, color="#22d3ee") -> str:
    if not values or len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    pts = []
    for i, v in enumerate(values):
        x = int(i / (len(values) - 1) * width)
        y = int((1 - (v - mn) / rng) * (height - 4)) + 2
        pts.append(f"{x},{y}")
    path = " ".join(pts)
    return (f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.5"/>'
            f'</svg>')


def build_dashboard_html() -> str:
    with get_conn() as conn:
        active_alerts = conn.execute(
            "SELECT * FROM alerts WHERE acknowledged=0 ORDER BY triggered_at DESC"
        ).fetchall()
        all_alerts = conn.execute(
            "SELECT * FROM alerts ORDER BY triggered_at DESC LIMIT 20"
        ).fetchall()

    checkpoint_sections = ""
    for ckpt in CHECKPOINTS:
        cutoff = (datetime.utcnow() - timedelta(days=14)).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT success_rate, avg_latency_ms, n_episodes FROM metric_samples "
                "WHERE checkpoint_id=? AND timestamp>=? ORDER BY timestamp",
                (ckpt, cutoff)
            ).fetchall()
        sr_vals = [r["success_rate"] for r in rows]
        lat_vals = [r["avg_latency_ms"] for r in rows]
        ep_vals = [r["n_episodes"] for r in rows]
        last_sr = f"{sr_vals[-1]:.1%}" if sr_vals else "—"
        last_lat = f"{lat_vals[-1]:.0f}ms" if lat_vals else "—"
        svg_sr = build_sparkline_svg(sr_vals, color="#22d3ee")
        svg_lat = build_sparkline_svg(lat_vals, color="#fb923c")
        svg_ep = build_sparkline_svg(ep_vals, color="#a78bfa")
        checkpoint_sections += f"""
        <div class="card">
          <div class="card-title">{ckpt}</div>
          <div class="metrics-row">
            <div class="metric"><div class="metric-label">Success Rate</div>
              {svg_sr}<div class="metric-value">{last_sr}</div></div>
            <div class="metric"><div class="metric-label">Avg Latency</div>
              {svg_lat}<div class="metric-value">{last_lat}</div></div>
            <div class="metric"><div class="metric-label">Episodes</div>
              {svg_ep}</div>
          </div>
        </div>"""

    def severity_badge(sev):
        colors = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#22d3ee"}
        c = colors.get(sev, "#6b7280")
        return f'<span style="background:{c};color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{sev.upper()}</span>'

    active_rows = ""
    for a in active_alerts:
        ts = a["triggered_at"][:16].replace("T", " ")
        active_rows += f"""<tr>
          <td>{severity_badge(a["severity"])}</td>
          <td>{a["checkpoint_id"] if "checkpoint_id" in a.keys() else a["metric"]}</td>
          <td style="max-width:340px">{a["message"]}</td>
          <td>{ts}</td>
          <td><button onclick="ack('{a["alert_id"]}')" class="btn-ack">ACK</button></td>
        </tr>"""
    if not active_rows:
        active_rows = '<tr><td colspan="5" style="text-align:center;color:#6b7280">No active alerts</td></tr>'

    history_rows = ""
    for a in all_alerts:
        ts = a["triggered_at"][:16].replace("T", " ")
        ack = "✓" if a["acknowledged"] else ""
        history_rows += f"""<tr style="opacity:{'0.5' if a['acknowledged'] else '1'}">
          <td>{severity_badge(a["severity"])}</td>
          <td style="max-width:360px;font-size:12px">{a["message"]}</td>
          <td>{ts}</td>
          <td style="color:#22d3ee">{ack}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>OCI Robot Cloud — Model Monitoring</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}
  h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .section-title{{font-size:15px;font-weight:600;color:#94a3b8;margin:24px 0 12px}}
  .cards{{display:flex;gap:16px;flex-wrap:wrap}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;min-width:320px}}
  .card-title{{font-weight:700;font-size:14px;color:#f8fafc;margin-bottom:12px}}
  .metrics-row{{display:flex;gap:18px}}
  .metric{{display:flex;flex-direction:column;gap:4px}}
  .metric-label{{font-size:11px;color:#94a3b8}}
  .metric-value{{font-size:13px;font-weight:600;color:#f1f5f9}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;color:#94a3b8;font-size:12px;font-weight:600;padding:10px 12px;text-align:left}}
  td{{padding:10px 12px;font-size:13px;border-bottom:1px solid #1e293b}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#253347}}
  .btn-ack{{background:#22d3ee;color:#0f172a;border:none;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:700}}
  .btn-ack:hover{{background:#06b6d4}}
  .tag{{background:#1e3a5f;color:#93c5fd;padding:2px 8px;border-radius:4px;font-size:11px}}
</style>
</head><body>
<h1>OCI Robot Cloud — Model Monitoring</h1>
<div class="subtitle">GR00T checkpoint health · port 8043 · refreshes every 30s</div>

<div class="section-title">Checkpoint Metrics (14-day sparklines)</div>
<div class="cards">{checkpoint_sections}</div>

<div class="section-title">Active Alerts ({len(active_alerts)})</div>
<table>
  <tr><th>Severity</th><th>Checkpoint</th><th>Message</th><th>Time (UTC)</th><th></th></tr>
  {active_rows}
</table>

<div class="section-title">Alert History (last 20)</div>
<table>
  <tr><th>Severity</th><th>Message</th><th>Time (UTC)</th><th>ACK</th></tr>
  {history_rows}
</table>

<script>
async function ack(id) {{
  await fetch('/api/alerts/' + id + '/acknowledge', {{method:'POST'}});
  location.reload();
}}
setTimeout(() => location.reload(), 30000);
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Model Monitoring", version="1.0.0")

    class IngestRequest(BaseModel):
        checkpoint_id: str
        success_rate: float
        avg_latency_ms: float
        n_episodes: int
        p95_latency_ms: float = 0.0
        source: str = "live"

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_dashboard_html()

    @app.post("/api/ingest")
    def ingest(req: IngestRequest):
        sample = ModelMetricSample(
            checkpoint_id=req.checkpoint_id,
            timestamp=datetime.utcnow().isoformat(),
            success_rate=req.success_rate,
            avg_latency_ms=req.avg_latency_ms,
            p95_latency_ms=req.p95_latency_ms or req.avg_latency_ms * 1.3,
            n_episodes=req.n_episodes,
            source=req.source,
        )
        insert_sample(sample)
        alerts = check_thresholds(req.checkpoint_id, sample)
        for a in alerts:
            insert_alert(a)
        return {"stored": True, "alerts_triggered": len(alerts),
                "alerts": [asdict(a) for a in alerts]}

    @app.post("/api/alerts/{alert_id}/acknowledge")
    def acknowledge_alert(alert_id: str):
        with get_conn() as conn:
            result = conn.execute(
                "UPDATE alerts SET acknowledged=1 WHERE alert_id=?", (alert_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Alert not found")
        return {"acknowledged": True, "alert_id": alert_id}

    @app.get("/api/alerts")
    def list_alerts(active_only: bool = Query(False)):
        with get_conn() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM alerts WHERE acknowledged=0 ORDER BY triggered_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alerts ORDER BY triggered_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/metrics/{checkpoint_id}")
    def get_metrics(checkpoint_id: str, days: int = Query(7)):
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM metric_samples WHERE checkpoint_id=? AND timestamp>=? "
                "ORDER BY timestamp",
                (checkpoint_id, cutoff)
            ).fetchall()
        return {"checkpoint_id": checkpoint_id, "days": days,
                "samples": [dict(r) for r in rows]}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "model_monitoring", "port": 8043}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Model Monitoring Service")
    parser.add_argument("--port", type=int, default=8043)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Seed mock data on startup (default: True)")
    args = parser.parse_args()

    print(f"[model_monitoring] Initializing DB at {DB_PATH}")
    init_db()

    if args.mock:
        print("[model_monitoring] Seeding mock data (30 days, 3 checkpoints, 2 degradation events)...")
        _maybe_seed()

    sim_state = {"running": True}
    sim_rng = random.Random()
    sim_thread = threading.Thread(
        target=simulate_monitoring, args=(sim_state, sim_rng), daemon=True
    )
    sim_thread.start()
    print("[model_monitoring] Background simulation thread started (new sample every 10s)")

    if not HAS_FASTAPI:
        print("[model_monitoring] FastAPI not installed. Install with: pip install fastapi uvicorn")
        print("[model_monitoring] Simulation running. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            sim_state["running"] = False
        return

    print(f"[model_monitoring] Starting server on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
