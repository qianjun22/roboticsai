"""Checkpoint Lifecycle Manager — FastAPI port 8738"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8738

def build_html():
    random.seed(42)
    # Checkpoint retention data: simulate 30 checkpoints over 30 days
    checkpoints = []
    for i in range(30):
        age_days = i
        size_gb = round(random.uniform(1.2, 4.8), 2)
        val_loss = round(0.35 * math.exp(-0.05 * i) + random.uniform(0, 0.02), 4)
        status = "retained" if (i % 5 == 0 or i == 29) else ("pruned" if i % 3 == 0 else "archived")
        checkpoints.append({"idx": i, "age": age_days, "size": size_gb, "val_loss": val_loss, "status": status})

    total_size = sum(c["size"] for c in checkpoints)
    retained = [c for c in checkpoints if c["status"] == "retained"]
    pruned = [c for c in checkpoints if c["status"] == "pruned"]
    archived = [c for c in checkpoints if c["status"] == "archived"]

    # SVG: val_loss curve over checkpoint index
    svg_w, svg_h = 540, 180
    pts = []
    for c in checkpoints:
        x = int(20 + (c["idx"] / 29) * (svg_w - 40))
        y = int(svg_h - 20 - ((0.35 - c["val_loss"]) / 0.35) * (svg_h - 40))
        pts.append(f"{x},{y}")
    polyline = " ".join(pts)

    # SVG: storage bar chart by status
    bar_data = [
        ("Retained", len(retained), "#22c55e"),
        ("Archived", len(archived), "#f59e0b"),
        ("Pruned",   len(pruned),   "#ef4444"),
    ]
    bars_svg = ""
    for bi, (label, count, color) in enumerate(bar_data):
        bx = 30 + bi * 160
        bh = int((count / 30) * 120)
        by = 150 - bh
        bars_svg += f'<rect x="{bx}" y="{by}" width="100" height="{bh}" fill="{color}" rx="4"/>'
        bars_svg += f'<text x="{bx+50}" y="{by - 6}" fill="#e2e8f0" font-size="13" text-anchor="middle">{count}</text>'
        bars_svg += f'<text x="{bx+50}" y="168" fill="#94a3b8" font-size="11" text-anchor="middle">{label}</text>'

    rows = ""
    for c in checkpoints[-10:]:
        color_map = {"retained": "#22c55e", "pruned": "#ef4444", "archived": "#f59e0b"}
        col = color_map.get(c["status"], "#e2e8f0")
        rows += f"""<tr>
          <td>ckpt-{c['idx']:03d}</td>
          <td>{c['age']}d</td>
          <td>{c['size']} GB</td>
          <td>{c['val_loss']}</td>
          <td style='color:{col};font-weight:600'>{c['status']}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Checkpoint Lifecycle Manager</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top}}
.grid{{display:flex;flex-wrap:wrap}}
.stat{{font-size:2em;font-weight:700;color:#38bdf8}}
.sublabel{{color:#94a3b8;font-size:0.85em}}
table{{border-collapse:collapse;width:100%;font-size:0.9em}}
th{{color:#94a3b8;border-bottom:1px solid #334155;padding:6px 10px;text-align:left}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Checkpoint Lifecycle Manager</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 12px'>Port {PORT} &mdash; Automated retention, pruning &amp; archival for model checkpoints</p>
<div class='grid'>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Total Checkpoints</div>
    <div class='stat'>30</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Storage Used</div>
    <div class='stat'>{total_size:.1f} GB</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Retained</div>
    <div class='stat' style='color:#22c55e'>{len(retained)}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Pruned</div>
    <div class='stat' style='color:#ef4444'>{len(pruned)}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Archived</div>
    <div class='stat' style='color:#f59e0b'>{len(archived)}</div>
  </div>
</div>
<div class='grid'>
  <div class='card' style='width:560px'>
    <h2>Validation Loss Curve (30 Checkpoints)</h2>
    <svg width='{svg_w}' height='{svg_h}' style='background:#0f172a;border-radius:6px'>
      <polyline points='{polyline}' fill='none' stroke='#38bdf8' stroke-width='2.5'/>
      <text x='10' y='18' fill='#94a3b8' font-size='11'>loss</text>
      <text x='{svg_w-30}' y='{svg_h-4}' fill='#94a3b8' font-size='11'>ckpt</text>
    </svg>
  </div>
  <div class='card' style='width:520px'>
    <h2>Checkpoint Status Breakdown</h2>
    <svg width='510' height='180' style='background:#0f172a;border-radius:6px'>
      {bars_svg}
    </svg>
  </div>
</div>
<div class='card' style='width:calc(100% - 60px)'>
  <h2>Recent Checkpoints (last 10)</h2>
  <table>
    <tr><th>ID</th><th>Age</th><th>Size</th><th>Val Loss</th><th>Status</th></tr>
    {rows}
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Lifecycle Manager")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/checkpoints")
    def api_checkpoints():
        random.seed(42)
        result = []
        for i in range(30):
            size_gb = round(random.uniform(1.2, 4.8), 2)
            val_loss = round(0.35 * math.exp(-0.05 * i) + random.uniform(0, 0.02), 4)
            status = "retained" if (i % 5 == 0 or i == 29) else ("pruned" if i % 3 == 0 else "archived")
            result.append({"id": f"ckpt-{i:03d}", "age_days": i, "size_gb": size_gb, "val_loss": val_loss, "status": status})
        return result

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
