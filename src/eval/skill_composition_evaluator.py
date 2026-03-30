"""Skill Composition Evaluator — FastAPI port 8840"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8840

def build_html():
    # Compute bar widths for skill chain success rates
    metrics = [
        ("Primitive (1-skill)", 91),
        ("2-skill chain", 73),
        ("3-skill chain", 54),
        ("4-skill chain", 38),
    ]

    # Build SVG skill composition success tree (horizontal bars)
    bar_svg_items = ""
    colors = ["#22c55e", "#84cc16", "#f59e0b", "#ef4444"]
    for i, (label, pct) in enumerate(metrics):
        y = 30 + i * 55
        bar_w = math.floor(pct * 3.6)  # max 360px for 100%
        bar_svg_items += (
            f'<text x="10" y="{y}" fill="#94a3b8" font-size="13">{label}</text>'
            f'<rect x="10" y="{y+8}" width="{bar_w}" height="22" rx="4" fill="{colors[i]}"/>'
            f'<text x="{bar_w + 18}" y="{y+23}" fill="#e2e8f0" font-size="13" font-weight="bold">{pct}%</text>'
        )

    svg_h = 30 + len(metrics) * 55 + 10

    # Build SVG tree diagram showing pick->place->inspect chain
    tree_svg = (
        '<svg width="480" height="120" xmlns="http://www.w3.org/2000/svg">'
        # Nodes
        '<rect x="10" y="45" width="90" height="32" rx="6" fill="#1e40af"/>'
        '<text x="55" y="65" text-anchor="middle" fill="#e2e8f0" font-size="12">Pick</text>'
        '<rect x="145" y="45" width="90" height="32" rx="6" fill="#0e7490"/>'
        '<text x="190" y="65" text-anchor="middle" fill="#e2e8f0" font-size="12">Place</text>'
        '<rect x="280" y="45" width="90" height="32" rx="6" fill="#6d28d9"/>'
        '<text x="325" y="65" text-anchor="middle" fill="#e2e8f0" font-size="12">Inspect</text>'
        '<rect x="385" y="45" width="85" height="32" rx="6" fill="#C74634"/>'
        '<text x="427" y="65" text-anchor="middle" fill="#e2e8f0" font-size="12">Sort</text>'
        # Arrows
        '<line x1="100" y1="61" x2="145" y2="61" stroke="#38bdf8" stroke-width="2" marker-end="url(#arr)"/>'
        '<line x1="235" y1="61" x2="280" y2="61" stroke="#38bdf8" stroke-width="2" marker-end="url(#arr)"/>'
        '<line x1="370" y1="61" x2="385" y2="61" stroke="#38bdf8" stroke-width="2" marker-end="url(#arr)"/>'
        # Success labels below arrows
        '<text x="122" y="90" text-anchor="middle" fill="#22c55e" font-size="11">73%</text>'
        '<text x="257" y="90" text-anchor="middle" fill="#f59e0b" font-size="11">54%</text>'
        '<text x="377" y="90" text-anchor="middle" fill="#ef4444" font-size="11">38%</text>'
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/></marker></defs>'
        '</svg>'
    )

    bar_svg = f'<svg width="420" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">{bar_svg_items}</svg>'

    return f"""<!DOCTYPE html><html><head><title>Skill Composition Evaluator</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.stat{{background:#0f172a;border-radius:6px;padding:14px;text-align:center}}
.stat .val{{font-size:2rem;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.85rem;color:#94a3b8;margin-top:4px}}
</style></head>
<body>
<h1>Skill Composition Evaluator</h1>
<p style="color:#94a3b8">Tests how well learned primitive skills compose into complex multi-step tasks (pick→place→inspect). Port {PORT}</p>

<div class="card">
  <h2>Key Metrics</h2>
  <div class="grid">
    <div class="stat"><div class="val">91%</div><div class="lbl">Primitive Success</div></div>
    <div class="stat"><div class="val">73%</div><div class="lbl">2-Skill Chain</div></div>
    <div class="stat"><div class="val">54%</div><div class="lbl">3-Skill Chain</div></div>
    <div class="stat"><div class="val" style="color:#ef4444">38%</div><div class="lbl">4-Skill Chain</div></div>
  </div>
</div>

<div class="card">
  <h2>Skill Chain: pick → place → inspect → sort</h2>
  {tree_svg}
</div>

<div class="card">
  <h2>Composition Success by Chain Length</h2>
  {bar_svg}
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Skill Composition Evaluator")
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
