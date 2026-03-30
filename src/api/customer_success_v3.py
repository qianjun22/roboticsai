"""Customer Success V3 — FastAPI port 8873"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8873

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    return f"""<!DOCTYPE html><html><head><title>Customer Success V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.85em}}
.green{{background:#14532d;color:#86efac}}.yellow{{background:#713f12;color:#fde68a}}.red{{background:#7f1d1d;color:#fca5a5}}</style></head>
<body><h1>Customer Success V3</h1>
<div class="card"><h2>Customer Health Scores</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Design Partner Dashboard</h2>
<table>
<tr><th>Partner</th><th>Health Score</th><th>MRR</th><th>Usage (API calls/mo)</th><th>Status</th></tr>
<tr><td>Acme Robotics</td><td>94</td><td>$2,400</td><td>142,800</td><td><span class="badge green">HEALTHY</span></td></tr>
<tr><td>NovaMech Labs</td><td>78</td><td>$1,800</td><td>89,200</td><td><span class="badge green">HEALTHY</span></td></tr>
<tr><td>SynTech AI</td><td>61</td><td>$1,200</td><td>44,100</td><td><span class="badge yellow">AT RISK</span></td></tr>
<tr><td>FuturaBots</td><td>88</td><td>$955</td><td>67,500</td><td><span class="badge green">HEALTHY</span></td></tr>
<tr><td>OmniArm Inc</td><td>42</td><td>$0</td><td>3,200</td><td><span class="badge red">CHURN RISK</span></td></tr>
</table></div>
<div class="card"><h2>Revenue Pipeline Summary</h2>
<p>Active MRR: <strong>$6,355</strong> | Pipeline (90-day): <strong>$18,400</strong> | Avg Health Score: <strong>72.6</strong></p>
<p>3 partners healthy, 1 at-risk (requires QBR), 1 churn risk (escalation initiated). Tracking satisfaction, usage trends, and expansion signals.</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Success V3")
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
