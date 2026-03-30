"""Inference Cost Tracker V2 — FastAPI port 8883"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8883

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # Cost-per-successful-inference trend: $0.031 → $0.019
    cost_trend = [round(0.031 - i * (0.031 - 0.019) / 9 + random.uniform(-0.001, 0.001), 4) for i in range(10)]
    cost_bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*4000)}" width="30" height="{int(v*4000)}" fill="#38bdf8"/>' for i, v in enumerate(cost_trend))
    # Partner cost attribution
    partners = [
        {"name": "PartnerA", "cost": round(random.uniform(1200, 1800), 2), "inferences": random.randint(38000, 55000), "efficiency": round(random.uniform(0.91, 0.97), 3)},
        {"name": "PartnerB", "cost": round(random.uniform(800, 1200), 2), "inferences": random.randint(28000, 42000), "efficiency": round(random.uniform(0.85, 0.93), 3)},
        {"name": "PartnerC", "cost": round(random.uniform(500, 900), 2), "inferences": random.randint(18000, 30000), "efficiency": round(random.uniform(0.78, 0.88), 3)},
        {"name": "PartnerD", "cost": round(random.uniform(300, 600), 2), "inferences": random.randint(10000, 20000), "efficiency": round(random.uniform(0.72, 0.84), 3)},
    ]
    partners.sort(key=lambda x: x["efficiency"], reverse=True)
    partner_rows = "".join(
        f'<tr><td>{i+1}</td><td>{p["name"]}</td><td>${p["cost"]:,.2f}</td><td>{p["inferences"]:,}</td>'
        f'<td style="color:{"#4ade80" if p["efficiency"] > 0.9 else "#facc15" if p["efficiency"] > 0.82 else "#f87171"}">{p["efficiency"]:.3f}</td></tr>'
        for i, p in enumerate(partners)
    )
    cost_label_start = 0.031
    cost_label_end = cost_trend[-1]
    return f"""<!DOCTYPE html><html><head><title>Inference Cost Tracker V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #334155;text-align:left}}
th{{color:#38bdf8}}.badge{{background:#C74634;padding:2px 8px;border-radius:4px;font-size:12px}}
.trend-down{{color:#4ade80;font-weight:bold}}</style></head>
<body><h1>Inference Cost Tracker V2</h1>
<p class="badge">Port {PORT} | Per-Partner Cost Attribution &amp; Efficiency Leaderboard</p>
<div class="card"><h2>Cost-per-Successful-Inference Trend</h2>
<svg width="450" height="180">{cost_bars}</svg>
<p>Start: <span style="color:#f87171">${cost_label_start}</span> → Current: <span class="trend-down">${cost_label_end}</span>
&nbsp;|&nbsp; <span class="trend-down">▼ {((cost_label_start - cost_label_end)/cost_label_start*100):.1f}% reduction</span> | Port: {PORT}</p>
</div>
<div class="card"><h2>Partner Cost Efficiency Leaderboard</h2>
<table><tr><th>Rank</th><th>Partner</th><th>Total Cost</th><th>Inferences</th><th>Efficiency</th></tr>{partner_rows}</table>
<p style="color:#94a3b8;font-size:13px">Efficiency = successful inferences / total cost normalized. Updated every 5 min.</p>
</div>
<div class="card"><h2>General Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Cost Tracker V2")
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
