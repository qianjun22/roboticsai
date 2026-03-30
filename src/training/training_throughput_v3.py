"""Training Throughput v3 — FastAPI port 8360"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8360

def build_html():
    random.seed(42)
    gpus = [1, 2, 3, 4]
    throughput = [2.35, 4.47, 6.81, 9.40]  # it/s
    ideal = [2.35 * g for g in gpus]
    efficiency = [round(t/i*100) for t, i in zip(throughput, ideal)]

    # Throughput vs GPU count SVG
    pts_actual = " ".join(f"{60+g*100},{200-t*15}" for g, t in zip(gpus, throughput))
    pts_ideal = " ".join(f"{60+g*100},{200-t*15}" for g, t in zip(gpus, ideal))

    # Bottleneck waterfall
    phases = [("data_loading", 12, "#38bdf8"), ("forward", 41, "#22c55e"), ("backward", 38, "#f59e0b"), ("grad_sync", 9, "#C74634")]
    waterfall = ""
    x_offset = 40
    for name, pct, color in phases:
        w = int(pct * 4.5)
        waterfall += f'<rect x="{x_offset}" y="60" width="{w}" height="40" fill="{color}" opacity="0.85" rx="2"/>'
        waterfall += f'<text x="{x_offset + w//2}" y="85" text-anchor="middle" fill="#fff" font-size="9">{pct}%</text>'
        waterfall += f'<text x="{x_offset + w//2}" y="120" text-anchor="middle" fill="{color}" font-size="8">{name.replace("_"," ")}</text>'
        x_offset += w + 4

    # Cost per 10k steps
    cost_data = [
        ("OCI A100\u00d71", 2.35, 0.43),
        ("OCI A100\u00d72 DDP", 4.47, 0.23),
        ("OCI A100\u00d74 DDP", 9.40, 0.11),
        ("FP8 (target)", 13.20, 0.08),
        ("AWS p4d equiv", 2.10, 4.13),
    ]
    cost_bars = ""
    for i, (name, its, cost) in enumerate(cost_data):
        color = "#C74634" if "AWS" in name else "#38bdf8" if "FP8" in name else "#22c55e"
        bar_w = int(cost * 60)
        cost_bars += f'<text x="10" y="{35+i*28}" fill="#94a3b8" font-size="9">{name}</text>'
        cost_bars += f'<rect x="160" y="{22+i*28}" width="{bar_w}" height="16" fill="{color}" opacity="0.8" rx="2"/>'
        cost_bars += f'<text x="{165+bar_w}" y="{35+i*28}" fill="{color}" font-size="9">${cost}/10k steps</text>'

    return f"""<!DOCTYPE html><html><head><title>Training Throughput v3 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Training Throughput v3</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">9.4 it/s</div><div style="font-size:0.75em;color:#94a3b8">4\u00d7A100 Peak</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">13.2 it/s</div><div style="font-size:0.75em;color:#94a3b8">FP8 Target</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">$0.11</div><div style="font-size:0.75em;color:#94a3b8">4\u00d7A100 / 10k steps</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">37\u00d7</div><div style="font-size:0.75em;color:#94a3b8">vs AWS p4d</div></div>
</div>
<div class="grid">
<div class="card"><h2>Throughput vs GPU Count</h2>
<svg viewBox="0 0 520 240"><rect width="520" height="240" fill="#0f172a" rx="4"/>
<line x1="40" y1="10" x2="40" y2="205" stroke="#334155" stroke-width="1"/>
<line x1="40" y1="205" x2="510" y2="205" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_ideal}" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4,3"/>
<polyline points="{pts_actual}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
{''.join(f'<circle cx="{60+g*100}" cy="{200-t*15}" r="5" fill="#22c55e"/><text x="{60+g*100+8}" y="{195-t*15}" fill="#22c55e" font-size="9">{t} it/s</text>' for g,t in zip(gpus,throughput))}
<text x="450" y="165" fill="#334155" font-size="9">ideal</text>
<text x="200" y="218" fill="#64748b" font-size="9">GPU Count (A100_80GB)</text>
<text x="42" y="218" fill="#64748b" font-size="8">1</text>
<text x="140" y="218" fill="#64748b" font-size="8">2</text>
<text x="240" y="218" fill="#64748b" font-size="8">3</text>
<text x="338" y="218" fill="#64748b" font-size="8">4</text>
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">
Scaling efficiency: {'  '.join(f'{g}\u00d7GPU={e}%' for g,e in zip(gpus,efficiency))}
</div>
</div>
<div class="card"><h2>Step Time Bottleneck Breakdown</h2>
<svg viewBox="0 0 530 140"><rect width="530" height="140" fill="#0f172a" rx="4"/>
{waterfall}
<line x1="35" y1="58" x2="530" y2="58" stroke="#334155" stroke-width="0.5"/>
</svg>
<div style="margin-top:8px;font-size:0.8em;color:#94a3b8">
Forward (41%) + Backward (38%) = 79% compute-bound. Data loading 12% \u2192 prefetch queue fix needed for FP8 target.
</div>
</div>
</div>
<div class="card" style="margin-top:16px"><h2>Cost per 10k Steps</h2>
<svg viewBox="0 0 580 160"><rect width="580" height="160" fill="#0f172a" rx="4"/>
{cost_bars}
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Throughput v3")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"throughput_4gpu":9.4,"cost_per_10k":0.11}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()
