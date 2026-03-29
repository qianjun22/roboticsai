"""
Hyperparameter optimization for GR00T fine-tuning on OCI.

Uses Optuna to find the optimal training configuration for maximizing
closed-loop success rate. Runs multiple short trials (500 steps each)
and evaluates with open-loop MAE as proxy metric.

HPO space:
  - learning_rate: [1e-5, 5e-4]
  - batch_size: [8, 16, 32]
  - warmup_ratio: [0.0, 0.1]
  - weight_decay: [0.0, 0.01]
  - action_chunk_size: [8, 16] (16 = GR00T default)

Usage:
    pip install optuna
    python3 hpo_search.py \\
        --dataset-path /tmp/lerobot_500 \\
        --output-dir /tmp/hpo_run \\
        --n-trials 20 \\
        --trial-steps 500

Output:
    /tmp/hpo_run/hpo_results.json  — all trial results sorted by MAE
    /tmp/hpo_run/best_config.json  — best hyperparameter config
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("[HPO] Optuna not installed — install with: pip install optuna")
    sys.exit(1)


# ── Trial objective ───────────────────────────────────────────────────────────

def objective(trial, dataset_path: Path, output_dir: Path,
              trial_steps: int, gpu_id: int) -> float:
    """
    Optuna objective: train for `trial_steps` and return validation MAE.
    Lower MAE = better (Optuna minimizes by default).
    """
    lr = trial.suggest_float("learning_rate", 1e-5, 5e-4, log=True)
    batch_size = trial.suggest_categorical("batch_size", [8, 16, 32])
    warmup_ratio = trial.suggest_float("warmup_ratio", 0.0, 0.1)
    weight_decay = trial.suggest_float("weight_decay", 0.0, 0.01)
    action_chunk = trial.suggest_categorical("action_chunk_size", [8, 16])

    trial_dir = output_dir / f"trial_{trial.number:03d}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    log_file = trial_dir / "train.log"

    print(f"\n[HPO] Trial {trial.number}: lr={lr:.2e} bs={batch_size} "
          f"warmup={warmup_ratio:.2f} wd={weight_decay:.4f} chunk={action_chunk}")

    cmd = [
        "python3", "launch_finetune.py",
        "--dataset-path", str(dataset_path),
        "--max-steps", str(trial_steps),
        "--global-batch-size", str(batch_size),
        "--learning-rate", str(lr),
        "--warmup-ratio", str(warmup_ratio),
        "--weight-decay", str(weight_decay),
        "--output-dir", str(trial_dir),
    ]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    t0 = time.time()
    with open(log_file, "w") as log_f:
        result = subprocess.run(
            cmd, env=env,
            stdout=log_f, stderr=subprocess.STDOUT,
            timeout=1800,  # 30 min max per trial
        )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"[HPO] Trial {trial.number} FAILED ({elapsed:.0f}s) — returning penalty MAE 9.99")
        return 9.99

    # Parse MAE from log
    mae = _parse_mae_from_log(log_file)
    print(f"[HPO] Trial {trial.number}: MAE={mae:.4f} ({elapsed:.0f}s)")

    # Save trial metadata
    meta = {
        "trial": trial.number,
        "params": dict(trial.params),
        "mae": mae,
        "elapsed_sec": elapsed,
        "returncode": result.returncode,
    }
    with open(trial_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return mae


def _parse_mae_from_log(log_file: Path) -> float:
    """Extract final validation MAE from training log."""
    try:
        lines = log_file.read_text().splitlines()
        # Look for lines like "val_mae: 0.0234" or "MAE: 0.0234"
        for line in reversed(lines):
            for key in ["val_mae", "MAE", "mae"]:
                if key in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            return float(parts[-1].strip().split()[0])
                        except ValueError:
                            pass
        # Fallback: parse final loss as proxy
        for line in reversed(lines):
            if "loss=" in line or "loss =" in line:
                try:
                    idx = line.index("loss")
                    snippet = line[idx:].split()[0].replace("loss=", "").replace("loss =", "").strip("=,")
                    return float(snippet)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return 9.99  # penalty if parse fails


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Optuna HPO for GR00T fine-tuning")
    parser.add_argument("--dataset-path", required=True,
                        help="LeRobot v2 dataset directory")
    parser.add_argument("--output-dir", default="/tmp/hpo_run",
                        help="Directory for trial outputs and results")
    parser.add_argument("--n-trials", type=int, default=20,
                        help="Number of Optuna trials")
    parser.add_argument("--trial-steps", type=int, default=500,
                        help="Fine-tuning steps per trial")
    parser.add_argument("--gpu-id", type=int, default=4)
    parser.add_argument("--storage", default=None,
                        help="Optuna storage URL (e.g. sqlite:///hpo.db) for resuming")
    parser.add_argument("--study-name", default="groot_hpo")
    args = parser.parse_args()

    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        print(f"[HPO] Dataset not found: {dataset_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[HPO] GR00T Fine-Tuning Hyperparameter Search")
    print(f"[HPO] Dataset: {dataset_path}")
    print(f"[HPO] Trials: {args.n_trials} × {args.trial_steps} steps each")
    print(f"[HPO] GPU: {args.gpu_id}\n")

    study = optuna.create_study(
        study_name=args.study_name,
        direction="minimize",
        storage=args.storage,
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=3),
    )

    def _obj(trial):
        return objective(trial, dataset_path, output_dir, args.trial_steps, args.gpu_id)

    study.optimize(_obj, n_trials=args.n_trials, timeout=None)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[HPO] Optimization complete — {len(study.trials)} trials")
    print(f"{'='*60}")

    best = study.best_trial
    print(f"\nBest trial #{best.number}:")
    print(f"  MAE: {best.value:.4f}")
    for k, v in best.params.items():
        print(f"  {k}: {v}")

    # Save results
    all_results = []
    for t in sorted(study.trials, key=lambda x: x.value or 9.99):
        if t.value is not None:
            all_results.append({
                "trial": t.number,
                "mae": t.value,
                "params": t.params,
            })

    with open(output_dir / "hpo_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    best_config = {
        "best_mae": best.value,
        "params": best.params,
        "recommended_full_run": {
            **best.params,
            "max_steps": 5000,
            "note": f"Run full 5000-step training with these params for production checkpoint",
        },
    }
    with open(output_dir / "best_config.json", "w") as f:
        json.dump(best_config, f, indent=2)

    print(f"\n[HPO] Results saved:")
    print(f"  All trials: {output_dir / 'hpo_results.json'}")
    print(f"  Best config: {output_dir / 'best_config.json'}")

    # Top-5 table
    print(f"\n{'Rank':>4} {'Trial':>6} {'MAE':>8}  Config")
    print("-" * 60)
    for rank, r in enumerate(all_results[:5], 1):
        params_str = ", ".join(f"{k}={v}" for k, v in list(r["params"].items())[:3])
        print(f"{rank:>4} {r['trial']:>6} {r['mae']:>8.4f}  {params_str}")

    print(f"\n[HPO] Recommended next step:")
    print(f"  python3 launch_finetune.py \\")
    print(f"    --dataset-path {dataset_path} \\")
    print(f"    --max-steps 5000 \\")
    for k, v in best.params.items():
        print(f"    --{k.replace('_', '-')} {v} \\")


if __name__ == "__main__":
    main()
