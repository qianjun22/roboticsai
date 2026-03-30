"""checkpoint_pruner.py — Checkpoint lifecycle manager: deduplication, compression, selective retention.
FastAPI service on port 8271.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock checkpoint data
# ---------------------------------------------------------------------------

random.seed(7)

STEPS = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900,
         1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900,
         2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900,
         3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900,
         4000, 4200, 4400, 4600, 4800]

MILESTONE_STEPS = {0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000}

# SR curve: ramp up, plateau, slight noise
def _sr(step):
    base = 0.30 + 0.48 * (1 - math.exp(-step / 1800))
    noise = random.gauss(0, 0.012)
    return min(0.97, max(0.25, base + noise))

random.seed(7)
CHECKPOINTS = []
for s in STEPS:
    sr_val = _sr(s)
    size_gb = round(random.uniform(16.5, 20.2), 2)  # per checkpoint
    CHECKPOINTS.append({"step": s, "sr": round(sr_val, 4), "size_gb": size_gb})

TOTAL_RAW_GB = sum(c["size_gb"] for c in CHECKPOINTS)   # ~847 GB
TOTAL_RAW_GB = 847.0  # fixed per spec

# Determine which checkpoints to keep
best_sr = max(c["sr"] for c in CHECKPOINTS)
for c in CHECKPOINTS:
    keep = (
        c["step"] in MILESTONE_STEPS
        or c["sr"] >= best_sr - 0.005  # near-best
        or c["step"] == STEPS[-1]       # latest
    )
    c["status"] = "KEEP" if keep else "DELETE"
    if c["step"] in MILESTONE_STEPS:
        c["status"] = "MILESTONE"

KEPT = [c for c in CHECKPOINTS if c["status"] != "DELETE"]
PRUNED_GB = 124.0  # fixed per spec — 85% savings
SAVINGS_PCT = round((1 - PRUNED_GB / TOTAL_RAW_GB) * 100, 1)

# Storage timeline: 90 days, 1 checkpoint saved every ~2 days
DAY0 = datetime(2026, 1, 1)
TIMELINE_NAIVE  = []   # keep-all cumulative GB
TIMELINE_SMART  = []   # pruned cumulative GB
cum_naive = 0.0
cum_smart = 0.0
for i, c in enumerate(CHECKPOINTS):
    day = i * 2
    cum_naive += c["size_gb"]
    if c["status"] != "DELETE":
        cum_smart += c["size_gb"]
    else:
        cum_smart += 0  # pruned away
    TIMELINE_NAIVE.append((day, round(cum_naive, 1)))
    TIMELINE_SMART.append((day, round(cum_smart, 1)))


def _build_html() -> str:
    # -----------------------------------------------------------------------
    # SVG 1 — Storage usage timeline
    # -----------------------------------------------------------------------
    svg1_w, svg1_h = 700, 260
    cx0, cy_bot = 70, 220
    chart_w, chart_h = 600, 180
    max_gb = 900

    def px_x(day):
        return cx0 + int(day / 90 * chart_w)

    def px_y(gb):
        return cy_bot - int(gb / max_gb * chart_h)

    # naive line
    naive_pts = " ".join(f"{px_x(d)},{px_y(g)}" for d, g in TIMELINE_NAIVE)
    smart_pts = " ".join(f"{px_x(d)},{px_y(g)}" for d, g in TIMELINE_SMART)

    # event markers for prune decisions
    markers = []
    for i, c in enumerate(CHECKPOINTS):
        day = i * 2
        if c["status"] == "DELETE":
            mx = px_x(day)
            my = px_y(TIMELINE_SMART[i][1])
            markers.append(f'<circle cx="{mx}" cy="{my}" r="4" fill="#f87171" opacity="0.7"/>')
        elif c["status"] == "MILESTONE":
            mx = px_x(day)
            my = px_y(TIMELINE_SMART[i][1])
            markers.append(f'<circle cx="{mx}" cy="{my}" r="5" fill="#facc15"/>')

    svg1_rows = [
        f'<line x1="{cx0}" y1="{cy_bot-chart_h}" x2="{cx0}" y2="{cy_bot}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{cx0}" y1="{cy_bot}" x2="{cx0+chart_w}" y2="{cy_bot}" stroke="#475569" stroke-width="1"/>',
        f'<polyline points="{naive_pts}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5,3"/>',
        f'<polyline points="{smart_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>',
        *markers,
        # labels
        f'<text x="{cx0+chart_w-10}" y="{px_y(TIMELINE_NAIVE[-1][1])-6}" fill="#64748b" font-size="11" text-anchor="end">Naive: {TOTAL_RAW_GB:.0f} GB</text>',
        f'<text x="{cx0+chart_w-10}" y="{px_y(TIMELINE_SMART[-1][1])-6}" fill="#38bdf8" font-size="11" text-anchor="end">Smart: {PRUNED_GB:.0f} GB</text>',
        # axes labels
        f'<text x="{cx0+chart_w//2}" y="{svg1_h-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Day (0–90)</text>',
        f'<text x="12" y="{cy_bot-chart_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,12,{cy_bot-chart_h//2})">GB</text>',
        f'<text x="{cx0+chart_w//2}" y="18" fill="#f1f5f9" font-size="13" text-anchor="middle" font-weight="bold">Cumulative Storage: Naive vs Smart Pruning (yellow=milestone, red=deleted)</text>',
        # y-axis ticks
        *[f'<text x="{cx0-6}" y="{px_y(g)+4}" fill="#64748b" font-size="9" text-anchor="end">{g}</text><line x1="{cx0-3}" y1="{px_y(g)}" x2="{cx0}" y2="{px_y(g)}" stroke="#334155" stroke-width="1"/>' for g in range(0, 901, 150)],
    ]

    svg1 = f'<svg width="{svg1_w}" height="{svg1_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">{"".join(svg1_rows)}</svg>'

    # -----------------------------------------------------------------------
    # SVG 2 — Checkpoint retention decision matrix (step vs SR scatter)
    # -----------------------------------------------------------------------
    svg2_w, svg2_h = 700, 300
    mx0, my_bot = 70, 260
    mw, mh = 590, 200
    max_step = 5000

    def scx(step):
        return mx0 + int(step / max_step * mw)

    def scy(sr):
        return my_bot - int((sr - 0.25) / 0.75 * mh)

    scatter = []
    for c in CHECKPOINTS:
        sx = scx(c["step"])
        sy = scy(c["sr"])
        color = {"KEEP": "#4ade80", "MILESTONE": "#facc15", "DELETE": "#f87171"}[c["status"]]
        r = 7 if c["status"] == "MILESTONE" else 5
        scatter.append(f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="{color}" opacity="0.85"/>')

    # best SR horizontal guide
    best_y = scy(best_sr)
    scatter.append(f'<line x1="{mx0}" y1="{best_y}" x2="{mx0+mw}" y2="{best_y}" stroke="#4ade80" stroke-width="1" stroke-dasharray="4,3"/>')
    scatter.append(f'<text x="{mx0+mw+4}" y="{best_y+4}" fill="#4ade80" font-size="9">Best SR {best_sr:.3f}</text>')

    svg2_rows = [
        f'<line x1="{mx0}" y1="{my_bot-mh}" x2="{mx0}" y2="{my_bot}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{mx0}" y1="{my_bot}" x2="{mx0+mw}" y2="{my_bot}" stroke="#475569" stroke-width="1"/>',
        *scatter,
        # legend
        '<circle cx="100" cy="280" r="5" fill="#4ade80"/>',
        '<text x="108" y="284" fill="#4ade80" font-size="10">KEEP</text>',
        '<circle cx="150" cy="280" r="7" fill="#facc15"/>',
        '<text x="160" y="284" fill="#facc15" font-size="10">MILESTONE</text>',
        '<circle cx="235" cy="280" r="5" fill="#f87171"/>',
        '<text x="243" y="284" fill="#f87171" font-size="10">DELETE</text>',
        # axes
        f'<text x="{mx0+mw//2}" y="{svg2_h-2}" fill="#94a3b8" font-size="11" text-anchor="middle">Training Step</text>',
        f'<text x="12" y="{my_bot-mh//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,12,{my_bot-mh//2})">Success Rate</text>',
        f'<text x="{mx0+mw//2}" y="18" fill="#f1f5f9" font-size="13" text-anchor="middle" font-weight="bold">Checkpoint Retention Matrix — 45 checkpoints, keeping {len(KEPT)}</text>',
        # x-axis ticks
        *[f'<text x="{scx(s)}" y="{my_bot+12}" fill="#64748b" font-size="9" text-anchor="middle">{s}</text><line x1="{scx(s)}" y1="{my_bot}" x2="{scx(s)}" y2="{my_bot+4}" stroke="#334155" stroke-width="1"/>' for s in range(0, 5001, 1000)],
        # y-axis ticks
        *[f'<text x="{mx0-5}" y="{scy(sr)+3}" fill="#64748b" font-size="9" text-anchor="end">{sr:.2f}</text>' for sr in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]],
    ]

    svg2 = f'<svg width="{svg2_w}" height="{svg2_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">{"".join(svg2_rows)}</svg>'

    # -----------------------------------------------------------------------
    # Checkpoint table (top 12 kept)
    # -----------------------------------------------------------------------
    kept_rows = ""
    for c in sorted(KEPT, key=lambda x: x["step"]):
        status_color = {"KEEP": "#4ade80", "MILESTONE": "#facc15"}.get(c["status"], "#94a3b8")
        kept_rows += f"""
        <tr>
          <td style="padding:5px 10px;color:#94a3b8;">{c['step']}</td>
          <td style="padding:5px 10px;color:#38bdf8;">{c['sr']:.4f}</td>
          <td style="padding:5px 10px;color:#f1f5f9;">{c['size_gb']:.1f} GB</td>
          <td style="padding:5px 10px;color:{status_color};">{c['status']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Checkpoint Pruner — Port 8271</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 18px; border: 1px solid #334155; }}
    .card h3 {{ color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }}
    .val {{ font-size: 1.7rem; font-weight: 700; color: #f1f5f9; }}
    .sub {{ color: #64748b; font-size: 0.78rem; margin-top: 2px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }}
    .section h2 {{ color: #f1f5f9; font-size: 1rem; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:nth-child(even) {{ background: #0f172a; }}
    th {{ padding: 8px 10px; color: #64748b; font-size: 0.78rem; text-align: left; border-bottom: 1px solid #334155; }}
  </style>
</head>
<body>
  <h1>Checkpoint Pruner</h1>
  <p class="subtitle">Checkpoint lifecycle manager: dedup, compress, retain &mdash; Port 8271 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

  <div class="grid">
    <div class="card">
      <h3>Total Checkpoints</h3>
      <div class="val">{len(CHECKPOINTS)}</div>
      <div class="sub">Across all runs</div>
    </div>
    <div class="card">
      <h3>Raw Storage</h3>
      <div class="val" style="color:#f87171">{TOTAL_RAW_GB:.0f} GB</div>
      <div class="sub">Naive keep-all</div>
    </div>
    <div class="card">
      <h3>After Pruning</h3>
      <div class="val" style="color:#4ade80">{PRUNED_GB:.0f} GB</div>
      <div class="sub">{len(KEPT)} of {len(CHECKPOINTS)} retained</div>
    </div>
    <div class="card">
      <h3>Storage Savings</h3>
      <div class="val" style="color:#38bdf8">{SAVINGS_PCT:.0f}%</div>
      <div class="sub">{TOTAL_RAW_GB - PRUNED_GB:.0f} GB freed</div>
    </div>
  </div>

  <div class="section">
    <h2>Storage Usage Timeline — 90 Days</h2>
    {svg1}
  </div>

  <div class="section">
    <h2>Checkpoint Retention Decision Matrix</h2>
    {svg2}
  </div>

  <div class="section">
    <h2>Retained Checkpoints ({len(KEPT)} of {len(CHECKPOINTS)})</h2>
    <table>
      <thead><tr><th>Step</th><th>Success Rate</th><th>Size</th><th>Status</th></tr></thead>
      <tbody>{kept_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _USE_FASTAPI:
    app = FastAPI(title="Checkpoint Pruner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "checkpoint_pruner", "port": 8271}

    @app.get("/checkpoints")
    async def list_checkpoints():
        return {
            "total": len(CHECKPOINTS),
            "kept": len(KEPT),
            "deleted": len(CHECKPOINTS) - len(KEPT),
            "raw_gb": TOTAL_RAW_GB,
            "pruned_gb": PRUNED_GB,
            "savings_pct": SAVINGS_PCT,
            "checkpoints": CHECKPOINTS,
        }

    @app.get("/checkpoints/kept")
    async def list_kept():
        return {"kept": KEPT, "count": len(KEPT), "total_gb": PRUNED_GB}

    @app.get("/checkpoints/best")
    async def best_checkpoint():
        best = max(CHECKPOINTS, key=lambda c: c["sr"])
        return {"best": best}

    @app.post("/prune")
    async def trigger_prune():
        deleted = [c for c in CHECKPOINTS if c["status"] == "DELETE"]
        return {
            "status": "pruned",
            "deleted_count": len(deleted),
            "freed_gb": round(TOTAL_RAW_GB - PRUNED_GB, 1),
            "savings_pct": SAVINGS_PCT,
            "timestamp": datetime.utcnow().isoformat(),
        }

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8271)
    else:
        print("[checkpoint_pruner] fastapi not found — using stdlib http.server on port 8271")
        with socketserver.TCPServer(("", 8271), _Handler) as srv:
            srv.serve_forever()
