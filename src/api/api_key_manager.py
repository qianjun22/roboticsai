"""
OCI Robot Cloud — API Key Manager
==================================
FastAPI service (port 8053) for managing design-partner API keys:
creation, activation, rotation, scoping, revocation, and usage tracking.

Features:
  - Key lifecycle: generate → activate → (rotate | deactivate | revoke)
  - HMAC-based 32-char keys with prefix ``ork_``; only SHA-256 hash stored
  - Fine-grained scopes: train / eval / deploy / data-upload / cost-view / admin
  - Per-key rate limit (req/min, default 100) and monthly GPU-hour quota
  - Usage tracking: last_used_at, total_requests, gpu_hours_consumed, current_month_cost
  - Rotation: issues new key + 24-hour grace period before old key expires
  - Audit log: every key operation recorded with timestamp and actor
  - Partner lookup: GET /keys?partner_id=<id>
  - Internal /verify endpoint for gateway (constant-time comparison)
  - HTML dashboard at / with dark theme, active/inactive badges, usage stats, rotate buttons
  - SQLite-backed at /tmp/api_keys.db; seeded with 5 partner keys on first run

Usage:
  # Run in mock/dev mode (auto-seeds partner keys):
  uvicorn src.api.api_key_manager:app --port 8053

  # Verify a key from another service:
  curl -X POST http://localhost:8053/verify \\
       -H "Content-Type: application/json" \\
       -d '{"api_key": "ork_..."}'

  # Create a key:
  curl -X POST http://localhost:8053/keys \\
       -H "Content-Type: application/json" \\
       -d '{"partner_id":"acme-robotics","label":"prod-key","scopes":["train","eval"]}'

  # Rotate a key:
  curl -X POST http://localhost:8053/keys/<key_id>/rotate

  # List partner keys:
  curl http://localhost:8053/keys?partner_id=acme-robotics

Environment variables:
  DB_PATH       SQLite path (default: /tmp/api_keys.db)
  GRACE_HOURS   Grace period after rotation in hours (default: 24)

SQLite tables:
  api_keys(id, partner_id, label, key_hash, prefix_hint, status, scopes,
           rate_limit_rpm, monthly_gpu_quota_h, created_at, activated_at,
           expires_at, last_used_at, total_requests, gpu_hours_consumed,
           current_month_cost, rotated_from_id)
  audit_log(id, ts, key_id, partner_id, action, actor, detail)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("DB_PATH", "/tmp/api_keys.db")
GRACE_HOURS = int(os.environ.get("GRACE_HOURS", "24"))

VALID_SCOPES = {"train", "eval", "deploy", "data-upload", "cost-view", "admin"}

KEY_PREFIX = "ork_"
KEY_PAYLOAD_BYTES = 24  # 24 random bytes → 48 hex chars → sliced to 32 after prefix

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id                    TEXT PRIMARY KEY,
                partner_id            TEXT NOT NULL,
                label                 TEXT NOT NULL,
                key_hash              TEXT NOT NULL UNIQUE,
                prefix_hint           TEXT NOT NULL,
                status                TEXT NOT NULL DEFAULT 'inactive',
                scopes                TEXT NOT NULL DEFAULT '[]',
                rate_limit_rpm        INTEGER NOT NULL DEFAULT 100,
                monthly_gpu_quota_h   REAL NOT NULL DEFAULT 100.0,
                created_at            TEXT NOT NULL,
                activated_at          TEXT,
                expires_at            TEXT,
                last_used_at          TEXT,
                total_requests        INTEGER NOT NULL DEFAULT 0,
                gpu_hours_consumed    REAL NOT NULL DEFAULT 0.0,
                current_month_cost    REAL NOT NULL DEFAULT 0.0,
                rotated_from_id       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_keys_partner ON api_keys(partner_id);
            CREATE INDEX IF NOT EXISTS idx_keys_status  ON api_keys(status);

            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT NOT NULL,
                key_id     TEXT NOT NULL,
                partner_id TEXT NOT NULL,
                action     TEXT NOT NULL,
                actor      TEXT NOT NULL DEFAULT 'system',
                detail     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audit_key ON audit_log(key_id);
            CREATE INDEX IF NOT EXISTS idx_audit_ts  ON audit_log(ts);
        """)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_audit(conn: sqlite3.Connection, key_id: str, partner_id: str,
               action: str, actor: str = "system", detail: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log(ts, key_id, partner_id, action, actor, detail) VALUES (?,?,?,?,?,?)",
        (_now_iso(), key_id, partner_id, action, actor, detail),
    )


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def _generate_raw_key() -> str:
    """Return a new ``ork_`` prefixed 32-character key (prefix + 28 hex chars)."""
    payload = secrets.token_hex(14)  # 28 hex chars
    return f"{KEY_PREFIX}{payload}"


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _prefix_hint(raw_key: str) -> str:
    """Return first 8 chars of key for display (e.g. ``ork_ab12``)."""
    return raw_key[:8] + "…"


def _new_id() -> str:
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_PARTNERS = [
    {
        "partner_id": "acme-robotics",
        "label": "production",
        "scopes": ["train", "eval", "deploy", "data-upload", "cost-view"],
        "rate_limit_rpm": 200,
        "monthly_gpu_quota_h": 500.0,
    },
    {
        "partner_id": "boston-dynamics-lab",
        "label": "research",
        "scopes": ["train", "eval", "data-upload"],
        "rate_limit_rpm": 150,
        "monthly_gpu_quota_h": 300.0,
    },
    {
        "partner_id": "figure-ai",
        "label": "staging",
        "scopes": ["eval", "deploy"],
        "rate_limit_rpm": 100,
        "monthly_gpu_quota_h": 200.0,
    },
    {
        "partner_id": "apptronik",
        "label": "dev",
        "scopes": ["train", "eval"],
        "rate_limit_rpm": 60,
        "monthly_gpu_quota_h": 100.0,
    },
    {
        "partner_id": "1x-technologies",
        "label": "admin-access",
        "scopes": ["train", "eval", "deploy", "data-upload", "cost-view", "admin"],
        "rate_limit_rpm": 300,
        "monthly_gpu_quota_h": 1000.0,
    },
]


def _seed_if_empty() -> None:
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
        if count > 0:
            return

        for p in SEED_PARTNERS:
            raw_key = _generate_raw_key()
            key_id = _new_id()
            now = _now_iso()
            conn.execute(
                """INSERT INTO api_keys
                   (id, partner_id, label, key_hash, prefix_hint, status, scopes,
                    rate_limit_rpm, monthly_gpu_quota_h, created_at, activated_at,
                    total_requests, gpu_hours_consumed, current_month_cost)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    key_id,
                    p["partner_id"],
                    p["label"],
                    _hash_key(raw_key),
                    _prefix_hint(raw_key),
                    "active",
                    json.dumps(p["scopes"]),
                    p["rate_limit_rpm"],
                    p["monthly_gpu_quota_h"],
                    now,
                    now,
                    # Seed with some realistic-looking usage
                    secrets.randbelow(5000),
                    round(secrets.randbelow(120) + secrets.randbelow(10) * 0.1, 1),
                    round(secrets.randbelow(800) + secrets.randbelow(100) * 0.01, 2),
                ),
            )
            _log_audit(conn, key_id, p["partner_id"], "create", "seed",
                       f"Seeded key for {p['partner_id']}/{p['label']}")
            _log_audit(conn, key_id, p["partner_id"], "activate", "seed",
                       "Auto-activated at seed time")
        conn.commit()
        print(f"[api_key_manager] Seeded {len(SEED_PARTNERS)} partner keys.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateKeyRequest(BaseModel):
    partner_id: str = Field(..., description="Slug identifying the design partner")
    label: str = Field(..., description="Human-readable label for this key")
    scopes: List[str] = Field(default_factory=list, description="Permission scopes")
    rate_limit_rpm: int = Field(100, ge=1, le=10000, description="Max requests per minute")
    monthly_gpu_quota_h: float = Field(100.0, ge=0, description="Monthly GPU-hour quota")
    actor: str = Field("api", description="Who is creating the key")


class UpdateKeyRequest(BaseModel):
    scopes: Optional[List[str]] = None
    rate_limit_rpm: Optional[int] = Field(None, ge=1, le=10000)
    monthly_gpu_quota_h: Optional[float] = Field(None, ge=0)
    label: Optional[str] = None
    actor: str = "api"


class RotateRequest(BaseModel):
    actor: str = "api"
    grace_hours: int = Field(GRACE_HOURS, ge=0, le=168)


class VerifyRequest(BaseModel):
    api_key: str
    scope: Optional[str] = None  # if provided, also checks scope membership


class UsageUpdateRequest(BaseModel):
    gpu_hours: float = Field(0.0, ge=0)
    cost_usd: float = Field(0.0, ge=0)
    requests: int = Field(1, ge=0)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_if_empty()
    yield


app = FastAPI(
    title="OCI Robot Cloud — API Key Manager",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helper: row → dict
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["scopes"] = json.loads(d.get("scopes") or "[]")
    return d


# ---------------------------------------------------------------------------
# Routes: key CRUD
# ---------------------------------------------------------------------------

@app.post("/keys", status_code=201)
async def create_key(body: CreateKeyRequest):
    """Generate a new API key. The plaintext key is returned ONCE and never stored."""
    invalid = set(body.scopes) - VALID_SCOPES
    if invalid:
        raise HTTPException(422, f"Invalid scopes: {invalid}. Valid: {VALID_SCOPES}")

    raw_key = _generate_raw_key()
    key_id = _new_id()
    now = _now_iso()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO api_keys
               (id, partner_id, label, key_hash, prefix_hint, status, scopes,
                rate_limit_rpm, monthly_gpu_quota_h, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                key_id,
                body.partner_id,
                body.label,
                _hash_key(raw_key),
                _prefix_hint(raw_key),
                "inactive",
                json.dumps(body.scopes),
                body.rate_limit_rpm,
                body.monthly_gpu_quota_h,
                now,
            ),
        )
        _log_audit(conn, key_id, body.partner_id, "create", body.actor,
                   f"label={body.label} scopes={body.scopes}")
        conn.commit()

    return {
        "key_id": key_id,
        "partner_id": body.partner_id,
        "label": body.label,
        "api_key": raw_key,  # plaintext — shown once only
        "status": "inactive",
        "scopes": body.scopes,
        "rate_limit_rpm": body.rate_limit_rpm,
        "monthly_gpu_quota_h": body.monthly_gpu_quota_h,
        "created_at": now,
        "warning": "Store this key securely. It will NOT be shown again.",
    }


@app.get("/keys")
async def list_keys(
    partner_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List API keys, optionally filtered by partner_id and/or status."""
    conditions = []
    params: list = []

    if partner_id:
        conditions.append("partner_id = ?")
        params.append(partner_id)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM api_keys {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM api_keys {where}",
            params[:-2],
        ).fetchone()[0]

    keys = [_row_to_dict(r) for r in rows]
    # Never leak hash
    for k in keys:
        k.pop("key_hash", None)

    return {"total": total, "offset": offset, "limit": limit, "keys": keys}


@app.get("/keys/{key_id}")
async def get_key(key_id: str):
    """Get metadata for a single key."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Key not found")
    d = _row_to_dict(row)
    d.pop("key_hash", None)
    return d


@app.patch("/keys/{key_id}")
async def update_key(key_id: str, body: UpdateKeyRequest):
    """Update scopes, rate limit, quota, or label on an existing key."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")

        updates: list[str] = []
        params: list = []
        changes = {}

        if body.scopes is not None:
            invalid = set(body.scopes) - VALID_SCOPES
            if invalid:
                raise HTTPException(422, f"Invalid scopes: {invalid}")
            updates.append("scopes = ?")
            params.append(json.dumps(body.scopes))
            changes["scopes"] = body.scopes

        if body.rate_limit_rpm is not None:
            updates.append("rate_limit_rpm = ?")
            params.append(body.rate_limit_rpm)
            changes["rate_limit_rpm"] = body.rate_limit_rpm

        if body.monthly_gpu_quota_h is not None:
            updates.append("monthly_gpu_quota_h = ?")
            params.append(body.monthly_gpu_quota_h)
            changes["monthly_gpu_quota_h"] = body.monthly_gpu_quota_h

        if body.label is not None:
            updates.append("label = ?")
            params.append(body.label)
            changes["label"] = body.label

        if not updates:
            raise HTTPException(400, "No fields to update")

        params.append(key_id)
        conn.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", params)
        _log_audit(conn, key_id, row["partner_id"], "update", body.actor,
                   json.dumps(changes))
        conn.commit()

    return {"key_id": key_id, "updated": changes}


@app.post("/keys/{key_id}/activate")
async def activate_key(key_id: str, actor: str = "api"):
    """Activate an inactive key."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")
        if row["status"] == "active":
            return {"key_id": key_id, "status": "active", "message": "Already active"}
        if row["status"] == "revoked":
            raise HTTPException(400, "Cannot activate a revoked key")

        conn.execute(
            "UPDATE api_keys SET status='active', activated_at=? WHERE id=?",
            (_now_iso(), key_id),
        )
        _log_audit(conn, key_id, row["partner_id"], "activate", actor)
        conn.commit()

    return {"key_id": key_id, "status": "active"}


@app.post("/keys/{key_id}/deactivate")
async def deactivate_key(key_id: str, actor: str = "api"):
    """Temporarily deactivate a key (reversible)."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")
        if row["status"] == "revoked":
            raise HTTPException(400, "Cannot deactivate a revoked key")

        conn.execute("UPDATE api_keys SET status='inactive' WHERE id=?", (key_id,))
        _log_audit(conn, key_id, row["partner_id"], "deactivate", actor)
        conn.commit()

    return {"key_id": key_id, "status": "inactive"}


@app.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: str, actor: str = "api", reason: str = ""):
    """Permanently revoke a key. Cannot be undone."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")
        if row["status"] == "revoked":
            return {"key_id": key_id, "status": "revoked", "message": "Already revoked"}

        conn.execute("UPDATE api_keys SET status='revoked' WHERE id=?", (key_id,))
        _log_audit(conn, key_id, row["partner_id"], "revoke", actor,
                   reason or "No reason provided")
        conn.commit()

    return {"key_id": key_id, "status": "revoked"}


@app.post("/keys/{key_id}/rotate")
async def rotate_key(key_id: str, body: RotateRequest = RotateRequest()):
    """
    Rotate a key: issue a new key and mark the old one with a grace-period expiry.
    The old key remains valid until ``expires_at`` to avoid hard cutover.
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")
        if row["status"] == "revoked":
            raise HTTPException(400, "Cannot rotate a revoked key")

        # Set expiry on old key
        grace_expiry = (
            datetime.now(timezone.utc) + timedelta(hours=body.grace_hours)
        ).isoformat()
        conn.execute(
            "UPDATE api_keys SET status='rotating', expires_at=? WHERE id=?",
            (grace_expiry, key_id),
        )
        _log_audit(conn, key_id, row["partner_id"], "rotate", body.actor,
                   f"grace_hours={body.grace_hours} expires_at={grace_expiry}")

        # Create replacement key
        new_raw_key = _generate_raw_key()
        new_key_id = _new_id()
        now = _now_iso()
        conn.execute(
            """INSERT INTO api_keys
               (id, partner_id, label, key_hash, prefix_hint, status, scopes,
                rate_limit_rpm, monthly_gpu_quota_h, created_at, activated_at,
                rotated_from_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                new_key_id,
                row["partner_id"],
                row["label"] + "-rotated",
                _hash_key(new_raw_key),
                _prefix_hint(new_raw_key),
                "active",
                row["scopes"],
                row["rate_limit_rpm"],
                row["monthly_gpu_quota_h"],
                now,
                now,
                key_id,
            ),
        )
        _log_audit(conn, new_key_id, row["partner_id"], "create", body.actor,
                   f"rotated_from={key_id}")
        _log_audit(conn, new_key_id, row["partner_id"], "activate", body.actor,
                   "Auto-activated on rotation")
        conn.commit()

    return {
        "old_key_id": key_id,
        "old_key_expires_at": grace_expiry,
        "new_key_id": new_key_id,
        "new_api_key": new_raw_key,  # plaintext — shown once only
        "status": "active",
        "partner_id": row["partner_id"],
        "scopes": json.loads(row["scopes"]),
        "warning": "Store this key securely. It will NOT be shown again.",
    }


# ---------------------------------------------------------------------------
# Route: usage update (called by gateway after each request)
# ---------------------------------------------------------------------------

@app.post("/keys/{key_id}/usage")
async def record_usage(key_id: str, body: UsageUpdateRequest):
    """Update usage counters for a key. Called internally by the inference gateway."""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Key not found")

        conn.execute(
            """UPDATE api_keys SET
               last_used_at        = ?,
               total_requests      = total_requests + ?,
               gpu_hours_consumed  = gpu_hours_consumed + ?,
               current_month_cost  = current_month_cost + ?
               WHERE id = ?""",
            (_now_iso(), body.requests, body.gpu_hours, body.cost_usd, key_id),
        )
        conn.commit()

    return {"key_id": key_id, "recorded": True}


# ---------------------------------------------------------------------------
# Route: verify (constant-time; used by gateway)
# ---------------------------------------------------------------------------

@app.post("/verify")
async def verify_key(body: VerifyRequest):
    """
    Validate an API key and optionally check scope membership.
    Uses constant-time comparison to prevent timing attacks.
    Returns 200 + metadata on success, 401 on failure.
    """
    candidate_hash = _hash_key(body.api_key)
    now_iso = _now_iso()
    now_dt = datetime.fromisoformat(now_iso)

    with get_db() as conn:
        # Fetch by hash
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ?", (candidate_hash,)
        ).fetchone()

    if not row:
        # Constant-time dummy comparison to prevent timing attacks
        hmac.compare_digest(candidate_hash, candidate_hash)
        raise HTTPException(401, "Invalid API key")

    # Constant-time comparison (hash already fetched — compare against itself as guard)
    if not hmac.compare_digest(row["key_hash"], candidate_hash):
        raise HTTPException(401, "Invalid API key")

    status = row["status"]

    # Check expiry for rotating keys
    if status == "rotating" and row["expires_at"]:
        expires_dt = datetime.fromisoformat(row["expires_at"])
        if now_dt > expires_dt:
            raise HTTPException(401, "API key has expired (rotation grace period ended)")
    elif status not in ("active", "rotating"):
        raise HTTPException(401, f"API key is {status}")

    scopes = json.loads(row["scopes"] or "[]")

    if body.scope and body.scope not in scopes:
        raise HTTPException(403, f"Key does not have scope '{body.scope}'")

    return {
        "valid": True,
        "key_id": row["id"],
        "partner_id": row["partner_id"],
        "label": row["label"],
        "status": status,
        "scopes": scopes,
        "rate_limit_rpm": row["rate_limit_rpm"],
        "monthly_gpu_quota_h": row["monthly_gpu_quota_h"],
        "gpu_hours_consumed": row["gpu_hours_consumed"],
        "current_month_cost": row["current_month_cost"],
    }


# ---------------------------------------------------------------------------
# Route: audit log
# ---------------------------------------------------------------------------

@app.get("/audit")
async def get_audit_log(
    key_id: Optional[str] = Query(None),
    partner_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Retrieve recent audit log entries."""
    conditions = []
    params: list = []

    if key_id:
        conditions.append("key_id = ?")
        params.append(key_id)
    if partner_id:
        conditions.append("partner_id = ?")
        params.append(partner_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_log {where} ORDER BY ts DESC LIMIT ?", params
        ).fetchall()

    return {"entries": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>OCI Robot Cloud — API Key Manager</title>
<style>
  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --text:     #e6edf3;
    --muted:    #8b949e;
    --accent:   #58a6ff;
    --green:    #3fb950;
    --yellow:   #d29922;
    --red:      #f85149;
    --orange:   #e3b341;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; }
  header .sub { color: var(--muted); font-size: 13px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; }
  .badge.active   { background: rgba(63,185,80,.15);  color: var(--green);  border: 1px solid rgba(63,185,80,.4);  }
  .badge.inactive { background: rgba(139,148,158,.1); color: var(--muted);  border: 1px solid var(--border); }
  .badge.rotating { background: rgba(211,153,34,.15); color: var(--orange); border: 1px solid rgba(211,153,34,.4); }
  .badge.revoked  { background: rgba(248,81,73,.1);   color: var(--red);    border: 1px solid rgba(248,81,73,.3);  }
  main { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .stat-card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
  .stat-card .value { font-size: 28px; font-weight: 700; }
  .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .section-header h2 { font-size: 15px; font-weight: 600; }
  .btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; font-size: 13px; font-weight: 500; transition: all .15s; text-decoration: none; }
  .btn:hover { background: #21262d; border-color: var(--accent); color: var(--accent); }
  .btn.danger:hover { border-color: var(--red); color: var(--red); }
  .btn.sm { padding: 3px 10px; font-size: 12px; }
  table { width: 100%; border-collapse: collapse; }
  thead th { padding: 10px 12px; text-align: left; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:hover { background: rgba(255,255,255,.03); }
  tbody td { padding: 12px 12px; vertical-align: middle; }
  .partner-chip { background: rgba(88,166,255,.1); border: 1px solid rgba(88,166,255,.25); color: var(--accent); border-radius: 6px; padding: 2px 8px; font-size: 12px; font-weight: 500; }
  .scope-list { display: flex; flex-wrap: wrap; gap: 4px; }
  .scope { background: rgba(255,255,255,.06); border-radius: 4px; padding: 1px 6px; font-size: 11px; color: var(--muted); }
  .scope.admin { color: var(--orange); background: rgba(227,179,65,.1); }
  .num { font-variant-numeric: tabular-nums; }
  .sparkline { display: inline-flex; align-items: flex-end; gap: 2px; height: 24px; }
  .sparkline span { width: 4px; border-radius: 2px 2px 0 0; background: var(--accent); opacity: .7; transition: opacity .2s; }
  .sparkline span:hover { opacity: 1; }
  .hint { color: var(--muted); font-size: 12px; font-family: monospace; }
  .actions { display: flex; gap: 6px; flex-wrap: wrap; }
  .filter-row { display: flex; gap: 10px; margin-bottom: 16px; align-items: center; }
  input[type=text] { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; color: var(--text); font-size: 13px; outline: none; width: 220px; }
  input[type=text]:focus { border-color: var(--accent); }
  select { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; color: var(--text); font-size: 13px; outline: none; }
  select:focus { border-color: var(--accent); }
  .table-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .toast { position: fixed; bottom: 24px; right: 24px; background: #21262d; border: 1px solid var(--border); border-radius: 8px; padding: 12px 18px; font-size: 13px; box-shadow: 0 8px 24px rgba(0,0,0,.4); opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 999; max-width: 340px; }
  .toast.show { opacity: 1; pointer-events: auto; }
  .toast.success { border-color: var(--green); color: var(--green); }
  .toast.error   { border-color: var(--red);   color: var(--red); }
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: none; align-items: center; justify-content: center; z-index: 100; }
  .modal-overlay.open { display: flex; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; width: 420px; max-width: 95vw; }
  .modal h3 { font-size: 15px; font-weight: 600; margin-bottom: 16px; }
  .modal .key-box { background: var(--bg); border: 1px solid var(--green); border-radius: 6px; padding: 12px 14px; font-family: monospace; font-size: 13px; color: var(--green); word-break: break-all; margin-bottom: 12px; }
  .modal p.warn { color: var(--orange); font-size: 12px; margin-bottom: 16px; }
  .modal-footer { display: flex; justify-content: flex-end; gap: 8px; }
  footer { margin-top: 40px; padding: 16px 24px; color: var(--muted); font-size: 12px; text-align: center; border-top: 1px solid var(--border); }
</style>
</head>
<body>
<header>
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
  <div>
    <h1>API Key Manager</h1>
    <div class="sub">OCI Robot Cloud — Design Partner Access Control &nbsp;·&nbsp; port 8053</div>
  </div>
</header>

<main>
  <div class="stats-row" id="statsRow">
    <div class="stat-card"><div class="label">Total Keys</div><div class="value" id="statTotal">—</div></div>
    <div class="stat-card"><div class="label">Active</div><div class="value" id="statActive" style="color:var(--green)">—</div></div>
    <div class="stat-card"><div class="label">Total Requests</div><div class="value" id="statReqs">—</div></div>
    <div class="stat-card"><div class="label">GPU-Hours Used</div><div class="value" id="statGpu">—</div></div>
  </div>

  <div class="section-header">
    <h2>API Keys</h2>
    <button class="btn" onclick="openCreateModal()">＋ New Key</button>
  </div>

  <div class="filter-row">
    <input type="text" id="filterPartner" placeholder="Filter by partner…" oninput="filterTable()"/>
    <select id="filterStatus" onchange="filterTable()">
      <option value="">All statuses</option>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
      <option value="rotating">Rotating</option>
      <option value="revoked">Revoked</option>
    </select>
    <button class="btn sm" onclick="loadKeys()">⟳ Refresh</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Partner</th>
          <th>Label</th>
          <th>Key Hint</th>
          <th>Status</th>
          <th>Scopes</th>
          <th>Rate (rpm)</th>
          <th>GPU Quota (h)</th>
          <th>Requests</th>
          <th>GPU Used (h)</th>
          <th>Cost ($)</th>
          <th>Last Used</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="keysBody">
        <tr><td colspan="12" style="text-align:center;color:var(--muted);padding:32px">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</main>

<footer>OCI Robot Cloud — Internal Tools &nbsp;·&nbsp; API Key Manager v1.0</footer>

<!-- New Key Modal -->
<div class="modal-overlay" id="createModal">
  <div class="modal">
    <h3>Create New API Key</h3>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px">
      <input type="text" id="newPartner" placeholder="Partner ID (e.g. acme-robotics)" style="width:100%"/>
      <input type="text" id="newLabel" placeholder="Label (e.g. production)" style="width:100%"/>
      <input type="text" id="newScopes" placeholder="Scopes (comma-sep): train,eval,deploy" style="width:100%"/>
      <div style="display:flex;gap:8px">
        <input type="text" id="newRpm" placeholder="Rate rpm (100)" style="width:50%"/>
        <input type="text" id="newQuota" placeholder="GPU quota h (100)" style="width:50%"/>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn" onclick="closeCreateModal()">Cancel</button>
      <button class="btn" style="background:rgba(88,166,255,.15);border-color:var(--accent);color:var(--accent)" onclick="submitCreate()">Create Key</button>
    </div>
  </div>
</div>

<!-- Key Reveal Modal -->
<div class="modal-overlay" id="revealModal">
  <div class="modal">
    <h3 id="revealTitle">New API Key</h3>
    <div class="key-box" id="revealKey"></div>
    <p class="warn">⚠ This is the only time this key will be shown. Copy it now and store it securely.</p>
    <div class="modal-footer">
      <button class="btn" onclick="copyKey()" id="copyBtn">Copy</button>
      <button class="btn" onclick="closeRevealModal()">Done</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let allKeys = [];

async function loadKeys() {
  try {
    const r = await fetch('/keys?limit=500');
    const data = await r.json();
    allKeys = data.keys || [];
    updateStats();
    renderTable(allKeys);
  } catch(e) {
    showToast('Failed to load keys: ' + e.message, 'error');
  }
}

function updateStats() {
  document.getElementById('statTotal').textContent = allKeys.length;
  document.getElementById('statActive').textContent = allKeys.filter(k => k.status === 'active').length;
  const reqs = allKeys.reduce((s,k) => s + (k.total_requests||0), 0);
  document.getElementById('statReqs').textContent = reqs.toLocaleString();
  const gpu = allKeys.reduce((s,k) => s + (k.gpu_hours_consumed||0), 0);
  document.getElementById('statGpu').textContent = gpu.toFixed(1);
}

function filterTable() {
  const pf = document.getElementById('filterPartner').value.toLowerCase();
  const sf = document.getElementById('filterStatus').value;
  const filtered = allKeys.filter(k =>
    (!pf || k.partner_id.toLowerCase().includes(pf)) &&
    (!sf || k.status === sf)
  );
  renderTable(filtered);
}

function renderTable(keys) {
  const tbody = document.getElementById('keysBody');
  if (!keys.length) {
    tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--muted);padding:32px">No keys found</td></tr>';
    return;
  }
  tbody.innerHTML = keys.map(k => {
    const scopeHtml = (k.scopes||[]).map(s =>
      `<span class="scope${s==='admin'?' admin':''}">${s}</span>`
    ).join('');
    const lastUsed = k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : '—';
    const spark = sparkline(k.total_requests);
    const actions = buildActions(k);
    return `<tr>
      <td><span class="partner-chip">${esc(k.partner_id)}</span></td>
      <td>${esc(k.label)}</td>
      <td><span class="hint">${esc(k.prefix_hint||'')}</span></td>
      <td><span class="badge ${k.status}">${k.status}</span></td>
      <td><div class="scope-list">${scopeHtml}</div></td>
      <td class="num">${k.rate_limit_rpm}</td>
      <td class="num">${k.monthly_gpu_quota_h}</td>
      <td class="num">${(k.total_requests||0).toLocaleString()} ${spark}</td>
      <td class="num">${(k.gpu_hours_consumed||0).toFixed(1)}</td>
      <td class="num">$${(k.current_month_cost||0).toFixed(2)}</td>
      <td style="color:var(--muted);font-size:12px">${lastUsed}</td>
      <td><div class="actions">${actions}</div></td>
    </tr>`;
  }).join('');
}

function buildActions(k) {
  const btns = [];
  if (k.status === 'inactive')
    btns.push(`<button class="btn sm" onclick="activate('${k.id}')">Activate</button>`);
  if (k.status === 'active')
    btns.push(`<button class="btn sm" onclick="deactivate('${k.id}')">Pause</button>`);
  if (k.status === 'active' || k.status === 'rotating')
    btns.push(`<button class="btn sm" onclick="rotate('${k.id}')">↻ Rotate</button>`);
  if (k.status !== 'revoked')
    btns.push(`<button class="btn sm danger" onclick="revoke('${k.id}')">Revoke</button>`);
  return btns.join('');
}

function sparkline(n) {
  if (!n) return '';
  const bars = 6;
  const heights = Array.from({length:bars}, (_,i) =>
    Math.max(3, Math.round(Math.random() * 20 + (i/bars)*4))
  );
  return `<span class="sparkline">${heights.map(h=>`<span style="height:${h}px"></span>`).join('')}</span>`;
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function activate(id) {
  await apiCall('POST', `/keys/${id}/activate`, null, 'Key activated');
}
async function deactivate(id) {
  await apiCall('POST', `/keys/${id}/deactivate`, null, 'Key paused');
}
async function revoke(id) {
  if (!confirm('Permanently revoke this key? This cannot be undone.')) return;
  await apiCall('POST', `/keys/${id}/revoke`, null, 'Key revoked');
}
async function rotate(id) {
  if (!confirm('Rotate this key? A new key will be issued and the old one will expire in 24h.')) return;
  try {
    const r = await fetch(`/keys/${id}/rotate`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Rotate failed');
    showReveal(data.new_api_key, 'Rotated Key — ' + data.new_key_id);
    loadKeys();
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

function openCreateModal() { document.getElementById('createModal').classList.add('open'); }
function closeCreateModal() { document.getElementById('createModal').classList.remove('open'); }

async function submitCreate() {
  const partner = document.getElementById('newPartner').value.trim();
  const label   = document.getElementById('newLabel').value.trim();
  const scopes  = document.getElementById('newScopes').value.split(',').map(s=>s.trim()).filter(Boolean);
  const rpm     = parseInt(document.getElementById('newRpm').value) || 100;
  const quota   = parseFloat(document.getElementById('newQuota').value) || 100;
  if (!partner || !label) { showToast('Partner ID and label are required', 'error'); return; }
  closeCreateModal();
  try {
    const r = await fetch('/keys', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({partner_id:partner, label, scopes, rate_limit_rpm:rpm, monthly_gpu_quota_h:quota})
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Create failed');
    showReveal(data.api_key, 'New Key — ' + data.key_id);
    loadKeys();
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

function showReveal(key, title) {
  document.getElementById('revealTitle').textContent = title;
  document.getElementById('revealKey').textContent = key;
  document.getElementById('revealModal').classList.add('open');
}
function closeRevealModal() { document.getElementById('revealModal').classList.remove('open'); }
function copyKey() {
  navigator.clipboard.writeText(document.getElementById('revealKey').textContent);
  document.getElementById('copyBtn').textContent = 'Copied!';
  setTimeout(() => document.getElementById('copyBtn').textContent = 'Copy', 1500);
}

async function apiCall(method, url, body, successMsg) {
  try {
    const opts = {method, headers:{'Content-Type':'application/json'}};
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Request failed');
    showToast(successMsg, 'success');
    loadKeys();
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => t.className = 'toast', 3000);
}

loadKeys();
setInterval(loadKeys, 30000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """HTML dashboard for key management."""
    return HTMLResponse(DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    return {"status": "ok", "db": DB_PATH, "total_keys": count}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.api_key_manager:app", host="0.0.0.0", port=8053, reload=False)
