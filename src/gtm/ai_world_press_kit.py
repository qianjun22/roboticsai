"""AI World Press Kit — media press release, fact sheet, demo video, and media inquiry service."""

import json
import os
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10191
SERVICE_NAME = "ai_world_press_kit"

_KEY_FACTS = {
    "success_rate_pct": 85,
    "cost_reduction_factor": 9.6,
    "inference_latency_ms": 235,
    "design_partners": 3,
    "platform": "NVIDIA-native",
    "event": "AI World 2026"
}

_MEDIA_TARGETS = [
    {"outlet": "The Robot Report", "tier": 1, "reach_k": 120},
    {"outlet": "IEEE Spectrum",    "tier": 1, "reach_k": 430},
    {"outlet": "TechCrunch",       "tier": 2, "reach_k": 9800},
    {"outlet": "VentureBeat",      "tier": 2, "reach_k": 3200},
    {"outlet": "NVIDIA Blog",      "tier": 1, "reach_k": 2100},
]

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI World Press Kit</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .cards { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem 1.75rem; min-width: 160px; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
    .card .note { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; font-size: 1rem; margin-bottom: 1rem; }
    .endpoints { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .endpoints h2 { color: #C74634; font-size: 1rem; margin-bottom: 0.75rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.4rem 0; border-bottom: 1px solid #0f172a; }
    .ep:last-child { border-bottom: none; }
    .method { border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.75rem; font-weight: 700; font-family: monospace; }
    .get  { background: #0f172a; color: #38bdf8; }
    .post { background: #0f172a; color: #C74634; }
    .path { font-family: monospace; font-size: 0.85rem; color: #e2e8f0; }
    .desc { font-size: 0.8rem; color: #64748b; margin-left: auto; }
  </style>
</head>
<body>
  <h1>AI World Press Kit</h1>
  <p class="subtitle">OCI Robot Cloud — AI World 2026 Media Package &nbsp;|&nbsp; Port {PORT}</p>

  <div class="cards">
    <div class="card">
      <div class="label">Success Rate</div>
      <div class="value">85%</div>
      <div class="note">Closed-loop eval</div>
    </div>
    <div class="card">
      <div class="label">Cost Reduction</div>
      <div class="value">9.6x</div>
      <div class="note">vs. on-prem GPU cluster</div>
    </div>
    <div class="card">
      <div class="label">Latency</div>
      <div class="value">235ms</div>
      <div class="note">End-to-end inference</div>
    </div>
    <div class="card">
      <div class="label">Design Partners</div>
      <div class="value">3</div>
      <div class="note">Active customers</div>
    </div>
    <div class="card">
      <div class="label">Platform</div>
      <div class="value" style="font-size:1.1rem;padding-top:0.3rem;">NVIDIA-native</div>
      <div class="note">GR00T + Isaac Sim</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Media Target Tiers — Estimated Reach (thousands)</h2>
    <svg viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;">
      <!-- Y axis -->
      <line x1="110" y1="10" x2="110" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- X axis -->
      <line x1="110" y1="160" x2="540" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="100" y="15"  text-anchor="end" fill="#64748b" font-size="9">10000k</text>
      <text x="100" y="57"  text-anchor="end" fill="#64748b" font-size="9">7500k</text>
      <text x="100" y="107" text-anchor="end" fill="#64748b" font-size="9">5000k</text>
      <text x="100" y="157" text-anchor="end" fill="#64748b" font-size="9">0</text>
      <!-- Grid -->
      <line x1="110" y1="13"  x2="540" y2="13"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="110" y1="55"  x2="540" y2="55"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="110" y1="107" x2="540" y2="107" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
      <!-- The Robot Report: 120k / 10000 * 150 = 1.8px (min 4) -->
      <rect x="120" y="156" width="50" height="4"  fill="#C74634" rx="2"/>
      <text x="145" y="153" text-anchor="middle" fill="#C74634" font-size="9" font-weight="bold">120k</text>
      <text x="145" y="175" text-anchor="middle" fill="#94a3b8" font-size="8">Robot Report</text>
      <!-- IEEE Spectrum: 430k / 10000 * 150 = 6.5px -->
      <rect x="195" y="153" width="50" height="7"  fill="#38bdf8" rx="2"/>
      <text x="220" y="150" text-anchor="middle" fill="#38bdf8" font-size="9" font-weight="bold">430k</text>
      <text x="220" y="175" text-anchor="middle" fill="#94a3b8" font-size="8">IEEE Spectrum</text>
      <!-- TechCrunch: 9800k / 10000 * 150 = 147px -->
      <rect x="270" y="13" width="50" height="147" fill="#C74634" rx="2"/>
      <text x="295" y="10" text-anchor="middle" fill="#C74634" font-size="9" font-weight="bold">9800k</text>
      <text x="295" y="175" text-anchor="middle" fill="#94a3b8" font-size="8">TechCrunch</text>
      <!-- VentureBeat: 3200k / 10000 * 150 = 48px -->
      <rect x="345" y="112" width="50" height="48" fill="#38bdf8" rx="2"/>
      <text x="370" y="109" text-anchor="middle" fill="#38bdf8" font-size="9" font-weight="bold">3200k</text>
      <text x="370" y="175" text-anchor="middle" fill="#94a3b8" font-size="8">VentureBeat</text>
      <!-- NVIDIA Blog: 2100k / 10000 * 150 = 31.5px -->
      <rect x="420" y="128" width="50" height="32" fill="#C74634" rx="2" opacity="0.85"/>
      <text x="445" y="125" text-anchor="middle" fill="#C74634" font-size="9" font-weight="bold">2100k</text>
      <text x="445" y="175" text-anchor="middle" fill="#94a3b8" font-size="8">NVIDIA Blog</text>
      <!-- Legend -->
      <rect x="115" y="190" width="12" height="10" fill="#C74634" rx="2"/>
      <text x="131" y="199" fill="#94a3b8" font-size="9">Tier 1</text>
      <rect x="185" y="190" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="201" y="199" fill="#94a3b8" font-size="9">Tier 2</text>
    </svg>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="ep"><span class="method get">GET</span><span class="path">/health</span><span class="desc">Service health</span></div>
    <div class="ep"><span class="method get">GET</span><span class="path">/press/ai_world_kit</span><span class="desc">Full press kit bundle</span></div>
    <div class="ep"><span class="method post">POST</span><span class="path">/press/generate_release</span><span class="desc">Generate press release draft</span></div>
    <div class="ep"><span class="method get">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_HTML)

    @app.get("/press/ai_world_kit")
    async def press_ai_world_kit():
        return JSONResponse({
            "kit_version": "1.0.0",
            "event": _KEY_FACTS["event"],
            "key_facts": _KEY_FACTS,
            "media_targets": _MEDIA_TARGETS,
            "assets": [
                {"type": "press_release",  "status": "draft",    "filename": "oci_robot_cloud_press_release.docx"},
                {"type": "fact_sheet",     "status": "draft",    "filename": "oci_robot_cloud_fact_sheet.pdf"},
                {"type": "demo_video",     "status": "ready",    "filename": "oci_robot_cloud_demo.mp4"},
                {"type": "logo_pack",      "status": "ready",    "filename": "oci_robot_cloud_logos.zip"},
            ],
            "media_contact": "press@oracle.com",
            "embargo_until": None,
            "generated_at": datetime.utcnow().isoformat()
        })

    class _GenerateReleaseRequest(BaseModel):
        outlet: str = "general"
        angle: str = "product_launch"
        word_limit: int = 400

    @app.post("/press/generate_release")
    async def generate_release(req: _GenerateReleaseRequest):
        headline = (
            f"Oracle Cloud Infrastructure Launches OCI Robot Cloud at AI World 2026, "
            f"Delivering {_KEY_FACTS['success_rate_pct']}% Task Success Rate at "
            f"{_KEY_FACTS['cost_reduction_factor']}x Lower Cost"
        )
        return JSONResponse({
            "outlet": req.outlet,
            "angle": req.angle,
            "headline": headline,
            "subheadline": (
                "NVIDIA-native GR00T fine-tuning platform enables enterprise robot AI with "
                f"{_KEY_FACTS['inference_latency_ms']}ms inference latency"
            ),
            "body_preview": (
                "[DRAFT] OCI Robot Cloud brings enterprise-grade robot policy training and inference "
                "to the cloud, empowering {design_partners} design partners to deploy embodied AI "
                "in production. Built on NVIDIA GR00T and Isaac Sim, the platform delivers {sr}% "
                "closed-loop success rates at {cost}x lower cost than on-premise GPU clusters."
            ).format(
                design_partners=_KEY_FACTS["design_partners"],
                sr=_KEY_FACTS["success_rate_pct"],
                cost=_KEY_FACTS["cost_reduction_factor"]
            ),
            "word_count_estimate": min(req.word_limit, 400),
            "status": "draft",
            "generated_at": datetime.utcnow().isoformat()
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
            elif self.path in ("/", ""):
                body = _HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass

    def _run_stdlib():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} (stdlib fallback) listening on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib()
