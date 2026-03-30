# Bimanual Policy Trainer — port 8924
# Dual-arm GR00T training: shared vision encoder + per-arm action decoder + coordination reward

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

APP_TITLE = "Bimanual Policy Trainer"
PORT = 8924

# ── Data ──────────────────────────────────────────────────────────────────────

STEPS = list(range(0, 5001, 500))

def _sr(step):
    """Sigmoid success-rate curve from 28% baseline toward 55% target."""
    x = step / 5000
    return 0.28 + (0.55 - 0.28) * (1 / (1 + math.exp(-10 * (x - 0.5))))

def _sync(step):
    """Arm synchronisation metric: improves from 0.42 toward 0.91."""
    x = step / 5000
    return 0.42 + (0.91 - 0.42) * (1 - math.exp(-3 * x))

SR_BASELINE = [round(0.28 + random.gauss(0, 0.01), 3) for _ in STEPS]   # no coord reward
SR_WITH     = [round(_sr(s) + random.gauss(0, 0.008), 3) for s in STEPS]
SYNC_METRIC = [round(_sync(s) + random.gauss(0, 0.005), 3) for s in STEPS]

# SVG helpers
def _polyline(xs, ys, w, h, pad, color, stroke_w=2.5):
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x == min_x: max_x = min_x + 1
    if max_y == min_y: max_y = min_y + 0.01
    pts = " ".join(
        f"{pad + (x - min_x)/(max_x - min_x)*(w - 2*pad):.1f},"
        f"{h - pad - (y - min_y)/(max_y - min_y)*(h - 2*pad):.1f}"
        for x, y in zip(xs, ys)
    )
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linejoin="round"/>'

def build_sr_svg():
    W, H, PAD = 560, 220, 32
    baseline = _polyline(STEPS, SR_BASELINE, W, H, PAD, "#64748b")
    with_cr   = _polyline(STEPS, SR_WITH,    W, H, PAD, "#38bdf8")
    target_y  = H - PAD - (0.55 - min(SR_WITH)) / (max(SR_WITH) - min(SR_WITH) + 1e-9) * (H - 2*PAD)
    return f'''
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Bimanual Success Rate vs Training Steps</text>
  {baseline}
  {with_cr}
  <line x1="{PAD}" y1="{target_y:.1f}" x2="{W-PAD}" y2="{target_y:.1f}" stroke="#C74634" stroke-width="1" stroke-dasharray="6,3"/>
  <text x="{W-PAD+2}" y="{target_y:.1f}" fill="#C74634" font-size="9" font-family="monospace" dominant-baseline="middle">55% target</text>
  <circle cx="{W-2*PAD}" cy="{H-14}" r="5" fill="#64748b"/><text x="{W-2*PAD+8}" y="{H-10}" fill="#94a3b8" font-size="9" font-family="monospace">No coord reward (28%)</text>
  <circle cx="{PAD}"     cy="{H-14}" r="5" fill="#38bdf8"/><text x="{PAD+8}"     y="{H-10}" fill="#94a3b8" font-size="9" font-family="monospace">With coord reward (47%)</text>
</svg>'''

def build_sync_svg():
    W, H, PAD = 560, 200, 32
    line = _polyline(STEPS, SYNC_METRIC, W, H, PAD, "#a78bfa")
    return f'''
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="18" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Arm Synchronisation Metric (0→1) vs Training Steps</text>
  {line}
  <text x="{W-PAD}" y="{H//2}" fill="#a78bfa" font-size="9" font-family="monospace" text-anchor="end">0.91 peak</text>
</svg>'''

def html_page():
    sr_svg   = build_sr_svg()
    sync_svg = build_sync_svg()
    latest_sr   = SR_WITH[-1]
    latest_sync = SYNC_METRIC[-1]
    gap = round(0.55 - latest_sr, 3)
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
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}}
  .kpi{{background:#1e293b;border-radius:8px;padding:16px;text-align:center}}
  .kpi .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
  .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:4px}}
  .kpi .val.red{{color:#C74634}}
  .kpi .val.green{{color:#4ade80}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th{{text-align:left;color:#94a3b8;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem}}
  .blue{{background:#0ea5e920;color:#38bdf8}}.red{{background:#C7463420;color:#C74634}}
  .green{{background:#4ade8020;color:#4ade80}}.purple{{background:#a78bfa20;color:#a78bfa}}
</style>
</head>
<body>
<h1>{APP_TITLE}</h1>
<p style="color:#94a3b8;margin:0 0 20px">Dual-arm GR00T training — shared vision encoder + per-arm action decoder + coordination reward</p>

<div class="grid">
  <div class="kpi"><div class="val red">28%</div><div class="lbl">SR without coord reward</div></div>
  <div class="kpi"><div class="val blue">47%</div><div class="lbl">SR with coord reward</div></div>
  <div class="kpi"><div class="val green">55%</div><div class="lbl">Target bimanual SR</div></div>
  <div class="kpi"><div class="val" style="color:#a78bfa">{latest_sync:.2f}</div><div class="lbl">Arm sync metric (latest)</div></div>
  <div class="kpi"><div class="val" style="color:#fbbf24">{gap:.3f}</div><div class="lbl">Gap to target</div></div>
</div>

<div class="card">
  <h2>Bimanual Success Rate vs Training Steps</h2>
  {sr_svg}
</div>

<div class="card">
  <h2>Arm Synchronisation Metric</h2>
  {sync_svg}
</div>

<div class="card">
  <h2>Architecture Summary</h2>
  <table>
    <tr><th>Component</th><th>Detail</th><th>Status</th></tr>
    <tr><td>Vision Encoder</td><td>Shared ViT-L/14 (frozen first 18 layers)</td><td><span class="badge green">active</span></td></tr>
    <tr><td>Left-Arm Decoder</td><td>8-layer transformer, 512 hidden, chunk=16</td><td><span class="badge blue">training</span></td></tr>
    <tr><td>Right-Arm Decoder</td><td>8-layer transformer, 512 hidden, chunk=16</td><td><span class="badge blue">training</span></td></tr>
    <tr><td>Coordination Head</td><td>Cross-attention between arm latents, λ=0.3</td><td><span class="badge blue">training</span></td></tr>
    <tr><td>Coord Reward Weight</td><td>λ_coord = 0.3 (annealed 0→0.3 over 1k steps)</td><td><span class="badge purple">tuned</span></td></tr>
    <tr><td>Training Hardware</td><td>4× A100 80 GB (DDP), batch 32 per GPU</td><td><span class="badge green">healthy</span></td></tr>
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
            "sr_baseline_pct": 28,
            "sr_with_coord_pct": 47,
            "sr_target_pct": 55,
            "latest_sync_metric": SYNC_METRIC[-1],
            "gap_to_target": round(0.55 - SR_WITH[-1], 3),
            "training_steps_logged": len(STEPS),
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
