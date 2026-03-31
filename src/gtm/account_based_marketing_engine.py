"""ABM engine — 50 named accounts in 3 tiers (T1: 5 full personalization / T2: 20 content-personalized / T3: 25 programmatic). T1 accounts → 40% of pipeline, 8× ROI. Scoring by firmographic + technographic + behavior.
FastAPI service — OCI Robot Cloud
Port: 10133"""
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
PORT = 10133
ACCOUNTS = {
    "t1": [f"enterprise_{i:03d}" for i in range(1, 6)],
    "t2": [f"midmarket_{i:03d}" for i in range(1, 21)],
    "t3": [f"smb_{i:03d}" for i in range(1, 26)],
}
ALL_ACCOUNTS = {a: "t1" for a in ACCOUNTS["t1"]}
ALL_ACCOUNTS.update({a: "t2" for a in ACCOUNTS["t2"]})
ALL_ACCOUNTS.update({a: "t3" for a in ACCOUNTS["t3"]})
if USE_FASTAPI:
    app = FastAPI(title="Account Based Marketing Engine", version="1.0.0")
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"ts":datetime.utcnow().isoformat()}
    @app.get("/",response_class=HTMLResponse)
    def index(): return HTMLResponse(f"<html><head><title>Account Based Marketing Engine</title><style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body><h1>Account Based Marketing Engine</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href='/docs'>API Docs</a></p></body></html>")
    @app.get("/abm/account_score")
    def account_score(company_id: str = "enterprise_001"):
        tier = ALL_ACCOUNTS.get(company_id, "t3")
        firmographic = round(random.uniform(60, 95), 1)
        technographic = round(random.uniform(50, 90), 1)
        behavior = round(random.uniform(40, 85), 1)
        score = round((firmographic * 0.35 + technographic * 0.35 + behavior * 0.30), 1)
        tier_actions = {
            "t1": [
                "Assign dedicated SDR + AE pair",
                "Create custom ROI model",
                "Schedule executive briefing",
                "Develop bespoke demo environment",
                "Produce personalized case study",
            ],
            "t2": [
                "Enroll in industry nurture track",
                "Send personalized content bundle",
                "Invite to exclusive webinar",
            ],
            "t3": [
                "Add to programmatic ad audience",
                "Enroll in standard email sequence",
            ],
        }
        personalization_assets = {
            "t1": ["custom_deck", "roi_calculator", "pilot_proposal", "exec_brief"],
            "t2": ["industry_whitepaper", "comparison_guide", "webinar_invite"],
            "t3": ["product_overview", "pricing_sheet"],
        }
        return JSONResponse({
            "company_id": company_id,
            "tier": tier,
            "score": score,
            "score_breakdown": {
                "firmographic": firmographic,
                "technographic": technographic,
                "behavior": behavior,
            },
            "recommended_actions": tier_actions.get(tier, []),
            "personalization_assets": personalization_assets.get(tier, []),
            "scored_at": datetime.utcnow().isoformat(),
        })
    @app.get("/abm/pipeline_contribution")
    def pipeline_contribution(period: str = "Q1-2026"):
        total_pipeline = round(random.uniform(8_000_000, 12_000_000), 0)
        t1_pct = 0.40
        t2_pct = 0.35
        t3_pct = 0.25
        t1_pipeline = round(total_pipeline * t1_pct, 0)
        t2_pipeline = round(total_pipeline * t2_pct, 0)
        t3_pipeline = round(total_pipeline * t3_pct, 0)
        abm_pipeline = round(total_pipeline * 0.72, 0)  # 72% of pipeline from ABM
        tier_roi = {"t1": 8.0, "t2": 4.5, "t3": 2.1}
        return JSONResponse({
            "period": period,
            "total_pipeline_usd": total_pipeline,
            "abm_pipeline_usd": abm_pipeline,
            "abm_pipeline_pct": 72.0,
            "tier_breakdown": {
                "t1": {"accounts": 5, "pipeline_usd": t1_pipeline, "pipeline_pct": round(t1_pct*100,1), "roi": tier_roi["t1"]},
                "t2": {"accounts": 20, "pipeline_usd": t2_pipeline, "pipeline_pct": round(t2_pct*100,1), "roi": tier_roi["t2"]},
                "t3": {"accounts": 25, "pipeline_usd": t3_pipeline, "pipeline_pct": round(t3_pct*100,1), "roi": tier_roi["t3"]},
            },
            "overall_roi": 5.8,
            "retrieved_at": datetime.utcnow().isoformat(),
        })
    if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
            self.wfile.write(json.dumps({"status":"ok","port":PORT}).encode())
        def log_message(self,*a): pass
    if __name__=="__main__": HTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
