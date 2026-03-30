"""DAgger Round Manager v2 — FastAPI port 8802"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8802

def build_html():
    # Generate DAgger round training metrics with math/random
    rounds = 12
    round_labels = list(range(1, rounds + 1))
    # Success rate improves with DAgger iterations (sigmoid-like curve)
    success_rates = [round(1 / (1 + math.exp(-0.6 * (r - 5))) * 100 + random.uniform(-2, 2), 1) for r in round_labels]
    # Query rate decreases as policy improves
    query_rates = [round(max(5, 95 - r * 7 + random.uniform(-3, 3)), 1) for r in round_labels]
    # Loss curve decreasing
    losses = [round(0.85 * math.exp(-0.25 * r) + random.uniform(0, 0.02), 4) for r in round_labels]

    # SVG bar chart for success rates (width=600, height=200)
    bar_w = 40
    bar_gap = 8
    chart_h = 160
    svg_bars = ""
    for i, val in enumerate(success_rates):
        x = 10 + i * (bar_w + bar_gap)
        h = val / 100 * chart_h
        y = chart_h - h + 20
        color = f"hsl({int(val * 1.2)}, 80%, 55%)"
        svg_bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h:.1f}" fill="{color}" rx="3"/>'
        svg_bars += f'<text x="{x + bar_w//2}" y="{y - 4}" text-anchor="middle" font-size="9" fill="#94a3b8">{val:.0f}%</text>'
        svg_bars += f'<text x="{x + bar_w//2}" y="{chart_h + 35}" text-anchor="middle" font-size="9" fill="#64748b">R{i+1}</text>'

    # SVG line chart for loss (width=600, height=160)
    pts = []
    for i, l in enumerate(losses):
        x = 10 + i * (560 / (rounds - 1))
        y = 10 + (1 - l / losses[0]) * 130
        pts.append((x, y))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    loss_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#f59e0b"/>'
        f'<title>R{i+1}: {losses[i]:.4f}</title>'
        for i, (x, y) in enumerate(pts)
    )

    # Current round stats
    cur_round = rounds
    cur_success = success_rates[-1]
    cur_loss = losses[-1]
    cur_query = query_rates[-1]
    total_demos = sum(random.randint(80, 120) for _ in range(rounds))
    policy_version = f"gr00t-dagger-v2.{rounds}"

    return f"""<!DOCTYPE html><html><head><title>DAgger Round Manager v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top}}
.wide{{width:calc(100% - 60px);display:block}}
.stat{{display:inline-block;margin:0 24px 0 0}}
.stat .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.75em;color:#64748b;text-transform:uppercase}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;background:#0f4c2a;color:#4ade80;margin-right:6px}}
.warn{{background:#431407;color:#fb923c}}
table{{width:100%;border-collapse:collapse;font-size:0.85em}}
th{{color:#64748b;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>DAgger Round Manager v2</h1>
<div style="padding:0 10px 10px">
  <span class="badge">Port 8802</span>
  <span class="badge">Policy: {policy_version}</span>
  <span class="badge">Round {cur_round}/{rounds}</span>
  <span class="badge {'warn' if cur_success < 70 else ''}">Success: {cur_success:.1f}%</span>
</div>

<div class="card">
  <div class="stat"><div class="val">{cur_round}</div><div class="lbl">Current Round</div></div>
  <div class="stat"><div class="val">{cur_success:.1f}%</div><div class="lbl">Success Rate</div></div>
  <div class="stat"><div class="val">{cur_loss:.4f}</div><div class="lbl">Policy Loss</div></div>
  <div class="stat"><div class="val">{cur_query:.1f}%</div><div class="lbl">Query Rate</div></div>
  <div class="stat"><div class="val">{total_demos}</div><div class="lbl">Total Demos</div></div>
</div>

<div class="card wide">
  <h2>Success Rate by DAgger Round</h2>
  <svg width="100%" viewBox="0 0 620 220" xmlns="http://www.w3.org/2000/svg">
    <line x1="10" y1="180" x2="610" y2="180" stroke="#334155" stroke-width="1"/>
    <text x="5" y="25" font-size="9" fill="#475569">100%</text>
    <text x="5" y="105" font-size="9" fill="#475569">50%</text>
    <text x="5" y="183" font-size="9" fill="#475569">0%</text>
    {svg_bars}
  </svg>
</div>

<div class="card wide">
  <h2>Training Loss Curve</h2>
  <svg width="100%" viewBox="0 0 600 160" xmlns="http://www.w3.org/2000/svg">
    <line x1="10" y1="10" x2="10" y2="140" stroke="#334155" stroke-width="1"/>
    <line x1="10" y1="140" x2="590" y2="140" stroke="#334155" stroke-width="1"/>
    <polyline points="{polyline}" fill="none" stroke="#f59e0b" stroke-width="2"/>
    {loss_dots}
    <text x="12" y="15" font-size="9" fill="#475569">loss={losses[0]:.4f}</text>
    <text x="{pts[-1][0]-10:.0f}" y="{pts[-1][1]-8:.0f}" font-size="9" fill="#4ade80">loss={losses[-1]:.4f}</text>
  </svg>
</div>

<div class="card wide">
  <h2>Round History</h2>
  <table>
    <tr><th>Round</th><th>Success Rate</th><th>Policy Loss</th><th>Query Rate</th><th>New Demos</th><th>Status</th></tr>
    {''.join(
      f'<tr><td>R{i+1}</td><td>{success_rates[i]:.1f}%</td><td>{losses[i]:.4f}</td><td>{query_rates[i]:.1f}%</td>'
      f'<td>{random.randint(80, 120)}</td>'
      f'<td><span style="color:#4ade80">complete</span></td></tr>'
      for i in range(rounds)
    )}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Round Manager v2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/rounds")
    def rounds_status():
        return {
            "current_round": 12,
            "policy_version": "gr00t-dagger-v2.12",
            "success_rate": round(random.uniform(88, 95), 2),
            "policy_loss": round(random.uniform(0.008, 0.015), 4),
            "query_rate": round(random.uniform(5, 12), 1),
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
