"""Pricing Optimizer Service — port 8911

4-tier pricing:
  Starter $990 / Growth $2,490 / Scale $5,990 / Enterprise custom
WTP analysis: median WTP $3,200/mo, elasticity -0.31
OCI 31% cheaper than AWS at Growth tier.
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

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pricing Optimizer</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.4rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.6rem 0 0.8rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .card {
    background: #1e293b; border-radius: 10px; padding: 1.2rem 1.6rem;
    min-width: 160px; flex: 1;
  }
  .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .05em; }
  .card .value { color: #f1f5f9; font-size: 1.8rem; font-weight: 700; margin-top: 0.3rem; }
  .card .delta { color: #4ade80; font-size: 0.85rem; margin-top: 0.2rem; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 1.2rem; margin-bottom: 1.5rem; }
  .tier-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .tier-card {
    background: #1e293b; border-radius: 10px; padding: 1.2rem;
    border-top: 4px solid #334155;
    transition: transform .15s;
  }
  .tier-card:hover { transform: translateY(-3px); }
  .tier-card.highlight { border-top-color: #C74634; }
  .tier-name { font-weight: 700; font-size: 1rem; color: #f1f5f9; }
  .tier-price { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin: 0.4rem 0; }
  .tier-sub { color: #94a3b8; font-size: 0.8rem; }
  .tier-features { margin-top: 0.8rem; }
  .tier-features li { font-size: 0.82rem; color: #cbd5e1; list-style: none; padding: 0.2rem 0; }
  .tier-features li::before { content: "✓ "; color: #4ade80; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #0f172a; color: #38bdf8; text-align: left; padding: 0.6rem 0.8rem; font-size: 0.82rem; text-transform: uppercase; }
  td { padding: 0.55rem 0.8rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
  tr:hover td { background: #1e293b; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #86efac; }
  .badge-red   { background: #7f1d1d; color: #fca5a5; }
</style>
</head>
<body>
<h1>Pricing Optimizer</h1>
<p class="subtitle">4-tier SaaS pricing analysis &mdash; WTP median $3,200/mo &mdash; elasticity &minus;0.31 &mdash; OCI 31% cheaper than AWS &mdash; port 8911</p>

<div class="cards">
  <div class="card"><div class="label">Median WTP</div><div class="value">$3,200</div><div class="delta">/month</div></div>
  <div class="card"><div class="label">Price Elasticity</div><div class="value">&minus;0.31</div><div class="delta">Inelastic demand</div></div>
  <div class="card"><div class="label">OCI vs AWS</div><div class="value">&minus;31%</div><div class="delta">At Growth tier</div></div>
  <div class="card"><div class="label">Revenue Peak</div><div class="value">$2,490</div><div class="delta">Growth tier optimal</div></div>
  <div class="card"><div class="label">TAM Coverage</div><div class="value">68%</div><div class="delta">Starter + Growth</div></div>
</div>

<h2>Pricing Tiers</h2>
<div class="tier-grid">
  <div class="tier-card">
    <div class="tier-name">Starter</div>
    <div class="tier-price">$990<span style="font-size:1rem;color:#94a3b8">/mo</span></div>
    <div class="tier-sub">Up to 5 robots</div>
    <ul class="tier-features">
      <li>BC fine-tuning</li>
      <li>5k inference calls/day</li>
      <li>Community support</li>
      <li>1 environment</li>
    </ul>
  </div>
  <div class="tier-card highlight">
    <div class="tier-name">Growth <span class="badge badge-green">Best Value</span></div>
    <div class="tier-price">$2,490<span style="font-size:1rem;color:#94a3b8">/mo</span></div>
    <div class="tier-sub">Up to 25 robots</div>
    <ul class="tier-features">
      <li>BC + DAgger fine-tuning</li>
      <li>50k inference calls/day</li>
      <li>Priority support</li>
      <li>5 environments</li>
      <li>SDG access</li>
    </ul>
  </div>
  <div class="tier-card">
    <div class="tier-name">Scale</div>
    <div class="tier-price">$5,990<span style="font-size:1rem;color:#94a3b8">/mo</span></div>
    <div class="tier-sub">Up to 100 robots</div>
    <ul class="tier-features">
      <li>Full pipeline</li>
      <li>Unlimited inference</li>
      <li>Dedicated SLA</li>
      <li>20 environments</li>
      <li>Multi-GPU DDP</li>
    </ul>
  </div>
  <div class="tier-card">
    <div class="tier-name">Enterprise</div>
    <div class="tier-price" style="font-size:1.2rem">Custom</div>
    <div class="tier-sub">Unlimited robots</div>
    <ul class="tier-features">
      <li>On-prem / VPC deploy</li>
      <li>Custom SLA &amp; support</li>
      <li>White-label option</li>
      <li>Data sovereignty</li>
      <li>Custom integrations</li>
    </ul>
  </div>
</div>

<h2>WTP Distribution (Survey N=240)</h2>
<div class="chart-box">
SVG_WTP
</div>

<h2>OCI vs AWS Tier Comparison</h2>
<div class="chart-box">
SVG_COMPARE
</div>

<h2>Competitor Pricing Analysis</h2>
<div class="chart-box">
<table>
  <thead><tr><th>Provider</th><th>Entry Tier</th><th>Growth Equiv.</th><th>Scale Equiv.</th><th>OCI Advantage</th></tr></thead>
  <tbody>
    <tr><td>OCI Robot Cloud</td><td>$990</td><td>$2,490</td><td>$5,990</td><td>&mdash;</td></tr>
    <tr><td>AWS RoboMaker</td><td>$1,400</td><td>$3,600</td><td>$8,700</td><td><span class="badge badge-green">−31% Growth</span></td></tr>
    <tr><td>Azure Percept</td><td>$1,250</td><td>$3,100</td><td>$7,400</td><td><span class="badge badge-green">−20% Growth</span></td></tr>
    <tr><td>GCP Robotics</td><td>$1,180</td><td>$2,950</td><td>$7,100</td><td><span class="badge badge-green">−16% Growth</span></td></tr>
    <tr><td>NVIDIA Fleet Cmd</td><td>$2,000</td><td>$4,800</td><td>N/A</td><td><span class="badge badge-green">−48% Entry</span></td></tr>
  </tbody>
</table>
</div>

</body>
</html>
"""


def _build_wtp_svg() -> str:
    """SVG histogram of WTP distribution with median marker."""
    W, H = 700, 220
    pad = {"l": 55, "r": 20, "t": 25, "b": 40}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]

    # Bins: (label, count) — roughly log-normal centred at $3200
    bins = [
        ("<$500", 8), ("$500-1k", 18), ("$1k-2k", 34),
        ("$2k-3k", 46), ("$3k-4k", 52), ("$4k-5k", 38),
        ("$5k-7k", 24), ("$7k-10k", 13), (">$10k", 7),
    ]
    max_count = max(c for _, c in bins)
    n = len(bins)
    bar_w = iw / n * 0.75

    def bx(i):
        return pad["l"] + (i + 0.5) * iw / n - bar_w / 2

    def by(count):
        return pad["t"] + ih * (1 - count / max_count)

    def bh(count):
        return ih * count / max_count

    grid = ""
    for cnt in [0, 20, 40, 60]:
        y = by(cnt)
        grid += f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{pad["l"]+iw}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        grid += f'<text x="{pad["l"]-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{cnt}</text>'

    bars = ""
    for i, (label, cnt) in enumerate(bins):
        x = bx(i)
        y = by(cnt)
        h = bh(cnt)
        color = "#C74634" if label in ("$3k-4k",) else "#3b82f6"
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>'
        bars += f'<text x="{x+bar_w/2:.1f}" y="{H-8}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'
        bars += f'<text x="{x+bar_w/2:.1f}" y="{y-3:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{cnt}</text>'

    # Median marker at $3200 (~mid of $3k-4k bin, index 4)
    med_x = pad["l"] + 4.5 * iw / n
    median_line = (
        f'<line x1="{med_x:.1f}" y1="{pad["t"]}" x2="{med_x:.1f}" y2="{pad["t"]+ih}"'
        f' stroke="#facc15" stroke-width="1.5" stroke-dasharray="4,3"/>'
        f'<text x="{med_x+4:.1f}" y="{pad["t"]+14}" fill="#facc15" font-size="10">Median $3,200</text>'
    )

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'{grid}{bars}{median_line}'
        f'<text x="{pad["l"]-35}" y="{pad["t"]+ih//2}" fill="#64748b" font-size="10" '
        f'transform="rotate(-90,{pad["l"]-35},{pad["t"]+ih//2})">Respondents</text>'
        f'</svg>'
    )
    return svg


def _build_compare_svg() -> str:
    """SVG grouped bar chart: OCI vs AWS pricing per tier."""
    W, H = 700, 220
    pad = {"l": 60, "r": 20, "t": 25, "b": 40}
    iw = W - pad["l"] - pad["r"]
    ih = H - pad["t"] - pad["b"]

    tiers = ["Starter", "Growth", "Scale"]
    oci   = [990, 2490, 5990]
    aws   = [1400, 3600, 8700]
    price_max = 9500
    n = len(tiers)
    group_w = iw / n
    bar_w = group_w * 0.3

    def px(i, j):  # j=0 OCI, j=1 AWS
        return pad["l"] + i * group_w + group_w * 0.15 + j * (bar_w + 4)

    def py(price):
        return pad["t"] + ih * (1 - price / price_max)

    def ph(price):
        return ih * price / price_max

    grid = ""
    for price in [0, 2000, 4000, 6000, 8000]:
        y = py(price)
        grid += f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{pad["l"]+iw}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        label = f"${price//1000}k" if price > 0 else "$0"
        grid += f'<text x="{pad["l"]-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>'

    bars = ""
    for i, tier in enumerate(tiers):
        # OCI bar
        x0 = px(i, 0)
        y0 = py(oci[i])
        h0 = ph(oci[i])
        bars += f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{h0:.1f}" fill="#C74634" rx="2"/>'
        bars += f'<text x="{x0+bar_w/2:.1f}" y="{y0-3:.1f}" fill="#fca5a5" font-size="9" text-anchor="middle">${oci[i]:,}</text>'
        # AWS bar
        x1 = px(i, 1)
        y1 = py(aws[i])
        h1 = ph(aws[i])
        bars += f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{bar_w:.1f}" height="{h1:.1f}" fill="#6b7280" rx="2"/>'
        bars += f'<text x="{x1+bar_w/2:.1f}" y="{y1-3:.1f}" fill="#d1d5db" font-size="9" text-anchor="middle">${aws[i]:,}</text>'
        # tier label
        cx = pad["l"] + i * group_w + group_w / 2
        bars += f'<text x="{cx:.1f}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">{tier}</text>'

    legend = (
        f'<rect x="{W-130}" y="{pad["t"]+4}" width="12" height="12" fill="#C74634"/>'
        f'<text x="{W-114}" y="{pad["t"]+14}" fill="#e2e8f0" font-size="11">OCI</text>'
        f'<rect x="{W-75}" y="{pad["t"]+4}" width="12" height="12" fill="#6b7280"/>'
        f'<text x="{W-59}" y="{pad["t"]+14}" fill="#e2e8f0" font-size="11">AWS</text>'
    )

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'{grid}{bars}{legend}'
        f'</svg>'
    )
    return svg


DASHBOARD_HTML = (
    HTML
    .replace("SVG_WTP", _build_wtp_svg())
    .replace("SVG_COMPARE", _build_compare_svg())
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Pricing Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return DASHBOARD_HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "pricing_optimizer", "port": 8911}

    @app.get("/api/tiers")
    def tiers():
        return {
            "tiers": [
                {"name": "Starter",    "price": 990,  "robots": 5,   "calls_per_day": 5000},
                {"name": "Growth",     "price": 2490, "robots": 25,  "calls_per_day": 50000},
                {"name": "Scale",      "price": 5990, "robots": 100, "calls_per_day": -1},
                {"name": "Enterprise", "price": None, "robots": -1,  "calls_per_day": -1},
            ]
        }

    @app.get("/api/wtp")
    def wtp():
        return {
            "median_wtp": 3200,
            "mean_wtp": 3580,
            "elasticity": -0.31,
            "survey_n": 240,
            "oci_vs_aws_growth_pct": -31,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8911)
    else:
        print("FastAPI not available — starting stdlib HTTPServer on port 8911")
        HTTPServer(("0.0.0.0", 8911), Handler).serve_forever()
