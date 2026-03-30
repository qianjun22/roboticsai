#!/usr/bin/env python3
"""
Unified Evaluation Harness for GR00T Checkpoints.

Orchestrates all 7 evaluation modules in one shot and produces a
consolidated HTML report, JSON output, and console summary.

Usage:
    python3 evaluation_harness.py \\
        --mock \\
        --checkpoint dagger_run9/checkpoint_5000 \\
        --output /tmp/evaluation_harness.html \\
        --seed 42
"""

import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + text + _RESET


# ---------------------------------------------------------------------------
# Module result dataclass (stdlib-friendly)
# ---------------------------------------------------------------------------
class ModuleResult:
    def __init__(
        self,
        name: str,
        status: str,          # "passed" | "warned" | "failed"
        key_metrics: dict,
        run_time_s: float,
        notes: str = "",
    ):
        self.name = name
        self.status = status
        self.key_metrics = key_metrics
        self.run_time_s = run_time_s
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "key_metrics": self.key_metrics,
            "run_time_s": round(self.run_time_s, 3),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Simulated evaluation modules
# ---------------------------------------------------------------------------

def _sleep(seconds: float) -> None:
    """Fake progress by sleeping a fraction of the claimed time."""
    time.sleep(min(seconds * 0.05, 0.6))


def run_closed_loop_eval(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(3.2)

    num_episodes = 20
    successes = rng.randint(7, 9)           # 35-45 % baseline
    sr_pct = round(successes / num_episodes * 100, 1)
    latencies_ms = [rng.gauss(228, 12) for _ in range(num_episodes)]
    avg_lat = round(sum(latencies_ms) / len(latencies_ms), 1)

    # 40 % SR is acceptable for this checkpoint (≥35 % threshold)
    status = "passed" if sr_pct >= 35.0 else "warned"

    return ModuleResult(
        name="closed_loop_eval",
        status=status,
        key_metrics={
            "num_episodes": num_episodes,
            "successes": successes,
            "success_rate_pct": sr_pct,
            "avg_latency_ms": avg_lat,
            "threshold_sr_pct": 35.0,
        },
        run_time_s=time.perf_counter() - start,
        notes=f"{successes}/{num_episodes} episodes successful",
    )


def run_mae_validation(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(1.8)

    mae = round(rng.gauss(0.013, 0.002), 4)
    threshold = 0.030
    status = "passed" if mae <= threshold else "failed"

    return ModuleResult(
        name="mae_validation",
        status=status,
        key_metrics={
            "validation_mae": mae,
            "threshold_mae": threshold,
            "improvement_vs_baseline_pct": round((0.103 - mae) / 0.103 * 100, 1),
        },
        run_time_s=time.perf_counter() - start,
        notes=f"MAE {mae} vs threshold {threshold}",
    )


def run_action_smoothness(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(1.2)

    jerk_rms = round(rng.gauss(0.042, 0.005), 4)
    threshold = 0.10
    status = "passed" if jerk_rms <= threshold else "warned"

    return ModuleResult(
        name="action_smoothness",
        status=status,
        key_metrics={
            "jerk_rms": jerk_rms,
            "threshold_jerk_rms": threshold,
            "num_action_sequences_sampled": 500,
        },
        run_time_s=time.perf_counter() - start,
        notes=f"Jerk RMS {jerk_rms} (lower is smoother)",
    )


def run_robustness_check(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(2.5)

    perturbations = {
        "brightness": round(rng.gauss(38, 4), 1),
        "joint_noise": round(rng.gauss(35, 3), 1),
        "dynamics_mismatch": round(rng.gauss(30, 5), 1),
    }
    threshold_pct = 25.0
    all_pass = all(v >= threshold_pct for v in perturbations.values())
    status = "passed" if all_pass else "warned"

    return ModuleResult(
        name="robustness_check",
        status=status,
        key_metrics={
            "sr_brightness_pct": perturbations["brightness"],
            "sr_joint_noise_pct": perturbations["joint_noise"],
            "sr_dynamics_mismatch_pct": perturbations["dynamics_mismatch"],
            "threshold_each_pct": threshold_pct,
        },
        run_time_s=time.perf_counter() - start,
        notes="SR under 3 perturbation scenarios",
    )


def run_regression_gate(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(0.9)

    # 14 regression thresholds — all pass for this checkpoint
    thresholds = [
        ("mae_franka_pick", 0.030, round(rng.gauss(0.014, 0.001), 4)),
        ("mae_franka_stack", 0.035, round(rng.gauss(0.018, 0.002), 4)),
        ("mae_franka_push", 0.028, round(rng.gauss(0.011, 0.001), 4)),
        ("mae_franka_slide", 0.032, round(rng.gauss(0.015, 0.002), 4)),
        ("sr_easy_pct", 50.0, round(rng.gauss(55, 4), 1)),
        ("sr_medium_pct", 35.0, round(rng.gauss(40, 4), 1)),
        ("sr_hard_pct", 15.0, round(rng.gauss(20, 3), 1)),
        ("jerk_rms_max", 0.10, round(rng.gauss(0.044, 0.005), 4)),
        ("latency_p50_ms", 300.0, round(rng.gauss(230, 10), 1)),
        ("latency_p95_ms", 380.0, round(rng.gauss(340, 15), 1)),
        ("latency_p99_ms", 450.0, round(rng.gauss(380, 20), 1)),
        ("peak_vram_gb", 10.0, round(rng.gauss(7.2, 0.3), 2)),
        ("load_time_s", 30.0, round(rng.gauss(18, 2), 1)),
        ("robustness_min_sr_pct", 25.0, round(rng.gauss(30, 3), 1)),
    ]

    results = []
    failures = 0
    for name, thresh, val in thresholds:
        passed = val <= thresh if "mae" in name or "latency" in name or "vram" in name or "load" in name or "jerk" in name else val >= thresh
        results.append({"metric": name, "threshold": thresh, "value": val, "passed": passed})
        if not passed:
            failures += 1

    status = "passed" if failures == 0 else ("warned" if failures <= 2 else "failed")

    return ModuleResult(
        name="regression_gate",
        status=status,
        key_metrics={
            "total_thresholds": len(thresholds),
            "passed": len(thresholds) - failures,
            "failed": failures,
            "details": results,
        },
        run_time_s=time.perf_counter() - start,
        notes=f"{len(thresholds) - failures}/{len(thresholds)} regression checks passed",
    )


def run_latency_benchmark(rng: random.Random) -> ModuleResult:
    """p99 = 410ms intentionally triggers a warning (SLA = 400ms)."""
    start = time.perf_counter()
    _sleep(1.5)

    # Simulate 200 inference calls
    samples = sorted(max(180.0, rng.gauss(230, 25)) for _ in range(200))
    p50 = round(samples[99], 1)
    p95 = round(samples[189], 1)
    # Force p99 slightly above 400ms SLA to produce the intended warning
    p99 = 410.0

    sla_p50 = 300.0
    sla_p95 = 380.0
    sla_p99 = 400.0

    warn = p99 > sla_p99
    failed = p50 > sla_p50 or p95 > sla_p95
    status = "failed" if failed else ("warned" if warn else "passed")

    return ModuleResult(
        name="latency_benchmark",
        status=status,
        key_metrics={
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "num_samples": 200,
            "sla_p50_ms": sla_p50,
            "sla_p95_ms": sla_p95,
            "sla_p99_ms": sla_p99,
        },
        run_time_s=time.perf_counter() - start,
        notes="p99=410ms exceeds SLA 400ms — within acceptable range for non-realtime",
    )


def run_memory_snapshot(rng: random.Random) -> ModuleResult:
    start = time.perf_counter()
    _sleep(0.7)

    peak_vram_gb = round(rng.gauss(7.2, 0.3), 2)
    load_time_s = round(rng.gauss(18.4, 1.5), 1)
    threshold_vram = 10.0
    threshold_load = 30.0

    status = "passed" if peak_vram_gb <= threshold_vram and load_time_s <= threshold_load else "warned"

    return ModuleResult(
        name="memory_snapshot",
        status=status,
        key_metrics={
            "peak_vram_gb": peak_vram_gb,
            "load_time_s": load_time_s,
            "threshold_vram_gb": threshold_vram,
            "threshold_load_s": threshold_load,
            "gpu": "NVIDIA A100 40GB",
        },
        run_time_s=time.perf_counter() - start,
        notes=f"VRAM {peak_vram_gb}GB / 10GB limit; load {load_time_s}s / 30s limit",
    )


# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------
MODULES = [
    ("closed_loop_eval",   run_closed_loop_eval),
    ("mae_validation",     run_mae_validation),
    ("action_smoothness",  run_action_smoothness),
    ("robustness_check",   run_robustness_check),
    ("regression_gate",    run_regression_gate),
    ("latency_benchmark",  run_latency_benchmark),
    ("memory_snapshot",    run_memory_snapshot),
]


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------
def compute_verdict(results: list[ModuleResult]) -> str:
    statuses = [r.status for r in results]
    if "failed" in statuses:
        return "BLOCKED"
    if "warned" in statuses:
        return "NEEDS_REVIEW"
    return "DEPLOY_READY"


# ---------------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------------
_STATUS_SYMBOLS = {"passed": "✓", "warned": "⚠", "failed": "✗"}
_STATUS_COLORS  = {"passed": _GREEN, "warned": _YELLOW, "failed": _RED}

def _status_str(status: str) -> str:
    sym = _STATUS_SYMBOLS.get(status, "?")
    col = _STATUS_COLORS.get(status, "")
    return _c(f" {sym} {status.upper()} ", col, _BOLD)


def print_progress(module_name: str, status: str, elapsed: float) -> None:
    label = f"  {module_name:<25}"
    badge = _status_str(status)
    timing = _c(f"  {elapsed:.2f}s", _DIM)
    print(f"{label} {badge}{timing}")


def print_verdict_banner(verdict: str, checkpoint: str, total_time: float) -> None:
    width = 62
    color = {
        "DEPLOY_READY":  _GREEN,
        "NEEDS_REVIEW":  _YELLOW,
        "BLOCKED":       _RED,
    }.get(verdict, "")

    border = _c("=" * width, color, _BOLD)
    pad    = " " * ((width - len(verdict)) // 2)
    mid    = _c(f"{pad}{verdict}{pad}", color, _BOLD)

    print()
    print(border)
    print(mid)
    print(border)
    print(_c(f"  Checkpoint : {checkpoint}", _CYAN))
    print(_c(f"  Total time : {total_time:.1f}s", _DIM))
    print()


# ---------------------------------------------------------------------------
# HTML generation (dark theme, self-contained)
# ---------------------------------------------------------------------------

_STATUS_CSS = {
    "passed":      ("#22c55e", "#14532d"),
    "warned":      ("#facc15", "#713f12"),
    "failed":      ("#ef4444", "#7f1d1d"),
    "DEPLOY_READY":("#22c55e", "#14532d"),
    "NEEDS_REVIEW":("#facc15", "#713f12"),
    "BLOCKED":     ("#ef4444", "#7f1d1d"),
}


def _badge(status: str) -> str:
    fg, bg = _STATUS_CSS.get(status, ("#94a3b8", "#1e293b"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:4px;font-weight:700;font-size:0.82em;'
        f'border:1px solid {fg};">{status.upper()}</span>'
    )


def _metric_rows(metrics: dict, indent: int = 0) -> str:
    rows = []
    for k, v in metrics.items():
        if k == "details":
            continue
        rows.append(
            f'<tr><td style="color:#94a3b8;padding:2px 6px;">{k}</td>'
            f'<td style="color:#e2e8f0;padding:2px 6px;">{v}</td></tr>'
        )
    return "".join(rows)


def _timing_bar_chart(results: list[ModuleResult], max_width_px: int = 320) -> str:
    max_t = max(r.run_time_s for r in results) or 1.0
    bars = []
    for r in results:
        width = int(r.run_time_s / max_t * max_width_px)
        fg, _ = _STATUS_CSS.get(r.status, ("#94a3b8", "#1e293b"))
        bars.append(
            f'<div style="display:flex;align-items:center;margin:4px 0;">'
            f'  <div style="width:180px;color:#94a3b8;font-size:0.78em;text-align:right;'
            f'padding-right:8px;">{r.name}</div>'
            f'  <div style="width:{width}px;height:16px;background:{fg};'
            f'border-radius:3px;"></div>'
            f'  <div style="color:#94a3b8;font-size:0.78em;padding-left:8px;">'
            f'{r.run_time_s:.2f}s</div>'
            f'</div>'
        )
    return "\n".join(bars)


def _full_metrics_table(results: list[ModuleResult]) -> str:
    rows = []
    for r in results:
        fg, bg = _STATUS_CSS.get(r.status, ("#94a3b8", "#1e293b"))
        for k, v in r.key_metrics.items():
            if k == "details":
                continue
            # Determine threshold key heuristically
            thresh_key = None
            for candidate in (f"threshold_{k}", f"sla_{k}", "threshold_mae",
                               "threshold_jerk_rms", "threshold_sr_pct"):
                if candidate in r.key_metrics:
                    thresh_key = candidate
                    break
            thresh_val = r.key_metrics.get(thresh_key, "—") if thresh_key else "—"
            row_status = r.status
            rows.append(
                f'<tr>'
                f'<td style="color:#94a3b8;padding:4px 10px;">{r.name}</td>'
                f'<td style="color:#e2e8f0;padding:4px 10px;">{k}</td>'
                f'<td style="color:#f1f5f9;padding:4px 10px;font-family:monospace;">{v}</td>'
                f'<td style="color:#64748b;padding:4px 10px;font-family:monospace;">{thresh_val}</td>'
                f'<td style="padding:4px 10px;">{_badge(row_status)}</td>'
                f'</tr>'
            )
    return "\n".join(rows)


def generate_html(
    results: list[ModuleResult],
    verdict: str,
    checkpoint: str,
    total_time: float,
    timestamp: str,
    recommendation: str,
) -> str:
    verdict_fg, verdict_bg = _STATUS_CSS.get(verdict, ("#94a3b8", "#1e293b"))

    # Module cards (2-column grid)
    cards = []
    for r in results:
        fg, bg = _STATUS_CSS.get(r.status, ("#94a3b8", "#1e293b"))
        metric_html = (
            '<table style="width:100%;border-collapse:collapse;">'
            + _metric_rows(r.key_metrics)
            + "</table>"
        )
        cards.append(f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                    padding:16px;display:flex;flex-direction:column;gap:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#e2e8f0;font-weight:700;font-size:0.95em;">{r.name}</span>
            {_badge(r.status)}
          </div>
          <div style="font-size:0.75em;color:#64748b;">{r.run_time_s:.2f}s &nbsp;|&nbsp; {r.notes}</div>
          {metric_html}
        </div>""")

    cards_html = "\n".join(cards)

    timing_chart = _timing_bar_chart(results)
    full_table   = _full_metrics_table(results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>GR00T Evaluation Harness — {checkpoint}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px;
      line-height: 1.6;
      padding: 32px;
    }}
    h2 {{ color: #94a3b8; font-size: 1em; font-weight: 600; margin-bottom: 12px;
           letter-spacing: 0.08em; text-transform: uppercase; }}
    section {{ margin-bottom: 40px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th {{ color: #64748b; font-size: 0.78em; text-align: left;
          padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    td {{ border-bottom: 1px solid #1e293b; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    .module-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }}
    @media (max-width: 800px) {{ .module-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>

<!-- ── VERDICT BANNER ──────────────────────────────────────────────── -->
<section>
  <div style="background:{verdict_bg};border:2px solid {verdict_fg};border-radius:12px;
              padding:28px 32px;text-align:center;">
    <div style="color:{verdict_fg};font-size:2.4em;font-weight:900;
                letter-spacing:0.12em;">{verdict}</div>
    <div style="color:#e2e8f0;margin-top:8px;font-size:1em;">
      Checkpoint: <strong>{checkpoint}</strong>
    </div>
    <div style="color:#94a3b8;margin-top:4px;font-size:0.82em;">
      Evaluated {timestamp} &nbsp;|&nbsp; Total runtime: {total_time:.1f}s
    </div>
  </div>
</section>

<!-- ── RECOMMENDATION ──────────────────────────────────────────────── -->
<section>
  <h2>Recommendation</h2>
  <div style="background:#1e293b;border-left:4px solid {verdict_fg};
              border-radius:0 8px 8px 0;padding:14px 20px;color:#f1f5f9;">
    {recommendation}
  </div>
</section>

<!-- ── MODULE CARDS ────────────────────────────────────────────────── -->
<section>
  <h2>Module Results</h2>
  <div class="module-grid">
    {cards_html}
  </div>
</section>

<!-- ── TIMING CHART ────────────────────────────────────────────────── -->
<section>
  <h2>Module Timing</h2>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;">
    {timing_chart}
  </div>
</section>

<!-- ── FULL METRICS TABLE ──────────────────────────────────────────── -->
<section>
  <h2>Full Metrics</h2>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;overflow:auto;">
    <table>
      <thead>
        <tr>
          <th>Module</th>
          <th>Metric</th>
          <th>Value</th>
          <th>Threshold</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {full_table}
      </tbody>
    </table>
  </div>
</section>

<div style="color:#334155;font-size:0.75em;text-align:center;margin-top:16px;">
  GR00T Evaluation Harness &mdash; OCI Robot Cloud &mdash; {timestamp}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# JSON serialization helper
# ---------------------------------------------------------------------------

def _make_json_output(
    results: list[ModuleResult],
    verdict: str,
    checkpoint: str,
    total_time_s: float,
    timestamp: str,
    recommendation: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "timestamp": timestamp,
        "checkpoint": checkpoint,
        "verdict": verdict,
        "total_time_s": round(total_time_s, 3),
        "recommendation": recommendation,
        "modules": [r.to_dict() for r in results],
    }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_harness(checkpoint: str, seed: int, mock: bool) -> tuple[list[ModuleResult], str, float]:
    rng = random.Random(seed)

    print()
    print(_c(f"  GR00T Evaluation Harness", _BOLD, _CYAN))
    print(_c(f"  Checkpoint : {checkpoint}", _DIM))
    print(_c(f"  Seed       : {seed}", _DIM))
    print(_c(f"  Mode       : {'mock (simulated)' if mock else 'live'}", _DIM))
    print()
    print(_c("  Module                    Status         Time", _DIM))
    print(_c("  " + "-" * 54, _DIM))

    results: list[ModuleResult] = []
    harness_start = time.perf_counter()

    for mod_name, mod_fn in MODULES:
        sys.stdout.write(f"  {mod_name:<25}  running...   ")
        sys.stdout.flush()
        result = mod_fn(rng)
        # Overwrite line with result
        sys.stdout.write(f"\r")
        print_progress(mod_name, result.status, result.run_time_s)
        results.append(result)

    total_time = time.perf_counter() - harness_start
    verdict = compute_verdict(results)
    return results, verdict, total_time


def build_recommendation(results: list[ModuleResult], verdict: str) -> str:
    warns = [r for r in results if r.status == "warned"]
    fails = [r for r in results if r.status == "failed"]

    if verdict == "DEPLOY_READY":
        return "All evaluation modules passed. Checkpoint is ready for deployment."

    if verdict == "BLOCKED":
        names = ", ".join(r.name for r in fails)
        return (
            f"{len(fails)} critical failure(s) in [{names}]. "
            "Resolve failures before deployment."
        )

    # NEEDS_REVIEW — surface specific warnings
    parts = []
    for r in warns:
        if r.name == "latency_benchmark":
            p99 = r.key_metrics.get("p99_ms", "?")
            sla = r.key_metrics.get("sla_p99_ms", "?")
            parts.append(
                f"1 warning: p99={p99}ms exceeds SLA {sla}ms "
                "— acceptable for non-realtime workloads"
            )
        else:
            parts.append(f"Warning in {r.name}: {r.notes}")
    return " | ".join(parts) if parts else f"{len(warns)} warning(s) — review before deploy."


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified GR00T evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Run in mock/simulated mode (no real inference calls)",
    )
    parser.add_argument(
        "--checkpoint",
        default="dagger_run9/checkpoint_5000",
        help="Checkpoint identifier (default: dagger_run9/checkpoint_5000)",
    )
    parser.add_argument(
        "--output",
        default="/tmp/evaluation_harness.html",
        help="Path for HTML report output (default: /tmp/evaluation_harness.html)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for mock simulation (default: 42)",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for JSON output (auto-derived from --output if not set)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.mock:
        print(
            _c(
                "\nWARNING: --mock not set. This script only supports mock mode.\n"
                "Re-run with --mock to proceed.\n",
                _YELLOW,
            )
        )
        sys.exit(1)

    results, verdict, total_time = run_harness(
        checkpoint=args.checkpoint,
        seed=args.seed,
        mock=args.mock,
    )

    recommendation = build_recommendation(results, verdict)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print_verdict_banner(verdict, args.checkpoint, total_time)

    if recommendation:
        print(_c(f"  Recommendation:", _BOLD))
        print(f"  {recommendation}")
        print()

    # ── HTML ──────────────────────────────────────────────────────────
    html = generate_html(
        results=results,
        verdict=verdict,
        checkpoint=args.checkpoint,
        total_time=total_time,
        timestamp=timestamp,
        recommendation=recommendation,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(_c(f"  HTML report  → {out_path}", _CYAN))

    # ── JSON ──────────────────────────────────────────────────────────
    json_path = Path(args.json_output) if args.json_output else out_path.with_suffix(".json")
    payload = _make_json_output(
        results=results,
        verdict=verdict,
        checkpoint=args.checkpoint,
        total_time_s=total_time,
        timestamp=timestamp,
        recommendation=recommendation,
    )
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(_c(f"  JSON output  → {json_path}", _CYAN))
    print()


if __name__ == "__main__":
    main()
