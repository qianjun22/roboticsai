"""3-track acquisition funnel v2 — enterprise ABM + PLG trial + partner referral. Total pipeline $840K (3× v1). CAC: enterprise $14K / PLG $6K / partner $8K / blended $10.2K. Multi-touch attribution.
FastAPI service — OCI Robot Cloud
Port: 10139"""
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

PORT = 10139

# Funnel v2 configuration — 3× pipeline vs v1
FUNNEL_CONFIG = {
    "enterprise_abm": {
        "name": "Enterprise ABM",
        "cac": 14000,
        "pipeline_value": 480000,
        "avg_deal_size": 120000,
        "stage_rates": {
            "awareness": 1.0,
            "consideration": 0.35,
            "evaluation": 0.20,
            "negotiation": 0.12,
            "closed_won": 0.08
        },
        "avg_velocity_days": 90,
        "channels": ["executive_outreach", "industry_events", "analyst_relations", "targeted_content"]
    },
    "plg_trial": {
        "name": "PLG Trial",
        "cac": 6000,
        "pipeline_value": 240000,
        "avg_deal_size": 48000,
        "stage_rates": {
            "signup": 1.0,
            "activation": 0.55,
            "engagement": 0.38,
            "expansion": 0.22,
            "conversion": 0.15
        },
        "avg_velocity_days": 30,
        "channels": ["free_trial", "docs", "community", "in_product_upsell"]
    },
    "partner_referral": {
        "name": "Partner Referral",
        "cac": 8000,
        "pipeline_value": 120000,
        "avg_deal_size": 75000,
        "stage_rates": {
            "referral_received": 1.0,
            "qualified": 0.60,
            "demo_completed": 0.40,
            "proposal_sent": 0.25,
            "closed_won": 0.16
        },
        "avg_velocity_days": 45,
        "channels": ["si_partners", "isvs", "resellers", "technology_alliances"]
    }
}

TOTAL_PIPELINE = 840000  # $840K total pipeline
BLENDED_CAC = 10200      # $10.2K blended CAC

if USE_FASTAPI:
    app = FastAPI(title="Customer Acquisition Funnel v2", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Customer Acquisition Funnel v2</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Customer Acquisition Funnel v2</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>3-track acquisition: Enterprise ABM + PLG Trial + Partner Referral · $840K pipeline</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/funnel/v2/metrics")
    def funnel_metrics(track: str = None):
        """Return stage_rates + velocity + cac + pipeline_value for one or all tracks."""
        if track and track not in FUNNEL_CONFIG:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown track '{track}'. Valid: {list(FUNNEL_CONFIG.keys())}"}
            )

        tracks_to_return = {track: FUNNEL_CONFIG[track]} if track else FUNNEL_CONFIG

        result = {}
        for track_key, config in tracks_to_return.items():
            # Multi-touch attribution weights
            attribution = {
                ch: round(1.0 / len(config["channels"]), 3)
                for ch in config["channels"]
            }

            result[track_key] = {
                "name": config["name"],
                "stage_rates": config["stage_rates"],
                "velocity_days": config["avg_velocity_days"],
                "cac": config["cac"],
                "pipeline_value": config["pipeline_value"],
                "avg_deal_size": config["avg_deal_size"],
                "conversion_rate": list(config["stage_rates"].values())[-1],
                "estimated_customers": math.floor(config["pipeline_value"] / config["avg_deal_size"]),
                "multi_touch_attribution": attribution,
                "channels": config["channels"]
            }

        return {
            "tracks": result,
            "summary": {
                "total_pipeline": TOTAL_PIPELINE,
                "blended_cac": BLENDED_CAC,
                "v2_vs_v1_multiplier": 3.0,
                "tracks_active": len(FUNNEL_CONFIG)
            }
        }

    @app.get("/funnel/v2/forecast")
    def funnel_forecast(horizon_months: int = 12):
        """Forecast pipeline + revenue + customer_count over horizon_months."""
        if horizon_months < 1 or horizon_months > 60:
            return JSONResponse(
                status_code=400,
                content={"error": "horizon_months must be between 1 and 60"}
            )

        monthly_forecasts = []
        cumulative_pipeline = 0
        cumulative_revenue = 0
        cumulative_customers = 0

        # Growth assumptions: enterprise 8%/mo, PLG 12%/mo, partner 6%/mo
        growth_rates = {
            "enterprise_abm": 0.08,
            "plg_trial": 0.12,
            "partner_referral": 0.06
        }

        base_monthly = {
            track: config["pipeline_value"] / 12
            for track, config in FUNNEL_CONFIG.items()
        }

        for month in range(1, horizon_months + 1):
            month_pipeline = 0
            month_revenue = 0
            month_customers = 0
            track_breakdown = {}

            for track, config in FUNNEL_CONFIG.items():
                growth_factor = (1 + growth_rates[track]) ** (month - 1)
                m_pipeline = base_monthly[track] * growth_factor
                conversion = list(config["stage_rates"].values())[-1]
                m_revenue = m_pipeline * conversion
                m_customers = math.floor(m_revenue / config["avg_deal_size"])

                month_pipeline += m_pipeline
                month_revenue += m_revenue
                month_customers += m_customers

                track_breakdown[track] = {
                    "pipeline": round(m_pipeline),
                    "revenue": round(m_revenue),
                    "customers": m_customers
                }

            cumulative_pipeline += month_pipeline
            cumulative_revenue += month_revenue
            cumulative_customers += month_customers

            monthly_forecasts.append({
                "month": month,
                "pipeline": round(month_pipeline),
                "revenue": round(month_revenue),
                "customer_count": month_customers,
                "by_track": track_breakdown
            })

        return {
            "horizon_months": horizon_months,
            "monthly_forecast": monthly_forecasts,
            "cumulative": {
                "pipeline": round(cumulative_pipeline),
                "revenue": round(cumulative_revenue),
                "customer_count": cumulative_customers,
                "blended_cac": BLENDED_CAC,
                "total_acquisition_spend": cumulative_customers * BLENDED_CAC
            },
            "assumptions": {
                "enterprise_monthly_growth": "8%",
                "plg_monthly_growth": "12%",
                "partner_monthly_growth": "6%",
                "pipeline_v1_baseline": 280000
            }
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
