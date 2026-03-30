"""Diffusion Policy Evaluator — FastAPI port 8766"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8766

def build_html():
    # Generate denoising trajectory data using sinusoidal + noise simulation
    random.seed(42)
    steps = 20
    # Simulated loss curve: exponential decay with noise
    loss_vals = [round(2.5 * math.exp(-0.18 * i) + random.uniform(-0.04, 0.04), 4) for i in range(steps)]
    # Simulated action MSE over eval episodes
    mse_vals = [round(0.08 + 0.04 * math.cos(i * 0.5) + random.uniform(0, 0.02), 4) for i in range(steps)]
    # Success rate per checkpoint (0-1)
    success_vals = [round(min(1.0, 0.1 + 0.85 * (1 - math.exp(-0.22 * i)) + random.uniform(-0.03, 0.03)), 3) for i in range(steps)]

    # SVG loss curve (400x120)
    w, h = 400, 120
    pad = 15
    max_loss = max(loss_vals)
    def lx(i): return pad + i * (w - 2*pad) / (steps - 1)
    def ly(v): return h - pad - (v / max_loss) * (h - 2*pad)
    loss_poly = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(loss_vals))
    mse_poly = " ".join(f"{lx(i):.1f},{ly(v*max_loss/max(mse_vals)):.1f}" for i, v in enumerate(mse_vals))

    # SVG success bar chart (400x120)
    bar_w = (w - 2*pad) / steps - 2
    bars_svg = "".join(
        f'<rect x="{pad + i*(bar_w+2):.1f}" y="{h - pad - success_vals[i]*(h-2*pad):.1f}" '
        f'width="{bar_w:.1f}" height="{success_vals[i]*(h-2*pad):.1f}" fill="#22d3ee" opacity="0.8"/>'
        for i in range(steps)
    )

    # Diffusion trajectory scatter (200x200) — 2D action space projection
    random.seed(7)
    traj_pts = [(round(math.cos(t)*80 + random.gauss(0, 12) + 100, 1),
                 round(math.sin(t)*60 + random.gauss(0, 10) + 100, 1))
                for t in [i * 2 * math.pi / 30 for i in range(30)]]
    traj_circles = "".join(
        f'<circle cx="{x}" cy="{y}" r="4" fill="#a78bfa" opacity="{0.4 + 0.6*i/30:.2f}"/>'
        for i, (x, y) in enumerate(traj_pts)
    )
    traj_line = "M " + " L ".join(f"{x},{y}" for x, y in traj_pts)

    # Noise schedule heatmap row (20 cells)
    noise_row = "".join(
        f'<rect x="{pad + i*18}" y="10" width="16" height="30" '
        f'fill="hsl({int(240 - 200*(i/steps))},80%,55%)" rx="2"/>'
        for i in range(steps)
    )

    best_ckpt = success_vals.index(max(success_vals))
    avg_mse = round(sum(mse_vals) / len(mse_vals), 4)
    final_sr = success_vals[-1]

    return f"""<!DOCTYPE html><html><head><title>Diffusion Policy Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:0 0 10px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:1100px}}
.card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
.stat{{font-size:2rem;font-weight:700;color:#22d3ee}}.label{{font-size:0.75rem;color:#94a3b8;margin-top:2px}}
.row{{display:flex;gap:14px}}.badge{{background:#0f172a;border:1px solid #38bdf8;padding:3px 10px;border-radius:20px;font-size:0.78rem;color:#38bdf8}}
.mono{{font-family:monospace;font-size:0.82rem;color:#a5f3fc}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 10px;text-align:left;font-size:0.83rem}}
th{{color:#94a3b8;border-bottom:1px solid #334155}}tr:nth-child(even){{background:#0f172a80}}
</style></head>
<body>
<h1>Diffusion Policy Evaluator</h1>
<p style="color:#94a3b8;margin:0 0 16px">OCI Robot Cloud — Closed-Loop Evaluation Dashboard &nbsp;
<span class="badge">port {PORT}</span>
<span class="badge" style="border-color:#22d3ee;color:#22d3ee">GR00T N1.6</span>
<span class="badge" style="border-color:#a78bfa;color:#a78bfa">DDPM T=100</span>
</p>

<div class="row" style="margin-bottom:14px">
  <div class="card" style="flex:1">
    <div class="label">Best Checkpoint</div><div class="stat">ckpt-{best_ckpt:02d}</div>
    <div class="label">success rate {max(success_vals):.1%}</div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Final Success Rate</div><div class="stat">{final_sr:.1%}</div>
    <div class="label">last eval epoch</div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Avg Action MSE</div><div class="stat">{avg_mse}</div>
    <div class="label">across {steps} checkpoints</div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Diffusion Steps</div><div class="stat">100</div>
    <div class="label">DDPM scheduler</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Denoising Loss Curve (Training)</h2>
    <svg width="{w}" height="{h}" style="overflow:visible">
      <polyline points="{loss_poly}" fill="none" stroke="#f97316" stroke-width="2"/>
      <polyline points="{mse_poly}" fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-dasharray="4 2"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155"/>
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155"/>
      <text x="{pad+2}" y="{pad+8}" font-size="9" fill="#94a3b8">loss</text>
    </svg>
    <div style="margin-top:6px;font-size:0.75rem;color:#94a3b8">
      <span style="color:#f97316">— Denoising Loss</span> &nbsp;
      <span style="color:#22d3ee">-- Action MSE (normalized)</span>
    </div>
  </div>

  <div class="card">
    <h2>Success Rate per Checkpoint</h2>
    <svg width="{w}" height="{h}">
      {bars_svg}
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155"/>
      <text x="{pad}" y="{pad+6}" font-size="9" fill="#94a3b8">1.0</text>
      <text x="{pad}" y="{h//2}" font-size="9" fill="#94a3b8">0.5</text>
    </svg>
  </div>

  <div class="card">
    <h2>Action Trajectory Projection (2D)</h2>
    <svg width="200" height="200">
      <path d="{traj_line}" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.5"/>
      {traj_circles}
      <text x="4" y="14" font-size="9" fill="#94a3b8">action dim 0</text>
      <text x="4" y="196" font-size="9" fill="#94a3b8">dim 1</text>
    </svg>
  </div>

  <div class="card">
    <h2>Noise Schedule (β₁…β_T)</h2>
    <svg width="400" height="50">
      {noise_row}
    </svg>
    <div style="font-size:0.75rem;color:#94a3b8;margin-top:6px">Linear schedule β: 1e-4 → 0.02, T=100 steps</div>
    <h2 style="margin-top:14px">Checkpoint Summary</h2>
    <table>
      <tr><th>Ckpt</th><th>Loss</th><th>MSE</th><th>SR</th></tr>
      {''.join(f'<tr><td class="mono">ckpt-{i:02d}</td><td class="mono">{loss_vals[i]}</td><td class="mono">{mse_vals[i]}</td><td class="mono" style="color:{"#22d3ee" if success_vals[i]==max(success_vals) else "#e2e8f0"}">{success_vals[i]:.3f}</td></tr>' for i in [0,4,9,14,19])}
    </table>
  </div>
</div>

<div class="card" style="margin-top:14px;max-width:1100px">
  <h2>Live Eval Log</h2>
  <div class="mono" style="line-height:1.8">
    [2026-03-30 14:01:02] Loading checkpoint ckpt-{best_ckpt:02d} from /mnt/models/groot_n16_finetune/<br>
    [2026-03-30 14:01:05] Env: LIBERO-Spatial, task=pick_and_place_cube, episodes=20<br>
    [2026-03-30 14:01:06] Diffusion steps=100, action_horizon=16, obs_horizon=2<br>
    [2026-03-30 14:02:44] Episode 20/20 complete — success=14/20 (70.0%) avg_steps=87<br>
    [2026-03-30 14:02:44] Action MSE={avg_mse} | Inference latency=231ms (A100)<br>
    [2026-03-30 14:02:44] Best checkpoint: ckpt-{best_ckpt:02d} SR={max(success_vals):.1%} — saved to registry
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Diffusion Policy Evaluator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "diffusion_policy_evaluator"}

    @app.get("/metrics")
    def metrics():
        random.seed(42)
        steps = 20
        success_vals = [round(min(1.0, 0.1 + 0.85*(1-math.exp(-0.22*i))+random.uniform(-0.03,0.03)),3) for i in range(steps)]
        best = success_vals.index(max(success_vals))
        return {
            "best_checkpoint": f"ckpt-{best:02d}",
            "best_success_rate": max(success_vals),
            "final_success_rate": success_vals[-1],
            "avg_mse": round(sum([0.08+0.04*math.cos(i*0.5)+random.uniform(0,0.02) for i in range(steps)])/steps, 4),
            "diffusion_steps": 100,
            "inference_latency_ms": 231,
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
