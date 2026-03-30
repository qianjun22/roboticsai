"""Pilot Contract Tracker — FastAPI port 8382"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8382

PARTNERS = {
    "PI Robotics":   {"nda": "done", "dpa": "done", "pilot": "active", "msa": "done",   "arr": 1247},
    "Apptronik":     {"nda": "done", "dpa": "done", "pilot": "active", "msa": "pending", "arr": 623},
    "Covariant":     {"nda": "done", "dpa": "done", "pilot": "active", "msa": "pending", "arr": 847},
    "Machina Labs":  {"nda": "done", "dpa": "blocked", "pilot": "pending", "msa": "pending", "arr": 0},
    "Wandelbots":    {"nda": "done", "dpa": "in_progress", "pilot": "pending", "msa": "pending", "arr": 0},
    "Figure AI":     {"nda": "in_progress", "dpa": "pending", "pilot": "pending", "msa": "pending", "arr": 0},
}

STAGE_COLORS = {
    "done": "#22c55e", "active": "#22c55e", "in_progress": "#f59e0b",
    "pending": "#334155", "blocked": "#C74634"
}

def build_html():
    # Timeline SVG
    stages = ["NDA", "DPA", "Pilot", "MSA"]
    stage_keys = ["nda", "dpa", "pilot", "msa"]
    
    timeline_cells = ""
    for si, stage in enumerate(stages):
        timeline_cells += f'<text x="{100+si*120+60}" y="22" text-anchor="middle" fill="#94a3b8" font-size="10">{stage}</text>'
    
    for pi, (partner, contract) in enumerate(PARTNERS.items()):
        y = 35 + pi * 40
        timeline_cells += f'<text x="90" y="{y+16}" text-anchor="end" fill="#94a3b8" font-size="9">{partner[:14]}</text>'
        for si, key in enumerate(stage_keys):
            status = contract[key]
            color = STAGE_COLORS[status]
            x = 100 + si * 120
            timeline_cells += f'<rect x="{x+5}" y="{y}" width="110" height="28" fill="{color}" opacity="0.7" rx="3"/>'
            timeline_cells += f'<text x="{x+60}" y="{y+18}" text-anchor="middle" fill="#fff" font-size="8">{status}</text>'
        arr = contract["arr"]
        arr_color = "#22c55e" if arr > 0 else "#334155"
        timeline_cells += f'<text x="590" y="{y+18}" fill="{arr_color}" font-size="9">${arr}/mo</text>'

    # ARR waterfall
    months = ["Now", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    arr_proj = [2927, 2927, 4174, 6721, 9268, 13568, 19000]
    max_arr = max(arr_proj)
    waterfall_pts = " ".join(f"{40+i*76},{190-v/max_arr*160}" for i,v in enumerate(arr_proj))
    
    waterfall_bars = ""
    for i, (month, arr) in enumerate(zip(months, arr_proj)):
        x = 30 + i * 76
        h = int(arr / max_arr * 160)
        color = "#22c55e" if arr > 5000 else "#f59e0b" if arr > 2000 else "#38bdf8"
        waterfall_bars += f'<rect x="{x}" y="{190-h}" width="56" height="{h}" fill="{color}" opacity="0.75" rx="2"/>'
        waterfall_bars += f'<text x="{x+28}" y="{185-h}" text-anchor="middle" fill="{color}" font-size="8">${arr//1000}k</text>'
        waterfall_bars += f'<text x="{x+28}" y="203" text-anchor="middle" fill="#64748b" font-size="8">{month}</text>'

    contract_score = round(sum(1 for p in PARTNERS.values() for k,v in p.items() if k != "arr" and v in ["done","active"]) / (len(PARTNERS)*4) * 100)

    return f"""<!DOCTYPE html><html><head><title>Pilot Contract Tracker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Pilot Contract Tracker</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">3</div><div style="font-size:0.75em;color:#94a3b8">Active Pilots</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">1</div><div style="font-size:0.75em;color:#94a3b8">Blocked</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">$2,717/mo</div><div style="font-size:0.75em;color:#94a3b8">Active ARR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">{contract_score}%</div><div style="font-size:0.75em;color:#94a3b8">Contract coverage</div></div>
</div>
<div class="card">
<h2>Contract Stage Status (6 partners)</h2>
<svg viewBox="0 650 640 260" style="height:270px">
<rect width="640" height="650" fill="#0f172a" rx="4"/>
{timeline_cells}
<text x="595" y="22" fill="#64748b" font-size="9">ARR/mo</text>
</svg>
</div>
<div class="card">
<h2>ARR Forecast (milestone-gated)</h2>
<svg viewBox="0 0 590 220"><rect width="590" height="220" fill="#0f172a" rx="4"/>
<line x1="20" y1="190" x2="580" y2="190" stroke="#334155" stroke-width="1"/>
{waterfall_bars}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">
Critical path: Machina DPA (BLOCKED) → pilot → +$1,247/mo. Escalate to legal by Apr 15.
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Pilot Contract Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"active_pilots":3,"blocked":1,"active_arr_mo":2717}

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
