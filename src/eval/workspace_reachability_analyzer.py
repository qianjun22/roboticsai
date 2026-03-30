"""Workspace Reachability Analyzer — FastAPI port 8449"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8449

def build_html():
    # 8x8 reachability grid top-down view
    random.seed(11)
    # simulate reachability based on distance from robot base
    reach_grid = []
    for row in range(8):
        for col in range(8):
            cx = (col - 3.5) * 0.12  # m
            cy = (row - 1.5) * 0.12
            dist = math.sqrt(cx**2 + cy**2)
            if dist < 0.35:
                score = 0.92 + random.gauss(0, 0.04)
            elif dist < 0.55:
                score = 0.72 + random.gauss(0, 0.06)
            elif dist < 0.75:
                score = 0.48 + random.gauss(0, 0.08)
            else:
                score = 0.18 + random.gauss(0, 0.05)
            score = max(0.0, min(1.0, score))
            reach_grid.append((col, row, score))

    grid_svg = ""
    cell = 36
    for col, row, score in reach_grid:
        x = 20 + col * cell
        y = 20 + row * cell
        if score >= 0.75:
            color = "#22c55e"
        elif score >= 0.45:
            color = "#f59e0b"
        else:
            color = "#C74634"
        opacity = 0.3 + score * 0.7
        grid_svg += f'<rect x="{x}" y="{y}" width="{cell-2}" height="{cell-2}" fill="{color}" opacity="{opacity:.2f}" rx="3"/>'
        grid_svg += f'<text x="{x+cell//2-1}" y="{y+cell//2+4}" fill="#e2e8f0" font-size="9" text-anchor="middle">{int(score*100)}</text>'
    # robot base marker
    grid_svg += f'<circle cx="{20+3.5*cell}" cy="{20+1.5*cell}" r="8" fill="#38bdf8" opacity="0.9"/>'
    grid_svg += f'<text x="{20+3.5*cell}" y="{20+1.5*cell+4}" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="bold">R</text>'

    # task coverage bars
    tasks = ["Pick-Place", "Push", "Stack", "Sweep", "High-Shelf", "Pour"]
    coverage = [0.94, 0.87, 0.81, 0.76, 0.41, 0.69]
    task_bars = ""
    for i, (t, c) in enumerate(zip(tasks, coverage)):
        x = 20 + i * 80
        w = int(c * 200)
        color = "#22c55e" if c >= 0.80 else "#f59e0b" if c >= 0.60 else "#C74634"
        task_bars += f'<rect x="{x}" y="{20 + i*28}" width="{w}" height="18" fill="{color}" rx="3" opacity="0.85"/>'
        task_bars += f'<text x="{x - 4}" y="{20 + i*28 + 13}" fill="#94a3b8" font-size="10" text-anchor="end">{t}</text>'
        task_bars += f'<text x="{x + w + 4}" y="{20 + i*28 + 13}" fill="#e2e8f0" font-size="10">{int(c*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Workspace Reachability Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.warn{{font-size:11px;color:#f59e0b;margin-top:4px}}
.legend{{display:flex;gap:16px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:6px;font-size:11px}}
.ld{{width:12px;height:12px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Workspace Reachability Analyzer — Franka Panda</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">850mm</div><div class="ml">Max Reach Radius</div></div>
  <div class="m"><div class="mv">74%</div><div class="ml">Full-Reach Coverage</div></div>
  <div class="m"><div class="mv">94%</div><div class="ml">Pick-Place Reachable</div></div>
  <div class="m"><div class="mv">41%</div><div class="ml">High-Shelf Reachable</div><div class="warn">⚠ stretch posture needed</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Top-Down Reachability Map (8×8 grid)</h3>
    <svg viewBox="0 0 310 310" width="100%">
      <rect width="310" height="310" fill="#0f172a" rx="6"/>
      {grid_svg}
    </svg>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#22c55e"></div>Full (≥75%)</div>
      <div class="li"><div class="ld" style="background:#f59e0b"></div>Partial (45-74%)</div>
      <div class="li"><div class="ld" style="background:#C74634"></div>Limited (&lt;45%)</div>
      <div class="li"><div class="ld" style="background:#38bdf8;border-radius:50%"></div>Robot Base</div>
    </div>
  </div>
  <div class="card">
    <h3>Task Coverage by Type</h3>
    <svg viewBox="0 0 480 200" width="100%">
      <line x1="200" y1="10" x2="440" y2="10" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>
      <text x="442" y="14" fill="#22c55e" font-size="9">80% target</text>
      {task_bars}
    </svg>
    <p style="font-size:11px;color:#f59e0b;margin:6px 0 0">High-shelf tasks require stretch posture planning; pour task needs tilted wrist configuration</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Workspace Reachability Analyzer")
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
