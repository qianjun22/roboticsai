"""ARR Dashboard v2 — FastAPI port 8743"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8743

# Deterministic-ish fake ARR data seeded by calendar month
random.seed(42)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SEGMENTS = [
    ("Enterprise",   "#C74634"),
    ("Mid-Market",   "#38bdf8"),
    ("SMB",          "#34d399"),
    ("Public Sector","#f472b6"),
]

def generate_arr_series(base, growth_rate, noise_scale, n=12):
    """Compound growth + Gaussian noise ARR series (in $k)."""
    vals = []
    v = base
    for _ in range(n):
        v *= (1 + growth_rate + random.gauss(0, noise_scale))
        vals.append(max(v, 0.0))
    return vals

def stacked_area_svg(series_list, colors, x0, y0, w, h, months):
    """Render stacked area chart for multiple series (same length)."""
    n = len(series_list[0])
    totals = [sum(series_list[s][i] for s in range(len(series_list))) for i in range(n)]
    max_total = max(totals) or 1
    parts = []
    # Accumulate stacked y positions bottom-up
    accum = [0.0] * n
    for si, (series, color) in enumerate(zip(series_list, colors)):
        top_y = []
        for i in range(n):
            accum[i] += series[i]
            yv = y0 + h - (accum[i] / max_total) * h
            top_y.append((x0 + i / (n - 1) * w, yv))
        # Build polygon: top line + bottom line reversed
        prev_accum = [accum[i] - series[i] for i in range(n)]
        bot_y = [
            (x0 + i / (n - 1) * w, y0 + h - (prev_accum[i] / max_total) * h)
            for i in range(n)
        ]
        pts = top_y + list(reversed(bot_y))
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(
            f'<polygon points="{pts_str}" fill="{color}" opacity="0.8"/>'
        )
    # Month labels
    for i, mo in enumerate(months):
        lx = x0 + i / (n - 1) * w
        parts.append(
            f'<text x="{lx:.1f}" y="{y0 + h + 16}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="10">{mo}</text>'
        )
    # Total line
    line_pts = " ".join(
        f"{x0 + i/(n-1)*w:.1f},{y0 + h - (totals[i]/max_total)*h:.1f}"
        for i in range(n)
    )
    parts.append(
        f'<polyline points="{line_pts}" fill="none" stroke="#fff" '
        f'stroke-width="1.5" stroke-dasharray="4 2" opacity="0.5"/>'
    )
    return "".join(parts)

def waterfall_svg(new_biz, expansion, churn, x0, y0, w, h):
    """ARR movement waterfall (new biz, expansion, churn)."""
    items = [
        ("New Biz", new_biz, "#34d399"),
        ("Expansion", expansion, "#38bdf8"),
        ("Churn", -abs(churn), "#f87171"),
        ("Net New", new_biz + expansion - abs(churn), "#C74634"),
    ]
    max_abs = max(abs(v) for _, v, _ in items) or 1
    bar_w = (w - 20) / len(items) - 10
    parts = []
    for i, (label, val, color) in enumerate(items):
        bh = (abs(val) / max_abs) * (h - 20)
        bx = x0 + i * (bar_w + 10)
        by = y0 + h / 2 - (bh if val >= 0 else 0)
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
            f'height="{bh:.1f}" fill="{color}" rx="3"/>'
        )
        sign = "+" if val >= 0 else ""
        parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 5:.1f}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-family="monospace">{sign}${val/1000:.0f}k</text>'
        )
        parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{y0 + h + 16}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="10">{label}</text>'
        )
    # Zero line
    zero_y = y0 + h / 2
    parts.append(
        f'<line x1="{x0}" y1="{zero_y:.1f}" x2="{x0 + w}" y2="{zero_y:.1f}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    return "".join(parts)

def build_html():
    # Generate per-segment ARR series
    seg_data = [
        generate_arr_series(base=b, growth_rate=g, noise_scale=0.02)
        for b, g in [(4200, 0.08), (1800, 0.06), (620, 0.04), (950, 0.07)]
    ]
    colors = [c for _, c in SEGMENTS]

    # Current month metrics
    total_arr = sum(series[-1] for series in seg_data)  # $k
    prev_arr = sum(series[-2] for series in seg_data)
    mom_growth = (total_arr - prev_arr) / prev_arr * 100
    yoy_growth = (sum(s[-1] for s in seg_data) / sum(s[0] for s in seg_data) - 1) * 100
    new_biz  = total_arr * 0.18
    expansion = total_arr * 0.09
    churn    = total_arr * 0.04
    net_new  = new_biz + expansion - churn
    nrr = (1 + (expansion - churn) / prev_arr) * 100

    # Top KPI cards
    kpis = [
        ("Total ARR",   f"${total_arr/1000:.2f}M",  f"+{mom_growth:.1f}% MoM", "#C74634"),
        ("Net New ARR", f"${net_new/1000:.2f}M",    f"This Month",              "#34d399"),
        ("NRR",         f"{nrr:.1f}%",              "Net Revenue Retention",   "#38bdf8"),
        ("YoY Growth",  f"{yoy_growth:.1f}%",       "Jan–Dec",                  "#f472b6"),
        ("Churn Rate",  f"{churn/total_arr*100:.1f}%", "Monthly Gross Churn",  "#fb923c"),
    ]
    kpi_cards = "".join(
        f'<div class="card" style="border-left:3px solid {clr}">'
        f'<div style="color:{clr};font-size:0.8rem;font-weight:700;text-transform:uppercase">{label}</div>'
        f'<div style="font-size:2rem;margin:4px 0;font-weight:800">{val}</div>'
        f'<div style="color:#94a3b8;font-size:0.78rem">{sub}</div>'
        f'</div>'
        for label, val, sub, clr in kpis
    )

    # Stacked area SVG
    area_w, area_h = 700, 160
    area_svg = (
        f'<svg width="{area_w}" height="{area_h + 30}" style="display:block">'
        + stacked_area_svg(seg_data, colors, 0, 0, area_w, area_h, MONTHS)
        + "</svg>"
    )

    # Waterfall SVG
    wf_w, wf_h = 420, 140
    wf_svg = (
        f'<svg width="{wf_w}" height="{wf_h + 30}" style="display:block">'
        + waterfall_svg(new_biz, expansion, churn, 10, 10, wf_w - 20, wf_h)
        + "</svg>"
    )

    # Segment breakdown table
    seg_rows = "".join(
        f'<tr style="border-bottom:1px solid #334155">'
        f'<td style="padding:9px 14px;color:{color};font-weight:600">{name}</td>'
        f'<td style="padding:9px 14px;font-family:monospace">${series[-1]/1000:.3f}M</td>'
        f'<td style="padding:9px 14px;font-family:monospace">{(series[-1]-series[-2])/series[-2]*100:+.1f}%</td>'
        f'<td style="padding:9px 14px;font-family:monospace">{series[-1]/total_arr*100:.1f}%</td>'
        f'<td style="padding:9px 14px">{sparkline(series, color)}</td>'
        f'</tr>'
        for (name, color), series in zip(SEGMENTS, seg_data)
    )

    # Legend
    legend = "".join(
        f'<span style="margin-right:16px"><span style="display:inline-block;width:12px;height:12px;'
        f'background:{color};border-radius:2px;margin-right:4px;vertical-align:middle"></span>'
        f'<span style="color:#cbd5e1;font-size:0.82rem">{name}</span></span>'
        for name, color in SEGMENTS
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>ARR Dashboard v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.5rem}}
.subtitle{{color:#94a3b8;padding:0 24px 16px;font-size:0.85rem}}
.section{{padding:0 24px 24px}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}}
.card{{background:#1e293b;padding:16px 20px;border-radius:8px;min-width:140px;flex:1}}
.charts{{display:flex;flex-wrap:wrap;gap:16px}}
.chart-box{{background:#1e293b;padding:16px 20px;border-radius:8px;flex:1;min-width:300px;overflow-x:auto}}
h2{{color:#38bdf8;margin-top:0;font-size:1rem}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:9px 14px;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em}}
</style></head>
<body>
<h1>ARR Dashboard v2</h1>
<div class="subtitle">OCI Robot Cloud &mdash; Annual Recurring Revenue Analytics &nbsp;|&nbsp; Port {PORT}</div>

<div class="section">
  <div class="cards">{kpi_cards}</div>
</div>

<div class="section">
  <div class="charts">
    <div class="chart-box">
      <h2>ARR by Segment (Stacked, 12-Month)</h2>
      <div style="margin-bottom:8px">{legend}</div>
      {area_svg}
    </div>
    <div class="chart-box">
      <h2>ARR Waterfall — Current Month</h2>
      {wf_svg}
    </div>
  </div>
</div>

<div class="section">
  <div class="card" style="overflow-x:auto">
    <h2>Segment Breakdown</h2>
    <table>
      <tr><th>Segment</th><th>ARR</th><th>MoM</th><th>Share</th><th>Trend</th></tr>
      {seg_rows}
    </table>
  </div>
</div>
</body></html>"""


def sparkline(pts, color, w=100, h=30):
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1e-9
    n = len(pts)
    coords = " ".join(
        f"{2 + i/(n-1)*(w-4):.1f},{2 + (h-4) - (v-lo)/span*(h-4):.1f}"
        for i, v in enumerate(pts)
    )
    return (
        f'<svg width="{w}" height="{h}">'
        f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>'
        f'</svg>'
    )


if USE_FASTAPI:
    app = FastAPI(title="ARR Dashboard v2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "segments": len(SEGMENTS)}

    @app.get("/api/arr")
    def api_arr():
        seg_data = [
            generate_arr_series(base=b, growth_rate=g, noise_scale=0.02)
            for b, g in [(4200, 0.08), (1800, 0.06), (620, 0.04), (950, 0.07)]
        ]
        return {
            seg: {"monthly_arr_k": series, "current_arr_k": series[-1]}
            for (seg, _), series in zip(SEGMENTS, seg_data)
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
