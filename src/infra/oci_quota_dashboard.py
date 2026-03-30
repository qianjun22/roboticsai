"""OCI Quota Dashboard — FastAPI port 8881"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8881

RESOURCES = [
    {"name": "A100 GPUs",     "limit": 64,   "unit": "GPUs"},
    {"name": "V100 GPUs",     "limit": 32,   "unit": "GPUs"},
    {"name": "CPU OCPUs",     "limit": 512,  "unit": "OCPUs"},
    {"name": "RAM (TB)",      "limit": 4,    "unit": "TB"},
    {"name": "Block Storage", "limit": 200,  "unit": "TB"},
    {"name": "Object Store",  "limit": 1000, "unit": "TB"},
]

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i / 3) + 1.5, 3) for i in range(10)]
    bars = "".join(
        f'<rect x="{30 + i * 40}" y="{150 - int(v * 60)}" width="30" height="{int(v * 60)}" fill="#C74634"/>'
        for i, v in enumerate(data)
    )
    # Per-resource utilization
    utilization = [{"resource": r["name"], "limit": r["limit"], "unit": r["unit"],
                    "used": round(random.uniform(0.3, 0.95) * r["limit"], 1),
                    "headroom_days": random.randint(5, 90)} for r in RESOURCES]
    util_bars = "".join(
        f'<rect x="{30 + i * 65}" y="{150 - int((u["used"] / u["limit"]) * 120)}" width="50" '
        f'height="{int((u["used"] / u["limit"]) * 120)}" fill="#C74634"/>'
        f'<text x="{55 + i * 65}" y="168" text-anchor="middle" fill="#e2e8f0" font-size="10">{u["resource"].split()[0]}</text>'
        f'<text x="{55 + i * 65}" y="{145 - int((u["used"] / u["limit"]) * 120)}" text-anchor="middle" fill="#fbbf24" font-size="9">{round(u["used"]/u["limit"]*100)}%</text>'
        for i, u in enumerate(utilization)
    )
    return f"""<!DOCTYPE html><html><head><title>OCI Quota Dashboard</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}.warn{{color:#f59e0b}}.ok{{color:#4ade80}}.crit{{color:#f87171}}</style></head>
<body><h1>OCI Quota Dashboard</h1>
<div class="card"><h2>Resource Utilization vs Limits</h2>
<svg width="450" height="180">{util_bars}</svg>
<p>Port: {PORT} | Resources tracked: {len(RESOURCES)}</p>
</div>
<div class="card"><h2>Quota Headroom &amp; Forecast</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current headroom index: {data[-1]} | Peak: {max(data)}</p>
</div>
<div class="card"><h2>Quota Detail Table</h2>
<table><tr><th>Resource</th><th>Used</th><th>Limit</th><th>Unit</th><th>Headroom (days)</th><th>Status</th></tr>
{''.join(f'<tr><td>{u["resource"]}</td><td>{u["used"]}</td><td>{u["limit"]}</td><td>{u["unit"]}</td><td>{u["headroom_days"]}</td><td class="{"crit" if u["used"]/u["limit"]>0.9 else "warn" if u["used"]/u["limit"]>0.7 else "ok"}">{"Critical" if u["used"]/u["limit"]>0.9 else "Warning" if u["used"]/u["limit"]>0.7 else "OK"}</td></tr>' for u in utilization)}
</table></div>
<div class="card"><h2>Limit Increase Requests</h2>
<p>Pending: {random.randint(0,3)} | Approved this month: {random.randint(1,5)} | Auto-trigger threshold: 85%</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Quota Dashboard")
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
