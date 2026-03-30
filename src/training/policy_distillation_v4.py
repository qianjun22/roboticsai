"""Policy Distillation V4 — FastAPI port 8870"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8870

def build_html():
    # Generate distillation loss curve (decreasing) and KL divergence metrics
    distillation_loss = [round(2.0 * math.exp(-i / 3.0) + random.uniform(0.0, 0.15), 3) for i in range(10)]
    kl_divergence = [round(1.5 * math.exp(-i / 4.0) + random.uniform(0.0, 0.1), 3) for i in range(10)]
    student_accuracy = [round(min(0.95, 0.4 + i * 0.06 + random.uniform(0.0, 0.03)), 3) for i in range(10)]

    loss_bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="14" height="{int(v*60)}" fill="#C74634"/>'
        for i, v in enumerate(distillation_loss)
    )
    kl_bars = "".join(
        f'<rect x="{44+i*40}" y="{150-int(v*60)}" width="14" height="{int(v*60)}" fill="#38bdf8"/>'
        for i, v in enumerate(kl_divergence)
    )

    return f"""<!DOCTYPE html><html><head><title>Policy Distillation V4</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:8px 16px;text-align:center}}.metric span{{display:block;font-size:1.6em;font-weight:bold;color:#C74634}}</style></head>
<body><h1>Policy Distillation V4</h1>
<p style="padding:0 10px;color:#94a3b8">Knowledge distillation from teacher to student policy — compressing large teacher models into efficient student networks.</p>
<div class="card"><h2>Distillation Loss &amp; KL Divergence (last 10 steps)</h2>
<svg width="450" height="180">{loss_bars}{kl_bars}
<text x="30" y="170" fill="#C74634" font-size="11">Loss</text>
<text x="80" y="170" fill="#38bdf8" font-size="11">KL Div</text>
</svg>
<p>Distillation Loss: {distillation_loss[-1]} | KL Divergence: {kl_divergence[-1]} | Student Accuracy: {student_accuracy[-1]*100:.1f}% | Port: {PORT}</p>
</div>
<div class="card"><h2>Live Metrics</h2>
<div class="metric"><span>{distillation_loss[-1]}</span>Distill Loss</div>
<div class="metric"><span>{kl_divergence[-1]}</span>KL Divergence</div>
<div class="metric"><span>{student_accuracy[-1]*100:.1f}%</span>Student Accuracy</div>
<div class="metric"><span>{min(distillation_loss)}</span>Best Loss</div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Distillation V4")
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
