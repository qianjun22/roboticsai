"""Eval variance analyzer — quantifies sources of evaluation variance (port 8339)."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
from datetime import datetime

# --- Mock Data ---
VARIANCE_SOURCES = [
    {"name": "episode_randomness",   "pct": 62, "color": "#C74634"},
    {"name": "environment_seed",     "pct": 21, "color": "#38bdf8"},
    {"name": "model_stochasticity",  "pct": 11, "color": "#a78bfa"},
    {"name": "hardware_timing",      "pct":  4, "color": "#fbbf24"},
    {"name": "operator_variability", "pct":  2, "color": "#34d399"},
]

# 95% CI width (±pp) vs episode count
EPISODE_COUNTS = [10, 20, 50, 100, 200, 500]
# CI = 1.96 * sqrt(p*(1-p)/n), p=0.5 worst case, scaled to percentage points
def _ci_width(n, p=0.5):
    return round(1.96 * math.sqrt(p * (1 - p) / n) * 100, 1)

CI_CURVE = [(n, _ci_width(n)) for n in EPISODE_COUNTS]
# Breakeven annotations
BREAKEVENS = [
    {"eps": 20,  "ci": _ci_width(20),  "label": "\u00b110% @ 20 eps"},
    {"eps": 100, "ci": _ci_width(100), "label": "\u00b15% @ 100 eps"},
]


def build_variance_bar_svg():
    """SVG 1: Horizontal bar chart — variance decomposition by source."""
    W, H = 580, 220
    BAR_H = 22
    LABEL_W = 160
    BAR_MAX_W = W - LABEL_W - 80
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:12px;">'
    ]
    # Title
    svg.append(
        f'<text x="{W//2}" y="22" text-anchor="middle" font-size="12" '
        f'fill="#38bdf8" font-family="monospace" font-weight="bold">'
        f'Variance Decomposition — 200-Episode Eval</text>'
    )
    # Axis label
    svg.append(
        f'<text x="{LABEL_W + BAR_MAX_W//2}" y="{H-8}" text-anchor="middle" '
        f'font-size="9" fill="#64748b" font-family="monospace">% contribution to total variance</text>'
    )
    for i, src in enumerate(VARIANCE_SOURCES):
        y = 38 + i * (BAR_H + 14)
        bar_w = int(BAR_MAX_W * src["pct"] / 100)
        # Label
        svg.append(
            f'<text x="{LABEL_W - 8}" y="{y + BAR_H//2 + 4}" text-anchor="end" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{src["name"].replace("_", " ")}</text>'
        )
        # Background bar
        svg.append(
            f'<rect x="{LABEL_W}" y="{y}" width="{BAR_MAX_W}" height="{BAR_H}" '
            f'rx="4" fill="#0f172a"/>'
        )
        # Value bar
        svg.append(
            f'<rect x="{LABEL_W}" y="{y}" width="{bar_w}" height="{BAR_H}" '
            f'rx="4" fill="{src[\"color\"]}" opacity="0.85"/>'
        )
        # Percentage label
        svg.append(
            f'<text x="{LABEL_W + bar_w + 6}" y="{y + BAR_H//2 + 4}" '
            f'font-size="10" fill="{src[\"color\"]}" font-family="monospace" font-weight="bold">{src["pct"]}%</text>'
        )
    svg.append('</svg>')
    return "".join(svg)


def build_ci_curve_svg():
    """SVG 2: Line chart — 95% CI width vs episode count."""
    W, H = 580, 240
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 30, 50
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    ci_values = [c for _, c in CI_CURVE]
    ci_min, ci_max = 0, max(ci_values) * 1.1

    def to_xy(n, ci):
        # x: log scale over episode range
        log_min = math.log10(EPISODE_COUNTS[0])
        log_max = math.log10(EPISODE_COUNTS[-1])
        xr = (math.log10(n) - log_min) / (log_max - log_min)
        yr = (ci - ci_min) / (ci_max - ci_min)
        px = PAD_L + xr * chart_w
        py = PAD_T + chart_h - yr * chart_h
        return px, py

    pts = [to_xy(n, ci) for n, ci in CI_CURVE]
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    # Area fill polygon
    area_pts = pts_str + f" {pts[-1][0]:.1f},{PAD_T+chart_h} {pts[0][0]:.1f},{PAD_T+chart_h}"

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:12px;">'
    ]
    # Title
    svg.append(
        f'<text x="{W//2}" y="20" text-anchor="middle" font-size="12" '
        f'fill="#38bdf8" font-family="monospace" font-weight="bold">'
        f'\u00b195% CI Width vs Episode Count (log scale)</text>'
    )
    # Axes
    svg.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )
    svg.append(
        f'<line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{PAD_L+chart_w}" y2="{PAD_T+chart_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )
    # Y gridlines + labels (CI widths: 0, 5, 10, 15)
    for ci_tick in [0, 5, 10, 15]:
        _, ty = to_xy(EPISODE_COUNTS[0], ci_tick)
        svg.append(
            f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{PAD_L+chart_w}" y2="{ty:.1f}" '
            f'stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4 3"/>'
        )
        svg.append(
            f'<text x="{PAD_L-6}" y="{ty+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#64748b" font-family="monospace">\u00b1{ci_tick}pp</text>'
        )
    # X axis labels
    for n, ci in CI_CURVE:
        px, py = to_xy(n, ci)
        svg.append(
            f'<text x="{px:.1f}" y="{PAD_T+chart_h+14}" text-anchor="middle" '
            f'font-size="9" fill="#64748b" font-family="monospace">{n}</text>'
        )
    svg.append(f'<text x="{PAD_L+chart_w//2}" y="{H-4}" text-anchor="middle" font-size="9" fill="#475569" font-family="monospace">episodes</text>')
    # Area
    svg.append(f'<polygon points="{area_pts}" fill="#38bdf8" opacity="0.07"/>')
    # Line
    svg.append(f'<polyline points="{pts_str}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')
    # Dots
    for (px, py), (n, ci) in zip(pts, CI_CURVE):
        svg.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>'
        )
        svg.append(
            f'<text x="{px:.1f}" y="{py-8:.1f}" text-anchor="middle" '
            f'font-size="8" fill="#38bdf8" font-family="monospace">{ci}</text>'
        )
    # Breakeven annotations
    be_colors = ["#C74634", "#a78bfa"]
    for be, bec in zip(BREAKEVENS, be_colors):
        bx, by = to_xy(be["eps"], be["ci"])
        svg.append(
            f'<line x1="{bx:.1f}" y1="{PAD_T}" x2="{bx:.1f}" y2="{PAD_T+chart_h}" '
            f'stroke="{bec}" stroke-width="1" stroke-dasharray="5 3" opacity="0.7"/>'
        )
        svg.append(
            f'<text x="{bx+4:.1f}" y="{PAD_T+14}" font-size="9" fill="{bec}" font-family="monospace">{be["label"]}</text>'
        )
    svg.append('</svg>')
    return "".join(svg)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>OCI Robot Cloud — Eval Variance Analyzer</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px;
            display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
  header span.badge {{ background: #38bdf8; color: #0f172a; padding: 2px 10px;
                       border-radius: 12px; font-size: 0.75rem; font-weight: bold; }}
  main {{ padding: 28px 32px; }}
  h2 {{ font-size: 1rem; color: #38bdf8; margin-bottom: 14px; letter-spacing: 0.05em; }}
  .section {{ margin-bottom: 36px; }}
  .svg-wrap {{ overflow-x: auto; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
           padding: 14px 16px; }}
  .kpi .label {{ font-size: 0.72rem; color: #64748b; margin-bottom: 4px; }}
  .kpi .val {{ font-size: 1.35rem; font-weight: bold; }}
  .kpi .desc {{ font-size: 0.68rem; color: #475569; margin-top: 3px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; color: #38bdf8; border-bottom: 1px solid #334155; padding: 8px 10px; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #1e293b; }}
  .rec {{ background: #0c1a2e; border-left: 3px solid #38bdf8; padding: 12px 16px;
           border-radius: 4px; font-size: 0.82rem; line-height: 1.6; color: #94a3b8; }}
  footer {{ text-align: center; padding: 20px; font-size: 0.7rem; color: #334155; }}
</style>
</head>
<body>
<header>
  <div style="width:32px;height:32px;background:#334155;border-radius:6px;
              display:flex;align-items:center;justify-content:center;font-size:1.1rem;">\u03c3</div>
  <h1>OCI Robot Cloud — Eval Variance Analyzer</h1>
  <span class="badge">PORT 8339</span>
  <span style="margin-left:auto;font-size:0.75rem;color:#64748b;">{timestamp}</span>
</header>
<main>
  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">CI @ 20 eps</div>
      <div class="val" style="color:#C74634;">&plusmn;8.9pp</div>
      <div class="desc">95% confidence interval</div>
    </div>
    <div class="kpi">
      <div class="label">CI @ 100 eps</div>
      <div class="val" style="color:#38bdf8;">&plusmn;4.1pp</div>
      <div class="desc">recommended eval size</div>
    </div>
    <div class="kpi">
      <div class="label">CI @ 200 eps</div>
      <div class="val" style="color:#34d399;">&plusmn;2.9pp</div>
      <div class="desc">high-confidence eval</div>
    </div>
    <div class="kpi">
      <div class="label">Top Variance Source</div>
      <div class="val" style="color:#a78bfa;">62%</div>
      <div class="desc">episode randomness</div>
    </div>
  </div>

  <div class="section">
    <h2>VARIANCE DECOMPOSITION</h2>
    <div class="svg-wrap">{variance_svg}</div>
  </div>

  <div class="section">
    <h2>CONFIDENCE INTERVAL vs EPISODE COUNT</h2>
    <div class="svg-wrap">{ci_svg}</div>
  </div>

  <div class="section">
    <h2>CI WIDTH TABLE</h2>
    <table>
      <thead><tr><th>Episode Count</th><th>&plusmn;95% CI (pp)</th><th>Reliable?</th><th>Notes</th></tr></thead>
      <tbody>
        {ci_rows}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>RECOMMENDATIONS</h2>
    <div class="rec">
      &bull; <strong>Minimum reliable eval:</strong> 50 episodes (&plusmn;6.9pp CI) &mdash; below this, results are noise-dominated.<br/>
      &bull; <strong>Standard eval:</strong> 100 episodes (&plusmn;4.1pp CI) &mdash; balances cost and statistical power.<br/>
      &bull; <strong>High-confidence eval:</strong> 200+ episodes for &lt;&plusmn;3pp CI.<br/>
      &bull; <strong>Top reduction opportunity:</strong> Seed diversity (fix 21% env_seed variance) via stratified episode sampling.<br/>
      &bull; <strong>Model stochasticity (11%):</strong> Use deterministic inference (temp=0) to eliminate this variance source.
    </div>
  </div>
</main>
<footer>OCI Robot Cloud Eval Variance Analyzer &mdash; port 8339 &mdash; Oracle Confidential</footer>
</body>
</html>
"""


def _ci_rows_html():
    thresholds = {10: "No", 20: "Marginal", 50: "Minimum", 100: "Yes", 200: "Yes", 500: "Yes"}
    notes = {
        10:  "too few — do not rely on result",
        20:  "acceptable only for fast iteration",
        50:  "minimum for publication",
        100: "recommended default",
        200: "high-confidence; use for final evals",
        500: "diminishing returns beyond 200",
    }
    colors = {"No": "#C74634", "Marginal": "#fbbf24", "Minimum": "#fb923c",
              "Yes": "#34d399"}
    rows = []
    for n, ci in CI_CURVE:
        rel = thresholds[n]
        c = colors[rel]
        rows.append(
            f'<tr><td>{n}</td><td>\u00b1{ci}pp</td>'
            f'<td style="color:{c};font-weight:bold;">{rel}</td>'
            f'<td style="color:#64748b;">{notes[n]}</td></tr>'
        )
    return "\n".join(rows)


def render_page():
    return HTML_TEMPLATE.format(
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        variance_svg=build_variance_bar_svg(),
        ci_svg=build_ci_curve_svg(),
        ci_rows=_ci_rows_html(),
    )


if HAS_FASTAPI:
    app = FastAPI(title="Eval Variance Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return render_page()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_variance_analyzer", "port": 8339}

    @app.get("/api/variance")
    async def variance():
        return {
            "sources": VARIANCE_SOURCES,
            "ci_curve": [{"episodes": n, "ci_pp": ci} for n, ci in CI_CURVE],
            "breakevens": BREAKEVENS,
            "recommended_episodes": 100,
            "minimum_episodes": 50,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8339)
    else:
        print("FastAPI not found — starting stdlib server on port 8339")
        HTTPServer(("0.0.0.0", 8339), _Handler).serve_forever()
