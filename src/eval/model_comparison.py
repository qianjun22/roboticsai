"""Model Comparison Service — OCI Robot Cloud, port 8134.

Head-to-head comparison of all trained models across 6 metrics.
"""

import math
from typing import Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None
    HTMLResponse = JSONResponse = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

MODELS = {
    "bc_baseline": {
        "sr": 0.05, "mae": 0.103, "latency_ms": 412,
        "cost_per_run": 0.89, "robustness": 0.31, "data_efficiency": 0.12,
        "estimated": False, "color": "#94a3b8",
    },
    "dagger_run5": {
        "sr": 0.42, "mae": 0.067, "latency_ms": 238,
        "cost_per_run": 0.45, "robustness": 0.58, "data_efficiency": 0.44,
        "estimated": False, "color": "#38bdf8",
    },
    "dagger_run9_v2": {
        "sr": 0.71, "mae": 0.031, "latency_ms": 231,
        "cost_per_run": 0.43, "robustness": 0.74, "data_efficiency": 0.67,
        "estimated": False, "color": "#818cf8",
    },
    "groot_finetune_v2": {
        "sr": 0.78, "mae": 0.023, "latency_ms": 226,
        "cost_per_run": 0.43, "robustness": 0.81, "data_efficiency": 0.79,
        "estimated": False, "color": "#C74634",
    },
    "groot_finetune_v3_est": {
        "sr": 0.84, "mae": 0.019, "latency_ms": 221,
        "cost_per_run": 0.41, "robustness": 0.87, "data_efficiency": 0.85,
        "estimated": True, "color": "#fb923c",
    },
}

METRICS = ["sr", "mae", "latency_ms", "cost_per_run", "robustness", "data_efficiency"]
METRIC_LABELS = {
    "sr": "Success Rate",
    "mae": "MAE (lower=better)",
    "latency_ms": "Latency (lower=better)",
    "cost_per_run": "Cost/Run (lower=better)",
    "robustness": "Robustness",
    "data_efficiency": "Data Efficiency",
}

# Normalization bounds for radar (higher normalized value = better)
def normalize(metric: str, value: float) -> float:
    """Return 0–1 where 1 is best."""
    if metric == "sr":
        return value  # already 0–1
    if metric == "mae":
        # range 0.019–0.103; invert
        return 1.0 - (value - 0.019) / (0.103 - 0.019)
    if metric == "latency_ms":
        # invert: (450 - x) / 400
        return (450 - value) / 400
    if metric == "cost_per_run":
        return 1.0 - (value - 0.41) / (0.89 - 0.41)
    if metric == "robustness":
        return value
    if metric == "data_efficiency":
        return value
    return value


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _polar_to_xy(cx: float, cy: float, r: float, angle_deg: float):
    """Convert polar coords (angle from top, clockwise) to SVG x,y."""
    rad = math.radians(angle_deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _radar_svg() -> str:
    """Generate 500x420 SVG radar/spider chart."""
    W, H = 500, 420
    cx, cy, R = 250, 195, 150
    axes = METRICS
    n = len(axes)
    rings = [0.25, 0.5, 0.75, 1.0]
    ring_colors = ["#1e293b", "#1e3a5f", "#1e4a6e", "#1e5a7e"]

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # Ring backgrounds
    for i, frac in enumerate(rings):
        pts = []
        for j in range(n):
            angle = 360 * j / n
            x, y = _polar_to_xy(cx, cy, R * frac, angle)
            pts.append(f"{x:.1f},{y:.1f}")
        poly = " ".join(pts)
        lines.append(f'<polygon points="{poly}" fill="{ring_colors[i]}" stroke="#334155" stroke-width="0.5"/>')

    # Ring labels (25%, 50%, 75%, 100%)
    for frac in rings:
        lx, ly = _polar_to_xy(cx, cy, R * frac, 0)
        lines.append(f'<text x="{lx+4:.1f}" y="{ly:.1f}" fill="#64748b" font-size="9" font-family="monospace">{int(frac*100)}%</text>')

    # Axis spokes + labels
    for j, metric in enumerate(axes):
        angle = 360 * j / n
        x2, y2 = _polar_to_xy(cx, cy, R, angle)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="1"/>')
        lx, ly = _polar_to_xy(cx, cy, R + 22, angle)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        label = METRIC_LABELS[metric].split(" ")[0]
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="{anchor}" font-family="sans-serif">{label}</text>')

    # Model polygons
    for name, data in MODELS.items():
        color = data["color"]
        pts = []
        for j, metric in enumerate(axes):
            angle = 360 * j / n
            r = normalize(metric, data[metric]) * R
            x, y = _polar_to_xy(cx, cy, r, angle)
            pts.append(f"{x:.1f},{y:.1f}")
        poly = " ".join(pts)
        dash = ' stroke-dasharray="5,3"' if data["estimated"] else ""
        lines.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="0.3" stroke="{color}" stroke-width="1.5"{dash}/>')

    # Legend
    legend_y = 355
    lx = 30
    for name, data in MODELS.items():
        color = data["color"]
        label = name.replace("_", " ")
        suffix = " *" if data["estimated"] else ""
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+16}" y="{legend_y+10}" fill="#cbd5e1" font-size="10" font-family="sans-serif">{label}{suffix}</text>')
        lx += 95
        if lx > 450:
            lx = 30
            legend_y += 18

    lines.append(f'<text x="{W//2}" y="{H-4}" fill="#475569" font-size="9" text-anchor="middle" font-family="monospace">* ESTIMATED — model in training</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _sr_bar_svg() -> str:
    """Generate 680x200 horizontal SR progression bar chart."""
    W, H = 680, 200
    sorted_models = sorted(MODELS.items(), key=lambda kv: kv[1]["sr"])
    bar_h = 24
    bar_gap = 10
    label_w = 170
    chart_w = W - label_w - 60
    pad_top = 20

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="14" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="sans-serif">Success Rate Progression</text>')

    for i, (name, data) in enumerate(sorted_models):
        y = pad_top + i * (bar_h + bar_gap)
        sr = data["sr"]
        bw = sr * chart_w
        color = data["color"]
        dash = ' stroke-dasharray="6,3" stroke="#f97316" stroke-width="1.5" fill="none"' if data["estimated"] else f' fill="{color}"'
        # background
        lines.append(f'<rect x="{label_w}" y="{y}" width="{chart_w:.1f}" height="{bar_h}" fill="#1e293b" rx="3"/>')
        # bar
        if data["estimated"]:
            lines.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" fill-opacity="0.35" rx="3"/>')
            lines.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" stroke="{color}" stroke-width="1.5" stroke-dasharray="6,3" fill="none" rx="3"/>')
        else:
            lines.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="3"/>')
        # label
        short = name.replace("_", " ")
        lines.append(f'<text x="{label_w-6}" y="{y+16}" fill="#cbd5e1" font-size="10" text-anchor="end" font-family="monospace">{short}</text>')
        # value
        lines.append(f'<text x="{label_w+bw+6:.1f}" y="{y+16}" fill="#e2e8f0" font-size="10" font-family="monospace">{sr*100:.0f}%{" *" if data["estimated"] else ""}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _html_dashboard() -> str:
    radar = _radar_svg()
    bars = _sr_bar_svg()
    rows = ""
    for name, d in sorted(MODELS.items(), key=lambda kv: -kv[1]["sr"]):
        est_badge = '<span style="font-size:10px;color:#fb923c"> ESTIMATED</span>' if d["estimated"] else ""
        rows += f"""
        <tr>
          <td style="color:{d['color']};font-weight:600">{name}{est_badge}</td>
          <td>{d['sr']*100:.0f}%</td>
          <td>{d['mae']:.3f}</td>
          <td>{d['latency_ms']} ms</td>
          <td>${d['cost_per_run']:.2f}</td>
          <td>{d['robustness']*100:.0f}%</td>
          <td>{d['data_efficiency']*100:.0f}%</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Robot Cloud — Model Comparison</title>
  <style>
    body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:sans-serif; }}
    h1 {{ color:#C74634; text-align:center; padding:24px 0 4px; font-size:22px; letter-spacing:1px; }}
    .subtitle {{ text-align:center; color:#64748b; font-size:12px; margin-bottom:16px; }}
    .champion {{ background:linear-gradient(90deg,#1e293b,#3b0a06,#1e293b); border:1px solid #C74634;
                 border-radius:8px; padding:14px 20px; margin:0 auto 20px; max-width:680px;
                 text-align:center; color:#fca5a5; font-size:14px; font-weight:600; letter-spacing:.5px; }}
    .charts {{ display:flex; flex-wrap:wrap; justify-content:center; gap:20px; padding:0 20px 20px; }}
    .card {{ background:#0f2340; border:1px solid #1e3a5f; border-radius:8px; padding:16px; }}
    table {{ width:100%; border-collapse:collapse; margin:0 auto; max-width:760px; }}
    th {{ background:#0f2340; color:#38bdf8; font-size:11px; text-transform:uppercase;
          padding:8px 10px; text-align:left; border-bottom:1px solid #1e3a5f; }}
    td {{ padding:7px 10px; font-size:12px; border-bottom:1px solid #1e293b; font-family:monospace; }}
    tr:hover td {{ background:#1e293b; }}
    .footer {{ text-align:center; color:#334155; font-size:10px; padding:12px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Model Comparison</h1>
  <p class="subtitle">Port 8134 &bull; 5 models &bull; 6 metrics &bull; 2026-03-30</p>
  <div class="champion">&#127942; groot_finetune_v2 PRODUCTION CHAMPION &mdash; SR 78% (+7pp vs DAgger run9)</div>
  <div class="charts">
    <div class="card">{radar}</div>
    <div class="card">{bars}</div>
  </div>
  <table>
    <thead><tr>
      <th>Model</th><th>Success Rate</th><th>MAE</th>
      <th>Latency</th><th>Cost/Run</th><th>Robustness</th><th>Data Eff.</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="footer">OCI Robot Cloud &bull; Model Comparison Service &bull; <a href="/models" style="color:#38bdf8">/models</a> &bull; <a href="/compare?a=bc_baseline&b=groot_finetune_v2" style="color:#38bdf8">/compare</a></p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Model Comparison", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/models")
    def list_models():
        payload = {}
        for name, d in MODELS.items():
            payload[name] = {k: v for k, v in d.items() if k not in ("color",)}
        return JSONResponse(content=payload)

    @app.get("/compare")
    def compare(
        a: str = Query("bc_baseline", description="First model name"),
        b: str = Query("groot_finetune_v2", description="Second model name"),
    ):
        if a not in MODELS:
            return JSONResponse(status_code=404, content={"error": f"Model '{a}' not found"})
        if b not in MODELS:
            return JSONResponse(status_code=404, content={"error": f"Model '{b}' not found"})
        da, db = MODELS[a], MODELS[b]
        diff = {}
        for m in METRICS:
            va, vb = da[m], db[m]
            delta = vb - va
            if m in ("mae", "latency_ms", "cost_per_run"):
                better = "b" if delta < 0 else ("a" if delta > 0 else "tie")
            else:
                better = "b" if delta > 0 else ("a" if delta < 0 else "tie")
            diff[m] = {"a": va, "b": vb, "delta": round(delta, 4), "better": better}
        wins_b = sum(1 for v in diff.values() if v["better"] == "b")
        wins_a = sum(1 for v in diff.values() if v["better"] == "a")
        return JSONResponse(content={
            "model_a": a, "model_b": b,
            "metrics": diff,
            "winner": b if wins_b > wins_a else (a if wins_a > wins_b else "tie"),
            "score": {a: wins_a, b: wins_b},
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise SystemExit("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("model_comparison:app", host="0.0.0.0", port=8134, reload=True)
