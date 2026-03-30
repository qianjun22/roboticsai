"""
sim_to_real_adaptation_tracker.py — port 8640
OCI Robot Cloud · cycle-145B
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

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_gap_closing_timeline() -> str:
    """Stacked area: sim2real gap Jan-Jun 2026, contributions: DAgger/Cosmos/DR."""
    W, H = 700, 320
    pad = {"l": 60, "r": 20, "t": 40, "b": 50}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]

    # months Jan-Jun (6 points)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    n = len(months)

    # Total gap goes from 27pp to 8pp
    total = [27, 24, 20, 16, 12, 8]
    # Contributions (sum = total)
    dagger  = [9,  9,  8,  7,  6,  4]
    cosmos  = [8,  7,  6,  5,  4,  2]
    dr      = [10, 8,  6,  4,  2,  2]

    y_max = 30

    def px(i):
        return pad["l"] + i * iw / (n - 1)

    def py(v):
        return pad["t"] + ih - (v / y_max) * ih

    def area_points(base, vals):
        top = [base[i] + vals[i] for i in range(n)]
        fwd = " ".join(f"{px(i):.1f},{py(top[i]):.1f}" for i in range(n))
        rev = " ".join(f"{px(i):.1f},{py(base[i]):.1f}" for i in range(n - 1, -1, -1))
        return fwd + " " + rev

    base0 = [0] * n
    base1 = dr
    base2 = [dr[i] + cosmos[i] for i in range(n)]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">Sim-to-Real Gap Closing Timeline (Jan\u2013Jun 2026)</text>',
        # DR area
        f'<polygon points="{area_points(base0, dr)}" fill="#C74634" opacity="0.55"/>',
        # Cosmos area
        f'<polygon points="{area_points(base1, cosmos)}" fill="#38bdf8" opacity="0.55"/>',
        # DAgger area
        f'<polygon points="{area_points(base2, dagger)}" fill="#34d399" opacity="0.55"/>',
        # total line
    ]
    # total line
    pts = " ".join(f"{px(i):.1f},{py(total[i]):.1f}" for i in range(n))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#f8fafc" stroke-width="2" stroke-dasharray="5,3"/>')

    # y-axis gridlines + labels
    for v in range(0, 31, 5):
        y = py(v)
        lines.append(f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{W - pad["r"]}" y2="{y:.1f}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad["l"] - 6}" y="{y + 4:.1f}" text-anchor="end" '
                     f'fill="#94a3b8" font-size="10">{v}pp</text>')

    # x-axis labels
    for i, m in enumerate(months):
        x = px(i)
        lines.append(f'<text x="{x:.1f}" y="{H - pad["b"] + 16}" text-anchor="middle" '
                     f'fill="#94a3b8" font-size="10">{m}</text>')
        lines.append(f'<line x1="{x:.1f}" y1="{pad["t"]}" x2="{x:.1f}" '
                     f'y2="{pad["t"] + ih}" stroke="#1e293b" stroke-width="1"/>')

    # data labels on total line
    for i in range(n):
        x, y = px(i), py(total[i])
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#f8fafc"/>')
        lines.append(f'<text x="{x:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
                     f'fill="#f8fafc" font-size="9">{total[i]}pp</text>')

    # legend
    legend = [("DR", "#C74634"), ("Cosmos", "#38bdf8"), ("DAgger", "#34d399")]
    for idx, (lbl, col) in enumerate(legend):
        lx = pad["l"] + idx * 120
        ly = H - 10
        lines.append(f'<rect x="{lx}" y="{ly - 9}" width="12" height="9" fill="{col}" opacity="0.75"/>')
        lines.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="10">{lbl}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def svg_per_modality_gap() -> str:
    """Horizontal bar chart: gap per modality with target line."""
    W, H = 640, 280
    modalities = ["Visual", "Dynamics", "Latency", "Force"]
    gaps    = [18, 8, 6, 4]
    targets = [6,  3, 2, 1]
    colors  = ["#C74634", "#f59e0b", "#38bdf8", "#34d399"]

    pad = {"l": 80, "r": 30, "t": 40, "b": 30}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]
    bar_h = ih / len(modalities) * 0.55
    x_max = 22

    def px(v):
        return pad["l"] + (v / x_max) * iw

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">Per-Modality Sim-to-Real Gap</text>',
    ]

    for i, (mod, gap, tgt, col) in enumerate(zip(modalities, gaps, targets, colors)):
        cy = pad["t"] + i * (ih / len(modalities)) + (ih / len(modalities)) * 0.2
        # bar
        lines.append(f'<rect x="{pad["l"]}" y="{cy:.1f}" width="{px(gap) - pad["l"]:.1f}" '
                     f'height="{bar_h:.1f}" fill="{col}" opacity="0.8" rx="2"/>')
        # target marker
        tx = px(tgt)
        lines.append(f'<line x1="{tx:.1f}" y1="{cy - 4:.1f}" x2="{tx:.1f}" '
                     f'y2="{cy + bar_h + 4:.1f}" stroke="#f8fafc" stroke-width="2" stroke-dasharray="3,2"/>')
        lines.append(f'<text x="{tx + 3:.1f}" y="{cy - 6:.1f}" fill="#94a3b8" font-size="9">target {tgt}pp</text>')
        # label left
        lines.append(f'<text x="{pad["l"] - 6}" y="{cy + bar_h * 0.65:.1f}" '
                     f'text-anchor="end" fill="#e2e8f0" font-size="11">{mod}</text>')
        # value right
        lines.append(f'<text x="{px(gap) + 5:.1f}" y="{cy + bar_h * 0.65:.1f}" '
                     f'fill="{col}" font-size="11" font-weight="bold">{gap}pp</text>')

    # x-axis
    for v in range(0, 23, 5):
        x = px(v)
        lines.append(f'<line x1="{x:.1f}" y1="{pad["t"]}" x2="{x:.1f}" '
                     f'y2="{H - pad["b"]}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H - pad["b"] + 12}" text-anchor="middle" '
                     f'fill="#64748b" font-size="9">{v}pp</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def svg_adaptation_velocity() -> str:
    """Line chart: gap reduction per DAgger round (diminishing returns)."""
    W, H = 640, 280
    pad = {"l": 55, "r": 20, "t": 40, "b": 50}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]

    rounds = list(range(1, 9))
    # gap reduction pp per round — diminishing returns
    reduction = [6.5, 4.8, 3.7, 2.9, 2.2, 1.7, 1.3, 1.0]
    y_max = 8

    def px(i):
        return pad["l"] + (i - 1) * iw / (len(rounds) - 1)

    def py(v):
        return pad["t"] + ih - (v / y_max) * ih

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="13" font-weight="bold">Adaptation Velocity \u2014 Gap Reduction / DAgger Round</text>',
    ]

    # fill under curve
    fill_pts = (f"{px(rounds[0]):.1f},{py(0):.1f} " +
                " ".join(f"{px(r):.1f},{py(v):.1f}" for r, v in zip(rounds, reduction)) +
                f" {px(rounds[-1]):.1f},{py(0):.1f}")
    lines.append(f'<polygon points="{fill_pts}" fill="#38bdf8" opacity="0.18"/>')

    # line
    pts = " ".join(f"{px(r):.1f},{py(v):.1f}" for r, v in zip(rounds, reduction))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # dots + labels
    for r, v in zip(rounds, reduction):
        x, y = px(r), py(v)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#38bdf8"/>')
        lines.append(f'<text x="{x:.1f}" y="{y - 9:.1f}" text-anchor="middle" '
                     f'fill="#38bdf8" font-size="9">{v}pp</text>')

    # gridlines + axes
    for v in [0, 2, 4, 6, 8]:
        y = py(v)
        lines.append(f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{W - pad["r"]}" y2="{y:.1f}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad["l"] - 5}" y="{y + 4:.1f}" text-anchor="end" '
                     f'fill="#94a3b8" font-size="9">{v}pp</text>')

    for r in rounds:
        x = px(r)
        lines.append(f'<text x="{x:.1f}" y="{H - pad["b"] + 16}" text-anchor="middle" '
                     f'fill="#94a3b8" font-size="10">R{r}</text>')

    # annotation
    lines.append(f'<text x="{px(5):.1f}" y="{py(4.5):.1f}" fill="#f59e0b" font-size="10"'
                 f' font-style="italic">diminishing returns</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_gap_closing_timeline()
    svg2 = svg_per_modality_gap()
    svg3 = svg_adaptation_velocity()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Sim-to-Real Adaptation Tracker \u00b7 OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
  h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
  .subtitle{{color:#38bdf8;font-size:.85rem;margin-bottom:20px}}
  .kpi-row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:160px}}
  .kpi .val{{font-size:1.7rem;font-weight:700;color:#C74634}}
  .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
  .kpi.blue .val{{color:#38bdf8}}
  .kpi.green .val{{color:#34d399}}
  .kpi.yellow .val{{color:#f59e0b}}
  .charts{{display:flex;flex-direction:column;gap:28px}}
  .chart-card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
  .chart-title{{color:#94a3b8;font-size:.8rem;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}}
  svg{{display:block;max-width:100%;height:auto}}
  footer{{margin-top:28px;color:#475569;font-size:.7rem;text-align:center}}
</style>
</head>
<body>
<h1>Sim-to-Real Adaptation Tracker</h1>
<p class="subtitle">OCI Robot Cloud \u00b7 port 8640 \u00b7 cycle-145B</p>

<div class="kpi-row">
  <div class="kpi"><div class="val">11pp</div><div class="lbl">Current sim2real gap</div></div>
  <div class="kpi blue"><div class="val">18pp</div><div class="lbl">Visual modality (largest)</div></div>
  <div class="kpi green"><div class="val">4pp</div><div class="lbl">Force modality (smallest)</div></div>
  <div class="kpi yellow"><div class="val">\u22125pp</div><div class="lbl">Cosmos per update cycle</div></div>
  <div class="kpi"><div class="val">100</div><div class="lbl">Real demos \u00b7 PI lab</div></div>
</div>

<div class="charts">
  <div class="chart-card">
    <div class="chart-title">Gap Closing Timeline \u2014 stacked contributions (Jan\u2013Jun 2026)</div>
    {svg1}
  </div>
  <div class="chart-card">
    <div class="chart-title">Per-Modality Gap vs Target</div>
    {svg2}
  </div>
  <div class="chart-card">
    <div class="chart-title">Adaptation Velocity \u2014 gap reduction per DAgger round</div>
    {svg3}
  </div>
</div>

<footer>OCI Robot Cloud \u00b7 Sim-to-Real Adaptation Tracker \u00b7 port 8640</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Sim-to-Real Adaptation Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_to_real_adaptation_tracker", "port": 8640}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8640)

else:
    # stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"sim_to_real_adaptation_tracker","port":8640}'
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", 8640), Handler).serve_forever()
