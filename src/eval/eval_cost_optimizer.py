"""Eval Cost Optimizer — FastAPI service on port 8301.

Optimizes evaluation frequency and scope to minimize cost while maintaining quality gates.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# Eval configurations: (name, cost_per_run, detection_coverage, runs_per_week)
EVAL_CONFIGS = [
    {"name": "safety_smoke_only",            "cost": 1.20, "coverage": 0.42, "weekly_cost": 2.40,  "runs_pw": 2, "pareto": False},
    {"name": "libero_quick",                 "cost": 2.10, "coverage": 0.61, "weekly_cost": 4.20,  "runs_pw": 2, "pareto": True},
    {"name": "libero_quick+safety_smoke",    "cost": 3.40, "coverage": 0.89, "weekly_cost": 6.80,  "runs_pw": 2, "pareto": True, "recommended": True},
    {"name": "libero_full",                  "cost": 5.20, "coverage": 0.83, "weekly_cost": 5.20,  "runs_pw": 1, "pareto": False},
    {"name": "libero_full+safety",           "cost": 6.80, "coverage": 0.93, "weekly_cost": 6.80,  "runs_pw": 1, "pareto": True},
    {"name": "SR_eval_1x",                   "cost": 18.70, "coverage": 0.71, "weekly_cost": 18.70, "runs_pw": 1, "pareto": False, "current": True},
    {"name": "SR_eval_2x",                   "cost": 18.70, "coverage": 0.71, "weekly_cost": 37.40, "runs_pw": 2, "pareto": False},
    {"name": "full_suite_weekly",            "cost": 18.70, "coverage": 0.97, "weekly_cost": 18.70, "runs_pw": 1, "pareto": True},
    {"name": "libero_quick+SR_smoke",        "cost": 4.80, "coverage": 0.78, "weekly_cost": 9.60,  "runs_pw": 2, "pareto": False},
    {"name": "safety_smoke_3x",              "cost": 1.20, "coverage": 0.55, "weekly_cost": 3.60,  "runs_pw": 3, "pareto": False},
    {"name": "libero_quick_3x",              "cost": 2.10, "coverage": 0.68, "weekly_cost": 6.30,  "runs_pw": 3, "pareto": False},
    {"name": "full_suite_monthly",           "cost": 18.70, "coverage": 0.97, "weekly_cost": 4.68,  "runs_pw": 0.25, "pareto": True},
]

# Frequency vs quality gate data (runs/week -> regression_detection_prob)
FREQ_CURVE = [
    (0.25, 0.31), (0.5, 0.47), (1.0, 0.63), (1.5, 0.74),
    (2.0, 0.82), (2.5, 0.87), (3.0, 0.90), (3.5, 0.92),
    (4.0, 0.93), (5.0, 0.94), (7.0, 0.95),
]

CURRENT_FREQ   = 1.0
RECOMMENDED_FREQ = 2.0
current_cfg = next(c for c in EVAL_CONFIGS if c.get("current"))
recommended_cfg = next(c for c in EVAL_CONFIGS if c.get("recommended"))

cost_per_detected = round(current_cfg["weekly_cost"] / (current_cfg["coverage"] * 10), 2)
rec_cost_per_detected = round(recommended_cfg["weekly_cost"] / (recommended_cfg["coverage"] * 10), 2)
fn_rate_current = round(1 - current_cfg["coverage"], 2)
fn_rate_rec     = round(1 - recommended_cfg["coverage"], 2)
coverage_cost_ratio = round(recommended_cfg["coverage"] / recommended_cfg["weekly_cost"], 4)

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_freq_quality_curve() -> str:
    W, H = 700, 360
    PL, PR, PT, PB = 70, 30, 30, 60
    cw = W - PL - PR
    ch = H - PT - PB

    def fx(v):  # runs/week 0..7
        return PL + (v / 7.0) * cw

    def fy(v):  # prob 0..1
        return PT + ch - v * ch

    # grid lines
    grid = ""
    for yv in [0.2, 0.4, 0.6, 0.8, 1.0]:
        y = fy(yv)
        grid += f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{PL-8}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yv:.1f}</text>'
    for xv in [1, 2, 3, 4, 5, 7]:
        x = fx(xv)
        grid += f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{H-PB}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{H-PB+16}" fill="#64748b" font-size="10" text-anchor="middle">{xv}</text>'

    # curve
    pts = " ".join(f"{fx(x):.1f},{fy(y):.1f}" for x, y in FREQ_CURVE)
    curve = f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'

    # shade area under curve (fill to bottom)
    fill_pts = f"{fx(FREQ_CURVE[0][0]):.1f},{fy(0):.1f} " + pts + f" {fx(FREQ_CURVE[-1][0]):.1f},{fy(0):.1f}"
    curve_fill = f'<polygon points="{fill_pts}" fill="#38bdf822"/>'

    # markers: current (1/week) and recommended (2/week)
    cur_x  = fx(CURRENT_FREQ)
    cur_y  = fy(0.63)
    rec_x  = fx(RECOMMENDED_FREQ)
    rec_y  = fy(0.82)

    markers = (
        f'<line x1="{cur_x:.1f}" y1="{PT}" x2="{cur_x:.1f}" y2="{H-PB}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,3"/>'
        f'<circle cx="{cur_x:.1f}" cy="{cur_y:.1f}" r="6" fill="#ef4444"/>'
        f'<text x="{cur_x+8:.1f}" y="{cur_y-8:.1f}" fill="#ef4444" font-size="11" font-family="monospace">Current 1×/wk (63%)</text>'
        f'<line x1="{rec_x:.1f}" y1="{PT}" x2="{rec_x:.1f}" y2="{H-PB}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
        f'<circle cx="{rec_x:.1f}" cy="{rec_y:.1f}" r="6" fill="#22c55e"/>'
        f'<text x="{rec_x+8:.1f}" y="{rec_y-8:.1f}" fill="#22c55e" font-size="11" font-family="monospace">Recommended 2×/wk (82%)</text>'
    )

    # axes labels
    axes = (
        f'<text x="{W//2}" y="{H-PB+38}" fill="#94a3b8" font-size="11" text-anchor="middle">Eval Runs / Week</text>'
        f'<text x="14" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{H//2})">Regression Detection Probability</text>'
        f'<text x="{W//2}" y="18" fill="#f8fafc" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Eval Frequency vs Quality Gate Reliability</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{grid}{curve_fill}{curve}{markers}{axes}
</svg>"""


def svg_cost_coverage_scatter() -> str:
    W, H = 700, 400
    PL, PR, PT, PB = 70, 30, 40, 60
    cw = W - PL - PR
    ch = H - PT - PB

    max_cost = 40.0
    def sx(v): return PL + (v / max_cost) * cw
    def sy(v): return PT + ch - v * ch  # coverage 0..1

    # grid
    grid = ""
    for yv in [0.2, 0.4, 0.6, 0.8, 1.0]:
        y = sy(yv)
        grid += f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{PL-8}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{yv:.1f}</text>'
    for xv in [5, 10, 15, 20, 25, 30, 37]:
        x = sx(xv)
        grid += f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{H-PB}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{H-PB+16}" fill="#64748b" font-size="10" text-anchor="middle">${xv}</text>'

    # Pareto frontier line
    pareto_pts = sorted(
        [(c["weekly_cost"], c["coverage"]) for c in EVAL_CONFIGS if c.get("pareto")],
        key=lambda t: t[0]
    )
    pf_pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pareto_pts)
    pareto_line = f'<polyline points="{pf_pts}" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>'

    # scatter points
    dots = ""
    for cfg in EVAL_CONFIGS:
        cx2 = sx(cfg["weekly_cost"])
        cy2 = sy(cfg["coverage"])
        is_rec = cfg.get("recommended", False)
        is_cur = cfg.get("current", False)
        is_par = cfg.get("pareto", False)
        color = "#C74634" if is_rec else ("#ef4444" if is_cur else ("#f59e0b" if is_par else "#475569"))
        r = 9 if (is_rec or is_cur) else 6
        dots += f'<circle cx="{cx2:.1f}" cy="{cy2:.1f}" r="{r}" fill="{color}" opacity="0.85"/>'
        if is_rec:
            dots += f'<text x="{cx2+12:.1f}" y="{cy2-8:.1f}" fill="#C74634" font-size="10" font-family="monospace">RECOMMENDED</text>'
            dots += f'<text x="{cx2+12:.1f}" y="{cy2+4:.1f}" fill="#94a3b8" font-size="9" font-family="monospace">{cfg["name"]}</text>'
            dots += f'<text x="{cx2+12:.1f}" y="{cy2+15:.1f}" fill="#94a3b8" font-size="9" font-family="monospace">${cfg["weekly_cost"]}/wk · {int(cfg["coverage"]*100)}% cov</text>'
        elif is_cur:
            dots += f'<text x="{cx2+12:.1f}" y="{cy2-6:.1f}" fill="#ef4444" font-size="10" font-family="monospace">CURRENT</text>'
            dots += f'<text x="{cx2+12:.1f}" y="{cy2+6:.1f}" fill="#94a3b8" font-size="9" font-family="monospace">${cfg["weekly_cost"]}/wk · {int(cfg["coverage"]*100)}% cov</text>'

    # Pareto label
    pareto_label = f'<text x="{sx(22):.1f}" y="{sy(0.60):.1f}" fill="#f59e0b" font-size="10" font-family="monospace" opacity="0.8">Pareto Frontier</text>'

    # axes labels
    axes = (
        f'<text x="{W//2}" y="{H-PB+38}" fill="#94a3b8" font-size="11" text-anchor="middle">Weekly Cost ($)</text>'
        f'<text x="14" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{H//2})">Detection Coverage</text>'
        f'<text x="{W//2}" y="22" fill="#f8fafc" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Eval Scope vs Cost (12 Configurations)</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{grid}{pareto_line}{dots}{pareto_label}{axes}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    freq_svg   = svg_freq_quality_curve()
    scatter_svg = svg_cost_coverage_scatter()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Eval Cost Optimizer — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#f8fafc;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .subtitle{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
    .kpi-row{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 24px;min-width:180px}}
    .kpi .val{{font-size:28px;font-weight:bold;color:#38bdf8}}
    .kpi .lbl{{font-size:11px;color:#94a3b8;margin-top:4px}}
    .section{{margin-bottom:32px}}
    .section h2{{color:#38bdf8;font-size:14px;margin-bottom:12px;text-transform:uppercase;letter-spacing:.08em}}
    .svg-wrap{{overflow-x:auto;background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px}}
    .charts-row{{display:flex;gap:24px;flex-wrap:wrap}}
    .rec-box{{background:#1a2e1a;border:1px solid #22c55e33;border-radius:8px;padding:16px 20px;margin-bottom:24px}}
    .rec-box h3{{color:#22c55e;font-size:13px;margin-bottom:8px}}
    .rec-box p{{color:#cbd5e1;font-size:12px;line-height:1.6}}
    footer{{color:#475569;font-size:11px;margin-top:32px;text-align:center}}
  </style>
</head>
<body>
  <h1>Eval Cost Optimizer</h1>
  <div class="subtitle">OCI Robot Cloud · Port 8301 · {ts}</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val">${current_cfg['weekly_cost']:.2f}</div><div class="lbl">Current Weekly Cost</div></div>
    <div class="kpi"><div class="val">{int(current_cfg['coverage']*100)}%</div><div class="lbl">Current Detection Coverage</div></div>
    <div class="kpi"><div class="val">${recommended_cfg['weekly_cost']:.2f}</div><div class="lbl">Recommended Weekly Cost</div></div>
    <div class="kpi"><div class="val">{int(recommended_cfg['coverage']*100)}%</div><div class="lbl">Recommended Coverage</div></div>
    <div class="kpi"><div class="val">{fn_rate_current:.0%}</div><div class="lbl">Current False Negative Rate</div></div>
    <div class="kpi"><div class="val">{fn_rate_rec:.0%}</div><div class="lbl">Recommended False Negative Rate</div></div>
  </div>

  <div class="rec-box">
    <h3>Recommended Weekly Schedule</h3>
    <p>
      Run <strong>LIBERO_quick + safety_smoke</strong> twice per week at <strong>$3.40/run ($6.80/week)</strong>.<br>
      Detection coverage: <strong>89%</strong> vs current 71% — saves <strong>$11.90/week</strong> (64% cost reduction) while improving regression catch rate by +18 pp.<br>
      Coverage-cost ratio: <strong>{coverage_cost_ratio:.4f} coverage/$</strong> · Cost per detected regression: <strong>${rec_cost_per_detected:.2f}</strong> vs current <strong>${cost_per_detected:.2f}</strong>.<br>
      Supplement with full_suite once per month ($18.70) for thoroughness.
    </p>
  </div>

  <div class="section">
    <h2>Eval Frequency vs Quality Gate Reliability</h2>
    <div class="svg-wrap">{freq_svg}</div>
  </div>

  <div class="section">
    <h2>Eval Scope vs Cost — 12 Configurations</h2>
    <div class="svg-wrap">{scatter_svg}</div>
  </div>

  <footer>OCI Robot Cloud · Eval Cost Optimizer · cycle-60A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(title="Eval Cost Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "eval_cost_optimizer", "port": 8301}

    @app.get("/api/configs")
    def api_configs():
        return {"configs": EVAL_CONFIGS, "recommended": recommended_cfg, "current": current_cfg}

    @app.get("/api/metrics")
    def api_metrics():
        return {
            "current_weekly_cost_usd": current_cfg["weekly_cost"],
            "current_coverage": current_cfg["coverage"],
            "recommended_weekly_cost_usd": recommended_cfg["weekly_cost"],
            "recommended_coverage": recommended_cfg["coverage"],
            "false_negative_rate_current": fn_rate_current,
            "false_negative_rate_recommended": fn_rate_rec,
            "coverage_cost_ratio": coverage_cost_ratio,
            "cost_per_detected_regression_current": cost_per_detected,
            "cost_per_detected_regression_recommended": rec_cost_per_detected,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8301}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8301)
    else:
        print("[eval_cost_optimizer] FastAPI not available — using stdlib http.server on port 8301")
        server = HTTPServer(("0.0.0.0", 8301), _Handler)
        server.serve_forever()
