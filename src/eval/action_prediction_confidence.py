"""Action Prediction Confidence — FastAPI port 8806"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8806

def build_html():
    random.seed(42)
    # Generate confidence scores per action class over 30 timesteps
    timesteps = 30
    action_labels = ["pick", "place", "push", "grasp", "rotate", "lift"]
    colors = ["#38bdf8", "#f472b6", "#4ade80", "#facc15", "#f87171", "#a78bfa"]

    # Simulate confidence trajectories using sin/cos + noise
    def conf_series(phase, freq, base):
        return [
            round(min(1.0, max(0.0, base + 0.18 * math.sin(freq * t + phase) + random.gauss(0, 0.04))), 3)
            for t in range(timesteps)
        ]

    series = [
        conf_series(i * 1.1, 0.4 + i * 0.07, 0.55 + i * 0.05)
        for i in range(len(action_labels))
    ]

    # Top predicted action per step
    top_actions = []
    for t in range(timesteps):
        vals = [s[t] for s in series]
        top_actions.append(action_labels[vals.index(max(vals))])

    # SVG line chart (600x200)
    svg_w, svg_h = 600, 200
    pad = 30
    chart_w = svg_w - 2 * pad
    chart_h = svg_h - 2 * pad

    def to_x(t):
        return pad + t * chart_w / (timesteps - 1)

    def to_y(v):
        return pad + (1 - v) * chart_h

    polylines = ""
    for idx, s in enumerate(series):
        pts = " ".join(f"{to_x(t):.1f},{to_y(v):.1f}" for t, v in enumerate(s))
        polylines += f'<polyline points="{pts}" fill="none" stroke="{colors[idx]}" stroke-width="1.8" opacity="0.85"/>\n'

    # Axis labels
    axis = ""
    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = to_y(tick)
        axis += f'<line x1="{pad}" y1="{y:.1f}" x2="{svg_w - pad}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'
        axis += f'<text x="{pad - 4}" y="{y + 4:.1f}" font-size="9" fill="#64748b" text-anchor="end">{tick:.2f}</text>'

    legend_items = "".join(
        f'<rect x="{10 + i * 95}" y="4" width="10" height="10" fill="{colors[i]}"/><text x="{23 + i * 95}" y="13" font-size="10" fill="#e2e8f0">{action_labels[i]}</text>'
        for i in range(len(action_labels))
    )

    # Per-action mean confidence
    means = [round(sum(s) / len(s), 3) for s in series]
    bar_rows = "".join(
        f'<tr><td style="padding:4px 10px;color:{colors[i]}">{action_labels[i]}</td>'
        f'<td style="padding:4px 10px">'
        f'<div style="background:#0f172a;border-radius:4px;width:200px;height:14px">'
        f'<div style="background:{colors[i]};width:{int(means[i]*200)}px;height:14px;border-radius:4px"></div></div></td>'
        f'<td style="padding:4px 10px;color:{colors[i]}">{means[i]:.3f}</td></tr>'
        for i in range(len(action_labels))
    )

    # Entropy per step
    def entropy(step):
        vals = [s[step] for s in series]
        total = sum(vals) + 1e-9
        probs = [v / total for v in vals]
        return -sum(p * math.log(p + 1e-9) for p in probs)

    entropies = [entropy(t) for t in range(timesteps)]
    ent_max = max(entropies)
    ent_pts = " ".join(
        f"{to_x(t):.1f},{to_y(e / ent_max):.1f}" for t, e in enumerate(entropies)
    )

    latest_conf = {action_labels[i]: series[i][-1] for i in range(len(action_labels))}
    top_now = max(latest_conf, key=latest_conf.get)
    top_conf = latest_conf[top_now]

    html = f"""<!DOCTYPE html><html><head><title>Action Prediction Confidence</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:16px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 20px;margin:6px;text-align:center}}
.stat .val{{font-size:1.8em;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.75em;color:#94a3b8}}
table{{border-collapse:collapse;width:100%}}
</style></head>
<body>
<h1>Action Prediction Confidence</h1>
<p style="color:#64748b">Port {PORT} | Real-time confidence scoring across action primitives</p>

<div class="card">
  <h2>Live Status</h2>
  <div class="stat"><div class="val">{top_now}</div><div class="lbl">Top Action (t=T)</div></div>
  <div class="stat"><div class="val">{top_conf:.3f}</div><div class="lbl">Confidence Score</div></div>
  <div class="stat"><div class="val">{entropies[-1]:.3f}</div><div class="lbl">Prediction Entropy</div></div>
  <div class="stat"><div class="val">{timesteps}</div><div class="lbl">Timesteps Evaluated</div></div>
</div>

<div class="card">
  <h2>Confidence Trajectories (all actions)</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    {axis}
    {polylines}
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{svg_h - pad}" stroke="#475569" stroke-width="1"/>
    <line x1="{pad}" y1="{svg_h - pad}" x2="{svg_w - pad}" y2="{svg_h - pad}" stroke="#475569" stroke-width="1"/>
    <text x="{svg_w // 2}" y="{svg_h - 4}" font-size="10" fill="#64748b" text-anchor="middle">Timestep</text>
  </svg>
  <svg width="{svg_w}" height="24">{legend_items}</svg>
</div>

<div class="card">
  <h2>Prediction Entropy Over Time</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    {axis}
    <polyline points="{ent_pts}" fill="none" stroke="#fb923c" stroke-width="2"/>
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{svg_h - pad}" stroke="#475569" stroke-width="1"/>
    <line x1="{pad}" y1="{svg_h - pad}" x2="{svg_w - pad}" y2="{svg_h - pad}" stroke="#475569" stroke-width="1"/>
    <text x="{svg_w // 2}" y="{svg_h - 4}" font-size="10" fill="#64748b" text-anchor="middle">Timestep</text>
  </svg>
  <p style="color:#94a3b8;font-size:0.85em">Entropy normalized to [0,1]. Higher = more uncertain multi-modal prediction.</p>
</div>

<div class="card">
  <h2>Mean Confidence per Action Class</h2>
  <table>{bar_rows}</table>
</div>

</body></html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="Action Prediction Confidence")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/confidence")
    def confidence_json():
        random.seed()
        actions = ["pick", "place", "push", "grasp", "rotate", "lift"]
        scores = [round(random.uniform(0.4, 0.98), 4) for _ in actions]
        total = sum(scores)
        probs = [round(s / total, 4) for s in scores]
        top = actions[probs.index(max(probs))]
        return {"action_scores": dict(zip(actions, probs)), "top_action": top, "port": PORT}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
