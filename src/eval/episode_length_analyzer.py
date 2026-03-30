"""Episode Length Analyzer — FastAPI port 8754"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8754

def build_html():
    # Generate episode length distribution data
    random.seed(42)
    num_episodes = 200
    lengths = [max(10, int(120 + 60 * math.sin(i * 0.3) + random.gauss(0, 25))) for i in range(num_episodes)]
    avg_len = sum(lengths) / len(lengths)
    min_len = min(lengths)
    max_len = max(lengths)
    std_dev = math.sqrt(sum((x - avg_len) ** 2 for x in lengths) / len(lengths))

    # Histogram buckets (10 bins from min to max)
    num_bins = 12
    bin_size = (max_len - min_len) / num_bins
    bins = [0] * num_bins
    for l in lengths:
        idx = min(int((l - min_len) / bin_size), num_bins - 1)
        bins[idx] += 1
    bin_max = max(bins)

    bar_width = 38
    chart_height = 180
    bars_svg = ""
    for i, count in enumerate(bins):
        bar_h = int((count / bin_max) * chart_height) if bin_max > 0 else 0
        x = 40 + i * (bar_width + 4)
        y = 200 - bar_h
        hue = int(200 + (i / num_bins) * 60)
        bars_svg += f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="hsl({hue},70%,55%)" rx="2"/>'
        label_val = int(min_len + i * bin_size)
        if i % 3 == 0:
            bars_svg += f'<text x="{x + bar_width//2}" y="218" font-size="9" fill="#94a3b8" text-anchor="middle">{label_val}</text>'
        bars_svg += f'<text x="{x + bar_width//2}" y="{y - 3}" font-size="8" fill="#e2e8f0" text-anchor="middle">{count}</text>'

    # Success rate per task over episodes (line chart)
    tasks = ["PickCube", "StackBlocks", "PourWater", "OpenDoor", "ReachTarget"]
    task_colors = ["#38bdf8", "#34d399", "#f59e0b", "#f87171", "#c084fc"]
    line_charts = ""
    legend_items = ""
    for ti, task in enumerate(tasks):
        pts = []
        sr = 0.3 + ti * 0.1
        for j in range(40):
            sr = min(0.98, sr + random.gauss(0.01, 0.03))
            cx = 50 + j * 14
            cy = 160 - int(sr * 140)
            pts.append(f"{cx},{cy}")
        polyline = " ".join(pts)
        color = task_colors[ti]
        line_charts += f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" opacity="0.85"/>'
        legend_items += f'<rect x="{10 + ti * 120}" y="175" width="12" height="12" fill="{color}" rx="2"/>'
        legend_items += f'<text x="{26 + ti * 120}" y="185" font-size="11" fill="#e2e8f0">{task}</text>'

    # Completion time scatter
    scatter_pts = ""
    for i in range(80):
        sx = 30 + random.randint(0, 340)
        sy = 30 + random.randint(0, 120)
        r = random.randint(3, 7)
        alpha = 0.4 + random.random() * 0.5
        scatter_pts += f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="#38bdf8" opacity="{alpha:.2f}"/>'

    return f"""<!DOCTYPE html><html><head><title>Episode Length Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:24px 24px 0;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1.1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.stat{{display:inline-block;margin:8px 16px 8px 0}}
.stat-val{{font-size:1.8rem;font-weight:700;color:#38bdf8}}
.stat-lbl{{font-size:0.75rem;color:#94a3b8;text-transform:uppercase}}
.full{{grid-column:1/-1}}
</style></head>
<body>
<h1>Episode Length Analyzer</h1>
<p style="color:#94a3b8;padding:0 24px;margin:4px 0 0">Port {PORT} &mdash; {num_episodes} episodes analyzed across {len(tasks)} tasks</p>
<div class="grid">
  <div class="card full">
    <h2>Episode Length Distribution</h2>
    <div class="stat"><div class="stat-val">{avg_len:.1f}</div><div class="stat-lbl">Mean Steps</div></div>
    <div class="stat"><div class="stat-val">{min_len}</div><div class="stat-lbl">Min Steps</div></div>
    <div class="stat"><div class="stat-val">{max_len}</div><div class="stat-lbl">Max Steps</div></div>
    <div class="stat"><div class="stat-val">{std_dev:.1f}</div><div class="stat-lbl">Std Dev</div></div>
    <svg width="540" height="230" style="display:block;margin-top:10px">
      <line x1="40" y1="10" x2="40" y2="205" stroke="#334155" stroke-width="1"/>
      <line x1="40" y1="205" x2="530" y2="205" stroke="#334155" stroke-width="1"/>
      {bars_svg}
      <text x="280" y="235" font-size="11" fill="#64748b" text-anchor="middle">Episode Length (steps)</text>
    </svg>
  </div>
  <div class="card">
    <h2>Task Success Rate Over Episodes</h2>
    <svg width="580" height="200" style="display:block">
      <line x1="50" y1="20" x2="50" y2="165" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="165" x2="570" y2="165" stroke="#334155" stroke-width="1"/>
      {line_charts}
      {legend_items}
    </svg>
  </div>
  <div class="card">
    <h2>Completion Time vs Episode Index</h2>
    <svg width="400" height="180" style="display:block">
      <line x1="20" y1="10" x2="20" y2="155" stroke="#334155" stroke-width="1"/>
      <line x1="20" y1="155" x2="390" y2="155" stroke="#334155" stroke-width="1"/>
      {scatter_pts}
      <text x="200" y="175" font-size="10" fill="#64748b" text-anchor="middle">Episode Index</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Episode Length Analyzer")

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
