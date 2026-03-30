"""Model A/B Tester — FastAPI port 8467"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8467

def build_html():
    # A vs B comparison
    metrics = ["SR (%)", "Latency (ms)", "Cost ($/1k req)", "Stability", "VRAM (GB)"]
    model_a = [0.71, 231, 0.89, 0.87, 19.2]  # dagger_r9
    model_b = [0.78, 226, 0.89, 0.91, 21.4]  # groot_v2
    # normalize for display
    norms = [1.0, 260, 1.0, 1.0, 25]
    max_vals = [1.0, 260, 1.0, 1.0, 25]
    bar_colors_a = "#64748b"
    bar_colors_b = "#C74634"

    ab_bars = ""
    for i, (metric, a, b, norm) in enumerate(zip(metrics, model_a, model_b, max_vals)):
        y = 15 + i * 36
        wa = int(a / norm * 260)
        wb = int(b / norm * 260)
        # for latency/cost/VRAM lower is better
        winner_b = b > a if i in [0, 3] else b < a
        highlight = "#22c55e" if winner_b else "#f59e0b"
        ab_bars += f'<rect x="130" y="{y}" width="{wa}" height="14" fill="{bar_colors_a}" opacity="0.7" rx="3"/>'
        ab_bars += f'<rect x="130" y="{y+16}" width="{wb}" height="14" fill="{bar_colors_b}" opacity="0.85" rx="3"/>'
        ab_bars += f'<text x="126" y="{y+10}" fill="#94a3b8" font-size="10" text-anchor="end">{metric}</text>'
        a_str = f"{int(a*100)}%" if norm == 1.0 else f"{a}"
        b_str = f"{int(b*100)}%" if norm == 1.0 else f"{b}"
        ab_bars += f'<text x="{130+wa+4}" y="{y+11}" fill="#94a3b8" font-size="9">{a_str}</text>'
        ab_bars += f'<text x="{130+wb+4}" y="{y+27}" fill="{highlight}" font-size="9">{b_str} ▲</text>'

    # p-value vs sample size
    sample_sizes = list(range(10, 101, 5))
    p_vals = [1/(1+math.exp((n-45)/8)) for n in sample_sizes]
    p_pts = " ".join(f"{30+i*17:.1f},{160-p_vals[i]*130:.1f}" for i in range(len(sample_sizes)))
    p_svg = f'<polyline points="{p_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
    sig_y = 160 - 0.05*130
    p_svg += f'<line x1="25" y1="{sig_y:.1f}" x2="360" y2="{sig_y:.1f}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
    p_svg += f'<text x="362" y="{sig_y+4:.1f}" fill="#22c55e" font-size="9">p=0.05</text>'
    # mark n=80 as sufficient
    n80_x = 30 + ((80-10)//5)*17
    p80_y = 160 - (1/(1+math.exp((80-45)/8)))*130
    p_svg += f'<circle cx="{n80_x}" cy="{p80_y:.1f}" r="5" fill="#C74634"/>'
    p_svg += f'<text x="{n80_x+6}" y="{p80_y-4:.1f}" fill="#C74634" font-size="9">n=80 (current)</text>'
    for n in [10, 30, 50, 70, 90]:
        p_svg += f'<text x="{30+(n-10)//5*17}" y="172" fill="#64748b" font-size="9" text-anchor="middle">{n}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Model A/B Tester</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
.legend{{display:flex;gap:16px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ld{{width:14px;height:8px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Model A/B Tester — dagger_r9 vs groot_v2</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">+7pp</div><div class="ml">SR: groot_v2 wins</div></div>
  <div class="m"><div class="mv">p=0.031</div><div class="ml">Statistical Significance</div><div class="delta">significant at p&lt;0.05</div></div>
  <div class="m"><div class="mv">80</div><div class="ml">Episodes in Test</div></div>
  <div class="m"><div class="mv">PROMOTE</div><div class="ml">Recommendation</div><div class="delta">groot_v2 → production</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>5-Metric Comparison (A=dagger_r9 / B=groot_v2)</h3>
    <svg viewBox="0 0 440 200" width="100%">
      <line x1="128" y1="10" x2="128" y2="195" stroke="#334155" stroke-width="1"/>
      {ab_bars}
    </svg>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#64748b;opacity:0.7"></div>A: dagger_r9 (current prod)</div>
      <div class="li"><div class="ld" style="background:#C74634"></div>B: groot_v2 (challenger)</div>
    </div>
  </div>
  <div class="card">
    <h3>p-Value vs Sample Size</h3>
    <svg viewBox="0 0 390 185" width="100%">
      <line x1="23" y1="10" x2="23" y2="163" stroke="#334155" stroke-width="1"/>
      <line x1="23" y1="163" x2="385" y2="163" stroke="#334155" stroke-width="1"/>
      {p_svg}
      <text x="205" y="183" fill="#64748b" font-size="9" text-anchor="middle">Sample Size (episodes) →</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model A/B Tester")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
