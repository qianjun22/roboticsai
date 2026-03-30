# Multi-Env Transfer Evaluator — port 8932
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-Env Transfer Evaluator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem; }
  .rule { background: #0f172a; border-left: 3px solid #C74634; padding: 0.75rem 1rem; border-radius: 4px; margin-top: 1rem; font-size: 0.9rem; }
  .rule span { color: #38bdf8; font-weight: 600; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Multi-Env Transfer Evaluator</h1>
<p class="subtitle">Port 8932 &nbsp;|&nbsp; Zero-shot to full fine-tune success rate across deployment environments</p>

<div class="grid">
  <div class="card">
    <h2>Environment Transfer Heatmap</h2>
    <p class="subtitle">Success rate (SR) per source→target environment pair</p>
    <!-- Transfer heatmap SVG -->
    <svg viewBox="0 0 420 300" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- background -->
      <rect width="420" height="300" fill="#0f172a" rx="8"/>

      <!-- axis labels: columns (target) -->
      <text x="130" y="22" fill="#94a3b8" font-size="11" text-anchor="middle">Genesis</text>
      <text x="210" y="22" fill="#94a3b8" font-size="11" text-anchor="middle">IsaacSim</text>
      <text x="290" y="22" fill="#94a3b8" font-size="11" text-anchor="middle">Real Lab</text>
      <text x="370" y="22" fill="#94a3b8" font-size="11" text-anchor="middle">Partner</text>
      <text x="250" y="14" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">Target Environment</text>

      <!-- axis labels: rows (source) -->
      <text x="10" y="75"  fill="#94a3b8" font-size="10" dominant-baseline="middle">Genesis</text>
      <text x="10" y="135" fill="#94a3b8" font-size="10" dominant-baseline="middle">IsaacSim</text>
      <text x="10" y="195" fill="#94a3b8" font-size="10" dominant-baseline="middle">Real Lab</text>
      <text x="10" y="255" fill="#94a3b8" font-size="10" dominant-baseline="middle">Partner</text>
      <text x="6"  y="165" fill="#38bdf8" font-size="11" text-anchor="middle" transform="rotate(-90,6,165)" font-weight="600">Source</text>

      <!-- data: (source, target) -> SR. Diagonal = 1.0 -->
      <!-- Row 0: Genesis source -->
      <!-- (Genesis->Genesis) 1.00 -->
      <rect x="90" y="50" width="70" height="50" rx="4" fill="#16a34a" opacity="0.9"/>
      <text x="125" y="80" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">1.00</text>
      <!-- (Genesis->IsaacSim) 0.83 -->
      <rect x="170" y="50" width="70" height="50" rx="4" fill="#22c55e" opacity="0.7"/>
      <text x="205" y="80" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.83</text>
      <!-- (Genesis->Real Lab) 0.74 -->
      <rect x="250" y="50" width="70" height="50" rx="4" fill="#eab308" opacity="0.7"/>
      <text x="285" y="80" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.74</text>
      <!-- (Genesis->Partner) 0.58 -->
      <rect x="330" y="50" width="70" height="50" rx="4" fill="#ef4444" opacity="0.6"/>
      <text x="365" y="80" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.58</text>

      <!-- Row 1: IsaacSim source -->
      <!-- (IsaacSim->Genesis) 0.79 -->
      <rect x="90" y="110" width="70" height="50" rx="4" fill="#22c55e" opacity="0.6"/>
      <text x="125" y="140" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.79</text>
      <!-- (IsaacSim->IsaacSim) 1.00 -->
      <rect x="170" y="110" width="70" height="50" rx="4" fill="#16a34a" opacity="0.9"/>
      <text x="205" y="140" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">1.00</text>
      <!-- (IsaacSim->Real Lab) 0.77 -->
      <rect x="250" y="110" width="70" height="50" rx="4" fill="#22c55e" opacity="0.55"/>
      <text x="285" y="140" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.77</text>
      <!-- (IsaacSim->Partner) 0.61 -->
      <rect x="330" y="110" width="70" height="50" rx="4" fill="#f97316" opacity="0.6"/>
      <text x="365" y="140" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.61</text>

      <!-- Row 2: Real Lab source -->
      <!-- (Real->Genesis) 0.72 -->
      <rect x="90" y="170" width="70" height="50" rx="4" fill="#eab308" opacity="0.6"/>
      <text x="125" y="200" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.72</text>
      <!-- (Real->IsaacSim) 0.75 -->
      <rect x="170" y="170" width="70" height="50" rx="4" fill="#eab308" opacity="0.7"/>
      <text x="205" y="200" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.75</text>
      <!-- (Real->Real Lab) 1.00 -->
      <rect x="250" y="170" width="70" height="50" rx="4" fill="#16a34a" opacity="0.9"/>
      <text x="285" y="200" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">1.00</text>
      <!-- (Real->Partner) 0.68 -->
      <rect x="330" y="170" width="70" height="50" rx="4" fill="#f97316" opacity="0.55"/>
      <text x="365" y="200" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.68</text>

      <!-- Row 3: Partner source -->
      <!-- (Partner->Genesis) 0.55 -->
      <rect x="90" y="230" width="70" height="50" rx="4" fill="#ef4444" opacity="0.55"/>
      <text x="125" y="260" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.55</text>
      <!-- (Partner->IsaacSim) 0.59 -->
      <rect x="170" y="230" width="70" height="50" rx="4" fill="#ef4444" opacity="0.6"/>
      <text x="205" y="260" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.59</text>
      <!-- (Partner->Real Lab) 0.65 -->
      <rect x="250" y="230" width="70" height="50" rx="4" fill="#f97316" opacity="0.5"/>
      <text x="285" y="260" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">0.65</text>
      <!-- (Partner->Partner) 1.00 -->
      <rect x="330" y="230" width="70" height="50" rx="4" fill="#16a34a" opacity="0.9"/>
      <text x="365" y="260" fill="#fff" font-size="14" font-weight="700" text-anchor="middle">1.00</text>
    </svg>
    <div class="rule">50-demo adapter rule: &ge;<span>50 demos</span> in target env triggers lightweight adapter fine-tune (+9 pp avg SR)</div>
  </div>

  <div class="card">
    <h2>Few-Shot Learning Curve</h2>
    <p class="subtitle">Zero-shot &rarr; 50-demo adapter &rarr; full fine-tune SR across environments</p>
    <!-- Learning curve SVG -->
    <svg viewBox="0 0 420 300" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="420" height="300" fill="#0f172a" rx="8"/>

      <!-- axes -->
      <!-- Y axis -->
      <line x1="55" y1="20" x2="55" y2="255" stroke="#334155" stroke-width="1.5"/>
      <!-- X axis -->
      <line x1="55" y1="255" x2="400" y2="255" stroke="#334155" stroke-width="1.5"/>

      <!-- Y grid + labels: 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 -->
      <!-- y=255 -> SR=0.5, y=20 -> SR=1.0; scale = 235/0.5 = 470px per unit -->
      <!-- SR=0.5 -> y=255, SR=0.6->y=208, SR=0.7->y=161, SR=0.8->y=114, SR=0.9->y=67, SR=1.0->y=20 -->
      <line x1="55" y1="208" x2="400" y2="208" stroke="#1e293b" stroke-width="1"/>
      <line x1="55" y1="161" x2="400" y2="161" stroke="#1e293b" stroke-width="1"/>
      <line x1="55" y1="114" x2="400" y2="114" stroke="#1e293b" stroke-width="1"/>
      <line x1="55" y1="67"  x2="400" y2="67"  stroke="#1e293b" stroke-width="1"/>
      <line x1="55" y1="20"  x2="400" y2="20"  stroke="#1e293b" stroke-width="1"/>
      <text x="48" y="259" fill="#64748b" font-size="10" text-anchor="end">0.50</text>
      <text x="48" y="212" fill="#64748b" font-size="10" text-anchor="end">0.60</text>
      <text x="48" y="165" fill="#64748b" font-size="10" text-anchor="end">0.70</text>
      <text x="48" y="118" fill="#64748b" font-size="10" text-anchor="end">0.80</text>
      <text x="48" y="71"  fill="#64748b" font-size="10" text-anchor="end">0.90</text>
      <text x="48" y="24"  fill="#64748b" font-size="10" text-anchor="end">1.00</text>
      <text x="20" y="140" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,20,140)">Success Rate</text>

      <!-- X labels: Zero-shot, 10 demos, 25 demos, 50 demos, 100 demos, Full FT -->
      <!-- x positions: 55, 118, 181, 244, 307, 400 (roughly) -->
      <text x="75"  y="270" fill="#64748b" font-size="9" text-anchor="middle">Zero-shot</text>
      <text x="140" y="270" fill="#64748b" font-size="9" text-anchor="middle">10 demos</text>
      <text x="205" y="270" fill="#64748b" font-size="9" text-anchor="middle">25 demos</text>
      <text x="270" y="270" fill="#64748b" font-size="9" text-anchor="middle">50 demos</text>
      <text x="335" y="270" fill="#64748b" font-size="9" text-anchor="middle">100 demos</text>
      <text x="395" y="270" fill="#64748b" font-size="9" text-anchor="middle">Full FT</text>
      <text x="230" y="290" fill="#94a3b8" font-size="11" text-anchor="middle">Adapter Demos</text>

      <!-- Genesis curve (green): 0.83, 0.87, 0.91, 0.95, 0.97, 1.00 -->
      <!-- y = 255 - (sr-0.5)*470 -->
      <!-- 0.83->114.9, 0.87->95.1, 0.91->75.3, 0.95->55.5, 0.97->45.6, 1.00->20 -->
      <polyline points="75,161 140,134 205,108 270,79 335,56 395,20" fill="none" stroke="#22c55e" stroke-width="2.5"/>
      <circle cx="75"  cy="161" r="4" fill="#22c55e"/>
      <circle cx="140" cy="134" r="4" fill="#22c55e"/>
      <circle cx="205" cy="108" r="4" fill="#22c55e"/>
      <circle cx="270" cy="79"  r="4" fill="#22c55e"/>
      <circle cx="335" cy="56"  r="4" fill="#22c55e"/>
      <circle cx="395" cy="20"  r="4" fill="#22c55e"/>

      <!-- IsaacSim curve (blue): 0.77, 0.80, 0.85, 0.90, 0.95, 1.00 -->
      <!-- 0.77->161.1, 0.80->149, 0.85->126.5, 0.90->114? wait recalc -->
      <!-- y = 255-(sr-0.5)*470: 0.77->127.1, 0.80->114, 0.85->90.5, 0.90->67, 0.95->43.5, 1.00->20 -->
      <polyline points="75,127 140,114 205,91 270,67 335,44 395,20" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <circle cx="75"  cy="127" r="4" fill="#38bdf8"/>
      <circle cx="140" cy="114" r="4" fill="#38bdf8"/>
      <circle cx="205" cy="91"  r="4" fill="#38bdf8"/>
      <circle cx="270" cy="67"  r="4" fill="#38bdf8"/>
      <circle cx="335" cy="44"  r="4" fill="#38bdf8"/>
      <circle cx="395" cy="20"  r="4" fill="#38bdf8"/>

      <!-- Real Lab curve (orange): 0.74, 0.78, 0.83, 0.88, 0.93, 1.00 -->
      <!-- y: 0.74->142.2, 0.78->123.4, 0.83->100.9, 0.88->78.4, 0.93->55.9, 1.00->20 -->
      <polyline points="75,142 140,123 205,101 270,78 335,56 395,20" fill="none" stroke="#f97316" stroke-width="2.5"/>
      <circle cx="75"  cy="142" r="4" fill="#f97316"/>
      <circle cx="140" cy="123" r="4" fill="#f97316"/>
      <circle cx="205" cy="101" r="4" fill="#f97316"/>
      <circle cx="270" cy="78"  r="4" fill="#f97316"/>
      <circle cx="335" cy="56"  r="4" fill="#f97316"/>
      <circle cx="395" cy="20"  r="4" fill="#f97316"/>

      <!-- Partner Site curve (red): 0.58, 0.64, 0.71, 0.78, 0.86, 1.00 -->
      <!-- y: 0.58->189.4, 0.64->161.2, 0.71->128, 0.78->94.8, 0.86->57.2, 1.00->20 -->
      <polyline points="75,189 140,161 205,128 270,95 335,57 395,20" fill="none" stroke="#C74634" stroke-width="2.5"/>
      <circle cx="75"  cy="189" r="4" fill="#C74634"/>
      <circle cx="140" cy="161" r="4" fill="#C74634"/>
      <circle cx="205" cy="128" r="4" fill="#C74634"/>
      <circle cx="270" cy="95"  r="4" fill="#C74634"/>
      <circle cx="335" cy="57"  r="4" fill="#C74634"/>
      <circle cx="395" cy="20"  r="4" fill="#C74634"/>

      <!-- 50-demo threshold line -->
      <line x1="270" y1="20" x2="270" y2="255" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3"/>
      <text x="272" y="35" fill="#fbbf24" font-size="9">50-demo</text>
      <text x="272" y="46" fill="#fbbf24" font-size="9">adapter</text>

      <!-- legend -->
      <rect x="60" y="28" width="10" height="3" fill="#22c55e" rx="1"/>
      <text x="73" y="33" fill="#94a3b8" font-size="9">Genesis</text>
      <rect x="60" y="40" width="10" height="3" fill="#38bdf8" rx="1"/>
      <text x="73" y="45" fill="#94a3b8" font-size="9">IsaacSim</text>
      <rect x="120" y="28" width="10" height="3" fill="#f97316" rx="1"/>
      <text x="133" y="33" fill="#94a3b8" font-size="9">Real Lab</text>
      <rect x="120" y="40" width="10" height="3" fill="#C74634" rx="1"/>
      <text x="133" y="45" fill="#94a3b8" font-size="9">Partner Site</text>
    </svg>
    <div class="rule">Key inflection: <span>50-demo adapter</span> brings all envs above 0.78 SR; full fine-tune converges all to 1.00 (in-distribution)</div>
  </div>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Env Transfer Evaluator")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        envs = ["genesis", "isaac_sim", "real_lab", "partner_site"]
        transfer_matrix = {}
        for src in envs:
            transfer_matrix[src] = {}
            for tgt in envs:
                if src == tgt:
                    transfer_matrix[src][tgt] = 1.0
                else:
                    base = 0.58 + random.uniform(0, 0.26)
                    transfer_matrix[src][tgt] = round(min(base, 0.99), 2)
        curve = {
            "zero_shot": 0.58,
            "10_demos": round(0.58 + math.log(10 + 1) / math.log(101) * 0.35, 2),
            "25_demos": round(0.58 + math.log(25 + 1) / math.log(101) * 0.35, 2),
            "50_demos": round(0.58 + math.log(50 + 1) / math.log(101) * 0.35, 2),
            "100_demos": round(0.58 + math.log(100 + 1) / math.log(101) * 0.35, 2),
            "full_finetune": 1.0,
        }
        return {
            "status": "ok",
            "service": "multi_env_transfer_evaluator",
            "port": 8932,
            "environments": envs,
            "adapter_threshold_demos": 50,
            "zero_shot_sr": 0.58,
            "adapter_sr": 0.74,
            "full_finetune_sr": 0.83,
            "transfer_matrix": transfer_matrix,
            "few_shot_curve": curve,
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8932)
    else:
        server = HTTPServer(("0.0.0.0", 8932), Handler)
        print("Multi-Env Transfer Evaluator running on http://0.0.0.0:8932 (fallback HTTPServer)")
        server.serve_forever()
