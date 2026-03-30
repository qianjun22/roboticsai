#!/usr/bin/env python3
"""
episode_annotator.py — Web UI for labeling robot episode quality (port 8034).

Design partners use this to review captured episodes and annotate:
  - Success / failure label override
  - Failure cause (approach/grasp/lift/drop/other)
  - Quality score (1–5 stars)
  - Free-text notes

Labeled data improves DAgger training by filtering out low-quality episodes
and weighting high-quality demonstrations more heavily.

Usage:
    python src/eval/episode_annotator.py --port 8034 --mock
    # → http://localhost:8034
"""

import json
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, Form, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

DB_PATH = "/tmp/episode_annotations.db"

FAILURE_CAUSES = [
    "approach_error",   # robot didn't reach cube
    "grasp_failure",    # gripper didn't close on cube
    "lift_failure",     # cube not lifted high enough
    "cube_dropped",     # cube dropped during lift
    "knocked_off",      # cube knocked off table
    "out_of_reach",     # cube too far from start position
    "other",
]


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS episodes (
            id TEXT PRIMARY KEY,
            run_name TEXT,
            episode_idx INTEGER,
            auto_success INTEGER,   -- 0/1 from eval script
            cube_z_final REAL,
            latency_ms REAL,
            n_steps INTEGER,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS annotations (
            episode_id TEXT PRIMARY KEY,
            success_override INTEGER,   -- NULL = use auto, 0/1 = manual override
            quality_score INTEGER,      -- 1–5 stars
            failure_cause TEXT,
            notes TEXT,
            annotated_by TEXT,
            annotated_at TEXT
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


def seed_mock_episodes(db_path: str = DB_PATH) -> None:
    rng = random.Random(2026)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM episodes")
        conn.execute("DELETE FROM annotations")

        runs = ["eval_1000demo", "dagger_run5_final", "dagger_run6_iter1"]
        for run in runs:
            for i in range(20):
                ep_id = f"{run}_ep{i:02d}"
                success = 1 if rng.random() < 0.15 else 0
                cube_z = 0.78 + rng.gauss(0, 0.02) if success else 0.705 + rng.gauss(0,0.01)
                conn.execute(
                    "INSERT OR IGNORE INTO episodes VALUES (?,?,?,?,?,?,?,?)",
                    (ep_id, run, i, success, cube_z,
                     rng.gauss(226, 12), 50 + rng.randint(0,20),
                     (datetime.now()-timedelta(days=rng.randint(0,7))).isoformat())
                )
                # Annotate some
                if rng.random() < 0.3:
                    cause = rng.choice(FAILURE_CAUSES) if not success else ""
                    conn.execute(
                        "INSERT OR IGNORE INTO annotations VALUES (?,?,?,?,?,?,?)",
                        (ep_id, None, rng.randint(1,5), cause,
                         "auto-annotated" if rng.random() < 0.5 else "",
                         "demo", datetime.now().isoformat())
                    )


# ── Queries ───────────────────────────────────────────────────────────────────

def get_episodes(run_name: Optional[str] = None,
                 unannotated_only: bool = False,
                 db_path: str = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        query = """
        SELECT e.*, a.success_override, a.quality_score, a.failure_cause, a.notes, a.annotated_at
        FROM episodes e
        LEFT JOIN annotations a ON e.id = a.episode_id
        """
        conditions = []
        params = []
        if run_name:
            conditions.append("e.run_name=?")
            params.append(run_name)
        if unannotated_only:
            conditions.append("a.episode_id IS NULL")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY e.created_at DESC, e.episode_idx ASC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def save_annotation(episode_id: str, success_override: Optional[int],
                    quality_score: int, failure_cause: str, notes: str,
                    annotated_by: str = "user", db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        INSERT INTO annotations (episode_id, success_override, quality_score,
                                  failure_cause, notes, annotated_by, annotated_at)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(episode_id) DO UPDATE SET
          success_override=excluded.success_override,
          quality_score=excluded.quality_score,
          failure_cause=excluded.failure_cause,
          notes=excluded.notes,
          annotated_by=excluded.annotated_by,
          annotated_at=excluded.annotated_at
        """, (episode_id, success_override, quality_score,
              failure_cause, notes, annotated_by, datetime.now().isoformat()))


# ── HTML pages ────────────────────────────────────────────────────────────────

def render_episode_list(db_path: str = DB_PATH) -> str:
    eps = get_episodes(db_path=db_path)
    runs = sorted(set(e["run_name"] for e in eps))
    n_annotated = sum(1 for e in eps if e["annotated_at"])
    n_total = len(eps)
    pct = n_annotated / max(n_total, 1) * 100

    run_options = "".join(f'<option value="{r}">{r}</option>' for r in runs)

    rows = ""
    for e in eps[:50]:
        success = e["success_override"] if e["success_override"] is not None else e["auto_success"]
        s_icon = "✅" if success else "❌"
        q_stars = "★" * (e["quality_score"] or 0)
        ann_icon = "✏️" if e["annotated_at"] else "○"
        cause = e["failure_cause"] or ""
        rows += f"""<tr onclick="window.location='/annotate/{e['id']}'" style="cursor:pointer">
          <td style="padding:8px 10px;font-family:monospace;font-size:12px">{e['id']}</td>
          <td style="padding:8px 10px;text-align:center">{s_icon}</td>
          <td style="padding:8px 10px;font-family:monospace">{e['cube_z_final']:.3f}m</td>
          <td style="padding:8px 10px;font-size:12px;color:#94a3b8">{e['latency_ms']:.0f}ms</td>
          <td style="padding:8px 10px;color:#f59e0b">{q_stars or '—'}</td>
          <td style="padding:8px 10px;font-size:12px;color:#64748b">{cause}</td>
          <td style="padding:8px 10px;text-align:center">{ann_icon}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Episode Annotator</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  tr:hover td{{background:#243249}}
  select{{background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:6px;border-radius:6px}}
</style>
</head>
<body>
<h1>Episode Annotator</h1>
<p style="color:#94a3b8;font-size:13px;margin:0 0 16px">Label episode quality to improve DAgger training</p>

<div class="card">
  <div style="display:flex;gap:16px;align-items:center">
    <div>
      <div style="font-size:24px;font-weight:700;color:#3b82f6">{n_annotated}/{n_total}</div>
      <div style="font-size:11px;color:#64748b">Annotated</div>
    </div>
    <div style="flex:1;background:#334155;height:8px;border-radius:4px">
      <div style="background:#3b82f6;width:{pct:.0f}%;height:100%;border-radius:4px"></div>
    </div>
    <div style="color:#64748b;font-size:13px">{pct:.0f}%</div>
  </div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:12px;text-transform:uppercase;margin-top:0">Episodes</h3>
  <table>
    <tr><th>Episode</th><th>Success</th><th>Cube Z</th><th>Latency</th><th>Quality</th><th>Cause</th><th>Ann.</th></tr>
    {rows}
  </table>
</div>

<div style="color:#475569;font-size:11px">
  <a href="/api/episodes" style="color:#3b82f6">/api/episodes</a> ·
  <a href="/api/export" style="color:#3b82f6">Export CSV</a>
</div>
</body>
</html>"""


def render_annotation_form(episode: dict) -> str:
    ep = episode
    success = ep["success_override"] if ep["success_override"] is not None else ep["auto_success"]
    quality = ep.get("quality_score") or 3
    cause   = ep.get("failure_cause") or ""
    notes   = ep.get("notes") or ""

    cause_options = "".join(
        f'<option value="{c}" {"selected" if c==cause else ""}>{c.replace("_"," ").title()}</option>'
        for c in [""] + FAILURE_CAUSES
    )
    stars_html = "".join(
        f'<input type="radio" name="quality_score" value="{i}" id="s{i}" '
        f'{"checked" if quality==i else ""}>'
        f'<label for="s{i}" style="cursor:pointer;font-size:20px;color:{"#f59e0b" if quality>=i else "#334155"}">★</label>'
        for i in range(1, 6)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Annotate {ep['id']}</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:24px;max-width:560px}}
  label{{display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;text-transform:uppercase}}
  select,textarea{{width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;
    color:#e2e8f0;border-radius:6px;padding:8px;font-size:14px;margin-bottom:14px}}
  button{{background:#3b82f6;color:white;border:none;padding:10px 20px;border-radius:6px;
    font-size:14px;font-weight:600;cursor:pointer}}
  .info{{background:#1e293b;border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px}}
</style>
</head>
<body>
<a href="/" style="color:#3b82f6;text-decoration:none;font-size:13px">← Episodes</a>
<h1 style="font-size:18px;color:#f8fafc;margin:12px 0">{ep['id']}</h1>

<div class="info">
  <strong>Auto result:</strong> {'✅ Success' if ep['auto_success'] else '❌ Failure'} ·
  cube_z={ep['cube_z_final']:.3f}m · {ep['latency_ms']:.0f}ms · {ep['n_steps']} steps
</div>

<form method="POST" action="/annotate/{ep['id']}">
  <label>Override Success</label>
  <select name="success_override">
    <option value="">Use auto ({('Success' if ep['auto_success'] else 'Failure')})</option>
    <option value="1" {"selected" if ep.get("success_override") == 1 else ""}>✅ Mark Success</option>
    <option value="0" {"selected" if ep.get("success_override") == 0 else ""}>❌ Mark Failure</option>
  </select>

  <label>Quality Score</label>
  <div style="margin-bottom:14px">{stars_html}</div>

  <label>Failure Cause</label>
  <select name="failure_cause">{cause_options}</select>

  <label>Notes</label>
  <textarea name="notes" rows="2" placeholder="Observations...">{notes}</textarea>

  <button type="submit">Save Annotation</button>
</form>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(db_path: str = DB_PATH) -> "FastAPI":
    app = FastAPI(title="Episode Annotator", version="1.0")

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        seed_mock_episodes(db_path)

    @app.get("/", response_class=HTMLResponse)
    async def episode_list():
        return render_episode_list(db_path)

    @app.get("/annotate/{episode_id}", response_class=HTMLResponse)
    async def annotation_form(episode_id: str):
        eps = get_episodes(db_path=db_path)
        ep = next((e for e in eps if e["id"] == episode_id), None)
        if not ep:
            raise HTTPException(404, "Episode not found")
        return render_annotation_form(ep)

    @app.post("/annotate/{episode_id}", response_class=HTMLResponse)
    async def save_ann(
        episode_id: str,
        success_override: str = Form(""),
        quality_score: int = Form(3),
        failure_cause: str = Form(""),
        notes: str = Form(""),
    ):
        so = int(success_override) if success_override in ("0","1") else None
        save_annotation(episode_id, so, quality_score, failure_cause, notes,
                        db_path=db_path)
        eps = get_episodes(db_path=db_path)
        ep = next((e for e in eps if e["id"] == episode_id), None)
        return render_annotation_form(ep) if ep else "<p>Saved</p>"

    @app.get("/api/episodes")
    async def api_episodes(run_name: Optional[str] = None, unannotated: bool = False):
        return get_episodes(run_name, unannotated, db_path)

    @app.get("/api/export")
    async def api_export():
        from fastapi.responses import Response
        eps = get_episodes(db_path=db_path)
        header = "id,run_name,episode_idx,auto_success,success_override,cube_z_final,quality_score,failure_cause,notes\n"
        body = "".join(
            f"{e['id']},{e['run_name']},{e['episode_idx']},{e['auto_success']},"
            f"{e['success_override'] or ''},"
            f"{e['cube_z_final']:.4f},{e['quality_score'] or ''},"
            f"{e['failure_cause'] or ''},{(e['notes'] or '').replace(',','')}\n"
            for e in eps
        )
        return Response(content=header+body, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=annotations.csv"})

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "episode_annotator", "port": 8034}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Episode annotator (port 8034)")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db",   default=DB_PATH)
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    init_db(args.db)
    seed_mock_episodes(args.db)
    app = create_app(args.db)
    print(f"Episode Annotator → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
