"""Action Space Coverage Analyzer V2 — FastAPI port 8896"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8896

# 14D action space dimensions
DIMENSIONS = [
    "joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5",
    "wrist_rot", "wrist_flex", "wrist_ext", "gripper",
    "ee_x", "ee_y", "ee_z", "ee_yaw"
]

# Per-task coverage budget (target: 91%)
TASK_COVERAGE = {
    "pour_task": {"current": 0.61, "target": 0.88, "gap": "wrist-rotation gap"},
    "pick_place": {"current": 0.84, "target": 0.92, "gap": "ee_z extremes"},
    "drawer_open": {"current": 0.79, "target": 0.91, "gap": "joint_5 range"},
    "stack_blocks": {"current": 0.82, "target": 0.93, "gap": "gripper precision"},
    "door_handle": {"current": 0.75, "target": 0.90, "gap": "wrist_flex limits"},
}

def build_html():
    random.seed(42)
    # Coverage values per dimension (14D), wrist-rotation dims are low
    coverage = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    # Normalize to 0.55-0.95 range
    norm = [round(0.55 + (v - min(coverage)) / (max(coverage) - min(coverage)) * 0.40, 3) for v in coverage]
    # Force wrist-rotation (index 6) low to reflect known gap
    dim_coverage = {}
    for idx, dim in enumerate(DIMENSIONS):
        if "wrist" in dim:
            dim_coverage[dim] = round(random.uniform(0.48, 0.63), 3)
        elif idx < len(norm):
            dim_coverage[dim] = norm[idx]
        else:
            dim_coverage[dim] = round(random.uniform(0.72, 0.94), 3)

    overall = round(sum(dim_coverage.values()) / len(dim_coverage), 3)

    # Heatmap cells (14 dims)
    heatmap_cells = ""
    for idx, (dim, cov) in enumerate(dim_coverage.items()):
        col = idx % 7
        row = idx // 7
        red = int(199 + (1 - cov) * 56)
        green = int(70 * cov)
        color = f"rgb({red},{green},52)"
        x = 10 + col * 62
        y = 50 + row * 62
        heatmap_cells += (
            f'<rect x="{x}" y="{y}" width="55" height="55" fill="{color}" rx="4"/>'
            f'<text x="{x+27}" y="{y+20}" text-anchor="middle" fill="#e2e8f0" font-size="9">{dim}</text>'
            f'<text x="{x+27}" y="{y+38}" text-anchor="middle" fill="white" font-size="11" font-weight="bold">{int(cov*100)}%</text>'
        )

    # Per-task coverage bars
    task_rows = ""
    for task, info in TASK_COVERAGE.items():
        pct = int(info['current'] * 100)
        tgt = int(info['target'] * 100)
        bar_w = int(info['current'] * 280)
        tgt_x = int(info['target'] * 280)
        task_rows += f"""
        <tr>
          <td style="padding:6px 10px;color:#94a3b8">{task}</td>
          <td style="padding:6px 10px">
            <svg width="290" height="20">
              <rect x="0" y="4" width="{bar_w}" height="12" fill="#C74634" rx="2"/>
              <rect x="{tgt_x}" y="0" width="2" height="20" fill="#38bdf8"/>
              <text x="{bar_w+4}" y="14" fill="#e2e8f0" font-size="10">{pct}%</text>
            </svg>
          </td>
          <td style="padding:6px 10px;color:#fbbf24;font-size:12px">{info['gap']}</td>
          <td style="padding:6px 10px;color:#38bdf8">{tgt}% target</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Action Space Coverage Analyzer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 5px}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:bold}}
table{{border-collapse:collapse;width:100%}}</style></head>
<body>
<h1>Action Space Coverage Analyzer V2</h1>
<p style="padding:0 20px;color:#94a3b8">14D robot action space coverage analysis — wrist-rotation gaps mapped to pour task failures</p>

<div class="card">
  <h2>Overall Coverage</h2>
  <span class="badge" style="background:#C74634">{int(overall*100)}% current</span>
  &nbsp;
  <span class="badge" style="background:#0369a1">91% target</span>
  &nbsp;
  <span style="color:#fbbf24;font-size:13px">Gap: {round((0.91 - overall)*100, 1)}pp — primary cause: wrist-rotation under-exploration</span>
</div>

<div class="card">
  <h2>14D Coverage Heatmap</h2>
  <p style="color:#94a3b8;font-size:13px">Red = low coverage (gaps), Green = high coverage</p>
  <svg width="450" height="180">
    {heatmap_cells}
  </svg>
</div>

<div class="card">
  <h2>Per-Task Coverage Budget</h2>
  <p style="color:#94a3b8;font-size:13px">Blue line = target threshold</p>
  <table>
    <thead><tr>
      <th style="text-align:left;padding:6px 10px;color:#64748b">Task</th>
      <th style="text-align:left;padding:6px 10px;color:#64748b">Coverage</th>
      <th style="text-align:left;padding:6px 10px;color:#64748b">Primary Gap</th>
      <th style="text-align:left;padding:6px 10px;color:#64748b">Target</th>
    </tr></thead>
    <tbody>{task_rows}</tbody>
  </table>
</div>

<div class="card" style="color:#94a3b8;font-size:12px">
  Port: {PORT} | Dims: 14 | Overall: {int(overall*100)}% → 91% target | Pour task wrist gap: coverage 78% → 91%
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Space Coverage Analyzer V2")
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
