"""Multi-Task Curriculum v2 — port 8259

Advanced multi-task curriculum with task graph dependencies for GR00T training.
Oracle OCI Robot Cloud — cycle-49B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Task graph
# ---------------------------------------------------------------------------

TASKS = [
    {"id": "reach",      "label": "Reach",      "mastery": 0.91, "unlocked": True,  "episode_unlocked": 0},
    {"id": "grasp",      "label": "Grasp",      "mastery": 0.79, "unlocked": True,  "episode_unlocked": 50},
    {"id": "pick_place", "label": "Pick/Place", "mastery": 0.73, "unlocked": True,  "episode_unlocked": 180},
    {"id": "wipe",       "label": "Wipe",       "mastery": 0.68, "unlocked": True,  "episode_unlocked": 100},
    {"id": "stack",      "label": "Stack",      "mastery": 0.44, "unlocked": True,  "episode_unlocked": 280},
    {"id": "pour",       "label": "Pour",       "mastery": 0.31, "unlocked": True,  "episode_unlocked": 230},
    {"id": "handover",   "label": "Handover",   "mastery": 0.18, "unlocked": False, "episode_unlocked": None},
    {"id": "assembly",   "label": "Assembly",   "mastery": 0.05, "unlocked": False, "episode_unlocked": None},
]

# prerequisite edges: (from_task_id, to_task_id)
EDGES = [
    ("reach",      "grasp"),
    ("reach",      "wipe"),
    ("grasp",      "pick_place"),
    ("grasp",      "pour"),
    ("pick_place", "stack"),
    ("pour",       "handover"),
    ("pick_place", "assembly"),
    ("stack",      "assembly"),
]

# Layout positions for DAG (x, y) in a 0-100 space
POSITIONS = {
    "reach":      (10, 50),
    "grasp":      (30, 50),
    "wipe":       (30, 80),
    "pick_place": (52, 35),
    "pour":       (52, 65),
    "stack":      (72, 20),
    "handover":   (72, 65),
    "assembly":   (90, 35),
}

MASTERY_THRESHOLD = 0.70

# Success rate per task over training episodes (100-episode intervals)
# Episodes: 0, 100, 200, 300, 400, 500
EPISODE_INTERVALS = [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]

# SR curves: each list index = episode bucket
SR_CURVES = {
    "reach":      [0.05, 0.45, 0.72, 0.85, 0.89, 0.91, 0.91, 0.91, 0.91, 0.91, 0.91],
    "grasp":      [0.00, 0.00, 0.08, 0.35, 0.60, 0.72, 0.79, 0.79, 0.79, 0.79, 0.79],
    "pick_place": [0.00, 0.00, 0.00, 0.00, 0.12, 0.30, 0.52, 0.65, 0.73, 0.73, 0.73],
    "wipe":       [0.00, 0.00, 0.10, 0.28, 0.48, 0.60, 0.68, 0.68, 0.68, 0.68, 0.68],
    "stack":      [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.10, 0.28, 0.44, 0.44, 0.44],
    "pour":       [0.00, 0.00, 0.00, 0.00, 0.05, 0.15, 0.31, 0.31, 0.31, 0.31, 0.31],
    "handover":   [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05, 0.18, 0.18, 0.18],
    "assembly":   [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.02, 0.05, 0.05],
}

# Composite multi-task SR (weighted average of active tasks)
COMPOSITE_SR = [0.01, 0.08, 0.18, 0.29, 0.40, 0.50, 0.57, 0.62, 0.67, 0.68, 0.71]

# Curriculum efficiency vs random sampling (baseline)
RANDOM_SR = [0.01, 0.04, 0.08, 0.12, 0.17, 0.22, 0.28, 0.33, 0.38, 0.42, 0.45]

METRICS = {
    "current_episode":          500,
    "composite_sr":             0.71,
    "tasks_unlocked":           6,
    "tasks_total":              8,
    "tasks_mastered":           2,   # reach + grasp
    "mastery_threshold":        MASTERY_THRESHOLD,
    "curriculum_efficiency_gain": round((0.71 - 0.45) / 0.45 * 100, 1),  # ~58%
    "next_unlock_task":         "handover",
    "next_unlock_threshold":    "pour SR ≥ 0.70",
}

# ---------------------------------------------------------------------------
# Mastery color helper (0→#C74634 red, 0.5→#fbbf24 yellow, 1→#34d399 green)
# ---------------------------------------------------------------------------

def mastery_color(m: float) -> str:
    if m >= MASTERY_THRESHOLD:
        return "#34d399"   # green — mastered
    if m >= 0.40:
        return "#fbbf24"   # yellow — in progress
    return "#C74634"       # red — not yet


# ---------------------------------------------------------------------------
# SVG 1: Task Dependency DAG
# ---------------------------------------------------------------------------

def make_dag_svg() -> str:
    W, H = 700, 260
    # Scale positions
    PAD = 30
    cw = W - 2 * PAD
    ch = H - 2 * PAD

    task_map = {t["id"]: t for t in TASKS}

    def cx(tid): return PAD + POSITIONS[tid][0] / 100 * cw
    def cy(tid): return PAD + POSITIONS[tid][1] / 100 * ch

    # Draw edges first (under nodes)
    edges_svg = ""
    for src, dst in EDGES:
        x1, y1 = cx(src), cy(src)
        x2, y2 = cx(dst), cy(dst)
        # simple straight line with arrowhead approximation
        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx * dx + dy * dy) or 1
        ux, uy = dx / dist, dy / dist
        # shorten to node radius (18)
        r = 18
        sx1, sy1 = x1 + ux * r, y1 + uy * r
        sx2, sy2 = x2 - ux * r, y2 - uy * r
        # arrowhead
        aw = 6
        ax1 = sx2 - ux * aw - uy * aw * 0.5
        ay1 = sy2 - uy * aw + ux * aw * 0.5
        ax2 = sx2 - ux * aw + uy * aw * 0.5
        ay2 = sy2 - uy * aw - ux * aw * 0.5
        # edge color based on src mastery
        ec = mastery_color(task_map[src]["mastery"])
        edges_svg += (f'<line x1="{sx1:.1f}" y1="{sy1:.1f}" x2="{sx2:.1f}" y2="{sy2:.1f}" '
                      f'stroke="{ec}" stroke-width="1.5" stroke-opacity="0.5"/>\n'
                      f'<polygon points="{sx2:.1f},{sy2:.1f} {ax1:.1f},{ay1:.1f} {ax2:.1f},{ay2:.1f}" '
                      f'fill="{ec}" fill-opacity="0.5"/>\n')

    # Draw nodes
    nodes_svg = ""
    for t in TASKS:
        tid = t["id"]
        x, y = cx(tid), cy(tid)
        m = t["mastery"]
        fill = mastery_color(m)
        lock_icon = "" if t["unlocked"] else " 🔒"
        nodes_svg += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="18" fill="{fill}" fill-opacity="0.25" '
            f'stroke="{fill}" stroke-width="2"/>\n'
            f'<text x="{x:.1f}" y="{y - 3:.1f}" fill="{fill}" font-size="9" font-weight="bold" '
            f'text-anchor="middle">{t["label"]}</text>\n'
            f'<text x="{x:.1f}" y="{y + 9:.1f}" fill="{fill}" font-size="9" text-anchor="middle">{m:.2f}</text>\n'
        )

    # Legend
    legend_items = [
        ("#34d399", f"Mastered (≥{MASTERY_THRESHOLD})"),
        ("#fbbf24", "In progress"),
        ("#C74634", "Not yet"),
    ]
    legend_svg = ""
    for i, (c, lbl) in enumerate(legend_items):
        lx = PAD + i * 160
        ly = H - 8
        legend_svg += (f'<circle cx="{lx + 5}" cy="{ly - 4}" r="4" fill="{c}" fill-opacity="0.7"/>\n'
                       f'<text x="{lx + 13}" y="{ly}" fill="#94a3b8" font-size="9">{lbl}</text>\n')

    title = (f'<text x="{W//2}" y="16" fill="#e2e8f0" font-size="11" '
             f'font-weight="bold" text-anchor="middle">Task Dependency DAG — Mastery Heatmap</text>\n')

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">\n'
            f'{title}{edges_svg}{nodes_svg}{legend_svg}'
            f'</svg>')


# ---------------------------------------------------------------------------
# SVG 2: Curriculum Progress Chart
# ---------------------------------------------------------------------------

def make_progress_svg() -> str:
    W, H = 700, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 30, 55
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    n = len(EPISODE_INTERVALS)
    max_ep = EPISODE_INTERVALS[-1]

    def px(ep):  return PAD_L + (ep / max_ep) * chart_w
    def py(sr):  return PAD_T + chart_h - sr * chart_h

    # Grid lines
    grid = ""
    for sr in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = py(sr)
        grid += (f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + chart_w}" y2="{y:.1f}" '
                 f'stroke="#1e293b" stroke-width="0.8"/>\n'
                 f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{int(sr*100)}%</text>\n')

    # Mastery threshold line
    thr_y = py(MASTERY_THRESHOLD)
    threshold_line = (f'<line x1="{PAD_L}" y1="{thr_y:.1f}" x2="{PAD_L + chart_w}" y2="{thr_y:.1f}" '
                      f'stroke="#34d399" stroke-width="1" stroke-dasharray="5,3" opacity="0.5"/>\n'
                      f'<text x="{PAD_L + chart_w - 2}" y="{thr_y - 3:.1f}" fill="#34d399" '
                      f'font-size="8" text-anchor="end">Mastery {int(MASTERY_THRESHOLD*100)}%</text>\n')

    # Random baseline (dashed gray)
    rand_pts = " ".join(f"{px(EPISODE_INTERVALS[i]):.1f},{py(RANDOM_SR[i]):.1f}" for i in range(n))
    random_line = (f'<polyline points="{rand_pts}" fill="none" stroke="#475569" '
                   f'stroke-width="1.5" stroke-dasharray="4,3"/>\n'
                   f'<text x="{px(200):.1f}" y="{py(RANDOM_SR[4]) - 5:.1f}" fill="#475569" font-size="8">Random baseline</text>\n')

    # Per-task SR lines
    task_colors = {t["id"]: mastery_color(t["mastery"]) for t in TASKS}
    task_lines = ""
    for t in TASKS:
        tid = t["id"]
        pts = " ".join(f"{px(EPISODE_INTERVALS[i]):.1f},{py(SR_CURVES[tid][i]):.1f}" for i in range(n))
        task_lines += (f'<polyline points="{pts}" fill="none" stroke="{task_colors[tid]}" '
                       f'stroke-width="1.2" opacity="0.6"/>\n')
        # label at last point
        last_sr = SR_CURVES[tid][-1]
        lx = px(EPISODE_INTERVALS[-1]) + 2
        ly = py(last_sr)
        # skip label if 0
        if last_sr > 0.02:
            task_lines += (f'<text x="{lx:.1f}" y="{ly + 4:.1f}" fill="{task_colors[tid]}" '
                           f'font-size="8">{t["label"]}</text>\n')

    # Composite SR (thick white line)
    comp_pts = " ".join(f"{px(EPISODE_INTERVALS[i]):.1f},{py(COMPOSITE_SR[i]):.1f}" for i in range(n))
    composite_line = (f'<polyline points="{comp_pts}" fill="none" stroke="#e2e8f0" '
                      f'stroke-width="2.5"/>\n'
                      f'<text x="{px(250):.1f}" y="{py(COMPOSITE_SR[5]) - 6:.1f}" fill="#e2e8f0" '
                      f'font-size="9" font-weight="bold">Composite SR</text>\n')

    # X axis
    x_labels = "".join(
        f'<text x="{px(ep):.1f}" y="{PAD_T + chart_h + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">{ep}</text>\n'
        for ep in EPISODE_INTERVALS[::2]
    )
    x_title = (f'<text x="{PAD_L + chart_w/2:.1f}" y="{H - 8}" fill="#94a3b8" '
               f'font-size="10" text-anchor="middle">Training Episodes</text>\n')
    y_title = (f'<text x="12" y="{PAD_T + chart_h/2:.1f}" fill="#94a3b8" font-size="10" '
               f'text-anchor="middle" transform="rotate(-90,12,{PAD_T + chart_h/2:.1f})">Success Rate</text>\n')

    # Unlock annotations
    unlock_annots = ""
    unlock_episodes = [
        (50,  "reach\nmastered"),
        (180, "grasp\nmastered"),
    ]
    for ep, lbl in unlock_episodes:
        ux = px(ep)
        unlock_annots += (f'<line x1="{ux:.1f}" y1="{PAD_T}" x2="{ux:.1f}" y2="{PAD_T + chart_h}" '
                          f'stroke="#38bdf8" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>\n'
                          f'<text x="{ux + 2:.1f}" y="{PAD_T + 20}" fill="#38bdf8" font-size="7">{lbl.split(chr(10))[0]}</text>\n'
                          f'<text x="{ux + 2:.1f}" y="{PAD_T + 29}" fill="#38bdf8" font-size="7">{lbl.split(chr(10))[1]}</text>\n')

    title = (f'<text x="{W//2}" y="16" fill="#e2e8f0" font-size="11" '
             f'font-weight="bold" text-anchor="middle">Curriculum Progress — SR per Task vs Episodes</text>\n')

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">\n'
            f'{title}{grid}{threshold_line}{random_line}{task_lines}{composite_line}{unlock_annots}{x_labels}{x_title}{y_title}'
            f'</svg>')


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    dag_svg      = make_dag_svg()
    progress_svg = make_progress_svg()
    m = METRICS
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    metric_cards = [
        ("Current Episode",        str(m["current_episode"]),        "#38bdf8"),
        ("Composite SR",           f"{m['composite_sr']:.0%}",       "#34d399"),
        ("Tasks Unlocked",         f"{m['tasks_unlocked']}/{m['tasks_total']}", "#a78bfa"),
        ("Tasks Mastered",         str(m["tasks_mastered"]),         "#34d399"),
        ("Mastery Threshold",      f"{m['mastery_threshold']:.0%}",  "#fbbf24"),
        ("Curriculum Gain vs Rand",f"+{m['curriculum_efficiency_gain']}%", "#C74634"),
        ("Next Unlock",            m["next_unlock_task"].title(),    "#38bdf8"),
    ]

    cards_html = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:14px 18px;border-left:3px solid {c};">'
        f'<div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">{label}</div>'
        f'<div style="color:{c};font-size:22px;font-weight:700;">{val}</div></div>\n'
        for label, val, c in metric_cards
    )

    # Task table
    rows = ""
    for t in TASKS:
        color = mastery_color(t["mastery"])
        lock = "Locked" if not t["unlocked"] else ("Mastered" if t["mastery"] >= MASTERY_THRESHOLD else "Training")
        ep_u = t["episode_unlocked"] if t["episode_unlocked"] is not None else "—"
        rows += (f'<tr><td style="color:{color};font-weight:bold">{t["label"]}</td>'
                 f'<td style="color:{color}">{t["mastery"]:.2f}</td>'
                 f'<td style="color:{color}">{lock}</td>'
                 f'<td>{ep_u}</td>'
                 f'<td style="color:#64748b">{SR_CURVES[t["id"]][-1]:.2f}</td></tr>\n')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Multi-Task Curriculum v2 — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 20px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill,minmax(160px,1fr)); gap: 12px; margin-bottom: 28px; }}
    .chart-wrap {{ margin-bottom: 28px; }}
    .chart-title {{ color: #94a3b8; font-size: 12px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: .05em; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; background: #1e293b; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
    th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
    td {{ padding: 7px 12px; border-bottom: 1px solid #0f172a; }}
    tr:last-child td {{ border-bottom: none; }}
    footer {{ color: #334155; font-size: 11px; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Multi-Task Curriculum v2</h1>
  <div class="sub">OCI Robot Cloud · GR00T Task Graph &amp; Dependency Scheduling · Generated {ts}</div>

  <div class="grid">
    {cards_html}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Task Dependency DAG — Node Color = Mastery Level</div>
    {dag_svg}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Curriculum Progress — Success Rate per Task over Training</div>
    {progress_svg}
  </div>

  <table>
    <thead><tr><th>Task</th><th>Mastery</th><th>Status</th><th>Unlocked At Ep</th><th>Current SR</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <footer>OCI Robot Cloud · Multi-Task Curriculum v2 · Port 8259 · Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Multi-Task Curriculum v2",
        description="Advanced multi-task curriculum with task graph dependencies for GR00T training.",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/metrics")
    def metrics():
        return METRICS

    @app.get("/tasks")
    def tasks():
        return TASKS

    @app.get("/edges")
    def edges():
        return [{"from": s, "to": d} for s, d in EDGES]

    @app.get("/progress")
    def progress():
        return {"episodes": EPISODE_INTERVALS, "sr_curves": SR_CURVES, "composite": COMPOSITE_SR, "random_baseline": RANDOM_SR}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "multi_task_curriculum_v2", "port": 8259}

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        def log_message(self, *_): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8259)
    else:
        print("FastAPI not available — serving via stdlib HTTP on port 8259")
        HTTPServer(("0.0.0.0", 8259), Handler).serve_forever()
