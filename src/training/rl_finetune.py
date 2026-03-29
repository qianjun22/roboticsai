#!/usr/bin/env python3
"""
RL Fine-Tuning for GR00T policy using PPO in Genesis simulation.

After open-loop imitation learning (MAE 0.013), this script applies PPO
to maximize closed-loop task success rate (cube lifted > 8cm above table).

The policy network is the fine-tuned GR00T served via HTTP (port 8002).
A lightweight residual action head is trained to correct GR00T's base actions.

Architecture:
  GR00T server (frozen) → base action chunk (16, 9)
                                         ↓
  Residual PPO head (trainable) → delta actions (16, 9)
                                         ↓
  Final action = clip(base + delta, joint_limits)

Usage:
    CUDA_VISIBLE_DEVICES=4 python3 src/training/rl_finetune.py \\
        --server-url http://localhost:8002 \\
        --num-envs 4 \\
        --total-steps 100000 \\
        --output /tmp/rl_residual.pt

References:
    - Schulman et al. 2017 (PPO)
    - Black et al. 2024 (π0 flow matching as RL objective)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

# ── Constants (must match closed_loop_eval.py and genesis_sdg_planned.py) ────

TABLE_Z    = 0.7
CUBE_HALF  = 0.025
LIFT_THRESH = TABLE_Z + 0.08   # 0.78m = success

Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04], dtype=np.float64)
JOINT_LOW  = np.array([-2.9, -1.8, -2.9, -3.1, -2.9, -0.09, -2.9, 0.0, 0.0], dtype=np.float32)
JOINT_HIGH = np.array([ 2.9,  1.8,  2.9, -0.01,  2.9,  3.75,  2.9, 0.08, 0.08], dtype=np.float32)

INSTRUCTION = "pick up the red cube from the table"


# ── Genesis environment ────────────────────────────────────────────────────────

class FrankaPickEnv:
    """
    Single-robot Genesis environment for Franka pick-and-lift.
    Matches the geometry in genesis_sdg_planned.py.
    """

    def __init__(self, seed: int = 0):
        import genesis as gs
        gs.init(backend=gs.cpu, logging_level="warning")

        scene = gs.Scene(
            show_viewer=False,
            renderer=gs.renderers.Rasterizer(),
            sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
        )
        scene.add_entity(gs.morphs.Plane())
        scene.add_entity(
            gs.morphs.Box(size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0.0, TABLE_Z / 2), fixed=True),
        )
        self._cube = scene.add_entity(
            gs.morphs.Box(size=(0.05, 0.05, 0.05), pos=(0.45, 0.0, TABLE_Z + CUBE_HALF)),
        )
        self._robot = scene.add_entity(
            gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml", requires_jac_and_IK=True),
        )
        self._cam = scene.add_camera(
            res=(256, 256),
            pos=(0.5, 0.0, 1.4),
            lookat=(0.45, 0.0, TABLE_Z),
            fov=55,
        )
        scene.build()

        self._scene = scene
        self._rng = np.random.default_rng(seed)
        self.step_count = 0

    def reset(self) -> tuple[np.ndarray, np.ndarray]:
        """Reset scene. Returns (arm_q, grip_q). No camera render for RL speed."""
        self._scene.reset()
        xy = self._rng.uniform(-0.12, 0.12, size=2)
        cube_pos = np.array([0.45 + xy[0], xy[1], TABLE_Z + CUBE_HALF])
        self._cube.set_pos(cube_pos)
        self._cube_start_z = float(TABLE_Z + CUBE_HALF)
        self._robot.set_dofs_position(Q_HOME)
        self._scene.step()
        self.step_count = 0
        return self._get_joint_state()

    def step(self, arm_q: np.ndarray, grip_q: np.ndarray,
             sim_steps: int = 5) -> tuple[np.ndarray, np.ndarray, float, bool]:
        """Apply action. Returns (arm_q, grip_q, reward, done).
        No camera render — uses joint state only for RL residual head."""
        self._robot.control_dofs_position(arm_q.astype(np.float64), dofs_idx_local=list(range(7)))
        self._robot.control_dofs_position(grip_q.astype(np.float64), dofs_idx_local=[7, 8])
        for _ in range(sim_steps):
            self._scene.step()
        self.step_count += 1

        arm_q_new, grip_q_new = self._get_joint_state()
        cube_z = self._get_cube_z()

        # Dense reward: height above table (clipped)
        height_above_table = max(0.0, cube_z - (TABLE_Z + CUBE_HALF))
        reward = float(np.clip(height_above_table / 0.08, 0.0, 1.0))
        if cube_z > LIFT_THRESH:
            reward = 10.0  # large success bonus

        # Done conditions
        done = cube_z > LIFT_THRESH or self.step_count >= 500

        return arm_q_new, grip_q_new, reward, done

    def get_rgb(self) -> np.ndarray:
        """Capture camera frame (called only when needed for GR00T query)."""
        result = self._cam.render(rgb=True, depth=False, segmentation=False, normal=False)
        rgb = result[0] if isinstance(result, (tuple, list)) else result
        if hasattr(rgb, "numpy"): rgb = rgb.cpu().numpy()
        if rgb.ndim == 4: rgb = rgb[0]
        if rgb.shape[-1] == 4: rgb = rgb[:, :, :3]
        return rgb.astype(np.uint8)

    def _get_joint_state(self) -> tuple[np.ndarray, np.ndarray]:
        q = self._robot.get_dofs_position()
        if hasattr(q, "numpy"): q = q.cpu().numpy()
        if q.ndim == 2: q = q[0]
        return q[:7].astype(np.float32), q[7:9].astype(np.float32)

    def _get_cube_z(self) -> float:
        pos = self._cube.get_pos()
        if hasattr(pos, "numpy"): pos = pos.cpu().numpy()
        if hasattr(pos, "ndim") and pos.ndim == 2: pos = pos[0]
        return float(pos[2])


# ── GR00T query (HTTP) ────────────────────────────────────────────────────────

def query_groot(server_url: str, rgb: np.ndarray, instruction: str) -> tuple[np.ndarray, np.ndarray]:
    """Query running GR00T server. Returns (arm_chunk [16,7], grip_chunk [16,2])."""
    from PIL import Image
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    Image.fromarray(rgb).save(tmp.name, quality=90)
    tmp.close()
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{server_url}/predict",
             "-F", f"image=@{tmp.name}", "-F", f"instruction={instruction}"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        return (np.array(data["arm"], dtype=np.float32),
                np.array(data["gripper"], dtype=np.float32))
    finally:
        os.unlink(tmp.name)


# ── Residual PPO head ─────────────────────────────────────────────────────────

class ResidualPPOHead:
    """
    Lightweight PPO actor-critic that outputs residual deltas on top of GR00T actions.
    State: (arm_q [7], grip_q [2]) = 9-dim
    Action: residual delta (9,) — added to GR00T base action
    """

    def __init__(self, lr: float = 3e-4, clip_eps: float = 0.2, entropy_coef: float = 0.01):
        import torch
        import torch.nn as nn

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.clip_eps = clip_eps
        self.entropy_coef = entropy_coef

        # Actor: maps (9,) state → (9,) mean residual
        self.actor = nn.Sequential(
            nn.Linear(9, 128), nn.ReLU(),
            nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, 9), nn.Tanh(),
        ).to(self.device)

        # Critic: maps (9,) state → scalar value
        self.critic = nn.Sequential(
            nn.Linear(9, 128), nn.ReLU(),
            nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, 1),
        ).to(self.device)

        # Create log_std directly on device (nn.Parameter.to() returns non-leaf)
        self.log_std = nn.Parameter(torch.full((9,), -1.0, device=self.device))

        self.opt = torch.optim.Adam(
            list(self.actor.parameters()) + list(self.critic.parameters()) + [self.log_std],
            lr=lr,
        )
        self._torch = torch
        self._nn = nn

    def get_action(self, arm_q: np.ndarray, grip_q: np.ndarray):
        """Sample residual action. Returns (delta_arm [7], delta_grip [2], log_prob, value)."""
        import torch
        state = torch.tensor(np.concatenate([arm_q, grip_q]), dtype=torch.float32).to(self.device)
        with torch.no_grad():
            mean = self.actor(state)
            std  = torch.exp(self.log_std)
            dist = torch.distributions.Normal(mean, std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum()
            value    = self.critic(state).squeeze()

        action_np = action.cpu().numpy()
        # Scale: arm ±0.05 rad per step, gripper ±0.005 m
        delta_arm  = action_np[:7] * 0.05
        delta_grip = action_np[7:] * 0.005
        return delta_arm, delta_grip, float(log_prob), float(value)

    def update(self, rollouts: list[dict], gamma: float = 0.99, lam: float = 0.95,
               epochs: int = 4, batch_size: int = 64) -> dict:
        """PPO update from collected rollouts. Returns loss info."""
        import torch

        # Compute GAE returns
        states, actions, log_probs_old, rewards, values, dones = [], [], [], [], [], []
        for r in rollouts:
            states.append(np.concatenate([r["arm_q"], r["grip_q"]]))
            actions.append(np.concatenate([r["delta_arm"], r["delta_grip"]]))
            log_probs_old.append(r["log_prob"])
            rewards.append(r["reward"])
            values.append(r["value"])
            dones.append(float(r["done"]))

        # Normalize actions back to network scale
        actions_arr = np.array(actions)
        actions_arr[:, :7] /= 0.05
        actions_arr[:, 7:]  /= 0.005

        # GAE
        advantages = []
        gae = 0.0
        next_value = 0.0
        for i in reversed(range(len(rewards))):
            delta = rewards[i] + gamma * next_value * (1 - dones[i]) - values[i]
            gae   = delta + gamma * lam * (1 - dones[i]) * gae
            advantages.insert(0, gae)
            next_value = values[i]
        returns = [adv + val for adv, val in zip(advantages, values)]

        # Tensors
        s  = torch.tensor(np.array(states),    dtype=torch.float32).to(self.device)
        a  = torch.tensor(actions_arr,          dtype=torch.float32).to(self.device)
        lp = torch.tensor(log_probs_old,        dtype=torch.float32).to(self.device)
        R  = torch.tensor(returns,              dtype=torch.float32).to(self.device)
        A  = torch.tensor(advantages,           dtype=torch.float32).to(self.device)
        A  = (A - A.mean()) / (A.std() + 1e-8)

        total_loss = 0.0
        for _ in range(epochs):
            idx = torch.randperm(len(s))
            for start in range(0, len(s), batch_size):
                b = idx[start:start + batch_size]
                mean_b   = self.actor(s[b])
                std_b    = torch.exp(self.log_std)
                dist_b   = torch.distributions.Normal(mean_b, std_b)
                log_prob_b = dist_b.log_prob(a[b]).sum(-1)
                entropy_b  = dist_b.entropy().sum(-1).mean()
                ratio      = torch.exp(log_prob_b - lp[b])

                # Clipped policy loss
                p_loss  = -torch.min(ratio * A[b],
                                     torch.clamp(ratio, 1 - self.clip_eps, 1 + self.clip_eps) * A[b]).mean()
                # Value loss
                v_pred  = self.critic(s[b]).squeeze()
                v_loss  = 0.5 * (v_pred - R[b]).pow(2).mean()
                # Total
                loss = p_loss + v_loss - self.entropy_coef * entropy_b
                self.opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    list(self.actor.parameters()) + list(self.critic.parameters()),
                    max_norm=0.5,
                )
                self.opt.step()
                total_loss += loss.item()

        return {"loss": total_loss / (epochs * max(1, len(s) // batch_size))}

    def save(self, path: str):
        import torch
        torch.save({
            "actor":  self.actor.state_dict(),
            "critic": self.critic.state_dict(),
            "log_std": self.log_std.data,
        }, path)
        print(f"[rl] Residual head saved → {path}")

    def load(self, path: str):
        import torch
        ckpt = torch.load(path, map_location=self.device)
        self.actor.load_state_dict(ckpt["actor"])
        self.critic.load_state_dict(ckpt["critic"])
        self.log_std.data = ckpt["log_std"]


# ── Training loop ─────────────────────────────────────────────────────────────

def train(server_url: str, total_steps: int, rollout_steps: int, output: str,
          seed: int = 42, sim_steps_per_action: int = 5):

    env  = FrankaPickEnv(seed=seed)
    head = ResidualPPOHead()

    arm_q, grip_q = env.reset()
    episode_reward = 0.0
    episode_count  = 0
    success_count  = 0
    rollout = []
    step = 0

    # Cache GR00T query to avoid per-step HTTP overhead.
    # Refresh every N steps or on episode reset.
    GROOT_REFRESH = 16   # query GR00T once per action chunk
    _arm_chunk  = np.tile(Q_HOME[:7].astype(np.float32), (16, 1))
    _grip_chunk = np.tile(Q_HOME[7:9].astype(np.float32), (16, 1))
    _groot_step = 0

    print(f"[rl] Starting PPO residual training: total_steps={total_steps}, rollout={rollout_steps}")
    print(f"[rl] GR00T server: {server_url}")
    print(f"[rl] Output: {output}\n")
    print(f"[rl] Note: camera render called every {GROOT_REFRESH} steps for GR00T query")

    t0 = time.time()
    last_log = 0

    while step < total_steps:
        # Refresh GR00T action chunk every GROOT_REFRESH steps
        if _groot_step % GROOT_REFRESH == 0:
            try:
                rgb = env.get_rgb()   # camera render only here, not every step
                arm_ch, grip_ch = query_groot(server_url, rgb, INSTRUCTION)
                _arm_chunk  = arm_ch
                _grip_chunk = grip_ch
            except Exception as e:
                pass  # keep previous chunk

        chunk_idx = _groot_step % GROOT_REFRESH
        base_arm  = _arm_chunk[min(chunk_idx, len(_arm_chunk) - 1)]
        base_grip = _grip_chunk[min(chunk_idx, len(_grip_chunk) - 1)]
        _groot_step += 1

        # Query residual head
        delta_arm, delta_grip, log_prob, value = head.get_action(arm_q, grip_q)

        # Apply base action + residual
        final_arm  = np.clip(base_arm  + delta_arm,  JOINT_LOW[:7],  JOINT_HIGH[:7])
        final_grip = np.clip(base_grip + delta_grip, JOINT_LOW[7:9], JOINT_HIGH[7:9])

        # Step environment (no camera render)
        arm_q, grip_q, reward, done = env.step(
            final_arm, final_grip, sim_steps=sim_steps_per_action,
        )
        episode_reward += reward
        step += 1

        rollout.append({
            "arm_q":     arm_q.copy(),
            "grip_q":    grip_q.copy(),
            "delta_arm": delta_arm,
            "delta_grip": delta_grip,
            "log_prob":  log_prob,
            "value":     value,
            "reward":    reward,
            "done":      done,
        })

        if done:
            if reward >= 10.0:
                success_count += 1
            episode_count += 1
            arm_q, grip_q = env.reset()
            _groot_step = 0  # force GR00T refresh on new episode
            episode_reward = 0.0

        # PPO update every rollout_steps
        if len(rollout) >= rollout_steps:
            info = head.update(rollout)
            rollout = []

            if step - last_log >= rollout_steps:
                elapsed = time.time() - t0
                sr = 100.0 * success_count / max(1, episode_count)
                print(f"[rl] step={step:6d}/{total_steps} | "
                      f"episodes={episode_count:4d} | "
                      f"success_rate={sr:.1f}% | "
                      f"loss={info['loss']:.4f} | "
                      f"elapsed={elapsed:.0f}s")
                last_log = step

    # Save residual head
    head.save(output)

    # Final eval
    print(f"\n[rl] Training complete. Running 10-episode eval...")
    success = 0
    for _ in range(10):
        arm_q, grip_q = env.reset()
        done = False
        _arm_ch = np.tile(Q_HOME[:7].astype(np.float32), (16, 1))
        _grip_ch = np.tile(Q_HOME[7:9].astype(np.float32), (16, 1))
        t = 0
        while not done:
            if t % GROOT_REFRESH == 0:
                try:
                    rgb = env.get_rgb()
                    _arm_ch, _grip_ch = query_groot(server_url, rgb, INSTRUCTION)
                except Exception:
                    pass
            idx = t % GROOT_REFRESH
            delta_arm, delta_grip, _, _ = head.get_action(arm_q, grip_q)
            final_arm  = np.clip(_arm_ch[min(idx, 15)]  + delta_arm,  JOINT_LOW[:7],  JOINT_HIGH[:7])
            final_grip = np.clip(_grip_ch[min(idx, 15)] + delta_grip, JOINT_LOW[7:9], JOINT_HIGH[7:9])
            arm_q, grip_q, reward, done = env.step(final_arm, final_grip)
            t += 1
            if reward >= 10.0:
                success += 1
                break

    print(f"[rl] Final eval: {success}/10 success ({success*10:.0f}%)")
    return success


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PPO residual fine-tuning for GR00T")
    parser.add_argument("--server-url", default="http://localhost:8002",
                        help="Running GR00T HTTP server URL")
    parser.add_argument("--total-steps",   type=int, default=50000)
    parser.add_argument("--rollout-steps", type=int, default=512,
                        help="Steps per PPO rollout batch")
    parser.add_argument("--sim-steps-per-action", type=int, default=5)
    parser.add_argument("--seed",  type=int, default=42)
    parser.add_argument("--output", default="/tmp/rl_residual.pt",
                        help="Output path for residual head checkpoint")
    args = parser.parse_args()

    train(
        server_url=args.server_url,
        total_steps=args.total_steps,
        rollout_steps=args.rollout_steps,
        output=args.output,
        seed=args.seed,
        sim_steps_per_action=args.sim_steps_per_action,
    )


if __name__ == "__main__":
    main()
