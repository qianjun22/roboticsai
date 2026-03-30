"""GR00T N2 Readiness — FastAPI port 8366"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8366

def build_html():
    checklist = [
        ("API compatibility layer", True, "v2 endpoints backward-compat with N1.6 SDK"),
        ("Bimanual support", False, "New capability in N2.0 — adapter code needed"),
        ("Cosmos WM integration", True, "World model already integrated via N1.6"),
        ("Tokenizer update", False, "N2.0 uses new visual tokenizer — re-encode demos"),
        ("LoRA adapter migration", True, "Adapter weights transferable with fine-tuning"),
        ("Inference pipeline update", True, "TensorRT plan rebuild needed, 2h process"),
        ("Customer SDK update", False, "v0.4.0 SDK required for N2.0 endpoints"),
        ("Performance validation", True, "Benchmark suite ready (sim_benchmark_v2)"),
    ]
    
    check_rows = ""
    for name, done, note in checklist:
        icon = "✓" if done else "○"
        color = "#22c55e" if done else "#f59e0b"
        check_rows += f"""<div style="display:flex;align-items:flex-start;padding:8px 0;border-bottom:1px solid #1e293b">
<span style="color:{color};font-size:1.2em;margin-right:8px;min-width:20px">{icon}</span>
<div>
<div style="color:#e2e8f0;font-size:0.9em">{name}</div>
<div style="color:#64748b;font-size:0.75em;margin-top:2px">{note}</div>
</div></div>"""

    ready_count = sum(1 for _, done, _ in checklist if done)
    readiness_pct = int(ready_count / len(checklist) * 100)
    
    # Capability radar (6 dims)
    dims = ["Manipulation", "Bimanual", "Vision", "Language", "Force-Ctrl", "Transfer"]
    n1_vals = [0.78, 0.0, 0.82, 0.71, 0.65, 0.74]
    n2_vals = [0.86, 0.62, 0.91, 0.84, 0.72, 0.83]
    
    cx, cy, r = 200, 120, 90
    n1_pts = []
    n2_pts = []
    for i, (n1, n2) in enumerate(zip(n1_vals, n2_vals)):
        angle = math.pi/2 - i * 2*math.pi/6
        n1_pts.append((cx + r*n1*math.cos(angle), cy - r*n1*math.sin(angle)))
        n2_pts.append((cx + r*n2*math.cos(angle), cy - r*n2*math.sin(angle)))
    
    n1_poly = " ".join(f"{x},{y}" for x,y in n1_pts)
    n2_poly = " ".join(f"{x},{y}" for x,y in n2_pts)
    
    grid_lines = ""
    label_positions = []
    for i, dim in enumerate(dims):
        angle = math.pi/2 - i * 2*math.pi/6
        gx = cx + r * math.cos(angle)
        gy = cy - r * math.sin(angle)
        grid_lines += f'<line x1="{cx}" y1="{cy}" x2="{gx}" y2="{gy}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r+15) * math.cos(angle)
        ly = cy - (r+15) * math.sin(angle)
        grid_lines += f'<text x="{lx}" y="{ly}" text-anchor="middle" fill="#94a3b8" font-size="9">{dim}</text>'
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = " ".join(f"{cx+r*ring*math.cos(math.pi/2-i*2*math.pi/6)},{cy-r*ring*math.sin(math.pi/2-i*2*math.pi/6)}" for i in range(7))
        grid_lines += f'<polygon points="{ring_pts}" fill="none" stroke="#334155" stroke-width="0.5"/>'

    # Migration timeline
    weeks = ["W1", "W2", "W3", "W4", "W5", "W6"]
    tasks_timeline = [
        ("Tokenizer update", 1, 1, "#f59e0b"),
        ("Bimanual adapter", 1, 2, "#38bdf8"),
        ("SDK v0.4.0", 2, 1, "#a78bfa"),
        ("Pipeline rebuild", 3, 1, "#22c55e"),
        ("Customer migration", 4, 2, "#C74634"),
    ]
    gantt_svg = ""
    for i, w in enumerate(weeks):
        gantt_svg += f'<text x="{50+i*70}" y="20" fill="#64748b" font-size="9">{w}</text>'
    for i, (task, start, dur, color) in enumerate(tasks_timeline):
        x = 50 + (start-1)*70
        w = dur * 70
        y = 30 + i * 25
        gantt_svg += f'<rect x="{x}" y="{y}" width="{w}" height="18" fill="{color}" opacity="0.7" rx="3"/>'
        gantt_svg += f'<text x="{x+5}" y="{y+13}" fill="#fff" font-size="8">{task}</text>'

    return f"""<!DOCTYPE html><html><head><title>GR00T N2 Readiness — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>GR00T N2 Readiness</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{readiness_pct}%</div><div style="font-size:0.75em;color:#94a3b8">Ready</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{ready_count}/{len(checklist)}</div><div style="font-size:0.75em;color:#94a3b8">Checklist</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">2 wks</div><div style="font-size:0.75em;color:#94a3b8">Migration Est.</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">Jun 2026</div><div style="font-size:0.75em;color:#94a3b8">Target</div></div>
</div>
<div class="grid">
<div class="card"><h2>Migration Checklist</h2>
{check_rows}
</div>
<div class="card"><h2>N1.6 vs N2.0 Capability Radar</h2>
<svg viewBox="0 0 400 260"><rect width="400" height="260" fill="#0f172a" rx="4"/>
{grid_lines}
<polygon points="{n1_poly}" fill="#38bdf8" fill-opacity="0.2" stroke="#38bdf8" stroke-width="1.5"/>
<polygon points="{n2_poly}" fill="#22c55e" fill-opacity="0.2" stroke="#22c55e" stroke-width="2"/>
<text x="310" y="230" fill="#38bdf8" font-size="9">■ N1.6</text>
<text x="350" y="230" fill="#22c55e" font-size="9">■ N2.0</text>
</svg>
</div>
</div>
<div class="card" style="margin-top:16px"><h2>Migration Timeline (6 weeks)</h2>
<svg viewBox="0 0 500 160"><rect width="500" height="160" fill="#0f172a" rx="4"/>
{gantt_svg}
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N2 Readiness")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"readiness_pct":73,"migration_weeks":2}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()
