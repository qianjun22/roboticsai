#!/usr/bin/env python3
"""
Benchmark Suite v2 — OCI Robot Cloud
Port 8331 | cycle-67B

Comprehensive benchmark suite v2 with standardized protocols and
community leaderboard support.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

BENCHMARK_TIERS = [
    {
        "name": "QUICK",
        "duration": "15 min",
        "cost": 2.00,
        "episodes": 20,
        "coverage": 42,
        "use_case": "Dev iteration",
        "color": "#38bdf8",
        "tasks": ["LIBERO-Spatial subset", "LIBERO-Object subset"],
    },
    {
        "name": "STANDARD",
        "duration": "1 hr",
        "cost": 8.00,
        "episodes": 80,
        "coverage": 68,
        "use_case": "Weekly CI gate",
        "color": "#4ade80",
        "tasks": ["LIBERO-Spatial", "LIBERO-Object", "RoboMimic subset"],
    },
    {
        "name": "FULL",
        "duration": "4 hr",
        "cost": 19.00,
        "episodes": 300,
        "coverage": 89,
        "use_case": "Pre-release validation",
        "color": "#fbbf24",
        "tasks": ["LIBERO-Spatial", "LIBERO-Object", "BridgeV2", "RoboMimic"],
    },
    {
        "name": "EXTENDED",
        "duration": "8 hr",
        "cost": 34.00,
        "episodes": 600,
        "coverage": 97,
        "use_case": "Publication results",
        "color": "#C74634",
        "tasks": ["LIBERO-Spatial", "LIBERO-Object", "BridgeV2", "RoboMimic", "Extra domains"],
    },
]

BASELINES = [
    {
        "benchmark": "LIBERO-Spatial",
        "our_model": 0.847,
        "sota": 0.821,
        "rt2": 0.641,
        "octo": 0.573,
        "diffusion_policy": 0.702,
    },
    {
        "benchmark": "LIBERO-Object",
        "our_model": 0.792,
        "sota": 0.771,
        "rt2": 0.589,
        "octo": 0.512,
        "diffusion_policy": 0.651,
    },
    {
        "benchmark": "BridgeV2",
        "our_model": 0.610,
        "sota": 0.790,
        "rt2": 0.720,
        "octo": 0.650,
        "diffusion_policy": 0.580,
    },
    {
        "benchmark": "RoboMimic",
        "our_model": 0.740,
        "sota": 0.760,
        "rt2": 0.680,
        "octo": 0.590,
        "diffusion_policy": 0.710,
    },
]

MODEL_NAME = "GR00T_v2"
BENCHMARK_COVERAGE_PCT = 89
PUBLICATION_CHECKLIST = [
    (True,  "Min 300 episodes per task"),
    (True,  "3 random seeds averaged"),
    (True,  "95% confidence intervals reported"),
    (True,  "Held-out test split (no leakage)"),
    (True,  "Hardware spec documented (A100 80GB)"),
    (False, "External evaluator blind review"),
    (False, "Cross-lab replication attempt"),
]


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_tier_diagram_svg() -> str:
    """Benchmark protocol tier diagram."""
    W, H = 600, 340
    PAD = 24

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">Benchmark Protocol Tiers</text>')

    tier_h = 54
    tier_gap = 14
    start_y = 40
    bar_max_w = W - PAD * 2 - 180

    for i, tier in enumerate(BENCHMARK_TIERS):
        y = start_y + i * (tier_h + tier_gap)
        col = tier["color"]
        cov = tier["coverage"] / 100

        # Background panel
        lines.append(f'<rect x="{PAD}" y="{y}" width="{W-PAD*2}" height="{tier_h}" rx="6" fill="#0f172a" stroke="{col}" stroke-width="1.5" opacity="0.9"/>')

        # Tier name badge
        lines.append(f'<rect x="{PAD+6}" y="{y+8}" width="80" height="24" rx="4" fill="{col}" opacity="0.2"/>')
        lines.append(f'<text x="{PAD+46}" y="{y+24}" text-anchor="middle" fill="{col}" font-size="12" font-weight="700">{tier["name"]}</text>')

        # Duration and cost
        lines.append(f'<text x="{PAD+96}" y="{y+20}" fill="#f1f5f9" font-size="12" font-weight="600">{tier["duration"]} · ${tier["cost"]:.0f}</text>')
        lines.append(f'<text x="{PAD+96}" y="{y+36}" fill="#64748b" font-size="10">{tier["episodes"]} episodes · {tier["use_case"]}</text>')

        # Coverage bar
        bar_x = W - PAD - 170
        bar_y = y + 16
        bar_h = 10
        bar_w = 150
        filled_w = int(bar_w * cov)
        lines.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4" fill="#1e3a5f"/>')
        lines.append(f'<rect x="{bar_x}" y="{bar_y}" width="{filled_w}" height="{bar_h}" rx="4" fill="{col}"/>')
        lines.append(f'<text x="{bar_x+bar_w+6}" y="{bar_y+9}" fill="{col}" font-size="11" font-weight="700">{tier["coverage"]}%</text>')
        lines.append(f'<text x="{bar_x}" y="{bar_y+bar_h+12}" fill="#475569" font-size="9">Task Coverage</text>')

        # Recommended marker for FULL tier
        if tier["name"] == "FULL":
            lines.append(f'<text x="{W-PAD-2}" y="{y+8}" text-anchor="end" fill="#fbbf24" font-size="9" font-weight="700">★ RECOMMENDED</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def build_baseline_comparison_svg() -> str:
    """Grouped bar chart: our model vs community baselines on 4 benchmarks."""
    W, H = 600, 360
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 40, 70

    models = ["our_model", "sota", "rt2", "octo", "diffusion_policy"]
    model_labels = {"our_model": "GR00T_v2 (ours)", "sota": "Pub. SOTA", "rt2": "RT-2", "octo": "Octo", "diffusion_policy": "Diff. Policy"}
    model_colors = {
        "our_model": "#C74634",
        "sota": "#fbbf24",
        "rt2": "#38bdf8",
        "octo": "#a78bfa",
        "diffusion_policy": "#4ade80",
    }

    n_benchmarks = len(BASELINES)
    n_models = len(models)
    bar_group_w = (W - PAD_L - PAD_R) / n_benchmarks
    bar_w = (bar_group_w - 16) / n_models
    bar_gap = 2
    max_val = 1.0
    min_val = 0.4

    def bx(bi, mi):
        return PAD_L + bi * bar_group_w + 8 + mi * (bar_w + bar_gap)

    def by(val):
        return PAD_T + (1 - (val - min_val) / (max_val - min_val)) * (H - PAD_T - PAD_B)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">OCI Robot Cloud vs Community Baselines</text>')
    lines.append(f'<text x="{W//2}" y="36" text-anchor="middle" fill="#64748b" font-size="10">Model: {MODEL_NAME} | ★ = above SOTA</text>')

    # Grid
    for yv in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        y = by(yv)
        lines.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{yv:.0%}</text>')

    # Axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')

    # Bars
    for bi, bench in enumerate(BASELINES):
        # Benchmark label
        label_x = PAD_L + bi * bar_group_w + bar_group_w / 2
        lines.append(f'<text x="{label_x:.1f}" y="{H-PAD_B+14}" text-anchor="middle" fill="#94a3b8" font-size="10">{bench["benchmark"]}</text>')

        sota_val = bench["sota"]
        our_val = bench["our_model"]
        above_sota = our_val >= sota_val

        for mi, m in enumerate(models):
            val = bench[m]
            x = bx(bi, mi)
            y_top = by(val)
            bar_height = H - PAD_B - y_top
            col = model_colors[m]

            # Dim bars that are not ours or SOTA
            opacity = "1" if m in ("our_model", "sota") else "0.65"
            lines.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bar_height:.1f}" fill="{col}" opacity="{opacity}" rx="2"/>')

            # Value label on top for our_model and sota
            if m in ("our_model", "sota"):
                lines.append(f'<text x="{x+bar_w/2:.1f}" y="{y_top-4:.1f}" text-anchor="middle" fill="{col}" font-size="9" font-weight="600">{val:.2f}</text>')

        # SOTA marker line
        sota_y = by(sota_val)
        marker_x1 = bx(bi, 0)
        marker_x2 = bx(bi, n_models - 1) + bar_w
        lines.append(f'<line x1="{marker_x1:.1f}" y1="{sota_y:.1f}" x2="{marker_x2:.1f}" y2="{sota_y:.1f}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>')

        # Above SOTA star
        if above_sota:
            our_y = by(our_val)
            cx_star = bx(bi, 0) + bar_w / 2
            lines.append(f'<text x="{cx_star:.1f}" y="{our_y-14:.1f}" text-anchor="middle" fill="#fbbf24" font-size="13">★</text>')

        # Sim2real gap note for BridgeV2
        if bench["benchmark"] == "BridgeV2":
            cx_note = PAD_L + bi * bar_group_w + bar_group_w / 2
            lines.append(f'<text x="{cx_note:.1f}" y="{H-PAD_B+26}" text-anchor="middle" fill="#C74634" font-size="9">sim2real gap</text>')

    # Legend
    legend_y = H - 16
    lx = PAD_L
    for k in models:
        col = model_colors[k]
        lbl = model_labels[k]
        lines.append(f'<rect x="{lx}" y="{legend_y-9}" width="12" height="9" rx="2" fill="{col}"/>')
        lines.append(f'<text x="{lx+15}" y="{legend_y}" fill="#cbd5e1" font-size="9">{lbl}</text>')
        lx += len(lbl) * 6 + 24

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    tier_svg = build_tier_diagram_svg()
    baseline_svg = build_baseline_comparison_svg()

    # Summary stats
    above_sota = sum(1 for b in BASELINES if b["our_model"] >= b["sota"])
    total_benchmarks = len(BASELINES)

    # Checklist HTML
    checklist_html = ""
    done_count = sum(1 for done, _ in PUBLICATION_CHECKLIST if done)
    for done, item in PUBLICATION_CHECKLIST:
        icon = "&#10003;" if done else "&#9675;"
        color = "#4ade80" if done else "#475569"
        checklist_html += f'<div style="margin-bottom:6px;color:{color};font-size:12px"><span style="margin-right:8px">{icon}</span>{item}</div>'

    # Baseline table rows
    table_rows = ""
    for b in BASELINES:
        above = b["our_model"] >= b["sota"]
        diff = b["our_model"] - b["sota"]
        diff_col = "#4ade80" if diff >= 0 else "#C74634"
        diff_str = f"+{diff:.3f}" if diff >= 0 else f"{diff:.3f}"
        note = "" if above else '<span style="color:#C74634;font-size:10px"> sim2real gap</span>'
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e3a5f">
          <td style="padding:7px 10px;font-weight:600">{b['benchmark']}</td>
          <td style="padding:7px 10px;text-align:right;color:#C74634;font-weight:700">{b['our_model']:.3f}{note}</td>
          <td style="padding:7px 10px;text-align:right;color:#fbbf24">{b['sota']:.3f}</td>
          <td style="padding:7px 10px;text-align:right;color:#38bdf8">{b['rt2']:.3f}</td>
          <td style="padding:7px 10px;text-align:right;color:#a78bfa">{b['octo']:.3f}</td>
          <td style="padding:7px 10px;text-align:right;color:#4ade80">{b['diffusion_policy']:.3f}</td>
          <td style="padding:7px 10px;text-align:right;color:{diff_col};font-weight:700">{diff_str}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark Suite v2 — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{color:#f1f5f9;font-size:22px;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
  .kpi{{background:#1e293b;border-radius:10px;padding:18px 20px;border-left:3px solid #C74634}}
  .kpi .label{{color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .kpi .value{{color:#f1f5f9;font-size:26px;font-weight:700}}
  .kpi .sub{{color:#64748b;font-size:11px;margin-top:4px}}
  .kpi.blue{{border-left-color:#38bdf8}}
  .kpi.green{{border-left-color:#4ade80}}
  .kpi.yellow{{border-left-color:#fbbf24}}
  .chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px}}
  .chart-box{{background:#1e293b;border-radius:10px;padding:16px}}
  .section-title{{color:#cbd5e1;font-size:13px;font-weight:600;margin-bottom:14px;letter-spacing:.04em;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{text-align:left;padding:8px 10px;color:#64748b;font-weight:600;border-bottom:2px solid #334155;font-size:11px;text-transform:uppercase}}
  th:not(:first-child){{text-align:right}}
  tr:hover{{background:rgba(56,189,248,.04)}}
  .checklist-box{{background:#1e293b;border-radius:10px;padding:20px}}
  svg{{max-width:100%;height:auto}}
</style>
</head>
<body>
<h1>Benchmark Suite v2</h1>
<div class="subtitle">OCI Robot Cloud · Port 8331 · Updated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} · Model: {MODEL_NAME}</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="label">Benchmarks Above SOTA</div>
    <div class="value">{above_sota}/{total_benchmarks}</div>
    <div class="sub">LIBERO-Spatial, LIBERO-Object</div>
  </div>
  <div class="kpi blue">
    <div class="label">Task Coverage</div>
    <div class="value">{BENCHMARK_COVERAGE_PCT}%</div>
    <div class="sub">FULL tier (300 episodes)</div>
  </div>
  <div class="kpi green">
    <div class="label">Cost / Full Benchmark</div>
    <div class="value">$19</div>
    <div class="sub">FULL tier · 4 hrs · A100</div>
  </div>
  <div class="kpi yellow">
    <div class="label">Pub. Checklist</div>
    <div class="value">{done_count}/{len(PUBLICATION_CHECKLIST)}</div>
    <div class="sub">{done_count} of {len(PUBLICATION_CHECKLIST)} criteria met</div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-box">
    {tier_svg}
  </div>
  <div class="chart-box">
    {baseline_svg}
  </div>
</div>

<div style="display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-bottom:28px">
  <div style="background:#1e293b;border-radius:10px;padding:20px">
    <div class="section-title">Detailed Comparison — {MODEL_NAME} vs Community Baselines</div>
    <table>
      <thead><tr>
        <th>Benchmark</th>
        <th style="text-align:right;color:#C74634">GR00T_v2</th>
        <th style="text-align:right;color:#fbbf24">SOTA</th>
        <th style="text-align:right;color:#38bdf8">RT-2</th>
        <th style="text-align:right;color:#a78bfa">Octo</th>
        <th style="text-align:right;color:#4ade80">Diff.Policy</th>
        <th style="text-align:right">vs SOTA</th>
      </tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
    <div style="margin-top:12px;color:#475569;font-size:11px">
      ★ LIBERO-Spatial +0.026 above SOTA &nbsp;·&nbsp; LIBERO-Object +0.021 above SOTA &nbsp;·&nbsp;
      BridgeV2 -0.180 (sim-to-real gap — real robot eval planned Q2 2026) &nbsp;·&nbsp; RoboMimic -0.020 (near SOTA)
    </div>
  </div>

  <div class="checklist-box">
    <div class="section-title">Publication-Ready Checklist</div>
    {checklist_html}
    <div style="margin-top:14px;background:#0f172a;border-radius:6px;padding:10px">
      <div style="color:#4ade80;font-size:11px;font-weight:600">{done_count}/{len(PUBLICATION_CHECKLIST)} criteria met</div>
      <div style="color:#64748b;font-size:11px;margin-top:4px">External review + cross-lab replication pending for CoRL 2026 submission</div>
    </div>
  </div>
</div>

<div style="margin-top:20px;color:#334155;font-size:11px;text-align:center">
  OCI Robot Cloud · Benchmark Suite v2 · Port 8331 · cycle-67B
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# App / server
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Benchmark Suite v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/tiers")
    async def api_tiers():
        return {"tiers": BENCHMARK_TIERS}

    @app.get("/api/baselines")
    async def api_baselines():
        return {
            "model": MODEL_NAME,
            "baselines": BASELINES,
            "above_sota_count": sum(1 for b in BASELINES if b["our_model"] >= b["sota"]),
        }

    @app.get("/api/checklist")
    async def api_checklist():
        return {
            "items": [{"done": d, "item": i} for d, i in PUBLICATION_CHECKLIST],
            "done": sum(1 for d, _ in PUBLICATION_CHECKLIST if d),
            "total": len(PUBLICATION_CHECKLIST),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8331, "service": "benchmark_v2"}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8331)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8331")
        server = HTTPServer(("0.0.0.0", 8331), Handler)
        server.serve_forever()
