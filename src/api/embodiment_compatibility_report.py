"""
OCI Robot Cloud — Embodiment Compatibility Report
Port 8685 | Cross-robot adapter layer analysis and zero-shot transfer scoring
"""

import math
import datetime
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

ROBOTS = ["Franka", "UR5e", "xArm", "Kinova", "Spot"]
TASKS = ["Pick", "Place", "Stack", "Pour", "Push", "Wipe", "Grasp", "Navigate"]

# Compatibility matrix [robot][task] 0.0-1.0
# Spot has low scores on manipulation tasks
COMPAT = [
    # Franka
    [0.95, 0.93, 0.89, 0.85, 0.82, 0.80, 0.92, 0.55],
    # UR5e
    [0.88, 0.86, 0.83, 0.79, 0.77, 0.74, 0.85, 0.50],
    # xArm
    [0.85, 0.83, 0.80, 0.76, 0.75, 0.72, 0.82, 0.48],
    # Kinova
    [0.80, 0.78, 0.75, 0.71, 0.70, 0.67, 0.78, 0.45],
    # Spot
    [0.28, 0.25, 0.20, 0.18, 0.65, 0.60, 0.22, 0.92],
]

# Adapter parameters in millions
ADAPTER_PARAMS_M = {"Franka": 12, "UR5e": 14, "xArm": 11, "Kinova": 13, "Spot": 18}
# Base GR00T N1.6 model: ~1.5B params → adapter overhead %
BASE_MODEL_M = 1500
ADAPTER_OVERHEAD_PCT = {k: round(v / BASE_MODEL_M * 100, 2) for k, v in ADAPTER_PARAMS_M.items()}

# Zero-shot transfer from Franka
ZERO_SHOT = {
    "UR5e":  0.71,
    "xArm":  0.68,
    "Kinova": 0.61,
    "Spot":  0.31,
}
ZERO_SHOT_TARGET = 0.70

# GR00T N2.0 improvement for Spot
N20_SPOT_SCORE = 0.54

KEY_METRICS = {
    "franka_ur5e_zero_shot": 0.71,
    "franka_spot_zero_shot": 0.31,
    "adapter_min_demos": 200,
    "adapter_params_franka_M": 12,
    "groot_n20_spot": 0.54,
    "zero_shot_target": 0.70,
}

# ---------------------------------------------------------------------------
# SVG Helpers
# ---------------------------------------------------------------------------

CELL_W = 74
CELL_H = 40
HEAT_PAD_L = 70
HEAT_PAD_T = 60
HEAT_PAD_R = 20
HEAT_PAD_B = 30


def _compat_color(v: float) -> str:
    """Green (#22c55e) → Yellow (#f59e0b) → Red (#ef4444) gradient."""
    if v >= 0.75:
        # Green region
        t = (v - 0.75) / 0.25  # 0→1
        r = int(0x22 + t * (0x22 - 0x22))
        g = int(0xc5 + t * (0xc5 - 0xc5))
        b = int(0x5e + t * (0x5e - 0x5e))
        return "#22c55e"
    elif v >= 0.40:
        # Yellow region
        t = (v - 0.40) / 0.35  # 0→1
        return "#f59e0b" if t < 0.5 else "#a3e635"
    else:
        return "#ef4444"


def build_svg_heatmap() -> str:
    """5 robots × 8 tasks compatibility matrix heatmap."""
    n_robots = len(ROBOTS)
    n_tasks = len(TASKS)
    svg_w = HEAT_PAD_L + n_tasks * CELL_W + HEAT_PAD_R
    svg_h = HEAT_PAD_T + n_robots * CELL_H + HEAT_PAD_B

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="8"/>',
    ]

    # Column headers (tasks)
    for ti, task in enumerate(TASKS):
        x = HEAT_PAD_L + ti * CELL_W + CELL_W // 2
        lines.append(
            f'<text x="{x}" y="{HEAT_PAD_T - 10}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{task}</text>'
        )

    # Row headers (robots) + cells
    for ri, robot in enumerate(ROBOTS):
        y_top = HEAT_PAD_T + ri * CELL_H
        cy = y_top + CELL_H // 2
        # Row label
        lines.append(
            f'<text x="{HEAT_PAD_L - 8}" y="{cy + 4}" text-anchor="end" '
            f'font-size="11" fill="#38bdf8" font-family="monospace">{robot}</text>'
        )
        for ti, task in enumerate(TASKS):
            val = COMPAT[ri][ti]
            color = _compat_color(val)
            x_left = HEAT_PAD_L + ti * CELL_W
            # Cell rect
            lines.append(
                f'<rect x="{x_left + 2}" y="{y_top + 2}" '
                f'width="{CELL_W - 4}" height="{CELL_H - 4}" '
                f'fill="{color}" opacity="0.75" rx="4"/>'
            )
            # Value text
            text_color = "#0f172a" if val >= 0.50 else "#f1f5f9"
            lines.append(
                f'<text x="{x_left + CELL_W // 2}" y="{cy + 4}" '
                f'text-anchor="middle" font-size="10" fill="{text_color}" '
                f'font-family="monospace" font-weight="600">{val:.2f}</text>'
            )

    # Color legend bar
    leg_x = HEAT_PAD_L
    leg_y = HEAT_PAD_T + n_robots * CELL_H + 10
    for i, (label, color) in enumerate([
        ("Low (<0.4)", "#ef4444"),
        ("Mid (0.4-0.75)", "#f59e0b"),
        ("High (≥0.75)", "#22c55e"),
    ]):
        rx = leg_x + i * 160
        lines.append(
            f'<rect x="{rx}" y="{leg_y}" width="12" height="12" fill="{color}" '
            f'opacity="0.8" rx="2"/>'
        )
        lines.append(
            f'<text x="{rx + 16}" y="{leg_y + 10}" font-size="9" fill="#94a3b8" '
            f'font-family="monospace">{label}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def build_svg_adapter_bars() -> str:
    """Adapter layer size bar chart: params in M + overhead %."""
    W, H = 560, 240
    pl, pr, pt, pb = 70, 30, 30, 50
    cw = W - pl - pr
    ch = H - pt - pb

    max_params = max(ADAPTER_PARAMS_M.values())
    robot_list = list(ADAPTER_PARAMS_M.keys())
    n = len(robot_list)
    bar_w = int(cw / n * 0.55)
    gap = cw / n

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>',
    ]

    # Gridlines
    for v in [0, 5, 10, 15, 20]:
        y = pt + ch - int(v / max_params * ch)
        lines.append(
            f'<line x1="{pl}" y1="{y}" x2="{pl + cw}" y2="{y}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl - 6}" y="{y + 4}" text-anchor="end" font-size="9" '
            f'fill="#64748b" font-family="monospace">{v}M</text>'
        )

    # Bars
    for i, robot in enumerate(robot_list):
        params = ADAPTER_PARAMS_M[robot]
        pct = ADAPTER_OVERHEAD_PCT[robot]
        x = pl + int(i * gap + gap / 2) - bar_w // 2
        bar_h = int(params / max_params * ch)
        y = pt + ch - bar_h
        color = "#38bdf8" if robot != "Spot" else "#f59e0b"
        lines.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{color}" opacity="0.85" rx="3"/>'
        )
        # Param label on top
        lines.append(
            f'<text x="{x + bar_w // 2}" y="{y - 5}" text-anchor="middle" '
            f'font-size="10" fill="{color}" font-family="monospace">{params}M</text>'
        )
        # Overhead % inside bar
        lines.append(
            f'<text x="{x + bar_w // 2}" y="{y + bar_h // 2 + 4}" text-anchor="middle" '
            f'font-size="9" fill="#0f172a" font-family="monospace" font-weight="700">{pct}%</text>'
        )
        # X label
        lines.append(
            f'<text x="{x + bar_w // 2}" y="{pt + ch + 18}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{robot}</text>'
        )

    # Y axis label
    lines.append(
        f'<text x="{pl - 40}" y="{pt + ch // 2}" text-anchor="middle" '
        f'font-size="9" fill="#64748b" font-family="monospace" '
        f'transform="rotate(-90,{pl - 40},{pt + ch // 2})">Adapter Params (M)</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def build_svg_zero_shot_bars() -> str:
    """Zero-shot transfer score bar chart (trained from Franka)."""
    W, H = 560, 240
    pl, pr, pt, pb = 70, 30, 30, 50
    cw = W - pl - pr
    ch = H - pt - pb

    robots = list(ZERO_SHOT.keys())
    scores = list(ZERO_SHOT.values())
    max_score = 1.0
    n = len(robots)
    bar_w = int(cw / n * 0.5)
    gap = cw / n
    target_y = pt + ch - int(ZERO_SHOT_TARGET / max_score * ch)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>',
    ]

    # Gridlines
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pt + ch - int(v / max_score * ch)
        lines.append(
            f'<line x1="{pl}" y1="{y}" x2="{pl + cw}" y2="{y}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl - 6}" y="{y + 4}" text-anchor="end" font-size="9" '
            f'fill="#64748b" font-family="monospace">{v:.1f}</text>'
        )

    # Target line
    lines.append(
        f'<line x1="{pl}" y1="{target_y}" x2="{pl + cw}" y2="{target_y}" '
        f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3"/>'
    )
    lines.append(
        f'<text x="{pl + cw - 4}" y="{target_y - 4}" text-anchor="end" font-size="9" '
        f'fill="#C74634" font-family="monospace">Target 0.70</text>'
    )

    # Bars
    for i, (robot, score) in enumerate(zip(robots, scores)):
        x = pl + int(i * gap + gap / 2) - bar_w // 2
        bar_h = int(score / max_score * ch)
        y = pt + ch - bar_h
        above = score >= ZERO_SHOT_TARGET
        color = "#22c55e" if above else "#f59e0b" if score >= 0.50 else "#ef4444"
        lines.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{color}" opacity="0.85" rx="3"/>'
        )
        # Score label
        lines.append(
            f'<text x="{x + bar_w // 2}" y="{y - 5}" text-anchor="middle" '
            f'font-size="11" fill="{color}" font-family="monospace" font-weight="700">{score:.2f}</text>'
        )
        # Robot name
        lines.append(
            f'<text x="{x + bar_w // 2}" y="{pt + ch + 18}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{robot}</text>'
        )
        # GR00T N2.0 annotation for Spot
        if robot == "Spot":
            n20_y = pt + ch - int(N20_SPOT_SCORE / max_score * ch)
            lines.append(
                f'<line x1="{x}" y1="{n20_y}" x2="{x + bar_w}" y2="{n20_y}" '
                f'stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="4,2"/>'
            )
            lines.append(
                f'<text x="{x + bar_w + 4}" y="{n20_y + 4}" font-size="8" '
                f'fill="#a78bfa" font-family="monospace">N2.0: {N20_SPOT_SCORE}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Page
# ---------------------------------------------------------------------------

def build_html() -> str:
    heatmap = build_svg_heatmap()
    adapter_bars = build_svg_adapter_bars()
    zero_shot = build_svg_zero_shot_bars()

    def metric_card(label: str, value: str, color: str = "#38bdf8") -> str:
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px 18px;flex:1;min-width:130px;">
          <div style="color:#64748b;font-size:11px;text-transform:uppercase;
                      letter-spacing:1px;margin-bottom:6px;">{label}</div>
          <div style="color:{color};font-size:26px;font-weight:800;">{value}</div>
        </div>"""

    cards = (
        metric_card("Franka→UR5e", "0.71", "#22c55e") +
        metric_card("Franka→xArm", "0.68", "#a3e635") +
        metric_card("Franka→Kinova", "0.61", "#f59e0b") +
        metric_card("Franka→Spot", "0.31", "#ef4444") +
        metric_card("N2.0 Spot", "0.54", "#a78bfa") +
        metric_card("Adapt Demos", "200", "#38bdf8")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Embodiment Compatibility Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont,
            'Segoe UI', sans-serif; min-height: 100vh; }}
    h1 {{ color: #C74634; font-size: 22px; font-weight: 800; letter-spacing: 0.5px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px 22px; margin-bottom: 22px; }}
    .section-title {{ color: #C74634; font-size: 12px; font-weight: 700; letter-spacing: 1px;
                      text-transform: uppercase; margin-bottom: 14px; }}
  </style>
</head>
<body>
  <div style="max-width:800px;margin:0 auto;padding:28px 20px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <div>
        <h1>OCI Robot Cloud</h1>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px;">
          Embodiment Compatibility Report &mdash; GR00T N1.6 Cross-Robot Transfer
        </div>
      </div>
      <div style="background:#1e293b;border-radius:8px;padding:8px 16px;
                  color:#38bdf8;font-size:12px;font-family:monospace;">PORT 8685</div>
    </div>

    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px;">
      {cards}
    </div>

    <div class="section">
      <div class="section-title">Embodiment Compatibility Matrix (5 Robots × 8 Tasks)</div>
      {heatmap}
      <div style="color:#64748b;font-size:11px;margin-top:10px;">
        Franka is the reference training platform. Spot excels at navigation but has low
        compatibility with manipulation tasks (Pick/Place/Stack/Pour/Grasp &lt;0.30).
      </div>
    </div>

    <div class="section">
      <div class="section-title">Adapter Layer Size (Params M + Overhead %)</div>
      {adapter_bars}
      <div style="color:#64748b;font-size:11px;margin-top:10px;">
        Adapters are lightweight (~0.8–1.2% of base model). Spot requires the largest adapter
        (18M) due to quadruped morphology divergence. Minimum 200 demos to adapt.
      </div>
    </div>

    <div class="section">
      <div class="section-title">Zero-Shot Transfer Score (Trained on Franka)</div>
      {zero_shot}
      <div style="color:#64748b;font-size:11px;margin-top:10px;">
        Target threshold: 0.70. UR5e clears the bar (0.71); xArm near (0.68);
        Spot (0.31) is below — GR00T N2.0 raises Spot to 0.54 (purple dashed line).
      </div>
    </div>

    <div style="text-align:center;color:#334155;font-size:11px;margin-top:28px;
                padding-top:16px;border-top:1px solid #1e293b;">
      Oracle Confidential | OCI Robot Cloud Embodiment Compatibility Report | Port 8685
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Embodiment Compatibility Report",
        description="Cross-robot adapter layer analysis and zero-shot transfer scoring",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "embodiment_compatibility_report", "port": 8685})

    @app.get("/compatibility")
    def compatibility():
        result = {}
        for ri, robot in enumerate(ROBOTS):
            result[robot] = {task: COMPAT[ri][ti] for ti, task in enumerate(TASKS)}
        return JSONResponse(result)

    @app.get("/zero-shot")
    def zero_shot():
        return JSONResponse({
            "source": "Franka",
            "scores": ZERO_SHOT,
            "target": ZERO_SHOT_TARGET,
            "groot_n20_spot": N20_SPOT_SCORE,
        })

    @app.get("/adapters")
    def adapters():
        return JSONResponse({
            "params_M": ADAPTER_PARAMS_M,
            "overhead_pct": ADAPTER_OVERHEAD_PCT,
            "min_demos_to_adapt": KEY_METRICS["adapter_min_demos"],
        })


# ---------------------------------------------------------------------------
# CLI fallback
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("embodiment_compatibility_report:app", host="0.0.0.0", port=8685, reload=False)
    else:
        out_path = "/tmp/embodiment_compatibility_report.html"
        with open(out_path, "w") as f:
            f.write(build_html())
        print(f"[embodiment_compatibility_report] Saved static HTML to {out_path}")
        print(f"[embodiment_compatibility_report] Key metrics: {json.dumps(KEY_METRICS, indent=2)}")
