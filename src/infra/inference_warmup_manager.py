"""Inference Warmup Manager — FastAPI service on port 8227.

Manages model warmup strategies to minimise cold-start latency in production.
Provides SVG visualisations of per-strategy latency and 24h warmup timeline.
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
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Mock data ─────────────────────────────────────────────────────────────────
random.seed(7)

# First-request latency (ms) by strategy
STRATEGIES = [
    {"name": "cold_start",         "p50": 1840, "p99": 3120, "color": "#C74634"},
    {"name": "partial_warmup",     "p50":  680, "p99": 1240, "color": "#f59e0b"},
    {"name": "full_warmup",        "p50":  226, "p99":  410, "color": "#38bdf8"},
    {"name": "predictive_preload", "p50":  228, "p99":  395, "color": "#22c55e"},
]

COLD_START_REDUCTION = 1.0 - (228 / 1840)  # 87.6%
WARMUP_GPU_IDLE_PCT  = 0.043               # 4.3% GPU time spent on warmup
SLA_COMPLIANCE_RATE  = 0.9983              # <500ms SLA
PREDICTIVE_COVERAGE  = 0.94               # 94% of requests covered by predictive preload

# 24h timeline: 3 GPU nodes, warmup events
# Each event: {node, start_h, dur_h, kind}
# kind: warmup / idle_cool / predictive
random.seed(99)
NODES = ["gpu-node-1", "gpu-node-2", "gpu-node-3"]

TIMELINE_EVENTS = [
    # Daily 3AM re-warmup
    {"node": "gpu-node-1", "start_h": 3.0,  "dur_h": 0.08, "kind": "warmup",     "lat_ms": 226},
    {"node": "gpu-node-2", "start_h": 3.1,  "dur_h": 0.08, "kind": "warmup",     "lat_ms": 226},
    {"node": "gpu-node-3", "start_h": 3.2,  "dur_h": 0.08, "kind": "warmup",     "lat_ms": 231},
    # Idle cooling windows (overnight)
    {"node": "gpu-node-1", "start_h": 1.0,  "dur_h": 1.8,  "kind": "idle_cool",  "lat_ms": None},
    {"node": "gpu-node-2", "start_h": 0.5,  "dur_h": 2.2,  "kind": "idle_cool",  "lat_ms": None},
    {"node": "gpu-node-3", "start_h": 0.8,  "dur_h": 1.9,  "kind": "idle_cool",  "lat_ms": None},
    # Predictive preload triggers (peak hours)
    {"node": "gpu-node-1", "start_h": 8.9,  "dur_h": 0.05, "kind": "predictive", "lat_ms": 228},
    {"node": "gpu-node-2", "start_h": 8.95, "dur_h": 0.05, "kind": "predictive", "lat_ms": 228},
    {"node": "gpu-node-3", "start_h": 13.9, "dur_h": 0.05, "kind": "predictive", "lat_ms": 228},
    {"node": "gpu-node-1", "start_h": 17.9, "dur_h": 0.05, "kind": "predictive", "lat_ms": 228},
    {"node": "gpu-node-2", "start_h": 17.95,"dur_h": 0.05, "kind": "predictive", "lat_ms": 228},
    # Mid-day re-warm after scale-up
    {"node": "gpu-node-3", "start_h": 10.0, "dur_h": 0.06, "kind": "warmup",     "lat_ms": 229},
]


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _bar_chart_svg(strategies, width=560, height=320):
    """Side-by-side p50/p99 bars for each warmup strategy."""
    pad_l, pad_r, pad_t, pad_b = 62, 20, 28, 52
    pw = width - pad_l - pad_r
    ph = height - pad_t - pad_b

    max_val = max(s["p99"] for s in strategies) * 1.12
    n = len(strategies)
    group_w = pw / n
    bar_w = group_w * 0.32

    def ty(v): return pad_t + ph - (v / max_val) * ph

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for gi in range(0, 6):
        gy = pad_t + ph * (1 - gi / 5)
        val = int(max_val * gi / 5)
        lines.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+pw}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{gy+4:.1f}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{val}</text>')

    for i, s in enumerate(strategies):
        gx = pad_l + i * group_w + group_w * 0.12
        # p50 bar
        p50h = (s["p50"] / max_val) * ph
        lines.append(f'<rect x="{gx:.1f}" y="{pad_t+ph-p50h:.1f}" width="{bar_w:.1f}" height="{p50h:.1f}" fill="{s["color"]}" fill-opacity="0.85" rx="2"/>')
        lines.append(f'<text x="{gx+bar_w/2:.1f}" y="{pad_t+ph-p50h-4:.1f}" fill="{s["color"]}" font-size="9" text-anchor="middle" font-family="monospace">{s["p50"]}</text>')
        # p99 bar
        p99h = (s["p99"] / max_val) * ph
        gx2 = gx + bar_w + 3
        lines.append(f'<rect x="{gx2:.1f}" y="{pad_t+ph-p99h:.1f}" width="{bar_w:.1f}" height="{p99h:.1f}" fill="{s["color"]}" fill-opacity="0.40" rx="2"/>')
        lines.append(f'<text x="{gx2+bar_w/2:.1f}" y="{pad_t+ph-p99h-4:.1f}" fill="{s["color"]}" font-size="9" text-anchor="middle" font-family="monospace">{s["p99"]}</text>')
        # X label
        lx = gx + bar_w + 1.5
        label = s["name"].replace("_", "\n")
        lines.append(f'<text x="{lx:.1f}" y="{pad_t+ph+14}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{s["name"].replace("_"," ")}</text>')

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ph}" x2="{pad_l+pw}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="12" y="{pad_t+ph//2}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace" transform="rotate(-90 12 {pad_t+ph//2})">Latency (ms)</text>')
    lines.append(f'<text x="{width//2}" y="17" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle" font-family="monospace">First-Request Latency by Warmup Strategy</text>')

    # Legend
    lines.append(f'<rect x="{pad_l}" y="{height-18}" width="10" height="8" fill="#94a3b8" fill-opacity="0.85" rx="1"/>')
    lines.append(f'<text x="{pad_l+13}" y="{height-11}" fill="#94a3b8" font-size="9" font-family="monospace">p50</text>')
    lines.append(f'<rect x="{pad_l+38}" y="{height-18}" width="10" height="8" fill="#94a3b8" fill-opacity="0.40" rx="1"/>')
    lines.append(f'<text x="{pad_l+51}" y="{height-11}" fill="#94a3b8" font-size="9" font-family="monospace">p99</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def _timeline_svg(events, nodes, width=660, height=220):
    """24h horizontal bar timeline per GPU node."""
    pad_l, pad_r, pad_t, pad_b = 100, 20, 28, 36
    pw = width - pad_l - pad_r
    ph = height - pad_t - pad_b

    n_nodes = len(nodes)
    row_h = ph / n_nodes
    bar_h = row_h * 0.5

    KIND_COLORS = {
        "warmup":     "#38bdf8",
        "idle_cool":  "#334155",
        "predictive": "#22c55e",
    }

    def tx(h): return pad_l + (h / 24.0) * pw
    def ty_row(i): return pad_t + i * row_h + row_h * 0.25

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">')

    # Background rows
    for i, node in enumerate(nodes):
        ry = pad_t + i * row_h
        fill = "#0f172a" if i % 2 == 0 else "#162032"
        lines.append(f'<rect x="{pad_l}" y="{ry:.1f}" width="{pw}" height="{row_h:.1f}" fill="{fill}"/>')
        lines.append(f'<text x="{pad_l-6}" y="{ry+row_h/2+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end" font-family="monospace">{node}</text>')

    # Hour grid
    for h in range(0, 25, 4):
        gx = tx(h)
        lines.append(f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t+ph}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{gx:.1f}" y="{pad_t+ph+14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">{h:02d}:00</text>')

    # Events
    for ev in events:
        ni = nodes.index(ev["node"])
        ex = tx(ev["start_h"])
        ew = max(4, (ev["dur_h"] / 24.0) * pw)
        ey = ty_row(ni)
        col = KIND_COLORS[ev["kind"]]
        lines.append(f'<rect x="{ex:.1f}" y="{ey:.1f}" width="{ew:.1f}" height="{bar_h:.1f}" fill="{col}" fill-opacity="0.9" rx="2"/>')
        # Annotate latency
        if ev["lat_ms"] is not None and ew > 20:
            lines.append(f'<text x="{ex+ew/2:.1f}" y="{ey+bar_h/2+4:.1f}" fill="#0f172a" font-size="8" text-anchor="middle" font-family="monospace" font-weight="bold">{ev["lat_ms"]}ms</text>')

    # Title
    lines.append(f'<text x="{width//2}" y="17" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle" font-family="monospace">24h Warmup Event Timeline — 3 GPU Nodes</text>')

    # Legend
    lx = pad_l
    for label, col in [("warmup", "#38bdf8"), ("idle_cool", "#334155"), ("predictive", "#22c55e")]:
        lines.append(f'<rect x="{lx}" y="{height-16}" width="10" height="8" fill="{col}" rx="1"/>')
        lines.append(f'<text x="{lx+13}" y="{height-9}" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')
        lx += 90
    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML dashboard ────────────────────────────────────────────────────────────

def build_html():
    bar_chart = _bar_chart_svg(STRATEGIES)
    timeline  = _timeline_svg(TIMELINE_EVENTS, NODES)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inference Warmup Manager — Port 8227</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace; min-height: 100vh; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 1.3rem; color: #f8fafc; }}
    header span {{ background: #C74634; color: #fff; font-size: 0.7rem; padding: 2px 8px;
                   border-radius: 4px; letter-spacing: 1px; }}
    .metrics {{ display: flex; gap: 16px; padding: 24px 32px 0; flex-wrap: wrap; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 16px 20px; min-width: 160px; flex: 1; }}
    .card .label {{ font-size: 0.72rem; color: #64748b; text-transform: uppercase;
                    letter-spacing: 1px; margin-bottom: 6px; }}
    .card .value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
    .card .sub {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
    .charts {{ display: flex; flex-wrap: wrap; gap: 24px; padding: 24px 32px; }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                  padding: 16px; flex: 1; min-width: 300px; }}
    .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;
                     text-transform: uppercase; letter-spacing: 1px; }}
    .strat-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 8px; }}
    .strat-table th {{ color: #64748b; font-weight: 600; padding: 6px 10px; text-align: left;
                        border-bottom: 1px solid #334155; }}
    .strat-table td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    footer {{ text-align: center; color: #334155; font-size: 0.7rem; padding: 16px;
              border-top: 1px solid #1e293b; margin-top: 8px; }}
  </style>
</head>
<body>
<header>
  <h1>Inference Warmup Manager</h1>
  <span>PORT 8227</span>
  <span style="background:#334155">COLD-START ELIMINATION</span>
</header>

<div class="metrics">
  <div class="card">
    <div class="label">Cold-Start Reduction</div>
    <div class="value" style="color:#22c55e">{COLD_START_REDUCTION*100:.1f}%</div>
    <div class="sub">1840ms → 228ms (predictive)</div>
  </div>
  <div class="card">
    <div class="label">GPU Idle (Warmup)</div>
    <div class="value" style="color:#f59e0b">{WARMUP_GPU_IDLE_PCT*100:.1f}%</div>
    <div class="sub">of total GPU-hours</div>
  </div>
  <div class="card">
    <div class="label">SLA Compliance</div>
    <div class="value">{SLA_COMPLIANCE_RATE*100:.2f}%</div>
    <div class="sub">&lt;500ms SLA target</div>
  </div>
  <div class="card">
    <div class="label">Predictive Coverage</div>
    <div class="value" style="color:#38bdf8">{PREDICTIVE_COVERAGE*100:.0f}%</div>
    <div class="sub">requests pre-warmed</div>
  </div>
  <div class="card">
    <div class="label">Best p50 Latency</div>
    <div class="value" style="color:#22c55e">226ms</div>
    <div class="sub">full_warmup strategy</div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h2>First-Request Latency — p50 vs p99</h2>
    {bar_chart}
    <table class="strat-table" style="margin-top:12px">
      <tr><th>Strategy</th><th>p50 (ms)</th><th>p99 (ms)</th><th>Notes</th></tr>
      {''.join(f"<tr><td style='color:{s['color']}'>{s['name']}</td><td>{s['p50']}</td><td>{s['p99']}</td><td>{'baseline' if s['name']=='cold_start' else '94% coverage' if s['name']=='predictive_preload' else ''}</td></tr>" for s in STRATEGIES)}
    </table>
  </div>
  <div class="chart-box">
    <h2>24h Warmup Timeline — GPU Nodes</h2>
    {timeline}
    <p style="font-size:0.78rem;color:#64748b;margin-top:10px">
      3AM daily re-warmup ensures models stay hot overnight.
      Predictive triggers fire 5 min before peak traffic windows (9AM, 2PM, 6PM).
    </p>
  </div>
</div>

<footer>OCI Robot Cloud · Inference Warmup Manager · port 8227 · GR00T N1.6 production</footer>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Inference Warmup Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/metrics")
    async def metrics():
        return {
            "cold_start_reduction_pct": round(COLD_START_REDUCTION * 100, 2),
            "warmup_gpu_idle_pct": round(WARMUP_GPU_IDLE_PCT * 100, 2),
            "sla_compliance_rate": SLA_COMPLIANCE_RATE,
            "predictive_coverage": PREDICTIVE_COVERAGE,
            "strategies": STRATEGIES,
        }

    @app.get("/strategies")
    async def strategies():
        return {"strategies": STRATEGIES}

    @app.get("/timeline")
    async def timeline():
        return {"events": TIMELINE_EVENTS, "nodes": NODES}

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8227, "service": "inference_warmup_manager"}


# ── Stdlib fallback ───────────────────────────────────────────────────────────

class _FallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = build_html().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8227)
    else:
        print("[inference_warmup_manager] FastAPI not available — using stdlib HTTP on port 8227")
        HTTPServer(("0.0.0.0", 8227), _FallbackHandler).serve_forever()
