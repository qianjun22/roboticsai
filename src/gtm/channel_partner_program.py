"""
Structured channel partner program — VAR (25% margin) / SI (20%) / ISV (15% rev share) /
distributor (30%), partner enablement kit, performance tracking,
channel economics (22% blended margin, $8K CAC).
FastAPI service — OCI Robot Cloud
Port: 10113
"""
from __future__ import annotations
import json, random, time
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI, Body
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10113

PARTNER_TYPES = {
    "VAR": {
        "full_name": "Value-Added Reseller",
        "margin_pct": 25,
        "revenue_share_pct": None,
        "annual_quota_usd": 500_000,
        "requirements": [
            "2+ certified robotics engineers",
            "Active customer base (min 5 accounts)",
            "$1M+ annual revenue",
            "OCI certification (Level 2)"
        ],
        "enablement_materials": [
            "OCI Robot Cloud Sales Deck",
            "ROI Calculator Tool",
            "Demo Environment Access (90 days)",
            "Technical Integration Guide",
            "Customer Case Studies (3)",
            "Co-branded Marketing Assets"
        ],
        "deal_registration": True,
        "mdf_eligible": True,
        "mdf_pct": 3,
        "support_tier": "Silver"
    },
    "SI": {
        "full_name": "Systems Integrator",
        "margin_pct": 20,
        "revenue_share_pct": None,
        "annual_quota_usd": 1_000_000,
        "requirements": [
            "5+ certified robotics engineers",
            "OCI Architecture certification",
            "Reference architecture delivery capability",
            "$5M+ annual services revenue",
            "3 completed robotics deployments"
        ],
        "enablement_materials": [
            "OCI Robot Cloud Architecture Blueprints",
            "Integration Playbooks (Manufacturing, Logistics, Healthcare)",
            "Professional Services Rate Card",
            "SOW Templates",
            "Training Lab Access (180 days)",
            "Pre-sales Engineering Support"
        ],
        "deal_registration": True,
        "mdf_eligible": True,
        "mdf_pct": 5,
        "support_tier": "Gold"
    },
    "ISV": {
        "full_name": "Independent Software Vendor",
        "margin_pct": None,
        "revenue_share_pct": 15,
        "annual_quota_usd": None,
        "requirements": [
            "Software product certified on OCI Robot Cloud",
            "API integration completed",
            "Listed in OCI Marketplace",
            "Joint go-to-market plan signed"
        ],
        "enablement_materials": [
            "OCI Robot Cloud API SDK",
            "Marketplace Listing Guide",
            "Co-sell Playbook",
            "Developer Sandbox (unlimited)",
            "ISV Technical Workshop (quarterly)"
        ],
        "deal_registration": False,
        "mdf_eligible": False,
        "mdf_pct": 0,
        "support_tier": "Developer"
    },
    "Distributor": {
        "full_name": "Authorized Distributor",
        "margin_pct": 30,
        "revenue_share_pct": None,
        "annual_quota_usd": 5_000_000,
        "requirements": [
            "Regional or national coverage",
            "Established robotics channel network (50+ resellers)",
            "$20M+ annual revenue",
            "Dedicated OCI Robot Cloud business unit",
            "Credit line approval"
        ],
        "enablement_materials": [
            "Full Partner Portal Access",
            "White-label Option (select SKUs)",
            "Channel Manager Assignment",
            "Quarterly Business Reviews",
            "Channel Marketing Fund (shared)",
            "Priority Deal Registration",
            "Tier-2 Support Authority"
        ],
        "deal_registration": True,
        "mdf_eligible": True,
        "mdf_pct": 8,
        "support_tier": "Platinum"
    }
}

CHANNEL_ECONOMICS = {
    "blended_margin_pct": 22,
    "customer_acquisition_cost_usd": 8_000,
    "avg_deal_size_usd": 120_000,
    "avg_sales_cycle_days": 90,
    "partner_sourced_revenue_pct": 45,
    "partner_influenced_revenue_pct": 68,
    "channel_ltv_multiplier": 3.2,
    "churn_rate_pct": 8,
    "nps_channel": 62
}

TERRITORIES = [
    "NA-West", "NA-East", "NA-Central",
    "EMEA-West", "EMEA-East",
    "APAC-North", "APAC-South",
    "LATAM"
]


def _generate_onboarding_plan(partner_info: dict, partner_type: str) -> dict:
    """Generate a structured onboarding plan for a new channel partner."""
    ptype = PARTNER_TYPES.get(partner_type, PARTNER_TYPES["VAR"])
    today = datetime.utcnow()

    milestones = [
        {"week": 1, "milestone": "Partner agreement signed + portal access provisioned"},
        {"week": 2, "milestone": "OCI certification kickoff + sales enablement workshop"},
        {"week": 4, "milestone": "Demo environment live + first opportunity registered"},
        {"week": 8, "milestone": "First co-sell engagement with Oracle field team"},
        {"week": 12, "milestone": "Quarterly business review + pipeline target set"}
    ]

    return {
        "partner_name": partner_info.get("name", "Unknown Partner"),
        "partner_type": partner_type,
        "assigned_territory": partner_info.get("territory", random.choice(TERRITORIES)),
        "assigned_channel_manager": f"CM-{random.randint(100, 199)}",
        "portal_access": {
            "url": "https://partner.oracle.com/oci-robot-cloud",
            "credentials_sent_to": partner_info.get("email", "partner@example.com"),
            "access_level": ptype["support_tier"]
        },
        "onboarding_milestones": milestones,
        "expected_first_deal_date": (today + timedelta(days=90)).strftime("%Y-%m-%d"),
        "annual_quota_usd": ptype["annual_quota_usd"],
        "margin_pct": ptype["margin_pct"],
        "revenue_share_pct": ptype["revenue_share_pct"],
        "mdf_budget_usd": int((ptype["annual_quota_usd"] or 0) * ptype["mdf_pct"] / 100),
        "enablement_materials": ptype["enablement_materials"],
        "onboarding_started": today.isoformat()
    }


if USE_FASTAPI:
    app = FastAPI(
        title="Channel Partner Program",
        version="1.0.0",
        description="OCI Robot Cloud structured channel partner program — VAR/SI/ISV/Distributor"
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        rows = "".join(
            f"<tr><td>{k}</td><td>{v['full_name']}</td>"
            f"<td>{v['margin_pct']}%</td>"
            f"<td>${v['annual_quota_usd']:,}</td>"
            f"<td>{v['support_tier']}</td></tr>"
            for k, v in PARTNER_TYPES.items()
            if v['annual_quota_usd']
        )
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Channel Partner Program</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}
h1{{color:#C74634}}a{{color:#38bdf8}}
table{{border-collapse:collapse;margin-top:1rem;width:100%}}td,th{{border:1px solid #334155;padding:0.5rem 1rem;text-align:left}}
th{{background:#1e293b}}.metric{{display:inline-block;margin:0.5rem 1rem;padding:1rem;background:#1e293b;border-radius:8px}}
.metric .val{{font-size:2rem;color:#C74634;font-weight:bold}}</style></head><body>
<h1>Channel Partner Program</h1>
<p>OCI Robot Cloud · Port {PORT}</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/channel/program?partner_type=VAR">Program (VAR)</a></p>
<h2>Channel Economics</h2>
<div class="metric"><div class="val">{CHANNEL_ECONOMICS['blended_margin_pct']}%</div><div>Blended Margin</div></div>
<div class="metric"><div class="val">${CHANNEL_ECONOMICS['customer_acquisition_cost_usd']:,}</div><div>CAC</div></div>
<div class="metric"><div class="val">${CHANNEL_ECONOMICS['avg_deal_size_usd']:,}</div><div>Avg Deal Size</div></div>
<div class="metric"><div class="val">{CHANNEL_ECONOMICS['partner_sourced_revenue_pct']}%</div><div>Partner-Sourced Revenue</div></div>
<h2>Partner Tiers</h2>
<table><tr><th>Type</th><th>Name</th><th>Margin</th><th>Annual Quota</th><th>Support Tier</th></tr>
{rows}
<tr><td>ISV</td><td>Independent Software Vendor</td><td>15% rev share</td><td>N/A</td><td>Developer</td></tr>
</table></body></html>""")

    @app.get("/channel/program")
    def channel_program(partner_type: str = "VAR"):
        """partner_type → margins + requirements + enablement_materials."""
        if partner_type not in PARTNER_TYPES:
            return JSONResponse(
                {"error": f"Unknown partner_type '{partner_type}'. Valid: {list(PARTNER_TYPES.keys())}"},
                status_code=400
            )
        ptype = PARTNER_TYPES[partner_type]
        return JSONResponse({
            "partner_type": partner_type,
            "full_name": ptype["full_name"],
            "economics": {
                "margin_pct": ptype["margin_pct"],
                "revenue_share_pct": ptype["revenue_share_pct"],
                "annual_quota_usd": ptype["annual_quota_usd"],
                "mdf_eligible": ptype["mdf_eligible"],
                "mdf_pct": ptype["mdf_pct"],
                "deal_registration": ptype["deal_registration"]
            },
            "requirements": ptype["requirements"],
            "enablement_materials": ptype["enablement_materials"],
            "support_tier": ptype["support_tier"],
            "channel_economics_overview": CHANNEL_ECONOMICS,
            "available_territories": TERRITORIES
        })

    @app.post("/channel/onboard")
    def channel_onboard(payload: dict = Body(default={})):
        """partner_info → onboarding_plan + portal_access + assigned_territory."""
        partner_info = payload.get("partner_info", {})
        partner_type = payload.get("partner_type", "VAR")

        if partner_type not in PARTNER_TYPES:
            return JSONResponse(
                {"error": f"Unknown partner_type '{partner_type}'. Valid: {list(PARTNER_TYPES.keys())}"},
                status_code=400
            )

        plan = _generate_onboarding_plan(partner_info, partner_type)
        return JSONResponse({
            "status": "onboarding_initiated",
            "onboarding_plan": plan,
            "ts": datetime.utcnow().isoformat()
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
