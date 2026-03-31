"""Gross margin optimizer — 89.4%→92% target. COGS: GPU $1,847 + storage $234 + network $89 + misc $43 = $2,213/mo. Levers: spot instances −$1,478 / reserved inference −$370 / storage opt −$70.
FastAPI service — OCI Robot Cloud
Port: 10135"""
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

PORT = 10135

# COGS breakdown (monthly, USD)
COGS_BREAKDOWN = {
    "gpu": 1847.0,
    "storage": 234.0,
    "network": 89.0,
    "misc": 43.0,
}
TOTAL_COGS = sum(COGS_BREAKDOWN.values())  # $2,213/mo

# Optimization levers
OPTIMIZATION_LEVERS = {
    "spot_instances": {"savings": 1478.0, "description": "Switch GPU workloads to OCI spot instances", "risk": "medium"},
    "reserved_inference": {"savings": 370.0, "description": "Reserved capacity for inference endpoints", "risk": "low"},
    "storage_optimization": {"savings": 70.0, "description": "Compress + deduplicate training data", "risk": "low"},
}

CURRENT_GM_PCT = 89.4
TARGET_GM_PCT = 92.0

if USE_FASTAPI:
    app = FastAPI(title="Gross Margin Optimizer", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Gross Margin Optimizer</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Gross Margin Optimizer</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/finance/gross_margin")
    def gross_margin(period: str = "monthly"):
        """Gross margin report — period → revenue + cogs_breakdown + gm_pct + optimization_opportunities."""
        multiplier = 1.0
        if period == "annual":
            multiplier = 12.0
        elif period == "quarterly":
            multiplier = 3.0

        cogs = {k: round(v * multiplier, 2) for k, v in COGS_BREAKDOWN.items()}
        total_cogs = round(TOTAL_COGS * multiplier, 2)

        # Derive revenue from current GM%: revenue = cogs / (1 - gm_pct)
        revenue = round(total_cogs / (1 - CURRENT_GM_PCT / 100), 2)
        gross_profit = round(revenue - total_cogs, 2)

        opportunities = [
            {
                "lever": lever,
                "monthly_savings": details["savings"],
                "period_savings": round(details["savings"] * multiplier, 2),
                "description": details["description"],
                "risk": details["risk"],
            }
            for lever, details in OPTIMIZATION_LEVERS.items()
        ]

        return JSONResponse({
            "period": period,
            "revenue": revenue,
            "cogs_breakdown": cogs,
            "total_cogs": total_cogs,
            "gross_profit": gross_profit,
            "gm_pct": CURRENT_GM_PCT,
            "target_gm_pct": TARGET_GM_PCT,
            "gap_pct": round(TARGET_GM_PCT - CURRENT_GM_PCT, 1),
            "optimization_opportunities": opportunities,
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/finance/gm_forecast")
    def gm_forecast(initiative_set: str = "all"):
        """GM forecast — initiative_set → projected_gm_pct + annual_impact."""
        if initiative_set == "all":
            selected_levers = list(OPTIMIZATION_LEVERS.keys())
        elif initiative_set == "low_risk":
            selected_levers = [k for k, v in OPTIMIZATION_LEVERS.items() if v["risk"] == "low"]
        elif initiative_set == "spot_only":
            selected_levers = ["spot_instances"]
        else:
            selected_levers = initiative_set.split(",")

        monthly_savings = sum(
            OPTIMIZATION_LEVERS[lever]["savings"]
            for lever in selected_levers
            if lever in OPTIMIZATION_LEVERS
        )
        annual_savings = round(monthly_savings * 12, 2)

        # New COGS after savings
        new_monthly_cogs = max(TOTAL_COGS - monthly_savings, 0)
        revenue = TOTAL_COGS / (1 - CURRENT_GM_PCT / 100)
        projected_gm_pct = round((1 - new_monthly_cogs / revenue) * 100, 2) if revenue > 0 else CURRENT_GM_PCT
        gm_improvement = round(projected_gm_pct - CURRENT_GM_PCT, 2)

        return JSONResponse({
            "initiative_set": initiative_set,
            "selected_levers": selected_levers,
            "monthly_savings": round(monthly_savings, 2),
            "annual_savings": annual_savings,
            "current_gm_pct": CURRENT_GM_PCT,
            "projected_gm_pct": projected_gm_pct,
            "gm_improvement_pct": gm_improvement,
            "target_gm_pct": TARGET_GM_PCT,
            "target_achieved": projected_gm_pct >= TARGET_GM_PCT,
            "ts": datetime.utcnow().isoformat(),
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
