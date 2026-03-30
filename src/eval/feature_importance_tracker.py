"""Feature Importance Tracker — FastAPI service on port 8328.

Tracks which input features most influence GR00T policy decisions
via attribution methods (SHAP-style importance).
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import math
import random
import json
from datetime import datetime

random.seed(42)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

FEATURES = [
    {"name": "wrist_rgb",      "importance": 0.41, "category": "vision"},
    {"name": "ee_xyz",         "importance": 0.28, "category": "proprioception"},
    {"name": "cube_pose",      "importance": 0.19, "category": "perception"},
    {"name": "overhead_rgb",   "importance": 0.14, "category": "vision"},
    {"name": "task_embedding", "importance": 0.09, "category": "language"},
    {"name": "gripper_state",  "importance": 0.07, "category": "proprioception"},
    {"name": "ee_xyz[2]",      "importance": 0.06, "category": "proprioception"},
    {"name": "cube_pose[z]",   "importance": 0.05, "category": "perception"},
    {"name": "joint_angles[4]","importance": 0.04, "category": "proprioception"},
    {"name": "joint_angles[5]","importance": 0.04, "category": "proprioception"},
    {"name": "joint_angles[6]","importance": 0.03, "category": "proprioception"},
    {"name": "joint_angles[7]","importance": 0.02, "category": "proprioception"},
]

FEATURE_PHASES = ["wrist_rgb", "ee_xyz", "cube_pose", "joint_angles"]
PHASE_STEPS = 100


def _phase_importance(feature: str, step: int) -> float:
    """Simulate phase-dependent importance across 100 episode steps."""
    # reach phase: 0-33, grasp phase: 34-66, lift phase: 67-100
    t = step / PHASE_STEPS
    if feature == "wrist_rgb":
        # always high but dips slightly at lift
        return max(0.05, 0.41 - 0.10 * math.sin(t * math.pi))
    elif feature == "ee_xyz":
        # rises sharply in grasp phase
        if 0.34 <= t <= 0.66:
            return 0.28 + 0.18 * math.sin((t - 0.34) / 0.32 * math.pi)
        return 0.28 - 0.08 * abs(t - 0.5)
    elif feature == "cube_pose":
        # peaks in lift phase
        if t >= 0.67:
            return 0.19 + 0.15 * ((t - 0.67) / 0.33)
        return 0.19 - 0.10 * (t / 0.67)
    elif feature == "joint_angles":
        # mostly flat, slight rise at start
        return 0.04 + 0.04 * math.exp(-t * 5)
    return 0.05


def _build_feature_bar_svg() -> str:
    """SHAP-style horizontal bar chart for 12 features sorted by importance."""
    features_sorted = sorted(FEATURES, key=lambda f: f["importance"], reverse=True)
    W, H = 620, 420
    margin = {"top": 40, "right": 20, "bottom": 30, "left": 130}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]
    bar_h = chart_h / len(features_sorted) - 4
    max_imp = 0.45

    CAT_COLORS = {
        "vision": "#38bdf8",
        "proprioception": "#C74634",
        "perception": "#a3e635",
        "language": "#f59e0b",
    }

    bars = ""
    for i, f in enumerate(features_sorted):
        y = margin["top"] + i * (bar_h + 4)
        bw = (f["importance"] / max_imp) * chart_w
        color = CAT_COLORS.get(f["category"], "#94a3b8")
        bars += (
            f'<rect x="{margin["left"]}" y="{y:.1f}" '
            f'width="{bw:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>\n'
        )
        bars += (
            f'<text x="{margin["left"] - 6}" y="{y + bar_h/2 + 4:.1f}" '
            f'fill="#cbd5e1" font-size="11" text-anchor="end">{f["name"]}</text>\n'
        )
        bars += (
            f'<text x="{margin["left"] + bw + 4}" y="{y + bar_h/2 + 4:.1f}" '
            f'fill="{color}" font-size="10">{f["importance"]:.2f}</text>\n'
        )

    # x-axis ticks
    ticks = ""
    for v in [0.0, 0.1, 0.2, 0.3, 0.4]:
        tx = margin["left"] + (v / max_imp) * chart_w
        ty = H - margin["bottom"] + 14
        ticks += (
            f'<line x1="{tx:.1f}" y1="{margin["top"]}" x2="{tx:.1f}" '
            f'y2="{H - margin["bottom"]}" stroke="#1e293b" stroke-width="1"/>\n'
        )
        ticks += (
            f'<text x="{tx:.1f}" y="{ty}" fill="#64748b" font-size="10" '
            f'text-anchor="middle">{v:.1f}</text>\n'
        )

    legend = ""
    lx = margin["left"]
    for cat, color in CAT_COLORS.items():
        legend += (
            f'<rect x="{lx}" y="{H - 16}" width="10" height="10" fill="{color}" rx="2"/>'
            f'<text x="{lx + 13}" y="{H - 7}" fill="#94a3b8" font-size="10">{cat}</text>'
        )
        lx += 100

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">\n'
        f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Feature Attribution (SHAP-style, avg over 200 episodes)</text>\n'
        + ticks + bars + legend +
        f'</svg>'
    )


def _build_phase_heatmap_svg() -> str:
    """Heatmap: feature importance across 100 episode steps (4 feature groups)."""
    W, H = 640, 260
    margin = {"top": 40, "right": 20, "bottom": 50, "left": 110}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]
    n_features = len(FEATURE_PHASES)
    n_steps = 50  # downsample to 50 columns for display
    cell_w = chart_w / n_steps
    cell_h = chart_h / n_features

    cells = ""
    for fi, feat in enumerate(FEATURE_PHASES):
        for si in range(n_steps):
            step = int(si / n_steps * PHASE_STEPS)
            imp = _phase_importance(feat, step)
            # map 0..0.6 to blue..orange heat
            norm = min(1.0, imp / 0.60)
            r = int(56 + norm * (199 - 56))
            g = int(189 + norm * (70 - 189))
            b = int(248 + norm * (52 - 248))
            x = margin["left"] + si * cell_w
            y = margin["top"] + fi * cell_h
            cells += (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w + 0.5:.1f}" '
                f'height="{cell_h:.1f}" fill="rgb({r},{g},{b})"/>\n'
            )
        # feature label
        cells += (
            f'<text x="{margin["left"] - 6}" y="{margin["top"] + fi * cell_h + cell_h/2 + 4:.1f}" '
            f'fill="#cbd5e1" font-size="11" text-anchor="end">{feat}</text>\n'
        )

    # phase separators + labels
    phase_labels = [(0, "Reach"), (33, "Grasp"), (66, "Lift")]
    for pstart, plabel in phase_labels:
        px = margin["left"] + (pstart / PHASE_STEPS) * chart_w
        cells += (
            f'<line x1="{px:.1f}" y1="{margin["top"]}" x2="{px:.1f}" '
            f'y2="{H - margin["bottom"]}" stroke="#f1f5f9" stroke-width="1.5" '
            f'stroke-dasharray="4,3"/>\n'
        )
        cells += (
            f'<text x="{px + 6}" y="{H - margin["bottom"] + 14}" '
            f'fill="#94a3b8" font-size="10">{plabel}</text>\n'
        )

    # colorbar legend
    grad_x = W - margin["right"] - 80
    grad_labels = ""
    for vi, (label, color) in enumerate([("low", "#38bdf8"), ("high", "#C74634")]):
        grad_labels += (
            f'<rect x="{grad_x + vi * 40}" y="{H - margin["bottom"] + 22}" '
            f'width="35" height="8" fill="{color}" rx="2"/>'
            f'<text x="{grad_x + vi * 40 + 17}" y="{H - margin["bottom"] + 44}" '
            f'fill="#64748b" font-size="9" text-anchor="middle">{label}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">\n'
        f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Feature Importance Across Episode Phases (Heatmap)</text>\n'
        + cells + grad_labels +
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    bar_svg = _build_feature_bar_svg()
    heatmap_svg = _build_phase_heatmap_svg()
    top3 = sorted(FEATURES, key=lambda f: f["importance"], reverse=True)[:3]
    top3_str = ", ".join(f["name"] for f in top3)
    total_imp = sum(f["importance"] for f in FEATURES)
    top3_share = sum(f["importance"] for f in top3) / total_imp
    redundancy = round(1.0 - len(set(f["category"] for f in FEATURES)) / len(FEATURES), 2)
    prune_savings = round(
        sum(f["importance"] for f in FEATURES if f["importance"] < 0.06) / total_imp * 100, 1
    )
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Feature Importance Tracker — Port 8328</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 14px 28px;
            display: flex; align-items: center; justify-content: space-between; }}
  header h1 {{ font-size: 1.2rem; color: #f1f5f9; }}
  header span {{ font-size: 0.8rem; color: #64748b; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px;
              padding: 20px 28px; }}
  .metric {{ background: #1e293b; border-radius: 8px; padding: 14px 18px;
             border-left: 3px solid #38bdf8; }}
  .metric .val {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; }}
  .metric .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
  .metric.warn .val {{ color: #f59e0b; }}
  .metric.warn {{ border-left-color: #f59e0b; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
             padding: 0 28px 28px; }}
  .chart-card {{ background: #1e293b; border-radius: 8px; padding: 16px; }}
  .chart-card h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;
                   text-transform: uppercase; letter-spacing: 0.05em; }}
  .chart-card svg {{ display: block; max-width: 100%; }}
  footer {{ padding: 10px 28px; font-size: 0.72rem; color: #475569; text-align: right; }}
</style>
</head>
<body>
<header>
  <h1>Feature Importance Tracker <span style="color:#C74634">GR00T Policy Attribution</span></h1>
  <span>Port 8328 &nbsp;|&nbsp; {now}</span>
</header>
<div class="metrics">
  <div class="metric">
    <div class="val">{top3_str[:22]}</div>
    <div class="lbl">Top-3 Features</div>
  </div>
  <div class="metric">
    <div class="val">{top3_share:.0%}</div>
    <div class="lbl">Top-3 Share of Total Importance</div>
  </div>
  <div class="metric warn">
    <div class="val">{redundancy}</div>
    <div class="lbl">Feature Redundancy Score</div>
  </div>
  <div class="metric">
    <div class="val">{prune_savings}%</div>
    <div class="lbl">Est. Compute Savings from Pruning</div>
  </div>
</div>
<div class="charts">
  <div class="chart-card">
    <h2>SHAP-style Feature Attribution (avg, 200 episodes)</h2>
    {bar_svg}
  </div>
  <div class="chart-card">
    <h2>Phase-Dependent Importance Shift</h2>
    {heatmap_svg}
  </div>
</div>
<footer>OCI Robot Cloud &nbsp;|&nbsp; Feature Importance Tracker v1.0 &nbsp;|&nbsp; cycle-67A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Feature Importance Tracker",
        description="Tracks GR00T policy input-feature attributions (SHAP-style).",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "feature_importance_tracker", "port": 8328}

    @app.get("/api/features")
    async def get_features():
        return {"features": FEATURES, "count": len(FEATURES)}

    @app.get("/api/phase-importance")
    async def get_phase_importance():
        data = {}
        for feat in FEATURE_PHASES:
            data[feat] = [
                {"step": s, "importance": round(_phase_importance(feat, s), 4)}
                for s in range(0, PHASE_STEPS + 1, 5)
            ]
        return {"phases": data, "phase_boundaries": {"reach": [0, 33], "grasp": [34, 66], "lift": [67, 100]}}

    @app.get("/api/metrics")
    async def get_metrics():
        top3 = sorted(FEATURES, key=lambda f: f["importance"], reverse=True)[:3]
        total_imp = sum(f["importance"] for f in FEATURES)
        return {
            "top_features": [f["name"] for f in top3],
            "top3_share": round(sum(f["importance"] for f in top3) / total_imp, 3),
            "redundancy_score": round(1.0 - len(set(f["category"] for f in FEATURES)) / len(FEATURES), 2),
            "pruning_savings_pct": round(
                sum(f["importance"] for f in FEATURES if f["importance"] < 0.06) / total_imp * 100, 1
            ),
            "vision_dominance": round(
                sum(f["importance"] for f in FEATURES if f["category"] == "vision") / total_imp, 3
            ),
        }

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8328)
    else:
        print("FastAPI not available — falling back to stdlib http.server on port 8328")
        with socketserver.TCPServer(("", 8328), _Handler) as httpd:
            httpd.serve_forever()
