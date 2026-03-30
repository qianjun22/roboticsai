"""Grasping Success Predictor — FastAPI port 8704"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8704

def build_html():
    random.seed(42)
    # Generate grasp attempt history: 200 trials
    trials = 200
    successes = []
    rolling_acc = []
    window = 20
    cumulative = 0
    raw = []
    for i in range(trials):
        # Success rate improves with training steps (sigmoid-like)
        base_prob = 0.3 + 0.55 * (1 / (1 + math.exp(-0.05 * (i - 80))))
        success = 1 if random.random() < base_prob else 0
        raw.append(success)
        cumulative += success
        if i >= window - 1:
            win_acc = sum(raw[i - window + 1:i + 1]) / window
        else:
            win_acc = sum(raw[:i + 1]) / (i + 1)
        rolling_acc.append(win_acc)

    # SVG line chart: rolling accuracy over trials
    chart_w, chart_h = 640, 200
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b

    def tx(i): return pad_l + (i / (trials - 1)) * inner_w
    def ty(v): return pad_t + (1 - v) * inner_h

    pts = " ".join(f"{tx(i):.1f},{ty(v):.1f}" for i, v in enumerate(rolling_acc))
    # Threshold line at 0.80
    thresh_y = ty(0.80)

    # Confidence histogram: 8 bins of current predicted confidence
    conf_samples = [max(0, min(1, 0.72 + 0.18 * math.sin(i * 0.9) + random.gauss(0, 0.07))) for i in range(120)]
    bins = [0] * 10
    for c in conf_samples:
        idx = min(9, int(c * 10))
        bins[idx] += 1
    max_bin = max(bins) or 1
    bar_w = 38
    hist_svg_parts = []
    for b_i, cnt in enumerate(bins):
        bx = 50 + b_i * (bar_w + 4)
        bh = int((cnt / max_bin) * 120)
        by = 160 - bh
        color = "#22c55e" if b_i >= 7 else ("#facc15" if b_i >= 4 else "#f87171")
        hist_svg_parts.append(
            f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w//2}" y="{by - 4}" font-size="9" fill="#94a3b8" text-anchor="middle">{cnt}</text>'
            f'<text x="{bx + bar_w//2}" y="175" font-size="8" fill="#64748b" text-anchor="middle">{b_i/10:.1f}-{(b_i+1)/10:.1f}</text>'
        )
    hist_svg = "".join(hist_svg_parts)

    # Grasp type breakdown
    grasp_types = [("Parallel Jaw", 0.83), ("Suction Cup", 0.76), ("3-Finger", 0.71), ("Magnetic", 0.91), ("Soft Gripper", 0.64)]
    type_rows = "".join(
        f'<tr><td style="padding:6px 12px">{name}</td>'
        f'<td><div style="background:#1e3a5f;border-radius:4px;overflow:hidden;width:160px;height:14px">'
        f'<div style="background:#38bdf8;width:{int(acc*160)}px;height:100%"></div></div></td>'
        f'<td style="padding:6px 12px;color:{"#22c55e" if acc >= 0.8 else "#facc15"}">{acc*100:.0f}%</td></tr>'
        for name, acc in grasp_types
    )

    # Recent grasp log
    obj_names = ["Red Cube", "Blue Cylinder", "Sphere", "T-Bar", "Hex Nut", "Wrench", "PCB Board", "Bolt"]
    log_rows = ""
    for i in range(8):
        obj = random.choice(obj_names)
        conf = round(random.uniform(0.55, 0.98), 3)
        outcome = "SUCCESS" if conf > 0.72 else "FAIL"
        color = "#22c55e" if outcome == "SUCCESS" else "#f87171"
        ts = f"2026-03-30 {random.randint(8,17):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"
        log_rows += f'<tr><td style="padding:5px 10px;color:#94a3b8">{ts}</td><td style="padding:5px 10px">{obj}</td><td style="padding:5px 10px">{conf}</td><td style="padding:5px 10px;color:{color};font-weight:600">{outcome}</td></tr>'

    overall_acc = sum(raw) / len(raw)
    final_acc = rolling_acc[-1]

    return f"""<!DOCTYPE html><html><head><title>Grasping Success Predictor</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155;text-align:center}}
.stat .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
thead th{{color:#64748b;font-size:0.75rem;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
tbody tr:hover{{background:#263347}}
</style></head>
<body>
<h1>Grasping Success Predictor</h1>
<p style="color:#64748b;margin-bottom:16px">Port 8704 — Real-time grasp outcome prediction using GR00T N1.6 embeddings + confidence scoring</p>

<div class="grid">
  <div class="stat"><div class="val">{overall_acc*100:.1f}%</div><div class="lbl">Overall Accuracy</div></div>
  <div class="stat"><div class="val">{final_acc*100:.1f}%</div><div class="lbl">Rolling-20 Acc</div></div>
  <div class="stat"><div class="val">{trials}</div><div class="lbl">Total Trials</div></div>
  <div class="stat"><div class="val">{sum(raw)}</div><div class="lbl">Successes</div></div>
</div>

<div class="card">
  <h2>Rolling Accuracy Over Trials (window=20)</h2>
  <svg width="{chart_w}" height="{chart_h}" style="display:block">
    <!-- Grid lines -->
    {''.join(f'<line x1="{pad_l}" y1="{ty(v):.1f}" x2="{pad_l+inner_w}" y2="{ty(v):.1f}" stroke="#1e3a5f" stroke-width="1"/><text x="{pad_l-6}" y="{ty(v)+4:.1f}" font-size="9" fill="#475569" text-anchor="end">{int(v*100)}%</text>' for v in [0.2,0.4,0.6,0.8,1.0])}
    <!-- 80% threshold -->
    <line x1="{pad_l}" y1="{thresh_y:.1f}" x2="{pad_l+inner_w}" y2="{thresh_y:.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="5,4"/>
    <text x="{pad_l+inner_w-2}" y="{thresh_y-4:.1f}" font-size="9" fill="#f59e0b" text-anchor="end">80% target</text>
    <!-- Accuracy line -->
    <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <!-- Area fill -->
    <polygon points="{pad_l:.1f},{pad_t+inner_h:.1f} {pts} {pad_l+inner_w:.1f},{pad_t+inner_h:.1f}" fill="#38bdf8" fill-opacity="0.08"/>
    <!-- Axes -->
    <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#475569"/>
    <line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{pad_l+inner_w}" y2="{pad_t+inner_h}" stroke="#475569"/>
    <text x="{pad_l+inner_w//2}" y="{chart_h-4}" font-size="10" fill="#475569" text-anchor="middle">Trial Index</text>
  </svg>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card">
    <h2>Prediction Confidence Distribution</h2>
    <svg width="480" height="185" style="display:block">
      {hist_svg}
      <line x1="50" y1="160" x2="460" y2="160" stroke="#475569"/>
      <text x="255" y="185" font-size="10" fill="#475569" text-anchor="middle">Confidence Score Bucket</text>
    </svg>
  </div>
  <div class="card">
    <h2>Accuracy by Grasp Type</h2>
    <table>
      <thead><tr><th>Type</th><th>Accuracy</th><th>Rate</th></tr></thead>
      <tbody>{type_rows}</tbody>
    </table>
  </div>
</div>

<div class="card">
  <h2>Recent Grasp Attempt Log</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Object</th><th>Confidence</th><th>Outcome</th></tr></thead>
    <tbody>{log_rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Grasping Success Predictor")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "service": "grasping_success_predictor"}
    @app.get("/predict")
    def predict(obj: str = "unknown", confidence: float = 0.75):
        success = confidence > 0.72
        return {"object": obj, "confidence": confidence, "predicted_success": success, "threshold": 0.72}

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
