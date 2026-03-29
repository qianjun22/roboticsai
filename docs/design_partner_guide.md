# OCI Robot Cloud — Design Partner Quick-Start Guide

**Get from demo data to a fine-tuned robot policy in 30 minutes on OCI A100.**

---

## Who This Is For

You're a robotics startup that:
- Has proprietary manipulation demo data (or wants to generate it)
- Needs A100-class GPU for GR00T fine-tuning but can't justify DGX CapEx
- Wants to validate whether your robot task can benefit from foundation model fine-tuning

We provide free OCI A100 compute for initial runs, direct engineering support, and co-authorship on joint publications.

---

## Step 1: Prepare Your Data

### Option A — Upload existing demos (HDF5 or raw video)

```bash
pip install oci-robot-cloud

# Upload via the SDK
python -c "
from oci_robot_cloud import RobotCloudClient
client = RobotCloudClient()
client.upload_dataset('/path/to/your/demos', embodiment='franka_panda')
"
```

Or use the REST API (port 8003):
```bash
curl -X POST http://OCI_IP:8003/upload \
    -F "file=@/path/to/demo_001.hdf5" \
    -F "embodiment=franka_panda" \
    -F "task=pick_and_place"
```

Accepted formats:
- **HDF5** (`.hdf5`): keys `action` (N, 9), `images/agentview` (N, H, W, 3)
- **NumPy** (`frames.npy` + `actions.npy`)
- **Video** (`.mp4`) + CSV action file

Supported embodiments: `franka_panda`, `ur5e`, `kinova_gen3`, `xarm7`

### Option B — Generate synthetic demos with Genesis

```bash
# 1000 IK-planned demonstrations for Franka pick-and-lift
python src/simulation/genesis_sdg_planned.py \
    --num-demos 1000 \
    --output /tmp/your_dataset \
    --seed 42
```

Requires: OCI GPU4 (A100), Genesis 0.4.3 (pip install genesis-world)

---

## Step 2: Launch Fine-Tuning

### Via the OCI Robot Cloud API

```bash
# Start a fine-tuning job
curl -X POST http://OCI_IP:8080/jobs/train \
    -H "Content-Type: application/json" \
    -d '{
        "dataset_path": "/tmp/your_dataset_lerobot",
        "base_model": "GR00T-N1.6-3B",
        "max_steps": 5000,
        "batch_size": 32,
        "gpu_id": 4
    }'

# Monitor progress (SSE stream)
curl http://OCI_IP:8004/stream
```

Open `http://OCI_IP:8004` in a browser for the live training dashboard.

### Via the CLI

```bash
oci-robot-cloud train \
    --demos /tmp/your_dataset \
    --steps 5000 \
    --gpu-id 4 \
    --output /tmp/finetune_job1
```

### Expected Performance

| Config | Throughput | Time for 5k steps | Cost |
|--------|-----------|-------------------|------|
| 1× A100 (batch=32) | 2.35 it/s | ~35 min | ~$0.43 |
| 4× A100 DDP (batch=128) | 2.51 it/s | ~33 min | ~$0.08 per GPU |

---

## Step 3: Evaluate Your Policy

### Closed-Loop Simulation (Genesis)

```bash
# Start inference server with your checkpoint
python src/inference/groot_franka_server.py \
    --model-path /tmp/finetune_job1/checkpoint-5000 \
    --port 8002

# Run closed-loop evaluation (20 episodes)
python src/eval/closed_loop_eval.py \
    --num-episodes 20 \
    --server-url http://localhost:8002 \
    --output /tmp/eval_results
```

### Query the Inference Server

```bash
curl -X POST http://localhost:8002/predict \
    -F "image=@current_frame.jpg" \
    -F "instruction=pick up the red cube from the table"
```

Response:
```json
{
    "arm": [[-0.022, -0.397, 0.005, -1.652, 0.003, 3.088, 0.780], ...],
    "gripper": [[0.04, 0.04], ...],
    "latency_ms": 179.3
}
```

The server returns 16-step action chunks. Execute one chunk per control cycle.

---

## Step 4: Inspect Data Quality

Before fine-tuning, check your dataset quality:

```bash
python src/training/dataset_inspector.py \
    --dataset /tmp/your_dataset_lerobot \
    --output /tmp/quality_report.html
```

The report shows: episode length distribution, joint angle ranges, PCA trajectory diversity, visual diversity score. Ideal minimum: 100+ episodes, median length >50 steps.

---

## Data Format Reference

### LeRobot v2 (required for fine-tuning)

```
dataset/
├── meta/
│   ├── info.json         # episode count, fps, feature shapes
│   ├── modality.json     # state/action/video structure
│   ├── tasks.jsonl       # task description
│   └── episodes.jsonl    # per-episode metadata
├── data/
│   └── chunk-000/
│       └── episode_000000.parquet  # state, action, timestamps
└── videos/
    └── chunk-000/
        └── observation.images.agentview/
            └── episode_000000.mp4
```

### Parquet row structure

```python
{
    "observation.state": np.float32[9],   # joint positions [7 arm + 2 gripper]
    "action": np.float32[9],              # target joint positions
    "timestamp": np.float32,             # seconds from episode start
    "frame_index": np.int64,             # step within episode
    "episode_index": np.int64,           # episode number
    "index": np.int64,                   # global frame index
    "task_index": np.int64,              # task label (0 for single-task)
}
```

### Convert from your format

```bash
# HDF5 with keys: action (N,9), images/agentview (N,H,W,3)
python src/training/genesis_to_lerobot.py \
    --input /path/to/hdf5_demos \
    --output /tmp/lerobot_dataset

# DAgger episodes (frames.npy + actions.npy + states.npy)
python src/training/dagger_to_lerobot.py \
    --input /path/to/dagger_dataset \
    --output /tmp/lerobot_dataset
```

---

## Pricing

| Tier | Compute | Included | Price |
|------|---------|----------|-------|
| **Starter** (free) | 1× A100 · up to 10k steps | Onboarding support | $0 |
| **Growth** | 1× A100 · up to 100k steps | Weekly sync, priority support | $50 |
| **Scale** | Up to 8× A100 DDP | Dedicated engineering, co-publication | Contact us |

Design partners get Starter tier free for initial pipeline validation.

---

## Supported Configurations

| Robot | DOF | Control | Tested |
|-------|-----|---------|--------|
| Franka Panda | 7+2 | Joint position | ✓ |
| UR5e | 6+2 | Joint position | ✓ |
| Kinova Gen3 | 7+2 | Joint position | ✓ |
| xArm7 | 7+2 | Joint position | ✓ |

Task types: pick-and-place, bin picking, assembly, push-to-goal, custom

---

## Get Started

**Email:** jun.q.qian@oracle.com
**GitHub:** github.com/qianjun22/roboticsai
**SDK:** `pip install oci-robot-cloud`

We respond within 24h and can typically provision your first training run within 48h of receiving a dataset sample.
