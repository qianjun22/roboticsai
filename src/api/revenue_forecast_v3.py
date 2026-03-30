"""Revenue Forecast V3 — FastAPI port 8891"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8891

def run_monte_carlo(n=1000, seed=7):
    rng = random.Random(seed)
    months = 9  # Apr-Dec 2026
    scenarios = []
    for _ in range(n):
        growth = rng.gauss(0.18, 0.07)
        base = 60.0
        arr = base
        for m in range(months):
            arr *= (1 + growth / 12 + rng.gauss(0, 0.03))
        scenarios.append(round(arr, 2))
    scenarios.sort()
    def pct(p): return scenarios[int(p * n / 100)]
    return {
        "p10": pct(10), "p25": pct(25), "p50": pct(50),
        "p75": pct(75), "p90": pct(90),
        "mean": round(sum(scenarios) / n, 2),
        "scenarios": scenarios,
    }

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    mc = run_monte_carlo()
    # Fan chart: 5 percentile bands as horizontal bars
    fan_svg = ""
    labels = [("p10", mc["p10"], "#1e40af"), ("p25", mc["p25"], "#0ea5e9"),
              ("p50", mc["p50"], "#22c55e"), ("p75", mc["p75"], "#f59e0b"), ("p90", mc["p90"], "#ef4444")]
    for idx, (lbl, val, color) in enumerate(labels):
        bar_w = int(val / 3)
        fan_svg += f'<rect x="80" y="{20+idx*30}" width="{bar_w}" height="20" fill="{color}" rx="3"/>'
        fan_svg += f'<text x="10" y="{35+idx*30}" fill="#e2e8f0" font-size="12">{lbl}</text>'
        fan_svg += f'<text x="{85+bar_w}" y="{35+idx*30}" fill="#e2e8f0" font-size="12">${val}k</text>'
    # Sensitivity table
    sens_rows = ""
    factors = [("design partner count", "+$18k/partner"), ("avg deal size", "+$12k/10%"),
               ("churn rate", "-$22k/+1%"), ("upsell rate", "+$15k/+5%")]
    for f, impact in factors:
        sens_rows += f"<tr><td>{f}</td><td>{impact}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Revenue Forecast V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 12px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a}}</style></head>
<body><h1>Revenue Forecast V3</h1>
<div class="card"><h2>Monte Carlo ARR Forecast — 1,000 Scenarios (Dec 2026)</h2>
<svg width="550" height="175">{fan_svg}</svg>
<p>p50 Dec 2026 = <strong>${mc['p50']}k ARR</strong> | Mean = ${mc['mean']}k | p10=${mc['p10']}k | p90=${mc['p90']}k | Scenarios: 1,000</p>
</div>
<div class="card"><h2>Revenue Sensitivity Analysis</h2>
<table><tr><th>Driver</th><th>ARR Impact</th></tr>{sens_rows}</table>
</div>
<div class="card"><h2>Signal Trace</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Forecast V3")
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
