#!/usr/bin/env python3
"""
oci_storage_manager.py — OCI Object Storage manager for robot training data.

Organizes datasets, checkpoints, eval results, and demo recordings into
structured buckets with lifecycle policies. Tracks costs and savings
opportunities across hot/cool/archive tiers.

Usage:
    python src/infra/oci_storage_manager.py --mock --output /tmp/oci_storage_manager.html
    python src/infra/oci_storage_manager.py --mock --seed 99 --output /tmp/report.html
"""

import argparse
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ── Cost constants (OCI Object Storage) ────────────────────────────────────────
COST_HOT_GB_MONTH     = 0.0255
COST_COOL_GB_MONTH    = 0.010
COST_ARCHIVE_GB_MONTH = 0.003

BUCKETS  = ["oci-robot-datasets", "oci-robot-checkpoints", "oci-robot-evals", "oci-robot-demos"]
PARTNERS = ["AgiBot", "Boston Dynamics", "Figure AI", "1X Technologies"]

BUCKET_OBJECT_TYPES = {
    "oci-robot-datasets":     "dataset",
    "oci-robot-checkpoints":  "checkpoint",
    "oci-robot-evals":        "eval_result",
    "oci-robot-demos":        "demo",
}

SIZE_RANGES_MB = {
    "dataset":     (100,   2000),
    "checkpoint":  (6000,  14000),
    "eval_result": (1,     10),
    "demo":        (50,    500),
    "telemetry":   (5,     50),
    "logs":        (1,     20),
}


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class StorageObject:
    object_name:    str
    bucket:         str
    size_mb:        float
    object_type:    str          # dataset/checkpoint/eval_result/demo/telemetry/logs
    partner:        str
    version:        str
    created_at:     datetime
    last_accessed:  datetime
    access_count:   int
    lifecycle_tier: str          # hot/cool/archive
    tags:           Dict[str, str] = field(default_factory=dict)


@dataclass
class BucketStats:
    bucket_name:            str
    partner:                str          # "mixed" for multi-partner buckets
    total_objects:          int
    total_size_gb:          float
    hot_size_gb:            float
    cool_size_gb:           float
    archive_size_gb:        float
    monthly_cost_usd:       float
    last_30day_ingress_gb:  float


# ── Mock data generation ─────────────────────────────────────────────────────────

def generate_mock_storage(n_objects: int = 200, seed: int = 42) -> List[StorageObject]:
    rng = random.Random(seed)
    now = datetime(2026, 3, 29, 12, 0, 0)
    objects: List[StorageObject] = []

    for i in range(n_objects):
        bucket       = rng.choice(BUCKETS)
        obj_type     = BUCKET_OBJECT_TYPES[bucket]
        partner      = rng.choice(PARTNERS)
        version      = f"v{rng.randint(1, 8)}.{rng.randint(0, 9)}"
        lo, hi       = SIZE_RANGES_MB[obj_type]
        size_mb      = round(rng.uniform(lo, hi), 2)

        # Spread creation across past 180 days
        days_old     = rng.randint(1, 180)
        created_at   = now - timedelta(days=days_old)

        # Last accessed: more recent than created; skewed toward recent
        access_lag   = rng.randint(0, days_old)
        last_accessed = now - timedelta(days=access_lag)
        access_count  = rng.randint(1, 200) if access_lag < 30 else rng.randint(0, 20)

        # Lifecycle tier: simulate real-world drift where ~25% of objects
        # haven't been re-tiered despite going stale (savings opportunity)
        drift = rng.random() < 0.25
        if access_lag < 30:
            tier = "hot"
        elif access_lag < 90:
            tier = "cool" if not drift else "hot"   # drift: stays hot when should be cool
        else:
            tier = "archive" if not drift else "cool"  # drift: stays cool when should be archive

        slug = obj_type.replace("_", "-")
        partner_slug = partner.lower().replace(" ", "-")
        obj_name = f"{partner_slug}/{slug}/{version}/obj_{i:04d}.bin"

        tags = {
            "partner": partner,
            "type":    obj_type,
            "version": version,
            "env":     rng.choice(["simulation", "real-world"]),
        }

        objects.append(StorageObject(
            object_name=obj_name,
            bucket=bucket,
            size_mb=size_mb,
            object_type=obj_type,
            partner=partner,
            version=version,
            created_at=created_at,
            last_accessed=last_accessed,
            access_count=access_count,
            lifecycle_tier=tier,
            tags=tags,
        ))

    return objects


# ── Analytics ──────────────────────────────────────────────────────────────────

def compute_lifecycle_savings(objects: List[StorageObject]) -> Dict[str, float]:
    """Return potential monthly savings by moving hot objects to cooler tiers."""
    hot_movable_gb   = 0.0   # hot, last accessed > 30 days → should be cool
    cool_movable_gb  = 0.0   # cool, last accessed > 90 days → should be archive
    now = datetime(2026, 3, 29, 12, 0, 0)

    for obj in objects:
        age_days = (now - obj.last_accessed).days
        size_gb  = obj.size_mb / 1024.0
        if obj.lifecycle_tier == "hot" and age_days > 30:
            hot_movable_gb += size_gb
        elif obj.lifecycle_tier == "cool" and age_days > 90:
            cool_movable_gb += size_gb

    hot_to_cool_savings  = hot_movable_gb  * (COST_HOT_GB_MONTH  - COST_COOL_GB_MONTH)
    cool_to_archive_savings = cool_movable_gb * (COST_COOL_GB_MONTH - COST_ARCHIVE_GB_MONTH)
    total_savings = hot_to_cool_savings + cool_to_archive_savings

    return {
        "hot_movable_gb":         round(hot_movable_gb,  2),
        "cool_movable_gb":        round(cool_movable_gb, 2),
        "hot_to_cool_savings":    round(hot_to_cool_savings, 4),
        "cool_to_archive_savings": round(cool_to_archive_savings, 4),
        "total_monthly_savings":  round(total_savings, 4),
    }


def generate_bucket_stats(objects: List[StorageObject]) -> List[BucketStats]:
    now = datetime(2026, 3, 29, 12, 0, 0)
    stats: Dict[str, dict] = {}

    for obj in objects:
        b = obj.bucket
        if b not in stats:
            stats[b] = {
                "total_objects": 0, "hot_gb": 0.0, "cool_gb": 0.0,
                "archive_gb": 0.0, "ingress_gb": 0.0, "partners": set(),
            }
        s       = stats[b]
        size_gb = obj.size_mb / 1024.0
        s["total_objects"] += 1
        s["partners"].add(obj.partner)

        if obj.lifecycle_tier == "hot":
            s["hot_gb"] += size_gb
        elif obj.lifecycle_tier == "cool":
            s["cool_gb"] += size_gb
        else:
            s["archive_gb"] += size_gb

        if (now - obj.created_at).days <= 30:
            s["ingress_gb"] += size_gb

    result = []
    for bucket_name, s in stats.items():
        hot_gb     = round(s["hot_gb"], 3)
        cool_gb    = round(s["cool_gb"], 3)
        archive_gb = round(s["archive_gb"], 3)
        total_gb   = round(hot_gb + cool_gb + archive_gb, 3)
        cost       = round(hot_gb * COST_HOT_GB_MONTH + cool_gb * COST_COOL_GB_MONTH
                           + archive_gb * COST_ARCHIVE_GB_MONTH, 4)
        partners   = s["partners"]
        partner_label = list(partners)[0] if len(partners) == 1 else "mixed"

        result.append(BucketStats(
            bucket_name=bucket_name,
            partner=partner_label,
            total_objects=s["total_objects"],
            total_size_gb=total_gb,
            hot_size_gb=hot_gb,
            cool_size_gb=cool_gb,
            archive_size_gb=archive_gb,
            monthly_cost_usd=cost,
            last_30day_ingress_gb=round(s["ingress_gb"], 3),
        ))

    return sorted(result, key=lambda x: x.total_size_gb, reverse=True)


# ── HTML Report ────────────────────────────────────────────────────────────────

def _stacked_bar_svg(bucket_stats: List[BucketStats]) -> str:
    """SVG: storage by bucket × tier (stacked horizontal bars)."""
    bar_h, gap, lpad, top_pad = 38, 12, 220, 40
    height = top_pad + len(bucket_stats) * (bar_h + gap) + 50
    max_gb = max(s.total_size_gb for s in bucket_stats) or 1
    bar_area = 520

    rows = ""
    for i, s in enumerate(bucket_stats):
        y      = top_pad + i * (bar_h + gap)
        label  = s.bucket_name.replace("oci-robot-", "")
        hot_w  = (s.hot_size_gb  / max_gb) * bar_area
        cool_w = (s.cool_size_gb / max_gb) * bar_area
        arc_w  = (s.archive_size_gb / max_gb) * bar_area
        x      = lpad

        rows += f'<text x="{lpad-8}" y="{y+bar_h//2+5}" text-anchor="end" fill="#94a3b8" font-size="12">{label}</text>\n'
        if hot_w > 0:
            rows += f'<rect x="{x}" y="{y}" width="{hot_w:.1f}" height="{bar_h}" fill="#C74634" rx="3"/>\n'
            if hot_w > 35:
                rows += f'<text x="{x+hot_w/2:.1f}" y="{y+bar_h//2+5}" text-anchor="middle" fill="#fff" font-size="10">{s.hot_size_gb:.1f}GB</text>\n'
            x += hot_w
        if cool_w > 0:
            rows += f'<rect x="{x:.1f}" y="{y}" width="{cool_w:.1f}" height="{bar_h}" fill="#f97316" rx="3"/>\n'
            if cool_w > 35:
                rows += f'<text x="{x+cool_w/2:.1f}" y="{y+bar_h//2+5}" text-anchor="middle" fill="#fff" font-size="10">{s.cool_size_gb:.1f}GB</text>\n'
            x += cool_w
        if arc_w > 0:
            rows += f'<rect x="{x:.1f}" y="{y}" width="{arc_w:.1f}" height="{bar_h}" fill="#64748b" rx="3"/>\n'
            if arc_w > 35:
                rows += f'<text x="{x+arc_w/2:.1f}" y="{y+bar_h//2+5}" text-anchor="middle" fill="#fff" font-size="10">{s.archive_size_gb:.1f}GB</text>\n'

    legend = (
        f'<rect x="{lpad}" y="{height-30}" width="14" height="14" fill="#C74634" rx="2"/>'
        f'<text x="{lpad+18}" y="{height-19}" fill="#94a3b8" font-size="11">Hot</text>'
        f'<rect x="{lpad+65}" y="{height-30}" width="14" height="14" fill="#f97316" rx="2"/>'
        f'<text x="{lpad+83}" y="{height-19}" fill="#94a3b8" font-size="11">Cool</text>'
        f'<rect x="{lpad+140}" y="{height-30}" width="14" height="14" fill="#64748b" rx="2"/>'
        f'<text x="{lpad+158}" y="{height-19}" fill="#94a3b8" font-size="11">Archive</text>'
    )

    return (f'<svg width="760" height="{height}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#0f172a;border-radius:8px">'
            f'<text x="{lpad}" y="22" fill="#C74634" font-size="13" font-weight="bold">'
            f'Storage by Bucket &amp; Tier (GB)</text>'
            f'{rows}{legend}</svg>')


def _cost_bar_svg(objects: List[StorageObject]) -> str:
    """SVG: monthly cost breakdown by partner (horizontal bars)."""
    partner_cost: Dict[str, float] = {}
    for obj in objects:
        gb   = obj.size_mb / 1024.0
        rate = {"hot": COST_HOT_GB_MONTH, "cool": COST_COOL_GB_MONTH,
                "archive": COST_ARCHIVE_GB_MONTH}[obj.lifecycle_tier]
        partner_cost[obj.partner] = partner_cost.get(obj.partner, 0.0) + gb * rate

    partners = sorted(partner_cost.items(), key=lambda x: x[1], reverse=True)
    bar_h, gap, lpad, top_pad = 36, 14, 175, 40
    height   = top_pad + len(partners) * (bar_h + gap) + 30
    max_cost = max(v for _, v in partners) or 1
    bar_area = 430

    rows = ""
    for i, (name, cost) in enumerate(partners):
        y = top_pad + i * (bar_h + gap)
        w = (cost / max_cost) * bar_area
        rows += (f'<text x="{lpad-8}" y="{y+bar_h//2+5}" text-anchor="end" fill="#94a3b8" font-size="12">{name}</text>\n'
                 f'<rect x="{lpad}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="#C74634" rx="3"/>\n'
                 f'<text x="{lpad+w+6:.1f}" y="{y+bar_h//2+5}" fill="#e2e8f0" font-size="11">${cost:.3f}/mo</text>\n')

    return (f'<svg width="680" height="{height}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#0f172a;border-radius:8px">'
            f'<text x="{lpad}" y="22" fill="#C74634" font-size="13" font-weight="bold">'
            f'Monthly Cost by Partner (USD)</text>'
            f'{rows}</svg>')


def build_html_report(objects: List[StorageObject],
                      bucket_stats: List[BucketStats],
                      savings: Dict[str, float]) -> str:
    now_str        = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    total_objects  = len(objects)
    total_size_gb  = sum(s.total_size_gb for s in bucket_stats)
    total_cost     = sum(s.monthly_cost_usd for s in bucket_stats)
    largest_bucket = max(bucket_stats, key=lambda s: s.total_size_gb).bucket_name
    savings_opp    = savings["total_monthly_savings"]

    def kpi(label, value, sub=""):
        return (f'<div class="kpi"><div class="kpi-value">{value}</div>'
                f'<div class="kpi-label">{label}</div>'
                + (f'<div class="kpi-sub">{sub}</div>' if sub else "")
                + '</div>')

    kpis = (
        kpi("Total Objects",        f"{total_objects:,}") +
        kpi("Total Storage",        f"{total_size_gb:.1f} GB") +
        kpi("Monthly Cost",         f"${total_cost:.2f}") +
        kpi("Archive Savings Opp.", f"${savings_opp:.2f}/mo",
            f"{savings['hot_movable_gb']:.1f}GB movable") +
        kpi("Largest Bucket",       largest_bucket.replace("oci-robot-", ""))
    )

    # Lifecycle savings table
    lc_rows = ""
    for s in bucket_stats:
        current = s.monthly_cost_usd
        # Optimized: move all cool→archive, all hot→cool if age allows
        # Use simple proxy: keep hot for objects accessed < 30d
        opt_hot  = s.hot_size_gb  * COST_COOL_GB_MONTH
        opt_cool = s.cool_size_gb * COST_ARCHIVE_GB_MONTH
        opt_arc  = s.archive_size_gb * COST_ARCHIVE_GB_MONTH
        optimized = opt_hot + opt_cool + opt_arc
        pct  = (current - optimized) / current * 100 if current > 0 else 0
        rec  = "Move cool→archive; downgrade idle hot" if pct > 10 else "Tier policy optimal"
        lc_rows += (f'<tr><td>{s.bucket_name}</td>'
                    f'<td>${current:.3f}</td>'
                    f'<td>${optimized:.3f}</td>'
                    f'<td class="savings">{pct:.1f}%</td>'
                    f'<td>{rec}</td></tr>\n')

    # Top 15 largest objects
    top15 = sorted(objects, key=lambda o: o.size_mb, reverse=True)[:15]
    obj_rows = ""
    for o in top15:
        size_str = f"{o.size_mb/1024:.2f} GB" if o.size_mb > 1000 else f"{o.size_mb:.0f} MB"
        tier_cls = {"hot": "tier-hot", "cool": "tier-cool", "archive": "tier-arc"}[o.lifecycle_tier]
        obj_rows += (f'<tr><td class="mono">{o.object_name}</td>'
                     f'<td>{o.bucket.replace("oci-robot-","")}</td>'
                     f'<td>{size_str}</td>'
                     f'<td><span class="{tier_cls}">{o.lifecycle_tier}</span></td>'
                     f'<td>{o.partner}</td>'
                     f'<td>{o.last_accessed.strftime("%Y-%m-%d")}</td></tr>\n')

    bar_svg  = _stacked_bar_svg(bucket_stats)
    cost_svg = _cost_bar_svg(objects)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Storage Manager</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
          font-size: 14px; line-height: 1.5; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 16px; margin: 28px 0 12px; border-bottom: 1px solid #334155;
        padding-bottom: 6px; }}
  .meta {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
  .kpi-grid {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .kpi {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
          padding: 18px 22px; min-width: 150px; flex: 1; }}
  .kpi-value {{ font-size: 26px; font-weight: 700; color: #C74634; }}
  .kpi-label {{ color: #94a3b8; font-size: 12px; margin-top: 4px; text-transform: uppercase;
                letter-spacing: .04em; }}
  .kpi-sub {{ color: #64748b; font-size: 11px; margin-top: 2px; }}
  .svg-wrap {{ overflow-x: auto; margin-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
  thead tr {{ background: #0f172a; }}
  th {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
        padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #1e3a5f22; }}
  .savings {{ color: #22c55e; font-weight: 600; }}
  .mono {{ font-family: 'Courier New', monospace; font-size: 12px; color: #94a3b8;
           max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .tier-hot  {{ background: #C7463422; color: #f87171; padding: 2px 8px; border-radius: 12px;
                font-size: 11px; font-weight: 600; }}
  .tier-cool {{ background: #f9731622; color: #fb923c; padding: 2px 8px; border-radius: 12px;
                font-size: 11px; font-weight: 600; }}
  .tier-arc  {{ background: #64748b22; color: #94a3b8; padding: 2px 8px; border-radius: 12px;
                font-size: 11px; font-weight: 600; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Storage Manager</h1>
<p class="meta">Generated {now_str} &nbsp;|&nbsp; {total_objects} objects &nbsp;|&nbsp; {len(bucket_stats)} buckets</p>

<div class="kpi-grid">{kpis}</div>

<h2>Storage by Bucket &amp; Tier</h2>
<div class="svg-wrap">{bar_svg}</div>

<h2>Monthly Cost by Partner</h2>
<div class="svg-wrap">{cost_svg}</div>

<h2>Lifecycle Savings Analysis</h2>
<table>
  <thead><tr><th>Bucket</th><th>Current Cost</th><th>Optimized Cost</th>
  <th>Savings %</th><th>Recommendation</th></tr></thead>
  <tbody>{lc_rows}</tbody>
</table>

<h2>Top 15 Largest Objects</h2>
<table>
  <thead><tr><th>Object Name</th><th>Bucket</th><th>Size</th>
  <th>Tier</th><th>Partner</th><th>Last Accessed</th></tr></thead>
  <tbody>{obj_rows}</tbody>
</table>
</body>
</html>"""


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="OCI Object Storage manager for robot training data")
    parser.add_argument("--mock",   action="store_true",  help="Use mock data")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--output", type=str, default="/tmp/oci_storage_manager.html",
                        help="Output HTML report path")
    args = parser.parse_args()

    if args.mock:
        print(f"Generating mock storage data (n=200, seed={args.seed})...")
        objects = generate_mock_storage(n_objects=200, seed=args.seed)
    else:
        print("No OCI credentials configured. Use --mock for demo data.")
        return

    bucket_stats = generate_bucket_stats(objects)
    savings      = compute_lifecycle_savings(objects)

    total_gb   = sum(s.total_size_gb for s in bucket_stats)
    total_cost = sum(s.monthly_cost_usd for s in bucket_stats)
    print(f"  {len(objects)} objects | {total_gb:.1f} GB | ${total_cost:.2f}/mo")
    print(f"  Savings opportunity: ${savings['total_monthly_savings']:.2f}/mo "
          f"({savings['hot_movable_gb']:.1f}GB hot→cool, "
          f"{savings['cool_movable_gb']:.1f}GB cool→archive)")

    html = build_html_report(objects, bucket_stats, savings)
    out  = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  Report saved: {out}")


if __name__ == "__main__":
    main()
