"""GR00T N2 Readiness Evaluator — FastAPI port 8818"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8818

def build_html():
    random.seed(42)
    # Simulate N2 readiness scores across eval dimensions
    dimensions = [
        "Language Grounding", "Visual Perception", "Motor Planning",
        "Object Manipulation", "Scene Understanding", "Generalization",
        "Sim-to-Real Transfer", "Safety Compliance"
    ]
    scores = [round(0.55 + 0.40 * (math.sin(i * 1.3) * 0.5 + 0.5) + random.uniform(-0.04, 0.04), 3) for i in range(len(dimensions))]
    overall = round(sum(scores) / len(scores), 3)

    # Radar chart polygon (SVG)
    cx, cy, r = 200, 200, 150
    n = len(dimensions)
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    points_outer = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]
    points_score = [(cx + r * s * math.cos(a), cy + r * s * math.sin(a)) for s, a in zip(scores, angles)]
    polygon_outer = " ".join(f"{x:.1f},{y:.1f}" for x, y in points_outer)
    polygon_score = " ".join(f"{x:.1f},{y:.1f}" for x, y in points_score)
    axis_lines = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#334155" stroke-width="1"/>'
        for px, py in points_outer
    )
    labels = "".join(
        f'<text x="{cx + (r + 18) * math.cos(a):.1f}" y="{cy + (r + 18) * math.sin(a):.1f}" '
        f'fill="#94a3b8" font-size="9" text-anchor="middle" dominant-baseline="middle">{d.split()[0]}</text>'
        for d, a in zip(dimensions, angles)
    )

    # Trend line for readiness over eval epochs (last 20 checkpoints)
    epochs = 20
    trend = [round(0.45 + 0.30 * (1 - math.exp(-i / 6)) + 0.04 * math.sin(i * 0.7) + random.uniform(-0.01, 0.01), 3) for i in range(epochs)]
    tw, th = 500, 100
    tpad = 10
    tx_scale = (tw - 2 * tpad) / (epochs - 1)
    ty_min, ty_max = 0.4, 0.85
    ty_scale = (th - 2 * tpad) / (ty_max - ty_min)
    trend_pts = " ".join(
        f"{tpad + i * tx_scale:.1f},{th - tpad - (v - ty_min) * ty_scale:.1f}"
        for i, v in enumerate(trend)
    )

    # Per-task success rates
    tasks = ["Pick-Place", "Stack", "Pour", "Wipe", "Open Drawer", "Push Button"]
    task_scores = [round(0.50 + 0.45 * math.sin(i * 0.9 + 0.3) * 0.5 + 0.45 * 0.5 + random.uniform(-0.05, 0.05), 2) for i in range(len(tasks))]
    bar_svg_parts = []
    bar_w, bar_h_max, bar_gap = 55, 80, 8
    for idx, (t, s) in enumerate(zip(tasks, task_scores)):
        bx = idx * (bar_w + bar_gap)
        bh = s * bar_h_max
        color = "#22c55e" if s >= 0.75 else ("#f59e0b" if s >= 0.55 else "#ef4444")
        bar_svg_parts.append(
            f'<rect x="{bx}" y="{bar_h_max - bh:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w/2:.1f}" y="{bar_h_max - bh - 4:.1f}" fill="#e2e8f0" font-size="10" text-anchor="middle">{s:.0%}</text>'
            f'<text x="{bx + bar_w/2:.1f}" y="{bar_h_max + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">{t}</text>'
        )
    bar_svg = "".join(bar_svg_parts)
    bar_total_w = len(tasks) * (bar_w + bar_gap)

    rows = "".join(
        f'<tr><td style="padding:6px 12px">{d}</td>'
        f'<td style="padding:6px 12px"><div style="width:{int(s*200)}px;height:12px;background:linear-gradient(90deg,#38bdf8,#0ea5e9);border-radius:3px;display:inline-block"></div></td>'
        f'<td style="padding:6px 12px;color:{"#22c55e" if s>=0.75 else ("#f59e0b" if s>=0.55 else "#ef4444")}">{s:.1%}</td></tr>'
        for d, s in zip(dimensions, scores)
    )

    readiness_color = "#22c55e" if overall >= 0.75 else ("#f59e0b" if overall >= 0.55 else "#ef4444")

    return f"""<!DOCTYPE html><html><head><title>GR00T N2 Readiness Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.5rem}}
.subtitle{{color:#64748b;padding:4px 20px 16px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:flex;flex-wrap:wrap;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;flex:1;min-width:280px}}
.badge{{display:inline-block;padding:4px 14px;border-radius:20px;font-size:1.1rem;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
tr:nth-child(even){{background:#243044}}
td{{border-bottom:1px solid #334155}}
</style></head>
<body>
<h1>GR00T N2 Readiness Evaluator</h1>
<div class="subtitle">OCI Robot Cloud — Model checkpoint readiness assessment dashboard | Port {PORT}</div>
<div class="grid">
  <div class="card" style="min-width:200px;max-width:260px;text-align:center">
    <h2>Overall Readiness</h2>
    <div style="font-size:3rem;font-weight:800;color:{readiness_color}">{overall:.1%}</div>
    <div class="badge" style="background:{readiness_color}22;color:{readiness_color};margin-top:8px">
      {'DEPLOY READY' if overall >= 0.75 else ('NEEDS WORK' if overall >= 0.55 else 'NOT READY')}
    </div>
    <div style="color:#64748b;font-size:0.8rem;margin-top:12px">Checkpoint: gr00t-n2-1.6-ft-ep480<br/>Evaluated: {epochs} epochs</div>
  </div>
  <div class="card">
    <h2>Readiness Radar — 8 Eval Dimensions</h2>
    <svg width="400" height="400" viewBox="0 0 400 400">
      <polygon points="{polygon_outer}" fill="none" stroke="#334155" stroke-width="1.5"/>
      {axis_lines}
      <polygon points="{polygon_score}" fill="#38bdf840" stroke="#38bdf8" stroke-width="2"/>
      {labels}
      {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>' for x, y in points_score)}
    </svg>
  </div>
  <div class="card" style="min-width:340px">
    <h2>Dimension Scores</h2>
    <table>
      <thead><tr><th style="text-align:left;padding:6px 12px;color:#64748b">Dimension</th>
        <th style="text-align:left;padding:6px 12px;color:#64748b">Score Bar</th>
        <th style="text-align:left;padding:6px 12px;color:#64748b">Score</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
<div class="grid">
  <div class="card" style="min-width:520px">
    <h2>Per-Task Success Rate</h2>
    <svg width="{bar_total_w}" height="{bar_h_max + 30}" viewBox="0 0 {bar_total_w} {bar_h_max + 30}">
      {bar_svg}
    </svg>
  </div>
  <div class="card" style="min-width:520px">
    <h2>Readiness Trend — Last {epochs} Checkpoints</h2>
    <svg width="{tw}" height="{th + 20}" viewBox="0 0 {tw} {th + 20}">
      <polyline points="{trend_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      {''.join(f'<circle cx="{tpad + i * tx_scale:.1f}" cy="{th - tpad - (v - ty_min) * ty_scale:.1f}" r="3" fill="#38bdf8"/>' for i, v in enumerate(trend))}
      <line x1="{tpad}" y1="{th - tpad - (0.75 - ty_min) * ty_scale:.1f}" x2="{tw - tpad}" y2="{th - tpad - (0.75 - ty_min) * ty_scale:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{tw - tpad - 2}" y="{th - tpad - (0.75 - ty_min) * ty_scale - 4:.1f}" fill="#22c55e" font-size="9" text-anchor="end">deploy threshold 75%</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N2 Readiness Evaluator")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/scores")
    def scores():
        random.seed(42)
        dims = ["Language Grounding", "Visual Perception", "Motor Planning",
                "Object Manipulation", "Scene Understanding", "Generalization",
                "Sim-to-Real Transfer", "Safety Compliance"]
        sc = [round(0.55 + 0.40 * (math.sin(i * 1.3) * 0.5 + 0.5) + random.uniform(-0.04, 0.04), 3) for i in range(len(dims))]
        return {"checkpoint": "gr00t-n2-1.6-ft-ep480", "scores": dict(zip(dims, sc)), "overall": round(sum(sc)/len(sc), 3)}

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
