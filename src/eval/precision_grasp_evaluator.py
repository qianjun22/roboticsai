# Precision Grasp Evaluator — port 8978
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Precision Grasp Evaluator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1rem; }
  .dim-row { display: flex; align-items: center; margin-bottom: 0.6rem; }
  .dim-label { width: 180px; color: #cbd5e1; font-size: 0.85rem; }
  .dim-bar-bg { flex: 1; background: #0f172a; border-radius: 4px; height: 10px; overflow: hidden; }
  .dim-bar { height: 10px; border-radius: 4px; background: #38bdf8; }
  .dim-val { width: 46px; text-align: right; color: #94a3b8; font-size: 0.82rem; margin-left: 8px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Precision Grasp Evaluator</h1>
<p class="subtitle">6-Dimension Grasp Quality Analysis &mdash; Port 8978</p>

<div class="grid">
  <div class="card">
    <h2>Grasp Quality Radar</h2>
    <svg width="100%" viewBox="0 0 320 280" xmlns="http://www.w3.org/2000/svg">
      <!-- Radar grid -->
      <g transform="translate(160,145)">
        <!-- Grid rings -->
        <polygon points="0,-90 77.9,-45 77.9,45 0,90 -77.9,45 -77.9,-45" fill="none" stroke="#334155" stroke-width="1"/>
        <polygon points="0,-67.5 58.4,-33.75 58.4,33.75 0,67.5 -58.4,33.75 -58.4,-33.75" fill="none" stroke="#334155" stroke-width="1"/>
        <polygon points="0,-45 38.97,-22.5 38.97,22.5 0,45 -38.97,22.5 -38.97,-22.5" fill="none" stroke="#334155" stroke-width="1"/>
        <polygon points="0,-22.5 19.5,-11.25 19.5,11.25 0,22.5 -19.5,11.25 -19.5,-11.25" fill="none" stroke="#334155" stroke-width="1"/>
        <!-- Axes -->
        <line x1="0" y1="0" x2="0" y2="-90" stroke="#475569" stroke-width="1"/>
        <line x1="0" y1="0" x2="77.9" y2="-45" stroke="#475569" stroke-width="1"/>
        <line x1="0" y1="0" x2="77.9" y2="45" stroke="#475569" stroke-width="1"/>
        <line x1="0" y1="0" x2="0" y2="90" stroke="#475569" stroke-width="1"/>
        <line x1="0" y1="0" x2="-77.9" y2="45" stroke="#475569" stroke-width="1"/>
        <line x1="0" y1="0" x2="-77.9" y2="-45" stroke="#475569" stroke-width="1"/>
        <!-- Data: contact_stability=0.91, force_distribution=0.88, approach_angle=0.85,
                   post_grasp=0.82, pre_grasp=0.79, transfer=0.76  -->
        <!-- scaled by 90 -->
        <!-- contact_stability up: 0,−81.9 -->
        <!-- force_dist upper-right: 77.9*0.88*cos30, −45*0.88 → 59.5,−39.6 -->
        <!-- approach_angle lower-right: 77.9*0.85, 45*0.85 → 66.2,38.25 -->
        <!-- post_grasp down: 0, 73.8 -->
        <!-- pre_grasp lower-left: −77.9*0.79, 45*0.79 → −61.5,35.55 -->
        <!-- transfer upper-left: −77.9*0.76, −45*0.76 → −59.2,−34.2 -->
        <polygon
          points="0,-81.9 59.5,-39.6 66.2,38.25 0,73.8 -61.5,35.55 -59.2,-34.2"
          fill="rgba(56,189,248,0.18)" stroke="#38bdf8" stroke-width="2"/>
        <!-- Labels -->
        <text x="0" y="-97" text-anchor="middle" fill="#cbd5e1" font-size="10">Contact Stability 0.91</text>
        <text x="87" y="-52" text-anchor="start" fill="#cbd5e1" font-size="10">Force Dist 0.88</text>
        <text x="87" y="52" text-anchor="start" fill="#cbd5e1" font-size="10">Approach Angle 0.85</text>
        <text x="0" y="108" text-anchor="middle" fill="#cbd5e1" font-size="10">Post-Grasp 0.82</text>
        <text x="-87" y="52" text-anchor="end" fill="#cbd5e1" font-size="10">Pre-Grasp 0.79</text>
        <text x="-87" y="-52" text-anchor="end" fill="#cbd5e1" font-size="10">Transfer 0.76</text>
      </g>
    </svg>
  </div>

  <div class="card">
    <h2>Per-Object Success Rate</h2>
    <svg width="100%" viewBox="0 0 320 240" xmlns="http://www.w3.org/2000/svg">
      <!-- Bars: cube 0.94, cylinder 0.87, bottle 0.79, bowl 0.71, deformable 0.43 -->
      <!-- bar width 48, gap 12, start x=30, bar height max 150 -->
      <g transform="translate(0,10)">
        <!-- y axis -->
        <line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>
        <line x1="40" y1="170" x2="310" y2="170" stroke="#475569" stroke-width="1"/>
        <!-- grid lines -->
        <line x1="40" y1="95" x2="310" y2="95" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="40" y1="20" x2="310" y2="20" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
        <text x="34" y="173" text-anchor="end" fill="#94a3b8" font-size="9">0</text>
        <text x="34" y="98" text-anchor="end" fill="#94a3b8" font-size="9">0.5</text>
        <text x="34" y="23" text-anchor="end" fill="#94a3b8" font-size="9">1.0</text>
        <!-- cube 0.94 → h=141 -->
        <rect x="50" y="29" width="40" height="141" fill="#38bdf8" rx="3"/>
        <text x="70" y="24" text-anchor="middle" fill="#38bdf8" font-size="10">0.94</text>
        <text x="70" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">Cube</text>
        <!-- cylinder 0.87 → h=130.5 -->
        <rect x="104" y="39.5" width="40" height="130.5" fill="#38bdf8" rx="3"/>
        <text x="124" y="34" text-anchor="middle" fill="#38bdf8" font-size="10">0.87</text>
        <text x="124" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">Cylinder</text>
        <!-- bottle 0.79 → h=118.5 -->
        <rect x="158" y="51.5" width="40" height="118.5" fill="#0ea5e9" rx="3"/>
        <text x="178" y="46" text-anchor="middle" fill="#0ea5e9" font-size="10">0.79</text>
        <text x="178" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">Bottle</text>
        <!-- bowl 0.71 → h=106.5 -->
        <rect x="212" y="63.5" width="40" height="106.5" fill="#7dd3fc" rx="3"/>
        <text x="232" y="58" text-anchor="middle" fill="#7dd3fc" font-size="10">0.71</text>
        <text x="232" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">Bowl</text>
        <!-- deformable 0.43 → h=64.5 -->
        <rect x="266" y="105.5" width="40" height="64.5" fill="#C74634" rx="3"/>
        <text x="286" y="100" text-anchor="middle" fill="#C74634" font-size="10">0.43</text>
        <text x="286" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">Deform.</text>
      </g>
    </svg>
  </div>
</div>

<div class="card" style="margin-top:1.5rem;">
  <h2>6-Dimension Grasp Quality Breakdown</h2>
  <div class="dim-row"><span class="dim-label">Contact Stability</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:91%"></div></div><span class="dim-val">0.91</span></div>
  <div class="dim-row"><span class="dim-label">Force Distribution</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:88%"></div></div><span class="dim-val">0.88</span></div>
  <div class="dim-row"><span class="dim-label">Approach Angle</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:85%"></div></div><span class="dim-val">0.85</span></div>
  <div class="dim-row"><span class="dim-label">Post-Grasp Stability</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:82%"></div></div><span class="dim-val">0.82</span></div>
  <div class="dim-row"><span class="dim-label">Pre-Grasp Configuration</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:79%"></div></div><span class="dim-val">0.79</span></div>
  <div class="dim-row"><span class="dim-label">In-Hand Transfer</span>
    <div class="dim-bar-bg"><div class="dim-bar" style="width:76%"></div></div><span class="dim-val">0.76</span></div>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Precision Grasp Evaluator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "precision_grasp_evaluator", "port": 8978}

    @app.get("/metrics")
    def metrics():
        dims = {
            "contact_stability": 0.91,
            "force_distribution": 0.88,
            "approach_angle": 0.85,
            "post_grasp": 0.82,
            "pre_grasp": 0.79,
            "transfer": 0.76,
        }
        objects = {
            "cube": 0.94,
            "cylinder": 0.87,
            "bottle": 0.79,
            "bowl": 0.71,
            "deformable": 0.43,
        }
        overall = sum(dims.values()) / len(dims)
        return {"dimensions": dims, "per_object_success": objects, "overall_quality": round(overall, 4)}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8978)
    else:
        server = HTTPServer(("0.0.0.0", 8978), Handler)
        print("Serving on http://0.0.0.0:8978 (fallback HTTPServer)")
        server.serve_forever()
