#!/usr/bin/env python3
"""
webhook_notifications.py — Outbound webhook delivery service for OCI Robot Cloud.

Delivers training, eval, and drift events to design-partner Slack channels, email
endpoints, or generic HTTP webhooks. Backed by SQLite queue with retry logic.

Usage:
    python src/api/webhook_notifications.py [--port 8021] [--mock]

Endpoints:
    POST /webhooks           Register a webhook
    GET  /webhooks           List all registered webhooks
    DELETE /webhooks/{id}    Remove a webhook
    POST /events             Emit an event (internal — called by training pipeline)
    GET  /events             Recent event log
    GET  /health             Health check
    GET  /                   Dashboard

Event types:
    training.started    fine-tune job kicked off
    training.completed  checkpoint saved, eval launched
    eval.completed      success_rate result available
    drift.detected      >10pp success drop — retrain triggered
    checkpoint.promoted new checkpoint reached production
    error               pipeline error with context
"""

import argparse
import hashlib
import hmac
import json
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
import uvicorn

DB_PATH = "/tmp/webhooks.db"
MAX_RETRIES = 3
RETRY_DELAYS = [10, 60, 300]   # seconds between retries


# ── DB setup ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS webhooks (
        id          TEXT PRIMARY KEY,
        url         TEXT NOT NULL,
        secret      TEXT,
        events      TEXT NOT NULL,   -- JSON list of event types, [] = all
        label       TEXT,
        created_at  TEXT NOT NULL,
        active      INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS deliveries (
        id          TEXT PRIMARY KEY,
        webhook_id  TEXT NOT NULL,
        event_type  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        status      TEXT DEFAULT 'pending',   -- pending / delivered / failed
        attempts    INTEGER DEFAULT 0,
        next_retry  REAL,
        created_at  TEXT NOT NULL,
        delivered_at TEXT
    );
    CREATE TABLE IF NOT EXISTS events (
        id          TEXT PRIMARY KEY,
        event_type  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


# ── Models ────────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = []   # empty = subscribe to all
    label: str = ""


class EventEmit(BaseModel):
    event_type: str
    payload: dict = {}


# ── Delivery logic ────────────────────────────────────────────────────────────

def _sign(secret: str, body: bytes) -> str:
    if not secret:
        return ""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(delivery_id: str):
    """Try delivering a single delivery record. Called in background thread."""
    conn = get_db()
    row = conn.execute(
        "SELECT d.*, w.url, w.secret FROM deliveries d JOIN webhooks w ON d.webhook_id=w.id WHERE d.id=?",
        (delivery_id,)
    ).fetchone()
    if not row:
        conn.close()
        return

    body = json.dumps({
        "id": row["id"],
        "event_type": row["event_type"],
        "payload": json.loads(row["payload"]),
        "created_at": row["created_at"],
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OCI-RobotCloud-Webhooks/1.0",
        "X-Event-Type": row["event_type"],
    }
    sig = _sign(row["secret"] or "", body)
    if sig:
        headers["X-Signature-256"] = sig

    attempts = row["attempts"] + 1
    try:
        req = urllib.request.Request(row["url"], data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                conn.execute(
                    "UPDATE deliveries SET status='delivered', attempts=?, delivered_at=? WHERE id=?",
                    (attempts, datetime.now().isoformat(), delivery_id)
                )
            else:
                raise Exception(f"HTTP {resp.status}")
    except Exception as e:
        if attempts >= MAX_RETRIES:
            conn.execute(
                "UPDATE deliveries SET status='failed', attempts=? WHERE id=?",
                (attempts, delivery_id)
            )
        else:
            delay = RETRY_DELAYS[min(attempts - 1, len(RETRY_DELAYS) - 1)]
            conn.execute(
                "UPDATE deliveries SET attempts=?, next_retry=? WHERE id=?",
                (attempts, time.time() + delay, delivery_id)
            )
    conn.commit()
    conn.close()


def _fanout_event(event_id: str, event_type: str, payload: dict):
    """Create delivery records for all matching webhooks and dispatch."""
    conn = get_db()
    webhooks = conn.execute(
        "SELECT * FROM webhooks WHERE active=1"
    ).fetchall()

    for wh in webhooks:
        subscribed = json.loads(wh["events"])
        if subscribed and event_type not in subscribed:
            continue
        did = hashlib.md5(f"{event_id}:{wh['id']}".encode()).hexdigest()[:16]
        conn.execute(
            "INSERT OR IGNORE INTO deliveries VALUES (?,?,?,?,?,?,?,?,?)",
            (did, wh["id"], event_type, json.dumps(payload), "pending",
             0, time.time(), datetime.now().isoformat(), None)
        )
        conn.commit()
        threading.Thread(target=_deliver, args=(did,), daemon=True).start()
    conn.close()


def _retry_worker():
    """Background thread: retry failed/pending deliveries past their next_retry time."""
    while True:
        time.sleep(30)
        conn = get_db()
        due = conn.execute(
            "SELECT id FROM deliveries WHERE status='pending' AND next_retry <= ?",
            (time.time(),)
        ).fetchall()
        conn.close()
        for row in due:
            threading.Thread(target=_deliver, args=(row["id"],), daemon=True).start()


# ── API ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud — Webhook Notifications")
init_db()
threading.Thread(target=_retry_worker, daemon=True).start()


@app.get("/health")
def health():
    conn = get_db()
    n_webhooks = conn.execute("SELECT COUNT(*) FROM webhooks WHERE active=1").fetchone()[0]
    n_pending = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status='pending'").fetchone()[0]
    n_delivered = conn.execute("SELECT COUNT(*) FROM deliveries WHERE status='delivered'").fetchone()[0]
    conn.close()
    return {"status": "ok", "active_webhooks": n_webhooks,
            "pending_deliveries": n_pending, "total_delivered": n_delivered}


@app.post("/webhooks", status_code=201)
def register_webhook(body: WebhookCreate):
    wid = hashlib.md5(f"{body.url}:{time.time()}".encode()).hexdigest()[:12]
    conn = get_db()
    conn.execute(
        "INSERT INTO webhooks VALUES (?,?,?,?,?,?,?)",
        (wid, body.url, body.secret, json.dumps(body.events),
         body.label, datetime.now().isoformat(), 1)
    )
    conn.commit()
    conn.close()
    return {"id": wid, "url": body.url, "events": body.events,
            "message": "Webhook registered. Test with POST /events."}


@app.get("/webhooks")
def list_webhooks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM webhooks ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/webhooks/{wid}")
def delete_webhook(wid: str):
    conn = get_db()
    conn.execute("UPDATE webhooks SET active=0 WHERE id=?", (wid,))
    conn.commit()
    conn.close()
    return {"deleted": wid}


@app.post("/events", status_code=202)
def emit_event(body: EventEmit, background_tasks: BackgroundTasks):
    eid = hashlib.md5(f"{body.event_type}:{time.time()}".encode()).hexdigest()[:16]
    conn = get_db()
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?)",
        (eid, body.event_type, json.dumps(body.payload), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    background_tasks.add_task(_fanout_event, eid, body.event_type, body.payload)
    return {"event_id": eid, "event_type": body.event_type, "dispatching": True}


@app.get("/events")
def list_events(limit: int = 50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    deliveries = conn.execute(
        "SELECT event_type, status, COUNT(*) as n FROM deliveries GROUP BY event_type, status"
    ).fetchall()
    conn.close()
    return {
        "events": [dict(r) for r in rows],
        "delivery_stats": [dict(r) for r in deliveries],
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    conn = get_db()
    webhooks = conn.execute("SELECT * FROM webhooks WHERE active=1 ORDER BY created_at DESC").fetchall()
    recent_events = conn.execute(
        "SELECT * FROM events ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    deliveries = conn.execute(
        "SELECT d.*, w.url, w.label FROM deliveries d JOIN webhooks w ON d.webhook_id=w.id "
        "ORDER BY d.created_at DESC LIMIT 30"
    ).fetchall()
    conn.close()

    wh_rows = "".join(
        f"<tr><td><code>{w['id']}</code></td>"
        f"<td style='max-width:280px;overflow:hidden'>{w['url']}</td>"
        f"<td>{w['label'] or '—'}</td>"
        f"<td style='color:#94a3b8'>{json.loads(w['events']) or 'all'}</td>"
        f"<td><button onclick=\"fetch('/webhooks/{w['id']}',{{method:'DELETE'}}).then(()=>location.reload())\" "
        f"style='background:#ef4444;color:white;border:none;padding:3px 8px;border-radius:4px;cursor:pointer'>✕</button></td></tr>"
        for w in webhooks
    )

    ev_rows = "".join(
        f"<tr><td><span style='color:#C74634;font-family:monospace'>{e['event_type']}</span></td>"
        f"<td style='color:#94a3b8;font-size:.8em'>{e['created_at'][:19]}</td>"
        f"<td style='max-width:400px;font-size:.8em;color:#cbd5e1'><code>{e['payload'][:120]}</code></td></tr>"
        for e in recent_events
    )

    dl_rows = "".join(
        f"<tr><td>{d['event_type']}</td>"
        f"<td style='max-width:200px;overflow:hidden;font-size:.8em'>{d['url']}</td>"
        f"<td style='color:{\"#10b981\" if d[\"status\"]==\"delivered\" else \"#ef4444\" if d[\"status\"]==\"failed\" else \"#f59e0b\"}'>"
        f"{d['status']}</td>"
        f"<td style='color:#94a3b8'>{d['attempts']}</td>"
        f"<td style='color:#94a3b8;font-size:.8em'>{(d['delivered_at'] or d['created_at'])[:19]}</td></tr>"
        for d in deliveries
    )

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Webhook Notifications — OCI Robot Cloud</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;
border-bottom:1px solid #1e293b;padding-bottom:5px;margin-top:28px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}
th{{background:#C74634;color:white;padding:7px 12px;text-align:left;font-size:.82em}}
td{{padding:6px 12px;border-bottom:1px solid #1e293b;font-size:.85em}}
tr:nth-child(even) td{{background:#172033}}
input,select{{background:#1e293b;color:#e2e8f0;border:1px solid #334155;padding:6px 10px;border-radius:6px;font-size:.9em;width:100%;box-sizing:border-box}}
button.submit{{background:#C74634;color:white;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:.9em;margin-top:8px}}
.form-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;background:#1e293b;padding:16px;border-radius:8px;margin:12px 0}}
label{{color:#94a3b8;font-size:.78em;display:block;margin-bottom:4px}}
.pill{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75em;background:#1e293b;margin:2px}}
</style></head><body>
<h1>Webhook Notifications</h1>
<p style="color:#64748b">OCI Robot Cloud · Outbound event delivery · Port 8021</p>

<h2>Register Webhook</h2>
<div class="form-grid">
  <div>
    <label>Destination URL</label>
    <input id="url" placeholder="https://hooks.slack.com/services/..." />
  </div>
  <div>
    <label>Label (optional)</label>
    <input id="label" placeholder="Acme Robotics Slack" />
  </div>
  <div>
    <label>HMAC Secret (optional)</label>
    <input id="secret" placeholder="webhook_secret_key" type="password" />
  </div>
  <div>
    <label>Event Filter (comma-separated, blank = all)</label>
    <input id="events" placeholder="training.completed, eval.completed" />
  </div>
</div>
<button class="submit" onclick="registerWebhook()">Register Webhook</button>

<h2>Active Webhooks</h2>
<table>
  <tr><th>ID</th><th>URL</th><th>Label</th><th>Events</th><th>Remove</th></tr>
  {wh_rows or "<tr><td colspan='5' style='color:#475569;text-align:center'>No webhooks registered</td></tr>"}
</table>

<h2>Recent Events</h2>
<table>
  <tr><th>Type</th><th>Time</th><th>Payload</th></tr>
  {ev_rows or "<tr><td colspan='3' style='color:#475569;text-align:center'>No events yet</td></tr>"}
</table>

<h2>Delivery Log</h2>
<table>
  <tr><th>Event</th><th>Destination</th><th>Status</th><th>Attempts</th><th>Time</th></tr>
  {dl_rows or "<tr><td colspan='5' style='color:#475569;text-align:center'>No deliveries yet</td></tr>"}
</table>

<h2>Emit Test Event</h2>
<div class="form-grid">
  <div>
    <label>Event Type</label>
    <select id="etype">
      <option>training.started</option>
      <option>training.completed</option>
      <option>eval.completed</option>
      <option>drift.detected</option>
      <option>checkpoint.promoted</option>
      <option>error</option>
    </select>
  </div>
  <div>
    <label>Payload JSON</label>
    <input id="epayload" value='{{"success_rate": 0.25, "checkpoint": "checkpoint-5000"}}' />
  </div>
</div>
<button class="submit" onclick="emitEvent()">Emit Event</button>

<p style="color:#475569;font-size:.8em;margin-top:28px">OCI Robot Cloud · github.com/qianjun22/roboticsai</p>

<script>
async function registerWebhook() {{
  const events = document.getElementById("events").value.split(",").map(s=>s.trim()).filter(Boolean);
  const res = await fetch("/webhooks", {{
    method: "POST", headers: {{"Content-Type":"application/json"}},
    body: JSON.stringify({{
      url: document.getElementById("url").value,
      secret: document.getElementById("secret").value,
      label: document.getElementById("label").value,
      events
    }})
  }});
  const j = await res.json();
  alert("Registered: " + j.id); location.reload();
}}
async function emitEvent() {{
  let payload = {{}};
  try {{ payload = JSON.parse(document.getElementById("epayload").value); }} catch(e) {{}}
  const res = await fetch("/events", {{
    method: "POST", headers: {{"Content-Type":"application/json"}},
    body: JSON.stringify({{event_type: document.getElementById("etype").value, payload}})
  }});
  const j = await res.json();
  alert("Event emitted: " + j.event_id); location.reload();
}}
</script>
</body></html>"""


# ── Mock seeder ───────────────────────────────────────────────────────────────

def seed_mock():
    """Insert a sample webhook + fire test events for demo purposes."""
    import time as _time
    _time.sleep(1)
    try:
        conn = get_db()
        existing = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
        if existing == 0:
            wid = "demo_webhook"
            conn.execute(
                "INSERT OR IGNORE INTO webhooks VALUES (?,?,?,?,?,?,?)",
                (wid, "http://localhost:8021/health", "", "[]",
                 "Self-test (health endpoint)", datetime.now().isoformat(), 1)
            )
            conn.commit()
        conn.close()
        # Emit a few historical events
        import urllib.request as _ur, json as _j
        base = "http://localhost:8021"
        for evt in [
            ("training.started", {"checkpoint": "1000-demo-5k", "steps": 5000}),
            ("training.completed", {"checkpoint": "checkpoint-5000", "loss": 0.099}),
            ("eval.completed", {"success_rate": 0.05, "n_episodes": 20, "avg_latency_ms": 226}),
        ]:
            body = _j.dumps({"event_type": evt[0], "payload": evt[1]}).encode()
            req = _ur.Request(f"{base}/events", data=body,
                              headers={"Content-Type": "application/json"}, method="POST")
            try:
                _ur.urlopen(req, timeout=5)
            except Exception:
                pass
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8021)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    if args.mock:
        threading.Thread(target=seed_mock, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
