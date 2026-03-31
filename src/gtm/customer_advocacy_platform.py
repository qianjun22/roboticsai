"""Customer Advocacy Platform — reference and case study management service.

Port: 10007
Cycle: 487B
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer Advocacy Platform</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.4rem; border: 1px solid #334155; }
    .card h3 { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .unit { font-size: 0.85rem; color: #64748b; margin-top: 0.2rem; }
    .highlight { color: #C74634 !important; }
    .green { color: #4ade80 !important; }
    h2 { color: #38bdf8; font-size: 1.2rem; margin-bottom: 1rem; }
    .chart-wrap { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
    svg text { fill: #94a3b8; font-family: 'Segoe UI', sans-serif; }
    .case-card { background: #0f172a; border-radius: 8px; padding: 1.2rem; margin-bottom: 0.8rem; border-left: 4px solid #C74634; }
    .case-card h4 { color: #38bdf8; margin-bottom: 0.4rem; }
    .case-card p { color: #94a3b8; font-size: 0.88rem; line-height: 1.5; }
    .metric { display: inline-block; background: #0c4a6e; color: #7dd3fc; border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.8rem; font-weight: 600; margin-right: 0.4rem; }
    .endpoint { background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; border-left: 3px solid #C74634; }
    .endpoint .method { color: #C74634; font-weight: 700; font-size: 0.85rem; }
    .endpoint .path { color: #38bdf8; font-size: 0.9rem; margin-left: 0.5rem; }
    .endpoint .desc { color: #64748b; font-size: 0.82rem; margin-top: 0.3rem; }
  </style>
</head>
<body>
  <h1>Customer Advocacy Platform</h1>
  <p class="subtitle">Reference &amp; Case Study Management &mdash; Cycle 487B</p>

  <div class="grid">
    <div class="card">
      <h3>Published Case Studies</h3>
      <div class="value green">3</div>
      <div class="unit">live &amp; approved</div>
    </div>
    <div class="card">
      <h3>References Enrolled</h3>
      <div class="value">8</div>
      <div class="unit">active reference customers</div>
    </div>
    <div class="card">
      <h3>Close Rate Lift</h3>
      <div class="value green">2.3×</div>
      <div class="unit">vs. no reference</div>
    </div>
    <div class="card">
      <h3>Avg SR Improvement</h3>
      <div class="value highlight">+77%</div>
      <div class="unit">across published studies</div>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>Success Rate Improvement by Customer</h2>
    <svg width="100%" height="260" viewBox="0 0 700 260" preserveAspectRatio="xMidYMid meet">
      <!-- Axes -->
      <line x1="80" y1="20" x2="80" y2="200" stroke="#334155" stroke-width="1.5"/>
      <line x1="80" y1="200" x2="680" y2="200" stroke="#334155" stroke-width="1.5"/>

      <!-- Y labels -->
      <text x="72" y="204" text-anchor="end" font-size="11">0%</text>
      <text x="72" y="154" text-anchor="end" font-size="11">25%</text>
      <text x="72" y="104" text-anchor="end" font-size="11">50%</text>
      <text x="72" y="54" text-anchor="end" font-size="11">75%</text>
      <text x="72" y="24" text-anchor="end" font-size="11">100%</text>
      <line x1="80" y1="150" x2="680" y2="150" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>
      <line x1="80" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>
      <line x1="80" y1="50" x2="680" y2="50" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>
      <line x1="80" y1="20" x2="680" y2="20" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>

      <!-- Machina before 63% -->
      <rect x="110" y="74" width="50" height="126" fill="#C74634" opacity="0.6" rx="4"/>
      <text x="135" y="70" text-anchor="middle" font-size="10" fill="#fca5a5">63%</text>

      <!-- Machina after 91% -->
      <rect x="165" y="18" width="50" height="182" fill="#C74634" rx="4"/>
      <text x="190" y="14" text-anchor="middle" font-size="10" fill="#fca5a5">91%</text>
      <text x="163" y="220" text-anchor="middle" font-size="11">Machina</text>

      <!-- Verdant 81% -->
      <rect x="310" y="38" width="80" height="162" fill="#38bdf8" rx="4"/>
      <text x="350" y="33" text-anchor="middle" font-size="11" fill="#7dd3fc">81%</text>
      <text x="350" y="220" text-anchor="middle" font-size="11">Verdant</text>

      <!-- Helix 77% -->
      <rect x="470" y="46" width="80" height="154" fill="#38bdf8" opacity="0.7" rx="4"/>
      <text x="510" y="41" text-anchor="middle" font-size="11" fill="#7dd3fc">77%</text>
      <text x="510" y="220" text-anchor="middle" font-size="11">Helix</text>

      <!-- Legend -->
      <rect x="100" y="235" width="14" height="10" fill="#C74634" opacity="0.6" rx="2"/>
      <text x="118" y="244" font-size="10">Before OCI Robot Cloud</text>
      <rect x="280" y="235" width="14" height="10" fill="#C74634" rx="2"/>
      <text x="298" y="244" font-size="10">After (Machina)</text>
      <rect x="400" y="235" width="14" height="10" fill="#38bdf8" rx="2"/>
      <text x="418" y="244" font-size="10">Final SR (Verdant / Helix)</text>
    </svg>
  </div>

  <div class="chart-wrap">
    <h2>Published Case Studies</h2>

    <div class="case-card">
      <h4>Machina Robotics</h4>
      <p>Deployed GR00T N1.6 fine-tuning pipeline on OCI A100 cluster. Improved pick-and-place
         success rate from <strong style="color:#fca5a5">63%</strong> to
         <strong style="color:#4ade80">91%</strong> (+28 pp) in 6 weeks.</p>
      <div style="margin-top:0.5rem">
        <span class="metric">SR 63% → 91%</span>
        <span class="metric">6 weeks</span>
        <span class="metric">A100 cluster</span>
      </div>
    </div>

    <div class="case-card">
      <h4>Verdant Agriculture</h4>
      <p>Leveraged Isaac Sim SDG + DAgger curriculum to achieve <strong style="color:#4ade80">81%</strong>
         weeding-task SR with zero physical demonstrations at training time.</p>
      <div style="margin-top:0.5rem">
        <span class="metric">SR 81%</span>
        <span class="metric">Zero physical demos</span>
        <span class="metric">Isaac Sim SDG</span>
      </div>
    </div>

    <div class="case-card">
      <h4>Helix Logistics</h4>
      <p>Multi-task fine-tune across 4 SKU families. Achieved <strong style="color:#4ade80">77%</strong>
         average SR, reducing human intervention by 61% in warehouse picking operations.</p>
      <div style="margin-top:0.5rem">
        <span class="metric">SR 77%</span>
        <span class="metric">4 SKU families</span>
        <span class="metric">-61% interventions</span>
      </div>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>API Endpoints</h2>
    <div class="endpoint">
      <span class="method">GET</span><span class="path">/health</span>
      <div class="desc">Service health check</div>
    </div>
    <div class="endpoint">
      <span class="method">GET</span><span class="path">/advocacy/references</span>
      <div class="desc">List available reference customers (filter by topic or SR threshold)</div>
    </div>
    <div class="endpoint">
      <span class="method">POST</span><span class="path">/advocacy/case_study</span>
      <div class="desc">Generate a draft case study from customer metrics</div>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

REFERENCES = [
    {"company": "Machina Robotics", "topics": ["fine-tuning", "pick-and-place", "A100"], "sr_improvement": "63% → 91%"},
    {"company": "Verdant Agriculture", "topics": ["SDG", "DAgger", "zero-demo"], "sr_improvement": "0% → 81%"},
    {"company": "Helix Logistics", "topics": ["multi-task", "warehouse", "SKU"], "sr_improvement": "N/A → 77%"},
    {"company": "Orbis Manufacturing", "topics": ["sim-to-real", "fine-tuning"], "sr_improvement": "55% → 82%"},
    {"company": "Apex Assembly", "topics": ["DAgger", "continual-learning"], "sr_improvement": "70% → 88%"},
    {"company": "Stratos Automotive", "topics": ["multi-robot", "orchestration"], "sr_improvement": "68% → 85%"},
    {"company": "Crestline Pharma", "topics": ["precision", "GMP", "pick-and-place"], "sr_improvement": "74% → 90%"},
    {"company": "Solaris Fulfillment", "topics": ["warehouse", "high-throughput"], "sr_improvement": "61% → 83%"},
]


def _filter_references(topic: Optional[str] = None, min_sr: Optional[float] = None) -> List[dict]:
    result = []
    for ref in REFERENCES:
        if topic and topic.lower() not in " ".join(ref["topics"]).lower():
            continue
        if min_sr is not None:
            # Parse final SR from the string e.g. "63% → 91%" or "0% → 81%"
            try:
                final_sr = float(ref["sr_improvement"].split("→")[-1].strip().replace("%", ""))
                if final_sr < min_sr:
                    continue
            except (ValueError, IndexError):
                pass
        result.append(ref)
    return result


def _generate_case_study_draft(customer_id: str, metrics: Dict) -> str:
    sr_before = metrics.get("sr_before", "N/A")
    sr_after = metrics.get("sr_after", "N/A")
    weeks = metrics.get("weeks", "N/A")
    use_case = metrics.get("use_case", "robotic manipulation")
    return (
        f"{customer_id} partnered with OCI Robot Cloud to transform their {use_case} operations. "
        f"Starting from a baseline success rate of {sr_before}%, the team leveraged OCI's "
        f"GR00T N1.6 fine-tuning pipeline, Isaac Sim synthetic data generation, and DAgger "
        f"correction collection to achieve {sr_after}% success rate in {weeks} weeks. "
        f"The solution reduced total correction overhead by over 40% compared to uniform "
        f"sampling baselines, enabling {customer_id} to scale robot deployment with confidence."
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Customer Advocacy Platform",
        description="Customer reference and case study management",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "customer_advocacy_platform", "port": 10007})

    @app.get("/advocacy/references")
    async def list_references(
        topic: Optional[str] = Query(None, description="Filter by topic keyword"),
        min_sr: Optional[float] = Query(None, description="Minimum final SR percentage"),
    ):
        refs = _filter_references(topic=topic, min_sr=min_sr)
        return JSONResponse({"available_references": refs, "total": len(refs)})

    @app.post("/advocacy/case_study")
    async def create_case_study(body: dict):
        customer_id = body.get("customer_id", "Unknown Customer")
        metrics = body.get("metrics", {})
        draft = _generate_case_study_draft(customer_id, metrics)
        return JSONResponse({"case_study_draft": draft, "status": "draft"})

else:
    # ---------------------------------------------------------------------------
    # stdlib fallback (HTTPServer)
    # ---------------------------------------------------------------------------
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, content_type: str, body: str):
            encoded = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)

            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "service": "customer_advocacy_platform", "port": 10007}))
            elif path == "/advocacy/references":
                topic = params.get("topic", [None])[0]
                min_sr_raw = params.get("min_sr", [None])[0]
                min_sr = float(min_sr_raw) if min_sr_raw else None
                refs = _filter_references(topic=topic, min_sr=min_sr)
                self._send(200, "application/json", json.dumps({"available_references": refs, "total": len(refs)}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/advocacy/case_study":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {}
                customer_id = body.get("customer_id", "Unknown Customer")
                metrics = body.get("metrics", {})
                draft = _generate_case_study_draft(customer_id, metrics)
                self._send(200, "application/json", json.dumps({"case_study_draft": draft, "status": "draft"}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10007)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", 10007), _Handler)
        print("Customer Advocacy Platform running on http://0.0.0.0:10007 (stdlib fallback)")
        server.serve_forever()
