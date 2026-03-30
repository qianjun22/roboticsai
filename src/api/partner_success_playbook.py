"""Partner Success Playbook — FastAPI port 8845"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8845

PARTNERS  = ["Acme Robotics", "NovaDyne", "Apex Systems", "CoreTech", "Stellar AI"]
SCENARIOS = ["SR Drop", "Churn Risk", "Onboarding", "Upgrade", "Support Surge", "Renewal", "Expansion", "NPS Dip"]

# Coverage matrix: 1 = playbook exists, 0 = gap
COVERAGE = [
    [1, 1, 1, 1, 0, 1, 0, 1],  # Acme Robotics
    [1, 1, 1, 0, 1, 1, 1, 0],  # NovaDyne
    [1, 0, 1, 1, 1, 0, 1, 1],  # Apex Systems
    [1, 1, 0, 1, 0, 1, 1, 1],  # CoreTech
    [0, 1, 1, 1, 1, 1, 0, 1],  # Stellar AI
]

def build_html():
    # Build SVG coverage matrix (5 partners × 8 scenarios)
    cell_w, cell_h = 58, 32
    label_w, label_h = 100, 20
    svg_w = label_w + len(SCENARIOS) * cell_w + 10
    svg_h = label_h + len(PARTNERS) * cell_h + 10

    svg_cells = ""
    # Column headers
    for j, sc in enumerate(SCENARIOS):
        x = label_w + j * cell_w + cell_w / 2
        svg_cells += f'<text x="{x:.0f}" y="14" fill="#94a3b8" font-size="9" text-anchor="middle">{sc}</text>\n'

    # Row labels + cells
    for i, partner in enumerate(PARTNERS):
        y_top = label_h + i * cell_h
        svg_cells += f'<text x="{label_w - 6}" y="{y_top + cell_h/2 + 4:.0f}" fill="#e2e8f0" font-size="10" text-anchor="end">{partner}</text>\n'
        for j, covered in enumerate(COVERAGE[i]):
            x = label_w + j * cell_w
            fill = "#16a34a" if covered else "#374151"
            symbol = "✓" if covered else "·"
            sym_fill = "#bbf7d0" if covered else "#6b7280"
            svg_cells += f'<rect x="{x+2}" y="{y_top+2}" width="{cell_w-4}" height="{cell_h-4}" rx="4" fill="{fill}" opacity="0.85"/>\n'
            svg_cells += f'<text x="{x + cell_w/2:.0f}" y="{y_top + cell_h/2 + 5:.0f}" fill="{sym_fill}" font-size="14" text-anchor="middle">{symbol}</text>\n'

    return f"""<!DOCTYPE html><html><head><title>Partner Success Playbook</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap}}
.metric{{background:#0f172a;padding:14px 20px;border-radius:6px;border-left:4px solid #C74634}}
.metric .val{{font-size:2em;font-weight:bold;color:#f8fafc}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:4px}}
.legend{{display:flex;gap:18px;margin-bottom:8px;font-size:0.85em}}
.dot{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:middle}}
</style></head>
<body>
<h1>Partner Success Playbook</h1>
<p style="padding:0 20px;color:#94a3b8">Automated playbook recommendations triggered by partner health signals · Port {PORT}</p>

<div class="card">
  <h2>Playbook Coverage Matrix — 5 Partners × 8 Scenarios</h2>
  <div class="legend">
    <span><span class="dot" style="background:#16a34a"></span>Playbook Active</span>
    <span><span class="dot" style="background:#374151"></span>Gap / No Coverage</span>
  </div>
  <svg width="{svg_w}" height="{svg_h}" style="display:block;overflow:visible">
    {svg_cells}
  </svg>
</div>

<div class="card">
  <h2>Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">91%</div><div class="lbl">SR Drop Resolution Rate</div></div>
    <div class="metric"><div class="val">78%</div><div class="lbl">Churn Risk Resolution</div></div>
    <div class="metric"><div class="val">5</div><div class="lbl">Active Playbooks</div></div>
    <div class="metric"><div class="val">8</div><div class="lbl">Scenario Types</div></div>
  </div>
</div>

<div class="card">
  <h2>Active Playbooks</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.9em">
    <thead><tr style="border-bottom:1px solid #334155;color:#94a3b8">
      <th style="text-align:left;padding:8px">Playbook</th>
      <th style="text-align:left;padding:8px">Trigger Signal</th>
      <th style="text-align:left;padding:8px">Resolution Rate</th>
      <th style="text-align:left;padding:8px">Avg. TTR</th>
    </tr></thead>
    <tbody>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#38bdf8">SR Drop Recovery</td>
        <td style="padding:8px">Success Rate &lt; 70%</td>
        <td style="padding:8px;color:#4ade80">91%</td>
        <td style="padding:8px">2.3 days</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#38bdf8">Churn Risk Mitigation</td>
        <td style="padding:8px">Health score &lt; 0.45</td>
        <td style="padding:8px;color:#4ade80">78%</td>
        <td style="padding:8px">4.1 days</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#38bdf8">Rapid Onboarding</td>
        <td style="padding:8px">New partner (day 0–30)</td>
        <td style="padding:8px;color:#4ade80">95%</td>
        <td style="padding:8px">7.0 days</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#38bdf8">Renewal Assist</td>
        <td style="padding:8px">Contract &lt; 60 days</td>
        <td style="padding:8px;color:#4ade80">88%</td>
        <td style="padding:8px">5.5 days</td>
      </tr>
      <tr>
        <td style="padding:8px;color:#38bdf8">NPS Recovery</td>
        <td style="padding:8px">NPS score &lt; 7</td>
        <td style="padding:8px;color:#4ade80">82%</td>
        <td style="padding:8px">3.8 days</td>
      </tr>
    </tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Success Playbook")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "sr_drop_resolution_rate_pct": 91,
            "churn_risk_resolution_rate_pct": 78,
            "active_playbooks": 5,
            "scenario_types": 8,
            "partners_monitored": 5,
        }

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
