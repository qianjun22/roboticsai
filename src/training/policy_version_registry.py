"""
Policy Version Registry — CLI + library tool for GR00T policy governance.

Usage:
    python policy_version_registry.py --list
    python policy_version_registry.py --lineage dagger_run4_iter3
    python policy_version_registry.py --promote dagger_run5 staging
    python policy_version_registry.py --compare dagger_run4_iter3 dagger_run5
    python policy_version_registry.py --report /tmp/policy_versions.html
    python policy_version_registry.py --seed
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

REGISTRY_PATH = "/tmp/policy_registry.json"

STAGE_ORDER = ["draft", "staging", "production", "archived"]

STAGE_BADGE_COLORS = {
    "draft": "#6B7280",
    "staging": "#D97706",
    "production": "#059669",
    "archived": "#374151",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PolicyVersion:
    version_id: str
    checkpoint_path: str
    training_method: str          # "BC" | "DAgger" | "DAgger+Curriculum" | "Transfer"
    base_version: Optional[str]   # parent version_id (None = root)
    n_demos: int
    n_steps: int
    success_rate: float           # 0–1
    mae: float
    latency_p50_ms: float
    training_cost_usd: float
    stage: str                    # "draft" | "staging" | "production" | "archived"
    created_at: str               # ISO-8601
    promoted_at: Optional[str]    # ISO-8601 or None
    notes: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyVersion":
        return cls(**d)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PolicyRegistry:
    def __init__(self, path: str = REGISTRY_PATH):
        self.path = path
        self._data: Dict[str, dict] = {}
        self._load()

    # --- persistence -------------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    # --- core API ----------------------------------------------------------

    def register(self, version: PolicyVersion) -> None:
        """Add or overwrite a version in the registry."""
        self._data[version.version_id] = version.to_dict()
        self._save()
        print(f"[registry] Registered {version.version_id} ({version.stage})")

    def promote(self, version_id: str, stage: str) -> PolicyVersion:
        """Update stage and set promoted_at timestamp."""
        if stage not in STAGE_ORDER:
            raise ValueError(f"Unknown stage '{stage}'. Choose from {STAGE_ORDER}")
        v = self.get(version_id)
        v.stage = stage
        v.promoted_at = datetime.now(timezone.utc).isoformat()
        self._data[version_id] = v.to_dict()
        self._save()
        print(f"[registry] Promoted {version_id} → {stage} at {v.promoted_at}")
        return v

    def get(self, version_id: str) -> PolicyVersion:
        if version_id not in self._data:
            raise KeyError(f"Version '{version_id}' not found in registry.")
        return PolicyVersion.from_dict(self._data[version_id])

    def lineage(self, version_id: str) -> List[PolicyVersion]:
        """Return chain from this version back to the root (oldest first)."""
        chain: List[PolicyVersion] = []
        current_id: Optional[str] = version_id
        visited = set()
        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            v = self.get(current_id)
            chain.append(v)
            current_id = v.base_version
        chain.reverse()
        return chain

    def production_version(self) -> Optional[PolicyVersion]:
        """Return the current production PolicyVersion (or None)."""
        for d in self._data.values():
            if d["stage"] == "production":
                return PolicyVersion.from_dict(d)
        return None

    def list_versions(self, stage: Optional[str] = None) -> List[PolicyVersion]:
        """Return all versions, optionally filtered by stage, sorted by created_at."""
        versions = [PolicyVersion.from_dict(d) for d in self._data.values()]
        if stage:
            versions = [v for v in versions if v.stage == stage]
        versions.sort(key=lambda v: v.created_at)
        return versions

    def compare(self, v1_id: str, v2_id: str) -> dict:
        """Return delta metrics between two versions (v2 - v1)."""
        v1 = self.get(v1_id)
        v2 = self.get(v2_id)

        def delta(a, b):
            if a is None or b is None:
                return None
            return round(b - a, 6)

        def pct(a, b):
            if not a:
                return None
            return round((b - a) / abs(a) * 100, 2)

        return {
            "v1": v1_id,
            "v2": v2_id,
            "success_rate": {"v1": v1.success_rate, "v2": v2.success_rate,
                             "delta": delta(v1.success_rate, v2.success_rate),
                             "pct_change": pct(v1.success_rate, v2.success_rate)},
            "mae": {"v1": v1.mae, "v2": v2.mae,
                    "delta": delta(v1.mae, v2.mae),
                    "pct_change": pct(v1.mae, v2.mae)},
            "latency_p50_ms": {"v1": v1.latency_p50_ms, "v2": v2.latency_p50_ms,
                               "delta": delta(v1.latency_p50_ms, v2.latency_p50_ms),
                               "pct_change": pct(v1.latency_p50_ms, v2.latency_p50_ms)},
            "training_cost_usd": {"v1": v1.training_cost_usd, "v2": v2.training_cost_usd,
                                  "delta": delta(v1.training_cost_usd, v2.training_cost_usd),
                                  "pct_change": pct(v1.training_cost_usd, v2.training_cost_usd)},
        }


# ---------------------------------------------------------------------------
# Mock seed data
# ---------------------------------------------------------------------------

SEED_VERSIONS = [
    PolicyVersion(
        version_id="bc_500demo",
        checkpoint_path="/tmp/checkpoints/bc_500demo/checkpoint-2000",
        training_method="BC",
        base_version=None,
        n_demos=500,
        n_steps=2000,
        success_rate=0.05,
        mae=0.103,
        latency_p50_ms=226.0,
        training_cost_usd=0.86,
        stage="archived",
        created_at="2026-01-10T08:00:00+00:00",
        promoted_at="2026-01-12T10:00:00+00:00",
        notes="Initial BC baseline on 500 IK-planned demos. Low success, no fine-tuning.",
        tags=["baseline", "bc", "ik-sdg"],
    ),
    PolicyVersion(
        version_id="bc_1000demo",
        checkpoint_path="/tmp/checkpoints/bc_1000demo/checkpoint-2000",
        training_method="BC",
        base_version="bc_500demo",
        n_demos=1000,
        n_steps=2000,
        success_rate=0.10,
        mae=0.073,
        latency_p50_ms=224.0,
        training_cost_usd=1.72,
        stage="archived",
        created_at="2026-01-18T09:00:00+00:00",
        promoted_at="2026-01-20T11:00:00+00:00",
        notes="Doubled demo count. MAE improved 29%, success 2×. Promoted to staging then archived.",
        tags=["bc", "ik-sdg", "1k-demos"],
    ),
    PolicyVersion(
        version_id="dagger_run4_iter1",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter1/checkpoint-5000",
        training_method="DAgger",
        base_version="bc_1000demo",
        n_demos=1000,
        n_steps=5000,
        success_rate=0.20,
        mae=0.051,
        latency_p50_ms=227.0,
        training_cost_usd=2.15,
        stage="archived",
        created_at="2026-02-01T10:00:00+00:00",
        promoted_at="2026-02-03T14:00:00+00:00",
        notes="First DAgger iteration. Closed-loop corrections on bc_1000demo. 4× success vs BC baseline.",
        tags=["dagger", "run4", "iter1"],
    ),
    PolicyVersion(
        version_id="dagger_run4_iter3",
        checkpoint_path="/tmp/checkpoints/dagger_run4/iter3/checkpoint-5000",
        training_method="DAgger",
        base_version="dagger_run4_iter1",
        n_demos=1000,
        n_steps=5000,
        success_rate=0.45,
        mae=0.031,
        latency_p50_ms=231.0,
        training_cost_usd=4.30,
        stage="production",
        created_at="2026-02-14T12:00:00+00:00",
        promoted_at="2026-02-16T09:00:00+00:00",
        notes="Production release. 3 DAgger iterations, 9× success over BC baseline. Stable latency.",
        tags=["dagger", "run4", "iter3", "production"],
    ),
    PolicyVersion(
        version_id="dagger_run5",
        checkpoint_path="/tmp/checkpoints/dagger_run5/checkpoint-5000",
        training_method="DAgger",
        base_version="dagger_run4_iter3",
        n_demos=1000,
        n_steps=5000,
        success_rate=0.05,
        mae=0.099,
        latency_p50_ms=226.0,
        training_cost_usd=4.30,
        stage="staging",
        created_at="2026-03-01T10:00:00+00:00",
        promoted_at="2026-03-15T11:00:00+00:00",
        notes="DAgger run5: 3 bugfixes (chunk_step reset, cube_z sanity, --checkpoint flag). "
              "Low eval success (1/20) due to insufficient correction episodes (99 vs 1000 BC). "
              "Needs longer DAgger rollout before production promotion.",
        tags=["dagger", "run5", "staging", "bugfix"],
    ),
    PolicyVersion(
        version_id="dagger_run6_projected",
        checkpoint_path="/tmp/checkpoints/dagger_run6/checkpoint-10000",
        training_method="DAgger+Curriculum",
        base_version="dagger_run5",
        n_demos=2000,
        n_steps=10000,
        success_rate=0.70,
        mae=0.018,
        latency_p50_ms=228.0,
        training_cost_usd=8.60,
        stage="draft",
        created_at="2026-03-28T08:00:00+00:00",
        promoted_at=None,
        notes="Projected: curriculum SDG (easy→hard) + 2000 demos + 10k steps. Target 70% success.",
        tags=["dagger", "curriculum", "run6", "projected", "draft"],
    ),
]


def seed_registry(registry: PolicyRegistry) -> None:
    for v in SEED_VERSIONS:
        registry.register(v)
    print(f"[registry] Seeded {len(SEED_VERSIONS)} versions.")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_pct(val: Optional[float], invert: bool = False) -> str:
    """Format a percent-change value with color hint for CLI output."""
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def _ascii_tree(registry: PolicyRegistry) -> str:
    """Build an ASCII lineage tree for all versions."""
    versions = registry.list_versions()
    children: Dict[Optional[str], List[str]] = {}
    for v in versions:
        children.setdefault(v.base_version, []).append(v.version_id)

    lines = []

    def walk(vid: str, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        try:
            v = registry.get(vid)
            badge = f"[{v.stage.upper()}]"
            lines.append(f"{prefix}{connector}{vid}  {badge}  sr={v.success_rate:.0%}  mae={v.mae:.3f}")
        except KeyError:
            lines.append(f"{prefix}{connector}{vid}")
        extension = "    " if is_last else "│   "
        kids = children.get(vid, [])
        for i, kid in enumerate(kids):
            walk(kid, prefix + extension, i == len(kids) - 1)

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        walk(root, "", i == len(roots) - 1)

    return "\n".join(lines)


def _versions_table(versions: List[PolicyVersion]) -> str:
    header = (
        f"{'Version':<28} {'Method':<22} {'Stage':<12} "
        f"{'Success':>8} {'MAE':>7} {'P50ms':>7} {'Cost$':>7} {'Demos':>6}"
    )
    sep = "-" * len(header)
    rows = [header, sep]
    for v in versions:
        rows.append(
            f"{v.version_id:<28} {v.training_method:<22} {v.stage:<12} "
            f"{v.success_rate:>7.1%} {v.mae:>7.3f} {v.latency_p50_ms:>7.1f} "
            f"{v.training_cost_usd:>7.2f} {v.n_demos:>6}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(registry: PolicyRegistry, output_path: str) -> None:
    versions = registry.list_versions()
    prod = registry.production_version()
    tree_text = _ascii_tree(registry)

    def badge_html(stage: str) -> str:
        color = STAGE_BADGE_COLORS.get(stage, "#6B7280")
        return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:0.8em;font-weight:600;">'
                f'{stage.upper()}</span>')

    rows_html = ""
    for v in versions:
        rows_html += (
            f"<tr>"
            f"<td>{v.version_id}</td>"
            f"<td>{v.training_method}</td>"
            f"<td>{badge_html(v.stage)}</td>"
            f"<td>{v.success_rate:.1%}</td>"
            f"<td>{v.mae:.3f}</td>"
            f"<td>{v.latency_p50_ms:.1f}</td>"
            f"<td>${v.training_cost_usd:.2f}</td>"
            f"<td>{v.n_demos}</td>"
            f"<td>{v.n_steps:,}</td>"
            f"<td style='font-size:0.8em;color:#9CA3AF'>{', '.join(v.tags)}</td>"
            f"</tr>\n"
        )

    prod_html = ""
    if prod:
        prod_html = f"""
        <div style="background:#064E3B;border:1px solid #059669;border-radius:8px;padding:20px;margin-bottom:24px;">
          <h2 style="color:#34D399;margin-top:0;">Production Version: {prod.version_id}</h2>
          <table style="width:100%;color:#D1FAE5;font-size:0.95em;">
            <tr>
              <td><b>Method:</b> {prod.training_method}</td>
              <td><b>Success Rate:</b> {prod.success_rate:.1%}</td>
              <td><b>MAE:</b> {prod.mae:.3f}</td>
            </tr>
            <tr>
              <td><b>Demos:</b> {prod.n_demos}</td>
              <td><b>Latency P50:</b> {prod.latency_p50_ms:.1f} ms</td>
              <td><b>Training Cost:</b> ${prod.training_cost_usd:.2f}</td>
            </tr>
            <tr>
              <td colspan="3"><b>Notes:</b> {prod.notes}</td>
            </tr>
            <tr>
              <td colspan="3"><b>Checkpoint:</b> <code style="color:#6EE7B7">{prod.checkpoint_path}</code></td>
            </tr>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Robot Cloud — Policy Version Registry</title>
  <style>
    body {{ background:#111827; color:#F9FAFB; font-family:'Menlo','Courier New',monospace; padding:32px; }}
    h1 {{ color:#60A5FA; border-bottom:1px solid #374151; padding-bottom:8px; }}
    h2 {{ color:#93C5FD; margin-top:28px; }}
    pre {{ background:#1F2937; padding:16px; border-radius:6px; overflow-x:auto;
           font-size:0.85em; color:#D1D5DB; line-height:1.5; }}
    table {{ border-collapse:collapse; width:100%; margin-top:12px; }}
    th {{ background:#1F2937; color:#9CA3AF; padding:8px 12px; text-align:left;
          border-bottom:2px solid #374151; font-size:0.85em; }}
    td {{ padding:8px 12px; border-bottom:1px solid #1F2937; font-size:0.85em; color:#E5E7EB; vertical-align:middle; }}
    tr:hover td {{ background:#1F2937; }}
    code {{ font-family:inherit; }}
    .footer {{ color:#6B7280; font-size:0.78em; margin-top:32px; border-top:1px solid #374151; padding-top:8px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Policy Version Registry</h1>
  <p style="color:#9CA3AF">Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

  {prod_html}

  <h2>Lineage Graph</h2>
  <pre>{tree_text}</pre>

  <h2>All Versions</h2>
  <table>
    <thead>
      <tr>
        <th>Version ID</th><th>Method</th><th>Stage</th>
        <th>Success</th><th>MAE</th><th>P50 (ms)</th>
        <th>Cost</th><th>Demos</th><th>Steps</th><th>Tags</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <div class="footer">OCI Robot Cloud — GR00T Fine-Tuning Pipeline | github.com/qianjun22/roboticsai</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"[registry] HTML report written to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Policy Version Registry — GR00T model governance tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--registry", default=REGISTRY_PATH,
                        help=f"Path to JSON registry file (default: {REGISTRY_PATH})")
    parser.add_argument("--seed", action="store_true",
                        help="Populate registry with mock seed data")
    parser.add_argument("--list", action="store_true",
                        help="Print all versions as a table")
    parser.add_argument("--stage", metavar="STAGE",
                        help="Filter --list by stage (draft/staging/production/archived)")
    parser.add_argument("--lineage", metavar="VERSION_ID",
                        help="Show lineage chain for a version")
    parser.add_argument("--promote", nargs=2, metavar=("VERSION_ID", "STAGE"),
                        help="Promote a version to a new stage")
    parser.add_argument("--compare", nargs=2, metavar=("V1", "V2"),
                        help="Compare two versions (delta metrics)")
    parser.add_argument("--report", metavar="OUTPUT_PATH",
                        help="Generate HTML report at given path")
    parser.add_argument("--production", action="store_true",
                        help="Show current production version")

    args = parser.parse_args()
    registry = PolicyRegistry(path=args.registry)

    if args.seed:
        seed_registry(registry)
        return

    if args.list:
        versions = registry.list_versions(stage=args.stage)
        if not versions:
            print("No versions found.")
            return
        print(_versions_table(versions))
        return

    if args.lineage:
        chain = registry.lineage(args.lineage)
        print(f"Lineage for '{args.lineage}' ({len(chain)} versions):\n")
        for i, v in enumerate(chain):
            arrow = "  " * i + ("" if i == 0 else "└─ ")
            print(f"  {arrow}{v.version_id}  [{v.stage}]  sr={v.success_rate:.1%}  mae={v.mae:.3f}")
        return

    if args.promote:
        version_id, stage = args.promote
        registry.promote(version_id, stage)
        return

    if args.compare:
        v1_id, v2_id = args.compare
        diff = registry.compare(v1_id, v2_id)
        print(f"\nComparison: {v1_id}  vs  {v2_id}\n")
        print(f"  {'Metric':<22} {'v1':>10} {'v2':>10} {'delta':>10} {'% change':>10}")
        print("  " + "-" * 64)
        for metric in ["success_rate", "mae", "latency_p50_ms", "training_cost_usd"]:
            d = diff[metric]
            pct_str = _fmt_pct(d["pct_change"])
            print(f"  {metric:<22} {d['v1']:>10.4f} {d['v2']:>10.4f} {d['delta']:>+10.4f} {pct_str:>10}")
        return

    if args.report:
        generate_html_report(registry, args.report)
        return

    if args.production:
        prod = registry.production_version()
        if prod:
            print(f"\nProduction: {prod.version_id}")
            print(f"  Method:    {prod.training_method}")
            print(f"  Success:   {prod.success_rate:.1%}")
            print(f"  MAE:       {prod.mae:.3f}")
            print(f"  P50 ms:    {prod.latency_p50_ms:.1f}")
            print(f"  Cost:      ${prod.training_cost_usd:.2f}")
            print(f"  Promoted:  {prod.promoted_at}")
            print(f"  Notes:     {prod.notes}")
        else:
            print("No production version currently set.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
