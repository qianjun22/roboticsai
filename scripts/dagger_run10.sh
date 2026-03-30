#!/usr/bin/env bash
# dagger_run10.sh
# DAgger run10 -- reward shaping v3.0 (task_success weight 0.40 -> 0.50)
# Starting from groot_finetune_v2 checkpoint (78% SR)
# Target: >80% SR on cube-lift
#
# Run on OCI A100 GPU4 (138.1.153.110)
# Prerequisites:
#   - groot_finetune_v2 checkpoint at /tmp/finetune_v2/checkpoint-5000
#   - GR00T server running on port 8002 (staging)
#
# Usage:
#   bash scripts/dagger_run10.sh
#   ITERS=10 EPS_PER_ITER=50 bash scripts/dagger_run10.sh  # aggressive

set -euo pipefail

ITERS=${ITERS:-6}
EPS_PER_ITER=${EPS_PER_ITER:-30}
FINETUNE_STEPS=${FINETUNE_STEPS:-5000}
BASE_CHECKPOINT="/tmp/finetune_v2/checkpoint-5000"
RUN_DIR="/tmp/dagger_run10"
GROOT_PORT=8002
GROOT_HOST="http://localhost:$GROOT_PORT"

export REWARD_TASK_SUCCESS=0.50
export REWARD_LIFT_HEIGHT=0.20
export REWARD_GRASP_STABILITY=0.13
export REWARD_SMOOTHNESS=0.10
export REWARD_EFFICIENCY=0.05
export REWARD_COLLISION=0.01
export REWARD_TIME_PENALTY=0.01

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "=== DAgger run10 --- reward shaping v3.0 ==="
log "Config: $ITERS iters x $EPS_PER_ITER eps x $FINETUNE_STEPS steps"
log "Reward v3.0: task_success=$REWARD_TASK_SUCCESS (was 0.40)"

mkdir -p "$RUN_DIR/lerobot"

[ -d "$BASE_CHECKPOINT" ] || { echo "ERROR: Base checkpoint not found: $BASE_CHECKPOINT"; exit 1; }
curl -sf "$GROOT_HOST/health" || { echo "ERROR: GR00T not running on port $GROOT_PORT"; exit 1; }

CURRENT_CHECKPOINT="$BASE_CHECKPOINT"

for iter in $(seq 1 $ITERS); do
  log "--- Iteration $iter / $ITERS ---"
  ITER_DIR="$RUN_DIR/iter_$iter"
  mkdir -p "$ITER_DIR/raw" "$ITER_DIR/lerobot" "$ITER_DIR/eval"

  BETA=$(python3 -c "print(f'{max(0.05, 0.30 - ($iter - 1) * 0.05):.2f}')")
  log "[$iter] Beta=$BETA  Collecting $EPS_PER_ITER episodes..."

  python3 src/training/dagger_train.py \
    --mode collect \
    --server-url "$GROOT_HOST" \
    --num-episodes "$EPS_PER_ITER" \
    --beta "$BETA" \
    --output-dir "$ITER_DIR/raw" \
    --reward-task-success "$REWARD_TASK_SUCCESS" \
    --reward-lift-height "$REWARD_LIFT_HEIGHT" \
    --seed "$iter"

  python3 scripts/genesis_to_lerobot.py \
    --input "$ITER_DIR/raw" \
    --output "$ITER_DIR/lerobot" \
    --min-frames 10

  MERGED="$RUN_DIR/merged_iter_$iter"
  mkdir -p "$MERGED"
  [ "$iter" -eq 1 ] && cp -r "$RUN_DIR/lerobot/." "$MERGED/" 2>/dev/null || true
  [ "$iter" -gt 1 ] && cp -r "$RUN_DIR/merged_iter_$((iter-1))/." "$MERGED/"
  python3 scripts/merge_lerobot_datasets.py \
    --base "$MERGED" --add "$ITER_DIR/lerobot" --output "$MERGED"

  ITER_FT="$RUN_DIR/finetune_iter_$iter"
  log "[$iter] Fine-tuning $FINETUNE_STEPS steps..."
  ISAAC_GROOT_ROOT="${ISAAC_GROOT_ROOT:-/root/Isaac-GR00T}"
  source "$ISAAC_GROOT_ROOT/venv/bin/activate" || true
  python "$ISAAC_GROOT_ROOT/scripts/gr00t_finetune.py" \
    --dataset-path "$MERGED" \
    --output-dir "$ITER_FT" \
    --base-model-path "$CURRENT_CHECKPOINT" \
    --batch-size 32 --max-steps "$FINETUNE_STEPS" \
    --learning-rate 1e-4 --save-steps 1000 \
    --video-backend decord --embodiment-tag new_embodiment \
    2>&1 | tee "$ITER_FT/train.log"

  CURRENT_CHECKPOINT="$ITER_FT/checkpoint-$FINETUNE_STEPS"

  pkill -f "groot_franka_server.*$GROOT_PORT" || true
  sleep 3
  nohup python src/api/groot_franka_server.py \
    --checkpoint "$CURRENT_CHECKPOINT" --port "$GROOT_PORT" \
    > "$ITER_DIR/server.log" 2>&1 &
  sleep 10

  python3 src/eval/closed_loop_eval.py \
    --server-url "$GROOT_HOST" --num-episodes 10 \
    --output-dir "$ITER_DIR/eval" --seed 99

  SR=$(python3 -c "import json; d=json.load(open('$ITER_DIR/eval/summary.json')); print(int(d['success_rate']*100))" 2>/dev/null || echo 0)
  log "[$iter] SR=${SR}%"
  python3 -c "import json,datetime; open('$RUN_DIR/progress.jsonl','a').write(json.dumps({'iter':$iter,'beta':'$BETA','sr_pct':$SR,'ts':datetime.datetime.utcnow().isoformat()+'Z'})+'\n')"

  [ "$SR" -ge 80 ] && { log "TARGET REACHED: SR=${SR}% >= 80%"; break; } || true
done

log "=== Final eval: 20 episodes ==="
mkdir -p "$RUN_DIR/final_eval"
python3 src/eval/closed_loop_eval.py \
  --server-url "$GROOT_HOST" --num-episodes 20 \
  --output-dir "$RUN_DIR/final_eval" --seed 42

FINAL_SR=$(python3 -c "import json; d=json.load(open('$RUN_DIR/final_eval/summary.json')); print(int(d['success_rate']*100))" 2>/dev/null || echo '?')

python3 -c "
import json, datetime
summary = {
    'run': 'dagger_run10', 'reward_version': 'v3.0',
    'reward_weights': {'task_success': 0.50, 'lift_height': 0.20, 'grasp_stability': 0.13,
                       'smoothness': 0.10, 'efficiency': 0.05, 'collision': 0.01, 'time_penalty': 0.01},
    'base_sr_pct': 78, 'final_sr_pct': $FINAL_SR,
    'final_checkpoint': '$CURRENT_CHECKPOINT',
    'completed_at': datetime.datetime.utcnow().isoformat() + 'Z',
}
open('$RUN_DIR/summary.json', 'w').write(json.dumps(summary, indent=2))
print('Summary written to $RUN_DIR/summary.json')
"

log "======================================="
log "DAgger run10 COMPLETE -- Final SR: ${FINAL_SR}%"
log "  If SR >= 80%: bash scripts/promote_groot_finetune_v2.sh"
log "======================================="
