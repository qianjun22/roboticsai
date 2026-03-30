"""Partner API Gateway V2 — port 8935
mTLS->rate_limit->auth->routing->circuit_breaker pipeline, API versioning, rate tier comparison.
"""

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
<title>Partner API Gateway V2</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px 0; }
  .subtitle { color: #94a3b8; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 12px; padding: 20px; }
  .card h3 { color: #38bdf8; font-size: 0.95rem; margin-bottom: 14px; }
  .metric { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .metric-label { color: #94a3b8; font-size: 0.88rem; }
  .metric-value { color: #f8fafc; font-weight: 600; font-size: 0.95rem; }
  .badge { background: #C74634; color: white; border-radius: 6px; padding: 2px 8px; font-size: 0.78rem; }
  .badge-blue { background: #0284c7; }
  .badge-green { background: #059669; }
  .badge-yellow { background: #d97706; }
  .layer { display: flex; align-items: center; gap: 12px; background: #0f172a; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }
  .layer-num { background: #C74634; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700; flex-shrink: 0; }
  .layer-info { flex: 1; }
  .layer-title { color: #f8fafc; font-size: 0.9rem; font-weight: 600; }
  .layer-detail { color: #94a3b8; font-size: 0.78rem; margin-top: 2px; }
  .layer-latency { color: #38bdf8; font-size: 0.82rem; font-weight: 600; }
  .tier-table { width: 100%; border-collapse: collapse; }
  .tier-table th { color: #38bdf8; font-size: 0.82rem; text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }
  .tier-table td { color: #e2e8f0; font-size: 0.85rem; padding: 8px 10px; border-bottom: 1px solid #1e293b; }
  .tier-table tr:last-child td { border-bottom: none; }
  .bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .bar-label { color: #94a3b8; font-size: 0.82rem; width: 80px; flex-shrink: 0; }
  .bar-bg { flex: 1; background: #0f172a; border-radius: 4px; height: 18px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; font-size: 0.75rem; font-weight: 600; color: white; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .footer { color: #475569; font-size: 0.78rem; margin-top: 32px; text-align: center; }
  .version-row { display: flex; gap: 12px; margin-bottom: 8px; }
  .version-chip { background: #0f172a; border-radius: 8px; padding: 10px 16px; flex: 1; text-align: center; }
  .version-chip .ver { color: #38bdf8; font-size: 1.1rem; font-weight: 700; }
  .version-chip .ver-label { color: #94a3b8; font-size: 0.78rem; margin-top: 2px; }
</style>
</head>
<body>
<h1>Partner API Gateway V2</h1>
<p class="subtitle">mTLS &rarr; rate_limit &rarr; auth &rarr; routing &rarr; circuit_breaker &middot; 99.97% availability &middot; Port 8935</p>

<div class="grid">
  <div class="card">
    <h3>Gateway Health</h3>
    <div class="metric"><span class="metric-label">Availability (30d)</span><span class="metric-value badge badge-green">99.97%</span></div>
    <div class="metric"><span class="metric-label">Active Connections</span><span class="metric-value">1,284</span></div>
    <div class="metric"><span class="metric-label">Avg Latency</span><span class="metric-value badge">4.7 ms</span></div>
    <div class="metric"><span class="metric-label">Requests / min</span><span class="metric-value">48,320</span></div>
    <div class="metric"><span class="metric-label">Error Rate</span><span class="metric-value badge badge-blue">0.03%</span></div>
    <div class="metric"><span class="metric-label">Circuit Breaker</span><span class="metric-value badge badge-green">CLOSED</span></div>
  </div>
  <div class="card">
    <h3>API Versioning</h3>
    <div class="version-row">
      <div class="version-chip">
        <div class="ver">v1.1</div>
        <div class="ver-label">Current / Stable</div>
        <div style="color:#059669;font-size:0.78rem;margin-top:4px;">&#9679; Active</div>
      </div>
      <div class="version-chip">
        <div class="ver">v2.0</div>
        <div class="ver-label">Beta / Preview</div>
        <div style="color:#d97706;font-size:0.78rem;margin-top:4px;">&#9651; Beta</div>
      </div>
    </div>
    <div class="metric" style="margin-top:10px;"><span class="metric-label">v1.1 traffic share</span><span class="metric-value">87%</span></div>
    <div class="metric"><span class="metric-label">v2.0 traffic share</span><span class="metric-value">13%</span></div>
    <div class="metric"><span class="metric-label">Deprecation notice</span><span class="metric-value badge badge-yellow">v1.0 EOL Jun 2026</span></div>
  </div>
</div>

<div class="card" style="margin-bottom:20px;">
  <h3>Gateway Architecture Layers</h3>
  <div class="layer">
    <div class="layer-num">1</div>
    <div class="layer-info">
      <div class="layer-title">mTLS Termination</div>
      <div class="layer-detail">Mutual TLS 1.3, certificate pinning, client cert validation, OCSP stapling</div>
    </div>
    <div class="layer-latency">0.8 ms</div>
  </div>
  <div class="layer">
    <div class="layer-num">2</div>
    <div class="layer-info">
      <div class="layer-title">Rate Limiting</div>
      <div class="layer-detail">Token bucket per partner key; Starter 100 / Growth 500 / Scale 2000 req/min</div>
    </div>
    <div class="layer-latency">0.3 ms</div>
  </div>
  <div class="layer">
    <div class="layer-num">3</div>
    <div class="layer-info">
      <div class="layer-title">Auth &amp; RBAC</div>
      <div class="layer-detail">JWT validation (RS256), scope check, partner tenant isolation, audit log</div>
    </div>
    <div class="layer-latency">0.9 ms</div>
  </div>
  <div class="layer">
    <div class="layer-num">4</div>
    <div class="layer-info">
      <div class="layer-title">Request Routing</div>
      <div class="layer-detail">Version-aware path rewrite, weighted canary (v2.0 13%), header injection</div>
    </div>
    <div class="layer-latency">0.4 ms</div>
  </div>
  <div class="layer" style="border: 1px solid #C74634;">
    <div class="layer-num" style="background:#059669;">5</div>
    <div class="layer-info">
      <div class="layer-title">Circuit Breaker</div>
      <div class="layer-detail">Hystrix-style; threshold 50% errors / 10s window; half-open probe every 30s</div>
    </div>
    <div class="layer-latency" style="color:#059669;">0.1 ms</div>
  </div>
</div>

<div class="card" style="margin-bottom:20px;">
  <h3>Rate Limit Tier Comparison</h3>
  <table class="tier-table">
    <thead>
      <tr>
        <th>Tier</th>
        <th>Req / Min</th>
        <th>Burst</th>
        <th>SLA</th>
        <th>mTLS</th>
        <th>Price</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span style="color:#94a3b8;font-weight:600;">Starter</span></td>
        <td>100</td>
        <td>150</td>
        <td>99.5%</td>
        <td style="color:#d97706;">Optional</td>
        <td>$99/mo</td>
      </tr>
      <tr>
        <td><span style="color:#38bdf8;font-weight:600;">Growth</span></td>
        <td>500</td>
        <td>800</td>
        <td>99.9%</td>
        <td style="color:#059669;">Required</td>
        <td>$499/mo</td>
      </tr>
      <tr>
        <td><span style="color:#C74634;font-weight:600;">Scale</span></td>
        <td>2,000</td>
        <td>3,500</td>
        <td>99.97%</td>
        <td style="color:#059669;">Required</td>
        <td>Custom</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h3>Rate Tier Capacity (req/min visual)</h3>
  <div class="bar-row">
    <span class="bar-label">Starter</span>
    <div class="bar-bg"><div class="bar-fill" style="width:5%;background:#475569;">100</div></div>
  </div>
  <div class="bar-row">
    <span class="bar-label">Growth</span>
    <div class="bar-bg"><div class="bar-fill" style="width:25%;background:#0284c7;">500</div></div>
  </div>
  <div class="bar-row">
    <span class="bar-label">Scale</span>
    <div class="bar-bg"><div class="bar-fill" style="width:100%;background:#C74634;">2,000</div></div>
  </div>

  <h3 style="margin-top:20px;">Gateway Layer Latency Breakdown</h3>
  <svg width="100%" height="80" viewBox="0 0 600 80">
    <rect x="10" y="20" width="156" height="28" fill="#0f172a" rx="4" stroke="#38bdf8" stroke-width="1"/>
    <text x="88" y="38" fill="#38bdf8" font-size="12" text-anchor="middle">mTLS 0.8ms</text>
    <rect x="178" y="20" width="80" height="28" fill="#0f172a" rx="4" stroke="#7c3aed" stroke-width="1"/>
    <text x="218" y="38" fill="#a78bfa" font-size="12" text-anchor="middle">RL 0.3ms</text>
    <rect x="270" y="20" width="112" height="28" fill="#0f172a" rx="4" stroke="#C74634" stroke-width="1"/>
    <text x="326" y="38" fill="#fca5a5" font-size="12" text-anchor="middle">Auth 0.9ms</text>
    <rect x="394" y="20" width="90" height="28" fill="#0f172a" rx="4" stroke="#0284c7" stroke-width="1"/>
    <text x="439" y="38" fill="#38bdf8" font-size="12" text-anchor="middle">Route 0.4ms</text>
    <rect x="496" y="20" width="90" height="28" fill="#0f172a" rx="4" stroke="#059669" stroke-width="1"/>
    <text x="541" y="38" fill="#6ee7b7" font-size="12" text-anchor="middle">CB 0.1ms</text>
    <text x="300" y="72" fill="#94a3b8" font-size="11" text-anchor="middle">Total gateway overhead: 2.5ms &bull; Backend + network: 2.2ms &bull; E2E: 4.7ms</text>
  </svg>
</div>

<p class="footer">Partner API Gateway V2 &bull; OCI Robot Cloud &bull; Port 8935</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner API Gateway V2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_api_gateway_v2", "port": 8935}

    @app.get("/metrics")
    async def metrics():
        total_rps = round(48320 / 60 + random.uniform(-5, 5), 1)
        error_rate = round(0.0003 + random.uniform(-0.00005, 0.00005), 6)
        availability = round(99.97 + random.uniform(-0.005, 0.005), 4)
        layer_latencies_ms = {
            "mtls_termination": round(0.8 + random.uniform(-0.05, 0.05), 3),
            "rate_limiting": round(0.3 + random.uniform(-0.02, 0.02), 3),
            "auth_rbac": round(0.9 + random.uniform(-0.05, 0.05), 3),
            "request_routing": round(0.4 + random.uniform(-0.02, 0.02), 3),
            "circuit_breaker": round(0.1 + random.uniform(-0.01, 0.01), 3),
        }
        gateway_overhead_ms = round(sum(layer_latencies_ms.values()), 3)
        backend_ms = round(2.2 + random.uniform(-0.1, 0.1), 3)
        e2e_ms = round(gateway_overhead_ms + backend_ms, 3)
        # utilization ratio (log scale for visual interest)
        starter_util = round(random.uniform(0.6, 0.9), 3)
        growth_util = round(random.uniform(0.4, 0.7), 3)
        scale_util = round(random.uniform(0.2, 0.5), 3)
        return {
            "availability_percent": availability,
            "active_connections": round(1284 + random.randint(-20, 20)),
            "requests_per_min": round(total_rps * 60),
            "error_rate": error_rate,
            "circuit_breaker_state": "CLOSED",
            "layer_latencies_ms": layer_latencies_ms,
            "gateway_overhead_ms": gateway_overhead_ms,
            "backend_latency_ms": backend_ms,
            "e2e_latency_ms": e2e_ms,
            "api_versions": {
                "v1_1": {"status": "stable", "traffic_share": 0.87},
                "v2_0": {"status": "beta", "traffic_share": 0.13},
                "v1_0": {"status": "deprecated", "eol": "2026-06-01"},
            },
            "rate_tiers": {
                "starter": {"req_per_min": 100, "burst": 150, "sla": 99.5, "utilization": starter_util},
                "growth": {"req_per_min": 500, "burst": 800, "sla": 99.9, "utilization": growth_util},
                "scale": {"req_per_min": 2000, "burst": 3500, "sla": 99.97, "utilization": scale_util},
            },
            "pipeline_stages": ["mtls", "rate_limit", "auth", "routing", "circuit_breaker"],
            "log2_scale_starter_ratio": round(math.log2(2000 / 100), 4),
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8935)
    else:
        server = HTTPServer(("0.0.0.0", 8935), Handler)
        print("Partner API Gateway V2 running on port 8935 (fallback)")
        server.serve_forever()
