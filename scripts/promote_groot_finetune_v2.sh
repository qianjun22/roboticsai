#!/usr/bin/env bash
# promote_groot_finetune_v2.sh
# Promote groot_finetune_v2 (78% SR, STAGING) -> PRODUCTION
# Replaces dagger_run9_v2.2 (71% SR) on port 8001
# Run on OCI A100 GPU4 (138.1.153.110)
#
# Usage:
#   bash scripts/promote_groot_finetune_v2.sh [--dry-run] [--rollback]

set -euo pipefail

STAGING_PORT=8002
PROD_PORT=8001
STAGING_CHECKPOINT="/tmp/finetune_v2/checkpoint-5000"
PROD_CHECKPOINT_LINK="/opt/robot_cloud/current_checkpoint"
MANIFEST="/opt/robot_cloud/deployment_manifest.json"
ROLLBACK_CHECKPOINT="/tmp/dagger_run9_v2.2/checkpoint-5000"
DRY_RUN=false
ROLLBACK=false

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --rollback) ROLLBACK=true ;;
  esac
done

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
run() {
  if $DRY_RUN; then
    echo "[DRY-RUN] $*"
  else
    eval "$*"
  fi
}

if $ROLLBACK; then
  log "=== ROLLBACK: restoring dagger_run9_v2.2 ==="
  run "pkill -f 'groot_franka_server.*8001' || true"
  run "sleep 2"
  run "ln -sfn $ROLLBACK_CHECKPOINT $PROD_CHECKPOINT_LINK"
  run "nohup python src/api/groot_franka_server.py --checkpoint $ROLLBACK_CHECKPOINT --port $PROD_PORT > /tmp/groot_prod.log 2>&1 &"
  run "sleep 5 && curl -sf http://localhost:$PROD_PORT/health"
  log "Rollback complete -- dagger_run9_v2.2 (71% SR) restored on port $PROD_PORT"
  exit 0
fi

log "=== STEP 1: Verify staging checkpoint ==="
if [ ! -d "$STAGING_CHECKPOINT" ]; then
  echo "ERROR: Staging checkpoint not found at $STAGING_CHECKPOINT"
  exit 1
fi
log "Checkpoint found: $STAGING_CHECKPOINT"

log "=== STEP 2: Staging smoke test (5 episodes on port $STAGING_PORT) ==="
run "curl -sf http://localhost:$STAGING_PORT/health || { echo 'Staging server not running'; exit 1; }"
run "python src/eval/closed_loop_eval.py --server-url http://localhost:$STAGING_PORT --num-episodes 5 --output-dir /tmp/promote_smoke_test --seed 42"

if ! $DRY_RUN; then
  python3 -c "
import json
d = json.load(open('/tmp/promote_smoke_test/summary.json'))
sr = d['success_rate']
if sr < 0.60:
    print(f'ERROR: Smoke test SR {sr:.0%} < 60% -- aborting')
    exit(1)
print(f'Smoke test PASSED ({sr:.0%})')
"
fi

log "=== STEP 3: Hot-swap production model ==="
run "curl -sf -X POST http://localhost:$PROD_PORT/shutdown?drain_sec=5 || true"
run "sleep 6"
run "pkill -f 'groot_franka_server.*$PROD_PORT' || true"
run "sleep 2"
run "ln -sfn $STAGING_CHECKPOINT $PROD_CHECKPOINT_LINK"
run "nohup python src/api/groot_franka_server.py --checkpoint $STAGING_CHECKPOINT --port $PROD_PORT > /tmp/groot_prod.log 2>&1 &"

if ! $DRY_RUN; then
  for i in $(seq 1 30); do
    if curl -sf http://localhost:$PROD_PORT/health > /dev/null 2>&1; then
      log "Production server up (${i}s)"
      break
    fi
    sleep 1
  done
fi

log "=== STEP 4: Production validation (5 episodes) ==="
run "python src/eval/closed_loop_eval.py --server-url http://localhost:$PROD_PORT --num-episodes 5 --output-dir /tmp/promote_validation --seed 42"

log "=== STEP 5: Update deployment manifest ==="
run "python3 -c \"import json, datetime; manifest = {'production': {'model': 'groot_finetune_v2', 'checkpoint': '$STAGING_CHECKPOINT', 'sr_pct': 78, 'latency_ms': 226, 'promoted_at': datetime.datetime.utcnow().isoformat()+'Z', 'previous_model': 'dagger_run9_v2.2', 'previous_sr_pct': 71}}; open('$MANIFEST', 'w').write(json.dumps(manifest, indent=2))\""

log "=== STEP 6: GitHub tag ==="
run "git tag -a 'production/groot_finetune_v2' -m 'Promote groot_finetune_v2 to production (78% SR)' || true"
run "git push origin 'production/groot_finetune_v2' || true"

log ""
log "======================================="
log "PROMOTION COMPLETE"
log "  groot_finetune_v2 -> PRODUCTION (port $PROD_PORT)"
log "  SR: 71% -> 78% (+7pp)"
log "  Rollback: bash scripts/promote_groot_finetune_v2.sh --rollback"
log "======================================="
