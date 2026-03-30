#!/usr/bin/env python3
"""
online_learning_dashboard.py — Real-time dashboard for DAgger / online learning runs.

Monitors active online learning jobs: current SR, DAgger round progress, data buffer
growth, model improvement rate, intervention frequency, and training health.

Usage:
    python src/api/online_learning_dashboard.py --mock --output /tmp/online_learning_dashboard.html
    python src/api/online_learning_dashboard.py --run-dir /tmp/dagger_run9 --port 8072
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class DaggerRound:
    round_num: int
    episodes_collected: int
    interventions: int
    intervention_rate: float   # interventions / episodes
    new_demos_added: int
    buffer_size: int
    sr_before: float
    sr_after: float
    sr_delta: float
    train_loss_start: float
    train_loss_end: float
    train_steps: int
    wall_time_s: float
    status: str  # running / complete / failed


@dataclass
class LiveMetrics:
    run_id: str
    current_round: int
    total_rounds_planned: int
    current_sr: float
    target_sr: float
    buffer_total: int
    total_interventions: int
    cumulative_wall_h: float
    est_completion_h: float
    rounds: list[DaggerRound] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_dagger_run(run_id: str = "dagger_run9", n_rounds: int = 12,
                        seed: int = 42) -> LiveMetrics:
    rng = random.Random(seed)
    rounds = []

    sr = 0.05           # starting SR (BC baseline)
    buffer_size = 1000  # initial BC demos
    cumulative_time = 0.0
    target_sr = 0.90

    for r in range(1, n_rounds + 1):
        # Diminishing returns on SR gain per round
        max_gain = max(0.01, (target_sr - sr) * 0.35)
        sr_gain = rng.uniform(max_gain * 0.5, max_gain) if sr < target_sr else rng.gauss(0, 0.01)

        episodes = rng.randint(18, 25)
        inv_rate = max(0.05, 0.65 - r * 0.05 + rng.gauss(0, 0.05))
        interventions = int(episodes * inv_rate)
        new_demos = interventions + rng.randint(2, 6)  # some clean demos too
        buffer_size += new_demos

        loss_start = 0.12 + rng.gauss(0, 0.01)
        loss_end   = max(0.04, loss_start * (0.65 + rng.gauss(0, 0.05)))
        train_steps = rng.randint(800, 1200)
        wall_time = episodes * 45 + train_steps * 0.3 + rng.gauss(0, 60)
        cumulative_time += wall_time

        sr_before = sr
        sr_after  = min(0.99, max(0.0, sr + sr_gain + rng.gauss(0, 0.015)))
        sr = sr_after

        status = "complete" if r < n_rounds else "running"

        rounds.append(DaggerRound(
            round_num=r,
            episodes_collected=episodes,
            interventions=interventions,
            intervention_rate=round(inv_rate, 3),
            new_demos_added=new_demos,
            buffer_size=buffer_size,
            sr_before=round(sr_before, 4),
            sr_after=round(sr_after, 4),
            sr_delta=round(sr_after - sr_before, 4),
            train_loss_start=round(loss_start, 4),
            train_loss_end=round(loss_end, 4),
            train_steps=train_steps,
            wall_time_s=round(wall_time, 1),
            status=status,
        ))

    current_sr = rounds[-1].sr_after
    total_interventions = sum(r.interventions for r in rounds)
    time_per_round = cumulative_time / n_rounds
    rounds_remaining = total_rounds_planned = n_rounds
    est_remaining = time_per_round * max(0, total_rounds_planned - n_rounds)

    return LiveMetrics(
        run_id=run_id,
        current_round=n_rounds,
        total_rounds_planned=total_rounds_planned,
        current_sr=round(current_sr, 4),
        target_sr=target_sr,
        buffer_total=buffer_size,
        total_interventions=total_interventions,
        cumulative_wall_h=round(cumulative_time / 3600, 2),
        est_completion_h=round(est_remaining / 3600, 2),
        rounds=rounds,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(metrics: LiveMetrics) -> str:
    rounds = metrics.rounds
    sr_pct = metrics.current_sr * 100
    target_pct = metrics.target_sr * 100
    progress_pct = min(100, sr_pct / target_pct * 100)

    sr_col = "#22c55e" if sr_pct >= target_pct * 0.9 else "#f59e0b" if sr_pct >= target_pct * 0.6 else "#ef4444"

    # SVG: SR over rounds
    w, h = 520, 160
    n = len(rounds)
    x_scale = (w - 50) / max(n - 1, 1)
    y_scale = (h - 30) / 1.0

    svg_sr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_sr += f'<line x1="40" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    # Target line
    ty = h - 20 - metrics.target_sr * y_scale
    svg_sr += (f'<line x1="40" y1="{ty:.1f}" x2="{w}" y2="{ty:.1f}" '
               f'stroke="#22c55e" stroke-width="1" stroke-dasharray="5,3" opacity="0.6"/>')
    svg_sr += f'<text x="43" y="{ty-3:.1f}" fill="#22c55e" font-size="8.5">target {target_pct:.0f}%</text>'

    # SR before / after lines
    pts_before = " ".join(
        f"{40+i*x_scale:.1f},{h-20-r.sr_before*y_scale:.1f}" for i, r in enumerate(rounds))
    pts_after = " ".join(
        f"{40+i*x_scale:.1f},{h-20-r.sr_after*y_scale:.1f}" for i, r in enumerate(rounds))

    svg_sr += f'<polyline points="{pts_before}" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="3,2" opacity="0.7"/>'
    svg_sr += f'<polyline points="{pts_after}" fill="none" stroke="#3b82f6" stroke-width="2" opacity="0.9"/>'

    # Mark last point
    last_r = rounds[-1]
    last_x = 40 + (n-1) * x_scale
    last_y = h - 20 - last_r.sr_after * y_scale
    svg_sr += f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="#C74634"/>'
    svg_sr += '</svg>'

    # SVG: buffer growth + intervention rate dual axis
    w2, h2 = 520, 160
    max_buf = max(r.buffer_size for r in rounds) * 1.1
    svg_buf = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    svg_buf += f'<line x1="40" y1="{h2-20}" x2="{w2-40}" y2="{h2-20}" stroke="#334155" stroke-width="1"/>'

    # Buffer area fill
    buf_pts = " ".join(
        f"{40+i*x_scale:.1f},{h2-20-r.buffer_size/max_buf*(h2-30):.1f}"
        for i, r in enumerate(rounds))
    buf_pts_closed = f"40,{h2-20} {buf_pts} {40+(n-1)*x_scale:.1f},{h2-20}"
    svg_buf += f'<polygon points="{buf_pts_closed}" fill="#3b82f6" opacity="0.15"/>'
    svg_buf += f'<polyline points="{buf_pts}" fill="none" stroke="#3b82f6" stroke-width="2"/>'

    # Intervention rate bars
    bar_width = x_scale * 0.4
    for i, r in enumerate(rounds):
        bh = r.intervention_rate * (h2 - 30)
        x = 40 + i * x_scale - bar_width / 2
        col = "#ef4444" if r.intervention_rate > 0.5 else "#f59e0b" if r.intervention_rate > 0.3 else "#22c55e"
        svg_buf += (f'<rect x="{x:.1f}" y="{h2-20-bh:.1f}" width="{bar_width:.1f}" '
                    f'height="{bh:.1f}" fill="{col}" opacity="0.6" rx="1"/>')

    svg_buf += '</svg>'

    # Round table rows
    rows = ""
    for r in rounds:
        delta_col = "#22c55e" if r.sr_delta > 0.02 else "#f59e0b" if r.sr_delta > 0 else "#ef4444"
        status_col = {"complete": "#22c55e", "running": "#3b82f6", "failed": "#ef4444"}.get(r.status, "#94a3b8")
        rows += (f'<tr>'
                 f'<td style="color:#64748b">{r.round_num}</td>'
                 f'<td style="color:#e2e8f0">{r.episodes_collected}</td>'
                 f'<td style="color:#f59e0b">{r.interventions} ({r.intervention_rate*100:.0f}%)</td>'
                 f'<td style="color:#94a3b8">{r.new_demos_added}</td>'
                 f'<td style="color:#64748b">{r.buffer_size:,}</td>'
                 f'<td style="color:#94a3b8">{r.sr_before*100:.1f}%</td>'
                 f'<td style="color:#3b82f6">{r.sr_after*100:.1f}%</td>'
                 f'<td style="color:{delta_col}">{r.sr_delta*100:+.1f}%</td>'
                 f'<td style="color:#64748b">{r.train_steps:,}</td>'
                 f'<td style="color:{status_col}">{r.status}</td>'
                 f'</tr>')

    progress_bar = (f'<div style="background:#0f172a;border-radius:4px;height:12px;width:100%;margin:8px 0">'
                    f'<div style="background:{sr_col};height:12px;border-radius:4px;'
                    f'width:{progress_pct:.0f}%"></div></div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Online Learning Dashboard</title>
<meta http-equiv="refresh" content="30">
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:26px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Online Learning Dashboard</h1>
<div class="meta">
  Run: {metrics.run_id} ·
  Round {metrics.current_round}/{metrics.total_rounds_planned} ·
  Auto-refresh 30s
</div>

<div class="grid">
  <div class="card"><h3>Current SR</h3>
    <div class="big" style="color:{sr_col}">{sr_pct:.1f}%</div>
    <div style="color:#64748b;font-size:10px">target {target_pct:.0f}%</div>
    {progress_bar}
  </div>
  <div class="card"><h3>Buffer Size</h3>
    <div class="big" style="color:#3b82f6">{metrics.buffer_total:,}</div>
    <div style="color:#64748b;font-size:10px">demos</div>
  </div>
  <div class="card"><h3>Interventions</h3>
    <div class="big" style="color:#f59e0b">{metrics.total_interventions}</div>
    <div style="color:#64748b;font-size:10px">total operator</div>
  </div>
  <div class="card"><h3>Wall Time</h3>
    <div class="big" style="color:#94a3b8">{metrics.cumulative_wall_h:.1f}h</div>
    <div style="color:#64748b;font-size:10px">elapsed</div>
  </div>
</div>

<div class="charts">
  <div>
    <h3 class="sec">Success Rate over DAgger Rounds</h3>
    {svg_sr}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Blue = SR after training · Gray = SR before · Red dot = current
    </div>
  </div>
  <div>
    <h3 class="sec">Buffer Growth (blue) + Intervention Rate (bars)</h3>
    {svg_buf}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Bars: green &lt;30% · yellow 30-50% · red &gt;50% intervention rate
    </div>
  </div>
</div>

<h3 class="sec">DAgger Round History</h3>
<table>
  <tr><th>Round</th><th>Episodes</th><th>Interventions</th><th>New Demos</th>
      <th>Buffer</th><th>SR Before</th><th>SR After</th><th>Δ SR</th><th>Steps</th><th>Status</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Intervention rate ↓ = policy improving (fewer corrections needed) ·
  Target: &lt;15% intervention rate at SR 90%
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Online learning / DAgger dashboard")
    parser.add_argument("--mock",       action="store_true", default=True)
    parser.add_argument("--run-dir",    default="")
    parser.add_argument("--run-id",     default="dagger_run9")
    parser.add_argument("--n-rounds",   type=int, default=12)
    parser.add_argument("--output",     default="/tmp/online_learning_dashboard.html")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    print(f"[ol-dashboard] Run: {args.run_id}  ({args.n_rounds} rounds)")
    t0 = time.time()

    metrics = simulate_dagger_run(args.run_id, args.n_rounds, args.seed)

    print(f"\n  {'Round':>6} {'SR Before':>10} {'SR After':>10} {'Δ SR':>8} {'Inv%':>7}  Status")
    print(f"  {'─'*6} {'─'*10} {'─'*10} {'─'*8} {'─'*7}  {'─'*8}")
    for r in metrics.rounds:
        print(f"  {r.round_num:>6} {r.sr_before*100:>9.1f}% {r.sr_after*100:>9.1f}% "
              f"{r.sr_delta*100:>+7.1f}% {r.intervention_rate*100:>6.0f}%  {r.status}")

    print(f"\n  Current SR: {metrics.current_sr*100:.1f}%  Target: {metrics.target_sr*100:.0f}%")
    print(f"  Buffer: {metrics.buffer_total:,} demos  Interventions: {metrics.total_interventions}")
    print(f"  Wall time: {metrics.cumulative_wall_h:.1f}h")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(metrics)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "run_id": metrics.run_id,
        "current_round": metrics.current_round,
        "current_sr": metrics.current_sr,
        "target_sr": metrics.target_sr,
        "buffer_total": metrics.buffer_total,
        "total_interventions": metrics.total_interventions,
        "cumulative_wall_h": metrics.cumulative_wall_h,
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
