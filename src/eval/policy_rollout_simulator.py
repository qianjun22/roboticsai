"""Policy Rollout Simulator — FastAPI service on port 8244.

Simulates policy rollouts under perturbed conditions to test robustness
pre-deployment. Compares dagger_run9 vs groot_v2 across 5 perturbation
conditions with CI bars and a hexagonal radar chart.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime

# ── Mock data ──────────────────────────────────────────────────────────────
random.seed(42)

PERTURBATIONS = [
    "nominal",
    "cube_displaced_5mm",
    "lighting_dim_50pct",
    "camera_jitter",
    "gripper_force_noise",
]

# Success rates per perturbation per model
DAGGER_SR = {
    "nominal":              0.78,
    "cube_displaced_5mm":   0.51,
    "lighting_dim_50pct":   0.62,
    "camera_jitter":        0.65,
    "gripper_force_noise":  0.70,
}
GROOT_SR = {
    "nominal":              0.81,
    "cube_displaced_5mm":   0.56,
    "lighting_dim_50pct":   0.74,
    "camera_jitter":        0.69,
    "gripper_force_noise":  0.72,
}

RADAR_AXES = [
    "force_perturbation",
    "visual_perturbation",
    "kinematic_noise",
    "timing_jitter",
    "sensor_fault",
]
DAGGER_RADAR = [0.70, 0.62, 0.68, 0.73, 0.65]
GROOT_RADAR  = [0.74, 0.74, 0.71, 0.76, 0.68]

N_ROLLOUTS = 20


def _ci95(p: float, n: int) -> float:
    """Wilson confidence interval half-width approximation."""
    if n == 0:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def _rollout_counts(sr_map):
    counts = {}
    for cond, sr in sr_map.items():
        successes = int(round(sr * N_ROLLOUTS))
        counts[cond] = {"successes": successes, "total": N_ROLLOUTS, "sr": sr}
    return counts


def _robustness_index(sr_map):
    vals = list(sr_map.values())
    return round(sum(vals) / len(vals), 4)


def _worst_perturbation(sr_map):
    return min(sr_map, key=lambda k: sr_map[k])


def _deployment_gate(ri: float) -> str:
    if ri >= 0.75:
        return "PASS"
    if ri >= 0.65:
        return "CONDITIONAL"
    return "FAIL"


# ── SVG helpers ────────────────────────────────────────────────────────────

def _bar_chart_svg(dagger_counts, groot_counts) -> str:
    W, H = 700, 340
    margin_l, margin_r, margin_t, margin_b = 60, 20, 30, 80
    chart_w = W - margin_l - margin_r
    chart_h = H - margin_t - margin_b

    n = len(PERTURBATIONS)
    group_w = chart_w / n
    bar_w = group_w * 0.32
    gap = group_w * 0.08

    max_val = N_ROLLOUTS
    y_scale = chart_h / max_val

    labels = [p.replace("_", " ") for p in PERTURBATIONS]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace">Rollout Success Counts — 20 trials per condition</text>')

    # Y grid
    for tick in range(0, N_ROLLOUTS + 1, 5):
        y = margin_t + chart_h - tick * y_scale
        lines.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{W - margin_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{margin_l - 4}" y="{y + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">{tick}</text>')

    for i, cond in enumerate(PERTURBATIONS):
        x0 = margin_l + i * group_w + gap

        # dagger bar
        d = dagger_counts[cond]
        bh = d["successes"] * y_scale
        by = margin_t + chart_h - bh
        ci = _ci95(d["sr"], N_ROLLOUTS) * N_ROLLOUTS
        lines.append(f'<rect x="{x0:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="#38bdf8" opacity="0.85"/>')
        # CI bar
        cx = x0 + bar_w / 2
        lines.append(f'<line x1="{cx:.1f}" y1="{by - ci:.1f}" x2="{cx:.1f}" y2="{by + ci:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<line x1="{cx - 3:.1f}" y1="{by - ci:.1f}" x2="{cx + 3:.1f}" y2="{by - ci:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<line x1="{cx - 3:.1f}" y1="{by + ci:.1f}" x2="{cx + 3:.1f}" y2="{by + ci:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<text x="{cx:.1f}" y="{by - ci - 3:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle" font-family="monospace">{d["successes"]}</text>')

        # groot bar
        g = groot_counts[cond]
        x1 = x0 + bar_w + gap * 0.5
        bh2 = g["successes"] * y_scale
        by2 = margin_t + chart_h - bh2
        ci2 = _ci95(g["sr"], N_ROLLOUTS) * N_ROLLOUTS
        lines.append(f'<rect x="{x1:.1f}" y="{by2:.1f}" width="{bar_w:.1f}" height="{bh2:.1f}" fill="#C74634" opacity="0.85"/>')
        cx2 = x1 + bar_w / 2
        lines.append(f'<line x1="{cx2:.1f}" y1="{by2 - ci2:.1f}" x2="{cx2:.1f}" y2="{by2 + ci2:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<line x1="{cx2 - 3:.1f}" y1="{by2 - ci2:.1f}" x2="{cx2 + 3:.1f}" y2="{by2 - ci2:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<line x1="{cx2 - 3:.1f}" y1="{by2 + ci2:.1f}" x2="{cx2 + 3:.1f}" y2="{by2 + ci2:.1f}" stroke="#e2e8f0" stroke-width="1.5"/>')
        lines.append(f'<text x="{cx2:.1f}" y="{by2 - ci2 - 3:.1f}" fill="#C74634" font-size="9" text-anchor="middle" font-family="monospace">{g["successes"]}</text>')

        # X label
        lx = margin_l + (i + 0.5) * group_w
        for j, word in enumerate(labels[i].split()):
            lines.append(f'<text x="{lx:.1f}" y="{margin_t + chart_h + 14 + j * 12}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{word}</text>')

    # Legend
    lines.append(f'<rect x="{margin_l}" y="{H - 14}" width="10" height="10" fill="#38bdf8"/>')
    lines.append(f'<text x="{margin_l + 13}" y="{H - 5}" fill="#e2e8f0" font-size="10" font-family="monospace">dagger_run9</text>')
    lines.append(f'<rect x="{margin_l + 90}" y="{H - 14}" width="10" height="10" fill="#C74634"/>')
    lines.append(f'<text x="{margin_l + 103}" y="{H - 5}" fill="#e2e8f0" font-size="10" font-family="monospace">groot_v2</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _radar_svg(dagger_vals, groot_vals, axes) -> str:
    W, H = 480, 420
    cx, cy, r = W // 2, H // 2 - 10, 140
    n = len(axes)
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace">Robustness Radar — dagger_run9 vs groot_v2</text>')

    def _pt(val, i):
        angle = math.pi / 2 - (2 * math.pi * i / n)
        return cx + val * r * math.cos(angle), cy - val * r * math.sin(angle)

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = [_pt(ring, i) for i in range(n)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lines.append(f'<polygon points="{poly}" fill="none" stroke="#334155" stroke-width="1"/>')
        # ring label
        rx, ry = _pt(ring, 0)
        lines.append(f'<text x="{rx + 3:.1f}" y="{ry:.1f}" fill="#475569" font-size="9" font-family="monospace">{ring:.2f}</text>')

    # Spokes
    for i in range(n):
        ex, ey = _pt(1.0, i)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>')
        lx, ly = _pt(1.18, i)
        label = axes[i].replace("_", " ")
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">{label}</text>')

    # dagger polygon
    d_pts = [_pt(v, i) for i, v in enumerate(dagger_vals)]
    d_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in d_pts)
    lines.append(f'<polygon points="{d_poly}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="2"/>')
    for x, y in d_pts:
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>')

    # groot polygon
    g_pts = [_pt(v, i) for i, v in enumerate(groot_vals)]
    g_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in g_pts)
    lines.append(f'<polygon points="{g_poly}" fill="#C74634" fill-opacity="0.15" stroke="#C74634" stroke-width="2"/>')
    for x, y in g_pts:
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#C74634"/>')

    # Legend
    lines.append(f'<rect x="30" y="{H - 24}" width="12" height="12" fill="#38bdf8" fill-opacity="0.5" stroke="#38bdf8" stroke-width="1.5"/>')
    lines.append(f'<text x="46" y="{H - 13}" fill="#e2e8f0" font-size="10" font-family="monospace">dagger_run9</text>')
    lines.append(f'<rect x="140" y="{H - 24}" width="12" height="12" fill="#C74634" fill-opacity="0.5" stroke="#C74634" stroke-width="1.5"/>')
    lines.append(f'<text x="156" y="{H - 13}" fill="#e2e8f0" font-size="10" font-family="monospace">groot_v2</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_html() -> str:
    dagger_counts = _rollout_counts(DAGGER_SR)
    groot_counts  = _rollout_counts(GROOT_SR)
    ri_dagger = _robustness_index(DAGGER_SR)
    ri_groot  = _robustness_index(GROOT_SR)
    worst_d = _worst_perturbation(DAGGER_SR)
    worst_g = _worst_perturbation(GROOT_SR)
    gate_d = _deployment_gate(ri_dagger)
    gate_g = _deployment_gate(ri_groot)
    bar_svg   = _bar_chart_svg(dagger_counts, groot_counts)
    radar_svg = _radar_svg(DAGGER_RADAR, GROOT_RADAR, RADAR_AXES)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    gate_color = {"PASS": "#22c55e", "CONDITIONAL": "#f59e0b", "FAIL": "#ef4444"}

    rows = ""
    for cond in PERTURBATIONS:
        d = dagger_counts[cond]
        g = groot_counts[cond]
        rows += f"""
        <tr>
          <td>{cond}</td>
          <td style="color:#38bdf8">{d['successes']}/{N_ROLLOUTS} ({d['sr']:.0%})</td>
          <td style="color:#C74634">{g['successes']}/{N_ROLLOUTS} ({g['sr']:.0%})</td>
          <td style="color:{'#22c55e' if g['sr'] >= d['sr'] else '#f59e0b'}">
            {'+' if g['sr'] >= d['sr'] else ''}{(g['sr']-d['sr']):.0%}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Policy Rollout Simulator — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:12px;margin-bottom:20px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px}}
    .card .label{{color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px}}
    .card .value{{font-size:26px;font-weight:bold;margin-top:4px}}
    .card .sub2{{font-size:11px;color:#475569;margin-top:2px}}
    .charts{{display:flex;flex-wrap:wrap;gap:20px;margin-bottom:24px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;padding:10px 14px;text-align:left}}
    td{{padding:9px 14px;border-bottom:1px solid #1e293b;font-size:13px}}
    tr:hover td{{background:#263348}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}}
  </style>
</head>
<body>
  <h1>Policy Rollout Simulator</h1>
  <div class="sub">Port 8244 &bull; OCI Robot Cloud &bull; {ts}</div>

  <div class="grid">
    <div class="card">
      <div class="label">Robustness Index — dagger_run9</div>
      <div class="value" style="color:#38bdf8">{ri_dagger:.3f}</div>
      <div class="sub2">avg SR across all perturbations</div>
    </div>
    <div class="card">
      <div class="label">Robustness Index — groot_v2</div>
      <div class="value" style="color:#C74634">{ri_groot:.3f}</div>
      <div class="sub2">avg SR across all perturbations</div>
    </div>
    <div class="card">
      <div class="label">Worst Perturbation</div>
      <div class="value" style="color:#f59e0b;font-size:14px">{worst_d}</div>
      <div class="sub2">dagger_run9 weakest condition</div>
    </div>
    <div class="card">
      <div class="label">Deployment Gate</div>
      <div class="value">
        <span class="badge" style="background:{gate_color[gate_d]};color:#0f172a">D: {gate_d}</span>
        <span class="badge" style="background:{gate_color[gate_g]};color:#0f172a;margin-left:6px">G: {gate_g}</span>
      </div>
      <div class="sub2">threshold: RI &ge; 0.75 = PASS</div>
    </div>
  </div>

  <div class="charts">
    {bar_svg}
    {radar_svg}
  </div>

  <table>
    <thead>
      <tr>
        <th>Perturbation Condition</th>
        <th>dagger_run9</th>
        <th>groot_v2</th>
        <th>Delta</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <div style="margin-top:16px;color:#475569;font-size:11px">
    Simulation: {N_ROLLOUTS} rollouts &times; {len(PERTURBATIONS)} conditions &times; 2 models = {N_ROLLOUTS * len(PERTURBATIONS) * 2} total rollouts
  </div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(
        title="Policy Rollout Simulator",
        description="Simulates policy rollouts under perturbed conditions to test robustness pre-deployment.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/api/summary")
    def summary():
        dagger_counts = _rollout_counts(DAGGER_SR)
        groot_counts  = _rollout_counts(GROOT_SR)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "n_rollouts_per_condition": N_ROLLOUTS,
            "perturbations": PERTURBATIONS,
            "dagger_run9": {
                "success_rates": DAGGER_SR,
                "robustness_index": _robustness_index(DAGGER_SR),
                "worst_perturbation": _worst_perturbation(DAGGER_SR),
                "deployment_gate": _deployment_gate(_robustness_index(DAGGER_SR)),
            },
            "groot_v2": {
                "success_rates": GROOT_SR,
                "robustness_index": _robustness_index(GROOT_SR),
                "worst_perturbation": _worst_perturbation(GROOT_SR),
                "deployment_gate": _deployment_gate(_robustness_index(GROOT_SR)),
            },
        }

    @app.get("/api/radar")
    def radar_data():
        return {
            "axes": RADAR_AXES,
            "dagger_run9": DAGGER_RADAR,
            "groot_v2": GROOT_RADAR,
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "port": 8244, "service": "policy_rollout_simulator"}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","port":8244}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress default logging


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8244)
    else:
        print("FastAPI not available — starting stdlib fallback on port 8244")
        HTTPServer(("0.0.0.0", 8244), Handler).serve_forever()
