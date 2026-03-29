"""
GR00T N1.6 Modality Configuration — Franka Panda (OCI Synthetic Data)

Defines the embodiment config for a 7-DOF Franka Panda arm with parallel gripper.
Used with EmbodimentTag.NEW_EMBODIMENT for fine-tuning on Genesis-generated data.

Register:
    python3 -c "import franka_config"  # registers on import

Usage in fine-tuning:
    CUDA_VISIBLE_DEVICES=4 python gr00t/experiment/launch_finetune.py \
        --base-model-path /home/ubuntu/models/GR00T-N1.6-3B \
        --dataset-path /tmp/franka_lerobot \
        --embodiment-tag NEW_EMBODIMENT \
        --modality-config-path ~/roboticsai/src/training/franka_config.py \
        --num-gpus 1 \
        --output-dir /tmp/franka_finetune \
        --max-steps 500 --save-steps 500 --global-batch-size 16

State / Action layout (9 floats, concatenated):
    [0:7]  arm joints (radians)
    [7:9]  gripper fingers (meters)
"""

from gr00t.configs.data.embodiment_configs import register_modality_config
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.data.types import (
    ActionConfig,
    ActionFormat,
    ActionRepresentation,
    ActionType,
    ModalityConfig,
)

franka_config = {
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["agentview"],
    ),
    "state": ModalityConfig(
        delta_indices=[0],
        modality_keys=["arm", "gripper"],
    ),
    "action": ModalityConfig(
        delta_indices=list(range(0, 16)),
        modality_keys=["arm", "gripper"],
        action_configs=[
            # arm joints — absolute joint positions
            ActionConfig(
                rep=ActionRepresentation.ABSOLUTE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
            # gripper — absolute finger positions
            ActionConfig(
                rep=ActionRepresentation.ABSOLUTE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
        ],
    ),
    "language": ModalityConfig(
        delta_indices=[0],
        modality_keys=["annotation.human.task_description"],
    ),
}

register_modality_config(franka_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
