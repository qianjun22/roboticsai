#!/usr/bin/env python3
"""
real_robot_eval_v2.py — Enhanced real-world robot evaluation service
Port: 8336
Dashboard: sim-real comparison + test session timeline
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
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

METRICS = [
    {"name": "SR",                  "sim": 0.81, "real": 0.71, "unit": "",    "higher_better": True},
    {"name": "Latency",             "sim": 226,  "real": 241,  "unit": "ms",  "higher_better": False},
    {"name": "Grasp Force Var",     "sim": 0.18, "real": 0.12, "unit": "",    "higher_better": False},
    {"name": "Traj Smoothness",     "sim": 0.87, "real": 0.79, "unit": "",    "higher_better": True},
    {"name": "Recovery Rate",       "sim": 0.64, "real": 0.58, "unit": "",    "higher_better": True},
]

SESSIONS = [
    {"id": "PI_SF_Jan",     "lab": "Physical Intelligence SF",  "month": "Jan 2026",
     "planned": 20, "completed": 18, "success": 11, "hw_issues": 2, "sr": 0.62},
    {"id": "Apt_Austin_Feb","lab": "Apptronik Austin",           "month": "Feb 2026",
     "planned": 20, "completed": 20, "success": 14, "hw_issues": 1, "sr": 0.68},
    {"id": "PI_SF_Mar",     "lab": "Physical Intelligence SF",  "month": "Mar 2026",
     "planned": 22, "completed": 22, "success": 16, "hw_issues": 0, "sr": 0.71},
]

TOTAL_REAL_EPISODES = sum(s["completed"] for s in SESSIONS)
AVG_REAL_SR = round(sum(s["sr"] for s in SESSIONS) / len(SESSIONS), 3)

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_sim_real_comparison() -> str:
    """Side-by-side bar chart: sim vs real for 5 metrics, with gap annotation."""
    W, H = 760, 340
    pad_l, pad_r, pad_t, pad_b = 90, 30, 40, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    # Normalise all metrics to 0-1 scale for bar height comparison
    def norm(metric, val):
        if metric["unit"] == "ms":
            # invert: lower latency → higher bar conceptually; show absolute
            return val / 300
        return float(val)

    n = len(METRICS)
    group_w = chart_w / n
    bar_w = group_w * 0.28
    gap = group_w * 0.08

    bars_svg = ""
    labels_svg = ""
    gap_svg = ""
    legend_svg = ""

    for i, m in enumerate(METRICS):
        x_group = pad_l + i * group_w + group_w * 0.1

        sim_norm = norm(m, m["sim"])
        real_norm = norm(m, m["real"])

        sim_h = sim_norm * chart_h * 0.82
        real_h = real_norm * chart_h * 0.82

        x_sim = x_group
        x_real = x_group + bar_w + gap

        y_sim = pad_t + chart_h - sim_h
        y_real = pad_t + chart_h - real_h

        bars_svg += (
            f'<rect x="{x_sim:.1f}" y="{y_sim:.1f}" width="{bar_w:.1f}" height="{sim_h:.1f}" '
            f'fill="#38bdf8" rx="2"/>\n'
            f'<rect x="{x_real:.1f}" y="{y_real:.1f}" width="{bar_w:.1f}" height="{real_h:.1f}" '
            f'fill="#C74634" rx="2"/>\n'
        )

        # value labels
        sim_lbl = f"{m['sim']}"
        real_lbl = f"{m['real']}"
        bars_svg += (
            f'<text x="{x_sim + bar_w/2:.1f}" y="{y_sim - 5:.1f}" '
            f'fill="#38bdf8" font-size="9" text-anchor="middle">{sim_lbl}</text>\n'
            f'<text x="{x_real + bar_w/2:.1f}" y="{y_real - 5:.1f}" '
            f'fill="#C74634" font-size="9" text-anchor="middle">{real_lbl}</text>\n'
        )

        # gap annotation
        if m["unit"] == "ms":
            gap_val = m["real"] - m["sim"]
            gap_str = f"+{gap_val}ms"
        elif m["name"] == "Grasp Force Var":
            gap_val = round(m["sim"] - m["real"], 2)
            gap_str = f"real -{gap_val} better"
        else:
            gap_val = round(m["sim"] - m["real"], 2)
            gap_str = f"gap {gap_val}"

        gap_svg += (
            f'<text x="{x_group + bar_w + gap/2:.1f}" y="{pad_t + chart_h + 30:.1f}" '
            f'fill="#94a3b8" font-size="8" text-anchor="middle">{gap_str}</text>\n'
        )

        # metric name label
        lx = x_group + bar_w + gap / 2
        labels_svg += (
            f'<text x="{lx:.1f}" y="{pad_t + chart_h + 16:.1f}" '
            f'fill="#cbd5e1" font-size="10" text-anchor="middle">{m["name"]}</text>\n'
        )

    # axes
    axis_svg = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" '
        f'stroke="#334155" stroke-width="1"/>\n'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" '
        f'stroke="#334155" stroke-width="1"/>\n'
    )

    # legend
    legend_svg = (
        f'<rect x="{W - pad_r - 120}" y="{pad_t}" width="12" height="12" fill="#38bdf8" rx="2"/>'
        f'<text x="{W - pad_r - 105}" y="{pad_t + 10}" fill="#cbd5e1" font-size="11">Sim (GR00T_v2)</text>'
        f'<rect x="{W - pad_r - 120}" y="{pad_t + 18}" width="12" height="12" fill="#C74634" rx="2"/>'
        f'<text x="{W - pad_r - 105}" y="{pad_t + 28}" fill="#cbd5e1" font-size="11">Real Robot</text>'
    )

    title = f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">GR00T_v2 Sim vs Real — Per-Metric Comparison</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{title}{axis_svg}{bars_svg}{labels_svg}{gap_svg}{legend_svg}'
        f'</svg>'
    )


def svg_session_timeline() -> str:
    """3 real eval sessions timeline — planned/completed/success bars + SR trend."""
    W, H = 760, 320
    pad_l, pad_r, pad_t, pad_b = 60, 40, 50, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(SESSIONS)
    group_w = chart_w / n
    bar_w = group_w * 0.22
    spacing = group_w * 0.06

    bars_svg = ""
    labels_svg = ""
    trend_pts = []

    max_eps = 25

    for i, s in enumerate(SESSIONS):
        x0 = pad_l + i * group_w + group_w * 0.08

        def bar(x_off, val, color, label):
            bh = (val / max_eps) * chart_h * 0.85
            by = pad_t + chart_h - bh
            bx = x0 + x_off * (bar_w + spacing)
            return (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" rx="2"/>'
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="{color}" '
            f'font-size="9" text-anchor="middle">{val}</text>'
        )

        bars_svg += bar(0, s["planned"],   "#475569", "planned")
        bars_svg += bar(1, s["completed"], "#38bdf8",  "done")
        bars_svg += bar(2, s["success"],   "#22c55e",  "success")

        # hw issues badge
        if s["hw_issues"] > 0:
            bx_hw = x0 + 3 * (bar_w + spacing)
            bars_svg += (
                f'<rect x="{bx_hw:.1f}" y="{pad_t + 8:.1f}" width="38" height="16" '
                f'fill="#7f1d1d" rx="3"/>'
                f'<text x="{bx_hw + 19:.1f}" y="{pad_t + 19:.1f}" fill="#fca5a5" '
                f'font-size="9" text-anchor="middle">HW {s["hw_issues"]}x</text>'
            )

        # session label
        lx = x0 + 1.5 * (bar_w + spacing)
        labels_svg += (
            f'<text x="{lx:.1f}" y="{pad_t + chart_h + 16:.1f}" '
            f'fill="#94a3b8" font-size="9" text-anchor="middle">{s["id"]}</text>'
            f'<text x="{lx:.1f}" y="{pad_t + chart_h + 28:.1f}" '
            f'fill="#64748b" font-size="9" text-anchor="middle">{s["month"]}</text>'
        )

        # trend point for SR
        tx = x0 + 1.5 * (bar_w + spacing)
        ty = pad_t + chart_h - (s["sr"] / 1.0) * chart_h * 0.85
        trend_pts.append((tx, ty, s["sr"]))

    # SR trend line
    trend_svg = ""
    for j in range(len(trend_pts) - 1):
        x1, y1, _ = trend_pts[j]
        x2, y2, _ = trend_pts[j + 1]
        trend_svg += (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,2"/>'
        )
    for tx, ty, sr in trend_pts:
        trend_svg += (
            f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="5" fill="#f59e0b"/>'
            f'<text x="{tx:.1f}" y="{ty - 9:.1f}" fill="#f59e0b" '
            f'font-size="10" text-anchor="middle" font-weight="bold">SR {sr}</text>'
        )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>'
    )

    legend = (
        f'<rect x="{pad_l}" y="{pad_t - 32}" width="10" height="10" fill="#475569" rx="2"/>'
        f'<text x="{pad_l + 14}" y="{pad_t - 23}" fill="#94a3b8" font-size="10">Planned</text>'
        f'<rect x="{pad_l + 75}" y="{pad_t - 32}" width="10" height="10" fill="#38bdf8" rx="2"/>'
        f'<text x="{pad_l + 89}" y="{pad_t - 23}" fill="#94a3b8" font-size="10">Completed</text>'
        f'<rect x="{pad_l + 175}" y="{pad_t - 32}" width="10" height="10" fill="#22c55e" rx="2"/>'
        f'<text x="{pad_l + 189}" y="{pad_t - 23}" fill="#94a3b8" font-size="10">Success</text>'
        f'<line x1="{pad_l + 260}" y1="{pad_t - 27}" x2="{pad_l + 282}" y2="{pad_t - 27}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,2"/>'
        f'<text x="{pad_l + 286}" y="{pad_t - 23}" fill="#f59e0b" font-size="10">SR Trend</text>'
    )

    title = f'<text x="{W//2}" y="18" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Real Robot Eval Sessions — Partner Lab Timeline</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{title}{axes}{bars_svg}{labels_svg}{trend_svg}{legend}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_sim_real_comparison()
    svg2 = svg_session_timeline()

    sim_sr = METRICS[0]["sim"]
    real_sr = METRICS[0]["real"]
    gap_pp = round((sim_sr - real_sr) * 100, 1)
    lat_gap = METRICS[1]["real"] - METRICS[1]["sim"]
    sr_trend = f"{SESSIONS[0]['sr']} → {SESSIONS[1]['sr']} → {SESSIONS[2]['sr']}"

    stat_cards = "".join([
        f'<div class="card"><div class="label">{lbl}</div><div class="value" style="color:{col}">{val}</div></div>'
        for lbl, val, col in [
            ("Real SR (latest)",      f"{real_sr}",              "#22c55e"),
            ("Sim SR",                f"{sim_sr}",               "#38bdf8"),
            ("Sim-Real Gap",          f"{gap_pp} pp",            "#f59e0b"),
            ("Latency Gap",           f"+{lat_gap} ms",          "#C74634"),
            ("Total Real Episodes",   f"{TOTAL_REAL_EPISODES}",  "#a78bfa"),
            ("SR Trend",              sr_trend,                   "#34d399"),
        ]
    ])

    session_rows = "".join([
        f'<tr><td>{s["id"]}</td><td>{s["lab"]}</td><td>{s["month"]}</td>'
        f'<td>{s["planned"]}</td><td>{s["completed"]}</td><td>{s["success"]}</td>'
        f'<td style="color:{"#ef4444" if s["hw_issues"] > 0 else "#22c55e"}">{s["hw_issues"]}</td>'
        f'<td style="color:#f59e0b">{s["sr"]}</td></tr>'
        for s in SESSIONS
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Real Robot Eval v2 — Port 8336</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 20px; }}
  .oracle-badge {{ display:inline-block; background:#C74634; color:#fff; font-size:0.72rem;
                   padding:2px 10px; border-radius:4px; margin-left:12px; vertical-align:middle; }}
  .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:14px 20px; min-width:160px; }}
  .label {{ font-size:0.72rem; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }}
  .value {{ font-size:1.3rem; font-weight:700; }}
  .section {{ margin-bottom:28px; }}
  h2 {{ font-size:1rem; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px; }}
  svg {{ max-width:100%; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.85rem; }}
  th {{ background:#1e293b; color:#64748b; text-transform:uppercase; font-size:0.72rem;
        letter-spacing:.05em; padding:8px 12px; text-align:left; border-bottom:1px solid #334155; }}
  td {{ padding:8px 12px; border-bottom:1px solid #1e293b; color:#cbd5e1; }}
  tr:hover td {{ background:#1e293b; }}
  .footer {{ color:#475569; font-size:0.75rem; margin-top:24px; }}
</style>
</head>
<body>
<h1>Real Robot Eval v2 <span class="oracle-badge">OCI Robot Cloud</span></h1>
<p class="subtitle">Enhanced real-world evaluation — multi-metric sim-real comparison · partner lab sessions · Port 8336</p>

<div class="stats">{stat_cards}</div>

<div class="section">
  <h2>Sim vs Real — Per-Metric Comparison</h2>
  {svg1}
</div>

<div class="section">
  <h2>Partner Lab Eval Sessions</h2>
  {svg2}
</div>

<div class="section">
  <h2>Session Details</h2>
  <table>
    <thead><tr>
      <th>Session ID</th><th>Lab</th><th>Month</th>
      <th>Planned</th><th>Completed</th><th>Success</th><th>HW Issues</th><th>SR</th>
    </tr></thead>
    <tbody>{session_rows}</tbody>
  </table>
</div>

<div class="footer">Real Robot Eval v2 · OCI Robot Cloud · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Real Robot Eval v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/api/metrics")
    def api_metrics():
        return {"metrics": METRICS, "sessions": SESSIONS,
                "total_real_episodes": TOTAL_REAL_EPISODES,
                "avg_real_sr": AVG_REAL_SR}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "real_robot_eval_v2", "port": 8336}

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
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
        uvicorn.run(app, host="0.0.0.0", port=8336)
    else:
        srv = http.server.HTTPServer(("0.0.0.0", 8336), Handler)
        print("Serving on http://0.0.0.0:8336 (stdlib fallback)")
        srv.serve_forever()
