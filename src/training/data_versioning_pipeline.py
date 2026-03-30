"""
Dataset versioning and provenance tracking for GR00T fine-tuning pipeline.
Tracks SDG, DAgger, and augmented dataset lineage.
"""

import argparse
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DatasetVersion:
    version_id: str                        # e.g. "v1.0"
    source: str                            # sdg / dagger / human / augmented
    n_episodes: int
    n_frames: int
    size_gb: float
    created_date: str                      # ISO date string
    parent_version: Optional[str]
    quality_score: float                   # 0–1
    tags: List[str] = field(default_factory=list)


@dataclass
class DataVersionReport:
    latest_version: str
    total_episodes: int
    total_gb: float
    quality_trend: str                     # improving / stable / degrading
    lineage_depth: int
    versions: List[DatasetVersion]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_versions(seed: int = 42) -> List[DatasetVersion]:
    """Return 10 pre-defined dataset versions v1.0–v2.4."""
    random.seed(seed)
    base_date = datetime(2025, 10, 1)

    def d(offset_days: int) -> str:
        return (base_date + timedelta(days=offset_days)).strftime("%Y-%m-%d")

    def frames(eps: int, jitter: bool = True) -> int:
        avg = 100
        if jitter:
            avg += random.randint(-5, 5)
        return eps * avg

    versions = [
        DatasetVersion(
            version_id="v1.0",
            source="sdg",
            n_episodes=100,
            n_frames=frames(100, False),
            size_gb=round(100 * 0.012, 3),
            created_date=d(0),
            parent_version=None,
            quality_score=0.52,
            tags=["genesis", "initial"],
        ),
        DatasetVersion(
            version_id="v1.1",
            source="augmented",
            n_episodes=300,
            n_frames=frames(300),
            size_gb=round(300 * 0.012, 3),
            created_date=d(5),
            parent_version="v1.0",
            quality_score=0.61,
            tags=["augmented", "color-jitter", "noise"],
        ),
        DatasetVersion(
            version_id="v1.2",
            source="dagger",
            n_episodes=150,
            n_frames=frames(150),
            size_gb=round(150 * 0.013, 3),
            created_date=d(12),
            parent_version="v1.1",
            quality_score=0.67,
            tags=["dagger-round1", "online"],
        ),
        DatasetVersion(
            version_id="v2.0",
            source="sdg",
            n_episodes=500,
            n_frames=frames(500, False),
            size_gb=round(500 * 0.014, 3),
            created_date=d(20),
            parent_version="v1.2",
            quality_score=0.74,
            tags=["isaac-sim", "domain-rand", "improved-sdg"],
        ),
        DatasetVersion(
            version_id="v2.1",
            source="dagger",
            n_episodes=620,
            n_frames=frames(620),
            size_gb=round(620 * 0.014, 3),
            created_date=d(28),
            parent_version="v2.0",
            quality_score=0.77,
            tags=["dagger-round2"],
        ),
        DatasetVersion(
            version_id="v2.2",
            source="dagger",
            n_episodes=750,
            n_frames=frames(750),
            size_gb=round(750 * 0.014, 3),
            created_date=d(36),
            parent_version="v2.1",
            quality_score=0.80,
            tags=["dagger-round3", "curriculum"],
        ),
        DatasetVersion(
            version_id="v2.3",
            source="dagger",
            n_episodes=880,
            n_frames=frames(880),
            size_gb=round(880 * 0.015, 3),
            created_date=d(44),
            parent_version="v2.2",
            quality_score=0.84,
            tags=["dagger-round4", "hard-negatives"],
        ),
        DatasetVersion(
            version_id="v2.4",
            source="dagger",
            n_episodes=1000,
            n_frames=frames(1000),
            size_gb=round(1000 * 0.015, 3),
            created_date=d(52),
            parent_version="v2.3",
            quality_score=0.87,
            tags=["dagger-round5", "production"],
        ),
    ]

    # Pad to 10 by inserting two minor human-collected variants
    versions.insert(4, DatasetVersion(
        version_id="v1.3",
        source="human",
        n_episodes=60,
        n_frames=frames(60),
        size_gb=round(60 * 0.016, 3),
        created_date=d(15),
        parent_version="v1.2",
        quality_score=0.70,
        tags=["human-demo", "teleop"],
    ))
    versions.insert(6, DatasetVersion(
        version_id="v1.4",
        source="augmented",
        n_episodes=180,
        n_frames=frames(180),
        size_gb=round(180 * 0.013, 3),
        created_date=d(18),
        parent_version="v1.3",
        quality_score=0.72,
        tags=["augmented", "sim-to-real"],
    ))

    return versions


def build_report(versions: List[DatasetVersion]) -> DataVersionReport:
    latest = versions[-1]
    total_episodes = sum(v.n_episodes for v in versions)
    total_gb = round(sum(v.size_gb for v in versions), 3)

    # Compute quality trend from last 3 versions
    q_last3 = [v.quality_score for v in versions[-3:]]
    if q_last3[-1] > q_last3[0] + 0.01:
        trend = "improving"
    elif q_last3[-1] < q_last3[0] - 0.01:
        trend = "degrading"
    else:
        trend = "stable"

    # Lineage depth: longest chain
    parent_map = {v.version_id: v.parent_version for v in versions}
    def depth(vid: Optional[str]) -> int:
        if vid is None:
            return 0
        return 1 + depth(parent_map.get(vid))

    lineage_depth = max(depth(v.version_id) for v in versions)

    return DataVersionReport(
        latest_version=latest.version_id,
        total_episodes=total_episodes,
        total_gb=total_gb,
        quality_trend=trend,
        lineage_depth=lineage_depth,
        versions=versions,
    )


# ---------------------------------------------------------------------------
# CLI stdout table
# ---------------------------------------------------------------------------

def print_table(versions: List[DatasetVersion]) -> None:
    header = f"{'Version':<10} {'Source':<12} {'Episodes':>9} {'Frames':>9} {'GB':>7} {'Quality':>8} {'Parent':<10} {'Tags'}"
    sep = "-" * 95
    print(sep)
    print(header)
    print(sep)
    for v in versions:
        tags_str = ", ".join(v.tags)
        parent = v.parent_version or "—"
        print(
            f"{v.version_id:<10} {v.source:<12} {v.n_episodes:>9} {v.n_frames:>9} "
            f"{v.size_gb:>7.2f} {v.quality_score:>8.2f} {parent:<10} {tags_str}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

SOURCE_COLORS = {
    "sdg":       "#3b82f6",   # blue
    "dagger":    "#C74634",   # Oracle red
    "human":     "#10b981",   # green
    "augmented": "#f59e0b",   # amber
}

QUALITY_COLOR = "#C74634"


def _stat_card(label: str, value: str, sub: str = "") -> str:
    return f"""
      <div class="card">
        <div class="card-label">{label}</div>
        <div class="card-value">{value}</div>
        {f'<div class="card-sub">{sub}</div>' if sub else ''}
      </div>"""


def _quality_line_chart(versions: List[DatasetVersion]) -> str:
    """SVG polyline of quality score per version."""
    w, h = 640, 200
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40

    n = len(versions)
    x_step = (w - pad_l - pad_r) / max(n - 1, 1)
    y_min, y_max = 0.45, 0.95

    def px(i: int) -> float:
        return pad_l + i * x_step

    def py(q: float) -> float:
        frac = (q - y_min) / (y_max - y_min)
        return pad_t + (1 - frac) * (h - pad_t - pad_b)

    points = " ".join(f"{px(i):.1f},{py(v.quality_score):.1f}" for i, v in enumerate(versions))

    # Grid lines
    grid_lines = ""
    for yv in [0.5, 0.6, 0.7, 0.8, 0.9]:
        y = py(yv)
        grid_lines += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        grid_lines += f'<text x="{pad_l - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8">{yv:.1f}</text>'

    # X labels
    x_labels = ""
    for i, v in enumerate(versions):
        x_labels += f'<text x="{px(i):.1f}" y="{h - 5}" text-anchor="middle" font-size="10" fill="#94a3b8">{v.version_id}</text>'

    # Dots
    dots = ""
    for i, v in enumerate(versions):
        col = SOURCE_COLORS.get(v.source, "#64748b")
        dots += f'<circle cx="{px(i):.1f}" cy="{py(v.quality_score):.1f}" r="5" fill="{col}" stroke="#1e293b" stroke-width="2"/>'

    return f"""
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart-svg">
      {grid_lines}
      <polyline points="{points}" fill="none" stroke="{QUALITY_COLOR}" stroke-width="2.5" stroke-linejoin="round"/>
      {dots}
      {x_labels}
      <text x="{pad_l - 38}" y="{pad_t + (h - pad_t - pad_b) // 2}" transform="rotate(-90,{pad_l - 38},{pad_t + (h - pad_t - pad_b) // 2})" text-anchor="middle" font-size="11" fill="#94a3b8">Quality</text>
    </svg>"""


def _episode_bar_chart(versions: List[DatasetVersion]) -> str:
    """SVG grouped bar chart of episodes per version coloured by source."""
    w, h = 640, 220
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50

    n = len(versions)
    bar_w = max(18, (w - pad_l - pad_r) / n - 8)
    x_step = (w - pad_l - pad_r) / n
    max_eps = max(v.n_episodes for v in versions)

    def bx(i: int) -> float:
        return pad_l + i * x_step + (x_step - bar_w) / 2

    def bar_h(eps: int) -> float:
        return (eps / max_eps) * (h - pad_t - pad_b)

    bars = ""
    x_labels = ""
    for i, v in enumerate(versions):
        col = SOURCE_COLORS.get(v.source, "#64748b")
        bh = bar_h(v.n_episodes)
        by = h - pad_b - bh
        bars += f'<rect x="{bx(i):.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{col}" rx="3"/>'
        bars += f'<text x="{bx(i) + bar_w / 2:.1f}" y="{by - 4:.1f}" text-anchor="middle" font-size="9" fill="#cbd5e1">{v.n_episodes}</text>'
        x_labels += f'<text x="{bx(i) + bar_w / 2:.1f}" y="{h - pad_b + 14}" text-anchor="middle" font-size="10" fill="#94a3b8">{v.version_id}</text>'

    # Y axis grid
    grid = ""
    for yv_frac in [0.25, 0.5, 0.75, 1.0]:
        eps_val = int(max_eps * yv_frac)
        y = h - pad_b - bar_h(eps_val)
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        grid += f'<text x="{pad_l - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8">{eps_val}</text>'

    # Legend
    legend = ""
    lx = pad_l
    for src, col in SOURCE_COLORS.items():
        legend += f'<rect x="{lx}" y="{h - 16}" width="12" height="12" fill="{col}" rx="2"/>'
        legend += f'<text x="{lx + 16}" y="{h - 5}" font-size="10" fill="#94a3b8">{src}</text>'
        lx += 90

    return f"""
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart-svg">
      {grid}
      {bars}
      {x_labels}
      {legend}
      <text x="{pad_l - 38}" y="{pad_t + (h - pad_t - pad_b) // 2}" transform="rotate(-90,{pad_l - 38},{pad_t + (h - pad_t - pad_b) // 2})" text-anchor="middle" font-size="11" fill="#94a3b8">Episodes</text>
    </svg>"""


def _lineage_tree(versions: List[DatasetVersion]) -> str:
    """SVG tree showing parent→child relationships."""
    w, h = 900, 280
    pad_x, pad_y = 60, 50
    node_r = 22

    # Assign column by version order, row by source family
    source_row = {"sdg": 0, "augmented": 1, "human": 2, "dagger": 3}

    n = len(versions)
    x_step = (w - 2 * pad_x) / max(n - 1, 1)
    row_h = (h - 2 * pad_y) / 4

    positions: dict[str, tuple[float, float]] = {}
    for i, v in enumerate(versions):
        row = source_row.get(v.source, 2)
        cx = pad_x + i * x_step
        cy = pad_y + row * row_h
        positions[v.version_id] = (cx, cy)

    arrows = ""
    for v in versions:
        if v.parent_version and v.parent_version in positions:
            x1, y1 = positions[v.parent_version]
            x2, y2 = positions[v.version_id]
            # Slightly shorten arrow to not overlap nodes
            dx, dy = x2 - x1, y2 - y1
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist > 0:
                ux, uy = dx / dist, dy / dist
                sx, sy = x1 + ux * node_r, y1 + uy * node_r
                ex, ey = x2 - ux * (node_r + 5), y2 - uy * (node_r + 5)
            else:
                sx, sy, ex, ey = x1, y1, x2, y2
            arrows += (
                f'<defs><marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
                f'<polygon points="0 0, 8 3, 0 6" fill="#64748b"/></marker></defs>'
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                f'stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>'
            )

    nodes = ""
    for v in versions:
        cx, cy = positions[v.version_id]
        col = SOURCE_COLORS.get(v.source, "#64748b")
        nodes += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{node_r}" fill="{col}" opacity="0.85"/>'
            f'<text x="{cx:.1f}" y="{cy - 4:.1f}" text-anchor="middle" font-size="9" font-weight="bold" fill="#fff">{v.version_id}</text>'
            f'<text x="{cx:.1f}" y="{cy + 7:.1f}" text-anchor="middle" font-size="8" fill="#fff">{v.quality_score:.2f}</text>'
        )

    # Row labels
    row_labels = ""
    for src, row in source_row.items():
        cy = pad_y + row * row_h
        row_labels += f'<text x="4" y="{cy + 4:.1f}" font-size="10" fill="#64748b">{src}</text>'

    return f"""
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="chart-svg" style="height:280px">
      {row_labels}
      {arrows}
      {nodes}
    </svg>"""


def _version_table_html(versions: List[DatasetVersion]) -> str:
    rows = ""
    for v in versions:
        tags = ", ".join(v.tags)
        parent = v.parent_version or "—"
        src_col = SOURCE_COLORS.get(v.source, "#64748b")
        rows += f"""
        <tr>
          <td><strong>{v.version_id}</strong></td>
          <td><span class="badge" style="background:{src_col}20;color:{src_col};border:1px solid {src_col}40">{v.source}</span></td>
          <td>{v.n_episodes:,}</td>
          <td>{v.size_gb:.2f}</td>
          <td>
            <div class="qual-bar-wrap">
              <div class="qual-bar" style="width:{v.quality_score * 100:.0f}%;background:{src_col}"></div>
              <span>{v.quality_score:.2f}</span>
            </div>
          </td>
          <td>{parent}</td>
          <td class="tags-cell">{tags}</td>
        </tr>"""
    return rows


def generate_html(report: DataVersionReport) -> str:
    versions = report.versions
    stat_cards = (
        _stat_card("Latest Version", report.latest_version)
        + _stat_card("Total Episodes", f"{report.total_episodes:,}")
        + _stat_card("Quality Score", f"{versions[-1].quality_score:.2f}", report.quality_trend)
        + _stat_card("Lineage Depth", str(report.lineage_depth))
    )

    quality_chart = _quality_line_chart(versions)
    bar_chart = _episode_bar_chart(versions)
    lineage_svg = _lineage_tree(versions)
    table_rows = _version_table_html(versions)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Dataset Versioning Pipeline — GR00T Fine-Tuning</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      padding: 24px;
    }}
    h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }}
    h2 {{ font-size: 1.1rem; font-weight: 600; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-top: 4px; margin-bottom: 24px; }}
    .header {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 4px; }}
    .oracle-badge {{ background: #C74634; color: #fff; font-size: 0.7rem; font-weight: 700;
                     padding: 2px 8px; border-radius: 4px; letter-spacing: 0.06em; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }}
    .card-label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 8px; }}
    .card-value {{ font-size: 2rem; font-weight: 700; color: #f1f5f9; }}
    .card-sub {{ font-size: 0.8rem; color: #C74634; margin-top: 4px; font-weight: 600; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .chart-svg {{ width: 100%; height: auto; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    thead tr {{ background: #0f172a; }}
    th {{ text-align: left; padding: 10px 12px; color: #64748b; font-weight: 600;
          font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em;
          border-bottom: 1px solid #334155; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; vertical-align: middle; }}
    tr:hover {{ background: #0f172a50; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
    .tags-cell {{ color: #64748b; font-size: 0.78rem; }}
    .qual-bar-wrap {{ display: flex; align-items: center; gap: 8px; }}
    .qual-bar {{ height: 6px; border-radius: 3px; min-width: 4px; }}
    .qual-bar-wrap span {{ font-size: 0.8rem; color: #cbd5e1; min-width: 32px; }}
    .footer {{ text-align: center; color: #475569; font-size: 0.78rem; margin-top: 16px; }}
    @media (max-width: 800px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Dataset Versioning Pipeline</h1>
    <span class="oracle-badge">OCI Robot Cloud</span>
  </div>
  <p class="subtitle">GR00T fine-tuning provenance: SDG &rarr; Augmentation &rarr; DAgger lineage &mdash; Generated {generated_at}</p>

  <div class="cards">
    {stat_cards}
  </div>

  <div class="section">
    <h2>Quality Score Over Versions</h2>
    {quality_chart}
  </div>

  <div class="section">
    <h2>Episodes Per Version (by Source)</h2>
    {bar_chart}
  </div>

  <div class="section">
    <h2>Dataset Provenance Lineage</h2>
    <p style="color:#64748b;font-size:0.8rem;margin-bottom:12px;">Nodes coloured by source type. Rows: SDG / Augmented / Human / DAgger. Arrows show parent→child inheritance.</p>
    {lineage_svg}
  </div>

  <div class="section">
    <h2>Version Registry</h2>
    <table>
      <thead>
        <tr>
          <th>Version</th>
          <th>Source</th>
          <th>Episodes</th>
          <th>Size (GB)</th>
          <th>Quality</th>
          <th>Parent</th>
          <th>Tags</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>

  <div class="footer">OCI Robot Cloud &mdash; Dataset Versioning Pipeline &mdash; GR00T Fine-Tuning &mdash; Oracle Confidential</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataset versioning and provenance tracking for GR00T fine-tuning."
    )
    parser.add_argument("--mock", action="store_true", help="Use simulated dataset versions (default mode)")
    parser.add_argument("--output", default="/tmp/data_versioning_pipeline.html", help="Output HTML path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for simulation")
    args = parser.parse_args()

    versions = simulate_versions(seed=args.seed)
    report = build_report(versions)

    # Stdout table
    print(f"\nDataset Versioning Report — {len(versions)} versions")
    print_table(versions)
    print(f"\nSummary:")
    print(f"  Latest version : {report.latest_version}")
    print(f"  Total episodes : {report.total_episodes:,}")
    print(f"  Total size     : {report.total_gb:.2f} GB")
    print(f"  Quality trend  : {report.quality_trend}")
    print(f"  Lineage depth  : {report.lineage_depth}")

    # HTML report
    html = generate_html(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\nHTML report written to: {args.output}\n")


if __name__ == "__main__":
    main()
