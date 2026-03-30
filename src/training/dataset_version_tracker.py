#!/usr/bin/env python3
"""
dataset_version_tracker.py — Versioned dataset lineage tracker for GR00T fine-tuning.

Tracks dataset provenance across DAgger iterations, synthetic SDG batches, and quality
filtering passes. Enables reproducible training by pinning exact dataset versions used
for paper submissions and GTC demos.

Usage:
    python src/training/dataset_version_tracker.py --mock
    python src/training/dataset_version_tracker.py --mock --output /tmp/dataset_version_tracker.html
    python src/training/dataset_version_tracker.py --mock --seed 123
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class DatasetVersion:
    version_id: str          # e.g. "v1.0", "v2.2"
    parent_id: Optional[str] # lineage pointer (None for root)
    source: str              # initial_bc / dagger_run1..N / synthetic_sdg / augmented / quality_filter
    n_episodes: int
    n_frames: int
    size_mb: float
    tasks: List[str]
    created_at: datetime
    quality_score: float     # avg from quality_scorer, 0-1
    dedup_removed: int       # episodes removed by deduplication
    status: str              # active / archived / pinned
    training_runs: List[str] = field(default_factory=list)  # run_ids that used this version

    def episodes_added(self, versions: List["DatasetVersion"]) -> int:
        """Net episodes added vs parent."""
        if self.parent_id is None:
            return self.n_episodes
        parent = next((v for v in versions if v.version_id == self.parent_id), None)
        if parent is None:
            return self.n_episodes
        return self.n_episodes - parent.n_episodes


# ── Mock data generation ───────────────────────────────────────────────────────

def generate_version_history(n: int = 12, seed: int = 42) -> List[DatasetVersion]:
    """Generate a realistic 12-version dataset lineage."""
    random.seed(seed)

    base_date = datetime(2025, 10, 1, 9, 0, 0)

    def dt(days: float) -> datetime:
        return base_date + timedelta(days=days)

    TASKS_PICK_PLACE = ["pick_and_place", "cube_stack"]
    TASKS_FULL = ["pick_and_place", "cube_stack", "drawer_open", "peg_insert"]

    versions = [
        DatasetVersion(
            version_id="v1.0",
            parent_id=None,
            source="initial_bc",
            n_episodes=100,
            n_frames=48200,
            size_mb=1840.0,
            tasks=TASKS_PICK_PLACE,
            created_at=dt(0),
            quality_score=0.61,
            dedup_removed=0,
            status="archived",
            training_runs=["run-bc-001"],
        ),
        DatasetVersion(
            version_id="v1.1",
            parent_id="v1.0",
            source="dagger_run1",
            n_episodes=142,
            n_frames=68450,
            size_mb=2612.0,
            tasks=TASKS_PICK_PLACE,
            created_at=dt(6),
            quality_score=0.64,
            dedup_removed=8,
            status="archived",
            training_runs=["run-dagger-001"],
        ),
        DatasetVersion(
            version_id="v1.2",
            parent_id="v1.1",
            source="dagger_run2",
            n_episodes=213,
            n_frames=102500,
            size_mb=3912.0,
            tasks=TASKS_PICK_PLACE,
            created_at=dt(14),
            quality_score=0.67,
            dedup_removed=4,
            status="archived",
            training_runs=["run-dagger-002"],
        ),
        DatasetVersion(
            version_id="v1.3",
            parent_id="v1.2",
            source="dagger_run3",
            n_episodes=278,
            n_frames=133700,
            size_mb=5102.0,
            tasks=TASKS_PICK_PLACE,
            created_at=dt(22),
            quality_score=0.70,
            dedup_removed=10,
            status="archived",
            training_runs=["run-dagger-003", "run-eval-103"],
        ),
        DatasetVersion(
            version_id="v2.0",
            parent_id="v1.3",
            source="synthetic_sdg",
            n_episodes=478,
            n_frames=230100,
            size_mb=8780.0,
            tasks=TASKS_FULL,
            created_at=dt(35),
            quality_score=0.72,
            dedup_removed=0,
            status="archived",
            training_runs=["run-sdg-001"],
        ),
        DatasetVersion(
            version_id="v2.1",
            parent_id="v2.0",
            source="quality_filter",
            n_episodes=455,
            n_frames=218800,
            size_mb=8355.0,
            tasks=TASKS_FULL,
            created_at=dt(37),
            quality_score=0.76,
            dedup_removed=23,
            status="archived",
            training_runs=["run-qf-001", "run-eval-201"],
        ),
        DatasetVersion(
            version_id="v2.2",
            parent_id="v2.1",
            source="dagger_run5",
            n_episodes=551,
            n_frames=264900,
            size_mb=10116.0,
            tasks=TASKS_FULL,
            created_at=dt(48),
            quality_score=0.79,
            dedup_removed=4,
            status="pinned",
            training_runs=["run-dagger-005", "run-corl-paper-v1"],
        ),
        DatasetVersion(
            version_id="v2.3",
            parent_id="v2.2",
            source="augmented",
            n_episodes=638,
            n_frames=306700,
            size_mb=11702.0,
            tasks=TASKS_FULL,
            created_at=dt(57),
            quality_score=0.80,
            dedup_removed=13,
            status="archived",
            training_runs=["run-aug-001"],
        ),
        DatasetVersion(
            version_id="v2.4",
            parent_id="v2.3",
            source="dagger_run6",
            n_episodes=714,
            n_frames=342900,
            size_mb=13088.0,
            tasks=TASKS_FULL,
            created_at=dt(66),
            quality_score=0.82,
            dedup_removed=11,
            status="pinned",
            training_runs=["run-dagger-006", "run-gtc-demo-2026"],
        ),
        DatasetVersion(
            version_id="v3.0",
            parent_id="v2.4",
            source="synthetic_sdg",
            n_episodes=964,
            n_frames=463200,
            size_mb=17684.0,
            tasks=TASKS_FULL + ["sweep", "sort_objects"],
            created_at=dt(82),
            quality_score=0.83,
            dedup_removed=0,
            status="archived",
            training_runs=["run-sdg-002"],
        ),
        DatasetVersion(
            version_id="v3.1",
            parent_id="v3.0",
            source="dagger_run7",
            n_episodes=1042,
            n_frames=500350,
            size_mb=19082.0,
            tasks=TASKS_FULL + ["sweep", "sort_objects"],
            created_at=dt(92),
            quality_score=0.86,
            dedup_removed=16,
            status="active",
            training_runs=["run-dagger-007"],
        ),
        DatasetVersion(
            version_id="v3.2",
            parent_id="v3.1",
            source="dagger_run8",
            n_episodes=1138,
            n_frames=546650,
            size_mb=20876.0,
            tasks=TASKS_FULL + ["sweep", "sort_objects"],
            created_at=dt(103),
            quality_score=0.88,
            dedup_removed=6,
            status="active",
            training_runs=["run-dagger-008"],
        ),
    ]

    return versions[:n]


# ── Analytics ─────────────────────────────────────────────────────────────────

def compute_lineage_stats(versions: List[DatasetVersion]) -> dict:
    """Aggregate statistics across all dataset versions."""
    if not versions:
        return {}

    latest = max(versions, key=lambda v: v.created_at)
    total_dedup = sum(v.dedup_removed for v in versions)

    source_eps: dict = {}
    for v in versions:
        cat = v.source if v.source in ("initial_bc", "synthetic_sdg", "augmented") else "dagger"
        added = v.episodes_added(versions)
        source_eps[cat] = source_eps.get(cat, 0) + max(added, 0)

    total_src = sum(source_eps.values()) or 1
    source_pct = {k: round(100 * val / total_src, 1) for k, val in source_eps.items()}

    quality_trend = [v.quality_score for v in sorted(versions, key=lambda v: v.created_at)]
    quality_delta = quality_trend[-1] - quality_trend[0] if len(quality_trend) > 1 else 0.0

    return {
        "total_versions": len(versions),
        "latest_episodes": latest.n_episodes,
        "latest_version_id": latest.version_id,
        "total_dedup_removed": total_dedup,
        "quality_start": round(quality_trend[0], 3),
        "quality_end": round(quality_trend[-1], 3),
        "quality_delta": round(quality_delta, 3),
        "source_breakdown_pct": source_pct,
        "growth_factor": round(latest.n_episodes / versions[0].n_episodes, 2),
        "total_size_mb": round(latest.size_mb, 1),
    }


def find_pinned_versions(versions: List[DatasetVersion]) -> List[DatasetVersion]:
    """Return all versions marked as pinned (paper/GTC)."""
    return [v for v in versions if v.status == "pinned"]


# ── SVG charts ────────────────────────────────────────────────────────────────

def _svg_stacked_area(versions: List[DatasetVersion]) -> str:
    """Stacked area chart: BC base / DAgger additions / synthetic additions."""
    sorted_v = sorted(versions, key=lambda v: v.created_at)
    n = len(sorted_v)
    W, H = 680, 240
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40

    # Compute stacked episode counts per version
    bc_base: List[float] = []
    dagger_cum: List[float] = []
    synth_cum: List[float] = []
    aug_cum: List[float] = []

    running = {"initial_bc": 0.0, "dagger": 0.0, "synthetic_sdg": 0.0, "augmented": 0.0}
    for v in sorted_v:
        added = max(v.episodes_added(versions), 0)
        src = v.source if v.source in ("initial_bc", "synthetic_sdg", "augmented") else "dagger"
        running[src] += added
        bc_base.append(running["initial_bc"])
        dagger_cum.append(running["dagger"])
        synth_cum.append(running["synthetic_sdg"])
        aug_cum.append(running["augmented"])

    max_eps = max(bc_base[i] + dagger_cum[i] + synth_cum[i] + aug_cum[i] for i in range(n))

    def x(i: int) -> float:
        return pad_l + (i / max(n - 1, 1)) * (W - pad_l - pad_r)

    def y(val: float) -> float:
        return pad_t + H - pad_b - (val / max_eps) * (H - pad_t - pad_b)

    def area_points(bottoms: List[float], tops: List[float]) -> str:
        fwd = " ".join(f"{x(i):.1f},{y(tops[i]):.1f}" for i in range(n))
        bwd = " ".join(f"{x(i):.1f},{y(bottoms[i]):.1f}" for i in range(n - 1, -1, -1))
        return fwd + " " + bwd

    zeros = [0.0] * n
    b1 = [bc_base[i] for i in range(n)]
    b2 = [bc_base[i] + dagger_cum[i] for i in range(n)]
    b3 = [b2[i] + synth_cum[i] for i in range(n)]
    b4 = [b3[i] + aug_cum[i] for i in range(n)]

    # Y axis ticks
    tick_count = 5
    y_ticks = [int(max_eps * i / tick_count) for i in range(tick_count + 1)]
    ticks_svg = ""
    for t in y_ticks:
        yp = y(t)
        ticks_svg += f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{W - pad_r}" y2="{yp:.1f}" stroke="#334155" stroke-width="1"/>'
        ticks_svg += f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{t}</text>'

    # X axis labels (version IDs)
    x_labels = ""
    for i, v in enumerate(sorted_v):
        xp = x(i)
        x_labels += f'<text x="{xp:.1f}" y="{H - 2}" fill="#94a3b8" font-size="9" text-anchor="middle">{v.version_id}</text>'

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">
  {ticks_svg}
  <polygon points="{area_points(zeros, b1)}" fill="#3b82f6" opacity="0.75"/>
  <polygon points="{area_points(b1, b2)}" fill="#C74634" opacity="0.75"/>
  <polygon points="{area_points(b2, b3)}" fill="#10b981" opacity="0.75"/>
  <polygon points="{area_points(b3, b4)}" fill="#f59e0b" opacity="0.75"/>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H - pad_b}" stroke="#475569" stroke-width="1.5"/>
  <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - pad_r}" y2="{H - pad_b}" stroke="#475569" stroke-width="1.5"/>
  {x_labels}
  <circle cx="30" cy="12" r="6" fill="#3b82f6" opacity="0.85"/>
  <text x="40" y="16" fill="#94a3b8" font-size="10">BC base</text>
  <circle cx="105" cy="12" r="6" fill="#C74634" opacity="0.85"/>
  <text x="115" y="16" fill="#94a3b8" font-size="10">DAgger</text>
  <circle cx="180" cy="12" r="6" fill="#10b981" opacity="0.85"/>
  <text x="190" y="16" fill="#94a3b8" font-size="10">Synthetic SDG</text>
  <circle cx="285" cy="12" r="6" fill="#f59e0b" opacity="0.85"/>
  <text x="295" y="16" fill="#94a3b8" font-size="10">Augmented</text>
</svg>"""


def _svg_quality_trend(versions: List[DatasetVersion]) -> str:
    """Line chart of quality score across versions."""
    sorted_v = sorted(versions, key=lambda v: v.created_at)
    n = len(sorted_v)
    W, H = 680, 180
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 35

    q_min, q_max = 0.55, 1.0
    scores = [v.quality_score for v in sorted_v]

    def x(i: int) -> float:
        return pad_l + (i / max(n - 1, 1)) * (W - pad_l - pad_r)

    def y(val: float) -> float:
        return pad_t + (H - pad_t - pad_b) * (1 - (val - q_min) / (q_max - q_min))

    polyline = " ".join(f"{x(i):.1f},{y(scores[i]):.1f}" for i in range(n))
    area_pts = polyline + f" {x(n-1):.1f},{H - pad_b} {x(0):.1f},{H - pad_b}"

    dots = ""
    for i, v in enumerate(sorted_v):
        color = "#f59e0b" if v.status == "pinned" else "#C74634"
        dots += f'<circle cx="{x(i):.1f}" cy="{y(scores[i]):.1f}" r="5" fill="{color}" stroke="#1e293b" stroke-width="1.5"/>'

    ticks_svg = ""
    for t in [0.60, 0.70, 0.80, 0.90]:
        yp = y(t)
        ticks_svg += f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{W - pad_r}" y2="{yp:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
        ticks_svg += f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{t:.2f}</text>'

    x_labels = ""
    for i, v in enumerate(sorted_v):
        x_labels += f'<text x="{x(i):.1f}" y="{H - 4}" fill="#94a3b8" font-size="9" text-anchor="middle">{v.version_id}</text>'

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">
  {ticks_svg}
  <polygon points="{area_pts}" fill="#C74634" opacity="0.15"/>
  <polyline points="{polyline}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>
  {dots}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H - pad_b}" stroke="#475569" stroke-width="1.5"/>
  <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - pad_r}" y2="{H - pad_b}" stroke="#475569" stroke-width="1.5"/>
  {x_labels}
  <circle cx="30" cy="12" r="5" fill="#f59e0b"/>
  <text x="40" y="16" fill="#94a3b8" font-size="10">Pinned version</text>
  <circle cx="140" cy="12" r="5" fill="#C74634"/>
  <text x="150" y="16" fill="#94a3b8" font-size="10">Standard version</text>
</svg>"""


# ── HTML report ───────────────────────────────────────────────────────────────

def _source_bars_html(source_pct: dict) -> str:
    color_map = {
        "initial_bc": "#3b82f6",
        "dagger": "#C74634",
        "synthetic_sdg": "#10b981",
        "augmented": "#f59e0b",
        "quality_filter": "#8b5cf6",
    }
    rows = ""
    for src, pct in sorted(source_pct.items(), key=lambda x: -x[1]):
        color = color_map.get(src, "#64748b")
        label = src.replace("_", " ").title()
        rows += f"""
        <div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="color:#cbd5e1;font-size:13px">{label}</span>
            <span style="color:#94a3b8;font-size:13px">{pct}%</span>
          </div>
          <div style="background:#334155;border-radius:4px;height:10px;overflow:hidden">
            <div style="background:{color};width:{pct}%;height:100%;border-radius:4px;opacity:0.85"></div>
          </div>
        </div>"""
    return rows


def _status_badge(status: str) -> str:
    colors = {
        "pinned": ("#f59e0b", "#1c1008"),
        "active": ("#10b981", "#051a12"),
        "archived": ("#64748b", "#0f172a"),
    }
    bg, fg = colors.get(status, ("#64748b", "#0f172a"))
    return f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{status.upper()}</span>'


def generate_html_report(versions: List[DatasetVersion]) -> str:
    stats = compute_lineage_stats(versions)
    pinned = find_pinned_versions(versions)
    sorted_v = sorted(versions, key=lambda v: v.created_at)

    # KPI cards
    kpi_cards = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px">
      <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px;text-align:center">
        <div style="color:#C74634;font-size:32px;font-weight:700">{stats['total_versions']}</div>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px">Total Versions</div>
      </div>
      <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px;text-align:center">
        <div style="color:#C74634;font-size:32px;font-weight:700">{stats['latest_episodes']:,}</div>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px">Current Episodes ({stats['latest_version_id']})</div>
      </div>
      <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px;text-align:center">
        <div style="color:#C74634;font-size:32px;font-weight:700">{stats['total_dedup_removed']}</div>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px">Total Dedup Removed</div>
      </div>
      <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px;text-align:center">
        <div style="color:#C74634;font-size:32px;font-weight:700">{stats['quality_start']:.2f} → {stats['quality_end']:.2f}</div>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px">Quality Score Trend (+{stats['quality_delta']:.3f})</div>
      </div>
    </div>"""

    # Version table rows
    table_rows = ""
    for v in sorted_v:
        added = v.episodes_added(versions)
        added_str = f"+{added}" if added >= 0 else str(added)
        parent_str = v.parent_id if v.parent_id else "—"
        runs_str = ", ".join(v.training_runs[:2]) + ("…" if len(v.training_runs) > 2 else "")
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e3a4a">
          <td style="padding:10px 12px;color:#e2e8f0;font-weight:600">{v.version_id}</td>
          <td style="padding:10px 12px;color:#94a3b8">{parent_str}</td>
          <td style="padding:10px 12px;color:#94a3b8">{v.source.replace('_',' ')}</td>
          <td style="padding:10px 12px;color:#e2e8f0;text-align:right">{v.n_episodes:,}</td>
          <td style="padding:10px 12px;color:#64748b;text-align:right;font-size:12px">{added_str}</td>
          <td style="padding:10px 12px;color:#e2e8f0;text-align:right">{v.quality_score:.3f}</td>
          <td style="padding:10px 12px;color:#64748b;text-align:right">{v.dedup_removed}</td>
          <td style="padding:10px 12px;color:#64748b;font-size:11px">{v.size_mb:,.0f} MB</td>
          <td style="padding:10px 12px">{_status_badge(v.status)}</td>
          <td style="padding:10px 12px;color:#64748b;font-size:11px">{runs_str}</td>
        </tr>"""

    pinned_info = " | ".join(
        f"{v.version_id} ({', '.join(v.training_runs)})" for v in pinned
    )

    stacked_svg = _svg_stacked_area(versions)
    quality_svg = _svg_quality_trend(versions)
    source_bars = _source_bars_html(stats["source_breakdown_pct"])
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Dataset Version Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ background:#1e293b; color:#e2e8f0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:32px }}
  h1 {{ color:#C74634; font-size:26px; font-weight:700; margin-bottom:6px }}
  h2 {{ color:#C74634; font-size:17px; font-weight:600; margin-bottom:16px; padding-bottom:8px; border-bottom:1px solid #334155 }}
  .section {{ background:#162032; border:1px solid #253347; border-radius:10px; padding:24px; margin-bottom:24px }}
  table {{ width:100%; border-collapse:collapse }}
  thead th {{ background:#0f172a; padding:10px 12px; text-align:left; color:#94a3b8; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.05em }}
  tbody tr:hover {{ background:#0f1f30 }}
</style>
</head>
<body>
<div style="max-width:1100px;margin:0 auto">
  <h1>Dataset Version Tracker</h1>
  <p style="color:#64748b;font-size:13px;margin-bottom:28px">GR00T Fine-Tuning — Dataset Lineage &amp; Provenance &nbsp;|&nbsp; Generated {report_time}</p>

  {kpi_cards}

  <div class="section">
    <h2>Dataset Growth Over Versions</h2>
    {stacked_svg}
  </div>

  <div style="display:grid;grid-template-columns:2fr 1fr;gap:24px;margin-bottom:24px">
    <div class="section" style="margin-bottom:0">
      <h2>Quality Score Trend</h2>
      {quality_svg}
    </div>
    <div class="section" style="margin-bottom:0">
      <h2>Episode Source Breakdown</h2>
      {source_bars}
      <p style="color:#475569;font-size:11px;margin-top:12px">Growth factor: {stats['growth_factor']}× from v1.0 to {stats['latest_version_id']}</p>
    </div>
  </div>

  <div class="section">
    <h2>Pinned Versions</h2>
    <p style="color:#cbd5e1;font-size:13px;background:#0f172a;padding:10px 14px;border-radius:6px;border-left:3px solid #f59e0b">
      {pinned_info if pinned_info else "No pinned versions found."}
    </p>
  </div>

  <div class="section">
    <h2>Version Lineage</h2>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Version</th><th>Parent</th><th>Source</th><th style="text-align:right">Episodes</th>
          <th style="text-align:right">Added</th><th style="text-align:right">Quality</th>
          <th style="text-align:right">Dedup−</th><th style="text-align:right">Size</th>
          <th>Status</th><th>Training Runs</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>
    </div>
  </div>

  <p style="color:#334155;font-size:11px;text-align:center;margin-top:16px">OCI Robot Cloud — Dataset Version Tracker v1.0 | Oracle Confidential</p>
</div>
</body>
</html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset version tracker for GR00T fine-tuning")
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    parser.add_argument("--output", default="/tmp/dataset_version_tracker.html", help="Output HTML path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--n", type=int, default=12, help="Number of versions to generate")
    args = parser.parse_args()

    if args.mock:
        versions = generate_version_history(n=args.n, seed=args.seed)
        stats = compute_lineage_stats(versions)
        pinned = find_pinned_versions(versions)

        print(f"[dataset_version_tracker] Generated {len(versions)} versions")
        print(f"  Latest : {stats['latest_version_id']} — {stats['latest_episodes']:,} episodes")
        print(f"  Growth : {stats['growth_factor']}× from v1.0")
        print(f"  Quality: {stats['quality_start']:.3f} → {stats['quality_end']:.3f} (+{stats['quality_delta']:.3f})")
        print(f"  Dedup  : {stats['total_dedup_removed']} episodes removed across all versions")
        print(f"  Pinned : {[v.version_id for v in pinned]}")
        print(f"  Sources: {stats['source_breakdown_pct']}")

        html = generate_html_report(versions)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"\n  Report written to: {args.output}")
    else:
        print("[dataset_version_tracker] No data source specified. Use --mock for demo mode.")
        print("  For live mode, integrate with dataset_versioning.py registry.")


if __name__ == "__main__":
    main()
