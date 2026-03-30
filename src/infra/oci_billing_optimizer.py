# OCI Billing Optimizer — port 8943
import math
import random
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HOST = "0.0.0.0"
PORT = 8943

SAVINGS_DATA = {
    "reserved_annual": 28800,
    "spot_savings_pct": 65,
    "spot_job_coverage": 67,
    "committed_monthly": 4200,
    "payg_monthly": 8900,
    "net_monthly_savings": 4700,
    "annual_savings": 56400,
    "breakeven_months": 3.2,
}

COMMITMENT_COVERAGE = [
    {"label": "Reserved (3yr A100×2)", "pct": 33, "color": "#38bdf8", "monthly": 2400},
    {"label": "Spot Instances (eval)", "pct": 44, "color": "#4ade80", "monthly": 1800},
    {"label": "On-Demand (burst)", "pct": 14, "color": "#f59e0b", "monthly": 1200},
    {"label": "PAYG Residual", "pct": 9, "color": "#f87171", "monthly": 760},
]

WATERFALL = [
    {"label": "PAYG Baseline", "value": 8900, "type": "base"},
    {"label": "Reserved Discount", "value": -2400, "type": "saving"},
    {"label": "Spot Coverage", "value": -1800, "type": "saving"},
    {"label": "Commit Credits", "value": -500, "type": "saving"},
    {"label": "Optimized Total", "value": 4200, "type": "result"},
]

MONTHLY_TREND = [8900, 8750, 8200, 7400, 6300, 5800, 5100, 4600, 4200]
TREND_LABELS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]


def build_donut_svg():
    cx, cy, r_outer, r_inner = 140, 150, 110, 60
    total = sum(c["pct"] for c in COMMITMENT_COVERAGE)
    start = -math.pi / 2
    slices = ""
    legend = ""
    for i, seg in enumerate(COMMITMENT_COVERAGE):
        sweep = 2 * math.pi * seg["pct"] / total
        x1 = cx + r_outer * math.cos(start)
        y1 = cy + r_outer * math.sin(start)
        end = start + sweep
        x2 = cx + r_outer * math.cos(end)
        y2 = cy + r_outer * math.sin(end)
        ix1 = cx + r_inner * math.cos(end)
        iy1 = cy + r_inner * math.sin(end)
        ix2 = cx + r_inner * math.cos(start)
        iy2 = cy + r_inner * math.sin(start)
        large = 1 if sweep > math.pi else 0
        path = (f"M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} "
                f"L {ix1:.1f} {iy1:.1f} A {r_inner} {r_inner} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z")
        slices += f'<path d="{path}" fill="{seg["color"]}" opacity="0.85"/>\n'
        legend += (f'<rect x="290" y="{30+i*32}" width="14" height="14" fill="{seg["color"]}" rx="2"/>'
                   f'<text x="310" y="{42+i*32}" fill="#cbd5e1" font-size="12">{seg["label"]} ({seg["pct"]}%)</text>'
                   f'<text x="310" y="{56+i*32}" fill="#64748b" font-size="11">${seg["monthly"]}/mo</text>')
        start = end
    center = (f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#38bdf8" font-size="22" font-weight="700">$4,200</text>'
              f'<text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#94a3b8" font-size="11">/mo committed</text>')
    return (f'<svg width="520" height="300" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="520" height="300" fill="#1e293b" rx="8"/>'
            f'{slices}{center}{legend}</svg>')


def build_waterfall_svg():
    width, height = 600, 280
    pad_l, pad_b = 60, 40
    chart_w = width - pad_l - 20
    chart_h = height - pad_b - 30
    bar_w = chart_w / (len(WATERFALL) * 1.6)
    max_val = 9500

    def y_for(v):
        return pad_b + chart_h * (1 - v / max_val)

    bars = ""
    running = 0
    for i, item in enumerate(WATERFALL):
        x = pad_l + i * (chart_w / len(WATERFALL)) + 10
        if item["type"] == "base":
            y = y_for(item["value"])
            h = chart_h - y + pad_b
            bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#475569" rx="3"/>'
            running = item["value"]
        elif item["type"] == "saving":
            top = running
            running += item["value"]
            y_top = y_for(top)
            y_bot = y_for(running)
            h = abs(y_bot - y_top)
            bars += f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#4ade80" rx="3"/>'
        else:
            y = y_for(item["value"])
            h = chart_h - y + pad_b
            bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#38bdf8" rx="3"/>'

        label_y = height - 10
        bars += f'<text x="{x+bar_w/2:.1f}" y="{label_y}" text-anchor="middle" fill="#94a3b8" font-size="10">{item["label"]}</text>'
        val_str = f'${abs(item["value"]):,}'
        if item["type"] == "saving":
            val_str = f'-${abs(item["value"]):,}'
        val_y = y_for(max(running, item["value"] if item["value"] > 0 else running)) - 5
        bars += f'<text x="{x+bar_w/2:.1f}" y="{val_y:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="600">{val_str}</text>'

    # y-axis
    axis = f'<line x1="{pad_l}" y1="{pad_b}" x2="{pad_l}" y2="{pad_b+chart_h}" stroke="#334155" stroke-width="1"/>'
    for v in [0, 2000, 4000, 6000, 8000]:
        y = y_for(v)
        axis += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-20}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        axis += f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#64748b" font-size="10">${v//1000}k</text>'

    return (f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{height}" fill="#1e293b" rx="8"/>'
            f'{axis}{bars}</svg>')


def build_trend_svg():
    width, height, pad = 560, 200, 40
    cw = width - 2 * pad
    ch = height - 2 * pad
    pts = []
    for i, v in enumerate(MONTHLY_TREND):
        x = pad + i * cw / (len(MONTHLY_TREND) - 1)
        y = pad + ch * (1 - (v - 3000) / 6500)
        pts.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_pts = f"{pad},{pad+ch} " + poly + f" {width-pad},{pad+ch}"
    labels = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{height-8}" text-anchor="middle" fill="#64748b" font-size="10">{TREND_LABELS[i]}</text>'
        for i in range(len(TREND_LABELS))
    )
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>'
        f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9">${MONTHLY_TREND[i]//100/10}k</text>'
        for i, (x, y) in enumerate(pts)
    )
    return (f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{height}" fill="#1e293b" rx="8"/>'
            f'<polygon points="{area_pts}" fill="#38bdf8" fill-opacity="0.1"/>'
            f'<polyline points="{poly}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
            f'{labels}{dots}</svg>')


HTML = f"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>OCI Billing Optimizer</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;text-align:center;padding:28px 0 4px;font-size:2rem;letter-spacing:1px}}
  h2{{color:#38bdf8;font-size:1.1rem;margin:28px 0 10px;padding-left:4px}}
  .wrap{{max-width:960px;margin:0 auto;padding:0 24px 48px}}
  .cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px 14px;text-align:center}}
  .card .val{{font-size:1.9rem;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:0.78rem;color:#94a3b8;margin-top:6px}}
  .card .sub{{font-size:0.72rem;color:#64748b;margin-top:2px}}
  .charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px}}
  .chart-box{{background:#1e293b;border-radius:10px;padding:16px}}
  .chart-box svg{{width:100%;height:auto}}
  .full{{grid-column:1/-1}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden}}
  th{{background:#0f172a;color:#38bdf8;padding:10px 12px;text-align:left;font-size:0.78rem;text-transform:uppercase}}
  td{{padding:9px 12px;font-size:0.82rem;border-top:1px solid #334155}}
  .green{{color:#4ade80}}.blue{{color:#38bdf8}}.yellow{{color:#f59e0b}}
  footer{{text-align:center;color:#475569;font-size:0.75rem;padding-top:24px}}
</style></head><body><div class="wrap">
  <h1>OCI Billing Optimizer</h1>
  <p style="text-align:center;color:#64748b;margin-bottom:24px">Reserved + spot strategy — $4,200/mo committed vs $8,900/mo PAYG ($56,400/yr savings)</p>
  <div class="cards">
    <div class="card"><div class="val">$28.8k</div><div class="lbl">Reserved Annual Savings</div><div class="sub">2×A100 3-year commitment</div></div>
    <div class="card"><div class="val">65%</div><div class="lbl">Spot Instance Discount</div><div class="sub">{SAVINGS_DATA['spot_job_coverage']}% of eval jobs on spot</div></div>
    <div class="card"><div class="val">$4,200</div><div class="lbl">Committed Monthly</div><div class="sub">vs $8,900/mo PAYG</div></div>
    <div class="card"><div class="val">$56.4k</div><div class="lbl">Annual Savings</div><div class="sub">Breakeven in {SAVINGS_DATA['breakeven_months']}mo</div></div>
  </div>
  <div class="charts">
    <div class="chart-box"><h2>Commitment Coverage</h2>{build_donut_svg()}</div>
    <div class="chart-box"><h2>Savings Waterfall (Monthly)</h2>{build_waterfall_svg()}</div>
    <div class="chart-box full"><h2>Monthly Spend Trend (9-Month Optimization Journey)</h2>{build_trend_svg()}</div>
  </div>
  <h2>Commitment Plan Details</h2>
  <table>
    <tr><th>Strategy</th><th>Coverage</th><th>Monthly Cost</th><th>Savings vs PAYG</th><th>Notes</th></tr>
    <tr><td>2×A100 Reserved (3yr)</td><td class="blue">33%</td><td class="blue">$2,400</td><td class="green">-$3,200</td><td>Baseline training workloads</td></tr>
    <tr><td>Spot for Eval Jobs</td><td class="blue">44% of eval</td><td class="blue">$1,800</td><td class="green">-$2,600</td><td>67% of eval on spot, 65% cheaper</td></tr>
    <tr><td>Commit Credits</td><td class="yellow">—</td><td class="yellow">—</td><td class="green">-$500</td><td>OCI commit credit tier 2</td></tr>
    <tr><td>On-Demand Burst</td><td class="yellow">14%</td><td class="yellow">$760</td><td>—</td><td>Overflow / urgent jobs only</td></tr>
    <tr><td><strong>Optimized Total</strong></td><td class="blue">100%</td><td class="blue"><strong>$4,200</strong></td><td class="green"><strong>-$4,700/mo</strong></td><td>52.8% cost reduction</td></tr>
  </table>
  <footer>OCI Robot Cloud &mdash; OCI Billing Optimizer &mdash; port {PORT}</footer>
</div></body></html>
"""


if USE_FASTAPI:
    app = FastAPI(title="OCI Billing Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "oci_billing_optimizer"}

    @app.get("/api/savings")
    def savings():
        return SAVINGS_DATA

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *a):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host=HOST, port=PORT)
    else:
        print(f"FastAPI unavailable — fallback HTTPServer on port {PORT}")
        HTTPServer((HOST, PORT), Handler).serve_forever()
