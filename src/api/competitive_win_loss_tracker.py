# Competitive Win/Loss Tracker — port 8925
# 12 competitive deals: 8 wins / 4 losses (67% win rate)

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

APP_TITLE = "Competitive Win/Loss Tracker"
PORT = 8925

# ── Data ──────────────────────────────────────────────────────────────────────

DEALS = [
    {"id": 1,  "customer": "AutoDrive Corp",      "outcome": "win",  "value": 420000, "driver": "NVIDIA stack",        "quarter": "Q1-2026"},
    {"id": 2,  "customer": "RoboFlex Inc",         "outcome": "win",  "value": 310000, "driver": "Cost advantage",      "quarter": "Q1-2026"},
    {"id": 3,  "customer": "PrecisionArm Ltd",     "outcome": "loss", "value": 280000, "reason": "Price",              "quarter": "Q1-2026"},
    {"id": 4,  "customer": "AgilBot Systems",      "outcome": "win",  "value": 500000, "driver": "NVIDIA stack",        "quarter": "Q1-2026"},
    {"id": 5,  "customer": "SmartGrip AI",         "outcome": "loss", "value": 195000, "reason": "No enterprise contract","quarter": "Q2-2026"},
    {"id": 6,  "customer": "NovaMech Robotics",    "outcome": "win",  "value": 375000, "driver": "OCI reliability",     "quarter": "Q2-2026"},
    {"id": 7,  "customer": "BioRobot Labs",        "outcome": "loss", "value": 220000, "reason": "AWS",                 "quarter": "Q2-2026"},
    {"id": 8,  "customer": "TerraBot Inc",         "outcome": "win",  "value": 460000, "driver": "Cost advantage",      "quarter": "Q2-2026"},
    {"id": 9,  "customer": "VisionArm Co",         "outcome": "win",  "value": 290000, "driver": "NVIDIA stack",        "quarter": "Q3-2026"},
    {"id": 10, "customer": "HexaDrive Systems",    "outcome": "loss", "value": 340000, "reason": "No enterprise contract","quarter": "Q3-2026"},
    {"id": 11, "customer": "ClearPath Robotics",   "outcome": "win",  "value": 530000, "driver": "Support & SLA",       "quarter": "Q3-2026"},
    {"id": 12, "customer": "DeltaBot AI",          "outcome": "win",  "value": 410000, "driver": "Cost advantage",      "quarter": "Q3-2026"},
]

WINS   = [d for d in DEALS if d["outcome"] == "win"]
LOSSES = [d for d in DEALS if d["outcome"] == "loss"]
WIN_VALUE   = sum(d["value"] for d in WINS)
LOSS_VALUE  = sum(d["value"] for d in LOSSES)
TOTAL_VALUE = WIN_VALUE + LOSS_VALUE

LOSS_REASONS = {"No enterprise contract": 2, "Price": 1, "AWS": 1}  # 25%/25%/17% (rounded)
WIN_DRIVERS  = {"NVIDIA stack": 3, "Cost advantage": 3, "OCI reliability": 1, "Support & SLA": 1}

# SVG helpers
def _bar_chart(labels, values, colors, W=520, H=200, pad=40, title=""):
    max_v = max(values) or 1
    n = len(labels)
    slot = (W - 2*pad) / n
    bar_w = slot * 0.55
    bars = ""
    for i, (lbl, v, c) in enumerate(zip(labels, values, colors)):
        x = pad + i*slot + (slot - bar_w)/2
        bh = (v / max_v) * (H - 2*pad - 20)
        y  = H - pad - bh
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" rx="3"/>'
        bars += f'<text x="{x+bar_w/2:.1f}" y="{y-4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="9" font-family="monospace">{v}</text>'
        bars += f'<text x="{x+bar_w/2:.1f}" y="{H-pad+12:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{lbl}</text>'
    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px"><text x="{W//2}" y="14" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{title}</text>{bars}</svg>'

def build_loss_svg():
    reasons = list(LOSS_REASONS.keys())
    counts  = [LOSS_REASONS[r] for r in reasons]
    colors  = ["#C74634", "#f87171", "#fca5a5"]
    return _bar_chart(reasons, counts, colors, title="Loss Reasons (Pareto)")

def build_win_svg():
    drivers = list(WIN_DRIVERS.keys())
    counts  = [WIN_DRIVERS[d] for d in drivers]
    colors  = ["#38bdf8", "#38bdf8", "#7dd3fc", "#bae6fd"]
    return _bar_chart(drivers, counts, colors, title="Win Drivers (Pareto)")

def build_pipeline_svg():
    """Quarterly pipeline value bars — wins vs losses."""
    quarters = ["Q1-2026", "Q2-2026", "Q3-2026"]
    win_vals  = [sum(d["value"] for d in WINS   if d["quarter"]==q) for q in quarters]
    loss_vals = [sum(d["value"] for d in LOSSES if d["quarter"]==q) for q in quarters]
    W, H, PAD = 540, 210, 40
    max_v = max(max(win_vals), max(loss_vals)) or 1
    slot  = (W - 2*PAD) / len(quarters)
    bar_w = slot * 0.3
    svg   = f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">'
    svg  += f'<text x="{W//2}" y="14" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Pipeline Value by Quarter ($)</text>'
    for i, q in enumerate(quarters):
        cx = PAD + i*slot + slot/2
        for j, (v, c) in enumerate([(win_vals[i], "#38bdf8"), (loss_vals[i], "#C74634")]):
            x  = cx - bar_w + j*(bar_w+2)
            bh = (v / max_v) * (H - 2*PAD - 20)
            y  = H - PAD - bh
            svg += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" rx="3"/>'
            svg += f'<text x="{x+bar_w/2:.1f}" y="{y-4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="8" font-family="monospace">${v//1000}k</text>'
        svg += f'<text x="{cx:.1f}" y="{H-PAD+14:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{q}</text>'
    svg += '</svg>'
    return svg

def html_page():
    loss_svg     = build_loss_svg()
    win_svg      = build_win_svg()
    pipeline_svg = build_pipeline_svg()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{APP_TITLE}</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif}}
  h1{{color:#C74634;margin:0 0 4px}}
  h2{{color:#38bdf8;font-size:1rem;margin:20px 0 8px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
  .kpi{{background:#1e293b;border-radius:8px;padding:16px;text-align:center}}
  .kpi .val{{font-size:2rem;font-weight:700}}
  .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:4px}}
  .charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  table{{width:100%;border-collapse:collapse;font-size:.83rem}}
  th{{text-align:left;color:#94a3b8;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
  .win{{color:#4ade80}}.loss{{color:#C74634}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.72rem}}
  .bw{{background:#4ade8020;color:#4ade80}}.bl{{background:#C7463420;color:#C74634}}
</style>
</head>
<body>
<h1>{APP_TITLE}</h1>
<p style="color:#94a3b8;margin:0 0 20px">12 competitive deals tracked — OCI Robot Cloud vs AWS / Azure / GCP</p>

<div class="grid">
  <div class="kpi"><div class="val" style="color:#4ade80">8</div><div class="lbl">Wins</div></div>
  <div class="kpi"><div class="val" style="color:#C74634">4</div><div class="lbl">Losses</div></div>
  <div class="kpi"><div class="val" style="color:#38bdf8">67%</div><div class="lbl">Win Rate</div></div>
  <div class="kpi"><div class="val" style="color:#4ade80">${WIN_VALUE//1000}k</div><div class="lbl">Won Pipeline</div></div>
  <div class="kpi"><div class="val" style="color:#C74634">${LOSS_VALUE//1000}k</div><div class="lbl">Lost Pipeline</div></div>
  <div class="kpi"><div class="val" style="color:#fbbf24">${TOTAL_VALUE//1000}k</div><div class="lbl">Total Pipeline</div></div>
</div>

<div class="card">
  <h2>Loss Reasons &amp; Win Drivers (Pareto)</h2>
  <div class="charts">
    {loss_svg}
    {win_svg}
  </div>
  <p style="color:#94a3b8;font-size:.8rem;margin-top:12px">
    Loss breakdown: No enterprise contract 25% · Price 25% · AWS 17% · Other 33%<br>
    Top win drivers: NVIDIA stack 40% · Cost advantage 30% · OCI reliability + Support 30%
  </p>
</div>

<div class="card">
  <h2>Pipeline Value by Quarter</h2>
  {pipeline_svg}
</div>

<div class="card">
  <h2>All Deals</h2>
  <table>
    <tr><th>#</th><th>Customer</th><th>Outcome</th><th>Value</th><th>Key Factor</th><th>Quarter</th></tr>
    {''.join(
      f'<tr><td>{d["id"]}</td><td>{d["customer"]}</td>'
      f'<td><span class="badge {"bw" if d["outcome"]=="win" else "bl"}">{d["outcome"].upper()}</span></td>'
      f'<td>${d["value"]:,}</td>'
      f'<td>{d.get("driver", d.get("reason","-"))}</td>'
      f'<td>{d["quarter"]}</td></tr>'
      for d in DEALS
    )}
  </table>
</div>

<p style="color:#475569;font-size:.75rem;margin-top:24px">OCI Robot Cloud · {APP_TITLE} · port {PORT}</p>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title=APP_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(html_page())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": APP_TITLE, "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "total_deals": len(DEALS),
            "wins": len(WINS),
            "losses": len(LOSSES),
            "win_rate_pct": round(len(WINS) / len(DEALS) * 100, 1),
            "won_pipeline_usd": WIN_VALUE,
            "lost_pipeline_usd": LOSS_VALUE,
            "total_pipeline_usd": TOTAL_VALUE,
            "top_loss_reason": "No enterprise contract / Price (tied 25%)",
            "top_win_driver": "NVIDIA stack (40%)",
        }
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = html_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI unavailable — falling back to stdlib HTTPServer on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), _H).serve_forever()
