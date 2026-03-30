"""
API feature adoption analytics for OCI Robot Cloud. Tracks feature usage patterns
across design partners to guide product and upsell strategy.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FeatureUsage:
    feature_name: str
    partner_name: str
    first_used_day: int        # days since onboarding
    calls_30d: int
    active: bool
    satisfaction: float        # 1.0 – 5.0


@dataclass
class PartnerAdoption:
    partner_name: str
    tier: str
    features_adopted: int
    features_available: int
    adoption_pct: float
    power_features: list[str]
    unused_features: list[str]


@dataclass
class FeatureReport:
    most_popular_feature: str
    least_adopted_feature: str
    avg_adoption_pct: float
    upsell_opportunities: list[dict]
    features: list[FeatureUsage]
    partner_profiles: list[PartnerAdoption]


# ---------------------------------------------------------------------------
# Feature catalog
# ---------------------------------------------------------------------------

FEATURES_BY_TIER: dict[str, list[str]] = {
    "pilot": [
        "inference",
        "fine_tune",
        "closed_loop_eval",
        "checkpoint_save",
        "basic_sdg",
        "usage_dashboard",
    ],
    "growth": [
        "dagger_training",
        "multi_task_eval",
        "advanced_sdg",
    ],
    "enterprise": [
        "federated_learning",
        "embodiment_adapter",
        "custom_rewards",
        "priority_gpu",
        "white_label",
        "dedicated_support",
    ],
}

FEATURE_TIER: dict[str, str] = {
    f: tier for tier, feats in FEATURES_BY_TIER.items() for f in feats
}

ALL_FEATURES: list[str] = (
    FEATURES_BY_TIER["pilot"]
    + FEATURES_BY_TIER["growth"]
    + FEATURES_BY_TIER["enterprise"]
)

TIER_ORDER = ["pilot", "growth", "enterprise"]

# Features accessible per partner tier (cumulative)
TIER_ACCESS: dict[str, list[str]] = {
    "pilot": FEATURES_BY_TIER["pilot"],
    "growth": FEATURES_BY_TIER["pilot"] + FEATURES_BY_TIER["growth"],
    "enterprise": ALL_FEATURES,
}

TIER_COLORS: dict[str, str] = {
    "pilot": "#3B82F6",
    "growth": "#10B981",
    "enterprise": "#C74634",
}


# ---------------------------------------------------------------------------
# Partner simulation
# ---------------------------------------------------------------------------

def _make_usage(
    rng: random.Random,
    feature: str,
    partner: str,
    calls_30d: int,
    active: bool,
    satisfaction: float,
) -> FeatureUsage:
    first_used_day = rng.randint(1, 30) if calls_30d > 0 else 0
    return FeatureUsage(
        feature_name=feature,
        partner_name=partner,
        first_used_day=first_used_day,
        calls_30d=calls_30d,
        active=active,
        satisfaction=round(satisfaction, 1),
    )


def generate_mock_data(seed: int = 42) -> list[FeatureUsage]:
    rng = random.Random(seed)
    usages: list[FeatureUsage] = []

    # partner_alpha — enterprise, 11/15, misses federated + custom_rewards
    alpha_skip = {"federated_learning", "custom_rewards"}
    for f in TIER_ACCESS["enterprise"]:
        if f in alpha_skip:
            usages.append(_make_usage(rng, f, "partner_alpha", 0, False, 0.0))
        else:
            calls = rng.randint(80, 500)
            sat = round(rng.uniform(3.8, 5.0), 1)
            usages.append(_make_usage(rng, f, "partner_alpha", calls, True, sat))

    # partner_beta — growth, 7/9, power user of dagger_training
    beta_access = TIER_ACCESS["growth"]
    beta_skip = {"advanced_sdg"}
    for f in beta_access:
        if f in beta_skip:
            usages.append(_make_usage(rng, f, "partner_beta", 0, False, 0.0))
        elif f == "dagger_training":
            usages.append(_make_usage(rng, f, "partner_beta", rng.randint(300, 800), True, 4.9))
        else:
            calls = rng.randint(40, 250)
            sat = round(rng.uniform(3.5, 4.8), 1)
            usages.append(_make_usage(rng, f, "partner_beta", calls, True, sat))

    # partner_gamma — pilot, 4/6, only uses inference + eval
    gamma_access = TIER_ACCESS["pilot"]
    gamma_active = {"inference", "closed_loop_eval", "fine_tune", "checkpoint_save"}
    for f in gamma_access:
        if f in gamma_active:
            calls = rng.randint(20, 180)
            sat = round(rng.uniform(3.2, 4.5), 1)
            usages.append(_make_usage(rng, f, "partner_gamma", calls, True, sat))
        else:
            usages.append(_make_usage(rng, f, "partner_gamma", 0, False, 0.0))

    # partner_delta — enterprise, 8/15, hasn't tried advanced SDG features
    delta_skip = {
        "advanced_sdg", "basic_sdg", "federated_learning",
        "embodiment_adapter", "custom_rewards", "white_label", "dedicated_support",
    }
    for f in TIER_ACCESS["enterprise"]:
        if f in delta_skip:
            usages.append(_make_usage(rng, f, "partner_delta", 0, False, 0.0))
        else:
            calls = rng.randint(30, 350)
            sat = round(rng.uniform(3.0, 4.6), 1)
            usages.append(_make_usage(rng, f, "partner_delta", calls, True, sat))

    # partner_epsilon — growth, 5/9, recently onboarded
    epsilon_access = TIER_ACCESS["growth"]
    epsilon_active = {"inference", "fine_tune", "usage_dashboard", "dagger_training", "closed_loop_eval"}
    for f in epsilon_access:
        if f in epsilon_active:
            calls = rng.randint(5, 60)
            sat = round(rng.uniform(3.0, 4.2), 1)
            usages.append(_make_usage(rng, f, "partner_epsilon", calls, True, sat))
        else:
            usages.append(_make_usage(rng, f, "partner_epsilon", 0, False, 0.0))

    return usages


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

PARTNER_TIER: dict[str, str] = {
    "partner_alpha": "enterprise",
    "partner_beta": "growth",
    "partner_gamma": "pilot",
    "partner_delta": "enterprise",
    "partner_epsilon": "growth",
}


def build_report(usages: list[FeatureUsage]) -> FeatureReport:
    partners = list(PARTNER_TIER.keys())
    profiles: list[PartnerAdoption] = []

    for partner in partners:
        tier = PARTNER_TIER[partner]
        accessible = TIER_ACCESS[tier]
        partner_usages = {u.feature_name: u for u in usages if u.partner_name == partner}
        adopted = [f for f in accessible if partner_usages.get(f, FeatureUsage(f, partner, 0, 0, False, 0.0)).active]
        unused = [f for f in accessible if f not in adopted]
        adoption_pct = round(len(adopted) / len(accessible) * 100, 1) if accessible else 0.0
        # power features: top 3 by calls_30d
        sorted_adopted = sorted(
            [partner_usages[f] for f in adopted if f in partner_usages],
            key=lambda u: u.calls_30d,
            reverse=True,
        )
        power_features = [u.feature_name for u in sorted_adopted[:3]]
        profiles.append(PartnerAdoption(
            partner_name=partner,
            tier=tier,
            features_adopted=len(adopted),
            features_available=len(accessible),
            adoption_pct=adoption_pct,
            power_features=power_features,
            unused_features=unused,
        ))

    # Feature popularity: % of eligible partners using each feature
    feature_popularity: dict[str, float] = {}
    for feature in ALL_FEATURES:
        eligible = [p for p, t in PARTNER_TIER.items() if feature in TIER_ACCESS[t]]
        if not eligible:
            feature_popularity[feature] = 0.0
            continue
        using = [
            u for u in usages
            if u.feature_name == feature and u.active and u.partner_name in eligible
        ]
        feature_popularity[feature] = round(len(using) / len(eligible) * 100, 1)

    most_popular = max(feature_popularity, key=lambda f: feature_popularity[f])
    least_adopted = min(feature_popularity, key=lambda f: feature_popularity[f])
    avg_adoption = round(sum(p.adoption_pct for p in profiles) / len(profiles), 1)

    # Upsell opportunities: partners with unused high-value features
    upsells: list[dict] = []
    high_value_features = FEATURES_BY_TIER["growth"] + FEATURES_BY_TIER["enterprise"]
    for profile in profiles:
        unused_hv = [f for f in profile.unused_features if f in high_value_features]
        if unused_hv:
            upsells.append({
                "partner": profile.partner_name,
                "tier": profile.tier,
                "unused_high_value": unused_hv,
            })

    return FeatureReport(
        most_popular_feature=most_popular,
        least_adopted_feature=least_adopted,
        avg_adoption_pct=avg_adoption,
        upsell_opportunities=upsells,
        features=usages,
        partner_profiles=profiles,
    )


# ---------------------------------------------------------------------------
# Stdout table
# ---------------------------------------------------------------------------

def print_adoption_table(report: FeatureReport) -> None:
    print("\n" + "=" * 88)
    print("  OCI ROBOT CLOUD — FEATURE ADOPTION REPORT")
    print("=" * 88)
    header = f"{'Partner':<18} {'Tier':<12} {'Adopted/Avail':<16} {'Adoption %':<12} {'Power Features'}"
    print(header)
    print("-" * 88)
    for p in report.partner_profiles:
        power = ", ".join(p.power_features) if p.power_features else "—"
        print(
            f"{p.partner_name:<18} {p.tier:<12} "
            f"{p.features_adopted}/{p.features_available:<14} "
            f"{p.adoption_pct:<12.1f} {power}"
        )
    print("-" * 88)
    print(f"\n  Avg adoption:        {report.avg_adoption_pct}%")
    print(f"  Most popular:        {report.most_popular_feature}")
    print(f"  Least adopted:       {report.least_adopted_feature}")
    print(f"  Upsell candidates:   {len(report.upsell_opportunities)} partners\n")

    print("  ROADMAP INSIGHTS (features used by <50% of eligible partners):")
    print("  " + "-" * 60)
    all_features_sorted = sorted(ALL_FEATURES, key=lambda f: (
        TIER_ORDER.index(FEATURE_TIER[f]), f
    ))
    for feature in all_features_sorted:
        eligible = [p for p, t in PARTNER_TIER.items() if feature in TIER_ACCESS[t]]
        using = [
            u for u in report.features
            if u.feature_name == feature and u.active and u.partner_name in eligible
        ]
        pct = len(using) / len(eligible) * 100 if eligible else 0.0
        if pct < 50:
            tier = FEATURE_TIER[feature]
            print(f"    [{tier:>10}] {feature:<25} {pct:.0f}% adoption → prioritize onboarding")
    print()


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _feature_popularity_map(report: FeatureReport) -> dict[str, float]:
    result: dict[str, float] = {}
    for feature in ALL_FEATURES:
        eligible = [p for p, t in PARTNER_TIER.items() if feature in TIER_ACCESS[t]]
        if not eligible:
            result[feature] = 0.0
            continue
        using = [
            u for u in report.features
            if u.feature_name == feature and u.active and u.partner_name in eligible
        ]
        result[feature] = round(len(using) / len(eligible) * 100, 1)
    return result


def _render_heatmap(report: FeatureReport) -> str:
    """SVG heatmap: rows = partners, cols = features."""
    partners = [p.partner_name for p in report.partner_profiles]
    features = ALL_FEATURES
    cell_w, cell_h = 52, 36
    label_w, label_h = 130, 90
    svg_w = label_w + len(features) * cell_w + 20
    svg_h = label_h + len(partners) * cell_h + 20

    usage_lookup: dict[tuple[str, str], bool] = {
        (u.partner_name, u.feature_name): u.active for u in report.features
    }

    lines = [
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg"',
        f'  style="background:#0f172a;border-radius:8px;font-family:monospace">',
    ]

    # Column headers (rotated)
    for ci, feat in enumerate(features):
        x = label_w + ci * cell_w + cell_w // 2
        tier_color = TIER_COLORS[FEATURE_TIER[feat]]
        lines.append(
            f'  <text x="{x}" y="{label_h - 5}" '
            f'fill="{tier_color}" font-size="10" '
            f'text-anchor="start" '
            f'transform="rotate(-45,{x},{label_h - 5})">'
            f'{feat}</text>'
        )

    # Row labels + cells
    for ri, profile in enumerate(report.partner_profiles):
        y = label_h + ri * cell_h
        tier_color = TIER_COLORS[profile.tier]
        lines.append(
            f'  <text x="{label_w - 6}" y="{y + cell_h // 2 + 4}" '
            f'fill="{tier_color}" font-size="11" text-anchor="end">'
            f'{profile.partner_name}</text>'
        )
        for ci, feat in enumerate(features):
            x = label_w + ci * cell_w
            accessible = feat in TIER_ACCESS[profile.tier]
            adopted = usage_lookup.get((profile.partner_name, feat), False)
            if not accessible:
                fill = "#1e293b"
                stroke = "#334155"
            elif adopted:
                fill = TIER_COLORS[FEATURE_TIER[feat]]
                stroke = "#0f172a"
            else:
                fill = "#1e3a4a"
                stroke = "#334155"
            lines.append(
                f'  <rect x="{x + 2}" y="{y + 2}" '
                f'width="{cell_w - 4}" height="{cell_h - 4}" '
                f'rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


def _render_bar_chart(report: FeatureReport) -> str:
    """SVG horizontal bar chart: feature popularity sorted desc."""
    pop = _feature_popularity_map(report)
    sorted_feats = sorted(ALL_FEATURES, key=lambda f: pop[f], reverse=True)

    bar_h = 22
    label_w = 170
    chart_w = 420
    padding = 10
    svg_h = len(sorted_feats) * (bar_h + 4) + padding * 2 + 20
    svg_w = label_w + chart_w + 60

    lines = [
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg"',
        f'  style="background:#0f172a;border-radius:8px;font-family:monospace">',
    ]

    for i, feat in enumerate(sorted_feats):
        y = padding + i * (bar_h + 4)
        pct = pop[feat]
        bar_len = int(pct / 100 * chart_w)
        color = TIER_COLORS[FEATURE_TIER[feat]]
        lines.append(
            f'  <text x="{label_w - 6}" y="{y + bar_h // 2 + 4}" '
            f'fill="#94a3b8" font-size="11" text-anchor="end">{feat}</text>'
        )
        lines.append(
            f'  <rect x="{label_w}" y="{y}" '
            f'width="{bar_len}" height="{bar_h}" '
            f'rx="3" fill="{color}" opacity="0.85"/>'
        )
        lines.append(
            f'  <text x="{label_w + bar_len + 6}" y="{y + bar_h // 2 + 4}" '
            f'fill="#e2e8f0" font-size="10">{pct:.0f}%</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _tier_badge(tier: str) -> str:
    color = TIER_COLORS[tier]
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:11px;font-weight:600">{tier.upper()}</span>'
    )


def build_html(report: FeatureReport) -> str:
    pop = _feature_popularity_map(report)
    enterprise_profiles = [p for p in report.partner_profiles if p.tier == "enterprise"]
    ent_avg = (
        round(sum(p.adoption_pct for p in enterprise_profiles) / len(enterprise_profiles), 1)
        if enterprise_profiles else 0.0
    )
    ent_gap = round(100.0 - ent_avg, 1)

    # ---- stat cards ----
    stat_cards_html = f"""
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{report.avg_adoption_pct}%</div>
        <div class="stat-label">Avg Adoption</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="font-size:18px">{report.most_popular_feature}</div>
        <div class="stat-label">Most Popular Feature</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(report.upsell_opportunities)}</div>
        <div class="stat-label">Upsell Opportunities</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:#C74634">{ent_gap}%</div>
        <div class="stat-label">Enterprise Adoption Gap</div>
      </div>
    </div>
    """

    # ---- heatmap ----
    heatmap_svg = _render_heatmap(report)

    # ---- bar chart ----
    bar_svg = _render_bar_chart(report)

    # ---- partner table ----
    table_rows = ""
    for p in report.partner_profiles:
        upsell_item = next((u for u in report.upsell_opportunities if u["partner"] == p.partner_name), None)
        upsell_html = ""
        if upsell_item:
            top_upsell = upsell_item["unused_high_value"][:2]
            upsell_html = (
                '<span style="color:#C74634">&#9650; '
                + ", ".join(top_upsell)
                + "</span>"
            )
        else:
            upsell_html = '<span style="color:#10B981">&#10003; Fully utilized</span>'

        power_html = ", ".join(
            f'<span style="color:{TIER_COLORS[FEATURE_TIER[f]]}">{f}</span>'
            for f in p.power_features
        ) or "—"

        table_rows += f"""
        <tr>
          <td style="font-weight:600;color:#e2e8f0">{p.partner_name}</td>
          <td>{_tier_badge(p.tier)}</td>
          <td style="text-align:center">{p.features_adopted}/{p.features_available}</td>
          <td style="text-align:center">
            <span style="color:{'#10B981' if p.adoption_pct >= 70 else '#f59e0b' if p.adoption_pct >= 50 else '#C74634'};font-weight:600">
              {p.adoption_pct}%
            </span>
          </td>
          <td>{power_html}</td>
          <td>{upsell_html}</td>
        </tr>"""

    # ---- roadmap insights ----
    insights_html = ""
    low_adoption = [
        (f, pop[f]) for f in ALL_FEATURES if pop[f] < 50
    ]
    low_adoption.sort(key=lambda x: x[1])
    for feat, pct in low_adoption:
        tier = FEATURE_TIER[feat]
        color = TIER_COLORS[tier]
        insights_html += f"""
        <div class="insight-row">
          <span class="insight-badge" style="background:{color}">{tier}</span>
          <span class="insight-feature">{feat}</span>
          <span class="insight-pct" style="color:#f59e0b">{pct:.0f}% adoption</span>
          <span class="insight-action">→ Prioritize onboarding</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OCI Robot Cloud — Feature Usage Analytics</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      padding: 32px;
      min-height: 100vh;
    }}
    h1 {{
      font-size: 26px;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 4px;
    }}
    .subtitle {{
      color: #64748b;
      font-size: 13px;
      margin-bottom: 28px;
    }}
    .oracle-red {{ color: #C74634; }}
    h2 {{
      font-size: 16px;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin: 32px 0 14px;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 6px;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 8px;
    }}
    .stat-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 20px 24px;
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 4px;
    }}
    .stat-label {{
      font-size: 12px;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: .06em;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 20px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th {{
      text-align: left;
      padding: 10px 12px;
      background: #0f172a;
      color: #64748b;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: .06em;
    }}
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid #1e293b;
      color: #94a3b8;
    }}
    tr:hover td {{ background: #0f172a; }}
    .legend {{
      display: flex;
      gap: 20px;
      margin-top: 10px;
      font-size: 12px;
      color: #64748b;
    }}
    .legend-dot {{
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 2px;
      margin-right: 5px;
      vertical-align: middle;
    }}
    .insight-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 4px;
      border-bottom: 1px solid #1e293b;
      font-size: 13px;
    }}
    .insight-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      color: #fff;
      min-width: 70px;
      text-align: center;
      text-transform: uppercase;
    }}
    .insight-feature {{
      color: #e2e8f0;
      min-width: 180px;
      font-weight: 500;
    }}
    .insight-pct {{
      min-width: 100px;
      font-weight: 600;
    }}
    .insight-action {{
      color: #64748b;
      font-style: italic;
    }}
    footer {{
      margin-top: 40px;
      color: #334155;
      font-size: 11px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud <span class="oracle-red">—</span> Feature Usage Analytics</h1>
  <p class="subtitle">API feature adoption across design partners · guides product roadmap &amp; upsell strategy</p>

  <h2>Summary</h2>
  {stat_cards_html}

  <h2>Adoption Heatmap</h2>
  <div class="card">
    {heatmap_svg}
    <div class="legend">
      {"".join(
        f'<span><span class="legend-dot" style="background:{TIER_COLORS[t]}"></span>{t.capitalize()} adopted</span>'
        for t in TIER_ORDER
      )}
      <span><span class="legend-dot" style="background:#1e3a4a;border:1px solid #334155"></span>Eligible, not adopted</span>
      <span><span class="legend-dot" style="background:#1e293b;border:1px solid #334155"></span>Not in tier</span>
    </div>
  </div>

  <h2>Feature Popularity</h2>
  <div class="card">
    {bar_svg}
    <p style="font-size:11px;color:#475569;margin-top:8px">% of eligible partners actively using each feature (30-day window)</p>
  </div>

  <h2>Partner Profiles</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Partner</th>
          <th>Tier</th>
          <th>Adopted / Available</th>
          <th>Adoption %</th>
          <th>Power Features</th>
          <th>Upsell Opportunity</th>
        </tr>
      </thead>
      <tbody>{table_rows}
      </tbody>
    </table>
  </div>

  <h2>Roadmap Insights</h2>
  <div class="card">
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">
      Features with &lt;50% adoption among eligible partners — focus onboarding &amp; enablement here.
    </p>
    {insights_html}
  </div>

  <footer>
    OCI Robot Cloud · Feature Usage Analytics · Generated by analytics pipeline
  </footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud — API feature adoption analytics"
    )
    parser.add_argument("--mock", action="store_true", default=False,
                        help="Generate mock data (always enabled for now)")
    parser.add_argument("--output", default="/tmp/feature_usage_analytics.html",
                        help="Output path for HTML report (default: /tmp/feature_usage_analytics.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for mock data (default: 42)")
    args = parser.parse_args()

    usages = generate_mock_data(seed=args.seed)
    report = build_report(usages)

    print_adoption_table(report)

    html = build_html(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"  HTML report saved → {args.output}\n")


if __name__ == "__main__":
    main()
