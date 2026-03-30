"""OCI Robot Cloud — Policy Benchmarker
Compares multiple GR00T policies head-to-head on standardized benchmark tasks.
Port: 8130
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

import math
from typing import Any

app = FastAPI(title="OCI Robot Cloud Policy Benchmarker", description="Head-to-head policy comparison dashboard for GR00T N1.6-3B", version="1.0.0")

POLICIES: dict[str, dict[str, Any]] = {
    "bc_baseline":         {"label": "bc_baseline",         "avg_sr": 34, "avg_latency_ms": 231, "status": "RETIRED",     "episodes": 20, "color_hex": "#6b7280"},
    "dagger_run9_v2":      {"label": "dagger_run9_v2",      "avg_sr": 71, "avg_latency_ms": 226, "status": "PRODUCTION",   "episodes": 20, "color_hex": "#38bdf8"},
    "groot_finetune_v2":   {"label": "groot_finetune_v2",   "avg_sr": 78, "avg_latency_ms": 223, "status": "STAGING",     "episodes": 20, "color_hex": "#C74634"},
    "dagger_run10_partial":{"label": "dagger_run10_partial","avg_sr": 67, "avg_latency_ms": 229, "status": "IN_PROGRESS",  "episodes": 50, "color_hex": "#f59e0b"},
}

TASKS: dict[str, dict[str, Any]] = {
    "cube_lift":    {"label": "cube_lift",    "results": {"bc_baseline": 38, "dagger_run9_v2": 74, "groot_finetune_v2": 82, "dagger_run10_partial": 70}},
    "cube_place":   {"label": "cube_place",   "results": {"bc_baseline": 31, "dagger_run9_v2": 68, "groot_finetune_v2": 75, "dagger_run10_partial": 64}},
    "push_to_goal": {"label": "push_to_goal", "results": {"bc_baseline": 33, "dagger_run9_v2": 71, "groot_finetune_v2": 77, "dagger_run10_partial": 67}},
}

POLICY_ORDER = ["bc_baseline", "dagger_run9_v2", "groot_finetune_v2", "dagger_run10_partial"]
TASK_ORDER = ["cube_lift", "cube_place", "push_to_goal"]


def _grouped_bar_chart() -> str:
    W, H = 700, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 40, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n_groups = len(TASK_ORDER)
    n_bars = len(POLICY_ORDER)
    group_w = chart_w / n_groups
    bar_w = (group_w * 0.72) / n_bars
    group_gap = group_w * 0.28
    y_scale = chart_h / 100

    lines: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;">']
    for tick in [0, 25, 50, 75, 100]:
        y = PAD_T + chart_h - tick * y_scale
        lines.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick}%</text>')
    for gi, task_key in enumerate(TASK_ORDER):
        group_x = PAD_L + gi * group_w + group_gap / 2
        task = TASKS[task_key]
        for bi, policy_key in enumerate(POLICY_ORDER):
            sr = task["results"][policy_key]
            bh = sr * y_scale
            bx = group_x + bi * bar_w
            by = PAD_T + chart_h - bh
            color = POLICIES[policy_key]["color_hex"]
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w-1:.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>')
            lines.append(f'<text x="{bx+(bar_w-1)/2:.1f}" y="{by-3:.1f}" fill="#e2e8f0" font-size="8" text-anchor="middle">{sr}</text>')
        label_x = group_x + (n_bars * bar_w) / 2
        lines.append(f'<text x="{label_x:.1f}" y="{PAD_T+chart_h+16}" fill="#94a3b8" font-size="11" text-anchor="middle">{task_key.replace("_"," ")}</text>')
    legend_items = [("bc_baseline", "#6b7280", "BC Baseline"), ("dagger_run9_v2", "#38bdf8", "DAgger Run9 v2"), ("groot_finetune_v2", "#C74634", "GR00T Finetune v2"), ("dagger_run10_partial", "#f59e0b", "DAgger Run10 (partial)")]
    lx = PAD_L
    for _key, color, lbl in legend_items:
        lines.append(f'<rect x="{lx}" y="10" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+16}" y="21" fill="#cbd5e1" font-size="10">{lbl}</text>')
        lx += len(lbl) * 6.5 + 24
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{W-PAD_R}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>')
    lines.append("</svg>")
    return "\n".join(lines)


def _radar_chart() -> str:
    W, H = 700, 220
    cx, cy = W / 2, H / 2 + 5
    r_max = 85
    n_axes = 3
    axes_angles = [math.radians(-90 + i * (360 / n_axes)) for i in range(n_axes)]
    axis_labels = ["cube_lift", "cube_place", "push_to_goal"]

    lines: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;">']
    for ring_val in [25, 50, 75, 100]:
        rr = r_max * ring_val / 100
        pts = " ".join(f"{cx+rr*math.cos(a):.1f},{cy+rr*math.sin(a):.1f}" for a in axes_angles)
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')
        lx = cx + (rr + 3) * math.cos(axes_angles[0]) + 4
        ly = cy + (rr + 3) * math.sin(axes_angles[0]) + 4
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#475569" font-size="8">{ring_val}%</text>')
    for angle in axes_angles:
        lines.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx+r_max*math.cos(angle):.1f}" y2="{cy+r_max*math.sin(angle):.1f}" stroke="#334155" stroke-width="1"/>')
    label_offset = 18
    for i, (angle, label) in enumerate(zip(axes_angles, axis_labels)):
        lx = cx + (r_max + label_offset) * math.cos(angle)
        ly = cy + (r_max + label_offset) * math.sin(angle)
        anchor = "middle" if abs(math.cos(angle)) <= 0.3 else ("start" if math.cos(angle) > 0.3 else "end")
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="{anchor}" dominant-baseline="middle">{label.replace("_"," ")}</text>')
    for policy_key in reversed(POLICY_ORDER):
        color = POLICIES[policy_key]["color_hex"]
        pts = " ".join(f"{cx+r_max*TASKS[TASK_ORDER[i]]['results'][policy_key]/100*math.cos(angle):.1f},{cy+r_max*TASKS[TASK_ORDER[i]]['results'][policy_key]/100*math.sin(angle):.1f}" for i, angle in enumerate(axes_angles))
        lines.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2"/>')
        for i, angle in enumerate(axes_angles):
            sr = TASKS[TASK_ORDER[i]]["results"][policy_key]
            rr = r_max * sr / 100
            lines.append(f'<circle cx="{cx+rr*math.cos(angle):.1f}" cy="{cy+rr*math.sin(angle):.1f}" r="3" fill="{color}"/>')
    lx = 12
    for _key, color, lbl in [("bc_baseline", "#6b7280", "BC Baseline"), ("dagger_run9_v2", "#38bdf8", "DAgger Run9 v2"), ("groot_finetune_v2", "#C74634", "GR00T Finetune v2"), ("dagger_run10_partial", "#f59e0b", "DAgger Run10 (partial)")]:
        lines.append(f'<rect x="{lx}" y="8" width="10" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="17" fill="#cbd5e1" font-size="9">{lbl}</text>')
        lx += len(lbl) * 5.8 + 22
    lines.append("</svg>")
    return "\n".join(lines)


def _build_html() -> str:
    bar_svg = _grouped_bar_chart()
    radar_svg = _radar_chart()
    status_badge = {
        "PRODUCTION": ("background:#166534;color:#86efac", "PRODUCTION"),
        "STAGING": ("background:#1e3a5f;color:#38bdf8", "STAGING"),
        "IN_PROGRESS": ("background:#78350f;color:#fcd34d", "IN PROGRESS"),
        "RETIRED": ("background:#1c1917;color:#78716c", "RETIRED"),
    }
    cards_html = ""
    for pk in POLICY_ORDER:
        p = POLICIES[pk]
        style, badge_txt = status_badge.get(p["status"], ("background:#1e293b;color:#94a3b8", p["status"]))
        border = f'border: 2px solid {p["color_hex"]};' if p["status"] in ("PRODUCTION", "STAGING") else "border: 1px solid #334155;"
        cards_html += f'<div style="background:#1e293b;{border}border-radius:10px;padding:18px 22px;min-width:160px;flex:1;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><span style="color:#e2e8f0;font-weight:700;font-size:13px;">{pk}</span><span style="padding:2px 8px;border-radius:9999px;font-size:10px;font-weight:600;{style}">{badge_txt}</span></div><div style="color:{p["color_hex"]};font-size:2rem;font-weight:800;">{p["avg_sr"]}%</div><div style="color:#64748b;font-size:11px;margin-top:2px;">avg success rate</div><div style="color:#94a3b8;font-size:12px;margin-top:8px;">{p["avg_latency_ms"]} ms &nbsp;|&nbsp; {p["episodes"]} eps</div></div>'
    table_rows = ""
    for task_key in TASK_ORDER:
        task = TASKS[task_key]
        best_policy = max(task["results"], key=lambda k: task["results"][k])
        cols = "".join(f'<td style="text-align:center;{"font-weight:700;" if pk==best_policy else ""}color:{POLICIES[pk]["color_hex"]};">{task["results"][pk]}%</td>' for pk in POLICY_ORDER)
        table_rows += f'<tr style="border-bottom:1px solid #1e293b;"><td style="padding:10px 14px;color:#e2e8f0;font-weight:500;">{task_key.replace("_"," ")}</td>{cols}</tr>'
    policy_headers = "".join(f'<th style="text-align:center;padding:10px 12px;color:{POLICIES[pk]["color_hex"]};">{pk}</th>' for pk in POLICY_ORDER)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — Policy Benchmarker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .content {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
    .winner-callout {{ background: linear-gradient(135deg,#1a1033 0%,#1e1a2e 100%); border: 1px solid #C74634; border-radius: 10px; padding: 16px 22px; margin-bottom: 28px; display: flex; align-items: center; gap: 14px; }}
    .winner-badge {{ background: #C74634; color: #fff; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700; }}
    .section-title {{ font-size: 1rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 14px; }}
    .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 30px; }}
    .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
    .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; border: 1px solid #334155; }}
    th {{ background: #0f172a; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 10px 14px; text-align: left; }}
    td {{ padding: 10px 14px; color: #94a3b8; font-size: 13px; }}
    tr:hover {{ background: #243046; }}
    .footer {{ text-align: center; color: #334155; font-size: 11px; margin-top: 40px; padding: 16px; border-top: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="header">
    <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;"><svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="none" stroke="white" stroke-width="2"/><line x1="10" y1="2" x2="10" y2="18" stroke="white" stroke-width="2"/><line x1="2" y1="10" x2="18" y2="10" stroke="white" stroke-width="2"/></svg></div>
    <div><div style="font-size:1.3rem;font-weight:700;color:#f1f5f9;">Policy Benchmarker</div><div style="font-size:0.8rem;color:#64748b;margin-top:2px;">OCI Robot Cloud &mdash; GR00T N1.6-3B head-to-head evaluation</div></div>
    <div style="margin-left:auto;color:#334155;font-size:12px;">Port 8130</div>
  </div>
  <div class="content">
    <div class="winner-callout">
      <span class="winner-badge">WINNER</span>
      <div><span style="color:#C74634;font-weight:700;font-size:14px;">groot_finetune_v2</span><span style="color:#94a3b8;font-size:13px;margin-left:10px;">leads on all 3 benchmark tasks &mdash; cube_lift 82%, cube_place 75%, push_to_goal 77%</span></div>
      <div style="margin-left:auto;background:#1e3a5f;color:#38bdf8;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">STAGING &rarr; PROD CANDIDATE</div>
    </div>
    <div class="section-title">Policy Overview</div>
    <div class="cards">{cards_html}</div>
    <div class="section-title">Benchmark Results</div>
    <div class="chart-grid">
      <div class="chart-card">{bar_svg}</div>
      <div class="chart-card">{radar_svg}</div>
    </div>
    <div class="section-title" style="margin-top:10px;">Per-Task Results</div>
    <table><thead><tr><th>Task</th>{policy_headers}</tr></thead><tbody>{table_rows}</tbody></table>
  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud Policy Benchmarker | Port 8130</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_build_html())


@app.get("/policies")
async def get_policies():
    return JSONResponse(content=POLICIES)


@app.get("/tasks")
async def get_tasks():
    return JSONResponse(content=TASKS)


@app.get("/matrix")
async def get_matrix():
    matrix: dict[str, dict[str, int]] = {}
    for pk in POLICY_ORDER:
        matrix[pk] = {tk: TASKS[tk]["results"][pk] for tk in TASK_ORDER}
    return JSONResponse(content={"policies": POLICY_ORDER, "tasks": TASK_ORDER, "matrix": matrix})


@app.get("/health")
async def health():
    return JSONResponse(content={"status": "healthy", "service": "policy_benchmarker", "port": 8130, "policies_tracked": len(POLICIES), "tasks_tracked": len(TASKS), "production_policy": "dagger_run9_v2", "staging_policy": "groot_finetune_v2"})


def main():
    uvicorn.run(app, host="0.0.0.0", port=8130, log_level="info")


if __name__ == "__main__":
    main()
