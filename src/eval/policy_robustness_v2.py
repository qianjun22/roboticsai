"""Policy Robustness V2 — FastAPI port 8846"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8846

# 12 perturbation categories with robustness scores
PERTURBATIONS = [
    ("lighting",         0.81),
    ("texture",          0.78),
    ("clutter",          0.61),
    ("noise",            0.76),
    ("occlusion",        0.52),
    ("velocity",         0.72),
    ("mass",             0.79),
    ("friction",         0.74),
    ("camera_angle",     0.68),
    ("distractor",       0.65),
    ("delay",            0.70),
    ("calibration_err",  0.66),
]

# Per-model scores (GR00T_v2, BC, DAgger_r9)
MODEL_SCORES = {
    "GR00T_v2":  [0.81, 0.78, 0.61, 0.76, 0.52, 0.72, 0.79, 0.74, 0.68, 0.65, 0.70, 0.66],
    "BC":        [0.62, 0.59, 0.44, 0.58, 0.38, 0.55, 0.61, 0.57, 0.50, 0.47, 0.52, 0.49],
    "DAgger_r9": [0.74, 0.71, 0.55, 0.69, 0.46, 0.66, 0.72, 0.68, 0.62, 0.59, 0.64, 0.61],
}

def _radar_points(scores, cx, cy, r):
    """Convert N scores (0-1) to SVG polygon points on a radar chart."""
    n = len(scores)
    pts = []
    for i, s in enumerate(scores):
        angle = math.pi / 2 - 2 * math.pi * i / n   # start at top
        dist = s * r
        x = cx + dist * math.cos(angle)
        y = cy - dist * math.sin(angle)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)

def _radar_axis_label(i, n, cx, cy, r, label):
    angle = math.pi / 2 - 2 * math.pi * i / n
    x = cx + (r + 22) * math.cos(angle)
    y = cy - (r + 22) * math.sin(angle)
    anchor = "middle"
    if x < cx - 5:  anchor = "end"
    elif x > cx + 5: anchor = "start"
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="10" fill="#94a3b8">{label}</text>'

def build_html():
    cx, cy, r = 260, 270, 180
    n = len(PERTURBATIONS)
    labels = [p[0] for p in PERTURBATIONS]

    # Grid rings at 25%, 50%, 75%, 100%
    rings = ""
    for pct in [0.25, 0.50, 0.75, 1.0]:
        pts = _radar_points([pct] * n, cx, cy, r)
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
        rings += f'<text x="{cx+4:.1f}" y="{cy - pct*r - 3:.1f}" font-size="9" fill="#475569">{int(pct*100)}%</text>'

    # Axis lines
    axes = ""
    for i in range(n):
        angle = math.pi / 2 - 2 * math.pi * i / n
        x2 = cx + r * math.cos(angle)
        y2 = cy - r * math.sin(angle)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>'

    # Axis labels
    axis_labels = "".join(_radar_axis_label(i, n, cx, cy, r, labels[i]) for i in range(n))

    # Model polygons
    colors = {"GR00T_v2": "#38bdf8", "BC": "#f97316", "DAgger_r9": "#a78bfa"}
    polys = ""
    for model, scores in MODEL_SCORES.items():
        pts = _radar_points(scores, cx, cy, r)
        c = colors[model]
        polys += f'<polygon points="{pts}" fill="{c}" fill-opacity="0.15" stroke="{c}" stroke-width="2"/>'

    # Legend
    legend = ""
    for idx, (model, c) in enumerate(colors.items()):
        lx, ly = 460, 160 + idx * 28
        avg = sum(MODEL_SCORES[model]) / n
        legend += f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{c}" rx="2"/>'
        legend += f'<text x="{lx+20}" y="{ly+12}" font-size="12" fill="#e2e8f0">{model} (avg {avg:.2f})</text>'

    # Metric cards
    cards = ""
    metrics = [
        ("Overall Robustness", "0.74", "GR00T_v2 composite"),
        ("Worst-case (Occlusion)", "SR = 0.52", "hardest perturbation"),
        ("Clutter SR", "0.61", "second hardest"),
        ("vs BC improvement", "+26%", "GR00T_v2 vs BC avg"),
        ("vs DAgger_r9", "+8%", "GR00T_v2 vs DAgger avg"),
        ("Perturbation categories", "12", "tested"),
    ]
    for i, (title, val, sub) in enumerate(metrics):
        col, row = i % 3, i // 3
        mx, my = 30 + col * 190, 580 + row * 80
        cards += f'<rect x="{mx}" y="{my}" width="175" height="65" rx="6" fill="#1e293b"/>'
        cards += f'<text x="{mx+10}" y="{my+18}" font-size="10" fill="#94a3b8">{title}</text>'
        cards += f'<text x="{mx+10}" y="{my+42}" font-size="20" font-weight="bold" fill="#38bdf8">{val}</text>'
        cards += f'<text x="{mx+10}" y="{my+58}" font-size="9" fill="#64748b">{sub}</text>'

    svg = f"""
    <svg width="600" height="760" xmlns="http://www.w3.org/2000/svg">
      <rect width="600" height="760" fill="#0f172a" rx="12"/>
      <text x="300" y="32" text-anchor="middle" font-size="16" font-weight="bold" fill="#C74634">Policy Robustness V2 — Radar Chart</text>
      <text x="300" y="52" text-anchor="middle" font-size="11" fill="#64748b">GR00T_v2 vs BC vs DAgger_r9 across 12 perturbation categories</text>
      {rings}{axes}{axis_labels}{polys}{legend}{cards}
    </svg>"""

    return f"""<!DOCTYPE html><html><head><title>Policy Robustness V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.meta{{color:#64748b;font-size:13px;padding:0 20px 10px}}</style></head>
<body>
<h1>Policy Robustness V2</h1>
<p class="meta">Port {PORT} &mdash; 12 perturbation categories &mdash; GR00T_v2 / BC / DAgger_r9</p>
<div class="card">
  <h2>Robustness Radar</h2>
  {svg}
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Robustness V2")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        n = len(PERTURBATIONS)
        return {
            "port": PORT,
            "overall_robustness": 0.74,
            "worst_case": {"category": "occlusion", "sr": 0.52},
            "clutter_sr": 0.61,
            "categories_tested": n,
            "models": {
                model: {"avg": round(sum(s) / n, 3), "scores": dict(zip([p[0] for p in PERTURBATIONS], s))}
                for model, s in MODEL_SCORES.items()
            },
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
