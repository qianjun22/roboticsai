"""
AI World launch press kit generator — press release, fact sheet, media angles, spokesperson briefing, 3 audience variants (executive/technical/press).
FastAPI service — OCI Robot Cloud
Port: 10091
"""
from __future__ import annotations
import json, random, time
from datetime import datetime
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10091

# ---------------------------------------------------------------------------
# Press-kit content database
# ---------------------------------------------------------------------------

PRESS_KIT: Dict[str, Dict] = {
    "press_release": {
        "content": (
            "FOR IMMEDIATE RELEASE\n\n"
            "ORACLE CLOUD INFRASTRUCTURE LAUNCHES OCI ROBOT CLOUD AT AI WORLD 2026\n"
            "Industry-first cloud platform delivers end-to-end robot learning pipeline — "
            "from synthetic data generation to production deployment — at $0.0043 per 10 k training steps.\n\n"
            "AUSTIN, TX — Oracle today announced the general availability of OCI Robot Cloud, "
            "a fully managed platform for training, fine-tuning, and deploying robot foundation models at scale. "
            "Built on NVIDIA GR00T N1.6 and validated on OCI A100 GPU clusters, the platform achieves "
            "85% closed-loop success rate on standardised pick-and-place benchmarks — a 39% reduction in "
            "training loss versus baseline checkpoints. \n\n"
            "\"Robot AI is the next frontier for enterprise automation,\" said Jun Qian, Principal Product Manager, OCI. "
            "\"OCI Robot Cloud collapses the path from lab demo to production line from 18 months to 6 weeks.\"\n\n"
            "Key capabilities include Isaac Sim domain-randomised synthetic data generation, "
            "multi-GPU DDP fine-tuning with 3.07x throughput, DAgger interactive correction, "
            "and a Python SDK installable via pip.  Pricing starts at $0.0043 per 10 k training steps "
            "on OCI A100 bare metal.\n\n"
            "General availability begins April 1, 2026.  Design partner program open now at oracle.com/oci-robot-cloud."
        ),
        "key_messages": [
            "85% closed-loop success rate on pick-and-place benchmarks",
            "39% training loss reduction vs baseline GR00T checkpoint",
            "3.07x multi-GPU DDP throughput on OCI A100 bare metal",
            "$0.0043 per 10k training steps — lowest cost-per-step in industry",
            "6-week time-to-production vs 18-month industry average",
        ],
        "approved_quotes": [
            "Robot AI is the next frontier for enterprise automation. OCI Robot Cloud collapses the path from lab demo to production line from 18 months to 6 weeks. — Jun Qian, Principal PM, OCI",
            "We were able to fine-tune a manipulation policy on our custom dataset and deploy to our Jetson fleet in under a week. The OCI SDK made it seamless. — Design Partner, Tier-1 Automotive OEM",
            "The ensemble DAgger correction loop cut our human labelling effort by 40% while improving success rate by 3 percentage points. — Design Partner, Industrial Robotics ISV",
        ],
    },
    "fact_sheet": {
        "content": (
            "OCI ROBOT CLOUD — PRODUCT FACT SHEET (AI World 2026)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Foundation Model: NVIDIA GR00T N1.6 (3B params, 227ms inference, 6.7 GB GPU)\n"
            "Synthetic Data: Isaac Sim RTX domain randomisation, IK motion-planned demos\n"
            "Fine-tuning: Multi-GPU DDP, 2.35 it/s per GPU, 87% GPU utilisation\n"
            "Benchmark SR: 85% (17/20 closed-loop episodes, 235ms mean latency)\n"
            "Training Loss: 0.099 (1000-demo fine-tune, 35.4 min, −39% vs baseline)\n"
            "DAgger: Run138 ensemble (3 policies, majority vote, +3% SR over single policy)\n"
            "Deploy: Jetson Orin NX / AGX, OCI A10/A100, Docker Compose + Makefile\n"
            "SDK: pip install oci-robot-cloud; CLI: oci-robot-cloud <command>\n"
            "Pricing: $0.0043 / 10k steps (A100 BM); free tier: 50k steps/month\n"
            "Regions: us-ashburn-1, eu-frankfurt-1, ap-tokyo-1 (GA); 5 more regions Q2 2026\n"
            "Compliance: SOC 2 Type II (in progress), ISO 27001, OCI Security Zones\n"
            "GA Date: April 1, 2026 | Design partner program: oracle.com/oci-robot-cloud"
        ),
        "key_messages": [
            "Full-stack: SDG → fine-tuning → eval → deploy in one platform",
            "OCI-native: leverages OCI A100 BM, OCI Block Storage, OCI Container Registry",
            "Open standards: LeRobot dataset format, HuggingFace model hub integration",
            "Enterprise-grade: multi-region failover, 99.94% SLA, Oracle Support",
        ],
        "approved_quotes": [
            "OCI Robot Cloud is the AWS SageMaker moment for robotics — a fully managed ML platform purpose-built for physical AI. — Jun Qian, Principal PM, OCI",
        ],
    },
    "spokesperson_briefing": {
        "content": (
            "SPOKESPERSON BRIEFING — AI World 2026\n"
            "Message hierarchy:\n"
            "  1. LEAD with 85% SR benchmark and 39% loss reduction — these are defensible numbers.\n"
            "  2. BRIDGE to total cost: $0.0043/10k steps + free tier lowers barrier to entry.\n"
            "  3. CLOSE with 6-week time-to-production narrative.\n\n"
            "Anticipated tough questions:\n"
            "  Q: How does this compare to AWS RoboMaker or Azure robot offerings?\n"
            "  A: Neither AWS nor Azure offers a managed fine-tuning pipeline for robot foundation models. "
            "OCI Robot Cloud is first-to-market with end-to-end managed training on GR00T.\n\n"
            "  Q: Is 85% SR production-grade?\n"
            "  A: 85% on standardised benchmarks is on par with published academic SOTA. "
            "Real-world deployments with our design partners exceed 90% after domain-specific fine-tuning.\n\n"
            "  Q: What's the lock-in story?\n"
            "  A: LeRobot dataset format and HuggingFace model hub — full data + model portability.\n\n"
            "Do NOT discuss: unreleased hardware partnerships, specific customer names (use 'design partner'), "
            "roadmap items beyond Q2 2026."
        ),
        "key_messages": [
            "Speak to outcomes (SR, loss, cost, time-to-production) not features",
            "Always anchor competitive claims to public benchmarks",
            "Design partner anecdotes are approved — no named customer references",
        ],
        "approved_quotes": [
            "We built OCI Robot Cloud because our enterprise customers were spending 80% of their time on infrastructure, not on improving their policies. We flip that ratio. — Jun Qian, Principal PM, OCI",
        ],
    },
}

AUDIENCE_VARIANTS: Dict[str, Dict[str, str]] = {
    "executive": {
        "press_release": (
            "Oracle OCI Robot Cloud: From lab demo to production line in 6 weeks. "
            "85% task success rate. 39% lower training cost. GA April 1, 2026."
        ),
        "fact_sheet": (
            "ROI summary: $0.0043/10k training steps, 6-week deployment, "
            "99.94% SLA, multi-region HA. Design partner ROI: 40% less human labelling, "
            "3x faster iteration cycles."
        ),
        "positioning": "Board-level: physical AI as competitive moat; OCI as infrastructure layer.",
    },
    "technical": {
        "press_release": (
            "OCI Robot Cloud: GR00T N1.6 fine-tuning pipeline with multi-GPU DDP (3.07x), "
            "Isaac Sim IK-planned SDG, DAgger ensemble correction (3 policies, majority vote, +3% SR). "
            "pip install oci-robot-cloud. REST API + Python SDK. LeRobot format."
        ),
        "fact_sheet": (
            "Stack: FastAPI services (ports 8001–10091+), LeRobot HDF5 dataset, "
            "HuggingFace model hub, Docker Compose, Makefile, OCI A100 BM. "
            "Fine-tune CLI: oci-robot-cloud finetune --episodes 1000 --steps 2000."
        ),
        "positioning": "ML engineers: drop-in replacement for custom fine-tuning scripts with 3x throughput gain.",
    },
    "press": {
        "press_release": (
            "Oracle enters the robot AI race with OCI Robot Cloud — a cloud platform that teaches "
            "robots new skills in under 6 weeks and costs less than half a cent per 10,000 training steps. "
            "General availability: April 1, 2026."
        ),
        "fact_sheet": (
            "The headline numbers: 85% success rate picking up objects, 39% smarter than out-of-the-box "
            "models, 3x faster training than a single GPU. Price: $0.0043 per 10k steps "
            "(a 1000-step fine-tune costs $0.43)."
        ),
        "positioning": "Story angle: Oracle vs AWS/Azure in the physical AI land-grab; cost democratisation.",
    },
}

MEDIA_ANGLES: Dict[str, Dict] = {
    "trade_robotics": {
        "recommended_angle": "Benchmark deep-dive: 85% SR + ensemble DAgger — how OCI closes the sim-to-real gap",
        "supporting_data": [
            "85% closed-loop SR (17/20 episodes, 235ms latency)",
            "MAE 0.013 after IK-planned SDG fine-tune (vs 0.103 baseline)",
            "DAgger run138: +3% SR over best single policy via ensemble uncertainty",
            "3.07x multi-GPU DDP throughput on A100 bare metal",
        ],
    },
    "enterprise_tech": {
        "recommended_angle": "6-week time-to-production: how OCI Robot Cloud makes robot AI enterprise-ready",
        "supporting_data": [
            "Full pipeline: Isaac Sim SDG → GR00T fine-tune → eval → Jetson deploy",
            "$0.0043/10k steps — lowest published cost-per-step",
            "99.94% SLA, SOC 2 in progress, Oracle Support SLAs",
            "Design partner: 40% reduction in human labelling effort",
        ],
    },
    "cloud_infrastructure": {
        "recommended_angle": "Oracle's physical AI play: OCI A100 BM + managed robotics MLOps vs AWS/Azure",
        "supporting_data": [
            "OCI A100 BM: 2.35 it/s per GPU, 87% utilisation",
            "Multi-region GA: us-ashburn-1, eu-frankfurt-1, ap-tokyo-1",
            "No managed GR00T offering from AWS or Azure at GA",
            "LeRobot + HuggingFace: open-standard data/model portability",
        ],
    },
    "mainstream_business": {
        "recommended_angle": "The AWS moment for robot brains: Oracle bets on physical AI as next cloud wave",
        "supporting_data": [
            "Robot AI market: $38B by 2030 (IDC)",
            "OCI Robot Cloud: teach a robot a new skill for under $5",
            "Design partners span automotive, logistics, and semiconductor manufacturing",
            "GA April 1, 2026 — ahead of projected AWS/Azure competing launches",
        ],
    },
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="AI World Press Kit", version="1.0.0")

    @app.get("/pr/press_kit")
    def press_kit(
        section: str = Query(default="press_release", description="press_release | fact_sheet | spokesperson_briefing"),
        audience: str = Query(default="press", description="executive | technical | press"),
    ):
        """
        Return a press kit section, optionally tailored to an audience variant.
        Available sections: press_release, fact_sheet, spokesperson_briefing.
        Audience variants (press_release + fact_sheet only): executive, technical, press.
        """
        if section not in PRESS_KIT:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Unknown section '{section}'. Valid: {list(PRESS_KIT.keys())}",
            )

        base = PRESS_KIT[section]
        content = base["content"]
        key_messages = base["key_messages"]
        approved_quotes = base["approved_quotes"]

        # Overlay audience variant if available
        audience_overlay = AUDIENCE_VARIANTS.get(audience, {})
        if section in audience_overlay:
            content = audience_overlay[section]
        positioning = audience_overlay.get("positioning", "")

        return {
            "section": section,
            "audience": audience,
            "content": content,
            "key_messages": key_messages,
            "approved_quotes": approved_quotes,
            "positioning_note": positioning,
            "generated_at": datetime.utcnow().isoformat(),
        }

    @app.get("/pr/media_angles")
    def media_angles(
        outlet_type: str = Query(
            default="trade_robotics",
            description="trade_robotics | enterprise_tech | cloud_infrastructure | mainstream_business",
        )
    ):
        """
        Return the recommended media angle and supporting data points for a given outlet type.
        """
        if outlet_type not in MEDIA_ANGLES:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Unknown outlet_type '{outlet_type}'. Valid: {list(MEDIA_ANGLES.keys())}",
            )
        angle = MEDIA_ANGLES[outlet_type]
        return {
            "outlet_type": outlet_type,
            "recommended_angle": angle["recommended_angle"],
            "supporting_data": angle["supporting_data"],
            "all_outlet_types": list(MEDIA_ANGLES.keys()),
            "generated_at": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ai_world_press_kit", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>AI World Press Kit</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>AI World Press Kit</h1><p>OCI Robot Cloud · Port 10091</p>
<p>Press release · Fact sheet · Media angles · Spokesperson briefing · 3 audience variants (executive / technical / press)</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p>
<div class="stat">GET /pr/press_kit?section=press_release&audience=executive</div>
<div class="stat">GET /pr/media_angles?outlet_type=trade_robotics</div>
</body></html>""")

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
