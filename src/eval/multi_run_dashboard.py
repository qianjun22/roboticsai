#!/usr/bin/env python3
"""
multi_run_dashboard.py — Multi-run evaluation aggregator dashboard (port 8040).

Ingests results from BC, DAgger iterations, and different checkpoints, then
generates a unified comparison dashboard for GTC talk preparation.

Usage:
    python src/eval/multi_run_dashboard.py --mock
    python src/eval/multi_run_dashboard.py --port 8040 --host 0.0.0.0
"""

import argparse
import csv
import io
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class EvalRun:
    run_id: str
    checkpoint_path: str
    training_method: str        # "BC", "DAgger", "Curriculum"
    n_demos: int
    n_steps: int
    success_rate: float         # 0–100
    mae: float
    avg_latency_ms: float
    p95_latency_ms: float
    n_episodes: int
    eval_date: str              # ISO date string
    notes: str
    color_hint: str             # CSS color hint for badges

# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_RUNS: List[EvalRun] = [
    EvalRun(
        run_id="bc_500demo",
        checkpoint_path="/tmp/checkpoints/bc_500demo/step_2000",
        training_method="BC",
        n_demos=500,
        n_steps=2000,
        success_rate=5.0,
        mae=0.015,
        avg_latency_ms=231.0,
        p95_latency_ms=268.0,
        n_episodes=20,
        eval_date="2026-01-15",
        notes="Baseline BC with 500 demos",
        color_hint="#6366f1",
    ),
    EvalRun(
        run_id="bc_1000demo",
        checkpoint_path="/tmp/checkpoints/bc_1000demo/step_5000",
        training_method="BC",
        n_demos=1000,
        n_steps=5000,
        success_rate=5.0,
        mae=0.013,
        avg_latency_ms=226.0,
        p95_latency_ms=261.0,
        n_episodes=20,
        eval_date="2026-01-28",
        notes="BC with 1000 demos — MAE improved, success unchanged",
        color_hint="#6366f1",
    ),
    EvalRun(
        run_id="dagger_run3_iter1",
        checkpoint_path="/tmp/checkpoints/dagger_run3/iter1",
        training_method="DAgger",
        n_demos=1000,
        n_steps=1000,
        success_rate=12.0,
        mae=0.012,
        avg_latency_ms=228.0,
        p95_latency_ms=263.0,
        n_episodes=20,
        eval_date="2026-02-05",
        notes="DAgger run3 iteration 1 — first interactive signal",
        color_hint="#f59e0b",
    ),
    EvalRun(
        run_id="dagger_run3_iter3",
        checkpoint_path="/tmp/checkpoints/dagger_run3/iter3",
        training_method="DAgger",
        n_demos=1000,
        n_steps=3000,
        success_rate=22.0,
        mae=0.011,
        avg_latency_ms=227.0,
        p95_latency_ms=259.0,
        n_episodes=20,
        eval_date="2026-02-12",
        notes="DAgger run3 iteration 3 — consistent improvement",
        color_hint="#f59e0b",
    ),
    EvalRun(
        run_id="dagger_run4_iter1",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter1",
        training_method="DAgger",
        n_demos=1000,
        n_steps=2000,
        success_rate=30.0,
        mae=0.012,
        avg_latency_ms=229.0,
        p95_latency_ms=264.0,
        n_episodes=20,
        eval_date="2026-02-20",
        notes="DAgger run4 iteration 1 — improved expert policy",
        color_hint="#f59e0b",
    ),
    EvalRun(
        run_id="dagger_run4_iter3",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter3",
        training_method="DAgger",
        n_demos=1000,
        n_steps=5000,
        success_rate=65.0,
        mae=0.011,
        avg_latency_ms=226.0,
        p95_latency_ms=258.0,
        n_episodes=20,
        eval_date="2026-03-01",
        notes="DAgger run4 iteration 3 — breakthrough result",
        color_hint="#f59e0b",
    ),
    EvalRun(
        run_id="dagger_run5",
        checkpoint_path="/tmp/checkpoints/dagger_run5/final",
        training_method="DAgger",
        n_demos=99,
        n_steps=5000,
        success_rate=5.0,
        mae=0.013,
        avg_latency_ms=229.0,
        p95_latency_ms=265.0,
        n_episodes=20,
        eval_date="2026-03-10",
        notes="DAgger run5 — diluted signal, too few demos (99 vs 1000)",
        color_hint="#ef4444",
    ),
    EvalRun(
        run_id="curriculum_projected",
        checkpoint_path="/tmp/checkpoints/curriculum/projected",
        training_method="Curriculum",
        n_demos=2000,
        n_steps=10000,
        success_rate=72.0,
        mae=0.009,
        avg_latency_ms=224.0,
        p95_latency_ms=252.0,
        n_episodes=0,
        eval_date="2026-04-15",
        notes="Projected: curriculum SDG + DAgger — not yet evaluated",
        color_hint="#10b981",
    ),
]

# ── SQLite helpers ─────────────────────────────────────────────────────────────

DB_PATH = "/tmp/eval_dashboard.db"

def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            run_id TEXT PRIMARY KEY,
            checkpoint_path TEXT,
            training_method TEXT,
            n_demos INTEGER,
            n_steps INTEGER,
            success_rate REAL,
            mae REAL,
            avg_latency_ms REAL,
            p95_latency_ms REAL,
            n_episodes INTEGER,
            eval_date TEXT,
            notes TEXT,
            color_hint TEXT
        )
    """)
    conn.commit()
    return conn


def seed_mock(conn: sqlite3.Connection) -> None:
    for run in MOCK_RUNS:
        conn.execute(
            """INSERT OR IGNORE INTO eval_runs VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run.run_id, run.checkpoint_path, run.training_method,
                run.n_demos, run.n_steps, run.success_rate, run.mae,
                run.avg_latency_ms, run.p95_latency_ms, run.n_episodes,
                run.eval_date, run.notes, run.color_hint,
            ),
        )
    conn.commit()


def fetch_runs(conn: sqlite3.Connection) -> List[EvalRun]:
    rows = conn.execute("SELECT * FROM eval_runs ORDER BY eval_date, run_id").fetchall()
    cols = [
        "run_id", "checkpoint_path", "training_method", "n_demos", "n_steps",
        "success_rate", "mae", "avg_latency_ms", "p95_latency_ms", "n_episodes",
        "eval_date", "notes", "color_hint",
    ]
    return [EvalRun(**dict(zip(cols, row))) for row in rows]


def insert_run(conn: sqlite3.Connection, run: EvalRun) -> None:
    d = asdict(run)
    conn.execute(
        """INSERT OR REPLACE INTO eval_runs VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(d.values()),
    )
    conn.commit()

# ── SVG chart helpers ──────────────────────────────────────────────────────────

_ESTIMATED_COST = {
    "bc_500demo": 0.86,
    "bc_1000demo": 2.15,
    "dagger_run3_iter1": 2.58,
    "dagger_run3_iter3": 3.44,
    "dagger_run4_iter1": 3.01,
    "dagger_run4_iter3": 4.72,
    "dagger_run5": 1.29,
    "curriculum_projected": 8.60,
}


def _cost(run: EvalRun) -> float:
    return _ESTIMATED_COST.get(run.run_id, run.n_steps * run.n_demos / 10_000_000 * 43.0)


def plot_progress_svg(runs: List[EvalRun], w: int = 760, h: int = 280) -> str:
    pad = {"l": 60, "r": 30, "t": 30, "b": 60}
    iw = w - pad["l"] - pad["r"]
    ih = h - pad["t"] - pad["b"]
    n = len(runs)

    def xi(i: int) -> float:
        return pad["l"] + (i / max(n - 1, 1)) * iw

    def yi(v: float) -> float:
        return pad["t"] + ih - (v / 100.0) * ih

    # Gridlines
    grid_lines = ""
    for pct in [0, 25, 50, 75, 100]:
        y = yi(pct)
        grid_lines += (
            f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{w - pad["r"]}" y2="{y:.1f}" '
            f'stroke="#374151" stroke-width="1"/>'
            f'<text x="{pad["l"] - 6}" y="{y + 4:.1f}" fill="#9CA3AF" font-size="11" '
            f'text-anchor="end">{pct}%</text>'
        )

    # Split real vs projected
    real_pts = [(i, r) for i, r in enumerate(runs) if r.n_episodes > 0]
    proj_pts = [(i, r) for i, r in enumerate(runs) if r.n_episodes == 0]

    real_poly = " ".join(f"{xi(i):.1f},{yi(r.success_rate):.1f}" for i, r in real_pts)
    proj_poly = " ".join(f"{xi(i):.1f},{yi(r.success_rate):.1f}" for i, r in proj_pts)

    # Connect last real to first projected with dashed bridge
    bridge = ""
    if real_pts and proj_pts:
        last_i, last_r = real_pts[-1]
        first_i, first_r = proj_pts[0]
        bridge = (
            f'<line x1="{xi(last_i):.1f}" y1="{yi(last_r.success_rate):.1f}" '
            f'x2="{xi(first_i):.1f}" y2="{yi(first_r.success_rate):.1f}" '
            f'stroke="#10b981" stroke-width="2" stroke-dasharray="6,4" opacity="0.7"/>'
        )

    polylines = ""
    if real_poly:
        polylines += (
            f'<polyline points="{real_poly}" fill="none" stroke="#60a5fa" '
            f'stroke-width="2.5" stroke-linejoin="round"/>'
        )
    if proj_poly:
        polylines += (
            f'<polyline points="{proj_poly}" fill="none" stroke="#10b981" '
            f'stroke-width="2.5" stroke-dasharray="8,5" stroke-linejoin="round"/>'
        )

    # Dots + labels
    dots = ""
    for i, run in enumerate(runs):
        cx, cy = xi(i), yi(run.success_rate)
        color = run.color_hint or "#60a5fa"
        is_proj = run.n_episodes == 0
        fill = "none" if is_proj else color
        dots += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{fill}" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{cx:.1f}" y="{cy - 9:.1f}" fill="{color}" font-size="10" '
            f'text-anchor="middle">{run.success_rate:.0f}%</text>'
        )

    # X-axis labels
    x_labels = ""
    for i, run in enumerate(runs):
        x_labels += (
            f'<text x="{xi(i):.1f}" y="{h - pad["b"] + 18}" fill="#9CA3AF" '
            f'font-size="9" text-anchor="middle" transform="rotate(-30,{xi(i):.1f},'
            f'{h - pad["b"] + 18})">{run.run_id}</text>'
        )

    # DAgger start annotation
    dagger_idx = next((i for i, r in enumerate(runs) if r.training_method == "DAgger"), None)
    annotation = ""
    if dagger_idx is not None:
        ax = xi(dagger_idx)
        annotation = (
            f'<line x1="{ax:.1f}" y1="{pad["t"]}" x2="{ax:.1f}" y2="{h - pad["b"]}" '
            f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.6"/>'
            f'<text x="{ax + 4:.1f}" y="{pad["t"] + 12}" fill="#f59e0b" font-size="10">'
            f'DAgger start</text>'
        )

    title = (
        f'<text x="{w // 2}" y="16" fill="#e5e7eb" font-size="13" '
        f'font-weight="bold" text-anchor="middle">Success Rate vs Run</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#1f2937;border-radius:8px">'
        f'{title}{grid_lines}{annotation}{polylines}{bridge}{dots}{x_labels}'
        f'</svg>'
    )


def plot_latency_bar(runs: List[EvalRun], w: int = 760, h: int = 260) -> str:
    pad = {"l": 150, "r": 30, "t": 30, "b": 40}
    iw = w - pad["l"] - pad["r"]
    n = len(runs)
    bar_h = max(6, (h - pad["t"] - pad["b"]) // (n * 2 + 1))
    spacing = bar_h * 2 + 4

    max_lat = max((r.p95_latency_ms for r in runs), default=300)
    scale = iw / (max_lat * 1.05)

    bars = ""
    for i, run in enumerate(runs):
        y_base = pad["t"] + i * spacing
        avg_w = run.avg_latency_ms * scale
        p95_w = run.p95_latency_ms * scale
        color = run.color_hint or "#60a5fa"
        bars += (
            f'<rect x="{pad["l"]}" y="{y_base}" width="{avg_w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="2" opacity="0.9"/>'
            f'<rect x="{pad["l"]}" y="{y_base + bar_h + 2}" width="{p95_w:.1f}" '
            f'height="{bar_h}" fill="{color}" rx="2" opacity="0.5"/>'
            f'<text x="{pad["l"] - 4}" y="{y_base + bar_h:.1f}" fill="#d1d5db" '
            f'font-size="9.5" text-anchor="end">{run.run_id}</text>'
            f'<text x="{pad["l"] + avg_w + 3:.1f}" y="{y_base + bar_h:.1f}" '
            f'fill="{color}" font-size="9">{run.avg_latency_ms:.0f}ms</text>'
            f'<text x="{pad["l"] + p95_w + 3:.1f}" y="{y_base + bar_h * 2 + 2:.1f}" '
            f'fill="{color}" font-size="9" opacity="0.7">p95:{run.p95_latency_ms:.0f}ms</text>'
        )

    legend = (
        f'<rect x="{pad["l"]}" y="{h - 22}" width="12" height="8" fill="#60a5fa" rx="1"/>'
        f'<text x="{pad["l"] + 15}" y="{h - 14}" fill="#9CA3AF" font-size="10">avg</text>'
        f'<rect x="{pad["l"] + 45}" y="{h - 22}" width="12" height="8" fill="#60a5fa" '
        f'opacity="0.5" rx="1"/>'
        f'<text x="{pad["l"] + 60}" y="{h - 14}" fill="#9CA3AF" font-size="10">p95</text>'
    )
    title = (
        f'<text x="{w // 2}" y="16" fill="#e5e7eb" font-size="13" '
        f'font-weight="bold" text-anchor="middle">Inference Latency per Run</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#1f2937;border-radius:8px">'
        f'{title}{bars}{legend}</svg>'
    )


def plot_cost_scatter(runs: List[EvalRun], w: int = 760, h: int = 280) -> str:
    pad = {"l": 60, "r": 30, "t": 30, "b": 50}
    iw = w - pad["l"] - pad["r"]
    ih = h - pad["t"] - pad["b"]

    costs = [_cost(r) for r in runs]
    max_cost = max(costs) * 1.1 if costs else 1
    max_demos = max(r.n_demos for r in runs) if runs else 1

    def cx(c: float) -> float:
        return pad["l"] + (c / max_cost) * iw

    def cy(sr: float) -> float:
        return pad["t"] + ih - (sr / 100.0) * ih

    # Grid
    grid = ""
    for pct in [0, 25, 50, 75, 100]:
        y = cy(pct)
        grid += (
            f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{w - pad["r"]}" y2="{y:.1f}" '
            f'stroke="#374151" stroke-width="1"/>'
            f'<text x="{pad["l"] - 6}" y="{y + 4:.1f}" fill="#9CA3AF" font-size="10" '
            f'text-anchor="end">{pct}%</text>'
        )

    bubbles = ""
    for i, (run, cost) in enumerate(zip(runs, costs)):
        r = 5 + (run.n_demos / max_demos) * 18
        x, y = cx(cost), cy(run.success_rate)
        color = run.color_hint or "#60a5fa"
        is_proj = run.n_episodes == 0
        fill = color if not is_proj else "none"
        bubbles += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{color}" stroke-width="1.5" opacity="0.8"/>'
            f'<text x="{x:.1f}" y="{y - r - 3:.1f}" fill="{color}" font-size="9" '
            f'text-anchor="middle">{run.run_id}</text>'
        )

    # X-axis ticks
    x_ticks = ""
    for tick in [0, 2, 4, 6, 8, 10]:
        if tick <= max_cost:
            x = cx(tick)
            x_ticks += (
                f'<line x1="{x:.1f}" y1="{h - pad["b"]}" x2="{x:.1f}" '
                f'y2="{h - pad["b"] + 4}" stroke="#6b7280"/>'
                f'<text x="{x:.1f}" y="{h - pad["b"] + 15}" fill="#9CA3AF" '
                f'font-size="10" text-anchor="middle">${tick}</text>'
            )

    axis_labels = (
        f'<text x="{w // 2}" y="{h - 5}" fill="#9CA3AF" font-size="11" '
        f'text-anchor="middle">Est. Cost (USD)</text>'
        f'<text x="14" y="{h // 2}" fill="#9CA3AF" font-size="11" '
        f'text-anchor="middle" transform="rotate(-90,14,{h // 2})">Success Rate</text>'
    )
    title = (
        f'<text x="{w // 2}" y="16" fill="#e5e7eb" font-size="13" '
        f'font-weight="bold" text-anchor="middle">Cost vs Success (bubble = n_demos)</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#1f2937;border-radius:8px">'
        f'{title}{grid}{bubbles}{x_ticks}{axis_labels}</svg>'
    )

# ── HTML dashboard ─────────────────────────────────────────────────────────────

def _method_badge(method: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600">{method}</span>'
    )


def render_dashboard(runs: List[EvalRun]) -> str:
    svg_progress = plot_progress_svg(runs)
    svg_latency = plot_latency_bar(runs)
    svg_cost = plot_cost_scatter(runs)

    real_runs = [r for r in runs if r.n_episodes > 0]
    best = max(real_runs, key=lambda r: r.success_rate) if real_runs else None
    best_callout = ""
    if best:
        best_callout = (
            f'<div style="background:#065f46;border:1px solid #10b981;border-radius:8px;'
            f'padding:12px 18px;margin-bottom:20px">'
            f'<span style="color:#6ee7b7;font-weight:700">Best model: </span>'
            f'<span style="color:#d1fae5">{best.run_id}</span>'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'<span style="color:#6ee7b7">Success:</span> '
            f'<span style="color:#d1fae5;font-weight:700">{best.success_rate:.0f}%</span>'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'<span style="color:#6ee7b7">MAE:</span> '
            f'<span style="color:#d1fae5">{best.mae:.3f}</span>'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'<span style="color:#6ee7b7">Latency:</span> '
            f'<span style="color:#d1fae5">{best.avg_latency_ms:.0f}ms</span>'
            f'</div>'
        )

    rows = ""
    for run in runs:
        cost = _cost(run)
        proj_tag = ' <span style="color:#9ca3af;font-size:10px">(proj)</span>' if run.n_episodes == 0 else ""
        rows += (
            f"<tr>"
            f'<td style="padding:8px 12px;font-family:monospace;font-size:12px;color:#93c5fd">'
            f'{run.run_id}</td>'
            f'<td style="padding:8px 12px">{_method_badge(run.training_method, run.color_hint)}</td>'
            f'<td style="padding:8px 12px;text-align:right">{run.n_demos}</td>'
            f'<td style="padding:8px 12px;text-align:right">{run.n_steps:,}</td>'
            f'<td style="padding:8px 12px;text-align:right;font-weight:700;color:'
            f'{"#10b981" if run.success_rate >= 50 else "#f59e0b" if run.success_rate >= 20 else "#ef4444"}">'
            f'{run.success_rate:.0f}%{proj_tag}</td>'
            f'<td style="padding:8px 12px;text-align:right">{run.mae:.3f}</td>'
            f'<td style="padding:8px 12px;text-align:right">{run.avg_latency_ms:.0f}ms</td>'
            f'<td style="padding:8px 12px;text-align:right">{run.p95_latency_ms:.0f}ms</td>'
            f'<td style="padding:8px 12px;text-align:right">${cost:.2f}</td>'
            f'<td style="padding:8px 12px;color:#9ca3af;font-size:11px">{run.eval_date}</td>'
            f'<td style="padding:8px 12px;color:#6b7280;font-size:11px;max-width:200px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{run.notes}</td>'
            f"</tr>"
        )

    insights = [
        "BC plateaus at 5% success regardless of demo count (500→1000) — more data alone insufficient.",
        "DAgger run3→run4 demonstrates the interactive correction flywheel: 12%→22%→30%→65%.",
        "DAgger run5 regression (5%) confirms minimum demo threshold (~1000) for reliable learning.",
        "Latency is stable across all runs (224–231ms avg) — compute overhead is negligible.",
        "Curriculum SDG projection (72%) targets GTC demo milestone at ~$8.60 training cost.",
        "MAE correlation with success is weak — task completion is the ground-truth metric.",
    ]
    insight_html = "".join(
        f'<li style="margin-bottom:6px;color:#d1d5db">{ins}</li>' for ins in insights
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OCI Robot Cloud — Multi-Run Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111827; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont,
    'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; font-weight: 700; color: #f9fafb; margin-bottom: 4px; }}
  .subtitle {{ color: #6b7280; font-size: 13px; margin-bottom: 24px; }}
  .charts {{ display: grid; gap: 20px; margin-bottom: 24px; }}
  .card {{ background: #1f2937; border: 1px solid #374151; border-radius: 10px;
    padding: 16px; overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead tr {{ background: #111827; }}
  th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600;
    color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #374151; }}
  th.right {{ text-align: right; }}
  tbody tr:hover {{ background: #1a2535; }}
  tbody tr {{ border-bottom: 1px solid #1f2937; }}
  .btn {{ background: #2563eb; color: #fff; border: none; padding: 8px 16px;
    border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }}
  .btn:hover {{ background: #1d4ed8; }}
  ul {{ list-style: disc; padding-left: 20px; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Multi-Run Evaluation Dashboard</h1>
<p class="subtitle">GTC 2026 prep · {len(runs)} runs · generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</p>

{best_callout}

<div class="charts">
  <div class="card">{svg_progress}</div>
  <div class="card">{svg_latency}</div>
  <div class="card">{svg_cost}</div>
</div>

<div class="card" style="margin-bottom:20px">
  <h2 style="font-size:15px;font-weight:700;margin-bottom:14px;color:#f3f4f6">Key Insights</h2>
  <ul>{insight_html}</ul>
</div>

<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <h2 style="font-size:15px;font-weight:700;color:#f3f4f6">Run Comparison Table</h2>
    <a href="/api/export"><button class="btn">Export CSV</button></a>
  </div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr>
      <th>Run ID</th><th>Method</th>
      <th class="right">Demos</th><th class="right">Steps</th>
      <th class="right">Success</th><th class="right">MAE</th>
      <th class="right">Avg Lat</th><th class="right">p95 Lat</th>
      <th class="right">Cost</th><th>Date</th><th>Notes</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</div>
</body>
</html>"""

# ── FastAPI app ────────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="Multi-Run Eval Dashboard", version="1.0.0")
    _conn: Optional[sqlite3.Connection] = None

    def get_conn() -> sqlite3.Connection:
        global _conn
        if _conn is None:
            _conn = init_db()
        return _conn

    @app.get("/", response_class=HTMLResponse)
    def root():
        runs = fetch_runs(get_conn())
        return render_dashboard(runs)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "multi_run_dashboard", "port": 8040}

    @app.get("/api/runs")
    def list_runs():
        return [asdict(r) for r in fetch_runs(get_conn())]

    @app.post("/api/runs", status_code=201)
    def add_run(run: dict):
        required = {f.name for f in EvalRun.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        missing = required - set(run.keys())
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
        er = EvalRun(**{k: run[k] for k in required})
        insert_run(get_conn(), er)
        return {"inserted": er.run_id}

    @app.get("/api/export")
    def export_csv():
        runs = fetch_runs(get_conn())
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "run_id", "checkpoint_path", "training_method", "n_demos", "n_steps",
            "success_rate", "mae", "avg_latency_ms", "p95_latency_ms", "n_episodes",
            "eval_date", "notes", "color_hint", "est_cost_usd",
        ])
        for r in runs:
            writer.writerow([
                r.run_id, r.checkpoint_path, r.training_method, r.n_demos, r.n_steps,
                r.success_rate, r.mae, r.avg_latency_ms, r.p95_latency_ms, r.n_episodes,
                r.eval_date, r.notes, r.color_hint, f"{_cost(r):.2f}",
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=eval_runs.csv"},
        )

# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Run Eval Dashboard")
    parser.add_argument("--port", type=int, default=8040)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", help="Seed mock data on startup")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
        return

    conn = init_db()
    if args.mock:
        seed_mock(conn)
        print(f"[dashboard] Seeded {len(MOCK_RUNS)} mock runs into {DB_PATH}")

    global _conn
    _conn = conn
    print(f"[dashboard] Starting on http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
