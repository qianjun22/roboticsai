"""Policy Confidence Estimator — FastAPI port 8512"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8512

def build_html():
    # confidence score distribution
    bins = [i/10 for i in range(11)]
    counts_correct = [2, 3, 5, 8, 14, 22, 32, 24, 12, 4]
    counts_incorrect = [8, 12, 14, 10, 7, 4, 2, 1, 0, 0]
    
    max_count = max(max(counts_correct), max(counts_incorrect))
    hist_svg = ""
    for i, (cc, ci) in enumerate(zip(counts_correct, counts_incorrect)):
        x_c = i * 48 + 5
        x_i = i * 48 + 27
        h_c = cc / max_count * 80
        h_i = ci / max_count * 80
        hist_svg += f'<rect x="{x_c}" y="{80-h_c:.0f}" width="20" height="{h_c:.0f}" fill="#22c55e" opacity="0.8" rx="1"/>'
        hist_svg += f'<rect x="{x_i}" y="{80-h_i:.0f}" width="20" height="{h_i:.0f}" fill="#ef4444" opacity="0.8" rx="1"/>'
    hist_svg += f'<line x1="{0.35*480:.0f}" y1="0" x2="{0.35*480:.0f}" y2="80" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,2"/>'
    
    # calibration curve
    conf_bins = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    actual_acc = [0.12, 0.19, 0.31, 0.42, 0.51, 0.63, 0.72, 0.81, 0.88]
    
    calib_pts = []
    for c, a in zip(conf_bins, actual_acc):
        x = c * 400
        y = 100 - a * 100
        calib_pts.append(f"{x:.0f},{y:.0f}")
    
    calib_svg = f'<polyline points="{" ".join(calib_pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    # perfect calibration diagonal
    perfect_svg = f'<line x1="0" y1="100" x2="400" y2="0" stroke="#334155" stroke-width="1" stroke-dasharray="4,2"/>'
    
    # ECE calculation visualization
    ece = 0.041
    early_abort_threshold = 0.35
    compute_savings = 34
    
    return f"""<!DOCTYPE html><html><head><title>Policy Confidence Estimator</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Policy Confidence Estimator</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Calibration ECE</h3><div class="stat">{ece}</div><div class="sub">well-calibrated · target &lt;0.05</div></div>
<div class="card"><h3>Abort Threshold</h3><div class="stat">{early_abort_threshold}</div><div class="sub">low-conf episodes → abort</div></div>
<div class="card"><h3>Compute Savings</h3><div class="stat">{compute_savings}%</div><div class="sub">via early-abort on low confidence</div></div>
<div class="card" style="grid-column:span 2"><h3>Confidence Distribution (correct vs incorrect)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">■</span> correct outcomes <span style="color:#ef4444;margin-left:8px">■</span> incorrect <span style="color:#f59e0b;margin-left:8px">| abort threshold 0.35</span></div>
<svg width="100%" viewBox="0 0 480 80">{hist_svg}</svg></div>
<div class="card"><h3>Calibration Curve</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#38bdf8">—</span> GR00T_v2 <span style="color:#334155;margin-left:8px">- -</span> perfect</div>
<svg width="100%" viewBox="0 0 400 100">{calib_svg}{perfect_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Confidence Estimator")
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
