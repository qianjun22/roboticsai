#!/usr/bin/env python3
"""
GR00T Fine-tune v3 Training Progress Dashboard
Port 8306 — tracks the next staging model after v2
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ── Mock training data ──────────────────────────────────────────────────────

TOTAL_STEPS = 3000
CURRENT_STEP = 800
CURRENT_LOSS = 0.121

# Loss at step 800 for v1 and v2
V1_LOSS_800  = 0.158
V2_LOSS_800  = 0.134
V3_LOSS_800  = 0.121

V1_FINAL_LOSS = 0.141
V2_FINAL_LOSS = 0.103
V3_PROJ_LOSS  = 0.089   # projected at step 3000

V1_SR   = 0.67
V2_SR   = 0.76
V3_PROJ_SR_LOW  = 0.83
V3_PROJ_SR_HIGH = 0.86

V1_COST  = 12.40
V2_COST  = 18.70
V3_COST  = 22.10   # projected

V1_LATENCY = 241
V2_LATENCY = 227
V3_LATENCY = 219   # projected

V1_MAE = 0.148
V2_MAE = 0.103
V3_MAE = 0.079   # projected

V1_STEPS = 2000
V2_STEPS = 2500
V3_STEPS = 3000

ETA_DATE = "April 21, 2026"
NEW_DATA_SOURCES = ["real_robot_pi demos (82 eps)", "improved domain randomization", "extended workspace range"]

# Generate a plausible loss curve for v3 (steps 0..800)
random.seed(42)

def _v3_loss_at_step(s: int) -> float:
    """Exponential decay + small noise."""
    base = 0.38 * math.exp(-s / 950) + 0.089
    noise = random.gauss(0, 0.003)
    return round(max(0.08, base + noise), 4)

def _v2_loss_at_step(s: int) -> float:
    base = 0.41 * math.exp(-s / 900) + 0.100
    noise = random.gauss(0, 0.003)
    return round(max(0.095, base + noise), 4)

LOSS_STEPS = list(range(0, CURRENT_STEP + 1, 50))
V3_LOSS_CURVE = [_v3_loss_at_step(s) for s in LOSS_STEPS]
V2_LOSS_CURVE = [_v2_loss_at_step(s) for s in LOSS_STEPS]

# ── SVG helpers ─────────────────────────────────────────────────────────────

def svg_loss_curve() -> str:
    """SVG 1: Training progress — step counter, loss curve, v2 comparison."""
    W, H = 820, 400
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 40, 60

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    # x maps step → px
    def xp(step):
        return PAD_L + (step / TOTAL_STEPS) * plot_w

    # y maps loss → px  (loss range 0.08 .. 0.42)
    LOSS_MIN, LOSS_MAX = 0.075, 0.42
    def yp(loss):
        frac = (loss - LOSS_MIN) / (LOSS_MAX - LOSS_MIN)
        return PAD_T + plot_h - frac * plot_h

    def polyline(steps, losses, color, dash=""):
        pts = " ".join(f"{xp(s):.1f},{yp(l):.1f}" for s, l in zip(steps, losses))
        da = f'stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" {da}/>'

    # projected tail (step 800 → 3000) using exponential curve
    proj_steps = list(range(CURRENT_STEP, TOTAL_STEPS + 1, 50))
    proj_losses = [_v3_loss_at_step(s) for s in proj_steps]

    # Grid lines
    grid = ""
    for loss_tick in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        y = yp(loss_tick)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        grid += f'<text x="{PAD_L-8}" y="{y+4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{loss_tick:.2f}</text>'

    for step_tick in range(0, TOTAL_STEPS + 1, 500):
        x = xp(step_tick)
        grid += f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T+plot_h}" stroke="#1e3a5f" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{PAD_T+plot_h+18}" fill="#94a3b8" font-size="11" text-anchor="middle">{step_tick}</text>'

    # Current step vertical marker
    cx = xp(CURRENT_STEP)
    marker = f'<line x1="{cx:.1f}" y1="{PAD_T}" x2="{cx:.1f}" y2="{PAD_T+plot_h}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="6,3"/>'
    marker += f'<text x="{cx+4:.1f}" y="{PAD_T+14}" fill="#f59e0b" font-size="11">step {CURRENT_STEP}</text>'

    # Projected endpoint dot
    px_end = xp(TOTAL_STEPS)
    py_end = yp(V3_PROJ_LOSS)
    proj_dot = f'<circle cx="{px_end:.1f}" cy="{py_end:.1f}" r="5" fill="#38bdf8" stroke="#0f172a" stroke-width="2"/>'
    proj_dot += f'<text x="{px_end-4:.1f}" y="{py_end-10:.1f}" fill="#38bdf8" font-size="11" text-anchor="end">proj {V3_PROJ_LOSS}</text>'

    svg = f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="22" fill="#f1f5f9" font-size="15" font-weight="bold" text-anchor="middle">GR00T v3 Training — Loss Curve (step {CURRENT_STEP}/{TOTAL_STEPS})</text>
  {grid}
  {polyline(LOSS_STEPS, V2_LOSS_CURVE, "#94a3b8", "8,4")}
  {polyline(LOSS_STEPS, V3_LOSS_CURVE, "#C74634")}
  {polyline(proj_steps, proj_losses, "#38bdf8", "6,3")}
  {marker}
  {proj_dot}
  <!-- Legend -->
  <rect x="{PAD_L}" y="{H-22}" width="14" height="4" fill="#94a3b8"/>
  <text x="{PAD_L+18}" y="{H-16}" fill="#94a3b8" font-size="11">v2 baseline</text>
  <rect x="{PAD_L+110}" y="{H-22}" width="14" height="4" fill="#C74634"/>
  <text x="{PAD_L+128}" y="{H-16}" fill="#C74634" font-size="11">v3 actual</text>
  <rect x="{PAD_L+210}" y="{H-22}" width="14" height="4" fill="#38bdf8"/>
  <text x="{PAD_L+228}" y="{H-16}" fill="#38bdf8" font-size="11">v3 projected</text>
  <!-- Y axis label -->
  <text x="14" y="{PAD_T + plot_h//2}" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,14,{PAD_T + plot_h//2})">Loss</text>
  <text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="12" text-anchor="middle">Training Steps</text>
</svg>"""
    return svg


def svg_version_comparison() -> str:
    """SVG 2: v1 vs v2 vs v3 bar comparison across 5 metrics."""
    W, H = 820, 400
    PAD_L, PAD_R, PAD_T, PAD_B = 90, 30, 50, 50

    metrics = [
        ("Training Steps", [V1_STEPS, V2_STEPS, V3_STEPS], 3200, False),
        ("Success Rate", [V1_SR, V2_SR, V3_PROJ_SR_LOW], 1.0, False),
        ("Cost ($)",      [V1_COST, V2_COST, V3_COST],    25.0, False),
        ("Latency (ms)",  [V1_LATENCY, V2_LATENCY, V3_LATENCY], 260, True),  # lower better
        ("MAE",           [V1_MAE, V2_MAE, V3_MAE],       0.17, True),       # lower better
    ]
    N_METRICS = len(metrics)
    VERSIONS = ["v1", "v2", "v3 (proj)"]
    COLORS   = ["#64748b", "#C74634", "#38bdf8"]

    group_w = (W - PAD_L - PAD_R) / N_METRICS
    bar_gap  = 4
    bar_w    = (group_w - 4 * bar_gap) / 3

    plot_h = H - PAD_T - PAD_B

    bars = ""
    labels = ""
    for mi, (name, vals, max_val, lower_better) in enumerate(metrics):
        gx = PAD_L + mi * group_w
        # group label
        labels += f'<text x="{gx + group_w/2:.1f}" y="{H - 10}" fill="#94a3b8" font-size="11" text-anchor="middle">{name}</text>'
        if lower_better:
            labels += f'<text x="{gx + group_w/2:.1f}" y="{H - 0}" fill="#64748b" font-size="9" text-anchor="middle">↓ better</text>'
        for vi, (val, color) in enumerate(zip(vals, COLORS)):
            bx = gx + bar_gap + vi * (bar_w + bar_gap)
            frac = val / max_val
            bh   = frac * plot_h * 0.85
            by   = PAD_T + plot_h - bh
            bars  += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="3"/>'
            # value label on top
            label = str(val) if isinstance(val, int) else f"{val:.3f}" if val < 1 else f"{val:.1f}"
            bars  += f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="{color}" font-size="10" text-anchor="middle">{label}</text>'

    # Legend
    legend = ""
    for vi, (ver, color) in enumerate(zip(VERSIONS, COLORS)):
        lx = PAD_L + vi * 140
        legend += f'<rect x="{lx}" y="18" width="14" height="10" fill="{color}" rx="2"/>'
        legend += f'<text x="{lx+18}" y="27" fill="{color}" font-size="12">{ver}</text>'

    svg = f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="14" fill="#f1f5f9" font-size="15" font-weight="bold" text-anchor="middle">GR00T v1 / v2 / v3 — Version Comparison</text>
  {legend}
  <!-- Grid -->
  {''.join(f'<line x1="{PAD_L}" y1="{PAD_T + plot_h - i*plot_h*0.85/4:.1f}" x2="{W-PAD_R}" y2="{PAD_T + plot_h - i*plot_h*0.85/4:.1f}" stroke="#1e3a5f" stroke-width="1"/>' for i in range(5))}
  {bars}
  {labels}
</svg>"""
    return svg


# ── HTML page ────────────────────────────────────────────────────────────────

def build_html() -> str:
    progress_pct = round(CURRENT_STEP / TOTAL_STEPS * 100, 1)
    loss_delta   = round(V2_LOSS_800 - V3_LOSS_800, 4)
    steps_left   = TOTAL_STEPS - CURRENT_STEP

    bullets = "".join(f"<li>{src}</li>" for src in NEW_DATA_SOURCES)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>GR00T v3 Training Progress</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px; border-left: 4px solid #C74634; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .lbl {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
    .progress-bar {{ background: #1e293b; border-radius: 6px; height: 22px; margin: 8px 0 24px; overflow: hidden; }}
    .progress-fill {{ height: 100%; background: linear-gradient(90deg,#C74634,#38bdf8); border-radius: 6px;
                      width: {progress_pct}%; transition: width 1s; display: flex; align-items: center;
                      padding-left: 8px; font-size: 0.8rem; font-weight: 700; color: #0f172a; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .section h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 14px; }}
    svg {{ max-width: 100%; display: block; margin: 0 auto; }}
    .tag {{ display: inline-block; background: #0f3460; color: #38bdf8; border-radius: 999px;
             padding: 2px 10px; font-size: 0.78rem; margin: 3px 3px 3px 0; }}
    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .info-box {{ background: #0f172a; border-radius: 8px; padding: 14px; }}
    .info-box h3 {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; }}
    ul {{ padding-left: 16px; color: #cbd5e1; font-size: 0.9rem; line-height: 1.7; }}
    .green {{ color: #4ade80; }}
    .amber {{ color: #fbbf24; }}
    .footer {{ text-align: center; color: #475569; font-size: 0.8rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>GR00T v3 Fine-tune Training Progress</h1>
  <p class="subtitle">Next staging model after v2 &mdash; target SR 0.83&ndash;0.86 &bull; ETA {ETA_DATE}</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="val">{CURRENT_STEP:,}/{TOTAL_STEPS:,}</div><div class="lbl">Training Steps ({progress_pct}%)</div></div>
    <div class="kpi"><div class="val">{CURRENT_LOSS}</div><div class="lbl">Current Loss <span class="green">(−{loss_delta:.4f} vs v2)</span></div></div>
    <div class="kpi"><div class="val">{V3_PROJ_SR_LOW}–{V3_PROJ_SR_HIGH}</div><div class="lbl">Projected Success Rate</div></div>
    <div class="kpi"><div class="val">{steps_left:,}</div><div class="lbl">Steps Remaining</div></div>
  </div>

  <div class="progress-bar"><div class="progress-fill">{progress_pct}%</div></div>

  <div class="section">
    <h2>Training Loss Curve — v3 vs v2 Baseline</h2>
    {svg_loss_curve()}
  </div>

  <div class="section">
    <h2>Version Comparison — v1 / v2 / v3</h2>
    {svg_version_comparison()}
  </div>

  <div class="section">
    <div class="info-grid">
      <div class="info-box">
        <h3>New Training Data Sources</h3>
        <ul>{bullets}</ul>
      </div>
      <div class="info-box">
        <h3>v3 vs v2 at Step 800</h3>
        <ul>
          <li>v2 loss @ 800: <span class="amber">{V2_LOSS_800}</span></li>
          <li>v3 loss @ 800: <span class="green">{V3_LOSS_800}</span></li>
          <li>Improvement: <span class="green">−{loss_delta:.4f} ({round(loss_delta/V2_LOSS_800*100,1)}%)</span></li>
          <li>Projected final loss: <span class="green">{V3_PROJ_LOSS}</span></li>
          <li>Projected MAE: <span class="green">{V3_MAE}</span> (v2: {V2_MAE})</li>
          <li>Expected latency: <span class="green">{V3_LATENCY} ms</span> (v2: {V2_LATENCY} ms)</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="footer">OCI Robot Cloud &bull; GR00T v3 Dashboard &bull; Port 8306 &bull; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
</body>
</html>
"""


# ── App ──────────────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="GR00T v3 Training Progress", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/status")
    async def status():
        return {
            "current_step": CURRENT_STEP,
            "total_steps": TOTAL_STEPS,
            "progress_pct": round(CURRENT_STEP / TOTAL_STEPS * 100, 1),
            "current_loss": CURRENT_LOSS,
            "v2_loss_at_800": V2_LOSS_800,
            "loss_improvement_vs_v2": round(V2_LOSS_800 - V3_LOSS_800, 4),
            "projected_loss": V3_PROJ_LOSS,
            "projected_sr_low": V3_PROJ_SR_LOW,
            "projected_sr_high": V3_PROJ_SR_HIGH,
            "projected_mae": V3_MAE,
            "projected_latency_ms": V3_LATENCY,
            "steps_remaining": TOTAL_STEPS - CURRENT_STEP,
            "eta": ETA_DATE,
            "new_data_sources": NEW_DATA_SOURCES,
        }

    @app.get("/api/loss_curve")
    async def loss_curve():
        return {
            "steps": LOSS_STEPS,
            "v3_loss": V3_LOSS_CURVE,
            "v2_loss": V2_LOSS_CURVE,
        }

else:
    # Fallback: stdlib http.server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8306)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8306")
        HTTPServer(("0.0.0.0", 8306), Handler).serve_forever()
