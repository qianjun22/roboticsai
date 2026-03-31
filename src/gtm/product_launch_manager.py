"""product_launch_manager.py — AI World September 2026 Launch Manager (port 10047).

Cycle-497B | OCI Robot Cloud

Tracks 5 workstreams: product, marketing, sales, partners, legal.
Overall readiness: 65%.  Critical path: marketing (45%) and partners (60%).
"""

from __future__ import annotations

import time
from typing import Dict, Any, List

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse as _urlparse
    import json as _json

# ---------------------------------------------------------------------------
# Workstream data
# ---------------------------------------------------------------------------
_LAUNCH_DATE = "2026-09-15"  # AI World, San Francisco
_DAYS_REMAINING = 169  # from 2026-03-30

_WORKSTREAMS: Dict[str, Dict[str, Any]] = {
    "product": {
        "completion_pct": 72.0,
        "owner": "Jun Qian",
        "blockers": [
            "Isaac Sim 2.0 certification pending",
            "GR00T N2 integration not yet validated",
        ],
        "next_milestone": "Alpha feature freeze — 2026-05-01",
    },
    "marketing": {
        "completion_pct": 45.0,
        "owner": "Maya Lin",
        "blockers": [
            "Brand guidelines v2 not approved",
            "Demo video production not started",
            "Press kit copy pending legal review",
        ],
        "next_milestone": "Campaign brief sign-off — 2026-04-15",
    },
    "sales": {
        "completion_pct": 68.0,
        "owner": "Alex Romero",
        "blockers": [
            "Pricing tiers not finalized",
            "3 design partner LOIs outstanding",
        ],
        "next_milestone": "Sales deck v3 review — 2026-04-22",
    },
    "partners": {
        "completion_pct": 60.0,
        "owner": "Priya Nair",
        "blockers": [
            "NVIDIA partnership agreement in legal",
            "Boston Dynamics MOU not signed",
            "AWS co-sell agreement delayed",
        ],
        "next_milestone": "Partner summit planning kickoff — 2026-04-10",
    },
    "legal": {
        "completion_pct": 80.0,
        "owner": "Dana Park",
        "blockers": [
            "Data processing addendum (DPA) under review",
        ],
        "next_milestone": "DPA sign-off — 2026-04-05",
    },
}

_OVERALL_READINESS = 65.0
_CRITICAL_PATH = ["marketing", "partners"]
_STARTED_AT = time.time()


def _readiness_payload() -> Dict[str, Any]:
    return {
        "overall_readiness_pct": _OVERALL_READINESS,
        "launch_event": "AI World September 2026",
        "launch_date": _LAUNCH_DATE,
        "days_remaining": _DAYS_REMAINING,
        "critical_path": _CRITICAL_PATH,
        "workstream_summary": {
            ws: d["completion_pct"] for ws, d in _WORKSTREAMS.items()
        },
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI World 2026 Launch Manager</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }}
    .subtitle {{ color: #38bdf8; font-size: 0.9rem; margin-bottom: 2rem; }}
    .cards {{ display: flex; gap: 1.2rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; flex: 1; min-width: 170px; }}
    .card h3 {{ font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
    .card .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .card .sub {{ font-size: 0.72rem; color: #64748b; margin-top: 0.3rem; }}
    .card.warn .val {{ color: #C74634; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
    .section h2 {{ color: #C74634; font-size: 1rem; margin-bottom: 1rem; }}
    svg text {{ font-family: 'Segoe UI', sans-serif; }}
    .bar-label {{ fill: #94a3b8; font-size: 11px; }}
    .bar-val   {{ fill: #e2e8f0; font-size: 11px; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th {{ text-align: left; color: #94a3b8; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; font-weight: 500; }}
    td {{ padding: 0.45rem 0.6rem; border-bottom: 1px solid #1e293b; }}
    .cp-tag {{ display: inline-block; background: #C74634; color: #fff; font-size: 0.68rem; border-radius: 4px; padding: 0.1rem 0.4rem; margin-left: 0.4rem; }}
    .endpoints {{ display: flex; gap: 0.6rem; flex-wrap: wrap; }}
    .ep {{ background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 0.4rem 0.8rem; font-size: 0.78rem; color: #38bdf8; }}
    .ep span {{ color: #C74634; font-weight: 600; }}
    footer {{ color: #475569; font-size: 0.72rem; margin-top: 2rem; }}
  </style>
</head>
<body>
  <h1>AI World 2026 Launch Manager</h1>
  <p class="subtitle">OCI Robot Cloud · Cycle-497B · Port 10047 · AI World San Francisco — September 15, 2026</p>

  <div class="cards">
    <div class="card"><h3>Overall Readiness</h3><div class="val">65%</div><div class="sub">across 5 workstreams</div></div>
    <div class="card"><h3>Days Remaining</h3><div class="val">169</div><div class="sub">to launch day</div></div>
    <div class="card warn"><h3>Critical Path</h3><div class="val">2</div><div class="sub">marketing, partners</div></div>
    <div class="card"><h3>Legal</h3><div class="val">80%</div><div class="sub">most advanced stream</div></div>
  </div>

  <div class="section">
    <h2>Workstream Readiness</h2>
    <!-- SVG bar chart: 5 workstreams -->
    <svg width="100%" viewBox="0 0 620 220" preserveAspectRatio="xMidYMid meet">
      <!-- axes -->
      <line x1="80" y1="10" x2="80" y2="175" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="175" x2="610" y2="175" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels (0, 25, 50, 75, 100) -->
      <text x="72" y="178" text-anchor="end" class="bar-label">0%</text>
      <text x="72" y="134" text-anchor="end" class="bar-label">25%</text>
      <text x="72" y="90"  text-anchor="end" class="bar-label">50%</text>
      <text x="72" y="47"  text-anchor="end" class="bar-label">75%</text>
      <text x="72" y="14"  text-anchor="end" class="bar-label">100%</text>
      <!-- gridlines -->
      <line x1="80" y1="134" x2="610" y2="134" stroke="#0f172a" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="80" y1="90"  x2="610" y2="90"  stroke="#0f172a" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="80" y1="47"  x2="610" y2="47"  stroke="#0f172a" stroke-width="1" stroke-dasharray="4 3"/>
      <!-- bars: bar height = pct/100 * 165, y = 175 - height -->
      <!-- product  72% → h=118.8, y=56.2 -->
      <rect x="95"  y="56"  width="75" height="119" fill="#38bdf8" rx="4"/>
      <!-- marketing 45% → h=74.25, y=100.75 -->
      <rect x="195" y="101" width="75" height="74"  fill="#C74634" rx="4"/>
      <!-- sales 68% → h=112.2, y=62.8 -->
      <rect x="295" y="63"  width="75" height="112" fill="#38bdf8" rx="4" opacity="0.85"/>
      <!-- partners 60% → h=99, y=76 -->
      <rect x="395" y="76"  width="75" height="99"  fill="#C74634" rx="4" opacity="0.8"/>
      <!-- legal 80% → h=132, y=43 -->
      <rect x="495" y="43"  width="75" height="132" fill="#38bdf8" rx="4" opacity="0.9"/>
      <!-- x labels -->
      <text x="132" y="193" text-anchor="middle" class="bar-label">Product</text>
      <text x="232" y="193" text-anchor="middle" class="bar-label">Marketing</text>
      <text x="332" y="193" text-anchor="middle" class="bar-label">Sales</text>
      <text x="432" y="193" text-anchor="middle" class="bar-label">Partners</text>
      <text x="532" y="193" text-anchor="middle" class="bar-label">Legal</text>
      <!-- value labels -->
      <text x="132" y="52"  text-anchor="middle" class="bar-val">72%</text>
      <text x="232" y="97"  text-anchor="middle" class="bar-val">45%</text>
      <text x="332" y="59"  text-anchor="middle" class="bar-val">68%</text>
      <text x="432" y="72"  text-anchor="middle" class="bar-val">60%</text>
      <text x="532" y="39"  text-anchor="middle" class="bar-val">80%</text>
    </svg>
    <p style="font-size:0.75rem;color:#64748b;margin-top:0.5rem;">Red bars = critical-path workstreams (marketing, partners)</p>
  </div>

  <div class="section">
    <h2>Workstream Details</h2>
    <table>
      <thead>
        <tr><th>Workstream</th><th>Owner</th><th>Completion</th><th>Next Milestone</th><th>Blockers</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>Product</td>
          <td>Jun Qian</td>
          <td>72%</td>
          <td>Alpha feature freeze — 2026-05-01</td>
          <td>2</td>
        </tr>
        <tr>
          <td>Marketing <span class="cp-tag">critical</span></td>
          <td>Maya Lin</td>
          <td style="color:#C74634">45%</td>
          <td>Campaign brief sign-off — 2026-04-15</td>
          <td>3</td>
        </tr>
        <tr>
          <td>Sales</td>
          <td>Alex Romero</td>
          <td>68%</td>
          <td>Sales deck v3 review — 2026-04-22</td>
          <td>2</td>
        </tr>
        <tr>
          <td>Partners <span class="cp-tag">critical</span></td>
          <td>Priya Nair</td>
          <td style="color:#C74634">60%</td>
          <td>Partner summit kickoff — 2026-04-10</td>
          <td>3</td>
        </tr>
        <tr>
          <td>Legal</td>
          <td>Dana Park</td>
          <td style="color:#38bdf8">80%</td>
          <td>DPA sign-off — 2026-04-05</td>
          <td>1</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>API Endpoints</h2>
    <div class="endpoints">
      <div class="ep"><span>GET</span> /health</div>
      <div class="ep"><span>GET</span> /launch/readiness</div>
      <div class="ep"><span>GET</span> /launch/status?workstream=product</div>
    </div>
  </div>

  <footer>OCI Robot Cloud · Product Launch Manager · Cycle-497B · AI World September 2026</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="AI World 2026 Launch Manager",
        description="Tracks 5 workstreams for the AI World September 2026 OCI Robot Cloud launch.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Dark-background HTML dashboard."""
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        """JSON health check."""
        return JSONResponse({
            "status": "ok",
            "service": "product_launch_manager",
            "port": 10047,
            "overall_readiness_pct": _OVERALL_READINESS,
            "days_remaining": _DAYS_REMAINING,
            "uptime_s": round(time.time() - _STARTED_AT, 1),
        })

    @app.get("/launch/status")
    async def launch_status(workstream: str = Query(..., description="One of: product, marketing, sales, partners, legal")):
        """Return status for a specific workstream."""
        ws = workstream.lower()
        if ws not in _WORKSTREAMS:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Unknown workstream '{workstream}'. Valid: {list(_WORKSTREAMS.keys())}",
            )
        data = _WORKSTREAMS[ws]
        return JSONResponse({
            "workstream": ws,
            "completion_pct": data["completion_pct"],
            "blockers": data["blockers"],
            "owner": data["owner"],
            "next_milestone": data["next_milestone"],
            "is_critical_path": ws in _CRITICAL_PATH,
        })

    @app.get("/launch/readiness")
    async def launch_readiness():
        """Return overall launch readiness, critical path, and days remaining."""
        return JSONResponse(_readiness_payload())

# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------
else:  # pragma: no cover
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
            parsed = _urlparse.urlparse(self.path)
            path = parsed.path
            params = dict(_urlparse.parse_qsl(parsed.query))

            if path == "/":
                self._send(200, "text/html", _DASHBOARD_HTML)
            elif path == "/health":
                body = _json.dumps({"status": "ok", "service": "product_launch_manager", "port": 10047})
                self._send(200, "application/json", body)
            elif path == "/launch/readiness":
                self._send(200, "application/json", _json.dumps(_readiness_payload()))
            elif path == "/launch/status":
                ws = params.get("workstream", "").lower()
                if ws not in _WORKSTREAMS:
                    self._send(404, "application/json", _json.dumps({"detail": "unknown workstream"}))
                    return
                data = _WORKSTREAMS[ws]
                body = _json.dumps({
                    "workstream": ws,
                    "completion_pct": data["completion_pct"],
                    "blockers": data["blockers"],
                    "owner": data["owner"],
                    "next_milestone": data["next_milestone"],
                    "is_critical_path": ws in _CRITICAL_PATH,
                })
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", '{"detail":"not found"}')


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10047)
    else:  # pragma: no cover
        server = HTTPServer(("0.0.0.0", 10047), _Handler)
        print("Serving on http://0.0.0.0:10047 (stdlib fallback)")
        server.serve_forever()
