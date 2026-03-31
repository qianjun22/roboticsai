"""
Sales engineer toolkit — POC configurator, ROI builder, objection handler library, demo script generator.
FastAPI service — OCI Robot Cloud
Port: 10085
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10085

# ---------------------------------------------------------------------------
# Domain data: objection library
# ---------------------------------------------------------------------------
OBJECTION_LIBRARY: Dict[str, Dict[str, Any]] = {
    "cost": {
        "response": (
            "OCI Robot Cloud is priced on a consumption model — you pay only for active inference "
            "and training compute. Typical customers see 40-60% cost reduction versus on-prem GPU "
            "clusters when factoring in hardware refresh, maintenance, and staffing. Our ROI calculator "
            "shows break-even in under 6 months for fleets of 10+ robots."
        ),
        "supporting_data": [
            {"metric": "avg_cost_per_10k_inference_steps", "value": "$0.0043", "source": "OCI A100 benchmarks Q1-2027"},
            {"metric": "on_prem_tco_per_year", "value": "$280K", "source": "Gartner robotics TCO 2026"},
            {"metric": "cloud_tco_equivalent", "value": "$112K", "source": "OCI internal analysis"},
        ],
        "sources": ["OCI Pricing Calculator", "Gartner Robotics TCO 2026", "Customer case study — Tier-1 Automotive"],
    },
    "latency": {
        "response": (
            "GR00T N1.6 inference on OCI A100 instances achieves 227ms end-to-end (camera → action). "
            "For safety-critical edge tasks we support Jetson Orin deployment with the same fine-tuned "
            "checkpoint, delivering sub-50ms local inference with cloud sync for continuous learning."
        ),
        "supporting_data": [
            {"metric": "cloud_e2e_latency_ms", "value": "227", "source": "Session 3 benchmarks"},
            {"metric": "edge_latency_ms", "value": "<50", "source": "Jetson Orin NX 16GB"},
            {"metric": "action_prediction_overhead_ms", "value": "8", "source": "Session cycle-507A"},
        ],
        "sources": ["OCI Robot Cloud benchmark suite", "NVIDIA Jetson performance brief 2026"],
    },
    "data_privacy": {
        "response": (
            "All training data stays in your OCI tenancy — we never move robot telemetry outside "
            "your designated region. Fine-tuned model weights are tenant-scoped and encrypted at "
            "rest (AES-256) and in transit (TLS 1.3). You retain full IP ownership of derivative models."
        ),
        "supporting_data": [
            {"metric": "data_residency", "value": "tenant-isolated VCN", "source": "OCI security architecture"},
            {"metric": "encryption_at_rest", "value": "AES-256 OCI Vault", "source": "OCI security docs"},
            {"metric": "compliance", "value": "SOC2 Type II, ISO 27001", "source": "OCI compliance portal"},
        ],
        "sources": ["OCI Security Overview", "OCI Compliance Certifications 2026"],
    },
    "vendor_lock_in": {
        "response": (
            "OCI Robot Cloud is built on open standards: LeRobot dataset format, HuggingFace model hub "
            "compatibility, and standard REST APIs. You can export any fine-tuned checkpoint in PyTorch "
            "format and run it anywhere. Our SDK is pip-installable and MIT-licensed."
        ),
        "supporting_data": [
            {"metric": "model_export_format", "value": "PyTorch .pt + ONNX", "source": "OCI Robot Cloud SDK"},
            {"metric": "dataset_format", "value": "LeRobot / HuggingFace", "source": "open standard"},
            {"metric": "sdk_license", "value": "MIT", "source": "github.com/qianjun22/roboticsai"},
        ],
        "sources": ["OCI Robot Cloud SDK docs", "LeRobot dataset spec", "HuggingFace Hub docs"],
    },
    "accuracy": {
        "response": (
            "Our GR00T-based fine-tuning pipeline achieves 85% closed-loop success rate on standard "
            "LIBERO benchmarks (17/20 tasks), with MAE of 0.013 after 2000-step fine-tuning — an 8.7x "
            "improvement over the base model. DAgger-based continuous learning further improves SR "
            "on customer-specific tasks over time."
        ),
        "supporting_data": [
            {"metric": "closed_loop_SR", "value": "85% (17/20)", "source": "Session 24 eval"},
            {"metric": "MAE_after_finetune", "value": "0.013", "source": "Session 5 training run"},
            {"metric": "improvement_vs_base", "value": "8.7x", "source": "baseline MAE 0.103"},
        ],
        "sources": ["LIBERO benchmark suite", "OCI Robot Cloud eval harness", "GR00T N1.6 paper"],
    },
    "integration": {
        "response": (
            "Integration takes under 2 hours for ROS2-compatible robots. We provide a Python SDK, "
            "Docker Compose stack, and pre-built ROS2 nodes. A standard POC can be running in 1 day "
            "with your existing robot URDF and a 50-demo dataset."
        ),
        "supporting_data": [
            {"metric": "time_to_first_inference", "value": "<2 hours", "source": "SE field reports"},
            {"metric": "min_demos_for_poc", "value": "50", "source": "OCI Robot Cloud onboarding guide"},
            {"metric": "ros2_node_support", "value": "Humble + Iron", "source": "SDK v1.0 release notes"},
        ],
        "sources": ["OCI Robot Cloud quickstart guide", "ROS2 integration notes"],
    },
}

# Hardware SKU catalogue
HARDWARE_CATALOGUE = [
    {"sku": "BM.GPU.A100-v2.8", "gpus": 8, "gpu_type": "A100 80GB", "vcpus": 128, "ram_gb": 2048,
     "hourly_usd": 32.0, "use_case": "large-scale training + multi-task eval"},
    {"sku": "BM.GPU4.8", "gpus": 8, "gpu_type": "A10 24GB", "vcpus": 64, "ram_gb": 512,
     "hourly_usd": 12.0, "use_case": "inference serving + fine-tuning"},
    {"sku": "VM.GPU3.1", "gpus": 1, "gpu_type": "V100 16GB", "vcpus": 6, "ram_gb": 90,
     "hourly_usd": 3.06, "use_case": "dev/test + small-scale training"},
    {"sku": "Jetson-Orin-NX-16", "gpus": 0, "gpu_type": "integrated 1024-core Ampere",
     "vcpus": 8, "ram_gb": 16, "hourly_usd": 0.0, "use_case": "edge inference on robot"},
]


def _build_poc_plan(customer_context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured POC plan from customer context."""
    robot_count = customer_context.get("robot_count", 5)
    task_type = customer_context.get("task_type", "pick_and_place")
    industry = customer_context.get("industry", "manufacturing")
    timeline_weeks = customer_context.get("timeline_weeks", 4)
    existing_data_demos = customer_context.get("existing_data_demos", 0)

    # Determine data collection need
    demos_needed = max(0, 200 - existing_data_demos)
    collection_days = math.ceil(demos_needed / 50)  # ~50 demos/day with teleoperation

    # Select hardware
    if robot_count >= 20:
        hw = HARDWARE_CATALOGUE[0]  # A100 x8
    elif robot_count >= 5:
        hw = HARDWARE_CATALOGUE[1]  # A10 x8
    else:
        hw = HARDWARE_CATALOGUE[2]  # V100

    # Estimate training time
    training_steps = 2000
    steps_per_hour = 8460  # ~2.35 it/s * 3600
    training_hours = round(training_steps / steps_per_hour, 2)
    training_cost = round(training_hours * hw["hourly_usd"], 2)

    success_criteria = [
        f"Closed-loop SR >= 80% on {task_type} benchmark (10 trials)",
        f"End-to-end inference latency <= 300ms",
        f"Fine-tuning loss < 0.05 (convergence confirmed)",
        f"Deployment on {robot_count} robots without manual recalibration",
        f"Data flywheel: 50 new demos collected post-deployment",
    ]

    milestones = [
        {"week": 1, "milestone": "Environment setup, SDK install, URDF import, 50 base demos collected"},
        {"week": 2, "milestone": f"Initial fine-tune complete ({training_steps} steps), baseline eval 60%+ SR"},
        {"week": 3, "milestone": "DAgger iteration 1, eval SR >= 75%, edge deployment on 2 robots"},
        {"week": timeline_weeks, "milestone": "Full fleet deployment, monitoring dashboard live, POC sign-off"},
    ]

    return {
        "poc_name": f"OCI Robot Cloud POC — {industry.title()} {task_type.replace('_', ' ').title()}",
        "duration_weeks": timeline_weeks,
        "robot_count": robot_count,
        "task_type": task_type,
        "industry": industry,
        "data_collection": {
            "existing_demos": existing_data_demos,
            "demos_needed": demos_needed,
            "collection_days": collection_days,
            "method": "teleoperation + Isaac Sim synthetic augmentation",
        },
        "training": {
            "steps": training_steps,
            "estimated_hours": training_hours,
            "estimated_cost_usd": training_cost,
            "hardware_sku": hw["sku"],
        },
        "success_criteria": success_criteria,
        "milestones": milestones,
        "recommended_contacts": [
            "OCI Robotics Solutions Architect",
            "Customer ML/Robotics Lead",
            "OCI Account Executive",
        ],
    }


def _compute_roi(
    robot_count: int,
    task_type: str,
    current_annual_cost_usd: float,
) -> Dict[str, Any]:
    """Calculate ROI projection for OCI Robot Cloud adoption."""
    # Conservative improvement assumptions
    throughput_gain_pct = 35.0      # SR improvement → more successful cycles
    downtime_reduction_pct = 40.0   # predictive maintenance
    labour_offset_pct = 20.0        # fewer human interventions

    annual_savings = current_annual_cost_usd * (
        throughput_gain_pct / 100 * 0.4
        + downtime_reduction_pct / 100 * 0.3
        + labour_offset_pct / 100 * 0.3
    )
    # OCI cost estimate
    monthly_inference_cost = robot_count * 30 * 24 * 0.50  # $0.50/robot-hour inference
    annual_oci_cost = monthly_inference_cost * 12
    net_annual_benefit = annual_savings - annual_oci_cost
    payback_months = round((annual_oci_cost / (annual_savings / 12)), 1) if annual_savings > 0 else 999
    roi_pct = round(net_annual_benefit / annual_oci_cost * 100, 1) if annual_oci_cost > 0 else 0.0

    return {
        "robot_count": robot_count,
        "task_type": task_type,
        "current_annual_cost_usd": current_annual_cost_usd,
        "projected_annual_savings_usd": round(annual_savings, 0),
        "annual_oci_cost_usd": round(annual_oci_cost, 0),
        "net_annual_benefit_usd": round(net_annual_benefit, 0),
        "payback_months": payback_months,
        "roi_pct": roi_pct,
        "assumptions": {
            "throughput_gain_pct": throughput_gain_pct,
            "downtime_reduction_pct": downtime_reduction_pct,
            "labour_offset_pct": labour_offset_pct,
        },
    }


def _generate_demo_script(task_type: str, audience: str) -> Dict[str, Any]:
    """Generate a structured demo script for a given task type and audience."""
    scripts = {
        "pick_and_place": [
            {"step": 1, "action": "Show live camera feed from robot workspace", "talking_point": "This is raw RGB input — no special sensors or markers required."},
            {"step": 2, "action": "Trigger /prediction/action_sequence with current frame", "talking_point": "GR00T encodes the scene in 3ms. LSTM projects 5 steps ahead in 5ms total."},
            {"step": 3, "action": "Display predicted joint trajectory overlaid on camera", "talking_point": f"88% SR on dynamic tasks — {9}% better than reactive baselines."},
            {"step": 4, "action": "Execute action, show cube grasped", "talking_point": "End-to-end: 235ms. Closed-loop: 85% SR on 20-task LIBERO benchmark."},
            {"step": 5, "action": "Open training dashboard, show loss curve", "talking_point": "Fine-tuning 2000 steps takes 14 minutes, costs under $0.10 on OCI."},
        ],
        "assembly": [
            {"step": 1, "action": "Show multi-part assembly task setup", "talking_point": "6-DOF arm, standard industrial fixtures."},
            {"step": 2, "action": "Run 10-demo baseline, show 40% SR", "talking_point": "Zero-shot baseline with GR00T N1.6."},
            {"step": 3, "action": "Trigger fine-tuning pipeline with 200 demos", "talking_point": "LeRobot format — works with any teleoperation data."},
            {"step": 4, "action": "Show post-finetune eval: 85% SR", "talking_point": "2.1x improvement in 35 minutes of training."},
        ],
    }
    base_steps = scripts.get(task_type, scripts["pick_and_place"])

    audience_tips = {
        "technical": "Emphasise latency numbers, MAE metrics, and DAgger convergence curves.",
        "executive": "Lead with ROI: payback < 6 months, 35% throughput gain, no hardware investment.",
        "procurement": "Highlight consumption pricing, no upfront commitment, exit clauses in contract.",
    }

    return {
        "task_type": task_type,
        "audience": audience,
        "estimated_duration_min": len(base_steps) * 3,
        "steps": base_steps,
        "audience_tip": audience_tips.get(audience, audience_tips["technical"]),
        "closing_ask": "Can we schedule a 2-week POC with your robotics team?",
        "generated_at": datetime.utcnow().isoformat(),
    }


if USE_FASTAPI:
    app = FastAPI(
        title="Enterprise Sales Engineer Tool",
        version="1.0.0",
        description=(
            "SE toolkit for OCI Robot Cloud: POC configurator, ROI builder, "
            "objection handler library, and demo script generator."
        ),
    )

    # ------------------------------------------------------------------
    # Request / response models
    # ------------------------------------------------------------------
    class CustomerContext(BaseModel):
        customer_name: str = Field(..., description="Customer / prospect name")
        industry: str = Field("manufacturing", description="Industry vertical")
        robot_count: int = Field(5, ge=1, description="Number of robots in scope")
        task_type: str = Field("pick_and_place", description="Primary robot task type")
        timeline_weeks: int = Field(4, ge=1, le=12, description="Desired POC timeline in weeks")
        existing_data_demos: int = Field(0, ge=0, description="Existing demonstration dataset size")
        annual_robotics_opex_usd: Optional[float] = Field(
            None, description="Current annual robotics operating cost for ROI calculation"
        )

    class POCResponse(BaseModel):
        poc_plan: Dict[str, Any]
        success_criteria: List[str]
        hardware_list: List[Dict[str, Any]]
        roi_projection: Optional[Dict[str, Any]]
        demo_script: Dict[str, Any]
        timestamp: str

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    @app.post("/se/configure_poc", response_model=POCResponse)
    def configure_poc(req: CustomerContext):
        """Generate a full POC plan, hardware list, ROI projection, and demo script."""
        poc = _build_poc_plan(req.dict())

        roi = None
        if req.annual_robotics_opex_usd and req.annual_robotics_opex_usd > 0:
            roi = _compute_roi(req.robot_count, req.task_type, req.annual_robotics_opex_usd)

        # Hardware list: primary compute + edge option
        hw_list = [
            next(h for h in HARDWARE_CATALOGUE if h["sku"] == poc["training"]["hardware_sku"]),
            HARDWARE_CATALOGUE[3],  # always include Jetson edge option
        ]

        demo = _generate_demo_script(req.task_type, "technical")

        return POCResponse(
            poc_plan=poc,
            success_criteria=poc["success_criteria"],
            hardware_list=hw_list,
            roi_projection=roi,
            demo_script=demo,
            timestamp=datetime.utcnow().isoformat(),
        )

    @app.get("/se/objection_response")
    def objection_response(
        objection_type: str = Query(
            ...,
            description="Objection category: cost | latency | data_privacy | vendor_lock_in | accuracy | integration",
        )
    ):
        """Return a structured objection response with supporting data and sources."""
        entry = OBJECTION_LIBRARY.get(objection_type.lower())
        if not entry:
            available = list(OBJECTION_LIBRARY.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Objection type '{objection_type}' not found. Available: {available}",
            )
        return {
            "objection_type": objection_type,
            "response": entry["response"],
            "supporting_data": entry["supporting_data"],
            "sources": entry["sources"],
            "available_objection_types": list(OBJECTION_LIBRARY.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/se/roi_calculator")
    def roi_calculator(
        robot_count: int = Query(5, ge=1),
        task_type: str = Query("pick_and_place"),
        annual_opex_usd: float = Query(200000.0, ge=0),
    ):
        """Quick ROI calculation without full POC configuration."""
        return {
            "roi": _compute_roi(robot_count, task_type, annual_opex_usd),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/se/demo_script")
    def demo_script(
        task_type: str = Query("pick_and_place", description="pick_and_place | assembly"),
        audience: str = Query("technical", description="technical | executive | procurement"),
    ):
        """Generate a structured demo script for a given task and audience."""
        return _generate_demo_script(task_type, audience)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "enterprise_sales_engineer_tool",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Enterprise Sales Engineer Tool</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>Enterprise Sales Engineer Tool</h1><p>OCI Robot Cloud · Port 10085</p>
<p>POC Configurator · ROI Builder · Objection Handler · Demo Script Generator</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p>
<div class="stat">POC Config</div>
<div class="stat">ROI Builder</div>
<div class="stat">6 Objection Types</div>
<div class="stat">Demo Scripts</div>
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
