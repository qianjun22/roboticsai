"""Fleet Upgrade Planner — FastAPI port 8364"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8364

def build_html():
    # Node comparison
    nodes = [
        ("Ashburn GPU1", "A100_80GB", 0.78, "PROD", "#22c55e"),
        ("Ashburn GPU4", "A100_80GB", 0.78, "PROD", "#22c55e"),
        ("Phoenix GPU1", "A100_40GB", 0.62, "EVAL", "#f59e0b"),
        ("Frankfurt GPU1", "A100_40GB", 0.71, "STG", "#38bdf8"),
    ]
    
    node_rows = ""
    for name, gpu, sr, role, color in nodes:
        upgrade_to = "H100_80GB" if gpu == "A100_80GB" else "A100_80GB"
        node_rows += f"""<tr>
<td style="padding:8px;color:#e2e8f0">{name}</td>
<td style="padding:8px;color:#94a3b8">{gpu}</td>
<td style="padding:8px;font-weight:bold;color:{color}">{sr}</td>
<td style="padding:8px"><span style="background:{color};color:#fff;padding:2px 6px;border-radius:3px;font-size:0.75em">{role}</span></td>
<td style="padding:8px;color:#38bdf8">{upgrade_to}</td>
</tr>"""

    # ROI comparison
    gpus_roi = [
        ("A100_40GB (current)", 0.62, 2.8, "#C74634"),
        ("A100_80GB", 0.78, 3.2, "#f59e0b"),
        ("H100_80GB (target)", 0.87, 6.1, "#22c55e"),
    ]
    roi_bars = ""
    for i, (name, sr, its, color) in enumerate(gpus_roi):
        y = 30 + i * 55
        sr_w = int(sr * 200)
        its_w = int(its * 28)
        roi_bars += f'<text x="10" y="{y+15}" fill="#94a3b8" font-size="10">{name}</text>'
        roi_bars += f'<rect x="200" y="{y}" width="{sr_w}" height="18" fill="{color}" opacity="0.6" rx="2"/>'
        roi_bars += f'<text x="{205+sr_w}" y="{y+13}" fill="{color}" font-size="9">SR={sr}</text>'
        roi_bars += f'<rect x="200" y="{y+22}" width="{its_w}" height="14" fill="{color}" opacity="0.4" rx="2"/>'
        roi_bars += f'<text x="{205+its_w}" y="{y+34}" fill="{color}" font-size="9">{its} it/s</text>'

    # Gantt upgrade timeline
    gantt_items = [
        ("Phoenix node1", 5, 3, "#f59e0b"),   # month offset, duration
        ("Frankfurt node1", 6, 2, "#38bdf8"),
        ("Add Ashburn H100", 8, 2, "#22c55e"),
    ]
    gantt_bars = ""
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    for i, month in enumerate(months):
        gantt_bars += f'<text x="{60+i*60}" y="20" fill="#64748b" font-size="9">{month}</text>'
        gantt_bars += f'<line x1="{60+i*60}" y1="25" x2="{60+i*60}" y2="130" stroke="#334155" stroke-width="0.5"/>'
    for i, (name, start, dur, color) in enumerate(gantt_items):
        x = 60 + (start-4)*60
        w = dur * 60
        y = 35 + i * 30
        gantt_bars += f'<rect x="{x}" y="{y}" width="{w}" height="20" fill="{color}" opacity="0.7" rx="3"/>'
        gantt_bars += f'<text x="{x+5}" y="{y+14}" fill="#fff" font-size="9">{name}</text>'
        gantt_bars += f'<text x="10" y="{y+14}" fill="#94a3b8" font-size="8">{name[:10]}</text>'

    return f"""<!DOCTYPE html><html><head><title>Fleet Upgrade Planner — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px;color:#64748b;text-align:left;border-bottom:1px solid #334155;font-size:0.8em}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Fleet Upgrade Planner</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">1</div><div style="font-size:0.75em;color:#94a3b8">Priority Upgrade</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">+0.16pp</div><div style="font-size:0.75em;color:#94a3b8">SR Lift (Phoenix)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">$1,200/mo</div><div style="font-size:0.75em;color:#94a3b8">Capacity Lift</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#94a3b8">Jun 2026</div><div style="font-size:0.75em;color:#94a3b8">First Upgrade</div></div>
</div>
<div class="card">
<h2>Current Fleet State</h2>
<table><thead><tr><th>Node</th><th>GPU</th><th>SR</th><th>Role</th><th>Upgrade To</th></tr></thead>
<tbody>{node_rows}</tbody></table>
</div>
<div class="grid">
<div class="card"><h2>GPU ROI Comparison</h2>
<svg viewBox="0 0 580 185"><rect width="580" height="185" fill="#0f172a" rx="4"/>
{roi_bars}
</svg></div>
<div class="card"><h2>Upgrade Timeline (Apr–Oct 2026)</h2>
<svg viewBox="0 0 490 140"><rect width="490" height="140" fill="#0f172a" rx="4"/>
{gantt_bars}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">Phoenix node1 first (SR bottleneck 0.62 → 0.78). H100 added pre-AI World Sep 2026.</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Upgrade Planner")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"priority_upgrade":"Phoenix_GPU1","capacity_lift_mo":1200}

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
