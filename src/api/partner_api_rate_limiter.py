"""Partner API Rate Limiter — FastAPI port 8563"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8563

def build_html():
    partners = [
        ("RoboLogic", "Basic", 1000, 680, "#22c55e"),
        ("AutoMfg Co", "Pro", 10000, 7200, "#22c55e"),
        ("FlexArm Inc", "Enterprise", 99999, 12400, "#22c55e"),
        ("BotWorks", "Pro", 10000, 9400, "#f59e0b"),
        ("MechVision", "Basic", 1000, 520, "#22c55e"),
    ]
    bars = "".join(
        f'<rect x="180" y="{15+i*48}" width="{int(p[3]/p[2]*320)}" height="32" fill="{p[4]}" rx="3"/>'
        f'<text x="175" y="{35+i*48}" fill="#94a3b8" font-size="11" text-anchor="end">{p[0]}</text>'
        f'<text x="{185+int(p[3]/p[2]*320)}" y="{35+i*48}" fill="#e2e8f0" font-size="11">{p[3]:,}/{p[2]:,} ({int(p[3]/p[2]*100)}%)</text>'
        for i,p in enumerate(partners)
    )
    return f"""<!DOCTYPE html><html><head><title>Partner API Rate Limiter</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Partner API Rate Limiter</h1><span style="color:#64748b">Quota utilization | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">5</div><div class="lbl">Active Partners</div></div>
<div class="card"><div class="metric">94%</div><div class="lbl">BotWorks Quota Used</div></div>
<div class="card"><div class="metric">85%</div><div class="lbl">Auto-Upgrade Trigger</div></div>
<div class="card"><div class="metric">2×</div><div class="lbl">Burst Allowance (5min)</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">DAILY QUOTA UTILIZATION (calls used / limit)</div>
<svg width="100%" height="{15+len(partners)*48+10}" viewBox="0 600 {15+len(partners)*48+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner API Rate Limiter")
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
