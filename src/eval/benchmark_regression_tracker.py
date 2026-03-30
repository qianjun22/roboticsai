"""Benchmark Regression Tracker — FastAPI service on port 8272.

Tracks benchmark performance across model updates to catch regressions
before deployment. Provides control charts and suite comparison views.
"""

from __future__ import annotations

import math
import random
import json
from datetime import datetime, timedelta
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

NUM_VERSIONS = 20
CURRENT_VERSION = 20

# Base success-rate trajectory with two injected regressions
_BASE_SR = [
    0.71, 0.73, 0.74, 0.75, 0.76, 0.74, 0.75, 0.76, 0.77, 0.78,
    0.72,  # v11 regression: data-augmentation bug (-6pp)
    0.76, 0.77, 0.78, 0.79, 0.79,
    0.76,  # v17 regression: chunk_size misconfiguration (-3pp)
    0.77, 0.78, 0.78,
]

VERSION_NOTES = {
    11: "Regression: data-augmentation bug (-6pp) — fixed in v12",
    17: "Regression: chunk_size misconfiguration (-3pp) — fixed in v18",
    20: "Current — v20 PASSING (SR=0.78)",
}

BENCHMARK_SUITES = [
    {"name": "LIBERO-Spatial",  "current": 0.847, "previous": 0.831},
    {"name": "LIBERO-Object",   "current": 0.803, "previous": 0.812},
    {"name": "LIBERO-Goal",     "current": 0.769, "previous": 0.754},
    {"name": "LIBERO-100",      "current": 0.721, "previous": 0.718},
    {"name": "LIBERO-Custom",   "current": 0.684, "previous": 0.671},
]

_mean_sr = sum(_BASE_SR) / len(_BASE_SR)
_variance = sum((x - _mean_sr) ** 2 for x in _BASE_SR) / len(_BASE_SR)
_std_sr = math.sqrt(_variance)
UCL = _mean_sr + 2 * _std_sr
LCL = max(0.0, _mean_sr - 2 * _std_sr)

KEY_METRICS = {
    "regression_frequency": "2 in 20 versions (10%)",
    "avg_recovery_time": "1.5 versions (~3 days)",
    "benchmark_coverage": "5 suites / 847 tasks",
    "sla_gate_pass_rate": "90.0%",
    "current_version": f"v{CURRENT_VERSION}",
    "current_sr": f"{_BASE_SR[CURRENT_VERSION - 1]:.3f}",
    "status": "PASSING",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _build_control_chart_svg() -> str:
    """Control chart: SR over 20 versions with UCL/LCL bands."""
    W, H = 700, 280
    pad_l, pad_r, pad_t, pad_b = 55, 25, 20, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    sr_min, sr_max = 0.60, 0.92

    def sx(ver_idx: int) -> float:  # version index 0-based
        return pad_l + ver_idx / (NUM_VERSIONS - 1) * chart_w

    def sy(val: float) -> float:
        return pad_t + (1 - (val - sr_min) / (sr_max - sr_min)) * chart_h

    lines: list[str] = []

    # Background
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # UCL/LCL bands (filled region)
    ucl_y = sy(UCL)
    lcl_y = sy(LCL)
    lines.append(
        f'<rect x="{pad_l}" y="{ucl_y:.1f}" '
        f'width="{chart_w}" height="{lcl_y - ucl_y:.1f}" '
        f'fill="#1e3a5f" opacity="0.4"/>'
    )

    # UCL line
    lines.append(
        f'<line x1="{pad_l}" y1="{ucl_y:.1f}" x2="{pad_l + chart_w}" y2="{ucl_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{ucl_y:.1f}" fill="#f59e0b" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">UCL</text>'
    )

    # LCL line
    lines.append(
        f'<line x1="{pad_l}" y1="{lcl_y:.1f}" x2="{pad_l + chart_w}" y2="{lcl_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{lcl_y:.1f}" fill="#f59e0b" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">LCL</text>'
    )

    # Mean line
    mean_y = sy(_mean_sr)
    lines.append(
        f'<line x1="{pad_l}" y1="{mean_y:.1f}" x2="{pad_l + chart_w}" y2="{mean_y:.1f}" '
        f'stroke="#64748b" stroke-width="1" stroke-dasharray="2,2"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{mean_y:.1f}" fill="#64748b" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">\u03bc</text>'
    )

    # SR polyline
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(_BASE_SR))
    lines.append(
        f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    )

    # Data points
    regression_versions = {11, 17}  # 1-based
    for i, v in enumerate(_BASE_SR):
        ver = i + 1
        cx, cy = sx(i), sy(v)
        if ver in regression_versions:
            color = "#C74634"
            r = 5
        elif ver == CURRENT_VERSION:
            color = "#22c55e"
            r = 6
        else:
            color = "#38bdf8"
            r = 3
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}"/>')
        if ver in regression_versions:
            lines.append(
                f'<text x="{cx:.1f}" y="{cy - 9:.1f}" fill="{color}" font-size="8" '
                f'text-anchor="middle">v{ver}</text>'
            )
        if ver == CURRENT_VERSION:
            lines.append(
                f'<text x="{cx:.1f}" y="{cy - 10:.1f}" fill="#22c55e" font-size="9" '
                f'text-anchor="middle" font-weight="bold">v{ver}</text>'
            )

    # X-axis ticks
    for i in range(NUM_VERSIONS):
        ver = i + 1
        x = sx(i)
        lines.append(
            f'<text x="{x:.1f}" y="{pad_t + chart_h + 14}" fill="#94a3b8" '
            f'font-size="8" text-anchor="middle">{ver}</text>'
        )

    # Y-axis ticks
    for tick in [0.65, 0.70, 0.75, 0.80, 0.85]:
        ty = sy(tick)
        lines.append(
            f'<line x1="{pad_l - 3}" y1="{ty:.1f}" x2="{pad_l}" y2="{ty:.1f}" stroke="#334155"/>'
        )
        lines.append(
            f'<text x="{pad_l - 6}" y="{ty:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end" dominant-baseline="middle">{tick:.2f}</text>'
        )
        lines.append(
            f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + chart_w}" y2="{ty:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )

    # Axes
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )

    # Labels
    lines.append(
        f'<text x="{W // 2}" y="{H - 5}" fill="#94a3b8" font-size="10" '
        f'text-anchor="middle">Model Version</text>'
    )
    lines.append(
        f'<text x="12" y="{H // 2}" fill="#94a3b8" font-size="10" '
        f'text-anchor="middle" transform="rotate(-90,12,{H // 2})">Success Rate</text>'
    )

    # Legend
    lx = pad_l + 10
    ly = pad_t + 8
    for color, label in [
        ("#38bdf8", "SR value"),
        ("#C74634", "Regression"),
        ("#22c55e", f"Current v{CURRENT_VERSION}"),
        ("#f59e0b", "UCL/LCL ±2σ"),
    ]:
        lines.append(f'<circle cx="{lx + 4}" cy="{ly}" r="4" fill="{color}"/>')
        lines.append(
            f'<text x="{lx + 12}" y="{ly}" fill="#cbd5e1" font-size="9" '
            f'dominant-baseline="middle">{label}</text>'
        )
        lx += 115

    inner = "\n  ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n  {inner}\n</svg>'


def _build_suite_comparison_svg() -> str:
    """Benchmark suite comparison table SVG."""
    W, H = 700, 200
    pad_x, pad_y = 20, 15
    row_h = 32
    col_widths = [180, 120, 120, 80, 80, 80]  # name, curr, prev, delta, bar_curr, bar_prev
    headers = ["Suite", "Current (v20)", "Previous (v19)", "Delta", "", ""]

    lines: list[str] = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # Header row background
    lines.append(
        f'<rect x="{pad_x}" y="{pad_y}" width="{W - 2 * pad_x}" height="{row_h}" '
        f'fill="#1e293b" rx="4"/>'
    )

    # Column headers
    cx = pad_x + 8
    for i, (hdr, cw) in enumerate(zip(headers[:4], col_widths[:4])):
        lines.append(
            f'<text x="{cx}" y="{pad_y + row_h // 2}" fill="#94a3b8" font-size="10" '
            f'font-weight="bold" dominant-baseline="middle">{hdr}</text>'
        )
        cx += cw

    # Bar header
    lines.append(
        f'<text x="{cx + 10}" y="{pad_y + row_h // 2}" fill="#94a3b8" font-size="10" '
        f'font-weight="bold" dominant-baseline="middle">SR Bars</text>'
    )

    # Data rows
    for row_idx, suite in enumerate(BENCHMARK_SUITES):
        ry = pad_y + (row_idx + 1) * row_h
        bg = "#0f172a" if row_idx % 2 == 0 else "#131f2e"
        lines.append(
            f'<rect x="{pad_x}" y="{ry}" width="{W - 2 * pad_x}" height="{row_h}" '
            f'fill="{bg}"/>'
        )

        delta = suite["current"] - suite["previous"]
        delta_color = "#22c55e" if delta >= 0 else "#C74634"
        arrow = "▲" if delta >= 0 else "▼"

        cx2 = pad_x + 8
        mid_y = ry + row_h // 2

        # Suite name
        name_color = "#38bdf8" if row_idx == 0 else "#e2e8f0"
        font_w = "bold" if row_idx == 0 else "normal"
        lines.append(
            f'<text x="{cx2}" y="{mid_y}" fill="{name_color}" font-size="11" '
            f'font-weight="{font_w}" dominant-baseline="middle">{suite["name"]}</text>'
        )
        cx2 += col_widths[0]

        # Current SR
        lines.append(
            f'<text x="{cx2}" y="{mid_y}" fill="#f1f5f9" font-size="11" '
            f'dominant-baseline="middle">{suite["current"]:.3f}</text>'
        )
        cx2 += col_widths[1]

        # Previous SR
        lines.append(
            f'<text x="{cx2}" y="{mid_y}" fill="#94a3b8" font-size="11" '
            f'dominant-baseline="middle">{suite["previous"]:.3f}</text>'
        )
        cx2 += col_widths[2]

        # Delta
        lines.append(
            f'<text x="{cx2}" y="{mid_y}" fill="{delta_color}" font-size="11" '
            f'font-weight="bold" dominant-baseline="middle">{arrow} {abs(delta):.3f}</text>'
        )
        cx2 += col_widths[3]

        # Mini bars (current + previous side by side)
        bar_max_w = 130
        bar_scale = bar_max_w  # SR 0→1 → 0→bar_max_w
        bar_h = 10
        by_curr = mid_y - bar_h - 1
        by_prev = mid_y + 1

        # Previous bar
        lines.append(
            f'<rect x="{cx2}" y="{by_prev}" '
            f'width="{suite["previous"] * bar_scale:.1f}" height="{bar_h}" '
            f'fill="#475569" rx="2"/>'
        )
        # Current bar
        lines.append(
            f'<rect x="{cx2}" y="{by_curr}" '
            f'width="{suite["current"] * bar_scale:.1f}" height="{bar_h}" '
            f'fill="#38bdf8" rx="2"/>'
        )

    inner = "\n  ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n  {inner}\n</svg>'


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _render_html() -> str:
    control_svg = _build_control_chart_svg()
    suite_svg = _build_suite_comparison_svg()
    metrics_json = json.dumps(KEY_METRICS, indent=2)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    status_color = "#22c55e" if KEY_METRICS["status"] == "PASSING" else "#C74634"

    metric_cards = ""
    for k, v in KEY_METRICS.items():
        label = k.replace("_", " ").title()
        val_color = status_color if k == "status" else "#38bdf8"
        metric_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px 18px;">
          <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">{label}</div>
          <div style="color:{val_color};font-size:15px;font-weight:700;">{v}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark Regression Tracker | OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;min-height:100vh;}}
  header{{background:#1e293b;border-bottom:3px solid #C74634;padding:16px 32px;display:flex;align-items:center;justify-content:space-between;}}
  .logo{{color:#C74634;font-size:20px;font-weight:800;letter-spacing:1px;}}
  .subtitle{{color:#94a3b8;font-size:13px;}}
  .badge{{background:#C74634;color:#fff;border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;}}
  main{{padding:28px 32px;max-width:900px;margin:0 auto;}}
  h2{{color:#f1f5f9;font-size:16px;font-weight:700;margin-bottom:14px;border-left:4px solid #C74634;padding-left:10px;}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:24px;}}
  .metrics-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;}}
  .ts{{color:#64748b;font-size:11px;text-align:right;margin-top:8px;}}
  pre{{background:#0d1b2a;border-radius:6px;padding:12px;font-size:11px;color:#94a3b8;overflow:auto;}}
  .version-notes{{margin-top:12px;}}
  .note-item{{padding:6px 10px;border-radius:4px;margin-bottom:4px;font-size:12px;}}
  .note-regression{{background:#2d0f0a;border-left:3px solid #C74634;color:#fca5a5;}}
  .note-current{{background:#052e16;border-left:3px solid #22c55e;color:#86efac;}}
  .note-normal{{background:#1e293b;border-left:3px solid #475569;color:#94a3b8;}}
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">OCI ROBOT CLOUD</div>
    <div class="subtitle">Benchmark Regression Tracker — Port 8272</div>
  </div>
  <span class="badge">SLA GATE: PASSING</span>
</header>
<main>
  <div class="metrics-grid">{metric_cards}</div>

  <div class="card">
    <h2>Control Chart — Success Rate over Model Versions</h2>
    {control_svg}
    <div class="version-notes">
      <div class="note-item note-regression">v11 Regression: data-augmentation bug caused -6pp drop — fixed in v12 (1 version recovery)</div>
      <div class="note-item note-regression">v17 Regression: chunk_size misconfiguration caused -3pp drop — fixed in v18 (1 version recovery)</div>
      <div class="note-item note-current">v20 Current: SR=0.780 — PASSING SLA gate (threshold ≥ 0.75)</div>
    </div>
  </div>

  <div class="card">
    <h2>Benchmark Suite Comparison — v20 vs v19</h2>
    {suite_svg}
    <div style="margin-top:10px;font-size:11px;color:#64748b;">
      Blue bars = current v20 &nbsp;|&nbsp; Gray bars = previous v19 &nbsp;|&nbsp;
      ▲ green = improvement &nbsp;|&nbsp; ▼ red = regression
    </div>
  </div>

  <div class="card">
    <h2>Raw Metrics</h2>
    <pre>{metrics_json}</pre>
    <div class="ts">Last updated: {ts}</div>
  </div>
</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Benchmark Regression Tracker",
        description="Tracks benchmark performance across model updates",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _render_html()

    @app.get("/api/versions")
    def get_versions():
        return JSONResponse({
            "versions": [
                {
                    "version": i + 1,
                    "sr": _BASE_SR[i],
                    "regression": (i + 1) in {11, 17},
                    "current": (i + 1) == CURRENT_VERSION,
                    "note": VERSION_NOTES.get(i + 1, ""),
                }
                for i in range(NUM_VERSIONS)
            ],
            "mean_sr": round(_mean_sr, 4),
            "ucl": round(UCL, 4),
            "lcl": round(LCL, 4),
        })

    @app.get("/api/suites")
    def get_suites():
        return JSONResponse({"suites": BENCHMARK_SUITES})

    @app.get("/api/metrics")
    def get_metrics():
        return JSONResponse(KEY_METRICS)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "benchmark_regression_tracker", "port": 8272}

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = _render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress noisy logs
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8272)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8272")
        with socketserver.TCPServer(("", 8272), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8272")
            httpd.serve_forever()
