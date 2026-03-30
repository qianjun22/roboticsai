#!/usr/bin/env python3
"""
hyperparameter_sensitivity_analyzer.py — Hyperparameter sensitivity analysis for GR00T fine-tuning.

Performs Sobol-style sensitivity analysis on key hyperparameters to identify which ones
most impact MAE and SR, guiding where to focus HPO budget.

Usage:
    python src/training/hyperparameter_sensitivity_analyzer.py --mock --output /tmp/hp_sensitivity.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Hyperparameter space ───────────────────────────────────────────────────────

HP_SPACE = [
    # (name, display_name, lo, hi, log_scale, sensitivity_true_mae, sensitivity_true_sr)
    ("learning_rate",     "Learning Rate",      1e-5, 1e-3, True,  0.42, 0.38),
    ("lora_rank",         "LoRA Rank",          4,    64,   False, 0.31, 0.28),
    ("batch_size",        "Batch Size",         1,    16,   False, 0.18, 0.15),
    ("n_steps",           "Training Steps",     500,  10000,True,  0.35, 0.40),
    ("warmup_steps",      "Warmup Steps",       0,    500,  False, 0.08, 0.07),
    ("weight_decay",      "Weight Decay",       0.0,  0.1,  False, 0.12, 0.10),
    ("dropout",           "Dropout",            0.0,  0.3,  False, 0.09, 0.08),
    ("grad_clip",         "Grad Clip Norm",     0.5,  5.0,  False, 0.14, 0.12),
    ("action_chunk_size", "Action Chunk Size",  1,    16,   False, 0.22, 0.25),
    ("n_demos",           "Num Demos",          100,  5000, True,  0.45, 0.50),
]

# Sobol-style first-order sensitivity indices (S1) for MAE and SR (normalized)
# These represent true effect size; simulated measurements add noise


@dataclass
class HPSensitivity:
    name: str
    display_name: str
    lo: float
    hi: float
    log_scale: bool
    s1_mae: float        # first-order Sobol index for MAE
    s1_sr: float         # first-order Sobol index for SR
    s1_mae_ci: float     # 95% CI half-width
    s1_sr_ci: float
    mae_at_lo: float     # MAE when HP at lower bound
    mae_at_hi: float     # MAE when HP at upper bound
    sr_at_lo: float
    sr_at_hi: float
    optimal_value: float # estimated optimal value
    optimal_label: str


@dataclass
class SensitivityReport:
    n_samples: int
    top_mae_hp: str
    top_sr_hp: str
    total_variance_explained_mae: float    # sum of S1
    total_variance_explained_sr: float
    results: list[HPSensitivity] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_sensitivity(n_samples: int = 512, seed: int = 42) -> SensitivityReport:
    rng = random.Random(seed)
    results = []

    # Normalize S1 values so they sum to ~1 with noise
    raw_s1_mae = [s[4] for s in HP_SPACE]
    raw_s1_sr  = [s[5] for s in HP_SPACE]
    sum_mae = sum(raw_s1_mae)
    sum_sr  = sum(raw_s1_sr)

    for name, disp, lo, hi, log_sc, s1m_raw, s1s_raw in HP_SPACE:
        # Normalize + add noise
        s1m = s1m_raw / sum_mae * 0.85 + rng.gauss(0, 0.02)
        s1s = s1s_raw / sum_sr  * 0.85 + rng.gauss(0, 0.02)
        s1m = max(0.01, s1m)
        s1s = max(0.01, s1s)
        ci_m = abs(rng.gauss(0, s1m * 0.12))
        ci_s = abs(rng.gauss(0, s1s * 0.12))

        # MAE/SR at boundary values
        # Lower bound usually worse for most HPs (LR too low, rank too low, etc.)
        effect_range = s1m * 0.08  # effect size on MAE
        baseline_mae = 0.016
        mae_lo = baseline_mae + effect_range * rng.uniform(0.5, 1.5)
        mae_hi = baseline_mae - effect_range * rng.uniform(0.3, 0.8)

        # SR: n_demos, n_steps, LR most impactful
        sr_effect = s1s * 0.4
        baseline_sr = 0.78
        sr_lo = max(0.05, baseline_sr - sr_effect + rng.gauss(0, 0.02))
        sr_hi = min(0.95, baseline_sr + sr_effect * 0.5 + rng.gauss(0, 0.02))

        # Optimal value estimation
        if log_sc:
            opt_val = math.exp((math.log(lo) + math.log(hi)) * 0.6)  # slightly above midpoint
        else:
            opt_val = lo + (hi - lo) * 0.55 + rng.gauss(0, (hi - lo) * 0.05)
        opt_val = max(lo, min(hi, opt_val))

        if log_sc:
            opt_label = f"{opt_val:.2e}"
        elif opt_val >= 100:
            opt_label = f"{int(opt_val):,}"
        elif opt_val < 1:
            opt_label = f"{opt_val:.3f}"
        else:
            opt_label = f"{opt_val:.1f}"

        results.append(HPSensitivity(
            name=name, display_name=disp,
            lo=lo, hi=hi, log_scale=log_sc,
            s1_mae=round(s1m, 4), s1_sr=round(s1s, 4),
            s1_mae_ci=round(ci_m, 4), s1_sr_ci=round(ci_s, 4),
            mae_at_lo=round(mae_lo, 5), mae_at_hi=round(mae_hi, 5),
            sr_at_lo=round(sr_lo, 4), sr_at_hi=round(sr_hi, 4),
            optimal_value=round(opt_val, 6), optimal_label=opt_label,
        ))

    results.sort(key=lambda r: r.s1_mae, reverse=True)
    top_mae = results[0].name
    top_sr  = max(results, key=lambda r: r.s1_sr).name

    return SensitivityReport(
        n_samples=n_samples,
        top_mae_hp=top_mae,
        top_sr_hp=top_sr,
        total_variance_explained_mae=round(sum(r.s1_mae for r in results), 3),
        total_variance_explained_sr=round(sum(r.s1_sr for r in results), 3),
        results=results,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(report: SensitivityReport) -> str:
    results = report.results

    # SVG: Tornado chart for S1 MAE (horizontal bars)
    bw, bh = 480, 220
    max_s1 = max(r.s1_mae for r in results) * 1.1
    bar_h = (bh - 20) / len(results) - 3

    svg_tornado = f'<svg width="{bw}" height="{bh}" style="background:#0f172a;border-radius:8px">'
    for i, r in enumerate(results):
        y = 10 + i * (bar_h + 3)
        bar_w = r.s1_mae / max_s1 * (bw - 160)
        ci_x = (r.s1_mae - r.s1_mae_ci) / max_s1 * (bw - 160) + 120
        ci_x2 = (r.s1_mae + r.s1_mae_ci) / max_s1 * (bw - 160) + 120
        col = "#C74634" if i < 3 else "#3b82f6" if i < 6 else "#64748b"
        svg_tornado += (f'<rect x="120" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                        f'fill="{col}" opacity="0.85" rx="2"/>')
        # CI error bar
        svg_tornado += (f'<line x1="{ci_x:.1f}" y1="{y+bar_h/2:.1f}" '
                        f'x2="{ci_x2:.1f}" y2="{y+bar_h/2:.1f}" '
                        f'stroke="#ffffff" stroke-width="2" opacity="0.6"/>')
        svg_tornado += (f'<text x="118" y="{y+bar_h*0.72:.1f}" fill="#94a3b8" font-size="8.5" '
                        f'text-anchor="end">{r.display_name}</text>')
        svg_tornado += (f'<text x="{123+bar_w:.1f}" y="{y+bar_h*0.72:.1f}" fill="{col}" '
                        f'font-size="8.5">{r.s1_mae:.3f}</text>')
    svg_tornado += '</svg>'

    # SVG: SR sensitivity (same layout, different color)
    sorted_sr = sorted(results, key=lambda r: r.s1_sr, reverse=True)
    max_s1_sr = max(r.s1_sr for r in sorted_sr) * 1.1
    svg_sr = f'<svg width="{bw}" height="{bh}" style="background:#0f172a;border-radius:8px">'
    for i, r in enumerate(sorted_sr):
        y = 10 + i * (bar_h + 3)
        bar_w = r.s1_sr / max_s1_sr * (bw - 160)
        col = "#22c55e" if i < 3 else "#3b82f6" if i < 6 else "#64748b"
        svg_sr += (f'<rect x="120" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                   f'fill="{col}" opacity="0.85" rx="2"/>')
        svg_sr += (f'<text x="118" y="{y+bar_h*0.72:.1f}" fill="#94a3b8" font-size="8.5" '
                   f'text-anchor="end">{r.display_name}</text>')
        svg_sr += (f'<text x="{123+bar_w:.1f}" y="{y+bar_h*0.72:.1f}" fill="{col}" '
                   f'font-size="8.5">{r.s1_sr:.3f}</text>')
    svg_sr += '</svg>'

    # Table rows
    rows = ""
    for r in results:
        mae_effect = r.mae_at_lo - r.mae_at_hi
        sr_effect  = r.sr_at_hi - r.sr_at_lo
        priority = "HIGH" if r.s1_mae > 0.10 else "MED" if r.s1_mae > 0.06 else "LOW"
        p_col = "#C74634" if priority == "HIGH" else "#f59e0b" if priority == "MED" else "#64748b"
        rows += (f'<tr>'
                 f'<td style="color:#e2e8f0">{r.display_name}</td>'
                 f'<td style="color:#C74634">{r.s1_mae:.3f} ±{r.s1_mae_ci:.3f}</td>'
                 f'<td style="color:#22c55e">{r.s1_sr:.3f} ±{r.s1_sr_ci:.3f}</td>'
                 f'<td style="color:#94a3b8">{r.mae_at_lo:.4f} → {r.mae_at_hi:.4f}</td>'
                 f'<td style="color:#94a3b8">{r.sr_at_lo*100:.0f}% → {r.sr_at_hi*100:.0f}%</td>'
                 f'<td style="color:#3b82f6">{r.optimal_label}</td>'
                 f'<td style="color:{p_col};font-weight:bold">{priority}</td>'
                 f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Hyperparameter Sensitivity Analyzer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Hyperparameter Sensitivity Analyzer</h1>
<div class="meta">Sobol first-order sensitivity · {len(HP_SPACE)} hyperparameters · {report.n_samples} quasi-random samples</div>

<div class="grid">
  <div class="card"><h3>Top MAE Driver</h3>
    <div class="big" style="color:#C74634">{report.top_mae_hp.replace("_"," ")}</div>
  </div>
  <div class="card"><h3>Top SR Driver</h3>
    <div class="big" style="color:#22c55e">{report.top_sr_hp.replace("_"," ")}</div>
  </div>
  <div class="card"><h3>Var Explained (MAE)</h3>
    <div class="big" style="color:#3b82f6">{report.total_variance_explained_mae:.1%}</div>
  </div>
  <div class="card"><h3>Var Explained (SR)</h3>
    <div class="big" style="color:#3b82f6">{report.total_variance_explained_sr:.1%}</div>
  </div>
</div>

<div class="charts">
  <div>
    <h3 class="sec">MAE Sensitivity (S1 Index) — Tornado Chart</h3>
    {svg_tornado}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Red = top-3 MAE drivers. Error bars = 95% CI. Focus HPO on top-3.
    </div>
  </div>
  <div>
    <h3 class="sec">SR Sensitivity (S1 Index) — Tornado Chart</h3>
    {svg_sr}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Green = top-3 SR drivers. Sorted by SR sensitivity.
    </div>
  </div>
</div>

<h3 class="sec">Full Sensitivity Table</h3>
<table>
  <tr><th>Hyperparameter</th><th>S1 MAE ±CI</th><th>S1 SR ±CI</th>
      <th>MAE (lo→hi)</th><th>SR (lo→hi)</th><th>Optimal</th><th>HPO Priority</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Focus HPO budget on HIGH priority HPs: num_demos, learning_rate, n_steps, lora_rank.<br>
  Warmup/dropout/weight_decay have low sensitivity — use defaults and skip tuning.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HP sensitivity analysis for GR00T fine-tuning")
    parser.add_argument("--mock",      action="store_true", default=True)
    parser.add_argument("--n-samples", type=int, default=512)
    parser.add_argument("--output",    default="/tmp/hp_sensitivity.html")
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    print(f"[hp-sensitivity] {len(HP_SPACE)} HPs · {args.n_samples} samples")
    t0 = time.time()

    report = simulate_sensitivity(args.n_samples, args.seed)

    print(f"\n  {'Hyperparameter':<22} {'S1 MAE':>8} {'S1 SR':>8}  Priority")
    print(f"  {'─'*22} {'─'*8} {'─'*8}  {'─'*8}")
    for r in report.results:
        pri = "HIGH" if r.s1_mae > 0.10 else "MED" if r.s1_mae > 0.06 else "LOW"
        print(f"  {r.display_name:<22} {r.s1_mae:>8.4f} {r.s1_sr:>8.4f}  {pri}")

    print(f"\n  Top MAE: {report.top_mae_hp}  Top SR: {report.top_sr_hp}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "top_mae_hp": report.top_mae_hp,
        "top_sr_hp": report.top_sr_hp,
        "total_variance_explained_mae": report.total_variance_explained_mae,
        "total_variance_explained_sr": report.total_variance_explained_sr,
        "sensitivities": [{
            "name": r.name, "s1_mae": r.s1_mae, "s1_sr": r.s1_sr,
            "optimal_value": r.optimal_value,
        } for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
