"""Developer Relations Dashboard — FastAPI port 8821"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8821

def build_html():
    random.seed(7)
    weeks = 16

    # SDK downloads per week (growing trend with noise)
    sdk_downloads = [
        int(420 + 280 * (i / weeks) + 90 * math.sin(i * 0.7) + random.uniform(-30, 30))
        for i in range(weeks)
    ]

    # Forum posts per week
    forum_posts = [
        int(18 + 22 * (i / weeks) + 8 * math.cos(i * 0.9) + random.uniform(-3, 3))
        for i in range(weeks)
    ]

    # GitHub stars cumulative
    weekly_stars = [int(12 + 18 * math.sqrt(i + 1) + random.uniform(-2, 2)) for i in range(weeks)]
    cum_stars = []
    total = 340
    for s in weekly_stars:
        total += s
        cum_stars.append(total)

    # SDK downloads SVG (area chart)
    svg_w, svg_h = 560, 140
    max_dl = max(sdk_downloads) or 1
    dl_pts = " ".join(
        f"{int(10 + i * (svg_w - 20) / (weeks - 1))},{int(svg_h - 10 - (sdk_downloads[i] / max_dl) * (svg_h - 20))}"
        for i in range(weeks)
    )
    dl_area = (
        f"M 10,{svg_h - 10} "
        + " L ".join(
            f"{int(10 + i * (svg_w - 20) / (weeks - 1))},{int(svg_h - 10 - (sdk_downloads[i] / max_dl) * (svg_h - 20))}"
            for i in range(weeks)
        )
        + f" L {svg_w - 10},{svg_h - 10} Z"
    )

    # Stars cumulative SVG line
    max_stars = cum_stars[-1] or 1
    star_path = "M " + " L ".join(
        f"{int(10 + i * (svg_w - 20) / (weeks - 1))},{int(svg_h - 10 - (cum_stars[i] / max_stars) * (svg_h - 20))}"
        for i in range(weeks)
    )

    # Forum bar chart
    bar_svg_w, bar_svg_h = 560, 120
    max_fp = max(forum_posts) or 1
    bar_w = (bar_svg_w - 20) / weeks
    fp_bars = "".join(
        f"<rect x='{10 + k * bar_w:.1f}' y='{bar_svg_h - 10 - forum_posts[k]/max_fp*(bar_svg_h-20):.1f}' "
        f"width='{bar_w-2:.1f}' height='{forum_posts[k]/max_fp*(bar_svg_h-20):.1f}' "
        f"fill='{'#38bdf8' if forum_posts[k] > max_fp*0.7 else '#0ea5e9'}' opacity='0.9'/>"
        for k in range(weeks)
    )

    # Developer cohort data
    cohorts = [
        {"name": "Robotics / Sim", "devs": 1840, "active_30d": 1210, "avg_calls": 4320, "nps": 62},
        {"name": "CV / Perception", "devs": 2310, "active_30d": 1760, "avg_calls": 5870, "nps": 71},
        {"name": "LLM Agents",      "devs": 3640, "active_30d": 2950, "avg_calls": 8140, "nps": 78},
        {"name": "Industrial IoT",  "devs": 980,  "active_30d": 620,  "avg_calls": 2110, "nps": 55},
        {"name": "Autonomous Sys",  "devs": 1270, "active_30d": 890,  "avg_calls": 3490, "nps": 68},
    ]
    cohort_rows = "".join(
        f"<tr><td>{c['name']}</td><td>{c['devs']:,}</td><td>{c['active_30d']:,}</td>"
        f"<td>{c['avg_calls']:,}</td>"
        f"<td style='color:{'#4ade80' if c['nps']>=70 else '#facc15' if c['nps']>=60 else '#f87171'}'>{c['nps']}</td></tr>"
        for c in cohorts
    )

    # Support ticket status (pie-like horizontal bars)
    ticket_cats = [
        ("Authentication", 38, "#f87171"),
        ("SDK Integration", 61, "#facc15"),
        ("Rate Limits",     29, "#34d399"),
        ("Inference API",   77, "#38bdf8"),
        ("Docs / Examples", 42, "#a78bfa"),
    ]
    total_tickets = sum(t[1] for t in ticket_cats)
    ticket_bars = "".join(
        f"""<div style='margin:6px 0'>
          <div style='display:flex;justify-content:space-between;font-size:0.8rem;color:#94a3b8;margin-bottom:2px'>
            <span>{t[0]}</span><span>{t[1]}</span></div>
          <div style='background:#0f172a;border-radius:4px;height:10px'>
            <div style='background:{t[2]};width:{int(t[1]/total_tickets*100*2.5)}%;height:10px;border-radius:4px'></div>
          </div></div>"""
        for t in ticket_cats
    )

    # Event funnel
    funnel_steps = [
        ("Registered",  5200),
        ("Attended",    3780),
        ("Demo'd SDK",  2140),
        ("Trial API Key",1390),
        ("Active User",  870),
    ]
    max_funnel = funnel_steps[0][1]
    funnel_bars = "".join(
        f"""<div style='margin:5px 0;text-align:center'>
          <div style='display:inline-block;background:{c};height:28px;line-height:28px;
            width:{int(v/max_funnel*100)}%;min-width:60px;border-radius:4px;font-size:0.8rem;
            font-weight:600;color:#0f172a'>{label} ({v:,})</div></div>"""
        for (label, v), c in zip(funnel_steps, ["#C74634","#f97316","#facc15","#34d399","#38bdf8"])
    )

    total_devs = sum(c["devs"] for c in cohorts)
    total_active = sum(c["active_30d"] for c in cohorts)
    avg_nps = round(sum(c["nps"] for c in cohorts) / len(cohorts), 1)
    total_dl = sum(sdk_downloads)

    return f"""<!DOCTYPE html><html><head><title>Developer Relations Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.stat-row{{display:flex;gap:12px;flex-wrap:wrap;padding:0 16px 4px}}
.stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 18px;flex:1;min-width:100px}}
.stat-val{{font-size:1.6rem;font-weight:700;color:#f8fafc}}
.stat-label{{font-size:0.72rem;color:#64748b;margin-top:3px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:#0f172a;color:#94a3b8;padding:6px 8px;text-align:left;font-weight:600}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:hover td{{background:#1e3a5f}}
.legend{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
svg{{width:100%;height:auto;display:block}}
</style></head>
<body>
<h1>Developer Relations Dashboard</h1>
<div class="subtitle">OCI Robot Cloud — SDK adoption, community health &amp; DevRel KPIs &nbsp;|&nbsp; Port {PORT}</div>

<div class="stat-row">
  <div class="stat"><div class="stat-val">{total_devs:,}</div><div class="stat-label">Registered Developers</div></div>
  <div class="stat"><div class="stat-val">{total_active:,}</div><div class="stat-label">Active (30d)</div></div>
  <div class="stat"><div class="stat-val">{total_dl:,}</div><div class="stat-label">SDK Downloads (16w)</div></div>
  <div class="stat"><div class="stat-val" style="color:#4ade80">{cum_stars[-1]:,}</div><div class="stat-label">GitHub Stars</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#4ade80' if avg_nps>=70 else '#facc15'}">{avg_nps}</div><div class="stat-label">Avg NPS</div></div>
</div>

<div class="grid" style="margin-top:12px">
  <div class="card" style="grid-column:span 2">
    <h2>SDK Downloads — 16-Week Trend</h2>
    <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
      <defs><linearGradient id="dlg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#C74634" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="#C74634" stop-opacity="0.0"/>
      </linearGradient></defs>
      <line x1="10" y1="{int(svg_h*0.33)}" x2="{svg_w-10}" y2="{int(svg_h*0.33)}" stroke="#1e293b" stroke-width="1"/>
      <line x1="10" y1="{int(svg_h*0.66)}" x2="{svg_w-10}" y2="{int(svg_h*0.66)}" stroke="#1e293b" stroke-width="1"/>
      <path d="{dl_area}" fill="url(#dlg)"/>
      <polyline points="{dl_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>
      {''.join(f'<circle cx="{int(10+i*(svg_w-20)/(weeks-1))}" cy="{int(svg_h-10-(sdk_downloads[i]/max_dl)*(svg_h-20))}" r="3" fill="#f87171"/>' for i in range(0,weeks,2))}
    </svg>
    <div class="legend">Week 1 – {weeks} &nbsp;|&nbsp; Y-axis: downloads per week (max {max_dl:,})</div>
  </div>

  <div class="card">
    <h2>GitHub Stars (Cumulative)</h2>
    <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
      <line x1="10" y1="{int(svg_h*0.5)}" x2="{svg_w-10}" y2="{int(svg_h*0.5)}" stroke="#1e293b" stroke-width="1"/>
      <path d="{star_path}" fill="none" stroke="#facc15" stroke-width="2.5"/>
      {''.join(f'<circle cx="{int(10+i*(svg_w-20)/(weeks-1))}" cy="{int(svg_h-10-(cum_stars[i]/max_stars)*(svg_h-20))}" r="3" fill="#fde68a"/>' for i in range(0,weeks,3))}
    </svg>
    <div class="legend">Cumulative stars: {cum_stars[0]:,} → {cum_stars[-1]:,}</div>
  </div>

  <div class="card">
    <h2>Forum Activity (Posts/Week)</h2>
    <svg viewBox="0 0 {bar_svg_w} {bar_svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{bar_svg_w}" height="{bar_svg_h}" fill="#0f172a" rx="4"/>
      {fp_bars}
      <line x1="10" y1="{bar_svg_h-10}" x2="{bar_svg_w-10}" y2="{bar_svg_h-10}" stroke="#475569" stroke-width="1"/>
    </svg>
    <div class="legend">Discourse / Stack Overflow posts per week | peak: {max(forum_posts)}</div>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Developer Cohorts</h2>
    <table>
      <tr><th>Segment</th><th>Total Devs</th><th>Active 30d</th><th>Avg API Calls/Mo</th><th>NPS</th></tr>
      {cohort_rows}
    </table>
  </div>

  <div class="card">
    <h2>Open Support Tickets by Category</h2>
    {ticket_bars}
    <div class="legend" style="margin-top:8px">Total open: {total_tickets} tickets</div>
  </div>

  <div class="card">
    <h2>Developer Event Funnel (Last Hackathon)</h2>
    {funnel_bars}
    <div class="legend" style="margin-top:8px">Conversion: {int(funnel_steps[-1][1]/funnel_steps[0][1]*100)}% registered → active</div>
  </div>

  <div class="card">
    <h2>DevRel Program Health</h2>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>SDK Languages</td><td>Python, Go, TypeScript</td></tr>
      <tr><td>Doc Pages Published</td><td>214</td></tr>
      <tr><td>Sample Notebooks</td><td>38</td></tr>
      <tr><td>Office Hours / Month</td><td>4</td></tr>
      <tr><td>Partner Integrations</td><td>17</td></tr>
      <tr><td>Changelog Subscribers</td><td>4,820</td></tr>
      <tr><td>Discord Members</td><td>6,140</td></tr>
      <tr><td>Avg Time-to-First-Call</td><td>8.3 min</td></tr>
    </table>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Developer Relations Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


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
