# OCI Robot Cloud — Production Status

Last updated: 2026-03-30

## Active Production Model

| Item | Value |
|------|-------|
| Model | GR00T N1.6 fine-tuned |
| Checkpoint | finetune_1000_5k/checkpoint-5000 |
| SR (closed-loop) | **85%** (17/20 episodes) |
| Latency | 235ms |
| Server | groot_franka_server.py |
| Port | 8001 |
| GPU | OCI A100 GPU3 (138.1.153.110) |
| Promoted | 2026-03-30 |

## History

| Date | Model | SR | Notes |
|------|-------|-----|-------|
| 2026-03-30 | finetune_1000_5k/ckpt-5000 | 85% | Current production |
| 2026-03-15 | dagger_run9_v2.2 | 71% | Superseded |

## Eval Script

`scripts/eval_groot_cl.py` — Fixed cam.render tuple bug (commit 23625e7)
