"""Sales Intelligence Dashboard — port 8953

ICP match scoring (8 signals), intent signal tracking,
47 target Series B+ robotics startups, Agility Robotics fit score 91.
Topics: GitHub star/GTC view/whitepaper → lead score,
prospect scoring heatmap, deal velocity chart.
"""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8953
TITLE = "Sales Intelligence Dashboard"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

ICP_SIGNALS = [
    "Humanoid / AMR fleet",
    "Series B+ funded",
    "GPU compute buyer",
    "GTC / ROSCon attendee",
    "GitHub stars on robot repo",
    "Whitepaper download",
    "Job posts: ML/robotics",
    "Open-source policy eval",
]

PROSPECTS = [
    {"name": "Agility Robotics",  "score": 91, "stage": "Negotiation",  "arr": 420, "signals": [1,1,1,1,1,1,1,0]},
    {"name": "Figure AI",         "score": 88, "stage": "Proof-of-Value","arr": 380, "signals": [1,1,1,1,1,0,1,1]},
    {"name": "1X Technologies",   "score": 85, "stage": "Discovery",     "arr": 290, "signals": [1,1,1,0,1,1,1,0]},
    {"name": "Physical Intelligence","score":83,"stage": "Proof-of-Value","arr": 340, "signals": [1,1,1,1,0,1,1,0]},
    {"name": "Apptronik",         "score": 79, "stage": "Discovery",     "arr": 210, "signals": [1,1,0,1,1,0,1,0]},
    {"name": "Sanctuary AI",      "score": 77, "stage": "Prospecting",   "arr": 180, "signals": [1,1,0,0,1,1,0,1]},
    {"name": "Robust AI",         "score": 74, "stage": "Prospecting",   "arr": 150, "signals": [0,1,1,0,1,0,1,1]},
    {"name": "Machina Labs",      "score": 71, "stage": "Discovery",     "arr": 130, "signals": [1,1,0,0,0,1,1,1]},
    {"name": "Miso Robotics",     "score": 68, "stage": "Prospecting",   "arr": 110, "signals": [0,0,1,1,1,0,1,0]},
    {"name": "Formant",           "score": 65, "stage": "Prospecting",   "arr": 90,  "signals": [0,1,1,0,0,1,0,1]},
]

STAGE_COLORS = {
    "Negotiation":    "#C74634",
    "Proof-of-Value": "#38bdf8",
    "Discovery":      "#4ade80",
    "Prospecting":    "#94a3b8",
}

INTENT_EVENTS = [
    {"week": "W-8",  "github": 12, "gtc": 0,  "whitepaper": 3},
    {"week": "W-7",  "github": 18, "gtc": 0,  "whitepaper": 5},
    {"week": "W-6",  "github": 22, "gtc": 8,  "whitepaper": 7},
    {"week": "W-5",  "github": 35, "gtc": 42, "whitepaper": 14},
    {"week": "W-4",  "github": 41, "gtc": 61, "whitepaper": 19},
    {"week": "W-3",  "github": 38, "gtc": 55, "whitepaper": 22},
    {"week": "W-2",  "github": 53, "gtc": 38, "whitepaper": 28},
    {"week": "W-1",  "github": 67, "gtc": 29, "whitepaper": 33},
    {"week": "W0",   "github": 74, "gtc": 21, "whitepaper": 41},
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def heatmap_svg() -> str:
    """Prospect × ICP-signal heatmap."""
    COLS = len(ICP_SIGNALS)
    ROWS = len(PROSPECTS)
    CW, CH = 62, 28
    LW = 160  # left label width
    TH = 110  # top header height
    W = LW + COLS * CW + 20
    H = TH + ROWS * CH + 20

    lines = []
    # Column headers (rotated)
    for j, sig in enumerate(ICP_SIGNALS):
        x = LW + j * CW + CW / 2
        y = TH - 8
        lines.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="#94a3b8" font-size="9" text-anchor="start" transform="rotate(-45,{x:.1f},{y:.1f})">{sig}</text>')

    for i, p in enumerate(PROSPECTS):
        y_top = TH + i * CH
        # Row label
        color = STAGE_COLORS.get(p["stage"], "#94a3b8")
        lines.append(f'<text x="{LW-6}" y="{y_top+CH/2+4:.1f}" fill="{color}" font-size="11" text-anchor="end">{p["name"]}</text>')
        # Score bar on left
        bar_w = p["score"] / 100 * 40
        lines.append(f'<rect x="{LW-50}" y="{y_top+CH/2-4:.1f}" width="{bar_w:.1f}" height="7" fill="{color}" rx="2" opacity="0.5"/>')
        # Cells
        for j, sig_val in enumerate(p["signals"]):
            x_left = LW + j * CW + 3
            fill = "#C74634" if sig_val else "#1e293b"
            opacity = "0.85" if sig_val else "1"
            lines.append(f'<rect x="{x_left:.1f}" y="{y_top+3:.1f}" width="{CW-6}" height="{CH-6}" fill="{fill}" opacity="{opacity}" rx="3"/>')
            if sig_val:
                cx2 = x_left + (CW - 6) / 2
                cy2 = y_top + 3 + (CH - 6) / 2 + 4
                lines.append(f'<text x="{cx2:.1f}" y="{cy2:.1f}" fill="#fff" font-size="11" text-anchor="middle">✓</text>')

    # Score column header
    lines.append(f'<text x="{LW/2:.1f}" y="{TH-8}" fill="#38bdf8" font-size="10" text-anchor="middle">ICP Score →</text>')
    # Title
    lines.append(f'<text x="{W/2:.1f}" y="18" fill="#C74634" font-size="13" font-weight="bold" text-anchor="middle">Prospect × ICP Signal Heatmap</text>')

    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{chr(10).join(lines)}</svg>'


def deal_velocity_svg() -> str:
    """Stacked area: intent events over time (GitHub / GTC / Whitepaper)."""
    W, H = 520, 300
    PAD = {"l": 55, "r": 20, "t": 40, "b": 50}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]

    N = len(INTENT_EVENTS)
    max_total = max(e["github"] + e["gtc"] + e["whitepaper"] for e in INTENT_EVENTS)
    y_max = math.ceil(max_total / 20) * 20 + 20

    def cx(i): return PAD["l"] + i / (N - 1) * pw
    def cy(v): return PAD["t"] + ph - v / y_max * ph

    layers = [
        ("whitepaper", "#4ade80"),
        ("gtc",        "#38bdf8"),
        ("github",     "#C74634"),
    ]

    lines = []
    # Grid
    for yg in range(0, int(y_max) + 1, 20):
        y = cy(yg)
        lines.append(f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+pw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{PAD["l"]-6}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yg}</text>')

    # Stacked areas
    cumulative = [0.0] * N
    for key, color in layers:
        vals = [INTENT_EVENTS[i][key] for i in range(N)]
        top_pts = [(cx(i), cy(cumulative[i] + vals[i])) for i in range(N)]
        bot_pts = [(cx(i), cy(cumulative[i])) for i in range(N)]

        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        pts += " " + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts))
        lines.append(f'<polygon points="{pts}" fill="{color}" opacity="0.5"/>')
        # Line on top
        line_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        lines.append(f'<polyline points="{line_pts}" fill="none" stroke="{color}" stroke-width="2"/>')

        for i in range(N):
            cumulative[i] += vals[i]

    # X labels
    for i, e in enumerate(INTENT_EVENTS):
        x = cx(i)
        lines.append(f'<text x="{x:.1f}" y="{PAD["t"]+ph+16}" fill="#64748b" font-size="10" text-anchor="middle">{e["week"]}</text>')

    # Legend
    legend_items = [("GitHub Stars", "#C74634"), ("GTC Views", "#38bdf8"), ("Whitepaper", "#4ade80")]
    lx = PAD["l"]
    for label, color in legend_items:
        lines.append(f'<rect x="{lx}" y="{H-16}" width="12" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+16}" y="{H-7}" fill="#94a3b8" font-size="10">{label}</text>')
        lx += 110

    lines.append(f'<text x="{PAD["l"]+pw/2:.1f}" y="{PAD["t"]-14}" fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">Intent Signal Velocity (8 weeks)</text>')
    lines.append(f'<text x="14" y="{PAD["t"]+ph/2:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PAD["t"]+ph/2:.1f})">Events</text>')

    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">{chr(10).join(lines)}</svg>'


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    heatmap = heatmap_svg()
    velocity = deal_velocity_svg()

    total_arr = sum(p["arr"] for p in PROSPECTS)
    avg_score = sum(p["score"] for p in PROSPECTS) / len(PROSPECTS)

    rows = ""
    for p in PROSPECTS:
        color = STAGE_COLORS.get(p["stage"], "#94a3b8")
        sig_count = sum(p["signals"])
        rows += f"""
        <tr>
          <td style="font-weight:600">{p['name']}</td>
          <td style="text-align:right">
            <span style="background:{color};color:#fff;padding:2px 10px;border-radius:10px;font-weight:bold">{p['score']}</span>
          </td>
          <td><span style="background:{color};color:#0f172a;padding:2px 10px;border-radius:8px;font-size:12px">{p['stage']}</span></td>
          <td style="text-align:right">${p['arr']}K</td>
          <td style="text-align:right">{sig_count}/8</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{TITLE}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 28px; }}
    h1 {{ color: #C74634; font-size: 26px; margin-bottom: 6px; }}
    h2 {{ color: #38bdf8; font-size: 16px; margin: 24px 0 10px; }}
    .meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px 24px; min-width: 160px; }}
    .kpi .val {{ font-size: 28px; font-weight: bold; color: #C74634; }}
    .kpi .lbl {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
    .charts {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 28px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background: #1e293b; color: #94a3b8; padding: 10px 14px; text-align: left; }}
    td {{ padding: 9px 14px; border-bottom: 1px solid #1e293b; }}
    tr:hover {{ background: #1e293b88; }}
    .signal-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }}
    .signal-tag {{ background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 4px 10px; border-radius: 12px; font-size: 11px; }}
  </style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="meta">Port {PORT} &nbsp;|&nbsp; 47 target Series B+ robotics startups &nbsp;|&nbsp; Agility Robotics fit score 91</p>

  <div class="kpi-row">
    <div class="kpi"><div class="val">47</div><div class="lbl">Target Accounts</div></div>
    <div class="kpi"><div class="val">91</div><div class="lbl">Top ICP Score (Agility)</div></div>
    <div class="kpi"><div class="val">{avg_score:.0f}</div><div class="lbl">Avg ICP Score</div></div>
    <div class="kpi"><div class="val">${total_arr}K</div><div class="lbl">Pipeline ARR</div></div>
    <div class="kpi"><div class="val">8</div><div class="lbl">ICP Signals Tracked</div></div>
  </div>

  <h2>ICP Signal Tags</h2>
  <div class="signal-tags">
    {''.join(f'<span class="signal-tag">{s}</span>' for s in ICP_SIGNALS)}
  </div>

  <h2>Prospect Scoring Heatmap &amp; Intent Velocity</h2>
  <div class="charts">
    {heatmap}
    {velocity}
  </div>

  <h2>Top 10 Prospects by ICP Score</h2>
  <table>
    <thead><tr><th>Company</th><th style="text-align:right">ICP Score</th><th>Stage</th><th style="text-align:right">ARR Est.</th><th style="text-align:right">Signals Hit</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    @app.get("/api/prospects")
    def api_prospects():
        return PROSPECTS

    @app.get("/api/signals")
    def api_signals():
        return ICP_SIGNALS

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        srv = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{TITLE} running on http://0.0.0.0:{PORT}")
        srv.serve_forever()
