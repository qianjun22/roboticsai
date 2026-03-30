#!/usr/bin/env python3
"""
groot_version_manager.py — GR00T Model Version Manager for OCI Robot Cloud

Tracks checkpoints, lineage, A/B deployments, and rollback capability.

Usage:
    python groot_version_manager.py --mock --output /tmp/groot_version_manager.html --seed 42
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ModelVersion:
    version_id: str
    parent_id: Optional[str]
    algo: str                    # BC / DAgger / LoRA
    task: str
    checkpoint_step: int
    val_loss: float
    sr_eval: float               # 0.0–1.0 success rate
    created_at: datetime
    size_gb: float
    status: str                  # staging / production / archived / rollback
    tags: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class DeploymentRecord:
    deploy_id: str
    version_id: str
    customer: str
    deployed_at: datetime
    traffic_pct: float           # 0–100
    sr_observed: Optional[float]
    error_count: int
    active: bool


# ---------------------------------------------------------------------------
# Mock Data Generation
# ---------------------------------------------------------------------------

def generate_version_tree(n_versions: int = 18, seed: int = 42) -> List[ModelVersion]:
    rng = random.Random(seed)
    now = datetime(2026, 3, 29, 12, 0, 0)

    versions: List[ModelVersion] = []

    # Root — BC v1.0 in production
    root = ModelVersion(
        version_id="v1.0",
        parent_id=None,
        algo="BC",
        task="pick_and_place",
        checkpoint_step=1000,
        val_loss=0.312,
        sr_eval=0.05,
        created_at=now - timedelta(days=90),
        size_gb=6.7,
        status="archived",
        tags=["baseline", "bc-only"],
        notes="Initial BC baseline from LIBERO demos",
    )
    versions.append(root)

    # BC v1.1 — production root
    v11 = ModelVersion(
        version_id="v1.1",
        parent_id="v1.0",
        algo="BC",
        task="pick_and_place",
        checkpoint_step=2000,
        val_loss=0.241,
        sr_eval=0.10,
        created_at=now - timedelta(days=80),
        size_gb=6.7,
        status="archived",
        tags=["bc", "improved-demos"],
        notes="2000-step fine-tune; double the demos",
    )
    versions.append(v11)

    # DAgger branch from v1.1
    dagger_steps = [3000, 5000, 7000, 10000]
    dagger_sr    = [0.15, 0.25, 0.38, 0.52]
    dagger_loss  = [0.198, 0.143, 0.099, 0.071]
    prev_id = "v1.1"
    for i, (steps, sr, loss) in enumerate(zip(dagger_steps, dagger_sr, dagger_loss)):
        minor = i + 2
        vid = f"v1.{minor}"
        status = "archived" if minor < 5 else "archived"
        versions.append(ModelVersion(
            version_id=vid,
            parent_id=prev_id,
            algo="DAgger",
            task="pick_and_place",
            checkpoint_step=steps,
            val_loss=loss,
            sr_eval=sr,
            created_at=now - timedelta(days=70 - i * 8),
            size_gb=6.7 + rng.uniform(0, 0.3),
            status="archived",
            tags=["dagger", f"run{i+1}"],
            notes=f"DAgger iteration {i+1}",
        ))
        prev_id = vid

    # v2.0 — major DAgger branch, LoRA adapter layer, production
    v20 = ModelVersion(
        version_id="v2.0",
        parent_id="v1.5",
        algo="DAgger",
        task="pick_and_place",
        checkpoint_step=15000,
        val_loss=0.058,
        sr_eval=0.61,
        created_at=now - timedelta(days=38),
        size_gb=6.9,
        status="archived",
        tags=["dagger", "milestone"],
        notes="15k-step DAgger; first >60% SR",
    )
    versions.append(v20)

    # LoRA adapter from v2.0 — curriculum variant
    lora1 = ModelVersion(
        version_id="v2.1-lora",
        parent_id="v2.0",
        algo="LoRA",
        task="stack_blocks",
        checkpoint_step=5000,
        val_loss=0.072,
        sr_eval=0.48,
        created_at=now - timedelta(days=30),
        size_gb=0.4,
        status="archived",
        tags=["lora", "stack-blocks", "transfer"],
        notes="LoRA adapter for stack_blocks task; small delta",
    )
    versions.append(lora1)

    lora2 = ModelVersion(
        version_id="v2.2-lora",
        parent_id="v2.1-lora",
        algo="LoRA",
        task="stack_blocks",
        checkpoint_step=10000,
        val_loss=0.051,
        sr_eval=0.64,
        created_at=now - timedelta(days=22),
        size_gb=0.4,
        status="archived",
        tags=["lora", "stack-blocks"],
        notes="Extended LoRA training; matches DAgger full fine-tune",
    )
    versions.append(lora2)

    # v2.3 — currently in A/B production (50%)
    v23 = ModelVersion(
        version_id="v2.3",
        parent_id="v2.0",
        algo="DAgger",
        task="pick_and_place",
        checkpoint_step=20000,
        val_loss=0.044,
        sr_eval=0.72,
        created_at=now - timedelta(days=18),
        size_gb=7.1,
        status="production",
        tags=["production", "ab-control"],
        notes="Stable production: 72% SR. A/B control arm.",
    )
    versions.append(v23)

    # v2.4 — new A/B production candidate (50%)
    v24 = ModelVersion(
        version_id="v2.4",
        parent_id="v2.3",
        algo="DAgger",
        task="pick_and_place",
        checkpoint_step=25000,
        val_loss=0.038,
        sr_eval=0.79,
        created_at=now - timedelta(days=10),
        size_gb=7.1,
        status="production",
        tags=["production", "ab-treatment", "curriculum"],
        notes="Curriculum SDG + 5k extra DAgger steps. Best SR yet.",
    )
    versions.append(v24)

    # Staging candidates
    v25 = ModelVersion(
        version_id="v2.5",
        parent_id="v2.4",
        algo="DAgger",
        task="pick_and_place",
        checkpoint_step=30000,
        val_loss=0.031,
        sr_eval=0.83,
        created_at=now - timedelta(days=4),
        size_gb=7.2,
        status="staging",
        tags=["staging", "candidate"],
        notes="30k steps; eval pending deployment approval",
    )
    versions.append(v25)

    lora3 = ModelVersion(
        version_id="v2.5-lora-arm",
        parent_id="v2.4",
        algo="LoRA",
        task="arm_reach",
        checkpoint_step=8000,
        val_loss=0.040,
        sr_eval=0.76,
        created_at=now - timedelta(days=3),
        size_gb=0.5,
        status="staging",
        tags=["lora", "arm-reach", "new-task"],
        notes="LoRA for arm_reach task on Franka Emika",
    )
    versions.append(lora3)

    # Rollback marker — bad deployment that was rolled back
    v22_bad = ModelVersion(
        version_id="v2.2-bad",
        parent_id="v2.1-lora",
        algo="DAgger",
        task="pick_and_place",
        checkpoint_step=12000,
        val_loss=0.089,
        sr_eval=0.31,
        created_at=now - timedelta(days=25),
        size_gb=6.8,
        status="rollback",
        tags=["rollback", "regressed"],
        notes="Regression: low-quality DAgger demos caused SR drop. Rolled back.",
    )
    versions.append(v22_bad)

    # Curriculum variant in staging
    curric = ModelVersion(
        version_id="v2.6-curric",
        parent_id="v2.5",
        algo="BC",
        task="multi_task",
        checkpoint_step=35000,
        val_loss=0.028,
        sr_eval=0.86,
        created_at=now - timedelta(days=1),
        size_gb=7.4,
        status="staging",
        tags=["staging", "curriculum", "multi-task"],
        notes="Multi-task curriculum: pick+stack+reach. Experimental.",
    )
    versions.append(curric)

    # Fill remaining slots with archived BC experiments
    extras = [
        ("v1.1-bc-aug", "v1.1", "BC", "pick_and_place", 2500, 0.218, 0.12, 78, "archived", ["bc", "data-aug"]),
        ("v1.3-bc-lrwarm", "v1.2", "BC", "pick_and_place", 3500, 0.177, 0.18, 72, "archived", ["bc", "lr-warmup"]),
        ("v2.0-distill", "v2.0", "BC", "pick_and_place", 8000, 0.062, 0.58, 40, "archived", ["distillation"]),
        ("v2.3-lora-weld", "v2.3", "LoRA", "welding", 6000, 0.055, 0.69, 14, "staging", ["lora", "welding", "new-task"]),
        ("v2.4-rl", "v2.4", "DAgger", "pick_and_place", 28000, 0.035, 0.81, 7, "staging", ["rl-finetune", "experimental"]),
    ]
    for vid, par, algo, task, steps, loss, sr, days_ago, status, tags in extras:
        versions.append(ModelVersion(
            version_id=vid,
            parent_id=par,
            algo=algo,
            task=task,
            checkpoint_step=steps,
            val_loss=loss,
            sr_eval=sr,
            created_at=now - timedelta(days=days_ago),
            size_gb=rng.uniform(0.4, 7.5),
            status=status,
            tags=tags,
            notes="",
        ))

    # Trim to n_versions
    versions = sorted(versions, key=lambda v: v.created_at)[:n_versions]
    return versions


def generate_deployments(versions: List[ModelVersion], seed: int = 42) -> List[DeploymentRecord]:
    rng = random.Random(seed + 1)
    now = datetime(2026, 3, 29, 12, 0, 0)
    vid_map = {v.version_id: v for v in versions}
    records: List[DeploymentRecord] = []

    deploys = [
        ("dep-001", "v1.1",     "Boston Dynamics",    85, 0.09, 0,  False, 75),
        ("dep-002", "v2.0",     "Boston Dynamics",    85, 0.60, 2,  False, 35),
        ("dep-003", "v2.2-bad", "Agility Robotics",  100, 0.30, 18, False, 24),  # rolled back
        ("dep-004", "v2.3",     "Agility Robotics",   50, 0.71, 1,  True,  17),  # A/B control
        ("dep-005", "v2.4",     "Agility Robotics",   50, 0.78, 0,  True,  10),  # A/B treatment
        ("dep-006", "v2.3",     "Figure AI",         100, 0.74, 0,  True,  15),
        ("dep-007", "v2.4",     "Apptronik",         100, 0.80, 0,  True,   8),
        ("dep-008", "v2.5",     "Internal QA",       100, None,  0, True,   3),
    ]

    for dep_id, vid, customer, traffic, sr_obs, errs, active, days_ago in deploys:
        if vid not in vid_map:
            continue
        records.append(DeploymentRecord(
            deploy_id=dep_id,
            version_id=vid,
            customer=customer,
            deployed_at=now - timedelta(days=days_ago),
            traffic_pct=traffic,
            sr_observed=sr_obs,
            error_count=errs,
            active=active,
        ))

    return records


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_version_stats(versions: List[ModelVersion]) -> Dict:
    production = [v for v in versions if v.status == "production"]
    staging    = [v for v in versions if v.status == "staging"]
    all_sr     = [v.sr_eval for v in versions]
    best_sr    = max(all_sr) if all_sr else 0.0
    prod_sr    = sum(v.sr_eval for v in production) / len(production) if production else 0.0

    # Lineage depth: BFS
    children: Dict[str, List[str]] = {}
    id_map = {v.version_id: v for v in versions}
    for v in versions:
        if v.parent_id:
            children.setdefault(v.parent_id, []).append(v.version_id)

    def depth(vid: str) -> int:
        kids = children.get(vid, [])
        return 1 + max((depth(k) for k in kids), default=0)

    roots = [v for v in versions if v.parent_id is None]
    max_depth = max((depth(r.version_id) for r in roots), default=0)

    return {
        "total": len(versions),
        "production_count": len(production),
        "staging_count": len(staging),
        "archived_count": len([v for v in versions if v.status == "archived"]),
        "rollback_count": len([v for v in versions if v.status == "rollback"]),
        "best_sr": best_sr,
        "prod_sr": prod_sr,
        "lineage_depth": max_depth,
        "staging_candidates": [v.version_id for v in staging],
    }


# ---------------------------------------------------------------------------
# SVG Helpers
# ---------------------------------------------------------------------------

STATUS_COLOR = {
    "production": "#22c55e",
    "staging":    "#f59e0b",
    "archived":   "#64748b",
    "rollback":   "#ef4444",
}

ALGO_COLOR = {
    "BC":     "#60a5fa",
    "DAgger": "#a78bfa",
    "LoRA":   "#34d399",
}


def build_tree_svg(versions: List[ModelVersion]) -> str:
    id_map = {v.version_id: v for v in versions}
    children: Dict[str, List[str]] = {}
    roots = []
    for v in versions:
        if v.parent_id and v.parent_id in id_map:
            children.setdefault(v.parent_id, []).append(v.version_id)
        elif v.parent_id is None or v.parent_id not in id_map:
            roots.append(v.version_id)

    # Assign (col, row) positions via BFS
    pos: Dict[str, tuple] = {}
    col_counter: Dict[int, int] = {}

    def assign(vid: str, depth: int):
        col = col_counter.get(depth, 0)
        col_counter[depth] = col + 1
        pos[vid] = (depth, col)
        for child in children.get(vid, []):
            assign(child, depth + 1)

    for r in roots:
        assign(r, 0)

    max_depth = max(p[0] for p in pos.values()) if pos else 0
    max_col   = max(p[1] for p in pos.values()) if pos else 0

    W, H = 820, max(320, (max_col + 1) * 54 + 40)
    x_step = min(130, (W - 60) / (max_depth + 1)) if max_depth > 0 else 130

    def px(vid: str):
        d, c = pos[vid]
        return (30 + d * x_step, 30 + c * 52)

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append('<rect width="100%" height="100%" fill="#0f172a" rx="8"/>')

    # Draw edges
    for v in versions:
        if v.parent_id and v.parent_id in pos and v.version_id in pos:
            x1, y1 = px(v.parent_id)
            x2, y2 = px(v.version_id)
            lines.append(
                f'<line x1="{x1+48}" y1="{y1+14}" x2="{x2}" y2="{y2+14}" '
                f'stroke="#334155" stroke-width="1.5" stroke-dasharray="4,2"/>'
            )

    # Draw nodes
    for v in versions:
        if v.version_id not in pos:
            continue
        x, y = px(v.version_id)
        color = STATUS_COLOR.get(v.status, "#64748b")
        label = v.version_id
        sr_pct = f"{v.sr_eval*100:.0f}%"
        lines.append(
            f'<rect x="{x}" y="{y}" width="96" height="28" rx="5" '
            f'fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="1.5"/>'
        )
        lines.append(
            f'<text x="{x+48}" y="{y+12}" text-anchor="middle" '
            f'font-size="9" fill="{color}" font-family="monospace" font-weight="bold">{label}</text>'
        )
        lines.append(
            f'<text x="{x+48}" y="{y+23}" text-anchor="middle" '
            f'font-size="8" fill="#94a3b8" font-family="monospace">SR {sr_pct} · {v.algo}</text>'
        )

    # Legend
    lx, ly = 10, H - 26
    for i, (status, color) in enumerate(STATUS_COLOR.items()):
        ox = lx + i * 130
        lines.append(f'<rect x="{ox}" y="{ly}" width="10" height="10" rx="2" fill="{color}"/>')
        lines.append(
            f'<text x="{ox+14}" y="{ly+9}" font-size="9" fill="#94a3b8" font-family="sans-serif">{status}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def build_scatter_svg(versions: List[ModelVersion]) -> str:
    W, H, pad = 820, 300, 50
    inner_w, inner_h = W - pad * 2, H - pad * 2

    steps = [v.checkpoint_step for v in versions]
    losses = [v.val_loss for v in versions]
    min_s, max_s = min(steps), max(steps)
    min_l, max_l = min(losses), max(losses)
    rng_s = max_s - min_s or 1
    rng_l = max_l - min_l or 0.01

    def sx(s): return pad + (s - min_s) / rng_s * inner_w
    def sy(l): return pad + inner_h - (max_l - l) / rng_l * inner_h

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append('<rect width="100%" height="100%" fill="#0f172a" rx="8"/>')

    # Grid
    for i in range(5):
        gy = pad + i * inner_h // 4
        gx = pad + i * inner_w // 4
        lines.append(f'<line x1="{pad}" y1="{gy}" x2="{W-pad}" y2="{gy}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<line x1="{gx}" y1="{pad}" x2="{gx}" y2="{H-pad}" stroke="#1e293b" stroke-width="1"/>')

    # Axes
    lines.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<text x="{W//2}" y="{H-8}" text-anchor="middle" font-size="11" fill="#94a3b8" font-family="sans-serif">Checkpoint Step</text>')
    lines.append(f'<text x="12" y="{H//2}" text-anchor="middle" font-size="11" fill="#94a3b8" font-family="sans-serif" transform="rotate(-90,12,{H//2})">Val Loss</text>')

    # Points
    for v in versions:
        cx, cy = sx(v.checkpoint_step), sy(v.val_loss)
        color = ALGO_COLOR.get(v.algo, "#94a3b8")
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}" fill-opacity="0.85"/>')
        lines.append(
            f'<text x="{cx:.1f}" y="{cy-10:.1f}" text-anchor="middle" '
            f'font-size="8" fill="{color}" font-family="monospace">{v.version_id}</text>'
        )

    # Algo legend
    for i, (algo, color) in enumerate(ALGO_COLOR.items()):
        lx = pad + i * 120
        lines.append(f'<circle cx="{lx+5}" cy="14" r="5" fill="{color}"/>')
        lines.append(f'<text x="{lx+14}" y="18" font-size="10" fill="#94a3b8" font-family="sans-serif">{algo}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------

def render_html(versions: List[ModelVersion], deployments: List[DeploymentRecord]) -> str:
    stats = compute_version_stats(versions)
    tree_svg = build_tree_svg(versions)
    scatter_svg = build_scatter_svg(versions)

    def badge(status: str) -> str:
        color = STATUS_COLOR.get(status, "#64748b")
        return (f'<span style="background:{color}22;color:{color};border:1px solid {color}66;'
                f'padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{status}</span>')

    # Deployment table rows
    dep_rows = ""
    for d in deployments:
        sr_str = f"{d.sr_observed*100:.0f}%" if d.sr_observed is not None else "—"
        active_str = '<span style="color:#22c55e">●</span> active' if d.active else '<span style="color:#64748b">○</span> inactive'
        dep_rows += (
            f"<tr><td>{d.deploy_id}</td><td>{d.customer}</td><td><code>{d.version_id}</code></td>"
            f"<td>{d.traffic_pct:.0f}%</td><td>{sr_str}</td><td>{d.error_count}</td>"
            f"<td>{active_str}</td><td>{d.deployed_at.strftime('%Y-%m-%d')}</td></tr>\n"
        )

    # Version table rows
    sorted_versions = sorted(versions, key=lambda v: v.created_at)
    ver_rows = ""
    for v in sorted_versions:
        parent_str = v.parent_id or "—"
        tags_str = ", ".join(v.tags) if v.tags else "—"
        ver_rows += (
            f"<tr><td><code>{v.version_id}</code></td><td>{badge(v.status)}</td>"
            f"<td>{v.algo}</td><td>{v.task}</td><td>{v.checkpoint_step:,}</td>"
            f"<td>{v.val_loss:.3f}</td><td>{v.sr_eval*100:.0f}%</td>"
            f"<td><code style='color:#94a3b8;font-size:10px'>{parent_str}</code></td>"
            f"<td style='font-size:10px;color:#94a3b8'>{tags_str}</td>"
            f"<td>{v.created_at.strftime('%Y-%m-%d')}</td></tr>\n"
        )

    kpi_html = ""
    kpis = [
        ("Total Versions",      str(stats["total"]),               "#60a5fa"),
        ("In Production",       str(stats["production_count"]),    "#22c55e"),
        ("Best SR Ever",        f"{stats['best_sr']*100:.0f}%",    "#C74634"),
        ("Staging Candidates",  str(stats["staging_count"]),       "#f59e0b"),
    ]
    for label, value, color in kpis:
        kpi_html += (
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px 28px;'
            f'text-align:center;flex:1;min-width:160px">'
            f'<div style="font-size:32px;font-weight:700;color:{color}">{value}</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:4px">{label}</div></div>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>GR00T Version Manager — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 32px; }}
  h1 {{ color: #C74634; font-size: 24px; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 16px; margin: 28px 0 12px; letter-spacing: 0.5px; text-transform: uppercase; }}
  .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 28px; }}
  .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 24px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ color: #94a3b8; font-weight: 600; padding: 8px 12px; border-bottom: 1px solid #334155; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #1e293b; vertical-align: middle; }}
  tr:hover td {{ background: #0f172a44; }}
  code {{ color: #a78bfa; font-family: monospace; }}
  .footer {{ color: #334155; font-size: 11px; text-align: center; margin-top: 32px; }}
</style>
</head>
<body>
<h1>GR00T Model Version Manager</h1>
<div class="subtitle">OCI Robot Cloud · Checkpoint lineage, A/B deployments, rollback tracking · {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC</div>

<div class="kpi-row">
{kpi_html}
</div>

<h2>Version Lineage Tree</h2>
<div class="section">
{tree_svg}
</div>

<h2>Val Loss vs Checkpoint Step</h2>
<div class="section">
{scatter_svg}
</div>

<h2>Active Deployments</h2>
<div class="section">
<table>
<thead><tr>
  <th>Deploy ID</th><th>Customer</th><th>Version</th><th>Traffic %</th>
  <th>Observed SR</th><th>Errors</th><th>Status</th><th>Deployed</th>
</tr></thead>
<tbody>
{dep_rows}
</tbody>
</table>
</div>

<h2>All Model Versions</h2>
<div class="section">
<table>
<thead><tr>
  <th>Version</th><th>Status</th><th>Algo</th><th>Task</th>
  <th>Steps</th><th>Val Loss</th><th>SR</th>
  <th>Parent</th><th>Tags</th><th>Created</th>
</tr></thead>
<tbody>
{ver_rows}
</tbody>
</table>
</div>

<div class="footer">Generated by groot_version_manager.py · OCI Robot Cloud · Oracle Confidential</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GR00T Model Version Manager — OCI Robot Cloud")
    parser.add_argument("--mock", action="store_true", default=True, help="Use mock data (default)")
    parser.add_argument("--output", default="/tmp/groot_version_manager.html", help="Output HTML path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible mock data")
    parser.add_argument("--json", action="store_true", help="Also dump stats as JSON to stdout")
    args = parser.parse_args()

    print(f"[groot_version_manager] Generating mock version tree (seed={args.seed})...")
    versions    = generate_version_tree(n_versions=18, seed=args.seed)
    deployments = generate_deployments(versions, seed=args.seed)
    stats       = compute_version_stats(versions)

    print(f"  Versions   : {stats['total']} ({stats['production_count']} prod, {stats['staging_count']} staging, {stats['rollback_count']} rollback)")
    print(f"  Best SR    : {stats['best_sr']*100:.0f}%")
    print(f"  Prod SR    : {stats['prod_sr']*100:.0f}%")
    print(f"  Tree depth : {stats['lineage_depth']}")
    print(f"  Staging IDs: {', '.join(stats['staging_candidates'])}")

    if args.json:
        print(json.dumps(stats, indent=2, default=str))

    html = render_html(versions, deployments)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"[groot_version_manager] Report written → {args.output}")


if __name__ == "__main__":
    main()
