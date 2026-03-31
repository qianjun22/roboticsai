"""Automated renewal management — T-90 kickoff through T-0 close, health score predictor (>80 auto-renew / 60-80 intervention / <60 exec call), 100% renewal rate to date, expansion opportunity at each renewal. Endpoints: GET /renewals/pipeline (period → upcoming_renewals + health_scores + expansion_opportunities + actions), POST /renewals/kickoff (customer_id → renewal_plan + qbr_scheduled + expansion_proposal), GET /health.
FastAPI service — OCI Robot Cloud
Port: 10121"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler
PORT = 10121
if USE_FASTAPI:
    app = FastAPI(title="Enterprise Renewal Automation", version="1.0.0")

    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"ts":datetime.utcnow().isoformat()}

    @app.get("/",response_class=HTMLResponse)
    def index(): return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Enterprise Renewal Automation</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>Enterprise Renewal Automation</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p></body></html>""")

    def _health_score(customer_id: str) -> float:
        """Deterministic health score based on customer_id hash."""
        seed = sum(ord(c) for c in customer_id)
        random.seed(seed)
        return round(random.uniform(55, 98), 1)

    def _renewal_action(score: float) -> dict:
        if score > 80:
            return {"tier": "auto-renew", "action": "Send renewal notice T-30", "owner": "CSM"}
        elif score >= 60:
            return {"tier": "intervention", "action": "Schedule QBR + exec sponsor call", "owner": "AE + CSM"}
        else:
            return {"tier": "exec-call", "action": "VP-level rescue call + custom expansion offer", "owner": "VP Sales"}

    @app.get("/renewals/pipeline")
    def pipeline(period: str = "Q2-2026"):
        """List upcoming renewals with health scores, expansion opportunities, and recommended actions."""
        customers = [
            {"id": "cust-001", "name": "Acme Robotics", "arr": 480000, "days_to_renewal": 87},
            {"id": "cust-002", "name": "Stellar Automation", "arr": 320000, "days_to_renewal": 62},
            {"id": "cust-003", "name": "NovaBots Inc", "arr": 750000, "days_to_renewal": 45},
            {"id": "cust-004", "name": "Orion Dynamics", "arr": 195000, "days_to_renewal": 31},
            {"id": "cust-005", "name": "Zenith Mechatronics", "arr": 620000, "days_to_renewal": 14},
        ]
        upcoming_renewals = []
        for c in customers:
            score = _health_score(c["id"])
            action = _renewal_action(score)
            expansion_upsell = round(c["arr"] * random.uniform(0.15, 0.35), -3)
            upcoming_renewals.append({
                **c,
                "health_score": score,
                "action": action,
                "expansion_opportunity_usd": expansion_upsell,
                "renewal_stage": f"T-{c['days_to_renewal']}",
            })
        total_arr = sum(c["arr"] for c in customers)
        total_expansion = sum(r["expansion_opportunity_usd"] for r in upcoming_renewals)
        return JSONResponse({
            "period": period,
            "upcoming_renewals": upcoming_renewals,
            "summary": {
                "total_customers": len(customers),
                "total_arr_at_risk": total_arr,
                "total_expansion_opportunity": total_expansion,
                "renewal_rate_to_date": "100%",
                "auto_renew_count": sum(1 for r in upcoming_renewals if r["action"]["tier"] == "auto-renew"),
                "intervention_count": sum(1 for r in upcoming_renewals if r["action"]["tier"] == "intervention"),
                "exec_call_count": sum(1 for r in upcoming_renewals if r["action"]["tier"] == "exec-call"),
            },
        })

    @app.post("/renewals/kickoff")
    def kickoff(customer_id: str):
        """Kick off renewal motion for a customer — returns renewal plan, QBR schedule, and expansion proposal."""
        score = _health_score(customer_id)
        action = _renewal_action(score)
        qbr_date = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
        renewal_plan = {
            "customer_id": customer_id,
            "health_score": score,
            "tier": action["tier"],
            "kickoff_stage": "T-90",
            "milestones": [
                {"stage": "T-90", "task": "Internal renewal review + health assessment"},
                {"stage": "T-60", "task": "Customer success review + expansion scoping"},
                {"stage": "T-30", "task": "Formal renewal quote + legal review"},
                {"stage": "T-14", "task": "Executive alignment + final negotiation"},
                {"stage": "T-0", "task": "Contract signed + close"},
            ],
        }
        expansion_proposal = {
            "modules": ["Multi-Robot Fleet Management", "Isaac Sim Premium", "Global Failover Add-on"],
            "estimated_expansion_arr": round(random.uniform(80000, 250000), -3),
            "proposal_ready_by": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        return JSONResponse({
            "renewal_plan": renewal_plan,
            "qbr_scheduled": qbr_date,
            "expansion_proposal": expansion_proposal,
            "owner_action": action["action"],
            "owner": action["owner"],
        })

    if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
            self.wfile.write(json.dumps({"status":"ok","port":PORT}).encode())
        def log_message(self,*a): pass
    if __name__=="__main__": HTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
