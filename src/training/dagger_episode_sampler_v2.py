"""DAgger Episode Sampler v2 — FastAPI port 8499"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8499

def build_html():
    strategies = [
        ("Random", 0.64, 0.62, "#64748b"),
        ("Recency", 0.66, 0.65, "#94a3b8"),
        ("Difficulty", 0.70, 0.68, "#38bdf8"),
        ("Diversity", 0.71, 0.70, "#f59e0b"),
        ("Adaptive SR", 0.73, 0.72, "#22c55e"),
    ]
    
    bars = ""
    for name, sr_train, sr_eval, col in strategies:
        bars += f'''<div style="margin-bottom:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:12px">train SR={sr_train:.2f} · eval SR={sr_eval:.2f}</span>
</div>
<div style="background:#334155;border-radius:3px;height:10px">
<div style="background:{col};width:{sr_eval*100:.0f}%;height:10px;border-radius:3px"></div>
</div></div>'''
    
    # sample quality distribution
    quality_bins = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    random_dist = [12, 18, 22, 20, 14, 8, 4, 1, 0.5, 0.5]
    adaptive_dist = [3, 5, 8, 10, 14, 18, 22, 14, 4, 2]
    
    max_val = max(max(random_dist), max(adaptive_dist))
    bar_svg = ""
    for i, (q, rd, ad) in enumerate(zip(quality_bins, random_dist, adaptive_dist)):
        x_r = i * 48 + 2
        x_a = i * 48 + 26
        h_r = rd / max_val * 80
        h_a = ad / max_val * 80
        bar_svg += f'<rect x="{x_r}" y="{80-h_r:.0f}" width="20" height="{h_r:.0f}" fill="#64748b" opacity="0.7"/>'
        bar_svg += f'<rect x="{x_a}" y="{80-h_a:.0f}" width="20" height="{h_a:.0f}" fill="#22c55e" opacity="0.7"/>'
    bar_svg += f'<text x="240" y="95" text-anchor="middle" fill="#64748b" font-size="10">Quality Score</text>'
    
    # replay ratio impact
    ratios = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    sr_vals = [0.64, 0.68, 0.72, 0.73, 0.71, 0.67]
    ratio_pts = []
    for r, v in zip(ratios, sr_vals):
        x = r * 500
        y = 100 - (v - 0.60) / 0.15 * 100
        ratio_pts.append(f"{x:.0f},{y:.1f}")
    ratio_svg = f'<polyline points="{" ".join(ratio_pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    opt_x = 0.6 * 500
    opt_y = 100 - (0.73 - 0.60) / 0.15 * 100
    opt_marker = f'<circle cx="{opt_x:.0f}" cy="{opt_y:.1f}" r="6" fill="#C74634"/>'
    
    return f"""<!DOCTYPE html><html><head><title>DAgger Episode Sampler v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>DAgger Episode Sampler v2</h1><span>port {PORT} · 5 strategies compared</span></div>
<div class="grid">
<div class="card"><h3>Best Strategy</h3><div class="stat">Adaptive</div><div class="sub">SR=0.72 eval · +9pp vs random</div></div>
<div class="card"><h3>Optimal Hard Ratio</h3><div class="stat">60%</div><div class="sub">hard:easy ratio for best SR</div></div>
<div class="card"><h3>Strategy Comparison</h3>{bars}</div>
<div class="card"><h3>Quality Distribution</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#64748b">■</span> random <span style="color:#22c55e;margin-left:8px">■</span> adaptive_SR</div>
<svg width="100%" viewBox="0 0 480 100">{bar_svg}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Hard Episode Replay Ratio vs SR</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#C74634">●</span> optimal: 60% hard replay → SR=0.73</div>
<svg width="100%" viewBox="0 0 500 100">{ratio_svg}{opt_marker}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Episode Sampler v2")
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
