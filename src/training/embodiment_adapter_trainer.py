"""Embodiment Adapter Trainer — FastAPI port 8726"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8726

def build_html():
    # Generate training loss curve with exponential decay + noise
    epochs = 60
    loss_points = []
    val_points = []
    for i in range(epochs):
        t = i / epochs
        train_loss = 0.85 * math.exp(-3.2 * t) + 0.08 + random.gauss(0, 0.012)
        val_loss = 0.90 * math.exp(-2.9 * t) + 0.10 + random.gauss(0, 0.018)
        loss_points.append(max(0.05, train_loss))
        val_points.append(max(0.06, val_loss))

    # SVG polyline coords (600x160 canvas)
    def to_svg(pts, x0=40, y0=10, w=540, h=140):
        mn, mx = min(pts), max(pts)
        coords = []
        for i, v in enumerate(pts):
            x = x0 + (i / (len(pts) - 1)) * w
            y = y0 + h - ((v - mn) / (mx - mn + 1e-9)) * h
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)

    train_poly = to_svg(loss_points)
    val_poly = to_svg(val_points)

    # Embodiment adapter metrics
    adapters = [
        ("Franka Panda", random.uniform(0.91, 0.97), random.randint(18, 28)),
        ("UR5e",         random.uniform(0.87, 0.94), random.randint(14, 22)),
        ("xArm 7",       random.uniform(0.84, 0.92), random.randint(12, 20)),
        ("Spot Arm",     random.uniform(0.79, 0.88), random.randint(10, 18)),
        ("Kinova Gen3",  random.uniform(0.82, 0.90), random.randint(11, 19)),
    ]

    # Bar chart SVG for adapter accuracy
    bar_svg_items = []
    bar_w = 72
    for idx, (name, acc, _) in enumerate(adapters):
        x = 40 + idx * (bar_w + 16)
        bar_h = int(acc * 130)
        y = 160 - bar_h
        hue = int(200 + idx * 15)
        bar_svg_items.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="hsl({hue},70%,55%)" rx="4"/>'
            f'<text x="{x+bar_w//2}" y="{y-5}" text-anchor="middle" fill="#e2e8f0" font-size="11">{acc:.2%}</text>'
            f'<text x="{x+bar_w//2}" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">{name.split()[0]}</text>'
        )

    # Radar chart for multi-domain transfer (sin/cos offsets)
    axes = ["Pick", "Place", "Pour", "Wipe", "Stack", "Insert"]
    n = len(axes)
    scores = [random.uniform(0.72, 0.96) for _ in axes]
    cx, cy, r = 200, 170, 110
    radar_pts = []
    for i, s in enumerate(scores):
        angle = math.pi / 2 - 2 * math.pi * i / n
        radar_pts.append((cx + s * r * math.cos(angle), cy - s * r * math.sin(angle)))
    radar_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in radar_pts)
    axis_lines = []
    for i, label in enumerate(axes):
        angle = math.pi / 2 - 2 * math.pi * i / n
        ex = cx + r * math.cos(angle)
        ey = cy - r * math.sin(angle)
        lx = cx + (r + 20) * math.cos(angle)
        ly = cy - (r + 20) * math.sin(angle)
        axis_lines.append(
            f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{label}</text>'
        )

    final_train = loss_points[-1]
    final_val = val_points[-1]
    best_adapter = max(adapters, key=lambda x: x[1])

    return f"""<!DOCTYPE html><html><head><title>Embodiment Adapter Trainer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.75rem;background:#1e3a5f;color:#38bdf8;margin:2px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{text-align:left;color:#64748b;font-weight:600;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.bar-bg{{background:#0f172a;border-radius:4px;height:8px;width:100%}}
.bar-fg{{background:linear-gradient(90deg,#38bdf8,#6366f1);height:8px;border-radius:4px}}
</style></head>
<body>
<h1>Embodiment Adapter Trainer</h1>
<div class="subtitle">Port {PORT} &nbsp;·&nbsp; Cross-embodiment policy transfer &nbsp;·&nbsp; GR00T N1.6 backbone</div>

<div class="grid">
  <div class="card">
    <div class="label">Train Loss (final)</div>
    <div class="stat">{final_train:.4f}</div>
    <div style="margin-top:8px">
      <span class="badge">AdapterRank=16</span>
      <span class="badge">LR=3e-4</span>
      <span class="badge">Epochs={epochs}</span>
    </div>
  </div>
  <div class="card">
    <div class="label">Val Loss (final)</div>
    <div class="stat">{final_val:.4f}</div>
    <div style="margin-top:8px">
      <span class="badge">DropOut=0.1</span>
      <span class="badge">WarmupSteps=200</span>
    </div>
  </div>
  <div class="card">
    <div class="label">Best Embodiment</div>
    <div class="stat" style="font-size:1.2rem;padding-top:8px">{best_adapter[0]}</div>
    <div style="color:#38bdf8;font-size:1.4rem;font-weight:700">{best_adapter[1]:.2%}</div>
    <div class="label">Transfer Accuracy</div>
  </div>
  <div class="card">
    <div class="label">Adapter Params</div>
    <div class="stat">12.4M</div>
    <div style="margin-top:8px">
      <span class="badge">Frozen=98.2%</span>
      <span class="badge">Trainable=1.8%</span>
    </div>
  </div>
</div>

<div class="grid">
  <div class="card" style="grid-column:span 2">
    <h2>Training &amp; Validation Loss Curve</h2>
    <svg width="100%" viewBox="0 0 620 180" preserveAspectRatio="xMidYMid meet">
      <polyline points="{train_poly}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <polyline points="{val_poly}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="6 3"/>
      <text x="45" y="175" fill="#64748b" font-size="10">Epoch 0</text>
      <text x="555" y="175" fill="#64748b" font-size="10">Epoch {epochs}</text>
      <circle cx="500" cy="20" r="5" fill="#38bdf8"/><text x="510" y="24" fill="#e2e8f0" font-size="11">Train</text>
      <circle cx="500" cy="38" r="5" fill="#f59e0b"/><text x="510" y="42" fill="#e2e8f0" font-size="11">Val</text>
    </svg>
  </div>

  <div class="card">
    <h2>Multi-Task Radar</h2>
    <svg width="100%" viewBox="0 0 400 350" preserveAspectRatio="xMidYMid meet">
      {''.join(axis_lines)}
      <polygon points="{radar_poly}" fill="rgba(56,189,248,0.15)" stroke="#38bdf8" stroke-width="2"/>
      {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>' for x,y in radar_pts)}
    </svg>
  </div>
</div>

<div class="card">
  <h2>Adapter Performance by Embodiment</h2>
  <svg width="100%" viewBox="0 0 560 195" preserveAspectRatio="xMidYMid meet">
    {''.join(bar_svg_items)}
  </svg>
</div>

<div class="card">
  <h2>Registered Embodiments</h2>
  <table>
    <tr><th>Embodiment</th><th>Transfer Acc</th><th>Adapter Rank</th><th>Train Steps</th><th>Status</th></tr>
    {''.join(f"<tr><td>{name}</td><td style='color:#38bdf8'>{acc:.2%}</td><td>{rank}</td><td>{random.randint(4000,12000)}</td><td style='color:#4ade80'>&#10003; Ready</td></tr>" for name,acc,rank in adapters)}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Embodiment Adapter Trainer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "port": PORT,
            "service": "embodiment_adapter_trainer",
            "adapter_rank": 16,
            "trainable_params_M": 12.4,
            "frozen_pct": 98.2,
            "embodiments_registered": 5,
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
