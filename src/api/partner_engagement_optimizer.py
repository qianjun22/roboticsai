"""Partner Engagement Optimizer — FastAPI port 8837"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8837

# Simulated partner dataset (engagement_score, revenue_k, at_risk)
random.seed(42)
_PARTNERS = [
    {"name": f"Partner-{i+1:02d}",
     "engagement": round(random.uniform(0.55, 0.98), 3),
     "revenue_k":  round(random.uniform(8, 80), 1),
     "at_risk":    False}
    for i in range(18)
] + [
    {"name": f"AtRisk-{i+1:02d}",
     "engagement": round(random.uniform(0.20, 0.42), 3),
     "revenue_k":  round(random.uniform(20, 100), 1),
     "at_risk":    True}
    for i in range(5)
]

random.seed()  # re-seed for any runtime use

def _svg_scatter():
    W, H, PL, PR, PT, PB = 560, 280, 55, 20, 20, 40
    cw = W - PL - PR
    ch = H - PT - PB

    # x = engagement (0.15 .. 1.0), y = revenue_k (0 .. 110)
    def px(e): return PL + (e - 0.15) / 0.85 * cw
    def py(r): return PT + ch - r / 110 * ch

    dots = ""
    for p in _PARTNERS:
        cx = px(p["engagement"])
        cy = py(p["revenue_k"])
        color = "#f87171" if p["at_risk"] else "#38bdf8"
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}" opacity="0.85"><title>{p["name"]}: eng={p["engagement"]}, rev=${p["revenue_k"]}K</title></circle>\n'

    # Axis ticks
    x_ticks = "".join(
        f'<text x="{px(v):.1f}" y="{H-PB+14}" text-anchor="middle" font-size="9" fill="#94a3b8">{v:.1f}</text>'
        for v in [0.2, 0.4, 0.6, 0.8, 1.0]
    )
    y_ticks = "".join(
        f'<text x="{PL-6}" y="{py(v)+3:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">${v}K</text>'
        for v in [0, 25, 50, 75, 100]
    )

    return f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>
  <!-- Axes -->
  <line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+ch}" stroke="#334155" stroke-width="1"/>
  <line x1="{PL}" y1="{PT+ch}" x2="{PL+cw}" y2="{PT+ch}" stroke="#334155" stroke-width="1"/>
  {x_ticks}
  {y_ticks}
  <!-- Axis labels -->
  <text x="{PL+cw//2}" y="{H-4}" text-anchor="middle" font-size="10" fill="#94a3b8">Engagement Score</text>
  <text x="14" y="{PT+ch//2}" text-anchor="middle" font-size="10" fill="#94a3b8"
        transform="rotate(-90,14,{PT+ch//2})">Revenue ($K)</text>
  <!-- Risk threshold line -->
  <line x1="{px(0.45):.1f}" y1="{PT}" x2="{px(0.45):.1f}" y2="{PT+ch}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="{px(0.45)+4:.1f}" y="{PT+12}" font-size="9" fill="#f59e0b">Risk threshold</text>
  <!-- Scatter dots -->
  {dots}
  <!-- Legend -->
  <circle cx="{PL+10}" cy="{PT+6}" r="5" fill="#38bdf8"/>
  <text x="{PL+20}" y="{PT+10}" font-size="9" fill="#e2e8f0">Healthy (18)</text>
  <circle cx="{PL+100}" cy="{PT+6}" r="5" fill="#f87171"/>
  <text x="{PL+110}" y="{PT+10}" font-size="9" fill="#e2e8f0">At-Risk (5)</text>
</svg>"""

_NBA_RULES = [
    (0.80, "Schedule executive business review"),
    (0.60, "Assign dedicated partner success manager"),
    (0.45, "Trigger 30-day re-engagement playbook"),
    (0.00, "Escalate to VP — churn risk imminent"),
]

def _nba(engagement: float) -> str:
    for threshold, action in _NBA_RULES:
        if engagement >= threshold:
            return action
    return _NBA_RULES[-1][1]

def build_html():
    chart = _svg_scatter()
    at_risk_rev = sum(p["revenue_k"] for p in _PARTNERS if p["at_risk"])
    rows = "".join(
        f"<tr><td>{p['name']}</td><td>{p['engagement']:.2f}</td>"
        f"<td>${p['revenue_k']}K</td>"
        f"<td style='color:{'#f87171' if p['at_risk'] else '#4ade80'}'>"
        f"{'At-Risk' if p['at_risk'] else 'Healthy'}</td>"
        f"<td style='font-size:0.82rem'>{_nba(p['engagement'])}</td></tr>"
        for p in sorted(_PARTNERS, key=lambda x: x["engagement"])
    )
    return f"""<!DOCTYPE html><html><head><title>Partner Engagement Optimizer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px}}
.metric{{background:#1e293b;padding:16px;border-radius:8px;text-align:center}}
.metric .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.8rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{color:#94a3b8;border-bottom:1px solid #334155;padding:6px 8px;text-align:left}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}</style></head>
<body>
<h1 style="margin:16px 10px">Partner Engagement Optimizer</h1>
<p style="margin:0 10px 12px;color:#94a3b8">Tracks partner health scores and recommends next best actions (NBA) for partner success teams.</p>
<div class="grid">
  <div class="metric"><div class="val">18</div><div class="lbl">High-Health Partners</div></div>
  <div class="metric"><div class="val" style="color:#f87171">5</div><div class="lbl">At-Risk Partners</div></div>
  <div class="metric"><div class="val" style="color:#f59e0b">${at_risk_rev:.0f}K</div><div class="lbl">Revenue at Risk</div></div>
</div>
<div class="card">
  <h2>Partner Engagement vs. Revenue</h2>
  {chart}
</div>
<div class="card">
  <h2>Partner Health Table &amp; Next Best Actions</h2>
  <table>
    <thead><tr><th>Partner</th><th>Engagement</th><th>Revenue</th><th>Status</th><th>Next Best Action</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div class="card" style="font-size:0.85rem;color:#94a3b8">
  Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud — Partner Success Suite
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Engagement Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        at_risk_rev = sum(p["revenue_k"] for p in _PARTNERS if p["at_risk"])
        return {
            "high_health_partners": 18,
            "at_risk_partners": 5,
            "revenue_at_risk_k": round(at_risk_rev, 1),
            "total_partners": len(_PARTNERS),
        }

    @app.get("/partners")
    def partners():
        return [{**p, "next_best_action": _nba(p["engagement"])} for p in _PARTNERS]

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
