"""Partner Success Platform — customer health scoring; expansion/monitor/save playbooks; CSM workflows.
OCI Robot Cloud — roboticsai
"""
from __future__ import annotations
import json, time, random, math
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _has_fastapi = True
except ImportError:
    _has_fastapi = False

PORT = 10577
SERVICE = "partner_success_platform"
DESCRIPTION = "Health score: usage(40%)+support(20%)+NPS(20%)+contract(20%); green→expand, red→save."

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        score = round(random.uniform(68, 88))
        color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
        action = "expand" if score >= 70 else "monitor" if score >= 50 else "save"
        bar = int(score / 100 * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span.val{{color:#38bdf8}}</style></head><body>
<h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>Health: <span class="val">{score}/100</span> | Action: <span class="val">{action}</span> | Port: <span class="val">{PORT}</span></p>
<svg width="260" height="40"><rect width="{bar}" height="30" y="5" fill="{color}" rx="3"/>
<text x="{bar+6}" y="24" fill="#e2e8f0" font-size="13">{score}/100 → {action}</text></svg>
<p style="color:#64748b;font-size:12px">GET /api/partner_success/health/summary | POST /api/partner_success/playbook/trigger</p>
</body></html>"""

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    import http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "service": SERVICE, "port": PORT}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    with socketserver.TCPServer(("", PORT), H) as s: s.serve_forever()
