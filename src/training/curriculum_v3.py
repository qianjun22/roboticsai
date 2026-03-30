"""Curriculum v3 — FastAPI port 8384"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8384

def build_html():
    tasks = ["reach","grasp","lift","place","push","stack","pour","insert"]
    levels = [1,2,3,4,5]
    random.seed(42)
    # per-task mastery (0-1)
    mastery = {t: round(random.uniform(0.4, 0.95), 2) for t in tasks}
    mastery["reach"] = 0.94
    mastery["grasp"] = 0.82
    mastery["lift"] = 0.78
    mastery["place"] = 0.73
    mastery["push"] = 0.71
    mastery["stack"] = 0.61
    mastery["pour"] = 0.44
    mastery["insert"] = 0.23

    # build SVG bar chart of mastery
    bar_w = 60
    spacing = 80
    svg_w = len(tasks) * spacing + 60
    svg_h = 200
    bars = ""
    for i, t in enumerate(tasks):
        x = 40 + i * spacing
        h = int(mastery[t] * 150)
        y = 160 - h
        color = "#22c55e" if mastery[t] >= 0.75 else ("#f59e0b" if mastery[t] >= 0.5 else "#ef4444")
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>'
        bars += f'<text x="{x+bar_w//2}" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">{t[:5]}</text>'
        bars += f'<text x="{x+bar_w//2}" y="{y-4}" text-anchor="middle" fill="#e2e8f0" font-size="10">{mastery[t]}</text>'
    # threshold line
    threshold_y = 160 - int(0.7 * 150)
    bars += f'<line x1="30" y1="{threshold_y}" x2="{svg_w-10}" y2="{threshold_y}" stroke="#f59e0b" stroke-dasharray="4,3" stroke-width="1.5"/>'
    bars += f'<text x="{svg_w-8}" y="{threshold_y+4}" fill="#f59e0b" font-size="10">0.70</text>'
    mastery_svg = f'<svg width="{svg_w}" height="{svg_h}">{bars}</svg>'

    # SR trajectory stages
    stages = ["easy_single","medium_seq","hard_seq","full_combined","adaptive_v3"]
    stage_sr = [0.51, 0.63, 0.71, 0.76, 0.81]
    pts = ""
    sw2, sh2 = 500, 160
    for i, (s, sr) in enumerate(zip(stages, stage_sr)):
        cx = 60 + i * 90
        cy = int((1 - sr) * 120) + 20
        pts += f'{cx},{cy} '
        color = "#22c55e" if sr >= 0.78 else "#38bdf8"
        pts = pts.rstrip()
    poly_pts = " ".join([f"{60+i*90},{int((1-sr)*120)+20}" for i, sr in enumerate(stage_sr)])
    sr_svg = f'<svg width="{sw2}" height="{sh2}"><polyline points="{poly_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    for i, (s, sr) in enumerate(zip(stages, stage_sr)):
        cx = 60 + i * 90
        cy = int((1 - sr) * 120) + 20
        sr_svg += f'<circle cx="{cx}" cy="{cy}" r="5" fill="#C74634"/>'
        sr_svg += f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#e2e8f0" font-size="9">{sr}</text>'
        sr_svg += f'<text x="{cx}" y="148" text-anchor="middle" fill="#94a3b8" font-size="8">{s[:8]}</text>'
    sr_svg += '</svg>'

    composite_sr = 0.81
    unlocked = sum(1 for v in mastery.values() if v >= 0.70)

    return f"""<!DOCTYPE html>
<html><head><title>Curriculum v3 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}}
.stat{{display:inline-block;margin:0 20px;text-align:center}}
.big{{font-size:28px;font-weight:bold;color:#C74634}}
.green{{color:#22c55e}}.amber{{color:#f59e0b}}.red{{color:#ef4444}}
</style></head><body>
<h1>Curriculum v3 — Port {PORT}</h1>
<div class="card">
  <div class="stat"><div class="big">{composite_sr}</div><div>Composite SR</div></div>
  <div class="stat"><div class="big" style="color:#22c55e">{unlocked}/8</div><div>Tasks Unlocked</div></div>
  <div class="stat"><div class="big" style="color:#38bdf8">0.70</div><div>Mastery Threshold</div></div>
  <div class="stat"><div class="big" style="color:#f59e0b">v3</div><div>Curriculum Version</div></div>
</div>
<div class="card">
  <h2>Task Mastery (mastery-based unlock)</h2>
  {mastery_svg}
</div>
<div class="card">
  <h2>SR Trajectory by Curriculum Stage</h2>
  {sr_svg}
</div>
<div class="card">
  <h2>v2 vs v3 Comparison</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr style="color:#94a3b8"><th>Metric</th><th>v2</th><th>v3</th><th>Delta</th></tr>
    <tr><td>Composite SR</td><td>0.71</td><td class="green">0.81</td><td class="green">+0.10</td></tr>
    <tr><td>Tasks Mastered</td><td>4</td><td class="green">5</td><td class="green">+1</td></tr>
    <tr><td>Curriculum Stages</td><td>4</td><td>5</td><td>+1</td></tr>
    <tr><td>Adaptation Speed</td><td>static</td><td class="green">adaptive</td><td>—</td></tr>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Curriculum v3")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "composite_sr": 0.81}

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
