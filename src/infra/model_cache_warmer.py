"""Model Cache Warmer — FastAPI port 8359"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8359

def build_html():
    random.seed(55)
    hours = list(range(24))
    # Request volume by hour (peak 9AM-6PM)
    req_vol = [int(30 + 120 * max(0, math.sin(math.pi*(h-7)/11)) + random.randint(-10,10)) for h in hours]
    
    # Warmup strategy coverage
    strategies = [
        ("cold_start", 1840, 0.31, "#C74634"),
        ("partial_warmup", 620, 0.62, "#f59e0b"),
        ("full_warmup", 226, 0.89, "#22c55e"),
        ("predictive_preload", 226, 0.94, "#38bdf8"),
    ]

    # Bar chart for strategies
    strat_bars = ""
    for i, (name, lat, sla_cov, color) in enumerate(strategies):
        x = 40 + i * 130
        h_lat = int(lat / 10)
        strat_bars += f'<rect x="{x}" y="{200-h_lat}" width="60" height="{h_lat}" fill="{color}" opacity="0.85" rx="3"/>'
        strat_bars += f'<text x="{x+30}" y="{200-h_lat-5}" text-anchor="middle" fill="{color}" font-size="9">{lat}ms</text>'
        strat_bars += f'<text x="{x+30}" y="215" text-anchor="middle" fill="#94a3b8" font-size="8">{name.replace("_"," ")}</text>'
        strat_bars += f'<text x="{x+30}" y="228" text-anchor="middle" fill="{color}" font-size="8">{int(sla_cov*100)}% SLA</text>'

    # 24h coverage timeline
    coverage_rects = ""
    for h in hours:
        vol = req_vol[h]
        is_peak = 9 <= h <= 18
        in_warmup = 7 <= h <= 20
        fill = "#22c55e" if in_warmup else "#334155"
        x = 30 + h * 22
        coverage_rects += f'<rect x="{x}" y="{120-min(100, vol//2)}" width="18" height="{min(100, vol//2)}" fill="{fill}" opacity="0.8" rx="2"/>'
        if h % 3 == 0:
            coverage_rects += f'<text x="{x+9}" y="135" text-anchor="middle" fill="#64748b" font-size="8">{h:02d}h</text>'

    return f"""<!DOCTYPE html><html><head><title>Model Cache Warmer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Model Cache Warmer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">226ms</div><div style="font-size:0.75em;color:#94a3b8">Warm p50</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">1840ms</div><div style="font-size:0.75em;color:#94a3b8">Cold p50</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">94%</div><div style="font-size:0.75em;color:#94a3b8">SLA Coverage</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">$12/d</div><div style="font-size:0.75em;color:#94a3b8">Idle GPU Cost</div></div>
</div>
<div class="grid">
<div class="card"><h2>Strategy Latency Comparison</h2>
<svg viewBox="0 0 580 245"><rect width="580" height="245" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="200" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="200" x2="560" y2="200" stroke="#334155" stroke-width="1"/>
<!-- SLA line at 300ms = 30 px -->
<line x1="30" y1="170" x2="560" y2="170" stroke="#22c55e" stroke-dasharray="3,3" stroke-width="1" opacity="0.5"/>
<text x="490" y="168" fill="#22c55e" font-size="8">SLA 300ms</text>
{strat_bars}
</svg>
</div>
<div class="card"><h2>24h Request Volume + Warmup Schedule</h2>
<svg viewBox="0 0 580 150"><rect width="580" height="150" fill="#0f172a" rx="4"/>
<line x1="30" y1="120" x2="560" y2="120" stroke="#334155" stroke-width="1"/>
{coverage_rects}
<rect x="168" y="8" width="286" height="108" fill="#22c55e" opacity="0.04" rx="2"/>
<text x="311" y="20" text-anchor="middle" fill="#22c55e" font-size="8" opacity="0.7">Warmup window active (07h–20h)</text>
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">
<span style="color:#22c55e">■</span> warmup active &nbsp;
<span style="color:#334155">■</span> idle (cold-start risk)
</div>
</div>
</div>
<div class="card" style="margin-top:16px">
<h2>Predictive Pre-load Strategy</h2>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:0.8em">
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">Trigger Logic</div>
<div style="color:#64748b;margin-top:4px">Load model 15min before predicted demand spike (ML forecast, MAPE=6%)</div>
</div>
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">GPU Idle Cost</div>
<div style="color:#64748b;margin-top:4px">$12/day to keep A100 warm outside peak hours — justified by SLA penalty avoidance</div>
</div>
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">Cold-Start Risk</div>
<div style="color:#64748b;margin-top:4px">6% traffic hits cold cache (22h-07h) — acceptable for current partner SLAs</div>
</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Cache Warmer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "warm_p50_ms": 226, "sla_coverage_pct": 94}

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
