"""Product usage analytics v2 — API call patterns (847 inference/day, 12 eval/day, 0.3 fine-tune/day), feature adoption funnel (inference 100% → fine-tune 67% → SDK 45% → data flywheel 23%), usage health signals for churn/expansion triggers.
FastAPI service — OCI Robot Cloud
Port: 10151"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10151

# Simulated usage data
API_PATTERNS_DEFAULTS = {
    "inference_calls_per_day": 847,
    "eval_calls_per_day": 12,
    "finetune_calls_per_day": 0.3,
    "sdk_calls_per_day": 381,
    "data_flywheel_calls_per_day": 195,
}

FEATURE_ADOPTION_FUNNEL = {
    "inference": 1.00,
    "fine_tune": 0.67,
    "sdk": 0.45,
    "data_flywheel": 0.23,
}

HEALTH_THRESHOLDS = {
    "churn_risk_inference_drop_pct": 30,
    "expansion_signal_finetune_growth_pct": 20,
    "healthy_dau_min": 500,
}

def _compute_health_signals(api_patterns: dict, period: str) -> dict:
    inference = api_patterns.get("inference_calls_per_day", 0)
    finetune = api_patterns.get("finetune_calls_per_day", 0)
    signals = []
    if inference < HEALTH_THRESHOLDS["healthy_dau_min"]:
        signals.append({"signal": "churn_risk", "reason": "inference DAU below healthy threshold", "severity": "high"})
    if finetune > 0.5:
        signals.append({"signal": "expansion", "reason": "fine-tune adoption growing", "severity": "opportunity"})
    if not signals:
        signals.append({"signal": "healthy", "reason": "all usage metrics within normal range", "severity": "none"})
    return {"signals": signals, "evaluated_at": datetime.utcnow().isoformat()}

def _billing_preview(api_patterns: dict, period_days: int) -> dict:
    inference_cost = api_patterns.get("inference_calls_per_day", 0) * period_days * 0.002
    finetune_cost = api_patterns.get("finetune_calls_per_day", 0) * period_days * 1.50
    total = round(inference_cost + finetune_cost, 2)
    return {
        "inference_cost_usd": round(inference_cost, 2),
        "finetune_cost_usd": round(finetune_cost, 2),
        "total_estimated_usd": total,
        "period_days": period_days,
    }

if USE_FASTAPI:
    app = FastAPI(title="Product Usage Analytics v2", version="2.0.0")

    @app.get("/usage/v2/analytics")
    def analytics(
        customer_id: str = Query(default="demo-customer"),
        period: str = Query(default="30d"),
    ):
        period_days = int(period.replace("d", "")) if period.endswith("d") else 30
        # Simulate per-customer variation
        seed = sum(ord(c) for c in customer_id)
        rng = random.Random(seed)
        api_patterns = {
            k: round(v * rng.uniform(0.8, 1.2), 2)
            for k, v in API_PATTERNS_DEFAULTS.items()
        }
        health_signals = _compute_health_signals(api_patterns, period)
        billing = _billing_preview(api_patterns, period_days)
        return JSONResponse({
            "customer_id": customer_id,
            "period": period,
            "api_patterns": api_patterns,
            "feature_adoption": FEATURE_ADOPTION_FUNNEL,
            "health_signals": health_signals,
            "billing_preview": billing,
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/usage/v2/fleet")
    def fleet():
        # Aggregate fleet-level metrics across simulated customers
        num_customers = 47
        total_inference = round(API_PATTERNS_DEFAULTS["inference_calls_per_day"] * num_customers * random.uniform(0.95, 1.05))
        growth_trends = {
            "inference_wow_pct": round(random.uniform(2.1, 6.4), 1),
            "finetune_wow_pct": round(random.uniform(8.3, 15.2), 1),
            "sdk_wow_pct": round(random.uniform(3.5, 9.8), 1),
        }
        return JSONResponse({
            "total_customers": num_customers,
            "total_api_calls_per_day": total_inference,
            "feature_adoption_rates": FEATURE_ADOPTION_FUNNEL,
            "growth_trends": growth_trends,
            "churn_risk_customers": random.randint(2, 5),
            "expansion_signal_customers": random.randint(8, 14),
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Product Usage Analytics v2</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Product Usage Analytics v2</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>847 inference/day · 12 eval/day · 0.3 fine-tune/day</p>"
            f"<p>Feature funnel: inference 100% → fine-tune 67% → SDK 45% → data flywheel 23%</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

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
