"""
Customer Onboarding Progress Tracker — OCI Robot Cloud
FastAPI service on port 8049

Tracks each design partner's progress through a 20-step onboarding checklist.
Serves as a shared dashboard between Oracle CSM and the partner.
"""

import argparse
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/onboarding.db"
PORT = 8049

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

PHASES = {
    1: "Setup",
    2: "Data",
    3: "Training",
    4: "Eval",
    5: "Production",
}

STEP_DEFINITIONS = [
    # (step_id, phase, name, description)
    (1,  1, "OCI Account Provisioned",       "OCI account provisioned with GPU4 (A100) access"),
    (2,  1, "API Key Issued",                 "API key issued and validated against service"),
    (3,  1, "SDK Installed",                  "SDK installed: pip install oci-robot-cloud"),
    (4,  1, "Health Check Passed",            "Health check passed: oci-robot-cloud health"),
    (5,  2, "First Dataset Uploaded",         "First dataset uploaded (≥50 demonstrations)"),
    (6,  2, "Quality Check Passed",           "Dataset quality check passed (diversity score ≥0.3)"),
    (7,  2, "Data Format Validated",          "Data format validated (LeRobot v2 or HDF5)"),
    (8,  2, "Dataset Registered",             "Dataset registered in lineage registry"),
    (9,  3, "BC Fine-Tune Submitted",         "First BC fine-tune job submitted"),
    (10, 3, "First Checkpoint Generated",     "First model checkpoint generated and saved"),
    (11, 3, "Open-Loop Eval Run",             "Open-loop evaluation run with MAE computed"),
    (12, 3, "DAgger Iteration 1 Done",        "DAgger iteration 1 completed successfully"),
    (13, 4, "Closed-Loop Eval ≥5%",           "Closed-loop eval: ≥5% task success rate achieved"),
    (14, 4, "Latency p95 <280ms",             "Inference latency validated: p95 below 280ms"),
    (15, 4, "Checkpoint Promoted to Staging", "Checkpoint promoted to staging environment"),
    (16, 4, "A/B Test Completed",             "A/B test vs baseline completed"),
    (17, 5, "Jetson Deploy Built",            "Jetson deploy package built and signed"),
    (18, 5, "Real Robot Integration Test",    "Real robot integration test passed"),
    (19, 5, "Model Card Generated",           "Model card generated with performance metrics"),
    (20, 5, "Production Checkpoint Promoted", "Production checkpoint promoted and active"),
]

STEPS_PER_PHASE = 4
HOURS_PER_STEP = 8  # rough estimate for "Time to Production" calculation


@dataclass
class ChecklistItem:
    step_id: int
    phase: int
    name: str
    description: str
    status: str = "not_started"   # not_started | in_progress | done | blocked
    completed_at: Optional[str] = None
    blockers: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class PartnerChecklist:
    partner_id: str
    partner_name: str
    items: List[ChecklistItem] = field(default_factory=list)
    csm_notes: str = ""
    last_updated: str = ""

    @property
    def overall_pct(self) -> int:
        if not self.items:
            return 0
        done = sum(1 for i in self.items if i.status == "done")
        return round(done / len(self.items) * 100)

    @property
    def current_phase(self) -> str:
        for item in self.items:
            if item.status in ("not_started", "in_progress", "blocked"):
                return f"Phase {item.phase} — {PHASES[item.phase]}"
        return "Phase 5 — Production (Complete)"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_cursor():
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS partners (
                partner_id   TEXT PRIMARY KEY,
                partner_name TEXT NOT NULL,
                csm_notes    TEXT DEFAULT '',
                last_updated TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS checklist_items (
                partner_id   TEXT NOT NULL,
                step_id      INTEGER NOT NULL,
                phase        INTEGER NOT NULL,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL,
                status       TEXT DEFAULT 'not_started',
                completed_at TEXT,
                blockers     TEXT DEFAULT '[]',
                notes        TEXT DEFAULT '',
                PRIMARY KEY (partner_id, step_id)
            )
        """)


def _build_items_for_partner(done_count: int, in_progress_step: Optional[int] = None) -> List[dict]:
    items = []
    for step_id, phase, name, description in STEP_DEFINITIONS:
        if step_id <= done_count:
            status = "done"
            completed_at = f"2026-0{phase}-{step_id:02d}T10:00:00Z"
        elif step_id == in_progress_step:
            status = "in_progress"
            completed_at = None
        else:
            status = "not_started"
            completed_at = None
        items.append({
            "step_id": step_id, "phase": phase, "name": name,
            "description": description, "status": status,
            "completed_at": completed_at, "blockers": "[]", "notes": "",
        })
    return items


def seed_mock_data():
    mock_partners = [
        ("partner-alpha",   "Agility Robotics",     20, None,  "All steps complete. Outstanding account!"),
        ("partner-beta",    "Boston Dynamics",       12, 13,   "Closed-loop eval in progress. p95 latency looks good."),
        ("partner-gamma",   "Apptronik",             6,  7,    "Data format validation pending. Needs HDF5 migration."),
        ("partner-delta",   "Fourier Intelligence",  3,  4,    "Health check failing — suspect firewall on port 443."),
        ("partner-epsilon", "Unitree Robotics",      1,  2,    "API key just issued. Onboarding call scheduled for next week."),
    ]
    with db_cursor() as cur:
        for partner_id, partner_name, done_count, in_progress_step, csm_notes in mock_partners:
            cur.execute("SELECT 1 FROM partners WHERE partner_id=?", (partner_id,))
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO partners VALUES (?, ?, ?, ?)",
                (partner_id, partner_name, csm_notes, datetime.now(timezone.utc).isoformat()),
            )
            items = _build_items_for_partner(done_count, in_progress_step)
            for item in items:
                cur.execute(
                    "INSERT INTO checklist_items VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        partner_id, item["step_id"], item["phase"], item["name"],
                        item["description"], item["status"], item["completed_at"],
                        item["blockers"], item["notes"],
                    ),
                )


def load_partner(partner_id: str) -> Optional[PartnerChecklist]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM partners WHERE partner_id=?", (partner_id,))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            "SELECT * FROM checklist_items WHERE partner_id=? ORDER BY step_id",
            (partner_id,),
        )
        item_rows = cur.fetchall()
    items = [
        ChecklistItem(
            step_id=r["step_id"], phase=r["phase"], name=r["name"],
            description=r["description"], status=r["status"],
            completed_at=r["completed_at"],
            blockers=json.loads(r["blockers"] or "[]"),
            notes=r["notes"] or "",
        )
        for r in item_rows
    ]
    return PartnerChecklist(
        partner_id=row["partner_id"], partner_name=row["partner_name"],
        items=items, csm_notes=row["csm_notes"], last_updated=row["last_updated"],
    )


def load_all_partners() -> List[PartnerChecklist]:
    with db_cursor() as cur:
        cur.execute("SELECT partner_id FROM partners ORDER BY partner_id")
        ids = [r["partner_id"] for r in cur.fetchall()]
    return [p for pid in ids if (p := load_partner(pid))]


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

STATUS_COLOR = {
    "done": "#22c55e",
    "in_progress": "#f59e0b",
    "blocked": "#ef4444",
    "not_started": "#6b7280",
}
STATUS_ICON = {"done": "✓", "in_progress": "⟳", "blocked": "✗", "not_started": "○"}

_BASE_CSS = """
body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:24px}
a{color:#38bdf8;text-decoration:none}a:hover{text-decoration:underline}
h1{color:#f1f5f9;font-size:1.6rem;margin-bottom:4px}
h2{color:#cbd5e1;font-size:1.2rem;margin:18px 0 8px}
.subtitle{color:#94a3b8;margin-bottom:24px}
table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}
th{background:#0f172a;color:#94a3b8;font-size:.75rem;text-transform:uppercase;padding:10px 14px;text-align:left}
td{padding:10px 14px;border-top:1px solid #334155;vertical-align:middle}
tr:hover td{background:#263040}
.bar-bg{background:#334155;border-radius:4px;height:10px;width:160px;display:inline-block;vertical-align:middle}
.bar-fg{height:10px;border-radius:4px;background:linear-gradient(90deg,#0ea5e9,#22c55e);display:block}
.pct{margin-left:8px;font-weight:600;color:#f1f5f9}
.phase-badge{background:#1e3a5f;color:#7dd3fc;border-radius:12px;padding:2px 10px;font-size:.78rem}
.step-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #1e293b}
.step-icon{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.8rem;flex-shrink:0}
.step-name{font-size:.9rem;flex:1}
.step-desc{font-size:.78rem;color:#94a3b8}
.phase-block{background:#1e293b;border-radius:8px;padding:14px 18px;margin-bottom:14px}
.phase-title{font-weight:600;color:#7dd3fc;margin-bottom:10px}
.back{margin-bottom:18px;display:inline-block}
.csm-box{background:#1e293b;border-radius:8px;padding:14px 18px;margin-top:24px}
.csm-box label{color:#94a3b8;font-size:.85rem}
.ttp{background:#0f4c31;color:#6ee7b7;border-radius:6px;padding:6px 14px;display:inline-block;margin-top:8px;font-size:.9rem}
"""


def render_overview(partners: List[PartnerChecklist]) -> str:
    rows = ""
    for p in partners:
        pct = p.overall_pct
        rows += f"""
        <tr>
          <td><a href="/partner/{p.partner_id}">{p.partner_name}</a></td>
          <td><span class="bar-bg"><span class="bar-fg" style="width:{pct}%"></span></span>
              <span class="pct">{pct}%</span></td>
          <td><span class="phase-badge">{p.current_phase}</span></td>
          <td style="color:#94a3b8;font-size:.82rem">{p.last_updated[:10] if p.last_updated else '—'}</td>
        </tr>"""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>OCI Robot Cloud — Onboarding</title>
<style>{_BASE_CSS}</style></head><body>
<h1>OCI Robot Cloud — Customer Onboarding Dashboard</h1>
<p class="subtitle">Design partner progress through 20-step onboarding checklist</p>
<table>
  <thead><tr><th>Partner</th><th>Progress</th><th>Current Phase</th><th>Last Updated</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""


def render_partner_detail(p: PartnerChecklist) -> str:
    remaining_steps = sum(1 for i in p.items if i.status != "done")
    ttp_hours = remaining_steps * HOURS_PER_STEP
    ttp_days = ttp_hours // 8
    ttp_str = f"~{ttp_days} business days" if ttp_days > 0 else "Complete!"

    phases_html = ""
    for phase_id, phase_name in PHASES.items():
        phase_items = [i for i in p.items if i.phase == phase_id]
        done_count = sum(1 for i in phase_items if i.status == "done")
        steps_html = ""
        for item in phase_items:
            color = STATUS_COLOR[item.status]
            icon = STATUS_ICON[item.status]
            note_txt = f" — <em style='color:#94a3b8'>{item.notes}</em>" if item.notes else ""
            steps_html += f"""
            <div class="step-row">
              <div class="step-icon" style="background:{color}20;color:{color}">{icon}</div>
              <div>
                <div class="step-name">{item.step_id}. {item.name}{note_txt}</div>
                <div class="step-desc">{item.description}</div>
              </div>
            </div>"""
        phases_html += f"""
        <div class="phase-block">
          <div class="phase-title">Phase {phase_id} — {phase_name}
            <span style="font-weight:400;color:#94a3b8;font-size:.82rem;margin-left:8px">
              {done_count}/{len(phase_items)} complete</span>
          </div>
          {steps_html}
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{p.partner_name} — Onboarding</title>
<style>{_BASE_CSS}
  .update-form{{display:inline-flex;gap:6px;align-items:center;margin-top:4px}}
  select,input[type=text],textarea{{background:#0f172a;color:#e2e8f0;border:1px solid #334155;
    border-radius:4px;padding:4px 8px;font-size:.82rem}}
  button{{background:#0369a1;color:#fff;border:none;border-radius:4px;padding:5px 12px;
    cursor:pointer;font-size:.82rem}}button:hover{{background:#0284c7}}
</style></head><body>
<a class="back" href="/">← All Partners</a>
<h1>{p.partner_name}</h1>
<p class="subtitle">Partner ID: <code>{p.partner_id}</code></p>
<div style="display:flex;gap:18px;align-items:center;margin-bottom:20px">
  <div>
    <span class="bar-bg" style="width:220px">
      <span class="bar-fg" style="width:{p.overall_pct}%"></span>
    </span>
    <span class="pct">{p.overall_pct}% complete</span>
  </div>
  <span class="phase-badge">{p.current_phase}</span>
  <span class="ttp">Time to Production: {ttp_str}</span>
</div>

{phases_html}

<div class="csm-box">
  <label>CSM Notes</label>
  <p style="margin:6px 0 0">{p.csm_notes or '<em style="color:#6b7280">No notes yet.</em>'}</p>
</div>

<div class="csm-box" style="margin-top:14px">
  <label>Update a Step</label>
  <form style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end"
        onsubmit="updateStep(event)">
    <div>
      <div style="font-size:.75rem;color:#94a3b8;margin-bottom:3px">Step</div>
      <select id="step_sel">
        {''.join(f'<option value="{i.step_id}">{i.step_id}. {i.name}</option>' for i in p.items)}
      </select>
    </div>
    <div>
      <div style="font-size:.75rem;color:#94a3b8;margin-bottom:3px">Status</div>
      <select id="status_sel">
        <option value="done">done</option>
        <option value="in_progress">in_progress</option>
        <option value="not_started">not_started</option>
        <option value="blocked">blocked</option>
      </select>
    </div>
    <div>
      <div style="font-size:.75rem;color:#94a3b8;margin-bottom:3px">Notes</div>
      <input type="text" id="notes_inp" placeholder="optional notes" style="width:220px">
    </div>
    <button type="submit">Update</button>
    <span id="upd_msg" style="color:#22c55e;font-size:.82rem"></span>
  </form>
</div>

<script>
async function updateStep(e) {{
  e.preventDefault();
  const step = document.getElementById('step_sel').value;
  const status = document.getElementById('status_sel').value;
  const notes = document.getElementById('notes_inp').value;
  const resp = await fetch(`/partner/{p.partner_id}/step/${{step}}`,
    {{method:'POST',headers:{{'Content-Type':'application/json'}},
     body:JSON.stringify({{status,notes}})}});
  const msg = document.getElementById('upd_msg');
  if(resp.ok) {{ msg.textContent='Updated!'; setTimeout(()=>location.reload(),800); }}
  else {{ msg.style.color='#ef4444'; msg.textContent='Error: '+resp.status; }}
}}
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Customer Onboarding Checklist", version="1.0.0")

    @app.on_event("startup")
    def startup():
        init_db()
        seed_mock_data()

    @app.get("/", response_class=HTMLResponse)
    def overview():
        partners = load_all_partners()
        return render_overview(partners)

    @app.get("/partner/{partner_id}", response_class=HTMLResponse)
    def partner_detail(partner_id: str):
        p = load_partner(partner_id)
        if not p:
            raise HTTPException(status_code=404, detail="Partner not found")
        return render_partner_detail(p)

    @app.post("/partner/{partner_id}/step/{step_id}")
    def update_step(partner_id: str, step_id: int, request_body: dict):
        status = request_body.get("status", "done")
        notes = request_body.get("notes", "")
        valid_statuses = {"not_started", "in_progress", "done", "blocked"}
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")
        completed_at = datetime.now(timezone.utc).isoformat() if status == "done" else None
        with db_cursor() as cur:
            cur.execute("SELECT 1 FROM partners WHERE partner_id=?", (partner_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Partner not found")
            cur.execute(
                """UPDATE checklist_items
                   SET status=?, completed_at=?, notes=?
                   WHERE partner_id=? AND step_id=?""",
                (status, completed_at, notes, partner_id, step_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Step not found")
            cur.execute(
                "UPDATE partners SET last_updated=? WHERE partner_id=?",
                (datetime.now(timezone.utc).isoformat(), partner_id),
            )
        return {"ok": True, "partner_id": partner_id, "step_id": step_id, "status": status}

    @app.get("/api/partners")
    def api_list_partners():
        partners = load_all_partners()
        result = []
        for p in partners:
            result.append({
                "partner_id": p.partner_id,
                "partner_name": p.partner_name,
                "overall_pct": p.overall_pct,
                "current_phase": p.current_phase,
                "csm_notes": p.csm_notes,
                "last_updated": p.last_updated,
            })
        return result

    @app.get("/api/partner/{partner_id}")
    def api_get_partner(partner_id: str):
        p = load_partner(partner_id)
        if not p:
            raise HTTPException(status_code=404, detail="Partner not found")
        data = asdict(p)
        data["overall_pct"] = p.overall_pct
        data["current_phase"] = p.current_phase
        return data

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "customer_onboarding_checklist", "port": PORT}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Customer Onboarding Checklist — OCI Robot Cloud")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port (default: {PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: FastAPI and uvicorn are required. Install with:")
        print("  pip install fastapi uvicorn")
        raise SystemExit(1)

    print(f"Starting Customer Onboarding Checklist on http://{args.host}:{args.port}")
    uvicorn.run(
        "customer_onboarding_checklist:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
