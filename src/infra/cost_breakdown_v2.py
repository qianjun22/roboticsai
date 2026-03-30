"""Cost Breakdown v2 — FastAPI service on port 8245.

Enhanced cost breakdown with per-customer and per-pipeline attribution for
OCI Robot Cloud. Treemap decomposition + monthly trend area chart.
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
from datetime import datetime

# ── Mock data ──────────────────────────────────────────────────────────────

# March 2026 actuals ($224 total)
MARCH_TOTAL = 224.0

CATEGORIES = [
    {"name": "fine_tune", "pct": 0.41, "amount": 92.0,  "color": "#38bdf8"},
    {"name": "dagger",    "pct": 0.28, "amount": 63.0,  "color": "#C74634"},
    {"name": "sdg",       "pct": 0.18, "amount": 40.0,  "color": "#a78bfa"},
    {"name": "eval",      "pct": 0.08, "amount": 18.0,  "color": "#34d399"},
    {"name": "inference", "pct": 0.05, "amount": 11.0,  "color": "#f59e0b"},
]

PARTNERS = [
    {"name": "PI",          "pct": 0.38},
    {"name": "AgiBot",      "pct": 0.24},
    {"name": "Apptronik",   "pct": 0.19},
    {"name": "PickNikRob",  "pct": 0.12},
    {"name": "Internal",   "pct": 0.07},
]

# Monthly trend Jan-Jun 2026 (projected from March actuals)
# [fine_tune, dagger, sdg, eval, inference]
MONTHLY = {
    "Jan": [38,  26,  16,  7,   5],
    "Feb": [52,  35,  22,  9,   6],
    "Mar": [92,  63,  40,  18,  11],    # actuals
    "Apr": [145, 98,  62,  28,  17],    # projected
    "May": [280, 195, 120, 54,  33],    # AI World ramp
    "Jun": [420, 290, 180, 82,  50],    # ramp continues
}
MONTHS = list(MONTHLY.keys())
AI_WORLD_START = "May"  # ramp-up marker

# Forward projection $224 Mar → $1200 Sep
FULL_PROJECTION = {
    "Jan": 92, "Feb": 124, "Mar": 224, "Apr": 350,
    "May": 682, "Jun": 1022, "Jul": 1080, "Aug": 1150, "Sep": 1200,
}


def _cost_per_sr_point() -> float:
    """Rough cost per percentage point SR improvement (dagger vs BC baseline)."""
    sr_improvement = 0.05  # 5% absolute improvement per DAgger cycle
    cost_per_cycle = MARCH_TOTAL
    return round(cost_per_cycle / (sr_improvement * 100), 2)


def _partner_efficiency(partner_pct: float, sr_attributed: float = 0.72) -> float:
    """SR per dollar for a partner."""
    partner_cost = MARCH_TOTAL * partner_pct
    return round(sr_attributed / partner_cost, 4)


# ── SVG helpers ────────────────────────────────────────────────────────────

def _treemap_svg() -> str:
    """Nested rect treemap: top-level = categories, sub-rects = partner slices."""
    W, H = 700, 340
    margin_t, margin_b, margin_l, margin_r = 30, 10, 10, 10
    tw = W - margin_l - margin_r
    th = H - margin_t - margin_b

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace">Cost Treemap — March 2026 (${MARCH_TOTAL:.0f} total)</text>')

    x_cursor = margin_l
    for cat in CATEGORIES:
        cw = tw * cat["pct"]
        # outer rect
        lines.append(f'<rect x="{x_cursor:.1f}" y="{margin_t}" width="{cw:.1f}" height="{th}" fill="{cat["color"]}" fill-opacity="0.18" stroke="{cat["color"]}" stroke-width="1.5" rx="4"/>')
        # category label
        lx = x_cursor + cw / 2
        lines.append(f'<text x="{lx:.1f}" y="{margin_t + 14}" fill="{cat["color"]}" font-size="11" text-anchor="middle" font-family="monospace" font-weight="bold">{cat["name"]}</text>')
        lines.append(f'<text x="{lx:.1f}" y="{margin_t + 26}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">${cat["amount"]:.0f} ({cat["pct"]:.0%})</text>')

        # inner partner sub-rects (stacked vertically)
        inner_pad = 6
        inner_x = x_cursor + inner_pad
        inner_w = cw - inner_pad * 2
        inner_h_total = th - 40 - inner_pad * 2
        y_inner = margin_t + 38

        for partner in PARTNERS:
            ph = inner_h_total * partner["pct"]
            p_cost = cat["amount"] * partner["pct"]
            lines.append(f'<rect x="{inner_x:.1f}" y="{y_inner:.1f}" width="{inner_w:.1f}" height="{ph:.1f}" fill="{cat["color"]}" fill-opacity="0.45" rx="2"/>')
            if ph > 14 and inner_w > 40:
                lines.append(f'<text x="{inner_x + inner_w/2:.1f}" y="{y_inner + ph/2 + 4:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle" font-family="monospace">{partner["name"]}</text>')
            elif ph > 9 and inner_w > 20:
                lines.append(f'<text x="{inner_x + inner_w/2:.1f}" y="{y_inner + ph/2 + 3:.1f}" fill="#e2e8f0" font-size="8" text-anchor="middle" font-family="monospace">{partner["name"][0]}</text>')
            y_inner += ph

        x_cursor += cw

    # Partner legend
    lx0 = margin_l
    for p in PARTNERS:
        lines.append(f'<text x="{lx0}" y="{H - 2}" fill="#64748b" font-size="9" font-family="monospace">{p["name"]} {p["pct"]:.0%}</text>')
        lx0 += 108

    lines.append('</svg>')
    return '\n'.join(lines)


def _trend_svg() -> str:
    W, H = 700, 340
    margin_l, margin_r, margin_t, margin_b = 60, 20, 30, 50
    chart_w = W - margin_l - margin_r
    chart_h = H - margin_t - margin_b

    totals = [sum(MONTHLY[m]) for m in MONTHS]
    max_total = max(totals) * 1.15

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace">Monthly Cost Trend — Jan–Jun 2026 (Stacked)</text>')

    n = len(MONTHS)
    x_step = chart_w / (n - 1)

    def _x(i):
        return margin_l + i * x_step

    def _y(val):
        return margin_t + chart_h - (val / max_total) * chart_h

    # Y grid
    for tick in range(0, int(max_total) + 100, 200):
        yy = _y(tick)
        lines.append(f'<line x1="{margin_l}" y1="{yy:.1f}" x2="{W - margin_r}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{margin_l - 4}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">${tick}</text>')

    # Stacked area polygons (draw bottom-up: inference, eval, sdg, dagger, fine_tune)
    cat_order = list(reversed(CATEGORIES))  # fine_tune on top
    # compute stacked baseline per month
    stacks = [[0.0] * n]  # stacks[0] = zero baseline
    running = [0.0] * n
    for cat in cat_order:
        new_stack = []
        for i, m in enumerate(MONTHS):
            cat_idx = [c["name"] for c in CATEGORIES].index(cat["name"])
            running[i] += MONTHLY[m][cat_idx]
            new_stack.append(running[i])
        stacks.append(new_stack[:])

    for k, cat in enumerate(cat_order):
        top    = stacks[k + 1]
        bottom = stacks[k]
        pts_top    = [(f"{_x(i):.1f}", f"{_y(top[i]):.1f}")    for i in range(n)]
        pts_bottom = [(f"{_x(i):.1f}", f"{_y(bottom[i]):.1f}") for i in range(n - 1, -1, -1)]
        poly = " ".join(f"{x},{y}" for x, y in pts_top + pts_bottom)
        lines.append(f'<polygon points="{poly}" fill="{cat["color"]}" fill-opacity="0.55" stroke="{cat["color"]}" stroke-width="0.5"/>')

    # Total line
    total_pts = " ".join(f"{_x(i):.1f},{_y(totals[i]):.1f}" for i in range(n))
    lines.append(f'<polyline points="{total_pts}" fill="none" stroke="#f8fafc" stroke-width="2" stroke-dasharray="4 2"/>')
    for i, t in enumerate(totals):
        lines.append(f'<circle cx="{_x(i):.1f}" cy="{_y(t):.1f}" r="3" fill="#f8fafc"/>')
        lines.append(f'<text x="{_x(i):.1f}" y="{_y(t) - 7:.1f}" fill="#f8fafc" font-size="9" text-anchor="middle" font-family="monospace">${t}</text>')

    # X labels
    for i, m in enumerate(MONTHS):
        lines.append(f'<text x="{_x(i):.1f}" y="{margin_t + chart_h + 14}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">{m}</text>')

    # AI World ramp marker
    ai_i = MONTHS.index(AI_WORLD_START)
    ax = _x(ai_i)
    lines.append(f'<line x1="{ax:.1f}" y1="{margin_t}" x2="{ax:.1f}" y2="{margin_t + chart_h}" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6 3"/>')
    lines.append(f'<text x="{ax + 4:.1f}" y="{margin_t + 12}" fill="#fbbf24" font-size="10" font-family="monospace">AI World ramp</text>')

    # Legend
    lx = margin_l
    for cat in CATEGORIES:
        lines.append(f'<rect x="{lx}" y="{H - 16}" width="10" height="10" fill="{cat["color"]}" fill-opacity="0.7"/>')
        lines.append(f'<text x="{lx + 13}" y="{H - 6}" fill="#e2e8f0" font-size="9" font-family="monospace">{cat["name"]}</text>')
        lx += 90

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_html() -> str:
    treemap = _treemap_svg()
    trend   = _trend_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    cost_per_sr = _cost_per_sr_point()
    pi_efficiency = _partner_efficiency(0.38)
    ai_world_forecast = 682  # June projected total

    rows = ""
    for cat in CATEGORIES:
        partner_breakdown = " | ".join(
            f"{p['name']}: ${cat['amount'] * p['pct']:.1f}" for p in PARTNERS
        )
        rows += f"""
        <tr>
          <td style="color:{cat['color']}">{cat['name']}</td>
          <td>${cat['amount']:.0f}</td>
          <td>{cat['pct']:.0%}</td>
          <td style="font-size:11px;color:#64748b">{partner_breakdown}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Cost Breakdown v2 — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:12px;margin-bottom:20px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px}}
    .card .label{{color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px}}
    .card .value{{font-size:24px;font-weight:bold;margin-top:4px}}
    .card .sub2{{font-size:11px;color:#475569;margin-top:2px}}
    .charts{{display:flex;flex-wrap:wrap;gap:20px;margin-bottom:24px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;padding:10px 14px;text-align:left}}
    td{{padding:9px 14px;border-bottom:1px solid #0f172a;font-size:13px}}
    tr:hover td{{background:#263348}}
  </style>
</head>
<body>
  <h1>Cost Breakdown v2</h1>
  <div class="sub">Port 8245 &bull; OCI Robot Cloud &bull; {ts}</div>

  <div class="grid">
    <div class="card">
      <div class="label">March 2026 Actuals</div>
      <div class="value" style="color:#38bdf8">${MARCH_TOTAL:.0f}</div>
      <div class="sub2">total spend across all pipelines</div>
    </div>
    <div class="card">
      <div class="label">Cost / SR Point</div>
      <div class="value" style="color:#C74634">${cost_per_sr}</div>
      <div class="sub2">per 1% absolute SR improvement</div>
    </div>
    <div class="card">
      <div class="label">PI Partner Efficiency</div>
      <div class="value" style="color:#a78bfa">{pi_efficiency:.4f}</div>
      <div class="sub2">SR per dollar (largest partner 38%)</div>
    </div>
    <div class="card">
      <div class="label">AI World Budget (Jun)</div>
      <div class="value" style="color:#f59e0b">${ai_world_forecast}</div>
      <div class="sub2">projected; Sep target $1,200</div>
    </div>
  </div>

  <div class="charts">
    {treemap}
    {trend}
  </div>

  <table>
    <thead>
      <tr>
        <th>Pipeline</th>
        <th>March Cost</th>
        <th>Share</th>
        <th>Partner Attribution</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <div style="margin-top:16px;color:#475569;font-size:11px">
    Projection: $224 (Mar actuals) &rarr; $1,200 (Sep forecast) &bull; AI World ramp-up starts May 2026
  </div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(
        title="Cost Breakdown v2",
        description="Enhanced cost breakdown with per-customer and per-pipeline attribution for OCI Robot Cloud.",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/api/summary")
    def summary():
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "march_total_usd": MARCH_TOTAL,
            "categories": CATEGORIES,
            "partners": PARTNERS,
            "cost_per_sr_point_usd": _cost_per_sr_point(),
            "ai_world_ramp_start": AI_WORLD_START,
            "sep_projection_usd": 1200,
        }

    @app.get("/api/monthly")
    def monthly_trend():
        return {
            "months": MONTHS,
            "categories": [c["name"] for c in CATEGORIES],
            "data": {m: MONTHLY[m] for m in MONTHS},
            "totals": {m: sum(MONTHLY[m]) for m in MONTHS},
        }

    @app.get("/api/partners")
    def partner_breakdown():
        result = []
        for p in PARTNERS:
            result.append({
                "partner": p["name"],
                "share_pct": p["pct"],
                "march_cost_usd": round(MARCH_TOTAL * p["pct"], 2),
                "efficiency_sr_per_dollar": _partner_efficiency(p["pct"]),
            })
        return result

    @app.get("/health")
    def health():
        return {"status": "ok", "port": 8245, "service": "cost_breakdown_v2"}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","port":8245}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8245)
    else:
        print("FastAPI not available — starting stdlib fallback on port 8245")
        HTTPServer(("0.0.0.0", 8245), Handler).serve_forever()
