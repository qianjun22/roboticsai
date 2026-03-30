"""Cost Anomaly Detector — FastAPI port 8425"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8425

def build_html():
    # 90-day cost time series with anomalies
    days = list(range(90))
    base_cost = 8.0
    costs = []
    anomaly_days = [14, 28, 47, 71]
    anomaly_causes = ["DAgger_launch","eval_spike","checkpoint_flood","spot_preemption"]
    anomaly_costs =  [28.0, 19.0, 22.0, 16.0]

    for d in days:
        c = base_cost + random.gauss(0, 1.2) + d*0.02
        if d in anomaly_days:
            idx = anomaly_days.index(d)
            c = anomaly_costs[idx]
        costs.append(max(2, c))

    # Rolling mean and std
    window = 7
    rolling_mean = []
    rolling_std = []
    for i in range(len(costs)):
        start = max(0, i-window)
        subset = costs[start:i+1]
        m = sum(subset)/len(subset)
        s = (sum((x-m)**2 for x in subset)/len(subset))**0.5
        rolling_mean.append(m)
        rolling_std.append(max(0.5, s))

    max_cost = 32
    svg_ts = '<svg width="420" height="220" style="background:#0f172a">'
    svg_ts += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_ts += '<line x1="40" y1="170" x2="400" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*8; y = 170-yv*150/max_cost
        svg_ts += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">${yv}</text>'
    for i in range(10):
        x = 40+i*40
        svg_ts += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">d{i*10}</text>'

    # Upper/lower bands (±2σ)
    band_pts_upper = [(40+d*360/89, 170-(rolling_mean[d]+2*rolling_std[d])*150/max_cost) for d in days]
    band_pts_lower = [(40+d*360/89, 170-max(0,rolling_mean[d]-2*rolling_std[d])*150/max_cost) for d in days]
    # Fill band
    path_d = f"M {band_pts_upper[0][0]:.0f} {band_pts_upper[0][1]:.0f}"
    for x,y in band_pts_upper[1:]:
        path_d += f" L {x:.0f} {y:.0f}"
    for x,y in reversed(band_pts_lower):
        path_d += f" L {x:.0f} {y:.0f}"
    svg_ts += f'<path d="{path_d} Z" fill="#38bdf8" opacity="0.08"/>'
    # Mean line
    mean_pts = [(40+d*360/89, 170-rolling_mean[d]*150/max_cost) for d in days]
    for j in range(len(mean_pts)-1):
        x1,y1=mean_pts[j]; x2,y2=mean_pts[j+1]
        svg_ts += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#38bdf8" stroke-width="1" stroke-dasharray="3,2"/>'
    # Cost line
    cost_pts = [(40+d*360/89, 170-costs[d]*150/max_cost) for d in days]
    for j in range(len(cost_pts)-1):
        x1,y1=cost_pts[j]; x2,y2=cost_pts[j+1]
        svg_ts += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#22c55e" stroke-width="1.5"/>'
    # Anomaly markers
    for ad, cause, acost in zip(anomaly_days, anomaly_causes, anomaly_costs):
        ax = 40+ad*360/89; ay = 170-acost*150/max_cost
        svg_ts += f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="6" fill="#C74634" opacity="0.9"/>'
        svg_ts += f'<text x="{ax:.0f}" y="{ay-10:.0f}" fill="#C74634" font-size="7" text-anchor="middle">{cause[:8]}</text>'
    svg_ts += '</svg>'

    # Root cause bar
    svg_rc = '<svg width="320" height="180" style="background:#0f172a">'
    for i, (cause, acost) in enumerate(zip(anomaly_causes, anomaly_costs)):
        y = 20+i*36; w = int(acost/32*260)
        col = "#C74634" if acost > 25 else "#f59e0b" if acost > 18 else "#22c55e"
        svg_rc += f'<rect x="110" y="{y}" width="{w}" height="24" fill="{col}" opacity="0.8" rx="3"/>'
        svg_rc += f'<text x="105" y="{y+16}" fill="#94a3b8" font-size="8" text-anchor="end">{cause}</text>'
        svg_rc += f'<text x="{112+w}" y="{y+16}" fill="white" font-size="9">${acost:.0f}</text>'
    svg_rc += '<text x="200" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Anomaly Cost ($/day)</text>'
    svg_rc += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Cost Anomaly Detector — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Cost Anomaly Detector</h1>
<p style="color:#94a3b8">Port {PORT} | 90-day GPU cost time series with ±2σ anomaly detection</p>
<div class="grid">
<div class="card"><h2>Cost Timeline (rolling μ ±2σ)</h2>{svg_ts}</div>
<div class="card"><h2>Anomaly Root Cause</h2>{svg_rc}
<div style="margin-top:8px">
<div class="stat">4</div><div class="label">Anomaly events detected in 90 days</div>
<div class="stat" style="color:#C74634;margin-top:8px">$28</div><div class="label">DAgger launch day (highest anomaly)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Auto-budget lock triggers at 3σ deviation<br>DAgger launches: +250% expected cost spike<br>Pre-authorize known spikes to reduce false alerts<br>Checkpoint flood: reduce eval checkpoint frequency</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Anomaly Detector")
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
