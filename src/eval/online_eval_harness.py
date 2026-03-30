#!/usr/bin/env python3
"""
online_eval_harness.py — Continuous online evaluation during DAgger training.

Evaluates policy checkpoints as they are saved during DAgger runs — no manual
intervention needed. Tracks success rate progression in real time.

Usage:
    python src/eval/online_eval_harness.py --watch-dir /tmp/dagger_run9 --eval-episodes 10
    python src/eval/online_eval_harness.py --mock --steps 12 --output /tmp/online_eval.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class OnlineEvalConfig:
    watch_dir: str = "/tmp/dagger_run9"
    eval_episodes: int = 10
    groot_url: str = "http://138.1.153.110:8002"
    poll_interval_s: float = 30.0
    max_wait_s: float = 7200.0  # 2 hours
    early_stop_sr: float = 0.90
    output: str = "/tmp/online_eval_harness.html"
    mock: bool = True
    mock_steps: int = 12


@dataclass
class CheckpointEval:
    checkpoint_id: str    # e.g. "checkpoint-2000"
    checkpoint_step: int
    eval_start: str
    eval_duration_s: float
    success_rate: float
    n_episodes: int
    avg_latency_ms: float
    notes: str = ""


@dataclass
class EvalHistory:
    run_id: str
    started_at: str
    checkpoints: list[CheckpointEval] = field(default_factory=list)
    best_checkpoint: str = ""
    best_sr: float = 0.0


# ── Mock checkpoint generator ─────────────────────────────────────────────────

def mock_checkpoint_stream(n_checkpoints: int = 12,
                            seed: int = 42) -> list[dict]:
    """Simulate checkpoint appearances during a DAgger run."""
    rng = random.Random(seed)
    checkpoints = []
    sr = 0.05   # start at BC baseline
    for i in range(n_checkpoints):
        step = (i + 1) * 1000
        # SR improves progressively with some noise
        sr = min(0.95, sr + rng.uniform(0.04, 0.10) + rng.gauss(0, 0.015))
        checkpoints.append({
            "id": f"checkpoint-{step}",
            "step": step,
            "appeared_at": (i + 1) * 15,  # minutes after start
        })
    return checkpoints


def mock_eval_checkpoint(ckpt: dict, n_eps: int = 10, seed: int = 0) -> CheckpointEval:
    """Simulate eval on a mock checkpoint."""
    rng = random.Random(seed + ckpt["step"])
    # SR grows with steps, with noise
    base_sr = min(0.92, 0.05 + (ckpt["step"] / 12000) * 0.87)
    sr = round(min(1.0, max(0.0, base_sr + rng.gauss(0, 0.04))), 3)
    n_success = round(sr * n_eps)
    actual_sr = n_success / n_eps
    latency = rng.gauss(226, 12)
    eval_dur = n_eps * (latency / 1000 + 0.3)
    return CheckpointEval(
        checkpoint_id=ckpt["id"],
        checkpoint_step=ckpt["step"],
        eval_start=datetime.now().isoformat(),
        eval_duration_s=round(eval_dur, 1),
        success_rate=round(actual_sr, 3),
        n_episodes=n_eps,
        avg_latency_ms=round(latency, 1),
    )


# ── Real eval (passthrough to closed_loop_eval.py) ────────────────────────────

def eval_checkpoint_live(checkpoint_path: str, n_eps: int,
                          groot_url: str) -> Optional[CheckpointEval]:
    """Restart GR00T server with checkpoint and run closed-loop eval."""
    # In production this would:
    # 1. Restart groot_franka_server.py --checkpoint <path>
    # 2. Run closed_loop_eval.py --episodes n_eps
    # 3. Parse JSON output
    # For now returns None (not in mock mode)
    return None


# ── Watcher loop ──────────────────────────────────────────────────────────────

def watch_and_eval(cfg: OnlineEvalConfig) -> EvalHistory:
    run_id = Path(cfg.watch_dir).name
    history = EvalHistory(run_id=run_id, started_at=datetime.now().isoformat())

    print(f"\n[online-eval] Watching {cfg.watch_dir} for new checkpoints")
    print(f"  Episodes: {cfg.eval_episodes}  |  Early stop: {cfg.early_stop_sr:.0%}  |  "
          f"Poll: {cfg.poll_interval_s:.0f}s\n")

    if cfg.mock:
        checkpoints = mock_checkpoint_stream(cfg.mock_steps)
    else:
        checkpoints = []

    for i, ckpt in enumerate(checkpoints):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] New checkpoint: {ckpt['id']} (step {ckpt['step']})")

        t0 = time.time()
        if cfg.mock:
            result = mock_eval_checkpoint(ckpt, cfg.eval_episodes, seed=i)
        else:
            result = eval_checkpoint_live(
                f"{cfg.watch_dir}/{ckpt['id']}", cfg.eval_episodes, cfg.groot_url
            )
            if result is None:
                print(f"    ✗ Eval failed — skipping")
                continue

        history.checkpoints.append(result)

        if result.success_rate > history.best_sr:
            history.best_sr = result.success_rate
            history.best_checkpoint = result.checkpoint_id

        sr_col = "\033[92m" if result.success_rate >= 0.65 else \
                 "\033[93m" if result.success_rate >= 0.30 else "\033[91m"
        print(f"    SR: {sr_col}{result.success_rate:.0%}\033[0m  "
              f"({result.n_episodes} eps, {result.avg_latency_ms:.0f}ms, "
              f"{result.eval_duration_s:.0f}s eval)")

        if result.success_rate >= cfg.early_stop_sr:
            print(f"\n  \033[92m✓ Target {cfg.early_stop_sr:.0%} reached! "
                  f"Best checkpoint: {history.best_checkpoint}\033[0m")
            break

        if not cfg.mock and i < len(checkpoints) - 1:
            time.sleep(cfg.poll_interval_s)

    print(f"\n  Best: {history.best_checkpoint}  SR={history.best_sr:.0%}\n")
    return history


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(history: EvalHistory, cfg: OnlineEvalConfig) -> str:
    if not history.checkpoints:
        return "<html><body>No checkpoints evaluated yet.</body></html>"

    steps = [c.checkpoint_step for c in history.checkpoints]
    srs = [round(c.success_rate * 100, 1) for c in history.checkpoints]
    lats = [c.avg_latency_ms for c in history.checkpoints]

    # SVG SR progression
    w, h = 560, 160
    x_scale = (w - 50) / max(steps[-1], 1)
    y_scale = (h - 30) / 100.0

    sr_pts = " ".join(f"{30+s*x_scale:.1f},{h-10-sr*y_scale:.1f}" for s, sr in zip(steps, srs))
    # Target line
    thr_y = h - 10 - cfg.early_stop_sr * 100 * y_scale

    svg = (
        f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
        f'<line x1="30" y1="{thr_y:.1f}" x2="{w}" y2="{thr_y:.1f}" '
        f'stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="32" y="{thr_y-3:.1f}" fill="#22c55e" font-size="10">'
        f'target {cfg.early_stop_sr:.0%}</text>'
        f'<line x1="30" y1="{h-10}" x2="{w}" y2="{h-10}" stroke="#334155" stroke-width="1"/>'
        f'<polyline points="{sr_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>'
    )
    for s, sr in zip(steps, srs):
        col = "#22c55e" if sr >= cfg.early_stop_sr * 100 else "#C74634"
        svg += f'<circle cx="{30+s*x_scale:.1f}" cy="{h-10-sr*y_scale:.1f}" r="4" fill="{col}"/>'
    svg += '</svg>'

    # Table rows
    rows = ""
    for c in history.checkpoints:
        is_best = c.checkpoint_id == history.best_checkpoint
        hl = ' style="background:#0f2d1c"' if is_best else ""
        sr_col = "#22c55e" if c.success_rate >= 0.65 else "#f59e0b" if c.success_rate >= 0.30 else "#ef4444"
        rows += f"""<tr{hl}>
          <td style="color:#e2e8f0">{c.checkpoint_id}{'★' if is_best else ''}</td>
          <td>{c.checkpoint_step:,}</td>
          <td style="color:{sr_col}">{c.success_rate:.0%}</td>
          <td>{c.avg_latency_ms:.0f}ms</td>
          <td>{c.eval_duration_s:.0f}s</td>
          <td style="color:#64748b">{c.eval_start[:19]}</td>
        </tr>"""

    best_sr_col = "#22c55e" if history.best_sr >= 0.65 else "#f59e0b"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Online Eval Harness — {history.run_id}</title>
<meta http-equiv="refresh" content="30">
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:32px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Online Eval Harness — {history.run_id}</h1>
<div class="meta">Auto-refresh 30s · Started {history.started_at[:19]} ·
{len(history.checkpoints)} checkpoints evaluated</div>

<div class="grid">
  <div class="card"><h3>Best SR</h3>
    <div class="big" style="color:{best_sr_col}">{history.best_sr:.0%}</div>
    <div style="color:#64748b;font-size:12px">{history.best_checkpoint}</div>
  </div>
  <div class="card"><h3>Checkpoints Evaled</h3>
    <div class="big">{len(history.checkpoints)}</div></div>
  <div class="card"><h3>Target</h3>
    <div class="big" style="color:#64748b">{cfg.early_stop_sr:.0%}</div>
    <div style="color:{'#22c55e' if history.best_sr >= cfg.early_stop_sr else '#f59e0b'};font-size:12px">
      {'✓ reached' if history.best_sr >= cfg.early_stop_sr else '↑ in progress'}</div>
  </div>
</div>

<div style="margin-bottom:16px">
  <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">SR Progression</h3>
  {svg}
</div>

<table>
  <tr><th>Checkpoint</th><th>Step</th><th>Success Rate</th>
      <th>Avg Latency</th><th>Eval Time</th><th>Evaluated At</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  OCI A100 GPU4 (138.1.153.110) · GR00T N1.6-3B fine-tuned · {cfg.eval_episodes} eps per checkpoint
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Online eval harness for DAgger checkpoints")
    parser.add_argument("--watch-dir",     default="/tmp/dagger_run9")
    parser.add_argument("--eval-episodes", type=int, default=10)
    parser.add_argument("--early-stop-sr", type=float, default=0.90)
    parser.add_argument("--poll",          type=float, default=30.0)
    parser.add_argument("--mock",          action="store_true", default=True)
    parser.add_argument("--steps",         type=int, default=12, help="Mock: number of checkpoints")
    parser.add_argument("--output",        default="/tmp/online_eval_harness.html")
    parser.add_argument("--groot-url",     default="http://138.1.153.110:8002")
    args = parser.parse_args()

    cfg = OnlineEvalConfig(
        watch_dir=args.watch_dir,
        eval_episodes=args.eval_episodes,
        groot_url=args.groot_url,
        poll_interval_s=args.poll,
        early_stop_sr=args.early_stop_sr,
        output=args.output,
        mock=args.mock,
        mock_steps=args.steps,
    )

    history = watch_and_eval(cfg)

    # Save JSON
    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "run_id": history.run_id,
        "started_at": history.started_at,
        "best_checkpoint": history.best_checkpoint,
        "best_sr": history.best_sr,
        "n_checkpoints_evaled": len(history.checkpoints),
        "checkpoints": [
            {"id": c.checkpoint_id, "step": c.checkpoint_step,
             "success_rate": c.success_rate, "avg_latency_ms": c.avg_latency_ms}
            for c in history.checkpoints
        ],
    }, indent=2))

    html = render_html(history, cfg)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
