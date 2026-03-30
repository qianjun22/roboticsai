#!/usr/bin/env python3
"""
generate_api_docs.py — OCI Robot Cloud API Reference Generator

Produces a self-contained dark-theme HTML reference for every service
in the OCI Robot Cloud platform (ports 8000–8080).

Usage:
    python docs/generate_api_docs.py
    python docs/generate_api_docs.py --output docs/API_REFERENCE.html

No external dependencies — uses only the Python standard library.
"""

import argparse
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SERVICES = [
    # ── Core Inference ──────────────────────────────────────────────────────
    {
        "port": 8000,
        "name": "OpenVLA Inference Server",
        "title": "OCI Robot Cloud — Inference API",
        "file": "src/inference/server.py",
        "category": "Core Services",
        "description": (
            "Original OpenVLA-7B inference endpoint. Accepts camera images and "
            "language instructions; returns joint-space action vectors. Supports "
            "optional INT4/INT8 quantisation for reduced VRAM usage."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/predict", "Run a single inference step; returns action array"),
            ("GET",  "/health",  "Liveness check; returns model name and device"),
        ],
        "example": (
            "curl -s -X POST http://localhost:8000/predict \\\n"
            "  -F 'image=@frame.jpg' -F 'instruction=pick up the cube'"
        ),
    },
    {
        "port": 8001,
        "name": "GR00T N1.6 Inference Server",
        "title": "OCI Robot Cloud — GR00T N1.6 Inference API",
        "file": "src/inference/groot_server.py",
        "category": "Core Services",
        "description": (
            "Primary production inference server for NVIDIA GR00T N1.6 (6.7 GB, "
            "227 ms median latency on A100). Accepts multi-modal observations "
            "(RGB image + proprioception) and returns 16-step action chunks. "
            "Supports --mock flag for CI/demo without GPU."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/predict", "Action-chunk inference; returns List[float] of length 16×7"),
            ("GET",  "/health",  "Returns model path, device, load time, and chunk size"),
        ],
        "example": (
            "curl -s http://localhost:8001/health\n"
            "# POST with multipart: image (JPEG) + state (JSON float array)"
        ),
    },
    {
        "port": 8002,
        "name": "GR00T Franka Inference Server",
        "title": "OCI Robot Cloud — GR00T Franka Inference API",
        "file": "src/inference/groot_franka_server.py",
        "category": "Core Services",
        "description": (
            "Franka Panda–specific inference endpoint. Applies Franka joint-limit "
            "clamping and IK post-processing to raw GR00T action chunks. Used by "
            "DAgger training loop and the GTC live demo."
        ),
        "mock": True,
        "endpoints": [
            ("GET",  "/",        "Service info page (HTML)"),
            ("GET",  "/health",  "Returns model status and Franka config"),
            ("POST", "/predict", "Franka-specific action prediction with joint clamping"),
            ("GET",  "/model_info", "Model metadata: param count, chunk size, latency stats"),
        ],
        "example": (
            "python src/inference/groot_franka_server.py --port 8002 --mock\n"
            "curl -s http://localhost:8002/model_info"
        ),
    },
    {
        "port": 8003,
        "name": "Data Collection API",
        "title": "OCI Robot Cloud — Data Collection API",
        "file": "src/api/data_collection_api.py",
        "category": "Core Services",
        "description": (
            "REST API for uploading robot demonstration episodes. Stores episodes "
            "in LeRobot-compatible HDF5 format. Includes per-dataset quality scoring "
            "and automatic trigger for fine-tuning when episode thresholds are met."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/",                                 "Dashboard HTML"),
            ("GET",    "/datasets",                         "List all datasets"),
            ("GET",    "/datasets/{name}",                  "Dataset metadata and episode count"),
            ("POST",   "/datasets/{name}/episodes",         "Upload a new episode (multipart)"),
            ("POST",   "/datasets/{name}/finetune",         "Trigger GR00T fine-tune job"),
            ("GET",    "/datasets/{name}/quality",          "Quality score for dataset"),
            ("DELETE", "/datasets/{name}",                  "Delete dataset and all episodes"),
        ],
        "example": (
            "python src/api/data_collection_api.py\n"
            "curl -s http://localhost:8003/datasets"
        ),
    },
    {
        "port": 8004,
        "name": "Training Monitor",
        "title": "OCI Robot Cloud Training Monitor",
        "file": "src/api/training_monitor.py",
        "category": "Core Services",
        "description": (
            "Real-time training metrics dashboard. Tails loss/grad-norm from "
            "trainer log files and streams Server-Sent Events (SSE) to connected "
            "browsers. Includes an HTML dashboard at /dashboard."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/stream",    "SSE stream: loss, grad_norm, step, elapsed"),
            ("GET", "/status",    "Current training status JSON"),
            ("GET", "/metrics",   "Full metrics history"),
            ("GET", "/health",    "Service liveness"),
            ("GET", "/dashboard", "HTML live-chart dashboard"),
        ],
        "example": (
            "python src/api/training_monitor.py --port 8004 --log /tmp/train.log\n"
            "# Open http://localhost:8004/dashboard in browser"
        ),
    },
    {
        "port": 8005,
        "name": "Cost Calculator",
        "title": "OCI Robot Cloud Cost Calculator",
        "file": "src/api/cost_calculator.py",
        "category": "Infrastructure",
        "description": (
            "Interactive cost estimator for OCI Robot Cloud workloads. Computes "
            "estimated USD cost for fine-tuning jobs given GPU shape, step count, "
            "and dataset size. Exposes both a JSON API and a browser form."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",        "HTML cost calculator form"),
            ("GET",  "/estimate","JSON cost estimate; query params: steps, gpus, shape"),
            ("GET",  "/pricing", "Current GPU pricing table"),
            ("GET",  "/health",  "Service liveness"),
        ],
        "example": (
            "python src/api/cost_calculator.py --port 8005\n"
            "curl 'http://localhost:8005/estimate?steps=5000&gpus=4&shape=A100'"
        ),
    },
    {
        "port": 8006,
        "name": "Design Partner Portal",
        "title": "OCI Robot Cloud Design Partner Portal",
        "file": "src/api/design_partner_portal.py",
        "category": "Partner",
        "description": (
            "Self-service portal for design-partner onboarding. Manages partner "
            "accounts, quota allocations, API key issuance, and usage tracking. "
            "Partners register here before accessing fine-tune or data APIs."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/partners",               "List all design partners"),
            ("POST",   "/partners",               "Register a new design partner"),
            ("GET",    "/partners/{id}",           "Partner profile and quota"),
            ("PUT",    "/partners/{id}/quota",     "Update GPU-hour quota"),
            ("DELETE", "/partners/{id}",           "Offboard a partner"),
            ("GET",    "/dashboard",               "HTML management dashboard"),
        ],
        "example": (
            "python src/api/design_partner_portal.py --port 8006\n"
            "curl -s http://localhost:8006/partners"
        ),
    },
    {
        "port": 8007,
        "name": "Real Data Ingestion API",
        "title": "OCI Robot Cloud — Real Data Ingestion API",
        "file": "src/api/real_data_ingestion.py",
        "category": "Core Services",
        "description": (
            "High-throughput ingestion endpoint for real-robot telemetry. Accepts "
            "streamed sensor bags (ROS2 / HDF5), validates joint-limit compliance, "
            "deduplicates, converts to LeRobot format, and triggers the data flywheel."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/ingest",          "Upload raw sensor bag; returns dataset ID"),
            ("GET",  "/ingest/{id}",     "Ingestion job status and validation report"),
            ("GET",  "/datasets",        "List ingested datasets"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/api/real_data_ingestion.py --port 8007\n"
            "curl -s -X POST http://localhost:8007/ingest -F 'bag=@run1.h5'"
        ),
    },
    {
        "port": 8008,
        "name": "Fleet Dashboard",
        "title": "OCI Robot Cloud — Fleet Dashboard",
        "file": "src/api/deployment_dashboard.py",
        "category": "Infrastructure",
        "description": (
            "Deployment and fleet management dashboard. Tracks deployed model "
            "versions per robot, inference latency P50/P95, uptime SLA, and "
            "Jetson / OCI GPU resource utilisation across the entire fleet."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",                   "HTML fleet overview dashboard"),
            ("GET",  "/deployments",        "List all active deployments"),
            ("POST", "/deployments",        "Register a new deployment"),
            ("GET",  "/deployments/{id}",   "Deployment detail: version, metrics, SLA"),
            ("GET",  "/metrics/summary",    "Aggregated latency and uptime stats"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/deployment_dashboard.py --port 8008\n"
            "curl -s http://localhost:8008/deployments"
        ),
    },
    {
        "port": 8009,
        "name": "Inference Cache / Model Registry",
        "title": "GR00T Inference Cache",
        "file": "src/api/inference_cache.py  |  src/api/model_registry.py",
        "category": "Core Services",
        "description": (
            "Dual-purpose port. inference_cache.py (default) is an in-memory "
            "LRU cache layer sitting in front of the inference servers, reducing "
            "repeated-scene latency by ~40%. model_registry.py is an alternative "
            "that serves as a checkpoint database with promotion workflows."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/predict",             "Cache-aware predict (inference_cache mode)"),
            ("GET",  "/cache/stats",         "Hit/miss ratio and entry count"),
            ("GET",  "/checkpoints",         "All registered checkpoints (registry mode)"),
            ("GET",  "/checkpoints/best",    "Best checkpoint by eval metric"),
            ("POST", "/checkpoints",         "Register a new checkpoint"),
            ("POST", "/checkpoints/{tag}/promote", "Promote checkpoint to production"),
            ("GET",  "/dashboard",           "HTML registry dashboard"),
        ],
        "example": (
            "python src/api/inference_cache.py --port 8009\n"
            "# or: python src/api/model_registry.py --port 8009"
        ),
    },
    {
        "port": 8010,
        "name": "Cosmos World Model Server",
        "title": "OCI Robot Cloud — Cosmos Augmentation Server",
        "file": "src/simulation/cosmos_data_augmentation.py",
        "category": "Core Services",
        "description": (
            "Serves NVIDIA Cosmos world-model augmentation. Takes real or simulated "
            "episode frames and applies physics-consistent domain randomisation "
            "(lighting, textures, clutter) to expand training diversity and "
            "reduce the sim-to-real gap."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/augment",   "Augment an episode HDF5; returns augmented dataset path"),
            ("GET",  "/health",    "Returns Cosmos model status and GPU memory"),
        ],
        "example": (
            "python src/simulation/cosmos_data_augmentation.py --serve --port 8010\n"
            "curl -s -X POST http://localhost:8010/augment -F 'dataset=@ep.h5'"
        ),
    },
    {
        "port": 8011,
        "name": "Live Eval Streamer",
        "title": "OCI Robot Cloud — Live Eval Streamer",
        "file": "src/eval/live_eval_streamer.py",
        "category": "Evaluation",
        "description": (
            "Streams real-time evaluation results via SSE and WebSocket. Displays "
            "per-episode success/failure, action MAE, and cumulative success rate "
            "as a live HTML dashboard during long evaluation runs."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",         "HTML live evaluation dashboard"),
            ("GET", "/stream",   "SSE: episode results as they complete"),
            ("GET", "/status",   "Current eval state: episode count, success rate"),
            ("GET", "/health",   "Service liveness"),
        ],
        "example": (
            "python src/eval/live_eval_streamer.py --port 8011\n"
            "# Open http://localhost:8011 while running closed_loop_eval.py"
        ),
    },
    {
        "port": 8012,
        "name": "Model Comparison Portal",
        "title": "Model Comparison Portal",
        "file": "src/api/model_comparison_portal.py",
        "category": "Evaluation",
        "description": (
            "Side-by-side comparison of multiple GR00T checkpoints. Plots success "
            "rate, action MAE, inference latency, and cost-per-episode for up to "
            "four checkpoints simultaneously. Used for DAgger iteration reviews."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",                       "HTML comparison dashboard"),
            ("POST", "/compare",                "Submit comparison job: list of checkpoint paths"),
            ("GET",  "/compare/{job_id}",       "Comparison results with charts"),
            ("GET",  "/health",                 "Service liveness"),
        ],
        "example": (
            "python src/api/model_comparison_portal.py --port 8012\n"
            "curl -s http://localhost:8012/"
        ),
    },
    {
        "port": 8013,
        "name": "Cost Optimizer / Partner Weekly Reports",
        "title": "OCI Robot Cloud Cost Optimizer",
        "file": "src/api/cost_optimizer.py  |  src/api/partner_weekly_report.py",
        "category": "Infrastructure",
        "description": (
            "Dual-purpose port. cost_optimizer.py analyses training job history to "
            "recommend optimal batch size, gradient checkpointing, and spot-instance "
            "strategy. partner_weekly_report.py auto-generates weekly usage and "
            "ROI summaries for design partners."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/recommendations",    "Cost optimisation recommendations JSON"),
            ("POST", "/simulate",           "Simulate cost for a proposed job config"),
            ("GET",  "/reports",            "List partner weekly reports (report mode)"),
            ("GET",  "/reports/{id}",       "Rendered HTML/PDF weekly report"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/cost_optimizer.py --serve --port 8013\n"
            "curl -s http://localhost:8013/recommendations"
        ),
    },
    {
        "port": 8014,
        "name": "Retrain Scheduler",
        "title": "OCI Robot Cloud — Retrain Scheduler",
        "file": "src/api/retrain_scheduler.py",
        "category": "Infrastructure",
        "description": (
            "Cron-style scheduler for automatic retraining. Monitors per-partner "
            "data pipelines; triggers fine-tune jobs when new episode thresholds "
            "are exceeded or scheduled intervals elapse. Integrates with the "
            "training notifier (port 8052)."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/schedules",           "List all retrain schedules"),
            ("POST",   "/schedules",           "Create a new schedule"),
            ("DELETE", "/schedules/{id}",      "Delete a schedule"),
            ("POST",   "/schedules/{id}/trigger", "Manually trigger a scheduled retrain"),
            ("GET",    "/history",             "Past retrain job history"),
            ("GET",    "/health",              "Service liveness"),
        ],
        "example": (
            "python src/api/retrain_scheduler.py --port 8014\n"
            "curl -s http://localhost:8014/schedules"
        ),
    },
    {
        "port": 8015,
        "name": "Teleoperation Collector",
        "title": "OCI Teleop Collector",
        "file": "src/api/teleoperation_collector.py",
        "category": "Core Services",
        "description": (
            "WebSocket + REST API for collecting human teleoperation demonstrations. "
            "Receives 6-DOF controller inputs at 30 Hz, time-stamps and stores them "
            "as LeRobot HDF5 episodes, and optionally streams to the data collection "
            "API (port 8003)."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/",            "HTML teleop control panel"),
            ("POST",   "/episodes",    "Start a new episode recording"),
            ("PUT",    "/episodes/{id}/step", "Append a teleop step to episode"),
            ("POST",   "/episodes/{id}/end", "Finalise and save episode"),
            ("GET",    "/episodes",    "List saved episodes"),
            ("GET",    "/health",      "Service liveness"),
        ],
        "example": (
            "python src/api/teleoperation_collector.py --port 8015\n"
            "# Open http://localhost:8015 for browser-based teleop UI"
        ),
    },
    {
        "port": 8016,
        "name": "Safety Monitor",
        "title": "OCI Robot Safety Monitor",
        "file": "src/safety/safety_monitor.py",
        "category": "Infrastructure",
        "description": (
            "Real-time safety enforcement service. Validates every action chunk "
            "before it reaches the robot: joint-limit checks, velocity caps, "
            "workspace boundary enforcement, and collision-probability estimation. "
            "Raises alerts and optionally halts inference on violation."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/validate",       "Validate an action chunk; returns safe/unsafe + reason"),
            ("GET",  "/violations",     "Recent violation log"),
            ("GET",  "/config",         "Current safety parameters"),
            ("PUT",  "/config",         "Update safety thresholds"),
            ("GET",  "/health",         "Service liveness"),
        ],
        "example": (
            "python src/safety/safety_monitor.py --port 8016\n"
            "curl -s -X POST http://localhost:8016/validate -d '{\"actions\":[...]}'"
        ),
    },
    {
        "port": 8017,
        "name": "Billing Integration",
        "title": "OCI Robot Billing",
        "file": "src/api/billing_integration.py",
        "category": "Infrastructure",
        "description": (
            "Bridges OCI metering with partner billing. Tracks GPU-hour consumption "
            "per tenant, applies contracted pricing tiers, generates invoices, and "
            "pushes usage records to OCI Metering API. Supports prepaid and "
            "pay-as-you-go models."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/usage",                  "Aggregated usage by tenant and period"),
            ("GET",  "/usage/{tenant_id}",      "Per-tenant usage details"),
            ("POST", "/invoice",                "Generate invoice for a billing period"),
            ("GET",  "/rates",                  "Current pricing tiers"),
            ("GET",  "/health",                 "Service liveness"),
        ],
        "example": (
            "python src/api/billing_integration.py --port 8017\n"
            "curl -s http://localhost:8017/usage"
        ),
    },
    {
        "port": 8018,
        "name": "Continuous Learning Loop",
        "title": "OCI Continuous Learning Loop",
        "file": "src/training/continuous_learning.py",
        "category": "Core Services",
        "description": (
            "Orchestrates the closed-loop continuous learning pipeline: collects "
            "real-world failure episodes, merges them with the existing dataset, "
            "triggers incremental fine-tuning, evaluates the new checkpoint, and "
            "promotes it to production automatically when success rate improves."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/cycle",          "Trigger one CL iteration"),
            ("GET",  "/cycle/{id}",     "Cycle status: collect → train → eval → promote"),
            ("GET",  "/history",        "CL iteration history with metrics"),
            ("GET",  "/health",         "Service liveness"),
        ],
        "example": (
            "python src/training/continuous_learning.py --port 8018 --mock\n"
            "curl -s -X POST http://localhost:8018/cycle"
        ),
    },
    {
        "port": 8019,
        "name": "Experiment Tracker",
        "title": "OCI Experiment Tracker",
        "file": "src/eval/multimodal_experiment_tracker.py",
        "category": "Evaluation",
        "description": (
            "MLflow-style experiment tracking for multi-modal robot-learning runs. "
            "Records hyperparameters, training curves, eval metrics, and artifact "
            "paths per experiment. Provides a sortable comparison table UI."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/experiments",              "Create a new experiment"),
            ("GET",  "/experiments",              "List experiments with summary metrics"),
            ("GET",  "/experiments/{id}",         "Full experiment detail"),
            ("POST", "/experiments/{id}/runs",    "Add a training run to experiment"),
            ("GET",  "/compare",                  "HTML comparison table"),
            ("GET",  "/health",                   "Service liveness"),
        ],
        "example": (
            "python src/eval/multimodal_experiment_tracker.py --port 8019\n"
            "curl -s http://localhost:8019/experiments"
        ),
    },
    {
        "port": 8020,
        "name": "Data Flywheel",
        "title": "OCI Data Flywheel",
        "file": "src/api/data_flywheel.py",
        "category": "Core Services",
        "description": (
            "Automates the data flywheel: ingestion → quality filter → diversity "
            "sampling → augmentation → dataset versioning → fine-tune trigger. "
            "Connects ports 8003, 8007, 8010, and 8014 into a single orchestrated "
            "pipeline with configurable quality thresholds."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/pipeline/start",   "Start a flywheel pipeline run"),
            ("GET",  "/pipeline/{id}",    "Pipeline run status with per-stage progress"),
            ("GET",  "/pipeline",         "Recent pipeline runs"),
            ("GET",  "/health",           "Service liveness"),
        ],
        "example": (
            "python src/api/data_flywheel.py --port 8020\n"
            "curl -s -X POST http://localhost:8020/pipeline/start"
        ),
    },
    {
        "port": 8021,
        "name": "Webhook Notifications",
        "title": "OCI Robot Cloud — Webhook Notifications",
        "file": "src/api/webhook_notifications.py",
        "category": "Infrastructure",
        "description": (
            "Manages webhook subscriptions for design partners. Partners register "
            "HTTPS endpoints to receive real-time notifications for events: "
            "job_complete, eval_done, threshold_exceeded, invoice_ready, and "
            "safety_violation. Includes retry logic with exponential back-off."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/webhooks",            "List registered webhooks"),
            ("POST",   "/webhooks",            "Register a new webhook endpoint"),
            ("DELETE", "/webhooks/{id}",       "Remove a webhook"),
            ("POST",   "/webhooks/{id}/test",  "Send a test event"),
            ("GET",    "/webhooks/{id}/log",   "Delivery log for a webhook"),
            ("GET",    "/health",              "Service liveness"),
        ],
        "example": (
            "python src/api/webhook_notifications.py --port 8021\n"
            "curl -s http://localhost:8021/webhooks"
        ),
    },
    {
        "port": 8022,
        "name": "SLA Monitor",
        "title": "OCI Robot Cloud — SLA Monitor",
        "file": "src/api/partner_sla_monitor.py",
        "category": "Partner",
        "description": (
            "Continuously polls all registered services (ports 8001–8059) and "
            "tracks uptime, P95 latency, and error rates against per-partner SLA "
            "contracts. Fires webhook alerts when SLOs are breached."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/sla",                 "SLA status summary for all services"),
            ("GET", "/sla/{service}",       "Per-service SLA metrics and breach history"),
            ("GET", "/dashboard",           "HTML SLA dashboard with traffic-light status"),
            ("GET", "/health",              "Service liveness"),
        ],
        "example": (
            "python src/api/partner_sla_monitor.py --port 8022\n"
            "curl -s http://localhost:8022/sla"
        ),
    },
    {
        "port": 8023,
        "name": "Multi-Tenant Manager",
        "title": "OCI Robot Cloud — Multi-Tenant Manager",
        "file": "src/api/multi_tenant_manager.py",
        "category": "Infrastructure",
        "description": (
            "Resource isolation and quota enforcement for multi-tenant deployments. "
            "Maps partner API keys to OCI compartments, enforces GPU-hour and "
            "storage quotas, provides per-tenant cost attribution, and controls "
            "service access via RBAC."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/tenants",               "List tenants and quota status"),
            ("POST", "/tenants",               "Provision a new tenant"),
            ("GET",  "/tenants/{id}/usage",    "Real-time resource usage for tenant"),
            ("PUT",  "/tenants/{id}/quota",    "Update quota limits"),
            ("GET",  "/health",                "Service liveness"),
        ],
        "example": (
            "python src/api/multi_tenant_manager.py --port 8023\n"
            "curl -s http://localhost:8023/tenants"
        ),
    },
    {
        "port": 8024,
        "name": "Partner Onboarding Wizard",
        "title": "OCI Robot Cloud — Partner Onboarding Wizard",
        "file": "src/api/partner_onboarding_wizard.py",
        "category": "Partner",
        "description": (
            "Step-by-step guided onboarding for new design partners. Walkthroughs "
            "cover: OCI account setup, API key generation, first dataset upload, "
            "first fine-tune job, and integration health check. Tracks completion "
            "percentage per partner."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/onboarding/{partner_id}",          "Current onboarding progress"),
            ("POST", "/onboarding/{partner_id}/step/{n}", "Complete a step"),
            ("GET",  "/onboarding",                       "All partners and completion %"),
            ("GET",  "/health",                           "Service liveness"),
        ],
        "example": (
            "python src/api/partner_onboarding_wizard.py --port 8024\n"
            "curl -s http://localhost:8024/onboarding"
        ),
    },
    {
        "port": 8025,
        "name": "Episode Playback Server",
        "title": "Episode Playback Server",
        "file": "src/demo/episode_playback_server.py",
        "category": "Demo",
        "description": (
            "Serves recorded episodes as video streams for review and debugging. "
            "Reads HDF5 episode files, renders joint-trajectory overlays and "
            "camera frames, and streams them as MJPEG. Supports frame scrubbing "
            "and annotation via the browser UI."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",                       "HTML episode browser"),
            ("GET", "/episodes",               "List available episodes"),
            ("GET", "/episodes/{id}/stream",   "MJPEG stream of episode"),
            ("GET", "/episodes/{id}/metadata", "Episode metadata and trajectory stats"),
            ("GET", "/health",                 "Service liveness"),
        ],
        "example": (
            "python src/demo/episode_playback_server.py --port 8025\n"
            "# Open http://localhost:8025 for episode browser"
        ),
    },
    {
        "port": 8026,
        "name": "Analytics Dashboard",
        "title": "OCI Robot Cloud — Analytics Dashboard",
        "file": "src/api/analytics_dashboard.py",
        "category": "Infrastructure",
        "description": (
            "Business analytics dashboard aggregating usage, revenue, partner "
            "activity, and model performance. Displays time-series charts for "
            "GPU-hours consumed, inference request volume, fine-tune job counts, "
            "and estimated MRR."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",             "HTML analytics dashboard"),
            ("GET", "/metrics",      "JSON metrics: usage, jobs, revenue, latency"),
            ("GET", "/export",       "Export metrics as CSV"),
            ("GET", "/health",       "Service liveness"),
        ],
        "example": (
            "python src/api/analytics_dashboard.py --port 8026\n"
            "curl -s http://localhost:8026/metrics"
        ),
    },
    {
        "port": 8027,
        "name": "Partner Usage Analytics",
        "title": "Partner Usage Analytics",
        "file": "src/api/partner_usage_analytics.py",
        "category": "Partner",
        "description": (
            "Per-partner usage breakdown: API call counts, GPU-hours consumed, "
            "dataset upload volumes, fine-tune job history, and success-rate "
            "trends. Powers the partner self-service portal usage tab."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/partners/{id}/analytics",  "Full analytics for a partner"),
            ("GET", "/partners/{id}/summary",    "7-day and 30-day usage summary"),
            ("GET", "/report",                   "Cross-partner analytics report"),
            ("GET", "/health",                   "Service liveness"),
        ],
        "example": (
            "python src/api/partner_usage_analytics.py --port 8027\n"
            "curl -s http://localhost:8027/report"
        ),
    },
    {
        "port": 8028,
        "name": "Federated Training Coordinator",
        "title": "Federated Training Coordinator",
        "file": "src/training/federated_training.py",
        "category": "Core Services",
        "description": (
            "Coordinates federated learning across N partner nodes. Runs on OCI "
            "as the central aggregator: receives gradient updates from partner "
            "edge nodes, performs FedAvg aggregation, broadcasts the updated model, "
            "and tracks per-round convergence."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/rounds",           "Start a new federated round"),
            ("POST", "/rounds/{id}/grad", "Submit gradient update from a node"),
            ("GET",  "/rounds/{id}",      "Round status: nodes joined, aggregation done"),
            ("GET",  "/model/current",    "Current global model checkpoint URL"),
            ("GET",  "/health",           "Service liveness"),
        ],
        "example": (
            "python src/training/federated_training.py --mode coordinator --port 8028\n"
            "curl -s http://localhost:8028/rounds"
        ),
    },
    {
        "port": 8029,
        "name": "Demo Request Portal",
        "title": "OCI Robot Cloud Demo Portal",
        "file": "src/api/demo_request_portal.py",
        "category": "Demo",
        "description": (
            "Manages inbound demo requests from prospective customers and partners. "
            "Provides a public-facing form, slots available demo slots from the "
            "live demo scheduler (port 8031), sends confirmation emails via "
            "webhook, and tracks conversion funnel."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",                   "HTML demo request form"),
            ("POST", "/requests",           "Submit a demo request"),
            ("GET",  "/requests",           "Admin: list all requests"),
            ("PUT",  "/requests/{id}",      "Update request status"),
            ("GET",  "/slots",              "Available demo time slots"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/demo_request_portal.py --port 8029\n"
            "curl -s http://localhost:8029/slots"
        ),
    },
    {
        "port": 8030,
        "name": "Multi-GPU Orchestrator",
        "title": "Multi-GPU Training Orchestrator",
        "file": "src/training/multi_gpu_orchestrator.py",
        "category": "Core Services",
        "description": (
            "Manages multi-GPU DDP training jobs on OCI BM.GPU.A100.v2 shapes. "
            "Handles torchrun process group setup, per-GPU health checks, "
            "checkpoint synchronisation, and automatic fault recovery. "
            "Achieved 3.07× throughput vs single-GPU baseline."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/jobs",            "Submit a multi-GPU training job"),
            ("GET",  "/jobs/{id}",       "Job status: GPU utilisation, loss, ETA"),
            ("GET",  "/jobs/{id}/logs",  "Streaming log output"),
            ("DELETE", "/jobs/{id}",     "Cancel a running job"),
            ("GET",  "/gpus",            "Real-time per-GPU utilisation"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/training/multi_gpu_orchestrator.py --port 8030\n"
            "curl -s http://localhost:8030/gpus"
        ),
    },
    {
        "port": 8031,
        "name": "Live Demo Scheduler",
        "title": "OCI Robot Cloud — Live Demo Scheduler",
        "file": "src/api/live_demo_scheduler.py",
        "category": "Demo",
        "description": (
            "Calendar-based scheduler for live robot demos. Books OCI GPU capacity "
            "and Jetson hardware slots, coordinates with the GTC live demo (port 8050), "
            "sends pre-demo system checks, and notifies presenters via Slack webhook."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/slots",           "Available demo slots (next 14 days)"),
            ("POST", "/bookings",        "Book a demo slot"),
            ("GET",  "/bookings",        "All upcoming bookings"),
            ("DELETE", "/bookings/{id}", "Cancel a booking"),
            ("GET",  "/preflight/{id}",  "Pre-demo system health check"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/api/live_demo_scheduler.py --port 8031\n"
            "curl -s http://localhost:8031/slots"
        ),
    },
    {
        "port": 8032,
        "name": "Customer Success Dashboard",
        "title": "Customer Success Dashboard",
        "file": "src/api/customer_success_dashboard.py",
        "category": "Partner",
        "description": (
            "CS team dashboard tracking partner health scores, NPS, open support "
            "tickets, upcoming renewals, and escalation flags. Aggregates data "
            "from billing (8017), usage analytics (8027), and feedback tracker (8046)."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",                    "HTML CS dashboard"),
            ("GET", "/partners/health",     "Health score for all partners"),
            ("GET", "/partners/{id}/health","Detailed health breakdown"),
            ("GET", "/alerts",              "Active escalation alerts"),
            ("GET", "/health",              "Service liveness"),
        ],
        "example": (
            "python src/api/customer_success_dashboard.py --port 8032\n"
            "curl -s http://localhost:8032/alerts"
        ),
    },
    {
        "port": 8033,
        "name": "SDK Documentation Server",
        "title": "OCI Robot Cloud SDK Docs",
        "file": "src/api/sdk_documentation_server.py",
        "category": "Partner",
        "description": (
            "Serves auto-generated SDK reference documentation. Extracts docstrings "
            "from the oci-robot-cloud Python SDK, renders them as searchable HTML "
            "with code examples, and provides a live API playground backed by the "
            "mock inference server."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",               "SDK docs landing page"),
            ("GET", "/api/{module}",   "Module reference (HTML)"),
            ("GET", "/search",         "Full-text search: ?q=query"),
            ("GET", "/openapi.json",   "OpenAPI 3.0 spec for the SDK"),
            ("GET", "/health",         "Service liveness"),
        ],
        "example": (
            "python src/api/sdk_documentation_server.py --port 8033\n"
            "curl -s http://localhost:8033/openapi.json | python -m json.tool"
        ),
    },
    {
        "port": 8034,
        "name": "Inference Gateway",
        "title": "OCI Robot Cloud — Inference Gateway",
        "file": "src/api/inference_gateway.py",
        "category": "Core Services",
        "description": (
            "Load-balancing gateway in front of all inference servers. Performs "
            "round-robin or latency-weighted routing to GR00T N1.6 (8001), Franka "
            "(8002), or cached (8009) endpoints. Exposes a single /predict surface "
            "with circuit-breaker and request tracing."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/predict",   "Routed inference predict; auto-selects backend"),
            ("GET",  "/health",    "Gateway and backend health summary"),
            ("GET",  "/metrics",   "Request counts, latency P50/P95, error rate"),
            ("POST", "/config",    "Update routing weights and circuit-breaker thresholds"),
            ("GET",  "/",          "HTML gateway status dashboard"),
        ],
        "example": (
            "python src/api/inference_gateway.py  # hardcoded port 8034\n"
            "curl -s http://localhost:8034/metrics"
        ),
    },
    {
        "port": 8035,
        "name": "Knowledge Base",
        "title": "OCI Robot Cloud Knowledge Base",
        "file": "src/api/knowledge_base.py",
        "category": "Partner",
        "description": (
            "Searchable documentation and troubleshooting knowledge base for "
            "design partners. Articles cover hardware setup, API integration, "
            "dataset formatting, fine-tuning recipes, and common failure modes. "
            "Includes a vector-search endpoint for semantic queries."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/articles",        "List all articles by category"),
            ("GET",  "/articles/{id}",   "Article content (Markdown + HTML)"),
            ("GET",  "/search",          "Keyword search: ?q=query"),
            ("POST", "/search/semantic", "Semantic vector search over article corpus"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/api/knowledge_base.py --port 8035\n"
            "curl 'http://localhost:8035/search?q=franka+joint+limit'"
        ),
    },
    {
        "port": 8036,
        "name": "NVIDIA Integration Tracker",
        "title": "NVIDIA Integration Tracker",
        "file": "src/api/nvidia_integration_tracker.py",
        "category": "Partner",
        "description": (
            "Tracks milestones for the NVIDIA co-engineering partnership. Records "
            "status of deliverables (Isaac Sim integration, Cosmos weights, GTC "
            "talk confirmation, NGC listing) with target dates, owners, and "
            "completion evidence."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/milestones",        "All integration milestones and status"),
            ("PUT",  "/milestones/{id}",   "Update milestone status / evidence"),
            ("GET",  "/summary",           "One-page partnership health summary"),
            ("GET",  "/health",            "Service liveness"),
        ],
        "example": (
            "python src/api/nvidia_integration_tracker.py --port 8036\n"
            "curl -s http://localhost:8036/summary"
        ),
    },
    {
        "port": 8037,
        "name": "Auto SDG Pipeline",
        "title": "Auto SDG Pipeline",
        "file": "src/training/auto_sdg_pipeline.py",
        "category": "Core Services",
        "description": (
            "Fully automated Synthetic Data Generation pipeline. Orchestrates "
            "Genesis simulation scene building, IK motion planning, domain "
            "randomisation, Cosmos augmentation, and export to LeRobot HDF5. "
            "A single POST generates thousands of diverse training episodes."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/generate",        "Start SDG job; params: scene, n_episodes, DR"),
            ("GET",  "/jobs/{id}",       "Job status with per-stage progress"),
            ("GET",  "/jobs",            "Recent SDG jobs"),
            ("GET",  "/",               "HTML pipeline dashboard"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/training/auto_sdg_pipeline.py --port 8037 --mock\n"
            "curl -s -X POST http://localhost:8037/generate -d '{\"n_episodes\":100}'"
        ),
    },
    {
        "port": 8038,
        "name": "Fine-tune Cost Estimator",
        "title": "OCI Robot Cloud — Fine-tune Cost Estimator",
        "file": "src/api/finetune_cost_estimator.py",
        "category": "Infrastructure",
        "description": (
            "Detailed fine-tuning cost breakdown before job submission. Models "
            "GPU-hour costs across BM.GPU shapes, estimates wall-clock time from "
            "throughput benchmarks, and compares OCI vs GCP vs AWS pricing. "
            "Includes per-step and per-episode cost projections."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/estimate",       "Cost estimate; query: steps, gpus, shape, region"),
            ("GET",  "/compare",        "Multi-cloud cost comparison table"),
            ("GET",  "/benchmarks",     "Throughput benchmarks by GPU shape"),
            ("GET",  "/health",         "Service liveness"),
        ],
        "example": (
            "python src/api/finetune_cost_estimator.py --serve --port 8038\n"
            "curl 'http://localhost:8038/estimate?steps=5000&gpus=4&shape=A100'"
        ),
    },
    {
        "port": 8039,
        "name": "Partner Support Portal",
        "title": "OCI Robot Cloud Partner Support Portal",
        "file": "src/api/partner_support_portal.py",
        "category": "Partner",
        "description": (
            "Ticketing and escalation portal for design partners. Partners submit "
            "support tickets tagged by category (infra, training, inference, "
            "billing). CS team triages, assigns, and resolves via the admin UI. "
            "SLA response-time tracking enforced."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/tickets",           "List tickets (partner-scoped or all for admin)"),
            ("POST",   "/tickets",           "Submit a new support ticket"),
            ("GET",    "/tickets/{id}",      "Ticket detail with thread"),
            ("POST",   "/tickets/{id}/reply","Reply to ticket"),
            ("PUT",    "/tickets/{id}/status","Update ticket status"),
            ("GET",    "/health",            "Service liveness"),
        ],
        "example": (
            "python src/api/partner_support_portal.py --port 8039\n"
            "curl -s http://localhost:8039/tickets"
        ),
    },
    {
        "port": 8040,
        "name": "Multi-Run Eval Dashboard",
        "title": "Multi-Run Eval Dashboard",
        "file": "src/eval/multi_run_dashboard.py",
        "category": "Evaluation",
        "description": (
            "Aggregates results from multiple evaluation runs into a sortable "
            "leaderboard. Plots success rate, action MAE, and inference latency "
            "across checkpoints and DAgger iterations. Supports filtering by "
            "task, embodiment, and date range."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",            "HTML leaderboard dashboard"),
            ("GET",  "/runs",        "All eval runs with summary metrics"),
            ("POST", "/runs",        "Register a completed eval run"),
            ("GET",  "/runs/{id}",   "Full run detail with per-episode breakdown"),
            ("GET",  "/health",      "Service liveness"),
        ],
        "example": (
            "python src/eval/multi_run_dashboard.py --port 8040\n"
            "curl -s http://localhost:8040/runs"
        ),
    },
    {
        "port": 8041,
        "name": "Experiment Planner",
        "title": "OCI Robot Cloud — Experiment Planner",
        "file": "src/api/experiment_planner.py",
        "category": "Evaluation",
        "description": (
            "Hyperparameter experiment planning tool. Generates experiment grids "
            "from a YAML config (LR, batch size, LoRA rank, DAgger iterations), "
            "estimates total compute cost via port 8038, submits to the "
            "multi-GPU orchestrator (8030), and tracks results in the experiment "
            "tracker (8019)."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/plans",           "Create an experiment plan from config YAML"),
            ("GET",  "/plans/{id}",      "Plan status: queued / running / done experiments"),
            ("GET",  "/plans",           "All experiment plans"),
            ("GET",  "/health",          "Service liveness"),
        ],
        "example": (
            "python src/api/experiment_planner.py --port 8041\n"
            "curl -s http://localhost:8041/plans"
        ),
    },
    {
        "port": 8042,
        "name": "ROI Calculator",
        "title": "ROI Calculator",
        "file": "src/api/roi_calculator.py",
        "category": "Infrastructure",
        "description": (
            "Customer-facing ROI calculator. Takes inputs (robot count, task type, "
            "current success rate, target success rate, labour cost) and computes "
            "projected payback period, 3-year NPV, and cost-per-task improvement. "
            "Used in sales motions and partner onboarding."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",         "HTML ROI calculator form"),
            ("POST", "/calculate","JSON ROI calculation"),
            ("GET",  "/examples", "Pre-filled industry vertical examples"),
            ("GET",  "/health",   "Service liveness"),
        ],
        "example": (
            "python src/api/roi_calculator.py --port 8042\n"
            "curl -s http://localhost:8042/examples"
        ),
    },
    {
        "port": 8043,
        "name": "Model Monitoring",
        "title": "Model Monitoring",
        "file": "src/api/model_monitoring.py",
        "category": "Infrastructure",
        "description": (
            "Production model drift and performance monitoring. Tracks inference "
            "output distributions over time and alerts on statistical drift from "
            "the training distribution. Integrates with the auto-retrain trigger "
            "to schedule retraining when drift exceeds configured thresholds."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/drift",              "Current drift scores per model and feature"),
            ("GET",  "/alerts",             "Active drift alerts"),
            ("POST", "/baseline",           "Set a new distribution baseline"),
            ("GET",  "/dashboard",          "HTML monitoring dashboard"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/model_monitoring.py --port 8043\n"
            "curl -s http://localhost:8043/drift"
        ),
    },
    {
        "port": 8044,
        "name": "Data Marketplace",
        "title": "OCI Robot Cloud — Data Marketplace",
        "file": "src/api/data_marketplace.py",
        "category": "Partner",
        "description": (
            "Marketplace for sharing and licensing robot demonstration datasets "
            "across design partners. Partners list datasets with quality scores, "
            "task tags, and licensing terms. Buyers purchase access; revenue is "
            "split between contributor and OCI platform."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/listings",           "Browse dataset marketplace"),
            ("POST", "/listings",           "List a dataset for sale"),
            ("GET",  "/listings/{id}",      "Dataset details and preview"),
            ("POST", "/listings/{id}/buy",  "Purchase access to a dataset"),
            ("GET",  "/my/purchases",       "Datasets purchased by current partner"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/data_marketplace.py --port 8044\n"
            "curl -s http://localhost:8044/listings"
        ),
    },
    {
        "port": 8045,
        "name": "Telemetry Collector",
        "title": "Telemetry Collector",
        "file": "src/api/telemetry_collector.py",
        "category": "Infrastructure",
        "description": (
            "Collects structured telemetry from all platform services: request "
            "counts, error rates, latency histograms, GPU memory, and custom "
            "business events. Stores in time-series format and forwards to the "
            "analytics dashboard (8026) and SLA monitor (8022)."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/events",        "Ingest telemetry event batch"),
            ("GET",  "/metrics",       "Query metrics by service and time range"),
            ("GET",  "/summary",       "24-hour platform summary stats"),
            ("GET",  "/health",        "Service liveness"),
        ],
        "example": (
            "python src/api/telemetry_collector.py --port 8045\n"
            "curl -s http://localhost:8045/summary"
        ),
    },
    {
        "port": 8046,
        "name": "Partner Feedback Tracker",
        "title": "Partner Feedback Tracker",
        "file": "src/api/partner_feedback_tracker.py",
        "category": "Partner",
        "description": (
            "Structured feedback collection from design partners. Captures NPS "
            "survey responses, feature requests, bug reports, and qualitative "
            "interview notes. Tags items by product area and priority for "
            "roadmap planning."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/feedback",           "Submit feedback item"),
            ("GET",  "/feedback",           "Browse feedback (filterable by tag/priority)"),
            ("GET",  "/feedback/{id}",      "Feedback item detail"),
            ("PUT",  "/feedback/{id}/tag",  "Add tag or priority"),
            ("GET",  "/nps/summary",        "NPS score trend"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/partner_feedback_tracker.py --port 8046\n"
            "curl -s http://localhost:8046/nps/summary"
        ),
    },
    {
        "port": 8047,
        "name": "Real-Time Policy Visualiser",
        "title": "GR00T Real-Time Policy Visualization",
        "file": "src/eval/realtime_policy_viz.py",
        "category": "Evaluation",
        "description": (
            "Visualises live inference in real time. Reads action chunks from the "
            "GR00T server (8001/8002) and renders joint trajectories, end-effector "
            "paths, and attention heatmaps as animated SVG in the browser. "
            "Used for debugging and live demo presentations."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",          "HTML real-time visualisation dashboard"),
            ("GET", "/frames",    "SSE stream of latest rendered frames"),
            ("GET", "/actions",   "Latest raw action chunk JSON"),
            ("GET", "/health",    "Service liveness"),
        ],
        "example": (
            "python src/eval/realtime_policy_viz.py --port 8047\n"
            "# Point inference at port 8001 and open http://localhost:8047"
        ),
    },
    {
        "port": 8048,
        "name": "GR00T Fine-tune API v2",
        "title": "GR00T Fine-tune API v2",
        "file": "src/api/finetune_api_v2.py",
        "category": "Core Services",
        "description": (
            "Second-generation fine-tuning REST API with full job lifecycle "
            "management. Supports full fine-tune, LoRA, and DAgger jobs. "
            "Provides live log streaming, cost tracking per job, and automatic "
            "checkpoint registration to the model registry (8009)."
        ),
        "mock": True,
        "endpoints": [
            ("GET",    "/",                 "HTML job manager dashboard"),
            ("GET",    "/health",           "Service liveness"),
            ("POST",   "/jobs",             "Submit fine-tune job (full / LoRA / DAgger)"),
            ("GET",    "/jobs",             "List all jobs with status"),
            ("GET",    "/jobs/{id}",        "Job detail: config, progress, cost"),
            ("DELETE", "/jobs/{id}",        "Cancel a running job"),
            ("GET",    "/jobs/{id}/logs",   "Streaming log output"),
            ("GET",    "/api/costs",        "Per-job cost breakdown"),
        ],
        "example": (
            "python src/api/finetune_api_v2.py --port 8048 --mock\n"
            "curl -s -X POST http://localhost:8048/jobs \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\"type\":\"lora\",\"dataset\":\"/tmp/dataset\",\"steps\":5000}'"
        ),
    },
    {
        "port": 8049,
        "name": "Customer Onboarding Checklist",
        "title": "Customer Onboarding Checklist",
        "file": "src/api/customer_onboarding_checklist.py",
        "category": "Partner",
        "description": (
            "Tracks completion of onboarding milestones for new customers. "
            "Each customer has a checklist: account creation, hardware setup, "
            "first dataset upload, first successful inference call, and first "
            "fine-tune completion. CS team monitors all customers from the admin view."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/customers",               "All customers and checklist completion %"),
            ("GET",  "/customers/{id}/checklist","Full checklist for a customer"),
            ("POST", "/customers/{id}/check/{n}","Mark a checklist item complete"),
            ("GET",  "/health",                  "Service liveness"),
        ],
        "example": (
            "python src/api/customer_onboarding_checklist.py  # port 8049 hardcoded\n"
            "curl -s http://localhost:8049/customers"
        ),
    },
    {
        "port": 8050,
        "name": "GTC 2027 Q&A Server",
        "title": "GTC 2027 Q&A Server",
        "file": "src/demo/gtc_qna_server.py",
        "category": "Demo",
        "description": (
            "Live Q&A session management for the GTC 2027 talk. Audience members "
            "submit questions via QR code; presenter sees a moderated queue ranked "
            "by votes. Supports pre-loaded FAQ answers and can display answers on "
            "the presentation screen via WebSocket broadcast."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",              "Audience question submission form"),
            ("POST", "/questions",     "Submit a question"),
            ("GET",  "/questions",     "Moderator: sorted question queue"),
            ("POST", "/questions/{id}/vote", "Upvote a question"),
            ("GET",  "/live",          "Presenter WebSocket feed"),
            ("GET",  "/health",        "Service liveness"),
        ],
        "example": (
            "python src/demo/gtc_qna_server.py --port 8050\n"
            "# Share http://localhost:8050 QR code with audience"
        ),
    },
    {
        "port": 8051,
        "name": "Model Versioning API",
        "title": "OCI Robot Cloud — Model Version Management API",
        "file": "src/api/model_versioning_api.py",
        "category": "Infrastructure",
        "description": (
            "Manages model version lineage across the full fine-tuning history. "
            "Tracks parent–child checkpoint relationships, metadata (training config, "
            "eval results, data provenance), blue-green deployment rollout, and "
            "rollback. Powers the model registry dashboard."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/models",                      "All model lineages"),
            ("POST", "/models",                      "Register a new model version"),
            ("GET",  "/models/{id}",                 "Model version detail with lineage graph"),
            ("POST", "/models/{id}/promote",         "Promote to staging or production"),
            ("POST", "/models/{id}/rollback",        "Rollback to a previous version"),
            ("GET",  "/models/{id}/diff",            "Diff two model versions' eval metrics"),
            ("GET",  "/health",                      "Service liveness"),
        ],
        "example": (
            "python src/api/model_versioning_api.py  # port 8051 hardcoded\n"
            "curl -s http://localhost:8051/models"
        ),
    },
    {
        "port": 8052,
        "name": "Training Notifier",
        "title": "OCI Robot Cloud — Training Notifier",
        "file": "src/api/training_notifier.py",
        "category": "Infrastructure",
        "description": (
            "Sends notifications when training events occur: job start/complete, "
            "loss plateau detection, checkpoint saved, eval score improved, "
            "and GPU OOM errors. Dispatches via Slack webhook, email, and "
            "the webhook notification service (8021)."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/notify",            "Trigger a notification event"),
            ("GET",  "/subscriptions",     "List notification subscriptions"),
            ("POST", "/subscriptions",     "Create a subscription (channel + event type)"),
            ("DELETE", "/subscriptions/{id}", "Remove a subscription"),
            ("GET",  "/history",           "Recent notification history"),
            ("GET",  "/health",            "Service liveness"),
        ],
        "example": (
            "python src/api/training_notifier.py --port 8052\n"
            "curl -s http://localhost:8052/subscriptions"
        ),
    },
    {
        "port": 8053,
        "name": "API Key Manager",
        "title": "OCI Robot Cloud — API Key Manager",
        "file": "src/api/api_key_manager.py",
        "category": "Infrastructure",
        "description": (
            "Issues, rotates, and revokes API keys for design partners. Keys are "
            "scoped to allowed endpoints (inference / training / data) with "
            "configurable rate limits. Integrates with the multi-tenant manager "
            "(8023) for per-key quota enforcement."
        ),
        "mock": False,
        "endpoints": [
            ("GET",    "/keys",            "List API keys for a partner"),
            ("POST",   "/keys",            "Issue a new API key with scope and limits"),
            ("DELETE", "/keys/{id}",       "Revoke an API key"),
            ("POST",   "/keys/{id}/rotate","Rotate (reissue) an API key"),
            ("GET",    "/keys/{id}/usage", "Per-key request count and quota remaining"),
            ("GET",    "/health",          "Service liveness"),
        ],
        "example": (
            "python src/api/api_key_manager.py  # port 8053 hardcoded\n"
            "curl -s http://localhost:8053/keys?partner=acme"
        ),
    },
    {
        "port": 8054,
        "name": "Health Aggregator",
        "title": "Health Aggregator",
        "file": "src/api/health_aggregator.py",
        "category": "Infrastructure",
        "description": (
            "Single pane of glass for platform health. Polls /health on all "
            "registered services (ports 8001–8059), aggregates results into an "
            "overall status page, and exposes a Prometheus-compatible /metrics "
            "endpoint for Grafana dashboards."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/health",   "Overall platform health (aggregated)"),
            ("GET", "/services", "Per-service health status JSON"),
            ("GET", "/metrics",  "Prometheus text format metrics"),
            ("GET", "/",         "HTML status page with service grid"),
        ],
        "example": (
            "python src/api/health_aggregator.py --serve  # port 8054 hardcoded\n"
            "curl -s http://localhost:8054/services"
        ),
    },
    {
        "port": 8055,
        "name": "Contract Generator",
        "title": "OCI Robot Cloud Contract Generator",
        "file": "src/api/contract_generator.py",
        "category": "Partner",
        "description": (
            "Auto-generates design partner and commercial contracts. Takes partner "
            "tier, committed GPU-hours, pricing schedule, and SLA terms as inputs "
            "and produces a DocX/PDF contract from an Oracle-approved template. "
            "Routes for legal review and e-signature via webhook."
        ),
        "mock": False,
        "endpoints": [
            ("POST", "/contracts",          "Generate a contract from template + inputs"),
            ("GET",  "/contracts",          "List all contracts by status"),
            ("GET",  "/contracts/{id}",     "Contract detail and download URL"),
            ("POST", "/contracts/{id}/send","Send for e-signature"),
            ("GET",  "/templates",          "Available contract templates"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/contract_generator.py --serve --port 8055\n"
            "curl -s http://localhost:8055/templates"
        ),
    },
    {
        "port": 8056,
        "name": "Revenue Dashboard",
        "title": "OCI Robot Cloud Revenue Dashboard",
        "file": "src/api/revenue_dashboard.py",
        "category": "Infrastructure",
        "description": (
            "Executive revenue dashboard. Shows MRR, ARR, GPU-hour revenue, "
            "partner count by tier, churn indicators, and pipeline projections. "
            "Data sourced from billing (8017) and usage analytics (8027). "
            "Role-gated to Oracle executive access."
        ),
        "mock": False,
        "endpoints": [
            ("GET", "/",            "HTML executive revenue dashboard"),
            ("GET", "/metrics",     "Revenue KPIs: MRR, ARR, growth, churn"),
            ("GET", "/breakdown",   "Revenue breakdown by partner tier and region"),
            ("GET", "/forecast",    "3-month revenue forecast"),
            ("GET", "/health",      "Service liveness"),
        ],
        "example": (
            "python src/api/revenue_dashboard.py --port 8056\n"
            "curl -s http://localhost:8056/metrics"
        ),
    },
    {
        "port": 8057,
        "name": "GTC Talk Timer",
        "title": "GTC 2027 Talk Timer",
        "file": "src/demo/gtc_talk_timer.py",
        "category": "Demo",
        "description": (
            "Presenter-facing countdown timer for the GTC 2027 talk. Displays "
            "current slide, time remaining per section, and overall progress. "
            "Supports auto-advance mode, manual slide control via keyboard, and "
            "a stage-facing display at a configurable secondary URL."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",              "HTML presenter timer view"),
            ("POST", "/advance",       "Advance to next slide/section"),
            ("POST", "/back",          "Go back to previous section"),
            ("POST", "/reset",         "Reset timer to start"),
            ("GET",  "/status",        "Current slide, elapsed, remaining JSON"),
            ("GET",  "/health",        "Service liveness"),
        ],
        "example": (
            "python src/demo/gtc_talk_timer.py --web --port 8057\n"
            "# Open http://localhost:8057 on presenter display"
        ),
    },
    {
        "port": 8058,
        "name": "A/B Test Framework",
        "title": "OCI Robot Cloud — A/B Test Framework",
        "file": "src/eval/ab_test_framework.py",
        "category": "Evaluation",
        "description": (
            "Statistical A/B testing framework for comparing policy variants. "
            "Routes inference requests to two checkpoints according to a "
            "configurable traffic split, collects success/failure outcomes, "
            "and computes statistical significance (Mann-Whitney U, bootstrap CI). "
            "Automatically promotes the winner."
        ),
        "mock": True,
        "endpoints": [
            ("POST", "/experiments",           "Create A/B experiment with checkpoint pair"),
            ("GET",  "/experiments",           "List experiments with interim results"),
            ("GET",  "/experiments/{id}",      "Full results with significance stats"),
            ("POST", "/experiments/{id}/stop", "Stop experiment and promote winner"),
            ("GET",  "/health",                "Service liveness"),
        ],
        "example": (
            "python src/eval/ab_test_framework.py --port 8058\n"
            "curl -s http://localhost:8058/experiments"
        ),
    },
    {
        "port": 8059,
        "name": "NVIDIA Partnership CRM",
        "title": "NVIDIA Partnership CRM",
        "file": "src/api/nvidia_crm.py",
        "category": "Partner",
        "description": (
            "Internal CRM for managing the NVIDIA co-engineering partnership. "
            "Tracks contacts, meeting notes, deliverable commitments, escalation "
            "paths, and co-marketing activities. Integrates with the integration "
            "tracker (8036) for milestone status."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/contacts",           "NVIDIA team contacts"),
            ("POST", "/meetings",           "Log a meeting note"),
            ("GET",  "/meetings",           "Meeting history with NVIDIA"),
            ("GET",  "/deliverables",       "Joint deliverable tracker"),
            ("PUT",  "/deliverables/{id}",  "Update deliverable status"),
            ("GET",  "/health",             "Service liveness"),
        ],
        "example": (
            "python src/api/nvidia_crm.py  # port 8059 hardcoded\n"
            "curl -s http://localhost:8059/deliverables"
        ),
    },
    {
        "port": 8080,
        "name": "OCI Robot Cloud API (Main)",
        "title": "OCI Robot Cloud API",
        "file": "src/api/robot_cloud_api.py",
        "category": "Core Services",
        "description": (
            "Primary customer-facing REST API. Accepts fine-tune job submissions, "
            "returns job status and results, manages deployment of trained models "
            "back to the inference servers, and exposes pricing. This is the "
            "canonical endpoint documented in the public SDK."
        ),
        "mock": False,
        "endpoints": [
            ("GET",  "/",                       "Service info JSON"),
            ("GET",  "/health",                 "Liveness check"),
            ("POST", "/jobs/train",             "Submit a fine-tune job"),
            ("GET",  "/jobs/{job_id}/status",   "Poll job status"),
            ("GET",  "/jobs/{job_id}/results",  "Retrieve completed job results"),
            ("POST", "/jobs/{job_id}/deploy",   "Deploy model to inference server"),
            ("GET",  "/jobs",                   "List all jobs for caller"),
            ("GET",  "/pricing",                "Current GPU pricing table"),
        ],
        "example": (
            "python src/api/robot_cloud_api.py  # port 8080\n"
            "curl -s http://localhost:8080/health\n"
            "curl -s -X POST http://localhost:8080/jobs/train \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\"dataset_path\":\"/tmp/dataset\",\"num_steps\":5000,\"num_gpus\":4}'"
        ),
    },
]

# ---------------------------------------------------------------------------
# CLI scripts reference
# ---------------------------------------------------------------------------

CLI_SCRIPTS = [
    {
        "name": "dagger_train.py",
        "path": "src/training/dagger_train.py",
        "description": "DAgger (Dataset Aggregation) iterative training loop for GR00T closed-loop improvement.",
        "args": [
            ("--server-url", "str", "http://localhost:8002", "GR00T inference server URL"),
            ("--output-dir", "str", "/tmp/dagger_run", "Directory for checkpoints and logs"),
            ("--dagger-iters", "int", "5", "Number of DAgger iterations"),
            ("--episodes-per-iter", "int", "20", "Episodes to collect per iteration"),
            ("--finetune-steps", "int", "500", "Fine-tune steps per iteration"),
            ("--max-steps", "int", "100", "Max sim steps per episode"),
            ("--beta-start", "float", "0.9", "Initial expert mixing coefficient"),
            ("--beta-decay", "float", "0.7", "Beta multiplier per iteration"),
            ("--gpu-id", "int", "4", "CUDA GPU index"),
            ("--base-model", "str", "/tmp/finetune_500_5k/checkpoint-5000", "Starting checkpoint path"),
            ("--dry-run", "flag", "", "Validate config without running"),
        ],
    },
    {
        "name": "lora_finetune.py",
        "path": "src/training/lora_finetune.py",
        "description": "LoRA (Low-Rank Adaptation) fine-tuning for GR00T — lower VRAM, faster iteration than full fine-tune.",
        "args": [
            ("--base-model", "str", "/tmp/finetune_1000_5k/checkpoint-5000", "Base checkpoint to adapt"),
            ("--dataset", "str", "/tmp/sdg_1000_lerobot", "LeRobot-format HDF5 dataset"),
            ("--output-dir", "str", "/tmp/lora_run", "Output directory for LoRA weights"),
            ("--rank", "int", "8", "LoRA rank (r)"),
            ("--alpha", "float", "16.0", "LoRA scaling factor (alpha)"),
            ("--n-steps", "int", "3000", "Training steps"),
            ("--lr", "float", "2e-4", "Learning rate"),
            ("--batch-size", "int", "32", "Batch size"),
            ("--mock", "flag", "", "Use mock model (no GPU required)"),
            ("--merge", "flag", "", "Merge LoRA weights into base model"),
            ("--lora-path", "str", "", "Path to existing LoRA weights (for --merge)"),
            ("--report", "str", "/tmp/lora_report.html", "Output HTML training report"),
            ("--compare-ranks", "flag", "", "Run rank ablation study"),
            ("--seed", "int", "42", "Random seed"),
        ],
    },
    {
        "name": "closed_loop_eval.py",
        "path": "src/eval/closed_loop_eval.py",
        "description": "Runs closed-loop policy evaluation in Genesis/LIBERO simulation, reporting per-episode success rate and action MAE.",
        "args": [
            ("--checkpoint", "str", "", "Checkpoint path (mutually exclusive with --server-url)"),
            ("--server-url", "str", "", "Running inference server URL (mutually exclusive with --checkpoint)"),
            ("--num-episodes", "int", "20", "Number of evaluation episodes"),
            ("--max-steps", "int", "500", "Max steps per episode before timeout"),
            ("--sim-steps-per-action", "int", "2", "Physics steps per action chunk step"),
            ("--gpu-id", "int", "0", "CUDA GPU index"),
            ("--output", "str", "/tmp/eval_results.json", "JSON output path"),
            ("--cuda / --no-cuda", "flag", "", "Enable/disable CUDA"),
            ("--mock", "flag", "", "Mock evaluation (no GPU/sim required)"),
        ],
    },
    {
        "name": "hpo_search.py",
        "path": "src/training/hpo_search.py",
        "description": "Hyperparameter optimisation search using random/grid/Bayesian strategies.",
        "args": [
            ("--strategy", "str", "random", "Search strategy: random | grid | bayesian"),
            ("--n-trials", "int", "20", "Number of HPO trials"),
            ("--budget-hours", "float", "4.0", "Wall-clock budget in hours"),
            ("--output", "str", "/tmp/hpo_results.json", "Results output path"),
            ("--mock", "flag", "", "Mock training (no GPU required)"),
        ],
    },
    {
        "name": "benchmark_throughput.py",
        "path": "src/training/benchmark_throughput.py",
        "description": "Measures training throughput (it/s) across GPU counts and batch sizes.",
        "args": [
            ("--gpus", "int", "1", "Number of GPUs to test"),
            ("--batch-size", "int", "32", "Batch size"),
            ("--steps", "int", "100", "Benchmark steps"),
            ("--output", "str", "/tmp/throughput.json", "Results JSON"),
        ],
    },
    {
        "name": "checkpoint_compare.py",
        "path": "src/eval/checkpoint_compare.py",
        "description": "Side-by-side evaluation of two checkpoints; auto-starts inference servers on ports 8010/8011.",
        "args": [
            ("--ckpt-a", "str", "", "Path to checkpoint A"),
            ("--ckpt-b", "str", "", "Path to checkpoint B"),
            ("--port-a", "int", "8010", "Port for checkpoint A server"),
            ("--port-b", "int", "8011", "Port for checkpoint B server"),
            ("--episodes", "int", "20", "Evaluation episodes per checkpoint"),
            ("--output", "str", "/tmp/compare.json", "Comparison results JSON"),
        ],
    },
    {
        "name": "sim_to_real_gap.py",
        "path": "src/eval/sim_to_real_gap.py",
        "description": "Quantifies the sim-to-real performance gap by comparing simulated vs real-robot eval metrics.",
        "args": [
            ("--sim-results", "str", "", "JSON file with simulation eval results"),
            ("--real-results", "str", "", "JSON file with real-robot eval results"),
            ("--output", "str", "/tmp/gap_report.html", "HTML gap analysis report"),
        ],
    },
    {
        "name": "genesis_sdg.py",
        "path": "src/simulation/genesis_sdg.py",
        "description": "Synthetic Data Generation using Genesis physics simulator with IK motion planning.",
        "args": [
            ("--scene", "str", "lift_cube", "Scene name: lift_cube | stack_blocks | pour_liquid"),
            ("--n-episodes", "int", "1000", "Episodes to generate"),
            ("--output-dir", "str", "/tmp/sdg_dataset", "LeRobot output directory"),
            ("--domain-rand", "flag", "", "Enable domain randomisation"),
            ("--gpu-id", "int", "0", "CUDA GPU for rendering"),
            ("--mock", "flag", "", "Mock generation (no simulator required)"),
        ],
    },
    {
        "name": "jetson_benchmark.py",
        "path": "src/inference/jetson_benchmark.py",
        "description": "Benchmarks GR00T inference performance on Jetson AGX Orin edge devices.",
        "args": [
            ("--server-url", "str", "http://localhost:8002", "GR00T server URL"),
            ("--n-requests", "int", "100", "Number of benchmark requests"),
            ("--model-variant", "str", "full", "Model variant: full | quantized | distilled"),
            ("--output", "str", "/tmp/jetson_bench.json", "Results JSON"),
        ],
    },
    {
        "name": "policy_distillation.py",
        "path": "src/training/policy_distillation.py",
        "description": "Distils a large GR00T policy into a smaller student model for edge deployment.",
        "args": [
            ("--teacher", "str", "", "Teacher checkpoint path"),
            ("--student-size", "str", "small", "Student model size: small | medium"),
            ("--dataset", "str", "", "LeRobot dataset for distillation"),
            ("--steps", "int", "10000", "Distillation steps"),
            ("--output-dir", "str", "/tmp/distilled", "Output checkpoint directory"),
            ("--mock", "flag", "", "Mock distillation"),
        ],
    },
    {
        "name": "results_aggregator.py",
        "path": "src/eval/results_aggregator.py",
        "description": "Aggregates eval results across multiple runs into a unified report with statistics.",
        "args": [
            ("--results-dir", "str", "/tmp/eval_runs", "Directory of JSON eval result files"),
            ("--output", "str", "/tmp/aggregated.json", "Aggregated results JSON"),
            ("--report", "str", "/tmp/agg_report.html", "HTML summary report"),
        ],
    },
    {
        "name": "curriculum_dagger.py",
        "path": "src/training/curriculum_dagger.py",
        "description": "Curriculum-ordered DAgger training: progressively increases task difficulty across iterations.",
        "args": [
            ("--curriculum", "str", "easy_to_hard", "Curriculum strategy: easy_to_hard | hard_first | random"),
            ("--tasks", "str", "lift_cube,stack_blocks", "Comma-separated task list"),
            ("--iters", "int", "10", "Total curriculum iterations"),
            ("--server-url", "str", "http://localhost:8002", "Inference server"),
            ("--output-dir", "str", "/tmp/curriculum_run", "Output directory"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Category order and colours
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "Core Services",
    "Training",
    "Evaluation",
    "Infrastructure",
    "Demo",
    "Partner",
]

CATEGORY_COLORS = {
    "Core Services":  "#3b82f6",  # blue
    "Training":       "#8b5cf6",  # purple
    "Evaluation":     "#f59e0b",  # amber
    "Infrastructure": "#10b981",  # emerald
    "Demo":           "#ef4444",  # red
    "Partner":        "#06b6d4",  # cyan
}

# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def method_badge(method: str) -> str:
    colors = {
        "GET":    "#3b82f6",
        "POST":   "#10b981",
        "PUT":    "#f59e0b",
        "DELETE": "#ef4444",
        "PATCH":  "#8b5cf6",
    }
    bg = colors.get(method.upper(), "#6b7280")
    return (
        f'<span style="background:{bg};color:#fff;font-size:0.68rem;'
        f'font-weight:700;padding:2px 7px;border-radius:4px;'
        f'letter-spacing:.04em;font-family:monospace">{method.upper()}</span>'
    )


def build_sidebar(services: list) -> str:
    by_cat: dict = {c: [] for c in CATEGORY_ORDER}
    for s in services:
        cat = s.get("category", "Core Services")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(s)

    html = '<nav id="sidebar">\n'
    html += '<div id="sidebar-header"><span id="logo">&#x1F916;</span> OCI Robot Cloud</div>\n'
    html += '<div id="search-wrap"><input id="search" placeholder="Search services…" autocomplete="off"></div>\n'
    html += '<ul id="nav-list">\n'

    for cat in CATEGORY_ORDER:
        if not by_cat.get(cat):
            continue
        color = CATEGORY_COLORS.get(cat, "#9ca3af")
        html += (
            f'<li class="nav-category" style="color:{color}">'
            f'{cat}</li>\n'
        )
        for s in by_cat[cat]:
            html += (
                f'<li><a class="nav-link" href="#svc-{s["port"]}" '
                f'data-name="{s["name"].lower()}" '
                f'data-port="{s["port"]}" '
                f'data-desc="{s["description"][:80].lower()}">'
                f'<span class="nav-port">{s["port"]}</span>'
                f'<span class="nav-name">{s["name"]}</span>'
                f'</a></li>\n'
            )

    html += "</ul>\n"

    # Quick-reference card
    html += '<div id="quick-ref">\n'
    html += '<div class="qr-title">Quick Reference</div>\n'
    for s in sorted(services, key=lambda x: x["port"]):
        html += (
            f'<div class="qr-row" data-port="{s["port"]}">'
            f'<span class="qr-port">{s["port"]}</span>'
            f'<span class="qr-name">{s["name"]}</span>'
            f'</div>\n'
        )
    html += "</div>\n"
    html += "</nav>\n"
    return html


def build_service_card(s: dict) -> str:
    port = s["port"]
    name = s["name"]
    cat = s.get("category", "Core Services")
    cat_color = CATEGORY_COLORS.get(cat, "#9ca3af")
    mock_badge = (
        '<span class="mock-badge">MOCK SUPPORTED</span>'
        if s.get("mock") else ""
    )

    # Endpoint table
    ep_rows = ""
    for method, path, desc in s.get("endpoints", []):
        ep_rows += (
            f'<tr>'
            f'<td>{method_badge(method)}</td>'
            f'<td><code>{path}</code></td>'
            f'<td class="ep-desc">{desc}</td>'
            f'</tr>\n'
        )

    ep_table = ""
    if ep_rows:
        ep_table = (
            '<div class="section-label">Endpoints</div>'
            '<table class="ep-table">'
            '<thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>'
            f'<tbody>{ep_rows}</tbody>'
            '</table>'
        )

    # Example block
    example_html = ""
    if s.get("example"):
        escaped = s["example"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        example_html = (
            '<div class="section-label">Example</div>'
            f'<pre class="code-block">{escaped}</pre>'
        )

    html = f"""
<section id="svc-{port}" class="svc-card">
  <div class="svc-header">
    <div class="svc-title-row">
      <span class="svc-port">:{port}</span>
      <h2 class="svc-name">{name}</h2>
      {mock_badge}
      <span class="cat-badge" style="background:{cat_color}22;color:{cat_color};border:1px solid {cat_color}44">{cat}</span>
    </div>
    <div class="svc-file"><code>{s.get("file","")}</code></div>
  </div>
  <p class="svc-desc">{s["description"]}</p>
  {ep_table}
  {example_html}
</section>
"""
    return html


def build_cli_card(script: dict) -> str:
    rows = ""
    for flag, typ, default, desc in script.get("args", []):
        default_str = f'<span class="arg-default">(default: {default})</span>' if default else ""
        rows += (
            f'<tr>'
            f'<td><code class="arg-flag">{flag}</code></td>'
            f'<td><span class="arg-type">{typ}</span></td>'
            f'<td>{desc} {default_str}</td>'
            f'</tr>\n'
        )

    table = (
        '<table class="ep-table">'
        '<thead><tr><th>Flag</th><th>Type</th><th>Description</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    ) if rows else ""

    html = f"""
<section class="svc-card cli-card">
  <div class="svc-header">
    <div class="svc-title-row">
      <h2 class="svc-name">{script["name"]}</h2>
    </div>
    <div class="svc-file"><code>{script["path"]}</code></div>
  </div>
  <p class="svc-desc">{script["description"]}</p>
  <div class="section-label">Arguments</div>
  {table}
</section>
"""
    return html


def build_html(services: list, cli_scripts: list, output_path: str) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(services)

    sidebar = build_sidebar(services)

    # Group service cards by category
    by_cat: dict = {c: [] for c in CATEGORY_ORDER}
    for s in services:
        cat = s.get("category", "Core Services")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(s)

    cards_html = ""
    for cat in CATEGORY_ORDER:
        svcs = by_cat.get(cat, [])
        if not svcs:
            continue
        color = CATEGORY_COLORS.get(cat, "#9ca3af")
        cards_html += (
            f'<div class="category-divider" style="border-left:4px solid {color}">'
            f'<span style="color:{color}">{cat}</span>'
            f'<span class="cat-count">{len(svcs)} service{"s" if len(svcs)!=1 else ""}</span>'
            f'</div>\n'
        )
        for s in svcs:
            cards_html += build_service_card(s)

    cli_html = ""
    for script in cli_scripts:
        cli_html += build_cli_card(script)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — API Reference</title>
<style>
  :root {{
    --bg:       #0f172a;
    --surface:  #1e293b;
    --surface2: #273449;
    --border:   #334155;
    --text:     #e2e8f0;
    --muted:    #94a3b8;
    --accent:   #3b82f6;
    --code-bg:  #111827;
    --sidebar-w: 280px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    display: flex;
    min-height: 100vh;
  }}

  /* ── Sidebar ──────────────────────────────────────────────── */
  #sidebar {{
    width: var(--sidebar-w);
    min-width: var(--sidebar-w);
    background: var(--surface);
    border-right: 1px solid var(--border);
    height: 100vh;
    position: sticky;
    top: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0;
  }}
  #sidebar-header {{
    padding: 16px;
    font-size: 1rem;
    font-weight: 700;
    color: #f1f5f9;
    border-bottom: 1px solid var(--border);
    background: var(--surface2);
    letter-spacing: .02em;
  }}
  #logo {{ margin-right: 8px; font-size: 1.2rem; }}
  #search-wrap {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
  }}
  #search {{
    width: 100%;
    background: var(--code-bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
  }}
  #search:focus {{ outline: 2px solid var(--accent); }}
  #nav-list {{
    list-style: none;
    padding: 8px 0;
    flex: 1;
  }}
  .nav-category {{
    padding: 8px 14px 4px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
  }}
  .nav-link {{
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 4px 14px;
    text-decoration: none;
    color: var(--muted);
    border-left: 3px solid transparent;
    transition: all .15s;
    font-size: 12px;
  }}
  .nav-link:hover {{
    color: var(--text);
    background: var(--surface2);
    border-left-color: var(--accent);
  }}
  .nav-port {{
    font-family: monospace;
    font-size: 11px;
    color: var(--accent);
    min-width: 36px;
  }}
  .nav-name {{ flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  /* ── Quick-reference card ─────────────────────────────────── */
  #quick-ref {{
    border-top: 1px solid var(--border);
    padding: 10px 0 16px;
    background: var(--code-bg);
  }}
  .qr-title {{
    padding: 8px 14px 4px;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .qr-row {{
    display: flex;
    gap: 8px;
    padding: 2px 14px;
    font-size: 11px;
  }}
  .qr-port {{
    font-family: monospace;
    color: var(--accent);
    min-width: 38px;
  }}
  .qr-name {{ color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  /* ── Main content ─────────────────────────────────────────── */
  #main {{
    flex: 1;
    overflow-y: auto;
    padding: 0 0 80px;
  }}
  #page-header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 40px 28px;
  }}
  #page-header h1 {{
    font-size: 1.7rem;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 6px;
  }}
  #page-header .subtitle {{
    color: var(--muted);
    font-size: .9rem;
  }}
  #page-header .stats {{
    margin-top: 14px;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }}
  .stat-chip {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 12px;
    color: var(--muted);
  }}
  .stat-chip strong {{ color: var(--text); }}

  #content {{ padding: 0 40px; }}

  /* ── Section divider ──────────────────────────────────────── */
  .category-divider {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 24px 0 8px;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: .02em;
    padding-left: 12px;
    margin-bottom: 4px;
    border-radius: 4px;
  }}
  .cat-count {{ font-size: .75rem; color: var(--muted); font-weight: 400; }}

  /* ── Service cards ────────────────────────────────────────── */
  .svc-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 22px 24px;
    margin-bottom: 18px;
    transition: border-color .2s;
  }}
  .svc-card:hover {{ border-color: #475569; }}
  .svc-card.hidden {{ display: none; }}

  .svc-header {{ margin-bottom: 12px; }}
  .svc-title-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }}
  .svc-port {{
    font-family: monospace;
    font-size: 1rem;
    font-weight: 700;
    color: var(--accent);
    background: #1e3a5f;
    padding: 2px 8px;
    border-radius: 5px;
  }}
  .svc-name {{
    font-size: 1.05rem;
    font-weight: 700;
    color: #f1f5f9;
  }}
  .svc-file {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .svc-file code {{ font-size: 11px; }}

  .mock-badge {{
    background: #14532d;
    color: #86efac;
    border: 1px solid #166534;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: .05em;
  }}
  .cat-badge {{
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 12px;
    letter-spacing: .03em;
  }}
  .svc-desc {{
    color: var(--muted);
    margin-bottom: 16px;
    line-height: 1.7;
  }}

  /* ── Tables ───────────────────────────────────────────────── */
  .section-label {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
    margin-top: 16px;
  }}
  .ep-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    margin-bottom: 4px;
  }}
  .ep-table th {{
    background: var(--surface2);
    text-align: left;
    padding: 6px 10px;
    color: var(--muted);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
  }}
  .ep-table td {{
    padding: 6px 10px;
    border-bottom: 1px solid #1e293b;
    vertical-align: top;
  }}
  .ep-table tr:last-child td {{ border-bottom: none; }}
  .ep-table tr:hover td {{ background: var(--surface2); }}
  .ep-desc {{ color: var(--muted); }}
  .ep-table code {{
    font-family: "JetBrains Mono", "Fira Mono", Consolas, monospace;
    font-size: 11.5px;
    color: #a5f3fc;
  }}

  /* ── Code blocks ──────────────────────────────────────────── */
  .code-block {{
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    font-family: "JetBrains Mono", "Fira Mono", Consolas, monospace;
    font-size: 12px;
    color: #a5f3fc;
    overflow-x: auto;
    white-space: pre;
    margin-top: 8px;
  }}

  /* ── CLI section ──────────────────────────────────────────── */
  #cli-section {{ margin-top: 32px; }}
  #cli-section h2 {{
    font-size: 1.2rem;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 16px;
    padding-left: 12px;
    border-left: 4px solid #8b5cf6;
  }}
  .cli-card {{ border-left: 3px solid #8b5cf6; }}
  .arg-flag {{ color: #86efac; font-size: 12px; }}
  .arg-type {{
    background: #1e293b;
    color: #f59e0b;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    font-family: monospace;
  }}
  .arg-default {{ color: #475569; font-size: 11px; }}

  /* ── Footer ───────────────────────────────────────────────── */
  #footer {{
    text-align: center;
    color: var(--muted);
    font-size: 11px;
    padding: 32px;
    border-top: 1px solid var(--border);
    margin-top: 40px;
  }}

  /* ── Scrollbar ────────────────────────────────────────────── */
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
</style>
</head>
<body>

{sidebar}

<div id="main">
  <div id="page-header">
    <h1>OCI Robot Cloud — API Reference</h1>
    <p class="subtitle">Complete endpoint and CLI reference for the OCI Robot Cloud platform</p>
    <div class="stats">
      <div class="stat-chip"><strong>{total}</strong> services documented</div>
      <div class="stat-chip">Ports <strong>8000</strong> – <strong>8080</strong></div>
      <div class="stat-chip"><strong>{len(cli_scripts)}</strong> CLI scripts</div>
      <div class="stat-chip">Generated <strong>{now}</strong></div>
    </div>
  </div>

  <div id="content">
    {cards_html}

    <div id="cli-section">
      <h2>CLI Reference</h2>
      {cli_html}
    </div>

    <div id="footer">
      OCI Robot Cloud &middot; Internal reference &middot; Generated {now}
    </div>
  </div>
</div>

<script>
// ── Client-side search ────────────────────────────────────────────────────────
(function() {{
  const input = document.getElementById('search');
  const navLinks = document.querySelectorAll('.nav-link');
  const qrRows = document.querySelectorAll('.qr-row');
  const cards = document.querySelectorAll('.svc-card:not(.cli-card)');
  const dividers = document.querySelectorAll('.category-divider');

  input.addEventListener('input', () => {{
    const q = input.value.toLowerCase().trim();
    if (!q) {{
      navLinks.forEach(l => l.closest('li').style.display = '');
      qrRows.forEach(r => r.style.display = '');
      cards.forEach(c => c.classList.remove('hidden'));
      dividers.forEach(d => d.style.display = '');
      return;
    }}

    // Filter nav links
    navLinks.forEach(link => {{
      const matches = (
        link.dataset.name.includes(q) ||
        link.dataset.port.includes(q) ||
        link.dataset.desc.includes(q)
      );
      link.closest('li').style.display = matches ? '' : 'none';
    }});

    // Filter quick-ref
    qrRows.forEach(row => {{
      const name = row.querySelector('.qr-name').textContent.toLowerCase();
      row.style.display = (name.includes(q) || row.dataset.port.includes(q)) ? '' : 'none';
    }});

    // Filter service cards
    cards.forEach(card => {{
      const text = card.textContent.toLowerCase();
      card.classList.toggle('hidden', !text.includes(q));
    }});

    // Show/hide category dividers based on whether any card in their group is visible
    dividers.forEach(div => {{
      // Find following sibling cards until next divider
      let el = div.nextElementSibling;
      let anyVisible = false;
      while (el && !el.classList.contains('category-divider')) {{
        if (el.classList.contains('svc-card') && !el.classList.contains('hidden')) {{
          anyVisible = true;
        }}
        el = el.nextElementSibling;
      }}
      div.style.display = anyVisible ? '' : 'none';
    }});
  }});

  // Highlight active nav link on scroll
  const allSections = document.querySelectorAll('section[id^="svc-"]');
  const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
      if (entry.isIntersecting) {{
        const id = entry.target.id;
        navLinks.forEach(l => {{
          const active = l.getAttribute('href') === '#' + id;
          l.style.borderLeftColor = active ? 'var(--accent)' : 'transparent';
          l.style.color = active ? 'var(--text)' : '';
        }});
      }}
    }});
  }}, {{ threshold: 0.3 }});
  allSections.forEach(s => observer.observe(s));
}})();
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate OCI Robot Cloud API reference HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default="docs/API_REFERENCE.html",
        help="Output HTML file path (default: docs/API_REFERENCE.html)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating API reference for {len(SERVICES)} services and {len(CLI_SCRIPTS)} CLI scripts…")
    html = build_html(SERVICES, CLI_SCRIPTS, str(output_path))
    output_path.write_text(html, encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"Written: {output_path}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
