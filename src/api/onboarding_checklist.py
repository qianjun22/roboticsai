"""Onboarding Checklist Service — port 8334
Tracks new partner onboarding completion with automated validation and next-step guidance.
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ONBOARDING_STEPS = [
    "account", "api_key", "sdk_install", "test_call", "data_upload",
    "baseline_eval", "fine_tune_run", "eval_result", "go_live_review", "go_live"
]

PARTNERS = [
    {
        "name": "Machina_Labs",
        "progress": 7,  # 70% — 7/10 steps
        "blocked": "DPA signature pending",
        "status": "blocked",
        "days_in_onboarding": 18,
        "completed": [True]*7 + [False]*3,
    },
    {
        "name": "Wandelbots",
        "progress": 5,  # 50%
        "blocked": "SDK install — dependency conflict",
        "status": "in_progress",
        "days_in_onboarding": 11,
        "completed": [True]*5 + [False]*5,
    },
    {
        "name": "Matic",
        "progress": 3,  # 30%
        "blocked": "Account setup — legal review",
        "status": "in_progress",
        "days_in_onboarding": 6,
        "completed": [True]*3 + [False]*7,
    },
    {
        "name": "Figure_AI",
        "progress": 1,  # 10%
        "blocked": "Intro call only",
        "status": "early",
        "days_in_onboarding": 2,
        "completed": [True]*1 + [False]*9,
    },
]

# Historical step durations (days) across 5 past partners
HISTORICAL_STEP_DAYS = {
    "account":       [0.5, 0.5, 1.0, 0.5, 1.5],
    "api_key":       [0.2, 0.3, 0.4, 0.3, 0.3],
    "sdk_install":   [0.5, 1.0, 2.0, 0.8, 1.2],
    "test_call":     [0.3, 0.5, 0.5, 1.0, 0.7],
    "data_upload":   [1.0, 14.0, 3.0, 5.0, 2.0],
    "baseline_eval": [1.0, 1.5, 2.0, 1.0, 1.5],
    "fine_tune_run": [1.5, 2.0, 2.5, 1.5, 2.0],
    "eval_result":   [0.5, 1.0, 0.5, 0.8, 0.7],
    "go_live_review":[1.0, 2.0, 1.5, 1.0, 1.5],
    "go_live":       [0.5, 0.5, 1.0, 0.5, 0.5],
}

METRICS = {
    "completion_pct": 40.0,
    "bottleneck": "data_upload",
    "avg_days_to_go_live": 13.7,
    "time_to_first_value_days": 4.2,
    "nps_at_go_live": 72,
    "partners_active": 4,
    "false_alarm_rate": 0.03,
}

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_progress_svg() -> str:
    """Multi-partner onboarding progress — horizontal progress bars per partner."""
    W, H = 820, 320
    bar_h = 28
    bar_gap = 58
    left_margin = 130
    bar_width = 560
    top = 50

    status_colors = {"blocked": "#ef4444", "in_progress": "#38bdf8", "early": "#a78bfa"}
    step_labels = [
        "Account", "API Key", "SDK", "Test Call", "Data Upload",
        "Baseline", "Fine-Tune", "Eval", "Review", "Go-Live"
    ]

    # tick marks
    ticks = ""
    for i in range(11):
        x = left_margin + (bar_width * i / 10)
        ticks += f'<line x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{top + bar_gap*4 - 6}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>'
        ticks += f'<text x="{x:.1f}" y="{top-14}" text-anchor="middle" fill="#94a3b8" font-size="9">{i*10}%</text>'

    # step name labels along top
    for i, lbl in enumerate(step_labels):
        x = left_margin + bar_width * i / 10 + bar_width / 20
        ticks += f'<text x="{x:.1f}" y="{top-26}" text-anchor="middle" fill="#64748b" font-size="8">{lbl}</text>'

    bars = ""
    for pi, p in enumerate(PARTNERS):
        y = top + pi * bar_gap
        pct = p["progress"] / 10.0
        filled_w = bar_width * pct
        color = status_colors.get(p["status"], "#38bdf8")

        # background bar
        bars += f'<rect x="{left_margin}" y="{y}" width="{bar_width}" height="{bar_h}" rx="4" fill="#1e293b"/>'
        # filled portion
        if filled_w > 0:
            bars += f'<rect x="{left_margin}" y="{y}" width="{filled_w:.1f}" height="{bar_h}" rx="4" fill="{color}" opacity="0.85"/>'
        # step segment dividers
        for s in range(1, 10):
            sx = left_margin + bar_width * s / 10
            bars += f'<line x1="{sx:.1f}" y1="{y}" x2="{sx:.1f}" y2="{y+bar_h}" stroke="#0f172a" stroke-width="1.5"/>'
        # completed step checkmarks
        for si, done in enumerate(p["completed"]):
            cx = left_margin + bar_width * si / 10 + bar_width / 20
            cy = y + bar_h / 2
            if done:
                bars += f'<text x="{cx:.1f}" y="{cy+4:.1f}" text-anchor="middle" fill="white" font-size="11" font-weight="bold">✓</text>'
        # partner name
        bars += f'<text x="{left_margin-8}" y="{y+bar_h/2+4:.1f}" text-anchor="end" fill="#e2e8f0" font-size="12" font-weight="600">{p["name"]}</text>'
        # pct label
        bars += f'<text x="{left_margin+filled_w+6:.1f}" y="{y+bar_h/2+4:.1f}" fill="{color}" font-size="11" font-weight="700">{p["progress"]*10}%</text>'
        # blocked label
        if p["blocked"]:
            bars += f'<text x="{left_margin + bar_width + 10}" y="{y+bar_h/2+4:.1f}" fill="#94a3b8" font-size="9">⚠ {p["blocked"][:28]}</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="24" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="700">Partner Onboarding Progress — 10-Step Pipeline</text>
  {ticks}
  {bars}
  <!-- legend -->
  <rect x="{left_margin}" y="{top + bar_gap*4 + 8}" width="14" height="14" rx="2" fill="#ef4444"/>
  <text x="{left_margin+18}" y="{top + bar_gap*4 + 20}" fill="#94a3b8" font-size="11">Blocked</text>
  <rect x="{left_margin+80}" y="{top + bar_gap*4 + 8}" width="14" height="14" rx="2" fill="#38bdf8"/>
  <text x="{left_margin+98}" y="{top + bar_gap*4 + 20}" fill="#94a3b8" font-size="11">In Progress</text>
  <rect x="{left_margin+190}" y="{top + bar_gap*4 + 8}" width="14" height="14" rx="2" fill="#a78bfa"/>
  <text x="{left_margin+208}" y="{top + bar_gap*4 + 20}" fill="#94a3b8" font-size="11">Early Stage</text>
</svg>'''
    return svg


def build_boxplot_svg() -> str:
    """Time-to-value box plot per onboarding step."""
    W, H = 820, 300
    left = 90
    right = W - 30
    chart_w = right - left
    top = 40
    bottom = H - 50
    chart_h = bottom - top

    steps = list(HISTORICAL_STEP_DAYS.keys())
    n = len(steps)
    slot_w = chart_w / n

    # y-axis: max ~15 days
    y_max = 16.0

    def y_pos(val):
        return bottom - (val / y_max) * chart_h

    # y-axis ticks
    axes = ""
    for yv in [0, 2, 4, 6, 8, 10, 12, 14, 16]:
        yp = y_pos(yv)
        axes += f'<line x1="{left}" y1="{yp:.1f}" x2="{right}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        axes += f'<text x="{left-6}" y="{yp+4:.1f}" text-anchor="end" fill="#64748b" font-size="9">{yv}d</text>'

    boxes = ""
    for i, step in enumerate(steps):
        vals = sorted(HISTORICAL_STEP_DAYS[step])
        mn = min(vals)
        mx = max(vals)
        q1 = sorted(vals)[1]
        q3 = sorted(vals)[3]
        med = sorted(vals)[2]
        mean_v = sum(vals) / len(vals)
        cx = left + slot_w * i + slot_w / 2
        bw = slot_w * 0.4

        # whiskers
        boxes += f'<line x1="{cx:.1f}" y1="{y_pos(mn):.1f}" x2="{cx:.1f}" y2="{y_pos(mx):.1f}" stroke="#475569" stroke-width="1.5"/>'
        boxes += f'<line x1="{cx-bw/3:.1f}" y1="{y_pos(mn):.1f}" x2="{cx+bw/3:.1f}" y2="{y_pos(mn):.1f}" stroke="#475569" stroke-width="1.5"/>'
        boxes += f'<line x1="{cx-bw/3:.1f}" y1="{y_pos(mx):.1f}" x2="{cx+bw/3:.1f}" y2="{y_pos(mx):.1f}" stroke="#475569" stroke-width="1.5"/>'
        # IQR box
        box_top = y_pos(q3)
        box_bot = y_pos(q1)
        boxes += f'<rect x="{cx-bw/2:.1f}" y="{box_top:.1f}" width="{bw:.1f}" height="{box_bot-box_top:.1f}" fill="#1d4ed8" opacity="0.5" rx="2"/>'
        # median line
        boxes += f'<line x1="{cx-bw/2:.1f}" y1="{y_pos(med):.1f}" x2="{cx+bw/2:.1f}" y2="{y_pos(med):.1f}" stroke="#38bdf8" stroke-width="2"/>'
        # mean dot
        boxes += f'<circle cx="{cx:.1f}" cy="{y_pos(mean_v):.1f}" r="3" fill="#C74634"/>'
        # outlier (data_upload max is extreme)
        if step == "data_upload":
            boxes += f'<circle cx="{cx:.1f}" cy="{y_pos(14.0):.1f}" r="4" fill="none" stroke="#ef4444" stroke-width="1.5"/>'
        # x label
        short = step.replace("_", "\n")
        label = step.replace("_", " ")
        boxes += f'<text x="{cx:.1f}" y="{bottom+14}" text-anchor="middle" fill="#94a3b8" font-size="8">{label[:10]}</text>'
        boxes += f'<text x="{cx:.1f}" y="{bottom+24}" text-anchor="middle" fill="#64748b" font-size="7">{label[10:]}</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="14" font-weight="700">Time-to-Value Box Plot — Days per Onboarding Step (5 Historical Partners)</text>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#334155" stroke-width="1.5"/>
  {axes}
  {boxes}
  <!-- legend -->
  <rect x="{left}" y="{bottom+34}" width="12" height="12" rx="2" fill="#1d4ed8" opacity="0.5"/>
  <text x="{left+16}" y="{bottom+44}" fill="#94a3b8" font-size="10">IQR (p25–p75)</text>
  <line x1="{left+120}" y1="{bottom+40}" x2="{left+138}" y2="{bottom+40}" stroke="#38bdf8" stroke-width="2"/>
  <text x="{left+142}" y="{bottom+44}" fill="#94a3b8" font-size="10">Median</text>
  <circle cx="{left+220}" cy="{bottom+40}" r="3" fill="#C74634"/>
  <text x="{left+228}" y="{bottom+44}" fill="#94a3b8" font-size="10">Mean</text>
  <circle cx="{left+290}" cy="{bottom+40}" r="4" fill="none" stroke="#ef4444" stroke-width="1.5"/>
  <text x="{left+300}" y="{bottom+44}" fill="#94a3b8" font-size="10">Outlier</text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    progress_svg = build_progress_svg()
    boxplot_svg = build_boxplot_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    partner_rows = ""
    for p in PARTNERS:
        pct = p["progress"] * 10
        color = {"blocked": "#ef4444", "in_progress": "#38bdf8", "early": "#a78bfa"}.get(p["status"], "#38bdf8")
        badge = {"blocked": "BLOCKED", "in_progress": "IN PROGRESS", "early": "EARLY STAGE"}.get(p["status"], p["status"].upper())
        partner_rows += f"""
        <tr>
          <td style="color:#e2e8f0;font-weight:600">{p['name']}</td>
          <td>
            <div style="background:#1e293b;border-radius:4px;height:16px;width:120px">
              <div style="background:{color};height:16px;border-radius:4px;width:{pct*1.2:.0f}px"></div>
            </div>
          </td>
          <td style="color:{color};font-weight:700">{pct}%</td>
          <td><span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{badge}</span></td>
          <td style="color:#94a3b8;font-size:12px">{p['blocked']}</td>
          <td style="color:#64748b">{p['days_in_onboarding']}d</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Onboarding Checklist — Port 8334</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .kpi-val {{ font-size: 28px; font-weight: 800; color: #38bdf8; }}
    .kpi-val.red {{ color: #C74634; }}
    .kpi-label {{ font-size: 11px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .card h2 {{ font-size: 14px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 8px; text-align: left; border-bottom: 1px solid #334155; }}
    td {{ padding: 10px 8px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
    .accent {{ color: #C74634; }}
    .footer {{ color: #334155; font-size: 11px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
    <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px">🚀</div>
    <h1>Onboarding Checklist <span class="accent">Service</span></h1>
  </div>
  <p class="subtitle">Partner onboarding pipeline · automated validation · next-step guidance · port 8334 · {ts}</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-val">{METRICS['completion_pct']:.0f}%</div><div class="kpi-label">Avg Completion</div></div>
    <div class="kpi"><div class="kpi-val">{METRICS['avg_days_to_go_live']}</div><div class="kpi-label">Avg Days to Go-Live</div></div>
    <div class="kpi"><div class="kpi-val red">{METRICS['time_to_first_value_days']}</div><div class="kpi-label">Time-to-First-Value (days)</div></div>
    <div class="kpi"><div class="kpi-val">{METRICS['nps_at_go_live']}</div><div class="kpi-label">NPS at Go-Live</div></div>
  </div>

  <div class="card">
    <h2>Active Partners — Onboarding Status</h2>
    <table>
      <thead><tr><th>Partner</th><th>Progress</th><th>%</th><th>Status</th><th>Blocker / Notes</th><th>Days Active</th></tr></thead>
      <tbody>{partner_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Partner Onboarding Progress — 10-Step Pipeline</h2>
    {progress_svg}
  </div>

  <div class="card">
    <h2>Time-to-Value Analysis — Step Duration Box Plot</h2>
    {boxplot_svg}
    <p style="color:#475569;font-size:11px;margin-top:8px">api_key fastest (≈0.3 days avg) · data_upload most variable (1–14 days) · historical avg 13.7 days to go-live</p>
  </div>

  <div class="footer">OCI Robot Cloud · Onboarding Checklist Service · port 8334 · © 2026 Oracle Corporation</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Onboarding Checklist", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "onboarding_checklist", "port": 8334}

    @app.get("/api/partners")
    async def get_partners():
        return {"partners": PARTNERS, "metrics": METRICS}

    @app.get("/api/steps")
    async def get_steps():
        return {"steps": ONBOARDING_STEPS, "historical_days": HISTORICAL_STEP_DAYS}

else:
    # Stdlib fallback
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
        uvicorn.run(app, host="0.0.0.0", port=8334)
    else:
        import http.server
        with http.server.HTTPServer(("0.0.0.0", 8334), Handler) as srv:
            print("Serving on http://0.0.0.0:8334 (stdlib fallback)")
            srv.serve_forever()
