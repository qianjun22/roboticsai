"""Policy Compression Suite — port 8952

GR00T_v2 3B → 200M Jetson model compression dashboard.
Topics: LoRA/quant/pruning/distill Pareto, 91% SR at 6.7× smaller,
65ms INT8 TRT, cloud cost $0.43→$0.19/run.
"""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8952
TITLE = "Policy Compression Suite"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

COMPRESSION_METHODS = [
    {"name": "Baseline (3B)",      "params_m": 3000, "sr": 93.2, "latency_ms": 312, "cost": 0.43, "method": "none"},
    {"name": "LoRA r=64",          "params_m": 820,  "sr": 91.8, "latency_ms": 198, "cost": 0.31, "method": "lora"},
    {"name": "INT8 Quant",         "params_m": 750,  "sr": 90.5, "latency_ms": 141, "cost": 0.22, "method": "quant"},
    {"name": "Structured Pruning", "params_m": 480,  "sr": 88.1, "latency_ms": 119, "cost": 0.18, "method": "pruning"},
    {"name": "KD + LoRA",          "params_m": 320,  "sr": 91.4, "latency_ms": 89,  "cost": 0.21, "method": "distill"},
    {"name": "INT8 TRT (Jetson)",  "params_m": 200,  "sr": 91.0, "latency_ms": 65,  "cost": 0.19, "method": "trt"},
    {"name": "FP16 TRT",           "params_m": 200,  "sr": 91.5, "latency_ms": 78,  "cost": 0.20, "method": "trt"},
    {"name": "Aggressive Prune",   "params_m": 120,  "sr": 82.3, "latency_ms": 55,  "cost": 0.14, "method": "pruning"},
]

METHOD_COLORS = {
    "none":    "#94a3b8",
    "lora":    "#38bdf8",
    "quant":   "#a78bfa",
    "pruning": "#fb923c",
    "distill": "#4ade80",
    "trt":     "#C74634",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def pareto_chart() -> str:
    """Scatter: x=params_m, y=SR, size~latency — Compression Pareto."""
    W, H = 560, 340
    PAD = {"l": 60, "r": 20, "t": 40, "b": 60}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]

    x_min, x_max = 100, 3100
    y_min, y_max = 80, 96

    def cx(v): return PAD["l"] + (v - x_min) / (x_max - x_min) * pw
    def cy(v): return PAD["t"] + ph - (v - y_min) / (y_max - y_min) * ph

    lines = []
    # Grid
    for xg in [500, 1000, 1500, 2000, 2500, 3000]:
        x = cx(xg)
        lines.append(f'<line x1="{x:.1f}" y1="{PAD["t"]}" x2="{x:.1f}" y2="{PAD["t"]+ph}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{PAD["t"]+ph+16}" fill="#64748b" font-size="10" text-anchor="middle">{xg}M</text>')
    for yg in [82, 84, 86, 88, 90, 92, 94]:
        y = cy(yg)
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{PAD["l"]-8}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yg}%</text>')

    # Pareto frontier (sorted by params ascending, SR descending per step)
    sorted_pts = sorted(COMPRESSION_METHODS, key=lambda d: d["params_m"])
    best_sr = -1
    frontier = []
    for p in sorted_pts:
        if p["sr"] >= best_sr:
            frontier.append(p)
            best_sr = p["sr"]
    if len(frontier) > 1:
        pts_str = " ".join(f"{cx(p['params_m']):.1f},{cy(p['sr']):.1f}" for p in frontier)
        lines.append(f'<polyline points="{pts_str}" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5"/>')

    # Dots
    for d in COMPRESSION_METHODS:
        x = cx(d["params_m"])
        y = cy(d["sr"])
        r = 6 + math.sqrt(d["latency_ms"]) * 0.5
        color = METHOD_COLORS.get(d["method"], "#94a3b8")
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" opacity="0.85" stroke="#0f172a" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{y-r-4:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{d["name"]}</text>')

    # Axes labels
    lines.append(f'<text x="{PAD["l"]+pw/2:.1f}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">Model Size (params)</text>')
    lines.append(f'<text x="14" y="{PAD["t"]+ph/2:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PAD["t"]+ph/2:.1f})">Success Rate (%)</text>')
    lines.append(f'<text x="{PAD["l"]+pw/2:.1f}" y="{PAD["t"]-12}" fill="#C74634" font-size="13" font-weight="bold" text-anchor="middle">Compression Pareto (size vs SR)</text>')

    inner = "\n".join(lines)
    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


def sr_vs_size_chart() -> str:
    """Bar: SR grouped by method, annotated with latency."""
    W, H = 560, 320
    PAD = {"l": 55, "r": 20, "t": 40, "b": 70}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]

    N = len(COMPRESSION_METHODS)
    bar_w = pw / N * 0.7
    gap = pw / N
    y_min, y_max = 78, 96

    def bar_h(sr):
        return (sr - y_min) / (y_max - y_min) * ph

    lines = []
    # Grid
    for yg in [80, 84, 88, 92, 96]:
        y = PAD["t"] + ph - bar_h(yg)
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{PAD["l"]-6}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yg}%</text>')

    for i, d in enumerate(COMPRESSION_METHODS):
        x = PAD["l"] + i * gap + (gap - bar_w) / 2
        bh = bar_h(d["sr"])
        y = PAD["t"] + ph - bh
        color = METHOD_COLORS.get(d["method"], "#94a3b8")
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="3"/>')
        lines.append(f'<text x="{x+bar_w/2:.1f}" y="{y-4:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{d["sr"]}%</text>')
        lines.append(f'<text x="{x+bar_w/2:.1f}" y="{PAD["t"]+ph+14}" fill="#94a3b8" font-size="8" text-anchor="middle" transform="rotate(-35,{x+bar_w/2:.1f},{PAD["t"]+ph+14})">{d["name"]}</text>')
        # latency annotation
        lines.append(f'<text x="{x+bar_w/2:.1f}" y="{y+bh/2+4:.1f}" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">{d["latency_ms"]}ms</text>')

    lines.append(f'<text x="{PAD["l"]+pw/2:.1f}" y="{PAD["t"]-12}" fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">SR vs Model (latency annotated)</text>')
    lines.append(f'<text x="14" y="{PAD["t"]+ph/2:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PAD["t"]+ph/2:.1f})">Success Rate (%)</text>')

    inner = "\n".join(lines)
    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{inner}</svg>'


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    pareto_svg = pareto_chart()
    sr_svg = sr_vs_size_chart()

    rows = ""
    for d in COMPRESSION_METHODS:
        highlight = ' style="background:#1e3a4a"' if d["name"] == "INT8 TRT (Jetson)" else ""
        rows += f"""
        <tr{highlight}>
          <td>{d['name']}</td>
          <td style="text-align:right">{d['params_m']}M</td>
          <td style="text-align:right">{d['sr']}%</td>
          <td style="text-align:right">{d['latency_ms']} ms</td>
          <td style="text-align:right">${d['cost']:.2f}</td>
          <td><span style="background:{METHOD_COLORS.get(d['method'],'#94a3b8')};color:#0f172a;padding:2px 8px;border-radius:4px;font-size:12px">{d['method']}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{TITLE}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 28px; }}
    h1 {{ color: #C74634; font-size: 26px; margin-bottom: 6px; }}
    h2 {{ color: #38bdf8; font-size: 16px; margin: 24px 0 10px; }}
    .meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px 24px; min-width: 160px; }}
    .kpi .val {{ font-size: 28px; font-weight: bold; color: #C74634; }}
    .kpi .lbl {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
    .charts {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 28px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background: #1e293b; color: #94a3b8; padding: 10px 14px; text-align: left; }}
    td {{ padding: 9px 14px; border-bottom: 1px solid #1e293b; }}
    tr:hover {{ background: #1e293b88; }}
    .badge-trt {{ background: #C74634; color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="meta">Port {PORT} &nbsp;|&nbsp; GR00T_v2 3B → 200M Jetson &nbsp;|&nbsp; INT8 TRT: 65 ms, 91% SR, $0.19/run</p>

  <div class="kpi-row">
    <div class="kpi"><div class="val">6.7×</div><div class="lbl">Size Reduction (3B→200M)</div></div>
    <div class="kpi"><div class="val">91%</div><div class="lbl">Success Rate (INT8 TRT)</div></div>
    <div class="kpi"><div class="val">65 ms</div><div class="lbl">Jetson Latency (INT8)</div></div>
    <div class="kpi"><div class="val">$0.19</div><div class="lbl">Cost/Run (vs $0.43 base)</div></div>
    <div class="kpi"><div class="val">56%</div><div class="lbl">Cloud Cost Reduction</div></div>
  </div>

  <h2>Compression Pareto (size vs SR)</h2>
  <div class="charts">
    {pareto_svg}
    {sr_svg}
  </div>

  <h2>Method Comparison Table</h2>
  <table>
    <thead><tr><th>Method</th><th style="text-align:right">Params</th><th style="text-align:right">SR</th><th style="text-align:right">Latency</th><th style="text-align:right">Cost/Run</th><th>Type</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    @app.get("/api/methods")
    def api_methods():
        return COMPRESSION_METHODS

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        srv = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{TITLE} running on http://0.0.0.0:{PORT}")
        srv.serve_forever()
