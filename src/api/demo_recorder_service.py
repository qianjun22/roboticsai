"""Demo Recorder Service — port 8240
Manages teleoperation demo recording sessions for DAgger data collection.
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

OPERATORS = ["operator_1", "operator_2", "operator_3", "operator_4"]
ROBOT_IDS = ["robot-A1", "robot-A2", "robot-B1", "robot-B2", "robot-C1"]
STATUSES = ["UPLOADED", "PROCESSING", "FAILED"]
STATUS_WEIGHTS = [0.70, 0.20, 0.10]

# 3 sessions are FAILED (network timeout), rest distributed
def _gen_sessions(n=10):
    sessions = []
    base_time = datetime(2026, 3, 28, 8, 0, 0)
    for i in range(n):
        start = base_time + timedelta(hours=i * 2.3 + random.uniform(0, 0.5))
        duration_min = random.randint(30, 75)
        end = start + timedelta(minutes=duration_min)
        operator = OPERATORS[i % len(OPERATORS)]
        # operator_2 gets highest quality
        if operator == "operator_2":
            quality = round(random.uniform(0.78, 0.93), 2)
        else:
            quality = round(random.uniform(0.55, 0.88), 2)
        episodes = int(duration_min * (31 / 47) + random.randint(-3, 3))
        # 3 FAILED sessions
        if i in (2, 5, 8):
            status = "FAILED"
            fail_reason = "network timeout"
        elif i % 5 == 1:
            status = "PROCESSING"
            fail_reason = None
        else:
            status = "UPLOADED"
            fail_reason = None
        sessions.append({
            "id": f"sess-{2600 + i}",
            "start": start,
            "end": end,
            "duration_min": duration_min,
            "robot_id": ROBOT_IDS[i % len(ROBOT_IDS)],
            "operator": operator,
            "episodes": episodes,
            "quality": quality,
            "status": status,
            "fail_reason": fail_reason,
        })
    return sessions

def _gen_episode_quality(n=500):
    """Return list of quality scores for 500 demos."""
    scores = []
    # 82% acceptance rate => ~410 accepted
    for _ in range(n):
        r = random.random()
        if r < 0.18:          # rejected <0.5
            scores.append(round(random.uniform(0.10, 0.499), 3))
        elif r < 0.55:        # accepted 0.5-0.8
            scores.append(round(random.uniform(0.50, 0.799), 3))
        else:                 # high-quality >0.8
            scores.append(round(random.uniform(0.80, 0.99), 3))
    return scores

SESSIONS = _gen_sessions(10)
EPISODE_SCORES = _gen_episode_quality(500)

# Derived metrics
ACCEPTED = sum(1 for s in EPISODE_SCORES if s >= 0.5)
ACCEPTANCE_RATE = round(ACCEPTED / len(EPISODE_SCORES) * 100, 1)
TOTAL_HOURS = sum(s["duration_min"] for s in SESSIONS) / 60
TOTAL_DEMOS = sum(s["episodes"] for s in SESSIONS)
DEMOS_PER_HOUR = round(TOTAL_DEMOS / max(TOTAL_HOURS, 1), 1)
UPLOAD_SUCCESS = sum(1 for s in SESSIONS if s["status"] == "UPLOADED")
UPLOAD_RATE = round(UPLOAD_SUCCESS / len(SESSIONS) * 100, 1)

# Operator quality ranking
op_scores = {op: [] for op in OPERATORS}
for s in SESSIONS:
    op_scores[s["operator"]].append(s["quality"])
OP_RANKING = sorted(
    [(op, round(sum(v) / len(v), 2)) for op, v in op_scores.items() if v],
    key=lambda x: -x[1],
)

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "UPLOADED": "#22c55e",
    "PROCESSING": "#f59e0b",
    "FAILED": "#ef4444",
}


def _svg_gantt() -> str:
    """Gantt-style chart of 10 recording sessions."""
    W, H = 820, 340
    LEFT = 110
    RIGHT = W - 20
    TOP = 30
    ROW_H = 26
    BAR_H = 16

    # time range
    t_min = SESSIONS[0]["start"]
    t_max = SESSIONS[-1]["end"]
    span = (t_max - t_min).total_seconds()

    def tx(dt):
        frac = (dt - t_min).total_seconds() / span
        return LEFT + frac * (RIGHT - LEFT)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    # title
    lines.append(f'<text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Recording Session Timeline (last 10 sessions)</text>')

    # time axis ticks
    for i in range(6):
        frac = i / 5
        xp = LEFT + frac * (RIGHT - LEFT)
        tick_time = t_min + timedelta(seconds=frac * span)
        label = tick_time.strftime("%H:%M")
        lines.append(f'<line x1="{xp:.1f}" y1="{TOP}" x2="{xp:.1f}" y2="{TOP + len(SESSIONS)*ROW_H + 4}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{xp:.1f}" y="{TOP + len(SESSIONS)*ROW_H + 16}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{label}</text>')

    for idx, s in enumerate(SESSIONS):
        y = TOP + idx * ROW_H
        x1 = tx(s["start"])
        x2 = tx(s["end"])
        bar_w = max(x2 - x1, 4)
        color = STATUS_COLORS[s["status"]]
        bar_y = y + (ROW_H - BAR_H) // 2
        # row label
        label = f"{s['id']} | {s['operator']}"
        lines.append(f'<text x="{LEFT - 4}" y="{bar_y + BAR_H - 4}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')
        # bar
        lines.append(f'<rect x="{x1:.1f}" y="{bar_y}" width="{bar_w:.1f}" height="{BAR_H}" fill="{color}" rx="3" opacity="0.85"/>')
        # inside label: episodes + quality
        if bar_w > 60:
            mid = (x1 + x2) / 2
            lines.append(f'<text x="{mid:.1f}" y="{bar_y + BAR_H - 4}" text-anchor="middle" fill="#0f172a" font-size="8" font-family="monospace">{s["episodes"]}ep Q{s["quality"]}</text>')

    # legend
    lx = LEFT
    ly = TOP + len(SESSIONS) * ROW_H + 30
    for i, (st, col) in enumerate(STATUS_COLORS.items()):
        bx = lx + i * 130
        lines.append(f'<rect x="{bx}" y="{ly}" width="12" height="12" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{bx + 16}" y="{ly + 10}" fill="#94a3b8" font-size="10" font-family="monospace">{st}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _svg_quality_dist() -> str:
    """Episode quality distribution bar chart (binned)."""
    W, H = 820, 280
    BINS = 20
    bin_size = 1.0 / BINS
    counts = [0] * BINS
    for sc in EPISODE_SCORES:
        b = min(int(sc / bin_size), BINS - 1)
        counts[b] += 1
    max_count = max(counts)

    LEFT, RIGHT, TOP, BOT = 50, W - 20, 20, H - 50
    bar_w = (RIGHT - LEFT) / BINS

    def bar_color(bin_idx):
        mid = (bin_idx + 0.5) * bin_size
        if mid < 0.5:
            return "#ef4444"   # rejected
        elif mid < 0.8:
            return "#f59e0b"   # accepted
        else:
            return "#22c55e"   # high-quality

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="14" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Episode Quality Distribution (n=500 demos)</text>')

    # threshold lines
    for thresh, label in [(0.5, "reject/accept"), (0.8, "accept/high")]:
        xp = LEFT + thresh * (RIGHT - LEFT)
        lines.append(f'<line x1="{xp:.1f}" y1="{TOP}" x2="{xp:.1f}" y2="{BOT}" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{xp + 3:.1f}" y="{TOP + 12}" fill="#64748b" font-size="9" font-family="monospace">{label}</text>')

    for i, cnt in enumerate(counts):
        bh = (cnt / max_count) * (BOT - TOP)
        bx = LEFT + i * bar_w
        by = BOT - bh
        color = bar_color(i)
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 1:.1f}" height="{bh:.1f}" fill="{color}" rx="2" opacity="0.85"/>')
        # count label on taller bars
        if cnt > 15:
            lines.append(f'<text x="{bx + bar_w/2:.1f}" y="{by - 2:.1f}" text-anchor="middle" fill="#94a3b8" font-size="8" font-family="monospace">{cnt}</text>')

    # x-axis labels
    for i in range(0, BINS + 1, 4):
        xp = LEFT + i * bar_w
        lines.append(f'<text x="{xp:.1f}" y="{BOT + 14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{i * bin_size:.1f}</text>')

    # y-axis
    lines.append(f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{BOT}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="12" y="{(TOP+BOT)//2}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace" transform="rotate(-90,12,{(TOP+BOT)//2})">count</text>')

    # legend
    for i, (label, color) in enumerate([("Rejected (<0.5)", "#ef4444"), ("Accepted (0.5-0.8)", "#f59e0b"), ("High-quality (>0.8)", "#22c55e")]):
        lx = LEFT + i * 220
        ly = BOT + 28
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{ly + 10}" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    gantt = _svg_gantt()
    quality_dist = _svg_quality_dist()

    op_rows = ""
    for rank, (op, avg_q) in enumerate(OP_RANKING, 1):
        badge = ' style="color:#22c55e;font-weight:bold"' if op == "operator_2" else ""
        op_rows += f"<tr><td>{rank}</td><td{badge}>{op}</td><td>{avg_q}</td></tr>\n"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Demo Recorder Service — Port 8240</title>
<style>
  body {{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px;}}
  h1 {{color:#C74634;margin-bottom:4px;}}
  h2 {{color:#38bdf8;margin-top:28px;margin-bottom:8px;font-size:14px;}}
  .grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
  .card {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px;text-align:center;}}
  .card .val {{font-size:28px;font-weight:bold;color:#38bdf8;}}
  .card .lbl {{font-size:11px;color:#64748b;margin-top:4px;}}
  svg {{max-width:100%;display:block;margin-bottom:16px;}}
  table {{border-collapse:collapse;width:320px;font-size:12px;}}
  th {{background:#1e293b;color:#38bdf8;padding:6px 12px;text-align:left;}}
  td {{padding:5px 12px;border-bottom:1px solid #1e293b;}}
  .badge-up {{color:#22c55e;}} .badge-proc {{color:#f59e0b;}} .badge-fail {{color:#ef4444;}}
  footer {{margin-top:32px;font-size:10px;color:#334155;}}
</style>
</head>
<body>
<h1>Demo Recorder Service</h1>
<p style="color:#64748b;font-size:12px;">Port 8240 — DAgger teleoperation data collection pipeline</p>

<div class="grid">
  <div class="card"><div class="val">500</div><div class="lbl">Total Demos</div></div>
  <div class="card"><div class="val" style="color:#22c55e">{ACCEPTANCE_RATE}%</div><div class="lbl">Acceptance Rate</div></div>
  <div class="card"><div class="val">{DEMOS_PER_HOUR}</div><div class="lbl">Demos / Hour</div></div>
  <div class="card"><div class="val" style="color:{'#22c55e' if UPLOAD_RATE >= 70 else '#ef4444'}">{UPLOAD_RATE}%</div><div class="lbl">Upload Success Rate</div></div>
</div>

<h2>Recording Session Timeline (Gantt)</h2>
{gantt}

<h2>Episode Quality Distribution</h2>
{quality_dist}

<h2>Operator Quality Ranking</h2>
<table>
<tr><th>#</th><th>Operator</th><th>Avg Quality</th></tr>
{op_rows}
</table>

<footer>OCI Robot Cloud | Demo Recorder Service v1.0 | cycle-45A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Demo Recorder Service", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "demo_recorder_service", "port": 8240}

    @app.get("/api/sessions")
    async def get_sessions():
        return [{**s, "start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in SESSIONS]

    @app.get("/api/metrics")
    async def get_metrics():
        return {
            "total_demos": len(EPISODE_SCORES),
            "acceptance_rate": ACCEPTANCE_RATE,
            "demos_per_hour": DEMOS_PER_HOUR,
            "upload_success_rate": UPLOAD_RATE,
            "operator_ranking": OP_RANKING,
            "failed_sessions": sum(1 for s in SESSIONS if s["status"] == "FAILED"),
        }

else:
    # Fallback: stdlib http.server
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
        uvicorn.run(app, host="0.0.0.0", port=8240)
    else:
        print("[demo_recorder_service] FastAPI not found, using stdlib http.server on port 8240")
        HTTPServer(("0.0.0.0", 8240), _Handler).serve_forever()
