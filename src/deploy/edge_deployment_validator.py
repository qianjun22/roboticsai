#!/usr/bin/env python3
"""
edge_deployment_validator.py — OCI Robot Cloud Edge Deployment Validator
Validates GR00T N1.6 model artifacts for Jetson edge deployment.
Dependencies: stdlib + numpy only
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

@dataclass
class EdgeTarget:
    device_id: str
    device_type: str
    memory_gb: float
    compute_tflops: float
    os_version: str
    jetpack_version: str

@dataclass
class ModelArtifact:
    model_id: str
    checkpoint_path: str
    param_count_b: float
    quantization: str
    file_size_mb: float

@dataclass
class ValidationResult:
    artifact_id: str
    target_id: str
    passed: bool
    checks: Dict[str, bool]
    latency_ms: float
    memory_mb: float
    score: float
    notes: List[str] = field(default_factory=list)


EDGE_TARGETS: List[EdgeTarget] = [
    EdgeTarget("jetson-agx-orin-64",  "Jetson AGX Orin", 64.0, 275.0, "Ubuntu 22.04", "6.0"),
    EdgeTarget("jetson-orin-nx-16",   "Jetson Orin NX",  16.0, 100.0, "Ubuntu 20.04", "5.1"),
    EdgeTarget("jetson-nano-8",        "Jetson Nano",      8.0,  21.0, "Ubuntu 20.04", "5.0"),
]

MODELS: List[ModelArtifact] = [
    ModelArtifact("gr00t_n1.6_fp16",    "/checkpoints/gr00t_n1.6/fp16/model.safetensors",  3.0, "fp16", 6700.0),
    ModelArtifact("gr00t_n1.6_int8",    "/checkpoints/gr00t_n1.6/int8/model.safetensors",  3.0, "int8", 3400.0),
    ModelArtifact("gr00t_n1.6_int4",    "/checkpoints/gr00t_n1.6/int4/model.safetensors",  3.0, "int4", 1800.0),
    ModelArtifact("gr00t_distilled_1b", "/checkpoints/gr00t_distilled/1b/model.safetensors", 1.0, "fp16", 2100.0),
]

RECOMMENDED_DEPLOYMENTS: List[Tuple[str, str]] = [
    ("gr00t_n1.6_fp16",    "jetson-agx-orin-64"),
    ("gr00t_n1.6_int8",    "jetson-agx-orin-64"),
    ("gr00t_n1.6_int8",    "jetson-orin-nx-16"),
    ("gr00t_distilled_1b", "jetson-nano-8"),
]


def _jetpack_ge(version: str, minimum: str) -> bool:
    return tuple(int(x) for x in version.split(".")) >= tuple(int(x) for x in minimum.split("."))

def _estimate_latency_ms(artifact: ModelArtifact, target: EdgeTarget) -> float:
    qf = {"fp16": 1.0, "int8": 0.55, "int4": 0.32}.get(artifact.quantization, 1.0)
    return round((artifact.param_count_b / target.compute_tflops) * 1000.0 * qf, 2)

def _estimate_runtime_memory_mb(artifact: ModelArtifact) -> float:
    return round(artifact.file_size_mb * 1.3, 1)


def validate_model_for_target(artifact: ModelArtifact, target: EdgeTarget) -> ValidationResult:
    notes: List[str] = []
    checks: Dict[str, bool] = {}
    runtime_mem_mb = _estimate_runtime_memory_mb(artifact)
    device_mem_mb = target.memory_gb * 1024.0
    checks["memory_fit"] = runtime_mem_mb < device_mem_mb
    if not checks["memory_fit"]: notes.append(f"Memory: {runtime_mem_mb:.0f}MB > {device_mem_mb:.0f}MB available")
    compute_ratio = artifact.param_count_b / target.compute_tflops
    checks["compute_ok"] = compute_ratio < 0.05
    if not checks["compute_ok"]: notes.append(f"Compute ratio {compute_ratio:.4f} >= 0.05")
    latency_ms = _estimate_latency_ms(artifact, target)
    checks["latency_ok"] = latency_ms < 500.0
    if not checks["latency_ok"]: notes.append(f"Latency {latency_ms:.1f}ms >= 500ms target")
    if artifact.quantization == "int4" and target.device_type == "Jetson Nano":
        checks["quantization_supported"] = False; notes.append("INT4 not supported on Jetson Nano")
    else:
        checks["quantization_supported"] = True
    if artifact.quantization in ("int8", "int4"):
        compat = _jetpack_ge(target.jetpack_version, "5.1")
        checks["jetpack_compat"] = compat
        if not compat: notes.append(f"{artifact.quantization.upper()} requires JetPack>=5.1; device has {target.jetpack_version}")
    else:
        checks["jetpack_compat"] = True
    score = sum(checks.values()) / len(checks)
    passed = all(checks.values())
    if passed: notes.append("All checks passed")
    return ValidationResult(artifact_id=artifact.model_id, target_id=target.device_id, passed=passed, checks=checks, latency_ms=latency_ms, memory_mb=runtime_mem_mb, score=score, notes=notes)


def run_full_validation_matrix() -> List[ValidationResult]:
    return [validate_model_for_target(a, t) for a in MODELS for t in EDGE_TARGETS]


def generate_validation_report(results: List[ValidationResult]) -> str:
    recommended_set = set(RECOMMENDED_DEPLOYMENTS)
    result_map = {(r.artifact_id, r.target_id): r for r in results}
    device_headers = "".join(f"<th>{t.device_type}<br/><span style='font-weight:400;color:#94a3b8'>{t.memory_gb:.0f}GB | {t.compute_tflops:.0f}TFLOPS | JP{t.jetpack_version}</span></th>" for t in EDGE_TARGETS)
    matrix_rows = ""
    for artifact in MODELS:
        row = f"<tr><td style='background:#1e293b;font-weight:600;color:#f1f5f9;min-width:200px'>{artifact.model_id}<br/><span style='font-weight:400;color:#64748b;font-size:0.75rem'>{artifact.param_count_b:.0f}B params | {artifact.quantization.upper()} | {artifact.file_size_mb/1024:.1f}GB</span></td>"
        for target in EDGE_TARGETS:
            res = result_map.get((artifact.model_id, target.device_id))
            if not res: row += "<td>—</td>"; continue
            is_rec = (artifact.model_id, target.device_id) in recommended_set
            bg = "#166534" if (res.passed and is_rec) else ("#14532d" if res.passed else "#450a0a")
            border = "2px solid #4ade80" if is_rec else ("1px solid #22c55e" if res.passed else "1px solid #ef4444")
            sc = "#4ade80" if res.passed else "#f87171"
            checks_html = "".join(f"<div style='font-size:0.7rem;color:{'#86efac' if ok else '#fca5a5'}'>{'&#10003;' if ok else '&#10007;'} {name.replace('_',' ')}</div>" for name, ok in res.checks.items())
            row += f"<td style='background:{bg};border:{border};padding:0.7rem;vertical-align:top'><div style='font-weight:700;color:{sc};margin-bottom:0.3rem'>{'PASS' if res.passed else 'FAIL'}{'&#9733;' if is_rec else ''}</div><div style='font-size:0.75rem;color:#cbd5e1'>{res.latency_ms:.0f}ms</div><div style='font-size:0.72rem;color:#94a3b8'>{res.memory_mb:.0f}MB | {res.score:.0%}</div><hr style='border-color:#334155;margin:0.4rem 0'/>{checks_html}</td>"
        matrix_rows += row + "</tr>"
    rec_rows = "".join(f"<tr><td>&#9733; {m_id}</td><td>{next(t.device_type for t in EDGE_TARGETS if t.device_id==d_id)}</td><td>{result_map[(m_id,d_id)].latency_ms:.0f}ms</td><td>{result_map[(m_id,d_id)].memory_mb:.0f}MB</td><td style='color:#4ade80;font-weight:600'>READY</td></tr>" for m_id, d_id in RECOMMENDED_DEPLOYMENTS if (m_id, d_id) in result_map)
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Edge Validator</title><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}}header{{background:#1e293b;border-left:4px solid #C74634;padding:1.5rem 2rem;margin-bottom:2rem;border-radius:0 8px 8px 0}}h1{{font-size:1.6rem;color:#f1f5f9}}h2{{font-size:1.1rem;color:#C74634;margin:1.5rem 0 0.8rem;padding-bottom:0.4rem;border-bottom:1px solid #334155}}.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}.kpi{{background:#1e293b;border-radius:8px;padding:1rem;border-top:3px solid #C74634}}.kpi .label{{font-size:0.7rem;color:#64748b;text-transform:uppercase}}.kpi .value{{font-size:1.5rem;font-weight:700;color:#f1f5f9;margin-top:0.2rem}}table{{width:100%;border-collapse:collapse;font-size:0.85rem}}th{{background:#1e293b;color:#94a3b8;text-align:left;padding:0.6rem 0.8rem;font-size:0.75rem}}td{{padding:0.5rem 0.8rem;border-bottom:1px solid #1e293b;color:#cbd5e1}}footer{{text-align:center;color:#475569;font-size:0.75rem;margin-top:3rem;padding-top:1rem;border-top:1px solid #1e293b}}</style></head><body><header><h1>OCI Robot Cloud — Edge Deployment Validator</h1><p style='color:#94a3b8;font-size:0.9rem;margin-top:0.3rem'>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | {len(MODELS)} models × {len(EDGE_TARGETS)} devices = {len(results)} pairs</p></header><div class="kpi-grid"><div class="kpi"><div class="label">Pairs Passed</div><div class="value">{sum(1 for r in results if r.passed)}/{len(results)}</div></div><div class="kpi"><div class="label">Recommended</div><div class="value">{len(RECOMMENDED_DEPLOYMENTS)}</div></div><div class="kpi"><div class="label">Total Checks</div><div class="value">{len(results)*5}</div></div><div class="kpi"><div class="label">Avg Score</div><div class="value">{sum(r.score for r in results)/len(results):.0%}</div></div></div><h2>Recommended Deployments &#9733;</h2><table><thead><tr><th>Model</th><th>Device</th><th>Latency</th><th>RAM</th><th>Status</th></tr></thead><tbody>{rec_rows}</tbody></table><h2>Validation Matrix</h2><table><thead><tr><th>Model</th>{device_headers}</tr></thead><tbody>{matrix_rows}</tbody></table><footer>OCI Robot Cloud — Edge Deployment Validator | Oracle Confidential | Latency target: &lt;500ms | INT4 not supported on Nano</footer></body></html>"""
    with open("/tmp/edge_deployment_validator.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    return "/tmp/edge_deployment_validator.html"


def main() -> None:
    print("=" * 72); print("  OCI Robot Cloud — Edge Deployment Validator"); print("=" * 72)
    results = run_full_validation_matrix()
    result_map = {(r.artifact_id, r.target_id): r for r in results}
    print("\n  Compatibility Matrix:")
    print(f"  {'Model':<28}" + "".join(f"{t.device_type[:22]:<22}" for t in EDGE_TARGETS))
    print("  " + "-" * 94)
    for artifact in MODELS:
        row = f"  {artifact.model_id:<28}"
        for target in EDGE_TARGETS:
            res = result_map.get((artifact.model_id, target.device_id))
            cell = f"{'PASS' if res.passed else 'FAIL'} {res.latency_ms:>5.0f}ms {res.score:.0%}" if res else "—"
            row += f"{cell:<22}"
        print(row)
    passed = sum(1 for r in results if r.passed)
    print(f"\n  {passed}/{len(results)} pairs passed | {len(RECOMMENDED_DEPLOYMENTS)} recommended configs")
    output_path = generate_validation_report(results)
    print(f"  Report: {output_path}")


if __name__ == "__main__":
    main()
