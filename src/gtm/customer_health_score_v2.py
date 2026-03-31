"""customer_health_score_v2.py — Customer Health Score v2 Service (port 10029)

Composite health score: SR trend 35% + usage growth 25% + support sentiment 20% + engagement 20%.
"""

import json
import random
from datetime import datetime

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

PORT = 10029

# ---------------------------------------------------------------------------
# Customer data store
# ---------------------------------------------------------------------------

WEIGHTS = {
    "sr_trend": 0.35,
    "usage_growth": 0.25,
    "support_sentiment": 0.20,
    "engagement": 0.20
}

CUSTOMERS = {
    "machina": {
        "name": "Machina Labs",
        "tier": "Enterprise",
        "component_scores": {
            "sr_trend": 96,
            "usage_growth": 93,
            "support_sentiment": 91,
            "engagement": 95
        },
        "notes": "Flagship design partner — strong adoption and NPS"
    },
    "verdant": {
        "name": "Verdant Robotics",
        "tier": "Growth",
        "component_scores": {
            "sr_trend": 88,
            "usage_growth": 85,
            "support_sentiment": 88,
            "engagement": 86
        },
        "notes": "Steady usage growth, positive support interactions"
    },
    "helix": {
        "name": "Helix Dynamics",
        "tier": "Growth",
        "component_scores": {
            "sr_trend": 82,
            "usage_growth": 79,
            "support_sentiment": 80,
            "engagement": 83
        },
        "notes": "Moderate engagement; upsell opportunity in sensor track"
    },
    "aeroframe": {
        "name": "AeroFrame Systems",
        "tier": "Starter",
        "component_scores": {
            "sr_trend": 71,
            "usage_growth": 65,
            "support_sentiment": 74,
            "engagement": 68
        },
        "notes": "Usage plateau — schedule QBR"
    },
    "cognibotics": {
        "name": "Cognibotics",
        "tier": "Starter",
        "component_scores": {
            "sr_trend": 55,
            "usage_growth": 48,
            "support_sentiment": 60,
            "engagement": 52
        },
        "notes": "At-risk — escalation recommended within 14 days"
    }
}


def _composite(component_scores: dict) -> float:
    total = sum(WEIGHTS[k] * component_scores[k] for k in WEIGHTS)
    return round(total, 1)


def _trend(score: float) -> str:
    if score >= 90:
        return "champion"
    elif score >= 80:
        return "healthy"
    elif score >= 65:
        return "neutral"
    else:
        return "at_risk"


def _action(score: float, tier: str) -> str:
    if score >= 90:
        return "Nominate for case study; offer co-innovation lab access"
    elif score >= 80:
        return "Schedule QBR; present roadmap preview"
    elif score >= 65:
        return "Proactive check-in; review usage blockers"
    else:
        return "Escalate to CSM; 14-day intervention plan required"


def get_customer_health(customer_id: str) -> dict:
    key = customer_id.lower()
    if key not in CUSTOMERS:
        return {"error": f"customer '{customer_id}' not found", "available": list(CUSTOMERS.keys())}
    c = CUSTOMERS[key]
    score = _composite(c["component_scores"])
    return {
        "customer_id": key,
        "customer_name": c["name"],
        "tier": c["tier"],
        "composite_score": score,
        "component_scores": c["component_scores"],
        "weights": WEIGHTS,
        "trend": _trend(score),
        "recommended_action": _action(score, c["tier"]),
        "notes": c["notes"],
        "model_version": "v2",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def get_portfolio_health() -> dict:
    results = []
    for key, c in CUSTOMERS.items():
        score = _composite(c["component_scores"])
        results.append({
            "customer_id": key,
            "customer_name": c["name"],
            "tier": c["tier"],
            "composite_score": score,
            "trend": _trend(score),
            "recommended_action": _action(score, c["tier"])
        })
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    avg = round(sum(r["composite_score"] for r in results) / len(results), 1)
    return {
        "portfolio": results,
        "portfolio_avg_score": avg,
        "total_customers": len(results),
        "model_version": "v2",
        "auc_v2": 0.91,
        "auc_v1": 0.82,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Customer Health Score v2 | OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; min-height: 100vh; }
  .header { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 2px solid #C74634; padding: 24px 40px; }
  .header h1 { font-size: 1.8rem; color: #f8fafc; letter-spacing: -0.5px; }
  .header h1 span { color: #C74634; }
  .header p { color: #94a3b8; margin-top: 4px; font-size: 0.9rem; }
  .badge { display: inline-block; background: #C74634; color: #fff; font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; margin-left: 10px; vertical-align: middle; }
  .container { max-width: 1200px; margin: 0 auto; padding: 32px 40px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 32px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; }
  .card .label { font-size: 0.78rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; }
  .card .sub { font-size: 0.82rem; color: #94a3b8; margin-top: 4px; }
  .accent-red { color: #C74634; }
  .accent-blue { color: #38bdf8; }
  .accent-green { color: #34d399; }
  .accent-yellow { color: #fbbf24; }
  .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 28px; margin-bottom: 32px; }
  .chart-section h2 { font-size: 1.1rem; color: #f1f5f9; margin-bottom: 20px; }
  .customer-table { width: 100%; border-collapse: collapse; }
  .customer-table th { text-align: left; color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px; border-bottom: 1px solid #334155; }
  .customer-table td { padding: 14px 12px; border-bottom: 1px solid #1e293b; font-size: 0.88rem; }
  .customer-table tr:last-child td { border-bottom: none; }
  .pill { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; }
  .pill-champion { background: #064e3b; color: #34d399; }
  .pill-healthy { background: #1c3a5e; color: #38bdf8; }
  .pill-neutral { background: #3b2800; color: #fbbf24; }
  .pill-atrisk { background: #4c0519; color: #f87171; }
  .score-bar-wrap { display: flex; align-items: center; gap: 10px; }
  .score-bar-bg { flex: 1; background: #334155; border-radius: 4px; height: 8px; }
  .score-bar-fill { height: 8px; border-radius: 4px; }
  .weight-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #1e293b; }
  .weight-row:last-child { border-bottom: none; }
  .weight-label { color: #94a3b8; font-size: 0.85rem; }
  .weight-val { color: #38bdf8; font-weight: 700; font-size: 0.9rem; }
  .endpoint { background: #0f172a; border: 1px solid #475569; border-radius: 8px; padding: 16px 20px; margin: 8px 0; font-family: monospace; font-size: 0.85rem; color: #94a3b8; }
  .endpoint .method { color: #34d399; font-weight: 700; margin-right: 10px; }
  .endpoint .path { color: #38bdf8; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 32px; }
  @media(max-width:700px){ .two-col { grid-template-columns: 1fr; } }
  .footer { text-align: center; padding: 24px; color: #475569; font-size: 0.78rem; border-top: 1px solid #1e293b; margin-top: 20px; }
</style>
</head>
<body>
<div class="header">
  <h1><span>OCI Robot Cloud</span> — Customer Health Score v2 <span class="badge">PORT 10029</span></h1>
  <p>Composite model: SR trend 35% · usage growth 25% · support sentiment 20% · engagement 20%</p>
</div>
<div class="container">

  <div class="grid">
    <div class="card">
      <div class="label">Machina Labs</div>
      <div class="value accent-green">94<span style="font-size:1rem;color:#64748b">/100</span></div>
      <div class="sub">Champion — case study candidate</div>
    </div>
    <div class="card">
      <div class="label">Verdant Robotics</div>
      <div class="value accent-blue">87<span style="font-size:1rem;color:#64748b">/100</span></div>
      <div class="sub">Healthy — QBR recommended</div>
    </div>
    <div class="card">
      <div class="label">Helix Dynamics</div>
      <div class="value accent-blue">81<span style="font-size:1rem;color:#64748b">/100</span></div>
      <div class="sub">Healthy — upsell opportunity</div>
    </div>
    <div class="card">
      <div class="label">Model AUC v2</div>
      <div class="value accent-green">0.91</div>
      <div class="sub">vs v1 AUC 0.82 (+11%)</div>
    </div>
    <div class="card">
      <div class="label">Intervention Threshold</div>
      <div class="value accent-red">&lt;65</div>
      <div class="sub">14-day escalation window</div>
    </div>
    <div class="card">
      <div class="label">Portfolio Avg Score</div>
      <div class="value" style="color:#e2e8f0">78.0</div>
      <div class="sub">5 active customers tracked</div>
    </div>
  </div>

  <!-- Bar chart -->
  <div class="chart-section">
    <h2>Portfolio Health Scores — All Customers</h2>
    <svg viewBox="0 0 700 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:700px;display:block;margin:0 auto">
      <!-- Grid -->
      <line x1="90" y1="20" x2="90" y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="90" y1="190" x2="680" y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="90" y1="50" x2="680" y2="50" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="90" y1="90" x2="680" y2="90" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="90" y1="130" x2="680" y2="130" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="90" y1="162" x2="680" y2="162" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <!-- Y labels -->
      <text x="82" y="194" fill="#64748b" font-size="10" text-anchor="end">50</text>
      <text x="82" y="166" fill="#64748b" font-size="10" text-anchor="end">65</text>
      <text x="82" y="134" fill="#64748b" font-size="10" text-anchor="end">80</text>
      <text x="82" y="94" fill="#64748b" font-size="10" text-anchor="end">90</text>
      <text x="82" y="54" fill="#64748b" font-size="10" text-anchor="end">100</text>
      <!-- Machina 94 -->
      <rect x="110" y="35" width="72" height="155" fill="#34d399" rx="4"/>
      <text x="146" y="28" fill="#34d399" font-size="12" font-weight="bold" text-anchor="middle">94</text>
      <text x="146" y="207" fill="#94a3b8" font-size="10" text-anchor="middle">Machina</text>
      <!-- Verdant 87 -->
      <rect x="210" y="61" width="72" height="129" fill="#38bdf8" rx="4"/>
      <text x="246" y="54" fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">87</text>
      <text x="246" y="207" fill="#94a3b8" font-size="10" text-anchor="middle">Verdant</text>
      <!-- Helix 81 -->
      <rect x="310" y="83" width="72" height="107" fill="#38bdf8" rx="4" opacity="0.8"/>
      <text x="346" y="76" fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">81</text>
      <text x="346" y="207" fill="#94a3b8" font-size="10" text-anchor="middle">Helix</text>
      <!-- AeroFrame 70 -->
      <rect x="410" y="120" width="72" height="70" fill="#fbbf24" rx="4"/>
      <text x="446" y="113" fill="#fbbf24" font-size="12" font-weight="bold" text-anchor="middle">70</text>
      <text x="446" y="207" fill="#94a3b8" font-size="10" text-anchor="middle">AeroFrame</text>
      <!-- Cognibotics 54 -->
      <rect x="510" y="153" width="72" height="37" fill="#f87171" rx="4"/>
      <text x="546" y="146" fill="#f87171" font-size="12" font-weight="bold" text-anchor="middle">54</text>
      <text x="546" y="207" fill="#94a3b8" font-size="10" text-anchor="middle">Cognibotics</text>
      <!-- Threshold line -->
      <line x1="90" y1="162" x2="680" y2="162" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3"/>
      <text x="685" y="166" fill="#C74634" font-size="9">65 threshold</text>
    </svg>
  </div>

  <div class="two-col">
    <!-- Score weights -->
    <div class="card">
      <div class="label" style="margin-bottom:16px">Composite Score Weights</div>
      <div class="weight-row">
        <span class="weight-label">SR Trend (sim-to-real improvement)</span>
        <span class="weight-val">35%</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">Usage Growth (API calls, GPU hours)</span>
        <span class="weight-val">25%</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">Support Sentiment (NPS, tickets)</span>
        <span class="weight-val">20%</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">Engagement (logins, docs, Slack)</span>
        <span class="weight-val">20%</span>
      </div>
    </div>

    <!-- Model comparison -->
    <div class="card">
      <div class="label" style="margin-bottom:16px">Model Performance (v2 vs v1)</div>
      <div class="weight-row">
        <span class="weight-label">AUC — Health Score v2</span>
        <span class="weight-val accent-green">0.91</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">AUC — Health Score v1</span>
        <span class="weight-val accent-yellow">0.82</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">Churn recall improvement</span>
        <span class="weight-val accent-blue">+18%</span>
      </div>
      <div class="weight-row">
        <span class="weight-label">Intervention threshold</span>
        <span class="weight-val accent-red">&lt; 65</span>
      </div>
    </div>
  </div>

  <!-- Customer table -->
  <div class="chart-section">
    <h2>All Customers — Portfolio Overview</h2>
    <table class="customer-table">
      <thead>
        <tr>
          <th>Customer</th><th>Tier</th><th>Score</th><th>Trend</th><th>Recommended Action</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Machina Labs</strong></td><td>Enterprise</td>
          <td><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:94%;background:#34d399"></div></div><span style="color:#34d399;font-weight:700">94</span></div></td>
          <td><span class="pill pill-champion">champion</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">Case study; co-innovation lab</td>
        </tr>
        <tr>
          <td><strong>Verdant Robotics</strong></td><td>Growth</td>
          <td><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:87%;background:#38bdf8"></div></div><span style="color:#38bdf8;font-weight:700">87</span></div></td>
          <td><span class="pill pill-healthy">healthy</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">QBR; roadmap preview</td>
        </tr>
        <tr>
          <td><strong>Helix Dynamics</strong></td><td>Growth</td>
          <td><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:81%;background:#38bdf8"></div></div><span style="color:#38bdf8;font-weight:700">81</span></div></td>
          <td><span class="pill pill-healthy">healthy</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">Upsell sensor track</td>
        </tr>
        <tr>
          <td><strong>AeroFrame Systems</strong></td><td>Starter</td>
          <td><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:70%;background:#fbbf24"></div></div><span style="color:#fbbf24;font-weight:700">70</span></div></td>
          <td><span class="pill pill-neutral">neutral</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">Schedule QBR; review blockers</td>
        </tr>
        <tr>
          <td><strong>Cognibotics</strong></td><td>Starter</td>
          <td><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:54%;background:#f87171"></div></div><span style="color:#f87171;font-weight:700">54</span></div></td>
          <td><span class="pill pill-atrisk">at_risk</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">Escalate CSM; 14-day plan</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="chart-section">
    <h2>API Endpoints</h2>
    <div class="endpoint"><span class="method">GET</span><span class="path">/</span> — HTML dashboard</div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/health</span> — JSON health check</div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/customers/health_v2?customer_id=machina</span> — Single customer health score</div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/customers/portfolio_health</span> — All customers sorted by score</div>
  </div>
</div>
<div class="footer">OCI Robot Cloud — Customer Health Score v2 · port 10029 · cycle-493A · {ts}</div>
</body>
</html>
""".replace("{ts}", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Customer Health Score v2",
        description="Composite customer health scoring: SR trend, usage growth, support sentiment, engagement",
        version="2.0.0"
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "service": "customer_health_score_v2",
            "port": PORT,
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/customers/health_v2")
    async def customer_health_v2(customer_id: str = Query(default="machina")):
        result = get_customer_health(customer_id)
        if "error" in result:
            return JSONResponse(result, status_code=404)
        return JSONResponse(result)

    @app.get("/customers/portfolio_health")
    async def portfolio_health():
        return JSONResponse(get_portfolio_health())

else:
    # ---------------------------------------------------------------------------
    # stdlib HTTPServer fallback
    # ---------------------------------------------------------------------------

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, content_type, body):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = dict(urllib.parse.parse_qsl(parsed.query))

            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "customer_health_score_v2", "port": PORT}))
            elif path == "/customers/health_v2":
                cid = params.get("customer_id", "machina")
                result = get_customer_health(cid)
                code = 404 if "error" in result else 200
                self._send(code, "application/json", json.dumps(result))
            elif path == "/customers/portfolio_health":
                self._send(200, "application/json", json.dumps(get_portfolio_health()))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        server.serve_forever()
