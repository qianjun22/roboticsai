"""
OCI Robot Cloud — Isaac Sim SDG with Domain Randomization

Generates GR00T-ready training data using NVIDIA Isaac Sim 4.5.0 with:
  - RTX ray-traced rendering (photorealistic)
  - RmpFlow motion planning for IK-based pick-and-lift
  - Replicator domain randomization (lighting, texture, camera viewpoint, object color)
  - Output compatible with genesis_to_lerobot.py (joints.npy + rgb.npy per demo)

OCI advantage: Isaac Sim RTX rendering on A100 produces photorealistic domain-randomized
data that generalizes better to real robots vs. rasterized Genesis output.

Usage (inside Isaac Sim Docker container on OCI A100):
    docker run --rm \\
      --entrypoint /isaac-sim/python.sh \\
      --runtime=nvidia --gpus '"device=4"' \\
      -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \\
      -v ~/docker/isaac-sim/cache/kit:/isaac-sim/kit/cache:rw \\
      -v ~/docker/isaac-sim/cache/ov:/root/.cache/ov:rw \\
      -v ~/docker/isaac-sim/cache/pip:/root/.cache/pip:rw \\
      -v ~/roboticsai:/workspace \\
      -v /tmp/isaac_dr_output:/data:rw \\
      nvcr.io/nvidia/isaac-sim:4.5.0 \\
      /workspace/src/simulation/isaac_sim_sdg_dr.py \\
        --num-demos 100 \\
        --steps-per-demo 100 \\
        --output /data

Output per demo:
    /data/demo_0000/rgb.npy      — (T, H, W, 3) uint8, agentview camera
    /data/demo_0000/joints.npy   — (T, 9) float32, Franka joint angles [arm×7 + gripper×2]

Convert to LeRobot v2 for GR00T:
    python3 /workspace/src/training/genesis_to_lerobot.py \\
        --input /tmp/isaac_dr_output \\
        --output /tmp/isaac_lerobot \\
        --task "pick up the red cube"
"""

import argparse
import json
import os
import time

# SimulationApp MUST be instantiated before any other omniverse imports
from isaacsim import SimulationApp

parser = argparse.ArgumentParser(description="Isaac Sim SDG with domain randomization")
parser.add_argument("--num-demos",      type=int, default=10,              help="Number of demos")
parser.add_argument("--steps-per-demo", type=int, default=100,             help="Steps per episode")
parser.add_argument("--output",         type=str, default="/tmp/sdg_dr",   help="Output directory")
parser.add_argument("--img-size",       type=int, default=256,             help="Camera resolution (square)")
parser.add_argument("--seed",           type=int, default=42)
args = parser.parse_args()

simulation_app = SimulationApp({"headless": True, "renderer": "RayTracedLighting"})

# Late imports (after SimulationApp)
import carb
import numpy as np
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid, VisualCuboid
from omni.isaac.core.utils.prims import create_prim
from omni.isaac.franka import Franka
from omni.isaac.franka.controllers import RMPFlowController
from omni.isaac.sensor import Camera
import omni.replicator.core as rep

os.makedirs(args.output, exist_ok=True)
rng = np.random.default_rng(seed=args.seed)

# ── Phase durations (must sum to steps_per_demo) ─────────────────────────────
# Mimics genesis_sdg_planned.py for dataset consistency
PHASE_APPROACH = 40   # move to pre-grasp above target
PHASE_DESCEND  = 20   # descend to grasp
PHASE_GRASP    = 10   # close gripper
PHASE_LIFT     = 30   # lift to carry height
assert PHASE_APPROACH + PHASE_DESCEND + PHASE_GRASP + PHASE_LIFT == 100, \
    "Phase steps must sum to 100; adjust steps-per-demo accordingly"


# ── Scene builder ─────────────────────────────────────────────────────────────

def build_scene(world: World):
    """Build Franka + table + target cube + camera."""
    world.scene.add_default_ground_plane()

    # Table
    table = VisualCuboid(
        prim_path="/World/Table",
        name="table",
        position=np.array([0.4, 0.0, 0.35]),
        scale=np.array([0.8, 0.6, 0.7]),
        color=np.array([0.6, 0.4, 0.2]),
    )
    world.scene.add(table)

    # Franka robot at origin
    robot = Franka(prim_path="/World/Franka", name="franka")
    world.scene.add(robot)

    # Target cube (to be picked up)
    target = DynamicCuboid(
        prim_path="/World/Target",
        name="target",
        position=np.array([0.4, 0.0, 0.73]),
        scale=np.array([0.05, 0.05, 0.05]),
        color=np.array([1.0, 0.2, 0.2]),
        mass=0.1,
    )
    world.scene.add(target)

    # Primary camera (agentview — 70° tilt, matches LIBERO / Genesis convention)
    camera = Camera(
        prim_path="/World/Camera",
        position=np.array([0.5, 0.0, 1.4]),
        frequency=20,
        resolution=(args.img_size, args.img_size),
        orientation=rep.utils.euler_angles_to_quats([0, 70, 0], degrees=True),
    )
    world.scene.add(camera)

    return robot, table, target, camera


# ── Domain randomization setup ────────────────────────────────────────────────

def setup_replicator(target_prim_path: str, camera_prim_path: str):
    """
    Register Replicator randomizers:
    - Key light: intensity and direction
    - Fill light: soft hemisphere
    - Camera viewpoint: small cone around default position
    - Target cube: color
    All triggered once per episode reset.
    """
    with rep.new_layer():

        # Key light (directional — simulate sun angle variation)
        key_light = rep.create.light(
            light_type="Distant",
            intensity=rep.distribution.uniform(500, 1500),
            direction=rep.distribution.uniform((-30, -30, -90), (30, 30, -60)),
            color=rep.distribution.uniform((0.95, 0.90, 0.85), (1.0, 1.0, 1.0)),
            name="KeyLight",
        )

        # Fill light (dome — randomize intensity for ambient variation)
        dome_light = rep.create.light(
            light_type="Dome",
            intensity=rep.distribution.uniform(100, 500),
            name="DomeLight",
        )

        # Camera viewpoint jitter: ±5cm position, ±3° tilt
        camera_rep = rep.get.prim(camera_prim_path)
        with camera_rep:
            rep.modify.pose(
                position=rep.distribution.uniform(
                    (0.45, -0.05, 1.35),
                    (0.55,  0.05, 1.45),
                ),
                rotation=rep.distribution.uniform(
                    (0, 67, 0),
                    (0, 73, 0),
                ),
            )

        # Target cube color randomization (warm hues → red/orange/yellow)
        target_rep = rep.get.prim(target_prim_path)
        with target_rep:
            rep.modify.color(
                colors=rep.distribution.uniform((0.6, 0.0, 0.0), (1.0, 0.4, 0.1))
            )

    return rep.orchestrator


# ── Episode runner ────────────────────────────────────────────────────────────

def run_episode(world: World, robot: Franka, target: DynamicCuboid,
                camera: Camera, controller: RMPFlowController,
                rep_orch, demo_idx: int) -> dict:
    """Run one pick-and-lift episode with domain randomization."""

    # 1. Reset world and randomize scene
    world.reset()
    rep_orch.step(pause_timeline=False)  # apply Replicator randomizations

    # Randomize target XY on table surface
    tx = rng.uniform(-0.12, 0.12)
    ty = rng.uniform(-0.10, 0.10)
    target_pos = np.array([0.4 + tx, ty, 0.73])
    target.set_world_pose(position=target_pos)

    # Wait a couple steps for physics to settle
    for _ in range(5):
        world.step(render=False)

    # 2. Define waypoints for 4-phase pick-and-lift
    pre_grasp_pos = np.array([target_pos[0], target_pos[1], 0.95])  # above cube
    grasp_pos     = np.array([target_pos[0], target_pos[1], 0.755]) # at cube
    lift_pos      = np.array([target_pos[0], target_pos[1], 1.05])  # lifted

    # Phases: (target_ee_pos, gripper_open, num_steps)
    phases = [
        (pre_grasp_pos, True,  PHASE_APPROACH),
        (grasp_pos,     True,  PHASE_DESCEND),
        (grasp_pos,     False, PHASE_GRASP),    # close gripper
        (lift_pos,      False, PHASE_LIFT),
    ]

    frames = []
    joints_list = []

    for ee_target, gripper_open, n_steps in phases:
        gripper_cmd = np.array([0.04, 0.04]) if gripper_open else np.array([0.0, 0.0])

        for _ in range(n_steps):
            # RmpFlow: compute joint action toward EE target
            joint_pos = robot.get_joint_positions()
            ee_pos, ee_rot = robot.end_effector.get_world_pose()

            action = controller.forward(
                target_end_effector_position=ee_target,
                target_end_effector_orientation=np.array([0.0, 0.707, 0.0, 0.707]),  # pointing down
            )

            # Apply arm action + gripper command
            full_action = np.concatenate([action.joint_positions[:7], gripper_cmd])
            robot.apply_action(
                robot.get_articulation_controller().get_action_from_position(full_action)
            )

            world.step(render=True)

            # Record joint state (9 DoF: 7 arm + 2 gripper)
            q = robot.get_joint_positions()
            joints_list.append(q[:9].astype(np.float32))

            # Capture camera frame
            img = camera.get_rgba()
            if img is not None:
                frames.append(img[:, :, :3].copy())
            else:
                frames.append(np.zeros((args.img_size, args.img_size, 3), dtype=np.uint8))

    return {
        "demo_idx": demo_idx,
        "target_pos": target_pos.tolist(),
        "frames": frames,        # list of (H,W,3) arrays
        "joints": joints_list,   # list of (9,) arrays
    }


# ── Save ──────────────────────────────────────────────────────────────────────

def save_episode(ep: dict):
    demo_dir = os.path.join(args.output, f"demo_{ep['demo_idx']:04d}")
    os.makedirs(demo_dir, exist_ok=True)

    rgb = np.stack(ep["frames"]).astype(np.uint8)      # (T, H, W, 3)
    joints = np.stack(ep["joints"]).astype(np.float32)  # (T, 9)

    np.save(os.path.join(demo_dir, "rgb.npy"), rgb)
    np.save(os.path.join(demo_dir, "joint_states.npy"), joints)  # matches genesis_to_lerobot.py

    with open(os.path.join(demo_dir, "meta.json"), "w") as f:
        json.dump({"target_pos": ep["target_pos"], "steps": len(ep["frames"])}, f)

    print(f"  [SDG] demo_{ep['demo_idx']:04d}: rgb{rgb.shape} joint_states{joints.shape}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 64)
    print(" OCI Robot Cloud — Isaac Sim SDG with Domain Randomization")
    print(f" Renderer: RTX RayTracedLighting")
    print(f" Demos: {args.num_demos}  Steps/demo: {args.steps_per_demo}")
    print(f" Image: {args.img_size}×{args.img_size}  Output: {args.output}")
    print("=" * 64)

    world = World(stage_units_in_meters=1.0)
    robot, table, target, camera = build_scene(world)
    world.reset()

    # RmpFlow motion controller (Isaac Sim built-in)
    controller = RMPFlowController(
        name="rmpflow_controller",
        robot_articulation=robot,
    )

    # Replicator randomization orchestrator
    rep_orch = setup_replicator(
        target_prim_path="/World/Target",
        camera_prim_path="/World/Camera",
    )

    t_start = time.perf_counter()
    success = 0

    for i in range(args.num_demos):
        try:
            ep = run_episode(world, robot, target, camera, controller, rep_orch, demo_idx=i)
            save_episode(ep)
            success += 1
        except Exception as e:
            print(f"  [SDG] demo_{i:04d} FAILED: {e}")

    elapsed = time.perf_counter() - t_start
    total_frames = success * args.steps_per_demo
    fps = total_frames / elapsed if elapsed > 0 else 0

    print()
    print("=" * 64)
    print(f" Done: {success}/{args.num_demos} demos, {elapsed:.1f}s")
    print(f" Throughput: {fps:.1f} frames/sec (RTX ray-traced)")
    print(f" Domain randomization: lighting + camera + object color")
    print(f" Output: {args.output}  (convert with genesis_to_lerobot.py)")
    print("=" * 64)

    # Write summary JSON
    summary = {
        "num_demos": success,
        "steps_per_demo": args.steps_per_demo,
        "wall_time_sec": round(elapsed, 1),
        "fps": round(fps, 1),
        "img_size": args.img_size,
        "domain_randomization": ["lighting_intensity", "lighting_direction",
                                  "camera_viewpoint", "object_color", "object_position"],
        "renderer": "RTX RayTracedLighting",
        "hardware": "OCI A100-SXM4-80GB",
    }
    with open(os.path.join(args.output, "sdg_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
    simulation_app.close()
