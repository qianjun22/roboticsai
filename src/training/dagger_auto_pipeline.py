#!/usr/bin/env python3
"""
dagger_auto_pipeline.py — Monitors a DAgger run and auto-launches next iteration.

Polls the DAgger run output dir for results, generates a progress report,
optionally auto-launches run6 (long-tail DAgger) when run5 completes above threshold.

Usage:
    # Monitor run5 and auto-launch run6 when done (>= 25% success)
    python src/training/dagger_auto_pipeline.py \
        --watch-dir /tmp/dagger_run5 \
        --next-script src/training/dagger_run6.sh \
        --threshold 0.25 \
        --output /tmp/dagger_pipeline_report.html

    # Just monitor (no auto-launch)
    python src/training/dagger_auto_pipeline.py --watch-dir /tmp/dagger_run5

    # Mock mode (simulates run5 completing at 35%)
    python src/training/dagger_auto_pipeline.py --mock --output /tmp/dagger_pipeline_mock.html
"""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data polling
# ---------------------------------------------------------------------------

def poll_run_status(watch_dir: str) -> Dict:
    """
    Read summary.json or per-iter JSONs from watch_dir.

    Returns a dict:
        {
            "iter_count": int,
            "latest_success_rate": float,   # 0.0–1.0
            "run_complete": bool,
            "history": [
                {
                    "iter": int,
                    "success_rate": float,
                    "n_episodes": int,
                    "interventions_per_ep": float,
                }
            ]
        }
    """
    watch_path = Path(watch_dir)
    result = {
        "iter_count": 0,
        "latest_success_rate": 0.0,
        "run_complete": False,
        "history": [],
    }

    if not watch_path.exists():
        return result

    # Prefer consolidated summary.json
    summary_file = watch_path / "summary.json"
    if summary_file.exists():
        try:
            with open(summary_file) as f:
                data = json.load(f)
            result["run_complete"] = bool(data.get("run_complete", False))
            history = data.get("history", [])
            result["history"] = history
            result["iter_count"] = len(history)
            if history:
                result["latest_success_rate"] = history[-1].get("success_rate", 0.0)
            return result
        except (json.JSONDecodeError, KeyError):
            pass

    # Fall back to per-iter files: iter_001.json, iter_002.json, …
    iter_files = sorted(watch_path.glob("iter_*.json"))
    history = []
    for f in iter_files:
        try:
            with open(f) as fh:
                entry = json.load(fh)
            history.append(
                {
                    "iter": entry.get("iter", len(history) + 1),
                    "success_rate": float(entry.get("success_rate", 0.0)),
                    "n_episodes": int(entry.get("n_episodes", 0)),
                    "interventions_per_ep": float(entry.get("interventions_per_ep", 0.0)),
                }
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    # Check for a completion flag file
    complete_flag = watch_path / "run_complete"
    run_complete = complete_flag.exists()

    result["history"] = history
    result["iter_count"] = len(history)
    result["run_complete"] = run_complete
    if history:
        result["latest_success_rate"] = history[-1].get("success_rate", 0.0)

    return result


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

def wait_for_completion(
    watch_dir: str,
    poll_interval: int = 30,
    timeout_minutes: int = 180,
) -> Dict:
    """
    Poll watch_dir until run_complete flag appears in summary or timeout.

    Prints iteration progress to console. Returns final status dict.
    """
    deadline = time.time() + timeout_minutes * 60
    last_iter_count = -1

    print(f"[DAgger Pipeline] Watching: {watch_dir}")
    print(f"[DAgger Pipeline] Poll interval: {poll_interval}s  Timeout: {timeout_minutes}min")
    print(f"[DAgger Pipeline] Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    while True:
        status = poll_run_status(watch_dir)

        # Print new iterations as they appear
        if status["iter_count"] > last_iter_count:
            for entry in status["history"][last_iter_count + 1 :]:
                ts = datetime.now().strftime("%H:%M:%S")
                sr_pct = entry["success_rate"] * 100
                print(
                    f"  [{ts}] Iter {entry['iter']:>2d} | "
                    f"Success: {sr_pct:5.1f}% | "
                    f"Episodes: {entry['n_episodes']:>3d} | "
                    f"Interventions/ep: {entry['interventions_per_ep']:.1f}"
                )
            last_iter_count = status["iter_count"]

        if status["run_complete"]:
            print("-" * 60)
            print(
                f"[DAgger Pipeline] Run complete — "
                f"{status['iter_count']} iters, "
                f"final success {status['latest_success_rate'] * 100:.1f}%"
            )
            return status

        if time.time() >= deadline:
            print("-" * 60)
            print(
                f"[DAgger Pipeline] TIMEOUT after {timeout_minutes} min — "
                f"treating as incomplete."
            )
            status["run_complete"] = False
            return status

        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(
    history: List[Dict],
    output_path: str,
    run_name: str = "DAgger Run",
    next_action: str = "N/A",
) -> None:
    """
    Generate a dark-theme HTML report with SVG charts for success rate progression
    and expert intervention decline.
    """
    if not history:
        print("[DAgger Pipeline] No history data — skipping report.")
        return

    iters = [e["iter"] for e in history]
    success_rates = [e["success_rate"] * 100 for e in history]
    interventions = [e["interventions_per_ep"] for e in history]
    n_episodes = [e["n_episodes"] for e in history]

    # SVG dimensions
    W, H = 560, 220
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 40

    def make_svg(values: List[float], color: str, y_label: str, y_max: Optional[float] = None) -> str:
        if not values:
            return ""
        v_max = y_max if y_max is not None else max(values) * 1.15
        v_max = v_max if v_max > 0 else 1.0
        inner_w = W - pad_l - pad_r
        inner_h = H - pad_t - pad_b
        n = len(values)

        def px(i: int) -> float:
            return pad_l + (i / max(n - 1, 1)) * inner_w

        def py(v: float) -> float:
            return pad_t + inner_h - (v / v_max) * inner_h

        # Grid lines (4 horizontal)
        gridlines = ""
        for k in range(5):
            yv = (k / 4) * v_max
            y_coord = py(yv)
            gridlines += (
                f'<line x1="{pad_l}" y1="{y_coord:.1f}" '
                f'x2="{W - pad_r}" y2="{y_coord:.1f}" '
                f'stroke="#2A2A2E" stroke-width="1"/>'
            )
            label = f"{yv:.0f}" if y_max is None or y_max >= 10 else f"{yv:.1f}"
            gridlines += (
                f'<text x="{pad_l - 6}" y="{y_coord + 4:.1f}" '
                f'fill="#888" font-size="11" text-anchor="end">{label}</text>'
            )

        # Filled area
        if n == 1:
            area_pts = f"{px(0):.1f},{py(values[0]):.1f} {px(0):.1f},{py(0):.1f}"
        else:
            pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
            bottom_l = f"{px(n - 1):.1f},{py(0):.1f}"
            bottom_r = f"{px(0):.1f},{py(0):.1f}"
            area_pts = f"{pts} {bottom_l} {bottom_r}"

        area = (
            f'<polygon points="{area_pts}" '
            f'fill="{color}" fill-opacity="0.15"/>'
        )

        # Polyline
        if n == 1:
            line_pts = f"{px(0):.1f},{py(values[0]):.1f}"
        else:
            line_pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
        polyline = (
            f'<polyline points="{line_pts}" '
            f'fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

        # Dots + value labels
        dots = ""
        for i, v in enumerate(values):
            dots += (
                f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="4" '
                f'fill="{color}" stroke="#111113" stroke-width="2"/>'
            )
            val_text = f"{v:.1f}"
            dots += (
                f'<text x="{px(i):.1f}" y="{py(v) - 8:.1f}" '
                f'fill="{color}" font-size="11" text-anchor="middle">{val_text}</text>'
            )

        # X-axis labels
        x_labels = ""
        for i, it in enumerate(iters):
            x_labels += (
                f'<text x="{px(i):.1f}" y="{H - 8}" '
                f'fill="#888" font-size="11" text-anchor="middle">Iter {it}</text>'
            )

        # Y-axis label (rotated)
        y_axis_label = (
            f'<text transform="rotate(-90)" x="{-(pad_t + inner_h / 2):.1f}" '
            f'y="14" fill="#aaa" font-size="11" text-anchor="middle">{y_label}</text>'
        )

        # Axes
        axes = (
            f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + inner_h}" '
            f'stroke="#444" stroke-width="1"/>'
            f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{W - pad_r}" y2="{pad_t + inner_h}" '
            f'stroke="#444" stroke-width="1"/>'
        )

        return (
            f'<svg width="{W}" height="{H}" '
            f'style="background:#1C1C1E;border-radius:8px;display:block;width:100%">'
            f'{gridlines}{area}{polyline}{dots}{x_labels}{y_axis_label}{axes}'
            f"</svg>"
        )

    svg_success = make_svg(success_rates, "#C74634", "Success Rate (%)", y_max=100)
    svg_interventions = make_svg(interventions, "#4A90D9", "Interventions / Episode")

    # Key insights
    delta_sr = success_rates[-1] - success_rates[0] if len(success_rates) > 1 else 0.0
    delta_iv = interventions[0] - interventions[-1] if len(interventions) > 1 else 0.0
    final_sr = success_rates[-1]
    final_iv = interventions[-1]

    insights_html = f"""
    <div class="insight-box">
        <div class="insight-title">Key Insights</div>
        <ul class="insight-list">
            <li>Final success rate: <strong>{final_sr:.1f}%</strong>
                (+{delta_sr:.1f}pp over {len(history)} iters)</li>
            <li>Expert interventions reduced from
                <strong>{interventions[0]:.1f}</strong> →
                <strong>{final_iv:.1f}</strong> per episode
                (−{delta_iv:.1f})</li>
            <li>Total episodes collected:
                <strong>{sum(n_episodes)}</strong></li>
            <li>Next action: <strong>{next_action}</strong></li>
        </ul>
    </div>
    """

    # Table
    rows_html = ""
    for e in history:
        rows_html += (
            f"<tr>"
            f"<td>{e['iter']}</td>"
            f"<td>{e['success_rate'] * 100:.1f}%</td>"
            f"<td>{e['n_episodes']}</td>"
            f"<td>{e['interventions_per_ep']:.1f}</td>"
            f"</tr>\n"
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{run_name} — DAgger Pipeline Report</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #111113;
    color: #E5E5EA;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    padding: 32px 24px;
    max-width: 860px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
  .subtitle {{ color: #888; font-size: 13px; margin-bottom: 28px; }}
  .section-title {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #C74634;
    margin: 28px 0 12px;
  }}
  .card {{
    background: #1C1C1E;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .card-title {{ font-size: 14px; font-weight: 600; color: #E5E5EA; margin-bottom: 14px; }}
  .insight-box {{
    background: #1C1C1E;
    border-left: 3px solid #C74634;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin-bottom: 20px;
  }}
  .insight-title {{ font-size: 13px; font-weight: 700; color: #C74634; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.06em; }}
  .insight-list {{ padding-left: 18px; line-height: 1.9; color: #ccc; }}
  .insight-list strong {{ color: #E5E5EA; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    text-align: left;
    padding: 8px 12px;
    background: #252528;
    color: #888;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #222; color: #ddd; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #222224; }}
  .footer {{
    margin-top: 32px;
    font-size: 12px;
    color: #555;
    text-align: center;
  }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    margin-left: 10px;
    vertical-align: middle;
  }}
  .badge-green {{ background: #1a3a1a; color: #5cb85c; }}
  .badge-yellow {{ background: #3a2e00; color: #f0c040; }}
  .badge-red {{ background: #3a1a1a; color: #e06060; }}
</style>
</head>
<body>

<h1>{run_name}</h1>
<div class="subtitle">OCI Robot Cloud — DAgger Auto-Pipeline Report &nbsp;·&nbsp; Generated {generated_at}</div>

{insights_html}

<div class="section-title">Success Rate Progression</div>
<div class="card">
  <div class="card-title">Task Success Rate per DAgger Iteration (%)</div>
  {svg_success}
</div>

<div class="section-title">Expert Intervention Decline</div>
<div class="card">
  <div class="card-title">Expert Interventions per Episode</div>
  {svg_interventions}
</div>

<div class="section-title">Iteration Details</div>
<div class="card" style="padding:0;overflow:hidden;">
<table>
  <thead>
    <tr>
      <th>Iteration</th>
      <th>Success Rate</th>
      <th>Episodes</th>
      <th>Interventions/Ep</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</div>

<div class="footer">OCI Robot Cloud · DAgger Auto-Pipeline · oracle.com/cloud/compute/gpu</div>
</body>
</html>
"""

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path_obj, "w") as f:
        f.write(html)
    print(f"[DAgger Pipeline] Report saved → {output_path}")


# ---------------------------------------------------------------------------
# Auto-launch next run
# ---------------------------------------------------------------------------

def maybe_launch_next(
    success_rate: float,
    threshold: float,
    next_script: Optional[str],
) -> bool:
    """
    Launch next_script if success_rate >= threshold.
    Returns True if launched, False otherwise.
    """
    if next_script is None:
        print("[DAgger Pipeline] No --next-script provided — skipping auto-launch.")
        return False

    if success_rate >= threshold:
        print(
            f"[DAgger Pipeline] Success rate {success_rate * 100:.1f}% >= "
            f"threshold {threshold * 100:.1f}% — launching {next_script}"
        )
        try:
            proc = subprocess.Popen(
                ["bash", next_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            print(f"[DAgger Pipeline] Launched PID {proc.pid}: {next_script}")
            return True
        except FileNotFoundError:
            print(f"[DAgger Pipeline] ERROR: script not found: {next_script}")
            return False
        except OSError as exc:
            print(f"[DAgger Pipeline] ERROR launching {next_script}: {exc}")
            return False
    else:
        print(
            f"[DAgger Pipeline] Success rate {success_rate * 100:.1f}% < "
            f"threshold {threshold * 100:.1f}% — NOT launching next run."
        )
        return False


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_HISTORY = [
    {"iter": 1, "success_rate": 0.07, "n_episodes": 80,  "interventions_per_ep": 19.2},
    {"iter": 2, "success_rate": 0.18, "n_episodes": 80,  "interventions_per_ep": 14.8},
    {"iter": 3, "success_rate": 0.28, "n_episodes": 80,  "interventions_per_ep": 10.3},
    {"iter": 4, "success_rate": 0.35, "n_episodes": 80,  "interventions_per_ep":  7.1},
    {"iter": 5, "success_rate": 0.41, "n_episodes": 80,  "interventions_per_ep":  4.9},
]


def run_mock(args: argparse.Namespace) -> None:
    """Simulate a completed run5 at 41% and exercise the full pipeline."""
    print("[DAgger Pipeline] MOCK MODE — simulating run5 completion")
    print("-" * 60)

    history = MOCK_HISTORY
    for entry in history:
        ts = datetime.now().strftime("%H:%M:%S")
        sr_pct = entry["success_rate"] * 100
        print(
            f"  [{ts}] Iter {entry['iter']:>2d} | "
            f"Success: {sr_pct:5.1f}% | "
            f"Episodes: {entry['n_episodes']:>3d} | "
            f"Interventions/ep: {entry['interventions_per_ep']:.1f}"
        )
        time.sleep(0.15)  # brief visual delay

    print("-" * 60)
    final_sr = history[-1]["success_rate"]
    print(f"[DAgger Pipeline] Mock run complete — final success {final_sr * 100:.1f}%")

    output = args.output or "/tmp/dagger_pipeline_mock.html"
    next_action = "Skipped (--no-auto-launch)" if args.no_auto_launch else (
        f"Auto-launch {args.next_script}" if args.next_script else "No next script"
    )
    generate_html_report(history, output, run_name="DAgger Run5 (Mock)", next_action=next_action)

    if not args.no_auto_launch:
        maybe_launch_next(final_sr, args.threshold, args.next_script)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor a DAgger run and auto-launch next iteration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--watch-dir",
        default=None,
        help="Directory to watch for DAgger run output (summary.json or iter_*.json).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Seconds between polls (default: 30).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        metavar="MINUTES",
        help="Max minutes to wait before giving up (default: 180).",
    )
    parser.add_argument(
        "--next-script",
        default=None,
        metavar="PATH",
        help="Shell script to launch when run completes above threshold.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.25,
        metavar="RATE",
        help="Minimum success rate (0–1) to trigger auto-launch (default: 0.25).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Path for HTML report output.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (simulates run5 completing at 41%%).",
    )
    parser.add_argument(
        "--no-auto-launch",
        action="store_true",
        help="Monitor only — do not auto-launch next script even if threshold met.",
    )

    args = parser.parse_args()

    if args.mock:
        run_mock(args)
        return

    if not args.watch_dir:
        parser.error("--watch-dir is required unless --mock is set.")

    # Live monitoring
    status = wait_for_completion(
        args.watch_dir,
        poll_interval=args.poll_interval,
        timeout_minutes=args.timeout,
    )

    history = status.get("history", [])
    final_sr = status.get("latest_success_rate", 0.0)

    if args.output:
        next_action = "Skipped (--no-auto-launch)" if args.no_auto_launch else (
            f"Auto-launch {args.next_script}" if args.next_script else "No next script configured"
        )
        run_name = Path(args.watch_dir).name if args.watch_dir else "DAgger Run"
        generate_html_report(history, args.output, run_name=run_name, next_action=next_action)

    if not args.no_auto_launch and status.get("run_complete", False):
        maybe_launch_next(final_sr, args.threshold, args.next_script)
    elif args.no_auto_launch:
        print("[DAgger Pipeline] --no-auto-launch set — skipping auto-launch check.")


if __name__ == "__main__":
    main()
