"""Competitive differentiation map — OCI vs PI Research vs Covariant vs AWS across 7 dimensions (NVIDIA-native / cost / SR / latency / embodiment / enterprise / ecosystem). Core message: 'Only cloud with 100% NVIDIA stack + 9.6× cheaper + 85% SR proven on A100'.
FastAPI service — OCI Robot Cloud
Port: 10123"""
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

PORT = 10123

DIFF_MAP = {
    "nvidia_native": {
        "oci": 10,
        "pi_research": 4,
        "covariant": 5,
        "aws": 3,
        "oci_advantage": "100% NVIDIA stack: GR00T + Isaac Sim + NIM + H100/A100 native"
    },
    "cost": {
        "oci": 10,
        "pi_research": 2,
        "covariant": 3,
        "aws": 5,
        "oci_advantage": "9.6× cheaper than PI Research; $0.0043/10k training steps on A100"
    },
    "success_rate": {
        "oci": 9,
        "pi_research": 8,
        "covariant": 7,
        "aws": 5,
        "oci_advantage": "85% SR proven on A100 (GR00T closed-loop eval, 17/20 episodes)"
    },
    "latency": {
        "oci": 9,
        "pi_research": 7,
        "covariant": 6,
        "aws": 6,
        "oci_advantage": "227ms end-to-end inference; RDMA networking for sub-250ms SLA"
    },
    "embodiment_support": {
        "oci": 9,
        "pi_research": 6,
        "covariant": 8,
        "aws": 4,
        "oci_advantage": "Universal embodiment adapter; supports 10+ robot platforms via LeRobot"
    },
    "enterprise": {
        "oci": 9,
        "pi_research": 5,
        "covariant": 6,
        "aws": 8,
        "oci_advantage": "Oracle enterprise contracts, compliance, multi-region failover (99.94% uptime)"
    },
    "ecosystem": {
        "oci": 9,
        "pi_research": 7,
        "covariant": 6,
        "aws": 8,
        "oci_advantage": "NVIDIA DGX Cloud alliance + Oracle database + Cosmos world model integration"
    }
}

MESSAGING = {
    "cto": {
        "primary_message": "Only cloud with 100% NVIDIA stack + 9.6× cheaper + 85% SR proven on A100",
        "supporting_points": [
            "GR00T N1.6 + Isaac Sim + NIM inference — fully integrated, no DIY glue",
            "Multi-GPU DDP 3.07× throughput; fine-tune in hours, not days",
            "Universal embodiment adapter: swap robot hardware without retraining"
        ],
        "proof_points": [
            "MAE 0.013 after SDG fine-tune (8.7× improvement over baseline)",
            "85% closed-loop SR (17/20 episodes, 235ms avg latency)",
            "$0.0043/10k training steps on OCI A100"
        ]
    },
    "vp_engineering": {
        "primary_message": "Production-ready robotics AI platform — deploy in days, not months",
        "supporting_points": [
            "pip-installable SDK (oci-robot-cloud CLI), FastAPI microservices, Docker compose",
            "Automated DAgger + continuous learning loop; auto-retrain on SR regression",
            "Multi-region failover, safety monitor, A/B policy testing built-in"
        ],
        "proof_points": [
            "80+ production scripts; CI workflow; model registry with versioning",
            "99.94% uptime SLA; RDMA sub-250ms inference guarantee",
            "CoRL paper draft: noise-robust DAgger +8% SR under sensor noise"
        ]
    },
    "cfo": {
        "primary_message": "9.6× lower TCO vs PI Research; proven ROI at scale",
        "supporting_points": [
            "OCI A100 spot pricing vs dedicated PI Research hardware",
            "Design partner CRM pipeline: $6,355/mo tracked; billing service included",
            "Pay-per-use inference; no upfront robot compute commitment"
        ],
        "proof_points": [
            "$0.0043/10k training steps (benchmarked, reproducible)",
            "35.4min for 1000-demo fine-tune on single A100",
            "Inference cost tracker + cost optimizer services deployed"
        ]
    },
    "default": {
        "primary_message": "Only cloud with 100% NVIDIA stack + 9.6× cheaper + 85% SR proven on A100",
        "supporting_points": [
            "NVIDIA-native: GR00T + Isaac Sim + NIM on OCI H100/A100",
            "Enterprise-grade: Oracle compliance, multi-region, 99.94% uptime",
            "Proven results: 85% SR, MAE 0.013, 3.07× multi-GPU throughput"
        ],
        "proof_points": [
            "85% closed-loop success rate (17/20 episodes)",
            "9.6× cheaper than PI Research",
            "227ms end-to-end inference latency"
        ]
    }
}

if USE_FASTAPI:
    app = FastAPI(title="Product Differentiation Map", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Product Differentiation Map</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>Product Differentiation Map</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p></body></html>""")

    @app.get("/competitive/diff_map")
    def diff_map(dimension: str = None):
        """dimension → oci_score + competitor_scores + oci_advantage"""
        if dimension and dimension in DIFF_MAP:
            d = DIFF_MAP[dimension]
            return JSONResponse({
                "dimension": dimension,
                "oci_score": d["oci"],
                "competitor_scores": {
                    "pi_research": d["pi_research"],
                    "covariant": d["covariant"],
                    "aws": d["aws"]
                },
                "oci_advantage": d["oci_advantage"],
                "ts": datetime.utcnow().isoformat()
            })
        # Return full map if no dimension specified
        result = {}
        for dim, scores in DIFF_MAP.items():
            result[dim] = {
                "oci_score": scores["oci"],
                "competitor_scores": {
                    "pi_research": scores["pi_research"],
                    "covariant": scores["covariant"],
                    "aws": scores["aws"]
                },
                "oci_advantage": scores["oci_advantage"]
            }
        return JSONResponse({
            "dimensions": result,
            "core_message": "Only cloud with 100% NVIDIA stack + 9.6× cheaper + 85% SR proven on A100",
            "competitors_covered": ["pi_research", "covariant", "aws"],
            "ts": datetime.utcnow().isoformat()
        })

    @app.get("/competitive/messaging")
    def messaging(audience: str = "default"):
        """audience → primary_message + supporting_points + proof_points"""
        msg = MESSAGING.get(audience, MESSAGING["default"])
        return JSONResponse({
            "audience": audience,
            "primary_message": msg["primary_message"],
            "supporting_points": msg["supporting_points"],
            "proof_points": msg["proof_points"],
            "available_audiences": list(MESSAGING.keys()),
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
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
