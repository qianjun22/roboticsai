#!/bin/bash
# dagger_run9.sh — GTC-Ready DAgger Run 9: >90% Closed-Loop Success Target
#
# This is the production-quality training run intended to produce a checkpoint
# suitable for live demonstration at GTC 2027. It builds on run8's flywheel
# foundation and pushes the policy into the >90% success regime via three
# progressively demanding phases with per-phase evaluation and early stopping.
#
# ── ARCHITECTURE ─────────────────────────────────────────────────────────────
#
#   Phase 1 — Warmup (4 iters × 40 eps × 3000 steps, beta_start=0.08)
#     Low teacher-forcing from the start (policy already strong from run8).
#     Goal: stabilize policy on current distribution, gather diverse on-policy
#     data, quality-filter and deduplicate before each fine-tune step.
#
#   Phase 2 — Main (6 iters × 50 eps × 4000 steps, beta decays 0.05→0.0)
#     Gradually removes teacher-forcing entirely. Finer-grained eval after
#     each iteration tracks SR progress toward the 90% threshold.
#     Data quality scorer (min-score=6.0) and deduplication (threshold=0.40)
#     applied before every fine-tune to keep training signal clean.
#
#   Phase 3 — Refinement (2 iters × 30 eps × 2000 steps, beta=0.0)
#     Pure on-policy rollouts — zero teacher-forcing. The policy must succeed
#     entirely on its own. Stricter quality threshold (min-score=7.0).
#
# ── EVAL & EARLY STOP ────────────────────────────────────────────────────────
#   After each phase, 20-episode closed-loop eval runs against the latest
#   checkpoint. SR is appended to /tmp/dagger_run9/eval_history.json.
#   If SR >= 0.90, the script exits immediately with success and promotes the
#   checkpoint to /tmp/production_checkpoint_gtc/.
#
# ── CHECKPOINT RESUME ────────────────────────────────────────────────────────
#   On re-invocation the script detects an existing phase marker file
#   (/tmp/dagger_run9/phase_N.done) and skips completed phases, resuming from
#   the last completed checkpoint so re-runs are idempotent.
#
# ── COST ESTIMATE ────────────────────────────────────────────────────────────
#   Phase 1: 4 iters × (40-ep collect ~5min + 3000-step train ~18min) ≈ 92min
#   Phase 2: 6 iters × (50-ep collect ~7min + 4000-step train ~24min) ≈ 186min
#   Phase 3: 2 iters × (30-ep collect ~4min + 2000-step train ~12min) ≈ 32min
#   Total: ~310min ≈ 5.2h → with GPU4 BM.GPU4.8 ($4.20/hr) ≈ $21.84
#   (Single-GPU share: ~1/8 GPU → ~1.8 effective GPU-hours × $4.20 ≈ $7.56)
#
# ── OCI TARGET HOST ──────────────────────────────────────────────────────────
#   ubuntu@138.1.153.110, CUDA_VISIBLE_DEVICES=4
#
# ── USAGE ────────────────────────────────────────────────────────────────────
#   # Normal run (inside tmux on OCI GPU4):
#   tmux new -s dagger_run9
#   bash src/training/dagger_run9.sh
#
#   # Dry-run (prints all commands, skips compute):
#   DRY_RUN=1 bash src/training/dagger_run9.sh
#
#   # Resume after a partial run:
#   bash src/training/dagger_run9.sh        # idempotent — skips done phases
#
# ── OUTPUTS ──────────────────────────────────────────────────────────────────
#   /tmp/dagger_run9/                — all checkpoints, episodes, eval results
#   /tmp/dagger_run9/eval_history.json  — per-phase SR log
#   /tmp/dagger_run9/run9.log           — full timestamped log
#   /tmp/dagger_run9/journey_report.html — final summary report
#   /tmp/production_checkpoint_gtc/  — promoted checkpoint (if SR >= 0.90)
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Dry-run mode ─────────────────────────────────────────────────────────────
# Set DRY_RUN=1 to print all commands without executing compute steps.
DRY_RUN="${DRY_RUN:-0}"

# ── GPU assignment ────────────────────────────────────────────────────────────
export CUDA_VISIBLE_DEVICES=4

# ── Path configuration ────────────────────────────────────────────────────────
GROOT_PYTHON="/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
GROOT_REPO="/home/ubuntu/Isaac-GR00T"
ROBOTICS_DIR="$HOME/roboticsai"

DAGGER_SCRIPT="$ROBOTICS_DIR/src/training/dagger_train.py"
QUALITY_SCORER="$ROBOTICS_DIR/src/training/data_quality_scorer.py"
DEDUP_SCRIPT="$ROBOTICS_DIR/src/training/dataset_deduplication.py"
EVAL_SCRIPT="$ROBOTICS_DIR/src/eval/closed_loop_eval.py"
SERVER_SCRIPT="$ROBOTICS_DIR/src/inference/groot_franka_server.py"
JOURNEY_SCRIPT="$ROBOTICS_DIR/src/eval/generate_journey_report.py"
FRANKA_CONFIG="$ROBOTICS_DIR/src/training/franka_config.py"

OUTPUT_BASE="/tmp/dagger_run9"
LOG="${OUTPUT_BASE}/run9.log"
EVAL_HISTORY="${OUTPUT_BASE}/eval_history.json"
GTC_CHECKPOINT="/tmp/production_checkpoint_gtc"

# ── Early-stop / success target ───────────────────────────────────────────────
SUCCESS_TARGET=0.90   # exit with success when SR >= this
EVAL_EPISODES=20      # episodes per inter-phase eval

# ── Phase 1 hyperparameters ───────────────────────────────────────────────────
P1_ITERS=4
P1_EPS_PER_ITER=40
P1_FINETUNE_STEPS=3000
P1_BETA_START=0.08
P1_QUALITY_MIN=6.0

# ── Phase 2 hyperparameters ───────────────────────────────────────────────────
P2_ITERS=6
P2_EPS_PER_ITER=50
P2_FINETUNE_STEPS=4000
P2_BETA_START=0.05
P2_BETA_END=0.0
P2_QUALITY_MIN=6.0

# ── Phase 3 hyperparameters ───────────────────────────────────────────────────
P3_ITERS=2
P3_EPS_PER_ITER=30
P3_FINETUNE_STEPS=2000
P3_BETA=0.0
P3_QUALITY_MIN=7.0

# ── Deduplication threshold (L2 distance, lower = stricter) ───────────────────
DEDUP_THRESHOLD=0.40

# ── Batch size / save cadence ─────────────────────────────────────────────────
GLOBAL_BATCH_SIZE=16
SAVE_STEPS=1000

# ─────────────────────────────────────────────────────────────────────────────
# Setup: directories, logging
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_BASE"

# Timestamped log helper
ts()  { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[run9] $(ts) $*" | tee -a "$LOG"; }

# Initialize eval history JSON if it doesn't exist
if [ ! -f "$EVAL_HISTORY" ]; then
    echo '{"evals": []}' > "$EVAL_HISTORY"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight: verify required files exist
# ─────────────────────────────────────────────────────────────────────────────
log "===== DAgger Run 9 — GTC-Ready Production Run START ====="
log "DRY_RUN=${DRY_RUN} | CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
log "Success target: SR >= ${SUCCESS_TARGET} after any phase eval"

preflight_failed=0
for required in "$DAGGER_SCRIPT" "$QUALITY_SCORER" "$DEDUP_SCRIPT" \
                "$EVAL_SCRIPT" "$SERVER_SCRIPT" "$JOURNEY_SCRIPT" \
                "$FRANKA_CONFIG"; do
    if [ ! -f "$required" ]; then
        log "ERROR: required file not found: $required"
        preflight_failed=1
    fi
done

if [ "$preflight_failed" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
        log "Aborting — fix missing files before continuing."
        exit 1
    else
        log "[DRY_RUN] Ignoring missing files (not executing compute)."
    fi
fi

if [ "$DRY_RUN" -eq 0 ] && ! command -v "$GROOT_PYTHON" &>/dev/null; then
    log "ERROR: GR00T Python not found at $GROOT_PYTHON"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint resolution: run8 final → run6 best → error
# ─────────────────────────────────────────────────────────────────────────────
resolve_checkpoint() {
    # Prefer run9's own latest checkpoint (resume support)
    local run9_ckpt
    run9_ckpt=$(ls -d "${OUTPUT_BASE}"/*/finetune/checkpoint-* 2>/dev/null \
                | sort -V | tail -1 || true)
    if [ -n "$run9_ckpt" ] && [ -d "$run9_ckpt" ]; then
        echo "$run9_ckpt"
        return
    fi

    # run8 merged checkpoint (primary upstream)
    local run8_merged="/tmp/dagger_run8/merged_checkpoint"
    if [ -d "$run8_merged" ]; then
        echo "$run8_merged"
        return
    fi

    # run8 final checkpoint (fallback within run8)
    local run8_final
    run8_final=$(ls -d /tmp/dagger_run8/*/finetune/checkpoint-* 2>/dev/null \
                 | sort -V | tail -1 || true)
    if [ -n "$run8_final" ] && [ -d "$run8_final" ]; then
        echo "$run8_final"
        return
    fi

    # run6 best checkpoint (last-resort fallback)
    local run6_ckpt
    run6_ckpt=$(ls -d /tmp/dagger_run6/iter*/finetune/checkpoint-* 2>/dev/null \
                | sort -V | tail -1 || true)
    if [ -n "$run6_ckpt" ] && [ -d "$run6_ckpt" ]; then
        log "WARNING: run8 checkpoint not found — falling back to run6: $run6_ckpt"
        echo "$run6_ckpt"
        return
    fi

    echo ""
}

BASE_CKPT=$(resolve_checkpoint)
if [ -z "$BASE_CKPT" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        BASE_CKPT="/tmp/DRYRUN_PLACEHOLDER/checkpoint-0000"
        log "[DRY_RUN] No upstream checkpoint found; using placeholder: $BASE_CKPT"
    else
        log "ERROR: no valid base checkpoint found."
        log "  Checked: /tmp/dagger_run8/merged_checkpoint"
        log "           /tmp/dagger_run8/*/finetune/checkpoint-*"
        log "           /tmp/dagger_run6/iter*/finetune/checkpoint-*"
        exit 1
    fi
fi

log "Base checkpoint  : $BASE_CKPT"
log "Output           : $OUTPUT_BASE"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers: collect → quality-filter → dedup → fine-tune
# ─────────────────────────────────────────────────────────────────────────────

# run_collect PHASE ITER EPS BETA ITER_DIR
# Runs dagger_train.py to collect on-policy episodes.
run_collect() {
    local phase="$1" iter="$2" eps="$3" beta="$4" iter_dir="$5"
    local raw_dir="${iter_dir}/episodes_raw"
    mkdir -p "$raw_dir"

    log "  [Collect] phase=${phase} iter=${iter} eps=${eps} beta=${beta}"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  [DRY_RUN] $GROOT_PYTHON $DAGGER_SCRIPT \\"
        log "      --checkpoint <CKPT> --num-episodes ${eps} --beta ${beta} \\"
        log "      --output-dir ${raw_dir} --server-url http://localhost:8002"
        # Create placeholder directory so downstream steps can proceed
        mkdir -p "${raw_dir}/episode_000000"
    else
        $GROOT_PYTHON "$DAGGER_SCRIPT" \
            --checkpoint "$CURRENT_CKPT" \
            --num-episodes "$eps" \
            --beta "$beta" \
            --output-dir "$raw_dir" \
            --server-url http://localhost:8002 \
            2>&1 | tee -a "$LOG"
    fi
}

# run_quality_filter RAW_DIR FILTERED_DIR MIN_SCORE
# Scores episodes and copies those above min-score to filtered dir.
run_quality_filter() {
    local raw_dir="$1" filtered_dir="$2" min_score="$3"
    mkdir -p "$filtered_dir"

    log "  [QualityFilter] min-score=${min_score} | raw=${raw_dir} → filtered=${filtered_dir}"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  [DRY_RUN] $GROOT_PYTHON $QUALITY_SCORER \\"
        log "      --episodes-dir ${raw_dir} --output ${filtered_dir}/quality_report.html \\"
        log "      --min-score ${min_score} --filtered-dir ${filtered_dir}"
        # Mirror raw structure for dry-run so dedup has something to read
        cp -r "${raw_dir}/." "${filtered_dir}/" 2>/dev/null || true
    else
        $GROOT_PYTHON "$QUALITY_SCORER" \
            --episodes-dir "$raw_dir" \
            --output "${filtered_dir}/quality_report.html" \
            --min-score "$min_score" \
            --filtered-dir "$filtered_dir" \
            2>&1 | tee -a "$LOG"
    fi
}

# run_dedup FILTERED_DIR DEDUPED_DIR
# Removes near-duplicate episodes.
run_dedup() {
    local filtered_dir="$1" deduped_dir="$2"
    mkdir -p "$deduped_dir"

    log "  [Dedup] threshold=${DEDUP_THRESHOLD} | ${filtered_dir} → ${deduped_dir}"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  [DRY_RUN] $GROOT_PYTHON $DEDUP_SCRIPT \\"
        log "      --input-dir ${filtered_dir} --output-dir ${deduped_dir} \\"
        log "      --threshold ${DEDUP_THRESHOLD} --output ${deduped_dir}/dedup_report.html"
        cp -r "${filtered_dir}/." "${deduped_dir}/" 2>/dev/null || true
    else
        $GROOT_PYTHON "$DEDUP_SCRIPT" \
            --input-dir "$filtered_dir" \
            --output-dir "$deduped_dir" \
            --threshold "$DEDUP_THRESHOLD" \
            --output "${deduped_dir}/dedup_report.html" \
            2>&1 | tee -a "$LOG"
    fi
}

# run_finetune PHASE ITER DEDUPED_DIR FINETUNE_DIR STEPS
# Fine-tunes GR00T on the clean dataset. Updates CURRENT_CKPT on success.
run_finetune() {
    local phase="$1" iter="$2" deduped_dir="$3" finetune_dir="$4" steps="$5"
    mkdir -p "$finetune_dir"

    log "  [Finetune] phase=${phase} iter=${iter} steps=${steps}"
    log "             dataset=${deduped_dir} → ${finetune_dir}"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  [DRY_RUN] $GROOT_PYTHON $GROOT_REPO/gr00t/experiment/launch_finetune.py \\"
        log "      --base-model-path <CKPT> --dataset-path ${deduped_dir} \\"
        log "      --embodiment-tag NEW_EMBODIMENT --modality-config-path ${FRANKA_CONFIG} \\"
        log "      --num-gpus 1 --output-dir ${finetune_dir} --max-steps ${steps} \\"
        log "      --save-steps ${SAVE_STEPS} --global-batch-size ${GLOBAL_BATCH_SIZE}"
        mkdir -p "${finetune_dir}/checkpoint-${steps}"
    else
        (cd "$GROOT_REPO" && $GROOT_PYTHON gr00t/experiment/launch_finetune.py \
            --base-model-path "$CURRENT_CKPT" \
            --dataset-path "$deduped_dir" \
            --embodiment-tag NEW_EMBODIMENT \
            --modality-config-path "$FRANKA_CONFIG" \
            --num-gpus 1 \
            --output-dir "$finetune_dir" \
            --max-steps "$steps" \
            --save-steps "$SAVE_STEPS" \
            --global-batch-size "$GLOBAL_BATCH_SIZE" \
            2>&1 | tee -a "$LOG")
    fi

    # Resolve latest checkpoint in the fine-tune output
    local new_ckpt
    new_ckpt=$(ls -d "${finetune_dir}"/checkpoint-* 2>/dev/null | sort -V | tail -1 || true)
    if [ -z "$new_ckpt" ] && [ "$DRY_RUN" -eq 0 ]; then
        log "ERROR: no checkpoint found after fine-tune in ${finetune_dir}"
        exit 1
    fi
    if [ -z "$new_ckpt" ]; then
        new_ckpt="${finetune_dir}/checkpoint-${steps}"
    fi

    CURRENT_CKPT="$new_ckpt"
    log "  New checkpoint: $CURRENT_CKPT"
}

# ─────────────────────────────────────────────────────────────────────────────
# Eval + early-stop helper
# ─────────────────────────────────────────────────────────────────────────────

# Ensure the GR00T inference server is running with CURRENT_CKPT.
start_server() {
    log "Starting GR00T inference server with checkpoint: $CURRENT_CKPT"

    pkill -f "groot_franka_server.py" 2>/dev/null || true
    sleep 3

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY_RUN] Skipping server launch."
        return
    fi

    nohup $GROOT_PYTHON "$SERVER_SCRIPT" \
        --checkpoint "$CURRENT_CKPT" \
        --port 8002 \
        >> "${OUTPUT_BASE}/server.log" 2>&1 &
    SERVER_PID=$!
    log "Server launched (PID ${SERVER_PID}), polling /health ..."

    local ready=0
    for i in $(seq 1 36); do
        if curl -s http://localhost:8002/health >/dev/null 2>&1; then
            log "Server ready after $((i * 5))s"
            ready=1
            break
        fi
        sleep 5
    done

    if [ "$ready" -eq 0 ]; then
        log "ERROR: GR00T server did not become ready within 180s"
        exit 1
    fi
}

# run_eval PHASE_LABEL EVAL_DIR
# Runs closed-loop eval, appends result to eval_history.json, and checks
# early-stop condition. Sets LAST_SR variable.
LAST_SR="0.00"
run_eval() {
    local phase_label="$1" eval_dir="$2"
    mkdir -p "$eval_dir"

    log "===== Eval: ${phase_label} (${EVAL_EPISODES} episodes) ====="
    start_server

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY_RUN] Skipping closed-loop eval; reporting SR=0.00"
        LAST_SR="0.00"
    else
        $GROOT_PYTHON "$EVAL_SCRIPT" \
            --server-url http://localhost:8002 \
            --num-episodes "$EVAL_EPISODES" \
            --output "$eval_dir" \
            2>&1 | tee -a "$LOG"

        # Extract SR from summary.json (preferred) or summary.txt fallback
        if [ -f "${eval_dir}/summary.json" ]; then
            LAST_SR=$(python3 -c \
                "import json; d=json.load(open('${eval_dir}/summary.json')); print(f\"{d.get('success_rate', d.get('sr', 0.0)):.4f}\")" \
                2>/dev/null || echo "0.00")
        elif [ -f "${eval_dir}/summary.txt" ]; then
            LAST_SR=$(grep -oP '(?<=success_rate: )\d+\.\d+' "${eval_dir}/summary.txt" \
                      2>/dev/null | tail -1 || echo "0.00")
        else
            log "WARNING: no eval summary found in ${eval_dir}; defaulting SR=0.00"
            LAST_SR="0.00"
        fi
    fi

    log "  SR=${LAST_SR} (target=${SUCCESS_TARGET})"

    # Append to eval history
    python3 - <<PYEOF
import json, datetime, pathlib
h = json.loads(pathlib.Path("${EVAL_HISTORY}").read_text())
h["evals"].append({
    "phase": "${phase_label}",
    "checkpoint": "${CURRENT_CKPT}",
    "success_rate": float("${LAST_SR}"),
    "eval_episodes": ${EVAL_EPISODES},
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
})
pathlib.Path("${EVAL_HISTORY}").write_text(json.dumps(h, indent=2))
PYEOF

    # Early-stop check
    local meets_target
    meets_target=$(python3 -c \
        "print(1 if float('${LAST_SR}') >= ${SUCCESS_TARGET} else 0)" 2>/dev/null || echo 0)

    if [ "$meets_target" -eq 1 ]; then
        log ""
        log "***** EARLY STOP: SR=${LAST_SR} >= ${SUCCESS_TARGET} after ${phase_label} *****"
        log "Promoting checkpoint to ${GTC_CHECKPOINT}"
        if [ "$DRY_RUN" -eq 0 ]; then
            rm -rf "$GTC_CHECKPOINT"
            cp -r "$CURRENT_CKPT" "$GTC_CHECKPOINT"
        fi
        finalize_and_exit 0
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Finalization: generate journey report and print summary
# ─────────────────────────────────────────────────────────────────────────────
finalize_and_exit() {
    local exit_code="$1"
    echo "" | tee -a "$LOG"
    log "===== DAgger Run 9 — Finalizing ====="
    log "Generating journey report ..."

    local journey_output="${OUTPUT_BASE}/journey_report.html"
    local eval_dirs=""
    # Collect all per-phase eval dirs in order
    for phase_dir in "${OUTPUT_BASE}"/phase*/eval; do
        [ -d "$phase_dir" ] && eval_dirs="${eval_dirs} ${phase_dir}"
    done

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY_RUN] Skipping journey report generation."
    else
        python3 "$JOURNEY_SCRIPT" \
            --output "$journey_output" \
            ${eval_dirs:+--eval-dirs $eval_dirs} \
            2>&1 | tee -a "$LOG" || log "WARNING: journey report generation failed (non-fatal)"
    fi

    echo "" | tee -a "$LOG"
    log "===== DAgger Run 9 — COMPLETE ====="
    log "Final checkpoint : $CURRENT_CKPT"
    log "Final SR         : $LAST_SR"
    log "GTC checkpoint   : ${GTC_CHECKPOINT} (exists=$([ -d $GTC_CHECKPOINT ] && echo yes || echo no))"
    log "Eval history     : $EVAL_HISTORY"
    log "Journey report   : $journey_output"
    log "Full log         : $LOG"
    log "=================================================="

    exit "$exit_code"
}

# ─────────────────────────────────────────────────────────────────────────────
# Initialize CURRENT_CKPT (may be updated to a run9-internal ckpt on resume)
# ─────────────────────────────────────────────────────────────────────────────
CURRENT_CKPT="$BASE_CKPT"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Warmup (4 iters × 40 eps × 3000 steps, beta_start=0.08)
# ─────────────────────────────────────────────────────────────────────────────
PHASE1_DONE="${OUTPUT_BASE}/phase1.done"

if [ -f "$PHASE1_DONE" ]; then
    log "===== Phase 1: ALREADY DONE (skipping) ====="
    # Resume from last phase1 checkpoint
    p1_last=$(ls -d "${OUTPUT_BASE}"/phase1/iter*/finetune/checkpoint-* 2>/dev/null \
              | sort -V | tail -1 || true)
    [ -n "$p1_last" ] && CURRENT_CKPT="$p1_last"
    log "Resuming from: $CURRENT_CKPT"
else
    echo "" | tee -a "$LOG"
    log "===== Phase 1: Warmup (${P1_ITERS} iters × ${P1_EPS_PER_ITER} eps × ${P1_FINETUNE_STEPS} steps, beta_start=${P1_BETA_START}) ====="

    for ITER in $(seq 1 "$P1_ITERS"); do
        ITER_DIR="${OUTPUT_BASE}/phase1/iter${ITER}"
        mkdir -p "$ITER_DIR"

        # Constant beta throughout warmup phase
        BETA=$(python3 -c "print(f'{${P1_BETA_START}:.4f}')")

        log "── Phase 1 Iter ${ITER}/${P1_ITERS} | beta=${BETA} ──"

        run_collect "phase1" "$ITER" "$P1_EPS_PER_ITER" "$BETA" "$ITER_DIR"
        run_quality_filter "${ITER_DIR}/episodes_raw" "${ITER_DIR}/episodes_filtered" "$P1_QUALITY_MIN"
        run_dedup "${ITER_DIR}/episodes_filtered" "${ITER_DIR}/episodes_deduped"
        run_finetune "phase1" "$ITER" "${ITER_DIR}/episodes_deduped" "${ITER_DIR}/finetune" "$P1_FINETUNE_STEPS"
    done

    touch "$PHASE1_DONE"
    log "===== Phase 1 complete — current checkpoint: $CURRENT_CKPT ====="
fi

# Phase 1 eval
run_eval "Phase1-Warmup" "${OUTPUT_BASE}/phase1/eval"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Main (6 iters × 50 eps × 4000 steps, beta decays 0.05→0.0)
# ─────────────────────────────────────────────────────────────────────────────
PHASE2_DONE="${OUTPUT_BASE}/phase2.done"

if [ -f "$PHASE2_DONE" ]; then
    log "===== Phase 2: ALREADY DONE (skipping) ====="
    p2_last=$(ls -d "${OUTPUT_BASE}"/phase2/iter*/finetune/checkpoint-* 2>/dev/null \
              | sort -V | tail -1 || true)
    [ -n "$p2_last" ] && CURRENT_CKPT="$p2_last"
    log "Resuming from: $CURRENT_CKPT"
else
    echo "" | tee -a "$LOG"
    log "===== Phase 2: Main (${P2_ITERS} iters × ${P2_EPS_PER_ITER} eps × ${P2_FINETUNE_STEPS} steps, beta ${P2_BETA_START}→${P2_BETA_END}) ====="

    for ITER in $(seq 1 "$P2_ITERS"); do
        ITER_DIR="${OUTPUT_BASE}/phase2/iter${ITER}"
        mkdir -p "$ITER_DIR"

        # Beta decays linearly from P2_BETA_START to P2_BETA_END over P2_ITERS iters
        BETA=$(python3 -c "
iters=${P2_ITERS}; start=${P2_BETA_START}; end=${P2_BETA_END}; i=${ITER}
if iters == 1:
    v = end
else:
    v = start + (end - start) * (i - 1) / (iters - 1)
print(f'{max(end, v):.4f}')
")

        log "── Phase 2 Iter ${ITER}/${P2_ITERS} | beta=${BETA} ──"

        run_collect "phase2" "$ITER" "$P2_EPS_PER_ITER" "$BETA" "$ITER_DIR"
        run_quality_filter "${ITER_DIR}/episodes_raw" "${ITER_DIR}/episodes_filtered" "$P2_QUALITY_MIN"
        run_dedup "${ITER_DIR}/episodes_filtered" "${ITER_DIR}/episodes_deduped"
        run_finetune "phase2" "$ITER" "${ITER_DIR}/episodes_deduped" "${ITER_DIR}/finetune" "$P2_FINETUNE_STEPS"
    done

    touch "$PHASE2_DONE"
    log "===== Phase 2 complete — current checkpoint: $CURRENT_CKPT ====="
fi

# Phase 2 eval
run_eval "Phase2-Main" "${OUTPUT_BASE}/phase2/eval"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Refinement (2 iters × 30 eps × 2000 steps, beta=0.0)
# ─────────────────────────────────────────────────────────────────────────────
PHASE3_DONE="${OUTPUT_BASE}/phase3.done"

if [ -f "$PHASE3_DONE" ]; then
    log "===== Phase 3: ALREADY DONE (skipping) ====="
    p3_last=$(ls -d "${OUTPUT_BASE}"/phase3/iter*/finetune/checkpoint-* 2>/dev/null \
              | sort -V | tail -1 || true)
    [ -n "$p3_last" ] && CURRENT_CKPT="$p3_last"
    log "Resuming from: $CURRENT_CKPT"
else
    echo "" | tee -a "$LOG"
    log "===== Phase 3: Refinement (${P3_ITERS} iters × ${P3_EPS_PER_ITER} eps × ${P3_FINETUNE_STEPS} steps, beta=${P3_BETA}, pure on-policy) ====="

    for ITER in $(seq 1 "$P3_ITERS"); do
        ITER_DIR="${OUTPUT_BASE}/phase3/iter${ITER}"
        mkdir -p "$ITER_DIR"

        log "── Phase 3 Iter ${ITER}/${P3_ITERS} | beta=${P3_BETA} (pure on-policy) ──"

        run_collect "phase3" "$ITER" "$P3_EPS_PER_ITER" "$P3_BETA" "$ITER_DIR"
        run_quality_filter "${ITER_DIR}/episodes_raw" "${ITER_DIR}/episodes_filtered" "$P3_QUALITY_MIN"
        run_dedup "${ITER_DIR}/episodes_filtered" "${ITER_DIR}/episodes_deduped"
        run_finetune "phase3" "$ITER" "${ITER_DIR}/episodes_deduped" "${ITER_DIR}/finetune" "$P3_FINETUNE_STEPS"
    done

    touch "$PHASE3_DONE"
    log "===== Phase 3 complete — current checkpoint: $CURRENT_CKPT ====="
fi

# Phase 3 eval (final)
run_eval "Phase3-Refinement" "${OUTPUT_BASE}/phase3/eval"

# ─────────────────────────────────────────────────────────────────────────────
# All phases complete — did not hit early-stop target
# ─────────────────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
log "All 3 phases complete. Final SR=${LAST_SR} (target=${SUCCESS_TARGET})."

MEETS_TARGET=$(python3 -c \
    "print(1 if float('${LAST_SR}') >= ${SUCCESS_TARGET} else 0)" 2>/dev/null || echo 0)

if [ "$MEETS_TARGET" -eq 1 ]; then
    log "Target reached! Promoting checkpoint to ${GTC_CHECKPOINT}"
    if [ "$DRY_RUN" -eq 0 ]; then
        rm -rf "$GTC_CHECKPOINT"
        cp -r "$CURRENT_CKPT" "$GTC_CHECKPOINT"
    fi
    finalize_and_exit 0
else
    log "SR=${LAST_SR} did NOT reach target ${SUCCESS_TARGET} — manual review required."
    log "Consider: longer Phase 2, more aggressive dedup, or additional Phase 3 iters."
    finalize_and_exit 1
fi
