"""deployment_health_scorer.py — FastAPI service on port 8215.

Computes a composite health score for production robot model deployments.
Serves a dark-theme HTML dashboard with a gauge SVG (current score) and a
timeline SVG (30-day trend with incident markers).
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data / scoring
# ---------------------------------------------------------------------------

HEALTH_DIMENSIONS = {
    "Latency SLA":     {"score": 92, "weight": 0.25, "color": "#38bdf8"},
    "Error Rate":      {"score": 98, "weight": 0.25, "color": "#4ade80"},
    "Model Freshness": {"score": 81, "weight": 0.20, "color": "#facc15"},
    "Data Drift":      {"score": 85, "weight": 0.15, "color": "#fb923c"},
    "GPU Utilization": {"score": 89, "weight": 0.15, "color": "#a78bfa"},
}

CURRENT_SCORE = 87  # composite (matches weighted sum)

# Incidents: (day_offset_from_today, label, severity)  — offset is negative = past
INCIDENTS = [
    (-25, "Latency spike",     "warn"),
    (-14, "Model stale 3d",    "crit"),
    (-4,  "GPU OOM flash",     "warn"),
]

# Derived KPIs
MTTR_HOURS = 1.4
INCIDENT_FREQ = len(INCIDENTS)  # in last 30 days
SCORE_DELTA = +3  # vs last week


def generate_trend(days: int = 30) -> list:
    """Simulate daily health scores for the past `days` days."""
    random.seed(7)
    score = 84.0
    series = []
    incident_offsets = {inc[0] for inc in INCIDENTS}
    for d in range(-days, 1):
        # Dip on incident days, recover gradually
        if d in incident_offsets:
            inc = next(i for i in INCIDENTS if i[0] == d)
            drop = 18 if inc[2] == "crit" else 9
            score = max(score - drop, 40)
        else:
            # Drift back toward target
            score += (CURRENT_SCORE - score) * 0.12 + random.uniform(-1.2, 1.2)
            score = min(max(score, 40), 100)
        series.append(round(score, 1))
    return series


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_gauge(score: int) -> str:
    """Semicircular arc gauge showing composite health score 0-100."""
    W, H = 320, 200
    cx, cy = 160, 160
    r_outer, r_inner = 110, 76

    def color_for(s: int) -> str:
        if s >= 85:
            return "#4ade80"
        if s >= 65:
            return "#facc15"
        return "#C74634"

    def arc_path(r: float, start_deg: float, end_deg: float) -> str:
        """SVG arc path (large-arc auto-detected)."""
        def pt(angle_deg):
            a = math.radians(angle_deg)
            return cx + r * math.cos(a), cy + r * math.sin(a)

        x1, y1 = pt(start_deg)
        x2, y2 = pt(end_deg)
        span = abs(end_deg - start_deg)
        large = 1 if span > 180 else 0
        sweep = 1 if end_deg > start_deg else 0
        return f"M {x1:.2f},{y1:.2f} A {r},{r} 0 {large},{sweep} {x2:.2f},{y2:.2f}"

    # Gauge spans from 210° to 330° (= -150° to -30° from right, i.e. left-bottom to right-bottom)
    START_DEG = 210
    END_DEG   = 330
    total_span = END_DEG - START_DEG  # 120 deg for 0→100

    # Background arc (full range)
    bg_path_outer = arc_path(r_outer, START_DEG, END_DEG)
    bg_path_inner = arc_path(r_inner, END_DEG, START_DEG)

    # Filled arc (0 → score)
    fill_end = START_DEG + (score / 100) * total_span
    fill_color = color_for(score)
    fill_path_outer = arc_path(r_outer, START_DEG, fill_end)
    fill_path_inner = arc_path(r_inner, fill_end, START_DEG)

    # Tick marks
    ticks = ""
    for pct in range(0, 101, 10):
        angle = math.radians(START_DEG + pct * total_span / 100)
        x1t = cx + (r_outer - 2) * math.cos(angle)
        y1t = cy + (r_outer - 2) * math.sin(angle)
        x2t = cx + (r_outer + 8) * math.cos(angle)
        y2t = cy + (r_outer + 8) * math.sin(angle)
        ticks += (
            f'<line x1="{x1t:.1f}" y1="{y1t:.1f}" x2="{x2t:.1f}" y2="{y2t:.1f}" '
            f'stroke="#334155" stroke-width="2"/>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#1e293b;border-radius:8px">'
        # background donut
        f'<path d="{bg_path_outer} L {cx + r_inner * math.cos(math.radians(END_DEG)):.2f},'
        f'{cy + r_inner * math.sin(math.radians(END_DEG)):.2f} {bg_path_inner} Z" '
        f'fill="#0f172a"/>'
        # filled arc
        f'<path d="{fill_path_outer} L {cx + r_inner * math.cos(math.radians(fill_end)):.2f},'
        f'{cy + r_inner * math.sin(math.radians(fill_end)):.2f} {fill_path_inner} Z" '
        f'fill="{fill_color}" opacity="0.9"/>'
        + ticks +
        # Center text
        f'<text x="{cx}" y="{cy-10}" fill="{fill_color}" font-size="42" font-weight="700" '
        f'text-anchor="middle" dominant-baseline="auto">{score}</text>'
        f'<text x="{cx}" y="{cy+16}" fill="#94a3b8" font-size="13" '
        f'text-anchor="middle">Health Score</text>'
        f'<text x="{cx}" y="{cy+34}" fill="#64748b" font-size="11" '
        f'text-anchor="middle">Production · GR00T-3B</text>'
        # Range labels
        f'<text x="{cx + (r_outer+14)*math.cos(math.radians(START_DEG)):.0f}" '
        f'y="{cy + (r_outer+14)*math.sin(math.radians(START_DEG)):.0f}" '
        f'fill="#475569" font-size="11" text-anchor="middle">0</text>'
        f'<text x="{cx + (r_outer+14)*math.cos(math.radians(END_DEG)):.0f}" '
        f'y="{cy + (r_outer+14)*math.sin(math.radians(END_DEG)):.0f}" '
        f'fill="#475569" font-size="11" text-anchor="middle">100</text>'
        '</svg>'
    )


def svg_timeline(trend: list) -> str:
    """Line chart of 30-day health score trend with incident markers."""
    W, H = 560, 240
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    n = len(trend)
    y_min, y_max = 0, 100

    def px(i: int) -> float:
        return pad_l + (i / (n - 1)) * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - (v - y_min) / (y_max - y_min) * plot_h

    # Area fill
    pts_area = f"{px(0):.1f},{py(0):.1f} "
    pts_area += " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(trend))
    pts_area += f" {px(n-1):.1f},{py(0):.1f}"

    # Line
    pts_line = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(trend))

    # SLA threshold at 80
    sla_y = py(80)
    sla_line = (
        f'<line x1="{pad_l}" y1="{sla_y:.1f}" x2="{pad_l+plot_w}" y2="{sla_y:.1f}" '
        f'stroke="#C74634" stroke-width="1.2" stroke-dasharray="6,4"/>'
        f'<text x="{pad_l+plot_w-2}" y="{sla_y-5:.1f}" fill="#C74634" '
        f'font-size="10" text-anchor="end">SLA min 80</text>'
    )

    # Incident markers
    today_idx = n - 1
    markers = ""
    for offset, label, severity in INCIDENTS:
        idx = today_idx + offset  # offset is negative
        if 0 <= idx < n:
            ix, iy = px(idx), py(trend[idx])
            mc = "#C74634" if severity == "crit" else "#facc15"
            markers += (
                f'<line x1="{ix:.1f}" y1="{iy-6:.1f}" x2="{ix:.1f}" y2="{iy-22:.1f}" '
                f'stroke="{mc}" stroke-width="1.5"/>'
                f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="5" fill="{mc}" opacity="0.9"/>'
                f'<text x="{ix:.1f}" y="{iy-26:.1f}" fill="{mc}" font-size="9" '
                f'text-anchor="middle">{label}</text>'
            )

    # X-axis date labels
    today = datetime.utcnow().date()
    xlabels = ""
    for days_ago in (30, 20, 10, 0):
        idx = today_idx - days_ago
        if 0 <= idx < n:
            d = today - timedelta(days=days_ago)
            xlabels += (
                f'<text x="{px(idx):.1f}" y="{pad_t+plot_h+16}" fill="#94a3b8" '
                f'font-size="10" text-anchor="middle">{d.strftime("%m/%d")}</text>'
            )

    # Y ticks
    yticks = ""
    for v in (0, 25, 50, 75, 100):
        y = py(v)
        yticks += (
            f'<text x="{pad_l-6}" y="{y:.0f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end" dominant-baseline="middle">{v}</text>'
            f'<line x1="{pad_l}" y1="{y:.0f}" x2="{pad_l+plot_w}" y2="{y:.0f}" '
            f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>'
        )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#1e293b;border-radius:8px">'
        + yticks + axes + sla_line
        + f'<polygon points="{pts_area}" fill="#38bdf8" opacity="0.08"/>'
        + f'<polyline points="{pts_line}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>'
        + markers + xlabels
        + f'<text x="{pad_l+plot_w//2}" y="{H-4}" fill="#64748b" font-size="11" text-anchor="middle">Date (UTC)</text>'
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    trend = generate_trend(30)
    gauge = svg_gauge(CURRENT_SCORE)
    timeline = svg_timeline(trend)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Dimension rows
    dim_rows = ""
    for name, cfg in HEALTH_DIMENSIONS.items():
        pct = cfg["score"]
        color = cfg["color"]
        dim_rows += (
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
            f'<div style="width:130px;font-size:12px;color:#94a3b8;flex-shrink:0">{name}</div>'
            f'<div style="flex:1;background:#0f172a;border-radius:999px;height:8px">'
            f'<div style="width:{pct}%;background:{color};border-radius:999px;height:100%"></div>'
            f'</div>'
            f'<div style="width:36px;text-align:right;font-size:12px;color:{color};font-weight:600">{pct}%</div>'
            f'</div>'
        )

    def kpi(label, val, sub=""):
        sub_html = f'<div style="font-size:10px;color:#64748b;margin-top:2px">{sub}</div>' if sub else ""
        return (
            f'<div style="background:#1e293b;border-radius:8px;padding:14px 18px;'
            f'min-width:130px;text-align:center">'
            f'<div style="font-size:20px;font-weight:700;color:#38bdf8">{val}</div>'
            f'<div style="font-size:11px;color:#94a3b8;margin-top:4px">{label}</div>'
            + sub_html + '</div>'
        )

    kpis = (
        kpi("Composite Score", CURRENT_SCORE, f"+{SCORE_DELTA} vs last week")
        + kpi("MTTR", f"{MTTR_HOURS}h", "mean time to recover")
        + kpi("Incidents / 30d", INCIDENT_FREQ, "")
        + kpi("Latency SLA", "92%", "p95 < 250ms")
        + kpi("Error Rate", "0.21%", "last 24h")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Deployment Health Scorer — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      padding: 24px;
    }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; }}
    h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8;
          margin: 24px 0 10px; text-transform: uppercase; letter-spacing: .05em; }}
    .badge {{
      background: #C74634;
      color: #fff;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      margin-left: 10px;
      vertical-align: middle;
    }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }}
    .ts {{ font-size: 11px; color: #475569; }}
    .kpis {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .charts {{
      display: grid;
      grid-template-columns: 1fr 1.7fr;
      gap: 20px;
      align-items: start;
    }}
    .card {{
      background: #1e293b;
      border-radius: 10px;
      padding: 16px;
    }}
    .card-title {{
      font-size: 13px;
      font-weight: 600;
      color: #cbd5e1;
      margin-bottom: 12px;
    }}
    @media (max-width: 700px) {{
      .charts {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Deployment Health Scorer <span class="badge">port 8215</span></h1>
      <p style="font-size:13px;color:#64748b;margin-top:4px">Production · GR00T-3B · OCI A100</p>
    </div>
    <div class="ts">{ts}</div>
  </div>

  <h2>Key Metrics</h2>
  <div class="kpis">{kpis}</div>

  <div class="charts">
    <div>
      <div class="card">
        <div class="card-title">Composite Health Score</div>
        {gauge}
      </div>
      <div class="card" style="margin-top:16px">
        <div class="card-title">Health Dimensions</div>
        {dim_rows}
      </div>
    </div>
    <div class="card">
      <div class="card-title">30-Day Health Score Trend</div>
      {timeline}
    </div>
  </div>

  <p style="font-size:11px;color:#334155;margin-top:24px;text-align:center">
    OCI Robot Cloud · Deployment Health Scorer · port 8215
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (with stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Deployment Health Scorer",
        description="Composite health score for production robot model deployments.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "deployment_health_scorer", "port": 8215}

    @app.get("/api/score")
    async def score():
        """Return current composite health score and dimension breakdown."""
        composite = sum(
            cfg["score"] * cfg["weight"]
            for cfg in HEALTH_DIMENSIONS.values()
        )
        return {
            "composite_score": round(composite, 1),
            "score_delta_vs_last_week": SCORE_DELTA,
            "mttr_hours": MTTR_HOURS,
            "incident_count_30d": INCIDENT_FREQ,
            "dimensions": {
                name: {"score": cfg["score"], "weight": cfg["weight"]}
                for name, cfg in HEALTH_DIMENSIONS.items()
            },
        }

    @app.get("/api/trend")
    async def trend():
        """Return 30-day health score trend and incident markers."""
        today = datetime.utcnow().date()
        data = generate_trend(30)
        dates = [
            (today - timedelta(days=30 - i)).isoformat()
            for i in range(len(data))
        ]
        incidents_out = [
            {
                "date": (today + timedelta(days=offset)).isoformat(),
                "label": label,
                "severity": severity,
            }
            for offset, label, severity in INCIDENTS
        ]
        return {"dates": dates, "scores": data, "incidents": incidents_out}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
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
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8215)
    else:
        print("[deployment_health_scorer] FastAPI not found — using stdlib on port 8215")
        with socketserver.TCPServer(("", 8215), _Handler) as srv:
            srv.serve_forever()
