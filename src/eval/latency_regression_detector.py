"""Latency Regression Detector — FastAPI port 8371"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8371

def build_html():
    random.seed(50)
    versions = list(range(1, 31))
    
    # p50 latency per version (with regressions at v11 and v17)
    p50 = []
    p99 = []
    for v in versions:
        base = 226 + 3*math.sin(v/3)
        if v == 11: base += 45  # chunk_size bug
        elif v == 17: base += 28  # token overflow
        elif v > 11: base = max(226, base - 5)
        elif v > 17: base = max(226, base - 3)
        noise = random.uniform(-4, 4)
        p50.append(round(base + noise, 1))
        p99.append(round(base * 1.18 + noise*2, 1))

    avg = sum(p50)/len(p50)
    std = math.sqrt(sum((v-avg)**2 for v in p50)/len(p50))
    ucl = round(avg + 2*std, 1)
    lcl = round(avg - 2*std, 1)

    pts_p50 = " ".join(f"{30+i*17},{180-p50[i]*0.3}" for i in range(len(versions)))
    pts_p99 = " ".join(f"{30+i*17},{180-p99[i]*0.3}" for i in range(len(versions)))
    y_avg = 180 - avg*0.3
    y_ucl = 180 - ucl*0.3
    y_lcl = 180 - lcl*0.3

    regression_markers = ""
    for i, v in enumerate(versions):
        if v in [11, 17]:
            x = 30 + i*17
            regression_markers += f'<circle cx="{x}" cy="{180-p50[i]*0.3}" r="6" fill="#C74634" stroke="#fff" stroke-width="1"/>'
            regression_markers += f'<text x="{x}" y="{170-p50[i]*0.3}" text-anchor="middle" fill="#C74634" font-size="8">v{v}</text>'

    # Component breakdown SVG
    components = [
        ("tokenize", 8.2, "#38bdf8"),
        ("vision_enc", 41.3, "#22c55e"),
        ("transformer", 132.4, "#C74634"),
        ("action_head", 28.1, "#f59e0b"),
        ("decode", 12.8, "#a78bfa"),
        ("network", 3.2, "#64748b"),
    ]
    comp_bars = ""
    for i, (name, ms, color) in enumerate(components):
        w = int(ms * 2.1)
        y = 20 + i * 26
        comp_bars += f'<rect x="100" y="{y}" width="{w}" height="18" fill="{color}" opacity="0.8" rx="2"/>'
        comp_bars += f'<text x="95" y="{y+13}" text-anchor="end" fill="#94a3b8" font-size="9">{name}</text>'
        comp_bars += f'<text x="{105+w}" y="{y+13}" fill="{color}" font-size="9">{ms}ms ({round(ms/226*100)}%)</text>'

    return f"""<!DOCTYPE html><html><head><title>Latency Regression Detector — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Latency Regression Detector</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">226ms</div><div style="font-size:0.75em;color:#94a3b8">Current p50</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">2</div><div style="font-size:0.75em;color:#94a3b8">Regressions (30v)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">{round(ucl,0):.0f}ms</div><div style="font-size:0.75em;color:#94a3b8">UCL</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">PASS</div><div style="font-size:0.75em;color:#94a3b8">v30 Gate</div></div>
</div>
<div class="card"><h2>p50/p99 Control Chart (30 versions)</h2>
<svg viewBox="0 0 540 210"><rect width="540" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="530" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="{y_ucl}" x2="530" y2="{y_ucl}" stroke="#C74634" stroke-dasharray="4,3" stroke-width="1.5"/>
<text x="490" y="{y_ucl-3}" fill="#C74634" font-size="8">UCL {ucl}ms</text>
<line x1="30" y1="{y_avg}" x2="530" y2="{y_avg}" stroke="#64748b" stroke-dasharray="2,2" stroke-width="1"/>
<text x="490" y="{y_avg-3}" fill="#64748b" font-size="8">mean</text>
<polyline points="{pts_p99}" fill="none" stroke="#f59e0b" stroke-width="1" opacity="0.7"/>
<polyline points="{pts_p50}" fill="none" stroke="#22c55e" stroke-width="2"/>
{regression_markers}
<text x="260" y="198" fill="#64748b" font-size="9">Version</text>
<text x="400" y="30" fill="#22c55e" font-size="8">p50</text>
<text x="400" y="42" fill="#f59e0b" font-size="8">p99</text>
</svg>
<div style="margin-top:8px;font-size:0.8em;color:#64748b">
v11 regression: chunk_size=8 bug (+45ms). v17: token overflow (+28ms). Both resolved within 2 days.
</div>
</div>
<div class="grid">
<div class="card"><h2>Component Breakdown (p50=226ms)</h2>
<svg viewBox="0 0 560 185"><rect width="560" height="185" fill="#0f172a" rx="4"/>
{comp_bars}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">transformer (58.6%) dominates — TRT FP8 target: 90ms → total 109ms</div>
</div>
<div class="card"><h2>Rollback Decision Gate</h2>
<div style="font-size:0.85em">
<div style="padding:10px;background:#0f172a;border-radius:6px;margin:6px 0;border-left:3px solid #22c55e">
<div style="color:#22c55e;font-weight:bold">DEPLOY</div>
<div style="color:#64748b">p50 &lt; UCL ({round(ucl,0):.0f}ms) AND no regression in last 3 versions</div>
</div>
<div style="padding:10px;background:#0f172a;border-radius:6px;margin:6px 0;border-left:3px solid #f59e0b">
<div style="color:#f59e0b;font-weight:bold">HOLD</div>
<div style="color:#64748b">p50 &gt; UCL OR single-version p99 spike &gt;350ms</div>
</div>
<div style="padding:10px;background:#0f172a;border-radius:6px;margin:6px 0;border-left:3px solid #C74634">
<div style="color:#C74634;font-weight:bold">ROLLBACK</div>
<div style="color:#64748b">p50 &gt; UCL+2σ OR p99 &gt;500ms OR 2+ consecutive regressions</div>
</div>
<div style="margin-top:12px;color:#22c55e;font-size:0.85em">v30 status: <strong>DEPLOY</strong> — p50=226ms, within UCL</div>
</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Latency Regression Detector")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"current_p50_ms":226,"regressions_30v":2,"gate":"DEPLOY"}

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
