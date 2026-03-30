"""Technical Documentation Hub — FastAPI port 8809"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8809

def build_html():
    random.seed(99)

    # Simulate doc sections with view counts and coverage scores
    sections = [
        ("GR00T N1.6 API Reference",   random.randint(340, 890),  95),
        ("Fine-Tuning Pipeline",        random.randint(200, 700),  88),
        ("Isaac Sim Integration",        random.randint(150, 600),  76),
        ("OCI Deployment Guide",         random.randint(120, 500),  82),
        ("Data Collection API",          random.randint(100, 450),  71),
        ("Closed-Loop Evaluation",       random.randint( 80, 400),  68),
        ("SDK Quick Start",              random.randint(400, 950),  99),
        ("DAgger Training",              random.randint( 60, 350),  60),
    ]

    # Bar chart: views per section
    max_views = max(v for _, v, _ in sections)
    bar_h = 22
    bar_svg_h = len(sections) * (bar_h + 6) + 30
    bars = ""
    for i, (name, views, cov) in enumerate(sections):
        bw = views / max_views * 340
        cy = 20 + i * (bar_h + 6)
        color = "#38bdf8" if cov >= 80 else "#f59e0b" if cov >= 65 else "#ef4444"
        bars += f'<rect x="160" y="{cy}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>'
        bars += f'<text x="155" y="{cy + bar_h//2 + 4}" fill="#94a3b8" font-size="10" text-anchor="end">{name[:26]}</text>'
        bars += f'<text x="{160 + bw + 6:.1f}" y="{cy + bar_h//2 + 4}" fill="#e2e8f0" font-size="10">{views}</text>'

    # Coverage donut segments
    total_cov = sum(c for _, _, c in sections) / len(sections)
    # Build donut arcs for each section
    def arc_path(cx, cy, r, start_deg, end_deg):
        s = math.radians(start_deg - 90)
        e = math.radians(end_deg - 90)
        x1, y1 = cx + r * math.cos(s), cy + r * math.sin(s)
        x2, y2 = cx + r * math.cos(e), cy + r * math.sin(e)
        large = 1 if (end_deg - start_deg) > 180 else 0
        return f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z"

    donut_svgs = ""
    colors_donut = ["#38bdf8","#818cf8","#34d399","#f59e0b","#f472b6","#a78bfa","#22d3ee","#fb923c"]
    angle = 0
    for i, (name, views, cov) in enumerate(sections):
        slice_angle = 360 / len(sections)
        donut_svgs += f'<path d="{arc_path(90, 90, 70, angle, angle + slice_angle)}" fill="{colors_donut[i]}" opacity="0.85" stroke="#0f172a" stroke-width="2"/>'
        angle += slice_angle
    # inner cutout
    donut_svgs += '<circle cx="90" cy="90" r="40" fill="#1e293b"/>'
    donut_svgs += f'<text x="90" y="86" fill="#e2e8f0" font-size="13" font-weight="700" text-anchor="middle">{total_cov:.0f}%</text>'
    donut_svgs += '<text x="90" y="102" fill="#94a3b8" font-size="9" text-anchor="middle">avg coverage</text>'

    # Search activity sparkline: rolling 30-day queries
    spark_pts = []
    base = 80
    for i in range(30):
        base += random.uniform(-8, 10)
        base = max(20, min(200, base))
        spark_pts.append(base)
    sp_max = max(spark_pts)
    sp_min = min(spark_pts)
    spark_d = " ".join([f"{'M' if i == 0 else 'L'}{20 + i * 13},{100 - (spark_pts[i] - sp_min) / (sp_max - sp_min) * 70:.1f}" for i in range(30)])
    # Area fill
    area_d = spark_d + f" L{20+29*13} 100 L20 100 Z"

    # Recent activity feed
    activities = [
        ("2026-03-30 14:22", "Updated",  "GR00T N1.6 API Reference",   "v3.2.1"),
        ("2026-03-30 11:05", "Created",  "DAgger Training Cookbook",   "v1.0.0"),
        ("2026-03-29 16:44", "Reviewed", "OCI Deployment Guide",        "v2.1.0"),
        ("2026-03-29 09:30", "Updated",  "Fine-Tuning Pipeline",        "v4.0.2"),
        ("2026-03-28 17:15", "Deprecated","Legacy ROS Bridge",          "v1.9.0"),
    ]
    badge_color = {"Updated": "#1d4ed8", "Created": "#166534", "Reviewed": "#6b21a8", "Deprecated": "#7f1d1d"}
    badge_text = {"Updated": "#93c5fd", "Created": "#86efac", "Reviewed": "#d8b4fe", "Deprecated": "#fca5a5"}
    feed_rows = ""
    for ts, action, doc, ver in activities:
        bc = badge_color.get(action, "#334155")
        bt = badge_text.get(action, "#e2e8f0")
        feed_rows += f"""<tr style='border-bottom:1px solid #1e293b'>
          <td style='padding:8px 12px;color:#64748b;font-size:0.8rem'>{ts}</td>
          <td style='padding:8px 12px'><span style='background:{bc};color:{bt};padding:2px 8px;border-radius:10px;font-size:0.75rem'>{action}</span></td>
          <td style='padding:8px 12px;color:#e2e8f0;font-size:0.85rem'>{doc}</td>
          <td style='padding:8px 12px;color:#94a3b8;font-size:0.8rem'>{ver}</td>
        </tr>"""

    total_docs = 142
    open_issues = 17
    contributors = 8
    total_views = sum(v for _, v, _ in sections)

    return f"""<!DOCTYPE html><html><head><title>Technical Documentation Hub</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.row{{display:flex;flex-wrap:wrap;gap:12px}}
.stat{{background:#0f172a;padding:12px 18px;border-radius:6px;text-align:center;min-width:110px;flex:1}}
.stat .val{{font-size:1.6rem;font-weight:700;color:#22d3ee}}.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:2px}}
table{{border-collapse:collapse;width:100%}}
th{{text-align:left;padding:8px 12px;color:#64748b;font-size:0.8rem;border-bottom:1px solid #334155}}
</style></head>
<body>
<h1>Technical Documentation Hub</h1>
<p style="color:#94a3b8;margin-top:0">OCI Robot Cloud — Docs portal &amp; analytics | Port {PORT}</p>

<div class="row">
  <div class="stat"><div class="val">{total_docs}</div><div class="lbl">Total Documents</div></div>
  <div class="stat"><div class="val">{total_views}</div><div class="lbl">Total Views (7d)</div></div>
  <div class="stat"><div class="val">{total_cov:.0f}%</div><div class="lbl">Avg Coverage</div></div>
  <div class="stat"><div class="val">{open_issues}</div><div class="lbl">Open Issues</div></div>
  <div class="stat"><div class="val">{contributors}</div><div class="lbl">Contributors</div></div>
</div>

<div class="row" style="margin-top:4px">
  <div class="card" style="flex:2;min-width:300px">
    <h2>Document Views (7-day, by section)</h2>
    <svg width="100%" height="{bar_svg_h}" style="background:#0f172a;border-radius:6px">
      {bars}
    </svg>
    <div style="margin-top:8px;font-size:0.75rem;color:#64748b">
      <span style="color:#38bdf8">■</span> &ge;80% coverage &nbsp;
      <span style="color:#f59e0b">■</span> 65–79% &nbsp;
      <span style="color:#ef4444">■</span> &lt;65%
    </div>
  </div>

  <div style="display:flex;flex-direction:column;gap:12px;flex:1;min-width:200px">
    <div class="card">
      <h2>Coverage by Section</h2>
      <svg width="180" height="180" style="background:#0f172a;border-radius:6px;display:block;margin:auto">
        {donut_svgs}
      </svg>
    </div>
    <div class="card">
      <h2>Search Queries (30d)</h2>
      <svg width="100%" height="110" style="background:#0f172a;border-radius:6px">
        <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="{area_d}" fill="url(#sg)"/>
        <path d="{spark_d}" fill="none" stroke="#38bdf8" stroke-width="2"/>
        <line x1="20" y1="100" x2="410" y2="100" stroke="#334155" stroke-width="1"/>
        <text x="20" y="112" fill="#64748b" font-size="9">30d ago</text>
        <text x="370" y="112" fill="#64748b" font-size="9">today</text>
      </svg>
    </div>
  </div>
</div>

<div class="card">
  <h2>Recent Activity</h2>
  <table>
    <tr>{"<th>Timestamp</th><th>Action</th><th>Document</th><th>Version</th>"}</tr>
    {feed_rows}
  </table>
</div>

<div class="card">
  <h2>Quick Links</h2>
  <div class="row">
    {''.join(f"<div style='background:#0f172a;padding:10px 16px;border-radius:6px;font-size:0.85rem;color:#38bdf8;min-width:160px'>&#128196; {name}</div>" for name, _, _ in sections[:6])}
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Technical Documentation Hub")
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
