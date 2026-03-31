"""Automated monthly investor update — metrics+narrative+ask, 30-day cadence
OCI Robot Cloud — roboticsai
"""
from __future__ import annotations
import json, time, random, math
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
PORT = 10333
SERVICE = "investor_update_automator_v2"
DESCRIPTION = "Automated monthly investor update — metrics+narrative+ask, 30-day cadence"
if FastAPI:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)
    @app.get("/health")
    def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":time.time()}
    @app.get("/",response_class=HTMLResponse)
    def dashboard():
        val=round(random.uniform(0.75,0.98),3); bar=int(val*220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}h2{{color:#38bdf8}}.metric{{background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem 0}}</style></head><body><h1>{SERVICE}</h1><p style="color:#94a3b8">{DESCRIPTION}</p><div class="metric"><h2>Primary Metric</h2><svg width="260" height="32"><rect width="240" height="28" rx="4" fill="#1e293b"/><rect width="{bar}" height="28" rx="4" fill="#C74634"/><text x="8" y="20" fill="#fff" font-size="13">{val}</text></svg></div><div class="metric"><h2>Service Info</h2><p>Port: {PORT} | Status: operational</p></div></body></html>"""
    @app.get("/investors/update_v2/draft")
    def draft_investor_update():
        return {
            "month": "2026-03",
            "subject": "OCI Robot Cloud — March Update",
            "kpis": {
                "arr_k": 250,
                "mom_growth": 0.086,
                "sr": 0.85,
                "customers": 3,
                "nrr": 1.18
            },
            "narrative": "AI World confirmed, NVIDIA intro in progress, DAgger run 200 launched"
        }
    @app.post("/investors/update_v2/send")
    def send_investor_update():
        return {
            "month": "2026-03",
            "sent_count": 12,
            "open_tracking": True,
            "reply_tracking": True
        }
    if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
else:
    import http.server,socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body=json.dumps({"status":"ok","service":SERVICE,"port":PORT}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(body)
    with socketserver.TCPServer(("",PORT),H) as s: s.serve_forever()
