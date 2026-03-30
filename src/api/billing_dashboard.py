"""Partner billing and revenue tracking dashboard — port 8147."""
from __future__ import annotations

import math
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn") from e

app = FastAPI(title="Billing Dashboard", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

MONTHS = ["Jan 2026", "Feb 2026", "Mar 2026"]

PARTNERS: list[str] = ["physical_intelligence", "apptronik", "1x", "agility"]
PARTNER_COLORS: dict[str, str] = {
    "physical_intelligence": "#38bdf8",
    "apptronik":             "#f59e0b",
    "1x":                    "#22c55e",
    "agility":               "#a855f7",
}

BILLING: list[dict[str, Any]] = [
    {
        "month": "Jan 2026",
        "physical_intelligence": 1204.80,
        "apptronik":              0.00,
        "1x":                     0.00,
        "agility":                0.00,
        "total":               1204.80,
        "mom_growth": None,
    },
    {
        "month": "Feb 2026",
        "physical_intelligence": 1612.40,
        "apptronik":              412.30,
        "1x":                       0.00,
        "agility":                  0.00,
        "total":               2024.70,
        "mom_growth": 68.1,
    },
    {
        "month": "Mar 2026",
        "physical_intelligence": 1847.20,
        "apptronik":              876.50,
        "1x":                     298.86,
        "agility":                160.28,
        "total":               3182.84,
        "mom_growth": 57.2,
    },
]

PRICING_TIERS: list[dict[str, Any]] = [
    {"tier": "enterprise", "a100_hr": 3.06, "eval": 0.15, "finetune": 50.00},
    {"tier": "growth",     "a100_hr": 3.26, "eval": 0.20, "finetune": 65.00},
    {"tier": "starter",    "a100_hr": 3.46, "eval": 0.25, "finetune": 80.00},
]

UNIT_ECONOMICS = {
    "oci_a100_cost_hr":  2.18,
    "sell_price_hr":     3.06,
    "gross_margin_pct":  28.8,
    "target_margin_pct": 40.0,
    "target_monthly_rev": 10_000.0,
}

PROJECTED_APR = 4200.0

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _stacked_bar_svg() -> str:
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    max_total = max(b["total"] for b in BILLING) * 1.15
    n = len(BILLING)
    bar_w = plot_w / n * 0.55
    gap   = plot_w / n

    def bx(i: int) -> float:
        return pad_l + i * gap + (gap - bar_w) / 2

    def by(val: float, base: float = 0.0) -> float:
        return pad_t + plot_h * (1.0 - (base + val) / max_total)

    def bh(val: float) -> float:
        return plot_h * val / max_total

    bars = ""
    for i, month_data in enumerate(BILLING):
        base = 0.0
        x = bx(i)
        for partner in PARTNERS:
            val = month_data[partner]
            if val <= 0:
                base += val
                continue
            y = by(val, base)
            h = bh(val)
            color = PARTNER_COLORS[partner]
            bars += (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h,1):.1f}" '
                f'fill="{color}" opacity="0.9" rx="2"/>\n'
            )
            base += val
        # MoM label
        if month_data["mom_growth"] is not None:
            lx = x + bar_w / 2
            ly = by(month_data["total"]) - 6
            bars += (
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="10" fill="#22c55e" '
                f'text-anchor="middle">+{month_data["mom_growth"]:.0f}%</text>\n'
            )
        # X label
        mx = x + bar_w / 2
        my = H - 8
        bars += (
            f'<text x="{mx:.1f}" y="{my}" font-size="11" fill="#cbd5e1" '
            f'text-anchor="middle">{month_data["month"]}</text>\n'
        )

    # Y ticks
    y_ticks = ""
    for val in [0, 1000, 2000, 3000]:
        if val > max_total:
            break
        y = by(val)
        y_ticks += (
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.5"/>'
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" font-size="10" fill="#94a3b8" '
            f'text-anchor="end">${val:,}</text>\n'
        )

    # Legend
    legend = ""
    for j, partner in enumerate(PARTNERS):
        lx = pad_l + j * 155
        legend += (
            f'<rect x="{lx}" y="4" width="12" height="12" fill="{PARTNER_COLORS[partner]}"/>'
            f'<text x="{lx + 16}" y="14" font-size="10" fill="#cbd5e1">{partner}</text>\n'
        )

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{y_ticks}{bars}{legend}</svg>'
    )


def _partner_donut_svg() -> str:
    """Mar 2026 revenue breakdown."""
    W, H, cx, cy, R, r = 420, 280, 160, 140, 110, 60
    mar = BILLING[-1]  # Mar 2026
    total = mar["total"]
    start = -math.pi / 2
    paths = ""
    labels = ""
    for partner in PARTNERS:
        val = mar[partner]
        if val <= 0:
            continue
        sweep = 2 * math.pi * val / total
        end = start + sweep
        mid = start + sweep / 2
        lx = cx + (R + 22) * math.cos(mid)
        ly = cy + (R + 22) * math.sin(mid)
        x1, y1 = cx + R * math.cos(start), cy + R * math.sin(start)
        x2, y2 = cx + R * math.cos(end),   cy + R * math.sin(end)
        xi1, yi1 = cx + r * math.cos(end),  cy + r * math.sin(end)
        xi2, yi2 = cx + r * math.cos(start), cy + r * math.sin(start)
        large = 1 if sweep > math.pi else 0
        color = "#C74634" if partner == "physical_intelligence" else PARTNER_COLORS[partner]
        pct = val / total * 100
        paths += (
            f'<path d="M {x1:.2f},{y1:.2f} A {R},{R} 0 {large},1 {x2:.2f},{y2:.2f} '
            f'L {xi1:.2f},{yi1:.2f} A {r},{r} 0 {large},0 {xi2:.2f},{yi2:.2f} Z" '
            f'fill="{color}" opacity="0.9" stroke="#0f172a" stroke-width="2"/>\n'
        )
        anchor = "start" if lx > cx else "end"
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="#cbd5e1" '
            f'text-anchor="{anchor}">{pct:.0f}%</text>\n'
        )
        start = end

    center = (
        f'<text x="{cx}" y="{cy - 6}" font-size="12" fill="#94a3b8" text-anchor="middle">Mar 2026</text>'
        f'<text x="{cx}" y="{cy + 10}" font-size="12" fill="#38bdf8" text-anchor="middle">${total:,.2f}</text>'
    )
    legend = ""
    for i, partner in enumerate(PARTNERS):
        color = "#C74634" if partner == "physical_intelligence" else PARTNER_COLORS[partner]
        lx2, ly2 = W - 175, 60 + i * 26
        legend += (
            f'<rect x="{lx2}" y="{ly2 - 10}" width="12" height="12" fill="{color}"/>'
            f'<text x="{lx2 + 16}" y="{ly2}" font-size="10" fill="#cbd5e1">{partner}</text>\n'
        )
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{paths}{center}{labels}{legend}</svg>'
    )


def _arr_line_svg() -> str:
    """Cumulative ARR projection Jan–Dec 2026 at 40%/mo growth."""
    W, H = 680, 160
    pad_l, pad_r, pad_t, pad_b = 70, 20, 20, 40
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # Seed Jan with actuals, then grow at 40%/mo
    actuals = {0: 1204.80, 1: 2024.70, 2: 3182.84}
    values: list[float] = []
    for i in range(12):
        if i in actuals:
            values.append(actuals[i])
        else:
            values.append(values[-1] * 1.40)

    max_val = max(values) * 1.1

    def px(i: int) -> float:
        return pad_l + i * plot_w / 11

    def py(v: float) -> float:
        return pad_t + plot_h * (1.0 - v / max_val)

    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
    line = f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>\n'

    # Fill area
    fill_pts = f"{pad_l},{py(0):.1f} " + pts + f" {px(11):.1f},{py(0):.1f}"
    area = f'<polygon points="{fill_pts}" fill="#38bdf8" opacity="0.12"/>\n'

    # Dots for actuals
    dots = ""
    for i in range(3):
        dots += f'<circle cx="{px(i):.1f}" cy="{py(values[i]):.1f}" r="4" fill="#C74634"/>\n'

    # X labels
    x_labels = ""
    for i, lbl in enumerate(month_labels):
        x_labels += (
            f'<text x="{px(i):.1f}" y="{H - 6}" font-size="9" fill="#94a3b8" '
            f'text-anchor="middle">{lbl}</text>\n'
        )

    # Final value annotation
    final_val = values[-1]
    fx, fy = px(11), py(final_val) - 8
    annotation = (
        f'<text x="{fx:.1f}" y="{fy:.1f}" font-size="10" fill="#22c55e" '
        f'text-anchor="end">${final_val:,.0f}/mo</text>'
    )

    # Y ticks
    y_ticks = ""
    for val in [0, 10000, 20000, 30000, 40000]:
        if val > max_val:
            break
        y = py(val)
        y_ticks += (
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.5"/>'
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" font-size="9" fill="#94a3b8" '
            f'text-anchor="end">${val//1000}k</text>\n'
        )

    legend = (
        '<circle cx="12" cy="8" r="5" fill="#C74634"/>'
        '<text x="20" y="12" font-size="9" fill="#cbd5e1">actuals</text>'
        '<line x1="80" y1="8" x2="96" y2="8" stroke="#38bdf8" stroke-width="2.5"/>'
        '<text x="100" y="12" font-size="9" fill="#cbd5e1">40%/mo projection</text>'
    )
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{y_ticks}{area}{line}{dots}{x_labels}{annotation}{legend}</svg>'
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    total_billed = sum(b["total"] for b in BILLING)
    mar_total = BILLING[-1]["total"]
    ue = UNIT_ECONOMICS

    stat_cards = ""
    stats = [
        ("Jan–Mar Revenue", f"${total_billed:,.2f}", "#38bdf8"),
        ("Mar 2026 MRR",     f"${mar_total:,.2f}",    "#C74634"),
        ("Projected Apr",    f"${PROJECTED_APR:,.0f}", "#22c55e"),
        ("Gross Margin",     f"{ue['gross_margin_pct']:.1f}%", "#f59e0b"),
    ]
    for label, val, color in stats:
        stat_cards += f"""
        <div style="background:#1e293b;border-radius:10px;padding:18px 24px;
                    border-left:4px solid {color};min-width:160px">
          <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">{label}</div>
          <div style="font-size:26px;font-weight:700;color:{color}">{val}</div>
        </div>"""

    tier_rows = ""
    for tier in PRICING_TIERS:
        margin = (tier["a100_hr"] - ue["oci_a100_cost_hr"]) / tier["a100_hr"] * 100
        tier_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="text-transform:capitalize;font-weight:600">{tier['tier']}</td>
          <td style="text-align:center;color:#38bdf8">${tier['a100_hr']:.2f}/hr</td>
          <td style="text-align:center">${tier['eval']:.2f}/eval</td>
          <td style="text-align:center">${tier['finetune']:.2f}/run</td>
          <td style="text-align:center;color:#22c55e">{margin:.1f}%</td>
        </tr>"""

    billing_rows = ""
    for b in BILLING:
        growth_cell = (
            f'<td style="text-align:center;color:#22c55e">+{b["mom_growth"]:.0f}%</td>'
            if b["mom_growth"] else
            '<td style="text-align:center;color:#64748b">—</td>'
        )
        billing_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="font-weight:600">{b['month']}</td>
          {''.join(f'<td style="text-align:center;color:{PARTNER_COLORS[p]}">${b[p]:,.2f}</td>' for p in PARTNERS)}
          <td style="text-align:center;color:#e2e8f0;font-weight:600">${b['total']:,.2f}</td>
          {growth_cell}
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Billing Dashboard · Port 8147</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;padding:28px}}
  h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
  h2{{color:#cbd5e1;font-size:15px;margin:28px 0 12px;font-weight:600;text-transform:uppercase;
      letter-spacing:.08em}}
  .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
  table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px}}
  th{{background:#1e293b;color:#94a3b8;padding:10px 12px;text-align:left;
      font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
  td{{padding:10px 12px;color:#e2e8f0}}
  tr:hover td{{background:#1a2744}}
  .charts{{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start}}
  a{{color:#38bdf8;text-decoration:none;font-size:13px}}
  .nav{{display:flex;gap:12px;margin-bottom:24px}}
  .note{{background:#1e293b;border-left:3px solid #f59e0b;padding:10px 16px;
          border-radius:6px;font-size:12px;color:#94a3b8;margin-top:8px}}
</style></head><body>
<div class="nav">
  <a href="/">Dashboard</a>
  <a href="/invoices">Invoices JSON</a>
  <a href="/summary">Summary JSON</a>
  <a href="/forecast">Forecast JSON</a>
</div>
<h1>Partner Billing Dashboard</h1>
<p class="sub">Port 8147 · OCI Robot Cloud · Jan–Mar 2026 actuals</p>
<div class="cards">{stat_cards}</div>

<h2>Monthly Revenue by Partner (Stacked)</h2>
{_stacked_bar_svg()}

<h2>Billing History</h2>
<table>
<tr>
  <th>Month</th>
  {''.join(f'<th style="text-align:center">{p}</th>' for p in PARTNERS)}
  <th style="text-align:center">Total</th>
  <th style="text-align:center">MoM Growth</th>
</tr>
{billing_rows}
</table>

<h2>Pricing Tiers</h2>
<table>
<tr>
  <th>Tier</th><th style="text-align:center">A100/hr</th>
  <th style="text-align:center">Per Eval</th>
  <th style="text-align:center">Fine-Tune Run</th>
  <th style="text-align:center">GPU Margin</th>
</tr>
{tier_rows}
</table>
<div class="note">OCI A100 cost: ${ue['oci_a100_cost_hr']:.2f}/hr · Sell: ${ue['sell_price_hr']:.2f}/hr · Current margin: {ue['gross_margin_pct']:.1f}% · Target: {ue['target_margin_pct']:.0f}% at ${ue['target_monthly_rev']:,.0f}/mo</div>

<h2>Charts</h2>
<div class="charts">
  <div>
    <p style="color:#94a3b8;font-size:12px;margin-bottom:8px">Mar 2026 Partner Revenue Share</p>
    {_partner_donut_svg()}
  </div>
</div>

<h2>Cumulative ARR Projection (Jan–Dec 2026 · 40%/mo)</h2>
{_arr_line_svg()}
<div class="note">Red dots = actuals. Blue line = projection at 40%/mo sustained growth. Apr 2026 pipeline: figure_ai pilot conversion + organic growth → ${PROJECTED_APR:,.0f} target.</div>
</body></html>"""


@app.get("/invoices")
async def get_invoices() -> JSONResponse:
    return JSONResponse({"invoices": BILLING, "partners": PARTNERS})


@app.get("/summary")
async def get_summary() -> JSONResponse:
    ue = UNIT_ECONOMICS
    return JSONResponse({
        "jan_mar_total": round(sum(b["total"] for b in BILLING), 2),
        "mar_mrr": BILLING[-1]["total"],
        "projected_apr": PROJECTED_APR,
        "unit_economics": ue,
        "pricing_tiers": PRICING_TIERS,
    })


@app.get("/forecast")
async def get_forecast() -> JSONResponse:
    actuals = {0: 1204.80, 1: 2024.70, 2: 3182.84}
    values: list[float] = []
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i in range(12):
        if i in actuals:
            values.append(actuals[i])
        else:
            values.append(round(values[-1] * 1.40, 2))
    return JSONResponse({
        "year": 2026,
        "growth_rate_pct": 40.0,
        "monthly_forecast": [
            {"month": labels[i], "revenue": round(values[i], 2), "is_actual": i < 3}
            for i in range(12)
        ],
        "dec_2026_projected": round(values[-1], 2),
        "full_year_projected": round(sum(values), 2),
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8147)
