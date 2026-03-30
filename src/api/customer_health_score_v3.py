"""Customer Health Score V3 — FastAPI port 8843"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8843

# Segment data: (name, health_score 0-100, red_flagged, churn_risk_usd)
SEGMENTS = [
    {"name": "Enterprise",    "score": 91, "red_flagged": 0, "churn_risk": 0,       "nps": 62, "usage": 94, "tickets": 2,  "expansion": 85},
    {"name": "Mid-Market",    "score": 78, "red_flagged": 2, "churn_risk": 950000,  "nps": 38, "usage": 71, "tickets": 9,  "expansion": 45},
    {"name": "SMB",           "score": 83, "red_flagged": 1, "churn_risk": 250000,  "nps": 44, "usage": 79, "tickets": 6,  "expansion": 38},
]

AVG_HEALTH  = 84   # overall average
TOTAL_RED   = 3
CHURN_RISK  = 1_200_000


def build_gauge_svg(score: int, label: str) -> str:
    """Semi-circle gauge for a health score 0-100."""
    cx, cy, r = 80, 80, 60
    # Arc: 180 degrees for 0-100
    angle_deg = 180 - (score / 100) * 180   # 180=left(0), 0=right(100)
    angle_rad = math.radians(angle_deg)
    needle_x = cx + r * math.cos(angle_rad)
    needle_y = cy - r * math.sin(angle_rad)

    # Background arc (grey)
    bg_arc = (
        f'<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" '
        f'fill="none" stroke="#334155" stroke-width="14" stroke-linecap="round"/>'
    )
    # Coloured fill arc up to score
    fill_color = "#22c55e" if score >= 80 else ("#eab308" if score >= 60 else "#ef4444")
    end_x = cx + r * math.cos(math.radians(180 - (score / 100) * 180))
    end_y = cy - r * math.sin(math.radians(180 - (score / 100) * 180))
    large = 1 if score > 50 else 0
    fill_arc = (
        f'<path d="M {cx-r} {cy} A {r} {r} 0 {large} 1 {end_x:.2f} {end_y:.2f}" '
        f'fill="none" stroke="{fill_color}" stroke-width="14" stroke-linecap="round"/>'
    )
    needle = f'<line x1="{cx}" y1="{cy}" x2="{needle_x:.2f}" y2="{needle_y:.2f}" stroke="white" stroke-width="2"/>'
    text   = f'<text x="{cx}" y="{cy+18}" fill="{fill_color}" font-size="22" font-weight="bold" text-anchor="middle">{score}</text>'
    sublbl = f'<text x="{cx}" y="{cy+34}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'

    return (
        f'<svg width="160" height="100" xmlns="http://www.w3.org/2000/svg">'
        + bg_arc + fill_arc + needle + text + sublbl
        + "</svg>"
    )


def build_html():
    gauges_html = "".join(
        f"<div style='text-align:center'>"
        f"{build_gauge_svg(seg['score'], seg['name'])}"
        f"<div style='color:#38bdf8;font-size:0.85rem'>{seg['name']}</div>"
        f"{'<div style=color:#ef4444;font-size:0.75rem>RED FLAGGED</div>' if seg['red_flagged'] else ''}"
        f"</div>"
        for seg in SEGMENTS
    )
    rows = "".join(
        f"<tr>"
        f"<td>{s['name']}</td>"
        f"<td style='color:{'#ef4444' if s['score']<80 else '#22c55e'}'>{s['score']}</td>"
        f"<td>{s['nps']}</td>"
        f"<td>{s['usage']}%</td>"
        f"<td>{s['tickets']}</td>"
        f"<td>{s['expansion']}%</td>"
        f"<td style='color:{'#ef4444' if s['red_flagged'] else '#94a3b8'}'>{'YES x'+str(s['red_flagged']) if s['red_flagged'] else 'No'}</td>"
        f"<td>${s['churn_risk']:,}</td>"
        f"</tr>"
        for s in SEGMENTS
    )
    return f"""<!DOCTYPE html><html><head><title>Customer Health Score V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}.metric{{font-size:2rem;font-weight:bold;color:#f97316}}</style></head>
<body>
<h1>Customer Health Score V3</h1>
<div class="card">
  <h2>Overall Metrics</h2>
  <div style="display:flex;gap:30px;flex-wrap:wrap">
    <div><div class="metric" style="color:#22c55e">{AVG_HEALTH}%</div><div>Avg Health Score</div></div>
    <div><div class="metric" style="color:#ef4444">{TOTAL_RED}</div><div>Red-Flagged Customers</div></div>
    <div><div class="metric" style="color:#eab308">${CHURN_RISK/1e6:.1f}M</div><div>Churn Risk Identified</div></div>
    <div><div class="metric" style="color:#38bdf8">{PORT}</div><div>Port</div></div>
  </div>
</div>
<div class="card">
  <h2>Health Score by Segment</h2>
  <div style="display:flex;gap:20px;flex-wrap:wrap;align-items:flex-end">
    {gauges_html}
  </div>
</div>
<div class="card">
  <h2>Segment Detail — V3 Signals</h2>
  <table>
    <tr><th>Segment</th><th>Health</th><th>NPS</th><th>Usage</th><th>Tickets</th><th>Expansion</th><th>Red Flagged</th><th>Churn Risk</th></tr>
    {rows}
  </table>
</div>
<div class="card">
  <h2>Model Version: V3 Enhancements</h2>
  <ul style="color:#94a3b8">
    <li>Added expansion signal weighting (+15% predictive accuracy vs V2)</li>
    <li>NPS decay model: scores older than 90 days discounted by 40%</li>
    <li>Support ticket severity-weighted (P1=5x, P2=2x, P3=1x)</li>
    <li>Usage trend: 30-day rolling slope replaces raw utilisation</li>
  </ul>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Customer Health Score V3")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/scores")
    def scores():
        return {
            "avg_health_score": AVG_HEALTH,
            "red_flagged_count": TOTAL_RED,
            "churn_risk_usd": CHURN_RISK,
            "segments": SEGMENTS,
        }


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
