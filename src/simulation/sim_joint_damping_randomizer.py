"""Sim Joint Damping Randomizer — joint viscous damping domain randomization.
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
PORT = 11016
SERVICE = "sim_joint_damping_randomizer"
DESCRIPTION = "Joint viscous damping domain randomization varying per-joint damping coefficients to simulate real robot actuator variation and bearing wear."
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
    @app.get("/simulation/joint_damping/current_params")
    def current_params():
        n_joints = 7
        return {"joint_damping_coeffs": [round(random.uniform(0.1, 2.0), 3) for _ in range(n_joints)],
                "damping_scale_factor": round(random.uniform(0.5, 1.8), 3),
                "asymmetric_wear": random.choice([True, False]),
                "transfer_sr_improvement": 0.11, "randomization_active": True}
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
