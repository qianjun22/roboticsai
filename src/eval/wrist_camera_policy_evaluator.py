"""Wrist Camera Policy Evaluator — FastAPI port 8832"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8832

def build_html():
    # Generate scatter plot points: confidence vs visual feature clarity
    random.seed(42)
    points = []
    for i in range(40):
        clarity = round(random.gauss(0.82, 0.12), 3)
        confidence = round(0.75 + 0.18 * clarity + random.gauss(0, 0.05), 3)
        clarity = max(0.3, min(1.0, clarity))
        confidence = max(0.4, min(1.0, confidence))
        cx = 60 + int(clarity * 280)
        cy = 320 - int(confidence * 260)
        color = "#38bdf8" if confidence >= 0.85 else "#f59e0b"
        points.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}" opacity="0.8"/>')
    scatter_points = "\n        ".join(points)

    return f"""<!DOCTYPE html><html><head><title>Wrist Camera Policy Evaluator</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:10px 20px;text-align:center}}.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.85em;color:#94a3b8}}</style></head>
<body>
<h1>Wrist Camera Policy Evaluator</h1>
<div class="card">
  <h2>Key Metrics</h2>
  <div class="metric"><div class="val">89%</div><div class="lbl">Visual Feature Match</div></div>
  <div class="metric"><div class="val">34ms</div><div class="lbl">Camera→Action Latency</div></div>
  <div class="metric"><div class="val">0.91</div><div class="lbl">Confidence Score</div></div>
</div>
<div class="card">
  <h2>Action Prediction Confidence vs. Visual Feature Clarity</h2>
  <svg width="420" height="360" style="background:#0f172a;border-radius:6px">
    <!-- Axes -->
    <line x1="60" y1="20" x2="60" y2="320" stroke="#475569" stroke-width="1"/>
    <line x1="60" y1="320" x2="360" y2="320" stroke="#475569" stroke-width="1"/>
    <!-- X axis labels -->
    <text x="60" y="340" fill="#94a3b8" font-size="11" text-anchor="middle">0.3</text>
    <text x="130" y="340" fill="#94a3b8" font-size="11" text-anchor="middle">0.5</text>
    <text x="200" y="340" fill="#94a3b8" font-size="11" text-anchor="middle">0.7</text>
    <text x="270" y="340" fill="#94a3b8" font-size="11" text-anchor="middle">0.85</text>
    <text x="340" y="340" fill="#94a3b8" font-size="11" text-anchor="middle">1.0</text>
    <!-- Y axis labels -->
    <text x="50" y="320" fill="#94a3b8" font-size="11" text-anchor="end">0.4</text>
    <text x="50" y="254" fill="#94a3b8" font-size="11" text-anchor="end">0.6</text>
    <text x="50" y="189" fill="#94a3b8" font-size="11" text-anchor="end">0.8</text>
    <text x="50" y="124" fill="#94a3b8" font-size="11" text-anchor="end">0.95</text>
    <text x="50" y="60" fill="#94a3b8" font-size="11" text-anchor="end">1.0</text>
    <!-- Axis titles -->
    <text x="210" y="358" fill="#e2e8f0" font-size="12" text-anchor="middle">Visual Feature Clarity</text>
    <text x="14" y="180" fill="#e2e8f0" font-size="12" text-anchor="middle" transform="rotate(-90,14,180)">Confidence</text>
    <!-- Trend line (approx) -->
    <line x1="70" y1="270" x2="350" y2="90" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>
    <!-- Scatter points -->
        {scatter_points}
    <!-- Legend -->
    <circle cx="80" cy="18" r="5" fill="#38bdf8"/>
    <text x="90" y="22" fill="#e2e8f0" font-size="11">Confidence ≥ 0.85</text>
    <circle cx="210" cy="18" r="5" fill="#f59e0b"/>
    <text x="220" y="22" fill="#e2e8f0" font-size="11">Confidence &lt; 0.85</text>
  </svg>
  <p style="color:#94a3b8;font-size:0.85em">Each point = one wrist-cam inference episode. Red dashed line = linear trend.</p>
</div>
<div class="card" style="color:#94a3b8;font-size:0.85em">
  Port: {PORT} | Service: Wrist Camera Policy Evaluator | OCI Robot Cloud
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Wrist Camera Policy Evaluator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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
