#!/usr/bin/env python3
"""
Training Data Mixer — OCI Robot Cloud
FastAPI service on port 8299
Optimizes training data mixing ratios between real demos, synthetic, and augmented data.
"""

import random
import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data — mixing experiments
# ---------------------------------------------------------------------------

random.seed(42)

# 20 mixing configs: (real%, synthetic%, augmented%, SR)
MIX_EXPERIMENTS = [
    # Optimal region — real 40-50%, synthetic 35-45%, aug 10-20%
    {"id": "MX-01", "real": 45, "synthetic": 40, "aug": 15, "sr": 0.79, "label": "OPTIMAL"},
    {"id": "MX-02", "real": 42, "synthetic": 43, "aug": 15, "sr": 0.77, "label": "OPTIMAL"},
    {"id": "MX-03", "real": 48, "synthetic": 38, "aug": 14, "sr": 0.76, "label": "OPTIMAL"},
    {"id": "MX-04", "real": 44, "synthetic": 42, "aug": 14, "sr": 0.78, "label": "OPTIMAL"},
    {"id": "MX-05", "real": 50, "synthetic": 36, "aug": 14, "sr": 0.75, "label": "OPTIMAL"},
    # Real-heavy
    {"id": "MX-06", "real": 70, "synthetic": 20, "aug": 10, "sr": 0.71, "label": "REAL_HEAVY"},
    {"id": "MX-07", "real": 80, "synthetic": 12, "aug":  8, "sr": 0.68, "label": "REAL_HEAVY"},
    {"id": "MX-08", "real": 60, "synthetic": 28, "aug": 12, "sr": 0.72, "label": "REAL_HEAVY"},
    # Pure real
    {"id": "MX-09", "real": 100, "synthetic": 0, "aug":  0, "sr": 0.71, "label": "PURE_REAL"},
    # Synthetic-heavy
    {"id": "MX-10", "real": 20, "synthetic": 70, "aug": 10, "sr": 0.67, "label": "SYNTH_HEAVY"},
    {"id": "MX-11", "real": 10, "synthetic": 80, "aug": 10, "sr": 0.65, "label": "SYNTH_HEAVY"},
    # Pure synthetic
    {"id": "MX-12", "real":  0, "synthetic": 100, "aug":  0, "sr": 0.64, "label": "PURE_SYNTH"},
    # Aug-heavy
    {"id": "MX-13", "real": 30, "synthetic": 30, "aug": 40, "sr": 0.66, "label": "AUG_HEAVY"},
    {"id": "MX-14", "real": 20, "synthetic": 40, "aug": 40, "sr": 0.63, "label": "AUG_HEAVY"},
    # Near-optimal but off
    {"id": "MX-15", "real": 55, "synthetic": 30, "aug": 15, "sr": 0.73, "label": "OFF_OPTIMAL"},
    {"id": "MX-16", "real": 38, "synthetic": 48, "aug": 14, "sr": 0.74, "label": "OFF_OPTIMAL"},
    {"id": "MX-17", "real": 45, "synthetic": 35, "aug": 20, "sr": 0.74, "label": "OFF_OPTIMAL"},
    # Low quality mixes
    {"id": "MX-18", "real": 10, "synthetic": 10, "aug": 80, "sr": 0.49, "label": "LOW_QUALITY"},
    {"id": "MX-19", "real": 33, "synthetic": 33, "aug": 34, "sr": 0.61, "label": "MIXED"},
    {"id": "MX-20", "real": 25, "synthetic": 55, "aug": 20, "sr": 0.69, "label": "SYNTH_HEAVY"},
]

# SR contribution area chart — 5000 training steps
# steps: 0,500,1000,1500,2000,2500,3000,3500,4000,4500,5000
STEPS = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]

# Synthetic dominates early, real demos critical after step 2000, dagger corrections after ep 400
SR_CURVES = {
    "synthetic_sdg":    [0.20, 0.35, 0.42, 0.44, 0.40, 0.36, 0.33, 0.31, 0.29, 0.27, 0.25],
    "real_demos":       [0.10, 0.15, 0.20, 0.26, 0.34, 0.39, 0.42, 0.44, 0.45, 0.46, 0.47],
    "dagger_correct":   [0.00, 0.00, 0.02, 0.05, 0.07, 0.09, 0.12, 0.14, 0.15, 0.16, 0.17],
    "augmented":        [0.05, 0.07, 0.08, 0.08, 0.07, 0.07, 0.06, 0.06, 0.06, 0.06, 0.06],
}

# Total SR at each step (sum of contributions)
SR_TOTAL = [sum(SR_CURVES[k][i] for k in SR_CURVES) for i in range(len(STEPS))]

OPTIMAL_MIX = MIX_EXPERIMENTS[0]  # MX-01

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def label_color(label):
    return {
        "OPTIMAL":     "#22c55e",
        "REAL_HEAVY":  "#38bdf8",
        "SYNTH_HEAVY": "#a78bfa",
        "AUG_HEAVY":   "#f97316",
        "PURE_REAL":   "#60a5fa",
        "PURE_SYNTH":  "#c084fc",
        "OFF_OPTIMAL": "#facc15",
        "LOW_QUALITY": "#ef4444",
        "MIXED":       "#94a3b8",
    }.get(label, "#94a3b8")


def build_scatter_svg():
    """Scatter: real% (x) vs SR (y), colored by dominant source, sized by aug%."""
    W, H = 700, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 30, 60

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    def px(real_pct):  # x = real%: 0-100
        return PAD_L + (real_pct / 100) * plot_w

    def py(sr):  # y = SR: 0.4-0.85 inverted
        sr_min, sr_max = 0.40, 0.85
        return PAD_T + (1 - (sr - sr_min) / (sr_max - sr_min)) * plot_h

    lines = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')

    # Grid
    for sr_tick in [0.50, 0.60, 0.65, 0.70, 0.75, 0.80]:
        yg = py(sr_tick)
        lines.append(f'<line x1="{PAD_L}" y1="{yg:.1f}" x2="{W-PAD_R}" y2="{yg:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{yg+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{sr_tick:.2f}</text>')

    for r_tick in [0, 20, 40, 60, 80, 100]:
        xg = px(r_tick)
        lines.append(f'<line x1="{xg:.1f}" y1="{PAD_T}" x2="{xg:.1f}" y2="{H-PAD_B}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{xg:.1f}" y="{H-PAD_B+14}" fill="#64748b" font-size="10" text-anchor="middle">{r_tick}%</text>')

    # Optimal zone shading (real 40-50%)
    x_opt_lo = px(40); x_opt_hi = px(50)
    lines.append(f'<rect x="{x_opt_lo:.1f}" y="{PAD_T}" width="{x_opt_hi-x_opt_lo:.1f}" height="{plot_h}" fill="#22c55e" fill-opacity="0.07"/>')
    lines.append(f'<text x="{(x_opt_lo+x_opt_hi)/2:.1f}" y="{PAD_T+14}" fill="#22c55e" font-size="9" text-anchor="middle" opacity="0.7">OPTIMAL ZONE</text>')

    # Points
    for exp in MIX_EXPERIMENTS:
        cx = px(exp["real"])
        cy = py(exp["sr"])
        r  = 5 + exp["aug"] / 10  # size ~ aug%
        col = label_color(exp["label"])
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="0.85" stroke="#0f172a" stroke-width="1">'
            f'<title>{exp["id"]}: real {exp["real"]}% / synth {exp["synthetic"]}% / aug {exp["aug"]}% → SR={exp["sr"]}</title>'
            f'</circle>'
        )
        if exp["label"] == "OPTIMAL" and exp["id"] == "MX-01":
            lines.append(f'<text x="{cx+r+4:.1f}" y="{cy+4:.1f}" fill="#22c55e" font-size="10" font-weight="600">★ {exp["sr"]}</text>')

    # Axes labels
    lines.append(f'<text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Real Demo % in Mix</text>')
    lines.append(f'<text x="14" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{H//2})">Success Rate (SR)</text>')

    # Legend
    legend_items = [("OPTIMAL", "#22c55e"), ("REAL_HEAVY", "#38bdf8"), ("SYNTH_HEAVY", "#a78bfa"),
                    ("AUG_HEAVY", "#f97316"), ("OFF_OPTIMAL", "#facc15"), ("LOW_QUALITY", "#ef4444")]
    for k, (lbl, col) in enumerate(legend_items):
        lx = PAD_L + k * 105
        ly = H - 8
        lines.append(f'<circle cx="{lx}" cy="{ly}" r="4" fill="{col}"/>')
        lines.append(f'<text x="{lx+8}" y="{ly+4}" fill="#94a3b8" font-size="9">{lbl}</text>')

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(lines)}</svg>'


def build_area_chart_svg():
    """SR contribution area chart over 5000 training steps."""
    W, H = 700, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 30, 55
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    max_sr = max(SR_TOTAL)

    def px(i):  # step index → x
        return PAD_L + (STEPS[i] / 5000) * plot_w

    def py(val):  # contribution value → y (stacked, so we pass cumulative)
        return PAD_T + (1 - val / (max_sr * 1.05)) * plot_h

    lines = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')

    # Grid lines (y)
    for tick in [0.2, 0.4, 0.6, 0.8]:
        yg = py(tick)
        lines.append(f'<line x1="{PAD_L}" y1="{yg:.1f}" x2="{W-PAD_R}" y2="{yg:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{yg+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick:.1f}</text>')

    # Step markers (x)
    for step in [0, 1000, 2000, 3000, 4000, 5000]:
        xi = STEPS.index(step) if step in STEPS else None
        xg = PAD_L + (step / 5000) * plot_w
        lines.append(f'<line x1="{xg:.1f}" y1="{PAD_T}" x2="{xg:.1f}" y2="{H-PAD_B}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{xg:.1f}" y="{H-PAD_B+14}" fill="#64748b" font-size="10" text-anchor="middle">{step}</text>')

    # Handoff annotation at step 2000
    xh = PAD_L + (2000 / 5000) * plot_w
    lines.append(f'<line x1="{xh:.1f}" y1="{PAD_T}" x2="{xh:.1f}" y2="{H-PAD_B}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>')
    lines.append(f'<text x="{xh+4:.1f}" y="{PAD_T+12}" fill="#C74634" font-size="9">Real-demo handoff</text>')

    # DAgger annotation at ep 400 ≈ step 2400
    xd = PAD_L + (2400 / 5000) * plot_w
    lines.append(f'<line x1="{xd:.1f}" y1="{PAD_T}" x2="{xd:.1f}" y2="{H-PAD_B}" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{xd+4:.1f}" y="{PAD_T+24}" fill="#38bdf8" font-size="9">DAgger ep 400</text>')

    COLORS = {
        "synthetic_sdg":  "#a78bfa",
        "real_demos":     "#22c55e",
        "dagger_correct": "#38bdf8",
        "augmented":      "#f97316",
    }
    LABELS = {
        "synthetic_sdg":  "Synthetic SDG",
        "real_demos":     "Real Demos",
        "dagger_correct": "DAgger Corrections",
        "augmented":      "Augmented",
    }

    # Build stacked areas bottom-up
    layer_order = ["augmented", "dagger_correct", "real_demos", "synthetic_sdg"]
    N = len(STEPS)

    # Precompute cumulative at each step
    cumulative = [[0.0] * N]
    for layer in layer_order:
        prev = cumulative[-1]
        cur  = [prev[i] + SR_CURVES[layer][i] for i in range(N)]
        cumulative.append(cur)

    for li, layer in enumerate(layer_order):
        top  = cumulative[li + 1]
        bot  = cumulative[li]
        col  = COLORS[layer]

        top_pts = " ".join(f"{px(i):.1f},{py(top[i]):.1f}" for i in range(N))
        bot_pts = " ".join(f"{px(i):.1f},{py(bot[i]):.1f}" for i in range(N - 1, -1, -1))
        poly_pts = top_pts + " " + bot_pts
        lines.append(f'<polygon points="{poly_pts}" fill="{col}" fill-opacity="0.55" stroke="{col}" stroke-width="1"><title>{LABELS[layer]}</title></polygon>')

    # Total SR line
    total_pts = " ".join(f"{px(i):.1f},{py(SR_TOTAL[i]):.1f}" for i in range(N))
    lines.append(f'<polyline points="{total_pts}" fill="none" stroke="#f8fafc" stroke-width="2" stroke-dasharray="5,3"/>')

    # Axes labels
    lines.append(f'<text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Training Steps</text>')
    lines.append(f'<text x="14" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{H//2})">SR Contribution</text>')

    # Legend
    all_layers = list(layer_order) + ["total"]
    for k, layer in enumerate(layer_order):
        lx = PAD_L + k * 160
        ly = H - 8
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="12" height="8" fill="{COLORS[layer]}" fill-opacity="0.7"/>')
        lines.append(f'<text x="{lx+15}" y="{ly}" fill="#94a3b8" font-size="9">{LABELS[layer]}</text>')
    # Total
    lines.append(f'<line x1="{PAD_L + 4*160}" y1="{H-4}" x2="{PAD_L + 4*160 + 20}" y2="{H-4}" stroke="#f8fafc" stroke-width="2" stroke-dasharray="4,2"/>')
    lines.append(f'<text x="{PAD_L + 4*160 + 24}" y="{H}" fill="#f8fafc" font-size="9">Total SR</text>')

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(lines)}</svg>'


def build_dashboard_html():
    scatter_svg = build_scatter_svg()
    area_svg    = build_area_chart_svg()

    best = OPTIMAL_MIX
    pure_synth = next(e for e in MIX_EXPERIMENTS if e["label"] == "PURE_SYNTH")
    pure_real  = next(e for e in MIX_EXPERIMENTS if e["label"] == "PURE_REAL")
    synth_real_uplift = round((best["sr"] - pure_synth["sr"]) / pure_synth["sr"] * 100, 1)
    real_uplift = round((best["sr"] - pure_real["sr"]) / pure_real["sr"] * 100, 1)

    rows = ""
    for exp in sorted(MIX_EXPERIMENTS, key=lambda x: -x["sr"])[:10]:
        col = label_color(exp["label"])
        bar_w = int(exp["sr"] * 200)
        rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px;color:#94a3b8;font-size:12px">{exp['id']}</td>
          <td style="padding:8px;color:#e2e8f0;font-size:12px">{exp['real']}% / {exp['synthetic']}% / {exp['aug']}%</td>
          <td style="padding:8px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="background:{col};height:12px;width:{bar_w}px;border-radius:3px"></div>
              <span style="color:{col};font-weight:700;font-size:13px">{exp['sr']:.2f}</span>
            </div>
          </td>
          <td style="padding:8px"><span style="background:{col}22;color:{col};padding:2px 8px;border-radius:4px;font-size:11px">{exp['label']}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Training Data Mixer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1   {{ color: #f8fafc; font-size: 22px; font-weight: 700; }}
  h2   {{ color: #94a3b8; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px; }}
  .card {{ background:#1e293b; border-radius:12px; padding:20px; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th    {{ padding:8px; color:#64748b; font-size:11px; text-align:left; border-bottom:1px solid #334155; }}
  .metric-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; margin-bottom:24px; }}
  .metric {{ background:#1e293b; border-radius:10px; padding:16px; text-align:center; }}
  .metric .val {{ font-size:30px; font-weight:700; color:#38bdf8; }}
  .metric .lbl {{ font-size:11px; color:#64748b; margin-top:4px; text-transform:uppercase; }}
  .header-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }}
  .optimal-badge {{ background:#14532d; color:#22c55e; padding:4px 14px; border-radius:20px; font-size:13px; font-weight:600; }}
  .svg-scroll {{ overflow-x:auto; }}
  .mix-pill {{ display:inline-flex; gap:6px; padding:6px 14px; background:#0f172a; border-radius:20px; margin-top:8px; }}
  .mix-pill span {{ font-size:13px; font-weight:700; }}
</style>
</head>
<body>
<div class="header-row">
  <div>
    <h1>Training Data Mixer</h1>
    <p style="color:#64748b;font-size:13px;margin-top:4px">OCI Robot Cloud — Mixing Ratio Optimizer · 20 Experiments</p>
  </div>
  <span class="optimal-badge">Optimal Mix Found</span>
</div>

<div class="metric-grid">
  <div class="metric">
    <div class="val" style="color:#22c55e">{best['sr']:.2f}</div>
    <div class="lbl">Best SR (Optimal Mix)</div>
  </div>
  <div class="metric">
    <div class="val" style="color:#a78bfa">{pure_synth['sr']:.2f}</div>
    <div class="lbl">Pure Synthetic SR</div>
  </div>
  <div class="metric">
    <div class="val" style="color:#38bdf8">{pure_real['sr']:.2f}</div>
    <div class="lbl">Pure Real SR</div>
  </div>
  <div class="metric">
    <div class="val" style="color:#22c55e">+{synth_real_uplift}%</div>
    <div class="lbl">SR Uplift vs Pure Synth</div>
  </div>
  <div class="metric">
    <div class="val" style="color:#22c55e">+{real_uplift}%</div>
    <div class="lbl">SR Uplift vs Pure Real</div>
  </div>
  <div class="metric">
    <div class="val">2000</div>
    <div class="lbl">Synth→Real Handoff Step</div>
  </div>
  <div class="metric">
    <div class="val">400</div>
    <div class="lbl">DAgger Critical Episode</div>
  </div>
  <div class="metric">
    <div class="val" style="color:#f97316">2.3×</div>
    <div class="lbl">Cost Efficiency vs All-Real</div>
  </div>
</div>

<div class="card">
  <h2>Optimal Mix Configuration</h2>
  <div class="mix-pill">
    <span style="color:#22c55e">Real Demos {best['real']}%</span>
    <span style="color:#64748b">/</span>
    <span style="color:#a78bfa">Synthetic SDG {best['synthetic']}%</span>
    <span style="color:#64748b">/</span>
    <span style="color:#f97316">Augmented {best['aug']}%</span>
    <span style="color:#64748b">→</span>
    <span style="color:#38bdf8">SR = {best['sr']:.2f}</span>
  </div>
  <p style="color:#64748b;font-size:12px;margin-top:10px">DAgger corrections become critical after episode 400. Synthetic data dominates early training; real demos are the decisive factor after step 2000.</p>
</div>

<div class="card">
  <h2>Mixing Ratio Experiments — SR vs Real Demo %</h2>
  <p style="color:#64748b;font-size:12px;margin-bottom:12px">Circle size = augmented %; green shading = optimal zone (real 40-50%); hover for details</p>
  <div class="svg-scroll">{scatter_svg}</div>
</div>

<div class="card">
  <h2>SR Contribution by Data Source — Training Steps 0→5000</h2>
  <p style="color:#64748b;font-size:12px;margin-bottom:12px">Stacked area = per-source SR contribution; dashed white = total SR; red line = synthetic→real handoff; blue = DAgger onset</p>
  <div class="svg-scroll">{area_svg}</div>
</div>

<div class="card">
  <h2>Top 10 Experiments by Success Rate</h2>
  <table>
    <thead><tr>
      <th>Exp ID</th><th>Real / Synth / Aug</th><th>Success Rate</th><th>Category</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<p style="color:#334155;font-size:11px;text-align:center;margin-top:16px">OCI Robot Cloud · Training Data Mixer · Port 8299</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Training Data Mixer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_dashboard_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "training_data_mixer", "port": 8299}

    @app.get("/api/experiments")
    async def get_experiments():
        return {"experiments": MIX_EXPERIMENTS, "count": len(MIX_EXPERIMENTS)}

    @app.get("/api/optimal")
    async def get_optimal():
        return {
            "optimal_mix": OPTIMAL_MIX,
            "synth_real_handoff_step": 2000,
            "dagger_critical_episode": 400,
            "sr_curves": SR_CURVES,
            "steps": STEPS,
        }

    @app.get("/api/metrics")
    async def get_metrics():
        best = OPTIMAL_MIX
        pure_synth = next(e for e in MIX_EXPERIMENTS if e["label"] == "PURE_SYNTH")
        pure_real  = next(e for e in MIX_EXPERIMENTS if e["label"] == "PURE_REAL")
        return {
            "best_sr": best["sr"],
            "optimal_real_pct": best["real"],
            "optimal_synthetic_pct": best["synthetic"],
            "optimal_aug_pct": best["aug"],
            "pure_synthetic_sr": pure_synth["sr"],
            "pure_real_sr": pure_real["sr"],
            "uplift_vs_pure_synth_pct": round((best["sr"] - pure_synth["sr"]) / pure_synth["sr"] * 100, 1),
            "uplift_vs_pure_real_pct": round((best["sr"] - pure_real["sr"]) / pure_real["sr"] * 100, 1),
            "synth_real_handoff_step": 2000,
            "dagger_critical_episode": 400,
            "cost_efficiency_vs_all_real": 2.3,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8299)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8299")
        HTTPServer(("0.0.0.0", 8299), Handler).serve_forever()
