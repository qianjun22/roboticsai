"""Bimanual Grasp Planner — FastAPI port 8464"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8464

def build_html():
    # dual-arm workspace overlap SVG
    cx1, cy1, cx2, cy2, r = 130, 150, 270, 150, 110
    workspace_svg = f'<circle cx="{cx1}" cy="{cy1}" r="{r}" fill="#38bdf8" opacity="0.18" stroke="#38bdf8" stroke-width="2"/>'
    workspace_svg += f'<circle cx="{cx2}" cy="{cy2}" r="{r}" fill="#C74634" opacity="0.18" stroke="#C74634" stroke-width="2"/>'
    workspace_svg += f'<text x="{cx1}" y="{cy1+130}" fill="#38bdf8" font-size="11" text-anchor="middle">Left Arm</text>'
    workspace_svg += f'<text x="{cx2}" y="{cy2+130}" fill="#C74634" font-size="11" text-anchor="middle">Right Arm</text>'
    # intersection zone highlight
    workspace_svg += f'<text x="200" y="{cy1+5}" fill="#22c55e" font-size="10" text-anchor="middle" font-weight="bold">Coordination</text>'
    workspace_svg += f'<text x="200" y="{cy1+18}" fill="#22c55e" font-size="10" text-anchor="middle">Zone</text>'
    workspace_svg += f'<text x="200" y="{cy1+32}" fill="#22c55e" font-size="9" text-anchor="middle">~38% overlap</text>'
    # arm base markers
    workspace_svg += f'<circle cx="{cx1}" cy="{cy1}" r="8" fill="#38bdf8"/>'
    workspace_svg += f'<text x="{cx1}" y="{cy1+4}" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">L</text>'
    workspace_svg += f'<circle cx="{cx2}" cy="{cy2}" r="8" fill="#C74634"/>'
    workspace_svg += f'<text x="{cx2}" y="{cy2+4}" fill="#fff" font-size="8" text-anchor="middle" font-weight="bold">R</text>'

    # coordination timeline SVG
    phases = [("Reach", 0, 2), ("Pre-Grasp", 2, 3.5), ("Grasp", 3.5, 5), ("Lift", 5, 7), ("Handoff", 7, 9), ("Place", 9, 11)]
    phase_colors = {"Reach": "#64748b", "Pre-Grasp": "#38bdf8", "Grasp": "#C74634", "Lift": "#22c55e", "Handoff": "#f59e0b", "Place": "#8b5cf6"}
    timeline_svg = ""
    for phase, t_start, t_end in phases:
        x_start = 30 + t_start * 35
        width = (t_end - t_start) * 35 - 3
        color = phase_colors[phase]
        # left arm (y=20) with slight delay
        delay = 0.2 if phase == "Handoff" else 0
        x_l = 30 + (t_start + delay) * 35
        w_l = width - delay * 35
        timeline_svg += f'<rect x="{x_l:.1f}" y="20" width="{max(2,w_l):.1f}" height="30" fill="{color}" rx="4" opacity="0.85"/>'
        # right arm (y=65)
        timeline_svg += f'<rect x="{x_start:.1f}" y="65" width="{width:.1f}" height="30" fill="{color}" rx="4" opacity="0.6"/>'
        timeline_svg += f'<text x="{x_start+width/2:.1f}" y="115" fill="#94a3b8" font-size="9" text-anchor="middle">{phase}</text>'
    timeline_svg += f'<text x="22" y="39" fill="#38bdf8" font-size="10" text-anchor="end">L</text>'
    timeline_svg += f'<text x="22" y="84" fill="#C74634" font-size="10" text-anchor="end">R</text>'

    # synchrony scores
    task_sync = [("bimanual_pass", 0.81), ("cloth_fold", 0.74), ("bi_insert", 0.68), ("handoff", 0.91)]
    sync_bars = ""
    for i, (task, score) in enumerate(task_sync):
        x = 20 + i * 100
        h = int(score * 100)
        color = "#22c55e" if score >= 0.80 else "#f59e0b" if score >= 0.65 else "#C74634"
        sync_bars += f'<rect x="{x}" y="{110-h}" width="72" height="{h}" fill="{color}" rx="4" opacity="0.85"/>'
        sync_bars += f'<text x="{x+36}" y="125" fill="#94a3b8" font-size="9" text-anchor="middle">{task}</text>'
        sync_bars += f'<text x="{x+36}" y="{110-h-4}" fill="#e2e8f0" font-size="9" text-anchor="middle">{int(score*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Bimanual Grasp Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 2fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Bimanual Grasp Planner — GR00T N2.0 Readiness</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">+12pp</div><div class="ml">SR Gain (bimanual tasks)</div></div>
  <div class="m"><div class="mv">0.81</div><div class="ml">Synchrony Score (pass)</div></div>
  <div class="m"><div class="mv">38%</div><div class="ml">Workspace Overlap</div></div>
  <div class="m"><div class="mv">Jun 2026</div><div class="ml">N2.0 Migration Target</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Workspace Overlap</h3>
    <svg viewBox="0 0 400 290" width="100%">
      <rect width="400" height="290" fill="#0f172a" rx="6"/>
      {workspace_svg}
    </svg>
  </div>
  <div class="card">
    <h3>Dual-Arm Coordination Timeline</h3>
    <svg viewBox="0 0 430 130" width="100%">
      <line x1="25" y1="10" x2="25" y2="120" stroke="#334155" stroke-width="1"/>
      {timeline_svg}
    </svg>
  </div>
  <div class="card">
    <h3>Synchrony by Task</h3>
    <svg viewBox="0 0 430 140" width="100%">
      <line x1="15" y1="10" x2="15" y2="115" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="115" x2="425" y2="115" stroke="#334155" stroke-width="1"/>
      {sync_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Bimanual Grasp Planner")
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
