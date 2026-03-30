"""Platform API V3 — port 8947

v3 new endpoints, latency improvements, SDK compatibility matrix, May 15 beta → Jun 1 GA.
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
<title>Platform API V3</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 6px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 8px; }
  .subtitle { color: #94a3b8; margin-bottom: 28px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
  .metric-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #334155; }
  .metric-row:last-child { border-bottom: none; }
  .label { color: #94a3b8; font-size: 0.9rem; }
  .value { font-weight: 600; }
  .good { color: #4ade80; }
  .warn { color: #fbbf24; }
  .new { color: #a78bfa; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { color: #38bdf8; text-align: left; padding: 8px 10px; border-bottom: 2px solid #334155; }
  td { padding: 7px 10px; border-bottom: 1px solid #1e293b; }
  tr:nth-child(even) td { background: #1e293b44; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
  .badge-new { background: #312e81; color: #a5b4fc; }
  .badge-stable { background: #14532d; color: #4ade80; }
  .badge-beta { background: #7c2d12; color: #fca5a5; }
  .badge-dep { background: #1e293b; color: #94a3b8; border: 1px solid #475569; }
  svg { width: 100%; }
  .timeline-item { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
  .tl-dot { width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
  .tl-line { width: 2px; background: #334155; flex-shrink: 0; min-height: 28px; margin-left: 6px; }
  .tl-content h4 { color: #e2e8f0; font-size: 0.95rem; margin-bottom: 3px; }
  .tl-content p { color: #94a3b8; font-size: 0.83rem; }
  .endpoint-chip { display: inline-block; background: #0f172a; border: 1px solid #38bdf8; border-radius: 6px; padding: 2px 8px; font-size: 0.8rem; color: #38bdf8; margin: 2px; font-family: monospace; }
</style>
</head>
<body>
<h1>Platform API V3</h1>
<p class="subtitle">New streaming &amp; async endpoints · 4ms overhead (↓ from 8ms) · SDK compatibility matrix · Beta May 15 → GA Jun 1</p>

<h2>Key Metrics</h2>
<div class="grid">
  <div class="card">
    <h3>Latency Improvement</h3>
    <div class="metric-row"><span class="label">v2 per-call overhead</span><span class="value warn">8 ms</span></div>
    <div class="metric-row"><span class="label">v3 per-call overhead</span><span class="value good">4 ms</span></div>
    <div class="metric-row"><span class="label">Reduction</span><span class="value good">50%</span></div>
    <div class="metric-row"><span class="label">Method</span><span class="value">Connection pooling + proto3</span></div>
  </div>
  <div class="card">
    <h3>Release Timeline</h3>
    <div class="metric-row"><span class="label">Beta release</span><span class="value warn">May 15, 2026</span></div>
    <div class="metric-row"><span class="label">GA release</span><span class="value good">Jun 1, 2026</span></div>
    <div class="metric-row"><span class="label">v2 EOL</span><span class="value">Sep 1, 2026</span></div>
    <div class="metric-row"><span class="label">Migration guide</span><span class="value good">Available</span></div>
  </div>
  <div class="card">
    <h3>New Endpoints (v3)</h3>
    <div style="margin-top:8px">
      <span class="endpoint-chip">streaming_inference</span>
      <span class="endpoint-chip">async_dagger</span>
      <span class="endpoint-chip">checkpoint_diff</span>
      <span class="endpoint-chip">video_finetune</span>
      <span class="endpoint-chip">bimanual</span>
    </div>
    <div style="margin-top:10px">
      <div class="metric-row"><span class="label">Total v3 endpoints</span><span class="value good">23</span></div>
      <div class="metric-row"><span class="label">v2-compatible</span><span class="value good">18</span></div>
    </div>
  </div>
</div>

<h2>API Changelog Timeline</h2>
<div class="card">
  <svg viewBox="0 0 700 180" xmlns="http://www.w3.org/2000/svg">
    <rect width="700" height="180" fill="#1e293b" rx="6"/>
    <!-- timeline spine -->
    <line x1="60" y1="90" x2="640" y2="90" stroke="#334155" stroke-width="2"/>
    <!-- v1 -->
    <circle cx="80" cy="90" r="8" fill="#475569"/>
    <text x="80" y="115" fill="#64748b" font-size="10" text-anchor="middle">v1.0</text>
    <text x="80" y="128" fill="#64748b" font-size="9" text-anchor="middle">Jan 2025</text>
    <text x="80" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">Initial release</text>
    <!-- v2 -->
    <circle cx="220" cy="90" r="8" fill="#38bdf8"/>
    <text x="220" y="115" fill="#38bdf8" font-size="10" text-anchor="middle">v2.0</text>
    <text x="220" y="128" fill="#64748b" font-size="9" text-anchor="middle">Sep 2025</text>
    <text x="220" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">Async support</text>
    <text x="220" y="60" fill="#94a3b8" font-size="9" text-anchor="middle">8ms overhead</text>
    <!-- v3 beta -->
    <circle cx="440" cy="90" r="10" fill="#fbbf24"/>
    <text x="440" y="115" fill="#fbbf24" font-size="10" text-anchor="middle">v3 Beta</text>
    <text x="440" y="128" fill="#64748b" font-size="9" text-anchor="middle">May 15, 2026</text>
    <text x="440" y="68" fill="#a78bfa" font-size="9" text-anchor="middle">streaming_inference</text>
    <text x="440" y="56" fill="#a78bfa" font-size="9" text-anchor="middle">async_dagger · bimanual</text>
    <!-- v3 GA -->
    <circle cx="600" cy="90" r="12" fill="#C74634"/>
    <text x="600" y="117" fill="#C74634" font-size="10" text-anchor="middle" font-weight="bold">v3 GA</text>
    <text x="600" y="130" fill="#64748b" font-size="9" text-anchor="middle">Jun 1, 2026</text>
    <text x="600" y="68" fill="#4ade80" font-size="9" text-anchor="middle">4ms overhead</text>
    <text x="600" y="56" fill="#4ade80" font-size="9" text-anchor="middle">Full 23 endpoints</text>
    <!-- connector from beta to GA -->
    <line x1="450" y1="90" x2="588" y2="90" stroke="#C74634" stroke-width="2" stroke-dasharray="5,3"/>
    <!-- latency arrow annotation -->
    <line x1="220" y1="142" x2="600" y2="142" stroke="#334155" stroke-width="1" marker-end="url(#arr)"/>
    <text x="410" y="158" fill="#64748b" font-size="9" text-anchor="middle">Overhead: 8ms → 4ms (50% reduction)</text>
  </svg>
</div>

<h2>New Endpoint Capabilities</h2>
<div class="card">
  <table>
    <thead><tr><th>Endpoint</th><th>Description</th><th>v2</th><th>v3</th><th>Latency</th><th>Auth</th></tr></thead>
    <tbody>
      <tr>
        <td><code>streaming_inference</code></td>
        <td>Token-streamed action prediction</td>
        <td>—</td>
        <td><span class="badge badge-new">NEW</span></td>
        <td class="good">18 ms p50</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>async_dagger</code></td>
        <td>Non-blocking DAgger episode submission</td>
        <td>—</td>
        <td><span class="badge badge-new">NEW</span></td>
        <td class="good">6 ms p50</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>checkpoint_diff</code></td>
        <td>Delta between two checkpoint versions</td>
        <td>—</td>
        <td><span class="badge badge-new">NEW</span></td>
        <td>32 ms p50</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>video_finetune</code></td>
        <td>Submit MP4 video for fine-tuning</td>
        <td>—</td>
        <td><span class="badge badge-new">NEW</span></td>
        <td>120 ms p50</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>bimanual</code></td>
        <td>Dual-arm coordinated action inference</td>
        <td>—</td>
        <td><span class="badge badge-new">NEW</span></td>
        <td class="good">22 ms p50</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>infer</code></td>
        <td>Standard single-step inference</td>
        <td><span class="badge badge-stable">STABLE</span></td>
        <td><span class="badge badge-stable">STABLE</span></td>
        <td class="good">4 ms overhead</td>
        <td>Bearer</td>
      </tr>
      <tr>
        <td><code>batch_infer</code></td>
        <td>Batched inference (up to 32)</td>
        <td><span class="badge badge-stable">STABLE</span></td>
        <td><span class="badge badge-stable">STABLE</span></td>
        <td class="good">4 ms overhead</td>
        <td>Bearer</td>
      </tr>
    </tbody>
  </table>
</div>

<h2>SDK Compatibility Matrix</h2>
<div class="card">
  <table>
    <thead><tr><th>SDK Version</th><th>v1 API</th><th>v2 API</th><th>v3 API</th><th>Status</th><th>Notes</th></tr></thead>
    <tbody>
      <tr><td>oci-robot-cloud &lt; 1.0</td><td><span class="badge badge-dep">deprecated</span></td><td>—</td><td>—</td><td class="warn">EOL</td><td>Upgrade required</td></tr>
      <tr><td>oci-robot-cloud 1.x</td><td><span class="badge badge-stable">yes</span></td><td><span class="badge badge-stable">yes</span></td><td>—</td><td class="warn">Maintenance</td><td>EOL Sep 2026</td></tr>
      <tr><td>oci-robot-cloud 2.x</td><td><span class="badge badge-stable">yes</span></td><td><span class="badge badge-stable">yes</span></td><td><span class="badge badge-beta">partial</span></td><td class="good">Supported</td><td>v3 streaming via plugin</td></tr>
      <tr><td>oci-robot-cloud 3.x</td><td>—</td><td><span class="badge badge-stable">yes</span></td><td><span class="badge badge-stable">yes</span></td><td class="good">Recommended</td><td>Full v3 support</td></tr>
      <tr><td>Python SDK (raw)</td><td>—</td><td><span class="badge badge-stable">yes</span></td><td><span class="badge badge-stable">yes</span></td><td class="good">Supported</td><td>requests / httpx</td></tr>
      <tr><td>gRPC client</td><td>—</td><td>—</td><td><span class="badge badge-new">NEW v3</span></td><td class="good">Beta May 15</td><td>proto3 schema published</td></tr>
    </tbody>
  </table>
</div>

<p style="color:#475569;font-size:0.78rem;margin-top:32px;text-align:center;">Platform API V3 · port 8947 · OCI Robot Cloud</p>
</body></html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Platform API V3", version="3.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "platform_api_v3", "port": 8947}

    @app.get("/api/endpoints")
    async def get_endpoints():
        return {
            "version": "3.0.0",
            "new_endpoints": ["streaming_inference", "async_dagger", "checkpoint_diff", "video_finetune", "bimanual"],
            "total_endpoints": 23,
            "v2_compatible": 18,
        }

    @app.get("/api/latency")
    async def get_latency():
        return {
            "v2_overhead_ms": 8,
            "v3_overhead_ms": 4,
            "reduction_pct": 50,
            "method": "connection_pooling_plus_proto3",
        }

    @app.get("/api/timeline")
    async def get_timeline():
        return {
            "beta": "2026-05-15",
            "ga": "2026-06-01",
            "v2_eol": "2026-09-01",
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8947)
    else:
        server = HTTPServer(("0.0.0.0", 8947), Handler)
        print("Platform API V3 running on http://0.0.0.0:8947 (fallback mode)")
        server.serve_forever()
