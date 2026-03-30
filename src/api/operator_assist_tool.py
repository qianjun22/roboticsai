"""operator_assist_tool.py — AI-Assisted Operator Diagnostic Tool (port 8321)

Helps robot operators diagnose issues and get intervention recommendations.
Dark theme dashboard with SVG flowchart and issue-frequency bar chart.
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

ISSUE_CATEGORIES = [
    # (name, count_30d, self_service_pct, avg_min_self, avg_days_escalated, escalation_pct)
    ("SR_drop",         16, 80, 7,  2.1, 20),
    ("latency_spike",    9, 78, 6,  1.8, 22),
    ("grasping_fail",   10, 59, 11, 2.6, 41),
    ("safety_stop",      7, 71, 9,  2.5, 29),
    ("training_plateau", 5, 60, 10, 3.1, 40),
]

KEY_METRICS = {
    "total_queries_30d":        47,
    "self_service_rate":        "71%",
    "avg_time_self_service":    "8 min",
    "avg_time_escalated":       "2.3 days",
    "escalation_rate":          "29%",
    "top_issue":                "SR_drop (34%)",
    "highest_escalation_issue": "grasping_fail (41%)",
    "kb_coverage":              "87 articles",
}

ISSUE_PATHS = [
    # (id, symptom, diagnoses, action, color)
    ("SR_drop",         "SR drop > 5pp",     "model drift / env change",     "trigger DAgger run",    "#C74634"),
    ("latency_spike",   "latency > 300ms",   "GPU overload / net congestion", "scale inference pods", "#f97316"),
    ("grasping_fail",   "grasp success < 60%","IK error / calibration drift", "recalibrate + fine-tune","#eab308"),
    ("safety_stop",     "E-stop triggered",   "collision / OOD pose",         "manual inspection",    "#a855f7"),
    ("training_plateau","loss not improving", "LR too low / data imbalance",  "HPO sweep + augment",  "#38bdf8"),
]


# ---------------------------------------------------------------------------
# SVG 1: Decision support flowchart
# ---------------------------------------------------------------------------

def build_flowchart_svg() -> str:
    W, H = 820, 380

    # Node definitions: (id, x, y, w, h, label, color)
    BOX_W, BOX_H = 140, 38
    INPUT_X, INPUT_Y = 30, 171
    DIAG_X = 230
    ACTION_X = 600

    input_node = (INPUT_X, INPUT_Y, 120, 38, "Operator Input", "#1d4ed8", "#bfdbfe")

    issue_nodes = [
        (DIAG_X, 30  + i * 65, BOX_W, BOX_H, d[0], d[4], "#e2e8f0")
        for i, d in enumerate(ISSUE_PATHS)
    ]

    diag_nodes = [
        (420, 30 + i * 65, 150, BOX_H, d[2], "#164e63", "#38bdf8")
        for i, d in enumerate(ISSUE_PATHS)
    ]

    action_nodes = [
        (ACTION_X, 30 + i * 65, 160, BOX_H, d[3], "#14532d", "#86efac")
        for i, d in enumerate(ISSUE_PATHS)
    ]

    def rect_svg(x, y, w, h, label, bg, fg):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{bg}" stroke="#334155" stroke-width="1"/>'
            f'<text x="{x + w//2}" y="{y + h//2 + 4}" fill="{fg}" font-size="10" text-anchor="middle">{label}</text>'
        )

    def arrow(x1, y1, x2, y2, color="#475569"):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#arr)"/>'

    parts = [
        f'<defs><marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
        f'<polygon points="0 0, 8 3, 0 6" fill="#475569"/></marker></defs>',
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="bold">Operator Diagnostic Decision Flowchart</text>',
    ]

    # Input box
    ix, iy, iw, ih, ilbl, ibg, ifg = input_node
    parts.append(rect_svg(ix, iy, iw, ih, ilbl, ibg, ifg))

    for i, ((nx, ny, nw, nh, nlbl, nbg, nfg), (dx, dy, dw, dh, dlbl, dbg, dfg), (ax, ay, aw, ah, albl, abg, afg)) in enumerate(
        zip(issue_nodes, diag_nodes, action_nodes)
    ):
        # Input → issue
        parts.append(arrow(ix + iw, iy + ih // 2, nx, ny + nh // 2, ISSUE_PATHS[i][4]))
        parts.append(rect_svg(nx, ny, nw, nh, nlbl, nbg, nfg))
        # issue → diagnosis
        parts.append(arrow(nx + nw, ny + nh // 2, dx, dy + dh // 2))
        parts.append(rect_svg(dx, dy, dw, dh, dlbl, dbg, dfg))
        # diagnosis → action
        parts.append(arrow(dx + dw, dy + dh // 2, ax, ay + ah // 2))
        parts.append(rect_svg(ax, ay, aw, ah, albl, abg, afg))

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">'
        + "".join(parts)
        + '</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# SVG 2: Issue frequency bar chart
# ---------------------------------------------------------------------------

def build_bar_chart_svg() -> str:
    W, H = 700, 320
    pad_l, pad_r, pad_t, pad_b = 160, 30, 40, 60
    n = len(ISSUE_CATEGORIES)
    bar_h = 30
    gap = 20
    inner_h = n * (bar_h + gap) - gap
    total_w = W - pad_l - pad_r

    max_count = max(c[1] for c in ISSUE_CATEGORIES)

    parts = [
        f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="bold">30-Day Issue Frequency &amp; Resolution</text>'
    ]

    colors = ["#C74634", "#f97316", "#eab308", "#a855f7", "#38bdf8"]

    for i, (name, count, ss_pct, avg_min, avg_days, esc_pct) in enumerate(ISSUE_CATEGORIES):
        y = pad_t + i * (bar_h + gap)
        bar_w = int(count / max_count * total_w * 0.6)
        ss_w  = int(bar_w * ss_pct / 100)
        esc_w = bar_w - ss_w
        color = colors[i]
        # Label
        parts.append(f'<text x="{pad_l - 8}" y="{y + bar_h//2 + 4}" fill="#94a3b8" font-size="11" text-anchor="end">{name}</text>')
        # Self-service portion
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{ss_w}" height="{bar_h}" rx="3" fill="{color}" opacity="0.9"/>')
        # Escalated portion
        parts.append(f'<rect x="{pad_l + ss_w}" y="{y}" width="{esc_w}" height="{bar_h}" rx="3" fill="{color}" opacity="0.4"/>')
        # Count label
        parts.append(f'<text x="{pad_l + bar_w + 6}" y="{y + bar_h//2 + 4}" fill="#e2e8f0" font-size="11">{count} issues</text>')
        # Avg time
        parts.append(f'<text x="{pad_l + bar_w + 80}" y="{y + bar_h//2 + 4}" fill="#64748b" font-size="10">{avg_min}min / {avg_days}d</text>')

    # Legend
    lx = pad_l
    ly = H - pad_b + 15
    parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="12" fill="#C74634" opacity="0.9"/>')
    parts.append(f'<text x="{lx+18}" y="{ly+10}" fill="#94a3b8" font-size="11">Self-service resolved</text>')
    parts.append(f'<rect x="{lx+170}" y="{ly}" width="14" height="12" fill="#C74634" opacity="0.4"/>')
    parts.append(f'<text x="{lx+188}" y="{ly+10}" fill="#94a3b8" font-size="11">Escalated</text>')
    parts.append(f'<text x="{lx+280}" y="{ly+10}" fill="#64748b" font-size="10">Bar suffix: avg self-service min / avg escalated days</text>')

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">'
        + "".join(parts)
        + '</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    flowchart_svg = build_flowchart_svg()
    bar_svg       = build_bar_chart_svg()
    m = KEY_METRICS
    metric_cards = "".join(
        f'<div class="metric"><div class="mval">{v}</div><div class="mlbl">{k.replace("_"," ")}</div></div>'
        for k, v in m.items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Operator Assist Tool | Port 8321</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;text-align:center;margin:24px 0 4px}}
  .subtitle{{text-align:center;color:#38bdf8;font-size:13px;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:0 24px 24px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px}}
  .card h2{{color:#38bdf8;font-size:14px;margin:0 0 12px}}
  .full{{grid-column:1/-1}}
  .metrics{{display:flex;flex-wrap:wrap;gap:14px;padding:0 24px 20px}}
  .metric{{background:#1e293b;border-radius:8px;padding:14px 18px;min-width:150px;flex:1}}
  .mval{{font-size:22px;font-weight:700;color:#38bdf8}}
  .mlbl{{font-size:11px;color:#94a3b8;margin-top:4px;text-transform:capitalize}}
</style>
</head>
<body>
<h1>Operator Assist Tool</h1>
<p class="subtitle">AI-Powered Robot Diagnostic &amp; Intervention Recommendations &mdash; Port 8321</p>
<div class="metrics">{metric_cards}</div>
<div class="grid">
  <div class="card full">
    <h2>Decision Support Flowchart</h2>
    {flowchart_svg}
  </div>
  <div class="card full">
    <h2>30-Day Issue Frequency by Category</h2>
    {bar_svg}
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Operator Assist Tool", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "operator_assist_tool", "port": 8321}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/issues")
    async def issues():
        return [
            {
                "name": name,
                "count_30d": count,
                "self_service_pct": ss_pct,
                "avg_min_self_service": avg_min,
                "avg_days_escalated": avg_days,
                "escalation_pct": esc_pct,
            }
            for name, count, ss_pct, avg_min, avg_days, esc_pct in ISSUE_CATEGORIES
        ]

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8321)
    else:
        server = HTTPServer(("0.0.0.0", 8321), Handler)
        print("Serving operator_assist_tool on http://0.0.0.0:8321 (stdlib fallback)")
        server.serve_forever()
