"""Training Scheduler — FastAPI port 8419"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8419

def build_html():
    # Weekly calendar heatmap: 7 days × 24 hours GPU-hrs usage
    days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    hours = list(range(24))

    usage_matrix = []
    for d in range(7):
        row = []
        for h in range(24):
            if d < 5:  # weekdays
                if 9 <= h <= 18:
                    usage = 3.5 + random.uniform(-0.5,0.5)
                elif 0 <= h <= 6:
                    usage = 2.8 + random.uniform(-0.3,0.3)  # overnight training
                else:
                    usage = 1.5 + random.uniform(-0.3,0.3)
            else:  # weekend
                usage = 1.2 + random.uniform(-0.3,0.3)
            row.append(max(0, usage))
        usage_matrix.append(row)

    cw6, rh6 = 14, 22
    svg_cal = f'<svg width="{len(hours)*cw6+60}" height="{len(days)*rh6+50}" style="background:#0f172a">'
    for hi, h in enumerate(hours):
        if h % 6 == 0:
            svg_cal += f'<text x="{60+hi*cw6+cw6//2}" y="18" fill="#94a3b8" font-size="7" text-anchor="middle">{h:02d}h</text>'
    for di, day in enumerate(days):
        svg_cal += f'<text x="55" y="{30+di*rh6+14}" fill="#94a3b8" font-size="9" text-anchor="end">{day}</text>'
        for hi, val in enumerate(usage_matrix[di]):
            intensity = val/4.5; g = int(200*intensity); r = int(100*(1-intensity)); b = 150
            svg_cal += f'<rect x="{60+hi*cw6}" y="{24+di*rh6}" width="{cw6-1}" height="{rh6-1}" fill="rgb({r},{g},{b})" opacity="0.85"/>'
    svg_cal += '</svg>'

    # Priority queue
    jobs_q = [
        ("dagger_run10","HIGH",5000,0.28,"GPU4"),
        ("groot_v3_finetune","HIGH",3000,0.27,"GPU1"),
        ("hpo_search_3","MED",1000,0.0,"TBD"),
        ("eval_full_suite","MED",500,0.0,"TBD"),
        ("bc_v3_retrain","LOW",5000,0.0,"TBD"),
        ("lora_sweep_v2","LOW",2000,0.0,"TBD"),
        ("sim_render_batch2","MED",800,0.0,"Phoenix1"),
        ("ablation_study","LOW",3000,0.0,"TBD"),
    ]
    priority_colors = {"HIGH":"#C74634","MED":"#f59e0b","LOW":"#22c55e"}

    svg_q2 = '<svg width="420" height="260" style="background:#0f172a">'
    for ji, (name, pri, steps, prog, node) in enumerate(jobs_q):
        y = 15+ji*30; col = priority_colors[pri]
        # Priority badge
        svg_q2 += f'<rect x="10" y="{y}" width="35" height="20" fill="{col}" rx="3" opacity="0.8"/>'
        svg_q2 += f'<text x="27" y="{y+13}" fill="white" font-size="7" text-anchor="middle">{pri}</text>'
        # Job name
        svg_q2 += f'<text x="52" y="{y+13}" fill="#e2e8f0" font-size="9">{name}</text>'
        # Steps
        svg_q2 += f'<text x="185" y="{y+13}" fill="#94a3b8" font-size="8">{steps}st</text>'
        # Progress if running
        if prog > 0:
            pw2 = int(prog*80)
            svg_q2 += f'<rect x="225" y="{y+2}" width="80" height="14" fill="#1e293b" rx="2"/>'
            svg_q2 += f'<rect x="226" y="{y+3}" width="{pw2}" height="12" fill="{col}" rx="2" opacity="0.7"/>'
            svg_q2 += f'<text x="310" y="{y+13}" fill="#94a3b8" font-size="7">{prog:.0%}</text>'
        else:
            svg_q2 += f'<text x="225" y="{y+13}" fill="#475569" font-size="8">QUEUED</text>'
        # Node
        svg_q2 += f'<text x="380" y="{y+13}" fill="#94a3b8" font-size="7" text-anchor="end">{node}</text>'
    svg_q2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Training Scheduler \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Training Scheduler</h1>
<p style="color:#94a3b8">Port {PORT} | Weekly GPU calendar + priority job queue</p>
<div class="grid">
<div class="card"><h2>Weekly GPU Usage Calendar</h2>{svg_cal}
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Overnight slots (0-6h): DAgger long runs<br>Weekend gap: 18% idle opportunity<br>Optimal schedule saves 18% vs naive FCFS</div>
</div>
<div class="card"><h2>Priority Job Queue</h2>{svg_q2}
<div style="margin-top:8px">
<div class="stat">8</div><div class="label">Jobs in queue (2 running, 6 pending)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">HIGH: deadline-gated (DAgger run10 target Apr 14)<br>MED: weekly eval/HPO cadence<br>LOW: research/ablation (weekend slots)<br>Auto-schedule: fill idle GPU with queued LOW jobs</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Scheduler")
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
