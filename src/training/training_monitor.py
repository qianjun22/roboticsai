"""Training Monitor — FastAPI port 8132

Real-time dashboard for active GR00T / DAgger training runs.
"""

import math
import random
import json
from typing import Dict, Any, List

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    import uvicorn
except ImportError:  # pragma: no cover
    raise ImportError("Install fastapi and uvicorn: pip install fastapi uvicorn")

app = FastAPI(title="Training Monitor", version="1.0.0")

# ---------------------------------------------------------------------------
# Static run data
# ---------------------------------------------------------------------------

RUNS: Dict[str, Dict[str, Any]] = {
    "dagger_run10": {
        "id": "dagger_run10",
        "step": 1420,
        "max_steps": 5000,
        "loss": 0.094,
        "sr": 0.0,
        "eta": "6.2h",
        "gpu": "ashburn-prod-1",
        "lr": 1e-4,
        "color": "#38bdf8",  # sky blue
    },
    "groot_finetune_v3": {
        "id": "groot_finetune_v3",
        "step": 800,
        "max_steps": 3000,
        "loss": 0.112,
        "sr": 0.0,
        "eta": "4.8h",
        "gpu": "ashburn-canary-1",
        "lr": 5e-5,
        "color": "#f59e0b",  # amber
    },
    "hpo_search_v3": {
        "id": "hpo_search_v3",
        "step": 340,
        "max_steps": 1000,
        "loss": 0.087,
        "sr": 0.0,
        "eta": "2.1h",
        "gpu": "phoenix-eval-1",
        "lr": 2e-4,
        "color": "#4ade80",  # green
    },
}

# ---------------------------------------------------------------------------
# Loss history generation (seeded, exponential decay + noise)
# ---------------------------------------------------------------------------

def _loss_history(start: float, final: float, n: int, seed: int) -> List[float]:
    """Generate n loss values decaying from start toward final with noise."""
    rng = random.Random(seed)
    history: List[float] = []
    for i in range(n):
        t = i / max(n - 1, 1)
        smooth = start * math.exp(-3.0 * t) + final * (1 - math.exp(-3.0 * t))
        noise = rng.gauss(0, 0.005)
        history.append(round(max(0.0, smooth + noise), 4))
    return history


LOSS_HISTORIES: Dict[str, List[float]] = {
    "dagger_run10": _loss_history(0.35, 0.094, 50, seed=42),
    "groot_finetune_v3": _loss_history(0.35, 0.112, 50, seed=7),
    "hpo_search_v3": _loss_history(0.35, 0.087, 50, seed=13),
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _loss_curves_svg() -> str:
    """680x220 SVG with polylines for each run's loss history."""
    W, H = 680, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 18, 38
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    y_max = 0.40

    def to_px(i: int, val: float, n: int) -> str:
        x = PAD_L + (i / (n - 1)) * chart_w
        y = PAD_T + (1 - val / y_max) * chart_h
        return f"{x:.1f},{y:.1f}"

    lines = []
    for run in RUNS.values():
        history = LOSS_HISTORIES[run["id"]]
        pts = " ".join(to_px(i, v, len(history)) for i, v in enumerate(history))
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{run["color"]}" '
            f'stroke-width="2" stroke-linejoin="round"/>'
        )

    # Y-axis ticks
    y_ticks = ""
    for tick in [0.0, 0.1, 0.2, 0.3, 0.4]:
        y = PAD_T + (1 - tick / y_max) * chart_h
        y_ticks += (
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
            f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end">{tick:.1f}</text>'
        )

    # X-axis label
    x_labels = ""
    for pct in [0, 25, 50, 75, 100]:
        x = PAD_L + (pct / 100) * chart_w
        x_labels += (
            f'<text x="{x:.1f}" y="{H - 6}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">{pct}%</text>'
        )

    # Legend
    legend = ""
    for idx, run in enumerate(RUNS.values()):
        lx = PAD_L + idx * 200
        ly = H - 10
        legend += (
            f'<rect x="{lx}" y="{ly - 8}" width="12" height="4" fill="{run["color"]}"/>'
            f'<text x="{lx + 16}" y="{ly - 1}" fill="#cbd5e1" font-size="9">{run["id"]}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'{y_ticks}{x_labels}'
        + "\n".join(lines)
        + legend
        + "</svg>"
    )


def _progress_bars_html() -> str:
    """Horizontal progress bars for each run."""
    html = ""
    for run in RUNS.values():
        pct = round(run["step"] / run["max_steps"] * 100, 1)
        html += f"""
        <div style="margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="color:#e2e8f0;font-size:13px;font-weight:600;">{run['id']}</span>
            <span style="color:#94a3b8;font-size:12px;">{run['step']:,} / {run['max_steps']:,} steps &nbsp; ({pct}%) &nbsp; ETA: {run['eta']}</span>
          </div>
          <div style="background:#1e293b;border-radius:4px;height:12px;overflow:hidden;">
            <div style="background:{run['color']};width:{pct}%;height:100%;border-radius:4px;"></div>
          </div>
        </div>
        """
    return html


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Training Monitor — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 16px 22px; min-width: 150px; flex: 1; }}
  .card-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
  .card-value {{ color: #38bdf8; font-size: 26px; font-weight: 700; margin-top: 4px; }}
  .card-unit {{ color: #94a3b8; font-size: 12px; }}
  .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  .section-title {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 14px; }}
  .run-meta {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; }}
  .badge {{ background: #0f172a; border-radius: 4px; padding: 2px 8px; font-size: 11px; color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ color: #64748b; font-weight: 500; text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:last-child td {{ border-bottom: none; }}
  .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
</style>
</head>
<body>
<h1>Training Monitor</h1>
<p class="sub">OCI Robot Cloud &mdash; port 8132 &mdash; {ts}</p>

<div class="cards">
  <div class="card"><div class="card-label">Active Runs</div><div class="card-value">3</div><div class="card-unit">training jobs</div></div>
  <div class="card"><div class="card-label">GPU-Hours Consumed</div><div class="card-value">12.4</div><div class="card-unit">hr</div></div>
  <div class="card"><div class="card-label">Estimated Cost</div><div class="card-value">$37.94</div><div class="card-unit">USD</div></div>
  <div class="card"><div class="card-label">Avg GPU Util</div><div class="card-value">84%</div><div class="card-unit">utilization</div></div>
</div>

<div class="section">
  <div class="section-title">Loss Curves (all runs)</div>
  {loss_svg}
</div>

<div class="section">
  <div class="section-title">Progress</div>
  {progress_bars}
</div>

<div class="section">
  <div class="section-title">Run Details</div>
  <table>
    <thead><tr><th>Run ID</th><th>Step</th><th>Loss</th><th>LR</th><th>GPU</th><th>ETA</th></tr></thead>
    <tbody>
    {run_rows}
    </tbody>
  </table>
</div>
</body>
</html>
"""


def _run_rows_html() -> str:
    rows = ""
    for run in RUNS.values():
        pct = round(run["step"] / run["max_steps"] * 100, 1)
        rows += (
            f'<tr>'
            f'<td><span class="dot" style="background:{run["color"]}"></span>{run["id"]}</td>'
            f'<td>{run["step"]:,} / {run["max_steps"]:,} ({pct}%)</td>'
            f'<td>{run["loss"]:.4f}</td>'
            f'<td>{run["lr"]:g}</td>'
            f'<td>{run["gpu"]}</td>'
            f'<td>{run["eta"]}</td>'
            f'</tr>'
        )
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = DASHBOARD_HTML.format(
        ts=ts,
        loss_svg=_loss_curves_svg(),
        progress_bars=_progress_bars_html(),
        run_rows=_run_rows_html(),
    )
    return HTMLResponse(content=html)


@app.get("/runs")
async def list_runs():
    result = []
    for run in RUNS.values():
        r = dict(run)
        pct = round(run["step"] / run["max_steps"] * 100, 2)
        r["progress_pct"] = pct
        r["loss_history"] = LOSS_HISTORIES[run["id"]]
        result.append(r)
    return {"runs": result, "count": len(result)}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    run = dict(RUNS[run_id])
    run["progress_pct"] = round(run["step"] / run["max_steps"] * 100, 2)
    run["loss_history"] = LOSS_HISTORIES[run_id]
    return run


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("training_monitor:app", host="0.0.0.0", port=8132, reload=True)
