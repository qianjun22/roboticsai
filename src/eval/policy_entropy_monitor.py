"""Policy Entropy Monitor — FastAPI port 8784"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8784

def build_html():
    random.seed(42)
    # Generate entropy time-series data (bits) — lower entropy = more confident policy
    n_steps = 60
    entropies = []
    base = 2.8
    for i in range(n_steps):
        # Simulate training: entropy decreases then stabilizes with noise
        decay = base * math.exp(-0.03 * i)
        noise = random.gauss(0, 0.08)
        entropies.append(max(0.1, decay + noise + 0.45))

    # Action distribution entropy per joint (7-DOF arm)
    joint_labels = ["J1", "J2", "J3", "J4", "J5", "J6", "J7"]
    joint_entropies = [round(random.uniform(0.3, 1.8), 3) for _ in joint_labels]

    # SVG entropy curve (400x120)
    svg_w, svg_h = 400, 120
    e_min, e_max = 0.0, 3.2
    pts = []
    for i, e in enumerate(entropies):
        x = int(i * (svg_w - 20) / (n_steps - 1)) + 10
        y = int(svg_h - 10 - (e - e_min) / (e_max - e_min) * (svg_h - 20))
        pts.append(f"{x},{y}")
    polyline_pts = " ".join(pts)

    # Threshold line at entropy=1.0 (policy considered confident)
    thresh_y = int(svg_h - 10 - (1.0 - e_min) / (e_max - e_min) * (svg_h - 20))

    # Bar chart for joint entropies
    bar_svg_w, bar_svg_h = 400, 120
    bar_max = 2.0
    bar_items = ""
    bar_width = int((bar_svg_w - 40) / len(joint_labels))
    for idx, (lbl, val) in enumerate(zip(joint_labels, joint_entropies)):
        bh = int((val / bar_max) * (bar_svg_h - 30))
        bx = 20 + idx * bar_width + 4
        by = bar_svg_h - 20 - bh
        color = "#f87171" if val > 1.2 else "#34d399"
        bar_items += f'<rect x="{bx}" y="{by}" width="{bar_width-8}" height="{bh}" fill="{color}" rx="3"/>'
        bar_items += f'<text x="{bx + (bar_width-8)//2}" y="{bar_svg_h - 4}" fill="#94a3b8" font-size="10" text-anchor="middle">{lbl}</text>'
        bar_items += f'<text x="{bx + (bar_width-8)//2}" y="{by - 3}" fill="#e2e8f0" font-size="9" text-anchor="middle">{val}</text>'

    # Current stats
    current_entropy = round(entropies[-1], 4)
    mean_entropy = round(sum(entropies) / len(entropies), 4)
    min_entropy = round(min(entropies), 4)
    policy_confidence = round((1.0 - min(current_entropy / 3.2, 1.0)) * 100, 1)
    alert_joints = [lbl for lbl, v in zip(joint_labels, joint_entropies) if v > 1.2]
    alert_str = ", ".join(alert_joints) if alert_joints else "None"

    # KL divergence from uniform (7 actions)
    kl_from_uniform = round(math.log(7) - current_entropy, 4)

    return f"""<!DOCTYPE html><html><head><title>Policy Entropy Monitor</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 10px 0}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155}}
.metric{{font-size:1.8rem;font-weight:700;color:#f8fafc}}
.label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}}
.good{{color:#34d399}}.warn{{color:#fbbf24}}.bad{{color:#f87171}}
.chart-card{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155;margin-bottom:14px}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{text-align:left;color:#64748b;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600}}
.badge-ok{{background:#064e3b;color:#34d399}}.badge-warn{{background:#451a03;color:#fbbf24}}
</style></head>
<body>
<h1>Policy Entropy Monitor</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; GR00T N1.6 Policy &nbsp;|&nbsp; 7-DOF Manipulation &nbsp;|&nbsp; Real-time entropy analysis</div>

<div class="grid">
  <div class="card">
    <div class="metric {'good' if current_entropy < 1.0 else 'warn'}">{current_entropy}</div>
    <div class="label">Current Entropy (bits)</div>
  </div>
  <div class="card">
    <div class="metric">{mean_entropy}</div>
    <div class="label">Mean Entropy (60-step)</div>
  </div>
  <div class="card">
    <div class="metric good">{policy_confidence}%</div>
    <div class="label">Policy Confidence</div>
  </div>
  <div class="card">
    <div class="metric {'warn' if alert_joints else 'good'}">{len(alert_joints)}</div>
    <div class="label">High-Entropy Joints</div>
  </div>
</div>

<div class="row">
  <div class="chart-card">
    <h2>Entropy Over Training Steps</h2>
    <svg width="{svg_w}" height="{svg_h}" style="background:#0f172a;border-radius:6px">
      <line x1="10" y1="{thresh_y}" x2="{svg_w-10}" y2="{thresh_y}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{svg_w-8}" y="{thresh_y-3}" fill="#fbbf24" font-size="9" text-anchor="end">threshold=1.0</text>
      <polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <circle cx="{pts[-1].split(',')[0]}" cy="{pts[-1].split(',')[1]}" r="4" fill="#f87171"/>
      <text x="15" y="15" fill="#64748b" font-size="9">3.2 bits</text>
      <text x="15" y="{svg_h-12}" fill="#64748b" font-size="9">0.0 bits</text>
    </svg>
  </div>
  <div class="chart-card">
    <h2>Per-Joint Entropy Distribution</h2>
    <svg width="{bar_svg_w}" height="{bar_svg_h}" style="background:#0f172a;border-radius:6px">
      {bar_items}
      <line x1="20" y1="{int(bar_svg_h-20-(1.2/bar_max)*(bar_svg_h-30))}" x2="{bar_svg_w-10}" y2="{int(bar_svg_h-20-(1.2/bar_max)*(bar_svg_h-30))}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,3"/>
    </svg>
  </div>
</div>

<div class="chart-card">
  <h2>Entropy Statistics</h2>
  <table>
    <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
    <tr><td>Current Entropy</td><td>{current_entropy} bits</td><td><span class="badge {'badge-ok' if current_entropy < 1.0 else 'badge-warn'}">{'OK' if current_entropy < 1.0 else 'ELEVATED'}</span></td></tr>
    <tr><td>Min Entropy (best step)</td><td>{min_entropy} bits</td><td><span class="badge badge-ok">OK</span></td></tr>
    <tr><td>KL Div from Uniform</td><td>{kl_from_uniform} bits</td><td><span class="badge {'badge-ok' if kl_from_uniform > 0.5 else 'badge-warn'}">{'SPECIALIZED' if kl_from_uniform > 0.5 else 'UNCERTAIN'}</span></td></tr>
    <tr><td>High-Entropy Joints (&gt;1.2)</td><td>{alert_str}</td><td><span class="badge {'badge-warn' if alert_joints else 'badge-ok'}">{'REVIEW' if alert_joints else 'OK'}</span></td></tr>
    <tr><td>Monitoring Window</td><td>60 steps</td><td><span class="badge badge-ok">LIVE</span></td></tr>
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Entropy Monitor")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        random.seed(42)
        entropies = [max(0.1, 2.8 * math.exp(-0.03 * i) + random.gauss(0, 0.08) + 0.45) for i in range(60)]
        return {
            "current_entropy_bits": round(entropies[-1], 4),
            "mean_entropy_bits": round(sum(entropies) / len(entropies), 4),
            "min_entropy_bits": round(min(entropies), 4),
            "policy_confidence_pct": round((1.0 - min(entropies[-1] / 3.2, 1.0)) * 100, 1),
            "kl_from_uniform_bits": round(math.log(7) - entropies[-1], 4),
            "port": PORT
        }

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
