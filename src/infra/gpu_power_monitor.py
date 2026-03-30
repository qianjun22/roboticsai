"""
gpu_power_monitor.py — OCI Robot Cloud
Port 8683 | GPU power consumption monitoring, SR-per-watt efficiency, cost breakdown.
Dark theme FastAPI. stdlib only.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_power_timeline() -> str:
    """4 GPU power lines over 24 hours; training peaks 380W, inference 200W, idle 140W."""
    import math

    w, h = 640, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 40, 50
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    hours = 24
    y_min, y_max = 100, 420

    gpu_colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634"]
    gpu_labels = ["GPU-0", "GPU-1", "GPU-2", "GPU-3 (training)"]

    # Power profiles: (hour, watts) key events
    # GPU-3 trains 06:00–14:00 (380W peak), GPU-0/1/2 inference 08:00–18:00 (200W), idle otherwise
    def gpu_power(gpu_idx: int, hour: float) -> float:
        noise = math.sin(hour * 2.7 + gpu_idx * 1.3) * 5
        if gpu_idx == 3:  # training GPU
            if 6 <= hour < 14:
                ramp = min(1.0, (hour - 6) / 0.5)
                decay = min(1.0, (14 - hour) / 0.5)
                base = 340 + 40 * min(ramp, decay)
                return base + noise
            elif 14 <= hour < 18:
                return 200 + noise * 0.5
            else:
                return 140 + noise * 0.3
        else:  # inference GPUs
            if 8 <= hour < 18:
                phase_offset = gpu_idx * 0.8
                burst = 20 * max(0, math.sin((hour - 8) * math.pi / 10 + phase_offset))
                return 200 + burst + noise
            else:
                return 140 + noise * 0.3

    def to_xy(hour, watts):
        x = pad_l + hour / hours * chart_w
        y = pad_t + (1 - (watts - y_min) / (y_max - y_min)) * chart_h
        return x, y

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{w//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" '
        f'text-anchor="middle">GPU Power Consumption — 24-Hour Timeline</text>',
        # Axes
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # Y gridlines
    for w_tick in [140, 200, 300, 380]:
        _, yy = to_xy(0, w_tick)
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+chart_w}" y2="{yy:.1f}" '
                     f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>')
        lbl = {140: "idle 140W", 200: "infer 200W", 300: "300W", 380: "peak 380W"}.get(w_tick, f"{w_tick}W")
        lines.append(f'<text x="{pad_l-4}" y="{yy+4:.1f}" fill="#64748b" font-size="7.5" text-anchor="end">{lbl}</text>')

    # X axis labels
    for hh in range(0, 25, 4):
        x, _ = to_xy(hh, y_min)
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+chart_h}" '
                     f'stroke="#1e293b" stroke-width="1" stroke-dasharray="2,4"/>')
        lines.append(f'<text x="{x:.1f}" y="{pad_t+chart_h+14}" fill="#64748b" font-size="8" '
                     f'text-anchor="middle">{hh:02d}:00</text>')

    # GPU lines
    step = 0.25
    for gi in range(4):
        pts = []
        t = 0.0
        while t <= 24:
            x, y = to_xy(t, gpu_power(gi, t))
            pts.append(f"{x:.1f},{y:.1f}")
            t += step
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{gpu_colors[gi]}" '
                     f'stroke-width="1.8" opacity="0.9"/>')

    # Annotations
    _, peak_y = to_xy(0, 380)
    peak_x, _ = to_xy(10, 0)
    lines.append(f'<text x="{peak_x:.1f}" y="{peak_y-6:.1f}" fill="#fca5a5" font-size="8" '
                 f'text-anchor="middle">▲ 380W training peak</text>')

    # Legend
    for gi in range(4):
        lx = pad_l + gi * 145
        ly = h - 12
        lines.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+16}" y2="{ly}" stroke="{gpu_colors[gi]}" stroke-width="2"/>')
        lines.append(f'<text x="{lx+20}" y="{ly+4}" fill="#94a3b8" font-size="8">{gpu_labels[gi]}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_sr_per_watt() -> str:
    """SR-per-watt efficiency trend over 10 runs; FP16 jump marker; FP8 target line."""
    runs = list(range(1, 11))
    sr_per_watt = [0.0021, 0.0025, 0.0028, 0.0031, 0.0034,
                   0.0042, 0.0046, 0.0049, 0.0052, 0.0055]  # jump at run 6 (FP16)
    fp8_target = 0.0065

    w, h = 480, 280
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    y_min, y_max = 0.0015, 0.0070
    n = len(runs)

    def to_xy(run_idx, val):
        x = pad_l + run_idx / (n - 1) * chart_w
        y = pad_t + (1 - (val - y_min) / (y_max - y_min)) * chart_h
        return x, y

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{w//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" '
        f'text-anchor="middle">SR-per-Watt Efficiency Trend</text>',
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # FP8 target line
    _, fp8_y = to_xy(0, fp8_target)
    lines.append(f'<line x1="{pad_l}" y1="{fp8_y:.1f}" x2="{pad_l+chart_w}" y2="{fp8_y:.1f}" '
                 f'stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>')
    lines.append(f'<text x="{pad_l+chart_w-2}" y="{fp8_y-4:.1f}" fill="#a78bfa" font-size="8" '
                 f'text-anchor="end">FP8 target</text>')

    # Y gridlines
    for tick in [0.002, 0.003, 0.004, 0.005, 0.006]:
        _, yy = to_xy(0, tick)
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+chart_w}" y2="{yy:.1f}" '
                     f'stroke="#1e293b" stroke-width="1" stroke-dasharray="3,4"/>')
        lines.append(f'<text x="{pad_l-4}" y="{yy+4:.1f}" fill="#64748b" font-size="7.5" '
                     f'text-anchor="end">{tick:.4f}</text>')

    # Line
    pts = [f"{to_xy(i, v)[0]:.1f},{to_xy(i, v)[1]:.1f}" for i, v in enumerate(sr_per_watt)]
    lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#22c55e" stroke-width="2"/>')

    # Dots + labels
    for i, v in enumerate(sr_per_watt):
        x, y = to_xy(i, v)
        color = "#f59e0b" if i == 5 else "#22c55e"
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        lines.append(f'<text x="{x:.1f}" y="{pad_t+chart_h+14}" fill="#64748b" font-size="8" '
                     f'text-anchor="middle">R{runs[i]}</text>')

    # FP16 jump annotation
    fp16_x, fp16_y = to_xy(5, sr_per_watt[5])
    lines.append(f'<text x="{fp16_x:.1f}" y="{fp16_y-8:.1f}" fill="#f59e0b" font-size="8" '
                 f'text-anchor="middle">▲ FP16 −22% power</text>')

    # Y axis label
    lines.append(f'<text x="12" y="{pad_t+chart_h//2}" fill="#64748b" font-size="8" '
                 f'text-anchor="middle" transform="rotate(-90,12,{pad_t+chart_h//2})">SR / Watt</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_power_cost() -> str:
    """Monthly power cost breakdown: training vs inference hours × power × rate."""
    months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    # Training cost ($) and inference cost ($) per month
    train_cost = [58, 63, 71, 76, 80, 84]
    infer_cost  = [22, 25, 27, 28, 30, 32]

    w, h = 500, 280
    pad_l, pad_r, pad_t, pad_b = 55, 20, 40, 50
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n = len(months)
    group_w = chart_w / n
    bar_w = group_w * 0.35
    y_max = 120

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{w//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Monthly Power Cost — Training vs Inference</text>',
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
    ]

    for tick in [20, 40, 60, 80, 100]:
        yy = pad_t + (1 - tick / y_max) * chart_h
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+chart_w}" y2="{yy:.1f}" '
                     f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{pad_l-4}" y="{yy+4:.1f}" fill="#64748b" font-size="7.5" text-anchor="end">${tick}</text>')

    for i, month in enumerate(months):
        gx = pad_l + i * group_w + group_w * 0.1
        # Training bar
        th = train_cost[i] / y_max * chart_h
        ty = pad_t + chart_h - th
        lines.append(f'<rect x="{gx:.1f}" y="{ty:.1f}" width="{bar_w:.1f}" height="{th:.1f}" '
                     f'fill="#C74634" rx="2" opacity="0.85"/>')
        lines.append(f'<text x="{gx+bar_w/2:.1f}" y="{ty-3:.1f}" fill="#fca5a5" font-size="7.5" '
                     f'text-anchor="middle">${train_cost[i]}</text>')
        # Inference bar
        ih = infer_cost[i] / y_max * chart_h
        iy = pad_t + chart_h - ih
        dx = gx + bar_w + 3
        lines.append(f'<rect x="{dx:.1f}" y="{iy:.1f}" width="{bar_w:.1f}" height="{ih:.1f}" '
                     f'fill="#38bdf8" rx="2" opacity="0.85"/>')
        lines.append(f'<text x="{dx+bar_w/2:.1f}" y="{iy-3:.1f}" fill="#7dd3fc" font-size="7.5" '
                     f'text-anchor="middle">${infer_cost[i]}</text>')
        # X label
        lx = gx + bar_w
        lines.append(f'<text x="{lx:.1f}" y="{pad_t+chart_h+14}" fill="#94a3b8" font-size="9" '
                     f'text-anchor="middle">{month}</text>')

    # Annotations
    lines += [
        f'<text x="{w//2}" y="{h-8}" fill="#64748b" font-size="8" text-anchor="middle">'
        f'Training: $0.021/hr · Inference: $0.008/hr · Mar total: ~$116</text>',
    ]

    # Legend
    lines += [
        f'<rect x="{pad_l}" y="{h-22}" width="10" height="8" fill="#C74634" rx="1"/>',
        f'<text x="{pad_l+13}" y="{h-15}" fill="#94a3b8" font-size="8">Training ($0.021/hr)</text>',
        f'<rect x="{pad_l+120}" y="{h-22}" width="10" height="8" fill="#38bdf8" rx="1"/>',
        f'<text x="{pad_l+133}" y="{h-15}" fill="#94a3b8" font-size="8">Inference ($0.008/hr)</text>',
    ]
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>GPU Power Monitor — Port 8683</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:1.5rem;margin-bottom:4px}}
    .sub{{color:#38bdf8;font-size:.85rem;margin-bottom:24px}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}}
    .card{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:10px;padding:20px}}
    .card h2{{color:#38bdf8;font-size:.95rem;margin-bottom:14px}}
    .card-wide{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:10px;padding:20px;margin-bottom:24px}}
    .card-wide h2{{color:#38bdf8;font-size:.95rem;margin-bottom:14px}}
    .metrics{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px}}
    .metric{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:8px;padding:14px 20px;min-width:155px}}
    .metric .val{{font-size:1.8rem;font-weight:bold;color:#C74634}}
    .metric .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
    .metric .sub2{{font-size:.7rem;color:#38bdf8}}
    svg{{max-width:100%;height:auto;display:block}}
    .badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;
             padding:2px 8px;font-size:.7rem;margin-left:8px;vertical-align:middle}}
    footer{{color:#334155;font-size:.7rem;margin-top:30px;text-align:center}}
  </style>
</head>
<body>
  <h1>GPU Power Monitor <span class="badge">PORT 8683</span></h1>
  <div class="sub">OCI Robot Cloud — GPU power consumption, efficiency, and cost analytics</div>

  <div class="metrics">
    <div class="metric">
      <div class="val">380W</div>
      <div class="lbl">GPU-3 training peak</div>
      <div class="sub2">A100 80GB during fine-tune</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#38bdf8">140W</div>
      <div class="lbl">Idle power per GPU</div>
      <div class="sub2">all 4 GPUs baseline</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#22c55e">−22%</div>
      <div class="lbl">FP16 power reduction</div>
      <div class="sub2">FP8 adds further −18%</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#f59e0b">~$84</div>
      <div class="lbl">Monthly power cost</div>
      <div class="sub2">training + inference combined</div>
    </div>
  </div>

  <div class="card-wide">
    <h2>Power Consumption Timeline — 4 GPUs over 24 Hours</h2>
    {svg_power_timeline()}
  </div>

  <div class="grid">
    <div class="card">
      <h2>SR-per-Watt Efficiency Trend (10 Runs)</h2>
      {svg_sr_per_watt()}
    </div>
    <div class="card">
      <h2>Monthly Power Cost Breakdown</h2>
      {svg_power_cost()}
    </div>
  </div>

  <footer>OCI Robot Cloud · gpu_power_monitor.py · port 8683 · stdlib only</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app / fallback HTTP server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="GPU Power Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gpu_power_monitor", "port": 8683}

    @app.get("/metrics")
    async def metrics():
        return {
            "gpu3_training_peak_watts": 380,
            "idle_watts_per_gpu": 140,
            "inference_baseline_watts": 200,
            "fp16_power_reduction_pct": 22,
            "fp8_additional_reduction_pct": 18,
            "monthly_training_cost_usd": 84,
            "cost_per_hr_training": 0.021,
            "cost_per_hr_inference": 0.008,
            "gpus_monitored": 4,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8683)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"gpu_power_monitor","port":8683}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI not found — using stdlib HTTPServer on port 8683")
        HTTPServer(("0.0.0.0", 8683), Handler).serve_forever()
