"""OCI Egress Reducer — FastAPI port 8783"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8783


def build_html():
    random.seed(7)
    # 30-day egress cost timeline (GB/day) — before vs after reducer
    days = list(range(1, 31))
    # Before: noisy high egress ~2.0 TB/day with weekly spikes
    before_gb = [
        round(1800 + 400 * math.sin(d * 0.9) + 200 * random.uniform(0, 1) + (300 if d % 7 == 0 else 0), 0)
        for d in days
    ]
    # After (day 15 cutover): drops ~60%, compression + caching kicks in
    after_gb = [
        round(before_gb[i] * (1.0 if i < 14 else (0.38 + 0.04 * math.sin(i * 1.3) + 0.02 * random.uniform(0, 1))), 0)
        for i in range(len(days))
    ]

    # Savings
    cost_per_gb = 0.0085  # OCI standard egress $/GB
    total_before = sum(before_gb)
    total_after  = sum(after_gb)
    saved_gb     = total_before - total_after
    saved_usd    = round(saved_gb * cost_per_gb, 2)
    pct_saved    = round(saved_gb / total_before * 100, 1)

    # SVG line chart
    W, H = 600, 220
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_val = max(max(before_gb), max(after_gb))

    def xp(d_idx):
        return pad_l + d_idx / (len(days) - 1) * chart_w

    def yp(v):
        return pad_t + chart_h - (v / max_val) * chart_h

    def polyline(vals, color, dash=""):
        pts = " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(vals))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{da} stroke-linejoin="round"/>'

    def area(vals, color):
        pts = f"{xp(0):.1f},{yp(0):.1f} " + " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(vals)) + f" {xp(len(vals)-1):.1f},{yp(0):.1f}"
        return f'<polygon points="{pts}" fill="{color}" opacity="0.15"/>'

    # Y-axis ticks
    y_step = 500
    y_ticks = ""
    for v in range(0, int(max_val) + y_step, y_step):
        if v > max_val * 1.05:
            break
        y_ticks += (
            f'<text x="{pad_l - 8}" y="{yp(v):.1f}" fill="#94a3b8" font-size="10" text-anchor="end" dominant-baseline="middle">{v}</text>'
            f'<line x1="{pad_l}" y1="{yp(v):.1f}" x2="{pad_l + chart_w}" y2="{yp(v):.1f}" stroke="#334155" stroke-width="0.5"/>'
        )

    # X-axis day labels every 5
    x_ticks = "".join(
        f'<text x="{xp(i):.1f}" y="{pad_t + chart_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">D{d}</text>'
        for i, d in enumerate(days) if d % 5 == 0 or d == 1
    )

    # Cutover annotation line
    cutover_x = xp(14)
    cutover_line = (
        f'<line x1="{cutover_x:.1f}" y1="{pad_t}" x2="{cutover_x:.1f}" y2="{pad_t + chart_h}" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="5,3"/>'
        f'<text x="{cutover_x + 4:.1f}" y="{pad_t + 12}" fill="#4ade80" font-size="10">Reducer ON</text>'
    )

    # Compression technique breakdown (donut-like bar)
    techniques = [
        ("Zstd compression",    38),
        ("CDN cache hits",      27),
        ("Model diff transfer", 18),
        ("Batched uploads",     10),
        ("Other",                7),
    ]
    colors = ["#38bdf8", "#C74634", "#facc15", "#4ade80", "#a78bfa"]

    BW, BH = 300, 160
    bpad_l, bpad_t, bpad_b = 130, 15, 30
    bchart_h = BH - bpad_t - bpad_b
    bar_h_each = bchart_h / len(techniques) * 0.65
    bar_gap    = bchart_h / len(techniques)
    bchart_w   = BW - bpad_l - 10

    h_bars = ""
    for i, ((name, pct), color) in enumerate(zip(techniques, colors)):
        by = bpad_t + i * bar_gap
        bw = pct / 100 * bchart_w
        h_bars += (
            f'<rect x="{bpad_l}" y="{by:.1f}" width="{bw:.1f}" height="{bar_h_each:.1f}" fill="{color}" rx="2"/>'
            f'<text x="{bpad_l - 6}" y="{by + bar_h_each/2:.1f}" fill="#e2e8f0" font-size="10" text-anchor="end" dominant-baseline="middle">{name}</text>'
            f'<text x="{bpad_l + bw + 4:.1f}" y="{by + bar_h_each/2:.1f}" fill="{color}" font-size="10" dominant-baseline="middle">{pct}%</text>'
        )

    # Top egress sources table
    sources = [
        ("Model checkpoint sync", "682 GB", "214 GB", "69%"),
        ("Training dataset pull", "504 GB", "189 GB", "62%"),
        ("Inference results",     "341 GB", "156 GB", "54%"),
        ("Telemetry export",      "198 GB",  "92 GB", "54%"),
        ("API responses",         "120 GB",  "74 GB", "38%"),
    ]

    rows = ""
    for src, bef, aft, red in sources:
        rows += f"""<tr>
          <td style="padding:5px 10px">{src}</td>
          <td style="padding:5px 10px;text-align:right;color:#f87171">{bef}</td>
          <td style="padding:5px 10px;text-align:right;color:#4ade80">{aft}</td>
          <td style="padding:5px 10px;text-align:right;color:#38bdf8">{red}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>OCI Egress Reducer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1100px;margin-top:16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 18px;margin:4px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#4ade80}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
thead tr{{border-bottom:1px solid #334155}}
th{{text-align:left;color:#94a3b8;padding:5px 10px;font-weight:500}}
tbody tr:nth-child(even){{background:#0f172a}}
</style></head>
<body>
<h1>OCI Egress Reducer</h1>
<p style="color:#94a3b8;margin:0 0 20px 0">Real-time egress cost optimization for Robot Cloud training pipelines | port {PORT}</p>

<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
  <div class="stat"><div class="val">{pct_saved}%</div><div class="lbl">Egress Reduced (30d)</div></div>
  <div class="stat"><div class="val">${saved_usd:,.0f}</div><div class="lbl">Cost Saved (30d)</div></div>
  <div class="stat"><div class="val">{round(saved_gb/1024, 1)} TB</div><div class="lbl">Data Saved</div></div>
  <div class="stat" style="--c:#38bdf8"><div class="val" style="color:#38bdf8">{round(total_after/1024/30, 1)} TB/d</div><div class="lbl">Current Avg Egress</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Daily Egress — Before vs After (GB)</h2>
    <div style="display:flex;gap:16px;font-size:0.8rem;margin-bottom:8px">
      <span style="color:#f87171">&#9644; Before</span>
      <span style="color:#4ade80">&#9644; After</span>
    </div>
    <svg width="{W}" height="{H}" style="overflow:visible">
      {y_ticks}
      {x_ticks}
      <text x="{pad_l - 40}" y="{pad_t + chart_h/2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90 {pad_l-40} {pad_t + chart_h/2})">GB / day</text>
      {area(before_gb, '#f87171')}
      {area(after_gb,  '#4ade80')}
      {polyline(before_gb, '#f87171')}
      {polyline(after_gb,  '#4ade80')}
      {cutover_line}
    </svg>
  </div>

  <div class="card">
    <h2>Savings by Technique</h2>
    <svg width="{BW}" height="{BH}" style="overflow:visible">
      {h_bars}
    </svg>
  </div>
</div>

<div class="card" style="margin-top:16px;max-width:1100px">
  <h2>Top Egress Sources — Last 30 Days</h2>
  <table>
    <thead><tr>
      <th>Source</th>
      <th style="text-align:right">Before</th>
      <th style="text-align:right">After</th>
      <th style="text-align:right">Reduction</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="OCI Egress Reducer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/savings")
    def savings():
        random.seed(7)
        cost_per_gb = 0.0085
        days = list(range(1, 31))
        before_gb = [
            round(1800 + 400 * math.sin(d * 0.9) + 200 * random.uniform(0, 1) + (300 if d % 7 == 0 else 0), 0)
            for d in days
        ]
        after_gb = [
            round(before_gb[i] * (1.0 if i < 14 else (0.38 + 0.04 * math.sin(i * 1.3))), 0)
            for i in range(len(days))
        ]
        saved = sum(before_gb) - sum(after_gb)
        return {
            "saved_gb": saved,
            "saved_usd": round(saved * cost_per_gb, 2),
            "pct_saved": round(saved / sum(before_gb) * 100, 1),
        }


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
