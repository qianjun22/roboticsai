"""Training Data Augmentor v2 — FastAPI port 8623"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8623

def build_html():
    # --- Augmentation strategy SR gain bar chart ---
    strategies = [
        ("domain_rand",  0.12, True),
        ("color_jitter", 0.07, False),
        ("temporal",     0.05, False),
        ("action_noise", 0.04, False),
        ("rotation",     0.03, False),
        ("gaussian",     0.02, False),
        ("none",         0.00, False),
        ("flip",        -0.01, False),
    ]
    # Sort descending by gain
    strategies_sorted = sorted(strategies, key=lambda x: -x[1])

    BAR_W = 480
    BAR_H = 300
    PAD_L, PAD_R, PAD_T, PAD_B = 110, 20, 20, 36
    inner_w = BAR_W - PAD_L - PAD_R
    inner_h = BAR_H - PAD_T - PAD_B
    bar_h = inner_h / len(strategies_sorted) * 0.68
    spacing = inner_h / len(strategies_sorted)
    gain_min, gain_max = -0.02, 0.14

    def bar_x(v):
        return PAD_L + (v - gain_min) / (gain_max - gain_min) * inner_w

    zero_x = bar_x(0.0)
    bar_elems = []
    # zero line
    bar_elems.append(f'<line x1="{zero_x:.1f}" y1="{PAD_T}" x2="{zero_x:.1f}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>')
    for i, (name, gain, is_top) in enumerate(strategies_sorted):
        y_center = PAD_T + (i + 0.5) * spacing
        bar_y = y_center - bar_h / 2
        color = '#C74634' if is_top else ('#38bdf8' if gain > 0 else '#ef4444')
        if gain >= 0:
            bx = zero_x
            bw = bar_x(gain) - zero_x
        else:
            bx = bar_x(gain)
            bw = zero_x - bx
        bar_elems.append(f'<rect x="{bx:.1f}" y="{bar_y:.1f}" width="{max(bw,1):.1f}" height="{bar_h:.1f}" fill="{color}" rx="3"/>')
        # label left
        bar_elems.append(f'<text x="{PAD_L-6}" y="{y_center+4:.1f}" text-anchor="end" fill="#e2e8f0" font-size="11">{name}</text>')
        # value right of bar
        val_x = bar_x(gain) + (5 if gain >= 0 else -5)
        anchor = 'start' if gain >= 0 else 'end'
        sign = '+' if gain > 0 else ''
        bar_elems.append(f'<text x="{val_x:.1f}" y="{y_center+4:.1f}" text-anchor="{anchor}" fill="#94a3b8" font-size="10">{sign}{gain:.2f}</text>')

    # x-axis
    for gv in [-0.01, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14]:
        bx2 = bar_x(gv)
        sign = '+' if gv > 0 else ''
        bar_elems.append(f'<text x="{bx2:.0f}" y="{PAD_T+inner_h+14}" text-anchor="middle" fill="#64748b" font-size="9">{sign}{gv:.2f}</text>')
    bar_elems.append(f'<text x="{PAD_L + inner_w//2}" y="{BAR_H-3}" text-anchor="middle" fill="#64748b" font-size="10">SR Gain (pp)</text>')
    bar_svg = '\n'.join(bar_elems)

    # --- Data Multiplier vs SR curve ---
    CURVE_W, CURVE_H = 420, 240
    C_PAD_L, C_PAD_R, C_PAD_T, C_PAD_B = 52, 20, 20, 38
    c_inner_w = CURVE_W - C_PAD_L - C_PAD_R
    c_inner_h = CURVE_H - C_PAD_T - C_PAD_B

    multipliers = [1, 2, 4, 8]
    # Diminishing returns plateau at 4x
    sr_vals = [0.61, 0.72, 0.79, 0.80]
    mult_min, mult_max = 1, 8
    sr_cmin, sr_cmax = 0.55, 0.85

    def cx(v): return C_PAD_L + (v - mult_min) / (mult_max - mult_min) * c_inner_w
    def cy(v): return C_PAD_T + c_inner_h - (v - sr_cmin) / (sr_cmax - sr_cmin) * c_inner_h

    # Smooth interpolated path
    interp_pts = []
    for s in range(101):
        t = s / 100.0
        xv = 1 + t * 7
        # Plateau function: SR = a + b*(1-exp(-c*x))
        yv = 0.61 + 0.195 * (1 - math.exp(-0.55 * (xv - 1)))
        interp_pts.append((cx(xv), cy(yv)))
    path_d = 'M ' + ' L '.join(f'{px:.1f},{py:.1f}' for px, py in interp_pts)

    c_elems = []
    # Axes
    c_elems.append(f'<line x1="{C_PAD_L}" y1="{C_PAD_T}" x2="{C_PAD_L}" y2="{C_PAD_T+c_inner_h}" stroke="#475569" stroke-width="1"/>')
    c_elems.append(f'<line x1="{C_PAD_L}" y1="{C_PAD_T+c_inner_h}" x2="{C_PAD_L+c_inner_w}" y2="{C_PAD_T+c_inner_h}" stroke="#475569" stroke-width="1"/>')
    # Plateau annotation line at 4x
    c_elems.append(f'<line x1="{cx(4):.1f}" y1="{C_PAD_T}" x2="{cx(4):.1f}" y2="{C_PAD_T+c_inner_h}" stroke="#C74634" stroke-width="1" stroke-dasharray="5,3" opacity="0.7"/>')
    c_elems.append(f'<text x="{cx(4)+4:.0f}" y="{C_PAD_T+14}" fill="#C74634" font-size="10">plateau ≈4×</text>')
    c_elems.append(f'<path d="{path_d}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')
    # Data points
    for m, s in zip(multipliers, sr_vals):
        c_elems.append(f'<circle cx="{cx(m):.1f}" cy="{cy(s):.1f}" r="5" fill="#C74634"/>')
        c_elems.append(f'<text x="{cx(m)+8:.0f}" y="{cy(s)-6:.0f}" fill="#e2e8f0" font-size="10">{m}× → {s:.0%}</text>')
    # Axis labels
    for mv in [1, 2, 4, 8]:
        c_elems.append(f'<text x="{cx(mv):.0f}" y="{C_PAD_T+c_inner_h+14}" text-anchor="middle" fill="#64748b" font-size="9">{mv}×</text>')
    for sv2 in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        c_elems.append(f'<text x="{C_PAD_L-6}" y="{cy(sv2)+4:.0f}" text-anchor="end" fill="#64748b" font-size="9">{sv2:.0%}</text>')
    c_elems.append(f'<text x="{C_PAD_L+c_inner_w//2}" y="{CURVE_H-4}" text-anchor="middle" fill="#64748b" font-size="10">Data Multiplier</text>')
    c_elems.append(f'<text x="14" y="{C_PAD_T+c_inner_h//2}" text-anchor="middle" fill="#64748b" font-size="10" transform="rotate(-90,14,{C_PAD_T+c_inner_h//2})">Success Rate</text>')
    curve_svg = '\n'.join(c_elems)

    # --- Augmentation Radar (5 dims) ---
    RADAR_SIZE = 280
    RC = RADAR_SIZE // 2
    R_MAX = 100
    dims = ['Geometric', 'Photometric', 'Noise', 'Temporal', 'Semantic']
    N = len(dims)
    angles = [math.pi/2 - 2*math.pi*i/N for i in range(N)]

    # Scores per strategy (subset of top 4)
    strat_scores = [
        ('domain_rand',  [0.9, 0.8, 0.5, 0.6, 0.7], '#C74634'),
        ('color_jitter', [0.2, 0.9, 0.3, 0.1, 0.2], '#38bdf8'),
        ('temporal',     [0.3, 0.2, 0.4, 0.9, 0.5], '#a78bfa'),
        ('action_noise', [0.4, 0.3, 0.8, 0.5, 0.3], '#34d399'),
    ]

    rad_elems = []
    # Background rings
    for level in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = []
        for ang in angles:
            rx = RC + R_MAX * level * math.cos(ang)
            ry = RC - R_MAX * level * math.sin(ang)
            ring_pts.append(f'{rx:.1f},{ry:.1f}')
        rad_elems.append(f'<polygon points="{" ".join(ring_pts)}" fill="none" stroke="#334155" stroke-width="1"/>')
    # Axes
    for i, ang in enumerate(angles):
        ex = RC + R_MAX * math.cos(ang)
        ey = RC - R_MAX * math.sin(ang)
        rad_elems.append(f'<line x1="{RC}" y1="{RC}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>')
        lx = RC + (R_MAX + 18) * math.cos(ang)
        ly = RC - (R_MAX + 18) * math.sin(ang)
        rad_elems.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="middle" fill="#94a3b8" font-size="10">{dims[i]}</text>')
    # Strategy polygons
    for sname, scores, color in strat_scores:
        pts = []
        for i, s in enumerate(scores):
            rx = RC + R_MAX * s * math.cos(angles[i])
            ry = RC - R_MAX * s * math.sin(angles[i])
            pts.append(f'{rx:.1f},{ry:.1f}')
        rad_elems.append(f'<polygon points="{" ".join(pts)}" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="1.5"/>')
    radar_svg = '\n'.join(rad_elems)

    # Legend for radar
    legend_items = ''
    for sname, _, color in strat_scores:
        legend_items += f'<div class="leg-item"><div class="leg-dot" style="background:{color}"></div>{sname}</div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Training Data Augmentor v2 — Port {PORT}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
  h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: 4px; }}
  .subtitle {{ color: #38bdf8; font-size: 0.95rem; margin-bottom: 28px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 24px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
  .card h2 {{ color: #38bdf8; font-size: 1.05rem; margin-bottom: 14px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 24px; }}
  .metric {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; text-align: center; }}
  .metric .val {{ font-size: 2rem; font-weight: 700; color: #C74634; }}
  .metric .lbl {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
  .legend {{ display: flex; gap: 14px; margin-top: 10px; font-size: 0.8rem; flex-wrap: wrap; }}
  .leg-item {{ display: flex; align-items: center; gap: 5px; }}
  .leg-dot {{ width: 12px; height: 12px; border-radius: 2px; }}
  svg {{ display: block; }}
</style>
</head>
<body>
<h1>Training Data Augmentor v2</h1>
<div class="subtitle">Augmentation strategy analysis · port {PORT}</div>

<div class="grid">
  <div class="card">
    <h2>Augmentation Strategy SR Gain</h2>
    <svg width="{BAR_W}" height="{BAR_H}" viewBox="0 0 {BAR_W} {BAR_H}">
      {bar_svg}
    </svg>
    <div style="margin-top:6px;font-size:0.78rem;color:#64748b">Oracle red = top strategy · dashed zero line</div>
  </div>

  <div class="card">
    <h2>Data Multiplier vs Success Rate</h2>
    <svg width="{CURVE_W}" height="{CURVE_H}" viewBox="0 0 {CURVE_W} {CURVE_H}">
      {curve_svg}
    </svg>
    <div style="margin-top:6px;font-size:0.78rem;color:#64748b">Diminishing returns plateau at 4× multiplier</div>
  </div>

  <div class="card" style="grid-column: 1 / -1; display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
    <div>
      <h2>Augmentation Radar (5 Dimensions)</h2>
      <svg width="{RADAR_SIZE}" height="{RADAR_SIZE}" viewBox="0 0 {RADAR_SIZE} {RADAR_SIZE}">
        {radar_svg}
      </svg>
      <div class="legend">{legend_items}</div>
    </div>
    <div style="flex:1; min-width:220px;">
      <h2 style="margin-bottom:12px;">Dimension Guide</h2>
      <ul style="color:#94a3b8; font-size:0.85rem; line-height:1.9; padding-left:16px;">
        <li><b style="color:#e2e8f0;">Geometric</b> — rotations, flips, scaling</li>
        <li><b style="color:#e2e8f0;">Photometric</b> — color jitter, brightness</li>
        <li><b style="color:#e2e8f0;">Noise</b> — Gaussian, action perturbation</li>
        <li><b style="color:#e2e8f0;">Temporal</b> — frame skip, speed variation</li>
        <li><b style="color:#e2e8f0;">Semantic</b> — domain randomization, scene swap</li>
      </ul>
      <div style="margin-top:18px; padding:14px; background:#0f172a; border-radius:8px; border:1px solid #334155;">
        <div style="color:#38bdf8; font-size:0.85rem; font-weight:600; margin-bottom:6px;">Recommendation</div>
        <div style="color:#94a3b8; font-size:0.82rem; line-height:1.6;">Combine top 4 strategies (domain_rand + color_jitter + temporal + action_noise) at 4× multiplier for optimal +0.18pp SR gain with efficient compute use.</div>
      </div>
    </div>
  </div>
</div>

<div class="metrics">
  <div class="metric">
    <div class="val">+0.18pp</div>
    <div class="lbl">Combined SR gain (top 4 strategies)</div>
  </div>
  <div class="metric">
    <div class="val">4×</div>
    <div class="lbl">Optimal data multiplier (plateau threshold)</div>
  </div>
  <div class="metric">
    <div class="val">+0.12pp</div>
    <div class="lbl">Best single strategy: domain_rand</div>
  </div>
  <div class="metric">
    <div class="val">8</div>
    <div class="lbl">Augmentation strategies evaluated</div>
  </div>
</div>

</body>
</html>'''

if USE_FASTAPI:
    app = FastAPI(title="Training Data Augmentor v2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok","port":8623}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
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
