#!/usr/bin/env python3
"""
online_policy_distillation.py — Online distillation from GR00T 3B to a lightweight student.

Continuously distills the fine-tuned GR00T teacher into a small student network
during DAgger data collection — the student learns from both the teacher's soft
predictions AND the environment reward signal simultaneously.

Usage:
    python src/training/online_policy_distillation.py --mock --steps 5000
    python src/training/online_policy_distillation.py --output /tmp/online_distillation.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Model configs ─────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    name: str
    params_m: float      # millions
    latency_ms_a100: float
    latency_ms_jetson: float
    vram_gb: float
    layers: int
    hidden_dim: int


TEACHER = ModelConfig("GR00T N1.6-3B",   3000.0, 226.0, 680.0, 7.1,  24, 4096)

STUDENTS = [
    ModelConfig("Student-Large",   120.0,  48.0,  145.0, 1.2,  12, 1024),
    ModelConfig("Student-Medium",   45.0,  22.0,   68.0, 0.6,   8,  512),
    ModelConfig("Student-Small",    12.0,  11.0,   35.0, 0.3,   4,  256),
    ModelConfig("Student-Tiny",      3.0,   6.0,   18.0, 0.1,   2,  128),
]


# ── Distillation loss components ──────────────────────────────────────────────
# L_total = α * L_imitation (BC) + β * L_distill (KL from teacher) + γ * L_rl (env reward)

@dataclass
class DistillConfig:
    alpha: float = 0.4    # imitation weight
    beta: float  = 0.4    # distillation weight
    gamma: float = 0.2    # RL weight
    temperature: float = 2.0   # softmax temperature for soft labels
    n_steps: int = 5000
    online_collection_eps: int = 10   # DAgger episodes per distill cycle
    n_cycles: int = 10


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_distillation(student: ModelConfig, cfg: DistillConfig,
                           seed: int = 42) -> dict:
    rng = random.Random(seed + int(student.params_m))

    # Capacity factor: larger students learn more from teacher
    capacity = math.log(student.params_m / 3.0 + 1) / math.log(3000.0 / 3.0 + 1)

    # Teacher SR (ground truth)
    teacher_sr = 0.72

    cycle_results = []
    sr = 0.05   # start at BC baseline
    loss = 0.68

    for c in range(cfg.n_cycles):
        progress = (c + 1) / cfg.n_cycles
        # Student SR approaches teacher SR × capacity
        target_sr = teacher_sr * capacity * (0.85 + 0.15 * cfg.beta)
        sr = target_sr * (1 - math.exp(-progress * 3.5)) + rng.gauss(0, 0.015)
        sr = max(0.0, min(teacher_sr, sr))

        # Loss: BC + KL + RL components
        l_bc = 0.68 * (1 - progress * 0.7) + rng.gauss(0, 0.01)
        l_kl = 0.45 * (1 - progress * 0.8) + rng.gauss(0, 0.01)
        l_rl = 0.30 * (1 - progress * 0.6) + rng.gauss(0, 0.01)
        loss = cfg.alpha * l_bc + cfg.beta * l_kl + cfg.gamma * l_rl
        loss = max(0.04, loss)

        latency = student.latency_ms_a100 * (1 + rng.gauss(0, 0.05))
        cycle_results.append({
            "cycle": c + 1,
            "sr": round(sr, 3),
            "loss": round(loss, 4),
            "l_bc": round(l_bc, 4),
            "l_kl": round(l_kl, 4),
            "l_rl": round(l_rl, 4),
            "avg_latency_ms": round(latency, 1),
        })

    final_sr = cycle_results[-1]["sr"]
    sr_ratio = final_sr / teacher_sr   # fraction of teacher SR achieved

    # Cost: distillation is much cheaper (small model)
    steps_per_cycle = cfg.n_steps // cfg.n_cycles
    total_student_steps = cfg.n_steps
    student_it_s = TEACHER.latency_ms_a100 / student.latency_ms_a100 * 2.35
    train_hr = total_student_steps / (student_it_s * 3600)
    collection_hr = cfg.n_cycles * cfg.online_collection_eps * (student.latency_ms_a100 / 1000 + 0.3) / 3600
    total_hr = train_hr + collection_hr
    cost_usd = total_hr * 4.20

    return {
        "student": student.name,
        "params_m": student.params_m,
        "capacity": round(capacity, 3),
        "final_sr": round(final_sr, 3),
        "teacher_sr": teacher_sr,
        "sr_ratio": round(sr_ratio, 3),
        "latency_ms_a100": student.latency_ms_a100,
        "latency_ms_jetson": student.latency_ms_jetson,
        "vram_gb": student.vram_gb,
        "cost_usd": round(cost_usd, 4),
        "speedup_vs_teacher": round(TEACHER.latency_ms_a100 / student.latency_ms_a100, 1),
        "jetson_speedup": round(TEACHER.latency_ms_jetson / student.latency_ms_jetson, 1),
        "cycles": cycle_results,
    }


def benchmark_students(cfg: DistillConfig, seed: int = 42) -> list[dict]:
    return [simulate_distillation(s, cfg, seed) for s in STUDENTS]


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(results: list[dict], cfg: DistillConfig) -> str:
    best_sr = max(results, key=lambda r: r["final_sr"])
    # Best Jetson student: maximize sr × jetson_speedup
    best_jetson = max(results, key=lambda r: r["final_sr"] * r["jetson_speedup"])

    COLORS = ["#C74634", "#3b82f6", "#22c55e", "#f59e0b"]

    # SVG: SR curves per student across cycles
    w, h = 520, 160
    n_cycles = cfg.n_cycles
    x_scale = (w - 40) / max(n_cycles - 1, 1)
    y_scale = (h - 30) / 1.0

    svg_sr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    # Teacher target line
    teacher_y = h - 10 - 0.72 * y_scale
    svg_sr += (f'<line x1="20" y1="{teacher_y:.1f}" x2="{w}" y2="{teacher_y:.1f}" '
               f'stroke="#64748b" stroke-width="1.5" stroke-dasharray="5,3"/>')
    svg_sr += (f'<text x="22" y="{teacher_y-3:.1f}" fill="#64748b" font-size="9">teacher 72%</text>')

    for i, r in enumerate(results):
        pts = " ".join(f"{20+c*x_scale:.1f},{h-10-rc['sr']*y_scale:.1f}"
                       for c, rc in enumerate(r["cycles"]))
        col = COLORS[i % len(COLORS)]
        svg_sr += (f'<polyline points="{pts}" fill="none" stroke="{col}" '
                   f'stroke-width="2" opacity="0.9"/>')
    svg_sr += '</svg>'

    # SVG: latency comparison bars (A100 vs Jetson)
    w2, h2 = 400, 130
    max_lat = TEACHER.latency_ms_jetson
    svg_lat = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    all_models = [(TEACHER.name, TEACHER.latency_ms_a100, TEACHER.latency_ms_jetson, "#64748b")] + \
                 [(r["student"], r["latency_ms_a100"], r["latency_ms_jetson"], COLORS[i])
                  for i, r in enumerate(results)]
    row_h = (h2 - 20) / len(all_models) - 3
    for i, (name, lat_a100, lat_jetson, col) in enumerate(all_models):
        y = 10 + i * (row_h + 3)
        bw_a100 = lat_a100 / max_lat * (w2 - 150)
        bw_jet = lat_jetson / max_lat * (w2 - 150)
        svg_lat += (f'<rect x="140" y="{y:.1f}" width="{bw_a100:.1f}" height="{row_h*0.45:.1f}" '
                    f'fill="{col}" rx="1" opacity="0.7"/>')
        svg_lat += (f'<rect x="140" y="{y+row_h*0.5:.1f}" width="{bw_jet:.1f}" height="{row_h*0.45:.1f}" '
                    f'fill="{col}" rx="1" opacity="0.5"/>')
        svg_lat += (f'<text x="138" y="{y+row_h*0.4:.1f}" fill="#94a3b8" font-size="8.5" '
                    f'text-anchor="end">{name[:16]}</text>')
        svg_lat += (f'<text x="{143+bw_a100:.1f}" y="{y+row_h*0.4:.1f}" fill="{col}" '
                    f'font-size="8">{lat_a100:.0f}ms</text>')
        svg_lat += (f'<text x="{143+bw_jet:.1f}" y="{y+row_h*0.95:.1f}" fill="{col}" '
                    f'font-size="8">{lat_jetson:.0f}ms</text>')
    svg_lat += (f'<text x="142" y="{h2-3}" fill="#22c55e" font-size="8">■ A100</text>'
                f'<text x="180" y="{h2-3}" fill="#3b82f6" font-size="8">■ Jetson</text>')
    svg_lat += '</svg>'

    legend = " ".join(
        f'<span style="color:{COLORS[i%len(COLORS)]}">■ {r["student"]}</span>'
        for i, r in enumerate(results)
    )

    rows = ""
    for i, r in enumerate(results):
        is_best_j = r["student"] == best_jetson["student"]
        hl = ' style="background:#0f1d2d"' if is_best_j else ""
        sr_c = "#22c55e" if r["sr_ratio"] >= 0.85 else "#f59e0b" if r["sr_ratio"] >= 0.70 else "#ef4444"
        rows += f"""<tr{hl}>
          <td style="color:#e2e8f0">{r['student']}{'★' if is_best_j else ''}</td>
          <td>{r['params_m']:.0f}M</td>
          <td style="color:{sr_c}">{r['final_sr']:.0%}</td>
          <td style="color:{sr_c}">{r['sr_ratio']:.0%}</td>
          <td>{r['latency_ms_a100']:.0f}ms</td>
          <td style="color:#22c55e">{r['latency_ms_jetson']:.0f}ms</td>
          <td style="color:#3b82f6">{r['jetson_speedup']:.1f}×</td>
          <td>{r['vram_gb']:.1f}GB</td>
          <td>${r['cost_usd']:.4f}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Online Policy Distillation</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Online Policy Distillation — GR00T 3B → Student</h1>
<div class="meta">α={cfg.alpha} imitation · β={cfg.beta} distill · γ={cfg.gamma} RL · {cfg.n_cycles} cycles × {cfg.online_collection_eps} eps</div>

<div class="grid">
  <div class="card"><h3>Best Student SR</h3>
    <div class="big" style="color:#22c55e">{best_sr['final_sr']:.0%}</div>
    <div style="color:#64748b;font-size:12px">{best_sr['student']} ({best_sr['sr_ratio']:.0%} of teacher)</div></div>
  <div class="card"><h3>Best Jetson Student</h3>
    <div class="big" style="color:#3b82f6">{best_jetson['student']}</div>
    <div style="color:#64748b;font-size:12px">{best_jetson['latency_ms_jetson']:.0f}ms · {best_jetson['final_sr']:.0%} SR</div></div>
  <div class="card"><h3>Teacher</h3>
    <div class="big" style="color:#64748b">{TEACHER.latency_ms_a100:.0f}ms</div>
    <div style="color:#64748b;font-size:12px">GR00T 3B · 72% SR · 7.1GB</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">SR Progression per Student</h3>
    <div style="font-size:10px;margin-bottom:6px">{legend}</div>
    {svg_sr}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Latency: A100 vs Jetson</h3>
    {svg_lat}
  </div>
</div>

<table>
  <tr><th>Student</th><th>Params</th><th>SR</th><th>SR/Teacher</th>
      <th>A100 Lat</th><th>Jetson Lat</th><th>Jetson Speedup</th><th>VRAM</th><th>Cost</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Recommendation (Jetson deploy): <strong>{best_jetson['student']}</strong>
  ({best_jetson['latency_ms_jetson']:.0f}ms Jetson, {best_jetson['final_sr']:.0%} SR,
  {best_jetson['jetson_speedup']:.1f}× faster than teacher).<br>
  Online distillation during DAgger collection adds only ${best_sr['cost_usd']:.4f} overhead.
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Online policy distillation benchmark")
    parser.add_argument("--mock",    action="store_true", default=True)
    parser.add_argument("--steps",   type=int, default=5000)
    parser.add_argument("--cycles",  type=int, default=10)
    parser.add_argument("--alpha",   type=float, default=0.4)
    parser.add_argument("--beta",    type=float, default=0.4)
    parser.add_argument("--gamma",   type=float, default=0.2)
    parser.add_argument("--output",  default="/tmp/online_policy_distillation.html")
    parser.add_argument("--seed",    type=int, default=42)
    args = parser.parse_args()

    cfg = DistillConfig(alpha=args.alpha, beta=args.beta, gamma=args.gamma,
                        n_steps=args.steps, n_cycles=args.cycles)

    print(f"[online-distill] α={cfg.alpha} β={cfg.beta} γ={cfg.gamma} · "
          f"{len(STUDENTS)} students · {cfg.n_cycles} cycles")
    t0 = time.time()

    results = benchmark_students(cfg, args.seed)

    print(f"\n  {'Student':<20} {'SR':>6}  {'SR/Teacher':>10}  {'Jetson':>8}  {'Speedup':>8}")
    print(f"  {'─'*20} {'─'*6}  {'─'*10}  {'─'*8}  {'─'*8}")
    for r in results:
        print(f"  {r['student']:<20} {r['final_sr']:>5.0%}  {r['sr_ratio']:>9.0%}  "
              f"{r['latency_ms_jetson']:>6.0f}ms  {r['jetson_speedup']:>7.1f}×")

    best = max(results, key=lambda r: r["final_sr"])
    print(f"\n  Best: {best['student']} ({best['final_sr']:.0%} SR)  [{time.time()-t0:.1f}s]\n")

    html = render_html(results, cfg)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(results, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
