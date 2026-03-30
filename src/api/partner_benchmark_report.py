"""
Partner Benchmark Report — port 8679
OCI Robot Cloud | cycle-155A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ── data ──────────────────────────────────────────────────────────────────────

PARTNERS = ["PI", "Apt", "1X", "Franka", "Unitree"]

# KPI data: SR, latency(ms), cost_per_run($), uptime(%)
KPI_CURRENT = {
    "PI":      {"sr": 0.82, "latency": 195, "cost": 0.018, "uptime": 99.7},
    "Apt":     {"sr": 0.71, "latency": 231, "cost": 0.022, "uptime": 99.1},
    "1X":      {"sr": 0.64, "latency": 248, "cost": 0.031, "uptime": 98.6},
    "Franka":  {"sr": 0.58, "latency": 263, "cost": 0.027, "uptime": 98.9},
    "Unitree": {"sr": 0.61, "latency": 255, "cost": 0.029, "uptime": 99.0},
}
KPI_PREV = {
    "PI":      {"sr": 0.71, "latency": 212, "cost": 0.022, "uptime": 99.3},
    "Apt":     {"sr": 0.64, "latency": 251, "cost": 0.026, "uptime": 98.7},
    "1X":      {"sr": 0.64, "latency": 250, "cost": 0.031, "uptime": 98.5},
    "Franka":  {"sr": 0.53, "latency": 278, "cost": 0.030, "uptime": 98.6},
    "Unitree": {"sr": 0.56, "latency": 261, "cost": 0.031, "uptime": 98.8},
}

# Competitive: OCI, CompA, CompB, CompC, DGX
# Metrics (normalized 0-1, higher=better): SR, speed(inv-latency), cost-eff(inv), uptime
COMP_ENTITIES = ["OCI", "CompA", "CompB", "CompC", "DGX"]
COMP_METRICS  = ["SR", "Speed", "Cost Eff.", "Uptime"]
COMP_DATA = {
    "OCI":   [0.82, 0.88, 0.96, 0.997],
    "CompA": [0.74, 0.71, 0.62, 0.981],
    "CompB": [0.68, 0.65, 0.57, 0.976],
    "CompC": [0.61, 0.59, 0.51, 0.968],
    "DGX":   [0.78, 0.82, 0.41, 0.989],
}

# SR velocity Apr-Jun 2026
MONTHS = ["Apr", "May", "Jun"]
VELOCITY = {
    "PI":      [0.74, 0.78, 0.82],
    "Apt":     [0.65, 0.68, 0.71],
    "1X":      [0.63, 0.63, 0.64],
    "Franka":  [0.54, 0.56, 0.58],
    "Unitree": [0.57, 0.59, 0.61],
}
LINE_COLORS = ["#C74634", "#38bdf8", "#f59e0b", "#a78bfa", "#22c55e"]

# ── SVG builders ──────────────────────────────────────────────────────────────

def svg_partner_kpi() -> str:
    """Grouped bars: 4 KPIs × 5 partners with QoQ arrows."""
    W, H = 680, 380
    PAD_L, PAD_T, PAD_R, PAD_B = 56, 50, 20, 60

    kpis = ["sr", "latency", "cost", "uptime"]
    kpi_labels = ["SR", "Latency (ms)", "Cost/Run ($)", "Uptime (%)"]
    # normalise each KPI to 0-1 for display height (higher bar = better)
    def norm(key, val):
        ranges = {
            "sr":      (0.0, 1.0),
            "latency": (150, 280),   # lower is better → invert
            "cost":    (0.01, 0.04), # lower is better → invert
            "uptime":  (98.0, 100.0),
        }
        lo, hi = ranges[key]
        n = (val - lo) / (hi - lo)
        if key in ("latency", "cost"):
            n = 1 - n
        return max(0.0, min(1.0, n))

    P_COLORS = ["#C74634", "#38bdf8", "#f59e0b", "#a78bfa", "#22c55e"]
    IW = W - PAD_L - PAD_R
    IH = H - PAD_T - PAD_B

    n_kpi = len(kpis)
    n_p   = len(PARTNERS)
    group_w = IW / n_kpi
    bar_w   = group_w * 0.14
    bar_gap = group_w * 0.02

    bars = ""
    for ki, key in enumerate(kpis):
        gx = PAD_L + ki * group_w
        for pi, partner in enumerate(PARTNERS):
            bx = gx + bar_gap + pi * (bar_w + bar_gap)
            cur = KPI_CURRENT[partner][key]
            prv = KPI_PREV[partner][key]
            nh  = norm(key, cur)
            bh  = nh * IH
            by  = PAD_T + IH - bh
            col = P_COLORS[pi]
            bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{col}" rx="2" fill-opacity="0.88"/>'
            # QoQ arrow
            improved = (cur > prv) if key != "latency" and key != "cost" else (cur < prv)
            arrow = "▲" if improved else ("▼" if cur != prv else "—")
            acol  = "#22c55e" if improved else ("#C74634" if cur != prv else "#64748b")
            bars += f'<text x="{bx + bar_w/2:.1f}" y="{by - 3:.1f}" text-anchor="middle" fill="{acol}" font-size="7">{arrow}</text>'
        # KPI label
        lx = gx + group_w / 2
        bars += f'<text x="{lx:.1f}" y="{PAD_T + IH + 18}" text-anchor="middle" fill="#94a3b8" font-size="11">{kpi_labels[ki]}</text>'

    # baseline
    base = f'<line x1="{PAD_L}" y1="{PAD_T+IH}" x2="{PAD_L+IW}" y2="{PAD_T+IH}" stroke="#475569" stroke-width="1"/>'

    # legend
    legend = ""
    for pi, p in enumerate(PARTNERS):
        lx = PAD_L + pi * (IW / n_p) + 8
        legend += (
            f'<rect x="{lx:.0f}" y="{H-16}" width="10" height="10" fill="{P_COLORS[pi]}" rx="2"/>'
            f'<text x="{lx+13:.0f}" y="{H-7}" fill="#cbd5e1" font-size="10">{p}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="26" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">Partner Quarterly KPI Comparison (▲/▼ = QoQ)</text>
  {base}{bars}{legend}
</svg>'''


def svg_competitive_position() -> str:
    """Grouped bars: 4 metrics × 5 entities (OCI clearly best on cost/SR)."""
    W, H = 620, 340
    PAD_L, PAD_T, PAD_R, PAD_B = 50, 50, 20, 56

    E_COLORS = {
        "OCI":   "#C74634",
        "CompA": "#38bdf8",
        "CompB": "#a78bfa",
        "CompC": "#f59e0b",
        "DGX":   "#64748b",
    }
    IW = W - PAD_L - PAD_R
    IH = H - PAD_T - PAD_B
    n_m = len(COMP_METRICS)
    n_e = len(COMP_ENTITIES)
    group_w = IW / n_m
    bar_w   = group_w * 0.15
    bar_gap = group_w * 0.02

    bars = ""
    for mi, metric in enumerate(COMP_METRICS):
        gx = PAD_L + mi * group_w
        for ei, ent in enumerate(COMP_ENTITIES):
            val = COMP_DATA[ent][mi]
            bh  = val * IH
            bx  = gx + bar_gap + ei * (bar_w + bar_gap)
            by  = PAD_T + IH - bh
            col = E_COLORS[ent]
            bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{col}" rx="2" fill-opacity="0.85"/>'
            if ent == "OCI":
                bars += f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" text-anchor="middle" fill="#C74634" font-size="7.5" font-weight="bold">{val:.2f}</text>'
        mx = gx + group_w / 2
        bars += f'<text x="{mx:.1f}" y="{PAD_T+IH+18}" text-anchor="middle" fill="#94a3b8" font-size="11">{metric}</text>'

    base = f'<line x1="{PAD_L}" y1="{PAD_T+IH}" x2="{PAD_L+IW}" y2="{PAD_T+IH}" stroke="#475569" stroke-width="1"/>'

    legend = ""
    for ei, ent in enumerate(COMP_ENTITIES):
        lx = PAD_L + ei * (IW / n_e) + 4
        legend += (
            f'<rect x="{lx:.0f}" y="{H-15}" width="10" height="10" fill="{E_COLORS[ent]}" rx="2"/>'
            f'<text x="{lx+13:.0f}" y="{H-6}" fill="#cbd5e1" font-size="10">{ent}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="26" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">Competitive Position — Normalised Metrics</text>
  <text x="{W//2}" y="40" text-anchor="middle" fill="#64748b" font-size="10">OCI leads on Cost Efficiency &amp; SR | 9.6× cheaper than DGX</text>
  {base}{bars}{legend}
</svg>'''


def svg_velocity() -> str:
    """SR improvement velocity — 5 lines Apr–Jun 2026."""
    W, H = 520, 340
    PAD_L, PAD_T, PAD_R, PAD_B = 60, 50, 30, 56

    IW = W - PAD_L - PAD_R
    IH = H - PAD_T - PAD_B
    Y_MIN, Y_MAX = 0.50, 0.90
    X_STEP = IW / (len(MONTHS) - 1)

    def px(i):    return PAD_L + i * X_STEP
    def py(v):    return PAD_T + IH * (1 - (v - Y_MIN) / (Y_MAX - Y_MIN))

    grid = ""
    for v in [0.5, 0.6, 0.7, 0.8, 0.9]:
        gy = py(v)
        grid += (
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+IW}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1.5"/>'
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+IW}" y2="{gy:.1f}" stroke="#334155" stroke-width="0.8" stroke-dasharray="3,3"/>'
            f'<text x="{PAD_L-8}" y="{gy+4:.1f}" text-anchor="end" fill="#64748b" font-size="9">{v:.1f}</text>'
        )

    lines_svg = ""
    for pi, (partner, vals) in enumerate(VELOCITY.items()):
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
        col = LINE_COLORS[pi]
        # gain rate label
        gain = vals[-1] - vals[0]
        gain_pp = gain / (len(MONTHS) - 1) * 100
        is_pi = partner == "PI"
        lines_svg += f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{2.4 if is_pi else 1.6}" stroke-linejoin="round"/>'
        for i, v in enumerate(vals):
            lines_svg += f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="{4 if is_pi else 3}" fill="{col}"/>'
        # end label
        ex = px(len(MONTHS)-1) + 5
        ey = py(vals[-1]) + 4
        lines_svg += f'<text x="{ex:.0f}" y="{ey:.0f}" fill="{col}" font-size="10">{partner}</text>'
        if partner == "PI":
            lines_svg += f'<text x="{ex:.0f}" y="{ey+11:.0f}" fill="{col}" font-size="9" opacity="0.8">+{gain_pp:.1f}pp/mo</text>'

    # x-axis labels
    x_labels = ""
    for i, m in enumerate(MONTHS):
        x_labels += f'<text x="{px(i):.1f}" y="{PAD_T+IH+16}" text-anchor="middle" fill="#94a3b8" font-size="11">{m} 2026</text>'

    axis = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+IH}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{PAD_T+IH}" x2="{PAD_L+IW}" y2="{PAD_T+IH}" stroke="#475569" stroke-width="1"/>'
    )

    # note
    note = (
        f'<text x="{W//2}" y="{H-10}" text-anchor="middle" fill="#475569" font-size="9">'
        f'PI steepest gain +3.7pp/mo | 1X flat | Q2 target PI→0.87</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="26" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">SR Improvement Velocity (Apr–Jun 2026)</text>
  {grid}{axis}{lines_svg}{x_labels}{note}
  <text x="16" y="{PAD_T+IH//2}" text-anchor="middle" fill="#64748b" font-size="10" transform="rotate(-90,16,{PAD_T+IH//2})">Success Rate</text>
</svg>'''

# ── HTML ──────────────────────────────────────────────────────────────────────

def build_html() -> str:
    kpi  = svg_partner_kpi()
    comp = svg_competitive_position()
    vel  = svg_velocity()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Partner Benchmark Report — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#f1f5f9;font-family:'Segoe UI',system-ui,sans-serif;padding:32px}}
  h1{{font-size:1.6rem;color:#38bdf8;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.9rem;margin-bottom:28px}}
  .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px 24px;min-width:170px}}
  .kpi .val{{font-size:2rem;font-weight:700;color:#C74634}}
  .kpi .lbl{{font-size:.8rem;color:#94a3b8;margin-top:2px}}
  .kpi.good .val{{color:#22c55e}}
  .kpi.blue .val{{color:#38bdf8}}
  .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px}}
  .card h2{{font-size:1rem;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
  svg{{width:100%;height:auto}}
  footer{{margin-top:36px;color:#475569;font-size:.8rem;text-align:center}}
</style>
</head>
<body>
<h1>Partner Benchmark Report</h1>
<p class="sub">OCI Robot Cloud — port 8679 | cycle-155A | Q2 2026</p>

<div class="kpi-row">
  <div class="kpi good"><div class="val">0.82</div><div class="lbl">PI SR (+11pp QoQ)</div></div>
  <div class="kpi blue"><div class="val">0.71</div><div class="lbl">Apt SR (+7pp QoQ)</div></div>
  <div class="kpi"><div class="val">0.64</div><div class="lbl">1X SR (flat QoQ)</div></div>
  <div class="kpi good"><div class="val">9.6×</div><div class="lbl">OCI Cheaper vs DGX</div></div>
  <div class="kpi blue"><div class="val">0.87</div><div class="lbl">PI Q2 Target SR</div></div>
</div>

<div class="charts">
  <div class="card"><h2>Partner KPI Comparison (QoQ)</h2>{kpi}</div>
  <div class="card"><h2>Competitive Position</h2>{comp}</div>
  <div class="card"><h2>SR Improvement Velocity</h2>{vel}</div>
</div>

<footer>OCI Robot Cloud &mdash; Partner Benchmark Report &mdash; Q2 2026</footer>
</body>
</html>"""

# ── app ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Partner Benchmark Report", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "partner_benchmark_report", "port": 8679})

    @app.get("/metrics")
    def metrics():
        return JSONResponse({
            "partners": KPI_CURRENT,
            "pi_sr_gain_pp": 11,
            "apt_sr_gain_pp": 7,
            "oci_cost_advantage_x": 9.6,
            "pi_q2_target_sr": 0.87,
        })

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8679)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status":"ok","service":"partner_benchmark_report","port":8679}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers(); self.wfile.write(body)

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", 8679), Handler).serve_forever()
