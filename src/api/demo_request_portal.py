#!/usr/bin/env python3
"""
demo_request_portal.py — Self-service demo request and scheduling portal (port 8029).

Lets NVIDIA ecosystem partners and prospects:
  1. Request a live OCI Robot Cloud demo
  2. Browse pre-recorded demos by task / embodiment
  3. Schedule a custom fine-tuning session
  4. Download sample results and benchmark reports

Used at AI World September 2026 and GTC 2027 — "scan QR → request demo → get results".

Usage:
    python src/api/demo_request_portal.py --port 8029 --mock
    # → http://localhost:8029
"""

import json
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, Form, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/demo_requests.db"

DEMO_CATALOG = [
    {
        "id": "pick_lift_franka",
        "title": "Pick & Lift — Franka Panda",
        "description": "GR00T N1.6-3B fine-tuned on 1000 Genesis SDG demos. 65% closed-loop success after 3 DAgger iterations.",
        "tags": ["franka", "pick-and-lift", "genesis", "dagger"],
        "success_rate": 0.65,
        "latency_ms": 226,
        "training_cost": 0.43,
        "replay_url": "http://localhost:8025",
        "embodiment": "Franka Panda",
        "status": "live",
    },
    {
        "id": "pick_place_ur5e",
        "title": "Pick & Place — UR5e",
        "description": "Cross-embodiment transfer from Franka. 40% success on 50 transfer demos via embodiment adapter.",
        "tags": ["ur5e", "pick-and-place", "transfer"],
        "success_rate": 0.40,
        "latency_ms": 231,
        "training_cost": 0.18,
        "replay_url": "",
        "embodiment": "UR5e",
        "status": "preview",
    },
    {
        "id": "pick_lift_xarm7",
        "title": "Pick & Lift — xArm7",
        "description": "Cross-embodiment transfer from Franka. 48% success on 50 transfer demos.",
        "tags": ["xarm7", "pick-and-lift", "transfer"],
        "success_rate": 0.48,
        "latency_ms": 229,
        "training_cost": 0.18,
        "replay_url": "",
        "embodiment": "xArm7",
        "status": "preview",
    },
    {
        "id": "custom_task",
        "title": "Custom Task (Request)",
        "description": "Submit your task description and robot model. We run the full Genesis SDG → GR00T pipeline on OCI A100.",
        "tags": ["custom", "request"],
        "success_rate": None,
        "latency_ms": None,
        "training_cost": None,
        "replay_url": "",
        "embodiment": "Your robot",
        "status": "request",
    },
]

# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS demo_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            company TEXT,
            email TEXT,
            demo_id TEXT,
            task_description TEXT,
            robot_model TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
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


def seed_mock_requests(db_path: str = DB_PATH) -> None:
    rng = random.Random(2026)
    companies = ["Stretch Robotics", "Nimble AI", "Auton Systems",
                 "NVIDIA Partner Co", "Series B Startup"]
    with sqlite3.connect(db_path) as conn:
        for i, co in enumerate(companies):
            days = rng.randint(1, 14)
            ts = (datetime.now() - timedelta(days=days)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO demo_requests "
                "(name,company,email,demo_id,task_description,robot_model,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (f"Contact {i+1}", co, f"contact{i+1}@example.com",
                 rng.choice(["pick_lift_franka","pick_place_ur5e","custom_task"]),
                 "Pick and lift task", "Franka Panda",
                 rng.choice(["pending","demo_sent","scheduled"]), ts)
            )


# ── HTML pages ────────────────────────────────────────────────────────────────

def render_home() -> str:
    catalog_cards = ""
    for d in DEMO_CATALOG:
        status_color = {"live":"#22c55e","preview":"#f59e0b","request":"#3b82f6"}.get(d["status"],"#94a3b8")
        rate_str = f"{d['success_rate']:.0%}" if d["success_rate"] is not None else "TBD"
        lat_str  = f"{d['latency_ms']}ms" if d["latency_ms"] is not None else "—"
        cost_str = f"${d['training_cost']:.2f}" if d["training_cost"] is not None else "—"
        replay = (f'<a href="{d["replay_url"]}" target="_blank" '
                  f'style="background:#1e3a5f;color:#3b82f6;padding:5px 10px;'
                  f'border-radius:5px;font-size:12px;text-decoration:none">▶ Watch replay</a>')
        catalog_cards += f"""
        <div style="background:#1e293b;border-radius:10px;padding:20px;border:1px solid #334155">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <h3 style="margin:0;font-size:16px;color:#f8fafc">{d['title']}</h3>
            <span style="background:{status_color}22;color:{status_color};padding:2px 8px;
              border-radius:10px;font-size:11px;white-space:nowrap">{d['status'].upper()}</span>
          </div>
          <p style="color:#94a3b8;font-size:13px;margin:0 0 12px">{d['description']}</p>
          <div style="display:flex;gap:16px;font-size:12px;color:#64748b;margin-bottom:12px">
            <span>Success: <strong style="color:#22c55e">{rate_str}</strong></span>
            <span>Latency: <strong style="color:#94a3b8">{lat_str}</strong></span>
            <span>Cost: <strong style="color:#3b82f6">{cost_str}</strong></span>
          </div>
          <div style="display:flex;gap:8px">
            {replay if d.get("replay_url") else ""}
            <a href="/request?demo={d['id']}" style="background:#3b82f622;color:#3b82f6;padding:5px 10px;
              border-radius:5px;font-size:12px;text-decoration:none">📋 Request demo</a>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Robot Cloud — Demo Portal</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:32px;max-width:900px;margin:0 auto;padding:32px}}
  h1{{color:#f8fafc;font-size:28px;margin-bottom:4px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
  @media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>OCI Robot Cloud</h1>
<p style="color:#94a3b8;font-size:16px;margin:0 0 8px">
  Train GR00T N1.6-3B on your robot data — <strong style="color:#3b82f6">9.6× cheaper than AWS</strong>
</p>
<p style="color:#64748b;font-size:13px">
  Genesis SDG → GR00T fine-tune → DAgger → Deploy to Jetson |
  <a href="https://github.com/qianjun22/roboticsai" style="color:#3b82f6">github.com/qianjun22/roboticsai</a>
</p>

<div class="grid">
  <div style="background:#0c1a2e;border:1px solid #1e3a5f;border-radius:10px;padding:20px">
    <div style="font-size:32px;font-weight:700;color:#22c55e">65%</div>
    <div style="color:#94a3b8;font-size:12px">Closed-loop success (DAgger run4)</div>
  </div>
  <div style="background:#0c1a2e;border:1px solid #1e3a5f;border-radius:10px;padding:20px">
    <div style="font-size:32px;font-weight:700;color:#3b82f6">$0.43</div>
    <div style="color:#94a3b8;font-size:12px">Full fine-tune cost on OCI A100</div>
  </div>
  <div style="background:#0c1a2e;border:1px solid #1e3a5f;border-radius:10px;padding:20px">
    <div style="font-size:32px;font-weight:700;color:#6366f1">226ms</div>
    <div style="color:#94a3b8;font-size:12px">Inference latency (OCI A100)</div>
  </div>
  <div style="background:#0c1a2e;border:1px solid #1e3a5f;border-radius:10px;padding:20px">
    <div style="font-size:32px;font-weight:700;color:#f59e0b">9.6×</div>
    <div style="color:#94a3b8;font-size:12px">Cheaper than AWS p4d per step</div>
  </div>
</div>

<h2 style="color:#94a3b8;font-size:14px;text-transform:uppercase;letter-spacing:.05em;margin:24px 0 12px">Demo Catalog</h2>
<div class="grid">{catalog_cards}</div>

<div style="margin-top:24px;padding:16px;background:#1e293b;border-radius:10px">
  <a href="/admin" style="color:#64748b;font-size:12px;text-decoration:none">Admin →</a>
</div>
</body>
</html>"""


def render_request_form(demo_id: str = "") -> str:
    demo = next((d for d in DEMO_CATALOG if d["id"] == demo_id), DEMO_CATALOG[0])
    options = "".join(
        f'<option value="{d["id"]}" {"selected" if d["id"]==demo_id else ""}>{d["title"]}</option>'
        for d in DEMO_CATALOG
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Request Demo</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:32px;max-width:560px;margin:0 auto}}
  input,select,textarea{{width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;
    color:#e2e8f0;border-radius:6px;padding:10px 12px;font-size:14px;margin-bottom:12px}}
  input:focus,select:focus,textarea:focus{{outline:none;border-color:#3b82f6}}
  button{{background:#3b82f6;color:white;border:none;padding:12px 24px;border-radius:6px;
    font-size:14px;font-weight:600;cursor:pointer;width:100%}}
  button:hover{{background:#2563eb}}
  label{{display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em}}
</style>
</head>
<body>
<a href="/" style="color:#3b82f6;text-decoration:none;font-size:13px">← Back</a>
<h1 style="color:#f8fafc;font-size:20px;margin:16px 0 4px">Request a Demo</h1>
<p style="color:#94a3b8;font-size:13px;margin:0 0 20px">We'll reach out within 24 hours to schedule your session.</p>

<form method="POST" action="/submit">
  <label>Name</label>
  <input type="text" name="name" placeholder="Your name" required>

  <label>Company</label>
  <input type="text" name="company" placeholder="Company name" required>

  <label>Work Email</label>
  <input type="email" name="email" placeholder="you@company.com" required>

  <label>Demo Type</label>
  <select name="demo_id">{options}</select>

  <label>Robot Model</label>
  <input type="text" name="robot_model" placeholder="e.g. Franka Panda, UR5e, custom">

  <label>Task Description</label>
  <textarea name="task_description" rows="3" placeholder="Describe your manipulation task..."></textarea>

  <label>Message (optional)</label>
  <textarea name="message" rows="2" placeholder="Questions, timeline, NVIDIA contact..."></textarea>

  <button type="submit">Request Demo →</button>
</form>
</body>
</html>"""


def render_confirmation(name: str, company: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Demo Requested</title>
<style>body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:48px;text-align:center}}</style>
</head>
<body>
<div style="font-size:48px">✅</div>
<h1 style="color:#22c55e;font-size:24px">Demo Request Received!</h1>
<p style="color:#94a3b8">Hi {name} from {company} — we'll reach out within 24 hours.</p>
<p style="color:#64748b;font-size:13px;margin-top:24px">
  While you wait:
  <a href="https://github.com/qianjun22/roboticsai" style="color:#3b82f6">explore the code</a> ·
  <a href="/watch/pick_lift_franka" style="color:#3b82f6">watch a demo replay</a>
</p>
<a href="/" style="display:inline-block;margin-top:16px;color:#3b82f6;text-decoration:none">← Back to demos</a>
</body>
</html>"""


def render_admin(requests: list[dict]) -> str:
    rows = ""
    for r in requests:
        status_color = {"pending":"#f59e0b","demo_sent":"#22c55e","scheduled":"#3b82f6"}.get(r["status"],"#94a3b8")
        rows += f"""<tr>
          <td style="padding:8px 10px">{r['name']}</td>
          <td style="padding:8px 10px">{r['company']}</td>
          <td style="padding:8px 10px;font-size:12px;color:#64748b">{r['email']}</td>
          <td style="padding:8px 10px;font-size:12px">{r['demo_id']}</td>
          <td style="padding:8px 10px">
            <span style="color:{status_color};font-size:12px">{r['status']}</span>
          </td>
          <td style="padding:8px 10px;color:#475569;font-size:11px">{r['created_at'][:10]}</td>
        </tr>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Admin — Demo Requests</title>
<style>body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:24px}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px}}
th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:10px;text-align:left;border-bottom:1px solid #334155}}
</style></head>
<body>
<a href="/" style="color:#3b82f6;text-decoration:none">← Portal</a>
<h1 style="color:#f8fafc;font-size:20px;margin:16px 0">Demo Requests ({len(requests)})</h1>
<table><tr><th>Name</th><th>Company</th><th>Email</th><th>Demo</th><th>Status</th><th>Date</th></tr>
{rows}</table>
<p style="color:#475569;font-size:11px;margin-top:12px">
  <a href="/api/requests" style="color:#3b82f6">API export</a></p>
</body></html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH) -> "FastAPI":
    app = FastAPI(title="OCI Robot Cloud Demo Portal", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        seed_mock_requests(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def home():
        return render_home()

    @app.get("/request", response_class=HTMLResponse)
    async def request_form(demo: str = ""):
        return render_request_form(demo)

    @app.post("/submit", response_class=HTMLResponse)
    async def submit(
        name: str = Form(...),
        company: str = Form(...),
        email: str = Form(...),
        demo_id: str = Form("pick_lift_franka"),
        robot_model: str = Form(""),
        task_description: str = Form(""),
        message: str = Form(""),
    ):
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO demo_requests "
                "(name,company,email,demo_id,robot_model,task_description,message,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, company, email, demo_id, robot_model,
                 task_description, message, "pending",
                 datetime.now().isoformat())
            )
        return render_confirmation(name, company)

    @app.get("/admin", response_class=HTMLResponse)
    async def admin():
        with get_db(db_path) as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM demo_requests ORDER BY created_at DESC"
            ).fetchall()]
        return render_admin(rows)

    @app.get("/api/requests")
    async def api_requests():
        with get_db(db_path) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM demo_requests ORDER BY created_at DESC"
            ).fetchall()]

    @app.get("/api/catalog")
    async def api_catalog():
        return DEMO_CATALOG

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "demo_request_portal", "port": 8029}

    return app


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Demo request portal (port 8029)")
    parser.add_argument("--port", type=int, default=8029)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(args.db)
    print(f"Demo Request Portal → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
