"""
Quick environment sanity check — run this before inference_loop.py.
Verifies install, renders a few steps with random actions, reports obs/action shapes.

Usage:
    python test_env.py --env pusht
    python test_env.py --env xarm
    python test_env.py --env aloha
"""

import argparse
import time

import cv2
import gymnasium as gym
import numpy as np

# Register environments by importing their packages
import gym_pusht  # noqa: F401
import gym_xarm  # noqa: F401
import gym_aloha  # noqa: F401

ENV_IDS = {
    "pusht": "gym_pusht/PushT-v0",
    "xarm":  "gym_xarm/XarmLift-v0",
    "aloha": "gym_aloha/AlohaInsertion-v0",
}

def test(env_name: str, steps: int = 100):
    gym_id = ENV_IDS[env_name]
    print(f"Testing {gym_id}...")

    env = gym.make(gym_id, obs_type="pixels", render_mode="rgb_array")
    obs, info = env.reset(seed=0)

    # Print shapes
    if isinstance(obs, dict):
        print("Observation keys:", list(obs.keys()))
        for k, v in obs.items():
            arr = np.array(v)
            print(f"  {k}: shape={arr.shape} dtype={arr.dtype}")
    else:
        print(f"Observation: shape={np.array(obs).shape}")

    print(f"Action space: {env.action_space}")
    print(f"Action shape: {env.action_space.shape}")
    print()

    # Run random steps and display
    t0 = time.perf_counter()
    for i in range(steps):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

        frame = env.render()
        if frame is not None:
            if frame.dtype != np.uint8:
                frame = (frame * 255).astype(np.uint8)
            # Headless mode: skip cv2.imshow (no display available in non-interactive session)
            # cv2.imshow and cv2.waitKey omitted intentionally

        if terminated or truncated:
            obs, info = env.reset()

    elapsed = time.perf_counter() - t0
    print(f"Ran {steps} steps in {elapsed:.2f}s ({steps/elapsed:.1f} steps/sec)")
    print("Environment test passed.")

    env.close()
    # cv2.destroyAllWindows()  # skipped in headless mode


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--env", choices=list(ENV_IDS.keys()), default="pusht")
    p.add_argument("--steps", type=int, default=100)
    args = p.parse_args()
    test(args.env, args.steps)
