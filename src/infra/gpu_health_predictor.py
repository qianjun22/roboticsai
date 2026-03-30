"""GPU Health Predictor Service — port 8335
Predicts GPU hardware failures using thermal, utilization, and error count signals.
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
# Mock data
# ---------------------------------------------------------------------------

GPU_NODES = [
    {
        "id": "GPU4",
        "region": "US-Ashburn",
        "score": 94,
        "forecast_days": 180,
        "status": "excellent",
        "temp_c": 62,
        "temp_trend": +0.3,
        "ecc_errors_24h": 0,
        "mem_bw_pct": 98.1,
        "util_variance": 4.2,
        "uptime_days": 92,
        "last_maintenance": "2025-12-30",
        "sparkline": [91, 92, 93, 93, 94, 94, 94, 94, 93, 94],
    },
    {
        "id": "GPU5",
        "region": "US-Ashburn",
        "score": 88,
        "forecast_days": 120,
        "status": "good",
        "temp_c": 71,
        "temp_trend": +0.8,
        "ecc_errors_24h": 1,
        "mem_bw_pct": 95.4,
        "util_variance": 9.1,
        "uptime_days": 140,
        "last_maintenance": "2025-10-18",
        "sparkline": [93, 92, 91, 90, 90, 89, 89, 88, 88, 88],
    },
    {
        "id": "Phoenix_GPU1",
        "region": "US-Phoenix",
        "score": 79,
        "forecast_days": 45,
        "status": "watch",
        "temp_c": 79,
        "temp_trend": +2.1,
        "ecc_errors_24h": 4,
        "mem_bw_pct": 88.7,
        "util_variance": 18.3,
        "uptime_days": 210,
        "last_maintenance": "2025-08-05",
        "sparkline": [90, 88, 87, 85, 84, 83, 82, 81, 80, 79],
    },
    {
        "id": "Frankfurt_GPU1",
        "region": "EU-Frankfurt",
        "score": 91,
        "forecast_days": 150,
        "status": "good",
        "temp_c": 65,
        "temp_trend": +0.5,
        "ecc_errors_24h": 0,
        "mem_bw_pct": 97.2,
        "util_variance": 6.8,
        "uptime_days": 108,
        "last_maintenance": "2025-12-01",
        "sparkline": [90, 91, 90, 91, 92, 91, 91, 92, 91, 91],
    },
]

FEATURE_IMPORTANCE = [
    {"name": "ecc_error_rate",             "importance": 0.48, "color": "#ef4444"},
    {"name": "temperature_trend",           "importance": 0.31, "color": "#f97316"},
    {"name": "memory_bw_degradation",       "importance": 0.22, "color": "#eab308"},
    {"name": "utilization_variance",        "importance": 0.14, "color": "#38bdf8"},
    {"name": "uptime_days",                 "importance": 0.09, "color": "#a78bfa"},
]

METRICS = {
    "fleet_avg_score": 88.0,
    "nodes_watch": 1,
    "false_alarm_rate": 0.027,
    "model_accuracy": 0.924,
    "avg_forecast_days": 123.75,
    "maintenance_cost_saved_pct": 34,
}

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_health_dashboard_svg() -> str:
    """4-GPU health score cards with sparklines and risk signals."""
    W, H = 820, 340
    card_w = 180
    card_h = 260
    gap = 24
    start_x = (W - (card_w * 4 + gap * 3)) / 2
    top = 40

    status_color = {"excellent": "#22c55e", "good": "#38bdf8", "watch": "#f97316", "critical": "#ef4444"}

    cards = ""
    for i, g in enumerate(GPU_NODES):
        x = start_x + i * (card_w + gap)
        y = top
        col = status_color.get(g["status"], "#38bdf8")
        score = g["score"]

        # card background
        cards += f'<rect x="{x:.1f}" y="{y}" width="{card_w}" height="{card_h}" rx="10" fill="#1e293b" stroke="{col}" stroke-width="1.5"/>'

        # GPU id
        cards += f'<text x="{x+card_w/2:.1f}" y="{y+22}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">{g["id"]}</text>'
        cards += f'<text x="{x+card_w/2:.1f}" y="{y+36}" text-anchor="middle" fill="#64748b" font-size="9">{g["region"]}</text>'

        # score arc (simple gauge)
        arc_cx = x + card_w / 2
        arc_cy = y + 80
        arc_r = 38
        # background arc
        cards += f'<circle cx="{arc_cx:.1f}" cy="{arc_cy:.1f}" r="{arc_r}" fill="none" stroke="#0f172a" stroke-width="8"/>'
        # score arc (circumference-based)
        circ = 2 * math.pi * arc_r
        dash = circ * score / 100
        cards += f'<circle cx="{arc_cx:.1f}" cy="{arc_cy:.1f}" r="{arc_r}" fill="none" stroke="{col}" stroke-width="8" stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90 {arc_cx:.1f} {arc_cy:.1f})"/>'
        cards += f'<text x="{arc_cx:.1f}" y="{arc_cy+6:.1f}" text-anchor="middle" fill="{col}" font-size="18" font-weight="800">{score}</text>'
        cards += f'<text x="{arc_cx:.1f}" y="{arc_cy+18:.1f}" text-anchor="middle" fill="#64748b" font-size="8">HEALTH</text>'

        # status badge
        badge_y = y + 128
        cards += f'<rect x="{x+card_w/2-30:.1f}" y="{badge_y}" width="60" height="16" rx="8" fill="{col}22"/>'
        cards += f'<text x="{x+card_w/2:.1f}" y="{badge_y+11}" text-anchor="middle" fill="{col}" font-size="9" font-weight="700">{g["status"].upper()}</text>'

        # forecast
        cards += f'<text x="{x+card_w/2:.1f}" y="{y+160}" text-anchor="middle" fill="#94a3b8" font-size="10">Next maint. in</text>'
        cards += f'<text x="{x+card_w/2:.1f}" y="{y+174}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">{g["forecast_days"]}d</text>'

        # sparkline (30-day trend)
        spark_pts = g["sparkline"]
        s_x0 = x + 14
        s_y0 = y + card_h - 60
        s_w = card_w - 28
        s_h = 30
        s_min, s_max = min(spark_pts), max(spark_pts)
        s_range = max(s_max - s_min, 1)
        pts = ""
        for si, sv in enumerate(spark_pts):
            sx = s_x0 + s_w * si / (len(spark_pts) - 1)
            sy = s_y0 + s_h - (sv - s_min) / s_range * s_h
            pts += f"{sx:.1f},{sy:.1f} "
        cards += f'<polyline points="{pts.strip()}" fill="none" stroke="{col}" stroke-width="1.5" opacity="0.8"/>'
        cards += f'<text x="{x+card_w/2:.1f}" y="{s_y0-4}" text-anchor="middle" fill="#475569" font-size="8">30d trend</text>'

        # risk signals
        sig_y = y + card_h - 18
        temp_col = "#ef4444" if g["temp_trend"] > 1.5 else "#94a3b8"
        ecc_col = "#ef4444" if g["ecc_errors_24h"] > 2 else "#94a3b8"
        cards += f'<text x="{x+8}" y="{sig_y}" fill="{temp_col}" font-size="8">🌡{g["temp_c"]}°C +{g["temp_trend"]}°/mo</text>'
        cards += f'<text x="{x+8}" y="{sig_y-12}" fill="{ecc_col}" font-size="8">ECC {g["ecc_errors_24h"]}/24h</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="24" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="700">GPU Health Prediction Dashboard — Fleet Status</text>
  {cards}
</svg>'''
    return svg


def build_feature_importance_svg() -> str:
    """SHAP-style horizontal bar chart of predictive feature importances."""
    W, H = 820, 240
    left = 210
    right = W - 100
    bar_w_max = right - left
    bar_h = 28
    gap = 14
    top = 40
    i_max = FEATURE_IMPORTANCE[0]["importance"]

    axes = ""
    for pct in [0, 0.1, 0.2, 0.3, 0.4, 0.5]:
        x = left + bar_w_max * pct / i_max
        if x > right:
            break
        axes += f'<line x1="{x:.1f}" y1="{top-8}" x2="{x:.1f}" y2="{top + (bar_h+gap)*len(FEATURE_IMPORTANCE) - gap + 8}" stroke="#1e293b" stroke-width="1"/>'
        axes += f'<text x="{x:.1f}" y="{top-12}" text-anchor="middle" fill="#475569" font-size="9">{pct:.1f}</text>'

    bars = ""
    for i, feat in enumerate(FEATURE_IMPORTANCE):
        y = top + i * (bar_h + gap)
        bw = bar_w_max * feat["importance"] / i_max
        bars += f'<rect x="{left}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="4" fill="{feat["color"]}" opacity="0.75"/>'
        bars += f'<text x="{left-8}" y="{y+bar_h/2+4:.1f}" text-anchor="end" fill="#e2e8f0" font-size="12">{feat["name"]}</text>'
        bars += f'<text x="{left+bw+8:.1f}" y="{y+bar_h/2+4:.1f}" fill="{feat["color"]}" font-size="12" font-weight="700">{feat["importance"]:.2f}</text>'
        # gradient overlay
        bars += f'<rect x="{left}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="4" fill="url(#grad)" opacity="0.15"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:10px">
  <defs>
    <linearGradient id="grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="white" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="white" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="14" font-weight="700">Predictive Feature Importance (SHAP) — GPU Failure Signals</text>
  <line x1="{left}" y1="{top-8}" x2="{left}" y2="{top + (bar_h+gap)*len(FEATURE_IMPORTANCE) + 8}" stroke="#334155" stroke-width="1.5"/>
  {axes}
  {bars}
  <text x="{W//2}" y="{top + (bar_h+gap)*len(FEATURE_IMPORTANCE) + 26}" text-anchor="middle" fill="#475569" font-size="11">ECC error rate is the strongest predictor of GPU failures (importance 0.48) · model accuracy {METRICS['model_accuracy']:.1%}</text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    health_svg = build_health_dashboard_svg()
    shap_svg = build_feature_importance_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    node_rows = ""
    for g in GPU_NODES:
        col = {"excellent": "#22c55e", "good": "#38bdf8", "watch": "#f97316", "critical": "#ef4444"}.get(g["status"], "#38bdf8")
        node_rows += f"""
        <tr>
          <td style="color:#e2e8f0;font-weight:600">{g['id']}</td>
          <td style="color:#64748b;font-size:12px">{g['region']}</td>
          <td style="color:{col};font-weight:700">{g['score']}</td>
          <td><span style="background:{col}22;color:{col};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{g['status'].upper()}</span></td>
          <td style="color:#e2e8f0">{g['forecast_days']}d</td>
          <td style="color:#94a3b8">{g['temp_c']}°C <span style="color:{'#ef4444' if g['temp_trend']>1.5 else '#64748b'}">+{g['temp_trend']:.1f}°/mo</span></td>
          <td style="color:{'#ef4444' if g['ecc_errors_24h']>2 else '#94a3b8'}">{g['ecc_errors_24h']}</td>
          <td style="color:#64748b">{g['mem_bw_pct']:.1f}%</td>
          <td style="color:#64748b">{g['uptime_days']}d</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>GPU Health Predictor — Port 8335</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .kpi-val {{ font-size: 28px; font-weight: 800; color: #38bdf8; }}
    .kpi-val.orange {{ color: #f97316; }}
    .kpi-val.green {{ color: #22c55e; }}
    .kpi-label {{ font-size: 11px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .card h2 {{ font-size: 14px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 8px; text-align: left; border-bottom: 1px solid #334155; }}
    td {{ padding: 10px 8px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
    .accent {{ color: #C74634; }}
    .footer {{ color: #334155; font-size: 11px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
    <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px">⚡</div>
    <h1>GPU Health <span class="accent">Predictor</span></h1>
  </div>
  <p class="subtitle">Predictive GPU failure detection · thermal + ECC + utilization signals · port 8335 · {ts}</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-val green">{METRICS['fleet_avg_score']:.0f}</div><div class="kpi-label">Fleet Avg Health Score</div></div>
    <div class="kpi"><div class="kpi-val orange">{METRICS['nodes_watch']}</div><div class="kpi-label">Nodes Under Watch</div></div>
    <div class="kpi"><div class="kpi-val">{METRICS['model_accuracy']:.1%}</div><div class="kpi-label">Model Accuracy</div></div>
    <div class="kpi"><div class="kpi-val">{METRICS['maintenance_cost_saved_pct']}%</div><div class="kpi-label">Maintenance Cost Saved</div></div>
  </div>

  <div class="card">
    <h2>GPU Fleet Health Dashboard</h2>
    {health_svg}
  </div>

  <div class="card">
    <h2>Fleet Detail — All GPU Nodes</h2>
    <table>
      <thead><tr><th>GPU ID</th><th>Region</th><th>Score</th><th>Status</th><th>Next Maint.</th><th>Temperature</th><th>ECC Errors/24h</th><th>Mem BW</th><th>Uptime</th></tr></thead>
      <tbody>{node_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Predictive Feature Importance — SHAP Analysis</h2>
    {shap_svg}
    <p style="color:#475569;font-size:11px;margin-top:8px">ECC error rate is the strongest predictor · false alarm rate {METRICS['false_alarm_rate']:.1%} · Phoenix_GPU1 flagged for proactive maintenance (45d forecast)</p>
  </div>

  <div class="footer">OCI Robot Cloud · GPU Health Predictor Service · port 8335 · © 2026 Oracle Corporation</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="GPU Health Predictor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gpu_health_predictor", "port": 8335}

    @app.get("/api/nodes")
    async def get_nodes():
        return {"nodes": GPU_NODES, "metrics": METRICS}

    @app.get("/api/features")
    async def get_features():
        return {"feature_importance": FEATURE_IMPORTANCE}

else:
    import http.server

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
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8335)
    else:
        import http.server
        with http.server.HTTPServer(("0.0.0.0", 8335), Handler) as srv:
            print("Serving on http://0.0.0.0:8335 (stdlib fallback)")
            srv.serve_forever()
