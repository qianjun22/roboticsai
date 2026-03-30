"""Robot Arm IK Solver Analytics — FastAPI service on port 8217.

IK solution analytics for Franka Panda 7-DOF arm in GR00T pipeline.
Shows joint angle trajectories and IK solve-time distribution.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(7)

NUM_JOINTS   = 7
NUM_STEPS    = 100
NUM_SOLVES   = 1000

# Joint limits (rad) for Franka Panda
JOINT_LIMITS = [
    (-2.8973,  2.8973),  # j1
    (-1.7628,  1.7628),  # j2
    (-2.8973,  2.8973),  # j3
    (-3.0718, -0.0698),  # j4  — near-limit critical
    (-2.8973,  2.8973),  # j5
    (-0.0175,  3.7525),  # j6
    (-2.8973,  2.8973),  # j7
]

JOINT_COLORS = ["#38bdf8", "#C74634", "#a3e635", "#f97316", "#e879f9", "#facc15", "#34d399"]
JOINT_NAMES  = [f"J{i+1}" for i in range(NUM_JOINTS)]

def _gen_trajectory():
    """Generate realistic joint angle trajectories across NUM_STEPS."""
    trajs = []
    for j in range(NUM_JOINTS):
        lo, hi = JOINT_LIMITS[j]
        mid = (lo + hi) / 2
        amp = (hi - lo) * 0.25
        freq = 0.04 + 0.02 * j
        pts = []
        for s in range(NUM_STEPS):
            v = mid + amp * math.sin(2 * math.pi * freq * s + j * 0.5)
            # J4 biased near lower limit to simulate near-limit condition
            if j == 3:
                v = lo + abs(hi - lo) * 0.11 + random.gauss(0, 0.03)
            else:
                v += random.gauss(0, 0.02)
            pts.append(round(max(lo, min(hi, v)), 4))
        trajs.append(pts)
    return trajs

def _gen_solve_times():
    """Simulate 1000 IK solve times (ms) with realistic distribution."""
    times = []
    for _ in range(NUM_SOLVES):
        # bimodal: most fast (<10ms), tail out to ~50ms
        if random.random() < 0.85:
            t = max(0.5, random.gauss(8.3, 2.1))
        else:
            t = max(10.0, random.gauss(20.0, 6.0))
        times.append(round(min(50.0, t), 2))
    return sorted(times)


TRAJECTORY  = _gen_trajectory()
SOLVE_TIMES = _gen_solve_times()

# Key statistics
_sorted = sorted(SOLVE_TIMES)
IK_P50   = round(_sorted[int(0.50 * NUM_SOLVES)], 2)
IK_P95   = round(_sorted[int(0.95 * NUM_SOLVES)], 2)
IK_P99   = round(_sorted[int(0.99 * NUM_SOLVES)], 2)
IK_AVG   = round(sum(SOLVE_TIMES) / NUM_SOLVES, 2)
IK_FAIL_RATE = 0.7   # percent (simulated)

# Near-limit detection: J4 near limit
NEAR_LIMIT_JOINT  = 4  # 1-indexed
NEAR_LIMIT_PCT    = 89  # percent of grasp phase
REC_WORKSPACE_ADJ = "Reduce end-effector reach by 8cm along X-axis"

# ---------------------------------------------------------------------------
# SVG: joint trajectory
# ---------------------------------------------------------------------------

def _trajectory_svg() -> str:
    W, H = 720, 300
    ml, mr, mt, mb = 55, 20, 30, 40
    pw, ph = W - ml - mr, H - mt - mb

    def sx(i): return ml + int(i / (NUM_STEPS - 1) * pw)

    lines = []
    for j in range(NUM_JOINTS):
        lo, hi = JOINT_LIMITS[j]
        span = hi - lo

        # shaded safe band (inner 80%)
        band_lo = lo + 0.1 * span
        band_hi = hi - 0.1 * span

        def sy(v, lo=lo, span=span): return mt + int((1 - (v - lo) / span) * ph)

        # draw shaded safe range — only for J4 to highlight near-limit
        if j == 3:
            y_band_top = sy(band_hi)
            y_band_bot = sy(band_lo)
            lines.append(
                f'<rect x="{ml}" y="{y_band_top}" width="{pw}" '
                f'height="{y_band_bot - y_band_top}" fill="{JOINT_COLORS[j]}" opacity="0.08"/>'
            )

        pts = " ".join(f"{sx(s)},{sy(TRAJECTORY[j][s])}" for s in range(NUM_STEPS))
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{JOINT_COLORS[j]}" '
            f'stroke-width="1.5" opacity="0.85"/>'
        )

    # X axis ticks
    xticks = ""
    for i in [0, 25, 50, 75, 99]:
        x = sx(i)
        xticks += f'<text x="{x}" y="{mt+ph+14}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{i}</text>'

    # Legend
    legend = ""
    for j in range(NUM_JOINTS):
        lx = ml + j * 90
        ly = H - 8
        legend += f'<rect x="{lx}" y="{ly-8}" width="10" height="4" fill="{JOINT_COLORS[j]}"/>'
        legend += f'<text x="{lx+13}" y="{ly}" fill="{JOINT_COLORS[j]}" font-size="9" font-family="monospace">{JOINT_NAMES[j]}</text>'

    # Y axis labels
    yaxis = (
        f'<text x="{ml-4}" y="{mt+4}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">+lim</text>'
        f'<text x="{ml-4}" y="{mt+ph}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">-lim</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#f1f5f9" '
        f'font-size="13" font-family="monospace" font-weight="bold">'
        f'Joint Angle Trajectories — 7 DOF Franka Panda (100 timesteps)</text>'
        + "".join(lines)
        + xticks + legend + yaxis
        + f'<text x="{ml + pw//2}" y="{mt+ph+28}" text-anchor="middle" fill="#64748b" '
        f'font-size="9" font-family="monospace">timestep</text>'
        + "</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# SVG: IK solve time histogram
# ---------------------------------------------------------------------------

def _histogram_svg() -> str:
    W, H = 720, 280
    ml, mr, mt, mb = 55, 20, 30, 50
    pw, ph = W - ml - mr, H - mt - mb

    # Bins: 0-50ms in 5ms steps → 10 bins
    BIN_W = 5
    bins = [0] * 10
    for t in SOLVE_TIMES:
        idx = min(9, int(t / BIN_W))
        bins[idx] += 1

    max_count = max(bins)
    num_bins  = len(bins)
    bar_pw    = pw // num_bins - 4

    def sx(i): return ml + i * (pw // num_bins) + 2
    def sy(v): return mt + int((1 - v / max_count) * ph)

    bars = []
    for i, count in enumerate(bins):
        x = sx(i)
        y = sy(count)
        bh = mt + ph - y
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_pw}" height="{bh}" '
            f'fill="#38bdf8" rx="2" opacity="0.85"/>'
        )
        label_ms = f"{i*BIN_W}-{(i+1)*BIN_W}"
        bars.append(
            f'<text x="{x + bar_pw//2}" y="{mt+ph+14}" text-anchor="middle" '
            f'fill="#64748b" font-size="9" font-family="monospace">{label_ms}</text>'
        )

    # Percentile markers
    def pct_x(v): return ml + int(v / 50.0 * pw)

    markers = ""
    for label, val, color in [("p50", IK_P50, "#a3e635"), ("p95", IK_P95, "#fbbf24"), ("p99", IK_P99, "#C74634")]:
        x = pct_x(val)
        markers += f'<line x1="{x}" y1="{mt}" x2="{x}" y2="{mt+ph}" stroke="{color}" stroke-width="1.5" stroke-dasharray="4,3"/>'
        markers += f'<text x="{x+2}" y="{mt+10}" fill="{color}" font-size="9" font-family="monospace">{label}={val}ms</text>'

    # Y axis ticks
    yticks = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        v = int(max_count * frac)
        y = sy(v)
        yticks += f'<line x1="{ml}" y1="{y}" x2="{ml+pw}" y2="{y}" stroke="#334155" stroke-width="1"/>'
        yticks += f'<text x="{ml-4}" y="{y+4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v}</text>'

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#f1f5f9" '
        f'font-size="13" font-family="monospace" font-weight="bold">'
        f'IK Solve Time Distribution — 1000 Attempts (ms bins)</text>'
        + yticks
        + "".join(bars)
        + markers
        + f'<text x="{ml + pw//2}" y="{mt+ph+32}" text-anchor="middle" fill="#64748b" '
        f'font-size="9" font-family="monospace">solve time (ms)</text>'
        + "</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _html() -> str:
    traj_svg = _trajectory_svg()
    hist_svg = _histogram_svg()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Robot Arm IK Solver — Port 8217</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 20px; min-width: 170px; }}
    .card .val {{ font-size: 1.6rem; font-weight: bold; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
    .card.warn .val {{ color: #fbbf24; }}
    .card.alert .val {{ color: #C74634; }}
    .section {{ margin-bottom: 28px; }}
    .section h2 {{ color: #C74634; font-size: 1rem; margin-bottom: 10px; }}
    .warning-box {{ background: #1e293b; border-left: 3px solid #fbbf24; padding: 10px 14px;
                    border-radius: 4px; font-size: 0.82rem; color: #fbbf24; margin-top: 12px; }}
    .rec-box {{ background: #1e293b; border-left: 3px solid #38bdf8; padding: 10px 14px;
                border-radius: 4px; font-size: 0.82rem; color: #38bdf8; margin-top: 8px; }}
  </style>
</head>
<body>
  <h1>Robot Arm IK Solver Analytics</h1>
  <p class="subtitle">Franka Panda 7-DOF · GR00T Pipeline · Port 8217</p>

  <div class="cards">
    <div class="card">
      <div class="val">{IK_AVG}ms</div>
      <div class="lbl">Avg IK Solve Time</div>
    </div>
    <div class="card">
      <div class="val">{IK_P50}ms</div>
      <div class="lbl">p50 Solve Time</div>
    </div>
    <div class="card warn">
      <div class="val">{IK_P95}ms</div>
      <div class="lbl">p95 Solve Time</div>
    </div>
    <div class="card alert">
      <div class="val">{IK_P99}ms</div>
      <div class="lbl">p99 Solve Time</div>
    </div>
    <div class="card alert">
      <div class="val">{IK_FAIL_RATE}%</div>
      <div class="lbl">IK Failure Rate</div>
    </div>
    <div class="card warn">
      <div class="val">J{NEAR_LIMIT_JOINT} {NEAR_LIMIT_PCT}%</div>
      <div class="lbl">Near-Limit Joint (grasp phase)</div>
    </div>
  </div>

  <div class="section">
    <h2>Joint Angle Trajectories</h2>
    {traj_svg}
    <div class="warning-box">&#x26A0; Joint 4 (J4) operates near lower limit during {NEAR_LIMIT_PCT}% of the grasp phase.
    Shaded region = safe operating band (inner 80% of joint range).</div>
  </div>

  <div class="section">
    <h2>IK Solve Time Distribution</h2>
    {hist_svg}
    <div class="rec-box">Recommendation: {REC_WORKSPACE_ADJ}.
    This will reduce J4 near-limit occurrences and bring p99 solve time below 20ms.</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Robot Arm IK Solver Analytics", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html())

    @app.get("/api/stats")
    def api_stats():
        return {
            "avg_solve_ms": IK_AVG,
            "p50_ms": IK_P50,
            "p95_ms": IK_P95,
            "p99_ms": IK_P99,
            "failure_rate_pct": IK_FAIL_RATE,
            "near_limit_joint": NEAR_LIMIT_JOINT,
            "near_limit_pct": NEAR_LIMIT_PCT,
            "recommended_workspace_adj": REC_WORKSPACE_ADJ,
        }

    @app.get("/api/trajectory")
    def api_trajectory():
        return {
            "joints": JOINT_NAMES,
            "limits": JOINT_LIMITS,
            "trajectories": TRAJECTORY,
        }

    @app.get("/api/solve_times")
    def api_solve_times():
        return {
            "solve_times_ms": SOLVE_TIMES,
            "num_solves": NUM_SOLVES,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8217)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8217")
        HTTPServer(("0.0.0.0", 8217), _Handler).serve_forever()
