"""Foundation Model Updater — FastAPI service on port 8316.

Manages updates from NVIDIA when new GR00T base model versions are released.
Tracks adoption readiness, migration cost, and capability deltas per upgrade.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MODEL_VERSIONS = [
    {
        "version": "N1.0",
        "release_date": "Oct 2025",
        "release_ts": 0,
        "params": "1.5B",
        "key_capability": "Single-arm pick & place, basic grasping",
        "adoption_lag_days": 45,
        "adoption_status": "deprecated",
    },
    {
        "version": "N1.5",
        "release_date": "Jan 2026",
        "release_ts": 3,
        "params": "2.1B",
        "key_capability": "Multi-object manipulation, improved contact",
        "adoption_lag_days": 28,
        "adoption_status": "deprecated",
    },
    {
        "version": "N1.6",
        "release_date": "Mar 2026",
        "release_ts": 5,
        "params": "3.0B",
        "key_capability": "Cross-embodiment transfer, deformable objects",
        "adoption_lag_days": 12,
        "adoption_status": "active",
    },
    {
        "version": "N2.0",
        "release_date": "Jun 2026 (proj.)",
        "release_ts": 8,
        "params": "6.0B",
        "key_capability": "Bimanual tasks, new robot tasks, long-horizon planning",
        "adoption_lag_days": None,
        "adoption_status": "projected",
    },
]

RADAR_DIMENSIONS = [
    "dataset_compatibility",
    "API_compatibility",
    "fine_tune_pipeline_ready",
    "eval_suite_updated",
    "SDK_updated",
    "customer_migration_effort",  # lower = easier, inverted for display
]

# N1.5 → N1.6 readiness (already adopted)
RADAR_N16 = [0.95, 0.90, 0.88, 0.92, 0.85, 0.80]
# N1.6 → N2.0 projected readiness
RADAR_N20 = [0.70, 0.65, 0.73, 0.60, 0.68, 0.45]

KEY_METRICS = {
    "current_version": "N1.6",
    "n16_adoption_pct": 100,
    "n20_pipeline_readiness_pct": 73,
    "n20_projected_release": "Jun 2026",
    "n20_new_capabilities": "bimanual support, new robot tasks",
    "customer_migration_est_weeks": 2,
    "avg_adoption_lag_days": round((45 + 28 + 12) / 3, 1),
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_version_timeline() -> str:
    """SVG timeline of GR00T base model releases with adoption lag annotations."""
    W, H = 780, 200
    margin_l, margin_r = 60, 40
    margin_t, margin_b = 50, 60
    inner_w = W - margin_l - margin_r
    inner_h = H - margin_t - margin_b
    cy = margin_t + inner_h // 2

    # x positions (evenly spaced)
    xs = [
        margin_l + int(inner_w * i / (len(MODEL_VERSIONS) - 1))
        for i in range(len(MODEL_VERSIONS))
    ]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Axis line
    lines.append(f'<line x1="{xs[0]}" y1="{cy}" x2="{xs[-1]}" y2="{cy}" stroke="#475569" stroke-width="2"/>')

    colors = {"deprecated": "#64748b", "active": "#C74634", "projected": "#38bdf8"}
    label_offset = [-1, 1, -1, 1]  # alternate above/below

    for i, (v, x) in enumerate(zip(MODEL_VERSIONS, xs)):
        color = colors[v["adoption_status"]]
        r = 10 if v["adoption_status"] == "active" else 7

        # Node circle
        lines.append(f'<circle cx="{x}" cy="{cy}" r="{r}" fill="{color}" stroke="#0f172a" stroke-width="2"/>')

        # Version label
        side = label_offset[i]
        ty = cy - 28 if side < 0 else cy + 40
        lines.append(f'<text x="{x}" y="{ty}" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold" font-family="monospace">{v["version"]}</text>')

        # Date
        dy = cy - 16 if side < 0 else cy + 52
        lines.append(f'<text x="{x}" y="{dy}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">{v["release_date"]}</text>')

        # Params
        py2 = cy - 44 if side < 0 else cy + 64
        lines.append(f'<text x="{x}" y="{py2}" text-anchor="middle" fill="#cbd5e1" font-size="10" font-family="sans-serif">{v["params"]}</text>')

        # Adoption lag badge
        if v["adoption_lag_days"] is not None:
            lag_color = "#22c55e" if v["adoption_lag_days"] < 20 else "#f59e0b"
            bx, by = x - 20, cy + (16 if side < 0 else -26)
            lines.append(f'<rect x="{bx}" y="{by}" width="40" height="16" rx="4" fill="{lag_color}" opacity="0.25"/>')
            lines.append(f'<text x="{x}" y="{by+11}" text-anchor="middle" fill="{lag_color}" font-size="10" font-family="sans-serif">lag {v["adoption_lag_days"]}d</text>')
        else:
            bx, by = x - 20, cy + (16 if side < 0 else -26)
            lines.append(f'<rect x="{bx}" y="{by}" width="40" height="16" rx="4" fill="#38bdf8" opacity="0.18"/>')
            lines.append(f'<text x="{x}" y="{by+11}" text-anchor="middle" fill="#38bdf8" font-size="10" font-family="sans-serif">TBD</text>')

    # Legend
    legend = [("active", "#C74634", "Active"), ("deprecated", "#64748b", "Deprecated"), ("projected", "#38bdf8", "Projected")]
    lx = margin_l
    for key, col, label in legend:
        lines.append(f'<circle cx="{lx+6}" cy="{H-14}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{lx+14}" y="{H-10}" fill="#94a3b8" font-size="11" font-family="sans-serif">{label}</text>')
        lx += 90

    lines.append('<text x="390" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold" font-family="sans-serif">GR00T Base Model Version History</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def svg_adoption_radar() -> str:
    """SVG radar chart comparing N1.5→N1.6 vs N1.6→N2.0 adoption readiness."""
    W, H = 480, 400
    cx, cy, radius = W // 2, H // 2 + 10, 140
    n = len(RADAR_DIMENSIONS)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def polar(val: float, idx: int):
        a = angles[idx]
        r = radius * val
        return cx + r * math.cos(a), cy - r * math.sin(a)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = [polar(ring, i) for i in range(n)]
        poly = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        lines.append(f'<polygon points="{poly}" fill="none" stroke="#334155" stroke-width="1"/>')

    # Axis lines
    for i in range(n):
        x1, y1 = polar(0.0, i)
        x2, y2 = polar(1.0, i)
        lines.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')

    def draw_shape(data, color, opacity):
        pts = [polar(v, i) for i, v in enumerate(data)]
        poly = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        lines.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="2"/>')

    draw_shape(RADAR_N16, "#C74634", 0.25)
    draw_shape(RADAR_N20, "#38bdf8", 0.20)

    # Axis labels
    short_labels = [
        "dataset\ncompat", "API\ncompat", "finetune\npipeline",
        "eval\nsuite", "SDK\nupdated", "migration\neffort"
    ]
    for i, label in enumerate(short_labels):
        x, y = polar(1.15, i)
        parts = label.split('\n')
        for j, part in enumerate(parts):
            lines.append(f'<text x="{x:.1f}" y="{y:.1f + j*13}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">{part}</text>')

    # Legend
    lines.append(f'<rect x="20" y="{H-50}" width="12" height="12" fill="#C74634" opacity="0.8"/>')
    lines.append(f'<text x="36" y="{H-40}" fill="#e2e8f0" font-size="11" font-family="sans-serif">N1.5→N1.6 (adopted)</text>')
    lines.append(f'<rect x="20" y="{H-32}" width="12" height="12" fill="#38bdf8" opacity="0.8"/>')
    lines.append(f'<text x="36" y="{H-22}" fill="#e2e8f0" font-size="11" font-family="sans-serif">N1.6→N2.0 (projected)</text>')

    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold" font-family="sans-serif">Adoption Readiness Radar</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    timeline_svg = svg_version_timeline()
    radar_svg = svg_adoption_radar()
    m = KEY_METRICS
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def metric_card(title, value, sub="", color="#38bdf8"):
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:16px 20px;border-left:3px solid {color};">
          <div style="color:#94a3b8;font-size:12px;margin-bottom:4px;">{title}</div>
          <div style="color:{color};font-size:24px;font-weight:700;">{value}</div>
          {f'<div style="color:#64748b;font-size:11px;margin-top:4px;">{sub}</div>' if sub else ''}
        </div>"""

    cards = [
        metric_card("Current Version", m["current_version"], "running on OCI", "#C74634"),
        metric_card("N1.6 Adoption", f"{m['n16_adoption_pct']}%", "fully adopted", "#22c55e"),
        metric_card("N2.0 Pipeline Readiness", f"{m['n20_pipeline_readiness_pct']}%", f"projected {m['n20_projected_release']}", "#38bdf8"),
        metric_card("Avg Adoption Lag", f"{m['avg_adoption_lag_days']}d", "across N1.0–N1.6", "#f59e0b"),
        metric_card("Customer Migration Est.", f"{m['customer_migration_est_weeks']} weeks", "for N1.6→N2.0", "#a78bfa"),
        metric_card("N2.0 New Capabilities", m["n20_new_capabilities"], "bimanual + new robot tasks", "#38bdf8"),
    ]

    version_rows = ""
    for v in MODEL_VERSIONS:
        status_color = {"deprecated": "#64748b", "active": "#22c55e", "projected": "#38bdf8"}[v["adoption_status"]]
        lag = f"{v['adoption_lag_days']}d" if v["adoption_lag_days"] is not None else "—"
        version_rows += f"""
        <tr>
          <td style="color:#C74634;font-weight:700;font-family:monospace;">{v['version']}</td>
          <td style="color:#94a3b8;">{v['release_date']}</td>
          <td style="color:#cbd5e1;">{v['params']}</td>
          <td style="color:#e2e8f0;font-size:12px;">{v['key_capability']}</td>
          <td style="color:#f59e0b;">{lag}</td>
          <td><span style="color:{status_color};background:{status_color}22;padding:2px 8px;border-radius:9999px;font-size:11px;">{v['adoption_status']}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Foundation Model Updater — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px;}}
    h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px;}}
    h2{{color:#38bdf8;font-size:15px;font-weight:600;margin:28px 0 12px;}}
    .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px;}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:28px;}}
    .svg-row{{display:flex;flex-wrap:wrap;gap:24px;margin-bottom:28px;align-items:flex-start;}}
    table{{width:100%;border-collapse:collapse;}}
    th{{color:#64748b;font-size:12px;text-align:left;padding:8px 12px;border-bottom:1px solid #1e293b;}}
    td{{padding:10px 12px;border-bottom:1px solid #1e293b22;font-size:13px;vertical-align:top;}}
    tr:hover td{{background:#1e293b44;}}
    .footer{{color:#334155;font-size:11px;margin-top:32px;text-align:center;}}
  </style>
</head>
<body>
  <h1>Foundation Model Updater</h1>
  <div class="subtitle">OCI Robot Cloud — GR00T Base Model Version Tracker &nbsp;·&nbsp; port 8316 &nbsp;·&nbsp; {now}</div>

  <div class="grid">{''.join(cards)}</div>

  <h2>Version History &amp; Adoption Readiness</h2>
  <div class="svg-row">
    <div>{timeline_svg}</div>
    <div>{radar_svg}</div>
  </div>

  <h2>Model Version Details</h2>
  <table>
    <thead><tr><th>Version</th><th>Release</th><th>Params</th><th>Key Capability</th><th>Adoption Lag</th><th>Status</th></tr></thead>
    <tbody>{version_rows}</tbody>
  </table>

  <div class="footer">OCI Robot Cloud &mdash; Foundation Model Updater &mdash; cycle-64A</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Foundation Model Updater",
        description="Tracks GR00T base model updates, adoption readiness, and migration cost.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "foundation_model_updater", "port": 8316}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/versions")
    async def versions():
        return {"versions": MODEL_VERSIONS}

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress default logging


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8316)
    else:
        print("FastAPI not available — using stdlib http.server on port 8316")
        with socketserver.TCPServer(("", 8316), Handler) as httpd:
            httpd.serve_forever()
