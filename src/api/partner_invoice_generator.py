"""Partner Invoice Generator — FastAPI port 8549"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8549

def build_html():
    line_items = [
        ("Inference API Calls", "847,200 calls", "$1,270"),
        ("Fine-tune GPU-hrs", "18.4 hrs × A100", "$920"),
        ("Support Tier", "Pro (monthly)", "$500"),
        ("Storage", "2.1TB × month", "$157"),
    ]
    rows = "".join(f'<tr><td style="padding:8px;color:#e2e8f0">{i[0]}</td><td style="padding:8px;color:#94a3b8">{i[1]}</td><td style="padding:8px;color:#38bdf8;text-align:right">{i[2]}</td></tr>' for i in line_items)
    return f"""<!DOCTYPE html><html><head><title>Partner Invoice Generator</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Partner Invoice Generator</h1><span style="color:#64748b">Monthly billing | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$2,847</div><div class="lbl">Avg Invoice</div></div>
<div class="card"><div class="metric">94%</div><div class="lbl">On-Time Payment</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">Disputes (Q1)</div></div>
<div class="card"><div class="metric">Net-30</div><div class="lbl">Payment Terms</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">INVOICE LINE ITEMS (RoboLogic — March 2026)</div>
<table><tr><th>Line Item</th><th>Quantity</th><th style="text-align:right">Amount</th></tr>
{rows}
<tr style="border-top:1px solid #334155"><td colspan="2" style="padding:8px;color:#64748b;font-weight:bold">TOTAL</td><td style="padding:8px;color:#22c55e;text-align:right;font-weight:bold">$2,847</td></tr>
</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Invoice Generator")
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
