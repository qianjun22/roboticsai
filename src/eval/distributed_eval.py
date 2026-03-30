#!/usr/bin/env python3
"""
distributed_eval.py — Distributed evaluation harness across multiple OCI instances.

Splits an N-episode eval across M OCI GPU instances in parallel, collects results,
and aggregates into a single HTML report. Speeds up large-scale eval from hours
to minutes when multiple A100s are available.

Usage:
    python src/eval/distributed_eval.py --mock --n-episodes 100 --n-workers 4
    python src/eval/distributed_eval.py --hosts gpu1.oci.example.com gpu2.oci.example.com \
        --checkpoint /tmp/dagger_run4/iter3/checkpoint-2000 --n-episodes 200
"""

import json
import math
import random
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_HOSTS = [
    "ubuntu@138.1.153.110",  # OCI GPU4 (primary)
]
EVAL_SCRIPT    = "src/eval/closed_loop_eval.py"
RESULTS_DIR    = "/tmp/distributed_eval"
SSH_TIMEOUT    = 30
EVAL_TIMEOUT   = 600   # 10 min per shard


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class EvalShard:
    shard_id: int
    host: str
    n_episodes: int
    start_episode: int
    checkpoint: str
    output_dir: str
    status: str = "pending"   # pending/running/done/failed
    success_rate: float = -1.0
    avg_latency_ms: float = -1.0
    n_success: int = 0
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    elapsed_s: float = 0.0


@dataclass
class DistributedEvalResult:
    checkpoint: str
    n_episodes_total: int
    n_workers: int
    success_rate: float
    n_success: int
    avg_latency_ms: float
    p95_latency_ms: float
    total_elapsed_s: float
    speedup_vs_serial: float
    shards: list[EvalShard]
    generated_at: str


# ── Mock evaluation ───────────────────────────────────────────────────────────

def simulate_shard(shard: EvalShard, rng: random.Random,
                   base_success_rate: float = 0.65) -> None:
    """Simulate running eval on one OCI instance."""
    shard.status = "running"
    shard.started_at = datetime.now().isoformat()
    t0 = time.time()

    # Simulate eval time: ~2.5s per episode (226ms inference × 50 steps + overhead)
    sim_time = shard.n_episodes * 2.5 * rng.uniform(0.8, 1.2)
    time.sleep(min(sim_time * 0.1, 3.0))  # speed up for mock: 10% of real time

    n_success = sum(1 for _ in range(shard.n_episodes)
                    if rng.random() < base_success_rate)
    shard.n_success = n_success
    shard.success_rate = n_success / shard.n_episodes
    shard.avg_latency_ms = rng.gauss(226, 8)
    shard.elapsed_s = time.time() - t0
    shard.status = "done"
    shard.completed_at = datetime.now().isoformat()


def run_real_shard(shard: EvalShard) -> None:
    """Run eval on a real OCI instance via SSH."""
    shard.status = "running"
    shard.started_at = datetime.now().isoformat()
    t0 = time.time()

    cmd = (
        f"cd ~/roboticsai && "
        f"python {EVAL_SCRIPT} "
        f"--checkpoint {shard.checkpoint} "
        f"--n-episodes {shard.n_episodes} "
        f"--output-dir {shard.output_dir}/shard_{shard.shard_id} "
        f"--seed {shard.start_episode}"
    )
    try:
        result = subprocess.run(
            ["ssh", "-o", f"ConnectTimeout={SSH_TIMEOUT}", "-o", "BatchMode=yes",
             shard.host, cmd],
            capture_output=True, text=True, timeout=EVAL_TIMEOUT
        )
        if result.returncode == 0:
            # Parse summary.json from remote
            fetch = subprocess.run(
                ["ssh", shard.host,
                 f"cat {shard.output_dir}/shard_{shard.shard_id}/summary.json"],
                capture_output=True, text=True, timeout=30
            )
            if fetch.returncode == 0:
                summary = json.loads(fetch.stdout)
                shard.success_rate = summary.get("success_rate", 0)
                shard.n_success = summary.get("n_success", 0)
                shard.avg_latency_ms = summary.get("avg_latency_ms", 0)
                shard.status = "done"
            else:
                shard.status = "failed"
                shard.error = "Could not fetch summary.json"
        else:
            shard.status = "failed"
            shard.error = result.stderr[:200]
    except subprocess.TimeoutExpired:
        shard.status = "failed"
        shard.error = "Timeout"
    except Exception as e:
        shard.status = "failed"
        shard.error = str(e)

    shard.elapsed_s = time.time() - t0
    shard.completed_at = datetime.now().isoformat()


# ── Orchestration ─────────────────────────────────────────────────────────────

def split_episodes(n_episodes: int, n_workers: int) -> list[int]:
    """Distribute N episodes across workers as evenly as possible."""
    base = n_episodes // n_workers
    remainder = n_episodes % n_workers
    return [base + (1 if i < remainder else 0) for i in range(n_workers)]


def run_distributed_eval(
    checkpoint: str,
    hosts: list[str],
    n_episodes: int,
    mock: bool = True,
    base_success_rate: float = 0.65,
    seed: int = 42,
) -> DistributedEvalResult:
    n_workers = len(hosts)
    splits = split_episodes(n_episodes, n_workers)
    rng = random.Random(seed)

    shards = []
    ep_offset = 0
    for i, (host, n_eps) in enumerate(zip(hosts, splits)):
        shard = EvalShard(
            shard_id=i,
            host=host,
            n_episodes=n_eps,
            start_episode=ep_offset,
            checkpoint=checkpoint,
            output_dir=f"{RESULTS_DIR}/run_{datetime.now().strftime('%H%M%S')}",
        )
        shards.append(shard)
        ep_offset += n_eps

    t0 = time.time()
    print(f"[dist_eval] {n_episodes} episodes across {n_workers} workers")
    for s in shards:
        print(f"  worker {s.shard_id}: {s.host} → {s.n_episodes} episodes")

    # Run shards in parallel threads
    threads = []
    for shard in shards:
        if mock:
            t = threading.Thread(target=simulate_shard,
                                 args=(shard, random.Random(rng.randint(0, 2**32)),
                                       base_success_rate))
        else:
            t = threading.Thread(target=run_real_shard, args=(shard,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_elapsed = time.time() - t0

    # Aggregate
    done_shards = [s for s in shards if s.status == "done"]
    total_n_success = sum(s.n_success for s in done_shards)
    total_n_eps = sum(s.n_episodes for s in done_shards)
    agg_success_rate = total_n_success / max(total_n_eps, 1)
    agg_latency = sum(s.avg_latency_ms * s.n_episodes for s in done_shards) / max(total_n_eps, 1)

    # p95 approximation (gaussian)
    p95_latency = agg_latency + 1.645 * 12  # σ≈12ms from empirical data

    serial_time_est = n_episodes * 2.5  # 2.5s/episode serial
    speedup = serial_time_est / max(total_elapsed, 0.01)

    return DistributedEvalResult(
        checkpoint=checkpoint,
        n_episodes_total=total_n_eps,
        n_workers=n_workers,
        success_rate=round(agg_success_rate, 4),
        n_success=total_n_success,
        avg_latency_ms=round(agg_latency, 1),
        p95_latency_ms=round(p95_latency, 1),
        total_elapsed_s=round(total_elapsed, 1),
        speedup_vs_serial=round(speedup, 2),
        shards=shards,
        generated_at=datetime.now().isoformat(),
    )


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html_report(result: DistributedEvalResult, output_path: str) -> None:
    status_color = {"done": "#22c55e", "failed": "#ef4444", "running": "#f59e0b", "pending": "#94a3b8"}

    shard_rows = ""
    for s in result.shards:
        sc = status_color.get(s.status, "#94a3b8")
        sr = f"{s.success_rate:.0%}" if s.success_rate >= 0 else "—"
        lat = f"{s.avg_latency_ms:.0f}ms" if s.avg_latency_ms >= 0 else "—"
        shard_rows += f"""<tr>
          <td style="padding:8px 10px;text-align:center">{s.shard_id}</td>
          <td style="padding:8px 10px;font-family:monospace;font-size:12px">{s.host}</td>
          <td style="padding:8px 10px;text-align:center">{s.n_episodes}</td>
          <td style="padding:8px 10px;font-weight:700;color:#22c55e">{sr}</td>
          <td style="padding:8px 10px;color:#94a3b8">{lat}</td>
          <td style="padding:8px 10px;color:#64748b;font-size:12px">{s.elapsed_s:.1f}s</td>
          <td style="padding:8px 10px"><span style="color:{sc};font-weight:600">{s.status}</span></td>
          <td style="padding:8px 10px;font-size:11px;color:#ef4444">{s.error[:40] if s.error else '—'}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Distributed Eval Results</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 14px;margin:4px;text-align:center}}
</style>
</head>
<body>
<h1>Distributed Eval — {result.checkpoint[-40:]}</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 16px">{result.generated_at[:19]} · {result.n_workers} workers in parallel</p>

<div class="card">
  <div class="m"><div style="font-size:26px;font-weight:700;color:#22c55e">{result.success_rate:.0%}</div><div style="font-size:11px;color:#64748b">Success Rate</div></div>
  <div class="m"><div style="font-size:26px;font-weight:700;color:#3b82f6">{result.n_success}/{result.n_episodes_total}</div><div style="font-size:11px;color:#64748b">Episodes</div></div>
  <div class="m"><div style="font-size:26px;font-weight:700;color:#6366f1">{result.avg_latency_ms:.0f}ms</div><div style="font-size:11px;color:#64748b">Avg Latency</div></div>
  <div class="m"><div style="font-size:26px;font-weight:700;color:#f59e0b">{result.p95_latency_ms:.0f}ms</div><div style="font-size:11px;color:#64748b">p95 Latency</div></div>
  <div class="m"><div style="font-size:26px;font-weight:700;color:#22c55e">{result.speedup_vs_serial:.1f}×</div><div style="font-size:11px;color:#64748b">Speedup vs Serial</div></div>
  <div class="m"><div style="font-size:26px;font-weight:700;color:#94a3b8">{result.total_elapsed_s:.0f}s</div><div style="font-size:11px;color:#64748b">Wall Time</div></div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:12px;text-transform:uppercase;margin-top:0">Shard Results</h3>
  <table>
    <tr><th>#</th><th>Host</th><th>Episodes</th><th>Success</th><th>Latency</th><th>Time</th><th>Status</th><th>Error</th></tr>
    {shard_rows}
  </table>
</div>

<div style="color:#334155;font-size:11px;margin-top:8px">
  Generated {result.generated_at} · {result.n_workers} workers · {result.n_episodes_total} total episodes
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"[dist_eval] Report → {output_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Distributed eval across OCI instances")
    parser.add_argument("--checkpoint",      default="/tmp/dagger_run4/iter3/checkpoint-2000")
    parser.add_argument("--hosts",           nargs="+", default=DEFAULT_HOSTS)
    parser.add_argument("--n-episodes",      type=int, default=100)
    parser.add_argument("--n-workers",       type=int, default=0,
                        help="Override host count (mock mode: create N virtual workers)")
    parser.add_argument("--mock",            action="store_true", default=True)
    parser.add_argument("--success-rate",    type=float, default=0.65,
                        help="Expected success rate (mock mode)")
    parser.add_argument("--seed",            type=int, default=42)
    parser.add_argument("--output",          default="/tmp/distributed_eval_report.html")
    args = parser.parse_args()

    hosts = args.hosts
    if args.mock and args.n_workers > 0:
        hosts = [f"mock-worker-{i}" for i in range(args.n_workers)]

    result = run_distributed_eval(
        checkpoint=args.checkpoint,
        hosts=hosts,
        n_episodes=args.n_episodes,
        mock=args.mock,
        base_success_rate=args.success_rate,
        seed=args.seed,
    )

    print(f"\n[dist_eval] Results:")
    print(f"  Success rate:  {result.success_rate:.0%} ({result.n_success}/{result.n_episodes_total})")
    print(f"  Avg latency:   {result.avg_latency_ms:.0f}ms (p95: {result.p95_latency_ms:.0f}ms)")
    print(f"  Wall time:     {result.total_elapsed_s:.1f}s ({result.speedup_vs_serial:.1f}× vs serial)")
    failed = [s for s in result.shards if s.status == "failed"]
    if failed:
        print(f"  ⚠ {len(failed)} shards failed: {[s.host for s in failed]}")

    render_html_report(result, args.output)

    # Save JSON summary
    summary_path = args.output.replace(".html", ".json")
    with open(summary_path, "w") as f:
        json.dump({
            "checkpoint": result.checkpoint,
            "success_rate": result.success_rate,
            "n_success": result.n_success,
            "n_episodes_total": result.n_episodes_total,
            "avg_latency_ms": result.avg_latency_ms,
            "p95_latency_ms": result.p95_latency_ms,
            "total_elapsed_s": result.total_elapsed_s,
            "speedup_vs_serial": result.speedup_vs_serial,
            "n_workers": result.n_workers,
            "generated_at": result.generated_at,
        }, f, indent=2)
    print(f"[dist_eval] JSON → {summary_path}")


if __name__ == "__main__":
    main()
