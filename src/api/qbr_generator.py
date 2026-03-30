# QBR Generator — port 8971
# AI-generated 12-slide QBR deck per partner
# Schedule: PI Apr22, Covariant Apr24, Machina Apr29, 1X May1, Apptronik May6
# Auto-prep 48hr before each session

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
<title>QBR Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 0.5rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
  .card .label { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
  .chart-section { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 1.5rem; }
  .slide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }
  .slide-card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.9rem; }
  .slide-num { color: #C74634; font-size: 0.75rem; font-weight: 700; margin-bottom: 0.3rem; }
  .slide-title { color: #e2e8f0; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.3rem; }
  .slide-desc { color: #64748b; font-size: 0.75rem; }
  .cal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }
  .cal-card { background: #0f172a; border-radius: 8px; padding: 1rem; border-left: 4px solid #C74634; }
  .cal-date { color: #C74634; font-size: 0.8rem; font-weight: 700; }
  .cal-partner { color: #38bdf8; font-size: 1rem; font-weight: 700; margin: 0.2rem 0; }
  .cal-prep { color: #4ade80; font-size: 0.75rem; }
  .cal-status { font-size: 0.7rem; color: #64748b; margin-top: 0.25rem; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-blue { background: #1e3a5f; color: #38bdf8; }
  .badge-red { background: #450a0a; color: #fca5a5; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { text-align: left; padding: 0.5rem 0.75rem; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #334155; }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
</style>
</head>
<body>
<h1>QBR Generator</h1>
<p class="subtitle">AI-generated 12-slide Quarterly Business Review decks per partner &mdash; auto-prep 48hr before each session &mdash; port 8971</p>

<div class="grid">
  <div class="card">
    <div class="value">12</div>
    <div class="label">Slides per QBR deck</div>
  </div>
  <div class="card">
    <div class="value">5</div>
    <div class="label">Partners scheduled Q2</div>
  </div>
  <div class="card">
    <div class="value">48 hr</div>
    <div class="label">Auto-prep lead time</div>
  </div>
  <div class="card">
    <div class="value">~4 min</div>
    <div class="label">Deck generation time</div>
  </div>
</div>

<div class="chart-section">
  <h2>QBR Schedule &mdash; Q2 2026</h2>
  <div class="cal-grid">
    <div class="cal-card">
      <div class="cal-date">Apr 22</div>
      <div class="cal-partner">Physical Intelligence</div>
      <div class="cal-prep">&#9654; Prep: Apr 20 (auto)</div>
      <div class="cal-status"><span class="badge badge-red">UPCOMING</span></div>
    </div>
    <div class="cal-card">
      <div class="cal-date">Apr 24</div>
      <div class="cal-partner">Covariant</div>
      <div class="cal-prep">&#9654; Prep: Apr 22 (auto)</div>
      <div class="cal-status"><span class="badge badge-red">UPCOMING</span></div>
    </div>
    <div class="cal-card">
      <div class="cal-date">Apr 29</div>
      <div class="cal-partner">Machina Labs</div>
      <div class="cal-prep">&#9654; Prep: Apr 27 (auto)</div>
      <div class="cal-status"><span class="badge badge-red">UPCOMING</span></div>
    </div>
    <div class="cal-card">
      <div class="cal-date">May 1</div>
      <div class="cal-partner">1X Technologies</div>
      <div class="cal-prep">&#9654; Prep: Apr 29 (auto)</div>
      <div class="cal-status"><span class="badge badge-red">UPCOMING</span></div>
    </div>
    <div class="cal-card">
      <div class="cal-date">May 6</div>
      <div class="cal-partner">Apptronik</div>
      <div class="cal-prep">&#9654; Prep: May 4 (auto)</div>
      <div class="cal-status"><span class="badge badge-red">UPCOMING</span></div>
    </div>
  </div>
</div>

<div class="chart-section">
  <h2>Standard 12-Slide QBR Outline</h2>
  <div class="slide-grid">
    <div class="slide-card"><div class="slide-num">SLIDE 01</div><div class="slide-title">Executive Summary</div><div class="slide-desc">Partnership health score, key wins, and 1-line status for each pillar</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 02</div><div class="slide-title">Partnership Overview</div><div class="slide-desc">Timeline, milestones achieved, team contacts, and engagement model</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 03</div><div class="slide-title">OCI Usage &amp; Compute</div><div class="slide-desc">GPU-hours consumed, cost trend, top workloads (training vs inference)</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 04</div><div class="slide-title">Model Training Results</div><div class="slide-desc">Loss curves, MAE, task success rate vs baseline; fine-tune runs QTD</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 05</div><div class="slide-title">Inference Performance</div><div class="slide-desc">p50/p99 latency, throughput, SLA compliance, cost per inference</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 06</div><div class="slide-title">Data Pipeline Health</div><div class="slide-desc">Demo ingestion volume, SDG ratio, dataset versions, quality metrics</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 07</div><div class="slide-title">SDK &amp; API Adoption</div><div class="slide-desc">API calls/day, SDK version in use, feature utilization heatmap</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 08</div><div class="slide-title">Support &amp; Issues</div><div class="slide-desc">Tickets opened/closed, MTTR, open P1s, escalation history</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 09</div><div class="slide-title">Commercial Update</div><div class="slide-desc">ARR, expansion opportunities, contract renewal timeline, credits used</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 10</div><div class="slide-title">Roadmap Alignment</div><div class="slide-desc">Partner asks vs OCI Robot Cloud roadmap; confirmed deliverables Q3</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 11</div><div class="slide-title">Risks &amp; Mitigations</div><div class="slide-desc">Top 3 risks (technical, commercial, competitive) with mitigation plan</div></div>
    <div class="slide-card"><div class="slide-num">SLIDE 12</div><div class="slide-title">Next Steps &amp; Actions</div><div class="slide-desc">Owner, due date, and success criteria for each committed action item</div></div>
  </div>
</div>

<div class="chart-section">
  <h2>Partner Pipeline (Q2 QBRs)</h2>
  <table>
    <thead>
      <tr><th>Partner</th><th>QBR Date</th><th>Auto-Prep</th><th>Focus Area</th><th>Est. ARR</th><th>Status</th></tr>
    </thead>
    <tbody>
      <tr><td style="color:#38bdf8;">Physical Intelligence</td><td>Apr 22</td><td>Apr 20</td><td>GR00T N1.6 fine-tune scale</td><td>$420K</td><td><span class="badge badge-red">UPCOMING</span></td></tr>
      <tr><td style="color:#38bdf8;">Covariant</td><td>Apr 24</td><td>Apr 22</td><td>Multi-task policy eval</td><td>$380K</td><td><span class="badge badge-red">UPCOMING</span></td></tr>
      <tr><td style="color:#38bdf8;">Machina Labs</td><td>Apr 29</td><td>Apr 27</td><td>SDG + domain randomization</td><td>$310K</td><td><span class="badge badge-red">UPCOMING</span></td></tr>
      <tr><td style="color:#38bdf8;">1X Technologies</td><td>May 1</td><td>Apr 29</td><td>Humanoid inference latency</td><td>$290K</td><td><span class="badge badge-red">UPCOMING</span></td></tr>
      <tr><td style="color:#38bdf8;">Apptronik</td><td>May 6</td><td>May 4</td><td>DAgger + continuous learning</td><td>$265K</td><td><span class="badge badge-red">UPCOMING</span></td></tr>
    </tbody>
  </table>
</div>

<div class="chart-section">
  <h2>Generation Pipeline</h2>
  <p style="color:#94a3b8; font-size:0.9rem; margin-bottom:0.75rem;">48 hours before each QBR, the pipeline auto-pulls OCI usage metrics, training logs, inference telemetry, and support ticket data for the partner, then generates the 12-slide deck and sends a Slack notification to the account team for review.</p>
  <svg viewBox="0 0 700 80" width="100%">
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/>
      </marker>
    </defs>
    <!-- steps -->
    <rect x="10" y="20" width="100" height="40" rx="6" fill="#1e293b" stroke="#334155"/>
    <text x="60" y="38" fill="#38bdf8" font-size="10" text-anchor="middle">Data Pull</text>
    <text x="60" y="52" fill="#64748b" font-size="9" text-anchor="middle">OCI + Logs</text>
    <line x1="110" y1="40" x2="148" y2="40" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
    <rect x="150" y="20" width="100" height="40" rx="6" fill="#1e293b" stroke="#334155"/>
    <text x="200" y="38" fill="#38bdf8" font-size="10" text-anchor="middle">AI Synthesis</text>
    <text x="200" y="52" fill="#64748b" font-size="9" text-anchor="middle">Narrative + KPIs</text>
    <line x1="250" y1="40" x2="288" y2="40" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
    <rect x="290" y="20" width="100" height="40" rx="6" fill="#1e293b" stroke="#334155"/>
    <text x="340" y="38" fill="#38bdf8" font-size="10" text-anchor="middle">Deck Build</text>
    <text x="340" y="52" fill="#64748b" font-size="9" text-anchor="middle">12 slides PPTX</text>
    <line x1="390" y1="40" x2="428" y2="40" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
    <rect x="430" y="20" width="100" height="40" rx="6" fill="#1e293b" stroke="#334155"/>
    <text x="480" y="38" fill="#38bdf8" font-size="10" text-anchor="middle">Review Alert</text>
    <text x="480" y="52" fill="#64748b" font-size="9" text-anchor="middle">Slack notify</text>
    <line x1="530" y1="40" x2="568" y2="40" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrow)"/>
    <rect x="570" y="20" width="120" height="40" rx="6" fill="#14532d" stroke="#4ade80"/>
    <text x="630" y="38" fill="#4ade80" font-size="10" text-anchor="middle">QBR Ready</text>
    <text x="630" y="52" fill="#4ade80" font-size="9" text-anchor="middle">48hr before session</text>
  </svg>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="QBR Generator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "qbr_generator", "port": 8971}

    @app.get("/schedule")
    async def schedule():
        return {
            "partners": [
                {"name": "Physical Intelligence", "qbr_date": "2026-04-22", "prep_date": "2026-04-20", "est_arr_usd": 420000},
                {"name": "Covariant",             "qbr_date": "2026-04-24", "prep_date": "2026-04-22", "est_arr_usd": 380000},
                {"name": "Machina Labs",          "qbr_date": "2026-04-29", "prep_date": "2026-04-27", "est_arr_usd": 310000},
                {"name": "1X Technologies",       "qbr_date": "2026-05-01", "prep_date": "2026-04-29", "est_arr_usd": 290000},
                {"name": "Apptronik",             "qbr_date": "2026-05-06", "prep_date": "2026-05-04", "est_arr_usd": 265000},
            ],
            "slides_per_deck": 12,
            "auto_prep_lead_hours": 48,
            "generation_time_minutes": 4,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8971)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *args): pass

    if __name__ == "__main__":
        print("FastAPI unavailable, using stdlib HTTPServer on port 8971")
        HTTPServer(("0.0.0.0", 8971), Handler).serve_forever()
