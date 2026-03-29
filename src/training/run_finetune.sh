#!/usr/bin/env bash
# OCI Robot Cloud — GR00T Fine-tuning Pipeline for Franka Panda
#
# Full pipeline: Genesis SDG → LeRobot format → GR00T fine-tune → eval
#
# Usage:
#   bash src/training/run_finetune.sh [--num-demos N] [--steps M] [--gpu G]
#
# Defaults: 100 demos, 500 training steps, GPU 4

set -euo pipefail

NUM_DEMOS=${NUM_DEMOS:-100}
STEPS_PER_DEMO=${STEPS_PER_DEMO:-100}
TRAIN_STEPS=${TRAIN_STEPS:-500}
GPU=${GPU:-4}

SDG_DIR=/tmp/genesis_sdg
DATASET_DIR=/tmp/franka_lerobot
FINETUNE_DIR=/tmp/franka_finetune
MODEL_PATH=/home/ubuntu/models/GR00T-N1.6-3B
ROBOTICSAI_DIR=~/roboticsai

echo "================================================================"
echo " OCI Robot Cloud — GR00T Fine-tuning Pipeline"
echo " GPU: $GPU | Demos: $NUM_DEMOS | Train steps: $TRAIN_STEPS"
echo "================================================================"

# --- Step 1: Generate synthetic data with Genesis ---
echo ""
echo "[1/4] Generating synthetic data with Genesis..."
source ~/genesis_venv/bin/activate
CUDA_VISIBLE_DEVICES=$GPU python3 $ROBOTICSAI_DIR/src/simulation/genesis_sdg.py \
    --num-demos "$NUM_DEMOS" \
    --steps-per-demo "$STEPS_PER_DEMO" \
    --output "$SDG_DIR" \
    --img-size 256
deactivate

# --- Step 2: Convert to LeRobot v2 format ---
echo ""
echo "[2/4] Converting Genesis output to GR00T LeRobot v2 format..."
# Use Isaac-GR00T venv (has pandas + pyarrow)
source ~/Isaac-GR00T/.venv/bin/activate
python3 $ROBOTICSAI_DIR/src/training/genesis_to_lerobot.py \
    --input "$SDG_DIR" \
    --output "$DATASET_DIR" \
    --task "pick the red cube from the table" \
    --fps 20

# --- Step 3: Fine-tune GR00T on OCI ---
echo ""
echo "[3/4] Fine-tuning GR00T N1.6 on OCI A100 GPU $GPU..."
cd ~/Isaac-GR00T
CUDA_VISIBLE_DEVICES=$GPU python gr00t/experiment/launch_finetune.py \
    --base-model-path "$MODEL_PATH" \
    --dataset-path "$DATASET_DIR" \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path "$ROBOTICSAI_DIR/src/training/franka_config.py" \
    --num-gpus 1 \
    --output-dir "$FINETUNE_DIR" \
    --save-total-limit 3 \
    --save-steps "$TRAIN_STEPS" \
    --max-steps "$TRAIN_STEPS" \
    --global-batch-size 16 \
    --dataloader-num-workers 4

# --- Step 4: Open-loop evaluation ---
echo ""
echo "[4/4] Running open-loop evaluation..."
CHECKPOINT=$(ls -d $FINETUNE_DIR/checkpoint-* | sort -V | tail -1)
echo "Evaluating checkpoint: $CHECKPOINT"
python gr00t/eval/open_loop_eval.py \
    --dataset-path "$DATASET_DIR" \
    --embodiment-tag NEW_EMBODIMENT \
    --model-path "$CHECKPOINT" \
    --traj-ids 0 1 2 \
    --action-horizon 16 \
    --steps 100 \
    --modality-keys arm gripper

echo ""
echo "================================================================"
echo " Fine-tuning complete!"
echo " Checkpoint: $CHECKPOINT"
echo " Dataset:    $DATASET_DIR"
echo "================================================================"
