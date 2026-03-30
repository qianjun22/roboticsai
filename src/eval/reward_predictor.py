"""Reward Predictor — predict episode success from partial trajectory (port 8161)."""
import math

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
MODEL_TRAINED_ON = 1000  # episodes
MAX_STEPS = 847

ACCURACY_DATA = [
    {"steps": 50,  "pct": 5,   "accuracy": 0.61, "auc": 0.68, "false_positive_rate": 0.22, "false_negative_rate": 0.31},
    {"steps": 100, "pct": 12,  "accuracy": 0.72, "auc": 0.79, "false_positive_rate": 0.18, "false_negative_rate": 0.24},
    {"steps": 200, "pct": 24,  "accuracy": 0.81, "auc": 0.87, "false_positive_rate": 0.12, "false_negative_rate": 0.16},
    {"steps": 400, "pct": 47,  "accuracy": 0.89, "auc": 0.93, "false_positive_rate": 0.08, "false_negative_rate": 0.09},
    {"steps": 600, "pct": 71,  "accuracy": 0.94, "auc": 0.97, "false_positive_rate": 0.04, "false_negative_rate": 0.05},
    {"steps": 847, "pct": 100, "accuracy": 0.98, "auc": 0.99, "false_positive_rate": 0.01, "false_negative_rate": 0.01},
]

EARLY_TERM_STEPS = 400
_STEPS_SAVED_PER_FAILED_EPISODE = round(MAX_STEPS * 0.22 * 0.53)  # = 99


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _accuracy_chart_svg() -> str:
    """Line chart: accuracy + AUC vs steps, with dashed thresholds."""
    W, H = 680, 220
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    def _x(steps: int) -> float:
        return pad_l + (steps / MAX_STEPS) * chart_w

    def _y(val: float) -> float:
        return pad_t + chart_h - (val - 0.55) / 0.45 * chart_h

    # Grid
    grids = []
    for tick in [0.6, 0.7, 0.8, 0.9, 1.0]:
        y = _y(tick)
        grids.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W - pad_r}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
            f'<text x="{pad_l - 5}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end">{tick:.1f}</text>'
        )

    # Threshold dashed lines at 0.8 and 0.9
    dashes = []
    for thresh, label in [(0.8, "0.80"), (0.9, "0.90")]:
        y = _y(thresh)
        dashes.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W - pad_r}" y2="{y:.1f}" '
            f'stroke="#475569" stroke-width="1" stroke-dasharray="4 3"/>'
            f'<text x="{W - pad_r + 2}" y="{y + 4:.1f}" fill="#475569" font-size="9">{label}</text>'
        )

    # Lines
    def _polyline(key: str, color: str) -> str:
        pts = " ".join(
            f"{_x(d['steps']):.1f},{_y(d[key]):.1f}" for d in ACCURACY_DATA
        )
        return (
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    acc_line = _polyline("accuracy", "#38bdf8")
    auc_line = _polyline("auc", "#fb923c")

    # Dots
    dots = []
    for d in ACCURACY_DATA:
        for key, color in [("accuracy", "#38bdf8"), ("auc", "#fb923c")]:
            dots.append(
                f'<circle cx="{_x(d["steps"]):.1f}" cy="{_y(d[key]):.1f}" r="3.5" '
                f'fill="{color}"/>'
            )

    # Early-termination annotation at step 400
    et_x = _x(EARLY_TERM_STEPS)
    annotation = (
        f'<line x1="{et_x:.1f}" y1="{pad_t}" x2="{et_x:.1f}" y2="{pad_t + chart_h}" '
        f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="3 2"/>'
        f'<text x="{et_x + 4:.1f}" y="{pad_t + 14}" fill="#C74634" font-size="9">'
        f'early term @ 400 steps (89% acc)</text>'
    )

    # x-axis labels
    xlabels = []
    for d in ACCURACY_DATA:
        x = _x(d["steps"])
        xlabels.append(
            f'<text x="{x:.1f}" y="{H - pad_b + 14}" fill="#94a3b8" font-size="8.5" '
            f'text-anchor="middle">{d["steps"]}\n({d["pct"]}%)</text>'
            f'<text x="{x:.1f}" y="{H - pad_b + 24}" fill="#64748b" font-size="8" '
            f'text-anchor="middle">({d["pct"]}%)</text>'
        )

    legend = (
        '<rect x="60" y="4" width="10" height="10" fill="#38bdf8"/>'
        '<text x="74" y="13" fill="#cbd5e1" font-size="10">accuracy</text>'
        '<rect x="160" y="4" width="10" height="10" fill="#fb923c"/>'
        '<text x="174" y="13" fill="#cbd5e1" font-size="10">AUC-ROC</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        + legend
        + "".join(grids)
        + "".join(dashes)
        + acc_line + auc_line
        + "".join(dots)
        + annotation
        + "</svg>"
    )


def _roc_svg() -> str:
    """ROC curves for different step counts."""
    W, H = 480, 320
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    def _cx(fpr: float) -> float:
        return pad_l + fpr * chart_w

    def _cy(tpr: float) -> float:
        return pad_t + chart_h - tpr * chart_h

    # Diagonal reference
    diag = (
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t}" '
        f'stroke="#334155" stroke-width="1" stroke-dasharray="4 3"/>'
    )

    # Grid
    grids = []
    for tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = _cy(tick)
        gx = _cx(tick)
        grids.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + chart_w}" y2="{gy:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{pad_l - 4}" y="{gy + 4:.1f}" fill="#475569" font-size="8" '
            f'text-anchor="end">{tick:.1f}</text>'
            f'<text x="{gx:.1f}" y="{pad_t + chart_h + 12}" fill="#475569" font-size="8" '
            f'text-anchor="middle">{tick:.1f}</text>'
        )

    # Approximate ROC curve for each step count
    # Color gradient: sky blue (#38bdf8) → Oracle red (#C74634)
    step_colors = ["#38bdf8", "#60a5fa", "#a78bfa", "#f472b6", "#C74634"]
    curves = []
    legend_items = []
    for ci, d in enumerate(ACCURACY_DATA[:-1]):  # skip 100% for clarity
        auc = d["auc"]
        fpr_end = d["false_positive_rate"]
        col = step_colors[min(ci, len(step_colors) - 1)]
        # Build approximate ROC: (0,0) → several points → (1,1)
        # Use a simple parametric model: tpr = fpr^((1-auc)/(auc+0.001))
        exp = (1 - auc) / (auc + 1e-6)
        pts_list = [(0.0, 0.0)]
        for t in range(1, 21):
            fpr = t / 20
            tpr = min(1.0, fpr ** exp)
            pts_list.append((fpr, tpr))
        pts_list.append((1.0, 1.0))
        pts_str = " ".join(f"{_cx(x):.1f},{_cy(y):.1f}" for x, y in pts_list)
        curves.append(
            f'<polyline points="{pts_str}" fill="none" stroke="{col}" stroke-width="2" '
            f'stroke-linejoin="round"/>'
        )
        lx = pad_l + 10
        ly = pad_t + 10 + ci * 22
        legend_items.append(
            f'<rect x="{W - 110}" y="{ly - 8}" width="10" height="10" fill="{col}"/>'
            f'<text x="{W - 96}" y="{ly + 1}" fill="#cbd5e1" font-size="9">'
            f'{d["steps"]} steps (AUC={d["auc"]})</text>'
        )

    axis_labels = (
        f'<text x="{pad_l + chart_w / 2}" y="{H - 4}" fill="#64748b" font-size="9" '
        f'text-anchor="middle">False Positive Rate</text>'
        f'<text x="12" y="{pad_t + chart_h / 2}" fill="#64748b" font-size="9" '
        f'text-anchor="middle" transform="rotate(-90,12,{pad_t + chart_h / 2})">True Positive Rate</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(grids)
        + diag
        + "".join(curves)
        + "".join(legend_items)
        + axis_labels
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _build_html() -> str:
    acc_svg = _accuracy_chart_svg()
    roc_svg = _roc_svg()

    et_row = next(d for d in ACCURACY_DATA if d["steps"] == EARLY_TERM_STEPS)

    rows = ""
    for d in ACCURACY_DATA:
        highlight = "color:#C74634;font-weight:700" if d["steps"] == EARLY_TERM_STEPS else ""
        badge = ' <span style="background:#C74634;color:#fff;padding:1px 5px;border-radius:3px;font-size:9px">THRESHOLD</span>' if d["steps"] == EARLY_TERM_STEPS else ""
        rows += f"""
        <tr>
          <td style="padding:6px 10px;{highlight}">{d['steps']}{badge}</td>
          <td style="padding:6px 10px;color:#64748b;text-align:center">{d['pct']}%</td>
          <td style="padding:6px 10px;color:#38bdf8;text-align:center">{d['accuracy']:.2f}</td>
          <td style="padding:6px 10px;color:#fb923c;text-align:center">{d['auc']:.2f}</td>
          <td style="padding:6px 10px;color:#f87171;text-align:center">{d['false_positive_rate']:.2f}</td>
          <td style="padding:6px 10px;color:#fbbf24;text-align:center">{d['false_negative_rate']:.2f}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Reward Predictor — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 14px; border-top: 3px solid #C74634; }}
    .card-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
    .card-value {{ color: #38bdf8; font-size: 26px; font-weight: 700; margin-top: 4px; }}
    .card-sub {{ color: #475569; font-size: 11px; margin-top: 2px; }}
    section {{ margin-bottom: 28px; }}
    h2 {{ color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: .07em; margin-bottom: 10px; }}
    .charts {{ display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #64748b; text-align: left; padding: 6px 10px; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #334155; }}
    tr:hover td {{ background: #1e293b; }}
  </style>
</head>
<body>
  <h1>Reward Predictor</h1>
  <div class="sub">Learned reward model &mdash; predict episode success from partial trajectory &mdash; port 8161 &mdash; trained on {MODEL_TRAINED_ON} episodes</div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Early Term @ 400 Steps</div>
      <div class="card-value">{et_row['accuracy']:.0%}</div>
      <div class="card-sub">accuracy, AUC {et_row['auc']:.2f}</div>
    </div>
    <div class="card">
      <div class="card-label">Time Saved</div>
      <div class="card-value">53%</div>
      <div class="card-sub">episode time on failed episodes</div>
    </div>
    <div class="card">
      <div class="card-label">Steps Saved</div>
      <div class="card-value">{_STEPS_SAVED_PER_FAILED_EPISODE}</div>
      <div class="card-sub">per failed episode (847×0.22×0.53)</div>
    </div>
    <div class="card">
      <div class="card-label">Full Traj Accuracy</div>
      <div class="card-value">98%</div>
      <div class="card-sub">AUC 0.99 @ 847 steps</div>
    </div>
  </div>

  <section>
    <h2>Accuracy &amp; AUC vs Trajectory Steps</h2>
    {acc_svg}
  </section>

  <section>
    <h2>ROC Curves by Step Count</h2>
    <div class="charts">
      {roc_svg}
    </div>
  </section>

  <section>
    <h2>Prediction Accuracy by Trajectory Length</h2>
    <table>
      <thead><tr>
        <th>Steps</th><th style="text-align:center">Traj %</th>
        <th style="text-align:center">Accuracy</th>
        <th style="text-align:center">AUC</th>
        <th style="text-align:center">FPR</th>
        <th style="text-align:center">FNR</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>

  <div style="color:#334155;font-size:11px;margin-top:16px">
    Early termination threshold: step 400 (89% accuracy) &mdash;
    terminate failed episodes early &rarr; save 53% episode time &mdash;
    {_STEPS_SAVED_PER_FAILED_EPISODE} steps saved per failed episode
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Reward Predictor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/accuracy")
    def get_accuracy():
        return JSONResponse({"model_trained_on": MODEL_TRAINED_ON, "max_steps": MAX_STEPS, "data": ACCURACY_DATA})

    @app.get("/predict")
    def predict(steps: int = EARLY_TERM_STEPS):
        # Find nearest data point
        best = min(ACCURACY_DATA, key=lambda d: abs(d["steps"] - steps))
        recommendation = "terminate" if best["accuracy"] >= 0.89 else "continue"
        return JSONResponse({
            "requested_steps": steps,
            "nearest_checkpoint": best["steps"],
            "accuracy": best["accuracy"],
            "auc": best["auc"],
            "false_positive_rate": best["false_positive_rate"],
            "false_negative_rate": best["false_negative_rate"],
            "recommendation": recommendation,
            "early_termination_threshold_steps": EARLY_TERM_STEPS,
            "steps_saved_per_failed_episode": _STEPS_SAVED_PER_FAILED_EPISODE,
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise SystemExit("uvicorn not installed — pip install uvicorn fastapi")
    uvicorn.run(app, host="0.0.0.0", port=8161)
