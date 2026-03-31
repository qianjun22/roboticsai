"""revenue_operations_v2.py — Cycle-496A (port 10041)

Unified RevOps: marketing + sales + CS aligned metrics with automated alerts.

Endpoints:
  GET  /                      → HTML dashboard
  GET  /health                → JSON health
  GET  /revops/metrics        → ?period=  → ARR, pipeline, win rate, CAC, LTV, LTV:CAC, alerts
  GET  /revops/attribution    → ?customer_id= → multi-touch attribution breakdown
"""

import json
import random
from datetime import datetime

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:  # pragma: no cover
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Domain data
# ---------------------------------------------------------------------------

_PERIODS = ["mtd", "qtd", "ytd", "last_quarter", "last_year"]

_BASE_METRICS = {
    "arr": 250_000,
    "pipeline": 1_200_000,
    "win_rate": 73,
    "cac": 12_000,
    "ltv": 415_000,
    "ltv_cac_ratio": 34.6,
}

_PERIOD_MULTIPLIERS = {
    "mtd":          {"arr": 1.00, "pipeline": 0.32, "win_rate": 1.00, "cac": 1.00, "ltv": 1.00},
    "qtd":          {"arr": 1.00, "pipeline": 0.78, "win_rate": 1.00, "cac": 1.00, "ltv": 1.00},
    "ytd":          {"arr": 1.00, "pipeline": 1.00, "win_rate": 1.00, "cac": 1.00, "ltv": 1.00},
    "last_quarter": {"arr": 0.88, "pipeline": 0.91, "win_rate": 0.96, "cac": 1.05, "ltv": 0.97},
    "last_year":    {"arr": 0.62, "pipeline": 0.55, "win_rate": 0.89, "cac": 1.18, "ltv": 0.91},
}

_ALERTS = [
    "Pipeline coverage 4.8× — healthy (threshold: 3×)",
    "Win rate 73% exceeds Q-target of 65% — on track",
    "LTV:CAC 34.6× well above SaaS benchmark of 3×",
    "ALERT: 2 deals >$200k at risk — last activity >14 days",
    "ALERT: CAC payback 0.35 months — verify data completeness",
]

_ATTRIBUTION_CHANNELS = [
    {"channel": "NVIDIA Referral",      "touches": 3, "attribution_pct": 40.0, "stage": "sourced"},
    {"channel": "OCI Partner Program",  "touches": 2, "attribution_pct": 25.0, "stage": "influenced"},
    {"channel": "GTC Conference",       "touches": 4, "attribution_pct": 20.0, "stage": "accelerated"},
    {"channel": "Inbound Web",          "touches": 1, "attribution_pct": 10.0, "stage": "influenced"},
    {"channel": "SDR Outbound",         "touches": 2, "attribution_pct": 5.0,  "stage": "influenced"},
]


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML_DASHBOARD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Revenue Operations v2 | OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Arial, sans-serif; }
  header { background: #C74634; padding: 1.2rem 2rem; display: flex; align-items: center; gap: 1rem; }
  header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: .03em; }
  header span { font-size: 0.85rem; background: rgba(0,0,0,.25); padding: .2rem .7rem; border-radius: 999px; }
  main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.2rem; border-top: 3px solid #38bdf8; }
  .card.red { border-top-color: #C74634; }
  .card.green { border-top-color: #22c55e; }
  .card.yellow { border-top-color: #f59e0b; }
  .card h3 { font-size: .75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .5rem; }
  .card .val { font-size: 1.85rem; font-weight: 700; color: #38bdf8; }
  .card.green .val { color: #4ade80; }
  .card.yellow .val { color: #fbbf24; }
  .card.red .val { color: #f87171; }
  .card .sub { font-size: .8rem; color: #64748b; margin-top: .3rem; }
  section { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
  section h2 { font-size: 1rem; color: #38bdf8; margin-bottom: 1rem; font-weight: 600; }
  svg text { font-family: 'Segoe UI', Arial, sans-serif; }
  .alert-list { list-style: none; }
  .alert-list li { padding: .55rem .75rem; border-left: 3px solid #22c55e;
                   background: #0f172a; border-radius: 0 6px 6px 0; margin-bottom: .5rem;
                   font-size: .88rem; color: #cbd5e1; }
  .alert-list li.warn { border-left-color: #f59e0b; }
  .attr-row { display: flex; align-items: center; gap: .75rem; margin-bottom: .6rem; }
  .attr-label { width: 180px; font-size: .85rem; color: #94a3b8; flex-shrink: 0; }
  .attr-bar-bg { flex: 1; background: #0f172a; border-radius: 4px; height: 18px; }
  .attr-bar-fill { height: 18px; border-radius: 4px; background: #38bdf8; }
  .attr-bar-fill.nvidia { background: #C74634; }
  .attr-pct { width: 45px; text-align: right; font-size: .85rem; color: #e2e8f0; font-weight: 600; }
  footer { text-align: center; color: #334155; font-size: .75rem; padding: 2rem 0; }
</style>
</head>
<body>
<header>
  <h1>Revenue Operations v2</h1>
  <span>port 10041</span>
  <span>cycle-496A</span>
  <span>Unified Marketing + Sales + CS</span>
</header>
<main>
  <div class="grid">
    <div class="card">
      <h3>Annual Recurring Revenue</h3>
      <div class="val">$250K</div>
      <div class="sub">ARR (YTD)</div>
    </div>
    <div class="card green">
      <h3>Pipeline</h3>
      <div class="val">$1.2M</div>
      <div class="sub">4.8× coverage</div>
    </div>
    <div class="card green">
      <h3>Win Rate</h3>
      <div class="val">73%</div>
      <div class="sub">vs 65% target</div>
    </div>
    <div class="card">
      <h3>CAC</h3>
      <div class="val">$12K</div>
      <div class="sub">Customer acq. cost</div>
    </div>
    <div class="card">
      <h3>LTV</h3>
      <div class="val">$415K</div>
      <div class="sub">Lifetime value</div>
    </div>
    <div class="card green">
      <h3>LTV:CAC Ratio</h3>
      <div class="val">34.6×</div>
      <div class="sub">Benchmark: 3×</div>
    </div>
  </div>

  <section>
    <h2>Pipeline by Stage (SVG Bar Chart)</h2>
    <svg width="100%" viewBox="0 0 700 220" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="100" y1="20" x2="100" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="180" x2="680" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- grid lines -->
      <line x1="100" y1="20"  x2="680" y2="20"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
      <line x1="100" y1="60"  x2="680" y2="60"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
      <line x1="100" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
      <line x1="100" y1="140" x2="680" y2="140" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
      <!-- y labels (in $K) -->
      <text x="92" y="24"  text-anchor="end" fill="#64748b" font-size="11">$500K</text>
      <text x="92" y="64"  text-anchor="end" fill="#64748b" font-size="11">$375K</text>
      <text x="92" y="104" text-anchor="end" fill="#64748b" font-size="11">$250K</text>
      <text x="92" y="144" text-anchor="end" fill="#64748b" font-size="11">$125K</text>
      <text x="92" y="184" text-anchor="end" fill="#64748b" font-size="11">$0</text>
      <!-- bars: scale 500K → 160px -->
      <!-- Prospecting $480K → h=153.6 -->
      <rect x="115" y="26"  width="80" height="154" fill="#38bdf8" rx="3"/>
      <text x="155" y="20"  text-anchor="middle" fill="#7dd3fc" font-size="11" font-weight="700">$480K</text>
      <text x="155" y="198" text-anchor="middle" fill="#94a3b8" font-size="11">Prospecting</text>
      <!-- Qualified $300K → h=96 -->
      <rect x="215" y="84"  width="80" height="96"  fill="#38bdf8" rx="3"/>
      <text x="255" y="78"  text-anchor="middle" fill="#7dd3fc" font-size="11" font-weight="700">$300K</text>
      <text x="255" y="198" text-anchor="middle" fill="#94a3b8" font-size="11">Qualified</text>
      <!-- Proposal $220K → h=70.4 -->
      <rect x="315" y="109" width="80" height="71"  fill="#C74634" rx="3"/>
      <text x="355" y="103" text-anchor="middle" fill="#fca5a5" font-size="11" font-weight="700">$220K</text>
      <text x="355" y="198" text-anchor="middle" fill="#94a3b8" font-size="11">Proposal</text>
      <!-- Negotiation $140K → h=44.8 -->
      <rect x="415" y="135" width="80" height="45"  fill="#f59e0b" rx="3"/>
      <text x="455" y="129" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="700">$140K</text>
      <text x="455" y="198" text-anchor="middle" fill="#94a3b8" font-size="11">Negotiation</text>
      <!-- Closed-Won $60K → h=19.2 -->
      <rect x="515" y="161" width="80" height="19"  fill="#22c55e" rx="3"/>
      <text x="555" y="155" text-anchor="middle" fill="#4ade80" font-size="11" font-weight="700">$60K</text>
      <text x="555" y="198" text-anchor="middle" fill="#94a3b8" font-size="11">Closed-Won</text>
    </svg>
  </section>

  <section>
    <h2>Multi-Touch Attribution (sample customer)</h2>
    <div class="attr-row">
      <span class="attr-label">NVIDIA Referral</span>
      <div class="attr-bar-bg"><div class="attr-bar-fill nvidia" style="width:40%"></div></div>
      <span class="attr-pct">40%</span>
    </div>
    <div class="attr-row">
      <span class="attr-label">OCI Partner Program</span>
      <div class="attr-bar-bg"><div class="attr-bar-fill" style="width:25%"></div></div>
      <span class="attr-pct">25%</span>
    </div>
    <div class="attr-row">
      <span class="attr-label">GTC Conference</span>
      <div class="attr-bar-bg"><div class="attr-bar-fill" style="width:20%"></div></div>
      <span class="attr-pct">20%</span>
    </div>
    <div class="attr-row">
      <span class="attr-label">Inbound Web</span>
      <div class="attr-bar-bg"><div class="attr-bar-fill" style="width:10%"></div></div>
      <span class="attr-pct">10%</span>
    </div>
    <div class="attr-row">
      <span class="attr-label">SDR Outbound</span>
      <div class="attr-bar-bg"><div class="attr-bar-fill" style="width:5%"></div></div>
      <span class="attr-pct">5%</span>
    </div>
  </section>

  <section>
    <h2>Automated Alerts</h2>
    <ul class="alert-list">
      <li>Pipeline coverage 4.8× — healthy (threshold: 3×)</li>
      <li>Win rate 73% exceeds Q-target of 65% — on track</li>
      <li>LTV:CAC 34.6× well above SaaS benchmark of 3×</li>
      <li class="warn">ALERT: 2 deals &gt;$200k at risk — last activity &gt;14 days</li>
      <li class="warn">ALERT: CAC payback 0.35 months — verify data completeness</li>
    </ul>
  </section>

  <section>
    <h2>API Reference</h2>
    <p style="color:#94a3b8;font-size:.88rem;line-height:1.7;">
      <code style="color:#38bdf8">GET /health</code> — service health<br/>
      <code style="color:#38bdf8">GET /revops/metrics?period=ytd</code> — unified RevOps KPIs<br/>
      <code style="color:#38bdf8">GET /revops/attribution?customer_id=&lt;id&gt;</code> — multi-touch attribution
    </p>
  </section>
</main>
<footer>OCI Robot Cloud &mdash; Revenue Operations v2 &mdash; cycle-496A &mdash; port 10041</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Revenue Operations v2",
        description="Unified RevOps: marketing + sales + CS aligned metrics with alerts",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "service": "revenue_operations_v2",
            "port": 10041,
            "cycle": "496A",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/revops/metrics")
    def revops_metrics(period: str = Query(default="ytd", description="Period: mtd|qtd|ytd|last_quarter|last_year")):
        mult = _PERIOD_MULTIPLIERS.get(period, _PERIOD_MULTIPLIERS["ytd"])
        arr      = int(_BASE_METRICS["arr"]      * mult["arr"])
        pipeline = int(_BASE_METRICS["pipeline"] * mult["pipeline"])
        win_rate = round(_BASE_METRICS["win_rate"] * mult["win_rate"], 1)
        cac      = int(_BASE_METRICS["cac"]      * mult["cac"])
        ltv      = int(_BASE_METRICS["ltv"]      * mult["ltv"])
        ltv_cac  = round(ltv / cac, 1)
        alerts   = list(_ALERTS)
        if win_rate < 60:
            alerts.insert(0, f"ALERT: win rate {win_rate}% below 60% threshold")
        if pipeline < 600_000:
            alerts.insert(0, f"ALERT: pipeline ${pipeline:,} — coverage may be below 3×")
        return JSONResponse({
            "period": period,
            "arr": arr,
            "pipeline": pipeline,
            "win_rate": win_rate,
            "cac": cac,
            "ltv": ltv,
            "ltv_cac_ratio": ltv_cac,
            "alerts": alerts,
            "as_of": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/revops/attribution")
    def revops_attribution(customer_id: str = Query(default="sample-001", description="Customer ID")):
        rng = random.Random(hash(customer_id) & 0xFFFFFFFF)
        channels = []
        for ch in _ATTRIBUTION_CHANNELS:
            jitter = rng.uniform(-3.0, 3.0)
            pct = max(1.0, round(ch["attribution_pct"] + jitter, 1))
            channels.append({**ch, "attribution_pct": pct})
        # re-normalise to 100%
        total = sum(c["attribution_pct"] for c in channels)
        for c in channels:
            c["attribution_pct"] = round(c["attribution_pct"] / total * 100, 1)
        return JSONResponse({
            "customer_id": customer_id,
            "model": "linear_multi_touch",
            "channels": channels,
            "primary_source": max(channels, key=lambda x: x["attribution_pct"])["channel"],
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
        })

else:  # stdlib HTTPServer fallback
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs   = urllib.parse.parse_qs(parsed.query)
            if path == "/":
                self._send(200, "text/html; charset=utf-8", HTML_DASHBOARD.encode())
            elif path == "/health":
                body = json.dumps({"status": "ok", "port": 10041, "cycle": "496A"}).encode()
                self._send(200, "application/json", body)
            elif path == "/revops/metrics":
                period = qs.get("period", ["ytd"])[0]
                mult = _PERIOD_MULTIPLIERS.get(period, _PERIOD_MULTIPLIERS["ytd"])
                result = {
                    "period": period,
                    "arr": int(_BASE_METRICS["arr"] * mult["arr"]),
                    "pipeline": int(_BASE_METRICS["pipeline"] * mult["pipeline"]),
                    "win_rate": round(_BASE_METRICS["win_rate"] * mult["win_rate"], 1),
                    "cac": int(_BASE_METRICS["cac"] * mult["cac"]),
                    "ltv": int(_BASE_METRICS["ltv"] * mult["ltv"]),
                    "ltv_cac_ratio": 34.6,
                    "alerts": _ALERTS,
                }
                self._send(200, "application/json", json.dumps(result).encode())
            elif path == "/revops/attribution":
                customer_id = qs.get("customer_id", ["sample-001"])[0]
                result = {
                    "customer_id": customer_id,
                    "model": "linear_multi_touch",
                    "channels": _ATTRIBUTION_CHANNELS,
                    "primary_source": "NVIDIA Referral",
                }
                self._send(200, "application/json", json.dumps(result).encode())
            else:
                self._send(404, "text/plain", b"Not Found")


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10041)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", 10041), _Handler)
        print("[revenue_operations_v2] stdlib fallback listening on :10041")
        server.serve_forever()
