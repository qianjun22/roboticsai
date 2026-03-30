"""model_lineage_tracker.py — FastAPI service on port 8249

Tracks full training lineage and provenance for GR00T model versions
in the OCI Robot Cloud fine-tuning pipeline.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Lineage data
# ---------------------------------------------------------------------------

LINEAGE_NODES = [
    {
        "id": "pretrained",
        "label": "GR00T\nPretrained",
        "sr": 0.05,
        "stage": "pretrained",
        "facts": "Base model · 1.5B params",
        "status": "ARCHIVED",
        "depth": 0,
    },
    {
        "id": "bc_500",
        "label": "BC_500",
        "sr": 0.42,
        "stage": "bc",
        "facts": "500 demos · 2000 steps",
        "status": "ARCHIVED",
        "depth": 1,
    },
    {
        "id": "dagger_r5",
        "label": "DAgger_r5",
        "sr": 0.61,
        "stage": "dagger",
        "facts": "DAgger run-5 · 5000 steps",
        "status": "ARCHIVED",
        "depth": 2,
    },
    {
        "id": "dagger_r9_v2",
        "label": "DAgger_r9\nv2.2",
        "sr": 0.71,
        "stage": "dagger",
        "facts": "DAgger run-9 · 10k steps",
        "status": "PROD",
        "depth": 3,
    },
    {
        "id": "groot_v2",
        "label": "GR00T_v2",
        "sr": 0.78,
        "stage": "bc",
        "facts": "1000 demos · IK SDG",
        "status": "STAGING",
        "depth": 4,
    },
    {
        "id": "groot_v3",
        "label": "GR00T_v3",
        "sr": None,
        "stage": "bc",
        "facts": "In progress · RTX rand.",
        "status": "TRAINING",
        "depth": 5,
    },
]

LINEAGE_EDGES = [
    ("pretrained", "bc_500"),
    ("bc_500",     "dagger_r5"),
    ("dagger_r5",  "dagger_r9_v2"),
    ("dagger_r9_v2", "groot_v2"),
    ("groot_v2",   "groot_v3"),
]

SR_STEPS = [
    {"stage": "Pretrained",     "sr": 0.05, "delta": 0.00},
    {"stage": "BC_500",         "sr": 0.42, "delta": 0.37},
    {"stage": "DAgger_r5",      "sr": 0.61, "delta": 0.19},
    {"stage": "DAgger_r9_v2.2", "sr": 0.71, "delta": 0.10},
    {"stage": "GR00T_v2(STG)",  "sr": 0.78, "delta": 0.07},
]

LINEAGE_DEPTH   = len(LINEAGE_NODES)
PROVENANCE_SCORE = 0.96  # all nodes have full metadata
TOTAL_SR_GAIN   = round(SR_STEPS[-1]["sr"] - SR_STEPS[0]["sr"], 2)

STATUS_COLORS = {
    "PROD":     "#C74634",
    "STAGING":  "#f59e0b",
    "TRAINING": "#38bdf8",
    "ARCHIVED": "#475569",
}

# ---------------------------------------------------------------------------
# SVG 1 — DAG lineage graph
# ---------------------------------------------------------------------------

def _dag_svg(width=680, height=260):
    n = len(LINEAGE_NODES)
    pad_l, pad_r, pad_t, pad_b = 30, 30, 30, 30
    slot_w = (width - pad_l - pad_r) / (n - 1)

    node_x = {node["id"]: pad_l + node["depth"] * slot_w for node in LINEAGE_NODES}
    node_y = {node["id"]: height / 2 for node in LINEAGE_NODES}
    # slight arc: middle nodes dip slightly
    for node in LINEAGE_NODES:
        d = node["depth"]
        node_y[node["id"]] = height / 2 + math.sin(d / (n - 1) * math.pi) * 18

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{width//2}" y="16" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">',
        'Model Lineage DAG — GR00T Training Provenance</text>',
    ]

    # edges
    for src_id, dst_id in LINEAGE_EDGES:
        x1, y1 = node_x[src_id], node_y[src_id]
        x2, y2 = node_x[dst_id], node_y[dst_id]
        cx = (x1 + x2) / 2
        lines.append(f'<path d="M{x1:.1f},{y1:.1f} C{cx:.1f},{y1:.1f} {cx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}" '
                     f'stroke="#334155" stroke-width="2" fill="none" marker-end="url(#arr)"/>')

    # arrowhead marker
    lines.insert(2, '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
                    '<path d="M0,0 L0,6 L8,3 z" fill="#475569"/></marker></defs>')

    # nodes
    RX = 38
    RY = 22
    for node in LINEAGE_NODES:
        cx = node_x[node["id"]]
        cy = node_y[node["id"]]
        col = STATUS_COLORS[node["status"]]
        lines.append(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{RX}" ry="{RY}" '
                     f'fill="#0f172a" stroke="{col}" stroke-width="2"/>')

        # multi-line label
        label_parts = node["label"].split("\n")
        for li, part in enumerate(label_parts):
            dy = cy - 4 + li * 12 - (len(label_parts) - 1) * 6
            lines.append(f'<text x="{cx:.1f}" y="{dy:.1f}" text-anchor="middle" '
                         f'fill="{col}" font-size="9" font-family="monospace" font-weight="bold">{part}</text>')

        # SR annotation
        sr_str = f"SR={node['sr']}" if node["sr"] is not None else "SR=TBD"
        lines.append(f'<text x="{cx:.1f}" y="{cy+RY+12:.1f}" text-anchor="middle" '
                     f'fill="#94a3b8" font-size="8" font-family="monospace">{sr_str}</text>')

        # status badge
        badge_col = STATUS_COLORS[node["status"]]
        lines.append(f'<text x="{cx:.1f}" y="{cy+RY+22:.1f}" text-anchor="middle" '
                     f'fill="{badge_col}" font-size="7" font-family="monospace">[{node["status"]}]</text>')

        # facts above
        lines.append(f'<text x="{cx:.1f}" y="{cy-RY-5:.1f}" text-anchor="middle" '
                     f'fill="#475569" font-size="7" font-family="monospace">{node["facts"]}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG 2 — Bar chart: delta SR per fine-tuning stage
# ---------------------------------------------------------------------------

def _delta_bar_svg(width=640, height=300):
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    stages = SR_STEPS
    n = len(stages)
    bar_w = plot_w / n * 0.6
    slot = plot_w / n

    sr_max = max(s["sr"] for s in stages)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{width//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">',
        'SR per Fine-Tuning Stage — Cumulative Improvement from Pretrained</text>',
    ]

    # y grid
    for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pad_t + plot_h - v / sr_max * plot_h
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v}</text>')

    # axis label
    lines.append(f'<text x="12" y="{pad_t+plot_h//2}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,12,{pad_t+plot_h//2})">Success Rate</text>')

    cumulative_y = pad_t + plot_h  # previous bar top for delta bracket
    prev_top = None

    for i, s in enumerate(stages):
        cx = pad_l + i * slot + slot / 2 - bar_w / 2
        bar_h = s["sr"] / sr_max * plot_h
        by = pad_t + plot_h - bar_h

        # choose color: prod=red, staging=amber, else blue
        if i == 3:
            col = "#C74634"
        elif i == 4:
            col = "#f59e0b"
        else:
            col = "#38bdf8"

        lines.append(f'<rect x="{cx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{col}" opacity="0.85" rx="2"/>')

        # SR label on top
        lines.append(f'<text x="{cx+bar_w/2:.1f}" y="{by-4:.1f}" text-anchor="middle" fill="#f8fafc" font-size="9" font-family="monospace">{s["sr"]}</text>')

        # delta label if > 0
        if s["delta"] > 0 and prev_top is not None:
            mid_y = (prev_top + by) / 2
            lines.append(f'<text x="{cx+bar_w/2:.1f}" y="{mid_y:.1f}" text-anchor="middle" fill="#34d399" font-size="9" font-family="monospace">+{s["delta"]}</text>')

        # stage name (rotated)
        lines.append(f'<text x="{cx+bar_w/2:.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#94a3b8" font-size="8" font-family="monospace" transform="rotate(30,{cx+bar_w/2:.1f},{pad_t+plot_h+14})">{s["stage"]}</text>')

        prev_top = by

    # cumulative annotation
    lines.append(f'<text x="{pad_l+plot_w-4}" y="{pad_t+12}" text-anchor="end" fill="#34d399" font-size="10" font-family="monospace">Total gain: +{TOTAL_SR_GAIN} SR</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html():
    dag   = _dag_svg()
    bars  = _delta_bar_svg()
    ts    = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    prod_node = next(n for n in LINEAGE_NODES if n["status"] == "PROD")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Model Lineage Tracker — Port 8249</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.35rem; margin-bottom: 4px; }}
    h2   {{ color: #38bdf8; font-size: 1rem; margin: 20px 0 8px; }}
    .sub {{ color: #64748b; font-size: 0.8rem; margin-bottom: 20px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .card  {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
              padding: 16px 20px; min-width: 155px; flex: 1; }}
    .card .val  {{ font-size: 1.6rem; color: #38bdf8; font-weight: bold; }}
    .card .lbl  {{ font-size: 0.72rem; color: #94a3b8; margin-top: 4px; }}
    .card.red .val {{ color: #C74634; }}
    .card.green .val {{ color: #34d399; }}
    .chart {{ margin-bottom: 28px; }}
    table  {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
    th     {{ background: #1e293b; color: #38bdf8; padding: 8px; text-align: left; }}
    td     {{ padding: 6px 8px; border-top: 1px solid #1e293b; }}
    tr:nth-child(even) td {{ background: #0f172a; }}
    .badge {{ display: inline-block; padding: 2px 7px; border-radius: 4px;
              font-size: 0.7rem; font-weight: bold; }}
    .PROD     {{ background: #C74634; color: #fff; }}
    .STAGING  {{ background: #f59e0b; color: #000; }}
    .TRAINING {{ background: #38bdf8; color: #0f172a; }}
    .ARCHIVED {{ background: #334155; color: #94a3b8; }}
    .ts    {{ color: #334155; font-size: 0.7rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>GR00T Model Lineage Tracker</h1>
  <p class="sub">Port 8249 &nbsp;|&nbsp; Full training provenance for OCI Robot Cloud model versions</p>

  <div class="cards">
    <div class="card">
      <div class="val">{LINEAGE_DEPTH}</div>
      <div class="lbl">Lineage Depth (nodes)</div>
    </div>
    <div class="card red">
      <div class="val">{prod_node['sr']}</div>
      <div class="lbl">Current PROD SR ({prod_node['label'].replace(chr(10), ' ')})</div>
    </div>
    <div class="card green">
      <div class="val">+{TOTAL_SR_GAIN}</div>
      <div class="lbl">Total SR Gain (pretrained → PROD)</div>
    </div>
    <div class="card">
      <div class="val">{PROVENANCE_SCORE}</div>
      <div class="lbl">Provenance Completeness Score</div>
    </div>
  </div>

  <h2>Lineage DAG</h2>
  <div class="chart">{dag}</div>

  <h2>Success Rate Progression per Stage</h2>
  <div class="chart">{bars}</div>

  <h2>Lineage Table</h2>
  <table>
    <tr><th>Model</th><th>Status</th><th>SR</th><th>Delta SR</th><th>Training Facts</th></tr>
    {''.join(f"<tr><td>{n['label'].replace(chr(10), ' ')}</td>"
              + f"<td><span class='badge {n[\"status\"]}'>{n['status']}</span></td>"
              + f"<td>{'—' if n['sr'] is None else n['sr']}</td>"
              + f"<td style='color:#34d399'>{'—' if i==0 else '+'+str(SR_STEPS[i]['delta']) if i < len(SR_STEPS) else 'TBD'}</td>"
              + f"<td>{n['facts']}</td></tr>"
              for i, n in enumerate(LINEAGE_NODES))}
  </table>

  <p class="ts">Generated: {ts} UTC</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Model Lineage Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "model_lineage_tracker", "port": 8249}

    @app.get("/api/lineage")
    async def api_lineage():
        return {
            "nodes": LINEAGE_NODES,
            "edges": [{"src": s, "dst": d} for s, d in LINEAGE_EDGES],
            "sr_steps": SR_STEPS,
            "lineage_depth": LINEAGE_DEPTH,
            "total_sr_gain": TOTAL_SR_GAIN,
            "provenance_score": PROVENANCE_SCORE,
        }

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    PORT = 8249
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib server on port {PORT}")
        with socketserver.TCPServer(("", PORT), _Handler) as srv:
            print(f"Serving on http://0.0.0.0:{PORT}")
            srv.serve_forever()
