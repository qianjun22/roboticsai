"""Policy Export Manager — FastAPI service on port 8281.

Manages policy export to multiple formats (PyTorch / ONNX / TensorRT / CoreML)
for deployment on cloud and edge targets.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

FORMATS = [
    {"name": "PyTorch",   "size_gb": 6.7, "latency_ms": 226, "color": "#ee4b2b"},
    {"name": "ONNX",      "size_gb": 3.4, "latency_ms": 156, "color": "#38bdf8"},
    {"name": "TensorRT",  "size_gb": 3.1, "latency_ms": 109, "color": "#22c55e"},
    {"name": "CoreML",    "size_gb": 2.8, "latency_ms":  71, "color": "#a78bfa"},
]

# Compatibility matrix: rows=formats, cols=targets
# Values: S=SUPPORTED, P=PARTIAL, E=EXPERIMENTAL, U=UNSUPPORTED
TARGETS = ["OCI_A100", "OCI_A40", "Jetson_AGX", "Jetson_Orin", "RPi5", "iPhone", "WebAssembly", "ROS2"]

COMPAT = {
    #              OCI_A100  OCI_A40   Jet_AGX   Jet_Orin   RPi5     iPhone    WASM      ROS2
    "PyTorch":   ["S",      "S",      "S",      "S",       "P",     "U",      "U",      "S"],
    "ONNX":      ["S",      "S",      "S",      "S",       "S",     "E",      "E",      "S"],
    "TensorRT":  ["S",      "S",      "S",      "S",       "U",     "U",      "U",      "P"],
    "CoreML":    ["U",      "U",      "S",      "S",       "U",     "S",      "U",      "U"],
}

STATUS_COLOR = {
    "S": "#22c55e",
    "P": "#eab308",
    "E": "#f97316",
    "U": "#1e293b",
}
STATUS_LABEL = {
    "S": "SUPPORTED",
    "P": "PARTIAL",
    "E": "EXPERIMENTAL",
    "U": "UNSUPPORTED",
}

# Export pipeline metrics (mock)
EXPORT_STATS = {
    "format_coverage_score": 0.72,       # fraction of target/format combos supported
    "size_reduction_ratio": 2.39,        # PyTorch / TensorRT
    "pipeline_duration_min": 8.4,        # avg export + validation time
    "validation_pass_rate": 0.97,
}

# Recent export jobs
RECENT_JOBS = [
    {"id": "exp-0041", "model": "GR00T_v2", "format": "TensorRT", "target": "OCI_A100",  "status": "SUCCESS", "duration_s": 312, "size_gb": 3.1},
    {"id": "exp-0040", "model": "GR00T_v2", "format": "ONNX",     "target": "Jetson_Orin","status": "SUCCESS", "duration_s": 198, "size_gb": 3.4},
    {"id": "exp-0039", "model": "GR00T_v2", "format": "CoreML",   "target": "Jetson_AGX", "status": "SUCCESS", "duration_s": 224, "size_gb": 2.8},
    {"id": "exp-0038", "model": "GR00T_v2", "format": "PyTorch",  "target": "ROS2",       "status": "SUCCESS", "duration_s": 45,  "size_gb": 6.7},
    {"id": "exp-0037", "model": "GR00T_v1", "format": "TensorRT", "target": "OCI_A40",   "status": "SUCCESS", "duration_s": 289, "size_gb": 2.9},
    {"id": "exp-0036", "model": "GR00T_v2", "format": "ONNX",     "target": "WebAssembly","status": "EXPERIMENTAL", "duration_s": 411, "size_gb": 3.5},
]


def build_html() -> str:
    # -----------------------------------------------------------------------
    # SVG 1 — compatibility matrix
    # -----------------------------------------------------------------------
    cell_w, cell_h = 60, 36
    row_label_w = 90
    col_label_h = 56
    svg1_w = row_label_w + len(TARGETS) * cell_w + 20
    svg1_h = col_label_h + len(FORMATS) * cell_h + 20

    cells_svg = ""
    for ri, fmt in enumerate(FORMATS):
        for ci, tgt in enumerate(TARGETS):
            status = COMPAT[fmt["name"]][ci]
            cx = row_label_w + ci * cell_w
            cy = col_label_h + ri * cell_h
            color = STATUS_COLOR[status]
            cells_svg += f'<rect x="{cx}" y="{cy}" width="{cell_w-2}" height="{cell_h-2}" fill="{color}" rx="3" opacity="0.85"/>'
            cells_svg += f'<text x="{cx + cell_w//2 - 1}" y="{cy + cell_h//2 + 4}" fill="#0f172a" font-size="8" font-weight="bold" text-anchor="middle">{status}</text>'

    # row labels
    row_labels_svg = ""
    for ri, fmt in enumerate(FORMATS):
        cy = col_label_h + ri * cell_h
        row_labels_svg += f'<text x="{row_label_w - 8}" y="{cy + cell_h//2 + 4}" fill="#e2e8f0" font-size="11" text-anchor="end">{fmt["name"]}</text>'

    # col labels (rotated)
    col_labels_svg = ""
    for ci, tgt in enumerate(TARGETS):
        cx = row_label_w + ci * cell_w + cell_w // 2
        col_labels_svg += f'<text x="0" y="0" fill="#94a3b8" font-size="9" text-anchor="start" transform="translate({cx},{col_label_h - 6}) rotate(-45)">{tgt}</text>'

    # legend
    lx, ly = row_label_w, svg1_h - 14
    legend1_svg = ""
    for status, color in STATUS_COLOR.items():
        legend1_svg += f'<rect x="{lx}" y="{ly - 8}" width="10" height="10" fill="{color}" rx="2"/>'
        legend1_svg += f'<text x="{lx + 13}" y="{ly}" fill="#94a3b8" font-size="8">{STATUS_LABEL[status]}</text>'
        lx += 95

    svg1 = f"""<svg viewBox="0 0 {svg1_w} {svg1_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{svg1_w}px;background:#1e293b;border-radius:8px">
  <text x="{svg1_w//2}" y="16" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Export Format Compatibility Matrix — GR00T v2</text>
  {col_labels_svg}
  {row_labels_svg}
  {cells_svg}
  {legend1_svg}
</svg>"""

    # -----------------------------------------------------------------------
    # SVG 2 — grouped bar: size (GB) and latency (ms) per format
    # -----------------------------------------------------------------------
    svg2_w, svg2_h = 640, 300
    group_w = 120
    bar_w = 32
    gap_inner = 8
    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 50
    chart_h = svg2_h - pad_t - pad_b
    chart_w = svg2_w - pad_l - pad_r

    # dual axis: size max=8GB, latency max=260ms
    max_size = 8.0
    max_latency = 260.0
    size_color = "#38bdf8"
    latency_color = "#C74634"

    bars2_svg = ""
    for i, fmt in enumerate(FORMATS):
        gx = pad_l + i * (chart_w // len(FORMATS))
        # size bar (left axis)
        size_h = (fmt["size_gb"] / max_size) * chart_h
        bars2_svg += f'<rect x="{gx + 10}" y="{pad_t + chart_h - size_h:.1f}" width="{bar_w}" height="{size_h:.1f}" fill="{size_color}" opacity="0.85" rx="2"/>'
        bars2_svg += f'<text x="{gx + 10 + bar_w//2}" y="{pad_t + chart_h - size_h - 4:.1f}" fill="{size_color}" font-size="10" text-anchor="middle">{fmt["size_gb"]}GB</text>'
        # latency bar (right axis — scaled to left chart_h for visual)
        lat_h = (fmt["latency_ms"] / max_latency) * chart_h
        lat_x = gx + 10 + bar_w + gap_inner
        bars2_svg += f'<rect x="{lat_x}" y="{pad_t + chart_h - lat_h:.1f}" width="{bar_w}" height="{lat_h:.1f}" fill="{latency_color}" opacity="0.85" rx="2"/>'
        bars2_svg += f'<text x="{lat_x + bar_w//2}" y="{pad_t + chart_h - lat_h - 4:.1f}" fill="{latency_color}" font-size="10" text-anchor="middle">{fmt["latency_ms"]}ms</text>'
        # x label
        bars2_svg += f'<text x="{gx + 10 + bar_w + gap_inner//2}" y="{pad_t + chart_h + 16}" fill="#94a3b8" font-size="11" text-anchor="middle">{fmt["name"]}</text>'

    # left y-axis ticks (size)
    yticks2 = ""
    for tick in [0, 2, 4, 6, 8]:
        y = pad_t + chart_h - (tick / max_size) * chart_h
        yticks2 += f'<line x1="{pad_l-5}" y1="{y:.1f}" x2="{svg2_w - pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        yticks2 += f'<text x="{pad_l-8}" y="{y+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick}GB</text>'

    # right y-axis ticks (latency)
    for tick in [0, 65, 130, 195, 260]:
        y = pad_t + chart_h - (tick / max_latency) * chart_h
        yticks2 += f'<text x="{svg2_w - pad_r + 5}" y="{y+4:.1f}" fill="#64748b" font-size="9">{tick}ms</text>'

    # legend
    leg2_x = pad_l + 20
    leg2_y = pad_t + 8
    leg2_svg = (f'<rect x="{leg2_x}" y="{leg2_y}" width="10" height="10" fill="{size_color}"/>'
                f'<text x="{leg2_x+13}" y="{leg2_y+9}" fill="#cbd5e1" font-size="9">Model Size (GB)</text>'
                f'<rect x="{leg2_x+130}" y="{leg2_y}" width="10" height="10" fill="{latency_color}"/>'
                f'<text x="{leg2_x+143}" y="{leg2_y+9}" fill="#cbd5e1" font-size="9">Inference Latency (ms)</text>')

    svg2 = f"""<svg viewBox="0 0 {svg2_w} {svg2_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{svg2_w}px;background:#1e293b;border-radius:8px">
  <text x="{svg2_w//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Export Size &amp; Inference Latency — GR00T v2 in 4 Formats</text>
  <text x="12" y="{pad_t + chart_h//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,12,{pad_t + chart_h//2})">Size (GB)</text>
  <text x="{svg2_w - 10}" y="{pad_t + chart_h//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(90,{svg2_w-10},{pad_t + chart_h//2})">Latency (ms)</text>
  {yticks2}
  {bars2_svg}
  {leg2_svg}
</svg>"""

    # -----------------------------------------------------------------------
    # Metrics cards
    # -----------------------------------------------------------------------
    stats = EXPORT_STATS
    metrics_html = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px">
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">FORMAT COVERAGE SCORE</div>
        <div style="color:#22c55e;font-size:28px;font-weight:bold">{int(stats['format_coverage_score']*100)}%</div>
        <div style="color:#475569;font-size:10px">of target/format combos</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">SIZE REDUCTION RATIO</div>
        <div style="color:#38bdf8;font-size:28px;font-weight:bold">{stats['size_reduction_ratio']}x</div>
        <div style="color:#475569;font-size:10px">PyTorch → TensorRT</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">PIPELINE DURATION</div>
        <div style="color:#a78bfa;font-size:28px;font-weight:bold">{stats['pipeline_duration_min']} min</div>
        <div style="color:#475569;font-size:10px">avg export + validation</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">
        <div style="color:#64748b;font-size:11px;margin-bottom:6px">VALIDATION PASS RATE</div>
        <div style="color:#C74634;font-size:28px;font-weight:bold">{int(stats['validation_pass_rate']*100)}%</div>
        <div style="color:#475569;font-size:10px">across all recent jobs</div>
      </div>
    </div>
    """

    # recent jobs table
    status_dot = {"SUCCESS": "#22c55e", "EXPERIMENTAL": "#f97316", "FAILED": "#ef4444"}
    job_rows = ""
    for job in RECENT_JOBS:
        dot = status_dot.get(job["status"], "#64748b")
        job_rows += f"""<tr style="border-bottom:1px solid #0f172a">
          <td style="padding:8px 12px;color:#94a3b8">{job['id']}</td>
          <td style="padding:8px 12px;color:#e2e8f0">{job['model']}</td>
          <td style="padding:8px 12px;color:#38bdf8">{job['format']}</td>
          <td style="padding:8px 12px;color:#94a3b8">{job['target']}</td>
          <td style="padding:8px 12px"><span style="color:{dot};font-weight:bold">{job['status']}</span></td>
          <td style="padding:8px 12px;color:#64748b;text-align:right">{job['duration_s']}s</td>
          <td style="padding:8px 12px;color:#a78bfa;text-align:right">{job['size_gb']} GB</td>
        </tr>"""

    jobs_table = f"""
    <table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;margin-bottom:24px">
      <thead>
        <tr style="background:#0f172a">
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">JOB ID</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">MODEL</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">FORMAT</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">TARGET</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:left;font-size:11px">STATUS</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">DURATION</th>
          <th style="padding:10px 12px;color:#94a3b8;text-align:right;font-size:11px">SIZE</th>
        </tr>
      </thead>
      <tbody>{job_rows}</tbody>
    </table>
    """

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Policy Export Manager — Port 8281</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #38bdf8; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .section-title {{ color: #94a3b8; font-size: 13px; font-weight: 600; text-transform: uppercase;
                      letter-spacing: 0.05em; margin: 20px 0 10px; }}
    .badge {{ display:inline-block;background:#C74634;color:#fff;font-size:10px;padding:2px 8px;
              border-radius:4px;margin-left:8px;vertical-align:middle; }}
  </style>
</head>
<body>
  <h1>Policy Export Manager <span class="badge">PORT 8281</span></h1>
  <div class="subtitle">GR00T v2 — Multi-format export pipeline for cloud and edge deployment &nbsp;·&nbsp; Updated: {now}</div>

  {metrics_html}

  <div class="section-title">Format Compatibility Matrix</div>
  {svg1}

  <div class="section-title" style="margin-top:28px">Export Size &amp; Latency Comparison</div>
  {svg2}

  <div class="section-title" style="margin-top:28px">Recent Export Jobs</div>
  {jobs_table}
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Policy Export Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_export_manager", "port": 8281}

    @app.get("/api/formats")
    async def get_formats():
        return {"formats": FORMATS, "compatibility": COMPAT, "targets": TARGETS}

    @app.get("/api/jobs")
    async def get_jobs():
        return {"jobs": RECENT_JOBS, "stats": EXPORT_STATS}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = b'{"status":"ok","port":8281}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8281)
    else:
        print("[policy_export_manager] FastAPI not found — using stdlib http.server on port 8281")
        server = HTTPServer(("0.0.0.0", 8281), Handler)
        server.serve_forever()
