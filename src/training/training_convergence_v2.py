"""Training Convergence V2 Service — port 8247

Advanced convergence analysis for GR00T fine-tuning with early stopping recommendations.
"""

import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock convergence data
# ---------------------------------------------------------------------------

random.seed(42)

STEPS = list(range(0, 5001, 100))

def _smooth(base, noise, decay, step, total=5000):
    t = step / total
    return base * math.exp(-decay * t) + noise * (random.random() - 0.5)

random.seed(42)
TRAIN_LOSS = [_smooth(1.85, 0.04, 2.8, s) + 0.12 for s in STEPS]
VAL_LOSS   = [_smooth(1.85, 0.06, 2.2, s) + 0.18 for s in STEPS]
# Clamp val loss to not drop below train_loss*0.95 before overfit onset
OVERFIT_STEP = 4200
for i, s in enumerate(STEPS):
    if s > OVERFIT_STEP:
        VAL_LOSS[i] = TRAIN_LOSS[i] + 0.025 + 0.004 * ((s - OVERFIT_STEP) / 100)

def _sr_curve(plateau, onset_step, step):
    if step < onset_step:
        return 0.0
    t = (step - onset_step) / (5000 - onset_step)
    return round(min(plateau, plateau * (1 - math.exp(-4 * t)) + random.uniform(-0.01, 0.01)), 3)

random.seed(7)
EVAL_SR = [max(0.0, _sr_curve(0.72, 500, s)) for s in STEPS]

# Early stopping candidate
EARLY_STOP_STEP = 3800
EARLY_STOP_IDX  = STEPS.index(EARLY_STOP_STEP)
COMPUTE_SAVINGS_PCT = round(100 * (5000 - EARLY_STOP_STEP) / 5000, 1)  # 24%

# Convergence milestone data: steps to reach SR threshold for 4 configs
CONFIGS = ["BC_1000", "DAgger_r9", "GR00T_v2", "GR00T_v3 (proj.)"]
MILESTONES = [0.50, 0.60, 0.70, 0.75]
STEPS_TO_MILESTONE = {
    "BC_1000":        {0.50: 1800, 0.60: 2600, 0.70: 3800, 0.75: 4700},
    "DAgger_r9":      {0.50: 1400, 0.60: 2100, 0.70: 3100, 0.75: 4100},
    "GR00T_v2":       {0.50: 900,  0.60: 1500, 0.70: 2400, 0.75: 3600},
    "GR00T_v3 (proj.)": {0.50: 600, 0.60: 1000, 0.70: 1700, 0.75: 2500},
}

# Efficiency gain vs BC_1000 at SR=0.70
_bc_sr70 = STEPS_TO_MILESTONE["BC_1000"][0.70]
EFFICIENCY = {cfg: round(100 * (1 - STEPS_TO_MILESTONE[cfg][0.70] / _bc_sr70), 1) for cfg in CONFIGS}

# Key metrics
METRICS = {
    "gr00t_v2_sr70_step":       STEPS_TO_MILESTONE["GR00T_v2"][0.70],
    "bc_sr70_step":             STEPS_TO_MILESTONE["BC_1000"][0.70],
    "early_stop_step":          EARLY_STOP_STEP,
    "compute_savings_pct":      COMPUTE_SAVINGS_PCT,
    "overfit_onset_step":       OVERFIT_STEP,
    "val_loss_at_early_stop":   round(VAL_LOSS[EARLY_STOP_IDX], 4),
    "train_loss_at_early_stop": round(TRAIN_LOSS[EARLY_STOP_IDX], 4),
    "eval_sr_at_early_stop":    EVAL_SR[EARLY_STOP_IDX],
}

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _build_loss_svg() -> str:
    """Line chart: training loss, val loss, eval SR over 5000 steps."""
    W, H = 700, 300
    pad_left, pad_right = 60, 20
    pad_top, pad_bot = 30, 50
    cw = W - pad_left - pad_right
    ch = H - pad_top - pad_bot

    max_loss = 1.9
    min_loss = 0.08

    def sx(step): return pad_left + cw * step / 5000
    def sy_loss(v): return pad_top + ch * (1 - (v - min_loss) / (max_loss - min_loss))
    def sy_sr(v): return pad_top + ch * (1 - v)  # SR 0..1 mapped to chart

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">']

    # Title
    lines.append(f'<text x="{W//2}" y="18" text-anchor="middle" font-size="12" font-weight="bold" fill="#e2e8f0" font-family="monospace">Loss &amp; Eval SR over Training Steps</text>')

    # Grid lines
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = pad_top + ch * (1 - pct)
        loss_v = round(min_loss + (max_loss - min_loss) * pct, 2)
        lines.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - pad_right}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b" font-family="monospace">{loss_v}</text>')

    # X axis labels
    for s in [0, 1000, 2000, 3000, 4000, 5000]:
        x = sx(s)
        lines.append(f'<text x="{x:.1f}" y="{H - pad_bot + 15}" text-anchor="middle" font-size="9" fill="#64748b" font-family="monospace">{s}</text>')
    lines.append(f'<text x="{W//2}" y="{H - 5}" text-anchor="middle" font-size="10" fill="#64748b" font-family="monospace">Training Steps</text>')

    # Overfit shading (step 4200 onward)
    x_of = sx(OVERFIT_STEP)
    lines.append(f'<rect x="{x_of:.1f}" y="{pad_top}" width="{sx(5000) - x_of:.1f}" height="{ch}" fill="#ef4444" opacity="0.08"/>')
    lines.append(f'<text x="{(x_of + sx(5000))/2:.1f}" y="{pad_top + 14}" text-anchor="middle" font-size="9" fill="#ef4444" font-family="monospace">Overfit Risk</text>')

    # Early stop marker
    x_es = sx(EARLY_STOP_STEP)
    lines.append(f'<line x1="{x_es:.1f}" y1="{pad_top}" x2="{x_es:.1f}" y2="{H - pad_bot}" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3"/>')
    lines.append(f'<text x="{x_es + 4:.1f}" y="{pad_top + 12}" font-size="9" fill="#38bdf8" font-family="monospace">Early Stop</text>')
    lines.append(f'<text x="{x_es + 4:.1f}" y="{pad_top + 22}" font-size="9" fill="#38bdf8" font-family="monospace">step={EARLY_STOP_STEP}</text>')

    # Val loss line
    pts_val = " ".join(f"{sx(STEPS[i]):.1f},{sy_loss(VAL_LOSS[i]):.1f}" for i in range(len(STEPS)))
    lines.append(f'<polyline points="{pts_val}" fill="none" stroke="#f59e0b" stroke-width="2" opacity="0.9"/>')

    # Train loss line
    pts_train = " ".join(f"{sx(STEPS[i]):.1f},{sy_loss(TRAIN_LOSS[i]):.1f}" for i in range(len(STEPS)))
    lines.append(f'<polyline points="{pts_train}" fill="none" stroke="#22c55e" stroke-width="2" opacity="0.9"/>')

    # Eval SR line (secondary axis — occupies upper portion for visual clarity)
    pts_sr = " ".join(f"{sx(STEPS[i]):.1f},{sy_sr(EVAL_SR[i] * 0.9):.1f}" for i in range(len(STEPS)))
    lines.append(f'<polyline points="{pts_sr}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3" opacity="0.9"/>')

    # Legend
    items = [("#22c55e", "Train Loss", ""), ("#f59e0b", "Val Loss", ""), ("#C74634", "Eval SR (dashed)", "6,3")]
    lx = pad_left
    for color, label, dash in items:
        lines.append(f'<line x1="{lx}" y1="{H - pad_bot + 28}" x2="{lx + 22}" y2="{H - pad_bot + 28}" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>')
        lines.append(f'<text x="{lx + 26}" y="{H - pad_bot + 32}" font-size="10" fill="#94a3b8" font-family="monospace">{label}</text>')
        lx += len(label) * 7 + 40

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_convergence_svg() -> str:
    """Bar chart: steps to reach SR milestones for 4 configs."""
    W, H = 700, 320
    n_configs = len(CONFIGS)
    n_ms = len(MILESTONES)
    group_w = 120
    bar_w = 22
    gap_bar = 4
    pad_left = 90
    pad_top = 40
    pad_bot = 60
    max_steps = 5000
    ch = H - pad_top - pad_bot

    CONFIG_COLORS = ["#64748b", "#f59e0b", "#22c55e", "#38bdf8"]

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">']
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" font-size="12" font-weight="bold" fill="#e2e8f0" font-family="monospace">Steps to SR Milestone (lower = faster convergence)</text>')

    # Y axis grid
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = pad_top + ch * (1 - pct)
        step_v = int(max_steps * pct)
        lines.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - 20}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b" font-family="monospace">{step_v}</text>')

    for mi, ms in enumerate(MILESTONES):
        group_x = pad_left + mi * group_w + 10
        for ci, cfg in enumerate(CONFIGS):
            s2m = STEPS_TO_MILESTONE[cfg][ms]
            bar_h = int(ch * s2m / max_steps)
            x = group_x + ci * (bar_w + gap_bar)
            y = pad_top + ch - bar_h
            color = CONFIG_COLORS[ci]
            lines.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="3" fill="{color}" opacity="0.85"/>')
            lines.append(f'<text x="{x + bar_w//2}" y="{y - 3}" text-anchor="middle" font-size="8" fill="{color}" font-family="monospace">{s2m}</text>')

        # Milestone label
        gx_mid = group_x + (n_configs * (bar_w + gap_bar)) // 2
        lines.append(f'<text x="{gx_mid}" y="{H - pad_bot + 14}" text-anchor="middle" font-size="11" font-weight="bold" fill="#e2e8f0" font-family="monospace">SR={ms}</text>')

    # Legend
    lx = pad_left
    for ci, cfg in enumerate(CONFIGS):
        eff = EFFICIENCY[cfg]
        eff_str = f"+{eff}%" if eff > 0 else (f"{eff}%" if eff < 0 else "baseline")
        eff_color = "#22c55e" if eff > 0 else ("#ef4444" if eff < 0 else "#94a3b8")
        lines.append(f'<rect x="{lx}" y="{H - pad_bot + 26}" width="14" height="14" rx="3" fill="{CONFIG_COLORS[ci]}"/>')
        lines.append(f'<text x="{lx + 17}" y="{H - pad_bot + 37}" font-size="10" fill="#cbd5e1" font-family="monospace">{cfg}</text>')
        lines.append(f'<text x="{lx + 17}" y="{H - pad_bot + 49}" font-size="9" fill="{eff_color}" font-family="monospace">{eff_str} vs BC@SR=0.7</text>')
        lx += len(cfg) * 7 + 28

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_html() -> str:
    loss_svg = _build_loss_svg()
    conv_svg = _build_convergence_svg()

    milestone_rows = ""
    for cfg in CONFIGS:
        for ms in MILESTONES:
            s = STEPS_TO_MILESTONE[cfg][ms]
            milestone_rows += f"<tr><td style='color:#e2e8f0'>{cfg}</td><td style='color:#38bdf8;text-align:center'>SR={ms}</td><td style='color:#f59e0b;text-align:center'>{s:,}</td><td style='color:#22c55e;text-align:center'>{EFFICIENCY[cfg]}%</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Training Convergence V2 — OCI Robot Cloud</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',monospace,sans-serif; }}
    header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    header h1 {{ font-size:22px; font-weight:700; color:#fff; }}
    header .badge {{ background:#C74634; color:#fff; padding:3px 12px; border-radius:20px; font-size:12px; font-weight:600; }}
    .port-badge {{ background:#1e3a4f; color:#38bdf8; padding:3px 10px; border-radius:20px; font-size:12px; border:1px solid #38bdf8; }}
    .container {{ padding:28px 32px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:28px; }}
    .metric-card {{ background:#1e293b; border-radius:10px; padding:18px; border:1px solid #334155; }}
    .metric-card .label {{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px; }}
    .metric-card .value {{ font-size:28px; font-weight:700; color:#38bdf8; }}
    .metric-card .sub {{ font-size:11px; color:#94a3b8; margin-top:4px; }}
    .section {{ background:#1e293b; border-radius:10px; padding:20px; margin-bottom:24px; border:1px solid #334155; }}
    .section h2 {{ font-size:14px; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ text-align:left; font-size:11px; color:#64748b; text-transform:uppercase; padding:8px 10px; border-bottom:1px solid #334155; }}
    td {{ padding:9px 10px; border-bottom:1px solid #1e293b; font-size:13px; }}
    tr:hover td {{ background:#243044; }}
    .svg-wrap {{ overflow-x:auto; }}
    .alert-box {{ background:#1a2e44; border:1px solid #38bdf8; border-radius:8px; padding:12px 18px; margin-bottom:20px; font-size:13px; color:#bae6fd; }}
    .alert-box strong {{ color:#38bdf8; }}
    footer {{ text-align:center; padding:16px; font-size:11px; color:#475569; }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>Training Convergence V2</h1>
    <div style="margin-top:4px;font-size:12px;color:#94a3b8">GR00T Fine-Tuning — Advanced Convergence Analysis &amp; Early Stopping</div>
  </div>
  <span class="badge">LIVE</span>
  <span class="port-badge">:8247</span>
  <div style="margin-left:auto;font-size:12px;color:#475569">Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</header>
<div class="container">

  <div class="alert-box">
    <strong>Early Stop Recommendation:</strong> Stop at step {METRICS['early_stop_step']:,} — 
    Val loss {METRICS['val_loss_at_early_stop']}, Eval SR {METRICS['eval_sr_at_early_stop']}. 
    Saves <strong>{METRICS['compute_savings_pct']}% compute</strong>. 
    Overfit risk detected after step {METRICS['overfit_onset_step']:,}.
  </div>

  <div class="metrics">
    <div class="metric-card">
      <div class="label">GR00T v2 → SR=0.70</div>
      <div class="value">{METRICS['gr00t_v2_sr70_step']:,}</div>
      <div class="sub">steps (vs BC: {METRICS['bc_sr70_step']:,})</div>
    </div>
    <div class="metric-card">
      <div class="label">Early Stop Step</div>
      <div class="value" style="color:#38bdf8">{METRICS['early_stop_step']:,}</div>
      <div class="sub">saves {METRICS['compute_savings_pct']}% compute</div>
    </div>
    <div class="metric-card">
      <div class="label">Overfit Onset</div>
      <div class="value" style="color:#ef4444">{METRICS['overfit_onset_step']:,}</div>
      <div class="sub">step (train-val gap &gt;0.02)</div>
    </div>
    <div class="metric-card">
      <div class="label">Val Loss @ Early Stop</div>
      <div class="value" style="color:#22c55e">{METRICS['val_loss_at_early_stop']}</div>
      <div class="sub">SR={METRICS['eval_sr_at_early_stop']} at that checkpoint</div>
    </div>
  </div>

  <div class="section">
    <h2>Loss Landscape &amp; Eval SR (5000 steps)</h2>
    <div class="svg-wrap">{loss_svg}</div>
  </div>

  <div class="section">
    <h2>Convergence Rate Comparison — Steps to SR Milestone</h2>
    <div class="svg-wrap">{conv_svg}</div>
  </div>

  <div class="section">
    <h2>Milestone Details</h2>
    <table>
      <thead><tr>
        <th>Config</th><th style="text-align:center">Milestone</th>
        <th style="text-align:center">Steps</th>
        <th style="text-align:center">Efficiency vs BC@SR=0.7</th>
      </tr></thead>
      <tbody>{milestone_rows}</tbody>
    </table>
  </div>

</div>
<footer>OCI Robot Cloud &mdash; Training Convergence V2 &mdash; Port 8247</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Training Convergence V2",
        description="Advanced convergence analysis for GR00T fine-tuning with early stopping recommendations",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "training_convergence_v2", "port": 8247}

    @app.get("/api/metrics")
    async def metrics():
        return METRICS

    @app.get("/api/loss-curve")
    async def loss_curve():
        return {
            "steps": STEPS,
            "train_loss": [round(v, 4) for v in TRAIN_LOSS],
            "val_loss":   [round(v, 4) for v in VAL_LOSS],
            "eval_sr":    EVAL_SR,
        }

    @app.get("/api/convergence")
    async def convergence():
        return {
            "configs": CONFIGS,
            "milestones": MILESTONES,
            "steps_to_milestone": STEPS_TO_MILESTONE,
            "efficiency_vs_bc": EFFICIENCY,
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8247)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8247")
        server = HTTPServer(("0.0.0.0", 8247), _Handler)
        server.serve_forever()
