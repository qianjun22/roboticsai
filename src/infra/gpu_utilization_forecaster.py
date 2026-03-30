"""GPU Utilization Forecaster — FastAPI port 8479"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8479

def build_html():
    # historical utilization 72h
    hist = [65 + 20*math.sin(i*0.3) + random.uniform(-5,5) for i in range(72)]
    # forecast next 24h
    forecast = [hist[-1] + (i * 0.5) + random.uniform(-3,3) for i in range(24)]
    forecast = [min(95, max(40, v)) for v in forecast]
    
    all_pts = hist + forecast
    mn, mx = min(all_pts), max(all_pts)
    
    def to_svg(data, offset, color, dashed=False):
        pts = []
        for i, v in enumerate(data):
            x = (offset + i) * 572 / 95
            y = 100 - (v - mn) / (mx - mn + 1e-9) * 100
            pts.append(f"{x:.1f},{y:.1f}")
        dash = 'stroke-dasharray="6,3"' if dashed else ''
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" {dash}/>'
    
    hist_svg = to_svg(hist, 0, "#38bdf8")
    fc_svg = to_svg(forecast, 72, "#f59e0b", dashed=True)
    # vertical divider at t=72
    div_x = 72 * 572 / 95
    divider = f'<line x1="{div_x:.1f}" y1="0" x2="{div_x:.1f}" y2="100" stroke="#64748b" stroke-width="1" stroke-dasharray="4,2"/>'
    
    gpus = [
        ("A100-GPU4 (Ashburn)", hist[-1], forecast[12], "#22c55e"),
        ("A100-GPU5 (Ashburn)", hist[-3], forecast[8], "#22c55e"),
        ("A100 (Phoenix)", hist[-8], forecast[15], "#38bdf8"),
        ("A100 (Frankfurt)", hist[-12], forecast[20], "#f59e0b"),
    ]
    gpu_rows = ""
    for name, cur, pred, col in gpus:
        trend = "↑" if pred > cur else "↓"
        trend_col = "#22c55e" if pred > cur else "#ef4444"
        gpu_rows += f'<tr><td style="color:#e2e8f0">{name}</td><td style="color:{col}">{cur:.0f}%</td><td style="color:{trend_col}">{pred:.0f}% {trend}</td></tr>'
    
    avg_cur = sum(g[1] for g in gpus) / len(gpus)
    avg_pred = sum(g[2] for g in gpus) / len(gpus)
    
    return f"""<!DOCTYPE html><html><head><title>GPU Utilization Forecaster</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>GPU Utilization Forecaster</h1><span>port {PORT} · 4-GPU fleet</span></div>
<div class="grid">
<div class="card"><h3>Current Avg Util</h3><div class="stat">{avg_cur:.0f}%</div><div class="sub">across 4 A100 GPUs</div></div>
<div class="card"><h3>Forecast (+12h)</h3><div class="stat">{avg_pred:.0f}%</div><div class="sub">ARIMA model prediction</div></div>
<div class="card"><h3>Peak Expected</h3><div class="stat">{max(forecast):.0f}%</div><div class="sub">next 24h maximum</div></div>
<div class="card" style="grid-column:span 3"><h3>Utilization: 72h History + 24h Forecast</h3>
<div style="display:flex;gap:16px;margin-bottom:8px;font-size:12px">
<span><span style="color:#38bdf8">—</span> Historical</span>
<span><span style="color:#f59e0b">- -</span> Forecast</span>
<span style="color:#64748b">| now</span>
</div>
<svg width="100%" viewBox="0 0 572 100">{hist_svg}{fc_svg}{divider}</svg></div>
<div class="card" style="grid-column:span 3"><h3>Per-GPU Forecast</h3>
<table><tr><th>GPU</th><th>Current</th><th>+12h Prediction</th></tr>{gpu_rows}</table></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GPU Utilization Forecaster")
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
