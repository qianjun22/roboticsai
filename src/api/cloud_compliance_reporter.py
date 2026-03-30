"""Cloud Compliance Reporter — FastAPI port 8761"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8761

def build_html():
    random.seed(99)

    # Compliance frameworks and their scores
    frameworks = [
        ("SOC 2 Type II",  round(91 + random.uniform(-2, 3), 1)),
        ("ISO 27001",       round(88 + random.uniform(-2, 3), 1)),
        ("NIST CSF",        round(84 + random.uniform(-3, 4), 1)),
        ("GDPR",            round(95 + random.uniform(-1, 2), 1)),
        ("HIPAA",           round(79 + random.uniform(-2, 3), 1)),
        ("PCI-DSS",         round(86 + random.uniform(-2, 2), 1)),
        ("FedRAMP",         round(72 + random.uniform(-3, 4), 1)),
        ("CIS Benchmarks",  round(90 + random.uniform(-2, 2), 1)),
    ]
    overall = round(sum(s for _, s in frameworks) / len(frameworks), 1)

    # Build horizontal bar chart SVG
    bar_svg_w, bar_h, bar_gap = 480, 22, 8
    bar_svg_h = len(frameworks) * (bar_h + bar_gap) + 20
    bars = []
    for i, (name, score) in enumerate(frameworks):
        y = 10 + i * (bar_h + bar_gap)
        bar_len = int((score / 100) * 280)
        color = "#4ade80" if score >= 90 else "#facc15" if score >= 80 else "#f87171"
        bars.append(
            f'<text x="145" y="{y + bar_h - 6}" text-anchor="end" font-size="11" fill="#94a3b8">{name}</text>'
            f'<rect x="150" y="{y}" width="{bar_len}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>'
            f'<text x="{150 + bar_len + 6}" y="{y + bar_h - 6}" font-size="11" fill="#e2e8f0">{score}%</text>'
        )

    # Risk trend over 12 months (rolling average)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    risk_scores = [round(38 + 20 * abs(math.sin(i * 0.6 + 1.2)) + random.uniform(-3, 3), 1) for i in range(12)]
    trend_svg_w, trend_svg_h = 460, 110
    x_step = (trend_svg_w - 60) // 11
    trend_pts = [
        f"{35 + i * x_step},{trend_svg_h - 20 - int(risk_scores[i] / 70 * (trend_svg_h - 35))}"
        for i in range(12)
    ]
    trend_area = f'M {trend_pts[0]} ' + ' '.join(f'L {p}' for p in trend_pts[1:]) \
                 + f' L {35 + 11*x_step},{trend_svg_h-20} L 35,{trend_svg_h-20} Z'
    month_labels = ''.join(
        f'<text x="{35 + i*x_step}" y="{trend_svg_h-4}" text-anchor="middle" font-size="9" fill="#64748b">{months[i]}</text>'
        for i in range(12)
    )
    trend_dots = ''.join(
        f'<circle cx="{35+i*x_step}" cy="{int(trend_pts[i].split(",")[1])}" r="3" fill="#f97316"/>'
        for i in range(12)
    )

    # Open findings by severity
    severities = [("Critical", random.randint(1, 4), "#ef4444"),
                  ("High",     random.randint(5, 14), "#f97316"),
                  ("Medium",   random.randint(18, 35), "#facc15"),
                  ("Low",      random.randint(40, 80), "#4ade80")]
    total_findings = sum(c for _, c, _ in severities)

    # Donut chart for findings
    donut_r, cx, cy = 55, 80, 70
    donut_parts = []
    start_angle = -math.pi / 2
    for label, count, color in severities:
        angle = 2 * math.pi * count / total_findings
        end_angle = start_angle + angle
        x1 = cx + donut_r * math.cos(start_angle)
        y1 = cy + donut_r * math.sin(start_angle)
        x2 = cx + donut_r * math.cos(end_angle)
        y2 = cy + donut_r * math.sin(end_angle)
        large = 1 if angle > math.pi else 0
        ir = donut_r - 20
        ix1 = cx + ir * math.cos(start_angle)
        iy1 = cy + ir * math.sin(start_angle)
        ix2 = cx + ir * math.cos(end_angle)
        iy2 = cy + ir * math.sin(end_angle)
        path = (f'M {x1:.1f},{y1:.1f} A {donut_r},{donut_r} 0 {large},1 {x2:.1f},{y2:.1f} '
                f'L {ix2:.1f},{iy2:.1f} A {ir},{ir} 0 {large},0 {ix1:.1f},{iy1:.1f} Z')
        donut_parts.append(f'<path d="{path}" fill="{color}" opacity="0.88"/>')
        start_angle = end_angle

    legend_items = ''.join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0">'
        f'<span style="display:inline-block;width:12px;height:12px;background:{c};border-radius:2px"></span>'
        f'<span style="color:#94a3b8;font-size:0.82rem">{l}: <strong style="color:#e2e8f0">{n}</strong></span></div>'
        for l, n, c in severities
    )

    # Control categories table
    controls = [
        ("Access Control",       random.randint(92,99), random.randint(0,2)),
        ("Data Encryption",      random.randint(97,100), 0),
        ("Network Security",     random.randint(85,94), random.randint(1,4)),
        ("Incident Response",    random.randint(80,92), random.randint(1,5)),
        ("Vulnerability Mgmt",   random.randint(75,88), random.randint(3,8)),
        ("Audit Logging",        random.randint(93,99), random.randint(0,2)),
        ("Change Management",    random.randint(82,92), random.randint(1,4)),
        ("Vendor Risk",          random.randint(70,85), random.randint(2,6)),
    ]
    ctrl_rows = ''.join(
        f'<tr>'
        f'<td style="color:#94a3b8">{name}</td>'
        f'<td><div style="background:#0f172a;border-radius:4px;height:14px;width:120px">'
        f'<div style="background:{"#4ade80" if pct>=90 else "#facc15" if pct>=80 else "#f87171"};'
        f'width:{pct}%;height:100%;border-radius:4px"></div></div></td>'
        f'<td style="color:#e2e8f0;font-size:0.82rem">{pct}%</td>'
        f'<td style="color:{"#4ade80" if gaps==0 else "#f97316"}">{gaps}</td>'
        f'</tr>'
        for name, pct, gaps in controls
    )

    return f"""<!DOCTYPE html><html><head><title>Cloud Compliance Reporter</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:16px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px}}
table{{border-collapse:collapse;width:100%;font-size:0.83rem}}
th{{color:#64748b;font-weight:600;padding:6px 10px;border-bottom:1px solid #334155;text-align:left}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
.stat{{font-size:2rem;font-weight:700;color:#C74634}}
.sub{{font-size:0.78rem;color:#64748b;margin-top:2px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:600}}
</style></head>
<body>
<h1>Cloud Compliance Reporter</h1>
<p style="color:#64748b;margin:0">OCI Robot Cloud — Regulatory &amp; Security Posture | Port {PORT} | 2026-03-30</p>

<div class="grid3" style="margin-top:16px">
  <div class="card"><div class="stat">{overall}%</div><div class="sub">Overall Score</div></div>
  <div class="card"><div class="stat" style="color:#4ade80">{sum(1 for _,s in frameworks if s>=90)}</div><div class="sub">Passing Frameworks</div></div>
  <div class="card"><div class="stat" style="color:#f97316">{total_findings}</div><div class="sub">Open Findings</div></div>
  <div class="card"><div class="stat" style="color:#38bdf8">99.94%</div><div class="sub">Uptime SLA</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Framework Scores</h2>
    <svg width="{bar_svg_w}" height="{bar_svg_h}" style="display:block">
      {''.join(bars)}
      <line x1="150" y1="0" x2="150" y2="{bar_svg_h}" stroke="#334155" stroke-width="1"/>
      <line x1="150" y1="{bar_svg_h-5}" x2="430" y2="{bar_svg_h-5}" stroke="#334155" stroke-width="1"/>
      <text x="150" y="{bar_svg_h}" font-size="9" fill="#475569">0%</text>
      <text x="290" y="{bar_svg_h}" font-size="9" fill="#475569">50%</text>
      <text x="420" y="{bar_svg_h}" font-size="9" fill="#475569">100%</text>
    </svg>
  </div>
  <div class="card">
    <h2>Open Findings by Severity</h2>
    <div style="display:flex;align-items:center;gap:20px">
      <svg width="160" height="140" style="display:block">
        {''.join(donut_parts)}
        <text x="{cx}" y="{cy+5}" text-anchor="middle" font-size="13" font-weight="700" fill="#e2e8f0">{total_findings}</text>
        <text x="{cx}" y="{cy+18}" text-anchor="middle" font-size="9" fill="#64748b">total</text>
      </svg>
      <div>{legend_items}</div>
    </div>
    <div style="margin-top:8px">
      {''.join(f"<span class='badge' style='background:{'#7f1d1d' if l=='Critical' else '#431407' if l=='High' else '#3b3000' if l=='Medium' else '#14532d'};color:{c};margin:3px'>{l}: {n}</span>" for l,n,c in severities)}
    </div>
  </div>
</div>

<div class="card">
  <h2>Risk Score Trend — Rolling 12 Months</h2>
  <svg width="{trend_svg_w}" height="{trend_svg_h}" style="display:block">
    <defs>
      <linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f97316" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#f97316" stop-opacity="0.02"/>
      </linearGradient>
    </defs>
    <path d="{trend_area}" fill="url(#rg)"/>
    <polyline points="{' '.join(trend_pts)}" fill="none" stroke="#f97316" stroke-width="2"/>
    {trend_dots}
    {month_labels}
    <text x="5" y="20" font-size="9" fill="#64748b">High</text>
    <text x="5" y="{trend_svg_h-20}" font-size="9" fill="#64748b">Low</text>
    <line x1="30" y1="{trend_svg_h-20}" x2="{trend_svg_w-10}" y2="{trend_svg_h-20}" stroke="#334155" stroke-width="1"/>
  </svg>
</div>

<div class="card">
  <h2>Security Control Categories</h2>
  <table>
    <tr><th>Control Domain</th><th>Coverage</th><th>Score</th><th>Gaps</th></tr>
    {ctrl_rows}
  </table>
</div>

<div style="color:#475569;font-size:0.72rem;margin-top:16px">
  Region: us-ashburn-1 &nbsp;|&nbsp; Tenancy: roboticsai-prod &nbsp;|&nbsp; Last Scan: 2026-03-30T18:42:00Z &nbsp;|&nbsp; Next Audit: 2026-06-01
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cloud Compliance Reporter")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/summary")
    def summary():
        random.seed(99)
        frameworks = [
            ("SOC 2 Type II", round(91 + random.uniform(-2, 3), 1)),
            ("ISO 27001",     round(88 + random.uniform(-2, 3), 1)),
            ("NIST CSF",      round(84 + random.uniform(-3, 4), 1)),
            ("GDPR",          round(95 + random.uniform(-1, 2), 1)),
        ]
        return {"frameworks": [{"name": n, "score": s} for n, s in frameworks]}

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
