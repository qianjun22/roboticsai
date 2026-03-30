"""Unified Evaluation Harness — port 8296

Runs all benchmark suites and produces standardized reports.
Provides coverage matrix and cost/duration breakdown dashboards.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

EVAL_DIMENSIONS = [
    "Success Rate",
    "MAE",
    "Latency",
    "Robustness",
    "Transfer",
    "Calibration",
    "Safety",
    "Efficiency",
]

EVAL_SUITES = ["LIBERO", "Custom", "Stress", "Sim2Real", "Partner"]

# 0=missing, 1=partial, 2=covered
COVERAGE_MATRIX = [
    # SR   MAE  Lat  Rob  Trn  Cal  Saf  Eff
    [2,    2,   2,   2,   2,   2,   2,   2],   # LIBERO
    [2,    2,   2,   1,   2,   2,   2,   2],   # Custom
    [2,    1,   2,   2,   1,   1,   2,   2],   # Stress
    [2,    2,   2,   2,   2,   1,   2,   1],   # Sim2Real
    [2,    2,   1,   1,   1,   0,   0,   1],   # Partner
]

# (suite, gpu_hours, wall_hours, cost_usd)
SUITE_COSTS = [
    ("LIBERO",   0.8,  0.8,  3.20),
    ("Custom",   0.9,  0.9,  3.60),
    ("Stress",   0.7,  0.7,  2.80),
    ("Sim2Real", 1.8,  1.8,  7.40),
    ("Partner",  0.0,  0.0,  1.70),  # partner provides compute; licensing cost only
]

TOTAL_GPU_HOURS = sum(c[1] for c in SUITE_COSTS)
TOTAL_WALL_HOURS = sum(c[2] for c in SUITE_COSTS)
TOTAL_COST = sum(c[3] for c in SUITE_COSTS)

KEY_METRICS = {
    "benchmark_coverage_pct": 87,
    "eval_cost_per_dimension": round(TOTAL_COST / len(EVAL_DIMENSIONS), 2),
    "time_to_result_hours": TOTAL_WALL_HOURS,
    "coverage_gaps": ["Partner→Safety", "Partner→Calibration"],
    "recommendation": "Monthly full eval + weekly LIBERO quick; full run every model version before production",
}


def _coverage_color(val: int) -> str:
    return {2: "#22c55e", 1: "#f59e0b", 0: "#ef4444"}[val]


def _coverage_label(val: int) -> str:
    return {2: "Covered", 1: "Partial", 0: "Missing"}[val]


# ---------------------------------------------------------------------------
# SVG 1: Benchmark Coverage Matrix
# ---------------------------------------------------------------------------

def build_coverage_svg() -> str:
    cell_w, cell_h = 90, 46
    left_margin = 120
    top_margin = 90
    cols = len(EVAL_DIMENSIONS)
    rows = len(EVAL_SUITES)
    width = left_margin + cols * cell_w + 40
    height = top_margin + rows * cell_h + 60

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:10px;">',
        f'<text x="{width//2}" y="28" text-anchor="middle" '
        f'fill="#f1f5f9" font-size="15" font-weight="bold" font-family="monospace">'
        f'Benchmark Coverage Matrix</text>',
        f'<text x="{width//2}" y="48" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">'
        f'Overall Coverage: 87% · green=covered · amber=partial · red=missing</text>',
    ]

    # Column headers (eval dimensions)
    for ci, dim in enumerate(EVAL_DIMENSIONS):
        cx = left_margin + ci * cell_w + cell_w // 2
        svg_lines.append(
            f'<text x="{cx}" y="{top_margin - 12}" text-anchor="middle" '
            f'fill="#38bdf8" font-size="10" font-family="monospace" '
            f'transform="rotate(-30,{cx},{top_margin - 12})">{dim}</text>'
        )

    # Row headers (suites) + cells
    for ri, (suite, _, _, _) in enumerate(SUITE_COSTS):
        cy = top_margin + ri * cell_h
        svg_lines.append(
            f'<text x="{left_margin - 8}" y="{cy + cell_h//2 + 4}" '
            f'text-anchor="end" fill="#e2e8f0" font-size="12" font-family="monospace">{suite}</text>'
        )
        for ci, dim in enumerate(EVAL_DIMENSIONS):
            val = COVERAGE_MATRIX[ri][ci]
            color = _coverage_color(val)
            label = _coverage_label(val)
            rx = left_margin + ci * cell_w + 3
            ry = cy + 3
            svg_lines.append(
                f'<rect x="{rx}" y="{ry}" width="{cell_w - 6}" height="{cell_h - 6}" '
                f'rx="5" fill="{color}" opacity="0.25"/>'
            )
            svg_lines.append(
                f'<rect x="{rx}" y="{ry}" width="{cell_w - 6}" height="{cell_h - 6}" '
                f'rx="5" fill="none" stroke="{color}" stroke-width="1.5"/>'
            )
            svg_lines.append(
                f'<text x="{left_margin + ci * cell_w + cell_w//2}" '
                f'y="{cy + cell_h//2 + 4}" text-anchor="middle" '
                f'fill="{color}" font-size="9" font-family="monospace">{label}</text>'
            )

    # Legend
    legend_y = top_margin + rows * cell_h + 30
    for i, (label, color) in enumerate([("Covered", "#22c55e"), ("Partial", "#f59e0b"), ("Missing", "#ef4444")]):
        lx = left_margin + i * 160
        svg_lines.append(
            f'<rect x="{lx}" y="{legend_y - 10}" width="16" height="16" rx="3" fill="{color}" opacity="0.7"/>'
        )
        svg_lines.append(
            f'<text x="{lx + 22}" y="{legend_y + 3}" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>'
        )

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


# ---------------------------------------------------------------------------
# SVG 2: Eval Duration and Cost Breakdown
# ---------------------------------------------------------------------------

def build_cost_svg() -> str:
    bar_height = 32
    bar_gap = 18
    left_margin = 90
    top_margin = 80
    right_margin = 30
    rows = len(SUITE_COSTS)
    width = 720
    height = top_margin + rows * (bar_height * 2 + bar_gap) + 80

    max_gpu = max(c[1] for c in SUITE_COSTS) or 1
    max_cost = max(c[3] for c in SUITE_COSTS) or 1
    bar_max_width = width - left_margin - right_margin - 160

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:10px;">',
        f'<text x="{width//2}" y="28" text-anchor="middle" '
        f'fill="#f1f5f9" font-size="15" font-weight="bold" font-family="monospace">'
        f'Eval Duration &amp; Cost Breakdown</text>',
        f'<text x="{width//2}" y="48" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">'
        f'Total: {TOTAL_GPU_HOURS:.1f} GPU-h · {TOTAL_WALL_HOURS:.1f}h wall-clock · ${TOTAL_COST:.2f} per full run</text>',
    ]

    for ri, (suite, gpu_h, wall_h, cost) in enumerate(SUITE_COSTS):
        base_y = top_margin + ri * (bar_height * 2 + bar_gap)

        # Suite label
        svg_lines.append(
            f'<text x="{left_margin - 8}" y="{base_y + bar_height - 4}" '
            f'text-anchor="end" fill="#e2e8f0" font-size="12" font-family="monospace">{suite}</text>'
        )

        # GPU hours bar
        gpu_w = int(gpu_h / max_gpu * bar_max_width) if max_gpu else 0
        svg_lines.append(
            f'<rect x="{left_margin}" y="{base_y}" width="{gpu_w}" height="{bar_height - 4}" '
            f'rx="4" fill="#38bdf8" opacity="0.75"/>'
        )
        if gpu_w > 0:
            svg_lines.append(
                f'<text x="{left_margin + gpu_w + 6}" y="{base_y + bar_height - 10}" '
                f'fill="#38bdf8" font-size="11" font-family="monospace">{gpu_h:.1f}h GPU</text>'
            )

        # Cost bar
        cost_w = int(cost / max_cost * bar_max_width) if max_cost else 0
        svg_lines.append(
            f'<rect x="{left_margin}" y="{base_y + bar_height}" width="{cost_w}" height="{bar_height - 4}" '
            f'rx="4" fill="#C74634" opacity="0.75"/>'
        )
        if cost_w > 0:
            svg_lines.append(
                f'<text x="{left_margin + cost_w + 6}" y="{base_y + bar_height * 2 - 10}" '
                f'fill="#C74634" font-size="11" font-family="monospace">${cost:.2f}</text>'
            )

    # Legend
    legend_y = top_margin + rows * (bar_height * 2 + bar_gap) + 20
    svg_lines.append(
        f'<rect x="{left_margin}" y="{legend_y}" width="14" height="14" rx="3" fill="#38bdf8" opacity="0.75"/>'
    )
    svg_lines.append(
        f'<text x="{left_margin + 20}" y="{legend_y + 11}" fill="#94a3b8" font-size="11" font-family="monospace">GPU Hours</text>'
    )
    svg_lines.append(
        f'<rect x="{left_margin + 120}" y="{legend_y}" width="14" height="14" rx="3" fill="#C74634" opacity="0.75"/>'
    )
    svg_lines.append(
        f'<text x="{left_margin + 140}" y="{legend_y + 11}" fill="#94a3b8" font-size="11" font-family="monospace">Cost (USD)</text>'
    )

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    coverage_svg = build_coverage_svg()
    cost_svg = build_cost_svg()
    gaps_html = ", ".join(f'<code style="color:#ef4444">{g}</code>' for g in KEY_METRICS["coverage_gaps"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Eval Harness — Port 8296</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', monospace, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
    .metric-card {{ background: #1e293b; border-radius: 10px; padding: 18px; border-left: 4px solid #C74634; }}
    .metric-value {{ font-size: 2rem; font-weight: bold; color: #38bdf8; }}
    .metric-label {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .section-title {{ color: #e2e8f0; font-size: 1.1rem; margin-bottom: 12px; font-weight: 600; }}
    .chart-wrapper {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 28px; overflow-x: auto; }}
    .info-box {{ background: #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 24px; border: 1px solid #334155; }}
    .info-box p {{ color: #cbd5e1; font-size: 0.88rem; line-height: 1.7; }}
    .tag {{ display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-right: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ background: #0f172a; color: #38bdf8; text-align: left; padding: 8px 12px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
    tr:nth-child(even) td {{ background: #172033; }}
  </style>
</head>
<body>
  <h1>Unified Evaluation Harness</h1>
  <p class="subtitle">Port 8296 · Benchmark suites · Standardized reports · Coverage tracking</p>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-value">{KEY_METRICS['benchmark_coverage_pct']}%</div>
      <div class="metric-label">Benchmark Coverage</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${KEY_METRICS['eval_cost_per_dimension']:.2f}</div>
      <div class="metric-label">Cost / Dimension</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{KEY_METRICS['time_to_result_hours']:.1f}h</div>
      <div class="metric-label">Wall Clock (Full Run)</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${TOTAL_COST:.2f}</div>
      <div class="metric-label">Total Cost / Run</div>
    </div>
  </div>

  <div class="section-title">Coverage Matrix (8 Dimensions × 5 Suites)</div>
  <div class="chart-wrapper">{coverage_svg}</div>

  <div class="section-title">Duration &amp; Cost Breakdown per Suite</div>
  <div class="chart-wrapper">{cost_svg}</div>

  <div class="info-box">
    <p><strong style="color:#38bdf8">Coverage Gaps:</strong> {gaps_html}</p>
    <p style="margin-top:10px"><strong style="color:#38bdf8">Recommendation:</strong> {KEY_METRICS['recommendation']}</p>
  </div>

  <div class="section-title">Suite Summary</div>
  <div style="background:#1e293b;border-radius:10px;padding:16px;overflow-x:auto;">
    <table>
      <thead><tr><th>Suite</th><th>GPU Hours</th><th>Wall Hours</th><th>Cost</th><th>Coverage</th></tr></thead>
      <tbody>
        {''.join(f"<tr><td>{s}</td><td>{g:.1f}h</td><td>{w:.1f}h</td><td>${c:.2f}</td><td>{round(sum(COVERAGE_MATRIX[i]) / (2*len(EVAL_DIMENSIONS))*100)}%</td></tr>" for i,(s,g,w,c) in enumerate(SUITE_COSTS))}
      </tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Eval Harness",
        description="Unified evaluation harness — all benchmark suites and standardized reports",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_harness", "port": 8296}

    @app.get("/metrics")
    async def metrics():
        return {
            "benchmark_coverage_pct": KEY_METRICS["benchmark_coverage_pct"],
            "total_cost_usd": TOTAL_COST,
            "total_wall_hours": TOTAL_WALL_HOURS,
            "total_gpu_hours": TOTAL_GPU_HOURS,
            "eval_dimensions": EVAL_DIMENSIONS,
            "eval_suites": EVAL_SUITES,
            "coverage_gaps": KEY_METRICS["coverage_gaps"],
            "recommendation": KEY_METRICS["recommendation"],
        }

    @app.get("/coverage")
    async def coverage():
        result = {}
        for ri, (suite, _, _, _) in enumerate(SUITE_COSTS):
            result[suite] = {
                dim: _coverage_label(COVERAGE_MATRIX[ri][ci])
                for ci, dim in enumerate(EVAL_DIMENSIONS)
            }
        return result

    @app.get("/run")
    async def run_eval(suite: str = "all"):
        """Simulate triggering an eval run."""
        if suite == "all":
            selected = list(EVAL_SUITES)
        elif suite in EVAL_SUITES:
            selected = [suite]
        else:
            return {"error": f"Unknown suite: {suite}", "available": EVAL_SUITES}
        estimated_cost = sum(c[3] for s, *_, c in SUITE_COSTS if s in selected)
        return {
            "status": "queued",
            "suites": selected,
            "estimated_cost_usd": estimated_cost,
            "run_id": f"eval-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        }

else:
    # Stdlib fallback
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
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
        uvicorn.run(app, host="0.0.0.0", port=8296)
    else:
        server = http.server.HTTPServer(("0.0.0.0", 8296), _Handler)
        print("Eval Harness running on http://0.0.0.0:8296 (stdlib fallback)")
        server.serve_forever()
