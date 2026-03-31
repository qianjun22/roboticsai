"""
GTM funnel optimizer: identify and fix conversion bottlenecks with A/B experiments.
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

PORT = 10283
SERVICE = "gtm_funnel_optimizer"
DESCRIPTION = "Optimize GTM funnel stages — identify and fix conversion bottlenecks with A/B experiments"

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

    @app.get("/gtm/funnel/optimizer")
    def gtm_funnel_optimizer():
        return {
            "stage": "sql_to_pilot",
            "current_conversion": 0.255,
            "benchmark": 0.35,
            "bottleneck": "pilot_setup_friction",
            "experiment": {
                "hypothesis": "guided_onboarding",
                "expected_lift": 0.40
            },
            "arr_impact_k": 180
        }

    @app.post("/gtm/funnel/optimizer/run_experiment")
    def run_experiment():
        return {
            "experiment_id": f"exp_{int(time.time())}",
            "hypothesis": "guided_onboarding_lt_30min",
            "success_metric": "sql_to_pilot_rate",
            "duration_days": 30,
            "status": "launched"
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    import http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "service": SERVICE, "port": PORT}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    with socketserver.TCPServer(("", PORT), H) as s: s.serve_forever()
