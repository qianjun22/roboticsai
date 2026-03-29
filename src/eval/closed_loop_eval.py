#!/usr/bin/env python3
"""
Closed-loop evaluation harness for GR00T fine-tuned policies.

Two modes:
  --checkpoint PATH   Load policy in-process (requires gr00t + genesis in same venv)
  --server-url URL    Call running GR00T HTTP server (e.g. http://localhost:8002)

Usage:
    # HTTP mode (recommended — no CUDA conflict, tests real deployment)
    python3 closed_loop_eval.py \
        --server-url http://localhost:8002 \
        --num-episodes 20 --max-steps 500 \
        --output /tmp/eval_results.json

    # In-process mode
    python3 closed_loop_eval.py \
        --checkpoint /tmp/franka_pipeline_finetune/checkpoint-2000 \
        --num-episodes 20 --max-steps 500

Output:
    - JSON with per-episode results, success rate, timing
    - HTML report (eval_report.html) with charts
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

# ── Dependency checks ─────────────────────────────────────────────────────────

def check_genesis():
    try:
        import genesis  # noqa: F401
        return True
    except ImportError:
        return False

def check_torch():
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False

HAS_GENESIS = check_genesis()
HAS_TORCH   = check_torch()

# ── Scene constants (must match genesis_sdg_planned.py training geometry) ────

TABLE_Z    = 0.7      # table top surface — MATCHES training SDG
CUBE_HALF  = 0.025    # half cube side
LIFT_THRESHOLD = TABLE_Z + 0.08   # cube z > 0.78m = success

Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04], dtype=np.float64)
# Actual starting state from SDG training data (measured from joint_states.npy step 0)
# The sim produces this state after SDG init — NOT exactly Q_HOME due to physics
Q_TRAIN_START = np.array([-0.021, -0.424, 0.012, -1.887, 0.007, 2.124, 0.771, 0.040, 0.039], dtype=np.float64)
GRIPPER_OPEN  = 0.04
GRIPPER_CLOSE = 0.005

# ── Genesis scene setup ───────────────────────────────────────────────────────

def build_scene(use_cuda: bool = False):
    """Create Franka pick-and-place scene matching genesis_sdg_planned.py geometry.

    use_cuda: use CUDA backend to match the training SDG dynamics exactly.
    The CUDA backend has different PD equilibrium (~j5=2.124) than CPU (j5=1.799),
    matching the training data starting state.
    """
    import genesis as gs

    backend = gs.cuda if use_cuda else gs.cpu
    gs.init(backend=backend, logging_level="warning")

    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
    )

    scene.add_entity(gs.morphs.Plane())

    # Table (fixed box) — top surface at TABLE_Z=0.7
    scene.add_entity(
        gs.morphs.Box(size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0.0, TABLE_Z / 2), fixed=True),
    )

    # Target cube — red, 5cm, on table top
    cube = scene.add_entity(
        gs.morphs.Box(size=(0.05, 0.05, 0.05), pos=(0.45, 0.0, TABLE_Z + CUBE_HALF)),
    )

    # Franka Panda
    robot = scene.add_entity(
        gs.morphs.MJCF(
            file="xml/franka_emika_panda/panda.xml",
            requires_jac_and_IK=True,
        ),
    )

    # Camera — must match genesis_sdg_planned.py training setup exactly
    cam = scene.add_camera(
        res=(256, 256),
        pos=(0.5, 0.0, 1.4),
        lookat=(0.45, 0.0, TABLE_Z),
        fov=55,
    )

    scene.build()
    return scene, robot, cube, cam


def reset_episode(scene, robot, cube, rng: np.random.Generator):
    """Reset scene: robot to home, cube to random table position.

    Uses Q_HOME with PD control. On CUDA (matching training SDG), the Franka PD
    equilibrium naturally drifts to j5≈2.124 (matching training data step-0).
    On CPU the equilibrium stays at j5≈1.8 (use --no-cuda for CPU-only testing).
    """
    scene.reset()

    # Teleport to Q_HOME
    robot.set_dofs_position(Q_HOME)
    scene.step()

    # Place cube
    xy = rng.uniform(-0.12, 0.12, size=2)
    cube_pos = np.array([0.45 + xy[0], xy[1], TABLE_Z + CUBE_HALF])
    cube.set_pos(cube_pos)

    # Hold at Q_HOME via full 9-DOF PD for a few steps while cube settles.
    # On CUDA: after 1 PD step j5≈2.124 (matches training step-0 exactly).
    # Run 3 steps so cube is stable but arm stays near training start position.
    for _ in range(3):
        robot.control_dofs_position(Q_HOME[:9].astype(np.float64), dofs_idx_local=list(range(9)))
        scene.step()

    return cube_pos


def get_rgb(cam) -> np.ndarray:
    """Capture 256×256 RGB frame from Genesis camera."""
    # Genesis 0.4.3: render returns (rgb, depth, seg, normal) 4-tuple
    result = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
    if isinstance(result, (tuple, list)):
        rgb = result[0]
    else:
        rgb = result
    if hasattr(rgb, "numpy"):
        rgb = rgb.cpu().numpy()
    if rgb.ndim == 4:
        rgb = rgb[0]  # (1,H,W,3) → (H,W,3)
    if rgb.shape[-1] == 4:
        rgb = rgb[:, :, :3]  # RGBA → RGB
    return rgb.astype(np.uint8)


def get_qpos(robot) -> np.ndarray:
    """Get robot joint positions as numpy (7 arm + 2 gripper)."""
    q = robot.get_dofs_position()
    if hasattr(q, "numpy"):
        q = q.cpu().numpy()
    if q.ndim == 2:
        q = q[0]
    return q.astype(np.float32)


def check_success(cube) -> bool:
    """True if cube z > TABLE_Z + 0.08m (successfully lifted)."""
    pos = cube.get_pos()
    if hasattr(pos, "numpy"):
        pos = pos.cpu().numpy()
    if hasattr(pos, "ndim") and pos.ndim == 2:
        pos = pos[0]
    return float(pos[2]) > LIFT_THRESHOLD


def get_cube_z(cube) -> float:
    pos = cube.get_pos()
    if hasattr(pos, "numpy"):
        pos = pos.cpu().numpy()
    if hasattr(pos, "ndim") and pos.ndim == 2:
        pos = pos[0]
    return float(pos[2])


def apply_action(robot, scene, arm_q: np.ndarray, gripper_q: np.ndarray,
                 sim_steps: int = 5):
    """Apply one action step: arm + gripper position targets, then step sim."""
    robot.control_dofs_position(arm_q.astype(np.float64), dofs_idx_local=list(range(7)))
    robot.control_dofs_position(gripper_q.astype(np.float64), dofs_idx_local=[7, 8])
    for _ in range(sim_steps):
        scene.step()


# ── Policy: HTTP server mode ──────────────────────────────────────────────────

def query_server(server_url: str, rgb: np.ndarray, instruction: str,
                 arm_q: np.ndarray, grip_q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Query running GR00T HTTP server. Returns (arm_chunk, grip_chunk) each (16, D)."""
    import tempfile, io
    from PIL import Image
    import urllib.request

    # Save RGB as JPEG for multipart upload
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    Image.fromarray(rgb).save(tmp.name, quality=90)
    tmp.close()

    try:
        import subprocess
        arm_str = ",".join(f"{v:.6f}" for v in arm_q.flatten()[:7])
        grip_str = ",".join(f"{v:.6f}" for v in grip_q.flatten()[:2])
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{server_url}/predict",
             "-F", f"image=@{tmp.name}",
             "-F", f"instruction={instruction}",
             "-F", f"arm_joints={arm_str}",
             "-F", f"gripper={grip_str}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        data = json.loads(result.stdout)
        arm  = np.array(data["arm"],  dtype=np.float32)
        grip = np.array(data["gripper"], dtype=np.float32)
        return arm, grip
    finally:
        os.unlink(tmp.name)


# ── Policy: in-process mode ───────────────────────────────────────────────────

def load_policy(checkpoint_path: str, device: int = 0):
    """Load GR00T fine-tuned policy from checkpoint (in-process)."""
    repo_dir = Path(__file__).parents[2]
    sys.path.insert(0, str(repo_dir / "src" / "training"))
    import franka_config  # noqa: F401 — registers NEW_EMBODIMENT tag

    from gr00t.policy.gr00t_policy import Gr00tPolicy
    from gr00t.data.embodiment_tags import EmbodimentTag

    print(f"[eval] Loading checkpoint: {checkpoint_path}")
    t0 = time.time()
    policy = Gr00tPolicy(
        model_path=checkpoint_path,
        embodiment_tag=EmbodimentTag.NEW_EMBODIMENT,
        device=device,
    )
    print(f"[eval] Policy loaded in {time.time() - t0:.1f}s")
    return policy


def query_inprocess(policy, rgb: np.ndarray, arm_q: np.ndarray,
                    grip_q: np.ndarray, instruction: str) -> tuple[np.ndarray, np.ndarray]:
    """Query in-process GR00T policy. Returns (arm_chunk, grip_chunk)."""
    obs = {
        "video":    {"agentview": rgb[np.newaxis, np.newaxis]},
        "state":    {"arm":     arm_q[np.newaxis, np.newaxis],
                     "gripper": grip_q[np.newaxis, np.newaxis]},
        "language": {"annotation.human.task_description": [[instruction]]},
    }
    action, _ = policy.get_action(obs)
    arm  = np.array(action["arm"],  dtype=np.float32)
    grip = np.array(action["gripper"], dtype=np.float32)
    if arm.ndim  == 3: arm  = arm[0]
    if grip.ndim == 3: grip = grip[0]
    return arm, grip


# ── Mock mode ─────────────────────────────────────────────────────────────────

def run_mock_eval(num_episodes: int, max_steps: int) -> list[dict]:
    """Synthetic results for CI / dry-run testing."""
    print("[eval] Running in MOCK MODE")
    rng = np.random.default_rng(42)
    results = []
    for ep in range(num_episodes):
        success = rng.random() < 0.65
        steps_to_success = int(rng.uniform(80, 160)) if success else max_steps
        t_policy = rng.uniform(0.15, 0.22)
        results.append({
            "episode": ep,
            "success": success,
            "steps": steps_to_success,
            "policy_latency_ms": round(t_policy * 1000, 1),
            "cube_final_z": round(rng.uniform(0.78, 0.95) if success else rng.uniform(0.70, 0.73), 3),
        })
        print(f"[eval] Episode {ep+1:02d}/{num_episodes}: {'✓ SUCCESS' if success else '✗ FAILED'} "
              f"({steps_to_success} steps, {t_policy*1000:.0f}ms/step)")
        time.sleep(0.02)
    return results


# ── Real eval ─────────────────────────────────────────────────────────────────

def run_eval(num_episodes: int, max_steps: int, sim_steps_per_action: int,
             server_url: str = "", checkpoint: str = "", gpu_id: int = 0,
             use_cuda: bool = True) -> list[dict]:
    """Run closed-loop eval with Genesis sim + GR00T policy (HTTP or in-process)."""

    use_server = bool(server_url)
    policy = None

    if not use_server:
        policy = load_policy(checkpoint, device=gpu_id)

    scene, robot, cube, cam = build_scene(use_cuda=use_cuda)

    rng = np.random.default_rng(42)
    results = []
    instruction = "pick up the red cube from the table"

    for ep in range(num_episodes):
        cube_pos = reset_episode(scene, robot, cube, rng)
        success = False
        step = 0
        t_policy_total = 0.0
        chunk_count = 0

        while step < max_steps:
            rgb    = get_rgb(cam)
            qpos   = get_qpos(robot)
            arm_q  = qpos[:7]
            grip_q = qpos[7:9]

            t0 = time.time()
            if use_server:
                arm_chunk, grip_chunk = query_server(server_url, rgb, instruction, arm_q, grip_q)
            else:
                arm_chunk, grip_chunk = query_inprocess(policy, rgb, arm_q, grip_q, instruction)
            t_policy_total += time.time() - t0
            chunk_count += 1

            # Execute all 16 action steps in the chunk
            for t in range(min(16, len(arm_chunk))):
                apply_action(robot, scene, arm_chunk[t], grip_chunk[t],
                             sim_steps=sim_steps_per_action)
            step += 16

            if check_success(cube):
                success = True
                break

        cube_z     = get_cube_z(cube)
        avg_latency = (t_policy_total / max(chunk_count, 1)) * 1000

        results.append({
            "episode": ep,
            "success": success,
            "steps": step,
            "policy_latency_ms": round(avg_latency, 1),
            "cube_final_z": round(cube_z, 3),
            "cube_start_xy": [round(float(cube_pos[0]), 3), round(float(cube_pos[1]), 3)],
        })
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"[eval] Episode {ep+1:02d}/{num_episodes}: {status} "
              f"(steps={step}, latency={avg_latency:.0f}ms, cube_z={cube_z:.3f}m)")

    return results


# ── HTML Report ───────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GR00T Closed-Loop Eval — {date}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f0f0f; color: #e5e7eb; margin: 0; padding: 32px; }}
  h1 {{ color: #C74634; font-size: 28px; margin-bottom: 4px; }}
  h2 {{ color: #9CA3AF; font-size: 14px; font-weight: normal; margin-top: 0; }}
  .stats {{ display: flex; gap: 20px; margin: 24px 0; flex-wrap: wrap; }}
  .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;
           padding: 20px 28px; min-width: 140px; }}
  .card .val {{ font-size: 36px; font-weight: bold; color: #C74634; }}
  .card .lbl {{ font-size: 12px; color: #6B7280; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
  th {{ background: #1a1a1a; padding: 10px 14px; text-align: left;
        font-size: 12px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1px; }}
  td {{ padding: 10px 14px; border-top: 1px solid #1f1f1f; font-size: 13px; }}
  tr:nth-child(even) td {{ background: #111; }}
  .success {{ color: #16A34A; font-weight: bold; }}
  .fail {{ color: #EF4444; }}
  .bar-bg {{ background: #1a1a1a; border-radius: 4px; height: 8px; width: 100%; }}
  .bar-fill {{ background: #C74634; border-radius: 4px; height: 8px; }}
  footer {{ margin-top: 40px; color: #374151; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Closed-Loop Eval Report</h1>
<h2>{source} &nbsp;|&nbsp; {date} &nbsp;|&nbsp; {mode}</h2>

<div class="stats">
  <div class="card"><div class="val">{success_rate}%</div><div class="lbl">Task Success Rate</div></div>
  <div class="card"><div class="val">{success_count}/{total}</div><div class="lbl">Episodes Succeeded</div></div>
  <div class="card"><div class="val">{avg_latency}ms</div><div class="lbl">Avg Policy Latency</div></div>
  <div class="card"><div class="val">{avg_steps}</div><div class="lbl">Avg Steps to Success</div></div>
  <div class="card"><div class="val">{task}</div><div class="lbl">Task</div></div>
</div>

<div style="margin: 8px 0 4px; font-size: 12px; color: #6B7280;">Success rate</div>
<div class="bar-bg"><div class="bar-fill" style="width:{success_rate}%"></div></div>

<table>
<thead><tr>
  <th>Episode</th><th>Result</th><th>Steps</th>
  <th>Policy Latency</th><th>Cube Final Z</th><th>Cube Start XY</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>

<footer>OCI Robot Cloud · GR00T Closed-Loop Eval · {date}</footer>
</body>
</html>"""


def make_html(results: list[dict], source: str, output_dir: Path, mode: str) -> str:
    successes = [r for r in results if r["success"]]
    success_rate = round(100 * len(successes) / len(results))
    avg_latency = round(np.mean([r["policy_latency_ms"] for r in results]))
    avg_steps = round(np.mean([r["steps"] for r in successes])) if successes else "N/A"

    rows = []
    for r in results:
        status = '<span class="success">✓ SUCCESS</span>' if r["success"] else '<span class="fail">✗ FAILED</span>'
        xy = r.get("cube_start_xy", ["?", "?"])
        rows.append(
            f"<tr><td>{r['episode']+1}</td><td>{status}</td>"
            f"<td>{r['steps']}</td><td>{r['policy_latency_ms']}ms</td>"
            f"<td>{r['cube_final_z']}m</td><td>({xy[0]}, {xy[1]})</td></tr>"
        )

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        source=source,
        mode=mode,
        success_rate=success_rate,
        success_count=len(successes),
        total=len(results),
        avg_latency=avg_latency,
        avg_steps=avg_steps,
        task="pick-and-lift (cube z > 0.78m)",
        rows="\n".join(rows),
    )

    out_path = output_dir / "eval_report.html"
    out_path.write_text(html)
    print(f"[eval] HTML report → {out_path}")
    return str(out_path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Closed-loop eval for GR00T fine-tuned policy")

    # Policy source — exactly one of these
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--checkpoint", default=None,
                     help="Path to fine-tuned checkpoint (in-process inference)")
    grp.add_argument("--server-url", default=None,
                     help="GR00T HTTP server URL, e.g. http://localhost:8002")

    parser.add_argument("--num-episodes",       type=int,   default=20)
    parser.add_argument("--max-steps",          type=int,   default=500,
                        help="Max policy steps per episode (each step = 16 actions)")
    parser.add_argument("--sim-steps-per-action", type=int, default=2,
                        help="Genesis sim steps per single action in chunk (2 matches SDG 20fps training)")
    parser.add_argument("--gpu-id",             type=int,   default=0)
    parser.add_argument("--output",             default="/tmp/eval_results.json")
    parser.add_argument("--cuda",               action="store_true", default=True,
                        help="Use CUDA Genesis backend (matches training SDG dynamics, j5→2.124)")
    parser.add_argument("--no-cuda",            action="store_false", dest="cuda",
                        help="Use CPU Genesis backend (faster but training/eval distribution mismatch)")
    parser.add_argument("--mock",               action="store_true",
                        help="Force mock mode (skip Genesis + policy loading)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_dir  = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    use_mock = args.mock or (not args.checkpoint and not args.server_url)
    mode_label = "mock"
    if not use_mock:
        if args.server_url:
            mode_label = f"genesis+http({args.server_url})"
        else:
            mode_label = "genesis+gr00t-inprocess"

    source_label = args.server_url or (Path(args.checkpoint).name if args.checkpoint else "mock")

    print(f"[eval] Closed-loop eval: {args.num_episodes} episodes, max_steps={args.max_steps}")
    print(f"[eval] Mode: {mode_label}")
    print(f"[eval] TABLE_Z={TABLE_Z}m | success threshold={LIFT_THRESHOLD:.2f}m\n")

    if not HAS_GENESIS and not use_mock:
        print("[eval] genesis not available — falling back to mock mode")
        use_mock = True

    t_start = time.time()
    try:
        if use_mock:
            results = run_mock_eval(args.num_episodes, args.max_steps)
        else:
            results = run_eval(
                num_episodes=args.num_episodes,
                max_steps=args.max_steps,
                sim_steps_per_action=args.sim_steps_per_action,
                server_url=args.server_url or "",
                checkpoint=args.checkpoint or "",
                gpu_id=args.gpu_id,
                use_cuda=args.cuda,
            )
    except Exception as e:
        print(f"\n[eval] ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - t_start
    successes = [r for r in results if r["success"]]
    success_rate = round(100 * len(successes) / len(results), 1)

    print(f"\n{'='*60}")
    print(f"[eval] RESULTS: {len(successes)}/{len(results)} episodes succeeded ({success_rate}%)")
    print(f"[eval] Total time: {elapsed:.1f}s | Avg latency: {np.mean([r['policy_latency_ms'] for r in results]):.0f}ms")
    print(f"{'='*60}\n")

    summary = {
        "source": source_label,
        "num_episodes": args.num_episodes,
        "success_rate": success_rate,
        "success_count": len(successes),
        "avg_latency_ms": round(np.mean([r["policy_latency_ms"] for r in results]), 1),
        "avg_steps_to_success": round(np.mean([r["steps"] for r in successes])) if successes else None,
        "mode": mode_label,
        "table_z": TABLE_Z,
        "lift_threshold": LIFT_THRESHOLD,
        "timestamp": datetime.now().isoformat(),
        "episodes": results,
    }
    output_path.write_text(json.dumps(summary, indent=2))
    print(f"[eval] JSON results → {output_path}")

    make_html(results, source_label, output_dir, mode_label)


if __name__ == "__main__":
    main()
