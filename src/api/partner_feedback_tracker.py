#!/usr/bin/env python3
"""
partner_feedback_tracker.py — Partner NPS and qualitative feedback tracker.

Sends periodic feedback surveys to design partners and aggregates results into
a dashboard for customer success and product roadmap prioritization.

Usage:
    python src/api/partner_feedback_tracker.py [--port 8046] [--mock]

Endpoints:
    GET  /             Dark-theme HTML dashboard (NPS gauge, heatmap, quotes)
    POST /api/survey   Ingest a survey response
    GET  /api/surveys  List surveys (?partner_id=X to filter)
    GET  /api/aggregate  Aggregated NPS + ratings JSON
    GET  /health       Health check
"""

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Database ─────────────────────────────────────────────────────────────────

DB_PATH = "/tmp/partner_feedback.db"

PARTNERS = ["Agility Robotics", "Boston Dynamics", "Unitree", "Apptronik", "Figure AI"]
PARTNER_IDS = ["partner_001", "partner_002", "partner_003", "partner_004", "partner_005"]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                survey_id TEXT PRIMARY KEY,
                partner_id TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                responded_at TEXT,
                nps_score INTEGER,
                ease_of_use REAL,
                most_useful_feature TEXT,
                biggest_pain_point TEXT,
                would_recommend INTEGER,
                open_feedback TEXT,
                category_ratings TEXT
            )
        """)
        conn.commit()


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class FeedbackSurvey:
    survey_id: str
    partner_id: str
    sent_at: str
    responded_at: Optional[str]
    nps_score: int                        # 0-10
    ease_of_use: float                    # 1-5
    most_useful_feature: str
    biggest_pain_point: str
    would_recommend: bool
    open_feedback: str
    product_category_ratings: Dict[str, int]  # training_quality/latency/cost/docs/support → 1-5


# ── Mock data ─────────────────────────────────────────────────────────────────

_PAIN_POINTS = [
    "Training cost too high",
    "Cost visibility unclear",
    "Latency spikes during peak hours",
    "Documentation incomplete for edge cases",
    "Cost hard to predict month-over-month",
    "Onboarding could be faster",
    "Support response time slow on weekends",
    "Training cost hard to optimize",
    "Real-to-sim gap still present",
    "Cost calculator needs more granularity",
]

_FEATURES = [
    "GR00T fine-tuning pipeline",
    "Isaac Sim SDG integration",
    "Multi-GPU DDP training",
    "Real-time training monitor",
    "One-click deployment to Jetson",
    "Python SDK and CLI",
    "Automated eval harness",
    "DAgger data collection",
]

_QUOTES = [
    "The fine-tuning pipeline saved us 3 weeks of engineering work.",
    "Isaac Sim integration is a game changer for synthetic data.",
    "Latency is consistently under 300ms which meets our real-time needs.",
    "Cost is the main concern — we need better budget controls.",
    "The Python SDK made it trivial to integrate into our existing stack.",
    "Support team is responsive and technically deep.",
    "Documentation for advanced fine-tuning configs needs improvement.",
    "Multi-GPU training gave us the throughput we needed for production.",
    "Would love tighter Cosmos world model integration.",
    "Overall the platform is miles ahead of what we built in-house.",
]

import random
import hashlib


def _seed_mock_data():
    """Insert 20 realistic surveys from 5 partners over 3 months if table is empty."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM surveys").fetchone()[0]
        if count >= 20:
            return

    rng = random.Random(42)
    base_date = datetime(2025, 12, 15)
    surveys = []

    for i in range(20):
        partner_idx = i % 5
        pid = PARTNER_IDS[partner_idx]
        # spread across 3 months
        days_offset = rng.randint(0, 90)
        sent = base_date + timedelta(days=days_offset)
        responded = sent + timedelta(hours=rng.randint(2, 72))

        # NPS skewed toward promoter range (target NPS 40-70)
        nps_roll = rng.random()
        if nps_roll < 0.55:
            nps = rng.randint(9, 10)    # promoter
        elif nps_roll < 0.75:
            nps = rng.randint(7, 8)    # passive
        else:
            nps = rng.randint(0, 6)    # detractor

        ease = round(rng.uniform(3.2, 4.5), 1)
        feature = rng.choice(_FEATURES)
        pain = rng.choice(_PAIN_POINTS)
        recommend = nps >= 7
        quote = rng.choice(_QUOTES)

        # cost is most cited pain — weight it
        if rng.random() < 0.4:
            pain = rng.choice([p for p in _PAIN_POINTS if "ost" in p])

        cat_ratings = {
            "training_quality": rng.randint(3, 5),
            "latency": rng.randint(3, 5),
            "cost": rng.randint(2, 4),   # cost rated lower on average
            "docs": rng.randint(2, 5),
            "support": rng.randint(3, 5),
        }

        sid = hashlib.md5(f"{pid}-{i}".encode()).hexdigest()[:12]

        surveys.append(FeedbackSurvey(
            survey_id=sid,
            partner_id=pid,
            sent_at=sent.isoformat(),
            responded_at=responded.isoformat(),
            nps_score=nps,
            ease_of_use=ease,
            most_useful_feature=feature,
            biggest_pain_point=pain,
            would_recommend=recommend,
            open_feedback=quote,
            product_category_ratings=cat_ratings,
        ))

    _bulk_insert(surveys)


def _bulk_insert(surveys: List[FeedbackSurvey]):
    with get_conn() as conn:
        for s in surveys:
            conn.execute("""
                INSERT OR IGNORE INTO surveys VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                s.survey_id, s.partner_id, s.sent_at, s.responded_at,
                s.nps_score, s.ease_of_use, s.most_useful_feature,
                s.biggest_pain_point, int(s.would_recommend),
                s.open_feedback, json.dumps(s.product_category_ratings),
            ))
        conn.commit()


# ── Aggregation ───────────────────────────────────────────────────────────────

def _row_to_survey(row) -> dict:
    d = dict(row)
    d["product_category_ratings"] = json.loads(d.get("category_ratings") or "{}")
    d.pop("category_ratings", None)
    return d


def aggregate_feedback(surveys: List[dict]) -> dict:
    responded = [s for s in surveys if s.get("responded_at") and s.get("nps_score") is not None]
    total_sent = len(surveys)
    total_responded = len(responded)
    response_rate = round(total_responded / total_sent * 100, 1) if total_sent else 0.0

    promoters = sum(1 for s in responded if s["nps_score"] >= 9)
    detractors = sum(1 for s in responded if s["nps_score"] <= 6)
    nps = round((promoters - detractors) / total_responded * 100, 1) if total_responded else 0.0

    avg_ease = round(sum(s["ease_of_use"] for s in responded) / total_responded, 2) if total_responded else 0.0

    pain_counter = Counter(s["biggest_pain_point"] for s in responded if s.get("biggest_pain_point"))
    feature_counter = Counter(s["most_useful_feature"] for s in responded if s.get("most_useful_feature"))

    cat_totals: Dict[str, List[int]] = {}
    for s in responded:
        ratings = s.get("product_category_ratings") or {}
        for cat, val in ratings.items():
            cat_totals.setdefault(cat, []).append(val)
    category_averages = {cat: round(sum(vals) / len(vals), 2) for cat, vals in cat_totals.items()}

    return {
        "nps": nps,
        "promoters": promoters,
        "detractors": detractors,
        "passives": total_responded - promoters - detractors,
        "avg_ease_of_use": avg_ease,
        "top_pain_points": pain_counter.most_common(5),
        "top_features": feature_counter.most_common(5),
        "category_averages": category_averages,
        "response_rate": response_rate,
        "total_sent": total_sent,
        "total_responded": total_responded,
    }


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

def _build_dashboard(agg: dict, surveys: List[dict]) -> str:
    nps = agg["nps"]
    nps_color = "#10b981" if nps >= 50 else ("#f59e0b" if nps >= 20 else "#ef4444")

    # NPS gauge: SVG semi-circle, value mapped 0-100 → 0°-180°
    # semi-circle arc from 180° to 0° (left to right), needle at nps position
    import math
    needle_angle = 180 - (nps / 100) * 180  # degrees from positive x-axis
    needle_rad = math.radians(needle_angle)
    nx = 100 + 80 * math.cos(needle_rad)
    ny = 100 - 80 * math.sin(needle_rad)

    gauge_svg = f"""
<svg width="200" height="110" viewBox="0 0 200 110">
  <path d="M 10,100 A 90,90 0 0,1 190,100" fill="none" stroke="#ef4444" stroke-width="16" stroke-linecap="round"/>
  <path d="M 10,100 A 90,90 0 0,1 100,10" fill="none" stroke="#f59e0b" stroke-width="16" stroke-linecap="round"/>
  <path d="M 100,10 A 90,90 0 0,1 190,100" fill="none" stroke="#10b981" stroke-width="16" stroke-linecap="round"/>
  <line x1="100" y1="100" x2="{nx:.1f}" y2="{ny:.1f}" stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="100" cy="100" r="6" fill="white"/>
  <text x="100" y="88" text-anchor="middle" fill="{nps_color}" font-size="22" font-weight="bold">{nps:.0f}</text>
  <text x="10" y="112" fill="#94a3b8" font-size="10">0</text>
  <text x="188" y="112" text-anchor="end" fill="#94a3b8" font-size="10">100</text>
</svg>"""

    # Category heatmap: 5 cats × 5 partners
    cats = ["training_quality", "latency", "cost", "docs", "support"]
    cat_labels = ["Training", "Latency", "Cost", "Docs", "Support"]
    partner_map: Dict[str, Dict[str, List[int]]] = {pid: {c: [] for c in cats} for pid in PARTNER_IDS}
    for s in surveys:
        pid = s["partner_id"]
        if pid in partner_map:
            for cat, val in (s.get("product_category_ratings") or {}).items():
                if cat in partner_map[pid]:
                    partner_map[pid][cat].append(val)

    def cell_color(vals):
        if not vals:
            return "#374151", "—"
        avg = sum(vals) / len(vals)
        if avg >= 4.0:
            return "#065f46", f"{avg:.1f}"
        if avg >= 3.0:
            return "#92400e", f"{avg:.1f}"
        return "#7f1d1d", f"{avg:.1f}"

    heatmap_rows = ""
    for pid, pname in zip(PARTNER_IDS, PARTNERS):
        cells = ""
        for cat in cats:
            bg, label = cell_color(partner_map[pid][cat])
            cells += f"<td style='background:{bg};text-align:center;padding:8px;font-size:.85em;color:white'>{label}</td>"
        heatmap_rows += f"<tr><td style='padding:8px;color:#e2e8f0;font-size:.85em;white-space:nowrap'>{pname}</td>{cells}</tr>"

    # Pain point badges
    pain_badges = ""
    badge_colors = ["#7f1d1d", "#78350f", "#365314", "#1e3a5f", "#3b1f72"]
    for i, (pain, cnt) in enumerate(agg["top_pain_points"]):
        bg = badge_colors[i % len(badge_colors)]
        pain_badges += f"<span style='background:{bg};color:white;padding:5px 12px;border-radius:16px;margin:4px;display:inline-block;font-size:.82em'>{pain} <b>×{cnt}</b></span>"

    # Feature badges
    feat_badges = ""
    feat_colors = ["#064e3b", "#1e3a5f", "#3b1f72", "#4a1942", "#1c3d2e"]
    for i, (feat, cnt) in enumerate(agg["top_features"]):
        bg = feat_colors[i % len(feat_colors)]
        feat_badges += f"<span style='background:{bg};color:white;padding:5px 12px;border-radius:16px;margin:4px;display:inline-block;font-size:.82em'>{feat} <b>×{cnt}</b></span>"

    # Open feedback quotes (last 5 with responses)
    quotes_html = ""
    responded = [s for s in surveys if s.get("open_feedback") and s.get("responded_at")][-5:]
    for s in responded:
        pid = s["partner_id"]
        pname = PARTNERS[PARTNER_IDS.index(pid)] if pid in PARTNER_IDS else pid
        nps_val = s.get("nps_score", "?")
        quotes_html += f"""
<div style='background:#1e293b;border-left:3px solid #3b82f6;padding:12px 16px;margin:10px 0;border-radius:4px'>
  <p style='color:#e2e8f0;margin:0 0 6px;font-style:italic;font-size:.9em'>"{s['open_feedback']}"</p>
  <span style='color:#94a3b8;font-size:.78em'>{pname} — NPS {nps_val}</span>
</div>"""

    # Survey history table (most recent 10)
    table_rows = ""
    for s in reversed(surveys[-10:]):
        pid = s["partner_id"]
        pname = PARTNERS[PARTNER_IDS.index(pid)] if pid in PARTNER_IDS else pid
        nps_val = s.get("nps_score", "—")
        ease_val = s.get("ease_of_use", "—")
        responded_at = s.get("responded_at", "")[:10] if s.get("responded_at") else "Pending"
        nps_color_cell = "#10b981" if isinstance(nps_val, int) and nps_val >= 9 else (
            "#f59e0b" if isinstance(nps_val, int) and nps_val >= 7 else "#ef4444")
        table_rows += (
            f"<tr>"
            f"<td>{s['survey_id']}</td>"
            f"<td>{pname}</td>"
            f"<td>{s['sent_at'][:10]}</td>"
            f"<td>{responded_at}</td>"
            f"<td style='color:{nps_color_cell};font-weight:bold'>{nps_val}</td>"
            f"<td>{ease_val}</td>"
            f"<td style='font-size:.78em;color:#94a3b8'>{(s.get('biggest_pain_point') or '')[:40]}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Partner Feedback Tracker — OCI Robot Cloud</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px 32px}}
h1{{color:#C74634;margin:0 0 4px}} .subtitle{{color:#94a3b8;font-size:.9em;margin-bottom:24px}}
h2{{color:#94a3b8;font-size:.78em;text-transform:uppercase;letter-spacing:.12em;
border-bottom:1px solid #334155;padding-bottom:6px;margin:28px 0 12px}}
.grid{{display:grid;grid-template-columns:240px 1fr 1fr;gap:20px;margin-bottom:8px}}
.card{{background:#1e293b;border-radius:8px;padding:20px}}
.stat-val{{font-size:2em;font-weight:bold;color:#f1f5f9}}
.stat-label{{color:#94a3b8;font-size:.82em;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:.83em}}
th{{background:#1e293b;color:#94a3b8;padding:8px 10px;text-align:left;font-size:.78em;text-transform:uppercase;letter-spacing:.06em}}
td{{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:hover td{{background:#1e293b}}
.badge-area{{line-height:2}}
</style></head><body>
<h1>Partner Feedback Tracker</h1>
<p class="subtitle">OCI Robot Cloud — Customer Success &amp; Roadmap Intelligence &nbsp;|&nbsp; {agg['total_responded']}/{agg['total_sent']} responses ({agg['response_rate']}% rate)</p>

<div class="grid">
  <div class="card" style="text-align:center">
    <h2 style="margin-top:0">Net Promoter Score</h2>
    {gauge_svg}
    <div style="color:{nps_color};font-size:1.1em;font-weight:bold;margin-top:4px">
      {'Excellent' if nps >= 50 else ('Good' if nps >= 20 else 'Needs Work')}
    </div>
    <div style="color:#94a3b8;font-size:.8em;margin-top:8px">
      P {agg['promoters']} · N {agg['passives']} · D {agg['detractors']}
    </div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">Key Metrics</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div><div class="stat-val" style="color:{nps_color}">{nps:.0f}</div><div class="stat-label">NPS Score</div></div>
      <div><div class="stat-val">{agg['avg_ease_of_use']}</div><div class="stat-label">Avg Ease of Use (1-5)</div></div>
      <div><div class="stat-val">{agg['response_rate']}%</div><div class="stat-label">Response Rate</div></div>
      <div><div class="stat-val">{agg['category_averages'].get('cost','—')}</div><div class="stat-label">Cost Rating (1-5)</div></div>
    </div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">Category Averages</h2>
    {"".join(f'<div style="display:flex;justify-content:space-between;margin:6px 0"><span style="color:#94a3b8;font-size:.85em">{cat.replace("_"," ").title()}</span><span style="font-weight:bold;color:#f1f5f9">{val}</span></div>' for cat,val in agg["category_averages"].items())}
  </div>
</div>

<h2>Partner Category Ratings Heatmap</h2>
<div class="card" style="overflow-x:auto">
<table>
<tr><th>Partner</th>{"".join(f'<th style="text-align:center">{l}</th>' for l in cat_labels)}</tr>
{heatmap_rows}
</table>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:0">
  <div class="card">
    <h2 style="margin-top:0">Top Pain Points</h2>
    <div class="badge-area">{pain_badges if pain_badges else '<span style="color:#94a3b8">No data</span>'}</div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">Most Valued Features</h2>
    <div class="badge-area">{feat_badges if feat_badges else '<span style="color:#94a3b8">No data</span>'}</div>
  </div>
</div>

<h2>Partner Quotes</h2>
<div class="card">{quotes_html if quotes_html else '<p style="color:#94a3b8">No responses yet.</p>'}</div>

<h2>Survey History (recent 10)</h2>
<div class="card" style="overflow-x:auto">
<table>
<tr><th>ID</th><th>Partner</th><th>Sent</th><th>Responded</th><th>NPS</th><th>Ease</th><th>Pain Point</th></tr>
{table_rows}
</table>
</div>

<p style="color:#475569;font-size:.75em;margin-top:28px;text-align:center">
OCI Robot Cloud · github.com/qianjun22/roboticsai · Confidential — Partner Use Only
</p>
</body></html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="Partner Feedback Tracker", version="1.0.0")

    @app.on_event("startup")
    def startup():
        init_db()
        _seed_mock_data()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "partner_feedback_tracker", "port": 8046}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM surveys ORDER BY sent_at").fetchall()
        surveys = [_row_to_survey(r) for r in rows]
        agg = aggregate_feedback(surveys)
        return _build_dashboard(agg, surveys)

    @app.post("/api/survey")
    def ingest_survey(survey: dict):
        required = {"survey_id", "partner_id", "sent_at", "nps_score"}
        missing = required - set(survey.keys())
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
        cat_ratings = survey.get("product_category_ratings", {})
        with get_conn() as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO surveys VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    survey["survey_id"], survey["partner_id"], survey["sent_at"],
                    survey.get("responded_at"), survey["nps_score"],
                    survey.get("ease_of_use"), survey.get("most_useful_feature"),
                    survey.get("biggest_pain_point"), int(bool(survey.get("would_recommend"))),
                    survey.get("open_feedback"), json.dumps(cat_ratings),
                ))
                conn.commit()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        return {"status": "ok", "survey_id": survey["survey_id"]}

    @app.get("/api/surveys")
    def list_surveys(partner_id: Optional[str] = Query(None)):
        with get_conn() as conn:
            if partner_id:
                rows = conn.execute(
                    "SELECT * FROM surveys WHERE partner_id=? ORDER BY sent_at DESC", (partner_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM surveys ORDER BY sent_at DESC").fetchall()
        return [_row_to_survey(r) for r in rows]

    @app.get("/api/aggregate")
    def get_aggregate():
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM surveys").fetchall()
        surveys = [_row_to_survey(r) for r in rows]
        return aggregate_feedback(surveys)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Partner NPS & Feedback Tracker")
    parser.add_argument("--port", type=int, default=8046, help="Port (default 8046)")
    parser.add_argument("--mock", action="store_true", help="Seed mock data on startup")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("FastAPI not installed. Run: pip install fastapi uvicorn")
        return

    print(f"Partner Feedback Tracker starting on http://0.0.0.0:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
