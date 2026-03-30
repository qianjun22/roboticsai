"""Revenue Velocity Tracker — FastAPI port 8819"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8819

def build_html():
    random.seed(7)

    # --- ARR & MRR simulation ---
    months = ["Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug"]
    n_months = len(months)
    base_mrr = 18_500
    mrr = [round(base_mrr * (1 + 0.07 * i + 0.03 * math.sin(i * 0.8)) + random.uniform(-400, 400)) for i in range(n_months)]
    arr = [m * 12 for m in mrr]
    current_mrr = mrr[-1]
    current_arr = arr[-1]
    mrr_growth = round((mrr[-1] - mrr[-2]) / mrr[-2] * 100, 1)

    # --- Revenue velocity by segment ---
    segments = ["Enterprise", "Mid-Market", "Startup", "Gov/Research"]
    seg_vel = [round(12000 + 8000 * math.sin(i * 1.1 + 0.5) * 0.5 + 8000 * 0.5 + random.uniform(-500, 500)) for i in range(len(segments))]
    seg_colors = ["#C74634", "#38bdf8", "#22c55e", "#f59e0b"]

    # --- MRR chart (line) ---
    cw, ch = 520, 110
    pad = 30
    x_scale = (cw - 2 * pad) / (n_months - 1)
    mrr_min, mrr_max = min(mrr) * 0.97, max(mrr) * 1.03
    y_scale = (ch - 2 * pad) / (mrr_max - mrr_min)
    mrr_pts = " ".join(f"{pad + i * x_scale:.1f},{ch - pad - (v - mrr_min) * y_scale:.1f}" for i, v in enumerate(mrr))
    month_labels = "".join(
        f'<text x="{pad + i * x_scale:.1f}" y="{ch - 4}" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )
    mrr_circles = "".join(
        f'<circle cx="{pad + i * x_scale:.1f}" cy="{ch - pad - (v - mrr_min) * y_scale:.1f}" r="3" fill="#38bdf8"/>'
        for i, v in enumerate(mrr)
    )

    # --- Win/Loss funnel ---
    funnel_stages = ["Qualified Leads", "Demos Booked", "POC Started", "Contracts Sent", "Closed Won"]
    funnel_vals = [320, 180, 90, 52, 34]
    funnel_max = funnel_vals[0]
    fw_max = 380
    funnel_svg = "".join(
        f'<g>'
        f'<rect x="{(fw_max - fw_max * v / funnel_max) / 2:.1f}" y="{idx * 26}" '
        f'width="{fw_max * v / funnel_max:.1f}" height="20" rx="3" fill="{seg_colors[min(idx, len(seg_colors)-1)]}"/>'
        f'<text x="{fw_max / 2:.1f}" y="{idx * 26 + 14}" fill="#fff" font-size="10" text-anchor="middle">{s}: {v}</text>'
        f'</g>'
        for idx, (s, v) in enumerate(zip(funnel_stages, funnel_vals))
    )
    funnel_h = len(funnel_stages) * 26 + 10

    # --- Velocity gauge (arc) ---
    velocity_score = round(68 + 15 * math.sin(random.uniform(0, math.pi)), 1)  # 0-100
    gauge_angle = -math.pi + math.pi * velocity_score / 100
    gx, gy, gr = 100, 90, 70
    needle_x = gx + gr * 0.85 * math.cos(gauge_angle)
    needle_y = gy + gr * 0.85 * math.sin(gauge_angle)
    arc_path_red   = f"M {gx - gr} {gy} A {gr} {gr} 0 0 1 {gx + gr * math.cos(-math.pi + math.pi * 0.33):.2f} {gy + gr * math.sin(-math.pi + math.pi * 0.33):.2f}"
    arc_path_yel   = f"M {gx + gr * math.cos(-math.pi + math.pi * 0.33):.2f} {gy + gr * math.sin(-math.pi + math.pi * 0.33):.2f} A {gr} {gr} 0 0 1 {gx + gr * math.cos(-math.pi + math.pi * 0.66):.2f} {gy + gr * math.sin(-math.pi + math.pi * 0.66):.2f}"
    arc_path_grn   = f"M {gx + gr * math.cos(-math.pi + math.pi * 0.66):.2f} {gy + gr * math.sin(-math.pi + math.pi * 0.66):.2f} A {gr} {gr} 0 0 1 {gx + gr} {gy}"
    vel_color = "#22c55e" if velocity_score >= 70 else ("#f59e0b" if velocity_score >= 40 else "#ef4444")

    # --- Segment velocity bars ---
    seg_max = max(seg_vel)
    seg_bw, seg_bpad = 60, 12
    seg_bar_svg = "".join(
        f'<rect x="{idx * (seg_bw + seg_bpad)}" y="{120 - int(v / seg_max * 100)}" width="{seg_bw}" height="{int(v / seg_max * 100)}" fill="{c}" rx="3"/>'
        f'<text x="{idx * (seg_bw + seg_bpad) + seg_bw // 2}" y="{120 - int(v / seg_max * 100) - 4}" fill="#e2e8f0" font-size="9" text-anchor="middle">${v//1000}k</text>'
        f'<text x="{idx * (seg_bw + seg_bpad) + seg_bw // 2}" y="136" fill="#94a3b8" font-size="9" text-anchor="middle">{s.replace("/","/")}</text>'
        for idx, (s, v, c) in enumerate(zip(segments, seg_vel, seg_colors))
    )
    seg_total_w = len(segments) * (seg_bw + seg_bpad)

    # --- Churn & Expansion ---
    churn_rate  = round(1.8 + 0.5 * math.sin(3.1), 2)
    expansion   = round(14.2 + 2.0 * math.cos(2.4), 2)
    ndr         = round(100 + expansion - churn_rate, 1)

    return f"""<!DOCTYPE html><html><head><title>Revenue Velocity Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.5rem}}
.subtitle{{color:#64748b;padding:4px 20px 16px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:flex;flex-wrap:wrap;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;flex:1;min-width:240px}}
.kpi{{font-size:2rem;font-weight:800;margin:4px 0}}
.label{{color:#64748b;font-size:0.8rem}}
.up{{color:#22c55e}}.down{{color:#ef4444}}
</style></head>
<body>
<h1>Revenue Velocity Tracker</h1>
<div class="subtitle">OCI Robot Cloud — Pipeline health, ARR momentum, and segment velocity | Port {PORT}</div>

<div class="grid">
  <div class="card">
    <div class="label">Current MRR</div>
    <div class="kpi" style="color:#38bdf8">${current_mrr:,}</div>
    <div class="{'up' if mrr_growth >= 0 else 'down'}" style="font-size:0.9rem">{'▲' if mrr_growth >= 0 else '▼'} {abs(mrr_growth)}% MoM</div>
  </div>
  <div class="card">
    <div class="label">ARR Run-Rate</div>
    <div class="kpi" style="color:#C74634">${current_arr:,}</div>
    <div class="label">Annualized</div>
  </div>
  <div class="card">
    <div class="label">Net Dollar Retention</div>
    <div class="kpi" style="color:#22c55e">{ndr}%</div>
    <div class="label">Expansion {expansion}% | Churn {churn_rate}%</div>
  </div>
  <div class="card">
    <div class="label">Closed Won (MTD)</div>
    <div class="kpi" style="color:#f59e0b">{funnel_vals[-1]}</div>
    <div class="label">From {funnel_vals[0]} qualified leads</div>
  </div>
</div>

<div class="grid">
  <div class="card" style="min-width:540px">
    <h2>MRR Trend — Last 12 Months</h2>
    <svg width="{cw}" height="{ch + 10}" viewBox="0 0 {cw} {ch + 10}">
      <polyline points="{mrr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      {mrr_circles}
      {month_labels}
    </svg>
  </div>
  <div class="card" style="min-width:220px;max-width:280px">
    <h2>Revenue Velocity Score</h2>
    <svg width="200" height="110" viewBox="0 0 200 110">
      <path d="{arc_path_red}" fill="none" stroke="#ef4444" stroke-width="12" stroke-linecap="butt"/>
      <path d="{arc_path_yel}" fill="none" stroke="#f59e0b" stroke-width="12" stroke-linecap="butt"/>
      <path d="{arc_path_grn}" fill="none" stroke="#22c55e" stroke-width="12" stroke-linecap="butt"/>
      <line x1="{gx}" y1="{gy}" x2="{needle_x:.1f}" y2="{needle_y:.1f}" stroke="#e2e8f0" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="{gx}" cy="{gy}" r="5" fill="#e2e8f0"/>
      <text x="{gx}" y="{gy + 24}" fill="{vel_color}" font-size="18" font-weight="bold" text-anchor="middle">{velocity_score}</text>
      <text x="{gx}" y="{gy + 38}" fill="#64748b" font-size="9" text-anchor="middle">/ 100</text>
    </svg>
  </div>
</div>

<div class="grid">
  <div class="card" style="min-width:420px">
    <h2>Revenue by Segment</h2>
    <svg width="{seg_total_w + 20}" height="160" viewBox="0 0 {seg_total_w + 20} 160">
      {seg_bar_svg}
    </svg>
  </div>
  <div class="card" style="min-width:420px">
    <h2>Deal Funnel</h2>
    <svg width="{fw_max}" height="{funnel_h}" viewBox="0 0 {fw_max} {funnel_h}">
      {funnel_svg}
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Velocity Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        random.seed(7)
        base_mrr = 18_500
        mrr = [round(base_mrr * (1 + 0.07 * i + 0.03 * math.sin(i * 0.8)) + random.uniform(-400, 400)) for i in range(12)]
        current_mrr = mrr[-1]
        return {
            "current_mrr": current_mrr,
            "current_arr": current_mrr * 12,
            "mrr_growth_pct": round((mrr[-1] - mrr[-2]) / mrr[-2] * 100, 1),
            "ndr_pct": round(100 + 14.2 + 2.0 * math.cos(2.4) - (1.8 + 0.5 * math.sin(3.1)), 1),
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
