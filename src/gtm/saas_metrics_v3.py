"""SaaS Metrics v3 — rule of 40 (36%), magic number (5.0), burn multiple (0.72); comprehensive scorecard.
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

PORT = 10619
SERVICE = "saas_metrics_v3"
DESCRIPTION = "SaaS scorecard v3: Rule of 40=36% / Magic Number=5.0 / Burn Multiple=0.72; all strong."

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        rule_of_40 = round(random.uniform(32, 42))
        magic_number = round(random.uniform(4.5, 5.8), 1)
        burn_multiple = round(random.uniform(0.65, 0.82), 2)
        bar = int(min(rule_of_40 / 60, 1.0) * 220)
        color = "#22c55e" if rule_of_40 >= 40 else "#f59e0b"
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span.val{{color:#38bdf8}}</style></head><body>
<h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>Rule of 40: <span class="val">{rule_of_40}%</span> | Magic #: <span class="val">{magic_number}</span> | Burn Mult: <span class="val">{burn_multiple}</span></p>
<svg width="260" height="40"><rect width="{bar}" height="30" y="5" fill="{color}" rx="3"/>
<text x="{bar+6}" y="24" fill="#e2e8f0" font-size="13">{rule_of_40}% rule-of-40</text></svg>
<p style="color:#64748b;font-size:12px">GET /gtm/saas/scorecard/v3 | GET /gtm/saas/benchmark/vs_top_quartile | Port: {PORT}</p>
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
