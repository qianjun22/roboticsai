"""robot_skill_library.py — FastAPI service on port 8275

Catalog of composable robot skills available for multi-task GR00T policies.
Tracks mastery levels, composition relationships, and acquisition velocity.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SKILLS = [
    {"id": "reach",    "sr": 0.94, "stage": "mastered",  "x": 160, "y": 200, "v_ver": "v1"},
    {"id": "grasp",    "sr": 0.82, "stage": "mastered",  "x": 280, "y": 130, "v_ver": "v1"},
    {"id": "push",     "sr": 0.78, "stage": "mastered",  "x": 280, "y": 270, "v_ver": "v1"},
    {"id": "pull",     "sr": 0.75, "stage": "mastered",  "x": 400, "y": 200, "v_ver": "v2"},
    {"id": "rotate",   "sr": 0.69, "stage": "learning",  "x": 400, "y": 80,  "v_ver": "v2"},
    {"id": "pour",     "sr": 0.61, "stage": "learning",  "x": 520, "y": 140, "v_ver": "v2"},
    {"id": "wipe",     "sr": 0.58, "stage": "learning",  "x": 520, "y": 270, "v_ver": "v2"},
    {"id": "press",    "sr": 0.54, "stage": "learning",  "x": 400, "y": 330, "v_ver": "v3"},
    {"id": "insert",   "sr": 0.23, "stage": "learning",  "x": 640, "y": 200, "v_ver": "v3"},
    {"id": "handover", "sr": 0.41, "stage": "learning",  "x": 640, "y": 80,  "v_ver": "v3"},
    {"id": "fold",     "sr": 0.00, "stage": "planned",   "x": 760, "y": 140, "v_ver": "v4"},
    {"id": "cut",      "sr": 0.00, "stage": "planned",   "x": 760, "y": 270, "v_ver": "v4"},
]

SKILL_INDEX = {s["id"]: s for s in SKILLS}

EDGES = [
    ("reach", "grasp"),
    ("reach", "push"),
    ("grasp", "pull"),
    ("grasp", "pour"),
    ("grasp", "handover"),
    ("pull",  "rotate"),
    ("push",  "wipe"),
    ("push",  "press"),
    ("rotate", "insert"),
    ("pour",  "insert"),
    ("pull",  "fold"),
    ("wipe",  "fold"),
    ("insert", "cut"),
]

METRICS = {
    "skill_coverage_index": 0.72,
    "composition_success_rate": 0.68,
    "skill_acquisition_velocity": 1.4,   # skills/sprint
    "planned_skills_eta": "Q4-2026",
    "composite_task_score": 0.72,
    "mastered_count": 4,
    "learning_count": 6,
    "planned_count": 2,
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _stage_color(stage: str) -> str:
    return {"mastered": "#10b981", "learning": "#38bdf8", "planned": "#475569"}.get(stage, "#64748b")


def _skill_graph_svg() -> str:
    """Skill dependency graph with nodes and edges."""
    svg_w, svg_h = 920, 420
    padding = 10

    # edges first (behind nodes)
    edge_lines = ""
    for src_id, dst_id in EDGES:
        src = SKILL_INDEX[src_id]
        dst = SKILL_INDEX[dst_id]
        # offset to canvas coords (add padding)
        x1, y1 = src["x"] + padding, src["y"] + padding + 30
        x2, y2 = dst["x"] + padding, dst["y"] + padding + 30
        both_mastered = src["stage"] == "mastered" and dst["stage"] == "mastered"
        stroke = "#10b981" if both_mastered else ("#38bdf8" if dst["stage"] == "learning" else "#334155")
        edge_lines += (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                       f'stroke="{stroke}" stroke-width="1.8" opacity="0.6" '
                       f'marker-end="url(#arrow)"/>')

    # nodes
    node_shapes = ""
    for s in SKILLS:
        nx = s["x"] + padding
        ny = s["y"] + padding + 30
        # radius proportional to SR (mastery level), min 16 max 30
        rad = max(16, min(30, int(16 + s["sr"] * 18)))
        col = _stage_color(s["stage"])
        stroke_col = "#C74634" if s["stage"] == "mastered" else col
        opacity = "1.0" if s["stage"] != "planned" else "0.4"
        node_shapes += (
            f'<circle cx="{nx}" cy="{ny}" r="{rad}" fill="{col}" fill-opacity="0.25" '
            f'stroke="{stroke_col}" stroke-width="2" opacity="{opacity}">'
            f'<title>{s["id"]} | SR={s["sr"]:.0%} | {s["stage"]} | {s["v_ver"]}</title></circle>'
            f'<text x="{nx}" y="{ny+1}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="{col}" font-size="9" font-weight="bold" opacity="{opacity}">{s["id"]}</text>'
            f'<text x="{nx}" y="{ny + rad + 11}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="8" opacity="{opacity}">{s["sr"]:.0%}</text>'
        )

    # legend
    legend = ""
    for i, (stage, col, label) in enumerate([
        ("mastered", "#10b981", "Mastered (SR>0.80)"),
        ("learning", "#38bdf8", "Learning (SR 0.50-0.80)"),
        ("planned",  "#475569", "Planned (SR<0.50)"),
    ]):
        lx, ly = 16, svg_h - 52 + i * 17
        legend += (f'<circle cx="{lx+5}" cy="{ly+5}" r="5" fill="{col}" opacity="0.8"/>'
                   f'<text x="{lx+16}" y="{ly+10}" fill="#94a3b8" font-size="11">{label}</text>')

    arrow_marker = (
        '<defs><marker id="arrow" markerWidth="7" markerHeight="7" '
        'refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L7,3 z" fill="#475569"/></marker></defs>'
    )

    title = (f'<text x="{svg_w//2}" y="22" text-anchor="middle" fill="#f1f5f9" '
             f'font-size="15" font-weight="bold">Skill Dependency Graph — 12 Primitive Skills</text>')

    return (
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + arrow_marker + title + edge_lines + node_shapes + legend
        + '</svg>'
    )


def _skill_bar_svg() -> str:
    """Skill success rate bar chart, colored by acquisition stage."""
    svg_w, svg_h = 680, 380
    margin = {"top": 45, "right": 20, "bottom": 100, "left": 55}
    plot_w = svg_w - margin["left"] - margin["right"]
    plot_h = svg_h - margin["top"] - margin["bottom"]

    ordered = sorted(SKILLS, key=lambda s: -s["sr"])
    n = len(ordered)
    bar_w = plot_w / n * 0.7
    gap   = plot_w / n
    ox = margin["left"]
    oy = margin["top"] + plot_h

    bars = ""
    for i, s in enumerate(ordered):
        bx = ox + i * gap + (gap - bar_w) / 2
        bh = s["sr"] * plot_h
        by = oy - bh
        col = _stage_color(s["stage"])
        bars += (f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{max(bh, 2):.1f}" '
                 f'fill="{col}" rx="3" opacity="0.85">'
                 f'<title>{s["id"]} SR={s["sr"]:.0%} ({s["stage"]})</title></rect>')
        sr_label = f'{s["sr"]:.0%}' if s["sr"] > 0 else "—"
        bars += (f'<text x="{bx + bar_w/2:.1f}" y="{max(by - 4, margin["top"] + 4):.1f}" '
                 f'text-anchor="middle" fill="{col}" font-size="9">{sr_label}</text>')
        # rotated x label
        lx = bx + bar_w / 2
        bars += (f'<text transform="rotate(-35 {lx:.1f} {oy + 14})" '
                 f'x="{lx:.1f}" y="{oy + 14}" text-anchor="end" '
                 f'fill="#cbd5e1" font-size="11">{s["id"]}</text>')
        bars += (f'<text transform="rotate(-35 {lx:.1f} {oy + 28})" '
                 f'x="{lx:.1f}" y="{oy + 28}" text-anchor="end" '
                 f'fill="#475569" font-size="9">{s["v_ver"]}</text>')

    # y-axis
    yaxis = ""
    for tick in [0, 0.25, 0.5, 0.75, 0.8, 1.0]:
        ty = oy - tick * plot_h
        col = "#C74634" if tick == 0.8 else "#334155"
        dash = "4,3" if tick == 0.8 else ""
        yaxis += (f'<line x1="{ox}" y1="{ty:.1f}" x2="{ox + plot_w}" y2="{ty:.1f}" '
                  f'stroke="{col}" stroke-width="{1.5 if tick==0.8 else 1}" '
                  + (f'stroke-dasharray="{dash}"' if dash else "") + '/>'
                  f'<text x="{ox - 6}" y="{ty + 4:.1f}" text-anchor="end" '
                  f'fill="{"#C74634" if tick==0.8 else "#94a3b8"}" font-size="10">{tick:.0%}</text>')

    threshold_label = (f'<text x="{ox + plot_w}" y="{oy - 0.8*plot_h - 6:.1f}" '
                       f'text-anchor="end" fill="#C74634" font-size="9">mastered threshold 80%</text>')

    # legend
    legend = ""
    for i, (stage, col) in enumerate([("mastered", "#10b981"), ("learning", "#38bdf8"), ("planned", "#475569")]):
        lx = ox + i * 180
        legend += (f'<rect x="{lx}" y="{svg_h - 18}" width="12" height="12" fill="{col}" rx="2"/>'
                   f'<text x="{lx + 16}" y="{svg_h - 7}" fill="#e2e8f0" font-size="11">{stage}</text>')

    title = (f'<text x="{svg_w//2}" y="28" text-anchor="middle" fill="#f1f5f9" '
             f'font-size="15" font-weight="bold">Skill Success Rates — GR00T_v2</text>')

    return (
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + title + yaxis + threshold_label + bars + legend
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robot Skill Library — Port 8275</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
    header span.badge {{ background: #C74634; color: #fff; font-size: 0.75rem;
                         padding: 3px 10px; border-radius: 12px; }}
    .port-tag {{ color: #38bdf8; font-size: 0.85rem; margin-left: auto; }}
    .kpi-row {{ display: flex; gap: 16px; padding: 24px 32px 8px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 18px 24px; min-width: 160px; flex: 1; }}
    .kpi .label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;
                   letter-spacing: .05em; margin-bottom: 6px; }}
    .kpi .value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .sub   {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
    .green {{ color: #10b981 !important; }}
    .warn  {{ color: #f59e0b !important; }}
    .charts {{ display: flex; gap: 24px; padding: 24px 32px; flex-wrap: wrap; }}
    .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
                   padding: 20px; flex: 1; min-width: 340px; overflow-x: auto; }}
    .chart-card h2 {{ font-size: 0.95rem; color: #94a3b8; margin-bottom: 14px; }}
    .skill-table {{ width: 100%; border-collapse: collapse; margin: 0 32px 24px; width: calc(100% - 64px); }}
    table.skill-table th {{ background: #1e293b; color: #94a3b8; font-size: 0.8rem;
                            text-transform: uppercase; padding: 10px 14px; text-align: left; }}
    table.skill-table td {{ padding: 9px 14px; font-size: 0.85rem; border-top: 1px solid #1e293b; }}
    table.skill-table tr:nth-child(even) {{ background: #0f172a; }}
    .pill {{ display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }}
    .pill-mastered {{ background: #064e3b; color: #10b981; }}
    .pill-learning  {{ background: #0c2e4a; color: #38bdf8; }}
    .pill-planned   {{ background: #1e293b; color: #64748b; }}
    footer {{ text-align: center; color: #475569; font-size: 0.75rem; padding: 20px; }}
  </style>
</head>
<body>
  <header>
    <h1>Robot Skill Library</h1>
    <span class="badge">OCI Robot Cloud</span>
    <span class="port-tag">:8275</span>
  </header>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Total Skills</div>
      <div class="value">12</div>
      <div class="sub">4 mastered / 6 learning / 2 planned</div>
    </div>
    <div class="kpi">
      <div class="label">Skill Coverage Index</div>
      <div class="value">0.72</div>
      <div class="sub">Target 0.90 by Q3-2026</div>
    </div>
    <div class="kpi">
      <div class="label">Composition SR</div>
      <div class="value warn">0.68</div>
      <div class="sub">Multi-step composite tasks</div>
    </div>
    <div class="kpi">
      <div class="label">Acq. Velocity</div>
      <div class="value green">1.4</div>
      <div class="sub">skills / sprint</div>
    </div>
    <div class="kpi">
      <div class="label">Planned Skills ETA</div>
      <div class="value" style="font-size:1.1rem;padding-top:8px">Q4-2026</div>
      <div class="sub">fold + cut (v4 target)</div>
    </div>
    <div class="kpi">
      <div class="label">Composite Task Score</div>
      <div class="value">0.72</div>
      <div class="sub">Avg across all multi-skill tasks</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <h2>Skill Dependency Graph (node size = mastery level)</h2>
      {_skill_graph_svg()}
    </div>
    <div class="chart-card">
      <h2>Success Rate by Skill — GR00T_v2 (dashed = mastered threshold)</h2>
      {_skill_bar_svg()}
    </div>
  </div>

  <table class="skill-table">
    <thead>
      <tr>
        <th>Skill</th>
        <th>SR (GR00T_v2)</th>
        <th>Stage</th>
        <th>Target Version</th>
        <th>Depends On</th>
      </tr>
    </thead>
    <tbody>
      {''.join(f'''<tr>
        <td style="color:#f1f5f9;font-weight:600">{s['id']}</td>
        <td style="color:{'#10b981' if s['sr']>=0.8 else ('#38bdf8' if s['sr']>=0.5 else ('#f59e0b' if s['sr']>0 else '#475569'))}">{s['sr']:.0%}</td>
        <td><span class="pill pill-{s['stage']}">{s['stage']}</span></td>
        <td style="color:#64748b">{s['v_ver']}</td>
        <td style="color:#64748b;font-size:0.8rem">{', '.join(e[0] for e in EDGES if e[1]==s['id']) or '—'}</td>
      </tr>''' for s in sorted(SKILLS, key=lambda x: -x['sr']))}
    </tbody>
  </table>

  <footer>OCI Robot Cloud &mdash; Robot Skill Library v1.0 &mdash; Port 8275</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or fallback)
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Robot Skill Library",
        description="Catalog of composable robot skills for multi-task GR00T policies.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "robot_skill_library", "port": 8275}

    @app.get("/api/skills")
    async def list_skills():
        return {"skills": SKILLS, "edges": EDGES, "metrics": METRICS}

    @app.get("/api/skills/{skill_id}")
    async def get_skill(skill_id: str):
        skill = SKILL_INDEX.get(skill_id)
        if not skill:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
        deps = [e[0] for e in EDGES if e[1] == skill_id]
        enables = [e[1] for e in EDGES if e[0] == skill_id]
        return {"skill": skill, "depends_on": deps, "enables": enables}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "robot_skill_library", "port": 8275}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif self.path == "/api/skills":
                body = json.dumps({"skills": SKILLS, "edges": EDGES, "metrics": METRICS}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8275)
    else:
        print("[robot_skill_library] fastapi not found — starting stdlib fallback on :8275")
        HTTPServer(("0.0.0.0", 8275), Handler).serve_forever()
