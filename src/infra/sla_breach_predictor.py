"""SLA Breach Predictor — FastAPI port 8855"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8855

# Partner SLA risk profiles
PARTNER_PROFILES = {
    "PI": {
        "latency_p99_ms": 210,
        "uptime_pct":     99.96,
        "error_rate_pct":  0.08,
        "breach_prob_pct": 1.2,
        "trend":           "stable",
    },
    "1X": {
        "latency_p99_ms": 485,
        "uptime_pct":     99.71,
        "error_rate_pct":  0.41,
        "breach_prob_pct": 23.0,
        "trend":           "rising",
    },
    "Agility": {
        "latency_p99_ms": 298,
        "uptime_pct":     99.88,
        "error_rate_pct":  0.19,
        "breach_prob_pct": 6.4,
        "trend":           "stable",
    },
    "Boston Dynamics": {
        "latency_p99_ms": 331,
        "uptime_pct":     99.83,
        "error_rate_pct":  0.23,
        "breach_prob_pct": 9.1,
        "trend":           "improving",
    },
}

SLA_THRESHOLDS = {
    "latency_p99_ms": 400,   # must stay below
    "uptime_pct":     99.9,  # must stay above
    "error_rate_pct":  0.5,  # must stay below
}

KEY_METRICS = {
    "breaches_last_30d":    0,
    "partners_at_risk":     1,   # 1X latency risk
    "avg_breach_prob_pct": round(
        sum(p["breach_prob_pct"] for p in PARTNER_PROFILES.values()) / len(PARTNER_PROFILES), 1
    ),
}


def _forecast_series(base: float, trend: str, days: int = 7) -> list:
    """Generate a 7-day breach probability forecast."""
    random.seed(hash(trend) & 0xFFFF)
    series = []
    v = base
    for _ in range(days):
        if trend == "rising":
            v += random.uniform(0.5, 2.0)
        elif trend == "improving":
            v -= random.uniform(0.2, 0.8)
        else:
            v += random.uniform(-0.5, 0.5)
        v = max(0.0, min(99.0, v))
        series.append(round(v, 1))
    return series


def build_svg_timeline() -> str:
    """SVG multi-line breach probability forecast (7 days)."""
    W, H = 500, 280
    pad_l, pad_r, pad_t, pad_b = 55, 20, 25, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    days = 7
    lo, hi = 0.0, 30.0

    def sx(i):
        return pad_l + i / (days - 1) * plot_w

    def sy(v):
        return pad_t + plot_h - (v - lo) / (hi - lo) * plot_h

    COLORS = {"PI": "#34d399", "1X": "#f87171",
              "Agility": "#60a5fa", "Boston Dynamics": "#a78bfa"}

    lines = ""
    for partner, profile in PARTNER_PROFILES.items():
        series = _forecast_series(profile["breach_prob_pct"], profile["trend"], days)
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(series))
        c = COLORS[partner]
        lines += f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>\n'
        # end dot
        last_x, last_y = sx(days - 1), sy(series[-1])
        lines += f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="{c}"/>\n'

    # SLA risk threshold line (25% = warning)
    ry = sy(25.0)
    lines += (f'<line x1="{pad_l}" y1="{ry:.1f}" x2="{W - pad_r}" y2="{ry:.1f}" '
              f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="5 3"/>'
              f'<text x="{W - pad_r - 2}" y="{ry - 4:.1f}" fill="#f59e0b" font-size="9" '
              f'text-anchor="end">25% warning</text>\n')

    # grid + x-axis day labels
    x_labels = ""
    for i in range(days):
        label = f"D+{i}" if i > 0 else "Today"
        x_labels += (f'<text x="{sx(i):.1f}" y="{H - pad_b + 14}" fill="#94a3b8" '
                     f'font-size="9" text-anchor="middle">{label}</text>\n')
        x_labels += (f'<line x1="{sx(i):.1f}" y1="{pad_t}" x2="{sx(i):.1f}" '
                     f'y2="{H - pad_b}" stroke="#334155" stroke-width="0.5"/>\n')
    y_ticks = ""
    for v in [0, 5, 10, 15, 20, 25]:
        y_ticks += (f'<text x="{pad_l - 6}" y="{sy(v) + 4:.1f}" fill="#94a3b8" '
                    f'font-size="9" text-anchor="end">{v}%</text>\n')
        y_ticks += (f'<line x1="{pad_l}" y1="{sy(v):.1f}" x2="{W - pad_r}" '
                    f'y2="{sy(v):.1f}" stroke="#334155" stroke-width="0.5"/>\n')

    # legend
    legend = ""
    for i, (partner, color) in enumerate(COLORS.items()):
        lx = pad_l + i * 108
        legend += (f'<rect x="{lx}" y="{H - 14}" width="10" height="10" fill="{color}"/>'
                   f'<text x="{lx + 13}" y="{H - 4}" fill="#94a3b8" font-size="9">{partner}</text>\n')

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#0f172a"/>'
        f'<rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#1e293b"/>'
        + y_ticks + x_labels + lines
        + f'<text x="{W // 2}" y="{pad_t - 8}" fill="#e2e8f0" font-size="12" font-weight="bold" '
          f'text-anchor="middle">7-Day SLA Breach Probability Forecast</text>'
        + f'<text x="{pad_l - 42}" y="{pad_t + plot_h // 2}" fill="#94a3b8" font-size="10" '
          f'text-anchor="middle" transform="rotate(-90,{pad_l - 42},{pad_t + plot_h // 2})">Breach Prob (%)</text>'
        + legend
        + '</svg>'
    )


def build_html() -> str:
    svg = build_svg_timeline()
    partner_rows = ""
    for name, p in PARTNER_PROFILES.items():
        risk_color = "#f87171" if p["breach_prob_pct"] >= 20 else (
            "#facc15" if p["breach_prob_pct"] >= 8 else "#34d399")
        trend_icon = {"rising": "↑", "improving": "↓", "stable": "→"}.get(p["trend"], "")
        lat_color = "#f87171" if p["latency_p99_ms"] > SLA_THRESHOLDS["latency_p99_ms"] else "#34d399"
        partner_rows += (
            f'<tr>'
            f'<td>{name}</td>'
            f'<td style="color:{lat_color}">{p["latency_p99_ms"]} ms</td>'
            f'<td>{p["uptime_pct"]}%</td>'
            f'<td>{p["error_rate_pct"]}%</td>'
            f'<td style="color:{risk_color}">{p["breach_prob_pct"]}% {trend_icon}</td>'
            f'</tr>\n'
        )
    return f"""<!DOCTYPE html><html><head><title>SLA Breach Predictor</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.metric{{font-size:2rem;font-weight:bold;color:#C74634}}
.sub{{font-size:0.85rem;color:#94a3b8;margin-top:2px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.badge-green{{background:#064e3b;color:#34d399;padding:2px 8px;border-radius:4px;font-size:0.8rem}}
.badge-red{{background:#450a0a;color:#f87171;padding:2px 8px;border-radius:4px;font-size:0.8rem}}
</style></head>
<body>
<h1>SLA Breach Predictor</h1>
<p style="color:#94a3b8">7-day breach probability forecast per partner per SLA type. Port {PORT}</p>
<div class="grid">
  <div class="card"><div class="metric">1.2%</div><div class="sub">PI breach probability (healthy) <span class="badge-green">OK</span></div></div>
  <div class="card"><div class="metric">23%</div><div class="sub">1X latency SLA risk <span class="badge-red">AT RISK</span></div></div>
  <div class="card"><div class="metric">0</div><div class="sub">SLA breaches in last 30 days</div></div>
</div>
<div class="card">
  <h2>Breach Probability Timeline (7-day forecast)</h2>
  {svg}
</div>
<div class="card">
  <h2>Partner SLA Status</h2>
  <table>
    <tr><th>Partner</th><th>Latency p99</th><th>Uptime</th><th>Error Rate</th><th>Breach Prob (7d)</th></tr>
    {partner_rows}
  </table>
  <p style="color:#64748b;font-size:0.8rem;margin-top:8px">
    SLA thresholds: latency &lt; 400 ms | uptime &gt; 99.9% | error rate &lt; 0.5%
  </p>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="SLA Breach Predictor")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/forecast")
    def forecast():
        result = {}
        for partner, profile in PARTNER_PROFILES.items():
            series = _forecast_series(profile["breach_prob_pct"], profile["trend"])
            result[partner] = {
                "breach_prob_today_pct": profile["breach_prob_pct"],
                "7d_forecast": series,
                "trend": profile["trend"],
            }
        return {"partners": result, "sla_breaches_last_30d": KEY_METRICS["breaches_last_30d"]}

    @app.get("/partners/{partner_name}")
    def partner_detail(partner_name: str):
        p = PARTNER_PROFILES.get(partner_name)
        if not p:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Partner not found")
        return p


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
