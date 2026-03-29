#!/usr/bin/env python3
"""
Multi-task evaluation harness for GR00T fine-tuned policies.

Evaluates across 3 canonical manipulation tasks and compares:
  - Task 1: pick-and-lift (cube > 0.1m)
  - Task 2: pick-and-place (cube reaches target zone ±3cm)
  - Task 3: push-to-goal (cube reaches goal via lateral push)

Usage:
    python3 multi_task_eval.py \
        --checkpoint /tmp/franka_planned_finetune/checkpoint-2000 \
        --episodes-per-task 10 \
        --output /tmp/multi_task_eval.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# Reuse closed_loop_eval helpers
sys.path.insert(0, str(Path(__file__).parent))

TASKS = [
    {
        "id": "pick_and_lift",
        "name": "Pick and Lift",
        "instruction": "pick up the red cube from the table",
        "success_fn": "cube_z_above_0.1",
        "threshold": 0.10,
    },
    {
        "id": "pick_and_place",
        "name": "Pick and Place",
        "instruction": "pick up the red cube and place it on the green target",
        "success_fn": "cube_near_target",
        "threshold": 0.03,   # within 3cm of target (0.25, 0.0)
    },
    {
        "id": "push_to_goal",
        "name": "Push to Goal",
        "instruction": "push the red cube to the goal position",
        "success_fn": "cube_near_goal_xy",
        "threshold": 0.05,   # within 5cm of goal (0.3, 0.0)
    },
]


def run_mock_task_eval(task: dict, num_episodes: int, base_success_rate: float = 0.65) -> list[dict]:
    """Mock eval for a single task with realistic variance."""
    rng = np.random.default_rng(hash(task["id"]) % (2**31))
    # Different tasks have different simulated success rates
    sr_map = {"pick_and_lift": 0.65, "pick_and_place": 0.45, "push_to_goal": 0.55}
    sr = sr_map.get(task["id"], base_success_rate)

    results = []
    for ep in range(num_episodes):
        success = rng.random() < sr
        results.append({
            "episode": ep,
            "task": task["id"],
            "success": success,
            "steps": int(rng.uniform(60, 160)) if success else 200,
            "policy_latency_ms": round(rng.uniform(155, 220), 1),
        })
    return results


def run_all_tasks_eval(checkpoint: str, num_episodes: int, gpu_id: int) -> dict:
    """Run real Genesis+GR00T eval across all tasks."""
    try:
        from closed_loop_eval import load_policy, build_scene, reset_episode, \
            get_observation, execute_action_chunk
        import genesis as gs
    except ImportError:
        print("[multi-task] Genesis not available, using mock mode")
        return None

    policy = load_policy(checkpoint, device=gpu_id)
    scene, robot, cube, cam = build_scene(gpu_id=gpu_id)
    rng = np.random.default_rng(42)

    all_results = {}
    for task in TASKS:
        results = []
        print(f"\n[multi-task] === Task: {task['name']} ===")
        for ep in range(num_episodes):
            arm_q, grip_q = reset_episode(scene, robot, cube, rng)

            # Place target marker for pick-and-place task
            target_pos = np.array([0.25, 0.0])
            success = False
            step = 0

            # Patch obs language instruction per task
            while step < 200:
                import genesis as gs
                obs = {
                    "video":    {"agentview": cam.render(rgb=True)[0][np.newaxis, np.newaxis]},
                    "state":    {"arm": robot.get_qpos()[0][:7][np.newaxis, np.newaxis].astype(np.float32),
                                 "gripper": robot.get_qpos()[0][7:9][np.newaxis, np.newaxis].astype(np.float32)},
                    "language": {"annotation.human.task_description": [[task["instruction"]]]},
                }
                from closed_loop_eval import run_policy_step
                arm_a, grip_a = run_policy_step(policy, obs)
                execute_action_chunk(scene, robot, arm_a, grip_a)
                step += 16

                cube_pos = cube.get_pos()[0]
                if task["success_fn"] == "cube_z_above_0.1":
                    success = float(cube_pos[2]) > task["threshold"]
                elif task["success_fn"] == "cube_near_target":
                    dist = float(np.linalg.norm(cube_pos[:2] - target_pos))
                    success = dist < task["threshold"] and float(cube_pos[2]) < 0.05
                elif task["success_fn"] == "cube_near_goal_xy":
                    goal = np.array([0.3, 0.0])
                    dist = float(np.linalg.norm(cube_pos[:2] - goal))
                    success = dist < task["threshold"]

                if success:
                    break

            results.append({"episode": ep, "task": task["id"], "success": success, "steps": step})
            print(f"  Ep {ep+1:02d}: {'✓' if success else '✗'} (steps={step})")

        all_results[task["id"]] = results

    return all_results


def make_multi_task_html(task_results: dict, checkpoint: str, output_dir: Path, mode: str) -> str:
    """Generate comparison HTML report across all tasks."""
    rows_html = ""
    summary_cards = ""

    for task in TASKS:
        results = task_results.get(task["id"], [])
        if not results:
            continue
        successes = [r for r in results if r["success"]]
        sr = round(100 * len(successes) / len(results)) if results else 0

        summary_cards += f"""
        <div class="card">
          <div class="val">{sr}%</div>
          <div class="lbl">{task['name']}</div>
          <div style="margin-top:8px">
            <div class="bar-bg"><div class="bar-fill" style="width:{sr}%"></div></div>
          </div>
        </div>"""

        for r in results:
            status = '<span class="success">✓</span>' if r["success"] else '<span class="fail">✗</span>'
            rows_html += f"<tr><td>{task['name']}</td><td>{r['episode']+1}</td><td>{status}</td><td>{r['steps']}</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Multi-Task Eval — {datetime.now().strftime('%Y-%m-%d')}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f0f0f; color: #e5e7eb; margin: 0; padding: 32px; }}
  h1 {{ color: #C74634; font-size: 28px; margin-bottom: 4px; }}
  h2 {{ color: #9CA3AF; font-size: 14px; font-weight: normal; margin-top: 0; }}
  .stats {{ display: flex; gap: 20px; margin: 24px 0; flex-wrap: wrap; }}
  .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;
           padding: 20px 28px; min-width: 180px; }}
  .card .val {{ font-size: 36px; font-weight: bold; color: #C74634; }}
  .card .lbl {{ font-size: 12px; color: #6B7280; margin-top: 4px; }}
  .bar-bg {{ background: #222; border-radius: 4px; height: 6px; width: 100%; }}
  .bar-fill {{ background: #C74634; border-radius: 4px; height: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
  th {{ background: #1a1a1a; padding: 10px 14px; text-align: left;
        font-size: 12px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1px; }}
  td {{ padding: 10px 14px; border-top: 1px solid #1f1f1f; font-size: 13px; }}
  tr:nth-child(even) td {{ background: #111; }}
  .success {{ color: #16A34A; font-weight: bold; }}
  .fail {{ color: #EF4444; }}
  footer {{ margin-top: 40px; color: #374151; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Multi-Task Evaluation Report</h1>
<h2>Checkpoint: {Path(checkpoint).name if checkpoint else 'mock'} &nbsp;|&nbsp;
    {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; Mode: {mode}</h2>

<div class="stats">{summary_cards}</div>

<table>
<thead><tr>
  <th>Task</th><th>Episode</th><th>Result</th><th>Steps</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>

<footer>OCI Robot Cloud · GR00T Multi-Task Eval · {datetime.now().strftime('%Y-%m-%d')}</footer>
</body>
</html>"""

    out_path = output_dir / "multi_task_eval_report.html"
    out_path.write_text(html)
    print(f"[multi-task] HTML report → {out_path}")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Multi-task closed-loop eval for GR00T")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--episodes-per-task", type=int, default=10)
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--output", default="/tmp/multi_task_eval.json")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_dir  = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    use_mock = args.mock or args.checkpoint is None

    print(f"[multi-task] Evaluating {len(TASKS)} tasks × {args.episodes_per_task} episodes")
    print(f"[multi-task] Mode: {'MOCK' if use_mock else 'REAL'}\n")

    all_results = {}

    if use_mock:
        for task in TASKS:
            print(f"[multi-task] Task: {task['name']}")
            all_results[task["id"]] = run_mock_task_eval(task, args.episodes_per_task)
            successes = sum(1 for r in all_results[task["id"]] if r["success"])
            print(f"  → {successes}/{args.episodes_per_task} succeeded "
                  f"({round(100*successes/args.episodes_per_task)}%)")
        mode = "mock"
    else:
        real = run_all_tasks_eval(args.checkpoint, args.episodes_per_task, args.gpu_id)
        if real is None:
            for task in TASKS:
                all_results[task["id"]] = run_mock_task_eval(task, args.episodes_per_task)
            mode = "mock (genesis unavailable)"
        else:
            all_results = real
            mode = "genesis+gr00t"

    print(f"\n{'='*60}")
    print(f"[multi-task] SUMMARY")
    print(f"{'='*60}")
    for task in TASKS:
        results = all_results.get(task["id"], [])
        sr = round(100 * sum(1 for r in results if r["success"]) / len(results)) if results else 0
        print(f"  {task['name']:20s}: {sr:3d}%")
    print(f"{'='*60}\n")

    summary = {
        "checkpoint": args.checkpoint,
        "episodes_per_task": args.episodes_per_task,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "tasks": {
            task["id"]: {
                "name": task["name"],
                "success_rate": round(100 * sum(1 for r in all_results.get(task["id"], []) if r["success"])
                                      / args.episodes_per_task),
                "episodes": all_results.get(task["id"], []),
            }
            for task in TASKS
        },
    }
    output_path.write_text(json.dumps(summary, indent=2))
    print(f"[multi-task] JSON results → {output_path}")

    make_multi_task_html(all_results, args.checkpoint or "mock", output_dir, mode)


if __name__ == "__main__":
    main()
