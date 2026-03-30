"""DAgger Intervention Analyzer — FastAPI port 8722"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8722

def build_html():
    random.seed(42)
    # Generate intervention rate time series (50 steps)
    steps = list(range(1, 51))
    # DAgger iterations reduce intervention rate over time
    intervention_rates = [
        max(0.02, 0.85 * math.exp(-0.07 * s) + random.uniform(-0.03, 0.03))
        for s in steps
    ]
    # Policy confidence improves over iterations
    confidences = [
        min(0.99, 0.30 + 0.65 * (1 - math.exp(-0.08 * s)) + random.uniform(-0.02, 0.02))
        for s in steps
    ]

    # SVG line chart for intervention rate (600x180)
    svg_w, svg_h = 600, 180
    pad = 40
    chart_w = svg_w - 2 * pad
    chart_h = svg_h - 2 * pad

    def to_x(i): return pad + (i / (len(steps) - 1)) * chart_w
    def to_y(v, vmin=0.0, vmax=1.0): return pad + (1 - (v - vmin) / (vmax - vmin)) * chart_h

    # Intervention rate polyline
    ir_pts = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(intervention_rates))
    # Confidence polyline
    conf_pts = " ".join(f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(confidences))

    # Shaded area under intervention rate
    area_pts = f"{to_x(0):.1f},{to_y(0):.1f} " + ir_pts + f" {to_x(len(steps)-1):.1f},{to_y(0):.1f}"

    # Recent intervention episodes table (last 8)
    random.seed(99)
    episodes = []
    task_names = ["PickCube", "StackBlocks", "OpenDoor", "PourLiquid", "AssembleGear"]
    reasons = ["near-collision", "grasp slip", "pose drift", "joint limit", "out-of-distribution"]
    for ep in range(1, 9):
        ep_id = 1000 - ep
        task = random.choice(task_names)
        reason = random.choice(reasons)
        step_num = random.randint(15, 280)
        q_delta = round(random.uniform(0.12, 0.88), 3)
        episodes.append((ep_id, task, reason, step_num, q_delta))

    rows = "".join(
        f"<tr><td>#{e[0]}</td><td>{e[1]}</td><td><span class='tag'>{e[2]}</span></td>"
        f"<td>{e[3]}</td><td>{e[4]:.3f}</td></tr>"
        for e in episodes
    )

    # Stats
    total_interventions = sum(int(r * 20) for r in intervention_rates)
    avg_rate = round(sum(intervention_rates) / len(intervention_rates), 3)
    final_rate = round(intervention_rates[-1], 3)
    avg_conf = round(sum(confidences) / len(confidences), 3)

    return f"""<!DOCTYPE html><html lang='en'><head><title>DAgger Intervention Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.5rem;letter-spacing:.02em}}
.subtitle{{color:#64748b;padding:0 24px 16px;font-size:.85rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:span 4}}
.card.half{{grid-column:span 2}}
.stat-val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat-label{{font-size:.75rem;color:#94a3b8;margin-top:4px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{color:#94a3b8;font-weight:600;border-bottom:1px solid #334155;padding:6px 8px;text-align:left}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#263249}}
.tag{{background:#1d4ed8;color:#bfdbfe;padding:2px 8px;border-radius:12px;font-size:.75rem}}
.legend{{display:flex;gap:20px;font-size:.75rem;margin-bottom:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}}
</style></head>
<body>
<h1>DAgger Intervention Analyzer</h1>
<div class='subtitle'>Real-time analysis of human expert interventions across DAgger training iterations — port {PORT}</div>
<div class='grid'>
  <div class='card'><div class='stat-val'>{total_interventions}</div><div class='stat-label'>Total Interventions</div></div>
  <div class='card'><div class='stat-val'>{avg_rate:.1%}</div><div class='stat-label'>Avg Intervention Rate</div></div>
  <div class='card'><div class='stat-val' style='color:#4ade80'>{final_rate:.1%}</div><div class='stat-label'>Current Rate (latest iter)</div></div>
  <div class='card'><div class='stat-val'>{avg_conf:.1%}</div><div class='stat-label'>Avg Policy Confidence</div></div>

  <div class='card wide'>
    <h2>Intervention Rate &amp; Policy Confidence over DAgger Iterations</h2>
    <div class='legend'>
      <span><span class='dot' style='background:#f87171'></span>Intervention Rate</span>
      <span><span class='dot' style='background:#38bdf8'></span>Policy Confidence</span>
    </div>
    <svg width='{svg_w}' height='{svg_h}' viewBox='0 0 {svg_w} {svg_h}'>
      <!-- Y gridlines -->
      <line x1='{pad}' y1='{to_y(0.25):.1f}' x2='{pad+chart_w}' y2='{to_y(0.25):.1f}' stroke='#334155' stroke-dasharray='4'/>
      <line x1='{pad}' y1='{to_y(0.5):.1f}' x2='{pad+chart_w}' y2='{to_y(0.5):.1f}' stroke='#334155' stroke-dasharray='4'/>
      <line x1='{pad}' y1='{to_y(0.75):.1f}' x2='{pad+chart_w}' y2='{to_y(0.75):.1f}' stroke='#334155' stroke-dasharray='4'/>
      <!-- Axes -->
      <line x1='{pad}' y1='{pad}' x2='{pad}' y2='{pad+chart_h}' stroke='#475569'/>
      <line x1='{pad}' y1='{pad+chart_h}' x2='{pad+chart_w}' y2='{pad+chart_h}' stroke='#475569'/>
      <!-- Shaded area -->
      <polygon points='{area_pts}' fill='#f8717120' />
      <!-- Intervention rate line -->
      <polyline points='{ir_pts}' fill='none' stroke='#f87171' stroke-width='2'/>
      <!-- Confidence line -->
      <polyline points='{conf_pts}' fill='none' stroke='#38bdf8' stroke-width='2' stroke-dasharray='6 3'/>
      <!-- Y labels -->
      <text x='{pad-6}' y='{to_y(1.0):.1f}' fill='#64748b' font-size='10' text-anchor='end'>1.0</text>
      <text x='{pad-6}' y='{to_y(0.75):.1f}' fill='#64748b' font-size='10' text-anchor='end'>.75</text>
      <text x='{pad-6}' y='{to_y(0.5):.1f}' fill='#64748b' font-size='10' text-anchor='end'>.50</text>
      <text x='{pad-6}' y='{to_y(0.25):.1f}' fill='#64748b' font-size='10' text-anchor='end'>.25</text>
      <text x='{pad-6}' y='{to_y(0.0):.1f}' fill='#64748b' font-size='10' text-anchor='end'>0</text>
      <!-- X labels -->
      <text x='{to_x(0):.1f}' y='{pad+chart_h+16}' fill='#64748b' font-size='10' text-anchor='middle'>1</text>
      <text x='{to_x(12):.1f}' y='{pad+chart_h+16}' fill='#64748b' font-size='10' text-anchor='middle'>13</text>
      <text x='{to_x(24):.1f}' y='{pad+chart_h+16}' fill='#64748b' font-size='10' text-anchor='middle'>25</text>
      <text x='{to_x(37):.1f}' y='{pad+chart_h+16}' fill='#64748b' font-size='10' text-anchor='middle'>38</text>
      <text x='{to_x(49):.1f}' y='{pad+chart_h+16}' fill='#64748b' font-size='10' text-anchor='middle'>50</text>
    </svg>
  </div>

  <div class='card wide'>
    <h2>Recent Intervention Episodes</h2>
    <table>
      <thead><tr><th>Episode</th><th>Task</th><th>Trigger Reason</th><th>Step @Intervention</th><th>Q-Value Delta</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Intervention Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
