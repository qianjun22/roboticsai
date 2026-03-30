"""Hyperparameter Registry V2 — port 8930
Config lineage DAG, run diff, param sensitivity heatmap.
"""
import math
import random

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hyperparameter Registry V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: #0f172a; color: #38bdf8; padding: 8px 12px; text-align: left; }
  td { padding: 7px 12px; border-bottom: 1px solid #334155; }
  .badge-new { background: #C74634; color: #fff; border-radius: 4px; padding: 1px 7px; font-size: 0.75rem; margin-left: 6px; }
  .badge-same { background: #334155; color: #94a3b8; border-radius: 4px; padding: 1px 7px; font-size: 0.75rem; margin-left: 6px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .meta { color: #64748b; font-size: 0.82rem; margin-top: 6px; }
</style>
</head>
<body>
<h1>Hyperparameter Registry V2</h1>
<p class="meta">Config lineage tracking &bull; HPO sweep &rarr; best config &rarr; run10 &rarr; run11 &bull; Port 8930</p>

<h2>Config Lineage DAG</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 760 200" xmlns="http://www.w3.org/2000/svg">
    <!-- edges -->
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/>
      </marker>
    </defs>
    <line x1="160" y1="100" x2="285" y2="100" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>
    <line x1="430" y1="100" x2="555" y2="100" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>
    <!-- fork from best_config -->
    <line x1="355" y1="82" x2="555" y2="50" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,3" marker-end="url(#arrow)"/>
    <!-- node: HPO_sweep -->
    <rect x="10" y="75" width="150" height="50" rx="8" fill="#0f172a" stroke="#C74634" stroke-width="2"/>
    <text x="85" y="96" text-anchor="middle" fill="#C74634" font-size="13" font-weight="bold">HPO Sweep</text>
    <text x="85" y="114" text-anchor="middle" fill="#94a3b8" font-size="11">128 trials, 48h</text>
    <!-- node: best_config -->
    <rect x="290" y="75" width="140" height="50" rx="8" fill="#0f172a" stroke="#38bdf8" stroke-width="2"/>
    <text x="360" y="96" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">best_config</text>
    <text x="360" y="114" text-anchor="middle" fill="#94a3b8" font-size="11">loss=0.103, MAE=0.013</text>
    <!-- node: run10 -->
    <rect x="560" y="75" width="100" height="50" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="610" y="96" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">run10</text>
    <text x="610" y="114" text-anchor="middle" fill="#94a3b8" font-size="11">baseline</text>
    <!-- node: run11 (top fork) -->
    <rect x="560" y="20" width="100" height="50" rx="8" fill="#1e293b" stroke="#C74634" stroke-width="2"/>
    <text x="610" y="41" text-anchor="middle" fill="#C74634" font-size="13" font-weight="bold">run11</text>
    <text x="610" y="59" text-anchor="middle" fill="#94a3b8" font-size="11">reward=v3, EWC</text>
    <!-- run10 -> run11 continuation -->
    <line x1="660" y1="100" x2="700" y2="100" stroke="#334155" stroke-width="1.5" stroke-dasharray="4,3"/>
    <text x="710" y="104" fill="#64748b" font-size="11">(next)</text>
    <!-- label -->
    <text x="380" y="185" text-anchor="middle" fill="#64748b" font-size="11">Dashed = experimental fork &nbsp;&bull;&nbsp; Solid = promoted lineage</text>
  </svg>
</div>

<div class="grid2">
  <div>
    <h2>run10 vs run11 — Config Diff</h2>
    <div class="card">
      <table>
        <thead><tr><th>Parameter</th><th>run10</th><th>run11</th></tr></thead>
        <tbody>
          <tr><td>lr</td><td>1e-4</td><td>1e-4 <span class="badge-same">same</span></td></tr>
          <tr><td>batch_size</td><td>32</td><td>32 <span class="badge-same">same</span></td></tr>
          <tr><td>reward_shaping</td><td>v2</td><td>v3 <span class="badge-new">new</span></td></tr>
          <tr><td>ewc_lambda</td><td>0.0</td><td>0.4 <span class="badge-new">new</span></td></tr>
          <tr><td>warmup_steps</td><td>500</td><td>500 <span class="badge-same">same</span></td></tr>
          <tr><td>grad_clip</td><td>1.0</td><td>1.0 <span class="badge-same">same</span></td></tr>
          <tr><td>dropout</td><td>0.1</td><td>0.1 <span class="badge-same">same</span></td></tr>
          <tr><td>weight_decay</td><td>0.01</td><td>0.01 <span class="badge-same">same</span></td></tr>
          <tr><td>action_horizon</td><td>16</td><td>16 <span class="badge-same">same</span></td></tr>
          <tr><td>obs_horizon</td><td>2</td><td>2 <span class="badge-same">same</span></td></tr>
        </tbody>
      </table>
      <p class="meta" style="margin-top:10px">2 parameters changed: reward=v3, EWC=0.4 (continual learning regularizer)</p>
    </div>
  </div>

  <div>
    <h2>Param Sensitivity Heatmap</h2>
    <div class="card">
      <svg width="100%" viewBox="0 0 360 280" xmlns="http://www.w3.org/2000/svg">
        <!-- heatmap: rows=params, cols=metrics, color=sensitivity 0..1 -->
        <!-- params: lr, batch_size, dropout, weight_decay, grad_clip, ewc_lambda, reward_shaping -->
        <!-- metrics: MAE, Loss, SR, Throughput -->
        <style>
          .hlabel { font-size: 11px; fill: #94a3b8; }
          .htitle { font-size: 12px; fill: #38bdf8; font-weight: bold; }
        </style>
        <!-- column headers -->
        <text x="130" y="18" class="hlabel">MAE</text>
        <text x="185" y="18" class="hlabel">Loss</text>
        <text x="235" y="18" class="hlabel">SR</text>
        <text x="278" y="18" class="hlabel">Throughput</text>

        <!-- rows: sensitivity values computed as |d metric / d param| normalized -->
        <!-- lr: high sensitivity to all -->
        <text x="5" y="50" class="hlabel">lr</text>
        <rect x="110" y="30" width="50" height="28" rx="3" fill="#C74634" opacity="0.95"/>
        <rect x="165" y="30" width="50" height="28" rx="3" fill="#C74634" opacity="0.9"/>
        <rect x="220" y="30" width="50" height="28" rx="3" fill="#C74634" opacity="0.85"/>
        <rect x="275" y="30" width="50" height="28" rx="3" fill="#C74634" opacity="0.4"/>
        <text x="135" y="49" text-anchor="middle" fill="#fff" font-size="10">0.91</text>
        <text x="190" y="49" text-anchor="middle" fill="#fff" font-size="10">0.88</text>
        <text x="245" y="49" text-anchor="middle" fill="#fff" font-size="10">0.82</text>
        <text x="300" y="49" text-anchor="middle" fill="#fff" font-size="10">0.38</text>

        <!-- batch_size -->
        <text x="5" y="90" class="hlabel">batch_size</text>
        <rect x="110" y="68" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.55"/>
        <rect x="165" y="68" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.50"/>
        <rect x="220" y="68" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.35"/>
        <rect x="275" y="68" width="50" height="28" rx="3" fill="#C74634" opacity="0.75"/>
        <text x="135" y="87" text-anchor="middle" fill="#fff" font-size="10">0.55</text>
        <text x="190" y="87" text-anchor="middle" fill="#fff" font-size="10">0.50</text>
        <text x="245" y="87" text-anchor="middle" fill="#fff" font-size="10">0.35</text>
        <text x="300" y="87" text-anchor="middle" fill="#fff" font-size="10">0.73</text>

        <!-- dropout -->
        <text x="5" y="128" class="hlabel">dropout</text>
        <rect x="110" y="106" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.30"/>
        <rect x="165" y="106" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.33"/>
        <rect x="220" y="106" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.28"/>
        <rect x="275" y="106" width="50" height="28" rx="3" fill="#334155" opacity="0.9"/>
        <text x="135" y="125" text-anchor="middle" fill="#fff" font-size="10">0.29</text>
        <text x="190" y="125" text-anchor="middle" fill="#fff" font-size="10">0.32</text>
        <text x="245" y="125" text-anchor="middle" fill="#fff" font-size="10">0.27</text>
        <text x="300" y="125" text-anchor="middle" fill="#94a3b8" font-size="10">0.08</text>

        <!-- weight_decay -->
        <text x="5" y="166" class="hlabel">weight_decay</text>
        <rect x="110" y="144" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.22"/>
        <rect x="165" y="144" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.25"/>
        <rect x="220" y="144" width="50" height="28" rx="3" fill="#38bdf8" opacity="0.18"/>
        <rect x="275" y="144" width="50" height="28" rx="3" fill="#334155" opacity="0.9"/>
        <text x="135" y="163" text-anchor="middle" fill="#fff" font-size="10">0.21</text>
        <text x="190" y="163" text-anchor="middle" fill="#fff" font-size="10">0.24</text>
        <text x="245" y="163" text-anchor="middle" fill="#fff" font-size="10">0.17</text>
        <text x="300" y="163" text-anchor="middle" fill="#94a3b8" font-size="10">0.06</text>

        <!-- ewc_lambda -->
        <text x="5" y="204" class="hlabel">ewc_lambda</text>
        <rect x="110" y="182" width="50" height="28" rx="3" fill="#C74634" opacity="0.55"/>
        <rect x="165" y="182" width="50" height="28" rx="3" fill="#C74634" opacity="0.52"/>
        <rect x="220" y="182" width="50" height="28" rx="3" fill="#C74634" opacity="0.68"/>
        <rect x="275" y="182" width="50" height="28" rx="3" fill="#334155" opacity="0.9"/>
        <text x="135" y="201" text-anchor="middle" fill="#fff" font-size="10">0.54</text>
        <text x="190" y="201" text-anchor="middle" fill="#fff" font-size="10">0.51</text>
        <text x="245" y="201" text-anchor="middle" fill="#fff" font-size="10">0.66</text>
        <text x="300" y="201" text-anchor="middle" fill="#94a3b8" font-size="10">0.11</text>

        <!-- reward_shaping -->
        <text x="5" y="242" class="hlabel">reward</text>
        <rect x="110" y="220" width="50" height="28" rx="3" fill="#C74634" opacity="0.78"/>
        <rect x="165" y="220" width="50" height="28" rx="3" fill="#C74634" opacity="0.72"/>
        <rect x="220" y="220" width="50" height="28" rx="3" fill="#C74634" opacity="0.85"/>
        <rect x="275" y="220" width="50" height="28" rx="3" fill="#334155" opacity="0.9"/>
        <text x="135" y="239" text-anchor="middle" fill="#fff" font-size="10">0.77</text>
        <text x="190" y="239" text-anchor="middle" fill="#fff" font-size="10">0.71</text>
        <text x="245" y="239" text-anchor="middle" fill="#fff" font-size="10">0.84</text>
        <text x="300" y="239" text-anchor="middle" fill="#94a3b8" font-size="10">0.09</text>

        <!-- legend -->
        <text x="110" y="272" fill="#C74634" font-size="10">High</text>
        <rect x="130" y="262" width="30" height="10" rx="2" fill="#C74634" opacity="0.9"/>
        <rect x="164" y="262" width="30" height="10" rx="2" fill="#38bdf8" opacity="0.55"/>
        <rect x="198" y="262" width="30" height="10" rx="2" fill="#334155" opacity="0.9"/>
        <text x="230" y="272" fill="#38bdf8" font-size="10">Med</text>
        <text x="265" y="272" fill="#64748b" font-size="10">Low</text>
      </svg>
    </div>
  </div>
</div>

<h2>Registry Summary</h2>
<div class="card">
  <table>
    <thead><tr><th>Run</th><th>Config Hash</th><th>MAE</th><th>Loss</th><th>SR</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>HPO Sweep</td><td>a3f1c2d</td><td>0.023</td><td>0.187</td><td>42%</td><td style="color:#94a3b8">archived</td></tr>
      <tr><td>best_config</td><td>b7e9f01</td><td>0.013</td><td>0.103</td><td>67%</td><td style="color:#38bdf8">promoted</td></tr>
      <tr><td>run10</td><td>c2a4d56</td><td>0.013</td><td>0.099</td><td>70%</td><td style="color:#38bdf8">stable</td></tr>
      <tr><td>run11</td><td>d8f3b12</td><td>0.011</td><td>0.091</td><td>74%</td><td style="color:#C74634">experimental</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="Hyperparameter Registry V2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "hyperparameter_registry_v2", "port": 8930}

    @app.get("/api/lineage")
    def lineage():
        return {
            "nodes": [
                {"id": "hpo_sweep", "label": "HPO Sweep", "mae": 0.023, "loss": 0.187, "sr": 0.42},
                {"id": "best_config", "label": "best_config", "mae": 0.013, "loss": 0.103, "sr": 0.67},
                {"id": "run10", "label": "run10", "mae": 0.013, "loss": 0.099, "sr": 0.70},
                {"id": "run11", "label": "run11", "mae": 0.011, "loss": 0.091, "sr": 0.74},
            ],
            "edges": [
                {"from": "hpo_sweep", "to": "best_config"},
                {"from": "best_config", "to": "run10"},
                {"from": "best_config", "to": "run11"},
            ],
            "diff_run10_run11": [
                {"param": "reward_shaping", "run10": "v2", "run11": "v3", "changed": True},
                {"param": "ewc_lambda", "run10": 0.0, "run11": 0.4, "changed": True},
            ],
        }

    @app.get("/api/sensitivity")
    def sensitivity():
        params = ["lr", "batch_size", "dropout", "weight_decay", "ewc_lambda", "reward_shaping"]
        metrics = ["MAE", "Loss", "SR", "Throughput"]
        data = [
            [0.91, 0.88, 0.82, 0.38],
            [0.55, 0.50, 0.35, 0.73],
            [0.29, 0.32, 0.27, 0.08],
            [0.21, 0.24, 0.17, 0.06],
            [0.54, 0.51, 0.66, 0.11],
            [0.77, 0.71, 0.84, 0.09],
        ]
        return {"params": params, "metrics": metrics, "values": data}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8930)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a): pass

    if __name__ == "__main__":
        print("Serving on http://0.0.0.0:8930")
        HTTPServer(("0.0.0.0", 8930), Handler).serve_forever()
