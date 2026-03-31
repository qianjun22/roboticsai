"""GTM Playbook v3 — port 10051.

Updated Go-To-Market playbook for post-pilot / AI World launch stage.
Tracks 3 motions (PLG + direct + channel) with NVIDIA referral as
highest-quality channel (81% win rate, $89K ACV, 52-day sales cycle).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10051
SERVICE_NAME = "gtm_playbook_v3"

CHANNEL_DATA = {
    "direct": {
        "mix_pct": 45,
        "win_rate": 73,
        "acv_k": 83,
        "days": 67,
        "motion": "Enterprise direct sales",
    },
    "nvidia_referral": {
        "mix_pct": 35,
        "win_rate": 81,
        "acv_k": 89,
        "days": 52,
        "motion": "NVIDIA partner co-sell",
    },
    "channel_partner": {
        "mix_pct": 20,
        "win_rate": 65,
        "acv_k": 71,
        "days": 81,
        "motion": "VAR / SI distribution",
    },
}

SEGMENT_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "enterprise": {
        "icp": {
            "company_size": "500-5000 employees",
            "verticals": ["automotive", "electronics", "logistics"],
            "trigger": "expanding robot fleet >10 units",
            "budget_range": "$75K-$150K ACV",
        },
        "sales_motion": "Executive-led, multi-stakeholder consensus (6-10 weeks)",
        "channel_mix": {"direct": "50%", "nvidia_referral": "40%", "channel_partner": "10%"},
        "metrics": {"avg_acv": "$112K", "win_rate": "78%", "sales_cycle_days": 58},
        "playbook_steps": [
            "1. CXO intro via NVIDIA field rep or OCI account team",
            "2. 30-min tech demo with GR00T N1.6 live inference",
            "3. Pilot proposal: 3-robot, 60-day, $0 (OCI credits)",
            "4. Pilot success review with ROI dashboard",
            "5. Production contract: 1-year, OCI Marketplace listing",
            "6. Expansion: multi-site, premium SLA, training services",
        ],
    },
    "mid_market": {
        "icp": {
            "company_size": "50-500 employees",
            "verticals": ["food & beverage", "pharma", "general manufacturing"],
            "trigger": "first robot deployment or replacing legacy automation",
            "budget_range": "$30K-$80K ACV",
        },
        "sales_motion": "PLG-led: self-serve trial → SDR follow-up → AE close (3-5 weeks)",
        "channel_mix": {"direct": "35%", "nvidia_referral": "25%", "channel_partner": "40%"},
        "metrics": {"avg_acv": "$52K", "win_rate": "68%", "sales_cycle_days": 34},
        "playbook_steps": [
            "1. Inbound via AI World demo or NVIDIA GTC session",
            "2. Self-serve signup → OCI free tier trial (14-day)",
            "3. SDR activation email at day 3 if no API call",
            "4. 45-min AE call: use-case fit + pricing walk",
            "5. Proof-of-concept on customer hardware (2 weeks)",
            "6. Close on annual subscription via OCI Marketplace",
        ],
    },
    "startup": {
        "icp": {
            "company_size": "<50 employees",
            "verticals": ["robotics startups", "university spinouts", "stealth AI"],
            "trigger": "seed/Series A, building first embodied AI product",
            "budget_range": "$10K-$30K ACV",
        },
        "sales_motion": "PLG: free credits → community → design partner program",
        "channel_mix": {"direct": "20%", "nvidia_referral": "50%", "channel_partner": "30%"},
        "metrics": {"avg_acv": "$18K", "win_rate": "55%", "sales_cycle_days": 21},
        "playbook_steps": [
            "1. GitHub/HuggingFace discovery → OCI Robotics SDK install",
            "2. Free $500 OCI credit offer via NVIDIA Inception",
            "3. Join design partner program (bi-weekly product calls)",
            "4. Co-develop fine-tuning pipeline on OCI GPUs",
            "5. Publish joint case study / paper",
            "6. Convert to paid on Series A close",
        ],
    },
}

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GTM Playbook v3 &mdash; OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; min-height: 100vh; }
    header {
      background: linear-gradient(135deg, #C74634 0%, #a83828 100%);
      padding: 24px 32px;
      display: flex; align-items: center; justify-content: space-between;
    }
    header h1 { font-size: 1.6rem; font-weight: 700; color: #fff; }
    header .sub { color: #fde68a; font-size: 0.85rem; margin-top: 4px; }
    header .badge {
      background: rgba(255,255,255,0.18); color: #fff;
      border-radius: 999px; padding: 4px 14px; font-size: 0.8rem;
    }
    .main { padding: 32px; max-width: 1100px; margin: 0 auto; }
    .kpi-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 28px; }
    .kpi {
      background: #1e293b; border-radius: 12px; padding: 20px 24px;
      border-left: 4px solid #38bdf8;
    }
    .kpi .label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .kpi .sub { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
    .kpi.red { border-left-color: #C74634; }
    .kpi.red .value { color: #C74634; }
    .kpi.gold { border-left-color: #fde68a; }
    .kpi.gold .value { color: #fde68a; }
    .kpi.green { border-left-color: #22c55e; }
    .kpi.green .value { color: #22c55e; }
    .section { background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .section h2 { font-size: 1.1rem; font-weight: 600; color: #38bdf8; margin-bottom: 18px; }
    .channel-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; }
    .ch-card {
      background: #0f172a; border-radius: 10px; padding: 18px 20px;
      border: 1px solid #334155;
    }
    .ch-card.best { border-color: #38bdf8; }
    .ch-card .ch-name { font-weight: 700; font-size: 1rem; margin-bottom: 10px; color: #e2e8f0; }
    .ch-card.best .ch-name { color: #38bdf8; }
    .ch-stat { display: flex; justify-content: space-between; font-size: 0.84rem; padding: 4px 0; border-bottom: 1px solid #1e293b; }
    .ch-stat .k { color: #94a3b8; }
    .ch-stat .v { font-weight: 600; color: #e2e8f0; }
    .ch-stat .v.good { color: #22c55e; }
    .ch-badge {
      display: inline-block; margin-top: 10px;
      background: #38bdf8; color: #0f172a;
      border-radius: 999px; padding: 3px 12px; font-size: 0.75rem; font-weight: 700;
    }
    .motion-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; }
    .motion-card {
      background: #0f172a; border-radius: 10px; padding: 16px 20px;
      border-left: 3px solid #C74634;
    }
    .motion-card .m-title { font-weight: 700; color: #fde68a; margin-bottom: 6px; }
    .motion-card .m-desc { font-size: 0.84rem; color: #94a3b8; line-height: 1.5; }
    svg text { font-family: 'Segoe UI', sans-serif; }
    footer { text-align: center; color: #334155; font-size: 0.75rem; padding: 24px; }
  </style>
</head>
<body>
<header>
  <div>
    <h1>GTM Playbook v3 &mdash; OCI Robot Cloud</h1>
    <p class="sub">Post-pilot &bull; AI World Launch Stage &bull; 3-motion GTM</p>
  </div>
  <span class="badge">port 10051</span>
</header>
<div class="main">
  <div class="kpi-row">
    <div class="kpi gold">
      <div class="label">Best Channel</div>
      <div class="value">NVIDIA</div>
      <div class="sub">81% win rate, $89K ACV</div>
    </div>
    <div class="kpi green">
      <div class="label">Highest ACV</div>
      <div class="value">$89K</div>
      <div class="sub">NVIDIA referral channel</div>
    </div>
    <div class="kpi">
      <div class="label">Fastest Close</div>
      <div class="value">52d</div>
      <div class="sub">NVIDIA referral</div>
    </div>
    <div class="kpi red">
      <div class="label">GTM Motions</div>
      <div class="value">3</div>
      <div class="sub">PLG + Direct + Channel</div>
    </div>
  </div>

  <div class="section">
    <h2>Channel Performance &mdash; Win Rate by Channel (SVG)</h2>
    <svg viewBox="0 0 680 220" width="100%" height="220">
      <!-- y-axis -->
      <line x1="80" y1="10" x2="80" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="170" x2="660" y2="170" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="72" y="174" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <text x="72" y="130" fill="#64748b" font-size="11" text-anchor="end">25%</text>
      <text x="72" y="90" fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="72" y="50" fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="72" y="13" fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <!-- grid -->
      <line x1="80" y1="126" x2="660" y2="126" stroke="#1e293b" stroke-dasharray="4,4" stroke-width="1"/>
      <line x1="80" y1="90" x2="660" y2="90" stroke="#1e293b" stroke-dasharray="4,4" stroke-width="1"/>
      <line x1="80" y1="50" x2="660" y2="50" stroke="#1e293b" stroke-dasharray="4,4" stroke-width="1"/>
      <!-- Win rate bars: scale 160px = 100% -->
      <!-- Direct 73% = 116.8px -->
      <rect x="130" y="53.2" width="100" height="116.8" fill="#38bdf8" rx="4"/>
      <text x="180" y="46" fill="#38bdf8" font-size="13" font-weight="700" text-anchor="middle">73%</text>
      <!-- NVIDIA 81% = 129.6px -->
      <rect x="290" y="40.4" width="100" height="129.6" fill="#22c55e" rx="4"/>
      <text x="340" y="33" fill="#22c55e" font-size="13" font-weight="700" text-anchor="middle">81% ★</text>
      <!-- Channel partner 65% = 104px -->
      <rect x="450" y="66" width="100" height="104" fill="#C74634" rx="4"/>
      <text x="500" y="59" fill="#C74634" font-size="13" font-weight="700" text-anchor="middle">65%</text>
      <!-- x labels -->
      <text x="180" y="190" fill="#94a3b8" font-size="12" text-anchor="middle">Direct (45%)</text>
      <text x="340" y="190" fill="#94a3b8" font-size="12" text-anchor="middle">NVIDIA Referral (35%)</text>
      <text x="500" y="190" fill="#94a3b8" font-size="12" text-anchor="middle">Channel Partner (20%)</text>
      <!-- ACV labels -->
      <text x="180" y="208" fill="#64748b" font-size="11" text-anchor="middle">$83K ACV &bull; 67d</text>
      <text x="340" y="208" fill="#64748b" font-size="11" text-anchor="middle">$89K ACV &bull; 52d</text>
      <text x="500" y="208" fill="#64748b" font-size="11" text-anchor="middle">$71K ACV &bull; 81d</text>
    </svg>
  </div>

  <div class="section">
    <h2>Channel Detail Cards</h2>
    <div class="channel-grid">
      <div class="ch-card">
        <div class="ch-name">Direct Sales</div>
        <div class="ch-stat"><span class="k">Mix</span><span class="v">45%</span></div>
        <div class="ch-stat"><span class="k">Win Rate</span><span class="v">73%</span></div>
        <div class="ch-stat"><span class="k">ACV</span><span class="v">$83K</span></div>
        <div class="ch-stat"><span class="k">Sales Cycle</span><span class="v">67 days</span></div>
        <div class="ch-stat"><span class="k">Motion</span><span class="v" style="font-size:0.78rem">Enterprise direct</span></div>
      </div>
      <div class="ch-card best">
        <div class="ch-name">NVIDIA Referral</div>
        <div class="ch-stat"><span class="k">Mix</span><span class="v">35%</span></div>
        <div class="ch-stat"><span class="k">Win Rate</span><span class="v good">81%</span></div>
        <div class="ch-stat"><span class="k">ACV</span><span class="v good">$89K</span></div>
        <div class="ch-stat"><span class="k">Sales Cycle</span><span class="v good">52 days</span></div>
        <div class="ch-stat"><span class="k">Motion</span><span class="v" style="font-size:0.78rem">NVIDIA co-sell</span></div>
        <span class="ch-badge">Highest Quality</span>
      </div>
      <div class="ch-card">
        <div class="ch-name">Channel Partner</div>
        <div class="ch-stat"><span class="k">Mix</span><span class="v">20%</span></div>
        <div class="ch-stat"><span class="k">Win Rate</span><span class="v">65%</span></div>
        <div class="ch-stat"><span class="k">ACV</span><span class="v">$71K</span></div>
        <div class="ch-stat"><span class="k">Sales Cycle</span><span class="v">81 days</span></div>
        <div class="ch-stat"><span class="k">Motion</span><span class="v" style="font-size:0.78rem">VAR / SI</span></div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>3-Motion GTM Strategy</h2>
    <div class="motion-row">
      <div class="motion-card">
        <div class="m-title">PLG &mdash; Product-Led Growth</div>
        <div class="m-desc">Free OCI credits via NVIDIA Inception &bull; Self-serve trial &bull; SDK on GitHub/HuggingFace &bull; Targets startups &amp; researchers</div>
      </div>
      <div class="motion-card">
        <div class="m-title">Direct &mdash; Enterprise AE</div>
        <div class="m-desc">OCI account team + CXO intros &bull; Pilot-to-production playbook &bull; Targets 500-5000 employee manufacturers</div>
      </div>
      <div class="motion-card">
        <div class="m-title">Channel &mdash; NVIDIA Co-Sell</div>
        <div class="m-desc">NVIDIA field referrals &bull; Inception program &bull; 81% win rate, fastest close at 52d &bull; Highest-quality deal flow</div>
      </div>
    </div>
  </div>
</div>
<footer>OCI Robot Cloud &mdash; GTM Playbook v3 &bull; port 10051 &bull; Oracle Confidential</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="GTM Playbook v3",
        description="Updated GTM playbook for post-pilot, AI World launch stage.",
        version="3.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "service": SERVICE_NAME,
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/gtm/playbook_v3")
    async def playbook_v3(segment: str = "enterprise") -> JSONResponse:
        key = segment.lower().replace("-", "_")
        if key not in SEGMENT_PLAYBOOKS:
            return JSONResponse(
                {"error": f"Unknown segment '{segment}'. Valid: {list(SEGMENT_PLAYBOOKS.keys())}"},
                status_code=404,
            )
        data = SEGMENT_PLAYBOOKS[key]
        return JSONResponse({"segment": key, **data})

    @app.get("/gtm/channel_performance")
    async def channel_performance() -> JSONResponse:
        return JSONResponse({
            "channels": {
                name: {
                    "mix_pct": d["mix_pct"],
                    "win_rate_pct": d["win_rate"],
                    "acv_k": d["acv_k"],
                    "sales_cycle_days": d["days"],
                    "motion": d["motion"],
                }
                for name, d in CHANNEL_DATA.items()
            },
            "best_channel": "nvidia_referral",
            "best_win_rate": 81,
            "best_acv_k": 89,
            "fastest_close_days": 52,
        })


# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------
if not _FASTAPI:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            pass

        def _send(self, code: int, body: str, ctype: str) -> None:
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, DASHBOARD_HTML, "text/html; charset=utf-8")
            elif path == "/health":
                self._send(200, json.dumps({"status": "healthy", "service": SERVICE_NAME, "port": PORT}), "application/json")
            elif path == "/gtm/channel_performance":
                payload = {
                    "channels": {
                        name: {
                            "mix_pct": d["mix_pct"],
                            "win_rate_pct": d["win_rate"],
                            "acv_k": d["acv_k"],
                            "sales_cycle_days": d["days"],
                            "motion": d["motion"],
                        }
                        for name, d in CHANNEL_DATA.items()
                    },
                    "best_channel": "nvidia_referral",
                }
                self._send(200, json.dumps(payload), "application/json")
            elif path == "/gtm/playbook_v3":
                self._send(200, json.dumps(SEGMENT_PLAYBOOKS.get("enterprise", {})), "application/json")
            else:
                self._send(404, json.dumps({"detail": "not found"}), "application/json")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
