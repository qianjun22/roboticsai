"""
Calibrates GR00T action prediction confidence scores. Measures ECE (Expected
Calibration Error), reliability diagrams, and per-phase calibration for
intervention triggering in production deployments.
"""

import argparse
import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

PHASES = ["approach", "grasp", "lift", "hold"]


@dataclass
class PredictionRecord:
    step: int
    joint_id: int          # 0-8
    predicted_action: float
    true_action: float
    confidence: float      # 0-1
    phase: str             # approach / grasp / lift / hold
    abs_error: float


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _generate_records(n: int, model: str, seed: int) -> List[PredictionRecord]:
    """
    BC  model: overconfident — confidence 0.70-0.95, errors often large, ECE ~0.18
    DAgger model: well-calibrated — confidence tracks accuracy,         ECE ~0.08
    """
    rng = random.Random(seed)
    records: List[PredictionRecord] = []

    phase_skill = {"approach": 0.8, "grasp": 0.5, "lift": 0.6, "hold": 0.9}

    for i in range(n):
        phase = PHASES[i % len(PHASES)]
        joint_id = rng.randint(0, 8)
        true_action = rng.uniform(-1.0, 1.0)

        skill = phase_skill[phase]

        if model == "bc":
            # Overconfident: confidence clusters 0.70-0.95 regardless of outcome.
            # True accuracy ≈ 65% but claimed confidence ≈ 82% → ECE ≈ 0.17-0.19
            confidence = rng.uniform(0.70, 0.95)
            if rng.random() < 0.65:           # 65% accurate
                abs_error = rng.uniform(0.00, 0.18)
            else:                              # 35% inaccurate
                abs_error = rng.uniform(0.21, 0.70)
        else:  # dagger
            # Well-calibrated: confidence spread 0.30-0.90; accuracy tracks it.
            # Noise ±0.12 on the accuracy probability → ECE ≈ 0.06-0.10
            confidence = rng.uniform(0.30, 0.90)
            acc_prob = min(0.95, max(0.05, confidence + rng.gauss(0, 0.12)))
            if rng.random() < acc_prob:
                abs_error = rng.uniform(0.00, 0.18)
            else:
                abs_error = rng.uniform(0.21, 0.60)

        predicted_action = true_action + rng.gauss(0, abs_error + 0.01)

        records.append(PredictionRecord(
            step=i,
            joint_id=joint_id,
            predicted_action=predicted_action,
            true_action=true_action,
            confidence=confidence,
            phase=phase,
            abs_error=abs_error,
        ))

    return records


# ---------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------

# A prediction is "accurate" when abs_error < threshold (0.20 rad / ~11 deg)
ACCURACY_THRESHOLD = 0.20


def _is_accurate(r: PredictionRecord) -> bool:
    return r.abs_error < ACCURACY_THRESHOLD


def compute_ece(records: List[PredictionRecord], n_bins: int = 10) -> float:
    """Expected Calibration Error — weighted mean |confidence - accuracy| per bin."""
    bins: List[List[PredictionRecord]] = [[] for _ in range(n_bins)]
    for r in records:
        idx = min(int(r.confidence * n_bins), n_bins - 1)
        bins[idx].append(r)

    ece = 0.0
    total = len(records)
    for b in bins:
        if not b:
            continue
        mean_conf = sum(r.confidence for r in b) / len(b)
        mean_acc = sum(1 for r in b if _is_accurate(r)) / len(b)
        ece += (len(b) / total) * abs(mean_conf - mean_acc)
    return ece


def reliability_diagram(records: List[PredictionRecord],
                         n_bins: int = 10) -> List[Tuple[float, float, int]]:
    """Returns list of (bin_confidence, bin_accuracy, bin_count) for plotting."""
    bins: List[List[PredictionRecord]] = [[] for _ in range(n_bins)]
    for r in records:
        idx = min(int(r.confidence * n_bins), n_bins - 1)
        bins[idx].append(r)

    result = []
    for b in bins:
        if not b:
            result.append((0.0, 0.0, 0))
        else:
            result.append((
                sum(r.confidence for r in b) / len(b),
                sum(1 for r in b if _is_accurate(r)) / len(b),
                len(b),
            ))
    return result


def per_phase_ece(records: List[PredictionRecord]) -> Dict[str, float]:
    """ECE broken down by manipulation phase."""
    phase_records: Dict[str, List[PredictionRecord]] = {p: [] for p in PHASES}
    for r in records:
        phase_records[r.phase].append(r)
    return {p: compute_ece(recs) for p, recs in phase_records.items()}


def intervention_threshold_analysis(records: List[PredictionRecord]) -> Dict:
    """
    Sweep confidence thresholds.  A prediction flags for intervention when
    confidence < threshold.  High-error = abs_error >= ACCURACY_THRESHOLD.
    Returns precision/recall at each threshold and the optimal F1 threshold.
    """
    thresholds = [i / 20 for i in range(1, 20)]  # 0.05 .. 0.95
    results = []
    best_f1, best_thresh = -1.0, 0.4

    for t in thresholds:
        tp = sum(1 for r in records if r.confidence < t and not _is_accurate(r))
        fp = sum(1 for r in records if r.confidence < t and _is_accurate(r))
        fn = sum(1 for r in records if r.confidence >= t and not _is_accurate(r))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)

        results.append({
            "threshold": t,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        })
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t

    return {"sweep": results, "optimal_threshold": best_thresh, "optimal_f1": round(best_f1, 4)}


# ---------------------------------------------------------------------------
# HTML / SVG rendering
# ---------------------------------------------------------------------------

def _svg_reliability(diag: List[Tuple[float, float, int]], color: str,
                      width: int = 280, height: int = 220) -> str:
    pad = 35
    w, h = width - pad * 2, height - pad * 2

    def sx(v): return pad + v * w
    def sy(v): return pad + (1 - v) * h

    # diagonal
    lines = [
        f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(1)}" y2="{sy(1)}" '
        f'stroke="#ccc" stroke-dasharray="4,3" stroke-width="1.5"/>',
    ]
    # bars
    n = len(diag)
    bar_w = max(2, w / n - 2)
    for i, (bc, ba, cnt) in enumerate(diag):
        if cnt == 0:
            continue
        bx = sx(i / n)
        bh = ba * h
        lines.append(
            f'<rect x="{bx:.1f}" y="{sy(ba):.1f}" '
            f'width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" opacity="0.7"/>'
        )
        lines.append(
            f'<circle cx="{sx(bc):.1f}" cy="{sy(ba):.1f}" r="3" '
            f'fill="{color}" stroke="white" stroke-width="1"/>'
        )

    # axes
    lines += [
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+h}" stroke="#666" stroke-width="1"/>',
        f'<line x1="{pad}" y1="{pad+h}" x2="{pad+w}" y2="{pad+h}" stroke="#666" stroke-width="1"/>',
        f'<text x="{pad+w//2}" y="{height-4}" text-anchor="middle" font-size="10" fill="#555">Confidence</text>',
        f'<text x="10" y="{pad+h//2}" text-anchor="middle" font-size="10" fill="#555" '
        f'transform="rotate(-90,10,{pad+h//2})">Accuracy</text>',
    ]
    for v in [0, 0.25, 0.5, 0.75, 1.0]:
        lines.append(
            f'<text x="{pad-3}" y="{sy(v)+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#777">{v:.2f}</text>'
        )
        lines.append(
            f'<text x="{sx(v):.1f}" y="{pad+h+14}" text-anchor="middle" '
            f'font-size="9" fill="#777">{v:.2f}</text>'
        )

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'style="background:#fafafa;border-radius:6px;">' +
            "\n".join(lines) + "</svg>")


def _svg_phase_bar(bc_phase: Dict[str, float], dag_phase: Dict[str, float],
                    width: int = 560, height: int = 180) -> str:
    pad_l, pad_b, pad_t = 60, 30, 20
    w = width - pad_l - 20
    h = height - pad_b - pad_t
    phases = PHASES
    n = len(phases)
    group_w = w / n
    bar_w = group_w * 0.35

    max_val = max(max(bc_phase.values()), max(dag_phase.values())) * 1.2 or 0.3
    def sy(v): return pad_t + (1 - v / max_val) * h
    def sx(i, offset): return pad_l + i * group_w + group_w * 0.15 + offset

    parts = []
    for i, p in enumerate(phases):
        # BC bar
        bv = bc_phase[p]
        parts.append(
            f'<rect x="{sx(i,0):.1f}" y="{sy(bv):.1f}" '
            f'width="{bar_w:.1f}" height="{(bv/max_val)*h:.1f}" '
            f'fill="#ef4444" opacity="0.8"/>'
        )
        # DAgger bar
        dv = dag_phase[p]
        parts.append(
            f'<rect x="{sx(i,bar_w+3):.1f}" y="{sy(dv):.1f}" '
            f'width="{bar_w:.1f}" height="{(dv/max_val)*h:.1f}" '
            f'fill="#3b82f6" opacity="0.8"/>'
        )
        # label
        parts.append(
            f'<text x="{sx(i, group_w*0.35):.1f}" y="{pad_t+h+18}" '
            f'text-anchor="middle" font-size="11" fill="#444">{p}</text>'
        )

    # y-axis ticks
    for v in [0, 0.1, 0.2, 0.3]:
        if v > max_val:
            break
        parts.append(
            f'<line x1="{pad_l}" y1="{sy(v):.1f}" x2="{pad_l+w}" y2="{sy(v):.1f}" '
            f'stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l-5}" y="{sy(v)+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#777">{v:.2f}</text>'
        )

    parts += [
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+h}" stroke="#666" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+h}" x2="{pad_l+w}" y2="{pad_t+h}" stroke="#666" stroke-width="1"/>',
        # legend
        f'<rect x="{width-130}" y="5" width="12" height="12" fill="#ef4444" opacity="0.8"/>',
        f'<text x="{width-114}" y="15" font-size="10" fill="#333">BC (overconfident)</text>',
        f'<rect x="{width-130}" y="22" width="12" height="12" fill="#3b82f6" opacity="0.8"/>',
        f'<text x="{width-114}" y="32" font-size="10" fill="#333">DAgger (calibrated)</text>',
    ]

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'style="background:#fafafa;border-radius:6px;">' +
            "\n".join(parts) + "</svg>")


def _svg_roc(sweep: List[Dict], width: int = 380, height: int = 220) -> str:
    pad = 40
    w, h = width - pad * 2, height - pad * 2

    def sx(v): return pad + v * w
    def sy(v): return pad + (1 - v) * h

    pts = [(d["recall"], d["precision"]) for d in sweep]
    polyline = " ".join(f"{sx(r):.1f},{sy(p):.1f}" for r, p in pts)

    parts = [
        f'<polyline points="{polyline}" fill="none" stroke="#8b5cf6" stroke-width="2"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+h}" stroke="#666" stroke-width="1"/>',
        f'<line x1="{pad}" y1="{pad+h}" x2="{pad+w}" y2="{pad+h}" stroke="#666" stroke-width="1"/>',
        f'<text x="{pad+w//2}" y="{height-4}" text-anchor="middle" font-size="10" fill="#555">Recall</text>',
        f'<text x="12" y="{pad+h//2}" text-anchor="middle" font-size="10" fill="#555" '
        f'transform="rotate(-90,12,{pad+h//2})">Precision</text>',
    ]
    for v in [0, 0.25, 0.5, 0.75, 1.0]:
        parts += [
            f'<text x="{pad-3}" y="{sy(v)+4:.1f}" text-anchor="end" font-size="9" fill="#777">{v:.2f}</text>',
            f'<text x="{sx(v):.1f}" y="{pad+h+14}" text-anchor="middle" font-size="9" fill="#777">{v:.2f}</text>',
        ]

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'style="background:#fafafa;border-radius:6px;">' +
            "\n".join(parts) + "</svg>")


def render_html(bc_records: List[PredictionRecord],
                dagger_records: List[PredictionRecord]) -> str:
    bc_ece = compute_ece(bc_records)
    dag_ece = compute_ece(dagger_records)
    bc_diag = reliability_diagram(bc_records)
    dag_diag = reliability_diagram(dagger_records)
    bc_phase = per_phase_ece(bc_records)
    dag_phase = per_phase_ece(dagger_records)
    dag_thresh = intervention_threshold_analysis(dagger_records)
    opt_t = dag_thresh["optimal_threshold"]
    opt_f1 = dag_thresh["optimal_f1"]

    bc_svg = _svg_reliability(bc_diag, "#ef4444")
    dag_svg = _svg_reliability(dag_diag, "#3b82f6")
    phase_svg = _svg_phase_bar(bc_phase, dag_phase)
    roc_svg = _svg_roc(dag_thresh["sweep"])

    def ece_card(label, ece, color):
        grade = "Poor" if ece > 0.15 else ("Fair" if ece > 0.10 else "Good")
        return f"""
        <div style="background:{color}15;border:1px solid {color}40;border-radius:8px;
                    padding:14px 20px;text-align:center;flex:1;min-width:160px;">
          <div style="font-size:13px;color:#555;margin-bottom:4px;">{label}</div>
          <div style="font-size:28px;font-weight:700;color:{color};">{ece:.4f}</div>
          <div style="font-size:12px;color:#777;margin-top:4px;">ECE &mdash; {grade}</div>
        </div>"""

    phase_rows = "".join(
        f'<tr><td style="padding:4px 10px">{p}</td>'
        f'<td style="padding:4px 10px;color:#ef4444">{bc_phase[p]:.4f}</td>'
        f'<td style="padding:4px 10px;color:#3b82f6">{dag_phase[p]:.4f}</td></tr>'
        for p in PHASES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>GR00T Confidence Calibration Report</title>
<style>
  body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;
         background:#f1f5f9;color:#1e293b;}}
  .container {{max-width:1000px;margin:0 auto;padding:24px;}}
  h1 {{font-size:22px;font-weight:700;margin-bottom:4px;}}
  h2 {{font-size:16px;font-weight:600;color:#334155;margin:24px 0 10px;}}
  .subtitle {{color:#64748b;font-size:13px;margin-bottom:24px;}}
  .card {{background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.08);
          padding:20px;margin-bottom:20px;}}
  .row {{display:flex;gap:20px;flex-wrap:wrap;}}
  table {{border-collapse:collapse;width:100%;font-size:13px;}}
  th {{background:#f8fafc;padding:6px 10px;text-align:left;color:#475569;
       border-bottom:1px solid #e2e8f0;}}
  .rec {{background:#ecfdf5;border-left:4px solid #22c55e;padding:12px 16px;
         border-radius:6px;font-size:13px;color:#166534;margin-top:12px;}}
  .label {{font-size:13px;font-weight:600;color:#475569;margin-bottom:8px;}}
</style>
</head>
<body>
<div class="container">
  <h1>GR00T Confidence Calibration Report</h1>
  <p class="subtitle">Measures whether predicted confidence scores match observed accuracy &mdash;
     enabling reliable intervention triggers in production. N={len(bc_records)} records/model.</p>

  <div class="card">
    <h2>Overall ECE</h2>
    <div class="row">
      {ece_card("BC Model", bc_ece, "#ef4444")}
      {ece_card("DAgger Model", dag_ece, "#3b82f6")}
    </div>
    <p style="font-size:12px;color:#94a3b8;margin-top:10px;">
      ECE = weighted mean |confidence &minus; accuracy| across bins.
      Lower is better. Threshold for accuracy: abs_error &lt; 0.20 rad.
    </p>
  </div>

  <div class="card">
    <h2>Reliability Diagrams</h2>
    <p style="font-size:12px;color:#94a3b8;margin-bottom:12px;">
      Bars show actual accuracy per confidence bin. Dashed line = perfect calibration.
      BC bars cluster high-confidence while accuracy is lower &mdash; classic overconfidence.
    </p>
    <div class="row">
      <div><div class="label" style="color:#ef4444;">BC Model (overconfident)</div>{bc_svg}</div>
      <div><div class="label" style="color:#3b82f6;">DAgger Model (well-calibrated)</div>{dag_svg}</div>
    </div>
  </div>

  <div class="card">
    <h2>Per-Phase ECE</h2>
    {phase_svg}
    <table style="margin-top:12px;">
      <tr><th>Phase</th><th style="color:#ef4444">BC ECE</th><th style="color:#3b82f6">DAgger ECE</th></tr>
      {phase_rows}
    </table>
  </div>

  <div class="card">
    <h2>Intervention Threshold Analysis (DAgger Model)</h2>
    <p style="font-size:12px;color:#94a3b8;margin-bottom:12px;">
      Flag for human intervention when confidence &lt; threshold.
      Precision&ndash;Recall curve below; optimal threshold at F1={opt_f1:.3f}.
    </p>
    {roc_svg}
    <div class="rec">
      Recommendation: <strong>Use confidence &lt; {opt_t:.2f} as intervention trigger (DAgger model)</strong>.
      This yields F1={opt_f1:.3f}, balancing false alarms vs missed high-error predictions.
      BC model is not recommended for intervention triggering due to ECE={bc_ece:.4f} &gt; 0.15.
    </div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GR00T confidence calibration analysis")
    parser.add_argument("--mock", default=True, action=argparse.BooleanOptionalAction,
                        help="Use mock data (default: True)")
    parser.add_argument("--n-records", type=int, default=2000,
                        help="Number of prediction records per model (default: 2000)")
    parser.add_argument("--output", default="/tmp/confidence_calibration.html",
                        help="Output HTML path (default: /tmp/confidence_calibration.html)")
    args = parser.parse_args()

    if args.mock:
        bc_records = _generate_records(args.n_records, "bc", seed=42)
        dag_records = _generate_records(args.n_records, "dagger", seed=99)
    else:
        raise NotImplementedError("Only --mock mode is currently supported.")

    print(f"BC  ECE : {compute_ece(bc_records):.4f}")
    print(f"Dag ECE : {compute_ece(dag_records):.4f}")
    print("Per-phase ECE (BC)    :", {p: f"{v:.4f}" for p, v in per_phase_ece(bc_records).items()})
    print("Per-phase ECE (DAgger):", {p: f"{v:.4f}" for p, v in per_phase_ece(dag_records).items()})

    thresh_info = intervention_threshold_analysis(dag_records)
    print(f"Optimal threshold: {thresh_info['optimal_threshold']:.2f}  F1={thresh_info['optimal_f1']:.3f}")

    html = render_html(bc_records, dag_records)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
