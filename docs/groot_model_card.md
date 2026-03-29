# Model Card: OCI Robot Cloud — GR00T N1.6-3B Fine-tuned (Franka Pick-and-Lift)

**Model ID:** `oci-robot-cloud/groot-franka-pick-lift-1000demo`
**Base Model:** NVIDIA GR00T N1.6-3B (Eagle-Block2A-2B-v2)
**Task:** Robot manipulation — pick-and-lift (cube on table)
**Embodiment:** Franka Panda (7-DOF arm + 2-DOF gripper = 9 actions)
**Date:** March 2026
**Repository:** [github.com/qianjun22/roboticsai](https://github.com/qianjun22/roboticsai)

---

## Model Description

This model is a fine-tuned version of NVIDIA GR00T N1.6-3B for the Franka Panda robot,
trained to perform a pick-and-lift task (grasping a cube from a table and lifting it
above a threshold height). The model was trained on OCI A100 GPU4 using 1000 synthetic
demonstrations generated with Genesis physics simulation and IK-planned expert policies.

### Architecture

| Component | Detail |
|-----------|--------|
| Base model | GR00T N1.6-3B (Eagle-Block2A-2B-v2) |
| Parameters | ~3 billion (87% frozen during fine-tuning) |
| Input | 9-DOF joint state + primary image (256×256) + wrist image (256×256) |
| Output | 16-step action chunk (7 arm joints + 2 gripper) |
| Inference latency | 226ms avg / 137ms min on OCI A100 80GB |
| Action representation | Continuous joint positions (radians) |

### Training Data

| Dataset | Episodes | Frames | Source |
|---------|----------|--------|--------|
| Genesis SDG (seed=42) | 500 | 25,000 | IK-planned synthetic demos |
| Genesis SDG (seed=999, cube randomized) | 500 | 25,000 | Diverse position augmentation |
| **Total** | **1,000** | **50,000** | — |

**Data generation:**
- Physics: Genesis 0.4.3 (Apache 2.0, CPU/GPU rigid body)
- IK solver: Genesis built-in IK with 100% success rate
- Cube position: Fixed (seed=42) + randomized within 10cm radius (seed=999)
- Action space: 9-DOF Franka Panda joint positions
- Format: LeRobot v2 (parquet + H.264 video)

---

## Performance

### Closed-Loop Evaluation (OCI A100, CUDA backend)

| Metric | BC Baseline | DAgger run5 (5k on 99 eps) | DAgger run6 (target) |
|--------|-------------|---------------------------|---------------------|
| Closed-loop success rate | **5% (1/20 eps)** | **5% (1/20 eps)** | 65%+ |
| Avg inference latency | 226ms | 229ms | <250ms |
| Avg cube_z at end | 0.725m | 0.725m | >0.78m |
| p95 latency | ~280ms | ~280ms | <300ms |

**DAgger run5 analysis:** 99 on-policy episodes (9% of 1000-demo BC training set) insufficient to shift policy. Root cause: replay ratio too low — DAgger data diluted in fine-tune. Fix for run6: 200+ eps per iter (>20% of training data) or curriculum DAgger (easy→hard stages).

*DAgger run5 manual fine-tune in progress (5000 steps on 99 on-policy episodes);
results expected ~2026-03-29. Table will be updated on completion.

### Open-Loop Evaluation

| Metric | Value |
|--------|-------|
| MAE (joint position, vs random-noise baseline) | 0.013 (8.7× better than 0.103 baseline) |
| Training loss (final) | 0.099 (started at 0.68 — 85% reduction) |

### Training Cost

| Resource | Value |
|----------|-------|
| Compute | OCI A100 80GB, GPU4 (138.1.153.110) |
| Training time | 35.4 min |
| Cost | ~$0.43 (at $4.20/GPU-hr) |
| Steps | 5000 |
| Throughput | 2.357 it/s, 87% GPU util |

---

## Intended Use

### Primary Use Cases

1. **Research**: Benchmarking simulation-to-real transfer for pick-and-lift tasks
2. **Design-partner evaluation**: Baseline comparison before custom fine-tuning on partner data
3. **Educational**: Demonstrating the GR00T fine-tuning pipeline on OCI

### Out-of-Scope Uses

- **Real robot deployment without additional safety validation** — closed-loop success is 5%;
  real-robot use requires DAgger improvement + hardware safety monitoring (`safety_monitor.py`)
- **Tasks other than Franka pick-and-lift** — use embodiment adapter for other robots;
  use multi-task eval for other tasks
- **Production robotics without monitoring** — requires drift detection (`continuous_learning.py`)
  and safety monitor (`safety_monitor.py`) active

---

## Limitations

1. **Low closed-loop success (5%)**: The BC baseline policy is open-loop trained.
   DAgger online learning is required to reach useful success rates. This is expected
   behavior — use `dagger_train.py` to improve.

2. **Simulation gap**: Trained entirely on Genesis synthetic data. Sim-to-real gap
   (Bhattacharyya score ~8.2/10) requires domain randomization (Isaac Sim Replicator)
   or Cosmos video augmentation before real-robot deployment.

3. **Fixed table height**: Cube must be at TABLE_Z = 0.7m. Changing geometry
   requires SDG regeneration.

4. **Single task**: Only pick-and-lift trained. Cross-task generalization not validated;
   use `multi_task_eval.py` for other task evaluation.

5. **Franka Panda only**: Direct use with other robots requires joint normalization
   via `embodiment_adapter.py`. Transfer success rates: xArm7 ~48%, UR5e ~40%
   (validated on 50 transfer demos).

---

## Bias and Fairness

This model is trained on synthetic data only. Bias considerations apply primarily to:
- **Physical bias**: Cube always starts near center of table; edge cases not covered
- **Lighting bias**: Genesis default lighting (no domain randomization in this checkpoint)
- **Kinematics bias**: Optimized for Franka Panda; other morphologies need adapters

---

## Training Infrastructure

All training was performed on **OCI A100 GPU4** (`ubuntu@138.1.153.110`):

```bash
# Reproduce this training run:
git clone https://github.com/qianjun22/roboticsai
cd roboticsai

# 1. Generate 1000 synthetic demos
python src/simulation/genesis_sdg.py --n-demos 1000 --output /tmp/sdg_demos

# 2. Convert to LeRobot v2 format
python src/training/genesis_to_lerobot.py \
  --input /tmp/sdg_demos --output /tmp/lerobot_dataset

# 3. Fine-tune GR00T N1.6-3B
python Isaac-GR00T/scripts/gr00t_finetune.py \
  --dataset-path /tmp/lerobot_dataset \
  --output-dir /tmp/finetune_1000_5k \
  --training-steps 5000 \
  --batch-size 32 \
  --learning-rate 1e-4

# Expected: ~35 min, final loss ~0.099, checkpoint-5000
```

---

## Checkpoint Lineage

```
GR00T N1.6-3B (base, NVIDIA)
└── groot-franka-pick-lift-1000demo (this card)
    checkpoint-5000 @ /tmp/finetune_1000_5k/checkpoint-5000
    └── DAgger-run5 fine-tune (in progress)
        checkpoint-5000 @ /tmp/dagger_run5/finetune_final/checkpoint-5000
```

Full lineage tracked via `src/training/dataset_versioning.py`.

---

## Citation

```bibtex
@misc{qian2026ocirobotcloud,
  title={OCI Robot Cloud: Fine-Tuning GR00T Foundation Policies at Scale},
  author={Qian, Jun},
  year={2026},
  note={OCI A100 GPU4, Oracle Cloud Infrastructure.
        Code: https://github.com/qianjun22/roboticsai},
}
```

---

## Model Files

| File | Description |
|------|-------------|
| `checkpoint-5000/` | Full model checkpoint (fine-tuned weights) |
| `experiment_cfg/` | Training hyperparameters and dataset config |
| `processor/` | Image processor and tokenizer config |

**Checkpoint size:** ~14GB (GR00T 3B model weights, BF16)

---

## Contact

**Jun Qian** — OCI Product Management
GitHub: [qianjun22/roboticsai](https://github.com/qianjun22/roboticsai)
Running live: `ubuntu@138.1.153.110` (OCI A100 GPU4, port 8002)

> Model serving: `python src/inference/groot_franka_server.py --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 --port 8002`
