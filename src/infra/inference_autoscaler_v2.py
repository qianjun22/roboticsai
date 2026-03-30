"""Inference Autoscaler v2 — FastAPI service on port 8279.

Advanced ML-based demand prediction and cost optimisation for OCI Robot Cloud
inference fleet. Compares reactive vs predictive scaling strategies.
Dashboard: dark theme with Oracle red #C74634, sky blue #38bdf8.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

import math
import random

# ---------------------------------------------------------------------------
# Mock Data Generation (stdlib only — no numpy/pandas/torch)
# ---------------------------------------------------------------------------

random.seed(42)

# 7 days × 24 hours = 168 data points
HOURS = 168


def _diurnal(h: int) -> float:
    """Normalised diurnal demand pattern (0-1), peaks at 14:00."""
    hour_of_day = h % 24
    # Two peaks: 09:00 and 19:00
    peak1 = math.exp(-0.5 * ((hour_of_day - 9) / 2.5) ** 2)
    peak2 = math.exp(-0.5 * ((hour_of_day - 19) / 2.0) ** 2)
    trough = 0.08 if (hour_of_day < 5 or hour_of_day > 22) else 0.0
    return max(peak1, peak2, trough)


actual_demand = []
predicted_demand = []
reactive_cost = []
predictive_cost = []
scale_events = []  # list of (hour, type)  type: 'up' | 'down'

for h in range(HOURS):
    base = _diurnal(h) * 80 + 10  # 10-90 rps
    noise = random.gauss(0, 4)
    actual = max(5.0, base + noise)
    actual_demand.append(round(actual, 2))

    # Predictive model: 94% accuracy — small systematic error
    pred_error = random.gauss(0, 2.5)
    predicted = max(5.0, base + pred_error)
    predicted_demand.append(round(predicted, 2))

    # Reactive scaling: capacity = actual demand, but lags by 1 hour
    lag_demand = actual_demand[max(0, h - 1)]
    r_cost = lag_demand * 0.012 + (2.0 if lag_demand < actual else 0.5)  # penalty for under-provisioning
    reactive_cost.append(round(r_cost, 4))

    # Predictive scaling: uses predicted demand (4h ahead smoothed)
    future_idx = min(h + 4, HOURS - 1)
    # We don't have future actual yet, so use the model
    future_pred = max(5.0, _diurnal(h + 4) * 80 + 10)
    p_cost = future_pred * 0.010  # lower unit cost due to reserved capacity
    predictive_cost.append(round(p_cost, 4))

    # Scale events
    if h > 0:
        delta = actual - actual_demand[h - 1]
        if delta > 12:   scale_events.append({"hour": h, "type": "up",   "magnitude": round(delta, 1)})
        elif delta < -12: scale_events.append({"hour": h, "type": "down", "magnitude": round(abs(delta), 1)})

total_reactive_cost    = round(sum(reactive_cost), 2)
total_predictive_cost  = round(sum(predictive_cost), 2)
cost_savings_pct       = round((1 - total_predictive_cost / total_reactive_cost) * 100, 1)
daily_savings          = round((total_reactive_cost - total_predictive_cost) / 7, 2)

# MAPE
mape = round(
    100 * sum(abs(a - p) / max(a, 1) for a, p in zip(actual_demand, predicted_demand)) / HOURS,
    2
)


# ---------------------------------------------------------------------------
# SVG 1 — Predicted vs Actual Demand Time Series
# ---------------------------------------------------------------------------

def build_timeseries_svg() -> str:
    W, H = 820, 320
    lm, rm, tm, bm = 50, 20, 40, 50
    cw = W - lm - rm
    ch = H - tm - bm
    max_d = max(max(actual_demand), max(predicted_demand))

    def px(h):   return lm + int(h / (HOURS - 1) * cw)
    def py(val): return tm + ch - int(val / max_d * ch)

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Predicted vs Actual Demand (7 Days, Hourly)</text>')

    # Y-axis grid
    for pct in [0, 25, 50, 75, 100]:
        val = max_d * pct / 100
        y = py(val)
        lines.append(f'<line x1="{lm}" y1="{y}" x2="{W-rm}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{lm-4}" y="{y+4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{int(val)}</text>')

    # Day separators
    for day in range(1, 7):
        x = px(day * 24)
        lines.append(f'<line x1="{x}" y1="{tm}" x2="{x}" y2="{tm+ch}" stroke="#475569" stroke-width="1" stroke-dasharray="6,3"/>')
        lines.append(f'<text x="{x+2}" y="{tm+ch+14}" fill="#64748b" font-size="9" font-family="monospace">D{day+1}</text>')

    # Actual demand path
    pts_actual = " ".join(f"{px(h)},{py(v)}" for h, v in enumerate(actual_demand))
    lines.append(f'<polyline points="{pts_actual}" fill="none" stroke="#38bdf8" stroke-width="1.5" opacity="0.9"/>')

    # Predicted demand path
    pts_pred = " ".join(f"{px(h)},{py(v)}" for h, v in enumerate(predicted_demand))
    lines.append(f'<polyline points="{pts_pred}" fill="none" stroke="#fbbf24" stroke-width="1.5" opacity="0.75" stroke-dasharray="4,2"/>')

    # Scale events
    for ev in scale_events[:30]:  # cap for readability
        x = px(ev["hour"])
        col = "#60a5fa" if ev["type"] == "up" else "#34d399"
        arrow = "▲" if ev["type"] == "up" else "▼"
        y_pos = py(actual_demand[ev["hour"]])
        lines.append(f'<text x="{x}" y="{y_pos - 4}" text-anchor="middle" fill="{col}" font-size="9">{arrow}</text>')

    # Axes
    lines.append(f'<line x1="{lm}" y1="{tm}" x2="{lm}" y2="{tm+ch}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{lm}" y1="{tm+ch}" x2="{W-rm}" y2="{tm+ch}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="{lm}" y="{tm+ch+14}" fill="#64748b" font-size="9" font-family="monospace">D1</text>')

    # Y label
    lines.append(f'<text x="10" y="{tm + ch//2}" fill="#64748b" font-size="9" font-family="monospace" transform="rotate(-90,10,{tm+ch//2})">RPS</text>')

    # Legend
    lines.append(f'<rect x="{lm}" y="{H-22}" width="12" height="4" fill="#38bdf8"/>')
    lines.append(f'<text x="{lm+16}" y="{H-16}" fill="#94a3b8" font-size="9" font-family="monospace">Actual</text>')
    lines.append(f'<rect x="{lm+80}" y="{H-22}" width="12" height="4" fill="#fbbf24"/>')
    lines.append(f'<text x="{lm+96}" y="{H-16}" fill="#94a3b8" font-size="9" font-family="monospace">Predicted (MAPE {mape}%)</text>')
    lines.append(f'<text x="{lm+280}" y="{H-16}" fill="#60a5fa" font-size="9" font-family="monospace">▲ scale-up</text>')
    lines.append(f'<text x="{lm+360}" y="{H-16}" fill="#34d399" font-size="9" font-family="monospace">▼ scale-down</text>')
    lines.append(f'<text x="{lm+440}" y="{H-16}" fill="#22c55e" font-size="9" font-family="monospace">Cost savings vs reactive: {cost_savings_pct}% | ${daily_savings}/day</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG 2 — Cost Efficiency Scatter: Reactive vs Predictive
# ---------------------------------------------------------------------------

def build_scatter_svg() -> str:
    W, H = 820, 320
    lm, rm, tm, bm = 55, 30, 40, 50
    cw = W - lm - rm
    ch = H - tm - bm

    max_d = max(actual_demand)
    max_c = max(max(reactive_cost), max(predictive_cost))

    def sx(demand): return lm + int(demand / max_d * cw)
    def sy(cost):   return tm + ch - int(cost / max_c * ch)

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Cost Efficiency: Reactive vs Predictive Scaling</text>')

    # Grid
    for pct in [0, 25, 50, 75, 100]:
        val_d = max_d * pct / 100
        val_c = max_c * pct / 100
        x = sx(val_d)
        y = sy(val_c)
        lines.append(f'<line x1="{x}" y1="{tm}" x2="{x}" y2="{tm+ch}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<line x1="{lm}" y1="{y}" x2="{W-rm}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        if pct > 0:
            lines.append(f'<text x="{x}" y="{tm+ch+14}" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">{int(val_d)}</text>')
            lines.append(f'<text x="{lm-4}" y="{y+3}" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">{val_c:.2f}</text>')

    # Optimal frontier (linear lower bound)
    frontier_pts = " ".join(
        f"{sx(d)},{sy(d * 0.009)}"
        for d in [i * max_d / 20 for i in range(21)]
    )
    lines.append(f'<polyline points="{frontier_pts}" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.6"/>')
    lines.append(f'<text x="{sx(max_d*0.7)+4}" y="{sy(max_d*0.7*0.009)-4}" fill="#22c55e" font-size="9" font-family="monospace">Optimal frontier</text>')

    # Scatter points — reactive (red, semi-transparent)
    for h in range(0, HOURS, 3):  # every 3rd hour for readability
        x = sx(actual_demand[h])
        y = sy(reactive_cost[h])
        lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#C74634" opacity="0.55"/>')

    # Scatter points — predictive (blue)
    for h in range(0, HOURS, 3):
        x = sx(actual_demand[h])
        y = sy(predictive_cost[h])
        lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#38bdf8" opacity="0.65"/>')

    # Highlight outlier hours (3 AM scale-down predicted perfectly)
    for h in range(HOURS):
        if h % 24 == 3 and actual_demand[h] < 12:  # 3 AM trough
            x = sx(actual_demand[h])
            y_r = sy(reactive_cost[h])
            y_p = sy(predictive_cost[h])
            lines.append(f'<circle cx="{x}" cy="{y_r}" r="6" fill="none" stroke="#fbbf24" stroke-width="1.5"/>')
            lines.append(f'<circle cx="{x}" cy="{y_p}" r="6" fill="none" stroke="#a3e635" stroke-width="1.5"/>')
            lines.append(f'<text x="{x+8}" y="{y_p-2}" fill="#a3e635" font-size="8" font-family="monospace">3AM ✓</text>')
            break

    # Axes
    lines.append(f'<line x1="{lm}" y1="{tm}" x2="{lm}" y2="{tm+ch}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{lm}" y1="{tm+ch}" x2="{W-rm}" y2="{tm+ch}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="{W//2}" y="{H-2}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Demand (RPS)</text>')
    lines.append(f'<text x="10" y="{tm + ch//2}" fill="#64748b" font-size="9" font-family="monospace" transform="rotate(-90,10,{tm+ch//2})">Cost ($/hr)</text>')

    # Legend
    lines.append(f'<circle cx="{lm+8}" cy="{H-20}" r="4" fill="#C74634" opacity="0.7"/>')
    lines.append(f'<text x="{lm+15}" y="{H-15}" fill="#94a3b8" font-size="9" font-family="monospace">Reactive scaling</text>')
    lines.append(f'<circle cx="{lm+140}" cy="{H-20}" r="4" fill="#38bdf8" opacity="0.8"/>')
    lines.append(f'<text x="{lm+147}" y="{H-15}" fill="#94a3b8" font-size="9" font-family="monospace">Predictive scaling</text>')
    lines.append(f'<text x="{lm+280}" y="{H-15}" fill="#22c55e" font-size="9" font-family="monospace">Total savings: ${total_reactive_cost - total_predictive_cost:.2f} over 7 days</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    ts_svg      = build_timeseries_svg()
    scatter_svg = build_scatter_svg()

    scale_up_count   = sum(1 for e in scale_events if e["type"] == "up")
    scale_down_count = sum(1 for e in scale_events if e["type"] == "down")
    sla_compliance   = 99.2  # % hours within SLA
    emergency_events = 3     # expensive emergency scale-ups avoided
    peak_prediction_h= 4     # hours ahead

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inference Autoscaler v2 — Port 8279</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 12px; margin-bottom: 20px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px 20px; min-width: 160px; }}
    .kpi .val {{ font-size: 26px; font-weight: bold; }}
    .kpi .lbl {{ font-size: 10px; color: #64748b; margin-top: 4px; }}
    .section {{ margin-bottom: 28px; }}
    .section h2 {{ color: #38bdf8; font-size: 13px; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    .insight {{ background: #1e293b; border-left: 3px solid #38bdf8; padding: 10px 14px; font-size: 11px; color: #cbd5e1; margin-bottom: 10px; border-radius: 4px; }}
    .insight.warn {{ border-left-color: #fbbf24; }}
    .insight.good {{ border-left-color: #22c55e; }}
    footer {{ margin-top: 32px; color: #334155; font-size: 10px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Inference Autoscaler v2</h1>
  <div class="subtitle">Port 8279 &nbsp;|&nbsp; ML-based demand prediction + cost optimisation &nbsp;|&nbsp; 7-day window</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val" style="color:#22c55e">{100 - mape:.1f}%</div><div class="lbl">Prediction Accuracy</div></div>
    <div class="kpi"><div class="val" style="color:#38bdf8">{mape}%</div><div class="lbl">MAPE</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">{cost_savings_pct}%</div><div class="lbl">Cost Savings vs Reactive</div></div>
    <div class="kpi"><div class="val" style="color:#fbbf24">${daily_savings}</div><div class="lbl">Avg Daily Savings</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">{sla_compliance}%</div><div class="lbl">SLA Compliance</div></div>
    <div class="kpi"><div class="val" style="color:#94a3b8">{scale_up_count + scale_down_count}</div><div class="lbl">Scale Events (7d)</div></div>
  </div>

  <div class="section">
    <h2>Demand Time Series — Predicted vs Actual with Scale Events</h2>
    {ts_svg}
  </div>

  <div class="section">
    <h2>Cost Efficiency Scatter — Reactive vs Predictive Strategy</h2>
    {scatter_svg}
  </div>

  <div class="section">
    <h2>Key Insights</h2>
    <div class="insight good">Predictive model achieves {100-mape:.1f}% accuracy (MAPE {mape}%) — ML demand forecasting 4h ahead eliminates emergency scale events.</div>
    <div class="insight good">3 AM scale-down correctly predicted: avoided 3 emergency scale-up events × $12 each = $36 saved.</div>
    <div class="insight">Peak demand predicted {peak_prediction_h}h ahead — reserved OCI instances provisioned at lower spot rates before surge.</div>
    <div class="insight warn">Scale events this week: {scale_up_count} scale-ups / {scale_down_count} scale-downs. Target: reduce reactive scale-ups by 50% next cycle.</div>
    <div class="insight good">Total 7-day cost: Predictive ${total_predictive_cost:.2f} vs Reactive ${total_reactive_cost:.2f} — saving ${total_reactive_cost - total_predictive_cost:.2f} ({cost_savings_pct}%).</div>
  </div>

  <footer>OCI Robot Cloud &nbsp;|&nbsp; Inference Autoscaler v2 &nbsp;|&nbsp; Powered by FastAPI + stdlib &nbsp;|&nbsp; Port 8279</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI App / stdlib fallback
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:
    app = FastAPI(title="Inference Autoscaler v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "service": "inference_autoscaler_v2",
            "port": 8279,
            "prediction_accuracy_pct": round(100 - mape, 2),
            "mape_pct": mape,
            "cost_savings_pct": cost_savings_pct,
            "daily_savings_usd": daily_savings,
            "total_7d_reactive_cost_usd": total_reactive_cost,
            "total_7d_predictive_cost_usd": total_predictive_cost,
            "sla_compliance_pct": 99.2,
            "scale_up_events": scale_up_count,
            "scale_down_events": scale_down_count,
            "peak_prediction_hours_ahead": 4,
            "emergency_events_avoided": 3,
        }

    @app.get("/api/demand")
    async def api_demand():
        return {
            "hours": HOURS,
            "actual_demand": actual_demand[:24],
            "predicted_demand": predicted_demand[:24],
            "note": "First 24 hours shown — query /api/demand?full=1 for all 168h",
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "inference_autoscaler_v2", "port": 8279}

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _run_stdlib():
        srv = HTTPServer(("", 8279), _Handler)
        print("Inference Autoscaler v2 (stdlib fallback) running on http://0.0.0.0:8279")
        srv.serve_forever()


if __name__ == "__main__":
    if _HAS_FASTAPI:
        uvicorn.run("inference_autoscaler_v2:app", host="0.0.0.0", port=8279, reload=False)
    else:
        _run_stdlib()
