"""
DAgger episode → GR00T LeRobot v2 Converter

Unlike genesis_to_lerobot.py (which uses joint_states[t+1] as action target),
this converter uses ACTUAL robot states as observations and EXPERT IK actions
as action targets. This is the correct DAgger formulation:

  obs[t]    = actual robot joint state at step t (what the robot was doing)
  action[t] = expert IK target at step t (what we want it to do)

DAgger episode structure:
    episode_XXXXXX/
        frames.npy        (N, 256, 256, 3) uint8 — camera frames
        actions.npy       (N, 9)           float32 — expert IK targets
        states.npy        (N, 9)           float32 — actual robot states
        meta.json

Usage:
    python3 src/training/dagger_to_lerobot.py \
        --input /tmp/dagger_run3/dataset \
        --output /tmp/dagger_run3/lerobot \
        --fps 20
"""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


def encode_frames_to_mp4(frames: np.ndarray, output_path: str, fps: int) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, frame in enumerate(frames):
            Image.fromarray(frame).save(os.path.join(tmpdir, f"frame_{i:06d}.png"))
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmpdir, "frame_%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def build_modality_json() -> dict:
    return {
        "state": {"arm": {"start": 0, "end": 7}, "gripper": {"start": 7, "end": 9}},
        "action": {"arm": {"start": 0, "end": 7}, "gripper": {"start": 7, "end": 9}},
        "video": {"agentview": {"original_key": "observation.images.agentview"}},
        "annotation": {"human.task_description": {"original_key": "task_index"}},
    }


def build_info_json(total_episodes, total_frames, fps, img_size):
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
                "names": ["joint_0","joint_1","joint_2","joint_3","joint_4","joint_5","joint_6","finger_left","finger_right"],
                "shape": [9],
            },
            "observation.state": {
                "dtype": "float32",
                "names": ["joint_0","joint_1","joint_2","joint_3","joint_4","joint_5","joint_6","finger_left","finger_right"],
                "shape": [9],
            },
            "observation.images.agentview": {
                "dtype": "video", "shape": [img_size, img_size, 3],
                "names": ["height", "width", "channels"],
                "info": {"video.height": img_size, "video.width": img_size,
                         "video.codec": "h264", "video.pix_fmt": "yuv420p",
                         "video.is_depth_map": False, "video.fps": fps,
                         "video.channels": 3, "has_audio": False},
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


def main():
    parser = argparse.ArgumentParser(description="Convert DAgger episodes to GR00T LeRobot v2")
    parser.add_argument("--input", required=True, help="DAgger dataset dir (contains episode_XXXXXX/)")
    parser.add_argument("--output", required=True, help="Output LeRobot v2 directory")
    parser.add_argument("--task", default="pick the red cube from the table")
    parser.add_argument("--fps", type=int, default=20)
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    ep_dirs = sorted(input_dir.glob("episode_*"))
    if not ep_dirs:
        raise RuntimeError(f"No episode_XXXXXX directories found in {input_dir}")

    print(f"[dagger2lr] Found {len(ep_dirs)} episodes in {input_dir}")

    meta_dir = output_dir / "meta"
    data_dir = output_dir / "data" / "chunk-000"
    video_dir = output_dir / "videos" / "chunk-000" / "observation.images.agentview"
    for d in [meta_dir, data_dir, video_dir]:
        d.mkdir(parents=True, exist_ok=True)

    episodes_meta = []
    total_frames = 0
    global_index = 0
    img_size = None

    for ep_idx, ep_dir in enumerate(ep_dirs):
        frames = np.load(ep_dir / "frames.npy")   # (N, H, W, 3)
        actions = np.load(ep_dir / "actions.npy") # (N, 9) expert IK targets

        # Use actual robot states if available, else fall back to expert actions
        states_path = ep_dir / "states.npy"
        if states_path.exists():
            states = np.load(states_path)          # (N, 9) actual robot states
        else:
            states = actions.copy()                # legacy: use expert actions as obs

        N = len(frames)
        if img_size is None:
            img_size = frames.shape[1]

        # Encode video
        mp4_path = str(video_dir / f"episode_{ep_idx:06d}.mp4")
        encode_frames_to_mp4(frames, mp4_path, args.fps)

        # Build parquet: obs = actual state, action = expert IK target
        rows = []
        for t in range(N):
            rows.append({
                "observation.state": states[t].astype(np.float32),
                "action": actions[t].astype(np.float32),
                "timestamp": np.float32(t / args.fps),
                "frame_index": np.int64(t),
                "episode_index": np.int64(ep_idx),
                "index": np.int64(global_index + t),
                "task_index": np.int64(0),
            })

        df = pd.DataFrame(rows)
        parquet_path = str(data_dir / f"episode_{ep_idx:06d}.parquet")
        df.to_parquet(parquet_path, index=False)

        episodes_meta.append({"episode_index": ep_idx, "tasks": [args.task], "length": N})
        global_index += N
        total_frames += N

        state_src = "actual" if states_path.exists() else "expert(legacy)"
        print(f"  [dagger2lr] ep_{ep_idx:04d}: {N} frames | obs={state_src}")

    # Write meta files
    with open(meta_dir / "info.json", "w") as f:
        json.dump(build_info_json(len(ep_dirs), total_frames, args.fps, img_size), f, indent=2)
    with open(meta_dir / "modality.json", "w") as f:
        json.dump(build_modality_json(), f, indent=2)
    with open(meta_dir / "tasks.jsonl", "w") as f:
        f.write(json.dumps({"task_index": 0, "task": args.task}) + "\n")
    with open(meta_dir / "episodes.jsonl", "w") as f:
        for ep in episodes_meta:
            f.write(json.dumps(ep) + "\n")

    print(f"\n[dagger2lr] Done! {len(ep_dirs)} episodes, {total_frames} frames")
    print(f"[dagger2lr] Output: {output_dir}")


if __name__ == "__main__":
    main()
