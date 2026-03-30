"""Reward Curriculum Optimizer — FastAPI port 8732"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8732

def build_html():
    random.seed(42)

    # Simulate reward shaping stages across curriculum phases
    phases = ["Phase 1: Reach", "Phase 2: Grasp", "Phase 3: Lift", "Phase 4: Place", "Phase 5: Stack"]
    phase_rewards = [round(random.uniform(0.55, 0.72), 3) for _ in phases]
    phase_entropy = [round(random.uniform(0.18, 0.45), 3) for _ in phases]
    phase_success = [round(min(1.0, 0.12 * (i + 1) + random.uniform(0.01, 0.08)), 3) for i in range(5)]

    # Reward signal over 200 training steps (sine + noise for realism)
    steps = 200
    reward_curve = [
        round(0.3 + 0.45 * (1 - math.exp(-i / 60)) + 0.05 * math.sin(i / 8) + random.gauss(0, 0.015), 4)
        for i in range(steps)
    ]

    # KL divergence decay curve
    kl_curve = [
        round(max(0.01, 1.2 * math.exp(-i / 45) + random.gauss(0, 0.02)), 4)
        for i in range(steps)
    ]

    # SVG reward curve (400x120)
    rw_min, rw_max = min(reward_curve), max(reward_curve)
    def rw_y(v): return 110 - int(90 * (v - rw_min) / (rw_max - rw_min + 1e-9))
    reward_points = " ".join(f"{int(2 * i)},{rw_y(reward_curve[i])}" for i in range(steps))

    kl_min, kl_max = min(kl_curve), max(kl_curve)
    def kl_y(v): return 110 - int(90 * (v - kl_min) / (kl_max - kl_min + 1e-9))
    kl_points = " ".join(f"{int(2 * i)},{kl_y(kl_curve[i])}" for i in range(steps))

    # Bar chart for phase success rates
    bar_w = 54
    bar_gap = 12
    bar_svg_rows = ""
    for idx, (ph, sr) in enumerate(zip(phases, phase_success)):
        x = 30 + idx * (bar_w + bar_gap)
        bh = int(sr * 160)
        by = 180 - bh
        hue = int(120 * sr)
        bar_svg_rows += (
            f'<rect x="{x}" y="{by}" width="{bar_w}" height="{bh}" fill="hsl({hue},70%,45%)" rx="3"/>'
            f'<text x="{x + bar_w//2}" y="{by - 5}" fill="#e2e8f0" font-size="11" text-anchor="middle">{sr*100:.1f}%</text>'
            f'<text x="{x + bar_w//2}" y="196" fill="#94a3b8" font-size="9" text-anchor="middle">Ph{idx+1}</text>'
        )

    phase_rows = "".join(
        f"<tr><td>{phases[i]}</td><td>{phase_rewards[i]:.3f}</td>"
        f"<td>{phase_entropy[i]:.3f}</td><td>{phase_success[i]*100:.1f}%</td></tr>"
        for i in range(5)
    )

    # Curriculum weight sliders (display only)
    reach_w = round(0.30 + random.uniform(-0.03, 0.03), 3)
    grasp_w = round(0.25 + random.uniform(-0.03, 0.03), 3)
    lift_w  = round(0.20 + random.uniform(-0.02, 0.02), 3)
    place_w = round(0.15 + random.uniform(-0.02, 0.02), 3)
    stack_w = round(1.0 - reach_w - grasp_w - lift_w - place_w, 3)

    current_step = random.randint(9800, 10200)
    current_phase = random.choice(phases)
    total_reward = round(sum(reward_curve[-20:]) / 20, 4)
    eta_hours = round(random.uniform(1.2, 3.5), 2)

    return f"""<!DOCTYPE html>
<html><head><title>Reward Curriculum Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 8px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;box-shadow:0 2px 8px #0006}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0}}
.stat{{background:#0f172a;border-radius:8px;padding:14px 18px;margin:6px}}
.stat-val{{font-size:1.8rem;font-weight:700;color:#f0abfc}}
.stat-lbl{{font-size:0.78rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
th{{background:#0f172a;color:#38bdf8;padding:8px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:7px 8px;border-bottom:1px solid #1e293b;color:#e2e8f0}}
tr:hover td{{background:#162032}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75rem;background:#0ea5e920;color:#38bdf8;border:1px solid #38bdf840}}
.progress-bar{{height:8px;background:#1e293b;border-radius:4px;overflow:hidden;margin:4px 0 8px}}
.progress-fill{{height:100%;border-radius:4px;background:linear-gradient(90deg,#C74634,#f0abfc)}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Reward Curriculum Optimizer</h1>
<p style="color:#64748b;margin:0 24px 4px;font-size:0.85rem">Adaptive multi-phase reward shaping with entropy regularization — Port {PORT}</p>

<div class="card">
  <div class="grid3">
    <div class="stat">
      <div class="stat-val">{current_step:,}</div>
      <div class="stat-lbl">Training Step</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#38bdf8">{total_reward:.4f}</div>
      <div class="stat-lbl">Avg Reward (last 20)</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#4ade80">{phase_success[-1]*100:.1f}%</div>
      <div class="stat-lbl">Stack Success Rate</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#fbbf24">{eta_hours}h</div>
      <div class="stat-lbl">ETA to Phase Promotion</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#f472b6">{phase_entropy[2]:.3f}</div>
      <div class="stat-lbl">Policy Entropy (π)</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#a78bfa">5</div>
      <div class="stat-lbl">Active Curriculum Phases</div>
    </div>
  </div>
  <div style="margin:10px 6px 0">
    <span class="badge">Current Phase: {current_phase}</span>&nbsp;
    <span class="badge">Optimizer: AdamW + CosineAnneal</span>&nbsp;
    <span class="badge">Reward Shaping: Dense+Sparse</span>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Reward Signal vs Training Steps</h2>
    <svg width="400" height="130" viewBox="0 0 400 130">
      <defs>
        <linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#C74634" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#C74634" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <rect width="400" height="130" fill="#0f172a" rx="6"/>
      <polyline points="{reward_points}" fill="none" stroke="#C74634" stroke-width="1.8"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">R={rw_max:.3f}</text>
      <text x="4" y="118" fill="#94a3b8" font-size="9">R={rw_min:.3f}</text>
      <text x="180" y="125" fill="#64748b" font-size="9">steps (×{steps//200}00)</text>
    </svg>
  </div>

  <div class="card">
    <h2>KL Divergence Decay</h2>
    <svg width="400" height="130" viewBox="0 0 400 130">
      <rect width="400" height="130" fill="#0f172a" rx="6"/>
      <polyline points="{kl_points}" fill="none" stroke="#38bdf8" stroke-width="1.8"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">KL={kl_max:.3f}</text>
      <text x="4" y="118" fill="#94a3b8" font-size="9">KL={kl_min:.3f}</text>
      <text x="160" y="125" fill="#64748b" font-size="9">steps →  policy convergence</text>
    </svg>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Phase Success Rates</h2>
    <svg width="380" height="210" viewBox="0 0 380 210">
      <rect width="380" height="210" fill="#0f172a" rx="6"/>
      {bar_svg_rows}
      <line x1="20" y1="180" x2="360" y2="180" stroke="#334155" stroke-width="1"/>
    </svg>
  </div>

  <div class="card">
    <h2>Curriculum Phase Metrics</h2>
    <table>
      <tr><th>Phase</th><th>Avg Reward</th><th>Entropy</th><th>Success</th></tr>
      {phase_rows}
    </table>
  </div>
</div>

<div class="card">
  <h2>Reward Component Weights</h2>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px">
    {''.join(f'<div><div style="font-size:0.8rem;color:#94a3b8;margin-bottom:4px">{ph.split(":")[1].strip()}</div><div class="progress-bar"><div class="progress-fill" style="width:{int(w*100)}%;background:hsl({80+idx*30},60%,50%)"></div></div><div style="font-size:0.85rem;color:#e2e8f0">{w:.3f}</div></div>' for idx,(ph,w) in enumerate(zip(phases,[reach_w,grasp_w,lift_w,place_w,stack_w])) )}
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Curriculum Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "reward_curriculum_optimizer"}

    @app.get("/metrics")
    def metrics():
        random.seed()
        return {
            "current_step": random.randint(9800, 10200),
            "avg_reward_last20": round(random.uniform(0.68, 0.74), 4),
            "policy_entropy": round(random.uniform(0.18, 0.30), 4),
            "kl_divergence": round(random.uniform(0.05, 0.12), 4),
            "phase_success_rates": [round(0.12 * (i + 1) + random.uniform(0.01, 0.05), 3) for i in range(5)],
            "active_phase": random.randint(3, 5),
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
