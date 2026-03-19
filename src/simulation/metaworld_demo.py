"""
MetaWorld multi-task demo script.

Cycles through 6 MetaWorld tasks, sending each camera frame to an inference
server and applying the returned action. Renders an overlay with task name,
instruction, step counter, latency, and reward.

Usage:
    # With display (default):
    python metaworld_demo.py

    # Headless (no window):
    python metaworld_demo.py --headless

    # Custom server + step count:
    python metaworld_demo.py --server-url http://my-server:8000 --steps-per-task 60
"""

import argparse
import io
import random
import sys
import time

import cv2
import numpy as np
import requests

# ---------------------------------------------------------------------------
# Task definitions — using MetaWorld v3 naming
# ---------------------------------------------------------------------------
TASKS = [
    ("reach-v3",                        "reach the target position"),
    ("push-v3",                         "push the puck to the goal"),
    ("pick-place-v3",                   "pick up the object and place it at the goal"),
    ("door-open-v3",                    "open the door handle"),
    ("drawer-open-v3",                  "pull the drawer open"),
    ("button-press-topdown-v3",         "press the button down"),
]

# Overlay appearance
FONT          = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE    = 0.55
FONT_THICK    = 1
TEXT_COLOR    = (255, 255, 255)
SHADOW_COLOR  = (0, 0, 0)
BAR_COLOR     = (30, 30, 30)
BAR_ALPHA     = 0.55
SUCCESS_COLOR = (0, 255, 80)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def adapt_7dim_to_4dim(raw: list[float]) -> np.ndarray:
    """Map 7-dim OpenVLA action [dx,dy,dz,droll,dpitch,dyaw,gripper] → 4-dim MetaWorld [dx,dy,dz,gripper]."""
    return np.array([raw[0], raw[1], raw[2], raw[6]], dtype=np.float32)


def call_server(server_url: str, frame_rgb: np.ndarray, instruction: str) -> tuple[np.ndarray, float]:
    """
    POST a JPEG frame + instruction to /predict.
    Returns (4-dim action, latency_ms).
    Falls back to a small random action if the server is unreachable.
    """
    _, buf = cv2.imencode(".jpg", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            f"{server_url}/predict",
            files={"image": ("frame.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")},
            data={"instruction": instruction},
            timeout=5.0,
        )
        resp.raise_for_status()
        data      = resp.json()
        raw       = data["action"]          # 7-dim
        latency   = data.get("latency_ms", (time.perf_counter() - t0) * 1000)
        action    = adapt_7dim_to_4dim(raw)
    except Exception as exc:
        print(f"[WARN] Server error: {exc} — using random action", file=sys.stderr)
        action  = np.random.uniform(-0.1, 0.1, size=(4,)).astype(np.float32)
        latency = (time.perf_counter() - t0) * 1000
    return action, latency


def draw_overlay(frame_bgr: np.ndarray,
                 task_name: str,
                 instruction: str,
                 step: int,
                 steps_per_task: int,
                 latency_ms: float,
                 reward: float,
                 success: bool,
                 task_idx: int,
                 total_tasks: int) -> np.ndarray:
    """Draw a semi-transparent info bar at the top of the frame."""
    img = frame_bgr.copy()
    h, w = img.shape[:2]
    bar_h = 100

    # Semi-transparent background bar
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), BAR_COLOR, -1)
    cv2.addWeighted(overlay, BAR_ALPHA, img, 1 - BAR_ALPHA, 0, img)

    def put(text, x, y, color=TEXT_COLOR, scale=FONT_SCALE, thick=FONT_THICK):
        # Drop-shadow
        cv2.putText(img, text, (x + 1, y + 1), FONT, scale, SHADOW_COLOR, thick + 1, cv2.LINE_AA)
        cv2.putText(img, text, (x, y),           FONT, scale, color,       thick,     cv2.LINE_AA)

    # Line 1: task name + progress
    put(f"Task [{task_idx + 1}/{total_tasks}]: {task_name}", 10, 22, scale=0.65, thick=2)

    # Line 2: instruction
    put(f"Instr: {instruction}", 10, 46)

    # Line 3: step + latency
    put(f"Step: {step:>3}/{steps_per_task}   Latency: {latency_ms:.0f} ms   Reward: {reward:+.3f}",
        10, 70)

    # Line 4: success tag (if achieved)
    if success:
        put("SUCCESS!", w - 110, 22, color=SUCCESS_COLOR, scale=0.65, thick=2)

    # Progress bar along the bottom of the overlay
    bar_y = bar_h - 6
    bar_w = int(w * step / max(steps_per_task, 1))
    cv2.rectangle(img, (0, bar_y), (bar_w, bar_h - 2), (0, 200, 100), -1)

    return img


def make_env(task_name: str, seed: int = 42):
    """Create and reset a MetaWorld ML1 environment for the given v3 task name."""
    import metaworld
    ml1      = metaworld.ML1(task_name, seed=seed)
    env_cls  = ml1.train_classes[task_name]
    env      = env_cls(render_mode="rgb_array")
    task     = random.choice(ml1.train_tasks)
    env.set_task(task)
    obs, info = env.reset()
    return env, obs, info


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args):
    print(f"MetaWorld multi-task demo | server={args.server_url} | steps_per_task={args.steps_per_task} | headless={args.headless}")

    # Verify server health (non-fatal)
    try:
        r = requests.get(f"{args.server_url}/health", timeout=3)
        print(f"[OK] Server health: {r.json()}")
    except Exception as exc:
        print(f"[WARN] Server not reachable ({exc}), will use random fallback actions")

    task_idx = 0
    total_tasks = len(TASKS)

    while True:
        task_name, instruction = TASKS[task_idx]
        print(f"\n--- Task {task_idx + 1}/{total_tasks}: {task_name} ---")
        print(f"    Instruction: {instruction}")

        # Build env
        try:
            env, obs, _ = make_env(task_name, seed=args.seed)
        except Exception as exc:
            print(f"[ERROR] Could not create env for {task_name}: {exc}", file=sys.stderr)
            task_idx = (task_idx + 1) % total_tasks
            continue

        # Introspect shapes once
        print(f"    obs shape={obs.shape}  action_space={env.action_space}")

        latency_ms = 0.0
        reward     = 0.0
        success    = False

        for step in range(1, args.steps_per_task + 1):
            # 1. Get camera frame
            frame_rgb = env.render()          # HxWx3 uint8, RGB
            if frame_rgb is None:
                print(f"[WARN] env.render() returned None at step {step}", file=sys.stderr)
                frame_rgb = np.zeros((480, 480, 3), dtype=np.uint8)

            # 2. Send to inference server
            action, latency_ms = call_server(args.server_url, frame_rgb, instruction)

            # Clamp to action space bounds
            lo = env.action_space.low
            hi = env.action_space.high
            action = np.clip(action, lo, hi)

            # 3. Step environment
            obs, reward, terminated, truncated, info = env.step(action)
            success = bool(info.get("success", False))

            # 4. Render overlay
            if not args.headless:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                display   = draw_overlay(
                    frame_bgr, task_name, instruction,
                    step, args.steps_per_task,
                    latency_ms, reward, success,
                    task_idx, total_tasks,
                )
                cv2.imshow("MetaWorld Demo", display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Quit key pressed.")
                    env.close()
                    cv2.destroyAllWindows()
                    return

            if step % 10 == 0 or success:
                print(f"    step={step:>3}  reward={reward:+.3f}  latency={latency_ms:.0f}ms  success={success}")

            if terminated or truncated:
                print(f"    Episode ended at step {step} (terminated={terminated}, truncated={truncated})")
                break

        env.close()
        print(f"    Task complete. Final reward={reward:+.3f}  success={success}")

        # Advance to next task, looping back to first
        task_idx = (task_idx + 1) % total_tasks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="MetaWorld multi-task inference demo")
    p.add_argument("--server-url",     default="http://localhost:8000",
                   help="Inference server base URL (default: http://localhost:8000)")
    p.add_argument("--steps-per-task", type=int, default=60,
                   help="Number of steps to run per task (default: 60)")
    p.add_argument("--headless",       action="store_true",
                   help="Disable cv2.imshow rendering (for servers / CI)")
    p.add_argument("--seed",           type=int, default=42,
                   help="Random seed for task sampling (default: 42)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if not args.headless:
            cv2.destroyAllWindows()
