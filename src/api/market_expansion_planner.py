# Market Expansion Planner — port 8941
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

if USE_FASTAPI:
    app = FastAPI(title="Market Expansion Planner")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=build_html())

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)
        def log_message(self, *a):
            pass


# ── Market data ─────────────────────────────────────────────────────────────
RINGS = [
    {"label": "Robotics Startups",    "tam_m": 180,  "color": "#C74634", "r_frac": 0.28},
    {"label": "Tier-2 Integrators",   "tam_m": 840,  "color": "#38bdf8", "r_frac": 0.55},
    {"label": "Enterprise OEMs",       "tam_m": 4200, "color": "#4ade80", "r_frac": 0.82},
]

EXPANSION_TIMELINE = [
    {"year": 2026, "regions": ["US"],         "milestone": "GA launch, 20 design partners"},
    {"year": 2027, "regions": ["JP", "DE"],   "milestone": "$10M ARR, ISO 10218 cert"},
    {"year": 2028, "regions": ["Global"],     "milestone": "$50M ARR, 5 OEM integrations"},
]

TRIGGERS = [
    {"metric": "Monthly Active Robots",  "threshold": "500",   "action": "Expand to next geo tier"},
    {"metric": "Avg SR (closed-loop)",   "threshold": "80%",   "action": "Unlock OEM tier pricing"},
    {"metric": "Churn Rate",             "threshold": "< 5%",  "action": "Raise Series B"},
    {"metric": "Data Flywheel Demos/wk", "threshold": "10 000", "action": "Launch self-serve portal"},
    {"metric": "NPS",                   "threshold": "≥ 55",  "action": "Accelerate partner program"},
]


def _tam_ring_svg() -> str:
    """Concentric ring diagram showing TAM layers."""
    W = H = 320
    cx = cy = 160
    max_r = 130

    parts = []
    # Draw rings from outermost to innermost
    for ring in reversed(RINGS):
        r = round(max_r * ring["r_frac"])
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ring["color"]}" fill-opacity="0.18" '
            f'stroke="{ring["color"]}" stroke-width="2"/>'
        )
        # Label on right side of ring
        angle = math.radians(-30)
        lx = round(cx + r * math.cos(angle))
        ly = round(cy + r * math.sin(angle))
        tam_b = ring["tam_m"]
        tam_str = f"${tam_b}M" if tam_b < 1000 else f"${tam_b//1000:.1f}B"
        parts.append(
            f'<text x="{lx+6}" y="{ly}" fill="{ring["color"]}" font-size="11" font-weight="600">{ring["label"]}</text>'
        )
        parts.append(
            f'<text x="{lx+6}" y="{ly+14}" fill="{ring["color"]}" font-size="10" fill-opacity="0.8">{tam_str} TAM</text>'
        )

    # Center label
    parts.append(f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">OCI Robot</text>')
    parts.append(f'<text x="{cx}" y="{cy+8}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">Cloud</text>')
    parts.append(f'<text x="{cx}" y="{cy+24}" text-anchor="middle" fill="#64748b" font-size="10">$5.22B Total</text>')

    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">{chr(10).join(parts)}</svg>'


def _timeline_svg() -> str:
    """SVG horizontal timeline for geographic expansion."""
    W, H = 520, 130
    years = [e["year"] for e in EXPANSION_TIMELINE]
    n = len(years)
    x0 = 60
    xn = W - 40
    y  = 50
    seg_w = (xn - x0) / (n - 1)

    parts = []
    # spine
    parts.append(f'<line x1="{x0}" y1="{y}" x2="{xn}" y2="{y}" stroke="#334155" stroke-width="2"/>')

    colors = ["#C74634", "#38bdf8", "#4ade80"]
    for i, ev in enumerate(EXPANSION_TIMELINE):
        x = round(x0 + i * seg_w)
        c = colors[i % len(colors)]
        parts.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{c}" fill-opacity="0.25" stroke="{c}" stroke-width="2"/>')
        region_str = " / ".join(ev["regions"])
        parts.append(f'<text x="{x}" y="{y - 18}" text-anchor="middle" fill="{c}" font-size="13" font-weight="700">{ev["year"]}</text>')
        parts.append(f'<text x="{x}" y="{y + 22}" text-anchor="middle" fill="#94a3b8" font-size="11">{region_str}</text>')
        # milestone below
        parts.append(f'<text x="{x}" y="{y + 38}" text-anchor="middle" fill="#64748b" font-size="9.5">{ev["milestone"]}</text>')

    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">{chr(10).join(parts)}</svg>'


def build_html() -> str:
    ring_svg     = _tam_ring_svg()
    timeline_svg = _timeline_svg()

    trigger_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#e2e8f0">{t["metric"]}</td>'
        f'<td style="padding:6px 12px;color:#C74634;text-align:center;font-weight:600">{t["threshold"]}</td>'
        f'<td style="padding:6px 12px;color:#94a3b8">{t["action"]}</td></tr>'
        for t in TRIGGERS
    )

    total_tam = sum(r["tam_m"] for r in RINGS)
    total_tam_str = f"${total_tam/1000:.2f}B"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Market Expansion Planner</title>
<style>
  body{{margin:0;background:#0f172a;font-family:'Segoe UI',sans-serif;color:#e2e8f0}}
  h1{{color:#C74634;margin:0 0 4px}}
  h2{{color:#38bdf8;font-size:1rem;margin:24px 0 8px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
  .stat{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#C74634}}
  .stat .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
  table{{border-collapse:collapse;width:100%}}
  th{{color:#64748b;font-size:.75rem;text-align:left;padding:6px 12px;border-bottom:1px solid #334155}}
  tr:hover td{{background:#273548}}
  .wrap{{max-width:820px;margin:0 auto;padding:28px 20px}}
  .badge{{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:4px;padding:2px 8px;font-size:.7rem;color:#94a3b8;margin-left:8px}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>Market Expansion Planner <span class="badge">port 8941</span></h1>
  <p style="color:#64748b;margin-top:0">Robotics startups → Tier-2 integrators → Enterprise OEMs · US 2026 → JP/DE 2027 → Global 2028</p>

  <div class="stat-grid">
    <div class="stat"><div class="val">$180M</div><div class="lbl">Robotics Startups TAM</div></div>
    <div class="stat"><div class="val">$840M</div><div class="lbl">Tier-2 Integrators TAM</div></div>
    <div class="stat"><div class="val">$4.2B</div><div class="lbl">Enterprise OEMs TAM</div></div>
    <div class="stat"><div class="val">{total_tam_str}</div><div class="lbl">Combined TAM</div></div>
  </div>

  <div class="two-col">
    <div class="card">
      <h2>TAM Ring Diagram</h2>
      {ring_svg}
    </div>
    <div class="card">
      <h2>Geographic Expansion Timeline</h2>
      {timeline_svg}
      <table style="margin-top:16px">
        <thead><tr><th>Year</th><th>Regions</th><th>Milestone</th></tr></thead>
        <tbody>
        {''.join(f'<tr><td style="padding:6px 12px;color:#C74634;font-weight:600">{e["year"]}</td><td style="padding:6px 12px;color:#38bdf8">{" / ".join(e["regions"])}</td><td style="padding:6px 12px;color:#94a3b8">{e["milestone"]}</td></tr>' for e in EXPANSION_TIMELINE)}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>Expansion Trigger Thresholds</h2>
    <table>
      <thead><tr><th>Metric</th><th>Threshold</th><th>Action Unlocked</th></tr></thead>
      <tbody>{trigger_rows}</tbody>
    </table>
  </div>

  <div class="card" style="font-size:.8rem;color:#64748b">
    <b style="color:#94a3b8">Strategy:</b> Land with high-velocity robotics startups (fastest feedback loop), expand to
    Tier-2 integrators (volume), then close Enterprise OEM contracts (ACV).
    Each ring unlocks the next via reference customers and certified integrations.
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8941)
    else:
        print("FastAPI not found — starting fallback HTTPServer on :8941")
        HTTPServer(("0.0.0.0", 8941), Handler).serve_forever()
