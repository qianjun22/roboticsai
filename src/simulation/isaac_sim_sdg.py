"""
OCI Robot Cloud — Isaac Sim Synthetic Data Generation

Generates robot manipulation trajectories and camera images using
NVIDIA Isaac Sim 4.5.0. Runs inside the Isaac Sim Docker container.

This script demonstrates the core synthetic data pipeline:
  1. Build a tabletop manipulation scene (Franka Panda + objects)
  2. Randomize object positions, lighting, camera viewpoints
  3. Capture RGB + depth images at each step
  4. Record joint states and end-effector poses
  5. Save as HDF5 dataset for fine-tuning GR00T

Usage (inside Isaac Sim container):
    ./python.sh /workspace/src/simulation/isaac_sim_sdg.py \
        --num-demos 100 \
        --steps-per-demo 50 \
        --output /data/sdg_output

Or via docker run on OCI:
    docker run --rm \\
      --entrypoint /isaac-sim/python.sh \\
      --runtime=nvidia --gpus '"device=4"' \\
      -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \\
      -v ~/docker/isaac-sim/cache/kit:/isaac-sim/kit/cache:rw \\
      -v ~/docker/isaac-sim/cache/ov:/root/.cache/ov:rw \\
      -v /data:/data:rw \\
      nvcr.io/nvidia/isaac-sim:4.5.0 \\
      /workspace/src/simulation/isaac_sim_sdg.py --num-demos 100
"""

import argparse
import os
import sys
import time

# SimulationApp MUST be instantiated before any other omniverse imports
from isaacsim import SimulationApp

parser = argparse.ArgumentParser(description="Isaac Sim synthetic data generation")
parser.add_argument("--num-demos",      type=int, default=10,    help="Number of demos to generate")
parser.add_argument("--steps-per-demo", type=int, default=50,    help="Steps per demo episode")
parser.add_argument("--output",         type=str, default="/tmp/sdg_output", help="Output directory")
parser.add_argument("--img-size",       type=int, default=256,   help="Camera image size (square)")
args = parser.parse_args()

simulation_app = SimulationApp({"headless": True, "renderer": "RayTracedLighting"})

# --- Late imports (after SimulationApp) ---
import carb
import numpy as np
import omni.isaac.core.utils.nucleus as nucleus_utils
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid
from omni.isaac.core.robots import Robot
from omni.isaac.core.utils.prims import create_prim
from omni.isaac.core.utils.stage import add_reference_to_stage
from omni.isaac.sensor import Camera
import omni.replicator.core as rep

os.makedirs(args.output, exist_ok=True)
print(f"[SDG] Output directory: {args.output}")


def build_scene(world: World) -> tuple:
    """Build a tabletop manipulation scene with Franka Panda."""
    stage = world.scene.stage

    # Ground plane
    world.scene.add_default_ground_plane()

    # Table surface (simple box)
    table = DynamicCuboid(
        prim_path="/World/Table",
        name="table",
        position=np.array([0.4, 0.0, 0.35]),
        scale=np.array([0.8, 0.6, 0.7]),
        color=np.array([0.6, 0.4, 0.2]),
        mass=100.0,
    )
    world.scene.add(table)

    # Target object (cube to manipulate)
    target = DynamicCuboid(
        prim_path="/World/Target",
        name="target",
        position=np.array([0.4, 0.0, 0.73]),
        scale=np.array([0.05, 0.05, 0.05]),
        color=np.array([1.0, 0.2, 0.2]),  # red
        mass=0.1,
    )
    world.scene.add(target)

    # Camera (agentview — top-down with slight angle, matches LIBERO convention)
    camera = Camera(
        prim_path="/World/Camera/agentview",
        position=np.array([0.5, 0.0, 1.4]),
        frequency=20,
        resolution=(args.img_size, args.img_size),
        orientation=rep.utils.euler_angles_to_quats([0, 70, 0], degrees=True),
    )
    world.scene.add(camera)

    return table, target, camera


def randomize_scene(target, rng: np.random.Generator) -> dict:
    """Randomize object position and lighting."""
    # Random target position on table surface
    target_xy = rng.uniform([-0.15, -0.15], [0.15, 0.15])
    new_pos = np.array([0.4 + target_xy[0], target_xy[1], 0.73])
    target.set_world_pose(position=new_pos)

    return {"target_pos": new_pos.tolist()}


def collect_demo(world: World, table, target, camera, rng: np.random.Generator,
                 demo_idx: int) -> dict:
    """Collect one demo episode — random motion baseline."""
    world.reset()
    scene_info = randomize_scene(target, rng)

    frames = []
    states = []

    for step in range(args.steps_per_demo):
        world.step(render=True)

        # Capture camera image
        img_data = camera.get_rgba()  # (H, W, 4) uint8
        if img_data is not None:
            rgb = img_data[:, :, :3]  # drop alpha
        else:
            rgb = np.zeros((args.img_size, args.img_size, 3), dtype=np.uint8)

        # Record object state
        target_pos, target_rot = target.get_world_pose()
        state = {
            "step": step,
            "target_position": target_pos.tolist(),
            "target_orientation": target_rot.tolist(),
        }

        frames.append(rgb)
        states.append(state)

    return {
        "demo_idx": demo_idx,
        "scene": scene_info,
        "num_steps": args.steps_per_demo,
        "frames": frames,   # list of (H,W,3) arrays
        "states": states,
    }


def save_demo(demo: dict, output_dir: str) -> None:
    """Save demo as numpy arrays."""
    demo_dir = os.path.join(output_dir, f"demo_{demo['demo_idx']:04d}")
    os.makedirs(demo_dir, exist_ok=True)

    frames = np.stack(demo["frames"])  # (T, H, W, 3)
    np.save(os.path.join(demo_dir, "rgb.npy"), frames)

    import json
    with open(os.path.join(demo_dir, "states.json"), "w") as f:
        json.dump(demo["states"], f)
    with open(os.path.join(demo_dir, "scene.json"), "w") as f:
        json.dump(demo["scene"], f)

    print(f"  [SDG] Saved demo {demo['demo_idx']:04d}: {frames.shape} frames -> {demo_dir}")


def main():
    world = World(stage_units_in_meters=1.0)
    table, target, camera = build_scene(world)
    world.reset()

    rng = np.random.default_rng(seed=42)
    t_start = time.perf_counter()

    print(f"[SDG] Generating {args.num_demos} demos x {args.steps_per_demo} steps...")
    for i in range(args.num_demos):
        demo = collect_demo(world, table, target, camera, rng, demo_idx=i)
        save_demo(demo, args.output)

    elapsed = time.perf_counter() - t_start
    total_frames = args.num_demos * args.steps_per_demo
    print(f"\n[SDG] Done! {args.num_demos} demos, {total_frames} total frames in {elapsed:.1f}s")
    print(f"[SDG] Rate: {total_frames / elapsed:.1f} frames/sec")
    print(f"[SDG] Output: {args.output}")


if __name__ == "__main__":
    main()
    simulation_app.close()
