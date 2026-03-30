"""Sensor Fusion Analyzer — FastAPI port 8472"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8472

def build_html():
    # modality ablation bar
    configs = [
        ("Wrist RGB only",         0.69),
        ("Overhead only",          0.63),
        ("Proprio only",           0.51),
        ("F-T only",               0.47),
        ("Wrist+Proprio",          0.74),
        ("Wrist+Overhead",         0.76),
        ("Wrist+Overhead+Proprio", 0.79),
        ("All (Wrist+OH+Prop+FT)", 0.81),
    ]
    ablation_bars = ""
    for i, (cfg, sr) in enumerate(configs):
        y = 15 + i * 30
        w = int(sr / 0.85 * 280)
        color = "#22c55e" if sr >= 0.78 else "#38bdf8" if sr >= 0.70 else "#64748b"
        ablation_bars += f'<rect x="195" y="{y}" width="{w}" height="22" fill="{color}" rx="3" opacity="0.85"/>'
        ablation_bars += f'<text x="191" y="{y+15}" fill="#94a3b8" font-size="9" text-anchor="end">{cfg}</text>'
        ablation_bars += f'<text x="{195+w+5}" y="{y+15}" fill="#e2e8f0" font-size="10">{int(sr*100)}%</text>'

    # modality radar per task type
    tasks = ["Pick-Place", "Stack", "Pour", "Push", "Insert"]
    modalities = ["Wrist RGB", "Overhead", "Proprioception", "Force-Torque"]
    mod_colors = ["#C74634", "#38bdf8", "#22c55e", "#f59e0b"]
    n = 4
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    cx, cy, r_rad = 140, 130, 100
    radar = ""
    # radar rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{cx + r_rad*ring*math.cos(a):.1f},{cy + r_rad*ring*math.sin(a):.1f}" for a in angles)
        radar += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
    for a, mod in zip(angles, modalities):
        x2 = cx + r_rad * math.cos(a)
        y2 = cy + r_rad * math.sin(a)
        radar += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r_rad + 16) * math.cos(a)
        ly = cy + (r_rad + 16) * math.sin(a)
        radar += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{mod}</text>'
    # All modalities polygon
    task_scores = [0.89, 0.91, 0.84, 0.76]
    pts = " ".join(f"{cx + r_rad*s*math.cos(a):.1f},{cy + r_rad*s*math.sin(a):.1f}" for s, a in zip(task_scores, angles))
    radar += f'<polygon points="{pts}" fill="#C74634" fill-opacity="0.2" stroke="#C74634" stroke-width="2"/>'
    radar += f'<text x="{cx}" y="{cy+130}" fill="#C74634" font-size="10" text-anchor="middle">Pick-Place (all modalities)</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Sensor Fusion Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Sensor Fusion Analyzer — Modality Ablation</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">81%</div><div class="ml">All Modalities SR</div></div>
  <div class="m"><div class="mv">+12pp</div><div class="ml">vs Wrist RGB Only</div></div>
  <div class="m"><div class="mv">+4pp</div><div class="ml">F-T for Contact Tasks</div></div>
  <div class="m"><div class="mv">Overhead</div><div class="ml">Best for Stack/Place</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Modality Ablation (8 configs)</h3>
    <svg viewBox="0 0 520 255" width="100%">
      <line x1="193" y1="10" x2="193" y2="250" stroke="#334155" stroke-width="1"/>
      {ablation_bars}
    </svg>
  </div>
  <div class="card">
    <h3>Modality Contribution (Pick-Place)</h3>
    <svg viewBox="0 0 320 275" width="100%">
      {radar}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sensor Fusion Analyzer")
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
