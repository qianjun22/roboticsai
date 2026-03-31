"""Q3 2026 board deck — $457K ARR, AI World 500 scans, Series A in process
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
PORT = 10337
SERVICE = "board_deck_q3"
DESCRIPTION = "Q3 2026 board deck — $457K ARR, AI World 500 scans, Series A in process"
if FastAPI:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)
    @app.get("/health")
    def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":time.time()}
    @app.get("/",response_class=HTMLResponse)
    def dashboard():
        val=round(random.uniform(0.75,0.98),3); bar=int(val*220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}h2{{color:#38bdf8}}.metric{{background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem 0}}</style></head><body><h1>{SERVICE}</h1><p style="color:#94a3b8">{DESCRIPTION}</p><div class="metric"><h2>Primary Metric</h2><svg width="260" height="32"><rect width="240" height="28" rx="4" fill="#1e293b"/><rect width="{bar}" height="28" rx="4" fill="#C74634"/><text x="8" y="20" fill="#fff" font-size="13">{val}</text></svg></div><div class="metric"><h2>Service Info</h2><p>Port: {PORT} | Status: operational</p></div></body></html>"""
    @app.get("/gtm/board_deck/q3")
    def board_deck_q3():
        return {
            "sections": ["traction", "ai_world_results", "series_a_update", "asks"],
            "arr_k": 457,
            "nrr": 1.22,
            "customers": 5,
            "series_a_status": "8_meetings_3_term_sheets_expected"
        }
    @app.get("/gtm/board_deck/q3/metrics")
    def board_deck_q3_metrics():
        return {
            "arr_k": 457,
            "vs_target": 1.06,
            "vs_q2": 1.82,
            "ai_world_badge_scans": 500,
            "ai_world_pilots": 3
        }
    if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
else:
    import http.server,socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body=json.dumps({"status":"ok","service":SERVICE,"port":PORT}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(body)
    with socketserver.TCPServer(("",PORT),H) as s: s.serve_forever()
