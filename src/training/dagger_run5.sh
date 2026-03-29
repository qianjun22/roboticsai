#!/bin/bash
# dagger_run5.sh
# Run DAgger starting from the 1000-demo fine-tuned checkpoint.
# Unlike run4 (which used stale 500-demo policy data), this collects
# on-policy trajectories with the stronger 1000-demo baseline.
#
# Usage:
#   bash src/training/dagger_run5.sh [BASE_CKPT] [OUTPUT_DIR] [GPU_ID]
#
# Defaults:
#   BASE_CKPT   = /tmp/finetune_1000_5k/checkpoint-5000
#   OUTPUT_DIR  = /tmp/dagger_run5
#   GPU_ID      = 4

BASE_CKPT=${1:-"/tmp/finetune_1000_5k/checkpoint-5000"}
OUTPUT_DIR=${2:-"/tmp/dagger_run5"}
GPU_ID=${3:-4}

GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
GROOT_REPO="/home/ubuntu/Isaac-GR00T"
ROBOTICS_DIR="$HOME/roboticsai"
SERVER_SCRIPT="$ROBOTICS_DIR/src/inference/groot_franka_server.py"
DAGGER_SCRIPT="$ROBOTICS_DIR/src/training/dagger_train.py"
EVAL_SCRIPT="$ROBOTICS_DIR/src/eval/closed_loop_eval.py"
LOG="$OUTPUT_DIR/run5.log"

export CUDA_VISIBLE_DEVICES=$GPU_ID

mkdir -p "$OUTPUT_DIR"

echo "[run5] Starting DAgger run5 from 1000-demo checkpoint" | tee -a $LOG
echo "[run5] Base: $BASE_CKPT" | tee -a $LOG
echo "[run5] Output: $OUTPUT_DIR" | tee -a $LOG
echo "[run5] GPU: $GPU_ID" | tee -a $LOG
echo "" | tee -a $LOG

# --- Step 1: Verify checkpoint exists ---
if [ ! -d "$BASE_CKPT" ]; then
    echo "[run5] ERROR: Checkpoint not found: $BASE_CKPT" | tee -a $LOG
    exit 1
fi

# --- Step 2: Start GR00T server with 1000-demo checkpoint ---
echo "[run5] Starting GR00T server with 1000-demo checkpoint on port 8002..." | tee -a $LOG
pkill -f "groot_franka_server.py" 2>/dev/null
sleep 5
nohup $GROOT_PYTHON $SERVER_SCRIPT \
    --checkpoint "$BASE_CKPT" \
    --port 8002 \
    >> $OUTPUT_DIR/server.log 2>&1 &
SERVER_PID=$!
echo "[run5] Server PID: $SERVER_PID" | tee -a $LOG

# Wait for server ready
echo "[run5] Waiting for server..." | tee -a $LOG
for i in $(seq 1 40); do
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        echo "[run5] Server ready after ${i}×5s" | tee -a $LOG
        break
    fi
    sleep 5
done

# --- Step 3: Baseline eval of 1000-demo checkpoint ---
echo "[run5] Running baseline eval (1000-demo, no DAgger)..." | tee -a $LOG
python3 $EVAL_SCRIPT \
    --num-episodes 20 \
    --server-url http://localhost:8002 \
    --output $OUTPUT_DIR/eval_baseline 2>&1 | tee -a $LOG
echo "[run5] === BASELINE EVAL COMPLETE ===" | tee -a $LOG

# --- Step 4: Run DAgger from 1000-demo base ---
# Key differences from run4:
#   - beta-start=0.3 (start with less expert mixing since policy is stronger)
#   - beta-decay=0.7 (same)
#   - finetune-steps=2000 (same)
#   - base-model = 1000-demo checkpoint (not 500-demo)
#
echo "[run5] Starting DAgger data collection (5 iters × 20 eps)..." | tee -a $LOG
cd $GROOT_REPO

$GROOT_PYTHON $DAGGER_SCRIPT \
    --server-url http://localhost:8002 \
    --output-dir $OUTPUT_DIR \
    --dagger-iters 5 \
    --episodes-per-iter 20 \
    --finetune-steps 2000 \
    --max-steps 100 \
    --beta-start 0.30 \
    --beta-decay 0.70 \
    --gpu-id $GPU_ID \
    --base-model "$BASE_CKPT" \
    2>&1 | tee -a $LOG

echo "[run5] DAgger complete" | tee -a $LOG

# --- Step 5: Eval final DAgger checkpoint ---
DAGGER_CKPT=$(ls -d ${OUTPUT_DIR}/checkpoints/iter_*/checkpoint-* 2>/dev/null | sort -V | tail -1)
if [ -z "$DAGGER_CKPT" ]; then
    echo "[run5] No DAgger checkpoint found, using last iter checkpoint..." | tee -a $LOG
    DAGGER_CKPT=$(ls -d ${OUTPUT_DIR}/checkpoints/iter_* 2>/dev/null | sort -V | tail -1)
fi

if [ -n "$DAGGER_CKPT" ]; then
    echo "[run5] Restarting server with DAgger checkpoint: $DAGGER_CKPT" | tee -a $LOG
    pkill -f "groot_franka_server.py" 2>/dev/null
    sleep 5
    nohup $GROOT_PYTHON $SERVER_SCRIPT \
        --model-path "$DAGGER_CKPT" \
        --port 8002 \
        >> $OUTPUT_DIR/server_dagger.log 2>&1 &
    sleep 30

    echo "[run5] Running final eval (DAgger run5 checkpoint)..." | tee -a $LOG
    python3 $EVAL_SCRIPT \
        --num-episodes 20 \
        --server-url http://localhost:8002 \
        --output $OUTPUT_DIR/eval_final 2>&1 | tee -a $LOG
    echo "[run5] === FINAL EVAL COMPLETE ===" | tee -a $LOG
fi

# --- Step 6: Aggregate results ---
echo "[run5] Generating progress report..." | tee -a $LOG
python3 $ROBOTICS_DIR/src/eval/results_aggregator.py \
    --results \
        /tmp/eval_500demo \
        /tmp/eval_1000demo \
        $OUTPUT_DIR/eval_baseline \
        $OUTPUT_DIR/eval_final \
    --labels \
        "500-demo BC" \
        "1000-demo BC (post_train)" \
        "1000-demo BC (run5 baseline)" \
        "DAgger run5 final" \
    --dagger-log $OUTPUT_DIR/dagger_results.json \
    --output $OUTPUT_DIR/progress_report.html 2>&1 | tee -a $LOG

echo "" | tee -a $LOG
echo "[run5] === PIPELINE COMPLETE ===" | tee -a $LOG
echo "[run5] Progress report: $OUTPUT_DIR/progress_report.html" | tee -a $LOG
