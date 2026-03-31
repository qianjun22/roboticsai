"""Sales comp model v2 — $140K base, $240K OTE, $600K quota, 5.6mo payback
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

PORT = 10319
SERVICE = "sales_comp_model_v2"
DESCRIPTION = "Sales comp model v2 — $140K base, $240K OTE, $600K quota, 5.6mo payback"

if FastAPI:
    app = FastAPI(title=SERVICE, description=DESCRIPTION)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE, "port": PORT, "ts": time.time()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        val = round(random.uniform(0.75, 0.98), 3)
        bar = int(val * 220)
        return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:2rem}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.metric{{background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem 0}}</style></head>
<body><h1>{SERVICE}</h1><p style="color:#94a3b8">{DESCRIPTION}</p>
<div class="metric"><h2>Primary Metric</h2>
<svg width="260" height="32"><rect width="240" height="28" rx="4" fill="#1e293b"/>
<rect width="{bar}" height="28" rx="4" fill="#C74634"/>
<text x="8" y="20" fill="#fff" font-size="13">{val}</text></svg></div>
<div class="metric"><h2>Service Info</h2><p>Port: {PORT} | Status: operational</p></div>
</body></html>"""

    @app.get("/sales/comp_v2/model")
    def sales_comp_v2_model():
        return {
            "rep_id": "AE_001",
            "base_k": 140,
            "ote_k": 240,
            "quota_k": 600,
            "ramp_schedule": {"q1": 0.5, "q2": 0.75, "q3": 1.0, "q4": 1.0},
            "ytd_attainment": 0.0
        }

    @app.get("/sales/comp_v2/cost_analysis")
    def sales_comp_v2_cost_analysis():
        return {
            "headcount": 1,
            "total_sales_cost_k": 280,
            "revenue_per_head_k": 600,
            "payback_mo": 5.6,
            "spiffs": {"ai_world_logo_k": 5, "nvidia_referral_close_k": 3}
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    import http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status":"ok","service":SERVICE,"port":PORT}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(body)
    with socketserver.TCPServer(("",PORT),H) as s: s.serve_forever()
