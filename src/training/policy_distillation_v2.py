"""Policy Distillation v2 — OCI Robot Cloud  (port 8189)"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math

# ---------------------------------------------------------------------------
# Static configuration data
# ---------------------------------------------------------------------------

V1_CONFIG = {
    "version": "v1",
    "temperature": 4.0,
    "alpha": 0.7,
    "feature_match": False,
    "intermediate_supervision": False,
    "feature_match_layers": [],
    "params_M": 300,
}

V2_CONFIG = {
    "version": "v2",
    "temperature": 6.0,
    "alpha": 0.6,
    "feature_match": True,
    "intermediate_supervision": True,
    "feature_match_layers": [8, 16, 24],
    "params_M": 300,
    "training_overhead_pct": 8,
}

TRAINING_STATUS = {
    "total_steps": 5000,
    "current_steps": 4000,
    "progress_pct": 80.0,
    "kd_loss": 0.071,
    "task_loss": 0.038,
    "feat_match_loss": 0.024,
    "total_loss": 0.133,
    "student_sr": 0.67,
    "teacher_sr": 0.78,
    "retention": 0.86,
    "retention_fraction": "67/78",
}

COMPRESSION = {
    "teacher_params_B": 3.0,
    "student_params_M": 300,
    "params_reduction": "10x",
    "size_reduction": "8.4x",
    "latency_reduction": "5x",
    "teacher_latency_ms": 226,
    "student_latency_jetson_ms": 45,
    "student_device": "Jetson Orin",
    "teacher_device": "A100 80GB",
}

SR_V1 = [
    (0, 0.10), (200, 0.18), (400, 0.25), (600, 0.31), (800, 0.36),
    (1000, 0.40), (1200, 0.44), (1400, 0.47), (1600, 0.50), (1800, 0.53),
    (2000, 0.58), (2200, 0.60), (2400, 0.62), (2600, 0.63), (2800, 0.64),
    (3000, 0.65), (3200, 0.655), (3400, 0.66), (3600, 0.661), (3800, 0.662),
    (4000, 0.663),
]

SR_V2 = [
    (0, 0.10), (200, 0.21), (400, 0.30), (600, 0.37), (800, 0.43),
    (1000, 0.48), (1200, 0.53), (1400, 0.57), (1600, 0.60), (1800, 0.64),
    (2000, 0.67), (2200, 0.695), (2400, 0.71), (2600, 0.72), (2800, 0.73),
    (3000, 0.74), (3200, 0.745), (3400, 0.75), (3600, 0.752), (3800, 0.753),
    (4000, 0.754),
]

TEACHER_SR = 0.78

# Loss components over 4000 steps (exponential decay approximation)
def _loss_series(steps: int, init: float, final: float):
    """Generate a smooth exponential decay series with minor noise."""
    series = []
    for i in range(steps + 1):
        t = i / steps
        # exponential decay
        val = final + (init - final) * math.exp(-4.5 * t)
        # add tiny deterministic variation using sin
        val += 0.003 * math.sin(i * 0.31) * (1 - t)
        series.append(round(max(val, 0.005), 4))
    return series

LOSS_STEPS = list(range(0, 4001, 200))  # 21 data points
KD_LOSS   = _loss_series(20, 0.45,  0.071)
TASK_LOSS = _loss_series(20, 0.28,  0.038)
FEAT_LOSS = _loss_series(20, 0.18,  0.024)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _loss_area_svg(width: int = 680, height: int = 220) -> str:
    pad_l, pad_r, pad_t, pad_b = 48, 20, 30, 40
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    n = len(LOSS_STEPS)
    max_loss = 0.50

    def px(step_idx: int) -> int:
        return pad_l + int(step_idx / (n - 1) * chart_w)

    def py(val: float) -> int:
        return pad_t + chart_h - int(val / max_loss * chart_h)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px">')
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Loss Components over Training Steps</text>')

    # Grid
    for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
        y = py(v)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{pad_l+chart_w}" y2="{y}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4}" text-anchor="end" fill="#475569" font-size="9" font-family="monospace">{v}</text>')

    # X-axis labels
    for i, s in enumerate(LOSS_STEPS):
        if s % 1000 == 0:
            x = px(i)
            lines.append(f'<text x="{x}" y="{pad_t+chart_h+14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{s}</text>')

    # Fill areas (stacked)
    def area_path(series, baseline_series=None):
        fwd = ' '.join(f'{px(i)},{py(v)}' for i, v in enumerate(series))
        if baseline_series:
            rev = ' '.join(f'{px(i)},{py(v)}' for i, v in reversed(list(enumerate(baseline_series))))
            return f'M {fwd} L {rev} Z'
        else:
            bot_y = py(0)
            rev = ' '.join(f'{px(i)},{bot_y}' for i in reversed(range(n)))
            return f'M {fwd} L {rev} Z'

    # Area: feat_match (bottom)
    lines.append(f'<path d="{area_path(FEAT_LOSS)}" fill="#7c3aed" opacity="0.55"/>')
    # Area: task stacked on feat
    task_stacked = [FEAT_LOSS[i] + TASK_LOSS[i] for i in range(n)]
    lines.append(f'<path d="{area_path(task_stacked, FEAT_LOSS)}" fill="#f59e0b" opacity="0.55"/>')
    # Area: kd stacked on task
    kd_stacked = [task_stacked[i] + KD_LOSS[i] for i in range(n)]
    lines.append(f'<path d="{area_path(kd_stacked, task_stacked)}" fill="#38bdf8" opacity="0.55"/>')

    # Lines on top
    def polyline(series, color):
        pts = ' '.join(f'{px(i)},{py(v)}' for i, v in enumerate(series))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'

    lines.append(polyline(FEAT_LOSS, "#a78bfa"))
    lines.append(polyline(task_stacked, "#fbbf24"))
    lines.append(polyline(kd_stacked, "#38bdf8"))

    # Legend
    for i, (label, color) in enumerate([("kd_loss", "#38bdf8"), ("task_loss", "#fbbf24"), ("feat_match_loss", "#a78bfa")]):
        lx = pad_l + i * 160
        ly = height - 8
        lines.append(f'<rect x="{lx}" y="{ly-9}" width="12" height="9" fill="{color}" opacity="0.8"/>')
        lines.append(f'<text x="{lx+15}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _sr_compare_svg(width: int = 680, height: int = 180) -> str:
    pad_l, pad_r, pad_t, pad_b = 48, 20, 30, 40
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    max_steps = 4000
    max_sr = 0.85

    def px(step: int) -> int:
        return pad_l + int(step / max_steps * chart_w)

    def py(sr: float) -> int:
        return pad_t + chart_h - int(sr / max_sr * chart_h)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px">')
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">v1 vs v2 Student Success Rate vs Steps</text>')

    # Grid
    for sr in [0.2, 0.4, 0.6, 0.78]:
        y = py(sr)
        dash = "4,4" if sr != 0.78 else "6,3"
        clr = "#1e293b" if sr != 0.78 else "#334155"
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{pad_l+chart_w}" y2="{y}" stroke="{clr}" stroke-dasharray="{dash}" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4}" text-anchor="end" fill="#475569" font-size="9" font-family="monospace">{sr}</text>')

    # Teacher SR dashed line
    ty = py(TEACHER_SR)
    lines.append(f'<line x1="{pad_l}" y1="{ty}" x2="{pad_l+chart_w}" y2="{ty}" stroke="#94a3b8" stroke-dasharray="6,3" stroke-width="1.5"/>')
    lines.append(f'<text x="{pad_l+chart_w+2}" y="{ty+4}" fill="#94a3b8" font-size="9" font-family="monospace">teacher 0.78</text>')

    # X ticks
    for s in [0, 1000, 2000, 3000, 4000]:
        x = px(s)
        lines.append(f'<text x="{x}" y="{pad_t+chart_h+14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{s}</text>')

    # v1 line
    pts_v1 = ' '.join(f'{px(s)},{py(sr)}' for s, sr in SR_V1)
    lines.append(f'<polyline points="{pts_v1}" fill="none" stroke="#C74634" stroke-width="2.5"/>')

    # v2 line
    pts_v2 = ' '.join(f'{px(s)},{py(sr)}' for s, sr in SR_V2)
    lines.append(f'<polyline points="{pts_v2}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # Gap annotation at step 2000
    gx = px(2000)
    y_v1 = py(0.58)
    y_v2 = py(0.67)
    mid_y = (y_v1 + y_v2) // 2
    lines.append(f'<line x1="{gx+4}" y1="{y_v1}" x2="{gx+4}" y2="{y_v2}" stroke="#4ade80" stroke-width="1.5" marker-end="url(#arr)"/>')
    lines.append(f'<text x="{gx+8}" y="{mid_y+4}" fill="#4ade80" font-size="10" font-family="monospace" font-weight="bold">+9pp</text>')

    # Legend
    legend_items = [("v1", "#C74634"), ("v2", "#38bdf8"), ("teacher (dashed)", "#94a3b8")]
    lx = pad_l
    for label, color in legend_items:
        lines.append(f'<line x1="{lx}" y1="{height-10}" x2="{lx+18}" y2="{height-10}" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{lx+22}" y="{height-6}" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')
        lx += len(label) * 7 + 36

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Policy Distillation v2", version="2.0.0")
else:
    app = None  # type: ignore


def _dashboard_html() -> str:
    loss_svg = _loss_area_svg()
    sr_svg   = _sr_compare_svg()
    st = TRAINING_STATUS
    c  = COMPRESSION

    progress_bar_w = int(st["progress_pct"] * 4.0)  # max ~400px

    comp_rows = [
        ("Model parameters",  f"{c['teacher_params_B']}B (teacher)", f"{c['student_params_M']}M (student)", c["params_reduction"]),
        ("Model size",        "~24 GB",  "~2.85 GB",  c["size_reduction"]),
        ("Inference latency", f"{c['teacher_latency_ms']}ms ({c['teacher_device']})",
                              f"{c['student_latency_jetson_ms']}ms ({c['student_device']})",
                              c["latency_reduction"]),
    ]

    comp_html = "".join(f"""
        <tr>
          <td style='padding:8px 12px;color:#94a3b8'>{r[0]}</td>
          <td style='padding:8px 12px;color:#e2e8f0'>{r[1]}</td>
          <td style='padding:8px 12px;color:#4ade80'>{r[2]}</td>
          <td style='padding:8px 12px;color:#38bdf8;font-weight:bold'>{r[3]}</td>
        </tr>""" for r in comp_rows)

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Policy Distillation v2 — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px; }}
    h1 {{ color:#38bdf8; font-size:22px; margin-bottom:4px; }}
    .subtitle {{ color:#64748b; font-size:13px; margin-bottom:24px; }}
    .card {{ background:#1e293b; border-radius:10px; padding:20px; margin-bottom:20px; }}
    h2 {{ color:#C74634; font-size:15px; margin:0 0 14px 0; }}
    table {{ border-collapse:collapse; width:100%; }}
    th {{ background:#0f172a; color:#94a3b8; padding:8px 12px; text-align:left; font-size:12px; }}
    tr:hover td {{ background:#263148; }}
    .progress-bg {{ background:#0f172a; border-radius:6px; height:18px; width:400px; overflow:hidden; }}
    .progress-fg {{ background:#38bdf8; height:18px; border-radius:6px; }}
    .kv {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:12px; }}
    .kv-item {{ background:#0f172a; border-radius:6px; padding:10px; }}
    .kv-label {{ color:#64748b; font-size:10px; }}
    .kv-value {{ color:#e2e8f0; font-size:16px; font-weight:bold; margin-top:4px; }}
    .note {{ color:#64748b; font-size:12px; margin-top:10px; }}
  </style>
</head>
<body>
  <h1>Policy Distillation v2</h1>
  <div class='subtitle'>OCI Robot Cloud — Knowledge Transfer Pipeline — Port 8189</div>

  <div class='card'>
    <h2>Training Progress</h2>
    <div class='kv'>
      <div class='kv-item'><div class='kv-label'>Steps</div><div class='kv-value'>{st['current_steps']}/{st['total_steps']}</div></div>
      <div class='kv-item'><div class='kv-label'>Total Loss</div><div class='kv-value' style='color:#38bdf8'>{st['total_loss']}</div></div>
      <div class='kv-item'><div class='kv-label'>Student SR</div><div class='kv-value' style='color:#4ade80'>{st['student_sr']}</div></div>
      <div class='kv-item'><div class='kv-label'>Teacher SR</div><div class='kv-value' style='color:#C74634'>{st['teacher_sr']}</div></div>
    </div>
    <div style='margin-bottom:6px;color:#64748b;font-size:12px'>Progress: {st['progress_pct']}%</div>
    <div class='progress-bg'><div class='progress-fg' style='width:{progress_bar_w}px'></div></div>
    <p class='note'>Retention: {st['retention']} ({st['retention_fraction']} of teacher SR achieved)</p>
  </div>

  <div class='card'>
    <h2>Loss Component Breakdown</h2>
    {loss_svg}
    <p class='note'>Stacked areas: feat_match_loss (purple) + task_loss (amber) + kd_loss (sky) = total_loss trajectory.</p>
  </div>

  <div class='card'>
    <h2>v1 vs v2 — Student SR Comparison</h2>
    {sr_svg}
    <p class='note'>v2 gains +9pp SR at step 2000 vs v1 (0.67 vs 0.58). Feature matching layers: [8, 16, 24]. Training overhead: +8%.</p>
  </div>

  <div class='card'>
    <h2>Compression Metrics</h2>
    <table>
      <thead><tr><th>Metric</th><th>Teacher</th><th>Student</th><th>Reduction</th></tr></thead>
      <tbody>{comp_html}</tbody>
    </table>
  </div>

  <div class='card'>
    <h2>API Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/</td><td>This dashboard</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/status</td><td>Current training status (JSON)</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/compare</td><td>v1 vs v2 config + SR comparison</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/metrics</td><td>Full metrics + compression table</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>"""


if app is not None:
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/status")
    def get_status():
        return JSONResponse({
            "training": TRAINING_STATUS,
            "config_v2": V2_CONFIG,
        })

    @app.get("/compare")
    def get_compare():
        v1_sr_at_2k = dict(SR_V1).get(2000, 0.58)
        v2_sr_at_2k = dict(SR_V2).get(2000, 0.67)
        return JSONResponse({
            "v1": {
                "config": V1_CONFIG,
                "sr_at_2000_steps": v1_sr_at_2k,
                "sr_series": SR_V1,
            },
            "v2": {
                "config": V2_CONFIG,
                "sr_at_2000_steps": v2_sr_at_2k,
                "sr_series": SR_V2,
            },
            "delta_sr_at_2000_steps": round(v2_sr_at_2k - v1_sr_at_2k, 4),
            "teacher_sr": TEACHER_SR,
        })

    @app.get("/metrics")
    def get_metrics():
        return JSONResponse({
            "training_status": TRAINING_STATUS,
            "compression": COMPRESSION,
            "loss_series": {
                "steps": LOSS_STEPS,
                "kd_loss": KD_LOSS,
                "task_loss": TASK_LOSS,
                "feat_match_loss": FEAT_LOSS,
                "total_loss": [round(KD_LOSS[i] + TASK_LOSS[i] + FEAT_LOSS[i], 4) for i in range(len(LOSS_STEPS))],
            },
        })


if __name__ == "__main__":
    if uvicorn and app:
        uvicorn.run(app, host="0.0.0.0", port=8189)
    else:
        print("FastAPI/uvicorn not installed. pip install fastapi uvicorn")
