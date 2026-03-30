"""fleet_autoscaler_v2.py — Advanced predictive fleet autoscaler for OCI GPU nodes (port 8224)."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

DAYS = 7
HOURS_PER_DAY = 24
TOTAL_HOURS = DAYS * HOURS_PER_DAY  # 168

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def _demand_curve(hour_of_day: int, day_of_week: int) -> float:
    """Simulate GPU demand 0-1 based on time-of-day and weekday."""
    is_weekend = day_of_week >= 5
    if is_weekend:
        base = 0.18 + 0.10 * math.sin(math.pi * hour_of_day / 23)
    else:
        # Business hours peak
        if 8 <= hour_of_day <= 18:
            base = 0.55 + 0.35 * math.sin(math.pi * (hour_of_day - 8) / 10)
        else:
            base = 0.15 + 0.10 * math.sin(math.pi * hour_of_day / 23)
    return min(1.0, max(0.0, base + random.gauss(0, 0.04)))

def build_time_series():
    actual, predicted, scale_events = [], [], []
    base_time = datetime(2026, 3, 23, 0, 0)  # Monday
    for h in range(TOTAL_HOURS):
        dow = (h // 24) % 7
        hod = h % 24
        dem = _demand_curve(hod, dow)
        actual.append(dem)
        # Predictive model sees 15 min ahead (1/4 hour)
        pred_hod = (hod + 0.25) % 24
        pred = _demand_curve(pred_hod, dow) + random.gauss(0, 0.02)
        predicted.append(min(1.0, max(0.0, pred)))

        # Scale events: reactive triggers at 0.72, predictive at 0.65
        if h > 0:
            prev = actual[h-1]
            if prev < 0.65 and dem >= 0.65 and dem < 0.72:
                scale_events.append({"h": h, "type": "predictive_up"})
            elif prev < 0.72 and dem >= 0.72:
                scale_events.append({"h": h, "type": "reactive_up"})
            elif prev >= 0.40 and dem < 0.30:
                scale_events.append({"h": h, "type": "scale_down"})
    return actual, predicted, scale_events

def build_cost_savings():
    rows = []
    for i, day in enumerate(DAY_NAMES):
        is_weekend = i >= 5
        if is_weekend:
            reactive = round(random.uniform(12, 20), 1)
            predictive = round(reactive * random.uniform(0.55, 0.68), 1)
        else:
            reactive = round(random.uniform(85, 120), 1)
            predictive = round(reactive * random.uniform(0.74, 0.80), 1)
        rows.append({"day": day, "reactive": reactive, "predictive": predictive,
                     "savings": round(reactive - predictive, 1)})
    return rows

ACTUAL, PREDICTED, SCALE_EVENTS = build_time_series()
COST_DATA = build_cost_savings()

total_reactive = sum(r["reactive"] for r in COST_DATA)
total_predictive = sum(r["predictive"] for r in COST_DATA)
AVG_DAILY_SAVING = round((total_reactive - total_predictive) / DAYS, 1)
OVERALL_SAVINGS_PCT = round((total_reactive - total_predictive) / total_reactive * 100, 1)

# MAPE
mape_vals = [abs(ACTUAL[i] - PREDICTED[i]) / max(ACTUAL[i], 0.01) for i in range(TOTAL_HOURS)]
MAPE = round(sum(mape_vals) / len(mape_vals) * 100, 2)

SCALE_UP_LEAD_MIN = 14.8  # avg minutes earlier than reactive

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _svg_line_chart() -> str:
    W, H = 900, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 30, 20, 50
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B
    n = TOTAL_HOURS

    def px(i): return PAD_L + i / (n - 1) * cw
    def py(v): return PAD_T + (1 - v) * ch

    # Grid lines
    grid = ""
    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = py(tick)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{tick:.2f}</text>'

    # Day separators
    day_sep = ""
    for d in range(1, DAYS):
        x = px(d * 24)
        day_sep += f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T+ch}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
        day_sep += f'<text x="{px(d*24 - 12):.1f}" y="{PAD_T+ch+18}" fill="#64748b" font-size="11" text-anchor="middle">{DAY_NAMES[d-1]}</text>'
    day_sep += f'<text x="{px(TOTAL_HOURS - 12):.1f}" y="{PAD_T+ch+18}" fill="#64748b" font-size="11" text-anchor="middle">{DAY_NAMES[6]}</text>'

    # Predicted line
    pts_pred = " ".join(f"{px(i):.1f},{py(PREDICTED[i]):.1f}" for i in range(n))
    # Actual line
    pts_act = " ".join(f"{px(i):.1f},{py(ACTUAL[i]):.1f}" for i in range(n))

    # Scale event markers
    markers = ""
    for ev in SCALE_EVENTS:
        x = px(ev["h"])
        y = py(ACTUAL[ev["h"]])
        if ev["type"] == "predictive_up":
            # Green up-triangle
            markers += f'<polygon points="{x:.1f},{y-10:.1f} {x-6:.1f},{y+2:.1f} {x+6:.1f},{y+2:.1f}" fill="#22c55e" opacity="0.9"/>'
        elif ev["type"] == "reactive_up":
            # Orange up-triangle
            markers += f'<polygon points="{x:.1f},{y-10:.1f} {x-6:.1f},{y+2:.1f} {x+6:.1f},{y+2:.1f}" fill="#f97316" opacity="0.9"/>'
        else:
            # Sky-blue down-triangle
            markers += f'<polygon points="{x:.1f},{y+10:.1f} {x-6:.1f},{y-2:.1f} {x+6:.1f},{y-2:.1f}" fill="#38bdf8" opacity="0.9"/>'

    # Legend
    legend = (
        f'<rect x="{PAD_L}" y="{H-14}" width="14" height="3" fill="#38bdf8"/>'
        f'<text x="{PAD_L+18}" y="{H-10}" fill="#94a3b8" font-size="11">Predicted demand</text>'
        f'<rect x="{PAD_L+140}" y="{H-14}" width="14" height="3" fill="#C74634"/>'
        f'<text x="{PAD_L+158}" y="{H-10}" fill="#94a3b8" font-size="11">Actual demand</text>'
        f'<polygon points="{PAD_L+270},{H-16} {PAD_L+264},{H-8} {PAD_L+276},{H-8}" fill="#22c55e"/>'
        f'<text x="{PAD_L+280}" y="{H-10}" fill="#94a3b8" font-size="11">Predictive scale-up</text>'
        f'<polygon points="{PAD_L+420},{H-16} {PAD_L+414},{H-8} {PAD_L+426},{H-8}" fill="#f97316"/>'
        f'<text x="{PAD_L+430}" y="{H-10}" fill="#94a3b8" font-size="11">Reactive scale-up</text>'
        f'<polygon points="{PAD_L+560},{H-8} {PAD_L+554},{H-16} {PAD_L+566},{H-16}" fill="#38bdf8"/>'
        f'<text x="{PAD_L+570}" y="{H-10}" fill="#94a3b8" font-size="11">Scale-down</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>'
        f'{grid}{day_sep}'
        f'<polyline points="{pts_pred}" fill="none" stroke="#38bdf8" stroke-width="1.5" opacity="0.75"/>'
        f'<polyline points="{pts_act}" fill="none" stroke="#C74634" stroke-width="2"/>'
        f'{markers}{legend}'
        f'<text x="{W//2}" y="{PAD_T+12}" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">GPU Demand: Actual vs Predicted (7-day, hourly)</text>'
        f'</svg>'
    )

def _svg_cost_chart() -> str:
    W, H = 700, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 30, 55
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B

    max_val = max(r["reactive"] for r in COST_DATA) * 1.1
    BAR_GROUP = cw / len(COST_DATA)
    BAR_W = BAR_GROUP * 0.35

    bars = ""
    for i, row in enumerate(COST_DATA):
        cx = PAD_L + i * BAR_GROUP + BAR_GROUP * 0.15
        # Reactive bar
        rh = row["reactive"] / max_val * ch
        ry = PAD_T + ch - rh
        bars += f'<rect x="{cx:.1f}" y="{ry:.1f}" width="{BAR_W:.1f}" height="{rh:.1f}" fill="#f97316" rx="2"/>'
        bars += f'<text x="{cx + BAR_W/2:.1f}" y="{ry-4:.1f}" fill="#f97316" font-size="10" text-anchor="middle">${row["reactive"]}</text>'
        # Predictive bar
        ph = row["predictive"] / max_val * ch
        py2 = PAD_T + ch - ph
        px2 = cx + BAR_W + 2
        bars += f'<rect x="{px2:.1f}" y="{py2:.1f}" width="{BAR_W:.1f}" height="{ph:.1f}" fill="#22c55e" rx="2"/>'
        bars += f'<text x="{px2 + BAR_W/2:.1f}" y="{py2-4:.1f}" fill="#22c55e" font-size="10" text-anchor="middle">${row["predictive"]}</text>'
        # Savings annotation
        bars += f'<text x="{cx + BAR_W:.1f}" y="{PAD_T+ch+18:.1f}" fill="#38bdf8" font-size="10" text-anchor="middle">-${row["savings"]}</text>'
        # Day label
        bars += f'<text x="{cx + BAR_W:.1f}" y="{PAD_T+ch+32:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle">{row["day"]}</text>'

    # Y-axis ticks
    grid = ""
    for tick in [0, 25, 50, 75, 100]:
        y = PAD_T + ch - tick / max_val * ch
        if y > PAD_T:
            grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
            grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">${tick}</text>'

    legend = (
        f'<rect x="{PAD_L}" y="{H-14}" width="12" height="10" fill="#f97316" rx="1"/>'
        f'<text x="{PAD_L+16}" y="{H-5}" fill="#94a3b8" font-size="11">Reactive (baseline)</text>'
        f'<rect x="{PAD_L+150}" y="{H-14}" width="12" height="10" fill="#22c55e" rx="1"/>'
        f'<text x="{PAD_L+166}" y="{H-5}" fill="#94a3b8" font-size="11">Predictive (OCI autoscaler)</text>'
        f'<text x="{PAD_L+370}" y="{H-5}" fill="#38bdf8" font-size="11">Avg {OVERALL_SAVINGS_PCT}% savings · ${AVG_DAILY_SAVING}/day saved</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>'
        f'{grid}{bars}{legend}'
        f'<text x="{W//2}" y="{PAD_T-10}" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">GPU Fleet Cost: Reactive vs Predictive Scaling ($/day)</text>'
        f'</svg>'
    )

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = _svg_line_chart()
    svg2 = _svg_cost_chart()
    predictive_events = sum(1 for e in SCALE_EVENTS if e["type"] == "predictive_up")
    reactive_events = sum(1 for e in SCALE_EVENTS if e["type"] == "reactive_up")
    scale_down_events = sum(1 for e in SCALE_EVENTS if e["type"] == "scale_down")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Fleet Autoscaler v2 — Port 8224</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em; }}
  .card-value {{ font-size: 1.8rem; font-weight: 700; margin-top: 4px; }}
  .card-sub {{ color: #475569; font-size: 0.78rem; margin-top: 4px; }}
  .red {{ color: #C74634; }}
  .sky {{ color: #38bdf8; }}
  .green {{ color: #22c55e; }}
  .orange {{ color: #f97316; }}
  .chart-wrap {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  .chart-title {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 14px; }}
  footer {{ color: #334155; font-size: 0.75rem; text-align: center; margin-top: 32px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ color: #64748b; font-weight: 600; padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #1e293b; }}
  tr:last-child td {{ border-bottom: none; }}
</style>
</head>
<body>
<h1>OCI Fleet Autoscaler v2</h1>
<div class="subtitle">Predictive GPU node scaling — Port 8224 &nbsp;|&nbsp; Region: us-ashburn-1 &nbsp;|&nbsp; Shape: BM.GPU.A100-v2.8</div>

<div class="metrics">
  <div class="card">
    <div class="card-label">Prediction Accuracy (MAPE)</div>
    <div class="card-value sky">{MAPE:.1f}%</div>
    <div class="card-sub">7-day rolling · lower is better</div>
  </div>
  <div class="card">
    <div class="card-label">Avg Cost Savings</div>
    <div class="card-value green">{OVERALL_SAVINGS_PCT:.1f}%</div>
    <div class="card-sub">${AVG_DAILY_SAVING}/day vs reactive baseline</div>
  </div>
  <div class="card">
    <div class="card-label">Scale-Up Lead Time</div>
    <div class="card-value sky">{SCALE_UP_LEAD_MIN} min</div>
    <div class="card-sub">Earlier than reactive trigger</div>
  </div>
  <div class="card">
    <div class="card-label">Predictive Scale-Ups</div>
    <div class="card-value green">{predictive_events}</div>
    <div class="card-sub">Reactive: {reactive_events} · Scale-downs: {scale_down_events}</div>
  </div>
  <div class="card">
    <div class="card-label">Node Range</div>
    <div class="card-value orange">4 → 8</div>
    <div class="card-sub">Business hours · Weekend idle prevention</div>
  </div>
  <div class="card">
    <div class="card-label">Weekly Savings</div>
    <div class="card-value green">${round(AVG_DAILY_SAVING * 7, 0):.0f}</div>
    <div class="card-sub">Predictive vs always-on reactive</div>
  </div>
</div>

<div class="chart-wrap">
  <div class="chart-title">GPU Demand Time Series — 7 Days Hourly Resolution</div>
  {svg1}
</div>

<div class="chart-wrap">
  <div class="chart-title">Daily Cost: Reactive Baseline vs Predictive Scaling</div>
  {svg2}
</div>

<div class="chart-wrap">
  <div class="chart-title">Daily Cost Breakdown</div>
  <table>
    <thead><tr><th>Day</th><th>Reactive ($)</th><th>Predictive ($)</th><th>Savings ($)</th><th>Savings %</th></tr></thead>
    <tbody>
      {''.join(f"<tr><td>{r['day']}</td><td class='orange'>{r['reactive']}</td><td class='green'>{r['predictive']}</td><td class='sky'>{r['savings']}</td><td class='sky'>{round(r['savings']/r['reactive']*100,1)}%</td></tr>" for r in COST_DATA)}
    </tbody>
  </table>
</div>

<footer>OCI Fleet Autoscaler v2 &mdash; cycle-41A &mdash; port 8224</footer>
</body>
</html>"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="OCI Fleet Autoscaler v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/metrics")
    async def metrics():
        return {
            "service": "fleet_autoscaler_v2",
            "port": 8224,
            "mape_pct": MAPE,
            "avg_daily_savings_usd": AVG_DAILY_SAVING,
            "overall_savings_pct": OVERALL_SAVINGS_PCT,
            "scale_up_lead_min": SCALE_UP_LEAD_MIN,
            "scale_events": {
                "predictive_up": sum(1 for e in SCALE_EVENTS if e["type"] == "predictive_up"),
                "reactive_up": sum(1 for e in SCALE_EVENTS if e["type"] == "reactive_up"),
                "scale_down": sum(1 for e in SCALE_EVENTS if e["type"] == "scale_down"),
            },
            "cost_by_day": COST_DATA,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "fleet_autoscaler_v2", "port": 8224}

else:
    # Stdlib fallback
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
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
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8224)
    else:
        with socketserver.TCPServer(("", 8224), Handler) as s:
            print("fleet_autoscaler_v2 (stdlib) running on http://0.0.0.0:8224")
            s.serve_forever()
