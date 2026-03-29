#!/bin/bash
# sync_to_oci.sh — Push local roboticsai changes to OCI A100 for testing
# Usage: bash src/infra/sync_to_oci.sh [OCI_IP]

OCI_IP=${1:-"138.1.153.110"}
LOCAL_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_DIR="/home/ubuntu/roboticsai"

echo "[sync] Local: $LOCAL_DIR → OCI: ubuntu@${OCI_IP}:${REMOTE_DIR}"
rsync -avz --delete \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".github" \
    --exclude "*.pptx" \
    "$LOCAL_DIR/" \
    "ubuntu@${OCI_IP}:${REMOTE_DIR}/"
echo "[sync] Done"
