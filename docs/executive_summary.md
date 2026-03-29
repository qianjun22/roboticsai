# **OCI Robot Cloud: Making Physical AI Accessible on Oracle Cloud**

*Jun Qian — OCI AI Infrastructure | March 2026*

---

## Value Proposition

Robotics companies need large GPU bursts to fine-tune foundation models, but most Series B startups can't justify on-prem DGX clusters for periodic workloads. OCI Robot Cloud provides a managed, end-to-end robotics AI pipeline — from synthetic data generation through policy fine-tuning to edge deployment — at 9.6× lower cost than AWS, with NVIDIA's full model stack (GR00T, Isaac Sim, Cosmos) running natively on OCI.

**The one-line pitch:** A robotics startup can go from 100 raw demonstrations to a fine-tuned, deployable robot policy for **$0.85** — in under an hour.

---

## Key Results

### Infrastructure Performance

| Metric | Result |
|---|---|
| GR00T N1.6-3B inference latency (A100) | 227ms avg |
| Synthetic data generation (Genesis, IK) | 38.5 fps, 100% IK success |
| Fine-tuning throughput (1× A100) | 2.357 it/s, 87% GPU util, 36.8GB VRAM |
| Multi-GPU DDP throughput (4× A100) | 3.07× vs single GPU |
| Edge inference (Jetson AGX Orin) | ~400–600ms |

### Cost

| Comparison | OCI | AWS p4d |
|---|---|---|
| Cost per 10k fine-tuning steps | $0.0043 | ~$0.041 |
| Full pipeline (100 demos → 5k steps → 20-ep eval) | **$0.85** | ~$8.20 |
| Relative advantage | **9.6× cheaper** | baseline |

### Policy Quality

| Training Condition | Fine-tune Loss | Closed-Loop Success |
|---|---|---|
| Baseline (random / no training) | 0.103 | — |
| 500 demos, 5k steps | 0.013 (8.7× ↑) | ~30% |
| 1000 demos, 5k steps | **0.099 (↓39%)** | 5% BC → **65% with DAgger** |

Dataset: 50,000 frames across 1,000 demonstrations, stored in LeRobot v2 format.

---

## Technical Approach (Summary)

The pipeline has four stages, each exposed as a managed OCI service:

1. **Synthetic Data Generation** — Isaac Sim on OCI GPU shapes, or Genesis for lightweight IK-planned motion. Outputs LeRobot v2 datasets directly to Object Storage.
2. **Policy Fine-Tuning** — GR00T N1.6-3B fine-tuning via OCI compute clusters. Single-GPU for cost-sensitive runs; DDP-scaled for time-sensitive jobs. Auto-retrain trigger on new data arrival.
3. **Closed-Loop Evaluation + DAgger** — Simulator-in-the-loop evaluation with automatic DAgger intervention collection. Drives BC baseline (5%) to production-grade success (65%).
4. **Edge Deployment** — Checkpoint export + FastAPI inference server deployable to Jetson AGX Orin. Python SDK + CLI (`oci-robot-cloud`) for integration.

NVIDIA stack runs unmodified: GR00T weights from NGC, Isaac Sim via NVIDIA container registry, Cosmos for world-model-based data augmentation.

---

## Go-to-Market

### Target Customer

**Series B robotics startups (ARR $2M–$20M) in the NVIDIA ecosystem** — companies already using Isaac Sim or GR00T who lack on-prem GPU infrastructure. Key characteristics:

- 5–30 person engineering team; no dedicated ML infra team
- Fine-tuning cadence: monthly or per-deployment (burst, not steady-state)
- Currently on AWS or running workloads on rented DGX time at $4–8/hr
- Robot form factors: manipulation arms, AMRs, humanoids in early pilot

### Why They Choose OCI

- **Cost** — 9.6× cheaper than AWS p4d for identical A100 workloads
- **NVIDIA-native** — same models (GR00T, Cosmos), same tooling (Isaac Sim), no porting
- **Managed pipeline** — no MLOps engineer needed; SDK handles data → train → eval → deploy
- **Enterprise support** — Oracle SLA, SOC 2, VCN isolation for proprietary demo data

### Timeline

| Milestone | Target |
|---|---|
| Design partner onboarding (3 startups) | Q2 2026 |
| OCI AI World live demo | September 2026 |
| NVIDIA co-marketing (GTC session submission) | October 2026 |
| GA launch | Q1 2027 |
| NVIDIA GTC talk | March 2027 |

---

## The Ask

### Oracle Investment
- **Engineering:** 2 FTE dedicated to managed service wrapper (API gateway, billing integration, customer isolation) — existing pipeline code is production-ready
- **GTM:** 1 cloud architect for design-partner co-engagements; connect to OCI startup credits program for partner pipeline
- **Greg/Clay sponsorship:** Exec-level commitment needed for NVIDIA partnership conversation at VP/SVP level

### NVIDIA Co-Engineering Partnership
We are proposing a joint engineering engagement structured as follows:

| Work Stream | Oracle Owns | NVIDIA Owns |
|---|---|---|
| GPU infra + serving optimization | OCI A100/H100 fleet, autoscaling, cost model | GR00T model updates, Isaac Sim container support |
| Pipeline integration | LeRobot ingest, training orchestrator, DAgger loop | Cosmos data augmentation API, NGC model registry |
| Customer co-sell | OCI startup credits, enterprise sales overlay | NVIDIA Inception program referrals, robotics ecosystem |
| Co-marketing | OCI AI World demo, Oracle blog | GTC session, NVIDIA developer blog, Isaac Sim showcase |

The ask to NVIDIA: formal co-engineering agreement, shared design-partner pipeline with 3 Inception-program robotics startups in Q2 2026, and joint GTC session submission for March 2027.

---

*Contact: Jun Qian, OCI AI Infrastructure | This document contains Oracle Confidential information.*
