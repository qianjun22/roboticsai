"""
NVIDIA Partnership CRM — FastAPI service (port 8059)

Lightweight CRM for tracking the OCI Robot Cloud × NVIDIA partnership:
contacts, meetings, action items, and milestones.

Usage:
    python nvidia_crm.py                  # start server on port 8059
    python nvidia_crm.py --port 8060      # custom port
    python nvidia_crm.py --reset          # drop + re-seed database, then start

REST endpoints:
    GET  /                  HTML executive dashboard (dark theme)
    GET  /contacts          all NVIDIA contacts
    POST /contacts          add a contact
    GET  /meetings          all meetings (newest first)
    POST /meetings          log a meeting
    GET  /actions           all action items
    POST /actions           add an action item
    PATCH /actions/{id}     update action item status
    GET  /milestones        all partnership milestones
    PATCH /milestones/{id}  update milestone status / projected date
    GET  /health            relationship health score + breakdown
    GET  /nextsteps         top-3 most urgent next steps

Dependencies: fastapi, uvicorn (pip install fastapi uvicorn)
Database:     ./nvidia_crm.db  (SQLite, created automatically)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import textwrap
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PORT = 8059
DB_PATH = Path(__file__).parent / "nvidia_crm.db"

NVIDIA_TEAMS = [
    "Isaac", "GR00T", "Cosmos", "DGX", "Jetson", "Robotics Business",
]

CONTACT_RELATIONSHIPS = [
    "champion", "technical", "executive", "business-dev", "engineering",
]

ACTION_STATUSES = ["open", "in-progress", "done", "blocked"]
MILESTONE_STATUSES = ["not-started", "in-progress", "done"]

AGING_DAYS = 7  # action items older than this get a visual alert

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(reset: bool = False) -> None:
    with db() as conn:
        if reset:
            for t in ["contacts", "meetings", "meeting_attendees",
                      "actions", "milestones"]:
                conn.execute(f"DROP TABLE IF EXISTS {t}")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                team        TEXT NOT NULL,
                email       TEXT,
                relationship TEXT,
                last_contact_date TEXT,
                notes       TEXT,
                created_at  TEXT DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                attendees   TEXT NOT NULL,   -- JSON list of names
                agenda      TEXT,
                outcomes    TEXT,
                follow_ups  TEXT,            -- JSON list of {task, owner, due}
                created_at  TEXT DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS actions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task        TEXT NOT NULL,
                owner       TEXT NOT NULL,
                due         TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                meeting_id  INTEGER REFERENCES meetings(id),
                created_at  TEXT DEFAULT (date('now')),
                updated_at  TEXT DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                description     TEXT,
                status          TEXT NOT NULL DEFAULT 'not-started',
                projected_date  TEXT,
                completed_date  TEXT,
                created_at      TEXT DEFAULT (date('now'))
            );
        """)


def seed_db() -> None:
    """Insert realistic seed data if tables are empty."""
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] > 0:
            return  # already seeded

        today = date.today()

        # 6 NVIDIA contacts
        contacts = [
            ("Jim Binkley",       "Isaac",             "jbinkley@nvidia.com",  "technical",     (today - timedelta(days=5)).isoformat(),  "Lead Isaac Sim integration engineer"),
            ("Priya Shenoy",      "GR00T",             "pshenoy@nvidia.com",   "champion",      (today - timedelta(days=12)).isoformat(), "GR00T N1.5/N1.6 PM; strong OCI interest"),
            ("Derek Malloy",      "Cosmos",            "dmalloy@nvidia.com",   "engineering",   (today - timedelta(days=3)).isoformat(),  "Cosmos world model API access contact"),
            ("Aisha Okonkwo",     "DGX",               "aokonkwo@nvidia.com",  "business-dev",  (today - timedelta(days=20)).isoformat(), "DGX Cloud × OCI preferred-cloud discussions"),
            ("Sam Torres",        "Jetson",            "storres@nvidia.com",   "technical",     (today - timedelta(days=7)).isoformat(),  "Jetson Orin edge deploy; eval unit shipped"),
            ("Marcus Wei",        "Robotics Business", "mwei@nvidia.com",      "executive",     (today - timedelta(days=30)).isoformat(), "VP Robotics Business; GTC co-present sponsor"),
        ]
        conn.executemany(
            "INSERT INTO contacts (name, team, email, relationship, last_contact_date, notes) "
            "VALUES (?,?,?,?,?,?)", contacts
        )

        # 3 past meetings
        m1_date = (today - timedelta(days=28)).isoformat()
        m2_date = (today - timedelta(days=14)).isoformat()
        m3_date = (today - timedelta(days=3)).isoformat()

        m1_follow = json.dumps([
            {"task": "Share OCI GPU benchmark report with NVIDIA", "owner": "Jun Qian", "due": (today - timedelta(days=18)).isoformat()},
            {"task": "NVIDIA to provide GR00T N1.6 API access", "owner": "Priya Shenoy", "due": (today - timedelta(days=10)).isoformat()},
        ])
        m2_follow = json.dumps([
            {"task": "Draft co-engineering agreement term sheet", "owner": "Jun Qian", "due": (today + timedelta(days=7)).isoformat()},
            {"task": "Cosmos world model sandbox credentials", "owner": "Derek Malloy", "due": (today + timedelta(days=3)).isoformat()},
        ])
        m3_follow = json.dumps([
            {"task": "Submit GTC co-present abstract", "owner": "Jun Qian", "due": (today + timedelta(days=14)).isoformat()},
        ])

        conn.execute(
            "INSERT INTO meetings (date, attendees, agenda, outcomes, follow_ups) VALUES (?,?,?,?,?)",
            (m1_date, json.dumps(["Jun Qian", "Priya Shenoy", "Jim Binkley"]),
             "OCI Robot Cloud intro + GR00T fine-tuning demo",
             "NVIDIA impressed with OCI A100 perf (2.35 it/s). Agreed to explore joint SDG pipeline.",
             m1_follow)
        )
        conn.execute(
            "INSERT INTO meetings (date, attendees, agenda, outcomes, follow_ups) VALUES (?,?,?,?,?)",
            (m2_date, json.dumps(["Jun Qian", "Derek Malloy", "Aisha Okonkwo"]),
             "Cosmos integration + DGX preferred-cloud scoping",
             "DGX Cloud × OCI preferred-cloud path is viable. Cosmos sandbox access unblocked next sprint.",
             m2_follow)
        )
        conn.execute(
            "INSERT INTO meetings (date, attendees, agenda, outcomes, follow_ups) VALUES (?,?,?,?,?)",
            (m3_date, json.dumps(["Jun Qian", "Marcus Wei", "Priya Shenoy"]),
             "GTC 2026 co-presentation planning + partnership milestones review",
             "Marcus confirmed exec sponsorship for GTC slot. Need abstract submitted in 2 weeks.",
             m3_follow)
        )

        # 5 action items (3 open / in-progress, 2 done)
        actions = [
            ("Draft co-engineering agreement term sheet",       "Jun Qian",      (today + timedelta(days=7)).isoformat(),   "in-progress", None),
            ("Submit GTC 2026 co-present abstract",             "Jun Qian",      (today + timedelta(days=14)).isoformat(),  "open",        None),
            ("Cosmos world model sandbox credentials",           "Derek Malloy",  (today + timedelta(days=3)).isoformat(),   "open",        None),
            ("Share OCI GPU benchmark report with NVIDIA",      "Jun Qian",      (today - timedelta(days=18)).isoformat(),  "done",        None),
            ("NVIDIA GR00T N1.6 API access provisioned",        "Priya Shenoy",  (today - timedelta(days=10)).isoformat(),  "done",        None),
        ]
        conn.executemany(
            "INSERT INTO actions (task, owner, due, status, meeting_id) VALUES (?,?,?,?,?)",
            actions
        )

        # 4 formal partnership milestones
        milestones = [
            ("Co-Engineering Agreement",
             "Signed agreement for joint SDG pipeline and GR00T fine-tuning on OCI",
             "in-progress", (today + timedelta(days=30)).isoformat(), None),
            ("OCI as NVIDIA Preferred Cloud for Robotics",
             "NVIDIA designates OCI as recommended cloud for Isaac/GR00T workloads",
             "not-started", (today + timedelta(days=90)).isoformat(), None),
            ("GTC 2026 Co-Presentation",
             "Joint keynote / breakout session at GTC Spring 2026",
             "in-progress", (today + timedelta(days=14)).isoformat(), None),
            ("Joint Closed-Loop Eval on OCI",
             "Publish shared benchmark: GR00T on Isaac Sim running OCI A100",
             "not-started", (today + timedelta(days=60)).isoformat(), None),
        ]
        conn.executemany(
            "INSERT INTO milestones (name, description, status, projected_date, completed_date) "
            "VALUES (?,?,?,?,?)",
            milestones
        )


# ---------------------------------------------------------------------------
# Business logic helpers
# ---------------------------------------------------------------------------

def compute_health(conn: sqlite3.Connection) -> Dict[str, Any]:
    today = date.today()

    # Meeting frequency: meetings in last 30 days (max score 40)
    cutoff_30 = (today - timedelta(days=30)).isoformat()
    recent_meetings = conn.execute(
        "SELECT COUNT(*) FROM meetings WHERE date >= ?", (cutoff_30,)
    ).fetchone()[0]
    meeting_score = min(recent_meetings * 15, 40)

    # Open/overdue action items (penalty)
    open_actions = conn.execute(
        "SELECT COUNT(*) FROM actions WHERE status NOT IN ('done')"
    ).fetchone()[0]
    overdue_actions = conn.execute(
        "SELECT COUNT(*) FROM actions WHERE status NOT IN ('done') AND due < ?",
        (today.isoformat(),)
    ).fetchone()[0]
    action_score = max(0, 30 - open_actions * 3 - overdue_actions * 5)

    # Milestone progress
    total_ms = conn.execute("SELECT COUNT(*) FROM milestones").fetchone()[0]
    done_ms = conn.execute(
        "SELECT COUNT(*) FROM milestones WHERE status = 'done'"
    ).fetchone()[0]
    inprog_ms = conn.execute(
        "SELECT COUNT(*) FROM milestones WHERE status = 'in-progress'"
    ).fetchone()[0]
    ms_score = 0 if total_ms == 0 else int(
        30 * (done_ms + 0.5 * inprog_ms) / total_ms
    )

    total = meeting_score + action_score + ms_score

    return {
        "score": total,
        "max": 100,
        "grade": "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D",
        "breakdown": {
            "meeting_frequency": {"score": meeting_score, "max": 40,
                                  "recent_meetings": recent_meetings},
            "action_items":      {"score": action_score, "max": 30,
                                  "open": open_actions, "overdue": overdue_actions},
            "milestones":        {"score": ms_score, "max": 30,
                                  "done": done_ms, "in_progress": inprog_ms,
                                  "total": total_ms},
        },
    }


def compute_nextsteps(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    today = date.today()
    items: List[Dict[str, Any]] = []

    # Overdue actions
    rows = conn.execute(
        "SELECT id, task, owner, due, status FROM actions "
        "WHERE status NOT IN ('done') AND due < ? ORDER BY due LIMIT 5",
        (today.isoformat(),)
    ).fetchall()
    for r in rows:
        items.append({"priority": 1, "type": "action",
                      "label": f"[OVERDUE] {r['task']} (owner: {r['owner']}, due: {r['due']})",
                      "id": r["id"]})

    # Blocked actions
    rows = conn.execute(
        "SELECT id, task, owner, due FROM actions WHERE status = 'blocked' ORDER BY due LIMIT 3"
    ).fetchall()
    for r in rows:
        items.append({"priority": 2, "type": "action",
                      "label": f"[BLOCKED] {r['task']} (owner: {r['owner']})",
                      "id": r["id"]})

    # Due soon (within 7 days)
    soon = (today + timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT id, task, owner, due FROM actions "
        "WHERE status NOT IN ('done','blocked') AND due >= ? AND due <= ? ORDER BY due LIMIT 5",
        (today.isoformat(), soon)
    ).fetchall()
    for r in rows:
        items.append({"priority": 3, "type": "action",
                      "label": f"[DUE SOON] {r['task']} — due {r['due']} (owner: {r['owner']})",
                      "id": r["id"]})

    # Milestones approaching
    rows = conn.execute(
        "SELECT id, name, projected_date FROM milestones "
        "WHERE status != 'done' AND projected_date <= ? ORDER BY projected_date LIMIT 3",
        (soon,)
    ).fetchall()
    for r in rows:
        items.append({"priority": 2, "type": "milestone",
                      "label": f"[MILESTONE] {r['name']} — projected {r['projected_date']}",
                      "id": r["id"]})

    # Sort and return top 3
    items.sort(key=lambda x: x["priority"])
    return items[:3]


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for key in ("attendees", "follow_ups"):
        if key in d and d[key]:
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def aging_flag(due: str, status: str) -> bool:
    if status == "done":
        return False
    try:
        return (date.today() - date.fromisoformat(due)).days > AGING_DAYS
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

if HAS_DEPS:
    class ContactIn(BaseModel):
        name: str
        team: str
        email: Optional[str] = None
        relationship: Optional[str] = None
        last_contact_date: Optional[str] = None
        notes: Optional[str] = None

    class MeetingIn(BaseModel):
        date: str
        attendees: List[str]
        agenda: Optional[str] = None
        outcomes: Optional[str] = None
        follow_ups: Optional[List[Dict[str, str]]] = None

    class ActionIn(BaseModel):
        task: str
        owner: str
        due: str
        status: str = "open"
        meeting_id: Optional[int] = None

    class ActionPatch(BaseModel):
        status: Optional[str] = None
        due: Optional[str] = None
        owner: Optional[str] = None

    class MilestonePatch(BaseModel):
        status: Optional[str] = None
        projected_date: Optional[str] = None
        completed_date: Optional[str] = None

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_STYLE = """
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #76b900;
    --danger: #f85149; --warn: #d29922; --ok: #3fb950; --info: #58a6ff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }
  header { background: var(--surface); border-bottom:1px solid var(--border); padding:16px 32px; display:flex; align-items:center; gap:16px; }
  header h1 { font-size:20px; font-weight:600; }
  header .sub { color:var(--muted); font-size:13px; }
  .badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
  .badge-ok      { background:#1a3a1f; color:var(--ok); }
  .badge-warn    { background:#3a2a0a; color:var(--warn); }
  .badge-danger  { background:#3a1010; color:var(--danger); }
  .badge-info    { background:#0d2137; color:var(--info); }
  .badge-muted   { background:#1a1f26; color:var(--muted); }
  .badge-accent  { background:#1a2e0a; color:var(--accent); }
  main { padding:24px 32px; display:grid; gap:24px; }
  .row2 { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
  .row3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:24px; }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:20px; }
  .card h2 { font-size:15px; font-weight:600; margin-bottom:16px; display:flex; align-items:center; gap:8px; }
  .card h2 .count { color:var(--muted); font-weight:400; font-size:12px; }
  table { width:100%; border-collapse:collapse; }
  th { text-align:left; color:var(--muted); font-weight:500; font-size:12px; padding:6px 8px; border-bottom:1px solid var(--border); }
  td { padding:8px; border-bottom:1px solid #1e242c; vertical-align:top; }
  tr:last-child td { border-bottom:none; }
  .health-gauge { display:flex; flex-direction:column; align-items:center; gap:8px; }
  .gauge-circle { width:110px; height:110px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-direction:column; border:6px solid; }
  .gauge-score { font-size:32px; font-weight:700; }
  .gauge-grade { font-size:14px; color:var(--muted); }
  .health-breakdown { width:100%; margin-top:12px; }
  .hb-row { display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid #1e242c; font-size:12px; }
  .hb-row:last-child { border-bottom:none; }
  .progress-bar { height:6px; background:#1e242c; border-radius:3px; flex:1; margin:0 10px; }
  .progress-fill { height:100%; border-radius:3px; background:var(--accent); }
  .ms-item { padding:10px 0; border-bottom:1px solid #1e242c; }
  .ms-item:last-child { border-bottom:none; }
  .ms-name { font-weight:500; margin-bottom:4px; }
  .ms-desc { color:var(--muted); font-size:12px; margin-bottom:6px; }
  .ms-meta { display:flex; gap:8px; align-items:center; font-size:12px; }
  .next-item { padding:8px 10px; border-radius:6px; margin-bottom:6px; font-size:13px; border-left:3px solid; }
  .next-overdue  { background:#1c1010; border-color:var(--danger); }
  .next-blocked  { background:#1c1810; border-color:var(--warn); }
  .next-soon     { background:#0d1820; border-color:var(--info); }
  .next-ms       { background:#0d1c0d; border-color:var(--accent); }
  .aging { color:var(--warn); font-weight:600; }
  .api-list { margin-top:4px; }
  .api-list li { list-style:none; padding:3px 0; font-size:12px; color:var(--muted); border-bottom:1px solid #1e242c; }
  .api-list li:last-child { border-bottom:none; }
  .tag { display:inline-block; padding:1px 6px; border-radius:4px; font-size:11px; margin-right:3px; }
  .tag-isaac   { background:#0d2137; color:#58a6ff; }
  .tag-groot   { background:#1a3a1f; color:#3fb950; }
  .tag-cosmos  { background:#2a1a3a; color:#bc8cff; }
  .tag-dgx     { background:#3a2a0a; color:#d29922; }
  .tag-jetson  { background:#1a2e0a; color:#76b900; }
  .tag-rb      { background:#2a1a1a; color:#f85149; }
</style>
"""

def team_tag(team: str) -> str:
    cls = {
        "Isaac": "tag-isaac",
        "GR00T": "tag-groot",
        "Cosmos": "tag-cosmos",
        "DGX": "tag-dgx",
        "Jetson": "tag-jetson",
        "Robotics Business": "tag-rb",
    }.get(team, "tag-isaac")
    return f'<span class="tag {cls}">{team}</span>'


def status_badge(status: str) -> str:
    mapping = {
        "open":        ("badge-warn",   "open"),
        "in-progress": ("badge-info",   "in-progress"),
        "done":        ("badge-ok",     "done"),
        "blocked":     ("badge-danger", "blocked"),
        "not-started": ("badge-muted",  "not-started"),
    }
    cls, label = mapping.get(status, ("badge-muted", status))
    return f'<span class="badge {cls}">{label}</span>'


def build_dashboard(conn: sqlite3.Connection) -> str:
    today = date.today()

    # --- contacts ---
    contacts = [row_to_dict(r) for r in
                conn.execute("SELECT * FROM contacts ORDER BY last_contact_date DESC").fetchall()]

    contacts_html = "<table><thead><tr><th>Name</th><th>Team</th><th>Role</th><th>Last Contact</th><th>Notes</th></tr></thead><tbody>"
    for c in contacts:
        lc = c.get("last_contact_date") or ""
        try:
            delta = (today - date.fromisoformat(lc)).days
            lc_str = f"{lc} <span style='color:var(--muted);font-size:11px'>({delta}d ago)</span>"
            lc_color = "var(--danger)" if delta > 30 else "var(--warn)" if delta > 14 else "var(--ok)"
            lc_str = f"<span style='color:{lc_color}'>{lc_str}</span>"
        except ValueError:
            lc_str = lc
        contacts_html += (
            f"<tr><td><strong>{c['name']}</strong><br>"
            f"<span style='color:var(--muted);font-size:11px'>{c.get('email','')}</span></td>"
            f"<td>{team_tag(c['team'])}</td>"
            f"<td><span style='color:var(--muted)'>{c.get('relationship','')}</span></td>"
            f"<td>{lc_str}</td>"
            f"<td style='color:var(--muted);font-size:12px'>{c.get('notes','')}</td></tr>"
        )
    contacts_html += "</tbody></table>"

    # --- action items ---
    actions = [row_to_dict(r) for r in
               conn.execute("SELECT * FROM actions ORDER BY CASE status WHEN 'blocked' THEN 0 WHEN 'open' THEN 1 WHEN 'in-progress' THEN 2 ELSE 3 END, due ASC").fetchall()]

    actions_html = "<table><thead><tr><th>Task</th><th>Owner</th><th>Due</th><th>Status</th></tr></thead><tbody>"
    for a in actions:
        aged = aging_flag(a.get("due", ""), a.get("status", ""))
        due_str = a.get("due", "")
        try:
            dd = date.fromisoformat(due_str)
            delta = (today - dd).days
            if a["status"] != "done" and delta > 0:
                due_str = f'<span class="aging">{due_str} ({delta}d overdue)</span>'
            elif a["status"] != "done" and delta <= 0 and abs(delta) <= 7:
                due_str = f'<span style="color:var(--info)">{due_str}</span>'
        except ValueError:
            pass
        actions_html += (
            f"<tr><td>{a['task']}"
            + (' <span style="color:var(--warn);font-size:10px">[aging]</span>' if aged else "")
            + f"</td><td>{a.get('owner','')}</td><td>{due_str}</td>"
            f"<td>{status_badge(a.get('status','open'))}</td></tr>"
        )
    actions_html += "</tbody></table>"

    # --- milestones ---
    milestones = [row_to_dict(r) for r in
                  conn.execute("SELECT * FROM milestones ORDER BY projected_date").fetchall()]

    ms_html = ""
    for m in milestones:
        proj = m.get("projected_date") or "TBD"
        try:
            delta = (date.fromisoformat(proj) - today).days
            proj_note = f"{proj} (in {delta}d)" if delta >= 0 else f"{proj} ({abs(delta)}d ago)"
        except ValueError:
            proj_note = proj
        ms_html += (
            f'<div class="ms-item">'
            f'<div class="ms-name">{m["name"]}</div>'
            f'<div class="ms-desc">{m.get("description","")}</div>'
            f'<div class="ms-meta">{status_badge(m.get("status","not-started"))}'
            f'<span style="color:var(--muted)">Projected: {proj_note}</span></div>'
            f'</div>'
        )

    # --- health ---
    health = compute_health(conn)
    score = health["score"]
    grade_color = (
        "var(--ok)" if score >= 85 else
        "var(--accent)" if score >= 70 else
        "var(--warn)" if score >= 55 else
        "var(--danger)"
    )
    bk = health["breakdown"]
    health_html = f"""
    <div class="health-gauge">
      <div class="gauge-circle" style="border-color:{grade_color}">
        <span class="gauge-score" style="color:{grade_color}">{score}</span>
        <span class="gauge-grade">Grade {health['grade']}</span>
      </div>
    </div>
    <div class="health-breakdown">
      <div class="hb-row">
        <span>Meeting Frequency</span>
        <div class="progress-bar"><div class="progress-fill" style="width:{bk['meeting_frequency']['score']/40*100:.0f}%"></div></div>
        <span>{bk['meeting_frequency']['score']}/40</span>
      </div>
      <div class="hb-row">
        <span>Action Items</span>
        <div class="progress-bar"><div class="progress-fill" style="width:{bk['action_items']['score']/30*100:.0f}%"></div></div>
        <span>{bk['action_items']['score']}/30</span>
      </div>
      <div class="hb-row">
        <span>Milestones</span>
        <div class="progress-bar"><div class="progress-fill" style="width:{bk['milestones']['score']/30*100:.0f}%"></div></div>
        <span>{bk['milestones']['score']}/30</span>
      </div>
    </div>
    <div style="margin-top:12px;font-size:12px;color:var(--muted)">
      {bk['meeting_frequency']['recent_meetings']} meetings (30d) &nbsp;·&nbsp;
      {bk['action_items']['open']} open actions &nbsp;·&nbsp;
      {bk['action_items']['overdue']} overdue &nbsp;·&nbsp;
      {bk['milestones']['done']}/{bk['milestones']['total']} milestones done
    </div>
    """

    # --- next steps ---
    nextsteps = compute_nextsteps(conn)
    if not nextsteps:
        ns_html = '<p style="color:var(--ok);font-size:13px">All clear — no urgent items.</p>'
    else:
        ns_html = ""
        for item in nextsteps:
            label = item["label"]
            if "[OVERDUE]" in label:
                cls = "next-overdue"
            elif "[BLOCKED]" in label:
                cls = "next-blocked"
            elif "[DUE SOON]" in label:
                cls = "next-soon"
            else:
                cls = "next-ms"
            ns_html += f'<div class="next-item {cls}">{label}</div>'

    # --- meetings summary ---
    meetings = [row_to_dict(r) for r in
                conn.execute("SELECT * FROM meetings ORDER BY date DESC LIMIT 3").fetchall()]
    meet_html = "<table><thead><tr><th>Date</th><th>Attendees</th><th>Outcomes</th></tr></thead><tbody>"
    for m in meetings:
        att = m.get("attendees") or []
        att_str = ", ".join(att) if isinstance(att, list) else str(att)
        meet_html += (
            f"<tr><td style='white-space:nowrap'>{m['date']}</td>"
            f"<td style='font-size:12px;color:var(--muted)'>{att_str}</td>"
            f"<td style='font-size:12px'>{m.get('outcomes','')}</td></tr>"
        )
    meet_html += "</tbody></table>"

    # --- REST API reference ---
    api_ref = """
    <ul class="api-list">
      <li>GET  /contacts — list all contacts</li>
      <li>POST /contacts — add contact</li>
      <li>GET  /meetings — list all meetings</li>
      <li>POST /meetings — log meeting</li>
      <li>GET  /actions — list action items</li>
      <li>POST /actions — add action item</li>
      <li>PATCH /actions/{id} — update status/due/owner</li>
      <li>GET  /milestones — list milestones</li>
      <li>PATCH /milestones/{id} — update status/date</li>
      <li>GET  /health — health score JSON</li>
      <li>GET  /nextsteps — top-3 urgent items</li>
    </ul>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>NVIDIA Partnership CRM</title>
  {DASHBOARD_STYLE}
</head>
<body>
<header>
  <div>
    <h1>NVIDIA Partnership CRM</h1>
    <div class="sub">OCI Robot Cloud × NVIDIA — Relationship Dashboard &nbsp;·&nbsp; {today.isoformat()}</div>
  </div>
  <div style="margin-left:auto;display:flex;gap:12px;align-items:center">
    <span class="badge badge-accent" style="font-size:13px;padding:4px 14px">Score: {score}/100 ({health['grade']})</span>
  </div>
</header>
<main>
  <div class="row2">
    <div class="card">
      <h2>Health Score <span class="count">composite</span></h2>
      {health_html}
    </div>
    <div class="card">
      <h2>Next Steps <span class="count">top 3 urgent</span></h2>
      {ns_html}
      <div style="margin-top:20px">
        <h2 style="margin-bottom:10px">REST API</h2>
        {api_ref}
      </div>
    </div>
  </div>

  <div class="card">
    <h2>NVIDIA Contacts <span class="count">{len(contacts)} tracked</span></h2>
    {contacts_html}
  </div>

  <div class="row2">
    <div class="card">
      <h2>Action Items <span class="count">{len(actions)} total</span></h2>
      {actions_html}
    </div>
    <div class="card">
      <h2>Partnership Milestones <span class="count">{len(milestones)} formal</span></h2>
      {ms_html}
    </div>
  </div>

  <div class="card">
    <h2>Recent Meetings <span class="count">last 3</span></h2>
    {meet_html}
  </div>
</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_DEPS:
    app = FastAPI(
        title="NVIDIA Partnership CRM",
        description="Lightweight CRM for OCI Robot Cloud × NVIDIA partnership tracking",
        version="1.0.0",
    )

    @app.on_event("startup")
    def on_startup():
        init_db()
        seed_db()

    # --- HTML dashboard ---
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        with db() as conn:
            return build_dashboard(conn)

    # --- Contacts ---
    @app.get("/contacts")
    def list_contacts():
        with db() as conn:
            rows = conn.execute("SELECT * FROM contacts ORDER BY last_contact_date DESC").fetchall()
            return [row_to_dict(r) for r in rows]

    @app.post("/contacts", status_code=201)
    def add_contact(c: ContactIn):
        if c.team not in NVIDIA_TEAMS:
            raise HTTPException(400, f"team must be one of: {NVIDIA_TEAMS}")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO contacts (name, team, email, relationship, last_contact_date, notes) "
                "VALUES (?,?,?,?,?,?)",
                (c.name, c.team, c.email, c.relationship, c.last_contact_date, c.notes)
            )
            return {"id": cur.lastrowid, **c.dict()}

    # --- Meetings ---
    @app.get("/meetings")
    def list_meetings():
        with db() as conn:
            rows = conn.execute("SELECT * FROM meetings ORDER BY date DESC").fetchall()
            return [row_to_dict(r) for r in rows]

    @app.post("/meetings", status_code=201)
    def add_meeting(m: MeetingIn):
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO meetings (date, attendees, agenda, outcomes, follow_ups) VALUES (?,?,?,?,?)",
                (m.date, json.dumps(m.attendees), m.agenda, m.outcomes,
                 json.dumps(m.follow_ups) if m.follow_ups else None)
            )
            return {"id": cur.lastrowid, **m.dict()}

    # --- Action Items ---
    @app.get("/actions")
    def list_actions():
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM actions ORDER BY "
                "CASE status WHEN 'blocked' THEN 0 WHEN 'open' THEN 1 WHEN 'in-progress' THEN 2 ELSE 3 END, due ASC"
            ).fetchall()
            result = []
            for r in rows:
                d = row_to_dict(r)
                d["aging"] = aging_flag(d.get("due", ""), d.get("status", ""))
                result.append(d)
            return result

    @app.post("/actions", status_code=201)
    def add_action(a: ActionIn):
        if a.status not in ACTION_STATUSES:
            raise HTTPException(400, f"status must be one of: {ACTION_STATUSES}")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO actions (task, owner, due, status, meeting_id) VALUES (?,?,?,?,?)",
                (a.task, a.owner, a.due, a.status, a.meeting_id)
            )
            return {"id": cur.lastrowid, **a.dict()}

    @app.patch("/actions/{action_id}")
    def update_action(action_id: int, patch: ActionPatch):
        with db() as conn:
            row = conn.execute("SELECT id FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Action item not found")
            updates = {k: v for k, v in patch.dict().items() if v is not None}
            if not updates:
                raise HTTPException(400, "No fields to update")
            if "status" in updates and updates["status"] not in ACTION_STATUSES:
                raise HTTPException(400, f"status must be one of: {ACTION_STATUSES}")
            updates["updated_at"] = date.today().isoformat()
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE actions SET {set_clause} WHERE id=?",
                (*updates.values(), action_id)
            )
            return row_to_dict(conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())

    # --- Milestones ---
    @app.get("/milestones")
    def list_milestones():
        with db() as conn:
            rows = conn.execute("SELECT * FROM milestones ORDER BY projected_date").fetchall()
            return [row_to_dict(r) for r in rows]

    @app.patch("/milestones/{ms_id}")
    def update_milestone(ms_id: int, patch: MilestonePatch):
        with db() as conn:
            row = conn.execute("SELECT id FROM milestones WHERE id=?", (ms_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Milestone not found")
            updates = {k: v for k, v in patch.dict().items() if v is not None}
            if not updates:
                raise HTTPException(400, "No fields to update")
            if "status" in updates and updates["status"] not in MILESTONE_STATUSES:
                raise HTTPException(400, f"status must be one of: {MILESTONE_STATUSES}")
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE milestones SET {set_clause} WHERE id=?",
                (*updates.values(), ms_id)
            )
            return row_to_dict(conn.execute("SELECT * FROM milestones WHERE id=?", (ms_id,)).fetchone())

    # --- Health + Next Steps ---
    @app.get("/health")
    def health_score():
        with db() as conn:
            return compute_health(conn)

    @app.get("/nextsteps")
    def next_steps():
        with db() as conn:
            return compute_nextsteps(conn)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NVIDIA Partnership CRM (port 8059)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--reset", action="store_true",
                        help="Drop and re-seed the database before starting")
    args = parser.parse_args()

    if not HAS_DEPS:
        print("Missing dependencies. Run: pip install fastapi uvicorn")
        raise SystemExit(1)

    init_db(reset=args.reset)
    seed_db()
    print(f"NVIDIA CRM starting on http://{args.host}:{args.port}")
    print(f"  Dashboard:  http://localhost:{args.port}/")
    print(f"  Health:     http://localhost:{args.port}/health")
    print(f"  API docs:   http://localhost:{args.port}/docs")
    uvicorn.run("nvidia_crm:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
