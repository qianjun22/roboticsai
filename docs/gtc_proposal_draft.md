# GTC 2027 Talk Proposal Draft

**Title:** From Synthetic Data to Real Robot Actions: How OCI + NVIDIA GR00T Cut Training Cost 9.6× Without Sacrificing Quality

**Session Type:** 30-minute talk + Q&A
**Track:** AI for Robotics / NVIDIA GR00T
**Target Conference:** GTC 2027 — San Jose, CA (March 2027)

---

## Abstract

Training robot foundation models requires A100-class GPUs, thousands of labeled demonstrations, and rapid iteration cycles — infrastructure most robotics startups can't afford. This talk presents OCI Robot Cloud, a validated pipeline that uses NVIDIA's full stack (Genesis/Isaac Sim for synthetic data generation, GR00T N1.6-3B for fine-tuning) on Oracle Cloud Infrastructure to cut training costs 9.6× vs AWS p4d while delivering an 8.7× improvement in closed-loop manipulation performance.

We share hard-won lessons from end-to-end experimentation: the CPU vs CUDA backend bug that caused 0% closed-loop success despite excellent open-loop MAE, the DAgger iteration loop that drove expert interventions from 22.8 to 10.9 per episode, and the infrastructure choices that make OCI A100s the right cloud for NVIDIA robotics workloads.

The talk includes a live 15-minute demo: SDG → fine-tune → query → evaluate, from scratch, for ~$0.85 total compute cost.

---

## Session Outline (30 min)

| Time | Section |
|------|---------|
| 0:00–3:00 | The Compute Barrier: Why 93% of robotics startups never reach 10k demos |
| 3:00–7:00 | Architecture: Full NVIDIA stack on OCI (Genesis/Isaac Sim + GR00T + Jetson) |
| 7:00–12:00 | Live Demo Step 1: SDG — 100 demos in 90 seconds |
| 12:00–18:00 | Live Demo Step 2: GR00T fine-tuning — 2.35 it/s, 87% GPU util, $0.0043/10k steps |
| 18:00–22:00 | Closed-loop debugging: the CPU/CUDA mismatch that cost 100% success rate |
| 22:00–26:00 | DAgger: on-policy correction loop (expert interventions: 22.8 → 10.9 per episode) |
| 26:00–28:00 | Results: 8.7× MAE, 9.6× cheaper than AWS, 3.07× DDP scaling |
| 28:00–30:00 | Design partner program + Q&A |

---

## Key Results to Present

- **MAE improvement**: 8.7× (0.013 vs 0.103 random baseline) on pick-and-lift task
- **Training loss**: 0.099 final (from 0.68) on 1000-demo 50k-frame dataset in 35.4 minutes
- **Cost**: $0.0043 per 10k training steps on OCI A100 (vs $0.041 on AWS p4d, 9.6× cheaper)
- **Throughput**: 2.36 it/s single A100, 3.07× with 4-GPU DDP (230 samples/sec)
- **Closed-loop DAgger**: 5% baseline → ~65% collection success; expert interventions 22.8 → 10.9/ep over 3 iters
- **Pipeline time**: ~15 minutes end-to-end (100 demos → 5000 steps → 20-ep eval), ~$0.85 total

---

## Speaker Bio

**Jun Qian** — AI Infrastructure, Oracle Cloud Infrastructure. Leads the robotics compute initiative at OCI, focused on making NVIDIA robotics foundation models accessible to startups via cloud-native infrastructure. Co-author of OCI Robot Cloud, an open-source pipeline for Genesis/Isaac Sim → GR00T fine-tuning → edge deployment.

---

## Proposed Co-Presenter

Seeking NVIDIA Isaac/GR00T team co-presenter to:
- Present GR00T N1.6 architecture and fine-tuning best practices
- Discuss Cosmos world model integration roadmap
- Validate joint OCI × NVIDIA narrative

**Contact:** jun.q.qian@oracle.com

---

## Supporting Materials

- Open-source code: `github.com/qianjun22/roboticsai`
- Live demo environment: OCI GPU4 (A100-SXM4-80GB) pre-configured
- Presentation deck: `OCI_Robot_Cloud_GTC2027.pptx`
- Technical paper: `docs/technical_paper_draft.md` (CoRL preprint)

---

*Status: Draft — pending NVIDIA co-presenter confirmation and session submission (GTC 2027 CFP ~Q3 2026)*
