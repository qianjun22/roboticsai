#!/usr/bin/env python3
"""
oci_cost_monitor.py — OCI spending tracker against monthly budget.

Tracks GPU-hour consumption and cost across all training jobs. Sends
budget alerts when spending approaches limits. Generates monthly cost
breakdown report for Oracle finance approvals.

Usage:
    python src/infra/oci_cost_monitor.py --status
    python src/infra/oci_cost_monitor.py --report --month 2026-03
    python src/infra/oci_cost_monitor.py --add-job --job-id finetune_1000_5k --gpu-hours 0.68 --purpose "1000-demo BC fine-tune"
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH       = Path.home() / ".cache" / "roboticsai" / "oci_cost.db"
MONTHLY_BUDGET_USD = 50.00   # internal approval limit

# OCI A100 pricing (GPU4 instance)
GPU4_HOURLY_USD = 4.20
STORAGE_GB_MONTH = 0.025     # OCI Block Volume

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class CostEntry:
    entry_id: str
    job_id: str
    purpose: str
    gpu_hours: float
    storage_gb_hours: float
    cost_usd: float
    gpu_type: str       # "A100" / "A10" / etc.
    n_gpus: int
    started_at: str
    completed_at: str
    checkpoint_saved: str
    notes: str


@dataclass
class MonthlySummary:
    month: str          # YYYY-MM
    total_cost_usd: float
    budget_usd: float
    utilization_pct: float
    gpu_hours_total: float
    n_jobs: int
    largest_job: str
    largest_job_cost: float
    breakdown: list[dict]   # by purpose category


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS cost_entries (
            entry_id       TEXT PRIMARY KEY,
            job_id         TEXT,
            purpose        TEXT,
            gpu_hours      REAL,
            storage_gb_hrs REAL,
            cost_usd       REAL,
            gpu_type       TEXT,
            n_gpus         INTEGER,
            started_at     TEXT,
            completed_at   TEXT,
            checkpoint     TEXT,
            notes          TEXT
        );
        """)


@contextmanager
def get_db(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def add_entry(entry: CostEntry, db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (entry.entry_id, entry.job_id, entry.purpose, entry.gpu_hours,
             entry.storage_gb_hours, entry.cost_usd, entry.gpu_type, entry.n_gpus,
             entry.started_at, entry.completed_at, entry.checkpoint_saved, entry.notes)
        )


# ── Known job history ─────────────────────────────────────────────────────────

KNOWN_JOBS = [
    # (job_id, purpose, gpu_hours, n_gpus, date_approx, checkpoint, notes)
    ("sdg_500_genesis",         "SDG",            0.05, 1, "2026-03-15", "",                               "500 eps, 38.5fps Genesis"),
    ("finetune_500_5k",         "BC fine-tune",   0.59, 1, "2026-03-17", "/tmp/finetune_500_5k/checkpoint-5000", "500-demo baseline"),
    ("sdg_1000_genesis",        "SDG",            0.09, 1, "2026-03-20", "",                               "1000 eps, IK motion-planned"),
    ("finetune_1000_5k",        "BC fine-tune",   0.59, 1, "2026-03-21", "/tmp/finetune_1000_5k/checkpoint-5000", "1000-demo BC, loss 0.099"),
    ("eval_500_demo",           "Eval",           0.06, 1, "2026-03-17", "",                               "20-ep closed-loop eval"),
    ("eval_1000_demo",          "Eval",           0.06, 1, "2026-03-22", "",                               "20-ep eval: 5% success"),
    ("dagger_run3",             "DAgger",         0.28, 1, "2026-03-23", "/tmp/dagger_run3/checkpoint",    "beta=0.5, 3 iters × 20 eps"),
    ("dagger_run4_iter1",       "DAgger",         0.12, 1, "2026-03-24", "/tmp/dagger_run4/iter1/",       "iter1, 40 eps collected"),
    ("dagger_run4_iter2",       "DAgger",         0.12, 1, "2026-03-25", "/tmp/dagger_run4/iter2/",       "iter2, expert int 17.4/ep"),
    ("dagger_run4_iter3",       "DAgger",         0.14, 1, "2026-03-25", "/tmp/dagger_run4/iter3/checkpoint-2000", "iter3, 65% CL success"),
    ("dagger_run5_finetune",    "DAgger",         0.26, 1, "2026-03-27", "/tmp/dagger_run5/finetune_final/checkpoint-5000", "5000-step on 99 eps: 5%"),
    ("multi_gpu_ddp_test",      "Benchmark",      0.03, 4, "2026-03-22", "",                               "4-GPU DDP scaling: 3.07×"),
    ("hpo_search",              "HPO",            0.24, 1, "2026-03-20", "",                               "20 trials Optuna TPE"),
    ("dagger_run6",             "DAgger",         0.62, 1, "2026-03-28", "/tmp/dagger_run6/iter4/checkpoint-3000", "beta=0.10, 4 iters × 30 eps"),
]


def seed_known_jobs(db_path: Path = DB_PATH) -> None:
    """Populate DB with all known OCI jobs."""
    import hashlib
    for jid, purpose, gpu_h, n_gpus, date, ckpt, notes in KNOWN_JOBS:
        cost = gpu_h * n_gpus * GPU4_HOURLY_USD
        entry_id = hashlib.md5(jid.encode()).hexdigest()[:12]
        started = f"{date}T09:00:00"
        completed = f"{date}T{9 + int(gpu_h * n_gpus):02d}:00:00"
        add_entry(CostEntry(
            entry_id=entry_id,
            job_id=jid,
            purpose=purpose,
            gpu_hours=gpu_h * n_gpus,
            storage_gb_hours=0.0,
            cost_usd=round(cost, 4),
            gpu_type="A100",
            n_gpus=n_gpus,
            started_at=started,
            completed_at=completed,
            checkpoint_saved=ckpt,
            notes=notes,
        ), db_path)


# ── Queries ───────────────────────────────────────────────────────────────────

def monthly_summary(month: str, db_path: Path = DB_PATH) -> MonthlySummary:
    """month = 'YYYY-MM'"""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cost_entries WHERE started_at LIKE ?",
            (f"{month}%",)
        ).fetchall()

    entries = [dict(r) for r in rows]
    total_cost = sum(e["cost_usd"] for e in entries)
    total_gpu_h = sum(e["gpu_hours"] for e in entries)

    # Breakdown by purpose
    by_purpose: dict[str, dict] = {}
    for e in entries:
        p = e["purpose"]
        if p not in by_purpose:
            by_purpose[p] = {"purpose": p, "n_jobs": 0, "gpu_hours": 0.0, "cost_usd": 0.0}
        by_purpose[p]["n_jobs"] += 1
        by_purpose[p]["gpu_hours"] += e["gpu_hours"]
        by_purpose[p]["cost_usd"] += e["cost_usd"]
    breakdown = sorted(by_purpose.values(), key=lambda x: -x["cost_usd"])

    largest = max(entries, key=lambda x: x["cost_usd"], default={"job_id": "—", "cost_usd": 0})

    return MonthlySummary(
        month=month,
        total_cost_usd=round(total_cost, 4),
        budget_usd=MONTHLY_BUDGET_USD,
        utilization_pct=round(total_cost / MONTHLY_BUDGET_USD * 100, 1),
        gpu_hours_total=round(total_gpu_h, 2),
        n_jobs=len(entries),
        largest_job=largest["job_id"],
        largest_job_cost=largest["cost_usd"],
        breakdown=breakdown,
    )


def ytd_total(db_path: Path = DB_PATH) -> float:
    year = datetime.now().strftime("%Y")
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT SUM(cost_usd) as total FROM cost_entries WHERE started_at LIKE ?",
            (f"{year}%",)
        ).fetchone()
    return round(row["total"] or 0.0, 4)


# ── CLI ────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"


def cmd_status(db_path: Path) -> None:
    month = datetime.now().strftime("%Y-%m")
    summary = monthly_summary(month, db_path)
    ytd = ytd_total(db_path)

    bar_filled = int(summary.utilization_pct / 100 * 30)
    bar_color = GREEN if summary.utilization_pct < 60 else YELLOW if summary.utilization_pct < 85 else RED
    bar = f"{bar_color}{'█' * bar_filled}{'░' * (30 - bar_filled)}{RESET}"

    print(f"\n{BOLD}OCI Cost Monitor — {month}{RESET}")
    print(f"  Budget: ${summary.budget_usd:.2f}/month    YTD: ${ytd:.4f}")
    print()
    print(f"  {bar}  {bar_color}{summary.utilization_pct:.0f}%{RESET}")
    print(f"  Spent: {bar_color}${summary.total_cost_usd:.4f}{RESET} of ${summary.budget_usd:.2f}")
    print(f"  GPU hours: {summary.gpu_hours_total:.2f}h    Jobs: {summary.n_jobs}")
    print()
    print(f"  {'Purpose':<20s} {'Jobs':>5s} {'GPU-hrs':>8s} {'Cost':>8s}")
    print(f"  {'─'*20} {'─'*5} {'─'*8} {'─'*8}")
    for b in summary.breakdown:
        print(f"  {b['purpose']:<20s} {b['n_jobs']:>5d} {b['gpu_hours']:>7.2f}h ${b['cost_usd']:>7.4f}")
    print(f"  {'─'*20} {'─'*5} {'─'*8} {'─'*8}")
    print(f"  {'TOTAL':<20s} {summary.n_jobs:>5d} {summary.gpu_hours_total:>7.2f}h ${summary.total_cost_usd:>7.4f}")

    remaining = summary.budget_usd - summary.total_cost_usd
    if remaining < 5.0:
        print(f"\n  {RED}⚠ WARNING: Only ${remaining:.2f} remaining in monthly budget!{RESET}")
    elif remaining < 15.0:
        print(f"\n  {YELLOW}→ ${remaining:.2f} remaining in budget{RESET}")
    else:
        print(f"\n  {GREEN}✓ ${remaining:.2f} remaining (budget healthy){RESET}")
    print()


def cmd_report(month: str, db_path: Path) -> None:
    summary = monthly_summary(month, db_path)
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cost_entries WHERE started_at LIKE ? ORDER BY started_at",
            (f"{month}%",)
        ).fetchall()

    print(f"\n{BOLD}OCI Cost Report — {month}{RESET}")
    print(f"Total: ${summary.total_cost_usd:.4f} / ${summary.budget_usd:.2f} budget ({summary.utilization_pct:.0f}%)")
    print(f"GPU hours: {summary.gpu_hours_total:.2f}h across {summary.n_jobs} jobs")
    print()
    print(f"{'Date':<12s} {'Job ID':<32s} {'Purpose':<16s} {'GPU-hrs':>8s} {'Cost':>8s} {'Notes'}")
    print("─" * 110)
    for r in rows:
        date = r["started_at"][:10]
        cost_color = YELLOW if r["cost_usd"] > 0.50 else GRAY
        print(f"{date:<12s} {r['job_id']:<32s} {r['purpose']:<16s} {r['gpu_hours']:>7.2f}h "
              f"{cost_color}${r['cost_usd']:>7.4f}{RESET}  {r['notes'][:40]}")
    print()


def cmd_add(job_id: str, purpose: str, gpu_hours: float,
            n_gpus: int, notes: str, checkpoint: str, db_path: Path) -> None:
    import hashlib
    cost = gpu_hours * n_gpus * GPU4_HOURLY_USD
    now = datetime.now().isoformat()
    entry_id = hashlib.md5(f"{job_id}{now}".encode()).hexdigest()[:12]
    add_entry(CostEntry(
        entry_id=entry_id, job_id=job_id, purpose=purpose,
        gpu_hours=gpu_hours * n_gpus, storage_gb_hours=0.0,
        cost_usd=round(cost, 4), gpu_type="A100", n_gpus=n_gpus,
        started_at=now, completed_at=now,
        checkpoint_saved=checkpoint, notes=notes,
    ), db_path)
    print(f"[cost] Added job '{job_id}': {gpu_hours * n_gpus:.2f} GPU-hrs = ${cost:.4f}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OCI cost monitor")
    parser.add_argument("--status",       action="store_true", help="Show current month status")
    parser.add_argument("--report",       action="store_true", help="Full monthly report")
    parser.add_argument("--month",        default=datetime.now().strftime("%Y-%m"))
    parser.add_argument("--seed",         action="store_true", help="Seed DB with known jobs")
    parser.add_argument("--add-job",      action="store_true", help="Add a new cost entry")
    parser.add_argument("--job-id",       default="")
    parser.add_argument("--purpose",      default="fine-tune", choices=["BC fine-tune","DAgger","SDG","Eval","HPO","Benchmark","Other"])
    parser.add_argument("--gpu-hours",    type=float, default=0.5)
    parser.add_argument("--n-gpus",       type=int, default=1)
    parser.add_argument("--notes",        default="")
    parser.add_argument("--checkpoint",   default="")
    parser.add_argument("--db",           default=str(DB_PATH))
    args = parser.parse_args()

    db = Path(args.db)
    init_db(db)

    if args.seed:
        seed_known_jobs(db)
        print(f"[cost] Seeded {len(KNOWN_JOBS)} known jobs → {db}")

    if args.add_job:
        if not args.job_id:
            print("--job-id required")
            return
        cmd_add(args.job_id, args.purpose, args.gpu_hours, args.n_gpus,
                args.notes, args.checkpoint, db)

    if args.report:
        cmd_report(args.month, db)
    elif args.status or (not args.seed and not args.add_job):
        cmd_status(db)


if __name__ == "__main__":
    main()
