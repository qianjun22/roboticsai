"""
LIBERO multi-task demo script.

Cycles through the first 5 tasks in the libero_spatial suite, sending each camera
frame to an inference server and applying the returned 7-dim action directly.
Renders an overlay with task name, instruction, step counter, latency, reward, and
a SUCCESS flash.

Key differences from metaworld_demo.py:
  - Uses LIBERO / robosuite / MuJoCo (matches OpenVLA training domain)
  - 7-dim action space Box(-1, 1, (7,)) — no scaling needed
  - env.step() returns 4-tuple (obs, reward, done, info) — NOT 5-tuple
  - Image obs key: "agentview_image" (256x256x3 uint8, already right-side-up)

Usage:
    # With display (default):
    python src/simulation/libero_demo.py

    # Headless (no window):
    python src/simulation/libero_demo.py --headless

    # Custom server + step count:
    python src/simulation/libero_demo.py --server-url http://my-server:8000 --steps-per-task 60
"""

import argparse
import io
import sys
import time
import warnings

import cv2
import numpy as np
import requests

# ---------------------------------------------------------------------------
# Suppress noisy robosuite warnings at import time
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore")

# Overlay appearance (mirrors metaworld_demo.py)
FONT          = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE    = 0.55
FONT_THICK    = 1
TEXT_COLOR    = (255, 255, 255)
SHADOW_COLOR  = (0, 0, 0)
BAR_COLOR     = (30, 30, 30)
BAR_ALPHA     = 0.55
SUCCESS_COLOR = (0, 255, 80)

NUM_TASKS = 5  # Cycle through first N tasks of libero_spatial


# ---------------------------------------------------------------------------
# Server communication
# ---------------------------------------------------------------------------

def call_server(server_url: str, frame_rgb: np.ndarray, instruction: str) -> tuple:
    """
    POST a JPEG frame + instruction to /predict.
    Returns (7-dim action np.ndarray, latency_ms float).
    Falls back to small random action if server is unreachable.
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
        data    = resp.json()
        raw     = data["action"]          # 7-dim list from OpenVLA
        latency = data.get("latency_ms", (time.perf_counter() - t0) * 1000)
        action  = np.array(raw, dtype=np.float32)
    except Exception as exc:
        print(f"[WARN] Server error: {exc} — using random action", file=sys.stderr)
        action  = np.random.uniform(-0.05, 0.05, size=(7,)).astype(np.float32)
        latency = (time.perf_counter() - t0) * 1000
    return action, latency


# ---------------------------------------------------------------------------
# Overlay rendering
# ---------------------------------------------------------------------------

def draw_overlay(frame_bgr: np.ndarray,
                 task_short: str,
                 instruction: str,
                 step: int,
                 steps_per_task: int,
                 latency_ms: float,
                 reward: float,
                 success: bool,
                 task_idx: int,
                 total_tasks: int) -> np.ndarray:
    """Draw a semi-transparent info bar at the BOTTOM of the frame (preserves full robot view)."""
    img = frame_bgr.copy()
    h, w = img.shape[:2]
    bar_h = 90   # height of the info strip
    bar_y0 = h - bar_h  # top edge of the strip

    # Semi-transparent background bar at bottom
    overlay = img.copy()
    cv2.rectangle(overlay, (0, bar_y0), (w, h), BAR_COLOR, -1)
    cv2.addWeighted(overlay, BAR_ALPHA, img, 1 - BAR_ALPHA, 0, img)

    def put(text, x, y, color=TEXT_COLOR, scale=FONT_SCALE, thick=FONT_THICK):
        cv2.putText(img, text, (x + 1, y + 1), FONT, scale, SHADOW_COLOR, thick + 1, cv2.LINE_AA)
        cv2.putText(img, text, (x, y),           FONT, scale, color,       thick,     cv2.LINE_AA)

    # Line 1: task index + short name
    put(f"Task [{task_idx + 1}/{total_tasks}]: {task_short}", 10, bar_y0 + 22, scale=0.60, thick=2)

    # Line 2: instruction (truncated to fit)
    instr_display = instruction if len(instruction) <= 72 else instruction[:69] + "..."
    put(f"Instr: {instr_display}", 10, bar_y0 + 44, scale=0.45)

    # Line 3: step / latency / reward
    put(f"Step: {step:>3}/{steps_per_task}   Latency: {latency_ms:.0f} ms   Reward: {reward:+.3f}",
        10, bar_y0 + 66)

    # SUCCESS flash (bottom-right)
    if success:
        put("SUCCESS!", w - 110, bar_y0 + 22, color=SUCCESS_COLOR, scale=0.65, thick=2)

    # Progress bar at the very bottom edge
    bar_w = int(w * step / max(steps_per_task, 1))
    cv2.rectangle(img, (0, h - 4), (bar_w, h), (0, 200, 100), -1)

    return img


# ---------------------------------------------------------------------------
# LIBERO environment helpers
# ---------------------------------------------------------------------------

def _find_image_key(obs: dict) -> str | None:
    """Return the key in obs that holds the agent camera image."""
    # Preferred key
    if "agentview_image" in obs:
        return "agentview_image"
    # Fallback: any key ending in '_image'
    for k, v in obs.items():
        if k.endswith("_image") and isinstance(v, np.ndarray) and v.ndim == 3:
            return k
    return None


def make_libero_env(bddl_file: str, seed: int = 42):
    """
    Create and reset an OffScreenRenderEnv for the given BDDL task file.
    Returns (env, obs, action_lo, action_hi).
    """
    from libero.libero.envs import OffScreenRenderEnv

    env = OffScreenRenderEnv(
        bddl_file_name=bddl_file,
        camera_heights=256,
        camera_widths=256,
    )
    obs = env.reset()
    action_lo, action_hi = env.env.action_spec   # Box(-1, 1, (7,))
    return env, obs, action_lo, action_hi


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args):
    print(f"LIBERO multi-task demo | server={args.server_url} "
          f"| steps_per_task={args.steps_per_task} | headless={args.headless}")

    # --- Health check (non-fatal) ---
    try:
        r = requests.get(f"{args.server_url}/health", timeout=3)
        print(f"[OK] Server health: {r.json()}")
    except Exception as exc:
        print(f"[WARN] Server not reachable ({exc}), will use random fallback actions")

    # --- Load task suite ---
    import os
    from libero.libero import benchmark, get_libero_path

    print("[INFO] Loading libero_spatial task suite...")
    benchmark_dict = benchmark.get_benchmark_dict()
    task_suite     = benchmark_dict["libero_spatial"]()
    all_task_names = task_suite.get_task_names()

    # Use first NUM_TASKS tasks
    n_tasks = min(NUM_TASKS, len(all_task_names))
    tasks   = [task_suite.get_task(i) for i in range(n_tasks)]
    print(f"[INFO] Running {n_tasks} tasks from libero_spatial")
    for i, t in enumerate(tasks):
        print(f"  {i}: {t.language}")

    bddl_base = get_libero_path("bddl_files")

    task_idx = 0

    while True:
        task       = tasks[task_idx]
        bddl_file  = os.path.join(bddl_base, task.problem_folder, task.bddl_file)
        instruction = task.language
        # Short display name: first 40 chars of underscored task name
        task_short  = task.name[:40] if len(task.name) > 40 else task.name

        print(f"\n--- Task {task_idx + 1}/{n_tasks}: {task.name} ---")
        print(f"    Instruction: {instruction}")

        # --- Build env ---
        try:
            env, obs, action_lo, action_hi = make_libero_env(bddl_file, seed=args.seed)
        except Exception as exc:
            print(f"[ERROR] Could not create env for {task.name}: {exc}", file=sys.stderr)
            import traceback; traceback.print_exc()
            task_idx = (task_idx + 1) % n_tasks
            continue

        # Find image key dynamically
        img_key = _find_image_key(obs)
        if img_key is None:
            print(f"[WARN] No image key found in obs — keys: {list(obs.keys())}", file=sys.stderr)
            img_key = "agentview_image"   # fallback, will error later if truly absent

        print(f"    image_key={img_key}  image_shape={obs[img_key].shape}")
        print(f"    action_space=Box({action_lo}, {action_hi})  action_dim={len(action_lo)}")

        latency_ms = 0.0
        reward     = 0.0
        success    = False

        for step in range(1, args.steps_per_task + 1):
            # 1. Get camera frame from obs (LIBERO puts image in obs, not via render())
            frame_rgb = obs[img_key]          # (H, W, 3) uint8 RGB
            if frame_rgb is None or frame_rgb.size == 0:
                print(f"[WARN] Empty image at step {step}", file=sys.stderr)
                frame_rgb = np.zeros((256, 256, 3), dtype=np.uint8)

            # 2. Send to inference server → 7-dim action
            action, latency_ms = call_server(args.server_url, frame_rgb, instruction)

            # Clamp to action spec bounds [-1, 1]
            action = np.clip(action, action_lo, action_hi)

            # 3. Step environment (4-tuple — NOT 5-tuple)
            obs, reward, done, info = env.step(action)
            success = bool(info.get("success", False))

            # 4. Render overlay to cv2 window
            if not args.headless:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                # LIBERO (MuJoCo/OpenGL) renders bottom-to-top — flip for display
                frame_bgr = cv2.flip(frame_bgr, 0)
                # Upscale from 256x256 to 512x512 for comfortable viewing
                frame_bgr = cv2.resize(frame_bgr, (512, 512), interpolation=cv2.INTER_LINEAR)
                display   = draw_overlay(
                    frame_bgr, task_short, instruction,
                    step, args.steps_per_task,
                    latency_ms, reward, success,
                    task_idx, n_tasks,
                )
                cv2.imshow("LIBERO Demo", display)
                cv2.moveWindow("LIBERO Demo", 80, 80)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Quit key pressed.")
                    env.close()
                    cv2.destroyAllWindows()
                    return

            if step % 10 == 0 or success:
                print(f"    step={step:>3}  reward={reward:+.3f}  "
                      f"latency={latency_ms:.0f}ms  success={success}")

            if done:
                print(f"    Episode done at step {step}")
                break

        env.close()
        print(f"    Task complete. Final reward={reward:+.3f}  success={success}")

        # Advance to next task, cycling
        task_idx = (task_idx + 1) % n_tasks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="LIBERO multi-task inference demo")
    p.add_argument("--server-url",     default="http://localhost:8000",
                   help="Inference server base URL (default: http://localhost:8000)")
    p.add_argument("--steps-per-task", type=int, default=600,
                   help="Steps to run per task (default: 600 — LIBERO tasks need ~600 steps)")
    p.add_argument("--headless",       action="store_true",
                   help="Disable cv2.imshow rendering (for servers / CI)")
    p.add_argument("--seed",           type=int, default=42,
                   help="Random seed (default: 42)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if not args.headless:
            cv2.destroyAllWindows()

    # Optional: capture a screenshot of the demo window
    import subprocess
    subprocess.run([
        sys.executable, "src/simulation/capture_demo.py",
        "--window", "LIBERO Demo",
        "--out", "/tmp/libero_capture.png",
    ])
