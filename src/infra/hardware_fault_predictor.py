try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Hardware Fault Predictor", version="1.0.0")

# Fault probability data per GPU node — 90-day rolling window (sampled at 10-day intervals)
NODES = [
    {
        "name": "Phoenix GPU1",
        "region": "phoenix",
        "gpu_type": "A100_40GB",
        "fault_prob_90d": [2, 3, 4, 5, 7, 9, 11, 14, 18, 23],  # crosses WARN at day ~80
        "current_prob_30d": 23,
        "status": "WARN",
        "color": "#C74634",
    },
    {
        "name": "Ashburn GPU4",
        "region": "ashburn",
        "gpu_type": "A100_80GB",
        "fault_prob_90d": [1, 1, 2, 2, 3, 3, 3, 4, 4, 4],
        "current_prob_30d": 4,
        "status": "OK",
        "color": "#22c55e",
    },
    {
        "name": "Frankfurt GPU2",
        "region": "frankfurt",
        "gpu_type": "A100_80GB",
        "fault_prob_90d": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "current_prob_30d": 12,
        "status": "OK",
        "color": "#38bdf8",
    },
    {
        "name": "Singapore GPU3",
        "region": "singapore",
        "gpu_type": "A100_40GB",
        "fault_prob_90d": [2, 2, 3, 4, 5, 6, 7, 7, 8, 9],
        "current_prob_30d": 9,
        "status": "OK",
        "color": "#a855f7",
    },
]

FEATURES = [
    {"name": "ECC errors",       "shap": 0.41, "color": "#C74634"},
    {"name": "temp_trend",       "shap": 0.28, "color": "#f97316"},
    {"name": "power_variance",   "shap": 0.17, "color": "#f59e0b"},
    {"name": "PCIe_correctable", "shap": 0.09, "color": "#38bdf8"},
    {"name": "fan_speed",        "shap": 0.05, "color": "#64748b"},
]

# Maintenance schedule: node, predicted_start_day, predicted_end_day, planned_start_day, planned_end_day
MAINT_SCHEDULE = [
    {"node": "Phoenix GPU1",  "pred_s": 80, "pred_e": 85, "plan_s": 84, "plan_e": 88},
    {"node": "Ashburn GPU4",  "pred_s": 95, "pred_e": 98, "plan_s": 95, "plan_e": 99},
    {"node": "Frankfurt GPU2","pred_s": 88, "pred_e": 91, "plan_s": 90, "plan_e": 94},
    {"node": "Singapore GPU3","pred_s": 92, "pred_e": 95, "plan_s": 93, "plan_e": 97},
]
GANTT_COLORS = ["#C74634", "#22c55e", "#38bdf8", "#a855f7"]

DAY_LABELS = ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90"]


def _build_probability_timeline_svg() -> str:
    W, H = 720, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 180, 20, 38
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n_pts = 10
    y_max = 35

    def xp(i):
        return PAD_L + i / (n_pts - 1) * inner_w

    def yp(v):
        return PAD_T + inner_h - v / y_max * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Grid and axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>')

    for v in (5, 10, 15, 20, 25, 30, 35):
        gy = yp(v)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+inner_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{gy+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{v}%</text>')

    # Threshold lines
    warn_y = yp(15)
    crit_y = yp(30)
    lines.append(f'<line x1="{PAD_L}" y1="{warn_y:.1f}" x2="{PAD_L+inner_w}" y2="{warn_y:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="8,4"/>')
    lines.append(f'<text x="{PAD_L+inner_w+4}" y="{warn_y+4:.1f}" fill="#f59e0b" font-size="10">WARN 15%</text>')
    lines.append(f'<line x1="{PAD_L}" y1="{crit_y:.1f}" x2="{PAD_L+inner_w}" y2="{crit_y:.1f}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="8,4"/>')
    lines.append(f'<text x="{PAD_L+inner_w+4}" y="{crit_y+4:.1f}" fill="#ef4444" font-size="10">CRIT 30%</text>')

    # X labels
    for i, label in enumerate(DAY_LABELS):
        lx = xp(i)
        lines.append(f'<text x="{lx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">d{label}</text>')

    # Lines per node
    for node in NODES:
        pts = node["fault_prob_90d"]
        color = node["color"]
        coords = [(xp(i), yp(pts[i])) for i in range(n_pts)]
        d = " ".join(f"{'M' if i == 0 else 'L'}{cx:.1f},{cy:.1f}" for i, (cx, cy) in enumerate(coords))
        lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        for cx, cy in coords:
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="{color}"/>')

    # Legend (right side)
    lx = PAD_L + inner_w + 54
    lines.append(f'<text x="{lx}" y="{PAD_T+10}" fill="#64748b" font-size="10" font-weight="600">Nodes</text>')
    for ni, node in enumerate(NODES):
        ly = PAD_T + 24 + ni * 20
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="16" height="3" fill="{node["color"]}" rx="1"/>')
        lines.append(f'<text x="{lx+20}" y="{ly}" fill="#94a3b8" font-size="10">{node["name"]}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _build_feature_importance_svg() -> str:
    W, H = 560, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 80, 15, 28
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(FEATURES)
    bar_h = max(14, inner_h // n - 6)
    gap = (inner_h - bar_h * n) // (n + 1)
    max_shap = 0.45

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]

    for v in (0.1, 0.2, 0.3, 0.4):
        gx = PAD_L + v / max_shap * inner_w
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{v:.1f}</text>')

    for i, feat in enumerate(FEATURES):
        y = PAD_T + gap + i * (bar_h + gap)
        bw = feat["shap"] / max_shap * inner_w
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{feat["color"]}" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{feat["name"]}</text>')
        lines.append(f'<text x="{PAD_L+bw+5:.1f}" y="{y+bar_h//2+4}" fill="#94a3b8" font-size="10">{feat["shap"]:.2f}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _build_gantt_svg() -> str:
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 30, 20, 38
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(MAINT_SCHEDULE)
    row_h = inner_h // n
    day_range = 100  # 0..100 days

    def xd(day):
        return PAD_L + day / day_range * inner_w

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]

    # Vertical day markers
    for d in range(0, 101, 10):
        gx = xd(d)
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">d{d}</text>')

    # Draw bars per row
    bar_h = row_h // 2 - 2
    for i, m in enumerate(MAINT_SCHEDULE):
        color = GANTT_COLORS[i]
        cy = PAD_T + i * row_h + row_h // 4

        # Planned bar (background, muted)
        px1 = xd(m["plan_s"])
        pw = xd(m["plan_e"]) - px1
        lines.append(f'<rect x="{px1:.1f}" y="{cy}" width="{pw:.1f}" height="{bar_h}" fill="#334155" rx="3"/>')
        lines.append(f'<text x="{px1+pw+4:.1f}" y="{cy+bar_h//2+4}" fill="#475569" font-size="9">planned</text>')

        # Predicted bar (colored)
        qx1 = xd(m["pred_s"])
        qw = xd(m["pred_e"]) - qx1
        lines.append(f'<rect x="{qx1:.1f}" y="{cy}" width="{qw:.1f}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>')

        # Savings indicator (overlap = savings)
        overlap_start = max(m["pred_s"], m["plan_s"])
        overlap_end = min(m["pred_e"], m["plan_e"])
        if overlap_end > overlap_start:
            ox1 = xd(overlap_start)
            ow = xd(overlap_end) - ox1
            lines.append(f'<rect x="{ox1:.1f}" y="{cy}" width="{ow:.1f}" height="{bar_h}" fill="#22c55e" rx="2" opacity="0.4"/>')

        # Row label
        lines.append(f'<text x="{PAD_L-6}" y="{cy+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{m["node"]}</text>')

    # Legend
    lx = PAD_L + 4
    ly = PAD_T + inner_h + 26
    lines.append(f'<rect x="{lx}" y="{ly-8}" width="12" height="8" fill="#C74634" rx="2" opacity="0.85"/>')
    lines.append(f'<text x="{lx+16}" y="{ly}" fill="#94a3b8" font-size="9">Predicted</text>')
    lines.append(f'<rect x="{lx+90}" y="{ly-8}" width="12" height="8" fill="#334155" rx="2"/>')
    lines.append(f'<text x="{lx+106}" y="{ly}" fill="#94a3b8" font-size="9">Planned</text>')
    lines.append(f'<rect x="{lx+180}" y="{ly-8}" width="12" height="8" fill="#22c55e" rx="2" opacity="0.4"/>')
    lines.append(f'<text x="{lx+196}" y="{ly}" fill="#94a3b8" font-size="9">Overlap = Savings</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def build_html() -> str:
    svg_timeline = _build_probability_timeline_svg()
    svg_features = _build_feature_importance_svg()
    svg_gantt = _build_gantt_svg()

    warn_nodes = [n for n in NODES if n["status"] == "WARN"]
    warn_count = len(warn_nodes)

    node_cards = ""
    for n in NODES:
        status_bg = "#431407" if n["status"] == "WARN" else "#14532d"
        status_fg = "#C74634" if n["status"] == "WARN" else "#22c55e"
        node_cards += f"""
    <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:16px 20px;border-top:3px solid {n['color']};">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div>
          <div style="font-size:14px;font-weight:700;color:#f1f5f9;">{n['name']}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">{n['gpu_type']} &nbsp;|&nbsp; {n['region'].upper()}</div>
        </div>
        <span style="background:{status_bg};color:{status_fg};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{n['status']}</span>
      </div>
      <div>
        <div style="font-size:10px;color:#64748b;margin-bottom:4px;">FAULT PROB (30D)</div>
        <div style="font-size:28px;font-weight:700;color:{n['color']};">{n['current_prob_30d']}%</div>
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — Hardware Fault Predictor</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #C74634; }}
    .header .dot {{ width: 10px; height: 10px; border-radius: 50%; background: #38bdf8; box-shadow: 0 0 6px #38bdf8; animation: pulse 2s infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.4}} }}
    .sub {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
    .content {{ padding: 28px 32px; max-width: 1100px; margin: 0 auto; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 20px; }}
    .stat-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .stat-value {{ font-size: 28px; font-weight: 700; color: #f1f5f9; }}
    .stat-sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }}
    .chart-wrap {{ overflow-x: auto; }}
    .node-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }}
    .footer {{ text-align: center; padding: 20px; font-size: 11px; color: #334155; border-top: 1px solid #1e293b; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="header">
    <div class="dot"></div>
    <div>
      <h1>Hardware Fault Predictor</h1>
      <div class="sub">OCI Robot Cloud — GPU Health Forecasting — 90-Day Rolling Window</div>
    </div>
  </div>
  <div class="content">

    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Phoenix GPU1 (30d)</div>
        <div class="stat-value" style="color:#C74634;">23%</div>
        <div class="stat-sub">fault probability — WARN</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Ashburn GPU4 (30d)</div>
        <div class="stat-value" style="color:#22c55e;">4%</div>
        <div class="stat-sub">fault probability — OK</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Downtime Cost Avoided</div>
        <div class="stat-value" style="color:#38bdf8;">$840</div>
        <div class="stat-sub">proactive maintenance savings</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Unplanned Savings</div>
        <div class="stat-value">4.2h</div>
        <div class="stat-sub">per proactive intervention</div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Fault Probability Timeline (90-Day Rolling)</div>
      <div class="chart-wrap">{svg_timeline}</div>
    </div>

    <div class="section" style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start;">
      <div>
        <div class="section-title">SHAP Feature Importance</div>
        <div class="chart-wrap">{svg_features}</div>
      </div>
      <div>
        <div class="section-title">Node Status</div>
        <div class="node-grid">{node_cards}</div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Maintenance Schedule Gantt — Predicted vs Planned (Days from Now)</div>
      <div class="chart-wrap">{svg_gantt}</div>
    </div>

  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud Hardware Fault Predictor | Port 8616</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return build_html()


@app.get("/nodes")
def list_nodes():
    return JSONResponse(content=[
        {
            "name": n["name"],
            "region": n["region"],
            "gpu_type": n["gpu_type"],
            "fault_prob_30d_pct": n["current_prob_30d"],
            "status": n["status"],
            "fault_prob_90d_series": n["fault_prob_90d"],
        }
        for n in NODES
    ])


@app.get("/features")
def feature_importance():
    return JSONResponse(content=[
        {"feature": f["name"], "shap_value": f["shap"]}
        for f in FEATURES
    ])


@app.get("/maintenance")
def maintenance_schedule():
    return JSONResponse(content=MAINT_SCHEDULE)


@app.get("/summary")
def summary():
    warn_nodes = [n["name"] for n in NODES if n["status"] == "WARN"]
    return JSONResponse(content={
        "total_nodes": len(NODES),
        "warn_nodes": warn_nodes,
        "warn_count": len(warn_nodes),
        "critical_count": 0,
        "downtime_cost_avoided_usd": 840,
        "avg_unplanned_downtime_saved_hr": 4.2,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


@app.get("/health")
def health():
    return JSONResponse(content={
        "status": "ok",
        "service": "hardware_fault_predictor",
        "port": 8616,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


def main():
    uvicorn.run("hardware_fault_predictor:app", host="0.0.0.0", port=8616, reload=False)


if __name__ == "__main__":
    main()
