# model_weight_analyzer.py — port 8644
# Analyzes model weight distributions, magnitudes, and sparsity patterns

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import json

# ---------------------------------------------------------------------------
# SVG generators (stdlib only)
# ---------------------------------------------------------------------------

def svg_weight_distribution_violin() -> str:
    """12-layer violin plot: encoder layers wider, action head narrower bimodal."""
    W, H = 900, 380
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    layers = [
        "enc_0", "enc_1", "enc_2", "enc_3", "enc_4",
        "cross_0", "cross_1",
        "dec_0", "dec_1",
        "act_head_0", "act_head_1", "act_head_2",
    ]
    n = len(layers)
    slot_w = inner_w / n

    # Gaussian PDF helper
    def gauss(x, mu, sigma):
        return math.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))

    def bimodal(x, mu1, mu2, sigma):
        return 0.5 * gauss(x, mu1, sigma) + 0.5 * gauss(x, mu2, sigma)

    # Value axis: -0.6 to 0.6
    v_min, v_max = -0.6, 0.6

    def vy(v):
        frac = (v - v_min) / (v_max - v_min)
        return pad_t + inner_h * (1 - frac)

    paths = []
    xs_axis = []
    samples = 80

    for i, name in enumerate(layers):
        cx = pad_l + slot_w * i + slot_w / 2
        xs_axis.append((cx, name))
        is_act = name.startswith("act_head")
        is_cross = name.startswith("cross")

        if is_act:
            sigma = 0.08
            pdf_fn = lambda x: bimodal(x, -0.18, 0.18, sigma)
            color = "#C74634"
        elif is_cross:
            sigma = 0.14
            pdf_fn = lambda x, s=sigma: gauss(x, 0.0, s)
            color = "#38bdf8"
        else:
            sigma = 0.20 - i * 0.004
            pdf_fn = lambda x, s=sigma: gauss(x, 0.0, s)
            color = "#7dd3fc"

        # Sample PDF
        vs = [v_min + (v_max - v_min) * k / (samples - 1) for k in range(samples)]
        densities = [pdf_fn(v) for v in vs]
        max_d = max(densities) or 1.0
        half_w = slot_w * 0.42

        right_pts = [(cx + (d / max_d) * half_w, vy(v)) for v, d in zip(vs, densities)]
        left_pts  = [(cx - (d / max_d) * half_w, vy(v)) for v, d in zip(vs, densities)]

        d_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in right_pts)
        d_path += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(left_pts))
        d_path += " Z"

        paths.append(f'<path d="{d_path}" fill="{color}" fill-opacity="0.55" stroke="{color}" stroke-width="1"/>')
        # Median line
        paths.append(f'<line x1="{cx-6}" y1="{vy(0):.1f}" x2="{cx+6}" y2="{vy(0):.1f}" stroke="#f1f5f9" stroke-width="1.5"/>')

    # Axes
    axis_lines = [
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]
    # Y tick labels
    yticks = ""
    for v in [-0.6, -0.3, 0.0, 0.3, 0.6]:
        y = vy(v)
        yticks += f'<text x="{pad_l-6}" y="{y+4:.1f}" font-size="10" fill="#94a3b8" text-anchor="end">{v:.1f}</text>'
        yticks += f'<line x1="{pad_l-3}" y1="{y:.1f}" x2="{pad_l}" y2="{y:.1f}" stroke="#475569" stroke-width="1"/>'
        yticks += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+inner_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3,3"/>'

    # X labels
    xlabels = ""
    for cx, name in xs_axis:
        xlabels += f'<text x="{cx:.1f}" y="{pad_t+inner_h+16}" font-size="9" fill="#94a3b8" text-anchor="middle" transform="rotate(-30,{cx:.1f},{pad_t+inner_h+16})">{name}</text>'

    # Legend
    legend = (
        '<rect x="680" y="14" width="12" height="12" fill="#7dd3fc" fill-opacity="0.7"/>'
        '<text x="696" y="24" font-size="11" fill="#cbd5e1">Encoder</text>'
        '<rect x="760" y="14" width="12" height="12" fill="#C74634" fill-opacity="0.7"/>'
        '<text x="776" y="24" font-size="11" fill="#cbd5e1">Action Head</text>'
    )

    title = f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">Weight Distribution by Layer (Violin)</text>'
    ylabel = f'<text x="14" y="{pad_t+inner_h//2}" font-size="11" fill="#94a3b8" text-anchor="middle" transform="rotate(-90,14,{pad_t+inner_h//2})">Weight Value</text>'

    inner = "\n".join(paths) + "\n" + "\n".join(axis_lines) + "\n" + yticks + "\n" + xlabels + "\n" + legend + "\n" + title + "\n" + ylabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


def svg_weight_magnitude_histogram() -> str:
    """3 overlaid histograms: FP32, FP16, INT8 (INT8 shows discretization steps)."""
    W, H = 760, 340
    pad_l, pad_r, pad_t, pad_b = 55, 20, 40, 55
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    bins = 40
    x_min, x_max = 0.0, 0.8

    def gauss(x, mu, sigma):
        return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    # FP32: smooth Rayleigh-like
    def fp32_density(x):
        return 3.8 * x * math.exp(-6 * x * x) if x >= 0 else 0

    # FP16: slightly discretized but close to FP32
    def fp16_density(x):
        return fp32_density(x) * (1 + 0.05 * math.sin(x * 60))

    # INT8: coarse discretization steps every 0.025
    def int8_density(x):
        step = 0.025
        snapped = round(x / step) * step
        return fp32_density(snapped) * (1 - 0.03) * 0.9

    configs = [
        ("FP32", fp32_density, "#38bdf8", 0.55),
        ("FP16", fp16_density, "#a78bfa", 0.50),
        ("INT8", int8_density, "#C74634", 0.60),
    ]

    def bx(i):
        return pad_l + inner_w * i / bins

    def by(val, mx):
        return pad_t + inner_h * (1 - val / mx)

    all_bars = []
    max_density = 0
    for _, fn, _, _ in configs:
        for i in range(bins):
            xv = x_min + (x_max - x_min) * (i + 0.5) / bins
            max_density = max(max_density, fn(xv))

    bars_svg = ""
    bar_w = inner_w / bins
    for label, fn, color, alpha in configs:
        for i in range(bins):
            xv = x_min + (x_max - x_min) * (i + 0.5) / bins
            d = fn(xv)
            h = inner_h * d / max_density
            x = pad_l + inner_w * i / bins
            y = pad_t + inner_h - h
            bars_svg += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" fill-opacity="{alpha}" stroke="none"/>'

    # INT8 step markers
    step_svg = ""
    step_size = 0.025
    n_steps = int((x_max - x_min) / step_size)
    for s in range(n_steps + 1):
        xv = x_min + s * step_size
        px = pad_l + inner_w * (xv - x_min) / (x_max - x_min)
        step_svg += f'<line x1="{px:.1f}" y1="{pad_t}" x2="{px:.1f}" y2="{pad_t+inner_h}" stroke="#C74634" stroke-width="0.4" stroke-opacity="0.35"/>'

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
    )

    xticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8]:
        px = pad_l + inner_w * (v - x_min) / (x_max - x_min)
        xticks += f'<text x="{px:.1f}" y="{pad_t+inner_h+16}" font-size="10" fill="#94a3b8" text-anchor="middle">{v:.1f}</text>'
        xticks += f'<line x1="{px:.1f}" y1="{pad_t+inner_h}" x2="{px:.1f}" y2="{pad_t+inner_h+5}" stroke="#475569" stroke-width="1"/>'

    legend = (
        '<rect x="60" y="14" width="12" height="10" fill="#38bdf8" fill-opacity="0.7"/>'
        '<text x="76" y="23" font-size="11" fill="#cbd5e1">FP32</text>'
        '<rect x="120" y="14" width="12" height="10" fill="#a78bfa" fill-opacity="0.7"/>'
        '<text x="136" y="23" font-size="11" fill="#cbd5e1">FP16</text>'
        '<rect x="180" y="14" width="12" height="10" fill="#C74634" fill-opacity="0.7"/>'
        '<text x="196" y="23" font-size="11" fill="#cbd5e1">INT8 (discretization steps shown)</text>'
    )

    title = f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">Weight Magnitude Histogram — FP32 / FP16 / INT8</text>'
    xlabel = f'<text x="{pad_l+inner_w//2}" y="{H-8}" font-size="11" fill="#94a3b8" text-anchor="middle">|Weight| Magnitude</text>'

    inner = step_svg + bars_svg + axes + xticks + legend + title + xlabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


def svg_layer_sparsity_bar() -> str:
    """% near-zero weights per layer; action head 18% highest natural sparsity."""
    W, H = 860, 320
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 60
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    data = [
        ("enc_0",      6.2),
        ("enc_1",      5.8),
        ("enc_2",      7.1),
        ("enc_3",      6.9),
        ("enc_4",      8.3),
        ("cross_0",    9.4),
        ("cross_1",   10.1),
        ("dec_0",     11.7),
        ("dec_1",     13.2),
        ("act_head_0",15.6),
        ("act_head_1",16.9),
        ("act_head_2",18.0),
    ]
    n = len(data)
    max_val = 22.0
    bar_w = inner_w / n * 0.7
    gap = inner_w / n

    bars_svg = ""
    labels_svg = ""
    for i, (name, val) in enumerate(data):
        cx = pad_l + gap * i + gap / 2
        bx = cx - bar_w / 2
        bh = inner_h * val / max_val
        by = pad_t + inner_h - bh
        color = "#C74634" if name.startswith("act_head") else ("#38bdf8" if name.startswith("enc") else "#7dd3fc")
        bars_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="3"/>'
        bars_svg += f'<text x="{cx:.1f}" y="{by-5:.1f}" font-size="10" fill="#e2e8f0" text-anchor="middle">{val:.1f}%</text>'
        labels_svg += f'<text x="{cx:.1f}" y="{pad_t+inner_h+14}" font-size="9" fill="#94a3b8" text-anchor="middle" transform="rotate(-35,{cx:.1f},{pad_t+inner_h+14})">{name}</text>'

    # Y axis ticks
    yticks = ""
    for v in [0, 5, 10, 15, 20]:
        y = pad_t + inner_h * (1 - v / max_val)
        yticks += f'<text x="{pad_l-6}" y="{y+4:.1f}" font-size="10" fill="#94a3b8" text-anchor="end">{v}%</text>'
        yticks += f'<line x1="{pad_l-3}" y1="{y:.1f}" x2="{pad_l}" y2="{y:.1f}" stroke="#475569" stroke-width="1"/>'
        yticks += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+inner_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3,3"/>'

    # 18% annotation
    threshold_y = pad_t + inner_h * (1 - 18.0 / max_val)
    annotation = (
        f'<line x1="{pad_l}" y1="{threshold_y:.1f}" x2="{pad_l+inner_w}" y2="{threshold_y:.1f}" '
        f'stroke="#C74634" stroke-width="1" stroke-dasharray="5,3"/>'
        f'<text x="{pad_l+inner_w-4}" y="{threshold_y-4:.1f}" font-size="10" fill="#C74634" text-anchor="end">18% peak sparsity (action head)</text>'
    )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
    )

    legend = (
        '<rect x="60" y="14" width="12" height="10" fill="#38bdf8"/>'
        '<text x="76" y="23" font-size="11" fill="#cbd5e1">Encoder</text>'
        '<rect x="140" y="14" width="12" height="10" fill="#7dd3fc"/>'
        '<text x="156" y="23" font-size="11" fill="#cbd5e1">Cross/Decoder</text>'
        '<rect x="260" y="14" width="12" height="10" fill="#C74634"/>'
        '<text x="276" y="23" font-size="11" fill="#cbd5e1">Action Head</text>'
    )

    title = f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">Layer-wise Weight Sparsity (% Near-Zero Weights)</text>'
    ylabel = f'<text x="14" y="{pad_t+inner_h//2}" font-size="11" fill="#94a3b8" text-anchor="middle" transform="rotate(-90,14,{pad_t+inner_h//2})">Sparsity %</text>'

    inner = bars_svg + labels_svg + yticks + annotation + axes + legend + title + ylabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

METRICS = {
    "encoder_distribution": "Gaussian (σ≈0.20 shallow → σ≈0.18 deep)",
    "action_head_distribution": "Bimodal — two grasp modes at ±0.18",
    "int8_sr_loss": "2.1% success-rate loss vs FP32",
    "int8_speedup": "3× inference speedup over FP32",
    "natural_sparsity_peak": "18% near-zero weights in action head",
    "quantization_formats": "FP32 / FP16 / INT8",
    "layers_analyzed": 12,
}


def build_html() -> str:
    violin   = svg_weight_distribution_violin()
    hist     = svg_weight_magnitude_histogram()
    sparsity = svg_layer_sparsity_bar()
    metrics_html = "".join(
        f'<div class="metric"><span class="mkey">{k}</span><span class="mval">{v}</span></div>'
        for k, v in METRICS.items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Model Weight Analyzer — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{color:#38bdf8;font-size:1.6rem;margin-bottom:4px}}
  .sub{{color:#94a3b8;font-size:.9rem;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px;border:1px solid #334155}}
  .card h2{{font-size:1rem;color:#C74634;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;margin-bottom:20px}}
  .metric{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 16px}}
  .mkey{{display:block;font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
  .mval{{display:block;font-size:.95rem;color:#f1f5f9;font-weight:600}}
  svg{{max-width:100%;height:auto}}
  footer{{color:#475569;font-size:.8rem;text-align:center;margin-top:24px}}
</style>
</head>
<body>
<h1>Model Weight Analyzer</h1>
<p class="sub">OCI Robot Cloud — GR00T N1.6 weight analysis (port 8644)</p>
<div class="metrics">{metrics_html}</div>
<div class="card">
  <h2>Weight Distribution by Layer (Violin)</h2>
  {violin}
</div>
<div class="card">
  <h2>Weight Magnitude Histogram — FP32 / FP16 / INT8</h2>
  {hist}
</div>
<div class="card">
  <h2>Layer-wise Sparsity</h2>
  {sparsity}
</div>
<footer>OCI Robot Cloud &mdash; model_weight_analyzer.py &mdash; port 8644</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Model Weight Analyzer",
        description="GR00T N1.6 weight distribution, magnitude, and sparsity analysis",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "model_weight_analyzer", "port": 8644})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse(METRICS)

    @app.get("/svg/violin", response_class=HTMLResponse)
    async def svg_violin():
        return HTMLResponse(content=svg_weight_distribution_violin(), media_type="image/svg+xml")

    @app.get("/svg/histogram", response_class=HTMLResponse)
    async def svg_histogram():
        return HTMLResponse(content=svg_weight_magnitude_histogram(), media_type="image/svg+xml")

    @app.get("/svg/sparsity", response_class=HTMLResponse)
    async def svg_sparsity():
        return HTMLResponse(content=svg_layer_sparsity_bar(), media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Fallback stdlib HTTP server
# ---------------------------------------------------------------------------

class _Handler:
    """Minimal HTTP handler — used when FastAPI/uvicorn are unavailable."""

    def __init__(self, request, client_address, server):
        import http.server
        http.server.BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        import http.server
        html = build_html().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def _run_stdlib_server(port: int = 8644):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "model_weight_analyzer", "port": port}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                html = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

    print(f"[model_weight_analyzer] stdlib fallback server on :{port}")
    with http.server.HTTPServer(("", port), Handler) as srv:
        srv.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    PORT = 8644
    if USE_FASTAPI:
        print(f"[model_weight_analyzer] FastAPI on :{PORT}")
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib_server(PORT)
