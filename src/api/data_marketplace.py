#!/usr/bin/env python3
"""
data_marketplace.py — Anonymized training data marketplace for OCI Robot Cloud.

Design partners can share anonymized episode statistics and discover compatible
datasets from other partners. Partners upload dataset metadata (not raw data),
and the system recommends cross-partner fine-tuning opportunities.

Usage:
    python src/api/data_marketplace.py --port 8044
    python src/api/data_marketplace.py --port 8044 --db /tmp/data_marketplace.db
"""

import argparse
import json
import random
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    print("pip install fastapi uvicorn pydantic")
    raise

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class DatasetListing:
    listing_id: str
    partner_id: str                    # anonymized, e.g. "partner_a"
    robot_type: str                    # franka / ur5e / xarm7
    task_category: str                 # pick / place / assembly / inspection
    n_episodes: int
    n_frames: int
    success_rate_of_demos: float       # 0.0 – 1.0
    joint_diversity_score: float       # 0.0 – 1.0
    position_diversity_score: float    # 0.0 – 1.0
    lighting_diversity_score: float    # 0.0 – 1.0
    created_at: str
    compatible_robots: List[str]
    price_type: str                    # "free" / "shared" / "request"
    tags: List[str]


# Pydantic model for POST body (FastAPI validation)
class DatasetListingIn(BaseModel):
    listing_id: str
    partner_id: str
    robot_type: str
    task_category: str
    n_episodes: int
    n_frames: int
    success_rate_of_demos: float
    joint_diversity_score: float
    position_diversity_score: float
    lighting_diversity_score: float
    created_at: Optional[str] = None
    compatible_robots: List[str] = []
    price_type: str = "free"
    tags: List[str] = []


class InterestIn(BaseModel):
    requester_id: str


# ── Compatibility scoring ──────────────────────────────────────────────────────

def compatibility_score(listing: DatasetListing, robot_type: str, task: str) -> float:
    """Compute 0-1 compatibility between a listing and a query (robot_type + task)."""
    score = 0.0

    # Robot type match (40%)
    if listing.robot_type == robot_type:
        score += 0.40
    elif robot_type in listing.compatible_robots:
        score += 0.25

    # Task match (30%) — allow partial substring match (e.g. "pick-and-lift" ~ "pick")
    task_norm = task.lower().replace("-", " ").replace("_", " ")
    listing_task_norm = listing.task_category.lower()
    if listing_task_norm in task_norm or task_norm in listing_task_norm:
        score += 0.30

    # Diversity scores contribute the remaining 30% (10% each)
    score += listing.joint_diversity_score * 0.10
    score += listing.position_diversity_score * 0.10
    score += listing.lighting_diversity_score * 0.10

    return round(min(score, 1.0), 4)


# ── SQLite persistence ─────────────────────────────────────────────────────────

DB_PATH = "/tmp/data_marketplace.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                listing_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                requester_id TEXT NOT NULL,
                requested_at TEXT NOT NULL
            )
        """)


def _row_to_listing(row) -> DatasetListing:
    d = json.loads(row["data"])
    return DatasetListing(**d)


def db_insert_listing(listing: DatasetListing) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO listings (listing_id, data) VALUES (?, ?)",
            (listing.listing_id, json.dumps(asdict(listing)))
        )


def db_get_all_listings() -> List[DatasetListing]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM listings").fetchall()
    return [_row_to_listing(r) for r in rows]


def db_get_listing(listing_id: str) -> Optional[DatasetListing]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
    return _row_to_listing(row) if row else None


def db_log_interest(listing_id: str, requester_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO interests (listing_id, requester_id, requested_at) VALUES (?, ?, ?)",
            (listing_id, requester_id, datetime.now(timezone.utc).isoformat())
        )


# ── Mock data ──────────────────────────────────────────────────────────────────

MOCK_LISTINGS: List[DatasetListing] = [
    DatasetListing("lst_001", "partner_a", "franka", "pick", 1200, 360000,
                   0.87, 0.82, 0.79, 0.65, "2026-01-10T08:00:00Z",
                   ["xarm7"], "free", ["tabletop", "single-arm", "short-horizon"]),
    DatasetListing("lst_002", "partner_a", "franka", "place", 800, 240000,
                   0.91, 0.74, 0.88, 0.70, "2026-01-15T09:30:00Z",
                   ["ur5e"], "shared", ["bin-packing", "precision"]),
    DatasetListing("lst_003", "partner_b", "ur5e", "assembly", 2000, 800000,
                   0.76, 0.93, 0.85, 0.55, "2026-02-01T11:00:00Z",
                   ["franka"], "request", ["multi-step", "contact-rich", "industrial"]),
    DatasetListing("lst_004", "partner_b", "ur5e", "inspection", 600, 180000,
                   0.95, 0.61, 0.72, 0.90, "2026-02-14T14:00:00Z",
                   [], "free", ["quality-control", "vision-heavy"]),
    DatasetListing("lst_005", "partner_c", "xarm7", "pick", 1500, 450000,
                   0.83, 0.88, 0.91, 0.77, "2026-02-20T10:00:00Z",
                   ["franka", "ur5e"], "shared", ["diverse-lighting", "clutter"]),
    DatasetListing("lst_006", "partner_c", "xarm7", "assembly", 900, 360000,
                   0.79, 0.85, 0.80, 0.68, "2026-03-01T08:45:00Z",
                   ["franka"], "request", ["screw-driving", "force-sensitive"]),
    DatasetListing("lst_007", "partner_d", "franka", "inspection", 400, 120000,
                   0.92, 0.55, 0.60, 0.88, "2026-03-10T13:00:00Z",
                   ["xarm7"], "free", ["surface-defect", "high-res-camera"]),
    DatasetListing("lst_008", "partner_e", "ur5e", "pick", 3000, 900000,
                   0.81, 0.96, 0.94, 0.82, "2026-03-15T07:30:00Z",
                   ["franka", "xarm7"], "shared", ["warehouse", "large-scale", "diverse-objects"]),
]


def seed_mock_data() -> None:
    existing = {l.listing_id for l in db_get_all_listings()}
    for listing in MOCK_LISTINGS:
        if listing.listing_id not in existing:
            db_insert_listing(listing)


# ── Recommendation ─────────────────────────────────────────────────────────────

def recommend_listings(robot_type: str, task: str, top_k: int = 3) -> List[dict]:
    all_listings = db_get_all_listings()
    scored = [
        {**asdict(l), "compatibility_score": compatibility_score(l, robot_type, task)}
        for l in all_listings
    ]
    scored.sort(key=lambda x: x["compatibility_score"], reverse=True)
    return scored[:top_k]


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="OCI Robot Cloud — Data Marketplace", version="1.0.0")


@app.on_event("startup")
def on_startup():
    init_db()
    seed_mock_data()


@app.get("/health")
def health():
    return {"status": "ok", "service": "data_marketplace", "port": 8044}


@app.post("/api/listings")
def register_listing(body: DatasetListingIn):
    listing = DatasetListing(
        listing_id=body.listing_id,
        partner_id=body.partner_id,
        robot_type=body.robot_type,
        task_category=body.task_category,
        n_episodes=body.n_episodes,
        n_frames=body.n_frames,
        success_rate_of_demos=body.success_rate_of_demos,
        joint_diversity_score=body.joint_diversity_score,
        position_diversity_score=body.position_diversity_score,
        lighting_diversity_score=body.lighting_diversity_score,
        created_at=body.created_at or datetime.now(timezone.utc).isoformat(),
        compatible_robots=body.compatible_robots,
        price_type=body.price_type,
        tags=body.tags,
    )
    db_insert_listing(listing)
    return {"status": "registered", "listing_id": listing.listing_id}


@app.get("/api/listings")
def get_listings(
    robot_type: Optional[str] = None,
    task: Optional[str] = None,
    compatible_only: bool = False,
):
    all_listings = db_get_all_listings()
    result = []
    for l in all_listings:
        d = asdict(l)
        if robot_type:
            if compatible_only and l.robot_type != robot_type and robot_type not in l.compatible_robots:
                continue
        if task:
            task_norm = task.lower().replace("-", " ").replace("_", " ")
            listing_task_norm = l.task_category.lower()
            if task_norm not in listing_task_norm and listing_task_norm not in task_norm:
                continue
        if robot_type:
            d["compatibility_score"] = compatibility_score(l, robot_type, task or l.task_category)
        result.append(d)
    return result


@app.get("/api/recommend")
def recommend(robot_type: str, task: str, top_k: int = 3):
    return recommend_listings(robot_type, task, top_k)


@app.post("/api/interest/{listing_id}")
def log_interest(listing_id: str, body: InterestIn):
    listing = db_get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    db_log_interest(listing_id, body.requester_id)
    return {"status": "logged", "listing_id": listing_id, "requester_id": body.requester_id}


@app.get("/", response_class=HTMLResponse)
def portal():
    listings = db_get_all_listings()

    def diversity_bar(label: str, value: float, color: str) -> str:
        pct = int(value * 100)
        return f"""
        <div style="margin:4px 0">
          <span style="font-size:11px;color:#9CA3AF;width:90px;display:inline-block">{label}</span>
          <div style="display:inline-block;vertical-align:middle;width:100px;height:8px;background:#374151;border-radius:4px;overflow:hidden">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:4px"></div>
          </div>
          <span style="font-size:11px;color:#D1D5DB;margin-left:6px">{pct}%</span>
        </div>"""

    price_badge = {"free": ("#10B981", "FREE"), "shared": ("#F59E0B", "SHARED"), "request": ("#6366F1", "REQUEST")}

    cards = ""
    for l in listings:
        col, label = price_badge.get(l.price_type, ("#6B7280", l.price_type.upper()))
        compat_robots = ", ".join(l.compatible_robots) if l.compatible_robots else "—"
        tags_html = "".join(
            f'<span style="background:#1F2937;color:#93C5FD;font-size:10px;padding:2px 7px;border-radius:10px;margin:2px 2px 0 0">{t}</span>'
            for t in l.tags
        )
        cards += f"""
        <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:20px;position:relative">
          <div style="position:absolute;top:14px;right:14px;background:{col};color:#fff;font-size:10px;font-weight:700;padding:3px 9px;border-radius:10px">{label}</div>
          <div style="font-size:13px;color:#6B7280;margin-bottom:2px">{l.partner_id} · {l.listing_id}</div>
          <div style="font-size:17px;font-weight:600;color:#F9FAFB;margin-bottom:4px">{l.robot_type.upper()} — {l.task_category}</div>
          <div style="font-size:12px;color:#9CA3AF;margin-bottom:10px">
            {l.n_episodes:,} episodes · {l.n_frames:,} frames · {int(l.success_rate_of_demos*100)}% success
          </div>
          {diversity_bar("Joint div.", l.joint_diversity_score, "#6366F1")}
          {diversity_bar("Position div.", l.position_diversity_score, "#10B981")}
          {diversity_bar("Lighting div.", l.lighting_diversity_score, "#F59E0B")}
          <div style="font-size:11px;color:#9CA3AF;margin-top:10px">Compatible: {compat_robots}</div>
          <div style="margin-top:8px">{tags_html}</div>
          <button onclick="requestAccess('{l.listing_id}')"
            style="margin-top:14px;width:100%;padding:8px;background:#1D4ED8;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600">
            Request Access
          </button>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — Data Marketplace</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: 'Inter', system-ui, sans-serif; background:#030712; color:#F9FAFB; }}
    input, select {{ background:#111827; border:1px solid #374151; color:#F9FAFB; border-radius:8px; padding:8px 12px; font-size:13px; outline:none; }}
    input:focus, select:focus {{ border-color:#6366F1; }}
  </style>
</head>
<body>
<div style="max-width:1200px;margin:0 auto;padding:32px 24px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:32px">
    <div>
      <div style="font-size:11px;color:#6366F1;font-weight:700;letter-spacing:2px;text-transform:uppercase">OCI Robot Cloud</div>
      <h1 style="margin:4px 0 0;font-size:28px;font-weight:700">Data Marketplace</h1>
      <p style="margin:6px 0 0;color:#6B7280;font-size:14px">Discover anonymized training datasets from design partners</p>
    </div>
    <div style="font-size:13px;color:#9CA3AF">{len(listings)} datasets · 5 partners</div>
  </div>

  <!-- Filters -->
  <div style="display:flex;gap:12px;margin-bottom:28px;flex-wrap:wrap">
    <select id="filterRobot" onchange="applyFilters()">
      <option value="">All robots</option>
      <option value="franka">Franka</option>
      <option value="ur5e">UR5e</option>
      <option value="xarm7">xArm7</option>
    </select>
    <select id="filterTask" onchange="applyFilters()">
      <option value="">All tasks</option>
      <option value="pick">Pick</option>
      <option value="place">Place</option>
      <option value="assembly">Assembly</option>
      <option value="inspection">Inspection</option>
    </select>
    <label style="display:flex;align-items:center;gap:6px;font-size:13px;color:#9CA3AF;cursor:pointer">
      <input type="checkbox" id="compatibleOnly" onchange="applyFilters()" style="width:16px;height:16px;accent-color:#6366F1"/>
      Compatible only
    </label>
    <button onclick="applyFilters()"
      style="padding:8px 20px;background:#6366F1;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600">
      Search
    </button>
  </div>

  <!-- Grid -->
  <div id="grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px">
    {cards}
  </div>

  <!-- Recommend panel -->
  <div style="margin-top:40px;background:#111827;border:1px solid #1F2937;border-radius:12px;padding:24px">
    <h2 style="margin:0 0 16px;font-size:18px">Get Recommendations</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap">
      <input id="recRobot" placeholder="Robot type (e.g. franka)" style="flex:1;min-width:160px"/>
      <input id="recTask"  placeholder="Task (e.g. pick-and-lift)" style="flex:1;min-width:160px"/>
      <button onclick="getRecommendations()"
        style="padding:8px 20px;background:#10B981;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600">
        Recommend
      </button>
    </div>
    <div id="recResults" style="margin-top:16px;font-size:13px;color:#9CA3AF"></div>
  </div>
</div>

<script>
function applyFilters() {{
  const robot = document.getElementById('filterRobot').value;
  const task  = document.getElementById('filterTask').value;
  const compat = document.getElementById('compatibleOnly').checked;
  let url = '/api/listings?';
  if (robot) url += 'robot_type=' + robot + '&';
  if (task)  url += 'task=' + task + '&';
  if (compat && robot) url += 'compatible_only=true&';
  fetch(url).then(r => r.json()).then(data => {{
    const grid = document.getElementById('grid');
    if (!data.length) {{ grid.innerHTML = '<p style="color:#6B7280">No datasets found.</p>'; return; }}
    grid.innerHTML = data.map(l => {{
      const score = l.compatibility_score !== undefined ? ` <span style="background:#1D4ED8;color:#fff;font-size:10px;padding:2px 7px;border-radius:8px">${{Math.round(l.compatibility_score*100)}}% match</span>` : '';
      return `<div style="background:#111827;border:1px solid #374151;border-radius:12px;padding:18px">
        <div style="font-size:14px;font-weight:600">${{l.robot_type.toUpperCase()}} — ${{l.task_category}}${{score}}</div>
        <div style="font-size:12px;color:#9CA3AF;margin-top:4px">${{l.partner_id}} · ${{l.n_episodes.toLocaleString()}} eps · ${{Math.round(l.success_rate_of_demos*100)}}% success</div>
        <div style="font-size:11px;color:#6B7280;margin-top:6px">J:${{Math.round(l.joint_diversity_score*100)}}% P:${{Math.round(l.position_diversity_score*100)}}% L:${{Math.round(l.lighting_diversity_score*100)}}%</div>
        <button onclick="requestAccess('${{l.listing_id}}')"
          style="margin-top:12px;width:100%;padding:7px;background:#1D4ED8;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:12px">
          Request Access
        </button>
      </div>`;
    }}).join('');
  }});
}}

function requestAccess(listingId) {{
  const requesterId = 'user_' + Math.random().toString(36).slice(2, 8);
  fetch('/api/interest/' + listingId, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{requester_id: requesterId}})
  }}).then(r => r.json()).then(() => alert('Access request logged for ' + listingId));
}}

function getRecommendations() {{
  const robot = document.getElementById('recRobot').value.trim();
  const task  = document.getElementById('recTask').value.trim();
  if (!robot || !task) {{ alert('Please enter both robot type and task.'); return; }}
  fetch('/api/recommend?robot_type=' + encodeURIComponent(robot) + '&task=' + encodeURIComponent(task))
    .then(r => r.json()).then(data => {{
      const div = document.getElementById('recResults');
      if (!data.length) {{ div.innerHTML = '<p>No recommendations found.</p>'; return; }}
      div.innerHTML = '<strong style="color:#F9FAFB">Top recommendations:</strong><br/>' + data.map(l =>
        `<div style="margin-top:10px;padding:10px;background:#1F2937;border-radius:8px">
          <span style="color:#F9FAFB;font-weight:600">${{l.robot_type.toUpperCase()}} / ${{l.task_category}}</span>
          <span style="background:#6366F1;color:#fff;font-size:10px;padding:2px 7px;border-radius:8px;margin-left:8px">${{Math.round(l.compatibility_score*100)}}% match</span>
          <div style="color:#9CA3AF;font-size:12px;margin-top:4px">${{l.partner_id}} · ${{l.n_episodes.toLocaleString()}} eps · ${{l.price_type}}</div>
        </div>`
      ).join('');
    }});
}}
</script>
</body>
</html>"""


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Data Marketplace")
    parser.add_argument("--port", type=int, default=8044, help="Port to listen on (default: 8044)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--db", type=str, default="/tmp/data_marketplace.db", help="SQLite DB path")
    args = parser.parse_args()

    DB_PATH = args.db
    init_db()
    seed_mock_data()

    print(f"Data Marketplace running at http://{args.host}:{args.port}")
    print(f"Database: {args.db}")
    uvicorn.run(app, host=args.host, port=args.port)
