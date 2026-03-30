"""
OCI Robot Cloud — Multi-Task Loss Weighting Service
Port 8634 | cycle-144A
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
<title>Multi-Task Loss Weighting | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.8rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.95rem;margin-bottom:32px}
  h2{color:#C74634;font-size:1.1rem;margin-bottom:16px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(540px,1fr));gap:28px;margin-bottom:32px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:32px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}
  .metric .val{color:#38bdf8;font-size:1.6rem;font-weight:700;margin-bottom:4px}
  .metric .lbl{color:#94a3b8;font-size:.82rem}
  svg{width:100%;height:auto;display:block}
  .legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px}
  .leg-item{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}
  .leg-dot{width:12px;height:12px;border-radius:2px;flex-shrink:0}
</style>
</head>
<body>
<h1>Multi-Task Loss Weighting</h1>
<p class="subtitle">GradNorm adaptive loss balancing across 6 manipulation tasks · Port 8634</p>

<div class="metrics">
  <div class="metric"><div class="val">0.847</div><div class="lbl">GradNorm Adaptive Best Avg SR</div></div>
  <div class="metric"><div class="val">2×</div><div class="lbl">pick_place faster convergence vs stack</div></div>
  <div class="metric"><div class="val">3×</div><div class="lbl">More steps for pour vs avg task</div></div>
  <div class="metric"><div class="val">+0.06pp</div><div class="lbl">GradNorm vs fixed weight baseline</div></div>
</div>

<div class="grid">
  <!-- Chart 1: Loss Weight Evolution Stacked Area -->
  <div class="card">
    <h2>Loss Weight Evolution (GradNorm Adaptive)</h2>
    <svg viewBox="0 0 500 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="500" height="300" fill="#1e293b"/>
      <g stroke="#334155" stroke-width="0.5">
        <line x1="60" y1="20" x2="60" y2="250"/>
        <line x1="60" y1="250" x2="480" y2="250"/>
        <line x1="60" y1="190" x2="480" y2="190" stroke-dasharray="4,3"/>
        <line x1="60" y1="130" x2="480" y2="130" stroke-dasharray="4,3"/>
        <line x1="60" y1="70" x2="480" y2="70" stroke-dasharray="4,3"/>
      </g>
      <text x="52" y="254" text-anchor="end" fill="#64748b" font-size="10">0%</text>
      <text x="52" y="194" text-anchor="end" fill="#64748b" font-size="10">25%</text>
      <text x="52" y="134" text-anchor="end" fill="#64748b" font-size="10">50%</text>
      <text x="52" y="74" text-anchor="end" fill="#64748b" font-size="10">75%</text>
      <text x="52" y="28" text-anchor="end" fill="#64748b" font-size="10">100%</text>
      <text x="60" y="268" text-anchor="middle" fill="#64748b" font-size="10">1</text>
      <text x="165" y="268" text-anchor="middle" fill="#64748b" font-size="10">5</text>
      <text x="270" y="268" text-anchor="middle" fill="#64748b" font-size="10">10</text>
      <text x="375" y="268" text-anchor="middle" fill="#64748b" font-size="10">15</text>
      <text x="480" y="268" text-anchor="middle" fill="#64748b" font-size="10">20</text>
      <text x="270" y="288" text-anchor="middle" fill="#94a3b8" font-size="11">Epoch</text>
      <!-- Area: pick_place (teal) -->
      <polygon points="60,177 165,183 270,188 375,193 480,199 480,250 375,250 270,250 165,250 60,250" fill="#0d9488" opacity="0.85"/>
      <!-- Area: stack (orange) -->
      <polygon points="60,119 165,129 270,138 375,147 480,158 480,199 375,193 270,188 165,183 60,177" fill="#f97316" opacity="0.85"/>
      <!-- Area: push (purple) -->
      <polygon points="60,78 165,90 270,101 375,112 480,121 480,158 375,147 270,138 165,129 60,119" fill="#8b5cf6" opacity="0.85"/>
      <!-- Area: reach (green) -->
      <polygon points="60,50 165,60 270,70 375,80 480,89 480,121 375,112 270,101 165,90 60,78" fill="#22c55e" opacity="0.85"/>
      <!-- Area: pour (red) -->
      <polygon points="60,32 165,41 270,49 375,54 480,43 480,89 375,80 270,70 165,60 60,50" fill="#C74634" opacity="0.85"/>
      <!-- Area: wipe (blue) -->
      <polygon points="60,20 165,30 270,40 375,50 480,20 480,43 375,54 270,49 165,41 60,32" fill="#38bdf8" opacity="0.85"/>
      <text x="270" y="14" text-anchor="middle" fill="#94a3b8" font-size="11">Adaptive weight share per task (stacked = 100%)</text>
    </svg>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#0d9488"></div>pick_place</div>
      <div class="leg-item"><div class="leg-dot" style="background:#f97316"></div>stack</div>
      <div class="leg-item"><div class="leg-dot" style="background:#8b5cf6"></div>push</div>
      <div class="leg-item"><div class="leg-dot" style="background:#22c55e"></div>reach</div>
      <div class="leg-item"><div class="leg-dot" style="background:#C74634"></div>pour</div>
      <div class="leg-item"><div class="leg-dot" style="background:#38bdf8"></div>wipe</div>
    </div>
  </div>

  <!-- Chart 2: Task Convergence Speed Scatter -->
  <div class="card">
    <h2>Task Convergence Speed vs Final Success Rate</h2>
    <svg viewBox="0 0 500 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="500" height="300" fill="#1e293b"/>
      <line x1="60" y1="20" x2="60" y2="250" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="250" x2="480" y2="250" stroke="#334155" stroke-width="1"/>
      <line x1="270" y1="20" x2="270" y2="250" stroke="#475569" stroke-width="1" stroke-dasharray="5,4"/>
      <line x1="60" y1="135" x2="480" y2="135" stroke="#475569" stroke-width="1" stroke-dasharray="5,4"/>
      <text x="155" y="38" text-anchor="middle" fill="#475569" font-size="9">Fast &amp; High SR</text>
      <text x="375" y="38" text-anchor="middle" fill="#475569" font-size="9">Slow &amp; High SR</text>
      <text x="155" y="245" text-anchor="middle" fill="#475569" font-size="9">Fast &amp; Low SR</text>
      <text x="375" y="245" text-anchor="middle" fill="#475569" font-size="9">Slow &amp; Low SR</text>
      <text x="52" y="254" text-anchor="end" fill="#64748b" font-size="10">0.5</text>
      <text x="52" y="195" text-anchor="end" fill="#64748b" font-size="10">0.65</text>
      <text x="52" y="135" text-anchor="end" fill="#64748b" font-size="10">0.78</text>
      <text x="52" y="75" text-anchor="end" fill="#64748b" font-size="10">0.91</text>
      <text x="52" y="28" text-anchor="end" fill="#64748b" font-size="10">1.0</text>
      <text x="60" y="268" text-anchor="middle" fill="#64748b" font-size="10">0</text>
      <text x="165" y="268" text-anchor="middle" fill="#64748b" font-size="10">500</text>
      <text x="270" y="268" text-anchor="middle" fill="#64748b" font-size="10">1000</text>
      <text x="375" y="268" text-anchor="middle" fill="#64748b" font-size="10">1500</text>
      <text x="480" y="268" text-anchor="middle" fill="#64748b" font-size="10">2000</text>
      <text x="270" y="288" text-anchor="middle" fill="#94a3b8" font-size="11">Convergence Steps</text>
      <text x="14" y="135" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,14,135)">Final SR</text>
      <!-- pick_place (teal) -->
      <circle cx="144" cy="62" r="9" fill="#0d9488" opacity="0.9"/>
      <text x="155" y="58" fill="#0d9488" font-size="10" font-weight="bold">pick_place</text>
      <!-- stack (orange) -->
      <circle cx="228" cy="89" r="9" fill="#f97316" opacity="0.9"/>
      <text x="239" y="85" fill="#f97316" font-size="10">stack</text>
      <!-- push (purple) -->
      <circle cx="186" cy="103" r="9" fill="#8b5cf6" opacity="0.9"/>
      <text x="197" y="99" fill="#8b5cf6" font-size="10">push</text>
      <!-- reach (green) -->
      <circle cx="123" cy="122" r="9" fill="#22c55e" opacity="0.9"/>
      <text x="134" y="118" fill="#22c55e" font-size="10">reach</text>
      <!-- wipe (blue) -->
      <circle cx="291" cy="167" r="9" fill="#38bdf8" opacity="0.9"/>
      <text x="302" y="163" fill="#38bdf8" font-size="10">wipe</text>
      <!-- pour (red) slowest -->
      <circle cx="438" cy="149" r="9" fill="#C74634" opacity="0.9"/>
      <text x="390" y="145" fill="#C74634" font-size="10">pour (slowest)</text>
    </svg>
  </div>

  <!-- Chart 3: SR Comparison Grouped Bars -->
  <div class="card" style="grid-column:1/-1">
    <h2>Success Rate: Uncertainty-Weighted vs Fixed vs GradNorm (per task)</h2>
    <svg viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="760" height="300" fill="#1e293b"/>
      <line x1="70" y1="20" x2="70" y2="240" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="240" x2="740" y2="240" stroke="#334155" stroke-width="1"/>
      <g stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3">
        <line x1="70" y1="200" x2="740" y2="200"/>
        <line x1="70" y1="160" x2="740" y2="160"/>
        <line x1="70" y1="120" x2="740" y2="120"/>
        <line x1="70" y1="80" x2="740" y2="80"/>
        <line x1="70" y1="40" x2="740" y2="40"/>
      </g>
      <text x="62" y="244" text-anchor="end" fill="#64748b" font-size="10">0.60</text>
      <text x="62" y="204" text-anchor="end" fill="#64748b" font-size="10">0.68</text>
      <text x="62" y="164" text-anchor="end" fill="#64748b" font-size="10">0.76</text>
      <text x="62" y="124" text-anchor="end" fill="#64748b" font-size="10">0.84</text>
      <text x="62" y="84" text-anchor="end" fill="#64748b" font-size="10">0.92</text>
      <text x="62" y="44" text-anchor="end" fill="#64748b" font-size="10">1.00</text>
      <!-- pick_place group -->
      <rect x="88" y="145" width="18" height="95" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="108" y="127" width="18" height="113" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="128" y="100" width="18" height="140" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="113" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">pick_place</text>
      <!-- stack group -->
      <rect x="193" y="168" width="18" height="72" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="213" y="155" width="18" height="86" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="233" y="127" width="18" height="113" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="218" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">stack</text>
      <!-- push group -->
      <rect x="298" y="159" width="18" height="81" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="318" y="150" width="18" height="90" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="338" y="141" width="18" height="99" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="323" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">push</text>
      <!-- reach group -->
      <rect x="403" y="172" width="18" height="68" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="423" y="163" width="18" height="77" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="443" y="159" width="18" height="81" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="428" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">reach</text>
      <!-- pour group -->
      <rect x="508" y="222" width="18" height="18" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="528" y="204" width="18" height="36" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="548" y="186" width="18" height="54" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="533" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">pour</text>
      <!-- wipe group -->
      <rect x="613" y="195" width="18" height="45" fill="#64748b" opacity="0.85" rx="2"/>
      <rect x="633" y="181" width="18" height="59" fill="#8b5cf6" opacity="0.85" rx="2"/>
      <rect x="653" y="168" width="18" height="72" fill="#C74634" opacity="0.85" rx="2"/>
      <text x="638" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">wipe</text>
      <!-- Legend -->
      <rect x="200" y="278" width="12" height="12" fill="#64748b" rx="2"/>
      <text x="216" y="289" fill="#94a3b8" font-size="11">Fixed Weight</text>
      <rect x="320" y="278" width="12" height="12" fill="#8b5cf6" rx="2"/>
      <text x="336" y="289" fill="#94a3b8" font-size="11">Uncertainty-Weighted</text>
      <rect x="490" y="278" width="12" height="12" fill="#C74634" rx="2"/>
      <text x="506" y="289" fill="#94a3b8" font-size="11">GradNorm Adaptive</text>
    </svg>
  </div>
</div>

<footer style="color:#475569;font-size:.8rem;margin-top:16px">OCI Robot Cloud · Multi-Task Loss Weighting · Port 8634</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Task Loss Weighting", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "multi_task_loss_weighting", "port": 8634}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8634)
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"multi_task_loss_weighting","port":8634}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI unavailable — starting stdlib HTTPServer on port 8634")
        HTTPServer(("0.0.0.0", 8634), Handler).serve_forever()
