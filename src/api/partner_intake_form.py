"""partner_intake_form.py — Partner onboarding intake forms and qualification scoring for OCI Robot Cloud.
FastAPI service on port 8269.
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
from datetime import datetime, timedelta

# ── Mock data ────────────────────────────────────────────────────────────────

random.seed(7)

FUNNEL_STAGES = [
    {"stage": "Applicants",    "count": 23, "color": "#38bdf8"},
    {"stage": "Qualified",     "count": 15, "color": "#818cf8"},
    {"stage": "Tech Eval",     "count": 8,  "color": "#a78bfa"},
    {"stage": "Pilot",         "count": 5,  "color": "#fb923c"},
    {"stage": "Paying",        "count": 3,  "color": "#34d399"},
]

RADAR_DIMS = ["technical_fit", "budget_size", "timeline", "data_availability", "executive_sponsor"]

PROSPECTS = [
    {"name": "Machina Labs",    "scores": [4.7, 4.5, 4.2, 3.8, 4.9], "source": "NVIDIA",  "color": "#38bdf8"},
    {"name": "Apptronik",       "scores": [4.2, 3.9, 3.5, 4.1, 3.8], "source": "NVIDIA",  "color": "#a78bfa"},
    {"name": "Agility Robotics","scores": [3.8, 4.4, 3.0, 3.5, 4.2], "source": "Organic", "color": "#fb923c"},
    {"name": "Covariant",       "scores": [4.5, 3.2, 4.0, 4.8, 3.5], "source": "Organic", "color": "#f43f5e"},
    {"name": "Skild AI",        "scores": [4.0, 3.6, 3.8, 3.2, 4.0], "source": "NVIDIA",  "color": "#fbbf24"},
]

MIN_VIABLE = [3.5, 3.5, 3.0, 3.0, 3.5]  # minimum viable score per dimension

KEY_METRICS = {
    "total_inbound_leads": 23,
    "qualified_leads": 15,
    "qualification_conversion_pct": round(15 / 23 * 100, 1),
    "paying_partners": 3,
    "avg_intake_to_pilot_days": 22,
    "top_prospect": "Machina Labs",
    "top_prospect_score": 4.7,
    "disqualified_budget": 2,
    "nvidia_referred_pct": round(3 / 5 * 100, 1),
    "since_date": "Jan 2026",
}

# ── SVG builders ─────────────────────────────────────────────────────────────

def build_funnel_svg() -> str:
    W, H = 640, 380
    pad_l, pad_r, pad_t, pad_b = 30, 30, 50, 40
    n = len(FUNNEL_STAGES)
    stage_h = (H - pad_t - pad_b) // n
    max_count = FUNNEL_STAGES[0]["count"]
    max_w = W - pad_l - pad_r

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:12px">',
        f'<text x="{W//2}" y="30" text-anchor="middle" fill="#e2e8f0" font-size="14" font-family="monospace" font-weight="bold">Partner Qualification Funnel</text>',
    ]

    for i, stage in enumerate(FUNNEL_STAGES):
        ratio = stage["count"] / max_count
        w = int(max_w * ratio)
        x_center = W // 2
        x_left = x_center - w // 2
        y_top = pad_t + i * stage_h
        y_bot = y_top + stage_h - 4

        # Trapezoid: narrow top if not first, using next ratio for bottom
        if i < n - 1:
            next_ratio = FUNNEL_STAGES[i + 1]["count"] / max_count
            w_bot = int(max_w * next_ratio)
        else:
            w_bot = w

        x_left_top = x_center - w // 2
        x_right_top = x_center + w // 2
        x_left_bot = x_center - w_bot // 2
        x_right_bot = x_center + w_bot // 2

        pts = f"{x_left_top},{y_top} {x_right_top},{y_top} {x_right_bot},{y_bot} {x_left_bot},{y_bot}"
        lines.append(f'<polygon points="{pts}" fill="{stage["color"]}" opacity="0.75"/>')
        lines.append(f'<polygon points="{pts}" fill="none" stroke="{stage["color"]}" stroke-width="1.5" opacity="0.9"/>')

        # Stage label (left)
        lines.append(f'<text x="{x_left_top - 12}" y="{y_top + stage_h // 2 + 5}" text-anchor="end" fill="#cbd5e1" font-size="12" font-family="monospace">{stage["stage"]}</text>')
        # Count (center)
        lines.append(f'<text x="{x_center}" y="{y_top + stage_h // 2 + 5}" text-anchor="middle" fill="#fff" font-size="15" font-family="monospace" font-weight="bold">{stage["count"]}</text>')
        # Conversion rate (right)
        if i > 0:
            prev = FUNNEL_STAGES[i - 1]["count"]
            conv = round(stage["count"] / prev * 100, 0)
            lines.append(f'<text x="{x_right_top + 12}" y="{y_top + 14}" fill="#94a3b8" font-size="11" font-family="monospace">{int(conv)}%</text>')
            lines.append(f'<line x1="{x_right_top + 8}" y1="{y_top}" x2="{x_right_top + 8}" y2="{y_bot}" stroke="#334155" stroke-width="1"/>')

    lines.append('</svg>')
    return "\n".join(lines)


def build_radar_svg() -> str:
    W, H = 500, 420
    cx, cy = W // 2, H // 2 + 10
    max_r = 150
    n_dims = len(RADAR_DIMS)
    MAX_SCORE = 5.0

    def polar(score, dim_idx, r_scale=1.0):
        angle = math.pi / 2 + 2 * math.pi * dim_idx / n_dims
        r = max_r * (score / MAX_SCORE) * r_scale
        return cx + r * math.cos(angle), cy - r * math.sin(angle)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:12px">',
        f'<text x="{W//2}" y="24" text-anchor="middle" fill="#e2e8f0" font-size="14" font-family="monospace" font-weight="bold">Prospect Qualification Radar</text>',
    ]

    # Grid rings
    for ring in [1.0, 0.8, 0.6, 0.4, 0.2]:
        pts = " ".join(f"{polar(MAX_SCORE * ring, d)[0]:.1f},{polar(MAX_SCORE * ring, d)[1]:.1f}" for d in range(n_dims))
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')
        score_val = round(MAX_SCORE * ring, 1)
        rx, ry = polar(MAX_SCORE * ring, 0)
        lines.append(f'<text x="{rx:.0f}" y="{ry - 4:.0f}" text-anchor="middle" fill="#475569" font-size="9" font-family="monospace">{score_val}</text>')

    # Spokes
    for d in range(n_dims):
        ox, oy = polar(0.0, d)
        ex, ey = polar(MAX_SCORE, d)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>')
        # Dimension label
        lx, ly = polar(MAX_SCORE * 1.18, d)
        label = RADAR_DIMS[d].replace("_", " ")
        lines.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>')

    # Minimum viable score polygon
    min_pts = " ".join(f"{polar(MIN_VIABLE[d], d)[0]:.1f},{polar(MIN_VIABLE[d], d)[1]:.1f}" for d in range(n_dims))
    lines.append(f'<polygon points="{min_pts}" fill="#ef4444" fill-opacity="0.08" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="5,3"/>')
    lines.append(f'<text x="{cx}" y="{cy + max_r + 18}" text-anchor="middle" fill="#ef4444" font-size="10" font-family="monospace">--- min viable threshold</text>')

    # Prospect polygons
    for p in PROSPECTS:
        pts = " ".join(f"{polar(p['scores'][d], d)[0]:.1f},{polar(p['scores'][d], d)[1]:.1f}" for d in range(n_dims))
        lines.append(f'<polygon points="{pts}" fill="{p["color"]}" fill-opacity="0.12" stroke="{p["color"]}" stroke-width="1.8" opacity="0.85"/>')

    # Legend
    leg_x, leg_y = 16, H - 20 - len(PROSPECTS) * 18
    lines.append(f'<text x="{leg_x}" y="{leg_y - 8}" fill="#64748b" font-size="10" font-family="monospace">Prospects:</text>')
    for i, p in enumerate(PROSPECTS):
        lx = leg_x
        ly = leg_y + i * 18
        lines.append(f'<rect x="{lx}" y="{ly - 9}" width="14" height="10" rx="2" fill="{p["color"]}" opacity="0.8"/>')
        avg_score = round(sum(p["scores"]) / len(p["scores"]), 2)
        lines.append(f'<text x="{lx + 18}" y="{ly}" fill="#cbd5e1" font-size="11" font-family="monospace">{p["name"]} ({avg_score}) [{p["source"]}]</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML dashboard ────────────────────────────────────────────────────────────

def build_html() -> str:
    svg1 = build_funnel_svg()
    svg2 = build_radar_svg()
    m = KEY_METRICS

    prospects_html = "".join(
        f'<div style="background:#1e293b;border-left:3px solid {p["color"]};padding:10px 14px;border-radius:6px;margin-bottom:8px">'
        f'<span style="color:{p["color"]};font-size:13px;font-weight:bold">{p["name"]}</span>'
        f'<span style="color:#94a3b8;font-size:11px;margin-left:12px">via {p["source"]}</span>'
        f'<div style="color:#e2e8f0;font-size:12px;margin-top:4px">'
        + " &nbsp;·&nbsp; ".join(f"{RADAR_DIMS[i].replace("_"," ")}: <span style=\"color:#38bdf8\">{p['scores'][i]}</span>" for i in range(len(RADAR_DIMS)))
        + f'</div></div>'
        for p in PROSPECTS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Partner Intake Form — Port 8269</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#C74634;margin:0 0 4px}}
  .sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
  .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
  .card{{background:#1e293b;border-radius:10px;padding:16px 20px;min-width:160px}}
  .card-val{{font-size:26px;font-weight:bold;color:#38bdf8}}
  .card-lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  .section{{margin-bottom:32px}}
  .section-title{{font-size:15px;font-weight:bold;color:#C74634;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
  svg{{max-width:100%;height:auto}}
  .charts{{display:flex;flex-wrap:wrap;gap:20px}}
</style>
</head>
<body>
<h1>Partner Intake Form</h1>
<div class="sub">OCI Robot Cloud — partner onboarding qualification scoring · Port 8269 · Since {m["since_date"]}</div>

<div class="metrics">
  <div class="card"><div class="card-val">{m["total_inbound_leads"]}</div><div class="card-lbl">Inbound Leads</div></div>
  <div class="card"><div class="card-val">{m["qualified_leads"]}</div><div class="card-lbl">Qualified</div></div>
  <div class="card"><div class="card-val">{m["qualification_conversion_pct"]}%</div><div class="card-lbl">Qualification Conv.</div></div>
  <div class="card"><div class="card-val">{m["paying_partners"]}</div><div class="card-lbl">Paying Partners</div></div>
  <div class="card"><div class="card-val">{m["avg_intake_to_pilot_days"]}d</div><div class="card-lbl">Avg Intake → Pilot</div></div>
  <div class="card"><div class="card-val">{m["top_prospect_score"]}</div><div class="card-lbl">Top Score ({m["top_prospect"]})</div></div>
  <div class="card"><div class="card-val">{m["nvidia_referred_pct"]}%</div><div class="card-lbl">NVIDIA Referred</div></div>
  <div class="card"><div class="card-val">{m["disqualified_budget"]}</div><div class="card-lbl">DQ'd (budget)</div></div>
</div>

<div class="section">
  <div class="section-title">Qualification Funnel &amp; Prospect Radar</div>
  <div class="charts">
    {svg1}
    {svg2}
  </div>
</div>

<div class="section">
  <div class="section-title">Current Prospects — Qualification Scores</div>
  {prospects_html}
</div>
</body></html>"""


# ── App / fallback ────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Partner Intake Form", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_intake_form", "port": 8269}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/funnel")
    async def funnel():
        return FUNNEL_STAGES

    @app.get("/prospects")
    async def prospects():
        return PROSPECTS

    @app.get("/radar-dims")
    async def radar_dims():
        return {"dimensions": RADAR_DIMS, "min_viable": MIN_VIABLE}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8269)
    else:
        print("[partner_intake_form] fastapi not found — using stdlib http.server on port 8269")
        with socketserver.TCPServer(("", 8269), Handler) as httpd:
            httpd.serve_forever()
