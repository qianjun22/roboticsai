"""OCI Region Failover — port 8955"""
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
<title>OCI Region Failover</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 18px; }
  .card .label { color: #94a3b8; font-size: 0.85rem; margin-bottom: 6px; }
  .card .value { font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }
  .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 24px; }
  .region-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
  .region-card { background: #1e293b; border-radius: 10px; padding: 18px; border-top: 4px solid #334155; }
  .region-card.primary { border-top-color: #4ade80; }
  .region-card.standby { border-top-color: #38bdf8; }
  .region-card.dr { border-top-color: #a78bfa; }
  .region-card h3 { font-size: 1rem; margin-bottom: 8px; }
  .region-card .role { font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 10px; display: inline-block; margin-bottom: 10px; }
  .primary .role { background: #166534; color: #bbf7d0; }
  .standby .role { background: #1d4ed8; color: #bfdbfe; }
  .dr .role { background: #5b21b6; color: #ddd6fe; }
  .region-stat { display: flex; justify-content: space-between; font-size: 0.82rem; padding: 4px 0; border-bottom: 1px solid #0f172a; }
  .region-stat .key { color: #64748b; }
  .region-stat .val { color: #e2e8f0; font-weight: 600; }
  .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  .dot-green { background: #4ade80; }
  .dot-blue { background: #38bdf8; }
  .dot-purple { background: #a78bfa; }
  footer { margin-top: 32px; color: #475569; font-size: 0.8rem; text-align: center; }
</style>
</head>
<body>
<h1>OCI Region Failover</h1>
<p style="color:#64748b;margin-bottom:20px;">Multi-region setup: Ashburn (primary) / Phoenix (standby) / San Jose (DR)</p>

<div class="grid">
  <div class="card">
    <div class="label">RTO Target</div>
    <div class="value" style="color:#38bdf8">15 min</div>
    <div class="sub">Last test achieved: 11 min</div>
  </div>
  <div class="card">
    <div class="label">RPO Target</div>
    <div class="value" style="color:#4ade80">0</div>
    <div class="sub">Synchronous replication</div>
  </div>
  <div class="card">
    <div class="label">Replication Lag (avg)</div>
    <div class="value" id="lag">340 ms</div>
    <div class="sub">Ashburn → Phoenix</div>
  </div>
  <div class="card">
    <div class="label">Overall Uptime</div>
    <div class="value" style="color:#4ade80">99.94%</div>
    <div class="sub">Rolling 90 days</div>
  </div>
  <div class="card">
    <div class="label">Last Failover Test</div>
    <div class="value" style="font-size:1.1rem">Mar 15</div>
    <div class="sub">RTO 11 min — PASS</div>
  </div>
  <div class="card">
    <div class="label">Active Regions</div>
    <div class="value">3 / 3</div>
    <div class="sub">All healthy</div>
  </div>
</div>

<h2>Region Health Grid</h2>
<div class="region-grid">
  <div class="region-card primary">
    <span class="status-dot dot-green"></span><h3>US East (Ashburn)</h3>
    <span class="role">PRIMARY</span>
    <div class="region-stat"><span class="key">Status</span><span class="val" style="color:#4ade80">ACTIVE</span></div>
    <div class="region-stat"><span class="key">Latency p50</span><span class="val">12 ms</span></div>
    <div class="region-stat"><span class="key">Throughput</span><span class="val">3.07 it/s</span></div>
    <div class="region-stat"><span class="key">GPU Nodes</span><span class="val">8×A100</span></div>
    <div class="region-stat"><span class="key">Repl. to PHX</span><span class="val">340 ms</span></div>
    <div class="region-stat"><span class="key">Repl. to SJC</span><span class="val">82 ms</span></div>
  </div>
  <div class="region-card standby">
    <span class="status-dot dot-blue"></span><h3>US West (Phoenix)</h3>
    <span class="role">STANDBY</span>
    <div class="region-stat"><span class="key">Status</span><span class="val" style="color:#38bdf8">STANDBY</span></div>
    <div class="region-stat"><span class="key">Latency p50</span><span class="val">14 ms</span></div>
    <div class="region-stat"><span class="key">Sync Lag</span><span class="val">340 ms</span></div>
    <div class="region-stat"><span class="key">GPU Nodes</span><span class="val">4×A100</span></div>
    <div class="region-stat"><span class="key">Promote ETA</span><span class="val">&lt;11 min</span></div>
    <div class="region-stat"><span class="key">Last Heartbeat</span><span class="val" id="phx-hb">2s ago</span></div>
  </div>
  <div class="region-card dr">
    <span class="status-dot dot-purple"></span><h3>US West 2 (San Jose)</h3>
    <span class="role">DISASTER RECOVERY</span>
    <div class="region-stat"><span class="key">Status</span><span class="val" style="color:#a78bfa">DR STANDBY</span></div>
    <div class="region-stat"><span class="key">Latency p50</span><span class="val">18 ms</span></div>
    <div class="region-stat"><span class="key">Async Lag</span><span class="val">82 ms</span></div>
    <div class="region-stat"><span class="key">GPU Nodes</span><span class="val">2×A100</span></div>
    <div class="region-stat"><span class="key">Activate ETA</span><span class="val">&lt;15 min</span></div>
    <div class="region-stat"><span class="key">Last Heartbeat</span><span class="val" id="sjc-hb">3s ago</span></div>
  </div>
</div>

<h2>Failover Decision Tree</h2>
<div class="chart-box">
  <svg viewBox="0 0 680 320" width="100%" style="display:block;">
    <!-- Root node -->
    <rect x="240" y="10" width="200" height="44" rx="8" fill="#1d4ed8" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="340" y="28" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="600">Health Check Failed?</text>
    <text x="340" y="46" fill="#bfdbfe" font-size="10" text-anchor="middle">Every 30s heartbeat</text>

    <!-- YES branch left -->
    <line x1="290" y1="54" x2="210" y2="100" stroke="#f97316" stroke-width="1.5"/>
    <text x="228" y="85" fill="#f97316" font-size="10">YES</text>
    <rect x="110" y="100" width="200" height="44" rx="8" fill="#7c2d12" stroke="#f97316" stroke-width="1.5"/>
    <text x="210" y="118" fill="#fde68a" font-size="12" text-anchor="middle" font-weight="600">3 consecutive misses?</text>
    <text x="210" y="136" fill="#fcd34d" font-size="10" text-anchor="middle">Grace period 90s</text>

    <!-- NO branch right (stay primary) -->
    <line x1="390" y1="54" x2="470" y2="100" stroke="#4ade80" stroke-width="1.5"/>
    <text x="452" y="85" fill="#4ade80" font-size="10">NO</text>
    <rect x="370" y="100" width="200" height="44" rx="8" fill="#166534" stroke="#4ade80" stroke-width="1.5"/>
    <text x="470" y="118" fill="#bbf7d0" font-size="12" text-anchor="middle" font-weight="600">Continue Normal Ops</text>
    <text x="470" y="136" fill="#86efac" font-size="10" text-anchor="middle">Ashburn PRIMARY active</text>

    <!-- YES → Promote Phoenix -->
    <line x1="210" y1="144" x2="210" y2="190" stroke="#f97316" stroke-width="1.5"/>
    <text x="215" y="175" fill="#f97316" font-size="10">YES</text>
    <rect x="110" y="190" width="200" height="44" rx="8" fill="#1d4ed8" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="210" y="208" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="600">Promote Phoenix</text>
    <text x="210" y="226" fill="#bfdbfe" font-size="10" text-anchor="middle">ETA &lt;11 min · RPO=0</text>

    <!-- Phoenix healthy? -->
    <line x1="210" y1="234" x2="210" y2="270" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="110" y="270" width="200" height="44" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="210" y="288" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="600">Phoenix healthy?</text>
    <text x="210" y="306" fill="#94a3b8" font-size="10" text-anchor="middle">Verify within 5 min</text>

    <!-- Phoenix NO → San Jose -->
    <line x1="110" y1="292" x2="60" y2="292" stroke="#a78bfa" stroke-width="1.5"/>
    <text x="70" y="283" fill="#a78bfa" font-size="10">NO</text>
    <rect x="10" y="270" width="50" height="44" rx="8" fill="#5b21b6" stroke="#a78bfa" stroke-width="1.5"/>
    <text x="35" y="288" fill="#ddd6fe" font-size="10" text-anchor="middle">SJC</text>
    <text x="35" y="303" fill="#c4b5fd" font-size="9" text-anchor="middle">DR</text>

    <!-- Phoenix YES → done -->
    <line x1="310" y1="292" x2="440" y2="292" stroke="#4ade80" stroke-width="1.5"/>
    <text x="370" y="283" fill="#4ade80" font-size="10">YES</text>
    <rect x="440" y="270" width="200" height="44" rx="8" fill="#166534" stroke="#4ade80" stroke-width="1.5"/>
    <text x="540" y="288" fill="#bbf7d0" font-size="12" text-anchor="middle" font-weight="600">Failover Complete</text>
    <text x="540" y="306" fill="#86efac" font-size="10" text-anchor="middle">Phoenix now PRIMARY</text>
  </svg>
</div>

<footer>OCI Robot Cloud · OCI Region Failover · port 8955</footer>

<script>
let phxAge = 2, sjcAge = 3;
let lag = 340;
function tick() {
  phxAge = Math.floor(Math.random() * 5) + 1;
  sjcAge = Math.floor(Math.random() * 6) + 1;
  lag = 320 + Math.floor(Math.random() * 40);
  document.getElementById('phx-hb').textContent = phxAge + 's ago';
  document.getElementById('sjc-hb').textContent = sjcAge + 's ago';
  document.getElementById('lag').textContent = lag + ' ms';
  setTimeout(tick, 3000);
}
tick();
</script>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Region Failover")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "oci_region_failover", "port": 8955}

    @app.get("/regions")
    def regions():
        lag = random.randint(320, 360)
        return {
            "primary": {
                "name": "Ashburn",
                "status": "ACTIVE",
                "repl_lag_to_phoenix_ms": lag,
                "repl_lag_to_sanjose_ms": random.randint(78, 88),
            },
            "standby": {
                "name": "Phoenix",
                "status": "STANDBY",
                "promote_eta_min": 11,
            },
            "dr": {
                "name": "San Jose",
                "status": "DR_STANDBY",
                "activate_eta_min": 15,
            },
            "rto_target_min": 15,
            "rpo_target_sec": 0,
            "last_test_rto_min": 11,
            "uptime_pct_90d": 99.94,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8955)
    else:
        print("Fallback: serving on port 8955")
        HTTPServer(("0.0.0.0", 8955), Handler).serve_forever()
