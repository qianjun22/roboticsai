#!/usr/bin/env python3
"""
customer_success_dashboard.py — Customer success metrics and health scoring (port 8032).

Tracks design-partner outcomes: policy success rate trends, training cadence,
time-to-value, and churn risk signals. Gives the CS team a single view of
all partner health, NPS proxies, and escalation triggers.

Usage:
    python src/api/customer_success_dashboard.py --port 8032 --mock
    # → http://localhost:8032
"""

import json
import math
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/customer_success.db"

# ── Health scoring ────────────────────────────────────────────────────────────

# Weights for composite health score (0-100)
HEALTH_WEIGHTS = {
    "success_rate_trend": 0.35,    # positive trend in closed-loop success
    "training_cadence":   0.20,    # regularity of fine-tune jobs
    "api_activity":       0.15,    # API calls in last 14d
    "dagger_usage":       0.20,    # using DAgger (vs just BC)
    "time_to_value":      0.10,    # days to first successful eval
}

HEALTH_THRESHOLDS = {
    "healthy":    75,
    "at_risk":    50,
    "critical":   25,
}

PARTNER_STAGES = ["onboarding","active","power_user","at_risk","churned"]


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS partners (
            id TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT,
            stage TEXT DEFAULT 'onboarding',
            joined_at TEXT,
            csm TEXT DEFAULT 'Jun Qian',
            robot_type TEXT,
            target_success_rate REAL DEFAULT 0.50
        );
        CREATE TABLE IF NOT EXISTS success_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id TEXT,
            event_type TEXT,   -- eval / train / dagger / onboarding / support_ticket / milestone
            value REAL DEFAULT 0,  -- success_rate for eval, loss for train, 1/0 for milestones
            notes TEXT,
            created_at TEXT
        );
        """)


@contextmanager
def get_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def seed_mock_data(db_path: str = DB_PATH) -> None:
    init_db(db_path)
    rng = random.Random(2026)

    partners = [
        ("p_stretch", "Stretch Robotics",  "growth",     "active",      "Stretch RE2",  0.60),
        ("p_nimble",  "Nimble AI",          "enterprise", "power_user",  "Franka Panda", 0.75),
        ("p_auton",   "Auton Systems",      "starter",    "at_risk",     "UR5e",         0.40),
        ("p_grasp",   "GraspTech Labs",     "starter",    "onboarding",  "Custom Arm",   0.45),
        ("p_verity",  "Verity Robotics",    "growth",     "active",      "xArm7",        0.65),
    ]

    robots = {"Stretch RE2": "Stretch", "Franka Panda": "Franka", "UR5e": "UR5e",
              "Custom Arm": "Custom", "xArm7": "xArm7"}

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM partners")
        conn.execute("DELETE FROM success_events")

        for pid, name, tier, stage, robot, target in partners:
            joined = (datetime.now() - timedelta(days=rng.randint(14, 90))).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO partners VALUES (?,?,?,?,?,?,?,?)",
                (pid, name, tier, stage, joined, "Jun Qian", robot, target)
            )

        # Seed success events (90 days)
        for pid, name, tier, stage, robot, target in partners:
            base_success = target * rng.uniform(0.6, 1.1)
            for day_ago in range(90, 0, -2):
                ts = (datetime.now() - timedelta(days=day_ago)).isoformat()
                # Eval events
                if rng.random() < 0.3:
                    trend_bonus = (90 - day_ago) / 90.0 * 0.2
                    success = min(1.0, max(0.0, base_success + trend_bonus + rng.gauss(0, 0.05)))
                    conn.execute(
                        "INSERT INTO success_events (partner_id,event_type,value,notes,created_at) VALUES (?,?,?,?,?)",
                        (pid, "eval", success, f"checkpoint-{rng.randint(1000,9999)}", ts)
                    )
                # Train events
                if rng.random() < 0.2:
                    loss = 0.5 - trend_bonus * 2 + rng.gauss(0, 0.05)
                    conn.execute(
                        "INSERT INTO success_events (partner_id,event_type,value,notes,created_at) VALUES (?,?,?,?,?)",
                        (pid, "train", max(0.08, loss), f"{rng.randint(1000,5000)} steps", ts)
                    )
                # DAgger events
                if rng.random() < 0.1 and stage in ("active","power_user"):
                    conn.execute(
                        "INSERT INTO success_events (partner_id,event_type,value,notes,created_at) VALUES (?,?,?,?,?)",
                        (pid, "dagger", 1.0, f"iter {rng.randint(1,4)}", ts)
                    )


# ── Health scoring ────────────────────────────────────────────────────────────

def compute_health_score(partner_id: str, db_path: str = DB_PATH) -> dict:
    """Compute composite health score (0-100) for a partner."""
    cutoff_14d = (datetime.now() - timedelta(days=14)).isoformat()
    cutoff_30d = (datetime.now() - timedelta(days=30)).isoformat()

    with get_db(db_path) as conn:
        # Recent eval events
        evals = conn.execute(
            "SELECT value, created_at FROM success_events "
            "WHERE partner_id=? AND event_type='eval' ORDER BY created_at DESC LIMIT 10",
            (partner_id,)
        ).fetchall()

        # Training cadence (jobs in last 30d)
        n_trains = conn.execute(
            "SELECT COUNT(*) FROM success_events "
            "WHERE partner_id=? AND event_type='train' AND created_at>=?",
            (partner_id, cutoff_30d)
        ).fetchone()[0]

        # API activity (any event in last 14d)
        n_recent = conn.execute(
            "SELECT COUNT(*) FROM success_events "
            "WHERE partner_id=? AND created_at>=?",
            (partner_id, cutoff_14d)
        ).fetchone()[0]

        # DAgger usage
        n_dagger = conn.execute(
            "SELECT COUNT(*) FROM success_events "
            "WHERE partner_id=? AND event_type='dagger'",
            (partner_id,)
        ).fetchone()[0]

        # Partner info
        p = conn.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()

    # Score components
    scores = {}

    # Success rate trend (recent avg vs 30d ago avg)
    if len(evals) >= 2:
        recent_rates = [e["value"] for e in evals[:3]]
        older_rates  = [e["value"] for e in evals[3:6]] if len(evals) >= 6 else recent_rates
        trend = (sum(recent_rates) / len(recent_rates)) - (sum(older_rates) / len(older_rates))
        scores["success_rate_trend"] = min(100, max(0, 50 + trend * 200))
    else:
        scores["success_rate_trend"] = 30.0

    # Training cadence (target: 4+ jobs / 30d)
    scores["training_cadence"] = min(100, (n_trains / 4.0) * 100)

    # API activity (any activity in 14d = 100, 0 = 0)
    scores["api_activity"] = min(100, n_recent * 10)

    # DAgger usage (0 = 0, 1+ iters = 60, 3+ iters = 100)
    scores["dagger_usage"] = min(100, n_dagger / 3.0 * 100)

    # Time to value: using joined_at + first eval > 50%
    scores["time_to_value"] = 70.0  # default

    # Composite
    composite = sum(scores[k] * HEALTH_WEIGHTS[k] for k in HEALTH_WEIGHTS)

    status = "healthy" if composite >= HEALTH_THRESHOLDS["healthy"] else \
             "at_risk" if composite >= HEALTH_THRESHOLDS["at_risk"] else "critical"

    latest_rate = evals[0]["value"] if evals else 0.0
    target = p["target_success_rate"] if p else 0.50

    return {
        "partner_id": partner_id,
        "composite_score": round(composite, 1),
        "status": status,
        "component_scores": {k: round(v, 1) for k, v in scores.items()},
        "latest_success_rate": round(latest_rate, 3),
        "target_success_rate": target,
        "on_track": latest_rate >= target * 0.8,
        "n_trains_30d": n_trains,
        "n_dagger_iters": n_dagger,
        "recent_activity_14d": n_recent,
    }


def all_partner_health(db_path: str = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        partners = [dict(r) for r in conn.execute("SELECT * FROM partners").fetchall()]
    return [compute_health_score(p["id"], db_path) | p for p in partners]


# ── HTML dashboard ────────────────────────────────────────────────────────────

def render_dashboard(db_path: str = DB_PATH) -> str:
    health_data = all_partner_health(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    n_healthy  = sum(1 for h in health_data if h["status"] == "healthy")
    n_at_risk  = sum(1 for h in health_data if h["status"] == "at_risk")
    n_critical = sum(1 for h in health_data if h["status"] == "critical")

    def status_color(status: str) -> str:
        return {"healthy":"#22c55e","at_risk":"#f59e0b","critical":"#ef4444"}.get(status,"#94a3b8")

    rows = ""
    for h in sorted(health_data, key=lambda x: x["composite_score"]):
        sc = status_color(h["status"])
        on_track = "✅" if h.get("on_track") else "⚠️"
        bar_w = int(h["composite_score"] * 1.0)
        rows += f"""<tr onclick="window.location='/partner/{h['partner_id']}'" style="cursor:pointer">
          <td style="padding:10px 12px;font-weight:600">{h.get('name','?')}</td>
          <td style="padding:10px 12px">
            <span style="color:{sc};background:{sc}22;padding:2px 8px;border-radius:10px;font-size:11px">{h['status']}</span>
          </td>
          <td style="padding:10px 12px">
            <div style="display:inline-flex;align-items:center;gap:6px">
              <div style="background:#334155;width:100px;height:8px;border-radius:4px">
                <div style="background:{sc};width:{bar_w}px;height:100%;border-radius:4px"></div>
              </div>
              <span style="font-size:13px;font-weight:600">{h['composite_score']:.0f}</span>
            </div>
          </td>
          <td style="padding:10px 12px">{h['latest_success_rate']:.0%}</td>
          <td style="padding:10px 12px;color:#64748b">{h['target_success_rate']:.0%}</td>
          <td style="padding:10px 12px;text-align:center">{on_track}</td>
          <td style="padding:10px 12px">{h['n_trains_30d']} jobs</td>
          <td style="padding:10px 12px">{h['n_dagger_iters']} iters</td>
          <td style="padding:10px 12px;color:#64748b;font-size:12px">{h.get('tier','?')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>Customer Success Dashboard</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
  tr:hover td{{background:#243249}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 14px;margin:4px;text-align:center}}
</style>
</head>
<body>
<h1>Customer Success Dashboard</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 16px">{now} · auto-refresh 60s · OCI Robot Cloud</p>

<div class="card">
  <div class="m"><div style="font-size:24px;font-weight:700;color:#22c55e">{n_healthy}</div><div style="font-size:11px;color:#64748b">Healthy</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#f59e0b">{n_at_risk}</div><div style="font-size:11px;color:#64748b">At Risk</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#ef4444">{n_critical}</div><div style="font-size:11px;color:#64748b">Critical</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#3b82f6">{len(health_data)}</div><div style="font-size:11px;color:#64748b">Total Partners</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#94a3b8">{sum(h['n_dagger_iters'] for h in health_data)}</div><div style="font-size:11px;color:#64748b">DAgger Iters</div></div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Partner Health</h3>
  <table>
    <tr>
      <th>Partner</th><th>Status</th><th>Health Score</th>
      <th>Success Rate</th><th>Target</th><th>On Track</th>
      <th>Training/30d</th><th>DAgger</th><th>Tier</th>
    </tr>
    {rows}
  </table>
</div>

<div style="color:#475569;font-size:11px">
  <a href="/api/health" style="color:#3b82f6">/api/health</a> · OCI Robot Cloud
</div>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH) -> "FastAPI":
    app = FastAPI(title="Customer Success Dashboard", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        seed_mock_data(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return render_dashboard(db_path)

    @app.get("/api/health")
    async def api_health():
        return all_partner_health(db_path)

    @app.get("/api/health/{partner_id}")
    async def api_partner_health(partner_id: str):
        return compute_health_score(partner_id, db_path)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "customer_success_dashboard", "port": 8032}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Customer success dashboard (port 8032)")
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(args.db)
    print(f"Customer Success Dashboard → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
