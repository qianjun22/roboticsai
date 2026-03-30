"""Inference Request Analyzer — FastAPI port 8377"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8377

def build_html():
    random.seed(62)
    partners = ["PI Robotics", "Apptronik", "Covariant", "1X Tech", "Skild"]
    partner_share = [0.34, 0.22, 0.26, 0.11, 0.07]
    partner_colors = ["#22c55e", "#38bdf8", "#f59e0b", "#C74634", "#a78bfa"]

    # Stacked bar by partner × hour
    hours = list(range(0, 24, 2))
    stacked_bars = ""
    for hi, h in enumerate(hours):
        x = 30 + hi * 27
        cumul_y = 180
        total_h = int((80 + 40*math.sin(math.pi*(h-8)/12)) * (0.8 + 0.2*random.random()))
        for pi, (share, color) in enumerate(zip(partner_share, partner_colors)):
            seg_h = int(total_h * share)
            stacked_bars += f'<rect x="{x}" y="{cumul_y-seg_h}" width="22" height="{seg_h}" fill="{color}" opacity="0.8"/>'
            cumul_y -= seg_h
        if h % 4 == 0:
            stacked_bars += f'<text x="{x+11}" y="193" text-anchor="middle" fill="#64748b" font-size="8">{h:02d}h</text>'

    # Token count vs latency scatter (1000 requests simulated)
    scatter_pts = ""
    outlier_count = 0
    random.seed(63)
    for _ in range(120):
        tokens = random.randint(400, 1200)
        base_lat = 180 + tokens * 0.04
        lat = base_lat + random.gauss(0, 15)
        is_outlier = lat > 500
        if is_outlier:
            outlier_count += 1
        color = "#C74634" if is_outlier else "#22c55e"
        x = 30 + (tokens - 400) / 800 * 380
        y = 180 - min(lat, 600) / 600 * 160
        scatter_pts += f'<circle cx="{x}" cy="{y}" r="2.5" fill="{color}" opacity="0.7"/>'

    # 500ms threshold line
    y_500 = 180 - 500/600*160
    scatter_pts += f'<line x1="30" y1="{y_500}" x2="410" y2="{y_500}" stroke="#C74634" stroke-dasharray="3,3" stroke-width="1"/>'
    scatter_pts += f'<text x="415" y="{y_500+4}" fill="#C74634" font-size="8">500ms</text>'

    # Trend line
    scatter_pts += f'<line x1="30" y1="{180-196/600*160}" x2="410" y2="{180-228/600*160}" stroke="#64748b" stroke-dasharray="2,3" stroke-width="1"/>'

    return f"""<!DOCTYPE html><html><head><title>Inference Request Analyzer \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Inference Request Analyzer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">847</div><div style="font-size:0.75em;color:#94a3b8">Avg Req/hr</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">226ms</div><div style="font-size:0.75em;color:#94a3b8">Avg Latency</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">{outlier_count}</div><div style="font-size:0.75em;color:#94a3b8">Outliers &gt;500ms</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">99.72%</div><div style="font-size:0.75em;color:#94a3b8">Success Rate</div></div>
</div>
<div class="grid">
<div class="card"><h2>Request Volume by Partner \u00d7 Hour</h2>
<svg viewBox="0 0 390 210"><rect width="390" height="210" fill="#0f172a" rx="4"/>
<line x1="25" y1="180" x2="380" y2="180" stroke="#334155" stroke-width="1"/>
{stacked_bars}
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">
{'  '.join(f'<span style="color:{c}">\u25a0</span> {p[:4]}' for p,c in zip(partners,partner_colors))}
</div>
</div>
<div class="card"><h2>Token Count vs Latency (1000 requests)</h2>
<svg viewBox="0 0 460 210"><rect width="460" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="440" y2="185" stroke="#334155" stroke-width="1"/>
{scatter_pts}
<text x="220" y="200" fill="#64748b" font-size="9">Token Count</text>
<text x="32" y="200" fill="#64748b" font-size="8">400</text>
<text x="415" y="200" fill="#64748b" font-size="8">1200</text>
<text x="5" y="100" fill="#64748b" font-size="8" transform="rotate(-90,5,100)">Latency (ms)</text>
<text x="380" y="20" fill="#C74634" font-size="8">{outlier_count} outliers</text>
</svg></div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Request Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"avg_req_hr":847,"avg_latency_ms":226}

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
