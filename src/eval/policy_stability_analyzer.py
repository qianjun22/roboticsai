"""Policy Stability Analyzer — FastAPI port 8388"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8388

RUNS = {
    "bc_baseline":      [0.61, 0.67, 0.59, 0.72, 0.71],
    "dagger_run5":      [0.71, 0.73, 0.68, 0.75, 0.74],
    "dagger_run9":      [0.82, 0.85, 0.79, 0.88, 0.86],
    "groot_v2":         [0.87, 0.89, 0.84, 0.92, 0.91],
    "groot_v3_partial": [0.88, 0.91, 0.85, 0.93, 0.91],
}
AXES = ["variance", "consistency", "drift", "robustness", "calibration"]
COLORS = ["#94a3b8", "#38bdf8", "#34d399", "#C74634", "#f59e0b"]
INSTABILITY = [(280, 320, "grasp_phase"), (520, 540, "regrasp"), (700, 710, "precision_lift")]
TOTAL_STEPS = 847


def _radar_svg():
    cx, cy, r = 220, 220, 160
    n = len(AXES)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def pt(val, idx):
        a = angles[idx]
        return cx + val * r * math.cos(a), cy - val * r * math.sin(a)

    grid = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(level, i)[0]:.1f},{pt(level, i)[1]:.1f}" for i in range(n))
        grid += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'
    for i in range(n):
        x2, y2 = pt(1.0, i)
        grid += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>\n'
        lx, ly = pt(1.13, i)
        grid += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" dominant-baseline="middle">{AXES[i]}</text>\n'

    polys = ""
    for ri, (name, scores) in enumerate(RUNS.items()):
        pts = " ".join(f"{pt(scores[i], i)[0]:.1f},{pt(scores[i], i)[1]:.1f}" for i in range(n))
        polys += f'<polygon points="{pts}" fill="{COLORS[ri]}" fill-opacity="0.15" stroke="{COLORS[ri]}" stroke-width="2"/>\n'

    legend = ""
    for ri, name in enumerate(RUNS):
        legend += f'<rect x="450" y="{80 + ri * 28}" width="14" height="14" fill="{COLORS[ri]}"/>\n'
        legend += f'<text x="470" y="{92 + ri * 28}" fill="#e2e8f0" font-size="12">{name}</text>\n'

    return f'''<svg width="620" height="440" style="background:#1e293b;border-radius:8px">
  <text x="310" y="28" fill="#f1f5f9" font-size="15" font-weight="bold" text-anchor="middle">5-Run Stability Score Radar</text>
  <g transform="translate(0,20)">{grid}{polys}</g>
  {legend}
</svg>'''


def _timeline_svg():
    w, h, pad = 760, 180, 40
    svg = f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">'
    svg += f'<text x="{w//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">Per-Episode Stability Timeline ({TOTAL_STEPS} steps)</text>'
    # baseline path: stability around 0.89 with small noise
    random.seed(42)
    pts = []
    for s in range(TOTAL_STEPS):
        base = 0.89
        for start, end, _ in INSTABILITY:
            if start <= s <= end:
                base = 0.55 + 0.1 * math.sin(math.pi * (s - start) / (end - start))
                break
        v = base + random.gauss(0, 0.02)
        v = max(0.3, min(1.0, v))
        x = pad + (s / (TOTAL_STEPS - 1)) * (w - 2 * pad)
        y = h - pad - v * (h - 2 * pad - 20)
        pts.append((x, y))
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    # highlight instability windows
    for start, end, label in INSTABILITY:
        x1 = pad + (start / (TOTAL_STEPS - 1)) * (w - 2 * pad)
        x2 = pad + (end / (TOTAL_STEPS - 1)) * (w - 2 * pad)
        svg += f'<rect x="{x1:.1f}" y="{pad}" width="{x2-x1:.1f}" height="{h-2*pad-20}" fill="#f59e0b" fill-opacity="0.25"/>'
        svg += f'<text x="{(x1+x2)/2:.1f}" y="{h-10}" fill="#f59e0b" font-size="10" text-anchor="middle">{label}</text>'
    svg += f'<path d="{path}" fill="none" stroke="#C74634" stroke-width="1.5"/>'
    svg += f'<line x1="{pad}" y1="{h-pad-20}" x2="{w-pad}" y2="{h-pad-20}" stroke="#475569" stroke-width="1"/>'
    svg += f'<text x="{pad}" y="{h-6}" fill="#94a3b8" font-size="10">0</text>'
    svg += f'<text x="{w-pad}" y="{h-6}" fill="#94a3b8" font-size="10">{TOTAL_STEPS}</text>'
    svg += '</svg>'
    return svg


def build_html():
    radar = _radar_svg()
    timeline = _timeline_svg()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Policy Stability Analyzer</title>
<style>body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#f1f5f9;font-size:22px;margin-bottom:4px}}.sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
.row{{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px 24px;min-width:200px}}
.stat-val{{font-size:28px;font-weight:700;color:#C74634}}.stat-label{{font-size:12px;color:#94a3b8;margin-top:4px}}
.tip{{background:#1e293b;border-left:4px solid #38bdf8;padding:12px 16px;border-radius:4px;font-size:13px;margin-top:8px}}</style></head>
<body>
<h1>Policy Stability Analyzer</h1>
<div class="sub">Port {PORT} — Consistency and stability of robot policy across episodes</div>
<div class="row">
  <div class="stat"><div class="stat-val">0.89</div><div class="stat-label">GR00T_v2 Overall Stability</div></div>
  <div class="stat"><div class="stat-val">0.67</div><div class="stat-label">BC Baseline Stability</div></div>
  <div class="stat"><div class="stat-val">3</div><div class="stat-label">Instability Events Detected</div></div>
  <div class="stat"><div class="stat-val">+32%</div><div class="stat-label">GR00T_v2 vs BC Improvement</div></div>
</div>
<div class="row">{radar}</div>
<div class="row">{timeline}</div>
<div class="tip">Primary instability source: phase transitions (grasp→regrasp→precision_lift). Recommendation: increase chunk overlap at phase boundaries.</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Policy Stability Analyzer")
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
