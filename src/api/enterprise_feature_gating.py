"""Enterprise Feature Gating — FastAPI port 8699"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8699

# Feature catalog with tier gating
FEATURES = [
    {"name": "Basic Inference",         "tier": "Free",       "enabled": True,  "calls_today": 0, "limit": 1000},
    {"name": "Batch Eval Pipeline",     "tier": "Starter",    "enabled": True,  "calls_today": 0, "limit": 5000},
    {"name": "DAgger Fine-Tuning",      "tier": "Pro",        "enabled": True,  "calls_today": 0, "limit": 20000},
    {"name": "Multi-Task Curriculum",   "tier": "Pro",        "enabled": True,  "calls_today": 0, "limit": 20000},
    {"name": "GR00T N1.6 Access",       "tier": "Enterprise", "enabled": True,  "calls_today": 0, "limit": 100000},
    {"name": "Isaac Sim SDG",           "tier": "Enterprise", "enabled": True,  "calls_today": 0, "limit": 100000},
    {"name": "Multi-GPU DDP Training",  "tier": "Enterprise", "enabled": True,  "calls_today": 0, "limit": 100000},
    {"name": "Jetson Edge Deploy",      "tier": "Enterprise", "enabled": False, "calls_today": 0, "limit": 100000},
    {"name": "Cosmos World Model",      "tier": "Custom",     "enabled": False, "calls_today": 0, "limit": 0},
    {"name": "Real-Time Teleoperation", "tier": "Custom",     "enabled": False, "calls_today": 0, "limit": 0},
    {"name": "Policy Distillation API", "tier": "Pro",        "enabled": True,  "calls_today": 0, "limit": 15000},
    {"name": "Data Flywheel Optimizer", "tier": "Enterprise", "enabled": True,  "calls_today": 0, "limit": 50000},
]

TIER_COLORS = {
    "Free":       "#64748b",
    "Starter":    "#22c55e",
    "Pro":        "#38bdf8",
    "Enterprise": "#a78bfa",
    "Custom":     "#f59e0b",
}

TENANTS = ["OCI-Robotics-Prod", "Toyota-Research", "Boston-Dynamics-Dev", "Agility-Pilot", "NVIDIA-Partner"]

def build_html():
    # Simulate per-feature usage (calls today and quota %)
    random.seed(42)
    for f in FEATURES:
        if f["limit"] > 0:
            f["calls_today"] = int(f["limit"] * random.uniform(0.1, 0.91))
        else:
            f["calls_today"] = 0

    # Time-series: API calls per hour (last 24h)
    hours = 24
    calls_per_hour = [
        max(0, int(3200 * (0.3 + 0.7 * abs(math.sin(math.pi * h / 12))) + random.uniform(-200, 200)))
        for h in range(hours)
    ]
    max_cph = max(calls_per_hour)
    bar_w = 520 / hours
    bar_chart = "".join(
        f'<rect x="{i*bar_w:.1f}" y="{120 - 110*(v/max_cph):.1f}" width="{bar_w*0.8:.1f}" height="{110*(v/max_cph):.1f}" fill="#38bdf8" opacity="0.75"/>'
        for i, v in enumerate(calls_per_hour)
    )
    hour_labels = "".join(
        f'<text x="{i*bar_w + bar_w/2:.1f}" y="135" fill="#64748b" font-size="8" text-anchor="middle">{i:02d}h</text>'
        for i in range(0, hours, 4)
    )

    # Pie chart: calls by tier (SVG arc approximation using circles)
    tier_totals = {}
    for f in FEATURES:
        tier_totals[f["tier"]] = tier_totals.get(f["tier"], 0) + f["calls_today"]
    total_calls = max(1, sum(tier_totals.values()))
    # Build donut segments via stroke-dasharray trick
    cx, cy, r = 90, 90, 60
    circ = 2 * math.pi * r
    segments = []
    offset = 0.0
    for tier, val in tier_totals.items():
        frac = val / total_calls
        color = TIER_COLORS.get(tier, "#94a3b8")
        dash = frac * circ
        segments.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="28" '
            f'stroke-dasharray="{dash:.2f} {circ:.2f}" stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += dash
    donut_svg = "".join(segments)
    legend_items = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
        f'<div style="width:12px;height:12px;border-radius:2px;background:{TIER_COLORS.get(t,"#94a3b8")}"></div>'
        f'<span style="color:#94a3b8;font-size:0.82em">{t}: {tier_totals[t]:,}</span></div>'
        for t in tier_totals
    )

    # Feature rows
    feature_rows = "".join(
        f"""<tr style='border-bottom:1px solid #0f172a'>
          <td style='padding:7px 8px'>{f['name']}</td>
          <td style='padding:7px 8px'><span style='background:{TIER_COLORS.get(f['tier'],'#94a3b8')}22;
            color:{TIER_COLORS.get(f['tier'],'#94a3b8')};padding:2px 8px;border-radius:4px;font-size:0.8em'>{f['tier']}</span></td>
          <td style='padding:7px 8px'><span style='color:{"#22c55e" if f["enabled"] else "#ef4444"}'>
            {"Enabled" if f["enabled"] else "Disabled"}</span></td>
          <td style='padding:7px 8px'>{f['calls_today']:,} / {f['limit']:,}</td>
          <td style='padding:7px 8px'>
            <div style='background:#0f172a;border-radius:4px;height:8px;width:120px'>
              <div style='background:{TIER_COLORS.get(f["tier"],'#94a3b8')};height:8px;border-radius:4px;
                width:{min(100, int(100*f["calls_today"]/max(1,f["limit"]))):.0f}px'></div>
            </div>
          </td>
        </tr>"""
        for f in FEATURES
    )

    # Tenant table
    tenant_rows = ""
    for t in TENANTS:
        tier = random.choice(["Pro", "Enterprise", "Custom"])
        active = random.randint(2, 8)
        calls = random.randint(1200, 48000)
        tenant_rows += (
            f"<tr style='border-bottom:1px solid #0f172a'>"
            f"<td style='padding:6px 8px'>{t}</td>"
            f"<td style='padding:6px 8px'><span style='color:{TIER_COLORS.get(tier,'#94a3b8')}'>{tier}</span></td>"
            f"<td style='padding:6px 8px'>{active} features</td>"
            f"<td style='padding:6px 8px'>{calls:,}</td>"
            f"<td style='padding:6px 8px'><span style='color:#22c55e'>Active</span></td>"
            "</tr>"
        )

    total_api = sum(calls_per_hour)
    enabled_count = sum(1 for f in FEATURES if f["enabled"])
    disabled_count = len(FEATURES) - enabled_count
    quota_pct = int(100 * sum(f["calls_today"] for f in FEATURES) / max(1, sum(f["limit"] for f in FEATURES if f["limit"] > 0)))

    return f"""<!DOCTYPE html><html><head><title>Enterprise Feature Gating</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;text-align:center}}
.stat-val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.stat-lbl{{color:#94a3b8;font-size:0.85em;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.88em}}
th{{text-align:left;padding:6px 8px;color:#94a3b8;border-bottom:1px solid #334155}}
.row2{{display:grid;grid-template-columns:2fr 1fr;gap:10px;margin:10px}}
</style></head>
<body>
<h1>Enterprise Feature Gating</h1>
<p style="color:#94a3b8;padding:0 20px;margin:4px 0">Port {PORT} — Manage feature access by tenant tier and enforce API quotas</p>

<div class="grid">
  <div class="stat"><div class="stat-val">{len(FEATURES)}</div><div class="stat-lbl">Total Features</div></div>
  <div class="stat"><div class="stat-val">{enabled_count}</div><div class="stat-lbl">Enabled</div></div>
  <div class="stat"><div class="stat-val">{disabled_count}</div><div class="stat-lbl">Gated / Disabled</div></div>
  <div class="stat"><div class="stat-val">{quota_pct}%</div><div class="stat-lbl">Overall Quota Used</div></div>
</div>

<div class="row2">
  <div class="card">
    <h2>API Calls — Last 24 Hours</h2>
    <svg viewBox="0 0 540 150" style="width:100%;height:150px">
      <line x1="0" y1="120" x2="540" y2="120" stroke="#334155" stroke-width="1"/>
      {bar_chart}
      {hour_labels}
      <text x="2" y="14" fill="#64748b" font-size="9">{max_cph:,}</text>
      <text x="2" y="118" fill="#64748b" font-size="9">0</text>
      <text x="200" y="148" fill="#94a3b8" font-size="10">Total today: {total_api:,} calls</text>
    </svg>
  </div>
  <div class="card">
    <h2>Calls by Tier</h2>
    <svg viewBox="0 0 180 180" style="width:180px;height:180px">
      {donut_svg}
      <text x="{cx}" y="{cy+5}" fill="#e2e8f0" font-size="11" text-anchor="middle">{total_calls:,}</text>
      <text x="{cx}" y="{cy+17}" fill="#94a3b8" font-size="8" text-anchor="middle">total calls</text>
    </svg>
    <div style="margin-top:8px">{legend_items}</div>
  </div>
</div>

<div class="card" style="margin:10px">
  <h2>Feature Registry</h2>
  <table>
    <tr><th>Feature</th><th>Tier</th><th>Status</th><th>Usage</th><th>Quota</th></tr>
    {feature_rows}
  </table>
</div>

<div class="card" style="margin:10px">
  <h2>Active Tenants</h2>
  <table>
    <tr><th>Tenant</th><th>Plan</th><th>Active Features</th><th>Calls Today</th><th>Status</th></tr>
    {tenant_rows}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Enterprise Feature Gating")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/features")
    def features(): return {"features": FEATURES, "total": len(FEATURES)}
    @app.get("/tenants")
    def tenants(): return {"tenants": TENANTS}

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
