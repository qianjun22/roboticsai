"""
OCI Robot Cloud — Genesis Synthetic Data Generation

Lightweight alternative to Isaac Sim using Genesis (Apache 2.0).
Generates Franka Panda manipulation trajectories + RGB/depth images.
Runs directly via pip — no Docker, no NVIDIA account required.

Genesis advantages over Isaac Sim for prototyping:
  - pip install genesis-world (no container overhead)
  - Apache 2.0 license (fully commercial)
  - Fast iteration for testing data pipelines
  - Good for validating GR00T fine-tuning before Isaac Sim scale-up

Usage:
    source ~/genesis_venv/bin/activate
    CUDA_VISIBLE_DEVICES=4 python3 src/simulation/genesis_sdg.py \
        --num-demos 50 --steps-per-demo 50 --output /tmp/genesis_sdg

Requirements:
    pip install genesis-world pillow numpy
"""

import argparse
import json
import os
import time

import numpy as np
from PIL import Image

parser = argparse.ArgumentParser(description="Genesis synthetic data generation for robot manipulation")
parser.add_argument("--num-demos",      type=int, default=10,             help="Number of demos")
parser.add_argument("--steps-per-demo", type=int, default=50,             help="Steps per demo")
parser.add_argument("--output",         type=str, default="/tmp/genesis_sdg", help="Output dir")
parser.add_argument("--img-size",       type=int, default=256,            help="Camera resolution")
parser.add_argument("--seed",           type=int, default=42,             help="Random seed")
args = parser.parse_args()

import genesis as gs

gs.init(backend=gs.cuda, logging_level="warning")

os.makedirs(args.output, exist_ok=True)
print(f"[SDG] Genesis {gs.__version__} | output: {args.output}")


def build_scene() -> tuple:
    """Build a tabletop manipulation scene with Franka Panda."""
    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02),
    )

    # Ground
    scene.add_entity(gs.morphs.Plane())

    # Table
    table = scene.add_entity(
        gs.morphs.Box(size=(0.8, 0.6, 0.7), pos=(0.4, 0.0, 0.35), fixed=True),
    )

    # Target object (small cube on table)
    target = scene.add_entity(
        gs.morphs.Box(size=(0.05, 0.05, 0.05), pos=(0.4, 0.0, 0.725)),
    )

    # Franka Panda arm
    robot = scene.add_entity(
        gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"),
    )

    # Agentview camera (matches LIBERO convention — angled top-down)
    cam = scene.add_camera(
        res=(args.img_size, args.img_size),
        pos=(0.5, 0.0, 1.4),
        lookat=(0.4, 0.0, 0.7),
        fov=55,
    )

    scene.build()
    return scene, robot, target, cam


def randomize_target(target, rng: np.random.Generator) -> np.ndarray:
    """Randomize target cube position on table surface."""
    xy_offset = rng.uniform(-0.15, 0.15, size=2)
    new_pos = np.array([0.4 + xy_offset[0], xy_offset[1], 0.725])
    target.set_pos(new_pos)
    return new_pos


def collect_demo(scene, robot, target, cam, rng: np.random.Generator, demo_idx: int) -> dict:
    """Collect one demo: randomize scene, run random joint motions, capture images."""
    scene.reset()
    target_pos = randomize_target(target, rng)

    # Random joint trajectory (placeholder — replace with motion planning for real demos)
    q_home = np.array([0, -0.3, 0, -2.0, 0, 1.9, 0.785, 0.0, 0.0])
    frames_rgb = []
    frames_depth = []
    joint_states = []

    for step in range(args.steps_per_demo):
        # Apply small random perturbation to joints (demonstrates actuation)
        noise = rng.uniform(-0.02, 0.02, size=robot.n_dofs)
        q_target = q_home + noise * step * 0.1
        robot.set_dofs_position(q_target)

        scene.step()

        # Capture image
        rgb, depth, _, _ = cam.render(rgb=True, depth=True, segmentation=False, normal=False)

        frames_rgb.append(rgb)          # (H, W, 3) uint8
        frames_depth.append(depth)      # (H, W) float32

        # Record state
        q = robot.get_dofs_position().cpu().numpy()
        joint_states.append(q.tolist())

    return {
        "demo_idx": demo_idx,
        "target_init_pos": target_pos.tolist(),
        "frames_rgb": np.stack(frames_rgb),       # (T, H, W, 3)
        "frames_depth": np.stack(frames_depth),   # (T, H, W)
        "joint_states": np.array(joint_states),   # (T, n_dofs)
        "n_dofs": robot.n_dofs,
    }


def save_demo(demo: dict, output_dir: str) -> None:
    """Save demo: RGB frames as PNGs + states as npy."""
    demo_dir = os.path.join(output_dir, f"demo_{demo['demo_idx']:04d}")
    os.makedirs(demo_dir, exist_ok=True)

    # Save RGB frames
    np.save(os.path.join(demo_dir, "rgb.npy"), demo["frames_rgb"])
    np.save(os.path.join(demo_dir, "depth.npy"), demo["frames_depth"])
    np.save(os.path.join(demo_dir, "joint_states.npy"), demo["joint_states"])

    # Save metadata
    meta = {
        "demo_idx": demo["demo_idx"],
        "target_init_pos": demo["target_init_pos"],
        "n_steps": len(demo["frames_rgb"]),
        "n_dofs": demo["n_dofs"],
        "img_size": args.img_size,
    }
    with open(os.path.join(demo_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Save first frame as preview PNG
    Image.fromarray(demo["frames_rgb"][0]).save(os.path.join(demo_dir, "frame_000.png"))

    print(f"  [SDG] demo_{demo['demo_idx']:04d}: "
          f"rgb{demo['frames_rgb'].shape} | "
          f"joints{demo['joint_states'].shape} -> {demo_dir}")


def main():
    scene, robot, target, cam = build_scene()
    rng = np.random.default_rng(seed=args.seed)

    print(f"[SDG] Robot DOFs: {robot.n_dofs} | "
          f"Generating {args.num_demos} demos x {args.steps_per_demo} steps...")

    t_start = time.perf_counter()

    for i in range(args.num_demos):
        demo = collect_demo(scene, robot, target, cam, rng, demo_idx=i)
        save_demo(demo, args.output)

    elapsed = time.perf_counter() - t_start
    total_frames = args.num_demos * args.steps_per_demo
    print(f"\n[SDG] Done! {total_frames} frames in {elapsed:.1f}s "
          f"({total_frames / elapsed:.1f} fps)")
    print(f"[SDG] Output: {args.output}")


if __name__ == "__main__":
    main()
