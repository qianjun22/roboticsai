"""Imitation Gap Analyzer — FastAPI port 8792"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8792

def build_html():
    random.seed(42)

    # Generate BC vs DAgger vs expert performance curves over training steps
    steps = list(range(0, 5001, 250))
    def bc_curve(s):
        return round(5 + 55 * (1 - math.exp(-s / 2000)) + random.uniform(-1.5, 1.5), 2)
    def dagger_curve(s):
        return round(8 + 70 * (1 - math.exp(-s / 1800)) + random.uniform(-1.2, 1.2), 2)
    expert_line = 92.0

    random.seed(42)
    bc_vals = [bc_curve(s) for s in steps]
    random.seed(7)
    dagger_vals = [dagger_curve(s) for s in steps]

    # SVG dimensions
    W, H = 700, 260
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    max_val, min_val = 100, 0

    def sx(i):
        return pad_l + (i / (len(steps) - 1)) * chart_w

    def sy(v):
        return pad_t + chart_h - ((v - min_val) / (max_val - min_val)) * chart_h

    def polyline(vals, color):
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>'

    # Expert reference line
    ey = sy(expert_line)
    expert_svg = f'<line x1="{pad_l}" y1="{ey:.1f}" x2="{pad_l+chart_w}" y2="{ey:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,4"/>'
    expert_label = f'<text x="{pad_l+chart_w-4}" y="{ey-6:.1f}" fill="#f59e0b" font-size="11" text-anchor="end">Expert 92%</text>'

    # Y-axis ticks
    yticks_svg = ""
    for tick in range(0, 101, 20):
        ty = sy(tick)
        yticks_svg += f'<line x1="{pad_l-4}" y1="{ty:.1f}" x2="{pad_l}" y2="{ty:.1f}" stroke="#475569"/>'
        yticks_svg += f'<text x="{pad_l-8}" y="{ty+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick}</text>'

    # X-axis ticks
    xticks_svg = ""
    for i, s in enumerate(steps):
        if s % 1000 == 0:
            tx = sx(i)
            xticks_svg += f'<line x1="{tx:.1f}" y1="{pad_t+chart_h}" x2="{tx:.1f}" y2="{pad_t+chart_h+4}" stroke="#475569"/>'
            xticks_svg += f'<text x="{tx:.1f}" y="{pad_t+chart_h+16:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{s}</text>'

    # Imitation gap shading between dagger and expert at last step
    gap_pct = round(expert_line - dagger_vals[-1], 1)
    bc_final = bc_vals[-1]
    dagger_final = dagger_vals[-1]

    # Covariate shift heatmap bars — simulated distribution shift over 8 tasks
    tasks = ["PickCube", "StackBlocks", "OpenDoor", "PourWater", "AssemblePeg", "LiftPlate", "InsertPin", "WipeTable"]
    random.seed(99)
    bc_task = [round(random.uniform(30, 75), 1) for _ in tasks]
    dagger_task = [round(bc_task[i] + random.uniform(10, 28), 1) for i in range(len(tasks))]

    bar_rows = ""
    for i, t in enumerate(tasks):
        bc_w = int(bc_task[i] * 2.8)
        dg_w = int(dagger_task[i] * 2.8)
        bar_rows += f"""
        <tr>
          <td style="padding:3px 8px;color:#94a3b8;font-size:12px;white-space:nowrap">{t}</td>
          <td style="padding:3px 8px">
            <div style="background:#334155;border-radius:3px;height:14px;width:280px;position:relative">
              <div style="background:#38bdf8;width:{bc_w}px;height:14px;border-radius:3px;position:absolute"></div>
            </div>
          </td>
          <td style="padding:3px 8px">
            <div style="background:#334155;border-radius:3px;height:14px;width:280px;position:relative">
              <div style="background:#a78bfa;width:{dg_w}px;height:14px;border-radius:3px;position:absolute"></div>
            </div>
          </td>
          <td style="padding:3px 8px;color:#f87171;font-size:12px">+{round(dagger_task[i]-bc_task[i],1)}%</td>
        </tr>"""

    # Action error distribution — simulated MAE per joint
    joints = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3", "gripper"]
    random.seed(55)
    bc_mae = [round(random.uniform(0.04, 0.14), 3) for _ in joints]
    dagger_mae = [round(bc_mae[i] * random.uniform(0.45, 0.72), 3) for i in range(len(joints))]

    mae_rows = ""
    for i, j in enumerate(joints):
        bc_bar = int(bc_mae[i] * 1200)
        dg_bar = int(dagger_mae[i] * 1200)
        improvement = round((1 - dagger_mae[i] / bc_mae[i]) * 100, 1)
        mae_rows += f"""
        <tr>
          <td style="padding:3px 8px;color:#94a3b8;font-size:12px">{j}</td>
          <td style="padding:3px 8px;color:#38bdf8;font-size:12px">{bc_mae[i]}</td>
          <td style="padding:3px 8px;color:#a78bfa;font-size:12px">{dagger_mae[i]}</td>
          <td style="padding:3px 8px">
            <div style="background:#334155;border-radius:3px;height:10px;width:120px;position:relative">
              <div style="background:#4ade80;width:{int(improvement*1.2)}px;height:10px;border-radius:3px"></div>
            </div>
          </td>
          <td style="padding:3px 8px;color:#4ade80;font-size:12px">↓{improvement}%</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><title>Imitation Gap Analyzer</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:22px}}
  h2{{color:#38bdf8;font-size:14px;margin:0 0 12px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px 24px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .card.full{{grid-column:1/-1}}
  .stat{{display:inline-block;margin:0 16px 0 0}}
  .stat .val{{font-size:26px;font-weight:700}}
  .stat .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
  .legend{{display:flex;gap:20px;margin-bottom:12px;font-size:12px}}
  .dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}}
  table{{border-collapse:collapse;width:100%}}
  th{{color:#64748b;font-size:11px;text-align:left;padding:4px 8px;border-bottom:1px solid #334155}}
  .subtitle{{color:#64748b;font-size:12px;margin-top:4px;padding:0 24px 12px}}
</style></head>
<body>
<h1>Imitation Gap Analyzer</h1>
<p class="subtitle">Behavioral Cloning vs. DAgger — covariate shift, action error & task success rate analysis</p>

<div style="padding:0 24px 4px;display:flex;gap:32px">
  <div class="stat"><div class="val" style="color:#38bdf8">{bc_final}%</div><div class="lbl">BC Final Success</div></div>
  <div class="stat"><div class="val" style="color:#a78bfa">{dagger_final}%</div><div class="lbl">DAgger Final Success</div></div>
  <div class="stat"><div class="val" style="color:#f59e0b">{expert_line}%</div><div class="lbl">Expert Performance</div></div>
  <div class="stat"><div class="val" style="color:#f87171">{gap_pct}%</div><div class="lbl">Remaining Gap</div></div>
  <div class="stat"><div class="val" style="color:#4ade80">{round(dagger_final-bc_final,1)}%</div><div class="lbl">DAgger Improvement</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Training Curve — Task Success Rate over Steps</h2>
    <div class="legend">
      <span><span class="dot" style="background:#38bdf8"></span>BC (Behavioral Cloning)</span>
      <span><span class="dot" style="background:#a78bfa"></span>DAgger</span>
      <span><span class="dot" style="background:#f59e0b"></span>Expert Baseline</span>
    </div>
    <svg width="{W}" height="{H}" style="display:block">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      <!-- grid lines -->
      {''.join(f'<line x1="{pad_l}" y1="{sy(t):.1f}" x2="{pad_l+chart_w}" y2="{sy(t):.1f}" stroke="#1e293b" stroke-width="1"/>' for t in range(0,101,20))}
      {yticks_svg}
      {xticks_svg}
      <text x="{pad_l//2}" y="{pad_t + chart_h//2}" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90,{pad_l//2},{pad_t+chart_h//2})">Success %</text>
      <text x="{pad_l + chart_w//2}" y="{H-4}" fill="#64748b" font-size="11" text-anchor="middle">Training Steps</text>
      {expert_svg}
      {expert_label}
      {polyline(bc_vals, '#38bdf8')}
      {polyline(dagger_vals, '#a78bfa')}
    </svg>
  </div>

  <div class="card">
    <h2>Task-Level Success Rate Comparison</h2>
    <table>
      <thead><tr><th>Task</th><th>BC</th><th>DAgger</th><th>Gain</th></tr></thead>
      <tbody>{bar_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Joint-Level Action MAE</h2>
    <table>
      <thead><tr><th>Joint</th><th>BC MAE</th><th>DAgger MAE</th><th>Improvement</th><th></th></tr></thead>
      <tbody>{mae_rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Imitation Gap Analyzer")
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
