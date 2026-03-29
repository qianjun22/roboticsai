"""
OCI Robot Cloud — Training Throughput Benchmark

Measures GR00T fine-tuning throughput on OCI A100 and computes cost
comparison vs on-premises DGX to support the NVIDIA partnership story.

Metrics captured:
  - steps/sec (training throughput)
  - GPU utilization %
  - GPU memory used (GB)
  - samples/sec
  - total wall-clock time
  - estimated cost per 10k steps at OCI A100 pricing

DGX reference (for comparison):
  - DGX A100 system: ~$200k CapEx (amortized ~$3.6/hr at 3yr/8760hr)
  - vs OCI A100 bare metal: ~$3.60/hr per GPU on-demand (similar!)
  - Key OCI advantage: burst capacity without CapEx lock-in

Usage:
    cd ~/Isaac-GR00T && source .venv/bin/activate
    python3 ~/roboticsai/src/training/benchmark_throughput.py \\
        --dataset /tmp/franka_planned_lerobot \\
        --modality-config ~/roboticsai/src/training/franka_config.py \\
        --steps 200 \\
        --batch-size 32 \\
        --gpu 4
"""

import argparse
import json
import os
import subprocess
import time
import importlib.util
import sys

import torch

parser = argparse.ArgumentParser(description="GR00T training throughput benchmark")
parser.add_argument("--dataset",         type=str, default="/tmp/franka_planned_lerobot")
parser.add_argument("--modality-config", type=str, default="/home/ubuntu/roboticsai/src/training/franka_config.py")
parser.add_argument("--model",           type=str, default="/home/ubuntu/models/GR00T-N1.6-3B")
parser.add_argument("--steps",           type=int, default=200,  help="Steps to benchmark")
parser.add_argument("--batch-size",      type=int, default=32)
parser.add_argument("--gpu",             type=int, default=4)
parser.add_argument("--output",          type=str, default="/tmp/benchmark_results.json")
args = parser.parse_args()

# OCI A100 on-demand pricing (USD/hr, as of 2026)
OCI_A100_PRICE_PER_HR = 3.60   # BM.GPU4.8 / 8 GPUs ≈ $3.60/GPU/hr
DGX_A100_AMORTIZED_HR = 3.80   # $200k / (3yr * 8760hr) / 8 GPUs ≈ $0.95 + colocation ~$2.85


def get_gpu_stats(gpu_idx: int) -> dict:
    """Query current GPU utilization and memory via nvidia-smi."""
    try:
        out = subprocess.check_output([
            "nvidia-smi",
            f"--id={gpu_idx}",
            "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw",
            "--format=csv,noheader,nounits",
        ]).decode().strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "gpu_util_pct":   float(parts[0]),
            "memory_used_gb": float(parts[1]) / 1024,
            "memory_total_gb":float(parts[2]) / 1024,
            "power_w":        float(parts[3]),
        }
    except Exception:
        return {}


def run_benchmark():
    # Load modality config
    spec = importlib.util.spec_from_file_location("franka_config", args.modality_config)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from gr00t.configs.base_config import get_default_config
    from gr00t.data.embodiment_tags import EmbodimentTag

    print(f"\n{'='*60}")
    print(f" OCI Robot Cloud — GR00T Training Throughput Benchmark")
    print(f"{'='*60}")
    print(f" Model:      GR00T-N1.6-3B")
    print(f" Dataset:    {args.dataset}")
    print(f" GPU:        A100-SXM4-80GB (OCI BM.GPU4.8)")
    print(f" Batch size: {args.batch_size}")
    print(f" Steps:      {args.steps}")
    print(f"{'='*60}\n")

    # Baseline GPU stats
    gpu_before = get_gpu_stats(args.gpu)

    # Run fine-tuning in subprocess and capture timing
    finetune_log = "/tmp/benchmark_finetune.log"
    cmd = [
        sys.executable,
        "gr00t/experiment/launch_finetune.py",
        "--base-model-path", args.model,
        "--dataset-path", args.dataset,
        "--embodiment-tag", "NEW_EMBODIMENT",
        "--modality-config-path", args.modality_config,
        "--num-gpus", "1",
        "--output-dir", "/tmp/benchmark_ckpt",
        "--save-steps", "99999",
        "--max-steps", str(args.steps),
        "--global-batch-size", str(args.batch_size),
        "--dataloader-num-workers", "2",
    ]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(args.gpu)

    print("[benchmark] Launching training run...")
    t_start = time.perf_counter()

    gpu_samples = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=env, cwd=os.path.expanduser("~/Isaac-GR00T"))

    # Sample GPU stats every 5s while training
    import threading
    def sample_gpu():
        while proc.poll() is None:
            s = get_gpu_stats(args.gpu)
            if s:
                gpu_samples.append(s)
            time.sleep(5)
    t = threading.Thread(target=sample_gpu, daemon=True)
    t.start()

    stdout_lines = []
    for line in proc.stdout:
        stdout_lines.append(line)
        # Print loss lines for visibility
        if "loss" in line.lower() or "step" in line.lower() or "%" in line:
            if any(c.isdigit() for c in line):
                pass  # suppress verbose progress to avoid noise

    proc.wait()
    t_end = time.perf_counter()
    elapsed = t_end - t_start

    # Extract training metrics from log
    loss_values = []
    steps_per_sec = None
    for line in stdout_lines:
        if "'loss'" in line:
            try:
                import ast
                d = ast.literal_eval(line.strip())
                if "loss" in d:
                    loss_values.append(float(d["loss"]))
            except Exception:
                pass
        if "train_steps_per_second" in line:
            try:
                import ast
                d = ast.literal_eval(line.strip())
                steps_per_sec = d.get("train_steps_per_second")
            except Exception:
                pass

    # Compute metrics
    throughput = args.steps / elapsed if elapsed > 0 else 0
    samples_per_sec = throughput * args.batch_size

    avg_gpu_util  = sum(s.get("gpu_util_pct", 0) for s in gpu_samples) / max(len(gpu_samples), 1)
    avg_gpu_mem   = sum(s.get("memory_used_gb", 0) for s in gpu_samples) / max(len(gpu_samples), 1)
    avg_power     = sum(s.get("power_w", 0) for s in gpu_samples) / max(len(gpu_samples), 1)

    # Cost calculation
    cost_per_10k_steps = (10000 / max(throughput, 0.001) / 3600) * OCI_A100_PRICE_PER_HR
    dgx_cost_per_10k   = (10000 / max(throughput, 0.001) / 3600) * DGX_A100_AMORTIZED_HR

    initial_loss = loss_values[0]  if loss_values else None
    final_loss   = loss_values[-1] if loss_values else None

    results = {
        "model": "GR00T-N1.6-3B",
        "hardware": "OCI A100-SXM4-80GB",
        "batch_size": args.batch_size,
        "steps_benchmarked": args.steps,
        "wall_time_sec": round(elapsed, 1),
        "throughput": {
            "steps_per_sec": round(throughput, 2),
            "samples_per_sec": round(samples_per_sec, 1),
        },
        "gpu": {
            "avg_utilization_pct": round(avg_gpu_util, 1),
            "avg_memory_gb": round(avg_gpu_mem, 2),
            "avg_power_w": round(avg_power, 1),
        },
        "training": {
            "initial_loss": round(initial_loss, 4) if initial_loss else None,
            "final_loss":   round(final_loss, 4) if final_loss else None,
        },
        "cost_analysis": {
            "oci_a100_per_gpu_hr_usd": OCI_A100_PRICE_PER_HR,
            "cost_per_10k_steps_oci_usd": round(cost_per_10k_steps, 4),
            "cost_per_10k_steps_dgx_usd": round(dgx_cost_per_10k, 4),
            "note": "DGX estimate = $200k CapEx / 3yr amortization + colocation",
        },
    }

    print(f"\n{'='*60}")
    print(f" BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f" Throughput:       {throughput:.2f} steps/sec | {samples_per_sec:.0f} samples/sec")
    print(f" Wall time:        {elapsed:.1f}s for {args.steps} steps")
    print(f" GPU utilization:  {avg_gpu_util:.0f}%")
    print(f" GPU memory:       {avg_gpu_mem:.1f} GB / 80 GB")
    print(f" Power draw:       {avg_power:.0f} W")
    if initial_loss and final_loss:
        print(f" Loss:             {initial_loss:.3f} → {final_loss:.3f}")
    print(f"\n Cost (OCI A100):  ${cost_per_10k_steps:.3f} / 10k steps")
    print(f" Cost (DGX est.):  ${dgx_cost_per_10k:.3f} / 10k steps")
    print(f" {'='*40}")
    print(f" OCI advantage:    No $200k CapEx, burst to 8 GPUs on demand")
    print(f"{'='*60}\n")

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[benchmark] Results saved to {args.output}")

    return results


if __name__ == "__main__":
    run_benchmark()
