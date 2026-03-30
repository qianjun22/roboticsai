#!/bin/bash
# dagger_run7.sh — Curriculum-Enhanced DAgger Run 7
#
# Builds on dagger_run6 iter4 checkpoint (or run4 iter3 as fallback).
# Run6 stalled near the 65% ceiling due to uniform difficulty episodes.
# Run7 adds 4-level curriculum progression so the policy is first
# reinforced on easy tasks before being challenged by harder ones,
# targeting >80% closed-loop success.
#
# Strategy:
#   - 8 iters × 40 episodes × 4000 fine-tune steps
#   - Iters 1-2: Level 1 (easy)   — cube placed close, large tolerances
#   - Iters 3-4: Level 2 (medium) — standard placement
#   - Iters 5-6: Level 3 (hard)   — varied placement, smaller tolerances
#   - Iters 7-8: Level 4 (expert) — adversarial placement, tight tolerances
#   - Beta starts at 0.05, decays 0.02/iter (policy-dominant from the start)
#   - Phase 2: 5000-step final fine-tune on all accumulated data
#   - Phase 3: 20-episode closed-loop eval
#
# Launch on OCI:
#   tmux new -s dagger_run7
#   bash /home/ubuntu/roboticsai/src/training/dagger_run7.sh

set -e

# ── Paths ────────────────────────────────────────────────────────────────────
GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
GROOT_REPO="/home/ubuntu/Isaac-GR00T"
ROBOTICS_DIR="$HOME/roboticsai"
DAGGER_SCRIPT="$ROBOTICS_DIR/src/training/dagger_train.py"
EVAL_SCRIPT="$ROBOTICS_DIR/src/eval/closed_loop_eval.py"
RESULTS_AGG="$ROBOTICS_DIR/src/eval/results_aggregator.py"
SERVER_SCRIPT="$ROBOTICS_DIR/src/inference/groot_franka_server.py"

OUTPUT_BASE="/tmp/dagger_run7"
LOG="/tmp/dagger_run7.log"

# ── Base checkpoint: run6 iter4, fallback to run4 iter3 ──────────────────────
RUN6_CKPT="/tmp/dagger_run6/iter4/checkpoint-3000"
RUN4_FALLBACK="/tmp/dagger_run4/iter3/checkpoint-2000"

if [ -d "$RUN6_CKPT" ]; then
    BASE_CKPT="$RUN6_CKPT"
else
    echo "[run7] WARNING: run6 checkpoint not found; falling back to run4 iter3" | tee -a "$LOG"
    BASE_CKPT="$RUN4_FALLBACK"
fi

# ── GPU + config ─────────────────────────────────────────────────────────────
export CUDA_VISIBLE_DEVICES=4

ITERS=8
EPS_PER_ITER=40
FINETUNE_STEPS=4000
BETA_START=0.05
BETA_DECAY=0.02

mkdir -p "$OUTPUT_BASE"

ts() { date "+%Y-%m-%d %H:%M:%S"; }

echo "" | tee -a "$LOG"
echo "[run7] $(ts) ── DAgger Run 7 (Curriculum) START ──" | tee -a "$LOG"
echo "[run7] Base checkpoint : $BASE_CKPT" | tee -a "$LOG"
echo "[run7] Config          : ${ITERS} iters × ${EPS_PER_ITER} eps × ${FINETUNE_STEPS} steps" | tee -a "$LOG"
echo "[run7] Beta schedule   : start=${BETA_START}, decay=${BETA_DECAY}/iter" | tee -a "$LOG"
echo "[run7] Output          : $OUTPUT_BASE" | tee -a "$LOG"

# ── Verify base checkpoint ───────────────────────────────────────────────────
if [ ! -d "$BASE_CKPT" ]; then
    echo "[run7] ERROR: base checkpoint not found: $BASE_CKPT" | tee -a "$LOG"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Curriculum DAgger iterations
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[run7] $(ts) ── Phase 1: Curriculum collection (8 iters) ──" | tee -a "$LOG"

CURRENT_CKPT="$BASE_CKPT"
LEROBOT_DIRS=""  # colon-separated list of all collected dataset dirs

for ITER in $(seq 1 $ITERS); do
    ITER_DIR="${OUTPUT_BASE}/iter${ITER}"
    LEROBOT_DIR="${ITER_DIR}/lerobot"
    CKPT_DIR="${ITER_DIR}/checkpoint-${FINETUNE_STEPS}"
    mkdir -p "$ITER_DIR"

    # Curriculum level: 1-2→easy, 3-4→medium, 5-6→hard, 7-8→expert
    if   [ "$ITER" -le 2 ]; then CURRICULUM_LEVEL=1; LEVEL_NAME="easy"
    elif [ "$ITER" -le 4 ]; then CURRICULUM_LEVEL=2; LEVEL_NAME="medium"
    elif [ "$ITER" -le 6 ]; then CURRICULUM_LEVEL=3; LEVEL_NAME="hard"
    else                          CURRICULUM_LEVEL=4; LEVEL_NAME="expert"
    fi

    # Beta: decays each iter, clamped to 0.0
    BETA=$(python3 -c "print(f'{max(0.0, ${BETA_START} - (${ITER}-1)*${BETA_DECAY}):.3f}')")

    echo "" | tee -a "$LOG"
    echo "[run7] $(ts) ── Iter ${ITER}/${ITERS} | level=${CURRICULUM_LEVEL} (${LEVEL_NAME}) | beta=${BETA} ──" | tee -a "$LOG"

    # Collect 40 on-policy episodes with curriculum level
    echo "[run7] Collecting ${EPS_PER_ITER} episodes at curriculum level ${CURRICULUM_LEVEL}..." | tee -a "$LOG"
    $GROOT_PYTHON "$DAGGER_SCRIPT" \
        --base-model "$CURRENT_CKPT" \
        --episodes-per-iter "$EPS_PER_ITER" \
        --dagger-iters 1 \
        --finetune-steps "$FINETUNE_STEPS" \
        --beta-start "$BETA" \
        --beta-decay 0.0 \
        --curriculum-level "$CURRICULUM_LEVEL" \
        --output-dir "$ITER_DIR" \
        --server-url http://localhost:8002 \
        2>&1 | tee -a "$LOG"

    # Accumulate dataset dirs for final fine-tune
    if [ -z "$LEROBOT_DIRS" ]; then
        LEROBOT_DIRS="$LEROBOT_DIR"
    else
        LEROBOT_DIRS="${LEROBOT_DIRS}:${LEROBOT_DIR}"
    fi

    # Resolve checkpoint produced by this iteration
    NEW_CKPT=$(ls -d "${ITER_DIR}"/checkpoint-* 2>/dev/null | sort -V | tail -1)
    if [ -z "$NEW_CKPT" ]; then
        echo "[run7] ERROR: no checkpoint found in ${ITER_DIR} after iter ${ITER}" | tee -a "$LOG"
        exit 1
    fi
    CURRENT_CKPT="$NEW_CKPT"
    echo "[run7] $(ts) Iter ${ITER} done. Checkpoint: $CURRENT_CKPT" | tee -a "$LOG"
done

echo "" | tee -a "$LOG"
echo "[run7] $(ts) Phase 1 complete. Final iter checkpoint: $CURRENT_CKPT" | tee -a "$LOG"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: Final validation fine-tune on all accumulated data
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[run7] $(ts) ── Phase 2: Final 5000-step fine-tune on merged dataset ──" | tee -a "$LOG"

FINAL_DIR="${OUTPUT_BASE}/final"
mkdir -p "$FINAL_DIR"

# Verify current checkpoint exists before final fine-tune
if [ ! -d "$CURRENT_CKPT" ]; then
    echo "[run7] ERROR: no checkpoint for final fine-tune: $CURRENT_CKPT" | tee -a "$LOG"
    exit 1
fi

echo "[run7] Merged dataset dirs: $LEROBOT_DIRS" | tee -a "$LOG"
echo "[run7] Starting 5000-step fine-tune..." | tee -a "$LOG"

cd "$GROOT_REPO"
$GROOT_PYTHON gr00t/experiment/launch_finetune.py \
    --base-model-path "$CURRENT_CKPT" \
    --dataset-path "$LEROBOT_DIRS" \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path "$ROBOTICS_DIR/src/training/franka_config.py" \
    --num-gpus 1 \
    --output-dir "$FINAL_DIR" \
    --max-steps 5000 \
    --save-steps 1000 \
    --global-batch-size 16 \
    2>&1 | tee -a "$LOG"

FINAL_CKPT=$(ls -d "${FINAL_DIR}"/checkpoint-* 2>/dev/null | sort -V | tail -1)
if [ -z "$FINAL_CKPT" ]; then
    echo "[run7] ERROR: no final checkpoint found in $FINAL_DIR" | tee -a "$LOG"
    exit 1
fi
echo "[run7] $(ts) Phase 2 complete. Final checkpoint: $FINAL_CKPT" | tee -a "$LOG"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: 20-episode closed-loop evaluation
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[run7] $(ts) ── Phase 3: 20-episode closed-loop eval ──" | tee -a "$LOG"

# Restart GR00T server with final checkpoint
pkill -f "groot_franka_server.py" 2>/dev/null || true
sleep 5
nohup $GROOT_PYTHON "$SERVER_SCRIPT" \
    --checkpoint "$FINAL_CKPT" \
    --port 8002 \
    >> "${FINAL_DIR}/server.log" 2>&1 &
SERVER_PID=$!
echo "[run7] Server PID: $SERVER_PID" | tee -a "$LOG"

# Wait for server to be ready (up to 200s)
echo "[run7] Waiting for server to be ready..." | tee -a "$LOG"
for i in $(seq 1 40); do
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        echo "[run7] Server ready after ${i}×5s" | tee -a "$LOG"
        break
    fi
    sleep 5
done

python3 "$EVAL_SCRIPT" \
    --num-episodes 20 \
    --server-url http://localhost:8002 \
    --output "${OUTPUT_BASE}/eval_final" \
    2>&1 | tee -a "$LOG"

# Aggregate and compare against prior runs
echo "" | tee -a "$LOG"
echo "[run7] $(ts) Generating results report..." | tee -a "$LOG"
python3 "$RESULTS_AGG" \
    --results \
        /tmp/eval_1000demo \
        /tmp/dagger_run6/eval_final \
        "${OUTPUT_BASE}/eval_final" \
    --labels \
        "1000-demo BC" \
        "DAgger run6 final" \
        "DAgger run7 final (curriculum)" \
    --output "${OUTPUT_BASE}/progress_report.html" \
    2>&1 | tee -a "$LOG" || true

echo "" | tee -a "$LOG"
echo "[run7] $(ts) ══════════════════════════════════" | tee -a "$LOG"
echo "[run7] RUN 7 COMPLETE" | tee -a "$LOG"
echo "[run7] Final checkpoint : $FINAL_CKPT" | tee -a "$LOG"
echo "[run7] Eval results     : ${OUTPUT_BASE}/eval_final/" | tee -a "$LOG"
echo "[run7] Progress report  : ${OUTPUT_BASE}/progress_report.html" | tee -a "$LOG"
echo "[run7] Full log         : $LOG" | tee -a "$LOG"
echo "[run7] ══════════════════════════════════" | tee -a "$LOG"
