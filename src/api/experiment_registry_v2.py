"""Experiment Registry V2 — FastAPI port 8902"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8902

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    experiments = [
        {"id": f"exp_{i:03d}", "type": random.choice(["BC","BC","BC","DAgger","DAgger","HPO"]), "sr": round(random.uniform(0.3, 0.95), 3),
         "data_hash": f"{random.randint(0xa000,0xffff):04x}", "config_hash": f"{random.randint(0xa000,0xffff):04x}", "seed": random.randint(0,9999),
         "repro": round(random.uniform(0.7, 1.0), 3)}
        for i in range(47)
    ]
    experiments.sort(key=lambda x: x["sr"], reverse=True)
    top10 = experiments[:10]
    rows = "".join(
        f'<tr><td>{e["id"]}</td><td>{e["type"]}</td><td>{e["sr"]}</td>'
        f'<td>{e["data_hash"]}</td><td>{e["config_hash"]}</td><td>{e["seed"]}</td><td>{e["repro"]}</td></tr>'
        for e in top10
    )
    bc_count, dagger_count, hpo_count = 23, 19, 5
    return f"""<!DOCTYPE html><html><head><title>Experiment Registry V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #334155;padding:6px 10px;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;margin:2px}}
.bc{{background:#1d4ed8}}.dagger{{background:#7c3aed}}.hpo{{background:#065f46}}</style></head>
<body><h1>Experiment Registry V2</h1>
<div class="card"><h2>Registry Overview — 47 Experiments</h2>
<p>
  <span class="badge bc">BC: {bc_count}</span>
  <span class="badge dagger">DAgger: {dagger_count}</span>
  <span class="badge hpo">HPO: {hpo_count}</span>
</p>
<p>Reproducibility scoring: <b>data_hash + config_hash + seed</b></p>
</div>
<div class="card"><h2>SR Trend (sample)</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Top-10 Experiments by Success Rate</h2>
<p>Search filters: type=<select><option>All</option><option>BC</option><option>DAgger</option><option>HPO</option></select> &nbsp; min_sr=<input type="number" value="0.5" step="0.05" style="width:60px;background:#0f172a;color:#e2e8f0;border:1px solid #334155"/></p>
<table><tr><th>ID</th><th>Type</th><th>SR</th><th>data_hash</th><th>config_hash</th><th>seed</th><th>repro_score</th></tr>
{rows}
</table>
</div>
<div class="card"><h2>Lineage Graph (47 experiments)</h2>
<svg width="450" height="80">
  <circle cx="60" cy="40" r="18" fill="#1d4ed8"/><text x="60" y="44" text-anchor="middle" font-size="10" fill="white">BC-base</text>
  <line x1="78" y1="40" x2="162" y2="40" stroke="#38bdf8" stroke-width="2"/>
  <circle cx="180" cy="40" r="18" fill="#7c3aed"/><text x="180" y="44" text-anchor="middle" font-size="10" fill="white">DAgger</text>
  <line x1="198" y1="40" x2="282" y2="40" stroke="#38bdf8" stroke-width="2"/>
  <circle cx="300" cy="40" r="18" fill="#065f46"/><text x="300" y="44" text-anchor="middle" font-size="10" fill="white">HPO</text>
  <line x1="318" y1="40" x2="402" y2="40" stroke="#38bdf8" stroke-width="2"/>
  <circle cx="420" cy="40" r="18" fill="#C74634"/><text x="420" y="44" text-anchor="middle" font-size="10" fill="white">Best</text>
</svg>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Experiment Registry V2")
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
