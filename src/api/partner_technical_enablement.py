"""Partner Technical Enablement — FastAPI port 8817"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8817

def build_html():
    random.seed(7)

    # Partner enablement data
    partners = [
        ("Acme Robotics",    "Tier 1", 94, 18, "Active"),
        ("NovaDyn Systems",  "Tier 1", 88, 14, "Active"),
        ("CortexAI Labs",    "Tier 2", 76, 9,  "Active"),
        ("SynapseTech",      "Tier 2", 71, 11, "Active"),
        ("HelixWorks",       "Tier 3", 63, 6,  "Onboarding"),
        ("PrecisionArm Co",  "Tier 3", 58, 5,  "Onboarding"),
        ("FlexBot Inc",      "Tier 2", 82, 13, "Active"),
        ("KinetiCore",       "Tier 3", 45, 3,  "Inactive"),
    ]

    tier_color = {"Tier 1": "#f472b6", "Tier 2": "#38bdf8", "Tier 3": "#a78bfa"}
    status_color = {"Active": "#4ade80", "Onboarding": "#fbbf24", "Inactive": "#94a3b8"}

    partner_rows = "".join(
        f'<tr><td>{p}</td><td style="color:{tier_color[t]}">{t}</td>'
        f'<td><div style="background:#0f172a;border-radius:4px;height:10px;width:120px;display:inline-block">'
        f'<div style="background:{tier_color[t]};width:{score}%;height:10px;border-radius:4px"></div></div> {score}%</td>'
        f'<td>{cases}</td><td style="color:{status_color[st]}">{st}</td></tr>'
        for p, t, score, cases, st in partners
    )

    # Enablement progress over 12 weeks (cumulative partner certifications)
    weeks = list(range(1, 13))
    cert_t1 = [int(2 * (1 - math.exp(-w * 0.35))) for w in weeks]
    cert_t2 = [int(3 * (1 - math.exp(-w * 0.28))) for w in weeks]
    cert_t3 = [int(3 * (1 - math.exp(-w * 0.22))) for w in weeks]

    # Bar chart: weekly new technical workshops run
    workshops = [max(1, int(4 + 3 * math.sin(w * 0.7) + random.uniform(-0.5, 0.5))) for w in weeks]
    bar_max = max(workshops)
    chart_w, chart_h = 540, 120
    bar_w = chart_w // len(workshops)
    bars = ""
    for i, v in enumerate(workshops):
        bh = int(v / bar_max * (chart_h - 20))
        bx = i * bar_w + 4
        by = chart_h - bh - 2
        bars += f'<rect x="{bx}" y="{by}" width="{bar_w-6}" height="{bh}" rx="3" fill="#38bdf8" opacity="0.8"/>'
        bars += f'<text x="{bx + (bar_w-6)//2}" y="{by-4}" text-anchor="middle" font-size="9" fill="#94a3b8">{v}</text>'
        bars += f'<text x="{bx + (bar_w-6)//2}" y="{chart_h+12}" text-anchor="middle" font-size="8" fill="#64748b">W{i+1}</text>'

    # Cumulative cert line chart
    lw, lh = 540, 130
    lpad = 30
    lchw = lw - 2 * lpad
    lchh = lh - 2 * lpad
    lmax = max(cert_t1[-1] + cert_t2[-1] + cert_t3[-1], 1)

    def line_pts(series):
        cumulative = []
        running = 0
        for v in series:
            running += v
            cumulative.append(running)
        pts = []
        for i, v in enumerate(cumulative):
            x = lpad + i * lchw / (len(series) - 1)
            y = lpad + lchh - (v / lmax) * lchh
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    t1_pts = line_pts(cert_t1)
    t2_pts = line_pts(cert_t2)
    t3_pts = line_pts(cert_t3)

    total_partners = len(partners)
    active_count = sum(1 for _, _, _, _, st in partners if st == "Active")
    avg_score = round(sum(s for _, _, s, _, _ in partners) / total_partners, 1)
    total_cases = sum(c for _, _, _, c, _ in partners)

    return f"""<!DOCTYPE html><html><head><title>Partner Technical Enablement</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:1rem;margin:12px 0 8px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px}}
.stat{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.stat .val{{font-size:1.8rem;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:#0f172a;padding:8px;text-align:left;color:#94a3b8;border-bottom:1px solid #334155}}
td{{padding:7px 8px;border-bottom:1px solid #1e293b}}
.badge{{background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:12px;font-size:0.75rem}}
.legend{{display:flex;gap:16px;font-size:0.75rem;margin-bottom:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}}
</style></head>
<body>
<h1>Partner Technical Enablement</h1>
<p style="color:#94a3b8;font-size:0.85rem;margin:0 0 16px 0">OCI Robot Cloud partner readiness, certification tracking, and workshop cadence &nbsp;<span class="badge">Port {PORT}</span></p>

<div class="grid">
  <div class="stat"><div class="val">{total_partners}</div><div class="lbl">Total Partners</div></div>
  <div class="stat"><div class="val">{active_count}</div><div class="lbl">Active Partners</div></div>
  <div class="stat"><div class="val">{avg_score}%</div><div class="lbl">Avg Enablement Score</div></div>
  <div class="stat"><div class="val">{total_cases}</div><div class="lbl">Support Cases Handled</div></div>
</div>

<div class="card">
  <h2>Weekly Technical Workshops Delivered (W1–W12)</h2>
  <svg width="{chart_w}" height="{chart_h+20}" style="background:#0f172a;border-radius:6px;display:block">
    {bars}
    <line x1="0" y1="{chart_h}" x2="{chart_w}" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
  </svg>
</div>

<div class="card">
  <h2>Cumulative Certifications by Tier (12-week ramp)</h2>
  <div class="legend">
    <span><span class="dot" style="background:#f472b6"></span>Tier 1</span>
    <span><span class="dot" style="background:#38bdf8"></span>Tier 2</span>
    <span><span class="dot" style="background:#a78bfa"></span>Tier 3</span>
  </div>
  <svg width="{lw}" height="{lh}" style="background:#0f172a;border-radius:6px;display:block">
    <polyline points="{t1_pts}" fill="none" stroke="#f472b6" stroke-width="2"/>
    <polyline points="{t2_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,3"/>
    <polyline points="{t3_pts}" fill="none" stroke="#a78bfa" stroke-width="2" stroke-dasharray="2,2"/>
    <line x1="{lpad}" y1="{lpad}" x2="{lpad}" y2="{lpad+lchh}" stroke="#334155" stroke-width="1"/>
    <line x1="{lpad}" y1="{lpad+lchh}" x2="{lpad+lchw}" y2="{lpad+lchh}" stroke="#334155" stroke-width="1"/>
    <text x="{lpad-4}" y="{lpad+6}" text-anchor="end" font-size="9" fill="#64748b">{lmax}</text>
    <text x="{lpad-4}" y="{lpad+lchh}" text-anchor="end" font-size="9" fill="#64748b">0</text>
  </svg>
</div>

<div class="card">
  <h2>Partner Enablement Scoreboard</h2>
  <table>
    <tr><th>Partner</th><th>Tier</th><th>Enablement Score</th><th>Cases</th><th>Status</th></tr>
    {partner_rows}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Technical Enablement")
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
