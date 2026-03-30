"""Gripper Force Analyzer — FastAPI service on port 8232.

Analyzes Franka gripper force profiles during cube_lift manipulation tasks.
Provides SVG dashboards with force vs time and peak force distribution.
"""

from __future__ import annotations

import math
import random
import json
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

_NUM_STEPS = 300
_GRASP_START = 80
_GRASP_END = 180
_NUM_EPISODES = 500
_AVG_PEAK_FORCE = 14.3
_SLIP_RATE = 0.06          # 6% below 10 N
_DAMAGE_RATE = 0.03        # 3% above 22 N
_OPTIMAL_COMPLIANCE = 0.94 # 94% in green band (12-18 N)


def _generate_force_trace() -> dict[str, list[float]]:
    """Generate fingertip contact, normal, and tangential force over 300 steps."""
    random.seed(RANDOM_SEED)
    contact, normal, tangential = [], [], []
    slip_events: list[int] = []

    # Pre-grasp noise
    for s in range(_GRASP_START):
        noise = random.gauss(0, 0.3)
        contact.append(max(0.0, 1.0 + noise))
        normal.append(max(0.0, 0.8 + random.gauss(0, 0.25)))
        tangential.append(max(0.0, 0.4 + random.gauss(0, 0.2)))

    # Grasp phase — ramp up
    for s in range(_GRASP_START, _GRASP_END):
        t = (s - _GRASP_START) / (_GRASP_END - _GRASP_START)
        base_c = 1.0 + 13.0 * (1 - math.exp(-5 * t))
        base_n = 0.8 + 11.0 * (1 - math.exp(-5 * t))
        base_t = 0.4 + 4.5 * (1 - math.exp(-4 * t))

        # occasional slip dips
        slip_dip = 0.0
        if s in (110, 142, 166):
            slip_events.append(s)
            slip_dip = -3.5

        contact.append(max(0.0, base_c + slip_dip + random.gauss(0, 0.4)))
        normal.append(max(0.0, base_n + slip_dip * 0.8 + random.gauss(0, 0.35)))
        tangential.append(max(0.0, base_t + slip_dip * 0.5 + random.gauss(0, 0.3)))

    # Release phase
    peak_c = contact[_GRASP_END - 1]
    peak_n = normal[_GRASP_END - 1]
    peak_t = tangential[_GRASP_END - 1]
    for s in range(_GRASP_END, _NUM_STEPS):
        t = (s - _GRASP_END) / (_NUM_STEPS - _GRASP_END)
        decay = math.exp(-4 * t)
        contact.append(max(0.0, peak_c * decay + random.gauss(0, 0.3)))
        normal.append(max(0.0, peak_n * decay + random.gauss(0, 0.25)))
        tangential.append(max(0.0, peak_t * decay + random.gauss(0, 0.2)))

    return {"contact": contact, "normal": normal, "tangential": tangential, "slip_events": slip_events}


def _generate_peak_force_histogram() -> dict[str, Any]:
    """Generate peak grasp force distribution for 500 episodes."""
    random.seed(RANDOM_SEED + 1)
    forces: list[float] = []
    for _ in range(_NUM_EPISODES):
        # Mixture: mostly optimal, some under/over
        r = random.random()
        if r < _SLIP_RATE:
            forces.append(random.gauss(7.5, 1.5))    # under-grasp
        elif r < _SLIP_RATE + _DAMAGE_RATE:
            forces.append(random.gauss(25.0, 2.0))   # over-grasp
        else:
            forces.append(random.gauss(_AVG_PEAK_FORCE, 2.1))

    # Bin into 0-40 N, 2 N bins
    bins = list(range(0, 42, 2))
    counts = [0] * (len(bins) - 1)
    for f in forces:
        for i in range(len(bins) - 1):
            if bins[i] <= f < bins[i + 1]:
                counts[i] += 1
                break

    return {"bins": bins, "counts": counts, "forces": forces}


_FORCE_TRACE = _generate_force_trace()
_HISTOGRAM = _generate_peak_force_histogram()


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

_SVG_W = 740
_SVG_H = 260
_PAD = {"top": 24, "right": 24, "bottom": 44, "left": 56}


def _scale_x(val: float, domain_max: float) -> float:
    plot_w = _SVG_W - _PAD["left"] - _PAD["right"]
    return _PAD["left"] + (val / domain_max) * plot_w


def _scale_y(val: float, domain_max: float) -> float:
    plot_h = _SVG_H - _PAD["top"] - _PAD["bottom"]
    return _SVG_H - _PAD["bottom"] - (val / domain_max) * plot_h


def _polyline(values: list[float], domain_max_x: float, domain_max_y: float, color: str, stroke_w: float = 2) -> str:
    pts = " ".join(
        f"{_scale_x(i, domain_max_x):.1f},{_scale_y(v, domain_max_y):.1f}"
        for i, v in enumerate(values)
    )
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linejoin="round"/>'


def _build_force_time_svg() -> str:
    trace = _FORCE_TRACE
    max_y = 22.0
    steps = _NUM_STEPS

    gx0 = _scale_x(_GRASP_START, steps)
    gx1 = _scale_x(_GRASP_END, steps)
    gy_top = _PAD["top"]
    gy_bot = _SVG_H - _PAD["bottom"]

    # axis lines
    ax_x = _PAD["left"]
    ax_y = _SVG_H - _PAD["bottom"]
    ax_right = _SVG_W - _PAD["right"]

    # y-grid & ticks
    ticks_y = [0, 5, 10, 15, 20]
    grid_lines = ""
    for t in ticks_y:
        y = _scale_y(t, max_y)
        grid_lines += f'<line x1="{ax_x}" y1="{y:.1f}" x2="{ax_right}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid_lines += f'<text x="{ax_x - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{t}</text>'

    # x-ticks
    x_ticks_labels = [0, 50, 100, 150, 200, 250, 300]
    x_tick_svg = ""
    for t in x_ticks_labels:
        x = _scale_x(t, steps)
        x_tick_svg += f'<text x="{x:.1f}" y="{ax_y + 16}" text-anchor="middle" fill="#94a3b8" font-size="11">{t}</text>'

    # grasp phase band
    band = (f'<rect x="{gx0:.1f}" y="{gy_top}" width="{gx1 - gx0:.1f}" '
            f'height="{gy_bot - gy_top}" fill="#38bdf8" fill-opacity="0.08"/>'
            f'<text x="{(gx0 + gx1)/2:.1f}" y="{gy_top + 14}" text-anchor="middle" fill="#38bdf8" font-size="10">GRASP PHASE</text>')

    # slip event markers
    slip_markers = ""
    for step in trace["slip_events"]:
        x = _scale_x(step, steps)
        y = _scale_y(trace["contact"][step], max_y)
        slip_markers += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ef4444" stroke="#fca5a5" stroke-width="1.5"/>'

    lines = (
        _polyline(trace["contact"], steps, max_y, "#38bdf8", 2)
        + _polyline(trace["normal"], steps, max_y, "#a78bfa", 1.5)
        + _polyline(trace["tangential"], steps, max_y, "#fb923c", 1.5)
    )

    legend = (
        f'<circle cx="{ax_x + 10}" cy="{_PAD["top"] + 8}" r="5" fill="#38bdf8"/>'
        f'<text x="{ax_x + 20}" y="{_PAD["top"] + 13}" fill="#38bdf8" font-size="11">Contact Force</text>'
        f'<circle cx="{ax_x + 120}" cy="{_PAD["top"] + 8}" r="5" fill="#a78bfa"/>'
        f'<text x="{ax_x + 130}" y="{_PAD["top"] + 13}" fill="#a78bfa" font-size="11">Normal Force</text>'
        f'<circle cx="{ax_x + 230}" cy="{_PAD["top"] + 8}" r="5" fill="#fb923c"/>'
        f'<text x="{ax_x + 240}" y="{_PAD["top"] + 13}" fill="#fb923c" font-size="11">Tangential Force</text>'
        f'<circle cx="{ax_x + 360}" cy="{_PAD["top"] + 8}" r="5" fill="#ef4444"/>'
        f'<text x="{ax_x + 370}" y="{_PAD["top"] + 13}" fill="#ef4444" font-size="11">Slip Event</text>'
    )

    axes = (
        f'<line x1="{ax_x}" y1="{ax_y}" x2="{ax_right}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<line x1="{ax_x}" y1="{gy_top}" x2="{ax_x}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<text x="{ax_x - 38}" y="{(gy_top + ax_y) / 2:.0f}" fill="#94a3b8" font-size="12" '
        f'transform="rotate(-90,{ax_x - 38},{(gy_top + ax_y) / 2:.0f})">Force (N)</text>'
        f'<text x="{(ax_x + ax_right) / 2:.0f}" y="{ax_y + 36}" text-anchor="middle" fill="#94a3b8" font-size="12">Trajectory Step</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{_SVG_H}" '
        f'style="background:#0f172a;border-radius:8px">'
        + grid_lines + band + lines + slip_markers + x_tick_svg + legend + axes
        + '</svg>'
    )


def _build_histogram_svg() -> str:
    hist = _HISTOGRAM
    bins = hist["bins"]
    counts = hist["counts"]
    max_count = max(counts) if counts else 1
    num_bins = len(counts)

    ax_x = _PAD["left"]
    ax_y = _SVG_H - _PAD["bottom"]
    ax_right = _SVG_W - _PAD["right"]
    gy_top = _PAD["top"]
    plot_w = ax_right - ax_x
    plot_h = ax_y - gy_top
    bin_w = plot_w / num_bins

    # Optimal range band: 12-18 N → bins index 6-9
    opt_start_n, opt_end_n = 12.0, 18.0
    max_force_n = float(bins[-1])
    band_x0 = ax_x + (opt_start_n / max_force_n) * plot_w
    band_x1 = ax_x + (opt_end_n / max_force_n) * plot_w
    opt_band = (
        f'<rect x="{band_x0:.1f}" y="{gy_top}" width="{band_x1 - band_x0:.1f}" '
        f'height="{plot_h}" fill="#22c55e" fill-opacity="0.12"/>'
        f'<text x="{(band_x0 + band_x1)/2:.1f}" y="{gy_top + 14}" text-anchor="middle" fill="#22c55e" font-size="10">OPTIMAL</text>'
    )

    # Under-grasp zone: 0-10 N
    ug_x1 = ax_x + (10.0 / max_force_n) * plot_w
    under_band = (
        f'<rect x="{ax_x}" y="{gy_top}" width="{ug_x1 - ax_x:.1f}" '
        f'height="{plot_h}" fill="#ef4444" fill-opacity="0.07"/>'
        f'<text x="{(ax_x + ug_x1)/2:.1f}" y="{gy_top + 14}" text-anchor="middle" fill="#ef4444" font-size="10">SLIP RISK</text>'
    )

    # Over-grasp zone: 22-40 N
    og_x0 = ax_x + (22.0 / max_force_n) * plot_w
    over_band = (
        f'<rect x="{og_x0:.1f}" y="{gy_top}" width="{ax_right - og_x0:.1f}" '
        f'height="{plot_h}" fill="#f97316" fill-opacity="0.07"/>'
        f'<text x="{(og_x0 + ax_right)/2:.1f}" y="{gy_top + 14}" text-anchor="middle" fill="#f97316" font-size="10">DAMAGE RISK</text>'
    )

    bars = ""
    for i, cnt in enumerate(counts):
        bh = (cnt / max_count) * plot_h
        bx = ax_x + i * bin_w
        by = ax_y - bh
        force_mid = (bins[i] + bins[i + 1]) / 2
        if 12 <= force_mid <= 18:
            color = "#22c55e"
        elif force_mid < 10:
            color = "#ef4444"
        elif force_mid > 22:
            color = "#f97316"
        else:
            color = "#38bdf8"
        bars += (f'<rect x="{bx + 1:.1f}" y="{by:.1f}" width="{bin_w - 2:.1f}" '
                 f'height="{bh:.1f}" fill="{color}" fill-opacity="0.85"/>')

    # x-axis ticks
    x_tick_svg = ""
    for n in range(0, 42, 10):
        x = ax_x + (n / max_force_n) * plot_w
        x_tick_svg += f'<text x="{x:.1f}" y="{ax_y + 16}" text-anchor="middle" fill="#94a3b8" font-size="11">{n}N</text>'

    # y-axis ticks
    y_tick_svg = ""
    for cnt in [0, 25, 50, 75, 100]:
        y = ax_y - (cnt / max_count) * plot_h
        y_tick_svg += (f'<line x1="{ax_x}" y1="{y:.1f}" x2="{ax_right}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
                       f'<text x="{ax_x - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{cnt}</text>')

    axes = (
        f'<line x1="{ax_x}" y1="{ax_y}" x2="{ax_right}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<line x1="{ax_x}" y1="{gy_top}" x2="{ax_x}" y2="{ax_y}" stroke="#475569" stroke-width="1.5"/>'
        f'<text x="{ax_x - 38}" y="{(gy_top + ax_y) / 2:.0f}" fill="#94a3b8" font-size="12" '
        f'transform="rotate(-90,{ax_x - 38},{(gy_top + ax_y) / 2:.0f})">Episodes</text>'
        f'<text x="{(ax_x + ax_right) / 2:.0f}" y="{ax_y + 36}" text-anchor="middle" fill="#94a3b8" font-size="12">Peak Grasp Force (N)</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{_SVG_H}" '
        f'style="background:#0f172a;border-radius:8px">'
        + y_tick_svg + under_band + opt_band + over_band + bars + x_tick_svg + axes
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg1 = _build_force_time_svg()
    svg2 = _build_histogram_svg()

    slip_pct = f"{_SLIP_RATE * 100:.0f}%"
    damage_pct = f"{_DAMAGE_RATE * 100:.0f}%"
    optimal_pct = f"{_OPTIMAL_COMPLIANCE * 100:.0f}%"
    num_slip_eps = int(_SLIP_RATE * _NUM_EPISODES)
    num_damage_eps = int(_DAMAGE_RATE * _NUM_EPISODES)
    num_optimal_eps = int(_OPTIMAL_COMPLIANCE * _NUM_EPISODES)

    cards = f"""
    <div class="metrics">
      <div class="card">
        <div class="label">Avg Peak Force</div>
        <div class="value" style="color:#38bdf8">{_AVG_PEAK_FORCE:.1f} N</div>
        <div class="sub">across {_NUM_EPISODES} episodes</div>
      </div>
      <div class="card">
        <div class="label">Slip Rate (&lt;10N)</div>
        <div class="value" style="color:#ef4444">{slip_pct}</div>
        <div class="sub">{num_slip_eps} episodes</div>
      </div>
      <div class="card">
        <div class="label">Damage Risk (&gt;22N)</div>
        <div class="value" style="color:#f97316">{damage_pct}</div>
        <div class="sub">{num_damage_eps} episodes</div>
      </div>
      <div class="card">
        <div class="label">Optimal Compliance</div>
        <div class="value" style="color:#22c55e">{optimal_pct}</div>
        <div class="sub">{num_optimal_eps}/{_NUM_EPISODES} in 12-18N</div>
      </div>
      <div class="card">
        <div class="label">Slip Events (trace)</div>
        <div class="value" style="color:#ef4444">{len(_FORCE_TRACE['slip_events'])}</div>
        <div class="sub">steps {', '.join(str(s) for s in _FORCE_TRACE['slip_events'])}</div>
      </div>
      <div class="card">
        <div class="label">Force Std Dev</div>
        <div class="value" style="color:#a78bfa">2.1 N</div>
        <div class="sub">consistency score</div>
      </div>
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gripper Force Analyzer — Port 8232</title>
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
             padding: 14px 18px; min-width: 160px; flex: 1; }}
    .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; }}
    .value {{ font-size: 26px; font-weight: 700; margin: 4px 0; }}
    .sub {{ font-size: 11px; color: #475569; }}
    svg {{ max-width: 100%; height: auto; display: block; }}
    .chart-wrap {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; }}
    footer {{ margin-top: 28px; color: #334155; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Gripper Force Analyzer <span class="oracle-badge">OCI Robot Cloud</span></h1>
  <div class="subtitle">Franka gripper force profiles · cube_lift manipulation task · port 8232</div>

  {cards}

  <div class="section">
    <h2>Force vs Time — Single Trajectory (300 Steps)</h2>
    <div class="chart-wrap">{svg1}</div>
  </div>

  <div class="section">
    <h2>Peak Grasp Force Distribution — 500 Episodes</h2>
    <div class="chart-wrap">{svg2}</div>
  </div>

  <footer>OCI Robot Cloud · Gripper Force Analyzer · &copy; 2026 Oracle</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Gripper Force Analyzer",
        description="Analyzes Franka gripper force profiles during cube_lift manipulation tasks",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_build_html())

    @app.get("/api/force-trace")
    async def force_trace_api() -> dict:
        trace = _FORCE_TRACE
        return {
            "steps": _NUM_STEPS,
            "grasp_phase": {"start": _GRASP_START, "end": _GRASP_END},
            "contact_force": trace["contact"],
            "normal_force": trace["normal"],
            "tangential_force": trace["tangential"],
            "slip_events": trace["slip_events"],
        }

    @app.get("/api/histogram")
    async def histogram_api() -> dict:
        hist = _HISTOGRAM
        return {
            "num_episodes": _NUM_EPISODES,
            "bins": hist["bins"],
            "counts": hist["counts"],
            "optimal_range_n": [12, 18],
        }

    @app.get("/api/metrics")
    async def metrics_api() -> dict:
        return {
            "avg_peak_force_n": _AVG_PEAK_FORCE,
            "slip_rate": _SLIP_RATE,
            "damage_rate": _DAMAGE_RATE,
            "optimal_compliance": _OPTIMAL_COMPLIANCE,
            "num_episodes": _NUM_EPISODES,
            "slip_events_in_trace": len(_FORCE_TRACE["slip_events"]),
            "force_std_dev_n": 2.1,
            "optimal_range_n": [12, 18],
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "gripper_force_analyzer", "port": 8232}

else:
    # stdlib fallback
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
        with socketserver.TCPServer(("", 8232), _Handler) as httpd:
            print("Gripper Force Analyzer (stdlib) running on http://localhost:8232")
            httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8232)
    else:
        _run_stdlib()
