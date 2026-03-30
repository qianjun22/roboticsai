"""Gripper State Machine — FastAPI port 8500"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8500

def build_html():
    states = [
        ("open", 60, 60, "#22c55e"),
        ("pre-grasp", 200, 60, "#38bdf8"),
        ("approaching", 340, 60, "#f59e0b"),
        ("contact", 200, 160, "#C74634"),
        ("grasping", 60, 200, "#a78bfa"),
        ("lifted", 340, 200, "#22c55e"),
    ]
    
    transitions = [
        ("open", "pre-grasp", 0.95),
        ("pre-grasp", "approaching", 0.92),
        ("approaching", "contact", 0.89),
        ("contact", "grasping", 0.82),
        ("grasping", "lifted", 0.91),
        ("contact", "pre-grasp", 0.11),  # retry
        ("approaching", "open", 0.08),   # abort
    ]
    
    state_map = {s[0]: (s[1], s[2]) for s in states}
    
    fsm_svg = ""
    for name, x, y, col in states:
        fsm_svg += f'<circle cx="{x}" cy="{y}" r="28" fill="{col}" fill-opacity="0.2" stroke="{col}" stroke-width="2"/>'
        fsm_svg += f'<text x="{x}" y="{y-4}" text-anchor="middle" fill="{col}" font-size="9" font-weight="bold">{name}</text>'
    
    # draw transition arrows
    for from_state, to_state, prob in transitions:
        x1, y1 = state_map[from_state]
        x2, y2 = state_map[to_state]
        col = "#22c55e" if prob > 0.8 else ("#f59e0b" if prob > 0.5 else "#ef4444")
        mx, my = (x1+x2)/2, (y1+y2)/2
        fsm_svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{1.5}" stroke-dasharray="4,2" opacity="0.7"/>'
        fsm_svg += f'<text x="{mx}" y="{my}" text-anchor="middle" fill="{col}" font-size="9">{prob:.0%}</text>'
    
    # state timeline - 200 episodes
    timeline_episodes = list(range(20))
    state_durations = [
        ("approaching", [random.uniform(0.8, 2.2) for _ in timeline_episodes], "#f59e0b"),
        ("contact", [random.uniform(0.5, 1.8) for _ in timeline_episodes], "#C74634"),
        ("grasping", [random.uniform(1.2, 3.5) for _ in timeline_episodes], "#a78bfa"),
    ]
    
    timeline_svg = ""
    for phase_i, (phase, durs, col) in enumerate(state_durations):
        pts = []
        for i, d in enumerate(durs):
            x = i * 500 / 19
            y = (1 - (d - 0.5) / 3.0) * 60 + phase_i * 25
            pts.append(f"{x:.1f},{y:.1f}")
        timeline_svg += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="1.5"/>'
        timeline_svg += f'<text x="505" y="{phase_i*25+35}" fill="{col}" font-size="9">{phase}</text>'
    
    return f"""<!DOCTYPE html><html><head><title>Gripper State Machine</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Gripper State Machine</h1><span>port {PORT} · 6-state FSM</span></div>
<div class="grid">
<div class="card"><h3>Lift Success Rate</h3><div class="stat">75%</div><div class="sub">contact→grasp→lift chain</div></div>
<div class="card"><h3>Contact→Grasp</h3><div class="stat">82%</div><div class="sub">critical transition · target 90%</div></div>
<div class="card"><h3>FSM Diagram</h3>
<svg width="100%" viewBox="0 0 400 260" style="background:#0f172a">{fsm_svg}</svg></div>
<div class="card"><h3>Phase Duration Timeline (20 episodes)</h3>
<svg width="100%" viewBox="0 0 560 100">{timeline_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Gripper State Machine")
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
