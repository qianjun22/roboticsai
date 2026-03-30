"""OCI Robot Cloud Product Roadmap Service — port 8350.

Tracks product roadmap items, feature completeness, and customer asks.
Stdlib-only at module level; FastAPI used if available, else http.server fallback.
"""

from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

FEATURES = [
    # (id, category, name, status, quarter, progress, customer_asks)
    (1,  "training",     "Distributed BC training",       "DONE",         "Q1 2026", 100, 2),
    (2,  "training",     "DAgger online learning",         "DONE",         "Q1 2026", 100, 3),
    (3,  "training",     "Multi-robot co-training",        "IN_PROGRESS",  "Q2 2026",  45, 5),
    (4,  "training",     "Curriculum SDG scheduler",       "IN_PROGRESS",  "Q2 2026",  60, 2),
    (5,  "training",     "Humanoid body support",          "PLANNED",      "Q3 2026",   0, 4),
    (6,  "training",     "Policy distillation pipeline",   "PLANNED",      "Q3 2026",   0, 1),
    (7,  "serving",      "GR00T N1.6 inference",           "DONE",         "Q1 2026", 100, 3),
    (8,  "serving",      "OpenVLA inference server",       "DONE",         "Q1 2026", 100, 2),
    (9,  "serving",      "Real-time inference (<50ms)",    "IN_PROGRESS",  "Q2 2026",  55, 3),
    (10, "serving",      "Multi-region failover",          "DONE",         "Q1 2026", 100, 1),
    (11, "serving",      "Inference cost optimizer",       "IN_PROGRESS",  "Q2 2026",  70, 2),
    (12, "serving",      "Batch inference scheduler",      "PLANNED",      "Q3 2026",   0, 2),
    (13, "eval",         "Closed-loop BC eval",            "DONE",         "Q1 2026", 100, 1),
    (14, "eval",         "Regression detector v2",         "IN_PROGRESS",  "Q2 2026",  80, 2),
    (15, "eval",         "Multi-task benchmark suite",     "IN_PROGRESS",  "Q2 2026",  40, 3),
    (16, "eval",         "Sim-to-real gap analysis",       "PLANNED",      "Q3 2026",   0, 2),
    (17, "SDG",          "Isaac Sim RTX randomization",    "DONE",         "Q1 2026", 100, 1),
    (18, "SDG",          "Genesis IK motion planning",     "DONE",         "Q1 2026", 100, 2),
    (19, "SDG",          "Cosmos world model integration", "IN_PROGRESS",  "Q2 2026",  35, 3),
    (20, "SDG",          "Domain randomization library",   "PLANNED",      "Q3 2026",   0, 1),
    (21, "SDK",          "pip-installable OCI SDK",        "DONE",         "Q1 2026", 100, 4),
    (22, "SDK",          "Python SDK v2 + CLI",            "IN_PROGRESS",  "Q2 2026",  65, 2),
    (23, "SDK",          "Edge deploy tool (Jetson)",      "CUSTOMER_ASK", "Q3 2026",   0, 3),
    (24, "SDK",          "ROS 2 bridge adapter",           "PLANNED",      "Q4 2026",   0, 2),
    (25, "integrations", "NVIDIA Isaac Lab plugin",        "IN_PROGRESS",  "Q2 2026",  50, 3),
    (26, "integrations", "Lerobot dataset format",         "DONE",         "Q1 2026", 100, 1),
    (27, "integrations", "OCI Data Science integration",   "PLANNED",      "Q3 2026",   0, 2),
    (28, "integrations", "Weights & Biases logging",       "PLANNED",      "Q3 2026",   0, 1),
    (29, "integrations", "NVIDIA DGX Cloud pipeline",      "CUSTOMER_ASK", "Q4 2026",   0, 2),
    (30, "integrations", "AI World live demo integration", "IN_PROGRESS",  "Q3 2026",  20, 4),
]

CUSTOMER_ASKS = [
    ("multi_robot_training",   "training",     5),
    ("humanoid_support",       "training",     4),
    ("real_time_inference",    "serving",      3),
    ("edge_deploy_tool",       "SDK",          3),
    ("cosmos_world_model",     "SDG",          3),
    ("multi_task_benchmark",   "eval",         3),
    ("isaac_lab_plugin",       "integrations", 3),
    ("ai_world_demo",          "integrations", 4),
    ("pip_sdk",                "SDK",          4),
    ("dgx_cloud_pipeline",     "integrations", 2),
    ("ros2_bridge",            "SDK",          2),
    ("sim_real_gap",           "eval",         2),
]

STATUS_COLOR = {
    "DONE":         "#22c55e",
    "IN_PROGRESS":  "#38bdf8",
    "PLANNED":      "#94a3b8",
    "CUSTOMER_ASK": "#f97316",
}

CATEGORIES = ["training", "serving", "eval", "SDG", "SDK", "integrations"]
QUARTERS   = ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026", "Q1 2027"]

# ---------------------------------------------------------------------------
# Computed metrics
# ---------------------------------------------------------------------------

total_features = len(FEATURES)
done_features  = sum(1 for f in FEATURES if f[3] == "DONE")
ip_features    = sum(1 for f in FEATURES if f[3] == "IN_PROGRESS")
completion_pct = round(done_features / total_features * 100, 1)
customer_ask_covered = sum(1 for a in CUSTOMER_ASKS if
    any(f[2].lower().replace(" ", "_").replace("-", "_") in a[0] or a[0] in f[2].lower().replace(" ", "_") for f in FEATURES if f[3] == "DONE"))
delivery_velocity = 2.3  # features/week

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_roadmap_timeline() -> str:
    W, H = 820, 360
    pad_left, pad_top, pad_right, pad_bot = 130, 50, 30, 40
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bot

    row_h  = chart_h / len(CATEGORIES)
    col_w  = chart_w / len(QUARTERS)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # grid verticals + quarter labels
    for qi, q in enumerate(QUARTERS):
        x = pad_left + qi * col_w
        lines.append(f'<line x1="{x}" y1="{pad_top}" x2="{x}" y2="{H-pad_bot}" stroke="#334155" stroke-width="1"/>')
        cx = x + col_w / 2
        lines.append(f'<text x="{cx}" y="{pad_top - 8}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{q}</text>')
    # right edge
    lines.append(f'<line x1="{pad_left+chart_w}" y1="{pad_top}" x2="{pad_left+chart_w}" y2="{H-pad_bot}" stroke="#334155" stroke-width="1"/>')

    # grid horizontals + category labels
    for ci, cat in enumerate(CATEGORIES):
        y = pad_top + ci * row_h
        lines.append(f'<line x1="{pad_left}" y1="{y}" x2="{W-pad_right}" y2="{y}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left - 8}" y="{y + row_h/2 + 4}" text-anchor="end" fill="#cbd5e1" font-size="11" font-family="sans-serif">{cat}</text>')
    lines.append(f'<line x1="{pad_left}" y1="{pad_top+chart_h}" x2="{W-pad_right}" y2="{pad_top+chart_h}" stroke="#334155" stroke-width="1"/>')

    # feature bars
    bar_h = row_h * 0.35
    slots: dict[tuple, int] = {}  # (cat, quarter) -> count placed
    for fid, cat, name, status, quarter, prog, asks in FEATURES:
        if cat not in CATEGORIES or quarter not in QUARTERS:
            continue
        ci = CATEGORIES.index(cat)
        qi = QUARTERS.index(quarter)
        slot = slots.get((ci, qi), 0)
        slots[(ci, qi)] = slot + 1

        x   = pad_left + qi * col_w + 3
        bw  = col_w - 6
        y   = pad_top + ci * row_h + slot * (bar_h + 2) + 4
        col = STATUS_COLOR.get(status, "#64748b")
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" rx="3" fill="{col}" opacity="0.85"/>')
        # progress overlay
        if prog > 0:
            pw = bw * prog / 100
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{bar_h:.1f}" rx="3" fill="{col}" opacity="0.3"/>')

    # legend
    lx, ly = pad_left, H - pad_bot + 14
    for i, (status, color) in enumerate(STATUS_COLOR.items()):
        ox = lx + i * 170
        lines.append(f'<rect x="{ox}" y="{ly}" width="12" height="12" rx="2" fill="{color}"/>')
        lines.append(f'<text x="{ox+16}" y="{ly+10}" fill="#94a3b8" font-size="10" font-family="sans-serif">{status}</text>')

    # title
    lines.append(f'<text x="{pad_left + chart_w/2}" y="18" text-anchor="middle" fill="#f8fafc" font-size="13" font-weight="bold" font-family="sans-serif">OCI Robot Cloud — Roadmap Timeline</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _svg_heatmap() -> str:
    AREAS = CATEGORIES
    ASKS  = [a[0] for a in CUSTOMER_ASKS]
    W, H  = 820, 380
    pad_left, pad_top, pad_right, pad_bot = 180, 50, 30, 30
    cell_w = (W - pad_left - pad_right) / len(AREAS)
    cell_h = (H - pad_top - pad_bot)   / len(ASKS)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W/2}" y="20" text-anchor="middle" fill="#f8fafc" font-size="13" font-weight="bold" font-family="sans-serif">Customer Ask × Feature Area Heatmap</text>')

    # column labels
    for ai, area in enumerate(AREAS):
        cx = pad_left + ai * cell_w + cell_w / 2
        lines.append(f'<text x="{cx:.1f}" y="{pad_top - 8}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">{area}</text>')

    # row labels + cells
    for ri, ask_name in enumerate(ASKS):
        ask_count = next(a[2] for a in CUSTOMER_ASKS if a[0] == ask_name)
        ask_area  = next(a[1] for a in CUSTOMER_ASKS if a[0] == ask_name)
        ry = pad_top + ri * cell_h
        lines.append(f'<text x="{pad_left - 8}" y="{ry + cell_h/2 + 4:.1f}" text-anchor="end" fill="#cbd5e1" font-size="9" font-family="sans-serif">{ask_name.replace("_"," ")}</text>')
        for ai, area in enumerate(AREAS):
            cx = pad_left + ai * cell_w
            # intensity: full if primary area, partial if related
            if area == ask_area:
                intensity = min(ask_count / 5, 1.0)
                base = 0.9
            else:
                intensity = random.Random(ask_name + area).random() * 0.3
                base = 0.25
            r  = int(56  + intensity * (199 - 56))
            g  = int(189 + intensity * (86  - 189))
            b  = int(248 + intensity * (70  - 248))
            r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
            fill = f"rgb({r},{g},{b})"
            margin = 2
            lines.append(f'<rect x="{cx+margin:.1f}" y="{ry+margin:.1f}" width="{cell_w-2*margin:.1f}" height="{cell_h-2*margin:.1f}" rx="3" fill="{fill}" opacity="{base:.2f}"/>')
            if area == ask_area and ask_count >= 3:
                lines.append(f'<text x="{cx+cell_w/2:.1f}" y="{ry+cell_h/2+4:.1f}" text-anchor="middle" fill="#0f172a" font-size="9" font-weight="bold" font-family="monospace">{ask_count}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg_timeline = _svg_roadmap_timeline()
    svg_heatmap  = _svg_heatmap()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    q3_critical = [f for f in FEATURES if f[4] == "Q3 2026" and "AI World" in f[2]]
    q3_count    = len(q3_critical)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OCI Robot Cloud — Product Roadmap</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: .85rem; margin-bottom: 20px; }}
    .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .kpi  {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 14px 20px; min-width: 160px; flex: 1; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .lbl {{ font-size: .75rem; color: #94a3b8; margin-top: 4px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 16px; margin-bottom: 24px; overflow-x: auto; }}
    .card h2 {{ font-size: 1rem; color: #cbd5e1; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
    th {{ text-align: left; padding: 6px 10px; color: #64748b; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #0f172a; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: .72rem; font-weight: 600; }}
    .DONE         {{ background: #14532d; color: #22c55e; }}
    .IN_PROGRESS  {{ background: #0c4a6e; color: #38bdf8; }}
    .PLANNED      {{ background: #1e293b; color: #94a3b8; border: 1px solid #334155; }}
    .CUSTOMER_ASK {{ background: #431407; color: #f97316; }}
    .bar-bg {{ background: #334155; border-radius: 4px; height: 8px; width: 100%; }}
    .bar-fill {{ background: #38bdf8; border-radius: 4px; height: 8px; }}
    footer {{ color: #475569; font-size: .75rem; margin-top: 12px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Product Roadmap</h1>
  <div class="sub">Last updated: {ts} &nbsp;|&nbsp; {total_features} features tracked &nbsp;|&nbsp; port 8350</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val">{completion_pct}%</div><div class="lbl">Roadmap Completion</div></div>
    <div class="kpi"><div class="val">{done_features}</div><div class="lbl">Features Done</div></div>
    <div class="kpi"><div class="val">{ip_features}</div><div class="lbl">In Progress</div></div>
    <div class="kpi"><div class="val">{delivery_velocity}</div><div class="lbl">Delivery Velocity (feat/wk)</div></div>
    <div class="kpi"><div class="val">{q3_count}</div><div class="lbl">Q3 AI World-Critical Items</div></div>
    <div class="kpi"><div class="val">5</div><div class="lbl">Top Customer Ask (multi-robot)</div></div>
  </div>

  <div class="card">
    <h2>Roadmap Timeline</h2>
    {svg_timeline}
  </div>

  <div class="card">
    <h2>Customer Ask Heatmap</h2>
    {svg_heatmap}
  </div>

  <div class="card">
    <h2>Feature Detail</h2>
    <table>
      <thead><tr><th>#</th><th>Category</th><th>Feature</th><th>Status</th><th>Quarter</th><th>Progress</th><th>Customer Asks</th></tr></thead>
      <tbody>
{''.join(f"""        <tr><td>{f[0]}</td><td>{f[1]}</td><td>{f[2]}</td>
          <td><span class="badge {f[3]}">{f[3]}</span></td>
          <td>{f[4]}</td>
          <td><div class="bar-bg"><div class="bar-fill" style="width:{f[5]}%"></div></div></td>
          <td style="text-align:center">{f[6]}</td></tr>\n""" for f in FEATURES)}
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud Product Engineering &nbsp;|&nbsp; Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="OCI Product Roadmap", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "oci_product_roadmap", "port": 8350}

    @app.get("/api/features")
    async def api_features():
        return [
            {"id": f[0], "category": f[1], "name": f[2], "status": f[3],
             "quarter": f[4], "progress": f[5], "customer_asks": f[6]}
            for f in FEATURES
        ]

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "total_features": total_features,
            "done": done_features,
            "in_progress": ip_features,
            "completion_pct": completion_pct,
            "delivery_velocity_per_week": delivery_velocity,
            "customer_ask_coverage": customer_ask_covered,
            "q3_ai_world_critical": q3_count,
            "top_ask": "multi_robot_training",
            "top_ask_count": 5,
        }

    @app.get("/api/customer_asks")
    async def api_customer_asks():
        return [
            {"ask": a[0], "area": a[1], "customer_count": a[2]}
            for a in sorted(CUSTOMER_ASKS, key=lambda x: -x[2])
        ]

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8350)
    else:
        with socketserver.TCPServer(("", 8350), _Handler) as srv:
            print("OCI Product Roadmap running on http://0.0.0.0:8350 (stdlib fallback)")
            srv.serve_forever()
