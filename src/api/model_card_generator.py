"""Model Card Generator — port 8918
Automated GR00T_v2 model card generation service.
"""

import math
import random
import json
from datetime import datetime

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Model Card Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  h3 { color: #38bdf8; font-size: 1rem; margin: 16px 0 8px; }
  .subtitle { color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .card .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .card .val.red { color: #C74634; }
  .card .val.green { color: #4ade80; }
  table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }
  th { background: #0f172a; color: #38bdf8; padding: 10px 14px; text-align: left; font-size: 0.85rem; }
  td { padding: 10px 14px; border-top: 1px solid #334155; font-size: 0.88rem; color: #cbd5e1; }
  tr:hover td { background: #263448; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 99px; font-size: 0.78rem; font-weight: 600; }
  .badge.complete { background: #14532d; color: #4ade80; }
  .badge.pending { background: #451a03; color: #fb923c; }
  .bar-wrap { background: #0f172a; border-radius: 6px; height: 14px; width: 100%; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 6px; background: linear-gradient(90deg, #38bdf8, #C74634); }
  .section-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .section-name { width: 220px; font-size: 0.85rem; color: #cbd5e1; flex-shrink: 0; }
  .section-pct { width: 48px; text-align: right; font-size: 0.82rem; color: #94a3b8; flex-shrink: 0; }
</style>
</head>
<body>
<h1>Model Card Generator</h1>
<p class="subtitle">Automated GR00T_v2 model card &mdash; 12 sections (10 complete, 2 pending) &mdash; port 8918</p>

<div class="grid">
  <div class="card"><div class="val">12</div><div class="lbl">Total Sections</div></div>
  <div class="card"><div class="val green">10</div><div class="lbl">Complete</div></div>
  <div class="card"><div class="val red">2</div><div class="lbl">Pending</div></div>
  <div class="card"><div class="val">83%</div><div class="lbl">Completeness</div></div>
  <div class="card"><div class="val">$1,842</div><div class="lbl">Training Cost (USD)</div></div>
  <div class="card"><div class="val">12.4 kg</div><div class="lbl">Carbon Estimate CO&#8322;e</div></div>
</div>

<h2>Card Completeness Bars</h2>
<div class="card">
  <div id="bars"></div>
</div>

<h2>Section Completion Status</h2>
<table>
  <thead><tr><th>#</th><th>Section</th><th>Status</th><th>Last Updated</th></tr></thead>
  <tbody id="sections"></tbody>
</table>

<h2>Per-Task Success Rate</h2>
<table>
  <thead><tr><th>Task</th><th>SR (BC)</th><th>SR (DAgger)</th><th>SR (GR00T v2)</th><th>Episodes</th></tr></thead>
  <tbody id="tasks"></tbody>
</table>

<h2>SVG Training Cost Chart</h2>
<div class="card">
  <svg id="cost-chart" width="100%" height="180" viewBox="0 0 700 180" xmlns="http://www.w3.org/2000/svg">
  </svg>
</div>

<script>
const sections = [
  { name: "Model Overview", pct: 100, status: "complete", updated: "2026-03-28" },
  { name: "Intended Use & Scope", pct: 100, status: "complete", updated: "2026-03-28" },
  { name: "Training Data", pct: 100, status: "complete", updated: "2026-03-27" },
  { name: "Architecture Details", pct: 100, status: "complete", updated: "2026-03-27" },
  { name: "Training Procedure", pct: 100, status: "complete", updated: "2026-03-26" },
  { name: "Evaluation Results", pct: 100, status: "complete", updated: "2026-03-29" },
  { name: "Limitations & Biases", pct: 100, status: "complete", updated: "2026-03-25" },
  { name: "Ethical Considerations", pct: 100, status: "complete", updated: "2026-03-25" },
  { name: "Safety & Risk Assessment", pct: 100, status: "complete", updated: "2026-03-26" },
  { name: "Deployment Guidelines", pct: 100, status: "complete", updated: "2026-03-29" },
  { name: "Carbon & Cost Footprint", pct: 40, status: "pending", updated: "2026-03-30" },
  { name: "Versioning & Changelog", pct: 60, status: "pending", updated: "2026-03-30" },
];

const barsEl = document.getElementById('bars');
sections.forEach((s, i) => {
  barsEl.innerHTML += `
    <div class="section-row">
      <div class="section-name">${i+1}. ${s.name}</div>
      <div class="bar-wrap" style="flex:1">
        <div class="bar-fill" style="width:${s.pct}%"></div>
      </div>
      <div class="section-pct">${s.pct}%</div>
    </div>`;
});

const sectBody = document.getElementById('sections');
sections.forEach((s, i) => {
  sectBody.innerHTML += `<tr>
    <td>${i+1}</td>
    <td>${s.name}</td>
    <td><span class="badge ${s.status}">${s.status}</span></td>
    <td>${s.updated}</td>
  </tr>`;
});

const tasks = [
  { name: "PickPlace_Cube", bc: 5, dagger: 30, groot: 72, eps: 500 },
  { name: "StackBlocks", bc: 10, dagger: 38, groot: 68, eps: 450 },
  { name: "OpenDrawer", bc: 8, dagger: 25, groot: 61, eps: 400 },
  { name: "PourWater", bc: 3, dagger: 18, groot: 55, eps: 350 },
  { name: "SweepDebris", bc: 12, dagger: 42, groot: 78, eps: 600 },
  { name: "InsertPeg", bc: 2, dagger: 14, groot: 48, eps: 300 },
];
const taskBody = document.getElementById('tasks');
tasks.forEach(t => {
  taskBody.innerHTML += `<tr>
    <td>${t.name}</td>
    <td>${t.bc}%</td>
    <td>${t.dagger}%</td>
    <td style="color:#4ade80;font-weight:700">${t.groot}%</td>
    <td>${t.eps}</td>
  </tr>`;
});

// SVG cost chart — bar chart of training cost components
const svg = document.getElementById('cost-chart');
const components = [
  { name: "Compute", cost: 980 },
  { name: "Storage", cost: 320 },
  { name: "Network", cost: 210 },
  { name: "Carbon Tax", cost: 180 },
  { name: "Misc", cost: 152 },
];
const maxCost = Math.max(...components.map(c => c.cost));
const barW = 80, gap = 40, startX = 60, baseY = 150;
components.forEach((c, i) => {
  const x = startX + i * (barW + gap);
  const barH = Math.round((c.cost / maxCost) * 110);
  const y = baseY - barH;
  svg.innerHTML += `
    <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="5" fill="#38bdf8" opacity="0.85"/>
    <text x="${x + barW/2}" y="${y - 6}" text-anchor="middle" fill="#e2e8f0" font-size="12">$${c.cost}</text>
    <text x="${x + barW/2}" y="168" text-anchor="middle" fill="#94a3b8" font-size="11">${c.name}</text>
  `;
});
svg.innerHTML += `<line x1="50" y1="150" x2="660" y2="150" stroke="#334155" stroke-width="1"/>`;
</script>
</body>
</html>
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn

    app = FastAPI(title="Model Card Generator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_PAGE)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "model_card_generator", "port": 8918}

    @app.get("/api/card")
    async def card_summary():
        sections = [
            {"id": i+1, "name": n, "complete": c, "pct": p}
            for i, (n, c, p) in enumerate([
                ("Model Overview", True, 100),
                ("Intended Use & Scope", True, 100),
                ("Training Data", True, 100),
                ("Architecture Details", True, 100),
                ("Training Procedure", True, 100),
                ("Evaluation Results", True, 100),
                ("Limitations & Biases", True, 100),
                ("Ethical Considerations", True, 100),
                ("Safety & Risk Assessment", True, 100),
                ("Deployment Guidelines", True, 100),
                ("Carbon & Cost Footprint", False, 40),
                ("Versioning & Changelog", False, 60),
            ])
        ]
        complete = sum(1 for s in sections if s["complete"])
        return JSONResponse({
            "model": "GR00T_v2",
            "total_sections": 12,
            "complete": complete,
            "pending": 12 - complete,
            "completeness_pct": round(complete / 12 * 100, 1),
            "training_cost_usd": 1842,
            "carbon_kg_co2e": 12.4,
            "sections": sections,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8918)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"model_card_generator","port":8918}'
                ct = "application/json"
            else:
                body = HTML_PAGE.encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("Fallback HTTPServer on :8918")
        HTTPServer(("0.0.0.0", 8918), Handler).serve_forever()
