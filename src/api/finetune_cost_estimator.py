"""
Fine-tuning Cost Estimator — CLI + FastAPI
Helps design partners plan training budgets before submitting jobs.
OCI A100 benchmark: 2.35 it/s (measured, session 5).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# HAS_FASTAPI pattern
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI, Query
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Pricing constants (USD / GPU-hour)
# ---------------------------------------------------------------------------
OCI_A100_PER_GPU_HOUR   = 4.20
AWS_P4D_PER_GPU_HOUR    = 40.48
DGX_PER_GPU_HOUR        = 19.50
LAMBDA_PER_GPU_HOUR     = 8.00

# Throughput measured on OCI A100, single-GPU, BF16
BASE_THROUGHPUT_IT_PER_S = 2.35

# VRAM model
VRAM_BASE_GB             = 36.8
VRAM_PER_100_BATCH_GB    = 1.2

# Precision multipliers (speed)
PRECISION_SPEEDUP = {
    "fp8":  1.45,
    "fp16": 1.15,
    "bf16": 1.00,
}

# DDP efficiency
DDP_EFFICIENCY = 0.90  # 10% overhead

# DAgger step multiplier per iteration
DAGGER_STEP_FRACTION = 0.40


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FinetuneConfig:
    n_demos:      int
    n_steps:      int
    batch_size:   int   = 32
    n_gpus:       int   = 1
    use_dagger:   bool  = False
    dagger_iters: int   = 3
    precision:    str   = "bf16"   # "bf16" | "fp16" | "fp8"
    embodiment:   str   = "franka" # "franka" | "ur5e" | "xarm7" | "kinova"


@dataclass
class CostEstimate:
    n_steps_total:       int
    gpu_hours:           float
    oci_cost_usd:        float
    aws_p4d_cost_usd:    float
    dgx_cost_usd:        float
    lambda_cost_usd:     float
    estimated_minutes:   float
    throughput_it_per_s: float
    vram_gb:             float
    savings_vs_aws_pct:  float


# ---------------------------------------------------------------------------
# Core estimation logic
# ---------------------------------------------------------------------------

def estimate_cost(config: FinetuneConfig) -> CostEstimate:
    """Predict GPU hours, cost, and completion time for a fine-tuning job."""

    # 1. Total training steps
    if config.use_dagger:
        n_steps_total = int(
            config.n_steps * (1 + config.dagger_iters * DAGGER_STEP_FRACTION)
        )
    else:
        n_steps_total = config.n_steps

    # 2. Effective throughput
    precision_key = config.precision.lower()
    if precision_key not in PRECISION_SPEEDUP:
        raise ValueError(f"Unknown precision '{config.precision}'. Choose: bf16, fp16, fp8")

    speed_multiplier = PRECISION_SPEEDUP[precision_key]
    # Per-GPU throughput
    per_gpu_throughput = BASE_THROUGHPUT_IT_PER_S * speed_multiplier
    # Multi-GPU effective throughput (DDP)
    if config.n_gpus > 1:
        effective_throughput = per_gpu_throughput * config.n_gpus * DDP_EFFICIENCY
    else:
        effective_throughput = per_gpu_throughput

    # 3. Wall-clock time
    total_seconds = n_steps_total / effective_throughput
    estimated_minutes = total_seconds / 60.0

    # 4. GPU-hours (all GPUs × wall time)
    gpu_hours = (config.n_gpus * total_seconds) / 3600.0

    # 5. Cloud costs
    oci_cost_usd     = gpu_hours * OCI_A100_PER_GPU_HOUR
    aws_p4d_cost_usd = gpu_hours * AWS_P4D_PER_GPU_HOUR
    dgx_cost_usd     = gpu_hours * DGX_PER_GPU_HOUR
    lambda_cost_usd  = gpu_hours * LAMBDA_PER_GPU_HOUR

    # 6. Savings vs AWS
    savings_vs_aws_pct = (aws_p4d_cost_usd - oci_cost_usd) / aws_p4d_cost_usd * 100.0

    # 7. VRAM estimate
    vram_gb = VRAM_BASE_GB + VRAM_PER_100_BATCH_GB * (config.batch_size / 100.0)

    return CostEstimate(
        n_steps_total       = n_steps_total,
        gpu_hours           = round(gpu_hours, 4),
        oci_cost_usd        = round(oci_cost_usd, 4),
        aws_p4d_cost_usd    = round(aws_p4d_cost_usd, 4),
        dgx_cost_usd        = round(dgx_cost_usd, 4),
        lambda_cost_usd     = round(lambda_cost_usd, 4),
        estimated_minutes   = round(estimated_minutes, 2),
        throughput_it_per_s = round(effective_throughput, 3),
        vram_gb             = round(vram_gb, 2),
        savings_vs_aws_pct  = round(savings_vs_aws_pct, 1),
    )


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def print_estimate(estimate: CostEstimate, label: str = "") -> None:
    """Print a nicely formatted cost estimate table."""
    header = f"  Cost Estimate{' — ' + label if label else ''}  "
    width = max(len(header) + 4, 56)
    border = "=" * width

    def row(name: str, value: str) -> str:
        return f"  {name:<30} {value:>18}"

    print(border)
    print(header.center(width))
    print(border)
    print(row("Total training steps:", f"{estimate.n_steps_total:,}"))
    print(row("Effective throughput:", f"{estimate.throughput_it_per_s:.2f} it/s"))
    print(row("Estimated wall time:", f"{estimate.estimated_minutes:.1f} min"))
    print(row("GPU-hours (all GPUs):", f"{estimate.gpu_hours:.3f} h"))
    print(row("VRAM estimate:", f"{estimate.vram_gb:.1f} GB"))
    print("-" * width)
    print(row("OCI A100 ($4.20/GPU-h):", f"${estimate.oci_cost_usd:.4f}"))
    print(row("AWS p4d  ($40.48/GPU-h):", f"${estimate.aws_p4d_cost_usd:.4f}"))
    print(row("DGX      ($19.50/GPU-h):", f"${estimate.dgx_cost_usd:.4f}"))
    print(row("Lambda   ($8.00/GPU-h):", f"${estimate.lambda_cost_usd:.4f}"))
    print("-" * width)
    print(row("OCI savings vs AWS:", f"{estimate.savings_vs_aws_pct:.1f}%"))
    print(border)
    print()


# ---------------------------------------------------------------------------
# Preset scenarios
# ---------------------------------------------------------------------------

PRESETS: Dict[str, FinetuneConfig] = {
    "quick_test": FinetuneConfig(
        n_demos=50, n_steps=500, n_gpus=1, use_dagger=False,
        batch_size=32, precision="bf16", embodiment="franka",
    ),
    "standard_bc": FinetuneConfig(
        n_demos=1000, n_steps=5000, n_gpus=1, use_dagger=False,
        batch_size=32, precision="bf16", embodiment="franka",
    ),
    "dagger_3iter": FinetuneConfig(
        n_demos=1000, n_steps=5000, n_gpus=1, use_dagger=True, dagger_iters=3,
        batch_size=32, precision="bf16", embodiment="franka",
    ),
    "multi_gpu": FinetuneConfig(
        n_demos=1000, n_steps=5000, n_gpus=4, use_dagger=True, dagger_iters=3,
        batch_size=32, precision="bf16", embodiment="franka",
    ),
    "full_curriculum": FinetuneConfig(
        # 5000 base steps + 14 curriculum tasks × 1500 steps each
        n_demos=1400, n_steps=5000 + 14 * 1500, n_gpus=4,
        use_dagger=True, dagger_iters=3,
        batch_size=32, precision="bf16", embodiment="franka",
    ),
}

PRESET_LABELS: Dict[str, str] = {
    "quick_test":       "Quick Test (50 demos, 500 steps, 1 GPU, no DAgger)",
    "standard_bc":      "Standard BC (1000 demos, 5000 steps, 1 GPU)",
    "dagger_3iter":     "DAgger 3-iter (1000 demos, 5000 steps, 1 GPU)",
    "multi_gpu":        "Multi-GPU DDP (1000 demos, 5000 steps, 4 GPUs + DAgger)",
    "full_curriculum":  "Full Curriculum (1400 demos, 5000+14×1500 steps, 4 GPUs + DAgger)",
}


# ---------------------------------------------------------------------------
# FastAPI app (conditional)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Fine-tune Cost Estimator",
        description="Predict GPU hours, cost, and completion time for GR00T fine-tuning jobs.",
        version="1.0.0",
    )

    @app.get("/api/estimate", response_model=None)
    def api_estimate(
        n_demos:      int   = Query(...,    description="Number of demonstration episodes"),
        n_steps:      int   = Query(...,    description="Training steps"),
        n_gpus:       int   = Query(1,      description="Number of GPUs"),
        batch_size:   int   = Query(32,     description="Batch size"),
        dagger:       bool  = Query(False,  description="Enable DAgger"),
        dagger_iters: int   = Query(3,      description="DAgger iterations"),
        precision:    str   = Query("bf16", description="Precision: bf16, fp16, fp8"),
        embodiment:   str   = Query("franka", description="Robot embodiment"),
    ):
        config = FinetuneConfig(
            n_demos      = n_demos,
            n_steps      = n_steps,
            n_gpus       = n_gpus,
            batch_size   = batch_size,
            use_dagger   = dagger,
            dagger_iters = dagger_iters,
            precision    = precision,
            embodiment   = embodiment,
        )
        est = estimate_cost(config)
        return {
            "n_steps_total":       est.n_steps_total,
            "gpu_hours":           est.gpu_hours,
            "oci_cost_usd":        est.oci_cost_usd,
            "aws_p4d_cost_usd":    est.aws_p4d_cost_usd,
            "dgx_cost_usd":        est.dgx_cost_usd,
            "lambda_cost_usd":     est.lambda_cost_usd,
            "estimated_minutes":   est.estimated_minutes,
            "throughput_it_per_s": est.throughput_it_per_s,
            "vram_gb":             est.vram_gb,
            "savings_vs_aws_pct":  est.savings_vs_aws_pct,
        }

    @app.get("/api/presets")
    def api_presets():
        results = {}
        for name, cfg in PRESETS.items():
            est = estimate_cost(cfg)
            results[name] = {
                "label":           PRESET_LABELS[name],
                "n_steps_total":   est.n_steps_total,
                "gpu_hours":       est.gpu_hours,
                "oci_cost_usd":    est.oci_cost_usd,
                "aws_p4d_cost_usd":est.aws_p4d_cost_usd,
                "estimated_minutes": est.estimated_minutes,
                "savings_vs_aws_pct": est.savings_vs_aws_pct,
            }
        return results

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "finetune-cost-estimator"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="finetune_cost_estimator.py",
        description="OCI Robot Cloud fine-tuning cost estimator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python finetune_cost_estimator.py --preset standard_bc
  python finetune_cost_estimator.py --n-demos 500 --n-steps 3000 --n-gpus 2 --dagger --dagger-iters 3
  python finetune_cost_estimator.py --all-presets
  python finetune_cost_estimator.py --compare-clouds --n-demos 1000 --n-steps 5000
  python finetune_cost_estimator.py --server --port 8038
""",
    )

    # Preset / mode flags
    mode = p.add_argument_group("Modes")
    mode.add_argument("--preset",        choices=list(PRESETS.keys()),
                      help="Use a named preset scenario")
    mode.add_argument("--all-presets",   action="store_true",
                      help="Run and compare all 5 preset scenarios")
    mode.add_argument("--compare-clouds", action="store_true",
                      help="Show side-by-side cloud pricing for the given config")
    mode.add_argument("--server",        action="store_true",
                      help="Start FastAPI server (requires fastapi + uvicorn)")
    mode.add_argument("--port",          type=int, default=8038,
                      help="Port for API server (default: 8038)")

    # Config flags
    cfg = p.add_argument_group("Training config")
    cfg.add_argument("--n-demos",      type=int, default=None)
    cfg.add_argument("--n-steps",      type=int, default=None)
    cfg.add_argument("--batch-size",   type=int, default=32)
    cfg.add_argument("--n-gpus",       type=int, default=1)
    cfg.add_argument("--dagger",       action="store_true", help="Enable DAgger")
    cfg.add_argument("--dagger-iters", type=int, default=3)
    cfg.add_argument("--precision",    choices=["bf16", "fp16", "fp8"], default="bf16")
    cfg.add_argument("--embodiment",   choices=["franka", "ur5e", "xarm7", "kinova"],
                     default="franka")
    return p


def print_compare_clouds(estimate: CostEstimate, label: str = "") -> None:
    """Print a comparison table across cloud providers."""
    title = f"  Cloud Cost Comparison{' — ' + label if label else ''}  "
    width = 64
    border = "=" * width

    clouds = [
        ("OCI A100",  estimate.oci_cost_usd,     "$4.20/GPU-h"),
        ("Lambda",    estimate.lambda_cost_usd,   "$8.00/GPU-h"),
        ("DGX",       estimate.dgx_cost_usd,      "$19.50/GPU-h"),
        ("AWS p4d",   estimate.aws_p4d_cost_usd,  "$40.48/GPU-h"),
    ]
    sorted_clouds = sorted(clouds, key=lambda x: x[1])

    print(border)
    print(title.center(width))
    print(f"  Steps: {estimate.n_steps_total:,}   GPU-hours: {estimate.gpu_hours:.3f}   "
          f"Wall time: {estimate.estimated_minutes:.1f} min")
    print("-" * width)
    print(f"  {'Cloud':<14} {'Rate':<16} {'Total Cost':>14} {'vs OCI':>10}")
    print("-" * width)
    oci_cost = estimate.oci_cost_usd
    for name, cost, rate in sorted_clouds:
        pct = ((cost - oci_cost) / oci_cost * 100) if oci_cost > 0 else 0.0
        pct_str = f"+{pct:.0f}%" if pct > 0 else "baseline"
        print(f"  {name:<14} {rate:<16} ${cost:>13.4f} {pct_str:>10}")
    print(border)
    print()


def run_cli(args: argparse.Namespace) -> None:
    # Server mode
    if args.server:
        if not HAS_FASTAPI:
            print("ERROR: FastAPI and uvicorn are required for server mode.")
            print("  pip install fastapi uvicorn")
            sys.exit(1)
        print(f"Starting Fine-tune Cost Estimator API on port {args.port}...")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
        return

    # All-presets mode
    if args.all_presets:
        print("\nComparing all preset scenarios\n")
        for name, cfg in PRESETS.items():
            est = estimate_cost(cfg)
            print_estimate(est, label=PRESET_LABELS[name])
        return

    # Build config from flags or preset
    if args.preset:
        cfg = PRESETS[args.preset]
        label = PRESET_LABELS[args.preset]
    else:
        if args.n_demos is None or args.n_steps is None:
            print("ERROR: --n-demos and --n-steps are required (or use --preset / --all-presets).")
            sys.exit(1)
        cfg = FinetuneConfig(
            n_demos      = args.n_demos,
            n_steps      = args.n_steps,
            batch_size   = args.batch_size,
            n_gpus       = args.n_gpus,
            use_dagger   = args.dagger,
            dagger_iters = args.dagger_iters,
            precision    = args.precision,
            embodiment   = args.embodiment,
        )
        dagger_desc = f", DAgger {cfg.dagger_iters}-iter" if cfg.use_dagger else ""
        label = (
            f"{cfg.n_demos} demos, {cfg.n_steps} steps, "
            f"{cfg.n_gpus} GPU(s), {cfg.precision}{dagger_desc}"
        )

    est = estimate_cost(cfg)

    if args.compare_clouds:
        print_compare_clouds(est, label=label)
    else:
        print_estimate(est, label=label)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    run_cli(args)
