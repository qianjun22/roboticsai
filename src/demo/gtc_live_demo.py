"""
GTC 2027 Live Demo Orchestrator
================================
Runs the full OCI Robot Cloud pipeline end-to-end during a 15-minute GTC presentation.
Prints timestamped audience-facing commentary at each step.

Usage:
    python src/demo/gtc_live_demo.py --demo-mode fast
    python src/demo/gtc_live_demo.py --demo-mode full --num-demos 100 --num-episodes 10
    python src/demo/gtc_live_demo.py --demo-mode eval-only --checkpoint /tmp/finetune_1000_5k/checkpoint-5000
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── ANSI colors ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[38;5;166m"   # OCI red-ish (256-color)
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
WHITE  = "\033[97m"

BORDER = "═" * 57


# ── Banner / formatting helpers ───────────────────────────────────────────────

def ts() -> str:
    """Return a short HH:MM:SS timestamp string."""
    t = time.localtime()
    return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"


def print_banner(step_num: int, total_steps: int, title: str, description: str) -> None:
    """Print a colored ASCII banner for the current pipeline step."""
    print()
    print(f"{RED}{BOLD}{BORDER}{RESET}")
    print(f"{RED}{BOLD}  STEP {step_num}/{total_steps} │ {title}{RESET}")
    print(f"{WHITE}  {description}{RESET}")
    print(f"{RED}{BOLD}{BORDER}{RESET}")
    print(f"{GRAY}  [{ts()}]{RESET}")
    print()


def print_info(msg: str) -> None:
    print(f"  {CYAN}▶{RESET}  {msg}")


def print_ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def print_warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def print_section(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RESET}")


# ── Core runner ───────────────────────────────────────────────────────────────

def run_step(cmd: list[str], label: str) -> tuple[int, float]:
    """
    Run *cmd* as a subprocess, streaming output live.
    Returns (exit_code, duration_seconds).
    """
    print_info(f"Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(f"    {GRAY}{line.rstrip()}{RESET}\n")
        sys.stdout.flush()
    proc.wait()
    duration = time.monotonic() - t0
    exit_code = proc.returncode
    if exit_code == 0:
        print_ok(f"{label} completed in {duration:.1f}s")
    else:
        print_warn(f"{label} exited with code {exit_code} (took {duration:.1f}s)")
    return exit_code, duration


# ── Server health check ───────────────────────────────────────────────────────

def wait_for_server(url: str, timeout: int = 30) -> bool:
    """
    Poll *url* (GET) until HTTP 200 is returned or *timeout* seconds elapse.
    Returns True if healthy, False on timeout.
    """
    health_url = url.rstrip("/") + "/health"
    deadline = time.monotonic() + timeout
    interval = 1.0
    print_info(f"Waiting for server at {health_url} (timeout {timeout}s)…")
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    print_ok("Server is healthy.")
                    return True
        except Exception:
            pass
        time.sleep(interval)
    print_warn(f"Server did not become healthy within {timeout}s.")
    return False


# ── Results display ───────────────────────────────────────────────────────────

def print_results_table(eval_summary_path: Path) -> dict:
    """Load eval summary JSON and print a clean results table. Returns the dict."""
    if not eval_summary_path.exists():
        print_warn(f"Summary not found: {eval_summary_path}")
        return {}
    with eval_summary_path.open() as f:
        data = json.load(f)

    sr = data.get("success_rate", 0.0)
    n  = data.get("num_episodes", 0)
    lat = data.get("avg_latency_ms", 0.0)
    cats: dict = data.get("failure_categories", {})

    col_w = 28
    print()
    print(f"{BOLD}{'─' * 50}{RESET}")
    print(f"{BOLD}{'METRIC':<{col_w}} VALUE{RESET}")
    print(f"{'─' * 50}")
    print(f"{'Success rate':<{col_w}} {GREEN}{sr * 100:.1f}%{RESET}")
    print(f"{'Episodes evaluated':<{col_w}} {n}")
    print(f"{'Avg inference latency':<{col_w}} {lat:.1f} ms")
    if cats:
        print(f"{'─' * 50}")
        print(f"{BOLD}{'OUTCOME':<{col_w}} COUNT{RESET}")
        for k, v in cats.items():
            print(f"  {k:<{col_w - 2}} {v}")
    print(f"{'─' * 50}")
    print()
    return data


# ── Cost estimator ────────────────────────────────────────────────────────────

def estimate_cost(num_demos: int, num_steps: int) -> None:
    """Print an OCI cost estimate for the fine-tuning run."""
    cost_per_10k = 0.0043          # $ / 10k training steps on OCI A100
    steps_cost   = (num_steps / 10_000) * cost_per_10k
    # Rough GPU-hour calc: ~2.35 it/s → 4.255k it/min at batch=32
    gpu_hours    = num_steps / (2.35 * 3600)
    hourly_rate  = 3.40            # OCI A100 on-demand $/hr approx
    gpu_cost     = gpu_hours * hourly_rate

    print_section("OCI Cost Estimate")
    print(f"  Training steps  : {num_steps:,}")
    print(f"  Demo episodes   : {num_demos:,}")
    print(f"  Cost @ $0.0043/10k steps : {GREEN}${steps_cost:.4f}{RESET}")
    print(f"  GPU time (~2.35 it/s)    : {gpu_hours * 60:.1f} min  ≈  ${gpu_cost:.2f}")
    print(f"  {BOLD}Note: AWS p4d equivalent would be ~9.6× more expensive{RESET}")
    print()


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GTC 2027 Live Demo — OCI Robot Cloud end-to-end pipeline"
    )
    p.add_argument(
        "--demo-mode",
        choices=["full", "sdg-only", "eval-only", "fast"],
        default="fast",
        help="Pipeline scope (default: fast — runs in ~3 min for live demos)",
    )
    p.add_argument(
        "--num-demos",
        type=int,
        default=100,
        help="SDG episodes to generate (fast mode uses 10)",
    )
    p.add_argument(
        "--num-episodes",
        type=int,
        default=10,
        help="Closed-loop eval episodes",
    )
    p.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Pre-existing checkpoint path — skips fine-tuning in live demo",
    )
    p.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:8002",
        help="GR00T inference server URL (default: http://localhost:8002)",
    )
    p.add_argument(
        "--eval-output-dir",
        type=str,
        default="/tmp/gtc_demo_eval",
        help="Directory for eval output (default: /tmp/gtc_demo_eval)",
    )
    return p.parse_args()


# ── Main orchestrator ─────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Resolve repo root relative to this script's location
    repo_root = Path(__file__).resolve().parents[2]
    src       = repo_root / "src"

    # Determine effective demo count for SDG
    sdg_demos = 10 if args.demo_mode == "fast" else args.num_demos
    # Fine-tune steps (fast = 500, full = 5000)
    ft_steps  = 500 if args.demo_mode == "fast" else 5000

    TOTAL_STEPS = 6
    t_global   = time.monotonic()
    step_times: dict[int, float] = {}
    server_proc: subprocess.Popen | None = None  # type: ignore[type-arg]

    # ─────────────────────────────────────────────────────────────────────────
    # GTC intro header
    # ─────────────────────────────────────────────────────────────────────────
    print()
    print(f"{RED}{BOLD}{'═' * 57}{RESET}")
    print(f"{RED}{BOLD}  OCI ROBOT CLOUD — GTC 2027 LIVE DEMO{RESET}")
    print(f"{WHITE}  From synthetic data to deployed policy in one command{RESET}")
    print(f"{RED}{BOLD}{'═' * 57}{RESET}")
    print(f"  Mode     : {BOLD}{args.demo_mode}{RESET}")
    print(f"  SDG demos: {sdg_demos}   |   FT steps: {ft_steps}")
    print(f"  Server   : {args.server_url}")
    if args.checkpoint:
        print(f"  Checkpoint: {args.checkpoint}")
    print()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — SYNTHETIC DATA GENERATION
    # ─────────────────────────────────────────────────────────────────────────
    if args.demo_mode not in ("eval-only",):
        print_banner(
            1, TOTAL_STEPS,
            "SYNTHETIC DATA",
            f"Generating {sdg_demos} motion-planned pick-and-lift demos with Genesis…",
        )
        sdg_script = src / "simulation" / "genesis_sdg_planned.py"
        sdg_out    = "/tmp/gtc_demo_sdg"
        cmd = [
            sys.executable, str(sdg_script),
            "--num-demos", str(sdg_demos),
            "--output-dir", sdg_out,
        ]
        rc, dur = run_step(cmd, "SDG")
        step_times[1] = dur
        if rc != 0:
            print_warn("SDG step failed — continuing to show eval with pre-existing data.")
    else:
        print_info("Skipping SDG step (eval-only mode).")
        step_times[1] = 0.0

    if args.demo_mode == "sdg-only":
        print_ok("SDG-only mode complete.")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — CONVERT TO LEROBOT FORMAT
    # ─────────────────────────────────────────────────────────────────────────
    if args.demo_mode not in ("eval-only",):
        print_banner(
            2, TOTAL_STEPS,
            "CONVERT",
            "Converting Genesis HDF5 demos → LeRobot v2 format for GR00T training…",
        )
        convert_script = src / "training" / "genesis_to_lerobot.py"
        lerobot_out    = "/tmp/gtc_demo_lerobot"
        cmd = [
            sys.executable, str(convert_script),
            "--input-dir", "/tmp/gtc_demo_sdg",
            "--output-dir", lerobot_out,
        ]
        rc, dur = run_step(cmd, "Convert")
        step_times[2] = dur
    else:
        print_info("Skipping convert step (eval-only mode).")
        step_times[2] = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — FINE-TUNE
    # ─────────────────────────────────────────────────────────────────────────
    print_banner(
        3, TOTAL_STEPS,
        "FINE-TUNE",
        "GR00T N1.6-3B fine-tuning on OCI A100 (Isaac-GR00T venv)…",
    )
    if args.checkpoint:
        print_ok(f"Using pre-existing checkpoint: {args.checkpoint}")
        print_info(
            "In a full run, execute:"
        )
        print(f"    {GRAY}python launch_finetune.py \\")
        print(f"        --dataset-path /tmp/gtc_demo_lerobot \\")
        print(f"        --output-dir /tmp/gtc_finetune \\")
        print(f"        --num-steps {ft_steps}{RESET}")
        print()
        estimate_cost(sdg_demos, ft_steps)
        step_times[3] = 0.0
    else:
        print_warn(
            "No --checkpoint provided and live fine-tuning is skipped in demo mode."
        )
        print_info(
            "To run fine-tuning outside the demo:\n"
            f"    python launch_finetune.py \\\n"
            f"        --dataset-path /tmp/gtc_demo_lerobot \\\n"
            f"        --output-dir /tmp/gtc_finetune \\\n"
            f"        --num-steps {ft_steps}"
        )
        estimate_cost(sdg_demos, ft_steps)
        step_times[3] = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — SERVE
    # ─────────────────────────────────────────────────────────────────────────
    print_banner(
        4, TOTAL_STEPS,
        "SERVE",
        f"GR00T N1.6-3B inference server starting on {args.server_url}…",
    )
    server_script = src / "inference" / "groot_franka_server.py"
    server_cmd    = [sys.executable, str(server_script)]
    if args.checkpoint:
        server_cmd += ["--checkpoint", args.checkpoint]

    t_serve = time.monotonic()
    print_info(f"Launching server: {' '.join(server_cmd)}")
    server_proc = subprocess.Popen(
        server_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    healthy = wait_for_server(args.server_url, timeout=30)
    step_times[4] = time.monotonic() - t_serve

    if not healthy:
        print_warn(
            "Server health check timed out. Proceeding anyway — "
            "the server may still be loading weights."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — EVALUATE
    # ─────────────────────────────────────────────────────────────────────────
    print_banner(
        5, TOTAL_STEPS,
        "EVALUATE",
        f"Closed-loop eval — {args.num_episodes} episodes — Genesis + GR00T server…",
    )
    eval_script = src / "eval" / "closed_loop_eval.py"
    eval_out    = Path(args.eval_output_dir)
    eval_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(eval_script),
        "--num-episodes", str(args.num_episodes),
        "--server-url",   args.server_url,
        "--output-dir",   str(eval_out),
    ]
    rc_eval, dur_eval = run_step(cmd, "Closed-loop eval")
    step_times[5] = dur_eval

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6 — RESULTS
    # ─────────────────────────────────────────────────────────────────────────
    print_banner(
        6, TOTAL_STEPS,
        "RESULTS",
        "Parsing eval summary and displaying final metrics…",
    )
    summary_path = eval_out / "summary.json"
    eval_data    = print_results_table(summary_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Final summary
    # ─────────────────────────────────────────────────────────────────────────
    total_elapsed = time.monotonic() - t_global

    print()
    print(f"{RED}{BOLD}{'═' * 57}{RESET}")
    print(f"{GREEN}{BOLD}  Pipeline complete!{RESET}")
    print(f"{RED}{BOLD}{'═' * 57}{RESET}")
    print(f"  Total elapsed : {BOLD}{total_elapsed:.1f}s  ({total_elapsed / 60:.1f} min){RESET}")
    print()
    print(f"  {'Step':<20} {'Duration':>10}")
    print(f"  {'─' * 32}")
    labels = {
        1: "1 · Synthetic data",
        2: "2 · Convert",
        3: "3 · Fine-tune",
        4: "4 · Serve",
        5: "5 · Evaluate",
    }
    for k, lbl in labels.items():
        d = step_times.get(k, 0.0)
        skipped = "" if d > 0 else "  (skipped)"
        print(f"  {lbl:<20} {d:>9.1f}s{skipped}")
    print()

    if eval_data:
        sr = eval_data.get("success_rate", 0.0)
        print(
            f"  {BOLD}Closed-loop success rate: "
            f"{GREEN}{sr * 100:.1f}%{RESET}"
        )
    print()
    print(f"  {GRAY}OCI Robot Cloud — oracle.com/cloud/robotics{RESET}")
    print(f"{RED}{BOLD}{'═' * 57}{RESET}")
    print()

    # Clean up background server
    if server_proc is not None:
        server_proc.terminate()


if __name__ == "__main__":
    main()
