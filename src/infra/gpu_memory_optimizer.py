"""GPU Memory Optimizer — FastAPI service on port 8280.

Optimizes GPU memory allocation for GR00T training to maximize
batch size and throughput across 4 optimization levels.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

CONFIGS = [
    {
        "name": "baseline",
        "label": "Baseline",
        "total_gb": 61.4,
        "model_weights": 13.4,
        "activations": 28.6,
        "gradients": 13.4,
        "optimizer_states": 6.0,
        "batch_size": 1,
        "throughput": 1.1,
        "color": "#ef4444",
    },
    {
        "name": "gradient_checkpointing",
        "label": "Grad Checkpoint",
        "total_gb": 44.8,
        "model_weights": 13.4,
        "activations": 12.0,
        "gradients": 13.4,
        "optimizer_states": 6.0,
        "batch_size": 2,
        "throughput": 1.7,
        "color": "#f97316",
    },
    {
        "name": "fp16",
        "label": "FP16",
        "total_gb": 36.2,
        "model_weights": 6.7,
        "activations": 16.1,
        "gradients": 6.7,
        "optimizer_states": 6.7,
        "batch_size": 4,
        "throughput": 2.35,
        "color": "#eab308",
    },
    {
        "name": "fp16_gc_offload",
        "label": "FP16+GC+Offload",
        "total_gb": 19.7,
        "model_weights": 6.7,
        "activations": 4.2,
        "gradients": 3.4,
        "optimizer_states": 5.4,
        "batch_size": 8,
        "throughput": 3.1,
        "color": "#22c55e",
    },
]

# 12 scatter configs for throughput vs memory
SCATTER_CONFIGS = [
    {"mem": 61.4, "tp": 1.1, "name": "baseline"},
    {"mem": 58.2, "tp": 1.15, "name": "baseline+tf32"},
    {"mem": 52.0, "tp": 1.3, "name": "gc_only"},
    {"mem": 44.8, "tp": 1.7, "name": "grad_checkpoint"},
    {"mem": 40.1, "tp": 1.9, "name": "gc+acc"},
    {"mem": 36.2, "tp": 2.35, "name": "fp16", "current": True},
    {"mem": 33.5, "tp": 2.5, "name": "fp16+gc"},
    {"mem": 28.1, "tp": 2.8, "name": "fp16+gc_full"},
    {"mem": 24.0, "tp": 2.9, "name": "fp16+gc+fused"},
    {"mem": 22.3, "tp": 3.0, "name": "fp16+gc+fused+acc"},
    {"mem": 19.7, "tp": 3.1, "name": "fp16+gc+offload", "recommended": True},
    {"mem": 17.1, "tp": 2.95, "name": "aggressive_offload"},
]

# Pareto frontier (max throughput at each memory level, sorted ascending mem)
PARETO = [
    {"mem": 17.1, "tp": 2.95},
    {"mem": 19.7, "tp": 3.1},
    {"mem": 22.3, "tp": 3.0},
    {"mem": 24.0, "tp": 2.9},
    {"mem": 28.1, "tp": 2.8},
    {"mem": 36.2, "tp": 2.35},
    {"mem": 44.8, "tp": 1.7},
    {"mem": 61.4, "tp": 1.1},
]


def build_html() -> str:
    # -----------------------------------------------------------------------
    # SVG 1 — stacked bar: memory allocation breakdown per config
    # -----------------------------------------------------------------------
    svg1_w, svg1_h = 640, 320
    bar_w = 80
    gap = 40
    left_pad = 70
    top_pad = 30
    bottom_pad = 60
    chart_h = svg1_h - top_pad - bottom_pad
    max_gb = 70.0

    seg_colors = {
        "model_weights": "#38bdf8",
        "activations": "#C74634",
        "gradients": "#a78bfa",
        "optimizer_states": "#34d399",
    }
    seg_labels = {
        "model_weights": "Model Weights",
        "activations": "Activations",
        "gradients": "Gradients",
        "optimizer_states": "Optimizer States",
    }

    bars_svg = ""
    for i, cfg in enumerate(CONFIGS):
        x = left_pad + i * (bar_w + gap)
        y_cursor = top_pad + chart_h  # start from bottom
        for seg_key in ["optimizer_states", "gradients", "activations", "model_weights"]:
            val = cfg[seg_key]
            seg_h = (val / max_gb) * chart_h
            y_cursor -= seg_h
            color = seg_colors[seg_key]
            bars_svg += f'<rect x="{x}" y="{y_cursor:.1f}" width="{bar_w}" height="{seg_h:.1f}" fill="{color}" opacity="0.85"/>\n'
        # total label
        total_y = top_pad + chart_h - (cfg["total_gb"] / max_gb) * chart_h - 6
        bars_svg += f'<text x="{x + bar_w/2:.0f}" y="{total_y:.0f}" fill="#e2e8f0" font-size="11" text-anchor="middle">{cfg["total_gb"]}GB</text>\n'
        # batch size annotation
        batch_y = top_pad + chart_h + 18
        bars_svg += f'<text x="{x + bar_w/2:.0f}" y="{batch_y}" fill="#38bdf8" font-size="10" text-anchor="middle">bs={cfg["batch_size"]}</text>\n'
        # x-axis label
        label_y = top_pad + chart_h + 34
        bars_svg += f'<text x="{x + bar_w/2:.0f}" y="{label_y}" fill="#94a3b8" font-size="9" text-anchor="middle">{cfg["label"]}</text>\n'

    # y-axis ticks
    yticks_svg = ""
    for tick in [0, 20, 40, 60]:
        y = top_pad + chart_h - (tick / max_gb) * chart_h
        yticks_svg += f'<line x1="{left_pad - 5}" y1="{y:.1f}" x2="{left_pad + 4 * (bar_w + gap) - gap}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>\n'
        yticks_svg += f'<text x="{left_pad - 8}" y="{y + 4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{tick}</text>\n'

    # legend
    legend_svg = ""
    lx, ly = left_pad, top_pad - 18
    for k, color in seg_colors.items():
        legend_svg += f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}"/>'
        legend_svg += f'<text x="{lx + 13}" y="{ly + 9}" fill="#cbd5e1" font-size="9">{seg_labels[k]}</text>'
        lx += 130

    svg1 = f"""<svg viewBox="0 0 {svg1_w} {svg1_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{svg1_w}px;background:#1e293b;border-radius:8px">
  <text x="{svg1_w//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">GPU Memory Allocation Breakdown by Optimization Level</text>
  <text x="14" y="{top_pad + chart_h//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,14,{top_pad + chart_h//2})">Memory (GB)</text>
  {yticks_svg}
  {bars_svg}
  {legend_svg}
</svg>"""

    # -----------------------------------------------------------------------
    # SVG 2 — scatter: throughput vs memory usage
    # -----------------------------------------------------------------------
    svg2_w, svg2_h = 640, 320
    pad_l, pad_r, pad_t, pad_b = 70, 30, 30, 50
    plot_w = svg2_w - pad_l - pad_r
    plot_h = svg2_h - pad_t - pad_b
    mem_min, mem_max = 14.0, 66.0
    tp_min, tp_max = 0.8, 3.4

    def sx(mem):
        return pad_l + (mem - mem_min) / (mem_max - mem_min) * plot_w

    def sy(tp):
        return pad_t + plot_h - (tp - tp_min) / (tp_max - tp_min) * plot_h

    # grid
    grid_svg = ""
    for m in [20, 30, 40, 50, 60]:
        gx = sx(m)
        grid_svg += f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t + plot_h}" stroke="#1e3a5f" stroke-width="1"/>'
        grid_svg += f'<text x="{gx:.1f}" y="{pad_t + plot_h + 14}" fill="#64748b" font-size="9" text-anchor="middle">{m}GB</text>'
    for t in [1.0, 1.5, 2.0, 2.5, 3.0]:
        gy = sy(t)
        grid_svg += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        grid_svg += f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{t:.1f}</text>'

    # Pareto frontier line
    pareto_sorted = sorted(PARETO, key=lambda p: p["mem"])
    pareto_pts = " ".join(f"{sx(p['mem']):.1f},{sy(p['tp']):.1f}" for p in pareto_sorted)
    pareto_svg = f'<polyline points="{pareto_pts}" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>'

    # dots
    dots_svg = ""
    for cfg in SCATTER_CONFIGS:
        cx_, cy_ = sx(cfg["mem"]), sy(cfg["tp"])
        is_current = cfg.get("current", False)
        is_rec = cfg.get("recommended", False)
        if is_current:
            color = "#facc15"
            r = 7
        elif is_rec:
            color = "#22c55e"
            r = 7
        else:
            color = "#7dd3fc"
            r = 5
        dots_svg += f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="{r}" fill="{color}" opacity="0.9"/>'
        label_offset = -10 if cy_ > pad_t + 20 else 14
        dots_svg += f'<text x="{cx_:.1f}" y="{cy_ + label_offset:.1f}" fill="#cbd5e1" font-size="8" text-anchor="middle">{cfg["name"]}</text>'

    # upgrade path arrow (current → recommended)
    curr = next(c for c in SCATTER_CONFIGS if c.get("current"))
    rec = next(c for c in SCATTER_CONFIGS if c.get("recommended"))
    ax1, ay1 = sx(curr["mem"]), sy(curr["tp"])
    ax2, ay2 = sx(rec["mem"]), sy(rec["tp"])
    arrow_svg = f'<line x1="{ax1:.1f}" y1="{ay1:.1f}" x2="{ax2:.1f}" y2="{ay2:.1f}" stroke="#C74634" stroke-width="2" marker-end="url(#arrowhead)"/>'
    defs_svg = '<defs><marker id="arrowhead" markerWidth="6" markerHeight="4" refX="3" refY="2" orient="auto"><polygon points="0 0, 6 2, 0 4" fill="#C74634"/></marker></defs>'

    # legend
    leg2 = (f'<circle cx="{pad_l+10}" cy="{pad_t+10}" r="5" fill="#facc15"/>'
            f'<text x="{pad_l+18}" y="{pad_t+14}" fill="#cbd5e1" font-size="9">Current (fp16)</text>'
            f'<circle cx="{pad_l+100}" cy="{pad_t+10}" r="5" fill="#22c55e"/>'
            f'<text x="{pad_l+108}" y="{pad_t+14}" fill="#cbd5e1" font-size="9">Recommended</text>'
            f'<line x1="{pad_l+200}" y1="{pad_t+10}" x2="{pad_l+220}" y2="{pad_t+10}" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3"/>'
            f'<text x="{pad_l+224}" y="{pad_t+14}" fill="#cbd5e1" font-size="9">Pareto Frontier</text>')

    svg2 = f"""<svg viewBox="0 0 {svg2_w} {svg2_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{svg2_w}px;background:#1e293b;border-radius:8px">
  {defs_svg}
  <text x="{svg2_w//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Throughput vs Memory Usage — 12 Configurations</text>
  <text x="12" y="{pad_t + plot_h//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,12,{pad_t + plot_h//2})">Throughput (it/s)</text>
  <text x="{pad_l + plot_w//2}" y="{pad_t + plot_h + 38}" fill="#94a3b8" font-size="10" text-anchor="middle">Memory Usage (GB)</text>
  {grid_svg}
  {pareto_svg}
  {arrow_svg}
  {dots_svg}
  {leg2}
</svg>"""

    # -----------------------------------------------------------------------
    # Metrics cards
    # -----------------------------------------------------------------------
    recommended_cfg = CONFIGS[3]  # fp16+gc+offload
    current_cfg = CONFIGS[2]      # fp16
    memory_efficiency_score = round((1 - recommended_cfg["total_gb"] / CONFIGS[0]["total_gb"]) * 100, 1)
    max_batch_a100_40 = 6  # fp16+GC fits 40GB
    tp_per_gb = round(recommended_cfg["throughput"] / recommended_cfg["total_gb"], 4)

    metrics_html = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px">
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">MEMORY EFFICIENCY SCORE</div>
        <div style="color:#22c55e;font-size:28px;font-weight:bold">{memory_efficiency_score}%</div>
        <div style="color:#475569;font-size:10px">vs baseline</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">MAX BATCH (A100 40GB)</div>
        <div style="color:#38bdf8;font-size:28px;font-weight:bold">{max_batch_a100_40}</div>
        <div style="color:#475569;font-size:10px">FP16+GC config</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">THROUGHPUT / GB</div>
        <div style="color:#a78bfa;font-size:28px;font-weight:bold">{tp_per_gb}</div>
        <div style="color:#475569;font-size:10px">it/s per GB (recommended)</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">RECOMMENDED CONFIG</div>
        <div style="color:#C74634;font-size:14px;font-weight:bold">FP16+GC+Offload</div>
        <div style="color:#475569;font-size:10px">19.7GB · 3.1 it/s · bs=8</div>
      </div>
    </div>
    """

    # config table
    rows = ""
    for cfg in CONFIGS:
        rows += f"""<tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:#e2e8f0">{cfg['label']}</td>
          <td style="padding:8px 12px;color:#38bdf8;text-align:right">{cfg['total_gb']}</td>
          <td style="padding:8px 12px;color:#a78bfa;text-align:right">{cfg['batch_size']}</td>
          <td style="padding:8px 12px;color:#22c55e;text-align:right">{cfg['throughput']}</td>
          <td style="padding:8px 12px;color:#94a3b8;text-align:right">{round(cfg['throughput']/cfg['total_gb']*100,2)}</td>
        </tr>"""

    table_html = f"""
    <table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;margin-bottom:24px">
      <thead>
        <tr style="background:#0f172a">
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">CONFIG</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">TOTAL GB</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">BATCH SIZE</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">THROUGHPUT (it/s)</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">TP/GB (x100)</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>GPU Memory Optimizer — Port 8280</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #38bdf8; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .section-title {{ color: #94a3b8; font-size: 13px; font-weight: 600; text-transform: uppercase;
                      letter-spacing: 0.05em; margin: 20px 0 10px; }}
    .badge {{ display:inline-block;background:#C74634;color:#fff;font-size:10px;padding:2px 8px;
              border-radius:4px;margin-left:8px;vertical-align:middle; }}
  </style>
</head>
<body>
  <h1>GPU Memory Optimizer <span class="badge">PORT 8280</span></h1>
  <div class="subtitle">GR00T N1.6 Training — Memory allocation optimization for A100 80GB / A100 40GB &nbsp;·&nbsp; Updated: {now}</div>

  {metrics_html}

  <div class="section-title">Memory Allocation Breakdown</div>
  {svg1}

  <div class="section-title" style="margin-top:28px">Throughput vs Memory — Pareto Analysis</div>
  {svg2}

  <div class="section-title" style="margin-top:28px">Configuration Details</div>
  {table_html}
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="GPU Memory Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gpu_memory_optimizer", "port": 8280}

    @app.get("/api/configs")
    async def get_configs():
        return {"configs": CONFIGS, "scatter": SCATTER_CONFIGS, "pareto": PARETO}

else:
    # Fallback to stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = b'{"status":"ok","port":8280}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8280)
    else:
        print("[gpu_memory_optimizer] FastAPI not found — using stdlib http.server on port 8280")
        server = HTTPServer(("0.0.0.0", 8280), Handler)
        server.serve_forever()
