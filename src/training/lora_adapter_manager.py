"""LoRA Adapter Registry and Performance Tracker — port 8152."""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

ADAPTERS = {
    "adapter_r4": {
        "id": "adapter_r4",
        "rank": 4,
        "alpha": 8,
        "params_m": 2.1,
        "sr": 0.61,
        "mae": 0.041,
        "size_mb": 8.4,
        "training_steps": 3000,
        "status": "ARCHIVED",
    },
    "adapter_r8": {
        "id": "adapter_r8",
        "rank": 8,
        "alpha": 16,
        "params_m": 4.2,
        "sr": 0.69,
        "mae": 0.032,
        "size_mb": 16.8,
        "training_steps": 3000,
        "status": "ARCHIVED",
    },
    "adapter_r16": {
        "id": "adapter_r16",
        "rank": 16,
        "alpha": 32,
        "params_m": 8.4,
        "sr": 0.78,
        "mae": 0.023,
        "size_mb": 33.6,
        "training_steps": 5000,
        "status": "PRODUCTION",
    },
    "adapter_r24": {
        "id": "adapter_r24",
        "rank": 24,
        "alpha": 48,
        "params_m": 12.6,
        "sr": 0.76,
        "mae": 0.026,
        "size_mb": 50.4,
        "training_steps": 5000,
        "status": "STAGING",
    },
    "adapter_r32": {
        "id": "adapter_r32",
        "rank": 32,
        "alpha": 64,
        "params_m": 16.8,
        "sr": 0.74,
        "mae": 0.029,
        "size_mb": 67.2,
        "training_steps": 5000,
        "status": "EXPERIMENTAL",
    },
    "adapter_r16_v2": {
        "id": "adapter_r16_v2",
        "rank": 16,
        "alpha": 32,
        "params_m": 8.4,
        "sr": 0.81,
        "mae": 0.019,
        "size_mb": 33.6,
        "training_steps": 8000,
        "status": "STAGING",
    },
}

STATUS_COLOR = {
    "PRODUCTION": "#22c55e",
    "STAGING": "#38bdf8",
    "EXPERIMENTAL": "#f59e0b",
    "ARCHIVED": "#6b7280",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_sr_vs_rank() -> str:
    """SR vs rank scatter with bubble size proportional to params (680x220)."""
    W, H, PL, PR, PT, PB = 680, 220, 60, 30, 20, 40
    plot_w = W - PL - PR
    plot_h = H - PT - PB

    ranks = [a["rank"] for a in ADAPTERS.values()]
    srs = [a["sr"] for a in ADAPTERS.values()]
    x_min, x_max = 0, 36
    y_min, y_max = 0.55, 0.85

    def px(rank):
        return PL + (rank - x_min) / (x_max - x_min) * plot_w

    def py(sr):
        return PT + plot_h - (sr - y_min) / (y_max - y_min) * plot_h

    # Dashed baseline y=0.78
    baseline_y = py(0.78)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Axes
    lines.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PL}" y1="{PT+plot_h}" x2="{PL+plot_w}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')

    # Baseline
    lines.append(f'<line x1="{PL}" y1="{baseline_y:.1f}" x2="{PL+plot_w}" y2="{baseline_y:.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{PL+plot_w-2}" y="{baseline_y-4:.1f}" fill="#f59e0b" font-size="10" text-anchor="end">SR=0.78 baseline</text>')

    # Y-axis ticks
    for sr_tick in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        ty = py(sr_tick)
        lines.append(f'<line x1="{PL-4}" y1="{ty:.1f}" x2="{PL}" y2="{ty:.1f}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{PL-6}" y="{ty+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{sr_tick:.2f}</text>')

    # X-axis ticks
    for r_tick in [4, 8, 16, 24, 32]:
        tx = px(r_tick)
        lines.append(f'<line x1="{tx:.1f}" y1="{PT+plot_h}" x2="{tx:.1f}" y2="{PT+plot_h+4}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{tx:.1f}" y="{PT+plot_h+16}" fill="#94a3b8" font-size="10" text-anchor="middle">{r_tick}</text>')

    # Axis labels
    lines.append(f'<text x="{PL+plot_w//2}" y="{H-2}" fill="#94a3b8" font-size="11" text-anchor="middle">LoRA Rank</text>')
    lines.append(f'<text x="14" y="{PT+plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PT+plot_h//2})">Success Rate</text>')
    lines.append(f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">SR vs LoRA Rank</text>')

    # Bubbles
    max_params = 16.8
    for a in ADAPTERS.values():
        cx = px(a["rank"])
        cy = py(a["sr"])
        r = 6 + (a["params_m"] / max_params) * 18
        color = STATUS_COLOR.get(a["status"], "#94a3b8")
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.7" stroke="{color}" stroke-width="1.5"/>')
        if a["status"] == "PRODUCTION":
            lines.append(f'<text x="{cx:.1f}" y="{cy+4:.1f}" fill="#ffffff" font-size="14" text-anchor="middle" font-weight="bold">&#9733;</text>')
        lines.append(f'<text x="{cx:.1f}" y="{cy-r-4:.1f}" fill="{color}" font-size="9" text-anchor="middle">{a["id"]}</text>')

    # Legend
    lx = PL + 4
    for i, (status, color) in enumerate(STATUS_COLOR.items()):
        lines.append(f'<circle cx="{lx+6}" cy="{PT+6+i*14}" r="5" fill="{color}" fill-opacity="0.7"/>')
        lines.append(f'<text x="{lx+14}" y="{PT+10+i*14}" fill="#94a3b8" font-size="9">{status}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _svg_params_vs_sr() -> str:
    """Params vs SR with Pareto frontier (680x200)."""
    W, H, PL, PR, PT, PB = 680, 200, 60, 30, 20, 40
    plot_w = W - PL - PR
    plot_h = H - PT - PB

    x_min, x_max = 0, 18
    y_min, y_max = 0.55, 0.85

    def px(p):
        return PL + (p - x_min) / (x_max - x_min) * plot_w

    def py(sr):
        return PT + plot_h - (sr - y_min) / (y_max - y_min) * plot_h

    # Pareto-optimal: at each params level, highest SR not dominated
    sorted_adapters = sorted(ADAPTERS.values(), key=lambda a: a["params_m"])
    pareto = []
    best_sr = 0.0
    for a in sorted_adapters:
        if a["sr"] >= best_sr:
            best_sr = a["sr"]
            pareto.append(a)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Axes
    lines.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PL}" y1="{PT+plot_h}" x2="{PL+plot_w}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')

    # Pareto frontier line
    if len(pareto) >= 2:
        pts = ' '.join(f"{px(a['params_m']):.1f},{py(a['sr']):.1f}" for a in pareto)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="4,2"/>')

    # Y-axis ticks
    for sr_tick in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        ty = py(sr_tick)
        lines.append(f'<line x1="{PL-4}" y1="{ty:.1f}" x2="{PL}" y2="{ty:.1f}" stroke="#475569"/>')
        lines.append(f'<text x="{PL-6}" y="{ty+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{sr_tick:.2f}</text>')

    # X-axis ticks
    for p_tick in [2, 4, 6, 8, 10, 12, 14, 16]:
        tx = px(p_tick)
        lines.append(f'<line x1="{tx:.1f}" y1="{PT+plot_h}" x2="{tx:.1f}" y2="{PT+plot_h+4}" stroke="#475569"/>')
        lines.append(f'<text x="{tx:.1f}" y="{PT+plot_h+16}" fill="#94a3b8" font-size="10" text-anchor="middle">{p_tick}</text>')

    # Axis labels
    lines.append(f'<text x="{PL+plot_w//2}" y="{H-2}" fill="#94a3b8" font-size="11" text-anchor="middle">Params (M)</text>')
    lines.append(f'<text x="14" y="{PT+plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PT+plot_h//2})">Success Rate</text>')
    lines.append(f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">Params vs SR — Efficiency Frontier</text>')

    # Dots
    for a in ADAPTERS.values():
        cx = px(a["params_m"])
        cy = py(a["sr"])
        color = STATUS_COLOR.get(a["status"], "#94a3b8")
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}" stroke="#ffffff" stroke-width="1"/>')
        lines.append(f'<text x="{cx+8:.1f}" y="{cy+4:.1f}" fill="{color}" font-size="9">{a["id"]}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    svg1 = _svg_sr_vs_rank()
    svg2 = _svg_params_vs_sr()

    rows = []
    for a in sorted(ADAPTERS.values(), key=lambda x: -x["sr"]):
        color = STATUS_COLOR.get(a["status"], "#94a3b8")
        rows.append(
            f'<tr>'
            f'<td style="padding:8px 12px;font-family:monospace;color:#e2e8f0">{a["id"]}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{a["rank"]}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{a["alpha"]}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{a["params_m"]}M</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#38bdf8;font-weight:bold">{a["sr"]:.2f}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{a["mae"]:.3f}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{a["training_steps"]:,}</td>'
            f'<td style="padding:8px 12px;text-align:center">'
            f'<span style="background:{color}22;color:{color};border:1px solid {color};border-radius:4px;padding:2px 8px;font-size:12px">{a["status"]}</span>'
            f'</td>'
            f'</tr>'
        )

    table_rows = ''.join(rows)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>LoRA Adapter Manager — port 8152</title>
<style>
  body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; }}
  .header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:16px 24px; display:flex; align-items:center; gap:12px; }}
  .header h1 {{ margin:0; font-size:20px; color:#ffffff; }}
  .badge {{ background:#C74634; color:#fff; border-radius:4px; padding:3px 10px; font-size:12px; font-weight:bold; }}
  .port {{ background:#1e3a5f; color:#38bdf8; border-radius:4px; padding:3px 10px; font-size:12px; }}
  .section {{ padding:20px 24px; }}
  .section h2 {{ margin:0 0 14px 0; font-size:15px; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; }}
  .charts {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:0 24px 20px; }}
  .card {{ background:#1e293b; border-radius:8px; padding:16px; border:1px solid #334155; }}
  .rec {{ background:#0f2a1a; border:1px solid #22c55e; border-radius:8px; padding:14px 18px; margin:0 24px 20px; }}
  .rec-title {{ color:#22c55e; font-size:13px; font-weight:bold; margin-bottom:6px; }}
  .rec-body {{ color:#86efac; font-size:13px; line-height:1.6; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#0f172a; color:#64748b; font-size:12px; text-transform:uppercase; padding:8px 12px; text-align:left; border-bottom:1px solid #334155; }}
  tr:hover {{ background:#1e293b44; }}
  tr:not(:last-child) td {{ border-bottom:1px solid #1e293b; }}
</style>
</head>
<body>
<div class="header">
  <span class="badge">OCI Robot Cloud</span>
  <h1>LoRA Adapter Registry</h1>
  <span class="port">port 8152</span>
</div>

<div class="section">
  <h2>Rank Analysis</h2>
</div>
<div class="charts">
  <div class="card">{svg1}</div>
  <div class="card">{svg2}</div>
</div>

<div class="rec">
  <div class="rec-title">Recommendation</div>
  <div class="rec-body">rank=16 optimal efficiency. adapter_r16_v2 (8k steps) shows +3pp gain at same param cost — promote to PRODUCTION</div>
</div>

<div class="section">
  <h2>All Adapters</h2>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Rank</th><th>Alpha</th><th>Params</th>
        <th>SR</th><th>MAE</th><th>Steps</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="LoRA Adapter Manager", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_dashboard_html())


@app.get("/adapters")
async def list_adapters():
    return JSONResponse(content=list(ADAPTERS.values()))


@app.get("/adapters/{adapter_id}")
async def get_adapter(adapter_id: str):
    if adapter_id not in ADAPTERS:
        raise HTTPException(status_code=404, detail=f"Adapter '{adapter_id}' not found")
    return JSONResponse(content=ADAPTERS[adapter_id])


@app.get("/optimal")
async def get_optimal():
    """Return the adapter with best SR/params trade-off (Pareto-optimal, most efficient)."""
    best = max(ADAPTERS.values(), key=lambda a: a["sr"] / a["params_m"])
    return JSONResponse(content={
        "optimal": best,
        "recommendation": "rank=16 optimal efficiency. adapter_r16_v2 (8k steps) shows +3pp gain at same param cost — promote to PRODUCTION",
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8152)
