"""Evaluation Episode Replay and Analysis Dashboard — port 8150"""

from __future__ import annotations

import math
import random
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    HTTPException = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Seed-deterministic episode data
# ---------------------------------------------------------------------------

def _build_episodes() -> list[dict[str, Any]]:
    rng = random.Random(42)
    failure_modes = ["lighting_variation", "background_clutter", "recovery_failure"]
    episodes: list[dict[str, Any]] = []
    for i in range(1, 21):
        # first 3 fail; remainder succeed with small random variation
        success = False if i <= 3 else (rng.random() < 0.78 / 0.78)  # all rest succeed → sr=17/20=0.85; spec says 0.78 → keep first 3 fail + episodes 7,12 fail for 4 failures = 16/20=0.80; adjust below
        episodes.append((i, success))
    # Enforce exactly sr=0.78 → 15 successes, 5 failures (first 3 + two more)
    # Rebuild deterministically: episodes 1,2,3,8,14 fail
    fail_set = {1, 2, 3, 8, 14}
    episodes_out: list[dict[str, Any]] = []
    for i in range(1, 21):
        success = i not in fail_set
        if success:
            steps = rng.randint(820, 890)
            failure_mode = None
        else:
            steps = rng.randint(200, 400)
            failure_mode = failure_modes[(i - 1) % len(failure_modes)]
        episodes_out.append({
            "episode_id": i,
            "success": success,
            "steps": steps,
            "failure_mode": failure_mode,
        })
    return episodes_out


SESSIONS: dict[str, dict[str, Any]] = {
    "eval_bc_baseline": {
        "session_id": "eval_bc_baseline",
        "model": "bc_baseline",
        "date": "2026-03-28",
        "n_episodes": 20,
        "sr": 0.05,
        "avg_steps": 412,
        "avg_latency": 412,
        "episodes": [],
    },
    "eval_groot_v2": {
        "session_id": "eval_groot_v2",
        "model": "groot_finetune_v2",
        "date": "2026-03-30",
        "n_episodes": 20,
        "sr": 0.78,
        "avg_steps": 847,
        "avg_latency": 226,
        "episodes": _build_episodes(),
    },
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _steps_histogram_svg(episodes: list[dict[str, Any]]) -> str:
    """680x200 histogram of step counts. sky=success, red=failure."""
    W, H, PAD = 680, 200, 30
    bin_size = 40
    min_steps, max_steps = 200, 1000
    n_bins = (max_steps - min_steps) // bin_size  # 20 bins

    success_counts = [0] * n_bins
    fail_counts = [0] * n_bins
    for ep in episodes:
        b = min((ep["steps"] - min_steps) // bin_size, n_bins - 1)
        b = max(b, 0)
        if ep["success"]:
            success_counts[b] += 1
        else:
            fail_counts[b] += 1

    max_count = max(max(success_counts), max(fail_counts), 1)
    chart_w = W - 2 * PAD
    chart_h = H - 2 * PAD
    bar_w = chart_w / n_bins

    rects = []
    for b in range(n_bins):
        x = PAD + b * bar_w + 1
        bw = bar_w - 2
        # failure
        if fail_counts[b]:
            fh = (fail_counts[b] / max_count) * chart_h
            fy = PAD + chart_h - fh
            rects.append(f'<rect x="{x:.1f}" y="{fy:.1f}" width="{bw:.1f}" height="{fh:.1f}" fill="#C74634" opacity="0.85"/>')
        # success
        if success_counts[b]:
            sh = (success_counts[b] / max_count) * chart_h
            sy = PAD + chart_h - sh - (fail_counts[b] / max_count) * chart_h
            rects.append(f'<rect x="{x:.1f}" y="{sy:.1f}" width="{bw:.1f}" height="{sh:.1f}" fill="#38bdf8" opacity="0.85"/>')

    # x-axis labels every 4 bins
    xlabels = []
    for b in range(0, n_bins + 1, 4):
        lx = PAD + b * bar_w
        lv = min_steps + b * bin_size
        xlabels.append(f'<text x="{lx:.1f}" y="{H - 8}" fill="#94a3b8" font-size="10" text-anchor="middle">{lv}</text>')

    legend = (
        '<rect x="480" y="12" width="12" height="12" fill="#38bdf8"/>'
        '<text x="496" y="23" fill="#cbd5e1" font-size="11">Success</text>'
        '<rect x="548" y="12" width="12" height="12" fill="#C74634"/>'
        '<text x="564" y="23" fill="#cbd5e1" font-size="11">Failure</text>'
    )

    body = "\n".join(rects + xlabels)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<text x="{W//2}" y="16" fill="#94a3b8" font-size="11" text-anchor="middle">Steps Distribution</text>'
        f'{legend}{body}'
        f'<line x1="{PAD}" y1="{PAD + chart_h}" x2="{W - PAD}" y2="{PAD + chart_h}" stroke="#334155" stroke-width="1"/>'
        f'</svg>'
    )


def _episode_timeline_svg(episodes: list[dict[str, Any]]) -> str:
    """680x140 grid: 4 rows of 5 squares. green=success, red=failure."""
    W, H = 680, 140
    sq = 80
    cols, rows = 5, 4
    x_start = (W - cols * sq) / 2
    y_start = 20

    max_steps_success = max((ep["steps"] for ep in episodes if ep["success"]), default=0)

    cells = []
    for idx, ep in enumerate(episodes):
        col = idx % cols
        row = idx // cols
        cx = x_start + col * sq + 4
        cy = y_start + row * (sq // 2) + 4
        bw = sq - 8
        bh = sq // 2 - 8
        color = "#22c55e" if ep["success"] else "#C74634"
        cells.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{bw}" height="{bh}" rx="4" fill="{color}" opacity="0.8"/>')
        # episode number
        tx = cx + bw / 2
        ty = cy + bh / 2 + 4
        cells.append(f'<text x="{tx:.1f}" y="{ty:.1f}" fill="#f8fafc" font-size="11" font-weight="bold" text-anchor="middle">{ep["episode_id"]}</text>')
        # star on longest-running success
        if ep["success"] and ep["steps"] == max_steps_success:
            cells.append(f'<text x="{cx + bw - 6:.1f}" y="{cy + 10:.1f}" fill="#fbbf24" font-size="10" text-anchor="middle">★</text>')

    legend = (
        '<rect x="16" y="8" width="12" height="10" rx="2" fill="#22c55e"/>'
        '<text x="31" y="18" fill="#cbd5e1" font-size="10">Success</text>'
        '<rect x="90" y="8" width="12" height="10" rx="2" fill="#C74634"/>'
        '<text x="105" y="18" fill="#cbd5e1" font-size="10">Failure</text>'
        '<text x="200" y="18" fill="#fbbf24" font-size="10">★ longest success</text>'
    )

    body = "\n".join(cells)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{legend}{body}</svg>'
    )


def _failure_donut_svg(episodes: list[dict[str, Any]]) -> str:
    """420x240 donut: failure modes + success slice."""
    W, H, R, r = 420, 240, 90, 45
    cx, cy = 150, 120

    from collections import Counter  # stdlib
    fm_counts = Counter(ep["failure_mode"] for ep in episodes if ep["failure_mode"])
    success_count = sum(1 for ep in episodes if ep["success"])
    total = len(episodes)

    slices = []
    for fm, cnt in sorted(fm_counts.items()):
        slices.append((fm, cnt))
    slices.append(("success", success_count))

    colors = ["#C74634", "#f97316", "#ef4444", "#22c55e"]

    def arc_path(cx: float, cy: float, R: float, r: float, start_deg: float, end_deg: float) -> str:
        def pt(angle_deg: float, radius: float):
            a = math.radians(angle_deg - 90)
            return cx + radius * math.cos(a), cy + radius * math.sin(a)
        large = 1 if (end_deg - start_deg) > 180 else 0
        ox, oy = pt(start_deg, R)
        ax, ay = pt(end_deg, R)
        ix, iy = pt(end_deg, r)
        bx, by = pt(start_deg, r)
        return f"M{ox:.2f},{oy:.2f} A{R},{R} 0 {large},1 {ax:.2f},{ay:.2f} L{ix:.2f},{iy:.2f} A{r},{r} 0 {large},0 {bx:.2f},{by:.2f} Z"

    paths = []
    start = 0.0
    for i, (label, count) in enumerate(slices):
        deg = (count / total) * 360
        end = start + deg
        color = colors[i % len(colors)]
        d = arc_path(cx, cy, R, r, start, end)
        paths.append(f'<path d="{d}" fill="{color}" opacity="0.9" stroke="#0f172a" stroke-width="1"/>')
        # label line
        mid_deg = start + deg / 2
        mid_r = (R + r) / 2
        a = math.radians(mid_deg - 90)
        lx = cx + (R + 15) * math.cos(a)
        ly = cy + (R + 15) * math.sin(a)
        pct = count / total * 100
        anchor = "start" if lx > cx else "end"
        paths.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#cbd5e1" font-size="9" text-anchor="{anchor}">{label} {pct:.0f}%</text>')
        start = end

    # legend
    legend_items = []
    lx0, ly0 = 300, 60
    for i, (label, count) in enumerate(slices):
        color = colors[i % len(colors)]
        lyi = ly0 + i * 22
        legend_items.append(f'<rect x="{lx0}" y="{lyi}" width="12" height="12" rx="2" fill="{color}"/>')
        legend_items.append(f'<text x="{lx0 + 16}" y="{lyi + 10}" fill="#cbd5e1" font-size="10">{label} ({count})</text>')

    body = "\n".join(paths + legend_items)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<text x="{cx}" y="{cy + 5}" fill="#cbd5e1" font-size="11" text-anchor="middle">Failure</text>'
        f'<text x="{cx}" y="{cy + 18}" fill="#cbd5e1" font-size="11" text-anchor="middle">Modes</text>'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    s_bc = SESSIONS["eval_bc_baseline"]
    s_v2 = SESSIONS["eval_groot_v2"]
    eps = s_v2["episodes"]

    hist_svg = _steps_histogram_svg(eps)
    timeline_svg = _episode_timeline_svg(eps)
    donut_svg = _failure_donut_svg(eps)

    failures = [ep for ep in eps if not ep["success"]]

    def sr_color(sr: float) -> str:
        return "#22c55e" if sr >= 0.5 else "#C74634"

    comparison_rows = ""
    metrics = [
        ("Session ID", s_bc["session_id"], s_v2["session_id"]),
        ("Model", s_bc["model"], s_v2["model"]),
        ("Date", s_bc["date"], s_v2["date"]),
        ("Episodes", str(s_bc["n_episodes"]), str(s_v2["n_episodes"])),
        ("Success Rate", f"{s_bc['sr']*100:.0f}%", f"{s_v2['sr']*100:.0f}%"),
        ("Avg Steps", str(s_bc["avg_steps"]), str(s_v2["avg_steps"])),
        ("Avg Latency (ms)", str(s_bc["avg_latency"]), str(s_v2["avg_latency"])),
    ]
    for label, v1, v2 in metrics:
        highlight = ' style="color:#38bdf8;font-weight:600"' if label == "Success Rate" else ""
        comparison_rows += f"<tr><td>{label}</td><td>{v1}</td><td{highlight}>{v2}</td></tr>"

    episode_rows = ""
    for ep in eps:
        status = '<span style="color:#22c55e">✓ Success</span>' if ep["success"] else f'<span style="color:#C74634">✗ {ep["failure_mode"]}</span>'
        episode_rows += f"<tr><td>{ep['episode_id']}</td><td>{status}</td><td>{ep['steps']}</td></tr>"

    failure_rows = ""
    for ep in failures:
        failure_rows += f"<tr><td>{ep['episode_id']}</td><td style='color:#C74634'>{ep['failure_mode']}</td><td>{ep['steps']}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Eval Replay Dashboard | OCI Robot Cloud</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
.sub{{color:#64748b;font-size:0.85rem;margin-bottom:24px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}}
.card{{background:#1e293b;border-radius:10px;padding:20px}}
.card h2{{font-size:1rem;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
th{{color:#64748b;font-weight:600;padding:6px 10px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#1e293b}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat-label{{font-size:0.75rem;color:#64748b;margin-top:4px}}
.stats-row{{display:flex;gap:20px;margin-bottom:20px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:16px 24px;flex:1;text-align:center}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600}}
.badge-up{{background:#166534;color:#86efac}}
.badge-down{{background:#7f1d1d;color:#fca5a5}}
svg{{max-width:100%;height:auto}}
</style>
</head>
<body>
<h1>Eval Replay Dashboard</h1>
<p class="sub">OCI Robot Cloud · Evaluation Analysis · Port 8150</p>

<div class="stats-row">
  <div class="stat-card"><div class="stat" style="color:#C74634">5%</div><div class="stat-label">BC Baseline SR</div></div>
  <div class="stat-card"><div class="stat" style="color:#22c55e">78%</div><div class="stat-label">GR00T v2 SR</div></div>
  <div class="stat-card"><div class="stat">+73pp</div><div class="stat-label">Improvement <span class="badge badge-up">15.6×</span></div></div>
  <div class="stat-card"><div class="stat" style="color:#38bdf8">226ms</div><div class="stat-label">GR00T v2 Latency</div></div>
  <div class="stat-card"><div class="stat">{len(failures)}</div><div class="stat-label">Failures (eval_groot_v2)</div></div>
</div>

<div class="card" style="margin-bottom:20px">
  <h2>Episode Timeline — eval_groot_v2</h2>
  {timeline_svg}
</div>

<div class="grid2">
  <div class="card">
    <h2>Steps Distribution</h2>
    {hist_svg}
  </div>
  <div class="card">
    <h2>Failure Mode Breakdown</h2>
    {donut_svg}
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Session Comparison</h2>
    <table>
      <thead><tr><th>Metric</th><th>BC Baseline</th><th>GR00T v2</th></tr></thead>
      <tbody>{comparison_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Episode Details — eval_groot_v2</h2>
    <div style="max-height:280px;overflow-y:auto">
    <table>
      <thead><tr><th>#</th><th>Status</th><th>Steps</th></tr></thead>
      <tbody>{episode_rows}</tbody>
    </table>
    </div>
  </div>
</div>

<div class="card" style="margin-top:20px">
  <h2>Failure Episodes</h2>
  <table>
    <thead><tr><th>Episode</th><th>Failure Mode</th><th>Steps</th></tr></thead>
    <tbody>{failure_rows}</tbody>
  </table>
</div>

<p style="color:#334155;font-size:0.75rem;margin-top:20px;text-align:center">
  API: GET /sessions · /sessions/{{id}} · /sessions/{{id}}/failures | Oracle Confidential
</p>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Eval Replay", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(_dashboard_html())

    @app.get("/sessions")
    def list_sessions() -> JSONResponse:
        summary = [
            {
                k: v for k, v in s.items() if k != "episodes"
            }
            for s in SESSIONS.values()
        ]
        return JSONResponse(summary)

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> JSONResponse:
        if session_id not in SESSIONS:
            raise HTTPException(status_code=404, detail="Session not found")
        return JSONResponse(SESSIONS[session_id])

    @app.get("/sessions/{session_id}/failures")
    def get_failures(session_id: str) -> JSONResponse:
        if session_id not in SESSIONS:
            raise HTTPException(status_code=404, detail="Session not found")
        failures = [ep for ep in SESSIONS[session_id]["episodes"] if not ep["success"]]
        return JSONResponse({"session_id": session_id, "failures": failures, "count": len(failures)})


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("eval_replay:app", host="0.0.0.0", port=8150, reload=True)
