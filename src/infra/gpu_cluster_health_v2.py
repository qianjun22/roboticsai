"""GPU Cluster Health v2 — FastAPI port 8383"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8383

def build_html():
    random.seed(85)
    nodes = [
        {"name": "Ashburn GPU4", "score": 97, "util": 91, "temp": 74, "ecc": 0, "status": "HEALTHY", "color": "#22c55e"},
        {"name": "Ashburn GPU1", "score": 94, "util": 87, "temp": 71, "ecc": 0, "status": "HEALTHY", "color": "#22c55e"},
        {"name": "Phoenix GPU1", "score": 81, "util": 62, "temp": 78, "ecc": 2, "status": "WATCH", "color": "#f59e0b"},
        {"name": "Frankfurt GPU1", "score": 89, "util": 71, "temp": 69, "ecc": 0, "status": "HEALTHY", "color": "#38bdf8"},
    ]

    # Node health cards with sparklines
    node_cards = ""
    for ni, node in enumerate(nodes):
        color = node["color"]
        x_offset = ni * 135

        # Generate sparkline data (30-day health score)
        random.seed(ni + 100)
        spark = [round(node["score"] + random.uniform(-5, 3), 1) for _ in range(30)]
        if node["status"] == "WATCH":
            # Declining trend
            spark = [round(90 - i*0.3 + random.uniform(-2,2), 1) for i in range(30)]
        
        spark_pts = " ".join(f"{i*4},{60-spark[i]*0.55}" for i in range(30))
        
        node_cards += f"""<g transform="translate({x_offset+5}, 20)">
<rect width="125" height="110" fill="#0f172a" rx="4" stroke="{color}" stroke-width="1"/>
<text x="62" y="18" text-anchor="middle" fill="{color}" font-size="8">{node["name"]}</text>
<text x="62" y="38" text-anchor="middle" fill="{color}" font-size="20" font-weight="bold">{node["score"]}</text>
<text x="62" y="50" text-anchor="middle" fill="#64748b" font-size="7">health score</text>
<text x="10" y="65" fill="#94a3b8" font-size="7">util:{node["util"]}% temp:{node["temp"]}°C ecc:{node["ecc"]}</text>
<polyline points="{spark_pts}" fill="none" stroke="{color}" stroke-width="1" transform="translate(5,75)"/>
<rect x="5" y="100" width="50" height="6" fill="{color}" rx="2"/>
<text x="62" y="107" fill="{color}" font-size="7">{node["status"]}</text>
</g>"""

    # Predictive maintenance timeline
    maint_events = [
        ("Phoenix GPU1", "2026-05-15", "WATCH", "#f59e0b", "ECC errors increasing, temp +2°C/mo"),
        ("Ashburn GPU4", "2026-08-01", "SCHEDULED", "#38bdf8", "Routine maintenance window"),
        ("Frankfurt GPU1", "2026-07-10", "PLANNED", "#22c55e", "GPU driver update"),
    ]
    
    maint_items = ""
    for i, (node, date, status, color, note) in enumerate(maint_events):
        y = 20 + i * 35
        maint_items += f"""<div style="padding:8px;background:#0f172a;border-radius:6px;margin:6px 0;border-left:3px solid {color}">
<div style="display:flex;justify-content:space-between">
<span style="color:#e2e8f0;font-size:0.85em">{node}</span>
<span style="background:{color};color:#fff;padding:1px 6px;border-radius:3px;font-size:0.75em">{status}</span>
</div>
<div style="color:#64748b;font-size:0.75em;margin-top:2px">{date} — {note}</div>
</div>"""

    # ECC error trend
    days = list(range(1, 31))
    ecc_counts = [0]*20 + [0,0,0,1,1,2,2,1,2,3]
    ecc_bars = ""
    for i, (d, ecc) in enumerate(zip(days, ecc_counts)):
        color = "#C74634" if ecc >= 2 else "#f59e0b" if ecc >= 1 else "#22c55e"
        h = max(2, ecc * 20)
        ecc_bars += f'<rect x="{20+i*17}" y="{80-h}" width="14" height="{h}" fill="{color}" opacity="0.8" rx="1"/>'
        if i % 5 == 0:
            ecc_bars += f'<text x="{27+i*17}" y="92" text-anchor="middle" fill="#64748b" font-size="7">d{d}</text>'

    fleet_health = round(sum(n["score"] for n in nodes)/len(nodes), 1)

    return f"""<!DOCTYPE html><html><head><title>GPU Cluster Health v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>GPU Cluster Health v2</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{fleet_health}%</div><div style="font-size:0.75em;color:#94a3b8">Fleet Health</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">1</div><div style="font-size:0.75em;color:#94a3b8">WATCH</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">3</div><div style="font-size:0.75em;color:#94a3b8">HEALTHY</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">May 15</div><div style="font-size:0.75em;color:#94a3b8">Next Maint.</div></div>
</div>
<div class="card">
<h2>Node Health Dashboard</h2>
<svg viewBox="0 555 550 135" style="height:145px">
<rect width="550" height="555" fill="#0f172a" rx="4"/>
{node_cards}
</svg>
</div>
<div class="grid">
<div class="card"><h2>ECC Error Trend (30d — Phoenix GPU1)</h2>
<svg viewBox="0 0 540 100"><rect width="540" height="100" fill="#0f172a" rx="4"/>
<line x1="15" y1="80" x2="535" y2="80" stroke="#334155" stroke-width="1"/>
{ecc_bars}
</svg>
<div style="margin-top:4px;font-size:0.75em;color:#f59e0b">ECC errors rising last 10 days — schedule maintenance before May 15</div>
</div>
<div class="card"><h2>Maintenance Timeline</h2>
{maint_items}
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GPU Cluster Health v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"fleet_health":96.2,"watch_nodes":1}

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
