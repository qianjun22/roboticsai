#!/bin/bash
# post_train_pipeline.sh
# Waits for 1000-demo fine-tune to finish, then:
#   1. Restarts GR00T server with new checkpoint
#   2. Runs closed-loop eval (20 episodes)
#   3. Runs DAgger fine-tune on top
#   4. Runs final closed-loop eval
#
# Usage: bash post_train_pipeline.sh [base_ckpt] [dagger_data] [output_dir]
#   Default: /tmp/finetune_1000_5k/checkpoint-5000

BASE_CKPT=${1:-"/tmp/finetune_1000_5k/checkpoint-5000"}
DAGGER_DATA=${2:-"/tmp/dagger_run4/lerobot"}
OUTPUT_DIR=${3:-"/tmp/dagger_run4_finetune"}
EVAL_SCRIPT="$HOME/roboticsai/src/eval/closed_loop_eval.py"
SERVER_SCRIPT="$HOME/roboticsai/src/inference/groot_franka_server.py"
GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
LOG="$HOME/post_train_pipeline.log"

export CUDA_VISIBLE_DEVICES=4

echo "[pipeline] Starting post-train pipeline" | tee -a $LOG
echo "[pipeline] Waiting for: $BASE_CKPT" | tee -a $LOG

# --- Step 1: Wait for checkpoint-5000 ---
while [ ! -d "$BASE_CKPT" ]; do
    echo "[pipeline] $(date +%H:%M) waiting for checkpoint..." | tee -a $LOG
    sleep 60
done

echo "[pipeline] $(date +%H:%M) Checkpoint found: $BASE_CKPT" | tee -a $LOG

# --- Step 2: Restart GR00T server ---
echo "[pipeline] Restarting GR00T server on port 8002..." | tee -a $LOG
pkill -f "groot_franka_server.py" 2>/dev/null
sleep 5
nohup $GROOT_PYTHON $SERVER_SCRIPT \
    --model-path "$BASE_CKPT" \
    --port 8002 \
    >> /tmp/groot_1000demo.log 2>&1 &
SERVER_PID=$!
echo "[pipeline] GR00T server PID: $SERVER_PID" | tee -a $LOG

# Wait for server to be ready
echo "[pipeline] Waiting for GR00T server to be ready..." | tee -a $LOG
for i in $(seq 1 30); do
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        echo "[pipeline] Server ready after ${i}s" | tee -a $LOG
        break
    fi
    sleep 5
done

# --- Step 3: Closed-loop eval on 1000-demo model ---
echo "[pipeline] Running closed-loop eval (1000-demo checkpoint)..." | tee -a $LOG
python3 $EVAL_SCRIPT \
    --num-episodes 20 \
    --output /tmp/eval_1000demo \
    --server-url http://localhost:8002 2>&1 | tee -a $LOG

echo "[pipeline] === 1000-DEMO EVAL COMPLETE ===" | tee -a $LOG

# --- Step 4: DAgger fine-tune on top of 1000-demo checkpoint ---
echo "[pipeline] Starting DAgger fine-tune on top of 1000-demo model..." | tee -a $LOG
mkdir -p $OUTPUT_DIR

cd /home/ubuntu/Isaac-GR00T
$GROOT_PYTHON gr00t/experiment/launch_finetune.py \
    --base-model-path "$BASE_CKPT" \
    --dataset-path "$DAGGER_DATA" \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path /home/ubuntu/roboticsai/src/training/franka_config.py \
    --num-gpus 1 \
    --output-dir "$OUTPUT_DIR" \
    --max-steps 2000 \
    --save-steps 500 \
    --global-batch-size 16 2>&1 | tee -a $LOG

echo "[pipeline] DAgger fine-tune complete" | tee -a $LOG

# --- Step 5: Restart server with DAgger checkpoint ---
DAGGER_CKPT=$(ls -d ${OUTPUT_DIR}/checkpoint-* 2>/dev/null | sort -V | tail -1)
if [ -z "$DAGGER_CKPT" ]; then
    echo "[pipeline] ERROR: No DAgger checkpoint found in $OUTPUT_DIR" | tee -a $LOG
    exit 1
fi

echo "[pipeline] Restarting server with DAgger checkpoint: $DAGGER_CKPT" | tee -a $LOG
pkill -f "groot_franka_server.py" 2>/dev/null
sleep 5
nohup $GROOT_PYTHON $SERVER_SCRIPT \
    --model-path "$DAGGER_CKPT" \
    --port 8002 \
    >> /tmp/groot_dagger.log 2>&1 &

sleep 30  # let server load

# --- Step 6: Final eval ---
echo "[pipeline] Running final closed-loop eval (DAgger+1000demo checkpoint)..." | tee -a $LOG
python3 $EVAL_SCRIPT \
    --num-episodes 20 \
    --output /tmp/eval_dagger_final \
    --server-url http://localhost:8002 2>&1 | tee -a $LOG

echo "[pipeline] === PIPELINE COMPLETE ===" | tee -a $LOG
echo "[pipeline] Results:" | tee -a $LOG
echo "  - 1000-demo eval: /tmp/eval_1000demo/" | tee -a $LOG
echo "  - DAgger final eval: /tmp/eval_dagger_final/" | tee -a $LOG
