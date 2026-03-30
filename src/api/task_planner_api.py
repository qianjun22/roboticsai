"""Task Planner API — port 8344
Hierarchical task planning: decomposes complex tasks into GR00T-executable primitives.
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
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TASKS = [
    {"name": "make_coffee",       "subtasks": 5, "sr": 0.54},
    {"name": "set_table",         "subtasks": 6, "sr": 0.51},
    {"name": "sort_items",        "subtasks": 3, "sr": 0.82},
    {"name": "assembly_simple",   "subtasks": 4, "sr": 0.68},
    {"name": "clean_surface",     "subtasks": 3, "sr": 0.85},
    {"name": "stack_boxes",       "subtasks": 2, "sr": 0.91},
    {"name": "organize_shelf",    "subtasks": 7, "sr": 0.47},
    {"name": "handover_object",   "subtasks": 2, "sr": 0.93},
]

PRIMITIVES = {
    "supported": [
        "reach", "grasp", "release", "push", "pull",
        "pick", "place", "lift", "lower", "rotate",
        "slide", "press",
    ],
    "unsupported": ["pour", "cut", "fold"],
}

METRICS = {
    "simple_sr": 0.91,
    "complex_sr": 0.54,
    "supported_primitives": 12,
    "required_primitives": 15,
    "boundary_failure_rate": 0.62,
    "avg_depth": 3.4,
}

# Make-coffee decomposition tree (fixed structure for SVG)
TREE = {
    "id": "make_coffee", "label": "make_coffee", "depth": 0, "terminal": False, "supported": False,
    "children": [
        {
            "id": "pick_mug", "label": "pick_mug", "depth": 1, "terminal": False, "supported": False,
            "children": [
                {"id": "reach_mug",  "label": "reach_mug",  "depth": 2, "terminal": True, "supported": True,  "children": []},
                {"id": "grasp_mug",  "label": "grasp_mug",  "depth": 2, "terminal": True, "supported": True,  "children": []},
            ],
        },
        {
            "id": "move_to_machine", "label": "move_to_machine", "depth": 1, "terminal": True, "supported": True, "children": []
        },
        {
            "id": "press_button", "label": "press_button", "depth": 1, "terminal": True, "supported": True, "children": []
        },
    ],
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _tree_svg() -> str:
    """Render the make_coffee decomposition tree as an SVG string."""
    W, H = 680, 320
    nodes = [
        # (id, label, x, y, terminal, supported)
        ("make_coffee",    "make_coffee",    340, 40,  False, False),
        ("pick_mug",       "pick_mug",       200, 120, False, False),
        ("move_to_machine","move_to_machine",380, 120, True,  True),
        ("press_button",   "press_button",   540, 120, True,  True),
        ("reach_mug",      "reach_mug",      120, 220, True,  True),
        ("grasp_mug",      "grasp_mug",      280, 220, True,  True),
    ]
    edges = [
        ("make_coffee", "pick_mug"),
        ("make_coffee", "move_to_machine"),
        ("make_coffee", "press_button"),
        ("pick_mug",    "reach_mug"),
        ("pick_mug",    "grasp_mug"),
    ]
    pos = {n[0]: (n[2], n[3]) for n in nodes}

    lines = []
    for src, dst in edges:
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        lines.append(f'<line x1="{x1}" y1="{y1+20}" x2="{x2}" y2="{y2-20}" stroke="#475569" stroke-width="1.5"/>')

    circles = []
    for nid, label, x, y, terminal, supported in nodes:
        r = 18 if not terminal else 14
        if not terminal:
            fill = "#1e3a5f"
            stroke = "#38bdf8"
        elif supported:
            fill = "#14532d"
            stroke = "#4ade80"
        else:
            fill = "#7f1d1d"
            stroke = "#C74634"
        circles.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        circles.append(
            f'<text x="{x}" y="{y+50}" text-anchor="middle" font-size="10" fill="#94a3b8">{label}</text>'
        )

    legend = (
        '<rect x="10" y="280" width="12" height="12" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5" rx="2"/>'
        '<text x="26" y="291" font-size="10" fill="#94a3b8">composite</text>'
        '<rect x="110" y="280" width="12" height="12" fill="#14532d" stroke="#4ade80" stroke-width="1.5" rx="2"/>'
        '<text x="126" y="291" font-size="10" fill="#94a3b8">GR00T-supported</text>'
        '<rect x="250" y="280" width="12" height="12" fill="#7f1d1d" stroke="#C74634" stroke-width="1.5" rx="2"/>'
        '<text x="266" y="291" font-size="10" fill="#94a3b8">unsupported</text>'
    )

    inner = "\n".join(lines + circles) + "\n" + legend
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">\n'
        + inner
        + "\n</svg>"
    )


def _bar_svg() -> str:
    """Bar chart: planning success rate per task."""
    W, H = 680, 260
    pad_l, pad_r, pad_t, pad_b = 130, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(TASKS)
    bar_w = max(10, chart_w // n - 8)

    bars = []
    for i, t in enumerate(TASKS):
        bh = int(t["sr"] * chart_h)
        x = pad_l + i * (chart_w // n) + (chart_w // n - bar_w) // 2
        y = pad_t + chart_h - bh
        color = "#38bdf8" if t["sr"] >= 0.7 else "#C74634"
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
        )
        bars.append(
            f'<text x="{x + bar_w//2}" y="{y - 4}" text-anchor="middle" font-size="10" fill="#e2e8f0">{t["sr"]:.0%}</text>'
        )
        label = t["name"].replace("_", "\u200b_")
        bars.append(
            f'<text x="{x + bar_w//2}" y="{H - 5}" text-anchor="middle" font-size="9" fill="#94a3b8" transform="rotate(-20,{x + bar_w//2},{H - 5})">{t["name"]}</text>'
        )

    # y-axis
    axis = []
    for pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h - int(pct / 100 * chart_h)
        axis.append(f'<line x1="{pad_l-4}" y1="{y}" x2="{W - pad_r}" y2="{y}" stroke="#334155" stroke-width="1"/>')
        axis.append(f'<text x="{pad_l-8}" y="{y+4}" text-anchor="end" font-size="10" fill="#64748b">{pct}%</text>')

    inner = "\n".join(axis + bars)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">\n'
        + inner
        + "\n</svg>"
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    tree_svg = _tree_svg()
    bar_svg = _bar_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    supported = ", ".join(PRIMITIVES["supported"])
    unsupported = ", ".join(PRIMITIVES["unsupported"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Task Planner API — Port 8344</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}
    h1{{color:#38bdf8;font-size:1.6rem;margin-bottom:4px}}
    .subtitle{{color:#94a3b8;font-size:.9rem;margin-bottom:24px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px}}
    .card-label{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em}}
    .card-value{{font-size:1.5rem;font-weight:700;margin-top:4px}}
    .red{{color:#C74634}} .blue{{color:#38bdf8}} .green{{color:#4ade80}} .yellow{{color:#fbbf24}}
    .section{{margin-bottom:32px}}
    .section h2{{color:#38bdf8;font-size:1rem;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
    .pill-list{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
    .pill{{background:#1e293b;border:1px solid #334155;border-radius:4px;padding:2px 8px;font-size:.8rem;color:#cbd5e1}}
    .pill.ok{{border-color:#4ade80;color:#4ade80}}
    .pill.bad{{border-color:#C74634;color:#C74634}}
    footer{{color:#475569;font-size:.75rem;margin-top:32px}}
  </style>
</head>
<body>
  <h1>Task Planner API</h1>
  <p class="subtitle">Hierarchical task decomposition → GR00T-executable primitives &nbsp;|&nbsp; Port 8344 &nbsp;|&nbsp; {ts}</p>

  <div class="grid">
    <div class="card"><div class="card-label">Simple Task SR</div><div class="card-value green">{METRICS['simple_sr']:.0%}</div></div>
    <div class="card"><div class="card-label">Complex Task SR</div><div class="card-value red">{METRICS['complex_sr']:.0%}</div></div>
    <div class="card"><div class="card-label">Supported Primitives</div><div class="card-value blue">{METRICS['supported_primitives']}/{METRICS['required_primitives']}</div></div>
    <div class="card"><div class="card-label">Boundary Failure Rate</div><div class="card-value yellow">{METRICS['boundary_failure_rate']:.0%}</div></div>
    <div class="card"><div class="card-label">Avg Decomp Depth</div><div class="card-value blue">{METRICS['avg_depth']}</div></div>
  </div>

  <div class="section">
    <h2>Task Decomposition Tree — make_coffee</h2>
    {tree_svg}
  </div>

  <div class="section">
    <h2>Planning Success Rate by Task</h2>
    {bar_svg}
  </div>

  <div class="section">
    <h2>GR00T-Supported Primitives</h2>
    <div class="pill-list">{chr(10).join(f'<span class="pill ok">{p}</span>' for p in PRIMITIVES["supported"])}</div>
    <div style="margin-top:10px;color:#94a3b8;font-size:.85rem;">Unsupported (bottleneck):</div>
    <div class="pill-list">{chr(10).join(f'<span class="pill bad">{p}</span>' for p in PRIMITIVES["unsupported"])}</div>
    <p style="margin-top:10px;font-size:.82rem;color:#64748b;">62% of failures occur at subtask boundaries — transitions are the primary bottleneck.</p>
  </div>

  <footer>OCI Robot Cloud &mdash; Task Planner API &mdash; cycle-71A</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Task Planner API", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "task_planner_api", "port": 8344}

    @app.get("/metrics")
    async def metrics():
        return {
            "metrics": METRICS,
            "tasks": TASKS,
            "primitives": PRIMITIVES,
        }

    @app.post("/plan")
    async def plan(task: dict):
        name = task.get("task", "unknown")
        depth = random.randint(2, 5)
        n_primitives = random.randint(2, depth * 2)
        sr = round(random.uniform(0.4, 0.95), 3)
        return {
            "task": name,
            "decomposition_depth": depth,
            "n_primitives": n_primitives,
            "estimated_sr": sr,
            "bottleneck": "subtask_boundary" if sr < 0.7 else None,
        }

    @app.get("/tree")
    async def tree():
        return TREE

else:
    # ---------------------------------------------------------------------------
    # Fallback: stdlib http.server
    # ---------------------------------------------------------------------------
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path in ("/", ""):
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = _json.dumps({"status": "ok", "port": 8344}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/metrics":
                body = _json.dumps({"metrics": METRICS, "tasks": TASKS}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    def _run_stdlib():
        server = HTTPServer(("0.0.0.0", 8344), Handler)
        print("Task Planner API (stdlib fallback) running on http://0.0.0.0:8344")
        server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run("task_planner_api:app", host="0.0.0.0", port=8344, reload=False)
    else:
        _run_stdlib()
