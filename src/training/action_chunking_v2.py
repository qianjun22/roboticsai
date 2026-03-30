"""Action Chunking V2 — FastAPI service on port 8277.

Analyzes and optimizes action chunk size and boundary detection for GR00T.
Fallback to stdlib http.server if FastAPI/uvicorn are not installed.
"""

import math
import random
import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(7)

# Chunk-size sweep results
CHUNK_SWEEP = [
    {"chunk": 4,  "sr": 0.71, "latency_ms": 112, "jerk": 0.38, "boundary_acc": 0.61},
    {"chunk": 8,  "sr": 0.71, "latency_ms": 148, "jerk": 0.29, "boundary_acc": 0.72},
    {"chunk": 12, "sr": 0.76, "latency_ms": 183, "jerk": 0.21, "boundary_acc": 0.81},
    {"chunk": 16, "sr": 0.78, "latency_ms": 226, "jerk": 0.15, "boundary_acc": 0.89},
    {"chunk": 20, "sr": 0.76, "latency_ms": 268, "jerk": 0.17, "boundary_acc": 0.86},
    {"chunk": 24, "sr": 0.74, "latency_ms": 310, "jerk": 0.19, "boundary_acc": 0.83},
    {"chunk": 32, "sr": 0.74, "latency_ms": 394, "jerk": 0.24, "boundary_acc": 0.78},
]

OPTIMAL_CHUNK = 16

# Boundary detection methods
BD_METHODS = [
    {"name": "Velocity-Threshold",  "accuracy": 0.89, "false_pos": 0.08, "latency_ms": 2.1},
    {"name": "Jerk-Peak",           "accuracy": 0.84, "false_pos": 0.12, "latency_ms": 1.4},
    {"name": "Learned-Classifier",  "accuracy": 0.93, "false_pos": 0.05, "latency_ms": 4.8},
]

# 300-step trajectory chunk quality
TRAJ_STEPS = 300
CHUNK_SIZE = 16

def _chunk_quality(chunk_idx):
    """Smoothness score 0-1 for each 16-step chunk in a 300-step trajectory."""
    random.seed(chunk_idx * 13 + 99)
    base = 0.82 + 0.12 * math.sin(chunk_idx * 0.7)
    noise = random.gauss(0, 0.06)
    q = max(0.0, min(1.0, base + noise))
    # Inject a few poor boundaries
    if chunk_idx in (3, 8, 14):
        q = round(random.uniform(0.28, 0.45), 3)
    return round(q, 3)

N_CHUNKS = TRAJ_STEPS // CHUNK_SIZE
CHUNK_QUALITIES = [_chunk_quality(i) for i in range(N_CHUNKS)]
POOR_CHUNKS = [i for i, q in enumerate(CHUNK_QUALITIES) if q < 0.55]


def compute_metrics():
    best = CHUNK_SWEEP[3]  # chunk=16
    worst_chunk = CHUNK_SWEEP[0]
    return {
        "optimal_chunk": OPTIMAL_CHUNK,
        "optimal_sr":    best["sr"],
        "optimal_lat":   best["latency_ms"],
        "boundary_acc":  best["boundary_acc"],
        "jerk_optimal":  best["jerk"],
        "poor_boundaries": len(POOR_CHUNKS),
        "sr_sensitivity": round((best["sr"] - worst_chunk["sr"]) / best["sr"] * 100, 1),
        "best_bd_method": "Learned-Classifier",
        "best_bd_acc":    0.93,
    }


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def svg_chunk_boundary() -> str:
    """300-step trajectory with 16-step chunk boundaries and quality heatmap."""
    W, H = 760, 260
    left, right_margin = 50, 20
    top, bottom = 50, 40
    traj_y   = top + 40
    chunk_bar_y = traj_y + 60
    chart_w  = W - left - right_margin

    def step_px(s):
        return left + (s / TRAJ_STEPS) * chart_w

    def chunk_px(ci):
        return step_px(ci * CHUNK_SIZE)

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="font-family:monospace;font-size:11px;">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">300-Step Trajectory — Chunk Boundaries &amp; Quality (chunk=16)</text>')

    # Simulated trajectory line (sine-based mock joint angle)
    pts = []
    for s in range(TRAJ_STEPS + 1):
        t   = s / TRAJ_STEPS
        val = math.sin(t * 4 * math.pi) * 0.4 + math.sin(t * 9 * math.pi) * 0.15
        x   = step_px(s)
        y   = traj_y - val * 28
        pts.append(f"{x:.1f},{y:.1f}")
    lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="1.5" opacity="0.7"/>')

    # Chunk quality color bars
    bar_h   = 18
    seg_w   = chart_w / N_CHUNKS
    for ci, q in enumerate(CHUNK_QUALITIES):
        x    = chunk_px(ci)
        # Color: green (good) → red (poor)
        if q >= 0.75:
            color = "#34d399"
        elif q >= 0.55:
            color = "#fbbf24"
        else:
            color = "#f87171"
        lines.append(f'<rect x="{x:.1f}" y="{chunk_bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}" opacity="{0.4 + q*0.5:.2f}"/>')
        if ci % 3 == 0:
            lines.append(f'<text x="{x + seg_w/2:.1f}" y="{chunk_bar_y+bar_h+12}" fill="#64748b" text-anchor="middle" font-size="9">{q:.2f}</text>')

    # Chunk boundary vertical lines
    for ci in range(1, N_CHUNKS):
        x     = chunk_px(ci)
        is_poor = (ci - 1) in POOR_CHUNKS or ci in POOR_CHUNKS
        color = "#f87171" if is_poor else "#475569"
        width = "2" if is_poor else "1"
        lines.append(f'<line x1="{x:.1f}" y1="{top+28}" x2="{x:.1f}" y2="{chunk_bar_y+bar_h}" stroke="{color}" stroke-width="{width}" stroke-dasharray="3 2" opacity="0.8"/>')
        if ci in POOR_CHUNKS:
            lines.append(f'<text x="{x:.1f}" y="{top+26}" fill="#f87171" text-anchor="middle" font-size="9">✗</text>')

    # Axis labels
    for s in range(0, 301, 50):
        x = step_px(s)
        lines.append(f'<line x1="{x:.1f}" y1="{chunk_bar_y+bar_h}" x2="{x:.1f}" y2="{chunk_bar_y+bar_h+4}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{chunk_bar_y+bar_h+16}" fill="#64748b" text-anchor="middle">t={s}</text>')

    # Legend
    for i, (label, color) in enumerate([("Good (≥0.75)","#34d399"),("OK (0.55-0.75)","#fbbf24"),("Poor (<0.55)","#f87171")]):
        lx = left + i * 190
        lines.append(f'<rect x="{lx}" y="{top}" width="10" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="{top+9}" fill="#94a3b8" font-size="10">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def svg_sr_vs_chunk() -> str:
    """Dual-axis line chart: SR and latency vs chunk size."""
    W, H = 760, 280
    left, right_margin = 60, 70
    top, bottom = 40, 50
    chart_h = H - top - bottom
    chart_w = W - left - right_margin

    n  = len(CHUNK_SWEEP)
    xs = [left + i * chart_w / (n - 1) for i in range(n)]

    sr_min, sr_max    = 0.65, 0.82
    lat_min, lat_max  = 0, 420

    def sr_y(sr):
        return top + chart_h - (sr - sr_min) / (sr_max - sr_min) * chart_h

    def lat_y(lat):
        return top + chart_h - (lat - lat_min) / (lat_max - lat_min) * chart_h

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="font-family:monospace;font-size:11px;">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Success Rate &amp; Latency vs Chunk Size</text>')

    # Y-axis left (SR)
    for sr in [0.65, 0.70, 0.75, 0.80]:
        y = sr_y(sr)
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W-right_margin}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{left-6}" y="{y+4:.1f}" fill="#38bdf8" text-anchor="end">{sr:.2f}</text>')
    lines.append(f'<text x="18" y="{top + chart_h//2}" fill="#38bdf8" text-anchor="middle" transform="rotate(-90 18 {top+chart_h//2})">SR</text>')

    # Y-axis right (latency)
    for lat in [0, 100, 200, 300, 400]:
        y = lat_y(lat)
        lines.append(f'<text x="{W-right_margin+6}" y="{y+4:.1f}" fill="#fbbf24">{lat}ms</text>')
    lines.append(f'<text x="{W-16}" y="{top+chart_h//2}" fill="#fbbf24" text-anchor="middle" transform="rotate(90 {W-16} {top+chart_h//2})">Latency</text>')

    # SR line
    sr_pts = " ".join(f"{xs[i]:.1f},{sr_y(d['sr']):.1f}" for i, d in enumerate(CHUNK_SWEEP))
    lines.append(f'<polyline points="{sr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # Latency line
    lat_pts = " ".join(f"{xs[i]:.1f},{lat_y(d['latency_ms']):.1f}" for i, d in enumerate(CHUNK_SWEEP))
    lines.append(f'<polyline points="{lat_pts}" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="6 3"/>')

    # Data points + labels
    for i, d in enumerate(CHUNK_SWEEP):
        x    = xs[i]
        sy   = sr_y(d["sr"])
        ly   = lat_y(d["latency_ms"])
        is_opt = d["chunk"] == OPTIMAL_CHUNK
        sr_color = "#C74634" if is_opt else "#38bdf8"
        lines.append(f'<circle cx="{x:.1f}" cy="{sy:.1f}" r="{5 if is_opt else 3}" fill="{sr_color}"/>')
        lines.append(f'<circle cx="{x:.1f}" cy="{ly:.1f}" r="3" fill="#fbbf24"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-8}" fill="#94a3b8" text-anchor="middle">{d["chunk"]}</text>')
        if is_opt:
            lines.append(f'<text x="{x+4:.1f}" y="{sy-10:.1f}" fill="#C74634" font-weight="bold" font-size="11">OPTIMAL</text>')
            lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+chart_h}" stroke="#C74634" stroke-width="1" stroke-dasharray="4 3" opacity="0.5"/>')
        lines.append(f'<text x="{x:.1f}" y="{sy-8:.1f}" fill="#64748b" text-anchor="middle" font-size="9">{d["sr"]}</text>')

    # X-axis label
    lines.append(f'<text x="{left + chart_w//2}" y="{H-2}" fill="#64748b" text-anchor="middle">Chunk Size (steps)</text>')

    # Legend
    lines.append(f'<line x1="{left+10}" y1="{top+8}" x2="{left+30}" y2="{top+8}" stroke="#38bdf8" stroke-width="2.5"/>')
    lines.append(f'<text x="{left+34}" y="{top+12}" fill="#94a3b8" font-size="10">Success Rate</text>')
    lines.append(f'<line x1="{left+10}" y1="{top+24}" x2="{left+30}" y2="{top+24}" stroke="#fbbf24" stroke-width="2" stroke-dasharray="6 3"/>')
    lines.append(f'<text x="{left+34}" y="{top+28}" fill="#94a3b8" font-size="10">Latency (ms)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    m      = compute_metrics()
    svg1   = svg_chunk_boundary()
    svg2   = svg_sr_vs_chunk()
    now    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    sweep_rows = ""
    for d in CHUNK_SWEEP:
        is_opt = d["chunk"] == OPTIMAL_CHUNK
        hl     = ' style="background:#1a2744"' if is_opt else ''
        badge  = ' <span style="color:#C74634;font-size:10px">★ OPTIMAL</span>' if is_opt else ''
        sweep_rows += f"""
        <tr{hl}>
          <td style="color:#e2e8f0;font-weight:{'700' if is_opt else '400'}">{d['chunk']}{badge}</td>
          <td style="color:#38bdf8">{d['sr']}</td>
          <td style="color:#fbbf24">{d['latency_ms']}ms</td>
          <td style="color:#94a3b8">{d['jerk']}</td>
          <td style="color:#34d399">{d['boundary_acc']}</td>
        </tr>"""

    bd_rows = ""
    for bd in BD_METHODS:
        is_best = bd["accuracy"] == m["best_bd_acc"]
        badge   = ' <span style="color:#34d399;font-size:10px">★ BEST</span>' if is_best else ''
        bd_rows += f"""
        <tr>
          <td style="color:#e2e8f0">{bd['name']}{badge}</td>
          <td style="color:#38bdf8">{bd['accuracy']}</td>
          <td style="color:#f87171">{bd['false_pos']}</td>
          <td style="color:#fbbf24">{bd['latency_ms']}ms</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Action Chunking V2 — Port 8277</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{font-size:22px;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .accent{{color:#C74634}}
    .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 20px;min-width:140px;flex:1}}
    .kpi .label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
    .kpi .value{{font-size:26px;font-weight:700;color:#38bdf8;margin-top:4px}}
    .kpi .value.warn{{color:#f87171}}
    .kpi .value.ok{{color:#34d399}}
    .kpi .value.neutral{{color:#fbbf24}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:20px}}
    .card h2{{font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:16px;text-transform:uppercase;letter-spacing:.05em}}
    .tables{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{color:#64748b;font-weight:500;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
    td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
    tr:hover td{{background:#0f172a}}
    footer{{color:#334155;font-size:11px;margin-top:24px;text-align:center}}
  </style>
</head>
<body>
  <h1>Action Chunking V2 <span class="accent">// GR00T Optimizer</span></h1>
  <div class="sub">Chunk size sweep &amp; boundary detection analysis &mdash; {now}</div>

  <div class="kpi-row">
    <div class="kpi"><div class="label">Optimal Chunk</div><div class="value">{m['optimal_chunk']} steps</div></div>
    <div class="kpi"><div class="label">SR @ Optimal</div><div class="value ok">{m['optimal_sr']}</div></div>
    <div class="kpi"><div class="label">Latency @ Opt</div><div class="value neutral">{m['optimal_lat']}ms</div></div>
    <div class="kpi"><div class="label">Boundary Acc.</div><div class="value ok">{m['boundary_acc']}</div></div>
    <div class="kpi"><div class="label">Poor Boundaries</div><div class="value warn">{m['poor_boundaries']}/ep</div></div>
    <div class="kpi"><div class="label">SR Sensitivity</div><div class="value neutral">{m['sr_sensitivity']}%</div></div>
  </div>

  <div class="card">
    <h2>Trajectory Chunk Boundaries (300 steps, chunk=16)</h2>
    {svg1}
  </div>

  <div class="card">
    <h2>Success Rate &amp; Latency vs Chunk Size</h2>
    {svg2}
  </div>

  <div class="tables">
    <div class="card">
      <h2>Chunk Size Sweep Results</h2>
      <table>
        <thead><tr><th>Chunk</th><th>SR</th><th>Latency</th><th>Jerk</th><th>Boundary Acc</th></tr></thead>
        <tbody>{sweep_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Boundary Detection Methods</h2>
      <table>
        <thead><tr><th>Method</th><th>Accuracy</th><th>False Pos</th><th>Latency</th></tr></thead>
        <tbody>{bd_rows}</tbody>
      </table>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; Action Chunking V2 &mdash; port 8277</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Action Chunking V2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/sweep")
    async def api_sweep():
        return {"sweep": CHUNK_SWEEP, "optimal_chunk": OPTIMAL_CHUNK}

    @app.get("/api/boundary_methods")
    async def api_boundary_methods():
        return {"methods": BD_METHODS}

    @app.get("/api/chunk_qualities")
    async def api_chunk_qualities():
        return {"qualities": CHUNK_QUALITIES, "poor_chunks": POOR_CHUNKS, "chunk_size": CHUNK_SIZE}

    @app.get("/api/metrics")
    async def api_metrics():
        return compute_metrics()

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8277, "service": "action_chunking_v2"}


# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------

if not USE_FASTAPI:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/sweep":
                body = json.dumps({"sweep": CHUNK_SWEEP, "optimal_chunk": OPTIMAL_CHUNK}).encode()
                ct   = "application/json"
            elif path == "/api/metrics":
                body = json.dumps(compute_metrics()).encode()
                ct   = "application/json"
            elif path == "/health":
                body = json.dumps({"status": "ok", "port": 8277}).encode()
                ct   = "application/json"
            else:
                body = build_html().encode()
                ct   = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8277)
    else:
        print("FastAPI not found — starting stdlib server on port 8277")
        server = HTTPServer(("0.0.0.0", 8277), _Handler)
        server.serve_forever()
