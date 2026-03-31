"""Expansion revenue tracker — Machina 2nd robot $41K (60% confidence) / Verdant use case 2 $28K (45%) / Helix volume $15K (70%). Expansion triggers (usage>80% / new use case inquiry / 3 successful months).
FastAPI service — OCI Robot Cloud
Port: 10125"""
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
PORT = 10125
_PIPELINE = [
    {"customer": "Machina", "opportunity": "2nd robot deployment", "arr_usd": 41000, "confidence": 0.60, "trigger": "usage>80%"},
    {"customer": "Verdant", "opportunity": "use case 2 expansion", "arr_usd": 28000, "confidence": 0.45, "trigger": "new_use_case_inquiry"},
    {"customer": "Helix", "opportunity": "volume scale-up", "arr_usd": 15000, "confidence": 0.70, "trigger": "3_successful_months"},
]
_TRIGGERS = {
    "usage>80%": "Customer utilization exceeded 80% — recommend expansion conversation",
    "new_use_case_inquiry": "Customer submitted new use case inquiry — schedule scoping call",
    "3_successful_months": "3 consecutive successful deployment months — propose volume discount",
}
if USE_FASTAPI:
    app = FastAPI(title="Expansion Revenue Tracker", version="1.0.0")
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"ts":datetime.utcnow().isoformat()}
    @app.get("/",response_class=HTMLResponse)
    def index(): return HTMLResponse(f"<html><head><title>Expansion Revenue Tracker</title><style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body><h1>Expansion Revenue Tracker</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href='/docs'>API Docs</a></p></body></html>")
    @app.get("/expansion/pipeline")
    def expansion_pipeline(period: str = "Q2-2026"):
        """Return expansion opportunities with confidence scores and total pipeline value."""
        opportunities = []
        for opp in _PIPELINE:
            opportunities.append({
                "customer": opp["customer"],
                "opportunity": opp["opportunity"],
                "arr_usd": opp["arr_usd"],
                "confidence": opp["confidence"],
                "weighted_arr_usd": round(opp["arr_usd"] * opp["confidence"]),
                "trigger": opp["trigger"],
                "stage": random.choice(["identified", "qualifying", "proposing"]),
                "next_step": _TRIGGERS.get(opp["trigger"], "Follow up with customer")
            })
        total_value = sum(o["arr_usd"] for o in _PIPELINE)
        total_weighted = sum(o["weighted_arr_usd"] for o in opportunities)
        return JSONResponse({
            "period": period,
            "opportunities": opportunities,
            "confidence_scores": {o["customer"]: o["confidence"] for o in opportunities},
            "total_value_usd": total_value,
            "total_weighted_value_usd": total_weighted,
            "opportunity_count": len(opportunities),
            "ts": datetime.utcnow().isoformat()
        })
    @app.get("/expansion/triggers")
    def expansion_triggers(customer_id: str = ""):
        """Return active expansion triggers and recommended actions for a customer."""
        matches = [o for o in _PIPELINE if o["customer"].lower() == customer_id.lower()]
        if not matches:
            matches = _PIPELINE
        active_triggers = []
        for opp in matches:
            trigger_key = opp["trigger"]
            active_triggers.append({
                "trigger": trigger_key,
                "description": _TRIGGERS.get(trigger_key, "Expansion signal detected"),
                "fired": True,
                "opportunity_arr_usd": opp["arr_usd"],
                "confidence": opp["confidence"]
            })
        projected_arr = sum(o["arr_usd"] * o["confidence"] for o in matches)
        recommended_actions = list({_TRIGGERS[o["trigger"]] for o in matches if o["trigger"] in _TRIGGERS})
        return JSONResponse({
            "customer_id": customer_id or "(all)",
            "active_triggers": active_triggers,
            "recommended_actions": recommended_actions,
            "projected_arr_usd": round(projected_arr),
            "expansion_ready": len(active_triggers) > 0,
            "ts": datetime.utcnow().isoformat()
        })
    if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
            self.wfile.write(json.dumps({"status":"ok","port":PORT}).encode())
        def log_message(self,*a): pass
    if __name__=="__main__": HTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
