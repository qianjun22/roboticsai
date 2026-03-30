"""Customer Expansion Tracker — FastAPI port 8711"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8711

def build_html():
    random.seed(99)

    # Accounts with expansion signals
    accounts = [
        {"name": "Acme Robotics",       "tier": "Enterprise", "arr": 420000, "growth": 0.38, "health": 92},
        {"name": "NovaMech Systems",     "tier": "Enterprise", "arr": 310000, "growth": 0.27, "health": 85},
        {"name": "Skyline Automation",   "tier": "Growth",     "arr": 180000, "growth": 0.61, "health": 78},
        {"name": "PrecisionBot Inc",     "tier": "Growth",     "arr": 145000, "growth": 0.45, "health": 81},
        {"name": "Horizon Mechatronics", "tier": "Enterprise", "arr": 530000, "growth": 0.22, "health": 89},
        {"name": "VaultDynamics",        "tier": "Starter",    "arr":  62000, "growth": 1.12, "health": 74},
        {"name": "OmegaArm Labs",        "tier": "Growth",     "arr": 210000, "growth": 0.33, "health": 88},
        {"name": "ClearPath Robotics",   "tier": "Enterprise", "arr": 475000, "growth": 0.18, "health": 91},
    ]

    total_arr = sum(a["arr"] for a in accounts)
    total_expansion = sum(a["arr"] * a["growth"] for a in accounts)
    avg_health = sum(a["health"] for a in accounts) / len(accounts)

    # Monthly ARR trend (12 months, sinusoidal growth)
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    base = 1_800_000
    monthly_arr = [
        base * (1 + 0.04 * i + 0.015 * math.sin(i * 0.9)) + random.uniform(-15000, 15000)
        for i in range(12)
    ]
    monthly_expansion = [
        v * (0.22 + 0.06 * math.sin(i * 0.7 + 1.2)) + random.uniform(-8000, 8000)
        for i, v in enumerate(monthly_arr)
    ]

    # SVG line chart for ARR trend
    W, H = 560, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 36
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    min_v = min(monthly_arr) * 0.97
    max_v = max(monthly_arr) * 1.03

    def to_x(i):
        return pad_l + (i / (len(months) - 1)) * chart_w

    def to_y(v):
        return pad_t + chart_h - ((v - min_v) / (max_v - min_v)) * chart_h

    arr_path = " ".join(
        ("M" if i == 0 else "L") + f"{to_x(i):.1f},{to_y(v):.1f}"
        for i, v in enumerate(monthly_arr)
    )
    exp_path_pts = [
        f"{to_x(i):.1f},{to_y(min_v + (monthly_expansion[i] / max_v) * (max_v - min_v) * 0.55):.1f}"
        for i in range(len(months))
    ]
    exp_path = "M" + " L".join(exp_path_pts)

    dots = "".join(
        f'<circle cx="{to_x(i):.1f}" cy="{to_y(v):.1f}" r="3" fill="#38bdf8"/>'
        for i, v in enumerate(monthly_arr)
    )
    x_labels = "".join(
        f'<text x="{to_x(i):.1f}" y="{pad_t+chart_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )
    y_ticks_v = [min_v + k * (max_v - min_v) / 4 for k in range(5)]
    y_labels = "".join(
        f'<text x="{pad_l-6}" y="{to_y(v)+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">${v/1e6:.1f}M</text>'
        f'<line x1="{pad_l}" y1="{to_y(v):.1f}" x2="{pad_l+chart_w}" y2="{to_y(v):.1f}" stroke="#1e3a52" stroke-width="1"/>'
        for v in y_ticks_v
    )

    # Account table rows
    tier_color = {"Enterprise": "#7dd3fc", "Growth": "#86efac", "Starter": "#fde68a"}
    table_rows = "".join(
        f"""<tr>
          <td>{a['name']}</td>
          <td><span style="background:#0f172a;color:{tier_color.get(a['tier'],'#e2e8f0')};padding:2px 8px;border-radius:10px;font-size:.78rem">{a['tier']}</span></td>
          <td style="text-align:right">${a['arr']:,}</td>
          <td style="text-align:right;color:#86efac">+{a['growth']:.0%}</td>
          <td>
            <div style="background:#1e293b;border-radius:4px;height:10px;width:100px">
              <div style="background:{'#22c55e' if a['health']>=85 else '#f59e0b'};height:10px;border-radius:4px;width:{a['health']}px"></div>
            </div>
          </td>
          <td style="text-align:center">{a['health']}</td>
        </tr>"""
        for a in sorted(accounts, key=lambda x: -x["arr"])
    )

    # Donut chart SVG for tier mix
    tier_counts = {}
    for a in accounts:
        tier_counts[a["tier"]] = tier_counts.get(a["tier"], 0) + a["arr"]
    total_tc = sum(tier_counts.values())
    tier_colors_map = {"Enterprise": "#38bdf8", "Growth": "#86efac", "Starter": "#fde68a"}
    cx_d, cy_d, r_outer, r_inner = 90, 90, 75, 45
    start_angle = -math.pi / 2
    donut_paths = []
    legend_items = []
    for tier, val in tier_counts.items():
        frac = val / total_tc
        sweep = frac * 2 * math.pi
        end_angle = start_angle + sweep
        lx1 = cx_d + r_outer * math.cos(start_angle)
        ly1 = cy_d + r_outer * math.sin(start_angle)
        lx2 = cx_d + r_outer * math.cos(end_angle)
        ly2 = cy_d + r_outer * math.sin(end_angle)
        sx1 = cx_d + r_inner * math.cos(end_angle)
        sy1 = cy_d + r_inner * math.sin(end_angle)
        sx2 = cx_d + r_inner * math.cos(start_angle)
        sy2 = cy_d + r_inner * math.sin(start_angle)
        large = 1 if sweep > math.pi else 0
        color = tier_colors_map.get(tier, "#94a3b8")
        donut_paths.append(
            f'<path d="M {lx1:.2f} {ly1:.2f} A {r_outer} {r_outer} 0 {large} 1 {lx2:.2f} {ly2:.2f} '
            f'L {sx1:.2f} {sy1:.2f} A {r_inner} {r_inner} 0 {large} 0 {sx2:.2f} {sy2:.2f} Z" fill="{color}" opacity="0.9"/>'
        )
        legend_items.append(
            f'<div style="display:flex;align-items:center;gap:6px;font-size:.8rem">'
            f'<div style="width:10px;height:10px;border-radius:2px;background:{color}"></div>'
            f'{tier}: {frac:.0%}</div>'
        )
        start_angle = end_angle

    donut_svg = "\n".join(donut_paths)
    legend_html = "\n".join(legend_items)

    return f"""<!DOCTYPE html><html><head><title>Customer Expansion Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;margin:0 0 20px 0;font-size:.85rem}}
h2{{color:#38bdf8;margin:0 0 12px 0;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1160px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.full{{grid-column:1/-1}}
.stat-row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:18px}}
.stat{{background:#1e293b;padding:12px 22px;border-radius:6px;border-left:3px solid #38bdf8}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th{{color:#64748b;font-weight:600;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:7px 10px;border-bottom:1px solid #1e2d3d}}
tr:last-child td{{border-bottom:none}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Customer Expansion Tracker</h1>
<p class="subtitle">OCI Robot Cloud — Design Partner Pipeline &amp; ARR Growth | port {PORT}</p>
<div class="stat-row">
  <div class="stat"><div class="val">${total_arr/1e6:.2f}M</div><div class="lbl">Total ARR</div></div>
  <div class="stat"><div class="val">${total_expansion/1e3:.0f}K</div><div class="lbl">Expansion Pipeline</div></div>
  <div class="stat"><div class="val">{len(accounts)}</div><div class="lbl">Active Accounts</div></div>
  <div class="stat"><div class="val">{avg_health:.1f}</div><div class="lbl">Avg Health Score</div></div>
  <div class="stat"><div class="val">{sum(1 for a in accounts if a['growth']>0.4)}</div><div class="lbl">High-Growth (&gt;40%)</div></div>
</div>
<div class="grid">
  <div class="card full">
    <h2>Monthly ARR Trend (TTM)</h2>
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
      {y_labels}
      {x_labels}
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>
      <line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>
      <path d="{arr_path}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <path d="{exp_path}" fill="none" stroke="#86efac" stroke-width="2" stroke-dasharray="5,4"/>
      {dots}
      <text x="{pad_l+16}" y="{pad_t+14}" fill="#38bdf8" font-size="11">— Total ARR</text>
      <text x="{pad_l+110}" y="{pad_t+14}" fill="#86efac" font-size="11">- - Expansion</text>
    </svg>
  </div>
  <div class="card full">
    <h2>Account Expansion Details</h2>
    <table>
      <thead><tr><th>Account</th><th>Tier</th><th style="text-align:right">ARR</th><th style="text-align:right">YoY Growth</th><th>Health</th><th style="text-align:center">Score</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>ARR by Tier</h2>
    <div style="display:flex;align-items:center;gap:24px">
      <svg width="180" height="180">
        {donut_svg}
        <text x="{cx_d}" y="{cy_d+5}" fill="#e2e8f0" font-size="13" font-weight="700" text-anchor="middle">${total_arr/1e6:.1f}M</text>
      </svg>
      <div style="display:flex;flex-direction:column;gap:8px">{legend_html}</div>
    </div>
  </div>
  <div class="card">
    <h2>Expansion Signals</h2>
    <div style="line-height:1.85;font-size:.88rem">
      <div><span style="color:#64748b">Top expander:</span> VaultDynamics (+112%)</div>
      <div><span style="color:#64748b">Largest account:</span> Horizon Mechatronics ($530K)</div>
      <div><span style="color:#64748b">At-risk (&lt;80 health):</span> {sum(1 for a in accounts if a['health']<80)} accounts</div>
      <div><span style="color:#64748b">QBRs due this month:</span> {random.randint(3,5)}</div>
      <div><span style="color:#64748b">Upsell opportunities:</span> {sum(1 for a in accounts if a['growth']>0.35 and a['tier']!='Enterprise')}</div>
      <div><span style="color:#64748b">NPS (last survey):</span> 67</div>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Expansion Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "customer_expansion_tracker"}

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
