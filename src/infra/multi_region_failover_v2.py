"""Multi-Region Failover v2 — FastAPI port 8387"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8387

REGIONS = [
    {"name": "Ashburn",  "role": "PRIMARY",   "color": "#22c55e", "health": 98.7, "load": 847,  "uptime": 99.94, "lag": None},
    {"name": "Phoenix",  "role": "SECONDARY",  "color": "#38bdf8", "health": 91.2, "load": 0,    "uptime": 99.97, "lag": 8.2},
    {"name": "Frankfurt","role": "DR",         "color": "#94a3b8", "health": 94.1, "load": 0,    "uptime": 99.91, "lag": 31.4},
]

SCENARIOS = [
    {"name": "planned_maintenance", "rto": 45,  "rpo": 0},
    {"name": "region_outage",       "rto": 18,  "rpo": 0},
    {"name": "network_partition",   "rto": 12,  "rpo": 0},
    {"name": "full_failover",       "rto": 28,  "rpo": 0},
]

DRILLS = [
    {"date": "Apr 1",  "result": "PASSED", "actual_rto": 12},
    {"date": "Mar 15", "result": "PASSED", "actual_rto": 18},
    {"date": "Mar 1",  "result": "PASSED", "actual_rto": 22},
]

def build_html():
    # --- Topology SVG ---
    tw, th = 700, 220
    cx = [120, 350, 580]
    cy = [110, 110, 110]
    node_r = 48
    topo = f'<rect width="{tw}" height="{th}" rx="8" fill="#0f172a"/>'
    # Arrows
    for src, dst, label in [(0, 1, "primary→secondary"), (1, 2, "secondary→DR")]:
        x1 = cx[src] + node_r
        x2 = cx[dst] - node_r
        ymid = cy[src]
        topo += f'<line x1="{x1}" y1="{ymid}" x2="{x2}" y2="{ymid}" stroke="#334155" stroke-width="2" marker-end="url(#arr)"/>'
    topo += '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#334155"/></marker></defs>'
    # Nodes
    for i, r in enumerate(REGIONS):
        topo += f'<circle cx="{cx[i]}" cy="{cy[i]}" r="{node_r}" fill="#1e293b" stroke="{r["color"]}" stroke-width="3"/>'
        topo += f'<text x="{cx[i]}" y="{cy[i]-14}" text-anchor="middle" fill="{r["color"]}" font-size="13" font-family="monospace" font-weight="bold">{r["name"]}</text>'
        topo += f'<text x="{cx[i]}" y="{cy[i]+2}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{r["role"]}</text>'
        topo += f'<text x="{cx[i]}" y="{cy[i]+16}" text-anchor="middle" fill="#f1f5f9" font-size="11" font-family="monospace">{r["health"]}%</text>'
        lag_str = f'lag {r["lag"]}m' if r["lag"] else f'{r["load"]} req/hr'
        topo += f'<text x="{cx[i]}" y="{cy[i]+30}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{lag_str}</text>'
    svg_topo = f'<svg width="{tw}" height="{th}">{topo}</svg>'

    # --- RTO/RPO bar chart SVG ---
    bw, bh = 700, 240
    bar_group_w = 140
    bar_w = 40
    max_rto = 50
    chart_h = 160
    y_base = 190
    bars = f'<rect width="{bw}" height="{bh}" rx="8" fill="#0f172a"/>'
    bars += f'<text x="{bw//2}" y="20" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">RTO (seconds) by Failover Scenario</text>'
    for i, sc in enumerate(SCENARIOS):
        gx = 40 + i * bar_group_w
        rto_h = int(chart_h * sc["rto"] / max_rto)
        bars += f'<rect x="{gx}" y="{y_base - rto_h}" width="{bar_w}" height="{rto_h}" rx="3" fill="#C74634"/>'
        bars += f'<text x="{gx + bar_w//2}" y="{y_base - rto_h - 5}" text-anchor="middle" fill="#f1f5f9" font-size="11" font-family="monospace">{sc["rto"]}s</text>'
        label = sc["name"].replace("_", "\n")
        bars += f'<text x="{gx + bar_w//2}" y="{y_base + 16}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{sc["name"].split("_")[0]}</text>'
    bars += f'<line x1="30" y1="{y_base}" x2="{bw-20}" y2="{y_base}" stroke="#334155" stroke-width="1"/>'
    svg_bars = f'<svg width="{bw}" height="{bh}">{bars}</svg>'

    # --- Drill table rows ---
    drill_rows = ""
    for d in DRILLS:
        color = "#22c55e" if d["result"] == "PASSED" else "#ef4444"
        drill_rows += f'<tr><td>{d["date"]}</td><td style="color:{color}">{d["result"]}</td><td>{d["actual_rto"]}s</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>Multi-Region Failover v2</title>
<style>body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:monospace;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:18px 0 8px}}
.stats{{display:flex;gap:20px;margin:16px 0;flex-wrap:wrap}}.stat{{background:#1e293b;border-radius:8px;padding:12px 18px}}
.stat .val{{font-size:20px;font-weight:bold;color:#38bdf8}}.stat .lbl{{font-size:11px;color:#94a3b8}}
table{{border-collapse:collapse;margin-top:8px}}td,th{{padding:8px 18px;border:1px solid #334155;font-size:13px}}
th{{background:#1e293b;color:#94a3b8}}
</style></head><body>
<h1>Multi-Region Failover v2</h1>
<p style="color:#94a3b8;font-size:13px">Automated failover management across 3 OCI regions — Port {PORT}</p>
<div class="stats">
  <div class="stat"><div class="val">15s</div><div class="lbl">Automated Failover RTO</div></div>
  <div class="stat"><div class="val">0s</div><div class="lbl">RPO (sync replication)</div></div>
  <div class="stat"><div class="val">3/3</div><div class="lbl">Drills PASSED</div></div>
  <div class="stat"><div class="val">99.97%</div><div class="lbl">Uptime Target</div></div>
</div>
<h2>Region Topology</h2>{svg_topo}
<h2>RTO by Scenario</h2>{svg_bars}
<h2>Failover Drill History</h2>
<table><tr><th>Date</th><th>Result</th><th>Actual RTO</th></tr>{drill_rows}</table>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Region Failover v2")
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
