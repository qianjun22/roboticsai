"""Resource Allocation Optimizer — OCI Robot Cloud
Port 8318 | Optimizes multi-tenant GPU resource allocation across design partners.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
random.seed(42)

GPU_CAPACITY_PER_DAY = 240  # A100 GPU-hrs/day across 4 nodes

ALLOCATION_PRIORITIES = [
    {"name": "Training",   "pct": 45, "color": "#C74634"},
    {"name": "DAgger",     "pct": 25, "color": "#38bdf8"},
    {"name": "Eval",       "pct": 15, "color": "#34d399"},
    {"name": "Inference",  "pct": 10, "color": "#fbbf24"},
    {"name": "Reserved",   "pct":  5, "color": "#a78bfa"},
]

PARTNERS = [
    {"name": "Machina_Labs",  "alloc_hrs": 68,  "used_hrs": 61, "jobs": 3},
    {"name": "Wandelbots",    "alloc_hrs": 52,  "used_hrs": 44, "jobs": 2},
    {"name": "Matic",         "alloc_hrs": 38,  "used_hrs": 29, "jobs": 2},
    {"name": "Figure_AI",     "alloc_hrs": 30,  "used_hrs": 18, "jobs": 1},
    {"name": "Internal_SDG",  "alloc_hrs": 52,  "used_hrs": 48, "jobs": 4},
]

WEEKDAY_UTIL = 91   # %
WEEKEND_UTIL = 55   # %
WASTE_PER_DAY = 47  # $ per weekend day
RECOVERED_PER_DAY = 31  # $ recovered via SDG reallocation

FAIRNESS_INDEX = 0.874

# Build hourly utilization matrix: day-of-week (0=Mon) x hour
def _build_util_matrix():
    matrix = []
    for dow in range(7):
        row = []
        for hour in range(24):
            is_weekend = dow >= 5
            base = WEEKEND_UTIL if is_weekend else WEEKDAY_UTIL
            # Night dip
            if 1 <= hour <= 6:
                val = base - random.randint(18, 28)
            elif 9 <= hour <= 17:
                val = base + random.randint(-4, 6)
            else:
                val = base + random.randint(-10, 5)
            row.append(max(10, min(99, val)))
        matrix.append(row)
    return matrix

UTIL_MATRIX = _build_util_matrix()

# ---------------------------------------------------------------------------
# HTML / SVG generation
# ---------------------------------------------------------------------------

def _color_for_util(pct: int) -> str:
    """Red-yellow-green gradient for utilization %."""
    if pct >= 85:
        return "#C74634"
    if pct >= 70:
        return "#f97316"
    if pct >= 55:
        return "#fbbf24"
    return "#38bdf8"


def _sankey_svg() -> str:
    """GPU capacity flow: pool -> priorities -> partners."""
    W, H = 720, 340
    svg_parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']

    # --- Source node (pool) ---
    pool_x, pool_y = 30, H // 2
    pool_h = 260
    pool_top = pool_y - pool_h // 2
    svg_parts.append(
        f'<rect x="{pool_x}" y="{pool_top}" width="40" height="{pool_h}" '
        f'rx="4" fill="#334155"/>'
    )
    svg_parts.append(
        f'<text x="{pool_x+20}" y="{pool_top-10}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">GPU Pool</text>'
    )
    svg_parts.append(
        f'<text x="{pool_x+20}" y="{pool_top-22}" text-anchor="middle" '
        f'fill="#38bdf8" font-size="10" font-family="monospace">240 hr/day</text>'
    )

    # --- Priority nodes (middle column) ---
    mid_x = 280
    total_pct = sum(p["pct"] for p in ALLOCATION_PRIORITIES)
    spacing = 8
    total_h_mid = pool_h
    usable_h = total_h_mid - spacing * (len(ALLOCATION_PRIORITIES) - 1)
    prio_rects = []
    cur_y = pool_top
    for p in ALLOCATION_PRIORITIES:
        ph = int(usable_h * p["pct"] / total_pct)
        prio_rects.append({"name": p["name"], "color": p["color"], "pct": p["pct"],
                            "x": mid_x, "y": cur_y, "w": 40, "h": max(ph, 8)})
        cur_y += ph + spacing

    for r in prio_rects:
        svg_parts.append(
            f'<rect x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" '
            f'rx="3" fill="{r["color"]}"/>'
        )
        svg_parts.append(
            f'<text x="{r["x"]+r["w"]+6}" y="{r["y"]+r["h"]//2+4}" '
            f'fill="{r["color"]}" font-size="10" font-family="monospace">'
            f'{r["name"]} {r["pct"]}%</text>'
        )
        # Flow band from pool to priority
        px1, py1 = pool_x + 40, pool_top + pool_h // 2
        px2, py2 = r["x"], r["y"] + r["h"] // 2
        ctrl_x = (px1 + px2) // 2
        bw = max(2, r["h"] // 2)
        svg_parts.append(
            f'<path d="M {px1} {py1-bw//2} C {ctrl_x} {py1-bw//2} {ctrl_x} {py2-bw//2} {px2} {py2-bw//2} '
            f'L {px2} {py2+bw//2} C {ctrl_x} {py2+bw//2} {ctrl_x} {py1+bw//2} {px1} {py1+bw//2} Z" '
            f'fill="{r["color"]}" opacity="0.22"/>'
        )

    # --- Partner nodes (right column) ---
    right_x = 560
    total_alloc = sum(p["alloc_hrs"] for p in PARTNERS)
    spacing2 = 6
    usable_h2 = pool_h - spacing2 * (len(PARTNERS) - 1)
    partner_rects = []
    cur_y2 = pool_top
    for p in PARTNERS:
        ph = int(usable_h2 * p["alloc_hrs"] / total_alloc)
        partner_rects.append({"name": p["name"], "alloc": p["alloc_hrs"],
                               "x": right_x, "y": cur_y2, "h": max(ph, 8)})
        cur_y2 += ph + spacing2

    partner_colors = ["#C74634", "#38bdf8", "#34d399", "#fbbf24", "#a78bfa"]
    for i, r in enumerate(partner_rects):
        col = partner_colors[i % len(partner_colors)]
        svg_parts.append(
            f'<rect x="{r["x"]}" y="{r["y"]}" width="36" height="{r["h"]}" '
            f'rx="3" fill="{col}"/>'
        )
        svg_parts.append(
            f'<text x="{r["x"]+42}" y="{r["y"]+r["h"]//2+4}" '
            f'fill="{col}" font-size="10" font-family="monospace">'
            f'{r["name"]} {r["alloc"]}hr</text>'
        )
        # Flow from nearest priority to partner
        src = prio_rects[i % len(prio_rects)]
        px1 = src["x"] + src["w"]
        py1 = src["y"] + src["h"] // 2
        px2 = r["x"]
        py2 = r["y"] + r["h"] // 2
        ctrl_x = (px1 + px2) // 2
        bw = max(2, r["h"] // 2)
        svg_parts.append(
            f'<path d="M {px1} {py1-bw//2} C {ctrl_x} {py1-bw//2} {ctrl_x} {py2-bw//2} {px2} {py2-bw//2} '
            f'L {px2} {py2+bw//2} C {ctrl_x} {py2+bw//2} {ctrl_x} {py1+bw//2} {px1} {py1+bw//2} Z" '
            f'fill="{col}" opacity="0.2"/>'
        )

    svg_parts.append("</svg>")
    return "".join(svg_parts)


def _heatmap_svg() -> str:
    """Utilization heatmap: hour-of-day (x) × day-of-week (y)."""
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cell_w, cell_h = 26, 34
    pad_l, pad_t = 50, 30
    W = pad_l + 24 * cell_w + 60
    H = pad_t + 7 * cell_h + 50
    svg_parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']

    # Title
    svg_parts.append(
        f'<text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" '
        f'font-size="12" font-family="monospace">Fleet Utilization % — Hour x Day of Week</text>'
    )

    # Cells
    for dow, row in enumerate(UTIL_MATRIX):
        for hour, val in enumerate(row):
            cx = pad_l + hour * cell_w
            cy = pad_t + dow * cell_h
            color = _color_for_util(val)
            svg_parts.append(
                f'<rect x="{cx}" y="{cy}" width="{cell_w-2}" height="{cell_h-3}" '
                f'rx="2" fill="{color}" opacity="0.85"/>'
            )
            if cell_w >= 22:
                svg_parts.append(
                    f'<text x="{cx+cell_w//2-1}" y="{cy+cell_h//2+3}" text-anchor="middle" '
                    f'fill="#0f172a" font-size="8" font-family="monospace">{val}</text>'
                )

    # Day labels
    for dow, day in enumerate(DAYS):
        cy = pad_t + dow * cell_h + cell_h // 2 + 4
        svg_parts.append(
            f'<text x="{pad_l-6}" y="{cy}" text-anchor="end" '
            f'fill="#94a3b8" font-size="10" font-family="monospace">{day}</text>'
        )

    # Hour labels (every 3h)
    for h in range(0, 24, 3):
        cx = pad_l + h * cell_w + cell_w // 2
        svg_parts.append(
            f'<text x="{cx}" y="{pad_t + 7*cell_h + 16}" text-anchor="middle" '
            f'fill="#64748b" font-size="9" font-family="monospace">{h:02d}h</text>'
        )

    # Annotations
    ann_y = pad_t + 7 * cell_h + 34
    svg_parts.append(
        f'<rect x="{pad_l}" y="{ann_y}" width="12" height="10" rx="2" fill="#38bdf8"/>'
    )
    svg_parts.append(
        f'<text x="{pad_l+16}" y="{ann_y+9}" fill="#94a3b8" font-size="9" font-family="monospace">Low (&lt;55%)</text>'
    )
    svg_parts.append(
        f'<rect x="{pad_l+80}" y="{ann_y}" width="12" height="10" rx="2" fill="#fbbf24"/>'
    )
    svg_parts.append(
        f'<text x="{pad_l+96}" y="{ann_y+9}" fill="#94a3b8" font-size="9" font-family="monospace">Mid</text>'
    )
    svg_parts.append(
        f'<rect x="{pad_l+130}" y="{ann_y}" width="12" height="10" rx="2" fill="#C74634"/>'
    )
    svg_parts.append(
        f'<text x="{pad_l+146}" y="{ann_y+9}" fill="#94a3b8" font-size="9" font-family="monospace">Peak (&gt;85%)</text>'
    )

    svg_parts.append("</svg>")
    return "".join(svg_parts)


def _build_html() -> str:
    sankey = _sankey_svg()
    heatmap = _heatmap_svg()

    partner_rows = ""
    for p in PARTNERS:
        util_pct = round(p["used_hrs"] / p["alloc_hrs"] * 100)
        bar_color = "#C74634" if util_pct > 85 else ("#34d399" if util_pct > 70 else "#fbbf24")
        partner_rows += f"""
        <tr>
          <td style="color:#e2e8f0">{p['name']}</td>
          <td style="color:#38bdf8;text-align:center">{p['alloc_hrs']}</td>
          <td style="color:#34d399;text-align:center">{p['used_hrs']}</td>
          <td style="text-align:center">
            <div style="background:#1e293b;border-radius:4px;height:14px;width:100%">
              <div style="background:{bar_color};height:14px;border-radius:4px;width:{util_pct}%"></div>
            </div>
            <span style="color:{bar_color};font-size:11px">{util_pct}%</span>
          </td>
          <td style="color:#94a3b8;text-align:center">{p['jobs']}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Resource Allocation Optimizer | OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
    .card .val{{font-size:28px;font-weight:bold;color:#38bdf8;margin-bottom:4px}}
    .card .lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px}}
    .section{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:22px}}
    .section h2{{color:#38bdf8;font-size:15px;margin-bottom:16px}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{color:#64748b;text-align:left;padding:8px 12px;border-bottom:1px solid #334155;font-weight:normal}}
    td{{padding:8px 12px;border-bottom:1px solid #1e293b}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px}}
    .green{{background:#052e16;color:#34d399;border:1px solid #166534}}
    .red{{background:#450a0a;color:#C74634;border:1px solid #991b1b}}
    .yellow{{background:#451a03;color:#fbbf24;border:1px solid #92400e}}
    svg{{max-width:100%;height:auto}}
  </style>
</head>
<body>
  <h1>Resource Allocation Optimizer</h1>
  <div class="subtitle">OCI Robot Cloud — Multi-Tenant GPU Scheduling | Port 8318 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="metrics">
    <div class="card"><div class="val">{GPU_CAPACITY_PER_DAY}</div><div class="lbl">A100 GPU-hrs / Day</div></div>
    <div class="card"><div class="val" style="color:#C74634">{WEEKDAY_UTIL}%</div><div class="lbl">Weekday Utilization</div></div>
    <div class="card"><div class="val" style="color:#fbbf24">{WEEKEND_UTIL}%</div><div class="lbl">Weekend Utilization</div></div>
    <div class="card"><div class="val" style="color:#34d399">${RECOVERED_PER_DAY}/day</div><div class="lbl">Recovered via SDG Realloc</div></div>
  </div>

  <div class="metrics" style="grid-template-columns:repeat(3,1fr)">
    <div class="card"><div class="val" style="color:#fbbf24">${WASTE_PER_DAY}/day</div><div class="lbl">Weekend GPU Waste</div></div>
    <div class="card"><div class="val">{FAIRNESS_INDEX}</div><div class="lbl">Fairness Index (Jain)</div></div>
    <div class="card"><div class="val" style="color:#a78bfa">{len(PARTNERS)}</div><div class="lbl">Active Tenants</div></div>
  </div>

  <div class="section">
    <h2>GPU Capacity Flow — Pool → Priorities → Partners</h2>
    {sankey}
  </div>

  <div class="section">
    <h2>Fleet Utilization Heatmap (Hour × Day)</h2>
    {heatmap}
    <p style="color:#64748b;font-size:11px;margin-top:10px">
      Weekend waste window: Sat-Sun 02h–08h (avg 37%). Spot reallocation to SDG batches recovers ~${RECOVERED_PER_DAY}/day.
    </p>
  </div>

  <div class="section">
    <h2>Per-Tenant Allocation</h2>
    <table>
      <thead><tr>
        <th>Tenant</th><th style="text-align:center">Alloc (hr)</th>
        <th style="text-align:center">Used (hr)</th>
        <th style="text-align:center">Utilization</th>
        <th style="text-align:center">Active Jobs</th>
      </tr></thead>
      <tbody>{partner_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app  (fallback to stdlib http.server)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Resource Allocation Optimizer",
        description="Multi-tenant GPU resource allocation for OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8318, "service": "resource_allocation_optimizer"}

    @app.get("/api/metrics")
    async def metrics():
        return {
            "gpu_capacity_per_day": GPU_CAPACITY_PER_DAY,
            "weekday_utilization_pct": WEEKDAY_UTIL,
            "weekend_utilization_pct": WEEKEND_UTIL,
            "waste_per_day_usd": WASTE_PER_DAY,
            "recovered_per_day_usd": RECOVERED_PER_DAY,
            "fairness_index": FAIRNESS_INDEX,
            "allocation_priorities": ALLOCATION_PRIORITIES,
            "partners": PARTNERS,
        }

    @app.get("/api/heatmap")
    async def heatmap():
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return {"days": days, "hours": list(range(24)), "matrix": UTIL_MATRIX}

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8318)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8318")
        with socketserver.TCPServer(("", 8318), _Handler) as srv:
            srv.serve_forever()
