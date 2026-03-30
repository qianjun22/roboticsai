#!/bin/bash
# dagger_run8.sh — Production Flywheel DAgger Run 8
#
# Architecture: 3-phase production flywheel combining curriculum DAgger,
# LoRA fine-tuning, online data augmentation, and replay buffer.
# This is designed to push GR00T past the 80% closed-loop success barrier.
#
# Phase 1 — Curriculum data collection (4 iters × 50 eps = 200 eps total)
#   Beta decays from 0.05 → 0.0 across iters (policy-dominant from iter 1).
#   Difficulty: iters 1-2 = level 2 (medium), iters 3-4 = level 3/4 (hard/expert).
#   Episodes saved per-iter to /tmp/dagger_run8/eps/iter_N/.
#
# Phase 2 — LoRA fine-tune on all accumulated episodes
#   Starts from run7 final checkpoint (fallback: run4 iter3).
#   LoRA rank=16, alpha=32, 5000 steps.
#   Adapter saved → merged into base weights for deployment.
#
# Phase 3 — Validation eval + conditional promotion
#   30-episode closed-loop eval against the merged checkpoint.
#   success_rate >= 0.60 → promotes to /tmp/production_checkpoint/.
#   Result appended to /tmp/dagger_run8.log.
#
# Launch: tmux new -s dagger_run8; bash src/training/dagger_run8.sh

set -euo pipefail

# ── Dry-run flag (set to 1 to skip compute steps for testing) ────────────────
DRY_RUN=0

# ── Paths ────────────────────────────────────────────────────────────────────
GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
GROOT_REPO="/home/ubuntu/Isaac-GR00T"
ROBOTICS_DIR="$HOME/roboticsai"
DAGGER_SCRIPT="$ROBOTICS_DIR/src/training/dagger_train.py"
LORA_SCRIPT="$ROBOTICS_DIR/src/training/lora_finetune.py"
EVAL_SCRIPT="$ROBOTICS_DIR/src/eval/closed_loop_eval.py"
SERVER_SCRIPT="$ROBOTICS_DIR/src/inference/groot_franka_server.py"

OUTPUT_BASE="/tmp/dagger_run8"
LOG="/tmp/dagger_run8.log"

# ── Checkpoint resolution: run7 final → run4 iter3 fallback ──────────────────
RUN7_CKPT=$(ls -d /tmp/dagger_run7/final/checkpoint-* 2>/dev/null | sort -V | tail -1 || true)
RUN4_FALLBACK="/tmp/dagger_run4/iter3/checkpoint-2000"

if [ -n "$RUN7_CKPT" ] && [ -d "$RUN7_CKPT" ]; then
    BASE_CKPT="$RUN7_CKPT"
elif [ -d "$RUN4_FALLBACK" ]; then
    echo "[run8] WARNING: run7 checkpoint not found; falling back to run4 iter3" | tee -a "$LOG"
    BASE_CKPT="$RUN4_FALLBACK"
else
    echo "[run8] ERROR: no valid base checkpoint found (tried run7 final and run4 iter3)" | tee -a "$LOG"
    exit 1
fi

# ── GPU + hyperparameters ─────────────────────────────────────────────────────
export CUDA_VISIBLE_DEVICES=4

ITERS=4             # curriculum collection iterations
EPS_PER_ITER=50     # episodes per iteration → 200 total
BETA_START=0.05     # initial teacher-forcing fraction (policy-dominant)
LORA_RANK=16        # LoRA intrinsic rank
LORA_ALPHA=32       # LoRA scaling (alpha/rank = 2.0)
LORA_STEPS=5000     # LoRA fine-tune steps
EVAL_EPISODES=30    # closed-loop validation episodes
PROMOTE_THRESHOLD=0.60  # promote to production if success_rate >= this

mkdir -p "$OUTPUT_BASE"

# ── Utility: timestamped log ──────────────────────────────────────────────────
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[run8] $(ts) $*" | tee -a "$LOG"; }

echo "" | tee -a "$LOG"
log "===== DAgger Run 8 — Production Flywheel START ====="
log "Base checkpoint  : $BASE_CKPT"
log "Collection       : ${ITERS} iters × ${EPS_PER_ITER} eps = $((ITERS * EPS_PER_ITER)) eps total"
log "Beta schedule    : start=${BETA_START} decaying to 0.0 over ${ITERS} iters"
log "LoRA config      : rank=${LORA_RANK}, alpha=${LORA_ALPHA}, steps=${LORA_STEPS}"
log "Eval episodes    : ${EVAL_EPISODES} (promote threshold: ${PROMOTE_THRESHOLD})"
log "Output           : $OUTPUT_BASE"
log "DRY_RUN          : $DRY_RUN"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Curriculum DAgger collection (4 iters × 50 eps)
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
log "===== Phase 1: Curriculum data collection (${ITERS} iters) ====="

# Accumulate all episode dirs for LoRA fine-tune
DATASET_DIRS=""

for ITER in $(seq 1 $ITERS); do
    ITER_EPS_DIR="${OUTPUT_BASE}/eps/iter_${ITER}"
    mkdir -p "$ITER_EPS_DIR"

    # Difficulty progression: iters 1-2 = level 2 (medium), iter 3 = level 3 (hard), iter 4 = level 4 (expert)
    if   [ "$ITER" -le 2 ]; then CURRICULUM_LEVEL=2; LEVEL_NAME="medium"
    elif [ "$ITER" -eq 3 ]; then CURRICULUM_LEVEL=3; LEVEL_NAME="hard"
    else                          CURRICULUM_LEVEL=4; LEVEL_NAME="expert"
    fi

    # Beta decays linearly from BETA_START to 0.0 over ITERS iterations
    BETA=$(python3 -c "import sys; v=max(0.0, ${BETA_START} - (${ITER}-1)*${BETA_START}/(${ITERS}-1)); print(f'{v:.3f}')" 2>/dev/null || echo "0.000")

    log "── Iter ${ITER}/${ITERS} | level=${CURRICULUM_LEVEL} (${LEVEL_NAME}) | beta=${BETA} | eps=${EPS_PER_ITER} ──"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY_RUN] Skipping data collection for iter ${ITER}"
        mkdir -p "${ITER_EPS_DIR}/lerobot"
    else
        $GROOT_PYTHON "$DAGGER_SCRIPT" \
            --base-model "$BASE_CKPT" \
            --episodes-per-iter "$EPS_PER_ITER" \
            --dagger-iters 1 \
            --finetune-steps 0 \
            --beta-start "$BETA" \
            --beta-decay 0.0 \
            --curriculum-level "$CURRICULUM_LEVEL" \
            --output-dir "$ITER_EPS_DIR" \
            --server-url http://localhost:8002 \
            2>&1 | tee -a "$LOG"
    fi

    # Accumulate dataset dirs (colon-separated, matching dagger_train.py convention)
    LEROBOT_DIR="${ITER_EPS_DIR}/lerobot"
    if [ -z "$DATASET_DIRS" ]; then
        DATASET_DIRS="$LEROBOT_DIR"
    else
        DATASET_DIRS="${DATASET_DIRS}:${LEROBOT_DIR}"
    fi
    log "Iter ${ITER} collection done. Dataset dirs so far: ${DATASET_DIRS}"
done

log "===== Phase 1 complete — ${ITERS} iters, $((ITERS * EPS_PER_ITER)) episodes collected ====="

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: LoRA fine-tune on accumulated episodes → merge into base weights
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
log "===== Phase 2: LoRA fine-tune (rank=${LORA_RANK}, alpha=${LORA_ALPHA}, ${LORA_STEPS} steps) ====="

LORA_ADAPTER_DIR="${OUTPUT_BASE}/lora_adapter"
MERGED_CKPT_DIR="${OUTPUT_BASE}/merged_checkpoint"
mkdir -p "$LORA_ADAPTER_DIR" "$MERGED_CKPT_DIR"

# Verify base checkpoint is still accessible
if [ ! -d "$BASE_CKPT" ]; then
    log "ERROR: base checkpoint missing for LoRA fine-tune: $BASE_CKPT"
    exit 1
fi

log "LoRA fine-tune: base=${BASE_CKPT} | dataset=${DATASET_DIRS} | adapter→${LORA_ADAPTER_DIR}"

if [ "$DRY_RUN" -eq 1 ]; then
    log "[DRY_RUN] Skipping LoRA fine-tune and merge"
else
    $GROOT_PYTHON "$LORA_SCRIPT" \
        --base-model   "$BASE_CKPT" \
        --dataset      "$DATASET_DIRS" \
        --output-dir   "$LORA_ADAPTER_DIR" \
        --rank         "$LORA_RANK" \
        --alpha        "$LORA_ALPHA" \
        --n-steps      "$LORA_STEPS" \
        2>&1 | tee -a "$LOG"

    # Merge LoRA adapter into base weights for clean deployment
    log "Merging LoRA adapter into base weights → ${MERGED_CKPT_DIR}"
    $GROOT_PYTHON "$LORA_SCRIPT" \
        --merge \
        --base-model   "$BASE_CKPT" \
        --lora-path    "$LORA_ADAPTER_DIR" \
        --output-dir   "$MERGED_CKPT_DIR" \
        2>&1 | tee -a "$LOG"
fi

log "===== Phase 2 complete — merged checkpoint: ${MERGED_CKPT_DIR} ====="

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: 30-episode closed-loop eval + conditional promotion
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
log "===== Phase 3: ${EVAL_EPISODES}-episode closed-loop eval + promotion ====="

EVAL_OUTPUT_DIR="${OUTPUT_BASE}/eval_final"
mkdir -p "$EVAL_OUTPUT_DIR"

# (Re)start GR00T inference server with the merged checkpoint
pkill -f "groot_franka_server.py" 2>/dev/null || true
sleep 3
nohup $GROOT_PYTHON "$SERVER_SCRIPT" \
    --checkpoint "$MERGED_CKPT_DIR" \
    --port 8002 \
    >> "${OUTPUT_BASE}/server.log" 2>&1 &
SERVER_PID=$!
log "GR00T server launched (PID ${SERVER_PID}), waiting for /health..."

# Wait up to 3 minutes for server readiness
READY=0
for i in $(seq 1 36); do
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        log "Server ready after $((i * 5))s"
        READY=1
        break
    fi
    sleep 5
done
if [ "$READY" -eq 0 ]; then
    log "ERROR: server did not become ready within 180s"
    exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
    log "[DRY_RUN] Skipping closed-loop eval; assuming success_rate=0.00"
    SUCCESS_RATE="0.00"
else
    python3 "$EVAL_SCRIPT" \
        --num-episodes "$EVAL_EPISODES" \
        --server-url http://localhost:8002 \
        --output "$EVAL_OUTPUT_DIR" \
        2>&1 | tee -a "$LOG"

    # Extract numeric success rate from eval output (format: "success_rate: 0.XX")
    SUCCESS_RATE=$(grep -oP '(?<=success_rate: )\d+\.\d+' "$EVAL_OUTPUT_DIR/summary.txt" 2>/dev/null | tail -1 || echo "0.00")
fi

log "Eval complete — success_rate=${SUCCESS_RATE} (threshold=${PROMOTE_THRESHOLD})"

# Conditional promotion to production checkpoint
PROMOTED=0
MEETS_THRESHOLD=$(python3 -c "print(1 if float('${SUCCESS_RATE}') >= ${PROMOTE_THRESHOLD} else 0)" 2>/dev/null || echo 0)

if [ "$MEETS_THRESHOLD" -eq 1 ]; then
    log "SUCCESS_RATE ${SUCCESS_RATE} >= ${PROMOTE_THRESHOLD} — promoting to /tmp/production_checkpoint/"
    if [ "$DRY_RUN" -eq 0 ]; then
        rm -rf /tmp/production_checkpoint
        cp -r "$MERGED_CKPT_DIR" /tmp/production_checkpoint
    fi
    PROMOTED=1
    log "Checkpoint promoted: /tmp/production_checkpoint/"
else
    log "SUCCESS_RATE ${SUCCESS_RATE} < ${PROMOTE_THRESHOLD} — NOT promoted (manual review required)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
log "===== DAgger Run 8 — Production Flywheel COMPLETE ====="
log "Base checkpoint    : $BASE_CKPT"
log "Episodes collected : $((ITERS * EPS_PER_ITER)) (${ITERS} iters × ${EPS_PER_ITER})"
log "LoRA adapter       : $LORA_ADAPTER_DIR"
log "Merged checkpoint  : $MERGED_CKPT_DIR"
log "Eval results       : $EVAL_OUTPUT_DIR"
log "Success rate       : $SUCCESS_RATE"
log "Promoted           : $PROMOTED (threshold=${PROMOTE_THRESHOLD})"
log "Full log           : $LOG"
log "====================================================="
