"""Serving Optimizer v2 — FastAPI service on port 8263.

Enhanced model serving optimization with TensorRT compilation,
FP8/FP16 quantization, and multi-GPU load balancing for GR00T policies.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

OPTIM_STEPS = [
    {"id": "fp32_baseline",    "label": "FP32 Baseline",      "latency_ms": 412, "throughput_rps": 2.4,  "gpu_mem_gb": 14.2, "color": "#94a3b8"},
    {"id": "fp16",             "label": "FP16",               "latency_ms": 288, "throughput_rps": 3.5,  "gpu_mem_gb": 7.1,  "color": "#38bdf8"},
    {"id": "trt_fp16",         "label": "TensorRT FP16",      "latency_ms": 198, "throughput_rps": 5.1,  "gpu_mem_gb": 6.8,  "color": "#22c55e"},
    {"id": "fp8",              "label": "FP8",                "latency_ms": 141, "throughput_rps": 7.1,  "gpu_mem_gb": 3.9,  "color": "#a78bfa"},
    {"id": "trt_fp8_batching", "label": "TRT FP8 + Batching", "latency_ms": 109, "throughput_rps": 9.2,  "gpu_mem_gb": 3.6,  "color": "#C74634"},
]

# Multi-GPU load data: 4 GPUs × 24h (hourly buckets)
GPU_NODES = ["GPU-A100-1", "GPU-A100-2", "GPU-A100-3", "GPU-A100-4"]
HOURS = list(range(24))
random.seed(42)

def _gpu_load(node_idx: int, hour: int) -> float:
    """Simulate load with GPU4 (idx=3) overloaded during peak hours."""
    base = 0.45 + 0.15 * math.sin((hour - 10) * math.pi / 12)
    if node_idx == 3 and 9 <= hour <= 17:  # GPU4 peak overload
        base = min(0.95, base + 0.35)
    elif node_idx == 3 and 18 <= hour <= 20:  # post-rebalance
        base = max(0.60, base - 0.10)
    noise = (random.random() - 0.5) * 0.08
    return round(min(0.98, max(0.05, base + noise)), 3)

GPU_HEATMAP = [[_gpu_load(gi, h) for h in HOURS] for gi in range(4)]

# Rebalancing events
REBALANCE_EVENTS = [
    {"hour": 10, "from_node": "GPU-A100-4", "to_node": "GPU-A100-5", "traffic_pct": 23, "trigger": "utilization>90%"},
    {"hour": 15, "from_node": "GPU-A100-4", "to_node": "GPU-A100-2", "traffic_pct": 15, "trigger": "utilization>88%"},
    {"hour": 19, "from_node": "GPU-A100-4", "to_node": "GPU-A100-1", "traffic_pct": 10, "trigger": "scheduled"},
]

METRICS = {
    "model": "groot_v2",
    "optimal_config": "TRT FP8 + Batching",
    "baseline_latency_ms": 412,
    "optimal_latency_ms": 109,
    "end_to_end_speedup": round(412 / 109, 2),
    "fp16_reduction_pct": 30,
    "trt_fp8_reduction_pct": 74,
    "gpu4_peak_utilization_pct": 92,
    "target_utilization_pct": 75,
    "rebalance_traffic_moved_pct": 23,
    "sla_target_ms": 150,
    "sla_headroom_ms": 41,
    "load_imbalance_coefficient": 0.31,
    "nodes": 4,
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def build_waterfall_svg() -> str:
    """Speedup waterfall chart: baseline → ... → TRT FP8 + Batching."""
    W, H = 860, 340
    LEFT = 60
    BOTTOM = H - 60
    CHART_H = BOTTOM - 50
    CHART_W = W - LEFT - 30
    MAX_LAT = 450
    n = len(OPTIM_STEPS)
    bar_w = int(CHART_W / (n + 0.5))
    bar_gap = int(bar_w * 0.18)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    # Title
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#94a3b8" font-size="13" font-family="monospace">'
                 'Optimization Speedup Waterfall (ms latency)</text>')
    # Y-axis grid
    for tick in [0, 100, 200, 300, 400]:
        gy = BOTTOM - int(tick / MAX_LAT * CHART_H)
        lines.append(f'<line x1="{LEFT}" y1="{gy}" x2="{W-30}" y2="{gy}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{LEFT-6}" y="{gy+4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{tick}</text>')
    # SLA line
    sla_y = BOTTOM - int(150 / MAX_LAT * CHART_H)
    lines.append(f'<line x1="{LEFT}" y1="{sla_y}" x2="{W-30}" y2="{sla_y}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,4"/>')
    lines.append(f'<text x="{W-28}" y="{sla_y-3}" fill="#f59e0b" font-size="9" font-family="monospace">SLA 150ms</text>')
    # Bars
    prev_y = None
    for i, step in enumerate(OPTIM_STEPS):
        bx = LEFT + i * bar_w + bar_gap
        bh = int(step["latency_ms"] / MAX_LAT * CHART_H)
        by = BOTTOM - bh
        col = step["color"]
        lines.append(f'<rect x="{bx}" y="{by}" width="{bar_w - 2*bar_gap}" height="{bh}" rx="3" fill="{col}44" stroke="{col}" stroke-width="1.5"/>')
        # Latency label on top
        lines.append(f'<text x="{bx + (bar_w-2*bar_gap)//2}" y="{by-6}" text-anchor="middle" fill="{col}" font-size="11" font-family="monospace" font-weight="bold">{step["latency_ms"]}ms</text>')
        # Reduction arrow between consecutive bars
        if prev_y is not None:
            prev_x = LEFT + (i-1) * bar_w + bar_gap + (bar_w-2*bar_gap)//2
            curr_x = bx + (bar_w-2*bar_gap)//2
            mid_x = (prev_x + curr_x) // 2
            prev_lat = OPTIM_STEPS[i-1]["latency_ms"]
            delta_pct = int((1 - step["latency_ms"] / prev_lat) * 100)
            arr_y = min(prev_y, by) - 20
            lines.append(f'<text x="{mid_x}" y="{arr_y}" text-anchor="middle" fill="#22c55e" font-size="9" font-family="monospace">-{delta_pct}%</text>')
        prev_y = by
        # X label
        lines.append(f'<text x="{bx + (bar_w-2*bar_gap)//2}" y="{BOTTOM+14}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{step["label"]}</text>')
        # Throughput sub-label
        lines.append(f'<text x="{bx + (bar_w-2*bar_gap)//2}" y="{BOTTOM+26}" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">{step["throughput_rps"]} rps</text>')
    # Baseline label
    lines.append(f'<text x="{LEFT}" y="{BOTTOM+40}" fill="#64748b" font-size="9" font-family="monospace">Mem: {" → ".join(str(s["gpu_mem_gb"])+"GB" for s in OPTIM_STEPS)}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def build_heatmap_svg() -> str:
    """Multi-GPU load distribution heatmap: 4 nodes × 24h."""
    W, H = 860, 250
    LEFT = 110
    TOP = 40
    BOTTOM = H - 40
    CHART_H = BOTTOM - TOP
    CHART_W = W - LEFT - 20
    cell_w = CHART_W // 24
    cell_h = CHART_H // 4

    def load_color(val: float) -> str:
        """Blue (low) → green (mid) → red (high)."""
        if val < 0.5:
            t = val / 0.5
            r = int(56 * t)
            g = int(189 * t)
            b = int(248 * (1 - t) + 248 * t)
            return f"#{r:02x}{g:02x}{int(248*(1-t)+130*t):02x}"
        elif val < 0.75:
            t = (val - 0.5) / 0.25
            return f"#{int(56+180*t):02x}{int(189-100*t):02x}{int(130-100*t):02x}"
        else:
            t = min(1.0, (val - 0.75) / 0.25)
            return f"#{int(236):02x}{int(89-50*t):02x}{int(30):02x}"

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#94a3b8" font-size="13" font-family="monospace">'
                 'Multi-GPU Load Heatmap (4 nodes × 24h) — target 75%</text>')
    # Cells
    for gi, gpu in enumerate(GPU_NODES):
        row_y = TOP + gi * cell_h
        # GPU label
        lines.append(f'<text x="{LEFT-6}" y="{row_y + cell_h//2 + 4}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{gpu}</text>')
        for h in HOURS:
            val = GPU_HEATMAP[gi][h]
            cx = LEFT + h * cell_w
            col = load_color(val)
            lines.append(f'<rect x="{cx+1}" y="{row_y+1}" width="{cell_w-2}" height="{cell_h-2}" rx="1" fill="{col}" opacity="0.85"/>')
            # Show % if cell is big enough
            if cell_w >= 30:
                lines.append(f'<text x="{cx + cell_w//2}" y="{row_y + cell_h//2 + 4}" text-anchor="middle" fill="#000000" font-size="8" font-family="monospace">{int(val*100)}</text>')
    # Hour labels
    for h in range(0, 24, 3):
        hx = LEFT + h * cell_w + cell_w // 2
        lines.append(f'<text x="{hx}" y="{BOTTOM+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{h:02d}h</text>')
    # Rebalance event markers
    for ev in REBALANCE_EVENTS:
        ex = LEFT + ev["hour"] * cell_w + cell_w // 2
        lines.append(f'<line x1="{ex}" y1="{TOP}" x2="{ex}" y2="{BOTTOM}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.7"/>')
        lines.append(f'<text x="{ex}" y="{TOP-6}" text-anchor="middle" fill="#f59e0b" font-size="8" font-family="monospace">↕{ev["traffic_pct"]}%</text>')
    # Legend
    legend_x = LEFT
    legend_y = BOTTOM + 24
    for pct, col_val in [("0%", 0.0), ("25%", 0.25), ("50%", 0.50), ("75%", 0.75), ("100%", 1.0)]:
        lx = legend_x + int(col_val * 200)
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="14" height="10" fill="{load_color(col_val)}"/>')
        lines.append(f'<text x="{lx+16}" y="{legend_y+9}" fill="#64748b" font-size="8" font-family="monospace">{pct}</text>')
    lines.append(f'<text x="{legend_x+240}" y="{legend_y+9}" fill="#f59e0b" font-size="8" font-family="monospace">| rebalance event</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    waterfall = build_waterfall_svg()
    heatmap = build_heatmap_svg()
    m = METRICS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Serving Optimizer v2 — Port 8263</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',monospace,sans-serif;padding:20px}}
  h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:12px;margin-bottom:24px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px}}
  .card .val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
  .card .val.green{{color:#22c55e}}
  .card .val.red{{color:#C74634}}
  .card .val.amber{{color:#f59e0b}}
  .section{{margin-bottom:28px}}
  .section h2{{font-size:1rem;color:#94a3b8;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}}
  svg{{max-width:100%;height:auto}}
  table{{width:100%;border-collapse:collapse;font-size:.8rem}}
  th{{background:#1e293b;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  td{{padding:7px 10px;border-bottom:1px solid #1e293b}}
  tr:hover td{{background:#1e293b}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.7rem;font-weight:600;background:#22c55e22;color:#22c55e;border:1px solid #22c55e}}
  footer{{color:#334155;font-size:.75rem;margin-top:30px;text-align:center}}
</style>
</head>
<body>
<h1>Serving Optimizer v2</h1>
<p class="sub">Port 8263 &nbsp;|&nbsp; Model: {m['model']} &nbsp;|&nbsp; Optimal: <span style="color:#22c55e">{m['optimal_config']}</span></p>

<div class="cards">
  <div class="card"><div class="val green">{m['end_to_end_speedup']}x</div><div class="lbl">End-to-End Speedup</div></div>
  <div class="card"><div class="val">{m['optimal_latency_ms']}ms</div><div class="lbl">Optimal Latency</div></div>
  <div class="card"><div class="val red">{m['baseline_latency_ms']}ms</div><div class="lbl">FP32 Baseline</div></div>
  <div class="card"><div class="val amber">{m['trt_fp8_reduction_pct']}%</div><div class="lbl">TRT FP8 Reduction</div></div>
  <div class="card"><div class="val">{m['sla_headroom_ms']}ms</div><div class="lbl">SLA Headroom</div></div>
  <div class="card"><div class="val red">{m['gpu4_peak_utilization_pct']}%</div><div class="lbl">GPU4 Peak Util</div></div>
  <div class="card"><div class="val">{m['target_utilization_pct']}%</div><div class="lbl">Target Utilization</div></div>
  <div class="card"><div class="val amber">{m['load_imbalance_coefficient']}</div><div class="lbl">Imbalance Coefficient</div></div>
</div>

<div class="section">
  <h2>Quantization Speedup Waterfall</h2>
  {waterfall}
</div>

<div class="section">
  <h2>Multi-GPU Load Heatmap</h2>
  {heatmap}
</div>

<div class="section">
  <h2>Optimization Steps</h2>
  <table>
    <tr><th>Config</th><th>Latency (ms)</th><th>Throughput (rps)</th><th>GPU Mem (GB)</th><th>vs Baseline</th></tr>
    {''.join(f"<tr><td style='color:{s[\"color\"]}'>{s['label']}</td><td><b>{s['latency_ms']}</b></td><td>{s['throughput_rps']}</td><td>{s['gpu_mem_gb']}</td><td style='color:#22c55e'>-{int((1-s['latency_ms']/412)*100)}%</td></tr>" for s in OPTIM_STEPS)}
  </table>
</div>

<div class="section">
  <h2>Rebalancing Events</h2>
  <table>
    <tr><th>Hour</th><th>From</th><th>To</th><th>Traffic Moved</th><th>Trigger</th></tr>
    {''.join(f"<tr><td>{ev['hour']}:00</td><td style='color:#C74634'>{ev['from_node']}</td><td style='color:#22c55e'>{ev['to_node']}</td><td>{ev['traffic_pct']}%</td><td style='color:#f59e0b'>{ev['trigger']}</td></tr>" for ev in REBALANCE_EVENTS)}
  </table>
</div>

<footer>OCI Robot Cloud &mdash; Serving Optimizer v2 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Serving Optimizer v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "serving_optimizer_v2", "port": 8263}

    @app.get("/metrics")
    async def metrics():
        return METRICS

    @app.get("/optim_steps")
    async def optim_steps():
        return OPTIM_STEPS

    @app.get("/gpu_heatmap")
    async def gpu_heatmap():
        return {"nodes": GPU_NODES, "hours": HOURS, "data": GPU_HEATMAP}

    @app.get("/rebalance_events")
    async def rebalance_events():
        return REBALANCE_EVENTS

    @app.get("/waterfall")
    async def waterfall_svg():
        from fastapi.responses import Response
        return Response(content=build_waterfall_svg(), media_type="image/svg+xml")

    @app.get("/heatmap")
    async def heatmap_svg():
        from fastapi.responses import Response
        return Response(content=build_heatmap_svg(), media_type="image/svg+xml")

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8263)
    else:
        PORT = 8263
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback)")
            httpd.serve_forever()
