"""Model Deployment v2 — FastAPI service on port 8347.

Enhanced model deployment pipeline v2 with blue-green strategy and
automated validation gates.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

PORT = 8347

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

BLUE_MODEL = {
    "name": "dagger_r9_v2.2",
    "role": "production",
    "color": "#38bdf8",
    "sr": 0.71,
    "latency_ms": 226,
    "traffic_pct": 100,
    "deploy_date": "2026-02-14",
    "status": "ACTIVE",
}

GREEN_MODEL = {
    "name": "groot_v2",
    "role": "staging",
    "color": "#4ade80",
    "sr": 0.78,
    "latency_ms": 226,
    "traffic_pct": 0,
    "deploy_date": "2026-04-05",
    "status": "PENDING",
}

GATES = [
    {"id": "SR_regression",       "label": "SR Regression",         "result": "PASS", "detail": "0.78 vs 0.71 baseline (+10%)",      "threshold": ">= baseline"},
    {"id": "latency_regression",   "label": "Latency Regression",     "result": "PASS", "detail": "226ms vs 226ms baseline (0%)",        "threshold": "<= 110% baseline"},
    {"id": "error_rate",           "label": "Error Rate",             "result": "PASS", "detail": "0.3% error rate over 10k requests",   "threshold": "< 1%"},
    {"id": "memory_usage",         "label": "Memory Usage",           "result": "PASS", "detail": "6.9 GB peak GPU memory",              "threshold": "< 8 GB"},
    {"id": "safety_checks",        "label": "Safety Checks",          "result": "PASS", "detail": "All 47 safety test cases passed",      "threshold": "100% pass"},
    {"id": "partner_compatibility", "label": "Partner Compatibility",  "result": "PASS", "detail": "SDK v1.4+ compatible — 3 partners",   "threshold": "All partners"},
    {"id": "load_test",            "label": "Load Test",              "result": "PASS", "detail": "847 req/hr sustained for 2h",          "threshold": ">= 500 req/hr"},
    {"id": "sign_off",             "label": "Engineering Sign-off",   "result": "PASS", "detail": "Approved by Jun Qian 2026-03-29",     "threshold": "Required"},
]

DEPLOY_HISTORY = [
    {"version": "dagger_r5_v1.0", "date": "2025-10-12", "sr": 0.52, "latency": 312, "result": "SUCCESS"},
    {"version": "dagger_r7_v1.8", "date": "2025-12-01", "sr": 0.61, "latency": 278, "result": "SUCCESS"},
    {"version": "dagger_r8_v2.0", "date": "2026-01-15", "sr": 0.66, "latency": 251, "result": "ROLLBACK"},
    {"version": "dagger_r9_v2.2", "date": "2026-02-14", "sr": 0.71, "latency": 226, "result": "SUCCESS"},
    {"version": "groot_v2",       "date": "2026-04-05", "sr": 0.78, "latency": 226, "result": "SCHEDULED"},
]

GATE_PASS_RATE = sum(1 for g in GATES if g["result"] == "PASS") / len(GATES) * 100


# ---------------------------------------------------------------------------
# SVG: Blue-green deployment diagram
# ---------------------------------------------------------------------------

def _bluegreen_svg() -> str:
    W, H = 680, 360

    # Blue box (production)
    blue_box = """
  <!-- BLUE: production -->
  <rect x="40" y="80" width="240" height="130" rx="12" fill="#0369a1" stroke="#38bdf8" stroke-width="2"/>
  <text x="160" y="104" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold" font-family="monospace">BLUE — PRODUCTION</text>
  <text x="160" y="124" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace">dagger_r9_v2.2</text>
  <rect x="60" y="134" width="200" height="20" rx="4" fill="#0f172a"/>
  <rect x="60" y="134" width="200" height="20" rx="4" fill="#38bdf8" opacity="0.8"/>
  <text x="160" y="149" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="bold" font-family="monospace">100% traffic</text>
  <text x="160" y="172" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">SR: 71% | 226ms | ACTIVE</text>
  <text x="160" y="190" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">deployed 2026-02-14</text>"""

    # Green box (staging)
    green_box = """
  <!-- GREEN: staging -->
  <rect x="400" y="80" width="240" height="130" rx="12" fill="#14532d" stroke="#4ade80" stroke-width="2" stroke-dasharray="6,3"/>
  <text x="520" y="104" text-anchor="middle" fill="#4ade80" font-size="13" font-weight="bold" font-family="monospace">GREEN — STAGING</text>
  <text x="520" y="124" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace">groot_v2</text>
  <rect x="420" y="134" width="200" height="20" rx="4" fill="#0f172a"/>
  <rect x="420" y="134" width="10" height="20" rx="4" fill="#4ade80" opacity="0.4"/>
  <text x="520" y="149" text-anchor="middle" fill="#4ade80" font-size="11" font-family="monospace">0% traffic (pending)</text>
  <text x="520" y="172" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">SR: 78% | 226ms | PENDING</text>
  <text x="520" y="190" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">scheduled 2026-04-05</text>"""

    # Switch arrow
    switch_arrow = """
  <!-- switch arrow -->
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#C74634"/>
    </marker>
    <marker id="arrowback" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
      <polygon points="10 0, 0 3.5, 10 7" fill="#64748b"/>
    </marker>
  </defs>
  <line x1="285" y1="135" x2="395" y2="135" stroke="#C74634" stroke-width="2.5" stroke-dasharray="8,4" marker-end="url(#arrowhead)"/>
  <text x="340" y="125" text-anchor="middle" fill="#C74634" font-size="11" font-family="monospace">SWITCH</text>
  <text x="340" y="138" text-anchor="middle" fill="#C74634" font-size="9" font-family="monospace">Apr 5</text>
  <!-- rollback path -->
  <path d="M 395 165 Q 340 200 285 165" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5,4" marker-end="url(#arrowback)"/>
  <text x="340" y="200" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">rollback path</text>"""

    # Deployment history timeline at bottom
    timeline = '<text x="40" y="255" fill="#38bdf8" font-size="12" font-family="monospace" font-weight="bold">DEPLOYMENT HISTORY</text>'
    x_start = 40
    spacing = 128
    for i, dep in enumerate(DEPLOY_HISTORY):
        x = x_start + i * spacing
        result_color = {"SUCCESS": "#4ade80", "ROLLBACK": "#ef4444", "SCHEDULED": "#eab308"}.get(dep["result"], "#94a3b8")
        timeline += f"""
  <rect x="{x}" y="265" width="118" height="74" rx="8" fill="#1e293b" stroke="{result_color}" stroke-width="1.5"/>
  <text x="{x+59}" y="282" text-anchor="middle" fill="{result_color}" font-size="10" font-family="monospace" font-weight="bold">{dep['result']}</text>
  <text x="{x+59}" y="296" text-anchor="middle" fill="#e2e8f0" font-size="9" font-family="monospace">{dep['version']}</text>
  <text x="{x+59}" y="310" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">SR {int(dep['sr']*100)}% / {dep['latency']}ms</text>
  <text x="{x+59}" y="324" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">{dep['date']}</text>"""

    return f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:12px">
  <text x="{W//2}" y="28" text-anchor="middle" fill="#38bdf8" font-size="15" font-weight="bold" font-family="monospace">BLUE-GREEN DEPLOYMENT STRATEGY</text>
  <text x="{W//2}" y="48" text-anchor="middle" fill="#64748b" font-size="11" font-family="monospace">Traffic switch scheduled Apr 5 — rollback path maintained</text>
  <!-- Load balancer -->
  <rect x="280" y="55" width="120" height="30" rx="8" fill="#334155" stroke="#64748b" stroke-width="1"/>
  <text x="340" y="74" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Load Balancer</text>
  <line x1="280" y1="70" x2="160" y2="95" stroke="#38bdf8" stroke-width="1.5"/>
  <line x1="400" y1="70" x2="520" y2="95" stroke="#4ade80" stroke-width="1" stroke-dasharray="4,3"/>
  {blue_box}
  {green_box}
  {switch_arrow}
  {timeline}
</svg>"""


# ---------------------------------------------------------------------------
# SVG: Automated gate results
# ---------------------------------------------------------------------------

def _gates_svg() -> str:
    W = 580
    row_h = 38
    pad_t = 55
    H = pad_t + len(GATES) * row_h + 30

    rows = ""
    for i, gate in enumerate(GATES):
        y = pad_t + i * row_h
        bg = "#1e293b" if i % 2 == 0 else "#162032"
        result_color = "#4ade80" if gate["result"] == "PASS" else "#ef4444"
        # status bar fill
        bar_fill = "#4ade8033" if gate["result"] == "PASS" else "#ef444433"
        rows += f"""
  <rect x="0" y="{y}" width="{W}" height="{row_h}" fill="{bg}"/>
  <!-- status pill -->
  <rect x="10" y="{y+9}" width="52" height="20" rx="4" fill="{result_color}22"/>
  <text x="36" y="{y+23}" text-anchor="middle" fill="{result_color}" font-size="10" font-weight="bold" font-family="monospace">{gate['result']}</text>
  <!-- gate name -->
  <text x="72" y="{y+23}" fill="#e2e8f0" font-size="11" font-family="monospace">{gate['label']}</text>
  <!-- detail -->
  <text x="230" y="{y+23}" fill="#94a3b8" font-size="10" font-family="monospace">{gate['detail']}</text>
  <!-- checkmark / X -->
  <text x="{W-20}" y="{y+23}" text-anchor="middle" fill="{result_color}" font-size="14" font-family="monospace">{chr(10003) if gate['result'] == 'PASS' else chr(10007)}</text>"""

    passed = sum(1 for g in GATES if g["result"] == "PASS")

    return f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:12px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14" font-weight="bold" font-family="monospace">AUTOMATED DEPLOYMENT GATES — groot_v2</text>
  <text x="{W//2}" y="40" text-anchor="middle" fill="#4ade80" font-size="11" font-family="monospace">{passed}/{len(GATES)} gates passed — CLEARED FOR DEPLOYMENT</text>
  {rows}
  <!-- summary bar -->
  <rect x="0" y="{pad_t + len(GATES)*row_h}" width="{W}" height="28" fill="#0f172a" rx="0"/>
  <rect x="10" y="{pad_t + len(GATES)*row_h + 6}" width="{int((passed/len(GATES))*560)}" height="14" rx="4" fill="#4ade80" opacity="0.8"/>
  <text x="{W//2}" y="{pad_t + len(GATES)*row_h + 19}" text-anchor="middle" fill="#4ade80" font-size="10" font-family="monospace">Gate Pass Rate: {GATE_PASS_RATE:.0f}%</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    history_rows = ""
    for dep in reversed(DEPLOY_HISTORY):
        result_color = {"SUCCESS": "#4ade80", "ROLLBACK": "#ef4444", "SCHEDULED": "#eab308"}.get(dep["result"], "#94a3b8")
        history_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#e2e8f0;font-family:monospace;font-size:13px">{dep['version']}</td>
          <td style="padding:8px 12px;color:#64748b;font-family:monospace;font-size:12px">{dep['date']}</td>
          <td style="padding:8px 12px;color:#38bdf8;font-family:monospace">{int(dep['sr']*100)}%</td>
          <td style="padding:8px 12px;color:#94a3b8;font-family:monospace">{dep['latency']}ms</td>
          <td style="padding:8px 12px"><span style="background:{result_color}22;color:{result_color};padding:2px 8px;border-radius:4px;font-size:12px;font-family:monospace">{dep['result']}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Model Deployment v2 — Port {PORT}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; }}
    header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    .logo {{ width:36px; height:36px; background:#C74634; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:18px; color:#fff; }}
    h1 {{ font-size:20px; color:#f8fafc; }}
    h1 span {{ color:#C74634; }}
    .badge {{ background:#38bdf822; color:#38bdf8; border:1px solid #38bdf8; border-radius:20px; padding:3px 12px; font-size:12px; margin-left:auto; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:20px; border-left:4px solid #C74634; }}
    .card-val {{ font-size:32px; font-weight:bold; color:#f8fafc; }}
    .card-label {{ font-size:12px; color:#64748b; margin-top:4px; }}
    .charts {{ display:flex; gap:20px; padding:0 32px 24px; flex-wrap:wrap; align-items:flex-start; }}
    .section {{ padding:0 32px 32px; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; }}
    thead th {{ background:#0f172a; color:#94a3b8; padding:10px 12px; text-align:left; font-size:12px; }}
    tbody tr:hover {{ background:#0f172a44; }}
    .footer {{ text-align:center; padding:16px; color:#334155; font-size:11px; }}
  </style>
</head>
<body>
  <header>
    <div class="logo">D</div>
    <div>
      <h1><span>OCI</span> Model Deployment v2</h1>
      <div style="color:#64748b;font-size:12px">Blue-Green Pipeline — Automated Validation Gates</div>
    </div>
    <div class="badge">Port {PORT}</div>
  </header>

  <div class="metrics">
    <div class="card" style="border-left-color:#4ade80">
      <div class="card-val" style="color:#4ade80">{GATE_PASS_RATE:.0f}%</div>
      <div class="card-label">Gate Pass Rate (groot_v2)</div>
    </div>
    <div class="card" style="border-left-color:#38bdf8">
      <div class="card-val" style="color:#38bdf8">4</div>
      <div class="card-label">Successful Deploys (6mo)</div>
    </div>
    <div class="card" style="border-left-color:#ef4444">
      <div class="card-val" style="color:#ef4444">1</div>
      <div class="card-label">Rollbacks (lifetime)</div>
    </div>
    <div class="card" style="border-left-color:#eab308">
      <div class="card-val" style="color:#eab308">Apr 5</div>
      <div class="card-label">Next Deployment (groot_v2)</div>
    </div>
  </div>

  <div class="charts">
    {_bluegreen_svg()}
    {_gates_svg()}
  </div>

  <div class="section">
    <div style="color:#38bdf8;font-size:14px;margin-bottom:12px">DEPLOYMENT HISTORY</div>
    <table>
      <thead><tr><th>Version</th><th>Date</th><th>SR</th><th>Latency</th><th>Result</th></tr></thead>
      <tbody>{history_rows}</tbody>
    </table>
  </div>

  <div class="footer">Model Deployment v2 | OCI RoboticsAI | Port {PORT} | Blue-Green Strategy | groot_v2 scheduled Apr 5 2026</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Model Deployment v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": PORT, "active_model": BLUE_MODEL["name"],
                "pending_model": GREEN_MODEL["name"], "gate_pass_rate": GATE_PASS_RATE}

    @app.get("/api/deployments")
    async def deployments():
        return {"blue": BLUE_MODEL, "green": GREEN_MODEL,
                "gates": GATES, "history": DEPLOY_HISTORY,
                "gate_pass_rate": GATE_PASS_RATE}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI unavailable — falling back to stdlib http.server on port {PORT}")
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            httpd.serve_forever()
