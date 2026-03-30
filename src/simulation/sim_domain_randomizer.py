"""sim_domain_randomizer.py — Isaac Sim domain randomization parameter manager.
FastAPI service on port 8270.
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

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

PARAMETERS = [
    {
        "name": "friction_coeff",
        "label": "Friction Coeff",
        "min": 0.20,
        "max": 0.90,
        "current": 0.55,
        "optimal_low": 0.30,
        "optimal_high": 0.70,
        "sr_impact": 0.09,
        "compute_overhead_pct": 1.2,
        "enabled": True,
    },
    {
        "name": "texture_id",
        "label": "Texture ID",
        "min": 0,
        "max": 127,
        "current": 64,
        "optimal_low": 10,
        "optimal_high": 110,
        "sr_impact": 0.07,
        "compute_overhead_pct": 3.8,
        "enabled": True,
    },
    {
        "name": "lighting_intensity",
        "label": "Lighting Intensity",
        "min": 200,
        "max": 1800,
        "current": 900,
        "optimal_low": 400,
        "optimal_high": 1400,
        "sr_impact": 0.05,
        "compute_overhead_pct": 0.8,
        "enabled": True,
    },
    {
        "name": "mass_scale",
        "label": "Mass Scale",
        "min": 0.50,
        "max": 2.00,
        "current": 1.10,
        "optimal_low": 0.70,
        "optimal_high": 1.50,
        "sr_impact": 0.05,
        "compute_overhead_pct": 0.4,
        "enabled": True,
    },
    {
        "name": "table_height",
        "label": "Table Height",
        "min": 0.70,
        "max": 0.90,
        "current": 0.80,
        "optimal_low": 0.74,
        "optimal_high": 0.86,
        "sr_impact": 0.04,
        "compute_overhead_pct": 0.2,
        "enabled": True,
    },
    {
        "name": "camera_pose_jitter",
        "label": "Camera Pose Jitter",
        "min": 0.00,
        "max": 0.05,
        "current": 0.02,
        "optimal_low": 0.005,
        "optimal_high": 0.035,
        "sr_impact": 0.03,
        "compute_overhead_pct": 0.1,
        "enabled": True,
    },
    {
        "name": "object_scale",
        "label": "Object Scale",
        "min": 0.80,
        "max": 1.20,
        "current": 1.00,
        "optimal_low": 0.88,
        "optimal_high": 1.12,
        "sr_impact": 0.02,
        "compute_overhead_pct": 0.3,
        "enabled": True,
    },
    {
        "name": "contact_stiffness",
        "label": "Contact Stiffness",
        "min": 1e4,
        "max": 1e6,
        "current": 2e5,
        "optimal_low": 5e4,
        "optimal_high": 6e5,
        "sr_impact": 0.02,
        "compute_overhead_pct": 1.6,
        "enabled": True,
    },
]

BASELINE_SR = 0.51   # DR fully off
FULL_DR_SR  = 0.78   # DR fully on


def _build_html() -> str:
    params_sorted = sorted(PARAMETERS, key=lambda p: p["sr_impact"], reverse=True)

    # -----------------------------------------------------------------------
    # SVG 1 — Parameter distribution ranges (horizontal bar chart)
    # -----------------------------------------------------------------------
    svg1_rows = []
    row_h = 40
    svg1_h = len(PARAMETERS) * row_h + 60
    svg1_w = 640
    chart_x0 = 170
    chart_w = 400

    for i, p in enumerate(PARAMETERS):
        y = i * row_h + 40
        vmin, vmax = p["min"], p["max"]
        span = vmax - vmin if vmax != vmin else 1

        def px(v):
            return chart_x0 + int((v - vmin) / span * chart_w)

        opt_x1 = px(p["optimal_low"])
        opt_x2 = px(p["optimal_high"])
        cur_x  = px(p["current"])

        # full range bar
        svg1_rows.append(f'<rect x="{chart_x0}" y="{y+10}" width="{chart_w}" height="12" rx="3" fill="#1e293b"/>')
        # optimal range
        svg1_rows.append(f'<rect x="{opt_x1}" y="{y+8}" width="{opt_x2-opt_x1}" height="16" rx="3" fill="#38bdf8" opacity="0.7"/>')
        # current value marker
        svg1_rows.append(f'<line x1="{cur_x}" y1="{y+4}" x2="{cur_x}" y2="{y+28}" stroke="#C74634" stroke-width="3"/>')
        # label
        svg1_rows.append(f'<text x="{chart_x0-8}" y="{y+20}" fill="#94a3b8" font-size="11" text-anchor="end">{p["label"]}</text>')

    svg1_rows.append(f'<text x="{chart_x0+chart_w//2}" y="20" fill="#f1f5f9" font-size="13" text-anchor="middle" font-weight="bold">Randomization Parameter Ranges (blue=optimal, red=current)</text>')

    svg1 = f'<svg width="{svg1_w}" height="{svg1_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">{"".join(svg1_rows)}</svg>'

    # -----------------------------------------------------------------------
    # SVG 2 — Sensitivity analysis: SR impact bars + cumulative gain
    # -----------------------------------------------------------------------
    svg2_rows = []
    bar_w = 42
    gap   = 12
    svg2_h = 280
    svg2_w = len(params_sorted) * (bar_w + gap) + 120
    chart_y0 = 220
    max_impact = 0.12

    cumulative = 0.0
    cum_pts = []

    for i, p in enumerate(params_sorted):
        x = 60 + i * (bar_w + gap)
        bar_h_px = int(p["sr_impact"] / max_impact * 160)
        bar_y = chart_y0 - bar_h_px
        cumulative += p["sr_impact"]
        cum_pts.append((x + bar_w // 2, chart_y0 - int(cumulative / 0.27 * 160)))

        color = "#C74634" if i == 0 else ("#38bdf8" if i == 1 else "#64748b")
        svg2_rows.append(f'<rect x="{x}" y="{bar_y}" width="{bar_w}" height="{bar_h_px}" rx="3" fill="{color}"/>')
        svg2_rows.append(f'<text x="{x+bar_w//2}" y="{chart_y0+14}" fill="#94a3b8" font-size="9" text-anchor="middle">{p["label"][:8]}</text>')
        svg2_rows.append(f'<text x="{x+bar_w//2}" y="{bar_y-4}" fill="#f1f5f9" font-size="10" text-anchor="middle">+{p["sr_impact"]:.2f}</text>')

    # cumulative line
    if len(cum_pts) > 1:
        pts_str = " ".join(f"{cx},{cy}" for cx, cy in cum_pts)
        svg2_rows.append(f'<polyline points="{pts_str}" fill="none" stroke="#facc15" stroke-width="2" stroke-dasharray="4,3"/>')
        for cx, cy in cum_pts:
            svg2_rows.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#facc15"/>')

    svg2_rows.append(f'<line x1="50" y1="{chart_y0}" x2="{svg2_w-10}" y2="{chart_y0}" stroke="#475569" stroke-width="1"/>')
    svg2_rows.append(f'<text x="{svg2_w//2}" y="20" fill="#f1f5f9" font-size="13" text-anchor="middle" font-weight="bold">SR Impact per DR Parameter (yellow=cumulative gain)</text>')
    svg2_rows.append(f'<text x="10" y="{chart_y0-80}" fill="#94a3b8" font-size="10" transform="rotate(-90,10,{chart_y0-80})">SR Gain</text>')
    svg2_rows.append(f'<text x="{svg2_w//2}" y="{chart_y0+30}" fill="#94a3b8" font-size="10" text-anchor="middle">Parameter (sorted by impact)</text>')

    svg2 = f'<svg width="{svg2_w}" height="{svg2_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">{"".join(svg2_rows)}</svg>'

    # -----------------------------------------------------------------------
    # Metrics table
    # -----------------------------------------------------------------------
    rows_html = ""
    for rank, p in enumerate(params_sorted, 1):
        rows_html += f"""
        <tr>
          <td style="padding:6px 12px;color:#94a3b8;">{rank}</td>
          <td style="padding:6px 12px;color:#f1f5f9;">{p['label']}</td>
          <td style="padding:6px 12px;color:#38bdf8;">+{p['sr_impact']:.2f}</td>
          <td style="padding:6px 12px;color:#facc15;">{p['compute_overhead_pct']:.1f}%</td>
          <td style="padding:6px 12px;color:{'#4ade80' if p['enabled'] else '#f87171'};">{'ON' if p['enabled'] else 'OFF'}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim Domain Randomizer — Port 8270</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 18px; border: 1px solid #334155; }}
    .card h3 {{ color: #38bdf8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }}
    .val {{ font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }}
    .sub {{ color: #64748b; font-size: 0.8rem; margin-top: 2px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }}
    .section h2 {{ color: #f1f5f9; font-size: 1rem; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:nth-child(even) {{ background: #0f172a; }}
    th {{ padding: 8px 12px; color: #64748b; font-size: 0.8rem; text-align: left; border-bottom: 1px solid #334155; }}
    .tag {{ display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <h1>Sim Domain Randomizer</h1>
  <p class="subtitle">Isaac Sim DR parameter manager &mdash; Port 8270 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

  <div class="grid">
    <div class="card">
      <h3>Baseline SR (DR off)</h3>
      <div class="val">{BASELINE_SR:.0%}</div>
      <div class="sub">All randomization disabled</div>
    </div>
    <div class="card">
      <h3>Full DR SR</h3>
      <div class="val" style="color:#4ade80">{FULL_DR_SR:.0%}</div>
      <div class="sub">All 8 parameters active</div>
    </div>
    <div class="card">
      <h3>Total SR Gain</h3>
      <div class="val" style="color:#38bdf8">+{FULL_DR_SR-BASELINE_SR:.0%}</div>
      <div class="sub">Absolute improvement from DR</div>
    </div>
    <div class="card">
      <h3>Active Parameters</h3>
      <div class="val">{sum(1 for p in PARAMETERS if p['enabled'])} / {len(PARAMETERS)}</div>
      <div class="sub">Total compute overhead: {sum(p['compute_overhead_pct'] for p in PARAMETERS):.1f}%</div>
    </div>
  </div>

  <div class="section">
    <h2>Parameter Distribution Ranges</h2>
    {svg1}
  </div>

  <div class="section">
    <h2>Sensitivity Analysis — SR Contribution per Parameter</h2>
    {svg2}
  </div>

  <div class="section">
    <h2>Parameter Impact Ranking</h2>
    <table>
      <thead><tr><th>#</th><th>Parameter</th><th>SR Impact</th><th>Compute Overhead</th><th>Status</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _USE_FASTAPI:
    app = FastAPI(title="Sim Domain Randomizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_domain_randomizer", "port": 8270}

    @app.get("/params")
    async def list_params():
        return {"parameters": PARAMETERS, "baseline_sr": BASELINE_SR, "full_dr_sr": FULL_DR_SR}

    @app.get("/params/{name}")
    async def get_param(name: str):
        for p in PARAMETERS:
            if p["name"] == name:
                return p
        return {"error": "not found"}

    @app.post("/randomize")
    async def trigger_randomize():
        """Sample new random values within each parameter's range."""
        updates = {}
        for p in PARAMETERS:
            if p["enabled"]:
                new_val = p["min"] + random.random() * (p["max"] - p["min"])
                updates[p["name"]] = round(new_val, 4)
        return {"status": "randomized", "new_values": updates, "timestamp": datetime.utcnow().isoformat()}

else:
    # Fallback stdlib HTTP server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logs
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8270)
    else:
        print("[sim_domain_randomizer] fastapi not found — using stdlib http.server on port 8270")
        with socketserver.TCPServer(("", 8270), _Handler) as srv:
            srv.serve_forever()
