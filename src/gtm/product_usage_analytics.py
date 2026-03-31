"""Product Usage Analytics — feature adoption, session depth, and PLG conversion signals.
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
PORT = 11005
SERVICE = "product_usage_analytics"
DESCRIPTION = "Product usage analytics platform tracking feature adoption, session depth, API call patterns, and PLG conversion signals for OCI Robot Cloud."
if _has_fastapi:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)
    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        val = round(random.uniform(0.75, 0.98), 3)
        bar = int(val * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:2rem}}
h1{{color:#C74634}}span{{color:#38bdf8}}</style></head>
<body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p>
<p>Port: <span>{PORT}</span> | Status: <span>online</span></p>
<svg width='240' height='30'><rect width='220' height='20' fill='#1e293b' rx='4'/>
<rect width='{bar}' height='20' fill='#C74634' rx='4'/></svg>
<p><span>{val}</span> efficiency</p></body></html>"""
    @app.get("/api/product_usage/weekly_summary")
    def weekly_summary():
        return {"wau": random.randint(28, 45), "api_calls_7d": random.randint(12000, 18000),
                "top_features": ["GR00T inference", "fine-tune API", "eval runner", "data collection"],
                "avg_session_min": 34.2, "power_users": random.randint(4, 8),
                "plg_signals_this_week": random.randint(3, 7), "upgrade_intents": random.randint(1, 3)}
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    import http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "service": SERVICE, "port": PORT}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    with socketserver.TCPServer(("", PORT), H) as s: s.serve_forever()
