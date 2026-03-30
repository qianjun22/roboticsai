"""Checkpoint Comparison Dashboard — FastAPI port 8394"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8394

CHECKPOINTS = [
    {"name": "bc_500",          "sr": 0.05, "mae": 0.103, "latency": 247, "robustness": 0.41, "cost": 0.80, "stability": 0.62, "status": "ARCHIVED"},
    {"name": "dagger_run5",     "sr": 0.31, "mae": 0.058, "latency": 231, "robustness": 0.61, "cost": 0.71, "stability": 0.73, "status": "ARCHIVED"},
    {"name": "dagger_run9",     "sr": 0.71, "mae": 0.016, "latency": 226, "robustness": 0.82, "cost": 0.89, "stability": 0.87, "status": "PRODUCTION"},
    {"name": "groot_v2",        "sr": 0.78, "mae": 0.014, "latency": 226, "robustness": 0.85, "cost": 0.88, "stability": 0.89, "status": "STAGING"},
    {"name": "groot_v3_partial","sr": 0.83, "mae": 0.012, "latency": 228, "robustness": 0.88, "cost": 0.87, "stability": 0.91, "status": "IN_TRAINING"},
]

WATERFALL = [
    {"label": "bc_500",          "sr": 0.05},
    {"label": "dagger_run5",     "sr": 0.31},
    {"label": "dagger_run9",     "sr": 0.71},
    {"label": "groot_v2",        "sr": 0.78},
    {"label": "groot_v3_partial","sr": 0.83},
]

STATUS_COLOR = {
    "PRODUCTION": "#C74634",
    "STAGING":    "#38bdf8",
    "IN_TRAINING":"#facc15",
    "ARCHIVED":   "#64748b",
}

def build_radar_svg():
    metrics = ["SR", "robustness", "stability", "cost", "1-MAE", "spd"]
    cx, cy, r = 220, 200, 140
    n = len(metrics)
    svg_lines = [f'<svg width="440" height="420" style="background:#1e293b;border-radius:8px">']
    for i in range(n):
        angle = math.pi/2 - 2*math.pi*i/n
        x2 = cx + r*math.cos(angle)
        y2 = cy - r*math.sin(angle)
        svg_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')
        lx = cx + (r+18)*math.cos(angle)
        ly = cy - (r+18)*math.sin(angle)
        svg_lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" dominant-baseline="middle">{metrics[i]}</text>')
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = math.pi/2 - 2*math.pi*i/n
            px = cx + r*ring*math.cos(angle)
            py = cy - r*ring*math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        svg_lines.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#334155" stroke-width="1"/>')
    colors = ["#64748b","#64748b","#C74634","#38bdf8","#facc15"]
    for ci, ck in enumerate(CHECKPOINTS):
        vals = [
            ck["sr"],
            ck["robustness"],
            ck["stability"],
            ck["cost"],
            1 - ck["mae"] / 0.103,
            1 - (ck["latency"] - 220) / 30,
        ]
        vals = [max(0, min(1, v)) for v in vals]
        pts = []
        for i, v in enumerate(vals):
            angle = math.pi/2 - 2*math.pi*i/n
            px = cx + r*v*math.cos(angle)
            py = cy - r*v*math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        col = STATUS_COLOR.get(ck["status"], "#64748b")
        sw = 2.5 if ck["status"] == "PRODUCTION" else 1.5
        op = 0.85 if ck["status"] == "PRODUCTION" else 0.5
        svg_lines.append(f'<polygon points="{" ".join(pts)}" fill="{col}" fill-opacity="0.15" stroke="{col}" stroke-width="{sw}" opacity="{op}"/>')
    svg_lines.append(f'<text x="{cx}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">6-Metric Radar — Top 5 Checkpoints</text>')
    for ci, ck in enumerate(CHECKPOINTS):
        col = STATUS_COLOR.get(ck["status"], "#64748b")
        svg_lines.append(f'<rect x="10" y="{340+ci*14}" width="10" height="10" fill="{col}"/>')
        svg_lines.append(f'<text x="24" y="{349+ci*14}" fill="#cbd5e1" font-size="10">{ck["name"]} ({ck["status"]})</text>')
    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)

def build_waterfall_svg():
    w, h = 500, 280
    pad_l, pad_b = 60, 40
    chart_w = w - pad_l - 20
    chart_h = h - pad_b - 40
    bar_w = chart_w // len(WATERFALL) - 10
    svg = [f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">']
    svg.append(f'<text x="{w//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">SR Delta Waterfall</text>')
    max_sr = 1.0
    def ys(sr):
        return pad_b + chart_h - int(sr / max_sr * chart_h)
    prev = 0.0
    for i, wf in enumerate(WATERFALL):
        x = pad_l + i * (bar_w + 10)
        delta = wf["sr"] - prev
        y_bot = ys(prev)
        bh = int(delta / max_sr * chart_h)
        color = "#C74634" if wf["label"] == "dagger_run9" else "#38bdf8"
        svg.append(f'<rect x="{x}" y="{y_bot-bh}" width="{bar_w}" height="{bh}" fill="{color}" rx="2"/>')
        svg.append(f'<text x="{x+bar_w//2}" y="{y_bot-bh-5}" fill="#f8fafc" font-size="10" text-anchor="middle">+{delta:.2f}</text>')
        svg.append(f'<text x="{x+bar_w//2}" y="{ys(0)+14}" fill="#94a3b8" font-size="9" text-anchor="middle">{wf["label"]}</text>')
        prev = wf["sr"]
    svg.append(f'<line x1="{pad_l}" y1="{ys(0)}" x2="{w-20}" y2="{ys(0)}" stroke="#475569" stroke-width="1"/>')
    svg.append('</svg>')
    return '\n'.join(svg)

def build_html():
    radar = build_radar_svg()
    waterfall = build_waterfall_svg()
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Checkpoint Comparison Dashboard</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:24px}}
h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}.sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
.row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px}}
.stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:180px}}
.sv{{font-size:1.5rem;font-weight:bold;color:#38bdf8}}
.sl{{font-size:.8rem;color:#94a3b8;margin-top:4px}}
.prod{{color:#C74634!important}}
</style></head><body>
<h1>Checkpoint Comparison Dashboard</h1>
<div class='sub'>Side-by-side comparison of top GR00T checkpoints &mdash; Port {PORT}</div>
<div class='row'>
  <div class='stat'><div class='sv prod'>0.71</div><div class='sl'>PRODUCTION SR (dagger_run9_v2.2)</div></div>
  <div class='stat'><div class='sv'>0.78</div><div class='sl'>STAGING SR (groot_v2) &nbsp;+7pp</div></div>
  <div class='stat'><div class='sv'>0.83</div><div class='sl'>groot_v3_partial SR (projected)</div></div>
  <div class='stat'><div class='sv'>+0.73</div><div class='sl'>Total SR gain vs BC baseline</div></div>
</div>
<div class='row'>
  <div>{radar}</div>
  <div>{waterfall}</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Comparison Dashboard")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {{"status": "ok", "port": PORT}}

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
