"""customer_roi_calculator.py — OCI Robot Cloud ROI Calculator (port 8218)

FastAPI service that calculates and visualizes ROI for robotics AI customers
considering OCI Robot Cloud vs. alternative deployment options.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

import math
import random
import json
from datetime import datetime

# ── Mock data ────────────────────────────────────────────────────────────────

ROI_DATA = {
    "payback_period_months": 18,
    "npv_3yr": 287_000,
    "tco_delta": -348_000,  # savings vs DGX baseline
    "break_even_vs_dgx_months": 18,
    "break_even_vs_aws_months": 9,
}

# 3-year monthly cost data (cumulative, USD)
MONTHS = list(range(0, 37))  # 0..36

def _cumulative_costs():
    """Return cumulative cost series for 4 deployment options."""
    oci, aws, dgx, self_built = [], [], [], []
    for m in MONTHS:
        # OCI Robot Cloud: $52k setup + $8k/mo
        oci.append(52_000 + 8_000 * m)
        # AWS Equivalent: $5k setup + $14k/mo
        aws.append(5_000 + 14_000 * m)
        # On-prem DGX: $400k upfront + $2k/mo
        dgx.append(400_000 + 2_000 * m)
        # Self-built: $120k setup + $11k/mo
        self_built.append(120_000 + 11_000 * m)
    return oci, aws, dgx, self_built

WATERFALL_COMPONENTS = [
    {"label": "Labor Savings",         "value":  210_000, "type": "gain"},
    {"label": "Time-to-Market",        "value":  85_000,  "type": "gain"},
    {"label": "Success Rate +12pp",    "value":  64_000,  "type": "gain"},
    {"label": "GPU Cost Savings",      "value":  76_000,  "type": "gain"},
    {"label": "Integration Cost",     "value": -48_000,  "type": "cost"},
    {"label": "Training & Ops",       "value": -24_000,  "type": "cost"},
    {"label": "OCI Subscription",     "value": -76_000,  "type": "cost"},
]

# ── SVG generators ────────────────────────────────────────────────────────────

def _svg_cost_comparison() -> str:
    """SVG line chart: 3-year cumulative cost comparison."""
    W, H = 760, 340
    PAD_L, PAD_R, PAD_T, PAD_B = 80, 30, 30, 50

    oci, aws, dgx, self_built = _cumulative_costs()

    all_vals = oci + aws + dgx + self_built
    max_v = max(all_vals)
    min_v = 0

    def sx(m):
        return PAD_L + (m / 36) * (W - PAD_L - PAD_R)

    def sy(v):
        return PAD_T + (1 - (v - min_v) / (max_v - min_v)) * (H - PAD_T - PAD_B)

    def polyline(series, color, dash=""):
        pts = " ".join(f"{sx(m):.1f},{sy(v):.1f}" for m, v in zip(MONTHS, series))
        da = f'stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" {da}/>'

    # y-axis labels
    y_labels = ""
    for tick in [0, 100_000, 200_000, 300_000, 400_000, 500_000]:
        if tick > max_v:
            break
        yy = sy(tick)
        label = f"${tick//1000}k"
        y_labels += f'<text x="{PAD_L-8}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="#94a3b8">{label}</text>'
        y_labels += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>'

    # x-axis labels
    x_labels = ""
    for m in [0, 6, 12, 18, 24, 30, 36]:
        xx = sx(m)
        x_labels += f'<text x="{xx:.1f}" y="{H-PAD_B+18}" text-anchor="middle" font-size="11" fill="#94a3b8">M{m}</text>'

    # break-even annotations
    be_oci_aws = 9
    be_oci_dgx = 18
    annots = ""
    for mo, label in [(be_oci_aws, "BE vs AWS"), (be_oci_dgx, "BE vs DGX")]:
        xx = sx(mo)
        annots += f'<line x1="{xx:.1f}" y1="{PAD_T}" x2="{xx:.1f}" y2="{H-PAD_B}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
        annots += f'<text x="{xx+4:.1f}" y="{PAD_T+14}" font-size="10" fill="#f59e0b">{label}</text>'

    legend = (
        f'<rect x="{PAD_L}" y="{H-18}" width="12" height="4" fill="#38bdf8"/>'
        f'<text x="{PAD_L+16}" y="{H-14}" font-size="11" fill="#cbd5e1">OCI Robot Cloud</text>'
        f'<rect x="{PAD_L+140}" y="{H-18}" width="12" height="4" fill="#f97316"/>'
        f'<text x="{PAD_L+156}" y="{H-14}" font-size="11" fill="#cbd5e1">AWS Equivalent</text>'
        f'<rect x="{PAD_L+275}" y="{H-18}" width="12" height="4" fill="#a78bfa"/>'
        f'<text x="{PAD_L+291}" y="{H-14}" font-size="11" fill="#cbd5e1">On-prem DGX</text>'
        f'<rect x="{PAD_L+395}" y="{H-18}" width="12" height="4" fill="#34d399"/>'
        f'<text x="{PAD_L+411}" y="{H-14}" font-size="11" fill="#cbd5e1">Self-built</text>'
    )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  <text x="{W//2}" y="20" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">3-Year Cumulative Cost Comparison</text>
  {y_labels}
  {x_labels}
  {annots}
  {polyline(oci, '#38bdf8')}
  {polyline(aws, '#f97316', '6,4')}
  {polyline(dgx, '#a78bfa', '2,4')}
  {polyline(self_built, '#34d399', '8,3')}
  {legend}
</svg>"""
    return svg


def _svg_roi_waterfall() -> str:
    """SVG waterfall chart: ROI value components."""
    W, H = 760, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 20, 40, 60

    items = WATERFALL_COMPONENTS
    n = len(items)
    bar_w = int((W - PAD_L - PAD_R) / (n + 1) * 0.7)
    gap = (W - PAD_L - PAD_R) / (n + 1)

    # compute running totals for waterfall
    running = 0
    bars = []
    for item in items:
        start = running if item["value"] > 0 else running + item["value"]
        bars.append({**item, "start": start, "abs": abs(item["value"])})
        running += item["value"]
    net = running

    all_vals = [b["start"] + b["abs"] for b in bars] + [0, net]
    max_v = max(all_vals) * 1.1
    min_v = min(0, net) * 1.1

    def sx(i):
        return PAD_L + gap * (i + 0.5) - bar_w / 2

    def sy(v):
        span = max_v - min_v
        return PAD_T + (1 - (v - min_v) / span) * (H - PAD_T - PAD_B)

    def bar_h(v):
        span = max_v - min_v
        return v / span * (H - PAD_T - PAD_B)

    rects = ""
    labels = ""
    for i, b in enumerate(bars):
        color = "#38bdf8" if b["type"] == "gain" else "#C74634"
        bx = sx(i)
        by = sy(b["start"] + b["abs"])
        bh = bar_h(b["abs"])
        rects += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{color}" rx="3" opacity="0.9"/>'
        sign = "+" if b["value"] > 0 else ""
        val_label = f"{sign}${abs(b['value'])//1000}k"
        lx = bx + bar_w / 2
        ly = by - 5 if b["value"] > 0 else by + bh + 14
        rects += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="10" fill="#f1f5f9">{val_label}</text>'
        # x label
        lbl_y = H - PAD_B + 14
        for j, word in enumerate(b["label"].split()):
            labels += f'<text x="{lx:.1f}" y="{lbl_y + j*13}" text-anchor="middle" font-size="10" fill="#94a3b8">{word}</text>'

    # net ROI bar
    net_i = n
    bx = sx(net_i)
    by = sy(max(0, net))
    bh = bar_h(abs(net))
    rects += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" fill="#22c55e" rx="3" opacity="0.95"/>'
    lx = bx + bar_w / 2
    rects += f'<text x="{lx:.1f}" y="{by-6:.1f}" text-anchor="middle" font-size="11" font-weight="bold" fill="#22c55e">Net ${net//1000}k</text>'
    labels += f'<text x="{lx:.1f}" y="{H-PAD_B+14}" text-anchor="middle" font-size="10" fill="#94a3b8">Net</text>'
    labels += f'<text x="{lx:.1f}" y="{H-PAD_B+27}" text-anchor="middle" font-size="10" fill="#94a3b8">ROI</text>'

    # zero line
    zero_y = sy(0)
    zero_line = f'<line x1="{PAD_L}" y1="{zero_y:.1f}" x2="{W-PAD_R}" y2="{zero_y:.1f}" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>'

    # y-axis
    y_labels = ""
    for tick in [-100_000, 0, 100_000, 200_000, 300_000, 400_000]:
        if tick < min_v or tick > max_v:
            continue
        yy = sy(tick)
        label = f"${tick//1000}k" if tick >= 0 else f"-${abs(tick)//1000}k"
        y_labels += f'<text x="{PAD_L-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8">{label}</text>'

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  <text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">ROI Waterfall — 3-Year Value Components</text>
  {zero_line}
  {y_labels}
  {rects}
  {labels}
</svg>"""
    return svg


# ── HTML dashboard ────────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Customer ROI Calculator</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 1.6rem; margin-bottom: 6px; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
  .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 22px; min-width: 180px; }}
  .kpi-label {{ color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; }}
  .kpi-value {{ color: #38bdf8; font-size: 1.9rem; font-weight: 700; margin-top: 4px; }}
  .kpi-value.red {{ color: #C74634; }}
  .kpi-value.green {{ color: #22c55e; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
  .card h2 {{ font-size: 1rem; color: #94a3b8; margin-bottom: 16px; text-transform: uppercase; letter-spacing: .05em; }}
  .footer {{ color: #475569; font-size: 0.75rem; margin-top: 20px; }}
  .oracle-bar {{ height: 4px; background: linear-gradient(90deg, #C74634, #38bdf8); border-radius: 2px; margin-bottom: 22px; }}
</style>
</head>
<body>
<div class="oracle-bar"></div>
<h1>OCI Robot Cloud — Customer ROI Calculator</h1>
<p class="subtitle">3-year total cost of ownership &amp; return on investment analysis · Port 8218</p>

<div class="kpi-row">
  <div class="kpi">
    <div class="kpi-label">Payback Period</div>
    <div class="kpi-value">{payback_period} mo</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">3-Year NPV</div>
    <div class="kpi-value green">${npv_3yr:,}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">TCO Delta vs DGX</div>
    <div class="kpi-value green">-${tco_savings:,}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">OCI Year-1 Cost</div>
    <div class="kpi-value">$52k</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">BE vs DGX</div>
    <div class="kpi-value">M18</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">BE vs AWS</div>
    <div class="kpi-value">M9</div>
  </div>
</div>

<div class="card">
  <h2>3-Year Cumulative Cost Comparison</h2>
  {chart_cost}
</div>

<div class="card">
  <h2>ROI Waterfall — Value Components</h2>
  {chart_waterfall}
</div>

<div class="footer">OCI Robot Cloud · Customer ROI Calculator · {ts} · Data based on representative customer profiles</div>
</body>
</html>
"""


def build_html() -> str:
    return DASHBOARD_HTML.format(
        payback_period=ROI_DATA["payback_period_months"],
        npv_3yr=ROI_DATA["npv_3yr"],
        tco_savings=abs(ROI_DATA["tco_delta"]),
        chart_cost=_svg_cost_comparison(),
        chart_waterfall=_svg_roi_waterfall(),
        ts=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


# ── FastAPI app (with stdlib fallback) ───────────────────────────────────────

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Customer ROI Calculator",
        description="OCI Robot Cloud ROI vs. alternatives — port 8218",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/roi")
    async def roi_data():
        return {
            "roi_data": ROI_DATA,
            "waterfall": WATERFALL_COMPONENTS,
            "cost_series": {
                "months": MONTHS,
                "oci": _cumulative_costs()[0],
                "aws": _cumulative_costs()[1],
                "dgx": _cumulative_costs()[2],
                "self_built": _cumulative_costs()[3],
            },
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "customer_roi_calculator", "port": 8218}

else:
    # stdlib fallback
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
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
    if FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8218)
    else:
        with socketserver.TCPServer(("", 8218), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8218 (stdlib fallback)")
            httpd.serve_forever()
