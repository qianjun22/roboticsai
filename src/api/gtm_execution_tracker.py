# GTM Execution Tracker — port 8977
import math
import random
import os

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8977
SERVICE_TITLE = "GTM Execution Tracker"

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GTM Execution Tracker</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 20px 0 10px; }
  .subtitle { color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
  .card .val { font-size: 2rem; font-weight: bold; color: #38bdf8; }
  .card .val-red { color: #C74634; }
  .card .val-green { color: #4ade80; }
  .card .val-yellow { color: #fbbf24; }
  .card .label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; margin-bottom: 20px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; margin: 2px; }
  .tag-blue { background: #0c4a6e; color: #38bdf8; }
  .tag-red  { background: #4c0519; color: #f87171; }
  .tag-yellow { background: #422006; color: #fbbf24; }
  .tag-green { background: #052e16; color: #4ade80; }
</style>
</head>
<body>
<h1>GTM Execution Tracker</h1>
<p class="subtitle">24 GTM initiatives across 6 tracks — velocity 2.1 vs 3.0 target | Port 8977</p>

<div class="grid">
  <div class="card">
    <div class="val val-green">8</div>
    <div class="label">Complete</div>
  </div>
  <div class="card">
    <div class="val val-yellow">11</div>
    <div class="label">In Progress</div>
  </div>
  <div class="card">
    <div class="val val-red">5</div>
    <div class="label">Blocked (4 on NVIDIA intro)</div>
  </div>
  <div class="card">
    <div class="val val-red">2.1</div>
    <div class="label">Velocity (target 3.0)</div>
  </div>
</div>

<h2>Initiative Status Gantt (6 Tracks)</h2>
<div class="chart-box">
  <!-- Tracks: Partnerships, Product Launch, Sales Enablement, Developer Relations, Events, Analyst Relations -->
  <!-- Weeks 1-12 on x-axis -->
  <svg viewBox="0 0 700 320" width="100%">
    <!-- y-axis track labels -->
    <text x="5"  y="42"  fill="#94a3b8" font-size="10">Partnerships</text>
    <text x="5"  y="90"  fill="#94a3b8" font-size="10">Product Launch</text>
    <text x="5"  y="138" fill="#94a3b8" font-size="10">Sales Enablement</text>
    <text x="5"  y="186" fill="#94a3b8" font-size="10">Dev Relations</text>
    <text x="5"  y="234" fill="#94a3b8" font-size="10">Events</text>
    <text x="5"  y="282" fill="#94a3b8" font-size="10">Analyst Relations</text>
    <!-- x-axis weeks -->
    <line x1="140" y1="10" x2="140" y2="295" stroke="#1e3a5f" stroke-width="0.8"/>
    <line x1="140" y1="295" x2="690" y2="295" stroke="#475569" stroke-width="1.5"/>
    <!-- week ticks -->
    <!-- 12 weeks, total width=550, step=45.8 -->
    <text x="140"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W1</text>
    <text x="186"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W2</text>
    <text x="232"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W3</text>
    <text x="278"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W4</text>
    <text x="324"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W5</text>
    <text x="370"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W6</text>
    <text x="416"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W7</text>
    <text x="462"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W8</text>
    <text x="508"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W9</text>
    <text x="554"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W10</text>
    <text x="600"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W11</text>
    <text x="646"  y="308" fill="#64748b" font-size="9" text-anchor="middle">W12</text>
    <!-- today marker W6 -->
    <line x1="370" y1="10" x2="370" y2="295" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>
    <text x="373" y="22" fill="#C74634" font-size="9">Today</text>
    <!-- Partnerships: 4 initiatives. Complete W1-W3, In-Progress W2-W8, Blocked W5-W12, In-Progress W6-W10 -->
    <rect x="140" y="22" width="138" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="33" fill="#052e16" font-size="8">NVIDIA MOU ✓</text>
    <rect x="186" y="38" width="276" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="191" y="49" fill="#422006" font-size="8">GTC Co-Mktg</text>
    <rect x="324" y="54" width="322" height="14" fill="#f87171" opacity="0.85" rx="3"/>
    <text x="329" y="65" fill="#4c0519" font-size="8">NVIDIA Intro Blocked ✗</text>
    <!-- Product Launch: 4 initiatives -->
    <rect x="140" y="70" width="184" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="81" fill="#052e16" font-size="8">Beta Docs ✓</text>
    <rect x="186" y="86" width="230" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="191" y="97" fill="#052e16" font-size="8">Pricing Page ✓</text>
    <rect x="278" y="102" width="322" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="283" y="113" fill="#422006" font-size="8">GA Launch</text>
    <!-- Sales Enablement -->
    <rect x="140" y="118" width="138" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="129" fill="#052e16" font-size="8">Pitch Deck ✓</text>
    <rect x="232" y="134" width="276" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="237" y="145" fill="#422006" font-size="8">SE Training</text>
    <rect x="370" y="150" width="276" height="14" fill="#f87171" opacity="0.85" rx="3"/>
    <text x="375" y="161" fill="#4c0519" font-size="8">NVIDIA Demo Blocked ✗</text>
    <!-- Dev Relations -->
    <rect x="140" y="166" width="184" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="177" fill="#052e16" font-size="8">SDK Docs ✓</text>
    <rect x="278" y="182" width="230" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="283" y="193" fill="#422006" font-size="8">Hackathon Prep</text>
    <rect x="416" y="198" width="230" height="14" fill="#f87171" opacity="0.85" rx="3"/>
    <text x="421" y="209" fill="#4c0519" font-size="8">NVIDIA DevRel Blocked ✗</text>
    <!-- Events -->
    <rect x="140" y="214" width="138" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="225" fill="#052e16" font-size="8">GTC Booth ✓</text>
    <rect x="232" y="230" width="322" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="237" y="241" fill="#422006" font-size="8">Robotics Summit</text>
    <rect x="462" y="246" width="184" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="467" y="257" fill="#422006" font-size="8">OCI Open World</text>
    <!-- Analyst Relations -->
    <rect x="140" y="262" width="184" height="14" fill="#4ade80" opacity="0.85" rx="3"/>
    <text x="145" y="273" fill="#052e16" font-size="8">Gartner Brief ✓</text>
    <rect x="278" y="278" width="276" height="14" fill="#fbbf24" opacity="0.85" rx="3"/>
    <text x="283" y="289" fill="#422006" font-size="8">IDC Positioning</text>
    <!-- legend -->
    <rect x="140" y="316" width="10" height="8" fill="#4ade80" rx="2"/>
    <text x="154" y="323" fill="#e2e8f0" font-size="9">Complete (8)</text>
    <rect x="240" y="316" width="10" height="8" fill="#fbbf24" rx="2"/>
    <text x="254" y="323" fill="#e2e8f0" font-size="9">In Progress (11)</text>
    <rect x="360" y="316" width="10" height="8" fill="#f87171" rx="2"/>
    <text x="374" y="323" fill="#e2e8f0" font-size="9">Blocked (5)</text>
  </svg>
</div>

<h2>Dependency Map</h2>
<div class="chart-box">
  <svg viewBox="0 0 700 200" width="100%">
    <!-- Node boxes -->
    <!-- NVIDIA Intro (center blocker) -->
    <rect x="270" y="80" width="130" height="40" fill="#C74634" opacity="0.9" rx="6"/>
    <text x="335" y="96" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">NVIDIA Intro</text>
    <text x="335" y="110" fill="#fca5a5" font-size="9" text-anchor="middle">(4 blockers)</text>
    <!-- Blocked nodes -->
    <rect x="30"  y="20"  width="110" height="35" fill="#7c3aed" opacity="0.8" rx="5"/>
    <text x="85"  y="34"  fill="#fff" font-size="9" text-anchor="middle">NVIDIA MOU V2</text>
    <text x="85"  y="47"  fill="#ddd6fe" font-size="8" text-anchor="middle">Partnerships</text>
    <rect x="30"  y="80"  width="110" height="35" fill="#7c3aed" opacity="0.8" rx="5"/>
    <text x="85"  y="94"  fill="#fff" font-size="9" text-anchor="middle">SE Demo</text>
    <text x="85"  y="107" fill="#ddd6fe" font-size="8" text-anchor="middle">Sales Enablement</text>
    <rect x="30"  y="145" width="110" height="35" fill="#7c3aed" opacity="0.8" rx="5"/>
    <text x="85"  y="159" fill="#fff" font-size="9" text-anchor="middle">DevRel Program</text>
    <text x="85"  y="172" fill="#ddd6fe" font-size="8" text-anchor="middle">Developer Relations</text>
    <rect x="550" y="52"  width="120" height="35" fill="#7c3aed" opacity="0.8" rx="5"/>
    <text x="610" y="66"  fill="#fff" font-size="9" text-anchor="middle">Co-Sell Agreement</text>
    <text x="610" y="79"  fill="#ddd6fe" font-size="8" text-anchor="middle">Partnerships</text>
    <rect x="550" y="112" width="120" height="35" fill="#0e7490" opacity="0.8" rx="5"/>
    <text x="610" y="126" fill="#fff" font-size="9" text-anchor="middle">GTC Co-Marketing</text>
    <text x="610" y="139" fill="#7dd3fc" font-size="8" text-anchor="middle">In Progress</text>
    <!-- arrows from NVIDIA Intro to blocked -->
    <line x1="270" y1="100" x2="142" y2="37"  stroke="#f87171" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="270" y1="100" x2="142" y2="97"  stroke="#f87171" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="270" y1="110" x2="142" y2="162" stroke="#f87171" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="400" y1="95"  x2="548" y2="70"  stroke="#f87171" stroke-width="1.5" marker-end="url(#arr)"/>
    <!-- arrow from NVIDIA Intro to in-progress -->
    <line x1="400" y1="105" x2="548" y2="128" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3" marker-end="url(#arr2)"/>
    <!-- arrowhead defs -->
    <defs>
      <marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill="#f87171"/>
      </marker>
      <marker id="arr2" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill="#fbbf24"/>
      </marker>
    </defs>
    <!-- legend -->
    <rect x="270" y="175" width="10" height="8" fill="#C74634" rx="2"/>
    <text x="284" y="182" fill="#e2e8f0" font-size="9">Critical Blocker</text>
    <rect x="370" y="175" width="10" height="8" fill="#7c3aed" rx="2"/>
    <text x="384" y="182" fill="#e2e8f0" font-size="9">Blocked Node</text>
    <rect x="460" y="175" width="10" height="8" fill="#0e7490" rx="2"/>
    <text x="474" y="182" fill="#e2e8f0" font-size="9">In Progress</text>
  </svg>
</div>

<div style="margin-top:16px;">
  <span class="tag tag-green">8 complete</span>
  <span class="tag tag-yellow">11 in-progress</span>
  <span class="tag tag-red">5 blocked</span>
  <span class="tag tag-red">4 on NVIDIA intro</span>
  <span class="tag tag-blue">velocity 2.1</span>
  <span class="tag tag-yellow">target 3.0</span>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": SERVICE_TITLE,
            "port": PORT,
            "metrics": {
                "total_initiatives": 24,
                "complete": 8,
                "in_progress": 11,
                "blocked": 5,
                "blocked_on_nvidia_intro": 4,
                "velocity_actual": 2.1,
                "velocity_target": 3.0,
                "tracks": 6,
            }
        }

    @app.get("/initiatives")
    async def initiatives():
        tracks = [
            {"track": "Partnerships", "complete": 1, "in_progress": 1, "blocked": 2},
            {"track": "Product Launch", "complete": 2, "in_progress": 1, "blocked": 0},
            {"track": "Sales Enablement", "complete": 1, "in_progress": 1, "blocked": 1},
            {"track": "Developer Relations", "complete": 1, "in_progress": 1, "blocked": 1},
            {"track": "Events", "complete": 1, "in_progress": 2, "blocked": 0},
            {"track": "Analyst Relations", "complete": 2, "in_progress": 0, "blocked": 0},
        ]
        return {"tracks": tracks, "blocker": "NVIDIA Intro (4 downstream items)", "velocity": {"actual": 2.1, "target": 3.0}}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{SERVICE_TITLE} fallback server on port {PORT}")
        server.serve_forever()
