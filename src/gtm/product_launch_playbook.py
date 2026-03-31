"""Product Launch Playbook — AI World 12-week countdown, owned+earned+paid channels.

Port 10203
"""

import json
from datetime import datetime

PORT = 10203
SERVICE_NAME = "product_launch_playbook"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Product Launch Playbook</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-bottom: 1rem; font-size: 1.1rem; }
    .metric { display: inline-block; margin-right: 2rem; margin-bottom: 0.5rem; }
    .metric .val { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; }
    .tag { display: inline-block; background: #0f172a; border: 1px solid #38bdf8;
           color: #38bdf8; border-radius: 4px; padding: 0.2rem 0.6rem;
           font-size: 0.75rem; margin: 0.2rem; }
    .phase { border-left: 3px solid #C74634; padding-left: 1rem; margin-bottom: 0.8rem; }
    .phase .pw { color: #C74634; font-weight: bold; font-size: 0.9rem; }
    .phase .pd { color: #94a3b8; font-size: 0.82rem; margin-top: 0.2rem; }
    .endpoints { font-size: 0.85rem; }
    .endpoints a { color: #38bdf8; text-decoration: none; display: block; margin: 0.3rem 0; }
    .endpoints a:hover { color: #C74634; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>Product Launch Playbook</h1>
  <p class="subtitle">AI World — 12-week countdown, owned + earned + paid channels</p>

  <div class="card">
    <h2>Launch Metrics Targets</h2>
    <svg width="520" height="200" viewBox="0 0 520 200">
      <!-- background -->
      <rect width="520" height="200" fill="#0f172a" rx="8"/>
      <!-- axes -->
      <line x1="60" y1="160" x2="500" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="20" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- gridlines -->
      <line x1="60" y1="120" x2="500" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="80" x2="500" y2="80" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="40" x2="500" y2="40" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- y-axis label -->
      <text x="52" y="164" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="52" y="44" fill="#64748b" font-size="10" text-anchor="end">100%</text>
      <!-- bar: press pickups 5 → scaled to 10% of chart height -->
      <rect x="90" y="148" width="55" height="12" fill="#C74634" rx="3"/>
      <text x="117" y="143" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">5</text>
      <text x="117" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Press</text>
      <text x="117" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Pickups</text>
      <!-- bar: social impressions 50K → 70% height -->
      <rect x="190" y="48" width="55" height="112" fill="#38bdf8" rx="3"/>
      <text x="217" y="42" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">50K</text>
      <text x="217" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Social</text>
      <text x="217" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Impressions</text>
      <!-- bar: MQLs 80 → 85% height -->
      <rect x="290" y="36" width="55" height="124" fill="#C74634" rx="3"/>
      <text x="317" y="30" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">80</text>
      <text x="317" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">MQLs</text>
      <text x="317" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Target</text>
      <!-- bar: demo requests 20 → 25% height -->
      <rect x="390" y="120" width="55" height="40" fill="#38bdf8" rx="3"/>
      <text x="417" y="114" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">20</text>
      <text x="417" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Demo</text>
      <text x="417" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Requests</text>
    </svg>
  </div>

  <div class="card">
    <h2>Launch Phases</h2>
    <div class="phase">
      <div class="pw">T-12 weeks — Messaging</div>
      <div class="pd">Finalize positioning, value props, competitive differentiation; align internal stakeholders; create content brief</div>
    </div>
    <div class="phase">
      <div class="pw">T-8 weeks — Media Outreach</div>
      <div class="pd">Brief analysts (Gartner, IDC); pitch top-tier tech press under embargo; seed influencer program; launch paid social campaign</div>
    </div>
    <div class="phase">
      <div class="pw">T-4 weeks — Embargo Lift</div>
      <div class="pd">Lift embargo for early-access press; publish blog + solution brief; activate partner co-marketing; SDR outreach sequences live</div>
    </div>
    <div class="phase">
      <div class="pw">T-0 — Launch Day</div>
      <div class="pd">Press release wire; exec keynote / webinar; social storm across owned channels; sales plays activated; demo environment live</div>
    </div>
    <div class="phase" style="border-color:#38bdf8">
      <div class="pw" style="color:#38bdf8">T+4 weeks — Post-Launch Activation</div>
      <div class="pd">Retarget engaged leads; case study pipeline; community AMA; measure MQLs vs target; iterate messaging based on feedback</div>
    </div>
  </div>

  <div class="card">
    <h2>Channel Mix</h2>
    <div class="metric"><div class="val">12</div><div class="lbl">Week Countdown</div></div>
    <div class="metric"><div class="val">3</div><div class="lbl">Channel Types (O+E+P)</div></div>
    <div class="metric"><div class="val">80</div><div class="lbl">MQL Target</div></div>
    <div class="metric"><div class="val">50K</div><div class="lbl">Social Impressions</div></div>
  </div>

  <div class="card">
    <h2>Tags</h2>
    <span class="tag">ai-world</span>
    <span class="tag">product-launch</span>
    <span class="tag">12-week-countdown</span>
    <span class="tag">owned-earned-paid</span>
    <span class="tag">gtm</span>
    <span class="tag">mql</span>
    <span class="tag">embargo</span>
    <span class="tag">post-launch</span>
  </div>

  <div class="card endpoints">
    <h2>Endpoints</h2>
    <a href="/health">/health — service health check</a>
    <a href="/launch/ai_world/playbook">/launch/ai_world/playbook — full 12-week playbook</a>
    <a href="/launch/ai_world/readiness">/launch/ai_world/readiness — launch readiness checklist</a>
  </div>
</body>
</html>
"""


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_HTML)

    @app.get("/launch/ai_world/playbook")
    async def launch_ai_world_playbook():
        """Return mock 12-week AI World launch playbook."""
        return JSONResponse({
            "launch": "ai_world",
            "total_weeks": 12,
            "channels": ["owned", "earned", "paid"],
            "phases": [
                {"phase": "T-12", "name": "Messaging",
                 "activities": ["positioning", "value_props", "competitive_diff", "content_brief"]},
                {"phase": "T-8", "name": "Media Outreach",
                 "activities": ["analyst_briefs", "press_embargo", "influencer_seed", "paid_social"]},
                {"phase": "T-4", "name": "Embargo Lift",
                 "activities": ["press_release", "blog_post", "partner_comarketing", "sdr_sequences"]},
                {"phase": "T-0", "name": "Launch Day",
                 "activities": ["wire_release", "exec_keynote", "social_storm", "sales_plays"]},
                {"phase": "T+4", "name": "Post-Launch Activation",
                 "activities": ["retargeting", "case_studies", "community_ama", "mql_review"]}
            ],
            "metrics_targets": {
                "press_pickups": 5,
                "social_impressions": 50000,
                "mqls": 80,
                "demo_requests": 20
            },
            "generated_at": datetime.utcnow().isoformat()
        })

    @app.get("/launch/ai_world/readiness")
    async def launch_ai_world_readiness():
        """Return mock launch readiness checklist."""
        return JSONResponse({
            "launch": "ai_world",
            "overall_readiness_pct": 78,
            "checklist": [
                {"item": "messaging_finalized", "complete": True},
                {"item": "press_kit_ready", "complete": True},
                {"item": "demo_environment_live", "complete": True},
                {"item": "analyst_briefs_sent", "complete": True},
                {"item": "embargo_agreements_signed", "complete": False},
                {"item": "paid_campaigns_configured", "complete": False},
                {"item": "sdr_sequences_active", "complete": False},
                {"item": "exec_keynote_rehearsed", "complete": False}
            ],
            "port": PORT,
            "checked_at": datetime.utcnow().isoformat()
        })

else:
    # Fallback: stdlib http.server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def _send(self, code, ctype, body):
            enc = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(enc)))
            self.end_headers()
            self.wfile.write(enc)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
            elif self.path in ("/", ""):
                self._send(200, "text/html", _HTML)
            elif self.path == "/launch/ai_world/playbook":
                self._send(200, "application/json",
                           json.dumps({"launch": "ai_world", "total_weeks": 12,
                                       "metrics_targets": {"press_pickups": 5,
                                                           "social_impressions": 50000,
                                                           "mqls": 80,
                                                           "demo_requests": 20}}))
            elif self.path == "/launch/ai_world/readiness":
                self._send(200, "application/json",
                           json.dumps({"launch": "ai_world", "overall_readiness_pct": 78}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback http.server listening on port {PORT}")
        server.serve_forever()
