"""
Trajectory Smoothness Benchmark Service — port 8652
OCI Robot Cloud | cycle-148B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Trajectory Smoothness Benchmark | OCI Robot Cloud</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem;}
  h1{color:#38bdf8;font-size:1.8rem;margin-bottom:.25rem;}
  .subtitle{color:#94a3b8;font-size:.95rem;margin-bottom:2rem;}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:1.5rem;}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.5rem;}
  .card h2{color:#C74634;font-size:1.1rem;margin-bottom:1rem;}
  svg{width:100%;height:auto;display:block;}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem;}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1rem;}
  .metric .val{font-size:1.6rem;font-weight:700;color:#38bdf8;}
  .metric .lbl{font-size:.8rem;color:#94a3b8;margin-top:.25rem;}
  .legend{display:flex;flex-wrap:wrap;gap:.75rem;margin-top:.75rem;}
  .legend-item{display:flex;align-items:center;gap:.4rem;font-size:.8rem;color:#cbd5e1;}
  .legend-dot{width:12px;height:12px;border-radius:2px;}
</style>
</head>
<body>
<h1>Trajectory Smoothness Benchmark</h1>
<p class="subtitle">OCI Robot Cloud · Policy Smoothness Analysis · port 8652</p>

<div class="metrics">
  <div class="metric"><div class="val">0.87</div><div class="lbl">GR00T_v2 Smoothness Score (best)</div></div>
  <div class="metric"><div class="val">0.54</div><div class="lbl">BC Smoothness Score (baseline)</div></div>
  <div class="metric"><div class="val">+0.04pp</div><div class="lbl">SR gain per 0.1 smoothness</div></div>
  <div class="metric"><div class="val">r=0.71</div><div class="lbl">Smoothness–SR Correlation</div></div>
</div>

<div class="grid">

<!-- SVG 1: Smoothness Metric Comparison (grouped bars) -->
<div class="card">
  <h2>Smoothness Metric Comparison (lower = better)</h2>
  <svg viewBox="0 0 540 340" xmlns="http://www.w3.org/2000/svg">
    <rect width="540" height="340" fill="#1e293b"/>
    <line x1="80" y1="20" x2="80" y2="270" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="270" x2="530" y2="270" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="220" x2="530" y2="220" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="80" y1="170" x2="530" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="80" y1="120" x2="530" y2="120" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="80" y1="70" x2="530" y2="70" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
    <text x="72" y="274" fill="#94a3b8" font-size="11" text-anchor="end">0</text>
    <text x="72" y="224" fill="#94a3b8" font-size="11" text-anchor="end">0.2</text>
    <text x="72" y="174" fill="#94a3b8" font-size="11" text-anchor="end">0.4</text>
    <text x="72" y="124" fill="#94a3b8" font-size="11" text-anchor="end">0.6</text>
    <text x="72" y="74" fill="#94a3b8" font-size="11" text-anchor="end">0.8</text>
    <text x="15" y="160" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,15,160)">Metric Value (normalized)</text>
    <!-- Group: Jerk -->
    <rect x="90" y="80" width="18" height="190" fill="#ef4444"/>
    <rect x="110" y="100" width="18" height="170" fill="#f59e0b"/>
    <rect x="130" y="168" width="18" height="102" fill="#22c55e"/>
    <rect x="150" y="140" width="18" height="130" fill="#38bdf8"/>
    <text x="139" y="288" fill="#94a3b8" font-size="10" text-anchor="middle">Jerk</text>
    <!-- Group: Snap -->
    <rect x="195" y="95" width="18" height="175" fill="#ef4444"/>
    <rect x="215" y="110" width="18" height="160" fill="#f59e0b"/>
    <rect x="235" y="173" width="18" height="97" fill="#22c55e"/>
    <rect x="255" y="150" width="18" height="120" fill="#38bdf8"/>
    <text x="244" y="288" fill="#94a3b8" font-size="10" text-anchor="middle">Snap</text>
    <!-- Group: Vel Variance -->
    <rect x="300" y="88" width="18" height="182" fill="#ef4444"/>
    <rect x="320" y="105" width="18" height="165" fill="#f59e0b"/>
    <rect x="340" y="163" width="18" height="107" fill="#22c55e"/>
    <rect x="360" y="145" width="18" height="125" fill="#38bdf8"/>
    <text x="349" y="288" fill="#94a3b8" font-size="10" text-anchor="middle">Vel Var</text>
    <!-- Group: Accel RMS -->
    <rect x="405" y="93" width="18" height="177" fill="#ef4444"/>
    <rect x="425" y="108" width="18" height="162" fill="#f59e0b"/>
    <rect x="445" y="170" width="18" height="100" fill="#22c55e"/>
    <rect x="465" y="148" width="18" height="122" fill="#38bdf8"/>
    <text x="454" y="288" fill="#94a3b8" font-size="10" text-anchor="middle">Accel RMS</text>
    <!-- Legend -->
    <rect x="88" y="308" width="10" height="10" fill="#ef4444" rx="1"/>
    <text x="102" y="318" fill="#cbd5e1" font-size="10">BC</text>
    <rect x="140" y="308" width="10" height="10" fill="#f59e0b" rx="1"/>
    <text x="154" y="318" fill="#cbd5e1" font-size="10">DAgger_r9</text>
    <rect x="220" y="308" width="10" height="10" fill="#22c55e" rx="1"/>
    <text x="234" y="318" fill="#cbd5e1" font-size="10">GR00T_v2</text>
    <rect x="310" y="308" width="10" height="10" fill="#38bdf8" rx="1"/>
    <text x="324" y="318" fill="#cbd5e1" font-size="10">GR00T_v3</text>
  </svg>
</div>

<!-- SVG 2: Joint Smoothness Radar -->
<div class="card">
  <h2>Joint Smoothness Radar (7 joints, outer = smoother)</h2>
  <svg viewBox="0 0 540 360" xmlns="http://www.w3.org/2000/svg">
    <rect width="540" height="360" fill="#1e293b"/>
    <!-- Radar grid rings -->
    <polygon points="270,243 297,229 297,201 270,187 243,201 243,229" fill="none" stroke="#1e3a5f" stroke-width="1"/>
    <polygon points="270,216 324,183 324,117 270,84 216,117 216,183" fill="none" stroke="#1e3a5f" stroke-width="1"/>
    <polygon points="270,189 351,156 351,84 270,51 189,84 189,156" fill="none" stroke="#334155" stroke-width="1"/>
    <polygon points="270,162 378,129 378,51 270,18 162,51 162,129" fill="none" stroke="#334155" stroke-width="1"/>
    <!-- Axis lines -->
    <line x1="270" y1="160" x2="270" y2="30"  stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="390" y2="93"  stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="400" y2="210" stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="310" y2="295" stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="190" y2="295" stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="140" y2="210" stroke="#475569" stroke-width="1"/>
    <line x1="270" y1="160" x2="150" y2="93"  stroke="#475569" stroke-width="1"/>
    <!-- Joint labels -->
    <text x="270" y="24"  fill="#94a3b8" font-size="11" text-anchor="middle">J0</text>
    <text x="400" y="88"  fill="#94a3b8" font-size="11" text-anchor="start">J1</text>
    <text x="410" y="215" fill="#94a3b8" font-size="11" text-anchor="start">J2</text>
    <text x="315" y="308" fill="#94a3b8" font-size="11" text-anchor="middle">J3</text>
    <text x="185" y="308" fill="#94a3b8" font-size="11" text-anchor="middle">J4</text>
    <text x="120" y="215" fill="#94a3b8" font-size="11" text-anchor="end">J5</text>
    <text x="140" y="88"  fill="#94a3b8" font-size="11" text-anchor="end">J6</text>
    <!-- BC polygon -->
    <polygon points="270,97 354,116 357,175 295,261 225,261 183,175 186,116"
      fill="rgba(239,68,68,0.12)" stroke="#ef4444" stroke-width="2"/>
    <!-- DAgger_r9 polygon -->
    <polygon points="270,84 362,107 366,182 300,272 220,272 174,182 178,107"
      fill="rgba(245,158,11,0.12)" stroke="#f59e0b" stroke-width="2"/>
    <!-- GR00T_v2 polygon -->
    <polygon points="270,56 384,90 390,205 308,291 210,291 160,205 166,90"
      fill="rgba(34,197,94,0.15)" stroke="#22c55e" stroke-width="2.5"/>
    <!-- GR00T_v3 polygon -->
    <polygon points="270,66 376,97 381,196 304,284 216,284 159,196 156,100"
      fill="rgba(56,189,248,0.12)" stroke="#38bdf8" stroke-width="2"/>
    <!-- Legend -->
    <line x1="30" y1="328" x2="55" y2="328" stroke="#ef4444" stroke-width="2"/>
    <text x="60" y="332" fill="#cbd5e1" font-size="10">BC</text>
    <line x1="90" y1="328" x2="115" y2="328" stroke="#f59e0b" stroke-width="2"/>
    <text x="120" y="332" fill="#cbd5e1" font-size="10">DAgger_r9</text>
    <line x1="200" y1="328" x2="225" y2="328" stroke="#22c55e" stroke-width="2.5"/>
    <text x="230" y="332" fill="#cbd5e1" font-size="10">GR00T_v2</text>
    <line x1="310" y1="328" x2="335" y2="328" stroke="#38bdf8" stroke-width="2"/>
    <text x="340" y="332" fill="#cbd5e1" font-size="10">GR00T_v3</text>
  </svg>
</div>

<!-- SVG 3: Smoothness vs SR Scatter -->
<div class="card" style="grid-column:1/-1;">
  <h2>Smoothness Score vs Success Rate (20 checkpoints, r=0.71)</h2>
  <svg viewBox="0 0 700 300" xmlns="http://www.w3.org/2000/svg">
    <rect width="700" height="300" fill="#1e293b"/>
    <line x1="70" y1="20" x2="70" y2="250" stroke="#334155" stroke-width="1.5"/>
    <line x1="70" y1="250" x2="680" y2="250" stroke="#334155" stroke-width="1.5"/>
    <line x1="70" y1="200" x2="680" y2="200" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="150" x2="680" y2="150" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="50"  x2="680" y2="50"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="190" y1="20" x2="190" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="310" y1="20" x2="310" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="430" y1="20" x2="430" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="550" y1="20" x2="550" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="62" y="254" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
    <text x="62" y="204" fill="#94a3b8" font-size="10" text-anchor="end">0.2</text>
    <text x="62" y="154" fill="#94a3b8" font-size="10" text-anchor="end">0.4</text>
    <text x="62" y="104" fill="#94a3b8" font-size="10" text-anchor="end">0.6</text>
    <text x="62" y="54"  fill="#94a3b8" font-size="10" text-anchor="end">0.8</text>
    <text x="70"  y="265" fill="#94a3b8" font-size="10" text-anchor="middle">0.50</text>
    <text x="190" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">0.60</text>
    <text x="310" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">0.70</text>
    <text x="430" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">0.80</text>
    <text x="550" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">0.90</text>
    <text x="670" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">1.00</text>
    <text x="375" y="285" fill="#94a3b8" font-size="11" text-anchor="middle">Smoothness Score</text>
    <text x="18" y="145" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,18,145)">Success Rate</text>
    <!-- Trend line -->
    <line x1="70" y1="238" x2="650" y2="62" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>
    <text x="655" y="58" fill="#C74634" font-size="10">r=0.71</text>
    <!-- BC cluster -->
    <circle cx="118" cy="238" r="6" fill="#ef4444" opacity="0.85"/>
    <circle cx="126" cy="230" r="6" fill="#ef4444" opacity="0.85"/>
    <circle cx="108" cy="242" r="6" fill="#ef4444" opacity="0.85"/>
    <text x="130" y="226" fill="#ef4444" font-size="9">BC</text>
    <!-- DAgger cluster -->
    <circle cx="226" cy="204" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="246" cy="196" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="238" cy="210" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="258" cy="188" r="6" fill="#f59e0b" opacity="0.85"/>
    <!-- GR00T_v3 cluster -->
    <circle cx="358" cy="148" r="6" fill="#38bdf8" opacity="0.85"/>
    <circle cx="378" cy="138" r="6" fill="#38bdf8" opacity="0.85"/>
    <circle cx="366" cy="156" r="6" fill="#38bdf8" opacity="0.85"/>
    <circle cx="388" cy="130" r="6" fill="#38bdf8" opacity="0.85"/>
    <!-- GR00T_v2 cluster -->
    <circle cx="526" cy="73"  r="7" fill="#22c55e" opacity="0.9"/>
    <circle cx="546" cy="63"  r="7" fill="#22c55e" opacity="0.9"/>
    <circle cx="538" cy="80"  r="7" fill="#22c55e" opacity="0.9"/>
    <circle cx="558" cy="68"  r="7" fill="#22c55e" opacity="0.9"/>
    <text x="568" y="65" fill="#22c55e" font-size="9">GR00T_v2</text>
    <!-- Misc checkpoints -->
    <circle cx="176" cy="222" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="300" cy="176" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="456" cy="120" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="486" cy="108" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="414" cy="140" r="5" fill="#94a3b8" opacity="0.6"/>
    <!-- Legend -->
    <circle cx="100" cy="284" r="5" fill="#ef4444"/>
    <text x="110" y="288" fill="#cbd5e1" font-size="10">BC</text>
    <circle cx="150" cy="284" r="5" fill="#f59e0b"/>
    <text x="160" y="288" fill="#cbd5e1" font-size="10">DAgger_r9</text>
    <circle cx="240" cy="284" r="5" fill="#22c55e"/>
    <text x="250" y="288" fill="#cbd5e1" font-size="10">GR00T_v2</text>
    <circle cx="330" cy="284" r="5" fill="#38bdf8"/>
    <text x="340" y="288" fill="#cbd5e1" font-size="10">GR00T_v3</text>
    <circle cx="420" cy="284" r="5" fill="#94a3b8"/>
    <text x="430" y="288" fill="#cbd5e1" font-size="10">Other checkpoints</text>
  </svg>
  <div class="legend" style="margin-top:.5rem;">
    <span style="color:#94a3b8;font-size:.82rem;">Key insight: Action chunk boundary is the main differentiator — GR00T_v2 smoothest at 0.87 score; each +0.1 smoothness ≈ +0.04pp SR gain</span>
  </div>
</div>

</div><!-- end grid -->

<div style="margin-top:1.5rem;color:#475569;font-size:.8rem;">OCI Robot Cloud · Trajectory Smoothness Benchmark · port 8652</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Trajectory Smoothness Benchmark", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "trajectory_smoothness_benchmark", "port": 8652}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8652)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "trajectory_smoothness_benchmark", "port": 8652}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
        def log_message(self, *a): pass

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8652), Handler)
        print("Serving on port 8652")
        srv.serve_forever()
