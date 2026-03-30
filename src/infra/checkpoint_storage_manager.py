#!/usr/bin/env python3
"""
checkpoint_storage_manager.py — Checkpoint storage lifecycle management for OCI Robot Cloud.

Manages checkpoint retention policies, storage costs, archival, and cleanup across
training runs to minimize OCI Object Storage costs while preserving key checkpoints.

Usage:
    python src/infra/checkpoint_storage_manager.py --mock --output /tmp/checkpoint_storage_manager.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Storage tiers ──────────────────────────────────────────────────────────────

STORAGE_TIERS = [
    # (name, cost_per_gb_month, retrieval_latency_s, use_case)
    ("hot_standard",   0.0255, 0.1,   "Active checkpoints, last 3 runs"),
    ("infrequent",     0.0102, 5.0,   "Recent runs, past 30 days"),
    ("archive",        0.0026, 3600,  "Historical checkpoints, 30-90 days"),
    ("deep_archive",   0.0009, 86400, "Long-term retention, >90 days"),
]

# ── Checkpoint metadata ────────────────────────────────────────────────────────

@dataclass
class CheckpointRecord:
    run_id: str
    step: int
    size_gb: float
    mae: float
    sr: float
    created_days_ago: int     # days since creation
    storage_tier: str
    is_production: bool
    is_best_mae: bool
    is_milestone: bool        # every 1000 steps, first/last of each run
    monthly_cost: float       # $/month at current tier
    action: str               # keep / archive / delete / promote


@dataclass
class StorageReport:
    total_checkpoints: int
    total_size_gb: float
    total_monthly_cost: float
    optimized_monthly_cost: float
    savings_pct: float
    checkpoints_to_delete: int
    checkpoints_to_archive: int
    kept_checkpoints: int
    records: list[CheckpointRecord] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

RUNS = [
    # (run_id, n_checkpoints, best_mae, best_sr, days_ago_start)
    ("dagger_run9",  10, 0.016, 0.78, 5),
    ("dagger_run8",   8, 0.021, 0.68, 18),
    ("dagger_run7",   6, 0.028, 0.55, 35),
    ("dagger_run6",   8, 0.035, 0.42, 52),
    ("dagger_run5",   5, 0.041, 0.31, 70),
    ("bc_1000demo",   4, 0.103, 0.05, 95),
    ("bc_500demo",    3, 0.145, 0.05, 120),
]

RETENTION_POLICY = {
    "keep_production": True,
    "keep_best_mae": True,
    "keep_milestones": True,   # every 1000 steps
    "keep_last_n_runs_full": 2,
    "archive_after_days": 30,
    "deep_archive_after_days": 90,
    "delete_after_days": 180,
    "max_hot_gb": 20.0,
}


def simulate_storage(seed: int = 42) -> StorageReport:
    rng = random.Random(seed)
    records = []
    best_mae_seen = float("inf")
    production_run = "dagger_run9"

    for run_idx, (run_id, n_ckpts, best_mae, best_sr, days_start) in enumerate(RUNS):
        run_best_step = n_ckpts * 500  # best checkpoint step

        for ckpt_i in range(n_ckpts):
            step = (ckpt_i + 1) * 500
            days_ago = days_start + (n_ckpts - ckpt_i) * 1

            # Size: roughly 2.9GB per checkpoint, slight variation
            size = 2.9 + rng.gauss(0, 0.1)

            # MAE and SR (improving toward end of run)
            progress = (ckpt_i + 1) / n_ckpts
            mae = best_mae * (1 + (1 - progress) * 2) + rng.gauss(0, 0.002)
            sr  = best_sr  * progress * 0.9 + rng.gauss(0, 0.02)

            is_prod = (run_id == production_run and ckpt_i == n_ckpts - 1)
            is_best = (mae < best_mae_seen)
            if is_best:
                best_mae_seen = mae
            is_milestone = (step % 1000 == 0 or ckpt_i == 0 or ckpt_i == n_ckpts - 1)

            # Determine current tier
            if days_ago <= 7:
                tier = "hot_standard"
            elif days_ago <= 30:
                tier = "infrequent"
            elif days_ago <= 90:
                tier = "archive"
            else:
                tier = "deep_archive"

            tier_cost = next(c for n, c, _, _ in STORAGE_TIERS if n == tier)
            monthly_cost = size * tier_cost

            # Determine recommended action
            if is_prod or is_best:
                action = "keep"
            elif run_idx < RETENTION_POLICY["keep_last_n_runs_full"]:
                action = "keep"
            elif is_milestone and days_ago <= 90:
                action = "archive"
            elif days_ago > RETENTION_POLICY["delete_after_days"]:
                action = "delete"
            elif days_ago > RETENTION_POLICY["deep_archive_after_days"]:
                action = "deep_archive"
            elif days_ago > RETENTION_POLICY["archive_after_days"]:
                action = "archive"
            else:
                action = "keep"

            records.append(CheckpointRecord(
                run_id=run_id, step=step, size_gb=round(size, 2),
                mae=round(mae, 4), sr=round(sr, 4),
                created_days_ago=days_ago, storage_tier=tier,
                is_production=is_prod, is_best_mae=is_best,
                is_milestone=is_milestone,
                monthly_cost=round(monthly_cost, 4),
                action=action,
            ))

    # Cost analysis
    total_cost = sum(r.monthly_cost for r in records)
    opt_cost = sum(
        r.size_gb * next(c for n, c, _, _ in STORAGE_TIERS
                         if n == ("deep_archive" if r.action == "deep_archive"
                                  else "archive" if r.action == "archive"
                                  else r.storage_tier))
        for r in records if r.action != "delete"
    )
    savings = (total_cost - opt_cost) / max(total_cost, 1e-9)

    return StorageReport(
        total_checkpoints=len(records),
        total_size_gb=round(sum(r.size_gb for r in records), 1),
        total_monthly_cost=round(total_cost, 2),
        optimized_monthly_cost=round(opt_cost, 2),
        savings_pct=round(savings * 100, 1),
        checkpoints_to_delete=sum(1 for r in records if r.action == "delete"),
        checkpoints_to_archive=sum(1 for r in records if r.action in ("archive", "deep_archive")),
        kept_checkpoints=sum(1 for r in records if r.action == "keep"),
        records=records,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(report: StorageReport) -> str:
    records = report.records

    # SVG: storage breakdown by tier (pie-ish → use bar)
    tier_gb: dict[str, float] = {}
    for r in records:
        tier_gb[r.storage_tier] = tier_gb.get(r.storage_tier, 0) + r.size_gb

    TIER_COLORS = {"hot_standard": "#C74634", "infrequent": "#f59e0b",
                   "archive": "#3b82f6", "deep_archive": "#64748b"}

    bw, bh = 420, 120
    total_gb = sum(tier_gb.values()) or 1
    svg_tier = f'<svg width="{bw}" height="{bh}" style="background:#0f172a;border-radius:8px">'
    x = 10
    bar_h = 40
    y = 30

    for tier_name, gb in tier_gb.items():
        bar_w = gb / total_gb * (bw - 20)
        col = TIER_COLORS.get(tier_name, "#64748b")
        svg_tier += (f'<rect x="{x:.1f}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        if bar_w > 30:
            svg_tier += (f'<text x="{x+bar_w/2:.1f}" y="{y+bar_h/2+4}" fill="#1e293b" '
                         f'font-size="9" text-anchor="middle" font-weight="bold">'
                         f'{gb:.1f}GB</text>')
        x += bar_w + 2

    # Legend
    lx = 10
    for tier_name, _ in tier_gb.items():
        col = TIER_COLORS.get(tier_name, "#64748b")
        svg_tier += (f'<rect x="{lx}" y="{y+bar_h+8}" width="8" height="8" fill="{col}"/>'
                     f'<text x="{lx+11}" y="{y+bar_h+16}" fill="#94a3b8" font-size="8.5">'
                     f'{tier_name.replace("_"," ")}</text>')
        lx += 110

    svg_tier += '</svg>'

    # Per-run summary table
    run_rows = ""
    for run_id, n_ckpts, _, _, days_start in RUNS:
        run_records = [r for r in records if r.run_id == run_id]
        run_gb = sum(r.size_gb for r in run_records)
        run_cost = sum(r.monthly_cost for r in run_records)
        keep_n  = sum(1 for r in run_records if r.action == "keep")
        del_n   = sum(1 for r in run_records if r.action == "delete")
        arch_n  = sum(1 for r in run_records if r.action in ("archive", "deep_archive"))
        age_col = "#ef4444" if days_start > 90 else "#f59e0b" if days_start > 30 else "#22c55e"
        run_rows += (f'<tr>'
                     f'<td style="color:#e2e8f0">{run_id}</td>'
                     f'<td style="color:{age_col}">{days_start}d ago</td>'
                     f'<td style="color:#94a3b8">{len(run_records)}</td>'
                     f'<td style="color:#f59e0b">{run_gb:.1f}GB</td>'
                     f'<td style="color:#64748b">${run_cost:.2f}/mo</td>'
                     f'<td style="color:#22c55e">{keep_n}</td>'
                     f'<td style="color:#3b82f6">{arch_n}</td>'
                     f'<td style="color:#ef4444">{del_n}</td>'
                     f'</tr>')

    # Checkpoint detail rows (top 15 most recent)
    ckpt_rows = ""
    for r in sorted(records, key=lambda r: r.created_days_ago)[:15]:
        act_col = {"keep": "#22c55e", "archive": "#3b82f6",
                   "deep_archive": "#64748b", "delete": "#ef4444"}.get(r.action, "#94a3b8")
        flags = []
        if r.is_production: flags.append("PROD")
        if r.is_best_mae:   flags.append("BEST")
        if r.is_milestone:  flags.append("★")
        ckpt_rows += (f'<tr>'
                      f'<td style="color:#94a3b8">{r.run_id}</td>'
                      f'<td style="color:#64748b">{r.step:,}</td>'
                      f'<td style="color:#e2e8f0">{r.mae:.4f}</td>'
                      f'<td style="color:#94a3b8">{r.sr*100:.0f}%</td>'
                      f'<td style="color:#64748b">{r.size_gb:.1f}GB</td>'
                      f'<td style="color:#64748b">{r.created_days_ago}d</td>'
                      f'<td style="color:#94a3b8">{r.storage_tier.replace("_"," ")}</td>'
                      f'<td style="color:#64748b">${r.monthly_cost:.4f}</td>'
                      f'<td style="color:#22c55e;font-size:9px">{" ".join(flags)}</td>'
                      f'<td style="color:{act_col};font-weight:bold">{r.action.upper()}</td>'
                      f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Checkpoint Storage Manager</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:24px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:20px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Checkpoint Storage Manager</h1>
<div class="meta">
  {len(RUNS)} training runs · {report.total_checkpoints} checkpoints ·
  {report.total_size_gb:.1f}GB total
</div>

<div class="grid">
  <div class="card"><h3>Current Cost</h3>
    <div class="big" style="color:#f59e0b">${report.total_monthly_cost:.2f}/mo</div>
  </div>
  <div class="card"><h3>Optimized Cost</h3>
    <div class="big" style="color:#22c55e">${report.optimized_monthly_cost:.2f}/mo</div>
    <div style="color:#64748b;font-size:10px">{report.savings_pct:.0f}% savings</div>
  </div>
  <div class="card"><h3>To Delete</h3>
    <div class="big" style="color:#ef4444">{report.checkpoints_to_delete}</div>
    <div style="color:#64748b;font-size:10px">checkpoints</div>
  </div>
  <div class="card"><h3>To Archive</h3>
    <div class="big" style="color:#3b82f6">{report.checkpoints_to_archive}</div>
    <div style="color:#64748b;font-size:10px">move to colder tier</div>
  </div>
</div>

<h3 class="sec">Storage by Tier</h3>
{svg_tier}
<div style="color:#64748b;font-size:10px;margin-top:4px;margin-bottom:20px">
  Hot $0.0255/GB·mo · Infrequent $0.0102 · Archive $0.0026 · Deep Archive $0.0009
</div>

<h3 class="sec">Per-Run Summary</h3>
<table>
  <tr><th>Run</th><th>Age</th><th>Checkpoints</th><th>Size</th><th>Cost/mo</th>
      <th>Keep</th><th>Archive</th><th>Delete</th></tr>
  {run_rows}
</table>

<h3 class="sec">Recent Checkpoints (last 15)</h3>
<table>
  <tr><th>Run</th><th>Step</th><th>MAE</th><th>SR</th><th>Size</th>
      <th>Age</th><th>Tier</th><th>Cost/mo</th><th>Flags</th><th>Action</th></tr>
  {ckpt_rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:8px">
  Policy: keep production + best_mae + last 2 runs full; archive milestones ≤90d; delete &gt;180d.<br>
  Optimized: move {report.checkpoints_to_archive} to colder tiers, delete {report.checkpoints_to_delete} old → save {report.savings_pct:.0f}% storage cost.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Checkpoint storage lifecycle manager")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/checkpoint_storage_manager.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[storage-mgr] {len(RUNS)} runs · analyzing checkpoints...")
    t0 = time.time()

    report = simulate_storage(args.seed)

    print(f"\n  Total: {report.total_checkpoints} checkpoints · {report.total_size_gb:.1f}GB · "
          f"${report.total_monthly_cost:.2f}/mo")
    print(f"  Optimized: ${report.optimized_monthly_cost:.2f}/mo ({report.savings_pct:.0f}% savings)")
    print(f"  Actions: keep={report.kept_checkpoints} archive={report.checkpoints_to_archive} "
          f"delete={report.checkpoints_to_delete}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_checkpoints": report.total_checkpoints,
        "total_size_gb": report.total_size_gb,
        "total_monthly_cost": report.total_monthly_cost,
        "optimized_monthly_cost": report.optimized_monthly_cost,
        "savings_pct": report.savings_pct,
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
