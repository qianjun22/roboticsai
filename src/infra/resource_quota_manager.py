#!/usr/bin/env python3
"""
resource_quota_manager.py — GPU quota enforcement for design partner workloads.

Tracks per-partner GPU-hour consumption and enforces monthly limits to prevent
runaway costs and ensure fair resource sharing across design partners.

Usage:
    python src/infra/resource_quota_manager.py --status
    python src/infra/resource_quota_manager.py --check --partner acme-robotics --gpu-hours 2.0
    python src/infra/resource_quota_manager.py --consume --partner acme-robotics \
        --gpu-hours 0.59 --job-id finetune_acme_002 --job-type fine-tune
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / ".cache" / "roboticsai" / "resource_quota.db"
GPU4_HOURLY_USD = 4.20

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
GRAY   = "\033[90m"

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotas (
    partner_id      TEXT PRIMARY KEY,
    display_name    TEXT,
    tier            TEXT DEFAULT 'starter',
    monthly_gpu_h   REAL DEFAULT 24.0,
    monthly_usd     REAL DEFAULT 100.0,
    created_at      TEXT
);
CREATE TABLE IF NOT EXISTS usage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id  TEXT NOT NULL,
    job_id      TEXT,
    job_type    TEXT,
    gpu_hours   REAL NOT NULL,
    cost_usd    REAL NOT NULL,
    started_at  TEXT NOT NULL,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS quota_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id  TEXT,
    event_type  TEXT,   -- check_ok / check_denied / quota_warning / quota_exceeded
    gpu_hours   REAL,
    message     TEXT,
    timestamp   TEXT
);
"""

# Tier quota defaults
TIER_QUOTAS = {
    "starter":    {"gpu_h": 24.0,  "usd": 100.0},
    "growth":     {"gpu_h": 120.0, "usd": 500.0},
    "enterprise": {"gpu_h": 500.0, "usd": 2100.0},
    "internal":   {"gpu_h": 999.0, "usd": 5000.0},
}

KNOWN_PARTNERS = [
    ("internal",       "OCI Internal",          "internal"),
    ("acme-robotics",  "ACME Robotics",          "growth"),
    ("autobot-inc",    "AutoBot Inc",            "starter"),
    ("deepmanip-ai",   "DeepManip AI",           "starter"),
    ("roboflex-corp",  "RoboFlex Corp",          "growth"),
]

SEED_USAGE = [
    # (partner_id, job_id, job_type, gpu_hours, date)
    ("internal",      "sdg_500_genesis",    "SDG",       0.05, "2026-03-15"),
    ("internal",      "finetune_500_5k",    "fine-tune", 0.59, "2026-03-17"),
    ("internal",      "sdg_1000_genesis",   "SDG",       0.09, "2026-03-20"),
    ("internal",      "finetune_1000_5k",   "fine-tune", 0.59, "2026-03-21"),
    ("internal",      "dagger_run6",        "DAgger",    0.62, "2026-03-28"),
    ("acme-robotics",  "acme_ft_01",        "fine-tune", 0.68, "2026-04-10"),
    ("acme-robotics",  "acme_eval_01",      "eval",      0.07, "2026-04-11"),
    ("autobot-inc",    "autobot_ft_01",     "fine-tune", 0.59, "2026-04-15"),
    ("deepmanip-ai",   "deepmanip_sdg_01",  "SDG",       0.12, "2026-04-18"),
    ("deepmanip-ai",   "deepmanip_ft_01",   "fine-tune", 0.59, "2026-04-19"),
]


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
        for pid, name, tier in KNOWN_PARTNERS:
            q = TIER_QUOTAS[tier]
            conn.execute(
                "INSERT OR IGNORE INTO quotas VALUES (?,?,?,?,?,?)",
                (pid, name, tier, q["gpu_h"], q["usd"], "2026-03-01T00:00:00")
            )
        for pid, jid, jtype, gpu_h, date in SEED_USAGE:
            conn.execute(
                "INSERT INTO usage (partner_id,job_id,job_type,gpu_hours,cost_usd,started_at) "
                "VALUES (?,?,?,?,?,?)",
                (pid, jid, jtype, gpu_h, round(gpu_h * GPU4_HOURLY_USD, 4),
                 f"{date}T09:00:00")
            )
    print(f"[quota] Seeded {len(KNOWN_PARTNERS)} partners + {len(SEED_USAGE)} usage records")


def get_month_usage(partner_id: str, month: str = None,
                    db_path: Path = DB_PATH) -> float:
    month = month or datetime.now().strftime("%Y-%m")
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT SUM(gpu_hours) as total FROM usage "
            "WHERE partner_id=? AND started_at LIKE ?",
            (partner_id, f"{month}%")
        ).fetchone()
    return round(row["total"] or 0.0, 3)


def check_quota(partner_id: str, requested_gpu_h: float,
                db_path: Path = DB_PATH) -> tuple[bool, str]:
    """Returns (allowed, message)."""
    with get_db(db_path) as conn:
        quota_row = conn.execute(
            "SELECT * FROM quotas WHERE partner_id=?", (partner_id,)
        ).fetchone()

    if not quota_row:
        return False, f"Partner '{partner_id}' not found"

    used = get_month_usage(partner_id, db_path=db_path)
    limit = quota_row["monthly_gpu_h"]
    after = used + requested_gpu_h

    if after > limit:
        msg = f"Quota exceeded: {used:.2f}h used + {requested_gpu_h:.2f}h requested = {after:.2f}h > {limit:.0f}h limit"
        _log_event(partner_id, "check_denied", requested_gpu_h, msg, db_path)
        return False, msg
    elif after > limit * 0.85:
        msg = f"Quota warning: {after:.2f}h would use {after/limit*100:.0f}% of {limit:.0f}h limit"
        _log_event(partner_id, "quota_warning", requested_gpu_h, msg, db_path)
        return True, msg
    else:
        msg = f"OK: {used:.2f}h + {requested_gpu_h:.2f}h = {after:.2f}h / {limit:.0f}h ({after/limit*100:.0f}%)"
        _log_event(partner_id, "check_ok", requested_gpu_h, msg, db_path)
        return True, msg


def consume_quota(partner_id: str, gpu_hours: float, job_id: str = "",
                  job_type: str = "fine-tune", notes: str = "",
                  db_path: Path = DB_PATH) -> dict:
    """Record GPU usage for a partner. Returns result dict."""
    allowed, msg = check_quota(partner_id, gpu_hours, db_path)
    if not allowed:
        return {"success": False, "message": msg}

    cost = round(gpu_hours * GPU4_HOURLY_USD, 4)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage (partner_id,job_id,job_type,gpu_hours,cost_usd,started_at,notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (partner_id, job_id, job_type, gpu_hours, cost,
             datetime.now().isoformat(), notes)
        )
    return {"success": True, "message": msg, "gpu_hours": gpu_hours, "cost_usd": cost}


def _log_event(partner_id: str, event_type: str, gpu_hours: float,
               message: str, db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO quota_events (partner_id,event_type,gpu_hours,message,timestamp) "
            "VALUES (?,?,?,?,?)",
            (partner_id, event_type, gpu_hours, message, datetime.now().isoformat())
        )


def cmd_status(db_path: Path) -> None:
    month = datetime.now().strftime("%Y-%m")
    with get_db(db_path) as conn:
        partners = conn.execute("SELECT * FROM quotas ORDER BY tier").fetchall()

    print(f"\n{BOLD}Resource Quota Manager — {month}{RESET}\n")
    print(f"  {'Partner':<22} {'Tier':<12} {'Used':>8} {'Limit':>8} {'%':>6} {'Status'}")
    print(f"  {'─'*22} {'─'*12} {'─'*8} {'─'*8} {'─'*6} {'─'*12}")

    for p in partners:
        used = get_month_usage(p["partner_id"], month, db_path)
        limit = p["monthly_gpu_h"]
        pct = used / limit * 100 if limit > 0 else 0
        col = GREEN if pct < 60 else YELLOW if pct < 85 else RED
        status = "healthy" if pct < 60 else "warning" if pct < 85 else "EXCEEDED"
        print(f"  {(p['display_name'] or p['partner_id']):<22} "
              f"{p['tier']:<12} "
              f"{used:>7.2f}h "
              f"{limit:>7.0f}h "
              f"{col}{pct:>5.0f}%{RESET} "
              f"{col}{status}{RESET}")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GPU resource quota manager")
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--check",    action="store_true", help="Check if quota allows request")
    parser.add_argument("--consume",  action="store_true", help="Record GPU usage")
    parser.add_argument("--seed",     action="store_true")
    parser.add_argument("--partner",  default="internal")
    parser.add_argument("--gpu-hours",type=float, default=0.5)
    parser.add_argument("--job-id",   default="")
    parser.add_argument("--job-type", default="fine-tune")
    parser.add_argument("--notes",    default="")
    parser.add_argument("--db",       default=str(DB_PATH))
    args = parser.parse_args()

    db = Path(args.db)
    init_db(db)

    if args.seed:
        seed_db(db)

    if args.check:
        allowed, msg = check_quota(args.partner, args.gpu_hours, db)
        icon = f"{GREEN}✓{RESET}" if allowed else f"{RED}✗{RESET}"
        print(f"  {icon} {msg}")

    elif args.consume:
        result = consume_quota(args.partner, args.gpu_hours, args.job_id,
                               args.job_type, args.notes, db)
        if result["success"]:
            print(f"  {GREEN}✓{RESET} Recorded: {args.gpu_hours}h = ${result['cost_usd']:.4f}")
            print(f"    {result['message']}")
        else:
            print(f"  {RED}✗{RESET} DENIED: {result['message']}")

    else:
        cmd_status(db)


if __name__ == "__main__":
    main()
