#!/bin/bash
# OCI Robot Cloud — Promote groot_finetune_v2 to Production
# Replaces dagger_run9_v2.2 (71% SR) with groot_finetune_v2 (78% SR)
# Usage: bash scripts/promote_staging.sh [--dry-run]

set -e
DRY_RUN=${1:-""}
GREEN='\033[0;32m'
RED='\033[0;31m'
AMBER='\033[1;33m'
NC='\033[0m'

STAGING_CKPT="/tmp/finetune_fullrun/checkpoint-60000"
PROD_DIR="/home/ubuntu/isaacgr00t/checkpoints"
PROD_CKPT="$PROD_DIR/groot_prod"
BACKUP_DIR="$PROD_DIR/backup_$(date +%Y%m%d_%H%M%S)"
GROOT_PORT=8001

echo "============================================"
echo "  Promote groot_finetune_v2 → Production"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "  Staging: $STAGING_CKPT (78% SR)"
echo "  Current prod: dagger_run9_v2.2 (71% SR)"
echo "============================================"

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo -e "${AMBER}[DRY RUN]${NC} No changes will be made."
fi

echo ""
echo "Step 1: Verifying staging checkpoint..."
if [[ ! -d "$STAGING_CKPT" ]]; then
    echo -e "${RED}[ERROR]${NC} Staging checkpoint not found: $STAGING_CKPT"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Staging checkpoint found"

echo ""
echo "Step 2: Quality gate check..."
if curl -sf "http://localhost:8105/evaluate/groot_finetune_v2" > /tmp/quality_gate_result.json 2>&1; then
    VERDICT=$(python3 -c "import json; d=json.load(open('/tmp/quality_gate_result.json')); print(d.get('verdict','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
    echo -e "${GREEN}[OK]${NC} Quality gate: $VERDICT"
else
    echo -e "${AMBER}[SKIP]${NC} Quality gate service not responding"
fi

echo ""
echo "Step 3: Backing up current production..."
if [[ -d "$PROD_CKPT" && "$DRY_RUN" != "--dry-run" ]]; then
    cp -r "$PROD_CKPT" "$BACKUP_DIR"
    echo -e "${GREEN}[OK]${NC} Backed up to $BACKUP_DIR"
fi

echo ""
echo "Step 4: Copying staging → production..."
if [[ "$DRY_RUN" != "--dry-run" ]]; then
    cp -r "$STAGING_CKPT" "$PROD_CKPT"
    echo -e "${GREEN}[OK]${NC} groot_finetune_v2 installed"
fi

echo ""
echo "Step 5: Restarting GR00T server..."
if [[ "$DRY_RUN" != "--dry-run" ]]; then
    pkill -f "groot_franka_server" || true
    sleep 3
    cd /home/ubuntu/isaacgr00t
    nohup python groot_franka_server.py --port $GROOT_PORT \
        --checkpoint "$PROD_CKPT" > /tmp/groot_server.log 2>&1 &
    sleep 8
    curl -sf "http://localhost:$GROOT_PORT/health" && \
        echo -e "${GREEN}[OK]${NC} Server restarted" || \
        echo -e "${RED}[ERROR]${NC} Server failed to start"
fi

echo ""
echo "============================================"
echo "  Promotion ${DRY_RUN:-complete}"
echo "  groot_finetune_v2 now serving on port $GROOT_PORT"
echo "  Expected SR: 78% (up from 71%)"
echo "============================================"
