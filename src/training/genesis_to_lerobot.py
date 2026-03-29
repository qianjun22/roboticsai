"""
OCI Robot Cloud — Genesis SDG → GR00T LeRobot v2 Converter

Converts Genesis synthetic data (npy arrays) to GR00T-flavored LeRobot v2 format
so it can be used directly with Isaac-GR00T fine-tuning.

Genesis output structure (per demo):
    demo_XXXX/
        rgb.npy          (T, H, W, 3) uint8
        joint_states.npy (T, 9) float32   [7 arm + 2 gripper]
        meta.json

LeRobot v2 output structure:
    <dataset>/
        meta/
            info.json
            episodes.jsonl
            tasks.jsonl
            modality.json
        data/chunk-000/
            episode_000000.parquet
            ...
        videos/chunk-000/
            observation.images.agentview/
                episode_000000.mp4
                ...

Usage:
    # First generate data with genesis_sdg.py, then:
    python3 src/training/genesis_to_lerobot.py \
        --input /tmp/genesis_sdg \
        --output /tmp/franka_lerobot \
        --task "pick the red cube from the table" \
        --fps 20

Requirements:
    pip install pandas pyarrow pillow numpy
    ffmpeg must be in PATH
"""

import argparse
import json
import os
import subprocess
import tempfile

import numpy as np
import pandas as pd
from PIL import Image

parser = argparse.ArgumentParser(description="Convert Genesis SDG output to GR00T LeRobot v2 format")
parser.add_argument("--input",  type=str, required=True, help="Genesis SDG output dir (contains demo_XXXX/)")
parser.add_argument("--output", type=str, required=True, help="Output dataset directory")
parser.add_argument("--task",   type=str, default="pick the red cube from the table")
parser.add_argument("--fps",    type=int, default=20, help="Video FPS (downsample from sim rate)")
args = parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def encode_frames_to_mp4(frames: np.ndarray, output_path: str, fps: int) -> None:
    """Encode (T, H, W, 3) uint8 RGB array to MP4 via ffmpeg."""
    T, H, W, C = frames.shape
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write frames as temp PNGs then encode — most portable approach
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, frame in enumerate(frames):
            Image.fromarray(frame).save(os.path.join(tmpdir, f"frame_{i:06d}.png"))

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmpdir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def build_modality_json() -> dict:
    """GR00T modality config for Franka Panda (7-DOF arm + 2 gripper)."""
    return {
        "state": {
            "arm": {"start": 0, "end": 7},
            "gripper": {"start": 7, "end": 9},
        },
        "action": {
            "arm": {"start": 0, "end": 7},
            "gripper": {"start": 7, "end": 9},
        },
        "video": {
            "agentview": {
                "original_key": "observation.images.agentview"
            }
        },
        "annotation": {
            "human.task_description": {
                "original_key": "task_index"
            }
        },
    }


def build_info_json(total_episodes: int, total_frames: int, fps: int, img_size: int) -> dict:
    return {
        "codebase_version": "v2.1",
        "robot_type": "franka_panda",
        "total_episodes": total_episodes,
        "total_frames": total_frames,
        "total_tasks": 1,
        "chunks_size": 1000,
        "fps": fps,
        "splits": {"train": f"0:{total_episodes}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "action": {
                "dtype": "float32",
                "names": [
                    "joint_0", "joint_1", "joint_2", "joint_3",
                    "joint_4", "joint_5", "joint_6",
                    "finger_left", "finger_right",
                ],
                "shape": [9],
            },
            "observation.state": {
                "dtype": "float32",
                "names": [
                    "joint_0", "joint_1", "joint_2", "joint_3",
                    "joint_4", "joint_5", "joint_6",
                    "finger_left", "finger_right",
                ],
                "shape": [9],
            },
            "observation.images.agentview": {
                "dtype": "video",
                "shape": [img_size, img_size, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.height": img_size,
                    "video.width": img_size,
                    "video.codec": "h264",
                    "video.pix_fmt": "yuv420p",
                    "video.is_depth_map": False,
                    "video.fps": fps,
                    "video.channels": 3,
                    "has_audio": False,
                },
            },
            "timestamp": {"dtype": "float32", "shape": [1], "names": None},
            "frame_index": {"dtype": "int64", "shape": [1], "names": None},
            "episode_index": {"dtype": "int64", "shape": [1], "names": None},
            "index": {"dtype": "int64", "shape": [1], "names": None},
            "task_index": {"dtype": "int64", "shape": [1], "names": None},
        },
        "total_chunks": 1,
        "total_videos": total_episodes,
    }


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def main():
    input_dir = args.input
    output_dir = args.output
    fps = args.fps

    # Discover demos
    demo_dirs = sorted([
        d for d in os.listdir(input_dir)
        if d.startswith("demo_") and os.path.isdir(os.path.join(input_dir, d))
    ])
    if not demo_dirs:
        raise RuntimeError(f"No demo_XXXX directories found in {input_dir}")

    print(f"[convert] Found {len(demo_dirs)} demos in {input_dir}")

    # Create output directories
    meta_dir = os.path.join(output_dir, "meta")
    data_dir = os.path.join(output_dir, "data", "chunk-000")
    video_dir = os.path.join(output_dir, "videos", "chunk-000", "observation.images.agentview")
    for d in [meta_dir, data_dir, video_dir]:
        os.makedirs(d, exist_ok=True)

    global_index = 0
    episodes_meta = []
    total_frames = 0
    img_size = None

    for ep_idx, demo_name in enumerate(demo_dirs):
        demo_path = os.path.join(input_dir, demo_name)

        rgb = np.load(os.path.join(demo_path, "rgb.npy"))           # (T, H, W, 3)
        joints = np.load(os.path.join(demo_path, "joint_states.npy"))  # (T, 9)

        T = len(joints)
        if img_size is None:
            img_size = rgb.shape[1]

        # Downsample frames if fps < sim_fps (sim_fps = 1/dt = 50)
        sim_fps = 50
        step = max(1, sim_fps // fps)
        indices = list(range(0, T, step))
        rgb_ds = rgb[indices]        # downsampled
        joints_ds = joints[indices]
        T_ds = len(joints_ds)

        # Encode video
        mp4_path = os.path.join(video_dir, f"episode_{ep_idx:06d}.mp4")
        encode_frames_to_mp4(rgb_ds, mp4_path, fps)

        # Build parquet: state = joints[t], action = joints[t+1] (behavior cloning targets)
        rows = []
        for t in range(T_ds):
            state = joints_ds[t].astype(np.float32)
            # Action: next joint state (last frame repeats)
            action = joints_ds[min(t + 1, T_ds - 1)].astype(np.float32)
            rows.append({
                "observation.state": state,
                "action": action,
                "timestamp": np.float32(t / fps),
                "frame_index": np.int64(t),
                "episode_index": np.int64(ep_idx),
                "index": np.int64(global_index + t),
                "task_index": np.int64(0),
            })

        df = pd.DataFrame(rows)
        parquet_path = os.path.join(data_dir, f"episode_{ep_idx:06d}.parquet")
        df.to_parquet(parquet_path, index=False)

        episodes_meta.append({
            "episode_index": ep_idx,
            "tasks": [args.task],
            "length": T_ds,
        })
        global_index += T_ds
        total_frames += T_ds

        print(f"  [convert] ep_{ep_idx:04d}: {T_ds} frames ({T} sim steps → {T_ds} @ {fps}fps) | {mp4_path}")

    # Write meta files
    with open(os.path.join(meta_dir, "info.json"), "w") as f:
        json.dump(build_info_json(len(demo_dirs), total_frames, fps, img_size), f, indent=2)

    with open(os.path.join(meta_dir, "modality.json"), "w") as f:
        json.dump(build_modality_json(), f, indent=2)

    with open(os.path.join(meta_dir, "tasks.jsonl"), "w") as f:
        f.write(json.dumps({"task_index": 0, "task": args.task}) + "\n")

    with open(os.path.join(meta_dir, "episodes.jsonl"), "w") as f:
        for ep in episodes_meta:
            f.write(json.dumps(ep) + "\n")

    print(f"\n[convert] Done! {len(demo_dirs)} episodes, {total_frames} total frames")
    print(f"[convert] Output: {output_dir}")
    print(f"\nNext step — fine-tune GR00T:")
    print(f"  cd ~/Isaac-GR00T && source .venv/bin/activate")
    print(f"  CUDA_VISIBLE_DEVICES=4 python gr00t/experiment/launch_finetune.py \\")
    print(f"    --base-model-path /home/ubuntu/models/GR00T-N1.6-3B \\")
    print(f"    --dataset-path {output_dir} \\")
    print(f"    --embodiment-tag NEW_EMBODIMENT \\")
    print(f"    --modality-config-path ~/roboticsai/src/training/franka_config.py \\")
    print(f"    --num-gpus 1 \\")
    print(f"    --output-dir /tmp/franka_finetune \\")
    print(f"    --max-steps 500 --save-steps 500 --global-batch-size 16")


if __name__ == "__main__":
    main()
