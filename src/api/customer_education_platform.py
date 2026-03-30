"""Customer Education Platform — FastAPI port 8825"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8825

def build_html():
    random.seed(77)

    # Learner engagement data over 12 weeks
    weeks = list(range(1, 13))
    enrollments  = [12, 19, 27, 34, 41, 38, 45, 52, 60, 58, 67, 74]
    completions  = [8,  14, 20, 27, 32, 30, 37, 44, 50, 48, 56, 63]
    quiz_scores  = [round(62 + w * 1.8 + random.uniform(-2, 2), 1) for w in weeks]

    # Line chart SVG for enrollment / completion trend
    cw, ch = 680, 160
    max_enr = max(enrollments)

    def to_pt(vals, maxv, w, h):
        pts = []
        for i, v in enumerate(vals):
            px = 30 + i * (w - 40) / (len(vals) - 1)
            py = h - 20 - v / maxv * (h - 30)
            pts.append(f"{px:.1f},{py:.1f}")
        return " ".join(pts)

    enr_pts  = to_pt(enrollments, max_enr, cw, ch)
    comp_pts = to_pt(completions, max_enr, cw, ch)

    # Week labels
    xlabels = ""
    for i, w in enumerate(weeks):
        px = 30 + i * (cw - 40) / (len(weeks) - 1)
        xlabels += f'<text x="{px:.1f}" y="{ch - 4}" text-anchor="middle" font-size="9" fill="#64748b">W{w}</text>'

    # Quiz score sparkline (wavy progress)
    qw, qh = 680, 100
    max_q = max(quiz_scores)
    q_pts = to_pt(quiz_scores, max_q, qw, qh)
    q_fill_pts = f"30,{qh-20} " + q_pts + f" {30 + (len(quiz_scores)-1)*(qw-40)/(len(quiz_scores)-1):.1f},{qh-20}"

    # Module completion donut segments
    modules = [
        ("Intro to Robotics AI",    312, "#38bdf8"),
        ("GR00T Fine-Tuning",       247, "#34d399"),
        ("Isaac Sim SDG",           198, "#a78bfa"),
        ("Deployment & Inference",  176, "#f59e0b"),
        ("Safety & Monitoring",     134, "#f87171"),
        ("Advanced DAgger",          89, "#fb923c"),
    ]
    total_learners = sum(m[1] for m in modules)
    donut_cx, donut_cy, donut_r, donut_inner = 160, 160, 130, 75
    start_angle = -math.pi / 2
    donut_segs = ""
    legend_items = ""
    for name, count, color in modules:
        frac = count / total_learners
        sweep = frac * 2 * math.pi
        end_angle = start_angle + sweep
        x1 = donut_cx + donut_r * math.cos(start_angle)
        y1 = donut_cy + donut_r * math.sin(start_angle)
        x2 = donut_cx + donut_r * math.cos(end_angle)
        y2 = donut_cy + donut_r * math.sin(end_angle)
        xi1 = donut_cx + donut_inner * math.cos(start_angle)
        yi1 = donut_cy + donut_inner * math.sin(start_angle)
        xi2 = donut_cx + donut_inner * math.cos(end_angle)
        yi2 = donut_cy + donut_inner * math.sin(end_angle)
        large = 1 if sweep > math.pi else 0
        donut_segs += (
            f'<path d="M {xi1:.2f},{yi1:.2f} L {x1:.2f},{y1:.2f} '
            f'A {donut_r},{donut_r} 0 {large},1 {x2:.2f},{y2:.2f} '
            f'L {xi2:.2f},{yi2:.2f} A {donut_inner},{donut_inner} 0 {large},0 {xi1:.2f},{yi1:.2f} Z" '
            f'fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        )
        legend_items += f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0"><div style="width:12px;height:12px;border-radius:3px;background:{color};flex-shrink:0"></div><div style="font-size:0.8rem"><span style="color:#e2e8f0">{name}</span> <span style="color:#64748b">({count})</span></div></div>'
        start_angle = end_angle

    # Heatmap: hours studied per day of week x time of day
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = ["9am", "11am", "1pm", "3pm", "5pm", "7pm", "9pm"]
    cell_w, cell_h = 60, 28
    heatmap_svg = ""
    for di, day in enumerate(days):
        for hi, hr in enumerate(hours):
            val = abs(math.sin(di * 1.3 + hi * 0.9)) * 0.7 + random.uniform(0.05, 0.3)
            val = min(val, 1.0)
            alpha = int(40 + val * 200)
            col = f"#{alpha:02x}{min(alpha+50,255):02x}ff"
            cx_ = 50 + hi * cell_w
            cy_ = 10 + di * cell_h
            heatmap_svg += f'<rect x="{cx_}" y="{cy_}" width="{cell_w-2}" height="{cell_h-2}" fill="{col}" rx="3"/>'
            heatmap_svg += f'<text x="{cx_ + cell_w/2 - 1:.0f}" y="{cy_ + cell_h/2 + 4:.0f}" text-anchor="middle" font-size="9" fill="#e2e8f0">{val:.2f}</text>'
    for hi, hr in enumerate(hours):
        heatmap_svg += f'<text x="{50 + hi * cell_w + cell_w/2 - 1:.0f}" y="8" text-anchor="middle" font-size="9" fill="#64748b">{hr}</text>'
    for di, day in enumerate(days):
        heatmap_svg += f'<text x="44" y="{10 + di * cell_h + cell_h/2 + 4:.0f}" text-anchor="end" font-size="9" fill="#94a3b8">{day}</text>'

    hm_w = 50 + len(hours) * cell_w + 10
    hm_h = 10 + len(days) * cell_h + 10

    # Leaderboard
    learner_rows = ""
    names = ["R. Tanaka", "S. Patel", "L. Müller", "A. Chen", "M. Okafor", "P. Ivanova", "B. Costa", "D. Kim"]
    scores = sorted([round(random.uniform(78, 99), 1) for _ in names], reverse=True)
    medals = ["#f59e0b", "#94a3b8", "#b45309"] + ["#334155"] * 10
    for idx, (name, score) in enumerate(zip(names, scores)):
        bar_pct = score - 70
        learner_rows += f'<tr><td style="color:{medals[idx]};font-weight:700">#{idx+1}</td><td>{name}</td><td><div style="background:#334155;border-radius:4px;height:12px;width:160px"><div style="background:{medals[idx]};height:12px;width:{bar_pct * 5.3:.0f}px;border-radius:4px"></div></div></td><td style="color:#38bdf8;font-weight:600">{score}%</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>Customer Education Platform</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 24px 4px;margin:0;font-size:1.6rem}}
.subtitle{{color:#64748b;padding:0 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 16px 24px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
h2{{color:#38bdf8;margin:0 0 14px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#263348}}
.kpi{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px}}
.kpi-box{{background:#0f172a;border-radius:8px;padding:12px 18px;border:1px solid #334155;min-width:110px}}
.kpi-val{{font-size:1.5rem;font-weight:700;color:#38bdf8}}
.kpi-lbl{{font-size:0.72rem;color:#64748b;margin-top:2px}}
.legend{{display:flex;gap:16px;font-size:0.78rem;margin-bottom:10px}}
.dot{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:5px}}
</style></head>
<body>
<h1>Customer Education Platform</h1>
<div class="subtitle">OCI Robot Cloud — learner engagement, module completion, and skill certification — port {PORT}</div>

<div style="padding:0 16px 12px">
  <div class="kpi">
    <div class="kpi-box"><div class="kpi-val">1,156</div><div class="kpi-lbl">Total Enrollments</div></div>
    <div class="kpi-box"><div class="kpi-val">84.2%</div><div class="kpi-lbl">Completion Rate</div></div>
    <div class="kpi-box"><div class="kpi-val">6</div><div class="kpi-lbl">Active Modules</div></div>
    <div class="kpi-box"><div class="kpi-val">87.4%</div><div class="kpi-lbl">Avg Quiz Score</div></div>
    <div class="kpi-box"><div class="kpi-val">4.7/5</div><div class="kpi-lbl">NPS Score</div></div>
    <div class="kpi-box"><div class="kpi-val">342</div><div class="kpi-lbl">Certifications Issued</div></div>
  </div>
</div>

<div class="grid">
  <div class="card" style="grid-column:span 2">
    <h2>Weekly Enrollment &amp; Completion Trend</h2>
    <div class="legend">
      <span><span class="dot" style="background:#38bdf8"></span>Enrollments</span>
      <span><span class="dot" style="background:#34d399"></span>Completions</span>
    </div>
    <svg width="{cw}" height="{ch}" style="display:block">
      <line x1="30" y1="{ch-20}" x2="{cw}" y2="{ch-20}" stroke="#334155"/>
      <polyline points="{enr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <polyline points="{comp_pts}" fill="none" stroke="#34d399" stroke-width="2" stroke-dasharray="6,3"/>
      {xlabels}
    </svg>
  </div>

  <div class="card">
    <h2>Module Completion Distribution</h2>
    <div style="display:flex;gap:16px;align-items:center">
      <svg width="320" height="320">
        {donut_segs}
        <text x="{donut_cx}" y="{donut_cy - 8}" text-anchor="middle" font-size="18" font-weight="700" fill="#e2e8f0">{total_learners}</text>
        <text x="{donut_cx}" y="{donut_cy + 14}" text-anchor="middle" font-size="11" fill="#64748b">learners</text>
      </svg>
      <div>{legend_items}</div>
    </div>
  </div>

  <div class="card">
    <h2>Avg Quiz Score Progression (12 Weeks)</h2>
    <svg width="{qw}" height="{qh}" style="display:block">
      <defs><linearGradient id="qg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/></linearGradient></defs>
      <polygon points="{q_fill_pts}" fill="url(#qg)"/>
      <polyline points="{q_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <line x1="30" y1="{qh-20}" x2="{qw-10}" y2="{qh-20}" stroke="#334155"/>
    </svg>
    <div style="text-align:right;font-size:0.8rem;color:#64748b">Scores from {quiz_scores[0]}% → {quiz_scores[-1]}%</div>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Study Activity Heatmap (Engagement × Time of Day)</h2>
    <svg width="{hm_w}" height="{hm_h}" style="display:block">
      {heatmap_svg}
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Learner Leaderboard — Top Quiz Performers</h2>
    <table>
      <thead><tr><th>Rank</th><th>Learner</th><th>Progress</th><th>Score</th></tr></thead>
      <tbody>{learner_rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Education Platform")
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
