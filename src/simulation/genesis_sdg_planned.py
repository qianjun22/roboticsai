"""
OCI Robot Cloud — Genesis Synthetic Data Generation (Motion-Planned)

Generates high-quality Franka Panda pick-and-place demonstrations using:
  - Inverse kinematics (IK) for end-effector targeting
  - Joint-space interpolation for smooth trajectories
  - PD position control for realistic robot dynamics

Task: pick red cube from randomized table position, lift to fixed height.

This replaces the random-noise baseline with real task demonstrations,
providing meaningful training signal for GR00T fine-tuning.

Demo phases per trajectory:
  1. Home → Pre-grasp (above cube, gripper open)    ~40 steps
  2. Pre-grasp → Grasp (lower to cube, gripper open) ~20 steps
  3. Grasp close (close fingers)                     ~10 steps
  4. Lift (raise end-effector up)                    ~30 steps

Usage:
    source ~/genesis_venv/bin/activate
    CUDA_VISIBLE_DEVICES=4 python3 src/simulation/genesis_sdg_planned.py \\
        --num-demos 100 --output /tmp/genesis_sdg_planned

Requirements:
    pip install genesis-world pillow numpy
"""

import argparse
import json
import os
import time

import numpy as np
from PIL import Image

parser = argparse.ArgumentParser(description="Motion-planned Genesis synthetic data generation")
parser.add_argument("--num-demos",  type=int, default=20,                    help="Number of demos")
parser.add_argument("--output",     type=str, default="/tmp/genesis_sdg_planned", help="Output dir")
parser.add_argument("--img-size",   type=int, default=256,                   help="Camera resolution")
parser.add_argument("--seed",       type=int, default=42,                    help="Random seed")
parser.add_argument("--show-failures", action="store_true",                  help="Save demos even if IK fails")
args = parser.parse_args()

import genesis as gs

gs.init(backend=gs.cuda, logging_level="warning")
os.makedirs(args.output, exist_ok=True)
print(f"[SDG] Genesis {gs.__version__} | output: {args.output}")

# ---------------------------------------------------------------------------
# Scene & robot constants
# ---------------------------------------------------------------------------

# Franka Panda home configuration (stable, arm above table)
Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04])

# Gripper DOF indices (last 2 of 9 total)
GRIPPER_OPEN  = 0.04   # 4cm per finger
GRIPPER_CLOSE = 0.005  # near-closed

# Table height
TABLE_Z = 0.7   # top surface
CUBE_HALF = 0.025

# Approach clearance above cube
PREGRASP_Z_OFFSET = 0.12   # 12cm above cube top
LIFT_Z = TABLE_Z + 0.25    # final lift height


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------

def build_scene() -> tuple:
    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
    )

    scene.add_entity(gs.morphs.Plane())

    # Table (fixed box)
    scene.add_entity(
        gs.morphs.Box(size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0.0, TABLE_Z / 2), fixed=True),
    )

    # Target cube — red, small, on table
    target = scene.add_entity(
        gs.morphs.Box(
            size=(0.05, 0.05, 0.05),
            pos=(0.45, 0.0, TABLE_Z + CUBE_HALF),
        ),
    )

    # Franka Panda — requires_jac_and_IK for IK solver
    robot = scene.add_entity(
        gs.morphs.MJCF(
            file="xml/franka_emika_panda/panda.xml",
            requires_jac_and_IK=True,
        ),
    )

    # Agentview camera
    cam = scene.add_camera(
        res=(args.img_size, args.img_size),
        pos=(0.5, 0.0, 1.4),
        lookat=(0.45, 0.0, 0.7),
        fov=55,
    )

    scene.build()
    return scene, robot, target, cam


# ---------------------------------------------------------------------------
# IK helper
# ---------------------------------------------------------------------------

def solve_ik(robot, ee_link, target_pos: np.ndarray, target_quat=None,
             init_q=None, pos_only=False) -> tuple[np.ndarray, bool]:
    """
    Solve IK for ee_link to reach target_pos.
    Returns (qpos, success).
    """
    quats = None if pos_only else (
        [target_quat] if target_quat is not None else None
    )
    try:
        result = robot.inverse_kinematics_multilink(
            links=[ee_link],
            poss=[target_pos],
            quats=quats,
            init_qpos=init_q,
            respect_joint_limit=True,
            max_samples=30,
            pos_tol=3e-3,      # 3mm — relaxed for speed
            rot_tol=0.1,
            pos_mask=[True, True, True],
            rot_mask=[False, False, True] if quats is None else [True, True, True],
            return_error=True,
        )
        qpos, err = result
        q = qpos.cpu().numpy().flatten()
        pos_err = np.linalg.norm(err.cpu().numpy()[:3])
        success = pos_err < 0.01  # 1cm tolerance
        return q, success
    except Exception:
        return Q_HOME.copy(), False


def interpolate_joints(q_start: np.ndarray, q_end: np.ndarray, n_steps: int) -> np.ndarray:
    """Linear interpolation between two joint configs."""
    t = np.linspace(0, 1, n_steps)[:, None]
    return q_start[None] * (1 - t) + q_end[None] * t


# ---------------------------------------------------------------------------
# Demo collection
# ---------------------------------------------------------------------------

def collect_demo(scene, robot, target, cam, rng: np.random.Generator,
                 demo_idx: int, ee_link) -> tuple[dict, bool]:
    """
    Collect one pick-and-lift demo.
    Returns (demo_dict, success).
    """
    scene.reset()

    # Randomize cube position on table
    xy = rng.uniform(-0.12, 0.12, size=2)
    cube_pos = np.array([0.45 + xy[0], xy[1], TABLE_Z + CUBE_HALF])
    target.set_pos(cube_pos)

    # Set robot to home
    robot.set_dofs_position(Q_HOME)
    scene.step()

    frames_rgb = []
    joint_states = []

    def step_and_record(q_traj: np.ndarray, set_gripper_val=None):
        """Execute a joint trajectory, recording frames and states."""
        for q in q_traj:
            if set_gripper_val is not None:
                q = q.copy()
                q[7] = set_gripper_val
                q[8] = set_gripper_val
            robot.control_dofs_position(q[:7], dofs_idx_local=list(range(7)))
            if set_gripper_val is not None:
                robot.control_dofs_position(
                    np.array([q[7], q[8]]), dofs_idx_local=[7, 8]
                )
            scene.step()
            rgb, _, _, _ = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
            frames_rgb.append(rgb)
            joint_states.append(robot.get_dofs_position().cpu().numpy().copy())

    # --- Phase 1: IK for pre-grasp (above cube) ---
    pregrasp_pos = cube_pos + np.array([0.0, 0.0, PREGRASP_Z_OFFSET])
    q_pregrasp, ok1 = solve_ik(robot, ee_link, pregrasp_pos, init_q=Q_HOME)
    q_pregrasp[7:] = GRIPPER_OPEN

    # --- Phase 2: IK for grasp (at cube) ---
    grasp_pos = cube_pos + np.array([0.0, 0.0, 0.01])
    q_grasp, ok2 = solve_ik(robot, ee_link, grasp_pos, init_q=q_pregrasp)
    q_grasp[7:] = GRIPPER_OPEN

    if not (ok1 and ok2):
        return {}, False

    # --- Phase 3: IK for lift ---
    lift_pos = cube_pos + np.array([0.0, 0.0, 0.22])
    q_lift, ok3 = solve_ik(robot, ee_link, lift_pos, init_q=q_grasp)
    q_lift[7:] = GRIPPER_CLOSE

    # Execute trajectory phases
    # Phase 1: Home → Pre-grasp (40 steps, gripper open)
    traj1 = interpolate_joints(Q_HOME, q_pregrasp, 40)
    step_and_record(traj1, set_gripper_val=GRIPPER_OPEN)

    # Phase 2: Pre-grasp → Grasp (20 steps, gripper open)
    traj2 = interpolate_joints(q_pregrasp, q_grasp, 20)
    step_and_record(traj2, set_gripper_val=GRIPPER_OPEN)

    # Phase 3: Close gripper (10 steps)
    traj3 = interpolate_joints(q_grasp, q_grasp, 10)
    step_and_record(traj3, set_gripper_val=GRIPPER_CLOSE)

    # Phase 4: Lift (30 steps, gripper closed)
    traj4 = interpolate_joints(q_grasp, q_lift, 30)
    step_and_record(traj4, set_gripper_val=GRIPPER_CLOSE)

    demo = {
        "demo_idx": demo_idx,
        "cube_pos": cube_pos.tolist(),
        "frames_rgb": np.stack(frames_rgb),            # (T, H, W, 3)
        "joint_states": np.array(joint_states),        # (T, 9)
        "n_dofs": robot.n_dofs,
        "phases": {"home_to_pregrasp": 40, "pregrasp_to_grasp": 20,
                   "gripper_close": 10, "lift": 30},
    }
    return demo, True


def save_demo(demo: dict, output_dir: str) -> None:
    demo_dir = os.path.join(output_dir, f"demo_{demo['demo_idx']:04d}")
    os.makedirs(demo_dir, exist_ok=True)

    np.save(os.path.join(demo_dir, "rgb.npy"),          demo["frames_rgb"])
    np.save(os.path.join(demo_dir, "joint_states.npy"), demo["joint_states"])

    meta = {
        "demo_idx":    demo["demo_idx"],
        "cube_pos":    demo["cube_pos"],
        "n_steps":     len(demo["frames_rgb"]),
        "n_dofs":      demo["n_dofs"],
        "img_size":    args.img_size,
        "phases":      demo["phases"],
        "task":        "pick the red cube from the table",
    }
    with open(os.path.join(demo_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    Image.fromarray(demo["frames_rgb"][0]).save(
        os.path.join(demo_dir, "frame_000.png")
    )
    Image.fromarray(demo["frames_rgb"][len(demo["frames_rgb"]) // 2]).save(
        os.path.join(demo_dir, "frame_mid.png")
    )
    Image.fromarray(demo["frames_rgb"][-1]).save(
        os.path.join(demo_dir, "frame_last.png")
    )

    T = demo["joint_states"].shape[0]
    print(f"  [SDG] demo_{demo['demo_idx']:04d}: {T} steps | "
          f"cube=[{demo['cube_pos'][0]:.2f},{demo['cube_pos'][1]:.2f}] -> {demo_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene, robot, target, cam = build_scene()

    # Get end-effector link (panda_hand or link8)
    ee_link = None
    for name in ["hand", "panda_hand", "panda_link8", "link8"]:
        try:
            ee_link = robot.get_link(name)
            print(f"[SDG] End-effector link: {name}")
            break
        except Exception:
            continue
    if ee_link is None:
        # Fall back to last link
        ee_link = robot.links[-1]
        print(f"[SDG] Using last link as EE: {robot.links[-1]}")

    rng = np.random.default_rng(seed=args.seed)
    t_start = time.perf_counter()
    n_success = 0
    attempt = 0

    print(f"[SDG] Generating {args.num_demos} motion-planned demos...")

    while n_success < args.num_demos:
        demo, success = collect_demo(scene, robot, target, cam, rng,
                                     demo_idx=n_success, ee_link=ee_link)
        attempt += 1

        if success:
            save_demo(demo, args.output)
            n_success += 1
        else:
            print(f"  [SDG] IK failed for attempt {attempt}, skipping...")
            if attempt > args.num_demos * 3:
                print("[SDG] Too many IK failures, stopping early.")
                break

    elapsed = time.perf_counter() - t_start
    total_frames = n_success * 100  # ~100 steps per demo
    print(f"\n[SDG] Done! {n_success}/{attempt} demos succeeded in {elapsed:.1f}s")
    print(f"[SDG] ~{elapsed / max(n_success, 1):.1f}s/demo | output: {args.output}")


if __name__ == "__main__":
    main()
