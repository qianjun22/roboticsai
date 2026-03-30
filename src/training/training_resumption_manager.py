"""training_resumption_manager.py — OCI Robot Cloud Training Resumption Manager
FastAPI service on port 8327
Manages automatic training job resumption after interruptions (OOM, spot preemption, crashes).
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

INTERRUPTION_TYPES = {
    "oom":              {"color": "#ef4444", "label": "OOM",             "avg_lost_pct": 0.3,  "avg_recovery_min": 2.1},
    "spot_preemption": {"color": "#f97316", "label": "Spot Preempt",    "avg_lost_pct": 1.2,  "avg_recovery_min": 3.1},
    "network_loss":    {"color": "#eab308", "label": "Network Loss",    "avg_lost_pct": 0.8,  "avg_recovery_min": 2.7},
    "manual_pause":    {"color": "#38bdf8", "label": "Manual Pause",    "avg_lost_pct": 0.0,  "avg_recovery_min": 0.5},
}

# 8 events spread across 90 days (day 0 = 90 days ago)
EVENTS = [
    {"day": 4,  "type": "oom",              "job": "gr00t-finetune-v3",   "step_lost": 2,   "checkpoint_step": 950,  "recovery_min": 1.8},
    {"day": 11, "type": "spot_preemption", "job": "dagger-run6",          "step_lost": 12,  "checkpoint_step": 4988, "recovery_min": 3.2},
    {"day": 23, "type": "oom",              "job": "gr00t-finetune-v4",   "step_lost": 3,   "checkpoint_step": 1750, "recovery_min": 2.0},
    {"day": 37, "type": "network_loss",    "job": "multi-task-eval",      "step_lost": 7,   "checkpoint_step": 2143, "recovery_min": 2.7},
    {"day": 52, "type": "spot_preemption", "job": "curriculum-train-b2", "step_lost": 14,  "checkpoint_step": 7800, "recovery_min": 3.0},
    {"day": 63, "type": "oom",              "job": "gr00t-finetune-v5",   "step_lost": 2,   "checkpoint_step": 2000, "recovery_min": 2.3},
    {"day": 74, "type": "spot_preemption", "job": "dagger-run7",          "step_lost": 11,  "checkpoint_step": 3500, "recovery_min": 3.1},
    {"day": 85, "type": "manual_pause",    "job": "sdg-gen-run9",         "step_lost": 0,   "checkpoint_step": 5000, "recovery_min": 0.4},
]

METRICS = {
    "total_interruptions_90d": 8,
    "oom_events": 3,
    "spot_preemptions": 3,
    "network_loss_events": 1,
    "manual_pauses": 1,
    "avg_progress_lost": "0.7%",
    "fastest_recovery": "OOM — 1.8 min",
    "slowest_recovery": "Spot preempt — 3.2 min",
    "complete_restarts": 0,
    "checkpoint_interval": "50 steps",
    "checkpoint_strategy": "rolling-3",
}

PROGRESS_LOST = {
    "OOM":          0.3,
    "Spot Preempt": 1.2,
    "Network Loss": 0.8,
    "Manual Pause": 0.0,
    "Mean":         0.7,
}


# ---------------------------------------------------------------------------
# SVG 1: Interruption event log timeline (90 days)
# ---------------------------------------------------------------------------

def svg_interruption_timeline() -> str:
    W, H = 820, 260
    PAD_L, PAD_R, PAD_T, PAD_B = 120, 30, 40, 50
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    days = 90

    def px(d):
        return PAD_L + (d / days) * plot_w

    # Row layout: one row per interruption type
    type_keys = list(INTERRUPTION_TYPES.keys())
    row_h = plot_h / len(type_keys)

    rows = ""
    for ri, tk in enumerate(type_keys):
        ty = INTERRUPTION_TYPES[tk]
        cy = PAD_T + ri * row_h + row_h / 2
        # Row label
        rows += f'<text x="{PAD_L - 8}" y="{cy + 4:.1f}" fill="{ty["color"]}" font-size="11" text-anchor="end" font-weight="600">{ty["label"]}</text>'
        # Baseline
        rows += f'<line x1="{PAD_L}" y1="{cy:.1f}" x2="{PAD_L + plot_w}" y2="{cy:.1f}" stroke="#1e293b" stroke-width="1.5"/>'

    # Event dots
    event_svg = ""
    for ev in EVENTS:
        tk = ev["type"]
        ty = INTERRUPTION_TYPES[tk]
        ri = type_keys.index(tk)
        cx = px(ev["day"])
        cy = PAD_T + ri * row_h + row_h / 2
        r = 9
        event_svg += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{ty["color"]}" fill-opacity="0.85" stroke="#0f172a" stroke-width="1.5"/>'
        # Checkpoint annotation
        ckpt_label = f'ckpt@{ev["checkpoint_step"]}'
        event_svg += f'<text x="{cx:.1f}" y="{cy - r - 5:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{ckpt_label}</text>'
        # Recovery time
        event_svg += f'<text x="{cx:.1f}" y="{cy + r + 12:.1f}" fill="#64748b" font-size="8" text-anchor="middle">{ev["recovery_min"]}m</text>'

    # X-axis: day markers
    x_axis = ""
    for d in range(0, days + 1, 15):
        xp = px(d)
        x_axis += f'<line x1="{xp:.1f}" y1="{PAD_T}" x2="{xp:.1f}" y2="{PAD_T + plot_h}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,4"/>'
        label = f"Day -{days - d}" if d < days else "Today"
        x_axis += f'<text x="{xp:.1f}" y="{PAD_T + plot_h + 18}" fill="#64748b" font-size="9" text-anchor="middle">{label}</text>'

    return f'''
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Interruption Event Log — 90-Day Timeline</text>
      <text x="{W//2}" y="34" fill="#64748b" font-size="10" text-anchor="middle">Each dot = 1 event; label shows checkpoint used for resumption + recovery time</text>
      {x_axis}
      {rows}
      {event_svg}
    </svg>
    '''


# ---------------------------------------------------------------------------
# SVG 2: Recovery efficiency bar chart
# ---------------------------------------------------------------------------

def svg_recovery_efficiency() -> str:
    W, H = 820, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 40, 60
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    items = list(PROGRESS_LOST.items())
    n = len(items)
    max_val = 1.8  # cap at 1.8% for readable scale
    bar_w = min(80, plot_w / n - 20)
    group_w = plot_w / n

    bars = ""
    colors = ["#ef4444", "#f97316", "#eab308", "#38bdf8", "#a78bfa"]
    for i, (label, val) in enumerate(items):
        cx = PAD_L + i * group_w + group_w / 2
        bar_h = (val / max_val) * plot_h
        by = PAD_T + plot_h - bar_h
        color = colors[i % len(colors)]
        is_mean = label == "Mean"
        if is_mean:
            # Mean as a horizontal reference line
            yref = PAD_T + plot_h - (val / max_val) * plot_h
            bars += f'<line x1="{PAD_L}" y1="{yref:.1f}" x2="{PAD_L + plot_w}" y2="{yref:.1f}" stroke="#a78bfa" stroke-width="2" stroke-dasharray="6,3"/>'
            bars += f'<text x="{PAD_L + plot_w + 4}" y="{yref + 4:.1f}" fill="#a78bfa" font-size="11">Mean {val}%</text>'
        else:
            bars += f'<rect x="{cx - bar_w/2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" rx="3"/>'
            bars += f'<text x="{cx:.1f}" y="{by - 6:.1f}" fill="{color}" font-size="12" font-weight="700" text-anchor="middle">{val}%</text>'
            bars += f'<text x="{cx:.1f}" y="{PAD_T + plot_h + 18}" fill="#e2e8f0" font-size="11" text-anchor="middle">{label}</text>'

    # Y-axis
    y_axis = ""
    for tick_pct in [0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8]:
        yp = PAD_T + plot_h - (tick_pct / max_val) * plot_h
        y_axis += f'<text x="{PAD_L - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick_pct}%</text>'
        y_axis += f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L + plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'

    # Sub-labels with recovery times
    recovery_notes = [
        ("OOM",          "ckpt/50 steps",   2.1),
        ("Spot Preempt", "ckpt/50 steps",   3.1),
        ("Network Loss", "ckpt/50 steps",   2.7),
        ("Manual Pause", "clean shutdown",  0.5),
    ]
    rec_svg = ""
    for i, (_, note, rec) in enumerate(recovery_notes):
        cx = PAD_L + i * group_w + group_w / 2
        rec_svg += f'<text x="{cx:.1f}" y="{PAD_T + plot_h + 33}" fill="#64748b" font-size="9" text-anchor="middle">{note}</text>'
        rec_svg += f'<text x="{cx:.1f}" y="{PAD_T + plot_h + 46}" fill="#64748b" font-size="9" text-anchor="middle">~{rec}min recovery</text>'

    return f'''
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Recovery Efficiency — % Training Progress Lost per Interruption Type</text>
      {y_axis}
      {bars}
      {rec_svg}
      <line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{PAD_L+plot_w}" y2="{PAD_T+plot_h}" stroke="#334155" stroke-width="1.5"/>
    </svg>
    '''


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_interruption_timeline()
    svg2 = svg_recovery_efficiency()

    metric_cards = ""
    for k, v in METRICS.items():
        label = k.replace("_", " ").title()
        metric_cards += f'''
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;min-width:160px;flex:1">
          <div style="color:#64748b;font-size:11px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">{label}</div>
          <div style="color:#e2e8f0;font-size:17px;font-weight:700">{v}</div>
        </div>
        '''

    event_rows = ""
    for ev in sorted(EVENTS, key=lambda e: e["day"], reverse=True):
        ty = INTERRUPTION_TYPES[ev["type"]]
        event_rows += f'''
        <tr>
          <td style="color:#64748b">Day -{90 - ev["day"]}</td>
          <td><span style="background:{ty["color"]}22;color:{ty["color"]};padding:2px 8px;border-radius:4px;font-size:11px">{ty["label"]}</span></td>
          <td style="color:#94a3b8;font-family:monospace;font-size:12px">{ev["job"]}</td>
          <td style="color:#e2e8f0;text-align:center">{ev["step_lost"]}</td>
          <td style="color:#38bdf8;text-align:center">{ev["checkpoint_step"]}</td>
          <td style="color:#22c55e;text-align:center">{ev["recovery_min"]} min</td>
        </tr>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Training Resumption Manager — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .badge {{ display:inline-block; background:#C74634; color:#fff; font-size:11px; padding:2px 10px; border-radius:999px; margin-left:10px; vertical-align:middle; }}
    .section {{ margin-bottom: 32px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
    .chart-wrap {{ border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #64748b; font-weight: 600; text-align: left; padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #1e293b40; }}
    footer {{ color: #334155; font-size: 11px; text-align: center; margin-top: 32px; }}
  </style>
</head>
<body>
  <h1>Training Resumption Manager <span class="badge">port 8327</span></h1>
  <div class="subtitle">Automatic resumption after OOM / spot preemption / network loss — zero complete restarts in 90 days</div>

  <div class="section">
    <div class="section-title">Resumption Metrics (90-day window)</div>
    <div class="metrics">
      {metric_cards}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Interruption Event Log — 90-Day Timeline</div>
    <div class="chart-wrap">{svg1}</div>
  </div>

  <div class="section">
    <div class="section-title">Recovery Efficiency — Progress Lost per Interruption Type</div>
    <div class="chart-wrap">{svg2}</div>
  </div>

  <div class="section">
    <div class="section-title">Event Log</div>
    <table>
      <thead><tr>
        <th>Date</th><th>Type</th><th>Job</th><th>Steps Lost</th><th>Resume Checkpoint</th><th>Recovery Time</th>
      </tr></thead>
      <tbody>
        {event_rows}
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; Training Resumption Manager &mdash; Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</footer>
</body>
</html>'''


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Training Resumption Manager",
        description="Manages automatic training job resumption after interruptions on OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/events")
    async def api_events():
        return {"events": EVENTS, "total": len(EVENTS)}

    @app.get("/api/metrics")
    async def api_metrics():
        return {"metrics": METRICS, "interruption_types": INTERRUPTION_TYPES}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "training_resumption_manager", "port": 8327}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8327)
    else:
        print("FastAPI not available — starting stdlib HTTP server on port 8327")
        HTTPServer(("0.0.0.0", 8327), Handler).serve_forever()
