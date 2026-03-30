"""Sim-to-Real Transfer Gap Validator — port 8139."""

import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

app = FastAPI(title="Sim-to-Real Validator", version="1.0.0") if FastAPI else None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

METRICS = [
    {"name": "task_success_rate",          "sim": 0.78, "real": 0.52, "gap": -0.26, "severity": "HIGH",   "higher_is_better": True,  "unit": "",   "notes": "Lighting variation main cause"},
    {"name": "grasp_stability",             "sim": 0.91, "real": 0.74, "gap": -0.17, "severity": "MEDIUM", "higher_is_better": True,  "unit": "",   "notes": "Gripper compliance model imperfect"},
    {"name": "collision_rate",              "sim": 0.04, "real": 0.09, "gap": +0.05, "severity": "MEDIUM", "higher_is_better": False, "unit": "",   "notes": "Unmodeled friction in real world"},
    {"name": "inference_latency_ms",        "sim": 226,  "real": 238,  "gap": +12,   "severity": "LOW",    "higher_is_better": False, "unit": "ms", "notes": "Sensor pipeline adds 12ms"},
    {"name": "episode_length_steps",        "sim": 847,  "real": 923,  "gap": +76,   "severity": "LOW",    "higher_is_better": False, "unit": "",   "notes": "Real robot moves more conservatively"},
    {"name": "recovery_rate",               "sim": 0.43, "real": 0.21, "gap": -0.22, "severity": "HIGH",   "higher_is_better": True,  "unit": "",   "notes": "Recovery policy undertrained in sim"},
    {"name": "object_localization_err_mm",  "sim": 3.2,  "real": 8.7,  "gap": +5.5,  "severity": "HIGH",   "higher_is_better": False, "unit": "mm", "notes": "Depth sensor noise not simulated"},
    {"name": "joint_tracking_error_deg",    "sim": 0.8,  "real": 1.4,  "gap": +0.6,  "severity": "LOW",    "higher_is_better": False, "unit": "°",  "notes": "Motor deadband not modeled"},
]

MITIGATIONS = [
    {
        "id": "M1",
        "title": "Domain Randomization: Lighting",
        "target_metric": "task_success_rate",
        "description": "Expand Isaac Sim lighting randomization range (0.1x-3.0x intensity, 2700K-6500K color temp). Expected +0.12 improvement.",
        "effort": "Medium",
        "impact": "High",
    },
    {
        "id": "M2",
        "title": "Real Gripper Data Collection",
        "target_metric": "grasp_stability",
        "description": "Collect 500 real-robot grasp demos with force/torque sensors to improve gripper compliance model in sim.",
        "effort": "High",
        "impact": "High",
    },
    {
        "id": "M3",
        "title": "Depth Sensor Noise Injection",
        "target_metric": "object_localization_err_mm",
        "description": "Profile RealSense D435i noise at 0.3–1.5m range; inject calibrated Gaussian + structured noise during sim training.",
        "effort": "Low",
        "impact": "High",
    },
    {
        "id": "M4",
        "title": "Recovery Scenario Expansion",
        "target_metric": "recovery_rate",
        "description": "Generate 10k adversarial recovery episodes in sim (dropped grasps, partial contacts). DAgger fine-tune on failures.",
        "effort": "Medium",
        "impact": "High",
    },
]

OVERALL_SCORE = 67
OVERALL_STATUS = "NEEDS_IMPROVEMENT"

# ---------------------------------------------------------------------------
# Normalise metrics to [0, 1] for chart (1 = best possible outcome)
# ---------------------------------------------------------------------------

# Normalisation bounds per metric
_NORM = {
    "task_success_rate":         (0.0, 1.0),
    "grasp_stability":           (0.0, 1.0),
    "collision_rate":            (0.0, 0.20),
    "inference_latency_ms":      (200, 300),
    "episode_length_steps":      (700, 1100),
    "recovery_rate":             (0.0, 1.0),
    "object_localization_err_mm":(0.0, 15.0),
    "joint_tracking_error_deg":  (0.0, 3.0),
}


def _normalise(m):
    """Return (sim_norm, real_norm) where 1=best."""
    lo, hi = _NORM.get(m["name"], (0, 1))
    rng = hi - lo if hi != lo else 1
    sv = (m["sim"] - lo) / rng
    rv = (m["real"] - lo) / rng
    sv = max(0.0, min(1.0, sv))
    rv = max(0.0, min(1.0, rv))
    if not m["higher_is_better"]:
        sv, rv = 1 - sv, 1 - rv
    return sv, rv


# ---------------------------------------------------------------------------
# SVG chart generators
# ---------------------------------------------------------------------------

def _grouped_bar_svg() -> str:
    """Grouped bar chart sim vs real (normalised), 680x220."""
    W, H = 680, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 24, 52
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(METRICS)
    group_w = chart_w / n
    bar_w = group_w * 0.30

    bars = ""
    x_labels = ""
    for i, m in enumerate(METRICS):
        sv, rv = _normalise(m)
        gx = PAD_L + i * group_w
        # sim bar
        sbh = sv * chart_h
        sbx = gx + group_w * 0.10
        sby = PAD_T + chart_h - sbh
        bars += f'<rect x="{sbx:.1f}" y="{sby:.1f}" width="{bar_w:.1f}" height="{sbh:.1f}" fill="#38bdf8" rx="2"/>'
        # real bar
        rbh = rv * chart_h
        rbx = sbx + bar_w + 2
        rby = PAD_T + chart_h - rbh
        bars += f'<rect x="{rbx:.1f}" y="{rby:.1f}" width="{bar_w:.1f}" height="{rbh:.1f}" fill="#C74634" rx="2"/>'
        # value labels
        sim_disp = m["sim"]
        real_disp = m["real"]
        bars += f'<text x="{sbx+bar_w/2:.1f}" y="{sby-3:.1f}" fill="#38bdf8" font-size="8" text-anchor="middle">{sim_disp}</text>'
        bars += f'<text x="{rbx+bar_w/2:.1f}" y="{rby-3:.1f}" fill="#C74634" font-size="8" text-anchor="middle">{real_disp}</text>'
        # x label
        short = m["name"].replace("_", " ")[:14]
        cx = gx + group_w / 2
        x_labels += f'<text x="{cx:.1f}" y="{H-34}" fill="#94a3b8" font-size="8" text-anchor="end" transform="rotate(-35,{cx:.1f},{H-34})">{short}</text>'

    # gridlines
    grid = ""
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = PAD_T + chart_h - v * chart_h
        pct = int(v * 100)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{pct}%</text>'

    svg = f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  {grid}
  {bars}
  {x_labels}
  <text x="{PAD_L+chart_w//2}" y="14" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="monospace">Sim vs Real Performance (normalised, higher=better)</text>
  <rect x="460" y="4" width="10" height="10" fill="#38bdf8"/><text x="474" y="13" fill="#94a3b8" font-size="10">Sim</text>
  <rect x="500" y="4" width="10" height="10" fill="#C74634"/><text x="514" y="13" fill="#94a3b8" font-size="10">Real</text>
</svg>"""
    return svg


def _heatmap_svg() -> str:
    """Gap severity heatmap, 680x120."""
    W, H = 680, 120
    n = len(METRICS)
    cell_w = W / n
    cell_h = 72
    PAD_T = 24

    sev_color = {"HIGH": "#C74634", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}

    cells = ""
    for i, m in enumerate(METRICS):
        cx = i * cell_w
        col = sev_color.get(m["severity"], "#64748b")
        gap_str = f"{m['gap']:+.2f}" if abs(m["gap"]) < 100 else f"{m['gap']:+.0f}"
        short = m["name"].replace("_", " ")[:12]
        cells += f'<rect x="{cx+2:.1f}" y="{PAD_T}" width="{cell_w-4:.1f}" height="{cell_h}" fill="{col}" rx="6" opacity="0.85"/>'
        cells += f'<text x="{cx+cell_w/2:.1f}" y="{PAD_T+22}" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">{m["severity"]}</text>'
        cells += f'<text x="{cx+cell_w/2:.1f}" y="{PAD_T+39}" fill="#fff" font-size="13" font-weight="bold" text-anchor="middle">{gap_str}</text>'
        cells += f'<text x="{cx+cell_w/2:.1f}" y="{PAD_T+57}" fill="rgba(255,255,255,0.75)" font-size="8" text-anchor="middle">{short}</text>'

    svg = f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="16" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="monospace">Gap Severity Heatmap</text>
  {cells}
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    bar_svg = _grouped_bar_svg()
    heat_svg = _heatmap_svg()

    score_color = "#C74634" if OVERALL_SCORE < 70 else ("#f59e0b" if OVERALL_SCORE < 85 else "#22c55e")

    metric_rows = ""
    sev_badge = {"HIGH": "background:#C74634", "MEDIUM": "background:#f59e0b;color:#0f172a", "LOW": "background:#22c55e;color:#0f172a"}
    for m in METRICS:
        gap_col = "#ef4444" if abs(m["gap"]) > 0.2 or (m["severity"] == "HIGH") else ("#f59e0b" if m["severity"] == "MEDIUM" else "#22c55e")
        metric_rows += f"""
        <tr>
          <td style="color:#38bdf8">{m['name']}</td>
          <td>{m['sim']}{m['unit']}</td>
          <td>{m['real']}{m['unit']}</td>
          <td style="color:{gap_col}">{m['gap']:+.2f}{m['unit'] if abs(m['gap'])<100 else ''}</td>
          <td><span style="{sev_badge.get(m['severity'],'')};padding:2px 8px;border-radius:9999px;font-size:11px">{m['severity']}</span></td>
          <td style="color:#94a3b8;font-size:12px">{m['notes']}</td>
        </tr>"""

    mit_cards = ""
    impact_col = {"High": "#C74634", "Medium": "#f59e0b", "Low": "#22c55e"}
    for mit in MITIGATIONS:
        mit_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px;border-left:3px solid #38bdf8">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="color:#38bdf8;font-weight:bold">{mit['id']}: {mit['title']}</span>
            <span style="color:{impact_col.get(mit['impact'],'#fff')};font-size:12px">Impact: {mit['impact']}</span>
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-bottom:4px">Target: {mit['target_metric']}</div>
          <div style="color:#cbd5e1;font-size:12px">{mit['description']}</div>
          <div style="color:#64748b;font-size:11px;margin-top:6px">Effort: {mit['effort']}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim-to-Real Validator — Port 8139</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
    .score-box {{ background: #1e293b; border-radius: 12px; padding: 20px 28px; margin-bottom: 24px;
                  display: flex; align-items: center; gap: 24px; border: 2px solid {score_color}; }}
    .score-num {{ font-size: 56px; font-weight: bold; color: {score_color}; line-height: 1; }}
    .score-label {{ color: #94a3b8; font-size: 13px; }}
    .score-status {{ color: {score_color}; font-size: 18px; font-weight: bold; margin-top: 4px; }}
    .section {{ margin-bottom: 28px; }}
    h2 {{ color: #cbd5e1; font-size: 15px; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #94a3b8; text-align: left; padding: 8px; border-bottom: 1px solid #1e293b; font-weight: 500; }}
    td {{ padding: 8px; border-bottom: 1px solid #0f172a; }}
    tr:hover td {{ background: #1e293b; }}
    .mit-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  </style>
</head>
<body>
  <h1>Sim-to-Real Transfer Gap Validator</h1>
  <div class="sub">OCI Robot Cloud — GR00T N1.6 | Port 8139 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="score-box">
    <div class="score-num">{OVERALL_SCORE}</div>
    <div>
      <div class="score-label">Overall Sim-to-Real Transfer Score (out of 100)</div>
      <div class="score-status">{OVERALL_STATUS}</div>
      <div style="color:#64748b;font-size:12px;margin-top:6px">3 HIGH severity gaps require attention before production deployment</div>
    </div>
  </div>

  <div class="section">
    <h2>Performance Comparison</h2>
    {bar_svg}
  </div>

  <div class="section">
    <h2>Gap Severity Heatmap</h2>
    {heat_svg}
  </div>

  <div class="section">
    <h2>Validation Metrics</h2>
    <table>
      <thead><tr><th>Metric</th><th>Sim</th><th>Real</th><th>Gap</th><th>Severity</th><th>Notes</th></tr></thead>
      <tbody>{metric_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Mitigation Recommendations</h2>
    <div class="mit-grid">{mit_cards}</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if app:
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/metrics")
    async def get_metrics():
        return {"metrics": METRICS, "count": len(METRICS)}

    @app.get("/summary")
    async def get_summary():
        high = sum(1 for m in METRICS if m["severity"] == "HIGH")
        medium = sum(1 for m in METRICS if m["severity"] == "MEDIUM")
        low = sum(1 for m in METRICS if m["severity"] == "LOW")
        return {
            "overall_score": OVERALL_SCORE,
            "status": OVERALL_STATUS,
            "severity_counts": {"HIGH": high, "MEDIUM": medium, "LOW": low},
            "total_metrics": len(METRICS),
            "service": "sim-to-real-validator",
            "port": 8139,
        }

    @app.get("/recommendations")
    async def get_recommendations():
        return {"mitigations": MITIGATIONS, "count": len(MITIGATIONS)}


if __name__ == "__main__":
    if uvicorn:
        uvicorn.run(app, host="0.0.0.0", port=8139)
    else:
        print("uvicorn not installed — run: pip install fastapi uvicorn")
