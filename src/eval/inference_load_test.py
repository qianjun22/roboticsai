#!/usr/bin/env python3
"""
inference_load_test.py — Concurrent request load test for the GR00T inference server.

Sends N requests at a given concurrency level, records per-request latency,
and reports p50/p95/p99 percentiles, throughput, and error rate.

Usage:
    # Hit a running server (default: localhost:8002):
    python src/eval/inference_load_test.py \\
        --server-url http://localhost:8002 \\
        --num-requests 100 \\
        --concurrency 4 \\
        --output /tmp/load_test.json

    # Mock mode (no server needed):
    python src/eval/inference_load_test.py --mock
"""

import argparse
import base64
import io
import json
import random
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import numpy as np

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_SERVER_URL   = "http://localhost:8002"
DEFAULT_NUM_REQUESTS = 100
DEFAULT_CONCURRENCY  = 4
DEFAULT_OUTPUT       = "/tmp/load_test.json"
HISTOGRAM_BUCKETS    = 10

# Joint angle ranges for a 7-DOF Franka + 2-DOF gripper
JOINT_LOWER = np.array([-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973, 0.0, 0.0])
JOINT_UPPER = np.array([ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973, 0.08, 0.08])

# Mock latency distribution (mean=230ms, std=40ms, clipped at [80, 600])
MOCK_LATENCY_MEAN = 0.230
MOCK_LATENCY_STD  = 0.040
MOCK_ERROR_RATE   = 0.02   # 2% simulated errors


# ── Payload generation ─────────────────────────────────────────────────────────

def make_jpeg_b64(width: int = 640, height: int = 480) -> str:
    """Return a random RGB frame encoded as base64 JPEG."""
    try:
        from PIL import Image
        arr = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # Pillow not available — encode a minimal valid JPEG-like blob
        raw = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8).tobytes()
        return base64.b64encode(raw).decode("ascii")


def make_payload(episode_id: int) -> dict:
    """Generate a synthetic observation payload matching the GR00T /act schema."""
    joint_states = (
        JOINT_LOWER + np.random.rand(9) * (JOINT_UPPER - JOINT_LOWER)
    ).tolist()
    return {
        "video_frame": make_jpeg_b64(),
        "joint_states": joint_states,
        "episode_id": episode_id,
    }


# ── Single request ─────────────────────────────────────────────────────────────

def send_request(server_url: str, payload: dict) -> tuple[float, bool, str]:
    """
    POST payload to server_url/act.
    Returns (latency_seconds, success, error_message).
    """
    url = server_url.rstrip("/") + "/act"
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            _ = resp.read()
        latency = time.monotonic() - t0
        return latency, True, ""
    except urllib.error.HTTPError as exc:
        latency = time.monotonic() - t0
        return latency, False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        latency = time.monotonic() - t0
        return latency, False, str(exc)


# ── Worker thread ──────────────────────────────────────────────────────────────

class _WorkerResult:
    __slots__ = ("latency_ms", "success", "error")

    def __init__(self, latency_ms: float, success: bool, error: str) -> None:
        self.latency_ms = latency_ms
        self.success    = success
        self.error      = error


def _worker(
    server_url: str,
    payloads: list[dict],
    results: list,
    mock: bool,
    rng: random.Random,
) -> None:
    for payload in payloads:
        if mock:
            # Simulate latency — occasionally inject an error
            lat = max(0.050, rng.gauss(MOCK_LATENCY_MEAN, MOCK_LATENCY_STD))
            time.sleep(lat)
            success = rng.random() > MOCK_ERROR_RATE
            error   = "" if success else "mock_error"
            results.append(_WorkerResult(lat * 1000.0, success, error))
        else:
            lat, success, error = send_request(server_url, payload)
            results.append(_WorkerResult(lat * 1000.0, success, error))


# ── Stats computation ──────────────────────────────────────────────────────────

def compute_stats(
    results: list[_WorkerResult],
    wall_seconds: float,
) -> dict:
    latencies = np.array([r.latency_ms for r in results], dtype=float)
    errors    = sum(1 for r in results if not r.success)
    total     = len(results)

    def pct(arr: np.ndarray, q: float) -> float:
        return float(np.percentile(arr, q)) if len(arr) > 0 else 0.0

    # Latency histogram
    if len(latencies) > 0:
        hist_min = float(latencies.min())
        hist_max = float(latencies.max())
        counts, edges = np.histogram(latencies, bins=HISTOGRAM_BUCKETS)
        histogram = [
            {
                "bucket_ms": f"{edges[i]:.0f}–{edges[i+1]:.0f}",
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]
    else:
        hist_min = hist_max = 0.0
        histogram = []

    return {
        "total_requests":    total,
        "successful":        total - errors,
        "failed":            errors,
        "error_rate_pct":    round(errors / total * 100, 2) if total > 0 else 0.0,
        "wall_seconds":      round(wall_seconds, 3),
        "requests_per_sec":  round(total / wall_seconds, 2) if wall_seconds > 0 else 0.0,
        "p50_latency_ms":    round(pct(latencies, 50), 1),
        "p95_latency_ms":    round(pct(latencies, 95), 1),
        "p99_latency_ms":    round(pct(latencies, 99), 1),
        "min_latency_ms":    round(float(latencies.min()), 1) if len(latencies) else 0.0,
        "max_latency_ms":    round(float(latencies.max()), 1) if len(latencies) else 0.0,
        "mean_latency_ms":   round(float(latencies.mean()), 1) if len(latencies) else 0.0,
        "histogram":         histogram,
        "histogram_range_ms": {"min": round(hist_min, 1), "max": round(hist_max, 1)},
        "generated":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── Print table ────────────────────────────────────────────────────────────────

def print_table(stats: dict, server_url: str, concurrency: int, mock: bool) -> None:
    width = 45
    sep   = "─" * width
    tag   = " [MOCK]" if mock else ""

    print(f"\nLoad Test Results — GR00T Inference Server{tag}")
    print(sep)
    print(f"  Server:       {server_url}")
    print(f"  Requests:     {stats['total_requests']} total, {concurrency} concurrent")
    print(f"  Duration:     {stats['wall_seconds']:.1f}s")
    print(f"  Throughput:   {stats['requests_per_sec']:.1f} req/s")
    print(sep)
    print(f"  Latency P50:  {stats['p50_latency_ms']:.0f}ms")
    print(f"  Latency P95:  {stats['p95_latency_ms']:.0f}ms")
    print(f"  Latency P99:  {stats['p99_latency_ms']:.0f}ms")
    print(f"  Latency max:  {stats['max_latency_ms']:.0f}ms")
    print(sep)
    print(f"  Successful:   {stats['successful']}/{stats['total_requests']}")
    print(f"  Error rate:   {stats['error_rate_pct']:.1f}%")
    print(sep)

    # Histogram
    if stats["histogram"]:
        print(f"\n  Latency distribution (ms):")
        max_count = max(b["count"] for b in stats["histogram"])
        bar_width  = 24
        for bucket in stats["histogram"]:
            count    = bucket["count"]
            bar_len  = int(count / max_count * bar_width) if max_count > 0 else 0
            bar      = "█" * bar_len
            label    = f"{bucket['bucket_ms']:>12}"
            print(f"    {label}  {bar:<{bar_width}} {count}")
    print()


# ── Arg parsing ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Load test the GR00T inference server under concurrent requests."
    )
    p.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        metavar="URL",
        help=f"Base URL of the inference server (default: {DEFAULT_SERVER_URL})",
    )
    p.add_argument(
        "--num-requests",
        type=int,
        default=DEFAULT_NUM_REQUESTS,
        metavar="N",
        help=f"Total requests to send (default: {DEFAULT_NUM_REQUESTS})",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        metavar="N",
        help=f"Number of concurrent worker threads (default: {DEFAULT_CONCURRENCY})",
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help=f"Output JSON path for aggregated stats (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for payload generation (default: 42)",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Simulate random latencies (mean=230ms, std=40ms) "
            "without hitting a real server"
        ),
    )
    return p.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    np.random.seed(args.seed)

    n       = args.num_requests
    c       = min(args.concurrency, n)
    server  = args.server_url
    output  = Path(args.output)

    print(f"\nGR00T Inference Load Test")
    print(f"{'─' * 44}")
    print(f"  Server     : {server}{' [MOCK]' if args.mock else ''}")
    print(f"  Requests   : {n}")
    print(f"  Concurrency: {c}")
    print(f"  Output     : {output}")
    print(f"  Generating {n} payloads ...", end="", flush=True)

    # Pre-generate all payloads
    payloads = [make_payload(i) for i in range(n)]
    print(" done.")

    # Split work across threads
    chunks: list[list[dict]] = [[] for _ in range(c)]
    for i, payload in enumerate(payloads):
        chunks[i % c].append(payload)

    all_results: list[list[_WorkerResult]] = [[] for _ in range(c)]
    threads: list[threading.Thread] = []
    rngs = [random.Random(args.seed + tid) for tid in range(c)]

    print(f"  Starting {c} worker thread(s) ...\n")
    t0 = time.monotonic()

    for tid in range(c):
        t = threading.Thread(
            target=_worker,
            args=(server, chunks[tid], all_results[tid], args.mock, rngs[tid]),
            daemon=True,
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    wall_seconds = time.monotonic() - t0

    # Flatten results
    flat_results: list[_WorkerResult] = []
    for res_list in all_results:
        flat_results.extend(res_list)

    stats = compute_stats(flat_results, wall_seconds)
    stats["config"] = {
        "server_url":    server,
        "num_requests":  n,
        "concurrency":   c,
        "mock":          args.mock,
        "seed":          args.seed,
    }

    # Write JSON
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    # Print table
    print_table(stats, server, c, args.mock)
    print(f"Results written to: {output.resolve()}")

    # Non-zero exit if error rate is high
    if stats["error_rate_pct"] > 10.0:
        print(
            f"  [WARN] Error rate {stats['error_rate_pct']:.1f}% exceeds 10% threshold.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
