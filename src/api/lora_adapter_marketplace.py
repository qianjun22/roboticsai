import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

SERVICE_TITLE = "LoRA Adapter Marketplace"
PORT = 8964

ADAPTERS = [
    {"id": 1, "name": "UR5e Precision Lift", "robot": "UR5e", "task": "Pick & Place", "sr_lift": "+7pp", "price": 990, "status": "available", "downloads": 142},
    {"id": 2, "name": "Franka Assembly Expert", "robot": "Franka Panda", "task": "Assembly", "sr_lift": "+9pp", "price": 1290, "status": "available", "downloads": 98},
    {"id": 3, "name": "Spot Inspection Pro", "robot": "Boston Dynamics Spot", "task": "Visual Inspection", "sr_lift": "+5pp", "price": 1490, "status": "available", "downloads": 67},
    {"id": 4, "name": "UR10 Welding Assist", "robot": "UR10", "task": "Welding", "sr_lift": "+6pp", "price": 890, "status": "available", "downloads": 54},
    {"id": 5, "name": "Kuka Palletizer", "robot": "KUKA KR 6", "task": "Palletizing", "sr_lift": "+8pp", "price": 790, "status": "available", "downloads": 113},
    {"id": 6, "name": "ABB Paint Optimizer", "robot": "ABB IRB 1200", "task": "Spray Painting", "sr_lift": "+4pp", "price": 490, "status": "available", "downloads": 89},
    {"id": 7, "name": "Doosan Bin Picking", "robot": "Doosan M0609", "task": "Bin Picking", "sr_lift": "+11pp", "price": 1390, "status": "coming_soon", "downloads": 0},
    {"id": 8, "name": "Yaskawa Arc Welder", "robot": "Yaskawa HC10", "task": "Arc Welding", "sr_lift": "+7pp", "price": 990, "status": "coming_soon", "downloads": 0},
    {"id": 9, "name": "Fanuc Screw Driver", "robot": "FANUC CRX-10iA", "task": "Screwdriving", "sr_lift": "+6pp", "price": 690, "status": "coming_soon", "downloads": 0},
    {"id": 10, "name": "UR3 Electronics", "robot": "UR3e", "task": "Electronics Assembly", "sr_lift": "+10pp", "price": 1190, "status": "coming_soon", "downloads": 0},
    {"id": 11, "name": "Sawyer Lab Automation", "robot": "Rethink Sawyer", "task": "Lab Pipetting", "sr_lift": "+8pp", "price": 890, "status": "coming_soon", "downloads": 0},
    {"id": 12, "name": "Stretch Warehouse Nav", "robot": "Hello Robot Stretch", "task": "Warehouse Navigation", "sr_lift": "+5pp", "price": 590, "status": "coming_soon", "downloads": 0},
]

LAUNCH_DATE = "May 15, 2026"
LAUNCH_ADAPTERS = 6
TOTAL_ADAPTERS = 12
ANNUAL_REVENUE = 29400


def build_revenue_svg():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # Revenue ramp starting May (index 4)
    revenue = [0, 0, 0, 0, 2450, 3675, 4900, 5390, 5880, 6370, 6860, 7350]
    w, h = 560, 200
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    max_rev = max(revenue) if max(revenue) > 0 else 1

    bars = ""
    bar_w = chart_w / len(months) * 0.6
    for i, (m, rv) in enumerate(zip(months, revenue)):
        bh = (rv / max_rev) * chart_h
        x = pad_l + i * (chart_w / len(months)) + (chart_w / len(months) - bar_w) / 2
        y = pad_t + chart_h - bh
        color = "#C74634" if rv > 0 else "#1e293b"
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>'
        label = f"${rv//1000}k" if rv >= 1000 else (f"${rv}" if rv > 0 else "")
        if label:
            bars += f'<text x="{x + bar_w/2:.1f}" y="{y - 4:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{label}</text>'
        bars += f'<text x="{x + bar_w/2:.1f}" y="{pad_t + chart_h + 14:.1f}" fill="#64748b" font-size="8" text-anchor="middle">{m}</text>'

    svg = f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>
  <text x="{w//2}" y="14" fill="#94a3b8" font-size="10" text-anchor="middle">2026 Monthly Revenue ($)</text>
  {bars}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>
  <line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>
</svg>'''
    return svg


def build_html():
    available = [a for a in ADAPTERS if a["status"] == "available"]
    coming_soon = [a for a in ADAPTERS if a["status"] == "coming_soon"]
    total_downloads = sum(a["downloads"] for a in ADAPTERS)
    avg_price = sum(a["price"] for a in ADAPTERS) / len(ADAPTERS)
    revenue_svg = build_revenue_svg()

    adapter_rows = ""
    for a in available:
        stars = "".join(["&#9733;" for _ in range(min(5, max(3, int(a["sr_lift"].replace("+","").replace("pp","")) // 2 + 2)))])
        adapter_rows += f'''
        <div style="background:#1e293b;border-radius:10px;padding:16px;border-left:4px solid #C74634;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <div style="color:#f1f5f9;font-weight:700;font-size:15px;">{a["name"]}</div>
              <div style="color:#64748b;font-size:12px;margin-top:2px;">{a["robot"]} &bull; {a["task"]}</div>
            </div>
            <div style="text-align:right;">
              <div style="color:#C74634;font-size:20px;font-weight:800;">${a["price"]}<span style="font-size:11px;color:#64748b;">/yr</span></div>
              <div style="color:#4ade80;font-size:12px;font-weight:600;">SR Lift {a["sr_lift"]}</div>
            </div>
          </div>
          <div style="margin-top:10px;display:flex;gap:16px;">
            <span style="color:#fbbf24;font-size:12px;">{stars}</span>
            <span style="color:#64748b;font-size:11px;">&#8595; {a["downloads"]} downloads</span>
            <span style="background:#0f172a;color:#38bdf8;padding:2px 8px;border-radius:12px;font-size:11px;">NVIDIA NGC Listed</span>
          </div>
        </div>'''

    coming_rows = ""
    for a in coming_soon:
        coming_rows += f'''
        <div style="background:#1e293b;border-radius:10px;padding:14px;border-left:4px solid #334155;opacity:0.7;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="color:#94a3b8;font-weight:600;font-size:14px;">{a["name"]}</div>
              <div style="color:#475569;font-size:11px;">{a["robot"]} &bull; {a["task"]}</div>
            </div>
            <div style="text-align:right;">
              <div style="color:#475569;font-size:16px;font-weight:700;">${a["price"]}<span style="font-size:10px;">/yr</span></div>
              <span style="background:#1e3a4a;color:#38bdf8;padding:2px 8px;border-radius:12px;font-size:10px;">Coming Soon</span>
            </div>
          </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SERVICE_TITLE} — Port {PORT}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 1px solid #334155; padding: 24px 32px; }}
  .badge {{ display: inline-block; background: #C74634; color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-bottom: 8px; }}
  h1 {{ font-size: 28px; color: #C74634; font-weight: 800; }}
  .subtitle {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px; border-top: 3px solid #C74634; }}
  .kpi-value {{ font-size: 26px; font-weight: 800; color: #f1f5f9; }}
  .kpi-label {{ color: #64748b; font-size: 12px; margin-top: 4px; }}
  .section-title {{ color: #38bdf8; font-size: 16px; font-weight: 700; margin-bottom: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
  .adapters-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .coming-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .launch-banner {{ background: linear-gradient(90deg, #1e293b 0%, #1a2640 100%); border: 1px solid #C74634; border-radius: 12px; padding: 18px 24px; margin-bottom: 28px; display: flex; align-items: center; gap: 24px; }}
  .launch-date {{ color: #C74634; font-size: 22px; font-weight: 800; }}
  .launch-desc {{ color: #94a3b8; font-size: 13px; }}
  .footer {{ text-align: center; color: #334155; font-size: 11px; padding: 20px; border-top: 1px solid #1e293b; margin-top: 20px; }}
  @media (max-width: 700px) {{ .kpi-grid {{ grid-template-columns: repeat(2,1fr); }} .grid2 {{ grid-template-columns: 1fr; }} .adapters-grid {{ grid-template-columns: 1fr; }} .coming-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
  <span class="badge">Port {PORT}</span>
  <h1>{SERVICE_TITLE}</h1>
  <div class="subtitle">12 pre-trained robot policy adapters &bull; NVIDIA NGC Catalog &bull; Passive Revenue Engine</div>
</div>
<div class="container">
  <div class="launch-banner">
    <div>
      <div style="color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;">Launch Date</div>
      <div class="launch-date">{LAUNCH_DATE}</div>
    </div>
    <div style="width:1px;height:40px;background:#334155;"></div>
    <div>
      <div style="color:#f1f5f9;font-weight:700;font-size:15px;">Phase 1: {LAUNCH_ADAPTERS} Adapters Available at Launch</div>
      <div class="launch-desc">{TOTAL_ADAPTERS - LAUNCH_ADAPTERS} additional adapters releasing Q3 2026 &bull; Annual subscription model &bull; NGC co-marketing</div>
    </div>
    <div style="margin-left:auto;text-align:center;">
      <div style="color:#4ade80;font-size:22px;font-weight:800;">${ANNUAL_REVENUE:,}</div>
      <div style="color:#64748b;font-size:11px;">Est. Year 1 ARR</div>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-value">{TOTAL_ADAPTERS}</div><div class="kpi-label">Total Adapters</div></div>
    <div class="kpi"><div class="kpi-value">${avg_price:,.0f}</div><div class="kpi-label">Avg Price / Adapter / Year</div></div>
    <div class="kpi"><div class="kpi-value">{total_downloads}</div><div class="kpi-label">Total Downloads</div></div>
    <div class="kpi"><div class="kpi-value">+7pp</div><div class="kpi-label">Avg SR Lift (UR5e)</div></div>
  </div>

  <div class="grid2">
    <div class="card">
      <div class="section-title">Revenue Forecast 2026</div>
      {revenue_svg}
      <div style="display:flex;gap:20px;margin-top:12px;">
        <div style="text-align:center;"><div style="color:#C74634;font-weight:700;">$29,400</div><div style="color:#64748b;font-size:11px;">Est. ARR</div></div>
        <div style="text-align:center;"><div style="color:#38bdf8;font-weight:700;">$2,450</div><div style="color:#64748b;font-size:11px;">Month 1 (May)</div></div>
        <div style="text-align:center;"><div style="color:#4ade80;font-weight:700;">$7,350</div><div style="color:#64748b;font-size:11px;">Month 12 Run Rate</div></div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Revenue Model</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead><tr style="color:#64748b;border-bottom:1px solid #334155;">
          <th style="text-align:left;padding:6px 0;">Tier</th>
          <th style="text-align:right;padding:6px 0;">Price</th>
          <th style="text-align:right;padding:6px 0;">SR Lift</th>
        </tr></thead>
        <tbody>
          <tr style="border-bottom:1px solid #1e3a5f;"><td style="padding:8px 0;color:#94a3b8;">Entry (6 adapters)</td><td style="text-align:right;color:#C74634;font-weight:700;">$490–$790</td><td style="text-align:right;color:#4ade80;">+4–8pp</td></tr>
          <tr style="border-bottom:1px solid #1e3a5f;"><td style="padding:8px 0;color:#94a3b8;">Pro (4 adapters)</td><td style="text-align:right;color:#C74634;font-weight:700;">$890–$1,190</td><td style="text-align:right;color:#4ade80;">+6–10pp</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Enterprise (2 adapters)</td><td style="text-align:right;color:#C74634;font-weight:700;">$1,290–$1,490</td><td style="text-align:right;color:#4ade80;">+9–11pp</td></tr>
        </tbody>
      </table>
      <div style="margin-top:16px;background:#0f172a;border-radius:8px;padding:12px;">
        <div style="color:#38bdf8;font-size:12px;font-weight:700;margin-bottom:8px;">NVIDIA NGC Partnership</div>
        <div style="color:#64748b;font-size:12px;line-height:1.6;">Listed in NGC catalog under &ldquo;Robot Policy Adapters&rdquo; &bull; Co-marketing with NVIDIA GR00T team &bull; Featured at GTC 2026 booth</div>
      </div>
    </div>
  </div>

  <div style="margin-bottom:28px;">
    <div class="section-title">Available at Launch — {LAUNCH_ADAPTERS} Adapters</div>
    <div class="adapters-grid">
      {adapter_rows}
    </div>
  </div>

  <div>
    <div class="section-title">Coming Q3 2026 — {TOTAL_ADAPTERS - LAUNCH_ADAPTERS} More Adapters</div>
    <div class="coming-grid">
      {coming_rows}
    </div>
  </div>
</div>
<div class="footer">OCI Robot Cloud &bull; {SERVICE_TITLE} &bull; Port {PORT} &bull; {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}</div>
</body>
</html>'''
    return html


if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT}

    @app.get("/adapters")
    def list_adapters():
        return {"adapters": ADAPTERS, "total": len(ADAPTERS), "available": len([a for a in ADAPTERS if a["status"] == "available"])}

    @app.get("/revenue")
    def revenue():
        return {"annual_revenue_est": ANNUAL_REVENUE, "launch_date": LAUNCH_DATE, "launch_adapters": LAUNCH_ADAPTERS}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *a): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        srv = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{SERVICE_TITLE} running on port {PORT} (stdlib fallback)")
        srv.serve_forever()
