"""Sim Scene Generator — FastAPI port 8429"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8429

def build_html():
    # 12-object × 5-arrangement coverage matrix
    objects = ["cube","sphere","cylinder","mug","bottle","plate","book","tool","bag","bowl","box","bin"]
    arrangements = ["tabletop","cluttered","stacked","drawer","bin_pick"]
    arr_colors = ["#22c55e","#f59e0b","#38bdf8","#a78bfa","#C74634"]

    coverage = [
        [1,1,1,0,1],[1,1,0,0,1],[1,1,1,0,0],[1,1,1,1,0],
        [1,1,0,1,0],[1,0,1,0,0],[0,1,0,1,0],[1,0,1,0,1],
        [0,1,0,0,1],[1,1,1,0,0],[1,1,1,1,1],[0,0,1,0,1],
    ]

    cw11, rh11 = 56, 25
    svg_cov = f'<svg width="{len(arrangements)*cw11+130}" height="{len(objects)*rh11+50}" style="background:#0f172a">'
    for ai, arr in enumerate(arrangements):
        svg_cov += f'<text x="{130+ai*cw11+28}" y="18" fill="#94a3b8" font-size="8" text-anchor="middle">{arr[:8]}</text>'
    for oi, obj in enumerate(objects):
        svg_cov += f'<text x="125" y="{30+oi*rh11+15}" fill="#94a3b8" font-size="9" text-anchor="end">{obj}</text>'
        for ai, covered in enumerate(coverage[oi]):
            col = arr_colors[ai] if covered else "#1e293b"
            svg_cov += f'<rect x="{130+ai*cw11+2}" y="{25+oi*rh11+2}" width="{cw11-4}" height="{rh11-4}" fill="{col}" rx="3" opacity={"0.8" if covered else "0.3"}/>'
            if covered:
                svg_cov += f'<text x="{130+ai*cw11+28}" y="{25+oi*rh11+16}" fill="white" font-size="9" text-anchor="middle">✓</text>'
    svg_cov += '</svg>'

    # Diversity score bars (8 axes)
    diversity_axes = ["lighting","texture","clutter","scale","position","angle","material","background"]
    div_scores = [0.88, 0.82, 0.79, 0.91, 0.84, 0.76, 0.71, 0.86]
    svg_div = '<svg width="320" height="220" style="background:#0f172a">'
    for di, (axis, score) in enumerate(zip(diversity_axes, div_scores)):
        y = 15+di*24; w = int(score*260)
        col = "#22c55e" if score >= 0.85 else "#f59e0b" if score >= 0.75 else "#C74634"
        svg_div += f'<rect x="100" y="{y}" width="{w}" height="18" fill="{col}" opacity="0.8" rx="3"/>'
        svg_div += f'<text x="95" y="{y+13}" fill="#94a3b8" font-size="9" text-anchor="end">{axis}</text>'
        svg_div += f'<text x="{102+w}" y="{y+13}" fill="white" font-size="8">{score:.2f}</text>'
    avg_div = sum(div_scores)/len(div_scores)
    svg_div += f'<text x="160" y="210" fill="#38bdf8" font-size="9" text-anchor="middle">Avg diversity: {avg_div:.2f} / 1.0</text>'
    svg_div += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Sim Scene Generator — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Sim Scene Generator</h1>
<p style="color:#94a3b8">Port {PORT} | 12-object × 5-arrangement coverage + diversity scoring</p>
<div class="grid">
<div class="card"><h2>Object × Arrangement Coverage</h2>{svg_cov}</div>
<div class="card"><h2>Scene Diversity Scores</h2>{svg_div}
<div style="margin-top:8px">
<div class="stat">847</div><div class="label">Unique scenes/hour (Genesis DR throughput)</div>
<div class="stat" style="color:#22c55e;margin-top:8px">0.84</div><div class="label">Overall diversity score</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Scale diversity highest (0.91): critical for generalization<br>Material diversity lowest (0.71): needs more textures<br>74% of object-arrangement pairs covered<br>Gap: bag/book in drawer (target: 100% by v4)</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Scene Generator")
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
