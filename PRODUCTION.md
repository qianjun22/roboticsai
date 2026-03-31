# OCI Robot Cloud — Production Status

Last updated: 2026-03-31

## Active Production Model

| Item | Value |
|------|-------|
| Model | GR00T N1.6 fine-tuned |
| Checkpoint | finetune_1000_5k/checkpoint-5000 |
| SR (closed-loop) | **100%** (20/20 episodes) |
| Latency | 233ms avg |
| Server | groot_franka_server.py |
| Port | 8001 |
| GPU | OCI A100 GPU3 (138.1.153.110) |
| Promoted | 2026-03-30 |

## Eval Setup (Corrected 2026-03-31)

Training data confirmed via `/tmp/sdg_500/demo_0000/meta.json`:
- TABLE_Z=0.7m, cube at (x,y,0.725), 5cm cube
- Q_HOME=[0,-0.4,0,-2.1,0,1.8,0.785,0.04,0.04]
- instruction: "pick the red cube from the table"
- camera: lookat=(0.45,0,0.7), fov=55, LIFT_THRESH=0.78

Prior eval (commit 23625e7) used cube on floor (z=0.02) — wrong setup, gave misleading 85%.

## DAgger Run5 Comparison

| Checkpoint | SR | Latency |
|------------|-----|---------|
| finetune_1000_5k/ckpt-5000 (PROD) | **100%** (20/20) | 233ms |
| dagger_run5/finetune_final/ckpt-5000 | **100%** (20/20) | 236ms |

Both checkpoints perform equally. Production stays on finetune_1000_5k (more stable training).

## History

| Date | Model | SR | Notes |
|------|-------|-----|-------|
| 2026-03-31 | finetune_1000_5k/ckpt-5000 | **100%** | Corrected eval — current production |
| 2026-03-30 | finetune_1000_5k/ckpt-5000 | 85%* | Incorrect eval setup (cube on floor) |
| 2026-03-15 | dagger_run9_v2.2 | 71% | Superseded |

## Eval Script

`scripts/eval_groot_cl.py` — Corrected eval setup matching training (commit e7451bb)
