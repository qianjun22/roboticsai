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

TASKS = ["reach_cube","grasp_cube","lift_cube","pick_place","stack","pour","insert","bimanual"]
DIFFICULTY = [1, 2, 3, 3, 4, 5, 5, 5]
MASTERY = [0.94, 0.89, 0.81, 0.74, 0.61, 0.0, 0.0, 0.0]
STAGES = ["reach_only","grasp_focus","lift_and_hold","full_precision","expert_generalize"]
STAGE_SR = [0.38, 0.55, 0.71, 0.81, 0.83]

def build_html():
    # --- SVG 1: 8 tasks x 5 difficulty grid ---
    cw, ch, pad = 72, 44, 8
    svg1_w = pad + len(TASKS)*(cw+pad)
    svg1_h = pad + 5*(ch+pad) + 30
    cells = []
    for ti, (task, mastery, diff) in enumerate(zip(TASKS, MASTERY, DIFFICULTY)):
        for di in range(1, 6):
            x = pad + ti*(cw+pad)
            y = pad + (5-di)*(ch+pad)
            if di > diff:
                fill = "#1e293b"; label = ""
            elif mastery == 0.0:
                fill = "#374151"; label = "locked"
            else:
                g = int(mastery * 200)
                r = int((1-mastery)*180 + 60)
                fill = f"rgb({r},{g},60)"
                label = f"{int(mastery*100)}%"
            cells.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="4" fill="{fill}" stroke="#334155" stroke-width="1"/>')
            cells.append(f'<text x="{x+cw//2}" y="{y+ch//2+4}" text-anchor="middle" font-size="10" fill="#e2e8f0">{label}</text>')
    for ti, task in enumerate(TASKS):
        x = pad + ti*(cw+pad) + cw//2
        cells.append(f'<text x="{x}" y="{svg1_h-6}" text-anchor="middle" font-size="9" fill="#94a3b8" transform="rotate(-20,{x},{svg1_h-6})">{task}</text>')
    for di in range(1, 6):
        y = pad + (5-di)*(ch+pad) + ch//2 + 4
        cells.append(f'<text x="4" y="{y}" font-size="9" fill="#94a3b8">d{di}</text>')
    svg1 = f'<svg width="{svg1_w}" height="{svg1_h}" style="background:#1e293b;border-radius:8px">{"".join(cells)}</svg>'

    # --- SVG 2: SR trajectory per stage (staircase) ---
    W2, H2, mx, my = 540, 200, 50, 20
    iw = (W2 - mx - 20) // len(STAGES)
    pts = []
    bars = []
    for i, (stage, sr) in enumerate(zip(STAGES, STAGE_SR)):
        x1 = mx + i*iw
        x2 = mx + (i+1)*iw
        y = my + int((1-sr)*(H2-my-30))
        y_base = H2 - 30
        bars.append(f'<rect x="{x1+2}" y="{y}" width="{iw-4}" height="{y_base-y}" fill="#1d4ed8" opacity="0.25"/>')
        pts.append(f"{x1},{y}")
        pts.append(f"{x2},{y}")
        bars.append(f'<text x="{(x1+x2)//2}" y="{y-5}" text-anchor="middle" font-size="10" fill="#38bdf8">{sr:.2f}</text>')
        bars.append(f'<text x="{(x1+x2)//2}" y="{H2-14}" text-anchor="middle" font-size="8" fill="#94a3b8">{stage[:8]}</text>')
    polyline = f'<polyline points="{",".join(pts)}" fill="none" stroke="#C74634" stroke-width="2.5"/>'
    axes = (f'<line x1="{mx}" y1="{my}" x2="{mx}" y2="{H2-30}" stroke="#475569" stroke-width="1"/>')
    svg2 = f'<svg width="{W2}" height="{H2}" style="background:#1e293b;border-radius:8px">{axes}{"".join(bars)}{polyline}</svg>'

    stats = [
        ("Composite Mastery", "0.81", "v2: 0.71 (+14%)"),
        ("Tasks Mastered", "3", "reach, grasp, lift"),
        ("Active Tasks", "2", "pick_place, stack"),
        ("Locked Tasks", "3", "pour, insert, bimanual"),
    ]
    stat_html = "".join(f'<div style="background:#1e293b;border-radius:8px;padding:14px 20px;min-width:160px"><div style="color:#94a3b8;font-size:11px">{s[0]}</div><div style="color:#38bdf8;font-size:26px;font-weight:700">{s[1]}</div><div style="color:#64748b;font-size:11px">{s[2]}</div></div>' for s in stats)

    return f"""<!DOCTYPE html><html><head><title>Curriculum v3</title>
<style>body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:sans-serif}}h1{{color:#C74634;font-size:20px;margin-bottom:4px}}.sub{{color:#64748b;font-size:13px;margin-bottom:20px}}.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}.chart{{margin-bottom:20px}}.label{{color:#94a3b8;font-size:12px;margin-bottom:6px}}</style></head>
<body><h1>Curriculum v3</h1><div class="sub">Adaptive curriculum scheduler with mastery-based task unlocking — port {PORT}</div>
<div class="stats">{stat_html}</div>
<div class="chart"><div class="label">Task Mastery Grid (8 tasks × 5 difficulty levels)</div>{svg1}</div>
<div class="chart"><div class="label">Success Rate Trajectory per Curriculum Stage</div>{svg2}</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Curriculum v3")
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
