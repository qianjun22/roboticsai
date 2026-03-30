"""Policy Uncertainty Monitor — FastAPI service on port 8233.

Monitors GR00T policy prediction uncertainty for safe deployment decisions.
Provides SVG dashboards with uncertainty vs success rate and ensemble variance
over trajectory.
"""

from __future__ import annotations

import math
import random
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants / mock configuration
# ---------------------------------------------------------------------------

RANDOM_SEED = 7
random.seed(RANDOM_SEED)

_NUM_EVAL_EPISODES = 200
_TRAJ_STEPS = 847
_UNCERTAINTY_THRESHOLD = 0.31
_GRASP_HANDOFF_START = 280
_GRASP_HANDOFF_END = 320
_FAILURE_REDUCTION_PCT = 0.27   # threshold reduces 27% of failures
_GRASP_HANDOFF_AVG_UNCERTAINTY = 0.38
_ENSEMBLE_SIZE = 3              # optimal cost/benefit


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _generate_scatter_data() -> dict[str, Any]:
    """Generate uncertainty score vs success rate for 200 episodes."""
    random.seed(RANDOM_SEED)
    episodes = []
    for ep in range(_NUM_EVAL_EPISODES):
        unc = random.betavariate(2, 5)   # mostly low uncertainty
        # Higher uncertainty → lower success probability
        success_prob = max(0.0, min(1.0, 0.95 - 1.4 * unc + random.gauss(0, 0.1)))
        r = random.random()
        if unc > _UNCERTAINTY_THRESHOLD:
            # near threshold: uncertain outcome
            if r < 0.45:
                outcome = "fail"
            elif r < 0.70:
                outcome = "uncertain"
            else:
                outcome = "success"
        else:
            if r < success_prob * 0.9:
                outcome = "success"
            elif r < success_prob * 0.9 + 0.08:
                outcome = "uncertain"
            else:
                outcome = "fail"
        episodes.append({"ep": ep, "uncertainty": round(unc, 4), "outcome": outcome})
    return {"episodes": episodes}


def _generate_trajectory_variance() -> dict[str, Any]:
    """Generate ensemble variance over 847-step trajectory."""
    random.seed(RANDOM_SEED + 3)
    variance: list[float] = []

    for s in range(_TRAJ_STEPS):
        base = 0.08 + 0.04 * math.sin(s * 0.015)
        # Grasp handoff phase: elevated uncertainty
        if _GRASP_HANDOFF_START <= s <= _GRASP_HANDOFF_END:
            t = (s - _GRASP_HANDOFF_START) / (_GRASP_HANDOFF_END - _GRASP_HANDOFF_START)
            spike = 0.30 * math.sin(math.pi * t) ** 2
            base += spike
        # Occasional random spikes correlating with failures
        if random.random() < 0.03:
            base += random.uniform(0.08, 0.18)
        variance.append(round(max(0.02, base + random.gauss(0, 0.015)), 4))

    # Mark high-uncertainty steps as potential failure points
    high_unc_steps = [s for s, v in enumerate(variance) if v > _UNCERTAINTY_THRESHOLD]
    return {"variance": variance, "high_uncertainty_steps": high_unc_steps}


_SCATTER = _generate_scatter_data()
_TRAJECTORY = _generate_trajectory_variance()


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def _compute_metrics() -> dict:
    eps = _SCATTER["episodes"]
    abstain = [e for e in eps if e["uncertainty"] > _UNCERTAINTY_THRESHOLD]
    abstain_rate = len(abstain) / len(eps)
    fail_eps = [e for e in eps if e["outcome"] == "fail"]
    fail_high = [e for e in fail_eps if e["uncertainty"] > _UNCERTAINTY_THRESHOLD]
    unc_fail_corr = len(fail_high) / len(fail_eps) if fail_eps else 0.0
    var = _TRAJECTORY["variance"]
    high_risk_segs = _TRAJECTORY["high_uncertainty_steps"]
    return {
        "abstain_rate": round(abstain_rate, 4),
        "uncertainty_failure_correlation": round(unc_fail_corr, 4),
        "high_risk_trajectory_steps": len(high_risk_segs),
        "grasp_handoff_avg_uncertainty": _GRASP_HANDOFF_AVG_UNCERTAINTY,
        "threshold": _UNCERTAINTY_THRESHOLD,
        "failure_reduction_at_threshold": _FAILURE_REDUCTION_PCT,
        "ensemble_size": _ENSEMBLE_SIZE,
        "total_episodes": _NUM_EVAL_EPISODES,
        "trajectory_steps": _TRAJ_STEPS,
        "avg_variance": round(sum(var) / len(var), 4),
        "max_variance": round(max(var), 4),
    }


_METRICS = _compute_metrics()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

_SVG_W = 740
_SVG_H = 280
_PAD = {"top": 28, "right": 28, "bottom": 46, "left": 58}

OUTCOME_COLORS = {"success": "#22c55e", "fail": "#ef4444", "uncertain": "#f59e0b"}


def _px(val: float, domain_max: float, axis: str) -> float:
    plot_w = _SVG_W - _PAD["left"] - _PAD["right"]
    plot_h = _SVG_H - _PAD["top"] - _PAD["bottom"]
    if axis == "x":
        return _PAD["left"] + (val / domain_max) * plot_w
    return _SVG_H - _PAD["bottom"] - (val / domain_max) * plot_h


def _build_scatter_svg() -> str:
    eps = _SCATTER["episodes"]
    max_unc = 1.0   # x-axis: uncertainty 0..1
    max_ep = float(_NUM_EVAL_EPISODES)  # y-axis: episode index

    ax_x = _PAD["left"]
    ax_y = _SVG_H - _PAD["bottom"]
    ax_right = _SVG_W - _PAD["right"]
    gy_top = _PAD["top"]
    plot_h = ax_y - gy_top

    # y-axis: episode index 0..200
    y_ticks = [0, 50, 100, 150, 200]
    y_grid = ""
    for t in y_ticks:
        y = _px(t, max_ep, "y")
        y_grid += (f'<line x1="{ax_x}" y1="{y:.1f}" x2="{ax_right}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
                   f'<text x="{ax_x - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{t}</text>')

    # x-axis ticks: uncertainty
    x_ticks = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    x_tick_svg = ""
    for t in x_ticks:
        x = _px(t, max_unc, "x")
        x_tick_svg += f'<text x="{x:.1f}" y="{ax_y + 16}" text-anchor="middle" fill="#94a3b8" font-size="10">{t:.1f}</text>'

    # Threshold vertical line
    tx = _px(_UNCERTAINTY_THRESHOLD, max_unc, "x")
    threshold_line = (
        f'<line x1="{tx:.1f}" y1="{gy_top}" x2="{tx:.1f}" y2="{ax_y}" '
        f'stroke="#C74634" stroke-width="2" stroke-dasharray="6 3"/>'
        f'<text x="{tx + 4:.1f}" y="{gy_top + 14}" fill="#C74634" font-size="11">abstain &gt; {_UNCERTAINTY_THRESHOLD}</text>'
    )

    # Scatter dots
    dots = ""
    for e in eps:
        x = _px(e["uncertainty"], max_unc, "x")
        y = _px(e["ep"], max_ep, "y")
        color = OUTCOME_COLORS[e["outcome"]]
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}" fill-opacity="0.75"/>'

    # Legend
    legend = ""
    for i, (label, color) in enumerate(OUTCOME_COLORS.items()):
        lx = ax_x + i * 130
        legend += (f'<circle cx="{lx + 7}" cy="{gy_top + 8}" r="5" fill="{color}"/>'
                   f'<text x="{lx + 16}" y="{gy_top + 13}" fill="{color}" font-size="11" text-transform="capitalize">{label.title()}</text>')

    axes = (
        f'<line x1="{ax_x}" y1="{ax_y}" x2="{ax_right}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<line x1="{ax_x}" y1="{gy_top}" x2="{ax_x}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<text x="{ax_x - 40}" y="{(gy_top + ax_y) / 2:.0f}" fill="#94a3b8" font-size="12" '
        f'transform="rotate(-90,{ax_x - 40},{(gy_top + ax_y) / 2:.0f})">Episode Index</text>'
        f'<text x="{(ax_x + ax_right) / 2:.0f}" y="{ax_y + 38}" text-anchor="middle" fill="#94a3b8" font-size="12">Uncertainty Score</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{_SVG_H}" '
        f'style="background:#0f172a;border-radius:8px">'
        + y_grid + threshold_line + dots + x_tick_svg + legend + axes
        + '</svg>'
    )


def _build_trajectory_svg() -> str:
    var = _TRAJECTORY["variance"]
    steps = _TRAJ_STEPS
    max_y = 0.55

    ax_x = _PAD["left"]
    ax_y = _SVG_H - _PAD["bottom"]
    ax_right = _SVG_W - _PAD["right"]
    gy_top = _PAD["top"]
    plot_w = ax_right - ax_x
    plot_h = ax_y - gy_top

    # High-uncertainty shaded region: grasp handoff
    gh_x0 = ax_x + (_GRASP_HANDOFF_START / steps) * plot_w
    gh_x1 = ax_x + (_GRASP_HANDOFF_END / steps) * plot_w
    handoff_band = (
        f'<rect x="{gh_x0:.1f}" y="{gy_top}" width="{gh_x1 - gh_x0:.1f}" '
        f'height="{plot_h}" fill="#f59e0b" fill-opacity="0.1"/>'
        f'<text x="{(gh_x0 + gh_x1)/2:.1f}" y="{gy_top + 14}" text-anchor="middle" fill="#f59e0b" font-size="10">GRASP HANDOFF</text>'
    )

    # Threshold line
    ty = ax_y - (_UNCERTAINTY_THRESHOLD / max_y) * plot_h
    threshold_line = (
        f'<line x1="{ax_x}" y1="{ty:.1f}" x2="{ax_right}" y2="{ty:.1f}" '
        f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="5 3"/>'
        f'<text x="{ax_right - 4}" y="{ty - 4:.1f}" text-anchor="end" fill="#C74634" font-size="11">threshold {_UNCERTAINTY_THRESHOLD}</text>'
    )

    # y-grid
    y_ticks = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    y_grid = ""
    for t in y_ticks:
        y = ax_y - (t / max_y) * plot_h
        y_grid += (f'<line x1="{ax_x}" y1="{y:.1f}" x2="{ax_right}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
                   f'<text x="{ax_x - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{t:.1f}</text>')

    # x-ticks
    x_tick_svg = ""
    for s in range(0, steps + 1, 100):
        x = ax_x + (s / steps) * plot_w
        x_tick_svg += f'<text x="{x:.1f}" y="{ax_y + 16}" text-anchor="middle" fill="#94a3b8" font-size="11">{s}</text>'

    # Variance line — downsample for SVG size
    stride = 2
    pts = " ".join(
        f"{ax_x + (i / steps) * plot_w:.1f},{ax_y - (v / max_y) * plot_h:.1f}"
        for i, v in enumerate(var)
        if i % stride == 0
    )
    line = f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="1.8" stroke-linejoin="round"/>'

    # Fill under line
    first_x = ax_x
    last_x = ax_x + ((len(var) - 1) / steps) * plot_w
    fill_pts = f"{first_x:.1f},{ax_y} " + pts + f" {last_x:.1f},{ax_y}"
    fill = f'<polygon points="{fill_pts}" fill="#38bdf8" fill-opacity="0.08"/>'

    # High-uncertainty spikes: orange dots
    spike_dots = ""
    spike_steps = [s for s, v in enumerate(var) if v > _UNCERTAINTY_THRESHOLD and not (_GRASP_HANDOFF_START <= s <= _GRASP_HANDOFF_END)]
    for s in spike_steps[:20]:  # cap for readability
        x = ax_x + (s / steps) * plot_w
        y = ax_y - (var[s] / max_y) * plot_h
        spike_dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#ef4444" fill-opacity="0.9"/>'

    axes = (
        f'<line x1="{ax_x}" y1="{ax_y}" x2="{ax_right}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<line x1="{ax_x}" y1="{gy_top}" x2="{ax_x}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<text x="{ax_x - 42}" y="{(gy_top + ax_y) / 2:.0f}" fill="#94a3b8" font-size="12" '
        f'transform="rotate(-90,{ax_x - 42},{(gy_top + ax_y) / 2:.0f})">Ensemble Variance</text>'
        f'<text x="{(ax_x + ax_right) / 2:.0f}" y="{ax_y + 38}" text-anchor="middle" fill="#94a3b8" font-size="12">Trajectory Step</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{_SVG_H}" '
        f'style="background:#0f172a;border-radius:8px">'
        + y_grid + handoff_band + fill + line + threshold_line + spike_dots + x_tick_svg + axes
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg1 = _build_scatter_svg()
    svg2 = _build_trajectory_svg()
    m = _METRICS

    cards = f"""
    <div class="metrics">
      <div class="card">
        <div class="label">Uncertainty Threshold</div>
        <div class="value" style="color:#C74634">{m['threshold']:.2f}</div>
        <div class="sub">auto-abstain above</div>
      </div>
      <div class="card">
        <div class="label">Abstain Rate</div>
        <div class="value" style="color:#f59e0b">{m['abstain_rate']*100:.1f}%</div>
        <div class="sub">of {m['total_episodes']} episodes</div>
      </div>
      <div class="card">
        <div class="label">Failure Reduction</div>
        <div class="value" style="color:#22c55e">{m['failure_reduction_at_threshold']*100:.0f}%</div>
        <div class="sub">at threshold</div>
      </div>
      <div class="card">
        <div class="label">Unc-Fail Correlation</div>
        <div class="value" style="color:#38bdf8">{m['uncertainty_failure_correlation']*100:.0f}%</div>
        <div class="sub">of failures flagged</div>
      </div>
      <div class="card">
        <div class="label">Grasp Handoff Unc.</div>
        <div class="value" style="color:#f97316">{m['grasp_handoff_avg_uncertainty']:.2f}</div>
        <div class="sub">steps {_GRASP_HANDOFF_START}-{_GRASP_HANDOFF_END}</div>
      </div>
      <div class="card">
        <div class="label">Ensemble Size</div>
        <div class="value" style="color:#a78bfa">{m['ensemble_size']}</div>
        <div class="sub">policies (optimal)</div>
      </div>
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Policy Uncertainty Monitor — Port 8233</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .oracle-badge {{ display:inline-block; background:#C74634; color:#fff; font-size:11px;
                     padding:2px 10px; border-radius:4px; margin-left:12px; vertical-align:middle; }}
    .section {{ margin-bottom: 24px; }}
    .section h2 {{ font-size: 15px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em;
                   margin-bottom: 10px; border-left: 3px solid #C74634; padding-left: 10px; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 14px 18px; min-width: 155px; flex: 1; }}
    .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; }}
    .value {{ font-size: 26px; font-weight: 700; margin: 4px 0; }}
    .sub {{ font-size: 11px; color: #475569; }}
    svg {{ max-width: 100%; height: auto; display: block; }}
    .chart-wrap {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; }}
    footer {{ margin-top: 28px; color: #334155; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Policy Uncertainty Monitor <span class="oracle-badge">OCI Robot Cloud</span></h1>
  <div class="subtitle">GR00T ensemble uncertainty · safe deployment decisions · port 8233</div>

  {cards}

  <div class="section">
    <h2>Uncertainty Score vs Episode — 200 Eval Episodes</h2>
    <div class="chart-wrap">{svg1}</div>
  </div>

  <div class="section">
    <h2>Ensemble Variance over Trajectory — {_TRAJ_STEPS} Steps</h2>
    <div class="chart-wrap">{svg2}</div>
  </div>

  <footer>OCI Robot Cloud · Policy Uncertainty Monitor · &copy; 2026 Oracle</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Policy Uncertainty Monitor",
        description="Monitors GR00T policy prediction uncertainty for safe deployment decisions",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_build_html())

    @app.get("/api/scatter")
    async def scatter_api() -> dict:
        return {
            "num_episodes": _NUM_EVAL_EPISODES,
            "threshold": _UNCERTAINTY_THRESHOLD,
            "episodes": _SCATTER["episodes"],
        }

    @app.get("/api/trajectory")
    async def trajectory_api() -> dict:
        return {
            "steps": _TRAJ_STEPS,
            "variance": _TRAJECTORY["variance"],
            "high_uncertainty_steps": _TRAJECTORY["high_uncertainty_steps"],
            "grasp_handoff": {"start": _GRASP_HANDOFF_START, "end": _GRASP_HANDOFF_END},
        }

    @app.get("/api/metrics")
    async def metrics_api() -> dict:
        return _METRICS

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "policy_uncertainty_monitor", "port": 8233}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    def _run_stdlib() -> None:
        with socketserver.TCPServer(("", 8233), _Handler) as httpd:
            print("Policy Uncertainty Monitor (stdlib) running on http://localhost:8233")
            httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8233)
    else:
        _run_stdlib()
