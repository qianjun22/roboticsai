#!/usr/bin/env python3
"""
cost_attribution.py — Per-partner, per-task, per-checkpoint cost attribution.

Breaks down OCI GPU spending by design partner, task type, and checkpoint to
support accurate billing, quota enforcement, and ROI reporting.

Usage:
    python src/infra/cost_attribution.py --status
    python src/infra/cost_attribution.py --partner-report --partner acme-robotics
    python src/infra/cost_attribution.py --add --partner acme-robotics \
        --task pick-lift --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 \
        --gpu-hours 0.59 --job-type fine-tune
    python src/infra/cost_attribution.py --export --output /tmp/cost_attribution.csv
"""

import csv
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / ".cache" / "roboticsai" / "cost_attribution.db"
GPU4_HOURLY_USD = 4.20   # OCI A100 GPU4

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
GRAY   = "\033[90m"


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS attribution (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id   TEXT NOT NULL,
    task         TEXT NOT NULL,
    job_type     TEXT NOT NULL,
    checkpoint   TEXT,
    gpu_hours    REAL NOT NULL,
    cost_usd     REAL NOT NULL,
    started_at   TEXT NOT NULL,
    job_id       TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS partners (
    partner_id   TEXT PRIMARY KEY,
    display_name TEXT,
    tier         TEXT DEFAULT 'starter',
    budget_usd   REAL DEFAULT 100.0,
    created_at   TEXT
);
"""

KNOWN_PARTNERS = [
    ("internal",        "OCI Internal",          "enterprise", 200.0),
    ("acme-robotics",   "ACME Robotics (pilot)",  "growth",     150.0),
    ("autobot-inc",     "AutoBot Inc",            "starter",    100.0),
    ("deepmanip-ai",    "DeepManip AI",           "starter",    100.0),
    ("roboflex-corp",   "RoboFlex Corp",          "growth",     150.0),
]

# Historical jobs attributed to partners
KNOWN_ATTRIBUTIONS = [
    # (partner_id, task, job_type, checkpoint, gpu_hours, date, job_id, notes)
    ("internal", "pick-lift", "SDG",       "",                                           0.05, "2026-03-15", "sdg_500_genesis",    "500 eps Genesis"),
    ("internal", "pick-lift", "fine-tune", "/tmp/finetune_500_5k/checkpoint-5000",       0.59, "2026-03-17", "finetune_500_5k",    "500-demo BC baseline"),
    ("internal", "pick-lift", "SDG",       "",                                           0.09, "2026-03-20", "sdg_1000_genesis",   "1000 eps IK"),
    ("internal", "pick-lift", "fine-tune", "/tmp/finetune_1000_5k/checkpoint-5000",      0.59, "2026-03-21", "finetune_1000_5k",   "1000-demo BC"),
    ("internal", "pick-lift", "eval",      "",                                           0.06, "2026-03-17", "eval_500_demo",      "20-ep eval"),
    ("internal", "pick-lift", "eval",      "",                                           0.06, "2026-03-22", "eval_1000_demo",     "20-ep eval: 5%"),
    ("internal", "pick-lift", "DAgger",    "/tmp/dagger_run3/checkpoint",                0.28, "2026-03-23", "dagger_run3",        "beta=0.5, 3 iters"),
    ("internal", "pick-lift", "DAgger",    "/tmp/dagger_run4/iter3/checkpoint-2000",     0.38, "2026-03-25", "dagger_run4",        "3 iters, 65% CL"),
    ("internal", "pick-lift", "DAgger",    "/tmp/dagger_run5/finetune_final/checkpoint-5000", 0.26, "2026-03-27", "dagger_run5", "5000-step: 5%"),
    ("internal", "benchmark", "Benchmark", "",                                           0.03, "2026-03-22", "multi_gpu_ddp_test", "4-GPU DDP 3.07×"),
    ("internal", "pick-lift", "HPO",       "",                                           0.24, "2026-03-20", "hpo_search",         "20 trials Optuna"),
    ("internal", "pick-lift", "DAgger",    "/tmp/dagger_run6/iter4/checkpoint-3000",     0.62, "2026-03-28", "dagger_run6",        "beta=0.10, 4 iters"),
    ("acme-robotics",  "pick-place", "fine-tune", "", 0.68, "2026-04-10", "acme_ft_01",      "Pilot fine-tune"),
    ("acme-robotics",  "pick-place", "eval",      "", 0.07, "2026-04-11", "acme_eval_01",    "20-ep eval pilot"),
    ("autobot-inc",    "push-goal",  "fine-tune", "", 0.59, "2026-04-15", "autobot_ft_01",   "Push-goal task"),
    ("deepmanip-ai",   "pick-lift",  "SDG",       "", 0.12, "2026-04-18", "deepmanip_sdg_01","200 eps"),
    ("deepmanip-ai",   "pick-lift",  "fine-tune", "", 0.59, "2026-04-19", "deepmanip_ft_01", "200-demo ft"),
]


# ── DB helpers ────────────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_db(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def seed_db(db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        for pid, name, tier, budget in KNOWN_PARTNERS:
            conn.execute(
                "INSERT OR IGNORE INTO partners VALUES (?,?,?,?,?)",
                (pid, name, tier, budget, "2026-03-01T00:00:00")
            )
        for (partner, task, jtype, ckpt, gpu_h, date, jid, notes) in KNOWN_ATTRIBUTIONS:
            cost = gpu_h * GPU4_HOURLY_USD
            conn.execute(
                "INSERT INTO attribution (partner_id,task,job_type,checkpoint,"
                "gpu_hours,cost_usd,started_at,job_id,notes) VALUES (?,?,?,?,?,?,?,?,?)",
                (partner, task, jtype, ckpt, gpu_h, round(cost, 4),
                 f"{date}T09:00:00", jid, notes)
            )
    print(f"[attr] Seeded {len(KNOWN_PARTNERS)} partners + {len(KNOWN_ATTRIBUTIONS)} jobs")


def add_entry(partner_id: str, task: str, job_type: str, checkpoint: str,
              gpu_hours: float, job_id: str, notes: str,
              db_path: Path = DB_PATH) -> None:
    cost = gpu_hours * GPU4_HOURLY_USD
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO attribution (partner_id,task,job_type,checkpoint,"
            "gpu_hours,cost_usd,started_at,job_id,notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (partner_id, task, job_type, checkpoint, gpu_hours,
             round(cost, 4), datetime.now().isoformat(), job_id, notes)
        )
    print(f"[attr] Added: {partner_id}/{task}/{job_type} — {gpu_hours:.2f} GPU-h = ${cost:.4f}")


# ── Queries ───────────────────────────────────────────────────────────────────

def partner_summary(db_path: Path = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute("""
            SELECT a.partner_id, p.display_name, p.tier, p.budget_usd,
                   SUM(a.gpu_hours) as total_gpu_h,
                   SUM(a.cost_usd)  as total_cost,
                   COUNT(*)         as n_jobs
            FROM attribution a
            LEFT JOIN partners p USING (partner_id)
            GROUP BY a.partner_id
            ORDER BY total_cost DESC
        """).fetchall()
    return [dict(r) for r in rows]


def partner_detail(partner_id: str, db_path: Path = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM attribution WHERE partner_id=? ORDER BY started_at",
            (partner_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def task_breakdown(db_path: Path = DB_PATH) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute("""
            SELECT task, job_type,
                   COUNT(*) as n_jobs,
                   SUM(gpu_hours) as total_gpu_h,
                   SUM(cost_usd)  as total_cost
            FROM attribution
            GROUP BY task, job_type
            ORDER BY total_cost DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ── CLI display ───────────────────────────────────────────────────────────────

def cmd_status(db_path: Path) -> None:
    summaries = partner_summary(db_path)
    grand_total = sum(s["total_cost"] for s in summaries)
    grand_gpu_h = sum(s["total_gpu_h"] for s in summaries)
    grand_jobs  = sum(s["n_jobs"]      for s in summaries)

    print(f"\n{BOLD}OCI Cost Attribution — All Partners{RESET}")
    print(f"  Total spent: ${grand_total:.4f}  |  GPU-hours: {grand_gpu_h:.2f}h  |  Jobs: {grand_jobs}\n")
    print(f"  {'Partner':<22} {'Tier':<12} {'Jobs':>5} {'GPU-h':>7} {'Cost':>9} {'Budget':>9} {'%':>6}")
    print(f"  {'─'*22} {'─'*12} {'─'*5} {'─'*7} {'─'*9} {'─'*9} {'─'*6}")
    for s in summaries:
        budget = s.get("budget_usd") or 100.0
        pct = s["total_cost"] / budget * 100
        col = GREEN if pct < 60 else YELLOW if pct < 85 else RED
        print(f"  {(s.get('display_name') or s['partner_id']):<22} "
              f"{(s.get('tier') or 'starter'):<12} "
              f"{s['n_jobs']:>5d} "
              f"{s['total_gpu_h']:>6.2f}h "
              f"${s['total_cost']:>8.4f} "
              f"${budget:>8.2f} "
              f"{col}{pct:>5.0f}%{RESET}")

    print(f"\n  {'Task Breakdown':}")
    print(f"  {'─'*60}")
    for tb in task_breakdown(db_path):
        print(f"  {tb['task']:<15} {tb['job_type']:<12} "
              f"{tb['n_jobs']:>3}× {tb['total_gpu_h']:>5.2f}h  ${tb['total_cost']:>7.4f}")
    print()


def cmd_partner_report(partner_id: str, db_path: Path) -> None:
    rows = partner_detail(partner_id, db_path)
    if not rows:
        print(f"[attr] No data for partner '{partner_id}'")
        return

    total_cost = sum(r["cost_usd"] for r in rows)
    total_gpu  = sum(r["gpu_hours"] for r in rows)

    print(f"\n{BOLD}Partner Report: {partner_id}{RESET}")
    print(f"  Total: ${total_cost:.4f}  |  {total_gpu:.2f} GPU-h  |  {len(rows)} jobs\n")
    print(f"  {'Date':<12} {'Task':<14} {'Type':<12} {'GPU-h':>6} {'Cost':>8}  Notes")
    print(f"  {'─'*12} {'─'*14} {'─'*12} {'─'*6} {'─'*8}  {'─'*30}")
    for r in rows:
        date = r["started_at"][:10]
        cost_col = YELLOW if r["cost_usd"] > 0.50 else GRAY
        print(f"  {date:<12} {r['task']:<14} {r['job_type']:<12} "
              f"{r['gpu_hours']:>5.2f}h {cost_col}${r['cost_usd']:>7.4f}{RESET}  "
              f"{(r['notes'] or '')[:35]}")
    print()


def cmd_export(output: str, db_path: Path) -> None:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT a.*, p.display_name, p.tier FROM attribution a "
            "LEFT JOIN partners p USING (partner_id) ORDER BY started_at"
        ).fetchall()

    out_path = Path(output)
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "partner_id", "display_name", "tier",
                          "task", "job_type", "gpu_hours", "cost_usd",
                          "job_id", "checkpoint", "notes"])
        for r in rows:
            writer.writerow([
                r["started_at"][:10], r["partner_id"], r["display_name"], r["tier"],
                r["task"], r["job_type"], r["gpu_hours"], r["cost_usd"],
                r["job_id"], r["checkpoint"], r["notes"]
            ])
    print(f"[attr] Exported {len(rows)} rows → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OCI cost attribution by partner/task")
    parser.add_argument("--status",         action="store_true", help="Show all-partner summary")
    parser.add_argument("--partner-report", action="store_true", help="Show detail for one partner")
    parser.add_argument("--partner",        default="internal")
    parser.add_argument("--add",            action="store_true", help="Add a cost entry")
    parser.add_argument("--task",           default="pick-lift")
    parser.add_argument("--job-type",       default="fine-tune",
                        choices=["fine-tune","DAgger","SDG","eval","HPO","benchmark","other"])
    parser.add_argument("--checkpoint",     default="")
    parser.add_argument("--gpu-hours",      type=float, default=0.5)
    parser.add_argument("--job-id",         default="")
    parser.add_argument("--notes",          default="")
    parser.add_argument("--export",         action="store_true", help="Export to CSV")
    parser.add_argument("--output",         default="/tmp/cost_attribution.csv")
    parser.add_argument("--seed",           action="store_true", help="Seed known jobs")
    parser.add_argument("--db",             default=str(DB_PATH))
    args = parser.parse_args()

    db = Path(args.db)
    init_db(db)

    if args.seed:
        seed_db(db)

    if args.add:
        add_entry(args.partner, args.task, args.job_type, args.checkpoint,
                  args.gpu_hours, args.job_id, args.notes, db)

    if args.partner_report:
        cmd_partner_report(args.partner, db)
    elif args.export:
        cmd_export(args.output, db)
    else:
        cmd_status(db)


if __name__ == "__main__":
    main()
