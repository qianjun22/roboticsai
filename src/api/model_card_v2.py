"""Model Card V2 — Enhanced model card generator with performance benchmarks,
fairness metrics, and data lineage. Port 8322."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAVE_FASTAPI = True
except ImportError:
    _HAVE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
MODEL_DATA = {
    "name": "GR00T_v2",
    "version": "2.1.4",
    "created": "2026-02-14",
    "framework": "PyTorch 2.3",
    "composite_score": 0.83,
    "baseline_score": 0.74,
    "mae": 0.013,
    "mae_baseline": 0.113,
    "mae_improvement": "8.7x",
    "calibration_ece": 0.041,
    "safety_score": 0.96,
    "total_samples": 2600,
    "diversity_index": 0.82,
    "lineage_completeness": 97.4,
    "radar_axes": [
        {"label": "SR",           "v2": 0.83, "base": 0.74},
        {"label": "MAE",          "v2": 0.91, "base": 0.62},
        {"label": "Latency",      "v2": 0.88, "base": 0.80},
        {"label": "Robustness",   "v2": 0.79, "base": 0.65},
        {"label": "Transfer",     "v2": 0.77, "base": 0.58},
        {"label": "Calibration",  "v2": 0.85, "base": 0.70},
        {"label": "Safety",       "v2": 0.96, "base": 0.88},
        {"label": "Efficiency",   "v2": 0.81, "base": 0.72},
    ],
    "data_sources": [
        {"name": "SDG_genesis",      "pct": 35, "tier": "A"},
        {"name": "human_demos_PI",   "pct": 22, "tier": "S"},
        {"name": "human_demos_Apt",  "pct": 18, "tier": "S"},
        {"name": "DAgger_r9",        "pct": 15, "tier": "B"},
        {"name": "real_robot_aug",   "pct": 10, "tier": "A"},
    ],
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _polar(cx, cy, r, angle_deg):
    """Return (x, y) for a polar coordinate."""
    a = math.radians(angle_deg - 90)  # start at top
    return cx + r * math.cos(a), cy + r * math.sin(a)


def build_radar_svg() -> str:
    """8-axis polygon radar for GR00T_v2 vs dagger_r9 baseline."""
    CX, CY, R = 260, 230, 160
    axes = MODEL_DATA["radar_axes"]
    N = len(axes)
    angle_step = 360 / N

    # grid rings
    rings = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{_polar(CX,CY,R*frac,i*angle_step)[0]:.1f},{_polar(CX,CY,R*frac,i*angle_step)[1]:.1f}" for i in range(N))
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'

    # spokes
    spokes = ""
    for i in range(N):
        x, y = _polar(CX, CY, R, i * angle_step)
        spokes += f'<line x1="{CX}" y1="{CY}" x2="{x:.1f}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>\n'

    # axis labels
    labels = ""
    for i, ax in enumerate(axes):
        lx, ly = _polar(CX, CY, R + 22, i * angle_step)
        labels += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="11" font-family="monospace">{ax["label"]}</text>\n'

    # baseline polygon
    base_pts = " ".join(f"{_polar(CX,CY,R*ax['base'],i*angle_step)[0]:.1f},{_polar(CX,CY,R*ax['base'],i*angle_step)[1]:.1f}" for i, ax in enumerate(axes))
    # v2 polygon
    v2_pts = " ".join(f"{_polar(CX,CY,R*ax['v2'],i*angle_step)[0]:.1f},{_polar(CX,CY,R*ax['v2'],i*angle_step)[1]:.1f}" for i, ax in enumerate(axes))

    # confidence interval band (±0.03 around v2)
    ci_outer = " ".join(f"{_polar(CX,CY,R*min(1.0,ax['v2']+0.03),i*angle_step)[0]:.1f},{_polar(CX,CY,R*min(1.0,ax['v2']+0.03),i*angle_step)[1]:.1f}" for i, ax in enumerate(axes))
    ci_inner = " ".join(f"{_polar(CX,CY,R*max(0.0,ax['v2']-0.03),i*angle_step)[0]:.1f},{_polar(CX,CY,R*max(0.0,ax['v2']-0.03),i*angle_step)[1]:.1f}" for i, ax in enumerate(axes))

    legend = '''
        <rect x="30" y="410" width="12" height="12" fill="#C74634" opacity="0.7"/>
        <text x="48" y="421" fill="#94a3b8" font-size="11" font-family="monospace">GR00T_v2 (0.83)</text>
        <rect x="180" y="410" width="12" height="12" fill="#38bdf8" opacity="0.5"/>
        <text x="198" y="421" fill="#94a3b8" font-size="11" font-family="monospace">dagger_r9 baseline (0.74)</text>
    '''

    return f'''<svg width="520" height="440" viewBox="0 0 520 440" xmlns="http://www.w3.org/2000/svg">
  <rect width="520" height="440" fill="#1e293b" rx="8"/>
  <text x="260" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold" font-family="monospace">Model Performance Radar — GR00T_v2 vs Baseline</text>
  {rings}{spokes}{labels}
  <polygon points="{ci_outer}" fill="#C74634" opacity="0.15" stroke="none"/>
  <polygon points="{ci_inner}" fill="#0f172a" opacity="0.3" stroke="none"/>
  <polygon points="{base_pts}" fill="#38bdf8" opacity="0.25" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4,3"/>
  <polygon points="{v2_pts}" fill="#C74634" opacity="0.35" stroke="#C74634" stroke-width="2"/>
  {legend}
</svg>'''


def build_sankey_svg() -> str:
    """Training data provenance sankey: sources → final model."""
    # Simple Sankey approximation using rects + bezier paths
    W, H = 560, 340
    sources = MODEL_DATA["data_sources"]
    tier_colors = {"S": "#C74634", "A": "#38bdf8", "B": "#fbbf24"}

    LEFT_X = 60
    RIGHT_X = 420
    MODEL_Y = H // 2
    MODEL_H = 200

    # total pct = 100
    total = sum(s["pct"] for s in sources)
    bar_h = MODEL_H  # full height for model bar

    paths = ""
    src_labels = ""
    y_cursor = (H - bar_h) // 2

    for src in sources:
        frac = src["pct"] / total
        src_h = int(bar_h * frac)
        src_y = y_cursor
        mid_y_src = src_y + src_h // 2
        mid_y_dst = MODEL_Y - bar_h // 2 + int(bar_h * (y_cursor - (H - bar_h) // 2) / bar_h) + src_h // 2
        color = tier_colors.get(src["tier"], "#94a3b8")

        # source rectangle
        src_labels += f'<rect x="{LEFT_X}" y="{src_y}" width="18" height="{src_h}" fill="{color}" opacity="0.8" rx="2"/>\n'
        src_labels += f'<text x="{LEFT_X+24}" y="{src_y + src_h//2 + 4}" fill="{color}" font-size="10" font-family="monospace">{src["name"]} ({src["pct"]}%)</text>\n'

        # bezier path
        ctrl1x = LEFT_X + 18 + (RIGHT_X - LEFT_X - 18) // 3
        ctrl2x = LEFT_X + 18 + 2 * (RIGHT_X - LEFT_X - 18) // 3
        paths += f'<path d="M {LEFT_X+18} {mid_y_src} C {ctrl1x} {mid_y_src}, {ctrl2x} {mid_y_dst}, {RIGHT_X} {mid_y_dst}" stroke="{color}" stroke-width="{max(2, src_h//3)}" fill="none" opacity="0.45"/>\n'

        y_cursor += src_h

    # model rectangle
    model_rect = f'<rect x="{RIGHT_X}" y="{(H-bar_h)//2}" width="22" height="{bar_h}" fill="#C74634" rx="3"/>\n'
    model_label = f'<text x="{RIGHT_X+28}" y="{H//2+4}" fill="#f1f5f9" font-size="12" font-weight="bold" font-family="monospace">GR00T_v2</text>\n'
    model_label += f'<text x="{RIGHT_X+28}" y="{H//2+18}" fill="#94a3b8" font-size="10" font-family="monospace">2600 samples</text>\n'

    legend = ""
    for tier, color in tier_colors.items():
        lx = 60 + list(tier_colors.keys()).index(tier) * 130
        legend += f'<rect x="{lx}" y="{H-20}" width="10" height="10" fill="{color}"/>'
        legend += f'<text x="{lx+14}" y="{H-11}" fill="#94a3b8" font-size="10" font-family="monospace">Tier {tier}</text>'

    return f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  <text x="{W//2}" y="18" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold" font-family="monospace">Training Data Provenance Sankey</text>
  {paths}{src_labels}{model_rect}{model_label}{legend}
</svg>'''


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    d = MODEL_DATA
    radar = build_radar_svg()
    sankey = build_sankey_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def metric_card(label, value, sub=""):
        return f'''
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;">
          <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">{label}</div>
          <div style="color:#f1f5f9;font-size:26px;font-weight:bold;margin:6px 0;">{value}</div>
          <div style="color:#64748b;font-size:11px;">{sub}</div>
        </div>'''

    mae_pct = f"baseline {d['mae_baseline']} → {d['mae']} ({d['mae_improvement']} improvement)"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Model Card V2 — {d["name"]}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin: 28px 0 12px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 16px; }}
    .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; overflow-x: auto; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
    .badge-green {{ background: #14532d; color: #86efac; }}
    .badge-red {{ background: #7f1d1d; color: #fca5a5; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ color: #38bdf8; text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 5px 8px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
    tr:hover td {{ background: #1e293b; }}
    .ts {{ color: #475569; font-size: 11px; margin-top: 32px; text-align: right; }}
  </style>
</head>
<body>
  <h1>Model Card V2 &mdash; {d["name"]} v{d["version"]}</h1>
  <p style="color:#64748b;font-size:12px;">Created {d["created"]} &bull; {d["framework"]} &bull; Service port 8322</p>

  <h2>Key Metrics</h2>
  <div class="grid">
    {metric_card("Composite Score", f"{d['composite_score']:.2f}", f"vs baseline {d['baseline_score']:.2f} (+{d['composite_score']-d['baseline_score']:.2f})")}
    {metric_card("MAE", f"{d['mae']:.3f}", mae_pct)}
    {metric_card("Calibration ECE", f"{d['calibration_ece']:.3f}", "lower is better")}
    {metric_card("Safety Score", f"{d['safety_score']:.2f}", "certified ✓")}
    {metric_card("Training Samples", f"{d['total_samples']:,}", "across 5 data sources")}
    {metric_card("Data Diversity", f"{d['diversity_index']:.2f}", "Shannon index")}
    {metric_card("Lineage Completeness", f"{d['lineage_completeness']}%", "all artifacts traced")}
  </div>

  <h2>Performance Radar &amp; Data Provenance</h2>
  <div class="charts">
    <div class="chart-box">{radar}</div>
    <div class="chart-box">{sankey}</div>
  </div>

  <h2>Data Sources</h2>
  <table>
    <thead><tr><th>Source</th><th>Samples (%)</th><th>Quality Tier</th><th>Count</th></tr></thead>
    <tbody>
      {''.join(f"<tr><td>{s['name']}</td><td>{s['pct']}%</td><td><span class='badge {'badge-green' if s['tier']=='S' else 'badge-red' if s['tier']=='B' else ''}'>Tier {s['tier']}</span></td><td>{int(d['total_samples']*s['pct']/100)}</td></tr>" for s in d['data_sources'])}
    </tbody>
  </table>

  <h2>Model Lineage</h2>
  <table>
    <thead><tr><th>Property</th><th>Value</th></tr></thead>
    <tbody>
      <tr><td>Base architecture</td><td>GR00T N1.6</td></tr>
      <tr><td>Fine-tune method</td><td>DAgger + BC hybrid</td></tr>
      <tr><td>Training steps</td><td>5,000 (DAgger r9)</td></tr>
      <tr><td>Optimizer</td><td>AdamW lr=1e-4</td></tr>
      <tr><td>Batch size</td><td>32</td></tr>
      <tr><td>Compute</td><td>4× A100 (OCI BM.GPU4.8)</td></tr>
      <tr><td>Reproducibility hash</td><td>sha256:a3f9c2e1b8d4</td></tr>
    </tbody>
  </table>

  <div class="ts">Generated {ts} &bull; model_card_v2.py port 8322</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAVE_FASTAPI:
    app = FastAPI(title="Model Card V2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "model_card_v2", "port": 8322}

    @app.get("/api/metrics")
    def metrics():
        return MODEL_DATA

    @app.get("/api/radar")
    def radar():
        return {"axes": MODEL_DATA["radar_axes"]}

    @app.get("/api/provenance")
    def provenance():
        return {"data_sources": MODEL_DATA["data_sources"], "total_samples": MODEL_DATA["total_samples"]}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, fmt, *args):
            pass

    def run_stdlib(port=8322):
        print(f"[model_card_v2] stdlib fallback on :{port}")
        HTTPServer(("", port), Handler).serve_forever()


if __name__ == "__main__":
    if _HAVE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8322)
    else:
        run_stdlib(8322)
