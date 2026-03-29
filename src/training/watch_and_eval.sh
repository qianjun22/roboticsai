#!/bin/bash
# watch_and_eval.sh
# Watches for a checkpoint to appear and auto-runs closed-loop eval.
# Use this after launching a fine-tune to get automatic results.
#
# Usage:
#   bash src/training/watch_and_eval.sh [--checkpoint /tmp/dir/checkpoint-5000] [--n-episodes 20]
#
# Example:
#   bash src/training/watch_and_eval.sh \
#     --checkpoint /tmp/dagger_run5/finetune_final/checkpoint-5000 \
#     --n-episodes 20 \
#     --server-port 8002

set -euo pipefail

CHECKPOINT="${1:-/tmp/dagger_run5/finetune_final/checkpoint-5000}"
N_EPISODES=20
SERVER_PORT=8002
GROOT_PYTHON="${GROOT_PYTHON:-/home/ubuntu/Isaac-GR00T/.venv/bin/python3}"
ROBOTICS_DIR="${ROBOTICS_DIR:-$HOME/roboticsai}"
POLL_INTERVAL=30
OUTPUT_DIR="/tmp/eval_dagger_run5_final"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkpoint) CHECKPOINT="$2"; shift 2 ;;
    --n-episodes) N_EPISODES="$2"; shift 2 ;;
    --server-port) SERVER_PORT="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log() { echo "[watch_eval] $1"; }
log "Watching for checkpoint: $CHECKPOINT"
log "Will run $N_EPISODES-episode eval when ready."
log "Poll interval: ${POLL_INTERVAL}s"

# ── Wait for checkpoint ────────────────────────────────────────────────────────

while [ ! -d "$CHECKPOINT" ]; do
  log "Checkpoint not found, sleeping ${POLL_INTERVAL}s..."
  sleep $POLL_INTERVAL
done

log "✓ Checkpoint found: $CHECKPOINT"

# ── Restart GR00T server with new checkpoint ──────────────────────────────────

log "Stopping existing GR00T server (port $SERVER_PORT)..."
pkill -f "groot_franka_server.py" 2>/dev/null || true
sleep 5

log "Starting GR00T server with DAgger checkpoint..."
export CUDA_VISIBLE_DEVICES=4
nohup $GROOT_PYTHON $ROBOTICS_DIR/src/inference/groot_franka_server.py \
  --checkpoint "$CHECKPOINT" \
  --port $SERVER_PORT \
  >> /tmp/groot_server_dagger.log 2>&1 &

SERVER_PID=$!
log "Server starting (PID $SERVER_PID)..."

# Wait for server to be ready
for i in $(seq 1 60); do
  curl -sf "http://localhost:${SERVER_PORT}/health" > /dev/null 2>&1 && break
  sleep 5
done

if ! curl -sf "http://localhost:${SERVER_PORT}/health" > /dev/null 2>&1; then
  log "✗ Server failed to start — check /tmp/groot_server_dagger.log"
  exit 1
fi
log "✓ Server ready on port $SERVER_PORT"

# ── Run closed-loop eval ────────────────────────────────────────────────────────

mkdir -p "$OUTPUT_DIR"
OUTPUT_HTML="$OUTPUT_DIR/eval_dagger_run5_final.html"
OUTPUT_JSON="$OUTPUT_DIR/summary.json"

log "Running $N_EPISODES-episode closed-loop eval..."
$GROOT_PYTHON $ROBOTICS_DIR/src/eval/closed_loop_eval.py \
  --server-url "http://localhost:${SERVER_PORT}" \
  --n-episodes "$N_EPISODES" \
  --output "$OUTPUT_HTML" \
  --checkpoint "$CHECKPOINT" \
  2>&1 | tee /tmp/eval_dagger_run5_final.log

# Extract result
if [ -f "$OUTPUT_JSON" ]; then
  SUCCESS=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print(f\"{d['success_rate']:.1%} ({d['n_success']}/{d['n_episodes']})\")" 2>/dev/null || echo "unknown")
  log ""
  log "==================================================="
  log "DAGGER RUN5 FINAL RESULT: $SUCCESS"
  log "==================================================="
  log "Report: $OUTPUT_HTML"
  log "JSON:   $OUTPUT_JSON"
else
  log "Eval complete — check $OUTPUT_HTML for results."
fi

log "Done."
