#!/usr/bin/env python3
"""
revenue_dashboard.py — Executive Revenue & Growth Dashboard for OCI Robot Cloud.

Tracks MRR, ARR, customer pipeline, funnel metrics, cohort retention, and
6-month revenue forecast for the OCI Robot Cloud business. Designed for
weekly executive review and Oracle finance integration.

Business targets:
  - First $10k MRR by September 2026 (AI World)
  - $50k MRR by GTC 2027

Usage:
    python src/api/revenue_dashboard.py [--port 8056] [--db /tmp/revenue.db]

Endpoints:
    GET /           Executive dashboard (dark theme HTML)
    GET /metrics    Raw JSON metrics for Oracle finance integration
    GET /pipeline   Customer pipeline JSON
    GET /forecast   6-month revenue forecast JSON
    GET /health     Health check

No external deps beyond fastapi + uvicorn + sqlite3 (stdlib).
"""

import argparse
import json
import math
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8056
DEFAULT_DB = "/tmp/oci_revenue.db"

# Revenue targets (USD / month)
TARGET_AI_WORLD_MRR = 10_000   # September 2026
TARGET_GTC_MRR = 50_000        # GTC 2027

# Tier pricing (per month)
TIER_PRICING = {
    "starter":    {"price": 500,   "label": "Starter",    "color": "#60a5fa"},
    "growth":     {"price": 2_000, "label": "Growth",     "color": "#34d399"},
    "enterprise": {"price": 8_000, "label": "Enterprise", "color": "#f59e0b"},
}

# Pipeline stages and their default probabilities
STAGE_PROBABILITY = {
    "lead":      5,
    "qualified": 15,
    "demo":      30,
    "proposal":  50,
    "pilot":     70,
    "won":       100,
    "lost":      0,
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_path() -> str:
    return _db_path


@contextmanager
def db_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables and seed initial data if empty."""
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                company     TEXT NOT NULL,
                contact     TEXT NOT NULL,
                tier        TEXT NOT NULL DEFAULT 'starter',
                mrr         REAL NOT NULL DEFAULT 0,
                start_date  TEXT NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS pipeline (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                company      TEXT NOT NULL,
                contact      TEXT NOT NULL,
                stage        TEXT NOT NULL DEFAULT 'lead',
                probability  INTEGER NOT NULL DEFAULT 5,
                expected_mrr REAL NOT NULL DEFAULT 0,
                close_date   TEXT NOT NULL,
                notes        TEXT DEFAULT '',
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gpu_hours (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                month       TEXT NOT NULL,
                hours       REAL NOT NULL DEFAULT 0,
                UNIQUE(customer_id, month)
            );
        """)

        # Seed customers if empty
        count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if count == 0:
            _seed_data(conn)


def _seed_data(conn: sqlite3.Connection):
    """Seed realistic 6-month history for OCI Robot Cloud ramp."""

    # Won customers — active MRR contributors
    customers = [
        ("ACME Robotics",   "Sarah Chen",    "enterprise", 8000, "2025-10-01"),
        ("RoboLogix Inc",   "Marcus Webb",   "growth",     2000, "2025-11-15"),
        ("Delta Automation","Priya Sharma",  "starter",     500, "2025-12-01"),
    ]
    for company, contact, tier, mrr, start in customers:
        conn.execute(
            "INSERT INTO customers (company, contact, tier, mrr, start_date) VALUES (?,?,?,?,?)",
            (company, contact, tier, mrr, start),
        )

    # Pipeline prospects
    pipeline = [
        # company,              contact,          stage,     prob, exp_mrr, close_date,        notes
        ("ACME Robotics",       "Sarah Chen",    "won",      100,  8000,   "2025-10-01", "Enterprise contract signed; 3 A100 clusters"),
        ("AutoBot Inc",         "James Liu",     "pilot",     70,  4000,   "2026-04-30", "Piloting GR00T fine-tuning on warehouse pick-and-place"),
        ("Nexus Robotics",      "Elena Voss",    "proposal",  50,  2000,   "2026-05-15", "Growth tier; submitted SOW"),
        ("Atlas Manufacturing", "Raj Patel",     "demo",      30,  6000,   "2026-06-30", "Enterprise interest; live demo scheduled"),
        ("ClearPath Systems",   "Yuki Tanaka",   "qualified", 15,  2000,   "2026-07-31", "Inbound from AI World talk"),
        ("BotWorks Co",         "Chris Müller",  "lead",       5,   500,   "2026-08-31", "Cold outbound; initial interest"),
        ("Roboverse Labs",      "Anna Novak",    "lost",       0,  2000,   "2026-03-01", "Chose on-prem solution"),
    ]
    now = datetime.utcnow().isoformat()
    for row in pipeline:
        conn.execute(
            """INSERT INTO pipeline
               (company, contact, stage, probability, expected_mrr, close_date, notes, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (*row, now),
        )

    # GPU-hours per customer per month (proxy for retention / engagement)
    # customer_id 1 = ACME (enterprise), 2 = RoboLogix (growth), 3 = Delta (starter)
    gpu_history = [
        # (customer_id, YYYY-MM, hours)
        (1, "2025-10",  420), (1, "2025-11",  680), (1, "2025-12",  870),
        (1, "2026-01", 1140), (1, "2026-02", 1380), (1, "2026-03", 1520),
        (2, "2025-11",  110), (2, "2025-12",  240),
        (2, "2026-01",  390), (2, "2026-02",  450), (2, "2026-03",  480),
        (3, "2025-12",   45),
        (3, "2026-01",   72), (3, "2026-02",   88), (3, "2026-03",   95),
    ]
    for cid, month, hours in gpu_history:
        conn.execute(
            "INSERT OR IGNORE INTO gpu_hours (customer_id, month, hours) VALUES (?,?,?)",
            (cid, month, hours),
        )


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_metrics() -> dict:
    with db_conn() as conn:
        # Active customers
        customers = conn.execute(
            "SELECT * FROM customers WHERE active=1"
        ).fetchall()

        mrr = sum(r["mrr"] for r in customers)
        arr = mrr * 12
        acv = mrr / len(customers) if customers else 0

        # Revenue by tier
        by_tier = {"starter": 0.0, "growth": 0.0, "enterprise": 0.0}
        for r in customers:
            by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + r["mrr"]

        # Pipeline
        pipeline = conn.execute("SELECT * FROM pipeline").fetchall()
        stages = {s: {"count": 0, "weighted_mrr": 0.0} for s in STAGE_PROBABILITY}
        for row in pipeline:
            s = row["stage"]
            if s in stages:
                stages[s]["count"] += 1
                stages[s]["weighted_mrr"] += row["expected_mrr"] * row["probability"] / 100

        weighted_pipeline = sum(
            v["weighted_mrr"] for k, v in stages.items() if k not in ("won", "lost")
        )

        # 90-day forecast: active MRR + pipeline deals closing within 90 days
        cutoff = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")
        closing_soon = conn.execute(
            """SELECT expected_mrr, probability FROM pipeline
               WHERE stage NOT IN ('won','lost') AND close_date <= ?""",
            (cutoff,),
        ).fetchall()
        forecast_90d = mrr + sum(
            r["expected_mrr"] * r["probability"] / 100 for r in closing_soon
        )

        # Cohort retention: GPU hours per customer per month
        cohort_raw = conn.execute(
            """SELECT c.company, g.month, g.hours
               FROM gpu_hours g JOIN customers c ON c.id=g.customer_id
               ORDER BY c.id, g.month"""
        ).fetchall()
        cohort: dict[str, dict[str, float]] = {}
        for row in cohort_raw:
            cohort.setdefault(row["company"], {})[row["month"]] = row["hours"]

        # MRR history (seeded ramp — computed from first customer start dates)
        mrr_history = _compute_mrr_history(conn)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "mrr": mrr,
        "arr": arr,
        "acv": acv,
        "customer_count": len(customers),
        "revenue_by_tier": by_tier,
        "pipeline_stages": stages,
        "weighted_pipeline": weighted_pipeline,
        "forecast_90d": forecast_90d,
        "cohort": cohort,
        "mrr_history": mrr_history,
        "targets": {
            "ai_world_mrr": TARGET_AI_WORLD_MRR,
            "gtc_mrr": TARGET_GTC_MRR,
            "ai_world_date": "2026-09",
            "gtc_date": "2027-03",
        },
    }


def _compute_mrr_history(conn: sqlite3.Connection) -> list[dict]:
    """Build month-by-month MRR from customer start dates."""
    customers = conn.execute("SELECT mrr, start_date FROM customers WHERE active=1").fetchall()

    # Determine range: 2025-10 to current month
    start = datetime(2025, 10, 1)
    now = datetime.utcnow().replace(day=1)
    months = []
    cur = start
    while cur <= now:
        months.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    history = []
    for m in months:
        total = sum(
            r["mrr"] for r in customers
            if r["start_date"][:7] <= m
        )
        history.append({"month": m, "mrr": total})
    return history


def compute_forecast(mrr_history: list[dict]) -> list[dict]:
    """Linear + seasonal extrapolation for next 6 months."""
    if len(mrr_history) < 2:
        return []

    # Simple linear regression on last 4 data points
    n = min(4, len(mrr_history))
    recent = mrr_history[-n:]
    x_vals = list(range(n))
    y_vals = [r["mrr"] for r in recent]
    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
    den = sum((x - x_mean) ** 2 for x in x_vals)
    slope = num / den if den else 0

    last_month_str = mrr_history[-1]["month"]
    last_mrr = mrr_history[-1]["mrr"]
    year, month = map(int, last_month_str.split("-"))

    # Seasonal multipliers (slight dip in Q1, ramp in Q2-Q3 for AI trade shows)
    seasonal = {1: 0.97, 2: 0.98, 3: 1.00, 4: 1.03, 5: 1.05,
                6: 1.04, 7: 1.02, 8: 1.03, 9: 1.08, 10: 1.05, 11: 1.02, 12: 0.97}

    forecasts = []
    for i in range(1, 7):
        month += 1
        if month > 12:
            month = 1
            year += 1
        predicted = max(0, last_mrr + slope * (n + i - 1) * seasonal.get(month, 1.0))
        forecasts.append({
            "month": f"{year:04d}-{month:02d}",
            "mrr": round(predicted, 2),
            "type": "forecast",
        })
    return forecasts


# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------

def _mrr_svg(history: list[dict], forecast: list[dict]) -> str:
    """Render an SVG line chart of MRR history + forecast."""
    W, H, PAD = 700, 200, 40
    all_points = history + forecast
    if not all_points:
        return ""

    values = [p["mrr"] for p in all_points]
    max_v = max(values) * 1.2 or TARGET_AI_WORLD_MRR
    min_v = 0

    def sx(i: int) -> float:
        return PAD + (i / (len(all_points) - 1)) * (W - 2 * PAD) if len(all_points) > 1 else W / 2

    def sy(v: float) -> float:
        return H - PAD - ((v - min_v) / (max_v - min_v)) * (H - 2 * PAD)

    # Build history polyline
    hist_pts = " ".join(f"{sx(i):.1f},{sy(p['mrr']):.1f}" for i, p in enumerate(history))
    # Build forecast polyline (starts where history ends)
    fc_pts_list = []
    offset = len(history) - 1
    for j, p in enumerate(forecast):
        fc_pts_list.append(f"{sx(offset + j):.1f},{sy(p['mrr']):.1f}")
    fc_pts = " ".join(fc_pts_list)

    # Target line at $10k
    target_y = sy(TARGET_AI_WORLD_MRR)
    target50_y = sy(TARGET_GTC_MRR) if TARGET_GTC_MRR <= max_v else None

    # X-axis labels (every other month)
    labels = []
    for i, p in enumerate(all_points):
        if i % 2 == 0:
            lx = sx(i)
            labels.append(
                f'<text x="{lx:.1f}" y="{H - 5}" fill="#94a3b8" font-size="9" text-anchor="middle">{p["month"][2:]}</text>'
            )

    # Y-axis labels
    y_ticks = []
    for tick in [0, 5000, 10000, 25000, 50000]:
        if tick <= max_v:
            ty = sy(tick)
            label = f"${tick//1000}k" if tick > 0 else "$0"
            y_ticks.append(
                f'<text x="{PAD - 5}" y="{ty:.1f}" fill="#64748b" font-size="8" text-anchor="end" dominant-baseline="middle">{label}</text>'
            )
            y_ticks.append(
                f'<line x1="{PAD}" y1="{ty:.1f}" x2="{W - PAD}" y2="{ty:.1f}" stroke="#1e293b" stroke-width="1"/>'
            )

    target_line = (
        f'<line x1="{PAD}" y1="{target_y:.1f}" x2="{W - PAD}" y2="{target_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="{W - PAD + 4}" y="{target_y:.1f}" fill="#f59e0b" font-size="8" dominant-baseline="middle">$10k</text>'
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  {"".join(y_ticks)}
  {target_line}
  <polyline points="{hist_pts}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linejoin="round"/>
  {"<polyline points=\"" + " ".join([f"{sx(len(history)-1):.1f},{sy(history[-1]['mrr']):.1f}", fc_pts]) + "\" fill=\"none\" stroke=\"#34d399\" stroke-width=\"2\" stroke-dasharray=\"5,3\" stroke-linejoin=\"round\"/>" if fc_pts else ""}
  {"".join(labels)}
  <text x="{PAD}" y="12" fill="#94a3b8" font-size="9">MRR ($USD)</text>
  <text x="{W - PAD}" y="{H - PAD - 8}" fill="#34d399" font-size="8" text-anchor="end">-- forecast</text>
  <text x="{W - PAD}" y="{H - PAD - 18}" fill="#3b82f6" font-size="8" text-anchor="end">— actual</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _gauge_svg(value: float, target: float, label: str, color: str = "#3b82f6") -> str:
    """Semi-circle gauge for MRR vs target."""
    pct = min(value / target, 1.0) if target else 0
    angle = pct * 180  # 0 → 180 degrees (semi-circle)
    r, cx, cy = 60, 80, 80
    stroke_w = 14

    def polar(deg: float):
        rad = math.radians(180 - deg)
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    x0, y0 = polar(0)
    x1, y1 = polar(angle)
    large = 1 if angle > 90 else 0

    track = f'<path d="M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}" fill="none" stroke="#1e293b" stroke-width="{stroke_w}" stroke-linecap="round"/>'
    arc = f'<path d="M {cx - r} {cy} A {r} {r} 0 {large} 1 {x1:.2f} {y1:.2f}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round"/>' if angle > 0 else ""
    pct_label = f"${value:,.0f}" if value < 10000 else f"${value/1000:.1f}k"

    return f"""<svg width="160" height="95" xmlns="http://www.w3.org/2000/svg">
  {track}
  {arc}
  <text x="{cx}" y="{cy - 2}" fill="white" font-size="16" font-weight="bold" text-anchor="middle" font-family="monospace">{pct_label}</text>
  <text x="{cx}" y="{cy + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>
  <text x="{cx}" y="{cy + 26}" fill="{color}" font-size="8" text-anchor="middle">{pct*100:.0f}% of ${target//1000}k target</text>
</svg>"""


def _pipeline_kanban(stages_data: dict, pipeline_rows: list) -> str:
    """HTML Kanban board for pipeline stages."""
    active_stages = ["lead", "qualified", "demo", "proposal", "pilot"]
    stage_colors = {
        "lead": "#475569", "qualified": "#2563eb", "demo": "#7c3aed",
        "proposal": "#b45309", "pilot": "#065f46", "won": "#166534", "lost": "#7f1d1d",
    }

    cols = []
    for stage in active_stages:
        color = stage_colors.get(stage, "#475569")
        deals = [r for r in pipeline_rows if r["stage"] == stage]
        cards = []
        for d in deals:
            weighted = d["expected_mrr"] * d["probability"] / 100
            cards.append(f"""
              <div style="background:#1e293b;border-radius:6px;padding:10px;margin-bottom:8px;border-left:3px solid {color}">
                <div style="font-weight:600;font-size:13px;color:#e2e8f0">{d['company']}</div>
                <div style="color:#94a3b8;font-size:11px;margin-top:2px">{d['contact']}</div>
                <div style="display:flex;justify-content:space-between;margin-top:6px">
                  <span style="color:#34d399;font-size:12px">${d['expected_mrr']:,.0f}/mo</span>
                  <span style="color:#94a3b8;font-size:11px">{d['probability']}% • ${weighted:,.0f}</span>
                </div>
                <div style="color:#64748b;font-size:10px;margin-top:3px">Close: {d['close_date']}</div>
              </div>""")
        count = stages_data.get(stage, {}).get("count", 0)
        w_mrr = stages_data.get(stage, {}).get("weighted_mrr", 0)
        cols.append(f"""
          <div style="flex:1;min-width:160px;max-width:200px">
            <div style="background:{color};border-radius:6px 6px 0 0;padding:8px 10px;display:flex;justify-content:space-between;align-items:center">
              <span style="font-weight:600;font-size:12px;text-transform:uppercase;color:white">{stage}</span>
              <span style="background:rgba(255,255,255,0.2);border-radius:10px;padding:1px 7px;font-size:11px;color:white">{count}</span>
            </div>
            <div style="background:#0f172a;border-radius:0 0 6px 6px;padding:8px;min-height:80px">
              {"".join(cards) if cards else '<div style="color:#334155;font-size:11px;text-align:center;padding:20px 0">No deals</div>'}
              <div style="color:#475569;font-size:10px;text-align:right;margin-top:4px">Weighted: ${w_mrr:,.0f}</div>
            </div>
          </div>""")

    return f'<div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:8px">{"".join(cols)}</div>'


def _cohort_table(cohort: dict) -> str:
    """HTML table for cohort GPU-hours retention."""
    if not cohort:
        return "<p style='color:#64748b'>No cohort data.</p>"

    # Collect all months
    all_months: set[str] = set()
    for hours in cohort.values():
        all_months.update(hours.keys())
    months = sorted(all_months)

    header_cells = "".join(f"<th>{m[2:]}</th>" for m in months)
    rows = []
    for company, month_hours in cohort.items():
        cells = []
        prev = None
        for m in months:
            h = month_hours.get(m)
            if h is None:
                cells.append('<td style="color:#334155">—</td>')
            else:
                delta = ""
                color = "#94a3b8"
                if prev is not None:
                    if h > prev:
                        delta = f" ▲"
                        color = "#34d399"
                    elif h < prev:
                        delta = f" ▼"
                        color = "#f87171"
                cells.append(f'<td style="color:{color}">{h:.0f}h{delta}</td>')
                prev = h
        rows.append(f"<tr><td style='color:#e2e8f0;font-weight:600'>{company}</td>{''.join(cells)}</tr>")

    return f"""<table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead>
        <tr style="color:#64748b;border-bottom:1px solid #1e293b">
          <th style="text-align:left;padding:6px">Customer</th>{header_cells}
        </tr>
      </thead>
      <tbody style="color:#94a3b8">
        {"".join(rows)}
      </tbody>
    </table>"""


def render_dashboard(metrics: dict, pipeline_rows: list) -> str:
    mrr = metrics["mrr"]
    arr = metrics["arr"]
    acv = metrics["acv"]
    n = metrics["customer_count"]
    by_tier = metrics["revenue_by_tier"]
    stages = metrics["pipeline_stages"]
    weighted = metrics["weighted_pipeline"]
    f90 = metrics["forecast_90d"]
    cohort = metrics["cohort"]
    history = metrics["mrr_history"]
    targets = metrics["targets"]

    forecast = compute_forecast(history)
    svg_chart = _mrr_svg(history, forecast)

    # Progress to $10k target
    pct_ai_world = min(mrr / TARGET_AI_WORLD_MRR * 100, 100)

    # Tier breakdown bars
    tier_bars = ""
    max_tier = max(by_tier.values()) or 1
    for tier, val in sorted(by_tier.items(), key=lambda x: -x[1]):
        cfg = TIER_PRICING[tier]
        w = val / max_tier * 100
        tier_bars += f"""
          <div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
              <span style="color:{cfg['color']};font-size:12px;font-weight:600">{cfg['label']}</span>
              <span style="color:#e2e8f0;font-size:12px">${val:,.0f}/mo</span>
            </div>
            <div style="background:#1e293b;border-radius:4px;height:8px">
              <div style="background:{cfg['color']};width:{w:.1f}%;height:8px;border-radius:4px"></div>
            </div>
          </div>"""

    kanban_html = _pipeline_kanban(stages, pipeline_rows)
    cohort_html = _cohort_table(cohort)

    gauge_ai = _gauge_svg(mrr, TARGET_AI_WORLD_MRR, "AI World Target (Sep '26)", "#3b82f6")
    gauge_gtc = _gauge_svg(mrr, TARGET_GTC_MRR, "GTC Target (Mar '27)", "#f59e0b")

    # Forecast table
    fc_rows = ""
    for p in forecast:
        fc_rows += f"""<tr>
          <td style="color:#94a3b8">{p['month']}</td>
          <td style="color:#34d399;text-align:right">${p['mrr']:,.0f}</td>
          <td style="color:#64748b;text-align:right">${p['mrr']*12:,.0f}</td>
        </tr>"""

    ts = metrics["timestamp"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Revenue Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #020617; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); padding: 20px 32px; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; align-items: center; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #f8fafc; letter-spacing: -0.5px; }}
    .header .subtitle {{ color: #64748b; font-size: 12px; margin-top: 2px; }}
    .header .ts {{ color: #475569; font-size: 11px; text-align: right; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; padding: 24px 32px 0; }}
    .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; }}
    .card .label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
    .card .value {{ font-size: 24px; font-weight: 700; color: #f8fafc; font-variant-numeric: tabular-nums; }}
    .card .sub {{ color: #475569; font-size: 11px; margin-top: 4px; }}
    .section {{ padding: 20px 32px; }}
    .section h2 {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .three-col {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }}
    .panel {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 18px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ color: #64748b; text-align: left; padding: 6px 8px; border-bottom: 1px solid #1e293b; font-weight: 500; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #0f172a; }}
    .progress-bar {{ background: #1e293b; border-radius: 6px; height: 10px; margin-top: 6px; }}
    .progress-fill {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 6px; height: 10px; transition: width 0.5s; }}
    .footer {{ padding: 16px 32px; color: #334155; font-size: 11px; text-align: center; border-top: 1px solid #0f172a; margin-top: 20px; }}
  </style>
</head>
<body>

<div class="header">
  <div>
    <h1>OCI Robot Cloud — Revenue Dashboard</h1>
    <div class="subtitle">Executive view · MRR, Pipeline, Forecast · Confidential</div>
  </div>
  <div class="ts">Updated: {ts[:19].replace('T',' ')} UTC<br/>Port 8056</div>
</div>

<!-- KPI Cards -->
<div class="grid">
  <div class="card">
    <div class="label">MRR</div>
    <div class="value" style="color:#3b82f6">${mrr:,.0f}</div>
    <div class="sub">Monthly Recurring Revenue</div>
  </div>
  <div class="card">
    <div class="label">ARR</div>
    <div class="value" style="color:#34d399">${arr:,.0f}</div>
    <div class="sub">Annual Run Rate</div>
  </div>
  <div class="card">
    <div class="label">Avg Contract Value</div>
    <div class="value" style="color:#f59e0b">${acv:,.0f}</div>
    <div class="sub">Per customer / month</div>
  </div>
  <div class="card">
    <div class="label">Active Customers</div>
    <div class="value" style="color:#a78bfa">{n}</div>
    <div class="sub">Live contracts</div>
  </div>
  <div class="card">
    <div class="label">Weighted Pipeline</div>
    <div class="value" style="color:#fb923c">${weighted:,.0f}</div>
    <div class="sub">Probability-adjusted</div>
  </div>
  <div class="card">
    <div class="label">90-Day Forecast</div>
    <div class="value" style="color:#38bdf8">${f90:,.0f}</div>
    <div class="sub">MRR in 90 days</div>
  </div>
</div>

<!-- Targets & Tier Breakdown -->
<div class="section">
  <div class="two-col">
    <div class="panel">
      <h2>Business Targets</h2>
      <div style="display:flex;gap:16px;justify-content:center;margin-bottom:16px">
        {gauge_ai}
        {gauge_gtc}
      </div>
      <div style="margin-top:8px">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;margin-bottom:4px">
          <span>AI World (Sep '26): ${TARGET_AI_WORLD_MRR:,}/mo</span>
          <span style="color:#3b82f6">{pct_ai_world:.0f}%</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:{pct_ai_world:.1f}%"></div></div>
      </div>
    </div>
    <div class="panel">
      <h2>Revenue by Tier</h2>
      {tier_bars}
      <div style="color:#475569;font-size:11px;margin-top:12px;border-top:1px solid #1e293b;padding-top:10px">
        <div>Starter: $500/mo &nbsp;·&nbsp; Growth: $2,000/mo &nbsp;·&nbsp; Enterprise: $8,000/mo</div>
      </div>
    </div>
  </div>
</div>

<!-- MRR Chart -->
<div class="section">
  <div class="panel">
    <h2>MRR Trend & 6-Month Forecast</h2>
    <div style="overflow-x:auto">{svg_chart}</div>
    <div style="display:flex;gap:24px;margin-top:10px">
      <span style="color:#3b82f6;font-size:12px">— Actual MRR</span>
      <span style="color:#34d399;font-size:12px">-- Forecast</span>
      <span style="color:#f59e0b;font-size:12px">--- $10k AI World target</span>
    </div>
  </div>
</div>

<!-- Pipeline Kanban -->
<div class="section">
  <div class="panel">
    <h2>Customer Pipeline</h2>
    {kanban_html}
  </div>
</div>

<!-- Forecast Table + Cohort Retention -->
<div class="section">
  <div class="two-col">
    <div class="panel">
      <h2>6-Month Revenue Forecast</h2>
      <table>
        <thead><tr><th>Month</th><th style="text-align:right">MRR</th><th style="text-align:right">ARR Run Rate</th></tr></thead>
        <tbody>{fc_rows}</tbody>
      </table>
      <div style="color:#475569;font-size:10px;margin-top:10px">Linear extrapolation with seasonal adjustment. Does not include new pipeline deals.</div>
    </div>
    <div class="panel">
      <h2>Cohort Retention (GPU-Hours / Month)</h2>
      {cohort_html}
      <div style="color:#475569;font-size:10px;margin-top:10px">GPU-hours used per customer as engagement proxy. ▲ growth &nbsp;▼ churn risk.</div>
    </div>
  </div>
</div>

<div class="footer">
  OCI Robot Cloud — Confidential &nbsp;·&nbsp; Data as of {ts[:10]} &nbsp;·&nbsp;
  <a href="/metrics" style="color:#3b82f6;text-decoration:none">/metrics JSON</a> &nbsp;·&nbsp;
  <a href="/pipeline" style="color:#3b82f6;text-decoration:none">/pipeline JSON</a> &nbsp;·&nbsp;
  <a href="/forecast" style="color:#3b82f6;text-decoration:none">/forecast JSON</a>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud Revenue Dashboard",
    description="Executive revenue, pipeline, and growth tracking",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse, summary="Executive HTML dashboard")
def dashboard():
    metrics = compute_metrics()
    with db_conn() as conn:
        pipeline_rows = [dict(r) for r in conn.execute("SELECT * FROM pipeline ORDER BY probability DESC").fetchall()]
    html = render_dashboard(metrics, pipeline_rows)
    return HTMLResponse(content=html)


@app.get("/metrics", summary="Raw JSON metrics for Oracle finance integration")
def metrics_json():
    return JSONResponse(compute_metrics())


@app.get("/pipeline", summary="Customer pipeline JSON")
def pipeline_json():
    with db_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM pipeline ORDER BY close_date").fetchall()]
    return JSONResponse({"pipeline": rows, "count": len(rows)})


@app.get("/forecast", summary="6-month MRR forecast JSON")
def forecast_json():
    metrics = compute_metrics()
    fc = compute_forecast(metrics["mrr_history"])
    return JSONResponse({
        "history": metrics["mrr_history"],
        "forecast": fc,
        "current_mrr": metrics["mrr"],
        "targets": metrics["targets"],
    })


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "service": "revenue_dashboard", "port": DEFAULT_PORT, "ts": datetime.utcnow().isoformat() + "Z"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _db_path
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Revenue Dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port (default 8056)")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default {DEFAULT_DB})")
    args = parser.parse_args()
    _db_path = args.db

    init_db()
    print(f"Revenue Dashboard running on http://0.0.0.0:{args.port}")
    print(f"  SQLite DB : {args.db}")
    print(f"  Dashboard : http://localhost:{args.port}/")
    print(f"  Metrics   : http://localhost:{args.port}/metrics")
    print(f"  Pipeline  : http://localhost:{args.port}/pipeline")
    print(f"  Forecast  : http://localhost:{args.port}/forecast")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


# Module-level DB path (set at startup or for tests)
_db_path = DEFAULT_DB

if __name__ == "__main__":
    main()
