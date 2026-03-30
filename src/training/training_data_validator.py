"""Training Data Validator — FastAPI port 8506"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8506

def build_html():
    checks = [
        ("Episode length (≥10 frames)", 572, 600, "#22c55e"),
        ("Frame rate (25±2 fps)", 558, 572, "#22c55e"),
        ("IK trajectory valid", 524, 558, "#22c55e"),
        ("Label completeness", 498, 524, "#38bdf8"),
        ("Quality score (≥0.6)", 472, 498, "#f59e0b"),
        ("Diversity filter", 445, 472, "#f59e0b"),
        ("Duplicate detection", 428, 445, "#f59e0b"),
        ("Bias check (task dist)", 421, 428, "#ef4444"),
    ]
    
    # funnel SVG
    funnel = ""
    funnel_w = 500
    for i, (name, remaining, total, col) in enumerate(checks):
        w = remaining / 600 * funnel_w
        x = (funnel_w - w) / 2 + 20
        y = i * 24 + 5
        funnel += f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="18" fill="{col}" opacity="0.7" rx="2"/>'
        funnel += f'<text x="20" y="{y+13}" fill="{col}" font-size="8">{name}</text>'
        funnel += f'<text x="545" y="{y+13}" fill="{col}" font-size="8">{remaining}</text>'
    
    # quality score histogram
    hist_bins = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    before = [8, 12, 18, 22, 20, 14, 8, 4, 2, 1]
    after = [0, 0, 1, 3, 8, 22, 34, 24, 6, 2]
    
    max_h = max(max(before), max(after))
    hist_svg = ""
    for i, (b, a) in enumerate(zip(before, after)):
        x_b = i * 48 + 5
        x_a = i * 48 + 27
        h_b = b / max_h * 80
        h_a = a / max_h * 80
        hist_svg += f'<rect x="{x_b}" y="{80-h_b:.0f}" width="20" height="{h_b:.0f}" fill="#64748b" opacity="0.7" rx="1"/>'
        hist_svg += f'<rect x="{x_a}" y="{80-h_a:.0f}" width="20" height="{h_a:.0f}" fill="#22c55e" opacity="0.7" rx="1"/>'
    
    rejection_rate = (600 - 421) / 600 * 100
    
    return f"""<!DOCTYPE html><html><head><title>Training Data Validator</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Training Data Validator</h1><span>port {PORT} · 8-check pipeline</span></div>
<div class="grid">
<div class="card"><h3>Pass Rate</h3><div class="stat">421/600</div><div class="sub">{100-rejection_rate:.0f}% pass · {rejection_rate:.1f}% rejected</div></div>
<div class="card"><h3>Top Filter</h3><div class="stat">Bias</div><div class="sub">pick_place 32% vs 15% target</div></div>
<div class="card" style="grid-column:span 2"><h3>Validation Funnel (600 → 421)</h3>
<svg width="100%" viewBox="0 0 570 200">{funnel}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Quality Score Distribution (before/after filtering)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#64748b">■</span> before <span style="color:#22c55e;margin-left:8px">■</span> after</div>
<svg width="100%" viewBox="0 0 480 80">{hist_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Data Validator")
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
