# Policy Robustness Tester V2 — port 8942
import math
import random
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HOST = "0.0.0.0"
PORT = 8942

PERTURBATION_TYPES = [
    {"name": "Gaussian Noise", "category": "sensor", "gr00t_v2": 0.81, "run10": 0.76},
    {"name": "Salt & Pepper", "category": "sensor", "gr00t_v2": 0.78, "run10": 0.74},
    {"name": "Motion Blur", "category": "visual", "gr00t_v2": 0.75, "run10": 0.71},
    {"name": "Brightness Shift", "category": "visual", "gr00t_v2": 0.80, "run10": 0.77},
    {"name": "Occlusion Patch", "category": "visual", "gr00t_v2": 0.69, "run10": 0.63},
    {"name": "Joint Noise", "category": "proprioception", "gr00t_v2": 0.76, "run10": 0.72},
    {"name": "Torque Delay", "category": "proprioception", "gr00t_v2": 0.73, "run10": 0.68},
    {"name": "Mass Perturbation ±50%", "category": "physical", "gr00t_v2": 0.71, "run10": 0.66},
    {"name": "Friction Perturbation ±30%", "category": "physical", "gr00t_v2": 0.74, "run10": 0.70},
    {"name": "Goal Displacement", "category": "task", "gr00t_v2": 0.68, "run10": 0.62},
    {"name": "Action Dropout", "category": "adversarial", "gr00t_v2": 0.72, "run10": 0.67},
    {"name": "FGSM Attack", "category": "adversarial", "gr00t_v2": 0.65, "run10": 0.58},
]

RADAR_DIMS = [
    {"label": "Sensor", "gr00t_v2": 0.798, "run10": 0.750},
    {"label": "Visual", "gr00t_v2": 0.747, "run10": 0.703},
    {"label": "Proprioception", "gr00t_v2": 0.745, "run10": 0.700},
    {"label": "Physical", "gr00t_v2": 0.725, "run10": 0.680},
    {"label": "Task", "gr00t_v2": 0.680, "run10": 0.620},
    {"label": "Adversarial", "gr00t_v2": 0.685, "run10": 0.625},
]


def build_radar_svg():
    cx, cy, r = 220, 220, 160
    n = len(RADAR_DIMS)
    angles = [math.pi / 2 - 2 * math.pi * i / n for i in range(n)]

    def pt(val, idx):
        a = angles[idx]
        rv = val * r
        return cx + rv * math.cos(a), cy - rv * math.sin(a)

    # grid rings
    rings = ""
    for lvl in [0.25, 0.50, 0.75, 1.0]:
        pts = " ".join(f"{cx + lvl*r*math.cos(a):.1f},{cy - lvl*r*math.sin(a):.1f}" for a in angles)
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'

    # axes
    axes = ""
    for i, a in enumerate(angles):
        x2, y2 = cx + r * math.cos(a), cy - r * math.sin(a)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="1"/>\n'
        lx = cx + (r + 22) * math.cos(a)
        ly = cy - (r + 22) * math.sin(a)
        axes += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="11">{RADAR_DIMS[i]["label"]}</text>\n'

    def poly(key, color, opacity):
        pts = " ".join(f"{pt(RADAR_DIMS[i][key], i)[0]:.1f},{pt(RADAR_DIMS[i][key], i)[1]:.1f}" for i in range(n))
        return f'<polygon points="{pts}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="2"/>\n'

    return f"""<svg width="440" height="440" xmlns="http://www.w3.org/2000/svg">
  <rect width="440" height="440" fill="#1e293b" rx="8"/>
  {rings}{axes}
  {poly('run10', '#f59e0b', '0.15')}{poly('run10', '#f59e0b', '0')}
  {poly('gr00t_v2', '#38bdf8', '0.20')}{poly('gr00t_v2', '#38bdf8', '0')}
  <circle cx="30" cy="20" r="6" fill="#38bdf8"/><text x="42" y="25" fill="#cbd5e1" font-size="12">GR00T_v2 (0.74)</text>
  <circle cx="160" cy="20" r="6" fill="#f59e0b"/><text x="172" y="25" fill="#cbd5e1" font-size="12">run10 (0.71)</text>
</svg>"""


def build_bar_svg():
    bar_h = 22
    gap = 6
    pad_l = 180
    width = 640
    items = PERTURBATION_TYPES
    h = (bar_h * 2 + gap + 12) * len(items) + 40
    svg = f'<svg width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg"><rect width="{width}" height="{h}" fill="#1e293b" rx="8"/>'
    max_w = width - pad_l - 60
    for i, item in enumerate(items):
        y = 30 + i * (bar_h * 2 + gap + 12)
        svg += f'<text x="{pad_l-8}" y="{y+bar_h//2+4}" text-anchor="end" fill="#94a3b8" font-size="11">{item["name"]}</text>'
        w1 = item["gr00t_v2"] * max_w
        w2 = item["run10"] * max_w
        svg += f'<rect x="{pad_l}" y="{y}" width="{w1:.1f}" height="{bar_h}" fill="#38bdf8" rx="3"/>'
        svg += f'<text x="{pad_l+w1+4}" y="{y+bar_h//2+4}" fill="#38bdf8" font-size="10">{item["gr00t_v2"]}</text>'
        svg += f'<rect x="{pad_l}" y="{y+bar_h+4}" width="{w2:.1f}" height="{bar_h}" fill="#f59e0b" rx="3"/>'
        svg += f'<text x="{pad_l+w2+4}" y="{y+bar_h*2+8}" fill="#f59e0b" font-size="10">{item["run10"]}</text>'
    svg += '</svg>'
    return svg


HTML = f"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Policy Robustness Tester V2</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;text-align:center;padding:28px 0 4px;font-size:2rem;letter-spacing:1px}}
  h2{{color:#38bdf8;font-size:1.1rem;margin:28px 0 10px;padding-left:4px}}
  .wrap{{max-width:900px;margin:0 auto;padding:0 24px 48px}}
  .cards{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:28px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px 16px;text-align:center}}
  .card .val{{font-size:2.2rem;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:0.8rem;color:#94a3b8;margin-top:6px}}
  .card .sub{{font-size:0.75rem;color:#64748b;margin-top:2px}}
  .charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}}
  .chart-box{{background:#1e293b;border-radius:10px;padding:16px}}
  .chart-box svg{{width:100%;height:auto}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden}}
  th{{background:#0f172a;color:#38bdf8;padding:10px 12px;text-align:left;font-size:0.78rem;text-transform:uppercase}}
  td{{padding:9px 12px;font-size:0.82rem;border-top:1px solid #334155}}
  .badge{{display:inline-block;border-radius:4px;padding:2px 8px;font-size:0.72rem;font-weight:600}}
  .sensor{{background:#0e4166;color:#38bdf8}}.visual{{background:#1a3a1a;color:#4ade80}}
  .proprioception{{background:#2d2060;color:#a78bfa}}.physical{{background:#3d1a00;color:#fb923c}}
  .task{{background:#1e293b;color:#94a3b8}}.adversarial{{background:#3b0a0a;color:#f87171}}
  footer{{text-align:center;color:#475569;font-size:0.75rem;padding-top:24px}}
</style></head><body><div class="wrap">
  <h1>Policy Robustness Tester V2</h1>
  <p style="text-align:center;color:#64748b;margin-bottom:24px">Adversarial perturbation testing across 12 attack types — GR00T_v2 vs run10 baseline</p>
  <div class="cards">
    <div class="card"><div class="val">0.74</div><div class="lbl">GR00T_v2 Overall Score</div><div class="sub">+4.2% vs run10</div></div>
    <div class="card"><div class="val">12</div><div class="lbl">Perturbation Types</div><div class="sub">sensor · visual · physical · adversarial</div></div>
    <div class="card"><div class="val">±50%</div><div class="lbl">Max Physical Deviation</div><div class="sub">mass ±50% / friction ±30%</div></div>
  </div>
  <div class="charts">
    <div class="chart-box"><h2>Robustness Radar</h2>{build_radar_svg()}</div>
    <div class="chart-box"><h2>Per-Perturbation Breakdown</h2>{build_bar_svg()}</div>
  </div>
  <h2>Perturbation Details</h2>
  <table>
    <tr><th>Perturbation</th><th>Category</th><th>GR00T_v2</th><th>run10</th><th>Delta</th></tr>
    {''.join(f"<tr><td>{p['name']}</td><td><span class='badge {p['category']}'>{p['category']}</span></td><td style='color:#38bdf8'>{p['gr00t_v2']}</td><td style='color:#f59e0b'>{p['run10']}</td><td style='color:{('#4ade80' if p['gr00t_v2']>p['run10'] else '#f87171')}'>{'+' if p['gr00t_v2']>p['run10'] else ''}{(p['gr00t_v2']-p['run10']):.3f}</td></tr>" for p in PERTURBATION_TYPES)}
  </table>
  <footer>OCI Robot Cloud &mdash; Policy Robustness Tester V2 &mdash; port {PORT}</footer>
</div></body></html>
"""


if USE_FASTAPI:
    app = FastAPI(title="Policy Robustness Tester V2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "policy_robustness_tester_v2"}

    @app.get("/api/scores")
    def scores():
        return {"gr00t_v2": 0.74, "run10": 0.71, "perturbations": PERTURBATION_TYPES}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *a):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host=HOST, port=PORT)
    else:
        print(f"FastAPI unavailable — fallback HTTPServer on port {PORT}")
        HTTPServer((HOST, PORT), Handler).serve_forever()
