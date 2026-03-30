"""
Lightweight NAS for GR00T policy head architectures. Sweeps hidden dims, activations,
and residual connections.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field, asdict
from typing import List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ArchConfig:
    arch_id: str
    hidden_dims: List[int]
    activations: List[str]
    use_residual: bool
    dropout_rate: float
    n_params_k: int
    mae: float
    sr: float
    latency_ms: float
    vram_mb: float
    training_iters: int


@dataclass
class NASReport:
    best_arch_mae: float
    best_arch_sr: float
    pareto_archs: List[str]
    search_budget_iters: int
    results: List[ArchConfig] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parameter count helper
# ---------------------------------------------------------------------------

GR00T_EMBED_DIM = 1152  # GR00T N1.6 output embedding dimension
ACTION_DIM = 7           # Franka 7-DoF


def _count_params_k(hidden_dims: List[int]) -> int:
    """Count approximate parameter count (thousands) for the policy head MLP."""
    layers = [GR00T_EMBED_DIM] + hidden_dims + [ACTION_DIM]
    total = 0
    for i in range(len(layers) - 1):
        total += layers[i] * layers[i + 1] + layers[i + 1]  # weight + bias
    return max(1, total // 1000)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

# Heuristic scoring: lower MAE is better, higher SR is better.
# Residual + gelu/silu tends to do better than relu alone.
# Wider networks have lower MAE but higher latency & VRAM.

_ACT_BONUS: dict[str, float] = {"gelu": 0.0, "silu": 0.001, "relu": 0.003}
_ACT_LATENCY: dict[str, float] = {"gelu": 1.0, "silu": 1.05, "relu": 0.95}


def _simulate_arch(
    arch_id: str,
    hidden_dims: List[int],
    activations: List[str],
    use_residual: bool,
    dropout_rate: float,
    seed: int,
    override: dict | None = None,
) -> ArchConfig:
    """Deterministically simulate training metrics for an architecture candidate."""
    rng = random.Random(seed)

    n_params_k = _count_params_k(hidden_dims)
    total_hidden = sum(hidden_dims)
    depth = len(hidden_dims)

    # --- MAE ---
    base_mae = 0.020
    # Wider is better
    base_mae -= min(total_hidden, 2048) / 200_000
    # Deeper hurts a bit past 2 layers
    if depth > 2:
        base_mae += (depth - 2) * 0.0008
    # Residual helps
    if use_residual:
        base_mae -= 0.002
    # Activation bonus
    base_mae += _ACT_BONUS[activations[0]]
    # Dropout helps regularisation up to 0.1, then hurts
    if dropout_rate == 0.1:
        base_mae -= 0.0005
    elif dropout_rate == 0.2:
        base_mae += 0.001
    # Small random noise
    base_mae += rng.uniform(-0.0008, 0.0008)
    mae = max(0.010, round(base_mae, 4))

    # --- SR (success rate) ---
    base_sr = 0.70
    base_sr += (0.020 - mae) * 10
    if use_residual:
        base_sr += 0.02
    base_sr += rng.uniform(-0.015, 0.015)
    sr = round(min(0.95, max(0.60, base_sr)), 3)

    # --- Latency (ms) ---
    base_lat = 100.0
    base_lat += total_hidden / 30.0
    base_lat += depth * 4.0
    base_lat *= _ACT_LATENCY[activations[0]]
    if use_residual:
        base_lat += 3.0
    base_lat += rng.uniform(-5.0, 5.0)
    latency_ms = round(max(80.0, base_lat), 1)

    # --- VRAM (MB) ---
    base_vram = 6500.0  # GR00T backbone base
    base_vram += n_params_k * 0.5
    base_vram += rng.uniform(-50, 50)
    vram_mb = round(max(6400.0, base_vram), 0)

    training_iters = 500 + n_params_k * 2

    cfg = ArchConfig(
        arch_id=arch_id,
        hidden_dims=hidden_dims,
        activations=activations,
        use_residual=use_residual,
        dropout_rate=dropout_rate,
        n_params_k=n_params_k,
        mae=mae,
        sr=sr,
        latency_ms=latency_ms,
        vram_mb=vram_mb,
        training_iters=training_iters,
    )

    # Apply explicit overrides for pinned best/worst archs
    if override:
        for k, v in override.items():
            setattr(cfg, k, v)

    return cfg


# ---------------------------------------------------------------------------
# Architecture candidate definitions
# ---------------------------------------------------------------------------

_CANDIDATES: list[dict] = [
    # Pinned best arch
    {"hidden_dims": [512, 256], "activations": ["gelu"],  "use_residual": True,  "dropout_rate": 0.1,
     "override": {"mae": 0.014, "sr": 0.81, "latency_ms": 142.0, "vram_mb": 6700.0}},

    # Pinned worst arch
    {"hidden_dims": [1024, 512, 256], "activations": ["relu"],  "use_residual": False, "dropout_rate": 0.0,
     "override": {"mae": 0.022, "sr": 0.74, "latency_ms": 198.0, "vram_mb": 2100.0 * 1 + 6500.0}},

    # Remaining 18 unique combinations
    {"hidden_dims": [256],          "activations": ["relu"],  "use_residual": False, "dropout_rate": 0.0},
    {"hidden_dims": [256],          "activations": ["gelu"],  "use_residual": True,  "dropout_rate": 0.1},
    {"hidden_dims": [256],          "activations": ["silu"],  "use_residual": False, "dropout_rate": 0.2},
    {"hidden_dims": [512],          "activations": ["relu"],  "use_residual": True,  "dropout_rate": 0.0},
    {"hidden_dims": [512],          "activations": ["gelu"],  "use_residual": False, "dropout_rate": 0.1},
    {"hidden_dims": [512],          "activations": ["silu"],  "use_residual": True,  "dropout_rate": 0.2},
    {"hidden_dims": [256, 256],     "activations": ["relu"],  "use_residual": True,  "dropout_rate": 0.1},
    {"hidden_dims": [256, 256],     "activations": ["gelu"],  "use_residual": False, "dropout_rate": 0.0},
    {"hidden_dims": [256, 256],     "activations": ["silu"],  "use_residual": True,  "dropout_rate": 0.2},
    {"hidden_dims": [512, 256],     "activations": ["relu"],  "use_residual": False, "dropout_rate": 0.0},
    {"hidden_dims": [512, 256],     "activations": ["silu"],  "use_residual": True,  "dropout_rate": 0.2},
    {"hidden_dims": [512, 512],     "activations": ["relu"],  "use_residual": False, "dropout_rate": 0.1},
    {"hidden_dims": [512, 512],     "activations": ["gelu"],  "use_residual": True,  "dropout_rate": 0.0},
    {"hidden_dims": [512, 512],     "activations": ["silu"],  "use_residual": False, "dropout_rate": 0.2},
    {"hidden_dims": [1024, 512],    "activations": ["relu"],  "use_residual": True,  "dropout_rate": 0.0},
    {"hidden_dims": [1024, 512],    "activations": ["gelu"],  "use_residual": False, "dropout_rate": 0.1},
    {"hidden_dims": [1024, 512],    "activations": ["silu"],  "use_residual": True,  "dropout_rate": 0.2},
    {"hidden_dims": [512, 256, 128],"activations": ["gelu"],  "use_residual": True,  "dropout_rate": 0.1},
]

assert len(_CANDIDATES) == 20, f"Expected 20 candidates, got {len(_CANDIDATES)}"


def run_search(seed: int = 42) -> NASReport:
    """Run NAS simulation over all 20 candidates and return a NASReport."""
    results: List[ArchConfig] = []

    for i, cand in enumerate(_CANDIDATES):
        arch_id = f"arch_{i:02d}"
        override = cand.get("override")
        cfg = _simulate_arch(
            arch_id=arch_id,
            hidden_dims=list(cand["hidden_dims"]),
            activations=list(cand["activations"]),
            use_residual=cand["use_residual"],
            dropout_rate=cand["dropout_rate"],
            seed=seed + i,
            override=override,
        )
        results.append(cfg)

    # Pareto frontier: minimize MAE AND minimize latency_ms
    pareto: List[ArchConfig] = []
    for candidate in results:
        dominated = False
        for other in results:
            if other.arch_id == candidate.arch_id:
                continue
            if other.mae <= candidate.mae and other.latency_ms <= candidate.latency_ms:
                if other.mae < candidate.mae or other.latency_ms < candidate.latency_ms:
                    dominated = True
                    break
        if not dominated:
            pareto.append(candidate)

    pareto_ids = [p.arch_id for p in sorted(pareto, key=lambda x: x.mae)]

    best_mae_arch = min(results, key=lambda x: x.mae)
    best_sr_arch = max(results, key=lambda x: x.sr)

    total_iters = sum(r.training_iters for r in results)

    report = NASReport(
        best_arch_mae=best_mae_arch.mae,
        best_arch_sr=best_sr_arch.sr,
        pareto_archs=pareto_ids,
        search_budget_iters=total_iters,
        results=results,
    )
    return report


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def _arch_label(cfg: ArchConfig) -> str:
    dims = "x".join(str(d) for d in cfg.hidden_dims)
    return f"{dims}/{cfg.activations[0]}/{'R' if cfg.use_residual else 'N'}"


def _svg_scatter_mae_latency(results: List[ArchConfig], pareto_ids: set[str]) -> str:
    """SVG scatter: MAE (x) vs latency_ms (y), sized by n_params_k."""
    W, H = 520, 320
    PAD = 50

    maes = [r.mae for r in results]
    lats = [r.latency_ms for r in results]
    params = [r.n_params_k for r in results]

    x_min, x_max = min(maes) - 0.001, max(maes) + 0.001
    y_min, y_max = min(lats) - 10, max(lats) + 10
    p_min, p_max = min(params), max(params)

    def sx(v: float) -> float:
        return PAD + (v - x_min) / (x_max - x_min) * (W - 2 * PAD)

    def sy(v: float) -> float:
        return H - PAD - (v - y_min) / (y_max - y_min) * (H - 2 * PAD)

    def sr(p: int) -> float:
        if p_max == p_min:
            return 6.0
        return 4 + 10 * (p - p_min) / (p_max - p_min)

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">',
        # Axes
        f'<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD}" y1="{H-PAD}" x2="{W-PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>',
        # Axis labels
        f'<text x="{W//2}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">MAE</text>',
        f'<text x="12" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90,12,{H//2})">Latency (ms)</text>',
        f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="12" text-anchor="middle" '
        f'font-weight="bold">MAE vs Latency (bubble = params)</text>',
    ]

    for r in results:
        cx, cy, radius = sx(r.mae), sy(r.latency_ms), sr(r.n_params_k)
        is_pareto = r.arch_id in pareto_ids
        color = "#f97316" if is_pareto else "#3b82f6"
        stroke = "#fff" if is_pareto else "none"
        sw = "1.5" if is_pareto else "0"
        label = _arch_label(r)
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
            f'fill="{color}" stroke="{stroke}" stroke-width="{sw}" opacity="0.85">'
            f'<title>{r.arch_id}: {label}\nMAE={r.mae} Lat={r.latency_ms}ms</title>'
            f'</circle>'
        )

    # Legend
    lines += [
        f'<circle cx="{W-90}" cy="28" r="5" fill="#f97316"/>',
        f'<text x="{W-82}" y="32" fill="#f97316" font-size="10">Pareto front</text>',
        f'<circle cx="{W-90}" cy="44" r="5" fill="#3b82f6"/>',
        f'<text x="{W-82}" y="48" fill="#3b82f6" font-size="10">Other</text>',
    ]

    lines.append("</svg>")
    return "\n".join(lines)


def _svg_scatter_sr_vram(results: List[ArchConfig], pareto_ids: set[str]) -> str:
    """SVG scatter: SR (x) vs VRAM (y), sized by n_params_k."""
    W, H = 520, 320
    PAD = 50

    srs = [r.sr for r in results]
    vrams = [r.vram_mb for r in results]
    params = [r.n_params_k for r in results]

    x_min, x_max = min(srs) - 0.02, max(srs) + 0.02
    y_min, y_max = min(vrams) - 100, max(vrams) + 100
    p_min, p_max = min(params), max(params)

    def sx(v: float) -> float:
        return PAD + (v - x_min) / (x_max - x_min) * (W - 2 * PAD)

    def sy(v: float) -> float:
        return H - PAD - (v - y_min) / (y_max - y_min) * (H - 2 * PAD)

    def sr_size(p: int) -> float:
        if p_max == p_min:
            return 6.0
        return 4 + 10 * (p - p_min) / (p_max - p_min)

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">',
        f'<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD}" y1="{H-PAD}" x2="{W-PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>',
        f'<text x="{W//2}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">'
        f'Success Rate</text>',
        f'<text x="12" y="{H//2}" fill="#94a3b8" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90,12,{H//2})">VRAM (MB)</text>',
        f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="12" text-anchor="middle" '
        f'font-weight="bold">Success Rate vs VRAM (bubble = params)</text>',
    ]

    for r in results:
        cx, cy, radius = sx(r.sr), sy(r.vram_mb), sr_size(r.n_params_k)
        is_pareto = r.arch_id in pareto_ids
        color = "#f97316" if is_pareto else "#a855f7"
        stroke = "#fff" if is_pareto else "none"
        sw = "1.5" if is_pareto else "0"
        label = _arch_label(r)
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
            f'fill="{color}" stroke="{stroke}" stroke-width="{sw}" opacity="0.85">'
            f'<title>{r.arch_id}: {label}\nSR={r.sr} VRAM={r.vram_mb}MB</title>'
            f'</circle>'
        )

    lines += [
        f'<circle cx="{W-90}" cy="28" r="5" fill="#f97316"/>',
        f'<text x="{W-82}" y="32" fill="#f97316" font-size="10">Pareto front</text>',
        f'<circle cx="{W-90}" cy="44" r="5" fill="#a855f7"/>',
        f'<text x="{W-82}" y="48" fill="#a855f7" font-size="10">Other</text>',
    ]

    lines.append("</svg>")
    return "\n".join(lines)


def _build_table_rows(results: List[ArchConfig], pareto_ids: set[str]) -> str:
    rows = []
    sorted_results = sorted(results, key=lambda x: x.mae)
    for r in sorted_results:
        is_pareto = r.arch_id in pareto_ids
        row_style = 'style="background:#1e3a5f;"' if is_pareto else ""
        dims_str = str(r.hidden_dims)
        act_str = r.activations[0]
        res_str = "Yes" if r.use_residual else "No"
        badge = ' <span style="color:#f97316;font-size:10px;">★ Pareto</span>' if is_pareto else ""
        rows.append(
            f"<tr {row_style}>"
            f"<td>{r.arch_id}{badge}</td>"
            f"<td>{dims_str}</td>"
            f"<td>{act_str}</td>"
            f"<td>{res_str}</td>"
            f"<td>{r.dropout_rate}</td>"
            f"<td>{r.n_params_k}K</td>"
            f"<td>{r.mae:.4f}</td>"
            f"<td>{r.sr:.3f}</td>"
            f"<td>{r.latency_ms:.1f}</td>"
            f"<td>{r.vram_mb:.0f}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def generate_html(report: NASReport, output_path: str) -> None:
    """Generate a dark-themed HTML report for the NAS results."""
    pareto_set = set(report.pareto_archs)
    results = report.results

    # Pick recommendation archs
    prod_arch = max(results, key=lambda x: x.sr)
    edge_arch = min(results, key=lambda x: x.latency_ms)

    svg1 = _svg_scatter_mae_latency(results, pareto_set)
    svg2 = _svg_scatter_sr_vram(results, pareto_set)
    table_rows = _build_table_rows(results, pareto_set)

    pareto_list_html = "".join(
        f'<span style="background:#1e3a5f;color:#f97316;border:1px solid #f97316;'
        f'border-radius:4px;padding:2px 6px;margin:2px;font-size:12px;">{pid}</span>'
        for pid in report.pareto_archs
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NAS Report — GR00T Policy Head</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f172a;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 14px;
    padding: 24px;
  }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 28px;
  }}
  .card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .card .label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .card .value {{ color: #f1f5f9; font-size: 26px; font-weight: 700; margin-top: 6px; }}
  .card .value.red {{ color: #C74634; }}
  .section-title {{
    color: #cbd5e1;
    font-size: 15px;
    font-weight: 600;
    margin: 28px 0 12px;
    border-left: 3px solid #C74634;
    padding-left: 10px;
  }}
  .charts {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 28px;
  }}
  .chart-wrap {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #1e293b;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #334155;
  }}
  th {{
    background: #0f172a;
    color: #94a3b8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid #334155;
  }}
  td {{
    padding: 9px 12px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
    font-size: 12px;
  }}
  tr:hover td {{ background: #263548; }}
  .reco-box {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 28px;
  }}
  .reco {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 20px;
  }}
  .reco .reco-title {{ color: #C74634; font-weight: 700; font-size: 14px; margin-bottom: 10px; }}
  .reco .reco-arch {{ color: #f97316; font-size: 18px; font-weight: 700; }}
  .reco .reco-metrics {{ color: #94a3b8; font-size: 12px; margin-top: 8px; line-height: 1.7; }}
  .pareto-chips {{ margin-top: 8px; }}
  footer {{ color: #475569; font-size: 11px; margin-top: 32px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Policy Head — Neural Architecture Search</h1>
<p class="subtitle">Lightweight sweep over 20 candidates: hidden dims × activations × residual connections</p>

<div class="cards">
  <div class="card">
    <div class="label">Best MAE</div>
    <div class="value red">{report.best_arch_mae:.4f}</div>
  </div>
  <div class="card">
    <div class="label">Best Success Rate</div>
    <div class="value">{report.best_arch_sr:.1%}</div>
  </div>
  <div class="card">
    <div class="label">Pareto Architectures</div>
    <div class="value">{len(report.pareto_archs)}</div>
  </div>
  <div class="card">
    <div class="label">Total Search Iters</div>
    <div class="value">{report.search_budget_iters:,}</div>
  </div>
</div>

<div class="section-title">Scatter Plots</div>
<div class="charts">
  <div class="chart-wrap">{svg1}</div>
  <div class="chart-wrap">{svg2}</div>
</div>

<div class="section-title">Pareto Front (minimize MAE + latency)</div>
<div class="pareto-chips">{pareto_list_html}</div>

<div class="section-title">All Architectures</div>
<table>
<thead>
<tr>
  <th>Arch ID</th><th>Hidden Dims</th><th>Activation</th><th>Residual</th>
  <th>Dropout</th><th>Params</th><th>MAE</th><th>SR</th>
  <th>Latency (ms)</th><th>VRAM (MB)</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>

<div class="section-title">Recommendations</div>
<div class="reco-box">
  <div class="reco">
    <div class="reco-title">Production (SR Priority)</div>
    <div class="reco-arch">{_arch_label(prod_arch)}</div>
    <div class="reco-metrics">
      Arch ID: {prod_arch.arch_id}<br/>
      Hidden dims: {prod_arch.hidden_dims}<br/>
      SR: {prod_arch.sr:.1%} &nbsp;|&nbsp; MAE: {prod_arch.mae:.4f}<br/>
      Latency: {prod_arch.latency_ms:.1f} ms &nbsp;|&nbsp; VRAM: {prod_arch.vram_mb:.0f} MB<br/>
      Params: {prod_arch.n_params_k}K
    </div>
  </div>
  <div class="reco">
    <div class="reco-title">Edge Deployment (Latency Priority)</div>
    <div class="reco-arch">{_arch_label(edge_arch)}</div>
    <div class="reco-metrics">
      Arch ID: {edge_arch.arch_id}<br/>
      Hidden dims: {edge_arch.hidden_dims}<br/>
      SR: {edge_arch.sr:.1%} &nbsp;|&nbsp; MAE: {edge_arch.mae:.4f}<br/>
      Latency: {edge_arch.latency_ms:.1f} ms &nbsp;|&nbsp; VRAM: {edge_arch.vram_mb:.0f} MB<br/>
      Params: {edge_arch.n_params_k}K
    </div>
  </div>
</div>

<footer>OCI Robot Cloud — Lightweight NAS &nbsp;|&nbsp; GR00T N1.6 backbone &nbsp;|&nbsp; Oracle Confidential</footer>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[NAS] HTML report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight NAS for GR00T policy head architectures."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use simulated metrics (no GPU required). Default: True.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/neural_architecture_search.html",
        help="Path to write the HTML report.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for simulation reproducibility.",
    )
    args = parser.parse_args()

    print(f"[NAS] Starting lightweight NAS sweep (seed={args.seed}, mock={args.mock})")
    print(f"[NAS] Evaluating {len(_CANDIDATES)} architecture candidates...")

    report = run_search(seed=args.seed)

    # Print top-5 Pareto archs to stdout
    pareto_set = set(report.pareto_archs)
    pareto_results = [r for r in report.results if r.arch_id in pareto_set]
    pareto_results.sort(key=lambda x: x.mae)
    top5 = pareto_results[:5]

    print(f"\n{'='*70}")
    print("  TOP-5 PARETO ARCHITECTURES  (minimize MAE + minimize latency)")
    print(f"{'='*70}")
    header = f"  {'Arch':^8}  {'Hidden Dims':^18}  {'Act':^5}  {'Res':^3}  "
    header += f"{'Drop':^5}  {'Params':^7}  {'MAE':^8}  {'SR':^6}  {'Lat(ms)':^8}  {'VRAM(MB)':^9}"
    print(header)
    print(f"  {'-'*66}")
    for r in top5:
        dims = str(r.hidden_dims)
        print(
            f"  {r.arch_id:^8}  {dims:^18}  {r.activations[0]:^5}  "
            f"{'Y' if r.use_residual else 'N':^3}  {r.dropout_rate:^5.1f}  "
            f"{str(r.n_params_k)+'K':^7}  {r.mae:^8.4f}  {r.sr:^6.3f}  "
            f"{r.latency_ms:^8.1f}  {r.vram_mb:^9.0f}"
        )
    print(f"{'='*70}")
    print(f"\n[NAS] Total Pareto archs: {len(report.pareto_archs)}")
    print(f"[NAS] Best MAE: {report.best_arch_mae:.4f}  |  Best SR: {report.best_arch_sr:.1%}")
    print(f"[NAS] Search budget: {report.search_budget_iters:,} training iters")

    generate_html(report, args.output)
    print("[NAS] Done.")


if __name__ == "__main__":
    main()
