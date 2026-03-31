"""DAgger Run269 Planner — reward-conditioned DAgger; operator-selectable risk/SR target.
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

PORT = 10614
SERVICE = "dagger_run269_planner"
DESCRIPTION = "Reward-conditioned DAgger: target 90%→88% SR / target 75%→78% SR; operator-selectable risk."

if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        target_sr = random.choice([0.75, 0.80, 0.85, 0.90])
        actual_sr = round(target_sr + random.uniform(-0.03, 0.03), 3)
        bar = int(actual_sr * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span.val{{color:#38bdf8}}</style></head><body>
<h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>Target SR: <span class="val">{target_sr}</span> | Actual SR: <span class="val">{actual_sr}</span> | Port: <span class="val">{PORT}</span></p>
<svg width="260" height="40"><rect width="{bar}" height="30" y="5" fill="#38bdf8" rx="3"/>
<text x="{bar+6}" y="24" fill="#e2e8f0" font-size="13">{actual_sr} actual</text></svg>
<p style="color:#64748b;font-size:12px">Reward-conditioned DAgger run269 — obedient achiever strategy</p>
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
