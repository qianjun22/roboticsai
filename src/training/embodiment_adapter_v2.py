"""Embodiment Adapter V2 — FastAPI port 8852"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8852

# Robot types and their transfer efficiency data (v1 vs v2)
ROBOT_DATA = [
    {"name": "UR5e",      "v1": 89, "v2": 93},
    {"name": "UR10e",     "v1": 87, "v2": 92},
    {"name": "Franka",    "v1": 85, "v2": 91},
    {"name": "Kuka iiwa", "v1": 83, "v2": 90},
    {"name": "ABB YuMi",  "v1": 81, "v2": 88},
    {"name": "Spot Arm",  "v1": 78, "v2": 86},
    {"name": "HEBI",      "v1": 76, "v2": 84},
    {"name": "Kinova",    "v1": 80, "v2": 87},
    {"name": "Doosan",    "v1": 77, "v2": 85},
    {"name": "Fanuc CR",  "v1": 74, "v2": 82},
    {"name": "IIWA 14",   "v1": 82, "v2": 89},
    {"name": "xArm7",     "v1": 79, "v2": 86},
]

def build_svg_chart():
    # Bar chart: v1 (gray) vs v2 (Oracle red) per robot type
    bar_w = 14
    gap = 4
    group_w = bar_w * 2 + gap + 10
    chart_w = len(ROBOT_DATA) * group_w + 60
    chart_h = 260
    bars = []
    labels = []
    for i, r in enumerate(ROBOT_DATA):
        x_base = 40 + i * group_w
        # v1 bar
        h1 = math.floor((r["v1"] / 100) * 200)
        y1 = 210 - h1
        bars.append(f'<rect x="{x_base}" y="{y1}" width="{bar_w}" height="{h1}" fill="#64748b" rx="2"/>')
        bars.append(f'<text x="{x_base + bar_w//2}" y="{y1 - 3}" text-anchor="middle" font-size="8" fill="#94a3b8">{r["v1"]}</text>')
        # v2 bar
        h2 = math.floor((r["v2"] / 100) * 200)
        y2 = 210 - h2
        x2 = x_base + bar_w + gap
        bars.append(f'<rect x="{x2}" y="{y2}" width="{bar_w}" height="{h2}" fill="#C74634" rx="2"/>')
        bars.append(f'<text x="{x2 + bar_w//2}" y="{y2 - 3}" text-anchor="middle" font-size="8" fill="#f87171">{r["v2"]}</text>')
        # Label
        lx = x_base + bar_w + gap // 2
        labels.append(f'<text x="{lx}" y="230" text-anchor="middle" font-size="8" fill="#94a3b8" transform="rotate(-35,{lx},230)">{r["name"]}</text>')
    bars_svg = "\n    ".join(bars)
    labels_svg = "\n    ".join(labels)
    # Y-axis ticks
    ticks = ""
    for pct in [60, 70, 80, 90, 100]:
        y = 210 - math.floor((pct / 100) * 200)
        ticks += f'<line x1="35" y1="{y}" x2="{chart_w - 10}" y2="{y}" stroke="#334155" stroke-width="0.5"/>'
        ticks += f'<text x="30" y="{y + 4}" text-anchor="end" font-size="8" fill="#64748b">{pct}%</text>'
    legend = (
        f'<rect x="{chart_w - 120}" y="10" width="10" height="10" fill="#64748b" rx="1"/>'
        f'<text x="{chart_w - 107}" y="19" font-size="9" fill="#94a3b8">v1 baseline</text>'
        f'<rect x="{chart_w - 120}" y="26" width="10" height="10" fill="#C74634" rx="1"/>'
        f'<text x="{chart_w - 107}" y="35" font-size="9" fill="#f87171">v2 LoRA</text>'
    )
    return (
        f'<svg viewBox="0 0 {chart_w} {chart_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{chart_w}px;background:#0f172a">'
        f'{ticks}{bars_svg}\n    {labels_svg}\n    {legend}'
        f'<text x="{chart_w//2}" y="{chart_h - 5}" text-anchor="middle" font-size="10" fill="#38bdf8">'
        f'Transfer Efficiency (%) — v1 vs v2 per Robot Type</text>'
        f'</svg>'
    )

def build_html():
    chart = build_svg_chart()
    return f"""<!DOCTYPE html><html><head><title>Embodiment Adapter V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:10px 20px 10px 0}}.metric .val{{font-size:2em;font-weight:bold;color:#C74634}}
.metric .lbl{{font-size:0.8em;color:#94a3b8}}.badge{{display:inline-block;padding:3px 10px;
border-radius:12px;font-size:0.8em;margin:4px;background:#0f172a;border:1px solid #38bdf8;color:#38bdf8}}</style></head>
<body><h1>Embodiment Adapter V2</h1>
<p style="color:#94a3b8">Shared GR00T backbone + per-robot LoRA adapter + kinematic projection layer. Port {PORT}.</p>
<div class="card"><h2>Key Metrics</h2>
  <div class="metric"><div class="val">93%</div><div class="lbl">UR5e Transfer Efficiency (v2)</div></div>
  <div class="metric"><div class="val">+8pp</div><div class="lbl">Improvement over v1 (89%)</div></div>
  <div class="metric"><div class="val">2M</div><div class="lbl">Optimal LoRA Params</div></div>
  <div class="metric"><div class="val">12</div><div class="lbl">Robot Types by Sep 2026</div></div>
</div>
<div class="card"><h2>Architecture</h2>
  <div class="badge">Shared GR00T Backbone (frozen)</div>
  <div class="badge">Per-Robot LoRA Adapter (2M params)</div>
  <div class="badge">Kinematic Projection Layer</div>
  <div class="badge">Joint-Space Normalization</div>
  <div class="badge">Rank-16 LoRA (r=16, alpha=32)</div>
</div>
<div class="card"><h2>Transfer Efficiency: v1 vs v2 by Robot Type</h2>
{chart}
</div>
<div class="card"><h2>V2 Improvements</h2>
  <ul>
    <li>+4pp average improvement across all 12 robot types</li>
    <li>Kinematic projection layer reduces DoF mismatch penalty by 61%</li>
    <li>2M param LoRA sweet-spot: 3.1× fewer params than v1 full adapter</li>
    <li>Fine-tune time per new robot: 4.2h (v1: 11.7h) on A100</li>
    <li>Target: 12 certified robot types by Sep 2026</li>
  </ul>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Embodiment Adapter V2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "service": "embodiment_adapter_v2",
            "port": PORT,
            "ur5e_transfer_v2": 0.93,
            "ur5e_transfer_v1": 0.89,
            "improvement_pp": 8,
            "lora_params_M": 2,
            "robot_types_supported": len(ROBOT_DATA),
            "robot_types_target_sep2026": 12,
        }

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
