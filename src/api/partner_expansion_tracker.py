"""Partner Expansion Tracker — FastAPI port 8581"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8581

def build_html():
    partners = [
        ("AutoMfg Co", "Pro→Enterprise", "$28,000", "negotiation", "#f59e0b"),
        ("FlexArm Inc", "+Bimanual Module", "$14,000", "proposal", "#38bdf8"),
        ("RoboLogic", "Add eval tier", "$8,400", "MQL", "#64748b"),
        ("MechVision", "Increase quota", "$6,200", "SQL", "#64748b"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8">{p[0]}</td>'
        f'<td style="padding:8px;color:#e2e8f0;font-size:11px">{p[1]}</td>'
        f'<td style="padding:8px;color:#22c55e">{p[2]}</td>'
        f'<td style="padding:8px;color:{p[4]}">{p[3]}</td>'
        f'</tr>'
        for p in partners
    )
    return f"""<!DOCTYPE html><html><head><title>Partner Expansion Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Partner Expansion Tracker</h1><span style="color:#64748b">Upsell pipeline | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">4</div><div class="lbl">Active Upsell Opportunities</div></div>
<div class="card"><div class="metric">$56.6K</div><div class="lbl">Pipeline ARR Value</div></div>
<div class="card"><div class="metric">127%</div><div class="lbl">NRR</div></div>
<div class="card"><div class="metric">Q2 2026</div><div class="lbl">Expected Close</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Partner</th><th>Expansion</th><th>ARR Value</th><th>Stage</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Expansion Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI: uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
