"""Training Efficiency Profiler — FastAPI service on port 8216.

Profiles training throughput bottlenecks for GR00T fine-tuning pipeline.
Shows time breakdown per phase and GPU utilization over training steps.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

PHASES = [
    {"name": "data_loading",    "pct": 12, "ms": 48.2},
    {"name": "forward_pass",    "pct": 41, "ms": 164.7},
    {"name": "backward_pass",   "pct": 38, "ms": 152.6},
    {"name": "optimizer_step",  "pct":  5, "ms":  20.1},
    {"name": "checkpoint_save", "pct":  2, "ms":   8.0},
    {"name": "eval",            "pct":  2, "ms":   8.0},
]

def _generate_step_metrics(n: int = 50):
    """Return lists of gpu_util and mem_bw over n steps."""
    gpu_util, mem_bw = [], []
    for i in range(n):
        noise = random.gauss(0, 2)
        gpu = max(60.0, min(99.0, 87.0 + noise + 3 * math.sin(i / 8)))
        bw  = max(200.0, min(900.0, 620.0 + random.gauss(0, 40) + 50 * math.sin(i / 10)))
        gpu_util.append(round(gpu, 1))
        mem_bw.append(round(bw, 1))
    return gpu_util, mem_bw


GPU_UTIL, MEM_BW = _generate_step_metrics()

EFFICIENCY_RATIO = round((100 - PHASES[0]["pct"]) / 100, 3)   # compute vs idle proxy
FLOPS_UTIL       = 78.4   # percent
REC_BATCH_SIZE   = 32
TOTAL_STEP_MS    = sum(p["ms"] for p in PHASES)

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    """Horizontal bar chart of time per training phase."""
    W, H = 700, 320
    margin_left, margin_top, bar_height, gap = 160, 30, 32, 10
    max_pct = max(p["pct"] for p in PHASES)
    avail_w = W - margin_left - 40

    bars = []
    phase_colors = ["#38bdf8", "#C74634", "#f97316", "#a3e635", "#e879f9", "#facc15"]
    for idx, phase in enumerate(PHASES):
        y = margin_top + idx * (bar_height + gap)
        bar_w = int(avail_w * phase["pct"] / max_pct)
        color = phase_colors[idx % len(phase_colors)]
        label = phase["name"].replace("_", " ")
        is_bottleneck = phase["pct"] >= 38
        bars.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_height}" '
            f'fill="{color}" rx="3" opacity="0.9"/>'
        )
        if is_bottleneck:
            bars.append(
                f'<text x="{margin_left + bar_w + 6}" y="{y + bar_height//2 + 5}" '
                f'fill="#fbbf24" font-size="11" font-family="monospace">'
                f'{phase["pct"]}% / {phase["ms"]}ms &#x26A0;</text>'
            )
        else:
            bars.append(
                f'<text x="{margin_left + bar_w + 6}" y="{y + bar_height//2 + 5}" '
                f'fill="#cbd5e1" font-size="11" font-family="monospace">'
                f'{phase["pct"]}% / {phase["ms"]}ms</text>'
            )
        bars.append(
            f'<text x="{margin_left - 6}" y="{y + bar_height//2 + 5}" '
            f'fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="end">'
            f'{label}</text>'
        )

    chart_h = margin_top + len(PHASES) * (bar_height + gap) + 20
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{chart_h}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#f1f5f9" '
        f'font-size="13" font-family="monospace" font-weight="bold">'
        f'Training Phase Breakdown (total {round(TOTAL_STEP_MS,1)}ms/step)</text>'
        + "".join(bars)
        + "</svg>"
    )
    return svg


def _line_chart_svg() -> str:
    """Dual-axis line chart: GPU util + mem bandwidth over 50 steps."""
    W, H = 700, 260
    ml, mr, mt, mb = 60, 80, 30, 40
    pw, ph = W - ml - mr, H - mt - mb
    n = len(GPU_UTIL)

    def sx(i):  return ml + int(i / (n - 1) * pw)
    def sy_gpu(v): return mt + int((1 - (v - 60) / 40) * ph)  # 60–100
    def sy_bw(v):  return mt + int((1 - (v - 200) / 700) * ph)  # 200–900

    gpu_pts = " ".join(f"{sx(i)},{sy_gpu(GPU_UTIL[i])}" for i in range(n))
    bw_pts  = " ".join(f"{sx(i)},{sy_bw(MEM_BW[i])}"  for i in range(n))

    # axis ticks
    yticks_left  = [60, 70, 80, 90, 100]
    yticks_right = [200, 400, 600, 800]
    xtick_labels = [0, 10, 20, 30, 40, 49]

    ticks = []
    for v in yticks_left:
        y = sy_gpu(v)
        ticks.append(f'<line x1="{ml}" y1="{y}" x2="{ml+pw}" y2="{y}" stroke="#334155" stroke-width="1"/>')
        ticks.append(f'<text x="{ml-6}" y="{y+4}" text-anchor="end" fill="#38bdf8" font-size="10" font-family="monospace">{v}%</text>')
    for v in yticks_right:
        y = sy_bw(v)
        ticks.append(f'<text x="{ml+pw+6}" y="{y+4}" fill="#f97316" font-size="10" font-family="monospace">{v}</text>')
    for i in xtick_labels:
        x = sx(i)
        ticks.append(f'<text x="{x}" y="{mt+ph+14}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{i}</text>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#f1f5f9" '
        f'font-size="13" font-family="monospace" font-weight="bold">'
        f'GPU Util (%) &amp; Mem Bandwidth (GB/s) — 50 Steps</text>'
        + "".join(ticks)
        + f'<polyline points="{gpu_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
        + f'<polyline points="{bw_pts}" fill="none" stroke="#f97316" stroke-width="2"/>'
        # legend
        + f'<rect x="{ml}" y="{mt+ph+22}" width="12" height="4" fill="#38bdf8"/>'
        + f'<text x="{ml+16}" y="{mt+ph+28}" fill="#38bdf8" font-size="10" font-family="monospace">GPU Util (%)</text>'
        + f'<rect x="{ml+120}" y="{mt+ph+22}" width="12" height="4" fill="#f97316"/>'
        + f'<text x="{ml+136}" y="{mt+ph+28}" fill="#f97316" font-size="10" font-family="monospace">Mem BW (GB/s)</text>'
        + "</svg>"
    )
    return svg

# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _html() -> str:
    bar_svg  = _bar_chart_svg()
    line_svg = _line_chart_svg()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Training Efficiency Profiler — Port 8216</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 20px; min-width: 170px; }}
    .card .val {{ font-size: 1.6rem; font-weight: bold; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
    .card.warn .val {{ color: #fbbf24; }}
    .section {{ margin-bottom: 28px; }}
    .section h2 {{ color: #C74634; font-size: 1rem; margin-bottom: 10px; }}
    .bottleneck {{ background: #1e293b; border-left: 3px solid #fbbf24; padding: 10px 14px;
                   border-radius: 4px; font-size: 0.82rem; color: #fbbf24; margin-top: 12px; }}
  </style>
</head>
<body>
  <h1>Training Efficiency Profiler</h1>
  <p class="subtitle">GR00T Fine-Tuning Pipeline · Port 8216</p>

  <div class="cards">
    <div class="card">
      <div class="val">{EFFICIENCY_RATIO}</div>
      <div class="lbl">Efficiency Ratio (compute/total)</div>
    </div>
    <div class="card">
      <div class="val">{FLOPS_UTIL}%</div>
      <div class="lbl">FLOPS Utilization</div>
    </div>
    <div class="card">
      <div class="val">{round(TOTAL_STEP_MS,1)}ms</div>
      <div class="lbl">Total Step Latency</div>
    </div>
    <div class="card warn">
      <div class="val">batch={REC_BATCH_SIZE}</div>
      <div class="lbl">Recommended Batch Size</div>
    </div>
    <div class="card">
      <div class="val">{round(sum(GPU_UTIL)/len(GPU_UTIL),1)}%</div>
      <div class="lbl">Avg GPU Utilization</div>
    </div>
  </div>

  <div class="section">
    <h2>Phase Breakdown</h2>
    {bar_svg}
    <div class="bottleneck">&#x26A0; Bottleneck detected: forward_pass (41%) + backward_pass (38%) account for 79% of step time.
    Consider gradient checkpointing or mixed-precision to reduce backward_pass overhead.</div>
  </div>

  <div class="section">
    <h2>GPU Utilization &amp; Memory Bandwidth</h2>
    {line_svg}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Training Efficiency Profiler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html())

    @app.get("/api/phases")
    def api_phases():
        return {"phases": PHASES, "total_ms": round(TOTAL_STEP_MS, 2)}

    @app.get("/api/metrics")
    def api_metrics():
        return {
            "efficiency_ratio": EFFICIENCY_RATIO,
            "flops_util_pct": FLOPS_UTIL,
            "recommended_batch_size": REC_BATCH_SIZE,
            "avg_gpu_util_pct": round(sum(GPU_UTIL) / len(GPU_UTIL), 2),
            "avg_mem_bw_gbs": round(sum(MEM_BW) / len(MEM_BW), 2),
        }

    @app.get("/api/step_metrics")
    def api_step_metrics():
        return {"gpu_util": GPU_UTIL, "mem_bw_gbs": MEM_BW}

else:
    # Fallback: stdlib HTTP server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8216)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8216")
        HTTPServer(("0.0.0.0", 8216), _Handler).serve_forever()
