"""NVIDIA Co-Engineering Tracker — FastAPI port 8885"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8885

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # 5 co-engineering workstreams
    workstreams = [
        {"name": "Isaac_Sim_opt",      "readiness": 82, "status": "Active",   "color": "#22c55e"},
        {"name": "Cosmos_weights",     "readiness": 67, "status": "In Review", "color": "#38bdf8"},
        {"name": "GR00T_N2",           "readiness": 54, "status": "Planning",  "color": "#f97316"},
        {"name": "GTC_2027",           "readiness": 91, "status": "On Track",  "color": "#22c55e"},
        {"name": "OCI_preferred_cloud","readiness": 73, "status": "Active",   "color": "#38bdf8"},
    ]
    readiness_bars = "".join(
        f'<g>'
        f'<text x="10" y="{28+i*36}" fill="#38bdf8" font-size="12">{ws["name"]}</text>'
        f'<rect x="180" y="{14+i*36}" width="{int(ws["readiness"]*2)}" height="18" fill="{ws["color"]}" rx="4"/>'
        f'<text x="{186+int(ws["readiness"]*2)}" y="{27+i*36}" fill="#e2e8f0" font-size="11"> {ws["readiness"]}%</text>'
        f'<text x="390" y="{27+i*36}" fill="#94a3b8" font-size="11">{ws["status"]}</text>'
        f'</g>'
        for i, ws in enumerate(workstreams)
    )
    # Dependency map as text table
    dep_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#38bdf8">{ws["name"]}</td>'
        f'<td style="padding:6px 12px;text-align:center">{ws["readiness"]}%</td>'
        f'<td style="padding:6px 12px;color:{ws["color"]}">{ws["status"]}</td></tr>'
        for ws in workstreams
    )
    return f"""<!DOCTYPE html><html><head><title>NVIDIA Co-Engineering Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{background:#0f172a;padding:8px 12px;color:#94a3b8;text-align:left}}
tr:nth-child(even){{background:#0f172a33}}</style></head>
<body><h1>NVIDIA Co-Engineering Tracker</h1>
<div class="card"><h2>Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Workstream Readiness</h2>
<svg width="500" height="{20+len(workstreams)*36}">{readiness_bars}</svg>
</div>
<div class="card"><h2>Dependency Map</h2>
<table><tr><th>Workstream</th><th>Readiness</th><th>Status</th></tr>{dep_rows}</table>
<p style="color:#94a3b8;font-size:13px;margin-top:12px">
Dependencies: GR00T_N2 ← Cosmos_weights ← Isaac_Sim_opt &nbsp;|&nbsp; GTC_2027 ← all tracks &nbsp;|&nbsp; OCI_preferred_cloud ← GTC_2027
</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="NVIDIA Co-Engineering Tracker")
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
