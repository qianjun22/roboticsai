"""Continual Learning Tracker — FastAPI service on port 8236.

Tracks catastrophic forgetting and knowledge retention across continual
learning pipelines (BC → DAgger rounds → GR00T fine-tune phases).
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
import json

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TASKS = ["pick_place", "stack", "pour", "wipe", "drawer"]
PHASES = ["BC", "DAgger_r5", "DAgger_r9", "GR00T_v2"]

# Retention matrix [phase_idx][task_idx] — naive fine-tuning
NAIVE_RETENTION = [
    [100.0, 100.0, 100.0, 100.0, 100.0],   # BC (baseline)
    [ 82.0,  85.0,  79.0,  88.0,  61.0],   # DAgger_r5 — drawer worst
    [ 74.0,  77.0,  71.0,  80.0,  55.0],   # DAgger_r9
    [ 77.0,  78.0,  74.0,  83.0,  58.0],   # GR00T_v2
]

# Retention matrix with EWC
EWC_RETENTION = [
    [100.0, 100.0, 100.0, 100.0, 100.0],
    [ 94.0,  95.0,  93.0,  96.0,  88.0],
    [ 92.0,  93.0,  91.0,  94.0,  86.0],
    [ 91.0,  92.0,  90.0,  93.0,  85.0],
]

# Backward / Forward transfer over 5 phases — (naive, ewc) tuples
BACKWARD_TRANSFER = [-0.18, -0.22, -0.26, -0.23, -0.20]  # naive
BACKWARD_EWC      = [-0.04, -0.06, -0.08, -0.07, -0.06]  # EWC
FORWARD_TRANSFER  = [ 0.12,  0.09,  0.11,  0.14,  0.13]  # naive
FORWARD_EWC       = [ 0.15,  0.13,  0.15,  0.17,  0.16]  # EWC

EWC_LAMBDA_OPTIMAL = 5000
EWC_LAMBDA_SWEEP   = [100, 500, 1000, 2000, 5000, 10000, 50000]
EWC_LAMBDA_ACC     = [74.1, 80.3, 84.7, 87.2, 91.4, 90.1, 88.6]  # peak at 5000


def _color_for_retention(pct: float) -> str:
    """Map retention % to a CSS hex color (dark-red → green)."""
    if pct >= 95:
        return "#22c55e"   # green
    elif pct >= 85:
        return "#84cc16"   # lime
    elif pct >= 75:
        return "#eab308"   # yellow
    elif pct >= 65:
        return "#f97316"   # orange
    else:
        return "#dc2626"   # dark red (catastrophic)


def _build_heatmap_svg() -> str:
    cell_w, cell_h = 120, 56
    pad_left, pad_top = 110, 50
    width  = pad_left + cell_w * len(TASKS) + 20
    height = pad_top  + cell_h * len(PHASES) + 40

    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#1e293b" rx="8"/>',
        f'<text x="{width//2}" y="24" fill="#e2e8f0" font-size="14" font-family="monospace"'
        f' text-anchor="middle" font-weight="bold">Task Retention Heatmap — Naive Fine-tuning</text>',
    ]

    # Column headers (tasks)
    for ci, task in enumerate(TASKS):
        x = pad_left + ci * cell_w + cell_w // 2
        parts.append(
            f'<text x="{x}" y="{pad_top - 8}" fill="#94a3b8" font-size="11"'
            f' font-family="monospace" text-anchor="middle">{task}</text>'
        )

    # Row headers (phases) + cells
    for ri, phase in enumerate(PHASES):
        y = pad_top + ri * cell_h
        parts.append(
            f'<text x="{pad_left - 8}" y="{y + cell_h//2 + 5}" fill="#94a3b8"'
            f' font-size="12" font-family="monospace" text-anchor="end">{phase}</text>'
        )
        for ci, task in enumerate(TASKS):
            ret = NAIVE_RETENTION[ri][ci]
            color = _color_for_retention(ret)
            cx = pad_left + ci * cell_w
            cy = y
            parts.append(
                f'<rect x="{cx + 2}" y="{cy + 2}" width="{cell_w - 4}" height="{cell_h - 4}"'
                f' fill="{color}" rx="4" opacity="0.85"/>'
            )
            parts.append(
                f'<text x="{cx + cell_w//2}" y="{cy + cell_h//2 + 5}" fill="#f8fafc"'
                f' font-size="13" font-family="monospace" text-anchor="middle"'
                f' font-weight="bold">{ret:.0f}%</text>'
            )

    # Legend
    legend_items = [
        ("≥95%", "#22c55e"), ("85-95%", "#84cc16"),
        ("75-85%", "#eab308"), ("65-75%", "#f97316"), ("<65%", "#dc2626"),
    ]
    lx = pad_left
    ly = pad_top + len(PHASES) * cell_h + 14
    for label, color in legend_items:
        parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(
            f'<text x="{lx + 18}" y="{ly + 11}" fill="#94a3b8" font-size="11"'
            f' font-family="monospace">{label}</text>'
        )
        lx += 90

    parts.append('</svg>')
    return '\n'.join(parts)


def _build_transfer_svg() -> str:
    phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]
    n = len(phases)
    pad_left, pad_top, pad_bottom = 60, 40, 50
    chart_w, chart_h = 540, 240
    width  = pad_left + chart_w + 40
    height = pad_top  + chart_h + pad_bottom

    # y scale: -0.30 .. +0.20
    y_min, y_max = -0.30, 0.22
    y_range = y_max - y_min

    def to_px(val):
        return pad_top + chart_h - int((val - y_min) / y_range * chart_h)

    def to_x(i):
        return pad_left + int(i / (n - 1) * chart_w)

    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#1e293b" rx="8"/>',
        f'<text x="{width//2}" y="24" fill="#e2e8f0" font-size="14" font-family="monospace"'
        f' text-anchor="middle" font-weight="bold">Backward / Forward Transfer — EWC vs Naive</text>',
    ]

    # Grid lines
    for val in [-0.25, -0.20, -0.15, -0.10, -0.05, 0.00, 0.05, 0.10, 0.15, 0.20]:
        yp = to_px(val)
        color = "#475569" if val != 0.0 else "#64748b"
        parts.append(f'<line x1="{pad_left}" y1="{yp}" x2="{pad_left + chart_w}" y2="{yp}" stroke="{color}" stroke-width="1" stroke-dasharray="4,4"/>')
        parts.append(f'<text x="{pad_left - 6}" y="{yp + 4}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="end">{val:.2f}</text>')

    # x-axis labels
    for i, ph in enumerate(phases):
        xp = to_x(i)
        parts.append(f'<text x="{xp}" y="{pad_top + chart_h + 20}" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">{ph}</text>')

    # Helper to draw a polyline
    def polyline(data_series, color, dash=""):
        pts = " ".join(f"{to_x(i)},{to_px(v)}" for i, v in enumerate(data_series))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"{da} stroke-linejoin="round"/>'

    # Draw lines
    parts.append(polyline(BACKWARD_TRANSFER, "#ef4444", "6,3"))          # BT naive (dashed red)
    parts.append(polyline(BACKWARD_EWC,      "#f97316"))                  # BT EWC (solid orange)
    parts.append(polyline(FORWARD_TRANSFER,  "#38bdf8", "6,3"))           # FT naive (dashed sky)
    parts.append(polyline(FORWARD_EWC,       "#22c55e"))                  # FT EWC (solid green)

    # Dots
    for series, color in [
        (BACKWARD_TRANSFER, "#ef4444"), (BACKWARD_EWC, "#f97316"),
        (FORWARD_TRANSFER,  "#38bdf8"), (FORWARD_EWC,  "#22c55e"),
    ]:
        for i, v in enumerate(series):
            parts.append(f'<circle cx="{to_x(i)}" cy="{to_px(v)}" r="4" fill="{color}"/>')

    # Legend
    legend = [
        ("BT Naive", "#ef4444", "6,3"),
        ("BT EWC",   "#f97316", ""),
        ("FT Naive", "#38bdf8", "6,3"),
        ("FT EWC",   "#22c55e", ""),
    ]
    lx = pad_left
    ly = pad_top + chart_h + 38
    for label, color, dash in legend:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 22}" y2="{ly - 4}" stroke="{color}" stroke-width="2.5"{da}/>')
        parts.append(f'<text x="{lx + 26}" y="{ly}" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>')
        lx += 110

    parts.append('</svg>')
    return '\n'.join(parts)


def _build_html() -> str:
    heatmap_svg  = _build_heatmap_svg()
    transfer_svg = _build_transfer_svg()

    # Summary stats
    avg_naive_final = sum(NAIVE_RETENTION[-1]) / len(NAIVE_RETENTION[-1])
    avg_ewc_final   = sum(EWC_RETENTION[-1])   / len(EWC_RETENTION[-1])
    drawer_naive    = NAIVE_RETENTION[-1][TASKS.index("drawer")]
    drawer_ewc      = EWC_RETENTION[-1][TASKS.index("drawer")]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Continual Learning Tracker — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Menlo', 'Monaco', monospace; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 20px; color: #f8fafc; }}
    header span {{ font-size: 12px; color: #94a3b8; }}
    .badge {{ background: #C74634; color: #fff; font-size: 11px; padding: 2px 8px;
              border-radius: 4px; margin-left: auto; }}
    main {{ padding: 24px 32px; max-width: 1200px; margin: 0 auto; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 16px 20px; }}
    .card .label {{ font-size: 11px; color: #64748b; text-transform: uppercase;
                    letter-spacing: 0.05em; margin-bottom: 6px; }}
    .card .value {{ font-size: 26px; font-weight: bold; }}
    .card .sub   {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
    .green {{ color: #22c55e; }}
    .red   {{ color: #ef4444; }}
    .sky   {{ color: #38bdf8; }}
    .oracle-red {{ color: #C74634; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                      padding: 20px; margin-bottom: 24px; }}
    .chart-section h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 16px;
                         text-transform: uppercase; letter-spacing: 0.05em; }}
    .chart-section svg {{ max-width: 100%; height: auto; }}
    .lambda-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .lambda-table th, .lambda-table td {{ border: 1px solid #334155; padding: 8px 12px; text-align: right; }}
    .lambda-table th {{ background: #0f172a; color: #64748b; }}
    .lambda-table tr:nth-child(even) {{ background: #0f172a; }}
    .highlight-row td {{ color: #22c55e; font-weight: bold; }}
    footer {{ text-align: center; padding: 20px; font-size: 11px; color: #475569; }}
  </style>
</head>
<body>
<header>
  <h1>Continual Learning Tracker</h1>
  <span>OCI Robot Cloud — port 8236</span>
  <div class="badge">LIVE</div>
</header>
<main>
  <div class="metrics">
    <div class="card">
      <div class="label">Avg Retention (Naive)</div>
      <div class="value red">{avg_naive_final:.1f}%</div>
      <div class="sub">After GR00T_v2 phase</div>
    </div>
    <div class="card">
      <div class="label">Avg Retention (EWC)</div>
      <div class="value green">{avg_ewc_final:.1f}%</div>
      <div class="sub">λ = {EWC_LAMBDA_OPTIMAL:,}</div>
    </div>
    <div class="card">
      <div class="label">Drawer Task — Naive</div>
      <div class="value red">{drawer_naive:.0f}%</div>
      <div class="sub">Most prone to forgetting</div>
    </div>
    <div class="card">
      <div class="label">Drawer Task — EWC</div>
      <div class="value green">{drawer_ewc:.0f}%</div>
      <div class="sub">+{drawer_ewc - drawer_naive:.0f}pp vs naive</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Task Retention Heatmap — Naive Fine-tuning</h2>
    {heatmap_svg}
  </div>

  <div class="chart-section">
    <h2>Backward &amp; Forward Transfer — EWC vs Naive</h2>
    {transfer_svg}
  </div>

  <div class="chart-section">
    <h2>EWC Lambda Sweep — Validation Accuracy</h2>
    <table class="lambda-table">
      <thead>
        <tr><th>Lambda</th>{''.join(f'<th>{l}</th>' for l in EWC_LAMBDA_SWEEP)}</tr>
      </thead>
      <tbody>
        <tr class="{'highlight-row' if True else ''}">
          <td style="color:#94a3b8;text-align:left">Acc (%)</td>
          {''.join(f'<td style="color:{"#22c55e" if l == EWC_LAMBDA_OPTIMAL else "#e2e8f0"}; font-weight:{"bold" if l == EWC_LAMBDA_OPTIMAL else "normal"}">{a}</td>' for l, a in zip(EWC_LAMBDA_SWEEP, EWC_LAMBDA_ACC))}
        </tr>
      </tbody>
    </table>
    <p style="font-size:11px;color:#64748b;margin-top:10px">Optimal lambda = <span class="green">{EWC_LAMBDA_OPTIMAL:,}</span> — peak accuracy {max(EWC_LAMBDA_ACC)}%</p>
  </div>
</main>
<footer>OCI Robot Cloud &mdash; Continual Learning Tracker &mdash; port 8236</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Continual Learning Tracker",
        description="Tracks catastrophic forgetting and EWC effectiveness across training phases",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/api/retention")
    async def api_retention():
        return {
            "phases": PHASES,
            "tasks": TASKS,
            "naive_retention": NAIVE_RETENTION,
            "ewc_retention": EWC_RETENTION,
        }

    @app.get("/api/transfer")
    async def api_transfer():
        return {
            "backward_transfer_naive": BACKWARD_TRANSFER,
            "backward_transfer_ewc": BACKWARD_EWC,
            "forward_transfer_naive": FORWARD_TRANSFER,
            "forward_transfer_ewc": FORWARD_EWC,
        }

    @app.get("/api/metrics")
    async def api_metrics():
        avg_naive = sum(NAIVE_RETENTION[-1]) / len(NAIVE_RETENTION[-1])
        avg_ewc   = sum(EWC_RETENTION[-1])   / len(EWC_RETENTION[-1])
        return {
            "avg_retention_naive": round(avg_naive, 2),
            "avg_retention_ewc": round(avg_ewc, 2),
            "ewc_improvement_pp": round(avg_ewc - avg_naive, 2),
            "ewc_lambda_optimal": EWC_LAMBDA_OPTIMAL,
            "worst_task_naive": TASKS[NAIVE_RETENTION[-1].index(min(NAIVE_RETENTION[-1]))],
            "backward_transfer_ewc_mean": round(sum(BACKWARD_EWC) / len(BACKWARD_EWC), 3),
            "forward_transfer_ewc_mean": round(sum(FORWARD_EWC) / len(FORWARD_EWC), 3),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8236, "service": "continual_learning_tracker"}

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8236)
    else:
        print("FastAPI not found — using stdlib http.server on port 8236")
        with socketserver.TCPServer(("", 8236), _Handler) as httpd:
            httpd.serve_forever()
