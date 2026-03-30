"""
policy_ensemble_v2.py — OCI Robot Cloud  (port 8658)
Ensemble strategy comparison: SR vs latency, reliability calibration, per-task weights.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import json
from datetime import datetime

# ── colour palette ────────────────────────────────────────────────────────────
BG      = "#0f172a"
SURFACE = "#1e293b"
BORDER  = "#334155"
RED     = "#C74634"
BLUE    = "#38bdf8"
GREEN   = "#4ade80"
AMBER   = "#fbbf24"
PURPLE  = "#a78bfa"
SLATE   = "#94a3b8"
WHITE   = "#f1f5f9"

# ── ensemble strategy data ────────────────────────────────────────────────────
STRATEGIES = [
    {"name": "single",            "latency_ms": 231,  "sr": 0.68, "color": SLATE,  "online": False},
    {"name": "voting-2",          "latency_ms": 298,  "sr": 0.76, "color": BLUE,   "online": False},
    {"name": "voting-3",          "latency_ms": 374,  "sr": 0.84, "color": GREEN,  "online": False},
    {"name": "weighted",          "latency_ms": 389,  "sr": 0.81, "color": AMBER,  "online": False},
    {"name": "uncertainty_gated", "latency_ms": 382,  "sr": 0.82, "color": RED,    "online": True},
    {"name": "stochastic",        "latency_ms": 261,  "sr": 0.53, "color": PURPLE, "online": False},
]

# ── reliability diagram data ──────────────────────────────────────────────────
RELIABILITY_BINS = [
    {"conf": 0.05, "single": 0.07, "ensemble": 0.06},
    {"conf": 0.15, "single": 0.11, "ensemble": 0.14},
    {"conf": 0.25, "single": 0.19, "ensemble": 0.24},
    {"conf": 0.35, "single": 0.26, "ensemble": 0.34},
    {"conf": 0.45, "single": 0.33, "ensemble": 0.44},
    {"conf": 0.55, "single": 0.41, "ensemble": 0.54},
    {"conf": 0.65, "single": 0.52, "ensemble": 0.63},
    {"conf": 0.75, "single": 0.61, "ensemble": 0.74},
    {"conf": 0.85, "single": 0.70, "ensemble": 0.84},
    {"conf": 0.95, "single": 0.78, "ensemble": 0.93},
]

# ── per-task ensemble weights ─────────────────────────────────────────────────
TASKS = ["lift", "stack", "push", "grasp", "pour", "assemble"]
MODELS = [
    {"name": "GR00T_v2",  "color": BLUE,   "weights": [0.51, 0.44, 0.48, 0.55, 0.39, 0.52]},
    {"name": "dagger_r9", "color": GREEN,  "weights": [0.32, 0.38, 0.35, 0.28, 0.42, 0.31]},
    {"name": "BC",        "color": AMBER,  "weights": [0.17, 0.18, 0.17, 0.17, 0.19, 0.17]},
]


# ══════════════════════════════════════════════════════════════════════════════
# SVG helpers
# ══════════════════════════════════════════════════════════════════════════════

def _scatter_svg() -> str:
    """Ensemble SR vs latency scatter with Pareto frontier."""
    W, H = 560, 380
    PAD = {"l": 60, "r": 140, "t": 40, "b": 55}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]

    lat_min, lat_max = 220, 410
    sr_min,  sr_max  = 0.45, 0.90

    def tx(lat):
        return PAD["l"] + (lat - lat_min) / (lat_max - lat_min) * pw

    def ty(sr):
        return PAD["t"] + ph - (sr - sr_min) / (sr_max - sr_min) * ph

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Ensemble SR vs Latency</text>',
        # axes
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]+ph}" x2="{PAD["l"]+pw}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        # axis labels
        f'<text x="{PAD["l"]+pw//2}" y="{H-8}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11">Latency (ms)</text>',
        f'<text x="14" y="{PAD["t"]+ph//2}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11" transform="rotate(-90,14,{PAD["t"]+ph//2})">Success Rate</text>',
    ]

    # grid lines
    for sr_v in [0.5, 0.6, 0.7, 0.8, 0.9]:
        y = ty(sr_v)
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" '
                     f'stroke="{BORDER}" stroke-width="0.5" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{PAD["l"]-6}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="{SLATE}" font-size="10">{sr_v:.1f}</text>')

    for lat_v in [250, 300, 350, 400]:
        x = tx(lat_v)
        lines.append(f'<line x1="{x:.1f}" y1="{PAD["t"]}" x2="{x:.1f}" y2="{PAD["t"]+ph}" '
                     f'stroke="{BORDER}" stroke-width="0.5" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{x:.1f}" y="{PAD["t"]+ph+15}" text-anchor="middle" '
                     f'fill="{SLATE}" font-size="10">{lat_v}</text>')

    # Pareto frontier (non-dominated: higher SR OR lower latency)
    pareto = [s for s in STRATEGIES if s["name"] in ("single", "voting-2", "voting-3", "uncertainty_gated")]
    pareto_sorted = sorted(pareto, key=lambda s: s["latency_ms"])
    pts = " ".join(f"{tx(s['latency_ms']):.1f},{ty(s['sr']):.1f}" for s in pareto_sorted)
    lines.append(f'<polyline points="{pts}" fill="none" stroke="{GREEN}" '
                 f'stroke-width="1.5" stroke-dasharray="6,3" opacity="0.6"/>')
    lines.append(f'<text x="{tx(340):.1f}" y="{ty(0.79):.1f}" fill="{GREEN}" '
                 f'font-size="10" opacity="0.8">Pareto frontier</text>')

    # scatter points
    for s in STRATEGIES:
        cx = tx(s["latency_ms"])
        cy = ty(s["sr"])
        r = 9 if s["online"] else 7
        sw = "2.5" if s["online"] else "1.5"
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
                     f'fill="{s["color"]}" fill-opacity="0.25" '
                     f'stroke="{s["color"]}" stroke-width="{sw}"/>')
        label = s["name"]
        anchor = "start"
        dx = r + 4
        if s["name"] == "uncertainty_gated":
            label = "uncertainty_gated ★ online"
            dx = r + 4
        lines.append(f'<text x="{cx+dx:.1f}" y="{cy+4:.1f}" fill="{s["color"]}" '
                     f'font-size="9">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _reliability_svg() -> str:
    """Reliability diagram: predicted confidence vs actual accuracy."""
    W, H = 520, 360
    PAD = {"l": 60, "r": 30, "t": 40, "b": 55}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]

    def tx(v):
        return PAD["l"] + v * pw

    def ty(v):
        return PAD["t"] + ph - v * ph

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Reliability Diagram (Calibration)</text>',
        # axes
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]+ph}" x2="{PAD["l"]+pw}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        f'<text x="{PAD["l"]+pw//2}" y="{H-8}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11">Predicted Confidence</text>',
        f'<text x="14" y="{PAD["t"]+ph//2}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11" transform="rotate(-90,14,{PAD["t"]+ph//2})">Actual Accuracy</text>',
    ]

    # diagonal perfect calibration
    lines.append(f'<line x1="{tx(0):.1f}" y1="{ty(0):.1f}" '
                 f'x2="{tx(1):.1f}" y2="{ty(1):.1f}" '
                 f'stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="4,4"/>')
    lines.append(f'<text x="{tx(0.78):.1f}" y="{ty(0.84):.1f}" fill="{SLATE}" '
                 f'font-size="9">perfect</text>')

    # grid
    for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
        y = ty(v)
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" '
                     f'stroke="{BORDER}" stroke-width="0.5" stroke-dasharray="2,4"/>')
        lines.append(f'<text x="{PAD["l"]-6}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="{SLATE}" font-size="10">{v:.1f}</text>')
        x = tx(v)
        lines.append(f'<text x="{x:.1f}" y="{PAD["t"]+ph+15}" text-anchor="middle" '
                     f'fill="{SLATE}" font-size="10">{v:.1f}</text>')

    # single model bars
    bar_w = pw / len(RELIABILITY_BINS) * 0.3
    for b in RELIABILITY_BINS:
        x  = tx(b["conf"])
        ys = ty(b["single"])
        ye = ty(0)
        lines.append(f'<rect x="{x-bar_w:.1f}" y="{ys:.1f}" width="{bar_w:.1f}" '
                     f'height="{ye-ys:.1f}" fill="{SLATE}" opacity="0.4"/>')

    # ensemble model bars
    for b in RELIABILITY_BINS:
        x  = tx(b["conf"])
        ye_v = ty(b["ensemble"])
        ye   = ty(0)
        lines.append(f'<rect x="{x:.1f}" y="{ye_v:.1f}" width="{bar_w:.1f}" '
                     f'height="{ye-ye_v:.1f}" fill="{BLUE}" opacity="0.55"/>')

    # legend
    lx, ly = PAD["l"] + 8, PAD["t"] + 8
    lines.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{SLATE}" opacity="0.6"/>')
    lines.append(f'<text x="{lx+14}" y="{ly+9}" fill="{WHITE}" font-size="10">Single model</text>')
    lines.append(f'<rect x="{lx}" y="{ly+18}" width="10" height="10" fill="{BLUE}" opacity="0.7"/>')
    lines.append(f'<text x="{lx+14}" y="{ly+27}" fill="{WHITE}" font-size="10">Ensemble</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _weights_svg() -> str:
    """Per-task ensemble weights: stacked bar chart."""
    W, H = 580, 360
    PAD = {"l": 80, "r": 140, "t": 40, "b": 55}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]
    bar_w = pw / len(TASKS) * 0.6
    gap   = pw / len(TASKS)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Per-Task Ensemble Weights</text>',
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]+ph}" x2="{PAD["l"]+pw}" '
        f'y2="{PAD["t"]+ph}" stroke="{BORDER}" stroke-width="1"/>',
        f'<text x="{PAD["l"]+pw//2}" y="{H-8}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11">Task</text>',
        f'<text x="16" y="{PAD["t"]+ph//2}" text-anchor="middle" '
        f'fill="{SLATE}" font-size="11" transform="rotate(-90,16,{PAD["t"]+ph//2})">Weight</text>',
    ]

    # y axis ticks
    for v in [0.25, 0.5, 0.75, 1.0]:
        y = PAD["t"] + ph - v * ph
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" '
                     f'stroke="{BORDER}" stroke-width="0.5" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{PAD["l"]-6}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="{SLATE}" font-size="10">{v:.2f}</text>')

    for ti, task in enumerate(TASKS):
        cx = PAD["l"] + ti * gap + gap / 2
        x  = cx - bar_w / 2
        cum = 0.0
        for model in MODELS:
            w  = model["weights"][ti]
            bh = w * ph
            by = PAD["t"] + ph - (cum + w) * ph
            lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                         f'height="{bh:.1f}" fill="{model["color"]}" opacity="0.8"/>')
            if w > 0.12:
                lines.append(f'<text x="{cx:.1f}" y="{by+bh/2+4:.1f}" '
                             f'text-anchor="middle" fill="{BG}" font-size="9" font-weight="bold">'
                             f'{w:.2f}</text>')
            cum += w
        lines.append(f'<text x="{cx:.1f}" y="{PAD["t"]+ph+18}" text-anchor="middle" '
                     f'fill="{WHITE}" font-size="10">{task}</text>')

    # legend
    lx = W - PAD["r"] + 10
    for i, model in enumerate(MODELS):
        ly = PAD["t"] + i * 22
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" '
                     f'fill="{model["color"]}" opacity="0.85"/>')
        lines.append(f'<text x="{lx+16}" y="{ly+10}" fill="{WHITE}" '
                     f'font-size="10">{model["name"]}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# HTML page
# ══════════════════════════════════════════════════════════════════════════════

def _build_html() -> str:
    scatter     = _scatter_svg()
    reliability = _reliability_svg()
    weights     = _weights_svg()

    metrics = [
        ("voting-3 SR (offline)",      "0.84",  GREEN),
        ("uncertainty-gated SR (online)", "0.82", BLUE),
        ("online overhead",            "+8 ms",  AMBER),
        ("stochastic mode-collapse",   "-31% SR", RED),
        ("single-model baseline SR",   "0.68",   SLATE),
    ]
    metric_cards = "".join(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;'
        f'padding:14px 18px;min-width:150px">'
        f'<div style="font-size:11px;color:{SLATE};margin-bottom:6px">{lbl}</div>'
        f'<div style="font-size:24px;font-weight:bold;color:{col}">{val}</div>'
        f'</div>'
        for lbl, val, col in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Policy Ensemble v2 — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:{BG};color:{WHITE};font-family:monospace;padding:24px}}
  h1{{color:{RED};font-size:20px;margin-bottom:4px}}
  .sub{{color:{SLATE};font-size:12px;margin-bottom:24px}}
  .cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
  .section{{margin-bottom:32px}}
  .section h2{{color:{BLUE};font-size:14px;margin-bottom:12px;border-bottom:1px solid {BORDER};padding-bottom:6px}}
  svg{{display:block;max-width:100%}}
  footer{{color:{SLATE};font-size:10px;margin-top:32px;border-top:1px solid {BORDER};padding-top:12px}}
</style>
</head>
<body>
<h1>Policy Ensemble v2</h1>
<div class="sub">OCI Robot Cloud · Ensemble Strategy Evaluation · Port 8658 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

<div class="cards">{metric_cards}</div>

<div class="section">
  <h2>Ensemble SR vs Latency Scatter</h2>
  {scatter}
</div>

<div class="section">
  <h2>Reliability Diagram (Calibration)</h2>
  {reliability}
</div>

<div class="section">
  <h2>Per-Task Ensemble Weights (GR00T_v2 / dagger_r9 / BC)</h2>
  {weights}
</div>

<footer>policy_ensemble_v2.py · cycle-150A · © 2026 Oracle OCI Robot Cloud</footer>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

if USE_FASTAPI:
    app = FastAPI(title="Policy Ensemble v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "policy_ensemble_v2", "port": 8658})

    @app.get("/api/strategies")
    async def strategies():
        return JSONResponse({"strategies": STRATEGIES})

    @app.get("/api/metrics")
    async def metrics():
        return JSONResponse({
            "voting3_sr_offline": 0.84,
            "uncertainty_gated_sr_online": 0.82,
            "online_overhead_ms": 8,
            "stochastic_mode_collapse_delta": -0.31,
            "baseline_sr": 0.68,
        })

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "policy_ensemble_v2", "port": 8658}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    PORT = 8658
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — stdlib HTTPServer on :{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
