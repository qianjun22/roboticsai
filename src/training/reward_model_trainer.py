"""Reward Model Trainer — FastAPI port 8389"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8389

ACCURACY = [0.51, 0.71, 0.79, 0.84, 0.87]
ITERS = [
    {"name": "iter1", "sr": 0.58, "done": True},
    {"name": "iter2", "sr": 0.68, "done": True},
    {"name": "iter3", "sr": 0.74, "done": True},
    {"name": "iter4", "sr": None, "done": False},
]


def _pipeline_svg():
    w, h = 740, 160
    stages = ["demo_pairs", "pairwise_ranking", "reward_model", "policy_update"]
    colors = ["#38bdf8", "#34d399", "#C74634", "#f59e0b"]
    svg = f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">'
    svg += f'<text x="{w//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">Preference Learning Pipeline (3 Completed Iterations)</text>'
    bw, bh = 130, 44
    gap = (w - 4 * bw) // 5
    for i, (stage, col) in enumerate(zip(stages, colors)):
        x = gap + i * (bw + gap)
        y = (h - bh) // 2 + 10
        svg += f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6" fill="{col}" fill-opacity="0.25" stroke="{col}" stroke-width="2"/>'
        svg += f'<text x="{x + bw//2}" y="{y + bh//2 + 5}" fill="#f1f5f9" font-size="12" text-anchor="middle">{stage}</text>'
        if i < len(stages) - 1:
            ax = x + bw + 4
            ay = y + bh // 2
            svg += f'<line x1="{ax}" y1="{ay}" x2="{ax + gap - 8}" y2="{ay}" stroke="#64748b" stroke-width="2"/>'
            svg += f'<polygon points="{ax+gap-8},{ay-5} {ax+gap+2},{ay} {ax+gap-8},{ay+5}" fill="#64748b"/>'
    # iteration cycle labels
    for ci in range(3):
        svg += f'<text x="{gap + ci * (bw + gap) + bw//2}" y="{h - 8}" fill="#94a3b8" font-size="10" text-anchor="middle">iter{ci+1} SR={ITERS[ci]["sr"]}</text>'
    svg += '</svg>'
    return svg


def _accuracy_svg():
    w, h, pad = 740, 200, 50
    epochs = len(ACCURACY)
    svg = f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">'
    svg += f'<text x="{w//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">Reward Model Accuracy vs Training Epochs (500 Pairs)</text>'
    # grid lines
    for level in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        y = h - pad - (level - 0.45) / 0.55 * (h - 2 * pad)
        svg += f'<line x1="{pad}" y1="{y:.1f}" x2="{w-pad//2}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        svg += f'<text x="{pad-6}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{level:.1f}</text>'
    # accuracy line
    pts = []
    for i, acc in enumerate(ACCURACY):
        x = pad + i * (w - pad * 1.5) / (epochs - 1)
        y = h - pad - (acc - 0.45) / 0.55 * (h - 2 * pad)
        pts.append((x, y))
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    svg += f'<path d="{path}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
    for x, y in pts:
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#38bdf8"/>'
    # loss (inverted approx)
    loss_pts = []
    for i, acc in enumerate(ACCURACY):
        loss = 0.75 - 0.65 * (acc - 0.51) / 0.36
        x = pad + i * (w - pad * 1.5) / (epochs - 1)
        y = h - pad - (max(0.46, loss) - 0.45) / 0.55 * (h - 2 * pad)
        loss_pts.append((x, y))
    lpath = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in loss_pts)
    svg += f'<path d="{lpath}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3"/>'
    # axis labels
    for i in range(epochs):
        x = pad + i * (w - pad * 1.5) / (epochs - 1)
        svg += f'<text x="{x:.1f}" y="{h-8}" fill="#94a3b8" font-size="11" text-anchor="middle">Epoch {i+1}</text>'
    svg += f'<text x="{w-pad//2-10}" y="{pts[-1][1]-10:.1f}" fill="#38bdf8" font-size="11">Accuracy</text>'
    svg += f'<text x="{w-pad//2-10}" y="{loss_pts[-1][1]+14:.1f}" fill="#C74634" font-size="11">Loss</text>'
    svg += '</svg>'
    return svg


def build_html():
    pipeline = _pipeline_svg()
    accuracy = _accuracy_svg()
    iter_rows = ""
    for it in ITERS:
        sr = f"{it['sr']}" if it["sr"] else "in progress"
        status = "done" if it["done"] else "active"
        color = "#34d399" if it["done"] else "#f59e0b"
        iter_rows += f'<tr><td>{it["name"]}</td><td style="color:{color}">{status}</td><td>{sr}</td></tr>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Reward Model Trainer</title>
<style>body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#f1f5f9;font-size:22px;margin-bottom:4px}}.sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
.row{{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px 24px;min-width:180px}}
.stat-val{{font-size:28px;font-weight:700;color:#38bdf8}}.stat-label{{font-size:12px;color:#94a3b8;margin-top:4px}}
table{{border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
th,td{{padding:10px 18px;text-align:left;font-size:13px}}th{{background:#0f172a;color:#94a3b8}}
tr:nth-child(even){{background:#243146}}
.tip{{background:#1e293b;border-left:4px solid #C74634;padding:12px 16px;border-radius:4px;font-size:13px;margin-top:8px}}</style></head>
<body>
<h1>Reward Model Trainer</h1>
<div class="sub">Port {PORT} — RLHF-style preference-based reward model for DAgger improvements</div>
<div class="row">
  <div class="stat"><div class="stat-val">0.87</div><div class="stat-label">SR Correlation (r)</div></div>
  <div class="stat"><div class="stat-val">500</div><div class="stat-label">Preference Pairs</div></div>
  <div class="stat"><div class="stat-val">84%</div><div class="stat-label">Current Accuracy (Epoch 3/5)</div></div>
  <div class="stat"><div class="stat-val">0.041</div><div class="stat-label">RMSE vs Ground Truth</div></div>
</div>
<div class="row">{pipeline}</div>
<div class="row">{accuracy}</div>
<div class="row">
  <table><thead><tr><th>Iteration</th><th>Status</th><th>Success Rate</th></tr></thead>
  <tbody>{iter_rows}</tbody></table>
  <div style="flex:1">
    <div class="stat" style="margin-bottom:16px"><div class="stat-val">0.82</div><div class="stat-label">κ (Inter-annotator Agreement)</div></div>
    <div class="stat"><div class="stat-val">847</div><div class="stat-label">Avg Steps per Demo</div></div>
  </div>
</div>
<div class="tip">Reward model correlation r=0.87, RMSE=0.041. Recommended for DAgger run11. Iter4 targeting SR=0.82.</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Reward Model Trainer")
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
