# Deal Desk Automation — port 8985
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
<title>Deal Desk Automation</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 28px 0 12px; }
  h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 8px; }
  .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card .val { font-size: 1.6rem; font-weight: 700; color: #38bdf8; }
  .card .label { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .card .delta { font-size: 0.85rem; color: #4ade80; margin-top: 6px; }
  table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }
  th { background: #0f172a; color: #38bdf8; padding: 10px 14px; text-align: left; font-size: 0.85rem; }
  td { padding: 10px 14px; font-size: 0.88rem; border-top: 1px solid #334155; }
  tr:hover td { background: #263248; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-yellow { background: #713f12; color: #fbbf24; }
  .badge-blue { background: #0c4a6e; color: #38bdf8; }
  .badge-red { background: #7f1d1d; color: #f87171; }
  code { background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 0.82rem; color: #fbbf24; }
</style>
</head>
<body>
<h1>Deal Desk Automation</h1>
<p class="subtitle">OCI Robot Cloud · Automated quote generation, approval routing, and deal velocity optimization · Port 8985</p>

<h2>Key Performance Metrics</h2>
<div class="grid">
  <div class="card">
    <div class="val">8 days</div>
    <div class="label">Automated Deal Cycle</div>
    <div class="delta">vs 23 days manual (65% faster)</div>
  </div>
  <div class="card">
    <div class="val">80%</div>
    <div class="label">Q2 Automation Target</div>
    <div class="delta">Deals via auto-approval</div>
  </div>
  <div class="card">
    <div class="val">&lt;$50k</div>
    <div class="label">Auto-Approval Threshold</div>
    <div class="delta">No exec sign-off needed</div>
  </div>
  <div class="card">
    <div class="val">65%</div>
    <div class="label">Velocity Improvement</div>
    <div class="delta">8 days automated vs 23 manual</div>
  </div>
</div>

<h2>Deal Velocity Comparison</h2>
<div class="chart-wrap">
  <svg viewBox="0 0 820 260" width="100%">
    <!-- Axis -->
    <line x1="60" y1="20" x2="60" y2="210" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="210" x2="780" y2="210" stroke="#334155" stroke-width="1"/>
    <!-- Grid -->
    <line x1="60" y1="210" x2="780" y2="210" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="60" y1="167" x2="780" y2="167" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="60" y1="123" x2="780" y2="123" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="60" y1="80" x2="780" y2="80" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="60" y1="36" x2="780" y2="36" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <!-- Y-labels (days) -->
    <text x="52" y="214" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <text x="52" y="171" fill="#64748b" font-size="10" text-anchor="end">5</text>
    <text x="52" y="127" fill="#64748b" font-size="10" text-anchor="end">10</text>
    <text x="52" y="84" fill="#64748b" font-size="10" text-anchor="end">15</text>
    <text x="52" y="40" fill="#64748b" font-size="10" text-anchor="end">20</text>
    <!-- Stage bars: Manual (gray) vs Automated (blue) -->
    <!-- Stage 1: Quote Generation -->
    <text x="130" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">Quote Gen</text>
    <rect x="90" y="80" width="30" height="130" fill="#475569" rx="3"/>
    <text x="105" y="76" fill="#94a3b8" font-size="9" text-anchor="middle">15d</text>
    <rect x="125" y="175" width="30" height="35" fill="#38bdf8" rx="3" opacity="0.85"/>
    <text x="140" y="171" fill="#38bdf8" font-size="9" text-anchor="middle">4d</text>
    <!-- Stage 2: Internal Review -->
    <text x="250" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">Internal Review</text>
    <rect x="210" y="149" width="30" height="61" fill="#475569" rx="3"/>
    <text x="225" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">7d</text>
    <rect x="245" y="192" width="30" height="18" fill="#38bdf8" rx="3" opacity="0.85"/>
    <text x="260" y="188" fill="#38bdf8" font-size="9" text-anchor="middle">2d</text>
    <!-- Stage 3: Legal / Compliance -->
    <text x="370" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">Legal/Compliance</text>
    <rect x="330" y="166" width="30" height="44" fill="#475569" rx="3"/>
    <text x="345" y="162" fill="#94a3b8" font-size="9" text-anchor="middle">5d</text>
    <rect x="365" y="201" width="30" height="9" fill="#38bdf8" rx="3" opacity="0.85"/>
    <text x="380" y="197" fill="#38bdf8" font-size="9" text-anchor="middle">1d</text>
    <!-- Stage 4: Exec Approval -->
    <text x="490" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">Exec Approval</text>
    <rect x="450" y="157" width="30" height="53" fill="#475569" rx="3"/>
    <text x="465" y="153" fill="#94a3b8" font-size="9" text-anchor="middle">6d</text>
    <rect x="485" y="201" width="30" height="9" fill="#38bdf8" rx="3" opacity="0.85"/>
    <text x="500" y="197" fill="#38bdf8" font-size="9" text-anchor="middle">auto</text>
    <!-- Stage 5: Customer Delivery -->
    <text x="610" y="228" fill="#94a3b8" font-size="9" text-anchor="middle">Customer Delivery</text>
    <rect x="570" y="201" width="30" height="9" fill="#475569" rx="3"/>
    <text x="585" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">1d</text>
    <rect x="605" y="201" width="30" height="9" fill="#38bdf8" rx="3" opacity="0.85"/>
    <text x="620" y="197" fill="#38bdf8" font-size="9" text-anchor="middle">1d</text>
    <!-- Legend -->
    <rect x="680" y="30" width="14" height="14" fill="#475569" rx="2"/>
    <text x="698" y="42" fill="#94a3b8" font-size="11">Manual (23d total)</text>
    <rect x="680" y="52" width="14" height="14" fill="#38bdf8" rx="2" opacity="0.85"/>
    <text x="698" y="64" fill="#e2e8f0" font-size="11">Automated (8d total)</text>
    <text x="420" y="16" fill="#64748b" font-size="10" text-anchor="middle">Days per stage</text>
  </svg>
</div>

<h2>Approval Routing Flow</h2>
<div class="chart-wrap">
  <svg viewBox="0 0 820 260" width="100%">
    <!-- Flow nodes -->
    <!-- Start: Deal Input -->
    <rect x="30" y="100" width="130" height="50" rx="8" fill="#0369a1"/>
    <text x="95" y="120" fill="white" font-size="11" text-anchor="middle" font-weight="600">Deal Input</text>
    <text x="95" y="136" fill="#bae6fd" font-size="9" text-anchor="middle">robot_count / task_type</text>
    <text x="95" y="148" fill="#bae6fd" font-size="9" text-anchor="middle">SR_target</text>
    <!-- Arrow → Quote Engine -->
    <line x1="160" y1="125" x2="200" y2="125" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>
    <!-- Quote Engine -->
    <rect x="200" y="100" width="130" height="50" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1"/>
    <text x="265" y="120" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Quote Engine</text>
    <text x="265" y="136" fill="#94a3b8" font-size="9" text-anchor="middle">Pricing proposal</text>
    <text x="265" y="148" fill="#94a3b8" font-size="9" text-anchor="middle">auto-generated</text>
    <!-- Arrow → Decision Diamond -->
    <line x1="330" y1="125" x2="380" y2="125" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>
    <!-- Decision Diamond -->
    <polygon points="405,95 445,125 405,155 365,125" fill="#713f12" stroke="#fbbf24" stroke-width="1.5"/>
    <text x="405" y="121" fill="#fbbf24" font-size="9" text-anchor="middle" font-weight="600">&lt; $50k?</text>
    <text x="405" y="133" fill="#fbbf24" font-size="9" text-anchor="middle">Check</text>
    <!-- Yes → Auto Approve -->
    <line x1="445" y1="105" x2="510" y2="60" stroke="#4ade80" stroke-width="2" marker-end="url(#arrow2)"/>
    <text x="475" y="78" fill="#4ade80" font-size="10" text-anchor="middle">YES</text>
    <rect x="510" y="30" width="130" height="50" rx="8" fill="#14532d"/>
    <text x="575" y="52" fill="#4ade80" font-size="11" text-anchor="middle" font-weight="600">Auto-Approve</text>
    <text x="575" y="66" fill="#86efac" font-size="9" text-anchor="middle">Instant · SLA: 2h</text>
    <text x="575" y="78" fill="#86efac" font-size="9" text-anchor="middle">80% of deals (Q2 target)</text>
    <!-- No → Exec Routing -->
    <line x1="445" y1="145" x2="510" y2="175" stroke="#f87171" stroke-width="2" marker-end="url(#arrow3)"/>
    <text x="475" y="168" fill="#f87171" font-size="10" text-anchor="middle">NO</text>
    <rect x="510" y="160" width="130" height="50" rx="8" fill="#7f1d1d"/>
    <text x="575" y="182" fill="#fca5a5" font-size="11" text-anchor="middle" font-weight="600">Exec Routing</text>
    <text x="575" y="196" fill="#fca5a5" font-size="9" text-anchor="middle">&gt;$50k · SLA: 3 days</text>
    <text x="575" y="208" fill="#fca5a5" font-size="9" text-anchor="middle">VP/CRO sign-off</text>
    <!-- Both → Customer Proposal -->
    <line x1="640" y1="55" x2="710" y2="100" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow4)"/>
    <line x1="640" y1="185" x2="710" y2="150" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow4)"/>
    <rect x="710" y="100" width="100" height="50" rx="8" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
    <text x="760" y="122" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Customer</text>
    <text x="760" y="136" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Proposal</text>
    <text x="760" y="148" fill="#94a3b8" font-size="9" text-anchor="middle">Signed PDF</text>
    <!-- Arrow markers -->
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/>
      </marker>
      <marker id="arrow2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#4ade80"/>
      </marker>
      <marker id="arrow3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#f87171"/>
      </marker>
      <marker id="arrow4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/>
      </marker>
    </defs>
    <text x="410" y="248" fill="#64748b" font-size="10" text-anchor="middle">Approval routing: auto (&lt;$50k) or exec (&gt;$50k) · Q2 target 80% auto</text>
  </svg>
</div>

<h2>Quote Generation Logic</h2>
<table>
  <thead>
    <tr><th>Input</th><th>Type</th><th>Example</th><th>Impact on Pricing</th></tr>
  </thead>
  <tbody>
    <tr><td><code>robot_count</code></td><td>int</td><td>5</td><td>Volume tier: 1–5 standard, 6–20 –8%, 21+ –15%</td></tr>
    <tr><td><code>task_type</code></td><td>enum</td><td>pick_place</td><td>Base rate per task family (manipulation +20%, inspection standard)</td></tr>
    <tr><td><code>SR_target</code></td><td>float 0–1</td><td>0.90</td><td>Higher SR target → more fine-tune compute → cost premium +5–20%</td></tr>
    <tr><td><code>contract_months</code></td><td>int</td><td>12</td><td>Annual contract: –10%, 24-month: –18%</td></tr>
    <tr><td><code>region</code></td><td>string</td><td>us-ashburn-1</td><td>Multi-region redundancy adds +12% to base</td></tr>
  </tbody>
</table>

<h2>Approval Routing Rules</h2>
<div class="grid">
  <div class="card">
    <h3>Auto-Approval Track</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Deal value &lt; $50,000. Proposal generated and signed PDF delivered within 2 hours. No human in the loop. Covers standard configurations with SR_target ≤ 0.88.</p>
    <div class="delta" style="margin-top:10px;">80% of deals (Q2 target)</div>
  </div>
  <div class="card">
    <h3>Executive Routing Track</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Deal value &gt; $50,000 or custom SLA. Routes to VP Sales → CRO for sign-off. 3-business-day SLA with automated reminder escalations.</p>
    <div class="delta" style="color:#fbbf24;margin-top:10px;">20% of deals · 3-day SLA</div>
  </div>
  <div class="card">
    <h3>Deal Velocity: Automated</h3>
    <div class="val" style="font-size:1.3rem;margin-top:6px;">8 days avg</div>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Quote Gen 4d · Review 2d · Delivery 1d · Legal 1d</p>
  </div>
  <div class="card">
    <h3>Deal Velocity: Manual</h3>
    <div class="val" style="font-size:1.3rem;margin-top:6px;color:#f87171;">23 days avg</div>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Quote Gen 15d · Review 7d · Legal 5d · Exec 6d · Delivery 1d (overlapping)</p>
  </div>
</div>

<p style="color:#475569;font-size:0.75rem;margin-top:32px;">OCI Robot Cloud · Deal Desk Automation · Port 8985 · &copy; 2026 Oracle</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Deal Desk Automation", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "deal_desk_automation",
            "port": 8985,
            "auto_approval_threshold_usd": 50000,
            "auto_approval_sla_hours": 2,
            "exec_routing_sla_days": 3,
            "deal_velocity_automated_days": 8,
            "deal_velocity_manual_days": 23,
            "velocity_improvement_pct": 65,
            "q2_automation_target_pct": 80,
        }

    @app.post("/quote")
    async def generate_quote(robot_count: int = 1, task_type: str = "pick_place",
                              sr_target: float = 0.85, contract_months: int = 12,
                              region: str = "us-ashburn-1"):
        base = 8000 * robot_count
        volume_disc = 0.0
        if robot_count >= 21:
            volume_disc = 0.15
        elif robot_count >= 6:
            volume_disc = 0.08
        task_mult = 1.2 if "manip" in task_type or "pick" in task_type else 1.0
        sr_premium = max(0.0, (sr_target - 0.80) * 100) * 0.01 * base
        contract_disc = 0.10 if contract_months >= 24 else (0.05 if contract_months >= 12 else 0.0)
        region_add = base * 0.12 if region != "us-ashburn-1" else 0.0
        total = base * task_mult * (1 - volume_disc) * (1 - contract_disc) + sr_premium + region_add
        approval = "auto" if total < 50000 else "exec_routing"
        return {
            "total_usd": round(total, 2),
            "approval_track": approval,
            "estimated_days": 8 if approval == "auto" else 11,
            "breakdown": {
                "base": round(base, 2),
                "volume_discount_pct": volume_disc * 100,
                "task_multiplier": task_mult,
                "sr_premium": round(sr_premium, 2),
                "contract_discount_pct": contract_disc * 100,
                "region_add": round(region_add, 2),
            }
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8985)
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
        srv = HTTPServer(("0.0.0.0", 8985), Handler)
        print("Serving on http://0.0.0.0:8985")
        srv.serve_forever()
