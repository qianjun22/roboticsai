"""Zero-shot and few-shot task transfer evaluation — port 8157."""

import json
import math
from typing import List, Dict, Any, Optional

try:
    from fastapi import FastAPI, Query, Response
    from fastapi.responses import HTMLResponse
    import uvicorn
except ImportError:
    FastAPI = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

SOURCE_TASK = "cube_lift"
SOURCE_SR = 0.78

TASKS: List[Dict[str, Any]] = [
    {
        "name": "cube_place",
        "zero_shot_sr": 0.71,
        "few_shot_5ep_sr": 0.79,
        "few_shot_20ep_sr": 0.84,
        "transfer_gap": -0.07,
        "difficulty": "medium",
    },
    {
        "name": "push_to_goal",
        "zero_shot_sr": 0.69,
        "few_shot_5ep_sr": 0.76,
        "few_shot_20ep_sr": 0.81,
        "transfer_gap": -0.09,
        "difficulty": "easy",
    },
    {
        "name": "drawer_open",
        "zero_shot_sr": 0.31,
        "few_shot_5ep_sr": 0.47,
        "few_shot_20ep_sr": 0.61,
        "transfer_gap": -0.47,
        "difficulty": "hard",
    },
    {
        "name": "bottle_pickup",
        "zero_shot_sr": 0.58,
        "few_shot_5ep_sr": 0.69,
        "few_shot_20ep_sr": 0.77,
        "transfer_gap": -0.20,
        "difficulty": "medium",
    },
    {
        "name": "peg_insertion",
        "zero_shot_sr": 0.21,
        "few_shot_5ep_sr": 0.36,
        "few_shot_20ep_sr": 0.52,
        "transfer_gap": -0.57,
        "difficulty": "very_hard",
    },
]

INSIGHT = (
    "cube_place and push_to_goal transfer well (>0.69 zero-shot). "
    "drawer_open and peg_insertion need dedicated fine-tuning."
)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------


def _transfer_efficiency_svg() -> str:
    """Grouped bar chart: zero_shot / 5ep / 20ep per task, sorted by zero_shot SR desc."""
    w, h = 680, 220
    pad_x, pad_y = 60, 20
    plot_w = w - pad_x - 20
    plot_h = h - pad_y - 50
    y_max = 1.0

    sorted_tasks = sorted(TASKS, key=lambda t: t["zero_shot_sr"], reverse=True)
    n = len(sorted_tasks)
    group_w = plot_w / n
    bar_w = group_w * 0.22
    colors = ["#38bdf8", "#f59e0b", "#34d399"]
    labels = ["zero-shot", "5-ep", "20-ep"]
    keys = ["zero_shot_sr", "few_shot_5ep_sr", "few_shot_20ep_sr"]

    lines = []
    # axes
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y}" x2="{pad_x}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y + plot_h}" x2="{pad_x + plot_w}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )

    # y gridlines and labels
    for val in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pad_y + plot_h - val * plot_h
        lines.append(f'<line x1="{pad_x}" y1="{y}" x2="{pad_x + plot_w}" y2="{y}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_x - 4}" y="{y + 4}" fill="#94a3b8" font-size="10" text-anchor="end">{val:.1f}</text>')

    # source SR dashed line
    y_src = pad_y + plot_h - SOURCE_SR * plot_h
    lines.append(
        f'<line x1="{pad_x}" y1="{y_src}" x2="{pad_x + plot_w}" y2="{y_src}" stroke="#C74634" stroke-dasharray="6,3" stroke-width="1.5"/>'
    )
    lines.append(
        f'<text x="{pad_x + plot_w - 2}" y="{y_src - 3}" fill="#C74634" font-size="9" text-anchor="end">source SR {SOURCE_SR}</text>'
    )

    # bars
    for gi, task in enumerate(sorted_tasks):
        gx = pad_x + gi * group_w + group_w * 0.08
        for bi, (key, color) in enumerate(zip(keys, colors)):
            bx = gx + bi * (bar_w + 2)
            bh = task[key] * plot_h
            by = pad_y + plot_h - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.85" rx="2"/>')
        # task label
        lx = gx + 1.5 * (bar_w + 1)
        lines.append(f'<text x="{lx:.1f}" y="{pad_y + plot_h + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">{task["name"]}</text>')

    # legend
    for i, (label, color) in enumerate(zip(labels, colors)):
        lx = pad_x + 10 + i * 100
        lines.append(f'<rect x="{lx}" y="{h - 16}" width="12" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{h - 7}" fill="#cbd5e1" font-size="10">{label}</text>')

    body = "\n".join(lines)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">'
        f'{body}</svg>'
    )


def _transfer_gap_heatmap_svg() -> str:
    """5-cell heatmap: gap magnitude drives color green→red."""
    w, h = 680, 100
    n = len(TASKS)
    cell_w = w / n
    sorted_tasks = sorted(TASKS, key=lambda t: t["zero_shot_sr"], reverse=True)

    diff_colors = {"easy": "#34d399", "medium": "#f59e0b", "hard": "#ef4444", "very_hard": "#7f1d1d"}

    lines = []
    for i, task in enumerate(sorted_tasks):
        cx = i * cell_w
        gap = task["transfer_gap"]  # negative
        intensity = min(1.0, abs(gap) / 0.6)  # 0=green, 1=red
        # interpolate green(52,211,153)→red(239,68,68)
        r = int(52 + intensity * (239 - 52))
        g = int(211 + intensity * (68 - 211))
        b = int(153 + intensity * (68 - 153))
        cell_color = f"rgb({r},{g},{b})"
        lines.append(f'<rect x="{cx:.1f}" y="0" width="{cell_w:.1f}" height="70" fill="{cell_color}" opacity="0.25"/>')
        lines.append(f'<rect x="{cx:.1f}" y="0" width="{cell_w:.1f}" height="70" fill="none" stroke="#0f172a" stroke-width="2"/>')
        # gap value
        lines.append(f'<text x="{cx + cell_w/2:.1f}" y="30" fill="#e2e8f0" font-size="16" font-weight="700" text-anchor="middle">{task["transfer_gap"]:+.2f}</text>')
        # task name
        lines.append(f'<text x="{cx + cell_w/2:.1f}" y="48" fill="#94a3b8" font-size="10" text-anchor="middle">{task["name"]}</text>')
        # difficulty badge
        dc = diff_colors.get(task["difficulty"], "#94a3b8")
        lines.append(f'<text x="{cx + cell_w/2:.1f}" y="64" fill="{dc}" font-size="9" text-anchor="middle">{task["difficulty"]}</text>')
    # axis label
    lines.append(f'<text x="{w/2}" y="88" fill="#64748b" font-size="10" text-anchor="middle">Transfer Gap (relative to source SR {SOURCE_SR})</text>')

    body = "\n".join(lines)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">'
        f'{body}</svg>'
    )


def _learning_curve_svg() -> str:
    """Line chart: SR vs episodes (0, 5, 20) per task."""
    w, h = 680, 200
    pad_x, pad_y = 55, 20
    plot_w = w - pad_x - 20
    plot_h = h - pad_y - 40
    x_vals = [0, 5, 20]
    x_max = 20
    y_max = 1.0
    colors = ["#38bdf8", "#34d399", "#f59e0b", "#a78bfa", "#C74634"]

    lines = []
    # axes
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y}" x2="{pad_x}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y + plot_h}" x2="{pad_x + plot_w}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )

    # x axis labels
    for xv in x_vals:
        xp = pad_x + (xv / x_max) * plot_w
        lines.append(f'<text x="{xp}" y="{pad_y + plot_h + 14}" fill="#94a3b8" font-size="10" text-anchor="middle">{xv}</text>')
    lines.append(f'<text x="{pad_x + plot_w/2}" y="{h - 4}" fill="#64748b" font-size="10" text-anchor="middle">fine-tuning episodes</text>')

    # y gridlines
    for val in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pad_y + plot_h - val * plot_h
        lines.append(f'<line x1="{pad_x}" y1="{y}" x2="{pad_x + plot_w}" y2="{y}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_x - 4}" y="{y + 4}" fill="#94a3b8" font-size="10" text-anchor="end">{val:.1f}</text>')

    # source SR line
    y_src = pad_y + plot_h - SOURCE_SR * plot_h
    lines.append(
        f'<line x1="{pad_x}" y1="{y_src}" x2="{pad_x + plot_w}" y2="{y_src}" stroke="#C74634" stroke-dasharray="5,3" stroke-width="1" opacity="0.6"/>'
    )

    sr_keys = ["zero_shot_sr", "few_shot_5ep_sr", "few_shot_20ep_sr"]
    for ti, (task, color) in enumerate(zip(TASKS, colors)):
        pts = []
        for xv, key in zip(x_vals, sr_keys):
            xp = pad_x + (xv / x_max) * plot_w
            yp = pad_y + plot_h - task[key] * plot_h
            pts.append(f"{xp:.1f},{yp:.1f}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>')
        # dot at each point
        for xv, key in zip(x_vals, sr_keys):
            xp = pad_x + (xv / x_max) * plot_w
            yp = pad_y + plot_h - task[key] * plot_h
            lines.append(f'<circle cx="{xp:.1f}" cy="{yp:.1f}" r="3" fill="{color}"/>')

    # legend
    for i, (task, color) in enumerate(zip(TASKS, colors)):
        lx = pad_x + 10 + i * 120
        lines.append(f'<circle cx="{lx + 4}" cy="{h - 10}" r="4" fill="{color}"/>')
        lines.append(f'<text x="{lx + 12}" y="{h - 6}" fill="#cbd5e1" font-size="9">{task["name"]}</text>')

    body = "\n".join(lines)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------


def _build_html() -> str:
    avg_zero = sum(t["zero_shot_sr"] for t in TASKS) / len(TASKS)
    avg_20ep = sum(t["few_shot_20ep_sr"] for t in TASKS) / len(TASKS)
    best = max(TASKS, key=lambda t: t["zero_shot_sr"])
    worst = min(TASKS, key=lambda t: t["zero_shot_sr"])

    stat_cards = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;">
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">SOURCE TASK SR</div>
        <div style="color:#C74634;font-size:24px;font-weight:700;">{SOURCE_SR:.2f}</div>
        <div style="color:#64748b;font-size:11px;">{SOURCE_TASK}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">AVG ZERO-SHOT SR</div>
        <div style="color:#38bdf8;font-size:24px;font-weight:700;">{avg_zero:.2f}</div>
        <div style="color:#64748b;font-size:11px;">across {len(TASKS)} tasks</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">BEST TRANSFER</div>
        <div style="color:#34d399;font-size:24px;font-weight:700;">{best['zero_shot_sr']:.2f}</div>
        <div style="color:#64748b;font-size:11px;">{best['name']}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">HARDEST TRANSFER</div>
        <div style="color:#f59e0b;font-size:24px;font-weight:700;">{worst['zero_shot_sr']:.2f}</div>
        <div style="color:#64748b;font-size:11px;">{worst['name']}</div>
      </div>
    </div>
    """

    task_rows = "".join(
        f"""<tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:8px 12px;color:#e2e8f0;font-weight:500;">{t['name']}</td>
          <td style="padding:8px 12px;color:#38bdf8;">{t['zero_shot_sr']:.2f}</td>
          <td style="padding:8px 12px;color:#f59e0b;">{t['few_shot_5ep_sr']:.2f}</td>
          <td style="padding:8px 12px;color:#34d399;">{t['few_shot_20ep_sr']:.2f}</td>
          <td style="padding:8px 12px;color:{'#34d399' if abs(t['transfer_gap']) < 0.15 else '#f59e0b' if abs(t['transfer_gap']) < 0.40 else '#ef4444'};">{t['transfer_gap']:+.2f}</td>
          <td style="padding:8px 12px;color:#94a3b8;">{t['difficulty']}</td>
        </tr>"""
        for t in TASKS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Task Transfer Eval — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 14px; margin: 20px 0 10px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; margin-bottom: 16px; }}
    .insight {{ background: #0f2744; border-left: 3px solid #38bdf8; padding: 12px 16px; border-radius: 6px; color: #94a3b8; font-size: 13px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #0f172a; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 8px 12px; text-align: left; }}
    a {{ color: #38bdf8; text-decoration: none; font-size: 12px; }}
    a:hover {{ text-decoration: underline; }}
    .api-links {{ display: flex; gap: 12px; margin-bottom: 20px; }}
  </style>
</head>
<body>
  <h1>Task Transfer Evaluation</h1>
  <p class="subtitle">Source: {SOURCE_TASK} (SR={SOURCE_SR}) &mdash; Zero-shot &amp; Few-shot &mdash; Port 8157</p>

  <div class="api-links">
    <a href="/tasks">/tasks</a>
    <a href="/summary">/summary</a>
    <a href="/compare?a=cube_place&b=drawer_open">/compare</a>
  </div>

  <div class="insight">{INSIGHT}</div>

  {stat_cards}

  <div class="card">
    <h2>Transfer Efficiency — Zero-shot / 5-ep / 20-ep</h2>
    {_transfer_efficiency_svg()}
  </div>

  <div class="card">
    <h2>Transfer Gap Heatmap</h2>
    {_transfer_gap_heatmap_svg()}
  </div>

  <div class="card">
    <h2>Few-shot Learning Curves</h2>
    {_learning_curve_svg()}
  </div>

  <div class="card">
    <h2>Full Results Table</h2>
    <table>
      <thead>
        <tr>
          <th>Task</th><th>Zero-shot SR</th><th>5-ep SR</th><th>20-ep SR</th><th>Transfer Gap</th><th>Difficulty</th>
        </tr>
      </thead>
      <tbody>{task_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Task Transfer Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/tasks")
    def get_tasks():
        return {"source_task": SOURCE_TASK, "source_sr": SOURCE_SR, "tasks": TASKS}

    @app.get("/summary")
    def get_summary():
        avg_zero = sum(t["zero_shot_sr"] for t in TASKS) / len(TASKS)
        avg_5ep = sum(t["few_shot_5ep_sr"] for t in TASKS) / len(TASKS)
        avg_20ep = sum(t["few_shot_20ep_sr"] for t in TASKS) / len(TASKS)
        return {
            "source_task": SOURCE_TASK,
            "source_sr": SOURCE_SR,
            "avg_zero_shot_sr": round(avg_zero, 4),
            "avg_5ep_sr": round(avg_5ep, 4),
            "avg_20ep_sr": round(avg_20ep, 4),
            "insight": INSIGHT,
        }

    @app.get("/compare")
    def compare_tasks(
        a: str = Query(..., description="First task name"),
        b: str = Query(..., description="Second task name"),
    ):
        task_map = {t["name"]: t for t in TASKS}
        missing = [n for n in [a, b] if n not in task_map]
        if missing:
            return {"error": f"Unknown tasks: {missing}", "available": list(task_map.keys())}
        ta, tb = task_map[a], task_map[b]
        return {
            "source_task": SOURCE_TASK,
            "source_sr": SOURCE_SR,
            "task_a": ta,
            "task_b": tb,
            "zero_shot_delta": round(ta["zero_shot_sr"] - tb["zero_shot_sr"], 4),
            "20ep_delta": round(ta["few_shot_20ep_sr"] - tb["few_shot_20ep_sr"], 4),
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("task_transfer_eval:app", host="0.0.0.0", port=8157, reload=False)
