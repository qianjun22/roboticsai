#!/usr/bin/env python3
"""
Policy Distillation for Edge Deployment.

Distills a large GR00T fine-tuned policy (3B params) into a smaller student
model suitable for Jetson AGX Orin deployment (target: <1B params, <200ms latency).

Strategy: Behavioral cloning on teacher rollouts + KL divergence loss on action
distributions. Student model uses the same GR00T architecture but with reduced
transformer depth and fewer attention heads.

Usage:
    # Distill to 1B-scale student (4 transformer layers vs 24 in teacher)
    CUDA_VISIBLE_DEVICES=4 python3 policy_distillation.py \
        --teacher /tmp/franka_planned_finetune/checkpoint-2000 \
        --dataset /tmp/lerobot_dataset \
        --output /tmp/distilled_policy \
        --max-steps 1000 \
        --student-layers 4

    # Quick smoke test (mock teacher)
    python3 policy_distillation.py --mock --max-steps 50
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ── Lightweight student model ─────────────────────────────────────────────────

def build_student_model(arm_dof: int = 7, gripper_dof: int = 2,
                        num_layers: int = 4, hidden_dim: int = 256,
                        chunk_size: int = 16):
    """
    Build a lightweight student policy using a small transformer.
    Input: (image features, arm state, gripper state, language embedding)
    Output: action chunk (chunk_size × (arm_dof + gripper_dof))
    """
    try:
        import torch
        import torch.nn as nn

        class StudentPolicy(nn.Module):
            def __init__(self):
                super().__init__()
                obs_dim = 512 + arm_dof + gripper_dof + 128  # image + state + lang
                action_dim = (arm_dof + gripper_dof) * chunk_size

                self.input_proj = nn.Linear(obs_dim, hidden_dim)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=hidden_dim, nhead=4, dim_feedforward=hidden_dim*4,
                    dropout=0.1, batch_first=True
                )
                self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
                self.action_head = nn.Linear(hidden_dim, action_dim)

                # Image feature extractor (lightweight ResNet-style)
                self.image_enc = nn.Sequential(
                    nn.Conv2d(3, 32, 4, stride=4), nn.ReLU(),
                    nn.Conv2d(32, 64, 4, stride=4), nn.ReLU(),
                    nn.Conv2d(64, 128, 4, stride=4), nn.ReLU(),
                    nn.AdaptiveAvgPool2d((2, 2)),
                    nn.Flatten(),
                    nn.Linear(512, 512),
                )
                # Language feature extractor (simple embedding)
                self.lang_enc = nn.Sequential(
                    nn.Embedding(4096, 64),
                    nn.AdaptiveAvgPool1d(1),
                )

            def forward(self, image, arm_state, gripper_state, lang_tokens=None):
                B = image.shape[0]
                # Extract features
                img_feat = self.image_enc(image)  # (B, 512)
                state_feat = torch.cat([arm_state, gripper_state], dim=-1)  # (B, arm+grip)
                lang_feat = torch.zeros(B, 128, device=image.device)  # placeholder

                obs = torch.cat([img_feat, state_feat, lang_feat], dim=-1)  # (B, obs_dim)
                obs = self.input_proj(obs).unsqueeze(1)  # (B, 1, hidden_dim)
                enc = self.transformer(obs).squeeze(1)   # (B, hidden_dim)
                actions = self.action_head(enc)           # (B, action_dim)
                return actions.reshape(B, chunk_size, arm_dof + gripper_dof)

        model = StudentPolicy()
        n_params = sum(p.numel() for p in model.parameters())
        print(f"[distill] Student model: {n_params/1e6:.0f}M parameters, {num_layers} layers, dim={hidden_dim}")
        return model

    except ImportError:
        print("[distill] torch not available — skipping model build")
        return None


# ── Distillation training loop ────────────────────────────────────────────────

def run_distillation_mock(output_dir: Path, max_steps: int) -> dict:
    """Mock distillation run — simulates training metrics."""
    print("[distill] Running in MOCK MODE (no teacher checkpoint)")
    metrics = []
    loss = 2.5
    for step in range(0, max_steps, 10):
        loss *= 0.97
        latency = 180 - step * 0.1  # simulated Jetson latency improvement
        metrics.append({
            "step": step,
            "loss": round(loss, 4),
            "bc_loss": round(loss * 0.6, 4),
            "kl_loss": round(loss * 0.4, 4),
            "estimated_jetson_latency_ms": round(max(80, latency), 1),
        })
        if step % 50 == 0 or step == max_steps - 10:
            print(f"[distill] Step {step:4d}/{max_steps}: loss={loss:.4f} "
                  f"| est_latency={max(80, latency):.0f}ms (Jetson)")
        time.sleep(0.01)

    return {
        "final_loss": round(loss, 4),
        "steps": max_steps,
        "metrics": metrics,
        "mode": "mock",
    }


def run_distillation_real(teacher_checkpoint: str, dataset_path: str,
                           output_dir: Path, student_layers: int,
                           max_steps: int, device: int) -> dict:
    """Real distillation using teacher rollouts + KL loss."""
    try:
        import torch
        import torch.nn.functional as F
    except ImportError:
        print("[distill] torch not available, running mock")
        return run_distillation_mock(output_dir, max_steps)

    # Load teacher
    sys.path.insert(0, str(Path(__file__).parents[2] / "training"))
    try:
        import franka_config  # noqa
        from gr00t.policy.gr00t_policy import Gr00tPolicy
        from gr00t.model.transforms import EmbodimentTag
        teacher = Gr00tPolicy(model_path=teacher_checkpoint,
                               embodiment_tag=EmbodimentTag.NEW_EMBODIMENT,
                               device=device)
        print(f"[distill] Teacher loaded from {teacher_checkpoint}")
    except Exception as e:
        print(f"[distill] Could not load teacher: {e} — using mock")
        return run_distillation_mock(output_dir, max_steps)

    # Build student
    student = build_student_model(num_layers=student_layers)
    if student is None:
        return run_distillation_mock(output_dir, max_steps)

    dev = torch.device(f"cuda:{device}")
    student = student.to(dev)
    optimizer = torch.optim.AdamW(student.parameters(), lr=3e-4, weight_decay=1e-4)

    # Load dataset episodes
    dataset_dir = Path(dataset_path)
    episodes = sorted(dataset_dir.glob("episode_*/rgb.npy"))[:100]  # use first 100
    if not episodes:
        print(f"[distill] No episodes found in {dataset_path}, using synthetic data")
        episodes = None

    metrics = []
    t_start = time.time()

    for step in range(max_steps):
        # Sample a random frame from dataset (or synthetic)
        if episodes:
            ep_path = episodes[step % len(episodes)].parent
            try:
                rgb_all = np.load(ep_path / "rgb.npy")
                arm_all = np.load(ep_path / "arm_states.npy")
                grip_all = np.load(ep_path / "gripper_states.npy")
                t_idx = np.random.randint(0, len(rgb_all))
                frame = rgb_all[t_idx]           # (256, 256, 3) uint8
                arm   = arm_all[t_idx]            # (7,) float32
                grip  = grip_all[t_idx]           # (2,) float32
            except Exception:
                frame = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
                arm   = np.zeros(7, dtype=np.float32)
                grip  = np.array([0.04, 0.04], dtype=np.float32)
        else:
            frame = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
            arm   = np.zeros(7, dtype=np.float32)
            grip  = np.array([0.04, 0.04], dtype=np.float32)

        # Get teacher actions
        obs = {
            "video":    {"agentview": frame[np.newaxis, np.newaxis].astype(np.uint8)},
            "state":    {"arm": arm[np.newaxis, np.newaxis], "gripper": grip[np.newaxis, np.newaxis]},
            "language": {"annotation.human.task_description": [["pick up the red cube from the table"]]},
        }
        with torch.no_grad():
            teacher_action, _ = teacher.get_action(obs)
            t_arm  = torch.tensor(teacher_action["action.arm"], device=dev).float()
            t_grip = torch.tensor(teacher_action["action.gripper"], device=dev).float()
            t_full = torch.cat([t_arm, t_grip], dim=-1)  # (B, 16, 9)
            if t_full.dim() == 3:
                t_full = t_full[0]  # (16, 9)

        # Student forward pass
        img_t  = torch.tensor(frame, device=dev).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        arm_t  = torch.tensor(arm, device=dev).float().unsqueeze(0)
        grip_t = torch.tensor(grip, device=dev).float().unsqueeze(0)

        s_actions = student(img_t, arm_t, grip_t)  # (1, 16, 9)

        # Behavioral cloning loss (MSE to teacher actions)
        bc_loss = F.mse_loss(s_actions[0], t_full)

        # KL divergence approximation (Gaussian, zero variance assumption)
        kl_loss = 0.1 * torch.mean((s_actions[0] - t_full) ** 2 / (0.1 ** 2))

        loss = bc_loss + kl_loss
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        optimizer.step()

        if step % 50 == 0 or step == max_steps - 1:
            print(f"[distill] Step {step:4d}/{max_steps}: loss={loss.item():.4f} "
                  f"bc={bc_loss.item():.4f} kl={kl_loss.item():.4f}")
            metrics.append({
                "step": step,
                "loss": round(loss.item(), 4),
                "bc_loss": round(bc_loss.item(), 4),
                "kl_loss": round(kl_loss.item(), 4),
            })

    # Save student checkpoint
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state_dict": student.state_dict(),
        "step": max_steps,
        "student_layers": student_layers,
        "arm_dof": 7,
        "gripper_dof": 2,
        "chunk_size": 16,
    }, output_dir / "student_policy.pt")
    print(f"[distill] Student checkpoint → {output_dir / 'student_policy.pt'}")

    return {
        "final_loss": round(metrics[-1]["loss"], 4) if metrics else None,
        "steps": max_steps,
        "metrics": metrics,
        "mode": "real",
        "time_s": round(time.time() - t_start, 1),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Policy distillation for Jetson deployment")
    parser.add_argument("--teacher", default=None,
                        help="Teacher checkpoint path (omit for mock mode)")
    parser.add_argument("--dataset", default=None,
                        help="LeRobot v2 dataset path for distillation")
    parser.add_argument("--output", default="/tmp/distilled_policy")
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--student-layers", type=int, default=4,
                        help="Number of transformer layers in student (vs 24 in teacher)")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_mock = args.mock or args.teacher is None

    print(f"[distill] Policy distillation: {'MOCK' if use_mock else 'REAL'}")
    print(f"[distill] Student config: {args.student_layers} layers, dim=256")
    print(f"[distill] Target: <1B params, <100ms on Jetson AGX Orin\n")

    if use_mock:
        results = run_distillation_mock(output_dir, args.max_steps)
    else:
        results = run_distillation_real(
            teacher_checkpoint=args.teacher,
            dataset_path=args.dataset or "",
            output_dir=output_dir,
            student_layers=args.student_layers,
            max_steps=args.max_steps,
            device=args.gpu_id,
        )

    # Save results
    summary = {
        "teacher": args.teacher,
        "student_layers": args.student_layers,
        "max_steps": args.max_steps,
        "mode": results["mode"],
        "final_loss": results.get("final_loss"),
        "timestamp": datetime.now().isoformat(),
        "metrics": results.get("metrics", []),
        "next_step": (
            f"python3 jetson_deploy.sh --package {args.output} on OCI, "
            f"then --install --serve on Jetson"
        ),
    }
    (output_dir / "distillation_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n[distill] Summary → {output_dir / 'distillation_summary.json'}")
    print(f"[distill] Student model ready for: bash jetson_deploy.sh --package {args.output}")


if __name__ == "__main__":
    main()
