"""
generate_api_docs.py

Generates a unified HTML API reference for all 58 OCI Robot Cloud services
(ports 8001-8058). Each service is linked to its corresponding script in the
roboticsai repository. Output is a self-contained, dark-themed HTML file with
a searchable sidebar and expandable endpoint cards.

Usage:
    python3 generate_api_docs.py --output /tmp/api_reference.html
"""

import argparse
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EndpointDef:
    method: str          # "GET" or "POST"
    path: str
    description: str
    params: Dict[str, str]
    returns: str


@dataclass
class ServiceDef:
    port: int
    name: str
    script_path: str
    description: str
    endpoints: List[EndpointDef]
    status: str          # "live" or "planned"


# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

SERVICES: List[ServiceDef] = [
    ServiceDef(
        port=8001,
        name="groot_franka_server",
        script_path="server/groot_franka_server.py",
        description="Primary GR00T N1.6 inference endpoint for Franka Panda robot actions. "
                    "Accepts vision + language observations and returns 7-DOF joint actions.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/health",    "Liveness probe",
                        {},
                        "{'status': 'ok', 'model': 'GR00T-N1.6', 'latency_ms': float}"),
            EndpointDef("POST", "/predict",   "Run inference: image + instruction -> joint actions",
                        {"image_b64": "base64-encoded RGB frame (str)",
                         "instruction": "natural language task description (str)",
                         "state": "current joint positions, 7-float list"},
                        "{'actions': [[float]*7], 'latency_ms': float}"),
            EndpointDef("GET",  "/model/info","Return loaded model metadata",
                        {},
                        "{'model_id': str, 'param_count': str, 'gpu_memory_gb': float}"),
        ],
    ),
    ServiceDef(
        port=8002,
        name="groot_inference_v2",
        script_path="server/groot_inference_v2.py",
        description="Second-generation GR00T inference service with batching support, "
                    "multi-camera inputs, and proprioceptive state fusion.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/predict",       "Batched multi-camera inference",
                        {"images": "list of base64 frames",
                         "instruction": "str",
                         "proprio": "14-float proprio state"},
                        "{'actions': [[float]*7]*N, 'confidence': float}"),
            EndpointDef("POST", "/predict/stream","Streaming action chunk generation (SSE)",
                        {"image_b64": "str", "instruction": "str"},
                        "Server-sent events: action chunks at 30 Hz"),
            EndpointDef("GET",  "/stats",         "Runtime throughput and GPU utilization stats",
                        {},
                        "{'requests_total': int, 'avg_latency_ms': float, 'gpu_util': float}"),
        ],
    ),
    ServiceDef(
        port=8003,
        name="data_collection_api",
        script_path="server/data_collection_api.py",
        description="REST API for recording robot demonstrations, annotating episodes, "
                    "and exporting LeRobot-format HDF5 datasets.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/episode/start",  "Begin a new demonstration recording session",
                        {"task": "task name (str)", "robot_id": "str"},
                        "{'episode_id': str, 'started_at': ISO8601}"),
            EndpointDef("POST", "/episode/step",   "Append an observation-action step to open episode",
                        {"episode_id": "str", "obs": "dict", "action": "[float]*7"},
                        "{'step_idx': int}"),
            EndpointDef("POST", "/episode/end",    "Finalize and save episode to dataset",
                        {"episode_id": "str", "success": "bool"},
                        "{'episode_id': str, 'steps': int, 'saved_path': str}"),
            EndpointDef("GET",  "/dataset/list",   "List available datasets",
                        {},
                        "{'datasets': [{'name': str, 'episodes': int, 'size_mb': float}]}"),
        ],
    ),
    ServiceDef(
        port=8004,
        name="simulation_bridge",
        script_path="server/simulation_bridge.py",
        description="WebSocket + REST bridge between Genesis/Isaac Sim simulation environments "
                    "and the inference stack.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/sim/status",   "Current simulation state and episode info",
                        {},
                        "{'running': bool, 'episode': int, 'step': int, 'task': str}"),
            EndpointDef("POST", "/sim/reset",    "Reset simulation to initial state",
                        {"task": "str", "seed": "int (optional)"},
                        "{'obs': dict, 'episode_id': str}"),
            EndpointDef("POST", "/sim/step",     "Advance simulation by one control step",
                        {"action": "[float]*7"},
                        "{'obs': dict, 'reward': float, 'done': bool}"),
        ],
    ),
    ServiceDef(
        port=8005,
        name="reward_model_server",
        script_path="server/reward_model_server.py",
        description="Vision-language reward model for online RL and DAgger success labeling.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/score",       "Score an observation-action trajectory",
                        {"frames": "list[base64]", "instruction": "str"},
                        "{'reward': float, 'success': bool, 'rationale': str}"),
            EndpointDef("POST", "/label_batch", "Batch-label a set of episodes for DAgger",
                        {"episode_ids": "list[str]"},
                        "{'labels': {episode_id: bool}}"),
            EndpointDef("GET",  "/model/version","Active reward model version",
                        {},
                        "{'version': str, 'accuracy': float}"),
        ],
    ),
    ServiceDef(
        port=8006,
        name="embodiment_adapter",
        script_path="server/embodiment_adapter.py",
        description="Translates generic GR00T action outputs to robot-specific joint formats "
                    "(Franka, UR5, xArm, Spot).",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/robots",       "List supported robot embodiments",
                        {},
                        "{'robots': [{'id': str, 'dof': int, 'type': str}]}"),
            EndpointDef("POST", "/translate",    "Convert canonical action to robot joint space",
                        {"robot_id": "str", "action": "[float]*7"},
                        "{'joint_positions': list[float], 'gripper': float}"),
            EndpointDef("POST", "/calibrate",    "Update kinematic calibration for a robot",
                        {"robot_id": "str", "calib_data": "dict"},
                        "{'status': 'ok', 'rmse': float}"),
        ],
    ),
    ServiceDef(
        port=8007,
        name="policy_distillation_server",
        script_path="server/policy_distillation_server.py",
        description="Distills large teacher policies into lightweight student models for "
                    "edge deployment on Jetson.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/distill/start",  "Launch a distillation job",
                        {"teacher_checkpoint": "str", "student_arch": "str", "epochs": "int"},
                        "{'job_id': str, 'estimated_minutes': int}"),
            EndpointDef("GET",  "/distill/{job_id}","Poll distillation job status",
                        {"job_id": "path param (str)"},
                        "{'status': str, 'epoch': int, 'kl_loss': float}"),
            EndpointDef("POST", "/distill/{job_id}/export", "Export distilled model to ONNX/TRT",
                        {"format": "onnx|tensorrt"},
                        "{'download_url': str, 'size_mb': float}"),
        ],
    ),
    ServiceDef(
        port=8008,
        name="dataset_versioning_api",
        script_path="server/dataset_versioning_api.py",
        description="Semantic versioning, lineage tracking, and OCI Object Storage sync "
                    "for robot demonstration datasets.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/datasets",           "List all versioned datasets",
                        {},
                        "{'datasets': [{'name': str, 'version': str, 'episodes': int}]}"),
            EndpointDef("POST", "/datasets/{name}/tag","Tag current HEAD with a semantic version",
                        {"version": "semver string", "notes": "str"},
                        "{'tag': str, 'sha': str}"),
            EndpointDef("GET",  "/datasets/{name}/diff","Diff two dataset versions",
                        {"v1": "version str", "v2": "version str"},
                        "{'added': int, 'removed': int, 'changed': int}"),
        ],
    ),
    ServiceDef(
        port=8009,
        name="model_registry_api",
        script_path="server/model_registry_api.py",
        description="Central registry for tracking trained model checkpoints, metrics, "
                    "and deployment status.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/models",             "List all registered models",
                        {},
                        "{'models': [{'id': str, 'task': str, 'mae': float, 'status': str}]}"),
            EndpointDef("POST", "/models/register",    "Register a new checkpoint",
                        {"checkpoint_path": "str", "metrics": "dict", "task": "str"},
                        "{'model_id': str, 'registered_at': ISO8601}"),
            EndpointDef("POST", "/models/{id}/promote","Promote model to production",
                        {"model_id": "path param"},
                        "{'status': 'promoted', 'previous_model': str}"),
        ],
    ),
    ServiceDef(
        port=8010,
        name="dagger_orchestrator",
        script_path="server/dagger_orchestrator.py",
        description="Dataset Aggregation (DAgger) training loop orchestrator: manages "
                    "rollout collection, expert correction, and iterative fine-tuning.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/run/start",    "Start a DAgger training run",
                        {"task": "str", "base_checkpoint": "str", "n_rollouts": "int"},
                        "{'run_id': str, 'iteration': int}"),
            EndpointDef("GET",  "/run/{run_id}", "Get DAgger run status and metrics",
                        {"run_id": "path param"},
                        "{'iteration': int, 'success_rate': float, 'dataset_size': int}"),
            EndpointDef("POST", "/run/{run_id}/correct", "Submit expert correction for a rollout",
                        {"run_id": "str", "rollout_id": "str", "correction": "list[action]"},
                        "{'correction_id': str, 'queued_for_training': bool}"),
            EndpointDef("POST", "/run/{run_id}/stop", "Gracefully stop a DAgger run",
                        {"run_id": "str"},
                        "{'status': 'stopped', 'final_mae': float}"),
        ],
    ),
    ServiceDef(
        port=8011,
        name="curriculum_scheduler",
        script_path="server/curriculum_scheduler.py",
        description="Automatic curriculum learning: schedules task difficulty progression "
                    "based on agent success rate.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/curriculum/current", "Get current task difficulty level",
                        {},
                        "{'level': int, 'task': str, 'success_threshold': float}"),
            EndpointDef("POST", "/curriculum/advance", "Advance curriculum if threshold met",
                        {"current_success_rate": "float"},
                        "{'advanced': bool, 'new_level': int, 'new_task': str}"),
            EndpointDef("GET",  "/curriculum/history", "Curriculum progression history",
                        {},
                        "{'history': [{'level': int, 'achieved_at': ISO8601, 'rate': float}]}"),
        ],
    ),
    ServiceDef(
        port=8012,
        name="hyperparameter_optimizer",
        script_path="server/hyperparameter_optimizer.py",
        description="Bayesian hyperparameter search for fine-tuning GR00T policies.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/search/start",    "Launch HPO search",
                        {"param_space": "dict", "n_trials": "int", "metric": "str"},
                        "{'search_id': str, 'estimated_hours': float}"),
            EndpointDef("GET",  "/search/{id}",     "Get HPO search progress",
                        {"id": "path param"},
                        "{'best_params': dict, 'best_score': float, 'trials_done': int}"),
            EndpointDef("GET",  "/search/{id}/results", "Full trial results table",
                        {},
                        "{'trials': [{'params': dict, 'score': float, 'duration_s': float}]}"),
        ],
    ),
    ServiceDef(
        port=8013,
        name="sim_to_real_validator",
        script_path="server/sim_to_real_validator.py",
        description="Measures sim-to-real transfer gap by comparing policy behavior in "
                    "simulation versus real robot telemetry.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/validate",        "Run sim-to-real comparison for a checkpoint",
                        {"checkpoint": "str", "real_episodes": "list[str]"},
                        "{'sim_success': float, 'real_success': float, 'gap': float}"),
            EndpointDef("GET",  "/report/{run_id}", "Get detailed validation report",
                        {"run_id": "path param"},
                        "{'metrics': dict, 'failure_modes': list[str], 'recommendations': list}"),
            EndpointDef("GET",  "/history",         "Historical sim-to-real gap over checkpoints",
                        {},
                        "{'checkpoints': [{'step': int, 'gap': float}]}"),
        ],
    ),
    ServiceDef(
        port=8014,
        name="teleoperation_collector",
        script_path="server/teleoperation_collector.py",
        description="Real-time teleoperation data collection via SpaceMouse, VR controller, "
                    "or keyboard with live recording.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/session/start",  "Start teleoperation recording session",
                        {"robot_id": "str", "task": "str", "device": "spacemouse|vr|keyboard"},
                        "{'session_id': str, 'stream_url': str}"),
            EndpointDef("POST", "/session/end",    "End session and save to dataset",
                        {"session_id": "str"},
                        "{'steps_recorded': int, 'saved_path': str}"),
            EndpointDef("GET",  "/devices",        "List available teleoperation devices",
                        {},
                        "{'devices': [{'id': str, 'type': str, 'connected': bool}]}"),
        ],
    ),
    ServiceDef(
        port=8015,
        name="safety_monitor",
        script_path="server/safety_monitor.py",
        description="Real-time safety constraint enforcement: joint limits, workspace bounds, "
                    "force torque thresholds, and collision detection.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/check",           "Validate an action against safety constraints",
                        {"robot_id": "str", "action": "[float]*7", "state": "dict"},
                        "{'safe': bool, 'violations': list[str], 'clipped_action': list}"),
            EndpointDef("GET",  "/constraints/{robot_id}", "Get safety constraint profile",
                        {"robot_id": "path param"},
                        "{'joint_limits': dict, 'workspace_bbox': dict, 'max_torque': list}"),
            EndpointDef("POST", "/emergency_stop",  "Trigger emergency stop for a robot",
                        {"robot_id": "str", "reason": "str"},
                        "{'stopped': bool, 'timestamp': ISO8601}"),
        ],
    ),
    ServiceDef(
        port=8016,
        name="continuous_learning_manager",
        script_path="server/continuous_learning_manager.py",
        description="Manages online continual learning: detects distribution shift, "
                    "triggers incremental fine-tuning, and prevents catastrophic forgetting.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/drift/status",    "Check for distribution shift in recent data",
                        {},
                        "{'drift_detected': bool, 'drift_score': float, 'window_hours': int}"),
            EndpointDef("POST", "/retrain/trigger", "Manually trigger an incremental retrain",
                        {"reason": "str", "new_data_path": "str"},
                        "{'job_id': str, 'started_at': ISO8601}"),
            EndpointDef("GET",  "/forgetting/score","Measure catastrophic forgetting on held-out set",
                        {},
                        "{'score': float, 'tasks_affected': list[str]}"),
        ],
    ),
    ServiceDef(
        port=8017,
        name="data_flywheel_api",
        script_path="server/data_flywheel_api.py",
        description="Closed-loop data flywheel: routes failed episodes to expert annotation, "
                    "tracks annotation queue, and kicks off retraining.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/failures/submit", "Submit failed episode for expert review",
                        {"episode_id": "str", "failure_mode": "str"},
                        "{'queue_position': int, 'estimated_review_hours': float}"),
            EndpointDef("GET",  "/queue",           "Current annotation queue status",
                        {},
                        "{'pending': int, 'in_review': int, 'completed_today': int}"),
            EndpointDef("GET",  "/flywheel/stats",  "Flywheel throughput and quality metrics",
                        {},
                        "{'episodes_per_day': float, 'success_rate_trend': list[float]}"),
        ],
    ),
    ServiceDef(
        port=8018,
        name="ab_test_manager",
        script_path="server/ab_test_manager.py",
        description="A/B testing framework for comparing policy checkpoints in deployment.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/experiments/create","Create a new A/B experiment",
                        {"name": "str", "policy_a": "str", "policy_b": "str",
                         "traffic_split": "float"},
                        "{'experiment_id': str, 'started_at': ISO8601}"),
            EndpointDef("GET",  "/experiments/{id}", "Get experiment results and significance",
                        {"id": "path param"},
                        "{'winner': str, 'p_value': float, 'success_a': float, 'success_b': float}"),
            EndpointDef("POST", "/experiments/{id}/conclude", "Conclude experiment and promote winner",
                        {"id": "str"},
                        "{'promoted': str, 'improvement': float}"),
        ],
    ),
    ServiceDef(
        port=8019,
        name="auto_retrain_trigger",
        script_path="server/auto_retrain_trigger.py",
        description="Monitors production success rate and automatically schedules retraining "
                    "when performance drops below configured thresholds.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/thresholds",      "Get current auto-retrain thresholds",
                        {},
                        "{'success_floor': float, 'drift_score_ceiling': float, 'window_hours': int}"),
            EndpointDef("POST", "/thresholds",      "Update auto-retrain thresholds",
                        {"success_floor": "float", "drift_score_ceiling": "float"},
                        "{'updated': bool}"),
            EndpointDef("GET",  "/triggers/recent", "Recent trigger events and outcomes",
                        {},
                        "{'triggers': [{'at': ISO8601, 'reason': str, 'job_id': str}]}"),
        ],
    ),
    ServiceDef(
        port=8020,
        name="pipeline_orchestrator",
        script_path="server/pipeline_orchestrator.py",
        description="End-to-end pipeline orchestration: SDG -> dataset prep -> fine-tuning -> "
                    "eval -> registry promotion.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/pipeline/run",    "Launch a full training pipeline",
                        {"task": "str", "n_demos": "int", "eval_episodes": "int"},
                        "{'pipeline_id': str, 'stages': list[str]}"),
            EndpointDef("GET",  "/pipeline/{id}",   "Get pipeline status by stage",
                        {"id": "path param"},
                        "{'current_stage': str, 'stages': {str: {'status': str, 'pct': float}}}"),
            EndpointDef("POST", "/pipeline/{id}/cancel", "Cancel a running pipeline",
                        {"id": "str"},
                        "{'cancelled': bool, 'at_stage': str}"),
            EndpointDef("GET",  "/pipeline/history","Recent pipeline runs and outcomes",
                        {},
                        "{'runs': [{'id': str, 'task': str, 'final_mae': float, 'status': str}]}"),
        ],
    ),
    ServiceDef(
        port=8021,
        name="multi_task_trainer",
        script_path="server/multi_task_trainer.py",
        description="Multi-task policy training across heterogeneous robot tasks with "
                    "task-conditioned embeddings.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/train",           "Launch multi-task training job",
                        {"tasks": "list[str]", "epochs": "int", "batch_size": "int"},
                        "{'job_id': str, 'tasks_included': int}"),
            EndpointDef("GET",  "/train/{job_id}",  "Multi-task training progress",
                        {"job_id": "path param"},
                        "{'per_task_loss': dict, 'global_step': int, 'eta_hours': float}"),
            EndpointDef("GET",  "/tasks",           "List supported tasks and their data counts",
                        {},
                        "{'tasks': [{'name': str, 'episodes': int, 'success_rate': float}]}"),
        ],
    ),
    ServiceDef(
        port=8022,
        name="jetson_deploy_server",
        script_path="server/jetson_deploy_server.py",
        description="Deploy and manage TensorRT-optimized policies on NVIDIA Jetson edge devices.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/devices",         "List registered Jetson devices",
                        {},
                        "{'devices': [{'id': str, 'model': str, 'ip': str, 'status': str}]}"),
            EndpointDef("POST", "/deploy",          "Push a TRT policy to a Jetson device",
                        {"device_id": "str", "model_id": "str"},
                        "{'deployment_id': str, 'started_at': ISO8601}"),
            EndpointDef("GET",  "/deploy/{id}",     "Deployment status",
                        {"id": "path param"},
                        "{'status': str, 'progress_pct': float, 'device_id': str}"),
        ],
    ),
    ServiceDef(
        port=8023,
        name="multi_gpu_trainer",
        script_path="server/multi_gpu_trainer.py",
        description="DDP-based multi-GPU fine-tuning with automatic gradient accumulation "
                    "and mixed precision.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/train/start",     "Launch DDP training job",
                        {"checkpoint": "str", "dataset": "str", "n_gpus": "int", "steps": "int"},
                        "{'job_id': str, 'gpus_allocated': int, 'throughput_it_s': float}"),
            EndpointDef("GET",  "/train/{job_id}",  "Training progress and GPU metrics",
                        {"job_id": "path param"},
                        "{'step': int, 'loss': float, 'gpu_util': float, 'eta_min': int}"),
            EndpointDef("POST", "/train/{job_id}/checkpoint", "Force save checkpoint",
                        {"job_id": "str"},
                        "{'saved_path': str, 'step': int}"),
        ],
    ),
    ServiceDef(
        port=8024,
        name="cosmos_world_model",
        script_path="server/cosmos_world_model.py",
        description="NVIDIA Cosmos world model interface for generating synthetic robot "
                    "video trajectories for SDG.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/generate",        "Generate synthetic video from text prompt",
                        {"prompt": "str", "frames": "int", "resolution": "str"},
                        "{'video_url': str, 'frames_generated': int, 'duration_s': float}"),
            EndpointDef("POST", "/extract_demos",   "Extract demonstrations from generated video",
                        {"video_url": "str", "task": "str"},
                        "{'demos_extracted': int, 'dataset_path': str}"),
            EndpointDef("GET",  "/quota",           "API quota and usage stats",
                        {},
                        "{'calls_today': int, 'quota_limit': int, 'cost_usd': float}"),
        ],
    ),
    ServiceDef(
        port=8025,
        name="isaac_sim_sdg",
        script_path="server/isaac_sim_sdg.py",
        description="Isaac Sim RTX synthetic data generation with domain randomization: "
                    "lighting, textures, object poses.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/sdg/start",       "Launch SDG batch",
                        {"task": "str", "n_demos": "int", "randomization_profile": "str"},
                        "{'job_id': str, 'estimated_minutes': int}"),
            EndpointDef("GET",  "/sdg/{job_id}",    "SDG job status",
                        {"job_id": "path param"},
                        "{'demos_generated': int, 'total': int, 'fps': float}"),
            EndpointDef("GET",  "/profiles",        "List domain randomization profiles",
                        {},
                        "{'profiles': [{'name': str, 'description': str}]}"),
        ],
    ),
    ServiceDef(
        port=8026,
        name="ik_motion_planner",
        script_path="server/ik_motion_planner.py",
        description="Inverse kinematics and motion planning service using cuRobo for "
                    "generating collision-free trajectories.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/plan",            "Compute IK trajectory to target pose",
                        {"robot_id": "str", "target_pose": "7-float [x,y,z,qx,qy,qz,qw]",
                         "current_joints": "list[float]"},
                        "{'trajectory': [[float]*7], 'plan_time_ms': float, 'collision_free': bool}"),
            EndpointDef("POST", "/plan/grasp",      "Plan grasp approach for an object",
                        {"object_pose": "dict", "robot_id": "str"},
                        "{'approach_traj': list, 'grasp_traj': list, 'retreat_traj': list}"),
            EndpointDef("GET",  "/workspace",       "Robot workspace bounds and obstacles",
                        {},
                        "{'bbox': dict, 'obstacles': list[dict]}"),
        ],
    ),
    ServiceDef(
        port=8027,
        name="eval_harness",
        script_path="server/eval_harness.py",
        description="Automated policy evaluation in simulation with success rate, "
                    "average reward, and episode statistics.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/eval/run",        "Run evaluation for a checkpoint",
                        {"checkpoint": "str", "task": "str", "n_episodes": "int"},
                        "{'eval_id': str, 'started_at': ISO8601}"),
            EndpointDef("GET",  "/eval/{id}",       "Evaluation progress and partial results",
                        {"id": "path param"},
                        "{'done': int, 'total': int, 'success_rate': float, 'avg_reward': float}"),
            EndpointDef("GET",  "/eval/{id}/report","Full evaluation report with per-episode data",
                        {},
                        "{'summary': dict, 'episodes': list[dict], 'failure_modes': dict}"),
        ],
    ),
    ServiceDef(
        port=8028,
        name="checkpoint_manager",
        script_path="server/checkpoint_manager.py",
        description="Training checkpoint storage, pruning, and OCI Object Storage sync.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/checkpoints",     "List all checkpoints",
                        {},
                        "{'checkpoints': [{'step': int, 'loss': float, 'path': str, 'size_mb': float}]}"),
            EndpointDef("POST", "/checkpoints/prune","Prune old checkpoints keeping top-K",
                        {"keep_top_k": "int", "metric": "str"},
                        "{'pruned': int, 'freed_gb': float}"),
            EndpointDef("POST", "/checkpoints/{step}/upload",
                        "Upload checkpoint to OCI Object Storage",
                        {"step": "path param"},
                        "{'uploaded': bool, 'oci_path': str}"),
        ],
    ),
    ServiceDef(
        port=8029,
        name="docker_compose_api",
        script_path="server/docker_compose_api.py",
        description="REST wrapper around Docker Compose for managing the multi-service stack.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/services",        "List all compose services and their status",
                        {},
                        "{'services': [{'name': str, 'status': str, 'port': int}]}"),
            EndpointDef("POST", "/services/{name}/restart", "Restart a specific service",
                        {"name": "path param"},
                        "{'restarted': bool, 'uptime_s': int}"),
            EndpointDef("POST", "/services/scale",  "Scale a service to N replicas",
                        {"service": "str", "replicas": "int"},
                        "{'scaled': bool, 'replicas': int}"),
        ],
    ),
    ServiceDef(
        port=8030,
        name="training_monitor",
        script_path="server/training_monitor.py",
        description="Real-time training metrics dashboard backend: loss curves, GPU stats, "
                    "ETA, and Slack notifications.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/metrics/live",    "Live training metrics (SSE stream)",
                        {},
                        "Server-sent events: {step, loss, lr, gpu_util, eta_min}"),
            EndpointDef("GET",  "/metrics/history", "Historical loss curve for current run",
                        {},
                        "{'steps': list[int], 'losses': list[float], 'lrs': list[float]}"),
            EndpointDef("POST", "/notify",          "Send training milestone notification to Slack",
                        {"milestone": "str", "metrics": "dict"},
                        "{'sent': bool}"),
        ],
    ),
    ServiceDef(
        port=8031,
        name="live_demo_scheduler",
        script_path="server/live_demo_scheduler.py",
        description="Schedules and manages live robot demo sessions for external stakeholders "
                    "and conference demonstrations.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/demos",           "List scheduled demo sessions",
                        {},
                        "{'demos': [{'id': str, 'audience': str, 'at': ISO8601, 'task': str}]}"),
            EndpointDef("POST", "/demos/book",      "Book a new demo slot",
                        {"audience": "str", "at": "ISO8601", "task": "str", "robot_id": "str"},
                        "{'demo_id': str, 'confirmed': bool}"),
            EndpointDef("POST", "/demos/{id}/run",  "Execute a scheduled demo",
                        {"id": "path param"},
                        "{'stream_url': str, 'started_at': ISO8601}"),
        ],
    ),
    ServiceDef(
        port=8032,
        name="closed_loop_eval",
        script_path="server/closed_loop_eval.py",
        description="Closed-loop policy evaluation: robot executes policy autonomously in "
                    "simulation or real with success/failure classification.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/eval/closed_loop","Run closed-loop evaluation",
                        {"checkpoint": "str", "task": "str", "episodes": "int",
                         "env": "sim|real"},
                        "{'eval_id': str, 'env': str}"),
            EndpointDef("GET",  "/eval/{id}/live",  "Live episode status during evaluation",
                        {"id": "path param"},
                        "{'episode': int, 'step': int, 'status': str, 'partial_success': float}"),
            EndpointDef("GET",  "/eval/{id}/summary","Final evaluation summary",
                        {},
                        "{'success_rate': float, 'avg_steps': float, 'avg_time_s': float}"),
        ],
    ),
    ServiceDef(
        port=8033,
        name="sdk_documentation_server",
        script_path="server/sdk_documentation_server.py",
        description="Serves the oci-robot-cloud Python SDK documentation, interactive examples, "
                    "and OpenAPI spec.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/",               "SDK documentation homepage (HTML)",
                        {},
                        "HTML page"),
            EndpointDef("GET",  "/openapi.json",   "OpenAPI 3.0 spec for the SDK",
                        {},
                        "OpenAPI JSON schema"),
            EndpointDef("GET",  "/examples/{name}","Fetch a runnable SDK example script",
                        {"name": "example name (str)"},
                        "{'code': str, 'language': 'python'}"),
        ],
    ),
    ServiceDef(
        port=8034,
        name="inference_gateway",
        script_path="server/inference_gateway.py",
        description="Unified inference gateway with API key auth, rate limiting, routing "
                    "to backend inference servers, and usage tracking.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/v1/predict",      "Authenticated inference (routes to 8001/8002)",
                        {"X-API-Key": "header", "image_b64": "str", "instruction": "str"},
                        "{'actions': list, 'latency_ms': float, 'backend': str}"),
            EndpointDef("GET",  "/v1/usage",        "API key usage stats",
                        {"X-API-Key": "header"},
                        "{'requests_today': int, 'quota_remaining': int, 'tier': str}"),
            EndpointDef("GET",  "/backends/status", "Backend server health",
                        {},
                        "{'backends': [{'port': int, 'healthy': bool, 'latency_ms': float}]}"),
        ],
    ),
    ServiceDef(
        port=8035,
        name="multi_task_eval",
        script_path="server/multi_task_eval.py",
        description="Parallel evaluation of a policy across multiple tasks simultaneously "
                    "with aggregated benchmark scores.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/eval/multi",      "Run multi-task evaluation",
                        {"checkpoint": "str", "tasks": "list[str]",
                         "episodes_per_task": "int"},
                        "{'eval_id': str, 'tasks': int}"),
            EndpointDef("GET",  "/eval/{id}",       "Multi-task evaluation results",
                        {"id": "path param"},
                        "{'per_task': {task: float}, 'aggregate': float, 'done': bool}"),
            EndpointDef("GET",  "/benchmarks",      "Standard benchmark suite definitions",
                        {},
                        "{'benchmarks': [{'name': str, 'tasks': list, 'description': str}]}"),
        ],
    ),
    ServiceDef(
        port=8036,
        name="convergence_monitor",
        script_path="server/convergence_monitor.py",
        description="Detects training convergence via gradient norm, loss plateau, and "
                    "validation metric stability.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/check",           "Check convergence for a training run",
                        {"job_id": "str", "window": "int steps"},
                        "{'converged': bool, 'plateau_steps': int, 'gradient_norm': float}"),
            EndpointDef("GET",  "/signals/{job_id}","Real-time convergence signals",
                        {"job_id": "path param"},
                        "{'loss_std': float, 'grad_norm': float, 'val_delta': float}"),
            EndpointDef("POST", "/early_stop",      "Trigger early stopping if converged",
                        {"job_id": "str"},
                        "{'stopped': bool, 'final_step': int}"),
        ],
    ),
    ServiceDef(
        port=8037,
        name="failure_mode_analyzer",
        script_path="server/failure_mode_analyzer.py",
        description="Automatically classifies robot failure modes (grasp failure, path "
                    "deviation, perception error) from episode recordings.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/analyze",         "Analyze failure modes in an episode",
                        {"episode_id": "str"},
                        "{'failure_type': str, 'confidence': float, 'frame_of_failure': int}"),
            EndpointDef("GET",  "/distribution",    "Failure mode distribution over recent episodes",
                        {},
                        "{'modes': {str: int}, 'total_failures': int, 'period_hours': int}"),
            EndpointDef("GET",  "/recommendations", "Remediation recommendations by failure mode",
                        {},
                        "{'recommendations': [{'mode': str, 'action': str, 'priority': str}]}"),
        ],
    ),
    ServiceDef(
        port=8038,
        name="stats_significance_tester",
        script_path="server/stats_significance_tester.py",
        description="Statistical significance testing for policy comparison experiments "
                    "(t-test, bootstrap CI, permutation test).",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/test",            "Run significance test between two policies",
                        {"success_a": "list[bool]", "success_b": "list[bool]",
                         "method": "ttest|bootstrap|permutation"},
                        "{'p_value': float, 'significant': bool, 'ci_95': [float, float]}"),
            EndpointDef("POST", "/power_analysis",  "Compute required sample size for given power",
                        {"effect_size": "float", "power": "float", "alpha": "float"},
                        "{'n_required': int}"),
            EndpointDef("GET",  "/methods",         "List supported statistical test methods",
                        {},
                        "{'methods': [{'name': str, 'description': str}]}"),
        ],
    ),
    ServiceDef(
        port=8039,
        name="training_curves_server",
        script_path="server/training_curves_server.py",
        description="Serves interactive Plotly training curve visualizations for all runs.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/curves/{job_id}", "HTML page with interactive loss curves",
                        {"job_id": "path param"},
                        "HTML page with Plotly charts"),
            EndpointDef("GET",  "/curves/{job_id}/json", "Raw curve data as JSON",
                        {"job_id": "path param"},
                        "{'steps': list, 'train_loss': list, 'val_loss': list}"),
            EndpointDef("GET",  "/compare",         "Compare curves across multiple runs",
                        {"job_ids": "comma-separated str"},
                        "HTML comparison page"),
        ],
    ),
    ServiceDef(
        port=8040,
        name="ablation_runner",
        script_path="server/ablation_runner.py",
        description="Automated ablation study runner: sweeps over config components and "
                    "measures each component's contribution.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/ablation/start",  "Define and launch an ablation study",
                        {"base_config": "dict", "ablations": "list[dict]", "metric": "str"},
                        "{'study_id': str, 'n_jobs': int}"),
            EndpointDef("GET",  "/ablation/{id}",   "Ablation study results table",
                        {"id": "path param"},
                        "{'results': [{'ablation': str, 'metric': float, 'delta': float}]}"),
            EndpointDef("GET",  "/ablation/{id}/report", "Formatted ablation report",
                        {},
                        "HTML or JSON ablation table"),
        ],
    ),
    ServiceDef(
        port=8041,
        name="portal_customer",
        script_path="server/portal_customer.py",
        description="Customer-facing portal backend: project management, usage dashboards, "
                    "and model deployment requests.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/projects",        "List customer's projects",
                        {"X-API-Key": "header"},
                        "{'projects': [{'id': str, 'name': str, 'status': str}]}"),
            EndpointDef("POST", "/projects/create", "Create a new project",
                        {"name": "str", "task": "str", "robot_type": "str"},
                        "{'project_id': str, 'onboarding_url': str}"),
            EndpointDef("GET",  "/usage",           "Usage and billing summary",
                        {"X-API-Key": "header"},
                        "{'compute_hours': float, 'api_calls': int, 'cost_usd': float}"),
        ],
    ),
    ServiceDef(
        port=8042,
        name="portal_internal",
        script_path="server/portal_internal.py",
        description="Internal OCI team portal: all customer accounts, deployments, "
                    "infrastructure costs, and operational alerts.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/customers",       "All customer accounts and tiers",
                        {},
                        "{'customers': [{'id': str, 'name': str, 'tier': str, 'mrr': float}]}"),
            EndpointDef("GET",  "/infrastructure",  "Infrastructure cost breakdown",
                        {},
                        "{'total_monthly': float, 'by_service': dict, 'by_customer': dict}"),
            EndpointDef("GET",  "/alerts",          "Active operational alerts",
                        {},
                        "{'alerts': [{'severity': str, 'service': str, 'message': str}]}"),
        ],
    ),
    ServiceDef(
        port=8043,
        name="billing_api",
        script_path="server/billing_api.py",
        description="Usage-based billing computation, invoice generation, and OCI Billing "
                    "integration.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/invoices/{customer_id}", "Get invoices for a customer",
                        {"customer_id": "path param"},
                        "{'invoices': [{'id': str, 'amount': float, 'period': str, 'status': str}]}"),
            EndpointDef("POST", "/invoices/generate","Generate monthly invoices for all customers",
                        {"month": "YYYY-MM"},
                        "{'generated': int, 'total_revenue': float}"),
            EndpointDef("GET",  "/revenue/summary", "MRR, ARR, and growth metrics",
                        {},
                        "{'mrr': float, 'arr': float, 'growth_pct': float}"),
        ],
    ),
    ServiceDef(
        port=8044,
        name="journey_report_server",
        script_path="server/journey_report_server.py",
        description="Generates narrative training journey reports combining metrics, "
                    "milestones, and visualizations.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/report/generate", "Generate a training journey report",
                        {"job_id": "str", "format": "html|pdf|md"},
                        "{'report_url': str, 'generated_at': ISO8601}"),
            EndpointDef("GET",  "/report/{id}",     "Fetch a generated report",
                        {"id": "path param"},
                        "Report content (HTML/PDF/Markdown)"),
            EndpointDef("GET",  "/milestones/{job_id}", "Key milestones for a training run",
                        {"job_id": "path param"},
                        "{'milestones': [{'step': int, 'event': str, 'metric': float}]}"),
        ],
    ),
    ServiceDef(
        port=8045,
        name="eval_watcher",
        script_path="server/eval_watcher.py",
        description="Watches the checkpoints directory and automatically triggers evaluation "
                    "when new checkpoints are saved.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/watching",        "List directories currently being watched",
                        {},
                        "{'dirs': [{'path': str, 'pattern': str, 'last_seen': ISO8601}]}"),
            EndpointDef("POST", "/watch",           "Add a directory to watch",
                        {"path": "str", "eval_config": "dict"},
                        "{'watching': bool, 'watch_id': str}"),
            EndpointDef("GET",  "/triggered",       "Recent auto-triggered evaluations",
                        {},
                        "{'evals': [{'checkpoint': str, 'eval_id': str, 'triggered_at': ISO8601}]}"),
        ],
    ),
    ServiceDef(
        port=8046,
        name="load_tester",
        script_path="server/load_tester.py",
        description="Load testing harness for inference endpoints: ramp profiles, "
                    "latency percentiles, and throughput benchmarks.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/test/run",        "Run a load test against a target endpoint",
                        {"target_url": "str", "rps": "int", "duration_s": "int"},
                        "{'test_id': str, 'started_at': ISO8601}"),
            EndpointDef("GET",  "/test/{id}/results","Load test results",
                        {"id": "path param"},
                        "{'p50_ms': float, 'p95_ms': float, 'p99_ms': float, 'errors': int}"),
            EndpointDef("GET",  "/profiles",        "Pre-defined load test profiles",
                        {},
                        "{'profiles': [{'name': str, 'rps': int, 'duration_s': int}]}"),
        ],
    ),
    ServiceDef(
        port=8047,
        name="preflight_checker",
        script_path="server/preflight_checker.py",
        description="Pre-flight system checks for demos and production deployments: GPU "
                    "health, model loading, network connectivity.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/check",           "Run full preflight check suite",
                        {"profile": "demo|production|training"},
                        "{'passed': bool, 'checks': [{'name': str, 'ok': bool, 'detail': str}]}"),
            EndpointDef("GET",  "/checks",          "List all available preflight checks",
                        {},
                        "{'checks': [{'name': str, 'category': str, 'timeout_s': int}]}"),
            EndpointDef("POST", "/check/{name}",    "Run a single named preflight check",
                        {"name": "path param"},
                        "{'ok': bool, 'detail': str, 'duration_ms': float}"),
        ],
    ),
    ServiceDef(
        port=8048,
        name="results_aggregator",
        script_path="server/results_aggregator.py",
        description="Aggregates evaluation results across runs, tasks, and checkpoints into "
                    "summary tables and trend reports.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/leaderboard",     "Top checkpoints by task and metric",
                        {},
                        "{'leaderboard': [{'rank': int, 'checkpoint': str, 'score': float}]}"),
            EndpointDef("POST", "/aggregate",       "Aggregate results for a set of eval IDs",
                        {"eval_ids": "list[str]", "group_by": "task|checkpoint|date"},
                        "{'table': list[dict], 'summary_stats': dict}"),
            EndpointDef("GET",  "/trends",          "Success rate trends over time",
                        {},
                        "{'dates': list[str], 'success_rates': list[float]}"),
        ],
    ),
    ServiceDef(
        port=8049,
        name="checkpoint_comparator",
        script_path="server/checkpoint_comparator.py",
        description="Side-by-side comparison of two model checkpoints: parameter diffs, "
                    "performance deltas, and behavioral divergence.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/compare",         "Compare two checkpoints",
                        {"checkpoint_a": "str", "checkpoint_b": "str", "task": "str"},
                        "{'delta_mae': float, 'delta_success': float, 'param_diff_pct': float}"),
            EndpointDef("GET",  "/compare/{id}/behavioral", "Behavioral divergence analysis",
                        {"id": "path param"},
                        "{'kl_divergence': float, 'action_diff_mean': float}"),
            EndpointDef("GET",  "/compare/{id}/report", "Full comparison report",
                        {},
                        "HTML report with charts and tables"),
        ],
    ),
    ServiceDef(
        port=8050,
        name="gtc_qna_server",
        script_path="server/gtc_qna_server.py",
        description="GTC talk Q&A assistant: indexes the OCI Robot Cloud presentation "
                    "and answers audience questions in real time.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/ask",             "Ask a question about OCI Robot Cloud",
                        {"question": "str", "context": "str (optional)"},
                        "{'answer': str, 'sources': list[str], 'confidence': float}"),
            EndpointDef("GET",  "/slides",          "List indexed slide topics",
                        {},
                        "{'slides': [{'idx': int, 'title': str, 'keywords': list[str]}]}"),
            EndpointDef("POST", "/slides/reindex",  "Reindex slides after deck update",
                        {"deck_path": "str"},
                        "{'slides_indexed': int, 'duration_s': float}"),
        ],
    ),
    ServiceDef(
        port=8051,
        name="model_versioning_api",
        script_path="server/model_versioning_api.py",
        description="Semantic versioning for production model releases with changelogs, "
                    "rollback support, and canary deployments.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/versions",        "All model versions",
                        {},
                        "{'versions': [{'tag': str, 'model_id': str, 'released_at': ISO8601}]}"),
            EndpointDef("POST", "/versions/release","Create a new versioned release",
                        {"model_id": "str", "version": "semver", "changelog": "str"},
                        "{'version': str, 'released': bool}"),
            EndpointDef("POST", "/versions/{ver}/rollback", "Rollback to a previous version",
                        {"ver": "path param"},
                        "{'rolled_back': bool, 'active_version': str}"),
        ],
    ),
    ServiceDef(
        port=8052,
        name="training_notifier",
        script_path="server/training_notifier.py",
        description="Sends Slack and email notifications for training milestones, failures, "
                    "and convergence events.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/notify/slack",    "Send a Slack notification",
                        {"channel": "str", "message": "str",
                         "attachments": "list (optional)"},
                        "{'sent': bool, 'ts': str}"),
            EndpointDef("POST", "/notify/email",    "Send an email notification",
                        {"to": "str", "subject": "str", "body_html": "str"},
                        "{'sent': bool, 'message_id': str}"),
            EndpointDef("GET",  "/subscriptions",   "List notification subscriptions",
                        {},
                        "{'subscriptions': [{'event': str, 'channel': str, 'email': str}]}"),
        ],
    ),
    ServiceDef(
        port=8053,
        name="api_key_manager",
        script_path="server/api_key_manager.py",
        description="API key lifecycle management: provisioning, rotation, scoping, "
                    "rate limit configuration, and revocation.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/keys/create",     "Create a new API key",
                        {"customer_id": "str", "tier": "free|starter|enterprise",
                         "scopes": "list[str]"},
                        "{'api_key': str, 'key_id': str, 'expires_at': ISO8601}"),
            EndpointDef("POST", "/keys/{id}/rotate","Rotate an API key",
                        {"id": "path param"},
                        "{'new_key': str, 'old_key_expires_in_s': int}"),
            EndpointDef("DELETE", "/keys/{id}",     "Revoke an API key",
                        {"id": "path param"},
                        "{'revoked': bool}"),
            EndpointDef("GET",  "/keys",            "List all keys for a customer",
                        {"customer_id": "query param"},
                        "{'keys': [{'id': str, 'tier': str, 'active': bool}]}"),
        ],
    ),
    ServiceDef(
        port=8054,
        name="health_aggregator",
        script_path="server/health_aggregator.py",
        description="Aggregates health checks from all 58 services into a unified status "
                    "dashboard with historical uptime.",
        status="live",
        endpoints=[
            EndpointDef("GET",  "/health",          "Overall system health summary",
                        {},
                        "{'healthy': int, 'degraded': int, 'down': int, 'uptime_pct': float}"),
            EndpointDef("GET",  "/health/services", "Per-service health status",
                        {},
                        "{'services': [{'port': int, 'name': str, 'status': str, "
                        "'latency_ms': float}]}"),
            EndpointDef("GET",  "/health/history",  "24-hour uptime history per service",
                        {},
                        "{'history': {port: [{'time': ISO8601, 'up': bool}]}}"),
        ],
    ),
    ServiceDef(
        port=8055,
        name="contract_generator",
        script_path="server/contract_generator.py",
        description="Auto-generates partner and customer contracts from templates with "
                    "pricing, SLA terms, and legal clauses.",
        status="planned",
        endpoints=[
            EndpointDef("POST", "/contracts/generate","Generate a contract from template",
                        {"template": "str", "parties": "dict", "pricing": "dict"},
                        "{'contract_id': str, 'pdf_url': str, 'docx_url': str}"),
            EndpointDef("GET",  "/templates",       "List available contract templates",
                        {},
                        "{'templates': [{'id': str, 'name': str, 'type': str}]}"),
            EndpointDef("GET",  "/contracts/{id}",  "Fetch a generated contract",
                        {"id": "path param"},
                        "PDF or DOCX binary"),
        ],
    ),
    ServiceDef(
        port=8056,
        name="revenue_dashboard",
        script_path="server/revenue_dashboard.py",
        description="Real-time revenue dashboard: MRR, ARR, churn, customer cohorts, "
                    "and pipeline forecast.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/metrics",         "Key revenue metrics",
                        {},
                        "{'mrr': float, 'arr': float, 'churn_rate': float, 'customers': int}"),
            EndpointDef("GET",  "/forecast",        "12-month revenue forecast",
                        {},
                        "{'months': list[str], 'projected_mrr': list[float], 'scenarios': dict}"),
            EndpointDef("GET",  "/cohorts",         "Customer cohort retention analysis",
                        {},
                        "{'cohorts': [{'month': str, 'retention': list[float]}]}"),
        ],
    ),
    ServiceDef(
        port=8057,
        name="gtc_talk_timer",
        script_path="server/gtc_talk_timer.py",
        description="GTC talk presentation timer with slide-by-slide time budgets, "
                    "pace alerts, and rehearsal logging.",
        status="live",
        endpoints=[
            EndpointDef("POST", "/session/start",   "Start a timed presentation session",
                        {"deck_id": "str", "total_minutes": "int"},
                        "{'session_id': str, 'slide_budgets': list[float]}"),
            EndpointDef("POST", "/session/{id}/advance",
                        "Advance to next slide (records timing)",
                        {"id": "path param"},
                        "{'slide': int, 'time_spent_s': float, 'on_pace': bool}"),
            EndpointDef("GET",  "/session/{id}/summary", "Post-presentation timing summary",
                        {"id": "path param"},
                        "{'total_s': float, 'per_slide': list[float], 'over_budget': list[int]}"),
        ],
    ),
    ServiceDef(
        port=8058,
        name="nvidia_partnership_tracker",
        script_path="server/nvidia_partnership_tracker.py",
        description="Tracks NVIDIA partnership milestones, joint GTM activities, co-sell "
                    "opportunities, and integration dependencies.",
        status="planned",
        endpoints=[
            EndpointDef("GET",  "/milestones",      "All partnership milestones and status",
                        {},
                        "{'milestones': [{'id': str, 'title': str, 'status': str, 'due': str}]}"),
            EndpointDef("POST", "/milestones/{id}/complete",
                        "Mark a milestone as complete",
                        {"id": "path param", "notes": "str"},
                        "{'completed': bool, 'completed_at': ISO8601}"),
            EndpointDef("GET",  "/opportunities",   "Joint co-sell pipeline",
                        {},
                        "{'opportunities': [{'account': str, 'stage': str, 'acv': float}]}"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

METHOD_COLORS = {
    "GET":    "#10B981",
    "POST":   "#3B82F6",
    "DELETE": "#EF4444",
    "PUT":    "#F59E0B",
    "PATCH":  "#8B5CF6",
}


def _endpoint_html(ep: EndpointDef, svc_port: int, ep_idx: int) -> str:
    color = METHOD_COLORS.get(ep.method, "#6B7280")
    card_id = f"ep-{svc_port}-{ep_idx}"
    if ep.params:
        params_rows = "".join(
            f"<tr><td class='param-name'>{k}</td>"
            f"<td class='param-desc'>{v}</td></tr>"
            for k, v in ep.params.items()
        )
    else:
        params_rows = "<tr><td colspan='2' class='no-params'>No parameters</td></tr>"
    return (
        f'<div class="endpoint-card" id="{card_id}">'
        f'<div class="ep-header" onclick="toggleEndpoint(\'{card_id}\')">'
        f'<span class="method-badge" style="background:{color}">{ep.method}</span>'
        f'<span class="ep-path">{ep.path}</span>'
        f'<span class="ep-desc">{ep.description}</span>'
        f'<span class="ep-chevron">&#9662;</span>'
        f'</div>'
        f'<div class="ep-body">'
        f'<table class="params-table">'
        f'<thead><tr><th>Parameter</th><th>Description</th></tr></thead>'
        f'<tbody>{params_rows}</tbody>'
        f'</table>'
        f'<div class="returns-row">'
        f'<span class="returns-label">Returns:</span>'
        f'<code class="returns-code">{ep.returns}</code>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def render_html(services: List[ServiceDef]) -> str:
    total_endpoints = sum(len(s.endpoints) for s in services)
    live_count = sum(1 for s in services if s.status == "live")
    planned_count = len(services) - live_count

    sidebar_items = "\n".join(
        f'<li class="sidebar-item {s.status}" '
        f'data-port="{s.port}" data-name="{s.name}" '
        f'onclick="scrollToService(\'{s.port}\')">'
        f'<span class="sb-port">{s.port}</span>'
        f'<span class="sb-name">{s.name}</span>'
        f'<span class="sb-badge sb-{s.status}">{s.status}</span>'
        f'</li>'
        for s in services
    )

    service_cards = ""
    for svc in services:
        eps_html = "".join(
            _endpoint_html(ep, svc.port, i)
            for i, ep in enumerate(svc.endpoints)
        )
        status_class = "live" if svc.status == "live" else "planned"
        service_cards += (
            f'<section class="service-card" id="svc-{svc.port}">'
            f'<div class="svc-header">'
            f'<div class="svc-title-row">'
            f'<span class="svc-port">:{svc.port}</span>'
            f'<h2 class="svc-name">{svc.name}</h2>'
            f'<span class="status-pill {status_class}">{svc.status}</span>'
            f'</div>'
            f'<p class="svc-desc">{svc.description}</p>'
            f'<div class="svc-script">'
            f'<span class="script-label">Script:</span>'
            f'<code class="script-path">{svc.script_path}</code>'
            f'</div>'
            f'</div>'
            f'<div class="endpoints-list">{eps_html}</div>'
            f'</section>'
        )

    css = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0F172A; --surface: #1E293B; --surface2: #263348;
      --border: #334155; --text: #E2E8F0; --muted: #94A3B8;
      --accent: #38BDF8; --green: #10B981; --gray: #6B7280;
      --sidebar-w: 280px;
    }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
           color: var(--text); display: flex; height: 100vh; overflow: hidden; }
    #topbar { position: fixed; top: 0; left: 0; right: 0; height: 56px;
              background: var(--surface); border-bottom: 1px solid var(--border);
              display: flex; align-items: center; padding: 0 24px; z-index: 100;
              gap: 24px; }
    #topbar .logo { font-size: 1.1rem; font-weight: 700; color: var(--accent);
                    white-space: nowrap; }
    #topbar .stats { display: flex; gap: 20px; font-size: 0.8rem; color: var(--muted); }
    #topbar .stats span strong { color: var(--text); }
    #search { flex: 1; max-width: 400px; background: var(--surface2);
              border: 1px solid var(--border); border-radius: 8px; color: var(--text);
              padding: 6px 14px; font-size: 0.9rem; outline: none; }
    #search:focus { border-color: var(--accent); }
    #search::placeholder { color: var(--muted); }
    #sidebar { position: fixed; top: 56px; left: 0; bottom: 0; width: var(--sidebar-w);
               background: var(--surface); border-right: 1px solid var(--border);
               overflow-y: auto; padding: 12px 0; }
    #main { margin-top: 56px; margin-left: var(--sidebar-w); flex: 1; overflow-y: auto;
            padding: 32px; height: calc(100vh - 56px); }
    .sidebar-item { display: flex; align-items: center; gap: 8px; padding: 8px 16px;
                    cursor: pointer; border-left: 3px solid transparent;
                    transition: background .15s; font-size: 0.82rem; }
    .sidebar-item:hover { background: var(--surface2); }
    .sidebar-item.live { border-left-color: var(--green); }
    .sidebar-item.planned { border-left-color: var(--gray); }
    .sb-port { color: var(--accent); font-family: monospace; font-size: 0.78rem;
               min-width: 42px; }
    .sb-name { color: var(--text); flex: 1; overflow: hidden; text-overflow: ellipsis;
               white-space: nowrap; }
    .sb-badge { font-size: 0.65rem; padding: 1px 6px; border-radius: 10px;
                text-transform: uppercase; font-weight: 600; }
    .sb-live { background: #064e3b; color: var(--green); }
    .sb-planned { background: #1f2937; color: var(--gray); }
    .service-card { background: var(--surface); border: 1px solid var(--border);
                    border-radius: 12px; margin-bottom: 28px; overflow: hidden; }
    .svc-header { padding: 20px 24px; border-bottom: 1px solid var(--border); }
    .svc-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
    .svc-port { font-family: monospace; font-size: 1.1rem; color: var(--accent);
                font-weight: 700; }
    .svc-name { font-size: 1.15rem; font-weight: 700; color: var(--text); }
    .status-pill { font-size: 0.7rem; padding: 2px 10px; border-radius: 12px;
                   text-transform: uppercase; font-weight: 700; }
    .status-pill.live { background: #064e3b; color: var(--green); }
    .status-pill.planned { background: #1f2937; color: var(--gray); }
    .svc-desc { color: var(--muted); font-size: 0.9rem; line-height: 1.5; margin-bottom: 10px; }
    .svc-script { font-size: 0.8rem; }
    .script-label { color: var(--muted); margin-right: 6px; }
    .script-path { background: var(--surface2); padding: 2px 8px; border-radius: 4px;
                   color: #F472B6; font-size: 0.8rem; }
    .endpoints-list { padding: 16px 24px; display: flex; flex-direction: column; gap: 8px; }
    .endpoint-card { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    .ep-header { display: flex; align-items: center; gap: 12px; padding: 10px 14px;
                 cursor: pointer; background: var(--surface2); user-select: none;
                 transition: background .15s; }
    .ep-header:hover { background: #2d3f58; }
    .method-badge { font-family: monospace; font-size: 0.72rem; font-weight: 700;
                    padding: 2px 8px; border-radius: 4px; color: #fff; min-width: 54px;
                    text-align: center; }
    .ep-path { font-family: monospace; font-size: 0.88rem; color: var(--text);
               min-width: 160px; }
    .ep-desc { color: var(--muted); font-size: 0.83rem; flex: 1; }
    .ep-chevron { color: var(--muted); transition: transform .2s; margin-left: auto; }
    .ep-body { display: none; padding: 14px 16px; background: var(--bg);
               border-top: 1px solid var(--border); }
    .ep-body.open { display: block; }
    .ep-chevron.open { transform: rotate(180deg); }
    .params-table { width: 100%; border-collapse: collapse; font-size: 0.83rem;
                    margin-bottom: 12px; }
    .params-table th { text-align: left; padding: 6px 10px; color: var(--muted);
                       border-bottom: 1px solid var(--border); font-weight: 600; }
    .params-table td { padding: 6px 10px; border-bottom: 1px solid #1e2d3d;
                       vertical-align: top; }
    .param-name { font-family: monospace; color: var(--accent); }
    .param-desc { color: var(--muted); }
    .no-params { color: var(--muted); font-style: italic; }
    .returns-row { font-size: 0.83rem; }
    .returns-label { color: var(--muted); margin-right: 8px; }
    .returns-code { background: var(--surface2); padding: 4px 10px; border-radius: 4px;
                    color: #86EFAC; font-size: 0.8rem; word-break: break-all; }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    .hidden { display: none !important; }
    """

    js = """
    function toggleEndpoint(id) {
      var card = document.getElementById(id);
      var body = card.querySelector('.ep-body');
      var chevron = card.querySelector('.ep-chevron');
      body.classList.toggle('open');
      chevron.classList.toggle('open');
    }
    function scrollToService(port) {
      var el = document.getElementById('svc-' + port);
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }
    function filterServices(query) {
      var q = query.trim().toLowerCase();
      var items = document.querySelectorAll('#sidebar-list .sidebar-item');
      var cards = document.querySelectorAll('.service-card');
      items.forEach(function(item) {
        var port = item.dataset.port;
        var name = item.dataset.name;
        var match = !q || port.indexOf(q) !== -1 || name.indexOf(q) !== -1;
        item.classList.toggle('hidden', !match);
      });
      cards.forEach(function(card) {
        var id = card.id.replace('svc-', '');
        var name = card.querySelector('.svc-name').textContent.toLowerCase();
        var match = !q || id.indexOf(q) !== -1 || name.indexOf(q) !== -1;
        card.classList.toggle('hidden', !match);
      });
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud - API Reference</title>
  <style>{css}</style>
</head>
<body>
  <div id="topbar">
    <span class="logo">OCI Robot Cloud API Reference</span>
    <div class="stats">
      <span><strong>{len(services)}</strong> services</span>
      <span><strong>{live_count}</strong> live</span>
      <span><strong>{planned_count}</strong> planned</span>
      <span><strong>{total_endpoints}</strong> endpoints</span>
    </div>
    <input id="search" type="text"
           placeholder="Search by port or service name..."
           oninput="filterServices(this.value)">
  </div>
  <nav id="sidebar">
    <ul id="sidebar-list" style="list-style:none">
{sidebar_items}
    </ul>
  </nav>
  <main id="main">
{service_cards}
  </main>
  <script>{js}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate unified HTML API reference for OCI Robot Cloud services"
    )
    parser.add_argument(
        "--output",
        default="/tmp/api_reference.html",
        help="Output path for the HTML file (default: /tmp/api_reference.html)",
    )
    args = parser.parse_args()

    html = render_html(SERVICES)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    total_endpoints = sum(len(s.endpoints) for s in SERVICES)
    live_count = sum(1 for s in SERVICES if s.status == "live")
    print(f"Generated {args.output}")
    print(f"  Services : {len(SERVICES)} (ports 8001-8058)")
    print(f"  Live     : {live_count}")
    print(f"  Planned  : {len(SERVICES) - live_count}")
    print(f"  Endpoints: {total_endpoints}")


if __name__ == "__main__":
    main()
