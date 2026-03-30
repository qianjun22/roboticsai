"""GR00T Deployment Advisor — FastAPI port 8450"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8450

def build_html():
    # 8-criteria deployment decision matrix
    criteria = ["SR", "Latency", "Cost", "VRAM", "Stability", "Compliance", "Partner Impact", "Rollback Risk"]
    configs = {
        "Cloud A100": [0.78, 0.72, 0.90, 0.88, 0.91, 0.95, 0.82, 0.94],
        "Cloud H100":  [0.82, 0.88, 0.52, 0.84, 0.93, 0.95, 0.89, 0.91],
        "Edge Jetson": [0.71, 0.95, 0.97, 0.98, 0.82, 0.88, 0.74, 0.87],
        "Hybrid":      [0.80, 0.85, 0.78, 0.90, 0.89, 0.93, 0.87, 0.92],
    }
    colors = {"Cloud A100": "#C74634", "Cloud H100": "#38bdf8", "Edge Jetson": "#22c55e", "Hybrid": "#f59e0b"}

    # radar chart
    n = len(criteria)
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    cx, cy, r = 200, 160, 120
    radar_rings = ""
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{cx + r*ring*math.cos(a):.1f},{cy + r*ring*math.sin(a):.1f}" for a in angles)
        radar_rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
    for a, c in zip(angles, criteria):
        x2 = cx + r * math.cos(a)
        y2 = cy + r * math.sin(a)
        radar_rings += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r + 18) * math.cos(a)
        ly = cy + (r + 18) * math.sin(a)
        radar_rings += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{c}</text>'

    radar_polys = ""
    for cfg, vals in configs.items():
        pts = " ".join(f"{cx + r*v*math.cos(a):.1f},{cy + r*v*math.sin(a):.1f}" for v, a in zip(vals, angles))
        color = colors[cfg]
        radar_polys += f'<polygon points="{pts}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.8"/>'

    # score summary bar
    score_bars = ""
    sorted_configs = sorted(configs.items(), key=lambda x: -sum(x[1]))
    for i, (cfg, vals) in enumerate(sorted_configs):
        score = sum(vals) / len(vals)
        w = int(score * 260)
        color = colors[cfg]
        score_bars += f'<rect x="90" y="{15 + i*36}" width="{w}" height="24" fill="{color}" rx="4" opacity="0.85"/>'
        score_bars += f'<text x="86" y="{15 + i*36 + 16}" fill="#94a3b8" font-size="11" text-anchor="end">{cfg}</text>'
        score_bars += f'<text x="{90+w+6}" y="{15 + i*36 + 16}" fill="#e2e8f0" font-size="11">{score:.2f}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>GR00T Deployment Advisor</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:22px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.rec{{font-size:12px;color:#22c55e;margin-top:4px}}
.legend{{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ld{{width:12px;height:12px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>GR00T Deployment Advisor — Multi-Config Decision Matrix</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">Hybrid</div><div class="ml">Recommended Config</div><div class="rec">Jun 2026 scale target</div></div>
  <div class="m"><div class="mv">0.86</div><div class="ml">Hybrid Composite Score</div></div>
  <div class="m"><div class="mv">0.82</div><div class="ml">SR: Cloud H100</div><div class="rec">Best SR config</div></div>
  <div class="m"><div class="mv">Edge Jetson</div><div class="ml">Best Cost+Latency</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>8-Criteria Radar Comparison</h3>
    <svg viewBox="0 0 400 300" width="100%">
      {radar_rings}
      {radar_polys}
    </svg>
    <div class="legend">
      {''.join(f'<div class="li"><div class="ld" style="background:{colors[c]}"></div>{c}</div>' for c in configs)}
    </div>
  </div>
  <div class="card">
    <h3>Composite Score by Config</h3>
    <svg viewBox="0 0 390 165" width="100%">
      {score_bars}
    </svg>
    <p style="font-size:11px;color:#22c55e;margin:8px 0 0">&#9650; Hybrid recommended: balances SR (0.80), cost (0.78), and compliance (0.93) — optimal for Jun 2026 multi-partner scale</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T Deployment Advisor")
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
