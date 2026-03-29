#!/usr/bin/env python3
"""
dataset_versioning.py — Dataset lineage and version tracking for OCI Robot Cloud.

Tracks which episodes trained which checkpoints, enabling:
  - Reproducibility: re-train from exact same data split
  - Auditability: design partners see what went into their model
  - Debug: bisect performance regressions to specific demo batches
  - Compliance: data provenance for gov/defense customers

Usage:
    python src/training/dataset_versioning.py --mock
    python src/training/dataset_versioning.py register-dataset /tmp/lerobot_dataset
    python src/training/dataset_versioning.py register-run --dataset <id> --checkpoint /tmp/ckpt-5000
    python src/training/dataset_versioning.py lineage <checkpoint_path>
    python src/training/dataset_versioning.py report --output /tmp/lineage_report.html

Storage:
    /tmp/dataset_versions.json — version registry (append-only log)
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np

REGISTRY_PATH = "/tmp/dataset_versions.json"


# ── Registry helpers ──────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if Path(REGISTRY_PATH).exists():
        return json.loads(Path(REGISTRY_PATH).read_text())
    return {"datasets": {}, "runs": {}}


def _save_registry(reg: dict):
    Path(REGISTRY_PATH).write_text(json.dumps(reg, indent=2))


def _hash_dir(path: str) -> str:
    """Stable content hash of a LeRobot v2 dataset directory."""
    p = Path(path)
    if not p.exists():
        return "unknown"
    files = sorted(p.rglob("*.parquet")) + sorted(p.rglob("meta/info.json"))
    h = hashlib.sha256()
    for f in files[:50]:   # cap at 50 files — deterministic, not exhaustive
        h.update(str(f.relative_to(p)).encode())
        try:
            h.update(str(f.stat().st_size).encode())
        except Exception:
            pass
    return h.hexdigest()[:16]


# ── Core operations ───────────────────────────────────────────────────────────

def register_dataset(path: str, source: str = "genesis_sdg", notes: str = "") -> str:
    """Register a dataset version. Returns dataset_id."""
    reg = _load_registry()
    content_hash = _hash_dir(path)
    did = f"ds_{content_hash}"

    # Count episodes and frames from meta/info.json if present
    info_path = Path(path) / "meta" / "info.json"
    n_episodes = None
    n_frames = None
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text())
            n_episodes = info.get("total_episodes")
            n_frames = info.get("total_frames")
        except Exception:
            pass

    reg["datasets"][did] = {
        "id": did,
        "path": str(path),
        "content_hash": content_hash,
        "source": source,
        "n_episodes": n_episodes,
        "n_frames": n_frames,
        "notes": notes,
        "registered_at": datetime.now().isoformat(),
    }
    _save_registry(reg)
    print(f"[versioning] Registered dataset: {did}")
    print(f"  path: {path}")
    if n_episodes:
        print(f"  episodes: {n_episodes}, frames: {n_frames}")
    return did


def register_run(
    dataset_id: str,
    checkpoint_path: str,
    training_steps: int = None,
    final_loss: float = None,
    eval_success_rate: float = None,
    parent_checkpoint: str = None,
    notes: str = "",
) -> str:
    """Register a training run linking dataset → checkpoint."""
    reg = _load_registry()
    if dataset_id not in reg["datasets"]:
        raise ValueError(f"Unknown dataset: {dataset_id}. Register it first.")

    ckpt_hash = hashlib.md5(checkpoint_path.encode()).hexdigest()[:8]
    rid = f"run_{ckpt_hash}_{int(time.time())}"

    reg["runs"][rid] = {
        "id": rid,
        "dataset_id": dataset_id,
        "checkpoint_path": checkpoint_path,
        "training_steps": training_steps,
        "final_loss": final_loss,
        "eval_success_rate": eval_success_rate,
        "parent_checkpoint": parent_checkpoint,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
    }
    _save_registry(reg)
    print(f"[versioning] Registered run: {rid}")
    print(f"  dataset: {dataset_id}")
    print(f"  checkpoint: {checkpoint_path}")
    if eval_success_rate is not None:
        print(f"  eval success: {eval_success_rate:.1%}")
    return rid


def get_lineage(checkpoint_path: str) -> list[dict]:
    """Return full lineage chain for a checkpoint (child → parent → grandparent ...)."""
    reg = _load_registry()
    chain = []
    current_ckpt = checkpoint_path
    seen = set()

    while current_ckpt:
        # Find run with this checkpoint
        run = None
        for r in reg["runs"].values():
            if r["checkpoint_path"] == current_ckpt:
                run = r
                break
        if not run or run["id"] in seen:
            break
        seen.add(run["id"])
        ds = reg["datasets"].get(run["dataset_id"], {})
        chain.append({"run": run, "dataset": ds})
        current_ckpt = run.get("parent_checkpoint")

    return chain


def print_lineage(checkpoint_path: str):
    chain = get_lineage(checkpoint_path)
    if not chain:
        print(f"[versioning] No lineage found for: {checkpoint_path}")
        return
    print(f"\nLineage for: {checkpoint_path}")
    print("=" * 60)
    for i, node in enumerate(chain):
        prefix = "  " * i + ("└─ " if i > 0 else "")
        r = node["run"]
        ds = node["dataset"]
        loss_str = f"loss={r['final_loss']:.4f}" if r.get("final_loss") else ""
        succ_str = f"success={r['eval_success_rate']:.1%}" if r.get("eval_success_rate") is not None else ""
        metrics = " · ".join(filter(None, [loss_str, succ_str]))
        print(f"{prefix}[{r['id']}] {r['checkpoint_path']}")
        if metrics:
            print(f"{'  '*(i+1)}  {metrics}")
        if ds.get("path"):
            n_str = f" ({ds['n_episodes']} eps)" if ds.get("n_episodes") else ""
            print(f"{'  '*(i+1)}  dataset: {ds['path']}{n_str} [{ds.get('source','?')}]")
        print(f"{'  '*(i+1)}  trained: {r['created_at'][:19]}")


# ── HTML report ───────────────────────────────────────────────────────────────

def make_report(output_path: str = "/tmp/lineage_report.html"):
    reg = _load_registry()
    datasets = sorted(reg["datasets"].values(), key=lambda d: d["registered_at"], reverse=True)
    runs = sorted(reg["runs"].values(), key=lambda r: r["created_at"], reverse=True)

    ds_rows = ""
    for d in datasets:
        n_str = f"{d['n_episodes']} eps / {d['n_frames']} frames" if d.get("n_episodes") else "—"
        ds_rows += (
            f"<tr><td><code>{d['id']}</code></td>"
            f"<td>{d['source']}</td>"
            f"<td>{n_str}</td>"
            f"<td style='max-width:250px;overflow:hidden;font-size:.8em'>{d['path']}</td>"
            f"<td style='color:#94a3b8'>{d['registered_at'][:10]}</td>"
            f"<td style='color:#64748b;font-size:.8em'>{d['notes'][:60]}</td></tr>"
        )
    if not ds_rows:
        ds_rows = "<tr><td colspan='6' style='color:#475569;text-align:center'>No datasets registered</td></tr>"

    run_rows = ""
    for r in runs:
        ds = reg["datasets"].get(r["dataset_id"], {})
        loss_str = f"{r['final_loss']:.4f}" if r.get("final_loss") is not None else "—"
        sr = r.get("eval_success_rate")
        sr_color = "#10b981" if sr and sr >= 0.1 else "#f59e0b" if sr and sr >= 0.01 else "#ef4444" if sr is not None else "#94a3b8"
        sr_str = f"{sr:.1%}" if sr is not None else "—"
        steps_str = f"{r['training_steps']:,}" if r.get("training_steps") else "—"
        parent_str = "↑ " + Path(r["parent_checkpoint"]).name if r.get("parent_checkpoint") else "BC"
        run_rows += (
            f"<tr><td><code>{r['id'][:18]}</code></td>"
            f"<td style='font-size:.8em'>{Path(r['checkpoint_path']).name}</td>"
            f"<td style='color:#94a3b8;font-size:.8em'>{r.get('dataset_id','—')}</td>"
            f"<td style='color:#94a3b8'>{steps_str}</td>"
            f"<td>{loss_str}</td>"
            f"<td style='color:{sr_color};font-weight:bold'>{sr_str}</td>"
            f"<td style='color:#64748b;font-size:.8em'>{parent_str}</td>"
            f"<td style='color:#94a3b8;font-size:.8em'>{r['created_at'][:10]}</td></tr>"
        )
    if not run_rows:
        run_rows = "<tr><td colspan='8' style='color:#475569;text-align:center'>No training runs registered</td></tr>"

    html = f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Dataset Lineage — OCI Robot Cloud</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px 32px;margin:0}}
h1{{color:#C74634}} h2{{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.1em;
border-bottom:1px solid #1e293b;padding-bottom:5px;margin-top:28px}}
table{{width:100%;border-collapse:collapse}} th{{background:#C74634;color:white;padding:7px 12px;text-align:left;font-size:.82em}}
td{{padding:6px 12px;border-bottom:1px solid #1e293b;font-size:.88em}}
tr:nth-child(even) td{{background:#172033}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0}}
.card{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
.val{{font-size:2em;font-weight:bold}} .lbl{{color:#64748b;font-size:.78em}}
</style></head><body>
<h1>Dataset Lineage Registry</h1>
<p style="color:#64748b">OCI Robot Cloud · Data provenance for reproducibility and compliance</p>

<div class="grid">
  <div class="card"><div class="val">{len(datasets)}</div><div class="lbl">Registered Datasets</div></div>
  <div class="card"><div class="val">{len(runs)}</div><div class="lbl">Training Runs</div></div>
  <div class="card"><div class="val" style="color:#10b981">{sum(1 for r in runs if r.get('eval_success_rate') and r['eval_success_rate'] > 0)}</div><div class="lbl">Runs with >0% Success</div></div>
</div>

<h2>Datasets</h2>
<table>
  <tr><th>ID</th><th>Source</th><th>Size</th><th>Path</th><th>Registered</th><th>Notes</th></tr>
  {ds_rows}
</table>

<h2>Training Runs (newest first)</h2>
<table>
  <tr><th>Run ID</th><th>Checkpoint</th><th>Dataset</th><th>Steps</th><th>Final Loss</th><th>Success Rate</th><th>Parent</th><th>Date</th></tr>
  {run_rows}
</table>

<h2>How to Use</h2>
<pre style="background:#1e293b;padding:14px;border-radius:6px;font-size:.82em;overflow-x:auto">
# Register a new dataset
python src/training/dataset_versioning.py register-dataset /tmp/lerobot_dataset --source genesis_sdg

# Register a training run
python src/training/dataset_versioning.py register-run \\
  --dataset ds_abc123def456 \\
  --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 \\
  --steps 5000 --loss 0.099 --success-rate 0.05

# Trace lineage
python src/training/dataset_versioning.py lineage /tmp/dagger_run5/finetune_final/checkpoint-5000

# Generate HTML report
python src/training/dataset_versioning.py report --output /tmp/lineage_report.html
</pre>

<p style="color:#475569;font-size:.8em;margin-top:28px">OCI Robot Cloud · github.com/qianjun22/roboticsai</p>
</body></html>"""

    Path(output_path).write_text(html)
    print(f"[versioning] Report: {output_path}")
    print(f"[versioning] Registry: {REGISTRY_PATH}")
    return html


# ── Mock seeder ───────────────────────────────────────────────────────────────

def seed_mock():
    """Populate registry with the actual OCI Robot Cloud training history."""
    reg = {"datasets": {}, "runs": {}}

    # Dataset 1: 100 IK-planned demos (SDG session 5)
    reg["datasets"]["ds_session5_100"] = {
        "id": "ds_session5_100", "path": "/tmp/lerobot_dataset",
        "content_hash": "a1b2c3d4e5f6a7b8", "source": "genesis_ik_sdg",
        "n_episodes": 100, "n_frames": 10000,
        "notes": "100 IK-planned pick-and-lift demos; seed=42; cube position fixed",
        "registered_at": "2026-03-15T10:00:00",
    }
    # Dataset 2: 1000 diverse demos (session 11)
    reg["datasets"]["ds_session11_1000"] = {
        "id": "ds_session11_1000", "path": "/tmp/sdg_1000_lerobot",
        "content_hash": "b2c3d4e5f6a7b8c9", "source": "genesis_ik_sdg",
        "n_episodes": 1000, "n_frames": 50000,
        "notes": "500 original + 500 extra (seed=999, cube position randomized); merged dataset",
        "registered_at": "2026-03-20T09:00:00",
    }
    # Dataset 3: DAgger run5 (99 on-policy episodes)
    reg["datasets"]["ds_dagger_run5_99"] = {
        "id": "ds_dagger_run5_99", "path": "/tmp/dagger_run5/dataset/lerobot",
        "content_hash": "c3d4e5f6a7b8c9d0", "source": "dagger_online",
        "n_episodes": 99, "n_frames": 9900,
        "notes": "DAgger run5; 5 iters × ~20 eps; beta 0.30→0.07; IK expert intervention decline 64→29 steps/ep",
        "registered_at": "2026-03-27T14:00:00",
    }

    # Run 1: 100-demo 2000-step baseline
    reg["runs"]["run_100d_2000s"] = {
        "id": "run_100d_2000s", "dataset_id": "ds_session5_100",
        "checkpoint_path": "/tmp/lerobot_finetune/checkpoint-2000",
        "training_steps": 2000, "final_loss": 0.30, "eval_success_rate": None,
        "parent_checkpoint": None, "notes": "Early MAE eval: 0.103 baseline, 0.013 after SDG fine-tune",
        "created_at": "2026-03-15T14:00:00",
    }
    # Run 2: 1000-demo 5000-step BC
    reg["runs"]["run_1000d_5000s"] = {
        "id": "run_1000d_5000s", "dataset_id": "ds_session11_1000",
        "checkpoint_path": "/tmp/finetune_1000_5k/checkpoint-5000",
        "training_steps": 5000, "final_loss": 0.099, "eval_success_rate": 0.05,
        "parent_checkpoint": None,
        "notes": "1000-demo BC baseline; 35.4min on OCI GPU4; 5% closed-loop success (1/20 episodes)",
        "created_at": "2026-03-20T13:30:00",
    }
    # Run 3: DAgger run5 iter02 fine-tune (the only successful iter fine-tune)
    reg["runs"]["run_dagger5_iter02"] = {
        "id": "run_dagger5_iter02", "dataset_id": "ds_dagger_run5_99",
        "checkpoint_path": "/tmp/dagger_run5/iter_02/checkpoint-2000",
        "training_steps": 2000, "final_loss": 0.058, "eval_success_rate": 0.0,
        "parent_checkpoint": "/tmp/finetune_1000_5k/checkpoint-5000",
        "notes": "DAgger run5 iter_02 fine-tune (only iter that completed; others OOM due to server+train competition)",
        "created_at": "2026-03-26T10:00:00",
    }
    # Run 4: Manual 5000-step fine-tune on all 99 DAgger eps (in progress → placeholder)
    reg["runs"]["run_dagger5_manual"] = {
        "id": "run_dagger5_manual", "dataset_id": "ds_dagger_run5_99",
        "checkpoint_path": "/tmp/dagger_run5/finetune_final/checkpoint-5000",
        "training_steps": 5000, "final_loss": None, "eval_success_rate": None,
        "parent_checkpoint": "/tmp/finetune_1000_5k/checkpoint-5000",
        "notes": "Manual fine-tune on all 99 DAgger episodes (run5 collection); targeting >5% CL success; IN PROGRESS",
        "created_at": "2026-03-29T14:04:00",
    }

    _save_registry(reg)
    print("[versioning] Mock registry seeded with OCI training history")
    make_report("/tmp/lineage_report.html")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dataset version registry for OCI Robot Cloud")
    sub = parser.add_subparsers(dest="cmd")

    p_reg = sub.add_parser("register-dataset")
    p_reg.add_argument("path")
    p_reg.add_argument("--source", default="genesis_sdg")
    p_reg.add_argument("--notes", default="")

    p_run = sub.add_parser("register-run")
    p_run.add_argument("--dataset", required=True)
    p_run.add_argument("--checkpoint", required=True)
    p_run.add_argument("--steps", type=int)
    p_run.add_argument("--loss", type=float)
    p_run.add_argument("--success-rate", type=float)
    p_run.add_argument("--parent", default=None)
    p_run.add_argument("--notes", default="")

    p_lin = sub.add_parser("lineage")
    p_lin.add_argument("checkpoint")

    p_rep = sub.add_parser("report")
    p_rep.add_argument("--output", default="/tmp/lineage_report.html")

    parser.add_argument("--mock", action="store_true")

    args = parser.parse_args()

    if args.mock or args.cmd is None:
        seed_mock()
        return

    if args.cmd == "register-dataset":
        register_dataset(args.path, args.source, args.notes)
    elif args.cmd == "register-run":
        register_run(
            args.dataset, args.checkpoint,
            training_steps=args.steps, final_loss=args.loss,
            eval_success_rate=args.success_rate,
            parent_checkpoint=args.parent, notes=args.notes,
        )
    elif args.cmd == "lineage":
        print_lineage(args.checkpoint)
    elif args.cmd == "report":
        make_report(args.output)


if __name__ == "__main__":
    main()
