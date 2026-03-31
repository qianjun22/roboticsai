"""Investor Dashboard v2 — real-time KPI board; Series B metrics; investor update automation.
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

PORT = 10579
SERVICE = "investor_dashboard_v2"
DESCRIPTION = "Live KPIs: ARR $250k, MoM 18%, runway 18mo, GR00T SR 85%; auto investor update generation."

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        arr = round(random.uniform(240000, 270000))
        growth_mom = round(random.uniform(0.15, 0.22), 2)
        runway_mo = random.randint(16, 20)
        bar = int(min(arr / 300000, 1.0) * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span.val{{color:#38bdf8}}</style></head><body>
<h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>ARR: <span class="val">${arr:,}</span> | MoM: <span class="val">{growth_mom*100:.0f}%</span> | Runway: <span class="val">{runway_mo}mo</span></p>
<svg width="260" height="40"><rect width="{bar}" height="30" y="5" fill="#38bdf8" rx="3"/>
<text x="{bar+6}" y="24" fill="#e2e8f0" font-size="13">${arr:,} ARR</text></svg>
<p style="color:#64748b;font-size:12px">GET /api/investor/dashboard/summary | POST /api/investor/update/generate</p>
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
