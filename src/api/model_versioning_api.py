"""
Model Versioning API — Production-grade FastAPI service (port 8051).

Extends src/training/policy_version_registry.py (JSON-backed) with a full
REST API + interactive HTML dashboard backed by SQLite.

Usage:
    # Start server (auto-seeds DB on first run):
    python src/api/model_versioning_api.py

    # Or via uvicorn:
    uvicorn src.api.model_versioning_api:app --port 8051 --reload

Endpoints:
    GET  /                          — HTML dashboard (lineage DAG + metrics table)
    GET  /versions                  — List all versions (optional ?stage=draft|staging|production|archived)
    POST /versions                  — Create a new version
    GET  /versions/production       — Current production pointer
    GET  /versions/compare?a=v1&b=v2 — Metric delta table
    GET  /versions/{id}             — Get a single version
    PATCH /versions/{id}            — Update mutable fields (notes, tags, metrics)
    DELETE /versions/{id}           — Soft-delete (sets stage=archived)
    POST /versions/{id}/promote     — Promote stage with approver + reason (audit logged)
    GET  /audit                     — Full audit trail (JSON)
    GET  /health                    — Liveness check

Stage transitions (one-way only):
    draft → staging → production → archived
    Any stage can be sent to archived directly.

Dependencies:
    pip install fastapi uvicorn

SQLite DB: /tmp/model_versioning.db
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import textwrap
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = "/tmp/model_versioning.db"
PORT = 8051

STAGE_ORDER = ["draft", "staging", "production", "archived"]

STAGE_COLORS = {
    "draft":      "#6B7280",
    "staging":    "#D97706",
    "production": "#059669",
    "archived":   "#374151",
}

STAGE_TEXT_COLORS = {
    "draft":      "#E5E7EB",
    "staging":    "#FEF3C7",
    "production": "#D1FAE5",
    "archived":   "#9CA3AF",
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class VersionCreate(BaseModel):
    version_id: str = Field(..., description="Unique identifier, e.g. 'bc_500demo'")
    checkpoint_path: str
    training_method: str = Field(..., description="BC | DAgger | DAgger+Curriculum | Transfer")
    parent_version_id: Optional[str] = None
    n_demos: int = 0
    n_steps: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    mae: float = 0.0
    training_cost_usd: float = 0.0
    notes: str = ""
    tags: List[str] = Field(default_factory=list)


class VersionUpdate(BaseModel):
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    success_rate: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    mae: Optional[float] = None
    training_cost_usd: Optional[float] = None
    checkpoint_path: Optional[str] = None


class PromoteRequest(BaseModel):
    target_stage: str = Field(..., description="Target stage: staging | production | archived")
    approver: str = Field(..., description="Name or user ID of approver")
    reason: str = Field(..., description="Reason for promotion / approval notes")


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str = DB_PATH) -> None:
    with _db(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS versions (
                version_id        TEXT PRIMARY KEY,
                checkpoint_path   TEXT NOT NULL,
                training_method   TEXT NOT NULL,
                parent_version_id TEXT,
                n_demos           INTEGER DEFAULT 0,
                n_steps           INTEGER DEFAULT 0,
                success_rate      REAL DEFAULT 0.0,
                avg_latency_ms    REAL DEFAULT 0.0,
                mae               REAL DEFAULT 0.0,
                training_cost_usd REAL DEFAULT 0.0,
                stage             TEXT NOT NULL DEFAULT 'draft',
                deleted           INTEGER DEFAULT 0,
                notes             TEXT DEFAULT '',
                tags              TEXT DEFAULT '[]',
                created_at        TEXT NOT NULL,
                promoted_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                version_id  TEXT NOT NULL,
                action      TEXT NOT NULL,
                from_stage  TEXT,
                to_stage    TEXT,
                actor       TEXT,
                reason      TEXT
            );
        """)


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["deleted"] = bool(d.get("deleted", 0))
    return d


def db_get_version(version_id: str, path: str = DB_PATH) -> dict:
    with _db(path) as conn:
        row = conn.execute(
            "SELECT * FROM versions WHERE version_id = ? AND deleted = 0",
            (version_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return _row_to_dict(row)


def db_list_versions(stage: Optional[str] = None, path: str = DB_PATH) -> List[dict]:
    with _db(path) as conn:
        if stage:
            rows = conn.execute(
                "SELECT * FROM versions WHERE deleted = 0 AND stage = ? ORDER BY created_at",
                (stage,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM versions WHERE deleted = 0 ORDER BY created_at"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def db_create_version(v: VersionCreate, path: str = DB_PATH) -> dict:
    # Check for duplicate
    with _db(path) as conn:
        existing = conn.execute(
            "SELECT version_id FROM versions WHERE version_id = ?",
            (v.version_id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Version '{v.version_id}' already exists")

        # Validate parent exists if provided
        if v.parent_version_id:
            parent = conn.execute(
                "SELECT version_id FROM versions WHERE version_id = ? AND deleted = 0",
                (v.parent_version_id,)
            ).fetchone()
            if not parent:
                raise HTTPException(
                    status_code=404,
                    detail=f"Parent version '{v.parent_version_id}' not found"
                )

        now = _now_iso()
        conn.execute("""
            INSERT INTO versions (
                version_id, checkpoint_path, training_method, parent_version_id,
                n_demos, n_steps, success_rate, avg_latency_ms, mae,
                training_cost_usd, stage, notes, tags, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            v.version_id, v.checkpoint_path, v.training_method, v.parent_version_id,
            v.n_demos, v.n_steps, v.success_rate, v.avg_latency_ms, v.mae,
            v.training_cost_usd, "draft", v.notes,
            json.dumps(v.tags), now
        ))
        conn.execute("""
            INSERT INTO audit_log (timestamp, version_id, action, from_stage, to_stage, actor, reason)
            VALUES (?, ?, 'created', NULL, 'draft', 'system', 'Version registered')
        """, (now, v.version_id))

    return db_get_version(v.version_id, path)


def db_update_version(version_id: str, upd: VersionUpdate, path: str = DB_PATH) -> dict:
    current = db_get_version(version_id, path)
    fields = []
    values = []
    if upd.notes is not None:
        fields.append("notes = ?"); values.append(upd.notes)
    if upd.tags is not None:
        fields.append("tags = ?"); values.append(json.dumps(upd.tags))
    if upd.success_rate is not None:
        fields.append("success_rate = ?"); values.append(upd.success_rate)
    if upd.avg_latency_ms is not None:
        fields.append("avg_latency_ms = ?"); values.append(upd.avg_latency_ms)
    if upd.mae is not None:
        fields.append("mae = ?"); values.append(upd.mae)
    if upd.training_cost_usd is not None:
        fields.append("training_cost_usd = ?"); values.append(upd.training_cost_usd)
    if upd.checkpoint_path is not None:
        fields.append("checkpoint_path = ?"); values.append(upd.checkpoint_path)
    if not fields:
        return current
    values.append(version_id)
    with _db(path) as conn:
        conn.execute(f"UPDATE versions SET {', '.join(fields)} WHERE version_id = ?", values)
        conn.execute("""
            INSERT INTO audit_log (timestamp, version_id, action, actor, reason)
            VALUES (?, ?, 'updated', 'system', 'Fields updated via API')
        """, (_now_iso(), version_id))
    return db_get_version(version_id, path)


def db_soft_delete(version_id: str, path: str = DB_PATH) -> dict:
    v = db_get_version(version_id, path)
    with _db(path) as conn:
        conn.execute(
            "UPDATE versions SET deleted = 1, stage = 'archived' WHERE version_id = ?",
            (version_id,)
        )
        conn.execute("""
            INSERT INTO audit_log (timestamp, version_id, action, from_stage, to_stage, actor, reason)
            VALUES (?, ?, 'deleted', ?, 'archived', 'system', 'Soft-deleted via API')
        """, (_now_iso(), version_id, v["stage"]))
    return {"deleted": True, "version_id": version_id}


def db_promote(version_id: str, req: PromoteRequest, path: str = DB_PATH) -> dict:
    v = db_get_version(version_id, path)
    from_stage = v["stage"]
    to_stage = req.target_stage

    if to_stage not in STAGE_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage '{to_stage}'. Must be one of {STAGE_ORDER}"
        )

    # One-way promotion enforcement (except archived which is always allowed)
    if to_stage != "archived":
        from_idx = STAGE_ORDER.index(from_stage)
        to_idx = STAGE_ORDER.index(to_stage)
        if to_idx <= from_idx:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot move '{version_id}' from '{from_stage}' back to '{to_stage}'. "
                       f"Stage transitions are one-way: {' → '.join(STAGE_ORDER)}"
            )

    now = _now_iso()

    with _db(path) as conn:
        # If promoting to production, archive the existing production version
        if to_stage == "production":
            conn.execute("""
                UPDATE versions SET stage = 'archived', promoted_at = ?
                WHERE stage = 'production' AND version_id != ? AND deleted = 0
            """, (now, version_id))
            # Audit the demotion
            old_prod = conn.execute(
                "SELECT version_id FROM versions WHERE stage = 'archived' AND version_id != ? "
                "ORDER BY promoted_at DESC LIMIT 1",
                (version_id,)
            ).fetchone()
            if old_prod:
                conn.execute("""
                    INSERT INTO audit_log (timestamp, version_id, action, from_stage, to_stage, actor, reason)
                    VALUES (?, ?, 'auto-archived', 'production', 'archived', 'system',
                            'Auto-archived: new production version promoted')
                """, (now, old_prod["version_id"]))

        conn.execute("""
            UPDATE versions SET stage = ?, promoted_at = ? WHERE version_id = ?
        """, (to_stage, now, version_id))

        conn.execute("""
            INSERT INTO audit_log (timestamp, version_id, action, from_stage, to_stage, actor, reason)
            VALUES (?, ?, 'promoted', ?, ?, ?, ?)
        """, (now, version_id, from_stage, to_stage, req.approver, req.reason))

    return db_get_version(version_id, path)


def db_production_version(path: str = DB_PATH) -> Optional[dict]:
    with _db(path) as conn:
        row = conn.execute(
            "SELECT * FROM versions WHERE stage = 'production' AND deleted = 0 LIMIT 1"
        ).fetchone()
    return _row_to_dict(row) if row else None


def db_compare(v1_id: str, v2_id: str, path: str = DB_PATH) -> dict:
    v1 = db_get_version(v1_id, path)
    v2 = db_get_version(v2_id, path)

    def delta(a, b):
        if a is None or b is None:
            return None
        return round(b - a, 6)

    def pct(a, b):
        if not a:
            return None
        return round((b - a) / abs(a) * 100, 2)

    metrics = ["success_rate", "avg_latency_ms", "mae", "training_cost_usd", "n_demos", "n_steps"]
    comparison = {}
    for m in metrics:
        a, b = v1.get(m, 0), v2.get(m, 0)
        comparison[m] = {
            "v1": a,
            "v2": b,
            "delta": delta(a, b),
            "pct_change": pct(a, b),
        }
    return {
        "v1": v1_id,
        "v2": v2_id,
        "v1_stage": v1["stage"],
        "v2_stage": v2["stage"],
        "metrics": comparison,
    }


def db_audit_log(path: str = DB_PATH, limit: int = 200) -> List[dict]:
    with _db(path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Seed data (mirrors policy_version_registry.py SEED_VERSIONS)
# ---------------------------------------------------------------------------


SEED_VERSIONS = [
    VersionCreate(
        version_id="bc_500demo",
        checkpoint_path="/tmp/checkpoints/bc_500demo/checkpoint-2000",
        training_method="BC",
        parent_version_id=None,
        n_demos=500, n_steps=2000,
        success_rate=0.05, avg_latency_ms=226.0, mae=0.103, training_cost_usd=0.86,
        notes="Initial BC baseline on 500 IK-planned demos. Low success, no fine-tuning.",
        tags=["baseline", "bc", "ik-sdg"],
    ),
    VersionCreate(
        version_id="bc_1000demo",
        checkpoint_path="/tmp/checkpoints/bc_1000demo/checkpoint-2000",
        training_method="BC",
        parent_version_id="bc_500demo",
        n_demos=1000, n_steps=2000,
        success_rate=0.10, avg_latency_ms=224.0, mae=0.073, training_cost_usd=1.72,
        notes="Doubled demo count. MAE improved 29%, success 2x. Promoted to staging then archived.",
        tags=["bc", "ik-sdg", "1k-demos"],
    ),
    VersionCreate(
        version_id="dagger_run4_iter1",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter1/checkpoint-5000",
        training_method="DAgger",
        parent_version_id="bc_1000demo",
        n_demos=1000, n_steps=5000,
        success_rate=0.20, avg_latency_ms=227.0, mae=0.051, training_cost_usd=2.15,
        notes="First DAgger iteration. Closed-loop corrections on bc_1000demo. 4x success vs BC baseline.",
        tags=["dagger", "run4", "iter1"],
    ),
    VersionCreate(
        version_id="dagger_run4_iter3",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter3/checkpoint-5000",
        training_method="DAgger",
        parent_version_id="dagger_run4_iter1",
        n_demos=1000, n_steps=5000,
        success_rate=0.45, avg_latency_ms=231.0, mae=0.031, training_cost_usd=4.30,
        notes="Production release. 3 DAgger iterations, 9x success over BC baseline. Stable latency.",
        tags=["dagger", "run4", "iter3", "production"],
    ),
    VersionCreate(
        version_id="dagger_run5",
        checkpoint_path="/tmp/checkpoints/dagger_run5/checkpoint-5000",
        training_method="DAgger",
        parent_version_id="dagger_run4_iter3",
        n_demos=1000, n_steps=5000,
        success_rate=0.05, avg_latency_ms=226.0, mae=0.099, training_cost_usd=4.30,
        notes=(
            "DAgger run5: 3 bugfixes (chunk_step reset, cube_z sanity, --checkpoint flag). "
            "Low eval success (1/20) due to insufficient correction episodes (99 vs 1000 BC). "
            "Needs longer DAgger rollout before production promotion."
        ),
        tags=["dagger", "run5", "bugfix"],
    ),
    VersionCreate(
        version_id="dagger_run6_projected",
        checkpoint_path="/tmp/checkpoints/dagger_run6/checkpoint-10000",
        training_method="DAgger+Curriculum",
        parent_version_id="dagger_run5",
        n_demos=2000, n_steps=10000,
        success_rate=0.70, avg_latency_ms=228.0, mae=0.018, training_cost_usd=8.60,
        notes="Projected: curriculum SDG (easy→hard) + 2000 demos + 10k steps. Target 70% success.",
        tags=["dagger", "curriculum", "run6", "projected"],
    ),
]

# Staged promotions for seed data
SEED_PROMOTIONS: List[tuple] = [
    # (version_id, stage, approver, reason, promoted_at_override)
    ("bc_500demo",       "staging",    "jun.qian", "Initial staging validation", "2026-01-11T10:00:00+00:00"),
    ("bc_500demo",       "archived",   "jun.qian", "Superseded by bc_1000demo",  "2026-01-18T08:00:00+00:00"),
    ("bc_1000demo",      "staging",    "jun.qian", "Improved MAE 29%, success 2x", "2026-01-19T09:00:00+00:00"),
    ("bc_1000demo",      "archived",   "jun.qian", "DAgger run4 ready",          "2026-02-01T08:00:00+00:00"),
    ("dagger_run4_iter1","staging",    "jun.qian", "DAgger iter1 validation OK", "2026-02-02T14:00:00+00:00"),
    ("dagger_run4_iter1","archived",   "jun.qian", "iter3 is strictly better",   "2026-02-14T11:00:00+00:00"),
    ("dagger_run4_iter3","staging",    "jun.qian", "3 DAgger iters, 45% success","2026-02-15T09:00:00+00:00"),
    ("dagger_run4_iter3","production", "jun.qian", "Approved for production: best policy to date", "2026-02-16T09:00:00+00:00"),
    ("dagger_run5",      "staging",    "jun.qian", "Bugfixes applied, staging for extended eval", "2026-03-15T11:00:00+00:00"),
]


def seed_db(path: str = DB_PATH) -> None:
    """Populate DB with training history seed data."""
    with _db(path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
    if count > 0:
        return  # Already seeded

    # Insert versions in order (parents first)
    for v in SEED_VERSIONS:
        db_create_version(v, path)

    # Apply stage promotions with overridden timestamps
    for version_id, stage, approver, reason, ts in SEED_PROMOTIONS:
        v = db_get_version(version_id, path)
        from_stage = v["stage"]

        with _db(path) as conn:
            if stage == "production":
                conn.execute("""
                    UPDATE versions SET stage = 'archived', promoted_at = ?
                    WHERE stage = 'production' AND version_id != ? AND deleted = 0
                """, (ts, version_id))

            conn.execute(
                "UPDATE versions SET stage = ?, promoted_at = ? WHERE version_id = ?",
                (stage, ts, version_id)
            )
            conn.execute("""
                INSERT INTO audit_log (timestamp, version_id, action, from_stage, to_stage, actor, reason)
                VALUES (?, ?, 'promoted', ?, ?, ?, ?)
            """, (ts, version_id, from_stage, stage, approver, reason))

    print(f"[model_versioning_api] Seeded {len(SEED_VERSIONS)} versions into {path}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud — Model Version Management API",
    description=__doc__,
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_db()
    seed_db()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "model_versioning_api", "port": PORT}


@app.get("/versions", response_class=JSONResponse)
def list_versions(stage: Optional[str] = Query(None, description="Filter by stage")):
    if stage and stage not in STAGE_ORDER:
        raise HTTPException(400, f"Invalid stage. Choose from {STAGE_ORDER}")
    return db_list_versions(stage)


@app.post("/versions", status_code=201)
def create_version(body: VersionCreate):
    return db_create_version(body)


@app.get("/versions/production")
def get_production():
    v = db_production_version()
    if not v:
        raise HTTPException(404, "No production version currently set")
    return v


@app.get("/versions/compare")
def compare_versions(
    a: str = Query(..., description="First version ID"),
    b: str = Query(..., description="Second version ID"),
):
    return db_compare(a, b)


@app.get("/versions/{version_id}")
def get_version(version_id: str):
    return db_get_version(version_id)


@app.patch("/versions/{version_id}")
def update_version(version_id: str, body: VersionUpdate):
    return db_update_version(version_id, body)


@app.delete("/versions/{version_id}")
def delete_version(version_id: str):
    return db_soft_delete(version_id)


@app.post("/versions/{version_id}/promote")
def promote_version(version_id: str, body: PromoteRequest):
    return db_promote(version_id, body)


@app.get("/audit")
def get_audit(limit: int = Query(100, ge=1, le=1000)):
    return db_audit_log(limit=limit)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------


def _stage_badge(stage: str) -> str:
    bg = STAGE_COLORS.get(stage, "#6B7280")
    return (
        f'<span style="background:{bg};color:#fff;padding:2px 10px;border-radius:12px;'
        f'font-size:0.75em;font-weight:700;letter-spacing:0.05em;">'
        f'{stage.upper()}</span>'
    )


def _promote_buttons(v: dict) -> str:
    """Render inline promote form buttons for a version row."""
    stage = v["stage"]
    vid = v["version_id"]
    if stage == "archived":
        return '<span style="color:#4B5563;font-size:0.8em">archived</span>'

    buttons = []
    stage_idx = STAGE_ORDER.index(stage)
    next_stages = STAGE_ORDER[stage_idx + 1:]

    for ns in next_stages:
        bg = STAGE_COLORS.get(ns, "#6B7280")
        js = (
            f"promoteVersion('{vid}', '{ns}')"
        )
        buttons.append(
            f'<button onclick="{js}" style="background:{bg};color:#fff;border:none;'
            f'padding:3px 10px;border-radius:6px;cursor:pointer;font-size:0.78em;'
            f'margin:1px;font-family:inherit;">'
            f'→ {ns}</button>'
        )
    return " ".join(buttons)


def _build_svg_dag(versions: List[dict]) -> str:
    """Build an SVG DAG of version lineage. Left-to-right layout."""
    if not versions:
        return "<svg width='600' height='60'><text x='20' y='30' fill='#6B7280'>No versions.</text></svg>"

    # Build adjacency: parent_version_id → [children]
    by_id: Dict[str, dict] = {v["version_id"]: v for v in versions}
    children: Dict[Optional[str], List[str]] = {}
    for v in versions:
        pid = v.get("parent_version_id")
        children.setdefault(pid, []).append(v["version_id"])

    # Topological layout: assign (col, row) to each node
    positions: Dict[str, tuple] = {}  # version_id → (col, row)
    col_row_counts: Dict[int, int] = {}

    def assign(vid: str, col: int) -> None:
        if vid in positions:
            return
        row = col_row_counts.get(col, 0)
        positions[vid] = (col, row)
        col_row_counts[col] = row + 1
        for child in children.get(vid, []):
            assign(child, col + 1)

    roots = children.get(None, [])
    for root in roots:
        assign(root, 0)

    # Fallback: any unpositioned nodes
    for v in versions:
        if v["version_id"] not in positions:
            col = 0
            row = col_row_counts.get(col, 0)
            positions[v["version_id"]] = (col, row)
            col_row_counts[col] = row + 1

    NODE_W, NODE_H = 160, 48
    H_GAP, V_GAP = 60, 20
    PAD_X, PAD_Y = 20, 20

    max_col = max(c for c, _ in positions.values()) if positions else 0
    max_row = max(r for _, r in positions.values()) if positions else 0

    svg_w = PAD_X * 2 + (max_col + 1) * NODE_W + max_col * H_GAP
    svg_h = PAD_Y * 2 + (max_row + 1) * NODE_H + max_row * V_GAP

    def node_center(vid: str) -> tuple:
        col, row = positions[vid]
        x = PAD_X + col * (NODE_W + H_GAP) + NODE_W // 2
        y = PAD_Y + row * (NODE_H + V_GAP) + NODE_H // 2
        return x, y

    def node_rect(vid: str) -> tuple:
        cx, cy = node_center(vid)
        return cx - NODE_W // 2, cy - NODE_H // 2

    lines = [
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#111827;border-radius:8px;">'
    ]

    # Draw edges first (behind nodes)
    for v in versions:
        vid = v["version_id"]
        pid = v.get("parent_version_id")
        if pid and pid in positions:
            px, py = node_center(pid)
            cx, cy = node_center(vid)
            # Edge from right of parent to left of child
            px_out = px + NODE_W // 2
            cx_in = cx - NODE_W // 2
            mid_x = (px_out + cx_in) // 2
            lines.append(
                f'<path d="M {px_out} {py} C {mid_x} {py}, {mid_x} {cy}, {cx_in} {cy}" '
                f'stroke="#4B5563" stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
            )

    # Arrow marker def
    lines.insert(1, textwrap.dedent("""\
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#4B5563"/>
          </marker>
        </defs>"""))

    # Draw nodes
    for v in versions:
        vid = v["version_id"]
        stage = v["stage"]
        rx, ry = node_rect(vid)
        bg = STAGE_COLORS.get(stage, "#374151")
        sr_pct = f"{v['success_rate']:.0%}"
        label = vid if len(vid) <= 18 else vid[:16] + "…"

        lines.append(
            f'<rect x="{rx}" y="{ry}" width="{NODE_W}" height="{NODE_H}" '
            f'rx="6" fill="{bg}" opacity="0.85" stroke="#6B7280" stroke-width="1"/>'
        )
        # Version ID
        lines.append(
            f'<text x="{rx + NODE_W//2}" y="{ry + 16}" text-anchor="middle" '
            f'font-family="Menlo,monospace" font-size="10" font-weight="600" fill="#F9FAFB">'
            f'{label}</text>'
        )
        # Stage + success rate
        lines.append(
            f'<text x="{rx + NODE_W//2}" y="{ry + 30}" text-anchor="middle" '
            f'font-family="Menlo,monospace" font-size="9" fill="#D1D5DB">'
            f'{stage.upper()} · sr={sr_pct}</text>'
        )
        # MAE
        lines.append(
            f'<text x="{rx + NODE_W//2}" y="{ry + 42}" text-anchor="middle" '
            f'font-family="Menlo,monospace" font-size="8" fill="#9CA3AF">'
            f'mae={v["mae"]:.3f}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    versions = db_list_versions()
    audit = db_audit_log(limit=20)
    prod = db_production_version()
    svg_dag = _build_svg_dag(versions)

    prod_banner = ""
    if prod:
        prod_banner = f"""
        <div class="prod-banner">
          <span style="color:#34D399;font-weight:700;font-size:1.1em;">PRODUCTION</span>
          <span style="margin-left:16px;font-size:1em;">{prod['version_id']}</span>
          <span style="color:#9CA3AF;margin-left:16px;">
            success={prod['success_rate']:.0%} &nbsp;|&nbsp;
            mae={prod['mae']:.3f} &nbsp;|&nbsp;
            latency={prod['avg_latency_ms']:.1f}ms &nbsp;|&nbsp;
            cost=${prod['training_cost_usd']:.2f} &nbsp;|&nbsp;
            promoted={prod.get('promoted_at','—')[:10]}
          </span>
        </div>
        """

    rows_html = ""
    for v in versions:
        rows_html += f"""
        <tr id="row-{v['version_id']}">
          <td style="font-family:monospace;font-weight:600">{v['version_id']}</td>
          <td>{v['training_method']}</td>
          <td>{_stage_badge(v['stage'])}</td>
          <td style="color:{'#34D399' if v['success_rate']>=0.4 else '#FCD34D' if v['success_rate']>=0.2 else '#F87171'}">{v['success_rate']:.1%}</td>
          <td>{v['mae']:.3f}</td>
          <td>{v['avg_latency_ms']:.1f}</td>
          <td>${v['training_cost_usd']:.2f}</td>
          <td>{v['n_demos']:,}</td>
          <td>{v['n_steps']:,}</td>
          <td style="color:#6EE7B7;font-size:0.78em">{v.get('parent_version_id') or '—'}</td>
          <td>{_promote_buttons(v)}</td>
        </tr>"""

    audit_rows = ""
    for a in audit:
        action_color = {
            "promoted": "#60A5FA",
            "created":  "#34D399",
            "deleted":  "#F87171",
            "updated":  "#FCD34D",
            "auto-archived": "#9CA3AF",
        }.get(a["action"], "#E5E7EB")
        audit_rows += f"""
        <tr>
          <td style="color:#6B7280;font-size:0.78em">{a['timestamp'][:19]}</td>
          <td style="font-family:monospace;font-size:0.85em">{a['version_id']}</td>
          <td><span style="color:{action_color};font-weight:600">{a['action']}</span></td>
          <td style="color:#9CA3AF">{a.get('from_stage') or '—'} → {a.get('to_stage') or '—'}</td>
          <td>{a.get('actor') or '—'}</td>
          <td style="color:#9CA3AF;font-size:0.82em">{a.get('reason') or ''}</td>
        </tr>"""

    version_ids_json = json.dumps([v["version_id"] for v in versions])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OCI Robot Cloud — Model Version Registry</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0D1117;
      color: #E5E7EB;
      font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
      font-size: 13px;
      padding: 24px 32px;
    }}
    h1 {{ color: #60A5FA; font-size: 1.4em; margin-bottom: 4px; }}
    h2 {{ color: #93C5FD; font-size: 1.0em; margin: 24px 0 10px; text-transform: uppercase;
          letter-spacing: 0.08em; border-bottom: 1px solid #1F2937; padding-bottom: 6px; }}
    .subtitle {{ color: #6B7280; font-size: 0.85em; margin-bottom: 20px; }}
    .prod-banner {{
      background: #064E3B;
      border: 1px solid #059669;
      border-radius: 8px;
      padding: 12px 20px;
      margin-bottom: 20px;
    }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
    th {{
      background: #161B22;
      color: #6B7280;
      padding: 8px 10px;
      text-align: left;
      border-bottom: 2px solid #21262D;
      font-size: 0.78em;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      white-space: nowrap;
    }}
    td {{
      padding: 8px 10px;
      border-bottom: 1px solid #161B22;
      font-size: 0.85em;
      color: #C9D1D9;
      vertical-align: middle;
    }}
    tr:hover td {{ background: #161B22; }}
    .dag-container {{
      overflow-x: auto;
      background: #111827;
      border-radius: 8px;
      padding: 12px;
      border: 1px solid #1F2937;
    }}
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.75);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }}
    .modal-overlay.active {{ display: flex; }}
    .modal {{
      background: #1F2937;
      border: 1px solid #374151;
      border-radius: 10px;
      padding: 28px;
      width: 440px;
      max-width: 95vw;
    }}
    .modal h3 {{ color: #60A5FA; margin-bottom: 16px; }}
    .modal label {{ color: #9CA3AF; font-size: 0.85em; display: block; margin-bottom: 4px; margin-top: 12px; }}
    .modal input, .modal select, .modal textarea {{
      width: 100%;
      background: #111827;
      border: 1px solid #374151;
      border-radius: 6px;
      color: #E5E7EB;
      padding: 8px 10px;
      font-family: inherit;
      font-size: 0.9em;
    }}
    .modal textarea {{ height: 72px; resize: vertical; }}
    .modal .btn-row {{ display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }}
    button.primary {{
      background: #2563EB;
      color: #fff;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.9em;
      font-weight: 600;
    }}
    button.primary:hover {{ background: #1D4ED8; }}
    button.cancel {{
      background: #374151;
      color: #E5E7EB;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.9em;
    }}
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1F2937;
      border: 1px solid #374151;
      border-radius: 8px;
      padding: 12px 20px;
      color: #34D399;
      font-size: 0.9em;
      opacity: 0;
      transition: opacity 0.3s;
      z-index: 200;
    }}
    #toast.show {{ opacity: 1; }}
    .compare-section {{
      background: #161B22;
      border: 1px solid #1F2937;
      border-radius: 8px;
      padding: 16px 20px;
      margin-top: 24px;
    }}
    .compare-section select, .compare-section input {{
      background: #111827;
      border: 1px solid #374151;
      border-radius: 6px;
      color: #E5E7EB;
      padding: 6px 10px;
      font-family: inherit;
      font-size: 0.88em;
      margin: 0 8px 0 4px;
    }}
    #compare-result table {{ margin-top: 12px; }}
    .footer {{
      color: #4B5563;
      font-size: 0.75em;
      margin-top: 40px;
      border-top: 1px solid #1F2937;
      padding-top: 10px;
    }}
  </style>
</head>
<body>

  <h1>OCI Robot Cloud — Model Version Registry</h1>
  <div class="subtitle">
    GR00T Fine-Tuning Pipeline &nbsp;·&nbsp; FastAPI port {PORT} &nbsp;·&nbsp;
    <a href="/docs" style="color:#60A5FA">Swagger UI</a> &nbsp;|&nbsp;
    <a href="/audit" style="color:#60A5FA">Audit Log (JSON)</a>
  </div>

  {prod_banner}

  <h2>Version Lineage DAG</h2>
  <div class="dag-container">{svg_dag}</div>

  <h2>All Versions</h2>
  <table>
    <thead>
      <tr>
        <th>Version ID</th>
        <th>Method</th>
        <th>Stage</th>
        <th>Success</th>
        <th>MAE</th>
        <th>Latency (ms)</th>
        <th>Cost</th>
        <th>Demos</th>
        <th>Steps</th>
        <th>Parent</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="versions-tbody">
      {rows_html}
    </tbody>
  </table>

  <!-- Compare widget -->
  <div class="compare-section">
    <span style="color:#93C5FD;font-weight:700;">Compare Versions</span>
    &nbsp;&nbsp;
    <label>A: <select id="cmp-a">{_version_options(versions)}</select></label>
    <label>B: <select id="cmp-b">{_version_options(versions, default_idx=1)}</select></label>
    <button class="primary" onclick="runCompare()" style="padding:6px 14px;font-size:0.85em">Compare</button>
    <div id="compare-result"></div>
  </div>

  <h2>Recent Audit Log</h2>
  <table>
    <thead>
      <tr>
        <th>Timestamp (UTC)</th>
        <th>Version</th>
        <th>Action</th>
        <th>Transition</th>
        <th>Actor</th>
        <th>Reason</th>
      </tr>
    </thead>
    <tbody>{audit_rows}</tbody>
  </table>

  <div class="footer">
    OCI Robot Cloud · github.com/qianjun22/roboticsai · Last refreshed: <span id="ts"></span>
  </div>

  <!-- Promote modal -->
  <div class="modal-overlay" id="promote-modal">
    <div class="modal">
      <h3 id="modal-title">Promote Version</h3>
      <input type="hidden" id="modal-version-id">
      <input type="hidden" id="modal-target-stage">
      <label>Approver</label>
      <input type="text" id="modal-approver" placeholder="your name or user ID">
      <label>Reason / Approval Notes</label>
      <textarea id="modal-reason" placeholder="Why is this version ready for promotion?"></textarea>
      <div class="btn-row">
        <button class="cancel" onclick="closeModal()">Cancel</button>
        <button class="primary" onclick="submitPromotion()">Confirm Promotion</button>
      </div>
    </div>
  </div>

  <div id="toast"></div>

  <script>
    const VERSION_IDS = {version_ids_json};

    document.getElementById('ts').textContent = new Date().toUTCString();

    function promoteVersion(versionId, targetStage) {{
      document.getElementById('modal-version-id').value = versionId;
      document.getElementById('modal-target-stage').value = targetStage;
      document.getElementById('modal-title').textContent =
        'Promote \u201c' + versionId + '\u201d \u2192 ' + targetStage.toUpperCase();
      document.getElementById('modal-approver').value = '';
      document.getElementById('modal-reason').value = '';
      document.getElementById('promote-modal').classList.add('active');
    }}

    function closeModal() {{
      document.getElementById('promote-modal').classList.remove('active');
    }}

    async function submitPromotion() {{
      const versionId   = document.getElementById('modal-version-id').value;
      const targetStage = document.getElementById('modal-target-stage').value;
      const approver    = document.getElementById('modal-approver').value.trim();
      const reason      = document.getElementById('modal-reason').value.trim();

      if (!approver || !reason) {{
        showToast('Approver and reason are required.', '#F87171');
        return;
      }}

      const resp = await fetch('/versions/' + versionId + '/promote', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ target_stage: targetStage, approver, reason }})
      }});

      if (resp.ok) {{
        showToast(versionId + ' promoted to ' + targetStage.toUpperCase(), '#34D399');
        closeModal();
        setTimeout(() => location.reload(), 800);
      }} else {{
        const err = await resp.json();
        showToast('Error: ' + (err.detail || 'unknown'), '#F87171');
      }}
    }}

    function showToast(msg, color='#34D399') {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.color = color;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 3000);
    }}

    function _version_options_js(ids, defaultIdx) {{
      return ids.map((id, i) =>
        `<option value="${{id}}" ${{i===defaultIdx ? 'selected' : ''}}>${{id}}</option>`
      ).join('');
    }}

    // Populate compare dropdowns dynamically
    (function() {{
      const a = document.getElementById('cmp-a');
      const b = document.getElementById('cmp-b');
      if (a && b) {{
        VERSION_IDS.forEach((id, i) => {{
          a.innerHTML += `<option value="${{id}}" ${{i===0?'selected':''}}>${{id}}</option>`;
          b.innerHTML += `<option value="${{id}}" ${{i===1?'selected':''}}>${{id}}</option>`;
        }});
      }}
    }})();

    async function runCompare() {{
      const a = document.getElementById('cmp-a').value;
      const b = document.getElementById('cmp-b').value;
      if (a === b) {{ showToast('Select two different versions', '#FCD34D'); return; }}

      const resp = await fetch('/versions/compare?a=' + a + '&b=' + b);
      const data = await resp.json();
      if (!resp.ok) {{ showToast('Error: ' + (data.detail||'unknown'), '#F87171'); return; }}

      const metricLabels = {{
        success_rate: 'Success Rate',
        avg_latency_ms: 'Latency P50 (ms)',
        mae: 'MAE',
        training_cost_usd: 'Training Cost ($)',
        n_demos: 'Demo Count',
        n_steps: 'Train Steps',
      }};

      let rows = '';
      for (const [key, label] of Object.entries(metricLabels)) {{
        const m = data.metrics[key];
        if (!m) continue;
        const pct = m.pct_change != null ? (m.pct_change > 0 ? '+' : '') + m.pct_change.toFixed(1) + '%' : '—';
        const pctColor = m.pct_change == null ? '#9CA3AF' :
          (key === 'mae' || key === 'avg_latency_ms' || key === 'training_cost_usd')
            ? (m.pct_change < 0 ? '#34D399' : '#F87171')
            : (m.pct_change > 0 ? '#34D399' : '#F87171');
        rows += `<tr>
          <td>${{label}}</td>
          <td>${{typeof m.v1 === 'number' ? m.v1.toFixed(4) : m.v1}}</td>
          <td>${{typeof m.v2 === 'number' ? m.v2.toFixed(4) : m.v2}}</td>
          <td style="color:${{m.delta>0?'#60A5FA':m.delta<0?'#F9A8D4':'#9CA3AF'}}">${{m.delta!=null?(m.delta>0?'+':'')+m.delta.toFixed(4):'—'}}</td>
          <td style="color:${{pctColor}};font-weight:600">${{pct}}</td>
        </tr>`;
      }}

      document.getElementById('compare-result').innerHTML = `
        <table style="margin-top:12px">
          <thead>
            <tr>
              <th>Metric</th>
              <th>${{a}}</th>
              <th>${{b}}</th>
              <th>Delta (b−a)</th>
              <th>% Change</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


def _version_options(versions: List[dict], default_idx: int = 0) -> str:
    """Render server-side <option> tags for dropdowns (overwritten client-side by JS)."""
    # The JS repopulates these, so just emit one placeholder
    return ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[model_versioning_api] Starting on http://0.0.0.0:{PORT}")
    print(f"[model_versioning_api] SQLite DB: {DB_PATH}")
    print(f"[model_versioning_api] Dashboard: http://localhost:{PORT}/")
    print(f"[model_versioning_api] Swagger UI: http://localhost:{PORT}/docs")
    uvicorn.run("model_versioning_api:app", host="0.0.0.0", port=PORT, reload=False)
