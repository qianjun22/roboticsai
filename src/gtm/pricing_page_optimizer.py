"""pricing_page_optimizer.py — port 10073
A/B testing for pricing page variants with conversion optimization.
Variant A: feature-led | Variant B: ROI-led | Variant C: comparison.
"""

from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10073

# Variant definitions
_VARIANTS: Dict[str, Dict[str, Any]] = {
    "A": {
        "name": "Feature-Led",
        "headline": "Enterprise Robot Orchestration",
        "subheadline": "Deploy, train, and manage robot fleets at scale.",
        "cta": "Start Free Trial",
        "cta_color": "#334155",
        "conversion_rate": 2.8,
        "sessions": 12400,
        "conversions": 347,
        "recommended_changes": [
            "Lead with ROI calculator instead of feature list",
            "Add social proof above the fold",
            "Replace generic CTA with 'Calculate My ROI'",
        ],
        "psychology": "Feature enumeration — low urgency, high cognitive load",
    },
    "B": {
        "name": "ROI-Led",
        "headline": "Cut Robot Training Costs by 60%",
        "subheadline": "OCI Robot Cloud pays for itself in 3 months. Calculate your savings.",
        "cta": "Calculate My ROI →",
        "cta_color": "#C74634",
        "conversion_rate": 4.2,
        "sessions": 11800,
        "conversions": 496,
        "recommended_changes": [
            "Add AWS/Azure pricing anchor in first screen",
            "Include customer logo strip (social proof)",
            "Shorten ROI calculator to 2 inputs (fleet size + training freq)",
        ],
        "psychology": "Loss aversion + ROI anchoring — highest conversion variant",
    },
    "C": {
        "name": "Comparison",
        "headline": "Why Teams Switch from AWS RoboMaker",
        "subheadline": "Side-by-side: cost, speed, and support.",
        "cta": "See Full Comparison",
        "cta_color": "#0ea5e9",
        "conversion_rate": 3.6,
        "sessions": 10950,
        "conversions": 394,
        "recommended_changes": [
            "Soften competitive tone — 'switch from' triggers defensiveness",
            "Add 'Try free for 30 days' below comparison table",
            "Highlight OCI free tier in comparison row",
        ],
        "psychology": "Competitor anchor — works well for already-aware buyers",
    },
}

# In-memory session store (resets on restart — suitable for demo)
_session_store: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pricing Page Optimizer — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
    header h1 { font-size: 1.5rem; color: #f8fafc; }
    header span.tag { background: #C74634; color: #fff; font-size: 0.75rem; padding: 3px 10px; border-radius: 9999px; font-weight: 600; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 36px; }
    .kpi { background: #1e293b; border-radius: 12px; padding: 22px 20px; border-left: 4px solid #C74634; }
    .kpi .val { font-size: 2.4rem; font-weight: 700; color: #38bdf8; }
    .kpi .label { font-size: 0.82rem; color: #94a3b8; margin-top: 4px; }
    .kpi .delta { font-size: 0.85rem; color: #4ade80; margin-top: 4px; }
    .kpi.winner { border-left-color: #4ade80; }
    .kpi.winner .val { color: #4ade80; }
    .section { background: #1e293b; border-radius: 12px; padding: 28px; margin-bottom: 28px; }
    .section h2 { font-size: 1.1rem; color: #38bdf8; margin-bottom: 20px; border-bottom: 1px solid #334155; padding-bottom: 10px; }
    .variant-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 18px; }
    .variant-card { background: #0f172a; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
    .variant-card.winner { border-color: #4ade80; }
    .variant-card h3 { font-size: 1rem; margin-bottom: 4px; }
    .variant-card .cr { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .variant-card .sessions { font-size: 0.8rem; color: #64748b; margin-bottom: 10px; }
    .variant-card .headline { font-size: 0.85rem; color: #94a3b8; font-style: italic; margin-bottom: 8px; }
    .variant-card ul { padding-left: 18px; font-size: 0.8rem; color: #64748b; line-height: 1.6; }
    .badge { display: inline-block; font-size: 0.72rem; padding: 2px 8px; border-radius: 9999px; font-weight: 600; margin-left: 8px; }
    .badge.winner { background: #166534; color: #4ade80; }
    .badge.mid { background: #1e3a5f; color: #38bdf8; }
    .badge.low { background: #3f1f1f; color: #f87171; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .psych-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; margin-top: 8px; }
    .psych-card { background: #0f172a; border-radius: 8px; padding: 14px 16px; border: 1px solid #334155; }
    .psych-card h3 { font-size: 0.88rem; color: #C74634; margin-bottom: 6px; }
    .psych-card p { font-size: 0.8rem; color: #94a3b8; line-height: 1.55; }
    .endpoint { background: #0f172a; border-radius: 6px; padding: 10px 14px; font-family: monospace; font-size: 0.82rem; color: #38bdf8; margin-top: 8px; border: 1px solid #334155; }
    footer { text-align: center; padding: 24px; color: #475569; font-size: 0.78rem; }
  </style>
</head>
<body>
<header>
  <h1>Pricing Page Optimizer</h1>
  <span class="tag">port 10073</span>
  <span class="tag" style="background:#166534;color:#4ade80">Variant B Leading — 4.2%</span>
</header>
<div class="container">
  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi winner">
      <div class="val">4.2%</div>
      <div class="label">Variant B — ROI-Led (winner)</div>
      <div class="delta">+1.4pp vs A · +0.6pp vs C</div>
    </div>
    <div class="kpi">
      <div class="val">2.8%</div>
      <div class="label">Variant A — Feature-Led</div>
      <div class="delta" style="color:#f87171">lowest conversion</div>
    </div>
    <div class="kpi">
      <div class="val">3.6%</div>
      <div class="label">Variant C — Comparison</div>
      <div class="delta">AWS anchor effect</div>
    </div>
    <div class="kpi">
      <div class="val">35,150</div>
      <div class="label">Total Sessions (30-day test)</div>
      <div class="delta">+1,237 conversions total</div>
    </div>
  </div>

  <!-- Bar Chart -->
  <div class="section">
    <h2>Conversion Rate by Variant — A/B/C Test (30-day)</h2>
    <svg width="100%" viewBox="0 0 700 280" xmlns="http://www.w3.org/2000/svg">
      <!-- background grid -->
      <line x1="80" y1="20" x2="80" y2="220" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="220" x2="680" y2="220" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="180" x2="680" y2="180" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="80" y1="140" x2="680" y2="140" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="80" y1="100" x2="680" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="80" y1="60" x2="680" y2="60" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <!-- y axis labels: 0% to 6% -->
      <text x="70" y="224" text-anchor="end" fill="#64748b" font-size="11">0%</text>
      <text x="70" y="184" text-anchor="end" fill="#64748b" font-size="11">1.5%</text>
      <text x="70" y="144" text-anchor="end" fill="#64748b" font-size="11">3%</text>
      <text x="70" y="104" text-anchor="end" fill="#64748b" font-size="11">4.5%</text>
      <text x="70" y="64" text-anchor="end" fill="#64748b" font-size="11">6%</text>
      <!-- Variant A: 2.8% → height = (2.8/6)*160 = 74.7 -->
      <rect x="130" y="145.3" width="80" height="74.7" fill="#334155" rx="4"/>
      <text x="170" y="140" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600">2.8%</text>
      <text x="170" y="248" text-anchor="middle" fill="#94a3b8" font-size="12">Variant A</text>
      <text x="170" y="262" text-anchor="middle" fill="#64748b" font-size="10">Feature-Led</text>
      <!-- Variant B: 4.2% → height = (4.2/6)*160 = 112 -->
      <rect x="300" y="108" width="80" height="112" fill="#C74634" rx="4"/>
      <text x="340" y="103" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600">4.2%</text>
      <text x="340" y="248" text-anchor="middle" fill="#4ade80" font-size="12" font-weight="700">Variant B ★</text>
      <text x="340" y="262" text-anchor="middle" fill="#64748b" font-size="10">ROI-Led</text>
      <!-- Variant C: 3.6% → height = (3.6/6)*160 = 96 -->
      <rect x="480" y="124" width="80" height="96" fill="#0ea5e9" rx="4" opacity="0.8"/>
      <text x="520" y="119" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600">3.6%</text>
      <text x="520" y="248" text-anchor="middle" fill="#94a3b8" font-size="12">Variant C</text>
      <text x="520" y="262" text-anchor="middle" fill="#64748b" font-size="10">Comparison</text>
      <!-- title annotation -->
      <text x="390" y="30" text-anchor="middle" fill="#475569" font-size="10">30-day A/B/C test · 35,150 sessions · p &lt; 0.01</text>
    </svg>
  </div>

  <!-- Variant cards -->
  <div class="section">
    <h2>Variant Details &amp; Recommendations</h2>
    <div class="variant-grid">
      <div class="variant-card">
        <h3>Variant A — Feature-Led <span class="badge low">2.8%</span></h3>
        <div class="cr">2.8%</div>
        <div class="sessions">12,400 sessions · 347 conversions</div>
        <div class="headline">"Enterprise Robot Orchestration — Deploy, train, and manage robot fleets at scale."</div>
        <ul>
          <li>Lead with ROI calculator instead of feature list</li>
          <li>Add social proof above the fold</li>
          <li>Replace generic CTA with 'Calculate My ROI'</li>
        </ul>
      </div>
      <div class="variant-card winner">
        <h3>Variant B — ROI-Led <span class="badge winner">4.2% winner</span></h3>
        <div class="cr" style="color:#4ade80">4.2%</div>
        <div class="sessions">11,800 sessions · 496 conversions</div>
        <div class="headline">"Cut Robot Training Costs by 60% — OCI Robot Cloud pays for itself in 3 months."</div>
        <ul>
          <li>Add AWS/Azure pricing anchor in first screen</li>
          <li>Include customer logo strip (social proof)</li>
          <li>Shorten ROI calculator to 2 inputs (fleet size + training freq)</li>
        </ul>
      </div>
      <div class="variant-card">
        <h3>Variant C — Comparison <span class="badge mid">3.6%</span></h3>
        <div class="cr">3.6%</div>
        <div class="sessions">10,950 sessions · 394 conversions</div>
        <div class="headline">"Why Teams Switch from AWS RoboMaker — side-by-side: cost, speed, and support."</div>
        <ul>
          <li>Soften competitive tone — 'switch from' triggers defensiveness</li>
          <li>Add 'Try free for 30 days' below comparison table</li>
          <li>Highlight OCI free tier in comparison row</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- Pricing Psychology -->
  <div class="section">
    <h2>Pricing Psychology &amp; Optimisation Levers</h2>
    <div class="psych-grid">
      <div class="psych-card">
        <h3>AWS Anchor Effect</h3>
        <p>Showing AWS RoboMaker at $4.80/hr before OCI at $1.92/hr creates a 60% savings anchor. Variant B leads with this in the hero section — highest engagement on scroll.</p>
      </div>
      <div class="psych-card">
        <h3>ROI Calculator CTA</h3>
        <p>"Calculate My ROI" outperforms "Start Free Trial" by 1.4pp. Interactive calculators qualify intent and increase perceived value before the free-trial commit.</p>
      </div>
      <div class="psych-card">
        <h3>Loss Aversion Framing</h3>
        <p>"Cut costs by 60%" activates loss aversion more strongly than "save money". Specific percentages increase credibility and urgency simultaneously.</p>
      </div>
      <div class="psych-card">
        <h3>Social Proof Timing</h3>
        <p>Logo strips placed after the value proposition (not in the header) increased scroll depth by 18% in Variant B. Logos validate, not introduce.</p>
      </div>
    </div>
  </div>

  <!-- Endpoints -->
  <div class="section">
    <h2>API Endpoints</h2>
    <div class="endpoint">GET  /pricing/page_config?variant=A|B|C — page elements, conversion rate, recommended changes</div>
    <div class="endpoint">POST /pricing/track_conversion — visitor_id, variant, converted → updated conversion rates</div>
    <div class="endpoint">GET  /health — service health JSON</div>
    <div class="endpoint">GET  /       — this dashboard</div>
  </div>
</div>
<footer>OCI Robot Cloud · Pricing Page Optimizer v1 · port 10073</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
if _USE_FASTAPI:
    class TrackConversionRequest(BaseModel):
        visitor_id: str
        variant: str
        converted: bool

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def _get_page_config(variant: str) -> Dict[str, Any]:
    variant = variant.upper()
    if variant not in _VARIANTS:
        raise ValueError(f"variant must be A, B, or C — got '{variant}'")
    cfg = dict(_VARIANTS[variant])
    cfg["variant"] = variant
    return cfg


def _track_conversion(visitor_id: str, variant: str, converted: bool) -> Dict[str, Any]:
    variant = variant.upper()
    if variant not in _VARIANTS:
        raise ValueError(f"variant must be A, B, or C — got '{variant}'")

    # Update in-memory store
    _session_store[visitor_id] = {
        "variant": variant,
        "converted": converted,
        "ts": time.time(),
    }

    # Recompute live conversion rates from session store
    live_rates: Dict[str, Dict[str, int]] = {
        v: {"sessions": 0, "conversions": 0} for v in ("A", "B", "C")
    }
    for record in _session_store.values():
        v = record["variant"]
        live_rates[v]["sessions"] += 1
        if record["converted"]:
            live_rates[v]["conversions"] += 1

    updated_rates = {}
    for v, counts in live_rates.items():
        s, c = counts["sessions"], counts["conversions"]
        updated_rates[v] = round((c / s * 100), 2) if s > 0 else _VARIANTS[v]["conversion_rate"]

    return {
        "visitor_id": visitor_id,
        "variant": variant,
        "converted": converted,
        "updated_conversion_rates": updated_rates,
        "live_sessions_tracked": len(_session_store),
        "timestamp": time.time(),
    }


_HEALTH_PAYLOAD = {
    "status": "ok",
    "service": "pricing_page_optimizer",
    "port": PORT,
    "variants": ["A", "B", "C"],
    "winner": "B",
    "timestamp": None,
}

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
if _USE_FASTAPI:
    app = FastAPI(
        title="Pricing Page Optimizer",
        description="A/B testing for pricing page variants with conversion optimization",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health", response_class=JSONResponse)
    async def health():
        payload = dict(_HEALTH_PAYLOAD)
        payload["timestamp"] = time.time()
        return JSONResponse(content=payload)

    @app.get("/pricing/page_config", response_class=JSONResponse)
    async def page_config(variant: str = "B"):
        try:
            result = _get_page_config(variant)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return JSONResponse(content=result)

    @app.post("/pricing/track_conversion", response_class=JSONResponse)
    async def track_conversion(req: TrackConversionRequest):
        try:
            result = _track_conversion(req.visitor_id, req.variant, req.converted)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return JSONResponse(content=result)

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, content_type: str, body):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif self.path == "/health":
                payload = dict(_HEALTH_PAYLOAD)
                payload["timestamp"] = time.time()
                self._send(200, "application/json", json.dumps(payload))
            elif self.path.startswith("/pricing/page_config"):
                variant = "B"
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                    for part in qs.split("&"):
                        if part.startswith("variant="):
                            variant = part.split("=", 1)[1]
                try:
                    result = _get_page_config(variant)
                    self._send(200, "application/json", json.dumps(result))
                except ValueError as exc:
                    self._send(422, "application/json", json.dumps({"error": str(exc)}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path == "/pricing/track_conversion":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                try:
                    result = _track_conversion(
                        body.get("visitor_id", str(uuid.uuid4())),
                        body.get("variant", "B"),
                        bool(body.get("converted", False)),
                    )
                    self._send(200, "application/json", json.dumps(result))
                except ValueError as exc:
                    self._send(422, "application/json", json.dumps({"error": str(exc)}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

    def _run_stdlib():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[pricing_page_optimizer] stdlib HTTPServer listening on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_stdlib()
