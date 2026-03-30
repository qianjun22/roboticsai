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

def build_html():
    regions = [
        ("Ashburn","PRIMARY","HEALTHY",91,226,99.97),
        ("Phoenix","SECONDARY","HEALTHY",62,241,99.94),
        ("Frankfurt","DR","HEALTHY",71,258,99.91),
    ]
    drills = [
        ("2026-02-14","Ashburn→Phoenix","15s","PASS","14.8s RTO"),
        ("2026-03-01","Ashburn→Frankfurt","15s","PASS","16.2s RTO"),
        ("2026-03-22","Full multi-region split","15s","PASS","18.1s avg"),
    ]

    # topology SVG
    sw, sh = 600, 220
    topo = f'<svg width="{sw}" height="{sh}">'
    positions = {"Ashburn":(120,110),"Phoenix":(300,60),"Frankfurt":(480,110)}
    color_map = {"HEALTHY":"#22c55e","DEGRADED":"#f59e0b","DOWN":"#ef4444"}
    # edges
    for (r1,p1), (r2,p2) in [(("Ashburn",positions["Ashburn"]),("Phoenix",positions["Phoenix"])),
                               (("Ashburn",positions["Ashburn"]),("Frankfurt",positions["Frankfurt"])),
                               (("Phoenix",positions["Phoenix"]),("Frankfurt",positions["Frankfurt"]))]:
        topo += f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="#475569" stroke-width="2" stroke-dasharray="6,3"/>'
    for name, role, health, util, lat, uptime in regions:
        x, y = positions[name]
        col = color_map[health]
        topo += f'<circle cx="{x}" cy="{y}" r="38" fill="#1e293b" stroke="{col}" stroke-width="3"/>'
        topo += f'<text x="{x}" y="{y-12}" text-anchor="middle" fill="{col}" font-size="11" font-weight="bold">{name}</text>'
        topo += f'<text x="{x}" y="{y+2}" text-anchor="middle" fill="#e2e8f0" font-size="10">{role}</text>'
        topo += f'<text x="{x}" y="{y+16}" text-anchor="middle" fill="#94a3b8" font-size="9">{lat}ms p50</text>'
        topo += f'<text x="{x}" y="{y+28}" text-anchor="middle" fill="#94a3b8" font-size="9">{uptime}%</text>'
    # failover arrows
    topo += '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#C74634"/></marker></defs>'
    topo += f'<line x1="162" y1="95" x2="265" y2="75" stroke="#C74634" stroke-width="2" marker-end="url(#arr)" opacity="0.6"/>'
    topo += f'<text x="210" y="72" fill="#C74634" font-size="9">failover</text>'
    topo += '</svg>'

    # RTO bar SVG
    scenarios = [("primary→secondary",14.8),("primary→DR",16.2),("split",18.1),("full_reset",52.3)]
    bar_svg = f'<svg width="500" height="130">'
    for i, (s, rto) in enumerate(scenarios):
        x = 140
        y = 10 + i * 27
        w = int(rto * 5)
        col = "#22c55e" if rto < 30 else "#f59e0b"
        bar_svg += f'<rect x="{x}" y="{y}" width="{w}" height="18" fill="{col}" rx="3"/>'
        bar_svg += f'<text x="135" y="{y+13}" text-anchor="end" fill="#e2e8f0" font-size="10">{s[:14]}</text>'
        bar_svg += f'<text x="{x+w+4}" y="{y+13}" fill="{col}" font-size="10">{rto}s</text>'
    bar_svg += '<line x1="215" y1="5" x2="215" y2="120" stroke="#38bdf8" stroke-dasharray="4,3" stroke-width="1"/>'
    bar_svg += '<text x="218" y="120" fill="#38bdf8" font-size="9">15s target</text>'
    bar_svg += '</svg>'

    drill_rows = "".join([f'<tr><td>{d}</td><td>{sc}</td><td>{t}</td>'
                          f'<td style="color:#22c55e">{res}</td><td>{notes}</td></tr>'
                          for d, sc, t, res, notes in drills])

    return f"""<!DOCTYPE html>
<html><head><title>Multi-Region Failover v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}}
.stat{{display:inline-block;margin:0 20px;text-align:center}}
.big{{font-size:28px;font-weight:bold;color:#C74634}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:6px 10px;border-bottom:1px solid #334155}}th{{color:#94a3b8}}
</style></head><body>
<h1>Multi-Region Failover v2 — Port {PORT}</h1>
<div class="card">
  <div class="stat"><div class="big">15s</div><div>RTO Target</div></div>
  <div class="stat"><div class="big" style="color:#22c55e">3/3</div><div>Drills Passed</div></div>
  <div class="stat"><div class="big" style="color:#22c55e">99.97%</div><div>Primary Uptime</div></div>
  <div class="stat"><div class="big" style="color:#38bdf8">0</div><div>Unplanned Failovers</div></div>
</div>
<div class="card">
  <h2>Region Topology</h2>
  {topo}
</div>
<div class="card">
  <h2>RTO by Scenario</h2>
  {bar_svg}
</div>
<div class="card">
  <h2>Failover Drill History</h2>
  <table><tr><th>Date</th><th>Scenario</th><th>Target</th><th>Result</th><th>Notes</th></tr>
  {drill_rows}
  </table>
</div>
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
