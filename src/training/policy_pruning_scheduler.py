"""
Policy Pruning Scheduler — OCI Robot Cloud (port 8636)
Cycle-144B: magnitude+activation hybrid pruning schedule manager.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="Policy Pruning Scheduler", version="1.0.0")

    HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Policy Pruning Scheduler — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.6rem;margin-bottom:4px}
  h2{color:#C74634;font-size:1.1rem;margin:28px 0 12px}
  .subtitle{color:#94a3b8;font-size:.85rem;margin-bottom:24px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px}
  .card.wide{grid-column:1/-1}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center}
  .metric .val{font-size:1.5rem;font-weight:700;color:#38bdf8}
  .metric .lbl{font-size:.75rem;color:#94a3b8;margin-top:4px}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>Policy Pruning Scheduler</h1>
<p class="subtitle">OCI Robot Cloud · Magnitude+Activation Hybrid · Port 8636</p>

<div class="metrics">
  <div class="metric"><div class="val">23%</div><div class="lbl">Better Structure (Hybrid vs Magnitude)</div></div>
  <div class="metric"><div class="val">1.4B</div><div class="lbl">Jetson Target Params</div></div>
  <div class="metric"><div class="val">37ms</div><div class="lbl">Jetson Inference Latency</div></div>
  <div class="metric"><div class="val">Round 2</div><div class="lbl">Optimal Sparsity (20%)</div></div>
</div>

<div class="grid">
  <!-- Gantt chart -->
  <div class="card wide">
    <h2>Pruning Schedule Gantt</h2>
    <svg viewBox="0 0 860 280" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="860" height="280" fill="#1e293b" rx="8"/>
      <line x1="160" y1="30" x2="160" y2="260" stroke="#334155" stroke-width="1"/>
      <line x1="300" y1="30" x2="300" y2="260" stroke="#334155" stroke-width="1"/>
      <line x1="440" y1="30" x2="440" y2="260" stroke="#334155" stroke-width="1"/>
      <line x1="580" y1="30" x2="580" y2="260" stroke="#334155" stroke-width="1"/>
      <line x1="720" y1="30" x2="720" y2="260" stroke="#334155" stroke-width="1"/>
      <line x1="840" y1="30" x2="840" y2="260" stroke="#334155" stroke-width="1"/>
      <text x="160" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 0</text>
      <text x="300" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 2</text>
      <text x="440" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 4</text>
      <text x="580" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 6</text>
      <text x="720" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 8</text>
      <text x="840" y="22" fill="#64748b" font-size="11" text-anchor="middle">Wk 10</text>
      <text x="10" y="72" fill="#94a3b8" font-size="12" font-weight="600">Round 1</text>
      <text x="10" y="87" fill="#64748b" font-size="10">10% sparse</text>
      <text x="10" y="152" fill="#94a3b8" font-size="12" font-weight="600">Round 2</text>
      <text x="10" y="167" fill="#64748b" font-size="10">20% sparse</text>
      <text x="10" y="232" fill="#94a3b8" font-size="12" font-weight="600">Round 3</text>
      <text x="10" y="247" fill="#64748b" font-size="10">30% sparse</text>
      <rect x="160" y="52" width="105" height="22" rx="4" fill="#38bdf8" opacity="0.85"/>
      <text x="212" y="67" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Train</text>
      <rect x="265" y="52" width="70" height="22" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="300" y="67" fill="#fff" font-size="10" font-weight="700" text-anchor="middle">Prune</text>
      <rect x="335" y="52" width="70" height="22" rx="4" fill="#f59e0b" opacity="0.85"/>
      <text x="370" y="67" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Eval</text>
      <rect x="405" y="52" width="105" height="22" rx="4" fill="#22c55e" opacity="0.85"/>
      <text x="457" y="67" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Retrain</text>
      <rect x="370" y="132" width="105" height="22" rx="4" fill="#38bdf8" opacity="0.85"/>
      <text x="422" y="147" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Train</text>
      <rect x="475" y="132" width="70" height="22" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="510" y="147" fill="#fff" font-size="10" font-weight="700" text-anchor="middle">Prune</text>
      <rect x="545" y="132" width="70" height="22" rx="4" fill="#f59e0b" opacity="0.85"/>
      <text x="580" y="147" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Eval</text>
      <rect x="615" y="132" width="105" height="22" rx="4" fill="#22c55e" opacity="0.85"/>
      <text x="667" y="147" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Retrain</text>
      <rect x="580" y="212" width="105" height="22" rx="4" fill="#38bdf8" opacity="0.85"/>
      <text x="632" y="227" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Train</text>
      <rect x="685" y="212" width="56" height="22" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="713" y="227" fill="#fff" font-size="10" font-weight="700" text-anchor="middle">Prune</text>
      <rect x="741" y="212" width="56" height="22" rx="4" fill="#f59e0b" opacity="0.85"/>
      <text x="769" y="227" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Eval</text>
      <rect x="797" y="212" width="42" height="22" rx="4" fill="#22c55e" opacity="0.85"/>
      <text x="818" y="227" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">Retrain</text>
      <rect x="170" y="258" width="12" height="10" rx="2" fill="#38bdf8"/>
      <text x="185" y="267" fill="#94a3b8" font-size="10">Train</text>
      <rect x="230" y="258" width="12" height="10" rx="2" fill="#C74634"/>
      <text x="245" y="267" fill="#94a3b8" font-size="10">Prune</text>
      <rect x="290" y="258" width="12" height="10" rx="2" fill="#f59e0b"/>
      <text x="305" y="267" fill="#94a3b8" font-size="10">Eval</text>
      <rect x="350" y="258" width="12" height="10" rx="2" fill="#22c55e"/>
      <text x="365" y="267" fill="#94a3b8" font-size="10">Retrain</text>
    </svg>
  </div>

  <!-- SR vs sparsity curve -->
  <div class="card">
    <h2>Success Rate vs Sparsity</h2>
    <svg viewBox="0 0 400 260" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="260" fill="#1e293b" rx="8"/>
      <line x1="50" y1="20" x2="50" y2="220" stroke="#475569" stroke-width="1.5"/>
      <line x1="50" y1="220" x2="380" y2="220" stroke="#475569" stroke-width="1.5"/>
      <text x="50"  y="235" fill="#64748b" font-size="10" text-anchor="middle">0%</text>
      <text x="116" y="235" fill="#64748b" font-size="10" text-anchor="middle">10%</text>
      <text x="182" y="235" fill="#64748b" font-size="10" text-anchor="middle">20%</text>
      <text x="248" y="235" fill="#64748b" font-size="10" text-anchor="middle">30%</text>
      <text x="314" y="235" fill="#64748b" font-size="10" text-anchor="middle">40%</text>
      <text x="380" y="235" fill="#64748b" font-size="10" text-anchor="middle">50%</text>
      <text x="215" y="252" fill="#64748b" font-size="10" text-anchor="middle">Sparsity (%)</text>
      <text x="45" y="224" fill="#64748b" font-size="10" text-anchor="end">0.60</text>
      <text x="45" y="184" fill="#64748b" font-size="10" text-anchor="end">0.65</text>
      <text x="45" y="144" fill="#64748b" font-size="10" text-anchor="end">0.70</text>
      <text x="45" y="104" fill="#64748b" font-size="10" text-anchor="end">0.75</text>
      <text x="45" y="64"  fill="#64748b" font-size="10" text-anchor="end">0.80</text>
      <line x1="50" y1="184" x2="380" y2="184" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="50" y1="144" x2="380" y2="144" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="50" y1="104" x2="380" y2="104" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="50" y1="64"  x2="380" y2="64"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <polyline points="50,76 116,76 182,84 248,108 314,148 380,188"
                fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="116" cy="76"  r="6" fill="#38bdf8" stroke="#0f172a" stroke-width="2"/>
      <circle cx="182" cy="84"  r="6" fill="#f59e0b" stroke="#0f172a" stroke-width="2"/>
      <circle cx="248" cy="108" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
      <text x="120" y="68"  fill="#38bdf8" font-size="10">R1: 0.78 (0%&#x2193;)</text>
      <text x="186" y="78"  fill="#f59e0b" font-size="10">R2: 0.77 (-0.01pp)</text>
      <text x="252" y="100" fill="#C74634" font-size="10">R3: 0.74 (-0.04pp)</text>
      <rect x="160" y="20" width="44" height="200" fill="#38bdf8" opacity="0.05" rx="2"/>
      <text x="182" y="36" fill="#38bdf8" font-size="9" text-anchor="middle" opacity="0.8">Optimal</text>
    </svg>
  </div>

  <!-- Parameter count waterfall -->
  <div class="card">
    <h2>Parameter Count Waterfall (Billions)</h2>
    <svg viewBox="0 0 400 260" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="260" fill="#1e293b" rx="8"/>
      <line x1="50" y1="20" x2="50" y2="220" stroke="#475569" stroke-width="1.5"/>
      <line x1="50" y1="220" x2="380" y2="220" stroke="#475569" stroke-width="1.5"/>
      <text x="45" y="224" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="45" y="157" fill="#64748b" font-size="10" text-anchor="end">1B</text>
      <text x="45" y="90"  fill="#64748b" font-size="10" text-anchor="end">2B</text>
      <text x="45" y="24"  fill="#64748b" font-size="10" text-anchor="end">3B</text>
      <line x1="50" y1="157" x2="380" y2="157" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="50" y1="90"  x2="380" y2="90"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <rect x="75"  y="20"  width="60" height="200" rx="4" fill="#38bdf8" opacity="0.7"/>
      <text x="105" y="14"  fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="700">3.0B</text>
      <text x="105" y="238" fill="#94a3b8" font-size="10" text-anchor="middle">Dense</text>
      <rect x="165" y="60"  width="60" height="160" rx="4" fill="#38bdf8" opacity="0.85"/>
      <text x="195" y="54"  fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="700">2.4B</text>
      <text x="195" y="238" fill="#94a3b8" font-size="10" text-anchor="middle">Round 1</text>
      <rect x="255" y="100" width="60" height="120" rx="4" fill="#f59e0b" opacity="0.85"/>
      <text x="285" y="94"  fill="#f59e0b" font-size="11" text-anchor="middle" font-weight="700">1.8B</text>
      <text x="285" y="238" fill="#94a3b8" font-size="10" text-anchor="middle">Round 2</text>
      <rect x="315" y="127" width="54" height="93" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="342" y="121" fill="#C74634" font-size="11" text-anchor="middle" font-weight="700">1.4B</text>
      <text x="342" y="238" fill="#94a3b8" font-size="10" text-anchor="middle">Round 3</text>
      <line x1="135" y1="60"  x2="165" y2="60"  stroke="#475569" stroke-width="1.5" stroke-dasharray="3,2"/>
      <line x1="225" y1="100" x2="255" y2="100" stroke="#475569" stroke-width="1.5" stroke-dasharray="3,2"/>
      <line x1="50" y1="127" x2="380" y2="127" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6,3"/>
      <text x="375" y="123" fill="#22c55e" font-size="9" text-anchor="end">Jetson target</text>
    </svg>
  </div>
</div>

</body>
</html>
"""

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "policy_pruning_scheduler",
            "port": 8636,
            "metrics": {
                "hybrid_improvement_pct": 23,
                "jetson_target_params_B": 1.4,
                "jetson_latency_ms": 37,
                "optimal_round": 2,
                "optimal_sparsity_pct": 20,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8636)

except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "policy_pruning_scheduler", "port": 8636}).encode()
                ct = "application/json"
            else:
                body = b"<h1>Policy Pruning Scheduler</h1><p>Install fastapi+uvicorn for full UI.</p>"
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", 8636), Handler).serve_forever()
