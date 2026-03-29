#!/usr/bin/env bash
# OCI Robot Cloud — Isaac Sim SDG with Domain Randomization
#
# Runs isaac_sim_sdg_dr.py inside the Isaac Sim 4.5.0 Docker container on OCI A100.
# Uses RTX RayTracedLighting for photorealistic training data.
#
# Usage:
#   bash src/simulation/run_isaac_sdg_dr.sh [--demos N] [--gpu ID]
#
# Defaults: 100 demos, GPU 4, output /tmp/isaac_dr_output
#
# Then convert to LeRobot v2 for GR00T:
#   python3 src/training/genesis_to_lerobot.py \
#       --input /tmp/isaac_dr_output \
#       --output /tmp/isaac_lerobot \
#       --task "pick up the red cube"

set -euo pipefail

NUM_DEMOS=${NUM_DEMOS:-100}
GPU_ID=${GPU_ID:-4}
OUTPUT_DIR=/tmp/isaac_dr_output
WORKSPACE=$HOME/roboticsai

echo "================================================================"
echo " OCI Robot Cloud — Isaac Sim SDG with Domain Randomization"
echo " GPU: A100 device=${GPU_ID} | Demos: ${NUM_DEMOS}"
echo " Renderer: RTX RayTracedLighting"
echo " Output: ${OUTPUT_DIR}"
echo "================================================================"

mkdir -p "${OUTPUT_DIR}"
mkdir -p ~/docker/isaac-sim/cache/{kit,ov,pip,glcache,computecache}
mkdir -p ~/docker/isaac-sim/logs ~/docker/isaac-sim/data

T_START=$(date +%s)

docker run --rm \
  --name isaac-sdg-dr \
  --entrypoint /isaac-sim/python.sh \
  --runtime=nvidia \
  --gpus "\"device=${GPU_ID}\"" \
  -e ACCEPT_EULA=Y \
  -e PRIVACY_CONSENT=Y \
  -v ~/docker/isaac-sim/cache/kit:/isaac-sim/kit/cache:rw \
  -v ~/docker/isaac-sim/cache/ov:/root/.cache/ov:rw \
  -v ~/docker/isaac-sim/cache/pip:/root/.cache/pip:rw \
  -v ~/docker/isaac-sim/cache/glcache:/root/.cache/nvidia/GLCache:rw \
  -v ~/docker/isaac-sim/cache/computecache:/root/.cache/computecache:rw \
  -v ~/docker/isaac-sim/logs:/root/.nvidia-omniverse/logs:rw \
  -v ~/docker/isaac-sim/data:/root/.local/share/ov/data:rw \
  -v "${WORKSPACE}:/workspace:ro" \
  -v "${OUTPUT_DIR}:/data:rw" \
  nvcr.io/nvidia/isaac-sim:4.5.0 \
  /workspace/src/simulation/isaac_sim_sdg_dr.py \
    --num-demos "${NUM_DEMOS}" \
    --steps-per-demo 100 \
    --output /data \
    --img-size 256

T_END=$(date +%s)
ELAPSED=$((T_END - T_START))

echo ""
echo "================================================================"
echo " Isaac Sim SDG Complete"
echo " Wall time: ${ELAPSED}s for ${NUM_DEMOS} demos"
echo " Output: ${OUTPUT_DIR}"
echo "================================================================"
echo ""
echo "Next: convert to LeRobot v2 format for GR00T fine-tuning:"
echo "  python3 ${WORKSPACE}/src/training/genesis_to_lerobot.py \\"
echo "      --input ${OUTPUT_DIR} \\"
echo "      --output /tmp/isaac_lerobot \\"
echo "      --task 'pick up the red cube'"
echo ""
echo "Or run the full pipeline (convert + finetune):"
echo "  bash ${WORKSPACE}/src/training/run_finetune.sh"
