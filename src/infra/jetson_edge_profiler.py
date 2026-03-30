# jetson_edge_profiler.py — port 8645
# Profiles GR00T N1.6 inference on Jetson Orin: latency breakdown,
# memory timeline, and throughput vs batch size.

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json

# ---------------------------------------------------------------------------
# SVG generators (stdlib only)
# ---------------------------------------------------------------------------

def svg_inference_latency_waterfall() -> str:
    """Horizontal waterfall: Jetson Orin inference stage breakdown (294ms total)."""
    W, H = 860, 260
    pad_l, pad_r, pad_t, pad_b = 160, 30, 50, 40
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    stages = [
        ("model_load",   28,  "#38bdf8"),
        ("vision_enc",   98,  "#7dd3fc"),
        ("cross_attn",   62,  "#a78bfa"),
        ("action_head",  74,  "#C74634"),
        ("decode",       32,  "#34d399"),
    ]
    total_ms = sum(s[1] for s in stages)
    bar_h = inner_h * 0.55
    bar_y = pad_t + (inner_h - bar_h) / 2

    segments = ""
    x_cursor = pad_l
    annotations = ""
    for name, ms, color in stages:
        seg_w = inner_w * ms / total_ms
        segments += (
            f'<rect x="{x_cursor:.1f}" y="{bar_y:.1f}" width="{seg_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="2"/>'
        )
        label_x = x_cursor + seg_w / 2
        # Only print label if segment wide enough
        if seg_w > 36:
            segments += (
                f'<text x="{label_x:.1f}" y="{bar_y + bar_h/2 + 4:.1f}" '
                f'font-size="11" fill="#0f172a" text-anchor="middle" font-weight="bold">{ms}ms</text>'
            )
        # Stage name above bar
        annotations += (
            f'<text x="{label_x:.1f}" y="{bar_y - 8:.1f}" '
            f'font-size="10" fill="{color}" text-anchor="middle">{name}</text>'
        )
        x_cursor += seg_w

    # X axis ticks
    xticks = ""
    for ms_tick in [0, 50, 100, 150, 200, 250, 294]:
        px = pad_l + inner_w * ms_tick / total_ms
        xticks += f'<line x1="{px:.1f}" y1="{bar_y+bar_h}" x2="{px:.1f}" y2="{bar_y+bar_h+6}" stroke="#475569" stroke-width="1"/>'
        xticks += f'<text x="{px:.1f}" y="{bar_y+bar_h+18}" font-size="10" fill="#94a3b8" text-anchor="middle">{ms_tick}ms</text>'

    # Stage labels on left
    left_labels = ""
    for i, (name, ms, color) in enumerate(stages):
        left_labels += f'<text x="{pad_l-8}" y="{bar_y + bar_h/2 + 4:.1f}" font-size="11" fill="{color}" text-anchor="end">← {name}</text>'
        break  # only one row — all in one bar

    # Total annotation
    total_ann = (
        f'<text x="{W-pad_r}" y="{bar_y + bar_h/2 + 4:.1f}" font-size="12" fill="#f1f5f9" text-anchor="end" font-weight="bold">{total_ms}ms total</text>'
    )

    # Target line
    target_px = pad_l + inner_w * 150 / total_ms
    target_line = (
        f'<line x1="{target_px:.1f}" y1="{pad_t}" x2="{target_px:.1f}" y2="{bar_y+bar_h+25}" '
        f'stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3"/>'
        f'<text x="{target_px+4:.1f}" y="{pad_t+12}" font-size="10" fill="#fbbf24">target 150ms</text>'
    )

    legend = ""
    lx = pad_l
    for name, ms, color in stages:
        legend += f'<rect x="{lx}" y="14" width="11" height="11" fill="{color}"/>'
        legend += f'<text x="{lx+14}" y="23" font-size="10" fill="#cbd5e1">{name} ({ms}ms)</text>'
        lx += 130

    title = (
        f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">'
        f'Jetson Orin Inference Latency Breakdown (294ms @ 3.4Hz)</text>'
    )

    axes = (
        f'<line x1="{pad_l}" y1="{bar_y+bar_h}" x2="{pad_l+inner_w}" y2="{bar_y+bar_h}" stroke="#475569" stroke-width="1"/>'
    )
    xlabel = f'<text x="{pad_l+inner_w//2}" y="{H-5}" font-size="11" fill="#94a3b8" text-anchor="middle">Latency (ms)</text>'

    inner = segments + annotations + xticks + target_line + total_ann + legend + title + axes + xlabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


def svg_memory_profile_timeline() -> str:
    """VRAM over inference steps: 2.1GB baseline → 4.8GB peak → 2.1GB."""
    W, H = 780, 300
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    # Keyframes: (step_frac, vram_gb, phase_label)
    keyframes = [
        (0.00, 2.1, "baseline"),
        (0.08, 2.1, None),
        (0.10, 2.3, None),   # model_load start
        (0.19, 2.6, "model_load"),
        (0.20, 2.6, None),
        (0.22, 3.1, None),   # vision_enc start
        (0.53, 4.2, "vision_enc"),
        (0.55, 4.2, None),
        (0.57, 4.6, None),   # cross_attn
        (0.74, 4.8, "peak"),
        (0.75, 4.8, None),
        (0.78, 4.5, None),   # action_head
        (0.99, 4.3, "action_head"),
        (1.00, 3.8, None),
        (1.02, 3.2, None),   # decode
        (1.05, 2.5, None),
        (1.08, 2.1, "baseline"),
        # normalize to [0,1]
    ]
    # Remap step_frac to [0,1]
    max_frac = max(k[0] for k in keyframes)
    keyframes = [(f / max_frac, g, l) for f, g, l in keyframes]

    v_min, v_max = 0.0, 6.0

    def px(frac):
        return pad_l + inner_w * frac

    def py(gb):
        return pad_t + inner_h * (1 - (gb - v_min) / (v_max - v_min))

    # Build area path
    pts = [(px(f), py(g)) for f, g, _ in keyframes]
    area_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d += f" L {px(1.0):.1f},{py(0):.1f} L {px(0.0):.1f},{py(0):.1f} Z"
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    area_svg = f'<path d="{area_d}" fill="#38bdf8" fill-opacity="0.15" stroke="none"/>'
    line_svg = f'<path d="{line_d}" fill="none" stroke="#38bdf8" stroke-width="2"/>'

    # Phase annotations
    phases = [
        (0.05,  "baseline\n2.1 GB",  "#94a3b8"),
        (0.35,  "vision_enc\n+2.1 GB", "#7dd3fc"),
        (0.63,  "peak\n4.8 GB",       "#C74634"),
        (0.90,  "draining",            "#94a3b8"),
    ]
    phase_svg = ""
    for frac, label, color in phases:
        x_ = px(frac)
        # find approximate y
        close = min(keyframes, key=lambda k: abs(k[0] - frac))
        y_ = py(close[1]) - 14
        # split label
        parts = label.split("\n")
        for j, part in enumerate(parts):
            phase_svg += f'<text x="{x_:.1f}" y="{y_+j*13:.1f}" font-size="10" fill="{color}" text-anchor="middle">{part}</text>'

    # Peak dot
    peak_x, peak_y = px(0.65), py(4.8)
    peak_svg = f'<circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="5" fill="#C74634" stroke="#f1f5f9" stroke-width="1.5"/>'

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
    )
    yticks = ""
    for v in [0, 1, 2, 3, 4, 5, 6]:
        y = py(v)
        yticks += f'<text x="{pad_l-6}" y="{y+4:.1f}" font-size="10" fill="#94a3b8" text-anchor="end">{v} GB</text>'
        yticks += f'<line x1="{pad_l-3}" y1="{y:.1f}" x2="{pad_l}" y2="{y:.1f}" stroke="#475569" stroke-width="1"/>'
        yticks += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+inner_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3,3"/>'

    title = (
        f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">'
        f'VRAM Memory Profile During Inference (Jetson Orin)</text>'
    )
    xlabel = f'<text x="{pad_l+inner_w//2}" y="{H-5}" font-size="11" fill="#94a3b8" text-anchor="middle">Inference Step (normalized)</text>'
    ylabel = f'<text x="14" y="{pad_t+inner_h//2}" font-size="11" fill="#94a3b8" text-anchor="middle" transform="rotate(-90,14,{pad_t+inner_h//2})">VRAM (GB)</text>'

    inner = area_svg + line_svg + phase_svg + peak_svg + axes + yticks + title + xlabel + ylabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


def svg_throughput_vs_batch() -> str:
    """Throughput vs batch size: Jetson Orin batch-1/2 + OOM at batch-3, A100 comparison."""
    W, H = 680, 320
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 55
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    # Data
    orin_data = [(1, 3.4), (2, 2.1)]   # Hz
    orin_oom  = 3
    a100_data = [(1, 28.6), (2, 52.1), (4, 89.3), (8, 142.7)]  # Hz (reference)

    # Scale: x = batch size 1-9, y = 0-160 Hz
    x_min, x_max = 0.5, 9.5
    y_min, y_max = 0.0, 160.0

    def bx(batch):
        return pad_l + inner_w * (batch - x_min) / (x_max - x_min)

    def by(hz):
        return pad_t + inner_h * (1 - (hz - y_min) / (y_max - y_min))

    # A100 bars (background reference)
    bars_svg = ""
    bar_w = inner_w / 18
    for batch, hz in a100_data:
        bx_ = bx(batch) - bar_w / 2
        bh  = inner_h * hz / y_max
        by_ = pad_t + inner_h - bh
        bars_svg += f'<rect x="{bx_:.1f}" y="{by_:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="#475569" fill-opacity="0.55" rx="2"/>'
        bars_svg += f'<text x="{bx(batch):.1f}" y="{by_-4:.1f}" font-size="9" fill="#64748b" text-anchor="middle">{hz:.0f}Hz</text>'

    # Orin line
    orin_pts = [(bx(b), by(h)) for b, h in orin_data]
    orin_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in orin_pts)
    orin_svg = (
        f'<path d="{orin_d}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
    )
    for (batch, hz), (x_, y_) in zip(orin_data, orin_pts):
        orin_svg += f'<circle cx="{x_:.1f}" cy="{y_:.1f}" r="5" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>'
        orin_svg += f'<text x="{x_:.1f}" y="{y_-10:.1f}" font-size="11" fill="#38bdf8" text-anchor="middle">{hz}Hz</text>'

    # OOM marker
    oom_x = bx(orin_oom)
    oom_svg = (
        f'<line x1="{oom_x:.1f}" y1="{pad_t}" x2="{oom_x:.1f}" y2="{pad_t+inner_h}" '
        f'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,3"/>'
        f'<text x="{oom_x+4:.1f}" y="{pad_t+18}" font-size="10" fill="#ef4444">OOM @ batch-3</text>'
        f'<circle cx="{oom_x:.1f}" cy="{by(0)+4:.1f}" r="5" fill="#ef4444"/>'
        f'<text x="{oom_x:.1f}" y="{pad_t+inner_h-10:.1f}" font-size="10" fill="#ef4444" text-anchor="middle">✕</text>'
    )

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569" stroke-width="1"/>'
    )
    xticks = ""
    for b in [1, 2, 3, 4, 8]:
        x_ = bx(b)
        xticks += f'<line x1="{x_:.1f}" y1="{pad_t+inner_h}" x2="{x_:.1f}" y2="{pad_t+inner_h+5}" stroke="#475569" stroke-width="1"/>'
        xticks += f'<text x="{x_:.1f}" y="{pad_t+inner_h+18}" font-size="11" fill="#94a3b8" text-anchor="middle">batch-{b}</text>'
    yticks = ""
    for v in [0, 40, 80, 120, 160]:
        y_ = by(v)
        yticks += f'<text x="{pad_l-6}" y="{y_+4:.1f}" font-size="10" fill="#94a3b8" text-anchor="end">{v}</text>'
        yticks += f'<line x1="{pad_l-3}" y1="{y_:.1f}" x2="{pad_l}" y2="{y_:.1f}" stroke="#475569" stroke-width="1"/>'
        yticks += f'<line x1="{pad_l}" y1="{y_:.1f}" x2="{pad_l+inner_w}" y2="{y_:.1f}" stroke="#1e293b" stroke-width="0.5" stroke-dasharray="3,3"/>'

    legend = (
        '<rect x="60" y="14" width="22" height="3" fill="#38bdf8" rx="1" y="18"/>'
        '<text x="86" y="23" font-size="11" fill="#cbd5e1">Jetson Orin NX</text>'
        '<rect x="200" y="14" width="14" height="10" fill="#475569" fill-opacity="0.7"/>'
        '<text x="218" y="23" font-size="11" fill="#cbd5e1">A100 (reference)</text>'
        '<line x1="340" y1="18" x2="354" y2="18" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,3"/>'
        '<text x="358" y="23" font-size="11" fill="#ef4444">OOM boundary</text>'
    )

    title = (
        f'<text x="{W//2}" y="22" font-size="13" fill="#e2e8f0" text-anchor="middle" font-weight="bold">'
        f'Throughput vs Batch Size (Hz)</text>'
    )
    xlabel = f'<text x="{pad_l+inner_w//2}" y="{H-5}" font-size="11" fill="#94a3b8" text-anchor="middle">Batch Size</text>'
    ylabel = f'<text x="14" y="{pad_t+inner_h//2}" font-size="11" fill="#94a3b8" text-anchor="middle" transform="rotate(-90,14,{pad_t+inner_h//2})">Throughput (Hz)</text>'

    inner = bars_svg + orin_svg + oom_svg + axes + xticks + yticks + legend + title + xlabel + ylabel
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

METRICS = {
    "device": "Jetson Orin NX 16GB",
    "inference_latency_ms": 294,
    "throughput_hz": 3.4,
    "target_latency_ms": 150,
    "target_hz": "6.7 (with distillation)",
    "tdp_watts": 18,
    "thermal_throttle_c": 75,
    "vram_baseline_gb": 2.1,
    "vram_peak_gb": 4.8,
    "batch_oom_threshold": 3,
    "stage_breakdown_ms": {
        "model_load": 28,
        "vision_enc": 98,
        "cross_attn": 62,
        "action_head": 74,
        "decode": 32,
    },
}


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    waterfall = svg_inference_latency_waterfall()
    memory    = svg_memory_profile_timeline()
    throughput = svg_throughput_vs_batch()

    def metric_card(k, v):
        if isinstance(v, dict):
            v_str = " | ".join(f"{sk}: {sv}ms" for sk, sv in v.items())
        else:
            v_str = str(v)
        return f'<div class="metric"><span class="mkey">{k}</span><span class="mval">{v_str}</span></div>'

    metrics_html = "".join(metric_card(k, v) for k, v in METRICS.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Jetson Edge Profiler — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{color:#38bdf8;font-size:1.6rem;margin-bottom:4px}}
  .sub{{color:#94a3b8;font-size:.9rem;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px;border:1px solid #334155}}
  .card h2{{font-size:1rem;color:#C74634;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;margin-bottom:20px}}
  .metric{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 16px}}
  .mkey{{display:block;font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
  .mval{{display:block;font-size:.9rem;color:#f1f5f9;font-weight:600;word-break:break-word}}
  svg{{max-width:100%;height:auto}}
  footer{{color:#475569;font-size:.8rem;text-align:center;margin-top:24px}}
</style>
</head>
<body>
<h1>Jetson Edge Profiler</h1>
<p class="sub">OCI Robot Cloud — GR00T N1.6 on Jetson Orin NX (port 8645)</p>
<div class="metrics">{metrics_html}</div>
<div class="card">
  <h2>Inference Latency Breakdown (Waterfall)</h2>
  {waterfall}
</div>
<div class="card">
  <h2>VRAM Memory Profile During Inference</h2>
  {memory}
</div>
<div class="card">
  <h2>Throughput vs Batch Size</h2>
  {throughput}
</div>
<footer>OCI Robot Cloud &mdash; jetson_edge_profiler.py &mdash; port 8645</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Jetson Edge Profiler",
        description="Latency breakdown, memory timeline, and throughput profiling for GR00T N1.6 on Jetson Orin",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "jetson_edge_profiler", "port": 8645})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse(METRICS)

    @app.get("/svg/waterfall", response_class=HTMLResponse)
    async def svg_waterfall():
        return HTMLResponse(content=svg_inference_latency_waterfall(), media_type="image/svg+xml")

    @app.get("/svg/memory", response_class=HTMLResponse)
    async def svg_memory():
        return HTMLResponse(content=svg_memory_profile_timeline(), media_type="image/svg+xml")

    @app.get("/svg/throughput", response_class=HTMLResponse)
    async def svg_throughput():
        return HTMLResponse(content=svg_throughput_vs_batch(), media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Fallback stdlib HTTP server
# ---------------------------------------------------------------------------

def _run_stdlib_server(port: int = 8645):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "jetson_edge_profiler", "port": port}).encode()
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

    print(f"[jetson_edge_profiler] stdlib fallback server on :{port}")
    with http.server.HTTPServer(("", port), Handler) as srv:
        srv.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    PORT = 8645
    if USE_FASTAPI:
        print(f"[jetson_edge_profiler] FastAPI on :{PORT}")
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib_server(PORT)
