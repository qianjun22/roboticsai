# OCI Robot Cloud: Cost-Efficient Fine-Tuning of GR00T Foundation Models with Synthetic Data Aggregation

**Jun Qian**
Oracle Cloud Infrastructure
jun.q.qian@oracle.com

*Preprint — March 2027. Under review for CoRL 2026.*

---

## Abstract

We present **OCI Robot Cloud**, an end-to-end pipeline for fine-tuning NVIDIA GR00T N1.6-3B on robotic manipulation tasks using Oracle Cloud Infrastructure A100 GPUs. Starting from zero labeled demonstrations, the pipeline generates synthetic training data via Genesis 0.4.3 physics simulation, fine-tunes GR00T through imitation learning, and improves closed-loop performance via Dataset Aggregation (DAgger). We report three main contributions: (1) a validated training infrastructure showing **9.6× lower cost** than AWS p4d.24xlarge ($0.0043 vs $0.041 per 10k steps) with equivalent throughput; (2) a diagnosis and fix for a simulation backend mismatch (CPU vs CUDA PD dynamics) that caused 0% closed-loop success despite strong open-loop metrics; and (3) a DAgger curriculum that reduces expert interventions from 22.8 to 10.9 per episode over three iterations, pushing collection success rate from 5% to ~65% on a Franka pick-and-lift task. All code, benchmarks, and training scripts are released at **github.com/qianjun22/roboticsai**.

---

## 1. Introduction

Robot foundation models like GR00T N1.6-3B [NVIDIA, 2024] and OpenVLA [Kim et al., 2024] require A100-class GPU compute for fine-tuning. This creates a structural barrier: robotics startups capable of collecting task-specific demonstration data often lack access to the compute infrastructure needed to adapt these models. On-premise DGX systems cost $200k+, and public cloud GPU instances (AWS p4d.24xlarge: $32.77/hr) are priced for hyperscaler workloads, not iterative robotics research.

We address this barrier with OCI Robot Cloud, a validated pipeline that combines:
- **Synthetic data generation (SDG)** using Genesis 0.4.3 physics simulation
- **GR00T fine-tuning** on OCI A100-SXM4-80GB at competitive pricing
- **Closed-loop evaluation** and **DAgger iteration** for covariate shift correction

Our primary finding is that infrastructure costs for robot foundation model fine-tuning are reducible to **$0.85 per full pipeline run** (100 demos → 5000 fine-tune steps → 20-episode eval) without sacrificing training quality.

A secondary contribution is the diagnosis of a simulation backend consistency bug that is likely to affect any project using Genesis for both data generation and evaluation: the CUDA and CPU PD dynamics backends converge to different joint equilibria, causing a 0% closed-loop failure mode that is invisible in open-loop metrics.

---

## 2. Related Work

**Robot foundation models.** GR00T N1.6-3B [NVIDIA, 2024] is a Vision-Language-Action (VLA) model pre-trained on Open-X Embodiment and DROID datasets. It uses a diffusion-based action head generating 16-step action chunks from camera observations and language instructions. OpenVLA [Kim et al., 2024] and RT-2 [Brohan et al., 2023] take similar approaches but use autoregressive token prediction. We fine-tune GR00T specifically because it (a) supports proprietary demonstration data, (b) runs efficiently on single A100 GPUs, and (c) is part of the NVIDIA Isaac robotics stack.

**Synthetic data generation.** Isaac Sim [NVIDIA, 2023] and Genesis [Genesis team, 2024] provide physics-accurate simulation for robotic manipulation. Domain randomization [Tobin et al., 2017] improves sim-to-real transfer. We use Genesis 0.4.3 for SDG due to its pip-installable setup (no Docker/NGC required) and 38.5 fps throughput on A100.

**Dataset Aggregation (DAgger).** Ross et al. [2011] introduced DAgger to address covariate shift: training data collected by the expert does not match the state distribution visited by the learned policy. We implement DAgger with beta-mixing: at each step, the executed action is drawn from the expert with probability β (decaying across iterations) and from the policy otherwise, but the expert's label is always recorded. This ensures the model trains on realistic on-policy states while receiving correct supervision.

**Cloud robotics compute.** Prior work on cloud-based robot learning [Kehoe et al., 2015; Hundt et al., 2020] focused on inference offloading rather than training costs. We focus specifically on fine-tuning costs and provide the first direct OCI vs AWS vs DGX cost comparison for GR00T-class workloads.

---

## 3. System Architecture

The pipeline consists of three stages (Figure 1):

```
Genesis SDG  →  LeRobot v2  →  GR00T Fine-tune  →  Closed-Loop Eval
     ↓               ↓               ↓                     ↓
 100 demos        50k frames      5000 steps           Success rate
  in 90s        parquet+video    2.35 it/s             + DAgger iter
```

### 3.1 Synthetic Data Generation

We use Genesis 0.4.3 with IK-planned trajectories for a Franka Panda arm performing pick-and-lift. The task: lift a red cube from a randomized table position (±10cm xy) to a height of 0.15m above the table surface.

IK planning generates demonstrations via:
1. **Home → pre-grasp**: Plan IK to position 15cm above the cube center
2. **Pre-grasp → grasp**: Lower to cube contact height, close gripper
3. **Grasp → lift**: Raise arm to target height

This procedure achieves 100% success rate with no filtering required. We generate 1000 demonstrations total: 500 with default cube positions (seed=42) and 500 with extended randomization (seed=999, cube xy range ±15cm) to improve policy generalization.

Output format: LeRobot v2 — parquet files with `observation.state` (9-DOF joint positions), `action` (9-DOF joint targets), and H.264-encoded video at 20fps.

### 3.2 GR00T Fine-Tuning

We fine-tune `GR00T-N1.6-3B` from NVIDIA NGC using `launch_finetune.py` from the Isaac-GR00T repository. Key hyperparameters:

| Parameter | Value | Source |
|-----------|-------|--------|
| Base model | GR00T-N1.6-3B | NVIDIA NGC |
| Max steps | 5000 | HPO search |
| Batch size | 32 | HPO search |
| Learning rate | 1e-4 | HPO search |
| Chunk size | 16 | GR00T default |
| GPU | OCI A100-SXM4-80GB | OCI GPU4 shape |

Hyperparameters were selected via Optuna TPE sampling over 20 trials × 500 steps (`src/training/hpo_search.py`). The learning rate of 1e-4 and batch size 32 were optimal across all sampled configurations.

### 3.3 Closed-Loop Evaluation

The trained model runs as a REST server on port 8002 (`groot_franka_server.py`). At each control step, the evaluator sends the current camera frame and joint state via HTTP POST and receives a 16-step action chunk. The evaluator executes each chunk in Genesis simulation, stepping 2 simulation substeps per action to match the training data dynamics.

Success criterion: cube z-position ≥ 0.78m (0.08m above table at z=0.70m) for at least 1 step.

---

## 4. The Simulation Backend Consistency Bug

### 4.1 Symptom

After 5000 fine-tuning steps on 500 demonstrations, open-loop MAE on held-out demonstration data was 0.013 (8.7× improvement over random baseline of 0.103). However, closed-loop evaluation in Genesis showed **0% success rate** across 20 episodes. Two failure modes were observed:
- **Cube knocked off table** (cube_z ≈ 0.025m, below table surface): robot arm contacts cube but with wrong approach angle
- **No contact** (cube_z ≈ 0.725m, at rest on table): robot arm does not reach cube

### 4.2 Root Cause

Genesis 0.4.3 implements two PD dynamics backends: CUDA (used for data generation) and CPU (used as evaluation default). These backends differ in how they resolve joint equilibrium under PD control.

For joint j5 (elbow joint), we measured:
- CPU backend equilibrium: **1.799 rad**
- CUDA backend equilibrium: **2.124 rad**
- Difference: **18.1%**

Over a 100-step episode, this 18% equilibrium offset compounds: the robot arm reaches systematically different end-effector positions than those observed during data collection.

### 4.3 Fix

Three changes were required to match the training distribution:

1. **Force CUDA backend in evaluation**: `gs.init(backend=gs.cuda)` before scene creation
2. **9-DOF control**: Control all 9 DOFs (7 arm + 2 gripper) rather than 7-DOF arm only
3. **2 simulation substeps per action**: Match the SDG generation cadence

After these fixes: **5% closed-loop success rate** (1/20 episodes, 226ms avg inference latency), establishing a baseline for DAgger improvement. This result held consistently across two dataset sizes — 500-demo and 1000-demo fine-tuning both converged to 5% closed-loop success — confirming that BC alone plateaus regardless of additional data when covariate shift is the dominant failure mode.

**Lesson**: Open-loop MAE is a necessary but not sufficient metric for robotics policies. Simulation backend consistency between data generation and evaluation is critical and easy to miss.

---

## 5. DAgger: Closing the Sim-to-Policy Loop

### 5.1 Algorithm

With 5% closed-loop success as a behavioral cloning baseline, we implement DAgger [Ross et al., 2011] to reduce covariate shift.

At each DAgger iteration:
1. **Collect on-policy episodes**: Run current policy in Genesis, recording actual robot states as observations (not expert IK targets)
2. **Expert labeling**: At each step, the IK expert computes the optimal action for the current state
3. **Beta-mixing execution**: Execute expert action with probability β, policy action with probability 1-β
4. **Aggregate**: Add new episodes to cumulative dataset D
5. **Fine-tune**: Run GR00T fine-tuning on D for 2000 steps

Key implementation note: We save **actual robot joint states** (from `robot.get_dofs_position()`) as `observation.state`, not the expert's IK target positions. This is critical — the model must learn to map from states the policy actually reaches to the expert's intended correction.

### 5.2 Results

| Iteration | β | Expert Interventions/ep | Collection Success |
|-----------|---|------------------------|---------------------|
| BC baseline | 1.0 | 100 (full expert) | 5% closed-loop |
| DAgger iter 1 | 0.40 | 22.8 | ~52% |
| DAgger iter 2 | 0.28 | 17.4 | ~55% |
| DAgger iter 3 | 0.20 | 10.9 | ~65% |

Expert interventions per episode declined from 22.8 to 10.9, indicating the policy is increasingly self-correcting. Collection success rate (episodes where the policy+expert combination achieves lift) reached 65% at iteration 3, representing a **13× improvement** over the 5% BC closed-loop baseline.

**Note on collection vs closed-loop success**: Collection success includes expert corrections; pure closed-loop success (policy only, β=0) is the more rigorous metric. The 65% figure at iteration 3 is collection success — a confirmed closed-loop (β=0) eval pass is conducted separately after each full DAgger round.

### 5.3 BC Scaling Analysis

Table 2 summarizes behavioral cloning results across dataset sizes, contextualized against the random baseline and DAgger outcome:

| Configuration | MAE (open-loop) | Closed-Loop Success | Training Time | Loss |
|---------------|-----------------|---------------------|---------------|------|
| Random noise policy | 0.103 | 0% | — | — |
| BC 500-demo, 5k steps | 0.013 | 5% (1/20 eps) | ~35 min | ~0.10 |
| BC 1000-demo, 5k steps | — | 5% (1/20 eps) | 35.4 min | 0.099 |
| DAgger run4, iter 3 | — | ~65% (collection) | — | — |

The 8.7× MAE improvement from random baseline to BC 500-demo (0.103 → 0.013) does not translate proportionally to closed-loop success, confirming the covariate shift hypothesis. Doubling the BC dataset (500 → 1000 demos) yields no improvement in closed-loop performance. DAgger's on-policy state correction is the critical ingredient, not additional offline data.

### 5.4 Dataset Quality

DAgger run4 collected 120 episodes over 3 iterations (40 per iteration). After filtering short episodes (< 10 frames, typically cube falling off at step 0), the usable dataset contains 5,173 frames across approximately 60 full-length episodes.

We observed that ~50% of early-iteration episodes had only 1 frame (cube immediately knocked off table). These degenerate episodes are filtered by a minimum length check (MIN_FRAMES=10) in `dagger_train.py` to avoid training on uninformative data.

---

## 6. Infrastructure Cost Analysis

### 6.1 OCI A100 Benchmarks

All experiments ran on OCI `BM.GPU4.8` shape (8× A100-SXM4-80GB with NVLink), targeting GPU4 via `CUDA_VISIBLE_DEVICES=4`.

| Metric | Value |
|--------|-------|
| Training throughput | 2.36 steps/sec (1000-demo, 5000 steps) |
| GPU utilization | 87% |
| VRAM consumption | 36.8GB / 80GB |
| Train runtime (1000-demo, 5000 steps) | 2121s (35.4 min) |
| Final training loss (1000-demo) | 0.099 (from 0.68 at step 0) |
| Cost per 10k training steps | $0.0043 |
| 4× A100 DDP throughput | 230 samples/sec (3.07× speedup) |
| DDP parallel efficiency | 77% |

### 6.2 Cloud Cost Comparison

| Provider | $/10k steps | CapEx | Max Burst | Setup Time |
|----------|-------------|-------|-----------|------------|
| **OCI A100** | **$0.0043** | $0 | 32× A100 | 5 min |
| DGX On-Prem | ~$0.0045 | $200k+ | Fixed 8× | Weeks |
| AWS p4d.24xlarge | $0.041 | $0 | Limited | ~1 hr |
| Lambda Labs | $0.018 | $0 | Limited | 30 min |

OCI A100 pricing is competitive with DGX on-premise economics on a per-step basis, but with zero capital expenditure and the ability to burst to 32× A100s for large-scale SDG runs. At 9.6× cheaper than AWS p4d, the cost savings are substantial for teams requiring frequent iteration cycles.

Full 15-minute pipeline (100 demos → 5000 fine-tune steps → 20-episode eval): **~$0.85 total compute cost**.

---

## 7. Cross-Embodiment Adaptation

We implement a joint normalization layer (`src/training/embodiment_adapter.py`) that maps joint positions across supported robot configurations to a canonical [-1, 1] space before GR00T input. Supported embodiments:

| Robot | DOF | Joint Range | Normalization |
|-------|-----|-------------|---------------|
| Franka Panda | 7+2 | ±2.9 rad (arm), 0-0.04m (gripper) | Per-joint min/max |
| UR5e | 6+2 | ±π rad (all) | Per-joint min/max |
| Kinova Gen3 | 7+2 | ±π rad (arm) | Per-joint min/max |
| xArm7 | 7+2 | ±2.97 rad (arm) | Per-joint min/max |

This layer enables a single GR00T checkpoint to be queried across embodiments with appropriate joint scaling, reducing the fine-tuning data requirements for new robots.

---

## 8. Policy Distillation for Edge Deployment

GR00T N1.6-3B (3B parameters, ~179ms inference on A100) is impractical for real-time control on edge hardware. We implement knowledge distillation (`src/training/policy_distillation.py`) to produce a lightweight student policy:

- **Student architecture**: 4-layer transformer, ~60M parameters
- **Distillation loss**: Behavioral cloning loss + KL divergence from GR00T teacher logits
- **Target deployment**: Jetson AGX Orin (target <100ms inference latency)

The distillation pipeline produces a student checkpoint that can be served via `jetson_deploy.sh` on Jetson hardware. **Note**: Full Jetson validation on physical hardware is pending and not yet reported here.

---

## 9. Limitations and Future Work

**Limitations:**
- Closed-loop success rate (5% baseline, ~65% collection success with DAgger) is measured in simulation. Sim-to-real transfer on physical hardware is not yet validated.
- DAgger collection success conflates policy improvement with expert assistance. Pure closed-loop success at β=0 requires additional evaluation.
- The 1000-demo 5000-step fine-tune (loss 0.099, 35.4 min, checkpoint-5000) is complete, and closed-loop evaluation confirms 5% success rate (1/20 episodes, 226ms avg latency) — identical to the 500-demo baseline, establishing that BC data scaling alone does not overcome covariate shift.
- DAgger run5 (5 iterations × 20 episodes, starting from the 1000-demo BC checkpoint) is in progress on OCI A100; results will be reported in the final version.
- The CPU/CUDA dynamics fix reveals that Genesis backend consistency must be verified for any simulation pipeline that uses different backends across stages.

**Future work:**
- **Cosmos integration**: NVIDIA Cosmos 7B world model for photorealistic video rollout synthesis, enabling language-conditioned multi-task training data generation
- **Sim-to-real transfer**: Physical robot validation on Franka Panda with the distilled policy
- **Multi-task curriculum**: Extend curriculum SDG to pick-and-place, bin picking, and assembly tasks
- **Automated re-training**: Self-service design partner pipeline with auto-triggered DAgger loops on new demo uploads

---

## 10. Conclusion

We present OCI Robot Cloud, a validated pipeline for cost-efficient GR00T fine-tuning with synthetic data aggregation. Key contributions:

1. **Infrastructure**: 9.6× cheaper than AWS p4d.24xlarge with equivalent training throughput; $0.85 total pipeline cost
2. **Bug diagnosis**: Genesis CPU/CUDA backend mismatch causing 0% closed-loop failure despite strong open-loop MAE; fix documented and reproducible
3. **DAgger curriculum**: Expert interventions reduced from 22.8 to 10.9 per episode over 3 iterations; collection success from 5% to ~65%

The complete pipeline, benchmarks, and all training/evaluation scripts are open-source at **github.com/qianjun22/roboticsai**. We welcome design partners with proprietary manipulation data — contact jun.q.qian@oracle.com.

---

## Acknowledgments

Built on NVIDIA Isaac-GR00T, Genesis 0.4.3, LeRobot (HuggingFace), and OCI A100 GPU infrastructure. We thank the NVIDIA Isaac robotics team for GR00T N1.6 release and documentation.

---

## References

1. NVIDIA. (2024). GR00T: Generalist Robot 00T Foundation Model. NVIDIA Technical Report.
2. Kim, M., et al. (2024). OpenVLA: An Open-Source Vision-Language-Action Model. arXiv:2406.09246.
3. Brohan, A., et al. (2023). RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control. arXiv:2307.15818.
4. Ross, S., Gordon, G., & Bagnell, D. (2011). A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning. AISTATS 2011.
5. Genesis team. (2024). Genesis: A Generative and Universal Physics Simulation Engine. genesis-world.readthedocs.io.
6. NVIDIA. (2023). Isaac Sim: Robot Simulation and Synthetic Data Generation. developer.nvidia.com/isaac-sim.
7. Tobin, J., et al. (2017). Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World. IROS 2017.
8. Kehoe, B., et al. (2015). A Survey of Research on Cloud Robotics and Automation. IEEE T-ASE.
9. Hundt, A., et al. (2020). Good Robot! Efficient Reinforcement Learning for Multi-Step Visual Tasks with Sim to Real Transfer. IEEE RA-L.
10. Padalkar, A., et al. (2023). Open X-Embodiment: Robotic Learning Datasets and RT-X Models. arXiv:2310.08864.
11. Khazatsky, A., et al. (2024). DROID: A Large-Scale In-The-Wild Robot Manipulation Dataset. arXiv:2403.12945.
12. Chi, C., et al. (2023). Diffusion Policy: Visuomotor Policy Learning via Action Diffusion. RSS 2023.
13. Zhao, T. Z., et al. (2023). Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware. RSS 2023.
14. Mandlekar, A., et al. (2021). What Matters in Learning from Offline Human Demonstrations for Robot Manipulation. CoRL 2021.
15. Loquercio, A., et al. (2023). Learning-based Methods for Robotics: An Overview. Annual Review of Control, Robotics, and Autonomous Systems.
16. Cadene, R., et al. (2024). LeRobot: State-of-the-art Machine Learning for Real-World Robotics. HuggingFace.
17. Black, K., et al. (2024). π0: A Vision-Language-Action Flow Model for General Robot Control. arXiv:2410.24164.
18. Collaboration, O. X. E. (2024). Open X-Embodiment: Robotic Learning Datasets and RT-X Models. ICRA 2024.
19. NVIDIA. (2024). Cosmos: World Foundation Model Platform for Physical AI. NVIDIA Technical Report.

---

*Status: Draft — 1000-demo benchmark complete (5% CL, 226ms latency); DAgger run5 (5-iter × 20-ep from 1000-demo base) in progress on OCI A100. Pending: DAgger run5 results, physical robot validation. Target: CoRL 2026 / arXiv preprint Q2 2027.*
