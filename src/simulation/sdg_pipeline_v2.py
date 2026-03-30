"""SDG Pipeline v2 — FastAPI service on port 8295.

SDG (Synthetic Data Generation) pipeline v2 with Cosmos world model
integration and Genesis physics backend. Tracks per-stage throughput,
quality metrics, and v1→v2 migration recommendations.
"""

import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Pipeline data
# ---------------------------------------------------------------------------

STAGES = [
    {
        "name": "scene_gen",
        "label": "Scene Gen",
        "v1_fps": 18,
        "v2_fps": 32,
        "v1_demos_hr": 38,
        "v2_demos_hr": 66,
        "improvement": "+73%",
        "notes": "Cosmos WM procedural layout",
    },
    {
        "name": "physics_sim",
        "label": "Physics Sim",
        "v1_fps": 95,
        "v2_fps": 148,
        "v1_demos_hr": 210,
        "v2_demos_hr": 320,
        "improvement": "+52%",
        "notes": "Genesis GPU-parallel sim",
    },
    {
        "name": "rendering",
        "label": "Rendering",
        "v1_fps": 24,
        "v2_fps": 40,
        "v1_demos_hr": 186,
        "v2_demos_hr": 312,
        "improvement": "+67%",
        "notes": "RTX domain randomisation",
    },
    {
        "name": "post_process",
        "label": "Post-Process",
        "v1_fps": 120,
        "v2_fps": 185,
        "v1_demos_hr": 410,
        "v2_demos_hr": 620,
        "improvement": "+51%",
        "notes": "Async annotation pipeline",
    },
    {
        "name": "export",
        "label": "Export",
        "v1_fps": 200,
        "v2_fps": 280,
        "v1_demos_hr": 820,
        "v2_demos_hr": 1100,
        "improvement": "+34%",
        "notes": "Parallel HDF5 write",
    },
]

# Quality radar — 6 axes, score 0.0–1.0
QUALITY_AXES = [
    {"axis": "physics_realism",   "v1": 0.82, "v2": 0.85},
    {"axis": "visual_fidelity",   "v1": 0.71, "v2": 0.89},
    {"axis": "diversity",         "v1": 0.68, "v2": 0.74},
    {"axis": "sim2real_gap",      "v1": 0.79, "v2": 0.87},
    {"axis": "generation_cost",   "v1": 0.88, "v2": 0.83},  # lower cost = worse score here (higher is cheaper)
    {"axis": "annotation_quality","v1": 0.77, "v2": 0.81},
]

OVERALL_V1_DEMOS_HR = 186
OVERALL_V2_DEMOS_HR = 312
OVERALL_IMPROVEMENT = round((OVERALL_V2_DEMOS_HR - OVERALL_V1_DEMOS_HR) / OVERALL_V1_DEMOS_HR * 100)

COST_V1_PER_1K = 0.12  # $ per 1k frames
COST_V2_PER_1K = 0.17

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _build_throughput_svg() -> str:
    """Grouped bar chart comparing v1 vs v2 demos/hr per stage."""
    W, H = 680, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 36, 60
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    n = len(STAGES)
    group_w = plot_w / n
    bar_w = group_w * 0.35
    max_val = max(max(s["v1_demos_hr"], s["v2_demos_hr"]) for s in STAGES)
    max_val = max(max_val, 1)

    def bar_y(val):
        return PAD_T + plot_h - val / max_val * plot_h

    def bar_h(val):
        return val / max_val * plot_h

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    parts.append(f'<text x="{W//2}" y="22" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Pipeline Stage Throughput — v1 vs v2 (demos/hr)</text>')

    # Grid
    for tick in [200, 400, 600, 800, 1000]:
        if tick > max_val:
            break
        gy = bar_y(tick)
        parts.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="#334155" stroke-width="0.5"/>')
        parts.append(f'<text x="{PAD_L-4}" y="{gy+4:.1f}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{tick}</text>')

    for i, stage in enumerate(STAGES):
        gx = PAD_L + i * group_w
        cx = gx + group_w / 2

        # v1 bar (left)
        b1x = cx - bar_w - 2
        b1y = bar_y(stage["v1_demos_hr"])
        b1h = bar_h(stage["v1_demos_hr"])
        parts.append(f'<rect x="{b1x:.1f}" y="{b1y:.1f}" width="{bar_w:.1f}" height="{b1h:.1f}" fill="#475569" rx="2"/>')
        parts.append(f'<text x="{b1x+bar_w/2:.1f}" y="{b1y-3:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{stage["v1_demos_hr"]}</text>')

        # v2 bar (right)
        b2x = cx + 2
        b2y = bar_y(stage["v2_demos_hr"])
        b2h = bar_h(stage["v2_demos_hr"])
        parts.append(f'<rect x="{b2x:.1f}" y="{b2y:.1f}" width="{bar_w:.1f}" height="{b2h:.1f}" fill="#38bdf8" rx="2"/>')
        parts.append(f'<text x="{b2x+bar_w/2:.1f}" y="{b2y-3:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle" font-family="monospace">{stage["v2_demos_hr"]}</text>')

        # improvement badge
        parts.append(f'<text x="{cx:.1f}" y="{PAD_T+plot_h+14}" fill="#22c55e" font-size="9" text-anchor="middle" font-family="monospace">{stage["improvement"]}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{PAD_T+plot_h+28}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{stage["label"]}</text>')

    # Axes
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>')
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{W-PAD_R}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>')

    # Legend
    parts.append(f'<rect x="{PAD_L}" y="{H-14}" width="10" height="10" fill="#475569" rx="2"/>')
    parts.append(f'<text x="{PAD_L+13}" y="{H-5}" fill="#94a3b8" font-size="10" font-family="monospace">v1 (baseline)</text>')
    parts.append(f'<rect x="{PAD_L+130}" y="{H-14}" width="10" height="10" fill="#38bdf8" rx="2"/>')
    parts.append(f'<text x="{PAD_L+143}" y="{H-5}" fill="#94a3b8" font-size="10" font-family="monospace">v2 (Cosmos+Genesis)</text>')

    parts.append('</svg>')
    return ''.join(parts)


def _build_radar_svg() -> str:
    """Radar/spider chart comparing v1 vs v2 quality across 6 axes."""
    W, H = 380, 320
    cx, cy = W // 2, H // 2 + 10
    R = 110
    n = len(QUALITY_AXES)
    
    def polar(angle_deg, r):
        rad = math.radians(angle_deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    angles = [i * 360 / n for i in range(n)]

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    parts.append(f'<text x="{W//2}" y="22" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Demo Quality Radar — v1 vs v2</text>')

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = " ".join(f"{polar(a, R*ring)[0]:.1f},{polar(a, R*ring)[1]:.1f}" for a in angles)
        parts.append(f'<polygon points="{ring_pts}" fill="none" stroke="#334155" stroke-width="0.8"/>')

    # Spokes
    for a, ax_data in zip(angles, QUALITY_AXES):
        ox, oy = polar(a, 0)
        ex, ey = polar(a, R)
        parts.append(f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>')
        lx, ly = polar(a, R + 22)
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#64748b" font-size="8.5" text-anchor="middle" font-family="monospace">{ax_data["axis"].replace("_"," ")}</text>')

    def poly_pts(key):
        pts = []
        for a, ax in zip(angles, QUALITY_AXES):
            score = ax[key]
            x, y = polar(a, R * score)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    # v1 polygon
    parts.append(f'<polygon points="{poly_pts("v1")}" fill="#475569" fill-opacity="0.3" stroke="#94a3b8" stroke-width="1.5"/>')
    # v2 polygon
    parts.append(f'<polygon points="{poly_pts("v2")}" fill="#38bdf8" fill-opacity="0.25" stroke="#38bdf8" stroke-width="2"/>')

    # Data point dots for v2
    for a, ax in zip(angles, QUALITY_AXES):
        px, py = polar(a, R * ax["v2"])
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="#38bdf8"/>')
        px1, py1 = polar(a, R * ax["v1"])
        parts.append(f'<circle cx="{px1:.1f}" cy="{py1:.1f}" r="3" fill="#94a3b8" opacity="0.7"/>')

    # Legend
    lx = 20
    parts.append(f'<rect x="{lx}" y="{H-20}" width="10" height="10" fill="#475569" opacity="0.7" rx="2"/>')
    parts.append(f'<text x="{lx+13}" y="{H-11}" fill="#94a3b8" font-size="10" font-family="monospace">v1</text>')
    parts.append(f'<rect x="{lx+50}" y="{H-20}" width="10" height="10" fill="#38bdf8" opacity="0.8" rx="2"/>')
    parts.append(f'<text x="{lx+63}" y="{H-11}" fill="#94a3b8" font-size="10" font-family="monospace">v2</text>')

    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    throughput_svg = _build_throughput_svg()
    radar_svg = _build_radar_svg()

    v2_improved = sum(1 for ax in QUALITY_AXES if ax["v2"] > ax["v1"])
    avg_v1 = round(sum(ax["v1"] for ax in QUALITY_AXES) / len(QUALITY_AXES), 3)
    avg_v2 = round(sum(ax["v2"] for ax in QUALITY_AXES) / len(QUALITY_AXES), 3)
    cost_delta = round((COST_V2_PER_1K - COST_V1_PER_1K) / COST_V1_PER_1K * 100, 1)
    migration_rec = "RECOMMENDED" if OVERALL_IMPROVEMENT >= 50 else "EVALUATE"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SDG Pipeline v2 | Port 8295</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.8rem; margin-bottom: 20px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; }}
  .card .val {{ font-size: 1.6rem; font-weight: bold; color: #38bdf8; }}
  .card .val.green {{ color: #22c55e; }}
  .card .val.warn {{ color: #f59e0b; }}
  .card .lbl {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
  .charts {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 24px; }}
  @media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
  .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px; }}
  .stages-table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  .stages-table th {{ color: #38bdf8; border-bottom: 1px solid #334155; padding: 6px 8px; text-align: left; }}
  .stages-table td {{ padding: 5px 8px; border-bottom: 1px solid #1e293b; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: 0.7rem; font-weight: bold; }}
  .badge-green {{ background: #0f2a1a; color: #22c55e; border: 1px solid #22c55e; }}
  .badge-blue {{ background: #0f2233; color: #38bdf8; border: 1px solid #38bdf8; }}
  footer {{ color: #334155; font-size: 0.72rem; margin-top: 24px; }}
</style>
</head>
<body>
<h1>SDG Pipeline v2</h1>
<p class="subtitle">Port 8295 &mdash; Cosmos World Model + Genesis Physics Backend &mdash; v1&rarr;v2 migration dashboard</p>

<div class="metrics">
  <div class="card"><div class="val">{OVERALL_V1_DEMOS_HR}</div><div class="lbl">v1 demos/hr (rendering)</div></div>
  <div class="card"><div class="val green">{OVERALL_V2_DEMOS_HR}</div><div class="lbl">v2 demos/hr (+{OVERALL_IMPROVEMENT}%)</div></div>
  <div class="card"><div class="val">{v2_improved}/6</div><div class="lbl">Quality axes improved</div></div>
  <div class="card"><div class="val">{avg_v1}</div><div class="lbl">Avg quality score v1</div></div>
  <div class="card"><div class="val green">{avg_v2}</div><div class="lbl">Avg quality score v2</div></div>
  <div class="card"><div class="val warn">${COST_V1_PER_1K}&rarr;${COST_V2_PER_1K}</div><div class="lbl">Cost/1k frames (+{cost_delta}%)</div></div>
  <div class="card"><div class="val green" style="font-size:1.1rem">{migration_rec}</div><div class="lbl">Migration recommendation</div></div>
</div>

<div class="charts">
  <div class="chart-box">
    <h2>Stage Throughput: v1 vs v2</h2>
    {throughput_svg}
  </div>
  <div class="chart-box">
    <h2>Quality Radar (6 Axes)</h2>
    {radar_svg}
  </div>
</div>

<div class="chart-box" style="margin-bottom:20px">
  <h2>Stage Details</h2>
  <table class="stages-table">
    <thead><tr><th>Stage</th><th>v1 FPS</th><th>v2 FPS</th><th>v1 demos/hr</th><th>v2 demos/hr</th><th>Improvement</th><th>Notes</th></tr></thead>
    <tbody>
    {''.join(f"<tr><td>{s['label']}</td><td>{s['v1_fps']}</td><td><b>{s['v2_fps']}</b></td><td>{s['v1_demos_hr']}</td><td><b>{s['v2_demos_hr']}</b></td><td><span class='badge badge-green'>{s['improvement']}</span></td><td style='color:#64748b'>{s['notes']}</td></tr>" for s in STAGES)}
    </tbody>
  </table>
</div>

<div class="chart-box" style="margin-bottom:20px">
  <h2>Quality Dimension Details</h2>
  <table class="stages-table">
    <thead><tr><th>Axis</th><th>v1 Score</th><th>v2 Score</th><th>Delta</th><th>Driver</th></tr></thead>
    <tbody>
    {''.join(f"<tr><td>{ax['axis'].replace('_',' ')}</td><td>{ax['v1']:.2f}</td><td><b>{ax['v2']:.2f}</b></td><td style='color:{\"#22c55e\" if ax[\"v2\"]>ax[\"v1\"] else \"#ef4444\"}'>{('+' if ax['v2']>=ax['v1'] else '')}{ax['v2']-ax['v1']:+.2f}</td><td style='color:#64748b'>{('Cosmos WM visual gen' if ax['axis']=='visual_fidelity' else 'Genesis physics' if ax['axis']=='physics_realism' else 'Domain rand' if ax['axis']=='sim2real_gap' else 'Cosmos diversity' if ax['axis']=='diversity' else 'Higher render cost' if ax['axis']=='generation_cost' else 'Auto-label pipeline')}</td></tr>" for ax in QUALITY_AXES)}
    </tbody>
  </table>
</div>

<footer>OCI Robot Cloud &mdash; SDG Pipeline v2.0 &mdash; Cosmos + Genesis &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app / stdlib fallback
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="SDG Pipeline v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sdg_pipeline_v2", "port": 8295}

    @app.get("/metrics")
    async def metrics():
        return {
            "overall_v1_demos_hr": OVERALL_V1_DEMOS_HR,
            "overall_v2_demos_hr": OVERALL_V2_DEMOS_HR,
            "overall_improvement_pct": OVERALL_IMPROVEMENT,
            "quality_axes_improved": sum(1 for ax in QUALITY_AXES if ax["v2"] > ax["v1"]),
            "cost_v1_per_1k_frames": COST_V1_PER_1K,
            "cost_v2_per_1k_frames": COST_V2_PER_1K,
            "migration_recommendation": "recommended",
        }

    @app.get("/stages")
    async def stages():
        return STAGES

    @app.get("/quality")
    async def quality():
        return QUALITY_AXES

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8295)
    else:
        print("FastAPI not available — using stdlib HTTP server on port 8295")
        HTTPServer(("0.0.0.0", 8295), _Handler).serve_forever()
