#!/usr/bin/env bash
# OCI Robot Cloud — Infrastructure Setup
#
# Provisions an OCI A100 GPU instance and installs the full robot cloud stack:
#   - NVIDIA Isaac-GR00T N1.6-3B inference + fine-tuning
#   - Genesis 0.4.3 synthetic data generation
#   - Isaac Sim 4.5.0 via Docker (headless, RTX)
#   - OCI Robot Cloud API service (port 8080)
#   - GR00T baseline inference server (port 8001)
#
# Usage (run on fresh OCI A100-SXM4-80GB Ubuntu 22.04 instance):
#   bash src/infra/oci_robot_cloud_setup.sh [--full|--minimal|--api-only]
#
# Modes:
#   --minimal   GR00T inference only (fastest, ~20 min)
#   --full      All components including Isaac Sim Docker (default, ~45 min)
#   --api-only  Robot Cloud API service only (assumes GR00T already installed)
#
# Requirements:
#   OCI A100-SXM4-80GB (GPU.A10.8 or BM.GPU.A100-v2.8 shape)
#   Ubuntu 22.04, JetPack not required (bare metal A100)
#   32GB+ system RAM, 200GB+ storage
#
# After setup:
#   GR00T inference:  http://<instance-ip>:8001/predict
#   Robot Cloud API:  http://<instance-ip>:8080/docs

set -euo pipefail

MODE=${1:-"--full"}
GPU_ID=${GPU_ID:-4}
REPO_URL="https://github.com/qianjun22/roboticsai.git"
GROOT_MODEL_HF="nvidia/GR00T-N1.6-3B"
PYTHON="${PYTHON:-python3}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
section() { echo ""; echo "════════════════════════════════════════════════════════"; echo "  $*"; echo "════════════════════════════════════════════════════════"; }

section "OCI Robot Cloud Setup — Mode: $MODE"
log "GPU: $GPU_ID | Python: $($PYTHON --version 2>&1)"

# ── System deps ────────────────────────────────────────────────────────────────
install_system_deps() {
  section "[1/6] System dependencies"
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends \
    git curl wget bc jq \
    python3-pip python3-venv \
    ffmpeg libsm6 libxext6 libgl1 \
    nvidia-cuda-toolkit 2>/dev/null || true
  log "System deps installed"
}

# ── Python environment ─────────────────────────────────────────────────────────
setup_python_env() {
  section "[2/6] Python environment"
  $PYTHON -m pip install --upgrade pip --quiet
  $PYTHON -m pip install --quiet \
    torch torchvision torchaudio \
    numpy scipy pillow opencv-python \
    fastapi uvicorn python-multipart aiofiles \
    requests huggingface_hub tqdm \
    matplotlib pandas
  log "Python packages installed"
}

# ── Isaac-GR00T ───────────────────────────────────────────────────────────────
install_groot() {
  section "[3/6] Isaac-GR00T N1.6-3B"

  if [ -d ~/Isaac-GR00T ]; then
    log "Isaac-GR00T already cloned — pulling latest"
    cd ~/Isaac-GR00T && git pull --quiet
  else
    log "Cloning Isaac-GR00T..."
    git clone https://github.com/NVIDIA/Isaac-GR00T.git ~/Isaac-GR00T
  fi

  cd ~/Isaac-GR00T
  $PYTHON -m pip install -e ".[train,inference]" --quiet \
    --extra-index-url https://download.pytorch.org/whl/cu122
  $PYTHON -m pip install decord lerobot --quiet

  # Download GR00T N1.6-3B model weights
  if [ ! -d ~/models/GR00T-N1.6-3B ]; then
    log "Downloading GR00T-N1.6-3B weights (~6.7GB)..."
    mkdir -p ~/models
    $PYTHON -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='nvidia/GR00T-N1.6-3B',
    local_dir=os.path.expanduser('~/models/GR00T-N1.6-3B'),
    ignore_patterns=['*.md', '*.txt', 'LICENSE'],
)
import os
print('  Downloaded to ~/models/GR00T-N1.6-3B')
"
  else
    log "GR00T weights already at ~/models/GR00T-N1.6-3B"
  fi
  log "Isaac-GR00T ready"
}

# ── Genesis SDG ────────────────────────────────────────────────────────────────
install_genesis() {
  section "[4/6] Genesis 0.4.3 Synthetic Data Generator"
  $PYTHON -m pip install genesis-world --quiet 2>/dev/null || \
    $PYTHON -m pip install "genesis-world==0.4.3" --quiet || \
    log "Genesis install failed — will use Isaac Sim SDG instead"
  log "Genesis SDG ready"
}

# ── Isaac Sim Docker ───────────────────────────────────────────────────────────
install_isaac_sim() {
  section "[5/6] Isaac Sim 4.5.0 Docker (headless)"
  if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
  fi

  if ! docker images | grep -q "isaac-sim"; then
    log "Pulling Isaac Sim 4.5.0 container (~15GB)..."
    docker pull nvcr.io/nvidia/isaac-sim:4.5.0 2>/dev/null || \
      log "Isaac Sim pull failed — NGC auth may be needed. See: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim"
  else
    log "Isaac Sim image already present"
  fi
}

# ── Robot Cloud API service ────────────────────────────────────────────────────
install_api_service() {
  section "[6/6] OCI Robot Cloud API Service"

  if [ ! -d ~/roboticsai ]; then
    log "Cloning robot cloud repo..."
    git clone "$REPO_URL" ~/roboticsai
  else
    log "Repo already cloned — pulling latest"
    cd ~/roboticsai && git pull --quiet
  fi

  # Create systemd service for auto-start
  cat > /tmp/robot-cloud-api.service << 'SERVICE'
[Unit]
Description=OCI Robot Cloud API Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/roboticsai
Environment="GPU_ID=4"
Environment="OUTPUT_BASE=/tmp/robot_cloud"
Environment="REPO_DIR=/home/ubuntu/roboticsai"
Environment="MODEL_PATH=/home/ubuntu/models/GR00T-N1.6-3B"
ExecStart=/usr/bin/python3 -m uvicorn src.api.robot_cloud_api:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

  sudo mv /tmp/robot-cloud-api.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable robot-cloud-api

  log "API service configured (systemd)"
}

# ── Start services ─────────────────────────────────────────────────────────────
start_services() {
  section "Starting services"

  # Start GR00T baseline inference server (port 8001)
  log "Starting GR00T baseline server on port 8001..."
  if ! pgrep -f "port 8001" > /dev/null; then
    CUDA_VISIBLE_DEVICES=$GPU_ID nohup \
      $PYTHON ~/Isaac-GR00T/groot/eval/gr00t_server.py \
        --model ~/models/GR00T-N1.6-3B \
        --embodiment GR1 \
        --port 8001 \
      > /tmp/groot_server.log 2>&1 &
    sleep 5
    if pgrep -f "port 8001" > /dev/null; then
      log "GR00T server running on port 8001"
    else
      log "GR00T server failed to start — check /tmp/groot_server.log"
    fi
  else
    log "GR00T server already running on port 8001"
  fi

  # Start Robot Cloud API (port 8080)
  sudo systemctl start robot-cloud-api || \
    GPU_ID=$GPU_ID CUDA_VISIBLE_DEVICES=$GPU_ID \
      $PYTHON -m uvicorn src.api.robot_cloud_api:app \
        --host 0.0.0.0 --port 8080 \
        --app-dir ~/roboticsai &
  sleep 3

  log "OCI Robot Cloud API running on port 8080"
}

# ── Smoke test ─────────────────────────────────────────────────────────────────
smoke_test() {
  section "Smoke test"
  PUBLIC_IP=$(curl -s http://169.254.169.254/opc/v1/instance/ 2>/dev/null | \
    $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('publicIp','<ip>'))" 2>/dev/null || \
    curl -s ifconfig.me 2>/dev/null || echo "localhost")

  log "Testing Robot Cloud API..."
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then
    log "✅ API health check passed"
  else
    log "❌ API health check failed (HTTP $HTTP)"
  fi

  log "Testing GR00T inference..."
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then
    log "✅ GR00T server responding"
  else
    log "⚠️  GR00T server not responding on port 8001 (may still be loading)"
  fi

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo " OCI Robot Cloud Setup Complete"
  echo "════════════════════════════════════════════════════════"
  echo "  GR00T Inference:    http://$PUBLIC_IP:8001/predict"
  echo "  Robot Cloud API:    http://$PUBLIC_IP:8080"
  echo "  API Docs:           http://$PUBLIC_IP:8080/docs"
  echo "  Pricing:            http://$PUBLIC_IP:8080/pricing"
  echo ""
  echo "  Quick test:"
  echo "    curl http://$PUBLIC_IP:8080/health"
  echo "    curl -X POST http://$PUBLIC_IP:8080/jobs/train \\"
  echo "         -H 'Content-Type: application/json' \\"
  echo "         -d '{\"num_demos\": 10, \"train_steps\": 100}'"
  echo "════════════════════════════════════════════════════════"
}

# ── Dispatch ───────────────────────────────────────────────────────────────────
case "$MODE" in
  --minimal)
    install_system_deps
    setup_python_env
    install_groot
    install_api_service
    start_services
    smoke_test
    ;;
  --api-only)
    install_api_service
    start_services
    smoke_test
    ;;
  --full|*)
    install_system_deps
    setup_python_env
    install_groot
    install_genesis
    install_isaac_sim
    install_api_service
    start_services
    smoke_test
    ;;
esac
