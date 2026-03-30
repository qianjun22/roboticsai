"""Inference Pipeline Monitor — port 8324

Monitors the complete inference pipeline from request receipt to action delivery.
Tracks per-stage latency, health, and optimization opportunities.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
import time
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

PIPELINE_STAGES = [
    {"name": "receive",          "base_ms": 0.3,   "color": "#38bdf8"},
    {"name": "parse",            "base_ms": 0.1,   "color": "#7dd3fc"},
    {"name": "auth",             "base_ms": 0.3,   "color": "#38bdf8"},
    {"name": "preprocess_image", "base_ms": 8.2,   "color": "#fb923c"},
    {"name": "tokenize",         "base_ms": 2.1,   "color": "#38bdf8"},
    {"name": "model_forward",    "base_ms": 180.0, "color": "#C74634"},
    {"name": "decode_action",    "base_ms": 3.4,   "color": "#38bdf8"},
    {"name": "postprocess",      "base_ms": 1.8,   "color": "#38bdf8"},
    {"name": "serialize",        "base_ms": 0.4,   "color": "#38bdf8"},
    {"name": "send",             "base_ms": 1.2,   "color": "#7dd3fc"},
]

TOTAL_P50 = 226.0
TOTAL_P99 = 267.0


def get_stage_stats():
    total = sum(s["base_ms"] for s in PIPELINE_STAGES)
    stages = []
    for s in PIPELINE_STAGES:
        pct = s["base_ms"] / total * 100
        stages.append({
            "name": s["name"],
            "p50_ms": round(s["base_ms"] + random.uniform(-0.05, 0.05) * s["base_ms"], 2),
            "p99_ms": round(s["base_ms"] * random.uniform(1.15, 1.25), 2),
            "pct": round(pct, 1),
            "color": s["color"],
            "health": "GREEN",
            "error_rate": round(random.uniform(0.0, 0.02), 4),
        })
    return stages, round(total, 2)


def get_7day_trend():
    """Per-stage p99 over 7 days."""
    days = [(datetime.now() - timedelta(days=6 - i)).strftime("%m/%d") for i in range(7)]
    trends = {}
    for s in PIPELINE_STAGES:
        trends[s["name"]] = [
            round(s["base_ms"] * (1 + 0.1 * math.sin(i * 0.9) + random.uniform(-0.03, 0.03)), 2)
            for i in range(7)
        ]
    return days, trends


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_pipeline_svg(stages, total_ms):
    """Horizontal segmented bar showing per-stage latency contribution."""
    W, H = 820, 180
    bar_h = 48
    bar_y = 60
    label_y = bar_y + bar_h + 22
    cumulative_line_y = bar_y - 16

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" ',
        'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        f'<text x="10" y="20" fill="#94a3b8" font-size="11">'
        f'End-to-End Pipeline  p50={TOTAL_P50}ms  p99={TOTAL_P99}ms  total_stages=10</text>',
    ]

    x = 10
    avail_w = W - 20
    cumulative = 0

    for s in stages:
        seg_w = max(4, s["pct"] / 100 * avail_w)
        color = s["color"]
        # segment rect
        svg_parts.append(
            f'<rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="2"/>'
        )
        # label inside if wide enough
        if seg_w > 28:
            svg_parts.append(
                f'<text x="{x + seg_w/2:.1f}" y="{bar_y + bar_h/2 + 4:.1f}" '
                f'fill="#0f172a" font-size="9" text-anchor="middle" font-weight="bold">'
                f'{s["p50_ms"]}ms</text>'
            )
        # cumulative tick
        cumulative += s["p50_ms"]
        svg_parts.append(
            f'<line x1="{x + seg_w:.1f}" y1="{bar_y - 5}" '
            f'x2="{x + seg_w:.1f}" y2="{bar_y}" stroke="#475569" stroke-width="1"/>'
        )
        # stage name below
        svg_parts.append(
            f'<text x="{x + seg_w/2:.1f}" y="{label_y}" fill="#94a3b8" '
            f'font-size="8" text-anchor="middle" transform="rotate(-30,{x + seg_w/2:.1f},{label_y})">'
            f'{s["name"]}</text>'
        )
        x += seg_w

    # cumulative bar caption
    svg_parts.append(
        f'<text x="{W//2}" y="{H - 8}" fill="#38bdf8" font-size="10" text-anchor="middle">'
        f'model_forward=79.6% of total  |  preprocess_image optimization target (-5ms)  |  '
        f'TensorRT would cut model_forward → 109ms</text>'
    )
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def build_health_trend_svg(days, trends):
    """7-day p99 trend lines per stage — spark-line grid."""
    W, H = 820, 260
    cols = 5
    rows = 2
    cw = W // cols
    ch = H // rows
    pad = 12

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        f'<text x="10" y="14" fill="#94a3b8" font-size="11">7-Day p99 Latency Trend per Stage</text>',
    ]

    stage_names = list(trends.keys())
    for idx, sname in enumerate(stage_names):
        col = idx % cols
        row = idx // cols
        cx = col * cw + pad
        cy = row * ch + 24
        cw2 = cw - pad * 2
        ch2 = ch - 36

        vals = trends[sname]
        mn, mx = min(vals), max(vals)
        span = mx - mn if mx != mn else 1

        color = next((s["color"] for s in PIPELINE_STAGES if s["name"] == sname), "#38bdf8")

        # background cell
        svg_parts.append(
            f'<rect x="{col * cw + 4}" y="{row * ch + 20}" '
            f'width="{cw - 8}" height="{ch - 24}" fill="#0f172a" rx="4"/>'
        )

        # sparkline
        pts = []
        for i, v in enumerate(vals):
            px = cx + i / (len(vals) - 1) * cw2
            py = cy + ch2 - (v - mn) / span * ch2
            pts.append(f"{px:.1f},{py:.1f}")
        svg_parts.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        )

        # label
        svg_parts.append(
            f'<text x="{col * cw + cw // 2}" y="{row * ch + 36}" '
            f'fill="{color}" font-size="9" text-anchor="middle">{sname}</text>'
        )
        svg_parts.append(
            f'<text x="{col * cw + cw // 2}" y="{row * ch + 46}" '
            f'fill="#64748b" font-size="8" text-anchor="middle">{vals[-1]}ms p99</text>'
        )

    svg_parts.append('</svg>')
    return ''.join(svg_parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html():
    stages, total_ms = get_stage_stats()
    days, trends = get_7day_trend()
    pipeline_svg = build_pipeline_svg(stages, total_ms)
    health_svg = build_health_trend_svg(days, trends)

    rows = ""
    for s in stages:
        health_badge = f'<span style="color:#22c55e;font-weight:bold">{s["health"]}</span>'
        rows += (
            f'<tr><td>{s["name"]}</td>'
            f'<td>{s["p50_ms"]}ms</td>'
            f'<td>{s["p99_ms"]}ms</td>'
            f'<td>{s["pct"]}%</td>'
            f'<td>{health_badge}</td>'
            f'<td>{s["error_rate"]*100:.2f}%</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Inference Pipeline Monitor — Port 8324</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',monospace; margin:0; padding:24px; }}
    h1   {{ color:#C74634; font-size:1.5rem; margin-bottom:4px; }}
    h2   {{ color:#38bdf8; font-size:1.1rem; margin:24px 0 8px; }}
    .badge {{ background:#1e293b; border:1px solid #334155; border-radius:6px;
              padding:12px 20px; display:inline-block; margin:6px; }}
    .metric-val {{ font-size:1.8rem; font-weight:bold; color:#38bdf8; }}
    .metric-lbl {{ font-size:0.75rem; color:#64748b; }}
    table {{ border-collapse:collapse; width:100%; background:#1e293b; border-radius:8px; overflow:hidden; margin-top:8px; }}
    th    {{ background:#0f172a; color:#C74634; padding:8px 12px; text-align:left; font-size:0.8rem; }}
    td    {{ padding:7px 12px; font-size:0.82rem; border-bottom:1px solid #1e293b; }}
    tr:hover td {{ background:#263348; }}
    .svg-wrap {{ margin:12px 0; border-radius:8px; overflow:hidden; }}
    .note {{ color:#94a3b8; font-size:0.8rem; margin-top:6px; }}
  </style>
</head>
<body>
  <h1>Inference Pipeline Monitor</h1>
  <p class="note">Port 8324 — OCI Robot Cloud — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

  <div>
    <div class="badge"><div class="metric-val">{TOTAL_P50}ms</div><div class="metric-lbl">p50 End-to-End</div></div>
    <div class="badge"><div class="metric-val">{TOTAL_P99}ms</div><div class="metric-lbl">p99 End-to-End</div></div>
    <div class="badge"><div class="metric-val">79.6%</div><div class="metric-lbl">model_forward share</div></div>
    <div class="badge"><div class="metric-val" style="color:#22c55e">99.8%</div><div class="metric-lbl">SLA Compliance</div></div>
    <div class="badge"><div class="metric-val">10</div><div class="metric-lbl">Pipeline Stages</div></div>
    <div class="badge"><div class="metric-val" style="color:#fb923c">-5ms</div><div class="metric-lbl">preprocess opt target</div></div>
  </div>

  <h2>End-to-End Pipeline Stage Timing</h2>
  <div class="svg-wrap">{pipeline_svg}</div>

  <h2>7-Day p99 Latency Trend per Stage</h2>
  <div class="svg-wrap">{health_svg}</div>

  <h2>Stage Breakdown Table</h2>
  <table>
    <tr><th>Stage</th><th>p50</th><th>p99</th><th>% of Total</th><th>Health</th><th>Error Rate</th></tr>
    {rows}
  </table>

  <p class="note" style="margin-top:16px">
    Optimization: TensorRT would cut model_forward 180ms → 109ms (−39%), total latency → 155ms.<br>
    preprocess_image GPU kernel fusion saves 5ms (3.6% → 1.4%).
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Inference Pipeline Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": 8324, "service": "inference_pipeline_monitor"}

    @app.get("/metrics")
    def metrics():
        stages, total_ms = get_stage_stats()
        return {
            "total_p50_ms": TOTAL_P50,
            "total_p99_ms": TOTAL_P99,
            "total_stages": len(stages),
            "model_forward_pct": 79.6,
            "sla_compliance_pct": 99.8,
            "stages": stages,
            "tensorrt_projected_p50_ms": 155.0,
        }

    @app.get("/stages/{stage_name}")
    def stage_detail(stage_name: str):
        stages, _ = get_stage_stats()
        for s in stages:
            if s["name"] == stage_name:
                days, trends = get_7day_trend()
                return {"stage": s, "7day_p99_trend": trends.get(stage_name, [])}
        return {"error": f"stage '{stage_name}' not found"}

else:
    # stdlib fallback
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8324)
    else:
        print("FastAPI not found — using stdlib http.server on port 8324")
        with socketserver.TCPServer(("", 8324), Handler) as srv:
            srv.serve_forever()
