"""Pipeline stage conversion rate optimizer — prospect→qual 67% / qual→proposal 78% / proposal→eval 71% / eval→close 73% / overall 27%. Biggest leak: prospect→qual (33%). NVIDIA referral 45% vs outbound 18%.
FastAPI service — OCI Robot Cloud
Port: 10129"""
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

PORT = 10129

# Baseline conversion rates per stage pair
STAGE_CONVERSIONS = {
    "prospect_to_qual": {
        "conversion_rate": 0.67,
        "leakage_rate": 0.33,
        "root_causes": [
            "Insufficient ICP (Ideal Customer Profile) fit scoring at top of funnel",
            "SDR outreach too generic — low personalization index (0.31)",
            "Missing robotics use-case discovery questions in initial call",
            "No NVIDIA ecosystem signal used for lead scoring"
        ],
        "stage_label": "Prospect → Qualified"
    },
    "qual_to_proposal": {
        "conversion_rate": 0.78,
        "leakage_rate": 0.22,
        "root_causes": [
            "Technical evaluation prerequisites not set before proposal",
            "Budget qualification delayed to late in cycle",
            "Champion not identified in 38% of stalled deals"
        ],
        "stage_label": "Qualified → Proposal"
    },
    "proposal_to_eval": {
        "conversion_rate": 0.71,
        "leakage_rate": 0.29,
        "root_causes": [
            "ROI model not customized to prospect's robot fleet size",
            "Competitive displacement by on-prem alternatives (23% of losses)",
            "Proposal turnaround > 5 days loses urgency (avg 7.2 days)"
        ],
        "stage_label": "Proposal → Evaluation"
    },
    "eval_to_close": {
        "conversion_rate": 0.73,
        "leakage_rate": 0.27,
        "root_causes": [
            "Security review delays (avg +18 days for enterprise)",
            "Procurement cycle misalignment with fiscal quarter",
            "POC success criteria not locked before eval start"
        ],
        "stage_label": "Evaluation → Close"
    }
}

# Channel-level conversion benchmarks
CHANNEL_BENCHMARKS = {
    "nvidia_referral": 0.45,
    "partner_referral": 0.38,
    "inbound_web": 0.29,
    "field_event": 0.24,
    "outbound_sdr": 0.18
}

OVERALL_CONVERSION = 0.27  # prospect-to-close

# Improvement initiatives and projected impact
IMPROVEMENT_INITIATIVES = {
    "icp_scoring_v2": {
        "target_stage": "prospect_to_qual",
        "projected_lift": 0.08,
        "arr_impact_per_point": 125000,
        "effort": "medium"
    },
    "nvidia_referral_expansion": {
        "target_stage": "prospect_to_qual",
        "projected_lift": 0.06,
        "arr_impact_per_point": 110000,
        "effort": "low"
    },
    "champion_identification_playbook": {
        "target_stage": "qual_to_proposal",
        "projected_lift": 0.05,
        "arr_impact_per_point": 95000,
        "effort": "low"
    },
    "roi_model_customization": {
        "target_stage": "proposal_to_eval",
        "projected_lift": 0.07,
        "arr_impact_per_point": 105000,
        "effort": "medium"
    },
    "security_review_fasttrack": {
        "target_stage": "eval_to_close",
        "projected_lift": 0.06,
        "arr_impact_per_point": 90000,
        "effort": "high"
    },
    "proposal_sla_3day": {
        "target_stage": "proposal_to_eval",
        "projected_lift": 0.04,
        "arr_impact_per_point": 80000,
        "effort": "low"
    }
}


def _compute_overall_conversion(stage_rates: dict) -> float:
    """Multiply stage conversion rates to get overall funnel conversion."""
    result = 1.0
    for stage_pair, rate in stage_rates.items():
        result *= rate
    return round(result, 4)


if USE_FASTAPI:
    app = FastAPI(title="Pipeline Stage Conversion Optimizer", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Pipeline Stage Conversion Optimizer</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Pipeline Stage Conversion Optimizer</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>Overall pipeline conversion: {int(OVERALL_CONVERSION*100)}% · Biggest leak: prospect→qual (33%) · NVIDIA referral: 45% vs outbound: 18%</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/sales/stage_conversion")
    def stage_conversion(stage_pair: str = None):
        """Return conversion rate, leakage rate, and root causes for a pipeline stage pair.
        Query param: stage_pair (optional). Valid values: prospect_to_qual, qual_to_proposal,
        proposal_to_eval, eval_to_close. Omit for full funnel view.
        """
        if stage_pair:
            if stage_pair not in STAGE_CONVERSIONS:
                return JSONResponse(
                    {"error": f"Unknown stage_pair: {stage_pair}",
                     "valid_pairs": list(STAGE_CONVERSIONS.keys())},
                    status_code=404
                )
            data = STAGE_CONVERSIONS[stage_pair]
            return JSONResponse({
                "stage_pair": stage_pair,
                "stage_label": data["stage_label"],
                "conversion_rate": data["conversion_rate"],
                "leakage_rate": data["leakage_rate"],
                "root_causes": data["root_causes"],
                "channel_benchmarks": CHANNEL_BENCHMARKS,
                "ts": datetime.utcnow().isoformat()
            })

        # Full funnel view
        stage_rates = {k: v["conversion_rate"] for k, v in STAGE_CONVERSIONS.items()}
        computed_overall = _compute_overall_conversion(stage_rates)
        return JSONResponse({
            "funnel": [
                {
                    "stage_pair": k,
                    "stage_label": v["stage_label"],
                    "conversion_rate": v["conversion_rate"],
                    "leakage_rate": v["leakage_rate"],
                    "root_causes": v["root_causes"]
                }
                for k, v in STAGE_CONVERSIONS.items()
            ],
            "overall_conversion": OVERALL_CONVERSION,
            "computed_overall": computed_overall,
            "biggest_leak": {
                "stage_pair": "prospect_to_qual",
                "leakage_rate": 0.33,
                "note": "Top-of-funnel ICP fit is the primary improvement lever"
            },
            "channel_benchmarks": CHANNEL_BENCHMARKS,
            "ts": datetime.utcnow().isoformat()
        })

    @app.get("/sales/conversion_forecast")
    def conversion_forecast(improvement_initiatives: str = None):
        """Forecast projected conversion improvement and ARR impact from selected initiatives.
        Query param: improvement_initiatives — comma-separated initiative names.
        Valid: icp_scoring_v2, nvidia_referral_expansion, champion_identification_playbook,
               roi_model_customization, security_review_fasttrack, proposal_sla_3day
        Omit to see all available initiatives.
        """
        if not improvement_initiatives:
            return JSONResponse({
                "available_initiatives": [
                    {
                        "name": k,
                        "target_stage": v["target_stage"],
                        "projected_lift": v["projected_lift"],
                        "estimated_arr_impact": v["projected_lift"] * v["arr_impact_per_point"],
                        "effort": v["effort"]
                    }
                    for k, v in IMPROVEMENT_INITIATIVES.items()
                ],
                "baseline_overall_conversion": OVERALL_CONVERSION,
                "ts": datetime.utcnow().isoformat()
            })

        selected = [s.strip() for s in improvement_initiatives.split(",")]
        invalid = [s for s in selected if s not in IMPROVEMENT_INITIATIVES]
        if invalid:
            return JSONResponse(
                {"error": f"Unknown initiatives: {invalid}",
                 "valid": list(IMPROVEMENT_INITIATIVES.keys())},
                status_code=400
            )

        # Apply lifts to stage rates
        adjusted_rates = {k: v["conversion_rate"] for k, v in STAGE_CONVERSIONS.items()}
        total_arr_impact = 0.0
        applied = []
        for init_name in selected:
            init = IMPROVEMENT_INITIATIVES[init_name]
            stage = init["target_stage"]
            lift = init["projected_lift"]
            old_rate = adjusted_rates[stage]
            adjusted_rates[stage] = min(1.0, old_rate + lift)
            arr_impact = lift * init["arr_impact_per_point"]
            total_arr_impact += arr_impact
            applied.append({
                "initiative": init_name,
                "target_stage": stage,
                "projected_lift": lift,
                "stage_rate_before": round(old_rate, 4),
                "stage_rate_after": round(adjusted_rates[stage], 4),
                "estimated_arr_impact": round(arr_impact, 0),
                "effort": init["effort"]
            })

        projected_overall = _compute_overall_conversion(adjusted_rates)
        overall_lift = round(projected_overall - OVERALL_CONVERSION, 4)

        return JSONResponse({
            "baseline_overall_conversion": OVERALL_CONVERSION,
            "projected_conversion": projected_overall,
            "overall_lift": overall_lift,
            "overall_lift_pct": round(overall_lift / OVERALL_CONVERSION * 100, 1),
            "total_arr_impact": round(total_arr_impact, 0),
            "applied_initiatives": applied,
            "adjusted_stage_rates": adjusted_rates,
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
