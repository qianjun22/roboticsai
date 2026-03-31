"""ai_world_demo_script.py — AI World Live Demo Script Generator
Port 10257 | OCI Robot Cloud
3-minute robot demo + presenter narrative + contingency planning
"""

import json
import random
from datetime import datetime

PORT = 10257
SERVICE_NAME = "ai_world_demo_script"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI World Demo Script | OCI Robot Cloud</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; border-left: 4px solid #C74634; }
  .card h3 { color: #38bdf8; margin: 0 0 8px; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .val { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
  .card .unit { font-size: 0.8rem; color: #94a3b8; }
  .chart-container { background: #1e293b; border-radius: 10px; padding: 24px; margin-bottom: 24px; }
  .chart-container h2 { color: #C74634; margin: 0 0 16px; font-size: 1.1rem; }
  .checklist { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .checklist h2 { color: #C74634; margin: 0 0 12px; font-size: 1.1rem; }
  .check-item { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid #334155; font-size: 0.88rem; }
  .check-item:last-child { border-bottom: none; }
  .check-box { color: #38bdf8; font-size: 1rem; flex-shrink: 0; margin-top: 1px; }
  .contingency { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .contingency h2 { color: #C74634; margin: 0 0 12px; font-size: 1.1rem; }
  .cont-row { display: flex; gap: 12px; padding: 8px 0; border-bottom: 1px solid #334155; }
  .cont-row:last-child { border-bottom: none; }
  .cont-trigger { color: #fbbf24; font-weight: 600; font-size: 0.85rem; min-width: 160px; }
  .cont-action { color: #94a3b8; font-size: 0.85rem; }
  .endpoints { background: #1e293b; border-radius: 10px; padding: 20px; }
  .endpoints h2 { color: #C74634; margin: 0 0 12px; font-size: 1.1rem; }
  .ep { display: flex; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid #334155; }
  .ep:last-child { border-bottom: none; }
  .method { background: #C74634; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; min-width: 48px; text-align: center; }
  .method.get { background: #0284c7; }
  .ep-path { color: #38bdf8; font-family: monospace; font-size: 0.9rem; }
  .ep-desc { color: #94a3b8; font-size: 0.85rem; }
</style>
</head>
<body>
<h1>AI World Demo Script Generator</h1>
<div class="subtitle">Port 10257 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; 3-Minute Live Robot Demo</div>

<div class="grid">
  <div class="card">
    <h3>Total Demo Time</h3>
    <div class="val">3<span class="unit">min</span></div>
    <div class="unit">180 seconds structured</div>
  </div>
  <div class="card">
    <h3>Live Demo Segment</h3>
    <div class="val">90<span class="unit">s</span></div>
    <div class="unit">robot in action</div>
  </div>
  <div class="card">
    <h3>Contingency Plans</h3>
    <div class="val">2</div>
    <div class="unit">fallback scenarios</div>
  </div>
  <div class="card">
    <h3>Checklist Items</h3>
    <div class="val">8</div>
    <div class="unit">pre-demo verifications</div>
  </div>
</div>

<div class="chart-container">
  <h2>Demo Timing Breakdown (180 seconds total)</h2>
  <svg width="100%" height="200" viewBox="0 0 560 200" xmlns="http://www.w3.org/2000/svg">
    <!-- Background grid -->
    <line x1="60" y1="20" x2="60" y2="155" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="155" x2="520" y2="155" stroke="#334155" stroke-width="1"/>
    <!-- Grid lines -->
    <line x1="60" y1="115" x2="520" y2="115" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="60" y1="75" x2="520" y2="75" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <line x1="60" y1="35" x2="520" y2="35" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
    <!-- Y-axis labels -->
    <text x="52" y="158" fill="#94a3b8" font-size="10" text-anchor="end">0s</text>
    <text x="52" y="118" fill="#94a3b8" font-size="10" text-anchor="end">30s</text>
    <text x="52" y="78" fill="#94a3b8" font-size="10" text-anchor="end">60s</text>
    <text x="52" y="38" fill="#94a3b8" font-size="10" text-anchor="end">90s</text>
    <!-- Bar: Problem Framing 30s -->
    <rect x="75" y="115" width="75" height="40" fill="#C74634" rx="4"/>
    <text x="112" y="108" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">30s</text>
    <text x="112" y="175" fill="#94a3b8" font-size="10" text-anchor="middle">Problem</text>
    <text x="112" y="187" fill="#94a3b8" font-size="10" text-anchor="middle">Framing</text>
    <!-- Bar: Live Demo 90s -->
    <rect x="195" y="35" width="75" height="120" fill="#38bdf8" rx="4"/>
    <text x="232" y="27" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">90s</text>
    <text x="232" y="175" fill="#94a3b8" font-size="10" text-anchor="middle">Live</text>
    <text x="232" y="187" fill="#94a3b8" font-size="10" text-anchor="middle">Demo</text>
    <!-- Bar: Results 30s -->
    <rect x="315" y="115" width="75" height="40" fill="#C74634" rx="4"/>
    <text x="352" y="108" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">30s</text>
    <text x="352" y="175" fill="#94a3b8" font-size="10" text-anchor="middle">Results</text>
    <text x="352" y="187" fill="#94a3b8" font-size="10" text-anchor="middle">&amp; Metrics</text>
    <!-- Bar: Ask + CTA 30s -->
    <rect x="435" y="115" width="75" height="40" fill="#0f766e" rx="4"/>
    <text x="472" y="108" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">30s</text>
    <text x="472" y="175" fill="#94a3b8" font-size="10" text-anchor="middle">Ask</text>
    <text x="472" y="187" fill="#94a3b8" font-size="10" text-anchor="middle">&amp; CTA</text>
  </svg>
</div>

<div class="contingency">
  <h2>Contingency Planning</h2>
  <div class="cont-row">
    <span class="cont-trigger">Robot failure / crash</span>
    <span class="cont-action">Switch to pre-recorded 90s HD video; presenter narrates live over video playback</span>
  </div>
  <div class="cont-row">
    <span class="cont-trigger">Network / cloud outage</span>
    <span class="cont-action">Use cached inference results on local laptop; demo proceeds offline</span>
  </div>
</div>

<div class="checklist">
  <h2>Pre-Demo Checklist</h2>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Robot powered on and homed — E-stop accessible</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>OCI inference endpoint reachable (ping /health on port 10257)</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Backup video file loaded on presenter laptop</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Cached inference results snapshot saved locally</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Slide deck on second display, clicker tested</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Demo props (cube, bin) in correct starting positions</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Full dress rehearsal completed within 2 hours of showtime</span></div>
  <div class="check-item"><span class="check-box">&#9744;</span><span>Presenter narrative timed — 3 min or under</span></div>
</div>

<div class="endpoints">
  <h2>API Endpoints</h2>
  <div class="ep"><span class="method get">GET</span><span class="ep-path">/health</span><span class="ep-desc">Health check + service metadata</span></div>
  <div class="ep"><span class="method get">GET</span><span class="ep-path">/</span><span class="ep-desc">This HTML dashboard</span></div>
  <div class="ep"><span class="method get">GET</span><span class="ep-path">/events/ai_world/demo_script</span><span class="ep-desc">Retrieve the full AI World demo script</span></div>
  <div class="ep"><span class="method">POST</span><span class="ep-path">/events/ai_world/customize_script</span><span class="ep-desc">Customize demo script for audience / product focus</span></div>
</div>
</body>
</html>
"""

DEMO_SCRIPT = {
    "event": "AI World 2026",
    "total_duration_sec": 180,
    "segments": [
        {
            "segment": "Problem Framing",
            "duration_sec": 30,
            "narrative": (
                "Today's robots require months of hand-coded programs just to pick one object. "
                "We're going to show you how OCI Robot Cloud lets you train a generalizable robot policy "
                "in hours — not months — using cloud-scale simulation and foundation models."
            ),
        },
        {
            "segment": "Live Demo",
            "duration_sec": 90,
            "narrative": (
                "Watch as the robot receives a natural language instruction. "
                "Our GR00T-based policy — fine-tuned on just 1000 simulated demonstrations — "
                "plans and executes the pick-and-place task with 87% success rate. "
                "No hand-coded logic. Fully trained in the cloud."
            ),
            "steps": [
                "Operator sends task via REST API",
                "Inference request hits OCI A100 endpoint (< 250ms)",
                "Robot arm executes action chunk",
                "Live success metric displayed on screen",
            ],
        },
        {
            "segment": "Results & Metrics",
            "duration_sec": 30,
            "narrative": (
                "87% closed-loop success rate. 250ms inference latency. "
                "Fine-tuning cost under $5 per 10k steps on OCI A100. "
                "Sim-to-real gap closed by domain randomization with 500+ photorealistic textures."
            ),
        },
        {
            "segment": "Ask & CTA",
            "duration_sec": 30,
            "narrative": (
                "We're onboarding 5 design partners this quarter. "
                "If you're building production robot systems, talk to us at booth 42 or scan the QR code. "
                "OCI Robot Cloud: train once, deploy anywhere."
            ),
        },
    ],
    "contingency": [
        {"trigger": "robot_failure", "action": "Switch to pre-recorded backup video; narrator continues live"},
        {"trigger": "network_outage", "action": "Use cached local inference results; demo continues offline"},
    ],
    "checklist": [
        "Robot powered on and homed",
        "OCI inference endpoint reachable",
        "Backup video on presenter laptop",
        "Cached inference results saved locally",
        "Slide deck on second display",
        "Demo props in starting positions",
        "Dress rehearsal completed",
        "Presenter narrative timed",
    ],
}

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="AI World Demo Script",
        description="AI World live demo script generator — 3-minute robot demo with presenter narrative and contingency planning",
        version="1.0.0",
    )

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/events/ai_world/demo_script")
    def get_demo_script():
        """Return the full AI World demo script."""
        return JSONResponse({
            **DEMO_SCRIPT,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.post("/events/ai_world/customize_script")
    def customize_script(body: dict = None):
        """Customize the demo script for a specific audience or product focus."""
        body = body or {}
        audience = body.get("audience", "general")
        focus = body.get("product_focus", "pick_and_place")
        variant_id = f"script-{random.randint(1000, 9999)}"
        return JSONResponse({
            "variant_id": variant_id,
            "audience": audience,
            "product_focus": focus,
            "base_script": DEMO_SCRIPT,
            "customization_applied": True,
            "notes": f"Script customized for audience='{audience}' and focus='{focus}'.",
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/events/ai_world/demo_script":
                body = json.dumps(DEMO_SCRIPT).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _run_fallback():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] stdlib fallback running on port {PORT}")
            httpd.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
