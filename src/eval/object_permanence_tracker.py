"""Object Permanence Tracker — FastAPI port 8794"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8794

def build_html():
    random.seed(42)
    # Simulate object permanence tracking over 60 time steps
    steps = 60
    # Object position (x,y) over time — sinusoidal with occlusion windows
    positions = []
    for i in range(steps):
        x = 200 + 120 * math.cos(i * 2 * math.pi / steps)
        y = 180 + 80 * math.sin(i * 2 * math.pi / steps)
        positions.append((x, y))

    # Occlusion windows: frames 15-25 and 40-48
    occlusion_ranges = [(15, 25), (40, 48)]
    def is_occluded(i):
        for s, e in occlusion_ranges:
            if s <= i <= e:
                return True
        return False

    # Predicted positions during occlusion (Kalman-like linear extrapolation)
    predicted = {}
    for s, e in occlusion_ranges:
        vx = positions[s][0] - positions[s-1][0]
        vy = positions[s][1] - positions[s-1][1]
        for j in range(s, e+1):
            dt = j - s
            px = positions[s-1][0] + vx * (dt+1) + random.gauss(0, 2)
            py = positions[s-1][1] + vy * (dt+1) + random.gauss(0, 2)
            predicted[j] = (px, py)

    # Build SVG path for true trajectory
    true_path = " ".join(
        f"{'M' if i==0 else 'L'}{p[0]:.1f},{p[1]:.1f}"
        for i, p in enumerate(positions) if not is_occluded(i)
    )
    pred_path = " ".join(
        f"{'M' if k==list(predicted.keys())[0] else 'L'}{v[0]:.1f},{v[1]:.1f}"
        for k, v in predicted.items()
    )

    # Confidence score over time (drops during occlusion, recovers after)
    conf_scores = []
    for i in range(steps):
        if is_occluded(i):
            # confidence decays linearly
            for s, e in occlusion_ranges:
                if s <= i <= e:
                    base = 0.95 - 0.04 * (i - s)
                    conf_scores.append(max(0.5, base + random.gauss(0, 0.02)))
                    break
        else:
            conf_scores.append(min(1.0, 0.92 + 0.05 * math.sin(i * 0.3) + random.gauss(0, 0.01)))

    # Bar chart for confidence — 60 bars across 540px
    bar_width = 540 / steps
    conf_bars = ""
    for i, c in enumerate(conf_scores):
        color = "#ef4444" if c < 0.7 else ("#f59e0b" if c < 0.85 else "#22c55e")
        h = c * 80
        conf_bars += f'<rect x="{30 + i*bar_width:.1f}" y="{100 - h:.1f}" width="{bar_width*0.8:.1f}" height="{h:.1f}" fill="{color}" opacity="0.85"/>'

    # Occlusion shading on confidence chart
    occ_shades = ""
    for s, e in occlusion_ranges:
        ox = 30 + s * bar_width
        ow = (e - s + 1) * bar_width
        occ_shades += f'<rect x="{ox:.1f}" y="10" width="{ow:.1f}" height="90" fill="#7c3aed" opacity="0.18"/>'

    # Summary metrics
    avg_conf = sum(conf_scores) / len(conf_scores)
    occ_frames = sum(1 for i in range(steps) if is_occluded(i))
    recovery_frames = 2  # frames to recover full confidence post-occlusion
    re_id_success = 2  # both occlusion windows successfully re-identified

    # IoU over time (simulated — drops during occlusion)
    iou_vals = []
    for i in range(steps):
        if is_occluded(i):
            iou_vals.append(0.0)
        else:
            iou_vals.append(0.78 + 0.15 * math.sin(i * 0.2) + random.gauss(0, 0.02))
    avg_iou = sum(v for v in iou_vals if v > 0) / sum(1 for v in iou_vals if v > 0)

    # IoU line chart
    iou_pts = " ".join(
        f"{30 + i * bar_width + bar_width/2:.1f},{110 - iou_vals[i]*80:.1f}"
        for i in range(steps)
    )

    return f"""<!DOCTYPE html><html><head><title>Object Permanence Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.9rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
.full{{grid-column:1/-1}}
.metric{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #334155}}
.metric:last-child{{border-bottom:none}}
.val{{font-size:1.4rem;font-weight:700;color:#38bdf8}}
.label{{color:#94a3b8;font-size:0.85rem}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600}}
.tag-green{{background:#14532d;color:#86efac}}
.tag-yellow{{background:#451a03;color:#fcd34d}}
.tag-red{{background:#450a0a;color:#fca5a5}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Object Permanence Tracker</h1>
<div class="subtitle">Port {PORT} · Real-time occlusion handling &amp; re-identification for robot manipulation</div>
<div class="grid">
  <div class="card full">
    <h2>3D Object Trajectory (Top-Down View) — True vs Predicted Under Occlusion</h2>
    <svg width="100%" viewBox="0 0 600 360" style="background:#0f172a;border-radius:6px">
      <!-- Grid -->
      {''.join(f'<line x1="{x}" y1="30" x2="{x}" y2="330" stroke="#1e293b" stroke-width="1"/>' for x in range(30, 580, 40))}
      {''.join(f'<line x1="30" y1="{y}" x2="570" y2="{y}" stroke="#1e293b" stroke-width="1"/>' for y in range(30, 340, 40))}
      <!-- Occlusion zones -->
      <rect x="{30 + 15 * (600/steps):.1f}" y="30" width="{11 * (600/steps):.1f}" height="300" fill="#7c3aed" opacity="0.12" rx="3"/>
      <rect x="{30 + 40 * (600/steps):.1f}" y="30" width="{9 * (600/steps):.1f}" height="300" fill="#7c3aed" opacity="0.12" rx="3"/>
      <text x="{30 + 19 * (600/steps):.1f}" y="25" fill="#a78bfa" font-size="10" text-anchor="middle">Occlusion 1</text>
      <text x="{30 + 43 * (600/steps):.1f}" y="25" fill="#a78bfa" font-size="10" text-anchor="middle">Occlusion 2</text>
      <!-- True trajectory -->
      <path d="{true_path}" stroke="#38bdf8" stroke-width="2" fill="none" stroke-dasharray="none"/>
      <!-- Predicted trajectory -->
      <path d="{pred_path}" stroke="#f59e0b" stroke-width="2" fill="none" stroke-dasharray="6,3"/>
      <!-- Object markers -->
      {''.join(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="{"#7c3aed" if is_occluded(i) else "#38bdf8"}" opacity="0.7"/>' for i, p in enumerate(positions))}
      <!-- Current position highlight -->
      <circle cx="{positions[-1][0]:.1f}" cy="{positions[-1][1]:.1f}" r="7" fill="none" stroke="#22c55e" stroke-width="2"/>
      <circle cx="{positions[-1][0]:.1f}" cy="{positions[-1][1]:.1f}" r="3" fill="#22c55e"/>
      <!-- Legend -->
      <rect x="420" y="310" width="160" height="42" fill="#1e293b" rx="4" opacity="0.9"/>
      <line x1="428" y1="322" x2="448" y2="322" stroke="#38bdf8" stroke-width="2"/>
      <text x="452" y="326" fill="#e2e8f0" font-size="11">True trajectory</text>
      <line x1="428" y1="340" x2="448" y2="340" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5,2"/>
      <text x="452" y="344" fill="#e2e8f0" font-size="11">Predicted (occluded)</text>
    </svg>
  </div>

  <div class="card full">
    <h2>Tracker Confidence Score Over Time</h2>
    <svg width="100%" viewBox="0 0 600 130" style="background:#0f172a;border-radius:6px">
      {occ_shades}
      {conf_bars}
      <!-- IoU line overlay -->
      <polyline points="{iou_pts}" stroke="#38bdf8" stroke-width="1.5" fill="none" opacity="0.7"/>
      <!-- Axes -->
      <line x1="30" y1="10" x2="30" y2="105" stroke="#475569" stroke-width="1"/>
      <line x1="30" y1="105" x2="570" y2="105" stroke="#475569" stroke-width="1"/>
      <text x="8" y="14" fill="#94a3b8" font-size="9">1.0</text>
      <text x="8" y="54" fill="#94a3b8" font-size="9">0.5</text>
      <text x="8" y="106" fill="#94a3b8" font-size="9">0.0</text>
      <text x="300" y="125" fill="#94a3b8" font-size="10" text-anchor="middle">Frame</text>
      <text x="16" y="60" fill="#94a3b8" font-size="10" transform="rotate(-90,16,60)">Conf</text>
      <!-- Labels -->
      <text x="30" y="120" fill="#94a3b8" font-size="9">0</text>
      <text x="300" y="120" fill="#94a3b8" font-size="9">30</text>
      <text x="565" y="120" fill="#94a3b8" font-size="9">60</text>
    </svg>
  </div>

  <div class="card">
    <h2>Tracking Metrics</h2>
    <div class="metric"><span class="label">Avg Confidence</span><span class="val">{avg_conf:.3f}</span></div>
    <div class="metric"><span class="label">Avg IoU (visible)</span><span class="val">{avg_iou:.3f}</span></div>
    <div class="metric"><span class="label">Total Frames</span><span class="val">{steps}</span></div>
    <div class="metric"><span class="label">Occluded Frames</span><span class="val">{occ_frames}</span></div>
    <div class="metric"><span class="label">Occlusion Events</span><span class="val">{len(occlusion_ranges)}</span></div>
    <div class="metric"><span class="label">Re-ID Success</span><span class="val">{re_id_success}/{len(occlusion_ranges)}</span></div>
    <div class="metric"><span class="label">Recovery Latency</span><span class="val">{recovery_frames} frames</span></div>
  </div>

  <div class="card">
    <h2>Object State</h2>
    <div class="metric"><span class="label">Tracker ID</span><span class="val">OBJ-007</span></div>
    <div class="metric"><span class="label">Class</span><span class="val">Cube (Red)</span></div>
    <div class="metric"><span class="label">Status</span><span class="tag tag-green">VISIBLE</span></div>
    <div class="metric"><span class="label">Pose Estimator</span><span class="val">FoundationPose</span></div>
    <div class="metric"><span class="label">Depth Source</span><span class="val">Realsense D435</span></div>
    <div class="metric"><span class="label">Prediction Model</span><span class="val">Kalman + GRU</span></div>
    <div class="metric"><span class="label">Last Seen</span><span class="val">Frame 59</span></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Object Permanence Tracker")
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
