"""
model_health_scorer.py — OCI Robot Cloud
Port 8673 | Health score gauge, per-dimension radar, degradation timeline
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
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Model Health Scorer — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:32px}
  h1{color:#C74634;font-size:1.7rem;font-weight:700;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:32px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .card h2{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:16px;text-transform:uppercase;letter-spacing:.06em}
  .metrics{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:32px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 24px;min-width:160px}
  .metric .val{color:#C74634;font-size:1.6rem;font-weight:700}
  .metric .lbl{color:#94a3b8;font-size:.78rem;margin-top:2px}
  svg{width:100%;height:auto;display:block}
  .legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
  .leg-item{display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8}
  .leg-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
  footer{margin-top:40px;color:#475569;font-size:.75rem;text-align:center}
</style>
</head>
<body>

<h1>Model Health Scorer</h1>
<p class="subtitle">OCI Robot Cloud — Production Model Health Dashboard</p>

<div class="metrics">
  <div class="metric"><div class="val">89/100</div><div class="lbl">groot_v2 health score</div></div>
  <div class="metric"><div class="val">82/100</div><div class="lbl">dagger_r9 (declining)</div></div>
  <div class="metric"><div class="val">&lt;75</div><div class="lbl">Auto-alert threshold</div></div>
  <div class="metric"><div class="val">226 ms</div><div class="lbl">Latency (amber zone)</div></div>
</div>

<div class="grid">

  <!-- Card 1: Health score arc gauge for groot_v2 -->
  <div class="card">
    <h2>Health Score Gauge — groot_v2</h2>
    <svg viewBox="0 0 460 240" xmlns="http://www.w3.org/2000/svg">
      <!-- Background arc -->
      <path d="M 80 200 A 150 150 0 0 1 380 200" fill="none" stroke="#1e3a5f" stroke-width="28" stroke-linecap="round"/>
      <!-- Red zone: 0-60 -->
      <path d="M 80 200 A 150 150 0 0 1 183.7 57.4" fill="none" stroke="#ef4444" stroke-width="26" stroke-linecap="butt" opacity="0.85"/>
      <!-- Amber zone: 60-80 -->
      <path d="M 183.7 57.4 A 150 150 0 0 1 351.4 111.8" fill="none" stroke="#f59e0b" stroke-width="26" stroke-linecap="butt" opacity="0.85"/>
      <!-- Green zone: 80-100 -->
      <path d="M 351.4 111.8 A 150 150 0 0 1 380 200" fill="none" stroke="#22c55e" stroke-width="26" stroke-linecap="butt" opacity="0.85"/>
      <!-- Zone labels -->
      <text x="100" y="195" fill="#ef4444" font-size="9" opacity="0.8">CRITICAL</text>
      <text x="198" y="44" fill="#f59e0b" font-size="9" opacity="0.8">WARN</text>
      <text x="350" y="105" fill="#22c55e" font-size="9" opacity="0.8">OK</text>
      <!-- Needle at score 89 -->
      <line x1="230" y1="200" x2="354.3" y2="155.2" stroke="#e2e8f0" stroke-width="3" stroke-linecap="round"/>
      <circle cx="230" cy="200" r="8" fill="#334155" stroke="#e2e8f0" stroke-width="2"/>
      <!-- Score label -->
      <text x="230" y="175" fill="#22c55e" font-size="28" font-weight="700" text-anchor="middle">89</text>
      <text x="230" y="193" fill="#94a3b8" font-size="11" text-anchor="middle">groot_v2</text>
      <!-- Scale labels -->
      <text x="68" y="215" fill="#64748b" font-size="9" text-anchor="middle">0</text>
      <text x="110" y="82" fill="#64748b" font-size="9" text-anchor="middle">25</text>
      <text x="230" y="36" fill="#64748b" font-size="9" text-anchor="middle">50</text>
      <text x="350" y="82" fill="#64748b" font-size="9" text-anchor="middle">75</text>
      <text x="392" y="215" fill="#64748b" font-size="9" text-anchor="middle">100</text>
    </svg>
  </div>

  <!-- Card 2: Per-dimension radar -->
  <div class="card">
    <h2>Per-Dimension Radar — 4 Models</h2>
    <svg viewBox="0 0 460 320" xmlns="http://www.w3.org/2000/svg">
      <!-- Grid circles -->
      <circle cx="230" cy="150" r="20" fill="none" stroke="#1e3a5f" stroke-width="1"/>
      <circle cx="230" cy="150" r="40" fill="none" stroke="#1e3a5f" stroke-width="1"/>
      <circle cx="230" cy="150" r="60" fill="none" stroke="#1e3a5f" stroke-width="1"/>
      <circle cx="230" cy="150" r="80" fill="none" stroke="#1e3a5f" stroke-width="1"/>
      <circle cx="230" cy="150" r="100" fill="none" stroke="#334155" stroke-width="1"/>
      <text x="233" y="132" fill="#475569" font-size="8">80</text>
      <text x="233" y="112" fill="#475569" font-size="8">100</text>
      <!-- Axis lines -->
      <line x1="230" y1="50" x2="230" y2="250" stroke="#334155" stroke-width="1"/>
      <line x1="143.4" y1="100" x2="316.6" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="143.4" y1="200" x2="316.6" y2="100" stroke="#334155" stroke-width="1"/>
      <!-- Axis labels -->
      <text x="230" y="43" fill="#64748b" font-size="9" text-anchor="middle">Success Rate</text>
      <text x="325" y="103" fill="#64748b" font-size="9">Latency</text>
      <text x="325" y="203" fill="#64748b" font-size="9">Calibration</text>
      <text x="230" y="262" fill="#64748b" font-size="9" text-anchor="middle">Robustness</text>
      <text x="78" y="203" fill="#64748b" font-size="9" text-anchor="end">Safety</text>
      <text x="132" y="103" fill="#64748b" font-size="9" text-anchor="end">Freshness</text>
      <!-- baseline -->
      <polygon points="230,90 307.7,105 306.4,182.5 230,208 168.4,186 186.6,130"
               fill="#94a3b8" fill-opacity="0.08" stroke="#94a3b8" stroke-width="1" stroke-opacity="0.5"/>
      <!-- bc_v3 -->
      <polygon points="230,75 303.2,107.5 291.6,186 230,218 160.7,190 178,122.5"
               fill="#818cf8" fill-opacity="0.12" stroke="#818cf8" stroke-width="1.5" stroke-opacity="0.7"/>
      <!-- dagger_r9 -->
      <polygon points="230,65 292.4,114 289.3,190 230,228 154.2,193.8 158.9,112.5"
               fill="#f59e0b" fill-opacity="0.12" stroke="#f59e0b" stroke-width="1.5" stroke-opacity="0.8"/>
      <!-- groot_v2 -->
      <polygon points="230,57 297.5,111 297.2,194 230,235 147.8,197.5 153.7,106.4"
               fill="#22c55e" fill-opacity="0.18" stroke="#22c55e" stroke-width="2" stroke-opacity="0.9"/>
    </svg>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#22c55e"></div>groot_v2 (89)</div>
      <div class="leg-item"><div class="leg-dot" style="background:#f59e0b"></div>dagger_r9 (82)</div>
      <div class="leg-item"><div class="leg-dot" style="background:#818cf8"></div>bc_v3 (71)</div>
      <div class="leg-item"><div class="leg-dot" style="background:#94a3b8"></div>baseline (63)</div>
    </div>
  </div>

  <!-- Card 3: Health degradation timeline -->
  <div class="card" style="grid-column:1/-1">
    <h2>Health Degradation Timeline — 30 Days (Production Model)</h2>
    <svg viewBox="0 0 860 240" xmlns="http://www.w3.org/2000/svg">
      <line x1="70" y1="20" x2="70" y2="200" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="200" x2="750" y2="200" stroke="#334155" stroke-width="1.5"/>
      <!-- Y labels + gridlines -->
      <text x="62" y="203" fill="#64748b" font-size="9" text-anchor="end">60</text>
      <text x="62" y="163" fill="#64748b" font-size="9" text-anchor="end">70</text>
      <line x1="70" y1="160" x2="750" y2="160" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="62" y="123" fill="#64748b" font-size="9" text-anchor="end">80</text>
      <line x1="70" y1="120" x2="750" y2="120" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="62" y="83" fill="#64748b" font-size="9" text-anchor="end">90</text>
      <line x1="70" y1="80" x2="750" y2="80" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="62" y="43" fill="#64748b" font-size="9" text-anchor="end">100</text>
      <line x1="70" y1="40" x2="750" y2="40" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <!-- Alert threshold at 75 -->
      <line x1="70" y1="140" x2="750" y2="140" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>
      <text x="755" y="143" fill="#ef4444" font-size="9" opacity="0.8">alert=75</text>
      <!-- X labels -->
      <text x="70" y="215" fill="#64748b" font-size="9" text-anchor="middle">1</text>
      <text x="257" y="215" fill="#64748b" font-size="9" text-anchor="middle">7</text>
      <text x="353" y="215" fill="#64748b" font-size="9" text-anchor="middle">10</text>
      <text x="540" y="215" fill="#64748b" font-size="9" text-anchor="middle">16</text>
      <text x="727" y="215" fill="#64748b" font-size="9" text-anchor="middle">22</text>
      <text x="750" y="215" fill="#64748b" font-size="9" text-anchor="middle">30</text>
      <text x="410" y="228" fill="#64748b" font-size="10" text-anchor="middle">Day</text>
      <!-- dagger_r9 line -->
      <polyline
        points="70,80 257,84 353,92 540,98 680,104 727,108 750,112"
        fill="none" stroke="#f59e0b" stroke-width="2" opacity="0.7" stroke-linejoin="round"/>
      <!-- groot_v2 line -->
      <polyline
        points="70,64 188,66 234,72.8 281,67.6 398,72 515,76 562,90.8 610,83.2 680,82 750,84"
        fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linejoin="round"/>
      <!-- Event 1: Day 8 data drift -->
      <circle cx="234" cy="72.8" r="5" fill="#f59e0b" stroke="#0f172a" stroke-width="1.5"/>
      <line x1="234" y1="68" x2="234" y2="30" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>
      <text x="224" y="26" fill="#f59e0b" font-size="8.5" text-anchor="middle">Data drift</text>
      <text x="224" y="17" fill="#f59e0b" font-size="8" text-anchor="middle">Day 8</text>
      <!-- Event 2: Day 22 latency spike -->
      <circle cx="562" cy="90.8" r="5" fill="#ef4444" stroke="#0f172a" stroke-width="1.5"/>
      <line x1="562" y1="86" x2="562" y2="30" stroke="#ef4444" stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>
      <text x="562" y="26" fill="#ef4444" font-size="8.5" text-anchor="middle">Latency spike</text>
      <text x="562" y="17" fill="#ef4444" font-size="8" text-anchor="middle">Day 22</text>
    </svg>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#22c55e"></div>groot_v2 (89 today)</div>
      <div class="leg-item"><div class="leg-dot" style="background:#f59e0b"></div>dagger_r9 (82, declining)</div>
      <div class="leg-item" style="color:#ef4444"><div class="leg-dot" style="background:#ef4444"></div>Auto-alert threshold (75)</div>
    </div>
  </div>

</div>

<footer>OCI Robot Cloud · Model Health Scorer · Port 8673 · © 2026 Oracle Corporation</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Health Scorer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "model_health_scorer",
            "port": 8673,
            "models": {
                "groot_v2": {"score": 89, "status": "healthy"},
                "dagger_r9": {"score": 82, "status": "declining"},
            },
            "alert_threshold": 75,
            "latency_ms": 226,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8673)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"model_health_scorer","port":8673}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("Serving on http://0.0.0.0:8673 (stdlib fallback)")
        HTTPServer(("0.0.0.0", 8673), Handler).serve_forever()
