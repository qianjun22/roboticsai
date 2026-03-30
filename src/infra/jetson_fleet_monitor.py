"""Jetson Fleet Monitor — FastAPI port 8407"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8407

def build_html():
    devices = [
        {"name":"PI_SF","model":"Jetson_AGX_Orin","policy":"groot_v2","sr":0.73,"status":"ONLINE","lag_hrs":0.3,"battery":None,"temp":62},
        {"name":"Apptronik_Austin","model":"Jetson_AGX_Orin","policy":"groot_v2","sr":0.71,"status":"ONLINE","lag_hrs":1.2,"battery":None,"temp":58},
        {"name":"1X_Stockholm","model":"Jetson_Orin_NX","policy":"dagger_r9","sr":0.68,"status":"DEGRADED","lag_hrs":8.4,"battery":None,"temp":71},
    ]

    # Device status cards SVG
    svg_d = '<svg width="420" height="200" style="background:#0f172a">'
    for di, dev in enumerate(devices):
        x = 10 + di*140; col = "#22c55e" if dev["status"]=="ONLINE" else "#f59e0b"
        svg_d += f'<rect x="{x}" y="10" width="130" height="170" fill="#1e293b" rx="6" stroke="{col}" stroke-width="1.5"/>'
        svg_d += f'<text x="{x+65}" y="30" fill="white" font-size="10" text-anchor="middle" font-weight="bold">{dev["name"]}</text>'
        svg_d += f'<text x="{x+65}" y="46" fill="#94a3b8" font-size="8" text-anchor="middle">{dev["model"]}</text>'
        svg_d += f'<circle cx="{x+65}" cy="80" r="20" fill="{col}" opacity="0.2" stroke="{col}" stroke-width="2"/>'
        svg_d += f'<text x="{x+65}" y="85" fill="{col}" font-size="11" text-anchor="middle" font-weight="bold">{dev["sr"]:.0%}</text>'
        svg_d += f'<text x="{x+65}" y="100" fill="#94a3b8" font-size="7" text-anchor="middle">SR on-device</text>'
        svg_d += f'<text x="{x+65}" y="120" fill="#94a3b8" font-size="8" text-anchor="middle">Policy: {dev["policy"]}</text>'
        svg_d += f'<text x="{x+65}" y="135" fill="{col}" font-size="8" text-anchor="middle">{dev["status"]}</text>'
        svg_d += f'<text x="{x+65}" y="150" fill="#94a3b8" font-size="8" text-anchor="middle">Sync lag: {dev["lag_hrs"]:.1f}h</text>'
        svg_d += f'<text x="{x+65}" y="165" fill={{"#f59e0b" if dev["temp"]>70 else "#94a3b8"}} font-size="8" text-anchor="middle">Temp: {dev["temp"]}\u00b0C</text>'
    svg_d += '</svg>'

    # Model sync timeline (30 days)
    days = list(range(1,31))
    svg_t = '<svg width="420" height="180" style="background:#0f172a">'
    svg_t += '<line x1="30" y1="10" x2="30" y2="150" stroke="#475569" stroke-width="1"/>'
    svg_t += '<line x1="30" y1="150" x2="400" y2="150" stroke="#475569" stroke-width="1"/>'
    dev_colors = ["#22c55e","#38bdf8","#f59e0b"]
    # Sync lag per day (hours)
    for di, (dev, col) in enumerate(zip(devices, dev_colors)):
        base_lag = [0.3,1.2,8.4][di]
        pts = []
        for day in days:
            lag = base_lag*(0.8+0.4*random.random())
            if day in [8,15,22]: lag *= 3  # occasional spikes
            x = 30 + (day-1)/29*360; y = 150 - min(lag, 24)/24*130
            pts.append((x, y))
        for j in range(len(pts)-1):
            x1,y1=pts[j]; x2,y2=pts[j+1]
            svg_t += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="1.5"/>'
        svg_t += f'<text x="405" y="{pts[-1][1]+4:.0f}" fill="{col}" font-size="8">{dev["name"][:5]}</text>'
    svg_t += '<text x="215" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Model Sync Lag Over 30 Days (hours)</text>'
    svg_t += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Jetson Fleet Monitor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;padding:16px;border-radius:8px;margin-bottom:16px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Jetson Fleet Monitor</h1>
<p style="color:#94a3b8">Port {PORT} | 3-device edge deployment status + model sync tracking</p>
<div class="card"><h2>Device Status</h2>{svg_d}
<div style="color:#f59e0b;font-size:12px;margin-top:8px">&#9888; 1X_Stockholm DEGRADED: sync lag 8.4h, temp 71\u00b0C — check network connectivity</div>
</div>
<div class="card"><h2>Model Sync Timeline (30 days)</h2>{svg_t}
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Offline resilience: 72hr local inference without cloud sync<br>Checkpoint compression: 6.7GB \u2192 2.1GB (Jetson-optimized)<br>Auto-retry on sync failure; manual override via SSH</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Jetson Fleet Monitor")
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
