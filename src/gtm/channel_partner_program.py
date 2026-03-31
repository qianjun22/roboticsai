"""Channel partner program — VAR (25% margin) / SI (20%) / ISV (15% rev share) / distributor (30%), enablement kit (2-day training + 40hr cert + demo env), 20% ARR target via channel, 33% cheaper CAC than direct.
FastAPI service — OCI Robot Cloud
Port: 10113"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI
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
        "rev_share_pct": None,
        "requirements": [
            "Minimum $500K annual OCI Robot Cloud commitment",
            "2 certified sales engineers",
            "Active robotics customer base (min 5 accounts)",
            "Quarterly business review participation"
        ],
        "enablement_materials": {
            "training_days": 2,
            "certification_hours": 40,
            "demo_environment": True,
            "co_marketing_mdf_usd": 10000,
            "deal_registration": True,
            "nfr_licenses": 2
        }
    },
    "SI": {
        "full_name": "Systems Integrator",
        "margin_pct": 20,
        "rev_share_pct": None,
        "requirements": [
            "Robotics or industrial automation practice",
            "3 certified solution architects",
            "Reference customer in manufacturing or logistics",
            "Joint go-to-market plan submitted annually"
        ],
        "enablement_materials": {
            "training_days": 2,
            "certification_hours": 40,
            "demo_environment": True,
            "co_marketing_mdf_usd": 15000,
            "deal_registration": True,
            "nfr_licenses": 3
        }
    },
    "ISV": {
        "full_name": "Independent Software Vendor",
        "margin_pct": None,
        "rev_share_pct": 15,
        "requirements": [
            "Robotics or AI software product",
            "OCI Marketplace listing",
            "1 certified integration engineer",
            "Jointly validated integration test suite"
        ],
        "enablement_materials": {
            "training_days": 2,
            "certification_hours": 40,
            "demo_environment": True,
            "co_marketing_mdf_usd": 5000,
            "deal_registration": False,
            "nfr_licenses": 1
        }
    },
    "distributor": {
        "full_name": "Distributor",
        "margin_pct": 30,
        "rev_share_pct": None,
        "requirements": [
            "Regional or national distribution capability",
            "Minimum $2M annual commitment",
            "Dedicated OCI Robot Cloud sales team (min 5 reps)",
            "Sub-reseller recruitment and enablement responsibility"
        ],
        "enablement_materials": {
            "training_days": 2,
            "certification_hours": 40,
            "demo_environment": True,
            "co_marketing_mdf_usd": 50000,
            "deal_registration": True,
            "nfr_licenses": 5
        }
    }
}

PROGRAM_METRICS = {
    "arr_target_via_channel_pct": 20,
    "cac_savings_vs_direct_pct": 33,
    "active_partners_target": 50,
    "regions": ["NA", "EMEA", "APAC", "LATAM"],
    "portal": "https://partners.oci-robot-cloud.oracle.com"
}

def _generate_onboarding_plan(partner_info: dict) -> dict:
    partner_type = partner_info.get("partner_type", "VAR")
    company = partner_info.get("company_name", "Partner Co.")
    region = partner_info.get("region", "NA")
    pdata = PARTNER_TYPES.get(partner_type, PARTNER_TYPES["VAR"])
    return {
        "company": company,
        "partner_type": partner_type,
        "region": region,
        "onboarding_steps": [
            {"step": 1, "action": "Sign partner agreement", "timeline_days": 3},
            {"step": 2, "action": "Portal access provisioned", "timeline_days": 1},
            {"step": 3, "action": f"2-day enablement training ({pdata['enablement_materials']['certification_hours']}hr cert track)", "timeline_days": 5},
            {"step": 4, "action": "Demo environment activated (OCI tenancy)", "timeline_days": 2},
            {"step": 5, "action": "First co-sell opportunity registered", "timeline_days": 30},
            {"step": 6, "action": "QBR scheduled", "timeline_days": 90}
        ],
        "portal_access": {
            "url": PROGRAM_METRICS["portal"],
            "credentials_sent_to": partner_info.get("contact_email", "partner@example.com"),
            "access_level": partner_type
        },
        "assigned_territory": {
            "region": region,
            "named_accounts": random.randint(10, 40),
            "channel_manager": f"channel-mgr-{region.lower()}@oracle.com"
        },
        "estimated_first_deal_days": random.randint(45, 120)
    }

if USE_FASTAPI:
    app = FastAPI(title="Channel Partner Program", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Channel Partner Program</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>Channel Partner Program</h1><p>OCI Robot Cloud · Port {PORT}</p>
<p>VAR 25% · SI 20% · ISV 15% rev share · Distributor 30% · 20% ARR via channel · 33% CAC savings</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/channel/program">Program Details</a></p></body></html>""")

    @app.get("/channel/program")
    def channel_program(partner_type: str = None):
        """Return partner type margins, requirements, and enablement materials."""
        if partner_type:
            pt = partner_type.upper() if partner_type.upper() in PARTNER_TYPES else partner_type.lower()
            if pt not in PARTNER_TYPES:
                return JSONResponse({"error": f"Unknown partner_type '{partner_type}'. Valid: {list(PARTNER_TYPES.keys())}"}, status_code=400)
            return JSONResponse({
                "status": "ok",
                "port": PORT,
                "partner_type": pt,
                **PARTNER_TYPES[pt],
                "program_metrics": PROGRAM_METRICS,
                "ts": datetime.utcnow().isoformat()
            })
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "partner_types": PARTNER_TYPES,
            "program_metrics": PROGRAM_METRICS,
            "ts": datetime.utcnow().isoformat()
        })

    @app.post("/channel/onboard")
    def channel_onboard(body: dict):
        """Partner info → onboarding_plan + portal_access + assigned_territory."""
        if not body.get("company_name"):
            return JSONResponse({"error": "company_name is required"}, status_code=422)
        if not body.get("partner_type"):
            return JSONResponse({"error": "partner_type is required (VAR, SI, ISV, distributor)"}, status_code=422)
        plan = _generate_onboarding_plan(body)
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
            "onboarding_plan": plan
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
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
