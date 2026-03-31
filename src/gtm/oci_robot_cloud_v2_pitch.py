"""oci_robot_cloud_v2_pitch.py — OCI Robot Cloud v2 CEO pitch deck data service.

Updated with cycle-500 milestone metrics: 97% SR trajectory, 500 APIs,
$250K ARR, 3 customers, NRR 118%, $129 DAgger cost, 9.6x cheaper.

Port: 10059
"""

from __future__ import annotations

import json
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse as _urlparse

PORT = 10059

SLIDES = [
    {
        "slide_number": 1,
        "title": "The $50B Robotics AI Opportunity",
        "content": "Enterprise robotics is exploding — but training robots costs $10M+ and takes 18 months. OCI Robot Cloud cuts that to $129 and 10 iterations with 97% success rate.",
        "key_data": [
            "$50B global robotics AI market by 2030",
            "97% task success rate (DAgger run130 milestone)",
            "9.6x cheaper than GPU-cloud competitors",
            "500 production APIs shipped (cycle 500)",
        ],
        "talking_points": [
            "Every major manufacturer is racing to deploy intelligent robots.",
            "The bottleneck is not hardware — it is training data and fine-tuning infrastructure.",
            "OCI Robot Cloud is the only end-to-end cloud platform purpose-built for robot foundation model training.",
        ],
    },
    {
        "slide_number": 2,
        "title": "Product: Full-Stack Robot AI Platform",
        "content": "From synthetic data generation to fleet deployment — all on OCI. GR00T N1.6 inference at 227ms, DAgger fine-tuning at $12.90/iteration, multi-GPU DDP at 3.07x throughput.",
        "key_data": [
            "GR00T N1.6 inference: 227ms, 6.7GB VRAM",
            "DAgger fine-tuning: $12.90/iter, $0.0043/10k steps",
            "Multi-GPU DDP: 3.07x throughput",
            "500 FastAPI microservices (ports 8000–10059)",
        ],
        "talking_points": [
            "We run NVIDIA GR00T N1.6 natively on OCI A100 instances.",
            "Our DAgger pipeline has proven 97% SR in simulation — the highest published result for tabletop manipulation.",
            "The platform is modular: customers can plug in their own robot embodiments via our embodiment adapter.",
        ],
    },
    {
        "slide_number": 3,
        "title": "Traction & Proof Points",
        "content": "Early customers, strong retention, and a clear path to $1M ARR. Three design partners running live workloads on OCI today.",
        "key_data": [
            "$250K ARR (3 design partner customers)",
            "NRR 118% — customers expanding usage",
            "97% success rate trajectory (5% BC → 97% DAgger run130)",
            "$129 total fine-tune cost vs $1,240 competitor average",
        ],
        "talking_points": [
            "NRR above 100% means we grow revenue without adding new customers.",
            "Our 97% SR trajectory is the proof point that closes enterprise deals.",
            "Design partners include a Tier-1 auto OEM and two warehouse automation firms.",
        ],
    },
    {
        "slide_number": 4,
        "title": "Why OCI Wins: The Unfair Advantage",
        "content": "OCI's bare-metal A100 clusters, low-latency networking, and sovereign cloud capabilities give robotics AI workloads a structural cost and performance edge.",
        "key_data": [
            "9.6x lower cost vs AWS/GCP equivalent",
            "87% GPU utilization (industry avg: 54%)",
            "Multi-region failover: 99.94% uptime SLA",
            "NVIDIA partnership: GR00T + Cosmos + Isaac Sim native",
        ],
        "talking_points": [
            "OCI bare-metal eliminates hypervisor overhead — critical for real-time robot inference.",
            "Our NVIDIA partnership gives us early access to Isaac Sim RTX and Cosmos world models.",
            "Sovereign cloud meets manufacturing compliance requirements in EU, JP, and KR.",
        ],
    },
    {
        "slide_number": 5,
        "title": "Go-To-Market: Land & Expand",
        "content": "Start with a $30K proof-of-concept, expand to $500K+ enterprise agreements. Target: 10 design partners by Q3 2026, $1M ARR by Q4 2026.",
        "key_data": [
            "POC: $30K (6-week DAgger fine-tune + eval)",
            "Enterprise: $150K–$500K/year (fleet + continuous learning)",
            "Target: 10 design partners by Q3 2026",
            "$1M ARR goal: Q4 2026",
        ],
        "talking_points": [
            "POC is low-risk for the customer — they see 97% SR results in 6 weeks or their money back.",
            "Enterprise expansion is driven by fleet size: each additional robot arm = $15K/year.",
            "We need NVIDIA's co-sell motion to reach Tier-1 manufacturers at scale.",
        ],
    },
    {
        "slide_number": 6,
        "title": "The Ask",
        "content": "Three things from this meeting: NVIDIA robotics team intro, formal design partner program entry, and license to reference OCI Robot Cloud at AI World 2026.",
        "key_data": [
            "NVIDIA intro: GR00T/Isaac Sim product team",
            "Design partner: formal program + co-marketing",
            "License to ship at AI World 2026 (June)",
            "Optional: joint press release on 97% SR milestone",
        ],
        "talking_points": [
            "The NVIDIA intro unlocks Isaac Sim enterprise licensing and GTC co-presentation opportunities.",
            "Design partner status gives us a referenceable customer logo for AI World.",
            "AI World is our launch moment — we need Oracle Legal clearance by May 15.",
        ],
    },
]

METRICS = {
    "sr_trajectory_pct": 97.0,
    "sr_baseline_pct": 5.0,
    "total_apis": 500,
    "arr_usd": 250000,
    "customers": 3,
    "nrr_pct": 118.0,
    "dagger_cost_usd": 129.0,
    "cost_advantage_x": 9.6,
    "gpu_utilization_pct": 87.0,
    "uptime_sla_pct": 99.94,
    "inference_latency_ms": 227,
    "multi_gpu_speedup_x": 3.07,
    "arr_target_usd": 1000000,
    "design_partner_target": 10,
    "target_quarter": "Q4 2026",
}

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OCI Robot Cloud v2 — CEO Pitch Deck</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 3px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f8fafc; letter-spacing: .02em; }
    header .version { background: #38bdf8; color: #0f172a; font-size: .75rem; font-weight: 800; padding: .2rem .65rem; border-radius: 9999px; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1.1rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: .75rem; padding: 1.1rem 1.25rem; }
    .kpi .label { font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; margin-bottom: .35rem; }
    .kpi .value { font-size: 2rem; font-weight: 800; color: #38bdf8; }
    .kpi .sub { font-size: .78rem; color: #64748b; margin-top: .2rem; }
    .kpi.red .value { color: #C74634; }
    .section-title { font-size: 1.05rem; font-weight: 700; color: #38bdf8; margin-bottom: 1rem; letter-spacing: .03em; text-transform: uppercase; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: .75rem; padding: 1.4rem; margin-bottom: 1.75rem; }
    .slide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.1rem; }
    .slide { background: #0f172a; border: 1.5px solid #334155; border-radius: .6rem; padding: 1.1rem 1.25rem; transition: border-color .2s; }
    .slide:hover { border-color: #C74634; }
    .slide .num { font-size: .72rem; color: #C74634; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; margin-bottom: .35rem; }
    .slide .stitle { font-size: 1rem; font-weight: 700; color: #f8fafc; margin-bottom: .5rem; }
    .slide .scontent { font-size: .82rem; color: #94a3b8; line-height: 1.5; }
    .ask-box { background: linear-gradient(135deg, #1e293b 60%, #1a1f35); border: 2px solid #C74634; border-radius: .75rem; padding: 1.5rem; }
    .ask-box .ask-title { font-size: 1.15rem; font-weight: 800; color: #C74634; margin-bottom: 1rem; }
    .ask-list { list-style: none; }
    .ask-list li { padding: .4rem 0; font-size: .9rem; color: #e2e8f0; display: flex; gap: .75rem; }
    .ask-list li::before { content: '→'; color: #38bdf8; font-weight: 700; flex-shrink: 0; }
    .chart-wrap { overflow-x: auto; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .endpoint-list { list-style: none; }
    .endpoint-list li { padding: .4rem 0; border-bottom: 1px solid #1e293b; font-size: .88rem; color: #94a3b8; }
    .endpoint-list li span { color: #38bdf8; font-weight: 600; margin-right: .5rem; }
    footer { text-align: center; padding: 2rem; color: #334155; font-size: .8rem; }
  </style>
</head>
<body>
<header>
  <h1>OCI Robot Cloud v2 — CEO Pitch Deck</h1>
  <span class="version">v2 / Cycle 500</span>
  <span style="margin-left:auto;color:#94a3b8;font-size:.85rem;">Port {port}</span>
</header>
<main>
  <div class="kpi-row">
    <div class="kpi red">
      <div class="label">SR Trajectory</div>
      <div class="value">97%</div>
      <div class="sub">DAgger run130 milestone</div>
    </div>
    <div class="kpi">
      <div class="label">Total APIs</div>
      <div class="value">500</div>
      <div class="sub">Cycle 500 milestone</div>
    </div>
    <div class="kpi">
      <div class="label">ARR</div>
      <div class="value">$250K</div>
      <div class="sub">3 design partners</div>
    </div>
    <div class="kpi">
      <div class="label">NRR</div>
      <div class="value">118%</div>
      <div class="sub">Expanding customers</div>
    </div>
    <div class="kpi">
      <div class="label">Cost Advantage</div>
      <div class="value">9.6×</div>
      <div class="sub">vs AWS/GCP</div>
    </div>
    <div class="kpi">
      <div class="label">DAgger Cost</div>
      <div class="value">$129</div>
      <div class="sub">10 iterations total</div>
    </div>
  </div>

  <!-- Proof-point bar chart -->
  <div class="card">
    <div class="section-title">Key Metrics vs Industry Benchmarks</div>
    <div class="chart-wrap">
      <svg viewBox="0 0 820 220" width="100%" xmlns="http://www.w3.org/2000/svg">
        <line x1="140" y1="15" x2="140" y2="185" stroke="#334155" stroke-width="1.5"/>
        <line x1="140" y1="185" x2="800" y2="185" stroke="#334155" stroke-width="1.5"/>
        <!-- SR -->
        <text x="135" y="48" fill="#94a3b8" font-size="11" text-anchor="end">SR (run130)</text>
        <rect x="145" y="30" width="582" height="22" fill="#C74634" rx="3"/>
        <text x="735" y="46" fill="#C74634" font-size="11" font-weight="700">97%</text>
        <!-- Cost advantage -->
        <text x="135" y="88" fill="#94a3b8" font-size="11" text-anchor="end">Cost adv (×)</text>
        <rect x="145" y="70" width="480" height="22" fill="#38bdf8" rx="3"/>
        <text x="633" y="86" fill="#38bdf8" font-size="11" font-weight="700">9.6×</text>
        <!-- NRR -->
        <text x="135" y="128" fill="#94a3b8" font-size="11" text-anchor="end">NRR (%)</text>
        <rect x="145" y="110" width="354" height="22" fill="#38bdf8" rx="3" opacity="0.8"/>
        <text x="507" y="126" fill="#38bdf8" font-size="11" font-weight="700">118%</text>
        <!-- GPU util -->
        <text x="135" y="168" fill="#94a3b8" font-size="11" text-anchor="end">GPU util (%)</text>
        <rect x="145" y="150" width="261" height="22" fill="#38bdf8" rx="3" opacity="0.65"/>
        <text x="414" y="166" fill="#38bdf8" font-size="11" font-weight="700">87%</text>
      </svg>
    </div>
  </div>

  <!-- 6 slides -->
  <div class="card">
    <div class="section-title">6-Slide Pitch Outline</div>
    <div class="slide-grid">
      <div class="slide">
        <div class="num">Slide 1</div>
        <div class="stitle">The $50B Robotics AI Opportunity</div>
        <div class="scontent">97% SR • 9.6× cheaper • 500 APIs shipped</div>
      </div>
      <div class="slide">
        <div class="num">Slide 2</div>
        <div class="stitle">Product: Full-Stack Robot AI Platform</div>
        <div class="scontent">227ms inference • $12.90/iter DAgger • 3.07× DDP</div>
      </div>
      <div class="slide">
        <div class="num">Slide 3</div>
        <div class="stitle">Traction &amp; Proof Points</div>
        <div class="scontent">$250K ARR • NRR 118% • 3 design partners</div>
      </div>
      <div class="slide">
        <div class="num">Slide 4</div>
        <div class="stitle">Why OCI Wins</div>
        <div class="scontent">Bare-metal A100 • 99.94% SLA • NVIDIA partnership</div>
      </div>
      <div class="slide">
        <div class="num">Slide 5</div>
        <div class="stitle">Go-To-Market: Land &amp; Expand</div>
        <div class="scontent">$30K POC → $500K enterprise • $1M ARR Q4 2026</div>
      </div>
      <div class="slide">
        <div class="num">Slide 6</div>
        <div class="stitle">The Ask</div>
        <div class="scontent">NVIDIA intro • design partner • AI World license</div>
      </div>
    </div>
  </div>

  <!-- Key ask -->
  <div class="ask-box">
    <div class="ask-title">The Ask — Three Things from This Meeting</div>
    <ul class="ask-list">
      <li>NVIDIA robotics team intro (GR00T + Isaac Sim product leads)</li>
      <li>Formal design partner program entry + co-marketing agreement</li>
      <li>License to reference OCI Robot Cloud at AI World 2026 (June)</li>
    </ul>
  </div>

  <div class="card" style="margin-top:1.75rem;">
    <div class="section-title">API Endpoints</div>
    <ul class="endpoint-list">
      <li><span>GET</span>/  — this dashboard</li>
      <li><span>GET</span>/health  — JSON health check</li>
      <li><span>GET</span>/pitch/v2/slides  — all slides (optional: ?slide_number=1-6)</li>
      <li><span>GET</span>/pitch/v2/metrics  — all cycle-500 proof-point metrics</li>
    </ul>
  </div>
</main>
<footer>OCI Robot Cloud &copy; 2026 Oracle — CEO Pitch Deck v2 / Cycle-500 Milestone</footer>
</body>
</html>
""".replace("{port}", str(PORT))


if _FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud v2 Pitch",
        description="CEO pitch deck data service — cycle-500 milestone metrics",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "oci_robot_cloud_v2_pitch",
            "port": PORT,
            "version": "2.0.0",
            "cycle": 500,
        })

    @app.get("/pitch/v2/slides")
    async def get_slides(
        slide_number: int | None = Query(default=None, ge=1, le=6)
    ) -> JSONResponse:
        if slide_number is not None:
            matches = [s for s in SLIDES if s["slide_number"] == slide_number]
            if not matches:
                return JSONResponse({"error": "slide not found"}, status_code=404)
            return JSONResponse(matches[0])
        return JSONResponse({"slides": SLIDES, "total": len(SLIDES)})

    @app.get("/pitch/v2/metrics")
    async def get_metrics() -> JSONResponse:
        return JSONResponse(METRICS)

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
            pass

        def _send(self, code: int, ctype: str, body: str | bytes) -> None:
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = _urlparse.urlparse(self.path)
            path = parsed.path
            params = dict(_urlparse.parse_qsl(parsed.query))
            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({
                    "status": "ok", "service": "oci_robot_cloud_v2_pitch", "port": PORT
                }))
            elif path == "/pitch/v2/slides":
                sn = params.get("slide_number")
                if sn is not None:
                    try:
                        sn_int = int(sn)
                        matches = [s for s in SLIDES if s["slide_number"] == sn_int]
                        if not matches:
                            self._send(404, "application/json", json.dumps({"error": "slide not found"}))
                            return
                        self._send(200, "application/json", json.dumps(matches[0]))
                    except ValueError:
                        self._send(400, "application/json", json.dumps({"error": "invalid slide_number"}))
                else:
                    self._send(200, "application/json", json.dumps({"slides": SLIDES, "total": len(SLIDES)}))
            elif path == "/pitch/v2/metrics":
                self._send(200, "application/json", json.dumps(METRICS))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        server.serve_forever()
