"""scene_complexity_scorer.py — FastAPI service on port 8248

Scores Isaac Sim scene complexity to predict training difficulty
and compute requirements for OCI Robot Cloud SDG pipelines.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

import random
import math
import json
from datetime import datetime

random.seed(42)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SCENE_TYPES = ["tabletop", "warehouse", "kitchen", "outdoor"]
SCENE_TYPE_COLORS = {
    "tabletop": "#38bdf8",
    "warehouse": "#f59e0b",
    "kitchen":   "#C74634",
    "outdoor":   "#34d399",
}

def _make_scatter_data():
    """30 scene configs: complexity score (0-1) vs GPU-hours required."""
    points = []
    # anchors: kitchen highest, tabletop simplest
    anchors = [
        ("kitchen",   0.87, 42.0),
        ("tabletop",  0.31,  8.0),
        ("warehouse", 0.65, 26.0),
        ("outdoor",   0.74, 33.0),
    ]
    for t, cx, gy in anchors:
        points.append({"type": t, "complexity": cx, "gpu_hours": gy})

    counts = {"kitchen": 3, "tabletop": 3, "warehouse": 3, "outdoor": 3}
    for t, base_c, base_g in anchors:
        for _ in range(counts[t] - 1):
            c = max(0.1, min(0.99, base_c + random.uniform(-0.12, 0.12)))
            g = max(2.0, base_g + random.uniform(-5, 5) + (c - base_c) * 30)
            points.append({"type": t, "complexity": round(c, 3), "gpu_hours": round(g, 1)})

    # fill remaining to 30
    while len(points) < 30:
        t = random.choice(SCENE_TYPES)
        c = round(random.uniform(0.25, 0.92), 3)
        g = round(max(3, c * 48 + random.uniform(-4, 4)), 1)
        points.append({"type": t, "complexity": c, "gpu_hours": g})
    return points

SCATTER_DATA = _make_scatter_data()

# Regression line: y = a*x + b  (r²=0.91 anchored)
REG_SLOPE = 46.5
REG_INTERCEPT = -6.2
REG_R2 = 0.91

CANONICAL_SCENES = [
    {"name": "Tabletop-S",  "object_count": 4,  "lighting_sources": 2, "texture_variety": 3,  "physics_objects": 4,  "collision_complexity": 2, "camera_count": 2},
    {"name": "Tabletop-M",  "object_count": 8,  "lighting_sources": 3, "texture_variety": 5,  "physics_objects": 7,  "collision_complexity": 3, "camera_count": 3},
    {"name": "Warehouse-S", "object_count": 15, "lighting_sources": 4, "texture_variety": 6,  "physics_objects": 12, "collision_complexity": 5, "camera_count": 4},
    {"name": "Warehouse-M", "object_count": 28, "lighting_sources": 5, "texture_variety": 9,  "physics_objects": 22, "collision_complexity": 7, "camera_count": 5},
    {"name": "Kitchen-S",   "object_count": 22, "lighting_sources": 4, "texture_variety": 10, "physics_objects": 18, "collision_complexity": 8, "camera_count": 4},
    {"name": "Kitchen-M",   "object_count": 35, "lighting_sources": 6, "texture_variety": 14, "physics_objects": 30, "collision_complexity": 11,"camera_count": 6},
    {"name": "Outdoor-S",   "object_count": 20, "lighting_sources": 3, "texture_variety": 12, "physics_objects": 15, "collision_complexity": 6, "camera_count": 5},
    {"name": "Outdoor-M",   "object_count": 42, "lighting_sources": 5, "texture_variety": 18, "physics_objects": 35, "collision_complexity": 9, "camera_count": 7},
]

COMPLEXITY_KEYS = ["object_count", "lighting_sources", "texture_variety",
                   "physics_objects", "collision_complexity", "camera_count"]
COMPLEXITY_COLORS = ["#38bdf8", "#f59e0b", "#C74634", "#34d399", "#a78bfa", "#f472b6"]

# Normalisation weights for overall score
WEIGHTS = {"object_count": 0.25, "lighting_sources": 0.15, "texture_variety": 0.20,
           "physics_objects": 0.20, "collision_complexity": 0.12, "camera_count": 0.08}
MAX_VAL = {"object_count": 50, "lighting_sources": 8, "texture_variety": 20,
           "physics_objects": 40, "collision_complexity": 12, "camera_count": 8}

def scene_score(s):
    return round(sum(WEIGHTS[k] * s[k] / MAX_VAL[k] for k in WEIGHTS), 3)

for s in CANONICAL_SCENES:
    s["score"] = scene_score(s)

SCENE_REUSE_SCORE = 0.74
RECOMMENDED_TIER = "Tier-2 (0.5–0.75) for balanced SDG budget"
MEAN_COMPLEXITY = round(sum(p["complexity"] for p in SCATTER_DATA) / len(SCATTER_DATA), 3)

# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def _scatter_svg(width=640, height=340):
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    cx_min, cx_max = 0.1, 1.0
    gy_min, gy_max = 0.0, 55.0

    def tx(c):
        return pad_l + (c - cx_min) / (cx_max - cx_min) * plot_w

    def ty(g):
        return pad_t + plot_h - (g - gy_min) / (gy_max - gy_min) * plot_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{width//2}" y="14" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">',
        'Scene Complexity Score vs Training Compute (GPU-hrs) — r²=0.91</text>',
    ]

    # grid
    for v in [0.2, 0.4, 0.6, 0.8]:
        x = tx(v)
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{pad_t+plot_h+12}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{v}</text>')
    for v in [10, 20, 30, 40, 50]:
        y = ty(v)
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v}</text>')

    # axis labels
    lines.append(f'<text x="{pad_l+plot_w//2}" y="{height-4}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Complexity Score</text>')
    lines.append(f'<text x="12" y="{pad_t+plot_h//2}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,12,{pad_t+plot_h//2})">GPU-Hours</text>')

    # regression line
    x1r, x2r = 0.15, 0.95
    y1r = REG_SLOPE * x1r + REG_INTERCEPT
    y2r = REG_SLOPE * x2r + REG_INTERCEPT
    lines.append(f'<line x1="{tx(x1r):.1f}" y1="{ty(y1r):.1f}" x2="{tx(x2r):.1f}" y2="{ty(y2r):.1f}" stroke="#f8fafc" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5"/>')
    lines.append(f'<text x="{tx(0.78):.1f}" y="{ty(REG_SLOPE*0.78+REG_INTERCEPT)-6:.1f}" fill="#f8fafc" font-size="9" font-family="monospace" opacity="0.7">r²=0.91</text>')

    # points
    for p in SCATTER_DATA:
        x, y = tx(p["complexity"]), ty(p["gpu_hours"])
        col = SCENE_TYPE_COLORS[p["type"]]
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{col}" opacity="0.85" stroke="#0f172a" stroke-width="1"/>')

    # legend
    lx, ly = pad_l + 4, pad_t + 4
    for i, (t, col) in enumerate(SCENE_TYPE_COLORS.items()):
        ox = lx + i * 100
        lines.append(f'<circle cx="{ox+6}" cy="{ly+5}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{ox+14}" y="{ly+9}" fill="#cbd5e1" font-size="9" font-family="monospace">{t}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _stacked_bar_svg(width=640, height=340):
    pad_l, pad_r, pad_t, pad_b = 70, 20, 25, 70
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    n = len(CANONICAL_SCENES)
    bar_w = plot_w / n * 0.7
    gap = plot_w / n

    # compute stacks (normalise each component 0-1 then weight)
    max_total = max(
        sum(s[k] / MAX_VAL[k] * 100 for k in COMPLEXITY_KEYS)
        for s in CANONICAL_SCENES
    )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{width//2}" y="16" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">',
        'Scene Complexity Components — 8 Canonical Scenes</text>',
    ]

    # y grid
    for pct in [25, 50, 75, 100]:
        y = pad_t + plot_h - pct / 100 * plot_h
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{pct}%</text>')

    for i, scene in enumerate(CANONICAL_SCENES):
        cx = pad_l + i * gap + gap / 2 - bar_w / 2
        base = 0.0
        total = sum(scene[k] / MAX_VAL[k] * 100 for k in COMPLEXITY_KEYS)
        for ki, key in enumerate(COMPLEXITY_KEYS):
            val = scene[key] / MAX_VAL[key] * 100
            seg_pct = val / max_total
            seg_h = seg_pct * plot_h
            y = pad_t + plot_h - (base + val) / max_total * plot_h
            lines.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{seg_h:.1f}" fill="{COMPLEXITY_COLORS[ki]}" opacity="0.85"/>')
            base += val
        # scene name
        lines.append(f'<text x="{cx+bar_w/2:.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#94a3b8" font-size="8" font-family="monospace" transform="rotate(35,{cx+bar_w/2:.1f},{pad_t+plot_h+14})">{scene["name"]}</text>')
        # score label
        bar_top = pad_t + plot_h - total / max_total * plot_h
        lines.append(f'<text x="{cx+bar_w/2:.1f}" y="{bar_top-3:.1f}" text-anchor="middle" fill="#f8fafc" font-size="8" font-family="monospace">{scene["score"]}</text>')

    # legend
    lx, ly = pad_l, height - 18
    for ki, key in enumerate(COMPLEXITY_KEYS):
        ox = lx + ki * 94
        lines.append(f'<rect x="{ox}" y="{ly}" width="8" height="8" fill="{COMPLEXITY_COLORS[ki]}" opacity="0.85"/>')
        label = key.replace("_", " ")
        lines.append(f'<text x="{ox+10}" y="{ly+8}" fill="#cbd5e1" font-size="8" font-family="monospace">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html():
    scatter = _scatter_svg()
    stacked = _stacked_bar_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    top_complex = max(CANONICAL_SCENES, key=lambda s: s["score"])
    top_simple  = min(CANONICAL_SCENES, key=lambda s: s["score"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Scene Complexity Scorer — Port 8248</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.35rem; margin-bottom: 4px; }}
    h2   {{ color: #38bdf8; font-size: 1rem; margin: 20px 0 8px; }}
    .sub {{ color: #64748b; font-size: 0.8rem; margin-bottom: 20px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .card  {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
              padding: 16px 20px; min-width: 160px; flex: 1; }}
    .card .val  {{ font-size: 1.6rem; color: #38bdf8; font-weight: bold; }}
    .card .lbl  {{ font-size: 0.72rem; color: #94a3b8; margin-top: 4px; }}
    .card.red .val {{ color: #C74634; }}
    .chart {{ margin-bottom: 28px; }}
    .rec   {{ background: #1e293b; border-left: 3px solid #C74634; padding: 10px 16px;
              border-radius: 4px; font-size: 0.82rem; color: #94a3b8; margin-bottom: 20px; }}
    table  {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
    th     {{ background: #1e293b; color: #38bdf8; padding: 8px; text-align: left; }}
    td     {{ padding: 6px 8px; border-top: 1px solid #1e293b; }}
    tr:nth-child(even) td {{ background: #0f172a; }}
    .tag   {{ display: inline-block; padding: 2px 6px; border-radius: 4px;
              font-size: 0.7rem; font-weight: bold; }}
    .ts    {{ color: #334155; font-size: 0.7rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Isaac Sim Scene Complexity Scorer</h1>
  <p class="sub">Port 8248 &nbsp;|&nbsp; Predicts training difficulty and OCI GPU compute requirements</p>

  <div class="cards">
    <div class="card">
      <div class="val">{MEAN_COMPLEXITY}</div>
      <div class="lbl">Mean Complexity Score (30 configs)</div>
    </div>
    <div class="card red">
      <div class="val">{top_complex['score']}</div>
      <div class="lbl">Highest: {top_complex['name']}</div>
    </div>
    <div class="card">
      <div class="val">{top_simple['score']}</div>
      <div class="lbl">Lowest: {top_simple['name']}</div>
    </div>
    <div class="card">
      <div class="val">{REG_R2}</div>
      <div class="lbl">Complexity–Compute Correlation r²</div>
    </div>
    <div class="card">
      <div class="val">{SCENE_REUSE_SCORE}</div>
      <div class="lbl">Scene Reuse Score</div>
    </div>
  </div>

  <div class="rec">
    Recommendation: {RECOMMENDED_TIER} — use 3–4 lighting sources for optimal quality/cost.
  </div>

  <h2>Scatter: Complexity vs Compute (GPU-hrs)</h2>
  <div class="chart">{scatter}</div>

  <h2>Stacked Bar: Complexity Components per Canonical Scene</h2>
  <div class="chart">{stacked}</div>

  <h2>Canonical Scene Details</h2>
  <table>
    <tr><th>Scene</th><th>Score</th><th>Objects</th><th>Lights</th><th>Textures</th>
        <th>Physics</th><th>Collision</th><th>Cameras</th></tr>
    {''.join(f"<tr><td>{s['name']}</td><td><strong style='color:#38bdf8'>{s['score']}</strong></td>"
              + f"<td>{s['object_count']}</td><td>{s['lighting_sources']}</td>"
              + f"<td>{s['texture_variety']}</td><td>{s['physics_objects']}</td>"
              + f"<td>{s['collision_complexity']}</td><td>{s['camera_count']}</td></tr>"
              for s in CANONICAL_SCENES)}
  </table>

  <p class="ts">Generated: {ts} UTC</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Scene Complexity Scorer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "scene_complexity_scorer", "port": 8248}

    @app.get("/api/scores")
    async def api_scores():
        return {
            "canonical_scenes": CANONICAL_SCENES,
            "scatter_data": SCATTER_DATA,
            "regression": {"slope": REG_SLOPE, "intercept": REG_INTERCEPT, "r2": REG_R2},
            "mean_complexity": MEAN_COMPLEXITY,
            "scene_reuse_score": SCENE_REUSE_SCORE,
            "recommended_tier": RECOMMENDED_TIER,
        }

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence access log
            pass


if __name__ == "__main__":
    PORT = 8248
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib server on port {PORT}")
        with socketserver.TCPServer(("", PORT), _Handler) as srv:
            print(f"Serving on http://0.0.0.0:{PORT}")
            srv.serve_forever()
