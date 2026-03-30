"""Workspace Collision Monitor — FastAPI service on port 8294.

Monitors and classifies collision events in robot workspace during
training and deployment. Provides spatial heatmaps, severity timelines,
and trend analysis.
"""

import math
import random
import json
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

SEVERITY_LABELS = ["minor_contact", "soft_collision", "hard_collision", "e_stop"]

# 30-day history: totals must be 47 minor, 8 soft, 2 hard, 0 e-stops
# Hard collisions both in week 1 (days 1-7)
def _generate_daily_history():
    """Return list of 30 dicts with daily collision counts."""
    days = []
    minor_remaining = 47
    soft_remaining = 8
    hard_remaining = 2
    for d in range(30):
        day_idx = d  # 0=oldest, 29=today
        is_week1 = day_idx < 7
        # Hard collisions only in week 1
        if hard_remaining > 0 and is_week1:
            hard = 1 if day_idx in (2, 5) else 0
            if hard:
                hard_remaining -= hard
        else:
            hard = 0
        # Soft collisions more likely early
        soft_budget = max(0, soft_remaining)
        if soft_budget > 0:
            prob = 0.25 if is_week1 else 0.05
            soft = 1 if random.random() < prob and soft_remaining > 0 else 0
            soft_remaining -= soft
        else:
            soft = 0
        # Minor collisions spread across all days, tapering
        minor_rate = max(0, 3 - day_idx * 0.05)
        minor = int(random.gauss(minor_rate, 0.5))
        minor = max(0, min(minor, minor_remaining))
        minor_remaining -= minor
        days.append({"minor": minor, "soft": soft, "hard": hard, "estop": 0})
    # Distribute any remaining minor evenly in early days
    i = 0
    while minor_remaining > 0:
        days[i % 15]["minor"] += 1
        minor_remaining -= 1
        i += 1
    return days

DAILY_HISTORY = _generate_daily_history()

# Spatial collision zones (x, y in metres, relative to robot base)
COLLISION_SPOTS = [
    {"x": 0.40, "y": 0.20, "freq": 18, "label": "Cube edge"},
    {"x": 0.30, "y": -0.10, "freq": 11, "label": "Shelf corner"},
    {"x": 0.55, "y": 0.05, "freq": 7, "label": "Drop zone rim"},
    {"x": 0.20, "y": 0.35, "freq": 5, "label": "Left boundary"},
    {"x": 0.10, "y": -0.25, "freq": 3, "label": "Rear obstacle"},
    {"x": 0.60, "y": -0.20, "freq": 2, "label": "Right wall"},
    {"x": 0.45, "y": -0.35, "freq": 1, "label": "Far corner"},
]

def _collision_rate():
    total = sum(d["minor"] + d["soft"] + d["hard"] for d in DAILY_HISTORY)
    # Assume avg 40 episodes/day
    return round(total / (30 * 40) * 100, 2)

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _build_heatmap_svg() -> str:
    """Top-down workspace heatmap showing collision frequency by location."""
    W, H = 500, 400
    # Workspace: x in [-0.1, 0.7], y in [-0.5, 0.5] metres
    # Map to SVG coords
    PAD = 50
    def to_svg(xm, ym):
        sx = PAD + (xm + 0.1) / 0.8 * (W - 2 * PAD)
        sy = PAD + (0.5 - ym) / 1.0 * (H - 2 * PAD)
        return sx, sy

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Background workspace rectangle
    bx, by = to_svg(-0.1, 0.5)
    ex, ey = to_svg(0.7, -0.5)
    parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{ex-bx:.1f}" height="{ey-by:.1f}" fill="#0f2a1a" stroke="#38bdf8" stroke-width="1.5" rx="4"/>')

    # Safe zone (low frequency)
    parts.append(f'<text x="{W//2}" y="20" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Workspace Collision Heatmap (Top-Down)</text>')

    # Trajectory lines
    # Common trajectory: base -> target
    bx0, by0 = to_svg(0.0, 0.0)
    tx1, ty1 = to_svg(0.40, 0.20)
    tx2, ty2 = to_svg(0.30, -0.10)
    tx3, ty3 = to_svg(0.55, 0.05)
    parts.append(f'<line x1="{bx0:.1f}" y1="{by0:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/>')
    parts.append(f'<line x1="{bx0:.1f}" y1="{by0:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/>')
    parts.append(f'<line x1="{bx0:.1f}" y1="{by0:.1f}" x2="{tx3:.1f}" y2="{ty3:.1f}" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.4"/>')

    # Collision spots as radial gradients simulated by concentric circles
    max_freq = max(s["freq"] for s in COLLISION_SPOTS)
    for spot in COLLISION_SPOTS:
        sx, sy = to_svg(spot["x"], spot["y"])
        ratio = spot["freq"] / max_freq
        r = 10 + ratio * 28
        if ratio > 0.7:
            color = "#ef4444"  # red hotspot
        elif ratio > 0.35:
            color = "#f59e0b"  # yellow caution
        else:
            color = "#22c55e"  # green safe
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r:.1f}" fill="{color}" opacity="0.25"/>')
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r*0.5:.1f}" fill="{color}" opacity="0.45"/>')
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" fill="{color}" opacity="0.9"/>')
        parts.append(f'<text x="{sx+7:.1f}" y="{sy-5:.1f}" fill="#e2e8f0" font-size="9" font-family="monospace">{spot["freq"]}</text>')

    # Robot base marker
    parts.append(f'<circle cx="{bx0:.1f}" cy="{by0:.1f}" r="8" fill="#C74634" opacity="0.9"/>')
    parts.append(f'<text x="{bx0+12:.1f}" y="{by0+4:.1f}" fill="#fca5a5" font-size="10" font-family="monospace">Base</text>')

    # Axes labels
    ax_y = ey + 15
    parts.append(f'<text x="{(bx+ex)/2:.1f}" y="{ax_y:.1f}" fill="#64748b" font-size="10" text-anchor="middle" font-family="monospace">X axis (m)</text>')
    parts.append(f'<text x="{bx-30:.1f}" y="{(by+ey)/2:.1f}" fill="#64748b" font-size="10" text-anchor="middle" font-family="monospace" transform="rotate(-90,{bx-30:.1f},{(by+ey)/2:.1f})">Y axis (m)</text>')

    # Legend
    legend_x = W - 130
    parts.append(f'<rect x="{legend_x}" y="{H-85}" width="120" height="78" fill="#1e293b" stroke="#334155" rx="4"/>')
    for i, (col, lbl) in enumerate([("#22c55e", "Safe (low)"), ("#f59e0b", "Caution"), ("#ef4444", "Hotspot")]):
        cy = H - 70 + i * 22
        parts.append(f'<circle cx="{legend_x+12}" cy="{cy}" r="6" fill="{col}" opacity="0.8"/>')
        parts.append(f'<text x="{legend_x+24}" y="{cy+4}" fill="#cbd5e1" font-size="10" font-family="monospace">{lbl}</text>')

    parts.append('</svg>')
    return ''.join(parts)


def _build_severity_timeline_svg() -> str:
    """Stacked bar chart of collision severity over 30 days."""
    W, H = 700, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 30, 50
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    n_days = len(DAILY_HISTORY)
    bar_w = plot_w / n_days - 1

    max_total = max(d["minor"] + d["soft"] + d["hard"] + d["estop"] for d in DAILY_HISTORY)
    max_total = max(max_total, 1)

    def ys(count, base_count):
        """SVG y for a bar segment starting at base_count."""
        top_y = PAD_T + plot_h - (base_count + count) / max_total * plot_h
        seg_h = count / max_total * plot_h
        return top_y, seg_h

    colors = {"minor": "#38bdf8", "soft": "#f59e0b", "hard": "#ef4444", "estop": "#C74634"}

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    parts.append(f'<text x="{W//2}" y="20" fill="#94a3b8" font-size="12" text-anchor="middle" font-family="monospace">Collision Severity Timeline — 30 Days</text>')

    # Grid lines
    for tick in [1, 2, 3, 4]:
        gy = PAD_T + plot_h - tick / max_total * plot_h
        parts.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="#334155" stroke-width="0.5"/>')
        parts.append(f'<text x="{PAD_L-4}" y="{gy+4:.1f}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{tick}</text>')

    for i, day in enumerate(DAILY_HISTORY):
        bx = PAD_L + i * (bar_w + 1)
        base = 0
        for sev in ["minor", "soft", "hard", "estop"]:
            cnt = day[sev]
            if cnt > 0:
                top_y, seg_h = ys(cnt, base)
                parts.append(f'<rect x="{bx:.1f}" y="{top_y:.1f}" width="{bar_w:.1f}" height="{seg_h:.1f}" fill="{colors[sev]}" opacity="0.85"/>')
                base += cnt

        # Week separator
        if i % 7 == 0 and i > 0:
            lx = bx - 0.5
            parts.append(f'<line x1="{lx:.1f}" y1="{PAD_T}" x2="{lx:.1f}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>')
            parts.append(f'<text x="{lx}" y="{PAD_T+plot_h+14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">W{i//7+1}</text>')

    # Axes
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>')
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{W-PAD_R}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>')

    # Legend
    lx = PAD_L
    for sev, col in colors.items():
        parts.append(f'<rect x="{lx}" y="{H-18}" width="10" height="10" fill="{col}" rx="2"/>')
        parts.append(f'<text x="{lx+13}" y="{H-9}" fill="#94a3b8" font-size="10" font-family="monospace">{sev}</text>')
        lx += 130

    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    heatmap = _build_heatmap_svg()
    timeline = _build_severity_timeline_svg()

    total_minor = sum(d["minor"] for d in DAILY_HISTORY)
    total_soft = sum(d["soft"] for d in DAILY_HISTORY)
    total_hard = sum(d["hard"] for d in DAILY_HISTORY)
    total_estop = sum(d["estop"] for d in DAILY_HISTORY)
    rate = _collision_rate()

    # Recent trend: compare last 7 days vs days 8-14
    recent7 = sum(d["hard"] + d["soft"] for d in DAILY_HISTORY[-7:])
    prev7 = sum(d["hard"] + d["soft"] for d in DAILY_HISTORY[-14:-7])
    trend = "IMPROVING" if recent7 <= prev7 else "DEGRADING"
    trend_color = "#22c55e" if trend == "IMPROVING" else "#ef4444"

    top_spot = max(COLLISION_SPOTS, key=lambda s: s["freq"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workspace Collision Monitor | Port 8294</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.8rem; margin-bottom: 20px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; }}
  .card .val {{ font-size: 1.6rem; font-weight: bold; color: #38bdf8; }}
  .card .val.warn {{ color: #f59e0b; }}
  .card .val.crit {{ color: #ef4444; }}
  .card .lbl {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  @media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
  .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px; }}
  .spots-table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  .spots-table th {{ color: #38bdf8; border-bottom: 1px solid #334155; padding: 6px 8px; text-align: left; }}
  .spots-table td {{ padding: 5px 8px; border-bottom: 1px solid #1e293b; }}
  .spots-table tr:hover td {{ background: #1e293b; }}
  .trend {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; background: #0f2a1a; color: {trend_color}; border: 1px solid {trend_color}; }}
  footer {{ color: #334155; font-size: 0.72rem; margin-top: 24px; }}
</style>
</head>
<body>
<h1>Workspace Collision Monitor</h1>
<p class="subtitle">Port 8294 &mdash; Real-time collision classification &amp; spatial analysis</p>

<div class="metrics">
  <div class="card"><div class="val">{rate}</div><div class="lbl">Collisions / 100 eps</div></div>
  <div class="card"><div class="val">{total_minor}</div><div class="lbl">Minor contacts (30d)</div></div>
  <div class="card"><div class="val warn">{total_soft}</div><div class="lbl">Soft collisions (30d)</div></div>
  <div class="card"><div class="val crit">{total_hard}</div><div class="lbl">Hard collisions (30d)</div></div>
  <div class="card"><div class="val">{total_estop}</div><div class="lbl">E-stops (30d)</div></div>
  <div class="card"><div class="val" style="font-size:1.1rem">{top_spot['label']}</div><div class="lbl">Top hotspot (x={top_spot['x']}m, y={top_spot['y']}m)</div></div>
  <div class="card"><div class="val" style="color:{trend_color};font-size:1.1rem">{trend}</div><div class="lbl">Safety trend (7d vs prev 7d)</div></div>
</div>

<div class="charts">
  <div class="chart-box">
    <h2>Spatial Collision Heatmap</h2>
    {heatmap}
  </div>
  <div class="chart-box">
    <h2>Severity Timeline (30 Days)</h2>
    {timeline}
  </div>
</div>

<div class="chart-box" style="margin-bottom:20px">
  <h2>Collision Hotspot Details</h2>
  <table class="spots-table">
    <thead><tr><th>Location</th><th>X (m)</th><th>Y (m)</th><th>Events</th><th>Risk Level</th></tr></thead>
    <tbody>
    {''.join(f"<tr><td>{s['label']}</td><td>{s['x']}</td><td>{s['y']}</td><td>{s['freq']}</td><td style='color:{'#ef4444' if s['freq']>14 else '#f59e0b' if s['freq']>5 else '#22c55e'}'>{('HIGH' if s['freq']>14 else 'MEDIUM' if s['freq']>5 else 'LOW')}</td></tr>" for s in sorted(COLLISION_SPOTS, key=lambda x: -x['freq']))}
    </tbody>
  </table>
</div>

<footer>OCI Robot Cloud &mdash; Workspace Collision Monitor v2.0 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app / stdlib fallback
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Workspace Collision Monitor", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "workspace_collision_monitor", "port": 8294}

    @app.get("/metrics")
    async def metrics():
        return {
            "collision_rate_per_100_eps": _collision_rate(),
            "totals_30d": {
                "minor_contact": sum(d["minor"] for d in DAILY_HISTORY),
                "soft_collision": sum(d["soft"] for d in DAILY_HISTORY),
                "hard_collision": sum(d["hard"] for d in DAILY_HISTORY),
                "e_stop": 0,
            },
            "top_hotspot": max(COLLISION_SPOTS, key=lambda s: s["freq"]),
            "safety_trend": "improving",
            "hard_collisions_last_3_weeks": 0,
        }

    @app.get("/history")
    async def history():
        return {"days": DAILY_HISTORY, "count": len(DAILY_HISTORY)}

    @app.get("/hotspots")
    async def hotspots():
        return sorted(COLLISION_SPOTS, key=lambda s: -s["freq"])

else:
    # Stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8294)
    else:
        print("FastAPI not available — using stdlib HTTP server on port 8294")
        HTTPServer(("0.0.0.0", 8294), _Handler).serve_forever()
