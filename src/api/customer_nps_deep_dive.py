"""Customer NPS Deep Dive — FastAPI port 8691"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8691

def build_html():
    random.seed(42)

    # NPS score history over 12 months
    months = ["Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb"]
    nps_scores = [38 + int(math.sin(i * 0.5) * 10 + random.uniform(-3, 3)) for i in range(12)]
    promoters = [50 + int(random.uniform(-5, 10) + i * 0.8) for i in range(12)]
    passives = [25 + int(random.uniform(-3, 3)) for _ in range(12)]
    detractors = [100 - promoters[i] - passives[i] for i in range(12)]

    # SVG bar chart for NPS trend
    bar_w = 32
    bar_gap = 10
    chart_h = 160
    nps_bars = ""
    for i, score in enumerate(nps_scores):
        x = 30 + i * (bar_w + bar_gap)
        h = max(4, int((score / 70) * chart_h))
        color = "#34d399" if score >= 50 else "#38bdf8" if score >= 35 else "#fb923c"
        nps_bars += f'<rect x="{x}" y="{180-h}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>'
        nps_bars += f'<text x="{x+bar_w//2}" y="{180-h-4}" text-anchor="middle" font-size="9" fill="#94a3b8">{score}</text>'
        nps_bars += f'<text x="{x+bar_w//2}" y="198" text-anchor="middle" font-size="9" fill="#64748b">{months[i]}</text>'

    # Segment breakdown (donut chart approximation as SVG arcs)
    segments = [
        ("Promoters", promoters[-1], "#34d399"),
        ("Passives", passives[-1], "#38bdf8"),
        ("Detractors", detractors[-1], "#f472b6"),
    ]
    total = sum(s[1] for s in segments)
    donut_svg = ""
    cx, cy, r_outer, r_inner = 110, 110, 90, 55
    start_angle = -math.pi / 2
    for label, val, color in segments:
        sweep = 2 * math.pi * val / total
        end_angle = start_angle + sweep
        x1 = cx + r_outer * math.cos(start_angle)
        y1 = cy + r_outer * math.sin(start_angle)
        x2 = cx + r_outer * math.cos(end_angle)
        y2 = cy + r_outer * math.sin(end_angle)
        xi1 = cx + r_inner * math.cos(end_angle)
        yi1 = cy + r_inner * math.sin(end_angle)
        xi2 = cx + r_inner * math.cos(start_angle)
        yi2 = cy + r_inner * math.sin(start_angle)
        large = 1 if sweep > math.pi else 0
        path = (f'M {x1:.2f} {y1:.2f} A {r_outer} {r_outer} 0 {large} 1 {x2:.2f} {y2:.2f} '
                f'L {xi1:.2f} {yi1:.2f} A {r_inner} {r_inner} 0 {large} 0 {xi2:.2f} {yi2:.2f} Z')
        donut_svg += f'<path d="{path}" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        start_angle = end_angle
    donut_svg += f'<text x="{cx}" y="{cy-8}" text-anchor="middle" font-size="13" fill="#e2e8f0" font-weight="bold">{nps_scores[-1]}</text>'
    donut_svg += f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="10" fill="#94a3b8">NPS</text>'

    # Legend for donut
    legend_svg = ""
    for i, (label, val, color) in enumerate(segments):
        pct = round(100 * val / total, 1)
        legend_svg += f'<rect x="240" y="{60+i*36}" width="14" height="14" fill="{color}" rx="3"/>'
        legend_svg += f'<text x="260" y="{72+i*36}" font-size="12" fill="#e2e8f0">{label}</text>'
        legend_svg += f'<text x="260" y="{88+i*36}" font-size="10" fill="#64748b">{val}% respondents ({pct}%)</text>'

    # Verbatim themes (simulated)
    themes = [
        ("Deployment Speed", 87, "+12 vs last quarter", "#34d399"),
        ("API Reliability", 81, "+5 vs last quarter", "#34d399"),
        ("Model Accuracy", 76, "+8 vs last quarter", "#38bdf8"),
        ("Support Response", 68, "-3 vs last quarter", "#fb923c"),
        ("Pricing Clarity", 54, "-7 vs last quarter", "#f472b6"),
        ("Onboarding UX", 61, "+1 vs last quarter", "#38bdf8"),
    ]
    theme_rows = ""
    for name, score, delta, color in themes:
        bar_w_px = int(score * 2.2)
        theme_rows += (
            f"<tr><td style='padding:7px 12px;color:#94a3b8;white-space:nowrap'>{name}</td>"
            f"<td style='padding:7px 12px'>"
            f"<div style='background:#0f172a;border-radius:4px;height:14px;width:220px'>"
            f"<div style='background:{color};height:14px;width:{bar_w_px}px;border-radius:4px'></div></div></td>"
            f"<td style='padding:7px 12px;color:{color};font-size:0.85em'>{score}/100</td>"
            f"<td style='padding:7px 12px;color:#64748b;font-size:0.82em'>{delta}</td></tr>"
        )

    # Cohort retention curve
    cohort_pts = []
    for i in range(50):
        x = 30 + i * 10
        retention = 100 * math.exp(-i / 35) * (1 + 0.05 * math.sin(i * 0.7)) + random.uniform(-1, 1)
        y = 220 - max(0, retention) * 1.8
        cohort_pts.append(f"{x:.1f},{y:.1f}")
    cohort_pts_str = " ".join(cohort_pts)

    return f"""<!DOCTYPE html><html><head><title>Customer NPS Deep Dive</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top}}
.grid{{display:flex;flex-wrap:wrap}}
table{{border-collapse:collapse;width:100%}}
tr:hover{{background:#ffffff08}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.78em;margin-left:6px}}
.ok{{background:#064e3b;color:#34d399}}
.subtitle{{color:#64748b;font-size:0.88em;padding:0 20px 16px}}
.kpi{{font-size:2em;font-weight:bold;color:#38bdf8}}
.kpi-label{{font-size:0.8em;color:#64748b;margin-top:4px}}
.kpi-block{{display:inline-block;margin:0 18px 0 0;text-align:center}}
</style></head>
<body>
<h1>Customer NPS Deep Dive <span class="badge ok">LIVE</span></h1>
<div class="subtitle">Port {PORT} — OCI Robot Cloud customer satisfaction analytics</div>

<div style="padding:0 10px 10px">
  <div class="kpi-block"><div class="kpi">{nps_scores[-1]}</div><div class="kpi-label">Current NPS</div></div>
  <div class="kpi-block"><div class="kpi" style="color:#34d399">{promoters[-1]}%</div><div class="kpi-label">Promoters</div></div>
  <div class="kpi-block"><div class="kpi" style="color:#fb923c">{detractors[-1]}%</div><div class="kpi-label">Detractors</div></div>
  <div class="kpi-block"><div class="kpi" style="color:#a78bfa">{random.randint(180,240)}</div><div class="kpi-label">Responses (Feb)</div></div>
</div>

<div class="grid">

<div class="card">
<h2>NPS Trend (12 Months)</h2>
<svg width="530" height="210" style="display:block">
  <line x1="25" y1="20" x2="25" y2="185" stroke="#334155" stroke-width="1"/>
  <line x1="25" y1="185" x2="520" y2="185" stroke="#334155" stroke-width="1"/>
  {''.join(f'<line x1="25" y1="{y}" x2="520" y2="{y}" stroke="#1e293b" stroke-width="1"/>' for y in range(50,186,45))}
  {nps_bars}
  <text x="0" y="185" font-size="8" fill="#475569">0</text>
  <text x="0" y="140" font-size="8" fill="#475569">25</text>
  <text x="0" y="95" font-size="8" fill="#475569">50</text>
</svg>
</div>

<div class="card">
<h2>Respondent Breakdown</h2>
<svg width="380" height="230" style="display:block">
  {donut_svg}
  {legend_svg}
</svg>
</div>

<div class="card" style="min-width:500px">
<h2>Driver Theme Scores</h2>
<table>{theme_rows}</table>
</div>

<div class="card">
<h2>Customer Retention Curve</h2>
<svg width="530" height="240" style="display:block">
  <line x1="25" y1="20" x2="25" y2="225" stroke="#334155" stroke-width="1"/>
  <line x1="25" y1="225" x2="520" y2="225" stroke="#334155" stroke-width="1"/>
  {''.join(f'<line x1="25" y1="{y}" x2="520" y2="{y}" stroke="#1e293b" stroke-width="1"/>' for y in range(50,226,45))}
  <polyline points="{cohort_pts_str}" fill="none" stroke="#a78bfa" stroke-width="2.5"/>
  <text x="200" y="238" font-size="9" fill="#475569">Days Since Onboarding</text>
  <text x="28" y="30" font-size="9" fill="#94a3b8">100%</text>
  <text x="28" y="225" font-size="9" fill="#94a3b8">0%</text>
</svg>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer NPS Deep Dive")
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
