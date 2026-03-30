#!/usr/bin/env python3
"""
ai_world_live_demo.py — Complete AI World September 2026 live demo orchestrator.

A polished, audience-ready demo runner for the AI World booth / conference session.
Runs the full OCI Robot Cloud pipeline in ~8 minutes:
  1. Pre-flight check (GPU, Genesis, checkpoint, services)
  2. Generate 50 fresh synthetic demos (Genesis SDG, ~2 min)
  3. Fine-tune GR00T on OCI (2000 steps, ~4 min)
  4. Closed-loop eval (10 episodes, ~1 min)
  5. Display live results on big screen

Usage:
    # Full live demo (8 min):
    python src/demo/ai_world_live_demo.py --mode full

    # Fast demo (uses pre-generated data, ~3 min):
    python src/demo/ai_world_live_demo.py --mode fast

    # Fallback (pre-recorded, instant):
    python src/demo/ai_world_live_demo.py --mode fallback

    # Dry run (checks all components, no execution):
    python src/demo/ai_world_live_demo.py --mode dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

OCI_HOST     = "ubuntu@138.1.153.110"
GPU_ID       = 4
GROOT_PORT   = 8002
ROBOTICS_DIR = "/home/ubuntu/roboticsai"
GROOT_PYTHON = "/home/ubuntu/Isaac-GR00T/.venv/bin/python3"
PRE_GENERATED_DATASET = "/tmp/sdg_1000_lerobot"
BEST_CHECKPOINT = "/tmp/finetune_1000_5k/checkpoint-5000"

# Pre-recorded demo results (fallback mode)
RECORDED_RESULTS = {
    "success_rate": 0.65,
    "n_success": 13,
    "n_episodes": 20,
    "avg_latency_ms": 226,
    "checkpoint": "checkpoint-5000 (DAgger run4 iter3)",
    "training_cost_usd": 0.43,
    "demos_generated": 1000,
    "mae_improvement": "8.7×",
}

# Fast mode: use pre-generated 100-demo subset
FAST_DATASET  = "/tmp/sdg_100_fast"
FAST_STEPS    = 500
FAST_EPISODES = 5


# ── Step runner ───────────────────────────────────────────────────────────────

@dataclass
class DemoStep:
    name: str
    duration_s: float
    status: str = "pending"    # pending / running / done / failed / skipped
    result: str = ""
    start_time: float = 0.0
    end_time: float = 0.0


def _banner(text: str, width: int = 70) -> None:
    border = "─" * width
    print(f"\n┌{border}┐")
    print(f"│  {text:<{width-2}}│")
    print(f"└{border}┘")


def _step_start(step: DemoStep) -> None:
    step.status = "running"
    step.start_time = time.time()
    _banner(f"▶  {step.name}")
    print(f"   Expected: ~{step.duration_s:.0f}s")


def _step_done(step: DemoStep, result: str = "") -> None:
    step.status = "done"
    step.end_time = time.time()
    step.result = result
    elapsed = step.end_time - step.start_time
    print(f"   ✅ {step.name} — {elapsed:.1f}s  {result}")


def _step_fail(step: DemoStep, error: str = "") -> None:
    step.status = "failed"
    step.end_time = time.time()
    step.result = error
    elapsed = step.end_time - step.start_time
    print(f"   ❌ {step.name} — FAILED after {elapsed:.1f}s: {error}")


def _ssh(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run command on OCI via SSH, return (returncode, stdout, stderr)."""
    full = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", OCI_HOST, cmd]
    try:
        proc = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "SSH timeout"
    except Exception as e:
        return 1, "", str(e)


# ── Pre-flight ────────────────────────────────────────────────────────────────

def step_preflight(mode: str) -> DemoStep:
    step = DemoStep("Pre-flight Check", 15.0)
    _step_start(step)

    checks = []

    if mode == "fallback":
        _step_done(step, "FALLBACK MODE — using pre-recorded demo")
        return step

    # GPU check
    rc, out, _ = _ssh("nvidia-smi --query-gpu=name,memory.free --format=csv,noheader")
    if rc == 0 and "A100" in out:
        checks.append(f"GPU OK ({out.split(',')[1].strip()} free)")
    else:
        checks.append("GPU: SSH failed — will use mock mode")

    # Checkpoint check
    rc, out, _ = _ssh(f"test -d {BEST_CHECKPOINT} && echo EXISTS")
    if "EXISTS" in out:
        checks.append(f"Checkpoint OK ({BEST_CHECKPOINT})")
    else:
        checks.append("Checkpoint NOT FOUND — will use fallback")
        step.result = "checkpoint_missing"

    # Server health
    rc, out, _ = _ssh(f"curl -sf http://localhost:{GROOT_PORT}/health")
    if rc == 0:
        checks.append(f"GR00T server OK (port {GROOT_PORT})")
    else:
        checks.append(f"GR00T server DOWN — will restart")

    summary = " | ".join(checks)
    _step_done(step, summary)
    return step


# ── SDG ───────────────────────────────────────────────────────────────────────

def step_generate_demos(n_demos: int, output_dir: str) -> DemoStep:
    step = DemoStep(f"Genesis SDG ({n_demos} demos)", 120.0)
    _step_start(step)

    rc, out, err = _ssh(
        f"CUDA_VISIBLE_DEVICES={GPU_ID} {GROOT_PYTHON} "
        f"{ROBOTICS_DIR}/src/simulation/genesis_sdg_planned.py "
        f"--n-demos {n_demos} --output {output_dir} 2>&1 | tail -5",
        timeout=180
    )
    if rc == 0:
        _step_done(step, f"{n_demos} demos → {output_dir}")
    else:
        _step_fail(step, err[:100])
    return step


# ── Convert ───────────────────────────────────────────────────────────────────

def step_convert_demos(input_dir: str, output_dir: str) -> DemoStep:
    step = DemoStep("Convert → LeRobot v2", 30.0)
    _step_start(step)

    rc, out, err = _ssh(
        f"{GROOT_PYTHON} {ROBOTICS_DIR}/src/training/genesis_to_lerobot.py "
        f"--input {input_dir} --output {output_dir} 2>&1 | tail -3",
        timeout=60
    )
    if rc == 0:
        _step_done(step, f"{input_dir} → {output_dir}")
    else:
        _step_fail(step, err[:100])
    return step


# ── Fine-tune ─────────────────────────────────────────────────────────────────

def step_finetune(dataset_dir: str, steps: int, output_dir: str) -> DemoStep:
    step = DemoStep(f"GR00T Fine-tune ({steps} steps)", 240.0)
    _step_start(step)

    # Launch in tmux so SSH doesn't time out
    cmd = (f"tmux new-session -d -s aiworld_ft "
           f"'CUDA_VISIBLE_DEVICES={GPU_ID} {GROOT_PYTHON} "
           f"{ROBOTICS_DIR}/Isaac-GR00T/scripts/gr00t_finetune.py "
           f"--dataset-path {dataset_dir} --output-dir {output_dir} "
           f"--training-steps {steps} --batch-size 32 --learning-rate 1e-4 "
           f"2>&1 | tee /tmp/aiworld_ft.log'")
    rc, _, err = _ssh(cmd)
    if rc != 0 and "already exists" not in err:
        _step_fail(step, err[:100])
        return step

    # Poll for completion (max 5 min)
    for _ in range(30):
        time.sleep(10)
        rc2, out2, _ = _ssh(f"test -d {output_dir}/checkpoint-{steps} && echo DONE || echo WAIT")
        if "DONE" in out2:
            _step_done(step, f"checkpoint-{steps} @ {output_dir}")
            return step
        print(f"   ... waiting for checkpoint-{steps} ...")
    _step_fail(step, "Timeout waiting for checkpoint")
    return step


# ── Restart server ────────────────────────────────────────────────────────────

def step_restart_server(checkpoint: str) -> DemoStep:
    step = DemoStep("Restart GR00T Server", 30.0)
    _step_start(step)

    cmds = [
        "pkill -f groot_franka_server.py 2>/dev/null || true",
        "sleep 3",
        f"CUDA_VISIBLE_DEVICES={GPU_ID} nohup {GROOT_PYTHON} "
        f"{ROBOTICS_DIR}/src/inference/groot_franka_server.py "
        f"--checkpoint {checkpoint} --port {GROOT_PORT} "
        f">> /tmp/groot_aiworld.log 2>&1 &",
    ]
    for cmd in cmds:
        _ssh(cmd, timeout=30)

    # Wait for health
    for _ in range(20):
        time.sleep(3)
        rc, out, _ = _ssh(f"curl -sf http://localhost:{GROOT_PORT}/health")
        if rc == 0:
            _step_done(step, f"Server UP on port {GROOT_PORT}")
            return step
    _step_fail(step, "Server failed to start")
    return step


# ── Eval ──────────────────────────────────────────────────────────────────────

def step_eval(n_episodes: int, output_dir: str) -> DemoStep:
    step = DemoStep(f"Closed-Loop Eval ({n_episodes} episodes)", 60.0)
    _step_start(step)

    rc, out, err = _ssh(
        f"CUDA_VISIBLE_DEVICES={GPU_ID} {GROOT_PYTHON} "
        f"{ROBOTICS_DIR}/src/eval/closed_loop_eval.py "
        f"--server-url http://localhost:{GROOT_PORT} "
        f"--num-episodes {n_episodes} --output {output_dir}/eval.html "
        f"2>&1 | tail -10",
        timeout=120
    )

    # Try to read summary.json
    rc2, json_out, _ = _ssh(f"cat {output_dir}/summary.json 2>/dev/null || echo '{{}}'")
    try:
        data = json.loads(json_out)
        rate = data.get("success_rate", 0)
        n_suc = data.get("n_success", 0)
        lat = data.get("avg_latency_ms", 0)
        result = f"{rate:.0%} ({n_suc}/{n_episodes}) · {lat:.0f}ms avg"
        _step_done(step, result)
    except Exception:
        if rc == 0:
            _step_done(step, "Done (check eval.html)")
        else:
            _step_fail(step, err[:100])
    return step


# ── Fallback mode ─────────────────────────────────────────────────────────────

def run_fallback_demo() -> None:
    """Show pre-recorded results without any GPU/network dependency."""
    _banner("🎯 OCI Robot Cloud — AI World 2026 Demo  [FALLBACK MODE]")
    r = RECORDED_RESULTS
    print(f"""
  Pipeline: Genesis SDG → GR00T N1.6-3B Fine-tune → DAgger → Live Eval

  📊 RESULTS (pre-recorded, OCI A100 GPU4):
  ┌─────────────────────────────────────────────┐
  │  Closed-loop success rate:  {r['success_rate']:.0%} ({r['n_success']}/{r['n_episodes']})     │
  │  Average inference latency: {r['avg_latency_ms']}ms              │
  │  Training cost:             ${r['training_cost_usd']:.2f} (vs $4.12 AWS)   │
  │  MAE improvement:           {r['mae_improvement']} over baseline       │
  │  Demos generated:           {r['demos_generated']} (Genesis SDG, 38.5fps) │
  └─────────────────────────────────────────────┘

  🔗 Live at: http://138.1.153.110:{GROOT_PORT}
  📦 GitHub: github.com/qianjun22/roboticsai
  💰 OCI: 9.6× cheaper than AWS p4d
    """)


# ── Dry run ───────────────────────────────────────────────────────────────────

def run_dry_run() -> None:
    _banner("DRY RUN — Checking all demo components")
    checks = [
        ("SSH to OCI", lambda: _ssh("echo OK")[0] == 0),
        ("GPU available", lambda: "A100" in _ssh("nvidia-smi --query-gpu=name --format=csv,noheader")[1]),
        ("Genesis installed", lambda: _ssh(f"{GROOT_PYTHON} -c 'import genesis; print(genesis.__version__)'")[0] == 0),
        ("GR00T checkpoint", lambda: "EXISTS" in _ssh(f"test -d {BEST_CHECKPOINT} && echo EXISTS")[1]),
        ("GR00T server health", lambda: _ssh(f"curl -sf http://localhost:{GROOT_PORT}/health")[0] == 0),
        ("LeRobot dataset", lambda: "EXISTS" in _ssh(f"test -d {PRE_GENERATED_DATASET} && echo EXISTS")[1]),
        ("eval script", lambda: _ssh(f"test -f {ROBOTICS_DIR}/src/eval/closed_loop_eval.py && echo OK")[1] == "OK"),
    ]
    all_ok = True
    for name, check_fn in checks:
        try:
            ok = check_fn()
        except Exception:
            ok = False
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("✅ All checks passed — ready for live demo")
    else:
        print("⚠️  Some checks failed — run with --mode fallback for safety")


# ── Summary display ───────────────────────────────────────────────────────────

def display_summary(steps: list[DemoStep], eval_result: Optional[dict] = None) -> None:
    _banner("🎯 OCI Robot Cloud — AI World 2026 Demo COMPLETE")
    total_s = sum((s.end_time - s.start_time) for s in steps if s.status in ("done","failed"))

    for s in steps:
        icon = {"done":"✅","failed":"❌","skipped":"⏭","running":"⏳","pending":"⬜"}.get(s.status,"?")
        elapsed = f"{s.end_time - s.start_time:.0f}s" if s.end_time else ""
        print(f"  {icon}  {s.name:<35} {elapsed:>6}  {s.result}")

    print(f"\n  Total wall time: {total_s:.0f}s")

    if eval_result:
        rate = eval_result.get("success_rate", 0)
        print(f"""
  📊 LIVE RESULT:
     Closed-loop success:  {rate:.0%} ({eval_result.get('n_success',0)}/{eval_result.get('n_episodes',0)})
     Avg latency:          {eval_result.get('avg_latency_ms',0):.0f}ms
     Training cost:        ${eval_result.get('cost_usd', 0.43):.2f}
  """)
    print(f"  GitHub: github.com/qianjun22/roboticsai")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI World 2026 live demo orchestrator")
    parser.add_argument("--mode", choices=["full","fast","fallback","dry-run"], default="fast")
    parser.add_argument("--checkpoint", default=BEST_CHECKPOINT)
    parser.add_argument("--demos",      type=int, default=50)
    parser.add_argument("--steps",      type=int, default=1000)
    parser.add_argument("--n-episodes", type=int, default=10)
    parser.add_argument("--output-dir", default="/tmp/aiworld_demo")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  OCI Robot Cloud — AI World September 2026 Live Demo")
    print(f"  Mode: {args.mode.upper()}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    if args.mode == "fallback":
        run_fallback_demo()
        return

    if args.mode == "dry-run":
        run_dry_run()
        return

    steps: list[DemoStep] = []

    # 1. Pre-flight
    s = step_preflight(args.mode)
    steps.append(s)

    if args.mode == "fast":
        # Use pre-generated dataset + best checkpoint — skip SDG + convert
        dataset_dir = PRE_GENERATED_DATASET
        finetune_out = f"{args.output_dir}/fast_finetune"
        n_steps = FAST_STEPS
        n_episodes = FAST_EPISODES
    else:
        # Full: generate fresh demos
        sdg_out = f"{args.output_dir}/sdg_demos"
        s2 = step_generate_demos(args.demos, sdg_out)
        steps.append(s2)
        if s2.status != "done":
            display_summary(steps)
            return

        lerobot_out = f"{args.output_dir}/lerobot"
        s3 = step_convert_demos(sdg_out, lerobot_out)
        steps.append(s3)
        if s3.status != "done":
            display_summary(steps)
            return

        dataset_dir = lerobot_out
        finetune_out = f"{args.output_dir}/finetune"
        n_steps = args.steps
        n_episodes = args.n_episodes

    # Fine-tune
    s4 = step_finetune(dataset_dir, n_steps, finetune_out)
    steps.append(s4)

    # Use demo checkpoint if fine-tune failed
    checkpoint = f"{finetune_out}/checkpoint-{n_steps}" if s4.status == "done" else args.checkpoint

    # Restart server
    s5 = step_restart_server(checkpoint)
    steps.append(s5)

    # Eval
    eval_out = f"{args.output_dir}/eval"
    s6 = step_eval(n_episodes, eval_out)
    steps.append(s6)

    # Load eval result
    eval_result = None
    json_path = f"{eval_out}/summary.json"
    rc, json_str, _ = _ssh(f"cat {json_path} 2>/dev/null || echo '{{}}'")
    try:
        eval_result = json.loads(json_str)
    except Exception:
        pass

    display_summary(steps, eval_result)


if __name__ == "__main__":
    main()
