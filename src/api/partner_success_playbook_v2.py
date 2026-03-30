"""Partner Success Playbook V2 — FastAPI port 8905"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8905

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    stages = [
        ("Onboard",  "< 14d",  "< 7d",  "Env setup, API keys, sandbox access",       "Health < 40"),
        ("Activate", "< 14d",  "< 10d", "First inference call, latency baseline",     "Health < 50"),
        ("First Eval","< 21d", "< 18d", "Closed-loop eval 20-episode suite",          "SR < 0.30"),
        ("DAgger",   "< 45d",  "< 38d", "First DAgger fine-tune cycle launched",      "No DAgger by day 40"),
        ("Expand",   "< 90d",  "< 75d", "2nd robot type or 2nd site deployed",        "Health < 60 at 60d"),
        ("Retain",   "< 180d", "< 150d","QBR completed, renewal intent confirmed",    "NPS < 7"),
        ("Renew",    "< 365d", "< 330d","Contract renewed or upsell closed",          "Renewal risk flag"),
    ]
    stage_rows = "".join(
        f'<tr><td style="color:#38bdf8"><strong>{s}</strong></td><td>{sla}</td><td style="color:#22c55e">{p50}</td>'
        f'<td style="color:#94a3b8">{milestone}</td><td style="color:#ef4444">{trigger}</td></tr>'
        for s, sla, p50, milestone, trigger in stages
    )
    triggers = [
        ("Health ≤ 40", "Auto-assign CSM EBR", "< 4h",  "Slack + email"),
        ("Health ≤ 55", "CSM check-in task",    "< 24h", "Salesforce task"),
        ("No eval 21d", "Eval nudge sequence",  "Day 22","Email + in-app"),
        ("SR drop >10%","Incident review open", "< 2h",  "PagerDuty"),
        ("NPS < 7",     "Exec sponsor alert",   "< 1h",  "Slack + email"),
        ("Day 330",     "Renewal workflow",     "Day 330","Salesforce opp"),
    ]
    trigger_rows = "".join(
        f'<tr><td style="color:#fbbf24">{cond}</td><td>{action}</td><td style="color:#38bdf8">{timing}</td><td style="color:#94a3b8">{channel}</td></tr>'
        for cond, action, timing, channel in triggers
    )
    return f"""<!DOCTYPE html><html><head><title>Partner Success Playbook V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}</style></head>
<body><h1>Partner Success Playbook V2</h1>
<div class="card"><h2>Lifecycle Playbook Coverage Matrix</h2>
<table><tr><th>Stage</th><th>SLA Target</th><th>P50 Actual</th><th>Milestone Definition</th><th>CSM Trigger</th></tr>
{stage_rows}</table></div>
<div class="card"><h2>Automated CSM Trigger Table</h2>
<table><tr><th>Condition</th><th>Action</th><th>Response Time</th><th>Channel</th></tr>
{trigger_rows}</table></div>
<div class="card"><h2>Partner Health Index</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Success Playbook V2")
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
