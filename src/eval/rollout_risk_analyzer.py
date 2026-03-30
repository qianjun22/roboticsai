"""Rollout Risk Analyzer — FastAPI port 8842"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8842

# Risk matrix data: (label, impact 1-5, probability 1-5, is_high_risk)
ROLLOUT_RISKS = [
    ("v2.1.0-canary", 4, 3, True),
    ("v2.0.9-stable", 2, 2, False),
    ("v2.1.1-patch",  3, 1, False),
]

def build_svg_heatmap():
    cell_size = 60
    pad = 50
    grid = 5
    width  = pad + grid * cell_size + 40
    height = pad + grid * cell_size + 40

    # Colour gradient: low=green, mid=yellow, high=red
    def cell_color(col, row):  # col=impact(1-5), row=prob(1-5)
        score = col * row  # 1..25
        if score <= 4:   return "#22c55e"
        if score <= 9:   return "#84cc16"
        if score <= 14:  return "#eab308"
        if score <= 19:  return "#f97316"
        return "#ef4444"

    rects = []
    for c in range(1, grid + 1):
        for r in range(1, grid + 1):
            x = pad + (c - 1) * cell_size
            y = pad + (grid - r) * cell_size
            color = cell_color(c, r)
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{color}" stroke="#0f172a" stroke-width="1" opacity="0.75"/>'
            )

    # Plot rollout dots
    dots = []
    for label, impact, prob, high in ROLLOUT_RISKS:
        cx = pad + (impact - 1) * cell_size + cell_size // 2
        cy = pad + (grid - prob) * cell_size + cell_size // 2
        fill = "#ef4444" if high else "#38bdf8"
        dots.append(
            f'<circle cx="{cx}" cy="{cy}" r="10" fill="{fill}" stroke="white" stroke-width="2"/>'
            f'<text x="{cx}" y="{cy - 14}" fill="white" font-size="9" text-anchor="middle">{label}</text>'
        )

    # Axis labels
    x_labels = "".join(
        f'<text x="{pad + (i)*cell_size + cell_size//2}" y="{pad + grid*cell_size + 18}" '
        f'fill="#94a3b8" font-size="10" text-anchor="middle">{i+1}</text>'
        for i in range(grid)
    )
    y_labels = "".join(
        f'<text x="{pad - 8}" y="{pad + (grid - 1 - i)*cell_size + cell_size//2 + 4}" '
        f'fill="#94a3b8" font-size="10" text-anchor="end">{i+1}</text>'
        for i in range(grid)
    )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(rects)
        + "".join(dots)
        + x_labels
        + y_labels
        + f'<text x="{pad + grid*cell_size//2}" y="{pad + grid*cell_size + 34}" '
          f'fill="#cbd5e1" font-size="11" text-anchor="middle">Impact</text>'
        + f'<text x="12" y="{pad + grid*cell_size//2}" fill="#cbd5e1" font-size="11" '
          f'text-anchor="middle" transform="rotate(-90,12,{pad + grid*cell_size//2})">Probability</text>'
        + "</svg>"
    )


def build_html():
    svg = build_svg_heatmap()
    rows = "".join(
        f"<tr><td>{label}</td><td>Impact {impact}</td><td>Prob {prob}</td>"
        f"<td style='color:{'#ef4444' if high else '#22c55e'}'>{'HIGH RISK' if high else 'OK'}</td></tr>"
        for label, impact, prob, high in ROLLOUT_RISKS
    )
    return f"""<!DOCTYPE html><html><head><title>Rollout Risk Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}.metric{{font-size:2rem;font-weight:bold;color:#f97316}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8rem}}</style></head>
<body>
<h1>Rollout Risk Analyzer</h1>
<div class="card">
  <h2>Live Metrics</h2>
  <div style="display:flex;gap:30px;flex-wrap:wrap">
    <div><div class="metric">3</div><div>Active Rollouts</div></div>
    <div><div class="metric" style="color:#ef4444">1</div><div>High-Risk Flagged</div></div>
    <div><div class="metric" style="color:#eab308">+0.4%</div><div>Avg Error Rate Delta</div></div>
    <div><div class="metric" style="color:#38bdf8">8842</div><div>Port</div></div>
  </div>
</div>
<div class="card">
  <h2>Risk Matrix (Impact × Probability)</h2>
  <div style="overflow-x:auto">{svg}</div>
  <p style="color:#94a3b8;font-size:0.85rem">
    <span class="badge" style="background:#ef4444">RED</span> = High Risk &nbsp;
    <span class="badge" style="background:#38bdf8">BLUE</span> = Normal
  </p>
</div>
<div class="card">
  <h2>Canary Metrics</h2>
  <table><tr><th>Version</th><th>Error Rate Delta</th><th>Latency P99</th><th>SR Change</th><th>Risk</th></tr>
    <tr><td>v2.1.0-canary</td><td style="color:#ef4444">+1.2%</td><td>342ms</td><td>-3.1%</td>
        <td><span class="badge" style="background:#ef4444">HIGH</span></td></tr>
    <tr><td>v2.0.9-stable</td><td style="color:#22c55e">-0.1%</td><td>198ms</td><td>+0.2%</td>
        <td><span class="badge" style="background:#22c55e">OK</span></td></tr>
    <tr><td>v2.1.1-patch</td><td style="color:#eab308">+0.1%</td><td>210ms</td><td>+0.5%</td>
        <td><span class="badge" style="background:#eab308">MED</span></td></tr>
  </table>
</div>
<div class="card">
  <h2>Rollout Summary</h2>
  <table><tr><th>Version</th><th>Impact</th><th>Probability</th><th>Status</th></tr>{rows}</table>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Rollout Risk Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/risks")
    def risks():
        return [
            {"version": label, "impact": impact, "probability": prob, "high_risk": high}
            for label, impact, prob, high in ROLLOUT_RISKS
        ]


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
