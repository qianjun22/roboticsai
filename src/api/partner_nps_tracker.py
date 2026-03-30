"""Partner NPS Tracker — FastAPI port 8893"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8893

def build_html():
    # NPS trend: Q4 2025 -> Q1 2026 -> Q2 2026 target
    quarters = ["Q4 2025", "Q1 2026", "Q2 2026 (target)"]
    nps_scores = [47, 61, 72]
    trend_bars = "".join(
        f'<rect x="{30+i*130}" y="{150-int(s*1.5)}" width="80" height="{int(s*1.5)}" fill="#C74634"/>'
        f'<text x="{70+i*130}" y="{165}" text-anchor="middle" fill="#e2e8f0" font-size="11">{q}</text>'
        f'<text x="{70+i*130}" y="{145-int(s*1.5)}" text-anchor="middle" fill="#38bdf8" font-size="12">{s}</text>'
        for i, (q, s) in enumerate(zip(quarters, nps_scores))
    )
    # Partner breakdown: promoter/passive/detractor
    partners = [
        ("Partner A", 55, 30, 15),
        ("Partner B", 62, 28, 10),
        ("Partner C", 48, 35, 17),
        ("Partner D", 70, 22, 8),
    ]
    partner_rows = "".join(
        f'<tr><td style="padding:6px 12px">{name}</td>'
        f'<td style="padding:6px 12px;color:#4ade80">{pro}%</td>'
        f'<td style="padding:6px 12px;color:#facc15">{pas}%</td>'
        f'<td style="padding:6px 12px;color:#f87171">{det}%</td>'
        f'<td style="padding:6px 12px;color:#38bdf8">{pro - det}</td></tr>'
        for name, pro, pas, det in partners
    )
    return f"""<!DOCTYPE html><html><head><title>Partner NPS Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{color:#94a3b8;text-align:left;padding:6px 12px}}</style></head>
<body><h1>Partner NPS Tracker</h1>
<div class="card"><h2>NPS Trend (Quarterly)</h2>
<svg width="450" height="180">{trend_bars}</svg>
<p>Q4 2025: 47 &rarr; Q1 2026: 61 &rarr; Q2 2026 target: 72 | Port: {PORT}</p>
</div>
<div class="card"><h2>Partner Breakdown (Q1 2026)</h2>
<table><thead><tr><th>Partner</th><th>Promoters</th><th>Passives</th><th>Detractors</th><th>NPS</th></tr></thead>
<tbody>{partner_rows}</tbody></table>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner NPS Tracker")
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
