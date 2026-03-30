"""Pilot Readiness Tracker — OCI Robot Cloud
Port 8319 | Tracks design partner pilot readiness, go-live checklists, and risk assessment.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
random.seed(7)

CRITERIA = [
    "NDA", "DPA", "API_Integration", "Test_Robot",
    "Data_Collection", "Eval_Baseline", "GoLive_Support", "Success_Metric",
]

PILOTS = [
    {
        "name": "Machina_Labs",
        "readiness": 87,
        "blocker": "DPA signature pending",
        "go_live": "Jun 12, 2026",
        "risk": "Low",
        "criteria_done": [1, 0, 1, 1, 1, 1, 1, 1],  # 0=blocked, 1=done
        "phases": [
            {"name": "Onboarding",     "start": 0,  "dur": 3},
            {"name": "First Demo",     "start": 3,  "dur": 2},
            {"name": "Data Collection","start": 5,  "dur": 5},
            {"name": "Fine-Tune",      "start": 10, "dur": 4},
            {"name": "Eval",           "start": 14, "dur": 2},
            {"name": "Go-Live",        "start": 16, "dur": 1, "critical": True},
        ],
    },
    {
        "name": "Wandelbots",
        "readiness": 71,
        "blocker": "API integration in progress",
        "go_live": "Jul 28, 2026",
        "risk": "Medium",
        "criteria_done": [1, 1, 0, 1, 1, 0, 1, 0],
        "phases": [
            {"name": "Onboarding",     "start": 2,  "dur": 3},
            {"name": "First Demo",     "start": 5,  "dur": 3},
            {"name": "Data Collection","start": 8,  "dur": 6},
            {"name": "Fine-Tune",      "start": 14, "dur": 5},
            {"name": "Eval",           "start": 19, "dur": 3},
            {"name": "Go-Live",        "start": 22, "dur": 1, "critical": True},
        ],
    },
    {
        "name": "Matic",
        "readiness": 52,
        "blocker": "No test robot yet",
        "go_live": "Sep 15, 2026",
        "risk": "High",
        "criteria_done": [1, 1, 0, 0, 0, 0, 1, 1],
        "phases": [
            {"name": "Onboarding",     "start": 4,  "dur": 4},
            {"name": "First Demo",     "start": 8,  "dur": 4},
            {"name": "Data Collection","start": 12, "dur": 7},
            {"name": "Fine-Tune",      "start": 19, "dur": 5},
            {"name": "Eval",           "start": 24, "dur": 3},
            {"name": "Go-Live",        "start": 27, "dur": 1, "critical": True},
        ],
    },
    {
        "name": "Figure_AI",
        "readiness": 38,
        "blocker": "Early stage — NDA only",
        "go_live": "Nov 30, 2026",
        "risk": "High",
        "criteria_done": [1, 0, 0, 0, 0, 0, 0, 1],
        "phases": [
            {"name": "Onboarding",     "start": 8,  "dur": 5},
            {"name": "First Demo",     "start": 13, "dur": 4},
            {"name": "Data Collection","start": 17, "dur": 8},
            {"name": "Fine-Tune",      "start": 25, "dur": 6},
            {"name": "Eval",           "start": 31, "dur": 3},
            {"name": "Go-Live",        "start": 34, "dur": 1, "critical": True},
        ],
    },
]

# ---------------------------------------------------------------------------
# SVG 1: Readiness Checklist Grid
# ---------------------------------------------------------------------------

def _checklist_svg() -> str:
    PILOT_COLORS = ["#C74634", "#38bdf8", "#34d399", "#fbbf24"]
    cell_w, cell_h = 80, 36
    pad_l, pad_t = 140, 50
    W = pad_l + len(CRITERIA) * cell_w + 20
    H = pad_t + len(PILOTS) * cell_h + 40
    svg_parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']

    # Column headers
    for ci, crit in enumerate(CRITERIA):
        cx = pad_l + ci * cell_w + cell_w // 2
        svg_parts.append(
            f'<text x="{cx}" y="{pad_t - 10}" text-anchor="middle" '
            f'fill="#64748b" font-size="10" font-family="monospace" '
            f'transform="rotate(-30,{cx},{pad_t-10})">{crit}</text>'
        )

    for ri, pilot in enumerate(PILOTS):
        col = PILOT_COLORS[ri % len(PILOT_COLORS)]
        py = pad_t + ri * cell_h

        # Pilot name
        svg_parts.append(
            f'<text x="{pad_l - 8}" y="{py + cell_h//2 + 4}" text-anchor="end" '
            f'fill="{col}" font-size="11" font-family="monospace">{pilot["name"]}</text>'
        )

        # Readiness bar background
        svg_parts.append(
            f'<rect x="0" y="{py+4}" width="{pad_l-14}" height="{cell_h-8}" '
            f'rx="4" fill="#0f172a"/>'
        )
        bar_w = int((pad_l - 20) * pilot["readiness"] / 100)
        svg_parts.append(
            f'<rect x="0" y="{py+4}" width="{bar_w}" height="{cell_h-8}" '
            f'rx="4" fill="{col}" opacity="0.6"/>'
        )
        svg_parts.append(
            f'<text x="{bar_w//2}" y="{py+cell_h//2+4}" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="10" font-family="monospace">{pilot["readiness"]}%</text>'
        )

        for ci, done in enumerate(pilot["criteria_done"]):
            cx = pad_l + ci * cell_w
            cy = py
            if done == 1:
                fill = "#166534"
                text_fill = "#34d399"
                symbol = "\u2713"
            else:
                fill = "#450a0a"
                text_fill = "#C74634"
                symbol = "\u2717"
            svg_parts.append(
                f'<rect x="{cx+2}" y="{cy+3}" width="{cell_w-4}" height="{cell_h-6}" '
                f'rx="4" fill="{fill}"/>'
            )
            svg_parts.append(
                f'<text x="{cx+cell_w//2}" y="{cy+cell_h//2+5}" text-anchor="middle" '
                f'fill="{text_fill}" font-size="15" font-family="monospace">{symbol}</text>'
            )

    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ---------------------------------------------------------------------------
# SVG 2: Pilot Timeline Gantt
# ---------------------------------------------------------------------------

def _gantt_svg() -> str:
    PILOT_COLORS = ["#C74634", "#38bdf8", "#34d399", "#fbbf24"]
    PHASE_COLORS = {
        "Onboarding":      "#334155",
        "First Demo":      "#38bdf8",
        "Data Collection": "#a78bfa",
        "Fine-Tune":       "#C74634",
        "Eval":            "#fbbf24",
        "Go-Live":         "#34d399",
    }
    TOTAL_WEEKS = 36
    scale = 18  # px per week
    row_h = 32
    pad_l, pad_t = 130, 40
    W = pad_l + TOTAL_WEEKS * scale + 30
    H = pad_t + len(PILOTS) * (len(PILOTS[0]["phases"]) + 1) * row_h + 50
    # Compute actual height
    total_rows = sum(len(p["phases"]) + 1 for p in PILOTS)
    H = pad_t + total_rows * row_h + 50
    svg_parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']

    # Week axis
    for w in range(0, TOTAL_WEEKS + 1, 4):
        cx = pad_l + w * scale
        svg_parts.append(
            f'<line x1="{cx}" y1="{pad_t-10}" x2="{cx}" y2="{H-30}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{cx}" y="{pad_t-14}" text-anchor="middle" '
            f'fill="#475569" font-size="9" font-family="monospace">W{w}</text>'
        )

    cur_y = pad_t
    for ri, pilot in enumerate(PILOTS):
        pcol = PILOT_COLORS[ri % len(PILOT_COLORS)]
        # Pilot header row
        svg_parts.append(
            f'<text x="{pad_l - 6}" y="{cur_y + row_h//2 + 4}" text-anchor="end" '
            f'fill="{pcol}" font-size="12" font-weight="bold" font-family="monospace">{pilot["name"]}</text>'
        )
        cur_y += row_h

        for phase in pilot["phases"]:
            x = pad_l + phase["start"] * scale
            w_px = phase["dur"] * scale - 3
            is_crit = phase.get("critical", False)
            fc = PHASE_COLORS.get(phase["name"], "#64748b")
            stroke = "#ffffff" if is_crit else "none"
            svg_parts.append(
                f'<rect x="{x}" y="{cur_y+4}" width="{w_px}" height="{row_h-8}" '
                f'rx="4" fill="{fc}" stroke="{stroke}" stroke-width="{2 if is_crit else 0}"/>'
            )
            if w_px > 28:
                svg_parts.append(
                    f'<text x="{x + w_px//2}" y="{cur_y + row_h//2 + 4}" text-anchor="middle" '
                    f'fill="#0f172a" font-size="9" font-family="monospace">{phase["name"]}</text>'
                )
            svg_parts.append(
                f'<text x="{pad_l - 6}" y="{cur_y + row_h//2 + 4}" text-anchor="end" '
                f'fill="#475569" font-size="9" font-family="monospace">{phase["name"]}</text>'
            )
            cur_y += row_h

    # Legend
    lx = pad_l
    ly = H - 20
    svg_parts.append(
        f'<rect x="{lx}" y="{ly}" width="10" height="10" rx="2" fill="#34d399" stroke="#ffffff" stroke-width="2"/>'
    )
    svg_parts.append(
        f'<text x="{lx+14}" y="{ly+9}" fill="#94a3b8" font-size="9" font-family="monospace">Go-Live (critical path)</text>'
    )
    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _build_html() -> str:
    checklist = _checklist_svg()
    gantt = _gantt_svg()

    risk_badge = {
        "Low":    ("#052e16", "#34d399", "#166534"),
        "Medium": ("#451a03", "#fbbf24", "#92400e"),
        "High":   ("#450a0a", "#C74634", "#991b1b"),
    }

    pilot_cards = ""
    for p in PILOTS:
        bg, fc, border = risk_badge.get(p["risk"], ("#1e293b", "#94a3b8", "#334155"))
        done_count = sum(p["criteria_done"])
        total_crit = len(CRITERIA)
        pilot_cards += f"""
        <div class="pcard" style="border-color:{border}">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="color:#e2e8f0;font-size:14px;font-weight:bold">{p['name']}</span>
            <span style="background:{bg};color:{fc};border:1px solid {border};padding:2px 10px;
                         border-radius:4px;font-size:11px">{p['risk']} Risk</span>
          </div>
          <div style="margin:10px 0">
            <div style="background:#0f172a;border-radius:6px;height:16px">
              <div style="background:{fc};height:16px;border-radius:6px;width:{p['readiness']}%"></div>
            </div>
            <span style="color:{fc};font-size:12px">{p['readiness']}% ready — {done_count}/{total_crit} criteria</span>
          </div>
          <div style="color:#94a3b8;font-size:11px">Blocker: <span style="color:#C74634">{p['blocker']}</span></div>
          <div style="color:#64748b;font-size:11px;margin-top:4px">Go-Live Target: <span style="color:#38bdf8">{p['go_live']}</span></div>
        </div>
        """

    total_pilots = len(PILOTS)
    low_risk = sum(1 for p in PILOTS if p["risk"] == "Low")
    med_risk = sum(1 for p in PILOTS if p["risk"] == "Medium")
    high_risk = sum(1 for p in PILOTS if p["risk"] == "High")
    avg_readiness = round(sum(p["readiness"] for p in PILOTS) / total_pilots)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Pilot Readiness Tracker | OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
    .card .val{{font-size:28px;font-weight:bold;color:#38bdf8;margin-bottom:4px}}
    .card .lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px}}
    .section{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:22px}}
    .section h2{{color:#38bdf8;font-size:15px;margin-bottom:16px}}
    .pilots-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:22px}}
    .pcard{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}}
    svg{{max-width:100%;height:auto}}
  </style>
</head>
<body>
  <h1>Pilot Readiness Tracker</h1>
  <div class="subtitle">OCI Robot Cloud — Design Partner Go-Live Pipeline | Port 8319 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="metrics">
    <div class="card"><div class="val">{total_pilots}</div><div class="lbl">Active Pilots</div></div>
    <div class="card"><div class="val" style="color:#34d399">{avg_readiness}%</div><div class="lbl">Avg Readiness</div></div>
    <div class="card"><div class="val" style="color:#C74634">{high_risk}</div><div class="lbl">High Risk Pilots</div></div>
    <div class="card"><div class="val" style="color:#38bdf8">Jun 12</div><div class="lbl">Earliest Go-Live (Machina)</div></div>
  </div>

  <div class="pilots-grid">
    {pilot_cards}
  </div>

  <div class="section">
    <h2>Readiness Checklist — 4 Pilots × 8 Criteria</h2>
    {checklist}
    <p style="color:#64748b;font-size:11px;margin-top:10px">
      Green = complete | Red = blocked/missing. Horizontal bars show overall readiness %.
    </p>
  </div>

  <div class="section">
    <h2>Pilot Timeline Gantt — Onboarding to Go-Live</h2>
    {gantt}
    <p style="color:#64748b;font-size:11px;margin-top:10px">
      Go-Live phases (white border) mark critical path. Machina Labs targets Jun 12, 2026 — first to production.
    </p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app  (fallback to stdlib http.server)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Pilot Readiness Tracker",
        description="Design partner pilot readiness and go-live tracking for OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8319, "service": "pilot_readiness_tracker"}

    @app.get("/api/pilots")
    async def pilots():
        return {"pilots": [
            {
                "name": p["name"],
                "readiness": p["readiness"],
                "blocker": p["blocker"],
                "go_live": p["go_live"],
                "risk": p["risk"],
                "criteria": {CRITERIA[i]: bool(done) for i, done in enumerate(p["criteria_done"])},
            }
            for p in PILOTS
        ]}

    @app.get("/api/pilots/{name}")
    async def pilot_detail(name: str):
        for p in PILOTS:
            if p["name"].lower() == name.lower():
                return p
        return {"error": "not found"}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8319)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8319")
        with socketserver.TCPServer(("", 8319), _Handler) as srv:
            srv.serve_forever()
