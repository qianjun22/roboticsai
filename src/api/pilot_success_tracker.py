"""Pilot Success Tracker — FastAPI port 8443"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8443

def build_html():
    pilots = ["PI_Robotics","Apptronik","1X_Tech","Machina_Labs","Wandelbots"]
    criteria = ["SR_threshold","Latency_ok","Uptime_ok","Demo_quality","ROI_met"]
    status_matrix = [
        [2,2,2,2,2],  # PI: all met -> GRADUATED
        [2,2,2,1,1],  # Apptronik: SR and latency met, ROI pending
        [1,2,2,1,0],  # 1X: SR borderline
        [0,0,3,0,0],  # Machina: blocked (DPA)
        [1,2,1,1,0],  # Wandelbots: early
    ]
    # 0=not started, 1=in_progress, 2=met, 3=blocked
    s_colors = {0:"#1e293b",1:"#f59e0b",2:"#22c55e",3:"#C74634"}
    s_labels = {0:"\u2014",1:"\u25b6",2:"\u2713",3:"\u26a0"}

    decisions = ["GRADUATED","ON_TRACK","AT_RISK","BLOCKED","IN_PROGRESS"]
    dec_colors = ["#22c55e","#38bdf8","#f59e0b","#C74634","#94a3b8"]

    cw15, rh15 = 72, 28
    svg_matrix2 = f'<svg width="{len(criteria)*cw15+130}" height="{len(pilots)*rh15+60}" style="background:#0f172a">'
    for ci, crit in enumerate(criteria):
        svg_matrix2 += f'<text x="{130+ci*cw15+36}" y="18" fill="#38bdf8" font-size="8" text-anchor="middle">{crit[:8]}</text>'
    for pi, (pilot, decision, dcol) in enumerate(zip(pilots, decisions, dec_colors)):
        svg_matrix2 += f'<text x="125" y="{36+pi*rh15+16}" fill="#94a3b8" font-size="9" text-anchor="end">{pilot[:10]}</text>'
        for ci, st in enumerate(status_matrix[pi]):
            col = s_colors[st]; lab = s_labels[st]
            svg_matrix2 += f'<rect x="{130+ci*cw15+2}" y="{30+pi*rh15+2}" width="{cw15-4}" height="{rh15-4}" fill="{col}" rx="3" opacity="0.85"/>'
            svg_matrix2 += f'<text x="{130+ci*cw15+36}" y="{30+pi*rh15+18}" fill="white" font-size="12" text-anchor="middle">{lab}</text>'
        # Decision badge
        svg_matrix2 += f'<rect x="{130+len(criteria)*cw15+5}" y="{30+pi*rh15+2}" width="70" height="{rh15-4}" fill="{dcol}" rx="3" opacity="0.7"/>'
        svg_matrix2 += f'<text x="{130+len(criteria)*cw15+40}" y="{30+pi*rh15+16}" fill="white" font-size="7" text-anchor="middle">{decision}</text>'
    svg_matrix2 += '</svg>'

    # 60-day progress timeline per pilot
    svg_prog = '<svg width="420" height="220" style="background:#0f172a">'
    pilot_colors = ["#22c55e","#38bdf8","#f59e0b","#C74634","#a78bfa"]
    for pi, (pilot, pcol) in enumerate(zip(pilots, pilot_colors)):
        y_base = 10+pi*40
        # Days 0-60
        completion = sum(1 for s in status_matrix[pi] if s==2)/len(criteria)
        svg_prog += f'<text x="90" y="{y_base+20}" fill="#94a3b8" font-size="8" text-anchor="end">{pilot[:10]}</text>'
        if status_matrix[pi][0] == 3:  # blocked
            svg_prog += f'<rect x="95" y="{y_base+8}" width="160" height="18" fill="#C74634" opacity="0.3" rx="3"/>'
            svg_prog += f'<text x="175" y="{y_base+20}" fill="#C74634" font-size="8">BLOCKED (DPA pending)</text>'
            continue
        # Progress bar
        w_prog = int(completion*280)
        svg_prog += f'<rect x="95" y="{y_base+8}" width="280" height="18" fill="#1e293b" rx="3"/>'
        svg_prog += f'<rect x="96" y="{y_base+9}" width="{w_prog}" height="16" fill="{pcol}" rx="2" opacity="0.8"/>'
        svg_prog += f'<text x="{97+w_prog}" y="{y_base+20}" fill="white" font-size="8">{completion:.0%}</text>'
    svg_prog += '<text x="250" y="215" fill="#94a3b8" font-size="9" text-anchor="middle">Pilot Criteria Completion</text>'
    svg_prog += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Pilot Success Tracker \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Pilot Success Tracker</h1>
<p style="color:#94a3b8">Port {PORT} | 5-pilot success criteria matrix + Go/No-Go decisions</p>
<div class="card" style="margin-bottom:16px"><h2>Success Criteria Matrix + Decision</h2>{svg_matrix2}</div>
<div class="grid">
<div class="card"><h2>Completion Progress</h2>{svg_prog}</div>
<div class="card">
<div class="stat" style="color:#22c55e">PI Robotics</div><div class="label">GRADUATED \u2014 all 5 criteria met, moving to production contract</div>
<div class="stat" style="color:#C74634;margin-top:12px">Machina BLOCKED</div><div class="label">DPA sign-off needed by Apr 15 \u2192 $1,247/mo ARR at risk</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">PI: renewal negotiation in progress ($2,100/mo Enterprise)<br>Apptronik: ROI tracking week 8 of 12 (on track)<br>1X: SR borderline 0.64 vs 0.65 target \u2192 needs DAgger<br>Wandelbots: 4 weeks into 12-week pilot, normal pace</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Pilot Success Tracker")
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
