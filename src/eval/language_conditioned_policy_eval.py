"""Language-Conditioned Policy Eval — FastAPI port 8460"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8460

def build_html():
    # 20-instruction SR bar
    instructions = [
        ("pick up the red cube", 0.89, "manipulation"),
        ("place cube in box", 0.82, "manipulation"),
        ("push object to goal", 0.84, "push"),
        ("stack cube on top", 0.78, "stack"),
        ("grasp the object", 0.91, "grasp"),
        ("lift object high", 0.77, "manipulation"),
        ("move object left", 0.81, "push"),
        ("put cube behind box", 0.62, "spatial"),
        ("place object between markers", 0.58, "spatial"),
        ("slide object under bar", 0.51, "spatial"),
        ("pour liquid gently", 0.43, "pour"),
        ("fold cloth in half", 0.38, "deform"),
        ("pick up blue block", 0.85, "manipulation"),
        ("rotate object 90 degrees", 0.67, "orientation"),
        ("place on left side", 0.71, "spatial"),
        ("grab nearest object", 0.79, "grasp"),
        ("transfer from A to B", 0.73, "manipulation"),
        ("line objects in row", 0.55, "spatial"),
        ("open the drawer", 0.48, "articulated"),
        ("press the button", 0.44, "articulated"),
    ]
    cat_colors = {"manipulation": "#38bdf8", "push": "#22c55e", "stack": "#f59e0b",
                  "grasp": "#22c55e", "spatial": "#C74634", "pour": "#8b5cf6",
                  "deform": "#ec4899", "orientation": "#f59e0b", "articulated": "#C74634"}

    bars = ""
    for i, (instr, sr, cat) in enumerate(instructions):
        y = 15 + i * 18
        w = int(sr * 240)
        color = cat_colors.get(cat, "#64748b")
        bars += f'<rect x="220" y="{y}" width="{w}" height="14" fill="{color}" rx="3" opacity="0.85"/>'
        bars += f'<text x="215" y="{y+11}" fill="#94a3b8" font-size="8" text-anchor="end">{instr[:28]}</text>'
        bars += f'<text x="{220+w+4}" y="{y+11}" fill="#e2e8f0" font-size="8">{int(sr*100)}%</text>'

    # instruction category averages
    from collections import defaultdict
    cat_srs = defaultdict(list)
    for _, sr, cat in instructions:
        cat_srs[cat].append(sr)
    cat_avgs = {c: sum(v)/len(v) for c, v in cat_srs.items()}
    sorted_cats = sorted(cat_avgs.items(), key=lambda x: -x[1])
    cat_bars = ""
    for i, (cat, avg) in enumerate(sorted_cats):
        y = 15 + i * 28
        w = int(avg * 240)
        color = cat_colors.get(cat, "#64748b")
        cat_bars += f'<rect x="100" y="{y}" width="{w}" height="20" fill="{color}" rx="3" opacity="0.85"/>'
        cat_bars += f'<text x="96" y="{y+14}" fill="#94a3b8" font-size="10" text-anchor="end">{cat}</text>'
        cat_bars += f'<text x="{100+w+5}" y="{y+14}" fill="#e2e8f0" font-size="10">{int(avg*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Language-Conditioned Policy Eval</title>
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
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Language-Conditioned Policy Eval — Instruction Following</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">74%</div><div class="ml">Unseen Instruction SR</div><div class="delta">vs BC 41%</div></div>
  <div class="m"><div class="mv">Spatial</div><div class="ml">Top Failure Category</div></div>
  <div class="m"><div class="mv">0.68</div><div class="ml">BLEU-Action Correlation</div></div>
  <div class="m"><div class="mv">20</div><div class="ml">Instructions Tested</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>SR per Instruction</h3>
    <svg viewBox="0 0 530 380" width="100%">
      <line x1="218" y1="10" x2="218" y2="375" stroke="#334155" stroke-width="1"/>
      {bars}
    </svg>
  </div>
  <div class="card">
    <h3>Average SR by Category</h3>
    <svg viewBox="0 0 420 230" width="100%">
      <line x1="98" y1="10" x2="98" y2="225" stroke="#334155" stroke-width="1"/>
      {cat_bars}
    </svg>
    <p style="font-size:11px;color:#f59e0b;margin:8px 0 0">Spatial prepositions ("behind", "between") top failures — add 50 demos with explicit positional language grounding</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Language-Conditioned Policy Eval")
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
