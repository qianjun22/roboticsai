"""dagger_run126_planner.py — DAgger Run 126 Augmentation Planner (port 10042)

Data augmentation DAgger: 10x corrections via spatial jitter, lighting variation,
color shuffle, camera angle, and noise injection.
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10042
RUN_ID = "run126"
AUGMENTATION_FACTOR = 10
AUGMENTED_SR = 93.0
NO_AUGMENT_SR = 89.0
AUGMENTATION_TYPES = ["spatial_jitter", "lighting", "color_shuffle", "camera_angle", "noise"]

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run 126 Planner | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f8fafc; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem 1.5rem; }
    .kpi .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .kpi .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { font-size: 1rem; font-weight: 600; color: #38bdf8; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .aug-pill { display: inline-block; background: #0f172a; border: 1px solid #38bdf8; color: #38bdf8; border-radius: 999px; padding: 0.25rem 0.75rem; font-size: 0.8rem; margin: 0.2rem; }
    .cost-row { display: flex; gap: 2rem; margin-top: 0.5rem; }
    .cost-item { flex: 1; background: #0f172a; border-radius: 0.5rem; padding: 0.75rem 1rem; }
    .cost-item .clabel { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; }
    .cost-item .cval { font-size: 1.1rem; font-weight: 600; color: #f8fafc; margin-top: 0.2rem; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem 0 3rem; }
  </style>
</head>
<body>
  <header>
    <h1>DAgger Run 126 — Augmentation Planner</h1>
    <span class="badge">port 10042</span>
  </header>
  <main>
    <div class="kpi-row">
      <div class="kpi"><div class="label">Augmented SR</div><div class="value">93%</div><div class="sub">with 10x augmentation</div></div>
      <div class="kpi"><div class="label">No-Augment SR</div><div class="value">89%</div><div class="sub">baseline DAgger</div></div>
      <div class="kpi"><div class="label">Data Multiplier</div><div class="value">10x</div><div class="sub">corrections expanded</div></div>
      <div class="kpi"><div class="label">Augmentation Types</div><div class="value">5</div><div class="sub">spatial · lighting · color · angle · noise</div></div>
    </div>

    <div class="section">
      <h2>Success Rate Comparison</h2>
      <svg viewBox="0 0 480 200" width="100%" height="200">
        <!-- grid lines -->
        <line x1="60" y1="20" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
        <line x1="60" y1="160" x2="460" y2="160" stroke="#334155" stroke-width="1"/>
        <!-- y-axis labels -->
        <text x="52" y="164" fill="#64748b" font-size="11" text-anchor="end">0%</text>
        <text x="52" y="112" fill="#64748b" font-size="11" text-anchor="end">50%</text>
        <text x="52" y="60" fill="#64748b" font-size="11" text-anchor="end">100%</text>
        <line x1="60" y1="110" x2="460" y2="110" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
        <!-- No-Augment bar -->
        <rect x="110" y="17" width="100" height="143" fill="#334155" rx="4"/>
        <rect x="110" y="17" width="100" height="143" fill="none" stroke="#475569" stroke-width="1" rx="4"/>
        <!-- filled portion 89% = 143*0.89 = 127.27 -->
        <rect x="110" y="30" width="100" height="130" fill="#475569" rx="4"/>
        <text x="160" y="15" fill="#94a3b8" font-size="11" text-anchor="middle">89%</text>
        <text x="160" y="175" fill="#94a3b8" font-size="10" text-anchor="middle">No Augment</text>
        <!-- Augmented bar -->
        <rect x="270" y="17" width="100" height="143" fill="#334155" rx="4"/>
        <rect x="270" y="17" width="100" height="143" fill="none" stroke="#38bdf8" stroke-width="1" rx="4"/>
        <!-- filled 93% = 143*0.93 = 132.99 -->
        <rect x="270" y="24" width="100" height="136" fill="#38bdf8" rx="4"/>
        <text x="320" y="15" fill="#38bdf8" font-size="11" text-anchor="middle">93%</text>
        <text x="320" y="175" fill="#38bdf8" font-size="10" text-anchor="middle">Augmented 10x</text>
        <!-- delta label -->
        <text x="380" y="90" fill="#C74634" font-size="12" font-weight="600">+4 pp</text>
      </svg>
    </div>

    <div class="section">
      <h2>Augmentation Types</h2>
      <div>
        <span class="aug-pill">spatial_jitter</span>
        <span class="aug-pill">lighting</span>
        <span class="aug-pill">color_shuffle</span>
        <span class="aug-pill">camera_angle</span>
        <span class="aug-pill">noise</span>
      </div>
    </div>

    <div class="section">
      <h2>Cost Comparison</h2>
      <div class="cost-row">
        <div class="cost-item"><div class="clabel">Without Augmentation</div><div class="cval">10,000 human corrections</div></div>
        <div class="cost-item"><div class="clabel">With 10x Augmentation</div><div class="cval">1,000 human corrections</div></div>
        <div class="cost-item"><div class="clabel">Cost Reduction</div><div class="cval" style="color:#38bdf8">90% fewer labels</div></div>
      </div>
    </div>
  </main>
  <footer>OCI Robot Cloud &mdash; DAgger Run 126 Planner &mdash; port 10042</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Core logic helpers
# ---------------------------------------------------------------------------

def _compute_plan(corrections: int, augmentation_factor: int) -> dict[str, Any]:
    effective_samples = corrections * augmentation_factor
    # Simple sigmoid-inspired SR estimation
    base = NO_AUGMENT_SR + (AUGMENTED_SR - NO_AUGMENT_SR) * min(augmentation_factor / AUGMENTATION_FACTOR, 1.0)
    augmented_sr = round(min(base + random.uniform(-0.3, 0.3), 99.9), 1)
    return {
        "effective_samples": effective_samples,
        "augmented_sr": augmented_sr,
        "no_augment_sr": NO_AUGMENT_SR,
        "augmentation_types": AUGMENTATION_TYPES,
    }


def _status_payload() -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "augmentation_factor": AUGMENTATION_FACTOR,
        "augmented_sr": AUGMENTED_SR,
        "no_augment_sr": NO_AUGMENT_SR,
        "augmentation_types": AUGMENTATION_TYPES,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="DAgger Run 126 Planner",
        description="Data augmentation DAgger planner: 10x corrections via spatial jitter, lighting, color shuffle, camera angle, and noise injection.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "dagger_run126_planner", "port": PORT, "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.post("/dagger/run126/plan")
    async def plan(body: dict = None):
        if body is None:
            body = {}
        corrections = int(body.get("corrections", 1000))
        augmentation_factor = int(body.get("augmentation_factor", AUGMENTATION_FACTOR))
        return JSONResponse(_compute_plan(corrections, augmentation_factor))

    @app.get("/dagger/run126/status")
    async def status():
        return JSONResponse(_status_payload())


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logs
            pass

        def _send(self, code: int, content_type: str, body: str | bytes):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                body = json.dumps({"status": "ok", "service": "dagger_run126_planner", "port": PORT})
                self._send(200, "application/json", body)
            elif path == "/dagger/run126/status":
                self._send(200, "application/json", json.dumps(_status_payload()))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/dagger/run126/plan":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw or b"{}")
                self._send(200, "application/json", json.dumps(_compute_plan(
                    int(body.get("corrections", 1000)),
                    int(body.get("augmentation_factor", AUGMENTATION_FACTOR)),
                )))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

    def _serve_fallback():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[dagger_run126_planner] stdlib HTTPServer listening on port {PORT}")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve_fallback()
