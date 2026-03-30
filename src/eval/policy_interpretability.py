"""Policy Interpretability Service — port 8348

Interprets GR00T policy decisions using saliency maps and probing classifiers.
Stdlib-only at module level; FastAPI loaded at runtime.
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

SALIENCY_REGIONS = [
    {"id": "cube_surface",  "label": "Cube Surface",    "score": 0.41, "x": 210, "y": 155, "w": 80, "h": 60,  "color": "rgba(199,70,52,0.55)"},
    {"id": "gripper",       "label": "Gripper Fingers", "score": 0.29, "x": 290, "y": 105, "w": 60, "h": 55,  "color": "rgba(56,189,248,0.45)"},
    {"id": "target_zone",   "label": "Target Zone",     "score": 0.17, "x": 390, "y": 185, "w": 75, "h": 50,  "color": "rgba(250,204,21,0.40)"},
    {"id": "table_edge",    "label": "Table Edge",      "score": 0.08, "x": 80,  "y": 215, "w": 420, "h": 12, "color": "rgba(163,230,53,0.35)"},
    {"id": "depth_shadow",  "label": "Depth Shadow",    "score": 0.05, "x": 195, "y": 210, "w": 110, "h": 20, "color": "rgba(168,85,247,0.30)"},
]

PROBE_RESULTS = [
    {"prop": "cube_position",           "acc": 0.94, "note": "strong spatial repr"},
    {"prop": "gripper_state",           "acc": 0.98, "note": "highest accuracy"},
    {"prop": "task_phase",              "acc": 0.87, "note": "good phase tracking"},
    {"prop": "cube_grasped",            "acc": 0.91, "note": "reliable grasp signal"},
    {"prop": "obstacle_present",        "acc": 0.73, "note": "weakest — needs work"},
    {"prop": "target_location",         "acc": 0.88, "note": "solid target encoding"},
    {"prop": "object_orientation",      "acc": 0.79, "note": "moderate orientation"},
    {"prop": "grasp_success_prediction","acc": 0.82, "note": "predictive signal"},
]

METRICS = {
    "saliency_concentration_score": 0.71,
    "probe_accuracy_mean":          round(sum(p["acc"] for p in PROBE_RESULTS) / len(PROBE_RESULTS), 3),
    "probe_accuracy_min":           min(p["acc"] for p in PROBE_RESULTS),
    "probe_accuracy_max":           max(p["acc"] for p in PROBE_RESULTS),
    "policy_transparency_index":    0.84,
    "blind_spots_identified":       1,
    "blind_spot_detail":            "obstacle_present (acc=0.73) — policy under-represents complex scene obstacles",
    "model":                        "GR00T-N1.6",
    "layers_probed":                12,
    "best_probe_layer":             8,
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _saliency_svg() -> str:
    rects = ""
    for r in SALIENCY_REGIONS:
        rects += (
            f'<rect x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" '
            f'fill="{r["color"]}" rx="4" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>'
            f'<text x="{r["x"] + r["w"]//2}" y="{r["y"] - 6}" '
            f'fill="#e2e8f0" font-size="9" text-anchor="middle" font-family="monospace">'
            f'{r["label"]} {r["score"]:.2f}</text>'
        )
    # Legend bar
    legend = ''
    for i, r in enumerate(SALIENCY_REGIONS):
        lx = 60 + i * 100
        legend += (
            f'<rect x="{lx}" y="290" width="14" height="14" fill="{r["color"]}" rx="2"/>'
            f'<text x="{lx+18}" y="302" fill="#94a3b8" font-size="9" font-family="monospace">{r["label"]}</text>'
        )
    return f"""
<svg viewBox="0 0 600 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px">
  <rect width="600" height="320" fill="#0f172a" rx="8"/>
  <!-- Scene background -->
  <rect x="60" y="60" width="480" height="200" fill="#1e293b" rx="6"/>
  <!-- Table -->
  <rect x="60" y="220" width="480" height="40" fill="#334155" rx="0"/>
  <!-- Robot arm (stylised) -->
  <line x1="180" y1="60" x2="295" y2="120" stroke="#64748b" stroke-width="6" stroke-linecap="round"/>
  <line x1="295" y1="120" x2="310" y2="155" stroke="#64748b" stroke-width="5" stroke-linecap="round"/>
  <!-- Gripper -->
  <rect x="293" y="105" width="8" height="40" fill="#475569" rx="2"/>
  <rect x="308" y="105" width="8" height="40" fill="#475569" rx="2"/>
  <!-- Cube -->
  <rect x="220" y="160" width="60" height="55" fill="#C74634" rx="4"/>
  <text x="250" y="192" fill="#fff" font-size="10" text-anchor="middle" font-family="monospace">CUBE</text>
  <!-- Target zone marker -->
  <rect x="395" y="190" width="65" height="10" fill="#38bdf8" rx="2" opacity="0.5"/>
  <text x="427" y="186" fill="#38bdf8" font-size="9" text-anchor="middle" font-family="monospace">TARGET</text>
  <!-- Saliency overlays -->
  {rects}
  <!-- Title -->
  <text x="300" y="22" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Saliency Map — Top-5 Salient Regions</text>
  <text x="300" y="38" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">GR00T-N1.6 · Gradient-weighted class activation</text>
  <!-- Legend -->
  {legend}
</svg>"""


def _probe_svg() -> str:
    bar_h = 26
    gap = 6
    total_h = len(PROBE_RESULTS) * (bar_h + gap) + 60
    bars = ""
    for i, p in enumerate(PROBE_RESULTS):
        y = 50 + i * (bar_h + gap)
        bar_w = int(p["acc"] * 400)
        color = "#C74634" if p["acc"] < 0.80 else ("#38bdf8" if p["acc"] >= 0.95 else "#34d399")
        bars += (
            f'<rect x="160" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>'
            f'<text x="155" y="{y + bar_h//2 + 5}" fill="#cbd5e1" font-size="10" text-anchor="end" font-family="monospace">{p["prop"]}</text>'
            f'<text x="{160 + bar_w + 6}" y="{y + bar_h//2 + 5}" fill="#e2e8f0" font-size="10" font-family="monospace">{p["acc"]:.2f}</text>'
        )
    # Threshold line at 0.80
    thresh_x = 160 + int(0.80 * 400)
    return f"""
<svg viewBox="0 0 620 {total_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:620px">
  <rect width="620" height="{total_h}" fill="#0f172a" rx="8"/>
  <text x="310" y="22" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Probing Classifier — Linear Probe Accuracy</text>
  <text x="310" y="38" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">GR00T-N1.6 Layer 8 Representations · 8 Object Properties</text>
  {bars}
  <!-- Threshold -->
  <line x1="{thresh_x}" y1="44" x2="{thresh_x}" y2="{total_h - 10}" stroke="#facc15" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="{thresh_x + 4}" y="{total_h - 12}" fill="#facc15" font-size="9" font-family="monospace">threshold 0.80</text>
  <!-- x-axis ticks -->
  {''.join(f'<text x="{160 + int(v*400)}" y="{total_h - 2}" fill="#475569" font-size="9" text-anchor="middle" font-family="monospace">{v:.1f}</text>' for v in [0.0, 0.25, 0.5, 0.75, 1.0])}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics_rows = "".join(
        f'<tr><td style="color:#94a3b8;padding:4px 12px">{k}</td>'
        f'<td style="color:#e2e8f0;padding:4px 12px">{v}</td></tr>'
        for k, v in METRICS.items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Policy Interpretability — Port 8348</title>
  <style>
    body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
    h2{{color:#38bdf8;font-size:1rem;margin:24px 0 8px}}
    .badge{{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:6px;
            padding:2px 10px;font-size:0.75rem;color:#94a3b8;margin-right:6px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:24px}}
    table{{border-collapse:collapse;width:100%}}
    tr:nth-child(even){{background:#0f172a}}
    .tag-red{{color:#C74634}} .tag-blue{{color:#38bdf8}} .tag-green{{color:#34d399}}
  </style>
</head>
<body>
  <h1>Policy Interpretability Dashboard</h1>
  <span class="badge">GR00T-N1.6</span>
  <span class="badge">Port 8348</span>
  <span class="badge">{ts}</span>

  <h2>SVG 1 — Saliency Map Overlay</h2>
  <div class="card">{_saliency_svg()}</div>

  <h2>SVG 2 — Probing Classifier Results</h2>
  <div class="card">{_probe_svg()}</div>

  <h2>Key Metrics</h2>
  <div class="card">
    <table>{metrics_rows}</table>
  </div>

  <h2>Interpretation Notes</h2>
  <div class="card">
    <p><span class="tag-red">Cube Surface (0.41)</span> — dominant driver; policy focuses heavily on cube surface texture and edges.</p>
    <p><span class="tag-blue">Gripper Fingers (0.29)</span> — second-most salient; fine motor control relies on fingertip proximity.</p>
    <p><span class="tag-green">Gripper State probe (0.98)</span> — highest linear probe accuracy across all properties.</p>
    <p><span class="tag-red">Obstacle Present probe (0.73)</span> — blind spot; intermediate representations weakly encode obstacle signals. Recommend augmenting training data with complex obstacle scenes.</p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Policy Interpretability",
        description="GR00T policy saliency maps and probing classifiers",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_dashboard_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_interpretability", "port": 8348}

    @app.get("/saliency")
    async def saliency():
        return {"regions": SALIENCY_REGIONS, "top_region": SALIENCY_REGIONS[0]["id"]}

    @app.get("/probes")
    async def probes():
        return {"results": PROBE_RESULTS, "metrics": METRICS}

    @app.get("/metrics")
    async def metrics():
        return METRICS

else:
    # Fallback stdlib server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8348)
    else:
        with socketserver.TCPServer(("", 8348), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8348 (stdlib fallback)")
            httpd.serve_forever()
