"""policy_smoothing_v2.py — Advanced policy output smoothing with temporal consistency.

FastAPI service on port 8312.
Cycle-63A: OCI Robot Cloud
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
random.seed(42)

SMOOTHING_METHODS = {
    "raw": {"jerk": 2.81, "sr": 0.78, "latency_ms": 0.0, "label": "Raw Policy"},
    "exponential": {"jerk": 2.12, "sr": 0.780, "latency_ms": 0.3, "label": "Exponential"},
    "savgol": {"jerk": 1.74, "sr": 0.775, "latency_ms": 1.2, "label": "Savgol"},
    "chunk_blend": {"jerk": 2.44, "sr": 0.780, "latency_ms": 0.6, "label": "Chunk Blend"},
    "learned_prior": {"jerk": 1.60, "sr": 0.780, "latency_ms": 2.1, "label": "Learned Prior"},
}

RECOMMENDATIONS = [
    {"use_case": "Real-time control (<1ms budget)", "method": "exponential", "reason": "Zero overhead, good jerk reduction"},
    {"use_case": "Standard deployment", "method": "savgol", "reason": "Best jerk/SR tradeoff under 2ms"},
    {"use_case": "High-fidelity fine-tuning", "method": "learned_prior", "reason": "Maximum jerk reduction, SR preserved"},
    {"use_case": "Chunk-action policies", "method": "chunk_blend", "reason": "Optimised for action chunking boundaries"},
]


def _generate_trajectory_data(steps: int = 200) -> Dict[str, Any]:
    """Generate mock joint_4 and ee_z trajectories for raw vs smoothed comparison."""
    t = [i for i in range(steps)]

    # Raw jagged signal
    raw_j4 = []
    raw_eez = []
    base_j4 = 0.0
    base_eez = 0.5
    for i in range(steps):
        base_j4 += 0.02 * math.sin(i * 0.15) + random.gauss(0, 0.08)
        base_eez += 0.01 * math.cos(i * 0.1) + random.gauss(0, 0.06)
        raw_j4.append(round(base_j4, 4))
        raw_eez.append(round(base_eez, 4))

    # Exponential smoothed
    alpha = 0.25
    exp_j4 = [raw_j4[0]]
    exp_eez = [raw_eez[0]]
    for i in range(1, steps):
        exp_j4.append(round(alpha * raw_j4[i] + (1 - alpha) * exp_j4[-1], 4))
        exp_eez.append(round(alpha * raw_eez[i] + (1 - alpha) * exp_eez[-1], 4))

    # Savgol-like (wider window average)
    window = 7
    savgol_j4 = []
    savgol_eez = []
    for i in range(steps):
        lo, hi = max(0, i - window // 2), min(steps, i + window // 2 + 1)
        savgol_j4.append(round(sum(raw_j4[lo:hi]) / (hi - lo), 4))
        savgol_eez.append(round(sum(raw_eez[lo:hi]) / (hi - lo), 4))

    # Learned prior (smoothest, slight phase boundary artifact at step 66 and 133)
    lp_j4 = list(savgol_j4)
    lp_eez = list(savgol_eez)
    for boundary in [66, 133]:
        for offset in range(-2, 3):
            idx = boundary + offset
            if 0 <= idx < steps:
                lp_j4[idx] += random.gauss(0, 0.03)
                lp_eez[idx] += random.gauss(0, 0.02)

    return {
        "t": t, "raw_j4": raw_j4, "raw_eez": raw_eez,
        "exp_j4": exp_j4, "exp_eez": exp_eez,
        "savgol_j4": savgol_j4, "savgol_eez": savgol_eez,
        "lp_j4": lp_j4, "lp_eez": lp_eez,
    }


def _svg_trajectory(traj: Dict[str, Any]) -> str:
    """SVG: Before/after smoothing trajectory (joint_4 and ee_z, 200 steps)."""
    W, H = 760, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 30, 45
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    steps = len(traj["t"])

    all_vals = traj["raw_j4"] + traj["exp_j4"] + traj["savgol_j4"] + traj["lp_j4"]
    y_min, y_max = min(all_vals) - 0.1, max(all_vals) + 0.1

    def sx(i):
        return PAD_L + (i / (steps - 1)) * plot_w

    def sy(v):
        return PAD_T + (1 - (v - y_min) / (y_max - y_min)) * plot_h

    def polyline(vals, color, width=1.5, dash=""):
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
        dash_attr = f'stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" {dash_attr}/>'

    lines = [
        polyline(traj["raw_j4"], "#64748b", 1.0, "4,3"),
        polyline(traj["exp_j4"], "#f59e0b", 1.5),
        polyline(traj["savgol_j4"], "#38bdf8", 1.8),
        polyline(traj["lp_j4"], "#C74634", 2.0),
    ]

    # Phase boundary annotations
    boundary_lines = ""
    for b in [66, 133]:
        bx = sx(b)
        boundary_lines += (
            f'<line x1="{bx:.1f}" y1="{PAD_T}" x2="{bx:.1f}" y2="{PAD_T + plot_h}" '
            f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="{bx + 3:.1f}" y="{PAD_T + 12}" fill="#94a3b8" font-size="9">phase boundary</text>'
        )

    # Axes
    axes = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{PAD_L + plot_w}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    # Y-axis ticks
    yticks = ""
    for i in range(5):
        v = y_min + i * (y_max - y_min) / 4
        yy = sy(v)
        yticks += f'<text x="{PAD_L - 6}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{v:.2f}</text>'
        yticks += f'<line x1="{PAD_L - 3}" y1="{yy:.1f}" x2="{PAD_L}" y2="{yy:.1f}" stroke="#475569" stroke-width="1"/>'

    # X-axis ticks
    xticks = ""
    for i in [0, 50, 100, 150, 199]:
        xx = sx(i)
        xticks += f'<text x="{xx:.1f}" y="{PAD_T + plot_h + 15}" fill="#94a3b8" font-size="9" text-anchor="middle">{i}</text>'

    # Legend
    legend = (
        f'<rect x="{PAD_L + 10}" y="{PAD_T + 5}" width="10" height="3" fill="#64748b"/>'
        f'<text x="{PAD_L + 24}" y="{PAD_T + 11}" fill="#94a3b8" font-size="9">Raw</text>'
        f'<rect x="{PAD_L + 60}" y="{PAD_T + 5}" width="10" height="3" fill="#f59e0b"/>'
        f'<text x="{PAD_L + 74}" y="{PAD_T + 11}" fill="#94a3b8" font-size="9">Exponential</text>'
        f'<rect x="{PAD_L + 145}" y="{PAD_T + 5}" width="10" height="3" fill="#38bdf8"/>'
        f'<text x="{PAD_L + 159}" y="{PAD_T + 11}" fill="#94a3b8" font-size="9">Savgol</text>'
        f'<rect x="{PAD_L + 210}" y="{PAD_T + 5}" width="10" height="3" fill="#C74634"/>'
        f'<text x="{PAD_L + 224}" y="{PAD_T + 11}" fill="#94a3b8" font-size="9">Learned Prior</text>'
    )

    title = f'<text x="{W // 2}" y="15" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">joint_4 Smoothing Comparison (200 steps)</text>'
    xlabel = f'<text x="{PAD_L + plot_w // 2}" y="{H - 5}" fill="#94a3b8" font-size="9" text-anchor="middle">Step</text>'
    ylabel = f'<text x="12" y="{PAD_T + plot_h // 2}" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90 12 {PAD_T + plot_h // 2})">joint_4 value</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
        + title + axes + yticks + xticks + boundary_lines
        + "".join(lines) + legend + xlabel + ylabel
        + "</svg>"
    )


def _svg_scatter() -> str:
    """SVG: Scatter of 5 smoothing methods by (jerk_reduction%, SR_impact) with Pareto frontier."""
    W, H = 520, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 65, 30, 40, 55
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    # Data: (jerk_reduction_pct, sr_impact_pp, label, color)
    raw_jerk = 2.81
    methods_scatter = [
        (0.0, 0.0, "Raw", "#64748b"),
        ((raw_jerk - 2.12) / raw_jerk * 100, 0.0, "Exponential", "#f59e0b"),
        ((raw_jerk - 1.74) / raw_jerk * 100, -0.5, "Savgol", "#38bdf8"),
        ((raw_jerk - 2.44) / raw_jerk * 100, 0.0, "Chunk Blend", "#a78bfa"),
        ((raw_jerk - 1.60) / raw_jerk * 100, 0.0, "Learned Prior", "#C74634"),
    ]

    x_min, x_max = -5.0, 50.0
    y_min, y_max = -1.5, 1.5

    def sx(v):
        return PAD_L + (v - x_min) / (x_max - x_min) * plot_w

    def sy(v):
        return PAD_T + (1 - (v - y_min) / (y_max - y_min)) * plot_h

    # Pareto frontier (best jerk reduction without SR loss)
    pareto_pts = [
        (0.0, 0.0),
        ((raw_jerk - 2.12) / raw_jerk * 100, 0.0),
        ((raw_jerk - 1.60) / raw_jerk * 100, 0.0),
    ]
    pareto_sorted = sorted(pareto_pts, key=lambda p: p[0])
    pareto_path = " ".join(f"{sx(p[0]):.1f},{sy(p[1]):.1f}" for p in pareto_sorted)

    axes = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{PAD_L + plot_w}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{sy(0):.1f}" x2="{PAD_L + plot_w}" y2="{sy(0):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    xticks = ""
    for v in [0, 10, 20, 30, 40]:
        xx = sx(v)
        xticks += f'<text x="{xx:.1f}" y="{PAD_T + plot_h + 15}" fill="#94a3b8" font-size="9" text-anchor="middle">{v}%</text>'
        xticks += f'<line x1="{xx:.1f}" y1="{PAD_T + plot_h}" x2="{xx:.1f}" y2="{PAD_T + plot_h + 4}" stroke="#475569" stroke-width="1"/>'

    yticks = ""
    for v in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        yy = sy(v)
        yticks += f'<text x="{PAD_L - 6}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{v:+.1f}pp</text>'
        yticks += f'<line x1="{PAD_L - 3}" y1="{yy:.1f}" x2="{PAD_L}" y2="{yy:.1f}" stroke="#475569" stroke-width="1"/>'

    pareto_line = (
        f'<polyline points="{pareto_path}" fill="none" stroke="#22d3ee" '
        f'stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        f'<text x="{sx(20):.1f}" y="{sy(0.4):.1f}" fill="#22d3ee" font-size="9">Pareto frontier</text>'
    )

    dots = ""
    for jk, sr, label, color in methods_scatter:
        cx, cy = sx(jk), sy(sr)
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" opacity="0.9"/>'
        offset_x = 10 if jk < 35 else -12
        dots += f'<text x="{cx + offset_x:.1f}" y="{cy - 9:.1f}" fill="#e2e8f0" font-size="9">{label}</text>'

    title = f'<text x="{W // 2}" y="20" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">Smoothing Methods: Jerk Reduction vs SR Impact</text>'
    xlabel = f'<text x="{PAD_L + plot_w // 2}" y="{H - 8}" fill="#94a3b8" font-size="9" text-anchor="middle">Jerk Reduction (%)</text>'
    ylabel = f'<text x="13" y="{PAD_T + plot_h // 2}" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90 13 {PAD_T + plot_h // 2})">SR Impact (pp)</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
        + title + axes + yticks + xticks + pareto_line + dots + xlabel + ylabel
        + "</svg>"
    )


def _build_html() -> str:
    traj = _generate_trajectory_data(200)
    svg1 = _svg_trajectory(traj)
    svg2 = _svg_scatter()

    rows = ""
    raw_jerk = SMOOTHING_METHODS["raw"]["jerk"]
    for key, m in SMOOTHING_METHODS.items():
        jerk_red = (raw_jerk - m["jerk"]) / raw_jerk * 100 if key != "raw" else 0.0
        sr_delta = m["sr"] - SMOOTHING_METHODS["raw"]["sr"]
        badge = '<span style="background:#C74634;color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;">BEST</span>' if key == "learned_prior" else ""
        rows += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:8px 12px;">{m["label"]} {badge}</td>'
            f'<td style="padding:8px 12px;text-align:right;">{m["jerk"]:.2f}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#38bdf8;">{jerk_red:.1f}%</td>'
            f'<td style="padding:8px 12px;text-align:right;">{m["sr"]:.3f}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:{"#ef4444" if sr_delta < 0 else "#94a3b8"}">{sr_delta:+.3f}</td>'
            f'<td style="padding:8px 12px;text-align:right;">{m["latency_ms"]:.1f} ms</td>'
            f'</tr>'
        )

    rec_rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b;">'
        f'<td style="padding:8px 12px;color:#38bdf8;">{r["use_case"]}</td>'
        f'<td style="padding:8px 12px;color:#C74634;font-weight:600;">{r["method"]}</td>'
        f'<td style="padding:8px 12px;color:#94a3b8;">{r["reason"]}</td>'
        f'</tr>'
        for r in RECOMMENDATIONS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Policy Smoothing v2 — Port 8312</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }}
    .badge {{ background: #1e3a5f; color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .kpi {{ background: #1e293b; border-radius: 8px; padding: 14px 18px; border-left: 3px solid #C74634; }}
    .kpi .val {{ font-size: 1.7rem; font-weight: 700; color: #C74634; }}
    .kpi .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
    tr:hover {{ background: #0f172a44; }}
    .svgs {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  </style>
</head>
<body>
  <h1>Policy Smoothing v2 <span class="badge">Port 8312</span></h1>
  <p class="subtitle">Advanced policy output smoothing with temporal consistency enforcement — OCI Robot Cloud</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="val">-43%</div><div class="lbl">Best Jerk Reduction (learned_prior)</div></div>
    <div class="kpi"><div class="val">0.780</div><div class="lbl">Success Rate (learned_prior, preserved)</div></div>
    <div class="kpi"><div class="val">5</div><div class="lbl">Smoothing Methods Evaluated</div></div>
    <div class="kpi"><div class="val">2.1 ms</div><div class="lbl">Learned Prior Latency Overhead</div></div>
  </div>

  <div class="section">
    <h2>SVG 1 — Before/After Smoothing Trajectory (joint_4, 200 steps)</h2>
    <div class="svgs">{svg1}</div>
    <p style="color:#64748b;font-size:0.75rem;margin-top:8px;">Dashed vertical lines mark phase boundaries (step 66, 133). Smoothing artifact visible in Learned Prior at boundaries.</p>
  </div>

  <div class="section">
    <h2>SVG 2 — Jerk Reduction vs SR Impact Scatter (Pareto Frontier)</h2>
    <div class="svgs">{svg2}</div>
    <p style="color:#64748b;font-size:0.75rem;margin-top:8px;">Learned Prior sits on Pareto frontier: maximum jerk reduction with zero SR penalty. Savgol runner-up (-38%, -0.5pp SR).</p>
  </div>

  <div class="section">
    <h2>Smoothing Method Comparison</h2>
    <table>
      <thead><tr>
        <th>Method</th><th style="text-align:right;">Jerk Score</th><th style="text-align:right;">Jerk Reduction</th>
        <th style="text-align:right;">SR</th><th style="text-align:right;">SR Delta</th><th style="text-align:right;">Latency Overhead</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Recommendations by Use Case</h2>
    <table>
      <thead><tr><th>Use Case</th><th>Recommended Method</th><th>Reason</th></tr></thead>
      <tbody>{rec_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Policy Smoothing v2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_smoothing_v2", "port": 8312}

    @app.get("/api/methods")
    async def methods():
        return SMOOTHING_METHODS

    @app.get("/api/recommendations")
    async def recommendations():
        return RECOMMENDATIONS

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
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
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8312)
    else:
        with socketserver.TCPServer(("", 8312), Handler) as srv:
            print("Serving on http://0.0.0.0:8312 (stdlib fallback)")
            srv.serve_forever()
