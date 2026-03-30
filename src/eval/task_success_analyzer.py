"""Task Success Analyzer — port 8241
Analyzes root causes of task success and failure in robot manipulation.
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

random.seed(7)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TOTAL_EPISODES = 200
SUCCESS_RATE = 0.71
SUCCESS_COUNT = int(TOTAL_EPISODES * SUCCESS_RATE)   # 142
FAILURE_COUNT = TOTAL_EPISODES - SUCCESS_COUNT        # 58

# Failure breakdown (must sum to FAILURE_COUNT=58)
FAILURE_MODES = {
    "early_drop":       int(TOTAL_EPISODES * 0.12),   # 24
    "grasp_miss":       int(TOTAL_EPISODES * 0.09),   # 18
    "trajectory_error": int(TOTAL_EPISODES * 0.05),   # 10
    "timeout":          FAILURE_COUNT - int(TOTAL_EPISODES * 0.12) - int(TOTAL_EPISODES * 0.09) - int(TOTAL_EPISODES * 0.05),  # 6
}

# Phase-wise failure counts
# grasp phase = 52% of all failures
PHASE_FAILURES = {
    "pre_grasp":  int(FAILURE_COUNT * 0.18),   # 10
    "grasp":      int(FAILURE_COUNT * 0.52),   # 30
    "transport":  int(FAILURE_COUNT * 0.18),   # 10
    "placement":  FAILURE_COUNT - int(FAILURE_COUNT * 0.18) - int(FAILURE_COUNT * 0.52) - int(FAILURE_COUNT * 0.18),  # 8
}

# Phase-wise success rates
PHASE_SUCCESS_RATES = {
    "pre_grasp":  0.95,
    "grasp":      0.78,
    "transport":  0.88,
    "placement":  0.91,
}

RECOVERY_SUCCESS_RATE = 0.34   # 34% of failed episodes recovered
COLLISION_RATE = 0.03           # 3%
TIMEOUT_THRESHOLD = 847         # steps

# ---------------------------------------------------------------------------
# SVG 1: Sankey / flow diagram
# ---------------------------------------------------------------------------

def _svg_sankey() -> str:
    W, H = 820, 320
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Episode Outcome Flow (n={TOTAL_EPISODES})</text>')

    # Column x positions
    COL = [80, 280, 520, W - 60]
    CY = H // 2  # center y for root node

    # Node definitions: (label, count, x, y, color)
    nodes = [
        ("All Episodes", TOTAL_EPISODES, COL[0], CY, "#38bdf8"),
        (f"Success\n{SUCCESS_RATE*100:.0f}%", SUCCESS_COUNT, COL[1], CY - 60, "#22c55e"),
        (f"Failure\n{(1-SUCCESS_RATE)*100:.0f}%", FAILURE_COUNT, COL[1], CY + 80, "#ef4444"),
        # Failure sub-modes
        (f"early_drop\n{FAILURE_MODES['early_drop']}", FAILURE_MODES['early_drop'], COL[2], CY + 20, "#f97316"),
        (f"grasp_miss\n{FAILURE_MODES['grasp_miss']}", FAILURE_MODES['grasp_miss'], COL[2], CY + 75, "#fb923c"),
        (f"traj_error\n{FAILURE_MODES['trajectory_error']}", FAILURE_MODES['trajectory_error'], COL[2], CY + 130, "#fbbf24"),
        (f"timeout\n{FAILURE_MODES['timeout']}", FAILURE_MODES['timeout'], COL[2], CY + 185, "#a78bfa"),
    ]

    def flow_width(count, max_count=TOTAL_EPISODES, max_w=40):
        return max(3, int(count / max_count * max_w))

    # Draw flows
    flows = [
        (0, 1, SUCCESS_COUNT, "#22c55e"),
        (0, 2, FAILURE_COUNT, "#ef4444"),
        (2, 3, FAILURE_MODES['early_drop'], "#f97316"),
        (2, 4, FAILURE_MODES['grasp_miss'], "#fb923c"),
        (2, 5, FAILURE_MODES['trajectory_error'], "#fbbf24"),
        (2, 6, FAILURE_MODES['timeout'], "#a78bfa"),
    ]

    for src_idx, dst_idx, count, color in flows:
        sx, sy = nodes[src_idx][2] + 55, nodes[src_idx][3]
        dx, dy = nodes[dst_idx][2] - 5, nodes[dst_idx][3]
        fw = flow_width(count)
        cp1x = sx + (dx - sx) * 0.4
        cp2x = sx + (dx - sx) * 0.6
        lines.append(f'<path d="M{sx},{sy} C{cp1x:.1f},{sy} {cp2x:.1f},{dy} {dx},{dy}" stroke="{color}" stroke-width="{fw}" fill="none" opacity="0.6"/>')

    # Draw nodes
    for label, count, nx, ny, color in nodes:
        rx, ry, rw, rh = nx - 55, ny - 20, 110, 40
        lines.append(f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{color}" rx="6" opacity="0.85"/>')
        for li, part in enumerate(label.split("\n")):
            lines.append(f'<text x="{nx}" y="{ny - 4 + li*14}" text-anchor="middle" fill="#0f172a" font-size="10" font-family="monospace" font-weight="bold">{part}</text>')

    # Root cause annotation
    lines.append(f'<text x="{COL[2] + 55}" y="{CY - 10}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Root causes</text>')
    lines.append(f'<text x="{COL[1] - 55}" y="{CY - 100}" text-anchor="middle" fill="#22c55e" font-size="9" font-family="monospace">{SUCCESS_COUNT} eps</text>')
    lines.append(f'<text x="{COL[1] - 55}" y="{CY + 120}" text-anchor="middle" fill="#ef4444" font-size="9" font-family="monospace">{FAILURE_COUNT} eps</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG 2: Phase-wise failure bar chart
# ---------------------------------------------------------------------------

def _svg_phase_bars() -> str:
    W, H = 820, 280
    LEFT, RIGHT, TOP, BOT = 80, W - 40, 30, H - 60
    phases = list(PHASE_FAILURES.keys())
    counts = [PHASE_FAILURES[p] for p in phases]
    max_count = max(counts)
    BAR_W = (RIGHT - LEFT) / len(phases) * 0.6
    GAP = (RIGHT - LEFT) / len(phases)
    PHASE_COLORS = ["#38bdf8", "#ef4444", "#f59e0b", "#a78bfa"]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Failure Frequency by Task Phase</text>')

    # y-axis
    lines.append(f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{BOT}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{LEFT}" y1="{BOT}" x2="{RIGHT}" y2="{BOT}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="18" y="{(TOP+BOT)//2}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace" transform="rotate(-90,18,{(TOP+BOT)//2})">failure count</text>')

    # y gridlines
    for yi in range(0, max_count + 5, 5):
        yp = BOT - (yi / max_count) * (BOT - TOP)
        if 0 <= yi <= max_count + 4:
            lines.append(f'<line x1="{LEFT}" y1="{yp:.1f}" x2="{RIGHT}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,4"/>')
            lines.append(f'<text x="{LEFT - 6}" y="{yp + 4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{yi}</text>')

    for i, (phase, cnt) in enumerate(zip(phases, counts)):
        cx = LEFT + i * GAP + GAP / 2
        bx = cx - BAR_W / 2
        bh = (cnt / max_count) * (BOT - TOP)
        by = BOT - bh
        color = PHASE_COLORS[i]
        # highlight grasp phase
        opacity = "1.0" if phase == "grasp" else "0.75"
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{BAR_W:.1f}" height="{bh:.1f}" fill="{color}" rx="4" opacity="{opacity}"/>')
        # count on top
        lines.append(f'<text x="{cx:.1f}" y="{by - 4:.1f}" text-anchor="middle" fill="{color}" font-size="13" font-family="monospace" font-weight="bold">{cnt}</text>')
        # pct label
        pct = round(cnt / FAILURE_COUNT * 100)
        lines.append(f'<text x="{cx:.1f}" y="{by - 18:.1f}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{pct}%</text>')
        # x-axis label
        lines.append(f'<text x="{cx:.1f}" y="{BOT + 16}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{phase}</text>')
        # success rate
        sr = PHASE_SUCCESS_RATES[phase]
        lines.append(f'<text x="{cx:.1f}" y="{BOT + 30}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">SR={sr:.0%}</text>')
        # annotation for grasp
        if phase == "grasp":
            lines.append(f'<text x="{cx:.1f}" y="{by - 34:.1f}" text-anchor="middle" fill="#ef4444" font-size="9" font-family="monospace">← 52% of failures</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    sankey = _svg_sankey()
    phase_bars = _svg_phase_bars()

    top_mode = max(FAILURE_MODES, key=FAILURE_MODES.get)
    top_mode_pct = round(FAILURE_MODES[top_mode] / FAILURE_COUNT * 100)

    failure_rows = ""
    for mode, cnt in sorted(FAILURE_MODES.items(), key=lambda x: -x[1]):
        pct = round(cnt / FAILURE_COUNT * 100)
        failure_rows += f"<tr><td>{mode}</td><td>{cnt}</td><td>{pct}%</td></tr>\n"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Task Success Analyzer — Port 8241</title>
<style>
  body {{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px;}}
  h1 {{color:#C74634;margin-bottom:4px;}}
  h2 {{color:#38bdf8;margin-top:28px;margin-bottom:8px;font-size:14px;}}
  .grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
  .card {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px;text-align:center;}}
  .card .val {{font-size:28px;font-weight:bold;color:#38bdf8;}}
  .card .lbl {{font-size:11px;color:#64748b;margin-top:4px;}}
  svg {{max-width:100%;display:block;margin-bottom:16px;}}
  table {{border-collapse:collapse;width:340px;font-size:12px;}}
  th {{background:#1e293b;color:#38bdf8;padding:6px 12px;text-align:left;}}
  td {{padding:5px 12px;border-bottom:1px solid #1e293b;}}
  .insight {{background:#1e293b;border-left:3px solid #C74634;padding:10px 14px;margin-bottom:12px;font-size:12px;color:#94a3b8;}}
  footer {{margin-top:32px;font-size:10px;color:#334155;}}
</style>
</head>
<body>
<h1>Task Success Analyzer</h1>
<p style="color:#64748b;font-size:12px;">Port 8241 — Root-cause analysis for robot manipulation episodes</p>

<div class="grid">
  <div class="card"><div class="val" style="color:#22c55e">{SUCCESS_RATE*100:.0f}%</div><div class="lbl">Overall Success Rate</div></div>
  <div class="card"><div class="val" style="color:#ef4444">{top_mode_pct}%</div><div class="lbl">Top Failure Mode<br>({top_mode})</div></div>
  <div class="card"><div class="val">{RECOVERY_SUCCESS_RATE*100:.0f}%</div><div class="lbl">Recovery Success Rate</div></div>
  <div class="card"><div class="val" style="color:#f59e0b">{COLLISION_RATE*100:.0f}%</div><div class="lbl">Collision Rate</div></div>
</div>

<div class="insight">Insight: <strong>grasp phase</strong> accounts for 52% of all failures — force control improvements are the highest-leverage intervention. Timeout episodes consistently exceed <strong>{TIMEOUT_THRESHOLD} steps</strong>.</div>

<h2>Episode Outcome Flow</h2>
{sankey}

<h2>Failure Frequency by Task Phase</h2>
{phase_bars}

<h2>Failure Mode Taxonomy</h2>
<table>
<tr><th>Mode</th><th>Count</th><th>% of Failures</th></tr>
{failure_rows}
</table>

<footer>OCI Robot Cloud | Task Success Analyzer v1.0 | cycle-45A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Task Success Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "task_success_analyzer", "port": 8241}

    @app.get("/api/failure-modes")
    async def failure_modes():
        return {
            "total_episodes": TOTAL_EPISODES,
            "success_count": SUCCESS_COUNT,
            "failure_count": FAILURE_COUNT,
            "failure_modes": FAILURE_MODES,
            "phase_failures": PHASE_FAILURES,
            "phase_success_rates": PHASE_SUCCESS_RATES,
        }

    @app.get("/api/metrics")
    async def get_metrics():
        return {
            "success_rate": SUCCESS_RATE,
            "top_failure_mode": max(FAILURE_MODES, key=FAILURE_MODES.get),
            "recovery_success_rate": RECOVERY_SUCCESS_RATE,
            "collision_rate": COLLISION_RATE,
            "timeout_threshold_steps": TIMEOUT_THRESHOLD,
            "grasp_phase_failure_pct": 0.52,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8241)
    else:
        print("[task_success_analyzer] FastAPI not found, using stdlib http.server on port 8241")
        HTTPServer(("0.0.0.0", 8241), _Handler).serve_forever()
