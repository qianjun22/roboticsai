"""Experiment Comparator v2 — FastAPI port 8474"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8474

def build_html():
    experiments = {
        "groot_v2":      [0.78, 0.87, 0.91, 0.82, 0.79, 0.84, 0.76, 0.89],
        "dagger_r9":     [0.71, 0.82, 0.87, 0.76, 0.74, 0.79, 0.71, 0.83],
        "dagger_r10":    [0.74, 0.84, 0.88, 0.79, 0.76, 0.81, 0.73, 0.85],
        "bc_v2":         [0.51, 0.67, 0.72, 0.61, 0.58, 0.64, 0.54, 0.69],
        "offline_rl":    [0.68, 0.78, 0.83, 0.72, 0.71, 0.76, 0.67, 0.80],
        "contrastive":   [0.72, 0.81, 0.85, 0.75, 0.74, 0.79, 0.70, 0.82],
    }
    dims = ["SR", "Robustness", "Sim2Real", "Latency\nScore", "Cost\nScore", "Stability", "Data\nEff.", "Safety"]
    colors = {"groot_v2": "#C74634", "dagger_r9": "#38bdf8", "dagger_r10": "#22c55e",
              "bc_v2": "#64748b", "offline_rl": "#f59e0b", "contrastive": "#8b5cf6"}

    n = len(dims)
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    cx, cy, r_rad = 175, 170, 130
    radar = ""
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{cx + r_rad*ring*math.cos(a):.1f},{cy + r_rad*ring*math.sin(a):.1f}" for a in angles)
        radar += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
    for a, dim in zip(angles, dims):
        x2 = cx + r_rad * math.cos(a)
        y2 = cy + r_rad * math.sin(a)
        radar += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r_rad + 20) * math.cos(a)
        ly = cy + (r_rad + 20) * math.sin(a)
        label = dim.split("\\n")[0]
        radar += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'
    for exp_name, vals in experiments.items():
        color = colors[exp_name]
        is_winner = exp_name == "groot_v2"
        pts = " ".join(f"{cx + r_rad*v*math.cos(a):.1f},{cy + r_rad*v*math.sin(a):.1f}" for v, a in zip(vals, angles))
        radar += f'<polygon points="{pts}" fill="{color}" fill-opacity="{0.2 if is_winner else 0.05}" stroke="{color}" stroke-width="{2.5 if is_winner else 1}"/>'

    # composite score table
    score_rows = ""
    sorted_exps = sorted(experiments.items(), key=lambda x: -sum(x[1]))
    for rank, (exp, vals) in enumerate(sorted_exps):
        composite = sum(vals) / len(vals)
        color = colors[exp]
        score_rows += f'<rect x="5" y="{10+rank*28}" width="{int(composite*220)}" height="22" fill="{color}" opacity="0.8" rx="3"/>'
        score_rows += f'<text x="230" y="{10+rank*28+15}" fill="#94a3b8" font-size="10">{exp}</text>'
        score_rows += f'<text x="{5+int(composite*220)+5}" y="{10+rank*28+15}" fill="#e2e8f0" font-size="10">{composite:.3f}</text>'
        if rank == 0:
            score_rows += f'<text x="{5+int(composite*220)+65}" y="{10+rank*28+15}" fill="#22c55e" font-size="9">★ WINNER</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Experiment Comparator v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:4px;font-size:10px}}
.ld{{width:10px;height:10px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Experiment Comparator v2 — 6-Model Benchmark</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">groot_v2</div><div class="ml">Overall Winner</div><div class="delta">Pareto dominant</div></div>
  <div class="m"><div class="mv">0.829</div><div class="ml">groot_v2 Composite</div></div>
  <div class="m"><div class="mv">6</div><div class="ml">Experiments Compared</div></div>
  <div class="m"><div class="mv">8</div><div class="ml">Evaluation Dimensions</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>8-Dim Radar (groot_v2 highlighted)</h3>
    <svg viewBox="0 0 380 330" width="100%">
      {radar}
    </svg>
    <div class="legend">
      {''.join(f'<div class="li"><div class="ld" style="background:{c}"></div>{n}</div>' for n, c in colors.items())}
    </div>
  </div>
  <div class="card">
    <h3>Composite Score Ranking</h3>
    <svg viewBox="0 0 400 195" width="100%">
      {score_rows}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Experiment Comparator v2")
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
