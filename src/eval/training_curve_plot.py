#!/usr/bin/env python3
"""
training_curve_plot.py — Plots training loss curves for GR00T fine-tuning runs.

Parses Hugging Face Trainer log files (trainer_state.json) or text logs
and generates a dark-theme HTML plot suitable for the GTC talk and paper.

Usage:
    # From a single run directory (contains trainer_state.json)
    python src/eval/training_curve_plot.py --run-dir /tmp/finetune_1000_5k

    # Compare multiple runs
    python src/eval/training_curve_plot.py \
        --run-dirs /tmp/finetune_500_5k /tmp/finetune_1000_5k \
        --labels "500-demo" "1000-demo" \
        --output /tmp/training_curves.html

    # Mock mode (uses documented training numbers)
    python src/eval/training_curve_plot.py --mock --output /tmp/training_curves.html
"""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_trainer_state(run_dir: str) -> Optional[List[Dict]]:
    """Load loss data from HuggingFace trainer_state.json."""
    state_path = Path(run_dir) / "trainer_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            history = state.get("log_history", [])
            points = []
            for entry in history:
                if "loss" in entry and "step" in entry:
                    points.append({"step": entry["step"], "loss": entry["loss"]})
            if points:
                return points
        except Exception:
            pass

    # Try parsing text log
    log_path = Path(run_dir) / "training.log"
    if not log_path.exists():
        log_path = Path(run_dir).parent / "training.log"
    if log_path.exists():
        try:
            points = []
            for line in log_path.read_text().splitlines():
                if "'loss':" in line or '"loss":' in line:
                    # Parse lines like "{'loss': 0.456, 'step': 100, ...}"
                    try:
                        d = json.loads(line.replace("'", '"'))
                        if "loss" in d and "step" in d:
                            points.append({"step": d["step"], "loss": d["loss"]})
                    except Exception:
                        pass
            if points:
                return points
        except Exception:
            pass

    return None


def simulate_training_curve(
    n_steps: int,
    initial_loss: float,
    final_loss: float,
    noise_scale: float = 0.02,
    log_interval: int = 100,
    seed: int = 42,
) -> List[Dict]:
    """Generate a realistic-looking training curve using exponential decay + noise."""
    import random
    rng = random.Random(seed)

    points = []
    for step in range(0, n_steps + 1, log_interval):
        t = step / n_steps
        # Exponential decay with slight warmup
        if step < 200:
            warmup_factor = step / 200
        else:
            warmup_factor = 1.0
        base_loss = final_loss + (initial_loss - final_loss) * math.exp(-4 * t) * warmup_factor
        noise = rng.gauss(0, noise_scale * base_loss)
        loss = max(final_loss * 0.8, base_loss + noise)
        points.append({"step": step, "loss": round(loss, 4)})
    return points


def build_svg_path(points: List[Dict], w: int, h: int, pad: int) -> str:
    """Build an SVG polyline path from loss data, normalized to plot area."""
    if not points:
        return ""
    steps = [p["step"] for p in points]
    losses = [p["loss"] for p in points]
    min_step, max_step = 0, max(steps)
    min_loss, max_loss = min(losses) * 0.95, losses[0] * 1.05

    def tx(s: float) -> float:
        return pad + (s - min_step) / (max_step - min_step) * (w - 2 * pad)

    def ty(l: float) -> float:
        return h - pad - (l - min_loss) / (max_loss - min_loss) * (h - 2 * pad)

    path_pts = " ".join(f"{tx(p['step']):.1f},{ty(p['loss']):.1f}" for p in points)
    return path_pts, min_loss, max_loss, min_step, max_step


COLORS = ["#C74634", "#34D399", "#FBBF24", "#60A5FA", "#A78BFA"]


def make_html(
    run_labels: List[str],
    curves: List[List[Dict]],
    output_path: str,
) -> None:
    W, H, PAD = 700, 300, 40
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Compute global bounds
    all_losses = [p["loss"] for c in curves for p in c]
    all_steps = [p["step"] for c in curves for p in c]
    if not all_losses:
        return

    min_loss = min(all_losses) * 0.95
    max_loss = max(all_losses) * 1.05
    min_step = 0
    max_step = max(all_steps)

    def tx(s: float) -> float:
        return PAD + (s - min_step) / (max_step - min_step) * (W - 2 * PAD)

    def ty(l: float) -> float:
        return H - PAD - (l - min_loss) / (max_loss - min_loss) * (H - 2 * PAD)

    # Grid lines
    grid_lines = ""
    for y_tick in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        if min_loss <= y_tick <= max_loss:
            y = ty(y_tick)
            grid_lines += f'<line x1="{PAD}" y1="{y:.1f}" x2="{W - PAD}" y2="{y:.1f}" stroke="#2D2D30" stroke-width="1"/>'
            grid_lines += f'<text x="{PAD - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="9" fill="#6B7280">{y_tick:.1f}</text>'

    # X-axis ticks
    x_ticks = ""
    for step_tick in range(0, max_step + 1, max_step // 5):
        x = tx(step_tick)
        x_ticks += f'<line x1="{x:.1f}" y1="{H - PAD}" x2="{x:.1f}" y2="{H - PAD + 4}" stroke="#4B5563" stroke-width="1"/>'
        x_ticks += f'<text x="{x:.1f}" y="{H - PAD + 14}" text-anchor="middle" font-size="9" fill="#6B7280">{step_tick}</text>'

    # Curve polylines
    polylines = ""
    for idx, (label, curve) in enumerate(zip(run_labels, curves)):
        color = COLORS[idx % len(COLORS)]
        pts = " ".join(f"{tx(p['step']):.1f},{ty(p['loss']):.1f}" for p in curve)
        polylines += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
        # Mark final point
        last = curve[-1]
        fx, fy = tx(last["step"]), ty(last["loss"])
        polylines += f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="4" fill="{color}"/>'
        polylines += f'<text x="{fx + 8:.1f}" y="{fy + 4:.1f}" font-size="10" fill="{color}">{last["loss"]:.3f}</text>'

    # Legend
    legend_items = ""
    for idx, (label, curve) in enumerate(zip(run_labels, curves)):
        color = COLORS[idx % len(COLORS)]
        start_loss = curve[0]["loss"] if curve else 0
        end_loss = curve[-1]["loss"] if curve else 0
        legend_items += f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;">
          <div style="width:24px;height:3px;background:{color};border-radius:2px;"></div>
          <div>
            <div style="font-size:13px;color:#E5E7EB;font-weight:600;">{label}</div>
            <div style="font-size:11px;color:#9CA3AF;">{start_loss:.3f} → {end_loss:.3f} ({(1-end_loss/start_loss)*100:.0f}% reduction)</div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Training Curves — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111113; color: #E5E7EB; font-family: 'Segoe UI', system-ui, sans-serif; padding: 40px 20px; }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  h1 {{ font-size: 22px; color: #FFFFFF; margin-bottom: 4px; }}
  h2 {{ font-size: 11px; color: #C74634; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; }}
  .footer {{ color: #4B5563; font-size: 11px; margin-top: 32px; text-align: center; }}
  .card {{ background: #1C1C1E; border-radius: 10px; padding: 20px; margin-bottom: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h2>OCI Robot Cloud · GR00T Fine-Tuning</h2>
  <h1>Training Loss Curves</h1>

  <div class="card" style="margin-bottom:20px;">
    <svg width="{W}" height="{H}" style="display:block;">
      <!-- Background -->
      <rect width="{W}" height="{H}" fill="#1C1C1E"/>
      <!-- Grid -->
      {grid_lines}
      {x_ticks}
      <!-- Axes -->
      <line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H - PAD}" stroke="#4B5563" stroke-width="1"/>
      <line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{H - PAD}" stroke="#4B5563" stroke-width="1"/>
      <!-- Axis labels -->
      <text x="{W / 2:.0f}" y="{H - 2}" text-anchor="middle" font-size="10" fill="#6B7280">Training Steps</text>
      <text x="10" y="{H / 2:.0f}" text-anchor="middle" font-size="10" fill="#6B7280" transform="rotate(-90, 10, {H / 2:.0f})">Loss</text>
      <!-- Curves -->
      {polylines}
    </svg>
  </div>

  <div class="card">
    <div style="font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Run Summary</div>
    {legend_items}
  </div>

  <div class="footer">
    OCI Robot Cloud · Jun Qian · Generated {ts}
  </div>
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot GR00T training loss curves")
    parser.add_argument("--run-dir", help="Single run directory (has trainer_state.json)")
    parser.add_argument("--run-dirs", nargs="*", default=[])
    parser.add_argument("--labels", nargs="*", default=[])
    parser.add_argument("--output", default="/tmp/training_curves.html")
    parser.add_argument("--mock", action="store_true",
                        help="Use synthetic curves (500-demo=0.164 final, 1000-demo=0.099)")
    args = parser.parse_args()

    if args.mock:
        curves = [
            ("Baseline (random)", simulate_training_curve(500, 0.68, 0.68, noise_scale=0.15, seed=0)),
            ("500-demo BC, 5k steps", simulate_training_curve(5000, 0.68, 0.164, seed=1)),
            ("1000-demo BC, 5k steps", simulate_training_curve(5000, 0.68, 0.099, seed=2)),
        ]
    else:
        dirs = []
        if args.run_dir:
            dirs = [args.run_dir]
        elif args.run_dirs:
            dirs = args.run_dirs

        labels = list(args.labels)
        while len(labels) < len(dirs):
            labels.append(f"Run {len(labels) + 1}")

        curves = []
        for label, d in zip(labels, dirs):
            data = load_trainer_state(d)
            if data is None:
                print(f"WARNING: no training data found in {d}")
                data = []
            curves.append((label, data))

    run_labels = [c[0] for c in curves]
    curve_data = [c[1] for c in curves]

    # Console summary
    print()
    print("Training Curve Summary")
    print("─" * 40)
    for label, data in curves:
        if data:
            start = data[0]["loss"]
            end = data[-1]["loss"]
            print(f"  {label:35}  {start:.3f} → {end:.3f}  ({(1-end/start)*100:.0f}% reduction)")
    print()

    make_html(run_labels, curve_data, args.output)
    print(f"Plot written to: {args.output}")


if __name__ == "__main__":
    main()
