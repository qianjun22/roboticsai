"""
API version compatibility checker for OCI Robot Cloud.
Detects breaking changes between partner SDK versions and server.
"""

import argparse
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from packaging.version import Version as PkgVersion


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChangeType(str, Enum):
    BREAKING = "breaking"
    ADDITIVE = "additive"
    DEPRECATION = "deprecation"


class MigrationEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class APIChange:
    version_from: str
    version_to: str
    change_type: ChangeType
    endpoint: str
    description: str
    migration_effort: MigrationEffort


@dataclass
class PartnerCompatibility:
    partner_name: str
    sdk_version: str
    server_version: str
    compatible: bool
    breaking_changes: int
    deprecation_warnings: int
    migration_required: bool


@dataclass
class CompatibilityReport:
    server_version: str
    n_partners: int
    n_compatible: int
    n_migration_required: int
    changes: list[APIChange]
    partner_results: list[PartnerCompatibility]


# ---------------------------------------------------------------------------
# Version helper
# ---------------------------------------------------------------------------

def _ver(v: str) -> tuple:
    """Return a comparable tuple from a semver string."""
    parts = v.split(".")
    return tuple(int(p) for p in parts)


def changes_between(sdk_version: str, server_version: str, all_changes: list[APIChange]) -> list[APIChange]:
    """Return all API changes that a client on sdk_version would encounter when talking to server_version."""
    sdk = _ver(sdk_version)
    srv = _ver(server_version)
    result = []
    for ch in all_changes:
        ch_from = _ver(ch.version_from)
        ch_to = _ver(ch.version_to)
        # The change is relevant if it was introduced after the sdk version
        # and at or before the server version.
        if sdk < ch_to <= srv:
            result.append(ch)
    return result


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SERVER_VERSION = "2.4.0"

ALL_CHANGES: list[APIChange] = [
    APIChange(
        version_from="1.9.0",
        version_to="2.0.0",
        change_type=ChangeType.BREAKING,
        endpoint="/v2/inference",
        description="Request schema changed: 'chunk_size' field renamed to 'action_chunk_size'.",
        migration_effort=MigrationEffort.HIGH,
    ),
    APIChange(
        version_from="2.0.0",
        version_to="2.1.0",
        change_type=ChangeType.ADDITIVE,
        endpoint="/v2/eval/multi_task",
        description="New multi-task evaluation endpoint added.",
        migration_effort=MigrationEffort.LOW,
    ),
    APIChange(
        version_from="2.1.0",
        version_to="2.2.0",
        change_type=ChangeType.DEPRECATION,
        endpoint="/v1/inference",
        description="/v1/inference deprecated; sunset scheduled for 2027-06.",
        migration_effort=MigrationEffort.MEDIUM,
    ),
    APIChange(
        version_from="2.2.0",
        version_to="2.3.0",
        change_type=ChangeType.BREAKING,
        endpoint="/v2/auth/token",
        description="Auth header format changed from 'Bearer <token>' to 'OCI-Robot <token>'.",
        migration_effort=MigrationEffort.MEDIUM,
    ),
    APIChange(
        version_from="2.3.0",
        version_to="2.4.0",
        change_type=ChangeType.ADDITIVE,
        endpoint="/v2/federated_learning",
        description="New federated learning endpoint for distributed fine-tuning.",
        migration_effort=MigrationEffort.LOW,
    ),
]

PARTNERS_RAW = [
    ("partner_alpha",   "2.4.0"),
    ("partner_beta",    "2.2.1"),
    ("partner_gamma",   "1.8.0"),
    ("partner_delta",   "2.3.0"),
    ("partner_epsilon", "2.4.0"),
]


# ---------------------------------------------------------------------------
# Core checker
# ---------------------------------------------------------------------------

def evaluate_partner(name: str, sdk_version: str, server_version: str) -> PartnerCompatibility:
    relevant = changes_between(sdk_version, server_version, ALL_CHANGES)
    breaking = [c for c in relevant if c.change_type == ChangeType.BREAKING]
    deprecations = [c for c in relevant if c.change_type == ChangeType.DEPRECATION]
    n_breaking = len(breaking)
    n_deprec = len(deprecations)
    compatible = n_breaking == 0
    migration_required = n_breaking > 0
    return PartnerCompatibility(
        partner_name=name,
        sdk_version=sdk_version,
        server_version=server_version,
        compatible=compatible,
        breaking_changes=n_breaking,
        deprecation_warnings=n_deprec,
        migration_required=migration_required,
    )


def run_mock_check() -> CompatibilityReport:
    partner_results = [
        evaluate_partner(name, sdk, SERVER_VERSION) for name, sdk in PARTNERS_RAW
    ]
    n_compatible = sum(1 for p in partner_results if p.compatible)
    n_migration = sum(1 for p in partner_results if p.migration_required)
    return CompatibilityReport(
        server_version=SERVER_VERSION,
        n_partners=len(partner_results),
        n_compatible=n_compatible,
        n_migration_required=n_migration,
        changes=ALL_CHANGES,
        partner_results=partner_results,
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_CHANGE_TYPE_COLORS = {
    ChangeType.BREAKING: "#ef4444",
    ChangeType.ADDITIVE: "#22c55e",
    ChangeType.DEPRECATION: "#f59e0b",
}

_EFFORT_BADGE = {
    MigrationEffort.LOW: ("bg-green", "#22c55e"),
    MigrationEffort.MEDIUM: ("bg-amber", "#f59e0b"),
    MigrationEffort.HIGH: ("bg-red", "#ef4444"),
}


def _version_timeline_svg(changes: list[APIChange]) -> str:
    """Build an SVG horizontal timeline from v1.0 to v2.4 with change markers."""
    versions = ["1.0", "1.5", "2.0", "2.1", "2.2", "2.3", "2.4"]
    width = 760
    height = 100
    margin_x = 40
    usable = width - 2 * margin_x
    step = usable / (len(versions) - 1)
    y_line = 55

    # Map version string → x position
    def vx(v: str) -> float:
        idx = versions.index(v) if v in versions else None
        if idx is None:
            return margin_x
        return margin_x + idx * step

    lines = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;padding:8px;">',
        # Main axis
        f'<line x1="{margin_x}" y1="{y_line}" x2="{margin_x + usable}" y2="{y_line}" '
        f'stroke="#475569" stroke-width="2"/>',
    ]

    # Version tick marks and labels
    for i, v in enumerate(versions):
        x = margin_x + i * step
        lines.append(
            f'<line x1="{x}" y1="{y_line - 6}" x2="{x}" y2="{y_line + 6}" '
            f'stroke="#94a3b8" stroke-width="1.5"/>'
        )
        lines.append(
            f'<text x="{x}" y="{y_line + 22}" text-anchor="middle" '
            f'font-size="11" fill="#94a3b8" font-family="monospace">v{v}</text>'
        )

    # Change markers — place at the version_to position
    marker_r = 7
    # Track used x positions to offset overlapping markers
    x_count: dict[float, int] = {}
    for ch in changes:
        v_to = ch.version_to
        # Normalise: strip trailing .0 for lookup
        short = ".".join(v_to.split(".")[:2])
        x = vx(short) if short in versions else vx("2.4")
        color = _CHANGE_TYPE_COLORS[ch.change_type]
        offset_count = x_count.get(x, 0)
        x_count[x] = offset_count + 1
        y_marker = y_line - 28 - offset_count * 18
        lines.append(
            f'<circle cx="{x}" cy="{y_marker}" r="{marker_r}" fill="{color}" opacity="0.9"/>'
        )
        # Small label
        label = ch.change_type.value[0].upper()
        lines.append(
            f'<text x="{x}" y="{y_marker + 4}" text-anchor="middle" '
            f'font-size="9" fill="white" font-weight="bold" font-family="sans-serif">{label}</text>'
        )
        # Connector to axis
        lines.append(
            f'<line x1="{x}" y1="{y_marker + marker_r}" x2="{x}" y2="{y_line - 6}" '
            f'stroke="{color}" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>'
        )

    # Legend
    legend_items = [
        ("Breaking", "#ef4444"),
        ("Additive", "#22c55e"),
        ("Deprecation", "#f59e0b"),
    ]
    lx = margin_x
    ly = height - 10
    for label, color in legend_items:
        lines.append(
            f'<circle cx="{lx + 6}" cy="{ly}" r="5" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{lx + 15}" y="{ly + 4}" font-size="10" fill="#94a3b8" font-family="sans-serif">{label}</text>'
        )
        lx += 90

    lines.append("</svg>")
    return "\n".join(lines)


def _partner_row(p: PartnerCompatibility) -> str:
    compat_badge = (
        '<span style="color:#22c55e;font-weight:600;">Yes</span>'
        if p.compatible
        else '<span style="color:#ef4444;font-weight:600;">No</span>'
    )
    action = "None"
    if p.migration_required:
        action = '<span style="color:#ef4444;">Migrate SDK</span>'
    elif p.deprecation_warnings > 0:
        action = '<span style="color:#f59e0b;">Update endpoints</span>'
    return f"""
    <tr>
      <td>{p.partner_name}</td>
      <td><code>v{p.sdk_version}</code></td>
      <td><code>v{p.server_version}</code></td>
      <td>{compat_badge}</td>
      <td>{p.breaking_changes}</td>
      <td>{p.deprecation_warnings}</td>
      <td>{action}</td>
    </tr>"""


def _change_row(ch: APIChange) -> str:
    color = _CHANGE_TYPE_COLORS[ch.change_type]
    _, effort_color = _EFFORT_BADGE[ch.migration_effort]
    return f"""
    <tr>
      <td><code>v{ch.version_from}</code></td>
      <td><code>v{ch.version_to}</code></td>
      <td><span style="color:{color};font-weight:600;">{ch.change_type.value}</span></td>
      <td><code>{ch.endpoint}</code></td>
      <td>{ch.description}</td>
      <td><span style="color:{effort_color};">{ch.migration_effort.value}</span></td>
    </tr>"""


def _migration_cards(changes: list[APIChange]) -> str:
    breaking = [c for c in changes if c.change_type == ChangeType.BREAKING]
    if not breaking:
        return "<p style='color:#94a3b8;'>No breaking changes — all partners fully compatible.</p>"
    cards = []
    for ch in breaking:
        _, effort_color = _EFFORT_BADGE[ch.migration_effort]
        cards.append(f"""
    <div style="border:1px solid #ef4444;border-radius:8px;padding:16px;margin-bottom:12px;background:#1e1a2e;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-size:14px;font-weight:700;color:#ef4444;">Breaking: {ch.endpoint}</span>
        <span style="font-size:12px;color:{effort_color};">Effort: {ch.migration_effort.value}</span>
      </div>
      <p style="color:#e2e8f0;margin:4px 0;font-size:13px;">{ch.description}</p>
      <p style="color:#94a3b8;margin:4px 0;font-size:12px;">Introduced in v{ch.version_to} (from v{ch.version_from})</p>
      <div style="margin-top:10px;padding:10px;background:#0f172a;border-radius:6px;font-size:12px;color:#94a3b8;">
        <strong style="color:#e2e8f0;">Migration steps:</strong><br/>
        1. Bump your SDK dependency to <code style="color:#C74634;">v{ch.version_to}+</code>.<br/>
        2. Review the endpoint documentation for <code style="color:#C74634;">{ch.endpoint}</code>.<br/>
        3. Update any request payloads or auth headers according to the change description above.<br/>
        4. Re-run integration tests against the staging server before promoting to production.
      </div>
    </div>""")
    return "\n".join(cards)


def generate_html(report: CompatibilityReport) -> str:
    total_breaking = sum(c.breaking_changes for c in report.partner_results)
    timeline_svg = _version_timeline_svg(report.changes)
    partner_rows = "".join(_partner_row(p) for p in report.partner_results)
    change_rows = "".join(_change_row(ch) for ch in report.changes)
    migration_section = _migration_cards(report.changes)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — API Version Compatibility Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 0 0 60px;
    }}
    header {{
      background: #1e293b;
      border-bottom: 3px solid #C74634;
      padding: 20px 40px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    header h1 {{
      font-size: 22px;
      font-weight: 700;
      color: #f1f5f9;
    }}
    header .oracle-badge {{
      background: #C74634;
      color: white;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 4px;
      letter-spacing: 0.05em;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 0 24px; }}
    .section {{ margin-top: 36px; }}
    .section-title {{
      font-size: 16px;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid #334155;
    }}
    /* Stat cards */
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }}
    .stat-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 20px;
      text-align: center;
    }}
    .stat-card .label {{
      font-size: 12px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }}
    .stat-card .value {{
      font-size: 34px;
      font-weight: 700;
    }}
    .stat-card.accent .value {{ color: #C74634; }}
    .stat-card.green .value {{ color: #22c55e; }}
    .stat-card.amber .value {{ color: #f59e0b; }}
    .stat-card.red .value {{ color: #ef4444; }}
    /* Tables */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th {{
      background: #1e293b;
      color: #94a3b8;
      text-align: left;
      padding: 10px 14px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 2px solid #334155;
    }}
    td {{
      padding: 10px 14px;
      border-bottom: 1px solid #1e293b;
      color: #e2e8f0;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #1e293b44; }}
    .table-wrapper {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      overflow: hidden;
    }}
    code {{
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 12px;
      background: #0f172a;
      padding: 2px 6px;
      border-radius: 4px;
      color: #93c5fd;
    }}
    footer {{
      margin-top: 48px;
      text-align: center;
      font-size: 11px;
      color: #475569;
    }}
  </style>
</head>
<body>
<header>
  <div>
    <div class="oracle-badge">ORACLE</div>
  </div>
  <h1>OCI Robot Cloud &mdash; API Version Compatibility Report</h1>
</header>

<div class="container">

  <!-- Stat cards -->
  <div class="section">
    <div class="section-title">Summary</div>
    <div class="stats-grid">
      <div class="stat-card accent">
        <div class="label">Server Version</div>
        <div class="value" style="font-size:24px;">v{report.server_version}</div>
      </div>
      <div class="stat-card green">
        <div class="label">Compatible Partners</div>
        <div class="value">{report.n_compatible} / {report.n_partners}</div>
      </div>
      <div class="stat-card amber">
        <div class="label">Migration Required</div>
        <div class="value">{report.n_migration_required}</div>
      </div>
      <div class="stat-card red">
        <div class="label">Total Breaking Changes Seen</div>
        <div class="value">{total_breaking}</div>
      </div>
    </div>
  </div>

  <!-- Version timeline -->
  <div class="section">
    <div class="section-title">API Version Timeline (v1.0 &rarr; v2.4)</div>
    {timeline_svg}
  </div>

  <!-- Partner compatibility table -->
  <div class="section">
    <div class="section-title">Partner Compatibility</div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Partner</th>
            <th>SDK Version</th>
            <th>Server Version</th>
            <th>Compatible</th>
            <th>Breaking Changes</th>
            <th>Deprecation Warnings</th>
            <th>Action Needed</th>
          </tr>
        </thead>
        <tbody>
          {partner_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Change log table -->
  <div class="section">
    <div class="section-title">API Change Log</div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>From</th>
            <th>To</th>
            <th>Type</th>
            <th>Endpoint</th>
            <th>Description</th>
            <th>Migration Effort</th>
          </tr>
        </thead>
        <tbody>
          {change_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Migration guide -->
  <div class="section">
    <div class="section-title">Migration Guide — Breaking Changes</div>
    {migration_section}
  </div>

</div>

<footer>
  Generated by OCI Robot Cloud API Versioning Checker &bull; Server v{report.server_version} &bull; Oracle Confidential
</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(report: CompatibilityReport) -> None:
    print(f"\nOCI Robot Cloud — API Compatibility Summary")
    print(f"{'=' * 52}")
    print(f"  Server version    : v{report.server_version}")
    print(f"  Partners checked  : {report.n_partners}")
    print(f"  Compatible        : {report.n_compatible}")
    print(f"  Migration required: {report.n_migration_required}")
    print(f"\n{'Partner':<20} {'SDK':<10} {'Compatible':<12} {'Breaking':<10} {'Deprec':<8} {'Action'}")
    print(f"{'-'*20} {'-'*10} {'-'*12} {'-'*10} {'-'*8} {'-'*20}")
    for p in report.partner_results:
        compat = "YES" if p.compatible else "NO "
        action = "migrate" if p.migration_required else ("update" if p.deprecation_warnings else "-")
        print(f"{p.partner_name:<20} v{p.sdk_version:<9} {compat:<12} {p.breaking_changes:<10} {p.deprecation_warnings:<8} {action}")
    print()
    print(f"API Changes ({len(report.changes)} total):")
    for ch in report.changes:
        mark = {"breaking": "[BREAK]", "additive": "[ADD  ]", "deprecation": "[DEPREC]"}[ch.change_type.value]
        print(f"  {mark} v{ch.version_from} -> v{ch.version_to}  {ch.endpoint}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="API version compatibility checker for OCI Robot Cloud."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with simulated data (no live server required).",
    )
    parser.add_argument(
        "--output",
        default="/tmp/api_versioning_checker.html",
        help="Path for the HTML report (default: /tmp/api_versioning_checker.html).",
    )
    args = parser.parse_args()

    if args.mock:
        report = run_mock_check()
    else:
        print("No live server integration implemented yet. Use --mock to run with simulated data.")
        return

    print_summary(report)

    html = generate_html(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML report written to: {args.output}")


if __name__ == "__main__":
    main()
