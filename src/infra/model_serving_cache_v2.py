"""Model Serving Cache V2 — FastAPI port 8786"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8786

def build_html():
    # Generate cache hit/miss data over 24 hours
    hours = list(range(24))
    hit_rates = [round(70 + 20 * math.sin(h * math.pi / 12) + random.uniform(-5, 5), 1) for h in hours]
    miss_rates = [round(100 - r, 1) for r in hit_rates]
    latencies = [round(12 + 8 * math.cos(h * math.pi / 8) + random.uniform(0, 4), 2) for h in hours]

    # SVG bar chart for cache hit rate
    bar_w = 18
    bar_gap = 2
    svg_w = 24 * (bar_w + bar_gap)
    svg_h = 120
    bars = ""
    for i, r in enumerate(hit_rates):
        bh = int(r * svg_h / 100)
        x = i * (bar_w + bar_gap)
        y = svg_h - bh
        color = "#22c55e" if r >= 80 else ("#facc15" if r >= 65 else "#ef4444")
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}" rx="2"/>'

    # SVG line chart for latency
    pts = " ".join(f"{i * (svg_w / 23):.1f},{svg_h - latencies[i] * svg_h / 25:.1f}" for i in range(24))
    line_svg = f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'

    # Summary stats
    avg_hit = round(sum(hit_rates) / 24, 1)
    avg_lat = round(sum(latencies) / 24, 2)
    total_requests = random.randint(820000, 950000)
    cache_size_gb = round(random.uniform(18.4, 22.1), 1)
    evictions = random.randint(1200, 3400)
    models_cached = random.randint(34, 48)

    rows = ""
    model_names = ["GR00T-N1.6", "OpenVLA-7B", "Pi0-base", "ACT-large", "Diffusion-Policy", "RDT-1B"]
    for mn in model_names:
        hits = random.randint(60000, 200000)
        hit_r = round(random.uniform(72, 96), 1)
        lat = round(random.uniform(8, 20), 1)
        evict = random.randint(0, 500)
        rows += f"<tr><td>{mn}</td><td>{hits:,}</td><td><span style='color:{'#22c55e' if hit_r>85 else '#facc15'}'>{hit_r}%</span></td><td>{lat}ms</td><td>{evict}</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>Model Serving Cache V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}}
.metric{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.9em}}
th{{background:#0f172a;color:#94a3b8;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #334155}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75em}}
.green{{background:#14532d;color:#4ade80}}.yellow{{background:#713f12;color:#fde047}}
</style></head>
<body>
<h1>Model Serving Cache V2</h1>
<p style='color:#64748b;margin-top:0'>Port {PORT} &nbsp;|&nbsp; Cache-aware inference routing with LRU + priority eviction</p>

<div class="grid">
  <div class="metric"><div class="val">{avg_hit}%</div><div class="lbl">Avg Cache Hit Rate (24h)</div></div>
  <div class="metric"><div class="val">{avg_lat}ms</div><div class="lbl">Avg Cache Latency</div></div>
  <div class="metric"><div class="val">{total_requests:,}</div><div class="lbl">Total Requests (24h)</div></div>
  <div class="metric"><div class="val">{cache_size_gb} GB</div><div class="lbl">Active Cache Size</div></div>
  <div class="metric"><div class="val">{models_cached}</div><div class="lbl">Models Cached</div></div>
  <div class="metric"><div class="val">{evictions:,}</div><div class="lbl">Evictions (24h)</div></div>
</div>

<div class="card">
  <h2>Cache Hit Rate — Last 24 Hours</h2>
  <svg width="100%" viewBox="0 0 {svg_w} {svg_h + 20}" preserveAspectRatio="none">
    {bars}
    <line x1="0" y1="{svg_h - int(80 * svg_h / 100)}" x2="{svg_w}" y2="{svg_h - int(80 * svg_h / 100)}" stroke="#334155" stroke-dasharray="4" stroke-width="1"/>
    <text x="2" y="{svg_h - int(80 * svg_h / 100) - 2}" fill="#64748b" font-size="8">80%</text>
  </svg>
  <div style="color:#64748b;font-size:0.8em">Green ≥80% &nbsp; Yellow ≥65% &nbsp; Red &lt;65%</div>
</div>

<div class="card">
  <h2>Cache Fetch Latency (ms) — Last 24 Hours</h2>
  <svg width="100%" viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="none">
    <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
    {line_svg}
  </svg>
</div>

<div class="card">
  <h2>Per-Model Cache Stats</h2>
  <table>
    <thead><tr><th>Model</th><th>Cache Hits</th><th>Hit Rate</th><th>Avg Latency</th><th>Evictions</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Serving Cache V2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "cache_hit_rate": round(random.uniform(78, 92), 2),
            "avg_latency_ms": round(random.uniform(10, 18), 2),
            "models_cached": random.randint(34, 48),
            "cache_size_gb": round(random.uniform(18, 22), 1),
            "evictions_24h": random.randint(1200, 3400)
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
