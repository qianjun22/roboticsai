"""Customer health score v2 — 6 signals: API usage trend (25%) + SR trend (20%) + support tickets (15%) + QBR attendance (15%) + invoice timeliness (15%) + feature adoption (10%). Machina 91/Verdant 84/Helix 76 (amber). Churn AUC 0.91.
FastAPI service — OCI Robot Cloud
Port: 10127"""
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

PORT = 10127

# Signal weights
SIGNAL_WEIGHTS = {
    "api_usage_trend": 0.25,
    "sr_trend": 0.20,
    "support_tickets": 0.15,
    "qbr_attendance": 0.15,
    "invoice_timeliness": 0.15,
    "feature_adoption": 0.10,
}

# Seeded customer data
CUSTOMER_DATA = {
    "machina": {"score": 91, "risk_level": "green"},
    "verdant": {"score": 84, "risk_level": "green"},
    "helix": {"score": 76, "risk_level": "amber"},
}

def _compute_score(signals: dict) -> float:
    score = 0.0
    for signal, weight in SIGNAL_WEIGHTS.items():
        score += signals.get(signal, random.uniform(60, 95)) * weight
    return round(score, 1)

def _risk_level(score: float) -> str:
    if score >= 85:
        return "green"
    elif score >= 70:
        return "amber"
    else:
        return "red"

def _recommended_actions(risk: str) -> list:
    if risk == "green":
        return ["Schedule upsell conversation", "Invite to beta program"]
    elif risk == "amber":
        return ["Schedule health check call", "Review SR trend", "Offer training session"]
    else:
        return ["Escalate to CSM", "Emergency QBR", "Executive sponsor outreach", "Review contract terms"]

if USE_FASTAPI:
    app = FastAPI(title="Customer Health Score v2", version="2.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"<html><head><title>Customer Health Score v2</title><style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body><h1>Customer Health Score v2</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href='/docs'>API Docs</a></p></body></html>")

    @app.get("/health_score/v2")
    def get_health_score(customer_id: str):
        """Return score + signal_breakdown + risk_level + recommended_actions for a customer."""
        base = CUSTOMER_DATA.get(customer_id.lower(), None)
        signals = {
            "api_usage_trend": round(random.uniform(70, 100), 1),
            "sr_trend": round(random.uniform(65, 100), 1),
            "support_tickets": round(random.uniform(60, 100), 1),
            "qbr_attendance": round(random.uniform(70, 100), 1),
            "invoice_timeliness": round(random.uniform(75, 100), 1),
            "feature_adoption": round(random.uniform(60, 95), 1),
        }
        score = base["score"] if base else _compute_score(signals)
        risk = base["risk_level"] if base else _risk_level(score)
        return JSONResponse({
            "customer_id": customer_id,
            "score": score,
            "signal_breakdown": {
                k: {"raw": signals[k], "weight": v, "contribution": round(signals[k] * v, 2)}
                for k, v in SIGNAL_WEIGHTS.items()
            },
            "risk_level": risk,
            "recommended_actions": _recommended_actions(risk),
            "churn_auc": 0.91,
            "model_version": "v2",
            "ts": datetime.utcnow().isoformat()
        })

    @app.get("/health_score/v2/portfolio")
    def get_portfolio():
        """Return all_customers health_distribution + at_risk_count + avg_score."""
        customers = [
            {"customer_id": "machina", "score": 91, "risk_level": "green"},
            {"customer_id": "verdant", "score": 84, "risk_level": "green"},
            {"customer_id": "helix", "score": 76, "risk_level": "amber"},
        ]
        scores = [c["score"] for c in customers]
        avg_score = round(sum(scores) / len(scores), 1)
        at_risk = [c for c in customers if c["risk_level"] in ("amber", "red")]
        health_distribution = {
            "green": sum(1 for c in customers if c["risk_level"] == "green"),
            "amber": sum(1 for c in customers if c["risk_level"] == "amber"),
            "red": sum(1 for c in customers if c["risk_level"] == "red"),
        }
        return {
            "all_customers": customers,
            "health_distribution": health_distribution,
            "at_risk_count": len(at_risk),
            "at_risk_customers": [c["customer_id"] for c in at_risk],
            "avg_score": avg_score,
            "churn_auc": 0.91,
            "model_version": "v2",
            "ts": datetime.utcnow().isoformat()
        }

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
