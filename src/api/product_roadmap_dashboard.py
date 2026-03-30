"""Product Roadmap Dashboard — FastAPI port 8753"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8753

def build_html():
    random.seed(7)

    quarters = ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]
    pillars = [
        ("Foundation",   "#38bdf8", [90, 100, 100, 100]),
        ("Training",     "#a78bfa", [70,  88,  97, 100]),
        ("Inference",    "#34d399", [55,  75,  90,  98]),
        ("Sim-to-Real",  "#fbbf24", [30,  55,  78,  95]),
        ("Fleet Deploy", "#f87171", [10,  35,  60,  85]),
    ]

    # Gantt bars — 20 items, start/end in week offsets (0-52)
    milestones = [
        ("GR00T N1.6 integration",   0,  8,  "done"),
        ("Multi-GPU DDP",             2,  10, "done"),
        ("Isaac Sim SDG pipeline",    4,  14, "done"),
        ("Fine-tune on OCI A100",     6,  16, "done"),
        ("Closed-loop eval v1",       10, 20, "done"),
        ("DAgger v1 rollout",         14, 22, "done"),
        ("CoRL paper submission",     18, 26, "in-progress"),
        ("Sim-to-real validator",     20, 28, "in-progress"),
        ("Fleet deploy agent",        24, 34, "planned"),
        ("Jetson edge packaging",     26, 36, "planned"),
        ("Multi-task curriculum",     28, 38, "planned"),
        ("Policy distillation v2",    30, 40, "planned"),
        ("World model Cosmos v2",     32, 44, "planned"),
        ("OCI marketplace listing",   36, 46, "planned"),
        ("Design partner GA",         40, 50, "planned"),
        ("Safety monitor v2",         38, 48, "planned"),
        ("Embodiment adapter API",    42, 50, "planned"),
        ("AI World demo",             44, 52, "planned"),
        ("Enterprise SDK v2",         46, 52, "planned"),
        ("Production GA launch",      50, 52, "planned"),
    ]

    status_colors = {"done": "#34d399", "in-progress": "#fbbf24", "planned": "#475569"}
    gantt_rows = []
    bar_w = 480
    for i, (name, start, end, status) in enumerate(milestones):
        x = int(start / 52 * bar_w)
        bw = max(4, int((end - start) / 52 * bar_w))
        color = status_colors[status]
        gantt_rows.append(
            f'<g transform="translate(0,{i*22})">' 
            f'<text x="0" y="14" fill="#cbd5e1" font-size="11">{name}</text>'
            f'</g>'
        )
    # Build SVG gantt
    svg_bars = []
    for i, (name, start, end, status) in enumerate(milestones):
        x = int(start / 52 * bar_w)
        bw = max(6, int((end - start) / 52 * bar_w))
        color = status_colors[status]
        y = i * 26 + 2
        svg_bars.append(
            f'<rect x="{x}" y="{y}" width="{bw}" height="18" rx="3" fill="{color}" opacity="0.85"/>'
        )
    # Quarter dividers
    dividers = ""
    for qi, ql in enumerate(quarters):
        dx = int(qi * bar_w / 4)
        dividers += f'<line x1="{dx}" y1="0" x2="{dx}" y2="{len(milestones)*26}" stroke="#334155" stroke-width="1"/>'
        dividers += f'<text x="{dx+4}" y="{len(milestones)*26+14}" fill="#64748b" font-size="10">{ql}</text>'
    gantt_total_h = len(milestones) * 26 + 20
    gantt_svg = (
        f'<svg width="{bar_w}" height="{gantt_total_h}" style="display:block">'
        + dividers + "".join(svg_bars) + "</svg>"
    )

    # Radar chart — 6 capability axes
    axes = ["Simulation", "Training", "Inference", "Deploy", "Safety", "Observability"]
    scores_now  = [0.75, 0.82, 0.70, 0.45, 0.55, 0.68]
    scores_eoy  = [0.95, 0.97, 0.90, 0.85, 0.88, 0.92]
    cx, cy, r = 150, 150, 110
    n = len(axes)
    def radar_pt(score, idx, radius=r):
        angle = math.pi / 2 - 2 * math.pi * idx / n
        x = cx + radius * score * math.cos(angle)
        y = cy - radius * score * math.sin(angle)
        return x, y
    def poly_pts(scores):
        return " ".join(f"{radar_pt(s,i)[0]:.1f},{radar_pt(s,i)[1]:.1f}" for i, s in enumerate(scores))
    axis_lines = ""
    axis_labels = ""
    for i, label in enumerate(axes):
        ex, ey = radar_pt(1.0, i)
        axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r + 18) * math.cos(math.pi / 2 - 2 * math.pi * i / n)
        ly = cy - (r + 18) * math.sin(math.pi / 2 - 2 * math.pi * i / n)
        axis_labels += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{label}</text>'
    # Grid rings
    rings = ""
    for lvl in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{radar_pt(lvl,i)[0]:.1f},{radar_pt(lvl,i)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#1e3a5f" stroke-width="1"/>'
    radar_svg = (
        '<svg width="300" height="300" style="display:block;background:#0d1b2e;border-radius:8px">'
        + rings + axis_lines + axis_labels
        + f'<polygon points="{poly_pts(scores_now)}" fill="#38bdf844" stroke="#38bdf8" stroke-width="2"/>'
        + f'<polygon points="{poly_pts(scores_eoy)}" fill="#a78bfa33" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="5,3"/>'
        + '</svg>'
    )

    # Completion progress bars per pillar
    current_q = 1  # Q2 progress index
    pillar_bars = ""
    for name, color, completions in pillars:
        pct = completions[current_q]
        pillar_bars += (
            f'<div style="margin-bottom:12px">' 
            f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">'
            f'<span style="color:{color}">{name}</span><span style="color:#94a3b8">{pct}%</span></div>'
            f'<div style="background:#1e293b;border-radius:4px;height:10px">'
            f'<div style="background:{color};width:{pct}%;height:10px;border-radius:4px"></div>'
            f'</div></div>'
        )

    done_count = sum(1 for m in milestones if m[3] == "done")
    inprog_count = sum(1 for m in milestones if m[3] == "in-progress")
    planned_count = sum(1 for m in milestones if m[3] == "planned")
    on_track_pct = 87

    return f"""<!DOCTYPE html><html><head><title>Product Roadmap Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.subtitle{{color:#94a3b8;margin-bottom:24px;font-size:14px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:16px}}
.card{{background:#1e293b;padding:20px;margin:0 0 16px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;text-align:center}}
.stat .val{{font-size:28px;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:12px;color:#94a3b8;margin-top:4px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.legend{{display:flex;gap:16px;font-size:12px;margin-bottom:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}}
.gantt-labels{{float:left;width:180px;margin-right:8px}}
.gantt-labels div{{height:26px;line-height:26px;font-size:11px;color:#cbd5e1;overflow:hidden;white-space:nowrap}}
.gantt-wrap{{display:flex;align-items:flex-start}}
</style></head>
<body>
<h1>Product Roadmap Dashboard</h1>
<p class="subtitle">OCI Robot Cloud — milestone tracking, capability radar, and pillar progress — port {PORT}</p>
<div class="grid">
  <div class="stat"><div class="val" style="color:#34d399">{done_count}</div><div class="lbl">Milestones Done</div></div>
  <div class="stat"><div class="val" style="color:#fbbf24">{inprog_count}</div><div class="lbl">In Progress</div></div>
  <div class="stat"><div class="val" style="color:#475569">{planned_count}</div><div class="lbl">Planned</div></div>
  <div class="stat"><div class="val" style="color:#a78bfa">{on_track_pct}%</div><div class="lbl">On-Track Rate</div></div>
</div>
<div class="card">
  <h2>Milestone Gantt — FY2026</h2>
  <div class="legend">
    <span><span class="dot" style="background:#34d399"></span>Done</span>
    <span><span class="dot" style="background:#fbbf24"></span>In Progress</span>
    <span><span class="dot" style="background:#475569"></span>Planned</span>
  </div>
  <div class="gantt-wrap">
    <div class="gantt-labels">
      {''.join(f'<div>{m[0]}</div>' for m in milestones)}
    </div>
    {gantt_svg}
  </div>
</div>
<div class="two-col">
  <div class="card">
    <h2>Capability Radar</h2>
    <div class="legend">
      <span><span class="dot" style="background:#38bdf8"></span>Current</span>
      <span><span class="dot" style="background:#a78bfa"></span>EoY Target</span>
    </div>
    {radar_svg}
  </div>
  <div class="card">
    <h2>Pillar Completion (Q2 2026)</h2>
    {pillar_bars}
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Product Roadmap Dashboard")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/summary")
    def summary():
        return {
            "port": PORT,
            "total_milestones": 20,
            "done": 6,
            "in_progress": 2,
            "planned": 12,
            "on_track_pct": 87,
            "current_quarter": "Q2 2026",
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
