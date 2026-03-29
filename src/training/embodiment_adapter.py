#!/usr/bin/env python3
"""
Embodiment Adapter for GR00T fine-tuning.

Converts robot-specific joint data from different embodiments to a unified
GR00T training format. Supports:
  - Franka Panda (7-DOF arm + 2 gripper)  [current]
  - UR5e (6-DOF arm + 2 gripper)
  - Kinova Gen3 (7-DOF arm + 2 gripper)
  - xArm7 (7-DOF arm + 2 gripper)

Usage:
    python3 embodiment_adapter.py \
        --robot ur5e \
        --input /tmp/ur5e_demos \
        --output /tmp/ur5e_lerobot \
        --show-mapping

    python3 embodiment_adapter.py --list-robots
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

# ── Embodiment registry ────────────────────────────────────────────────────────

EMBODIMENTS = {
    "franka": {
        "name": "Franka Panda",
        "arm_dof": 7,
        "gripper_dof": 2,
        "joint_names": [
            "panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
            "panda_joint5", "panda_joint6", "panda_joint7",
        ],
        "gripper_names": ["panda_finger_joint1", "panda_finger_joint2"],
        "arm_limits_rad": [
            (-2.897, 2.897), (-1.763, 1.763), (-2.897, 2.897), (-3.072, -0.069),
            (-2.897, 2.897), (-0.018, 3.752), (-2.897, 2.897),
        ],
        "gripper_limits_m": [(0.0, 0.04), (0.0, 0.04)],
        "home_q": [0.0, -0.3, 0.0, -2.0, 0.0, 1.8, 0.785],
        "home_gripper": [0.04, 0.04],
        "groot_embodiment_tag": "NEW_EMBODIMENT",
        "data_format": "joint_states",  # npy file format used in genesis_sdg_planned
    },
    "ur5e": {
        "name": "Universal Robots UR5e",
        "arm_dof": 6,
        "gripper_dof": 2,
        "joint_names": [
            "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
            "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
        ],
        "gripper_names": ["finger_joint_l", "finger_joint_r"],
        "arm_limits_rad": [
            (-6.28, 6.28), (-6.28, 6.28), (-3.14, 3.14),
            (-6.28, 6.28), (-6.28, 6.28), (-6.28, 6.28),
        ],
        "gripper_limits_m": [(0.0, 0.085), (0.0, 0.085)],
        "home_q": [0.0, -1.57, 1.57, -1.57, -1.57, 0.0],
        "home_gripper": [0.04, 0.04],
        "groot_embodiment_tag": "GR1",  # use GR1 tag for 6-DOF (closest match)
        "data_format": "joint_states",
        "adapter_note": "UR5e has 6 arm DOF — zero-pad to 7 for GR00T compatibility",
    },
    "kinova_gen3": {
        "name": "Kinova Gen3",
        "arm_dof": 7,
        "gripper_dof": 2,
        "joint_names": [
            "joint_1", "joint_2", "joint_3", "joint_4",
            "joint_5", "joint_6", "joint_7",
        ],
        "gripper_names": ["right_inner_finger_joint", "left_inner_finger_joint"],
        "arm_limits_rad": [
            (-3.14, 3.14), (-2.27, 2.27), (-3.14, 3.14), (-2.57, 2.57),
            (-3.14, 3.14), (-2.27, 2.27), (-3.14, 3.14),
        ],
        "gripper_limits_m": [(0.0, 0.03), (0.0, 0.03)],
        "home_q": [0.0, 0.26, 3.14, -2.27, 0.0, 0.96, 1.57],
        "home_gripper": [0.02, 0.02],
        "groot_embodiment_tag": "NEW_EMBODIMENT",
        "data_format": "joint_states",
    },
    "xarm7": {
        "name": "UFACTORY xArm 7",
        "arm_dof": 7,
        "gripper_dof": 2,
        "joint_names": [
            "joint1", "joint2", "joint3", "joint4",
            "joint5", "joint6", "joint7",
        ],
        "gripper_names": ["drive_joint", "right_outer_knuckle_joint"],
        "arm_limits_rad": [
            (-3.14, 3.14), (-2.60, 2.60), (-3.14, 3.14), (-0.19, 3.93),
            (-3.14, 3.14), (-1.69, 3.14), (-3.14, 3.14),
        ],
        "gripper_limits_m": [(0.0, 0.053), (0.0, 0.053)],
        "home_q": [0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        "home_gripper": [0.04, 0.04],
        "groot_embodiment_tag": "NEW_EMBODIMENT",
        "data_format": "joint_states",
    },
}


# ── Normalization utilities ───────────────────────────────────────────────────

def normalize_joints(joints: np.ndarray, limits: list) -> np.ndarray:
    """Normalize joints to [-1, 1] based on joint limits."""
    lo = np.array([l[0] for l in limits], dtype=np.float32)
    hi = np.array([l[1] for l in limits], dtype=np.float32)
    return 2.0 * (joints - lo) / (hi - lo + 1e-8) - 1.0


def denormalize_joints(joints_norm: np.ndarray, limits: list) -> np.ndarray:
    """Convert [-1, 1] normalized joints back to real values."""
    lo = np.array([l[0] for l in limits], dtype=np.float32)
    hi = np.array([l[1] for l in limits], dtype=np.float32)
    return 0.5 * (joints_norm + 1.0) * (hi - lo) + lo


def adapt_arm_to_franka_space(joints: np.ndarray, source_cfg: dict, target_dof: int = 7) -> np.ndarray:
    """
    Adapt arm joints from source embodiment to Franka-compatible space.
    - If source has fewer DOF than target, zero-pad the last joints.
    - If source has same DOF, apply per-joint normalization and rescale.
    """
    T = joints.shape[0]
    source_dof = source_cfg["arm_dof"]

    if source_dof == target_dof:
        # Normalize to [-1, 1] then denormalize into Franka space
        franka_cfg = EMBODIMENTS["franka"]
        normalized = normalize_joints(joints, source_cfg["arm_limits_rad"])
        adapted = denormalize_joints(normalized, franka_cfg["arm_limits_rad"])
        return adapted.astype(np.float32)
    elif source_dof < target_dof:
        # Pad with home position joints for missing DOFs
        franka_home = np.array(EMBODIMENTS["franka"]["home_q"], dtype=np.float32)
        normalized = normalize_joints(joints, source_cfg["arm_limits_rad"])
        # Denormalize into Franka space for the available joints
        franka_cfg = EMBODIMENTS["franka"]
        adapted_partial = denormalize_joints(
            normalized, franka_cfg["arm_limits_rad"][:source_dof]
        )
        # Pad remaining joints with Franka home values
        adapted = np.tile(franka_home, (T, 1))
        adapted[:, :source_dof] = adapted_partial
        return adapted.astype(np.float32)
    else:
        raise ValueError(f"Source DOF {source_dof} > target {target_dof} — cannot reduce DOF")


def adapt_gripper_to_franka_space(gripper: np.ndarray, source_cfg: dict) -> np.ndarray:
    """Adapt gripper state to Franka finger space [0, 0.04]."""
    franka_grip_limits = EMBODIMENTS["franka"]["gripper_limits_m"]
    source_grip_limits = source_cfg["gripper_limits_m"]

    normalized = normalize_joints(gripper, source_grip_limits)
    adapted    = denormalize_joints(normalized, franka_grip_limits)
    return adapted.astype(np.float32)


# ── Episode conversion ────────────────────────────────────────────────────────

def convert_episode(episode_dir: Path, output_dir: Path, source_cfg: dict) -> Optional[dict]:
    """
    Convert a single episode from source embodiment format to Franka-compatible
    LeRobot v2 format for GR00T fine-tuning.
    """
    # Load source data
    joint_file = episode_dir / "joint_states.npy"
    rgb_file   = episode_dir / "rgb.npy"
    meta_file  = episode_dir / "metadata.json"

    if not joint_file.exists() or not rgb_file.exists():
        return None

    raw_joints = np.load(joint_file)   # (T, arm_dof + gripper_dof)
    rgb        = np.load(rgb_file)     # (T, H, W, 3)
    meta       = json.loads(meta_file.read_text()) if meta_file.exists() else {}

    T = raw_joints.shape[0]
    arm_dof  = source_cfg["arm_dof"]

    raw_arm     = raw_joints[:, :arm_dof]
    raw_gripper = raw_joints[:, arm_dof:arm_dof + source_cfg["gripper_dof"]]

    # Adapt to Franka-compatible space
    adapted_arm     = adapt_arm_to_franka_space(raw_arm, source_cfg)
    adapted_gripper = adapt_gripper_to_franka_space(raw_gripper, source_cfg)

    # Save adapted data
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "rgb.npy",          rgb)
    np.save(output_dir / "arm_states.npy",   adapted_arm)
    np.save(output_dir / "gripper_states.npy", adapted_gripper)
    np.save(output_dir / "joint_states.npy",
            np.concatenate([adapted_arm, adapted_gripper], axis=-1))

    # Write conversion metadata
    adapted_meta = {
        **meta,
        "source_embodiment": source_cfg["name"],
        "target_embodiment": "Franka Panda",
        "original_arm_dof": arm_dof,
        "adapted_arm_dof": 7,
        "adaptation": "normalize→rescale" if arm_dof == 7 else "zero_pad",
        "groot_embodiment_tag": source_cfg["groot_embodiment_tag"],
    }
    (output_dir / "metadata.json").write_text(json.dumps(adapted_meta, indent=2))

    return {"T": T, "arm_dof": arm_dof, "adaptation": adapted_meta["adaptation"]}


# ── Dataset conversion ────────────────────────────────────────────────────────

def convert_dataset(input_dir: Path, output_dir: Path, robot: str) -> dict:
    """Convert all episodes in input_dir from source embodiment to Franka space."""
    source_cfg = EMBODIMENTS[robot]
    output_dir.mkdir(parents=True, exist_ok=True)

    episode_dirs = sorted(d for d in input_dir.iterdir()
                          if d.is_dir() and d.name.startswith("episode_"))

    if not episode_dirs:
        print(f"[adapter] No episode_XXXXXX dirs found in {input_dir}")
        return {}

    print(f"[adapter] Converting {len(episode_dirs)} episodes from {source_cfg['name']} → Franka space")

    stats = {"converted": 0, "skipped": 0, "total": len(episode_dirs)}
    for ep_dir in episode_dirs:
        out_ep_dir = output_dir / ep_dir.name
        result = convert_episode(ep_dir, out_ep_dir, source_cfg)
        if result:
            stats["converted"] += 1
        else:
            stats["skipped"] += 1
        if stats["converted"] % 20 == 0 and stats["converted"] > 0:
            print(f"[adapter]   {stats['converted']}/{len(episode_dirs)} converted...")

    # Write dataset manifest
    manifest = {
        "source_embodiment": source_cfg["name"],
        "source_robot_id": robot,
        "target_embodiment": "Franka Panda",
        "episodes_converted": stats["converted"],
        "episodes_skipped": stats["skipped"],
        "groot_embodiment_tag": source_cfg["groot_embodiment_tag"],
        "notes": source_cfg.get("adapter_note", ""),
    }
    (output_dir / "adapter_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"[adapter] Done: {stats['converted']} episodes converted")
    print(f"[adapter] Output → {output_dir}")
    return stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Embodiment adapter for GR00T fine-tuning")
    parser.add_argument("--robot", choices=list(EMBODIMENTS.keys()),
                        help="Source robot embodiment")
    parser.add_argument("--input", help="Input directory with episode_XXXXXX subdirs")
    parser.add_argument("--output", help="Output directory for adapted dataset")
    parser.add_argument("--list-robots", action="store_true",
                        help="List supported embodiments and exit")
    parser.add_argument("--show-mapping", action="store_true",
                        help="Show joint mapping details for --robot and exit")
    args = parser.parse_args()

    if args.list_robots:
        print("\nSupported embodiments for GR00T fine-tuning via OCI Robot Cloud:")
        print(f"{'ID':<16} {'Name':<30} {'Arm DOF':<10} {'GR00T Tag'}")
        print("-" * 72)
        for rid, cfg in EMBODIMENTS.items():
            print(f"{rid:<16} {cfg['name']:<30} {cfg['arm_dof']:<10} {cfg['groot_embodiment_tag']}")
        print()
        return

    if args.show_mapping and args.robot:
        cfg = EMBODIMENTS[args.robot]
        franka = EMBODIMENTS["franka"]
        print(f"\nJoint mapping: {cfg['name']} → Franka Panda")
        print(f"{'Source joint':<30} {'Limits (rad)':<25} → {'Franka joint':<30} {'Limits (rad)'}")
        print("-" * 105)
        for i in range(min(cfg["arm_dof"], 7)):
            src_name  = cfg["joint_names"][i]
            src_lim   = cfg["arm_limits_rad"][i]
            tgt_name  = franka["joint_names"][i] if i < 7 else "(padded)"
            tgt_lim   = franka["arm_limits_rad"][i]
            print(f"  {src_name:<28} {str(src_lim):<25} → {tgt_name:<28} {str(tgt_lim)}")
        if cfg["arm_dof"] < 7:
            for i in range(cfg["arm_dof"], 7):
                print(f"  (none — padded)              {'':25} → {franka['joint_names'][i]:<28} HOME={franka['home_q'][i]:.3f}")
        if cfg.get("adapter_note"):
            print(f"\n  NOTE: {cfg['adapter_note']}")
        print()
        return

    if not args.robot or not args.input or not args.output:
        parser.print_help()
        print("\nExamples:")
        print("  python3 embodiment_adapter.py --list-robots")
        print("  python3 embodiment_adapter.py --robot ur5e --show-mapping")
        print("  python3 embodiment_adapter.py --robot ur5e --input /tmp/ur5e_demos --output /tmp/ur5e_adapted")
        return

    convert_dataset(Path(args.input), Path(args.output), args.robot)
    print(f"\nNext step (fine-tune on adapted data):")
    cfg = EMBODIMENTS[args.robot]
    print(f"  CUDA_VISIBLE_DEVICES=4 python3 launch_finetune.py \\")
    print(f"    --dataset {args.output} \\")
    print(f"    --embodiment {cfg['groot_embodiment_tag']} \\")
    print(f"    --max-steps 2000")


if __name__ == "__main__":
    main()
