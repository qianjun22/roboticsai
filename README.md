# roboticsai

Open-source inference and simulation stack for robot foundation models.

## What it does

- Serves robot foundation models (OpenVLA, π0, GR00T) via a low-latency REST API
- Connects to LeRobot / MetaWorld / Isaac Sim simulation environments
- ROS2-compatible action output

## Quick Start

```bash
# Install
pip install -r src/inference/requirements.txt
pip install -r src/simulation/requirements.txt

# Serve OpenVLA on A100
python3 src/inference/server.py --model openvla/openvla-7b

# Run simulation loop
python3 src/simulation/inference_loop.py --env xarm --server-url http://localhost:8000

# Multi-task MetaWorld demo (6 tasks auto-cycling)
python3 src/simulation/metaworld_demo.py --server-url http://localhost:8000

# Local dev (no GPU) — mock server
python3 src/simulation/mock_server.py
```

## Stack

```
Robot Foundation Model (OpenVLA / π0 / GR00T)
            ↓
Inference API  (FastAPI, GPU-optimized, BF16)
            ↓
Simulation  (LeRobot · MetaWorld · Isaac Sim)
            ↓
ROS2 Client SDK
```

## Environments

| Env | Tasks | GPU needed |
|-----|-------|------------|
| LeRobot (xarm, aloha, pusht) | 3 | No — CPU |
| MetaWorld | 50 | No — CPU |
| Isaac Sim | unlimited | Yes — NVIDIA |

## Models

| Model | Params | VRAM (BF16) | Notes |
|-------|--------|-------------|-------|
| OpenVLA-7B | 7B | 14GB | A100 40G recommended |
| OpenVLA-7B (INT4) | 7B | ~5GB | Dev / 8GB GPU |
| π0 | 3B | 6GB | Physical Intelligence |
| GR00T N1 | TBD | A100 80G | NVIDIA humanoid model |

## Directory

```
src/
  inference/    # Model serving — OpenVLA inference API
  simulation/   # LeRobot, MetaWorld, Isaac Sim environments
  sdk/          # ROS2 client SDK
```
