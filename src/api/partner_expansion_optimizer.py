"""Partner Expansion Optimizer — FastAPI port 8759"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8759

def build_html():
    random.seed(99)

    # Partner pipeline data
    partners = [
        {"name": "AutomateX",    "stage": "Closed",     "arr": 84000,  "industry": "Automotive",   "fit": 0.94},
        {"name": "RoboFlex",     "stage": "Negotiation","arr": 120000, "industry": "Logistics",    "fit": 0.91},
        {"name": "NexaBot",      "stage": "Pilot",      "arr": 48000,  "industry": "Manufacturing","fit": 0.87},
        {"name": "AeroDyne",     "stage": "Pilot",      "arr": 60000,  "industry": "Aerospace",    "fit": 0.85},
        {"name": "TerraSync",    "stage": "Negotiation","arr": 95000,  "industry": "Agriculture",  "fit": 0.83},
        {"name": "MediArm",      "stage": "Qualified",  "arr": 75000,  "industry": "Healthcare",   "fit": 0.80},
        {"name": "PackBot",      "stage": "Qualified",  "arr": 55000,  "industry": "Logistics",    "fit": 0.78},
        {"name": "ConstructAI",  "stage": "Outreach",   "arr": 40000,  "industry": "Construction", "fit": 0.74},
        {"name": "SmartGrasp",   "stage": "Outreach",   "arr": 30000,  "industry": "Manufacturing","fit": 0.70},
        {"name": "FarmBot Pro",  "stage": "Research",   "arr": 22000,  "industry": "Agriculture",  "fit": 0.65},
    ]

    stage_order = ["Research", "Outreach", "Qualified", "Pilot", "Negotiation", "Closed"]
    stage_colors = {
        "Research":    "#475569",
        "Outreach":    "#0284c7",
        "Qualified":   "#7c3aed",
        "Pilot":       "#d97706",
        "Negotiation": "#059669",
        "Closed":      "#C74634",
    }

    partner_rows = ""
    for p in partners:
        sc = stage_colors.get(p["stage"], "#64748b")
        bar_pct = int(p["fit"] * 100)
        partner_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600">{p['name']}</td>
          <td style="padding:8px 12px">
            <span style="background:{sc};color:#fff;padding:2px 10px;border-radius:4px;font-size:.75rem;font-weight:600">{p['stage']}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{p['industry']}</td>
          <td style="padding:8px 12px;color:#22c55e;font-weight:700">${p['arr']:,}</td>
          <td style="padding:8px 12px;min-width:120px">
            <div style="background:#1e293b;border-radius:4px;height:8px;width:120px">
              <div style="background:#38bdf8;border-radius:4px;height:8px;width:{bar_pct}px"></div>
            </div>
            <span style="font-size:.75rem;color:#64748b">{bar_pct}% fit</span>
          </td>
        </tr>"""

    # Funnel SVG: count/arr per stage
    stage_counts = {s: 0 for s in stage_order}
    stage_arr = {s: 0 for s in stage_order}
    for p in partners:
        stage_counts[p["stage"]] += 1
        stage_arr[p["stage"]] += p["arr"]

    funnel_svg_w, funnel_svg_h = 400, 220
    funnel_pad = 20
    bar_h = (funnel_svg_h - 2*funnel_pad) / len(stage_order) - 4
    funnel_bars = ""
    max_arr = max(stage_arr.values()) or 1
    for idx, s in enumerate(stage_order):
        bw = max(20, int((stage_arr[s] / max_arr) * (funnel_svg_w - 100)))
        by = funnel_pad + idx * (bar_h + 4)
        color = stage_colors[s]
        funnel_bars += f"""
        <rect x="90" y="{by:.1f}" width="{bw}" height="{bar_h:.1f}" fill="{color}" rx="3" opacity="0.85"/>
        <text x="84" y="{by + bar_h/2 + 4:.1f}" text-anchor="end" style="font-size:10px;fill:#94a3b8">{s}</text>
        <text x="{90+bw+6}" y="{by + bar_h/2 + 4:.1f}" style="font-size:10px;fill:#e2e8f0">${stage_arr[s]//1000}k</text>"""

    # Monthly ARR expansion forecast (sigmoid growth + noise)
    n_months = 12
    forecast = []
    cumulative_arr = sum(p["arr"] for p in partners if p["stage"] == "Closed")
    for m in range(n_months):
        growth = cumulative_arr * (1 + 0.12 * math.exp(-0.3 * m) + random.gauss(0, 0.02))
        cumulative_arr = growth
        forecast.append(growth)

    fc_svg_w, fc_svg_h = 540, 160
    fc_pad = 35
    max_fc = max(forecast)
    min_fc = min(forecast)
    def fx(i): return fc_pad + i * (fc_svg_w - 2*fc_pad) / (n_months - 1)
    def fy(v): return fc_pad + (1 - (v - min_fc) / (max_fc - min_fc + 1)) * (fc_svg_h - 2*fc_pad)
    fc_path = " ".join(f"{fx(i):.1f},{fy(v):.1f}" for i, v in enumerate(forecast))
    month_labels = ""
    for i, v in enumerate(forecast):
        if i % 3 == 0:
            month_labels += f'<text x="{fx(i):.1f}" y="{fc_svg_h - fc_pad + 14}" text-anchor="middle" style="font-size:9px;fill:#64748b">M{i+1}</text>'

    # Score radar (pentagon) for top partner
    top = partners[0]
    dims = ["Tech Fit", "Market", "Revenue", "Deploy", "Support"]
    scores = [0.94, 0.88, 0.91, 0.85, 0.90]
    cx, cy, r = 120, 110, 80
    def radar_pt(angle_deg, radius):
        a = math.radians(angle_deg - 90)
        return cx + radius * math.cos(a), cy + radius * math.sin(a)
    angles = [i * 360 / len(dims) for i in range(len(dims))]
    outer_pts = " ".join(f"{radar_pt(a, r)[0]:.1f},{radar_pt(a, r)[1]:.1f}" for a in angles)
    score_pts = " ".join(f"{radar_pt(a, s*r)[0]:.1f},{radar_pt(a, s*r)[1]:.1f}" for a, s in zip(angles, scores))
    radar_labels = ""
    for i, (a, d) in enumerate(zip(angles, dims)):
        lx2, ly2 = radar_pt(a, r + 14)
        radar_labels += f'<text x="{lx2:.1f}" y="{ly2:.1f}" text-anchor="middle" style="font-size:9px;fill:#94a3b8">{d}</text>'

    total_pipeline_arr = sum(p["arr"] for p in partners)
    closed_arr = sum(p["arr"] for p in partners if p["stage"] == "Closed")
    active_partners = len([p for p in partners if p["stage"] not in ["Research", "Outreach"]])
    avg_fit = sum(p["fit"] for p in partners) / len(partners)

    return f"""<!DOCTYPE html>
<html><head><title>Partner Expansion Optimizer</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:1.5rem;letter-spacing:.02em}}
  h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .card.wide{{grid-column:span 2}}
  .stat{{display:inline-block;margin-right:28px;margin-bottom:8px}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#f1f5f9}}
  .stat .lbl{{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even){{background:#0f172a30}}
  th{{text-align:left;padding:8px 12px;color:#64748b;font-weight:500;border-bottom:1px solid #334155}}
  svg text{{font-family:system-ui,sans-serif}}
</style></head>
<body>
<h1>Partner Expansion Optimizer</h1>
<p style="color:#64748b;margin:4px 24px 0;font-size:.85rem">OCI Robot Cloud — Design Partner CRM &amp; Revenue Forecast — Port {PORT}</p>

<div class="grid">
  <div class="card wide">
    <h2>Pipeline Summary</h2>
    <div class="stat"><div class="val">${total_pipeline_arr//1000}k</div><div class="lbl">Total Pipeline ARR</div></div>
    <div class="stat"><div class="val">${closed_arr//1000}k</div><div class="lbl">Closed ARR</div></div>
    <div class="stat"><div class="val">{len(partners)}</div><div class="lbl">Total Partners</div></div>
    <div class="stat"><div class="val">{active_partners}</div><div class="lbl">Active (Pilot+)</div></div>
    <div class="stat"><div class="val">{avg_fit*100:.0f}%</div><div class="lbl">Avg Fit Score</div></div>
    <div class="stat"><div class="val">${forecast[-1]//1000}k</div><div class="lbl">12-mo Forecast ARR</div></div>
  </div>

  <div class="card">
    <h2>ARR by Pipeline Stage</h2>
    <svg width="{funnel_svg_w}" height="{funnel_svg_h}" style="display:block">
      {funnel_bars}
      <line x1="90" y1="{funnel_pad}" x2="90" y2="{funnel_svg_h-funnel_pad}" stroke="#334155" stroke-width="1"/>
    </svg>
  </div>

  <div class="card">
    <h2>Top Partner Fit Radar — {top['name']}</h2>
    <svg width="240" height="220" style="display:block">
      <polygon points="{outer_pts}" fill="none" stroke="#334155" stroke-width="1"/>
      <polygon points="{score_pts}" fill="#38bdf820" stroke="#38bdf8" stroke-width="2"/>
      {radar_labels}
      {''.join(f'<circle cx="{radar_pt(a,s*r)[0]:.1f}" cy="{radar_pt(a,s*r)[1]:.1f}" r="3" fill="#38bdf8"/>' for a,s in zip(angles,scores))}
    </svg>
  </div>

  <div class="card wide">
    <h2>12-Month ARR Expansion Forecast</h2>
    <svg width="{fc_svg_w}" height="{fc_svg_h}" style="display:block">
      <defs><linearGradient id="fcg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#22c55e" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#22c55e" stop-opacity="0"/>
      </linearGradient></defs>
      <polyline points="{fc_path}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
      <polygon points="{fc_path} {fx(n_months-1):.1f},{fc_svg_h-fc_pad} {fx(0):.1f},{fc_svg_h-fc_pad}" fill="url(#fcg)"/>
      <line x1="{fc_pad}" y1="{fc_svg_h-fc_pad}" x2="{fc_svg_w-fc_pad}" y2="{fc_svg_h-fc_pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{fc_pad}" y1="{fc_pad}" x2="{fc_pad}" y2="{fc_svg_h-fc_pad}" stroke="#334155" stroke-width="1"/>
      <text x="{fc_pad}" y="{fc_pad-4}" style="font-size:10px;fill:#64748b">${max_fc/1000:.0f}k</text>
      <text x="{fc_pad}" y="{fc_svg_h-fc_pad+14}" style="font-size:10px;fill:#64748b">${min_fc/1000:.0f}k</text>
      {month_labels}
    </svg>
  </div>

  <div class="card wide">
    <h2>Partner Pipeline</h2>
    <table>
      <thead><tr>
        <th>Partner</th><th>Stage</th><th>Industry</th><th>ARR</th><th>Fit Score</th>
      </tr></thead>
      <tbody>{partner_rows}</tbody>
    </table>
  </div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Expansion Optimizer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
