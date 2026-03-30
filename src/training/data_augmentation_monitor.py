"""Data Augmentation Pipeline Monitor — port 8164.

Tracks SDG training data augmentation transforms applied to genesis_sdg_v3
(1940 valid demos) and their impact on success rate.
"""

from __future__ import annotations

import math

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
except ImportError as _e:
    raise SystemExit(f"Missing dependency: {_e}. Install fastapi and uvicorn.") from _e

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

DATASET_NAME = "genesis_sdg_v3"
DATASET_DEMOS = 1940
BASE_SR = 0.64
AUGMENTED_SR = 0.78
TOTAL_SR_GAIN = round(AUGMENTED_SR - BASE_SR, 4)

TRANSFORMS = [
    {
        "name": "domain_randomization",
        "enabled": True,
        "intensity": 0.5,
        "applied_pct": 100,
        "sr_impact": 0.05,
        "description": "Lighting/texture variation",
    },
    {
        "name": "color_jitter",
        "enabled": True,
        "intensity": 0.3,
        "applied_pct": 80,
        "sr_impact": 0.03,
        "description": "Brightness/contrast/saturation jitter",
    },
    {
        "name": "random_crop",
        "enabled": True,
        "intensity": 0.15,
        "applied_pct": 100,
        "sr_impact": 0.02,
        "description": "Random 224→200 crop and resize",
    },
    {
        "name": "action_noise",
        "enabled": True,
        "intensity": 0.01,
        "applied_pct": 50,
        "sr_impact": 0.02,
        "description": "Gaussian noise on expert actions",
    },
    {
        "name": "gaussian_noise",
        "enabled": True,
        "intensity": 0.02,
        "applied_pct": 60,
        "sr_impact": 0.01,
        "description": "σ=0.02 pixel noise",
    },
    {
        "name": "random_rotation",
        "enabled": True,
        "intensity": 0.1,
        "applied_pct": 40,
        "sr_impact": 0.01,
        "description": "±10° rotation",
    },
    {
        "name": "horizontal_flip",
        "enabled": False,
        "intensity": 0.5,
        "applied_pct": 0,
        "sr_impact": -0.04,
        "description": "DISABLED: breaks chirality",
    },
]

# Sort transforms by sr_impact descending for cumulative chart order
TRANSFORMS_SORTED = sorted(TRANSFORMS, key=lambda t: t["sr_impact"], reverse=True)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    """Augmentation contribution bar chart — 680×200."""
    W, H = 680, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 20, 50
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    impacts = [t["sr_impact"] for t in TRANSFORMS]
    names = [t["name"] for t in TRANSFORMS]
    enabled = [t["enabled"] for t in TRANSFORMS]

    max_abs = max(abs(v) for v in impacts) or 0.01
    bar_w = chart_w / len(TRANSFORMS)
    bar_gap = bar_w * 0.15

    # zero line y
    zero_y = PAD_T + chart_h * (max_abs / (2 * max_abs))

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{zero_y:.1f}" x2="{W-PAD_R}" y2="{zero_y:.1f}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,2"/>')

    # y-axis ticks
    for tick_val in [-0.04, -0.02, 0, 0.02, 0.04]:
        ty = PAD_T + chart_h * (1 - (tick_val + max_abs) / (2 * max_abs))
        lines.append(f'<line x1="{PAD_L-4}" y1="{ty:.1f}" x2="{PAD_L}" y2="{ty:.1f}" stroke="#94a3b8" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{ty+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{tick_val:+.2f}</text>')

    for i, (impact, name, en) in enumerate(zip(impacts, names, enabled)):
        bx = PAD_L + i * bar_w + bar_gap
        bw = bar_w - 2 * bar_gap
        bh = abs(impact) / (2 * max_abs) * chart_h
        by = zero_y - bh if impact >= 0 else zero_y

        color = "#22c55e" if impact > 0 else "#ef4444"
        dashattr = ' stroke-dasharray="6,3" stroke="#94a3b8" stroke-width="1" fill-opacity="0.5"' if not en else ""
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}"{dashattr} rx="2"/>')

        # label
        label = name.replace("_", "\n")
        lx = bx + bw / 2
        ly = PAD_T + chart_h + 14
        short = name.replace("_", " ")
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{short[:10]}</text>')

        # value label
        vly = by - 3 if impact >= 0 else by + bh + 10
        lines.append(f'<text x="{lx:.1f}" y="{vly:.1f}" fill="{color}" font-size="9" text-anchor="middle">{impact:+.2f}</text>')

    lines.append("</svg>")
    return "".join(lines)


def _donut_svg() -> str:
    """Apply-rate donut chart — 420×260."""
    W, H = 420, 260
    cx, cy, R, r = 160, 130, 100, 55
    COLORS = ["#38bdf8", "#22c55e", "#a78bfa", "#f59e0b", "#ec4899", "#14b8a6", "#6b7280"]

    segments = [(t["name"], t["applied_pct"], t["enabled"]) for t in TRANSFORMS]
    total = sum(s[1] for s in segments) or 1

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    angle = -math.pi / 2  # start at top
    for idx, (name, pct, en) in enumerate(segments):
        sweep = 2 * math.pi * pct / total if total > 0 else 0
        x1 = cx + R * math.cos(angle)
        y1 = cy + R * math.sin(angle)
        x2 = cx + R * math.cos(angle + sweep)
        y2 = cy + R * math.sin(angle + sweep)
        xi1 = cx + r * math.cos(angle + sweep)
        yi1 = cy + r * math.sin(angle + sweep)
        xi2 = cx + r * math.cos(angle)
        yi2 = cy + r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        color = COLORS[idx % len(COLORS)] if en else "#374151"
        path = (
            f"M {x1:.2f},{y1:.2f} "
            f"A {R},{R} 0 {large},1 {x2:.2f},{y2:.2f} "
            f"L {xi1:.2f},{yi1:.2f} "
            f"A {r},{r} 0 {large},0 {xi2:.2f},{yi2:.2f} Z"
        )
        lines.append(f'<path d="{path}" fill="{color}" stroke="#0f172a" stroke-width="2"/>')
        # mid-angle label if segment big enough
        if pct >= 10:
            ma = angle + sweep / 2
            lx = cx + (R + r) / 2 * math.cos(ma)
            ly = cy + (R + r) / 2 * math.sin(ma)
            lines.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" fill="#fff" font-size="9" text-anchor="middle">{pct}%</text>')
        angle += sweep

    # center text
    lines.append(f'<text x="{cx}" y="{cy-6}" fill="#94a3b8" font-size="11" text-anchor="middle">Apply</text>')
    lines.append(f'<text x="{cx}" y="{cy+10}" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Rates</text>')

    # legend
    lx0 = 280
    for idx, (name, pct, en) in enumerate(segments):
        color = COLORS[idx % len(COLORS)] if en else "#374151"
        ly = 30 + idx * 28
        short = name.replace("_", " ")
        dis = " (off)" if not en else ""
        lines.append(f'<rect x="{lx0}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx0+16}" y="{ly+10}" fill="#cbd5e1" font-size="10">{short}{dis}</text>')

    lines.append("</svg>")
    return "".join(lines)


def _cumulative_sr_svg() -> str:
    """Cumulative SR improvement line chart — 680×180."""
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 65, 20, 20, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    # Build cumulative SR by adding transforms best-first (positive only)
    pts = [BASE_SR]
    running = BASE_SR
    labels = ["Base"]
    for t in TRANSFORMS_SORTED:
        running = round(running + t["sr_impact"], 4)
        pts.append(running)
        labels.append(t["name"].replace("_", " ")[:8])

    min_sr = min(pts) - 0.02
    max_sr = max(pts) + 0.02
    sr_range = max_sr - min_sr or 0.01

    def px(i: int) -> float:
        return PAD_L + i * chart_w / (len(pts) - 1)

    def py(v: float) -> float:
        return PAD_T + chart_h * (1 - (v - min_sr) / sr_range)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # grid lines
    for tick in [0.60, 0.65, 0.70, 0.75, 0.80]:
        ty = py(tick)
        if PAD_T <= ty <= PAD_T + chart_h:
            lines.append(f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{W-PAD_R}" y2="{ty:.1f}" stroke="#334155" stroke-width="1"/>')
            lines.append(f'<text x="{PAD_L-6}" y="{ty+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick:.2f}</text>')

    # area fill
    area_pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(pts))
    area_pts += f" {px(len(pts)-1):.1f},{PAD_T+chart_h:.1f} {PAD_L},{PAD_T+chart_h:.1f}"
    lines.append(f'<polygon points="{area_pts}" fill="#38bdf8" fill-opacity="0.12"/>')

    # line
    path_d = " ".join(("M" if i == 0 else "L") + f" {px(i):.1f},{py(v):.1f}" for i, v in enumerate(pts))
    lines.append(f'<path d="{path_d}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # dots + labels
    for i, (v, lbl) in enumerate(zip(pts, labels)):
        x, y = px(i), py(v)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>')
        lines.append(f'<text x="{x:.1f}" y="{y-8:.1f}" fill="#f1f5f9" font-size="8" text-anchor="middle">{v:.2f}</text>')
        lines.append(f'<text x="{x:.1f}" y="{PAD_T+chart_h+14:.1f}" fill="#64748b" font-size="8" text-anchor="middle">{lbl}</text>')

    lines.append("</svg>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    bar_svg = _bar_chart_svg()
    donut_svg = _donut_svg()
    cumulative_svg = _cumulative_sr_svg()

    enabled_count = sum(1 for t in TRANSFORMS if t["enabled"])
    disabled_count = len(TRANSFORMS) - enabled_count

    rows = ""
    for t in TRANSFORMS:
        status_color = "#22c55e" if t["enabled"] else "#ef4444"
        status_text = "ENABLED" if t["enabled"] else "DISABLED"
        impact_color = "#22c55e" if t["sr_impact"] > 0 else "#ef4444"
        rows += f"""
        <tr>
          <td style="color:#f1f5f9;font-weight:500">{t['name']}</td>
          <td style="color:{status_color};font-size:11px;font-weight:700">{status_text}</td>
          <td style="color:#94a3b8">{t['intensity']}</td>
          <td style="color:#38bdf8">{t['applied_pct']}%</td>
          <td style="color:{impact_color};font-weight:600">{t['sr_impact']:+.2f}</td>
          <td style="color:#64748b;font-size:12px">{t['description']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Augmentation Monitor — OCI Robot Cloud</title>
<style>
  * {{box-sizing:border-box;margin:0;padding:0}}
  body {{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1 {{font-size:22px;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
  .subtitle {{color:#64748b;font-size:13px;margin-bottom:24px}}
  .badge {{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;margin-right:6px}}
  .badge-blue {{background:#0ea5e940;color:#38bdf8;border:1px solid #38bdf840}}
  .badge-red {{background:#C7463440;color:#C74634;border:1px solid #C7463440}}
  .kpi-row {{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .kpi {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:140px}}
  .kpi-val {{font-size:26px;font-weight:700;color:#38bdf8}}
  .kpi-lbl {{font-size:11px;color:#64748b;margin-top:2px}}
  .kpi-val.green {{color:#22c55e}}
  .kpi-val.red {{color:#C74634}}
  .section {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:20px}}
  .section-title {{font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:0.05em}}
  .charts {{display:flex;gap:16px;flex-wrap:wrap}}
  table {{width:100%;border-collapse:collapse;font-size:13px}}
  th {{color:#64748b;font-weight:600;padding:8px 10px;border-bottom:1px solid #334155;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:0.04em}}
  td {{padding:8px 10px;border-bottom:1px solid #1e293b}}
  tr:last-child td {{border-bottom:none}}
  tr:hover td {{background:#263045}}
  .footer {{color:#334155;font-size:11px;text-align:center;margin-top:24px}}
</style>
</head>
<body>
<h1>Data Augmentation Pipeline Monitor
  <span class="badge badge-blue">Port 8164</span>
  <span class="badge badge-red">OCI Robot Cloud</span>
</h1>
<div class="subtitle">Dataset: {DATASET_NAME} &nbsp;|&nbsp; {DATASET_DEMOS:,} valid demos &nbsp;|&nbsp; {enabled_count} transforms active, {disabled_count} disabled</div>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">{BASE_SR:.2f}</div><div class="kpi-lbl">Base SR (no aug)</div></div>
  <div class="kpi"><div class="kpi-val green">{AUGMENTED_SR:.2f}</div><div class="kpi-lbl">Augmented SR</div></div>
  <div class="kpi"><div class="kpi-val green">+{TOTAL_SR_GAIN:.2f}</div><div class="kpi-lbl">Total SR Gain</div></div>
  <div class="kpi"><div class="kpi-val">{enabled_count}</div><div class="kpi-lbl">Active Transforms</div></div>
  <div class="kpi"><div class="kpi-val red">{disabled_count}</div><div class="kpi-lbl">Disabled Transforms</div></div>
  <div class="kpi"><div class="kpi-val">{DATASET_DEMOS:,}</div><div class="kpi-lbl">Training Demos</div></div>
</div>

<div class="section">
  <div class="section-title">SR Impact per Transform</div>
  {bar_svg}
</div>

<div class="section">
  <div class="charts">
    <div>
      <div class="section-title" style="margin-bottom:10px">Apply Rate Distribution</div>
      {donut_svg}
    </div>
    <div style="flex:1">
      <div class="section-title" style="margin-bottom:10px">Cumulative SR Improvement (best-first stacking)</div>
      {cumulative_svg}
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Transform Details</div>
  <table>
    <thead>
      <tr>
        <th>Transform</th>
        <th>Status</th>
        <th>Intensity</th>
        <th>Applied %</th>
        <th>SR Impact</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="footer">OCI Robot Cloud &mdash; Data Augmentation Monitor &mdash; Port 8164</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

try:
    app = FastAPI(
        title="Data Augmentation Monitor",
        description="SDG training data augmentation pipeline monitor for genesis_sdg_v3",
        version="1.0.0",
    )
except NameError:
    raise SystemExit("fastapi not available")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Dashboard HTML for augmentation pipeline."""
    return _dashboard_html()


@app.get("/transforms")
def get_transforms():
    """Return all transform configurations as JSON."""
    return JSONResponse({"dataset": DATASET_NAME, "demos": DATASET_DEMOS, "transforms": TRANSFORMS})


@app.get("/summary")
def get_summary():
    """Return high-level augmentation summary."""
    return JSONResponse({
        "dataset": DATASET_NAME,
        "demos": DATASET_DEMOS,
        "base_sr": BASE_SR,
        "augmented_sr": AUGMENTED_SR,
        "total_sr_gain": TOTAL_SR_GAIN,
        "enabled_transforms": sum(1 for t in TRANSFORMS if t["enabled"]),
        "disabled_transforms": sum(1 for t in TRANSFORMS if not t["enabled"]),
    })


@app.get("/impact")
def get_impact():
    """Return SR impact breakdown sorted by contribution."""
    return JSONResponse({
        "sorted_by_impact": [
            {"name": t["name"], "sr_impact": t["sr_impact"], "enabled": t["enabled"]}
            for t in TRANSFORMS_SORTED
        ]
    })


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8164)
    except ImportError:
        print("uvicorn not installed. Run: pip install fastapi uvicorn")
