#!/usr/bin/env python3
"""
checkpoint_sync.py — Bidirectional checkpoint sync between OCI GPU4 and local machine.

Maintains a version manifest so you always know which checkpoints are:
  - local-only (new, not yet pushed)
  - remote-only (on OCI, not downloaded)
  - synced (both)
  - stale (local older than remote)

Usage:
    python src/infra/checkpoint_sync.py --list                     # show all checkpoints + status
    python src/infra/checkpoint_sync.py --push /tmp/finetune_1000_5k/checkpoint-5000
    python src/infra/checkpoint_sync.py --pull dagger_run4_iter3
    python src/infra/checkpoint_sync.py --sync-all                 # push local-only + pull remote-only
    python src/infra/checkpoint_sync.py --status                   # compact sync status
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

OCI_HOST   = "ubuntu@138.1.153.110"
OCI_BASE   = "/tmp"
LOCAL_BASE = "/tmp/roboticsai_checkpoints"
MANIFEST_PATH = Path.home() / ".cache" / "roboticsai" / "checkpoint_manifest.json"

# Known checkpoints in the project
KNOWN_CHECKPOINTS = [
    "finetune_500_5k/checkpoint-5000",
    "finetune_1000_5k/checkpoint-5000",
    "finetune_1000_5k/checkpoint-1000",
    "finetune_1000_5k/checkpoint-2000",
    "dagger_run4/iter1/checkpoint-2000",
    "dagger_run4/iter2/checkpoint-2000",
    "dagger_run4/iter3/checkpoint-2000",
    "dagger_run5/finetune_final/checkpoint-5000",
    "dagger_run6/iter1/checkpoint-3000",
    "dagger_run6/iter2/checkpoint-3000",
    "dagger_run6/iter3/checkpoint-3000",
    "dagger_run6/iter4/checkpoint-3000",
    "online_dagger/iter1/checkpoint-1000",
    "online_dagger/iter2/checkpoint-1000",
    "distilled_60m/checkpoint",
    "transfer_xarm7/checkpoint-500",
    "curriculum_dagger/checkpoint",
]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class CheckpointEntry:
    name: str                      # e.g. "dagger_run4_iter3"
    remote_path: str               # full OCI path
    local_path: str                # local mirror path
    status: str                    # "remote_only"/"local_only"/"synced"/"stale"
    remote_size_mb: float = 0.0
    local_size_mb:  float = 0.0
    remote_mtime:   str = ""
    local_mtime:    str = ""
    last_synced_at: str = ""
    success_rate:   float = -1.0   # known eval result, -1 = unknown
    notes:          str = ""


@dataclass
class Manifest:
    last_updated: str = ""
    oci_host: str = OCI_HOST
    entries: list[CheckpointEntry] = field(default_factory=list)


# ── Manifest I/O ──────────────────────────────────────────────────────────────

def load_manifest() -> Manifest:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        return Manifest(last_updated=datetime.now().isoformat())
    with open(MANIFEST_PATH) as f:
        data = json.load(f)
    entries = [CheckpointEntry(**e) for e in data.get("entries", [])]
    return Manifest(
        last_updated=data.get("last_updated", ""),
        oci_host=data.get("oci_host", OCI_HOST),
        entries=entries,
    )


def save_manifest(m: Manifest) -> None:
    m.last_updated = datetime.now().isoformat()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump({
            "last_updated": m.last_updated,
            "oci_host": m.oci_host,
            "entries": [asdict(e) for e in m.entries],
        }, f, indent=2)


def seed_mock_manifest() -> Manifest:
    """Create a mock manifest for demo / offline testing."""
    known_sr = {
        "finetune_1000_5k/checkpoint-5000": 0.05,
        "dagger_run4/iter3/checkpoint-2000": 0.65,
        "dagger_run5/finetune_final/checkpoint-5000": 0.05,
        "distilled_60m/checkpoint": 0.41,
        "transfer_xarm7/checkpoint-500": 0.48,
    }
    known_status = {
        "finetune_500_5k/checkpoint-5000":            "synced",
        "finetune_1000_5k/checkpoint-5000":           "synced",
        "finetune_1000_5k/checkpoint-1000":           "remote_only",
        "finetune_1000_5k/checkpoint-2000":           "remote_only",
        "dagger_run4/iter1/checkpoint-2000":          "remote_only",
        "dagger_run4/iter2/checkpoint-2000":          "remote_only",
        "dagger_run4/iter3/checkpoint-2000":          "synced",
        "dagger_run5/finetune_final/checkpoint-5000": "synced",
        "dagger_run6/iter1/checkpoint-3000":          "remote_only",
        "dagger_run6/iter2/checkpoint-3000":          "remote_only",
        "dagger_run6/iter3/checkpoint-3000":          "remote_only",
        "dagger_run6/iter4/checkpoint-3000":          "remote_only",
        "distilled_60m/checkpoint":                   "local_only",
        "transfer_xarm7/checkpoint-500":              "local_only",
        "curriculum_dagger/checkpoint":               "local_only",
    }

    entries = []
    for ckpt in KNOWN_CHECKPOINTS:
        name = ckpt.replace("/", "_").replace("-", "_")
        status = known_status.get(ckpt, "remote_only")
        size = 12_800.0 if "60m" in ckpt else 51_200.0  # MB: 60M vs 3B model
        entries.append(CheckpointEntry(
            name=name,
            remote_path=f"{OCI_BASE}/{ckpt}",
            local_path=f"{LOCAL_BASE}/{ckpt}",
            status=status,
            remote_size_mb=size if status in ("synced", "remote_only") else 0,
            local_size_mb=size if status in ("synced", "local_only") else 0,
            remote_mtime="2026-03-28T10:00:00" if status != "local_only" else "",
            local_mtime="2026-03-29T08:00:00" if status != "remote_only" else "",
            last_synced_at="2026-03-29T08:00:00" if status == "synced" else "",
            success_rate=known_sr.get(ckpt, -1.0),
        ))
    return Manifest(last_updated=datetime.now().isoformat(), entries=entries)


# ── SSH helpers ───────────────────────────────────────────────────────────────

def _ssh(cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", OCI_HOST, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _rsync_push(local_path: str, remote_path: str) -> tuple[bool, str]:
    cmd = [
        "rsync", "-avz", "--progress",
        "--exclude", "*.tmp", "--exclude", "__pycache__",
        local_path + "/", f"{OCI_HOST}:{remote_path}/"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0, result.stdout or result.stderr


def _rsync_pull(remote_path: str, local_path: str) -> tuple[bool, str]:
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync", "-avz", "--progress",
        "--exclude", "*.tmp",
        f"{OCI_HOST}:{remote_path}/", local_path + "/"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0, result.stdout or result.stderr


def check_remote_exists(remote_path: str) -> bool:
    rc, _, _ = _ssh(f"test -d '{remote_path}' && echo ok")
    return rc == 0


def get_remote_size_mb(remote_path: str) -> float:
    rc, out, _ = _ssh(f"du -sm '{remote_path}' 2>/dev/null | cut -f1")
    if rc == 0 and out.isdigit():
        return float(out)
    return 0.0


def get_local_size_mb(local_path: str) -> float:
    p = Path(local_path)
    if not p.exists():
        return 0.0
    total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return total / 1_048_576


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(manifest: Manifest) -> None:
    status_color = {
        "synced":      "\033[92m",   # green
        "remote_only": "\033[94m",   # blue
        "local_only":  "\033[93m",   # yellow
        "stale":       "\033[91m",   # red
    }
    RESET = "\033[0m"

    print(f"\n{'Checkpoint':<45s} {'Status':<14s} {'Remote MB':>10s} {'Local MB':>10s} {'SR':>6s}")
    print("-" * 95)
    for e in sorted(manifest.entries, key=lambda x: x.name):
        sc = status_color.get(e.status, "")
        sr_str = f"{e.success_rate:.0%}" if e.success_rate >= 0 else "  —  "
        print(f"{e.name:<45s} {sc}{e.status:<14s}{RESET} "
              f"{e.remote_size_mb:>9.0f}M {e.local_size_mb:>9.0f}M {sr_str:>6s}")
    print()
    total_remote = sum(e.remote_size_mb for e in manifest.entries if e.status in ("synced","remote_only"))
    total_local  = sum(e.local_size_mb  for e in manifest.entries if e.status in ("synced","local_only"))
    print(f"  Remote total: {total_remote/1024:.1f} GB  |  Local total: {total_local/1024:.1f} GB")
    print(f"  Last updated: {manifest.last_updated}\n")


def cmd_status(manifest: Manifest) -> None:
    counts = {}
    for e in manifest.entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    print(f"Checkpoints: {len(manifest.entries)} total — "
          + " · ".join(f"{v} {k}" for k, v in sorted(counts.items())))


def cmd_push(manifest: Manifest, checkpoint_name: str, dry_run: bool = False) -> None:
    entry = next((e for e in manifest.entries if checkpoint_name in e.name or
                  checkpoint_name in e.local_path), None)
    if not entry:
        print(f"[sync] Checkpoint '{checkpoint_name}' not in manifest. Use --list to see options.")
        return
    if entry.status == "remote_only":
        print(f"[sync] {entry.name} is remote-only — nothing to push (use --pull instead)")
        return
    if dry_run:
        print(f"[sync] DRY RUN: would push {entry.local_path} → {OCI_HOST}:{entry.remote_path}")
        return
    print(f"[sync] Pushing {entry.name} to OCI...")
    ok, msg = _rsync_push(entry.local_path, entry.remote_path)
    if ok:
        entry.status = "synced"
        entry.last_synced_at = datetime.now().isoformat()
        entry.remote_size_mb = get_remote_size_mb(entry.remote_path)
        save_manifest(manifest)
        print(f"[sync] ✓ Pushed {entry.name} ({entry.remote_size_mb:.0f} MB)")
    else:
        print(f"[sync] ✗ Push failed: {msg[:200]}")


def cmd_pull(manifest: Manifest, checkpoint_name: str, dry_run: bool = False) -> None:
    entry = next((e for e in manifest.entries if checkpoint_name in e.name or
                  checkpoint_name in e.remote_path), None)
    if not entry:
        print(f"[sync] Checkpoint '{checkpoint_name}' not in manifest.")
        return
    if entry.status == "local_only":
        print(f"[sync] {entry.name} is local-only — nothing to pull")
        return
    if dry_run:
        print(f"[sync] DRY RUN: would pull {OCI_HOST}:{entry.remote_path} → {entry.local_path}")
        return
    print(f"[sync] Pulling {entry.name} from OCI ({entry.remote_size_mb:.0f} MB)...")
    ok, msg = _rsync_pull(entry.remote_path, entry.local_path)
    if ok:
        entry.status = "synced"
        entry.last_synced_at = datetime.now().isoformat()
        entry.local_size_mb = get_local_size_mb(entry.local_path)
        save_manifest(manifest)
        print(f"[sync] ✓ Pulled {entry.name} ({entry.local_size_mb:.0f} MB)")
    else:
        print(f"[sync] ✗ Pull failed: {msg[:200]}")


def cmd_sync_all(manifest: Manifest, dry_run: bool = False) -> None:
    pushable = [e for e in manifest.entries if e.status == "local_only"]
    pullable = [e for e in manifest.entries if e.status == "remote_only"]
    print(f"[sync] {len(pushable)} to push, {len(pullable)} to pull")
    for e in pushable:
        cmd_push(manifest, e.name, dry_run)
    for e in pullable:
        cmd_pull(manifest, e.name, dry_run)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Checkpoint sync — OCI ↔ local")
    parser.add_argument("--list",       action="store_true", help="Show all checkpoints")
    parser.add_argument("--status",     action="store_true", help="Compact status summary")
    parser.add_argument("--push",       metavar="NAME",      help="Push checkpoint to OCI")
    parser.add_argument("--pull",       metavar="NAME",      help="Pull checkpoint from OCI")
    parser.add_argument("--sync-all",   action="store_true", help="Push local-only + pull remote-only")
    parser.add_argument("--dry-run",    action="store_true", help="Show what would happen, no I/O")
    parser.add_argument("--mock",       action="store_true", help="Use mock manifest (no SSH)")
    parser.add_argument("--seed",       action="store_true", help="Initialize manifest from known checkpoints")
    args = parser.parse_args()

    if args.mock or args.seed:
        manifest = seed_mock_manifest()
        if args.seed:
            save_manifest(manifest)
            print(f"[sync] Manifest seeded with {len(manifest.entries)} checkpoints → {MANIFEST_PATH}")
    else:
        manifest = load_manifest()
        if not manifest.entries:
            manifest = seed_mock_manifest()

    if args.list:
        cmd_list(manifest)
    elif args.status:
        cmd_status(manifest)
    elif args.push:
        cmd_push(manifest, args.push, args.dry_run)
    elif args.pull:
        cmd_pull(manifest, args.pull, args.dry_run)
    elif args.sync_all:
        cmd_sync_all(manifest, args.dry_run)
    else:
        # Default: show status
        cmd_status(manifest)
        print("Use --list for full table, --sync-all to sync, --help for options.")


if __name__ == "__main__":
    main()
