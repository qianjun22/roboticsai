"""Series A readiness scoring — 7 dimensions: product 90 / traction 88 / market 82 / team 70 / financials 85 / data room 94 / narrative 91. Composite 85/100, threshold 80. Team is weakest.
FastAPI service — OCI Robot Cloud
Port: 10137"""
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

PORT = 10137

READINESS_THRESHOLD = 80

DIMENSIONS = {
    "product": {
        "score": 90,
        "evidence": [
            "GR00T fine-tuning pipeline end-to-end on OCI",
            "MAE 0.013 (8.7x vs baseline)",
            "Closed-loop eval validated at 85% SR",
            "Multi-GPU DDP 3.07x throughput",
        ],
        "gaps": ["Isaac Sim RTX integration still in beta"],
        "improvement_actions": ["Complete Isaac Sim GA release", "Add real-robot A/B test results"],
    },
    "traction": {
        "score": 88,
        "evidence": [
            "3 design partners signed LOIs",
            "$6,355/mo pipeline committed",
            "CoRL paper submitted",
            "OCI production deployment live",
        ],
        "gaps": ["No paid revenue yet", "Limited real-world deployment hours"],
        "improvement_actions": ["Convert LOIs to paid pilots", "Log 500+ real-robot hours"],
    },
    "market": {
        "score": 82,
        "evidence": [
            "Robotics AI market $38B by 2030",
            "NVIDIA partnership pathway via GR00T",
            "Manufacturing automation tailwinds",
        ],
        "gaps": ["Competitive moat not fully articulated", "No defensible data network effect yet"],
        "improvement_actions": ["Publish market sizing with bottoms-up analysis", "Launch data flywheel with 3 partners"],
    },
    "team": {
        "score": 70,
        "evidence": [
            "Founding team with OCI infra expertise",
            "LLM infra background (strong)",
        ],
        "gaps": [
            "No dedicated robotics hardware engineer",
            "No CFO or finance lead",
            "Thin go-to-market team",
        ],
        "improvement_actions": [
            "Hire robotics HW engineer (critical path)",
            "Bring on fractional CFO",
            "Add enterprise sales hire",
        ],
    },
    "financials": {
        "score": 85,
        "evidence": [
            "18-month runway modeled",
            "OCI cost: $0.0043/10k training steps",
            "Unit economics positive at scale",
        ],
        "gaps": ["No audited financials", "Revenue recognition policy TBD"],
        "improvement_actions": ["Complete financial audit", "Finalize revenue recognition policy"],
    },
    "data_room": {
        "score": 94,
        "evidence": [
            "Cap table clean (no convertible notes)",
            "IP assignments complete",
            "GitHub repo with 318+ scripts",
            "7-slide product deck + AI World 12-slide deck",
            "CoRL paper draft",
        ],
        "gaps": ["Customer contracts not fully executed"],
        "improvement_actions": ["Execute 2 design partner MSAs"],
    },
    "narrative": {
        "score": 91,
        "evidence": [
            "Clear problem: sim-to-real gap costs OEMs $2M+/year",
            "OCI Robot Cloud as cloud-native solution",
            "CEO pitch deck complete",
            "GTC presentation prepared",
        ],
        "gaps": ["Customer quote / testimonial missing from deck"],
        "improvement_actions": ["Add 1-2 design partner quotes to narrative deck"],
    },
}

def composite_score() -> float:
    scores = [v["score"] for v in DIMENSIONS.values()]
    return round(sum(scores) / len(scores), 1)

if USE_FASTAPI:
    app = FastAPI(title="Series A Readiness Score", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Series A Readiness Score</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Series A Readiness Score</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/fundraising/series_a_score")
    def series_a_score(dimension: str = "product"):
        """Return score, evidence, gaps, and improvement_actions for a given dimension."""
        dim = dimension.lower()
        if dim not in DIMENSIONS:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"Unknown dimension '{dimension}'",
                    "valid_dimensions": list(DIMENSIONS.keys()),
                },
            )
        data = DIMENSIONS[dim]
        return {
            "dimension": dim,
            "score": data["score"],
            "max_score": 100,
            "threshold": READINESS_THRESHOLD,
            "above_threshold": data["score"] >= READINESS_THRESHOLD,
            "evidence": data["evidence"],
            "gaps": data["gaps"],
            "improvement_actions": data["improvement_actions"],
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    @app.get("/fundraising/readiness_summary")
    def readiness_summary():
        """Return composite score, strongest/weakest dimension, and investor_ready flag."""
        comp = composite_score()
        sorted_dims = sorted(DIMENSIONS.items(), key=lambda x: x[1]["score"])
        weakest_name, weakest_data = sorted_dims[0]
        strongest_name, strongest_data = sorted_dims[-1]
        return {
            "composite_score": comp,
            "max_score": 100,
            "threshold": READINESS_THRESHOLD,
            "investor_ready_flag": comp >= READINESS_THRESHOLD,
            "strongest_dimension": {
                "name": strongest_name,
                "score": strongest_data["score"],
            },
            "weakest_dimension": {
                "name": weakest_name,
                "score": weakest_data["score"],
                "top_action": weakest_data["improvement_actions"][0] if weakest_data["improvement_actions"] else None,
            },
            "all_dimensions": {
                name: data["score"] for name, data in DIMENSIONS.items()
            },
            "evaluated_at": datetime.utcnow().isoformat(),
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
