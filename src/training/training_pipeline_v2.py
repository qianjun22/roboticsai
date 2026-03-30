"""Training Pipeline v2 — FastAPI service on port 8287.

Enhanced end-to-end training pipeline v2 with automated hyperparameter
tuning and checkpointing, plus a comparison Gantt vs v1.
Fallback to stdlib http.server if FastAPI/uvicorn are not installed.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# Pipeline stages: (name, v1_start_h, v1_dur_h, v2_start_h, v2_dur_h)
PIPELINE_STAGES = [
    {"name": "data_prep",  "v1_start": 0.0, "v1_dur": 0.5, "v2_start": 0.0,  "v2_dur": 0.4},
    {"name": "augment",    "v1_start": 0.5, "v1_dur": 0.6, "v2_start": 0.4,  "v2_dur": 0.5},
    {"name": "train",      "v1_start": 1.1, "v1_dur": 1.8, "v2_start": 0.9,  "v2_dur": 1.4},
    {"name": "eval",       "v1_start": 2.9, "v1_dur": 0.6, "v2_start": 1.7,  "v2_dur": 0.5},  # parallel w/ train in v2
    {"name": "checkpoint", "v1_start": 3.5, "v1_dur": 0.2, "v2_start": 2.2,  "v2_dur": 0.2},
    {"name": "report",     "v1_start": 3.7, "v1_dur": 0.3, "v2_start": 2.4,  "v2_dur": 0.3},
]
V1_TOTAL = max(s["v1_start"] + s["v1_dur"] for s in PIPELINE_STAGES)   # 4.0 h
V2_TOTAL = max(s["v2_start"] + s["v2_dur"] for s in PIPELINE_STAGES)   # 2.7 h

# HPO sweep: 25 runs (lr, chunk_size, lora_rank, SR)
random.seed(42)
HPO_RUNS = []
_lr_opts    = [1e-5, 2e-5, 3e-5, 5e-5, 8e-5]
_chunk_opts = [8, 16, 32]
_rank_opts  = [8, 16, 32]
for _ in range(25):
    lr    = random.choice(_lr_opts)
    chunk = random.choice(_chunk_opts)
    rank  = random.choice(_rank_opts)
    # Synthetic SR model: peaks near lr=3e-5, chunk=16, rank=16
    sr = (0.62
          - 4.0  * (math.log10(lr / 3e-5)) ** 2
          - 0.002 * (chunk - 16) ** 2
          - 0.001 * (rank  - 16) ** 2
          + random.uniform(-0.03, 0.03))
    sr = max(0.45, min(0.90, sr))
    HPO_RUNS.append({"lr": lr, "chunk": chunk, "rank": rank, "sr": round(sr, 3)})

# Force the optimal point to exist
HPO_RUNS[0] = {"lr": 3e-5, "chunk": 16, "rank": 16, "sr": 0.79}

# Pareto front (best SR per cost bracket) — SR + cost proxy = lr*1e6 * chunk / 16
PARETO = [
    {"lr": 3e-5, "chunk": 16, "rank": 16, "sr": 0.79, "label": "Optimal"},
    {"lr": 2e-5, "chunk": 16, "rank": 16, "sr": 0.74, "label": "Budget-friendly"},
    {"lr": 3e-5, "chunk": 32, "rank": 16, "sr": 0.76, "label": "High-throughput"},
]

KEY_METRICS = {
    "v1_wall_clock_h": round(V1_TOTAL, 2),
    "v2_wall_clock_h": round(V2_TOTAL, 2),
    "efficiency_gain_pct": round((1 - V2_TOTAL / V1_TOTAL) * 100, 1),
    "best_sr": 0.79,
    "best_lr": "3e-5",
    "best_chunk": 16,
    "best_rank": 16,
    "hpo_runs": len(HPO_RUNS),
    "pareto_configs": len(PARETO),
}

# ---------------------------------------------------------------------------
# SVG: Pipeline Gantt (v1 vs v2)
# ---------------------------------------------------------------------------

def build_gantt_svg() -> str:
    width, height = 680, 320
    pad_l, pad_r, pad_t, pad_b = 100, 20, 40, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    max_h  = max(V1_TOTAL, V2_TOTAL) * 1.05

    n_stages = len(PIPELINE_STAGES)
    row_h = plot_h / (n_stages * 2 + 1)   # v1 + gap + v2 per stage + padding
    bar_h = row_h * 0.7

    V1_COLOR = "#C74634"
    V2_COLOR = "#38bdf8"

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="background:#0f172a;font-family:monospace">']

    lines.append(f'<text x="{width//2}" y="18" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">Pipeline Stage Timeline: v1 vs v2</text>')

    # Hour ticks
    for h in [x * 0.5 for x in range(int(max_h / 0.5) + 2)]:
        if h > max_h:
            break
        x = pad_l + int(h / max_h * plot_w)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t+plot_h}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{h:.1f}h</text>')

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<text x="{width//2}" y="{height-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Wall-Clock Time (hours)</text>')

    for i, stage in enumerate(PIPELINE_STAGES):
        base_y = pad_t + i * (bar_h * 2 + 6)

        # Row label
        lines.append(f'<text x="{pad_l-6}" y="{base_y + bar_h + 2}" fill="#94a3b8" '
                     f'font-size="10" text-anchor="end">{stage["name"]}</text>')

        # v1 bar
        x1 = pad_l + int(stage["v1_start"] / max_h * plot_w)
        w1 = max(3, int(stage["v1_dur"]  / max_h * plot_w))
        lines.append(f'<rect x="{x1}" y="{base_y}" width="{w1}" height="{bar_h-1}" '
                     f'fill="{V1_COLOR}" opacity="0.75" rx="3"/>')
        lines.append(f'<text x="{x1+w1//2}" y="{base_y+bar_h//2+4}" fill="#fff" '
                     f'font-size="9" text-anchor="middle">{stage["v1_dur"]:.1f}h</text>')

        # v2 bar
        x2 = pad_l + int(stage["v2_start"] / max_h * plot_w)
        w2 = max(3, int(stage["v2_dur"]  / max_h * plot_w))
        lines.append(f'<rect x="{x2}" y="{base_y+bar_h+2}" width="{w2}" height="{bar_h-1}" '
                     f'fill="{V2_COLOR}" opacity="0.85" rx="3"/>')
        lines.append(f'<text x="{x2+w2//2}" y="{base_y+bar_h*2+2}" fill="#0f172a" '
                     f'font-size="9" text-anchor="middle">{stage["v2_dur"]:.1f}h</text>')

    # v1 / v2 total lines
    for total, color, label in [(V1_TOTAL, V1_COLOR, f"v1: {V1_TOTAL:.1f}h"),
                                 (V2_TOTAL, V2_COLOR, f"v2: {V2_TOTAL:.1f}h")]:
        xf = pad_l + int(total / max_h * plot_w)
        lines.append(f'<line x1="{xf}" y1="{pad_t}" x2="{xf}" y2="{pad_t+plot_h}" '
                     f'stroke="{color}" stroke-width="2" stroke-dasharray="6,3"/>')
        lines.append(f'<text x="{xf+3}" y="{pad_t+12}" fill="{color}" font-size="10">{label}</text>')

    # Legend
    for li, (color, label) in enumerate([(V1_COLOR, "v1 (sequential)"), (V2_COLOR, "v2 (parallel eval+train)")]):
        lx = pad_l + li * 200
        ly = pad_t - 12
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="8" fill="{color}"/>')
        lines.append(f'<text x="{lx+16}" y="{ly+8}" fill="#cbd5e1" font-size="10">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG: HPO scatter
# ---------------------------------------------------------------------------

def build_hpo_scatter_svg() -> str:
    width, height = 620, 360
    pad_l, pad_r, pad_t, pad_b = 70, 30, 40, 55
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    lr_vals   = sorted({r["lr"]    for r in HPO_RUNS})
    sr_min, sr_max = 0.40, 0.92

    def x_for_lr(lr):
        idx = lr_vals.index(lr)
        return pad_l + int((idx + 0.5) / len(lr_vals) * plot_w)

    def y_for_sr(sr):
        return pad_t + plot_h - int((sr - sr_min) / (sr_max - sr_min) * plot_h)

    chunk_to_r = {8: 6, 16: 10, 32: 14}
    rank_to_color = {8: "#a78bfa", 16: "#38bdf8", 32: "#34d399"}

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="background:#0f172a;font-family:monospace">']

    lines.append(f'<text x="{width//2}" y="18" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">HPO Sweep: 25 Configurations</text>')

    # Grid
    for sr in [0.5, 0.6, 0.7, 0.8, 0.9]:
        y = y_for_sr(sr)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{pad_l+plot_w}" y2="{y}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+4}" fill="#64748b" font-size="10" text-anchor="end">{sr:.1f}</text>')

    for i, lr in enumerate(lr_vals):
        x = x_for_lr(lr)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t+plot_h}" stroke="#1e293b" stroke-width="1"/>')
        lbl = f"{lr:.0e}"
        lines.append(f'<text x="{x}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{lbl}</text>')

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<text x="{width//2}" y="{height-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Learning Rate</text>')
    lines.append(f'<text x="14" y="{pad_t+plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" '
                 f'transform="rotate(-90,14,{pad_t+plot_h//2})">Success Rate</text>')

    # Pareto frontier highlight
    pareto_pts = sorted(PARETO, key=lambda p: p["lr"])
    for pp in pareto_pts:
        px = x_for_lr(pp["lr"])
        py = y_for_sr(pp["sr"])
        lines.append(f'<circle cx="{px}" cy="{py}" r="18" fill="none" stroke="#fbbf24" stroke-width="1.5" opacity="0.5"/>')

    # All runs
    seen = set()
    for run in HPO_RUNS:
        is_optimal = (run["lr"] == 3e-5 and run["chunk"] == 16 and run["rank"] == 16)
        r     = chunk_to_r.get(run["chunk"], 8)
        color = "#C74634" if is_optimal else rank_to_color.get(run["rank"], "#64748b")
        x = x_for_lr(run["lr"]) + random.randint(-8, 8) if not is_optimal else x_for_lr(run["lr"])
        y = y_for_sr(run["sr"])
        opacity = "1.0" if is_optimal else "0.7"
        lines.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="{opacity}"/>')
        if is_optimal:
            lines.append(f'<text x="{x+r+3}" y="{y-4}" fill="#C74634" font-size="10" font-weight="bold">Optimal</text>')
            lines.append(f'<text x="{x+r+3}" y="{y+8}" fill="#94a3b8" font-size="9">SR={run["sr"]} lr=3e-5 ch=16 r=16</text>')

    # Legends
    # Chunk size legend
    leg_x, leg_y = pad_l + 10, pad_t + 8
    lines.append(f'<text x="{leg_x}" y="{leg_y}" fill="#94a3b8" font-size="10">Marker size = chunk_size:</text>')
    for i, (c, r) in enumerate([(8,6),(16,10),(32,14)]):
        lx = leg_x + i * 70
        lines.append(f'<circle cx="{lx+5}" cy="{leg_y+18}" r="{r}" fill="#475569"/>')
        lines.append(f'<text x="{lx+5+r+3}" y="{leg_y+22}" fill="#cbd5e1" font-size="9">ch={c}</text>')

    # LoRA rank legend
    leg_y2 = leg_y + 38
    lines.append(f'<text x="{leg_x}" y="{leg_y2}" fill="#94a3b8" font-size="10">Color = lora_rank:</text>')
    for i, (rank, color) in enumerate([(8,"#a78bfa"),(16,"#38bdf8"),(32,"#34d399")]):
        lx = leg_x + i * 80
        lines.append(f'<rect x="{lx}" y="{leg_y2+8}" width="12" height="12" fill="{color}"/>')
        lines.append(f'<text x="{lx+16}" y="{leg_y2+19}" fill="#cbd5e1" font-size="9">r={rank}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_dashboard_html() -> str:
    gantt_svg = build_gantt_svg()
    hpo_svg   = build_hpo_scatter_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    m  = KEY_METRICS

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Training Pipeline v2 — Port 8287</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 28px; }}
    .card {{
      background: #1e293b; border: 1px solid #334155; border-radius: 8px;
      padding: 16px 20px; min-width: 180px; flex: 1;
    }}
    .card .val {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
    .card .val.red {{ color: #C74634; }}
    .section {{ margin-bottom: 36px; }}
    .section h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    .svg-wrap {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; overflow-x: auto; }}
    .pareto-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .pareto-table th {{ background: #1e293b; color: #94a3b8; padding: 8px 12px; text-align: left; }}
    .pareto-table td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
    .pareto-table tr:hover td {{ background: #1e3a5f; }}
    .badge {{ display: inline-block; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }}
    .opt  {{ background: #C74634; color: #fff; }}
    .good {{ background: #38bdf8; color: #0f172a; }}
    .std  {{ background: #475569; color: #fff; }}
  </style>
</head>
<body>
  <h1>Training Pipeline v2</h1>
  <div class="sub">Automated HPO, parallel eval+checkpoint, 33% faster end-to-end training &mdash; Port 8287 &mdash; {ts}</div>

  <div class="metrics">
    <div class="card"><div class="val">{m['v2_wall_clock_h']}h</div><div class="lbl">v2 Wall-Clock Time</div></div>
    <div class="card"><div class="val red">{m['efficiency_gain_pct']}%</div><div class="lbl">Faster than v1 ({m['v1_wall_clock_h']}h)</div></div>
    <div class="card"><div class="val">{m['best_sr']}</div><div class="lbl">Best HPO Config SR</div></div>
    <div class="card"><div class="val">{m['best_lr']}</div><div class="lbl">Optimal Learning Rate</div></div>
    <div class="card"><div class="val">{m['best_chunk']}</div><div class="lbl">Optimal Chunk Size</div></div>
    <div class="card"><div class="val">{m['hpo_runs']}</div><div class="lbl">HPO Configs Evaluated</div></div>
  </div>

  <div class="section">
    <h2>Pipeline Stage Gantt: v1 vs v2</h2>
    <div class="svg-wrap">{gantt_svg}</div>
    <p style="color:#64748b;font-size:0.8rem;margin-top:8px">
      v2 runs <strong style="color:#38bdf8">eval in parallel</strong> with the tail of training,
      saving {m['efficiency_gain_pct']}% wall-clock
      ({m['v1_wall_clock_h']}h &rarr; {m['v2_wall_clock_h']}h).
    </p>
  </div>

  <div class="section">
    <h2>Automated HPO Sweep Results</h2>
    <div class="svg-wrap">{hpo_svg}</div>
    <p style="color:#64748b;font-size:0.8rem;margin-top:8px">
      Gold rings = Pareto-optimal configs within cost budget &nbsp;|&nbsp;
      <span style="color:#C74634">Oracle-red dot = optimal config</span>
      (lr={m['best_lr']}, chunk={m['best_chunk']}, rank={m['best_rank']}, SR={m['best_sr']}).
    </p>
  </div>

  <div class="section">
    <h2>Pareto-Optimal Configurations</h2>
    <table class="pareto-table">
      <thead><tr><th>Config</th><th>LR</th><th>Chunk</th><th>LoRA Rank</th><th>SR</th><th>Notes</th></tr></thead>
      <tbody>
        <tr>
          <td><strong style="color:#C74634">Optimal</strong></td>
          <td>3e-5</td><td>16</td><td>16</td><td>0.79</td>
          <td><span class="badge opt">Recommended</span></td>
        </tr>
        <tr>
          <td>Budget-friendly</td>
          <td>2e-5</td><td>16</td><td>16</td><td>0.74</td>
          <td><span class="badge good">$5 budget</span></td>
        </tr>
        <tr>
          <td>High-throughput</td>
          <td>3e-5</td><td>32</td><td>16</td><td>0.76</td>
          <td><span class="badge std">Larger batch</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app  (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Training Pipeline v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_dashboard_html())

    @app.get("/api/pipeline")
    async def pipeline_stages():
        return {"stages": PIPELINE_STAGES, "v1_total_h": V1_TOTAL, "v2_total_h": V2_TOTAL}

    @app.get("/api/hpo")
    async def hpo_results():
        return {"runs": HPO_RUNS, "pareto": PARETO}

    @app.get("/api/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "training_pipeline_v2", "port": 8287}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8287)
    else:
        PORT = 8287
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback — install fastapi+uvicorn for full API)")
            httpd.serve_forever()
