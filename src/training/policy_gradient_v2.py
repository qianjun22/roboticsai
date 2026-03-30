"""Policy Gradient v2 — FastAPI service on port 8333.

Advanced policy gradient analysis for DAgger run10 with adaptive learning
rate scheduling, per-layer gradient health tracking, and plateau detection.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock training data — DAgger run10, 1420 steps
# ---------------------------------------------------------------------------

TOTAL_STEPS = 1420
GRAD_CLIP_TOTAL = 26
CURRENT_GRAD_NORM = 0.31
CURRENT_LR = 1.8e-6
ADAPTIVE_BOOST_STEP = 1150
ADAPTIVE_BOOST_SR = 0.03

LAYER_GROUPS = ["vision_encoder", "cross_attention", "action_head", "value_head"]
LAYER_COLORS = ["#38bdf8", "#22c55e", "#C74634", "#fbbf24"]

# Peak gradient norms per layer group
LAYER_PEAK_NORMS = {
    "vision_encoder": 0.62,
    "cross_attention": 0.74,
    "action_head": 0.89,
    "value_head": 0.51,
}
LAYER_CURRENT_NORMS = {
    "vision_encoder": 0.19,
    "cross_attention": 0.28,
    "action_head": 0.31,
    "value_head": 0.22,
}


def _grad_norm_series(layer: str, seed: int):
    """Generate gradient norm trajectory for a layer over TOTAL_STEPS."""
    rng = random.Random(seed)
    peak = LAYER_PEAK_NORMS[layer]
    final = LAYER_CURRENT_NORMS[layer]
    series = []
    for i in range(TOTAL_STEPS):
        t = i / (TOTAL_STEPS - 1)
        # Exponential decay with noise; spike early
        if i < 50:
            base = peak * (0.6 + rng.uniform(0, 0.4))
        elif i < 400:
            base = peak * math.exp(-2.5 * (i - 50) / 350)
            base = max(base, final * 1.5)
        else:
            base = final + (peak * 0.2 - final) * math.exp(-3 * (i - 400) / 1020)
        noise = rng.gauss(0, base * 0.12)
        series.append(max(0.01, round(base + noise, 3)))
    # Plateau region 1100-1200 slightly elevated
    for i in range(1100, min(1200, TOTAL_STEPS)):
        series[i] = round(series[i] * 1.18, 3)
    return series


# Pre-compute series (downsample to 140 points for SVG)
def _downsample(series, n=140):
    step = len(series) / n
    return [series[min(int(i * step), len(series) - 1)] for i in range(n)]


GRAD_SERIES = {layer: _grad_norm_series(layer, i * 7) for i, layer in enumerate(LAYER_GROUPS)}
GRAD_SERIES_DS = {layer: _downsample(GRAD_SERIES[layer]) for layer in LAYER_GROUPS}

# Clip events: mostly in first 400 steps
rng0 = random.Random(99)
CLIP_EVENTS = sorted(rng0.sample(range(0, 400), 22) + rng0.sample(range(400, TOTAL_STEPS), 4))


def _lr_schedule(step: int) -> float:
    """Warmup 200 steps, cosine decay 3e-5 → 1e-6 over 1420 steps."""
    lr_max = 3e-5
    lr_min = 1e-6
    warmup = 200
    if step < warmup:
        return lr_min + (lr_max - lr_min) * step / warmup
    t = (step - warmup) / (TOTAL_STEPS - warmup)
    cosine = lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * t))
    # Plateau boost at step 1100-1200
    if 1100 <= step <= 1200:
        boost = 1.0 + 0.4 * math.sin(math.pi * (step - 1100) / 100)
        cosine *= boost
    return round(cosine, 10)


LR_SERIES = [_lr_schedule(i) for i in range(TOTAL_STEPS)]
LR_SERIES_DS = _downsample(LR_SERIES)

# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def _grad_norm_svg() -> str:
    """SVG 1: Gradient norm trajectory per layer group over 1420 steps."""
    W, H = 640, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 40, 55
    bg = "#0f172a"
    oracle_red = "#C74634"
    gray = "#64748b"
    white = "#f1f5f9"

    CHART_W = W - PAD_L - PAD_R
    CHART_H = H - PAD_T - PAD_B
    N = len(GRAD_SERIES_DS["vision_encoder"])
    Y_MAX = 1.05
    Y_MIN = 0.0

    def to_px(val, i):
        px_x = PAD_L + (i / (N - 1)) * CHART_W
        px_y = PAD_T + (1 - (val - Y_MIN) / (Y_MAX - Y_MIN)) * CHART_H
        return px_x, px_y

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:{bg};border-radius:8px;">')
    lines.append(f'<text x="{W//2}" y="22" fill="{white}" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Gradient Norm Trajectory — DAgger Run10 (1420 steps)</text>')

    # Grid
    for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
        _, gy = to_px(v, 0)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="{gray}" stroke-width="0.5" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-5}" y="{gy+4:.1f}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="end">{v:.1f}</text>')

    # Clip threshold line at 1.0
    _, clip_y = to_px(1.0, 0)
    lines.append(f'<line x1="{PAD_L}" y1="{clip_y:.1f}" x2="{W-PAD_R}" y2="{clip_y:.1f}" stroke="{oracle_red}" stroke-width="1.5" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{W-PAD_R-2}" y="{clip_y-4:.1f}" fill="{oracle_red}" font-size="8" font-family="monospace" text-anchor="end">clip=1.0</text>')

    # Clip events (orange diamonds)
    for step in CLIP_EVENTS:
        i_ds = int(step / TOTAL_STEPS * N)
        if i_ds >= N:
            i_ds = N - 1
        val = GRAD_SERIES_DS["action_head"][i_ds]
        cx, cy = to_px(val, i_ds)
        lines.append(f'<polygon points="{cx:.1f},{cy-5:.1f} {cx+4:.1f},{cy:.1f} {cx:.1f},{cy+5:.1f} {cx-4:.1f},{cy:.1f}" fill="{oracle_red}" opacity="0.7"/>')

    # Stable zone marker (after step 800)
    stable_i = int(800 / TOTAL_STEPS * N)
    sx, _ = to_px(0.5, stable_i)
    lines.append(f'<line x1="{sx:.1f}" y1="{PAD_T}" x2="{sx:.1f}" y2="{H-PAD_B}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,4" stroke-opacity="0.5"/>')
    lines.append(f'<text x="{sx+4:.1f}" y="{PAD_T+12}" fill="#22c55e" font-size="9" font-family="monospace">stable</text>')

    # Plateau zone 1100-1200
    pi1 = int(1100 / TOTAL_STEPS * N)
    pi2 = int(1200 / TOTAL_STEPS * N)
    px1, _ = to_px(0.5, pi1)
    px2, _ = to_px(0.5, pi2)
    lines.append(f'<rect x="{px1:.1f}" y="{PAD_T}" width="{px2-px1:.1f}" height="{CHART_H}" fill="#fbbf24" opacity="0.08"/>')
    lines.append(f'<text x="{(px1+px2)/2:.1f}" y="{PAD_T+12}" fill="#fbbf24" font-size="8" font-family="monospace" text-anchor="middle">plateau</text>')

    # Layer lines
    for idx, (layer, color) in enumerate(zip(LAYER_GROUPS, LAYER_COLORS)):
        ds = GRAD_SERIES_DS[layer]
        pts = ["{:.1f},{:.1f}".format(*to_px(ds[i], i)) for i in range(N)]
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.6" stroke-opacity="0.9"/>')

    # X axis labels
    for step_lbl in [0, 400, 800, 1200, 1420]:
        i_ds = int(step_lbl / TOTAL_STEPS * (N - 1))
        px_x, _ = to_px(0, i_ds)
        lines.append(f'<text x="{px_x:.1f}" y="{H-PAD_B+14}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="middle">{step_lbl}</text>')

    lines.append(f'<text x="{W//2}" y="{H-PAD_B+28}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="middle">Training Step</text>')

    # Legend
    lx = PAD_L
    for layer, color in zip(LAYER_GROUPS, LAYER_COLORS):
        lines.append(f'<rect x="{lx}" y="{H-PAD_B+36}" width="14" height="4" fill="{color}"/>')
        lines.append(f'<text x="{lx+18}" y="{H-PAD_B+42}" fill="{color}" font-size="9" font-family="monospace">{layer}</text>')
        lx += 145

    lines.append(f'<text x="{W-PAD_R}" y="{H-4}" fill="#C74634" font-size="8" font-family="monospace" text-anchor="end">◆ clip event ({len(CLIP_EVENTS)} total)</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _lr_schedule_svg() -> str:
    """SVG 2: Adaptive LR schedule with grad_norm overlay."""
    W, H = 640, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 65, 40, 55
    bg = "#0f172a"
    oracle_red = "#C74634"
    sky = "#38bdf8"
    yellow = "#fbbf24"
    green = "#22c55e"
    gray = "#64748b"
    white = "#f1f5f9"

    CHART_W = W - PAD_L - PAD_R
    CHART_H = H - PAD_T - PAD_B
    N = len(LR_SERIES_DS)

    LR_MAX = 3e-5
    LR_MIN = 0.0
    GN_MAX = 1.0
    GN_MIN = 0.0

    def lr_px(val, i):
        px_x = PAD_L + (i / (N - 1)) * CHART_W
        px_y = PAD_T + (1 - (val - LR_MIN) / (LR_MAX - LR_MIN)) * CHART_H
        return px_x, px_y

    def gn_px(val, i):
        px_x = PAD_L + (i / (N - 1)) * CHART_W
        px_y = PAD_T + (1 - (val - GN_MIN) / (GN_MAX - GN_MIN)) * CHART_H
        return px_x, px_y

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:{bg};border-radius:8px;">')
    lines.append(f'<text x="{W//2}" y="22" fill="{white}" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Adaptive LR Schedule + Gradient Norm Overlay</text>')

    # LR grid + y-axis
    for frac, val_f in [(0, 0.0), (0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (1.0, 1.0)]:
        v = LR_MIN + frac * (LR_MAX - LR_MIN)
        _, gy = lr_px(v, 0)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="{gray}" stroke-width="0.5" stroke-dasharray="4,4"/>')
        label = f"{v*1e6:.1f}e-6" if v > 0 else "0"
        lines.append(f'<text x="{PAD_L-5}" y="{gy+4:.1f}" fill="{sky}" font-size="8" font-family="monospace" text-anchor="end">{label}</text>')

    # GN right y-axis
    for gn_v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        _, gy = gn_px(gn_v, 0)
        lines.append(f'<text x="{W-PAD_R+5}" y="{gy+4:.1f}" fill="{green}" font-size="8" font-family="monospace">{gn_v:.2f}</text>')

    lines.append(f'<text x="{PAD_L-45}" y="{PAD_T + CHART_H//2}" fill="{sky}" font-size="9" font-family="monospace" transform="rotate(-90,{PAD_L-45},{PAD_T + CHART_H//2})">LR</text>')
    lines.append(f'<text x="{W-PAD_R+50}" y="{PAD_T + CHART_H//2}" fill="{green}" font-size="9" font-family="monospace" transform="rotate(90,{W-PAD_R+50},{PAD_T + CHART_H//2})">grad_norm</text>')

    # Warmup zone
    warmup_i = int(200 / TOTAL_STEPS * N)
    wx, _ = lr_px(0, warmup_i)
    lines.append(f'<rect x="{PAD_L}" y="{PAD_T}" width="{wx-PAD_L:.1f}" height="{CHART_H}" fill="{sky}" opacity="0.05"/>')
    lines.append(f'<text x="{(PAD_L+wx)/2:.1f}" y="{PAD_T+14}" fill="{sky}" font-size="8" font-family="monospace" text-anchor="middle">warmup</text>')

    # Plateau zone 1100-1200
    pi1 = int(1100 / TOTAL_STEPS * N)
    pi2 = int(1200 / TOTAL_STEPS * N)
    px1, _ = lr_px(0, pi1)
    px2, _ = lr_px(0, pi2)
    lines.append(f'<rect x="{px1:.1f}" y="{PAD_T}" width="{px2-px1:.1f}" height="{CHART_H}" fill="{yellow}" opacity="0.1"/>')
    lines.append(f'<text x="{(px1+px2)/2:.1f}" y="{PAD_T+14}" fill="{yellow}" font-size="8" font-family="monospace" text-anchor="middle">LR boost</text>')

    # Boost annotation arrow
    bx, by = lr_px(_lr_schedule(ADAPTIVE_BOOST_STEP), int(ADAPTIVE_BOOST_STEP / TOTAL_STEPS * N))
    lines.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4" fill="{oracle_red}"/>')
    lines.append(f'<text x="{bx-2:.1f}" y="{by-9:.1f}" fill="{oracle_red}" font-size="8" font-family="monospace" text-anchor="middle">+{ADAPTIVE_BOOST_SR*100:.0f}% SR</text>')

    # Grad norm (action_head, downsampled)
    action_ds = GRAD_SERIES_DS["action_head"]
    gn_pts = ["{:.1f},{:.1f}".format(*gn_px(action_ds[i], i)) for i in range(N)]
    lines.append(f'<polyline points="{" ".join(gn_pts)}" fill="none" stroke="{green}" stroke-width="1.4" stroke-opacity="0.7" stroke-dasharray="4,2"/>')

    # LR line
    lr_pts = ["{:.1f},{:.1f}".format(*lr_px(LR_SERIES_DS[i], i)) for i in range(N)]
    lines.append(f'<polyline points="{" ".join(lr_pts)}" fill="none" stroke="{sky}" stroke-width="2" stroke-opacity="0.95"/>')

    # X axis labels
    for step_lbl in [0, 200, 400, 800, 1100, 1200, 1420]:
        i_ds = int(step_lbl / TOTAL_STEPS * (N - 1))
        px_x, _ = lr_px(0, i_ds)
        lines.append(f'<text x="{px_x:.1f}" y="{H-PAD_B+14}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="middle">{step_lbl}</text>')

    lines.append(f'<text x="{W//2}" y="{H-PAD_B+28}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="middle">Training Step</text>')

    # Legend
    lines.append(f'<rect x="{PAD_L}" y="{H-PAD_B+36}" width="16" height="4" fill="{sky}"/>')
    lines.append(f'<text x="{PAD_L+20}" y="{H-PAD_B+42}" fill="{sky}" font-size="9" font-family="monospace">Learning Rate</text>')
    lines.append(f'<rect x="{PAD_L+130}" y="{H-PAD_B+36}" width="16" height="4" fill="{green}"/>')
    lines.append(f'<text x="{PAD_L+150}" y="{H-PAD_B+42}" fill="{green}" font-size="9" font-family="monospace">action_head grad_norm (dashed)</text>')
    lines.append(f'<circle cx="{PAD_L+390}" cy="{H-PAD_B+38}" r="4" fill="{oracle_red}"/>')
    lines.append(f'<text x="{PAD_L+398}" y="{H-PAD_B+42}" fill="{oracle_red}" font-size="9" font-family="monospace">adaptive LR boost event</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    grad_svg = _grad_norm_svg()
    lr_svg = _lr_schedule_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    layer_rows = ""
    for layer, color in zip(LAYER_GROUPS, LAYER_COLORS):
        peak = LAYER_PEAK_NORMS[layer]
        curr = LAYER_CURRENT_NORMS[layer]
        health = "HEALTHY" if curr < 0.5 else "ELEVATED"
        h_color = "#22c55e" if curr < 0.5 else "#fbbf24"
        layer_rows += f"""
        <tr>
          <td><span style="color:{color};font-weight:bold;">{layer}</span></td>
          <td style="color:#38bdf8;">{peak:.2f}</td>
          <td style="color:#22c55e;">{curr:.2f}</td>
          <td style="color:#64748b;">{100*(peak-curr)/peak:.0f}%</td>
          <td><span style="color:{h_color};">{health}</span></td>
        </tr>"""

    clip_early = sum(1 for s in CLIP_EVENTS if s < 400)
    clip_late = len(CLIP_EVENTS) - clip_early
    clip_rate = len(CLIP_EVENTS) / TOTAL_STEPS * 100

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Policy Gradient v2 — DAgger Run10</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-title {{ color: #38bdf8; font-size: 13px; font-weight: bold; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .metric {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
    .metric-label {{ color: #64748b; font-size: 12px; }}
    .metric-value {{ color: #f1f5f9; font-size: 12px; font-weight: bold; }}
    .good {{ color: #22c55e !important; }}
    .warn {{ color: #fbbf24 !important; }}
    .charts {{ display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ color: #38bdf8; text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    .section-title {{ color: #C74634; font-size: 14px; font-weight: bold; margin: 20px 0 10px; text-transform: uppercase; }}
    .banner {{ background: #0d2137; border: 1px solid #38bdf8; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; color: #7dd3fc; font-size: 12px; }}
    footer {{ color: #334155; font-size: 10px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Policy Gradient v2</h1>
  <div class="subtitle">DAgger Run10 — Adaptive LR Analysis  |  {ts}</div>

  <div class="banner">Adaptive LR boost resolved plateau at step 1150 (+3% SR). Gradient norms stable after step 800. 93% of clips occurred in first 400 steps (expected early training behavior).</div>

  <div class="grid">
    <div class="card">
      <div class="card-title">Training Progress</div>
      <div class="metric"><span class="metric-label">Total Steps</span><span class="metric-value">{TOTAL_STEPS}</span></div>
      <div class="metric"><span class="metric-label">Current Grad Norm</span><span class="metric-value good">{CURRENT_GRAD_NORM:.2f} (healthy &lt;1.0)</span></div>
      <div class="metric"><span class="metric-label">Current LR</span><span class="metric-value">{CURRENT_LR:.2e}</span></div>
      <div class="metric"><span class="metric-label">Stable Since</span><span class="metric-value good">Step 800</span></div>
      <div class="metric"><span class="metric-label">Plateau Detected</span><span class="metric-value warn">Step 1100–1200</span></div>
    </div>
    <div class="card">
      <div class="card-title">Gradient Clipping Stats</div>
      <div class="metric"><span class="metric-label">Total Clips</span><span class="metric-value">{GRAD_CLIP_TOTAL}</span></div>
      <div class="metric"><span class="metric-label">Clip Rate</span><span class="metric-value">{clip_rate:.2f}% of steps</span></div>
      <div class="metric"><span class="metric-label">Early Clips (&lt;step 400)</span><span class="metric-value warn">{clip_early} ({clip_early*100//GRAD_CLIP_TOTAL}%)</span></div>
      <div class="metric"><span class="metric-label">Late Clips (&gt;step 400)</span><span class="metric-value good">{clip_late}</span></div>
      <div class="metric"><span class="metric-label">Adaptive Boost Effect</span><span class="metric-value good">+{ADAPTIVE_BOOST_SR*100:.0f}% SR at step {ADAPTIVE_BOOST_STEP}</span></div>
    </div>
  </div>

  <div class="charts">
    {grad_svg}
    {lr_svg}
  </div>

  <div class="section-title">Per-Layer Gradient Health</div>
  <table>
    <thead>
      <tr>
        <th>Layer Group</th><th>Peak Norm</th><th>Current Norm</th><th>Reduction</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{layer_rows}</tbody>
  </table>

  <footer>OCI Robot Cloud — Policy Gradient v2 | DAgger Run10 | Port 8333 | &copy; 2026 Oracle</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="Policy Gradient v2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_gradient_v2", "port": 8333}

    @app.get("/metrics")
    async def metrics():
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_steps": TOTAL_STEPS,
            "grad_clip_total": GRAD_CLIP_TOTAL,
            "current_grad_norm": CURRENT_GRAD_NORM,
            "current_lr": CURRENT_LR,
            "adaptive_boost_step": ADAPTIVE_BOOST_STEP,
            "adaptive_boost_sr_delta": ADAPTIVE_BOOST_SR,
            "per_layer_peak_norms": LAYER_PEAK_NORMS,
            "per_layer_current_norms": LAYER_CURRENT_NORMS,
            "clip_events": CLIP_EVENTS,
        }

    @app.get("/lr-schedule")
    async def lr_schedule():
        """Return full LR schedule (downsampled to 140 points)."""
        return {"steps": TOTAL_STEPS, "lr_series": LR_SERIES_DS}

    @app.get("/grad-norms")
    async def grad_norms():
        """Return downsampled gradient norm series per layer."""
        return {"steps": TOTAL_STEPS, "series": GRAD_SERIES_DS}

else:
    # Fallback stdlib HTTP server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"policy_gradient_v2","port":8333}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8333)
    else:
        print("FastAPI not available — using stdlib http.server on port 8333")
        with socketserver.TCPServer(("", 8333), _Handler) as httpd:
            httpd.serve_forever()
