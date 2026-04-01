"""
DAgger (Dataset Aggregation) training for closed-loop GR00T improvement.

Unlike pure imitation learning which gives 0% closed-loop success,
DAgger iteratively collects on-policy rollouts and queries an expert
corrector to label them, bootstrapping toward closed-loop competence.

Algorithm:
  1. Start with imitation-learned GR00T checkpoint (port 8002)
  2. Roll out current policy in Genesis simulation
  3. At each step, compare policy action vs IK expert action
  4. If diverging, record expert-labeled frame → aggregate into dataset
  5. Fine-tune GR00T on aggregated dataset
  6. Repeat for N DAgger iterations

Usage:
    python3 dagger_train.py \\
        --server-url http://localhost:8002 \\
        --output-dir /tmp/dagger_run \\
        --dagger-iters 5 \\
        --episodes-per-iter 20 \\
        --finetune-steps 500
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

try:
    import genesis as gs
except ImportError:
    print("[DAgger] Genesis not installed — install with: pip install genesis-world")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("[DAgger] Pillow not installed — install with: pip install Pillow")
    sys.exit(1)

# ── Scene constants (must match genesis_sdg_planned.py exactly) ──────────────
TABLE_Z     = 0.7
CUBE_HALF   = 0.025
LIFT_THRESH = TABLE_Z + 0.08        # 0.78m = success
Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04])

# IK phases for expert corrector (same as genesis_sdg_planned.py)
PRE_GRASP_POS  = np.array([0.45, 0.0, TABLE_Z + 0.12])
GRASP_POS      = np.array([0.45, 0.0, TABLE_Z + CUBE_HALF + 0.01])
LIFT_POS       = np.array([0.45, 0.0, TABLE_Z + 0.20])


# ── Scene builder ─────────────────────────────────────────────────────────────

def build_scene(use_cuda: bool = True):
    backend = gs.cuda if use_cuda else gs.cpu
    gs.init(backend=backend, logging_level="warning")
    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
    )
    scene.add_entity(gs.morphs.Plane())
    scene.add_entity(
        gs.morphs.Box(
            size=(0.8, 0.6, TABLE_Z),
            pos=(0.45, 0, TABLE_Z / 2),
            fixed=True,
        )
    )
    cube = scene.add_entity(
        gs.morphs.Box(
            size=(0.05, 0.05, 0.05),
            pos=(0.45, 0.0, TABLE_Z + CUBE_HALF),
        )
    )
    robot = scene.add_entity(
        gs.morphs.MJCF(
            file="xml/franka_emika_panda/panda.xml",
            requires_jac_and_IK=True,
        )
    )
    cam = scene.add_camera(
        res=(256, 256),
        pos=(0.5, 0, 1.4),
        lookat=(0.45, 0, TABLE_Z),
        fov=55,
    )
    scene.build()
    return scene, robot, cube, cam


# ── IK Expert ────────────────────────────────────────────────────────────────

class IKExpert:
    """
    Phase-based IK expert that produces reference joint positions.
    Mirrors the 4-phase planner in genesis_sdg_planned.py.
    """

    PHASES = ["approach", "pre_grasp", "grasp", "lift"]

    def __init__(self, robot, cube):
        self.robot = robot
        self.cube = cube
        self.phase_idx = 0
        self.step_in_phase = 0

    def reset(self):
        self.phase_idx = 0
        self.step_in_phase = 0

    def get_action(self, arm_q: np.ndarray, grip_q: np.ndarray) -> np.ndarray:
        """Return 9-DOF expert joint target for current step."""
        cube_pos = self._cube_pos()
        pre = np.array([cube_pos[0], cube_pos[1], TABLE_Z + 0.12])
        grasp = np.array([cube_pos[0], cube_pos[1], TABLE_Z + CUBE_HALF + 0.01])
        lift = np.array([cube_pos[0], cube_pos[1], TABLE_Z + 0.22])

        if self.phase_idx == 0:          # home → pre-grasp
            target_pos, gripper_open = pre, True
        elif self.phase_idx == 1:        # descend to grasp
            target_pos, gripper_open = grasp, True
        elif self.phase_idx == 2:        # close gripper
            target_pos, gripper_open = grasp, False
        else:                            # lift
            target_pos, gripper_open = lift, False

        # IK solve (returns None if unreachable)
        q_arm = self._ik(target_pos)
        if q_arm is None:
            q_arm = arm_q  # keep current if IK fails

        grip = np.array([0.04, 0.04]) if gripper_open else np.array([0.0, 0.0])

        self.step_in_phase += 1
        phase_durations = [25, 20, 10, 45]
        if self.step_in_phase >= phase_durations[min(self.phase_idx, 3)]:
            self.phase_idx = min(self.phase_idx + 1, 3)
            self.step_in_phase = 0

        return np.concatenate([q_arm, grip])

    def _ik(self, target_pos: np.ndarray):
        try:
            link = self.robot.get_link("hand")
            q = self.robot.inverse_kinematics(link=link, pos=target_pos)
            return np.array(q[:7]) if q is not None else None
        except Exception:
            return None

    def _cube_pos(self) -> np.ndarray:
        try:
            p = self.cube.get_pos()
            if hasattr(p, "cpu"):
                p = p.cpu()
            return np.array(p).flatten()[:3]
        except Exception:
            return np.array([0.45, 0.0, TABLE_Z + CUBE_HALF])


# ── GR00T policy query ────────────────────────────────────────────────────────

def query_policy(server_url: str, rgb: np.ndarray, instruction: str) -> tuple:
    """Query GR00T server, return (arm_actions[16×7], gripper_actions[16×2])."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        Image.fromarray(rgb).save(tmp.name, quality=90)
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{server_url}/predict",
             "-F", f"image=@{tmp.name}", "-F", f"instruction={instruction}"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        return np.array(data["arm"]), np.array(data["gripper"])
    finally:
        os.unlink(tmp.name)


# ── DAgger episode rollout ────────────────────────────────────────────────────

def rollout_episode(
    scene, robot, cube, cam,
    server_url: str,
    expert: IKExpert,
    instruction: str = "pick up the red cube from the table",
    max_steps: int = 100,
    beta: float = 0.5,        # prob of using expert vs policy
    diverge_threshold: float = 0.15,  # L∞ norm to trigger aggregation
) -> dict:
    """
    One DAgger episode.

    Returns dict with:
      - frames: list of RGB arrays (256×256×3)
      - expert_actions: list of 9-DOF expert joint targets
      - policy_actions: list of 9-DOF policy joint targets
      - success: bool
      - diverged_steps: int (steps where policy diverged from expert)
    """
    scene.reset()
    robot.set_dofs_position(Q_HOME)
    scene.step()  # 1 settle step (on CUDA, arm drifts to j5≈2.124 = training start)

    # Randomize cube position
    rng = np.random.default_rng()
    xy = rng.uniform(-0.12, 0.12, size=2)
    cube_pos_init = np.array([0.45 + xy[0], xy[1], TABLE_Z + CUBE_HALF])
    cube.set_pos(cube_pos_init)

    # 3 PD steps at Q_HOME while cube settles
    for _ in range(3):
        robot.control_dofs_position(Q_HOME[:9].astype(np.float64), dofs_idx_local=list(range(9)))
        scene.step()

    # Verify cube is on the table before starting (sanity check for Genesis state issues)
    try:
        cp0 = cube.get_pos()
        if hasattr(cp0, "cpu"):
            cp0 = cp0.cpu()
        z0 = float(np.array(cp0).flatten()[2])
        if z0 >= LIFT_THRESH:
            # Cube spawned above success threshold — re-place it
            cube.set_pos(np.array([0.45, 0.0, TABLE_Z + CUBE_HALF]))
            for _ in range(3):
                robot.control_dofs_position(Q_HOME[:9].astype(np.float64), dofs_idx_local=list(range(9)))
                scene.step()
    except Exception:
        pass

    expert.reset()
    frames, expert_acts, policy_acts, actual_states = [], [], [], []
    diverged_steps = 0

    arm_q = Q_HOME[:7].copy()
    grip_q = Q_HOME[7:9].copy()
    policy_chunk_arm = None
    policy_chunk_grip = None
    chunk_step = 0

    for step_i in range(max_steps):
        # Render observation
        rgb_raw = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
        rgb = rgb_raw[0] if isinstance(rgb_raw, (list, tuple)) else rgb_raw
        if hasattr(rgb, "cpu"):
            rgb = rgb.cpu()
        if hasattr(rgb, "numpy"):
            rgb = rgb.numpy()
        if rgb.ndim == 4:
            rgb = rgb[0]
        if rgb.shape[-1] == 4:
            rgb = rgb[:, :, :3]
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)

        # Expert action
        exp_action = expert.get_action(arm_q, grip_q)

        # Policy action (refresh chunk every 16 steps)
        if policy_chunk_arm is None or chunk_step >= 16:
            try:
                policy_chunk_arm, policy_chunk_grip = query_policy(
                    server_url, rgb, instruction
                )
                chunk_step = 0
            except Exception as e:
                print(f"  [warn] policy query failed at step {step_i}: {e}")
                policy_chunk_arm = np.tile(arm_q, (16, 1))
                policy_chunk_grip = np.tile(grip_q, (16, 1))
                chunk_step = 0  # must reset to avoid IndexError on next access

        pol_arm = policy_chunk_arm[chunk_step]
        pol_grip = policy_chunk_grip[chunk_step]
        pol_action = np.concatenate([pol_arm, pol_grip])
        chunk_step += 1

        # Record (always save expert label and actual robot state)
        frames.append(rgb.copy())
        expert_acts.append(exp_action.copy())
        policy_acts.append(pol_action.copy())
        actual_states.append(np.concatenate([arm_q, grip_q]).copy())

        # Detect divergence
        if np.max(np.abs(pol_action[:7] - exp_action[:7])) > diverge_threshold:
            diverged_steps += 1

        # Execute: mix policy and expert (beta-mixing)
        if np.random.random() < beta:
            exec_action = exp_action   # expert intervention
        else:
            exec_action = pol_action   # policy

        exec_arm = exec_action[:7]
        exec_grip = exec_action[7:9]
        exec_all = np.concatenate([exec_arm, exec_grip])
        robot.control_dofs_position(exec_all.astype(np.float64), dofs_idx_local=list(range(9)))
        for _ in range(2):  # 2 sim steps matches training SDG 20fps
            scene.step()

        q = robot.get_dofs_position()
        if hasattr(q, "cpu"):
            q = q.cpu()
        q = np.array(q).flatten()
        arm_q = q[:7]
        grip_q = q[7:9]

        # Check success
        try:
            cp = cube.get_pos()
            if hasattr(cp, "cpu"):
                cp = cp.cpu()
            cube_pos = np.array(cp).flatten()
            cube_z = float(cube_pos[2]) if len(cube_pos) > 2 else float(cube_pos)
            # Reject physically impossible values (Genesis state corruption)
            if cube_z < TABLE_Z - 0.15 or cube_z > TABLE_Z + 0.8:
                cube_z = TABLE_Z + CUBE_HALF
        except Exception:
            cube_z = TABLE_Z + CUBE_HALF
        if cube_z >= LIFT_THRESH and step_i >= 5:
            return {
                "frames": frames,
                "expert_actions": expert_acts,
                "policy_actions": policy_acts,
                "actual_states": actual_states,
                "success": True,
                "diverged_steps": diverged_steps,
                "steps": step_i + 1,
                "final_cube_z": cube_z,
            }

    return {
        "frames": frames,
        "expert_actions": expert_acts,
        "policy_actions": policy_acts,
        "actual_states": actual_states,
        "success": False,
        "diverged_steps": diverged_steps,
        "steps": max_steps,
        "final_cube_z": cube_z if 'cube_z' in dir() else TABLE_Z + CUBE_HALF,
    }


# ── Save aggregated dataset in LeRobot v2 format ─────────────────────────────

def save_lerobot_episode(
    out_dir: Path,
    episode_idx: int,
    frames: list,
    expert_actions: list,
    actual_states: list = None,
    fps: int = 20,
):
    """Save one DAgger episode as LeRobot v2-compatible numpy arrays.

    Saves three arrays:
      frames.npy        (N, 256, 256, 3) uint8 — camera frames
      actions.npy       (N, 9) float32       — expert IK action targets
      states.npy        (N, 9) float32       — actual robot joint states
                                               (falls back to actions if not provided)
    """
    ep_dir = out_dir / f"episode_{episode_idx:06d}"
    ep_dir.mkdir(parents=True, exist_ok=True)

    n = len(frames)
    np.save(ep_dir / "frames.npy", np.stack(frames).astype(np.uint8))
    np.save(ep_dir / "actions.npy", np.stack(expert_actions).astype(np.float32))
    if actual_states and len(actual_states) == n:
        np.save(ep_dir / "states.npy", np.stack(actual_states).astype(np.float32))
    else:
        # Fallback: use expert actions as states (legacy behavior)
        np.save(ep_dir / "states.npy", np.stack(expert_actions).astype(np.float32))

    # Write metadata JSON
    meta = {
        "episode_idx": episode_idx,
        "n_frames": len(frames),
        "fps": fps,
        "source": "dagger",
    }
    with open(ep_dir / "meta.json", "w") as f:
        json.dump(meta, f)


# ── Fine-tune step (calls existing launch_finetune.py) ───────────────────────

def run_finetune(dataset_dir: Path, checkpoint_dir: Path, steps: int, gpu_id: int,
                 base_model: str = "/tmp/finetune_500_5k/checkpoint-5000"):
    """Invoke GR00T fine-tuning on the DAgger-aggregated dataset."""
    # Resolve script paths relative to this file's location
    _here = Path(__file__).resolve().parent
    dagger_to_lerobot = _here / "dagger_to_lerobot.py"
    # GR00T launch_finetune lives in Isaac-GR00T repo
    groot_repo = Path(os.environ.get("GROOT_REPO", "/home/ubuntu/Isaac-GR00T"))
    launch_finetune = groot_repo / "gr00t" / "experiment" / "launch_finetune.py"
    python_bin = groot_repo / ".venv" / "bin" / "python3"
    if not python_bin.exists():
        python_bin = Path("python3")

    # First convert to LeRobot v2 format using DAgger-aware converter
    convert_cmd = [
        str(python_bin), str(dagger_to_lerobot),
        "--input", str(dataset_dir),
        "--output", str(dataset_dir / "lerobot"),
        "--fps", "20",
    ]
    print(f"[DAgger] Converting dataset → LeRobot v2...")
    result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[DAgger] Convert warning: {result.stderr[:200]}")

    modality_cfg = _here / "franka_config.py"
    finetune_cmd = [
        str(python_bin), str(launch_finetune),
        "--base-model-path", base_model,
        "--dataset-path", str(dataset_dir / "lerobot"),
        "--embodiment-tag", "NEW_EMBODIMENT",
        "--modality-config-path", str(modality_cfg),
        "--max-steps", str(steps),
        "--global-batch-size", "16",
        "--output-dir", str(checkpoint_dir),
    ]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    # Stop GR00T inference server to free GPU memory for fine-tune
    print(f"[DAgger] Stopping GR00T server to free GPU memory...")
    subprocess.run(["pkill", "-f", "groot_franka_server.py"], capture_output=True)
    import time as _time
    _time.sleep(8)  # wait for GPU memory to free

    print(f"[DAgger] Starting fine-tune: {steps} steps on GPU {gpu_id}...")
    result = subprocess.run(finetune_cmd, env=env, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        print(f"[DAgger] Fine-tune stderr: {result.stderr[-500:]}")
    else:
        print(f"[DAgger] Fine-tune complete.")
    return result.returncode == 0


# ── Main DAgger loop ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DAgger training for GR00T closed-loop improvement")
    parser.add_argument("--server-url", default="http://localhost:8002",
                        help="GR00T inference server URL")
    parser.add_argument("--output-dir", default="/tmp/dagger_run",
                        help="Directory to store aggregated dataset + checkpoints")
    parser.add_argument("--dagger-iters", type=int, default=5,
                        help="Number of DAgger iterations")
    parser.add_argument("--episodes-per-iter", type=int, default=20,
                        help="Episodes to collect per DAgger iteration")
    parser.add_argument("--finetune-steps", type=int, default=500,
                        help="Fine-tuning steps per iteration")
    parser.add_argument("--max-steps", type=int, default=100,
                        help="Max sim steps per episode")
    parser.add_argument("--beta-start", type=float, default=0.9,
                        help="Initial expert mixing probability (1.0 = pure expert)")
    parser.add_argument("--beta-decay", type=float, default=0.7,
                        help="Beta multiplier per iteration (0.7 → beta decays toward 0)")
    parser.add_argument("--gpu-id", type=int, default=4)
    parser.add_argument("--base-model", default="/tmp/finetune_500_5k/checkpoint-5000",
                        help="Base GR00T checkpoint to start fine-tuning from")
    parser.add_argument("--dry-run", action="store_true",
                        help="Collect one episode and exit (for testing)")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir = out_dir / "dataset"
    ckpt_dir = out_dir / "checkpoints"
    dataset_dir.mkdir(exist_ok=True)
    ckpt_dir.mkdir(exist_ok=True)

    results_log = []
    episode_counter = 0

    print(f"\n[DAgger] Starting {args.dagger_iters} iterations")
    print(f"[DAgger] {args.episodes_per_iter} episodes/iter, {args.finetune_steps} finetune steps/iter")
    print(f"[DAgger] Beta start={args.beta_start}, decay={args.beta_decay}")
    print(f"[DAgger] Output: {out_dir}\n")

    # Build Genesis scene once (reuse across iterations)
    print("[DAgger] Building Genesis scene (Taichi JIT — may take ~5min first run)...")
    scene, robot, cube, cam = build_scene(use_cuda=True)
    print("[DAgger] Scene ready.\n")

    beta = args.beta_start

    for iter_i in range(args.dagger_iters):
        print(f"{'='*60}")
        print(f"[DAgger] Iteration {iter_i+1}/{args.dagger_iters}  beta={beta:.2f}")
        print(f"{'='*60}")

        expert = IKExpert(robot, cube)
        iter_successes = 0
        iter_diverged = 0

        for ep_i in range(args.episodes_per_iter):
            print(f"  [ep {ep_i+1:02d}/{args.episodes_per_iter}] ", end="", flush=True)
            t0 = time.time()

            ep = rollout_episode(
                scene, robot, cube, cam,
                server_url=args.server_url,
                expert=expert,
                max_steps=args.max_steps,
                beta=beta,
            )

            dt = time.time() - t0
            status = "SUCCESS" if ep["success"] else f"cube_z={ep['final_cube_z']:.3f}"
            print(f"{status} | {ep['steps']} steps | {ep['diverged_steps']} diverged | {dt:.1f}s")

            if ep["success"]:
                iter_successes += 1
            iter_diverged += ep["diverged_steps"]

            # Skip degenerate episodes (cube fell off at step 0)
            MIN_FRAMES = 10
            if len(ep["frames"]) < MIN_FRAMES:
                print(f"  [warn] skipping short episode ({len(ep['frames'])} frames < {MIN_FRAMES})")
                continue

            # Save episode to aggregated dataset (with actual robot states)
            save_lerobot_episode(
                dataset_dir, episode_counter,
                ep["frames"], ep["expert_actions"],
                actual_states=ep.get("actual_states"),
            )
            episode_counter += 1

            if args.dry_run:
                print("[DAgger] Dry run complete — 1 episode collected.")
                return

        success_rate = iter_successes / args.episodes_per_iter
        avg_diverged = iter_diverged / args.episodes_per_iter
        print(f"\n  [DAgger iter {iter_i+1}] Success={success_rate:.0%} | Avg diverged={avg_diverged:.1f} steps/ep")
        print(f"  [DAgger iter {iter_i+1}] Total episodes aggregated: {episode_counter}")

        results_log.append({
            "iter": iter_i + 1,
            "beta": beta,
            "success_rate": success_rate,
            "avg_diverged_steps": avg_diverged,
            "total_episodes": episode_counter,
        })

        # Fine-tune on aggregated dataset (stops server to free GPU memory)
        iter_ckpt = ckpt_dir / f"iter_{iter_i+1:02d}"
        ok = run_finetune(dataset_dir, iter_ckpt, args.finetune_steps, args.gpu_id,
                          base_model=args.base_model)
        if ok:
            print(f"  [DAgger] Checkpoint saved to {iter_ckpt}")
            active_checkpoint = str(iter_ckpt)
        else:
            print(f"  [DAgger] Fine-tune failed — continuing with previous checkpoint")
            active_checkpoint = args.base_model

        # Restart GR00T server with new checkpoint for next iteration
        if iter_i < args.dagger_iters - 1:
            import time as _time2
            groot_venv = Path(os.environ.get("GROOT_REPO", "/home/ubuntu/Isaac-GR00T")) / ".venv" / "bin" / "python3"
            server_script = Path(__file__).resolve().parent.parent / "inference" / "groot_franka_server.py"
            if groot_venv.exists() and server_script.exists():
                print(f"  [DAgger] Restarting GR00T server with checkpoint: {active_checkpoint}")
                env2 = os.environ.copy()
                env2["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
                groot_repo = os.environ.get("GROOT_REPO", "/home/ubuntu/Isaac-GR00T")
                server_port = args.server_url.split(":")[-1].rstrip("/")
                subprocess.Popen(
                    [str(groot_venv), str(server_script),
                     "--checkpoint", active_checkpoint, "--port", server_port, "--device", "0"],
                    env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=groot_repo,
                )
                # Wait up to 90s for /health, then verify model loaded via /act
                import urllib.request as _ur, json as _json
                server_ready = False
                health_ok = False
                for _wait in range(18):
                    _time2.sleep(5)
                    try:
                        _ur.urlopen(f"{args.server_url}/health", timeout=3)
                        health_ok = True
                        break
                    except Exception:
                        pass
                if health_ok:
                    # /health passes when FastAPI starts but GR00T model may still be loading.
                    # Verify readiness by querying /act with a dummy payload (up to 60s more).
                    import numpy as _np
                    _dummy = {
                        "observation.images.cam_high": [[[[128,128,128]]*3]*3],
                        "observation.state": [[0.0]*7],
                        "annotation.human.action.task_description": ["pick up the cube"],
                    }
                    _dummy_data = _json.dumps(_dummy).encode()
                    for _vwait in range(12):
                        try:
                            _req = _ur.Request(f"{args.server_url}/act",
                                data=_dummy_data,
                                headers={"Content-Type": "application/json"})
                            _resp = _ur.urlopen(_req, timeout=10)
                            _body = _resp.read()
                            if _body and len(_body) > 2:
                                server_ready = True
                                break
                        except Exception:
                            pass
                        _time2.sleep(5)
                    if not server_ready:
                        # /act still not responding — wait 30s more as last resort
                        _time2.sleep(30)
                        server_ready = True  # proceed anyway, might work
                if server_ready:
                    print(f"  [DAgger] Server ready (model loaded + /act verified)")
                else:
                    print(f"  [DAgger] WARNING: server did not start, next iter may fail")

        # Decay beta (less expert intervention each iteration)
        beta = max(0.0, beta * args.beta_decay)
        print()

    # Save results log
    with open(out_dir / "dagger_results.json", "w") as f:
        json.dump(results_log, f, indent=2)

    print(f"\n{'='*60}")
    print(f"[DAgger] Training complete — {args.dagger_iters} iterations, {episode_counter} total episodes")
    print(f"[DAgger] Results: {out_dir / 'dagger_results.json'}")
    print(f"{'='*60}\n")

    # Print progression table
    print(f"{'Iter':>4} {'Beta':>6} {'Success':>8} {'Diverged/ep':>11} {'Total eps':>10}")
    print("-" * 45)
    for r in results_log:
        print(f"{r['iter']:>4} {r['beta']:>6.2f} {r['success_rate']:>8.0%} "
              f"{r['avg_diverged_steps']:>11.1f} {r['total_episodes']:>10}")


if __name__ == "__main__":
    main()
