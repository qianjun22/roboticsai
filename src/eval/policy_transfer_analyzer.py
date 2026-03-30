"""Policy Transfer Analyzer — FastAPI service on port 8286.

Analyzes how well policies transfer across task variants and environment changes.
Fallback to stdlib http.server if FastAPI/uvicorn are not installed.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TASKS = ["pick_place", "stack", "grasp", "pour", "handover", "sweep"]

# Zero-shot transfer success rate matrix (source row → target col)
# Diagonal = training SR on source task
TRANSFER_MATRIX = {
    "pick_place": {"pick_place": 0.82, "stack": 0.77, "grasp": 0.61, "pour": 0.44, "handover": 0.39, "sweep": 0.35},
    "stack":      {"pick_place": 0.68, "stack": 0.79, "grasp": 0.55, "pour": 0.38, "handover": 0.33, "sweep": 0.30},
    "grasp":      {"pick_place": 0.57, "stack": 0.51, "grasp": 0.85, "pour": 0.58, "handover": 0.49, "sweep": 0.42},
    "pour":       {"pick_place": 0.41, "stack": 0.38, "pour": 0.80, "grasp": 0.47, "handover": 0.31, "sweep": 0.27},
    "handover":   {"pick_place": 0.44, "stack": 0.40, "grasp": 0.53, "pour": 0.34, "handover": 0.78, "sweep": 0.36},
    "sweep":      {"pick_place": 0.38, "stack": 0.34, "grasp": 0.45, "pour": 0.29, "handover": 0.32, "sweep": 0.76},
}

# Few-shot adaptation: SR vs number of target-domain demos
FEW_SHOT_POLICIES = [
    {"name": "GR00T_v2",    "color": "#C74634", "plateau": 0.81, "demos_to_plateau": 40,  "slope_factor": 3.0},
    {"name": "OpenVLA",     "color": "#38bdf8", "plateau": 0.76, "demos_to_plateau": 70,  "slope_factor": 2.0},
    {"name": "Diffusion",   "color": "#a78bfa", "plateau": 0.72, "demos_to_plateau": 90,  "slope_factor": 1.6},
    {"name": "ACT",         "color": "#34d399", "plateau": 0.68, "demos_to_plateau": 100, "slope_factor": 1.3},
    {"name": "BC",          "color": "#fbbf24", "plateau": 0.61, "demos_to_plateau": 120, "slope_factor": 1.0},
]

KEY_METRICS = {
    "zero_shot_avg_transfer_pct": 62,
    "best_pair": "pick_place → stack (94% of source SR)",
    "worst_pair": "pour → handover (31% transfer)",
    "groot_v2_demos_to_target": 40,
    "bc_demos_to_target": 120,
    "slope_ratio": "3×",
    "diagonal_correlation": 0.94,
}

# ---------------------------------------------------------------------------
# SVG generation helpers
# ---------------------------------------------------------------------------

def _color_for_sr(sr: float) -> str:
    """Map SR [0,1] to a color from cold-blue to warm-red."""
    # low → #1e3a5f, high → #C74634
    r_low, g_low, b_low = 0x1e, 0x3a, 0x5f
    r_hi,  g_hi,  b_hi  = 0xC7, 0x46, 0x34
    t = max(0.0, min(1.0, sr))
    r = int(r_low + t * (r_hi - r_low))
    g = int(g_low + t * (g_hi - g_low))
    b = int(b_low + t * (b_hi - b_low))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_transfer_heatmap_svg() -> str:
    cell = 70
    label_w = 90
    label_h = 50
    n = len(TASKS)
    width  = label_w + n * cell + 20
    height = label_h + n * cell + 40

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="background:#0f172a;font-family:monospace">']

    # Title
    lines.append(f'<text x="{width//2}" y="20" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">Zero-Shot Transfer Matrix (Success Rate)</text>')

    # Column headers (target tasks)
    for ci, task in enumerate(TASKS):
        x = label_w + ci * cell + cell // 2
        lines.append(f'<text x="{x}" y="{label_h - 6}" fill="#94a3b8" font-size="10" '
                     f'text-anchor="middle" transform="rotate(-30,{x},{label_h-6})">{task}</text>')

    for ri, src in enumerate(TASKS):
        # Row label (source task)
        y_mid = label_h + ri * cell + cell // 2
        lines.append(f'<text x="{label_w - 6}" y="{y_mid + 4}" fill="#94a3b8" font-size="10" '
                     f'text-anchor="end">{src}</text>')

        for ci, tgt in enumerate(TASKS):
            sr = TRANSFER_MATRIX[src].get(tgt, 0.0)
            color = _color_for_sr(sr)
            x = label_w + ci * cell
            y = label_h + ri * cell
            # Diagonal gets a gold border
            border = ' stroke="#fbbf24" stroke-width="2"' if ri == ci else ' stroke="#1e293b" stroke-width="1"'
            lines.append(f'<rect x="{x}" y="{y}" width="{cell-2}" height="{cell-2}" '
                         f'fill="{color}"{border}/>')
            lines.append(f'<text x="{x + cell//2 - 1}" y="{y + cell//2 + 4}" fill="#f1f5f9" '
                         f'font-size="11" text-anchor="middle">{sr:.2f}</text>')

    # Legend
    leg_x = label_w
    leg_y = label_h + n * cell + 15
    for i, (label, sr) in enumerate([("0.0", 0.0), ("0.25", 0.25), ("0.5", 0.5), ("0.75", 0.75), ("1.0", 1.0)]):
        lx = leg_x + i * 80
        lines.append(f'<rect x="{lx}" y="{leg_y}" width="16" height="16" fill="{_color_for_sr(sr)}"/>')
        lines.append(f'<text x="{lx+20}" y="{leg_y+12}" fill="#94a3b8" font-size="10">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def build_few_shot_curve_svg() -> str:
    width, height = 620, 340
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    max_demos = 140
    demo_ticks = list(range(0, max_demos + 1, 20))
    sr_ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="background:#0f172a;font-family:monospace">']

    lines.append(f'<text x="{width//2}" y="18" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">Few-Shot Adaptation Curves</text>')

    # Grid lines
    for sr in sr_ticks:
        y = pad_t + plot_h - int(sr * plot_h)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{pad_l+plot_w}" y2="{y}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+4}" fill="#64748b" font-size="10" text-anchor="end">{sr:.1f}</text>')

    for d in demo_ticks:
        x = pad_l + int(d / max_demos * plot_w)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t+plot_h}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{d}</text>')

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<text x="{width//2}" y="{height-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Target-Domain Demos</text>')
    lines.append(f'<text x="14" y="{pad_t+plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" '
                 f'transform="rotate(-90,14,{pad_t+plot_h//2})">Success Rate</text>')

    # Curves — logistic growth model
    demo_steps = list(range(0, max_demos + 1, 2))
    for pol in FEW_SHOT_POLICIES:
        k = pol["slope_factor"] * 0.05   # growth rate
        mid = pol["demos_to_plateau"] / 2.0
        pts = []
        for d in demo_steps:
            sr = pol["plateau"] / (1.0 + math.exp(-k * (d - mid)))
            sr = max(0.0, min(1.0, sr))
            x = pad_l + int(d / max_demos * plot_w)
            y = pad_t + plot_h - int(sr * plot_h)
            pts.append(f"{x},{y}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{pol["color"]}" stroke-width="2.5"/>')
        # Legend dot + label on right
        last_x, last_y = map(int, pts[-1].split(','))
        lines.append(f'<circle cx="{last_x+4}" cy="{last_y}" r="4" fill="{pol["color"]}"/>')

    # Legend block
    leg_x, leg_y = pad_l + 10, pad_t + 8
    for i, pol in enumerate(FEW_SHOT_POLICIES):
        lx = leg_x
        ly = leg_y + i * 20
        lines.append(f'<rect x="{lx}" y="{ly}" width="14" height="4" fill="{pol[\"color\"]}"/>')
        lines.append(f'<text x="{lx+18}" y="{ly+5}" fill="#cbd5e1" font-size="10">{pol["name"]} '
                     f'(plateau {pol["demos_to_plateau"]} demos)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_dashboard_html() -> str:
    heatmap_svg  = build_transfer_heatmap_svg()
    fewshot_svg  = build_few_shot_curve_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    m  = KEY_METRICS

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Policy Transfer Analyzer — Port 8286</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 28px; }}
    .card {{
      background: #1e293b; border: 1px solid #334155; border-radius: 8px;
      padding: 16px 20px; min-width: 180px; flex: 1;
    }}
    .card .val {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
    .section {{ margin-bottom: 36px; }}
    .section h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    .svg-wrap {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; overflow-x: auto; }}
    .rec-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .rec-table th {{ background: #1e293b; color: #94a3b8; padding: 8px 12px; text-align: left; }}
    .rec-table td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
    .rec-table tr:hover td {{ background: #1e3a5f; }}
    .badge {{ display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <h1>Policy Transfer Analyzer</h1>
  <div class="sub">Measures cross-task zero-shot transfer and few-shot adaptation speed &mdash; Port 8286 &mdash; {ts}</div>

  <div class="metrics">
    <div class="card"><div class="val">{m['zero_shot_avg_transfer_pct']}%</div><div class="lbl">Avg Zero-Shot Transfer</div></div>
    <div class="card"><div class="val">{m['slope_ratio']}</div><div class="lbl">GR00T_v2 vs BC Slope</div></div>
    <div class="card"><div class="val">{m['groot_v2_demos_to_target']}</div><div class="lbl">GR00T_v2 Demos to Target SR</div></div>
    <div class="card"><div class="val">{m['bc_demos_to_target']}</div><div class="lbl">BC Demos to Target SR</div></div>
    <div class="card"><div class="val">{m['diagonal_correlation']}</div><div class="lbl">Diagonal Correlation</div></div>
  </div>

  <div class="section">
    <h2>Transfer Matrix Heatmap (Zero-Shot SR)</h2>
    <div class="svg-wrap">{heatmap_svg}</div>
    <p style="color:#64748b;font-size:0.8rem;margin-top:8px">
      Rows = source training task &nbsp;|&nbsp; Cols = target evaluation task &nbsp;|&nbsp;
      Diagonal (gold border) = in-domain training SR &nbsp;|&nbsp;
      Best pair: <span style="color:#C74634">pick_place &rarr; stack (0.77)</span> &nbsp;|&nbsp;
      Worst pair: <span style="color:#38bdf8">pour &rarr; handover (0.31)</span>
    </p>
  </div>

  <div class="section">
    <h2>Few-Shot Adaptation Curves</h2>
    <div class="svg-wrap">{fewshot_svg}</div>
    <p style="color:#64748b;font-size:0.8rem;margin-top:8px">
      GR00T_v2 reaches plateau in <strong style="color:#C74634">{m['groot_v2_demos_to_target']} demos</strong>
      vs BC&apos;s {m['bc_demos_to_target']} &mdash; a <strong style="color:#38bdf8">{m['slope_ratio']}</strong> steeper learning slope.
    </p>
  </div>

  <div class="section">
    <h2>Recommended Source Tasks per Transfer Target</h2>
    <table class="rec-table">
      <thead><tr><th>Target Task</th><th>Best Source</th><th>Transfer SR</th><th>Pct of Source SR</th><th>Recommendation</th></tr></thead>
      <tbody>
        <tr><td>stack</td><td>pick_place</td><td>0.77</td><td>94%</td><td><span class="badge">Strong</span></td></tr>
        <tr><td>pour</td><td>grasp</td><td>0.58</td><td>68%</td><td><span class="badge" style="background:#38bdf8;color:#0f172a">Good</span></td></tr>
        <tr><td>grasp</td><td>grasp (self)</td><td>0.85</td><td>100%</td><td><span class="badge" style="background:#34d399;color:#0f172a">Train direct</span></td></tr>
        <tr><td>handover</td><td>pour</td><td>0.31</td><td>39%</td><td><span class="badge" style="background:#475569">Few-shot needed</span></td></tr>
        <tr><td>sweep</td><td>grasp</td><td>0.42</td><td>49%</td><td><span class="badge" style="background:#475569">Few-shot needed</span></td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app  (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Policy Transfer Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_dashboard_html())

    @app.get("/api/transfer-matrix")
    async def transfer_matrix():
        return {"tasks": TASKS, "matrix": TRANSFER_MATRIX}

    @app.get("/api/few-shot")
    async def few_shot_data():
        return {"policies": FEW_SHOT_POLICIES}

    @app.get("/api/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_transfer_analyzer", "port": 8286}

else:
    # Stdlib fallback
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):  # suppress default logs
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8286)
    else:
        PORT = 8286
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback — install fastapi+uvicorn for full API)")
            httpd.serve_forever()
