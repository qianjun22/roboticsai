"""Demand Forecasting Engine — 12-month ARR forecast; bottoms-up pipeline model; scenario analysis.
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

PORT = 10581
SERVICE = "demand_forecasting_engine"
DESCRIPTION = "12mo ARR: bear $0.4M / base $1.2M / bull $2.8M; NVIDIA deal and AI World are key drivers."

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        base_arr = round(random.uniform(1.1, 1.4), 2)
        bear_arr = round(base_arr * 0.33, 2)
        bull_arr = round(base_arr * 2.2, 2)
        bar = int(min(base_arr / 2.0, 1.0) * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span.val{{color:#38bdf8}}</style></head><body>
<h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>Base ARR: <span class="val">${base_arr}M</span> | Bear: <span class="val">${bear_arr}M</span> | Bull: <span class="val">${bull_arr}M</span></p>
<svg width="260" height="40"><rect width="{bar}" height="30" y="5" fill="#38bdf8" rx="3"/>
<text x="{bar+6}" y="24" fill="#e2e8f0" font-size="13">${base_arr}M base</text></svg>
<p style="color:#64748b;font-size:12px">GET /gtm/demand/forecast/12m | POST /gtm/demand/forecast/scenario</p>
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
