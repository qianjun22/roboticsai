"""Partner Feature Request Tracker — FastAPI port 8899"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8899

FEATURE_REQUESTS = [
    {"name": "streaming DAgger",    "votes": 18, "impact": 9, "effort": 6, "age_days": 14},
    {"name": "bimanual policy",      "votes": 14, "impact": 8, "effort": 9, "age_days": 30},
    {"name": "video fine-tuning",    "votes": 12, "impact": 7, "effort": 7, "age_days": 21},
    {"name": "multi-arm support",    "votes": 9,  "impact": 6, "effort": 8, "age_days": 45},
    {"name": "edge SDK",             "votes": 7,  "impact": 5, "effort": 4, "age_days": 60},
]

def build_html():
    random.seed(99)
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>'
        for i, v in enumerate(data)
    )

    # Priority matrix rows (impact x effort)
    matrix_rows = "".join(
        f'<tr><td style="padding:6px 12px">{r["name"]}</td>'
        f'<td style="padding:6px 12px;text-align:center">{r["votes"]}</td>'
        f'<td style="padding:6px 12px;text-align:center">{r["impact"]}/10</td>'
        f'<td style="padding:6px 12px;text-align:center">{r["effort"]}/10</td>'
        f'<td style="padding:6px 12px;text-align:center">{r["age_days"]}d</td></tr>'
        for r in FEATURE_REQUESTS
    )

    # Age distribution bars
    age_bars = "".join(
        f'<rect x="{30+i*80}" y="{150-r[\"age_days\"]*2}" width="50" height="{r[\"age_days\"]*2}" fill="#38bdf8" opacity="0.8"/>'
        f'<text x="{30+i*80+10}" y="165" fill="#94a3b8" font-size="9">{r[\"name\"][:8]}</text>'
        for i, r in enumerate(FEATURE_REQUESTS)
    )

    total_votes = sum(r["votes"] for r in FEATURE_REQUESTS)
    top = FEATURE_REQUESTS[0]["name"]

    return f"""<!DOCTYPE html><html><head><title>Partner Feature Request Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{text-align:left;padding:6px 12px;border-bottom:1px solid #334155}}</style></head>
<body><h1>Partner Feature Request Tracker</h1>
<div class="card"><h2>Request Volume (rolling 10 periods)</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Priority Matrix — Impact × Effort</h2>
<table><tr><th>Feature</th><th>Votes</th><th>Impact</th><th>Effort</th><th>Age</th></tr>{matrix_rows}</table>
<p style="margin-top:12px">Total votes: {total_votes} | Top request: <strong>{top}</strong></p>
</div>
<div class="card"><h2>Request Age Distribution</h2>
<svg width="470" height="180">{age_bars}</svg>
<p style="color:#94a3b8">Age in days since first submitted by partner</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Feature Request Tracker")
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
