#!/usr/bin/env python3
"""
Curriculum Synthetic Data Generation (Curriculum SDG).

Generates training data in 3 difficulty stages, then combines into a single
LeRobot v2 dataset for GR00T fine-tuning. Curriculum learning improves
policy generalization by starting with easy configurations and progressively
increasing workspace randomization and object diversity.

Stages:
  Stage 1 (Easy)    — cube at fixed position, short reach, 30 demos
  Stage 2 (Medium)  — cube in front half of workspace, 40 demos
  Stage 3 (Hard)    — cube anywhere on table, full randomization, 30 demos

Usage:
    GPU_ID=4 python3 curriculum_sdg.py \
        --output /tmp/curriculum_sdg \
        --total-demos 100 \
        --stages 30,40,30

OCI command (GPU4):
    CUDA_VISIBLE_DEVICES=4 python3 curriculum_sdg.py \
        --output /tmp/curriculum_sdg \
        --total-demos 100
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# ── Dependency check ──────────────────────────────────────────────────────────

try:
    import genesis as gs
    HAS_GENESIS = True
except ImportError:
    HAS_GENESIS = False
    print("[curriculum] genesis not available — will use mock mode")


# ── Stage definitions ─────────────────────────────────────────────────────────

STAGES = [
    {
        "id": 1,
        "name": "Easy",
        "cube_x": (0.05, 0.10),   # narrow forward range
        "cube_y": (-0.05, 0.05),  # centered
        "description": "Fixed forward position, minimal lateral variance",
    },
    {
        "id": 2,
        "name": "Medium",
        "cube_x": (-0.02, 0.18),
        "cube_y": (-0.12, 0.12),
        "description": "Front-half workspace, moderate lateral variance",
    },
    {
        "id": 3,
        "name": "Hard",
        "cube_x": (-0.10, 0.22),
        "cube_y": (-0.18, 0.18),
        "description": "Full table, maximum randomization",
    },
]


# ── IK planner (same as genesis_sdg_planned.py) ───────────────────────────────

HOME_Q   = np.array([0.0, -0.3, 0.0, -2.0, 0.0, 1.8, 0.785], dtype=np.float32)
GRIP_OPEN   = np.array([0.04, 0.04], dtype=np.float32)
GRIP_CLOSED = np.array([0.00, 0.00], dtype=np.float32)

def ik_waypoints(cube_x: float, cube_y: float, cube_z: float = 0.02):
    """Return list of (arm_q, gripper) waypoints for pick-and-lift."""
    # Simplified analytical IK approximation for Franka above-table workspace
    # In production this calls genesis's IK solver; here we use a trajectory template
    pre_grasp_z  = 0.18
    grasp_z      = cube_z + 0.005
    lift_z       = 0.28

    # Offset end-effector target slightly from cube center
    ex, ey = cube_x + 0.0, cube_y + 0.0

    def arm_for_target(tx, ty, tz):
        """Very rough analytical IK — valid for small deviations from home."""
        q = HOME_Q.copy()
        q[0] += ty * 1.8      # base rotation ~ lateral
        q[1] += -(tz - 0.35) * 0.9  # shoulder pitch ~ height
        q[3] += (tx - 0.30) * 0.8   # elbow ~ forward reach
        return np.clip(q, -2.8, 2.8)

    waypoints = []
    # Pre-grasp (above cube)
    for _ in range(20):
        waypoints.append((arm_for_target(ex, ey, pre_grasp_z), GRIP_OPEN.copy()))
    # Descend
    for t in range(15):
        z = pre_grasp_z - (pre_grasp_z - grasp_z) * (t / 14)
        waypoints.append((arm_for_target(ex, ey, z), GRIP_OPEN.copy()))
    # Grasp
    for _ in range(10):
        waypoints.append((arm_for_target(ex, ey, grasp_z), GRIP_CLOSED.copy()))
    # Lift
    for t in range(15):
        z = grasp_z + (lift_z - grasp_z) * (t / 14)
        waypoints.append((arm_for_target(ex, ey, z), GRIP_CLOSED.copy()))
    # Hold
    for _ in range(40):
        waypoints.append((arm_for_target(ex, ey, lift_z), GRIP_CLOSED.copy()))

    return waypoints


# ── Single demo generation ────────────────────────────────────────────────────

def generate_demo_genesis(scene, robot, cube, cam, stage: dict, rng: np.random.Generator,
                           steps: int = 100) -> Optional[dict]:
    """Generate one demonstration episode for a given curriculum stage."""
    import genesis as gs

    # Reset robot
    home_qpos = np.concatenate([HOME_Q, GRIP_OPEN])
    robot.set_qpos(home_qpos[np.newaxis])

    # Place cube in stage-appropriate range
    cx = float(rng.uniform(*stage["cube_x"]))
    cy = float(rng.uniform(*stage["cube_y"]))
    cz = 0.02
    cube.set_pos(np.array([[cx, cy, cz]]))
    cube.set_quat(np.array([[1.0, 0.0, 0.0, 0.0]]))

    scene.step()

    waypoints = ik_waypoints(cx, cy, cz)
    if len(waypoints) < steps:
        waypoints = waypoints + [waypoints[-1]] * (steps - len(waypoints))
    waypoints = waypoints[:steps]

    frames, arm_states, gripper_states = [], [], []

    for arm_q, grip_q in waypoints:
        target = np.concatenate([arm_q, grip_q])
        robot.set_dofs_kp(np.array([4500]*7 + [100, 100]))
        robot.set_dofs_kv(np.array([450]*7 + [10, 10]))
        robot.set_dofs_position(target[np.newaxis])
        scene.step()

        rgb = cam.render(rgb=True)[0]  # (256, 256, 3) uint8
        qpos = robot.get_qpos()[0]     # (9,)

        frames.append(rgb)
        arm_states.append(qpos[:7].astype(np.float32))
        gripper_states.append(qpos[7:9].astype(np.float32))

    # Success check — cube z above table
    final_z = float(cube.get_pos()[0][2])
    success = final_z > 0.08

    if not success:
        return None

    return {
        "frames":   np.stack(frames),           # (T, 256, 256, 3) uint8
        "arm":      np.stack(arm_states),        # (T, 7) float32
        "gripper":  np.stack(gripper_states),    # (T, 2) float32
        "cube_pos": np.array([cx, cy, cz]),
        "stage":    stage["id"],
    }


# ── Mock demo generation (no Genesis) ────────────────────────────────────────

def generate_mock_demo(stage: dict, rng: np.random.Generator, steps: int = 100) -> dict:
    """Generate a plausible-shaped synthetic demo without Genesis."""
    cx = float(rng.uniform(*stage["cube_x"]))
    cy = float(rng.uniform(*stage["cube_y"]))

    frames  = (rng.integers(50, 200, (steps, 256, 256, 3), dtype=np.uint8))
    arm     = np.tile(HOME_Q, (steps, 1)) + rng.normal(0, 0.05, (steps, 7)).astype(np.float32)
    gripper = np.concatenate([
        np.tile(GRIP_OPEN, (steps//2, 1)),
        np.tile(GRIP_CLOSED, (steps - steps//2, 1)),
    ]).astype(np.float32)

    return {
        "frames":   frames,
        "arm":      arm.astype(np.float32),
        "gripper":  gripper,
        "cube_pos": np.array([cx, cy, 0.02]),
        "stage":    stage["id"],
    }


# ── LeRobot v2 episode saver ──────────────────────────────────────────────────

def save_episode(demo: dict, episode_id: int, output_dir: Path):
    """Save demo to LeRobot v2 format under output_dir/episode_{N:06d}/."""
    ep_dir = output_dir / f"episode_{episode_id:06d}"
    ep_dir.mkdir(parents=True, exist_ok=True)

    np.save(ep_dir / "rgb.npy",           demo["frames"])
    np.save(ep_dir / "joint_states.npy",  np.concatenate([demo["arm"], demo["gripper"]], axis=-1))
    np.save(ep_dir / "arm_states.npy",    demo["arm"])
    np.save(ep_dir / "gripper_states.npy", demo["gripper"])

    meta = {
        "episode_id":   episode_id,
        "stage":        demo["stage"],
        "cube_pos":     demo["cube_pos"].tolist(),
        "instruction":  "pick up the red cube from the table",
        "fps":          20,
        "length":       len(demo["frames"]),
    }
    (ep_dir / "metadata.json").write_text(json.dumps(meta, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Curriculum SDG for GR00T fine-tuning")
    parser.add_argument("--output", default="/tmp/curriculum_sdg",
                        help="Output directory for curriculum dataset")
    parser.add_argument("--total-demos", type=int, default=100,
                        help="Total demos across all stages")
    parser.add_argument("--stages", default="30,40,30",
                        help="Demos per stage, comma-separated (must sum to --total-demos)")
    parser.add_argument("--steps", type=int, default=100,
                        help="Steps per demo episode")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    stage_counts = list(map(int, args.stages.split(",")))
    assert len(stage_counts) == 3, "--stages must have exactly 3 values"
    assert sum(stage_counts) == args.total_demos, \
        f"Stage counts {stage_counts} must sum to --total-demos {args.total_demos}"

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_mock = args.mock or not HAS_GENESIS

    print(f"[curriculum] Curriculum SDG: {args.total_demos} total demos")
    print(f"[curriculum] Stages: Easy={stage_counts[0]}, Medium={stage_counts[1]}, Hard={stage_counts[2]}")
    print(f"[curriculum] Mode: {'MOCK' if use_mock else 'Genesis'} | Output: {output_dir}\n")

    rng = np.random.default_rng(42)
    t_start = time.time()
    episode_id = 0
    stage_stats = []

    if not use_mock:
        import genesis as gs
        gs.init(backend=gs.cuda, device=f"cuda:{args.gpu_id}", precision="32", logging_level="error")
        scene = gs.Scene(gravity=(0, 0, -9.81), dt=0.01, show_viewer=False,
                         renderer=gs.renderers.Rasterizer())
        scene.add_entity(gs.morphs.Plane())
        robot = scene.add_entity(gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"),
                                  material=gs.materials.Rigid())
        cube  = scene.add_entity(gs.morphs.Box(size=(0.04, 0.04, 0.04)),
                                  material=gs.materials.Rigid(rho=500),
                                  surface=gs.surfaces.Default(color=(0.8, 0.1, 0.1, 1.0)))
        cam   = scene.add_camera(res=(256, 256), pos=(0.5, 0.0, 0.5),
                                  lookat=(0.0, 0.0, 0.15), fov=60, GUI=False)
        scene.build(n_envs=1)

    for stage, count in zip(STAGES, stage_counts):
        stage_dir = output_dir / f"stage_{stage['id']}_{stage['name'].lower()}"
        stage_dir.mkdir(exist_ok=True)

        successes = 0
        attempts  = 0
        t_stage   = time.time()

        print(f"[curriculum] Stage {stage['id']} ({stage['name']}): {count} demos | {stage['description']}")

        while successes < count:
            attempts += 1
            if attempts > count * 5:
                print(f"[curriculum]   WARNING: too many attempts, stopping early ({successes}/{count})")
                break

            if use_mock:
                demo = generate_mock_demo(stage, rng, args.steps)
            else:
                demo = generate_demo_genesis(scene, robot, cube, cam, stage, rng, args.steps)

            if demo is None:
                continue

            save_episode(demo, episode_id, output_dir)
            save_episode(demo, successes, stage_dir)
            episode_id += 1
            successes += 1

            if successes % 10 == 0 or successes == count:
                elapsed = time.time() - t_stage
                print(f"[curriculum]   {successes:3d}/{count} demos | "
                      f"{elapsed:.0f}s elapsed | {successes/elapsed:.1f} demos/s")

        stage_stats.append({
            "stage": stage["id"],
            "name": stage["name"],
            "demos_generated": successes,
            "attempts": attempts,
            "success_rate": round(100 * successes / attempts, 1) if attempts > 0 else 100,
        })
        print(f"[curriculum]   Stage {stage['id']} complete: {successes} demos, "
              f"{attempts} attempts ({stage_stats[-1]['success_rate']}% IK success)")

    total_time = time.time() - t_start

    # Write dataset manifest
    manifest = {
        "dataset_type": "curriculum_sdg",
        "total_episodes": episode_id,
        "total_demos_requested": args.total_demos,
        "stages": stage_stats,
        "task": "pick-and-lift",
        "instruction": "pick up the red cube from the table",
        "fps": 20,
        "steps_per_demo": args.steps,
        "mode": "mock" if use_mock else "genesis",
        "generation_time_s": round(total_time, 1),
        "demos_per_second": round(episode_id / total_time, 2),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n[curriculum] Done: {episode_id} episodes in {total_time:.0f}s "
          f"({episode_id/total_time:.1f} demos/s)")
    print(f"[curriculum] Dataset → {output_dir}")
    print(f"\n[curriculum] Next step:")
    print(f"  python3 genesis_to_lerobot.py --input {output_dir} --output /tmp/curriculum_lerobot --fps 20")
    print(f"  CUDA_VISIBLE_DEVICES=4 python3 launch_finetune.py --dataset /tmp/curriculum_lerobot --max-steps 2000")


if __name__ == "__main__":
    main()
