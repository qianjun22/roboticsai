"""Investor Update Dashboard — FastAPI port 8777"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8777

def build_html():
    random.seed(2026)

    # --- KPI Data ---
    arr = 1_420_000          # Annual Recurring Revenue
    arr_growth = 34.7        # % QoQ
    design_partners = 12
    pilot_robots = 47
    nps = 68
    burn_multiple = 1.4
    runway_months = 22
    gross_margin = 71.3

    # --- Revenue trend (12 months, compound growth) ---
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    base = 65_000
    rev = [int(base * (1.08 ** i) + random.uniform(-3000, 3000)) for i in range(12)]

    svg_w, svg_h = 540, 140
    rev_max = max(rev)
    def rx(i): return int(30 + (svg_w - 40) * i / (len(rev) - 1))
    def ry(v): return int(svg_h - 20 - v / (rev_max * 1.05) * (svg_h - 30))

    rev_line = " ".join(f"{rx(i)},{ry(v)}" for i, v in enumerate(rev))
    rev_area  = f"{rx(0)},{svg_h-20} " + rev_line + f" {rx(len(rev)-1)},{svg_h-20}"
    rev_dots  = "".join(
        f"<circle cx='{rx(i)}' cy='{ry(v)}' r='4' fill='#22c55e'/>"
        f"<text x='{rx(i)}' y='{ry(v)-8}' fill='#94a3b8' font-size='9' text-anchor='middle'>${v//1000}k</text>"
        for i, v in enumerate(rev)
    )
    month_labels = "".join(
        f"<text x='{rx(i)}' y='{svg_h-4}' fill='#64748b' font-size='9' text-anchor='middle'>{m}</text>"
        for i, m in enumerate(months)
    )

    # --- Burn / Runway waterfall (6-month forward) ---
    cash = 4_800_000
    monthly_burn = cash / runway_months
    wf_months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    wf_vals = [cash - monthly_burn * i + random.uniform(-40000, 60000) for i in range(6)]
    wf_max = max(wf_vals)
    bar_w = 64
    wf_bars = ""
    for i, (m, v) in enumerate(zip(wf_months, wf_vals)):
        bh = int(v / (wf_max * 1.05) * 100)
        color = "#22c55e" if v > wf_max * 0.5 else "#f59e0b" if v > wf_max * 0.25 else "#ef4444"
        x = 20 + i * (bar_w + 14)
        wf_bars += (
            f"<rect x='{x}' y='{120 - bh}' width='{bar_w}' height='{bh}' rx='4' fill='{color}' fill-opacity='0.8'/>"
            f"<text x='{x + bar_w//2}' y='{115 - bh}' fill='{color}' font-size='9' text-anchor='middle'>${v/1e6:.2f}M</text>"
            f"<text x='{x + bar_w//2}' y='134' fill='#64748b' font-size='9' text-anchor='middle'>{m}</text>"
        )

    # --- Customer pipeline funnel ---
    stages = [("Prospect", 84), ("Qualified", 41), ("Pilot", 19), ("Closed", 12)]
    funnel_html = ""
    stage_w = 480
    for i, (label, count) in enumerate(stages):
        w = int(stage_w * count / stages[0][1])
        color = ["#3b82f6", "#8b5cf6", "#f59e0b", "#22c55e"][i]
        offset = (stage_w - w) // 2
        funnel_html += (
            f"<g transform='translate({offset},0)'>"
            f"<rect width='{w}' height='28' rx='6' fill='{color}' fill-opacity='0.85'/>"
            f"<text x='{w//2}' y='18' fill='white' font-size='12' font-weight='600' text-anchor='middle'>{label} ({count})</text>"
            f"</g><g transform='translate(0,38)'>"
        )
    # close all open <g> tags from transform trick
    funnel_html += "</g>" * len(stages)

    # --- Use-case adoption (donut-style arc chart) ---
    use_cases = [
        ("Pick & Place", 38, "#38bdf8"),
        ("Assembly",     27, "#a78bfa"),
        ("Inspection",   18, "#22c55e"),
        ("Logistics",    12, "#f59e0b"),
        ("Other",         5, "#64748b"),
    ]
    total_uc = sum(u[1] for u in use_cases)
    dcx, dcy, dr_outer, dr_inner = 130, 130, 110, 65
    arc_paths = ""
    legend_items = ""
    angle = -math.pi / 2
    for label, val, color in use_cases:
        sweep = 2 * math.pi * val / total_uc
        x1 = dcx + dr_outer * math.cos(angle)
        y1 = dcy + dr_outer * math.sin(angle)
        x2 = dcx + dr_outer * math.cos(angle + sweep)
        y2 = dcy + dr_outer * math.sin(angle + sweep)
        xi1 = dcx + dr_inner * math.cos(angle + sweep)
        yi1 = dcy + dr_inner * math.sin(angle + sweep)
        xi2 = dcx + dr_inner * math.cos(angle)
        yi2 = dcy + dr_inner * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        arc_paths += (
            f"<path d='M {x1:.1f} {y1:.1f} A {dr_outer} {dr_outer} 0 {large} 1 {x2:.1f} {y2:.1f} "
            f"L {xi1:.1f} {yi1:.1f} A {dr_inner} {dr_inner} 0 {large} 0 {xi2:.1f} {yi2:.1f} Z' "
            f"fill='{color}' stroke='#0f172a' stroke-width='2'/>"
        )
        legend_items += (
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
            f"<div style='width:12px;height:12px;border-radius:2px;background:{color};flex-shrink:0'></div>"
            f"<span style='font-size:12px;color:#94a3b8'>{label} <strong style='color:#e2e8f0'>{val}%</strong></span>"
            f"</div>"
        )
        angle += sweep

    return f"""<!DOCTYPE html><html><head><title>Investor Update Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:24px 24px 0}}
h2{{color:#38bdf8;margin:0 0 14px}}
.card{{background:#1e293b;padding:20px;margin:14px;border-radius:10px;box-shadow:0 2px 12px #0004}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:0 14px 0}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.grid3{{display:grid;grid-template-columns:5fr 3fr 4fr;gap:0}}
.kpi{{background:#1e293b;border-radius:10px;padding:18px 14px;text-align:center}}
.kpi .val{{font-size:1.8rem;font-weight:700;color:#f8fafc}}
.kpi .lbl{{color:#64748b;font-size:12px;margin-top:4px}}
.kpi .delta{{color:#22c55e;font-size:12px;margin-top:2px}}
.badge{{display:inline-block;background:#0f172a;border:1px solid #C74634;color:#C74634;font-size:11px;border-radius:4px;padding:2px 8px;margin-left:8px}}
.tag{{display:inline-block;background:#0f2d1a;color:#22c55e;border-radius:4px;padding:2px 8px;font-size:11px;margin:2px}}
</style></head><body>
<h1>OCI Robot Cloud — Investor Update Q1 2026 <span class='badge'>port {PORT}</span></h1>

<div class='grid4'>
  <div class='kpi'>
    <div class='val'>${arr/1e6:.2f}M</div>
    <div class='lbl'>ARR</div>
    <div class='delta'>+{arr_growth}% QoQ</div>
  </div>
  <div class='kpi'>
    <div class='val'>{design_partners}</div>
    <div class='lbl'>Design Partners</div>
    <div class='delta'>+3 this quarter</div>
  </div>
  <div class='kpi'>
    <div class='val'>{pilot_robots}</div>
    <div class='lbl'>Robots in Pilots</div>
    <div class='delta'>+18 vs last qtr</div>
  </div>
  <div class='kpi'>
    <div class='val'>{gross_margin}%</div>
    <div class='lbl'>Gross Margin</div>
    <div class='delta'>+4.1pp YoY</div>
  </div>
</div>

<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:0 14px'>
  <div class='kpi'>
    <div class='val'>{nps}</div>
    <div class='lbl'>NPS</div>
    <div class='delta'>Industry avg 42</div>
  </div>
  <div class='kpi'>
    <div class='val'>{burn_multiple}x</div>
    <div class='lbl'>Burn Multiple</div>
    <div class='delta' style='color:#f59e0b'>Improving</div>
  </div>
  <div class='kpi'>
    <div class='val'>{runway_months}mo</div>
    <div class='lbl'>Runway</div>
    <div class='delta'>Series A in Q3</div>
  </div>
  <div class='kpi'>
    <div class='val'>99.94%</div>
    <div class='lbl'>Platform Uptime</div>
    <div class='delta'>SLA: 99.9%</div>
  </div>
</div>

<div class='grid2'>

<div class='card'>
  <h2>Monthly Revenue (MRR)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block'>
    <defs><linearGradient id='rev_grad' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='#22c55e' stop-opacity='0.3'/>
      <stop offset='100%' stop-color='#22c55e' stop-opacity='0'/>
    </linearGradient></defs>
    <polygon points='{rev_area}' fill='url(#rev_grad)'/>
    <polyline points='{rev_line}' fill='none' stroke='#22c55e' stroke-width='2.5'/>
    {rev_dots}
    {month_labels}
  </svg>
</div>

<div class='card'>
  <h2>Cash Runway Forecast</h2>
  <svg width='500' height='150' style='display:block'>
    {wf_bars}
    <line x1='0' y1='120' x2='500' y2='120' stroke='#334155' stroke-width='1'/>
  </svg>
</div>

</div>

<div class='grid3'>

<div class='card'>
  <h2>Sales Pipeline Funnel</h2>
  <svg width='480' height='170' style='display:block;margin:auto'>
    <g transform='translate(0,10)'>
      {funnel_html}
    </g>
  </svg>
</div>

<div class='card' style='display:flex;flex-direction:column;align-items:center'>
  <h2>Use-Case Adoption</h2>
  <div style='display:flex;align-items:center;gap:16px'>
    <svg width='260' height='260' style='display:block'>
      {arc_paths}
      <text x='{dcx}' y='{dcy+5}' fill='#e2e8f0' font-size='13' font-weight='600' text-anchor='middle'>Mix</text>
    </svg>
    <div>{legend_items}</div>
  </div>
</div>

<div class='card'>
  <h2>Key Milestones</h2>
  <div style='font-size:13px;line-height:2'>
    <span class='tag'>✓</span> GR00T N1.6 on OCI (227ms)<br/>
    <span class='tag'>✓</span> Multi-GPU DDP 3.07× throughput<br/>
    <span class='tag'>✓</span> DAgger pipeline end-to-end<br/>
    <span class='tag'>✓</span> pip SDK: oci-robot-cloud<br/>
    <span class='tag'>✓</span> CoRL paper draft submitted<br/>
    <span class='tag' style='background:#1a1a0f;color:#f59e0b'>→</span> Isaac Sim GA (Q2 2026)<br/>
    <span class='tag' style='background:#1a1a0f;color:#f59e0b'>→</span> Series A close (Q3 2026)<br/>
    <span class='tag' style='background:#1a1a0f;color:#f59e0b'>→</span> 5 production deployments<br/>
  </div>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Investor Update Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "investor_update_dashboard"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
