#!/usr/bin/env python3
"""
live_demo_scheduler.py — FastAPI service (port 8031) for scheduling and coordinating
live robot demonstrations for design partners and conference events (AI World, GTC).

Features:
  - Demo request booking: title, requester, robot, task, preferred datetime,
    audience size, mode (live/recorded-fallback/offline)
  - Calendar view: 7-day upcoming demos with conflict detection
  - Demo runbook: per-demo pre-checklist, live steps, and fallback plan
  - Status tracking: scheduled/running/completed/cancelled/failed
  - SQLite-backed persistence at /tmp/demo_scheduler.db
  - HTML dashboard at / with upcoming demos, 24h highlights, quick-book form
  - Mock mode for CI (--mock flag skips GPU reservation side-effects)

REST endpoints:
  POST /demos               — Book a new demo
  GET  /demos               — List all demos (optional ?status= filter)
  GET  /demos/{id}          — Detail view for one demo
  PUT  /demos/{id}/status   — Update demo status
  GET  /calendar            — 7-day calendar JSON view

Usage:
    python src/api/live_demo_scheduler.py
    python src/api/live_demo_scheduler.py --port 8031 --mock
    # → http://localhost:8031
"""

import argparse
import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, Form, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = "/tmp/demo_scheduler.db"

ROBOTS = ["franka", "ur5e", "xarm7", "kinova"]
TASKS = ["pick-lift", "pick-place", "push-goal"]
MODES = ["live", "recorded-fallback", "offline"]
STATUSES = ["scheduled", "running", "completed", "cancelled", "failed"]

RUNBOOK_TEMPLATES = {
    "pick-lift": {
        "pre_checklist": [
            "preflight: verify robot power and e-stop cleared",
            "model-loaded: confirm GR00T checkpoint loaded on GPU",
            "network-ok: ping OCI inference endpoint < 50ms",
            "workspace: place target cube in marked zone A",
            "camera: verify wrist + overhead cameras active",
        ],
        "live_steps": [
            "Launch inference server (port 8001)",
            "Start data capture pipeline",
            "Execute pick-lift policy (15s per episode)",
            "Show live telemetry on demo dashboard",
            "Collect audience Q&A",
        ],
        "fallback_plan": "Switch to recorded-fallback: play best_run_pick_lift.mp4 with live commentary",
    },
    "pick-place": {
        "pre_checklist": [
            "preflight: verify robot power and e-stop cleared",
            "model-loaded: confirm pick-place checkpoint loaded",
            "network-ok: ping OCI inference endpoint < 50ms",
            "workspace: set up source tray and target tray",
            "camera: calibrate overhead camera perspective",
        ],
        "live_steps": [
            "Launch inference server (port 8001)",
            "Initialize workspace scene",
            "Execute pick-place policy (20s per episode)",
            "Show joint angle telemetry overlay",
            "Run 3 consecutive episodes for reliability demo",
        ],
        "fallback_plan": "Switch to recorded-fallback: play best_run_pick_place.mp4 with live commentary",
    },
    "push-goal": {
        "pre_checklist": [
            "preflight: verify robot power and e-stop cleared",
            "model-loaded: confirm push-goal checkpoint loaded",
            "network-ok: ping OCI inference endpoint < 50ms",
            "workspace: clear push table surface, place puck at start",
            "camera: verify top-down camera angle covers full table",
        ],
        "live_steps": [
            "Launch inference server (port 8001)",
            "Set goal position marker",
            "Execute push-goal policy (12s per episode)",
            "Overlay predicted vs actual trajectory on screen",
            "Reset and repeat for audience",
        ],
        "fallback_plan": "Switch to recorded-fallback: play best_run_push_goal.mp4 with live commentary",
    },
}

SEED_DEMOS = [
    {
        "title": "AI World Booth Demo — Live Robot Manipulation",
        "requester": "Jun Qian",
        "robot": "franka",
        "task": "pick-place",
        "preferred_dt": "2026-09-15T10:00:00",
        "audience_size": 50,
        "mode": "live",
        "notes": "Main AI World 2026 booth demo. High visibility — NVIDIA and Oracle executives attending.",
    },
    {
        "title": "NVIDIA Isaac Team Technical Meeting",
        "requester": "Jun Qian",
        "robot": "xarm7",
        "task": "pick-lift",
        "preferred_dt": "2026-06-15T14:00:00",
        "audience_size": 8,
        "mode": "live",
        "notes": "Deep-dive for Isaac Sim integration partners. Focus on fine-tuning pipeline and MAE metrics.",
    },
    {
        "title": "Design Partner Onboarding Demo",
        "requester": "Jun Qian",
        "robot": "ur5e",
        "task": "push-goal",
        "preferred_dt": "2026-06-01T15:00:00",
        "audience_size": 5,
        "mode": "recorded-fallback",
        "notes": "First demo for new design partner. Use recorded fallback as primary to reduce risk.",
    },
]

MOCK_MODE = False

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demos (
                id              TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                requester       TEXT NOT NULL,
                robot           TEXT NOT NULL,
                task            TEXT NOT NULL,
                preferred_dt    TEXT NOT NULL,
                audience_size   INTEGER NOT NULL DEFAULT 5,
                mode            TEXT NOT NULL DEFAULT 'live',
                status          TEXT NOT NULL DEFAULT 'scheduled',
                notes           TEXT DEFAULT '',
                runbook         TEXT DEFAULT '{}',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                started_at      TEXT,
                completed_at    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checklist_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                demo_id     TEXT NOT NULL,
                phase       TEXT NOT NULL,
                step_order  INTEGER NOT NULL,
                description TEXT NOT NULL,
                checked     INTEGER NOT NULL DEFAULT 0,
                checked_at  TEXT,
                FOREIGN KEY (demo_id) REFERENCES demos(id)
            )
        """)
        # Seed if empty
        row = conn.execute("SELECT COUNT(*) FROM demos").fetchone()
        if row[0] == 0:
            _seed_demos(conn)


def _seed_demos(conn: sqlite3.Connection):
    now = datetime.utcnow().isoformat()
    for sd in SEED_DEMOS:
        demo_id = str(uuid.uuid4())
        runbook = _build_runbook(sd["task"])
        conn.execute(
            """INSERT INTO demos
               (id, title, requester, robot, task, preferred_dt, audience_size,
                mode, status, notes, runbook, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                demo_id,
                sd["title"],
                sd["requester"],
                sd["robot"],
                sd["task"],
                sd["preferred_dt"],
                sd["audience_size"],
                sd["mode"],
                "scheduled",
                sd["notes"],
                json.dumps(runbook),
                now,
                now,
            ),
        )
        _insert_checklist(conn, demo_id, runbook)


def _build_runbook(task: str) -> dict:
    tmpl = RUNBOOK_TEMPLATES.get(task, RUNBOOK_TEMPLATES["pick-lift"])
    return {
        "pre_checklist": tmpl["pre_checklist"],
        "live_steps": tmpl["live_steps"],
        "fallback_plan": tmpl["fallback_plan"],
    }


def _insert_checklist(conn: sqlite3.Connection, demo_id: str, runbook: dict):
    phases = [
        ("pre", runbook.get("pre_checklist", [])),
        ("live", runbook.get("live_steps", [])),
    ]
    for phase, steps in phases:
        for i, step in enumerate(steps):
            conn.execute(
                """INSERT INTO checklist_items
                   (demo_id, phase, step_order, description)
                   VALUES (?,?,?,?)""",
                (demo_id, phase, i, step),
            )


def _detect_conflict(conn: sqlite3.Connection, preferred_dt: str, exclude_id: str = None) -> bool:
    """Return True if another demo overlaps within ±60 minutes."""
    dt = datetime.fromisoformat(preferred_dt)
    window_start = (dt - timedelta(minutes=60)).isoformat()
    window_end = (dt + timedelta(minutes=60)).isoformat()
    query = """
        SELECT id FROM demos
        WHERE status NOT IN ('cancelled', 'failed')
        AND preferred_dt BETWEEN ? AND ?
    """
    params = [window_start, window_end]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    row = conn.execute(query, params).fetchone()
    return row is not None


def row_to_dict(row) -> dict:
    d = dict(row)
    if "runbook" in d and isinstance(d["runbook"], str):
        try:
            d["runbook"] = json.loads(d["runbook"])
        except Exception:
            d["runbook"] = {}
    return d


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud — Live Demo Scheduler",
    description="Schedule and coordinate live robot demonstrations for design partners and events.",
    version="1.0.0",
)


@app.on_event("startup")
async def startup():
    init_db()


# ---------------------------------------------------------------------------
# REST: POST /demos
# ---------------------------------------------------------------------------


@app.post("/demos", response_class=JSONResponse)
async def book_demo(
    title: str = Form(...),
    requester: str = Form(...),
    robot: str = Form(...),
    task: str = Form(...),
    preferred_dt: str = Form(...),
    audience_size: int = Form(5),
    mode: str = Form("live"),
    notes: str = Form(""),
):
    if robot not in ROBOTS:
        raise HTTPException(400, f"robot must be one of {ROBOTS}")
    if task not in TASKS:
        raise HTTPException(400, f"task must be one of {TASKS}")
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {MODES}")
    try:
        datetime.fromisoformat(preferred_dt)
    except ValueError:
        raise HTTPException(400, "preferred_dt must be ISO-8601 (e.g. 2026-09-15T10:00:00)")

    now = datetime.utcnow().isoformat()
    demo_id = str(uuid.uuid4())
    runbook = _build_runbook(task)

    with db_conn() as conn:
        conflict = _detect_conflict(conn, preferred_dt)
        if conflict and not MOCK_MODE:
            raise HTTPException(
                409,
                "Another demo is scheduled within 60 minutes of that time. "
                "Choose a different slot or cancel the conflicting demo first.",
            )
        conn.execute(
            """INSERT INTO demos
               (id, title, requester, robot, task, preferred_dt, audience_size,
                mode, status, notes, runbook, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                demo_id, title, requester, robot, task, preferred_dt,
                audience_size, mode, "scheduled", notes,
                json.dumps(runbook), now, now,
            ),
        )
        _insert_checklist(conn, demo_id, runbook)

    gpu_note = " (GPU reservation skipped — mock mode)" if MOCK_MODE else ""
    return JSONResponse(
        status_code=201,
        content={
            "id": demo_id,
            "status": "scheduled",
            "conflict_warning": conflict,
            "message": f"Demo booked successfully{gpu_note}",
        },
    )


# ---------------------------------------------------------------------------
# REST: GET /demos
# ---------------------------------------------------------------------------


@app.get("/demos", response_class=JSONResponse)
async def list_demos(status: str = Query(None)):
    with db_conn() as conn:
        if status:
            if status not in STATUSES:
                raise HTTPException(400, f"status must be one of {STATUSES}")
            rows = conn.execute(
                "SELECT * FROM demos WHERE status=? ORDER BY preferred_dt", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM demos ORDER BY preferred_dt"
            ).fetchall()
    return [row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# REST: GET /demos/{id}
# ---------------------------------------------------------------------------


@app.get("/demos/{demo_id}", response_class=JSONResponse)
async def get_demo(demo_id: str):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM demos WHERE id=?", (demo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Demo not found")
        demo = row_to_dict(row)
        items = conn.execute(
            "SELECT * FROM checklist_items WHERE demo_id=? ORDER BY phase, step_order",
            (demo_id,),
        ).fetchall()
        demo["checklist"] = [dict(i) for i in items]
    return demo


# ---------------------------------------------------------------------------
# REST: PUT /demos/{id}/status
# ---------------------------------------------------------------------------


@app.put("/demos/{demo_id}/status", response_class=JSONResponse)
async def update_status(demo_id: str, status: str = Form(...)):
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    now = datetime.utcnow().isoformat()
    with db_conn() as conn:
        row = conn.execute("SELECT id, status FROM demos WHERE id=?", (demo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Demo not found")
        extra_cols = ""
        extra_vals = []
        if status == "running":
            extra_cols = ", started_at=?"
            extra_vals.append(now)
        elif status in ("completed", "failed"):
            extra_cols = ", completed_at=?"
            extra_vals.append(now)
        conn.execute(
            f"UPDATE demos SET status=?, updated_at=?{extra_cols} WHERE id=?",
            [status, now] + extra_vals + [demo_id],
        )
    return {"id": demo_id, "status": status, "updated_at": now}


# ---------------------------------------------------------------------------
# REST: GET /calendar
# ---------------------------------------------------------------------------


@app.get("/calendar", response_class=JSONResponse)
async def get_calendar():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=7)
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM demos
               WHERE preferred_dt >= ? AND preferred_dt < ?
               AND status NOT IN ('cancelled','failed')
               ORDER BY preferred_dt""",
            (today.isoformat(), end.isoformat()),
        ).fetchall()
    demos = [row_to_dict(r) for r in rows]

    days = []
    for i in range(7):
        day = today + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_demos = [
            d for d in demos
            if d["preferred_dt"].startswith(day_str)
        ]
        days.append({
            "date": day_str,
            "weekday": day.strftime("%A"),
            "demos": day_demos,
            "demo_count": len(day_demos),
        })

    return {
        "range_start": today.strftime("%Y-%m-%d"),
        "range_end": end.strftime("%Y-%m-%d"),
        "days": days,
        "total_demos": len(demos),
    }


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "scheduled": "#f59e0b",
    "running": "#3b82f6",
    "completed": "#22c55e",
    "cancelled": "#6b7280",
    "failed": "#ef4444",
}

STATUS_EMOJI = {
    "scheduled": "&#9679;",
    "running": "&#9654;",
    "completed": "&#10003;",
    "cancelled": "&#8722;",
    "failed": "&#10007;",
}


def _badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#6b7280")
    sym = STATUS_EMOJI.get(status, "&#9679;")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:600;">'
        f'{sym} {status.upper()}</span>'
    )


def _mode_badge(mode: str) -> str:
    color = {"live": "#C74634", "recorded-fallback": "#f59e0b", "offline": "#6b7280"}.get(mode, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 8px;'
        f'border-radius:10px;font-size:11px;">{mode}</span>'
    )


def _build_calendar_svg(days: list) -> str:
    """Build a 7-cell inline SVG calendar row showing demo counts per day."""
    cell_w, cell_h = 100, 70
    total_w = cell_w * 7 + 2
    total_h = cell_h + 2
    cells = []
    for i, day in enumerate(days):
        x = i * cell_w + 1
        y = 1
        count = day["demo_count"]
        fill = "#1e3a5f" if count == 0 else "#C74634"
        opacity = "0.5" if count == 0 else "1.0"
        short_day = day["weekday"][:3]
        short_date = day["date"][5:]  # MM-DD
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" '
            f'rx="6" fill="{fill}" opacity="{opacity}"/>'
            f'<text x="{x + cell_w // 2}" y="{y + 20}" text-anchor="middle" '
            f'font-size="11" fill="#94a3b8">{short_day}</text>'
            f'<text x="{x + cell_w // 2}" y="{y + 36}" text-anchor="middle" '
            f'font-size="10" fill="#cbd5e1">{short_date}</text>'
            f'<text x="{x + cell_w // 2}" y="{y + 56}" text-anchor="middle" '
            f'font-size="18" font-weight="bold" fill="#ffffff">'
            f'{"&mdash;" if count == 0 else str(count)}</text>'
        )
    return (
        f'<svg width="{total_w}" height="{total_h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">'
        + "".join(cells)
        + "</svg>"
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    next24 = datetime.utcnow() + timedelta(hours=24)

    with db_conn() as conn:
        all_demos = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM demos ORDER BY preferred_dt"
            ).fetchall()
        ]
        upcoming_7 = [
            row_to_dict(r)
            for r in conn.execute(
                """SELECT * FROM demos
                   WHERE preferred_dt >= ? AND status NOT IN ('cancelled','failed')
                   ORDER BY preferred_dt LIMIT 20""",
                (today.isoformat(),),
            ).fetchall()
        ]
        next24_demos = [
            row_to_dict(r)
            for r in conn.execute(
                """SELECT * FROM demos
                   WHERE preferred_dt BETWEEN ? AND ?
                   AND status NOT IN ('cancelled','failed')
                   ORDER BY preferred_dt""",
                (datetime.utcnow().isoformat(), next24.isoformat()),
            ).fetchall()
        ]

    # Build calendar days
    cal_days = []
    for i in range(7):
        d = today + timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        cnt = sum(1 for x in upcoming_7 if x["preferred_dt"].startswith(ds))
        cal_days.append({"date": ds, "weekday": d.strftime("%A"), "demo_count": cnt})
    svg_calendar = _build_calendar_svg(cal_days)

    # Stats
    total = len(all_demos)
    sched = sum(1 for d in all_demos if d["status"] == "scheduled")
    done = sum(1 for d in all_demos if d["status"] == "completed")
    running = sum(1 for d in all_demos if d["status"] == "running")

    def demo_row(d: dict) -> str:
        dt_str = d["preferred_dt"].replace("T", " ")[:16]
        return (
            f"<tr>"
            f'<td style="padding:10px 12px;">'
            f'<a href="/demos/{d["id"]}" style="color:#93c5fd;text-decoration:none;">'
            f'{d["title"]}</a></td>'
            f'<td style="padding:10px 12px;color:#94a3b8;">{d["requester"]}</td>'
            f'<td style="padding:10px 12px;">'
            f'<span style="color:#e2e8f0;font-family:monospace;">'
            f'{d["robot"].upper()}</span></td>'
            f'<td style="padding:10px 12px;color:#94a3b8;">{d["task"]}</td>'
            f'<td style="padding:10px 12px;">{_mode_badge(d["mode"])}</td>'
            f'<td style="padding:10px 12px;color:#cbd5e1;font-size:13px;">{dt_str}</td>'
            f'<td style="padding:10px 12px;text-align:center;">'
            f'<span style="color:#e2e8f0;">{d["audience_size"]}</span></td>'
            f'<td style="padding:10px 12px;">{_badge(d["status"])}</td>'
            f"</tr>"
        )

    table_rows = "".join(demo_row(d) for d in upcoming_7) if upcoming_7 else (
        '<tr><td colspan="8" style="padding:20px;text-align:center;color:#64748b;">'
        "No upcoming demos</td></tr>"
    )

    next24_rows = ""
    if next24_demos:
        for d in next24_demos:
            dt_str = d["preferred_dt"].replace("T", " ")[:16]
            next24_rows += (
                f'<div style="background:#1e3a5f;border-left:4px solid #C74634;'
                f'padding:10px 14px;border-radius:6px;margin-bottom:10px;">'
                f'<div style="color:#f1f5f9;font-weight:600;">{d["title"]}</div>'
                f'<div style="color:#94a3b8;font-size:12px;margin-top:4px;">'
                f'{dt_str} &bull; {d["robot"].upper()} &bull; {d["task"]} &bull; '
                f'{d["audience_size"]} attendees &bull; {_mode_badge(d["mode"])}'
                f'</div></div>'
            )
    else:
        next24_rows = '<p style="color:#64748b;font-size:13px;">No demos in the next 24 hours.</p>'

    robot_options = "".join(f'<option value="{r}">{r.upper()}</option>' for r in ROBOTS)
    task_options = "".join(f'<option value="{t}">{t}</option>' for t in TASKS)
    mode_options = "".join(f'<option value="{m}">{m}</option>' for m in MODES)

    mock_banner = (
        '<div style="background:#7c3aed;color:#fff;text-align:center;padding:6px;font-size:13px;">'
        "MOCK MODE — GPU reservation disabled</div>"
        if MOCK_MODE else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Live Demo Scheduler</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont,
         'Segoe UI', sans-serif; min-height: 100vh; }}
  a {{ color: inherit; }}
  h1, h2, h3 {{ color: #C74634; }}
  .header {{ background: #0f172a; padding: 18px 32px; border-bottom: 2px solid #C74634;
             display: flex; align-items: center; gap: 16px; }}
  .header h1 {{ font-size: 20px; letter-spacing: 0.5px; }}
  .header .sub {{ color: #64748b; font-size: 13px; margin-top: 2px; }}
  .stat-bar {{ display: flex; gap: 16px; padding: 20px 32px; background: #0f172a;
               border-bottom: 1px solid #1e3a5f; flex-wrap: wrap; }}
  .stat {{ background: #1e3a5f; padding: 12px 20px; border-radius: 8px; min-width: 120px;
           text-align: center; }}
  .stat .num {{ font-size: 26px; font-weight: 700; color: #f1f5f9; }}
  .stat .label {{ font-size: 11px; color: #64748b; margin-top: 2px; text-transform: uppercase;
                  letter-spacing: 0.5px; }}
  .main {{ display: grid; grid-template-columns: 1fr 320px; gap: 24px;
           padding: 24px 32px; max-width: 1400px; }}
  .card {{ background: #0f172a; border: 1px solid #1e3a5f; border-radius: 10px;
           padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 15px; margin-bottom: 16px; padding-bottom: 10px;
              border-bottom: 1px solid #1e3a5f; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{ background: #1e3a5f; padding: 10px 12px; text-align: left;
              font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
              color: #64748b; }}
  tbody tr:hover {{ background: #1e3a5f33; }}
  tbody tr {{ border-bottom: 1px solid #1e293b; }}
  .form-group {{ margin-bottom: 14px; }}
  .form-group label {{ display: block; font-size: 12px; color: #94a3b8;
                       margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .form-group input, .form-group select, .form-group textarea {{
    width: 100%; background: #1e3a5f; border: 1px solid #334155; border-radius: 6px;
    padding: 8px 10px; color: #e2e8f0; font-size: 13px; }}
  .form-group input:focus, .form-group select:focus, .form-group textarea:focus {{
    outline: none; border-color: #C74634; }}
  .btn {{ background: #C74634; color: #fff; border: none; padding: 10px 20px;
          border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer;
          width: 100%; margin-top: 4px; }}
  .btn:hover {{ background: #a83a2b; }}
  .mock-tag {{ font-size: 11px; color: #7c3aed; margin-left: 8px; }}
</style>
</head>
<body>
{mock_banner}
<div class="header">
  <div>
    <h1>OCI Robot Cloud &mdash; Live Demo Scheduler</h1>
    <div class="sub">Design Partner &amp; Conference Event Coordination &bull; Port 8031</div>
  </div>
</div>

<div class="stat-bar">
  <div class="stat"><div class="num">{total}</div><div class="label">Total Demos</div></div>
  <div class="stat"><div class="num" style="color:#f59e0b;">{sched}</div><div class="label">Scheduled</div></div>
  <div class="stat"><div class="num" style="color:#3b82f6;">{running}</div><div class="label">Running</div></div>
  <div class="stat"><div class="num" style="color:#22c55e;">{done}</div><div class="label">Completed</div></div>
</div>

<div class="main">
  <div>
    <!-- 7-day calendar -->
    <div class="card">
      <h2>7-Day Calendar View</h2>
      {svg_calendar}
      <p style="color:#64748b;font-size:11px;text-align:center;margin-top:8px;">
        Showing next 7 days from today (UTC) &bull;
        <a href="/calendar" style="color:#93c5fd;">JSON API</a>
      </p>
    </div>

    <!-- Next 24h -->
    <div class="card">
      <h2>Next 24 Hours</h2>
      {next24_rows}
    </div>

    <!-- Upcoming demos table -->
    <div class="card">
      <h2>Upcoming Demos</h2>
      <table>
        <thead>
          <tr>
            <th>Title</th><th>Requester</th><th>Robot</th><th>Task</th>
            <th>Mode</th><th>Date/Time (UTC)</th><th>Audience</th><th>Status</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Sidebar: quick-book form -->
  <div>
    <div class="card">
      <h2>Quick-Book Demo</h2>
      <form method="post" action="/demos/form">
        <div class="form-group">
          <label>Title</label>
          <input type="text" name="title" placeholder="Demo title" required>
        </div>
        <div class="form-group">
          <label>Requester</label>
          <input type="text" name="requester" placeholder="Your name" required>
        </div>
        <div class="form-group">
          <label>Robot</label>
          <select name="robot">{robot_options}</select>
        </div>
        <div class="form-group">
          <label>Task</label>
          <select name="task">{task_options}</select>
        </div>
        <div class="form-group">
          <label>Date &amp; Time (UTC)</label>
          <input type="datetime-local" name="preferred_dt" required>
        </div>
        <div class="form-group">
          <label>Audience Size</label>
          <input type="number" name="audience_size" value="5" min="1" max="500">
        </div>
        <div class="form-group">
          <label>Mode</label>
          <select name="mode">{mode_options}</select>
        </div>
        <div class="form-group">
          <label>Notes</label>
          <textarea name="notes" rows="3" placeholder="Optional context..."></textarea>
        </div>
        <button class="btn" type="submit">Book Demo</button>
      </form>
    </div>

    <!-- API reference -->
    <div class="card">
      <h2>API Reference</h2>
      <div style="font-size:12px;color:#94a3b8;line-height:1.9;">
        <div><code style="color:#93c5fd;">POST /demos</code> &mdash; Book demo</div>
        <div><code style="color:#93c5fd;">GET  /demos</code> &mdash; List all</div>
        <div><code style="color:#93c5fd;">GET  /demos/&lt;id&gt;</code> &mdash; Detail</div>
        <div><code style="color:#93c5fd;">PUT  /demos/&lt;id&gt;/status</code> &mdash; Update status</div>
        <div><code style="color:#93c5fd;">GET  /calendar</code> &mdash; 7-day JSON</div>
        <div style="margin-top:8px;"><a href="/docs" style="color:#C74634;">Swagger UI &rarr;</a></div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# HTML form submission endpoint (redirects back to dashboard)
# ---------------------------------------------------------------------------


@app.post("/demos/form", response_class=HTMLResponse)
async def book_demo_form(
    title: str = Form(...),
    requester: str = Form(...),
    robot: str = Form(...),
    task: str = Form(...),
    preferred_dt: str = Form(...),
    audience_size: int = Form(5),
    mode: str = Form("live"),
    notes: str = Form(""),
):
    # Normalize datetime-local (browser sends "2026-09-15T10:00", no seconds)
    if len(preferred_dt) == 16:
        preferred_dt += ":00"

    errors = []
    if robot not in ROBOTS:
        errors.append(f"Invalid robot '{robot}'")
    if task not in TASKS:
        errors.append(f"Invalid task '{task}'")
    if mode not in MODES:
        errors.append(f"Invalid mode '{mode}'")
    if errors:
        return HTMLResponse(
            f"<h3>Error</h3><ul>{''.join(f'<li>{e}</li>' for e in errors)}</ul>"
            '<a href="/">Back</a>',
            status_code=400,
        )

    now = datetime.utcnow().isoformat()
    demo_id = str(uuid.uuid4())
    runbook = _build_runbook(task)

    with db_conn() as conn:
        conflict = _detect_conflict(conn, preferred_dt)
        conn.execute(
            """INSERT INTO demos
               (id, title, requester, robot, task, preferred_dt, audience_size,
                mode, status, notes, runbook, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                demo_id, title, requester, robot, task, preferred_dt,
                audience_size, mode, "scheduled", notes,
                json.dumps(runbook), now, now,
            ),
        )
        _insert_checklist(conn, demo_id, runbook)

    warning = ""
    if conflict:
        warning = (
            '<div style="background:#92400e;color:#fef3c7;padding:10px 16px;'
            'border-radius:6px;margin-bottom:16px;">'
            "Warning: another demo is scheduled within 60 minutes of this slot."
            "</div>"
        )

    return HTMLResponse(
        f"""<html><head><meta http-equiv="refresh" content="2;url=/"></head>
<body style="background:#1e293b;color:#e2e8f0;font-family:sans-serif;padding:40px;">
{warning}
<div style="color:#22c55e;font-size:18px;">Demo booked! Redirecting...</div>
<p style="color:#64748b;margin-top:8px;">ID: <code>{demo_id}</code></p>
</body></html>"""
    )


# ---------------------------------------------------------------------------
# Demo detail page (HTML)
# ---------------------------------------------------------------------------


@app.get("/demos/{demo_id}/view", response_class=HTMLResponse)
async def demo_detail_html(demo_id: str):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM demos WHERE id=?", (demo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Demo not found")
        demo = row_to_dict(row)
        items = conn.execute(
            "SELECT * FROM checklist_items WHERE demo_id=? ORDER BY phase, step_order",
            (demo_id,),
        ).fetchall()

    runbook = demo.get("runbook", {})
    pre_steps = runbook.get("pre_checklist", [])
    live_steps = runbook.get("live_steps", [])
    fallback = runbook.get("fallback_plan", "N/A")

    def step_list(steps):
        return "".join(
            f'<li style="margin-bottom:6px;color:#cbd5e1;">{s}</li>'
            for s in steps
        )

    checklist_by_phase: dict = {}
    for item in items:
        d = dict(item)
        checklist_by_phase.setdefault(d["phase"], []).append(d)

    def checklist_html(phase_items):
        out = []
        for it in phase_items:
            color = "#22c55e" if it["checked"] else "#64748b"
            sym = "&#10003;" if it["checked"] else "&#9744;"
            out.append(
                f'<div style="color:{color};padding:4px 0;font-size:13px;">'
                f'{sym} {it["description"]}</div>'
            )
        return "".join(out) if out else '<div style="color:#64748b;">No items</div>'

    dt_str = demo["preferred_dt"].replace("T", " ")[:16]

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{demo['title']} — Demo Detail</title>
<style>
  body {{ background:#1e293b; color:#e2e8f0; font-family:-apple-system,sans-serif;
         padding:32px; max-width:900px; margin:0 auto; }}
  h1 {{ color:#C74634; margin-bottom:4px; }}
  h3 {{ color:#C74634; margin:20px 0 8px; }}
  .meta {{ color:#64748b; font-size:13px; margin-bottom:24px; }}
  .card {{ background:#0f172a; border:1px solid #1e3a5f; border-radius:10px;
           padding:20px; margin-bottom:20px; }}
  code {{ background:#1e3a5f; padding:2px 6px; border-radius:4px; font-size:12px; }}
  a {{ color:#93c5fd; }}
  ul {{ padding-left:20px; }}
</style>
</head>
<body>
<a href="/">&larr; Back to Dashboard</a>
<h1 style="margin-top:16px;">{demo['title']}</h1>
<div class="meta">
  ID: <code>{demo['id']}</code> &bull;
  Requester: {demo['requester']} &bull;
  Robot: {demo['robot'].upper()} &bull;
  Task: {demo['task']} &bull;
  Mode: {_mode_badge(demo['mode'])} &bull;
  {_badge(demo['status'])}
</div>

<div class="card">
  <h3>Scheduling</h3>
  <p>Preferred time: <strong>{dt_str} UTC</strong></p>
  <p>Audience size: {demo['audience_size']}</p>
  {"<p>Notes: " + demo['notes'] + "</p>" if demo['notes'] else ""}
</div>

<div class="card">
  <h3>Pre-Demo Checklist</h3>
  {checklist_html(checklist_by_phase.get('pre', []))}
</div>

<div class="card">
  <h3>Live Demo Steps</h3>
  {checklist_html(checklist_by_phase.get('live', []))}
</div>

<div class="card">
  <h3>Fallback Plan</h3>
  <p style="color:#fbbf24;">{fallback}</p>
</div>

<div class="card">
  <h3>Update Status</h3>
  <form method="post" action="/demos/{demo['id']}/status/form"
        style="display:flex;gap:10px;align-items:center;">
    <select name="status" style="background:#1e3a5f;border:1px solid #334155;
            border-radius:6px;padding:8px;color:#e2e8f0;">
      {''.join(f'<option value="{s}" {"selected" if s == demo["status"] else ""}>{s}</option>' for s in STATUSES)}
    </select>
    <button type="submit"
            style="background:#C74634;color:#fff;border:none;padding:8px 16px;
                   border-radius:6px;cursor:pointer;">Update</button>
  </form>
</div>
</body>
</html>""")


@app.post("/demos/{demo_id}/status/form", response_class=HTMLResponse)
async def update_status_form(demo_id: str, status: str = Form(...)):
    if status not in STATUSES:
        raise HTTPException(400, "Invalid status")
    now = datetime.utcnow().isoformat()
    with db_conn() as conn:
        row = conn.execute("SELECT id FROM demos WHERE id=?", (demo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Demo not found")
        extra_cols = ""
        extra_vals = []
        if status == "running":
            extra_cols = ", started_at=?"
            extra_vals.append(now)
        elif status in ("completed", "failed"):
            extra_cols = ", completed_at=?"
            extra_vals.append(now)
        conn.execute(
            f"UPDATE demos SET status=?, updated_at=?{extra_cols} WHERE id=?",
            [status, now] + extra_vals + [demo_id],
        )
    return HTMLResponse(
        f'<html><head><meta http-equiv="refresh" content="1;url=/demos/{demo_id}/view">'
        '</head><body style="background:#1e293b;color:#22c55e;padding:20px;">'
        "Status updated. Redirecting...</body></html>"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(description="Live Demo Scheduler — OCI Robot Cloud")
    parser.add_argument("--port", type=int, default=8031, help="Port to listen on (default: 8031)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock mode: skip GPU reservation, allow overlapping bookings (CI-safe)",
    )
    parser.add_argument("--db", default=DB_PATH, help=f"SQLite DB path (default: {DB_PATH})")
    return parser.parse_args()


if __name__ == "__main__":
    if not HAS_FASTAPI:
        print("ERROR: fastapi and uvicorn are required. Install with:")
        print("  pip install fastapi uvicorn")
        sys.exit(1)

    args = parse_args()
    MOCK_MODE = args.mock
    if args.db != DB_PATH:
        DB_PATH = args.db  # type: ignore[assignment]

    init_db()

    print(f"OCI Robot Cloud — Live Demo Scheduler")
    print(f"  URL   : http://{args.host}:{args.port}")
    print(f"  DB    : {DB_PATH}")
    print(f"  Mock  : {MOCK_MODE}")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
