"""OCI Robot Cloud — Knowledge Distillation Pipeline Tracker
Port 8145 | Compress groot_finetune_v2 (3B) → student (300M)
"""
from __future__ import annotations

import math
import json
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
TEACHER: dict[str, Any] = {
    "name": "groot_finetune_v2",
    "params_B": 3.0,
    "latency_ms": 226,
    "success_rate": 0.78,
    "size_GB": 6.7,
}

STUDENT: dict[str, Any] = {
    "name": "groot_student_v1",
    "params_B": 0.3,
    "target_latency_ms": 45,
    "target_success_rate": 0.72,
    "target_size_GB": 0.8,
    "current_success_rate": 0.58,  # eval at step 1000
}

DIST_CONFIG: dict[str, Any] = {
    "temperature": 4.0,
    "alpha": 0.7,    # KD loss weight
    "beta": 0.3,     # task loss weight
    "feature_matching": True,
    "feature_layers": [6, 12, 18, 24],
}

TRAINING: dict[str, Any] = {
    "total_steps": 5000,
    "current_step": 2000,
    "student_loss": 0.134,
    "kd_loss": 0.089,
    "task_loss": 0.045,
}

COMPRESSION: dict[str, Any] = {
    "params_ratio": 10.0,
    "latency_ratio": 5.0,
    "size_ratio": 8.4,
    "sr_retention_target_pct": 92.3,  # 0.72 / 0.78
}


# ---------------------------------------------------------------------------
# Loss curve generation (seeded exponential decay)
# ---------------------------------------------------------------------------
def _loss_curve(steps: int, init: float, floor: float, decay: float, noise_seed: int) -> list[float]:
    """Generate a smooth exponential decay with tiny deterministic noise."""
    vals: list[float] = []
    # Simple LCG for deterministic noise
    r = noise_seed
    for i in range(steps):
        r = (r * 1664525 + 1013904223) & 0xFFFFFFFF
        noise = ((r / 0xFFFFFFFF) - 0.5) * 0.004
        v = floor + (init - floor) * math.exp(-decay * i) + noise
        vals.append(max(v, floor))
    return vals


STEPS_RECORDED = 2000
_total_curve = _loss_curve(STEPS_RECORDED, 0.52, 0.10, 0.0018, 42)
_kd_curve = _loss_curve(STEPS_RECORDED, 0.35, 0.07, 0.0018, 7)
_task_curve = _loss_curve(STEPS_RECORDED, 0.17, 0.03, 0.0018, 99)


# ---------------------------------------------------------------------------
# SVG: loss curves
# ---------------------------------------------------------------------------
def _build_loss_svg() -> str:
    W, H = 680, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 30, 36
    CW = W - PAD_L - PAD_R
    CH = H - PAD_T - PAD_B

    curves = [
        ("Total Loss", _total_curve, "#38bdf8"),
        ("KD Loss", _kd_curve, "#f59e0b"),
        ("Task Loss", _task_curve, "#C74634"),
    ]

    all_vals = [v for _, c, _ in curves for v in c]
    y_min, y_max = min(all_vals) * 0.95, max(all_vals) * 1.05

    def sx(step: int) -> float:
        return PAD_L + step / (STEPS_RECORDED - 1) * CW

    def sy(val: float) -> float:
        return PAD_T + CH - (val - y_min) / (y_max - y_min) * CH

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )
    lines.append(
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Distillation Loss Curves (steps 0–{STEPS_RECORDED})</text>'
    )

    # Grid
    for tick in [0.1, 0.2, 0.3, 0.4, 0.5]:
        if y_min <= tick <= y_max:
            ty = sy(tick)
            lines.append(
                f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{W-PAD_R}" y2="{ty:.1f}" '
                f'stroke="#1e293b" stroke-width="1"/>'
            )
            lines.append(
                f'<text x="{PAD_L-4}" y="{ty+4:.1f}" fill="#475569" font-size="8" '
                f'text-anchor="end">{tick:.1f}</text>'
            )

    # X axis ticks
    for step_t in [0, 500, 1000, 1500, 2000]:
        tx = sx(step_t)
        lines.append(
            f'<line x1="{tx:.1f}" y1="{PAD_T}" x2="{tx:.1f}" y2="{PAD_T+CH}" '
            f'stroke="#1e293b" stroke-width="0.5" stroke-dasharray="2,3"/>'
        )
        lines.append(
            f'<text x="{tx:.1f}" y="{H-8}" fill="#475569" font-size="8" text-anchor="middle">{step_t}</text>'
        )

    # Downsample for polyline (every 20 steps)
    stride = 20
    for label, curve, color in curves:
        pts = " ".join(
            f"{sx(i):.1f},{sy(curve[i]):.1f}"
            for i in range(0, len(curve), stride)
        )
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8"/>')

    # Legend
    lx = PAD_L + 10
    for k, (label, _, color) in enumerate(curves):
        lines.append(f'<rect x="{lx}" y="{PAD_T+4}" width="14" height="4" fill="{color}" rx="2"/>')
        lines.append(
            f'<text x="{lx+18}" y="{PAD_T+10}" fill="{color}" font-size="9">{label}</text>'
        )
        lx += 90

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG: compression metrics bars
# ---------------------------------------------------------------------------
def _build_compression_svg() -> str:
    W, H = 680, 180
    METRICS = [
        {
            "label": "Params (B)",
            "teacher": TEACHER["params_B"],
            "student": STUDENT["params_B"],
            "target": STUDENT["params_B"],
            "unit": "B",
            "color": "#38bdf8",
        },
        {
            "label": "Latency (ms)",
            "teacher": TEACHER["latency_ms"],
            "student": TEACHER["latency_ms"] * 0.65,  # partial progress
            "target": STUDENT["target_latency_ms"],
            "unit": "ms",
            "color": "#f59e0b",
        },
        {
            "label": "Size (GB)",
            "teacher": TEACHER["size_GB"],
            "student": TEACHER["size_GB"] * 0.6,  # partial progress
            "target": STUDENT["target_size_GB"],
            "unit": "GB",
            "color": "#a78bfa",
        },
        {
            "label": "Success Rate",
            "teacher": TEACHER["success_rate"],
            "student": STUDENT["current_success_rate"],
            "target": STUDENT["target_success_rate"],
            "unit": "",
            "color": "#22c55e",
        },
    ]

    PAD_L, PAD_T = 110, 28
    METRIC_W = (W - PAD_L - 20) // len(METRICS)
    BAR_MAX_H = H - PAD_T - 40
    BAR_W = 22

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )
    lines.append(
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Compression Metrics: Teacher vs Student</text>'
    )

    for i, m in enumerate(METRICS):
        cx = PAD_L + i * METRIC_W + METRIC_W // 2
        ref = m["teacher"]

        def bar_h(val: float) -> float:
            return max(val / ref * BAR_MAX_H, 2.0)

        # Teacher bar
        th = bar_h(m["teacher"])
        lines.append(
            f'<rect x="{cx - BAR_W - 3}" y="{PAD_T + BAR_MAX_H - th:.1f}" '
            f'width="{BAR_W}" height="{th:.1f}" fill="{m['color']}" opacity="0.4" rx="2"/>'
        )
        lines.append(
            f'<text x="{cx - BAR_W//2 - 3}" y="{PAD_T + BAR_MAX_H - th - 3:.1f}" '
            f'fill="{m['color']}" font-size="7" text-anchor="middle">{m["teacher"]}{m["unit"]}</text>'
        )

        # Student bar (current)
        sh = bar_h(m["student"])
        lines.append(
            f'<rect x="{cx + 3}" y="{PAD_T + BAR_MAX_H - sh:.1f}" '
            f'width="{BAR_W}" height="{sh:.1f}" fill="{m['color']}" rx="2"/>'
        )
        lines.append(
            f'<text x="{cx + BAR_W//2 + 3}" y="{PAD_T + BAR_MAX_H - sh - 3:.1f}" '
            f'fill="{m['color']}" font-size="7" text-anchor="middle">{m["student"]:.2f}{m["unit"]}</text>'
        )

        # Dashed target line
        th_target = bar_h(m["target"])
        ty = PAD_T + BAR_MAX_H - th_target
        lines.append(
            f'<line x1="{cx-BAR_W-8}" y1="{ty:.1f}" x2="{cx+BAR_W+12}" y2="{ty:.1f}" '
            f'stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2"/>'
        )
        lines.append(
            f'<text x="{cx+BAR_W+14}" y="{ty+3:.1f}" fill="#22c55e" font-size="7">T</text>'
        )

        # Metric label
        lines.append(
            f'<text x="{cx}" y="{PAD_T + BAR_MAX_H + 14}" fill="#94a3b8" '
            f'font-size="9" text-anchor="middle">{m["label"]}</text>'
        )

    # Legend
    lx = PAD_L
    ly = H - 8
    for label, color, opacity in [("Teacher", "#94a3b8", "0.4"), ("Student (current)", "#94a3b8", "1"), ("Target", "#22c55e", "1")]:
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="10" height="8" fill="{color}" opacity="{opacity}" rx="1"/>')
        lines.append(f'<text x="{lx+13}" y="{ly}" fill="#94a3b8" font-size="8">{label}</text>')
        lx += 110

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace; }
.header { background: #1e293b; border-bottom: 2px solid #C74634;
          padding: 14px 28px; display: flex; align-items: center; gap: 16px; }
.header h1 { font-size: 18px; color: #f1f5f9; }
.badge { background: #C74634; color: #fff; padding: 2px 10px;
         border-radius: 999px; font-size: 11px; font-weight: bold; }
.main { padding: 24px 28px; }
.progress-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
                 padding: 16px 20px; margin-bottom: 20px; }
.progress-wrap h2 { font-size: 13px; color: #38bdf8; margin-bottom: 10px; }
.prog-bar-bg { background: #0f172a; border-radius: 999px; height: 16px;
               border: 1px solid #334155; overflow: hidden; }
.prog-bar-fg { height: 100%; border-radius: 999px;
               background: linear-gradient(90deg, #C74634, #f97316); }
.prog-meta { display: flex; justify-content: space-between;
             font-size: 11px; color: #64748b; margin-top: 6px; }
.cards { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 20px; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
        padding: 16px 18px; }
.card .label { color: #64748b; font-size: 11px; text-transform: uppercase;
               letter-spacing: .08em; margin-bottom: 6px; }
.card .value { font-size: 24px; font-weight: 700; color: #38bdf8; }
.card .sub { color: #94a3b8; font-size: 11px; margin-top: 4px; }
.section { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
           padding: 18px 20px; margin-bottom: 20px; }
.section h2 { font-size: 14px; color: #38bdf8; margin-bottom: 14px;
              border-bottom: 1px solid #334155; padding-bottom: 8px; }
.models { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
.model-card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 18px; }
.model-card h3 { font-size: 13px; margin-bottom: 10px; }
.model-card .row { display: flex; justify-content: space-between;
                   font-size: 11px; color: #94a3b8; padding: 3px 0;
                   border-bottom: 1px solid #1e293b; }
.model-card .row span { color: #e2e8f0; }
.teacher-label { color: #f97316; }
.student-label { color: #22c55e; }
.config-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; }
.cfg { background: #0f172a; border: 1px solid #334155; border-radius: 6px;
       padding: 10px 12px; font-size: 11px; }
.cfg .ck { color: #64748b; margin-bottom: 4px; }
.cfg .cv { color: #38bdf8; font-weight: 600; font-size: 14px; }
.jetson-note { background: #0f172a; border: 1px solid #22c55e; border-radius: 8px;
               padding: 12px 16px; color: #22c55e; font-size: 12px;
               display: flex; align-items: center; gap: 10px; margin-top: 14px; }
"""


def _build_dashboard_html() -> str:
    pct = TRAINING["current_step"] / TRAINING["total_steps"] * 100
    loss_svg = _build_loss_svg()
    comp_svg = _build_compression_svg()

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Knowledge Distillation — Port 8145</title>
<style>{CSS}</style></head><body>
<div class="header">
  <span style="font-size:22px">&#129504;</span>
  <h1>Knowledge Distillation Pipeline</h1>
  <span class="badge">PORT 8145</span>
  <span style="margin-left:auto;color:#64748b;font-size:12px">
    {TEACHER['name']} (3B) &#8594; {STUDENT['name']} (300M)
  </span>
</div>
<div class="main">

  <div class="progress-wrap">
    <h2>Training Progress — {TRAINING['current_step']:,} / {TRAINING['total_steps']:,} steps ({pct:.0f}%)</h2>
    <div class="prog-bar-bg"><div class="prog-bar-fg" style="width:{pct:.1f}%"></div></div>
    <div class="prog-meta">
      <span>Student loss: {TRAINING['student_loss']}</span>
      <span>KD loss: {TRAINING['kd_loss']}</span>
      <span>Task loss: {TRAINING['task_loss']}</span>
      <span>Student SR @ step 1000: {STUDENT['current_success_rate']:.0%}</span>
    </div>
  </div>

  <div class="cards">
    <div class="card">
      <div class="label">Params Ratio</div>
      <div class="value">{COMPRESSION['params_ratio']:.0f}×</div>
      <div class="sub">3B → 300M</div>
    </div>
    <div class="card">
      <div class="label">Latency Ratio</div>
      <div class="value">{COMPRESSION['latency_ratio']:.0f}×</div>
      <div class="sub">226ms → 45ms target</div>
    </div>
    <div class="card">
      <div class="label">Size Ratio</div>
      <div class="value">{COMPRESSION['size_ratio']:.1f}×</div>
      <div class="sub">6.7GB → 0.8GB target</div>
    </div>
    <div class="card">
      <div class="label">SR Retention</div>
      <div class="value">{COMPRESSION['sr_retention_target_pct']:.0f}%</div>
      <div class="sub">target ≥ 0.72 SR</div>
    </div>
  </div>

  <div class="models">
    <div class="model-card">
      <h3 class="teacher-label">Teacher — {TEACHER['name']}</h3>
      <div class="row">Parameters <span>{TEACHER['params_B']:.1f}B</span></div>
      <div class="row">Latency <span>{TEACHER['latency_ms']}ms</span></div>
      <div class="row">Success Rate <span>{TEACHER['success_rate']:.0%}</span></div>
      <div class="row">Model Size <span>{TEACHER['size_GB']}GB</span></div>
    </div>
    <div class="model-card">
      <h3 class="student-label">Student — {STUDENT['name']}</h3>
      <div class="row">Parameters <span>{STUDENT['params_B']:.1f}B</span></div>
      <div class="row">Target Latency <span>{STUDENT['target_latency_ms']}ms</span></div>
      <div class="row">Target SR <span>≥{STUDENT['target_success_rate']:.0%}</span></div>
      <div class="row">Target Size <span>{STUDENT['target_size_GB']}GB</span></div>
      <div class="row">Current SR (step 1k) <span>{STUDENT['current_success_rate']:.0%}</span></div>
    </div>
  </div>

  <div class="section">
    <h2>Loss Curves</h2>
    {loss_svg}
  </div>

  <div class="section">
    <h2>Compression Metrics</h2>
    {comp_svg}
    <div class="jetson-note">
      &#9989;&nbsp;<strong>Jetson Deploy:</strong>
      Student (0.8GB) fits in Jetson AGX Orin 64GB.
      Teacher (6.7GB) does NOT fit on Jetson — requires OCI A100.
    </div>
  </div>

  <div class="section">
    <h2>Distillation Config</h2>
    <div class="config-grid">
      <div class="cfg"><div class="ck">Temperature</div><div class="cv">{DIST_CONFIG['temperature']}</div></div>
      <div class="cfg"><div class="ck">Alpha (KD loss weight)</div><div class="cv">{DIST_CONFIG['alpha']}</div></div>
      <div class="cfg"><div class="ck">Beta (task loss weight)</div><div class="cv">{DIST_CONFIG['beta']}</div></div>
      <div class="cfg"><div class="ck">Feature Matching</div>
        <div class="cv">{str(DIST_CONFIG['feature_matching'])}</div></div>
      <div class="cfg"><div class="ck">Feature Layers</div>
        <div class="cv">{DIST_CONFIG['feature_layers']}</div></div>
      <div class="cfg"><div class="ck">Total Steps</div><div class="cv">{TRAINING['total_steps']:,}</div></div>
    </div>
  </div>

</div></body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="OCI Knowledge Distillation", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_build_dashboard_html())

    @app.get("/status")
    async def status() -> JSONResponse:
        pct = TRAINING["current_step"] / TRAINING["total_steps"] * 100
        return JSONResponse(content={
            "training": TRAINING,
            "progress_pct": round(pct, 1),
            "teacher": TEACHER["name"],
            "student": STUDENT["name"],
            "current_student_sr": STUDENT["current_success_rate"],
        })

    @app.get("/config")
    async def config() -> JSONResponse:
        return JSONResponse(content={"distillation_config": DIST_CONFIG, "teacher": TEACHER, "student": STUDENT})

    @app.get("/metrics")
    async def metrics() -> JSONResponse:
        return JSONResponse(content={
            "compression": COMPRESSION,
            "jetson_deploy": {
                "student_fits": True,
                "teacher_fits": False,
                "device": "Jetson AGX Orin 64GB",
            },
            "training_loss": {
                "student_loss": TRAINING["student_loss"],
                "kd_loss": TRAINING["kd_loss"],
                "task_loss": TRAINING["task_loss"],
            },
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("knowledge_distillation:app", host="0.0.0.0", port=8145, reload=True)
