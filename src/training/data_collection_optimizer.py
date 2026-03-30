"""Data Collection Optimizer — FastAPI service on port 8222.

Optimizes DAgger data collection strategy for maximum SR improvement per dollar.
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
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

CURRENT_SR = 0.65
UNCERTAINTY_GUIDED_COST_PER_PP = 8.40  # $ per SR percentage-point
RECOMMENDED_REAL_DEMOS = 180  # more real demos needed for 0.65→0.75

# Diminishing returns curves: (n_demos -> SR) for 3 strategies
def _sr_curve(n, base, scale, k):
    """Logistic-like saturation: SR = base + scale*(1-exp(-k*n))"""
    return base + scale * (1.0 - math.exp(-k * n))

def _demo_points():
    xs = list(range(0, 1001, 50))
    sim_only   = [round(_sr_curve(x, 0.30, 0.45, 0.003), 4) for x in xs]
    real_only  = [round(_sr_curve(x, 0.40, 0.50, 0.006), 4) for x in xs]
    mixed_opt  = [round(_sr_curve(x, 0.45, 0.52, 0.007), 4) for x in xs]
    return xs, sim_only, real_only, mixed_opt

def _cost_efficiency():
    """SR gain per $100 for 4 strategies at current SR milestone."""
    return [
        {"strategy": "pure_sim",           "gain_per_100": 3.2,  "milestone": "0.40-0.55", "recommended": False},
        {"strategy": "pure_real",           "gain_per_100": 6.1,  "milestone": "0.55-0.65", "recommended": False},
        {"strategy": "adaptive_mixed",      "gain_per_100": 9.8,  "milestone": "0.65-0.75", "recommended": True},
        {"strategy": "uncertainty_guided",  "gain_per_100": 11.9, "milestone": "0.75-0.85", "recommended": True},
    ]

def _metrics():
    return {
        "current_sr": CURRENT_SR,
        "target_sr": 0.75,
        "marginal_cost_per_sr_point": UNCERTAINTY_GUIDED_COST_PER_PP,
        "recommended_next_batch": RECOMMENDED_REAL_DEMOS,
        "breakeven_demo_count": 240,
        "recommended_strategy": "adaptive_mixed",
        "estimated_sessions_to_target": 3,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html():
    xs, sim_only, real_only, mixed_opt = _demo_points()
    strategies = _cost_efficiency()
    metrics = _metrics()

    # --- SVG 1: diminishing-returns line chart ---
    W, H = 560, 280
    PAD = {"l": 55, "r": 20, "t": 30, "b": 50}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]
    n_max = xs[-1]  # 1000
    sr_min, sr_max = 0.25, 1.0

    def tx(n):  return PAD["l"] + (n / n_max) * pw
    def ty(sr): return PAD["t"] + ph - ((sr - sr_min) / (sr_max - sr_min)) * ph

    def polyline(vals, colour):
        pts = " ".join(f"{tx(xs[i]):.1f},{ty(v):.1f}" for i, v in enumerate(vals))
        return f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.2"/>'

    # current position marker (x=360 demos is approx current for mixed_opt ~0.65)
    cur_x = 360
    cur_y = ty(_sr_curve(cur_x, 0.45, 0.52, 0.007))
    # next optimal (180 more real demos)
    next_x = cur_x + 180
    next_y = ty(_sr_curve(next_x, 0.45, 0.52, 0.007))

    # x-axis ticks
    x_ticks = ""
    for n in range(0, 1001, 200):
        xp = tx(n)
        x_ticks += f'<line x1="{xp:.1f}" y1="{PAD["t"]+ph}" x2="{xp:.1f}" y2="{PAD["t"]+ph+5}" stroke="#475569"/>'
        x_ticks += f'<text x="{xp:.1f}" y="{PAD["t"]+ph+18}" text-anchor="middle" fill="#94a3b8" font-size="11">{n}</text>'

    # y-axis ticks
    y_ticks = ""
    for sr_tick in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        yp = ty(sr_tick)
        y_ticks += f'<line x1="{PAD["l"]-4}" y1="{yp:.1f}" x2="{PAD["l"]+pw}" y2="{yp:.1f}" stroke="#1e3a5f" stroke-dasharray="3,3"/>'
        y_ticks += f'<text x="{PAD["l"]-8}" y="{yp+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{sr_tick:.1f}</text>'

    svg1 = f"""
    <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">SR vs Demonstrations (Diminishing Returns)</text>
      {y_ticks}
      {x_ticks}
      {polyline(sim_only,  '#60a5fa')}
      {polyline(real_only, '#f59e0b')}
      {polyline(mixed_opt, '#34d399')}
      <!-- current position -->
      <circle cx="{tx(cur_x):.1f}" cy="{cur_y:.1f}" r="6" fill="#C74634" stroke="white" stroke-width="1.5"/>
      <text x="{tx(cur_x)+8:.1f}" y="{cur_y-6:.1f}" fill="#C74634" font-size="11" font-weight="bold">current (SR={CURRENT_SR})</text>
      <!-- next optimal -->
      <circle cx="{tx(next_x):.1f}" cy="{next_y:.1f}" r="6" fill="#38bdf8" stroke="white" stroke-width="1.5"/>
      <text x="{tx(next_x)+8:.1f}" y="{next_y-6:.1f}" fill="#38bdf8" font-size="11">+{RECOMMENDED_REAL_DEMOS} demos</text>
      <!-- legend -->
      <rect x="{PAD['l']+10}" y="{PAD['t']+10}" width="12" height="4" fill="#60a5fa"/><text x="{PAD['l']+26}" y="{PAD['t']+17}" fill="#94a3b8" font-size="11">sim_only</text>
      <rect x="{PAD['l']+95}" y="{PAD['t']+10}" width="12" height="4" fill="#f59e0b"/><text x="{PAD['l']+111}" y="{PAD['t']+17}" fill="#94a3b8" font-size="11">real_only</text>
      <rect x="{PAD['l']+190}" y="{PAD['t']+10}" width="12" height="4" fill="#34d399"/><text x="{PAD['l']+206}" y="{PAD['t']+17}" fill="#94a3b8" font-size="11">mixed_optimal</text>
      <!-- axis labels -->
      <text x="{W//2}" y="{H-4}" text-anchor="middle" fill="#64748b" font-size="11">Number of Demonstrations</text>
      <text x="14" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11" transform="rotate(-90,14,{H//2})">Success Rate</text>
    </svg>"""

    # --- SVG 2: cost-efficiency bar chart ---
    BW, BH = 560, 260
    BPAD = {"l": 160, "r": 30, "t": 35, "b": 45}
    bpw = BW - BPAD["l"] - BPAD["r"]
    bph = BH - BPAD["t"] - BPAD["b"]
    bar_h = bph / (len(strategies) + 1)
    max_gain = max(s["gain_per_100"] for s in strategies)

    bars_svg = ""
    for i, s in enumerate(strategies):
        yp = BPAD["t"] + i * bar_h + bar_h * 0.15
        bw_val = (s["gain_per_100"] / max_gain) * bpw * 0.9
        colour = "#C74634" if s["recommended"] else "#475569"
        bars_svg += f'<rect x="{BPAD["l"]}" y="{yp:.1f}" width="{bw_val:.1f}" height="{bar_h*0.7:.1f}" fill="{colour}" rx="3"/>'
        bars_svg += f'<text x="{BPAD["l"]-6}" y="{yp+bar_h*0.42:.1f}" text-anchor="end" fill="#e2e8f0" font-size="11" font-weight="bold">{s["strategy"]}</text>'
        bars_svg += f'<text x="{BPAD["l"]+bw_val+6:.1f}" y="{yp+bar_h*0.42:.1f}" fill="#38bdf8" font-size="12" font-weight="bold">{s["gain_per_100"]}</text>'
        badge = " ★" if s["recommended"] else ""
        bars_svg += f'<text x="{BPAD["l"]-6}" y="{yp+bar_h*0.42+13:.1f}" text-anchor="end" fill="#64748b" font-size="10">{s["milestone"]}{badge}</text>'

    svg2 = f"""
    <svg viewBox="0 0 {BW} {BH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{BW}px;background:#0f172a;border-radius:8px">
      <text x="{BW//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">SR Gain per $100 by Collection Strategy</text>
      {bars_svg}
      <text x="{BW//2}" y="{BH-6}" text-anchor="middle" fill="#64748b" font-size="11">SR Gain (pp per $100 spent) — ★ recommended at current SR</text>
    </svg>"""

    # Metrics cards
    def card(label, value, sub=""):
        sub_html = f'<div style="color:#64748b;font-size:12px;margin-top:4px">{sub}</div>' if sub else ""
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:160px;flex:1">
          <div style="color:#94a3b8;font-size:12px;margin-bottom:6px">{label}</div>
          <div style="color:#38bdf8;font-size:22px;font-weight:bold">{value}</div>
          {sub_html}
        </div>"""

    cards = "".join([
        card("Current SR", f"{metrics['current_sr']:.0%}", "baseline"),
        card("Target SR", f"{metrics['target_sr']:.0%}", "next milestone"),
        card("Cost/SR Point", f"${metrics['marginal_cost_per_sr_point']:.2f}", "uncertainty_guided"),
        card("Next Batch", f"{metrics['recommended_next_batch']} demos", "real demos needed"),
        card("Breakeven", f"{metrics['breakeven_demo_count']} demos", "sim vs real crossover"),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Data Collection Optimizer — Port 8222</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px; }}
    .chart-wrap {{ margin-bottom: 28px; }}
    .chart-title {{ color: #94a3b8; font-size: 13px; margin-bottom: 8px; }}
    footer {{ color: #334155; font-size: 11px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Data Collection Optimizer</h1>
  <div class="sub">OCI Robot Cloud · DAgger Strategy · Port 8222 · Updated {metrics['last_updated']}</div>

  <div class="cards">{cards}</div>

  <div class="chart-wrap">
    <div class="chart-title">Diminishing Returns: SR vs Number of Demonstrations</div>
    {svg1}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Cost-Efficiency by Collection Strategy</div>
    {svg2}
  </div>

  <footer>OCI Robot Cloud · cycle-40B · data_collection_optimizer.py</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="Data Collection Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/api/metrics")
    async def api_metrics():
        return _metrics()

    @app.get("/api/curves")
    async def api_curves():
        xs, sim_only, real_only, mixed_opt = _demo_points()
        return {"x": xs, "sim_only": sim_only, "real_only": real_only, "mixed_optimal": mixed_opt}

    @app.get("/api/strategies")
    async def api_strategies():
        return _cost_efficiency()

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8222, "service": "data_collection_optimizer"}

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass  # suppress access logs


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8222)
    else:
        print("FastAPI not available — starting stdlib fallback on port 8222")
        with socketserver.TCPServer(("", 8222), _Handler) as httpd:
            httpd.serve_forever()
