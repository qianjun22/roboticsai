"""Inference Optimization Controller — OCI Robot Cloud (port 8199)

Manages TensorRT, quantization, and batching optimizations for the
GR00T N1.6 inference pipeline. Tracks current status and roadmap.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import json

# ---------------------------------------------------------------------------
# Static data — 4 optimization techniques
# ---------------------------------------------------------------------------

TECHNIQUES = [
    {
        "name": "fp16_inference",
        "label": "FP16 Inference",
        "status": "ENABLED",
        "speedup": "2.1x",
        "speedup_factor": 2.1,
        "memory_reduction": 0.46,
        "sr_impact": 0.0,
        "implementation_eta": None,
        "notes": "Enabled since Feb 2026",
    },
    {
        "name": "dynamic_batching",
        "label": "Dynamic Batching",
        "status": "ENABLED",
        "speedup": "1.3x throughput",
        "speedup_factor": 1.3,
        "memory_reduction": 0.0,
        "sr_impact": 0.0,
        "implementation_eta": None,
        "notes": "Batch 1-4 dynamically; solo requests unaffected",
    },
    {
        "name": "tensorrt_vit",
        "label": "TensorRT ViT",
        "status": "PLANNED",
        "speedup": "1.4x estimate",
        "speedup_factor": 1.4,
        "memory_reduction": 0.12,
        "sr_impact": 0.0,
        "implementation_eta": "May 2026",
        "notes": "",
    },
    {
        "name": "fp8_quantization",
        "label": "FP8 Quantization",
        "status": "PLANNED",
        "speedup": "1.6x estimate",
        "speedup_factor": 1.6,
        "memory_reduction": 0.50,
        "sr_impact": -0.01,
        "implementation_eta": "June 2026",
        "notes": "Minor SR drop expected; needs calibration dataset",
    },
]

# Latency roadmap (ms)
ROADMAP = [
    {"stage": "FP32 Baseline", "latency_ms": 412, "status": "historical", "throughput_rps": 2.43},
    {"stage": "FP16 (current)", "latency_ms": 226, "status": "current", "throughput_rps": 4.42},
    {"stage": "+ TensorRT ViT", "latency_ms": 161, "status": "planned", "throughput_rps": 6.21},
    {"stage": "+ FP8 Quant", "latency_ms": 100, "status": "planned", "throughput_rps": 10.0},
]

CURRENT_STATS = {
    "latency_ms": 226,
    "throughput_rps": 4.42,
    "gpu_utilization": 0.87,
    "memory_used_gb": 6.7,
    "model": "GR00T N1.6",
    "precision": "fp16",
    "batch_mode": "dynamic 1-4",
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _waterfall_svg() -> str:
    """680×220 SVG: horizontal latency waterfall from FP32 baseline to FP8 target."""
    W, H = 680, 220
    PAD_LEFT = 140
    PAD_RIGHT = 20
    PAD_TOP = 40
    BAR_H = 32
    BAR_GAP = 14
    CHART_W = W - PAD_LEFT - PAD_RIGHT
    MAX_MS = 450

    def ms_to_x(ms: float) -> float:
        return PAD_LEFT + (ms / MAX_MS) * CHART_W

    colors = {
        "historical": "#475569",
        "current": "#38bdf8",
        "planned": "#f59e0b",
    }
    status_label = {
        "historical": "BASELINE",
        "current": "ENABLED",
        "planned": "PLANNED",
    }

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#0f172a;font-family:monospace">']
    lines.append(f'<text x="{W//2}" y="16" text-anchor="middle" fill="#38bdf8" '
                 f'font-size="12" font-weight="bold">Inference Latency Waterfall (ms)</text>')

    # Grid lines every 100ms
    for ms in range(0, MAX_MS + 1, 100):
        gx = ms_to_x(ms)
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_TOP}" x2="{gx:.1f}" y2="{H - 20}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{gx:.1f}" y="{H - 8}" text-anchor="middle" '
                     f'fill="#475569" font-size="9">{ms}ms</text>')

    for i, stage in enumerate(ROADMAP):
        y = PAD_TOP + i * (BAR_H + BAR_GAP)
        bar_w = ms_to_x(stage["latency_ms"]) - PAD_LEFT
        color = colors[stage["status"]]
        opacity = "1.0" if stage["status"] == "current" else "0.75"

        # Bar
        lines.append(f'<rect x="{PAD_LEFT}" y="{y}" width="{bar_w:.1f}" height="{BAR_H}" '
                     f'fill="{color}" opacity="{opacity}" rx="3"/>')

        # Stage label (left)
        lines.append(f'<text x="{PAD_LEFT - 5}" y="{y + BAR_H//2 + 4}" text-anchor="end" '
                     f'fill="#94a3b8" font-size="9">{stage["stage"]}</text>')

        # ms label (inside or right of bar)
        lx = PAD_LEFT + bar_w - 6 if bar_w > 60 else PAD_LEFT + bar_w + 6
        anchor = "end" if bar_w > 60 else "start"
        txt_fill = "#0f172a" if bar_w > 60 else color
        lines.append(f'<text x="{lx:.1f}" y="{y + BAR_H//2 + 4}" text-anchor="{anchor}" '
                     f'fill="{txt_fill}" font-size="10" font-weight="bold">{stage["latency_ms"]}ms</text>')

        # Status badge
        badge_label = status_label[stage["status"]]
        bx = ms_to_x(stage["latency_ms"]) + 8
        lines.append(f'<text x="{bx:.1f}" y="{y + BAR_H//2 + 4}" fill="{color}" '
                     f'font-size="9">{badge_label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _throughput_bar_svg() -> str:
    """380×160 SVG: bar chart comparing current vs TensorRT vs FP8 throughput."""
    W, H = 380, 160
    PAD_LEFT = 40
    PAD_BOTTOM = 36
    CHART_H = H - PAD_BOTTOM - 20
    stages = [("FP16\n(now)", 4.42, "#38bdf8"),
              ("+ TRT\n(planned)", 6.21, "#f59e0b"),
              ("+ FP8\n(planned)", 10.0, "#4ade80")]
    max_v = 12.0
    bar_w = (W - PAD_LEFT - 20) // len(stages) - 10

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#1e293b;font-family:monospace">']
    lines.append(f'<text x="{W//2}" y="14" text-anchor="middle" fill="#38bdf8" '
                 f'font-size="11" font-weight="bold">Throughput (req/s)</text>')

    for i, (label, val, color) in enumerate(stages):
        bh = int((val / max_v) * CHART_H)
        bx = PAD_LEFT + i * (bar_w + 10)
        by = 20 + CHART_H - bh
        lines.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" '
                     f'fill="{color}" opacity="0.85" rx="3"/>')
        lines.append(f'<text x="{bx + bar_w//2}" y="{by - 4}" text-anchor="middle" '
                     f'fill="{color}" font-size="10" font-weight="bold">{val}</text>')
        # Label lines
        for li, line in enumerate(label.split("\n")):
            lines.append(f'<text x="{bx + bar_w//2}" y="{20 + CHART_H + 14 + li*12}" '
                         f'text-anchor="middle" fill="#94a3b8" font-size="9">{line}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    waterfall = _waterfall_svg()
    throughput_chart = _throughput_bar_svg()

    STATUS_COLORS = {"ENABLED": "#4ade80", "PLANNED": "#f59e0b"}
    STATUS_BG = {"ENABLED": "#14532d", "PLANNED": "#431a00"}

    tech_rows = ""
    for t in TECHNIQUES:
        sc = STATUS_COLORS.get(t["status"], "#94a3b8")
        bg = STATUS_BG.get(t["status"], "#1e293b")
        sr = f"{t['sr_impact']:+.0%}" if t["sr_impact"] != 0 else "0.0%"
        eta = t["implementation_eta"] or "—"
        mem = f"-{int(t['memory_reduction']*100)}%" if t["memory_reduction"] > 0 else "—"
        tech_rows += f"""
        <tr>
          <td style="color:#e2e8f0;font-weight:bold">{t['label']}</td>
          <td><span style="background:{bg};color:{sc};padding:2px 7px;border-radius:4px;font-size:11px">{t['status']}</span></td>
          <td style="color:{sc}">{t['speedup']}</td>
          <td style="color:#94a3b8">{mem}</td>
          <td style="color:{'#C74634' if t['sr_impact'] < 0 else '#4ade80'}">{sr}</td>
          <td style="color:#64748b;font-size:11px">{eta}</td>
          <td style="color:#64748b;font-size:11px">{t['notes']}</td>
        </tr>"""

    roadmap_rows = ""
    for r in ROADMAP:
        sc = {"historical": "#475569", "current": "#38bdf8", "planned": "#f59e0b"}[r["status"]]
        roadmap_rows += f"""
        <tr>
          <td style="color:{sc}">{r['stage']}</td>
          <td style="color:{sc};font-weight:bold">{r['latency_ms']} ms</td>
          <td style="color:#94a3b8">{r['throughput_rps']} req/s</td>
          <td><span style="color:{sc};font-size:11px">{r['status'].upper()}</span></td>
        </tr>"""

    s = CURRENT_STATS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inference Optimizer — OCI Robot Cloud</title>
  <style>
    body {{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
    h1 {{color:#C74634;margin:0 0 4px}}
    h2 {{color:#38bdf8;font-size:14px;margin:18px 0 8px}}
    .badge {{background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:4px;font-size:11px}}
    table {{border-collapse:collapse;width:100%;margin-bottom:12px}}
    th {{text-align:left;color:#475569;font-size:11px;padding:4px 10px;border-bottom:1px solid #1e293b}}
    td {{padding:6px 10px;border-bottom:1px solid #0f172a;font-size:12px}}
    tr:hover td {{background:#1e293b}}
    .grid {{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:12px}}
    .card {{background:#1e293b;border-radius:8px;padding:14px}}
    .stat {{font-size:26px;font-weight:bold;color:#38bdf8}}
    .stat-label {{font-size:11px;color:#64748b}}
    .stats-row {{display:flex;gap:24px;margin-bottom:16px;flex-wrap:wrap}}
  </style>
</head>
<body>
  <h1>Inference Optimization Controller</h1>
  <p style="color:#64748b;margin:0 0 16px">Port 8199 &nbsp;|&nbsp; <span class="badge">{s['model']}</span> &nbsp;|&nbsp; <span class="badge">{s['precision'].upper()}</span> &nbsp;|&nbsp; <span class="badge">Batch: {s['batch_mode']}</span></p>

  <div class="stats-row">
    <div><div class="stat">{s['latency_ms']} ms</div><div class="stat-label">Current Latency</div></div>
    <div><div class="stat">{s['throughput_rps']}</div><div class="stat-label">req/s Throughput</div></div>
    <div><div class="stat" style="color:#4ade80">{int(s['gpu_utilization']*100)}%</div><div class="stat-label">GPU Utilization</div></div>
    <div><div class="stat" style="color:#f59e0b">{s['memory_used_gb']} GB</div><div class="stat-label">VRAM Used</div></div>
    <div><div class="stat" style="color:#f59e0b">161 ms</div><div class="stat-label">Target (TensorRT)</div></div>
    <div><div class="stat" style="color:#4ade80">100 ms</div><div class="stat-label">Target (FP8)</div></div>
  </div>

  <h2>Optimization Techniques</h2>
  <table>
    <thead><tr><th>Technique</th><th>Status</th><th>Speedup</th><th>Memory</th><th>SR Impact</th><th>ETA</th><th>Notes</th></tr></thead>
    <tbody>{tech_rows}</tbody>
  </table>

  <div class="grid">
    <div class="card">
      <h2 style="margin-top:0">Latency Waterfall</h2>
      {waterfall}
    </div>
    <div class="card">
      <h2 style="margin-top:0">Throughput Roadmap</h2>
      {throughput_chart}
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <h2 style="margin-top:0">Optimization Roadmap</h2>
    <table>
      <thead><tr><th>Stage</th><th>Latency</th><th>Throughput</th><th>Status</th></tr></thead>
      <tbody>{roadmap_rows}</tbody>
    </table>
  </div>

  <p style="color:#1e3a5f;font-size:10px;margin-top:20px">OCI Robot Cloud &copy; 2026 Oracle Corporation</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="Inference Optimization Controller",
        description="Manages TensorRT, quantization, and batching for OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/techniques")
    def get_techniques():
        return JSONResponse({"techniques": TECHNIQUES})

    @app.get("/roadmap")
    def get_roadmap():
        return JSONResponse({"roadmap": ROADMAP})

    @app.get("/current-stats")
    def current_stats():
        return JSONResponse(CURRENT_STATS)

else:
    app = None


if __name__ == "__main__":
    if uvicorn and app:
        uvicorn.run(app, host="0.0.0.0", port=8199)
    else:
        print("FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn")
