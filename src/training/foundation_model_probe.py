"""Foundation Model Probe — FastAPI port 8457"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8457

def build_html():
    random.seed(31)
    # layer probing accuracy bar
    layers = list(range(1, 13))
    concepts = ["depth", "object_id", "grasp_pos", "orientation", "motion", "phase"]
    concept_colors = ["#38bdf8", "#22c55e", "#C74634", "#f59e0b", "#8b5cf6", "#ec4899"]
    probe_data = {
        "depth":      [0.42, 0.51, 0.58, 0.63, 0.67, 0.71, 0.74, 0.76, 0.73, 0.69, 0.65, 0.60],
        "object_id":  [0.55, 0.64, 0.72, 0.78, 0.81, 0.83, 0.82, 0.80, 0.77, 0.73, 0.68, 0.62],
        "grasp_pos":  [0.38, 0.47, 0.55, 0.62, 0.70, 0.77, 0.84, 0.87, 0.85, 0.81, 0.76, 0.70],
        "orientation":[0.40, 0.48, 0.54, 0.59, 0.64, 0.69, 0.73, 0.77, 0.78, 0.76, 0.72, 0.67],
        "motion":     [0.35, 0.43, 0.50, 0.57, 0.62, 0.66, 0.69, 0.71, 0.73, 0.75, 0.74, 0.72],
        "phase":      [0.45, 0.54, 0.63, 0.71, 0.78, 0.82, 0.81, 0.79, 0.76, 0.72, 0.67, 0.62],
    }
    probe_lines = ""
    for concept, color in zip(concepts, concept_colors):
        vals = probe_data[concept]
        pts = " ".join(f"{35+i*26:.1f},{150-vals[i]*130:.1f}" for i in range(12))
        probe_lines += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8"/>'
    # best layer marker for grasp_pos (layer 8)
    probe_lines += f'<circle cx="{35+7*26}" cy="{150-0.87*130:.1f}" r="5" fill="#C74634"/>'
    probe_lines += f'<text x="{35+7*26+7}" y="{150-0.87*130-4:.1f}" fill="#C74634" font-size="9">grasp_pos peak L8</text>'
    for i, l in enumerate(layers):
        probe_lines += f'<text x="{35+i*26}" y="163" fill="#64748b" font-size="9" text-anchor="middle">L{l}</text>'

    # UMAP cluster scatter
    task_clusters = [
        ("pick_place", "#C74634", [(120, 80), (130, 95), (115, 85), (125, 90), (118, 88)]),
        ("push", "#38bdf8", [(220, 130), (230, 120), (215, 135), (225, 125), (218, 128)]),
        ("stack", "#22c55e", [(160, 180), (170, 175), (155, 185), (165, 178), (162, 182)]),
        ("grasp_only", "#f59e0b", [(80, 150), (90, 145), (75, 155), (85, 148), (82, 152)]),
    ]
    umap_svg = ""
    for label, color, points in task_clusters:
        for px, py in points:
            px += random.gauss(0, 5)
            py += random.gauss(0, 5)
            umap_svg += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{color}" opacity="0.8"/>'
        cx_avg = sum(p[0] for p in points) / len(points)
        cy_avg = sum(p[1] for p in points) / len(points)
        umap_svg += f'<text x="{cx_avg:.1f}" y="{cy_avg-14:.1f}" fill="{color}" font-size="10" text-anchor="middle">{label}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Foundation Model Probe</title>
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
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:5px;font-size:10px}}
.ld{{width:10px;height:10px;border-radius:50%}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Foundation Model Probe — GR00T Layer Analysis</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">Layer 8</div><div class="ml">Best Grasp Geometry</div><div class="delta">probe acc 0.87</div></div>
  <div class="m"><div class="mv">Layer 6</div><div class="ml">Best Object ID</div><div class="delta">probe acc 0.83</div></div>
  <div class="m"><div class="mv">0.91</div><div class="ml">Cluster Purity (UMAP)</div></div>
  <div class="m"><div class="mv">12</div><div class="ml">Transformer Layers Probed</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Layer Probing Accuracy by Spatial Concept</h3>
    <svg viewBox="0 0 360 180" width="100%">
      <line x1="30" y1="10" x2="30" y2="155" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="155" x2="350" y2="155" stroke="#334155" stroke-width="1"/>
      {probe_lines}
    </svg>
    <div class="legend">
      {''.join(f'<div class="li"><div class="ld" style="background:{c}"></div>{l}</div>' for l, c in zip(concepts, concept_colors))}
    </div>
  </div>
  <div class="card">
    <h3>Activation UMAP (L8, task clusters)</h3>
    <svg viewBox="0 0 310 220" width="100%">
      <rect width="310" height="220" fill="#0f172a" rx="6"/>
      {umap_svg}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Foundation Model Probe")
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
