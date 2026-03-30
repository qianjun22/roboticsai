"""Multi-task policy trainer — port 8146.

Tracks shared backbone learning across 4 tasks and reports positive transfer.
"""
from __future__ import annotations

import math
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn") from e

app = FastAPI(title="Multi-Task Policy Trainer", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

TASKS: list[dict[str, Any]] = [
    {"name": "cube_lift",     "weight": 0.35, "sr": 0.78, "loss": 0.089, "episodes": 1200,
     "difficulty": "medium", "baseline_sr": 0.71, "color": "#38bdf8"},
    {"name": "cube_place",    "weight": 0.30, "sr": 0.71, "loss": 0.112, "episodes": 900,
     "difficulty": "medium", "baseline_sr": 0.64, "color": "#f59e0b"},
    {"name": "push_to_goal",  "weight": 0.20, "sr": 0.77, "loss": 0.097, "episodes": 600,
     "difficulty": "easy",   "baseline_sr": 0.72, "color": "#22c55e"},
    {"name": "drawer_open",   "weight": 0.15, "sr": 0.43, "loss": 0.187, "episodes": 400,
     "difficulty": "hard",   "baseline_sr": 0.38, "color": "#a855f7"},
]

# Pairwise transfer matrix (source → target), diagonal = 1.0
TRANSFER_MATRIX: list[list[float]] = [
    [1.00, 0.82, 0.61, 0.31],   # cube_lift →
    [0.82, 1.00, 0.58, 0.29],   # cube_place →
    [0.61, 0.58, 1.00, 0.44],   # push_to_goal →
    [0.31, 0.29, 0.44, 1.00],   # drawer_open →
]

TASK_NAMES = [t["name"] for t in TASKS]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _sigmoid_sr(epoch: int, target: float, steepness: float = 0.18) -> float:
    """Sigmoid from ~0.10 at epoch 0 to target at epoch 50."""
    midpoint = 25.0
    raw = 1.0 / (1.0 + math.exp(-steepness * (epoch - midpoint)))
    # re-scale so f(0)→0.10, f(50)→target
    f0 = 1.0 / (1.0 + math.exp(-steepness * (0 - midpoint)))
    f50 = 1.0 / (1.0 + math.exp(-steepness * (50 - midpoint)))
    return 0.10 + (target - 0.10) * (raw - f0) / (f50 - f0)


def _training_curve_svg() -> str:
    W, H = 680, 220
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 40
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    epochs = list(range(51))

    def ex(ep: int) -> float:
        return pad_l + ep * plot_w / 50

    def ey(sr: float) -> float:
        return pad_t + plot_h * (1.0 - sr)

    lines = ""
    for task in TASKS:
        pts = " ".join(
            f"{ex(ep):.1f},{ey(_sigmoid_sr(ep, task['sr'])):.1f}"
            for ep in epochs
        )
        lines += (
            f'<polyline points="{pts}" fill="none" '
            f'stroke="{task["color"]}" stroke-width="2.5" opacity="0.9"/>\n'
        )

    # Y-axis ticks
    y_ticks = ""
    for val in [0.0, 0.25, 0.50, 0.75, 1.0]:
        y = ey(val)
        y_ticks += (
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.5"/>'
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" font-size="10" fill="#94a3b8" '
            f'text-anchor="end">{val:.2f}</text>\n'
        )

    # X-axis ticks
    x_ticks = ""
    for ep in [0, 10, 20, 30, 40, 50]:
        x = ex(ep)
        x_ticks += (
            f'<text x="{x:.1f}" y="{H - 8}" font-size="10" fill="#94a3b8" '
            f'text-anchor="middle">{ep}</text>\n'
        )

    # Legend
    legend = ""
    for i, task in enumerate(TASKS):
        lx = pad_l + i * 160
        legend += (
            f'<rect x="{lx}" y="4" width="12" height="12" fill="{task["color"]}"/>'
            f'<text x="{lx + 16}" y="14" font-size="10" fill="#cbd5e1">{task["name"]}</text>\n'
        )

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{y_ticks}{x_ticks}{lines}{legend}'
        f'<text x="18" y="{pad_t + plot_h//2}" font-size="10" fill="#94a3b8" '
        f'transform="rotate(-90 18 {pad_t + plot_h//2})">Success Rate</text>'
        f'<text x="{pad_l + plot_w//2}" y="{H - 2}" font-size="10" fill="#94a3b8" '
        f'text-anchor="middle">Epoch</text>'
        f'</svg>'
    )


def _donut_svg() -> str:
    W, H, cx, cy, R, r = 420, 280, 160, 140, 110, 60
    total = sum(t["weight"] for t in TASKS)
    start = -math.pi / 2
    paths = ""
    labels = ""
    for task in TASKS:
        sweep = 2 * math.pi * task["weight"] / total
        end = start + sweep
        mid = start + sweep / 2
        lx = cx + (R + 20) * math.cos(mid)
        ly = cy + (R + 20) * math.sin(mid)
        x1, y1 = cx + R * math.cos(start), cy + R * math.sin(start)
        x2, y2 = cx + R * math.cos(end),   cy + R * math.sin(end)
        xi1, yi1 = cx + r * math.cos(end),   cy + r * math.sin(end)
        xi2, yi2 = cx + r * math.cos(start), cy + r * math.sin(start)
        large = 1 if sweep > math.pi else 0
        color = "#C74634" if task["name"] == "cube_lift" else task["color"]
        paths += (
            f'<path d="M {x1:.2f},{y1:.2f} A {R},{R} 0 {large},1 {x2:.2f},{y2:.2f} '
            f'L {xi1:.2f},{yi1:.2f} A {r},{r} 0 {large},0 {xi2:.2f},{yi2:.2f} Z" '
            f'fill="{color}" opacity="0.9" stroke="#0f172a" stroke-width="2"/>\n'
        )
        anchor = "start" if lx > cx else "end"
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="#cbd5e1" '
            f'text-anchor="{anchor}">{task["name"]} {int(task["weight"]*100)}%</text>\n'
        )
        start = end

    center_text = (
        f'<text x="{cx}" y="{cy - 6}" font-size="12" fill="#94a3b8" text-anchor="middle">Task</text>'
        f'<text x="{cx}" y="{cy + 10}" font-size="12" fill="#94a3b8" text-anchor="middle">Weight</text>'
    )
    legend = ""
    for i, task in enumerate(TASKS):
        lx2, ly2 = W - 170, 60 + i * 26
        color = "#C74634" if task["name"] == "cube_lift" else task["color"]
        legend += (
            f'<rect x="{lx2}" y="{ly2 - 10}" width="12" height="12" fill="{color}"/>'
            f'<text x="{lx2 + 16}" y="{ly2}" font-size="11" fill="#cbd5e1">{task["name"]}</text>\n'
        )
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{paths}{center_text}{labels}{legend}</svg>'
    )


def _transfer_matrix_svg() -> str:
    W, H = 480, 200
    cell = 36
    pad_l, pad_t = 90, 40
    n = 4
    short = ["lift", "place", "push", "draw"]

    def color_for(val: float) -> str:
        if val >= 0.9:
            return "#166534"   # dark green (diagonal)
        if val >= 0.6:
            return "#15803d"
        if val >= 0.45:
            return "#86efac"
        if val >= 0.35:
            return "#fef08a"
        return "#ef4444"

    cells = ""
    for row in range(n):
        for col in range(n):
            val = TRANSFER_MATRIX[row][col]
            x = pad_l + col * cell
            y = pad_t + row * cell
            cells += (
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{color_for(val)}" stroke="#0f172a" stroke-width="1"/>'
                f'<text x="{x + cell//2}" y="{y + cell//2 + 4}" font-size="10" '
                f'fill="#0f172a" text-anchor="middle" font-weight="bold">{val:.2f}</text>\n'
            )

    headers = ""
    for i, name in enumerate(short):
        x = pad_l + i * cell + cell // 2
        headers += (
            f'<text x="{x}" y="{pad_t - 8}" font-size="10" fill="#94a3b8" text-anchor="middle">{name}</text>\n'
        )
        y = pad_t + i * cell + cell // 2
        headers += (
            f'<text x="{pad_l - 8}" y="{y + 4}" font-size="10" fill="#94a3b8" text-anchor="end">{name}</text>\n'
        )

    title = (
        f'<text x="{W//2}" y="14" font-size="11" fill="#cbd5e1" text-anchor="middle">'
        f'Transfer Score Matrix (source → target)</text>'
    )
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{title}{headers}{cells}</svg>'
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    avg_sr_multi  = sum(t["sr"] for t in TASKS) / len(TASKS)
    avg_sr_single = sum(t["baseline_sr"] for t in TASKS) / len(TASKS)
    avg_gain      = (avg_sr_multi - avg_sr_single) / avg_sr_single * 100
    total_eps     = sum(t["episodes"] for t in TASKS)

    stat_cards = ""
    stats = [
        ("Avg SR Multi-Task", f"{avg_sr_multi:.3f}", "#38bdf8"),
        ("Avg SR Single-Task", f"{avg_sr_single:.3f}", "#94a3b8"),
        ("Avg Transfer Gain", f"+{avg_gain:.1f}%", "#22c55e"),
        ("Total Episodes", f"{total_eps:,}", "#f59e0b"),
    ]
    for label, val, color in stats:
        stat_cards += f"""
        <div style="background:#1e293b;border-radius:10px;padding:18px 24px;
                    border-left:4px solid {color};min-width:160px">
          <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">{label}</div>
          <div style="font-size:26px;font-weight:700;color:{color}">{val}</div>
        </div>"""

    task_rows = ""
    for t in TASKS:
        gain = t["sr"] - t["baseline_sr"]
        diff_color = "#22c55e" if gain >= 0 else "#ef4444"
        diff_colors = {"easy": "#22c55e", "medium": "#f59e0b", "hard": "#ef4444"}
        task_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                background:{t['color']};margin-right:8px"></span>{t['name']}</td>
          <td style="text-align:center">{t['weight']:.2f}</td>
          <td style="text-align:center;color:#38bdf8">{t['sr']:.3f}</td>
          <td style="text-align:center;color:#94a3b8">{t['baseline_sr']:.3f}</td>
          <td style="text-align:center;color:{diff_color}">+{gain:.2f}</td>
          <td style="text-align:center">{t['loss']:.3f}</td>
          <td style="text-align:center">{t['episodes']:,}</td>
          <td style="text-align:center">
            <span style="background:{diff_colors[t['difficulty']]};color:#0f172a;
                   border-radius:4px;padding:2px 8px;font-size:11px">{t['difficulty']}</span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Multi-Task Policy Trainer · Port 8146</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;padding:28px}}
  h1{{color:#38bdf8;font-size:22px;margin-bottom:4px}}
  h2{{color:#cbd5e1;font-size:15px;margin:28px 0 12px;font-weight:600;text-transform:uppercase;
      letter-spacing:.08em}}
  .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#1e293b;color:#94a3b8;padding:10px 12px;text-align:left;
      font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
  td{{padding:10px 12px;color:#e2e8f0}}
  tr:hover td{{background:#1a2744}}
  .charts{{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start}}
  a{{color:#38bdf8;text-decoration:none;font-size:13px}}
  .nav{{display:flex;gap:12px;margin-bottom:24px}}
</style></head><body>
<div class="nav">
  <a href="/">Dashboard</a>
  <a href="/tasks">Tasks JSON</a>
  <a href="/transfer-matrix">Transfer Matrix JSON</a>
  <a href="/comparison">Comparison JSON</a>
</div>
<h1>Multi-Task Policy Trainer</h1>
<p class="sub">Port 8146 · Shared backbone · 4 tasks · Positive transfer confirmed</p>
<div class="cards">{stat_cards}</div>
<h2>Training Curves — Success Rate over Epochs</h2>
{_training_curve_svg()}
<h2>Per-Task Summary</h2>
<table>
<tr>
  <th>Task</th><th>Weight</th><th>SR (multi)</th><th>SR (single)</th>
  <th>Transfer</th><th>Loss</th><th>Episodes</th><th>Difficulty</th>
</tr>
{task_rows}
</table>
<h2>Charts</h2>
<div class="charts">
  <div><p style="color:#94a3b8;font-size:12px;margin-bottom:8px">Task Weight Allocation</p>
       {_donut_svg()}</div>
  <div><p style="color:#94a3b8;font-size:12px;margin-bottom:8px">Transfer Score Matrix</p>
       {_transfer_matrix_svg()}</div>
</div>
</body></html>"""


@app.get("/tasks")
async def get_tasks() -> JSONResponse:
    return JSONResponse({"tasks": TASKS, "total_episodes": sum(t["episodes"] for t in TASKS)})


@app.get("/transfer-matrix")
async def get_transfer_matrix() -> JSONResponse:
    return JSONResponse({
        "tasks": TASK_NAMES,
        "matrix": TRANSFER_MATRIX,
        "description": "Pairwise transfer scores (source row → target col); diagonal=1.0",
    })


@app.get("/comparison")
async def get_comparison() -> JSONResponse:
    rows = []
    for t in TASKS:
        gain = t["sr"] - t["baseline_sr"]
        rows.append({
            "task": t["name"],
            "multi_task_sr": t["sr"],
            "single_task_sr": t["baseline_sr"],
            "absolute_gain": round(gain, 3),
            "relative_gain_pct": round(gain / t["baseline_sr"] * 100, 1),
        })
    avg_gain_abs = sum(r["absolute_gain"] for r in rows) / len(rows)
    return JSONResponse({"comparison": rows, "avg_absolute_gain": round(avg_gain_abs, 3)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8146)
