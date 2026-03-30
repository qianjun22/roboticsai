"""
gpu_allocation_optimizer.py — port 8641
OCI Robot Cloud · cycle-145B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

# ---------------------------------------------------------------------------
# Data constants
# ---------------------------------------------------------------------------

TOTAL_GPU_HRS = 240  # per day

CATEGORIES = ["DAgger", "SDG", "Eval", "Fine-tune", "Inference", "HPO", "Reserved"]
CURRENT_PCT  = [25, 22, 18, 15, 10, 7, 3]
OPTIMAL_PCT  = [22, 30, 15, 14, 10, 6, 3]   # shift SDG to weekend +12 net effect

COLORS = ["#C74634", "#38bdf8", "#34d399", "#f59e0b", "#a78bfa", "#fb923c", "#64748b"]

# ---------------------------------------------------------------------------
# SVG 1: GPU Allocation Sankey (horizontal flow bars)
# ---------------------------------------------------------------------------

def svg_sankey() -> str:
    W, H = 700, 340
    pad = {"l": 30, "r": 120, "t": 45, "b": 20}
    iw = W - pad["l"] - pad["r"]
    bar_h = 28
    gap = 10
    total_h = len(CATEGORIES) * (bar_h + gap) - gap
    y0 = pad["t"] + (H - pad["t"] - pad["b"] - total_h) / 2

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="26" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">GPU Allocation \u2014 {TOTAL_GPU_HRS} GPU-hrs/day</text>',
    ]

    # source block (total)
    src_w = 22
    lines.append(f'<rect x="{pad["l"]}" y="{y0:.1f}" width="{src_w}" '
                 f'height="{total_h:.1f}" fill="#1e40af" rx="3"/>')
    lines.append(f'<text x="{pad["l"] + src_w//2}" y="{y0 + total_h/2:.1f}" '
                 f'text-anchor="middle" fill="#e2e8f0" font-size="9" '
                 f'transform="rotate(-90,{pad["l"] + src_w//2},{y0 + total_h/2:.1f})">'
                 f'{TOTAL_GPU_HRS} GPU-hrs</text>')

    flow_x = pad["l"] + src_w + 6

    for i, (cat, pct, col) in enumerate(zip(CATEGORIES, CURRENT_PCT, COLORS)):
        y = y0 + i * (bar_h + gap)
        hrs = TOTAL_GPU_HRS * pct / 100
        bar_w = iw * pct / 100

        # flow connector
        cy_src = y0 + i * (bar_h + gap) + bar_h / 2
        lines.append(f'<line x1="{pad["l"] + src_w}" y1="{cy_src:.1f}" '
                     f'x2="{flow_x + 4:.1f}" y2="{y + bar_h/2:.1f}" '
                     f'stroke="{col}" stroke-width="1.5" opacity="0.4"/>')

        # bar
        lines.append(f'<rect x="{flow_x}" y="{y:.1f}" width="{bar_w:.1f}" '
                     f'height="{bar_h}" fill="{col}" opacity="0.82" rx="3"/>')

        # pct label inside bar
        if pct >= 8:
            lines.append(f'<text x="{flow_x + bar_w/2:.1f}" y="{y + bar_h*0.65:.1f}" '
                         f'text-anchor="middle" fill="#0f172a" font-size="11" font-weight="bold">{pct}%</text>')

        # hrs label right
        end_x = flow_x + bar_w + 6
        lines.append(f'<text x="{end_x:.1f}" y="{y + bar_h*0.65:.1f}" '
                     f'fill="{col}" font-size="10">{cat} {hrs:.0f}h</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG 2: Utilization Heatmap (GPU-node x hour-of-week)
# ---------------------------------------------------------------------------

def svg_heatmap() -> str:
    nodes = 5    # GPU node rows
    hours = 24   # columns: 0-23
    W = 700
    cell_w = (W - 120) / hours
    cell_h = 30
    H = nodes * cell_h + 80

    random.seed(42)

    def util(node_i, hour):
        # weekday pattern: business hours peak
        if 8 <= hour <= 20:
            base = 0.88 + random.uniform(-0.07, 0.07)
        else:
            base = 0.55 + random.uniform(-0.1, 0.1)
        # node 4 = weekend node (lower utilization shown in row)
        if node_i == 4:
            base *= 0.62
        return min(max(base, 0.1), 1.0)

    def col_for_util(u):
        # interpolate #1e293b (low) -> #38bdf8 (mid) -> #C74634 (high)
        if u < 0.5:
            t = u / 0.5
            r = int(0x1e + t * (0x38 - 0x1e))
            g = int(0x29 + t * (0xbd - 0x29))
            b_v = int(0x3b + t * (0xf8 - 0x3b))
        else:
            t = (u - 0.5) / 0.5
            r = int(0x38 + t * (0xC7 - 0x38))
            g = int(0xbd + t * (0x46 - 0xbd))
            b_v = int(0xf8 + t * (0x34 - 0xf8))
        return f"#{r:02x}{g:02x}{b_v:02x}"

    pad_l = 80
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">GPU Utilization Heatmap \u2014 Node \u00d7 Hour-of-Day</text>',
    ]

    for ni in range(nodes):
        y = 35 + ni * cell_h
        label = f"Node-{ni+1}" + (" (wknd)" if ni == 4 else "")
        lines.append(f'<text x="{pad_l - 5}" y="{y + cell_h*0.65:.1f}" '
                     f'text-anchor="end" fill="#94a3b8" font-size="10">{label}</text>')
        for h in range(hours):
            u = util(ni, h)
            x = pad_l + h * cell_w
            fill = col_for_util(u)
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" '
                         f'height="{cell_h - 1:.1f}" fill="{fill}"/>')
            if ni == 0 and h % 4 == 0:
                lines.append(f'<text x="{x + cell_w/2:.1f}" y="{35 + nodes*cell_h + 14:.1f}" '
                             f'text-anchor="middle" fill="#64748b" font-size="9">{h:02d}h</text>')

    # annotations
    lines.append(f'<text x="{pad_l + 12*cell_w:.1f}" y="{H - 8:.1f}" '
                 f'fill="#C74634" font-size="10">Weekday peak ~91%</text>')
    lines.append(f'<text x="{pad_l + 1*cell_w:.1f}" y="{H - 8:.1f}" '
                 f'fill="#38bdf8" font-size="10">Off-peak / weekend ~55%</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG 3: Reallocation Recommendation (grouped bars: current vs optimised)
# ---------------------------------------------------------------------------

def svg_reallocation() -> str:
    W, H = 700, 300
    pad = {"l": 70, "r": 30, "t": 45, "b": 50}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]
    n = len(CATEGORIES)
    group_w = iw / n
    bar_w = group_w * 0.35
    y_max = 35

    def px(i, offset):
        return pad["l"] + i * group_w + group_w * 0.15 + offset * (bar_w + 3)

    def py(v):
        return pad["t"] + ih - (v / y_max) * ih

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="25" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">Reallocation: Current vs Optimised \u2014 $29/day savings</text>',
    ]

    # gridlines
    for v in range(0, 36, 5):
        y = py(v)
        lines.append(f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{W - pad["r"]}" y2="{y:.1f}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad["l"] - 5}" y="{y + 4:.1f}" text-anchor="end" '
                     f'fill="#64748b" font-size="9">{v}%</text>')

    for i, (cat, cur, opt, col) in enumerate(zip(CATEGORIES, CURRENT_PCT, OPTIMAL_PCT, COLORS)):
        # current bar
        x0 = px(i, 0)
        h_cur = (cur / y_max) * ih
        y_cur = py(cur)
        lines.append(f'<rect x="{x0:.1f}" y="{y_cur:.1f}" width="{bar_w:.1f}" '
                     f'height="{h_cur:.1f}" fill="{col}" opacity="0.55" rx="2"/>')
        # optimised bar
        x1 = px(i, 1)
        h_opt = (opt / y_max) * ih
        y_opt = py(opt)
        lines.append(f'<rect x="{x1:.1f}" y="{y_opt:.1f}" width="{bar_w:.1f}" '
                     f'height="{h_opt:.1f}" fill="{col}" opacity="0.95" rx="2"/>')
        # savings highlight for SDG (biggest shift)
        if cat == "SDG":
            diff = opt - cur
            lines.append(f'<text x="{x1 + bar_w/2:.1f}" y="{y_opt - 5:.1f}" '
                         f'text-anchor="middle" fill="#34d399" font-size="9" font-weight="bold">+{diff}%</text>')
        # category label
        cx = pad["l"] + i * group_w + group_w / 2
        lines.append(f'<text x="{cx:.1f}" y="{H - pad["b"] + 16}" '
                     f'text-anchor="middle" fill="#94a3b8" font-size="9">{cat}</text>')

    # legend
    lines.append(f'<rect x="{pad["l"]}" y="{H - 16}" width="10" height="8" fill="#94a3b8" opacity="0.5"/>')
    lines.append(f'<text x="{pad["l"] + 14}" y="{H - 8}" fill="#94a3b8" font-size="9">Current</text>')
    lines.append(f'<rect x="{pad["l"] + 70}" y="{H - 16}" width="10" height="8" fill="#94a3b8" opacity="0.95"/>')
    lines.append(f'<text x="{pad["l"] + 84}" y="{H - 8}" fill="#94a3b8" font-size="9">Optimised</text>')

    # savings annotation
    lines.append(f'<text x="{W - pad["r"] - 5}" y="{pad["t"] + 18}" text-anchor="end" '
                 f'fill="#34d399" font-size="11" font-weight="bold">$29/day \u00b7 $870/mo savings</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_sankey()
    svg2 = svg_heatmap()
    svg3 = svg_reallocation()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>GPU Allocation Optimizer \u00b7 OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
  h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
  .subtitle{{color:#38bdf8;font-size:.85rem;margin-bottom:20px}}
  .kpi-row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:160px}}
  .kpi .val{{font-size:1.7rem;font-weight:700;color:#C74634}}
  .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
  .kpi.blue .val{{color:#38bdf8}}
  .kpi.green .val{{color:#34d399}}
  .kpi.yellow .val{{color:#f59e0b}}
  .charts{{display:flex;flex-direction:column;gap:28px}}
  .chart-card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
  .chart-title{{color:#94a3b8;font-size:.8rem;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}}
  svg{{display:block;max-width:100%;height:auto}}
  footer{{margin-top:28px;color:#475569;font-size:.7rem;text-align:center}}
</style>
</head>
<body>
<h1>GPU Allocation Optimizer</h1>
<p class="subtitle">OCI Robot Cloud \u00b7 port 8641 \u00b7 cycle-145B</p>

<div class="kpi-row">
  <div class="kpi"><div class="val">240</div><div class="lbl">GPU-hrs/day total</div></div>
  <div class="kpi blue"><div class="val">55%</div><div class="lbl">Weekend utilization</div></div>
  <div class="kpi green"><div class="val">+12%</div><div class="lbl">SDG shift to weekend</div></div>
  <div class="kpi yellow"><div class="val">$29/day</div><div class="lbl">Projected savings</div></div>
  <div class="kpi"><div class="val">3%</div><div class="lbl">Reserved burst capacity</div></div>
</div>

<div class="charts">
  <div class="chart-card">
    <div class="chart-title">GPU Allocation Sankey \u2014 240 GPU-hrs/day flow</div>
    {svg1}
  </div>
  <div class="chart-card">
    <div class="chart-title">Utilization Heatmap \u2014 GPU Node \u00d7 Hour of Day</div>
    {svg2}
  </div>
  <div class="chart-card">
    <div class="chart-title">Reallocation Recommendation \u2014 Current vs Optimised</div>
    {svg3}
  </div>
</div>

<footer>OCI Robot Cloud \u00b7 GPU Allocation Optimizer \u00b7 port 8641</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="GPU Allocation Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gpu_allocation_optimizer", "port": 8641}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8641)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"gpu_allocation_optimizer","port":8641}'
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", 8641), Handler).serve_forever()
