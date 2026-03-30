"""Curriculum Difficulty Tracker — OCI Robot Cloud (port 8599)

Competence-based curriculum scheduler with 8-task progression,
difficulty/SR scatter, and convergence comparison dashboard.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8599

TASKS = ["reach", "grasp", "lift", "stack", "pour", "assemble"]


def build_html() -> str:
    # ------------------------------------------------------------------ SVG 1
    progression_svg = """
<svg viewBox="0 0 680 280" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:700px">
  <rect width="680" height="280" fill="#1e293b" rx="8"/>
  <text x="340" y="24" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">Task Difficulty Progression &amp; SR Gating Timeline</text>
  <!-- x axis: training steps 0-2000 -->
  <line x1="60" y1="220" x2="640" y2="220" stroke="#475569" stroke-width="1.5"/>
  <!-- y axis: difficulty 0-1 -->
  <line x1="60" y1="40" x2="60" y2="220" stroke="#475569" stroke-width="1.5"/>
  <!-- axis labels -->
  <text x="350" y="244" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Training Steps (×100)</text>
  <text x="14" y="135" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,14,135)">Difficulty</text>
  <!-- step ticks -->
  <text x="60" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0</text>
  <text x="118" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">2</text>
  <text x="176" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">4</text>
  <text x="234" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">6</text>
  <text x="292" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">8</text>
  <text x="350" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">10</text>
  <text x="408" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">12</text>
  <text x="466" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">14</text>
  <text x="524" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">16</text>
  <text x="582" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">18</text>
  <text x="640" y="233" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">20</text>
  <!-- y ticks -->
  <text x="53" y="220" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.0</text>
  <text x="53" y="175" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.25</text>
  <text x="53" y="130" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.5</text>
  <text x="53" y="85" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.75</text>
  <text x="53" y="40" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">1.0</text>
  <!-- task difficulty bands (horizontal stripes) -->
  <!-- reach: diff 0.1, grasp: 0.25, lift: 0.42, stack: 0.58, pour: 0.72, assemble: 0.88 -->
  <!-- y = 220 - diff*180 -->
  <!-- reach line -->
  <line x1="60" y1="202" x2="118" y2="202" stroke="#22c55e" stroke-width="2.5"/>
  <!-- SR gate at step 200 -> x=118 -->
  <circle cx="118" cy="202" r="4" fill="#22c55e"/>
  <line x1="118" y1="202" x2="176" y2="175" stroke="#86efac" stroke-width="2" stroke-dasharray="4,2"/>
  <!-- grasp line -->
  <line x1="118" y1="175" x2="234" y2="175" stroke="#38bdf8" stroke-width="2.5"/>
  <circle cx="234" cy="175" r="4" fill="#38bdf8"/>
  <line x1="234" y1="175" x2="292" y2="144" stroke="#7dd3fc" stroke-width="2" stroke-dasharray="4,2"/>
  <!-- lift -->
  <line x1="234" y1="144" x2="350" y2="144" stroke="#a78bfa" stroke-width="2.5"/>
  <circle cx="350" cy="144" r="4" fill="#a78bfa"/>
  <line x1="350" y1="144" x2="408" y2="116" stroke="#c4b5fd" stroke-width="2" stroke-dasharray="4,2"/>
  <!-- stack -->
  <line x1="350" y1="116" x2="466" y2="116" stroke="#f59e0b" stroke-width="2.5"/>
  <circle cx="466" cy="116" r="4" fill="#f59e0b"/>
  <line x1="466" y1="116" x2="524" y2="90" stroke="#fcd34d" stroke-width="2" stroke-dasharray="4,2"/>
  <!-- pour -->
  <line x1="466" y1="90" x2="582" y2="90" stroke="#f87171" stroke-width="2.5"/>
  <circle cx="582" cy="90" r="4" fill="#f87171"/>
  <line x1="582" y1="90" x2="640" y2="60" stroke="#fca5a5" stroke-width="2" stroke-dasharray="4,2"/>
  <!-- assemble -->
  <line x1="582" y1="60" x2="640" y2="60" stroke="#C74634" stroke-width="2.5"/>
  <!-- SR gate labels -->
  <text x="118" y="195" fill="#22c55e" font-size="8" font-family="monospace">SR≥0.7</text>
  <text x="234" y="168" fill="#38bdf8" font-size="8" font-family="monospace">SR≥0.7</text>
  <text x="350" y="137" fill="#a78bfa" font-size="8" font-family="monospace">SR≥0.7</text>
  <text x="466" y="109" fill="#f59e0b" font-size="8" font-family="monospace">SR≥0.7</text>
  <text x="582" y="83" fill="#f87171" font-size="8" font-family="monospace">SR≥0.7</text>
  <!-- task name labels on right -->
  <text x="644" y="205" fill="#22c55e" font-size="9" font-family="monospace">reach</text>
  <text x="644" y="178" fill="#38bdf8" font-size="9" font-family="monospace">grasp</text>
  <text x="644" y="147" fill="#a78bfa" font-size="9" font-family="monospace">lift</text>
  <text x="644" y="119" fill="#f59e0b" font-size="9" font-family="monospace">stack</text>
  <text x="644" y="93" fill="#f87171" font-size="9" font-family="monospace">pour</text>
  <text x="644" y="63" fill="#C74634" font-size="9" font-family="monospace">assemble</text>
</svg>"""

    # ------------------------------------------------------------------ SVG 2
    scatter_svg = """
<svg viewBox="0 0 400 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:420px">
  <rect width="400" height="320" fill="#1e293b" rx="8"/>
  <text x="200" y="24" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">Difficulty vs SR per Task</text>
  <!-- axes -->
  <line x1="55" y1="270" x2="370" y2="270" stroke="#475569" stroke-width="1.5"/>
  <line x1="55" y1="270" x2="55" y2="40" stroke="#475569" stroke-width="1.5"/>
  <text x="212" y="296" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Difficulty Score</text>
  <text x="16" y="160" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,16,160)">Success Rate</text>
  <!-- ticks -->
  <text x="55" y="283" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0.0</text>
  <text x="134" y="283" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0.25</text>
  <text x="212" y="283" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0.5</text>
  <text x="291" y="283" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0.75</text>
  <text x="370" y="283" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">1.0</text>
  <text x="48" y="270" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.0</text>
  <text x="48" y="193" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.25</text>
  <text x="48" y="155" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.5</text>
  <text x="48" y="117" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.75</text>
  <text x="48" y="44" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">1.0</text>
  <!-- grid -->
  <line x1="55" y1="193" x2="370" y2="193" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <line x1="55" y1="155" x2="370" y2="155" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <line x1="55" y1="117" x2="370" y2="117" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <!-- trajectory arrow path: tasks advance from low SR to high SR as training progresses -->
  <!-- task coords: (difficulty, sr_early) -> (difficulty, sr_final) -->
  <!-- reach: diff=0.1 -> x=87, early SR=0.4->y=193, final SR=0.92->y=55 -->
  <!-- grasp: diff=0.25 -> x=134, early=0.35->y=204, final=0.85->y=90 -->
  <!-- lift: diff=0.42 -> x=187, early=0.28->y=213, final=0.78->y=108 -->
  <!-- stack: diff=0.58 -> x=237, early=0.2->y=221, final=0.71->y=126 -->
  <!-- pour: diff=0.72 -> x=282, early=0.15->y=230, final=0.62->y=140 -->
  <!-- assemble: diff=0.88 -> x=332, early=0.1->y=248, final=0.52->y=155 -->
  <!-- progression arrows per task -->
  <defs>
    <marker id="arrowhead" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
      <polygon points="0 0, 7 3.5, 0 7" fill="#38bdf8" opacity="0.8"/>
    </marker>
  </defs>
  <!-- reach -->
  <line x1="87" y1="193" x2="87" y2="60" stroke="#22c55e" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="87" cy="193" r="5" fill="#22c55e" opacity="0.5"/>
  <circle cx="87" cy="60" r="6" fill="#22c55e"/>
  <text x="87" y="54" text-anchor="middle" fill="#22c55e" font-size="8" font-family="monospace">reach</text>
  <!-- grasp -->
  <line x1="134" y1="204" x2="134" y2="90" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="134" cy="204" r="5" fill="#38bdf8" opacity="0.5"/>
  <circle cx="134" cy="90" r="6" fill="#38bdf8"/>
  <text x="134" y="84" text-anchor="middle" fill="#38bdf8" font-size="8" font-family="monospace">grasp</text>
  <!-- lift -->
  <line x1="187" y1="213" x2="187" y2="108" stroke="#a78bfa" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="187" cy="213" r="5" fill="#a78bfa" opacity="0.5"/>
  <circle cx="187" cy="108" r="6" fill="#a78bfa"/>
  <text x="187" y="102" text-anchor="middle" fill="#a78bfa" font-size="8" font-family="monospace">lift</text>
  <!-- stack -->
  <line x1="237" y1="221" x2="237" y2="126" stroke="#f59e0b" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="237" cy="221" r="5" fill="#f59e0b" opacity="0.5"/>
  <circle cx="237" cy="126" r="6" fill="#f59e0b"/>
  <text x="237" y="120" text-anchor="middle" fill="#f59e0b" font-size="8" font-family="monospace">stack</text>
  <!-- pour -->
  <line x1="282" y1="230" x2="282" y2="140" stroke="#f87171" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="282" cy="230" r="5" fill="#f87171" opacity="0.5"/>
  <circle cx="282" cy="140" r="6" fill="#f87171"/>
  <text x="282" y="134" text-anchor="middle" fill="#f87171" font-size="8" font-family="monospace">pour</text>
  <!-- assemble -->
  <line x1="332" y1="248" x2="332" y2="155" stroke="#C74634" stroke-width="1.5" marker-end="url(#arrowhead)"/>
  <circle cx="332" cy="248" r="5" fill="#C74634" opacity="0.5"/>
  <circle cx="332" cy="155" r="6" fill="#C74634"/>
  <text x="332" y="149" text-anchor="middle" fill="#C74634" font-size="8" font-family="monospace">assemble</text>
  <!-- legend -->
  <circle cx="65" cy="40" r="4" fill="#94a3b8" opacity="0.5"/>
  <text x="73" y="44" fill="#94a3b8" font-size="9" font-family="monospace">Start of training</text>
  <circle cx="65" cy="54" r="5" fill="#94a3b8"/>
  <text x="73" y="58" fill="#94a3b8" font-size="9" font-family="monospace">End of training</text>
</svg>"""

    # ------------------------------------------------------------------ SVG 3
    convergence_svg = """
<svg viewBox="0 0 480 280" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:500px">
  <rect width="480" height="280" fill="#1e293b" rx="8"/>
  <text x="240" y="24" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">Competence-Based vs Fixed Curriculum SR</text>
  <!-- axes -->
  <line x1="55" y1="230" x2="430" y2="230" stroke="#475569" stroke-width="1.5"/>
  <line x1="55" y1="230" x2="55" y2="40" stroke="#475569" stroke-width="1.5"/>
  <text x="242" y="252" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Training Steps (×100)</text>
  <text x="14" y="140" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,14,140)">Avg Success Rate</text>
  <!-- x ticks: 0-2000 in 200 steps, mapped 55..430 -> step 200=88.75 -->
  <!-- x = 55 + step/2000 * 375 -->
  <text x="55" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">0</text>
  <text x="130" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">4</text>
  <text x="205" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">8</text>
  <text x="280" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">12</text>
  <text x="355" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">16</text>
  <text x="430" y="243" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">20</text>
  <!-- y ticks: 0..1 -> 230..40 -->
  <text x="48" y="230" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.0</text>
  <text x="48" y="182" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.25</text>
  <text x="48" y="135" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.5</text>
  <text x="48" y="87" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">0.75</text>
  <text x="48" y="40" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">1.0</text>
  <!-- gridlines -->
  <line x1="55" y1="182" x2="430" y2="182" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <line x1="55" y1="135" x2="430" y2="135" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <line x1="55" y1="87" x2="430" y2="87" stroke="#334155" stroke-width="0.7" stroke-dasharray="3,3"/>
  <!-- 0.7 SR threshold line -->
  <line x1="55" y1="97" x2="430" y2="97" stroke="#475569" stroke-width="1" stroke-dasharray="6,3"/>
  <text x="433" y="100" fill="#475569" font-size="9" font-family="monospace">SR=0.7</text>
  <!-- competence-based curve (converges at step 680 -> x = 55 + 680/2000*375 = 182.5) -->
  <!-- points: (0,0.05),(200,0.15),(400,0.32),(600,0.58),(680,0.71),(800,0.78),(1000,0.83),(1400,0.87),(2000,0.90) -->
  <!-- x=55+s/2000*375, y=230-sr*190 -->
  <polyline points="
    55,221
    93,201
    130,169
    168,120
    183,95
    205,82
    243,72
    318,65
    430,59
  " fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
  <!-- convergence marker -->
  <circle cx="183" cy="95" r="5" fill="#38bdf8"/>
  <line x1="183" y1="95" x2="183" y2="230" stroke="#38bdf8" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>
  <text x="183" y="260" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="monospace">680</text>
  <!-- fixed curriculum curve (converges at step 1200 -> x = 55 + 1200/2000*375 = 280) -->
  <!-- points: (0,0.05),(200,0.09),(400,0.15),(600,0.24),(800,0.36),(1000,0.51),(1200,0.71),(1400,0.79),(1600,0.84),(2000,0.88) -->
  <polyline points="
    55,221
    93,213
    130,201
    168,184
    205,162
    243,133
    280,97
    318,80
    355,70
    430,63
  " fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linejoin="round" stroke-dasharray="8,3"/>
  <!-- convergence marker -->
  <circle cx="280" cy="97" r="5" fill="#f59e0b"/>
  <line x1="280" y1="97" x2="280" y2="230" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>
  <text x="280" y="260" text-anchor="middle" fill="#f59e0b" font-size="9" font-family="monospace">1200</text>
  <!-- legend -->
  <rect x="260" y="120" width="155" height="52" fill="#0f172a" rx="5"/>
  <line x1="268" y1="134" x2="288" y2="134" stroke="#38bdf8" stroke-width="2.5"/>
  <text x="293" y="138" fill="#38bdf8" font-size="10" font-family="monospace">Competence-based</text>
  <line x1="268" y1="154" x2="288" y2="154" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="6,3"/>
  <text x="293" y="158" fill="#f59e0b" font-size="10" font-family="monospace">Fixed curriculum</text>
</svg>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Curriculum Difficulty Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace, sans-serif; min-height: 100vh; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ color: #C74634; font-size: 1.35rem; font-weight: 700; letter-spacing: 0.5px; }}
  header span {{ color: #38bdf8; font-size: 0.85rem; margin-left: auto; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; padding: 24px 32px 0; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 14px; text-align: center; }}
  .metric-card .value {{ font-size: 1.9rem; font-weight: 800; color: #38bdf8; }}
  .metric-card .label {{ font-size: 0.75rem; color: #94a3b8; margin-top: 6px; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 24px 32px; }}
  .charts .wide {{ grid-column: 1 / -1; }}
  .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }}
  .chart-card h2 {{ color: #C74634; font-size: 0.9rem; margin-bottom: 14px; letter-spacing: 0.3px; }}
  footer {{ text-align: center; color: #475569; font-size: 0.75rem; padding: 20px; border-top: 1px solid #1e293b; }}
</style>
</head>
<body>
<header>
  <h1>Curriculum Difficulty Tracker</h1>
  <span>port 8599 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Competence-Based Scheduler</span>
</header>

<div class="metrics">
  <div class="metric-card"><div class="value">8</div><div class="label">Tasks in Curriculum</div></div>
  <div class="metric-card"><div class="value">0.70</div><div class="label">SR Threshold to Advance</div></div>
  <div class="metric-card"><div class="value">43%</div><div class="label">Faster Convergence (competence vs fixed)</div></div>
  <div class="metric-card"><div class="value">&#9888;</div><div class="label">Task Bleeding Detected</div></div>
</div>

<div class="charts">
  <div class="chart-card wide">
    <h2>Task Difficulty Progression &amp; SR Gating Timeline</h2>
    {progression_svg}
  </div>
  <div class="chart-card">
    <h2>Difficulty vs SR Scatter (arrows = training progression)</h2>
    {scatter_svg}
  </div>
  <div class="chart-card">
    <h2>Competence-Based vs Fixed Curriculum — SR Convergence</h2>
    {convergence_svg}
  </div>
</div>

<footer>OCI Robot Cloud &mdash; Curriculum Difficulty Tracker &mdash; port 8599</footer>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Curriculum Difficulty Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "curriculum_difficulty_tracker",
            "port": PORT,
            "metrics": {
                "num_tasks": 8,
                "sr_threshold": 0.70,
                "competence_speedup_pct": 43,
                "task_bleeding_detected": True,
                "competence_convergence_step": 680,
                "fixed_convergence_step": 1200,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","port":8599}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
