"""
OCI Robot Cloud — Data utilities
==================================
Convert between common robot demo formats and the OCI Robot Cloud native format
(episode_N/rgb.npy + episode_N/joint_states.npy).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterator

import numpy as np


# ── Episode reading ────────────────────────────────────────────────────────────

def iter_episodes(data_path: str) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """
    Yield (rgb_frames, joint_states) for each episode in native format.

    rgb_frames:    (T, H, W, 3) uint8
    joint_states:  (T, D) float32  where D = 7 arm + 2 gripper = 9
    """
    root = Path(data_path)
    for ep_dir in sorted(root.glob("episode_*")):
        rgb = np.load(ep_dir / "rgb.npy")
        joints = np.load(ep_dir / "joint_states.npy")
        yield rgb, joints


def episode_count(data_path: str) -> int:
    """Return number of episodes in a dataset directory."""
    return sum(1 for _ in Path(data_path).glob("episode_*"))


# ── Format conversion ─────────────────────────────────────────────────────────

def from_hdf5(hdf5_path: str, output_dir: str, camera_key: str = "observations/images/agentview_rgb",
              joint_key: str = "observations/qpos") -> int:
    """
    Convert a LeRobot / Open-X HDF5 file to native episode format.

    Returns number of episodes written.
    """
    try:
        import h5py
    except ImportError:
        raise ImportError("pip install h5py to use from_hdf5()")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = 0

    with h5py.File(hdf5_path, "r") as f:
        demo_keys = sorted(k for k in f.keys() if k.startswith("demo_"))
        for i, key in enumerate(demo_keys):
            ep_dir = out / f"episode_{i:04d}"
            ep_dir.mkdir(exist_ok=True)
            rgb = np.array(f[key][camera_key], dtype=np.uint8)
            joints = np.array(f[key][joint_key], dtype=np.float32)
            np.save(ep_dir / "rgb.npy", rgb)
            np.save(ep_dir / "joint_states.npy", joints)
            written += 1

    print(f"[data_utils] Converted {written} episodes → {output_dir}")
    return written


def from_mp4_csv(video_path: str, csv_path: str, output_dir: str,
                 resize: tuple[int, int] = (256, 256)) -> int:
    """
    Convert MP4 video + CSV joint log to native episode format.

    CSV must have columns: t, j0, j1, j2, j3, j4, j5, j6, finger_left, finger_right
    Returns 1 (single episode).
    """
    try:
        import cv2
        import csv as csv_module
    except ImportError:
        raise ImportError("pip install opencv-python-headless to use from_mp4_csv()")

    out = Path(output_dir)
    ep_dir = out / "episode_0000"
    ep_dir.mkdir(parents=True, exist_ok=True)

    # Read video frames
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, resize)
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    rgb = np.array(frames, dtype=np.uint8)

    # Read joint states
    with open(csv_path) as f:
        reader = csv_module.DictReader(f)
        joints = np.array([[
            float(row["j0"]), float(row["j1"]), float(row["j2"]),
            float(row["j3"]), float(row["j4"]), float(row["j5"]),
            float(row.get("j6", 0.0)),
            float(row.get("finger_left", 0.04)),
            float(row.get("finger_right", 0.04)),
        ] for row in reader], dtype=np.float32)

    # Align lengths
    T = min(len(rgb), len(joints))
    np.save(ep_dir / "rgb.npy", rgb[:T])
    np.save(ep_dir / "joint_states.npy", joints[:T])

    print(f"[data_utils] Converted {T} frames → {ep_dir}")
    return 1


# ── Dataset inspection ────────────────────────────────────────────────────────

def inspect(data_path: str) -> dict:
    """
    Return summary statistics for a dataset.

    Returns dict with: num_episodes, total_frames, avg_episode_length,
    joint_min, joint_max, image_shape.
    """
    root = Path(data_path)
    episode_dirs = sorted(root.glob("episode_*"))
    if not episode_dirs:
        return {"error": f"No episodes found in {data_path}"}

    lengths = []
    all_joints = []
    img_shape = None

    for ep_dir in episode_dirs:
        rgb_file = ep_dir / "rgb.npy"
        joint_file = ep_dir / "joint_states.npy"
        if not rgb_file.exists() or not joint_file.exists():
            continue
        rgb = np.load(rgb_file, mmap_mode="r")
        joints = np.load(joint_file, mmap_mode="r")
        lengths.append(len(joints))
        all_joints.append(joints)
        if img_shape is None:
            img_shape = rgb.shape[1:]  # (H, W, C)

    all_joints_np = np.concatenate(all_joints, axis=0)
    return {
        "num_episodes": len(lengths),
        "total_frames": int(np.sum(lengths)),
        "avg_episode_length": round(float(np.mean(lengths)), 1),
        "min_episode_length": int(np.min(lengths)),
        "max_episode_length": int(np.max(lengths)),
        "joint_min": all_joints_np.min(axis=0).tolist(),
        "joint_max": all_joints_np.max(axis=0).tolist(),
        "image_shape": list(img_shape) if img_shape else None,
    }
