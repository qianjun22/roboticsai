"""
Partner API Usage Heatmap - Port 8647
OCI Robot Cloud - cycle-147A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── data ──────────────────────────────────────────────────────────────────────
PARTNERS = ["PrecisionIndustries", "1X_Robotics", "Apptronik", "Agility", "Sanctuary"]
PARTNER_SHORT = ["PI", "1X", "Apt", "Agility", "Sanc"]

# Hourly call density (calls/hour averaged over a week)
HOURLY_DENSITY = {
    "PrecisionIndustries": [2,1,1,1,2,5,18,42,85,120,78,52,45,110,88,63,42,35,28,18,12,8,5,3],
    "1X_Robotics":         [3,2,2,2,3,3,5, 8,12, 14,13,12,11, 13,12,11,10, 9, 8, 7, 6,5,4,3],
    "Apptronik":           [1,1,1,1,2,8,22,55,98, 72,65,50,38, 44,42,38,32,28,22,15, 9,5,2,1],
    "Agility":             [2,1,1,2,3,6,14,28,45, 62,58,44,36, 48,52,41,33,27,20,14, 9,6,3,2],
    "Sanctuary":           [1,1,1,1,2,4, 9,18,32, 45,42,38,30, 36,38,32,25,20,15,10, 7,4,2,1],
}

ENDPOINT_USAGE = {
    "PrecisionIndustries": {"infer": 68, "train": 17, "eval": 11, "data": 4},
    "1X_Robotics":         {"infer": 72, "train": 14, "eval":  9, "data": 5},
    "Apptronik":           {"infer": 65, "train": 21, "eval": 10, "data": 4},
    "Agility":             {"infer": 66, "train": 19, "eval": 11, "data": 4},
    "Sanctuary":           {"infer": 64, "train": 18, "eval": 13, "data": 5},
}

# 30-day weekly volumes (4 data-points each = 4 weeks)
WEEKLY_TRENDS = {
    "PrecisionIndustries": [9800, 10500, 11200, 12400],
    "1X_Robotics":         [980,   930,   880,   803],
    "Apptronik":           [3200,  3800,  4600,  4288],  # +34% but latest week dipped slightly
    "Agility":             [2100,  2400,  2650,  2900],
    "Sanctuary":           [1500,  1600,  1750,  1820],
}
TREND_LABELS = {
    "PrecisionIndustries": "+27% MoM",
    "1X_Robotics":         "-18% MoM",
    "Apptronik":           "+34% MoM",
    "Agility":             "+38% MoM",
    "Sanctuary":           "+21% MoM",
}
TREND_COLORS = {
    "PrecisionIndustries": "#38bdf8",
    "1X_Robotics":         "#C74634",
    "Apptronik":           "#4ade80",
    "Agility":             "#a78bfa",
    "Sanctuary":           "#fbbf24",
}

# ── SVG builders ──────────────────────────────────────────────────────────────

def svg_heatmap() -> str:
    CELL_W, CELL_H = 26, 38
    PAD_L, PAD_T = 140, 50
    HOURS = 24
    W = PAD_L + HOURS * CELL_W + 20
    H = PAD_T + len(PARTNERS) * CELL_H + 50

    # global max for color normalization
    global_max = max(v for row in HOURLY_DENSITY.values() for v in row)

    def heat_color(val):
        t = val / global_max
        if t < 0.25:
            r = int(15 + t * 4 * (30 - 15))
            g = int(23 + t * 4 * (58 - 23))
            b = int(42 + t * 4 * (95 - 42))
        elif t < 0.5:
            s = (t - 0.25) * 4
            r = int(30 + s * (56 - 30))
            g = int(58 + s * (142 - 58))
            b = int(95 + s * (148 - 95))
        elif t < 0.75:
            s = (t - 0.5) * 4
            r = int(56 + s * (180 - 56))
            g = int(142 + s * (120 - 142))
            b = int(148 + s * (60 - 148))
        else:
            s = (t - 0.75) * 4
            r = int(180 + s * (199 - 180))
            g = int(120 + s * (70 - 120))
            b = int(60 + s * (52 - 60))
        return f"#{min(255,r):02x}{min(255,g):02x}{min(255,b):02x}"

    cells = ""
    for ri, p in enumerate(PARTNERS):
        for h in range(HOURS):
            val = HOURLY_DENSITY[p][h]
            x = PAD_L + h * CELL_W
            y = PAD_T + ri * CELL_H
            fill = heat_color(val)
            cells += (
                f'<rect x="{x}" y="{y}" width="{CELL_W-1}" height="{CELL_H-2}" '
                f'fill="{fill}" rx="2"/>'
            )
            if val >= 50:
                cells += (
                    f'<text x="{x+CELL_W//2}" y="{y+CELL_H//2+4}" text-anchor="middle" '
                    f'fill="#fff" font-size="8" font-weight="bold">{val}</text>'
                )

    row_labels = "".join(
        f'<text x="{PAD_L-6}" y="{PAD_T+ri*CELL_H+CELL_H//2+4}" text-anchor="end" '
        f'fill="{TREND_COLORS[p]}" font-size="11" font-family="monospace">{PARTNER_SHORT[ri]}</text>'
        for ri, p in enumerate(PARTNERS)
    )

    col_labels = "".join(
        f'<text x="{PAD_L+h*CELL_W+CELL_W//2}" y="{PAD_T+len(PARTNERS)*CELL_H+14}" '
        f'text-anchor="middle" fill="#64748b" font-size="9">{h}</text>'
        for h in range(0, 24, 2)
        for _ in [True]
    )

    # gradient legend
    grad_stops = " ".join(
        f'<stop offset="{i*10}%" stop-color="{heat_color(global_max*i/10)}"/>'
        for i in range(11)
    )

    svg = f"""<svg viewBox="0 0 {W} {H+30}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <defs>
    <linearGradient id="heatGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      {grad_stops}
    </linearGradient>
  </defs>
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Partner API Call Heatmap (calls/hour avg)</text>
  <text x="{W//2}" y="37" text-anchor="middle" fill="#64748b" font-size="10"
        font-family="monospace">5 partners × 24 hours · PI peaks 9AM/2PM · 1X flat · Apt high morning</text>
  {row_labels}
  {cells}
  {col_labels}
  <!-- legend -->
  <text x="{PAD_L}" y="{H+12}" fill="#64748b" font-size="9">low</text>
  <rect x="{PAD_L+25}" y="{H+2}" width="140" height="12" fill="url(#heatGrad)" rx="3"/>
  <text x="{PAD_L+170}" y="{H+12}" fill="#64748b" font-size="9">high ({global_max})</text>
  <text x="{W//2}" y="{H+26}" text-anchor="middle" fill="#475569" font-size="9">hour (0–23)</text>
</svg>"""
    return svg


def svg_endpoint_bars() -> str:
    W, H = 680, 300
    PAD = {"l": 110, "r": 120, "t": 50, "b": 50}
    CW = W - PAD["l"] - PAD["r"]
    CH = H - PAD["t"] - PAD["b"]
    bar_h = CH / len(PARTNERS) * 0.65
    gap = CH / len(PARTNERS)
    EP_COLORS = {"infer": "#38bdf8", "train": "#a78bfa", "eval": "#fbbf24", "data": "#4ade80"}
    endpoints = ["infer", "train", "eval", "data"]

    bars = ""
    for ri, p in enumerate(PARTNERS):
        y = PAD["t"] + ri * gap + gap * 0.175
        usage = ENDPOINT_USAGE[p]
        total = sum(usage.values())
        x_cursor = PAD["l"]
        for ep in endpoints:
            pct = usage[ep] / total
            bw = pct * CW
            bars += (
                f'<rect x="{x_cursor:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" '
                f'fill="{EP_COLORS[ep]}" opacity="0.88"/>'
            )
            if bw > 24:
                bars += (
                    f'<text x="{x_cursor+bw/2:.1f}" y="{y+bar_h/2+4:.1f}" text-anchor="middle" '
                    f'fill="#0f172a" font-size="10" font-weight="bold">{usage[ep]}%</text>'
                )
            x_cursor += bw
        bars += (
            f'<text x="{PAD["l"]-6}" y="{y+bar_h/2+4:.1f}" text-anchor="end" '
            f'fill="{TREND_COLORS[p]}" font-size="11" font-family="monospace">{PARTNER_SHORT[ri]}</text>'
        )

    legend = ""
    lx = W - PAD["r"] + 10
    for i, ep in enumerate(endpoints):
        ly = PAD["t"] + i * 24
        legend += (
            f'<rect x="{lx}" y="{ly}" width="12" height="12" fill="{EP_COLORS[ep]}" rx="2"/>'
            f'<text x="{lx+16}" y="{ly+10}" fill="#94a3b8" font-size="11" '
            f'font-family="monospace">/{ep}</text>'
        )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Endpoint Usage per Partner (stacked %)</text>
  <text x="{W//2}" y="36" text-anchor="middle" fill="#64748b" font-size="10"
        font-family="monospace">/infer dominant 67% · /train 18% · /eval 11% · /data 4%</text>
  {bars}
  {legend}
  <line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" y2="{PAD["t"]+CH}"
        stroke="#334155" stroke-width="1"/>
  <line x1="{PAD["l"]}" y1="{PAD["t"]+CH}" x2="{PAD["l"]+CW}" y2="{PAD["t"]+CH}"
        stroke="#334155" stroke-width="1"/>
</svg>"""
    return svg


def svg_sparklines() -> str:
    W, H = 700, 280
    MINI_W, MINI_H = 110, 50
    PAD_X, PAD_Y = 30, 55
    COLS = 5
    SPACING_X = (W - PAD_X * 2) / COLS

    sparks = ""
    for i, p in enumerate(PARTNERS):
        col = i % COLS
        bx = PAD_X + col * SPACING_X
        by = PAD_Y

        vols = WEEKLY_TRENDS[p]
        mn, mx = min(vols), max(vols)
        if mx == mn:
            mx = mn + 1

        def px(week): return bx + week / (len(vols) - 1) * MINI_W
        def py(v): return by + MINI_H - (v - mn) / (mx - mn) * MINI_H

        polyline = " ".join(f"{px(j):.1f},{py(v):.1f}" for j, v in enumerate(vols))
        color = TREND_COLORS[p]
        trend = TREND_LABELS[p]
        trend_color = "#4ade80" if trend.startswith("+") else "#C74634"

        # fill area
        area_pts = (
            f"{px(0):.1f},{by+MINI_H} "
            + polyline +
            f" {px(len(vols)-1):.1f},{by+MINI_H}"
        )

        sparks += (
            f'<polygon points="{area_pts}" fill="{color}" opacity="0.12"/>'
            f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<circle cx="{px(len(vols)-1):.1f}" cy="{py(vols[-1]):.1f}" r="4" fill="{color}"/>'
            f'<text x="{bx+MINI_W/2:.1f}" y="{by-18}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-family="monospace" font-weight="bold">'
            f'{PARTNER_SHORT[i]}</text>'
            f'<text x="{bx+MINI_W/2:.1f}" y="{by-6}" text-anchor="middle" '
            f'fill="{trend_color}" font-size="10" font-family="monospace">{trend}</text>'
            f'<text x="{bx+MINI_W/2:.1f}" y="{by+MINI_H+16}" text-anchor="middle" '
            f'fill="#64748b" font-size="9">{vols[-1]:,}/wk</text>'
            # bounding box
            f'<rect x="{bx-4}" y="{by-4}" width="{MINI_W+8}" height="{MINI_H+8}" '
            f'fill="none" stroke="#1e293b" stroke-width="1" rx="4"/>'
        )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Usage Trend Sparklines (30-day weekly volume)</text>
  <text x="{W//2}" y="37" text-anchor="middle" fill="#64748b" font-size="10"
        font-family="monospace">Apt +34% MoM · 1X -18% MoM · DAgger activity drives /train spikes</text>
  {sparks}
</svg>"""
    return svg


# ── HTML page ─────────────────────────────────────────────────────────────────

def build_html() -> str:
    hm = svg_heatmap()
    ep = svg_endpoint_bars()
    sp = svg_sparklines()

    summary_rows = ""
    for p, short in zip(PARTNERS, PARTNER_SHORT):
        weekly = WEEKLY_TRENDS[p][-1]
        trend = TREND_LABELS[p]
        pct_infer = ENDPOINT_USAGE[p]["infer"]
        color = TREND_COLORS[p]
        trend_color = "#4ade80" if trend.startswith("+") else "#C74634"
        summary_rows += (
            f"<tr><td style='color:{color}'>{short}</td>"
            f"<td>{weekly:,}/wk</td>"
            f"<td style='color:{trend_color}'>{trend}</td>"
            f"<td>{pct_infer}%</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Partner API Usage Heatmap — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#38bdf8;font-size:1.4rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
  .card h2{{color:#C74634;font-size:.95rem;margin-bottom:14px}}
  .full{{grid-column:1/-1}}
  .kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:140px}}
  .kpi .val{{color:#38bdf8;font-size:1.6rem;font-weight:bold}}
  .kpi .lbl{{color:#64748b;font-size:.75rem;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{color:#38bdf8;border-bottom:1px solid #334155;padding:8px 10px;text-align:left}}
  td{{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
  tr:hover td{{background:#1e293b}}
  svg{{display:block}}
</style>
</head>
<body>
<h1>Partner API Usage Heatmap</h1>
<div class="sub">OCI Robot Cloud · Port 8647 · cycle-147A</div>

<div class="kpi-row">
  <div class="kpi"><div class="val">12,400</div><div class="lbl">PI calls/week</div></div>
  <div class="kpi"><div class="val">67%</div><div class="lbl">/infer share</div></div>
  <div class="kpi"><div class="val" style="color:#C74634">-71%</div><div class="lbl">Weekend drop</div></div>
  <div class="kpi"><div class="val" style="color:#4ade80">+34%</div><div class="lbl">Apt MoM growth</div></div>
  <div class="kpi"><div class="val" style="color:#C74634">-18%</div><div class="lbl">1X MoM decline</div></div>
  <div class="kpi"><div class="val">5</div><div class="lbl">Active partners</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>API Call Heatmap (5 partners × 24 hours)</h2>
    {hm}
  </div>
  <div class="card full">
    <h2>Endpoint Usage per Partner</h2>
    {ep}
  </div>
  <div class="card full">
    <h2>Usage Trend Sparklines (30-day)</h2>
    {sp}
  </div>
  <div class="card">
    <h2>Partner Summary</h2>
    <table>
      <thead><tr><th>Partner</th><th>Volume</th><th>Trend</th><th>/infer %</th></tr></thead>
      <tbody>{summary_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Key Insights</h2>
    <table>
      <thead><tr><th>Insight</th><th>Detail</th></tr></thead>
      <tbody>
        <tr><td>Peak hours</td><td>PI: 9AM (120/hr) &amp; 2PM (110/hr)</td></tr>
        <tr><td>Flattest profile</td><td>1X: 8–14/hr throughout day</td></tr>
        <tr><td>Morning-heavy</td><td>Apt: 98/hr at 9AM then declines</td></tr>
        <tr><td>DAgger signal</td><td>/train spikes correlate with DAgger runs</td></tr>
        <tr><td>Weekend effect</td><td>-71% call drop on Sat/Sun</td></tr>
      </tbody>
    </table>
  </div>
</div>
</body>
</html>"""


# ── app ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Partner API Usage Heatmap", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "partner_api_usage_heatmap", "port": 8647})

    @app.get("/api/usage")
    async def get_usage():
        return JSONResponse({
            "hourly_density": HOURLY_DENSITY,
            "endpoint_usage": ENDPOINT_USAGE,
            "weekly_trends": WEEKLY_TRENDS,
            "trend_labels": TREND_LABELS,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8647)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8647}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8647), Handler)
        print("Partner API Usage Heatmap running on :8647")
        srv.serve_forever()
