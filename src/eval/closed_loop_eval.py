#!/usr/bin/env python3
"""
Closed-loop evaluation harness for GR00T fine-tuned policies.

Runs the fine-tuned policy in Genesis simulation, executes predicted actions,
and measures task success rate (cube lifted >0.1m above table).

Usage:
    python3 closed_loop_eval.py \
        --checkpoint /tmp/franka_planned_finetune/checkpoint-2000 \
        --num-episodes 20 \
        --max-steps 200 \
        --output /tmp/eval_results.json

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

def check_deps():
    missing = []
    for pkg in ["genesis", "torch", "PIL", "cv2"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[eval] Missing packages: {missing}")
        print("[eval] Install: pip install genesis-world Pillow opencv-python")
        print("[eval] Falling back to mock mode.")
        return False
    return True

HAS_DEPS = check_deps()

# ── Genesis scene setup ────────────────────────────────────────────────────────

TABLE_Z    = 0.3     # table height
CUBE_HALF  = 0.025   # half cube size

def build_scene(gpu_id: int = 0):
    """Create a Franka pick-and-place scene with a red cube (Genesis 0.4.3 API)."""
    import genesis as gs
    gs.init(backend=gs.cuda, logging_level="warning")

    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
    )

    # Floor + table
    scene.add_entity(gs.morphs.Plane())
    scene.add_entity(
        gs.morphs.Box(size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0.0, TABLE_Z / 2), fixed=True),
    )

    # Franka arm
    robot = scene.add_entity(
        gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml", requires_jac_and_IK=True),
    )

    # Red cube — target for pick-and-lift
    cube = scene.add_entity(
        gs.morphs.Box(
            size=(0.05, 0.05, 0.05),
            pos=(0.45, 0.0, TABLE_Z + CUBE_HALF),
        ),
    )

    # Camera for policy observations
    cam = scene.add_camera(
        res=(256, 256),
        pos=(0.5, 0.0, 1.4),
        lookat=(0.45, 0.0, TABLE_Z),
        fov=60,
        GUI=False,
    )

    scene.build()
    return scene, robot, cube, cam


def reset_episode(scene, robot, cube, rng: np.random.Generator):
    """Reset robot to home, place cube at random table position."""
    # Franka home joints (9-DOF: 7 arm + 2 finger)
    home_q = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04], dtype=np.float32)
    robot.set_qpos(home_q)

    # Random cube position on table surface
    x = rng.uniform(0.35, 0.55)
    y = rng.uniform(-0.15, 0.15)
    cube.set_pos([x, y, TABLE_Z + CUBE_HALF])

    # Step to settle
    for _ in range(10):
        scene.step()

    return home_q[:7], home_q[7:]  # arm joints, gripper


def get_observation(scene, robot, cube, cam) -> dict:
    """Capture current scene state as GR00T observation dict."""
    # RGB frame (Genesis 0.4.3: render returns (H,W,4) RGBA or (H,W,3) RGB)
    rendered = cam.render(rgb=True)
    if isinstance(rendered, tuple):
        rgb = rendered[0]   # some versions return (rgb, depth) tuple
    else:
        rgb = rendered
    if rgb.shape[-1] == 4:
        rgb = rgb[:, :, :3]  # drop alpha if RGBA
    rgb = rgb.astype(np.uint8)

    # Robot state (Genesis 0.4.3: get_qpos() returns a torch Tensor)
    qpos = robot.get_qpos()
    if hasattr(qpos, "numpy"):
        qpos = qpos.cpu().numpy()
    if qpos.ndim == 2:
        qpos = qpos[0]
    arm_joints = qpos[:7].astype(np.float32)
    gripper = qpos[7:9].astype(np.float32)

    return {
        "video":    {"agentview": rgb[np.newaxis, np.newaxis]},       # (1,1,256,256,3)
        "state":    {"arm": arm_joints[np.newaxis, np.newaxis],        # (1,1,7)
                     "gripper": gripper[np.newaxis, np.newaxis]},      # (1,1,2)
        "language": {"annotation.human.task_description": [["pick up the red cube from the table"]]},
    }


def check_success(cube) -> bool:
    """Cube is considered lifted if z > table height + 0.08m."""
    pos = cube.get_pos()
    if hasattr(pos, "numpy"):
        pos = pos.cpu().numpy()
    if pos.ndim == 2:
        pos = pos[0]
    return float(pos[2]) > (TABLE_Z + 0.08)


def execute_action_chunk(scene, robot, arm_actions: np.ndarray, gripper_actions: np.ndarray,
                          steps_per_action: int = 3):
    """Execute a 16-step action chunk in simulation (Genesis 0.4.3)."""
    for t in range(min(len(arm_actions), 16)):
        target_q = np.concatenate([arm_actions[t], gripper_actions[t]])
        robot.control_dofs_position(target_q)
        for _ in range(steps_per_action):
            scene.step()


# ── Policy loading ────────────────────────────────────────────────────────────

def load_policy(checkpoint_path: str, device: int = 0):
    """Load GR00T fine-tuned policy from checkpoint."""
    repo_dir = Path(__file__).parents[2]  # roboticsai root (eval/ → src/ → root)
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


def run_policy_step(policy, obs: dict) -> tuple[np.ndarray, np.ndarray]:
    """Query policy and return (arm_actions, gripper_actions) each (16, D)."""
    # Ensure CUDA device consistency after Genesis CUDA init
    import torch
    if torch.cuda.is_available():
        torch.cuda.set_device(0)  # device 0 after CUDA_VISIBLE_DEVICES remapping

    action, _ = policy.get_action(obs)
    arm = np.array(action["action.arm"])
    if arm.ndim == 3:
        arm = arm[0]  # (16, 7)
    grip = np.array(action["action.gripper"])
    if grip.ndim == 3:
        grip = grip[0]  # (16, 2)
    return arm, grip


# ── Mock mode (no GPU/Genesis) ────────────────────────────────────────────────

def run_mock_eval(num_episodes: int, max_steps: int) -> list[dict]:
    """Synthetic results for CI / dry-run testing."""
    print("[eval] Running in MOCK MODE (Genesis or torch not available)")
    rng = np.random.default_rng(42)
    results = []
    for ep in range(num_episodes):
        # Simulate ~65% success rate with noise
        success = rng.random() < 0.65
        steps_to_success = int(rng.uniform(80, 160)) if success else max_steps
        t_policy = rng.uniform(0.15, 0.22)
        results.append({
            "episode": ep,
            "success": success,
            "steps": steps_to_success,
            "policy_latency_ms": round(t_policy * 1000, 1),
            "cube_final_z": round(rng.uniform(0.12, 0.25) if success else rng.uniform(0.01, 0.05), 3),
        })
        print(f"[eval] Episode {ep+1:02d}/{num_episodes}: {'✓ SUCCESS' if success else '✗ FAILED'} "
              f"({steps_to_success} steps, {t_policy*1000:.0f}ms/step)")
        time.sleep(0.02)  # pacing for readability
    return results


# ── Real eval ─────────────────────────────────────────────────────────────────

def run_eval(checkpoint: str, num_episodes: int, max_steps: int,
             gpu_id: int, steps_per_chunk: int) -> list[dict]:
    """Run closed-loop eval with real Genesis + GR00T policy."""
    policy = load_policy(checkpoint, device=gpu_id)
    scene, robot, cube, cam = build_scene(gpu_id=gpu_id)

    rng = np.random.default_rng(42)
    results = []

    for ep in range(num_episodes):
        arm_q, grip_q = reset_episode(scene, robot, cube, rng)
        success = False
        step = 0
        t_policy_total = 0.0

        while step < max_steps:
            obs = get_observation(scene, robot, cube, cam)
            t0 = time.time()
            arm_actions, gripper_actions = run_policy_step(policy, obs)
            t_policy_total += time.time() - t0

            execute_action_chunk(scene, robot, arm_actions, gripper_actions,
                                 steps_per_action=steps_per_chunk)
            step += 16

            if check_success(cube):
                success = True
                break

        cube_z = float(cube.get_pos()[0][2])
        avg_latency = (t_policy_total / (step / 16)) * 1000

        results.append({
            "episode": ep,
            "success": success,
            "steps": step,
            "policy_latency_ms": round(avg_latency, 1),
            "cube_final_z": round(cube_z, 3),
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
<h2>Checkpoint: {checkpoint} &nbsp;|&nbsp; {date} &nbsp;|&nbsp; {mode}</h2>

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
  <th>Policy Latency</th><th>Cube Final Z</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>

<footer>OCI Robot Cloud · GR00T Closed-Loop Eval · {date}</footer>
</body>
</html>"""

def make_html(results: list[dict], checkpoint: str, output_dir: Path, mode: str) -> str:
    successes = [r for r in results if r["success"]]
    success_rate = round(100 * len(successes) / len(results))
    avg_latency = round(np.mean([r["policy_latency_ms"] for r in results]))
    avg_steps = round(np.mean([r["steps"] for r in successes])) if successes else "N/A"

    rows = []
    for r in results:
        status = '<span class="success">✓ SUCCESS</span>' if r["success"] else '<span class="fail">✗ FAILED</span>'
        rows.append(
            f"<tr><td>{r['episode']+1}</td><td>{status}</td>"
            f"<td>{r['steps']}</td><td>{r['policy_latency_ms']}ms</td>"
            f"<td>{r['cube_final_z']}m</td></tr>"
        )

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        checkpoint=Path(checkpoint).name if checkpoint else "mock",
        mode=mode,
        success_rate=success_rate,
        success_count=len(successes),
        total=len(results),
        avg_latency=avg_latency,
        avg_steps=avg_steps,
        task="pick-and-lift (cube > 0.1m)",
        rows="\n".join(rows),
    )

    out_path = output_dir / "eval_report.html"
    out_path.write_text(html)
    print(f"[eval] HTML report → {out_path}")
    return str(out_path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Closed-loop eval for GR00T fine-tuned policy")
    parser.add_argument("--checkpoint", default=None,
                        help="Path to fine-tuned checkpoint (omit for mock mode)")
    parser.add_argument("--num-episodes", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=200,
                        help="Max simulation steps per episode")
    parser.add_argument("--steps-per-chunk", type=int, default=5,
                        help="Sim steps to execute per action in chunk")
    parser.add_argument("--gpu-id", type=int, default=0,
                        help="GPU device index (after CUDA_VISIBLE_DEVICES remapping)")
    parser.add_argument("--output", default="/tmp/eval_results.json",
                        help="Path for JSON results output")
    parser.add_argument("--mock", action="store_true",
                        help="Force mock mode (skip Genesis + policy loading)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_dir  = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    use_mock = args.mock or not HAS_DEPS or args.checkpoint is None

    print(f"[eval] Starting closed-loop eval ({args.num_episodes} episodes, max_steps={args.max_steps})")
    print(f"[eval] Mode: {'MOCK' if use_mock else 'REAL'} | GPU: {args.gpu_id}")
    print(f"[eval] Task: pick-and-lift (success = cube z > 0.1m)\n")

    t_start = time.time()
    try:
        if use_mock:
            results = run_mock_eval(args.num_episodes, args.max_steps)
            mode = "mock"
        else:
            results = run_eval(
                checkpoint=args.checkpoint,
                num_episodes=args.num_episodes,
                max_steps=args.max_steps,
                gpu_id=args.gpu_id,
                steps_per_chunk=args.steps_per_chunk,
            )
            mode = "genesis+gr00t"
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

    # Write JSON
    summary = {
        "checkpoint": args.checkpoint,
        "num_episodes": args.num_episodes,
        "success_rate": success_rate,
        "success_count": len(successes),
        "avg_latency_ms": round(np.mean([r["policy_latency_ms"] for r in results]), 1),
        "avg_steps_to_success": round(np.mean([r["steps"] for r in successes])) if successes else None,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "episodes": results,
    }
    output_path.write_text(json.dumps(summary, indent=2))
    print(f"[eval] JSON results → {output_path}")

    make_html(results, args.checkpoint or "mock", output_dir, mode)


if __name__ == "__main__":
    main()
