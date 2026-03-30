"""Embodiment Registry Service — port 8246

Registry of supported robot embodiments with GR00T adapter compatibility matrix.
"""

import math
import random
import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

EMBODIMENTS = [
    {"id": "franka",     "name": "Franka Panda",   "type": "arm",       "dof": 7,  "demos_available": 1200, "demos_needed": 800},
    {"id": "ur5e",       "name": "UR5e",           "type": "arm",       "dof": 6,  "demos_available": 400,  "demos_needed": 600},
    {"id": "xarm6",      "name": "xArm 6",         "type": "arm",       "dof": 6,  "demos_available": 320,  "demos_needed": 500},
    {"id": "stretch",    "name": "Stretch RE3",    "type": "mobile",    "dof": 8,  "demos_available": 210,  "demos_needed": 700},
    {"id": "spot",       "name": "Boston Spot",    "type": "quadruped", "dof": 12, "demos_available": 580,  "demos_needed": 400},
    {"id": "unitreeh1",  "name": "Unitree H1",     "type": "humanoid",  "dof": 19, "demos_available": 150,  "demos_needed": 1500},
    {"id": "figure01",   "name": "Figure 01",      "type": "humanoid",  "dof": 22, "demos_available": 80,   "demos_needed": 2000},
    {"id": "apollo",     "name": "Apptronik Apollo","type": "humanoid",  "dof": 22, "demos_available": 60,   "demos_needed": 2000},
]

CAPABILITIES = ["manipulation", "locomotion", "mobile_manip", "bimanual", "tool_use"]

# SUPPORTED / PARTIAL / PLANNED / NOT_SUPPORTED
COMPAT_MATRIX = {
    "franka":    ["SUPPORTED",     "NOT_SUPPORTED", "NOT_SUPPORTED", "PARTIAL",       "SUPPORTED"],
    "ur5e":      ["PARTIAL",       "NOT_SUPPORTED", "NOT_SUPPORTED", "NOT_SUPPORTED", "PARTIAL"],
    "xarm6":     ["PARTIAL",       "NOT_SUPPORTED", "NOT_SUPPORTED", "PARTIAL",       "PARTIAL"],
    "stretch":   ["SUPPORTED",     "PARTIAL",       "SUPPORTED",     "NOT_SUPPORTED", "PARTIAL"],
    "spot":      ["PARTIAL",       "SUPPORTED",     "SUPPORTED",     "NOT_SUPPORTED", "PARTIAL"],
    "unitreeh1": ["PLANNED",       "PLANNED",       "PLANNED",       "PLANNED",       "PLANNED"],
    "figure01":  ["PLANNED",       "PLANNED",       "PLANNED",       "PLANNED",       "PLANNED"],
    "apollo":    ["PLANNED",       "PLANNED",       "PLANNED",       "PLANNED",       "PLANNED"],
}

STATUS_COLOR = {
    "SUPPORTED":     "#22c55e",
    "PARTIAL":       "#f59e0b",
    "PLANNED":       "#38bdf8",
    "NOT_SUPPORTED": "#374151",
}

STATUS_LABEL = {
    "SUPPORTED":     "S",
    "PARTIAL":       "P",
    "PLANNED":       "~",
    "NOT_SUPPORTED": "—",
}

# Derived metrics
_supported = sum(1 for e in EMBODIMENTS if COMPAT_MATRIX[e["id"]][0] == "SUPPORTED")
_gap_total = sum(max(0, e["demos_needed"] - e["demos_available"]) for e in EMBODIMENTS)
_humanoid_ids = [e["id"] for e in EMBODIMENTS if e["type"] == "humanoid"]
_humanoid_readiness = round(
    100 * sum(e["demos_available"] / e["demos_needed"] for e in EMBODIMENTS if e["id"] in _humanoid_ids)
    / len(_humanoid_ids), 1
)

# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_compat_svg() -> str:
    """Compatibility heatmap SVG."""
    cell_w, cell_h = 100, 40
    pad_left, pad_top = 130, 90
    n_rows = len(EMBODIMENTS)
    n_cols = len(CAPABILITIES)
    width  = pad_left + n_cols * cell_w + 20
    height = pad_top  + n_rows * cell_h + 30

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">']

    # Column headers
    cap_labels = ["Manip.", "Locomot.", "Mobile", "Bimanual", "Tool Use"]
    for ci, cap in enumerate(cap_labels):
        x = pad_left + ci * cell_w + cell_w // 2
        lines.append(f'<text x="{x}" y="{pad_top - 10}" text-anchor="middle" font-size="11" fill="#94a3b8" font-family="monospace">{cap}</text>')

    # Row headers + cells
    for ri, emb in enumerate(EMBODIMENTS):
        y_top = pad_top + ri * cell_h
        y_mid = y_top + cell_h // 2
        # row label
        lines.append(f'<text x="{pad_left - 8}" y="{y_mid + 4}" text-anchor="end" font-size="11" fill="#cbd5e1" font-family="monospace">{emb["name"]}</text>')
        for ci, cap in enumerate(CAPABILITIES):
            status = COMPAT_MATRIX[emb["id"]][ci]
            color  = STATUS_COLOR[status]
            label  = STATUS_LABEL[status]
            x_left = pad_left + ci * cell_w + 2
            lines.append(f'<rect x="{x_left}" y="{y_top + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="4" fill="{color}" opacity="0.85"/>')
            lines.append(f'<text x="{x_left + (cell_w-4)//2}" y="{y_top + cell_h//2 + 4}" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f172a" font-family="monospace">{label}</text>')

    # Legend
    legend_items = list(STATUS_COLOR.items())
    lx = pad_left
    ly = height - 18
    for status, color in legend_items:
        lines.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" fill="{color}"/>')
        lines.append(f'<text x="{lx + 15}" y="{ly}" font-size="10" fill="#94a3b8" font-family="monospace">{status}</text>')
        lx += len(status) * 7 + 30

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_demos_svg() -> str:
    """Bar chart: available vs needed demos per embodiment."""
    bar_h = 22
    gap   = 8
    pad_left = 145
    pad_top  = 40
    n = len(EMBODIMENTS)
    max_val  = max(max(e["demos_available"], e["demos_needed"]) for e in EMBODIMENTS)
    width    = 620
    chart_w  = width - pad_left - 20
    height   = pad_top + n * (bar_h * 2 + gap) + 50

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">']
    lines.append(f'<text x="{width//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#e2e8f0" font-family="monospace">Demo Coverage: Available vs Required (SR=0.75 target)</text>')

    for i, emb in enumerate(EMBODIMENTS):
        y0 = pad_top + i * (bar_h * 2 + gap)
        avail_w = int(chart_w * emb["demos_available"] / max_val)
        need_w  = int(chart_w * emb["demos_needed"]    / max_val)
        coverage = emb["demos_available"] / emb["demos_needed"]
        bar_color = "#22c55e" if coverage >= 1.0 else ("#f59e0b" if coverage >= 0.5 else "#ef4444")

        # row label
        lines.append(f'<text x="{pad_left - 5}" y="{y0 + bar_h - 4}" text-anchor="end" font-size="10" fill="#cbd5e1" font-family="monospace">{emb["name"]}</text>')
        # needed bar (background)
        lines.append(f'<rect x="{pad_left}" y="{y0}" width="{need_w}" height="{bar_h}" rx="3" fill="#334155"/>')
        lines.append(f'<text x="{pad_left + need_w + 3}" y="{y0 + bar_h - 6}" font-size="9" fill="#64748b" font-family="monospace">{emb["demos_needed"]} needed</text>')
        # available bar
        lines.append(f'<rect x="{pad_left}" y="{y0 + bar_h + 2}" width="{avail_w}" height="{bar_h - 4}" rx="3" fill="{bar_color}"/>')
        lines.append(f'<text x="{pad_left + avail_w + 3}" y="{y0 + bar_h * 2 - 4}" font-size="9" fill="{bar_color}" font-family="monospace">{emb["demos_available"]} avail ({int(coverage*100)}%)</text>')

    # legend
    lines.append(f'<rect x="{pad_left}" y="{height - 22}" width="10" height="10" fill="#22c55e"/>')
    lines.append(f'<text x="{pad_left + 13}" y="{height - 13}" font-size="10" fill="#94a3b8" font-family="monospace">Sufficient</text>')
    lines.append(f'<rect x="{pad_left + 85}" y="{height - 22}" width="10" height="10" fill="#f59e0b"/>')
    lines.append(f'<text x="{pad_left + 98}" y="{height - 13}" font-size="10" fill="#94a3b8" font-family="monospace">Partial</text>')
    lines.append(f'<rect x="{pad_left + 155}" y="{height - 22}" width="10" height="10" fill="#ef4444"/>')
    lines.append(f'<text x="{pad_left + 168}" y="{height - 13}" font-size="10" fill="#94a3b8" font-family="monospace">Insufficient</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _build_html() -> str:
    compat_svg = _build_compat_svg()
    demos_svg  = _build_demos_svg()
    rows = ""
    for emb in EMBODIMENTS:
        caps_supported = sum(1 for s in COMPAT_MATRIX[emb["id"]] if s == "SUPPORTED")
        gap = max(0, emb["demos_needed"] - emb["demos_available"])
        tag_color = {"arm": "#38bdf8", "mobile": "#a78bfa", "quadruped": "#f59e0b", "humanoid": "#C74634"}.get(emb["type"], "#64748b")
        rows += f"""
        <tr>
          <td style="color:#e2e8f0">{emb["name"]}</td>
          <td><span style="background:{tag_color};color:#0f172a;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">{emb["type"].upper()}</span></td>
          <td style="color:#94a3b8;text-align:center">{emb["dof"]}</td>
          <td style="color:#22c55e;text-align:center">{caps_supported}</td>
          <td style="color:#f59e0b;text-align:center">{emb["demos_available"]}</td>
          <td style="color:{('#ef4444' if gap > 0 else '#22c55e')};text-align:center">{gap if gap > 0 else '✓'}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Embodiment Registry — OCI Robot Cloud</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',monospace,sans-serif; }}
    header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    header h1 {{ font-size:22px; font-weight:700; color:#fff; }}
    header .badge {{ background:#C74634; color:#fff; padding:3px 12px; border-radius:20px; font-size:12px; font-weight:600; }}
    .port-badge {{ background:#1e3a4f; color:#38bdf8; padding:3px 10px; border-radius:20px; font-size:12px; border:1px solid #38bdf8; }}
    .container {{ padding:28px 32px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:28px; }}
    .metric-card {{ background:#1e293b; border-radius:10px; padding:18px; border:1px solid #334155; }}
    .metric-card .label {{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px; }}
    .metric-card .value {{ font-size:28px; font-weight:700; color:#38bdf8; }}
    .metric-card .sub {{ font-size:11px; color:#94a3b8; margin-top:4px; }}
    .section {{ background:#1e293b; border-radius:10px; padding:20px; margin-bottom:24px; border:1px solid #334155; }}
    .section h2 {{ font-size:14px; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ text-align:left; font-size:11px; color:#64748b; text-transform:uppercase; padding:8px 10px; border-bottom:1px solid #334155; }}
    td {{ padding:9px 10px; border-bottom:1px solid #1e293b; font-size:13px; }}
    tr:hover td {{ background:#243044; }}
    .svg-wrap {{ overflow-x:auto; }}
    footer {{ text-align:center; padding:16px; font-size:11px; color:#475569; }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>Embodiment Registry</h1>
    <div style="margin-top:4px;font-size:12px;color:#94a3b8">GR00T Adapter Compatibility Matrix — OCI Robot Cloud</div>
  </div>
  <span class="badge">LIVE</span>
  <span class="port-badge">:8246</span>
  <div style="margin-left:auto;font-size:12px;color:#475569">Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</header>
<div class="container">
  <div class="metrics">
    <div class="metric-card">
      <div class="label">Supported Embodiments</div>
      <div class="value">{_supported}</div>
      <div class="sub">of {len(EMBODIMENTS)} registered</div>
    </div>
    <div class="metric-card">
      <div class="label">Total Demo Gap</div>
      <div class="value" style="color:#f59e0b">{_gap_total:,}</div>
      <div class="sub">demos still needed</div>
    </div>
    <div class="metric-card">
      <div class="label">Humanoid Readiness</div>
      <div class="value" style="color:#C74634">{_humanoid_readiness}%</div>
      <div class="sub">avg data coverage (H1/Fig01/Apollo)</div>
    </div>
    <div class="metric-card">
      <div class="label">Capabilities Tracked</div>
      <div class="value">{len(CAPABILITIES)}</div>
      <div class="sub">per embodiment</div>
    </div>
  </div>

  <div class="section">
    <h2>GR00T Adapter Compatibility Matrix</h2>
    <div class="svg-wrap">{compat_svg}</div>
  </div>

  <div class="section">
    <h2>Demo Data Coverage (SR=0.75 target)</h2>
    <div class="svg-wrap">{demos_svg}</div>
  </div>

  <div class="section">
    <h2>Registered Embodiments</h2>
    <table>
      <thead><tr>
        <th>Name</th><th>Type</th><th style="text-align:center">DoF</th>
        <th style="text-align:center">Caps Supported</th>
        <th style="text-align:center">Demos Available</th>
        <th style="text-align:center">Demo Gap</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
<footer>OCI Robot Cloud &mdash; Embodiment Registry &mdash; Port 8246</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Embodiment Registry",
        description="Registry of supported robot embodiments with GR00T adapter compatibility matrix",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "embodiment_registry", "port": 8246}

    @app.get("/api/embodiments")
    async def list_embodiments():
        return {"embodiments": EMBODIMENTS, "count": len(EMBODIMENTS)}

    @app.get("/api/compatibility")
    async def compatibility_matrix():
        result = {}
        for emb in EMBODIMENTS:
            result[emb["id"]] = {cap: COMPAT_MATRIX[emb["id"]][i] for i, cap in enumerate(CAPABILITIES)}
        return {"matrix": result, "capabilities": CAPABILITIES}

    @app.get("/api/metrics")
    async def metrics():
        return {
            "supported_embodiments": _supported,
            "total_embodiments": len(EMBODIMENTS),
            "total_demo_gap": _gap_total,
            "humanoid_readiness_pct": _humanoid_readiness,
            "capabilities_tracked": len(CAPABILITIES),
        }

else:
    # Fallback: stdlib http.server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8246)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8246")
        server = HTTPServer(("0.0.0.0", 8246), _Handler)
        server.serve_forever()
