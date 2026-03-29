#!/bin/bash
# dagger_run6.sh
# DAgger run 6 — continues from DAgger run5 best checkpoint.
#
# Designed for the "long-tail" phase: we've already pushed from 5% (BC) to
# ~65% (run5 target). Run6 tries to push pure closed-loop success beyond
# 30% by:
#   - Lower beta-start (0.10) — policy does most of the work
#   - More episodes per iteration (30 vs 20) for better coverage
#   - Tighter expert threshold (expert intervenes only when cube_z < 0.65
#     i.e., near table — see dagger_train.py EXPERT_THRESHOLD)
#   - 3000 fine-tune steps per iteration (was 2000)
#
# Usage: bash dagger_run6.sh [run5_ckpt_dir] [output_dir]
#   Default: auto-detects latest checkpoint from run5

RUN5_BASE=${1:-"/tmp/dagger_run5_finetune"}
OUTPUT_BASE=${2:-"/tmp/dagger_run6"}
DAGGER_TRAIN="$HOME/roboticsai/src/training/dagger_train.py"
RESULTS_AGG="$HOME/roboticsai/src/eval/results_aggregator.py"
CONVERGENCE_ANALYSIS="$HOME/roboticsai/src/eval/dagger_convergence_analysis.py"
GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
LOG="$HOME/dagger_run6.log"

export CUDA_VISIBLE_DEVICES=4

# Config
ITERS=4
EPS_PER_ITER=30
FINETUNE_STEPS=3000
BETA_START=0.10
BETA_DECAY=0.03

echo "[run6] Starting DAgger run 6 (long-tail policy improvement)" | tee -a $LOG
echo "[run6] Run5 base: $RUN5_BASE" | tee -a $LOG
echo "[run6] Config: ${ITERS} iters × ${EPS_PER_ITER} eps, beta_start=${BETA_START}" | tee -a $LOG

# --- Auto-detect run5 best checkpoint ---
if [ -z "$1" ]; then
    RUN5_CKPT=$(ls -d ${RUN5_BASE}/checkpoint-* 2>/dev/null | sort -V | tail -1)
    if [ -z "$RUN5_CKPT" ]; then
        # Fall back to 1000-demo base
        RUN5_CKPT="/tmp/finetune_1000_5k/checkpoint-5000"
        echo "[run6] WARNING: no run5 checkpoint found, falling back to 1000-demo base" | tee -a $LOG
    fi
else
    RUN5_CKPT=$(ls -d ${RUN5_BASE}/checkpoint-* 2>/dev/null | sort -V | tail -1)
fi

echo "[run6] Starting from: $RUN5_CKPT" | tee -a $LOG
mkdir -p $OUTPUT_BASE

# Accumulate all data dirs across iterations for multi-iteration training
DATA_DIRS=""
CURRENT_CKPT="$RUN5_CKPT"
BETA=$BETA_START

for ITER in $(seq 1 $ITERS); do
    ITER_DIR="${OUTPUT_BASE}/iter${ITER}"
    LEROBOT_DIR="${ITER_DIR}/lerobot"
    FINETUNE_DIR="${ITER_DIR}/finetune"
    mkdir -p $ITER_DIR

    echo "" | tee -a $LOG
    echo "[run6] ===== Iteration ${ITER}/${ITERS} | beta=${BETA} =====" | tee -a $LOG

    # --- Collect on-policy episodes ---
    echo "[run6] Collecting ${EPS_PER_ITER} episodes (beta=${BETA})..." | tee -a $LOG
    python3 $DAGGER_TRAIN \
        --checkpoint "$CURRENT_CKPT" \
        --num-episodes $EPS_PER_ITER \
        --beta $BETA \
        --output-dir "$LEROBOT_DIR" \
        --server-url http://localhost:8002 2>&1 | tee -a $LOG

    if [ $? -ne 0 ]; then
        echo "[run6] ERROR: collection failed at iter ${ITER}" | tee -a $LOG
        exit 1
    fi

    # Accumulate data dirs (train on all data collected so far)
    if [ -z "$DATA_DIRS" ]; then
        DATA_DIRS="$LEROBOT_DIR"
    else
        DATA_DIRS="${DATA_DIRS}:${LEROBOT_DIR}"
    fi

    echo "[run6] Accumulated dataset dirs: $DATA_DIRS" | tee -a $LOG

    # --- Fine-tune on accumulated data ---
    echo "[run6] Fine-tuning ${FINETUNE_STEPS} steps on accumulated dataset..." | tee -a $LOG
    mkdir -p $FINETUNE_DIR

    cd /home/ubuntu/Isaac-GR00T
    $GROOT_PYTHON gr00t/experiment/launch_finetune.py \
        --base-model-path "$CURRENT_CKPT" \
        --dataset-path "$LEROBOT_DIR" \
        --embodiment-tag NEW_EMBODIMENT \
        --modality-config-path /home/ubuntu/roboticsai/src/training/franka_config.py \
        --num-gpus 1 \
        --output-dir "$FINETUNE_DIR" \
        --max-steps $FINETUNE_STEPS \
        --save-steps 1000 \
        --global-batch-size 16 2>&1 | tee -a $LOG

    if [ $? -ne 0 ]; then
        echo "[run6] ERROR: fine-tune failed at iter ${ITER}" | tee -a $LOG
        exit 1
    fi

    # Get latest checkpoint
    CURRENT_CKPT=$(ls -d ${FINETUNE_DIR}/checkpoint-* 2>/dev/null | sort -V | tail -1)
    if [ -z "$CURRENT_CKPT" ]; then
        echo "[run6] ERROR: no checkpoint found in $FINETUNE_DIR" | tee -a $LOG
        exit 1
    fi

    echo "[run6] Iter ${ITER} complete. New checkpoint: $CURRENT_CKPT" | tee -a $LOG

    # Decay beta
    BETA=$(python3 -c "print(f'{max(0.0, ${BETA} - ${BETA_DECAY}):.2f}')")
done

echo "" | tee -a $LOG
echo "[run6] All ${ITERS} iterations complete." | tee -a $LOG
echo "[run6] Final checkpoint: $CURRENT_CKPT" | tee -a $LOG

# --- Generate convergence report ---
echo "[run6] Generating convergence analysis..." | tee -a $LOG
python3 $CONVERGENCE_ANALYSIS \
    --runs \
        /tmp/eval_1000demo \
        ${OUTPUT_BASE}/iter1/eval \
        ${OUTPUT_BASE}/iter2/eval \
        ${OUTPUT_BASE}/iter3/eval \
        ${OUTPUT_BASE}/iter4/eval \
    --labels "1000-demo BC" "Run6 Iter1" "Run6 Iter2" "Run6 Iter3" "Run6 Iter4" \
    --output ${OUTPUT_BASE}/convergence_report.html 2>&1 | tee -a $LOG || true

echo "" | tee -a $LOG
echo "[run6] === RUN 6 COMPLETE ===" | tee -a $LOG
echo "[run6] Final checkpoint: $CURRENT_CKPT" | tee -a $LOG
echo "[run6] Convergence report: ${OUTPUT_BASE}/convergence_report.html" | tee -a $LOG
echo "[run6] Log: $LOG" | tee -a $LOG
