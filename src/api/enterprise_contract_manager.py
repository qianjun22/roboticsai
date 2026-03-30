"""Enterprise Contract Manager — FastAPI port 8841"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8841

def build_html():
    # Contract renewal calendar heatmap — 12 months, ~4 weeks each
    # Simulate renewal density: Q3 (months 7-9) has 3 major renewals
    months = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

    # Renewal counts per month (index 0=Jan)
    renewal_counts = [0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1]
    max_count = max(renewal_counts)

    def heat_color(count):
        if count == 0: return "#1e293b"
        intensity = count / max(max_count, 1)
        # interpolate from #0e7490 (low) to #C74634 (high)
        r = int(0x0e + (0xC7 - 0x0e) * intensity)
        g = int(0x74 + (0x46 - 0x74) * intensity)
        b = int(0x90 + (0x34 - 0x90) * intensity)
        return f"#{r:02x}{g:02x}{b:02x}"

    cells = ""
    cell_w, cell_h, gap = 54, 40, 6
    cols = 6
    for i, (month, count) in enumerate(zip(months, renewal_counts)):
        col = i % cols
        row = i // cols
        x = col * (cell_w + gap) + 4
        y = row * (cell_h + gap) + 4
        color = heat_color(count)
        cells += (
            f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="5" fill="{color}"/>'
            f'<text x="{x + cell_w//2}" y="{y + 15}" text-anchor="middle" fill="#94a3b8" font-size="11">{month}</text>'
        )
        if count > 0:
            cells += f'<text x="{x + cell_w//2}" y="{y + 30}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">{count}</text>'

    svg_w = cols * (cell_w + gap) + 8
    svg_h = (len(months) // cols) * (cell_h + gap) + 8
    heatmap_svg = f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">{cells}</svg>'

    # Pipeline bar: ARR breakdown across 3 renewal contracts
    contracts = [
        ("Acme Robotics", 1.8, "#22c55e", "Q3"),
        ("NovaTech Mfg", 1.4, "#f59e0b", "Q3"),
        ("SkyBridge AI", 1.0, "#ef4444", "Q3"),
    ]
    total_arr = sum(v for _, v, _, _ in contracts)
    contract_bars = ""
    for i, (name, arr, color, quarter) in enumerate(contracts):
        bar_w = math.floor(arr / total_arr * 360)
        y = i * 50 + 10
        contract_bars += (
            f'<text x="10" y="{y}" fill="#94a3b8" font-size="12">{name} ({quarter})</text>'
            f'<rect x="10" y="{y+6}" width="{bar_w}" height="20" rx="4" fill="{color}"/>'
            f'<text x="{bar_w + 18}" y="{y+20}" fill="#e2e8f0" font-size="12" font-weight="bold">${arr}M</text>'
        )
    bar_svg_h = len(contracts) * 50 + 20
    bar_svg = f'<svg width="420" height="{bar_svg_h}" xmlns="http://www.w3.org/2000/svg">{contract_bars}</svg>'

    return f"""<!DOCTYPE html><html><head><title>Enterprise Contract Manager</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.stat{{background:#0f172a;border-radius:6px;padding:14px;text-align:center}}
.stat .val{{font-size:2rem;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.85rem;color:#94a3b8;margin-top:4px}}
.legend{{display:flex;gap:16px;margin-top:10px;font-size:12px;color:#94a3b8}}
.dot{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:4px}}
</style></head>
<body>
<h1>Enterprise Contract Manager</h1>
<p style="color:#94a3b8">Tracks enterprise customer contracts, renewal dates, and expansion opportunities. Port {PORT}</p>

<div class="card">
  <h2>Portfolio Overview</h2>
  <div class="grid">
    <div class="stat"><div class="val">$4.2M</div><div class="lbl">ARR Managed</div></div>
    <div class="stat"><div class="val">3</div><div class="lbl">Q3 Renewals</div></div>
    <div class="stat"><div class="val" style="color:#22c55e">87%</div><div class="lbl">Net Revenue Retention</div></div>
  </div>
</div>

<div class="card">
  <h2>Contract Renewal Calendar (2026)</h2>
  {heatmap_svg}
  <div class="legend">
    <span><span class="dot" style="background:#1e293b"></span>No renewals</span>
    <span><span class="dot" style="background:#0e7490"></span>1 renewal</span>
    <span><span class="dot" style="background:#C74634"></span>High activity</span>
  </div>
</div>

<div class="card">
  <h2>Q3 Renewal Pipeline — ARR Breakdown</h2>
  {bar_svg}
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Enterprise Contract Manager")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
