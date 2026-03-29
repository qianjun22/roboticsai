# OCI Robot Cloud × NVIDIA Isaac/GR00T: Co-Engineering Partnership Proposal

**Date:** March 2026
**From:** Jun Qian, Oracle Cloud Infrastructure — Robotics AI
**To:** NVIDIA Isaac/GR00T Team
**Classification:** Confidential — Partner Review

---

## Executive Summary

- **Proven NVIDIA stack on OCI.** OCI Robot Cloud already runs GR00T N1.6-3B inference (226ms latency), Genesis 0.4.3 SDG, and Isaac Sim 4.5.0 RTX domain randomization on OCI A100 instances — all using the full NVIDIA software stack, US-origin, FedRAMP-ready.
- **Real results at production cost.** End-to-end training pipeline (SDG → fine-tune → eval) costs $0.85 per run on OCI BM.GPU.A100; DAgger closed-loop success reaches 65% on pick-and-lift with 1,000 demonstrations and 2,000 training steps.
- **Ask: 3 targeted co-engineering items + joint GTM.** We need Cosmos weight access, Isaac Sim 5.0 early access, and GR00T fine-tuning (not inference-only) model access. In return, OCI provides dedicated A100 compute for joint evaluation, co-authors NVIDIA blog posts, and co-presents at GTC 2027.

---

## 1. Current Integration State

OCI Robot Cloud is not a proof-of-concept — it is a running system with measurable performance numbers. The following components are in production on `github.com/qianjun22/roboticsai`.

### 1.1 GR00T N1.6-3B — Inference and Fine-Tuning

| Metric | Value |
|--------|-------|
| Inference latency (A100, batch=1) | 226 ms |
| Fine-tuning throughput | 2.35 it/s (single A100) |
| Multi-GPU DDP throughput (8× A100) | 3.07× linear scaling |
| Training cost (1,000 demos, 2,000 steps) | $0.85 end-to-end |
| Final MAE (GR00T fine-tuned vs baseline) | 0.013 vs 0.103 (8.7× improvement) |
| Closed-loop success with DAgger | 65% (pick-and-lift) |

The fine-tuning pipeline uses the published GR00T inference model as starting weights. We have implemented DAgger (Dataset Aggregation) with a short-episode filter (`MIN_FRAMES=10`) and an auto-retrain trigger. The pipeline runs end-to-end: Genesis SDG → LeRobot dataset format → GR00T fine-tune → closed-loop eval.

### 1.2 Genesis 0.4.3 — Synthetic Data Generation

| Metric | Value |
|--------|-------|
| Simulation throughput | 38.5 fps (parallel envs) |
| IK motion planning success | 100% |
| Episode generation cost | <$0.001 per episode |
| Dataset format | LeRobot HDF5 (direct GR00T input) |

Genesis provides fast CPU-based SDG for initial dataset generation. We have implemented inverse-kinematics motion-planned trajectories that produce high-quality, collision-free demonstrations at scale.

### 1.3 Isaac Sim 4.5.0 — RTX Domain Randomization

Isaac Sim with Replicator is integrated for domain randomization over lighting, texture, object pose, and camera extrinsics. Current configuration produces randomized episodes at ~2fps (RTX rendering), suitable for sim-to-real transfer evaluation. Isaac Sim runs inside a Docker container on OCI BM.GPU.A100 instances.

### 1.4 Cosmos World Model — Integration Scaffold

The Cosmos integration scaffold is implemented: the pipeline can route episodes through a Cosmos-based world model for video-based domain randomization. **This path is blocked pending Cosmos weight access** (see Co-Engineering Item 1). The code is ready; we need the model weights to complete the integration.

### 1.5 Stack Summary

| Component | Version | Status |
|-----------|---------|--------|
| GR00T N1.6 | 3B params | Running — inference + fine-tune |
| Genesis | 0.4.3 | Running — SDG at scale |
| Isaac Sim | 4.5.0 | Running — RTX domain randomization |
| Cosmos | 7B params | Scaffold ready — **weights blocked** |
| OCI compute | BM.GPU.A100 (8× A100 80GB) | Available on-demand |
| Compliance | US-origin, FedRAMP-ready | Verified |

---

## 2. Proposed Co-Engineering Work Items

### Item 1: Cosmos Weight Access

**The problem.** The Cosmos 7B world model (~40GB on NGC) is gated behind an access request. Our integration scaffold is complete — we can route synthetic episodes through Cosmos for photorealistic domain randomization — but we cannot pull the weights via `ngc registry model download` without an approved NGC access token for the Cosmos model family.

**What we need from NVIDIA.** An approved NGC download token for the Cosmos world model weights (7B, ~40GB). Alternatively, an engineer introduction to the Cosmos team to fast-track the access request.

**What OCI provides.** A dedicated BM.GPU.A100 instance (8× A100 80GB, 640GB total VRAM) for joint Cosmos evaluation. We will run the full SDG → Cosmos augmentation → GR00T fine-tune → eval pipeline and share all results with the NVIDIA Cosmos team.

**Target metric.** Sim-to-real gap score < 3.0 (current baseline without Cosmos: 8.2; industry target with Cosmos augmentation: 2.5–3.0).

**Estimated effort.** 1 engineer-day NVIDIA (access + brief integration call). 2 engineer-weeks OCI (full Cosmos pipeline integration and evaluation).

---

### Item 2: Isaac Sim 5.0 Early Access

**The problem.** Isaac Sim 4.5.0 RTX rendering runs at ~2fps for domain-randomized episode generation — sufficient for prototyping, but too slow for production-scale SDG (50k episodes). Isaac Sim 5.0 is expected to include significant rendering throughput improvements and an updated Replicator API.

**What we need from NVIDIA.** Early access to the Isaac Sim 5.0 Docker image (pre-release) to benchmark RTX Replicator domain randomization throughput at scale.

**What OCI provides.** 8× A100 compute for the joint benchmark. We will run 10,000 domain-randomized episodes using the Isaac Sim 5.0 build and publish results (with NVIDIA co-authorship) showing OCI as the preferred cloud for Isaac Sim 5.0 workloads.

**Target metric.** 50,000 domain-randomized episodes in < 24 hours on an 8× A100 OCI instance. This requires approximately 2fps → 10fps rendering throughput improvement from Isaac Sim 5.0.

**Estimated effort.** 0.5 engineer-days NVIDIA (Docker image share + API delta notes). 1 engineer-week OCI (port pipeline to 5.0 API, run benchmarks).

---

### Item 3: GR00T N1.6 Training-Weight Access

**The problem.** The publicly available GR00T N1.6 artifact is the inference-only model checkpoint. Fine-tuning from this starting point limits the achievable success rate because the base weights were not trained with DROID/Open-X trajectory diversity — they are post-trained for inference efficiency.

**What we need from NVIDIA.** A research collaboration with the GR00T team to access the training-phase weights (pre-distillation, DROID/Open-X base) for fine-tuning. This is not a general weight release — we are requesting a bilateral research agreement where OCI provides compute and evaluation results in exchange for access to the base training weights.

**What OCI provides.** Full fine-tuning pipeline (Genesis SDG → LeRobot → GR00T fine-tune → DAgger → closed-loop eval), dedicated A100 compute, and quantitative results comparing inference-weight fine-tuning vs. training-weight fine-tuning across 500, 1000, and 2000 demonstrations.

**Target metric.** > 80% closed-loop success on pick-and-lift with 1,000 demonstrations and DAgger, using DROID/Open-X base weights. Current baseline: 65% with inference-only weights.

**Estimated effort.** 2 engineer-days NVIDIA (research agreement + weight handoff). 3 engineer-weeks OCI (fine-tuning experiments across demo counts, ablation study, paper contribution).

---

## 3. Joint GTM Plan

| Quarter | Activity | NVIDIA Role | OCI Role |
|---------|----------|-------------|----------|
| Q3 2026 | NVIDIA Developer Blog: "GR00T Fine-Tuning on OCI" | Co-author, publish on developer.nvidia.com | Draft author, OCI benchmark numbers |
| Q3 2026 | NGC partner listing: OCI as GR00T-optimized cloud | NVIDIA partner portal | Technical integration validated |
| Q4 2026 | AI World Shanghai — joint booth presence | Isaac/GR00T demo hardware (Jetson AGX) | OCI cloud backend, live fine-tuning demo |
| Q1 2027 | GTC 2027 joint talk: "From Simulation to Production Robot Training" | GR00T team co-presenter | Primary presenter (Jun Qian) |
| Q2 2027 | NVIDIA Partner Portal: OCI as preferred cloud for Isaac/GR00T | Partner listing + badge | Technical reference architecture |

The NVIDIA Developer Blog post is already drafted (`/docs/technical_blog_draft.md`). The GTC 2027 talk proposal is prepared (`/docs/gtc_proposal_draft.md`). Both are ready to share with the NVIDIA team for review.

---

## 4. Success Metrics

All three co-engineering items have measurable completion criteria:

| Item | Metric | Current Baseline | Target |
|------|--------|-----------------|--------|
| Cosmos integration | Sim-to-real gap score | 8.2 (no Cosmos) | < 3.0 |
| Isaac Sim 5.0 scale | Domain-randomized episodes in 24h (8× A100) | ~8,640 (2fps) | > 50,000 |
| GR00T training weights | Closed-loop success @ 1k demos + DAgger | 65% | > 80% |

Secondary metrics tracked across all items:
- End-to-end pipeline cost per trained model: target < $5.00 (current: $0.85, will increase with Cosmos augmentation)
- Fine-tuning GPU utilization: current 87% (BM.GPU.A100), target maintained at > 85% with Isaac Sim 5.0 integration
- Time-to-first-trained-model for new robot task: target < 4 hours from raw URDF to deployed policy

---

## 5. Resource Ask from NVIDIA

This is a targeted, low-overhead ask:

1. **2 engineer-days** to unblock Cosmos weight download and provide a 30-minute integration call with the Cosmos team.
2. **Isaac Sim 5.0 early access Docker image** — no source code required, Docker pull token sufficient.
3. **1 introduction** to 1–2 NVIDIA robotics startup ecosystem companies (e.g., companies in NVIDIA Inception with active fine-tuning workloads) as first design-partner customers for OCI Robot Cloud.

OCI commits in return:
- Dedicated BM.GPU.A100 instance for joint evaluation (no charge to NVIDIA)
- All benchmark results shared with NVIDIA teams prior to publication
- Co-authorship on any blog post or paper that uses NVIDIA technology
- Reference architecture published on both oracle.com and developer.nvidia.com

---

## 6. Contact and Next Steps

**Proposed next step:** 45-minute technical call with the NVIDIA Isaac and GR00T teams to align on Item 3 (training weight access research agreement) and to exchange NGC access tokens for Cosmos (Item 1). Items 1 and 2 can be unblocked in a single call.

**Jun Qian**
Principal Product Manager, Oracle Cloud Infrastructure
Robotics AI — OCI Robot Cloud
GitHub: `qianjun22/roboticsai`

---

*All performance numbers are measured on OCI BM.GPU.A100 instances (8× NVIDIA A100 80GB SXM4). Full benchmark methodology and raw logs available on request.*
