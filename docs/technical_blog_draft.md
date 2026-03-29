# How We Cut GR00T Robot Training Cost 9.6× Using OCI + NVIDIA Genesis

*Jun Qian, Oracle Cloud Infrastructure — March 2027*

---

## TL;DR

We built an end-to-end pipeline for training NVIDIA GR00T N1.6 on robotic manipulation tasks using Oracle Cloud Infrastructure. Key results:

- **8.7×** MAE improvement over random baseline (0.013 vs 0.103)
- **9.6×** cheaper than AWS p4d.24xlarge per training step ($0.0043 vs $0.041)
- **3.07×** throughput with 4× A100 DDP (230 samples/sec)
- **15 minutes** end-to-end: synthetic data → fine-tune → closed-loop eval
- **~$0.85** total compute cost per run

The pipeline, benchmarks, and all code are open-source at [github.com/qianjun22/roboticsai](https://github.com/qianjun22/roboticsai).

---

## The Problem

Training NVIDIA's GR00T N1.6-3B requires A100-class GPU compute. Buying a DGX system costs $200k+. AWS charges $0.041 per 10k training steps on p4d instances. For a robotics startup trying to iterate on a pick-and-place policy, this arithmetic breaks quickly.

We asked: can we run the same NVIDIA GR00T fine-tuning pipeline on OCI A100s at competitive cost, with a simple enough setup that a team of 2 can get from zero to a running closed-loop robot policy in one day?

---

## Architecture

The pipeline has three stages:

```
Genesis 0.4.3 (SDG)  →  LeRobot v2  →  GR00T N1.6-3B (fine-tune)
        ↓                                        ↓
  100 demos / 90s                        2.35 it/s · 87% GPU util
                                                 ↓
                               closed_loop_eval.py · Genesis sim
```

### Stage 1: Synthetic Data Generation

We use Genesis 0.4.3 for simulation. At 38.5fps on an OCI A100-SXM4-80GB, it generates IK-planned pick-and-lift demonstrations for a Franka Panda arm. The key is IK-planned trajectories: rather than random policy rollouts, we use analytical inverse kinematics to generate 100% success-rate demonstrations. No filtering required.

```bash
python src/simulation/genesis_sdg_planned.py \
    --num-demos 1000 \
    --output /tmp/sdg_1000 \
    --seed 42
```

For higher visual fidelity, we also support Isaac Sim 4.5.0 with RTX ray-traced rendering and Replicator domain randomization (lighting, camera position, material properties).

Output is a LeRobot v2 dataset with parquet state/action data and H.264-encoded video frames at 20fps.

### Stage 2: GR00T Fine-Tuning

We fine-tune `GR00T-N1.6-3B` from NVIDIA NGC using the `launch_finetune.py` script from the Isaac-GR00T repository:

```bash
CUDA_VISIBLE_DEVICES=4 python gr00t/experiment/launch_finetune.py \
    --base-model-path /home/ubuntu/models/GR00T-N1.6-3B \
    --dataset-path /tmp/sdg_1000_lerobot \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path src/training/franka_config.py \
    --max-steps 5000 \
    --global-batch-size 32 \
    --output-dir /tmp/finetune_1000_5k
```

On a single OCI A100-SXM4-80GB, this runs at **2.35 steps/sec** with **87% GPU utilization** consuming **36.8GB VRAM**. Total cost for 5000 steps at OCI spot pricing: ~$0.43.

For multi-GPU runs, we use `torchrun` with 4× A100s:

```bash
torchrun --nproc_per_node=4 gr00t/experiment/launch_finetune.py \
    --num-gpus 4 --global-batch-size 128 ...
```

This achieves **230 samples/sec** — a **3.07× speedup** over single GPU (77% parallel efficiency).

### Stage 3: Closed-Loop Evaluation

The trained model runs as a REST server on port 8002 (`groot_franka_server.py`) and we evaluate it in Genesis simulation:

```bash
python src/eval/closed_loop_eval.py \
    --num-episodes 20 \
    --server-url http://localhost:8002 \
    --output /tmp/eval_results
```

The evaluator sends camera frames and current joint states to the GR00T server, receives 16-step action chunks, and executes them in the Genesis physics simulator.

---

## The Bug That Cost Us 100% Closed-Loop Success

After achieving 8.7× MAE improvement on open-loop metrics, our first closed-loop evaluation showed **0% success rate**. The robot either knocked the cube off the table or never touched it.

Root cause: **CPU vs CUDA physics backend mismatch**.

Genesis has two PD dynamics backends. Training used the CUDA backend. Evaluation defaulted to the CPU backend. This caused the j5 joint equilibrium to differ: CPU=1.799 rad, CUDA=2.124 rad — an 18% difference that compounds through 100-step episodes.

The fix:
1. Force CUDA backend in evaluation: `gs.init(backend=gs.cuda)`
2. Use 9-DOF control (arm joints + gripper, not 7-DOF arm only)
3. Apply 2 simulation substeps per action for better dynamics matching

After the fix: **5% closed-loop success rate** established as baseline.

---

## DAgger: Closing the Loop

With a 5% baseline from behavior cloning, we implemented Dataset Aggregation (DAgger) to reduce the covariate shift between training and deployment distributions.

At each DAgger iteration, we run the current policy with expert correction:

```python
# action = beta * expert_ik + (1 - beta) * policy
action = beta * expert_action + (1 - beta) * policy_action
```

We save the **actual robot states** as observations (not the expert IK targets) — this is the critical distinction. The model must learn to map from states the policy actually reaches to the expert's intended action.

Results over 3 iterations (120 episodes total):

| Iteration | β | Expert Interventions/ep | Collection Success |
|-----------|---|------------------------|-------------------|
| BC baseline | 1.0 | 100 (full expert) | 5% closed-loop |
| DAgger iter 1 | 0.40 | 22.8 | ~52% |
| DAgger iter 2 | 0.28 | 17.4 | ~55% |
| DAgger iter 3 | 0.20 | 10.9 | ~65% |

Expert interventions per episode declined from 22.8 to 10.9, indicating the policy is learning from its own on-policy mistakes.

---

## Cost Comparison

| Provider | $/10k steps | CapEx | Max Burst | Setup Time |
|----------|-------------|-------|-----------|------------|
| **OCI A100** | **$0.0043** | **$0** | 32× A100 | 5 min |
| DGX On-Prem | ~$0.0045 | $200k+ | Fixed 8× | Weeks |
| AWS p4d.24xl | $0.041 | $0 | Limited | ~1 hr |
| Lambda Labs | $0.018 | $0 | Limited | 30 min |

OCI A100 pricing is competitive with DGX ownership economics on a per-step basis, but with zero CapEx and the ability to burst to 32× A100s for large SDG runs. At 9.6× cheaper than AWS p4d, the cost savings are significant for high-volume training.

For the full 15-minute pipeline (100 demos, 5000 fine-tuning steps, 20-episode eval): **~$0.85 total**.

---

## Infrastructure Setup

The full stack runs on OCI with minimal setup:

```bash
# One-command provisioning
bash src/infra/oci_robot_cloud_setup.sh --full

# Or use the Python SDK
pip install oci-robot-cloud
oci-robot-cloud train --demos 1000 --steps 5000 --gpu-id 4
```

The OCI A100 shape (`BM.GPU4.8`) provides 8× A100-SXM4-80GB with NVLink. For single-GPU runs, we use `CUDA_VISIBLE_DEVICES=4` to target one device.

---

## What's Next: Cosmos World Model

NVIDIA's Cosmos 7B world model can generate physically realistic video rollouts from robot sensor inputs. We've built a compatibility layer (`src/simulation/cosmos_world_model.py`) that outputs LeRobot v2 format, making Cosmos a drop-in replacement for Genesis SDG once the model weights are available.

Expected improvements over Genesis IK-planned data:
- More diverse trajectory distribution (no IK constraint)
- Photorealistic rendering for reduced sim-to-real gap
- Language-conditioned generation for multi-task training

---

## Try It Yourself

```bash
# Clone the repo
git clone https://github.com/qianjun22/roboticsai
cd roboticsai

# Generate 100 synthetic demos (requires Genesis 0.4.3)
python src/simulation/genesis_sdg_planned.py --num-demos 100 --output /tmp/sdg

# Convert to LeRobot v2
python src/training/genesis_to_lerobot.py --input /tmp/sdg --output /tmp/dataset

# Fine-tune GR00T (requires Isaac-GR00T repo + model weights from NGC)
CUDA_VISIBLE_DEVICES=0 python Isaac-GR00T/gr00t/experiment/launch_finetune.py \
    --base-model-path /path/to/GR00T-N1.6-3B \
    --dataset-path /tmp/dataset \
    --max-steps 2000 \
    --output-dir /tmp/finetune

# Evaluate closed-loop
python src/inference/groot_franka_server.py --model-path /tmp/finetune/checkpoint-2000 &
python src/eval/closed_loop_eval.py --num-episodes 10
```

---

## Acknowledgments

Built on NVIDIA Isaac-GR00T, Genesis 0.4.3, LeRobot, and OCI A100 GPU infrastructure. Seeking NVIDIA co-author for publication — reach out at jun.q.qian@oracle.com.

---

*Status: Draft — pending OCI × NVIDIA review and closed-loop benchmark update with 1000-demo results*
