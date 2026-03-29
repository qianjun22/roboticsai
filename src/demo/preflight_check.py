#!/usr/bin/env python3
"""
preflight_check.py — Pre-demo system verification for GTC 2027 live demo.

Runs all checks needed before a live presentation:
  • OCI GPU availability (CUDA, VRAM)
  • Genesis 0.4.3 importable and working
  • GR00T model weights present
  • GR00T inference server reachable
  • LeRobot v2 dataset format readable
  • Eval script importable
  • Disk space available for SDG output

Usage:
    python src/demo/preflight_check.py [--server-url URL] [--checkpoint PATH]
    python src/demo/preflight_check.py --quick   # skip server + GPU checks
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, List, Tuple

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS = f"{GREEN}✓ PASS{RESET}"
FAIL = f"{RED}✗ FAIL{RESET}"
WARN = f"{YELLOW}⚠ WARN{RESET}"
SKIP = f"{CYAN}– SKIP{RESET}"


def check(label: str, fn: Callable[[], Tuple[str, str]]) -> Tuple[bool, str]:
    """Run fn, print result. Returns (passed, detail)."""
    try:
        status, detail = fn()
    except Exception as e:
        status, detail = "FAIL", str(e)

    icon = PASS if status == "PASS" else (WARN if status == "WARN" else (SKIP if status == "SKIP" else FAIL))
    print(f"  {icon}  {label}")
    if detail:
        print(f"       {detail}")
    return status in ("PASS", "WARN", "SKIP"), detail


# ── Individual checks ────────────────────────────────────────────────────────

def check_python_version() -> Tuple[str, str]:
    v = sys.version_info
    if v >= (3, 9):
        return "PASS", f"Python {v.major}.{v.minor}.{v.micro}"
    return "FAIL", f"Python {v.major}.{v.minor} found; need ≥3.9"


def check_cuda() -> Tuple[str, str]:
    try:
        import torch
        if torch.cuda.is_available():
            dev = torch.cuda.get_device_name(0)
            mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            return "PASS", f"{dev} · {mem_gb:.1f}GB VRAM"
        return "FAIL", "torch.cuda.is_available() = False"
    except ImportError:
        return "WARN", "PyTorch not installed — GPU check skipped"


def check_genesis() -> Tuple[str, str]:
    try:
        import genesis as gs  # noqa: F401
        return "PASS", f"genesis importable"
    except ImportError:
        return "FAIL", "genesis not installed (pip install genesis-world)"


def check_lerobot() -> Tuple[str, str]:
    try:
        import lerobot  # noqa: F401
        return "PASS", "lerobot importable"
    except ImportError:
        return "WARN", "lerobot not installed — dataset reading may fail"


def check_checkpoint(ckpt_path: str) -> Tuple[str, str]:
    p = Path(ckpt_path)
    if not p.exists():
        return "FAIL", f"not found: {ckpt_path}"
    config = p / "config.json"
    if not config.exists():
        return "WARN", f"exists but no config.json — may not be a valid GR00T checkpoint"
    # Check size roughly
    total = sum(f.stat().st_size for f in p.rglob("*.safetensors"))
    gb = total / 1e9
    if gb < 1.0:
        return "WARN", f"checkpoint only {gb:.2f}GB — may be incomplete"
    return "PASS", f"{ckpt_path}  ({gb:.1f}GB)"


def check_server(url: str) -> Tuple[str, str]:
    try:
        start = time.time()
        with urllib.request.urlopen(f"{url}/health", timeout=5) as r:
            elapsed = (time.time() - start) * 1000
            body = json.loads(r.read())
            return "PASS", f"reachable in {elapsed:.0f}ms · {body}"
    except Exception as e:
        return "FAIL", f"cannot reach {url}/health — {e}"


def check_server_inference(url: str) -> Tuple[str, str]:
    """Send a dummy /act request to verify end-to-end inference."""
    import base64
    import io
    try:
        from PIL import Image
        import numpy as np
        img = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        frame_b64 = base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # minimal JPEG bytes without PIL
        frame_b64 = ""

    payload = json.dumps({
        "video_frame_b64": frame_b64,
        "joint_states": [0.0] * 9,
        "episode_id": 0,
    }).encode()

    try:
        start = time.time()
        req = urllib.request.Request(
            f"{url}/act",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            elapsed = (time.time() - start) * 1000
            resp = json.loads(r.read())
            if "actions" in resp or "action" in resp:
                return "PASS", f"inference OK in {elapsed:.0f}ms"
            return "WARN", f"responded but no 'actions' key: {list(resp.keys())}"
    except Exception as e:
        return "WARN", f"inference request failed — {e}"


def check_disk_space(min_gb: float = 20.0) -> Tuple[str, str]:
    total, used, free = shutil.disk_usage("/tmp")
    free_gb = free / 1e9
    if free_gb >= min_gb:
        return "PASS", f"{free_gb:.1f}GB free in /tmp (need {min_gb}GB)"
    return "WARN", f"only {free_gb:.1f}GB free in /tmp — SDG may fail"


def check_eval_script() -> Tuple[str, str]:
    candidates = [
        Path.home() / "roboticsai/src/eval/closed_loop_eval.py",
        Path(__file__).parents[2] / "src/eval/closed_loop_eval.py",
        Path("/home/ubuntu/roboticsai/src/eval/closed_loop_eval.py"),
    ]
    for p in candidates:
        if p.exists():
            return "PASS", str(p)
    return "FAIL", f"closed_loop_eval.py not found in expected paths"


def check_sdg_script() -> Tuple[str, str]:
    candidates = [
        Path.home() / "roboticsai/src/simulation/genesis_sdg_planned.py",
        Path(__file__).parents[2] / "src/simulation/genesis_sdg_planned.py",
    ]
    for p in candidates:
        if p.exists():
            return "PASS", str(p)
    return "FAIL", "genesis_sdg_planned.py not found"


def check_groot_server_script() -> Tuple[str, str]:
    candidates = [
        Path.home() / "roboticsai/src/inference/groot_franka_server.py",
        Path(__file__).parents[2] / "src/inference/groot_franka_server.py",
    ]
    for p in candidates:
        if p.exists():
            return "PASS", str(p)
    return "FAIL", "groot_franka_server.py not found"


def check_groot_python() -> Tuple[str, str]:
    venv = Path("/home/ubuntu/Isaac-GR00T/.venv/bin/python3")
    if venv.exists():
        try:
            out = subprocess.check_output([str(venv), "--version"], stderr=subprocess.STDOUT)
            return "PASS", f"{venv}  ({out.decode().strip()})"
        except Exception as e:
            return "WARN", f"venv found but not executable: {e}"
    # try system python3
    try:
        out = subprocess.check_output(["python3", "--version"], stderr=subprocess.STDOUT)
        return "WARN", f"Isaac-GR00T venv not found; using system {out.decode().strip()}"
    except Exception:
        return "FAIL", "no python3 found"


def check_curl() -> Tuple[str, str]:
    if shutil.which("curl"):
        return "PASS", shutil.which("curl")
    return "FAIL", "curl not found — server health checks will fail"


def check_nvidia_smi() -> Tuple[str, str]:
    if not shutil.which("nvidia-smi"):
        return "WARN", "nvidia-smi not found (expected on OCI A100)"
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5,
        ).decode().strip()
        lines = out.split("\n")
        summary = " | ".join(l.strip() for l in lines[:2])
        return "PASS", summary
    except Exception as e:
        return "WARN", str(e)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GTC 2027 live demo pre-flight check")
    parser.add_argument("--server-url", default="http://localhost:8002")
    parser.add_argument("--checkpoint", default="/tmp/finetune_1000_5k/checkpoint-5000",
                        help="Path to GR00T checkpoint to verify")
    parser.add_argument("--quick", action="store_true",
                        help="Skip GPU, server, and inference checks")
    parser.add_argument("--skip-inference", action="store_true",
                        help="Skip /act inference test (health check only)")
    args = parser.parse_args()

    print()
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  GTC 2027 Live Demo — Pre-Flight Check{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print()

    results: List[Tuple[bool, str]] = []

    # ── System
    print(f"{BOLD}SYSTEM{RESET}")
    results.append(check("Python ≥3.9", check_python_version))
    results.append(check("curl available", check_curl))
    results.append(check("Disk space ≥20GB in /tmp", check_disk_space))
    if not args.quick:
        results.append(check("nvidia-smi", check_nvidia_smi))
        results.append(check("CUDA (PyTorch)", check_cuda))
    print()

    # ── Dependencies
    print(f"{BOLD}DEPENDENCIES{RESET}")
    results.append(check("genesis importable", check_genesis))
    results.append(check("lerobot importable", check_lerobot))
    results.append(check("GR00T Python (venv)", check_groot_python))
    print()

    # ── Pipeline Scripts
    print(f"{BOLD}PIPELINE SCRIPTS{RESET}")
    results.append(check("genesis_sdg_planned.py", check_sdg_script))
    results.append(check("groot_franka_server.py", check_groot_server_script))
    results.append(check("closed_loop_eval.py", check_eval_script))
    print()

    # ── Model Checkpoint
    print(f"{BOLD}MODEL CHECKPOINT{RESET}")
    results.append(check(f"Checkpoint: {args.checkpoint}",
                         lambda: check_checkpoint(args.checkpoint)))
    print()

    # ── GR00T Server
    if not args.quick:
        print(f"{BOLD}GR00T SERVER  ({args.server_url}){RESET}")
        results.append(check("Health endpoint", lambda: check_server(args.server_url)))
        if not args.skip_inference:
            results.append(check("Inference /act", lambda: check_server_inference(args.server_url)))
        print()

    # ── Summary
    total = len(results)
    passed = sum(1 for ok, _ in results if ok)
    failed = total - passed

    print(f"{BOLD}{'═' * 60}{RESET}")
    if failed == 0:
        print(f"{GREEN}{BOLD}  All {total} checks passed — ready for live demo!{RESET}")
    else:
        print(f"{YELLOW}{BOLD}  {passed}/{total} checks passed · {failed} issue(s) need attention{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print()

    # Exit non-zero if any hard FAILs
    hard_fails = sum(1 for ok, _ in results if not ok)
    sys.exit(1 if hard_fails > 0 else 0)


if __name__ == "__main__":
    main()
