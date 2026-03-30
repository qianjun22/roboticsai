"""Storage Performance Analyzer — FastAPI port 8689"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8689

def build_html():
    random.seed(7)

    # --- Throughput over time (24 hourly samples, MB/s) ---
    hours = list(range(24))
    read_tp  = [820 + 180 * math.sin(h * math.pi / 12) + random.uniform(-40, 40) for h in hours]
    write_tp = [510 + 120 * math.sin(h * math.pi / 12 + 1.2) + random.uniform(-30, 30) for h in hours]

    cw, ch = 580, 180
    pl, pr, pt, pb = 55, 20, 15, 35
    pw = cw - pl - pr
    ph = ch - pt - pb
    max_tp = 1050

    def tpx(h, v):
        x = pl + (h / 23) * pw
        y = pt + ph - (v / max_tp) * ph
        return x, y

    def tp_poly(vals, color):
        pts = " ".join(f"{tpx(hours[i], vals[i])[0]:.1f},{tpx(hours[i], vals[i])[1]:.1f}" for i in range(len(hours)))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"/>'

    tp_xticks = ""
    for h in range(0, 24, 4):
        x, _ = tpx(h, 0)
        tp_xticks += (f'<line x1="{x:.1f}" y1="{pt+ph}" x2="{x:.1f}" y2="{pt+ph+4}" stroke="#475569"/>'
                      f'<text x="{x:.1f}" y="{pt+ph+14}" text-anchor="middle" fill="#94a3b8" font-size="10">{h:02d}:00</text>')
    tp_yticks = ""
    for v in [200, 400, 600, 800, 1000]:
        _, y = tpx(0, v)
        tp_yticks += (f'<line x1="{pl}" y1="{y:.1f}" x2="{pl+pw}" y2="{y:.1f}" stroke="#1e3a5f" stroke-dasharray="4,3"/>'
                      f'<text x="{pl-6}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{v}</text>')

    tp_svg = f"""
    <svg width="{cw}" height="{ch}" style="background:#0f2744;border-radius:6px">
      {tp_yticks}{tp_xticks}
      {tp_poly(read_tp, '#22c55e')}
      {tp_poly(write_tp, '#f97316')}
      <text x="{pl}" y="12" fill="#22c55e" font-size="10">● Read MB/s</text>
      <text x="{pl+80}" y="12" fill="#f97316" font-size="10">● Write MB/s</text>
      <text x="{cw//2}" y="{ch-2}" text-anchor="middle" fill="#64748b" font-size="10">Hour of Day</text>
      <text x="14" y="{pt+ph//2}" text-anchor="middle" fill="#64748b" font-size="10" transform="rotate(-90,14,{pt+ph//2})">MB/s</text>
    </svg>"""

    # --- Latency percentile bar chart (p50, p90, p99, p999 per tier) ---
    tiers = ["NVMe Local", "OCI Block", "OCI FSS", "Object Store"]
    p50  = [0.08, 0.41, 1.2,  4.8]
    p90  = [0.19, 0.88, 2.7,  12.1]
    p99  = [0.52, 2.10, 6.3,  28.4]
    p999 = [1.84, 7.60, 19.8, 91.0]
    colors = ["#22c55e", "#38bdf8", "#f97316", "#ef4444"]
    labels = ["p50", "p90", "p99", "p999"]
    all_series = [p50, p90, p99, p999]

    lw, lh = 560, 200
    llpad, lrpad, ltpad, lbpad = 80, 20, 20, 50
    lpw = lw - llpad - lrpad
    lph = lh - ltpad - lbpad
    n_tiers = len(tiers)
    slot = lpw / n_tiers
    n_series = len(all_series)
    bw = slot * 0.18
    max_lat = 100.0

    lat_bars = ""
    for ti in range(n_tiers):
        x_slot = llpad + ti * slot
        for si, (ser, col) in enumerate(zip(all_series, colors)):
            bx = x_slot + slot * 0.06 + si * (bw + 1.5)
            val = ser[ti]
            bh_val = (val / max_lat) * lph
            by = ltpad + lph - bh_val
            lat_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh_val:.1f}" fill="{col}" rx="2"/>'
        # tier label
        lx = x_slot + slot / 2
        lat_bars += f'<text x="{lx:.1f}" y="{ltpad+lph+14}" text-anchor="middle" fill="#94a3b8" font-size="10" transform="rotate(-20,{lx:.1f},{ltpad+lph+14})">{tiers[ti]}</text>'

    lat_grids = ""
    for pct in [25, 50, 75, 100]:
        gy = ltpad + lph - (pct / max_lat) * lph
        lat_grids += (f'<line x1="{llpad}" y1="{gy:.1f}" x2="{llpad+lpw}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-dasharray="4,3"/>'
                      f'<text x="{llpad-5}" y="{gy+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{pct}ms</text>')

    legend_lat = "".join(
        f'<text x="{llpad + i*70}" y="12" fill="{col}" font-size="10">● {lab}</text>'
        for i, (lab, col) in enumerate(zip(labels, colors))
    )
    lat_svg = f"""
    <svg width="{lw}" height="{lh}" style="background:#0f2744;border-radius:6px">
      {lat_grids}{lat_bars}{legend_lat}
    </svg>"""

    # --- IOPS gauge (semi-circle) ---
    def semi_arc(cx, cy, r, pct, color, stroke_w=14):
        # pct in [0,1], 180-deg sweep left-to-right
        start_angle = math.pi  # left
        sweep = math.pi * pct
        end_angle = start_angle - sweep
        x1 = cx + r * math.cos(start_angle)
        y1 = cy - r * math.sin(start_angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy - r * math.sin(end_angle)
        large = 1 if pct > 0.5 else 0
        return (f'<path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round"/>')

    gauges = [
        ("Read IOPS",  "247k",  0.82, "#22c55e"),
        ("Write IOPS", "189k",  0.63, "#f97316"),
        ("Cache Hit",  "96.4%", 0.96, "#38bdf8"),
    ]
    gauge_svgs = ""
    for title, val, pct, color in gauges:
        gcx, gcy, gr = 80, 80, 58
        track = semi_arc(gcx, gcy, gr, 1.0, "#1e3a5f", 14)
        arc   = semi_arc(gcx, gcy, gr, pct, color, 14)
        gauge_svgs += f"""
        <div style="text-align:center">
          <svg width="160" height="95" style="background:#0f2744;border-radius:8px">
            {track}{arc}
            <text x="{gcx}" y="{gcy+8}" text-anchor="middle" fill="{color}" font-size="18" font-weight="700">{val}</text>
            <text x="{gcx}" y="{gcy+22}" text-anchor="middle" fill="#94a3b8" font-size="10">{title}</text>
          </svg>
        </div>"""

    # --- Storage tier utilisation stacked bar ---
    util_tiers = [
        ("NVMe Local",   88, "#ef4444"),
        ("OCI Block Vol",61, "#f97316"),
        ("OCI FSS",      44, "#38bdf8"),
        ("Object Store", 27, "#22c55e"),
    ]
    util_items = "".join(
        f'<div style="margin-bottom:10px">'
        f'<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">'
        f'<span>{name}</span><span style="color:{col}">{pct}%</span></div>'
        f'<div style="background:#0f2744;border-radius:4px;height:10px">'
        f'<div style="background:{col};width:{pct}%;height:100%;border-radius:4px"></div></div></div>'
        for name, pct, col in util_tiers
    )

    # --- KPI cards ---
    kpis = [
        ("Peak Read",   "1,024 MB/s", "NVMe burst"),
        ("Peak Write",  "638 MB/s",   "sustained"),
        ("Avg Latency", "0.41 ms",    "OCI Block p50"),
        ("Cache Hit",   "96.4%",      "read cache"),
        ("Total Cap.",  "48 TB",      "provisioned"),
        ("Data Written","2.1 PB",     "lifetime"),
    ]
    kpi_html = "".join(
        f'<div style="background:#1e293b;padding:12px 16px;border-radius:8px;border-left:3px solid #38bdf8">'
        f'<div style="font-size:11px;color:#64748b">{label}</div>'
        f'<div style="font-size:22px;font-weight:700;color:#38bdf8">{val}</div>'
        f'<div style="font-size:11px;color:#94a3b8">{sub}</div></div>'
        for label, val, sub in kpis
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Storage Performance Analyzer — Port {PORT}</title>
<style>
  * {{ box-sizing:border-box }}
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif }}
  h1 {{ color:#C74634; margin:0; font-size:22px }}
  h2 {{ color:#38bdf8; font-size:15px; margin:0 0 12px }}
  .topbar {{ background:#1e293b; padding:16px 24px; display:flex; align-items:center; gap:16px; border-bottom:1px solid #334155 }}
  .badge {{ background:#C74634; color:#fff; font-size:11px; padding:3px 8px; border-radius:4px }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:20px }}
  .card {{ background:#1e293b; padding:18px; border-radius:10px }}
  .card.full {{ grid-column:1/-1 }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px }}
  .gauge-row {{ display:flex; gap:12px; justify-content:center }}
  .status {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:#22c55e; margin-right:6px }}
</style></head>
<body>
<div class="topbar">
  <h1>Storage Performance Analyzer</h1>
  <span class="badge">LIVE</span>
  <span style="margin-left:auto;font-size:12px;color:#64748b">OCI Robot Cloud &nbsp;|&nbsp; <span class="status"></span>Healthy &nbsp;|&nbsp; Port {PORT}</span>
</div>
<div class="grid">
  <div class="card full">
    <h2>Storage KPIs</h2>
    <div class="kpi-grid">{kpi_html}</div>
  </div>
  <div class="card full">
    <h2>Read / Write Throughput — Last 24 Hours (MB/s)</h2>
    {tp_svg}
  </div>
  <div class="card">
    <h2>IOPS &amp; Cache Gauges</h2>
    <div class="gauge-row">{gauge_svgs}</div>
  </div>
  <div class="card">
    <h2>Tier Utilization</h2>
    {util_items}
  </div>
  <div class="card full">
    <h2>Latency Percentiles by Storage Tier (ms)</h2>
    {lat_svg}
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Storage Performance Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "storage_performance_analyzer"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
