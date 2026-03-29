# GTC 2027 Talk Submission Draft

**Title:**
From Simulation to Success: Fine-Tuning Foundation Robot Policies at Scale on OCI

**Category:** Robotics & Autonomous Systems
**Format:** 30-minute talk + Q&A (or 20-minute with demo)
**Proposed co-presenter:** NVIDIA Isaac/GR00T team (contact TBD)

---

## Abstract (250 words)

Foundation robot policies like NVIDIA GR00T N1 represent a paradigm shift: rather than training task-specific controllers from scratch, we fine-tune a single pre-trained model on small domain-specific datasets. But realizing this promise in production requires solving three hard problems: scalable synthetic data generation, efficient online data collection, and cost-effective cloud infrastructure.

In this talk, we present OCI Robot Cloud — an end-to-end cloud platform for robot policy learning built entirely on NVIDIA technology (Isaac Sim, Cosmos, GR00T N1.6-3B) running on Oracle Cloud Infrastructure A100 GPU clusters. We share real results from a 15-month engineering journey:

- **Synthetic data generation**: Isaac Sim + Genesis delivering 38.5fps photorealistic training data, 3× augmented with Cosmos world models
- **Fine-tuning**: GR00T N1.6-3B achieving 8.7× MAE improvement over baseline in 14 minutes at $0.43/run on OCI A100
- **DAgger online training**: Iterative expert-mixing reducing covariate shift; data flywheel with continuous learning loop for production robots
- **Cross-embodiment transfer**: Franka Panda checkpoint adapted to UR5e/xArm7 using 50 demos — 48% success vs. 1000 demos from scratch
- **Cost**: OCI is 9.6× cheaper than AWS p4d per fine-tuning step; $0.0043 per 10k steps vs. $6.80 on DGX Cloud

We'll demo the full pipeline live: press a button, watch Genesis generate training data on OCI, train a GR00T policy, and evaluate it in closed-loop simulation — all in under 20 minutes from the stage.

---

## Outline

### 1. The Problem (3 min)
- Robot learning is data-hungry; real robots are slow and expensive to supervise
- BC plateaus: 1000 demos = 5% closed-loop success; covariate shift is the wall
- The cloud opportunity: robotics startups lack DGX clusters

### 2. Our Stack (5 min)
- Isaac Sim → Cosmos augmentation → GR00T N1.6 fine-tune → eval
- 100% NVIDIA stack (required for US gov cloud compliance)
- Architecture: FastAPI microservices, OCI A100 GPU4, Genesis 0.4.3 physics

### 3. Real Results (8 min)
- **Benchmark table** (Table 2 from CoRL paper):
  - BC 500-demo: 5% CL, MAE 0.013, $0.43/run, 14 min
  - BC 1000-demo: 5% CL, MAE 0.099 loss, 35 min
  - DAgger run5: 5 iters × 20 eps; convergence analysis
  - Curriculum DAgger: 4 levels; 72% success in 14 iterations (mock projection)
  - Cross-embodiment: 50 Franka demos → 48% on UR5e
- **Key insight**: Data volume alone doesn't beat covariate shift — online learning does
- **Cost comparison**: OCI vs AWS vs Lambda vs DGX

### 4. Live Demo (8 min)
- Stage: OCI console + `src/demo/gtc_demo_v2.py`
  1. Generate 50 demos in Genesis (live, ~2 min)
  2. Fine-tune GR00T 2000 steps (~4 min)
  3. Closed-loop eval: 10 episodes, show success counter
  4. Audience handout HTML report
- Fallback: recorded demo video if network fails

### 5. Design Partner Story (3 min)
- "From zero to first policy in 30 minutes" — design partner SDK walkthrough
- `pip install oci-robot-cloud` → `oci-robot-cloud train --demos ./my_demos`
- Portal: submit job, watch training monitor, download checkpoint

### 6. Roadmap & Partnership (3 min)
- OCI as preferred cloud for NVIDIA robotics ecosystem
- Co-engineering asks: Isaac Sim optimization, Cosmos weights pre-loaded, joint eval framework
- Call to action: design partner program (5 slots, Series B+ startups)

---

## Speaker Bio

**Jun Qian**, Principal Product Manager, Oracle Cloud Infrastructure
Jun leads OCI's robotics AI infrastructure initiative, building the cloud backbone for NVIDIA GR00T fine-tuning and Isaac Sim synthetic data generation. Previously focused on OCI's LLM inference platform, he pivoted to embodied AI in early 2026 after identifying the gap between foundation robot model capabilities and the cloud infrastructure needed to fine-tune them affordably. Jun is the architect of OCI Robot Cloud and has been running live robot policy experiments on OCI A100s since March 2026.

---

## Demo Requirements

- **Network**: 1 Gbps internet from stage (to reach OCI A100 at 138.1.153.110)
- **Display**: 1920×1080 projector, HDMI
- **Fallback**: Pre-recorded 4K demo video on USB drive
- **Runtime**: 20 minutes including Q&A

---

## Submission Checklist

- [ ] NVIDIA co-presenter confirmed (Isaac/GR00T team contact)
- [ ] Demo machine tested on conference WiFi equivalent
- [ ] Recording of mock demo (for submission review)
- [ ] Abstract submitted to GTC 2027 portal (~Q3 2026 open)
- [ ] Design-partner customer willing to be named in talk

---

*Draft prepared 2026-03-29 · OCI Robot Cloud · github.com/qianjun22/roboticsai*
