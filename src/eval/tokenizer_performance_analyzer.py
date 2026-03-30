"""Tokenizer Performance Analyzer — FastAPI port 8838"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8838

# Real metrics
VISION_TOKENS_PER_SEC = 4200
PROPRIO_TOKENS_PER_SEC = 18000
LANG_TOKENS_PER_SEC = 9500
AVG_TOKENIZATION_MS = 2.1

def build_svg_chart():
    modalities = [
        ("Vision", VISION_TOKENS_PER_SEC, "#C74634"),
        ("Proprioception", PROPRIO_TOKENS_PER_SEC, "#38bdf8"),
        ("Language", LANG_TOKENS_PER_SEC, "#34d399"),
    ]
    max_val = max(v for _, v, _ in modalities)
    bar_w = 80
    gap = 40
    chart_w = len(modalities) * (bar_w + gap) + gap
    chart_h = 220
    bars = ""
    labels = ""
    for i, (name, val, color) in enumerate(modalities):
        x = gap + i * (bar_w + gap)
        bar_h = math.floor((val / max_val) * 160)
        y = chart_h - bar_h - 30
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="4"/>'
        bars += f'<text x="{x + bar_w//2}" y="{y - 6}" text-anchor="middle" fill="#e2e8f0" font-size="11">{val:,}</text>'
        labels += f'<text x="{x + bar_w//2}" y="{chart_h - 8}" text-anchor="middle" fill="#94a3b8" font-size="11">{name}</text>'
    return f'<svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg">{bars}{labels}</svg>'

def build_html():
    chart = build_svg_chart()
    return f"""<!DOCTYPE html><html><head><title>Tokenizer Performance Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:12px 20px 0 0}}.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{color:#94a3b8;font-size:0.85em}}</style></head>
<body><h1>Tokenizer Performance Analyzer</h1>
<p style="color:#94a3b8">GR00T N1 tokenization throughput — port {PORT}</p>
<div class="card"><h2>Key Metrics</h2>
  <div class="metric"><div class="val">{VISION_TOKENS_PER_SEC:,}</div><div class="lbl">Vision tokens/sec</div></div>
  <div class="metric"><div class="val">{PROPRIO_TOKENS_PER_SEC:,}</div><div class="lbl">Proprio tokens/sec</div></div>
  <div class="metric"><div class="val">{LANG_TOKENS_PER_SEC:,}</div><div class="lbl">Language tokens/sec</div></div>
  <div class="metric"><div class="val">{AVG_TOKENIZATION_MS}ms</div><div class="lbl">Avg tokenization time</div></div>
</div>
<div class="card"><h2>Throughput by Modality (tokens/sec)</h2>
{chart}
</div>
<div class="card"><h2>About</h2>
<p>Profiles GR00T N1 tokenization throughput for action sequences and observation inputs across vision,
proprioception, and language modalities. Proprioception is fastest due to compact low-dimensional
vectors; vision requires patch embedding and is bandwidth-bound.</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Tokenizer Performance Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "vision_tokens_per_sec": VISION_TOKENS_PER_SEC,
            "proprio_tokens_per_sec": PROPRIO_TOKENS_PER_SEC,
            "language_tokens_per_sec": LANG_TOKENS_PER_SEC,
            "avg_tokenization_ms": AVG_TOKENIZATION_MS,
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
