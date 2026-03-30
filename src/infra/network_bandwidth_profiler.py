#!/usr/bin/env python3
"""
network_bandwidth_profiler.py — Profiles network bandwidth requirements for OCI Robot Cloud.

Measures data transfer costs for model weights, checkpoint sync, telemetry streaming,
and SDG dataset uploads across OCI regions and Jetson edge deployments.

Usage:
    python src/infra/network_bandwidth_profiler.py --mock --output /tmp/network_bandwidth_profiler.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# OCI egress pricing ($/GB)
OCI_EGRESS_FIRST_10TB = 0.0085
OCI_EGRESS_NEXT_40TB  = 0.0051

TRANSFER_SCENARIOS = [
    # (name, direction, size_gb, frequency_per_day, compression_ratio)
    ("model_weights_download",  "egress",  6.7,   0.5,  1.0),   # GR00T weights to Jetson
    ("checkpoint_sync",         "ingress", 0.15,  8.0,  3.0),   # checkpoints from training
    ("sdg_dataset_upload",      "ingress", 2.5,   2.0,  2.0),   # Genesis episodes → OCI
    ("eval_results_download",   "egress",  0.05,  4.0,  1.5),   # HTML/JSON reports
    ("telemetry_stream",        "egress",  0.008, 288,  1.0),   # 5-min batches, 24h
    ("lora_adapter_sync",       "egress",  0.045, 6.0,  4.0),   # LoRA weights to edge
    ("partner_dataset_upload",  "ingress", 8.0,   0.25, 2.5),   # partner demo data
    ("dagger_corrections_sync", "ingress", 0.12,  16.0, 3.0),   # DAgger corrections
]

REGIONS = [
    ("US East (Ashburn)",    "us-ashburn-1",   0.0),     # OCI-to-OCI free
    ("US West (Phoenix)",    "us-phoenix-1",   0.0085),
    ("Frankfurt",            "eu-frankfurt-1", 0.0085),
    ("Singapore",            "ap-singapore-1", 0.0085),
    ("Tokyo",                "ap-tokyo-1",     0.0085),
]


@dataclass
class TransferProfile:
    scenario: str
    direction: str
    size_gb: float
    daily_volume_gb: float
    monthly_volume_gb: float
    monthly_cost_usd: float
    compressed_size_gb: float
    bandwidth_mbps: float        # required sustained bandwidth
    latency_impact: str          # low/medium/high


@dataclass
class RegionProfile:
    region_name: str
    region_id: str
    monthly_egress_gb: float
    monthly_cost_usd: float
    round_trip_ms: float


@dataclass
class BandwidthReport:
    total_monthly_gb: float
    total_monthly_cost: float
    highest_volume_scenario: str
    highest_cost_scenario: str
    jetson_daily_gb: float
    transfers: list[TransferProfile] = field(default_factory=list)
    regions: list[RegionProfile] = field(default_factory=list)


def simulate_bandwidth(seed: int = 42) -> BandwidthReport:
    rng = random.Random(seed)
    transfers: list[TransferProfile] = []

    for name, direction, size_gb, freq_per_day, comp in TRANSFER_SCENARIOS:
        compressed = size_gb / comp
        daily = compressed * freq_per_day + rng.gauss(0, compressed * 0.05)
        daily = max(0.001, daily)
        monthly = daily * 30

        # Cost: only egress charges in OCI
        if direction == "egress":
            if monthly <= 10240:  # first 10TB
                cost = monthly * OCI_EGRESS_FIRST_10TB
            else:
                cost = 10240 * OCI_EGRESS_FIRST_10TB + (monthly - 10240) * OCI_EGRESS_NEXT_40TB
        else:
            cost = 0.0  # ingress free

        # Required bandwidth: daily volume / seconds in day (Mbps)
        bw = (daily * 1024 * 8) / (24 * 3600)  # Mbps

        # Latency impact
        latency = ("high" if size_gb > 1.0 and freq_per_day < 2
                   else "medium" if size_gb > 0.1
                   else "low")

        transfers.append(TransferProfile(
            scenario=name, direction=direction,
            size_gb=round(size_gb, 3),
            daily_volume_gb=round(daily, 3),
            monthly_volume_gb=round(monthly, 1),
            monthly_cost_usd=round(cost, 2),
            compressed_size_gb=round(compressed, 3),
            bandwidth_mbps=round(bw, 2),
            latency_impact=latency,
        ))

    # Region profiles
    total_egress_monthly = sum(t.monthly_volume_gb for t in transfers if t.direction == "egress")
    regions: list[RegionProfile] = []
    rtt_base = {"us-ashburn-1": 8, "us-phoenix-1": 62, "eu-frankfurt-1": 105,
                "ap-singapore-1": 185, "ap-tokyo-1": 180}

    for rname, rid, rate in REGIONS:
        egress = total_egress_monthly * (0.15 + rng.gauss(0, 0.03))
        cost = egress * rate
        rtt = rtt_base.get(rid, 100) + rng.gauss(0, 5)
        regions.append(RegionProfile(
            region_name=rname, region_id=rid,
            monthly_egress_gb=round(egress, 1),
            monthly_cost_usd=round(cost, 2),
            round_trip_ms=round(rtt, 0),
        ))

    total_monthly_gb = sum(t.monthly_volume_gb for t in transfers)
    total_cost = sum(t.monthly_cost_usd for t in transfers)
    highest_vol = max(transfers, key=lambda t: t.monthly_volume_gb).scenario
    highest_cost = max(transfers, key=lambda t: t.monthly_cost_usd).scenario

    # Jetson daily: model_weights (occasional) + LoRA sync + telemetry
    jetson_daily = sum(
        t.daily_volume_gb for t in transfers
        if t.scenario in ("model_weights_download", "lora_adapter_sync", "telemetry_stream", "eval_results_download")
    )

    return BandwidthReport(
        total_monthly_gb=round(total_monthly_gb, 1),
        total_monthly_cost=round(total_cost, 2),
        highest_volume_scenario=highest_vol,
        highest_cost_scenario=highest_cost,
        jetson_daily_gb=round(jetson_daily, 2),
        transfers=transfers,
        regions=regions,
    )


def render_html(report: BandwidthReport) -> str:
    DIR_COLORS = {"egress": "#ef4444", "ingress": "#22c55e"}
    LAT_COLORS = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}

    # SVG: monthly volume bar chart (sorted)
    sorted_t = sorted(report.transfers, key=lambda t: t.monthly_volume_gb, reverse=True)
    w, h, ml, mb = 540, 200, 145, 30
    inner_w = w - ml - 20
    bar_h = 16
    gap = 6
    max_vol = max(t.monthly_volume_gb for t in sorted_t)

    svg_vol = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_vol += f'<line x1="{ml}" y1="15" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_vol += f'<line x1="{ml}" y1="{h-mb}" x2="{w-20}" y2="{h-mb}" stroke="#475569"/>'

    for i, t in enumerate(sorted_t):
        y = 20 + i * (bar_h + gap)
        bar_w = (t.monthly_volume_gb / max_vol) * inner_w
        col = DIR_COLORS[t.direction]
        svg_vol += (f'<rect x="{ml}" y="{y}" width="{bar_w:.1f}" '
                    f'height="{bar_h}" fill="{col}" opacity="0.7" rx="2"/>')
        svg_vol += (f'<text x="{ml-4}" y="{y+bar_h-3}" fill="#94a3b8" '
                    f'font-size="8.5" text-anchor="end">{t.scenario[:22]}</text>')
        svg_vol += (f'<text x="{ml+bar_w+4:.1f}" y="{y+bar_h-3}" fill="{col}" '
                    f'font-size="8">{t.monthly_volume_gb:.1f}GB</text>')

    for v in [50, 100, 200, 400]:
        if v > max_vol * 1.05:
            break
        x = ml + (v / max_vol) * inner_w
        svg_vol += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                    f'font-size="7.5" text-anchor="middle">{v}GB</text>')
        svg_vol += (f'<line x1="{x:.1f}" y1="15" x2="{x:.1f}" y2="{h-mb}" '
                    f'stroke="#1e293b" stroke-width="1"/>')

    svg_vol += '</svg>'

    # SVG: region cost / RTT scatter
    rw, rh, rm = 360, 200, 50
    max_rtt = max(r.round_trip_ms for r in report.regions)
    max_cost_r = max(r.monthly_cost_usd for r in report.regions)

    svg_reg = f'<svg width="{rw}" height="{rh}" style="background:#0f172a;border-radius:8px">'
    svg_reg += f'<line x1="{rm}" y1="{rm}" x2="{rm}" y2="{rh-rm}" stroke="#475569"/>'
    svg_reg += f'<line x1="{rm}" y1="{rh-rm}" x2="{rw-rm}" y2="{rh-rm}" stroke="#475569"/>'

    for reg in report.regions:
        cx = rm + (reg.round_trip_ms / (max_rtt * 1.1)) * (rw - 2 * rm)
        cy = rh - rm - (reg.monthly_cost_usd / (max_cost_r * 1.1 + 0.01)) * (rh - 2 * rm)
        col = "#22c55e" if reg.round_trip_ms < 20 else "#f59e0b" if reg.round_trip_ms < 100 else "#ef4444"
        svg_reg += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col}" opacity="0.8"/>')
        label = reg.region_name.split(" ")[0]
        svg_reg += (f'<text x="{cx:.1f}" y="{cy-9:.1f}" fill="{col}" '
                    f'font-size="7.5" text-anchor="middle">{label}</text>')

    svg_reg += (f'<text x="{rw//2}" y="{rh-rm+14}" fill="#64748b" '
                f'font-size="8" text-anchor="middle">Round-trip latency (ms) →</text>')
    svg_reg += (f'<text x="{rm-10}" y="{rh//2}" fill="#64748b" font-size="8" '
                f'text-anchor="middle" transform="rotate(-90,{rm-10},{rh//2})">Monthly cost ($) ↑</text>')
    svg_reg += '</svg>'

    # Table
    rows = ""
    for t in sorted_t:
        dir_col = DIR_COLORS[t.direction]
        lat_col = LAT_COLORS[t.latency_impact]
        cost_col = "#ef4444" if t.monthly_cost_usd > 1.0 else "#f59e0b" if t.monthly_cost_usd > 0.1 else "#22c55e"
        rows += (f'<tr>'
                 f'<td style="color:#e2e8f0">{t.scenario}</td>'
                 f'<td style="color:{dir_col}">{t.direction}</td>'
                 f'<td style="color:#94a3b8">{t.compressed_size_gb:.3f}GB</td>'
                 f'<td style="color:#64748b">{t.monthly_volume_gb:.1f}GB</td>'
                 f'<td style="color:{cost_col}">${t.monthly_cost_usd:.2f}</td>'
                 f'<td style="color:#3b82f6">{t.bandwidth_mbps:.2f}</td>'
                 f'<td style="color:{lat_col}">{t.latency_impact}</td>'
                 f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Network Bandwidth Profiler</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Network Bandwidth Profiler</h1>
<div class="meta">
  {len(TRANSFER_SCENARIOS)} transfer scenarios · {len(REGIONS)} OCI regions · monthly projection
</div>

<div class="grid">
  <div class="card"><h3>Monthly Data Volume</h3>
    <div class="big" style="color:#3b82f6">{report.total_monthly_gb:.0f}GB</div>
    <div style="color:#64748b;font-size:10px">all transfers combined</div>
  </div>
  <div class="card"><h3>Monthly Egress Cost</h3>
    <div class="big" style="color:#22c55e">${report.total_monthly_cost:.2f}</div>
    <div style="color:#64748b;font-size:10px">OCI egress only</div>
  </div>
  <div class="card"><h3>Highest Volume</h3>
    <div style="color:#f59e0b;font-size:11px">{report.highest_volume_scenario.replace("_"," ")}</div>
    <div class="big" style="color:#f59e0b">
      {max(t.monthly_volume_gb for t in report.transfers):.0f}GB/mo
    </div>
  </div>
  <div class="card"><h3>Jetson Daily Data</h3>
    <div class="big" style="color:#94a3b8">{report.jetson_daily_gb:.2f}GB</div>
    <div style="color:#64748b;font-size:10px">edge device transfer</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Monthly Volume by Scenario</h3>
    {svg_vol}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      <span style="color:#ef4444">■</span> egress (billed) &nbsp;
      <span style="color:#22c55e">■</span> ingress (free)
    </div>
  </div>
  <div>
    <h3 class="sec">Region Cost vs Latency</h3>
    {svg_reg}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      US Ashburn = $0 egress (same-region). Lowest latency + cost.
    </div>
  </div>
</div>

<h3 class="sec">Transfer Detail</h3>
<table>
  <tr><th>Scenario</th><th>Dir</th><th>Compressed</th><th>Monthly Vol</th>
      <th>Monthly Cost</th><th>BW (Mbps)</th><th>Latency Impact</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">COST OPTIMIZATION</div>
  <div style="color:#22c55e">telemetry_stream: batch 5-min windows → 288 transfers/day; compress 8× with zstd → saves ~40% egress</div>
  <div style="color:#f59e0b">model_weights: cache on Jetson after first download; only sync LoRA delta (45MB vs 6.7GB) for updates</div>
  <div style="color:#3b82f6">Use OCI us-ashburn-1 as primary region — $0 intra-region egress for OCI-to-OCI training data</div>
  <div style="color:#64748b;margin-top:4px">Total: ${report.total_monthly_cost:.2f}/mo ≈ ${report.total_monthly_cost*12:.0f}/yr — negligible vs compute costs</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Network bandwidth profiler for OCI Robot Cloud")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/network_bandwidth_profiler.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[bandwidth] {len(TRANSFER_SCENARIOS)} scenarios · {len(REGIONS)} regions")
    t0 = time.time()

    report = simulate_bandwidth(args.seed)

    print(f"\n  {'Scenario':<28} {'Dir':>8} {'Compressed':>11} {'Monthly':>9} {'Cost':>8}")
    print(f"  {'─'*28} {'─'*8} {'─'*11} {'─'*9} {'─'*8}")
    for t in sorted(report.transfers, key=lambda x: x.monthly_volume_gb, reverse=True):
        print(f"  {t.scenario:<28} {t.direction:>8} {t.compressed_size_gb:>9.3f}GB "
              f"{t.monthly_volume_gb:>7.1f}GB ${t.monthly_cost_usd:>6.2f}")

    print(f"\n  Total monthly: {report.total_monthly_gb:.1f}GB / ${report.total_monthly_cost:.2f}")
    print(f"  Jetson daily: {report.jetson_daily_gb:.2f}GB")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_monthly_gb": report.total_monthly_gb,
        "total_monthly_cost": report.total_monthly_cost,
        "highest_volume": report.highest_volume_scenario,
        "jetson_daily_gb": report.jetson_daily_gb,
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
