"""eval_data_curator.py — FastAPI service on port 8274

Curates and maintains evaluation datasets to ensure fair and
consistent benchmarking across robot policies.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TASK_DISTRIBUTION = [
    {"task": "pick_place", "count": 60, "pct": 30, "target": 14, "risk": "HIGH"},
    {"task": "stack",      "count": 40, "pct": 20, "target": 14, "risk": "MEDIUM"},
    {"task": "pour",       "count": 30, "pct": 15, "target": 14, "risk": "LOW"},
    {"task": "wipe",       "count": 24, "pct": 12, "target": 14, "risk": "LOW"},
    {"task": "drawer",     "count": 20, "pct": 10, "target": 14, "risk": "MEDIUM"},
    {"task": "button",     "count": 16, "pct":  8, "target": 14, "risk": "MEDIUM"},
    {"task": "handover",   "count": 10, "pct":  5, "target": 14, "risk": "HIGH"},
]

DIFFICULTY_TIERS = ["easy", "medium", "hard", "expert"]
DIFFICULTY_COUNTS = {"easy": 60, "medium": 72, "hard": 36, "expert": 32}  # total 200

POLICY_SR = {
    "BC":       {"easy": 0.88, "medium": 0.62, "hard": 0.31, "expert": 0.12},
    "DAgger":   {"easy": 0.91, "medium": 0.74, "hard": 0.47, "expert": 0.21},
    "GR00T_v2": {"easy": 0.97, "medium": 0.83, "hard": 0.58, "expert": 0.34},
}

TASK_BALANCE_SCORE = 0.61
DIFF_CALIBRATION   = 0.74
DISCRIM_POWER      = 0.82

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _donut_svg() -> str:
    """Task distribution donut chart."""
    cx, cy, r_out, r_in = 200, 200, 140, 75
    colors = ["#C74634", "#38bdf8", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899", "#64748b"]

    total = sum(t["count"] for t in TASK_DISTRIBUTION)
    slices = []
    angle = -math.pi / 2  # start at top
    for i, t in enumerate(TASK_DISTRIBUTION):
        sweep = 2 * math.pi * t["count"] / total
        slices.append((angle, sweep, colors[i % len(colors)], t))
        angle += sweep

    paths = []
    for (a0, sw, col, t) in slices:
        a1 = a0 + sw
        x0o = cx + r_out * math.cos(a0)
        y0o = cy + r_out * math.sin(a0)
        x1o = cx + r_out * math.cos(a1)
        y1o = cy + r_out * math.sin(a1)
        x0i = cx + r_in * math.cos(a1)
        y0i = cy + r_in * math.sin(a1)
        x1i = cx + r_in * math.cos(a0)
        y1i = cy + r_in * math.sin(a0)
        large = 1 if sw > math.pi else 0
        risk_stroke = "#ef4444" if t["risk"] == "HIGH" else ("#f59e0b" if t["risk"] == "MEDIUM" else col)
        d = (f"M {x0o:.1f} {y0o:.1f} "
             f"A {r_out} {r_out} 0 {large} 1 {x1o:.1f} {y1o:.1f} "
             f"L {x0i:.1f} {y0i:.1f} "
             f"A {r_in} {r_in} 0 {large} 0 {x1i:.1f} {y1i:.1f} Z")
        title = f"{t['task']} {t['pct']}% (risk:{t['risk']})"
        paths.append(f'<path d="{d}" fill="{col}" stroke="{risk_stroke}" stroke-width="2"><title>{title}</title></path>')

    # legend
    legend_items = ""
    for i, t in enumerate(TASK_DISTRIBUTION):
        lx, ly = 360, 100 + i * 24
        badge_col = "#ef4444" if t["risk"] == "HIGH" else ("#f59e0b" if t["risk"] == "MEDIUM" else "#10b981")
        legend_items += (
            f'<rect x="{lx}" y="{ly-10}" width="14" height="14" fill="{colors[i % len(colors)]}" rx="2"/>'
            f'<text x="{lx+20}" y="{ly+2}" fill="#e2e8f0" font-size="12">{t["task"]} {t["pct"]}%</text>'
            f'<text x="{lx+160}" y="{ly+2}" fill="{badge_col}" font-size="11" font-weight="bold">{t["risk"]}</text>'
        )

    center_label = (
        f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#94a3b8" font-size="13">200</text>'
        f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#94a3b8" font-size="11">episodes</text>'
        f'<text x="{cx}" y="{cy+28}" text-anchor="middle" fill="#C74634" font-size="10">IMBALANCE</text>'
    )

    return (
        '<svg width="560" height="400" xmlns="http://www.w3.org/2000/svg" '
        'style="background:#1e293b;border-radius:8px">'
        f'<text x="280" y="30" text-anchor="middle" fill="#f1f5f9" font-size="15" font-weight="bold">'
        'Eval Set Task Distribution (200 episodes)</text>'
        + "\n".join(paths)
        + center_label
        + legend_items
        + '<text x="280" y="390" text-anchor="middle" fill="#64748b" font-size="10">'
        'Target: ~14% per task | RED border = imbalance risk</text>'
        + '</svg>'
    )


def _difficulty_bar_svg() -> str:
    """Difficulty distribution bar chart with per-policy SR."""
    svg_w, svg_h = 640, 400
    margin = {"top": 50, "right": 20, "bottom": 80, "left": 55}
    plot_w = svg_w - margin["left"] - margin["right"]
    plot_h = svg_h - margin["top"] - margin["bottom"]

    difficulties = DIFFICULTY_TIERS
    n = len(difficulties)
    group_w = plot_w / n
    policies = list(POLICY_SR.keys())
    pol_colors = {"BC": "#38bdf8", "DAgger": "#f59e0b", "GR00T_v2": "#C74634"}
    bar_w = group_w * 0.22
    offsets = [-bar_w, 0, bar_w]

    ox = margin["left"]
    oy = margin["top"] + plot_h

    bars = ""
    for gi, diff in enumerate(difficulties):
        gx = ox + gi * group_w + group_w / 2
        for pi, pol in enumerate(policies):
            sr = POLICY_SR[pol][diff]
            bh = sr * plot_h
            bx = gx + offsets[pi] - bar_w / 2
            by = oy - bh
            col = pol_colors[pol]
            bars += (f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                     f'fill="{col}" rx="2" opacity="0.87">'
                     f'<title>{pol} {diff}: SR={sr:.0%}</title></rect>')
            bars += (f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" '
                     f'text-anchor="middle" fill="{col}" font-size="9">{sr:.0%}</text>')

    # x-axis labels
    xlabels = ""
    for gi, diff in enumerate(difficulties):
        gx = ox + gi * group_w + group_w / 2
        count = DIFFICULTY_COUNTS[diff]
        pct = count / 200 * 100
        target_flag = " ⚠" if abs(pct - 25) > 5 else ""
        xlabels += (f'<text x="{gx:.1f}" y="{oy + 18}" text-anchor="middle" '
                    f'fill="#cbd5e1" font-size="12">{diff}</text>')
        xlabels += (f'<text x="{gx:.1f}" y="{oy + 34}" text-anchor="middle" '
                    f'fill="#64748b" font-size="10">n={count} ({pct:.0f}%){target_flag}</text>')

    # y-axis
    yaxis = ""
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        ty = oy - tick * plot_h
        yaxis += (f'<line x1="{ox}" y1="{ty:.1f}" x2="{ox + plot_w}" y2="{ty:.1f}" '
                  f'stroke="#334155" stroke-width="1"/>')
        yaxis += (f'<text x="{ox - 6}" y="{ty + 4:.1f}" text-anchor="end" '
                  f'fill="#94a3b8" font-size="10">{tick:.0%}</text>')

    # ideal 25% target line
    ideal_y = oy - 0.70 * plot_h  # 70% SR is discrimination target for medium
    ideal_line = (f'<line x1="{ox}" y1="{ideal_y:.1f}" x2="{ox + plot_w}" y2="{ideal_y:.1f}" '
                  f'stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>'
                  f'<text x="{ox + plot_w - 2}" y="{ideal_y - 4:.1f}" text-anchor="end" '
                  f'fill="#38bdf8" font-size="9">target 70-75% (medium discrim.)</text>')

    # legend
    legend = ""
    for pi, pol in enumerate(policies):
        lx = ox + pi * 145
        legend += (f'<rect x="{lx}" y="{svg_h - 18}" width="12" height="12" '
                   f'fill="{pol_colors[pol]}" rx="2"/>'
                   f'<text x="{lx + 16}" y="{svg_h - 7}" fill="#e2e8f0" font-size="11">{pol}</text>')

    title = (f'<text x="{svg_w//2}" y="28" text-anchor="middle" fill="#f1f5f9" '
             f'font-size="15" font-weight="bold">Difficulty Calibration — SR by Policy & Tier</text>')

    return (
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + title + yaxis + ideal_line + bars + xlabels + legend
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Eval Data Curator — Port 8274</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
    header span.badge {{ background: #C74634; color: #fff; font-size: 0.75rem;
                         padding: 3px 10px; border-radius: 12px; }}
    .port-tag {{ color: #38bdf8; font-size: 0.85rem; margin-left: auto; }}
    .kpi-row {{ display: flex; gap: 16px; padding: 24px 32px 8px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 18px 24px; min-width: 180px; flex: 1; }}
    .kpi .label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;
                   letter-spacing: .05em; margin-bottom: 6px; }}
    .kpi .value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .sub   {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
    .warn {{ color: #f59e0b !important; }}
    .danger {{ color: #ef4444 !important; }}
    .charts {{ display: flex; gap: 24px; padding: 24px 32px; flex-wrap: wrap; }}
    .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
                   padding: 20px; flex: 1; min-width: 320px; }}
    .chart-card h2 {{ font-size: 0.95rem; color: #94a3b8; margin-bottom: 14px; }}
    .alerts {{ margin: 0 32px 24px; background: #1e293b; border: 1px solid #334155;
               border-radius: 10px; padding: 20px; }}
    .alerts h2 {{ font-size: 0.95rem; color: #94a3b8; margin-bottom: 12px; }}
    .alert-item {{ display: flex; gap: 10px; align-items: flex-start; margin-bottom: 8px;
                   font-size: 0.85rem; }}
    .sev-high {{ color: #ef4444; font-weight: bold; min-width: 60px; }}
    .sev-med  {{ color: #f59e0b; font-weight: bold; min-width: 60px; }}
    .sev-low  {{ color: #10b981; font-weight: bold; min-width: 60px; }}
    footer {{ text-align: center; color: #475569; font-size: 0.75rem; padding: 20px; }}
  </style>
</head>
<body>
  <header>
    <h1>Eval Data Curator</h1>
    <span class="badge">OCI Robot Cloud</span>
    <span class="port-tag">:8274</span>
  </header>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Total Eval Episodes</div>
      <div class="value">200</div>
      <div class="sub">7 task categories</div>
    </div>
    <div class="kpi">
      <div class="label">Task Balance Score</div>
      <div class="value warn">0.61</div>
      <div class="sub">Target &ge; 0.85 | pick_place over-represented</div>
    </div>
    <div class="kpi">
      <div class="label">Difficulty Calibration</div>
      <div class="value warn">0.74</div>
      <div class="sub">hard=18% (target 25%)</div>
    </div>
    <div class="kpi">
      <div class="label">Discriminative Power</div>
      <div class="value">0.82</div>
      <div class="sub">GR00T_v2 medium SR 83% &gt; 75% target</div>
    </div>
    <div class="kpi">
      <div class="label">Last Curation Run</div>
      <div class="value" style="font-size:1.1rem;padding-top:8px">2026-03-30</div>
      <div class="sub">Auto-rebalance pending</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <h2>Task Distribution — Imbalance Risk</h2>
      {_donut_svg()}
    </div>
    <div class="chart-card">
      <h2>Difficulty Calibration by Policy</h2>
      {_difficulty_bar_svg()}
    </div>
  </div>

  <div class="alerts">
    <h2>Curation Alerts</h2>
    <div class="alert-item"><span class="sev-high">[HIGH]</span>
      pick_place over-represented at 30% (target ~14%) — ceiling effect on BC/DAgger medium-difficulty SR; resample or cap at 28 episodes.</div>
    <div class="alert-item"><span class="sev-high">[HIGH]</span>
      handover under-represented at 5% (10 episodes) — insufficient statistical power; add 18+ episodes from sim SDG pipeline.</div>
    <div class="alert-item"><span class="sev-med">[MEDIUM]</span>
      hard tier at 18% (36 eps) vs target 25% — GR00T_v2 discriminative power inflated; augment with 14 harder variants.</div>
    <div class="alert-item"><span class="sev-med">[MEDIUM]</span>
      GR00T_v2 medium-difficulty SR = 83%, above 70-75% discrimination window — eval set too easy for this policy tier.</div>
    <div class="alert-item"><span class="sev-low">[LOW]</span>
      Expert tier n=32 — borderline sample size for 95% CI; consider expanding to 40+ before publishing benchmark numbers.</div>
  </div>

  <footer>OCI Robot Cloud &mdash; Eval Data Curator v1.0 &mdash; Port 8274</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or fallback)
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Eval Data Curator",
        description="Curates and maintains evaluation datasets for consistent robot policy benchmarking.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_data_curator", "port": 8274}

    @app.get("/api/stats")
    async def stats():
        return {
            "total_episodes": 200,
            "task_distribution": TASK_DISTRIBUTION,
            "difficulty_counts": DIFFICULTY_COUNTS,
            "policy_sr": POLICY_SR,
            "metrics": {
                "task_balance_score": TASK_BALANCE_SCORE,
                "difficulty_calibration": DIFF_CALIBRATION,
                "discriminative_power": DISCRIM_POWER,
            },
            "alerts": [
                {"severity": "HIGH",   "message": "pick_place over-represented at 30%"},
                {"severity": "HIGH",   "message": "handover under-represented at 5%"},
                {"severity": "MEDIUM", "message": "hard tier at 18% vs target 25%"},
                {"severity": "MEDIUM", "message": "GR00T_v2 medium SR 83% exceeds discrimination window"},
                {"severity": "LOW",    "message": "Expert tier n=32 — borderline for 95% CI"},
            ],
        }

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "eval_data_curator", "port": 8274}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8274)
    else:
        print("[eval_data_curator] fastapi not found — starting stdlib fallback on :8274")
        HTTPServer(("0.0.0.0", 8274), Handler).serve_forever()
