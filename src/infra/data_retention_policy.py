#!/usr/bin/env python3
"""
data_retention_policy.py — Data lifecycle, retention schedules & compliance
Port: 8337
Dashboard: retention timeline + storage cost projection
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TODAY = datetime(2026, 3, 30)

DATA_CATEGORIES = [
    {
        "name": "raw_demos",
        "display": "Raw Demonstrations",
        "size_tb": 1.8,
        "retention_days": 90,
        "action": "Archive → S3-IA",
        "color": "#38bdf8",
        "ingested": datetime(2026, 1, 1),
        "deletion_date": datetime(2026, 4, 1),
        "compliance": "GDPR Art.5(e)",
    },
    {
        "name": "eval_episodes",
        "display": "Eval Episodes",
        "size_tb": 0.6,
        "retention_days": 180,
        "action": "Delete after review",
        "color": "#a78bfa",
        "ingested": datetime(2025, 10, 1),
        "deletion_date": datetime(2026, 3, 31),
        "compliance": "Internal policy",
    },
    {
        "name": "model_checkpoints",
        "display": "Model Checkpoints",
        "size_tb": 1.1,
        "retention_days": 365,
        "action": "Keep top-12 only",
        "color": "#f59e0b",
        "ingested": datetime(2025, 6, 1),
        "deletion_date": datetime(2026, 6, 1),
        "compliance": "IP retention",
    },
    {
        "name": "inference_logs",
        "display": "Inference Logs",
        "size_tb": 0.7,
        "retention_days": 30,
        "action": "Auto-purge",
        "color": "#34d399",
        "ingested": datetime(2026, 2, 28),
        "deletion_date": datetime(2026, 3, 30),
        "compliance": "SOC 2",
    },
    {
        "name": "partner_data",
        "display": "Partner Data",
        "size_tb": 0.5,
        "retention_days": 0,
        "action": "Explicit deletion request",
        "color": "#C74634",
        "ingested": datetime(2025, 12, 1),
        "deletion_date": None,
        "compliance": "GDPR Art.17 / DPA",
    },
]

TOTAL_TB = round(sum(c["size_tb"] for c in DATA_CATEGORIES), 1)
COMPLIANCE_COVERAGE = 94  # %

# Cost model: $0.023/GB/month S3 standard; retention policy routes to cheaper tiers
COST_PER_TB_STD = 23.0   # $/TB/month
COST_PER_TB_IA  =  5.0   # $/TB/month  (S3-IA / archive)
GROWTH_TB_PER_MONTH = 0.5


def _monthly_cost_no_policy(month: int) -> float:
    """Unbounded growth, all data on standard storage."""
    total = TOTAL_TB + month * GROWTH_TB_PER_MONTH
    return round(total * COST_PER_TB_STD, 2)


def _monthly_cost_with_policy(month: int) -> float:
    """Retention keeps managed data roughly bounded; cheaper tiers applied."""
    active_tb = TOTAL_TB * 0.35 + month * GROWTH_TB_PER_MONTH * 0.25
    archive_tb = TOTAL_TB * 0.40
    cost = active_tb * COST_PER_TB_STD + archive_tb * COST_PER_TB_IA
    return round(cost, 2)


MONTHLY_DATA = [
    {
        "month": m,
        "label": (TODAY + timedelta(days=30 * m)).strftime("%b %y"),
        "no_policy": _monthly_cost_no_policy(m),
        "with_policy": _monthly_cost_with_policy(m),
    }
    for m in range(13)
]

SAVINGS_12MO = round(MONTHLY_DATA[12]["no_policy"] - MONTHLY_DATA[12]["with_policy"], 0)

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_retention_timeline() -> str:
    """Horizontal band per data category showing ingestion → deletion."""
    W, H = 760, 280
    pad_l, pad_r, pad_t, pad_b = 170, 30, 40, 30
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(DATA_CATEGORIES)
    row_h = chart_h / n

    # Time axis: Jan 2025 → Jun 2026 = 18 months
    t_start = datetime(2025, 6, 1)
    t_end   = datetime(2026, 7, 1)
    total_days = (t_end - t_start).days

    def x_of(dt):
        return pad_l + (dt - t_start).days / total_days * chart_w

    bands_svg = ""
    labels_svg = ""
    today_x = x_of(TODAY)

    for i, cat in enumerate(DATA_CATEGORIES):
        y = pad_t + i * row_h
        cy = y + row_h * 0.5
        bar_h = row_h * 0.42

        x0 = x_of(cat["ingested"])
        x1 = x_of(cat["deletion_date"]) if cat["deletion_date"] else x_of(t_end)

        # ingested portion (before today)
        x_today_clamped = min(today_x, x1)
        if x_today_clamped > x0:
            bands_svg += (
                f'<rect x="{x0:.1f}" y="{cy - bar_h/2:.1f}" '
                f'width="{x_today_clamped - x0:.1f}" height="{bar_h:.1f}" '
                f'fill="{cat["color"]}" opacity="0.85" rx="3"/>'
            )
        # scheduled deletion portion
        if cat["deletion_date"] and cat["deletion_date"] > TODAY:
            bands_svg += (
                f'<rect x="{today_x:.1f}" y="{cy - bar_h/2:.1f}" '
                f'width="{x1 - today_x:.1f}" height="{bar_h:.1f}" '
                f'fill="{cat["color"]}" opacity="0.3" rx="3" stroke-dasharray="4,2" stroke="{cat["color"]}" stroke-width="1"/>'
            )
            # deletion marker
            bands_svg += (
                f'<line x1="{x1:.1f}" y1="{cy - bar_h:.1f}" x2="{x1:.1f}" y2="{cy + bar_h:.1f}" '
                f'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3,2"/>'
                f'<text x="{x1 + 3:.1f}" y="{cy + 3:.1f}" fill="#ef4444" font-size="8">DEL</text>'
            )
        elif not cat["deletion_date"]:
            # partner data: arrow indicating ongoing
            bands_svg += (
                f'<text x="{x1 - 5:.1f}" y="{cy + 4:.1f}" fill="{cat["color"]}" font-size="14">→</text>'
            )

        # size label on bar
        mid_x = (x0 + min(x1, today_x)) / 2
        bands_svg += (
            f'<text x="{mid_x:.1f}" y="{cy + 4:.1f}" fill="#0f172a" '
            f'font-size="9" text-anchor="middle" font-weight="bold">{cat["size_tb"]}TB</text>'
        )

        # category label
        labels_svg += (
            f'<text x="{pad_l - 8}" y="{cy + 4:.1f}" fill="{cat["color"]}" '
            f'font-size="10" text-anchor="end">{cat["display"]}</text>'
            f'<text x="{pad_l - 8}" y="{cy + 16:.1f}" fill="#475569" '
            f'font-size="8" text-anchor="end">{cat["action"]}</text>'
        )

    # today line
    today_line = (
        f'<line x1="{today_x:.1f}" y1="{pad_t - 10}" x2="{today_x:.1f}" y2="{pad_t + chart_h}" '
        f'stroke="#f59e0b" stroke-width="1.5"/>'
        f'<text x="{today_x:.1f}" y="{pad_t - 14}" fill="#f59e0b" font-size="9" text-anchor="middle">Today</text>'
    )

    # time axis ticks (every 2 months)
    ticks = ""
    cur = datetime(2025, 6, 1)
    while cur <= t_end:
        tx = x_of(cur)
        ticks += (
            f'<line x1="{tx:.1f}" y1="{pad_t + chart_h}" x2="{tx:.1f}" y2="{pad_t + chart_h + 5}" '
            f'stroke="#334155" stroke-width="1"/>'
            f'<text x="{tx:.1f}" y="{pad_t + chart_h + 16}" fill="#64748b" '
            f'font-size="8" text-anchor="middle">{cur.strftime("%b %y")}</text>'
        )
        # advance 2 months
        month = cur.month + 2
        year  = cur.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        cur   = datetime(year, month, 1)

    axis = (
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )

    title = f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Data Retention Schedule — Category Timeline</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{title}{axis}{ticks}{bands_svg}{labels_svg}{today_line}'
        f'</svg>'
    )


def svg_cost_projection() -> str:
    """Line chart: monthly storage cost over 12 months — no-policy (red) vs with-policy (green)."""
    W, H = 760, 300
    pad_l, pad_r, pad_t, pad_b = 70, 30, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    all_costs = [d["no_policy"] for d in MONTHLY_DATA] + [d["with_policy"] for d in MONTHLY_DATA]
    max_cost = max(all_costs) * 1.1

    def pt(m, cost):
        x = pad_l + m / 12 * chart_w
        y = pad_t + chart_h - (cost / max_cost) * chart_h
        return x, y

    def polyline(series_key, color):
        pts = " ".join(f"{pt(d['month'], d[series_key])[0]:.1f},{pt(d['month'], d[series_key])[1]:.1f}" for d in MONTHLY_DATA)
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'

    no_poly = polyline("no_policy", "#ef4444")
    wp_poly = polyline("with_policy", "#22c55e")

    # dots + values at 0, 6, 12
    dots = ""
    for m in [0, 6, 12]:
        d = MONTHLY_DATA[m]
        for key, col in [("no_policy", "#ef4444"), ("with_policy", "#22c55e")]:
            x, y = pt(m, d[key])
            dots += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}"/>'
                f'<text x="{x:.1f}" y="{y - 8:.1f}" fill="{col}" font-size="9" text-anchor="middle">${d[key]:.0f}</text>'
            )

    # savings annotation at month 12
    x12_no, y12_no = pt(12, MONTHLY_DATA[12]["no_policy"])
    x12_wp, y12_wp = pt(12, MONTHLY_DATA[12]["with_policy"])
    mid_y = (y12_no + y12_wp) / 2
    savings_arrow = (
        f'<line x1="{x12_no - 10:.1f}" y1="{y12_no:.1f}" x2="{x12_wp - 10:.1f}" y2="{y12_wp:.1f}" '
        f'stroke="#f59e0b" stroke-width="1.5" marker-end="url(#arr)"/>'
        f'<text x="{x12_no - 14:.1f}" y="{mid_y:.1f}" fill="#f59e0b" font-size="10" text-anchor="end">-${SAVINGS_12MO:.0f}/mo</text>'
    )

    # x-axis ticks
    ticks = ""
    for d in MONTHLY_DATA[::2]:
        x, _ = pt(d["month"], 0)
        ticks += (
            f'<line x1="{x:.1f}" y1="{pad_t + chart_h}" x2="{x:.1f}" y2="{pad_t + chart_h + 5}" stroke="#334155" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{pad_t + chart_h + 16}" fill="#64748b" font-size="9" text-anchor="middle">{d["label"]}</text>'
        )

    # y-axis grid
    grid = ""
    y_steps = 4
    for s in range(y_steps + 1):
        cost = max_cost * s / y_steps
        _, gy = pt(0, cost)
        grid += (
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W - pad_r}" y2="{gy:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{pad_l - 5}" y="{gy + 4:.1f}" fill="#475569" font-size="9" text-anchor="end">${cost:.0f}</text>'
        )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>'
    )

    legend = (
        f'<line x1="{pad_l}" y1="{pad_t - 22}" x2="{pad_l + 22}" y2="{pad_t - 22}" stroke="#ef4444" stroke-width="2.5"/>'
        f'<text x="{pad_l + 26}" y="{pad_t - 18}" fill="#ef4444" font-size="10">No retention policy (unbounded growth)</text>'
        f'<line x1="{pad_l + 230}" y1="{pad_t - 22}" x2="{pad_l + 252}" y2="{pad_t - 22}" stroke="#22c55e" stroke-width="2.5"/>'
        f'<text x="{pad_l + 256}" y="{pad_t - 18}" fill="#22c55e" font-size="10">With retention policy (tiered storage)</text>'
    )

    title = f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Storage Cost Projection — 12-Month Forecast</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{title}{grid}{axes}{ticks}{no_poly}{wp_poly}{dots}{savings_arrow}{legend}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_retention_timeline()
    svg2 = svg_cost_projection()

    upcoming = [
        c for c in DATA_CATEGORIES
        if c["deletion_date"] and c["deletion_date"] >= TODAY
        and c["deletion_date"] <= TODAY + timedelta(days=30)
    ]
    upcoming_count = len(upcoming)

    stat_cards = "".join([
        f'<div class="card"><div class="label">{lbl}</div><div class="value" style="color:{col}">{val}</div></div>'
        for lbl, val, col in [
            ("Total Managed Data",     f"{TOTAL_TB} TB",               "#38bdf8"),
            ("Data Categories",        str(len(DATA_CATEGORIES)),      "#a78bfa"),
            ("Upcoming Deletions",     f"{upcoming_count} (30d)",      "#f59e0b"),
            ("Compliance Coverage",    f"{COMPLIANCE_COVERAGE}%",      "#22c55e"),
            ("Policy Savings @ 12mo",  f"${SAVINGS_12MO:.0f}/mo",      "#34d399"),
            ("Checkpoints Policy",     "Top-12 only",                  "#C74634"),
        ]
    ])

    def del_date(cat):
        return cat["deletion_date"].strftime("%Y-%m-%d") if cat["deletion_date"] else "On request"

    def ret_str(cat):
        return f"{cat['retention_days']}d" if cat["retention_days"] else "Manual"

    rows = "".join([
        f'<tr><td style="color:{c["color"]}">{c["display"]}</td>'
        f'<td>{c["size_tb"]} TB</td>'
        f'<td>{ret_str(c)}</td>'
        f'<td>{del_date(c)}</td>'
        f'<td>{c["action"]}</td>'
        f'<td style="color:#94a3b8">{c["compliance"]}</td></tr>'
        for c in DATA_CATEGORIES
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Retention Policy — Port 8337</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 20px; }}
  .oracle-badge {{ display:inline-block; background:#C74634; color:#fff; font-size:0.72rem;
                   padding:2px 10px; border-radius:4px; margin-left:12px; vertical-align:middle; }}
  .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:14px 20px; min-width:160px; }}
  .label {{ font-size:0.72rem; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }}
  .value {{ font-size:1.3rem; font-weight:700; }}
  .section {{ margin-bottom:28px; }}
  h2 {{ font-size:1rem; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px; }}
  svg {{ max-width:100%; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.85rem; }}
  th {{ background:#1e293b; color:#64748b; text-transform:uppercase; font-size:0.72rem;
        letter-spacing:.05em; padding:8px 12px; text-align:left; border-bottom:1px solid #334155; }}
  td {{ padding:8px 12px; border-bottom:1px solid #1e293b; color:#cbd5e1; }}
  tr:hover td {{ background:#1e293b; }}
  .footer {{ color:#475569; font-size:0.75rem; margin-top:24px; }}
</style>
</head>
<body>
<h1>Data Retention Policy <span class="oracle-badge">OCI Robot Cloud</span></h1>
<p class="subtitle">Data lifecycle management · GDPR/compliance-driven deletion · tiered storage · Port 8337</p>

<div class="stats">{stat_cards}</div>

<div class="section">
  <h2>Retention Schedule — Category Timeline</h2>
  {svg1}
</div>

<div class="section">
  <h2>Storage Cost Projection (12 Months)</h2>
  {svg2}
</div>

<div class="section">
  <h2>Policy Details</h2>
  <table>
    <thead><tr>
      <th>Category</th><th>Current Size</th><th>Retention</th>
      <th>Scheduled Deletion</th><th>Action</th><th>Compliance</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="footer">Data Retention Policy · OCI Robot Cloud · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Data Retention Policy", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/api/categories")
    def api_categories():
        return {
            "categories": [
                {
                    "name": c["name"],
                    "size_tb": c["size_tb"],
                    "retention_days": c["retention_days"],
                    "action": c["action"],
                    "compliance": c["compliance"],
                    "deletion_date": c["deletion_date"].isoformat() if c["deletion_date"] else None,
                }
                for c in DATA_CATEGORIES
            ],
            "total_tb": TOTAL_TB,
            "compliance_coverage_pct": COMPLIANCE_COVERAGE,
            "policy_savings_mo": SAVINGS_12MO,
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "data_retention_policy", "port": 8337}

else:
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
        uvicorn.run(app, host="0.0.0.0", port=8337)
    else:
        srv = http.server.HTTPServer(("0.0.0.0", 8337), Handler)
        print("Serving on http://0.0.0.0:8337 (stdlib fallback)")
        srv.serve_forever()
