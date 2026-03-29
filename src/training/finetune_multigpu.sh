#!/usr/bin/env bash
# OCI Robot Cloud — Multi-GPU GR00T Fine-tuning
#
# Demonstrates OCI burst advantage: scale from 1→4 A100s on demand.
# Uses torchrun + DDP for data-parallel training across GPUs 4,5,6,7.
#
# Key OCI pitch: same job runs 4× faster with 4 GPUs, no CapEx changes.
#
# Usage:
#   bash src/training/finetune_multigpu.sh [--gpus N] [--steps M]
#
# Defaults: 4 GPUs (4,5,6,7), 2000 steps, batch=128 (32/GPU)

set -euo pipefail

N_GPUS=${N_GPUS:-4}
TRAIN_STEPS=${TRAIN_STEPS:-2000}
GLOBAL_BATCH=${GLOBAL_BATCH:-128}   # 32 per GPU × 4 GPUs
GPU_LIST="4,5,6,7"                  # free GPUs on moirai-a100

DATASET_DIR=/tmp/franka_planned_lerobot
FINETUNE_DIR=/tmp/franka_multigpu_finetune
MODEL_PATH=/home/ubuntu/models/GR00T-N1.6-3B
MODALITY_CFG=/home/ubuntu/roboticsai/src/training/franka_config.py

echo "================================================================"
echo " OCI Robot Cloud — Multi-GPU GR00T Fine-tuning"
echo " GPUs: ${N_GPUS}× A100 (${GPU_LIST}) | Steps: ${TRAIN_STEPS}"
echo " Global batch: ${GLOBAL_BATCH} (${GLOBAL_BATCH}/${N_GPUS} per GPU)"
echo "================================================================"

cd ~/Isaac-GR00T
source .venv/bin/activate

rm -rf "$FINETUNE_DIR"

T_START=$(date +%s)

# torchrun launches one process per GPU; DDP handles gradient sync
CUDA_VISIBLE_DEVICES=$GPU_LIST torchrun \
    --nproc_per_node=$N_GPUS \
    --master_port=29501 \
    gr00t/experiment/launch_finetune.py \
        --base-model-path "$MODEL_PATH" \
        --dataset-path "$DATASET_DIR" \
        --embodiment-tag NEW_EMBODIMENT \
        --modality-config-path "$MODALITY_CFG" \
        --num-gpus "$N_GPUS" \
        --output-dir "$FINETUNE_DIR" \
        --save-total-limit 2 \
        --save-steps "$TRAIN_STEPS" \
        --max-steps "$TRAIN_STEPS" \
        --global-batch-size "$GLOBAL_BATCH" \
        --dataloader-num-workers 4

T_END=$(date +%s)
ELAPSED=$((T_END - T_START))
STEPS_PER_SEC=$(echo "scale=2; $TRAIN_STEPS / $ELAPSED" | bc)

echo ""
echo "================================================================"
echo " Multi-GPU Training Complete"
echo " Wall time: ${ELAPSED}s for ${TRAIN_STEPS} steps"
echo " Throughput: ${STEPS_PER_SEC} steps/sec across ${N_GPUS} GPUs"
echo " Checkpoint: ${FINETUNE_DIR}/checkpoint-${TRAIN_STEPS}"
echo "================================================================"
echo ""
echo "Compare to 1-GPU baseline: 2.345 steps/sec"
echo "OCI speedup: $(echo "scale=1; $STEPS_PER_SEC / 2.345" | bc)×"
