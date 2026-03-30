"""Hyperparameter Sensitivity Analysis — OCI Robot Cloud
Port 8196: Which hyperparameters matter most for success rate?
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import math

app = FastAPI(title="Hyperparam Sensitivity", version="1.0.0") if FastAPI else None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

PARAMS = [
    {
        "name": "learning_rate",
        "base": 1e-4,
        "range": [1e-5, 1e-3],
        "sensitivity": 0.89,
        "level": "HIGH",
        "optimal": 1e-4,
        "sr_at_base": 0.78,
        "sr_at_worst": 0.31,
    },
    {
        "name": "lora_rank",
        "base": 16,
        "range": [4, 64],
        "sensitivity": 0.51,
        "level": "MEDIUM",
        "optimal": 16,
        "sr_at_base": 0.78,
        "sr_at_worst": 0.54,
    },
    {
        "name": "batch_size",
        "base": 64,
        "range": [16, 256],
        "sensitivity": 0.42,
        "level": "MEDIUM",
        "optimal": 64,
        "sr_at_base": 0.78,
        "sr_at_worst": 0.61,
    },
    {
        "name": "chunk_size",
        "base": 16,
        "range": [4, 32],
        "sensitivity": 0.38,
        "level": "LOW",
        "optimal": 16,
        "sr_at_base": 0.78,
        "sr_at_worst": 0.61,
    },
    {
        "name": "warmup_steps",
        "base": 200,
        "range": [0, 1000],
        "sensitivity": 0.21,
        "level": "LOW",
        "optimal": 200,
        "sr_at_base": 0.78,
        "sr_at_worst": 0.71,
    },
]

INTERACTIONS = [
    {
        "pair": "learning_rate × lora_rank",
        "strength": 0.74,
        "note": "Strongest interaction — optimal at lr=1e-4 + rank=16 (current production config)",
    },
    {
        "pair": "batch_size × warmup_steps",
        "strength": 0.31,
        "note": "Moderate interaction — larger batch benefits from longer warmup",
    },
    {
        "pair": "chunk_size × lora_rank",
        "strength": 0.19,
        "note": "Weak interaction — mostly independent",
    },
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _sensitivity_curves_svg() -> str:
    """680×240 SVG — SR curves as each param varies (others fixed at base)."""
    W, H = 680, 240
    pad_l, pad_r, pad_t, pad_b = 52, 24, 20, 36
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    colors = ["#C74634", "#38bdf8", "#a78bfa", "#34d399", "#fbbf24"]

    # Build paths: each param has a parabola-like curve (worst at extremes, best at base)
    # x in [0,1] normalized; base is somewhere in [0,1] derived from param position
    def _curve_points(p, n=40):
        lo, hi = p["range"]
        base = p["base"]
        sr_base = p["sr_at_base"]
        sr_worst = p["sr_at_worst"]
        # normalized base position
        base_norm = (math.log10(base) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) \
            if p["name"] == "learning_rate" else (base - lo) / (hi - lo)
        points = []
        for i in range(n + 1):
            xn = i / n
            dist = abs(xn - base_norm)
            # SR drops quadratically from base toward worst at extremes
            sr = sr_base - (sr_base - sr_worst) * (dist / max(base_norm, 1 - base_norm)) ** 1.4
            sr = max(sr_worst - 0.02, min(sr_base, sr))
            px = pad_l + xn * plot_w
            py = pad_t + plot_h - (sr - 0.25) / 0.6 * plot_h
            points.append((px, py))
        return points

    lines = ""
    for idx, p in enumerate(PARAMS):
        pts = _curve_points(p)
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lines += f'<path d="{d}" fill="none" stroke="{colors[idx]}" stroke-width="2" opacity="0.9"/>\n'
        # Label at right end
        lx, ly = pts[-1]
        lines += f'<text x="{lx+3:.0f}" y="{ly+4:.0f}" fill="{colors[idx]}" font-size="9" font-family="monospace">{p["name"][:4]}</text>\n'

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    # Y-axis labels
    y_labels = ""
    for sr_val in [0.30, 0.50, 0.70, 0.78]:
        py = pad_t + plot_h - (sr_val - 0.25) / 0.6 * plot_h
        y_labels += f'<text x="{pad_l-4}" y="{py+4:.0f}" fill="#94a3b8" font-size="9" text-anchor="end" font-family="monospace">{sr_val:.0%}</text>'
        y_labels += f'<line x1="{pad_l}" y1="{py:.0f}" x2="{pad_l+plot_w}" y2="{py:.0f}" stroke="#1e293b" stroke-width="0.5"/>'
    # X labels
    x_labels = (
        f'<text x="{pad_l}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">0.0</text>'
        f'<text x="{pad_l+plot_w//2}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">0.5</text>'
        f'<text x="{pad_l+plot_w}" y="{pad_t+plot_h+14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">1.0</text>'
        f'<text x="{W//2}" y="{H-2}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">Normalized param value</text>'
    )
    title = f'<text x="{pad_l}" y="{pad_t-6}" fill="#e2e8f0" font-size="11" font-family="monospace">SR sensitivity curves (one-at-a-time, others @ base)</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + title + y_labels + axes + lines + x_labels +
        '</svg>'
    )


def _tornado_svg() -> str:
    """680×200 tornado chart — horizontal bars sorted by sensitivity."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 130, 100, 24, 28
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    sorted_params = sorted(PARAMS, key=lambda p: p["sensitivity"], reverse=True)
    n = len(sorted_params)
    bar_h = plot_h / n * 0.6
    gap = plot_h / n

    level_colors = {"HIGH": "#C74634", "MEDIUM": "#f59e0b", "LOW": "#38bdf8"}
    max_sens = 1.0

    bars = ""
    for i, p in enumerate(sorted_params):
        cy = pad_t + i * gap + gap / 2
        bw = p["sensitivity"] / max_sens * plot_w
        col = level_colors[p["level"]]
        bars += (
            f'<rect x="{pad_l}" y="{cy - bar_h/2:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{col}" rx="3"/>'
            f'<text x="{pad_l - 6}" y="{cy + 4:.0f}" fill="#cbd5e1" font-size="10" text-anchor="end" font-family="monospace">{p["name"]}</text>'
            f'<text x="{pad_l + bw + 6:.0f}" y="{cy + 4:.0f}" fill="{col}" font-size="10" font-family="monospace">{p["sensitivity"]:.2f} {p["level"]}</text>'
        )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    title = f'<text x="{pad_l}" y="{pad_t-8}" fill="#e2e8f0" font-size="11" font-family="monospace">Sensitivity tornado — sorted by impact on SR</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + title + axes + bars +
        '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    curves_svg = _sensitivity_curves_svg()
    tornado_svg = _tornado_svg()

    level_badge = {
        "HIGH": '<span style="background:#C74634;color:#fff;padding:1px 7px;border-radius:4px;font-size:11px">HIGH</span>',
        "MEDIUM": '<span style="background:#f59e0b;color:#0f172a;padding:1px 7px;border-radius:4px;font-size:11px">MEDIUM</span>',
        "LOW": '<span style="background:#38bdf8;color:#0f172a;padding:1px 7px;border-radius:4px;font-size:11px">LOW</span>',
    }

    param_rows = ""
    for p in PARAMS:
        param_rows += (
            f"<tr>"
            f"<td style='color:#38bdf8;font-family:monospace'>{p['name']}</td>"
            f"<td style='color:#e2e8f0'>{p['base']}</td>"
            f"<td style='color:#94a3b8'>{p['range'][0]} – {p['range'][1]}</td>"
            f"<td>{level_badge[p['level']]}</td>"
            f"<td style='color:#e2e8f0'>{p['sensitivity']:.2f}</td>"
            f"<td style='color:#34d399'>{p['sr_at_base']:.0%}</td>"
            f"<td style='color:#C74634'>{p['sr_at_worst']:.0%}</td>"
            f"</tr>\n"
        )

    interaction_rows = ""
    for ix in INTERACTIONS:
        interaction_rows += (
            f"<tr>"
            f"<td style='color:#a78bfa;font-family:monospace'>{ix['pair']}</td>"
            f"<td style='color:#e2e8f0'>{ix['strength']:.2f}</td>"
            f"<td style='color:#94a3b8'>{ix['note']}</td>"
            f"</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hyperparam Sensitivity — OCI Robot Cloud</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; }}
  .header {{ background:linear-gradient(135deg,#1e293b,#0f172a); border-bottom:2px solid #C74634; padding:20px 32px; }}
  .header h1 {{ margin:0; font-size:22px; color:#fff; }}
  .header p {{ margin:4px 0 0; color:#94a3b8; font-size:13px; }}
  .badge-port {{ background:#C74634; color:#fff; border-radius:4px; padding:2px 10px; font-size:12px; margin-left:12px; }}
  .content {{ padding:28px 32px; max-width:960px; }}
  h2 {{ color:#38bdf8; font-size:15px; margin:28px 0 10px; text-transform:uppercase; letter-spacing:.05em; }}
  table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; font-size:13px; }}
  th {{ background:#334155; color:#94a3b8; padding:8px 12px; text-align:left; font-weight:600; font-size:11px; text-transform:uppercase; }}
  td {{ padding:8px 12px; border-top:1px solid #334155; }}
  tr:hover td {{ background:#243044; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:24px; }}
  .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:16px 20px; }}
  .kpi .val {{ font-size:28px; font-weight:700; color:#38bdf8; }}
  .kpi .lbl {{ font-size:11px; color:#64748b; text-transform:uppercase; margin-top:4px; }}
  .svg-box {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:12px; margin-bottom:20px; overflow-x:auto; }}
  .insight {{ background:#1e293b; border-left:3px solid #C74634; border-radius:0 6px 6px 0; padding:10px 16px; margin:16px 0; font-size:13px; color:#cbd5e1; }}
</style>
</head>
<body>
<div class="header">
  <h1>Hyperparameter Sensitivity Analysis <span class="badge-port">:8196</span></h1>
  <p>OCI Robot Cloud · One-at-a-time sensitivity · Production config: lr=1e-4, batch=64, rank=16, chunk=16, warmup=200</p>
</div>
<div class="content">
  <div class="kpi-grid">
    <div class="kpi"><div class="val">78%</div><div class="lbl">SR @ base config</div></div>
    <div class="kpi"><div class="val" style="color:#C74634">0.89</div><div class="lbl">Max sensitivity (lr)</div></div>
    <div class="kpi"><div class="val" style="color:#34d399">0.21</div><div class="lbl">Min sensitivity (warmup)</div></div>
  </div>

  <h2>SR Sensitivity Curves</h2>
  <div class="svg-box">{curves_svg}</div>

  <h2>Tornado Chart</h2>
  <div class="svg-box">{tornado_svg}</div>

  <h2>Parameter Detail</h2>
  <table>
    <tr><th>Parameter</th><th>Base</th><th>Range</th><th>Level</th><th>Sensitivity</th><th>SR @ Base</th><th>SR @ Worst</th></tr>
    {param_rows}
  </table>

  <h2>Interaction Effects</h2>
  <div class="insight">Strongest interaction: <strong>learning_rate × lora_rank</strong> — optimal at lr=1e-4 + rank=16 (current production config validated).</div>
  <table>
    <tr><th>Parameter Pair</th><th>Interaction Strength</th><th>Notes</th></tr>
    {interaction_rows}
  </table>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if app:
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/params")
    def get_params():
        return JSONResponse(content=PARAMS)

    @app.get("/sensitivity")
    def get_sensitivity():
        return JSONResponse(content=[
            {"name": p["name"], "sensitivity": p["sensitivity"], "level": p["level"]}
            for p in PARAMS
        ])

    @app.get("/curves")
    def get_curves():
        return JSONResponse(content={
            "description": "SR at base vs worst for each parameter",
            "params": [
                {
                    "name": p["name"],
                    "base_value": p["base"],
                    "range": p["range"],
                    "sr_at_base": p["sr_at_base"],
                    "sr_at_worst": p["sr_at_worst"],
                    "sensitivity": p["sensitivity"],
                }
                for p in PARAMS
            ],
            "interactions": INTERACTIONS,
        })


if __name__ == "__main__":
    if uvicorn:
        uvicorn.run("hyperparam_sensitivity:app", host="0.0.0.0", port=8196, reload=False)
    else:
        print("uvicorn not installed — pip install fastapi uvicorn")
