#!/usr/bin/env python3
"""
finetune_pipeline_v2.py — Production fine-tune pipeline v2 for GR00T N1.6-3B on OCI Robot Cloud.

Integrates LoRA, dataset quality filtering, checkpoint management, and cost tracking.
Replaces manual shell script approach with a single orchestrated Python pipeline.

Stages: INIT → QUALITY_FILTER → CONVERT → TRAIN → EVAL → UPLOAD → DONE (or FAILED)

Usage:
    python src/training/finetune_pipeline_v2.py --mock --steps 2000 --lora-rank 16
    python src/training/finetune_pipeline_v2.py --mock --steps 5000 --output /tmp/finetune_v2.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Generator, List, Optional, Tuple


# ── Config & State ────────────────────────────────────────────────────────────

@dataclass
class FinetuneConfig:
    run_id: str = "groot_v2"
    dataset_dir: str = "/tmp/dataset"
    output_dir: str = "/tmp/finetune_v2_out"
    n_steps: int = 2000
    batch_size: int = 16
    lr: float = 1e-4
    lora_rank: int = 16          # 0 = full fine-tune
    warmup_steps: int = 100
    eval_episodes: int = 10
    checkpoint_interval: int = 500
    gpu_type: str = "A100"
    use_spot: bool = True
    seed: int = 42


class FinetuneStage(Enum):
    INIT = "INIT"
    QUALITY_FILTER = "QUALITY_FILTER"
    CONVERT = "CONVERT"
    TRAIN = "TRAIN"
    EVAL = "EVAL"
    UPLOAD = "UPLOAD"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class PipelineState:
    stage: FinetuneStage = FinetuneStage.INIT
    current_step: int = 0
    loss: float = 0.0
    best_loss: float = float("inf")
    eval_sr: float = 0.0
    cost_usd: float = 0.0
    elapsed_hr: float = 0.0
    checkpoints_saved: List[str] = field(default_factory=list)
    log_lines: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        print(line)


# ── GPU cost table ($/hr, spot) ────────────────────────────────────────────────
GPU_RATES = {
    "A100": 1.80,
    "A10":  0.60,
    "V100": 1.20,
}


# ── Pipeline ──────────────────────────────────────────────────────────────────

class FinetuneRun:
    def __init__(self, config: FinetuneConfig) -> None:
        self.config = config
        self.state = PipelineState()
        self._start_time = time.time()
        self._rng = random.Random(config.seed)
        self._loss_history: List[Tuple[int, float]] = []

        out = Path(config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "checkpoints").mkdir(exist_ok=True)

        self.state.log(
            f"Pipeline v2 init | run_id={config.run_id} lora_rank={config.lora_rank} "
            f"steps={config.n_steps} gpu={config.gpu_type}"
        )

    # ── Stage helpers ──────────────────────────────────────────────────────────

    def run_quality_filter(self) -> Tuple[int, int, float]:
        """Simulate quality filtering: drop episodes with quality score < 5.0."""
        self.state.stage = FinetuneStage.QUALITY_FILTER
        self.state.log("Quality filter: scanning dataset for score >= 5.0 ...")
        time.sleep(0.05)  # mock I/O

        n_before = self._rng.randint(800, 1200)
        keep_rate = self._rng.uniform(0.72, 0.91)
        n_after = max(1, int(n_before * keep_rate))
        pct_kept = n_after / n_before * 100

        self.state.log(
            f"Quality filter done: {n_before} → {n_after} episodes "
            f"({pct_kept:.1f}% kept, threshold=5.0)"
        )
        return n_before, n_after, pct_kept

    def run_convert(self) -> int:
        """Simulate genesis_to_lerobot conversion, returns total frame count."""
        self.state.stage = FinetuneStage.CONVERT
        self.state.log("Convert: genesis_to_lerobot format conversion ...")
        time.sleep(0.05)

        n_frames = self._rng.randint(48_000, 72_000)
        self.state.log(f"Convert done: {n_frames:,} frames written to LeRobot format")
        return n_frames

    def run_training(self) -> Generator[Tuple[int, float, float], None, None]:
        """
        Mock training loop.  Yields (step, loss, it_per_sec).

        Loss curve: S-curve from 0.68 → ~0.10 over 5000 steps.
        LoRA converges ~30% faster (effective steps scaled).
        Saves checkpoints at checkpoint_interval; early-stops if loss < 0.05.
        """
        self.state.stage = FinetuneStage.TRAIN
        cfg = self.config
        lora_speed = 1.30 if cfg.lora_rank > 0 else 1.0  # LoRA 30% faster convergence

        def s_curve_loss(step: int) -> float:
            eff_step = step * lora_speed
            x = eff_step / 5000.0
            # Sigmoid-based decay: from 0.68 toward 0.10
            raw = 0.68 / (1.0 + math.exp(8 * (x - 0.55)))
            noise = self._rng.gauss(0, 0.003)
            return max(0.04, raw + noise)

        base_it_per_sec = 2.35 if cfg.gpu_type == "A100" else 1.40

        ckpt_dir = Path(cfg.output_dir) / "checkpoints"
        last_ckpt_step = 0

        for step in range(1, cfg.n_steps + 1):
            loss = s_curve_loss(step)
            warmup_factor = min(1.0, step / max(1, cfg.warmup_steps))
            loss *= (0.7 + 0.3 * warmup_factor)  # slight warmup penalty early

            it_per_sec = base_it_per_sec * self._rng.uniform(0.95, 1.05)
            self.state.current_step = step
            self.state.loss = loss
            if loss < self.state.best_loss:
                self.state.best_loss = loss

            # Record for SVG
            if step % 50 == 0 or step == 1:
                self._loss_history.append((step, loss))

            # Checkpoint
            if step - last_ckpt_step >= cfg.checkpoint_interval or step == cfg.n_steps:
                ckpt_name = f"checkpoint_step{step:05d}.pt"
                ckpt_path = str(ckpt_dir / ckpt_name)
                (ckpt_dir / ckpt_name).touch()  # mock file
                self.state.checkpoints_saved.append(ckpt_path)
                last_ckpt_step = step
                self.state.log(
                    f"Train step {step}/{cfg.n_steps} | loss={loss:.4f} "
                    f"it/s={it_per_sec:.2f} | checkpoint saved"
                )

            # Early stop
            if loss < 0.05:
                self.state.log(f"Early stop at step {step}: loss={loss:.4f} < 0.05")
                yield step, loss, it_per_sec
                break

            yield step, loss, it_per_sec

    def run_eval(self, checkpoint_path: str) -> Tuple[float, float]:
        """Mock 10-episode eval on the given checkpoint; returns (success_rate, avg_latency_ms)."""
        self.state.stage = FinetuneStage.EVAL
        self.state.log(f"Eval: running {self.config.eval_episodes} episodes on {checkpoint_path} ...")
        time.sleep(0.05)

        # Better LoRA convergence → higher SR when loss is low
        base_sr = max(0.05, min(0.95, 1.0 - self.state.best_loss * 4.5))
        sr = round(self._rng.uniform(base_sr * 0.85, base_sr * 1.05), 2)
        sr = min(1.0, max(0.0, sr))
        avg_lat = self._rng.uniform(220, 240)

        self.state.eval_sr = sr
        self.state.log(f"Eval done: SR={sr:.0%} avg_latency={avg_lat:.0f}ms")
        return sr, avg_lat

    def cost_so_far(self) -> float:
        """GPU hours elapsed × per-hour rate."""
        elapsed_hr = (time.time() - self._start_time) / 3600.0
        rate = GPU_RATES.get(self.config.gpu_type, 1.80)
        if self.config.use_spot:
            rate *= 0.35  # ~65% spot discount on OCI
        return elapsed_hr * rate

    def run(self) -> PipelineState:
        """Execute full pipeline: filter → convert → train → eval. Saves state.json."""
        cfg = self.config
        state = self.state

        try:
            # QUALITY_FILTER
            n_before, n_after, pct_kept = self.run_quality_filter()

            # CONVERT
            n_frames = self.run_convert()

            # TRAIN
            state.stage = FinetuneStage.TRAIN
            state.log(f"Training started: lora_rank={cfg.lora_rank or 'full'} lr={cfg.lr}")
            for step, loss, it_s in self.run_training():
                state.elapsed_hr = (time.time() - self._start_time) / 3600.0
                state.cost_usd = self.cost_so_far()

            # EVAL — use best checkpoint
            best_ckpt = state.checkpoints_saved[-1] if state.checkpoints_saved else "none"
            sr, lat = self.run_eval(best_ckpt)

            # UPLOAD (mock)
            state.stage = FinetuneStage.UPLOAD
            state.log("Upload: pushing artifacts to OCI Object Storage ...")
            time.sleep(0.02)
            state.log("Upload done.")

            state.stage = FinetuneStage.DONE
            state.elapsed_hr = (time.time() - self._start_time) / 3600.0
            state.cost_usd = self.cost_so_far()
            state.log(
                f"Pipeline DONE | SR={sr:.0%} best_loss={state.best_loss:.4f} "
                f"cost=${state.cost_usd:.4f} elapsed={state.elapsed_hr*3600:.1f}s"
            )

        except Exception as exc:  # noqa: BLE001
            state.stage = FinetuneStage.FAILED
            state.log(f"FAILED: {exc}")

        # Persist state
        state_path = Path(cfg.output_dir) / "state.json"
        with open(state_path, "w") as fh:
            json.dump(
                {
                    "run_id": cfg.run_id,
                    "stage": state.stage.value,
                    "current_step": state.current_step,
                    "loss": state.loss,
                    "best_loss": state.best_loss,
                    "eval_sr": state.eval_sr,
                    "cost_usd": state.cost_usd,
                    "elapsed_hr": state.elapsed_hr,
                    "checkpoints_saved": state.checkpoints_saved,
                    "log_lines": state.log_lines,
                },
                fh,
                indent=2,
            )
        return state


# ── HTML Dashboard ─────────────────────────────────────────────────────────────

def render_html(state: PipelineState, config: FinetuneConfig, loss_history: List[Tuple[int, float]]) -> str:
    stages_order = [s.value for s in FinetuneStage if s not in (FinetuneStage.FAILED,)]
    current_idx = next((i for i, s in enumerate(stages_order) if s == state.stage.value), 0)

    # Stage progress bar
    stage_items = []
    for i, s in enumerate(stages_order):
        if i < current_idx:
            cls = "done"
        elif i == current_idx:
            cls = "active"
        else:
            cls = "pending"
        stage_items.append(f'<div class="stage {cls}">{s}</div>')
    stages_html = "\n".join(stage_items)

    # SVG loss curve
    svg_w, svg_h = 600, 180
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    plot_w = svg_w - pad_l - pad_r
    plot_h = svg_h - pad_t - pad_b

    svg_points = ""
    if loss_history:
        max_step = max(s for s, _ in loss_history) or 1
        max_loss = 0.70
        pts = []
        for step, loss in loss_history:
            x = pad_l + step / max_step * plot_w
            y = pad_t + (1 - loss / max_loss) * plot_h
            pts.append(f"{x:.1f},{y:.1f}")
        svg_points = '<polyline points="' + " ".join(pts) + '" fill="none" stroke="#38bdf8" stroke-width="2"/>'

    svg = f"""<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1"/>
  <line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1"/>
  <text x="{pad_l-5}" y="{pad_t+5}" fill="#94a3b8" font-size="10" text-anchor="end">0.70</text>
  <text x="{pad_l-5}" y="{pad_t+plot_h}" fill="#94a3b8" font-size="10" text-anchor="end">0.00</text>
  <text x="{pad_l + plot_w//2}" y="{svg_h-5}" fill="#94a3b8" font-size="10" text-anchor="middle">Step</text>
  {svg_points}
</svg>"""

    # Log tail
    log_tail = "\n".join(state.log_lines[-10:])

    # Metrics cards
    eta_s = max(0, (config.n_steps - state.current_step) / max(1, state.current_step / max(1e-9, state.elapsed_hr * 3600)))
    eta_str = f"{eta_s/60:.0f}m" if eta_s > 60 else f"{eta_s:.0f}s"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GR00T Fine-Tune Pipeline v2 — {config.run_id}</title>
<style>
  body {{ font-family: 'SF Mono', monospace; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .stages {{ display: flex; gap: 6px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stage {{ padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; letter-spacing: .05em; }}
  .stage.done {{ background: #134e4a; color: #6ee7b7; }}
  .stage.active {{ background: #1e3a5f; color: #38bdf8; border: 1px solid #38bdf8; }}
  .stage.pending {{ background: #1e293b; color: #475569; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 16px; }}
  .card-label {{ color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: .1em; }}
  .card-value {{ font-size: 1.6rem; font-weight: 700; margin-top: 4px; }}
  .sr {{ color: #34d399; }}
  .loss {{ color: #f472b6; }}
  .cost {{ color: #fbbf24; }}
  .eta {{ color: #a78bfa; }}
  .section-title {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; }}
  .log {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 14px;
           font-size: 0.78rem; color: #94a3b8; white-space: pre-wrap; line-height: 1.7; }}
  .info-row {{ display: flex; gap: 24px; color: #475569; font-size: 0.78rem; margin-bottom: 28px; }}
  .info-row span {{ color: #94a3b8; }}
</style>
</head>
<body>
<h1>GR00T N1.6-3B Fine-Tune Pipeline v2</h1>
<div class="subtitle">run_id: {config.run_id} &nbsp;|&nbsp; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

<div class="info-row">
  LoRA rank: <span>{config.lora_rank or "full"}</span>
  &nbsp;Steps: <span>{config.n_steps}</span>
  &nbsp;LR: <span>{config.lr}</span>
  &nbsp;Batch: <span>{config.batch_size}</span>
  &nbsp;GPU: <span>{config.gpu_type}{"(spot)" if config.use_spot else ""}</span>
  &nbsp;Seed: <span>{config.seed}</span>
</div>

<div class="stages">
{stages_html}
</div>

<div class="metrics">
  <div class="card"><div class="card-label">Success Rate</div><div class="card-value sr">{state.eval_sr:.0%}</div></div>
  <div class="card"><div class="card-label">Best Loss</div><div class="card-value loss">{state.best_loss:.4f}</div></div>
  <div class="card"><div class="card-label">Cost (USD)</div><div class="card-value cost">${state.cost_usd:.4f}</div></div>
  <div class="card"><div class="card-label">ETA</div><div class="card-value eta">{eta_str}</div></div>
</div>

<div class="section-title">Loss Curve — step {state.current_step}/{config.n_steps}</div>
{svg}
<br><br>

<div class="section-title">Log (last 10 lines)</div>
<div class="log">{log_tail}</div>
</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GR00T Fine-Tune Pipeline v2")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--output", default="/tmp/finetune_v2.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cfg = FinetuneConfig(
        run_id=f"groot_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        n_steps=args.steps,
        lora_rank=args.lora_rank,
        seed=args.seed,
    )

    pipeline = FinetuneRun(cfg)
    state = pipeline.run()

    html = render_html(state, cfg, pipeline._loss_history)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"\nDashboard saved → {out_path}")
    print(f"Final stage: {state.stage.value} | SR={state.eval_sr:.0%} | cost=${state.cost_usd:.4f}")


if __name__ == "__main__":
    main()
