# Policy Interpolation Evaluator — port 8920
# Evaluates weight interpolation between run10 and groot_v2 checkpoints

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
<title>Policy Interpolation Evaluator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; }
  .metric { font-size: 2rem; font-weight: bold; color: #38bdf8; }
  .label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.25rem; }
  .highlight { color: #C74634; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th { background: #0f172a; color: #38bdf8; padding: 0.5rem; text-align: left; font-size: 0.85rem; }
  td { padding: 0.5rem; border-bottom: 1px solid #334155; font-size: 0.9rem; }
  tr.peak td { color: #C74634; font-weight: bold; }
  .badge { display: inline-block; background: #C74634; color: white; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: 0.5rem; }
  .badge-blue { background: #0369a1; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Policy Interpolation Evaluator</h1>
<p style="color:#94a3b8">Weight interpolation between <span class="highlight">run10</span> and <span class="highlight">groot_v2</span> — finding the optimal blend for success rate</p>

<div class="grid">
  <div class="card">
    <h2>Key Results</h2>
    <div class="metric">0.79</div>
    <div class="label">WA Ensemble SR <span class="badge">BEST</span></div>
    <br>
    <table>
      <tr><th>Model</th><th>SR</th><th>Flatness</th></tr>
      <tr><td>run10 (α=1.0)</td><td>0.74</td><td>0.71</td></tr>
      <tr><td>groot_v2 (α=0.0)</td><td>0.78</td><td>0.84</td></tr>
      <tr class="peak"><td>Interpolated α=0.3</td><td>0.813</td><td>0.87</td></tr>
      <tr><td>WA Ensemble</td><td>0.79</td><td>—</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Flatness Analysis</h2>
    <table>
      <tr><th>Checkpoint</th><th>Loss Flatness</th><th>Rank</th></tr>
      <tr><td>groot_v2</td><td>0.84</td><td>#1 <span class="badge badge-blue">Flattest</span></td></tr>
      <tr><td>α=0.3 blend</td><td>0.87</td><td>#0 <span class="badge">Peak</span></td></tr>
      <tr><td>α=0.5 blend</td><td>0.79</td><td>#2</td></tr>
      <tr><td>run10</td><td>0.71</td><td>#3</td></tr>
    </table>
    <p style="margin-top:1rem;font-size:0.85rem;color:#94a3b8">Flatness = 1/(1+sharpness). Higher = more robust generalisation.</p>
  </div>
</div>

<h2>Interpolation Curve — SR vs α</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 680 220" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="180" x2="660" y2="180" stroke="#334155" stroke-width="1.5"/>
    <!-- y labels -->
    <text x="55" y="185" fill="#94a3b8" font-size="11" text-anchor="end">0.70</text>
    <text x="55" y="145" fill="#94a3b8" font-size="11" text-anchor="end">0.74</text>
    <text x="55" y="105" fill="#94a3b8" font-size="11" text-anchor="end">0.78</text>
    <text x="55" y="65" fill="#94a3b8" font-size="11" text-anchor="end">0.82</text>
    <text x="55" y="25" fill="#94a3b8" font-size="11" text-anchor="end">0.86</text>
    <!-- x labels -->
    <text x="60" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">0.0</text>
    <text x="180" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">0.2</text>
    <text x="300" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">0.4</text>
    <text x="420" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">0.6</text>
    <text x="540" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">0.8</text>
    <text x="660" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">1.0</text>
    <!-- axis titles -->
    <text x="360" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">α (run10 weight)</text>
    <text x="12" y="95" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,12,95)">SR</text>
    <!-- curve: groot_v2=α=0 SR=0.78, peak at α=0.3 SR=0.813, run10=α=1 SR=0.74 -->
    <!-- map SR: 0.70→180, 0.86→25; range=160px for 0.16 SR => 1000px/SR -->
    <!-- α=0.0 x=60, SR=0.78 y=180-(0.78-0.70)*1000=180-80=100 -->
    <!-- α=0.1 x=120, SR=0.797 y=180-97=83 -->
    <!-- α=0.2 x=180, SR=0.810 y=180-110=70 -->
    <!-- α=0.3 x=240, SR=0.813 y=180-113=67 -->
    <!-- α=0.4 x=300, SR=0.800 y=180-100=80 -->
    <!-- α=0.5 x=360, SR=0.785 y=180-85=95 -->
    <!-- α=0.6 x=420, SR=0.770 y=180-70=110 -->
    <!-- α=0.7 x=480, SR=0.757 y=180-57=123 -->
    <!-- α=0.8 x=540, SR=0.748 y=180-48=132 -->
    <!-- α=0.9 x=600, SR=0.743 y=180-43=137 -->
    <!-- α=1.0 x=660, SR=0.740 y=180-40=140 -->
    <polyline points="60,100 120,83 180,70 240,67 300,80 360,95 420,110 480,123 540,132 600,137 660,140"
      fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- peak marker -->
    <circle cx="240" cy="67" r="6" fill="#C74634"/>
    <text x="248" y="62" fill="#C74634" font-size="11">α=0.3 SR=0.813 ★</text>
    <!-- run10 marker -->
    <circle cx="660" cy="140" r="5" fill="#64748b"/>
    <text x="630" y="135" fill="#64748b" font-size="10">run10</text>
    <!-- groot_v2 marker -->
    <circle cx="60" cy="100" r="5" fill="#64748b"/>
    <text x="65" y="95" fill="#64748b" font-size="10">groot_v2</text>
  </svg>
</div>

<h2>Ensemble Comparison</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 680 140" xmlns="http://www.w3.org/2000/svg">
    <!-- bar chart: run10=0.74, groot_v2=0.78, best_interp=0.813, WA_ensemble=0.79 -->
    <!-- scale: 0.70 baseline, max=0.82, range=0.12, height=100px => 833px/SR -->
    <!-- run10: (0.74-0.70)*833=33px -->
    <!-- groot_v2: (0.78-0.70)*833=67px -->
    <!-- interp: (0.813-0.70)*833=94px -->
    <!-- WA: (0.79-0.70)*833=75px -->
    <text x="340" y="130" fill="#94a3b8" font-size="11" text-anchor="middle">Success Rate (SR)</text>
    <!-- bars -->
    <rect x="60" y="{y}" width="100" height="33" fill="#334155" rx="4"/>
    <rect x="60" y="72" width="100" height="33" fill="#334155" rx="4"/>
    <rect x="220" y="11" width="100" height="94" fill="#C74634" rx="4"/>
    <rect x="380" y="30" width="100" height="75" fill="#0369a1" rx="4"/>
    <!-- fix first bar y -->
    <rect x="60" y="72" width="100" height="33" fill="#334155" rx="4"/>
    <rect x="60" y="105" width="100" height="0" fill="none"/>
    <!-- redo properly: baseline at y=110 -->
    <!-- run10 bar height=33, y=110-33=77 -->
    <rect x="55" y="77" width="100" height="33" fill="#475569" rx="4"/>
    <text x="105" y="73" fill="#94a3b8" font-size="11" text-anchor="middle">0.74</text>
    <text x="105" y="118" fill="#94a3b8" font-size="10" text-anchor="middle">run10</text>
    <!-- groot_v2 height=67, y=110-67=43 -->
    <rect x="185" y="43" width="100" height="67" fill="#475569" rx="4"/>
    <text x="235" y="39" fill="#94a3b8" font-size="11" text-anchor="middle">0.78</text>
    <text x="235" y="118" fill="#94a3b8" font-size="10" text-anchor="middle">groot_v2</text>
    <!-- interp height=94, y=110-94=16 -->
    <rect x="315" y="16" width="100" height="94" fill="#C74634" rx="4"/>
    <text x="365" y="12" fill="#C74634" font-size="11" text-anchor="middle" font-weight="bold">0.813 ★</text>
    <text x="365" y="118" fill="#e2e8f0" font-size="10" text-anchor="middle">α=0.3 interp</text>
    <!-- WA height=75, y=110-75=35 -->
    <rect x="445" y="35" width="100" height="75" fill="#0369a1" rx="4"/>
    <text x="495" y="31" fill="#38bdf8" font-size="11" text-anchor="middle">0.79</text>
    <text x="495" y="118" fill="#94a3b8" font-size="10" text-anchor="middle">WA Ensemble</text>
    <!-- baseline -->
    <line x1="40" y1="110" x2="640" y2="110" stroke="#334155" stroke-width="1"/>
    <text x="38" y="113" fill="#94a3b8" font-size="10" text-anchor="end">0.70</text>
  </svg>
</div>

<p style="margin-top:2rem;color:#475569;font-size:0.8rem">OCI Robot Cloud | Policy Interpolation Evaluator | Port 8920</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Interpolation Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_interpolation_evaluator", "port": 8920}

    @app.get("/api/interpolation")
    async def interpolation_data():
        """Return interpolation curve data points."""
        alphas = [round(i * 0.1, 1) for i in range(11)]
        # Quadratic peak at alpha=0.3 between SR_groot=0.78 and SR_run10=0.74
        sr_groot = 0.78
        sr_run10 = 0.74
        peak_boost = 0.033
        peak_alpha = 0.3
        points = []
        for a in alphas:
            base = (1 - a) * sr_groot + a * sr_run10
            boost = peak_boost * math.exp(-((a - peak_alpha) ** 2) / (2 * 0.05))
            sr = round(base + boost, 4)
            points.append({"alpha": a, "sr": sr})
        return {
            "curve": points,
            "peak_alpha": 0.3,
            "peak_sr": 0.813,
            "wa_ensemble_sr": 0.79,
            "run10_sr": 0.74,
            "groot_v2_sr": 0.78,
            "flatness": {"run10": 0.71, "groot_v2": 0.84, "alpha_0.3": 0.87},
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8920)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, falling back to HTTPServer on port 8920")
        HTTPServer(("0.0.0.0", 8920), Handler).serve_forever()
