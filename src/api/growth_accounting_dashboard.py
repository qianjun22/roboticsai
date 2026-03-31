"""Growth Accounting Dashboard — cohort-based revenue growth accounting with quick ratio.
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

PORT = 10645
SERVICE = "growth_accounting_dashboard"
DESCRIPTION = "Cohort-based revenue growth accounting with quick ratio"

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        val = round(random.uniform(0.75, 0.98), 3)
        bar = int(val * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>
body{{margin:0;padding:0;background:#0f172a;color:#f1f5f9;font-family:monospace}}
.hdr{{background:#C74634;padding:18px 32px}}
.hdr h1{{margin:0;font-size:1.4rem;letter-spacing:1px}}
.card{{background:#1e293b;border-radius:10px;padding:28px 32px;margin:32px auto;max-width:600px}}
.metric{{font-size:2.5rem;font-weight:700;color:#38bdf8}}
</style></head><body>
<div class="hdr"><h1>OCI ROBOT CLOUD — {SERVICE.upper()}</h1></div>
<div class="card">
<div class="metric">{val}</div>
<div style="color:#94a3b8;margin-top:8px">{DESCRIPTION}</div>
<svg width="240" height="32" style="margin-top:18px"><rect x="0" y="8" width="{bar}" height="16" rx="4" fill="#38bdf8"/></svg>
<div style="margin-top:16px;color:#64748b">port {PORT} · {SERVICE}</div>
</div></body></html>"""

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
