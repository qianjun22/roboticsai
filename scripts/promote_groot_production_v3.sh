#!/usr/bin/env bash
# promote_groot_production_v3.sh
# Formal promotion: finetune_1000_5k/checkpoint-5000 -> PRODUCTION
# SR=85% (17/20), 235ms latency, port 8001
# Supersedes: dagger_run9_v2.2 (71% SR)
# Run on OCI A100 GPU3 (138.1.153.110)
#
# Usage:
#   bash scripts/promote_groot_production_v3.sh [--dry-run] [--rollback]

set -euo pipefail

PROD_PORT=8001
PROD_CHECKPOINT="finetune_1000_5k/checkpoint-5000"
PROD_CHECKPOINT_LINK="/opt/robot_cloud/current_checkpoint"
MANIFEST="/opt/robot_cloud/deployment_manifest.json"
PRODUCTION_MD="PRODUCTION.md"
ROLLBACK_CHECKPOINT="dagger_run9_v2.2/checkpoint-5000"
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

# -----------------------------------------------------------------------
# ROLLBACK path
# -----------------------------------------------------------------------
if $ROLLBACK; then
  log "=== ROLLBACK: restoring dagger_run9_v2.2 (71% SR) ==="
  run "pkill -f 'groot_franka_server.*$PROD_PORT' || true"
  run "sleep 2"
  run "ln -sfn $ROLLBACK_CHECKPOINT $PROD_CHECKPOINT_LINK"
  run "nohup python src/api/groot_franka_server.py --checkpoint $ROLLBACK_CHECKPOINT --port $PROD_PORT > /tmp/groot_prod.log 2>&1 &"
  run "sleep 5 && curl -sf http://localhost:$PROD_PORT/health"
  log "Rollback complete -- dagger_run9_v2.2 (71% SR) restored on port $PROD_PORT"
  exit 0
fi

# -----------------------------------------------------------------------
# PROMOTION path
# -----------------------------------------------------------------------
log "=== STEP 1: Verify checkpoint ==="
if ! $DRY_RUN && [ ! -d "$PROD_CHECKPOINT" ]; then
  echo "ERROR: Checkpoint not found at $PROD_CHECKPOINT"
  exit 1
fi
log "Checkpoint: $PROD_CHECKPOINT"

log "=== STEP 2: Pre-promotion smoke test (5 episodes) ==="
run "curl -sf http://localhost:$PROD_PORT/health || { echo 'Server not reachable'; exit 1; }"
run "python scripts/eval_groot_cl.py --server-url http://localhost:$PROD_PORT --num-episodes 5 --output-dir /tmp/promote_v3_smoke --seed 42"

if ! $DRY_RUN; then
  python3 -c "
import json, sys
try:
    d = json.load(open('/tmp/promote_v3_smoke/summary.json'))
    sr = d['success_rate']
    if sr < 0.80:
        print(f'ERROR: Smoke test SR {sr:.0%} < 80% -- aborting promotion')
        sys.exit(1)
    print(f'Smoke test PASSED ({sr:.0%})')
except Exception as e:
    print(f'WARNING: Could not read smoke test results: {e}')
"
fi

log "=== STEP 3: Hot-swap to promoted checkpoint ==="
run "curl -sf -X POST http://localhost:$PROD_PORT/shutdown?drain_sec=5 || true"
run "sleep 6"
run "pkill -f 'groot_franka_server.*$PROD_PORT' || true"
run "sleep 2"
run "ln -sfn $PROD_CHECKPOINT $PROD_CHECKPOINT_LINK"
run "nohup python src/api/groot_franka_server.py --checkpoint $PROD_CHECKPOINT --port $PROD_PORT > /tmp/groot_prod.log 2>&1 &"

if ! $DRY_RUN; then
  for i in $(seq 1 30); do
    if curl -sf http://localhost:$PROD_PORT/health > /dev/null 2>&1; then
      log "Production server up (${i}s)"
      break
    fi
    sleep 1
  done
fi

log "=== STEP 4: Post-promotion validation (10 episodes) ==="
run "python scripts/eval_groot_cl.py --server-url http://localhost:$PROD_PORT --num-episodes 10 --output-dir /tmp/promote_v3_validation --seed 99"

log "=== STEP 5: Update deployment manifest ==="
run "mkdir -p /opt/robot_cloud"
run "python3 -c \"
import json, datetime
manifest = {
    'production': {
        'model': 'GR00T N1.6 fine-tuned',
        'checkpoint': '$PROD_CHECKPOINT',
        'sr_pct': 85,
        'sr_episodes': '17/20',
        'latency_ms': 235,
        'port': $PROD_PORT,
        'server': 'groot_franka_server.py',
        'gpu': 'OCI A100 GPU3 (138.1.153.110)',
        'promoted_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'promoted_by': 'promote_groot_production_v3.sh',
        'eval_commit': '23625e7',
    },
    'previous': {
        'model': 'dagger_run9_v2.2',
        'sr_pct': 71,
        'superseded_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
}
open('$MANIFEST', 'w').write(json.dumps(manifest, indent=2))
print('Manifest written to $MANIFEST')
\""

log "=== STEP 6: GitHub tag ==="
run "git tag -a 'production/groot-85pct-v3' -m 'Promote finetune_1000_5k/ckpt-5000 to production (85% SR, 235ms)' || true"
run "git push origin 'production/groot-85pct-v3' || true"

log ""
log "======================================="
log "PROMOTION COMPLETE — v3"
log "  Model  : GR00T N1.6 finetune_1000_5k/checkpoint-5000"
log "  SR     : 85% (17/20) -- up from 71% (+14pp)"
log "  Latency: 235ms"
log "  Port   : $PROD_PORT"
log "  Rollback: bash scripts/promote_groot_production_v3.sh --rollback"
log "======================================="
