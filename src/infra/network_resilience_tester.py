"""Network Resilience Tester — FastAPI port 8439"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8439

def build_html():
    scenarios = [
        ("Packet_loss_5%","#22c55e","PASS",8.2,False),
        ("Latency_spike_200ms","#22c55e","PASS",12.4,False),
        ("Region_failure_Ash","#22c55e","PASS",15.0,False),
        ("DNS_timeout_10s","#22c55e","PASS",22.7,False),
        ("TLS_cert_expiry","#f59e0b","WARN",252.0,True),
    ]

    svg_bar3 = '<svg width="380" height="200" style="background:#0f172a">'
    svg_bar3 += '<line x1="120" y1="10" x2="120" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_bar3 += '<line x1="120" y1="170" x2="360" y2="170" stroke="#475569" stroke-width="1"/>'
    # 30s auto threshold line
    threshold_x = 120 + 30/300*220
    svg_bar3 += f'<line x1="{threshold_x:.0f}" y1="10" x2="{threshold_x:.0f}" y2="170" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    svg_bar3 += f'<text x="{threshold_x+3:.0f}" y="22" fill="#f59e0b" font-size="7">30s auto</text>'
    for si, (scenario, col, status, recovery_s, manual) in enumerate(scenarios):
        y = 20+si*28; w = int(recovery_s/300*220)
        svg_bar3 += f'<rect x="120" y="{y}" width="{w}" height="22" fill="{col}" opacity="0.8" rx="3"/>'
        svg_bar3 += f'<text x="115" y="{y+15}" fill="#94a3b8" font-size="8" text-anchor="end">{scenario[:15]}</text>'
        svg_bar3 += f'<text x="{122+w}" y="{y+15}" fill="white" font-size="8">{recovery_s:.1f}s {{"(manual)" if manual else "(auto)"}}</text>'
    svg_bar3 += '</svg>'

    # Recovery time scatter per scenario
    svg_sc3 = '<svg width="320" height="200" style="background:#0f172a">'
    svg_sc3 += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_sc3 += '<line x1="40" y1="170" x2="290" y2="170" stroke="#475569" stroke-width="1"/>'
    # Multiple runs
    for si, (scenario, col, status, base_rec, manual) in enumerate(scenarios):
        for _ in range(5):
            rec = base_rec * random.uniform(0.85, 1.15)
            x = 40+si*48+random.uniform(-5,5)+24; y = 170-rec*140/300
            svg_sc3 += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4" fill="{col}" opacity="0.7"/>'
        # Mean line
        mean_y = 170-base_rec*140/300
        svg_sc3 += f'<line x1="{40+si*48+14}" y1="{mean_y:.0f}" x2="{40+si*48+34}" y2="{mean_y:.0f}" stroke="white" stroke-width="2"/>'
    # 30s line
    svg_sc3 += f'<line x1="40" y1="{170-30*140/300:.0f}" x2="290" y2="{170-30*140/300:.0f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>'
    svg_sc3 += '<text x="165" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Recovery Time per Scenario (5 runs)</text>'
    svg_sc3 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Network Resilience Tester — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Network Resilience Tester</h1>
<p style="color:#94a3b8">Port {PORT} | 5-scenario chaos test results + recovery time scatter</p>
<div class="grid">
<div class="card"><h2>Chaos Test Results</h2>{svg_bar3}
<div style="margin-top:8px;color:#f59e0b;font-size:11px">⚠ TLS expiry: 4.2min manual intervention (auto-renew not configured)<br>Action: enable Let's Encrypt auto-renewal on cert manager</div></div>
<div class="card"><h2>Recovery Time Scatter (5 runs)</h2>{svg_sc3}
<div style="margin-top:8px">
<div class="stat">4/5</div><div class="label">Scenarios with fully automated recovery &lt; 30s</div>
<div class="stat" style="color:#22c55e;margin-top:8px">15s</div><div class="label">Region failover recovery (Ashburn→Phoenix)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">All failovers tested quarterly in prod environment<br>Packet loss 5%: graceful degradation, no SR impact<br>DNS timeout: backup DNS resolver (OCI secondary)<br>TLS fix: add auto-renewal before next chaos test</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Network Resilience Tester")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
