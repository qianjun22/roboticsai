"""Partner Integration Status — FastAPI port 8369"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8369

INTEGRATION_POINTS = ["API", "SDK", "Webhook", "Eval", "DAgger", "Billing", "Portal", "SLA"]

PARTNERS = {
    "PI Robotics":   [1,1,1,1,1,1,1,1],
    "Apptronik":     [1,1,1,1,1,1,0,1],
    "Covariant":     [1,1,0,1,1,1,1,0],
    "Machina Labs":  [1,0,0,0,0,1,0,0],
    "Wandelbots":    [1,1,0,1,0,1,0,0],
    "Figure AI":     [1,0,0,0,0,0,0,0],
}

def build_html():
    heatmap = ""
    for ri, (partner, status_row) in enumerate(PARTNERS.items()):
        for ci, status in enumerate(status_row):
            x = 140 + ci * 72
            y = 30 + ri * 35
            fill = "#22c55e" if status else "#1e293b"
            icon = "✓" if status else "·"
            icon_color = "#fff" if status else "#334155"
            heatmap += f'<rect x="{x}" y="{y}" width="68" height="28" fill="{fill}" opacity="0.75" rx="2"/>'
            heatmap += f'<text x="{x+34}" y="{y+18}" text-anchor="middle" fill="{icon_color}" font-size="12">{icon}</text>'
        pct = round(sum(status_row)/len(status_row)*100)
        color = "#22c55e" if pct >= 80 else "#f59e0b" if pct >= 50 else "#C74634"
        heatmap += f'<text x="130" y="{y+18}" text-anchor="end" fill="#94a3b8" font-size="9">{partner[:12]}</text>'
        heatmap += f'<text x="{140+len(INTEGRATION_POINTS)*72+5}" y="{y+18}" fill="{color}" font-size="9">{pct}%</text>'
    
    for ci, ip in enumerate(INTEGRATION_POINTS):
        x = 140 + ci * 72 + 34
        heatmap += f'<text x="{x}" y="22" text-anchor="middle" fill="#94a3b8" font-size="8">{ip}</text>'

    # Timeline SVG
    months = ["Mar", "Apr", "May", "Jun"]
    timeline_items = [
        ("PI full", 0, 0.5, "#22c55e"),
        ("Apptronik portal", 1, 0.5, "#f59e0b"),
        ("Covariant webhook+SLA", 1, 1, "#f59e0b"),
        ("Machina DPA→SDK→eval", 1.5, 2, "#C74634"),
        ("Wandelbots webhook+DAgger", 1.5, 1.5, "#f59e0b"),
        ("Figure AI full setup", 2, 3, "#38bdf8"),
    ]
    timeline_svg = ""
    for i, m in enumerate(months):
        timeline_svg += f'<text x="{50+i*110}" y="18" fill="#64748b" font-size="9">{m}</text>'
        timeline_svg += f'<line x1="{50+i*110}" y1="22" x2="{50+i*110}" y2="140" stroke="#334155" stroke-width="0.5"/>'
    for i, (name, start, dur, color) in enumerate(timeline_items):
        x = 50 + start * 110
        w = max(20, dur * 110)
        y = 28 + i * 20
        timeline_svg += f'<rect x="{x}" y="{y}" width="{w}" height="14" fill="{color}" opacity="0.7" rx="2"/>'
        timeline_svg += f'<text x="{x+4}" y="{y+10}" fill="#fff" font-size="7">{name}</text>'

    return f"""<!DOCTYPE html><html><head><title>Partner Integration Status — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Partner Integration Status</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">1</div><div style="font-size:0.75em;color:#94a3b8">Fully Integrated</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">3</div><div style="font-size:0.75em;color:#94a3b8">Partial</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">2</div><div style="font-size:0.75em;color:#94a3b8">Early Stage</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">DPA</div><div style="font-size:0.75em;color:#94a3b8">Blocking Machina</div></div>
</div>
<div class="card">
<h2>Integration Matrix</h2>
<svg viewBox="0 780 700 240" style="height:250px">
<rect width="700" height="780" fill="#0f172a" rx="4"/>
{heatmap}
</svg>
</div>
<div class="card">
<h2>Completion Timeline</h2>
<svg viewBox="0 0 500 150"><rect width="500" height="150" fill="#0f172a" rx="4"/>
{timeline_svg}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">
Critical path: <span style="color:#C74634">Machina Labs DPA</span> blocking SDK + eval + DAgger — CSM escalation needed.
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Integration Status")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"fully_integrated":1,"partial":3,"early_stage":2}

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
