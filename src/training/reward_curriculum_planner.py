"""Reward Curriculum Planner — FastAPI port 8607"""
import json, math
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8607

def build_html():
    # --- Reward Weight Schedule (DAgger runs r5→r11) ---
    runs = ["r5", "r6", "r7", "r8", "r9", "r10", "r11"]
    # Each row: [reach, grasp, lift, smooth, safety, time]
    # run11 target: 0.12/0.35/0.28/0.18/0.05/0.02
    weights = [
        [0.25, 0.25, 0.20, 0.15, 0.10, 0.05],  # r5
        [0.22, 0.27, 0.21, 0.16, 0.09, 0.05],  # r6
        [0.20, 0.29, 0.23, 0.17, 0.07, 0.04],  # r7
        [0.18, 0.31, 0.25, 0.17, 0.06, 0.03],  # r8
        [0.16, 0.32, 0.26, 0.17, 0.06, 0.03],  # r9
        [0.14, 0.33, 0.27, 0.18, 0.05, 0.03],  # r10
        [0.12, 0.35, 0.28, 0.18, 0.05, 0.02],  # r11
    ]
    components = ["reach", "grasp", "lift", "smooth", "safety", "time"]
    colors      = ["#38bdf8", "#C74634", "#34d399", "#a78bfa", "#f59e0b", "#64748b"]

    sw, sh = 580, 220
    sp_l, sp_r, sp_t, sp_b = 36, 130, 20, 32
    s_plot_w = sw - sp_l - sp_r
    s_plot_h = sh - sp_t - sp_b
    n_runs = len(runs)
    bar_group_w = s_plot_w / n_runs
    bar_w = bar_group_w * 0.65

    stacked_bars = ""
    for ri, run in enumerate(runs):
        x = sp_l + ri * bar_group_w + (bar_group_w - bar_w) / 2
        y_cursor = sp_t + s_plot_h  # bottom up
        for ci, (comp, color) in enumerate(zip(components, colors)):
            w = weights[ri][ci]
            bh = s_plot_h * w  # total weight sums to 1.0
            y_cursor -= bh
            stacked_bars += f'<rect x="{x:.1f}" y="{y_cursor:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.88"/>\n'
        # x label
        stacked_bars += f'<text x="{x + bar_w/2:.1f}" y="{sh - 10}" text-anchor="middle" font-size="10" fill="#94a3b8">{run}</text>\n'

    y_ticks = "".join(
        f'<text x="{sp_l - 5}" y="{sp_t + s_plot_h * (1 - v) + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{int(v*100)}%</text>'
        for v in [0.0, 0.25, 0.5, 0.75, 1.0]
    )
    y_gridlines = "".join(
        f'<line x1="{sp_l}" y1="{sp_t + s_plot_h * (1-v):.1f}" x2="{sp_l + s_plot_w}" y2="{sp_t + s_plot_h * (1-v):.1f}" stroke="#1e293b" stroke-width="1"/>'
        for v in [0.25, 0.5, 0.75]
    )
    # legend
    legend = ""
    for ci, (comp, color) in enumerate(zip(components, colors)):
        lx = sw - sp_r + 10
        ly = sp_t + ci * 22
        legend += f'<rect x="{lx}" y="{ly}" width="12" height="12" rx="2" fill="{color}"/>\n'
        legend += f'<text x="{lx + 16}" y="{ly + 10}" font-size="10" fill="#94a3b8">{comp}</text>\n'

    schedule_svg = f"""
    <svg width="{sw}" height="{sh}" xmlns="http://www.w3.org/2000/svg">
      {y_gridlines}
      {stacked_bars}
      {y_ticks}
      {legend}
    </svg>
    """

    # --- Reward Sensitivity Heatmap (grasp_weight x lift_weight, 5x5) ---
    grasp_vals = [0.20, 0.25, 0.30, 0.35, 0.40]
    lift_vals  = [0.15, 0.20, 0.25, 0.30, 0.35]
    # SR matrix — peaks near grasp=0.35, lift=0.28
    sr_matrix = [
        [0.41, 0.48, 0.52, 0.49, 0.43],
        [0.50, 0.58, 0.65, 0.61, 0.54],
        [0.57, 0.67, 0.76, 0.71, 0.62],
        [0.61, 0.72, 0.83, 0.79, 0.68],
        [0.55, 0.64, 0.71, 0.67, 0.58],
    ]
    optimal = (3, 2)  # row=grasp idx 3, col=lift idx 2

    hm_w, hm_h = 400, 280
    hm_pad_l, hm_pad_r, hm_pad_t, hm_pad_b = 56, 20, 20, 48
    cell_w = (hm_w - hm_pad_l - hm_pad_r) / 5
    cell_h = (hm_h - hm_pad_t - hm_pad_b) / 5

    def sr_color(v):
        # blue (low) → green (high)
        r = int(56  + (52  - 56)  * v)
        g = int(189 + (211 - 189) * v)
        b = int(248 + (153 - 248) * v)
        intensity = max(0.0, min(1.0, v))
        r2 = int(30  + (52  - 30)  * intensity)
        g2 = int(41  + (211 - 41)  * intensity)
        b2 = int(59  + (153 - 59)  * intensity)
        # simple lerp from dark-slate to teal-green
        rr = int(30  * (1-intensity) + 52  * intensity)
        gg = int(41  * (1-intensity) + 211 * intensity)
        bb = int(59  * (1-intensity) + 100 * intensity)
        return f"rgb({rr},{gg},{bb})"

    cells = ""
    for ri, gv in enumerate(grasp_vals):
        for ci, lv in enumerate(lift_vals):
            x = hm_pad_l + ci * cell_w
            y = hm_pad_t + (4 - ri) * cell_h  # flip so higher grasp = top
            sr = sr_matrix[ri][ci]
            fill = sr_color(sr)
            cells += f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{fill}"/>\n'
            cells += f'<text x="{x + cell_w/2:.1f}" y="{y + cell_h/2 + 5:.1f}" text-anchor="middle" font-size="10" fill="#e2e8f0" font-weight="600">{sr:.2f}</text>\n'

    # Optimal region box
    opt_ri, opt_ci = optimal
    opt_x = hm_pad_l + opt_ci * cell_w - 1
    opt_y = hm_pad_t + (4 - opt_ri) * cell_h - 1
    optimal_box = f'<rect x="{opt_x:.1f}" y="{opt_y:.1f}" width="{cell_w + 2:.1f}" height="{cell_h + 2:.1f}" fill="none" stroke="#fbbf24" stroke-width="2.5" rx="2"/>\n'
    optimal_box += f'<text x="{opt_x + cell_w/2:.1f}" y="{opt_y - 4:.1f}" text-anchor="middle" font-size="9" fill="#fbbf24">optimal</text>\n'

    hm_x_labels = "".join(
        f'<text x="{hm_pad_l + ci * cell_w + cell_w/2:.1f}" y="{hm_h - 28}" text-anchor="middle" font-size="9" fill="#94a3b8">{lv:.2f}</text>'
        for ci, lv in enumerate(lift_vals)
    )
    hm_x_axis = f'<text x="{hm_pad_l + (hm_w - hm_pad_l - hm_pad_r)/2:.1f}" y="{hm_h - 10}" text-anchor="middle" font-size="10" fill="#64748b">lift_weight</text>'
    hm_y_labels = "".join(
        f'<text x="{hm_pad_l - 5}" y="{hm_pad_t + (4 - ri) * cell_h + cell_h/2 + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{gv:.2f}</text>'
        for ri, gv in enumerate(grasp_vals)
    )
    hm_y_axis = f'<text x="12" y="{hm_pad_t + (hm_h - hm_pad_t - hm_pad_b)/2:.1f}" text-anchor="middle" font-size="10" fill="#64748b" transform="rotate(-90, 12, {hm_pad_t + (hm_h - hm_pad_t - hm_pad_b)/2:.1f})">grasp_weight</text>'

    heatmap_svg = f"""
    <svg width="{hm_w}" height="{hm_h}" xmlns="http://www.w3.org/2000/svg">
      {cells}
      {optimal_box}
      {hm_x_labels}
      {hm_x_axis}
      {hm_y_labels}
      {hm_y_axis}
    </svg>
    """

    # --- Curriculum Progression Scatter (8 tasks) ---
    tasks = [
        ("reach_cube",    0.15, 320),
        ("grasp_cube",    0.30, 580),
        ("lift_cube",     0.50, 920),
        ("stack_2",       0.62, 1380),
        ("pick_place",    0.72, 1750),
        ("sweep_table",   0.80, 2100),
        ("multi_obj",     0.88, 2800),
        ("dynamic_env",   0.95, 3600),
    ]
    colors_scatter = ["#38bdf8", "#38bdf8", "#34d399", "#34d399", "#a78bfa", "#a78bfa", "#C74634", "#C74634"]

    sc_w, sc_h = 580, 220
    sc_pl, sc_pr, sc_pt, sc_pb = 52, 16, 16, 32
    sc_pw = sc_w - sc_pl - sc_pr
    sc_ph = sc_h - sc_pt - sc_pb
    diff_min, diff_max = 0.0, 1.0
    step_min, step_max = 0, 4000

    def scx(d): return sc_pl + (d - diff_min) / (diff_max - diff_min) * sc_pw
    def scy(s): return sc_pt + sc_ph * (1 - (s - step_min) / (step_max - step_min))

    scatter_dots = ""
    for (name, diff, step), color in zip(tasks, colors_scatter):
        x, y = scx(diff), scy(step)
        scatter_dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" opacity="0.85"/>\n'
        anchor = "start" if diff < 0.7 else "end"
        dx = 10 if diff < 0.7 else -10
        scatter_dots += f'<text x="{x + dx:.1f}" y="{y + 4:.1f}" font-size="9" fill="#94a3b8" text-anchor="{anchor}">{name}</text>\n'

    # trend line (linear regression)
    n = len(tasks)
    mean_d = sum(t[1] for t in tasks) / n
    mean_s = sum(t[2] for t in tasks) / n
    num = sum((t[1] - mean_d) * (t[2] - mean_s) for t in tasks)
    den = sum((t[1] - mean_d) ** 2 for t in tasks)
    slope = num / den if den else 0
    intercept = mean_s - slope * mean_d
    trend_x1, trend_x2 = 0.1, 1.0
    trend_pts = f"{scx(trend_x1):.1f},{scy(slope*trend_x1+intercept):.1f} {scx(trend_x2):.1f},{scy(slope*trend_x2+intercept):.1f}"

    sc_x_labels = "".join(
        f'<text x="{scx(v):.1f}" y="{sc_h - 8}" text-anchor="middle" font-size="9" fill="#94a3b8">{v:.1f}</text>'
        for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    )
    sc_y_labels = "".join(
        f'<text x="{sc_pl - 5}" y="{scy(v) + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{v}</text>'
        for v in [0, 1000, 2000, 3000, 4000]
    )
    sc_gridlines = "".join(
        f'<line x1="{sc_pl}" y1="{scy(v):.1f}" x2="{sc_pl + sc_pw}" y2="{scy(v):.1f}" stroke="#1e293b" stroke-width="1"/>'
        for v in [1000, 2000, 3000, 4000]
    )

    scatter_svg = f"""
    <svg width="{sc_w}" height="{sc_h}" xmlns="http://www.w3.org/2000/svg">
      {sc_gridlines}
      <polyline points="{trend_pts}" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="5,3"/>
      {scatter_dots}
      {sc_x_labels}
      {sc_y_labels}
      <text x="{sc_pl + sc_pw/2:.1f}" y="{sc_h - 2}" text-anchor="middle" font-size="9" fill="#64748b">Difficulty</text>
      <text x="10" y="{sc_pt + sc_ph/2:.1f}" text-anchor="middle" font-size="9" fill="#64748b" transform="rotate(-90,10,{sc_pt + sc_ph/2:.1f})">Training Steps at SR&gt;0.7</text>
    </svg>
    """

    # run11 weight bars for summary display
    run11_weights = dict(zip(components, weights[-1]))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Reward Curriculum Planner — Port 8607</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .card-value {{ font-size: 1.6rem; font-weight: 700; }}
  .card-value.red   {{ color: #C74634; }}
  .card-value.cyan  {{ color: #38bdf8; }}
  .card-value.green {{ color: #34d399; }}
  .card-value.amber {{ color: #f59e0b; }}
  .card-sub {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
  .panel {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
  .panel-title {{ color: #38bdf8; font-size: 0.9rem; font-weight: 600; margin-bottom: 14px; }}
  .w-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-top: 12px; }}
  .w-cell {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px; text-align: center; }}
  .w-name  {{ font-size: 0.7rem; color: #64748b; margin-bottom: 4px; }}
  .w-val   {{ font-size: 1.1rem; font-weight: 700; }}
  footer {{ color: #334155; font-size: 0.75rem; text-align: center; margin-top: 24px; }}
</style>
</head>
<body>
<h1>Reward Curriculum Planner</h1>
<p class="subtitle">OCI Robot Cloud · Port 8607 · Adaptive reward shaping across DAgger runs r5→r11</p>

<div class="grid">
  <div class="card">
    <div class="card-label">Active Run</div>
    <div class="card-value cyan">r11</div>
    <div class="card-sub">7th DAgger iteration</div>
  </div>
  <div class="card">
    <div class="card-label">Sample Efficiency</div>
    <div class="card-value green">2.3×</div>
    <div class="card-sub">vs flat reward baseline</div>
  </div>
  <div class="card">
    <div class="card-label">Optimal Grasp Weight</div>
    <div class="card-value red">0.35</div>
    <div class="card-sub">sensitivity analysis peak</div>
  </div>
  <div class="card">
    <div class="card-label">Curriculum Tasks</div>
    <div class="card-value amber">8</div>
    <div class="card-sub">reach → dynamic_env</div>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Reward Weight Schedule — DAgger Runs r5 → r11 (stacked, sum=1.0)</div>
  {schedule_svg}
</div>

<div class="panel" style="display:flex; gap:32px; align-items:flex-start;">
  <div style="flex:0 0 auto;">
    <div class="panel-title">Sensitivity Heatmap — SR by Grasp × Lift Weight</div>
    {heatmap_svg}
  </div>
  <div style="flex:1;">
    <div class="panel-title">Run 11 Final Weights</div>
    <div class="w-grid">
      <div class="w-cell"><div class="w-name">reach</div><div class="w-val" style="color:#38bdf8">0.12</div></div>
      <div class="w-cell"><div class="w-name">grasp</div><div class="w-val" style="color:#C74634">0.35</div></div>
      <div class="w-cell"><div class="w-name">lift</div><div class="w-val" style="color:#34d399">0.28</div></div>
      <div class="w-cell"><div class="w-name">smooth</div><div class="w-val" style="color:#a78bfa">0.18</div></div>
      <div class="w-cell"><div class="w-name">safety</div><div class="w-val" style="color:#f59e0b">0.05</div></div>
      <div class="w-cell"><div class="w-name">time</div><div class="w-val" style="color:#64748b">0.02</div></div>
    </div>
    <p style="color:#64748b; font-size:0.78rem; margin-top:16px;">Weights evolved from uniform (0.25/0.25/0.20/0.15/0.10/0.05) over 7 runs via Bayesian optimization guided by success rate on the validation set of 50 episodes per task.</p>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Curriculum Progression — Training Steps to SR &gt; 0.7 per Task</div>
  {scatter_svg}
</div>

<footer>OCI Robot Cloud · Reward Curriculum Planner · cycle-137A</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Curriculum Planner")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "reward_curriculum_planner"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok", "port": PORT}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
