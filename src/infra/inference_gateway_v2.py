"""inference_gateway_v2.py — Enhanced inference API gateway with authentication, routing, and observability.
Port: 8315
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
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

GATEWAY_OVERHEAD_MS = 1.2
AUTH_LATENCY_MS = 0.3
ROUTING_LATENCY_MS = 0.4
TLS_LATENCY_MS = 0.5

PEAK_HOUR_UTC = 14
PEAK_REQS_PER_HR = 847
P99_MS = 267
SLA_P99_MS = 300
SUCCESS_RATE_PCT = 99.72
REJECT_RATE_PCT = 0.28

# 7-day × 24-hour request count mock data (Mon=0 .. Sun=6, hour 0-23)
random.seed(42)


def _mock_volume(day: int, hour: int) -> int:
    base = 300
    hour_curve = math.exp(-((hour - PEAK_HOUR_UTC) ** 2) / 30)
    weekend_penalty = 0.6 if day >= 5 else 1.0
    noise = random.uniform(0.85, 1.15)
    return max(10, int(base * hour_curve * weekend_penalty * noise))


def _mock_latency_p(day: int, hour: int, pct: str) -> float:
    vol = _mock_volume(day, hour)
    base = {"p50": 42, "p90": 120, "p99": 230}[pct]
    load_factor = 1 + (vol / PEAK_REQS_PER_HR) * 0.4
    noise = random.uniform(0.9, 1.1)
    return round(base * load_factor * noise, 1)


HEATMAP_DATA = [
    {"day": d, "hour": h, "volume": _mock_volume(d, h),
     "p50": _mock_latency_p(d, h, "p50"),
     "p90": _mock_latency_p(d, h, "p90"),
     "p99": _mock_latency_p(d, h, "p99")}
    for d in range(7) for h in range(24)
]

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------------------------------------------------------------------
# SVG 1: Request journey flowchart
# ---------------------------------------------------------------------------

def build_journey_svg() -> str:
    W, H = 900, 180
    stages = [
        {"label": "Client",       "lat": "",       "color": "#475569"},
        {"label": "API Gateway",  "lat": "1.2ms",  "color": "#38bdf8"},
        {"label": "Auth Check",   "lat": "0.3ms",  "color": "#a78bfa"},
        {"label": "Rate Limiter", "lat": "0.0ms",  "color": "#fb923c"},
        {"label": "Model Router", "lat": "0.4ms",  "color": "#4ade80"},
        {"label": "TLS Wrap",     "lat": "0.5ms",  "color": "#facc15"},
        {"label": "Backend Pool", "lat": "",       "color": "#C74634"},
        {"label": "Response",     "lat": "",       "color": "#64748b"},
    ]
    n = len(stages)
    box_w, box_h = 90, 44
    gap = (W - 40 - n * box_w) // (n - 1)
    cy = H // 2

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">',
        f'<text x="{W//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Request Journey — Gateway Overhead {GATEWAY_OVERHEAD_MS}ms Total</text>',
    ]

    for i, stage in enumerate(stages):
        x = 20 + i * (box_w + gap)
        # Arrow (except before first box)
        if i > 0:
            ax = x - gap
            svg_parts.append(f'<line x1="{ax + box_w}" y1="{cy}" x2="{x - 4}" y2="{cy}" stroke="#475569" stroke-width="2" marker-end="url(#arr)"/>')
            if stage["lat"]:
                mid_x = ax + box_w + gap // 2
                svg_parts.append(f'<text x="{mid_x}" y="{cy - 8}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{stage["lat"]}</text>')

        # Box
        svg_parts.append(f'<rect x="{x}" y="{cy - box_h//2}" width="{box_w}" height="{box_h}" rx="6" fill="{stage["color"]}" opacity="0.85"/>')
        # Label (split if long)
        label_parts = stage["label"].split(" ", 1)
        if len(label_parts) == 2:
            svg_parts.append(f'<text x="{x + box_w//2}" y="{cy - 4}" text-anchor="middle" fill="#0f172a" font-size="10" font-family="monospace" font-weight="bold">{label_parts[0]}</text>')
            svg_parts.append(f'<text x="{x + box_w//2}" y="{cy + 10}" text-anchor="middle" fill="#0f172a" font-size="10" font-family="monospace" font-weight="bold">{label_parts[1]}</text>')
        else:
            svg_parts.append(f'<text x="{x + box_w//2}" y="{cy + 5}" text-anchor="middle" fill="#0f172a" font-size="10" font-family="monospace" font-weight="bold">{stage["label"]}</text>')

    # Arrow marker def
    svg_parts.insert(1, '<defs><marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#475569"/></marker></defs>')

    # Annotation box
    note_x, note_y = W - 220, H - 45
    svg_parts.append(f'<rect x="{note_x}" y="{note_y}" width="200" height="30" rx="4" fill="#0f172a" stroke="#C74634" stroke-width="1"/>')
    svg_parts.append(f'<text x="{note_x + 100}" y="{note_y + 12}" text-anchor="middle" fill="#C74634" font-size="9" font-family="monospace">GW overhead: auth(0.3) + route(0.4) + TLS(0.5)</text>')
    svg_parts.append(f'<text x="{note_x + 100}" y="{note_y + 24}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">= {GATEWAY_OVERHEAD_MS}ms · 99.72% success rate</text>')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ---------------------------------------------------------------------------
# SVG 2: Gateway throughput heatmap (7 days × 24 hours, colored by p99 latency)
# ---------------------------------------------------------------------------

def build_heatmap_svg() -> str:
    W, H = 900, 240
    cell_w = 30
    cell_h = 24
    pad_left = 50
    pad_top = 40
    pad_bottom = 30

    # p99 latency color scale: green (low) → yellow → red (high)
    def latency_color(p99: float) -> str:
        # 40ms = green, 300ms = red
        t = min(1.0, max(0.0, (p99 - 40) / 260))
        r = int(255 * t)
        g = int(200 * (1 - t))
        b = 50
        return f"rgb({r},{g},{b})"

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">',
        f'<text x="{W//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Gateway Throughput &amp; p99 Latency Heatmap — 7 days × 24 hours</text>',
    ]

    # Hour labels (every 4h)
    for h in range(0, 24, 4):
        x = pad_left + h * cell_w + cell_w // 2
        svg_parts.append(f'<text x="{x}" y="{pad_top - 6}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{h:02d}h</text>')

    # Day labels
    for d, dname in enumerate(DAY_NAMES):
        y = pad_top + d * cell_h + cell_h // 2 + 4
        svg_parts.append(f'<text x="{pad_left - 6}" y="{y}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{dname}</text>')

    # Cells
    for entry in HEATMAP_DATA:
        d, h = entry["day"], entry["hour"]
        x = pad_left + h * cell_w
        y = pad_top + d * cell_h
        color = latency_color(entry["p99"])
        opacity = 0.4 + 0.6 * (entry["volume"] / PEAK_REQS_PER_HR)
        svg_parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 1}" height="{cell_h - 1}" fill="{color}" opacity="{opacity:.2f}" rx="1">')
        svg_parts.append(f'  <title>Day {DAY_NAMES[d]} {h:02d}h — vol:{entry["volume"]} p50:{entry["p50"]}ms p90:{entry["p90"]}ms p99:{entry["p99"]}ms</title>')
        svg_parts.append('</rect>')

    # Peak hour annotation
    peak_x = pad_left + PEAK_HOUR_UTC * cell_w
    svg_parts.append(f'<line x1="{peak_x + cell_w//2}" y1="{pad_top - 2}" x2="{peak_x + cell_w//2}" y2="{pad_top + 7 * cell_h + 2}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="3,2"/>')
    svg_parts.append(f'<text x="{peak_x + cell_w//2}" y="{pad_top + 7 * cell_h + 18}" text-anchor="middle" fill="#C74634" font-size="9" font-family="monospace">Peak {PEAK_HOUR_UTC}h UTC ({PEAK_REQS_PER_HR} req/hr)</text>')

    # SLA breach annotation (p99 > 300ms cells would be bright red — none in mock, annotate 267ms)
    legend_x = W - 200
    legend_y = pad_top + 7 * cell_h - 20
    gradient_steps = 6
    for i in range(gradient_steps):
        t = i / (gradient_steps - 1)
        p99_val = 40 + t * 260
        cx = legend_x + i * 22
        color = latency_color(p99_val)
        svg_parts.append(f'<rect x="{cx}" y="{legend_y}" width="22" height="12" fill="{color}"/>')
    svg_parts.append(f'<text x="{legend_x}" y="{legend_y - 4}" fill="#94a3b8" font-size="8" font-family="monospace">p99: low</text>')
    svg_parts.append(f'<text x="{legend_x + gradient_steps * 22 - 20}" y="{legend_y - 4}" fill="#94a3b8" font-size="8" font-family="monospace">high</text>')
    svg_parts.append(f'<text x="{legend_x + gradient_steps * 11}" y="{legend_y + 24}" text-anchor="middle" fill="#4ade80" font-size="8" font-family="monospace">p99 max={P99_MS}ms &lt; {SLA_P99_MS}ms SLA</text>')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    journey_svg = build_journey_svg()
    heatmap_svg = build_heatmap_svg()

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <title>Inference Gateway v2 | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 18px; color: #f8fafc; }}
    .badge {{ background: #C74634; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 12px; }}
    .port-badge {{ background: #334155; color: #94a3b8; padding: 2px 10px; border-radius: 12px; font-size: 12px; }}
    main {{ padding: 24px 32px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 24px; min-width: 160px; }}
    .kpi .label {{ font-size: 11px; color: #94a3b8; margin-bottom: 6px; }}
    .kpi .val {{ font-size: 24px; font-weight: bold; }}
    .kpi .sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .chart-section h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 14px; }}
    .stage-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .stage-table thead tr {{ background: #334155; }}
    .stage-table th {{ padding: 8px 12px; color: #94a3b8; text-align: left; font-weight: normal; }}
    .stage-table tbody tr {{ border-bottom: 1px solid #0f172a; }}
    .stage-table td {{ padding: 8px 12px; }}
    footer {{ text-align: center; padding: 16px; color: #475569; font-size: 11px; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Inference Gateway v2</h1>
      <div style='font-size:12px;color:#94a3b8;margin-top:4px'>Enhanced API Gateway — Auth · Routing · Observability</div>
    </div>
    <div style='margin-left:auto;display:flex;gap:8px;align-items:center'>
      <span class='badge'>Port 8315</span>
      <span class='port-badge'>v2.4.1</span>
    </div>
  </header>
  <main>
    <div class='kpi-row'>
      <div class='kpi'><div class='label'>GW Overhead</div><div class='val' style='color:#38bdf8'>{GATEWAY_OVERHEAD_MS}ms</div><div class='sub'>auth+route+TLS</div></div>
      <div class='kpi'><div class='label'>Peak Throughput</div><div class='val' style='color:#4ade80'>{PEAK_REQS_PER_HR}</div><div class='sub'>req/hr @ {PEAK_HOUR_UTC}h UTC</div></div>
      <div class='kpi'><div class='label'>p99 Latency</div><div class='val' style='color:#facc15'>{P99_MS}ms</div><div class='sub'>SLA: &lt;{SLA_P99_MS}ms</div></div>
      <div class='kpi'><div class='label'>Success Rate</div><div class='val' style='color:#4ade80'>{SUCCESS_RATE_PCT}%</div><div class='sub'>{REJECT_RATE_PCT}% rate-limited</div></div>
      <div class='kpi'><div class='label'>Auth Latency</div><div class='val' style='color:#a78bfa'>{AUTH_LATENCY_MS}ms</div><div class='sub'>JWT verify (cached)</div></div>
      <div class='kpi'><div class='label'>SLA Status</div><div class='val' style='color:#4ade80'>PASS</div><div class='sub'>p99 {P99_MS} &lt; {SLA_P99_MS}ms</div></div>
    </div>

    <div class='chart-section'>
      <h2>SVG 1 — Request Journey Flowchart (latency per stage)</h2>
      {journey_svg}
    </div>

    <div class='chart-section'>
      <h2>SVG 2 — Throughput &amp; p99 Latency Heatmap (7 days × 24 hours, hover for details)</h2>
      {heatmap_svg}
    </div>

    <div class='chart-section'>
      <h2>Gateway Stage Breakdown</h2>
      <table class='stage-table'>
        <thead><tr><th>Stage</th><th>Latency</th><th>Description</th><th>Failure Mode</th></tr></thead>
        <tbody>
          <tr><td style='color:#a78bfa'>Auth Check</td><td style='color:#38bdf8'>{AUTH_LATENCY_MS}ms</td><td style='color:#94a3b8'>JWT validate + RBAC lookup (Redis-cached, TTL 60s)</td><td style='color:#f87171'>401 Unauthorized → client retry</td></tr>
          <tr><td style='color:#fb923c'>Rate Limiter</td><td style='color:#38bdf8'>~0ms</td><td style='color:#94a3b8'>Token bucket per API key (1000 req/hr default)</td><td style='color:#f87171'>429 Too Many Requests (0.28% of traffic)</td></tr>
          <tr><td style='color:#4ade80'>Model Router</td><td style='color:#38bdf8'>{ROUTING_LATENCY_MS}ms</td><td style='color:#94a3b8'>Consistent hash on model_id → backend shard</td><td style='color:#f87171'>503 if shard unhealthy → failover</td></tr>
          <tr><td style='color:#facc15'>TLS Wrap</td><td style='color:#38bdf8'>{TLS_LATENCY_MS}ms</td><td style='color:#94a3b8'>mTLS to backend pool (session reuse, ~0.1ms steady)</td><td style='color:#f87171'>TLS handshake timeout 2s</td></tr>
          <tr><td style='color:#38bdf8'>Backend Pool</td><td style='color:#38bdf8'>~220ms</td><td style='color:#94a3b8'>GR00T inference (GPU, A100 40GB, batch size 1)</td><td style='color:#f87171'>504 timeout at 5s → DLQ</td></tr>
        </tbody>
      </table>
    </div>
  </main>
  <footer>OCI Robot Cloud · Inference Gateway v2 · Port 8315 · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Inference Gateway v2", version="2.4.1")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "inference_gateway_v2", "port": 8315, "version": "2.4.1"}

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "gateway_overhead_ms": GATEWAY_OVERHEAD_MS,
            "auth_latency_ms": AUTH_LATENCY_MS,
            "routing_latency_ms": ROUTING_LATENCY_MS,
            "tls_latency_ms": TLS_LATENCY_MS,
            "peak_hour_utc": PEAK_HOUR_UTC,
            "peak_reqs_per_hr": PEAK_REQS_PER_HR,
            "p99_ms": P99_MS,
            "sla_p99_ms": SLA_P99_MS,
            "success_rate_pct": SUCCESS_RATE_PCT,
            "reject_rate_pct": REJECT_RATE_PCT,
            "sla_status": "PASS" if P99_MS < SLA_P99_MS else "BREACH",
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8315)
    else:
        print("[inference_gateway_v2] FastAPI not found — falling back to stdlib HTTP server on port 8315")
        HTTPServer(("0.0.0.0", 8315), Handler).serve_forever()
