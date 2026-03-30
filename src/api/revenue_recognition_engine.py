"""Revenue Recognition Engine — FastAPI port 8807"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8807

# Revenue recognition for robot-cloud subscriptions (ASC 606 / IFRS 15)
# Recognizes revenue over contract performance obligations

def build_html():
    random.seed(7)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Simulate monthly contracted, recognized, deferred revenue (USD thousands)
    base_contract = 420
    recognized = []
    deferred = []
    contracted = []
    for i, _ in enumerate(months):
        growth = 1 + 0.07 * math.log1p(i)
        c = round(base_contract * growth + random.gauss(0, 18), 1)
        r = round(c * (0.72 + 0.04 * math.sin(i * 0.7)) + random.gauss(0, 8), 1)
        d = round(c - r + random.uniform(5, 25), 1)
        contracted.append(c)
        recognized.append(r)
        deferred.append(max(0, d))

    total_recognized = sum(recognized)
    total_deferred = sum(deferred)
    total_contracted = sum(contracted)
    avg_recognition_rate = round(total_recognized / total_contracted * 100, 1)

    # SVG grouped bar chart
    svg_w, svg_h = 660, 220
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b
    n = len(months)
    bar_group_w = chart_w / n
    bar_w = bar_group_w * 0.28
    max_val = max(max(contracted), max(recognized), max(deferred)) * 1.1

    def bar_y(v):
        return pad_t + chart_h * (1 - v / max_val)

    def bar_h(v):
        return chart_h * v / max_val

    bars = ""
    for i, m in enumerate(months):
        gx = pad_l + i * bar_group_w + bar_group_w * 0.05
        bars += f'<rect x="{gx:.1f}" y="{bar_y(contracted[i]):.1f}" width="{bar_w:.1f}" height="{bar_h(contracted[i]):.1f}" fill="#38bdf8" opacity="0.75"/>'
        bars += f'<rect x="{gx + bar_w + 2:.1f}" y="{bar_y(recognized[i]):.1f}" width="{bar_w:.1f}" height="{bar_h(recognized[i]):.1f}" fill="#4ade80" opacity="0.85"/>'
        bars += f'<rect x="{gx + 2 * (bar_w + 2):.1f}" y="{bar_y(deferred[i]):.1f}" width="{bar_w:.1f}" height="{bar_h(deferred[i]):.1f}" fill="#f472b6" opacity="0.75"/>'
        bars += f'<text x="{gx + bar_group_w * 0.35:.1f}" y="{pad_t + chart_h + 14}" font-size="9" fill="#94a3b8" text-anchor="middle">{m}</text>'

    # Y-axis gridlines
    grid = ""
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        v = max_val * tick
        y = bar_y(v)
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{svg_w - pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'
        grid += f'<text x="{pad_l - 4}" y="{y + 4:.1f}" font-size="8" fill="#64748b" text-anchor="end">${v:.0f}k</text>'

    legend = (
        '<rect x="60" y="4" width="10" height="10" fill="#38bdf8"/>'
        '<text x="73" y="13" font-size="10" fill="#e2e8f0">Contracted</text>'
        '<rect x="155" y="4" width="10" height="10" fill="#4ade80"/>'
        '<text x="168" y="13" font-size="10" fill="#e2e8f0">Recognized</text>'
        '<rect x="258" y="4" width="10" height="10" fill="#f472b6"/>'
        '<text x="271" y="13" font-size="10" fill="#e2e8f0">Deferred</text>'
    )

    # Cumulative recognized revenue curve (area chart)
    cum = []
    acc = 0
    for r in recognized:
        acc += r
        cum.append(acc)

    svg2_w, svg2_h = 660, 180
    c_pad = 40
    cx_range = svg2_w - 2 * c_pad
    cy_range = svg2_h - 2 * c_pad
    max_cum = cum[-1] * 1.05

    def cx(i):
        return c_pad + i * cx_range / (n - 1)

    def cy(v):
        return c_pad + cy_range * (1 - v / max_cum)

    area_pts = f"{cx(0):.1f},{cy(0):.1f} " + " ".join(f"{cx(i):.1f},{cy(v):.1f}" for i, v in enumerate(cum))
    area_pts += f" {cx(n-1):.1f},{svg2_h - c_pad} {cx(0):.1f},{svg2_h - c_pad}"
    line_pts = " ".join(f"{cx(i):.1f},{cy(v):.1f}" for i, v in enumerate(cum))
    cum_dots = "".join(
        f'<circle cx="{cx(i):.1f}" cy="{cy(v):.1f}" r="3" fill="#4ade80"/>'
        for i, v in enumerate(cum)
    )
    cum_grid = ""
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        v = max_cum * tick
        y = cy(v)
        cum_grid += f'<line x1="{c_pad}" y1="{y:.1f}" x2="{svg2_w - c_pad}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'
        cum_grid += f'<text x="{c_pad - 4}" y="{y + 4:.1f}" font-size="8" fill="#64748b" text-anchor="end">${v:.0f}k</text>'

    # Obligation breakdown table
    obligations = [
        ("Platform Access", round(total_recognized * 0.42, 1), "Ratable"),
        ("Fine-Tuning Compute", round(total_recognized * 0.27, 1), "Usage-Based"),
        ("Data Ingestion API", round(total_recognized * 0.16, 1), "Milestone"),
        ("Model Hosting SLA", round(total_recognized * 0.10, 1), "Ratable"),
        ("Professional Services", round(total_recognized * 0.05, 1), "Completed"),
    ]
    ob_colors = ["#38bdf8", "#4ade80", "#facc15", "#f472b6", "#a78bfa"]
    ob_rows = "".join(
        f'<tr><td style="padding:5px 12px;color:{ob_colors[i]}">{name}</td>'
        f'<td style="padding:5px 12px">${amt:.1f}k</td>'
        f'<td style="padding:5px 12px;color:#94a3b8">{method}</td>'
        f'<td style="padding:5px 12px">{round(amt/total_recognized*100,1)}%</td></tr>'
        for i, (name, amt, method) in enumerate(obligations)
    )

    html = f"""<!DOCTYPE html><html><head><title>Revenue Recognition Engine</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:16px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 20px;margin:6px;text-align:center}}
.stat .val{{font-size:1.8em;font-weight:bold;color:#4ade80}}
.stat .lbl{{font-size:0.75em;color:#94a3b8}}
table{{border-collapse:collapse;width:100%}}
tr:hover td{{background:#0f172a22}}
</style></head>
<body>
<h1>Revenue Recognition Engine</h1>
<p style="color:#64748b">Port {PORT} | ASC 606 / IFRS 15 compliant — OCI Robot Cloud subscriptions</p>

<div class="card">
  <h2>FY Summary</h2>
  <div class="stat"><div class="val">${total_contracted:.0f}k</div><div class="lbl">Total Contracted ARR</div></div>
  <div class="stat"><div class="val">${total_recognized:.0f}k</div><div class="lbl">Revenue Recognized</div></div>
  <div class="stat"><div class="val">${total_deferred:.0f}k</div><div class="lbl">Deferred Revenue</div></div>
  <div class="stat"><div class="val" style="color:#facc15">{avg_recognition_rate}%</div><div class="lbl">Avg Recognition Rate</div></div>
</div>

<div class="card">
  <h2>Monthly Revenue Breakdown (USD thousands)</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    {grid}
    {bars}
    <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>
    <line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{svg_w - pad_r}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>
  </svg>
  <svg width="{svg_w}" height="20">{legend}</svg>
</div>

<div class="card">
  <h2>Cumulative Recognized Revenue</h2>
  <svg width="{svg2_w}" height="{svg2_h}" style="display:block">
    {cum_grid}
    <polygon points="{area_pts}" fill="#4ade80" opacity="0.15"/>
    <polyline points="{line_pts}" fill="none" stroke="#4ade80" stroke-width="2"/>
    {cum_dots}
    <line x1="{c_pad}" y1="{c_pad}" x2="{c_pad}" y2="{svg2_h - c_pad}" stroke="#475569" stroke-width="1"/>
    <line x1="{c_pad}" y1="{svg2_h - c_pad}" x2="{svg2_w - c_pad}" y2="{svg2_h - c_pad}" stroke="#475569" stroke-width="1"/>
  </svg>
</div>

<div class="card">
  <h2>Performance Obligation Breakdown</h2>
  <table>
    <tr style="border-bottom:1px solid #334155">
      <th style="padding:6px 12px;text-align:left;color:#64748b">Obligation</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Recognized</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Method</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">% of Total</th>
    </tr>
    {ob_rows}
  </table>
</div>

</body></html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="Revenue Recognition Engine")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/summary")
    def summary():
        random.seed()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        recognized = [round(420 * (1 + 0.07 * math.log1p(i)) * (0.72 + 0.04 * math.sin(i * 0.7)), 1)
                      for i in range(12)]
        return {
            "total_recognized_usd_k": round(sum(recognized), 1),
            "months": dict(zip(months, recognized)),
            "port": PORT,
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
