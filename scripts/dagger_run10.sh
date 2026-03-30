#!/bin/bash
# OCI Robot Cloud — DAgger Run10
# Reward shaping v3.0: task_success weight 0.40→0.50, target >80% SR
# Starts from groot_finetune_v2 checkpoint (78% SR)
# Usage: bash scripts/dagger_run10.sh [--dry-run]

set -e
DRY_RUN=${1:-""}
GREEN='\033[0;32m'
AMBER='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BASE_CKPT="/home/ubuntu/isaacgr00t/checkpoints/groot_prod"
DAGGER_DIR="/tmp/dagger_run10"
N_ITERS=5
N_EPS_PER_ITER=40
FINETUNE_STEPS=5000
BETA_START=0.20
BETA_DECAY=0.80
GROOT_PORT=8001
MIN_FRAMES=10

export REWARD_TASK_SUCCESS=0.50
export REWARD_LIFT_HEIGHT=0.20
export REWARD_GRASP_STABILITY=0.13
export REWARD_SMOOTHNESS=0.10
export REWARD_EFFICIENCY=0.05
export REWARD_COLLISION=0.01
export REWARD_TIME_PENALTY=0.01

echo "============================================"
echo "  DAgger Run10 — Reward Shaping v3.0"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "  Base: groot_finetune_v2 (78% SR)"
echo "  Target: >80% SR"
echo "  Iters: $N_ITERS × $N_EPS_PER_ITER eps × ${FINETUNE_STEPS} steps"
echo "============================================"

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo -e "${AMBER}[DRY RUN]${NC} Showing plan only."
    beta=$BETA_START
    for i in $(seq 1 $N_ITERS); do
        echo "  Iter $i: beta=$beta, collect ${N_EPS_PER_ITER} eps, fine-tune ${FINETUNE_STEPS} steps"
        beta=$(echo "$beta * $BETA_DECAY" | bc -l | xargs printf '%.2f')
    done
    exit 0
fi

mkdir -p "$DAGGER_DIR"
COMBINED_DATA="$DAGGER_DIR/combined"
mkdir -p "$COMBINED_DATA"
LOG="$DAGGER_DIR/run10.log"
exec > >(tee -a "$LOG") 2>&1

if ! curl -sf "http://localhost:$GROOT_PORT/health" > /dev/null 2>&1; then
    echo -e "${RED}[ERROR]${NC} GR00T server not responding on port $GROOT_PORT"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} GR00T server up"

beta=$BETA_START
TOTAL_EPS=0

for ITER in $(seq 1 $N_ITERS); do
    ITER_DIR="$DAGGER_DIR/iter_$ITER"
    mkdir -p "$ITER_DIR"
    echo "======================================"
    echo "  Iter $ITER/$N_ITERS (beta=$beta)"
    echo "  $(date -u '+%H:%M:%S UTC')"
    echo "======================================"

    python src/training/dagger_train.py \
        --mode collect --n_episodes $N_EPS_PER_ITER --beta $beta \
        --output_dir "$ITER_DIR/raw" --groot_port $GROOT_PORT \
        --min_frames $MIN_FRAMES 2>/dev/null || true

    N_COLLECTED=$(find "$ITER_DIR/raw" -name "episode_*.npy" 2>/dev/null | wc -l || echo 0)
    TOTAL_EPS=$((TOTAL_EPS + N_COLLECTED))

    python scripts/genesis_to_lerobot.py \
        --input "$ITER_DIR/raw" --output "$ITER_DIR/lerobot" \
        --min_frames $MIN_FRAMES 2>/dev/null || true

    if [[ $ITER -gt 1 ]]; then
        python scripts/merge_datasets.py \
            --datasets "$COMBINED_DATA" "$ITER_DIR/lerobot" \
            --output "$COMBINED_DATA" 2>/dev/null || cp -r "$ITER_DIR/lerobot" "$COMBINED_DATA"
    else
        cp -r "$ITER_DIR/lerobot" "$COMBINED_DATA"
    fi

    CKPT_DIR="$DAGGER_DIR/checkpoint_iter$ITER"
    cd /home/ubuntu/isaacgr00t
    python -m gr00t.train \
        --dataset_path "$COMBINED_DATA" --output_dir "$CKPT_DIR" \
        --num_steps $FINETUNE_STEPS --learning_rate 1e-5 --batch_size 4 \
        --chunk_size 16 --lora_rank 16 \
        --resume_from_checkpoint "$BASE_CKPT" 2>/dev/null || true

    cp -r "$CKPT_DIR/checkpoint-$FINETUNE_STEPS" \
        "/home/ubuntu/isaacgr00t/checkpoints/groot_prod" 2>/dev/null || true
    pkill -f "groot_franka_server" || true
    sleep 3
    nohup python groot_franka_server.py --port $GROOT_PORT \
        --checkpoint "/home/ubuntu/isaacgr00t/checkpoints/groot_prod" \
        > /tmp/groot_server_run10.log 2>&1 &
    sleep 6

    python src/eval/closed_loop_eval.py --episodes 10 \
        --output "$ITER_DIR/eval" --host localhost --port $GROOT_PORT 2>/dev/null || true

    SR=$(python3 -c "
import json, pathlib
p = pathlib.Path('$ITER_DIR/eval/summary.json')
if p.exists():
    d = json.loads(p.read_text())
    print(f'{d.get(\"success_rate\", 0)*100:.0f}%')
else:
    print('N/A')
" 2>/dev/null || echo "N/A")
    echo -e "  ${GREEN}Iter $ITER SR: $SR${NC} (total eps: $TOTAL_EPS)"
    beta=$(echo "$beta * $BETA_DECAY" | bc -l | xargs printf '%.2f')
done

python src/eval/closed_loop_eval.py --episodes 20 \
    --output "$DAGGER_DIR/final_eval" --host localhost --port $GROOT_PORT 2>/dev/null || true

FINAL_SR=$(python3 -c "
import json, pathlib
p = pathlib.Path('$DAGGER_DIR/final_eval/summary.json')
if p.exists():
    d = json.loads(p.read_text())
    print(f'{d.get(\"success_rate\", 0)*100:.0f}%')
else:
    print('N/A')
" 2>/dev/null || echo "N/A")

echo ""
echo "============================================"
echo "  DAgger Run10 Complete"
echo "  Total episodes collected: $TOTAL_EPS"
echo "  Final SR: $FINAL_SR (target: >80%)"
echo "  Checkpoints: $DAGGER_DIR/checkpoint_iter*"
echo "============================================"
