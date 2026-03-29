#!/bin/bash
# oci_health_check.sh — Check OCI A100 instance health
# Usage: bash src/infra/oci_health_check.sh [OCI_IP] [--start-server]

OCI_IP=${1:-"138.1.153.110"}
START_SERVER=false

# Parse flags
for arg in "$@"; do
    if [ "$arg" = "--start-server" ]; then
        START_SERVER=true
    fi
done

# Track pass/fail for summary
declare -A RESULTS
ALL_PASS=true

echo "======================================"
echo "  OCI A100 Health Check"
echo "  Target: ubuntu@${OCI_IP}"
echo "======================================"
echo ""

run_check() {
    local name="$1"
    local cmd="$2"
    local output
    output=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@"${OCI_IP}" "$cmd" 2>&1)
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        RESULTS["$name"]="PASS"
        echo "[PASS] $name"
        if [ -n "$output" ]; then
            echo "$output" | sed 's/^/       /'
        fi
    else
        RESULTS["$name"]="FAIL"
        ALL_PASS=false
        echo "[FAIL] $name"
        if [ -n "$output" ]; then
            echo "$output" | sed 's/^/       /'
        fi
    fi
    echo ""
}

# 1. GPU availability (all 8 GPUs)
echo "--- 1. GPU Availability ---"
run_check "nvidia-smi (all 8 GPUs)" "nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader"

# 2. GPU4 specifically: utilization and VRAM
echo "--- 2. GPU4 Utilization & VRAM ---"
run_check "GPU4 utilization + VRAM" \
    "nvidia-smi -i 4 --query-gpu=index,utilization.gpu,memory.used,memory.free,memory.total --format=csv,noheader"

# 3. Disk space in /tmp (needs 20GB+ free)
echo "--- 3. Disk Space (/tmp needs 20GB+) ---"
run_check "Disk space /tmp >= 20GB free" \
    "python3 -c \"
import shutil
total, used, free = shutil.disk_usage('/tmp')
free_gb = free / (1024**3)
print(f'/tmp free: {free_gb:.1f} GB')
if free_gb < 20:
    print(f'WARNING: only {free_gb:.1f}GB free — need 20GB+')
    exit(1)
print('OK')
\""

# 4. Isaac-GR00T venv exists
echo "--- 4. Isaac-GR00T Venv ---"
run_check "Isaac-GR00T venv exists" \
    "test -d /home/ubuntu/Isaac-GR00T/.venv && echo 'Venv found at /home/ubuntu/Isaac-GR00T/.venv' || (test -d /home/ubuntu/isaac-groot-venv && echo 'Venv found at /home/ubuntu/isaac-groot-venv') || (find /home/ubuntu -maxdepth 3 -name 'groot_franka_server.py' 2>/dev/null | head -1 | xargs -I{} dirname {} | xargs -I{} ls {}/.. 2>/dev/null && echo 'GR00T server script found')"

# 5. GR00T model checkpoints present
echo "--- 5. GR00T Checkpoint (checkpoint-5000) ---"
run_check "checkpoint-5000 present" \
    "test -d /tmp/finetune_1000_5k/checkpoint-5000 && echo 'checkpoint-5000 found' && ls /tmp/finetune_1000_5k/checkpoint-5000/ | head -5"

# 6. DAgger dataset present
echo "--- 6. DAgger Dataset (dagger_run4) ---"
run_check "dagger_run4 lerobot dataset present" \
    "test -d /tmp/dagger_run4/lerobot && echo 'Dataset found' && du -sh /tmp/dagger_run4/lerobot"

# 7. Port 8002 status
echo "--- 7. Port 8002 (GR00T server) ---"
run_check "Port 8002 status" \
    "ss -tlnp 2>/dev/null | grep ':8002' && echo 'Port 8002: OPEN' || echo 'Port 8002: CLOSED (server not running)'"
# Port closed is not a failure — just informational
RESULTS["Port 8002 status"]="PASS"  # override: closed port is not a failure

# 8. Active python processes
echo "--- 8. Active Python Processes ---"
run_check "Python processes" \
    "ps aux | grep python | grep -v grep | awk '{print \$2, \$11, \$12, \$13}' | head -10 || echo 'No python processes running'"
RESULTS["Python processes"]="PASS"  # informational only

# 9. Summary table
echo ""
echo "======================================"
echo "  SUMMARY"
echo "======================================"
printf "%-45s %s\n" "Check" "Result"
printf "%-45s %s\n" "-----" "------"
for key in \
    "nvidia-smi (all 8 GPUs)" \
    "GPU4 utilization + VRAM" \
    "Disk space /tmp >= 20GB free" \
    "Isaac-GR00T venv exists" \
    "checkpoint-5000 present" \
    "dagger_run4 lerobot dataset present" \
    "Port 8002 status" \
    "Python processes"; do
    result="${RESULTS[$key]:-SKIP}"
    printf "%-45s %s\n" "$key" "$result"
done
echo "======================================"

if $ALL_PASS; then
    echo ""
    echo "All critical checks PASSED."

    if $START_SERVER; then
        echo ""
        echo "--- Starting GR00T Server (--start-server flag) ---"
        ssh -o StrictHostKeyChecking=no ubuntu@"${OCI_IP}" \
            "export CUDA_VISIBLE_DEVICES=4 && \
             cd /home/ubuntu && \
             nohup python groot_franka_server.py \
               --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 \
               --port 8002 \
               > /tmp/groot_server.log 2>&1 &
             echo \"Started GR00T server PID: \$!\"
             sleep 5
             for i in \$(seq 1 30); do
               if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
                 echo \"Server healthy after \${i} attempts\"
                 break
               fi
               echo \"Waiting for health... attempt \${i}/30\"
               sleep 5
             done"
        echo "GR00T server started. Connect via: ssh ubuntu@${OCI_IP} then curl localhost:8002/health"
    fi
else
    echo ""
    echo "One or more critical checks FAILED. Fix issues before running eval."
    exit 1
fi
