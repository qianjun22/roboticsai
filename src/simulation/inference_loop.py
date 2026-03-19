"""
OCI Robot Cloud — Simulation Inference Loop

Connects a LeRobot/MuJoCo simulation environment to the OCI inference API.
At each step:
  1. Capture camera frame from simulation
  2. Send to inference server (real A100 or mock)
  3. Get 7-dim action back
  4. Adapt action to environment's action space
  5. Step simulation, render, repeat

Usage:
    # Development (Mac, no GPU) — start mock server first
    python mock_server.py &
    python inference_loop.py --env pusht

    # With real inference server on A100
    python inference_loop.py --env pusht --server-url http://<OCI_IP>:8000

    # More impressive demo env
    python inference_loop.py --env xarm --server-url http://<OCI_IP>:8000

    # Headless (no display) mode
    python inference_loop.py --env pusht --headless
"""

import argparse
import io
import textwrap
import time
from collections import deque

import cv2
import gymnasium as gym
import gym_pusht  # noqa: F401
import gym_xarm   # noqa: F401
import gym_aloha  # noqa: F401
import httpx
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Supported environments
# ---------------------------------------------------------------------------

ENV_CONFIGS = {
    "pusht": {
        "gym_id": "gym_pusht/PushT-v0",
        "obs_image_key": "pixels",
        "action_dims": 2,
        "instruction": "push the T-shaped block to the target position",
        "action_adapter": "pusht",
    },
    "xarm": {
        "gym_id": "gym_xarm/XarmLift-v0",
        "obs_image_key": "pixels",
        "action_dims": 4,
        "instruction": "lift the object on the table",
        "action_adapter": "xarm",
    },
    "aloha": {
        "gym_id": "gym_aloha/AlohaInsertion-v0",
        "obs_image_key": "pixels",
        "action_dims": 14,
        "instruction": "insert the peg into the socket",
        "action_adapter": "aloha",
    },
}


# ---------------------------------------------------------------------------
# Action adapters — map 7-dim OpenVLA output to each env's action space
# ---------------------------------------------------------------------------

def adapt_action(raw_action: list[float], adapter: str, action_space) -> np.ndarray:
    """
    OpenVLA outputs 7-dim: [dx, dy, dz, droll, dpitch, dyaw, gripper]

    Each environment has a different action space — we map the relevant dims.
    This is intentionally simple for now; will be refined per-env.
    """
    a = np.array(raw_action, dtype=np.float32)
    low, high = action_space.low, action_space.high

    if adapter == "pusht":
        # 2D: use dx, dy as 2D agent velocity
        adapted = a[:2]

    elif adapter == "xarm":
        # 4D: xyz + gripper
        adapted = np.array([a[0], a[1], a[2], a[6]])

    elif adapter == "aloha":
        # 14D bimanual: broadcast single-arm action to both arms
        single_arm = a  # 7-dim
        adapted = np.concatenate([single_arm, single_arm])

    else:
        # Fallback: clip/pad to match action space dims
        n = action_space.shape[0]
        adapted = np.zeros(n, dtype=np.float32)
        adapted[:min(7, n)] = a[:min(7, n)]

    # Clip to valid action range
    return np.clip(adapted, low, high)


# ---------------------------------------------------------------------------
# Inference client
# ---------------------------------------------------------------------------

def call_inference(client: httpx.Client, server_url: str, image: np.ndarray, instruction: str) -> tuple[list[float], float]:
    """Send image + instruction to inference server, return (action, latency_ms)."""
    pil = Image.fromarray(image).convert("RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=90)
    buf.seek(0)

    t0 = time.perf_counter()
    resp = client.post(
        f"{server_url}/predict",
        files={"image": ("frame.jpg", buf, "image/jpeg")},
        data={"instruction": instruction},
        timeout=10.0,
    )
    resp.raise_for_status()
    latency_ms = (time.perf_counter() - t0) * 1000

    data = resp.json()
    return data["action"], latency_ms


# ---------------------------------------------------------------------------
# Overlay / dashboard helpers
# ---------------------------------------------------------------------------

def draw_box(frame, x, y, w, h, alpha=0.5):
    """Draw a semi-transparent dark rectangle on frame (in-place)."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def latency_color(ms: float):
    """BGR color based on latency bucket."""
    if ms < 200:
        return (0, 220, 0)       # green
    elif ms < 400:
        return (0, 200, 220)     # yellow (BGR: swap R/G)
    else:
        return (0, 0, 220)       # red


def draw_sparkline(frame, latencies: list, x: int, y: int, w: int, h: int):
    """Draw a mini bar chart of the last N latency readings in top-right area."""
    if not latencies:
        return
    draw_box(frame, x, y, w, h, alpha=0.55)
    n = len(latencies)
    bar_w = max(1, w // n)
    max_val = max(latencies) if max(latencies) > 0 else 1
    for i, val in enumerate(latencies):
        bar_h = int((val / max_val) * (h - 6))
        bar_h = max(bar_h, 2)
        bx = x + i * bar_w + 1
        by = y + h - bar_h - 2
        color = latency_color(val)
        cv2.rectangle(frame, (bx, by), (bx + bar_w - 1, y + h - 2), color, -1)
    # label
    cv2.putText(frame, "LATENCY", (x + 4, y + 11),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 180), 1, cv2.LINE_AA)


def draw_reward_chart(frame, rewards: list, x: int, y: int, w: int, h: int):
    """Draw a small line chart of episode rewards in bottom-right area."""
    if len(rewards) < 2:
        return
    draw_box(frame, x, y, w, h, alpha=0.55)
    mn, mx = min(rewards), max(rewards)
    span = mx - mn if mx != mn else 1.0
    pts = []
    for i, r in enumerate(rewards):
        px = x + int(i / (len(rewards) - 1) * (w - 4)) + 2
        py = y + h - 4 - int((r - mn) / span * (h - 8))
        pts.append((px, py))
    for i in range(len(pts) - 1):
        cv2.line(frame, pts[i], pts[i + 1], (0, 220, 120), 1, cv2.LINE_AA)
    # label
    cv2.putText(frame, "REWARD", (x + 4, y + 11),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{rewards[-1]:.2f}", (x + 4, y + h - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (0, 220, 120), 1, cv2.LINE_AA)


def render_dashboard(frame: np.ndarray, cfg: dict, step: int, episode: int,
                     latency_ms: float, avg_latency: float, fps: float,
                     total_reward: float, reward: float,
                     latency_history: list, reward_history: list) -> np.ndarray:
    """
    Render the production-style monitoring dashboard onto a copy of frame.
    frame is RGB; returns BGR (ready for cv2.imshow).
    """
    display = frame.copy()
    H, W = display.shape[:2]

    # ── Top-left info panel ────────────────────────────────────────────────
    panel_w = min(320, W - 20)
    instruction = cfg["instruction"]
    # Word-wrap instruction to ~36 chars
    wrapped = textwrap.wrap(instruction, width=36)
    panel_h = 30 + 18 + 18 + len(wrapped) * 16 + 8   # title + model + env + lines
    draw_box(display, 8, 8, panel_w, panel_h, alpha=0.60)

    # Title
    cv2.putText(display, "OCI Robot Cloud", (14, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 220, 60), 2, cv2.LINE_AA)

    ty = 48
    # Model / env row
    model_str = cfg.get("gym_id", "")
    cv2.putText(display, f"model: openvla-7b   env: {model_str}", (14, ty),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 220, 180), 1, cv2.LINE_AA)
    ty += 18
    # Instruction (word-wrapped)
    for line in wrapped:
        cv2.putText(display, line, (14, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)
        ty += 16

    # ── Bottom status bar ──────────────────────────────────────────────────
    bar_h = 26
    draw_box(display, 0, H - bar_h, W, bar_h, alpha=0.65)

    lat_color = latency_color(latency_ms)
    # Items: latency | avg latency | FPS | step | episode reward
    items = [
        (f"lat {latency_ms:.0f}ms", lat_color),
        (f"avg {avg_latency:.0f}ms", (180, 180, 180)),
        (f"fps {fps:.1f}", (180, 220, 255)),
        (f"step {step}", (200, 200, 200)),
        (f"ep {episode}", (200, 200, 200)),
        (f"reward {total_reward:.2f}", (120, 220, 120)),
    ]
    bx = 10
    for text, color in items:
        cv2.putText(display, text, (bx, H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
        (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        bx += tw + 20

    # ── Top-right latency sparkline ────────────────────────────────────────
    spark_w, spark_h = 120, 50
    draw_sparkline(display, latency_history, W - spark_w - 8, 8, spark_w, spark_h)

    # ── Bottom-right reward chart ──────────────────────────────────────────
    chart_w, chart_h = 130, 60
    if len(reward_history) >= 2:
        draw_reward_chart(display, reward_history, W - chart_w - 8, H - bar_h - chart_h - 8,
                          chart_w, chart_h)

    # Convert RGB → BGR for cv2.imshow
    return cv2.cvtColor(display, cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args):
    cfg = ENV_CONFIGS[args.env]
    headless = getattr(args, "headless", False)
    print(f"Environment:  {cfg['gym_id']}")
    print(f"Instruction:  {cfg['instruction']}")
    print(f"Server:       {args.server_url}")
    print(f"Max steps:    {args.max_steps}")
    print(f"Headless:     {headless}")
    print()

    # Build env
    env = gym.make(cfg["gym_id"], obs_type="pixels", render_mode="rgb_array")
    obs, _ = env.reset(seed=42)

    latency_window = deque(maxlen=20)
    reward_history = deque(maxlen=50)
    step = 0
    episode = 0
    total_reward = 0.0

    with httpx.Client() as client:
        # Verify server is up
        try:
            health = client.get(f"{args.server_url}/health", timeout=5).json()
            print(f"Server health: {health['status']} | model={health['model']} | device={health['device']}")
        except Exception as e:
            print(f"WARNING: Could not reach server at {args.server_url}: {e}")
            print("Make sure mock_server.py (or real server) is running.\n")
            return

        print(f"\nStarting inference loop...{' (headless)' if headless else ' (press Q in the render window to quit)'}\n")

        while step < args.max_steps:
            # Get camera frame
            frame = obs[cfg["obs_image_key"]] if isinstance(obs, dict) else env.render()
            if frame is None:
                frame = env.render()

            # Ensure HWC uint8
            if frame.dtype != np.uint8:
                frame = (frame * 255).astype(np.uint8)

            # Call inference API
            try:
                raw_action, latency_ms = call_inference(client, args.server_url, frame, cfg["instruction"])
                latency_window.append(latency_ms)
            except Exception as e:
                print(f"Inference error at step {step}: {e}")
                time.sleep(0.5)
                continue

            # Adapt action to env
            action = adapt_action(raw_action, cfg["action_adapter"], env.action_space)

            # Step environment
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            reward_history.append(reward)
            step += 1

            # Stats
            avg_latency = sum(latency_window) / len(latency_window)
            fps = 1000.0 / avg_latency if avg_latency > 0 else 0

            # Render with overlay (skip entirely in headless mode)
            if not headless:
                render_frame = env.render()
                if render_frame is not None:
                    bgr = render_dashboard(
                        render_frame, cfg,
                        step=step, episode=episode,
                        latency_ms=latency_ms, avg_latency=avg_latency, fps=fps,
                        total_reward=total_reward, reward=reward,
                        latency_history=list(latency_window),
                        reward_history=list(reward_history),
                    )
                    cv2.imshow("OCI Robot Cloud", bgr)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

            # Console log every 10 steps
            if step % 10 == 0:
                print(f"Step {step:4d} | latency={latency_ms:6.1f}ms | avg={avg_latency:6.1f}ms | reward={reward:.3f}")

            # Reset on episode end
            if terminated or truncated:
                episode += 1
                print(f"\nEpisode {episode} done — total_reward={total_reward:.3f}\n")
                obs, _ = env.reset()
                total_reward = 0.0

    env.close()
    if not headless:
        cv2.destroyAllWindows()
    print(f"\nDone. {step} steps, {episode} episodes.")
    if latency_window:
        sorted_l = sorted(latency_window)
        print(f"Latency — p50: {sorted_l[len(sorted_l)//2]:.1f}ms  mean: {sum(sorted_l)/len(sorted_l):.1f}ms")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="OCI Robot Cloud — simulation inference loop")
    p.add_argument("--env", choices=list(ENV_CONFIGS.keys()), default="pusht",
                   help="Simulation environment (default: pusht)")
    p.add_argument("--server-url", default="http://localhost:8000",
                   help="Inference server URL (default: localhost mock)")
    p.add_argument("--max-steps", type=int, default=500,
                   help="Max steps per run (default: 500)")
    p.add_argument("--headless", action="store_true",
                   help="Run without display (skip cv2.imshow/waitKey)")
    args = p.parse_args()
    run(args)
