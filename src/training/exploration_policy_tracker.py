"""
exploration_policy_tracker.py — port 8648
OCI Robot Cloud | cycle-147B
Tracks DAgger beta decay, state coverage growth, and exploration bonus.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_dagger_beta_decay() -> str:
    """DAgger beta decay S-curve, expert vs autonomous fractions shaded."""
    W, H = 520, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45

    def ex(ep):  # episode 0-400 → pixel x
        return pad_l + (ep / 400) * (W - pad_l - pad_r)

    def ey(beta):  # beta 0-1 → pixel y
        return pad_t + (1 - beta) * (H - pad_t - pad_b)

    # Sigmoid-style decay: beta(ep) = 0.18 + 0.77 / (1 + exp((ep-120)/40))
    eps = list(range(0, 401, 5))
    betas = [0.18 + 0.77 / (1 + math.exp((e - 120) / 40)) for e in eps]

    curve_pts = " ".join(f"{ex(e):.1f},{ey(b):.1f}" for e, b in zip(eps, betas))

    # Expert fraction area (above curve → y < curve y → blue fill down from top)
    expert_poly = (
        f"{ex(0):.1f},{pad_t} "
        + " ".join(f"{ex(e):.1f},{ey(b):.1f}" for e, b in zip(eps, betas))
        + f" {ex(400):.1f},{pad_t}"
    )

    # Autonomous fraction area (below curve → orange fill down to bottom)
    auto_poly = (
        " ".join(f"{ex(e):.1f},{ey(b):.1f}" for e, b in zip(eps, betas))
        + f" {ex(400):.1f},{H - pad_b} {ex(0):.1f},{H - pad_b}"
    )

    # Y-axis ticks
    y_ticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        yp = ey(v)
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{pad_l - 8}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end">{v:.1f}</text>'
        )
    # X-axis ticks
    x_ticks = ""
    for ep in [0, 100, 200, 300, 400]:
        xp = ex(ep)
        x_ticks += (
            f'<line x1="{xp:.1f}" y1="{H - pad_b}" x2="{xp:.1f}" y2="{H - pad_b + 4}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{H - pad_b + 16}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">{ep}</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <defs>
    <clipPath id="clip-beta">
      <rect x="{pad_l}" y="{pad_t}" width="{W-pad_l-pad_r}" height="{H-pad_t-pad_b}"/>
    </clipPath>
  </defs>
  <!-- axes -->
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  {y_ticks}
  {x_ticks}
  <!-- expert fraction (blue) -->
  <polygon points="{expert_poly}" fill="#38bdf8" fill-opacity="0.25" clip-path="url(#clip-beta)"/>
  <!-- autonomous fraction (orange) -->
  <polygon points="{auto_poly}" fill="#fb923c" fill-opacity="0.25" clip-path="url(#clip-beta)"/>
  <!-- beta curve -->
  <polyline points="{curve_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"
    clip-path="url(#clip-beta)"/>
  <!-- labels -->
  <text x="{ex(40):.1f}" y="{ey(0.88):.1f}" fill="#38bdf8" font-size="11" font-weight="600">Expert</text>
  <text x="{ex(240):.1f}" y="{ey(0.05):.1f}" fill="#fb923c" font-size="11" font-weight="600">Autonomous</text>
  <!-- axis labels -->
  <text x="{(pad_l + W - pad_r)//2}" y="{H}" fill="#94a3b8" font-size="12" text-anchor="middle">Episode</text>
  <text x="12" y="{(pad_t + H - pad_b)//2}" fill="#94a3b8" font-size="12" text-anchor="middle"
    transform="rotate(-90,12,{(pad_t + H - pad_b)//2})">Beta (β)</text>
  <text x="{(pad_l + W - pad_r)//2}" y="14" fill="#e2e8f0" font-size="13" font-weight="600"
    text-anchor="middle">DAgger β Decay</text>
</svg>"""


def svg_state_coverage() -> str:
    """State coverage growth — logarithmic saturation at 84% after round 6."""
    W, H = 520, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45

    rounds = list(range(1, 11))
    # log saturation: coverage(r) = 84 * (1 - exp(-0.55*(r-1)))
    coverages = [min(84.0, 84.0 * (1 - math.exp(-0.55 * (r - 1)))) for r in rounds]

    def px(r):
        return pad_l + ((r - 1) / 9) * (W - pad_l - pad_r)

    def py(c):
        return pad_t + (1 - c / 100) * (H - pad_t - pad_b)

    pts = " ".join(f"{px(r):.1f},{py(c):.1f}" for r, c in zip(rounds, coverages))
    area = (
        f"{px(1):.1f},{H - pad_b} "
        + pts
        + f" {px(10):.1f},{H - pad_b}"
    )

    y_ticks = ""
    for v in [0, 20, 40, 60, 80, 100]:
        yp = py(v)
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{pad_l - 8}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end">{v}%</text>'
        )
    x_ticks = ""
    for r in rounds:
        xp = px(r)
        x_ticks += (
            f'<line x1="{xp:.1f}" y1="{H - pad_b}" x2="{xp:.1f}" y2="{H - pad_b + 4}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{H - pad_b + 16}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">{r}</text>'
        )

    # Plateau annotation at round 6
    x6 = px(6)
    y84 = py(84)

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <defs>
    <clipPath id="clip-cov">
      <rect x="{pad_l}" y="{pad_t}" width="{W-pad_l-pad_r}" height="{H-pad_t-pad_b}"/>
    </clipPath>
  </defs>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  {y_ticks}
  {x_ticks}
  <!-- area fill -->
  <polygon points="{area}" fill="#C74634" fill-opacity="0.20" clip-path="url(#clip-cov)"/>
  <!-- curve -->
  <polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2.5"
    clip-path="url(#clip-cov)"/>
  <!-- plateau marker -->
  <line x1="{x6:.1f}" y1="{y84:.1f}" x2="{W - pad_r}" y2="{y84:.1f}"
    stroke="#facc15" stroke-width="1.2" stroke-dasharray="4,3" clip-path="url(#clip-cov)"/>
  <circle cx="{x6:.1f}" cy="{y84:.1f}" r="5" fill="#facc15"/>
  <text x="{x6 + 8:.1f}" y="{y84 - 6:.1f}" fill="#facc15" font-size="11">84% plateau</text>
  <!-- axis labels -->
  <text x="{(pad_l + W - pad_r)//2}" y="{H}" fill="#94a3b8" font-size="12" text-anchor="middle">Round</text>
  <text x="12" y="{(pad_t + H - pad_b)//2}" fill="#94a3b8" font-size="12" text-anchor="middle"
    transform="rotate(-90,12,{(pad_t + H - pad_b)//2})">Coverage (%)</text>
  <text x="{(pad_l + W - pad_r)//2}" y="14" fill="#e2e8f0" font-size="13" font-weight="600"
    text-anchor="middle">State Coverage Growth</text>
</svg>"""


def svg_exploration_bonus() -> str:
    """Intrinsic exploration reward — peaks at contact-rich phases."""
    W, H = 520, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45

    def ex(ep):
        return pad_l + (ep / 400) * (W - pad_l - pad_r)

    def ey(val, vmax=1.0):
        return pad_t + (1 - val / vmax) * (H - pad_t - pad_b)

    # Two contact-rich peaks at ep≈80 and ep≈220, decaying novelty
    def bonus(ep):
        b = 0.08 * math.exp(-ep / 300)  # baseline novelty decay
        b += 0.72 * math.exp(-((ep - 80) ** 2) / (2 * 35 ** 2))   # peak 1
        b += 0.55 * math.exp(-((ep - 220) ** 2) / (2 * 30 ** 2))  # peak 2
        return min(b, 1.0)

    eps = list(range(0, 401, 4))
    vals = [bonus(e) for e in eps]
    pts = " ".join(f"{ex(e):.1f},{ey(v):.1f}" for e, v in zip(eps, vals))
    area = f"{ex(0):.1f},{H - pad_b} " + pts + f" {ex(400):.1f},{H - pad_b}"

    y_ticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        yp = ey(v)
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{pad_l - 8}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="end">{v:.1f}</text>'
        )
    x_ticks = ""
    for ep in [0, 100, 200, 300, 400]:
        xp = ex(ep)
        x_ticks += (
            f'<line x1="{xp:.1f}" y1="{H - pad_b}" x2="{xp:.1f}" y2="{H - pad_b + 4}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{H - pad_b + 16}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">{ep}</text>'
        )

    p1x, p1y = ex(80), ey(bonus(80))
    p2x, p2y = ex(220), ey(bonus(220))

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <defs>
    <clipPath id="clip-bonus">
      <rect x="{pad_l}" y="{pad_t}" width="{W-pad_l-pad_r}" height="{H-pad_t-pad_b}"/>
    </clipPath>
  </defs>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  {y_ticks}
  {x_ticks}
  <polygon points="{area}" fill="#a855f7" fill-opacity="0.22" clip-path="url(#clip-bonus)"/>
  <polyline points="{pts}" fill="none" stroke="#a855f7" stroke-width="2.5"
    clip-path="url(#clip-bonus)"/>
  <!-- peak annotations -->
  <circle cx="{p1x:.1f}" cy="{p1y:.1f}" r="5" fill="#f472b6"/>
  <text x="{p1x - 4:.1f}" y="{p1y - 9:.1f}" fill="#f472b6" font-size="10" text-anchor="middle">grasp</text>
  <circle cx="{p2x:.1f}" cy="{p2y:.1f}" r="5" fill="#f472b6"/>
  <text x="{p2x:.1f}" y="{p2y - 9:.1f}" fill="#f472b6" font-size="10" text-anchor="middle">insert</text>
  <!-- axis labels -->
  <text x="{(pad_l + W - pad_r)//2}" y="{H}" fill="#94a3b8" font-size="12" text-anchor="middle">Episode</text>
  <text x="12" y="{(pad_t + H - pad_b)//2}" fill="#94a3b8" font-size="12" text-anchor="middle"
    transform="rotate(-90,12,{(pad_t + H - pad_b)//2})">Intrinsic Reward</text>
  <text x="{(pad_l + W - pad_r)//2}" y="14" fill="#e2e8f0" font-size="13" font-weight="600"
    text-anchor="middle">Exploration Bonus</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_dagger_beta_decay()
    svg2 = svg_state_coverage()
    svg3 = svg_exploration_bonus()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Exploration Policy Tracker — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;padding:24px}}
  h1{{color:#38bdf8;font-size:1.6rem;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#94a3b8;font-size:.875rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px;margin-bottom:28px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}}
  .card h2{{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:14px}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
  .metric{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}}
  .metric .label{{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .metric .value{{color:#C74634;font-size:1.4rem;font-weight:700}}
  .metric .sub{{color:#64748b;font-size:.75rem;margin-top:4px}}
  footer{{color:#475569;font-size:.75rem;margin-top:28px;text-align:center}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:.7rem;font-weight:700;
          padding:2px 8px;border-radius:999px;margin-left:8px;vertical-align:middle}}
</style>
</head>
<body>
<h1>Exploration Policy Tracker <span class="badge">Port 8648</span></h1>
<p class="subtitle">OCI Robot Cloud · DAgger Beta Decay · State Coverage · Intrinsic Bonus</p>

<div class="grid">
  <div class="card"><h2>DAgger β Decay</h2>{svg1}</div>
  <div class="card"><h2>State Coverage Growth</h2>{svg2}</div>
  <div class="card"><h2>Exploration Bonus</h2>{svg3}</div>
</div>

<div class="metrics">
  <div class="metric">
    <div class="label">β at Episode 0</div>
    <div class="value">0.95</div>
    <div class="sub">Expert-dominated rollout</div>
  </div>
  <div class="metric">
    <div class="label">β at Episode 400</div>
    <div class="value">0.18</div>
    <div class="sub">Autonomous SR 0.68</div>
  </div>
  <div class="metric">
    <div class="label">Coverage Plateau</div>
    <div class="value">84%</div>
    <div class="sub">Unique states · round 6</div>
  </div>
  <div class="metric">
    <div class="label">Contact Bonus Peaks</div>
    <div class="value">2</div>
    <div class="sub">Grasp ep≈80 · Insert ep≈220</div>
  </div>
  <div class="metric">
    <div class="label">Autonomous SR (β=0.18)</div>
    <div class="value">68%</div>
    <div class="sub">Success rate at final beta</div>
  </div>
  <div class="metric">
    <div class="label">Coverage Rounds</div>
    <div class="value">10</div>
    <div class="sub">DAgger data collection rounds</div>
  </div>
</div>

<footer>OCI Robot Cloud · cycle-147B · exploration_policy_tracker · port 8648</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Exploration Policy Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "exploration_policy_tracker", "port": 8648})

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8648)

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "exploration_policy_tracker", "port": 8648}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8648), Handler)
        print("Serving on port 8648")
        server.serve_forever()
