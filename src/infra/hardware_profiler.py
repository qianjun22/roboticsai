"""Hardware Profiler — FastAPI service on port 8237.

Profiles GPU fleet hardware utilization across OCI nodes for training,
DAgger, eval, inference, and idle workloads over a 24-hour window.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
import json

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

NODES = [
    {"id": "GPU4", "region": "Ashburn",  "shape": "A100_80GB", "role": "primary",  "health": "healthy"},
    {"id": "GPU5", "region": "Ashburn",  "shape": "A100_80GB", "role": "dagger",   "health": "healthy"},
    {"id": "GPU6", "region": "Phoenix",  "shape": "A100_40GB", "role": "eval",     "health": "degraded"},
    {"id": "GPU7", "region": "Frankfurt","shape": "A100_40GB", "role": "staging",  "health": "healthy"},
]

# 24 hours × 4 nodes — utilization % by workload type
# fine_tuning, dagger, eval, inference, idle  (must sum to ~100)
WORKLOAD_TYPES = ["fine_tuning", "dagger", "eval", "inference", "idle"]
WORKLOAD_COLORS = ["#C74634", "#f97316", "#38bdf8", "#22c55e", "#334155"]

# Per-node 24h utilization profile — each entry: [ft, dag, ev, inf, idle]
NODE_24H = {
    "GPU4": [
        (91, 0, 0, 5, 4),
        (88, 0, 0, 7, 5),
        (93, 0, 0, 4, 3),
        (90, 0, 0, 6, 4),
        (87, 0, 0, 8, 5),
        (92, 0, 0, 4, 4),
    ],
    "GPU5": [
        (0, 78, 0, 12, 10),
        (0, 81, 0, 10, 9),
        (5, 73, 0, 14, 8),
        (0, 79, 0, 11, 10),
        (3, 76, 0, 13, 8),
        (0, 80, 0, 11, 9),
    ],
    "GPU6": [
        (0, 0, 54, 20, 26),
        (0, 0, 51, 22, 27),
        (0, 8, 47, 24, 21),
        (0, 0, 56, 19, 25),
        (0, 0, 53, 21, 26),
        (0, 0, 55, 20, 25),
    ],
    "GPU7": [
        (0, 0, 12, 30, 58),
        (0, 5, 10, 27, 58),
        (8, 0, 11, 29, 52),
        (0, 0, 13, 31, 56),
        (0, 3, 10, 28, 59),
        (0, 0, 12, 30, 58),
    ],
}

HOUR_LABELS = ["00h", "04h", "08h", "12h", "16h", "20h"]

# HBM Bandwidth data
HBM_DATA = [
    {"node": "GPU4", "shape": "A100_80GB", "theoretical_tbps": 3.2, "measured_tbps": 2.8,  "health": "healthy"},
    {"node": "GPU5", "shape": "A100_80GB", "theoretical_tbps": 3.2, "measured_tbps": 2.65, "health": "healthy"},
    {"node": "GPU6", "shape": "A100_40GB", "theoretical_tbps": 2.0, "measured_tbps": 1.53, "health": "degraded"},
    {"node": "GPU7", "shape": "A100_40GB", "theoretical_tbps": 2.0, "measured_tbps": 1.47, "health": "healthy"},
]

FLEET_EFFICIENCY   = 73.5  # %
UNDERUTILIZED_PCT  = 26.5  # %
BOTTLENECK_NODE    = "GPU6"
FLEET_PEAK_UTIL    = 91.0  # GPU4 peak


def _build_stacked_area_svg() -> str:
    """Stacked area chart — GPU utilization by workload per node over 24h."""
    pad_left, pad_top = 60, 44
    cell_w = 200
    chart_h = 180
    gap = 30
    n_nodes = len(NODES)
    total_w = pad_left + n_nodes * (cell_w + gap) - gap + 40
    total_h = pad_top + chart_h + 80
    n_hours = len(HOUR_LABELS)

    parts = [
        f'<svg width="{total_w}" height="{total_h}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{total_w}" height="{total_h}" fill="#1e293b" rx="8"/>',
        f'<text x="{total_w//2}" y="24" fill="#e2e8f0" font-size="14" font-family="monospace"'
        f' text-anchor="middle" font-weight="bold">GPU Fleet — 24h Workload Utilization</text>',
    ]

    for ni, node in enumerate(NODES):
        ox = pad_left + ni * (cell_w + gap)
        oy = pad_top
        profile = NODE_24H[node["id"]]

        # Background
        parts.append(f'<rect x="{ox}" y="{oy}" width="{cell_w}" height="{chart_h}" fill="#0f172a" rx="4"/>')

        # Stacked area per hour segment
        x_step = cell_w / (n_hours - 1)
        # Build stacked points for each workload layer
        stacks = []  # list of lists of (x, y_bottom, y_top)
        for wi in range(len(WORKLOAD_TYPES)):
            pts_top = []
            pts_bot = []
            for hi in range(n_hours):
                x = ox + hi * x_step
                # sum workloads 0..wi
                top_sum = sum(profile[hi][wj] for wj in range(wi + 1))
                bot_sum = sum(profile[hi][wj] for wj in range(wi))
                y_top = oy + chart_h - int(top_sum / 100 * chart_h)
                y_bot = oy + chart_h - int(bot_sum / 100 * chart_h)
                pts_top.append((x, y_top))
                pts_bot.append((x, y_bot))
            stacks.append((pts_top, pts_bot))

        # Draw filled polygons bottom to top
        for wi, (pts_top, pts_bot) in enumerate(stacks):
            poly_pts = (
                " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_top)
                + " "
                + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(pts_bot))
            )
            parts.append(
                f'<polygon points="{poly_pts}" fill="{WORKLOAD_COLORS[wi]}" opacity="0.75"/>'
            )

        # X-axis labels
        for hi, label in enumerate(HOUR_LABELS):
            x = ox + hi * x_step
            parts.append(
                f'<text x="{x:.1f}" y="{oy + chart_h + 16}" fill="#64748b" font-size="9"'
                f' font-family="monospace" text-anchor="middle">{label}</text>'
            )

        # Node label
        health_color = "#22c55e" if node["health"] == "healthy" else "#f97316"
        parts.append(
            f'<text x="{ox + cell_w//2}" y="{oy + chart_h + 32}" fill="{health_color}"'
            f' font-size="12" font-family="monospace" text-anchor="middle"'
            f' font-weight="bold">{node["id"]} ({node["region"]})</text>'
        )
        parts.append(
            f'<text x="{ox + cell_w//2}" y="{oy + chart_h + 46}" fill="#64748b"'
            f' font-size="10" font-family="monospace" text-anchor="middle">{node["shape"]}</text>'
        )

    # Legend at bottom
    lx = pad_left
    ly = total_h - 18
    for wi, (wtype, color) in enumerate(zip(WORKLOAD_TYPES, WORKLOAD_COLORS)):
        parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="{color}" rx="2" opacity="0.85"/>')
        parts.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">{wtype}</text>')
        lx += 110

    parts.append('</svg>')
    return '\n'.join(parts)


def _build_hbm_bar_svg() -> str:
    """Bar chart — HBM bandwidth utilization per node at peak load."""
    n = len(HBM_DATA)
    pad_left, pad_top = 60, 44
    bar_group_w = 110
    bar_w = 40
    bar_gap = 12
    chart_h = 200
    width  = pad_left + n * bar_group_w + 60
    height = pad_top + chart_h + 80

    y_max = 3.5  # TB/s

    def to_y(val):
        return pad_top + chart_h - int(val / y_max * chart_h)

    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#1e293b" rx="8"/>',
        f'<text x="{width//2}" y="24" fill="#e2e8f0" font-size="14" font-family="monospace"'
        f' text-anchor="middle" font-weight="bold">HBM Bandwidth — Theoretical vs Measured (TB/s)</text>',
    ]

    # Grid lines
    for val in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
        yp = to_y(val)
        parts.append(f'<line x1="{pad_left}" y1="{yp}" x2="{width - 20}" y2="{yp}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        parts.append(f'<text x="{pad_left - 6}" y="{yp + 4}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">{val:.1f}</text>')

    for gi, hbm in enumerate(HBM_DATA):
        gx = pad_left + gi * bar_group_w + 10
        health_color = "#22c55e" if hbm["health"] == "healthy" else "#f97316"

        # Theoretical bar
        th = int(hbm["theoretical_tbps"] / y_max * chart_h)
        ty = pad_top + chart_h - th
        parts.append(f'<rect x="{gx}" y="{ty}" width="{bar_w}" height="{th}" fill="#334155" rx="3"/>')
        parts.append(f'<text x="{gx + bar_w//2}" y="{ty - 4}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">{hbm["theoretical_tbps"]:.1f}</text>')

        # Measured bar
        mh = int(hbm["measured_tbps"] / y_max * chart_h)
        my = pad_top + chart_h - mh
        mx = gx + bar_w + bar_gap
        pct = hbm["measured_tbps"] / hbm["theoretical_tbps"] * 100
        bar_color = health_color
        parts.append(f'<rect x="{mx}" y="{my}" width="{bar_w}" height="{mh}" fill="{bar_color}" rx="3" opacity="0.85"/>')
        parts.append(f'<text x="{mx + bar_w//2}" y="{my - 4}" fill="{bar_color}" font-size="10" font-family="monospace" text-anchor="middle">{hbm["measured_tbps"]:.2f}</text>')

        # Node label
        label_x = gx + bar_w + bar_gap // 2
        parts.append(f'<text x="{label_x}" y="{pad_top + chart_h + 18}" fill="{health_color}" font-size="12" font-family="monospace" text-anchor="middle" font-weight="bold">{hbm["node"]}</text>')
        parts.append(f'<text x="{label_x}" y="{pad_top + chart_h + 32}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">{hbm["shape"]}</text>')
        parts.append(f'<text x="{label_x}" y="{pad_top + chart_h + 46}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">{pct:.0f}% util</text>')

    # Legend
    lx = pad_left
    ly = height - 16
    parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="#334155" rx="2"/>')
    parts.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="11" font-family="monospace">Theoretical max</text>')
    lx += 150
    parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="#22c55e" rx="2"/>')
    parts.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="11" font-family="monospace">Measured (healthy)</text>')
    lx += 170
    parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="#f97316" rx="2"/>')
    parts.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="11" font-family="monospace">Measured (degraded)</text>')

    parts.append('</svg>')
    return '\n'.join(parts)


def _build_html() -> str:
    area_svg = _build_stacked_area_svg()
    bar_svg  = _build_hbm_bar_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hardware Profiler — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Menlo', 'Monaco', monospace; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 20px; color: #f8fafc; }}
    header span {{ font-size: 12px; color: #94a3b8; }}
    .badge {{ background: #C74634; color: #fff; font-size: 11px; padding: 2px 8px;
              border-radius: 4px; margin-left: auto; }}
    main {{ padding: 24px 32px; max-width: 1300px; margin: 0 auto; }}
    .metrics {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 14px 18px; }}
    .card .label {{ font-size: 11px; color: #64748b; text-transform: uppercase;
                    letter-spacing: 0.05em; margin-bottom: 6px; }}
    .card .value {{ font-size: 24px; font-weight: bold; }}
    .card .sub   {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
    .green {{ color: #22c55e; }}
    .red   {{ color: #ef4444; }}
    .sky   {{ color: #38bdf8; }}
    .orange {{ color: #f97316; }}
    .oracle-red {{ color: #C74634; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                      padding: 20px; margin-bottom: 24px; overflow-x: auto; }}
    .chart-section h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 16px;
                         text-transform: uppercase; letter-spacing: 0.05em; }}
    .chart-section svg {{ max-width: 100%; height: auto; }}
    .node-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .node-table th, .node-table td {{ border: 1px solid #334155; padding: 8px 14px; }}
    .node-table th {{ background: #0f172a; color: #64748b; text-align: left; }}
    .node-table tr:nth-child(even) {{ background: #0f172a; }}
    footer {{ text-align: center; padding: 20px; font-size: 11px; color: #475569; }}
  </style>
</head>
<body>
<header>
  <h1>Hardware Profiler</h1>
  <span>OCI Robot Cloud — port 8237</span>
  <div class="badge">LIVE</div>
</header>
<main>
  <div class="metrics">
    <div class="card">
      <div class="label">Fleet Efficiency</div>
      <div class="value sky">{FLEET_EFFICIENCY}%</div>
      <div class="sub">4-node average</div>
    </div>
    <div class="card">
      <div class="label">Underutilized</div>
      <div class="value orange">{UNDERUTILIZED_PCT}%</div>
      <div class="sub">Reclaim target</div>
    </div>
    <div class="card">
      <div class="label">Peak Node</div>
      <div class="value green">{FLEET_PEAK_UTIL}%</div>
      <div class="sub">GPU4 Ashburn</div>
    </div>
    <div class="card">
      <div class="label">Bottleneck</div>
      <div class="value oracle-red">{BOTTLENECK_NODE}</div>
      <div class="sub">HBM degraded</div>
    </div>
    <div class="card">
      <div class="label">Active Nodes</div>
      <div class="value green">4 / 4</div>
      <div class="sub">1 degraded</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>24h Workload Utilization per Node</h2>
    {area_svg}
  </div>

  <div class="chart-section">
    <h2>HBM Bandwidth — Theoretical vs Measured at Peak Load</h2>
    {bar_svg}
  </div>

  <div class="chart-section">
    <h2>Node Inventory</h2>
    <table class="node-table">
      <thead>
        <tr><th>Node</th><th>Region</th><th>Shape</th><th>Role</th><th>Health</th><th>Peak Util</th><th>HBM (TB/s)</th></tr>
      </thead>
      <tbody>
        {''.join(
            f'<tr><td style="color:#38bdf8">{n["id"]}</td><td>{n["region"]}</td><td>{n["shape"]}</td>'
            f'<td>{n["role"]}</td>'
            f'<td style="color:{"#22c55e" if n["health"]=="healthy" else "#f97316"}">{n["health"]}</td>'
            f'<td style="color:#e2e8f0">{HBM_DATA[i]["measured_tbps"]/HBM_DATA[i]["theoretical_tbps"]*100:.0f}%</td>'
            f'<td style="color:#e2e8f0">{HBM_DATA[i]["measured_tbps"]:.2f} / {HBM_DATA[i]["theoretical_tbps"]:.1f}</td></tr>'
            for i, n in enumerate(NODES)
        )}
      </tbody>
    </table>
  </div>
</main>
<footer>OCI Robot Cloud &mdash; Hardware Profiler &mdash; port 8237</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Hardware Profiler",
        description="Profiles GPU fleet hardware utilization across OCI nodes",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/api/nodes")
    async def api_nodes():
        return {"nodes": NODES, "hbm": HBM_DATA}

    @app.get("/api/utilization")
    async def api_utilization():
        return {
            "nodes": [n["id"] for n in NODES],
            "workload_types": WORKLOAD_TYPES,
            "hour_labels": HOUR_LABELS,
            "profiles": {k: v for k, v in NODE_24H.items()},
        }

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "fleet_efficiency_pct": FLEET_EFFICIENCY,
            "underutilized_pct": UNDERUTILIZED_PCT,
            "fleet_peak_util_pct": FLEET_PEAK_UTIL,
            "bottleneck_node": BOTTLENECK_NODE,
            "active_nodes": len(NODES),
            "degraded_nodes": sum(1 for n in NODES if n["health"] == "degraded"),
            "hbm_bandwidth": [
                {
                    "node": h["node"],
                    "theoretical_tbps": h["theoretical_tbps"],
                    "measured_tbps": h["measured_tbps"],
                    "utilization_pct": round(h["measured_tbps"] / h["theoretical_tbps"] * 100, 1),
                }
                for h in HBM_DATA
            ],
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8237, "service": "hardware_profiler"}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8237)
    else:
        print("FastAPI not found — using stdlib http.server on port 8237")
        with socketserver.TCPServer(("", 8237), _Handler) as httpd:
            httpd.serve_forever()
