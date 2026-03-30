#!/usr/bin/env python3
"""
partner_usage_analytics.py — Per-partner usage tracking and analytics API (port 8027).

Aggregates GPU hours, episodes, API calls, and training jobs per design partner.
Provides drill-down dashboards and a REST API for billing integration.

Usage:
    python src/api/partner_usage_analytics.py --port 8027 --mock
    # → http://localhost:8027  (dashboard)
    # → http://localhost:8027/api/partners        (all partners summary)
    # → http://localhost:8027/api/partners/{id}   (partner detail)
    # → http://localhost:8027/api/export/{id}?format=csv  (export)
"""

import json
import math
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse, Response
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH  = "/tmp/partner_usage.db"
GPU_COST = 4.20   # OCI A100 $/hr

# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS partners (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT DEFAULT 'starter',
            joined_at TEXT,
            contact_email TEXT
        );
        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id TEXT NOT NULL,
            event_type TEXT NOT NULL,   -- train_job / eval_job / api_call / demo_upload / dagger_iter
            gpu_minutes REAL DEFAULT 0,
            n_episodes INTEGER DEFAULT 0,
            n_steps INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
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


# ── Mock data seed ────────────────────────────────────────────────────────────

def seed_mock_data(db_path: str = DB_PATH) -> None:
    init_db(db_path)
    rng = random.Random(2026)

    partners = [
        ("p_stretch", "Stretch Robotics",  "growth",     "stretch@example.com"),
        ("p_nimble",  "Nimble AI",          "enterprise", "nimble@example.com"),
        ("p_auton",   "Auton Systems",      "starter",    "auton@example.com"),
        ("p_grasp",   "GraspTech Labs",     "starter",    "grasp@example.com"),
        ("p_verity",  "Verity Robotics",    "growth",     "verity@example.com"),
    ]

    event_types = ["train_job", "eval_job", "api_call", "demo_upload", "dagger_iter"]
    tier_gpu_scale = {"starter": 0.5, "growth": 2.0, "enterprise": 5.0}

    with sqlite3.connect(db_path) as conn:
        # Clear and re-seed
        conn.execute("DELETE FROM partners")
        conn.execute("DELETE FROM usage_events")

        for pid, name, tier, email in partners:
            joined = (datetime.now() - timedelta(days=rng.randint(10, 60))).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO partners VALUES (?,?,?,?,?)",
                (pid, name, tier, joined, email)
            )

        # Generate 90 days of events
        for pid, name, tier, _ in partners:
            scale = tier_gpu_scale[tier]
            n_events = int(rng.gauss(60, 10) * scale)
            for _ in range(max(10, n_events)):
                evt = rng.choice(event_types)
                days_ago = rng.expovariate(0.05)
                ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
                gpu_min = 0.0
                n_eps   = 0
                n_steps = 0
                if evt == "train_job":
                    gpu_min = rng.gauss(35.4 * scale, 5)
                    n_steps = rng.choice([1000, 2000, 5000])
                elif evt == "eval_job":
                    gpu_min = rng.gauss(2.0 * scale, 0.5)
                    n_eps   = rng.choice([10, 20])
                elif evt == "dagger_iter":
                    gpu_min = rng.gauss(8.0 * scale, 2)
                    n_eps   = rng.randint(20, 30)
                    n_steps = 3000
                elif evt == "demo_upload":
                    n_eps   = rng.randint(10, 100)
                cost = gpu_min / 60.0 * GPU_COST
                meta = json.dumps({"checkpoint": f"ckpt-{rng.randint(1000,9999)}"})
                conn.execute(
                    "INSERT INTO usage_events (partner_id,event_type,gpu_minutes,n_episodes,n_steps,cost_usd,metadata,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (pid, evt, gpu_min, n_eps, n_steps, cost, meta, ts)
                )


# ── Analytics queries ─────────────────────────────────────────────────────────

def partner_summary(db_path: str = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute("""
        SELECT p.id, p.name, p.tier, p.joined_at,
               COALESCE(SUM(e.gpu_minutes)/60.0, 0) AS gpu_hours,
               COALESCE(SUM(e.n_episodes), 0) AS total_episodes,
               COALESCE(SUM(e.n_steps), 0) AS total_steps,
               COALESCE(SUM(e.cost_usd), 0) AS total_cost,
               COUNT(CASE WHEN e.event_type='train_job' THEN 1 END) AS n_train_jobs,
               COUNT(CASE WHEN e.event_type='eval_job' THEN 1 END) AS n_eval_jobs,
               COUNT(CASE WHEN e.event_type='dagger_iter' THEN 1 END) AS n_dagger_iters,
               MAX(e.created_at) AS last_activity
        FROM partners p
        LEFT JOIN usage_events e ON p.id = e.partner_id
        GROUP BY p.id
        ORDER BY total_cost DESC
        """).fetchall()
    return [dict(r) for r in rows]


def partner_timeseries(partner_id: str, days: int = 30, db_path: str = DB_PATH) -> list[dict]:
    """Daily GPU hours + cost for sparkline chart."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute("""
        SELECT substr(created_at, 1, 10) AS day,
               SUM(gpu_minutes)/60.0 AS gpu_hours,
               SUM(cost_usd) AS cost,
               SUM(n_episodes) AS episodes
        FROM usage_events
        WHERE partner_id=? AND created_at >= ?
        GROUP BY day
        ORDER BY day
        """, (partner_id, cutoff)).fetchall()
    return [dict(r) for r in rows]


def platform_totals(db_path: str = DB_PATH) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute("""
        SELECT COALESCE(SUM(gpu_minutes)/60.0,0) AS total_gpu_hours,
               COALESCE(SUM(cost_usd),0) AS total_revenue,
               COALESCE(SUM(n_episodes),0) AS total_episodes,
               COALESCE(SUM(n_steps),0) AS total_steps,
               COUNT(DISTINCT partner_id) AS active_partners
        FROM usage_events
        """).fetchone()
    return dict(row) if row else {}


# ── HTML dashboard ────────────────────────────────────────────────────────────

def render_dashboard(partners: list[dict], totals: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    tier_colors = {"starter": "#6366f1", "growth": "#3b82f6", "enterprise": "#22c55e"}

    rows = ""
    for p in partners:
        tc = tier_colors.get(p["tier"], "#94a3b8")
        last = p.get("last_activity","")[:10] if p.get("last_activity") else "—"
        rows += f"""
        <tr onclick="window.location='/partner/{p['id']}'" style="cursor:pointer">
          <td style="padding:10px 12px;font-weight:600">{p['name']}</td>
          <td style="padding:10px 12px">
            <span style="background:{tc}22;color:{tc};padding:2px 8px;border-radius:10px;font-size:11px">
              {p['tier']}
            </span>
          </td>
          <td style="padding:10px 12px;font-family:monospace">{p['gpu_hours']:.1f} hr</td>
          <td style="padding:10px 12px;font-family:monospace">${p['total_cost']:.2f}</td>
          <td style="padding:10px 12px">{int(p['total_episodes'])}</td>
          <td style="padding:10px 12px">{int(p['n_train_jobs'])}</td>
          <td style="padding:10px 12px">{int(p['n_dagger_iters'])}</td>
          <td style="padding:10px 12px;color:#64748b;font-size:12px">{last}</td>
        </tr>"""

    def metric(val: str, label: str, color: str = "#f8fafc") -> str:
        return f"""<div style="background:#0f172a;border-radius:8px;padding:14px 20px;text-align:center;min-width:120px">
          <div style="font-size:28px;font-weight:700;color:{color}">{val}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">{label}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>Partner Usage Analytics</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  h2{{color:#94a3b8;font-size:13px;font-weight:400;margin:0 0 24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
  tr:hover td{{background:#243249}}
</style>
</head>
<body>
<h1>Partner Usage Analytics</h1>
<h2>Updated {now} · auto-refresh 60s · OCI Robot Cloud</h2>

<div class="card">
  <div style="display:flex;gap:12px;flex-wrap:wrap">
    {metric(str(int(totals.get('active_partners',0))), 'Active Partners', '#3b82f6')}
    {metric(f"${totals.get('total_revenue',0):.0f}", 'Total Revenue', '#22c55e')}
    {metric(f"{totals.get('total_gpu_hours',0):.1f}hr", 'GPU Hours Used', '#6366f1')}
    {metric(str(int(totals.get('total_episodes',0))), 'Demos Ingested', '#f59e0b')}
    {metric(f"{totals.get('total_steps',0)/1000:.0f}k", 'Training Steps', '#94a3b8')}
  </div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Partner Activity</h3>
  <table>
    <tr>
      <th>Partner</th><th>Tier</th><th>GPU Hours</th><th>Cost</th>
      <th>Episodes</th><th>Train Jobs</th><th>DAgger Iters</th><th>Last Active</th>
    </tr>
    {rows}
  </table>
</div>

<div style="color:#475569;font-size:11px">
  <a href="/api/partners" style="color:#3b82f6">API: /api/partners</a> ·
  <a href="/api/platform" style="color:#3b82f6">/api/platform</a>
</div>
</body>
</html>"""


def render_partner_detail(partner_id: str, partners: list[dict], ts: list[dict]) -> str:
    p = next((x for x in partners if x["id"] == partner_id), None)
    if not p:
        return "<h1>Partner not found</h1>"

    sparkline_pts = ""
    if ts:
        max_cost = max(d["cost"] for d in ts) or 1
        for i, d in enumerate(ts):
            x = 20 + i * (360 / max(len(ts)-1, 1))
            y = 80 - (d["cost"] / max_cost) * 60
            sparkline_pts += f"{x:.0f},{y:.0f} "

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{p['name']} — Usage</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  .metric{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 16px;margin:4px;text-align:center}}
</style>
</head>
<body>
<a href="/" style="color:#3b82f6;text-decoration:none">← All Partners</a>
<h1 style="color:#f8fafc;margin-top:12px">{p['name']}</h1>
<p style="color:#94a3b8">Tier: {p['tier']} · Joined: {p.get('joined_at','')[:10]}</p>

<div class="card">
  <div class="metric"><div style="font-size:24px;font-weight:700;color:#3b82f6">${p['total_cost']:.2f}</div><div style="font-size:11px;color:#64748b">Total Spend</div></div>
  <div class="metric"><div style="font-size:24px;font-weight:700;color:#6366f1">{p['gpu_hours']:.1f}hr</div><div style="font-size:11px;color:#64748b">GPU Hours</div></div>
  <div class="metric"><div style="font-size:24px;font-weight:700;color:#f59e0b">{int(p['total_episodes'])}</div><div style="font-size:11px;color:#64748b">Episodes</div></div>
  <div class="metric"><div style="font-size:24px;font-weight:700;color:#22c55e">{int(p['n_train_jobs'])}</div><div style="font-size:11px;color:#64748b">Train Jobs</div></div>
  <div class="metric"><div style="font-size:24px;font-weight:700;color:#94a3b8">{int(p['n_dagger_iters'])}</div><div style="font-size:11px;color:#64748b">DAgger Iters</div></div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:13px;text-transform:uppercase;margin-top:0">Daily Cost (30d)</h3>
  <svg width="400" height="100" style="background:#0f172a;border-radius:8px">
    {'<polyline points="' + sparkline_pts.strip() + '" fill="none" stroke="#3b82f6" stroke-width="2"/>' if sparkline_pts else '<text x="200" y="50" fill="#475569" font-size="12" text-anchor="middle">No data</text>'}
  </svg>
</div>

<div style="margin-top:8px">
  <a href="/api/export/{partner_id}?format=csv" style="background:#1e293b;color:#3b82f6;padding:8px 14px;border-radius:6px;text-decoration:none;font-size:13px">⬇ Export CSV</a>
</div>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH) -> "FastAPI":
    app = FastAPI(title="Partner Usage Analytics", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        seed_mock_data(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        partners = partner_summary(db_path)
        totals   = platform_totals(db_path)
        return render_dashboard(partners, totals)

    @app.get("/partner/{partner_id}", response_class=HTMLResponse)
    async def partner_detail(partner_id: str):
        partners = partner_summary(db_path)
        ts = partner_timeseries(partner_id, db_path=db_path)
        return render_partner_detail(partner_id, partners, ts)

    @app.get("/api/partners")
    async def api_partners():
        return partner_summary(db_path)

    @app.get("/api/partners/{partner_id}")
    async def api_partner(partner_id: str):
        partners = partner_summary(db_path)
        p = next((x for x in partners if x["id"] == partner_id), None)
        if not p:
            raise HTTPException(404, "Partner not found")
        ts = partner_timeseries(partner_id, db_path=db_path)
        return {"summary": p, "timeseries_30d": ts}

    @app.get("/api/platform")
    async def api_platform():
        return platform_totals(db_path)

    @app.get("/api/export/{partner_id}")
    async def api_export(partner_id: str, format: str = "csv"):
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM usage_events WHERE partner_id=? ORDER BY created_at DESC",
                (partner_id,)
            ).fetchall()
        if format == "csv":
            header = "id,partner_id,event_type,gpu_minutes,n_episodes,n_steps,cost_usd,created_at\n"
            body = "".join(
                f"{r['id']},{r['partner_id']},{r['event_type']},{r['gpu_minutes']:.2f},"
                f"{r['n_episodes']},{r['n_steps']},{r['cost_usd']:.5f},{r['created_at']}\n"
                for r in rows
            )
            return Response(content=header+body, media_type="text/csv",
                            headers={"Content-Disposition": f"attachment; filename={partner_id}_usage.csv"})
        return [dict(r) for r in rows]

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_usage_analytics", "port": 8027}

    return app


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Partner usage analytics service (port 8027)")
    parser.add_argument("--port", type=int, default=8027)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    parser.add_argument("--mock", action="store_true", help="Seed mock data on startup")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(args.db)
    print(f"Partner Usage Analytics → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
