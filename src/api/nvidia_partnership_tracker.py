"""
NVIDIA Partnership Pipeline Tracker — FastAPI service (port 8058)

CRM-style tracker for the Oracle-NVIDIA robotics co-engineering relationship.
Tracks every touchpoint, action item, and milestone from first contact through
GTC co-presentation and preferred-cloud announcement.

Usage:
    python nvidia_partnership_tracker.py               # start on port 8058
    python nvidia_partnership_tracker.py --port 8060   # custom port
    python nvidia_partnership_tracker.py --reset       # drop + re-seed DB, then start

REST endpoints:
    GET  /                          HTML executive dashboard (dark theme)
    GET  /status                    JSON executive summary (for Slack/email bots)
    GET  /contacts                  all NVIDIA contacts
    POST /contacts                  add a contact
    GET  /touchpoints               all touchpoints (newest first)
    POST /touchpoints               log a touchpoint
    GET  /actions                   all action items (optionally ?owner=Oracle|NVIDIA)
    POST /actions                   add an action item
    PATCH /actions/{id}             update action item status/notes
    GET  /milestones                all 8 partnership milestones
    PATCH /milestones/{id}          update milestone status / projected date
    GET  /integrations              per-product technical integration status
    PATCH /integrations/{id}        update integration status
    GET  /health                    200 OK liveness probe

Dependencies: fastapi, uvicorn  (pip install fastapi uvicorn)
Database:     ./nvidia_partnership_tracker.db  (SQLite, auto-created)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import textwrap
from contextlib import contextmanager
from datetime import date, datetime
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

PORT = 8058
DB_PATH = Path(__file__).parent / "nvidia_partnership_tracker.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _rows(conn, sql: str, params=()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn, sql: str, params=()) -> Optional[Dict[str, Any]]:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------------------
# Schema + seed data
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    title       TEXT NOT NULL,
    team        TEXT NOT NULL,   -- Isaac | GR00T | Cosmos | DGX | Jetson | DevRel | BizDev
    email       TEXT,
    linkedin    TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS touchpoints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tp_date     TEXT NOT NULL,
    tp_type     TEXT NOT NULL,   -- meeting | email | demo | shared_doc | call | conference
    title       TEXT NOT NULL,
    participants TEXT,           -- comma-separated names
    outcome     TEXT,
    follow_up   TEXT,
    contact_ids TEXT,            -- JSON array of contact ids
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,   -- Oracle | NVIDIA
    title       TEXT NOT NULL,
    description TEXT,
    due_date    TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | in_progress | done | blocked
    priority    TEXT NOT NULL DEFAULT 'medium',   -- high | medium | low
    touchpoint_id INTEGER,
    notes       TEXT,
    created_at  TEXT DEFAULT (date('now')),
    updated_at  TEXT DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS milestones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    seq             INTEGER NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'planned',  -- planned | in_progress | done
    projected_date  TEXT,
    actual_date     TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS integrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product     TEXT NOT NULL,   -- Isaac Sim 4.5 | GR00T N1.6 | Cosmos 7B | DGX OCI | Jetson
    area        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'planned',  -- planned | in_progress | done
    owner       TEXT,
    notes       TEXT,
    updated_at  TEXT DEFAULT (date('now'))
);
"""

SEED_CONTACTS = [
    ("Rev Lebaredian", "VP Omniverse & Simulation Technology", "Isaac", "rev@nvidia.com", "", "Isaac Sim lead; key technical champion for OCI SDG pipeline"),
    ("Jim Fan", "Senior Research Scientist, Embodied AI", "GR00T", "jfan@nvidia.com", "", "GR00T N1 lead; co-author of GR00T paper; target for fine-tuning collaboration"),
    ("Linxi 'Jim' Fan", "Research Lead, GEAR lab", "GR00T", "linxifan@nvidia.com", "", "Alias for Jim Fan — robotics foundation model track"),
    ("Hassan Salami", "Sr Director, Cosmos Platform", "Cosmos", "hsalami@nvidia.com", "", "Cosmos world-model team; coordinate on OCI inference hosting"),
    ("Ian Buck", "VP HPC & Hyperscale", "DGX", "ibuck@nvidia.com", "", "DGX Cloud partnership anchor; preferred-cloud discussions"),
    ("Deepu Talla", "VP Robotics & Edge", "Jetson", "dtalla@nvidia.com", "", "Jetson Orin PM; Jetson-on-OCI joint reference arch"),
    ("Cheryl Jez", "Director, Developer Relations — Robotics", "DevRel", "cjez@nvidia.com", "", "GTC speaker coordination; Isaac Gym dev community"),
    ("Jeff Herbst", "VP Business Development", "BizDev", "jherbst@nvidia.com", "", "Alliance & preferred-cloud commercial track"),
]

SEED_MILESTONES = [
    (1, "First Contact — Intro Call", "Initial meeting between Oracle Cloud and NVIDIA robotics leadership to explore partnership", "done", "2026-01-15", "2026-01-15", "Call went well; NVIDIA interested in OCI GPU capacity for GR00T training"),
    (2, "Technical Alignment — Isaac Sim on OCI", "Confirm Isaac Sim 4.5 runs on OCI A100/H100; share benchmark results", "done", "2026-02-01", "2026-02-03", "Isaac Sim 4.5 Docker image validated on OCI BM.GPU.A100.8 — 2.35 it/s SDG"),
    (3, "GR00T Fine-Tuning Demo", "Live demo of GR00T N1.6 fine-tuning pipeline on OCI; share MAE=0.013 results", "in_progress", "2026-04-10", None, "Demo environment ready; scheduling with Jim Fan's team"),
    (4, "Co-Engineering Agreement Signed", "Formal co-engineering MOU or NDA-level technical collaboration agreement", "planned", "2026-05-15", None, "BizDev intro needed first; Jeff Herbst is the contact"),
    (5, "Joint Reference Architecture Published", "Publish OCI Robot Cloud × NVIDIA reference arch doc on both oracle.com and developer.nvidia.com", "planned", "2026-06-01", None, "Waiting on co-eng agreement"),
    (6, "GTC Co-Presentation Abstract Submitted", "Submit joint GTC 2027 talk proposal: 'Fine-Tuning Humanoid Robots at Scale on OCI'", "in_progress", "2026-04-30", None, "Draft abstract written; needs NVIDIA co-author confirmation"),
    (7, "Preferred Cloud for NVIDIA Robotics Workloads", "NVIDIA names OCI as recommended cloud for Isaac Sim + GR00T training in official docs", "planned", "2026-09-01", None, "Commercial discussions with Ian Buck needed"),
    (8, "Public GTC Announcement & Press Release", "Joint press release at GTC 2027 announcing Oracle-NVIDIA robotics cloud partnership", "planned", "2027-03-15", None, "End-state goal — all prior milestones are prerequisites"),
]

SEED_TOUCHPOINTS = [
    ("2026-01-15", "call", "Intro Call: Oracle Cloud × NVIDIA Robotics",
     "Jun Qian (Oracle), Jeff Herbst (NVIDIA), Cheryl Jez (NVIDIA)",
     "NVIDIA confirmed strong interest in OCI as training cloud for GR00T N1 and Isaac Sim SDG workloads. "
     "NVIDIA requested Oracle share benchmark numbers and a working demo.",
     "Oracle to send A100 benchmark sheet + Isaac Sim SDG demo video within 2 weeks."),
    ("2026-02-10", "email", "CEO Pitch Deck Shared with NVIDIA BizDev",
     "Jun Qian (Oracle) → Jeff Herbst (NVIDIA)",
     "Sent OCI_Robot_Cloud_Deck_2026.pptx (12-slide deck) and AI World deck to Jeff Herbst. "
     "Deck covers GR00T fine-tuning pipeline, DAgger results, multi-GPU DDP perf, and pricing.",
     "Follow up in 1 week if no response. CC Ian Buck on next outreach."),
    ("2026-03-20", "shared_doc", "GTC 2027 Co-Presentation Abstract Drafted",
     "Jun Qian (Oracle), Cheryl Jez (NVIDIA)",
     "Drafted joint GTC abstract: 'Fine-Tuning Humanoid Robots at Scale on OCI with GR00T N1.6'. "
     "Abstract covers 8.7× MAE improvement, DAgger pipeline, and Isaac Sim SDG at OCI. "
     "Cheryl reviewed draft and provided edits; NVIDIA internal approval needed.",
     "Cheryl to get Jim Fan's sign-off by April 15. Oracle to register as GTC exhibitor."),
]

SEED_ACTIONS = [
    # Oracle-owned
    ("Oracle", "Send Isaac Sim A100 benchmark report to NVIDIA", "Full benchmark: throughput (2.35 it/s), GPU util (87%), cost ($0.0043/10k steps), latency (227ms inference). Format as 1-pager PDF.", "2026-04-05", "pending", "high"),
    ("Oracle", "Schedule live GR00T fine-tune demo with Jim Fan", "Demo: Genesis SDG → LeRobot dataset → GR00T finetune (MAE 0.013) → closed-loop eval. Run on OCI A100×8 node.", "2026-04-10", "pending", "high"),
    ("Oracle", "Publish pip-installable SDK (oci-robot-cloud) to PyPI", "SDK wraps inference (port 8001), data collection (port 8003), training monitor (port 8080). Needed for joint reference arch.", "2026-04-20", "in_progress", "medium"),
    # NVIDIA-owned
    ("NVIDIA", "Provide Isaac Sim 4.5 OCI optimization guide", "NVIDIA to share internal perf tuning notes for running Isaac Sim 4.5 headless on non-RTX cloud GPUs (A100/H100).", "2026-04-15", "pending", "high"),
    ("NVIDIA", "Confirm GTC co-presentation abstract", "Jim Fan or Cheryl Jez to confirm co-authorship and submit abstract through NVIDIA GTC portal by April 30.", "2026-04-30", "pending", "medium"),
]

SEED_INTEGRATIONS = [
    ("Isaac Sim 4.5", "Docker container on OCI BM.GPU.A100.8", "done", "Oracle Robotics Eng", "Validated 2.35 it/s SDG; 87% GPU utilization"),
    ("Isaac Sim 4.5", "RTX domain randomization SDG pipeline", "done", "Oracle Robotics Eng", "Integrated into ~/Downloads/roboticsai/scripts/sdg/"),
    ("Isaac Sim 4.5", "Replicator synthetic data export to LeRobot", "done", "Oracle Robotics Eng", "HDF5 export pipeline complete; min 10 frames guard"),
    ("GR00T N1.6", "Inference server (port 8001)", "done", "Oracle Robotics Eng", "227ms latency, 6.7GB VRAM, running on OCI"),
    ("GR00T N1.6", "Fine-tuning pipeline (LeRobot → GR00T finetune)", "done", "Oracle Robotics Eng", "MAE 0.013 (8.7× vs baseline); 2.35 it/s; commit 624cdf4"),
    ("GR00T N1.6", "Fine-tuning documentation from NVIDIA", "planned", "NVIDIA GR00T Team", "Requested from Jim Fan — needed for joint reference arch"),
    ("Cosmos 7B", "World model inference on OCI", "in_progress", "Oracle Robotics Eng", "Cosmos integration scripted in session 7; weights download pending NVIDIA confirmation"),
    ("Cosmos 7B", "OCI inference hosting (preferred cloud)", "planned", "Oracle + NVIDIA Cosmos Team", "Requires preferred-cloud agreement (Milestone 7)"),
    ("DGX OCI", "DGX Cloud on OCI commercial offering", "planned", "Oracle BizDev + Ian Buck", "Pending co-engineering agreement (Milestone 4)"),
    ("Jetson", "Jetson Orin deploy script", "done", "Oracle Robotics Eng", "jetson_deploy.py complete; tested with GR00T N1.6 quantized"),
    ("Jetson", "Jetson-on-OCI reference architecture", "planned", "Oracle + NVIDIA Jetson Team", "Joint doc needed; Deepu Talla is the contact"),
]


def init_db(reset: bool = False) -> None:
    with _db() as conn:
        if reset:
            for tbl in ("contacts", "touchpoints", "actions", "milestones", "integrations"):
                conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        conn.executescript(SCHEMA)

        # Seed only if tables are empty
        if not _one(conn, "SELECT 1 FROM contacts LIMIT 1"):
            for c in SEED_CONTACTS:
                conn.execute(
                    "INSERT INTO contacts (name, title, team, email, linkedin, notes) VALUES (?,?,?,?,?,?)", c
                )

        if not _one(conn, "SELECT 1 FROM milestones LIMIT 1"):
            for m in SEED_MILESTONES:
                conn.execute(
                    "INSERT INTO milestones (seq, title, description, status, projected_date, actual_date, notes) VALUES (?,?,?,?,?,?,?)", m
                )

        if not _one(conn, "SELECT 1 FROM touchpoints LIMIT 1"):
            for t in SEED_TOUCHPOINTS:
                conn.execute(
                    "INSERT INTO touchpoints (tp_date, tp_type, title, participants, outcome, follow_up) VALUES (?,?,?,?,?,?)", t
                )

        if not _one(conn, "SELECT 1 FROM actions LIMIT 1"):
            for a in SEED_ACTIONS:
                conn.execute(
                    "INSERT INTO actions (owner, title, description, due_date, status, priority) VALUES (?,?,?,?,?,?)", a
                )

        if not _one(conn, "SELECT 1 FROM integrations LIMIT 1"):
            for i in SEED_INTEGRATIONS:
                conn.execute(
                    "INSERT INTO integrations (product, area, status, owner, notes) VALUES (?,?,?,?,?)", i
                )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

if HAS_DEPS:
    class ContactIn(BaseModel):
        name: str
        title: str
        team: str
        email: Optional[str] = None
        linkedin: Optional[str] = None
        notes: Optional[str] = None

    class TouchpointIn(BaseModel):
        tp_date: str
        tp_type: str
        title: str
        participants: Optional[str] = None
        outcome: Optional[str] = None
        follow_up: Optional[str] = None
        contact_ids: Optional[List[int]] = None

    class ActionIn(BaseModel):
        owner: str
        title: str
        description: Optional[str] = None
        due_date: Optional[str] = None
        status: str = "pending"
        priority: str = "medium"
        touchpoint_id: Optional[int] = None
        notes: Optional[str] = None

    class ActionPatch(BaseModel):
        status: Optional[str] = None
        notes: Optional[str] = None
        due_date: Optional[str] = None
        priority: Optional[str] = None

    class MilestonePatch(BaseModel):
        status: Optional[str] = None
        projected_date: Optional[str] = None
        actual_date: Optional[str] = None
        notes: Optional[str] = None

    class IntegrationPatch(BaseModel):
        status: Optional[str] = None
        notes: Optional[str] = None
        owner: Optional[str] = None


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _status_badge(status: str) -> str:
    colors = {
        "done":        ("#22c55e", "#14532d"),
        "in_progress": ("#f59e0b", "#451a03"),
        "planned":     ("#6366f1", "#1e1b4b"),
        "pending":     ("#94a3b8", "#1e293b"),
        "blocked":     ("#ef4444", "#450a0a"),
        "live":        ("#22c55e", "#14532d"),
        "partial":     ("#f59e0b", "#451a03"),
    }
    fg, bg = colors.get(status, ("#94a3b8", "#1e293b"))
    label = status.replace("_", " ").upper()
    return f'<span style="background:{bg};color:{fg};border:1px solid {fg};border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;letter-spacing:.05em">{label}</span>'


def _priority_dot(priority: str) -> str:
    c = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}.get(priority, "#94a3b8")
    return f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c};margin-right:6px"></span>'


def _tp_icon(tp_type: str) -> str:
    icons = {
        "meeting": "🤝", "email": "✉️", "demo": "🖥️",
        "shared_doc": "📄", "call": "📞", "conference": "🎤",
    }
    return icons.get(tp_type, "📌")


def build_html(
    contacts: List[Dict],
    touchpoints: List[Dict],
    actions: List[Dict],
    milestones: List[Dict],
    integrations: List[Dict],
) -> str:

    today = date.today().isoformat()

    # -- Milestone progress bar --
    total_ms = len(milestones)
    done_ms = sum(1 for m in milestones if m["status"] == "done")
    inprog_ms = sum(1 for m in milestones if m["status"] == "in_progress")
    pct_done = int(done_ms / total_ms * 100) if total_ms else 0
    pct_inprog = int(inprog_ms / total_ms * 100) if total_ms else 0

    ms_rows = ""
    for m in milestones:
        date_str = m.get("actual_date") or m.get("projected_date") or "TBD"
        ms_rows += f"""
        <tr>
          <td style="color:#94a3b8;font-size:12px;padding:8px 4px">{m['seq']}</td>
          <td style="padding:8px 4px;font-weight:600">{m['title']}</td>
          <td style="padding:8px 4px">{_status_badge(m['status'])}</td>
          <td style="padding:8px 4px;color:#94a3b8;font-size:12px">{date_str}</td>
          <td style="padding:8px 4px;color:#cbd5e1;font-size:12px">{m.get('notes') or ''}</td>
        </tr>"""

    # -- Touchpoint timeline --
    tp_cards = ""
    for tp in touchpoints:
        tp_cards += f"""
        <div style="border-left:3px solid #6366f1;padding:12px 16px;margin-bottom:12px;background:#1e293b;border-radius:0 8px 8px 0">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-weight:700">{_tp_icon(tp['tp_type'])} {tp['title']}</span>
            <span style="color:#94a3b8;font-size:12px">{tp['tp_date']} &nbsp; {_status_badge(tp['tp_type'])}</span>
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-bottom:4px">👥 {tp.get('participants') or '—'}</div>
          <div style="color:#cbd5e1;font-size:13px;margin-bottom:4px">{tp.get('outcome') or ''}</div>
          {'<div style="color:#f59e0b;font-size:12px">→ ' + tp['follow_up'] + '</div>' if tp.get('follow_up') else ''}
        </div>"""

    # -- Action items split by owner --
    def _action_rows(owner: str) -> str:
        rows = ""
        for a in actions:
            if a["owner"] != owner:
                continue
            status_b = _status_badge(a["status"])
            due = a.get("due_date") or "—"
            overdue = ""
            if a.get("due_date") and a["due_date"] < today and a["status"] not in ("done",):
                overdue = ' <span style="color:#ef4444;font-size:11px">OVERDUE</span>'
            rows += f"""
            <tr>
              <td style="padding:8px 4px">{_priority_dot(a['priority'])}<span style="font-weight:600">{a['title']}</span></td>
              <td style="padding:8px 4px">{status_b}</td>
              <td style="padding:8px 4px;color:#94a3b8;font-size:12px">{due}{overdue}</td>
              <td style="padding:8px 4px;color:#94a3b8;font-size:12px">{a.get('description') or ''}</td>
            </tr>"""
        return rows or '<tr><td colspan="4" style="color:#475569;padding:8px">No items</td></tr>'

    oracle_rows = _action_rows("Oracle")
    nvidia_rows = _action_rows("NVIDIA")

    # -- Integration grid --
    products = sorted({i["product"] for i in integrations})
    integ_sections = ""
    for prod in products:
        items = [i for i in integrations if i["product"] == prod]
        item_rows = ""
        for i in items:
            item_rows += f"""
            <tr>
              <td style="padding:6px 4px;font-size:13px">{i['area']}</td>
              <td style="padding:6px 4px">{_status_badge(i['status'])}</td>
              <td style="padding:6px 4px;color:#94a3b8;font-size:12px">{i.get('owner') or '—'}</td>
              <td style="padding:6px 4px;color:#94a3b8;font-size:12px">{i.get('notes') or ''}</td>
            </tr>"""
        integ_sections += f"""
        <div style="margin-bottom:20px">
          <div style="font-size:13px;font-weight:700;color:#6366f1;margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">{prod}</div>
          <table style="width:100%;border-collapse:collapse">{item_rows}</table>
        </div>"""

    # -- Contacts --
    teams = sorted({c["team"] for c in contacts})
    contact_sections = ""
    for team in teams:
        members = [c for c in contacts if c["team"] == team]
        cards = ""
        for c in members:
            cards += f"""
            <div style="background:#1e293b;border-radius:8px;padding:12px;margin-bottom:8px">
              <div style="font-weight:700">{c['name']}</div>
              <div style="color:#6366f1;font-size:12px">{c['title']}</div>
              <div style="color:#94a3b8;font-size:12px;margin-top:4px">{c.get('email') or ''}</div>
              <div style="color:#cbd5e1;font-size:12px;margin-top:4px">{c.get('notes') or ''}</div>
            </div>"""
        contact_sections += f"""
        <div style="margin-bottom:16px">
          <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:8px;text-transform:uppercase;letter-spacing:.08em">{team} Team</div>
          {cards}
        </div>"""

    # -- Next step highlight --
    pending_high = [a for a in actions if a["status"] in ("pending", "in_progress") and a["priority"] == "high"]
    next_step_html = ""
    if pending_high:
        n = pending_high[0]
        next_step_html = f"""
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #6366f1;border-radius:12px;padding:20px;margin-bottom:24px">
          <div style="font-size:11px;font-weight:700;color:#a5b4fc;letter-spacing:.1em;margin-bottom:8px">NEXT CRITICAL ACTION</div>
          <div style="font-size:18px;font-weight:800;color:#e0e7ff;margin-bottom:6px">{n['title']}</div>
          <div style="color:#a5b4fc;font-size:13px">Owner: <strong>{n['owner']}</strong> &nbsp;|&nbsp; Due: <strong>{n.get('due_date') or 'TBD'}</strong> &nbsp;|&nbsp; {_status_badge(n['status'])}</div>
          {'<div style="color:#c7d2fe;font-size:13px;margin-top:8px">' + n['description'] + '</div>' if n.get('description') else ''}
        </div>"""

    # -- Summary stats --
    done_actions = sum(1 for a in actions if a["status"] == "done")
    pending_actions = sum(1 for a in actions if a["status"] in ("pending", "in_progress"))
    integ_done = sum(1 for i in integrations if i["status"] == "done")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oracle × NVIDIA Partnership Tracker</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.5 }}
  h2 {{ font-size:14px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px }}
  table {{ width:100%;border-collapse:collapse }}
  tr:hover td {{ background:rgba(255,255,255,.02) }}
  ::-webkit-scrollbar {{ width:6px }} ::-webkit-scrollbar-track {{ background:#1e293b }}
  ::-webkit-scrollbar-thumb {{ background:#475569;border-radius:3px }}
</style>
</head>
<body>
<div style="max-width:1400px;margin:0 auto;padding:32px 24px">

  <!-- Header -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px">
    <div>
      <div style="font-size:28px;font-weight:900;background:linear-gradient(90deg,#6366f1,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent">
        Oracle × NVIDIA Partnership Tracker
      </div>
      <div style="color:#64748b;font-size:14px;margin-top:4px">Robotics Co-Engineering Pipeline — as of {today}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:12px;color:#64748b">API: <a href="/status" style="color:#6366f1">/status</a> &nbsp; <a href="/docs" style="color:#6366f1">/docs</a></div>
    </div>
  </div>

  <!-- KPI strip -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px">
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155">
      <div style="font-size:32px;font-weight:900;color:#22c55e">{done_ms}/{total_ms}</div>
      <div style="color:#64748b;font-size:13px;margin-top:4px">Milestones Complete</div>
    </div>
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155">
      <div style="font-size:32px;font-weight:900;color:#6366f1">{len(touchpoints)}</div>
      <div style="color:#64748b;font-size:13px;margin-top:4px">Touchpoints Logged</div>
    </div>
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155">
      <div style="font-size:32px;font-weight:900;color:#f59e0b">{pending_actions}</div>
      <div style="color:#64748b;font-size:13px;margin-top:4px">Open Action Items</div>
    </div>
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155">
      <div style="font-size:32px;font-weight:900;color:#22d3ee">{integ_done}/{len(integrations)}</div>
      <div style="color:#64748b;font-size:13px;margin-top:4px">Integrations Done</div>
    </div>
  </div>

  <!-- Next step highlight -->
  {next_step_html}

  <!-- Milestone progress -->
  <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155;margin-bottom:24px">
    <h2>Partnership Milestones</h2>
    <div style="background:#0f172a;border-radius:8px;height:12px;margin-bottom:20px;overflow:hidden">
      <div style="height:100%;width:{pct_done + pct_inprog}%;background:linear-gradient(90deg,#22c55e {pct_done * 100 // max(pct_done + pct_inprog, 1)}%,#f59e0b);border-radius:8px;transition:width .5s"></div>
    </div>
    <table>
      <thead>
        <tr style="border-bottom:1px solid #334155">
          <th style="text-align:left;padding:8px 4px;color:#64748b;font-size:12px">#</th>
          <th style="text-align:left;padding:8px 4px;color:#64748b;font-size:12px">Milestone</th>
          <th style="text-align:left;padding:8px 4px;color:#64748b;font-size:12px">Status</th>
          <th style="text-align:left;padding:8px 4px;color:#64748b;font-size:12px">Date</th>
          <th style="text-align:left;padding:8px 4px;color:#64748b;font-size:12px">Notes</th>
        </tr>
      </thead>
      <tbody>{ms_rows}</tbody>
    </table>
  </div>

  <!-- Main 3-col layout -->
  <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:24px;margin-bottom:24px">

    <!-- Touchpoint timeline -->
    <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155">
      <h2>Touchpoint Timeline</h2>
      {tp_cards}
    </div>

    <!-- Contacts -->
    <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155;overflow-y:auto;max-height:600px">
      <h2>NVIDIA Contacts ({len(contacts)})</h2>
      {contact_sections}
    </div>

  </div>

  <!-- Action items -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px">
    <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155">
      <h2 style="color:#22d3ee">Oracle Action Items</h2>
      <table><tbody>{oracle_rows}</tbody></table>
    </div>
    <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155">
      <h2 style="color:#76e4f7">NVIDIA Action Items</h2>
      <table><tbody>{nvidia_rows}</tbody></table>
    </div>
  </div>

  <!-- Technical integrations -->
  <div style="background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155;margin-bottom:24px">
    <h2>Technical Integration Status</h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:24px">
      {integ_sections}
    </div>
  </div>

  <div style="text-align:center;color:#334155;font-size:12px;padding:16px">
    OCI Robot Cloud Partnership Tracker &nbsp;·&nbsp; Port {PORT} &nbsp;·&nbsp; {today}
  </div>

</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_DEPS:
    app = FastAPI(
        title="NVIDIA Partnership Tracker",
        description="CRM-style tracker for the Oracle × NVIDIA robotics co-engineering pipeline",
        version="1.0.0",
    )

    # ---- Dashboard ----

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        with _db() as conn:
            contacts = _rows(conn, "SELECT * FROM contacts ORDER BY team, name")
            touchpoints = _rows(conn, "SELECT * FROM touchpoints ORDER BY tp_date DESC")
            actions = _rows(conn, "SELECT * FROM actions ORDER BY priority DESC, due_date ASC")
            milestones = _rows(conn, "SELECT * FROM milestones ORDER BY seq")
            integrations = _rows(conn, "SELECT * FROM integrations ORDER BY product, area")
        return build_html(contacts, touchpoints, actions, milestones, integrations)

    # ---- /status (executive JSON) ----

    @app.get("/status")
    def status():
        with _db() as conn:
            milestones = _rows(conn, "SELECT * FROM milestones ORDER BY seq")
            actions = _rows(conn, "SELECT * FROM actions ORDER BY due_date")
            touchpoints = _rows(conn, "SELECT * FROM touchpoints ORDER BY tp_date DESC LIMIT 3")
            integrations = _rows(conn, "SELECT * FROM integrations")

        done_ms = sum(1 for m in milestones if m["status"] == "done")
        inprog_ms = sum(1 for m in milestones if m["status"] == "in_progress")
        next_ms = next((m for m in milestones if m["status"] != "done"), None)
        open_oracle = [a for a in actions if a["owner"] == "Oracle" and a["status"] not in ("done",)]
        open_nvidia = [a for a in actions if a["owner"] == "NVIDIA" and a["status"] not in ("done",)]
        integ_done = sum(1 for i in integrations if i["status"] == "done")

        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "partnership_health": {
                "milestones_done": done_ms,
                "milestones_in_progress": inprog_ms,
                "milestones_total": len(milestones),
                "completion_pct": round(done_ms / len(milestones) * 100, 1) if milestones else 0,
            },
            "next_milestone": {
                "title": next_ms["title"] if next_ms else None,
                "projected_date": next_ms["projected_date"] if next_ms else None,
                "status": next_ms["status"] if next_ms else None,
            },
            "action_items": {
                "oracle_open": len(open_oracle),
                "nvidia_open": len(open_nvidia),
                "top_oracle": [{"title": a["title"], "due": a["due_date"], "priority": a["priority"]} for a in open_oracle[:3]],
                "top_nvidia": [{"title": a["title"], "due": a["due_date"], "priority": a["priority"]} for a in open_nvidia[:3]],
            },
            "integrations": {
                "done": integ_done,
                "total": len(integrations),
            },
            "recent_touchpoints": [
                {"date": t["tp_date"], "type": t["tp_type"], "title": t["title"]} for t in touchpoints
            ],
        }

    # ---- Contacts ----

    @app.get("/contacts")
    def get_contacts(team: Optional[str] = None):
        with _db() as conn:
            if team:
                return _rows(conn, "SELECT * FROM contacts WHERE team=? ORDER BY name", (team,))
            return _rows(conn, "SELECT * FROM contacts ORDER BY team, name")

    @app.post("/contacts", status_code=201)
    def add_contact(c: ContactIn):
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO contacts (name, title, team, email, linkedin, notes) VALUES (?,?,?,?,?,?)",
                (c.name, c.title, c.team, c.email, c.linkedin, c.notes),
            )
            return _one(conn, "SELECT * FROM contacts WHERE id=?", (cur.lastrowid,))

    # ---- Touchpoints ----

    @app.get("/touchpoints")
    def get_touchpoints(tp_type: Optional[str] = None):
        with _db() as conn:
            if tp_type:
                return _rows(conn, "SELECT * FROM touchpoints WHERE tp_type=? ORDER BY tp_date DESC", (tp_type,))
            return _rows(conn, "SELECT * FROM touchpoints ORDER BY tp_date DESC")

    @app.post("/touchpoints", status_code=201)
    def add_touchpoint(t: TouchpointIn):
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO touchpoints (tp_date, tp_type, title, participants, outcome, follow_up, contact_ids) VALUES (?,?,?,?,?,?,?)",
                (t.tp_date, t.tp_type, t.title, t.participants, t.outcome, t.follow_up,
                 json.dumps(t.contact_ids) if t.contact_ids else None),
            )
            return _one(conn, "SELECT * FROM touchpoints WHERE id=?", (cur.lastrowid,))

    # ---- Action items ----

    @app.get("/actions")
    def get_actions(owner: Optional[str] = None, status: Optional[str] = None):
        with _db() as conn:
            clauses, params = [], []
            if owner:
                clauses.append("owner=?"); params.append(owner)
            if status:
                clauses.append("status=?"); params.append(status)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            return _rows(conn, f"SELECT * FROM actions {where} ORDER BY priority DESC, due_date ASC", params)

    @app.post("/actions", status_code=201)
    def add_action(a: ActionIn):
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO actions (owner, title, description, due_date, status, priority, touchpoint_id, notes) VALUES (?,?,?,?,?,?,?,?)",
                (a.owner, a.title, a.description, a.due_date, a.status, a.priority, a.touchpoint_id, a.notes),
            )
            return _one(conn, "SELECT * FROM actions WHERE id=?", (cur.lastrowid,))

    @app.patch("/actions/{action_id}")
    def patch_action(action_id: int, patch: ActionPatch):
        with _db() as conn:
            row = _one(conn, "SELECT * FROM actions WHERE id=?", (action_id,))
            if not row:
                raise HTTPException(404, "Action item not found")
            updates = {k: v for k, v in patch.dict().items() if v is not None}
            updates["updated_at"] = date.today().isoformat()
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE actions SET {sets} WHERE id=?", (*updates.values(), action_id))
            return _one(conn, "SELECT * FROM actions WHERE id=?", (action_id,))

    # ---- Milestones ----

    @app.get("/milestones")
    def get_milestones():
        with _db() as conn:
            return _rows(conn, "SELECT * FROM milestones ORDER BY seq")

    @app.patch("/milestones/{milestone_id}")
    def patch_milestone(milestone_id: int, patch: MilestonePatch):
        with _db() as conn:
            row = _one(conn, "SELECT * FROM milestones WHERE id=?", (milestone_id,))
            if not row:
                raise HTTPException(404, "Milestone not found")
            updates = {k: v for k, v in patch.dict().items() if v is not None}
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE milestones SET {sets} WHERE id=?", (*updates.values(), milestone_id))
            return _one(conn, "SELECT * FROM milestones WHERE id=?", (milestone_id,))

    # ---- Integrations ----

    @app.get("/integrations")
    def get_integrations(product: Optional[str] = None):
        with _db() as conn:
            if product:
                return _rows(conn, "SELECT * FROM integrations WHERE product=? ORDER BY area", (product,))
            return _rows(conn, "SELECT * FROM integrations ORDER BY product, area")

    @app.patch("/integrations/{integ_id}")
    def patch_integration(integ_id: int, patch: IntegrationPatch):
        with _db() as conn:
            row = _one(conn, "SELECT * FROM integrations WHERE id=?", (integ_id,))
            if not row:
                raise HTTPException(404, "Integration not found")
            updates = {k: v for k, v in patch.dict().items() if v is not None}
            updates["updated_at"] = date.today().isoformat()
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE integrations SET {sets} WHERE id=?", (*updates.values(), integ_id))
            return _one(conn, "SELECT * FROM integrations WHERE id=?", (integ_id,))

    # ---- Health ----

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "db": str(DB_PATH)}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NVIDIA Partnership Tracker")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    parser.add_argument("--reset", action="store_true", help="Drop and re-seed database before starting")
    args = parser.parse_args()

    if not HAS_DEPS:
        print("ERROR: missing dependencies. Run:  pip install fastapi uvicorn")
        return

    print(f"Initializing DB at {DB_PATH} (reset={args.reset})")
    init_db(reset=args.reset)
    print(f"Starting NVIDIA Partnership Tracker on http://0.0.0.0:{args.port}")
    print(f"  Dashboard : http://localhost:{args.port}/")
    print(f"  Status API: http://localhost:{args.port}/status")
    print(f"  API docs  : http://localhost:{args.port}/docs")
    uvicorn.run("nvidia_partnership_tracker:app", host="0.0.0.0", port=args.port, reload=False)


if __name__ == "__main__":
    main()
