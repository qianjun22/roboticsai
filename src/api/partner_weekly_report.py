#!/usr/bin/env python3
"""
partner_weekly_report.py — Auto-generated weekly progress reports for design partners (port 8013).

Each Monday, generates a dark-theme HTML report per partner showing:
  - Training jobs run this week
  - Success rate trend (7-day sparkline)
  - GPU hours consumed + cost
  - DAgger iterations completed
  - Key wins and recommended next actions

Usage:
    python src/api/partner_weekly_report.py --port 8013 --mock
    # → http://localhost:8013
"""

import json
import random
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, Response
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/weekly_reports.db"


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class WeeklyMetrics:
    partner_id: str
    partner_name: str
    week_start: str          # ISO date Monday
    week_end: str            # ISO date Sunday
    jobs_run: int
    episodes_collected: int
    gpu_hours: float
    cost_usd: float
    dagger_iters: int
    success_rate_start: float
    success_rate_end: float
    success_delta: float
    best_checkpoint: str
    key_wins: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    daily_success: list[float] = field(default_factory=list)  # 7 values Mon–Sun


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            partner_id TEXT,
            partner_name TEXT,
            week_start TEXT,
            week_end TEXT,
            metrics_json TEXT,
            generated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_partner ON reports(partner_id);
        """)


@contextmanager
def get_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_PARTNERS = [
    ("stretch",  "Stretch Robotics",  0.12, 0.31),
    ("nimble",   "Nimble AI",         0.05, 0.22),
    ("auton",    "Auton Systems",     0.28, 0.51),
    ("grasptech","GraspTech",         0.08, 0.18),
    ("verity",   "Verity",            0.41, 0.65),
]


def _make_wins(delta: float, dagger_iters: int, jobs: int) -> list[str]:
    wins = []
    if delta > 0.10:
        wins.append(f"Success rate improved +{delta:.0%} this week")
    if dagger_iters >= 2:
        wins.append(f"{dagger_iters} DAgger iterations completed successfully")
    if jobs >= 5:
        wins.append(f"{jobs} training jobs ran without errors")
    wins.append("Model checkpoint promoted to staging")
    return wins[:3] if wins else ["First training run completed", "Baseline checkpoint established"]


def _make_recs(success_end: float, delta: float) -> list[str]:
    recs = []
    if success_end < 0.10:
        recs.append("Collect 50+ more diverse episodes to break out of low-success plateau")
        recs.append("Try curriculum DAgger (start at Easy level) to build foundational skills")
    elif success_end < 0.30:
        recs.append("Increase DAgger beta decay (lower beta = more on-policy data)")
        recs.append("Add lighting/position randomization in SDG for better generalization")
    else:
        recs.append("Run curriculum eval to validate generalization across difficulty levels")
        recs.append("Test distilled 60M student model for Jetson deployment")
    if delta < 0:
        recs.insert(0, "⚠ Success rate declined — check for data distribution shift")
    return recs[:3]


def generate_mock_report(partner_id: str, partner_name: str,
                         sr_start: float, sr_end: float,
                         rng: random.Random, week_offset: int = 0) -> WeeklyMetrics:
    today = datetime.now() - timedelta(weeks=week_offset)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    jobs = rng.randint(3, 12)
    dagger_iters = rng.randint(0, 4)
    eps = jobs * rng.randint(15, 35)
    gpu_h = rng.uniform(1.5, 8.0)
    cost = gpu_h * 4.20

    # Daily success sparkline
    daily = []
    sr = sr_start
    for _ in range(7):
        sr = max(0.01, min(0.99, sr + rng.gauss(0.01, 0.03)))
        daily.append(round(sr, 3))
    sr_end_actual = daily[-1]
    delta = sr_end_actual - sr_start

    wins = _make_wins(delta, dagger_iters, jobs)
    recs = _make_recs(sr_end_actual, delta)

    ckpt_iter = dagger_iters if dagger_iters > 0 else 0
    ckpt = f"/tmp/partner_{partner_id}/dagger_iter{ckpt_iter}/checkpoint-{jobs*500}"

    return WeeklyMetrics(
        partner_id=partner_id,
        partner_name=partner_name,
        week_start=monday.strftime("%Y-%m-%d"),
        week_end=sunday.strftime("%Y-%m-%d"),
        jobs_run=jobs,
        episodes_collected=eps,
        gpu_hours=round(gpu_h, 2),
        cost_usd=round(cost, 2),
        dagger_iters=dagger_iters,
        success_rate_start=round(sr_start, 3),
        success_rate_end=round(sr_end_actual, 3),
        success_delta=round(delta, 3),
        best_checkpoint=ckpt,
        key_wins=wins,
        recommendations=recs,
        daily_success=daily,
    )


def seed_mock_reports(db_path: str = DB_PATH) -> list[WeeklyMetrics]:
    rng = random.Random(99)
    reports = []
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM reports")
        for pid, pname, sr0, sr1 in MOCK_PARTNERS:
            for week in range(3):
                sr_start = sr0 + week * (sr1 - sr0) / 3
                sr_end = sr_start + (sr1 - sr0) / 3
                m = generate_mock_report(pid, pname, sr_start, sr_end, rng, week_offset=2 - week)
                rep_id = f"{pid}_{m.week_start}"
                import json as _json
                conn.execute(
                    "INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?,?,?)",
                    (rep_id, pid, pname, m.week_start, m.week_end,
                     _json.dumps(m.__dict__), datetime.now().isoformat())
                )
                reports.append(m)
    return reports


# ── HTML rendering ─────────────────────────────────────────────────────────────

def sparkline_svg(values: list[float], width: int = 120, height: int = 30) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = max(mx - mn, 0.01)
    step = width / max(len(values) - 1, 1)
    pts = " ".join(
        f"{i * step:.1f},{height - (v - mn) / rng * (height - 4) - 2:.1f}"
        for i, v in enumerate(values)
    )
    color = "#22c55e" if values[-1] >= values[0] else "#ef4444"
    return (f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
            f'</svg>')


def render_report_html(m: WeeklyMetrics) -> str:
    trend_color = "#22c55e" if m.success_delta >= 0 else "#ef4444"
    trend_sign = "+" if m.success_delta >= 0 else ""
    spark = sparkline_svg(m.daily_success)

    wins_html = "".join(f'<li style="margin-bottom:6px">{w}</li>' for w in m.key_wins)
    recs_html = "".join(f'<li style="margin-bottom:6px">{r}</li>' for r in m.recommendations)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Weekly Report — {m.partner_name}</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:28px;max-width:700px}}
  h1{{color:#f8fafc;font-size:22px;margin-bottom:2px}}
  .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px;margin-bottom:16px}}
  .metric{{display:inline-block;background:#0f172a;border-radius:8px;padding:12px 16px;margin:4px;text-align:center;min-width:90px}}
  .num{{font-size:26px;font-weight:700}}
  .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
  ul{{margin:0;padding-left:18px;color:#94a3b8;font-size:13px}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px">
  <div>
    <h1>{m.partner_name} — Weekly Report</h1>
    <div class="sub">{m.week_start} → {m.week_end} · Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  </div>
  <a href="/" style="color:#3b82f6;font-size:13px;text-decoration:none">← All Partners</a>
</div>

<div class="card">
  <div class="metric"><div class="num" style="color:#22c55e">{m.success_rate_end:.0%}</div><div class="lbl">Success Rate</div></div>
  <div class="metric"><div class="num" style="color:{trend_color}">{trend_sign}{m.success_delta:.0%}</div><div class="lbl">Week Delta</div></div>
  <div class="metric"><div class="num" style="color:#3b82f6">{m.jobs_run}</div><div class="lbl">Jobs Run</div></div>
  <div class="metric"><div class="num" style="color:#6366f1">{m.dagger_iters}</div><div class="lbl">DAgger Iters</div></div>
  <div class="metric"><div class="num" style="color:#f59e0b">{m.episodes_collected}</div><div class="lbl">Episodes</div></div>
  <div class="metric"><div class="num" style="color:#94a3b8">${m.cost_usd:.2f}</div><div class="lbl">GPU Cost</div></div>
</div>

<div class="card">
  <div style="display:flex;align-items:center;gap:16px">
    <div>
      <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:4px">7-Day Success Rate Trend</div>
      {spark}
    </div>
    <div style="font-size:12px;color:#64748b">
      Mon: {m.daily_success[0]:.0%} → Sun: {m.daily_success[-1]:.0%}
    </div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card">
    <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:10px">🏆 Key Wins</div>
    <ul>{wins_html}</ul>
  </div>
  <div class="card">
    <div style="font-size:12px;color:#f59e0b;text-transform:uppercase;margin-bottom:10px">→ Recommended Next Steps</div>
    <ul>{recs_html}</ul>
  </div>
</div>

<div class="card" style="background:#0c1a2e;border:1px solid #1e3a5f">
  <div style="font-size:12px;color:#3b82f6;text-transform:uppercase;margin-bottom:8px">Best Checkpoint</div>
  <div style="font-family:monospace;font-size:12px;color:#94a3b8">{m.best_checkpoint}</div>
  <div style="margin-top:8px;font-size:12px;color:#475569">{m.gpu_hours:.1f} GPU hours · {m.episodes_collected} episodes · ${m.cost_usd:.2f} total</div>
</div>

<div style="color:#334155;font-size:11px;margin-top:12px">
  OCI Robot Cloud · auto-generated weekly report · <a href="/api/report/{m.partner_id}/latest?format=json" style="color:#3b82f6">JSON</a>
</div>
</body>
</html>"""


def render_index_html(all_reports: list[dict]) -> str:
    """Latest report per partner as index."""
    import json as _json
    # Deduplicate: latest per partner
    seen = {}
    for r in all_reports:
        pid = r["partner_id"]
        if pid not in seen or r["week_start"] > seen[pid]["week_start"]:
            seen[pid] = r

    rows = ""
    for r in sorted(seen.values(), key=lambda x: x["partner_name"]):
        m_dict = _json.loads(r["metrics_json"])
        delta = m_dict["success_delta"]
        color = "#22c55e" if delta >= 0 else "#ef4444"
        sign = "+" if delta >= 0 else ""
        spark = sparkline_svg(m_dict["daily_success"], 80, 24)
        rows += f"""<tr onclick="window.location='/report/{r['partner_id']}/latest'" style="cursor:pointer">
          <td style="padding:10px 12px;font-weight:600">{r['partner_name']}</td>
          <td style="padding:10px 12px">{spark}</td>
          <td style="padding:10px 12px;font-weight:700;color:#22c55e">{m_dict['success_rate_end']:.0%}</td>
          <td style="padding:10px 12px;color:{color}">{sign}{delta:.0%}</td>
          <td style="padding:10px 12px;color:#6366f1">{m_dict['dagger_iters']}</td>
          <td style="padding:10px 12px;color:#22c55e">${m_dict['cost_usd']:.2f}</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b">{r['week_start']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Partner Weekly Reports</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
  tr:hover td{{background:#243249}}
</style>
</head>
<body>
<h1>Partner Weekly Reports</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 20px">Auto-generated every Monday · click a partner for full report</p>
<div class="card">
  <table>
    <tr><th>Partner</th><th>7-Day Trend</th><th>Success Rate</th><th>Delta</th><th>DAgger Iters</th><th>Cost</th><th>Week</th></tr>
    {rows}
  </table>
</div>
<div style="color:#475569;font-size:11px">
  <a href="/api/reports" style="color:#3b82f6">/api/reports JSON</a> ·
  <a href="/health" style="color:#3b82f6">/health</a>
</div>
</body>
</html>"""


# ── FastAPI app ────────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH, mock: bool = True) -> "FastAPI":
    import json as _json
    app = FastAPI(title="Partner Weekly Reports", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        if mock:
            seed_mock_reports(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY week_start DESC"
            ).fetchall()
        return render_index_html([dict(r) for r in rows])

    @app.get("/report/{partner_id}/latest", response_class=HTMLResponse)
    async def latest_report(partner_id: str, format: str = "html"):
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE partner_id=? ORDER BY week_start DESC LIMIT 1",
                (partner_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Partner not found")
        m_dict = _json.loads(row["metrics_json"])
        m = WeeklyMetrics(**m_dict)
        if format == "json":
            return JSONResponse(m_dict)
        return render_report_html(m)

    @app.get("/api/reports")
    async def api_reports():
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT id, partner_id, partner_name, week_start, week_end, generated_at FROM reports ORDER BY week_start DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/report/{partner_id}/latest")
    async def api_latest(partner_id: str):
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE partner_id=? ORDER BY week_start DESC LIMIT 1",
                (partner_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Partner not found")
        return _json.loads(row["metrics_json"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_weekly_report", "port": 8013}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Partner weekly reports (port 8013)")
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(db_path=args.db, mock=args.mock)
    print(f"Partner Weekly Reports → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
