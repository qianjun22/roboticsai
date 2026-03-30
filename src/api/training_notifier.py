#!/usr/bin/env python3
"""
training_notifier.py — Push-notification service for OCI Robot Cloud training jobs.

Replaces manual SSH polling with real-time push notifications to design partners
via three delivery channels: webhook (HTTP POST + HMAC-SHA256), log-to-file, and
Server-Sent Events (SSE) stream.

Usage:
    python src/api/training_notifier.py [--port 8052] [--db /tmp/notifier.db]

Endpoints:
    POST   /subscribe               Register a partner subscription
    GET    /subscriptions           List all subscriptions
    DELETE /subscriptions/{id}      Remove a subscription
    POST   /notify                  Emit a notification event (internal / pipeline use)
    GET    /stream/{partner_id}     SSE stream — live events for a partner
    POST   /jobs/mock-train         Simulate a 5000-step training job (5 events over 30s)
    GET    /metrics                 Per-partner delivery stats
    GET    /queue                   Delivery queue status
    GET    /                        HTML dashboard (dark theme)
    GET    /health                  Health check

Notification types:
    training.started        fine-tune job kicked off
    checkpoint.saved        periodic checkpoint written (includes step + loss)
    training.completed      all steps done, model ready
    eval.result             success-rate result from closed-loop eval
    drift.detected          >10pp success drop detected
    retrain.triggered       auto-retrain scheduled

Delivery channels:
    webhook     HTTP POST to partner URL; body signed with HMAC-SHA256 (X-OCI-Signature)
    file        Append JSON lines to a local log file
    sse         Server-Sent Events — partner polls /stream/{partner_id}

Retry policy:
    Up to 3 attempts with exponential backoff: 5s → 15s → 45s

Seeded partners (webhook channel):
    acme-robotics    https://hooks.example.com/acme
    autobot-inc      https://hooks.example.com/autobot
    deepmanip-ai     https://hooks.example.com/deepmanip

Dependencies:
    pip install fastapi uvicorn
    stdlib: sqlite3, hmac, hashlib, asyncio, json, logging, threading, queue, time
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import queue
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8052
DEFAULT_DB = "/tmp/training_notifier.db"

RETRY_DELAYS = [5, 15, 45]  # seconds between attempts 1→2, 2→3

VALID_EVENT_TYPES = {
    "training.started",
    "checkpoint.saved",
    "training.completed",
    "eval.result",
    "drift.detected",
    "retrain.triggered",
}

SEED_PARTNERS = [
    {
        "partner_id": "acme-robotics",
        "channel": "webhook",
        "endpoint": "https://hooks.example.com/acme",
        "secret": "acme-secret-key-0001",
        "events": ["training.started", "checkpoint.saved", "training.completed", "eval.result"],
    },
    {
        "partner_id": "autobot-inc",
        "channel": "webhook",
        "endpoint": "https://hooks.example.com/autobot",
        "secret": "autobot-secret-key-0002",
        "events": ["training.completed", "eval.result", "drift.detected", "retrain.triggered"],
    },
    {
        "partner_id": "deepmanip-ai",
        "channel": "webhook",
        "endpoint": "https://hooks.example.com/deepmanip",
        "secret": "deepmanip-secret-key-0003",
        "events": [
            "training.started",
            "checkpoint.saved",
            "training.completed",
            "eval.result",
            "drift.detected",
            "retrain.triggered",
        ],
    },
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("training_notifier")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id          TEXT PRIMARY KEY,
            partner_id  TEXT NOT NULL,
            channel     TEXT NOT NULL,       -- 'webhook' | 'file' | 'sse'
            endpoint    TEXT,                -- URL for webhook, path for file, NULL for sse
            secret      TEXT,                -- HMAC secret for webhook
            events      TEXT NOT NULL,       -- JSON array of event types
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id          TEXT PRIMARY KEY,
            event_type  TEXT NOT NULL,
            payload     TEXT NOT NULL,       -- full JSON payload
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS delivery_queue (
            id              TEXT PRIMARY KEY,
            notification_id TEXT NOT NULL,
            subscription_id TEXT NOT NULL,
            partner_id      TEXT NOT NULL,
            status          TEXT NOT NULL,   -- 'pending' | 'delivered' | 'failed'
            attempts        INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT NOT NULL,
            last_error      TEXT,
            delivered_at    TEXT,
            created_at      TEXT NOT NULL
        );
        """
    )
    conn.commit()

    # Seed partners if table is empty
    cur.execute("SELECT COUNT(*) FROM subscriptions")
    count = cur.fetchone()[0]
    if count == 0:
        for p in SEED_PARTNERS:
            cur.execute(
                """
                INSERT INTO subscriptions (id, partner_id, channel, endpoint, secret, events, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    p["partner_id"],
                    p["channel"],
                    p["endpoint"],
                    p["secret"],
                    json.dumps(p["events"]),
                    _now(),
                ),
            )
        conn.commit()
        log.info("Seeded %d partner subscriptions", len(SEED_PARTNERS))

    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SSE broker — fan-out live events to connected clients
# ---------------------------------------------------------------------------


class SSEBroker:
    """Thread-safe fan-out broker for Server-Sent Events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[str, list[queue.Queue]] = {}

    def subscribe(self, partner_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._queues.setdefault(partner_id, []).append(q)
        return q

    def unsubscribe(self, partner_id: str, q: queue.Queue) -> None:
        with self._lock:
            qs = self._queues.get(partner_id, [])
            try:
                qs.remove(q)
            except ValueError:
                pass

    def publish(self, partner_id: str, data: dict) -> int:
        """Send event to all active SSE connections for a partner. Returns recipient count."""
        msg = json.dumps(data)
        delivered = 0
        with self._lock:
            qs = list(self._queues.get(partner_id, []))
        for q in qs:
            try:
                q.put_nowait(msg)
                delivered += 1
            except queue.Full:
                pass
        return delivered

    def broadcast(self, data: dict) -> int:
        """Send to all partners."""
        total = 0
        with self._lock:
            partner_ids = list(self._queues.keys())
        for pid in partner_ids:
            total += self.publish(pid, data)
        return total


sse_broker = SSEBroker()

# ---------------------------------------------------------------------------
# Delivery worker
# ---------------------------------------------------------------------------


class DeliveryWorker:
    """Background thread that drains the delivery queue with retry/backoff."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="delivery-worker")

    def start(self) -> None:
        self._thread.start()
        log.info("Delivery worker started")

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import urllib.request

        while not self._stop.is_set():
            try:
                self._process_due(urllib.request)
            except Exception as exc:
                log.exception("Delivery worker error: %s", exc)
            time.sleep(2)

    def _process_due(self, urllib_request) -> None:
        conn = get_db(self.db_path)
        cur = conn.cursor()
        now = _now()

        # Fetch all pending/retryable items due now
        cur.execute(
            """
            SELECT dq.id, dq.notification_id, dq.subscription_id, dq.partner_id,
                   dq.attempts, n.event_type, n.payload,
                   s.channel, s.endpoint, s.secret
            FROM delivery_queue dq
            JOIN notifications n ON n.id = dq.notification_id
            JOIN subscriptions s ON s.id = dq.subscription_id
            WHERE dq.status = 'pending'
              AND dq.next_attempt_at <= ?
            ORDER BY dq.created_at
            LIMIT 50
            """,
            (now,),
        )
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            self._deliver(row, urllib_request)

    def _deliver(self, row: sqlite3.Row, urllib_request) -> None:
        import urllib.error

        conn = get_db(self.db_path)
        cur = conn.cursor()

        item_id = row["id"]
        attempts = row["attempts"] + 1
        channel = row["channel"]
        payload = json.loads(row["payload"])

        success = False
        error_msg: Optional[str] = None

        try:
            if channel == "webhook":
                success = self._send_webhook(row, payload, urllib_request)
            elif channel == "file":
                success = self._send_file(row, payload)
            elif channel == "sse":
                delivered = sse_broker.publish(row["partner_id"], payload)
                success = delivered > 0
                if not success:
                    error_msg = "No active SSE connections"
        except Exception as exc:
            error_msg = str(exc)
            log.warning("Delivery attempt %d failed for %s: %s", attempts, item_id, exc)

        if success:
            cur.execute(
                "UPDATE delivery_queue SET status='delivered', attempts=?, delivered_at=? WHERE id=?",
                (attempts, _now(), item_id),
            )
            log.info(
                "Delivered [%s] %s → %s (%s)",
                row["event_type"],
                row["notification_id"][:8],
                row["partner_id"],
                channel,
            )
        elif attempts >= 3:
            cur.execute(
                "UPDATE delivery_queue SET status='failed', attempts=?, last_error=? WHERE id=?",
                (attempts, error_msg, item_id),
            )
            log.warning("Max retries reached for %s → giving up", item_id)
        else:
            delay = RETRY_DELAYS[attempts - 1] if attempts - 1 < len(RETRY_DELAYS) else 60
            next_at = datetime.fromtimestamp(time.time() + delay, tz=timezone.utc).isoformat()
            cur.execute(
                "UPDATE delivery_queue SET attempts=?, next_attempt_at=?, last_error=? WHERE id=?",
                (attempts, next_at, error_msg, item_id),
            )

        conn.commit()
        conn.close()

    def _send_webhook(self, row: sqlite3.Row, payload: dict, urllib_request) -> bool:
        import urllib.error
        import urllib.request as ur

        body = json.dumps(payload).encode()
        secret = (row["secret"] or "").encode()
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()

        req = ur.Request(
            row["endpoint"],
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-OCI-Signature": f"sha256={sig}",
                "X-OCI-Event": row["event_type"],
                "User-Agent": "OCI-RobotCloud-Notifier/1.0",
            },
            method="POST",
        )
        try:
            with ur.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"URL error: {e.reason}") from e

    def _send_file(self, row: sqlite3.Row, payload: dict) -> bool:
        path = row["endpoint"] or f"/tmp/oci_notifier_{row['partner_id']}.jsonl"
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps(payload) + "\n")
        return True


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


class AppState:
    db_path: str = DEFAULT_DB
    worker: Optional[DeliveryWorker] = None


state = AppState()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(state.db_path)
    state.worker = DeliveryWorker(state.db_path)
    state.worker.start()
    yield
    if state.worker:
        state.worker.stop()


app = FastAPI(
    title="OCI Robot Cloud — Training Notifier",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SubscribeRequest(BaseModel):
    partner_id: str
    channel: str  # webhook | file | sse
    endpoint: Optional[str] = None
    secret: Optional[str] = None
    events: list[str]


class NotifyRequest(BaseModel):
    event_type: str
    partner_id: Optional[str] = None  # None = broadcast to all subscribed
    data: dict = {}


# ---------------------------------------------------------------------------
# Helper: enqueue a notification for delivery
# ---------------------------------------------------------------------------


def _enqueue_notification(conn: sqlite3.Connection, notif_id: str, payload: dict) -> int:
    cur = conn.cursor()
    event_type = payload["event_type"]
    partner_id = payload.get("partner_id")

    if partner_id:
        cur.execute(
            "SELECT * FROM subscriptions WHERE partner_id = ?", (partner_id,)
        )
    else:
        cur.execute("SELECT * FROM subscriptions")

    subs = cur.fetchall()
    enqueued = 0
    for sub in subs:
        subscribed_events = json.loads(sub["events"])
        if event_type not in subscribed_events:
            continue
        cur.execute(
            """
            INSERT INTO delivery_queue
              (id, notification_id, subscription_id, partner_id, status, attempts, next_attempt_at, created_at)
            VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            (str(uuid.uuid4()), notif_id, sub["id"], sub["partner_id"], _now(), _now()),
        )
        enqueued += 1

    conn.commit()
    return enqueued


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "training_notifier", "port": DEFAULT_PORT}


@app.post("/subscribe", status_code=201)
def subscribe(req: SubscribeRequest):
    if req.channel not in ("webhook", "file", "sse"):
        raise HTTPException(400, "channel must be webhook | file | sse")
    for ev in req.events:
        if ev not in VALID_EVENT_TYPES:
            raise HTTPException(400, f"Unknown event type: {ev}")
    if req.channel == "webhook" and not req.endpoint:
        raise HTTPException(400, "endpoint required for webhook channel")

    sub_id = str(uuid.uuid4())
    secret = req.secret or secrets.token_hex(16)
    conn = get_db(state.db_path)
    conn.execute(
        """
        INSERT INTO subscriptions (id, partner_id, channel, endpoint, secret, events, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (sub_id, req.partner_id, req.channel, req.endpoint, secret, json.dumps(req.events), _now()),
    )
    conn.commit()
    conn.close()
    log.info("New subscription: %s / %s / %s", req.partner_id, req.channel, req.events)
    return {"id": sub_id, "partner_id": req.partner_id, "secret": secret}


@app.get("/subscriptions")
def list_subscriptions():
    conn = get_db(state.db_path)
    rows = conn.execute("SELECT * FROM subscriptions ORDER BY created_at").fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "partner_id": r["partner_id"],
            "channel": r["channel"],
            "endpoint": r["endpoint"],
            "events": json.loads(r["events"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.delete("/subscriptions/{sub_id}")
def delete_subscription(sub_id: str):
    conn = get_db(state.db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Subscription not found")
    conn.commit()
    conn.close()
    return {"deleted": sub_id}


@app.post("/notify", status_code=202)
def notify(req: NotifyRequest):
    if req.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(400, f"Unknown event type: {req.event_type}")

    notif_id = str(uuid.uuid4())
    payload = {
        "id": notif_id,
        "event_type": req.event_type,
        "partner_id": req.partner_id,
        "data": req.data,
        "timestamp": _now(),
    }

    conn = get_db(state.db_path)
    conn.execute(
        "INSERT INTO notifications (id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (notif_id, req.event_type, json.dumps(payload), _now()),
    )
    enqueued = _enqueue_notification(conn, notif_id, payload)
    conn.close()

    # Also fan-out SSE immediately (best-effort)
    if req.partner_id:
        sse_broker.publish(req.partner_id, payload)
    else:
        sse_broker.broadcast(payload)

    log.info("Notification %s (%s) enqueued for %d subscriptions", notif_id[:8], req.event_type, enqueued)
    return {"notification_id": notif_id, "enqueued": enqueued}


@app.get("/stream/{partner_id}")
async def sse_stream(partner_id: str, request: Request):
    """Server-Sent Events endpoint — partners connect once and receive live notifications."""

    async def event_generator() -> AsyncGenerator[str, None]:
        q = sse_broker.subscribe(partner_id)
        log.info("SSE client connected: %s", partner_id)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'partner_id': partner_id})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Poll queue with short timeout to stay responsive to disconnect
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=1)
                    )
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            sse_broker.unsubscribe(partner_id, q)
            log.info("SSE client disconnected: %s", partner_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/jobs/mock-train")
async def mock_train(background_tasks: BackgroundTasks):
    """
    Simulate a 5000-step training job that emits 5 push notifications over ~30 seconds:
      t=0s   training.started
      t=6s   checkpoint.saved  (step 1000, loss 0.312)
      t=12s  checkpoint.saved  (step 3000, loss 0.187)
      t=18s  checkpoint.saved  (step 5000, loss 0.099)
      t=24s  training.completed
      t=30s  eval.result       (success_rate 0.72)
    """
    job_id = str(uuid.uuid4())[:8]

    async def run_mock():
        events = [
            (0,  "training.started",    {"job_id": job_id, "total_steps": 5000, "model": "gr00t-n1.6", "dataset": "pick_cube_1000"}),
            (6,  "checkpoint.saved",    {"job_id": job_id, "step": 1000, "loss": 0.312, "checkpoint": f"ckpt-{job_id}-1000"}),
            (12, "checkpoint.saved",    {"job_id": job_id, "step": 3000, "loss": 0.187, "checkpoint": f"ckpt-{job_id}-3000"}),
            (18, "checkpoint.saved",    {"job_id": job_id, "step": 5000, "loss": 0.099, "checkpoint": f"ckpt-{job_id}-5000"}),
            (24, "training.completed",  {"job_id": job_id, "total_steps": 5000, "final_loss": 0.099, "duration_s": 2124}),
            (30, "eval.result",         {"job_id": job_id, "success_rate": 0.72, "episodes": 20, "checkpoint": f"ckpt-{job_id}-5000"}),
        ]

        prev_t = 0
        for delay, event_type, data in events:
            await asyncio.sleep(delay - prev_t)
            prev_t = delay
            notif_id = str(uuid.uuid4())
            payload = {
                "id": notif_id,
                "event_type": event_type,
                "partner_id": None,
                "data": data,
                "timestamp": _now(),
            }
            conn = get_db(state.db_path)
            conn.execute(
                "INSERT INTO notifications (id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (notif_id, event_type, json.dumps(payload), _now()),
            )
            _enqueue_notification(conn, notif_id, payload)
            conn.close()
            sse_broker.broadcast(payload)
            log.info("[mock-train %s] %s", job_id, event_type)

    background_tasks.add_task(run_mock)
    return {"job_id": job_id, "message": "Mock training job started; 6 events over 30s"}


@app.get("/metrics")
def metrics():
    conn = get_db(state.db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT partner_id,
               COUNT(*) AS total,
               SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN status='pending'   THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status='failed'    THEN 1 ELSE 0 END) AS failed
        FROM delivery_queue
        GROUP BY partner_id
        ORDER BY partner_id
        """
    )
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM notifications")
    total_notifs = cur.fetchone()[0]
    conn.close()

    partners = []
    for r in rows:
        total = r["total"] or 1
        partners.append(
            {
                "partner_id": r["partner_id"],
                "total": r["total"],
                "delivered": r["delivered"],
                "pending": r["pending"],
                "failed": r["failed"],
                "success_rate": round(r["delivered"] / total, 3),
            }
        )

    return {"total_notifications": total_notifs, "partners": partners}


@app.get("/queue")
def queue_status():
    conn = get_db(state.db_path)
    rows = conn.execute(
        """
        SELECT dq.id, dq.partner_id, dq.status, dq.attempts, dq.next_attempt_at,
               dq.last_error, dq.delivered_at, n.event_type, dq.created_at
        FROM delivery_queue dq
        JOIN notifications n ON n.id = dq.notification_id
        ORDER BY dq.created_at DESC
        LIMIT 100
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Training Notifier</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
    --text: #e2e8f0; --muted: #718096; --accent: #7c3aed;
    --green: #22c55e; --yellow: #eab308; --red: #ef4444; --blue: #3b82f6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; color: #a78bfa; }
  header span { color: var(--muted); font-size: 12px; }
  main { padding: 24px; max-width: 1400px; margin: 0 auto; }
  h2 { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; margin-top: 28px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .card .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
  th { background: #12151f; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
  td { padding: 10px 14px; border-bottom: 1px solid #1e2130; font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
  .badge-delivered { background: #14532d; color: var(--green); }
  .badge-pending   { background: #713f12; color: var(--yellow); }
  .badge-failed    { background: #7f1d1d; color: var(--red); }
  .rate-bar { display: flex; align-items: center; gap: 8px; }
  .bar-bg { flex: 1; height: 6px; background: var(--border); border-radius: 3px; }
  .bar-fill { height: 6px; border-radius: 3px; background: var(--green); }
  form.sub-form { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  form.sub-form label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }
  form.sub-form input, form.sub-form select { width: 100%; background: #12151f; border: 1px solid var(--border); border-radius: 4px; color: var(--text); padding: 7px 10px; font-size: 13px; }
  form.sub-form .full { grid-column: 1 / -1; }
  form.sub-form button { background: var(--accent); color: white; border: none; border-radius: 4px; padding: 8px 16px; cursor: pointer; font-size: 13px; font-weight: 600; }
  form.sub-form button:hover { background: #6d28d9; }
  .mock-btn { background: #1e3a5f; color: var(--blue); border: 1px solid var(--blue); border-radius: 6px; padding: 8px 18px; cursor: pointer; font-size: 13px; font-weight: 600; margin-top: 8px; }
  .mock-btn:hover { background: #1d4ed8; color: white; }
  #live-log { background: #0a0c12; border: 1px solid var(--border); border-radius: 8px; padding: 14px; height: 220px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #94a3b8; }
  #live-log .ev { margin-bottom: 4px; }
  #live-log .ts { color: #4b5563; margin-right: 6px; }
  #live-log .type { font-weight: 600; margin-right: 6px; }
  .t-started   { color: #60a5fa; }
  .t-checkpoint { color: #a78bfa; }
  .t-completed  { color: var(--green); }
  .t-eval       { color: #34d399; }
  .t-drift      { color: var(--red); }
  .t-retrain    { color: var(--yellow); }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
</style>
</head>
<body>
<header>
  <h1>&#9711; OCI Robot Cloud — Training Notifier</h1>
  <span>port 8052 &nbsp;|&nbsp; push notifications for design partners</span>
</header>
<main>

<h2>Overview</h2>
<div class="grid-3" id="stats-cards">
  <div class="card"><div class="label">Total Notifications</div><div class="value" id="st-total">—</div></div>
  <div class="card"><div class="label">Delivered</div><div class="value" style="color:var(--green)" id="st-delivered">—</div></div>
  <div class="card"><div class="label">Pending / Failed</div><div class="value" id="st-pf">—</div></div>
</div>

<h2>Per-Partner Delivery Stats</h2>
<table id="metrics-table">
  <thead><tr><th>Partner</th><th>Total</th><th>Delivered</th><th>Pending</th><th>Failed</th><th>Success Rate</th></tr></thead>
  <tbody id="metrics-body"><tr><td colspan="6" style="color:var(--muted)">Loading…</td></tr></tbody>
</table>

<h2>Recent Delivery Queue (last 30)</h2>
<table>
  <thead><tr><th>Event</th><th>Partner</th><th>Status</th><th>Attempts</th><th>Created</th><th>Error</th></tr></thead>
  <tbody id="queue-body"><tr><td colspan="6" style="color:var(--muted)">Loading…</td></tr></tbody>
</table>

<h2>Live Event Stream</h2>
<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
  <span class="status-dot" id="sse-dot" style="background:var(--yellow)"></span>
  <span id="sse-status" style="color:var(--muted);font-size:12px">Connecting to SSE stream…</span>
</div>
<div id="live-log"></div>

<h2>Mock Training Job</h2>
<p style="color:var(--muted);font-size:12px;margin-bottom:8px">Simulates a 5000-step job: start → ckpt 1000 → ckpt 3000 → ckpt 5000 → completed → eval result (over 30s)</p>
<button class="mock-btn" onclick="startMockJob()">&#9654; Start Mock Training Job</button>
<div id="mock-status" style="color:var(--muted);font-size:12px;margin-top:6px"></div>

<h2>Add Subscription</h2>
<form class="sub-form" onsubmit="addSubscription(event)">
  <div><label>Partner ID</label><input id="f-pid" placeholder="my-partner" required></div>
  <div><label>Channel</label>
    <select id="f-chan">
      <option value="webhook">webhook</option>
      <option value="file">file</option>
      <option value="sse">sse</option>
    </select>
  </div>
  <div><label>Endpoint (URL or file path)</label><input id="f-endpoint" placeholder="https://hooks.example.com/…"></div>
  <div><label>Secret (optional)</label><input id="f-secret" placeholder="auto-generated if blank"></div>
  <div class="full">
    <label>Events (comma-separated)</label>
    <input id="f-events" placeholder="training.started, checkpoint.saved, training.completed, eval.result" value="training.started, checkpoint.saved, training.completed, eval.result">
  </div>
  <div class="full"><button type="submit">Subscribe</button> <span id="sub-msg" style="color:var(--green);margin-left:10px;font-size:12px"></span></div>
</form>

<h2>Current Subscriptions</h2>
<table>
  <thead><tr><th>Partner</th><th>Channel</th><th>Endpoint</th><th>Events</th><th>Created</th></tr></thead>
  <tbody id="subs-body"><tr><td colspan="5" style="color:var(--muted)">Loading…</td></tr></tbody>
</table>

</main>
<script>
const LOG = document.getElementById('live-log');
const MAX_LOG = 80;

function typeClass(t) {
  if (t === 'training.started') return 't-started';
  if (t.startsWith('checkpoint')) return 't-checkpoint';
  if (t === 'training.completed') return 't-completed';
  if (t === 'eval.result') return 't-eval';
  if (t === 'drift.detected') return 't-drift';
  if (t === 'retrain.triggered') return 't-retrain';
  return '';
}

function appendLog(text, cls='') {
  const ts = new Date().toTimeString().slice(0,8);
  const div = document.createElement('div');
  div.className = 'ev';
  div.innerHTML = `<span class="ts">${ts}</span><span class="type ${cls}">${text}</span>`;
  LOG.prepend(div);
  while (LOG.children.length > MAX_LOG) LOG.removeChild(LOG.lastChild);
}

// SSE connection to "dashboard" stream
function connectSSE() {
  const src = new EventSource('/stream/dashboard');
  const dot = document.getElementById('sse-dot');
  const st = document.getElementById('sse-status');
  src.onopen = () => {
    dot.style.background = 'var(--green)';
    st.textContent = 'Connected to live stream';
  };
  src.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'connected') { appendLog('SSE connected', 't-started'); return; }
      const evt = msg.event_type || '';
      const pid = msg.partner_id || 'broadcast';
      const info = JSON.stringify(msg.data || {});
      appendLog(`[${evt}] partner=${pid} ${info}`, typeClass(evt));
      refreshMetrics();
      refreshQueue();
    } catch(ex) {}
  };
  src.onerror = () => {
    dot.style.background = 'var(--red)';
    st.textContent = 'SSE disconnected — retrying…';
    appendLog('SSE disconnected', 't-drift');
    setTimeout(connectSSE, 5000);
    src.close();
  };
}

async function refreshMetrics() {
  const r = await fetch('/metrics');
  const d = await r.json();
  document.getElementById('st-total').textContent = d.total_notifications;
  let totD=0, totP=0, totF=0;
  d.partners.forEach(p => { totD+=p.delivered; totP+=p.pending; totF+=p.failed; });
  document.getElementById('st-delivered').textContent = totD;
  document.getElementById('st-pf').textContent = `${totP} / ${totF}`;
  const tb = document.getElementById('metrics-body');
  if (!d.partners.length) { tb.innerHTML = '<tr><td colspan="6" style="color:var(--muted)">No data yet</td></tr>'; return; }
  tb.innerHTML = d.partners.map(p => {
    const pct = Math.round(p.success_rate * 100);
    return `<tr>
      <td><strong>${p.partner_id}</strong></td>
      <td>${p.total}</td>
      <td style="color:var(--green)">${p.delivered}</td>
      <td style="color:var(--yellow)">${p.pending}</td>
      <td style="color:var(--red)">${p.failed}</td>
      <td><div class="rate-bar"><div class="bar-bg"><div class="bar-fill" style="width:${pct}%"></div></div><span>${pct}%</span></div></td>
    </tr>`;
  }).join('');
}

async function refreshQueue() {
  const r = await fetch('/queue');
  const items = await r.json();
  const tb = document.getElementById('queue-body');
  if (!items.length) { tb.innerHTML = '<tr><td colspan="6" style="color:var(--muted)">Empty</td></tr>'; return; }
  tb.innerHTML = items.slice(0,30).map(i => {
    const badgeCls = i.status === 'delivered' ? 'badge-delivered' : i.status === 'pending' ? 'badge-pending' : 'badge-failed';
    const ts = (i.created_at||'').slice(0,19).replace('T',' ');
    return `<tr>
      <td>${i.event_type}</td>
      <td>${i.partner_id}</td>
      <td><span class="badge ${badgeCls}">${i.status}</span></td>
      <td>${i.attempts}</td>
      <td style="color:var(--muted)">${ts}</td>
      <td style="color:var(--red);font-size:11px">${i.last_error||''}</td>
    </tr>`;
  }).join('');
}

async function refreshSubs() {
  const r = await fetch('/subscriptions');
  const items = await r.json();
  const tb = document.getElementById('subs-body');
  if (!items.length) { tb.innerHTML = '<tr><td colspan="5" style="color:var(--muted)">None</td></tr>'; return; }
  tb.innerHTML = items.map(s => {
    const evs = (s.events||[]).map(e=>`<span style="font-size:11px;color:var(--accent)">${e}</span>`).join(' ');
    const ts = (s.created_at||'').slice(0,19).replace('T',' ');
    return `<tr>
      <td><strong>${s.partner_id}</strong></td>
      <td>${s.channel}</td>
      <td style="font-size:12px;color:var(--muted)">${s.endpoint||'—'}</td>
      <td>${evs}</td>
      <td style="color:var(--muted)">${ts}</td>
    </tr>`;
  }).join('');
}

async function startMockJob() {
  const r = await fetch('/jobs/mock-train', {method:'POST'});
  const d = await r.json();
  document.getElementById('mock-status').textContent = `Job ${d.job_id} started — watch live stream above`;
}

async function addSubscription(ev) {
  ev.preventDefault();
  const pid = document.getElementById('f-pid').value.trim();
  const chan = document.getElementById('f-chan').value;
  const endpoint = document.getElementById('f-endpoint').value.trim();
  const secret = document.getElementById('f-secret').value.trim();
  const evStr = document.getElementById('f-events').value;
  const events = evStr.split(',').map(s=>s.trim()).filter(Boolean);
  const body = {partner_id:pid, channel:chan, events};
  if (endpoint) body.endpoint = endpoint;
  if (secret) body.secret = secret;
  const r = await fetch('/subscribe', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const d = await r.json();
  if (r.ok) {
    document.getElementById('sub-msg').textContent = `Subscribed! secret=${d.secret}`;
    refreshSubs();
  } else {
    document.getElementById('sub-msg').textContent = d.detail || 'Error';
  }
}

// Initial load
refreshMetrics();
refreshQueue();
refreshSubs();
setInterval(() => { refreshMetrics(); refreshQueue(); }, 5000);
connectSSE();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Training Notifier Service")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default {DEFAULT_PORT})")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default {DEFAULT_DB})")
    args = parser.parse_args()

    state.db_path = args.db
    log.info("Starting training_notifier on port %d, db=%s", args.port, args.db)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
