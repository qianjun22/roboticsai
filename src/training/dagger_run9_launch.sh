#!/bin/bash
# DAgger run9 launch script — corrected beta decay
# Key fixes from run8 postmortem:
#   1. beta_decay=0.80 (multiply per iter) → meaningful DAgger signal throughout
#   2. /act warmup query ensures model loaded before collection starts (commit 3c61f52fe4)
cd /home/ubuntu/roboticsai
GROOT_REPO=/home/ubuntu/Isaac-GR00T
GROOT_VENV=/.venv/bin/python3
BASE_MODEL=/tmp/dagger_run8/checkpoints/iter_06/checkpoint-5000  # or best iter
OUTPUT=/tmp/dagger_run9

nohup  src/training/dagger_train.py     --server-url http://localhost:8001     --base-model      --output-dir      --dagger-iters 6     --episodes-per-iter 75     --finetune-steps 7000     --beta-start 0.40     --beta-decay 0.80     --gpu-id 3     > /tmp/dagger_run9.log 2>&1 &
echo "DAgger run9 PID: 0"
echo "Log: /tmp/dagger_run9.log"
