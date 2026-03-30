"""Inference Batching Optimizer — OCI Robot Cloud (port 8243)

Optimizes dynamic batching strategy for GR00T inference to maximize throughput
while respecting p99 < 300ms SLA.
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
# Mock data — calibrated to stated spec
# ---------------------------------------------------------------------------

random.seed(7)

BATCH_SIZES = [1, 2, 4, 8, 16, 32]

# A100 80GB throughput (req/hr) and p99 latency (ms)
A100_80 = {
    1:  {"throughput": 520,  "p99": 68},
    2:  {"throughput": 940,  "p99": 112},
    4:  {"throughput": 1520, "p99": 178},
    8:  {"throughput": 1847, "p99": 267},   # optimal point
    16: {"throughput": 2150, "p99": 412},
    32: {"throughput": 2260, "p99": 780},
}

# A100 40GB — ~2.4x lower throughput at batch=16 means roughly 40-50% of 80GB values
A100_40 = {
    1:  {"throughput": 310,  "p99": 82},
    2:  {"throughput": 570,  "p99": 138},
    4:  {"throughput": 890,  "p99": 221},
    8:  {"throughput": 1120, "p99": 310},
    16: {"throughput": 895,  "p99": 540},   # memory pressure
    32: {"throughput": 680,  "p99": 1100},
}

# 24h queue simulation — 15-min buckets (96 buckets)
_HOURS = [i * 15 / 60 for i in range(96)]   # 0.0 .. 23.75

def _demand(h: float) -> float:
    """Simulate request demand: two peaks at 9h and 15h."""
    base  = 400
    peak1 = 900 * math.exp(-0.5 * ((h - 9)  / 1.5) ** 2)
    peak2 = 700 * math.exp(-0.5 * ((h - 15) / 1.8) ** 2)
    noise = random.uniform(-30, 30)
    return max(50, base + peak1 + peak2 + noise)

QUEUE_DATA = []
for h in _HOURS:
    demand = _demand(h)
    static_tp  = min(demand, 1520)      # static batch=4 capped at 1520 req/hr
    dynamic_tp = min(demand, 1847)      # dynamic up to batch=8 optimal
    queue_depth_static  = max(0, (demand - static_tp)  / 60 * 5)
    queue_depth_dynamic = max(0, (demand - dynamic_tp) / 60 * 5)
    QUEUE_DATA.append({
        "hour":          h,
        "demand":        round(demand, 1),
        "static_tp":     round(static_tp, 1),
        "dynamic_tp":    round(dynamic_tp, 1),
        "queue_static":  round(queue_depth_static, 2),
        "queue_dynamic": round(queue_depth_dynamic, 2),
    })

KEY_METRICS = {
    "optimal_batch_size":           8,
    "optimal_throughput_req_hr":    1847,
    "optimal_p99_ms":               267,
    "sla_boundary_ms":              300,
    "dynamic_vs_static_gain_pct":   23,
    "a100_80gb_vs_40gb_ratio":      2.4,
    "sla_compliant_batch_range":    "1–8 (A100 80GB)  /  1–4 (A100 40GB)",
    "max_sustainable_throughput":   1847,
}

# ---------------------------------------------------------------------------
# SVG 1 — Throughput vs Latency tradeoff
# ---------------------------------------------------------------------------

def build_tradeoff_svg() -> str:
    W, H    = 640, 380
    PAD_L   = 70
    PAD_R   = 40
    PAD_T   = 40
    PAD_B   = 60
    cw      = W - PAD_L - PAD_R
    ch      = H - PAD_T - PAD_B

    max_tp  = 2400
    max_lat = 1200
    SLA_LAT = 300

    def px(tp):  return PAD_L + (tp / max_tp) * cw
    def py(lat): return PAD_T + ch - (lat / max_lat) * ch

    # SLA boundary horizontal line
    sla_y = py(SLA_LAT)
    sla_line = (
        f'<line x1="{PAD_L}" y1="{sla_y:.1f}" x2="{W - PAD_R}" y2="{sla_y:.1f}" '
        f'stroke="#f87171" stroke-width="1.5" stroke-dasharray="8 4"/>'
        f'<text x="{W - PAD_R - 4}" y="{sla_y - 6:.1f}" text-anchor="end" '
        f'fill="#f87171" font-size="11" font-family="monospace">p99 = 300ms SLA</text>'
    )

    # SLA-compliant shaded region (below line)
    shade = (
        f'<rect x="{PAD_L}" y="{sla_y:.1f}" width="{cw}" height="{ch - (sla_y - PAD_T):.1f}" '
        f'fill="#34d399" opacity="0.05"/>'
    )

    # grid
    grids = ""
    for t in [400, 800, 1200, 1600, 2000, 2400]:
        gx = px(t)
        grids += f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T + ch}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{gx:.1f}" y="{PAD_T + ch + 18}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{t}</text>'
    for lat in [0, 200, 400, 600, 800, 1000, 1200]:
        gy = py(lat)
        grids += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L - 6}" y="{gy + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{lat}</text>'

    def draw_line(data_dict, color, label, dash=""):
        points = " ".join(f"{px(v['throughput']):.1f},{py(v['p99']):.1f}" for k, v in sorted(data_dict.items()))
        stroke_extra = f'stroke-dasharray="{dash}"' if dash else ""
        dots = "".join(
            f'<circle cx="{px(v["throughput"]):.1f}" cy="{py(v["p99"]):.1f}" r="5" fill="{color}"/>'
            f'<text x="{px(v["throughput"]) + 8:.1f}" y="{py(v["p99"]) - 6:.1f}" fill="{color}" font-size="9" font-family="monospace">b={k}</text>'
            for k, v in sorted(data_dict.items())
        )
        return (
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round" {stroke_extra}/>' + dots
        )

    line_80 = draw_line(A100_80, "#38bdf8", "A100 80GB")
    line_40 = draw_line(A100_40, "#818cf8", "A100 40GB", dash="6 3")

    # optimal marker
    opt_x = px(1847)
    opt_y = py(267)
    optimal = (
        f'<circle cx="{opt_x:.1f}" cy="{opt_y:.1f}" r="9" fill="none" stroke="#fbbf24" stroke-width="2"/>'
        f'<text x="{opt_x + 12:.1f}" y="{opt_y + 4:.1f}" fill="#fbbf24" font-size="11" font-weight="bold" font-family="monospace">Optimal (b=8)</text>'
    )

    # axis labels
    axis = (
        f'<text x="{PAD_L + cw // 2}" y="{H - 10}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Throughput (req/hr)</text>'
        f'<text x="14" y="{PAD_T + ch // 2}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace" transform="rotate(-90 14 {PAD_T + ch // 2})">p99 Latency (ms)</text>'
    )

    legend = (
        f'<rect x="{PAD_L}" y="14" width="14" height="4" fill="#38bdf8" rx="2"/>'
        f'<text x="{PAD_L + 20}" y="20" fill="#e2e8f0" font-size="11" font-family="monospace">A100 80GB</text>'
        f'<rect x="{PAD_L + 110}" y="14" width="14" height="4" fill="#818cf8" rx="2"/>'
        f'<text x="{PAD_L + 130}" y="20" fill="#e2e8f0" font-size="11" font-family="monospace">A100 40GB</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:12px;width:100%;max-width:{W}px;">'
        + shade + sla_line + grids + line_80 + line_40 + optimal + axis + legend
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# SVG 2 — Queue depth over 24h: static vs dynamic
# ---------------------------------------------------------------------------

def build_queue_svg() -> str:
    W, H    = 640, 320
    PAD_L   = 65
    PAD_R   = 30
    PAD_T   = 30
    PAD_B   = 50
    cw      = W - PAD_L - PAD_R
    ch      = H - PAD_T - PAD_B
    n       = len(QUEUE_DATA)

    max_q = max(max(d["queue_static"], d["queue_dynamic"]) for d in QUEUE_DATA)
    max_q = max(max_q, 1.0)   # avoid div-zero

    def qx(i): return PAD_L + i / (n - 1) * cw
    def qy(v): return PAD_T + ch - (v / max_q) * ch

    # grid
    grids = ""
    for h in [0, 4, 8, 12, 16, 20, 24]:
        idx = min(int(h * 4), n - 1)
        gx = qx(idx)
        grids += f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T + ch}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{gx:.1f}" y="{PAD_T + ch + 18}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{h:02d}:00</text>'

    levels = [round(max_q * f, 1) for f in [0, 0.25, 0.5, 0.75, 1.0]]
    for lv in levels:
        gy = qy(lv)
        grids += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L - 6}" y="{gy + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{lv:.1f}</text>'

    # static batch polyline
    s_pts = " ".join(f"{qx(i):.1f},{qy(d['queue_static']):.1f}" for i, d in enumerate(QUEUE_DATA))
    static_line = (
        f'<polyline points="{s_pts}" fill="none" stroke="#f87171" stroke-width="2" stroke-linejoin="round" stroke-dasharray="6 3"/>'
    )

    # dynamic batch polyline
    d_pts = " ".join(f"{qx(i):.1f},{qy(d['queue_dynamic']):.1f}" for i, d in enumerate(QUEUE_DATA))
    dynamic_line = (
        f'<polyline points="{d_pts}" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linejoin="round"/>'
    )

    # peak hour annotations
    annots = ""
    for label, hour in [("AM Peak", 9), ("PM Peak", 15)]:
        idx = int(hour * 4)
        ax = qx(idx)
        annots += (
            f'<line x1="{ax:.1f}" y1="{PAD_T}" x2="{ax:.1f}" y2="{PAD_T + ch}" stroke="#fbbf24" stroke-width="1" opacity="0.4"/>'
            f'<text x="{ax:.1f}" y="{PAD_T - 8}" text-anchor="middle" fill="#fbbf24" font-size="10" font-family="monospace">{label}</text>'
        )

    axis = (
        f'<text x="{PAD_L + cw // 2}" y="{H - 10}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Hour of Day</text>'
        f'<text x="14" y="{PAD_T + ch // 2}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace" transform="rotate(-90 14 {PAD_T + ch // 2})">Queue Depth (reqs)</text>'
    )

    legend = (
        f'<rect x="{PAD_L}" y="12" width="14" height="4" fill="#f87171" rx="2"/>'
        f'<text x="{PAD_L + 20}" y="18" fill="#e2e8f0" font-size="11" font-family="monospace">Static batch=4</text>'
        f'<rect x="{PAD_L + 140}" y="12" width="14" height="4" fill="#34d399" rx="2"/>'
        f'<text x="{PAD_L + 160}" y="18" fill="#e2e8f0" font-size="11" font-family="monospace">Dynamic batching</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:12px;width:100%;max-width:{W}px;">'
        + grids + static_line + dynamic_line + annots + axis + legend
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    tradeoff_svg = build_tradeoff_svg()
    queue_svg    = build_queue_svg()

    batch_rows = ""
    for bs in BATCH_SIZES:
        v80 = A100_80[bs]
        v40 = A100_40[bs]
        sla_ok_80 = v80["p99"] < 300
        sla_ok_40 = v40["p99"] < 300
        opt_mark  = " ★" if bs == 8 else ""
        batch_rows += (
            f'<tr>'
            f'<td><b>{bs}{opt_mark}</b></td>'
            f'<td style="color:#38bdf8">{v80["throughput"]}</td>'
            f'<td style="color:{"#34d399" if sla_ok_80 else "#f87171"}">{v80["p99"]}ms {"✓" if sla_ok_80 else "✗"}</td>'
            f'<td style="color:#818cf8">{v40["throughput"]}</td>'
            f'<td style="color:{"#34d399" if sla_ok_40 else "#f87171"}">{v40["p99"]}ms {"✓" if sla_ok_40 else "✗"}</td>'
            f'</tr>'
        )

    km = KEY_METRICS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inference Batching Optimizer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1   {{ font-size: 1.6rem; color: #f8fafc; margin-bottom: 4px; }}
  h2   {{ font-size: 1.1rem; color: #94a3b8; margin: 28px 0 12px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
  .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; line-height: 1.1; }}
  .kpi .lbl {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
  .kpi .sub {{ font-size: 0.72rem; color: #475569; margin-top: 2px; }}
  .oracle-red {{ color: #C74634; }}
  .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 28px; }}
  .chart-title {{ font-size: 0.95rem; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; color: #64748b; font-weight: 500; padding: 8px 12px; border-bottom: 1px solid #334155; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #0f172a; }}
  .footer {{ margin-top: 40px; font-size: 0.75rem; color: #334155; text-align: center; }}
</style>
</head>
<body>
<h1>Inference Batching Optimizer <span class="oracle-red">&#9679;</span> OCI Robot Cloud</h1>
<p class="subtitle">Dynamic batching strategy for GR00T inference &mdash; throughput vs SLA tradeoff &mdash; port 8243</p>

<div class="kpi-grid">
  <div class="kpi"><div class="val">b={km['optimal_batch_size']}</div><div class="lbl">Optimal Batch Size</div><div class="sub">p99 {km['optimal_p99_ms']}ms &lt; 300ms SLA</div></div>
  <div class="kpi"><div class="val">{km['optimal_throughput_req_hr']}</div><div class="lbl">Max Throughput (req/hr)</div><div class="sub">A100 80GB at optimal batch</div></div>
  <div class="kpi"><div class="val">+{km['dynamic_vs_static_gain_pct']}%</div><div class="lbl">Dynamic vs Static Gain</div><div class="sub">vs static batch=4</div></div>
  <div class="kpi"><div class="val">{km['a100_80gb_vs_40gb_ratio']}x</div><div class="lbl">80GB vs 40GB Ratio</div><div class="sub">at batch=16</div></div>
</div>

<div class="chart-card">
  <div class="chart-title">Throughput vs p99 Latency — Batch Size Tradeoff (SLA boundary: p99 &lt; 300ms)</div>
  {tradeoff_svg}
</div>

<div class="chart-card">
  <div class="chart-title">24h Queue Depth Simulation — Static batch=4 vs Dynamic Batching</div>
  {queue_svg}
</div>

<h2>Batch Size Performance Table</h2>
<div class="chart-card">
  <table>
    <thead><tr>
      <th>Batch Size</th>
      <th>A100 80GB Throughput</th><th>A100 80GB p99</th>
      <th>A100 40GB Throughput</th><th>A100 40GB p99</th>
    </tr></thead>
    <tbody>{batch_rows}</tbody>
  </table>
  <p style="margin-top:12px;font-size:0.78rem;color:#475569">★ = optimal operating point &nbsp;|&nbsp; ✓ = SLA compliant (&lt;300ms) &nbsp;|&nbsp; ✗ = SLA violation</p>
</div>

<div class="footer">OCI Robot Cloud &bull; Inference Batching Optimizer &bull; port 8243 &bull; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Inference Batching Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/api/metrics")
    async def metrics():
        return {
            "key_metrics": KEY_METRICS,
            "a100_80gb":   {str(k): v for k, v in A100_80.items()},
            "a100_40gb":   {str(k): v for k, v in A100_40.items()},
            "batch_sizes": BATCH_SIZES,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "inference-batching-optimizer", "port": 8243}

else:
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
        def log_message(self, *a): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8243)
    else:
        with socketserver.TCPServer(("", 8243), Handler) as srv:
            print("Serving on http://0.0.0.0:8243  (stdlib fallback)")
            srv.serve_forever()
