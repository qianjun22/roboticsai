#!/usr/bin/env python3
"""
eval_watcher.py — Monitor OCI pipeline output dirs and generate a final results summary.

Polls one or more directories for summary.json files written by closed_loop_eval.py
or post_train_pipeline.sh.  Once ALL watched dirs have a summary, generates a
clean markdown report, prints it to stdout, and optionally patches roadmap.md.

Usage:
    # Watch two pipeline outputs, generate report when both finish:
    python src/eval/eval_watcher.py \\
        --watch /tmp/eval_1000demo /tmp/eval_dagger_final \\
        --labels "1000-demo BC" "DAgger-final" \\
        --output /tmp/final_results.md

    # Single check (CI / post-run):
    python src/eval/eval_watcher.py \\
        --watch /tmp/eval_1000demo \\
        --labels "1000-demo BC" \\
        --output /tmp/final_results.md \\
        --once

    # Mock mode — creates fake summary.json files and runs normally:
    python src/eval/eval_watcher.py --mock
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT        = "/tmp/final_results.md"
DEFAULT_POLL_INTERVAL = 30          # seconds
DEFAULT_TIMEOUT       = 3600        # seconds (1 h)
ROADMAP_PATH = Path(
    "/Users/junqian/Obsidian/Vault2026/Robotics/docs/roadmap.md"
)
ROADMAP_PLACEHOLDER = (
    "**1000-demo + DAgger pipeline results**: post_train_pipeline.sh in progress"
)

# ── Mock data ─────────────────────────────────────────────────────────────────
MOCK_SUMMARIES = {
    "1000-demo BC": {
        "label": "1000-demo BC",
        "success_rate": 0.10,
        "num_episodes": 20,
        "avg_latency_ms": 231.0,
        "train_loss": 0.099,
        "train_mae": None,
        "checkpoint": "checkpoint-5000",
        "steps": 5000,
    },
    "DAgger-final": {
        "label": "DAgger-final",
        "success_rate": 0.65,
        "num_episodes": 20,
        "avg_latency_ms": 227.3,
        "train_loss": 0.058,
        "train_mae": None,
        "checkpoint": "dagger-iter3-checkpoint-2000",
        "steps": 2000,
    },
}


# ── Summary loading ────────────────────────────────────────────────────────────

def load_summary(watch_dir: Path) -> dict | None:
    """Return parsed summary.json from *watch_dir*, or None if not ready."""
    path = watch_dir / "summary.json"
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [WARN] Could not parse {path}: {exc}", file=sys.stderr)
        return None


# ── Markdown report builder ────────────────────────────────────────────────────

def build_markdown(results: list[dict], date_str: str) -> str:
    """Generate the final pipeline results markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Training Metrics table ─────────────────────────────────────────────
    train_rows = []
    for r in results:
        ckpt   = r.get("checkpoint") or r.get("label", "—")
        steps  = r.get("steps")
        loss   = r.get("train_loss")
        mae    = r.get("train_mae")
        steps_str = f"{steps:,}" if steps else "—"
        loss_str  = f"{loss:.3f}" if loss is not None else "TBD"
        mae_str   = f"{mae:.3f}" if mae is not None else "TBD"
        # Annotate with step count in checkpoint column when available
        ckpt_col = f"{r.get('label', ckpt)}, {steps_str} steps" if steps else ckpt
        train_rows.append(f"| {ckpt_col} | {loss_str} | {mae_str} |")

    training_table = (
        "## Training Metrics\n"
        "| Checkpoint | Loss | MAE |\n"
        "|------------|------|-----|\n"
        + "\n".join(train_rows)
    )

    # ── Closed-loop Eval table ─────────────────────────────────────────────
    eval_rows = []
    for r in results:
        label   = r.get("label", "—")
        sr      = r.get("success_rate")
        n_ep    = r.get("num_episodes", "—")
        latency = r.get("avg_latency_ms")
        sr_str  = f"{sr * 100:.0f}%" if sr is not None else "—"
        lat_str = f"{latency:.0f}ms" if latency is not None else "—"
        eval_rows.append(f"| {label} | {sr_str} | {n_ep} | {lat_str} |")

    eval_table = (
        "## Closed-Loop Eval Results\n"
        "| Run | Success Rate | Episodes | Avg Latency |\n"
        "|-----|-------------|----------|-------------|\n"
        + "\n".join(eval_rows)
    )

    # ── Improvement summary ────────────────────────────────────────────────
    improvement_lines: list[str] = []
    if len(results) >= 2:
        baseline = results[0]
        best = max(results, key=lambda r: r.get("success_rate") or 0.0)
        bc_sr   = baseline.get("success_rate") or 0.0
        best_sr = best.get("success_rate") or 0.0
        best_lbl = best.get("label", "—")

        if bc_sr > 0:
            mult = best_sr / bc_sr
            improvement_lines.append(
                f"- DAgger improvement over BC baseline: {mult:.1f}×"
            )
        else:
            improvement_lines.append(
                "- DAgger improvement over BC baseline: BC was 0% (improvement unbounded)"
            )
        improvement_lines.append(
            f"- Best closed-loop success rate: {best_sr * 100:.0f}% ({best_lbl})"
        )
    else:
        sr = results[0].get("success_rate") or 0.0
        improvement_lines.append(
            f"- Closed-loop success rate: {sr * 100:.0f}%"
        )

    improvement_block = "## Improvement Summary\n" + "\n".join(improvement_lines)

    return (
        f"# Pipeline Results — {date_str}\n\n"
        f"{training_table}\n\n"
        f"{eval_table}\n\n"
        f"{improvement_block}\n\n"
        f"Generated: {now}\n"
    )


# ── Roadmap patcher ────────────────────────────────────────────────────────────

def patch_roadmap(results: list[dict]) -> None:
    """Replace the pending pipeline-results placeholder line in roadmap.md."""
    if not ROADMAP_PATH.exists():
        print(f"  [WARN] roadmap.md not found at {ROADMAP_PATH}", file=sys.stderr)
        return

    text = ROADMAP_PATH.read_text(encoding="utf-8")

    # Find the line containing the placeholder
    lines = text.splitlines(keepends=True)
    target_idx = None
    for i, line in enumerate(lines):
        if ROADMAP_PLACEHOLDER in line:
            target_idx = i
            break

    if target_idx is None:
        print(
            "  [INFO] Roadmap placeholder not found — skipping roadmap update.",
            file=sys.stderr,
        )
        return

    # Build replacement text
    if len(results) >= 2:
        baseline  = results[0]
        best      = max(results, key=lambda r: r.get("success_rate") or 0.0)
        bc_sr     = baseline.get("success_rate") or 0.0
        best_sr   = best.get("success_rate") or 0.0
        best_lbl  = best.get("label", "DAgger-final")
        if bc_sr > 0:
            mult_str = f"{best_sr / bc_sr:.1f}×"
        else:
            mult_str = "N/A (BC=0%)"
        replacement = (
            f"- [x] **1000-demo + DAgger pipeline results**: "
            f"BC closed-loop {bc_sr * 100:.0f}%, "
            f"{best_lbl} {best_sr * 100:.0f}% "
            f"({mult_str} improvement); final loss {baseline.get('train_loss', '—')}"
        )
    else:
        r  = results[0]
        sr = r.get("success_rate") or 0.0
        replacement = (
            f"- [x] **1000-demo + DAgger pipeline results**: "
            f"closed-loop {sr * 100:.0f}%, loss {r.get('train_loss', '—')}"
        )

    lines[target_idx] = replacement + "\n"
    ROADMAP_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"  [OK] roadmap.md updated at line {target_idx + 1}")


# ── Watch loop ─────────────────────────────────────────────────────────────────

def watch(
    watch_dirs: list[Path],
    labels: list[str],
    output: Path,
    poll_interval: int,
    timeout: int,
    once: bool,
) -> list[dict]:
    """
    Poll *watch_dirs* until all have summary.json (or timeout / once).
    Returns list of loaded result dicts (with label injected).
    """
    deadline = time.monotonic() + timeout
    iteration = 0

    while True:
        results: list[dict | None] = []
        pending: list[str] = []

        for watch_dir, label in zip(watch_dirs, labels):
            summary = load_summary(watch_dir)
            if summary is None:
                results.append(None)
                pending.append(label)
            else:
                summary.setdefault("label", label)
                results.append(summary)

        ready_count = sum(1 for r in results if r is not None)
        total_count = len(watch_dirs)

        if iteration == 0 or not once:
            ts = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{ts}] {ready_count}/{total_count} dirs ready"
                + (f"  — waiting for: {', '.join(pending)}" if pending else "")
            )

        # All ready
        if ready_count == total_count:
            return [r for r in results if r is not None]

        if once:
            # Return whatever is available
            available = [r for r in results if r is not None]
            if not available:
                print(
                    "[INFO] --once mode: no results available yet.",
                    file=sys.stderr,
                )
                sys.exit(0)
            return available

        # Timeout check
        if time.monotonic() >= deadline:
            print(
                f"[TIMEOUT] Waited {timeout}s — only {ready_count}/{total_count} dirs ready.",
                file=sys.stderr,
            )
            available = [r for r in results if r is not None]
            return available

        time.sleep(poll_interval)
        iteration += 1


# ── Arg parsing ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Monitor OCI eval output dirs for summary.json; "
            "generate markdown pipeline report when all complete."
        )
    )
    p.add_argument(
        "--watch",
        nargs="+",
        metavar="DIR",
        default=[],
        help="Directories to poll for summary.json",
    )
    p.add_argument(
        "--labels",
        nargs="+",
        metavar="LABEL",
        default=[],
        help="Human-readable label for each --watch dir (same order)",
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help=f"Output markdown path (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        metavar="SECS",
        help=f"Seconds between status checks (default: {DEFAULT_POLL_INTERVAL})",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        metavar="SECS",
        help=f"Give up after N seconds (default: {DEFAULT_TIMEOUT})",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit (no polling loop)",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Create fake summary.json files in /tmp/mock_eval_<label>/ "
            "and run the watcher against them"
        ),
    )
    return p.parse_args()


# ── Mock helpers ───────────────────────────────────────────────────────────────

def setup_mock() -> tuple[list[Path], list[str]]:
    """Write mock summary.json files and return (watch_dirs, labels)."""
    watch_dirs: list[Path] = []
    labels: list[str] = []
    for label, data in MOCK_SUMMARIES.items():
        slug = label.replace(" ", "_").replace("/", "-")
        mock_dir = Path(f"/tmp/mock_eval_{slug}")
        mock_dir.mkdir(parents=True, exist_ok=True)
        summary_path = mock_dir / "summary.json"
        summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  [mock] wrote {summary_path}")
        watch_dirs.append(mock_dir)
        labels.append(label)
    return watch_dirs, labels


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.mock:
        print("Mock mode — creating fake summary.json files.")
        watch_dirs, labels = setup_mock()
        # Override to --once (data is already there)
        once = True
    else:
        if not args.watch:
            print(
                "Error: provide --watch or use --mock.",
                file=sys.stderr,
            )
            sys.exit(1)
        watch_dirs = [Path(d) for d in args.watch]
        # Pad labels
        labels = list(args.labels)
        for i in range(len(labels), len(watch_dirs)):
            labels.append(f"run-{i}")
        once = args.once

    output = Path(args.output)

    print(f"\nEval Watcher — OCI Robot Cloud")
    print(f"{'─' * 44}")
    print(f"  Watching : {len(watch_dirs)} dir(s)")
    print(f"  Interval : {args.poll_interval}s")
    print(f"  Timeout  : {args.timeout}s")
    print(f"  Output   : {output}")
    print()

    results = watch(
        watch_dirs=watch_dirs,
        labels=labels,
        output=output,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        once=once,
    )

    if not results:
        print("No results collected — exiting.", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.now().strftime("%Y-%m-%d")
    md = build_markdown(results, date_str)

    # Write markdown file
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md, encoding="utf-8")

    # Print to stdout
    print()
    print(md)
    print(f"Report written to: {output.resolve()}")

    # Patch roadmap
    patch_roadmap(results)


if __name__ == "__main__":
    main()
