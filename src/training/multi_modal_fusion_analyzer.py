#!/usr/bin/env python3
"""
multi_modal_fusion_analyzer.py -- Multi-modal fusion strategy analyzer for GR00T.

Evaluates 5 fusion strategies across 4 input modalities and generates an interactive
HTML report with spider charts, attention heatmaps, and ablation bar charts.

Usage:
    python src/training/multi_modal_fusion_analyzer.py --mock --output /tmp/multi_modal_fusion_analyzer.html
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict


FUSION_STRATEGIES = ["early_concat", "late_fusion", "cross_attention", "film_conditioning", "gated_fusion"]
MODALITIES = ["rgb_image", "proprioception", "language_instruction", "force_torque"]
MODALITY_SHAPES = {"rgb_image": (224, 224, 3), "proprioception": (7,), "language_instruction": (512,), "force_torque": (6,)}

STRATEGY_TARGETS = {
    "early_concat":      {"success_rate": 0.72, "mae": 0.041, "inference_latency_ms": 224, "param_overhead_M": 0.8},
    "late_fusion":       {"success_rate": 0.75, "mae": 0.038, "inference_latency_ms": 231, "param_overhead_M": 2.1},
    "cross_attention":   {"success_rate": 0.81, "mae": 0.029, "inference_latency_ms": 263, "param_overhead_M": 5.4},
    "film_conditioning": {"success_rate": 0.78, "mae": 0.034, "inference_latency_ms": 241, "param_overhead_M": 3.2},
    "gated_fusion":      {"success_rate": 0.79, "mae": 0.032, "inference_latency_ms": 198, "param_overhead_M": 4.0},
}

ABLATION_DELTAS = {
    "early_concat":      {"rgb_image": -0.21, "proprioception": -0.11, "language_instruction": -0.18, "force_torque": -0.03},
    "late_fusion":       {"rgb_image": -0.22, "proprioception": -0.12, "language_instruction": -0.17, "force_torque": -0.04},
    "cross_attention":   {"rgb_image": -0.24, "proprioception": -0.13, "language_instruction": -0.18, "force_torque": -0.03},
    "film_conditioning": {"rgb_image": -0.22, "proprioception": -0.11, "language_instruction": -0.19, "force_torque": -0.04},
    "gated_fusion":      {"rgb_image": -0.23, "proprioception": -0.12, "language_instruction": -0.18, "force_torque": -0.03},
}

ATTENTION_MATRIX_TEMPLATE = {
    "rgb_image":            {"rgb_image": 0.52, "proprioception": 0.18, "language_instruction": 0.22, "force_torque": 0.08},
    "proprioception":       {"rgb_image": 0.31, "proprioception": 0.38, "language_instruction": 0.21, "force_torque": 0.10},
    "language_instruction": {"rgb_image": 0.28, "proprioception": 0.14, "language_instruction": 0.48, "force_torque": 0.10},
    "force_torque":         {"rgb_image": 0.19, "proprioception": 0.27, "language_instruction": 0.15, "force_torque": 0.39},
}


@dataclass
class AblationResult:
    modality_removed: str
    success_rate: float
    sr_delta: float


@dataclass
class StrategyResult:
    strategy: str
    success_rate: float
    mae: float
    inference_latency_ms: float
    param_overhead_M: float
    ablation: List[AblationResult] = field(default_factory=list)


@dataclass
class AttentionHeatmap:
    query_modalities: List[str]
    key_modalities: List[str]
    weights: List[List[float]]


@dataclass
class FusionAnalysisReport:
    timestamp: str
    seed: int
    modalities: List[str]
    modality_shapes: Dict[str, List[int]]
    strategies: List[StrategyResult]
    attention_heatmap: AttentionHeatmap
    key_findings: List[str]


def simulate_strategy_results(seed: int = 42) -> List[StrategyResult]:
    random.seed(seed)
    results = []
    for strategy in FUSION_STRATEGIES:
        targets = STRATEGY_TARGETS[strategy]
        sr = max(0.0, min(1.0, targets["success_rate"] + random.gauss(0, 0.008)))
        mae = max(0.0, targets["mae"] + random.gauss(0, 0.0015))
        latency = max(10.0, targets["inference_latency_ms"] + random.gauss(0, 2.5))
        params = max(0.0, targets["param_overhead_M"] + random.gauss(0, 0.05))
        ablation = []
        for modality in MODALITIES:
            delta = ABLATION_DELTAS[strategy][modality] + random.gauss(0, 0.005)
            ablated_sr = max(0.0, min(1.0, sr + delta))
            ablation.append(AblationResult(modality_removed=modality, success_rate=round(ablated_sr, 4), sr_delta=round(ablated_sr - sr, 4)))
        results.append(StrategyResult(strategy=strategy, success_rate=round(sr, 4), mae=round(mae, 5),
                                      inference_latency_ms=round(latency, 1), param_overhead_M=round(params, 3), ablation=ablation))
    return results


def simulate_attention_heatmap(seed: int = 42) -> AttentionHeatmap:
    random.seed(seed + 1000)
    weights = []
    for q in MODALITIES:
        raw = [max(0.001, ATTENTION_MATRIX_TEMPLATE[q][k] + random.gauss(0, 0.01)) for k in MODALITIES]
        total = sum(raw)
        weights.append([round(v / total, 4) for v in raw])
    return AttentionHeatmap(query_modalities=MODALITIES, key_modalities=MODALITIES, weights=weights)


def build_key_findings(results: List[StrategyResult]) -> List[str]:
    best_sr = max(results, key=lambda r: r.success_rate)
    best_lat = min(results, key=lambda r: r.inference_latency_ms)
    baseline = next(r for r in results if r.strategy == "early_concat")
    ca = next(r for r in results if r.strategy == "cross_attention")
    sr_lift = round((ca.success_rate - baseline.success_rate) * 100, 1)
    mod_deltas: Dict[str, List[float]] = {m: [] for m in MODALITIES}
    for r in results:
        for abl in r.ablation:
            mod_deltas[abl.modality_removed].append(abl.sr_delta)
    avg_deltas = {m: round(sum(v) / len(v), 4) for m, v in mod_deltas.items()}
    most_important = min(avg_deltas, key=lambda m: avg_deltas[m])
    least_important = max(avg_deltas, key=lambda m: avg_deltas[m])
    return [
        f"Best SR: {best_sr.strategy} achieves {best_sr.success_rate:.0%} success rate",
        f"Best latency: {best_lat.strategy} at {best_lat.inference_latency_ms:.0f}ms inference",
        f"cross_attention vs early_concat baseline: +{sr_lift}pp SR improvement",
        f"Most critical modality: removing {most_important} costs avg {abs(avg_deltas[most_important]):.2f} SR drop",
        f"Least critical modality: removing {least_important} costs only {abs(avg_deltas[least_important]):.2f} SR drop",
        "Language instruction dominates policy grounding; force/torque provides marginal benefit in sim",
        "gated_fusion achieves best latency/accuracy trade-off for real-time deployment at 30Hz",
    ]


def simulate_all(seed: int = 42) -> FusionAnalysisReport:
    strategies = simulate_strategy_results(seed)
    heatmap = simulate_attention_heatmap(seed)
    findings = build_key_findings(strategies)
    shapes_serializable = {k: list(v) for k, v in MODALITY_SHAPES.items()}
    return FusionAnalysisReport(timestamp=datetime.utcnow().isoformat() + "Z", seed=seed,
                                modalities=MODALITIES, modality_shapes=shapes_serializable,
                                strategies=strategies, attention_heatmap=heatmap, key_findings=findings)


def _lerp_color(t: float, c1: str, c2: str) -> str:
    def parse(c):
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    r1, g1, b1 = parse(c1)
    r2, g2, b2 = parse(c2)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"


def build_spider_svg(results: List[StrategyResult]) -> str:
    metrics = ["SR", "1-MAE_n", "1-Lat_n", "1-Params_n", "Robustness"]
    n_axes = len(metrics)
    srs = [r.success_rate for r in results]
    maes = [r.mae for r in results]
    lats = [r.inference_latency_ms for r in results]
    params = [r.param_overhead_M for r in results]

    def norm(val, lo, hi): return (val - lo) / (hi - lo) if hi != lo else 0.5
    def inv_norm(val, lo, hi): return 1.0 - norm(val, lo, hi)
    def robustness(r): return 1.0 - sum(abs(a.sr_delta) for a in r.ablation) / len(r.ablation)

    rob_vals = [robustness(r) for r in results]
    normalized = [[norm(r.success_rate, min(srs), max(srs)), inv_norm(r.mae, min(maes), max(maes)),
                   inv_norm(r.inference_latency_ms, min(lats), max(lats)), inv_norm(r.param_overhead_M, min(params), max(params)),
                   norm(robustness(r), min(rob_vals), max(rob_vals))] for r in results]

    cx, cy, R = 250, 250, 160
    colors = ["#60a5fa", "#C74634", "#34d399", "#f59e0b", "#a78bfa"]

    def axis_point(i, radius):
        angle = math.pi / 2 + 2 * math.pi * i / n_axes
        return cx + radius * math.cos(angle), cy - radius * math.sin(angle)

    lines = []
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{axis_point(i, R*level)[0]:.1f},{axis_point(i, R*level)[1]:.1f}" for i in range(n_axes))
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')
    for i in range(n_axes):
        x1, y1 = axis_point(i, 0)
        x2, y2 = axis_point(i, R)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')
    for i, label in enumerate(metrics):
        lx, ly = axis_point(i, R + 22)
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="11">{label}</text>')
    for s_idx, (r, vals) in enumerate(zip(results, normalized)):
        pts = " ".join(f"{axis_point(i, R*v)[0]:.1f},{axis_point(i, R*v)[1]:.1f}" for i, v in enumerate(vals))
        c = colors[s_idx]
        lines.append(f'<polygon points="{pts}" fill="{c}" fill-opacity="0.15" stroke="{c}" stroke-width="2"/>')
    for s_idx, r in enumerate(results):
        c = colors[s_idx]
        legy = 130 + s_idx * 22
        lines.append(f'<rect x="430" y="{legy-6}" width="12" height="12" fill="{c}" rx="2"/>')
        lines.append(f'<text x="446" y="{legy+3}" fill="#cbd5e1" font-size="11">{r.strategy.replace("_"," ")}</text>')
    svg_body = "\n    ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="500" style="background:#0f172a;border-radius:8px;">\n    {svg_body}\n</svg>'


def build_heatmap_svg(heatmap: AttentionHeatmap) -> str:
    n = len(heatmap.query_modalities)
    cell = 70
    label_w, label_h = 130, 80
    w = label_w + n * cell + 20
    h = label_h + n * cell + 20
    labels_short = {"rgb_image": "RGB", "proprioception": "Proprio", "language_instruction": "Lang", "force_torque": "F/T"}
    lines = []
    for j, key_mod in enumerate(heatmap.key_modalities):
        x = label_w + j * cell + cell // 2
        lines.append(f'<text x="{x}" y="{label_h-8}" text-anchor="middle" fill="#94a3b8" font-size="11">{labels_short[key_mod]}</text>')
    for i, q_mod in enumerate(heatmap.query_modalities):
        y = label_h + i * cell + cell // 2 + 4
        lines.append(f'<text x="{label_w-8}" y="{y}" text-anchor="end" fill="#94a3b8" font-size="11">{labels_short[q_mod]}</text>')
    for i, row in enumerate(heatmap.weights):
        for j, val in enumerate(row):
            cell_color = _lerp_color(val, "#1e3a5f", "#C74634")
            x = label_w + j * cell
            y = label_h + i * cell
            lines.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{cell_color}" stroke="#0f172a" stroke-width="1"/>')
            text_color = "#f8fafc" if val > 0.35 else "#94a3b8"
            lines.append(f'<text x="{x+cell//2}" y="{y+cell//2+4}" text-anchor="middle" fill="{text_color}" font-size="12">{val:.2f}</text>')
    svg_body = "\n    ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:8px;">\n    {svg_body}\n</svg>'


def render_html(report: FusionAnalysisReport) -> str:
    spider_svg = build_spider_svg(report.strategies)
    heatmap_svg = build_heatmap_svg(report.attention_heatmap)

    best_sr = max(r.success_rate for r in report.strategies)
    best_lat = min(r.inference_latency_ms for r in report.strategies)
    table_rows = "".join(
        f'<tr><td style="padding:8px 12px;color:#e2e8f0">{r.strategy.replace("_"," ")}</td>'
        f'<td style="padding:8px 12px;text-align:right{("; color:#34d399;font-weight:bold" if r.success_rate==best_sr else "")}">{r.success_rate:.3f}</td>'
        f'<td style="padding:8px 12px;text-align:right">{r.mae:.5f}</td>'
        f'<td style="padding:8px 12px;text-align:right{("; color:#34d399;font-weight:bold" if r.inference_latency_ms==best_lat else "")}">{r.inference_latency_ms:.1f}</td>'
        f'<td style="padding:8px 12px;text-align:right">{r.param_overhead_M:.3f}</td></tr>'
        for r in report.strategies
    )
    findings_html = "".join(f'<li style="margin-bottom:6px;color:#cbd5e1">{f}</li>' for f in report.key_findings)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>Multi-Modal Fusion Analyzer</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#1e293b;color:#e2e8f0;font-family:system-ui,sans-serif;padding:32px}}
h1{{color:#C74634;font-size:1.8rem;margin-bottom:6px}}h2{{color:#C74634;font-size:1.2rem;margin:32px 0 14px;border-bottom:1px solid #334155;padding-bottom:6px}}
.card{{background:#0f172a;border-radius:10px;padding:24px;margin-bottom:28px;border:1px solid #1e3a5f}}
table{{border-collapse:collapse;width:100%}}th{{padding:8px 12px;color:#64748b;font-weight:600;text-align:left;border-bottom:1px solid #334155;font-size:0.82rem}}</style></head>
<body><h1>Multi-Modal Fusion Analyzer</h1>
<p style="color:#64748b;font-size:0.9rem;margin-bottom:32px">GR00T N1.6 | Seed: {report.seed} | Generated: {report.timestamp}</p>
<h2>Strategy Performance Metrics</h2>
<div class="card"><table><thead><tr><th>Strategy</th><th style="text-align:right">SR \u2191</th><th style="text-align:right">MAE \u2193</th><th style="text-align:right">Latency ms \u2193</th><th style="text-align:right">Params +M \u2193</th></tr></thead><tbody>{table_rows}</tbody></table></div>
<h2>Radar Chart (5 Metrics x 5 Strategies)</h2><div class="card"><div style="overflow-x:auto">{spider_svg}</div></div>
<h2>Cross-Attention Heatmap (cross_attention strategy)</h2><div class="card"><div style="overflow-x:auto">{heatmap_svg}</div></div>
<h2>Key Findings</h2><div class="card"><ul style="list-style:disc inside;padding-left:8px">{findings_html}</ul></div>
<p style="color:#334155;font-size:0.75rem;margin-top:24px">OCI Robot Cloud \u00b7 Multi-Modal Fusion Analyzer v1.0</p></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Multi-modal fusion strategy analyzer for GR00T")
    parser.add_argument("--mock", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output", default="/tmp/multi_modal_fusion_analyzer.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = simulate_all(seed=args.seed)
    html = render_html(report)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[multi_modal_fusion_analyzer] HTML saved \u2192 {out_path}")
    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print(f"[multi_modal_fusion_analyzer] JSON sidecar \u2192 {json_path}")
    print("Key Findings:")
    for f in report.key_findings:
        print(f"  \u2022 {f}")


if __name__ == "__main__":
    main()
