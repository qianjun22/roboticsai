"""Data Quality Pipeline — FastAPI port 8746"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8746

def build_html():
    random.seed(42)

    # Generate quality score time series (sinusoidal trend + noise)
    n_points = 48
    scores = [round(0.82 + 0.10 * math.sin(i * math.pi / 12) + random.uniform(-0.03, 0.03), 3) for i in range(n_points)]
    svg_w, svg_h = 560, 120
    x_step = svg_w / (n_points - 1)
    min_s, max_s = 0.70, 1.00
    def sy(v): return svg_h - int((v - min_s) / (max_s - min_s) * svg_h)
    polyline_pts = " ".join(f"{int(i * x_step)},{sy(scores[i])}" for i in range(n_points))
    area_pts = f"0,{svg_h} " + polyline_pts + f" {svg_w},{svg_h}"

    # Episode length distribution (bar chart)
    buckets = [0] * 10
    for _ in range(2000):
        length = int(abs(random.gauss(120, 35)))
        bucket = min(length // 30, 9)
        buckets[bucket] += 1
    bar_max = max(buckets)
    bar_w = 44
    bar_gap = 12
    bars_svg_h = 100
    bars_html = ""
    labels = ["0-29","30-59","60-89","90-119","120-149","150-179","180-209","210-239","240-269","270+"]
    for idx, cnt in enumerate(buckets):
        bh = int(cnt / bar_max * bars_svg_h)
        bx = idx * (bar_w + bar_gap)
        color = "#38bdf8" if idx not in (0, 9) else "#f87171"
        bars_html += f'<rect x="{bx}" y="{bars_svg_h - bh}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
        bars_html += f'<text x="{bx + bar_w//2}" y="{bars_svg_h + 14}" text-anchor="middle" font-size="9" fill="#94a3b8">{labels[idx]}</text>'
        bars_html += f'<text x="{bx + bar_w//2}" y="{bars_svg_h - bh - 4}" text-anchor="middle" font-size="9" fill="#e2e8f0">{cnt}</text>'

    # Anomaly heatmap (8 x 6 grid = sensors x time)
    heatmap_cells = ""
    cell_w, cell_h = 52, 28
    sensor_labels = ["joint_pos","joint_vel","gripper","rgb_left","rgb_right","rgb_wrist","proprio","lang_emb"]
    time_labels = ["T-5h","T-4h","T-3h","T-2h","T-1h","Now"]
    for r, sensor in enumerate(sensor_labels):
        for c, tl in enumerate(time_labels):
            anom_rate = max(0.0, random.gauss(0.04, 0.03))
            intensity = min(anom_rate / 0.15, 1.0)
            red = int(31 + intensity * 180)
            green = int(41 + (1 - intensity) * 150)
            blue = int(55 + (1 - intensity) * 100)
            cx = 90 + c * (cell_w + 4)
            cy = 24 + r * (cell_h + 4)
            heatmap_cells += f'<rect x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" fill="rgb({red},{green},{blue})" rx="2"/>'
            heatmap_cells += f'<text x="{cx + cell_w//2}" y="{cy + 18}" text-anchor="middle" font-size="9" fill="#e2e8f0">{anom_rate:.2%}</text>'
        label_x = 0
        label_y = 24 + r * (cell_h + 4) + 18
        heatmap_cells += f'<text x="{label_x}" y="{label_y}" font-size="9" fill="#94a3b8">{sensor}</text>'
    for c, tl in enumerate(time_labels):
        cx = 90 + c * (cell_w + 4) + cell_w // 2
        heatmap_cells += f'<text x="{cx}" y="14" text-anchor="middle" font-size="9" fill="#94a3b8">{tl}</text>'

    # Summary stats
    total_eps = 14872
    passed = 13904
    failed = total_eps - passed
    pass_rate = passed / total_eps * 100
    avg_score = sum(scores) / len(scores)
    avg_len = sum(i * 30 * b for i, b in enumerate(buckets)) / sum(buckets)

    return f"""<!DOCTYPE html><html><head><title>Data Quality Pipeline</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:12px 0 8px 0;font-size:1rem}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}}
.stat{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.stat .val{{font-size:1.8rem;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
.stat.warn .val{{color:#f59e0b}}
.stat.err .val{{color:#f87171}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;margin-right:6px}}
.ok{{background:#166534;color:#86efac}}.bad{{background:#7f1d1d;color:#fca5a5}}
.sub{{color:#94a3b8;font-size:0.8rem;margin-bottom:8px}}
</style></head>
<body>
<h1>Data Quality Pipeline</h1>
<p class="sub">Port {PORT} — Real-time episode validation, anomaly detection &amp; quality scoring for robot training datasets</p>

<div class="grid">
  <div class="stat"><div class="val">{total_eps:,}</div><div class="lbl">Total Episodes Processed</div></div>
  <div class="stat"><div class="val">{pass_rate:.1f}%</div><div class="lbl">Pass Rate</div></div>
  <div class="stat warn"><div class="val">{failed:,}</div><div class="lbl">Rejected Episodes</div></div>
  <div class="stat"><div class="val">{avg_score:.3f}</div><div class="lbl">Avg Quality Score</div></div>
</div>

<div class="card">
  <h2>Quality Score — Last 48 Hours</h2>
  <svg width="{svg_w}" height="{svg_h + 10}" style="display:block">
    <defs><linearGradient id="qg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
    </linearGradient></defs>
    <polygon points="{area_pts}" fill="url(#qg)"/>
    <polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <line x1="0" y1="{sy(0.80)}" x2="{svg_w}" y2="{sy(0.80)}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="{svg_w - 4}" y="{sy(0.80) - 4}" text-anchor="end" font-size="10" fill="#f59e0b">threshold 0.80</text>
  </svg>
</div>

<div class="card">
  <h2>Episode Length Distribution (frames)</h2>
  <svg width="{len(buckets) * (bar_w + bar_gap)}" height="{bars_svg_h + 30}" style="display:block">
    {bars_html}
  </svg>
  <p class="sub" style="margin-top:8px">Avg length: {avg_len:.1f} frames &nbsp;|&nbsp; <span class="badge bad">Outlier buckets shown in red</span></p>
</div>

<div class="card">
  <h2>Sensor Anomaly Heatmap</h2>
  <svg width="500" height="{len(sensor_labels) * (cell_h + 4) + 30}" style="display:block">
    {heatmap_cells}
  </svg>
  <p class="sub" style="margin-top:8px">Cell value = anomaly rate per modality per hour window</p>
</div>

<div class="card">
  <h2>Active Validation Rules</h2>
  <span class="badge ok">min_frames &gt;= 10</span>
  <span class="badge ok">max_frames &lt;= 500</span>
  <span class="badge ok">joint_vel |v| &lt; 3.14</span>
  <span class="badge ok">gripper [0,1]</span>
  <span class="badge ok">rgb no NaN</span>
  <span class="badge ok">lang_emb L2 &gt; 0.1</span>
  <span class="badge bad">proprio drift &lt; 0.05 [WARN]</span>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Data Quality Pipeline")
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
