"""NPS Action Tracker — FastAPI port 8739"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8739

def build_html():
    random.seed(17)
    # Simulate NPS scores over 12 months
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    nps_scores = []
    for i, m in enumerate(months):
        base = 42 + 18 * math.sin(i / 3.0) + random.uniform(-5, 5)
        nps_scores.append(round(base, 1))

    latest_nps = nps_scores[-1]
    avg_nps = round(sum(nps_scores) / len(nps_scores), 1)
    peak_nps = max(nps_scores)
    trend = round(nps_scores[-1] - nps_scores[-2], 1)

    # Simulate open action items from detractors
    categories = ["Inference Latency", "API Reliability", "SDK Docs", "Billing Clarity", "Support Response"]
    actions = []
    for i, cat in enumerate(categories):
        count = random.randint(2, 9)
        resolved = random.randint(0, count)
        priority = ["High", "Medium", "Low"][i % 3]
        owner = random.choice(["Platform", "DevEx", "Infra", "Support"])
        actions.append({"cat": cat, "open": count - resolved, "resolved": resolved, "priority": priority, "owner": owner})

    # SVG: NPS trend line with filled area
    svg_w, svg_h = 560, 180
    min_nps, max_nps = 20, 75
    def scale_y(v):
        return int(svg_h - 20 - ((v - min_nps) / (max_nps - min_nps)) * (svg_h - 40))
    def scale_x(i):
        return int(20 + (i / (len(months) - 1)) * (svg_w - 40))

    line_pts = " ".join(f"{scale_x(i)},{scale_y(v)}" for i, v in enumerate(nps_scores))
    area_pts = f"20,{svg_h-20} " + line_pts + f" {scale_x(len(months)-1)},{svg_h-20}"

    # Month labels
    month_labels = ""
    for i, m in enumerate(months):
        month_labels += f'<text x="{scale_x(i)}" y="{svg_h-4}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'

    # NPS dots
    dots = ""
    for i, v in enumerate(nps_scores):
        col = "#22c55e" if v >= 50 else ("#f59e0b" if v >= 30 else "#ef4444")
        dots += f'<circle cx="{scale_x(i)}" cy="{scale_y(v)}" r="4" fill="{col}"/>'

    # SVG: horizontal bar chart for action items
    bar_svg = ""
    for bi, a in enumerate(actions):
        total = a["open"] + a["resolved"]
        bw_total = 280
        bw_res = int((a["resolved"] / total) * bw_total) if total > 0 else 0
        bw_open = bw_total - bw_res
        by = 20 + bi * 28
        bar_svg += f'<rect x="160" y="{by}" width="{bw_res}" height="18" fill="#22c55e" rx="3"/>'
        bar_svg += f'<rect x="{160+bw_res}" y="{by}" width="{bw_open}" height="18" fill="#ef4444" rx="3"/>'
        bar_svg += f'<text x="155" y="{by+13}" fill="#e2e8f0" font-size="11" text-anchor="end">{a["cat"][:16]}</text>'
        bar_svg += f'<text x="{162+bw_total}" y="{by+13}" fill="#94a3b8" font-size="11">{a["resolved"]}/{total}</text>'

    action_rows = ""
    priority_color = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
    for a in actions:
        pc = priority_color.get(a["priority"], "#e2e8f0")
        action_rows += f"""<tr>
          <td>{a['cat']}</td>
          <td style='color:{pc};font-weight:600'>{a['priority']}</td>
          <td>{a['owner']}</td>
          <td style='color:#ef4444'>{a['open']}</td>
          <td style='color:#22c55e'>{a['resolved']}</td>
        </tr>"""

    trend_color = "#22c55e" if trend >= 0 else "#ef4444"
    trend_arrow = "▲" if trend >= 0 else "▼"

    return f"""<!DOCTYPE html><html><head><title>NPS Action Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top}}
.grid{{display:flex;flex-wrap:wrap}}
.stat{{font-size:2em;font-weight:700;color:#38bdf8}}
.sublabel{{color:#94a3b8;font-size:0.85em}}
table{{border-collapse:collapse;width:100%;font-size:0.9em}}
th{{color:#94a3b8;border-bottom:1px solid #334155;padding:6px 10px;text-align:left}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:600}}
</style></head>
<body>
<h1>NPS Action Tracker</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 12px'>Port {PORT} &mdash; Net Promoter Score monitoring &amp; detractor action management for OCI Robot Cloud</p>
<div class='grid'>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Current NPS</div>
    <div class='stat'>{latest_nps}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>12-Mo Average</div>
    <div class='stat'>{avg_nps}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Peak NPS</div>
    <div class='stat' style='color:#22c55e'>{peak_nps}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>MoM Trend</div>
    <div class='stat' style='color:{trend_color}'>{trend_arrow} {abs(trend)}</div>
  </div>
  <div class='card' style='min-width:160px'>
    <div class='sublabel'>Open Actions</div>
    <div class='stat' style='color:#f59e0b'>{sum(a["open"] for a in actions)}</div>
  </div>
</div>
<div class='grid'>
  <div class='card' style='width:580px'>
    <h2>NPS Score Trend (12 Months)</h2>
    <svg width='{svg_w}' height='{svg_h}' style='background:#0f172a;border-radius:6px'>
      <polygon points='{area_pts}' fill='#38bdf8' opacity='0.12'/>
      <polyline points='{line_pts}' fill='none' stroke='#38bdf8' stroke-width='2.5'/>
      {dots}
      {month_labels}
      <text x='8' y='18' fill='#94a3b8' font-size='11'>NPS</text>
    </svg>
  </div>
  <div class='card' style='width:480px'>
    <h2>Action Resolution by Category</h2>
    <svg width='460' height='{20 + len(actions)*28 + 10}' style='background:#0f172a;border-radius:6px'>
      {bar_svg}
      <text x='162' y='{20+len(actions)*28+8}' fill='#22c55e' font-size='10'>Resolved</text>
      <text x='222' y='{20+len(actions)*28+8}' fill='#ef4444' font-size='10'>Open</text>
    </svg>
  </div>
</div>
<div class='card' style='width:calc(100% - 60px)'>
  <h2>Action Items by Category</h2>
  <table>
    <tr><th>Category</th><th>Priority</th><th>Owner</th><th>Open</th><th>Resolved</th></tr>
    {action_rows}
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="NPS Action Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/nps")
    def api_nps():
        random.seed(17)
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return [{"month": m, "nps": round(42 + 18 * math.sin(i / 3.0) + random.uniform(-5, 5), 1)}
                for i, m in enumerate(months)]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
