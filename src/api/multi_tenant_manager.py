#!/usr/bin/env python3
"""
multi_tenant_manager.py — Multi-tenant namespace isolation for OCI Robot Cloud.

Manages isolated workspaces for multiple design partners on the same OCI node:
  - Per-partner dataset directories under /tmp/partners/<id>/
  - Per-partner checkpoint namespaces
  - Resource quotas (max GPU hours, max episodes stored)
  - API key generation + validation
  - Usage tracking and billing hooks

Usage:
    python src/api/multi_tenant_manager.py [--port 8023] [--mock]

Endpoints:
    POST /partners               Create partner workspace
    GET  /partners               List all partners
    GET  /partners/{id}          Partner detail + usage
    DELETE /partners/{id}        Deactivate partner
    POST /partners/{id}/apikey   Rotate API key
    GET  /partners/{id}/usage    Usage + quota status
    GET  /health                 Health check
    GET  /                       Admin dashboard
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

DB_PATH = "/tmp/multi_tenant.db"
PARTNER_ROOT = "/tmp/partners"

# Default resource quotas
DEFAULT_QUOTAS = {
    "max_gpu_hours": 20.0,        # per month
    "max_episodes": 5000,         # total stored episodes
    "max_checkpoints": 10,        # retained checkpoints
    "max_concurrent_jobs": 1,     # concurrent fine-tune jobs
}

TIER_QUOTAS = {
    "starter":    {**DEFAULT_QUOTAS, "max_gpu_hours": 10.0,  "max_episodes": 1000},
    "growth":     {**DEFAULT_QUOTAS, "max_gpu_hours": 50.0,  "max_episodes": 10000},
    "enterprise": {**DEFAULT_QUOTAS, "max_gpu_hours": 200.0, "max_episodes": 100000, "max_concurrent_jobs": 4},
}


# ── DB ────────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS partners (
        id           TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        email        TEXT,
        tier         TEXT DEFAULT 'starter',
        api_key_hash TEXT NOT NULL,
        workspace    TEXT NOT NULL,
        quotas       TEXT NOT NULL,
        active       INTEGER DEFAULT 1,
        created_at   TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS usage (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        partner_id   TEXT NOT NULL,
        event        TEXT NOT NULL,   -- 'gpu_hour', 'episode_stored', 'checkpoint', 'api_call'
        amount       REAL DEFAULT 1.0,
        ts           REAL NOT NULL,
        metadata     TEXT
    );
    """)
    conn.commit()
    conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _make_api_key() -> str:
    return "oci_rc_" + secrets.token_urlsafe(32)


def _get_partner_by_key(api_key: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM partners WHERE api_key_hash=? AND active=1",
        (_hash_key(api_key),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def require_partner_key(x_api_key: str = Header(...)):
    partner = _get_partner_by_key(x_api_key)
    if not partner:
        raise HTTPException(401, "Invalid or inactive API key")
    return partner


def require_admin_key(x_admin_key: str = Header(...)):
    # In production: real admin secret; here we accept a fixed dev key
    if x_admin_key != os.environ.get("OCI_ADMIN_KEY", "dev_admin_key"):
        raise HTTPException(403, "Admin access required")


# ── Workspace helpers ─────────────────────────────────────────────────────────

def _create_workspace(partner_id: str) -> str:
    workspace = f"{PARTNER_ROOT}/{partner_id}"
    for sub in ["datasets", "checkpoints", "evals", "logs"]:
        Path(f"{workspace}/{sub}").mkdir(parents=True, exist_ok=True)
    return workspace


def _workspace_stats(workspace: str) -> dict:
    p = Path(workspace)
    if not p.exists():
        return {"datasets": 0, "checkpoints": 0, "disk_mb": 0}
    n_ds = len(list((p / "datasets").iterdir())) if (p / "datasets").exists() else 0
    n_ckpt = len(list((p / "checkpoints").iterdir())) if (p / "checkpoints").exists() else 0
    total_bytes = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return {"datasets": n_ds, "checkpoints": n_ckpt, "disk_mb": round(total_bytes / 1e6, 1)}


# ── Usage tracking ────────────────────────────────────────────────────────────

def track_usage(partner_id: str, event: str, amount: float = 1.0, metadata: dict = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO usage (partner_id, event, amount, ts, metadata) VALUES (?,?,?,?,?)",
        (partner_id, event, amount, time.time(), json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()


def get_usage_summary(partner_id: str, days: int = 30) -> dict:
    since = time.time() - days * 86400
    conn = get_db()
    rows = conn.execute(
        "SELECT event, SUM(amount) as total FROM usage WHERE partner_id=? AND ts>=? GROUP BY event",
        (partner_id, since)
    ).fetchall()
    conn.close()
    return {r["event"]: round(r["total"], 3) for r in rows}


def check_quota(partner_id: str, event: str, requested: float = 1.0) -> tuple[bool, str]:
    conn = get_db()
    partner = conn.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
    conn.close()
    if not partner:
        return False, "Partner not found"
    quotas = json.loads(partner["quotas"])
    usage = get_usage_summary(partner_id)

    quota_map = {
        "gpu_hour": ("max_gpu_hours", "GPU hours"),
        "episode_stored": ("max_episodes", "episodes"),
        "checkpoint": ("max_checkpoints", "checkpoints"),
    }
    if event not in quota_map:
        return True, "ok"

    quota_key, label = quota_map[event]
    limit = quotas.get(quota_key, float("inf"))
    current = usage.get(event, 0)
    if current + requested > limit:
        return False, f"Quota exceeded: {current:.1f}/{limit} {label} used this month"
    return True, "ok"


# ── API ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud — Multi-Tenant Manager")
init_db()


class PartnerCreate(BaseModel):
    name: str
    email: str = ""
    tier: str = "starter"


@app.get("/health")
def health():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM partners WHERE active=1").fetchone()[0]
    conn.close()
    return {"status": "ok", "active_partners": n}


@app.post("/partners", status_code=201)
def create_partner(body: PartnerCreate, x_admin_key: str = Header(...)):
    require_admin_key(x_admin_key)
    pid = "p_" + secrets.token_hex(6)
    api_key = _make_api_key()
    workspace = _create_workspace(pid)
    tier = body.tier if body.tier in TIER_QUOTAS else "starter"
    quotas = TIER_QUOTAS[tier]
    conn = get_db()
    conn.execute(
        "INSERT INTO partners VALUES (?,?,?,?,?,?,?,?,?)",
        (pid, body.name, body.email, tier, _hash_key(api_key),
         workspace, json.dumps(quotas), 1, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {
        "id": pid,
        "name": body.name,
        "tier": tier,
        "workspace": workspace,
        "api_key": api_key,   # shown once — partner must save this
        "quotas": quotas,
        "message": "Save your API key — it won't be shown again.",
    }


@app.get("/partners")
def list_partners(x_admin_key: str = Header(...)):
    require_admin_key(x_admin_key)
    conn = get_db()
    rows = conn.execute("SELECT * FROM partners ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        del d["api_key_hash"]
        d["usage_30d"] = get_usage_summary(r["id"])
        d["workspace_stats"] = _workspace_stats(r["workspace"])
        result.append(d)
    return result


@app.get("/partners/{pid}")
def get_partner(pid: str, x_admin_key: str = Header(...)):
    require_admin_key(x_admin_key)
    conn = get_db()
    row = conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Partner not found")
    d = dict(row)
    del d["api_key_hash"]
    d["quotas"] = json.loads(d["quotas"])
    d["usage_30d"] = get_usage_summary(pid)
    d["workspace_stats"] = _workspace_stats(d["workspace"])
    return d


@app.delete("/partners/{pid}")
def deactivate_partner(pid: str, x_admin_key: str = Header(...)):
    require_admin_key(x_admin_key)
    conn = get_db()
    conn.execute("UPDATE partners SET active=0 WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"deactivated": pid}


@app.post("/partners/{pid}/apikey")
def rotate_api_key(pid: str, x_admin_key: str = Header(...)):
    require_admin_key(x_admin_key)
    new_key = _make_api_key()
    conn = get_db()
    conn.execute("UPDATE partners SET api_key_hash=? WHERE id=?", (_hash_key(new_key), pid))
    conn.commit()
    conn.close()
    return {"id": pid, "api_key": new_key, "message": "Old key invalidated immediately."}


@app.get("/partners/{pid}/usage")
def get_partner_usage(pid: str, partner=Depends(require_partner_key)):
    if partner["id"] != pid:
        conn = get_db()
        row = conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(404, "Not found")
        target = dict(row)
    else:
        target = partner
    quotas = json.loads(target["quotas"])
    usage = get_usage_summary(pid)
    result = {}
    for event, (quota_key, label) in {
        "gpu_hour": ("max_gpu_hours", "GPU hours"),
        "episode_stored": ("max_episodes", "Episodes"),
        "checkpoint": ("max_checkpoints", "Checkpoints"),
    }.items():
        used = usage.get(event, 0)
        limit = quotas.get(quota_key, 0)
        result[event] = {
            "label": label, "used": used, "limit": limit,
            "pct": round(used / limit * 100, 1) if limit else 0,
        }
    return {"partner_id": pid, "tier": target["tier"], "quotas": result, "usage_30d": usage}


# ── Partner-facing endpoints (authenticated by API key) ───────────────────────

@app.get("/me")
def get_my_info(partner=Depends(require_partner_key)):
    quotas = json.loads(partner["quotas"])
    usage = get_usage_summary(partner["id"])
    ws_stats = _workspace_stats(partner["workspace"])
    return {
        "id": partner["id"],
        "name": partner["name"],
        "tier": partner["tier"],
        "workspace": partner["workspace"],
        "workspace_stats": ws_stats,
        "quotas": quotas,
        "usage_30d": usage,
    }


@app.post("/me/track")
def track_my_usage(event: str, amount: float = 1.0, partner=Depends(require_partner_key)):
    ok, msg = check_quota(partner["id"], event, amount)
    if not ok:
        raise HTTPException(429, f"Quota exceeded: {msg}")
    track_usage(partner["id"], event, amount)
    return {"tracked": True, "event": event, "amount": amount}


# ── Admin dashboard ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    conn = get_db()
    partners = conn.execute(
        "SELECT * FROM partners ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    rows = ""
    for p in partners:
        usage = get_usage_summary(p["id"])
        quotas = json.loads(p["quotas"])
        gpu_used = usage.get("gpu_hour", 0)
        gpu_limit = quotas.get("max_gpu_hours", 0)
        eps_used = usage.get("episode_stored", 0)
        eps_limit = quotas.get("max_episodes", 0)
        active_color = "#10b981" if p["active"] else "#ef4444"
        tier_colors = {"starter": "#64748b", "growth": "#3B82F6", "enterprise": "#C74634"}
        tc = tier_colors.get(p["tier"], "#64748b")
        rows += (
            f"<tr><td><b>{p['name']}</b><br><span style='color:#64748b;font-size:.78em'>{p['id']}</span></td>"
            f"<td><span style='color:{tc};font-weight:bold'>{p['tier']}</span></td>"
            f"<td style='color:{active_color}'>{'Active' if p['active'] else 'Inactive'}</td>"
            f"<td>{gpu_used:.1f}/{gpu_limit}</td>"
            f"<td>{eps_used:.0f}/{eps_limit}</td>"
            f"<td style='color:#94a3b8;font-size:.85em'>{p['created_at'][:10]}</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan='6' style='color:#475569;text-align:center'>No partners registered</td></tr>"

    n_active = sum(1 for p in partners if p["active"])

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Multi-Tenant Manager — OCI Robot Cloud</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;
border-bottom:1px solid #1e293b;padding-bottom:5px;margin-top:28px}}
table{{width:100%;border-collapse:collapse}} th{{background:#C74634;color:white;padding:7px 12px;text-align:left;font-size:.82em}}
td{{padding:6px 12px;border-bottom:1px solid #1e293b;font-size:.88em}}
tr:nth-child(even) td{{background:#172033}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0}}
.card{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
.val{{font-size:2em;font-weight:bold}} .lbl{{color:#64748b;font-size:.78em}}
input{{background:#1e293b;color:#e2e8f0;border:1px solid #334155;padding:6px 10px;border-radius:6px;font-size:.9em}}
select{{background:#1e293b;color:#e2e8f0;border:1px solid #334155;padding:6px 10px;border-radius:6px}}
button.submit{{background:#C74634;color:white;border:none;padding:8px 18px;border-radius:6px;cursor:pointer}}
.form-row{{display:flex;gap:12px;align-items:flex-end;margin:12px 0}}
</style></head><body>
<h1>Multi-Tenant Manager</h1>
<p style="color:#64748b">OCI Robot Cloud · Workspace isolation · Port 8023</p>

<div class="grid">
  <div class="card"><div class="val" style="color:#10b981">{n_active}</div><div class="lbl">Active Partners</div></div>
  <div class="card"><div class="val">{len(partners)}</div><div class="lbl">Total Registered</div></div>
  <div class="card"><div class="val">{PARTNER_ROOT}</div><div class="lbl">Workspace Root</div></div>
</div>

<h2>Partners</h2>
<table>
  <tr><th>Partner</th><th>Tier</th><th>Status</th><th>GPU Hrs Used/Limit</th><th>Episodes Used/Limit</th><th>Created</th></tr>
  {rows}
</table>

<h2>Register New Partner (Admin)</h2>
<div class="form-row">
  <div><label style="color:#94a3b8;font-size:.78em;display:block;margin-bottom:4px">Name</label>
    <input id="pname" placeholder="Acme Robotics" /></div>
  <div><label style="color:#94a3b8;font-size:.78em;display:block;margin-bottom:4px">Email</label>
    <input id="pemail" placeholder="cto@acme.com" /></div>
  <div><label style="color:#94a3b8;font-size:.78em;display:block;margin-bottom:4px">Tier</label>
    <select id="ptier"><option>starter</option><option>growth</option><option>enterprise</option></select></div>
  <div><label style="color:#94a3b8;font-size:.78em;display:block;margin-bottom:4px">Admin Key</label>
    <input id="akey" placeholder="dev_admin_key" type="password" /></div>
  <button class="submit" onclick="createPartner()">Create Partner</button>
</div>
<div id="result" style="color:#10b981;font-family:monospace;font-size:.85em;margin:8px 0"></div>

<h2>Tier Quotas</h2>
<table>
  <tr><th>Tier</th><th>GPU Hours/mo</th><th>Max Episodes</th><th>Max Checkpoints</th><th>Concurrent Jobs</th></tr>
  {"".join(f"<tr><td><b style='color:{'#C74634' if t=='enterprise' else '#3B82F6' if t=='growth' else '#64748b'}'>{t}</b></td><td>{q['max_gpu_hours']}</td><td>{q['max_episodes']:,}</td><td>{q['max_checkpoints']}</td><td>{q['max_concurrent_jobs']}</td></tr>" for t,q in TIER_QUOTAS.items())}
</table>

<p style="color:#475569;font-size:.8em;margin-top:28px">OCI Robot Cloud · github.com/qianjun22/roboticsai</p>

<script>
async function createPartner() {{
  const res = await fetch("/partners", {{
    method: "POST",
    headers: {{"Content-Type":"application/json","X-Admin-Key": document.getElementById("akey").value}},
    body: JSON.stringify({{name: document.getElementById("pname").value,
      email: document.getElementById("pemail").value,
      tier: document.getElementById("ptier").value}})
  }});
  const j = await res.json();
  if (j.api_key) {{
    document.getElementById("result").innerHTML =
      "✓ Created! ID: " + j.id + "<br>API Key (save now): <b>" + j.api_key + "</b>";
    setTimeout(() => location.reload(), 4000);
  }} else {{
    document.getElementById("result").style.color = "#ef4444";
    document.getElementById("result").textContent = JSON.stringify(j);
  }}
}}
</script>
</body></html>"""


def seed_mock():
    """Seed two demo partners."""
    import time as _t
    _t.sleep(1)
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0] > 0:
        conn.close()
        return
    conn.close()
    for name, email, tier in [
        ("Acme Robotics (Demo)", "demo@acme.com", "growth"),
        ("Beta Test Partner", "test@robotstartup.ai", "starter"),
    ]:
        pid = "p_" + hashlib.md5(name.encode()).hexdigest()[:6]
        api_key = _make_api_key()
        workspace = _create_workspace(pid)
        quotas = TIER_QUOTAS[tier]
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO partners VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, name, email, tier, _hash_key(api_key),
             workspace, json.dumps(quotas), 1, datetime.now().isoformat())
        )
        conn.commit()
        # Track some usage
        for event, amt in [("gpu_hour", 3.2), ("episode_stored", 250), ("api_call", 142)]:
            conn.execute(
                "INSERT INTO usage (partner_id, event, amount, ts, metadata) VALUES (?,?,?,?,?)",
                (pid, event, amt, time.time(), "{}")
            )
        conn.commit()
        conn.close()
    print("[multi_tenant] Demo partners seeded")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8023)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    if args.mock:
        import threading
        threading.Thread(target=seed_mock, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
