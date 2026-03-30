"""
Cost Per Episode Service — port 8653
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
<title>Cost Per Episode | OCI Robot Cloud</title>
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
  .insight{margin-top:.75rem;color:#94a3b8;font-size:.82rem;}
</style>
</head>
<body>
<h1>Cost Per Episode Analysis</h1>
<p class="subtitle">OCI Robot Cloud · Infrastructure Cost Tracking · port 8653</p>

<div class="metrics">
  <div class="metric"><div class="val">$0.043</div><div class="lbl">Current sim episode cost (run10)</div></div>
  <div class="metric"><div class="val">$0.12</div><div class="lbl">Real episode cost</div></div>
  <div class="metric"><div class="val">$0.008</div><div class="lbl">DAgger step cost</div></div>
  <div class="metric"><div class="val">$0.43</div><div class="lbl">Per fine-tune run (5000 steps)</div></div>
  <div class="metric"><div class="val">4×</div><div class="lbl">Cost reduction over project</div></div>
</div>

<div class="grid">

<!-- SVG 1: Cost Breakdown Horizontal Stacked Bars -->
<div class="card">
  <h2>Cost Per Episode Breakdown by Segment</h2>
  <svg viewBox="0 0 540 260" xmlns="http://www.w3.org/2000/svg">
    <rect width="540" height="260" fill="#1e293b"/>
    <text x="68" y="72"  fill="#e2e8f0" font-size="12" text-anchor="end">Sim</text>
    <text x="68" y="132" fill="#e2e8f0" font-size="12" text-anchor="end">Real</text>
    <text x="68" y="192" fill="#e2e8f0" font-size="12" text-anchor="end">DAgger</text>
    <!-- Sim row -->
    <rect x="75" y="50" width="65"  height="30" fill="#38bdf8"/>
    <rect x="140" y="50" width="20"  height="30" fill="#22c55e"/>
    <rect x="160" y="50" width="13"  height="30" fill="#f59e0b"/>
    <rect x="173" y="50" width="10"  height="30" fill="#C74634"/>
    <text x="188" y="70" fill="#94a3b8" font-size="10">$0.043</text>
    <!-- Real row -->
    <rect x="75"  y="110" width="150" height="30" fill="#38bdf8"/>
    <rect x="225" y="110" width="63"  height="30" fill="#22c55e"/>
    <rect x="288" y="110" width="50"  height="30" fill="#f59e0b"/>
    <rect x="338" y="110" width="38"  height="30" fill="#C74634"/>
    <text x="382" y="130" fill="#94a3b8" font-size="10">$0.120</text>
    <!-- DAgger step row -->
    <rect x="75"  y="170" width="13"  height="30" fill="#38bdf8"/>
    <rect x="88"  y="170" width="3"   height="30" fill="#22c55e"/>
    <rect x="91"  y="170" width="3"   height="30" fill="#f59e0b"/>
    <rect x="94"  y="170" width="3"   height="30" fill="#C74634"/>
    <text x="103" y="190" fill="#94a3b8" font-size="10">$0.008</text>
    <!-- X axis -->
    <line x1="75" y1="215" x2="480" y2="215" stroke="#334155" stroke-width="1"/>
    <text x="75"  y="228" fill="#94a3b8" font-size="9" text-anchor="middle">$0</text>
    <text x="188" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">$0.045</text>
    <text x="300" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">$0.090</text>
    <text x="412" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">$0.135</text>
    <text x="240" y="245" fill="#94a3b8" font-size="10" text-anchor="middle">Cost per episode ($USD)</text>
    <!-- Legend -->
    <rect x="75"  y="250" width="10" height="8" fill="#38bdf8"/>
    <text x="89"  y="258" fill="#cbd5e1" font-size="9">Compute</text>
    <rect x="145" y="250" width="10" height="8" fill="#22c55e"/>
    <text x="159" y="258" fill="#cbd5e1" font-size="9">Storage</text>
    <rect x="210" y="250" width="10" height="8" fill="#f59e0b"/>
    <text x="224" y="258" fill="#cbd5e1" font-size="9">Network</text>
    <rect x="275" y="250" width="10" height="8" fill="#C74634"/>
    <text x="289" y="258" fill="#cbd5e1" font-size="9">API</text>
  </svg>
</div>

<!-- SVG 2: Cost Trend Line -->
<div class="card">
  <h2>Sim Episode Cost Trend (run1 → run10, with optimizations)</h2>
  <svg viewBox="0 0 540 300" xmlns="http://www.w3.org/2000/svg">
    <rect width="540" height="300" fill="#1e293b"/>
    <line x1="65" y1="20" x2="65" y2="240" stroke="#334155" stroke-width="1.5"/>
    <line x1="65" y1="240" x2="520" y2="240" stroke="#334155" stroke-width="1.5"/>
    <line x1="65" y1="190" x2="520" y2="190" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="65" y1="140" x2="520" y2="140" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="65" y1="90"  x2="520" y2="90"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="65" y1="40"  x2="520" y2="40"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="58" y="244" fill="#94a3b8" font-size="10" text-anchor="end">$0.00</text>
    <text x="58" y="194" fill="#94a3b8" font-size="10" text-anchor="end">$0.05</text>
    <text x="58" y="144" fill="#94a3b8" font-size="10" text-anchor="end">$0.10</text>
    <text x="58" y="94"  fill="#94a3b8" font-size="10" text-anchor="end">$0.15</text>
    <text x="58" y="44"  fill="#94a3b8" font-size="10" text-anchor="end">$0.20</text>
    <text x="18" y="140" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,18,140)">Cost / sim episode ($)</text>
    <text x="65"  y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R1</text>
    <text x="116" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R2</text>
    <text x="167" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R3</text>
    <text x="218" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R4</text>
    <text x="268" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R5</text>
    <text x="319" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R6</text>
    <text x="370" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R7</text>
    <text x="421" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R8</text>
    <text x="471" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R9</text>
    <text x="520" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">R10</text>
    <text x="292" y="272" fill="#94a3b8" font-size="11" text-anchor="middle">Fine-tune Run</text>
    <polyline
      points="65,60 116,73 167,92 218,107 268,125 319,143 370,160 421,175 471,188 520,197"
      fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="65"  cy="60"  r="4" fill="#38bdf8"/>
    <circle cx="116" cy="73"  r="4" fill="#38bdf8"/>
    <circle cx="167" cy="92"  r="4" fill="#38bdf8"/>
    <circle cx="218" cy="107" r="4" fill="#38bdf8"/>
    <circle cx="268" cy="125" r="4" fill="#38bdf8"/>
    <circle cx="319" cy="143" r="4" fill="#38bdf8"/>
    <circle cx="370" cy="160" r="4" fill="#38bdf8"/>
    <circle cx="421" cy="175" r="4" fill="#38bdf8"/>
    <circle cx="471" cy="188" r="4" fill="#38bdf8"/>
    <circle cx="520" cy="197" r="5" fill="#22c55e"/>
    <text x="65"  y="52" fill="#C74634" font-size="10" text-anchor="middle">$0.180</text>
    <text x="520" y="190" fill="#22c55e" font-size="10" text-anchor="middle">$0.043</text>
    <!-- Optimization annotations -->
    <line x1="167" y1="92" x2="167" y2="70" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>
    <text x="167" y="66" fill="#f59e0b" font-size="8" text-anchor="middle">Batch opt.</text>
    <line x1="268" y1="125" x2="268" y2="103" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>
    <text x="268" y="99" fill="#f59e0b" font-size="8" text-anchor="middle">Caching</text>
    <line x1="370" y1="160" x2="370" y2="138" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>
    <text x="370" y="134" fill="#f59e0b" font-size="8" text-anchor="middle">Compress</text>
    <line x1="471" y1="188" x2="471" y2="166" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>
    <text x="471" y="162" fill="#f59e0b" font-size="8" text-anchor="middle">GPU sched.</text>
    <text x="292" y="285" fill="#22c55e" font-size="10" text-anchor="middle">4× total reduction: $0.180 → $0.043</text>
  </svg>
</div>

<!-- SVG 3: Cost Efficiency Pareto Scatter -->
<div class="card" style="grid-column:1/-1;">
  <h2>Cost Efficiency vs SR Contribution — Pareto Frontier (20 checkpoints)</h2>
  <svg viewBox="0 0 700 300" xmlns="http://www.w3.org/2000/svg">
    <rect width="700" height="300" fill="#1e293b"/>
    <line x1="70" y1="20" x2="70" y2="250" stroke="#334155" stroke-width="1.5"/>
    <line x1="70" y1="250" x2="680" y2="250" stroke="#334155" stroke-width="1.5"/>
    <line x1="70" y1="200" x2="680" y2="200" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="150" x2="680" y2="150" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="70" y1="50"  x2="680" y2="50"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="195" y1="20" x2="195" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="320" y1="20" x2="320" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="445" y1="20" x2="445" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="570" y1="20" x2="570" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="62" y="254" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
    <text x="62" y="204" fill="#94a3b8" font-size="10" text-anchor="end">0.2</text>
    <text x="62" y="154" fill="#94a3b8" font-size="10" text-anchor="end">0.4</text>
    <text x="62" y="104" fill="#94a3b8" font-size="10" text-anchor="end">0.6</text>
    <text x="62" y="54"  fill="#94a3b8" font-size="10" text-anchor="end">0.8</text>
    <text x="70"  y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.04</text>
    <text x="195" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.07</text>
    <text x="320" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.10</text>
    <text x="445" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.13</text>
    <text x="570" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.16</text>
    <text x="680" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">$0.19</text>
    <text x="375" y="285" fill="#94a3b8" font-size="11" text-anchor="middle">Cost per Episode ($USD)</text>
    <text x="18" y="145" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,18,145)">SR Contribution</text>
    <!-- Pareto frontier -->
    <polyline points="70,64 125,75 180,93 240,112 310,135"
      fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>
    <text x="315" y="131" fill="#C74634" font-size="9">Pareto frontier</text>
    <!-- GR00T_v2 -->
    <circle cx="80"  cy="64"  r="8" fill="#22c55e" opacity="0.95"/>
    <text x="92" y="61" fill="#22c55e" font-size="10" font-weight="bold">GR00T_v2 ★</text>
    <!-- GR00T_v3 -->
    <circle cx="111" cy="100" r="6" fill="#38bdf8" opacity="0.85"/>
    <circle cx="125" cy="110" r="6" fill="#38bdf8" opacity="0.85"/>
    <circle cx="140" cy="105" r="6" fill="#38bdf8" opacity="0.85"/>
    <text x="150" y="103" fill="#38bdf8" font-size="9">GR00T_v3</text>
    <!-- DAgger -->
    <circle cx="236" cy="158" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="254" cy="165" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="270" cy="155" r="6" fill="#f59e0b" opacity="0.85"/>
    <circle cx="290" cy="170" r="6" fill="#f59e0b" opacity="0.85"/>
    <text x="295" y="155" fill="#f59e0b" font-size="9">DAgger</text>
    <!-- BC -->
    <circle cx="422" cy="238" r="6" fill="#ef4444" opacity="0.85"/>
    <circle cx="455" cy="232" r="6" fill="#ef4444" opacity="0.85"/>
    <circle cx="490" cy="240" r="6" fill="#ef4444" opacity="0.85"/>
    <text x="495" y="228" fill="#ef4444" font-size="9">BC</text>
    <!-- Other -->
    <circle cx="165" cy="130" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="200" cy="145" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="355" cy="190" r="5" fill="#94a3b8" opacity="0.6"/>
    <circle cx="390" cy="210" r="5" fill="#94a3b8" opacity="0.6"/>
    <!-- Legend -->
    <circle cx="100" cy="284" r="5" fill="#22c55e"/>
    <text x="110" y="288" fill="#cbd5e1" font-size="10">GR00T_v2 (Pareto opt.)</text>
    <circle cx="255" cy="284" r="5" fill="#38bdf8"/>
    <text x="265" y="288" fill="#cbd5e1" font-size="10">GR00T_v3</text>
    <circle cx="340" cy="284" r="5" fill="#f59e0b"/>
    <text x="350" y="288" fill="#cbd5e1" font-size="10">DAgger</text>
    <circle cx="415" cy="284" r="5" fill="#ef4444"/>
    <text x="425" y="288" fill="#cbd5e1" font-size="10">BC</text>
    <circle cx="480" cy="284" r="5" fill="#94a3b8"/>
    <text x="490" y="288" fill="#cbd5e1" font-size="10">Other</text>
  </svg>
  <p class="insight">GR00T_v2 sits on the Pareto frontier: lowest cost ($0.043/episode sim) with highest SR contribution (0.81). Cost declined 4× over 10 fine-tune runs through batching, caching, model compression, and GPU scheduling optimizations.</p>
</div>

</div><!-- end grid -->
<div style="margin-top:1.5rem;color:#475569;font-size:.8rem;">OCI Robot Cloud · Cost Per Episode · port 8653</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Per Episode", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cost_per_episode", "port": 8653}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8653)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "cost_per_episode", "port": 8653}).encode()
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
        srv = HTTPServer(("0.0.0.0", 8653), Handler)
        print("Serving on port 8653")
        srv.serve_forever()
