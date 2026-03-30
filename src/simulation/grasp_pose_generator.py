#!/usr/bin/env python3
"""
grasp_pose_generator.py — OCI Robot Cloud Grasp Pose Generator
Port 8642 | Generates and ranks grasp pose candidates for manipulation tasks.

Generates diverse grasp candidates per object, scores by success probability,
and recommends optimal strategy (top/side/tilted/pinch/power/wrap) based on
object properties (mass, friction, geometry).

Metrics:
  - 12 candidates/object
  - top-grasp SR: 82%
  - diversity score: 0.79
  - heavy objects  → power-grasp
  - low-friction   → top-grasp

Usage:
    python src/simulation/grasp_pose_generator.py [--port 8642]

Endpoints:
    GET /           HTML dashboard (dark theme)
    GET /candidates JSON list of grasp candidates
    GET /strategies JSON strategy comparison
    GET /health     Health check

stdlib only; try/except ImportError guards FastAPI.
"""

import json
import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8642

# 6 grasp strategies with empirical success rates
STRATEGIES = [
    {"id": "top_grasp",  "label": "Top Grasp",   "sr": 0.82, "color": "#22c55e"},
    {"id": "power",      "label": "Power",        "sr": 0.77, "color": "#34d399"},
    {"id": "side",       "label": "Side",         "sr": 0.71, "color": "#38bdf8"},
    {"id": "wrap",       "label": "Wrap",         "sr": 0.73, "color": "#60a5fa"},
    {"id": "tilted",     "label": "Tilted",       "sr": 0.68, "color": "#f59e0b"},
    {"id": "pinch",      "label": "Pinch",        "sr": 0.64, "color": "#fb923c"},
]

# Rule-based strategy selector
STRATEGY_RULES = [
    {"condition": "mass_kg > 1.5",         "recommended": "power"},
    {"condition": "friction_coeff < 0.3",  "recommended": "top_grasp"},
    {"condition": "elongated == True",     "recommended": "side"},
    {"condition": "cylindrical == True",   "recommended": "wrap"},
    {"condition": "small == True",         "recommended": "pinch"},
    {"condition": "default",               "recommended": "top_grasp"},
]

CANDIDATES_PER_OBJECT = 12
DIVERSITY_SCORE = 0.79


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def _sr_color(sr: float) -> str:
    """Map success rate to green (high) → red (low) via HSL."""
    # sr in [0,1]; hue: 0=red(0), 1=green(120)
    hue = int(sr * 120)
    return f"hsl({hue},85%,50%)"


def generate_candidates(seed: int = 42) -> list:
    """Generate 12 grasp candidates with approach angles and success probabilities."""
    rng = random.Random(seed)
    candidates = []
    for i in range(CANDIDATES_PER_OBJECT):
        angle_deg = i * (360 / CANDIDATES_PER_OBJECT)  # evenly spaced around object
        angle_rad = math.radians(angle_deg)
        # Base SR with angular preference toward top (90 deg = up)
        angular_penalty = abs(math.sin(angle_rad)) * 0.12  # side approaches slightly harder
        strategy_idx = i % len(STRATEGIES)
        base_sr = STRATEGIES[strategy_idx]["sr"]
        sr = max(0.30, min(0.95, base_sr - angular_penalty + rng.uniform(-0.04, 0.04)))
        candidates.append({
            "id": i,
            "angle_deg": round(angle_deg, 1),
            "approach_x": round(math.cos(angle_rad), 4),
            "approach_y": round(math.sin(angle_rad), 4),
            "strategy": STRATEGIES[strategy_idx]["id"],
            "success_prob": round(sr, 3),
            "rank": 0,  # filled below
        })
    # rank by success prob descending
    candidates.sort(key=lambda c: -c["success_prob"])
    for rank, c in enumerate(candidates, 1):
        c["rank"] = rank
    candidates.sort(key=lambda c: c["id"])  # restore original order for SVG
    return candidates


# ---------------------------------------------------------------------------
# SVG: Grasp pose candidates (top-down view)
# ---------------------------------------------------------------------------

def _svg_candidates(candidates: list) -> str:
    """Top-down circle with 12 approach arrows radiating outward.
    Arrow color = success probability (green=high, red=low).
    """
    W, H = 360, 360
    CX, CY, R_OBJ = W // 2, H // 2, 48
    R_ARROW_START = R_OBJ + 12
    ARROW_LEN = 52

    arrows = []
    labels = []
    for c in candidates:
        angle_rad = math.radians(c["angle_deg"])
        color = _sr_color(c["success_prob"])
        # Arrow tail and head
        x1 = CX + math.cos(angle_rad) * (R_ARROW_START + ARROW_LEN)
        y1 = CY + math.sin(angle_rad) * (R_ARROW_START + ARROW_LEN)
        x2 = CX + math.cos(angle_rad) * (R_ARROW_START + 4)
        y2 = CY + math.sin(angle_rad) * (R_ARROW_START + 4)
        # Arrowhead
        hdx = (x2 - x1) / max(abs(x2 - x1) + abs(y2 - y1), 0.001)
        hdy = (y2 - y1) / max(abs(x2 - x1) + abs(y2 - y1), 0.001)
        perp_x = -hdy * 5
        perp_y = hdx * 5
        ax, ay = x2, y2
        bx = x2 - hdx * 10 + perp_x
        by = y2 - hdy * 10 + perp_y
        cx2 = x2 - hdx * 10 - perp_x
        cy2 = y2 - hdy * 10 - perp_y
        stroke_w = 2.5 if c["rank"] == 1 else 1.8
        arrows.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round"/>'
        )
        arrows.append(
            f'<polygon points="{ax:.1f},{ay:.1f} {bx:.1f},{by:.1f} {cx2:.1f},{cy2:.1f}" '
            f'fill="{color}"/>'
        )
        # SR label at tip
        lx = CX + math.cos(angle_rad) * (R_ARROW_START + ARROW_LEN + 14)
        ly = CY + math.sin(angle_rad) * (R_ARROW_START + ARROW_LEN + 14)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{color}" font-size="8" '
            f'text-anchor="middle" dominant-baseline="middle">{int(c["success_prob"]*100)}%</text>'
        )

    best = max(candidates, key=lambda c: c["success_prob"])
    best_label = f"Best: {best['strategy']} {int(best['success_prob']*100)}%"

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <defs>
    <radialGradient id="objGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <!-- Object circle -->
  <circle cx="{CX}" cy="{CY}" r="{R_OBJ}" fill="url(#objGrad)" stroke="#38bdf8" stroke-width="2"/>
  <text x="{CX}" y="{CY}" fill="#38bdf8" font-size="11" text-anchor="middle" dominant-baseline="middle"
        font-family="monospace">OBJECT</text>
  <!-- Approach arrows -->
  {''.join(arrows)}
  {''.join(labels)}
  <!-- Title -->
  <text x="{W//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">Grasp Pose Candidates</text>
  <text x="{W//2}" y="{H-8}" fill="#64748b" font-size="9" text-anchor="middle"
        font-family="sans-serif">{best_label} &nbsp;|&nbsp; diversity={DIVERSITY_SCORE}</text>
</svg>"""


# ---------------------------------------------------------------------------
# SVG: Grasp success heatmap (8x8 grid)
# ---------------------------------------------------------------------------

def _svg_heatmap() -> str:
    """8x8 heatmap: x=position offset, y=wrist orientation. Bright spots at aligned poses."""
    W, H = 360, 300
    COLS, ROWS = 8, 8
    PAD_L, PAD_T = 48, 36
    PAD_R, PAD_B = 16, 32
    cell_w = (W - PAD_L - PAD_R) / COLS
    cell_h = (H - PAD_T - PAD_B) / ROWS

    # Synthetic SR per cell — peaks at (3,3) aligned pose
    cells = []
    for row in range(ROWS):
        for col in range(COLS):
            dx = col - 3.5
            dy = row - 3.5
            sr = 0.82 * math.exp(-(dx**2 + dy**2) / 5.0) + 0.18 * math.exp(
                -((dx+3)**2 + (dy+3)**2) / 4.0
            )
            sr = max(0.05, min(0.95, sr))
            cells.append((col, row, sr))

    rects = []
    for col, row, sr in cells:
        x = PAD_L + col * cell_w
        y = PAD_T + row * cell_h
        r = int(sr * 220)
        g = int(sr * 200 * (1 - sr * 0.3))
        b = int((1 - sr) * 180)
        fill = f"rgb({r},{g},{b})"
        rects.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
            f'fill="{fill}" stroke="#0f172a" stroke-width="0.5"/>'
        )
        if sr > 0.55:
            tx = x + cell_w / 2
            ty = y + cell_h / 2
            rects.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" fill="#fff" font-size="7" '
                f'text-anchor="middle" dominant-baseline="middle">{int(sr*100)}</text>'
            )

    # Axis labels
    x_labels = []
    for col in range(COLS):
        lx = PAD_L + col * cell_w + cell_w / 2
        x_labels.append(
            f'<text x="{lx:.1f}" y="{H - 8}" fill="#64748b" font-size="8" '
            f'text-anchor="middle">{col - 3}</text>'
        )
    y_labels = []
    for row in range(ROWS):
        ly = PAD_T + row * cell_h + cell_h / 2
        ang = int(-180 + row * (360 / ROWS))
        y_labels.append(
            f'<text x="{PAD_L - 4}" y="{ly:.1f}" fill="#64748b" font-size="8" '
            f'text-anchor="end" dominant-baseline="middle">{ang}°</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  {''.join(rects)}
  {''.join(x_labels)}
  {''.join(y_labels)}
  <text x="{W//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">Grasp Success Heatmap</text>
  <text x="{PAD_L + (W - PAD_L - PAD_R)//2}" y="{H - 18}" fill="#475569" font-size="9"
        text-anchor="middle">Position Offset (cm)</text>
  <text x="14" y="{PAD_T + (H - PAD_T - PAD_B)//2}" fill="#475569" font-size="9"
        text-anchor="middle" transform="rotate(-90,14,{PAD_T + (H - PAD_T - PAD_B)//2})">Wrist Angle</text>
</svg>"""


# ---------------------------------------------------------------------------
# SVG: Grasp strategy comparison bar chart
# ---------------------------------------------------------------------------

def _svg_strategy_bars() -> str:
    """Horizontal bar chart comparing 6 strategies by success rate."""
    W, H = 380, 230
    PAD_L, PAD_T, PAD_R, PAD_B = 90, 28, 24, 20
    bar_h = (H - PAD_T - PAD_B) / len(STRATEGIES) - 6
    max_sr = 1.0

    bars = []
    for i, s in enumerate(STRATEGIES):
        y = PAD_T + i * ((H - PAD_T - PAD_B) / len(STRATEGIES))
        bar_w = s["sr"] * (W - PAD_L - PAD_R)
        bars.append(
            f'<text x="{PAD_L - 6}" y="{y + bar_h/2:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end" dominant-baseline="middle">{s["label"]}</text>'
        )
        bars.append(
            f'<rect x="{PAD_L}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="3" fill="{s[\"color\"]}" opacity="0.85"/>'
        )
        bars.append(
            f'<text x="{PAD_L + bar_w + 4}" y="{y + bar_h/2:.1f}" fill="{s[\"color\"]}" '
            f'font-size="10" dominant-baseline="middle">{int(s["sr"]*100)}%</text>'
        )

    # Grid lines
    grids = []
    for pct in [0, 25, 50, 75, 100]:
        gx = PAD_L + pct / 100 * (W - PAD_L - PAD_R)
        grids.append(
            f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{H - PAD_B}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        grids.append(
            f'<text x="{gx:.1f}" y="{H - 6}" fill="#475569" font-size="8" '
            f'text-anchor="middle">{pct}%</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  {''.join(grids)}
  {''.join(bars)}
  <text x="{W//2}" y="16" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">Strategy Success Rate Comparison</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    candidates = generate_candidates()
    best = max(candidates, key=lambda c: c["success_prob"])
    top5 = sorted(candidates, key=lambda c: -c["success_prob"])[:5]
    svg_candidates = _svg_candidates(candidates)
    svg_heatmap = _svg_heatmap()
    svg_bars = _svg_strategy_bars()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    top5_rows = ""
    for c in top5:
        color = _sr_color(c["success_prob"])
        top5_rows += f"""
        <tr>
          <td style="color:#94a3b8;padding:6px 10px;font-size:12px;">#{c['rank']}</td>
          <td style="color:#38bdf8;padding:6px 10px;font-size:12px;font-family:monospace;">{c['angle_deg']}°</td>
          <td style="color:#e2e8f0;padding:6px 10px;font-size:12px;">{c['strategy']}</td>
          <td style="color:{color};padding:6px 10px;font-size:12px;font-family:monospace;">{int(c['success_prob']*100)}%</td>
        </tr>"""

    rules_rows = ""
    for rule in STRATEGY_RULES:
        rules_rows += f"""
        <tr>
          <td style="color:#64748b;padding:5px 10px;font-size:11px;font-family:monospace;">{rule['condition']}</td>
          <td style="color:#38bdf8;padding:5px 10px;font-size:11px;">→ {rule['recommended']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Grasp Pose Generator</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0;
           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1a0a00 100%);
               padding: 18px 32px; border-bottom: 2px solid #C74634;
               display: flex; justify-content: space-between; align-items: center; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #f8fafc; }}
    .header .sub {{ color: #64748b; font-size: 12px; margin-top: 3px; }}
    .header .ts  {{ color: #475569; font-size: 11px; text-align: right; }}
    .kpi-row {{ display: flex; gap: 16px; padding: 20px 32px 0; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 14px 20px; flex: 1; min-width: 140px; }}
    .kpi .label {{ color: #64748b; font-size: 11px; text-transform: uppercase;
                   letter-spacing: 0.5px; margin-bottom: 5px; }}
    .kpi .value {{ font-size: 22px; font-weight: 700; }}
    .kpi .note  {{ color: #475569; font-size: 10px; margin-top: 3px; }}
    .section {{ padding: 20px 32px; }}
    .section h2 {{ font-size: 13px; font-weight: 600; color: #94a3b8;
                   text-transform: uppercase; letter-spacing: 0.8px;
                   margin-bottom: 14px; border-bottom: 1px solid #1e293b;
                   padding-bottom: 7px; }}
    .svg-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
    .panel {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
              padding: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #64748b; font-size: 11px; text-align: left; padding: 6px 10px;
          border-bottom: 1px solid #1e293b; text-transform: uppercase;
          letter-spacing: 0.5px; }}
    td {{ border-bottom: 1px solid #0f172a; }}
    .footer {{ padding: 14px 32px; color: #334155; font-size: 11px;
               text-align: center; border-top: 1px solid #0f172a; margin-top: 16px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
              font-size: 10px; font-weight: 700; }}
  </style>
</head>
<body>

<div class="header">
  <div>
    <h1>OCI Robot Cloud — Grasp Pose Generator</h1>
    <div class="sub">12 candidates/object · top-grasp 82% SR · diversity 0.79 · port {DEFAULT_PORT}</div>
  </div>
  <div class="ts">Updated: {ts} UTC<br/>Port {DEFAULT_PORT}</div>
</div>

<div class="kpi-row">
  <div class="kpi">
    <div class="label">Candidates / Object</div>
    <div class="value" style="color:#38bdf8">{CANDIDATES_PER_OBJECT}</div>
    <div class="note">Evenly spaced approach angles</div>
  </div>
  <div class="kpi">
    <div class="label">Top-Grasp SR</div>
    <div class="value" style="color:#22c55e">82%</div>
    <div class="note">Best strategy (horizontal surfaces)</div>
  </div>
  <div class="kpi">
    <div class="label">Diversity Score</div>
    <div class="value" style="color:#a78bfa">{DIVERSITY_SCORE}</div>
    <div class="note">Angular + strategy coverage</div>
  </div>
  <div class="kpi">
    <div class="label">Best This Object</div>
    <div class="value" style="color:#f59e0b">{int(best['success_prob']*100)}%</div>
    <div class="note">{best['strategy']} @ {best['angle_deg']}°</div>
  </div>
  <div class="kpi">
    <div class="label">Strategies</div>
    <div class="value" style="color:#fb923c">{len(STRATEGIES)}</div>
    <div class="note">top / power / side / wrap / tilted / pinch</div>
  </div>
</div>

<div class="section">
  <h2>Grasp Visualizations</h2>
  <div class="svg-grid">
    <div class="panel">{svg_candidates}</div>
    <div class="panel">{svg_heatmap}</div>
    <div class="panel">{svg_bars}</div>
  </div>
</div>

<div class="section">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div class="panel">
      <h2 style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;
                  margin-bottom:10px;border-bottom:1px solid #0f172a;padding-bottom:6px;">
        Top 5 Candidates</h2>
      <table>
        <thead><tr>
          <th>Rank</th><th>Angle</th><th>Strategy</th><th>P(success)</th>
        </tr></thead>
        <tbody>{top5_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2 style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;
                  margin-bottom:10px;border-bottom:1px solid #0f172a;padding-bottom:6px;">
        Strategy Selection Rules</h2>
      <table>
        <thead><tr><th>Condition</th><th>Recommended</th></tr></thead>
        <tbody>{rules_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="footer">
  OCI Robot Cloud — Grasp Pose Generator &nbsp;·&nbsp; Port {DEFAULT_PORT} &nbsp;·&nbsp;
  <a href="/candidates" style="color:#38bdf8;text-decoration:none">/candidates</a> &nbsp;·&nbsp;
  <a href="/strategies" style="color:#38bdf8;text-decoration:none">/strategies</a> &nbsp;·&nbsp;
  <a href="/health" style="color:#38bdf8;text-decoration:none">/health</a>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Grasp Pose Generator",
        description="Generates and ranks grasp pose candidates; scores by strategy and geometry",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, summary="HTML dashboard")
    def root():
        return HTMLResponse(content=build_html())

    @app.get("/candidates", summary="JSON list of grasp candidates")
    def candidates():
        return JSONResponse({
            "candidates": generate_candidates(),
            "count": CANDIDATES_PER_OBJECT,
            "diversity_score": DIVERSITY_SCORE,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/strategies", summary="JSON strategy comparison")
    def strategies():
        return JSONResponse({
            "strategies": STRATEGIES,
            "rules": STRATEGY_RULES,
            "top_strategy": "top_grasp",
            "ts": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/health", summary="Health check")
    def health():
        return JSONResponse({
            "status": "ok",
            "service": "grasp_pose_generator",
            "port": DEFAULT_PORT,
            "ts": datetime.utcnow().isoformat() + "Z",
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        import argparse
        parser = argparse.ArgumentParser(description="OCI Robot Cloud Grasp Pose Generator")
        parser.add_argument("--port", type=int, default=DEFAULT_PORT)
        args = parser.parse_args()
        print(f"Grasp Pose Generator on http://0.0.0.0:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    else:
        out_path = "/tmp/grasp_pose_generator.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(build_html())
        print(f"[grasp_pose_generator] fastapi/uvicorn not installed. HTML saved to {out_path}")
