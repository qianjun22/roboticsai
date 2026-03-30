"""FP8 Training Optimizer — FastAPI port 8750"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8750

def build_html():
    random.seed(42)
    # Simulate FP8 vs BF16 loss curves over 200 steps
    steps = list(range(0, 201, 10))
    fp8_loss   = [2.8 * math.exp(-i / 80) + 0.12 + random.gauss(0, 0.015) for i in steps]
    bf16_loss  = [2.8 * math.exp(-i / 95) + 0.14 + random.gauss(0, 0.012) for i in steps]

    # SVG loss curve (800x260)
    svg_w, svg_h = 760, 240
    def norm_x(s): return int(40 + (s / 200) * (svg_w - 60))
    def norm_y(v, lo=0.08, hi=2.9): return int(svg_h - 30 - ((v - lo) / (hi - lo)) * (svg_h - 50))

    fp8_pts  = " ".join(f"{norm_x(s)},{norm_y(v)}" for s, v in zip(steps, fp8_loss))
    bf16_pts = " ".join(f"{norm_x(s)},{norm_y(v)}" for s, v in zip(steps, bf16_loss))

    # Throughput bar chart (tokens/sec per precision)
    precisions  = ["FP32", "BF16", "FP8-E4M3", "FP8-E5M2"]
    throughputs = [18400, 34700, 61200, 58900]
    bar_svg_w, bar_svg_h = 520, 200
    max_t = max(throughputs)
    bars = ""
    for idx, (p, t) in enumerate(zip(precisions, throughputs)):
        bx = 60 + idx * 110
        bh = int((t / max_t) * (bar_svg_h - 50))
        by = bar_svg_h - 30 - bh
        color = "#C74634" if "FP8" in p else "#38bdf8"
        bars += f'<rect x="{bx}" y="{by}" width="80" height="{bh}" fill="{color}" rx="4"/>'
        bars += f'<text x="{bx+40}" y="{by-6}" fill="#e2e8f0" font-size="11" text-anchor="middle">{t//1000}k</text>'
        bars += f'<text x="{bx+40}" y="{bar_svg_h-10}" fill="#94a3b8" font-size="10" text-anchor="middle">{p}</text>'

    # Memory usage table rows
    mem_rows = ""
    mem_data = [
        ("FP8-E4M3", "7.1 GB", "4.6 GB", "61,200", "0.0043"),
        ("FP8-E5M2", "7.3 GB", "4.9 GB", "58,900", "0.0044"),
        ("BF16",     "14.2 GB", "9.1 GB", "34,700", "0.0074"),
        ("FP32",     "28.4 GB", "18.0 GB", "18,400", "0.0140"),
    ]
    for row in mem_data:
        mem_rows += "<tr>" + "".join(f"<td style='padding:8px 14px;border-bottom:1px solid #334155'>{c}</td>" for c in row) + "</tr>"

    # Gradient norm sparkline (50 points)
    gnorm = [1.2 * math.exp(-i / 30) + 0.05 + abs(random.gauss(0, 0.04)) for i in range(50)]
    sp_w, sp_h = 320, 60
    def spx(i): return int(10 + i * (sp_w - 20) / 49)
    def spy(v, lo=0.04, hi=1.25): return int(sp_h - 8 - ((v - lo) / (hi - lo)) * (sp_h - 16))
    sp_pts = " ".join(f"{spx(i)},{spy(v)}" for i, v in enumerate(gnorm))

    current_step = random.randint(145, 185)
    current_loss = round(fp8_loss[current_step // 10], 4)
    gpu_util     = random.randint(87, 96)
    mem_alloc    = round(random.uniform(6.8, 7.3), 1)

    return f"""<!DOCTYPE html>
<html><head><title>FP8 Training Optimizer — Port 8750</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;display:inline-block;vertical-align:top}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;margin:2px}}
.green{{background:#064e3b;color:#34d399}}.orange{{background:#431407;color:#fb923c}}
table{{border-collapse:collapse;width:100%}}th{{color:#94a3b8;padding:8px 14px;text-align:left;border-bottom:2px solid #334155}}
.stat{{font-size:2rem;font-weight:700;color:#C74634}}.sublabel{{color:#64748b;font-size:0.8rem}}
</style></head>
<body>
<h1>FP8 Training Optimizer</h1>
<p style="color:#64748b;margin:0 0 4px 24px">Mixed-precision FP8/BF16 training scheduler — OCI A100 cluster &bull; Port {PORT}</p>

<div style="padding:4px 12px">
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">Current Step</div><div class="stat">{current_step}</div>
  </div>
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">FP8 Loss</div><div class="stat">{current_loss}</div>
  </div>
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">GPU Util</div><div class="stat">{gpu_util}%</div>
  </div>
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">VRAM (GB)</div><div class="stat">{mem_alloc}</div>
  </div>
</div>

<div class="card" style="margin:12px">
  <h2>Training Loss — FP8-E4M3 vs BF16 (200 steps)</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    <!-- Grid lines -->
    {''.join(f'<line x1="40" y1="{norm_y(v)}" x2="{svg_w-20}" y2="{norm_y(v)}" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>' for v in [0.5,1.0,1.5,2.0,2.5])}
    <!-- Axes -->
    <line x1="40" y1="10" x2="40" y2="{svg_h-30}" stroke="#475569" stroke-width="1.5"/>
    <line x1="40" y1="{svg_h-30}" x2="{svg_w-20}" y2="{svg_h-30}" stroke="#475569" stroke-width="1.5"/>
    <!-- BF16 curve -->
    <polyline points="{bf16_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,3" opacity="0.8"/>
    <!-- FP8 curve -->
    <polyline points="{fp8_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>
    <!-- Labels -->
    <text x="{norm_x(200)-10}" y="{norm_y(fp8_loss[-1])-8}" fill="#C74634" font-size="12">FP8-E4M3</text>
    <text x="{norm_x(200)-10}" y="{norm_y(bf16_loss[-1])-8}" fill="#38bdf8" font-size="12">BF16</text>
    <!-- Y axis labels -->
    {''.join(f'<text x="4" y="{norm_y(v)+4}" fill="#64748b" font-size="10">{v:.1f}</text>' for v in [0.5,1.0,1.5,2.0,2.5])}
    <!-- X axis labels -->
    {''.join(f'<text x="{norm_x(s)}" y="{svg_h-12}" fill="#64748b" font-size="10" text-anchor="middle">{s}</text>' for s in [0,50,100,150,200])}
  </svg>
  <div>
    <span class="badge green">FP8 final: {round(fp8_loss[-1],3)}</span>
    <span class="badge" style="background:#0c1a2e;color:#38bdf8">BF16 final: {round(bf16_loss[-1],3)}</span>
  </div>
</div>

<div class="card">
  <h2>Throughput by Precision (tokens/sec)</h2>
  <svg width="{bar_svg_w}" height="{bar_svg_h}">{bars}</svg>
</div>

<div class="card">
  <h2>Gradient Norm (last 50 steps)</h2>
  <svg width="{sp_w}" height="{sp_h}" style="display:block">
    <rect width="{sp_w}" height="{sp_h}" fill="#0f172a" rx="4"/>
    <polyline points="{sp_pts}" fill="none" stroke="#a78bfa" stroke-width="1.8"/>
  </svg>
  <div style="color:#64748b;font-size:11px;margin-top:4px">Current grad norm: {round(gnorm[-1],4)} &bull; Clip threshold: 1.0</div>
</div>

<div class="card" style="min-width:560px">
  <h2>Precision Benchmark Summary</h2>
  <table>
    <thead><tr>
      <th>Precision</th><th>FWD Mem</th><th>Optimizer Mem</th><th>Tokens/sec</th><th>$/10k steps</th>
    </tr></thead>
    <tbody>{mem_rows}</tbody>
  </table>
</div>

<div style="padding:12px 24px;color:#334155;font-size:11px">
  FP8 Training Optimizer v1.0 &bull; OCI A100-80GB &bull; GR00T N1.6 backbone &bull; Port {PORT}
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="FP8 Training Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "fp8_training_optimizer"}

    @app.get("/metrics")
    def metrics():
        random.seed()
        return {
            "precision": "FP8-E4M3",
            "current_step": random.randint(140, 200),
            "loss": round(random.uniform(0.11, 0.15), 4),
            "throughput_tokens_per_sec": random.randint(59000, 63000),
            "gpu_util_pct": random.randint(87, 96),
            "vram_gb": round(random.uniform(6.8, 7.3), 2),
            "grad_norm": round(random.uniform(0.04, 0.12), 4),
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
