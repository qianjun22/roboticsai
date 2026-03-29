#!/bin/bash
# aiworld_demo_setup.sh
# Pre-flight setup for AI World 2026 live demo (September 2026, Las Vegas).
# Runs on OCI A100 node. Verifies all services, pre-warms GPU, and
# generates a pre-flight checklist HTML report.
#
# Usage:
#   bash src/infra/aiworld_demo_setup.sh [--check-only] [--start-all]
#
# Outputs:
#   /tmp/aiworld_preflight.html  — visual checklist report
#   /tmp/aiworld_preflight.json  — machine-readable pass/fail

set -euo pipefail

ROBOTICS_DIR="${ROBOTICS_DIR:-$HOME/roboticsai}"
GROOT_PYTHON="${GROOT_PYTHON:-/home/ubuntu/Isaac-GR00T/.venv/bin/python3}"
CHECKPOINT="${CHECKPOINT:-/tmp/finetune_1000_5k/checkpoint-5000}"
CHECK_ONLY="${CHECK_ONLY:-false}"
START_ALL="${START_ALL:-false}"
REPORT="/tmp/aiworld_preflight.html"
REPORT_JSON="/tmp/aiworld_preflight.json"

declare -A RESULTS
PASS=0
FAIL=0

log() { echo "[preflight] $1"; }
pass() { RESULTS["$1"]="PASS"; ((PASS++)); log "✓ $1"; }
fail() { RESULTS["$1"]="FAIL: ${2:-}"; ((FAIL++)); log "✗ $1: ${2:-}"; }
check() { # check <name> <command>
  local name="$1"; shift
  if "$@" > /dev/null 2>&1; then pass "$name"; else fail "$name" "exit code $?"; fi
}

# ── System checks ─────────────────────────────────────────────────────────────

log "=== AI World 2026 Pre-flight Check ==="
log "Date: $(date)"
log "Host: $(hostname)"

# GPU
if nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | grep -q A100; then
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
  GPU_MEM=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader | head -1 | tr -d ' ')
  pass "NVIDIA A100 GPU present ($GPU_MEM free)"
else
  fail "NVIDIA A100 GPU" "nvidia-smi not found or not A100"
fi

# Disk space
FREE_GB=$(df -BG /tmp | awk 'NR==2{print $4}' | tr -d G)
if [ "${FREE_GB:-0}" -gt 50 ]; then
  pass "Disk space (/tmp: ${FREE_GB}GB free)"
else
  fail "Disk space" "Only ${FREE_GB:-?}GB free in /tmp (need 50+)"
fi

# Python env
check "GR00T venv" test -f "$GROOT_PYTHON"

# Checkpoint
check "1000-demo checkpoint" test -d "$CHECKPOINT"

# Genesis
if $GROOT_PYTHON -c "import genesis" 2>/dev/null; then
  GENESIS_VER=$($GROOT_PYTHON -c "import genesis; print(genesis.__version__)" 2>/dev/null || echo "?")
  pass "Genesis installed (${GENESIS_VER})"
else
  fail "Genesis" "import genesis failed"
fi

# ── Service checks ────────────────────────────────────────────────────────────

check_port() {
  local name="$1" port="$2"
  if curl -sf "http://localhost:${port}/health" > /dev/null 2>&1; then
    pass "$name (port $port)"
  else
    fail "$name (port $port)" "health check failed"
  fi
}

check_port "GR00T server (1000-demo)" 8002
check_port "Training monitor" 8004
check_port "Cost calculator" 8005
check_port "Design partner portal" 8006

# ── Start services if requested ───────────────────────────────────────────────

if [ "$START_ALL" = "true" ] && [ "$CHECK_ONLY" != "true" ]; then
  log "Starting services..."

  # GR00T server
  if ! curl -sf http://localhost:8002/health > /dev/null 2>&1; then
    log "Starting GR00T server..."
    pkill -f groot_franka_server.py 2>/dev/null; sleep 3
    export CUDA_VISIBLE_DEVICES=4
    nohup $GROOT_PYTHON $ROBOTICS_DIR/src/inference/groot_franka_server.py \
      --checkpoint "$CHECKPOINT" --port 8002 \
      >> /tmp/server_aiworld.log 2>&1 &
    log "Waiting for server..."
    for i in $(seq 1 40); do
      curl -sf http://localhost:8002/health > /dev/null 2>&1 && break
      sleep 5
    done
    check_port "GR00T server (started)" 8002
  fi

  # API services
  for svc in training_monitor cost_calculator design_partner_portal; do
    PY="$ROBOTICS_DIR/src/api/${svc}.py"
    if [ -f "$PY" ]; then
      nohup python3 "$PY" >> "/tmp/${svc}.log" 2>&1 &
      sleep 2
    fi
  done
fi

# ── Smoke test: one inference call ────────────────────────────────────────────

if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
  LATENCY=$(curl -o /dev/null -s -w "%{time_total}" \
    -X POST http://localhost:8002/act \
    -H "Content-Type: application/json" \
    -d '{"state":[[0,0,0,0,0,0,0,0,0]],"image_primary":null,"image_wrist":null}' 2>/dev/null || echo "0")
  LATENCY_MS=$(echo "$LATENCY * 1000" | bc 2>/dev/null || echo "?")
  if [ "${LATENCY:-0}" != "0" ]; then
    pass "Inference latency (${LATENCY_MS}ms)"
  else
    fail "Inference latency" "POST /act failed"
  fi
fi

# ── Network ───────────────────────────────────────────────────────────────────

if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
  pass "Internet connectivity"
else
  fail "Internet" "no route to 8.8.8.8"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
log ""
log "=== RESULTS: $PASS/$TOTAL passed ==="

# JSON output
python3 - <<PYEOF
import json, datetime
results = {}
$(for k in "${!RESULTS[@]}"; do echo "results[\"$k\"] = \"${RESULTS[$k]}\""; done)
output = {
    "timestamp": datetime.datetime.now().isoformat(),
    "passed": $PASS,
    "failed": $FAIL,
    "total": $TOTAL,
    "ready": $FAIL == 0,
    "results": results,
}
with open("$REPORT_JSON", "w") as f:
    json.dump(output, f, indent=2)
print(f"[preflight] JSON: $REPORT_JSON")
PYEOF

# HTML report
python3 - <<PYEOF
import json, datetime

with open("$REPORT_JSON") as f:
    data = json.load(f)

rows = ""
for name, result in data["results"].items():
    passed = result == "PASS"
    color = "#10b981" if passed else "#ef4444"
    sym = "✓" if passed else "✗"
    detail = "" if passed else f" — {result.replace('FAIL: ', '')}"
    rows += f"<tr><td>{name}</td><td style='color:{color};font-weight:bold'>{sym} {result}{detail}</td></tr>"

overall_color = "#10b981" if data["ready"] else "#ef4444"
overall_label = "DEMO READY" if data["ready"] else f"NOT READY ({data['failed']} issues)"

html = f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>AI World 2026 Pre-flight</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} .status{{font-size:2em;font-weight:bold;color:{overall_color};padding:12px 20px;
border:2px solid {overall_color};border-radius:8px;display:inline-block;margin:16px 0}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th{{background:#C74634;color:white;padding:8px 12px;text-align:left}}
td{{padding:7px 12px;border-bottom:1px solid #1e293b}}
tr:nth-child(even) td{{background:#172033}}
</style></head><body>
<h1>AI World 2026 — Demo Pre-flight</h1>
<p style="color:#64748b">Generated: {data['timestamp'][:16]}</p>
<div class="status">{overall_label}</div>
<p style="color:#94a3b8">{data['passed']}/{data['total']} checks passed</p>
<table><tr><th>Check</th><th>Result</th></tr>{rows}</table>
<p style="color:#475569;font-size:.8em;margin-top:28px">
  OCI Robot Cloud · AI World September 2026 · Run: bash src/infra/aiworld_demo_setup.sh --start-all
</p>
</body></html>"""

with open("$REPORT", "w") as f:
    f.write(html)
print(f"[preflight] HTML report: $REPORT")
PYEOF

if [ "$FAIL" -gt 0 ]; then
  log "⚠ $FAIL checks FAILED — resolve before demo!"
  exit 1
else
  log "✓ All checks passed — ready for AI World demo!"
  exit 0
fi
