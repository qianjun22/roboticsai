"""Training Stability Monitor — FastAPI port 8363"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8363

def build_html():
    random.seed(88)
    steps = list(range(0, 1001, 10))
    
    # Run10 gradient norm (stable)
    run10_gnorm = [round(max(0.1, 1.2 * math.exp(-s/300) + 0.08 + 0.05*random.uniform(-1,1)), 3) for s in steps]
    # Run5 gradient norm (unstable early)
    run5_gnorm = [round(max(0.08, 1.8 * math.exp(-s/400) + 0.12 + 0.15*random.uniform(-1,1) + (0.8 if 100<s<200 else 0)), 3) for s in steps]

    pts_r10 = " ".join(f"{30+i*4.5},{160-min(2.5,run10_gnorm[i])*50}" for i in range(len(steps)))
    pts_r5 = " ".join(f"{30+i*4.5},{160-min(2.5,run5_gnorm[i])*50}" for i in range(len(steps)))

    # Rolling std (instability measure)
    window = 10
    r10_std = []
    r5_std = []
    for i in range(len(steps)):
        start = max(0, i - window)
        r10_std.append(round(max(0.01, sum(abs(run10_gnorm[j] - sum(run10_gnorm[start:i+1])/(i-start+1)) for j in range(start, i+1)) / max(1, i-start+1)), 3))
        r5_std.append(round(max(0.01, sum(abs(run5_gnorm[j] - sum(run5_gnorm[start:i+1])/(i-start+1)) for j in range(start, i+1)) / max(1, i-start+1)), 3))

    pts_r10_std = " ".join(f"{30+i*4.5},{160-min(1.0,r10_std[i])*60}" for i in range(len(steps)))
    pts_r5_std = " ".join(f"{30+i*4.5},{160-min(1.0,r5_std[i])*60}" for i in range(len(steps)))

    # Run stability scores
    runs = [
        ("run5", 0.73, "#C74634", "UNSTABLE early, clips steps 100-200"),
        ("run9_v2.2", 0.88, "#f59e0b", "Stable after step 150, 3 late clips"),
        ("run10 (current)", 0.91, "#22c55e", "Most stable, threshold auto-adjusted"),
        ("groot_v2 (staging)", 0.94, "#22c55e", "Excellent, no clips after step 50"),
    ]
    run_bars = ""
    for i, (name, score, color, note) in enumerate(runs):
        w = int(score * 200)
        y = 20 + i * 40
        run_bars += f'<rect x="140" y="{y}" width="{w}" height="22" fill="{color}" opacity="0.8" rx="3"/>'
        run_bars += f'<text x="10" y="{y+15}" fill="#94a3b8" font-size="9">{name}</text>'
        run_bars += f'<text x="{145+w}" y="{y+15}" fill="{color}" font-size="9">{score} — {note}</text>'

    return f"""<!DOCTYPE html><html><head><title>Training Stability Monitor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Training Stability Monitor</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.91</div><div style="font-size:0.75em;color:#94a3b8">run10 Stability</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">0.73</div><div style="font-size:0.75em;color:#94a3b8">run5 Stability</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.91</div><div style="font-size:0.75em;color:#94a3b8">Auto-clip thresh</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">1000</div><div style="font-size:0.75em;color:#94a3b8">Steps Monitored</div></div>
</div>
<div class="grid">
<div class="card"><h2>Gradient Norm Trajectory</h2>
<svg viewBox="0 0 500 180"><rect width="500" height="180" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="165" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="165" x2="490" y2="165" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_r5}" fill="none" stroke="#C74634" stroke-width="1.5" opacity="0.8"/>
<polyline points="{pts_r10}" fill="none" stroke="#22c55e" stroke-width="2"/>
<!-- instability region annotation for run5 -->
<rect x="75" y="20" width="45" height="100" fill="#C74634" opacity="0.05" rx="2"/>
<text x="97" y="18" text-anchor="middle" fill="#C74634" font-size="8">unstable</text>
<text x="200" y="178" fill="#64748b" font-size="9">Training Step</text>
<text x="400" y="40" fill="#22c55e" font-size="9">run10 (stable)</text>
<text x="400" y="55" fill="#C74634" font-size="9">run5 (unstable)</text>
</svg>
</div>
<div class="card"><h2>Rolling Std of Grad Norm (10-step window)</h2>
<svg viewBox="0 0 500 180"><rect width="500" height="180" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="165" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="165" x2="490" y2="165" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_r5_std}" fill="none" stroke="#C74634" stroke-width="1.5" opacity="0.8"/>
<polyline points="{pts_r10_std}" fill="none" stroke="#22c55e" stroke-width="2"/>
<line x1="30" y1="{160-0.15*60}" x2="490" y2="{160-0.15*60}" stroke="#f59e0b" stroke-dasharray="3,3" stroke-width="1" opacity="0.6"/>
<text x="450" y="{155-0.15*60}" fill="#f59e0b" font-size="8">clip threshold</text>
<text x="200" y="178" fill="#64748b" font-size="9">Step</text>
</svg>
</div>
</div>
<div class="card" style="margin-top:16px"><h2>Stability Score by Run</h2>
<svg viewBox="0 0 700 180"><rect width="700" height="180" fill="#0f172a" rx="4"/>
{run_bars}
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Stability Monitor")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"run10_stability":0.91,"run5_stability":0.73}

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
