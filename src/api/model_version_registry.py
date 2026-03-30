#!/usr/bin/env python3
"""
model_version_registry.py — GR00T fine-tuned checkpoint version registry.

Tracks lineage, performance, deployment status, and rollback capability for
GR00T N1.6 fine-tuned model checkpoints on OCI Robot Cloud.

Usage:
    python model_version_registry.py --mock --output /tmp/model_version_registry.html --seed 42
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

VALID_STATUSES = {"staging", "production", "retired", "rollback"}


@dataclass
class ModelVersion:
    version_id: str
    parent_version: Optional[str]
    checkpoint_path: str
    created_at: str          # ISO-8601
    training_run: str
    n_demos: int
    n_steps: int
    mae: float
    sr: float                # success-rate 0-1
    latency_ms: float
    vram_gb: float
    tags: List[str] = field(default_factory=list)
    status: str = "staging"  # staging | production | retired | rollback

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeploymentEvent:
    timestamp: str
    version_id: str
    action: str              # promote | rollback | retire | stage
    triggered_by: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Registry core
# ---------------------------------------------------------------------------

class ModelVersionRegistry:
    """Central registry for GR00T fine-tuned checkpoint versions."""

    def __init__(self):
        self._versions: Dict[str, ModelVersion] = {}
        self._history: List[DeploymentEvent] = []

    # ------------------------------------------------------------------ CRUD

    def add_version(self, v: ModelVersion) -> None:
        if v.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v.status}'")
        if v.parent_version and v.parent_version not in self._versions:
            raise ValueError(f"Parent '{v.parent_version}' not found")
        self._versions[v.version_id] = v
        self._refresh_auto_tags()

    def get(self, version_id: str) -> ModelVersion:
        if version_id not in self._versions:
            raise KeyError(f"Version '{version_id}' not found")
        return self._versions[version_id]

    # ----------------------------------------------------------------- ops

    def promote(self, version_id: str, triggered_by: str = "system",
                reason: str = "") -> None:
        """Promote a version to production; demote current production."""
        target = self.get(version_id)
        # Demote existing production
        for vid, v in self._versions.items():
            if v.status == "production" and vid != version_id:
                v.status = "staging"
                self._record(vid, "demote", triggered_by,
                             f"superseded by {version_id}")
        target.status = "production"
        self._record(version_id, "promote", triggered_by, reason)
        self._refresh_auto_tags()

    def rollback(self, version_id: str, triggered_by: str = "system",
                 reason: str = "manual rollback") -> None:
        """Mark current production as rollback, reinstate a previous version."""
        # Mark current prod as rollback
        for vid, v in self._versions.items():
            if v.status == "production" and vid != version_id:
                v.status = "rollback"
                self._record(vid, "rollback", triggered_by,
                             f"rolled back; {version_id} reinstated")
        target = self.get(version_id)
        target.status = "production"
        self._record(version_id, "promote", triggered_by,
                     f"rollback reinstatement — {reason}")
        self._refresh_auto_tags()

    def retire(self, version_id: str, triggered_by: str = "system",
               reason: str = "") -> None:
        target = self.get(version_id)
        target.status = "retired"
        self._record(version_id, "retire", triggered_by, reason)
        self._refresh_auto_tags()

    def compare(self, vid1: str, vid2: str) -> dict:
        """Return a side-by-side comparison dict."""
        a, b = self.get(vid1), self.get(vid2)
        fields = ["mae", "sr", "latency_ms", "vram_gb",
                  "n_demos", "n_steps", "status"]
        result = {"versions": [vid1, vid2], "fields": {}}
        for f in fields:
            va, vb = getattr(a, f), getattr(b, f)
            if isinstance(va, float):
                delta = round(vb - va, 6)
                pct = round((delta / va * 100), 2) if va != 0 else None
            else:
                delta = pct = None
            result["fields"][f] = {
                vid1: va, vid2: vb, "delta": delta, "pct_change": pct
            }
        return result

    # ---------------------------------------------------------------- query

    def production_version(self) -> Optional[ModelVersion]:
        for v in self._versions.values():
            if v.status == "production":
                return v
        return None

    def lineage(self, version_id: str) -> List[str]:
        """Return ancestor chain from root to version_id."""
        chain = []
        cur = version_id
        while cur:
            chain.append(cur)
            parent = self._versions[cur].parent_version
            cur = parent
        chain.reverse()
        return chain

    def children(self, version_id: str) -> List[str]:
        return [vid for vid, v in self._versions.items()
                if v.parent_version == version_id]

    def all_versions(self) -> List[ModelVersion]:
        return list(self._versions.values())

    def deployment_history(self, limit: int = 10) -> List[DeploymentEvent]:
        return self._history[-limit:]

    def to_dict(self) -> dict:
        return {
            "versions": {vid: v.to_dict()
                         for vid, v in self._versions.items()},
            "deployment_history": [e.to_dict() for e in self._history],
        }

    # --------------------------------------------------------------- helpers

    def _record(self, version_id: str, action: str,
                triggered_by: str, reason: str) -> None:
        self._history.append(DeploymentEvent(
            timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            version_id=version_id,
            action=action,
            triggered_by=triggered_by,
            reason=reason,
        ))

    def _refresh_auto_tags(self) -> None:
        """Recompute best_mae / best_sr / production / latest auto-tags."""
        eligible = [v for v in self._versions.values()
                    if v.status != "retired"]

        best_mae_v = min(eligible, key=lambda x: x.mae) if eligible else None
        best_sr_v  = max(eligible, key=lambda x: x.sr)  if eligible else None

        for v in self._versions.values():
            keep = [t for t in v.tags if t not in
                    {"best_mae", "best_sr", "production", "latest"}]
            v.tags = keep

        # latest = most recently created among non-retired
        if eligible:
            latest_v = max(eligible,
                           key=lambda x: x.created_at)
            latest_v.tags.append("latest")

        if best_mae_v:
            best_mae_v.tags.append("best_mae")
        if best_sr_v and best_sr_v is not best_mae_v:
            best_sr_v.tags.append("best_sr")
        elif best_sr_v:
            best_sr_v.tags.append("best_sr")

        prod = self.production_version()
        if prod:
            prod.tags.append("production")


# ---------------------------------------------------------------------------
# Simulated version data (12 versions)
# ---------------------------------------------------------------------------

def build_mock_registry(seed: int = 42) -> ModelVersionRegistry:
    rng = random.Random(seed)
    reg = ModelVersionRegistry()

    # Anchor timestamps — start ~6 months ago
    base_dt = datetime(2025, 9, 15, 10, 0, 0)

    def iso(dt: datetime) -> str:
        return dt.isoformat(timespec="seconds") + "Z"

    def jitter(dt: datetime, days_min: int = 5, days_max: int = 18) -> datetime:
        return dt + timedelta(days=rng.randint(days_min, days_max),
                              hours=rng.randint(0, 23))

    # Performance arc:
    #   MAE:  0.103 → 0.051 → 0.031 → 0.020 → 0.016 → 0.013 (dip then up a bit)
    #   SR:   0.05  → 0.18  → 0.32  → 0.55  → 0.72  → 0.78
    mae_arc = [0.103, 0.072, 0.051, 0.038, 0.031, 0.024,
               0.020, 0.018, 0.016, 0.014, 0.013, 0.016]
    sr_arc  = [0.05,  0.12,  0.18,  0.28,  0.38,  0.50,
               0.58,  0.65,  0.72,  0.75,  0.78,  0.74]
    n_demos = [0, 100, 200, 300, 500, 750,
               1000, 1000, 1000, 1000, 1000, 1000]
    n_steps = [0, 2000, 2000, 3000, 4000, 4000,
               5000, 5000, 5000, 5000, 5000, 5000]
    latency_arc = [227, 220, 218, 215, 212, 210,
                   208, 206, 205, 204, 203, 205]
    vram_arc    = [6.7, 6.7, 6.8, 6.8, 6.9, 6.9,
                   7.0, 7.0, 7.0, 7.1, 7.1, 7.1]

    versions_meta = [
        # (version_id, parent, training_run)
        ("v1.0",  None,    "gr00t_base_n1.6"),
        ("v1.1",  "v1.0",  "finetune_run1"),
        ("v1.2",  "v1.1",  "dagger_run1"),
        ("v1.3",  "v1.2",  "dagger_run2"),
        ("v2.0",  "v1.3",  "finetune_run2_1000demos"),
        ("v2.1",  "v2.0",  "dagger_run3"),
        ("v2.1a", "v2.1",  "dagger_run4_ablation"),
        ("v2.2",  "v2.1",  "dagger_run5"),
        ("v2.2a", "v2.2",  "dagger_run6_ablation"),
        ("v2.2b", "v2.2",  "hpo_run1"),
        ("v2.3",  "v2.2b", "dagger_run9"),
        ("v2.3e", "v2.3",  "dagger_run9_extended"),
    ]

    dt = base_dt
    for i, (vid, parent, run) in enumerate(versions_meta):
        if i > 0:
            dt = jitter(dt, days_min=4, days_max=14)
        ckpt = (f"/oci/checkpoints/gr00t/{vid}/checkpoint-{n_steps[i]}"
                if n_steps[i] > 0
                else "/oci/checkpoints/gr00t/v1.0/base")
        mv = ModelVersion(
            version_id=vid,
            parent_version=parent,
            checkpoint_path=ckpt,
            created_at=iso(dt),
            training_run=run,
            n_demos=n_demos[i],
            n_steps=n_steps[i],
            mae=mae_arc[i],
            sr=sr_arc[i],
            latency_ms=latency_arc[i],
            vram_gb=vram_arc[i],
            tags=[],
            status="staging",
        )
        reg.add_version(mv)

    # Simulate deployment history
    # Promote versions over time, with one rollback
    reg.promote("v1.1",  triggered_by="ci_bot",     reason="first fine-tune passes eval")
    reg.promote("v1.3",  triggered_by="ci_bot",     reason="DAgger run2 SR 28%")
    reg.promote("v2.0",  triggered_by="ci_bot",     reason="1000-demo fine-tune MAE 0.031")
    reg.promote("v2.2",  triggered_by="ci_bot",     reason="DAgger run5 SR 72%")
    # Simulate rollback: v2.2a had a regression in prod, rolled back to v2.2
    reg.promote("v2.2a", triggered_by="ci_bot",     reason="ablation candidate deploy")
    reg.rollback("v2.2", triggered_by="oncall_sre", reason="v2.2a latency spike +40ms")
    # Then promote to final
    reg.promote("v2.3",  triggered_by="ci_bot",     reason="DAgger run9 SR 78% — current production")
    # Retire early versions
    for vid in ["v1.0", "v1.1", "v1.2"]:
        reg.retire(vid, triggered_by="auto_cleanup", reason="superseded; >90 days old")

    return reg


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_version_tree(reg: ModelVersionRegistry) -> None:
    """Print an indented lineage tree to stdout."""
    versions = reg.all_versions()
    # Build children map
    children_map: Dict[str, List[str]] = {v.version_id: [] for v in versions}
    roots = []
    for v in versions:
        if v.parent_version is None:
            roots.append(v.version_id)
        else:
            children_map[v.parent_version].append(v.version_id)

    STATUS_SYMBOLS = {
        "production": "[PROD]",
        "staging":    "[stag]",
        "retired":    "[retd]",
        "rollback":   "[RBCK]",
    }

    header = f"{'Version':<10} {'Status':<8} {'MAE':>8} {'SR':>7} {'Lat(ms)':>9} {'Tags'}"
    print("\n" + "=" * 70)
    print("  GR00T Model Version Registry — Lineage Tree")
    print("=" * 70)
    print(header)
    print("-" * 70)

    def _print(vid: str, depth: int = 0) -> None:
        v = reg.get(vid)
        indent = "  " * depth + ("└─ " if depth > 0 else "")
        sym = STATUS_SYMBOLS.get(v.status, v.status)
        tags_str = ", ".join(v.tags) if v.tags else ""
        print(f"{indent}{v.version_id:<{max(1,10-len(indent))}}"
              f" {sym:<8} {v.mae:>8.4f} {v.sr:>6.1%} {v.latency_ms:>8.0f}ms"
              f"  {tags_str}")
        for child in children_map.get(vid, []):
            _print(child, depth + 1)

    for root in roots:
        _print(root)

    print("-" * 70)
    prod = reg.production_version()
    if prod:
        print(f"\n  Current production: {prod.version_id}"
              f"  (MAE {prod.mae:.4f}, SR {prod.sr:.1%},"
              f" {prod.latency_ms:.0f} ms)")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

# Color palette
BG_DARK    = "#1e293b"
BG_CARD    = "#263548"
BG_TABLE   = "#1a2535"
ORACLE_RED = "#C74634"
TEXT_MAIN  = "#e2e8f0"
TEXT_MUTED = "#94a3b8"
GREEN      = "#22c55e"
YELLOW     = "#eab308"
BLUE       = "#3b82f6"
GRAY       = "#6b7280"

STATUS_COLOR = {
    "production": GREEN,
    "staging":    BLUE,
    "retired":    GRAY,
    "rollback":   YELLOW,
}


def _svg_line_chart(
    points: List[Tuple[str, float]],
    title: str,
    color: str,
    y_fmt: str = ".4f",
    width: int = 520,
    height: int = 180,
) -> str:
    """Return a minimal SVG line chart as an HTML string fragment."""
    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 45
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    n = len(values)
    if n < 2:
        return f"<svg width='{width}' height='{height}'></svg>"

    mn, mx = min(values), max(values)
    spread = mx - mn or 1e-9
    # Pad 10%
    lo = mn - spread * 0.12
    hi = mx + spread * 0.12
    rng = hi - lo

    def px(i: int) -> float:
        return pad_l + i * inner_w / (n - 1)

    def py(v: float) -> float:
        return pad_t + inner_h - (v - lo) / rng * inner_h

    # Build polyline
    pts_str = " ".join(f"{px(i):.1f},{py(v):.1f}"
                       for i, v in enumerate(values))

    # Axis ticks (4 y-ticks)
    y_ticks = []
    for k in range(5):
        yv = lo + rng * k / 4
        yp = py(yv)
        fmt_val = format(yv, y_fmt) if "%" not in y_fmt else f"{yv:.0%}"
        y_ticks.append(
            f'<line x1="{pad_l-4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="{TEXT_MUTED}" stroke-width="1"/>'
            f'<text x="{pad_l-7}" y="{yp+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="{TEXT_MUTED}">{format(yv, y_fmt)}</text>'
        )

    # X labels (every other to avoid crowding)
    x_labels = []
    step = max(1, n // 7)
    for i, lbl in enumerate(labels):
        if i % step == 0 or i == n - 1:
            xp = px(i)
            x_labels.append(
                f'<text x="{xp:.1f}" y="{height - 6}" text-anchor="middle" '
                f'font-size="9" fill="{TEXT_MUTED}">{lbl}</text>'
            )

    # Dots
    dots = "".join(
        f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" fill="{color}"/>'
        + f'<title>{lbl}: {format(v, y_fmt)}</title>'
        for i, (lbl, v) in enumerate(points)
    )

    svg = f"""
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"
     style="background:{BG_CARD};border-radius:8px;">
  <text x="{width//2}" y="18" text-anchor="middle"
        font-size="12" font-weight="bold" fill="{TEXT_MAIN}">{title}</text>
  <!-- Grid lines -->
  {''.join(
      f'<line x1="{pad_l}" y1="{py(lo+rng*k/4):.1f}" x2="{width-pad_r}" y2="{py(lo+rng*k/4):.1f}" '
      f'stroke="{BG_DARK}" stroke-width="1" stroke-dasharray="3,3"/>'
      for k in range(5)
  )}
  <!-- Y axis -->
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}"
        stroke="{TEXT_MUTED}" stroke-width="1"/>
  <!-- X axis -->
  <line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{width-pad_r}" y2="{pad_t+inner_h}"
        stroke="{TEXT_MUTED}" stroke-width="1"/>
  {''.join(y_ticks)}
  {''.join(x_labels)}
  <polyline points="{pts_str}" fill="none" stroke="{color}"
            stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {dots}
</svg>"""
    return svg


def _svg_lineage_tree(reg: ModelVersionRegistry) -> str:
    """Return an SVG DAG of the version lineage."""
    versions = reg.all_versions()
    vmap = {v.version_id: v for v in versions}

    # Topological ordering + depth assignment
    children_map: Dict[str, List[str]] = {v.version_id: [] for v in versions}
    roots = []
    for v in versions:
        if v.parent_version is None:
            roots.append(v.version_id)
        else:
            children_map[v.parent_version].append(v.version_id)

    # BFS to assign (depth, col) coordinates
    from collections import deque
    positions: Dict[str, Tuple[int, int]] = {}  # vid -> (row, col)
    col_counter: Dict[int, int] = {}

    queue = deque()
    for r in roots:
        queue.append((r, 0))
    while queue:
        vid, row = queue.popleft()
        if vid in positions:
            continue
        col = col_counter.get(row, 0)
        col_counter[row] = col + 1
        positions[vid] = (row, col)
        for child in children_map[vid]:
            queue.append((child, row + 1))

    # Normalize columns to spread nodes on same row
    max_row = max(r for r, _ in positions.values()) if positions else 0

    node_w, node_h = 90, 36
    h_gap, v_gap = 110, 70
    pad = 20
    svg_w = (max(c for _, c in positions.values()) + 1) * h_gap + node_w + 2 * pad
    svg_h = (max_row + 1) * v_gap + node_h + 2 * pad + 30

    def cx(row: int, col: int) -> float:
        # Center nodes within their row
        n_on_row = col_counter.get(row, 1)
        total_w = n_on_row * h_gap
        offset = (svg_w - total_w) / 2
        return offset + col * h_gap + node_w / 2

    def cy(row: int) -> float:
        return pad + 30 + row * v_gap + node_h / 2

    edges = []
    nodes = []

    for vid, v in vmap.items():
        row, col = positions[vid]
        x_c = cx(row, col)
        y_c = cy(row)
        color = STATUS_COLOR.get(v.status, GRAY)
        tags_short = " ".join(
            {"production": "PROD", "best_mae": "MAE*",
             "best_sr": "SR*", "latest": "latest"}.get(t, t)
            for t in v.tags
        )
        label2 = f"SR {v.sr:.0%} | MAE {v.mae:.3f}"
        nodes.append(
            f'<rect x="{x_c - node_w/2:.1f}" y="{y_c - node_h/2:.1f}" '
            f'width="{node_w}" height="{node_h}" rx="6" '
            f'fill="{BG_DARK}" stroke="{color}" stroke-width="2"/>'
            f'<text x="{x_c:.1f}" y="{y_c - 5:.1f}" text-anchor="middle" '
            f'font-size="11" font-weight="bold" fill="{color}">{vid}</text>'
            f'<text x="{x_c:.1f}" y="{y_c + 8:.1f}" text-anchor="middle" '
            f'font-size="8" fill="{TEXT_MUTED}">{label2}</text>'
        )
        if tags_short:
            nodes.append(
                f'<text x="{x_c:.1f}" y="{y_c + 19:.1f}" text-anchor="middle" '
                f'font-size="7" fill="{YELLOW}">{tags_short}</text>'
            )

        if v.parent_version and v.parent_version in positions:
            pr, pc = positions[v.parent_version]
            px_c = cx(pr, pc)
            py_c = cy(pr)
            edges.append(
                f'<line x1="{px_c:.1f}" y1="{py_c + node_h/2:.1f}" '
                f'x2="{x_c:.1f}" y2="{y_c - node_h/2:.1f}" '
                f'stroke="{TEXT_MUTED}" stroke-width="1.5" stroke-dasharray="4,3" '
                f'marker-end="url(#arrow)"/>'
            )

    arrow_marker = f"""
<defs>
  <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L0,6 L8,3 z" fill="{TEXT_MUTED}"/>
  </marker>
</defs>"""

    title = (f'<text x="{svg_w//2}" y="20" text-anchor="middle" '
             f'font-size="13" font-weight="bold" fill="{TEXT_MAIN}">'
             f'Version Lineage DAG</text>')

    return (f'<svg width="{int(svg_w)}" height="{int(svg_h)}" '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'style="background:{BG_CARD};border-radius:8px;">'
            + arrow_marker + title
            + "".join(edges)
            + "".join(nodes)
            + "</svg>")


def generate_html_report(reg: ModelVersionRegistry) -> str:
    versions = sorted(reg.all_versions(), key=lambda v: v.created_at)
    prod = reg.production_version()

    best_mae = min(versions, key=lambda v: v.mae)
    best_sr  = max(versions, key=lambda v: v.sr)

    # Summary cards
    def card(label: str, value: str, sub: str = "") -> str:
        return f"""
        <div class="card">
          <div class="card-label">{label}</div>
          <div class="card-value">{value}</div>
          {'<div class="card-sub">' + sub + '</div>' if sub else ''}
        </div>"""

    cards_html = "".join([
        card("Total Versions",    str(len(versions))),
        card("Production",        prod.version_id if prod else "—",
             f"SR {prod.sr:.0%}" if prod else ""),
        card("Best MAE",          f"{best_mae.mae:.4f}",
             best_mae.version_id),
        card("Best SR",           f"{best_sr.sr:.0%}",
             best_sr.version_id),
    ])

    # Charts — only non-retired for clarity
    non_retired = [v for v in versions if v.status != "retired"]
    mae_pts = [(v.version_id, v.mae) for v in non_retired]
    sr_pts  = [(v.version_id, v.sr)  for v in non_retired]

    mae_svg = _svg_line_chart(mae_pts, "MAE over Versions (lower=better)",
                              ORACLE_RED, y_fmt=".4f")
    sr_svg  = _svg_line_chart(sr_pts,  "Success Rate over Versions",
                              GREEN, y_fmt=".0%")

    # Lineage SVG
    lineage_svg = _svg_lineage_tree(reg)

    # Version table
    def status_badge(s: str) -> str:
        c = STATUS_COLOR.get(s, GRAY)
        return (f'<span style="background:{c}22;color:{c};'
                f'border:1px solid {c};border-radius:4px;'
                f'padding:2px 8px;font-size:11px;">{s}</span>')

    def tag_chip(t: str) -> str:
        colors = {"best_mae": ORACLE_RED, "best_sr": GREEN,
                  "production": GREEN, "latest": BLUE}
        c = colors.get(t, TEXT_MUTED)
        return (f'<span style="background:{c}22;color:{c};'
                f'border-radius:3px;padding:1px 5px;font-size:10px;'
                f'margin-right:3px;">{t}</span>')

    rows_html = ""
    for v in versions:
        tags_html = "".join(tag_chip(t) for t in v.tags)
        rows_html += f"""
        <tr>
          <td>{v.version_id}</td>
          <td>{v.created_at[:10]}</td>
          <td>{status_badge(v.status)}</td>
          <td style="text-align:right">{v.mae:.4f}</td>
          <td style="text-align:right">{v.sr:.0%}</td>
          <td style="text-align:right">{v.latency_ms:.0f}</td>
          <td style="text-align:right">{v.n_demos:,}</td>
          <td style="text-align:right">{v.n_steps:,}</td>
          <td>{v.training_run}</td>
          <td>{tags_html}</td>
        </tr>"""

    # Deployment history table
    history = reg.deployment_history(limit=10)
    ACTION_COLOR = {
        "promote": GREEN, "rollback": YELLOW,
        "retire": GRAY, "demote": TEXT_MUTED, "stage": BLUE,
    }

    def action_badge(a: str) -> str:
        c = ACTION_COLOR.get(a, TEXT_MUTED)
        return (f'<span style="color:{c};font-weight:600;">{a}</span>')

    hist_rows = ""
    for e in reversed(history):
        hist_rows += f"""
        <tr>
          <td style="white-space:nowrap">{e.timestamp[:19].replace("T"," ")}</td>
          <td>{e.version_id}</td>
          <td>{action_badge(e.action)}</td>
          <td>{e.triggered_by}</td>
          <td style="color:{TEXT_MUTED}">{e.reason}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GR00T Model Version Registry</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: {BG_DARK};
    color: {TEXT_MAIN};
    padding: 24px;
    min-height: 100vh;
  }}
  h1 {{ font-size: 22px; font-weight: 700; color: {TEXT_MAIN}; }}
  h2 {{ font-size: 15px; font-weight: 600; color: {TEXT_MUTED};
        text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px; }}
  .header {{
    display: flex; align-items: center; gap: 14px;
    margin-bottom: 28px; padding-bottom: 16px;
    border-bottom: 2px solid {ORACLE_RED};
  }}
  .logo {{
    width: 36px; height: 36px; border-radius: 8px;
    background: {ORACLE_RED};
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 16px; color: #fff;
  }}
  .subtitle {{ color: {TEXT_MUTED}; font-size: 13px; margin-top: 2px; }}
  .section {{ margin-bottom: 32px; }}
  .cards {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
    gap: 14px; margin-bottom: 28px;
  }}
  .card {{
    background: {BG_CARD}; border-radius: 10px;
    padding: 16px 20px; border-left: 3px solid {ORACLE_RED};
  }}
  .card-label {{ font-size: 11px; color: {TEXT_MUTED}; text-transform: uppercase;
                 letter-spacing: .07em; margin-bottom: 6px; }}
  .card-value {{ font-size: 24px; font-weight: 700; color: {TEXT_MAIN}; }}
  .card-sub   {{ font-size: 11px; color: {TEXT_MUTED}; margin-top: 4px; }}
  .charts {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 8px;
  }}
  @media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 12px;
    background: {BG_TABLE}; border-radius: 8px; overflow: hidden;
  }}
  thead th {{
    background: {BG_CARD}; color: {TEXT_MUTED}; font-size: 11px;
    text-transform: uppercase; letter-spacing: .06em;
    padding: 10px 12px; text-align: left; font-weight: 600;
  }}
  tbody tr {{ border-bottom: 1px solid {BG_DARK}; }}
  tbody tr:hover {{ background: {BG_CARD}22; }}
  tbody td {{ padding: 9px 12px; color: {TEXT_MAIN}; vertical-align: middle; }}
  .lineage-wrap {{ overflow-x: auto; border-radius: 8px; }}
  .generated {{
    margin-top: 32px; text-align: center;
    font-size: 11px; color: {TEXT_MUTED};
  }}
</style>
</head>
<body>
<div class="header">
  <div class="logo">OCI</div>
  <div>
    <h1>GR00T Model Version Registry</h1>
    <div class="subtitle">
      OCI Robot Cloud — fine-tuned checkpoint lineage &amp; deployment tracker
      &nbsp;·&nbsp; Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
    </div>
  </div>
</div>

<!-- Summary cards -->
<div class="section">
  <h2>Overview</h2>
  <div class="cards">{cards_html}</div>
</div>

<!-- Charts -->
<div class="section">
  <h2>Performance Trends</h2>
  <div class="charts">
    <div>{mae_svg}</div>
    <div>{sr_svg}</div>
  </div>
</div>

<!-- Lineage DAG -->
<div class="section">
  <h2>Lineage Tree</h2>
  <div class="lineage-wrap">
    {lineage_svg}
  </div>
</div>

<!-- Version table -->
<div class="section">
  <h2>All Versions</h2>
  <table>
    <thead>
      <tr>
        <th>Version</th><th>Created</th><th>Status</th>
        <th style="text-align:right">MAE</th>
        <th style="text-align:right">SR</th>
        <th style="text-align:right">Lat (ms)</th>
        <th style="text-align:right">Demos</th>
        <th style="text-align:right">Steps</th>
        <th>Training Run</th><th>Tags</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<!-- Deployment history -->
<div class="section">
  <h2>Deployment History (last 10)</h2>
  <table>
    <thead>
      <tr>
        <th>Timestamp</th><th>Version</th><th>Action</th>
        <th>Triggered By</th><th>Reason</th>
      </tr>
    </thead>
    <tbody>{hist_rows}</tbody>
  </table>
</div>

<div class="generated">
  Oracle Confidential &nbsp;·&nbsp;
  OCI Robot Cloud — GR00T N1.6 Fine-Tuning Platform
</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# JSON dump
# ---------------------------------------------------------------------------

def generate_json(reg: ModelVersionRegistry) -> str:
    data = reg.to_dict()
    data["meta"] = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_versions": len(data["versions"]),
        "production_version": (reg.production_version().version_id
                               if reg.production_version() else None),
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T Model Version Registry — lineage, perf, deployment."
    )
    parser.add_argument("--mock", action="store_true",
                        help="Populate registry with 12 simulated versions")
    parser.add_argument("--output", default="/tmp/model_version_registry.html",
                        help="Path for the HTML report (default: %(default)s)")
    parser.add_argument("--json-output", default=None,
                        help="Optional path to write JSON dump")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for mock data (default: %(default)s)")
    args = parser.parse_args()

    if args.mock:
        reg = build_mock_registry(seed=args.seed)
    else:
        print("No data source specified. Use --mock to load simulated data.",
              file=sys.stderr)
        sys.exit(1)

    # Console output
    print_version_tree(reg)

    # HTML report
    html = generate_html_report(reg)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML report written → {args.output}")

    # JSON dump
    json_path = args.json_output or args.output.replace(".html", ".json")
    json_str = generate_json(reg)
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(json_str)
    print(f"JSON dump written   → {json_path}")

    # Quick compare example
    print("\nComparison v1.1 vs v2.3:")
    cmp = reg.compare("v1.1", "v2.3")
    for field_name, vals in cmp["fields"].items():
        delta = vals.get("delta")
        pct   = vals.get("pct_change")
        delta_str = (f"  Δ {delta:+.4g}"
                     + (f" ({pct:+.1f}%)" if pct is not None else "")
                     if delta is not None else "")
        print(f"  {field_name:<12} v1.1={vals['v1.1']}  v2.3={vals['v2.3']}"
              f"{delta_str}")


if __name__ == "__main__":
    main()
