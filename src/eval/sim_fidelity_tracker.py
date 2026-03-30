"""sim_fidelity_tracker.py — FastAPI service on port 8213.

Tracks simulation-to-reality fidelity metrics for Isaac Sim environments.
Cycle-38A: OCI Robot Cloud sim-to-real fidelity dashboard.
"""

from __future__ import annotations

import math
import random
from typing import List, Dict, Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Mock data (stdlib only)
# ---------------------------------------------------------------------------

# 6 fidelity dimensions: sim vs real scores (0-100)
FIDELITY_DIMS: List[str] = [
    "Physics Accuracy",
    "Visual Realism",
    "Contact Modeling",
    "Friction",
    "Inertia",
    "Sensor Noise",
]

SIM_SCORES: List[float] = [87.0, 71.0, 79.0, 82.0, 84.0, 68.0]   # sim fidelity %
REAL_BASELINE: List[float] = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]  # real world reference


def _generate_task_variants(n: int = 20) -> List[Dict[str, Any]]:
    """20 task variants with sim_success_rate and real_success_rate."""
    random.seed(77)
    tasks = []
    for i in range(n):
        # Correlated sim/real rates (r ≈ 0.83) with some scatter
        sim_base = 0.25 + 0.60 * random.random()
        noise = random.gauss(0, 0.08)
        real_base = 0.15 + 0.72 * sim_base + noise
        real_base = max(0.05, min(0.95, real_base))
        tasks.append({
            "task_id": i + 1,
            "task_name": f"task_variant_{i + 1:02d}",
            "sim_success_rate": round(sim_base, 3),
            "real_success_rate": round(real_base, 3),
            "gap": round(sim_base - real_base, 3),
        })
    return tasks


TASK_VARIANTS: List[Dict[str, Any]] = _generate_task_variants(20)


def _pearson_r(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy + 1e-12)


def _compute_metrics() -> Dict[str, Any]:
    gaps = [abs(t["gap"]) for t in TASK_VARIANTS]
    avg_gap = sum(gaps) / len(gaps)
    fidelity_gap_score = 1.0 - avg_gap
    xs = [t["sim_success_rate"] for t in TASK_VARIANTS]
    ys = [t["real_success_rate"] for t in TASK_VARIANTS]
    r = _pearson_r(xs, ys)
    # Lowest fidelity dim → highest impact improvement target
    min_idx = SIM_SCORES.index(min(SIM_SCORES))
    transfer_readiness = "HIGH" if r > 0.80 and fidelity_gap_score > 0.75 else "MEDIUM"
    return {
        "fidelity_gap_score": round(fidelity_gap_score, 3),
        "sim_real_correlation_r": round(r, 3),
        "highest_impact_dimension": FIDELITY_DIMS[min_idx],
        "lowest_fidelity_score_pct": SIM_SCORES[min_idx],
        "transfer_learning_readiness": transfer_readiness,
        "average_sim_real_gap": round(avg_gap, 3),
        "num_task_variants": len(TASK_VARIANTS),
    }


# ---------------------------------------------------------------------------
# SVG chart builders
# ---------------------------------------------------------------------------

def _svg_radar_chart(width: int = 520, height: int = 380) -> str:
    """Hexagonal radar chart comparing 6 fidelity dimensions: sim vs real."""
    cx, cy = width // 2, height // 2 - 10
    r_max = min(cx, cy) - 60
    n = len(FIDELITY_DIMS)
    colors_sim = "#38bdf8"
    colors_real = "#C74634"

    def angle(i): return math.pi / 2 - 2 * math.pi * i / n  # start top

    def point(val_pct, i):
        r = r_max * val_pct / 100.0
        a = angle(i)
        return (cx + r * math.cos(a), cy - r * math.sin(a))

    # Grid rings
    rings = ""
    for level in [25, 50, 75, 100]:
        pts = " ".join(f"{cx + r_max * level / 100 * math.cos(angle(i)):.1f},{cy - r_max * level / 100 * math.sin(angle(i)):.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#1e3a5f" stroke-width="1" />'
        # Label
        rings += f'<text x="{cx + 4}" y="{cy - r_max * level / 100 - 3:.1f}" fill="#334155" font-size="10">{level}%</text>'

    # Spokes
    spokes = ""
    for i in range(n):
        ox, oy = point(100, i)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{ox:.1f}" y2="{oy:.1f}" stroke="#1e3a5f" stroke-width="1" />'

    def poly_path(scores):
        pts = " ".join(f"{point(s, i)[0]:.1f},{point(s, i)[1]:.1f}" for i, s in enumerate(scores))
        return pts

    real_poly = poly_path(REAL_BASELINE)
    sim_poly = poly_path(SIM_SCORES)

    # Dim labels
    dim_labels = ""
    for i, dim in enumerate(FIDELITY_DIMS):
        lx, ly = point(115, i)
        anchor = "middle"
        if lx < cx - 10: anchor = "end"
        elif lx > cx + 10: anchor = "start"
        dim_labels += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="#94a3b8" font-size="11" font-weight="500">{dim}</text>'
        # Score dot
        sx, sy = point(SIM_SCORES[i], i)
        dim_labels += f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" fill="{colors_sim}" />'

    legend = (
        f'<polygon points="10,{height - 22} 22,{height - 22} 16,{height - 10}" fill="{colors_real}" fill-opacity="0.4" />'
        f'<text x="26" y="{height - 12}" fill="#94a3b8" font-size="11">Real World (100%)</text>'
        f'<polygon points="160,{height - 22} 172,{height - 22} 166,{height - 10}" fill="{colors_sim}" fill-opacity="0.5" />'
        f'<text x="176" y="{height - 12}" fill="#94a3b8" font-size="11">Isaac Sim Fidelity</text>'
    )

    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="8" />
  <text x="{width // 2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Sim Fidelity Radar — 6 Dimensions vs Real World</text>
  {rings}
  {spokes}
  <polygon points="{real_poly}" fill="#C74634" fill-opacity="0.18" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3" />
  <polygon points="{sim_poly}" fill="#38bdf8" fill-opacity="0.30" stroke="#38bdf8" stroke-width="2" />
  {dim_labels}
  {legend}
</svg>"""
    return svg


def _svg_scatter_plot(data: List[Dict[str, Any]], width: int = 580, height: int = 340) -> str:
    """Scatter plot: sim vs real success rates across 20 task variants + correlation line."""
    pad_l, pad_r, pad_t, pad_b = 55, 20, 28, 45
    W = width - pad_l - pad_r
    H = height - pad_t - pad_b

    def xp(v): return pad_l + v * W
    def yp(v): return pad_t + H - v * H

    # Compute linear regression line
    xs = [t["sim_success_rate"] for t in data]
    ys = [t["real_success_rate"] for t in data]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (sum((x - mx) ** 2 for x in xs) + 1e-12)
    intercept = my - slope * mx

    # Line endpoints
    x0, x1 = 0.1, 0.95
    y0, y1 = slope * x0 + intercept, slope * x1 + intercept
    corr_line = f'<line x1="{xp(x0):.1f}" y1="{yp(y0):.1f}" x2="{xp(x1):.1f}" y2="{yp(y1):.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3" />'
    r_val = _pearson_r(xs, ys)
    corr_label = f'<text x="{xp(x1) - 4:.1f}" y="{yp(y1) - 8:.1f}" fill="#f59e0b" font-size="11" text-anchor="end">r = {r_val:.2f}</text>'

    # Dots
    dots = ""
    for t in data:
        dx = xp(t["sim_success_rate"])
        dy = yp(t["real_success_rate"])
        gap = abs(t["gap"])
        color = "#4ade80" if gap < 0.08 else ("#f59e0b" if gap < 0.15 else "#C74634")
        dots += f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="5" fill="{color}" fill-opacity="0.85" stroke="#0f172a" stroke-width="0.5" />'

    # Diagonal parity line (sim == real)
    parity = f'<line x1="{xp(0):.1f}" y1="{yp(0):.1f}" x2="{xp(1):.1f}" y2="{yp(1):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="3,4" />'
    parity_label = f'<text x="{xp(0.88):.1f}" y="{yp(0.93):.1f}" fill="#334155" font-size="10">parity</text>'

    # Axes
    x_ticks, y_ticks = "", ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        xi = xp(v)
        x_ticks += f'<line x1="{xi:.1f}" y1="{pad_t + H}" x2="{xi:.1f}" y2="{pad_t + H + 5}" stroke="#64748b" />'
        x_ticks += f'<text x="{xi:.1f}" y="{pad_t + H + 18}" text-anchor="middle" fill="#94a3b8" font-size="11">{int(v * 100)}%</text>'
        yi = yp(v)
        y_ticks += f'<line x1="{pad_l - 4}" y1="{yi:.1f}" x2="{pad_l + W}" y2="{yi:.1f}" stroke="#1e293b" />'
        y_ticks += f'<text x="{pad_l - 8}" y="{yi + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{int(v * 100)}%</text>'

    x_axis_label = f'<text x="{pad_l + W // 2}" y="{pad_t + H + 38}" text-anchor="middle" fill="#64748b" font-size="12">Sim Success Rate</text>'
    y_axis_label = f'<text transform="rotate(-90 14 {pad_t + H // 2})" x="14" y="{pad_t + H // 2}" text-anchor="middle" fill="#64748b" font-size="12">Real Success Rate</text>'

    legend = (
        f'<circle cx="{pad_l + 10}" cy="{height - 10}" r="5" fill="#4ade80" fill-opacity="0.85" />'
        f'<text x="{pad_l + 20}" y="{height - 5}" fill="#94a3b8" font-size="11">Gap &lt; 8%</text>'
        f'<circle cx="{pad_l + 100}" cy="{height - 10}" r="5" fill="#f59e0b" fill-opacity="0.85" />'
        f'<text x="{pad_l + 110}" y="{height - 5}" fill="#94a3b8" font-size="11">Gap 8–15%</text>'
        f'<circle cx="{pad_l + 200}" cy="{height - 10}" r="5" fill="#C74634" fill-opacity="0.85" />'
        f'<text x="{pad_l + 210}" y="{height - 5}" fill="#94a3b8" font-size="11">Gap &gt; 15%</text>'
    )

    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="8" />
  <text x="{width // 2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Sim vs Real Success Rate — 20 Task Variants (r = {r_val:.2f})</text>
  {parity}
  {parity_label}
  {corr_line}
  {corr_label}
  {dots}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  <line x1="{pad_l}" y1="{pad_t + H}" x2="{pad_l + W}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  {x_ticks}
  {y_ticks}
  {x_axis_label}
  {y_axis_label}
  {legend}
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    metrics = _compute_metrics()
    svg1 = _svg_radar_chart()
    svg2 = _svg_scatter_plot(TASK_VARIANTS)

    metric_cards = ""
    card_data = [
        ("Fidelity Gap Score", f"{metrics['fidelity_gap_score']:.3f}", "1.0 = perfect sim-real match"),
        ("Sim-Real Correlation", f"r = {metrics['sim_real_correlation_r']:.2f}", "Pearson r across 20 tasks"),
        ("Highest Impact Target", metrics['highest_impact_dimension'], f"lowest: {metrics['lowest_fidelity_score_pct']}%"),
        ("Avg Sim-Real Gap", f"{metrics['average_sim_real_gap']:.1%}", "mean absolute gap"),
        ("Transfer Readiness", metrics['transfer_learning_readiness'], "policy transfer to real robot"),
        ("Task Variants", str(metrics['num_task_variants']), "evaluated in simulation"),
    ]
    for title, value, sub in card_data:
        color = "#4ade80" if value in ("HIGH",) else "#38bdf8"
        metric_cards += f"""
        <div class="card">
          <div class="card-label">{title}</div>
          <div class="card-value" style="color:{color}">{value}</div>
          <div class="card-sub">{sub}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sim Fidelity Tracker — Port 8213</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 1.5rem; color: #38bdf8; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .badge {{ display: inline-block; background: #C74634; color: #fff; font-size: 0.72rem;
              padding: 2px 8px; border-radius: 4px; margin-left: 10px; vertical-align: middle; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
    .card-value {{ font-size: 1.4rem; font-weight: 700; color: #38bdf8; }}
    .card-sub {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
    .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
    @media (max-width: 900px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; }}
    .chart-title {{ font-size: 0.9rem; color: #94a3b8; margin-bottom: 12px; }}
    .chart-section svg {{ width: 100%; display: block; margin: 0 auto; }}
    footer {{ margin-top: 24px; font-size: 0.75rem; color: #334155; text-align: center; }}
  </style>
</head>
<body>
  <h1>Sim Fidelity Tracker <span class="badge">PORT 8213</span></h1>
  <div class="subtitle">Isaac Sim environment fidelity vs real world — OCI Robot Cloud cycle-38A</div>

  <div class="metrics">{metric_cards}</div>

  <div class="charts-row">
    <div class="chart-section">
      <div class="chart-title">Fidelity Radar — 6 Dimensions: Isaac Sim vs Real World Baseline</div>
      {svg1}
    </div>
    <div class="chart-section">
      <div class="chart-title">Sim vs Real Success Rate — 20 Task Variants (Pearson r = {metrics['sim_real_correlation_r']:.2f})</div>
      {svg2}
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; Sim Fidelity Tracker v1.0 &mdash; cycle-38A</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# FastAPI app (with stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Sim Fidelity Tracker",
        description="Tracks simulation-to-reality fidelity metrics for Isaac Sim environments",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/api/fidelity", response_class=JSONResponse)
    async def get_fidelity():
        return JSONResponse(content={
            "dimensions": FIDELITY_DIMS,
            "sim_scores": SIM_SCORES,
            "real_baseline": REAL_BASELINE,
        })

    @app.get("/api/tasks", response_class=JSONResponse)
    async def get_tasks():
        return JSONResponse(content=TASK_VARIANTS)

    @app.get("/api/metrics", response_class=JSONResponse)
    async def get_metrics():
        return JSONResponse(content=_compute_metrics())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_fidelity_tracker", "port": 8213}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
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
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8213)
    else:
        print("[sim_fidelity_tracker] fastapi not found — using stdlib http.server on port 8213")
        with socketserver.TCPServer(("", 8213), _Handler) as srv:
            srv.serve_forever()
