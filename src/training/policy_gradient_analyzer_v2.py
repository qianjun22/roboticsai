"""Policy Gradient Analyzer v2 — OCI Robot Cloud (port 8627).

Dark-theme FastAPI service with SVG visualizations for gradient flow,
gradient SNR per layer, and gradient conflict reduction comparison.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8627

# ---------------------------------------------------------------------------
# Layer / metric data
# ---------------------------------------------------------------------------

LAYERS = [
    {"name": "Input Embed",    "snr": 0.8,  "grad_norm": 0.12},
    {"name": "Vision Enc 1",   "snr": 1.0,  "grad_norm": 0.18},
    {"name": "Vision Enc 2",   "snr": 1.2,  "grad_norm": 0.22},
    {"name": "Vision Enc 3",   "snr": 1.5,  "grad_norm": 0.28},
    {"name": "Cross Attn 1",   "snr": 2.1,  "grad_norm": 0.41},
    {"name": "Cross Attn 2",   "snr": 3.1,  "grad_norm": 0.58},
    {"name": "FFN 1",          "snr": 2.0,  "grad_norm": 0.38},
    {"name": "FFN 2",          "snr": 2.4,  "grad_norm": 0.45},
    {"name": "Decoder 1",      "snr": 4.1,  "grad_norm": 0.72},
    {"name": "Decoder 2",      "snr": 5.2,  "grad_norm": 0.88},
    {"name": "Decoder 3",      "snr": 6.3,  "grad_norm": 0.95},
    {"name": "Action Head",    "snr": 8.4,  "grad_norm": 1.00},
]

SNR_THRESHOLD = 2.0


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_gradient_flow() -> str:
    """12-layer network vertical stack; horizontal arrows thickness = grad magnitude."""
    BOX_W, BOX_H, GAP = 200, 32, 10
    LEFT = 60
    W = 760
    total_h = len(LAYERS) * (BOX_H + GAP)
    H = total_h + 70
    ARROW_MAX_W = 280
    MAX_NORM = max(l["grad_norm"] for l in LAYERS)

    items = []
    for i, layer in enumerate(LAYERS):
        y = 50 + i * (BOX_H + GAP)
        norm_ratio = layer["grad_norm"] / MAX_NORM
        arrow_w = max(4, int(norm_ratio * ARROW_MAX_W))
        opacity = max(0.25, norm_ratio)
        # Layer box
        box_color = "#1e3a5f" if layer["snr"] >= SNR_THRESHOLD else "#3b1f1f"
        items.append(
            f'<rect x="{LEFT}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="4" fill="{box_color}"/>'
            f'<text x="{LEFT + BOX_W//2}" y="{y+BOX_H//2+5}" font-family="monospace" font-size="12" '
            f'fill="#e2e8f0" text-anchor="middle">{layer["name"]}</text>'
        )
        # Arrow (gradient flow)
        ax = LEFT + BOX_W + 8
        ay = y + BOX_H // 2
        items.append(
            f'<rect x="{ax}" y="{ay - arrow_w//2}" width="{arrow_w}" height="{arrow_w}" '
            f'rx="2" fill="#38bdf8" opacity="{opacity:.2f}"/>'
            f'<text x="{ax + arrow_w + 6}" y="{ay+5}" font-family="monospace" font-size="10" '
            f'fill="#64748b">{layer["grad_norm"]:.2f}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{W//2}" y="30" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Gradient Flow — 12-Layer Policy Network</text>'
        f'<text x="{LEFT+BOX_W+12}" y="44" font-family="monospace" font-size="10" fill="#475569">'
        f'← bar width = gradient magnitude →</text>'
        + "".join(items)
        + "</svg>"
    )
    return svg


def svg_gradient_snr() -> str:
    """Horizontal bar chart: gradient SNR per layer with threshold line at 2.0."""
    W, H = 760, 340
    LEFT, RIGHT_PAD, TOP, BOT = 130, 40, 40, 30
    CHART_W = W - LEFT - RIGHT_PAD
    MAX_SNR = 10.0
    ROW_H = (H - TOP - BOT) / len(LAYERS)

    bars = []
    # Threshold line at SNR=2.0
    tx = LEFT + (SNR_THRESHOLD / MAX_SNR) * CHART_W
    bars.append(
        f'<line x1="{tx:.1f}" y1="{TOP-5}" x2="{tx:.1f}" y2="{H-BOT}" '
        f'stroke="#f97316" stroke-width="1.5" stroke-dasharray="4,3"/>'
        f'<text x="{tx+4}" y="{TOP-8}" font-size="10" fill="#f97316">SNR=2.0 threshold</text>'
    )
    # X-axis ticks
    for v in [0, 2, 4, 6, 8, 10]:
        vx = LEFT + (v / MAX_SNR) * CHART_W
        bars.append(
            f'<line x1="{vx:.1f}" y1="{TOP}" x2="{vx:.1f}" y2="{H-BOT}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{vx:.1f}" y="{H-BOT+14}" font-size="10" fill="#475569" text-anchor="middle">{v}</text>'
        )
    # Bars
    for i, layer in enumerate(LAYERS):
        y = TOP + i * ROW_H
        bw = (layer["snr"] / MAX_SNR) * CHART_W
        color = "#22c55e" if layer["snr"] >= SNR_THRESHOLD else "#ef4444"
        bars.append(
            f'<text x="{LEFT-6}" y="{y + ROW_H*0.62:.1f}" font-family="monospace" font-size="10" '
            f'fill="#94a3b8" text-anchor="end">{layer["name"]}</text>'
            f'<rect x="{LEFT}" y="{y + ROW_H*0.1:.1f}" width="{bw:.1f}" height="{ROW_H*0.7:.1f}" '
            f'rx="3" fill="{color}" opacity="0.8"/>'
            f'<text x="{LEFT + bw + 5:.1f}" y="{y + ROW_H*0.62:.1f}" font-size="10" '
            f'fill="{color}">{layer["snr"]}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{W//2}" y="24" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Gradient SNR per Layer</text>'
        + "".join(bars)
        + "</svg>"
    )
    return svg


def svg_conflict_reduction() -> str:
    """Grouped bars: Standard vs PCGrad vs gradient_surgery conflict rates."""
    methods = [
        {"name": "Standard",          "rate": 45, "color": "#ef4444"},
        {"name": "PCGrad",             "rate": 21, "color": "#fbbf24"},
        {"name": "Gradient Surgery",   "rate": 11, "color": "#22c55e"},
    ]
    W, H = 560, 260
    BAR_W = 100
    GAP = 40
    TOP, BOT = 50, 40
    MAX_RATE = 50
    CHART_H = H - TOP - BOT
    LEFT = 60

    bars = []
    # Y-axis
    for v in [0, 10, 20, 30, 40, 50]:
        vy = TOP + CHART_H - (v / MAX_RATE) * CHART_H
        bars.append(
            f'<line x1="{LEFT}" y1="{vy:.1f}" x2="{W-20}" y2="{vy:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{LEFT-6}" y="{vy+4:.1f}" font-size="10" fill="#475569" text-anchor="end">{v}%</text>'
        )
    for i, m in enumerate(methods):
        bx = LEFT + i * (BAR_W + GAP)
        bh = (m["rate"] / MAX_RATE) * CHART_H
        by = TOP + CHART_H - bh
        bars.append(
            f'<rect x="{bx}" y="{by:.1f}" width="{BAR_W}" height="{bh:.1f}" rx="4" '
            f'fill="{m["color"]}" opacity="0.8"/>'
            f'<text x="{bx + BAR_W//2}" y="{by - 6:.1f}" font-size="12" fill="{m["color"]}" '
            f'text-anchor="middle" font-weight="bold">{m["rate"]}%</text>'
            f'<text x="{bx + BAR_W//2}" y="{TOP + CHART_H + 16}" font-size="11" '
            f'fill="#94a3b8" text-anchor="middle" font-family="monospace">{m["name"]}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{W//2}" y="28" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Gradient Conflict Rate Comparison</text>'
        + "".join(bars)
        + "</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    flow_svg = svg_gradient_flow()
    snr_svg = svg_gradient_snr()
    conflict_svg = svg_conflict_reduction()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Policy Gradient Analyzer v2 — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 6px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin: 20px 0 8px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .metric {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
               padding: 14px 20px; min-width: 160px; }}
    .metric .val {{ font-size: 26px; font-weight: bold; color: #38bdf8; }}
    .metric .lbl {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
    .metric.warn .val {{ color: #f97316; }}
    .metric.ok   .val {{ color: #22c55e; }}
    .chart {{ margin-bottom: 28px; overflow-x: auto; }}
    svg {{ display: block; border-radius: 8px; border: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <h1>Policy Gradient Analyzer v2</h1>
  <p class="subtitle">OCI Robot Cloud · Port {PORT} · Gradient health diagnostics for GR00T N1.6 policy fine-tuning</p>

  <div class="metrics">
    <div class="metric ok"><div class="val">8.4</div><div class="lbl">Action Head SNR<br>(healthy)</div></div>
    <div class="metric warn"><div class="val">1.2</div><div class="lbl">Vision Encoder SNR<br>needs 3× LR boost</div></div>
    <div class="metric ok"><div class="val">34%</div><div class="lbl">Conflict Reduction<br>(Surgery vs Standard)</div></div>
    <div class="metric"><div class="val">11%</div><div class="lbl">Conflict Rate<br>Gradient Surgery</div></div>
  </div>

  <h2>Gradient Flow Diagram</h2>
  <div class="chart">{flow_svg}</div>

  <h2>Gradient SNR per Layer</h2>
  <div class="chart">{snr_svg}</div>

  <h2>Gradient Conflict Reduction</h2>
  <div class="chart">{conflict_svg}</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Policy Gradient Analyzer v2",
        description="Gradient flow, SNR per layer, and conflict reduction analysis for robot policy training.",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "policy_gradient_analyzer_v2", "port": PORT})

    @app.get("/api/gradient-stats")
    async def api_gradient_stats():
        return JSONResponse({
            "layers": LAYERS,
            "snr_threshold": SNR_THRESHOLD,
            "action_head_snr": 8.4,
            "vision_encoder_snr": 1.2,
            "vision_encoder_recommendation": "3x LR boost",
            "conflict_reduction_pct": 34,
            "conflict_rate_gradient_surgery": 0.11,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    # Fallback: stdlib HTTP server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
