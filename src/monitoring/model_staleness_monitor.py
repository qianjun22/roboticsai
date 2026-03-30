"""
Model Staleness Monitor — port 8614
OCI Robot Cloud | cycle-139A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler


def build_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Model Staleness Monitor | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.7rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:28px}
  h2{color:#C74634;font-size:1.1rem;margin-bottom:12px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px;margin-bottom:28px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:28px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}
  .metric-label{color:#94a3b8;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
  .metric-value{color:#38bdf8;font-size:1.6rem;font-weight:700}
  .metric-sub{color:#64748b;font-size:.78rem;margin-top:4px}
  .rules{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin-bottom:28px}
  .rules h2{margin-bottom:10px}
  .rule{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #0f172a;font-size:.9rem}
  .rule:last-child{border-bottom:none}
  .badge{padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
  .badge-red{background:#7f1d1d;color:#fca5a5}
  .badge-amber{background:#78350f;color:#fcd34d}
  .badge-green{background:#14532d;color:#86efac}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>Model Staleness Monitor</h1>
<p class="subtitle">OCI Robot Cloud &mdash; Port 8614 &mdash; Cycle-139A</p>

<div class="metrics">
  <div class="metric">
    <div class="metric-label">groot_v2 Age</div>
    <div class="metric-value" style="color:#22c55e">12 days</div>
    <div class="metric-sub">Drift score: 0.21 &mdash; STABLE</div>
  </div>
  <div class="metric">
    <div class="metric-label">dagger_r9 Age</div>
    <div class="metric-value" style="color:#f59e0b">31 days</div>
    <div class="metric-sub">Drift score: 0.48 &mdash; NEAR THRESHOLD</div>
  </div>
  <div class="metric">
    <div class="metric-label">bc Age</div>
    <div class="metric-value" style="color:#ef4444">47 days</div>
    <div class="metric-sub">Drift score: 0.62 &mdash; STALE</div>
  </div>
  <div class="metric">
    <div class="metric-label">Auto-Retrain Triggers</div>
    <div class="metric-value">1 active</div>
    <div class="metric-sub">bc model exceeds drift threshold</div>
  </div>
</div>

<div class="grid">

  <!-- SVG 1: SR degradation curves -->
  <div class="card">
    <h2>Model Age vs SR Degradation</h2>
    <svg viewBox="0 0 460 280" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- background -->
      <rect width="460" height="280" fill="#0f172a" rx="8"/>
      <!-- axes -->
      <line x1="50" y1="20" x2="50" y2="240" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="240" x2="440" y2="240" stroke="#334155" stroke-width="1.5"/>
      <!-- grid lines -->
      <line x1="50" y1="80" x2="440" y2="80" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="130" x2="440" y2="130" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="180" x2="440" y2="180" stroke="#1e293b" stroke-width="1"/>
      <!-- y axis labels -->
      <text x="44" y="84" fill="#94a3b8" font-size="10" text-anchor="end">0.90</text>
      <text x="44" y="134" fill="#94a3b8" font-size="10" text-anchor="end">0.75</text>
      <text x="44" y="184" fill="#94a3b8" font-size="10" text-anchor="end">0.60</text>
      <text x="44" y="244" fill="#94a3b8" font-size="10" text-anchor="end">0.45</text>
      <!-- x axis labels -->
      <text x="50"  y="255" fill="#94a3b8" font-size="10" text-anchor="middle">0</text>
      <text x="115" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">10</text>
      <text x="180" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">20</text>
      <text x="245" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">30</text>
      <text x="310" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">40</text>
      <text x="375" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">50</text>
      <text x="440" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">60</text>
      <!-- axis titles -->
      <text x="245" y="272" fill="#64748b" font-size="10" text-anchor="middle">Days Since Training</text>
      <text x="12" y="140" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90,12,140)">Success Rate</text>

      <!-- groot_v2 curve (green) — flat until 30, mild decay -->
      <polyline points="50,72 115,72 180,73 245,74 310,82 375,102 440,128"
                fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linejoin="round"/>
      <!-- dagger_r9 curve (amber) — slight earlier decay -->
      <polyline points="50,82 115,83 180,85 245,92 310,108 375,136 440,168"
                fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linejoin="round"/>
      <!-- bc curve (red) — steeper decay from day 25 -->
      <polyline points="50,95 115,96 180,100 245,115 310,145 375,185 440,220"
                fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linejoin="round"/>

      <!-- current positions -->
      <circle cx="127" cy="72" r="5" fill="#22c55e"/>
      <circle cx="251" cy="92" r="5" fill="#f59e0b"/>
      <circle cx="356" cy="178" r="5" fill="#ef4444"/>

      <!-- legend -->
      <rect x="310" y="24" width="10" height="3" fill="#22c55e" rx="1"/>
      <text x="324" y="28" fill="#e2e8f0" font-size="10">groot_v2</text>
      <rect x="310" y="36" width="10" height="3" fill="#f59e0b" rx="1"/>
      <text x="324" y="40" fill="#e2e8f0" font-size="10">dagger_r9</text>
      <rect x="310" y="48" width="10" height="3" fill="#ef4444" rx="1"/>
      <text x="324" y="52" fill="#e2e8f0" font-size="10">bc</text>
    </svg>
  </div>

  <!-- SVG 2: Data drift score bar chart -->
  <div class="card">
    <h2>Data Drift Score per Model</h2>
    <svg viewBox="0 0 460 280" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="280" fill="#0f172a" rx="8"/>
      <!-- axes -->
      <line x1="70" y1="20" x2="70" y2="220" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="220" x2="440" y2="220" stroke="#334155" stroke-width="1.5"/>
      <!-- grid -->
      <line x1="70" y1="60"  x2="440" y2="60"  stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="100" x2="440" y2="100" stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="140" x2="440" y2="140" stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="180" x2="440" y2="180" stroke="#1e293b" stroke-width="1"/>
      <!-- y labels -->
      <text x="64" y="64"  fill="#94a3b8" font-size="10" text-anchor="end">1.0</text>
      <text x="64" y="104" fill="#94a3b8" font-size="10" text-anchor="end">0.75</text>
      <text x="64" y="144" fill="#94a3b8" font-size="10" text-anchor="end">0.50</text>
      <text x="64" y="184" fill="#94a3b8" font-size="10" text-anchor="end">0.25</text>
      <text x="64" y="224" fill="#94a3b8" font-size="10" text-anchor="end">0.0</text>

      <!-- bars: scale y: 0=220, 1.0=60, so 160px = 1.0 -->
      <!-- groot_v2 drift=0.21 → height=33.6, y=186.4 -->
      <rect x="100" y="186" width="80" height="34" fill="#22c55e" opacity="0.85" rx="4"/>
      <text x="140" y="181" fill="#22c55e" font-size="11" text-anchor="middle">0.21</text>
      <text x="140" y="236" fill="#94a3b8" font-size="10" text-anchor="middle">groot_v2</text>

      <!-- dagger_r9 drift=0.48 → height=76.8, y=143.2 -->
      <rect x="210" y="143" width="80" height="77" fill="#f59e0b" opacity="0.85" rx="4"/>
      <text x="250" y="138" fill="#f59e0b" font-size="11" text-anchor="middle">0.48</text>
      <text x="250" y="236" fill="#94a3b8" font-size="10" text-anchor="middle">dagger_r9</text>

      <!-- bc drift=0.62 → height=99.2, y=120.8 -->
      <rect x="320" y="121" width="80" height="99" fill="#ef4444" opacity="0.85" rx="4"/>
      <text x="360" y="116" fill="#ef4444" font-size="11" text-anchor="middle">0.62</text>
      <text x="360" y="236" fill="#94a3b8" font-size="10" text-anchor="middle">bc</text>

      <!-- threshold line at 0.50 → y = 220 - (0.5*160) = 140 -->
      <line x1="70" y1="140" x2="440" y2="140" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,4"/>
      <text x="442" y="144" fill="#f59e0b" font-size="10">0.50 threshold</text>

      <text x="255" y="272" fill="#64748b" font-size="10" text-anchor="middle">Model</text>
      <text x="12" y="140" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90,12,140)">Drift Score</text>
    </svg>
  </div>

  <!-- SVG 3: Staleness gauge dashboard -->
  <div class="card" style="grid-column:1/-1">
    <h2>Staleness Score Dashboard</h2>
    <svg viewBox="0 0 460 200" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="200" fill="#0f172a" rx="8"/>

      <!-- Gauge helper: 3 gauges side by side -->
      <!-- groot_v2: composite score ~0.22 (GREEN) -->
      <!-- Semi-circle gauge at cx=80 cy=120 r=55 -->
      <path d="M 25,120 A 55,55 0 0,1 135,120" fill="none" stroke="#1e293b" stroke-width="14"/>
      <path d="M 25,120 A 55,55 0 0,1 135,120" fill="none" stroke="#22c55e" stroke-width="14"
            stroke-dasharray="173" stroke-dashoffset="135" stroke-linecap="round"/>
      <text x="80" y="115" fill="#22c55e" font-size="18" font-weight="700" text-anchor="middle">0.22</text>
      <text x="80" y="132" fill="#94a3b8" font-size="9" text-anchor="middle">STABLE</text>
      <text x="80" y="160" fill="#e2e8f0" font-size="11" font-weight="600" text-anchor="middle">groot_v2</text>
      <text x="80" y="173" fill="#64748b" font-size="9" text-anchor="middle">age 12d | drift 0.21</text>

      <!-- dagger_r9: composite score ~0.52 (AMBER) -->
      <path d="M 178,120 A 55,55 0 0,1 288,120" fill="none" stroke="#1e293b" stroke-width="14"/>
      <path d="M 178,120 A 55,55 0 0,1 288,120" fill="none" stroke="#f59e0b" stroke-width="14"
            stroke-dasharray="173" stroke-dashoffset="83" stroke-linecap="round"/>
      <text x="233" y="115" fill="#f59e0b" font-size="18" font-weight="700" text-anchor="middle">0.52</text>
      <text x="233" y="132" fill="#94a3b8" font-size="9" text-anchor="middle">WATCH</text>
      <text x="233" y="160" fill="#e2e8f0" font-size="11" font-weight="600" text-anchor="middle">dagger_r9</text>
      <text x="233" y="173" fill="#64748b" font-size="9" text-anchor="middle">age 31d | drift 0.48</text>

      <!-- bc: composite score ~0.78 (RED) -->
      <path d="M 330,120 A 55,55 0 0,1 440,120" fill="none" stroke="#1e293b" stroke-width="14"/>
      <path d="M 330,120 A 55,55 0 0,1 440,120" fill="none" stroke="#ef4444" stroke-width="14"
            stroke-dasharray="173" stroke-dashoffset="38" stroke-linecap="round"/>
      <text x="385" y="115" fill="#ef4444" font-size="18" font-weight="700" text-anchor="middle">0.78</text>
      <text x="385" y="132" fill="#94a3b8" font-size="9" text-anchor="middle">STALE</text>
      <text x="385" y="160" fill="#e2e8f0" font-size="11" font-weight="600" text-anchor="middle">bc</text>
      <text x="385" y="173" fill="#64748b" font-size="9" text-anchor="middle">age 47d | drift 0.62</text>

      <!-- title -->
      <text x="230" y="20" fill="#38bdf8" font-size="11" text-anchor="middle">Composite Staleness Score (age + drift weighted)</text>
    </svg>
  </div>

</div>

<div class="rules">
  <h2>Auto-Retrain Trigger Rules</h2>
  <div class="rule">
    <span class="badge badge-red">TRIGGERED</span>
    <span>Drift score &gt; 0.50 &mdash; <strong>bc</strong> at 0.62 exceeds threshold</span>
  </div>
  <div class="rule">
    <span class="badge badge-amber">WATCH</span>
    <span>Age &gt; 45 days &mdash; <strong>bc</strong> at 47d approaching limit; retrain queued</span>
  </div>
  <div class="rule">
    <span class="badge badge-amber">WATCH</span>
    <span>SR drop &gt; 3pp &mdash; <strong>dagger_r9</strong> monitoring active (age 31d)</span>
  </div>
  <div class="rule">
    <span class="badge badge-green">OK</span>
    <span>groot_v2 stable &mdash; 12 days old, drift 0.21, no action needed</span>
  </div>
</div>

<p style="color:#475569;font-size:.8rem;text-align:center">OCI Robot Cloud &mdash; Model Staleness Monitor &mdash; Port 8614 &mdash; &copy; 2026 Oracle</p>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Model Staleness Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "model_staleness_monitor", "port": 8614}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8614)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"model_staleness_monitor","port":8614}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("Model Staleness Monitor running on port 8614")
        HTTPServer(("0.0.0.0", 8614), Handler).serve_forever()
