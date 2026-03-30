try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Training Resume Optimizer", version="1.0.0")

# 8 recovery events: 3 OOM, 3 spot preemptions, 1 network, 1 manual
RECOVERY_EVENTS = [
    {"id": 1,  "type": "OOM",     "recovery_min": 1.8, "color": "#C74634"},
    {"id": 2,  "type": "spot",    "recovery_min": 2.1, "color": "#f97316"},
    {"id": 3,  "type": "OOM",     "recovery_min": 2.5, "color": "#C74634"},
    {"id": 4,  "type": "spot",    "recovery_min": 2.3, "color": "#f97316"},
    {"id": 5,  "type": "network", "recovery_min": 3.2, "color": "#38bdf8"},
    {"id": 6,  "type": "OOM",     "recovery_min": 1.9, "color": "#C74634"},
    {"id": 7,  "type": "spot",    "recovery_min": 2.6, "color": "#f97316"},
    {"id": 8,  "type": "manual",  "recovery_min": 2.8, "color": "#a855f7"},
]

# Progress loss vs checkpoint interval
PROGRESS_LOSS_DATA = [
    {"interval_steps": 100,  "progress_lost_pct": 0.2},
    {"interval_steps": 500,  "progress_lost_pct": 0.7},
    {"interval_steps": 1000, "progress_lost_pct": 2.1},
    {"interval_steps": 2000, "progress_lost_pct": 5.8},
]

# Cost vs recovery fidelity tradeoff curve (checkpoint overhead % vs avg progress loss %)
TRADEOFF_DATA = [
    {"overhead_pct": 2,  "progress_loss_pct": 5.8},
    {"overhead_pct": 4,  "progress_loss_pct": 2.1},
    {"overhead_pct": 8,  "progress_loss_pct": 0.7},   # optimal zone ~ 500 steps
    {"overhead_pct": 15, "progress_loss_pct": 0.3},
    {"overhead_pct": 28, "progress_loss_pct": 0.2},
]

AVG_RECOVERY_MIN = round(sum(e["recovery_min"] for e in RECOVERY_EVENTS) / len(RECOVERY_EVENTS), 1)

EVENT_TYPE_COLORS = {
    "OOM": "#C74634",
    "spot": "#f97316",
    "network": "#38bdf8",
    "manual": "#a855f7",
}


def _build_recovery_histogram_svg() -> str:
    W, H = 700, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 30, 20, 45
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(RECOVERY_EVENTS)
    gap = 8
    bar_w = (inner_w - gap * (n - 1)) / n
    y_max = 4.0

    def yp(v):
        return PAD_T + inner_h - v / y_max * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]

    # Y gridlines
    for v in (1.0, 2.0, 3.0, 4.0):
        gy = yp(v)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+inner_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{gy+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{v:.0f}m</text>')

    # Average line
    avg_y = yp(AVG_RECOVERY_MIN)
    lines.append(f'<line x1="{PAD_L}" y1="{avg_y:.1f}" x2="{PAD_L+inner_w}" y2="{avg_y:.1f}" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'<text x="{PAD_L+inner_w+4}" y="{avg_y+4:.1f}" fill="#38bdf8" font-size="10">avg {AVG_RECOVERY_MIN}m</text>')

    # Bars
    for i, ev in enumerate(RECOVERY_EVENTS):
        bx = PAD_L + i * (bar_w + gap)
        bh = ev["recovery_min"] / y_max * inner_h
        by = PAD_T + inner_h - bh
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{ev["color"]}" rx="3" opacity="0.85"/>')
        # Label: event type (abbreviated)
        label = ev["type"][:3]
        lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{label}{ev["id"]}</text>')
        lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{ev["recovery_min"]}m</text>')

    # Legend
    lx = PAD_L + 4
    ly = PAD_T + inner_h + 32
    for etype, ec in EVENT_TYPE_COLORS.items():
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="10" height="10" fill="{ec}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="{ly}" fill="#94a3b8" font-size="9">{etype}</text>')
        lx += 70

    lines.append("</svg>")
    return "\n".join(lines)


def _build_progress_loss_scatter_svg() -> str:
    W, H = 560, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 40, 20, 38
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    x_max = 2200
    y_max = 7.0

    def xp(v):
        return PAD_L + v / x_max * inner_w

    def yp(v):
        return PAD_T + inner_h - v / y_max * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]

    # Grid
    for xv in (500, 1000, 1500, 2000):
        gx = xp(xv)
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{xv}</text>')

    for yv in (1, 2, 3, 4, 5, 6):
        gy = yp(yv)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+inner_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{gy+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yv}%</text>')

    # Connect line
    coords = [(xp(d["interval_steps"]), yp(d["progress_lost_pct"])) for d in PROGRESS_LOSS_DATA]
    d_path = " ".join(f"{'M' if i == 0 else 'L'}{cx:.1f},{cy:.1f}" for i, (cx, cy) in enumerate(coords))
    lines.append(f'<path d="{d_path}" fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="4,4"/>')

    # Scatter points
    point_colors = ["#38bdf8", "#22c55e", "#f97316", "#C74634"]
    for i, (pt, color) in enumerate(zip(PROGRESS_LOSS_DATA, point_colors)):
        cx, cy = xp(pt["interval_steps"]), yp(pt["progress_lost_pct"])
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" opacity="0.85"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy-12:.1f}" fill="{color}" font-size="10" text-anchor="middle">{pt["interval_steps"]}s</text>')
        lines.append(f'<text x="{cx:.1f}" y="{cy+20:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{pt["progress_lost_pct"]}%</text>')

    # Axis labels
    lines.append(f'<text x="{PAD_L+inner_w//2}" y="{PAD_T+inner_h+30}" fill="#64748b" font-size="10" text-anchor="middle">Checkpoint Interval (steps)</text>')
    lines.append(f'<text x="12" y="{PAD_T+inner_h//2}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 12 {PAD_T+inner_h//2})">% Progress Lost</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _build_tradeoff_curve_svg() -> str:
    W, H = 560, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 40, 20, 38
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    x_max = 32.0
    y_max = 7.0

    def xp(v):
        return PAD_L + v / x_max * inner_w

    def yp(v):
        return PAD_T + inner_h - v / y_max * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]

    # Grid
    for xv in (5, 10, 15, 20, 25, 30):
        gx = xp(xv)
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{xv}%</text>')

    for yv in (1, 2, 3, 4, 5, 6):
        gy = yp(yv)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+inner_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{gy+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yv}%</text>')

    # Optimal zone highlight (x: 6-12%, y: 0.4-1.2%)
    oz_x1 = xp(6)
    oz_x2 = xp(12)
    oz_y1 = yp(1.2)
    oz_y2 = yp(0.4)
    lines.append(f'<rect x="{oz_x1:.1f}" y="{oz_y1:.1f}" width="{oz_x2-oz_x1:.1f}" height="{oz_y2-oz_y1:.1f}" fill="#22c55e" opacity="0.12" rx="4"/>')
    lines.append(f'<text x="{(oz_x1+oz_x2)/2:.1f}" y="{oz_y1-6:.1f}" fill="#22c55e" font-size="10" text-anchor="middle">Optimal Zone</text>')

    # Curve
    coords = [(xp(d["overhead_pct"]), yp(d["progress_loss_pct"])) for d in TRADEOFF_DATA]
    d_path = " ".join(f"{'M' if i == 0 else 'L'}{cx:.1f},{cy:.1f}" for i, (cx, cy) in enumerate(coords))
    lines.append(f'<path d="{d_path}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # Points
    for pt in TRADEOFF_DATA:
        cx, cy = xp(pt["overhead_pct"]), yp(pt["progress_loss_pct"])
        is_opt = pt["overhead_pct"] == 8
        pc = "#22c55e" if is_opt else "#38bdf8"
        r = 7 if is_opt else 5
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{pc}" opacity="0.9"/>')
        if is_opt:
            lines.append(f'<text x="{cx+12:.1f}" y="{cy-6:.1f}" fill="#22c55e" font-size="10">500-step</text>')

    # Axis labels
    lines.append(f'<text x="{PAD_L+inner_w//2}" y="{PAD_T+inner_h+30}" fill="#64748b" font-size="10" text-anchor="middle">Checkpoint Overhead (%)</text>')
    lines.append(f'<text x="12" y="{PAD_T+inner_h//2}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 12 {PAD_T+inner_h//2})">Avg Progress Loss (%)</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def build_html() -> str:
    svg_hist = _build_recovery_histogram_svg()
    svg_scatter = _build_progress_loss_scatter_svg()
    svg_tradeoff = _build_tradeoff_curve_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — Training Resume Optimizer</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #C74634; }}
    .header .dot {{ width: 10px; height: 10px; border-radius: 50%; background: #38bdf8; box-shadow: 0 0 6px #38bdf8; animation: pulse 2s infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.4}} }}
    .sub {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
    .content {{ padding: 28px 32px; max-width: 1100px; margin: 0 auto; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 20px; }}
    .stat-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .stat-value {{ font-size: 28px; font-weight: 700; color: #f1f5f9; }}
    .stat-sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: start; }}
    .chart-wrap {{ overflow-x: auto; }}
    .footer {{ text-align: center; padding: 20px; font-size: 11px; color: #334155; border-top: 1px solid #1e293b; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="header">
    <div class="dot"></div>
    <div>
      <h1>Training Resume Optimizer</h1>
      <div class="sub">OCI Robot Cloud — Checkpoint Strategy &amp; Fault Recovery Analytics</div>
    </div>
  </div>
  <div class="content">

    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Optimal Interval</div>
        <div class="stat-value" style="color:#22c55e;">500</div>
        <div class="stat-sub">steps — min cost/fidelity tradeoff</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Progress Lost (500s)</div>
        <div class="stat-value" style="color:#38bdf8;">0.7%</div>
        <div class="stat-sub">avg on interruption</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Checkpoint Overhead</div>
        <div class="stat-value">8%</div>
        <div class="stat-sub">at 500-step interval</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Adaptive Savings</div>
        <div class="stat-value" style="color:#C74634;">60%</div>
        <div class="stat-sub">overhead cut on gradient spike</div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Checkpoint Recovery Time — 8 Events (min)</div>
      <div class="chart-wrap">{svg_hist}</div>
    </div>

    <div class="section two-col">
      <div>
        <div class="section-title">Progress Lost vs Checkpoint Interval</div>
        <div class="chart-wrap">{svg_scatter}</div>
      </div>
      <div>
        <div class="section-title">Cost vs Recovery Fidelity Tradeoff</div>
        <div class="chart-wrap">{svg_tradeoff}</div>
      </div>
    </div>

  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud Training Resume Optimizer | Port 8617</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return build_html()


@app.get("/recovery-events")
def recovery_events():
    return JSONResponse(content=RECOVERY_EVENTS)


@app.get("/progress-loss")
def progress_loss():
    return JSONResponse(content=PROGRESS_LOSS_DATA)


@app.get("/tradeoff")
def tradeoff():
    return JSONResponse(content=TRADEOFF_DATA)


@app.get("/summary")
def summary():
    return JSONResponse(content={
        "optimal_checkpoint_interval_steps": 500,
        "optimal_progress_loss_pct": 0.7,
        "optimal_overhead_pct": 8.0,
        "adaptive_checkpoint_overhead_reduction_pct": 60,
        "avg_recovery_min": AVG_RECOVERY_MIN,
        "total_events": len(RECOVERY_EVENTS),
        "event_type_counts": {
            et: sum(1 for e in RECOVERY_EVENTS if e["type"] == et)
            for et in EVENT_TYPE_COLORS
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


@app.get("/health")
def health():
    return JSONResponse(content={
        "status": "ok",
        "service": "training_resume_optimizer",
        "port": 8617,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


def main():
    uvicorn.run("training_resume_optimizer:app", host="0.0.0.0", port=8617, reload=False)


if __name__ == "__main__":
    main()
