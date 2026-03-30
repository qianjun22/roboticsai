"""Bimanual Task Tracker — FastAPI port 8397"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8397

TASKS = [
    {"name": "bimanual_pass",   "current": 0.29, "target": 0.71},
    {"name": "bimanual_fold",   "current": 0.14, "target": 0.61},
    {"name": "bimanual_insert", "current": 0.09, "target": 0.54},
    {"name": "bimanual_handoff","current": 0.31, "target": 0.78},
]
PHASES = ["reach", "grasp", "transfer", "place", "release"]
# 5x5 coordination heatmap — diagonal ~0.9, off-diagonal lower, cross-arm ~0.3
HEATMAP = [
    [0.91, 0.72, 0.55, 0.41, 0.33],
    [0.72, 0.88, 0.61, 0.48, 0.37],
    [0.55, 0.61, 0.85, 0.59, 0.44],
    [0.41, 0.48, 0.59, 0.87, 0.68],
    [0.33, 0.37, 0.44, 0.68, 0.90],
]


def _lerp_color(v):
    """0=dark blue, 0.5=mid, 1=bright green"""
    r = int(15 + v * (34 - 15))
    g = int(23 + v * (197 - 23))
    b = int(42 + v * (94 - 42))
    return f"rgb({r},{g},{b})"


def build_html():
    # --- Grouped bar chart SVG ---
    bw, bh = 520, 220
    pad_l, pad_t, pad_b = 140, 30, 30
    inner_w = bw - pad_l - 20
    n = len(TASKS)
    grp_w = inner_w / n
    bar_w = grp_w * 0.35
    bars = ""
    for i, t in enumerate(TASKS):
        x_base = pad_l + i * grp_w + grp_w * 0.1
        max_h = bh - pad_t - pad_b
        # current bar
        ch = t["current"] * max_h
        cy = pad_t + max_h - ch
        bars += f'<rect x="{x_base:.1f}" y="{cy:.1f}" width="{bar_w:.1f}" height="{ch:.1f}" fill="#38bdf8" rx="2"/>'
        bars += f'<text x="{x_base+bar_w/2:.1f}" y="{cy-4:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle">{t["current"]:.2f}</text>'
        # target bar
        th = t["target"] * max_h
        ty = pad_t + max_h - th
        tx = x_base + bar_w + 4
        bars += f'<rect x="{tx:.1f}" y="{ty:.1f}" width="{bar_w:.1f}" height="{th:.1f}" fill="#C74634" rx="2" opacity="0.85"/>'
        bars += f'<text x="{tx+bar_w/2:.1f}" y="{ty-4:.1f}" fill="#C74634" font-size="9" text-anchor="middle">{t["target"]:.2f}</text>'
        # label
        lx = x_base + bar_w
        bars += f'<text x="{lx:.1f}" y="{bh-8}" fill="#94a3b8" font-size="9" text-anchor="middle">{t["name"].replace("bimanual_","")}</text>'
    svg1 = f'''<svg width="{bw}" height="{bh}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#1e293b" rx="8"/>
  <text x="{bw//2}" y="18" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Bimanual Task Success Rate: N1.6 vs N2.0 Target</text>
  {bars}
  <rect x="{pad_l}" y="26" width="12" height="10" fill="#38bdf8"/><text x="{pad_l+15}" y="35" fill="#38bdf8" font-size="10">N1.6 Current</text>
  <rect x="{pad_l+110}" y="26" width="12" height="10" fill="#C74634"/><text x="{pad_l+125}" y="35" fill="#C74634" font-size="10">N2.0 Target</text>
</svg>'''

    # --- Coordination heatmap SVG ---
    hw, hh = 380, 280
    cell = 44
    hpad_l, hpad_t = 70, 50
    cells = ""
    for r in range(5):
        for c in range(5):
            v = HEATMAP[r][c]
            color = _lerp_color(v)
            cx = hpad_l + c * cell
            cy = hpad_t + r * cell
            cells += f'<rect x="{cx}" y="{cy}" width="{cell-2}" height="{cell-2}" fill="{color}" rx="2"/>'
            cells += f'<text x="{cx+cell//2-1}" y="{cy+cell//2+4}" fill="#f1f5f9" font-size="11" text-anchor="middle">{v:.2f}</text>'
    row_labels = "".join(
        f'<text x="{hpad_l-6}" y="{hpad_t+i*cell+cell//2+4}" fill="#94a3b8" font-size="10" text-anchor="end">{PHASES[i]}</text>'
        for i in range(5)
    )
    col_labels = "".join(
        f'<text x="{hpad_l+i*cell+cell//2-1}" y="{hpad_t-8}" fill="#94a3b8" font-size="10" text-anchor="middle">{PHASES[i]}</text>'
        for i in range(5)
    )
    svg2 = f'''<svg width="{hw}" height="{hh}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#1e293b" rx="8"/>
  <text x="{hw//2}" y="18" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Dual-Arm Coordination Heatmap</text>
  <text x="{hw//2}" y="32" fill="#94a3b8" font-size="10" text-anchor="middle">(Left vs Right Arm Synchrony by Task Phase)</text>
  {cells}{row_labels}{col_labels}
  <text x="{hpad_l}" y="{hpad_t+5*cell+18}" fill="#475569" font-size="9">0.0 = no sync</text>
  <text x="{hpad_l+5*cell-20}" y="{hpad_t+5*cell+18}" fill="#22c55e" font-size="9" text-anchor="end">1.0 = perfect sync</text>
</svg>'''

    timeline_rows = "".join([
        "<tr><td>N2.0 API compat layer</td><td>May 2026</td><td style='color:#22c55e'>Planned</td></tr>",
        "<tr><td>Demo collection</td><td>May–Jun 2026</td><td style='color:#f59e0b'>0 demos so far</td></tr>",
        "<tr><td>Fine-tune on bimanual data</td><td>Jul 2026</td><td style='color:#94a3b8'>Pending</td></tr>",
        "<tr><td>Evaluation &amp; benchmark</td><td>Aug 2026</td><td style='color:#94a3b8'>Pending</td></tr>",
    ])
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Bimanual Task Tracker</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:24px}}
h1{{color:#C74634}}table{{border-collapse:collapse;width:100%;margin-top:8px}}td,th{{padding:6px 12px;border:1px solid #334155;font-size:13px}}
th{{background:#1e293b;color:#38bdf8}}.stat{{display:inline-block;background:#1e293b;border-radius:8px;padding:12px 24px;margin:8px;text-align:center}}
.sv{{font-size:28px;font-weight:bold;color:#38bdf8}}.sl{{font-size:12px;color:#94a3b8}}
.warn{{color:#f59e0b}}</style></head><body>
<h1>Bimanual Task Tracker — Port {PORT}</h1>
<div class='stat'><div class='sv'>0.21</div><div class='sl'>Current Avg SR (N1.6)</div></div>
<div class='stat'><div class='sv'>0.71</div><div class='sl'>N2.0 Target Avg SR</div></div>
<div class='stat'><div class='sv warn'>Jun 2026</div><div class='sl'>N2.0 ETA</div></div>
<div class='stat'><div class='sv warn'>0</div><div class='sl'>Bimanual Demos Collected</div></div>
<br/>{svg1}<br/><br/>{svg2}<br/>
<h2 style='color:#38bdf8'>Migration Timeline</h2>
<table><tr><th>Milestone</th><th>Date</th><th>Status</th></tr>{timeline_rows}</table>
<p style='color:#475569;font-size:12px;margin-top:16px'>Note: N1.6 SR limited by single-arm design. Bimanual dataset collection starts May 2026. Demo collection target: 500 demos minimum before fine-tune.</p>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Bimanual Task Tracker")
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
