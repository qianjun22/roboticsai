"""Fleet Autoscaler V3 — FastAPI port 8858"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8858

# Decision tree signal weights for SVG rendering
SIGNALS = [
    ("GPU Util %",       0.28),
    ("Queue Depth",      0.22),
    ("ML Demand Fcst",   0.18),
    ("Latency P99",      0.13),
    ("Cost Headroom",    0.10),
    ("Time-of-Day",      0.05),
    ("Event Calendar",   0.04),
]


def _signal_bars_svg() -> str:
    """SVG bar chart of the 7 autoscaler decision signals."""
    bar_h, bar_gap, bar_w = 26, 8, 360
    total_h = len(SIGNALS) * (bar_h + bar_gap) + 40
    bars = []
    for i, (label, weight) in enumerate(SIGNALS):
        y = 30 + i * (bar_h + bar_gap)
        w = int(bar_w * weight / SIGNALS[0][1])  # normalise to largest
        pct = int(weight * 100)
        color = "#C74634" if i == 0 else ("#38bdf8" if i < 3 else "#64748b")
        bars.append(
            f'<text x="0" y="{y + 18}" font-size="12" fill="#94a3b8">{label}</text>'
            f'<rect x="130" y="{y + 4}" width="{w}" height="{bar_h - 8}" rx="4" fill="{color}"/>'
            f'<text x="{130 + w + 6}" y="{y + 18}" font-size="12" fill="#e2e8f0">{pct}%</text>'
        )
    bars_str = "\n".join(bars)
    return (
        f'<svg viewBox="0 0 520 {total_h}" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="0" y="18" font-size="14" font-weight="bold" fill="#38bdf8">'
        f'Scale Decision Signal Weights</text>'
        f'{bars_str}'
        f'</svg>'
    )


def _scale_events_svg() -> str:
    """SVG timeline comparing v2 vs v3 unnecessary scale events."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    v2 = [42, 38, 45, 40, 36, 44]
    v3 = [29, 26, 31, 27, 25, 30]
    w, h = 480, 160
    max_v = max(v2)
    pts_v2 = " ".join(f"{40 + i*74},{h - 20 - int(v/max_v*(h-40))}" for i, v in enumerate(v2))
    pts_v3 = " ".join(f"{40 + i*74},{h - 20 - int(v/max_v*(h-40))}" for i, v in enumerate(v3))
    labels = "".join(
        f'<text x="{40 + i*74}" y="{h - 4}" font-size="11" fill="#64748b" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )
    return (
        f'<svg viewBox="0 0 {w} {h+30}" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="0" y="16" font-size="13" font-weight="bold" fill="#38bdf8">'
        f'Unnecessary Scale Events: V2 vs V3</text>'
        f'<polyline points="{pts_v2}" fill="none" stroke="#64748b" stroke-width="2"/>'
        f'<polyline points="{pts_v3}" fill="none" stroke="#C74634" stroke-width="2"/>'
        f'<text x="370" y="40" font-size="11" fill="#64748b">V2</text>'
        f'<text x="370" y="60" font-size="11" fill="#C74634">V3</text>'
        f'{labels}'
        f'</svg>'
    )


def build_html() -> str:
    signal_svg = _signal_bars_svg()
    events_svg = _scale_events_svg()
    # Simulated live metrics
    gpu_util   = 62 + random.randint(-5, 5)
    queue_depth = 14 + random.randint(-3, 3)
    replicas    = 8
    cost_day    = 47
    return f"""<!DOCTYPE html><html><head><title>Fleet Autoscaler V3</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.metric{{background:#0f172a;border-radius:8px;padding:16px;text-align:center}}
.metric .val{{font-size:2rem;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.8rem;
        background:#C74634;color:#fff;margin-left:8px}}
</style></head>
<body>
<h1>Fleet Autoscaler V3 <span class="badge">port {PORT}</span></h1>
<p style="color:#64748b">Predictive + reactive hybrid autoscaling using ML demand forecast
   and real-time GPU utilisation signals.</p>

<div class="grid">
  <div class="metric"><div class="val">{gpu_util}%</div><div class="lbl">GPU Util (live)</div></div>
  <div class="metric"><div class="val">{queue_depth}</div><div class="lbl">Queue Depth</div></div>
  <div class="metric"><div class="val">{replicas}</div><div class="lbl">Active Replicas</div></div>
  <div class="metric"><div class="val">${cost_day}</div><div class="lbl">Cost / Day</div></div>
</div>

<div class="card">
  <h2>Decision Signals (7-factor model)</h2>
  {signal_svg}
</div>

<div class="card">
  <h2>Scale Event Reduction vs V2</h2>
  {events_svg}
  <ul style="color:#94a3b8;font-size:0.9rem;margin-top:12px">
    <li>31% fewer unnecessary scale events vs V2</li>
    <li>AI World Sep 2026: 8× pre-provisioning from event-calendar signal</li>
    <li>Cost: <strong style="color:#C74634">$47/day</strong> vs $89/day (V2) — 47% reduction</li>
  </ul>
</div>

<div class="card">
  <h2>Architecture</h2>
  <p>Hybrid controller: ML demand forecast (LSTM, 24-h horizon) feeds a scale-up
  bias while reactive P99 latency &amp; queue-depth signals handle burst.  Cost
  headroom signal prevents over-provisioning.  Event calendar (AI World, GTC)
  triggers pre-warm 30 min ahead.</p>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Fleet Autoscaler V3")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/signals")
    def signals():
        return {"signals": [{"name": n, "weight": w} for n, w in SIGNALS]}

    @app.get("/metrics")
    def metrics():
        return {
            "gpu_util_pct": 62 + random.randint(-5, 5),
            "queue_depth": 14 + random.randint(-3, 3),
            "active_replicas": 8,
            "cost_per_day_usd": 47,
            "v2_cost_per_day_usd": 89,
            "scale_event_reduction_pct": 31,
            "ai_world_pre_provision_factor": 8,
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
