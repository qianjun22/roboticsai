"""sdk_usage_dashboard_v2.py — FastAPI service on port 8255

Enhanced SDK usage analytics with cohort analysis and feature
adoption funnels. Tracks user journey from download through
enterprise upgrade with weekly cohort retention heatmap.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from typing import List, Dict, Any, Tuple

random.seed(99)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ACTIVE_USERS = 78
ACTIVATION_RATE = 0.83          # first fine_tune within 7 days
FOUR_WEEK_RETENTION_V03 = 0.79  # v0.3.0 cohort week-4 retention
FOUR_WEEK_RETENTION_V02 = 0.58  # v0.2 cohort week-4 retention
ENTERPRISE_CONVERSION = 0.19

# SDK funnel stages
FUNNEL_STAGES = [
    {"name": "download",           "count": 347, "color": "#38bdf8"},
    {"name": "first_call",         "count": 289, "color": "#818cf8"},
    {"name": "fine_tune",          "count": 178, "color": "#22c55e"},
    {"name": "eval_integration",   "count": 143, "color": "#f59e0b"},
    {"name": "production",         "count":  94, "color": "#e879f9"},
    {"name": "enterprise_upgrade", "count":  31, "color": "#C74634"},
]

# Cohort retention data: 10 cohorts x 10 weeks
# Cohort 0 = oldest (v0.1); cohort 9 = newest (v0.3.1)
# Rows = cohort index; cols = weeks since join (0..9)
COHORT_LABELS = ["v0.1-w1", "v0.1-w2", "v0.2-w1", "v0.2-w2", "v0.2-w3",
                 "v0.3-w1", "v0.3-w2", "v0.3-w3", "v0.3-w4", "v0.3.1-w1"]

# Realistic retention improving with newer versions
BASE_RETENTION = [
    [1.00, 0.71, 0.58, 0.50, 0.44, 0.39, 0.35, 0.33, 0.31, 0.29],  # v0.1-w1
    [1.00, 0.69, 0.55, 0.48, 0.42, 0.38, 0.35, 0.32, 0.30, 0.28],  # v0.1-w2
    [1.00, 0.74, 0.61, 0.53, 0.47, 0.43, 0.40, 0.37, 0.35, 0.33],  # v0.2-w1
    [1.00, 0.76, 0.63, 0.55, 0.50, 0.45, 0.42, 0.39, 0.37, 0.35],  # v0.2-w2
    [1.00, 0.75, 0.62, 0.56, 0.51, 0.47, 0.44, 0.41, 0.38, 0.36],  # v0.2-w3
    [1.00, 0.81, 0.70, 0.64, 0.59, 0.55, 0.51, 0.49, 0.46, 0.44],  # v0.3-w1 (v0.3.0 released)
    [1.00, 0.83, 0.73, 0.67, 0.62, 0.58, 0.55, 0.52, 0.49, 0.47],  # v0.3-w2
    [1.00, 0.84, 0.74, 0.68, 0.63, 0.59, 0.56, 0.53, 0.50, None],  # v0.3-w3 (partial)
    [1.00, 0.85, 0.76, 0.69, 0.64, 0.61, 0.57, None, None, None],  # v0.3-w4 (partial)
    [1.00, 0.87, 0.78, 0.71, None, None, None, None, None, None],  # v0.3.1-w1 (newest)
]


# ---------------------------------------------------------------------------
# SVG 1: Funnel chart
# ---------------------------------------------------------------------------

def _svg_funnel() -> str:
    W, H = 760, 340
    n = len(FUNNEL_STAGES)
    TOP = 50
    BOT = H - 40
    chart_h = BOT - TOP
    BAR_H = int(chart_h / n) - 8
    LEFT = 160
    max_w = W - LEFT - 120
    max_count = FUNNEL_STAGES[0]["count"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">',
        f'<text x="{W//2}" y="28" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">SDK User Journey Funnel — Download → Enterprise Upgrade</text>',
    ]

    for i, stage in enumerate(FUNNEL_STAGES):
        y = TOP + i * (BAR_H + 8)
        bar_w = int((stage["count"] / max_count) * max_w)
        color = stage["color"]

        # bar
        parts.append(f'<rect x="{LEFT}" y="{y}" width="{bar_w}" height="{BAR_H}" fill="{color}" rx="3" opacity="0.85"/>')

        # stage label
        label = stage["name"].replace("_", " ")
        parts.append(f'<text x="{LEFT-8}" y="{y + BAR_H//2 + 4}" fill="#cbd5e1" font-size="11" font-family="monospace" text-anchor="end">{label}</text>')

        # count
        parts.append(f'<text x="{LEFT + bar_w + 8}" y="{y + BAR_H//2 + 4}" fill="{color}" font-size="12" font-family="monospace" font-weight="bold">{stage["count"]}</text>')

        # conversion rate arrow from previous stage
        if i > 0:
            prev = FUNNEL_STAGES[i - 1]["count"]
            rate = stage["count"] / prev
            ax = LEFT + bar_w + 52
            ay = y + BAR_H // 2
            rate_color = "#22c55e" if rate >= 0.70 else "#f59e0b" if rate >= 0.50 else "#C74634"
            parts.append(f'<text x="{ax}" y="{ay + 4}" fill="{rate_color}" font-size="10" font-family="monospace">↓{rate:.0%}</text>')

        # connector line to next
        if i < n - 1:
            next_w = int((FUNNEL_STAGES[i + 1]["count"] / max_count) * max_w)
            ny = y + BAR_H + 8
            # trapezoid connector
            pts = f"{LEFT},{y+BAR_H} {LEFT+bar_w},{y+BAR_H} {LEFT+next_w},{ny} {LEFT},{ny}"
            parts.append(f'<polygon points="{pts}" fill="{color}" opacity="0.18"/>')

    parts.append('</svg>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# SVG 2: Cohort retention heatmap
# ---------------------------------------------------------------------------

def _svg_cohort_heatmap() -> str:
    CELL_W = 56
    CELL_H = 34
    LABEL_W = 86
    TOP = 60
    LEFT = LABEL_W
    N_COHORTS = len(COHORT_LABELS)
    N_WEEKS = 10
    W = LEFT + N_WEEKS * CELL_W + 20
    H = TOP + N_COHORTS * CELL_H + 50

    def retention_color(val):
        if val is None:
            return "#1e293b"
        # blue scale: low retention = dark, high = bright sky blue
        r = int(15 + (1 - val) * 30)
        g = int(30 + val * 120)
        b = int(80 + val * 170)
        return f"rgb({r},{g},{b})"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">',
        f'<text x="{LEFT + N_WEEKS*CELL_W//2}" y="22" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Cohort Retention Heatmap — Weekly Cohorts × Weeks Since Join</text>',
        f'<text x="{LEFT + N_WEEKS*CELL_W//2}" y="40" fill="#f59e0b" font-size="10" font-family="monospace" text-anchor="middle">v0.3.0 release (cohort 5+) shows retention improvement: wk-4 retention 79% vs 58% for v0.2</text>',
    ]

    # column headers (week numbers)
    for w in range(N_WEEKS):
        cx = LEFT + w * CELL_W + CELL_W // 2
        parts.append(f'<text x="{cx}" y="{TOP - 6}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">wk {w}</text>')

    # rows
    for ci, cohort in enumerate(COHORT_LABELS):
        y = TOP + ci * CELL_H
        # row label
        label_color = "#f59e0b" if cohort.startswith("v0.3") else "#94a3b8"
        parts.append(f'<text x="{LEFT - 6}" y="{y + CELL_H//2 + 4}" fill="{label_color}" font-size="9" font-family="monospace" text-anchor="end">{cohort}</text>')

        for w in range(N_WEEKS):
            val = BASE_RETENTION[ci][w]
            x = LEFT + w * CELL_W
            color = retention_color(val)
            parts.append(f'<rect x="{x}" y="{y}" width="{CELL_W-2}" height="{CELL_H-2}" fill="{color}" rx="2"/>')
            if val is not None:
                txt_color = "#0f172a" if val > 0.55 else "#e2e8f0"
                parts.append(f'<text x="{x + CELL_W//2 - 1}" y="{y + CELL_H//2 + 4}" fill="{txt_color}" font-size="9" font-family="monospace" text-anchor="middle">{val:.0%}</text>')
            else:
                parts.append(f'<text x="{x + CELL_W//2 - 1}" y="{y + CELL_H//2 + 4}" fill="#334155" font-size="9" font-family="monospace" text-anchor="middle">—</text>')

    # legend
    ly = TOP + N_COHORTS * CELL_H + 20
    parts.append(f'<text x="{LEFT}" y="{ly}" fill="#64748b" font-size="10" font-family="monospace">Retention %:</text>')
    for i, (label, val) in enumerate([("0%", 0.0), ("25%", 0.25), ("50%", 0.50), ("75%", 0.75), ("100%", 1.0)]):
        lx = LEFT + 90 + i * 70
        color = retention_color(val)
        parts.append(f'<rect x="{lx}" y="{ly-12}" width="20" height="12" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{lx + 24}" y="{ly}" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    svg1 = _svg_funnel()
    svg2 = _svg_cohort_heatmap()

    top_stage = FUNNEL_STAGES[0]["count"]
    ft_stage = next(s for s in FUNNEL_STAGES if s["name"] == "fine_tune")
    activation_count = ft_stage["count"]
    activation_pct = f"{activation_count / top_stage:.0%}"

    metrics = [
        ("Active Users",           str(ACTIVE_USERS),                    "#38bdf8"),
        ("Activation Rate",        f"{ACTIVATION_RATE:.0%}",             "#22c55e"),
        ("4-Wk Retention v0.3",    f"{FOUR_WEEK_RETENTION_V03:.0%}",     "#22c55e"),
        ("4-Wk Retention v0.2",    f"{FOUR_WEEK_RETENTION_V02:.0%}",     "#f59e0b"),
        ("Enterprise Conversion",  f"{ENTERPRISE_CONVERSION:.0%}",       "#C74634"),
        ("First Fine-Tune (7d)",    "51%",                                "#818cf8"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:150px">'
        f'<div style="color:#64748b;font-size:11px;margin-bottom:4px">{label}</div>'
        f'<div style="color:{color};font-size:22px;font-weight:bold;font-family:monospace">{value}</div>'
        f'</div>'
        for label, value, color in metrics
    )

    stage_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#94a3b8">{s["name"].replace("_"," ")}</td>'
        f'<td style="padding:6px 12px;color:{s["color"]};font-weight:bold">{s["count"]}</td>'
        f'<td style="padding:6px 12px;color:#64748b">{s["count"]/top_stage:.1%}</td></tr>'
        for s in FUNNEL_STAGES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SDK Usage Dashboard v2 — Port 8255</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 10px; }}
    .svg-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; margin-top: 12px; }}
    th {{ color: #64748b; font-size: 11px; text-align: left; padding: 4px 12px; }}
  </style>
</head>
<body>
  <h1>SDK Usage Dashboard v2</h1>
  <div class="subtitle">Cohort analysis · Feature adoption funnels · Port 8255 · OCI Robot Cloud</div>

  <div class="cards">{cards}</div>

  <div class="section">
    <h2>User Journey Funnel</h2>
    <div class="svg-wrap">{svg1}</div>
    <table>
      <tr><th>Stage</th><th>Users</th><th>Overall Conv.</th></tr>
      {stage_rows}
    </table>
  </div>

  <div class="section">
    <h2>Cohort Retention Heatmap (Weekly)</h2>
    <div class="svg-wrap">{svg2}</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="SDK Usage Dashboard v2",
        description="Enhanced SDK analytics with cohort analysis and feature adoption funnels",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "sdk_usage_dashboard_v2", "port": 8255}

    @app.get("/metrics")
    def metrics_endpoint():
        return {
            "active_users": ACTIVE_USERS,
            "activation_rate": ACTIVATION_RATE,
            "four_week_retention_v03": FOUR_WEEK_RETENTION_V03,
            "four_week_retention_v02": FOUR_WEEK_RETENTION_V02,
            "enterprise_conversion": ENTERPRISE_CONVERSION,
            "first_fine_tune_7d_rate": 0.51,
        }

    @app.get("/funnel")
    def funnel():
        return {"stages": FUNNEL_STAGES}

    @app.get("/cohorts")
    def cohorts():
        return {
            "labels": COHORT_LABELS,
            "retention": BASE_RETENTION,
            "weeks": list(range(10)),
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "sdk_usage_dashboard_v2", "port": 8255}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8255)
    else:
        print("fastapi not installed — falling back to stdlib http.server on port 8255")
        HTTPServer(("0.0.0.0", 8255), _Handler).serve_forever()
