#!/usr/bin/env python3
"""
Robot Pose Estimator — port 8261
Estimates and tracks robot end-effector pose accuracy for fine-tuning QA.
"""

import random
import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data generation (stdlib only — no numpy)
# ---------------------------------------------------------------------------

random.seed(42)

N_EPISODES = 500
TARGET_X, TARGET_Y = 0.0, 0.0   # target EE position in normalised space
SUCCESS_RADIUS = 0.055           # 5.5cm in metres

TOLERANCES = {
    "dx":    5.0,   # mm
    "dy":    5.0,
    "dz":    7.0,   # taller tolerance for z (placement height)
    "droll": 3.0,   # degrees
    "dpitch":3.0,
    "dyaw":  4.0,
}

AVG_ERRORS = {
    "dx":    2.8,
    "dy":    3.1,
    "dz":    4.6,   # highest variance
    "droll": 1.7,
    "dpitch":2.1,
    "dyaw":  2.4,
}


def _gen_episodes():
    eps = []
    for i in range(N_EPISODES):
        # Position error (mm)
        ex = random.gauss(0, AVG_ERRORS["dx"])
        ey = random.gauss(0, AVG_ERRORS["dy"])
        ez = random.gauss(0, AVG_ERRORS["dz"])
        # Orientation error (degrees)
        er = random.gauss(0, AVG_ERRORS["droll"])
        ep = random.gauss(0, AVG_ERRORS["dpitch"])
        ew = random.gauss(0, AVG_ERRORS["dyaw"])

        dist_3d = math.sqrt(ex**2 + ey**2 + ez**2)
        success = dist_3d < (SUCCESS_RADIUS * 1000)  # convert m→mm roughly

        eps.append({
            "episode": i,
            "dx": round(ex, 2), "dy": round(ey, 2), "dz": round(ez, 2),
            "droll": round(er, 2), "dpitch": round(ep, 2), "dyaw": round(ew, 2),
            "dist_3d_mm": round(dist_3d, 2),
            "success": success,
        })
    return eps


EPISODES = _gen_episodes()
N_SUCCESS = sum(1 for e in EPISODES if e["success"])
SUCCESS_RATE = N_SUCCESS / N_EPISODES

# Compliance per component
COMPLIANCE = {k: round(sum(1 for e in EPISODES if abs(e[k]) <= TOLERANCES[k]) / N_EPISODES, 4)
              for k in TOLERANCES}

# Box-plot stats per component (approx with sorted list)
def _box_stats(vals):
    s = sorted(vals)
    n = len(s)
    def pct(p): return s[int(p * n / 100)]
    return {"min": round(pct(5), 2), "q1": round(pct(25), 2), "med": round(pct(50), 2),
            "q3": round(pct(75), 2), "max": round(pct(95), 2)}


BOX_STATS = {k: _box_stats([abs(e[k]) for e in EPISODES]) for k in TOLERANCES}

# ---------------------------------------------------------------------------
# SVG 1: EE scatter (projected to XY plane)
# ---------------------------------------------------------------------------

def build_scatter_svg() -> str:
    W, H = 400, 400
    cx, cy = W // 2, H // 2
    scale = 16  # pixels per mm
    radius_px = int(SUCCESS_RADIUS * 1000 * scale * 0.55)  # visual radius

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">EE Pose Scatter — XY Plane (200 eps)</text>')

    # Grid
    for offset in [-60, -40, -20, 0, 20, 40, 60]:
        x = cx + offset * scale // 5
        y = cy + offset * scale // 5
        lines.append(f'<line x1="{x}" y1="{cy - 80}" x2="{x}" y2="{cy + 80}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<line x1="{cx - 80}" y1="{y}" x2="{cx + 80}" y2="{y}" stroke="#334155" stroke-width="1"/>')

    # Success radius circle
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{radius_px}" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.7"/>')
    lines.append(f'<text x="{cx + radius_px + 4}" y="{cy - 4}" fill="#22c55e" font-size="9" font-family="monospace">±{int(SUCCESS_RADIUS*1000)}mm</text>')

    # Crosshair target
    lines.append(f'<line x1="{cx - 12}" y1="{cy}" x2="{cx + 12}" y2="{cy}" stroke="#fbbf24" stroke-width="2"/>')
    lines.append(f'<line x1="{cx}" y1="{cy - 12}" x2="{cx}" y2="{cy + 12}" stroke="#fbbf24" stroke-width="2"/>')
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="none" stroke="#fbbf24" stroke-width="2"/>')
    lines.append(f'<text x="{cx + 8}" y="{cy + 20}" fill="#fbbf24" font-size="9" font-family="monospace">target</text>')

    # Scatter dots (first 200 episodes)
    for ep in EPISODES[:200]:
        px = cx + int(ep["dx"] * scale * 0.55)
        py = cy - int(ep["dy"] * scale * 0.55)
        # Clamp to canvas
        px = max(10, min(W - 10, px))
        py = max(30, min(H - 20, py))
        color = "#38bdf8" if ep["success"] else "#C74634"
        lines.append(f'<circle cx="{px}" cy="{py}" r="2.5" fill="{color}" opacity="0.7"/>')

    # Legend
    lines.append(f'<circle cx="{W//2 - 60}" cy="{H - 16}" r="4" fill="#38bdf8"/>')
    lines.append(f'<text x="{W//2 - 52}" y="{H - 12}" fill="#94a3b8" font-size="10" font-family="monospace">Success</text>')
    lines.append(f'<circle cx="{W//2 + 20}" cy="{H - 16}" r="4" fill="#C74634"/>')
    lines.append(f'<text x="{W//2 + 28}" y="{H - 12}" fill="#94a3b8" font-size="10" font-family="monospace">Fail</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG 2: Box plot of pose error components
# ---------------------------------------------------------------------------

def build_boxplot_svg() -> str:
    W, H = 760, 300
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    keys = list(TOLERANCES.keys())
    labels = ["Δx (mm)", "Δy (mm)", "Δz (mm)", "Δroll (°)", "Δpitch (°)", "Δyaw (°)"]
    n = len(keys)
    col_w = chart_w / n
    box_w = col_w * 0.38
    max_val = 14.0

    def to_y(v):
        return pad_t + chart_h - int(v / max_val * chart_h)

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">6-DoF Pose Error Distribution — 500 Episodes</text>')

    # Y grid
    for v in [0, 3, 5, 7, 10, 14]:
        y = to_y(v)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{W - pad_r}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{y + 4}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">{v}</text>')

    for i, key in enumerate(keys):
        stats = BOX_STATS[key]
        tol   = TOLERANCES[key]
        comp  = COMPLIANCE[key]
        cx_  = pad_l + i * col_w + col_w / 2
        bx   = cx_ - box_w / 2

        # Tolerance band
        ty = to_y(tol)
        lines.append(f'<rect x="{pad_l + i * col_w + 4:.1f}" y="{ty}" width="{col_w - 8:.1f}" height="{pad_t + chart_h - ty}" fill="#22c55e" opacity="0.07" rx="2"/>')
        lines.append(f'<line x1="{pad_l + i * col_w + 4:.1f}" y1="{ty}" x2="{pad_l + (i+1) * col_w - 4:.1f}" y2="{ty}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>')

        # Whiskers
        lines.append(f'<line x1="{cx_:.1f}" y1="{to_y(stats["max"])}" x2="{cx_:.1f}" y2="{to_y(stats["min"])}" stroke="#64748b" stroke-width="1.5"/>')
        lines.append(f'<line x1="{bx:.1f}" y1="{to_y(stats["max"])}" x2="{bx + box_w:.1f}" y2="{to_y(stats["max"])}" stroke="#64748b" stroke-width="1.5"/>')
        lines.append(f'<line x1="{bx:.1f}" y1="{to_y(stats["min"])}" x2="{bx + box_w:.1f}" y2="{to_y(stats["min"])}" stroke="#64748b" stroke-width="1.5"/>')

        # IQR box
        bh = to_y(stats["q1"]) - to_y(stats["q3"])
        lines.append(f'<rect x="{bx:.1f}" y="{to_y(stats["q3"])}" width="{box_w:.1f}" height="{bh}" fill="#38bdf8" opacity="0.3" rx="2"/>')
        lines.append(f'<rect x="{bx:.1f}" y="{to_y(stats["q3"])}" width="{box_w:.1f}" height="{bh}" fill="none" stroke="#38bdf8" stroke-width="1.5" rx="2"/>')

        # Median line
        lines.append(f'<line x1="{bx:.1f}" y1="{to_y(stats["med"])}" x2="{bx + box_w:.1f}" y2="{to_y(stats["med"])}" stroke="#C74634" stroke-width="2"/>')

        # Compliance label
        color = "#22c55e" if comp >= 0.80 else "#f59e0b"
        lines.append(f'<text x="{cx_:.1f}" y="{to_y(stats["max"]) - 6}" fill="{color}" font-size="9" font-family="monospace" text-anchor="middle">{comp:.0%}</text>')

        # X label
        lines.append(f'<text x="{cx_:.1f}" y="{pad_t + chart_h + 16}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">{labels[i]}</text>')

    # Legend
    ly = H - 12
    lines.append(f'<line x1="{pad_l}" y1="{ly - 5}" x2="{pad_l + 18}" y2="{ly - 5}" stroke="#C74634" stroke-width="2"/>')
    lines.append(f'<text x="{pad_l + 22}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Median</text>')
    lines.append(f'<rect x="{pad_l + 80}" y="{ly - 10}" width="12" height="10" fill="#38bdf8" opacity="0.3" rx="2"/>')
    lines.append(f'<text x="{pad_l + 96}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">IQR</text>')
    lines.append(f'<line x1="{pad_l + 140}" y1="{ly - 5}" x2="{pad_l + 158}" y2="{ly - 5}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3" opacity="0.8"/>')
    lines.append(f'<text x="{pad_l + 162}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Tolerance</text>')
    lines.append(f'<text x="{pad_l + 260}" y="{ly}" fill="#22c55e" font-size="10" font-family="monospace">% = compliance</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_dashboard() -> str:
    svg1 = build_scatter_svg()
    svg2 = build_boxplot_svg()

    comp_rows = ""
    labels_map = {"dx": "Δx", "dy": "Δy", "dz": "Δz",
                  "droll": "Δroll", "dpitch": "Δpitch", "dyaw": "Δyaw"}
    for k, lbl in labels_map.items():
        comp = COMPLIANCE[k]
        tol  = TOLERANCES[k]
        avg  = round(sum(abs(e[k]) for e in EPISODES) / N_EPISODES, 2)
        unit = "mm" if k in ("dx", "dy", "dz") else "°"
        status = "PASS" if comp >= 0.80 else "WARN"
        color  = "#22c55e" if status == "PASS" else "#f59e0b"
        comp_rows += f"""
        <tr>
          <td style="color:#f1f5f9">{lbl}</td>
          <td style="color:#38bdf8">{avg} {unit}</td>
          <td style="color:#64748b">±{tol} {unit}</td>
          <td style="color:{color}">{comp:.1%}</td>
          <td><span style="background:{color};color:#0f172a;padding:2px 8px;border-radius:4px;font-size:11px">{status}</span></td>
        </tr>"""

    avg_pos_err = round(sum(e["dist_3d_mm"] for e in EPISODES) / N_EPISODES, 2)
    avg_ori_err = round(sum(math.sqrt(e["droll"]**2 + e["dpitch"]**2 + e["dyaw"]**2)
                           for e in EPISODES) / N_EPISODES, 2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Robot Pose Estimator — Port 8261</title>
<style>
  body {{background:#0f172a;color:#f1f5f9;font-family:monospace;margin:0;padding:20px}}
  h1   {{color:#C74634;margin-bottom:4px}}
  h2   {{color:#38bdf8;font-size:14px;margin:20px 0 8px}}
  .card{{background:#1e293b;border-radius:8px;padding:16px;margin-bottom:16px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
  .kpi {{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
  .kpi .val{{font-size:26px;font-weight:bold;color:#C74634}}
  .kpi .lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
  .charts{{display:flex;gap:16px;align-items:flex-start}}
  .chart-left{{flex-shrink:0}}
  .chart-right{{flex:1}}
</style>
</head>
<body>
<h1>Robot Pose Estimator</h1>
<p style="color:#64748b">End-Effector Pose Accuracy · {N_EPISODES} episodes · Port 8261</p>

<div class="kpi-grid">
  <div class="kpi"><div class="val">{avg_pos_err}mm</div><div class="lbl">Avg Position Error (3D)</div></div>
  <div class="kpi"><div class="val">{avg_ori_err:.1f}°</div><div class="lbl">Avg Orientation Error</div></div>
  <div class="kpi"><div class="val">{SUCCESS_RATE:.0%}</div><div class="lbl">Task Success Rate</div></div>
  <div class="kpi"><div class="val">{COMPLIANCE['dz']:.0%}</div><div class="lbl">Δz Compliance (tightest)</div></div>
</div>

<div class="card">
  <h2>EE Pose Scatter + Box Plots</h2>
  <div class="charts">
    <div class="chart-left">{svg1}</div>
  </div>
  {svg2}
</div>

<div class="card">
  <h2>Per-Component Compliance Report</h2>
  <table>
    <thead><tr><th>Component</th><th>Avg Error</th><th>Tolerance</th><th>Compliance</th><th>Status</th></tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
  <p style="color:#64748b;font-size:11px;margin-top:10px">
    Note: Δz shows highest variance — placement height sensitivity; orientation compliance above 80% threshold.
  </p>
</div>

<div class="card">
  <h2>Failure Mode Correlation</h2>
  <table>
    <thead><tr><th>Failure Mode</th><th>Correlated Component</th><th>Frequency</th><th>Avg Error When Failing</th></tr></thead>
    <tbody>
      <tr><td style="color:#f1f5f9">Missed grasp</td><td style="color:#38bdf8">Δz + Δroll</td><td style="color:#C74634">8.2%</td><td style="color:#94a3b8">Δz: 9.1mm, Δroll: 5.8°</td></tr>
      <tr><td style="color:#f1f5f9">Object drop</td><td style="color:#38bdf8">Δyaw</td><td style="color:#C74634">4.7%</td><td style="color:#94a3b8">Δyaw: 7.3°</td></tr>
      <tr><td style="color:#f1f5f9">Placement off-target</td><td style="color:#38bdf8">Δx + Δy</td><td style="color:#C74634">9.1%</td><td style="color:#94a3b8">Δx: 8.4mm, Δy: 7.9mm</td></tr>
      <tr><td style="color:#f1f5f9">Collision near target</td><td style="color:#38bdf8">Δpitch</td><td style="color:#C74634">3.2%</td><td style="color:#94a3b8">Δpitch: 6.1°</td></tr>
    </tbody>
  </table>
</div>

<p style="color:#334155;font-size:10px;margin-top:20px">OCI Robot Cloud · Robot Pose Estimator v1.0 · cycle-50A</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI / stdlib server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Robot Pose Estimator", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(build_dashboard())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "robot_pose_estimator", "port": 8261}

    @app.get("/api/compliance")
    async def api_compliance():
        return COMPLIANCE

    @app.get("/api/boxstats")
    async def api_boxstats():
        return BOX_STATS

    @app.get("/api/summary")
    async def api_summary():
        return {
            "n_episodes": N_EPISODES,
            "success_rate": SUCCESS_RATE,
            "avg_position_error_mm": round(sum(e["dist_3d_mm"] for e in EPISODES) / N_EPISODES, 2),
            "compliance": COMPLIANCE,
        }

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8261)
    else:
        print("[pose_estimator] FastAPI not found — using stdlib http.server on port 8261")
        server = http.server.HTTPServer(("0.0.0.0", 8261), Handler)
        server.serve_forever()
