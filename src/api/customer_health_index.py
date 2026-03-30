"""Customer Health Index — port 8967

6-dimension composite health score per partner:
  product_adoption | support | outcomes | relationship | financial | strategic

Scores (0-100):
  PI: 87  |  Covariant: 79  |  Machina: 63  |  1X: 41  |  Apptronik: 58

30-day trend: 1X declining.
"""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8967
TITLE = "Customer Health Index"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

DIMENSIONS = [
    "product_adoption",
    "support",
    "outcomes",
    "relationship",
    "financial",
    "strategic",
]

# Per-partner dimension scores (0-100)
PARTNER_DATA = {
    "PI":         [92, 88, 90, 85, 84, 83],
    "Covariant":  [82, 76, 80, 79, 77, 80],
    "Machina":    [65, 60, 63, 66, 62, 63],
    "1X":         [38, 42, 40, 45, 38, 43],
    "Apptronik":  [60, 55, 58, 62, 57, 56],
}

# Composite = mean of dimension scores
def composite(scores):
    return round(sum(scores) / len(scores), 1)

# 30-day trend sparkline data (last 30 days, sampled every 5 days → 7 points)
# Trend seed per partner so lines look plausible
RANDOM_SEED = 42

def trend_points(partner, base, declining=False):
    rng = random.Random(RANDOM_SEED + hash(partner) % 100)
    pts = [base]
    for _ in range(6):
        delta = rng.uniform(-3, 2) if not declining else rng.uniform(-5, 0.5)
        pts.append(max(0, min(100, pts[-1] + delta)))
    return [round(p, 1) for p in pts]

TREND_DATA = {
    p: trend_points(p, composite(PARTNER_DATA[p]), declining=(p == "1X"))
    for p in PARTNER_DATA
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def radar_svg(partner: str, scores: list, size: int = 220) -> str:
    """Hexagonal radar chart for 6 dimensions."""
    n = len(scores)
    cx, cy = size // 2, size // 2
    r_max = size // 2 - 30
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def pt(val, ang):
        r = r_max * val / 100
        return cx + r * math.cos(ang), cy - r * math.sin(ang)

    # Background rings
    rings = ""
    for pct in [25, 50, 75, 100]:
        pts = " ".join(f"{pt(pct, a)[0]:.1f},{pt(pct, a)[1]:.1f}" for a in angles)
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'

    # Axis lines
    axes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{pt(100, a)[0]:.1f}" y2="{pt(100, a)[1]:.1f}" '
        f'stroke="#334155" stroke-width="1"/>'
        for a in angles
    )

    # Data polygon
    data_pts = " ".join(f"{pt(s, a)[0]:.1f},{pt(s, a)[1]:.1f}" for s, a in zip(scores, angles))
    poly = (
        f'<polygon points="{data_pts}" fill="#C74634" fill-opacity="0.25" '
        f'stroke="#C74634" stroke-width="2"/>'
    )

    # Dimension labels (short)
    short_labels = ["Adopt", "Support", "Outcomes", "Relation", "Financial", "Strategic"]
    labels = ""
    for i, (s, a, lbl) in enumerate(zip(scores, angles, short_labels)):
        lx, ly = pt(115, a)
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="9" font-family="sans-serif">{lbl}</text>'
        )

    comp = composite(scores)
    center_label = (
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="#38bdf8" '
        f'font-size="18" font-family="monospace" font-weight="bold">{comp}</text>'
    )

    return (
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:{size}px;height:{size}px">'
        + rings + axes + poly + labels + center_label
        + f'<text x="{cx}" y="18" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="12" font-family="sans-serif" font-weight="600">{partner}</text>'
        + "</svg>"
    )


def sparkline_svg(pts: list, width=180, height=50, color="#38bdf8", declining=False) -> str:
    """Mini line sparkline."""
    if declining:
        color = "#f87171"
    min_v, max_v = min(pts), max(pts)
    rng = max_v - min_v or 1
    x_step = width / (len(pts) - 1)
    coords = [
        (round(i * x_step, 1), round(height - (p - min_v) / rng * (height - 4) - 2, 1))
        for i, p in enumerate(pts)
    ]
    polyline = " ".join(f"{x},{y}" for x, y in coords)
    last_x, last_y = coords[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:{width}px;height:{height}px">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="3" fill="{color}"/>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def health_color(score):
    if score >= 80: return "#4ade80"
    if score >= 65: return "#38bdf8"
    if score >= 50: return "#fbbf24"
    return "#f87171"


def build_html() -> str:
    # Radar cards
    radar_cards = ""
    for partner, scores in PARTNER_DATA.items():
        comp = composite(scores)
        hc = health_color(comp)
        declining = partner == "1X"
        spark = sparkline_svg(TREND_DATA[partner], declining=declining)
        radar_cards += (
            f'<div class="card" style="text-align:center">'
            f'{radar_svg(partner, scores)}'
            f'<p style="color:{hc};font-size:1.4rem;font-weight:700;margin:4px 0 0">'
            f'{comp}</p>'
            f'<p style="color:#64748b;font-size:0.75rem;margin-bottom:8px">composite</p>'
            f'<p style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px">30-day trend</p>'
            f'{spark}'
            + (f'<p style="color:#f87171;font-size:0.7rem;margin-top:4px">declining</p>' if declining else '')
            + '</div>'
        )

    # Summary table
    rows = ""
    for partner, scores in PARTNER_DATA.items():
        comp = composite(scores)
        hc = health_color(comp)
        dim_cells = "".join(
            f'<td style="padding:6px 10px;color:{health_color(s)};font-family:monospace">{s}</td>'
            for s in scores
        )
        rows += (
            f'<tr>'
            f'<td style="padding:6px 10px;color:#e2e8f0;font-weight:600">{partner}</td>'
            f'<td style="padding:6px 10px;color:{hc};font-family:monospace;font-weight:700">{comp}</td>'
            + dim_cells
            + '</tr>'
        )

    table = (
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
        '<thead><tr>'
        + "".join(
            f'<th style="padding:6px 10px;text-align:left;color:#C74634;'
            f'border-bottom:1px solid #334155">{h}</th>'
            for h in ["Partner", "Composite"] + [d.replace("_", " ").title() for d in DIMENSIONS]
        )
        + '</tr></thead><tbody>' + rows + '</tbody></table>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{TITLE}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:32px}}
    h1{{color:#C74634;font-size:2rem;margin-bottom:4px}}
    h2{{color:#38bdf8;font-size:1.2rem;margin:28px 0 12px}}
    .meta{{color:#64748b;font-size:0.85rem;margin-bottom:32px}}
    .card{{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:24px}}
    .radars{{display:flex;flex-wrap:wrap;gap:20px;justify-content:flex-start}}
    .radars .card{{min-width:240px;flex:0 0 auto}}
    .kpi-row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px}}
    .kpi{{background:#1e293b;border-radius:10px;padding:20px 28px;min-width:140px}}
    .kpi .val{{font-size:1.8rem;font-weight:700;font-family:monospace}}
    .kpi .lbl{{font-size:0.78rem;color:#64748b;margin-top:4px}}
  </style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="meta">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp;
    6-dimension composite health &nbsp;|&nbsp; 30-day rolling</p>

  <!-- KPIs -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="val" style="color:#4ade80">87</div>
      <div class="lbl">PI (highest)</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#f87171">41</div>
      <div class="lbl">1X (at-risk)</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#fbbf24">65.6</div>
      <div class="lbl">portfolio avg</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#f87171">1</div>
      <div class="lbl">declining partner</div>
    </div>
  </div>

  <!-- Radar charts -->
  <h2>Health Radar — per Partner</h2>
  <div class="radars">
    {radar_cards}
  </div>

  <!-- Dimension breakdown table -->
  <div class="card">
    <h2>Dimension Scores Breakdown</h2>
    {table}
  </div>

  <!-- Insight -->
  <div class="card">
    <h2>Insights &amp; Recommended Actions</h2>
    <ul style="color:#94a3b8;line-height:2;padding-left:20px;font-size:0.88rem">
      <li><strong style="color:#f87171">1X</strong> score 41 and declining — schedule EBR within 14 days;
        focus on financial (38) and product adoption (38).</li>
      <li><strong style="color:#fbbf24">Machina</strong> score 63 — marginal; outcomes (63) and
        support (60) need improvement. Assign dedicated CSM.</li>
      <li><strong style="color:#4ade80">PI</strong> score 87 — prime expansion candidate;
        upsell multi-GPU tier and co-market opportunity.</li>
      <li><strong style="color:#38bdf8">Covariant</strong> score 79 — healthy; monitor support
        dimension (76) to prevent decay.</li>
      <li><strong style="color:#fbbf24">Apptronik</strong> score 58 — support (55) is lowest dimension;
        consider proactive onboarding refresh.</li>
    </ul>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_): pass

    if __name__ == "__main__":
        print(f"{TITLE} (stdlib fallback) on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
