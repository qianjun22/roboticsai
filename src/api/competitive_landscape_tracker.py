"""Competitive Landscape Tracker — FastAPI port 8851"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8851

# 6 dimensions for radar chart
DIMENSIONS = [
    "Cost Efficiency",
    "Model Quality",
    "Cloud Integration",
    "US-Origin Moat",
    "NVIDIA Partnership",
    "Enterprise Readiness",
]

# Scores 0-10 per competitor per dimension
COMPETITORS = {
    "OCI Robot Cloud":        [9.6, 7.5, 9.8, 9.5, 9.2, 8.8],
    "Physical Intelligence":  [5.0, 9.2, 3.5, 8.0, 4.0, 5.5],
    "Figure AI":              [4.5, 8.0, 3.0, 8.5, 5.0, 5.0],
    "1X Technologies":        [4.0, 7.5, 2.5, 6.0, 3.0, 4.5],
    "Covariant":              [5.5, 8.5, 4.0, 7.5, 4.5, 7.0],
}

COLORS = {
    "OCI Robot Cloud":        "#C74634",
    "Physical Intelligence":  "#38bdf8",
    "Figure AI":              "#a78bfa",
    "1X Technologies":        "#fb923c",
    "Covariant":              "#4ade80",
}

SVG_W, SVG_H = 560, 520
CX, CY, R = SVG_W // 2, SVG_H // 2 - 20, 190
N = len(DIMENSIONS)

def _radar_pt(i, score, max_score=10):
    angle = math.pi / 2 - (2 * math.pi * i / N)
    r = R * score / max_score
    return CX + r * math.cos(angle), CY - r * math.sin(angle)

def _axis_pt(i, r_frac=1.0):
    angle = math.pi / 2 - (2 * math.pi * i / N)
    r = R * r_frac
    return CX + r * math.cos(angle), CY - r * math.sin(angle)

def build_svg():
    parts = []
    # Background rings
    for frac in [0.2, 0.4, 0.6, 0.8, 1.0]:
        ring_pts = " ".join(f"{_axis_pt(i, frac)[0]:.1f},{_axis_pt(i, frac)[1]:.1f}" for i in range(N))
        parts.append(f'<polygon points="{ring_pts}" fill="none" stroke="#334155" stroke-width="1"/>')
    # Ring labels (10% steps)
    for frac, label in [(0.2, "2"), (0.4, "4"), (0.6, "6"), (0.8, "8"), (1.0, "10")]:
        lx, ly = _axis_pt(0, frac)
        parts.append(f'<text x="{lx+4:.1f}" y="{ly:.1f}" fill="#475569" font-size="9">{label}</text>')
    # Axis lines + labels
    for i, dim in enumerate(DIMENSIONS):
        ax, ay = _axis_pt(i, 1.0)
        parts.append(f'<line x1="{CX}" y1="{CY}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#475569" stroke-width="1"/>')
        lx, ly = _axis_pt(i, 1.18)
        anchor = "middle"
        if lx < CX - 10: anchor = "end"
        elif lx > CX + 10: anchor = "start"
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="#94a3b8" font-size="11">{dim}</text>')
    # Competitor polygons (draw OCI last so it's on top)
    order = [k for k in COMPETITORS if k != "OCI Robot Cloud"] + ["OCI Robot Cloud"]
    for name in order:
        scores = COMPETITORS[name]
        color = COLORS[name]
        pts = " ".join(f"{_radar_pt(i, scores[i])[0]:.1f},{_radar_pt(i, scores[i])[1]:.1f}" for i in range(N))
        opacity = "0.18" if name != "OCI Robot Cloud" else "0.28"
        width = "2.5" if name == "OCI Robot Cloud" else "1.5"
        parts.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="{width}"/>')
    return f'<svg width="{SVG_W}" height="{SVG_H}" style="background:#0f172a;border-radius:8px">{chr(10).join(parts)}</svg>'

def build_html():
    svg = build_svg()
    legend_items = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
        f'<div style="width:14px;height:14px;border-radius:2px;background:{COLORS[n]}"></div>'
        f'<span style="font-size:13px">{n}</span></div>'
        for n in COMPETITORS
    )
    metrics_rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b">'
        f'<td style="padding:8px;color:{COLORS[name]}">{name}</td>'
        + "".join(f'<td style="text-align:right;padding:8px">{s:.1f}</td>' for s in scores)
        + f'<td style="text-align:right;padding:8px;font-weight:700">{sum(scores)/len(scores):.1f}</td>'
        f'</tr>'
        for name, scores in COMPETITORS.items()
    )
    return f"""<!DOCTYPE html><html><head><title>Competitive Landscape Tracker</title>
<style>body{{margin:0;padding:20px;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.moat{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}}
.metric{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.val{{font-size:26px;font-weight:700;color:#C74634}}.label{{font-size:12px;color:#94a3b8;margin-top:4px}}
</style></head>
<body>
<h1>Competitive Landscape Tracker</h1>
<p style="color:#94a3b8;margin-top:0">OCI Robot Cloud vs Physical Intelligence vs Figure AI vs 1X vs Covariant</p>

<div class="card" style="display:flex;gap:24px;align-items:flex-start">
  <div>
    <h2>Radar Chart — 6 Dimensions</h2>
    {svg}
  </div>
  <div style="min-width:180px">
    <h2>Legend</h2>
    {legend_items}
    <div style="margin-top:16px;font-size:12px;color:#64748b">
      Scale: 0–10 per dimension<br>
      Dimensions: Cost Efficiency, Model Quality,<br>
      Cloud Integration, US-Origin Moat,<br>
      NVIDIA Partnership, Enterprise Readiness
    </div>
  </div>
</div>

<div class="card">
<h2>Key Competitive Moats</h2>
<div class="moat">
  <div class="metric"><div class="val">9.6×</div><div class="label">Cost Advantage vs PI/Figure</div></div>
  <div class="metric"><div class="val">US</div><div class="label">Origin Moat (Fed/DoD eligible)</div></div>
  <div class="metric"><div class="val">3yr</div><div class="label">NVIDIA Partnership Runway</div></div>
  <div class="metric"><div class="val">#1</div><div class="label">Cloud Integration Score</div></div>
  <div class="metric"><div class="val">OCI</div><div class="label">Hyperscaler Backing</div></div>
  <div class="metric"><div class="val">Apr</div><div class="label">GR00T N1.6 GA Target</div></div>
</div>
</div>

<div class="card">
<h2>Dimension Scorecard</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<tr style="border-bottom:1px solid #334155;color:#94a3b8">
  <th style="text-align:left;padding:8px">Competitor</th>
  {''.join(f'<th style="text-align:right;padding:8px">{d[:8]}</th>' for d in DIMENSIONS)}
  <th style="text-align:right;padding:8px">Avg</th>
</tr>
{metrics_rows}
</table>
</div>

<div class="card" style="border-left:3px solid #C74634">
<strong style="color:#C74634">Strategic Summary:</strong>
OCI Robot Cloud leads on cost efficiency (9.6× advantage), cloud integration, and NVIDIA partnership depth.
US-origin moat blocks Physical Intelligence and Figure AI from federal/DoD markets.
Projected 3-year runway before competitive catch-up on model quality.
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Competitive Landscape Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "service": "competitive_landscape_tracker",
                          "cost_advantage": "9.6x", "us_origin_moat": True, "nvidia_runway_years": 3}

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
