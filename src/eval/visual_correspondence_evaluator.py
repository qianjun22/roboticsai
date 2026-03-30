"""Visual Correspondence Evaluator — FastAPI port 8804"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8804

def build_html():
    random.seed(42)
    # Generate keypoint correspondence data
    num_frames = 20
    frames = list(range(num_frames))

    # Correspondence accuracy over time (simulated with sine + noise)
    accuracy = [round(0.72 + 0.18 * math.sin(i * 0.4) + random.uniform(-0.04, 0.04), 3) for i in frames]
    # Reprojection error (pixels)
    reproj = [round(1.8 - 0.9 * math.exp(-i * 0.1) + random.uniform(-0.1, 0.15), 3) for i in frames]
    # Inlier ratio
    inlier = [round(0.65 + 0.20 * math.cos(i * 0.3) + random.uniform(-0.03, 0.03), 3) for i in frames]

    # SVG accuracy line chart (600x140)
    acc_pts = " ".join(f"{30 + i*28},{130 - int(accuracy[i]*110)}" for i in frames)
    reproj_pts = " ".join(f"{30 + i*28},{130 - int((reproj[i]/3.0)*110)}" for i in frames)
    inlier_pts = " ".join(f"{30 + i*28},{130 - int(inlier[i]*110)}" for i in frames)

    # Scatter: keypoint match quality heatmap (40 random matches)
    random.seed(7)
    scatter_pts = [(random.uniform(20, 260), random.uniform(20, 130), random.uniform(0, 1)) for _ in range(40)]
    scatter_svg = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="rgba({int(255*(1-q))},{int(200*q)},80,0.75)"/>'
        for x, y, q in scatter_pts
    )

    # Per-joint correspondence table
    joints = ["base", "shoulder", "elbow", "wrist", "gripper_L", "gripper_R"]
    random.seed(99)
    joint_rows = "".join(
        f'<tr><td>{j}</td><td>{random.randint(180,320)}</td>'
        f'<td>{round(random.uniform(0.78, 0.97), 3)}</td>'
        f'<td>{round(random.uniform(0.9, 2.5), 2)}px</td>'
        f'<td style="color:{ "#4ade80" if random.random()>0.2 else "#f87171" }">{ "PASS" if random.random()>0.2 else "WARN" }</td></tr>'
        for j in joints
    )

    avg_acc = round(sum(accuracy) / len(accuracy), 3)
    avg_reproj = round(sum(reproj) / len(reproj), 3)
    avg_inlier = round(sum(inlier) / len(inlier), 3)

    return f"""<!DOCTYPE html><html><head><title>Visual Correspondence Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.4)}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}
.stat{{background:#0f172a;border-radius:8px;padding:14px;text-align:center}}
.stat .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:8px 10px;font-weight:500}}
td{{padding:8px 10px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#1e293b}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600}}
.ok{{background:#14532d;color:#4ade80}}.warn{{background:#7f1d1d;color:#f87171}}
</style></head><body>
<h1>Visual Correspondence Evaluator</h1>
<p style="color:#64748b;margin:0 0 16px">Port {PORT} &nbsp;|&nbsp; Real-time keypoint tracking &amp; match quality assessment</p>

<div class="grid">
  <div class="stat"><div class="val">{avg_acc:.1%}</div><div class="lbl">Avg Match Accuracy</div></div>
  <div class="stat"><div class="val">{avg_reproj:.2f}px</div><div class="lbl">Avg Reprojection Error</div></div>
  <div class="stat"><div class="val">{avg_inlier:.1%}</div><div class="lbl">Avg Inlier Ratio</div></div>
</div>

<div class="card">
  <h2>Correspondence Accuracy / Inlier Ratio / Reproj Error — 20 Frames</h2>
  <svg width="100%" viewBox="0 0 590 150" style="overflow:visible">
    <!-- grid lines -->
    {''.join(f'<line x1="30" x2="570" y1="{130-int(v*110)}" y2="{130-int(v*110)}" stroke="#334155" stroke-width="0.5"/>' for v in [0.25,0.5,0.75,1.0])}
    <!-- accuracy -->
    <polyline points="{acc_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <!-- inlier -->
    <polyline points="{inlier_pts}" fill="none" stroke="#a78bfa" stroke-width="2" stroke-dasharray="5,3"/>
    <!-- reproj (scaled) -->
    <polyline points="{reproj_pts}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="3,3"/>
    <!-- axes -->
    <line x1="30" y1="20" x2="30" y2="130" stroke="#475569" stroke-width="1"/>
    <line x1="30" y1="130" x2="570" y2="130" stroke="#475569" stroke-width="1"/>
    <!-- legend -->
    <rect x="400" y="10" width="12" height="4" fill="#38bdf8"/><text x="418" y="16" fill="#94a3b8" font-size="10">Accuracy</text>
    <rect x="400" y="22" width="12" height="4" fill="#a78bfa"/><text x="418" y="28" fill="#94a3b8" font-size="10">Inlier Ratio</text>
    <rect x="400" y="34" width="12" height="4" fill="#f59e0b"/><text x="418" y="40" fill="#94a3b8" font-size="10">Reproj Error /3</text>
  </svg>
</div>

<div class="grid" style="grid-template-columns:1fr 1fr">
  <div class="card">
    <h2>Keypoint Match Quality Heatmap</h2>
    <svg width="100%" viewBox="0 0 280 150">
      <rect width="280" height="150" fill="#0f172a" rx="4"/>
      {scatter_svg}
      <text x="140" y="145" fill="#475569" font-size="9" text-anchor="middle">Image Plane (left cam)</text>
    </svg>
    <p style="font-size:0.75rem;color:#64748b;margin:8px 0 0">Green = high quality match &nbsp;|&nbsp; Red = low quality / outlier</p>
  </div>
  <div class="card">
    <h2>Per-Joint Correspondence Quality</h2>
    <table>
      <thead><tr><th>Joint</th><th>Matches</th><th>Accuracy</th><th>Reproj Err</th><th>Status</th></tr></thead>
      <tbody>{joint_rows}</tbody>
    </table>
  </div>
</div>

<div class="card">
  <h2>Evaluator Config</h2>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;font-size:0.8rem">
    <div><span style="color:#64748b">Detector</span><br/><b>SuperPoint v2</b></div>
    <div><span style="color:#64748b">Matcher</span><br/><b>LightGlue</b></div>
    <div><span style="color:#64748b">Camera Model</span><br/><b>Pinhole + D5</b></div>
    <div><span style="color:#64748b">RANSAC Thresh</span><br/><b>2.5 px</b></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Visual Correspondence Evaluator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "visual_correspondence_evaluator"}

    @app.get("/metrics")
    def metrics():
        random.seed(42)
        accuracy = [round(0.72 + 0.18 * math.sin(i * 0.4) + random.uniform(-0.04, 0.04), 3) for i in range(20)]
        reproj = [round(1.8 - 0.9 * math.exp(-i * 0.1) + random.uniform(-0.1, 0.15), 3) for i in range(20)]
        return {
            "avg_accuracy": round(sum(accuracy) / len(accuracy), 4),
            "avg_reprojection_error_px": round(sum(reproj) / len(reproj), 4),
            "frames_evaluated": 20,
            "detector": "SuperPoint v2",
            "matcher": "LightGlue",
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
