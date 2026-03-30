#!/usr/bin/env python3
"""
Model Compression Analyzer — port 8220
Analyzes GR00T model compression techniques for edge deployment on Jetson.
Cycle-40A | OCI Robot Cloud
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data — realistic compression benchmark results
# ---------------------------------------------------------------------------

COMPRESSION_METHODS = [
    {
        "name": "baseline_3B",
        "label": "Baseline 3B",
        "size_gb": 6.7,
        "sr_pct": 71.0,
        "latency_ms": 226,
        "compression_ratio": 1.0,
        "target": "cloud",
        "color": "#94a3b8",
        "recommended_for": "Cloud / research",
    },
    {
        "name": "pruning_50pct",
        "label": "Pruning 50%",
        "size_gb": 3.8,
        "sr_pct": 67.5,
        "latency_ms": 148,
        "compression_ratio": 1.76,
        "target": "cloud",
        "color": "#38bdf8",
        "recommended_for": "Cloud cost reduction",
    },
    {
        "name": "quantize_int8",
        "label": "Quantize INT8",
        "size_gb": 1.7,
        "sr_pct": 69.0,
        "latency_ms": 82,
        "compression_ratio": 3.94,
        "target": "jetson_agx",
        "color": "#a78bfa",
        "recommended_for": "Jetson AGX Xavier",
    },
    {
        "name": "knowledge_distill_1.5B",
        "label": "Distill 1.5B",
        "size_gb": 3.1,
        "sr_pct": 68.0,
        "latency_ms": 45,
        "compression_ratio": 2.16,
        "target": "jetson_orin",
        "color": "#34d399",
        "recommended_for": "Jetson Orin (best latency)",
    },
    {
        "name": "quantize_FP8",
        "label": "Quantize FP8",
        "size_gb": 3.2,
        "sr_pct": 70.0,
        "latency_ms": 109,
        "compression_ratio": 2.09,
        "target": "jetson_agx",
        "color": "#C74634",
        "recommended_for": "Jetson AGX Orin (best Pareto)",
    },
]

TARGET_COLORS = {
    "cloud": "#38bdf8",
    "jetson_agx": "#C74634",
    "jetson_orin": "#34d399",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_bar_chart_svg() -> str:
    """Bar chart: model size (GB) and SR% side by side for each compression method."""
    W, H = 700, 320
    pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 80
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    methods = COMPRESSION_METHODS
    n = len(methods)
    group_w = chart_w / n
    bar_w = group_w * 0.32
    gap = group_w * 0.06

    max_size = 8.0   # GB axis
    max_sr = 80.0    # SR% axis (secondary, scaled to same px height)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    # background
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    # title
    lines.append(f'<text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Model Size (GB) vs Success Rate (%) by Compression Method</text>')

    # y-axis grid lines (size)
    for v in [2, 4, 6, 8]:
        py = pad_t + chart_h - (v / max_size) * chart_h
        lines.append(f'<line x1="{pad_l}" y1="{py:.1f}" x2="{W - pad_r}" y2="{py:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{py + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{v}GB</text>')

    # bars
    for i, m in enumerate(methods):
        cx = pad_l + i * group_w + group_w / 2

        # size bar (left of pair)
        bh_size = (m["size_gb"] / max_size) * chart_h
        bx_size = cx - bar_w - gap / 2
        by_size = pad_t + chart_h - bh_size
        lines.append(f'<rect x="{bx_size:.1f}" y="{by_size:.1f}" width="{bar_w:.1f}" height="{bh_size:.1f}" fill="{m["color"]}" rx="2" opacity="0.9"/>')
        lines.append(f'<text x="{bx_size + bar_w/2:.1f}" y="{by_size - 4:.1f}" text-anchor="middle" fill="{m["color"]}" font-size="9" font-family="monospace">{m["size_gb"]}G</text>')

        # SR bar (right of pair)
        bh_sr = (m["sr_pct"] / max_sr) * chart_h
        bx_sr = cx + gap / 2
        by_sr = pad_t + chart_h - bh_sr
        lines.append(f'<rect x="{bx_sr:.1f}" y="{by_sr:.1f}" width="{bar_w:.1f}" height="{bh_sr:.1f}" fill="{m["color"]}" rx="2" opacity="0.5"/>')
        lines.append(f'<text x="{bx_sr + bar_w/2:.1f}" y="{by_sr - 4:.1f}" text-anchor="middle" fill="{m["color"]}" font-size="9" font-family="monospace">{m["sr_pct"]}%</text>')

        # x-axis label
        label_y = pad_t + chart_h + 18
        lines.append(f'<text x="{cx:.1f}" y="{label_y}" text-anchor="middle" fill="#cbd5e1" font-size="9" font-family="monospace">{m["label"]}</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')

    # legend
    lx, ly = pad_l, H - 18
    lines.append(f'<rect x="{lx}" y="{ly - 8}" width="12" height="10" fill="#94a3b8" rx="1"/>')
    lines.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="9" font-family="monospace">Model Size (GB)</text>')
    lines.append(f'<rect x="{lx + 130}" y="{ly - 8}" width="12" height="10" fill="#94a3b8" opacity="0.5" rx="1"/>')
    lines.append(f'<text x="{lx + 146}" y="{ly}" fill="#94a3b8" font-size="9" font-family="monospace">Success Rate (%)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def build_scatter_svg() -> str:
    """Scatter: inference latency (ms) vs model size (GB) with Pareto frontier."""
    W, H = 700, 340
    pad_l, pad_r, pad_t, pad_b = 65, 140, 40, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_x = 8.0   # size GB
    max_y = 260.0 # latency ms

    def px(size_gb):
        return pad_l + (size_gb / max_x) * chart_w

    def py(lat_ms):
        return pad_t + chart_h - (lat_ms / max_y) * chart_h

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{(W - pad_r + pad_l)//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Inference Latency (ms) vs Model Size (GB)</text>')

    # grid
    for v in [50, 100, 150, 200, 250]:
        yy = py(v)
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l + chart_w}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{v}ms</text>')
    for v in [2, 4, 6, 8]:
        xx = px(v)
        lines.append(f'<line x1="{xx:.1f}" y1="{pad_t}" x2="{xx:.1f}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{xx:.1f}" y="{pad_t + chart_h + 16}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{v}GB</text>')

    # Pareto frontier — sort by size, keep only non-dominated points
    pareto_pts = sorted(COMPRESSION_METHODS, key=lambda m: m["size_gb"])
    best_lat = 999
    frontier = []
    for m in pareto_pts:
        if m["latency_ms"] < best_lat:
            best_lat = m["latency_ms"]
            frontier.append(m)

    if len(frontier) >= 2:
        pts_str = " ".join(f"{px(m['size_gb']):.1f},{py(m['latency_ms']):.1f}" for m in frontier)
        lines.append(f'<polyline points="{pts_str}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.8"/>')
        lines.append(f'<text x="{px(frontier[-1]["size_gb"]) + 6:.1f}" y="{py(frontier[-1]["latency_ms"]) - 8:.1f}" fill="#fbbf24" font-size="9" font-family="monospace">Pareto</text>')

    # points
    for m in COMPRESSION_METHODS:
        cx_ = px(m["size_gb"])
        cy_ = py(m["latency_ms"])
        col = TARGET_COLORS.get(m["target"], "#94a3b8")
        lines.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="8" fill="{col}" stroke="#0f172a" stroke-width="2" opacity="0.9"/>')
        lines.append(f'<text x="{cx_ + 11:.1f}" y="{cy_ + 4:.1f}" fill="#e2e8f0" font-size="9" font-family="monospace">{m["label"]}</text>')
        lines.append(f'<text x="{cx_ + 11:.1f}" y="{cy_ + 15:.1f}" fill="#94a3b8" font-size="8" font-family="monospace">{m["latency_ms"]}ms/{m["size_gb"]}GB</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>')

    # axis labels
    lines.append(f'<text x="{pad_l + chart_w//2}" y="{H - 8}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Model Size (GB)</text>')
    lines.append(f'<text x="14" y="{pad_t + chart_h//2}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90 14 {pad_t + chart_h//2})">Latency (ms)</text>')

    # legend (target colors)
    legend_x = W - pad_r + 14
    lines.append(f'<text x="{legend_x}" y="{pad_t + 10}" fill="#94a3b8" font-size="10" font-family="monospace" font-weight="bold">Target</text>')
    for idx, (tgt, col) in enumerate(TARGET_COLORS.items()):
        ly2 = pad_t + 28 + idx * 18
        lines.append(f'<circle cx="{legend_x + 6}" cy="{ly2 - 4}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{legend_x + 16}" y="{ly2}" fill="#cbd5e1" font-size="9" font-family="monospace">{tgt}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    bar_svg = build_bar_chart_svg()
    scatter_svg = build_scatter_svg()

    rows = ""
    for m in COMPRESSION_METHODS:
        rows += f"""
        <tr>
          <td>{m['label']}</td>
          <td>{m['size_gb']} GB</td>
          <td>{m['sr_pct']}%</td>
          <td>{m['latency_ms']} ms</td>
          <td>{m['compression_ratio']:.2f}x</td>
          <td><span class="badge badge-{m['target']}">{m['target']}</span></td>
          <td style="color:#94a3b8;font-size:0.8rem">{m['recommended_for']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Model Compression Analyzer | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-label {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ color: #38bdf8; font-size: 1.6rem; font-weight: bold; margin: 4px 0; }}
    .card-sub {{ color: #64748b; font-size: 0.75rem; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 16px; }}
    svg {{ max-width: 100%; height: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th {{ color: #94a3b8; text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; font-size: 0.75rem; text-transform: uppercase; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #243044; }}
    .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }}
    .badge-cloud {{ background: #1e3a5f; color: #38bdf8; }}
    .badge-jetson_agx {{ background: #4a1a14; color: #C74634; }}
    .badge-jetson_orin {{ background: #0f3322; color: #34d399; }}
    .ts {{ color: #475569; font-size: 0.72rem; margin-top: 8px; }}
  </style>
</head>
<body>
  <h1>Model Compression Analyzer</h1>
  <p class="subtitle">GR00T compression benchmarks for edge deployment &mdash; OCI Robot Cloud &bull; Port 8220</p>

  <div class="grid">
    <div class="card">
      <div class="card-label">Best Pareto (FP8)</div>
      <div class="card-value">3.2 GB</div>
      <div class="card-sub">109ms latency &bull; SR 70%</div>
    </div>
    <div class="card">
      <div class="card-label">Best Jetson Latency</div>
      <div class="card-value">45 ms</div>
      <div class="card-sub">Distill 1.5B &bull; Jetson Orin</div>
    </div>
    <div class="card">
      <div class="card-label">Max Compression</div>
      <div class="card-value">3.94x</div>
      <div class="card-sub">INT8 quantization &bull; 1.7 GB</div>
    </div>
    <div class="card">
      <div class="card-label">SR Retention (FP8)</div>
      <div class="card-value">98.6%</div>
      <div class="card-sub">70% vs baseline 71%</div>
    </div>
  </div>

  <div class="section">
    <h2>Size vs Success Rate by Compression Method</h2>
    {bar_svg}
  </div>

  <div class="section">
    <h2>Latency vs Model Size &mdash; Pareto Frontier</h2>
    {scatter_svg}
  </div>

  <div class="section">
    <h2>Compression Method Comparison</h2>
    <table>
      <thead>
        <tr>
          <th>Method</th><th>Size</th><th>SR %</th><th>Latency</th><th>Ratio</th><th>Target</th><th>Recommended For</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <p class="ts">Updated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} UTC &bull; OCI Robot Cloud cycle-40A</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Model Compression Analyzer",
        description="GR00T model compression analysis for edge deployment on Jetson",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/methods")
    async def get_methods():
        return {"methods": COMPRESSION_METHODS, "count": len(COMPRESSION_METHODS)}

    @app.get("/api/recommended")
    async def get_recommended():
        fp8 = next(m for m in COMPRESSION_METHODS if m["name"] == "quantize_FP8")
        distill = next(m for m in COMPRESSION_METHODS if m["name"] == "knowledge_distill_1.5B")
        return {
            "cloud": "baseline_3B",
            "jetson_agx_orin_best_pareto": fp8,
            "jetson_orin_best_latency": distill,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "model_compression_analyzer", "port": 8220}

else:
    # Stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8220)
    else:
        server = HTTPServer(("0.0.0.0", 8220), Handler)
        print("[model_compression_analyzer] stdlib fallback running on :8220")
        server.serve_forever()
