"""Policy Behavior Cloner v2 — FastAPI port 8710"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8710

def build_html():
    random.seed(42)
    # Generate training loss curve data (exponential decay + noise)
    epochs = 120
    loss_points = []
    val_loss_points = []
    for i in range(epochs):
        t = i / epochs
        loss = 0.85 * math.exp(-4.5 * t) + 0.04 + random.uniform(-0.01, 0.01)
        val_loss = 0.90 * math.exp(-4.2 * t) + 0.055 + random.uniform(-0.015, 0.015)
        loss_points.append(max(0.01, loss))
        val_loss_points.append(max(0.015, val_loss))

    # SVG dimensions
    W, H = 560, 220
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    min_loss, max_loss = 0.0, 0.95

    def to_x(i):
        return pad_l + (i / (epochs - 1)) * chart_w

    def to_y(v):
        return pad_t + chart_h - ((v - min_loss) / (max_loss - min_loss)) * chart_h

    train_path = " ".join(
        ("M" if i == 0 else "L") + f"{to_x(i):.1f},{to_y(v):.1f}"
        for i, v in enumerate(loss_points)
    )
    val_path = " ".join(
        ("M" if i == 0 else "L") + f"{to_x(i):.1f},{to_y(v):.1f}"
        for i, v in enumerate(val_loss_points)
    )

    # Y-axis ticks
    y_ticks = [0.0, 0.2, 0.4, 0.6, 0.8]
    y_tick_svg = "".join(
        f'<line x1="{pad_l}" y1="{to_y(v):.1f}" x2="{pad_l + chart_w}" y2="{to_y(v):.1f}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{pad_l - 6}" y="{to_y(v) + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.1f}</text>'
        for v in y_ticks
    )
    # X-axis ticks
    x_ticks = [0, 20, 40, 60, 80, 100, 120]
    x_tick_svg = "".join(
        f'<text x="{to_x(min(v, epochs-1)):.1f}" y="{pad_t + chart_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{v}</text>'
        for v in x_ticks
    )

    # Action accuracy bars (joint accuracy per DOF)
    dof_names = ["J1", "J2", "J3", "J4", "J5", "J6", "gripper"]
    dof_acc = [0.94 + random.uniform(-0.04, 0.04) for _ in dof_names]
    bar_w = 44
    bar_gap = 12
    bar_svg_items = []
    for i, (name, acc) in enumerate(zip(dof_names, dof_acc)):
        bh = int(acc * 120)
        bx = 30 + i * (bar_w + bar_gap)
        by = 160 - bh
        color = "#38bdf8" if acc >= 0.92 else "#f59e0b"
        bar_svg_items.append(
            f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w//2}" y="{by - 4}" fill="#e2e8f0" font-size="10" text-anchor="middle">{acc:.2f}</text>'
            f'<text x="{bx + bar_w//2}" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">{name}</text>'
        )
    bar_svg = "".join(bar_svg_items)

    # Clone statistics
    demos_used = 1247
    train_steps = 48000
    final_loss = round(loss_points[-1], 4)
    final_val = round(val_loss_points[-1], 4)
    mean_acc = round(sum(dof_acc) / len(dof_acc), 4)
    throughput = round(2.35 + random.uniform(-0.1, 0.2), 2)

    return f"""<!DOCTYPE html><html><head><title>Policy Behavior Cloner v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;margin:0 0 20px 0;font-size:.85rem}}
h2{{color:#38bdf8;margin:0 0 12px 0;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1100px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.full{{grid-column:1/-1}}
.stat-row{{display:flex;gap:24px;flex-wrap:wrap}}
.stat{{background:#0f172a;padding:12px 20px;border-radius:6px;border-left:3px solid #C74634}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
.badge{{display:inline-block;background:#0f4c81;color:#7dd3fc;padding:2px 10px;border-radius:12px;font-size:.75rem;margin:2px}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Policy Behavior Cloner v2</h1>
<p class="subtitle">OCI Robot Cloud — Imitation Learning Pipeline | port {PORT}</p>
<div class="stat-row" style="margin-bottom:16px">
  <div class="stat"><div class="val">{demos_used:,}</div><div class="lbl">Demo Episodes</div></div>
  <div class="stat"><div class="val">{train_steps:,}</div><div class="lbl">Train Steps</div></div>
  <div class="stat"><div class="val">{final_loss}</div><div class="lbl">Final Train Loss</div></div>
  <div class="stat"><div class="val">{final_val}</div><div class="lbl">Final Val Loss</div></div>
  <div class="stat"><div class="val">{mean_acc:.1%}</div><div class="lbl">Mean Joint Acc</div></div>
  <div class="stat"><div class="val">{throughput} it/s</div><div class="lbl">Throughput</div></div>
</div>
<div class="grid">
  <div class="card full">
    <h2>Training &amp; Validation Loss (120 Epochs)</h2>
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
      {y_tick_svg}
      {x_tick_svg}
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>
      <line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>
      <path d="{train_path}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <path d="{val_path}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5,3"/>
      <circle cx="{to_x(epochs-1):.1f}" cy="{to_y(loss_points[-1]):.1f}" r="4" fill="#38bdf8"/>
      <circle cx="{to_x(epochs-1):.1f}" cy="{to_y(val_loss_points[-1]):.1f}" r="4" fill="#f59e0b"/>
      <text x="{pad_l+20}" y="{pad_t+14}" fill="#38bdf8" font-size="11">— Train Loss</text>
      <text x="{pad_l+110}" y="{pad_t+14}" fill="#f59e0b" font-size="11">- - Val Loss</text>
      <text x="{W//2}" y="{H-2}" fill="#94a3b8" font-size="11" text-anchor="middle">Epoch</text>
    </svg>
  </div>
  <div class="card">
    <h2>Per-Joint Action Accuracy</h2>
    <svg width="430" height="190">
      {bar_svg}
      <line x1="20" y1="160" x2="420" y2="160" stroke="#475569" stroke-width="1"/>
      <text x="215" y="188" fill="#94a3b8" font-size="11" text-anchor="middle">Joint / DOF</text>
    </svg>
  </div>
  <div class="card">
    <h2>Config &amp; Environment</h2>
    <div style="line-height:1.8;font-size:.88rem">
      <div><span style="color:#64748b">Model:</span> GR00T N1.6 (3B params)</div>
      <div><span style="color:#64748b">Action chunk:</span> 16 steps</div>
      <div><span style="color:#64748b">Obs horizon:</span> 2 frames</div>
      <div><span style="color:#64748b">Optimizer:</span> AdamW lr=1e-4</div>
      <div><span style="color:#64748b">Batch size:</span> 32</div>
      <div><span style="color:#64748b">GPU:</span> A100 80GB (OCI BM.GPU4.8)</div>
      <div><span style="color:#64748b">Checkpoint:</span> step_48000.pt</div>
    </div>
    <div style="margin-top:12px">
      <span class="badge">BC</span><span class="badge">GR00T</span>
      <span class="badge">LIBERO</span><span class="badge">LeRobot</span>
      <span class="badge">OCI</span>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Behavior Cloner v2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "policy_behavior_cloner_v2"}

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
