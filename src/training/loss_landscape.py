"""Loss landscape visualizer — FastAPI port 8137."""

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
import random
from typing import Optional, List

# ---------------------------------------------------------------------------
# Grid generation
# ---------------------------------------------------------------------------

# Log-spaced LR: 21 points from 1e-5 to 1e-3
LR_POINTS = 21
LR_MIN_LOG = math.log10(1e-5)
LR_MAX_LOG = math.log10(1e-3)
LR_RANGE = [10 ** (LR_MIN_LOG + i * (LR_MAX_LOG - LR_MIN_LOG) / (LR_POINTS - 1))
            for i in range(LR_POINTS)]

BATCH_RANGE = [16, 24, 32, 48, 64, 80, 96, 128]

OPT_LR = 1e-4
OPT_BATCH = 64
BASE_LOSS = 0.089

_rng = random.Random(42)


def _loss(lr: float, batch: int) -> float:
    lr_term = 2.1 * (math.log10(lr) - math.log10(OPT_LR)) ** 2
    batch_term = 0.0003 * (batch - OPT_BATCH) ** 2
    noise = _rng.gauss(0, 0.002)
    return BASE_LOSS + lr_term + batch_term + noise


def _build_grid() -> List[List[float]]:
    """Returns grid[batch_idx][lr_idx]."""
    _rng.seed(42)
    return [
        [round(_loss(lr, batch), 5) for lr in LR_RANGE]
        for batch in BATCH_RANGE
    ]


GRID = _build_grid()

# Stat precomputation
_all_losses = [GRID[bi][li] for bi in range(len(BATCH_RANGE)) for li in range(LR_POINTS)]
_min_loss = min(_all_losses)
_max_loss = max(_all_losses)
_opt_lr_idx = min(range(LR_POINTS), key=lambda i: abs(LR_RANGE[i] - OPT_LR))
_opt_batch_idx = BATCH_RANGE.index(OPT_BATCH)

# Sharpness: loss at 10x lr vs optimal
_lr_10x = OPT_LR * 10
_lr_10x_idx = min(range(LR_POINTS), key=lambda i: abs(LR_RANGE[i] - _lr_10x))
_sharpness = round(GRID[_opt_batch_idx][_lr_10x_idx] / GRID[_opt_batch_idx][_opt_lr_idx], 2)

# Flat region: cells with loss < 0.10
_flat_count = sum(1 for v in _all_losses if v < 0.10)

# LR slice at optimal batch
LR_SLICE = [GRID[_opt_batch_idx][li] for li in range(LR_POINTS)]

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _loss_color(loss: float) -> str:
    """Interpolate green→amber→red by loss value."""
    low, high = 0.089, min(_max_loss, 0.5)
    t = max(0.0, min(1.0, (loss - low) / (high - low)))
    if t < 0.5:
        s = t * 2
        r = int(34 + s * (245 - 34))
        g = int(197 + s * (158 - 197))
        b = int(94 + s * (11 - 94))
    else:
        s = (t - 0.5) * 2
        r = int(245 + s * (239 - 245))
        g = int(158 + s * (68 - 158))
        b = int(11 + s * (68 - 11))
    return f"rgb({r},{g},{b})"


# ---------------------------------------------------------------------------
# SVG: heatmap
# ---------------------------------------------------------------------------

def _heatmap_svg() -> str:
    W, H = 680, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 55
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n_lr = LR_POINTS
    n_batch = len(BATCH_RANGE)
    cell_w = chart_w / n_lr
    cell_h = chart_h / n_batch

    ISO_LEVELS = [0.10, 0.15, 0.20]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Cells
    for bi, batch in enumerate(BATCH_RANGE):
        for li, lr in enumerate(LR_RANGE):
            loss = GRID[bi][li]
            color = _loss_color(loss)
            x = pad_l + li * cell_w
            y = pad_t + bi * cell_h

            # Check iso-boundary: darker if near an iso level
            is_boundary = False
            for iso in ISO_LEVELS:
                if abs(loss - iso) < 0.006:
                    is_boundary = True
                    break
            fill = "#0f172a" if is_boundary else color
            lines.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w:.2f}" height="{cell_h:.2f}" fill="{fill}"/>')

    # Optimum star
    star_x = pad_l + _opt_lr_idx * cell_w + cell_w / 2
    star_y = pad_t + _opt_batch_idx * cell_h + cell_h / 2
    lines.append(f'<text x="{star_x:.1f}" y="{star_y+5:.1f}" text-anchor="middle" font-size="16" fill="white">&#9733;</text>')

    # x-axis labels (every 4th LR)
    for i in range(0, n_lr, 4):
        lx = pad_l + i * cell_w + cell_w / 2
        exp = round(math.log10(LR_RANGE[i]), 1)
        lines.append(f'<text x="{lx:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">1e{exp:.0f}</text>')

    # y-axis labels
    for bi, batch in enumerate(BATCH_RANGE):
        ly = pad_t + bi * cell_h + cell_h / 2 + 4
        lines.append(f'<text x="{pad_l-4}" y="{ly:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{batch}</text>')

    # x-axis title
    lines.append(f'<text x="{W//2}" y="{H-4}" text-anchor="middle" fill="#64748b" font-size="11" font-family="sans-serif">Learning Rate (log scale)</text>')
    # y-axis title
    lines.append(f'<text x="12" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11" font-family="sans-serif" transform="rotate(-90 12 {H//2})">Batch Size</text>')

    # Legend
    legend_x = pad_l
    legend_y = H - pad_b + 28
    grad_w = 80
    step = grad_w // 8
    for k in range(8):
        t = k / 7
        low, high = 0.089, 0.5
        lv = low + t * (high - low)
        c = _loss_color(lv)
        lines.append(f'<rect x="{legend_x + k*step}" y="{legend_y}" width="{step}" height="8" fill="{c}"/>')
    lines.append(f'<text x="{legend_x}" y="{legend_y+18}" fill="#64748b" font-size="9" font-family="monospace">low</text>')
    lines.append(f'<text x="{legend_x+grad_w}" y="{legend_y+18}" fill="#64748b" font-size="9" font-family="monospace">high</text>')
    lines.append(f'<text x="{legend_x+grad_w+8}" y="{legend_y+8}" fill="#f8fafc" font-size="10" font-family="monospace"> &#9733; = optimum</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG: 1D slice
# ---------------------------------------------------------------------------

def _slice_svg() -> str:
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_v = max(LR_SLICE)
    min_v = min(LR_SLICE)
    span = max_v - min_v if max_v != min_v else 0.001

    def px(i: int) -> float:
        return pad_l + i * chart_w / (LR_POINTS - 1)

    def py(v: float) -> float:
        return pad_t + chart_h - (v - min_v) / span * chart_h

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        yg = pad_t + (1 - frac) * chart_h
        val = min_v + frac * span
        lines.append(f'<line x1="{pad_l}" y1="{yg:.1f}" x2="{W-pad_r}" y2="{yg:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{yg+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{val:.3f}</text>')

    # Polyline
    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(LR_SLICE))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # Optimal point
    ox = px(_opt_lr_idx)
    oy = py(LR_SLICE[_opt_lr_idx])
    lines.append(f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="6" fill="#C74634" stroke="#f8fafc" stroke-width="2"/>')
    lines.append(f'<text x="{ox+8:.1f}" y="{oy-8:.1f}" fill="#f8fafc" font-size="10" font-family="monospace">lr=1e-4 loss={LR_SLICE[_opt_lr_idx]:.4f}</text>')

    # x-axis labels
    for i in range(0, LR_POINTS, 4):
        lx = px(i)
        exp = round(math.log10(LR_RANGE[i]), 1)
        lines.append(f'<text x="{lx:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">1e{exp:.0f}</text>')

    lines.append(f'<text x="{W//2}" y="{H-4}" text-anchor="middle" fill="#64748b" font-size="11" font-family="sans-serif">Learning Rate (batch=64 fixed)</text>')
    lines.append(f'<text x="14" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11" font-family="sans-serif" transform="rotate(-90 14 {H//2})">Loss</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _build_html() -> str:
    heatmap = _heatmap_svg()
    slice_chart = _slice_svg()
    opt_lr_str = f"{OPT_LR:.0e}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OCI Robot Cloud — Loss Landscape</title>
  <style>
    *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:#0f172a; color:#f1f5f9; font-family:system-ui,sans-serif; padding:32px; }}
    h1 {{ font-size:24px; font-weight:800; color:#f8fafc; margin-bottom:4px; }}
    h2 {{ font-size:13px; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin:28px 0 12px; }}
    .grid-4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:24px; }}
    .stat-card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:18px; }}
    .stat-label {{ color:#64748b; font-size:11px; margin-bottom:6px; }}
    .stat-value {{ font-size:26px; font-weight:800; }}
    .oracle-red {{ color:#C74634; }}
    .sky {{ color:#38bdf8; }}
    .green {{ color:#22c55e; }}
    .amber {{ color:#f59e0b; }}
    .chart-box {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px; margin-bottom:24px; }}
    .footer {{ color:#475569; font-size:11px; text-align:center; margin-top:32px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud &mdash; Loss Landscape Visualizer</h1>
  <p style="color:#64748b;margin-bottom:24px">Hyperparameter sensitivity around trial_007 (lr=1e-4, batch=64)</p>

  <div class="grid-4">
    <div class="stat-card">
      <div class="stat-label">Global Minimum Loss</div>
      <div class="stat-value green">{_min_loss:.4f}</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">lr=1e-4, batch=64</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Landscape Sharpness</div>
      <div class="stat-value amber">{_sharpness}×</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">loss ratio at 10× lr</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Flat Region</div>
      <div class="stat-value sky">{_flat_count}</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">cells with loss &lt; 0.10</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Grid Size</div>
      <div class="stat-value oracle-red">{len(BATCH_RANGE)}&times;{LR_POINTS}</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">batch &times; lr points</div>
    </div>
  </div>

  <h2>Loss Heatmap (&#9733; = optimum &nbsp;|&nbsp; dark cells = iso-loss boundaries at 0.10, 0.15, 0.20)</h2>
  <div class="chart-box">{heatmap}</div>

  <h2>1D LR Slice at Optimal Batch (batch=64)</h2>
  <div class="chart-box">{slice_chart}</div>

  <div class="footer">OCI Robot Cloud &mdash; Loss Landscape Visualizer &mdash; Port 8137</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Loss Landscape Visualizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/grid")
    async def grid():
        return JSONResponse(content={
            "grid": GRID,
            "lr_range": [round(lr, 8) for lr in LR_RANGE],
            "batch_range": BATCH_RANGE,
            "optimal": {"lr": OPT_LR, "batch": OPT_BATCH, "loss": GRID[_opt_batch_idx][_opt_lr_idx]},
        })

    @app.get("/slice")
    async def slice_endpoint(
        param: str = Query(default="lr", description="Axis to slice along: lr"),
        batch: int = Query(default=64, description="Batch size to fix for lr-slice"),
    ):
        if param == "lr":
            if batch not in BATCH_RANGE:
                batch = min(BATCH_RANGE, key=lambda b: abs(b - batch))
            bi = BATCH_RANGE.index(batch)
            return JSONResponse(content={
                "param": "lr",
                "fixed_batch": batch,
                "lr_range": [round(lr, 8) for lr in LR_RANGE],
                "loss_values": GRID[bi],
                "optimal_lr": OPT_LR,
                "optimal_loss": GRID[bi][_opt_lr_idx],
            })
        return JSONResponse(content={"error": "Only param=lr supported currently"}, status_code=400)


if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed. Run: pip install fastapi uvicorn")
    uvicorn.run("loss_landscape:app", host="0.0.0.0", port=8137, reload=True)
