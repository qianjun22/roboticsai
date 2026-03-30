"""GTM Attribution Model — FastAPI port 8833"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8833

def build_html():
    # Pie chart: NVIDIA-referred 67%, Conference 19%, Cold Outbound 14%
    sources = [
        {"label": "NVIDIA Referral", "pct": 67, "color": "#76b900"},
        {"label": "Conference",      "pct": 19, "color": "#38bdf8"},
        {"label": "Cold Outbound",   "pct": 14, "color": "#f59e0b"},
    ]
    cx, cy, r = 180, 170, 130
    total = sum(s["pct"] for s in sources)
    slices = []
    angle = -math.pi / 2  # start at top
    for s in sources:
        sweep = 2 * math.pi * s["pct"] / total
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        angle += sweep
        x2 = cx + r * math.cos(angle)
        y2 = cy + r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        mid_angle = angle - sweep / 2
        lx = cx + (r + 22) * math.cos(mid_angle)
        ly = cy + (r + 22) * math.sin(mid_angle)
        slices.append(
            f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large},1 {x2:.2f},{y2:.2f} Z" fill="{s["color"]}" opacity="0.9"/>'
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e2e8f0" font-size="12" text-anchor="middle">{s["pct"]}%</text>'
        )
    pie_svg = "\n    ".join(slices)

    legend_items = "".join(
        f'<div style="margin:4px 0"><span style="display:inline-block;width:14px;height:14px;background:{s["color"]};border-radius:3px;margin-right:8px;vertical-align:middle"></span>{s["label"]} — {s["pct"]}%</div>'
        for s in sources
    )

    return f"""<!DOCTYPE html><html><head><title>GTM Attribution Model</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:10px 20px;text-align:center}}.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.85em;color:#94a3b8}}.flex{{display:flex;align-items:center;gap:30px;flex-wrap:wrap}}</style></head>
<body>
<h1>GTM Attribution Model</h1>
<div class="card">
  <h2>Key Metrics</h2>
  <div class="metric"><div class="val">67%</div><div class="lbl">NVIDIA-Referred Pipeline</div></div>
  <div class="metric"><div class="val">$1.8M</div><div class="lbl">Attributed Pipeline</div></div>
  <div class="metric"><div class="val">4.2×</div><div class="lbl">NVIDIA Channel ROI</div></div>
</div>
<div class="card">
  <h2>Pipeline Attribution by Source</h2>
  <div class="flex">
    <svg width="360" height="340" style="background:#0f172a;border-radius:6px">
      {pie_svg}
      <text x="{cx}" y="{cy - 148}" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="bold">Attribution</text>
      <text x="{cx}" y="{cy - 132}" fill="#94a3b8" font-size="11" text-anchor="middle">Sources</text>
    </svg>
    <div>
      <div style="font-weight:bold;margin-bottom:10px;color:#38bdf8">Channel Breakdown</div>
      {legend_items}
      <div style="margin-top:18px;color:#94a3b8;font-size:0.85em">
        Total tracked deals: 38<br>
        Avg deal size: $47K<br>
        NVIDIA co-sell active: 12 accounts
      </div>
    </div>
  </div>
</div>
<div class="card" style="color:#94a3b8;font-size:0.85em">
  Port: {PORT} | Service: GTM Attribution Model | OCI Robot Cloud
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GTM Attribution Model")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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
