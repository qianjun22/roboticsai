"""Investor Pipeline Tracker — port 8945"""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Investor Pipeline Tracker</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.2rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .stat { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .stat-label { color: #94a3b8; font-size: 0.8rem; margin-top: 0.2rem; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th { background: #0f172a; color: #38bdf8; padding: 0.6rem 0.8rem; text-align: left; font-size: 0.82rem; }
  td { padding: 0.6rem 0.8rem; border-bottom: 1px solid #334155; font-size: 0.88rem; }
  tr:last-child td { border-bottom: none; }
  .stage-research   { color: #94a3b8; }
  .stage-intro      { color: #fbbf24; }
  .stage-meeting    { color: #38bdf8; }
  .stage-diligence  { color: #a78bfa; }
  .stage-term_sheet { color: #4ade80; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
  .b-research  { background:#1e293b; color:#94a3b8; border:1px solid #475569; }
  .b-intro     { background:#451a03; color:#fbbf24; }
  .b-meeting   { background:#0c2942; color:#38bdf8; }
  .b-diligence { background:#2e1065; color:#a78bfa; }
  .b-term      { background:#14532d; color:#4ade80; }
  .warm { color: #f97316; font-weight: 600; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Investor Pipeline Tracker</h1>
<p class="subtitle">$4M raise &nbsp;|&nbsp; $20M cap &nbsp;|&nbsp; 30 target investors &nbsp;|&nbsp; Sep 2026 close target</p>

<div class="grid">
  <div class="card"><div class="stat">30</div><div class="stat-label">Target investors in pipeline</div></div>
  <div class="card"><div class="stat">$4M</div><div class="stat-label">Raise target (SAFE / $20M cap)</div></div>
  <div class="card"><div class="stat">3</div><div class="stat-label">In diligence or term sheet</div></div>
  <div class="card"><div class="stat">Sep '26</div><div class="stat-label">Target close date</div></div>
</div>

<h2>Pipeline Funnel</h2>
<div class="card">
<svg width="100%" viewBox="0 0 600 220" xmlns="http://www.w3.org/2000/svg">
  <!-- Funnel bars, left-aligned with stage labels -->
  <!-- Stages: research=12, intro=7, meeting=5, diligence=3, term_sheet=1 -->
  <!-- max=12, bar max width=400px, starting x=160 -->
  <!-- research: 400 -->
  <rect x="160" y="18"  width="400" height="30" rx="4" fill="#334155"/>
  <text x="150" y="39" fill="#94a3b8" font-size="12" text-anchor="end">Research</text>
  <text x="568" y="39" fill="#94a3b8" font-size="12">12</text>
  <!-- intro: 7/12*400=233 -->
  <rect x="160" y="58"  width="233" height="30" rx="4" fill="#78350f"/>
  <text x="150" y="79" fill="#fbbf24" font-size="12" text-anchor="end">Intro</text>
  <text x="401" y="79" fill="#fbbf24" font-size="12">7</text>
  <!-- meeting: 5/12*400=167 -->
  <rect x="160" y="98"  width="167" height="30" rx="4" fill="#0c2942"/>
  <text x="150" y="119" fill="#38bdf8" font-size="12" text-anchor="end">Meeting</text>
  <text x="335" y="119" fill="#38bdf8" font-size="12">5</text>
  <!-- diligence: 2/12*400=67 -->
  <rect x="160" y="138" width="67"  height="30" rx="4" fill="#2e1065"/>
  <text x="150" y="159" fill="#a78bfa" font-size="12" text-anchor="end">Diligence</text>
  <text x="235" y="159" fill="#a78bfa" font-size="12">2</text>
  <!-- term_sheet: 1/12*400=33 -->
  <rect x="160" y="178" width="33"  height="30" rx="4" fill="#14532d"/>
  <text x="150" y="199" fill="#4ade80" font-size="12" text-anchor="end">Term Sheet</text>
  <text x="201" y="199" fill="#4ade80" font-size="12">1</text>
</svg>
</div>

<h2>Stage Distribution (Donut)</h2>
<div class="card">
<svg width="100%" viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg">
  <!-- Manual donut segments for 12/7/5/2/1 = total 27 (active pipeline counted) -->
  <!-- Using a simplified arc approximation as rectangles + legend -->
  <!-- Center 130,100 r_outer=80 r_inner=48 -->
  <!-- Angles: research=12/27*360=160deg, intro=93deg, meeting=67deg, diligence=27deg, term=13deg -->
  <!-- Segment paths (pre-computed) -->
  <!-- research: 0→160 -->
  <path d="M130,100 L210,100 A80,80 0 0,1 104.6,178.5 L91.8,150.5 A48,48 0 0,0 178,100 Z" fill="#334155"/>
  <!-- intro: 160→253 -->
  <path d="M130,100 L104.6,178.5 A80,80 0 0,1 56.4,142.8 L73.9,115.7 A48,48 0 0,0 91.8,150.5 Z" fill="#78350f"/>
  <!-- meeting: 253→320 -->
  <path d="M130,100 L56.4,142.8 A80,80 0 0,1 72.4,36.3 L88.8,62.2 A48,48 0 0,0 73.9,115.7 Z" fill="#0c2942"/>
  <!-- diligence: 320→347 -->
  <path d="M130,100 L72.4,36.3 A80,80 0 0,1 106.6,22.1 L97.0,43.7 A48,48 0 0,0 88.8,62.2 Z" fill="#2e1065"/>
  <!-- term: 347→360 -->
  <path d="M130,100 L106.6,22.1 A80,80 0 0,1 210,100 L178,100 A48,48 0 0,0 97.0,43.7 Z" fill="#14532d"/>
  <!-- center hole label -->
  <text x="130" y="97"  fill="#e2e8f0" font-size="13" font-weight="700" text-anchor="middle">30</text>
  <text x="130" y="113" fill="#94a3b8" font-size="10" text-anchor="middle">investors</text>
  <!-- legend -->
  <rect x="240" y="30"  width="14" height="14" rx="3" fill="#334155"/><text x="260" y="42" fill="#94a3b8" font-size="12">Research (12)</text>
  <rect x="240" y="54"  width="14" height="14" rx="3" fill="#78350f"/><text x="260" y="66" fill="#fbbf24" font-size="12">Intro (7)</text>
  <rect x="240" y="78"  width="14" height="14" rx="3" fill="#0c2942"/><text x="260" y="90" fill="#38bdf8" font-size="12">Meeting (5)</text>
  <rect x="240" y="102" width="14" height="14" rx="3" fill="#2e1065"/><text x="260" y="114" fill="#a78bfa" font-size="12">Diligence (2)</text>
  <rect x="240" y="126" width="14" height="14" rx="3" fill="#14532d"/><text x="260" y="138" fill="#4ade80" font-size="12">Term Sheet (1)</text>
</svg>
</div>

<h2>Warm Intro Map &amp; Key Investors</h2>
<div class="card">
<table>
  <thead><tr><th>Investor</th><th>Firm</th><th>Stage</th><th>Warm Intro</th><th>Focus</th></tr></thead>
  <tbody>
    <tr>
      <td>NVentures</td><td>NVIDIA</td>
      <td><span class="badge b-term">Term Sheet</span></td>
      <td class="warm">Greg Pavlik</td>
      <td>Robot infra, OCI stack</td>
    </tr>
    <tr>
      <td>Lux Capital</td><td>Lux</td>
      <td><span class="badge b-diligence">Diligence</span></td>
      <td class="warm">Greg Pavlik</td>
      <td>Embodied AI, deep tech</td>
    </tr>
    <tr>
      <td>GV (Google)</td><td>GV</td>
      <td><span class="badge b-diligence">Diligence</span></td>
      <td>Direct outreach</td>
      <td>Cloud AI infra</td>
    </tr>
    <tr>
      <td>Playground Global</td><td>Playground</td>
      <td><span class="badge b-meeting">Meeting</span></td>
      <td>Warm (robotics network)</td>
      <td>Robotics platform</td>
    </tr>
    <tr>
      <td>Radical Ventures</td><td>Radical</td>
      <td><span class="badge b-meeting">Meeting</span></td>
      <td>Conference intro</td>
      <td>Foundation models</td>
    </tr>
    <tr>
      <td>Bessemer</td><td>BVP</td>
      <td><span class="badge b-intro">Intro</span></td>
      <td>Alumni network</td>
      <td>Cloud infra SaaS</td>
    </tr>
    <tr>
      <td>a16z</td><td>Andreessen Horowitz</td>
      <td><span class="badge b-intro">Intro</span></td>
      <td>Direct outreach</td>
      <td>AI infra</td>
    </tr>
    <tr>
      <td>Toyota Ventures</td><td>TRI</td>
      <td><span class="badge b-research">Research</span></td>
      <td>—</td>
      <td>Automotive robotics</td>
    </tr>
  </tbody>
</table>
</div>

<h2>Raise Summary</h2>
<div class="card" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;">
  <div><div class="stat" style="font-size:1.4rem">$4M</div><div class="stat-label">Target raise</div></div>
  <div><div class="stat" style="font-size:1.4rem">$20M</div><div class="stat-label">Valuation cap (SAFE)</div></div>
  <div><div class="stat" style="font-size:1.4rem">Sep 2026</div><div class="stat-label">Target close</div></div>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Investor Pipeline Tracker")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "investor_pipeline_tracker", "port": 8945}

    @app.get("/api/pipeline")
    async def pipeline():
        return {
            "raise_target_usd": 4_000_000,
            "valuation_cap_usd": 20_000_000,
            "close_target": "2026-09",
            "total_investors": 30,
            "stages": {
                "research": 12,
                "intro": 7,
                "meeting": 5,
                "diligence": 2,
                "term_sheet": 1
            },
            "warm_intro_paths": [
                {"from": "Greg Pavlik", "to": "NVentures"},
                {"from": "Greg Pavlik", "to": "Lux Capital"}
            ]
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8945)
    else:
        print("Serving on http://0.0.0.0:8945 (stdlib fallback)")
        HTTPServer(("0.0.0.0", 8945), Handler).serve_forever()
