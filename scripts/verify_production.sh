#!/bin/bash
# OCI Robot Cloud — Production Verification Script
# Run on OCI A100 (138.1.153.110) to verify all production services
# Usage: bash scripts/verify_production.sh [--fix]

set -e
FIX=${1:-""}
GROOT_HOST="localhost"
PROD_PORT=8001
GATEWAY_PORT=8080
RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  OCI Robot Cloud — Production Verifier"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"
echo ""

# 1. GPU Status
echo "=== GPU Status ==="
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu \
  --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available"
echo ""

# 2. Check GR00T inference server (port 8001)
echo "=== GR00T Inference Server (port $PROD_PORT) ==="
if curl -sf "http://$GROOT_HOST:$PROD_PORT/health" > /tmp/groot_health.json 2>&1; then
    echo -e "${GREEN}[PASS]${NC} GR00T server responding"
    cat /tmp/groot_health.json
else
    echo -e "${RED}[FAIL]${NC} GR00T server not responding on port $PROD_PORT"
    if [[ "$FIX" == "--fix" ]]; then
        echo "  Attempting restart..."
        cd /home/ubuntu/isaacgr00t
        pkill -f "groot_franka_server" || true
        sleep 2
        nohup python groot_franka_server.py --port $PROD_PORT > /tmp/groot_server.log 2>&1 &
        sleep 5
        curl -sf "http://$GROOT_HOST:$PROD_PORT/health" && echo -e "${GREEN}  Restart successful${NC}" || echo -e "${RED}  Restart failed — check /tmp/groot_server.log${NC}"
    fi
fi
echo ""

# 3. Run a test inference
echo "=== Test Inference (latency check) ==="
INFERENCE_START=$(date +%s%N)
if curl -sf -X POST "http://$GROOT_HOST:$PROD_PORT/act" \
  -H "Content-Type: application/json" \
  -d '{"observation":{"image":null,"joint_state":[0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],"instruction":"pick up the cube"}}' \
  > /tmp/test_inference.json 2>&1; then
    INFERENCE_END=$(date +%s%N)
    LATENCY=$(( (INFERENCE_END - INFERENCE_START) / 1000000 ))
    echo -e "${GREEN}[PASS]${NC} Inference OK — ${LATENCY}ms"
    if [[ $LATENCY -lt 300 ]]; then
        echo -e "  Latency: ${GREEN}${LATENCY}ms${NC} (SLA: <300ms ✓)"
    else
        echo -e "  Latency: ${RED}${LATENCY}ms${NC} (SLA: <300ms ✗ — BREACH)"
    fi
else
    echo -e "${AMBER}[WARN]${NC} Inference endpoint test failed (may need correct payload format)"
fi
echo ""

# 4. Check staging model (groot_finetune_v2)
echo "=== Staging Checkpoint (groot_finetune_v2) ==="
STAGING_CKPT="/tmp/finetune_fullrun/checkpoint-60000"
if [[ -d "$STAGING_CKPT" ]]; then
    echo -e "${GREEN}[PASS]${NC} Staging checkpoint exists: $STAGING_CKPT"
    du -sh "$STAGING_CKPT" 2>/dev/null || true
    echo "  → To promote: cp -r $STAGING_CKPT /home/ubuntu/isaacgr00t/checkpoints/groot_prod"
else
    echo -e "${AMBER}[INFO]${NC} Staging checkpoint not found at $STAGING_CKPT"
    echo "  → Run: python scripts/run_full_pipeline.sh --demos 3000 --steps 60000"
fi
echo ""

# 5. Check DAgger checkpoint
echo "=== DAgger Checkpoints ==="
for ckpt in /tmp/dagger_run9_v2/checkpoint-25000 /tmp/dagger_run5_manual_finetune/checkpoint-5000; do
    if [[ -d "$ckpt" ]]; then
        echo -e "${GREEN}[PASS]${NC} $ckpt"
    else
        echo -e "${AMBER}[MISS]${NC} $ckpt (not found)"
    fi
done
echo ""

# 6. Disk space check
echo "=== Disk Space ==="
df -h / /tmp 2>/dev/null | head -5
echo ""

# 7. Process list
echo "=== Running Processes ==="
ps aux | grep -E '(groot|uvicorn|python.*port|dagger|genesis)' | grep -v grep || echo "  No matching processes"
echo ""

# 8. Summary
echo "============================================"
echo "  Summary"
echo "============================================"
GROOT_OK=$(curl -sf "http://$GROOT_HOST:$PROD_PORT/health" > /dev/null 2>&1 && echo "UP" || echo "DOWN")
if [[ "$GROOT_OK" == "UP" ]]; then
    echo -e "  GR00T port $PROD_PORT: ${GREEN}UP${NC}"
else
    echo -e "  GR00T port $PROD_PORT: ${RED}DOWN${NC}"
fi
echo ""
echo "  To run closed-loop eval (20 episodes):"
echo "    python src/eval/closed_loop_eval.py --episodes 20 --output /tmp/eval_verify"
echo ""
echo "  To promote groot_finetune_v2 (78% SR) to production:"
echo "    bash scripts/promote_staging.sh"
echo ""
echo "  To start DAgger run10 (reward v3.0, target >80% SR):"
echo "    bash scripts/dagger_run10.sh"
echo "============================================"
