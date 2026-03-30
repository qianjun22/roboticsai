# DAgger Efficiency Analyzer — port 8914
# Analyzes SR gain per DAgger round, sample efficiency vs BC, intervention rate trend

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

TITLE = "DAgger Efficiency Analyzer"
PORT = 8914

# --- Data ---
ROUNDS = [1, 2, 3, 4, 5, 6]
SR_BY_ROUND = [0.22, 0.41, 0.57, 0.67, 0.73, 0.77]          # success rate after each DAgger round
BC_SR = 0.18                                                   # baseline BC success rate
INTERVENTION_RATE = [0.61, 0.52, 0.43, 0.34, 0.25, 0.18]    # human intervention rate per round
# Sample efficiency: demos needed to reach same SR as DAgger round N via BC-only
BC_EQUIV_DEMOS = [880, 1640, 2300, 2700, 3100, 3400]         # BC demos needed for equivalent SR
DAGGER_DEMOS  = [200,  410,  620,  810, 1000, 1200]          # cumulative DAgger demos


def _spark_polyline(values, x0, y0, w, h, color, stroke=2):
    """Return an SVG polyline for a list of values in a bounding box."""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        px = x0 + (i / (n - 1)) * w
        py = y0 + h - ((v - mn) / rng) * h
        pts.append(f"{px:.1f},{py:.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linejoin="round" stroke-linecap="round"/>'


def build_html() -> str:
    # ---- Round Efficiency Curve SVG ----
    cw, ch = 560, 240
    pad_l, pad_r, pad_t, pad_b = 52, 20, 20, 40
    gw = cw - pad_l - pad_r
    gh = ch - pad_t - pad_b

    def rx(i):  # round index 0-5 → svg x
        return pad_l + (i / (len(ROUNDS) - 1)) * gw

    def sr_y(v):
        return pad_t + gh - v * gh

    # SR curve
    sr_pts = " ".join(f"{rx(i):.1f},{sr_y(SR_BY_ROUND[i]):.1f}" for i in range(len(ROUNDS)))
    # Intervention rate (secondary axis, same 0-1 scale)
    iv_pts = " ".join(f"{rx(i):.1f},{sr_y(INTERVENTION_RATE[i]):.1f}" for i in range(len(ROUNDS)))

    sr_dots = "".join(
        f'<circle cx="{rx(i):.1f}" cy="{sr_y(SR_BY_ROUND[i]):.1f}" r="5" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>'
        for i in range(len(ROUNDS))
    )
    iv_dots = "".join(
        f'<circle cx="{rx(i):.1f}" cy="{sr_y(INTERVENTION_RATE[i]):.1f}" r="4" fill="#f97316" stroke="#0f172a" stroke-width="1.5"/>'
        for i in range(len(ROUNDS))
    )
    # Y-axis ticks
    y_ticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        yy = sr_y(v)
        y_ticks += f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l + gw}" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        y_ticks += f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.1f}</text>'
    # X-axis labels
    x_labels = "".join(
        f'<text x="{rx(i):.1f}" y="{pad_t + gh + 18}" fill="#94a3b8" font-size="11" text-anchor="middle">R{ROUNDS[i]}</text>'
        for i in range(len(ROUNDS))
    )
    # SR gain annotations
    gain_labels = ""
    for i in range(1, len(ROUNDS)):
        gain = SR_BY_ROUND[i] - SR_BY_ROUND[i - 1]
        mx_ = (rx(i - 1) + rx(i)) / 2
        my_ = (sr_y(SR_BY_ROUND[i - 1]) + sr_y(SR_BY_ROUND[i])) / 2 - 10
        gain_labels += f'<text x="{mx_:.1f}" y="{my_:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle">+{gain:.2f}</text>'

    round_svg = f"""<svg width="{cw}" height="{ch}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
  <!-- grid -->
  {y_ticks}
  <!-- lines -->
  <polyline points="{iv_pts}" fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="6 3" stroke-linejoin="round"/>
  <polyline points="{sr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
  {sr_dots}{iv_dots}
  {gain_labels}
  {x_labels}
  <!-- BC baseline -->
  <line x1="{pad_l}" y1="{sr_y(BC_SR):.1f}" x2="{pad_l + gw}" y2="{sr_y(BC_SR):.1f}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text x="{pad_l + gw - 2}" y="{sr_y(BC_SR) - 5:.1f}" fill="#ef4444" font-size="10" text-anchor="end">BC baseline {BC_SR:.2f}</text>
  <!-- legend -->
  <rect x="{pad_l + 4}" y="{pad_t + 4}" width="12" height="3" fill="#38bdf8"/>
  <text x="{pad_l + 20}" y="{pad_t + 10}" fill="#38bdf8" font-size="10">Success Rate</text>
  <rect x="{pad_l + 100}" y="{pad_t + 4}" width="12" height="3" fill="#f97316"/>
  <text x="{pad_l + 116}" y="{pad_t + 10}" fill="#f97316" font-size="10">Intervention Rate</text>
  <text x="{cw // 2}" y="{ch - 4}" fill="#64748b" font-size="10" text-anchor="middle">DAgger Round</text>
</svg>"""

    # ---- Sample Efficiency SVG ----
    ew, eh = 560, 220
    ep_l, ep_r, ep_t, ep_b = 60, 20, 20, 40
    egw = ew - ep_l - ep_r
    egh = eh - ep_t - ep_b
    max_demos = max(max(BC_EQUIV_DEMOS), max(DAGGER_DEMOS))

    def ex(demos):
        return ep_l + (demos / max_demos) * egw

    def ey(sr_val):
        return ep_t + egh - sr_val * egh

    bc_pts = " ".join(f"{ex(BC_EQUIV_DEMOS[i]):.1f},{ey(SR_BY_ROUND[i]):.1f}" for i in range(len(ROUNDS)))
    dag_pts = " ".join(f"{ex(DAGGER_DEMOS[i]):.1f},{ey(SR_BY_ROUND[i]):.1f}" for i in range(len(ROUNDS)))

    e_y_ticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8]:
        yy = ey(v)
        e_y_ticks += f'<line x1="{ep_l}" y1="{yy:.1f}" x2="{ep_l + egw}" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        e_y_ticks += f'<text x="{ep_l - 6}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.1f}</text>'

    e_x_ticks = ""
    for d in [0, 500, 1000, 1500, 2000, 2500, 3000, 3400]:
        xx = ex(d)
        e_x_ticks += f'<line x1="{xx:.1f}" y1="{ep_t}" x2="{xx:.1f}" y2="{ep_t + egh}" stroke="#1e293b" stroke-width="1"/>'
        e_x_ticks += f'<text x="{xx:.1f}" y="{ep_t + egh + 16}" fill="#94a3b8" font-size="9" text-anchor="middle">{d}</text>'

    eff_svg = f"""<svg width="{ew}" height="{eh}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
  {e_y_ticks}{e_x_ticks}
  <polyline points="{bc_pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>
  <polyline points="{dag_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
  {''.join(f'<circle cx="{ex(BC_EQUIV_DEMOS[i]):.1f}" cy="{ey(SR_BY_ROUND[i]):.1f}" r="4" fill="#C74634"/>' for i in range(len(ROUNDS)))}
  {''.join(f'<circle cx="{ex(DAGGER_DEMOS[i]):.1f}" cy="{ey(SR_BY_ROUND[i]):.1f}" r="4" fill="#38bdf8"/>' for i in range(len(ROUNDS)))}
  <!-- efficiency label at 0.70 SR level -->
  <line x1="{ex(0):.1f}" y1="{ey(0.70):.1f}" x2="{ep_l + egw}" y2="{ey(0.70):.1f}" stroke="#facc15" stroke-width="1" stroke-dasharray="5 3"/>
  <text x="{ep_l + egw - 2}" y="{ey(0.70) - 4:.1f}" fill="#facc15" font-size="10" text-anchor="end">SR=0.70 threshold</text>
  <!-- legend -->
  <rect x="{ep_l + 4}" y="{ep_t + 4}" width="12" height="3" fill="#38bdf8"/>
  <text x="{ep_l + 20}" y="{ep_t + 10}" fill="#38bdf8" font-size="10">DAgger demos</text>
  <rect x="{ep_l + 110}" y="{ep_t + 4}" width="12" height="3" fill="#C74634"/>
  <text x="{ep_l + 126}" y="{ep_t + 10}" fill="#C74634" font-size="10">BC-equivalent demos</text>
  <text x="{ew // 2}" y="{eh - 4}" fill="#64748b" font-size="10" text-anchor="middle">Cumulative Demonstrations</text>
  <text x="{ep_l - 40}" y="{ep_t + egh // 2}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 {ep_l - 40} {ep_t + egh // 2})">Success Rate</text>
</svg>"""

    # ---- Efficiency ratio table ----
    rows = ""
    for i in range(len(ROUNDS)):
        ratio = BC_EQUIV_DEMOS[i] / DAGGER_DEMOS[i]
        rows += f"""<tr style="border-bottom:1px solid #1e293b">
          <td style="padding:6px 12px;color:#94a3b8">Round {ROUNDS[i]}</td>
          <td style="padding:6px 12px;color:#38bdf8">{SR_BY_ROUND[i]:.2f}</td>
          <td style="padding:6px 12px;color:#f97316">{INTERVENTION_RATE[i]:.0%}</td>
          <td style="padding:6px 12px;color:#a3e635">{DAGGER_DEMOS[i]}</td>
          <td style="padding:6px 12px;color:#C74634">{BC_EQUIV_DEMOS[i]}</td>
          <td style="padding:6px 12px;color:#facc15;font-weight:600">{ratio:.1f}×</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{TITLE}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 28px; }}
    h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 1.1rem; margin: 28px 0 12px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .stat-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .stat {{ background: #1e293b; border-radius: 8px; padding: 16px 22px; min-width: 160px; }}
    .stat-val {{ font-size: 1.6rem; font-weight: 700; }}
    .stat-lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th {{ text-align: left; padding: 8px 12px; color: #64748b; font-weight: 500; border-bottom: 2px solid #1e293b; }}
    tr:hover {{ background: #0f172a33; }}
    .port-badge {{ float: right; background: #1e293b; color: #38bdf8; font-size: 0.75rem; padding: 4px 10px; border-radius: 20px; }}
  </style>
</head>
<body>
  <h1>{TITLE} <span class="port-badge">:{PORT}</span></h1>
  <p class="subtitle">SR gain per DAgger round · sample efficiency vs BC · intervention rate trend</p>

  <div class="stat-row">
    <div class="stat"><div class="stat-val" style="color:#38bdf8">0.77</div><div class="stat-lbl">SR after Round 6</div></div>
    <div class="stat"><div class="stat-val" style="color:#a3e635">4.3×</div><div class="stat-lbl">Sample efficiency vs BC (R4)</div></div>
    <div class="stat"><div class="stat-val" style="color:#f97316">18%</div><div class="stat-lbl">Intervention rate Round 6</div></div>
    <div class="stat"><div class="stat-val" style="color:#C74634">0.59</div><div class="stat-lbl">Total SR gain (R1→R6)</div></div>
  </div>

  <h2>Round Efficiency Curve</h2>
  <div class="card" style="overflow-x:auto">{round_svg}</div>

  <h2>Sample Efficiency: DAgger vs BC-Equivalent Demonstrations</h2>
  <div class="card" style="overflow-x:auto">{eff_svg}</div>

  <h2>Per-Round Breakdown</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Round</th><th style="color:#38bdf8">Success Rate</th><th style="color:#f97316">Intervention Rate</th>
        <th style="color:#a3e635">DAgger Demos</th><th style="color:#C74634">BC Equiv Demos</th><th style="color:#facc15">Efficiency Ratio</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <p style="color:#334155;font-size:0.78rem;margin-top:8px">OCI Robot Cloud · DAgger Efficiency Analyzer · port {PORT}</p>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    @app.get("/api/data")
    async def api_data():
        return {
            "rounds": ROUNDS,
            "sr_by_round": SR_BY_ROUND,
            "intervention_rate": INTERVENTION_RATE,
            "dagger_demos": DAGGER_DEMOS,
            "bc_equiv_demos": BC_EQUIV_DEMOS,
            "bc_baseline_sr": BC_SR,
        }

else:
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
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{TITLE}] FastAPI unavailable — serving on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
