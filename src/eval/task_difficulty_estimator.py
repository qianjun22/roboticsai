"""Task Difficulty Estimator — FastAPI port 8385"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8385

def build_html():
    random.seed(7)
    tasks = [
        ("reach_cube",0.94,32,"easy"),("press_button",0.91,28,"easy"),
        ("grasp_cube",0.82,45,"easy"),("push_cube",0.78,52,"easy"),
        ("lift_cube",0.71,63,"medium"),("place_on_target",0.68,71,"medium"),
        ("stack_cubes",0.61,89,"medium"),("pour_beads",0.52,94,"medium"),
        ("insert_peg",0.44,112,"hard"),("open_drawer",0.39,121,"hard"),
        ("fold_cloth",0.31,138,"hard"),("cut_tape",0.22,156,"hard"),
        ("thread_needle",0.18,172,"hard"),("assemble_gear",0.14,191,"hard"),
        ("bimanual_pass",0.09,214,"expert"),("bimanual_fold",0.07,231,"expert"),
        ("humanoid_walk",0.05,247,"expert"),("tool_use",0.11,203,"expert"),
        ("loco_manip",0.03,261,"expert"),("whole_body",0.02,278,"expert"),
    ]
    # scatter SVG
    sw, sh = 600, 300
    scatter = f'<svg width="{sw}" height="{sh}">'
    scatter += '<text x="290" y="290" text-anchor="middle" fill="#94a3b8" font-size="11">Avg Episode Length (steps)</text>'
    scatter += '<text x="12" y="150" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,12,150)">SR</text>'
    color_map = {"easy":"#22c55e","medium":"#f59e0b","hard":"#ef4444","expert":"#a78bfa"}
    for t, sr, eps, diff in tasks:
        cx = int(40 + (eps - 28) / (278 - 28) * 520)
        cy = int(sh - 30 - sr * 230)
        scatter += f'<circle cx="{cx}" cy="{cy}" r="7" fill="{color_map[diff]}" opacity="0.8"/>'
        scatter += f'<title>{t}: SR={sr}, eps={eps}</title>'
    # legend
    for i, (d, c) in enumerate([("easy","#22c55e"),("medium","#f59e0b"),("hard","#ef4444"),("expert","#a78bfa")]):
        scatter += f'<circle cx="{480+i*0}" cy="{20+i*18}" r="5" fill="{c}"/>'
        scatter += f'<text x="490" y="{24+i*18}" fill="{c}" font-size="10">{d}</text>'
    scatter += '</svg>'

    # calibration bar SVG
    calib_data = [("reach_cube",0.94,0.91),("grasp_cube",0.82,0.85),("lift_cube",0.71,0.68),
                  ("stack_cubes",0.61,0.63),("insert_peg",0.44,0.40),("fold_cloth",0.31,0.28)]
    bar_svg = f'<svg width="520" height="200">'
    for i, (t, measured, estimated) in enumerate(calib_data):
        y = 15 + i * 28
        mw = int(measured * 300)
        ew = int(estimated * 300)
        bar_svg += f'<rect x="130" y="{y}" width="{mw}" height="11" fill="#38bdf8" opacity="0.7" rx="2"/>'
        bar_svg += f'<rect x="130" y="{y+12}" width="{ew}" height="9" fill="#f59e0b" opacity="0.8" rx="2"/>'
        bar_svg += f'<text x="125" y="{y+10}" text-anchor="end" fill="#e2e8f0" font-size="9">{t[:10]}</text>'
    bar_svg += '<text x="200" y="195" fill="#38bdf8" font-size="9">measured</text>'
    bar_svg += '<text x="300" y="195" fill="#f59e0b" font-size="9">estimated</text>'
    bar_svg += '</svg>'

    return f"""<!DOCTYPE html>
<html><head><title>Task Difficulty Estimator — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}}
.stat{{display:inline-block;margin:0 20px;text-align:center}}
.big{{font-size:28px;font-weight:bold;color:#C74634}}
.easy{{color:#22c55e}}.med{{color:#f59e0b}}.hard{{color:#ef4444}}.expert{{color:#a78bfa}}
</style></head><body>
<h1>Task Difficulty Estimator — Port {PORT}</h1>
<div class="card">
  <div class="stat"><div class="big">20</div><div>Tasks Analyzed</div></div>
  <div class="stat"><div class="big easy">4</div><div>Easy (SR≥0.75)</div></div>
  <div class="stat"><div class="big med">4</div><div>Medium</div></div>
  <div class="stat"><div class="big hard">6</div><div>Hard</div></div>
  <div class="stat"><div class="big expert">5</div><div>Expert</div></div>
  <div class="stat"><div class="big" style="color:#22c55e">0.08</div><div>RMSE</div></div>
</div>
<div class="card">
  <h2>Task Difficulty Scatter (SR vs Episode Length)</h2>
  {scatter}
</div>
<div class="card">
  <h2>Calibration: Estimated vs Measured SR</h2>
  {bar_svg}
</div>
<div class="card">
  <h2>Difficulty Tier Thresholds</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr style="color:#94a3b8"><th>Tier</th><th>SR Range</th><th>Avg Steps</th><th>Recommended Demo Count</th></tr>
    <tr><td class="easy">Easy</td><td>≥0.75</td><td>28–52</td><td>200</td></tr>
    <tr><td class="med">Medium</td><td>0.50–0.75</td><td>63–94</td><td>500</td></tr>
    <tr><td class="hard">Hard</td><td>0.20–0.50</td><td>112–172</td><td>1000</td></tr>
    <tr><td class="expert">Expert</td><td>&lt;0.20</td><td>191–278</td><td>2000+</td></tr>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Task Difficulty Estimator")
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
