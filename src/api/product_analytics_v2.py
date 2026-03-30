"""Product Analytics V2 — FastAPI port 8853"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8853

# AARRR funnel data
FUNNEL = [
    {"stage": "Acquire",  "label": "Leads",           "count": 1000, "color": "#38bdf8"},
    {"stage": "Activate", "label": "Trial Start",      "count": 420,  "color": "#818cf8"},
    {"stage": "Retain",   "label": "30-day Active",    "count": 231,  "color": "#a78bfa"},
    {"stage": "Expand",   "label": "Upsell / Expand",  "count": 112,  "color": "#f472b6"},
    {"stage": "Revenue",  "label": "Paid Contract",    "count": 58,   "color": "#C74634"},
]

# Feature adoption data
FEATURES = [
    {"name": "DAgger Training",   "adoption": 100, "color": "#C74634"},
    {"name": "Eval API",           "adoption": 86,  "color": "#f87171"},
    {"name": "Streaming Inference","adoption": 71,  "color": "#fb923c"},
    {"name": "Python SDK",         "adoption": 73,  "color": "#fbbf24"},
    {"name": "Model Registry",     "adoption": 64,  "color": "#a3e635"},
    {"name": "SDG Pipeline",       "adoption": 58,  "color": "#34d399"},
    {"name": "Multi-GPU DDP",      "adoption": 52,  "color": "#38bdf8"},
    {"name": "Closed-Loop Eval",   "adoption": 47,  "color": "#818cf8"},
]

def build_funnel_svg():
    svg_w, svg_h = 520, 300
    max_w = 440
    max_count = FUNNEL[0]["count"]
    bar_h = 38
    gap = 8
    result = [f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" '
              f'style="width:100%;max-width:{svg_w}px;background:#0f172a">']
    for i, stage in enumerate(FUNNEL):
        w = math.floor((stage["count"] / max_count) * max_w)
        x = (svg_w - w) // 2
        y = i * (bar_h + gap) + 20
        conv = ""
        if i > 0:
            rate = round(stage["count"] / FUNNEL[i-1]["count"] * 100, 1)
            conv = f'<text x="{svg_w - 8}" y="{y + bar_h//2 + 5}" text-anchor="end" font-size="10" fill="#94a3b8">{rate}% conv</text>'
        result.append(f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" fill="{stage["color"]}" rx="4" opacity="0.85"/>')
        result.append(f'<text x="{svg_w//2}" y="{y + bar_h//2 - 5}" text-anchor="middle" font-size="11" font-weight="bold" fill="#f8fafc">{stage["stage"]}: {stage["label"]}</text>')
        result.append(f'<text x="{svg_w//2}" y="{y + bar_h//2 + 10}" text-anchor="middle" font-size="10" fill="#f1f5f9">{stage["count"]:,} users</text>')
        if conv:
            result.append(conv)
    result.append(
        f'<text x="{svg_w//2}" y="{svg_h - 5}" text-anchor="middle" font-size="10" fill="#38bdf8">'
        f'AARRR Funnel — Acquire → Activate → Retain → Expand → Revenue</text>'
    )
    result.append('</svg>')
    return "\n".join(result)

def build_heatmap_svg():
    svg_w = 560
    bar_h = 28
    gap = 6
    svg_h = len(FEATURES) * (bar_h + gap) + 50
    result = [f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" '
              f'style="width:100%;max-width:{svg_w}px;background:#0f172a">']
    max_bar_w = 340
    label_w = 180
    for i, feat in enumerate(FEATURES):
        y = i * (bar_h + gap) + 20
        bw = math.floor((feat["adoption"] / 100) * max_bar_w)
        result.append(f'<text x="{label_w - 8}" y="{y + bar_h//2 + 5}" text-anchor="end" font-size="11" fill="#cbd5e1">{feat["name"]}</text>')
        result.append(f'<rect x="{label_w}" y="{y}" width="{max_bar_w}" height="{bar_h}" fill="#1e293b" rx="3"/>')
        result.append(f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" fill="{feat["color"]}" rx="3" opacity="0.85"/>')
        result.append(f'<text x="{label_w + bw + 6}" y="{y + bar_h//2 + 5}" font-size="11" font-weight="bold" fill="#f8fafc">{feat["adoption"]}%</text>')
    result.append(
        f'<text x="{svg_w//2}" y="{svg_h - 5}" text-anchor="middle" font-size="10" fill="#38bdf8">'
        f'Feature Adoption Heatmap (% of active users)</text>'
    )
    result.append('</svg>')
    return "\n".join(result)

def build_html():
    funnel_svg = build_funnel_svg()
    heatmap_svg = build_heatmap_svg()
    # Compute overall funnel conversion
    acq_to_rev = round(FUNNEL[-1]["count"] / FUNNEL[0]["count"] * 100, 1)
    return f"""<!DOCTYPE html><html><head><title>Product Analytics V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:10px 20px 10px 0}}.metric .val{{font-size:2em;font-weight:bold;color:#C74634}}
.metric .lbl{{font-size:0.8em;color:#94a3b8}}</style></head>
<body><h1>Product Analytics V2</h1>
<p style="color:#94a3b8">AARRR funnel + feature adoption heatmap. Port {PORT}.</p>
<div class="card"><h2>Funnel Summary</h2>
  <div class="metric"><div class="val">100%</div><div class="lbl">DAgger Adoption</div></div>
  <div class="metric"><div class="val">86%</div><div class="lbl">Eval API Adoption</div></div>
  <div class="metric"><div class="val">73%</div><div class="lbl">SDK Adoption</div></div>
  <div class="metric"><div class="val">71%</div><div class="lbl">Streaming Adoption</div></div>
  <div class="metric"><div class="val">{acq_to_rev}%</div><div class="lbl">Acquire→Revenue Rate</div></div>
</div>
<div class="card"><h2>AARRR Funnel</h2>
{funnel_svg}
</div>
<div class="card"><h2>Feature Adoption Heatmap</h2>
{heatmap_svg}
</div>
<div class="card"><h2>Insights</h2>
  <ul>
    <li>DAgger training is the stickiest feature at 100% adoption among retained users</li>
    <li>Streaming inference gap (71%) vs Eval API (86%) — 15pp opportunity for nudge campaigns</li>
    <li>Activate→Retain conversion (55%) is the biggest funnel drop-off; target onboarding improvement</li>
    <li>SDK adoption (73%) suggests strong programmatic integration demand</li>
    <li>Multi-GPU DDP (52%) — growth lever as customers scale workloads</li>
  </ul>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Product Analytics V2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "service": "product_analytics_v2",
            "port": PORT,
            "dagger_adoption": 1.0,
            "eval_api_adoption": 0.86,
            "streaming_adoption": 0.71,
            "sdk_adoption": 0.73,
            "funnel_stages": {s["stage"]: s["count"] for s in FUNNEL},
            "features": {f["name"]: f["adoption"] for f in FEATURES},
        }

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
