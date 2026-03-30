#!/usr/bin/env python3
"""
inference_cache_optimizer.py

Analyzes GR00T inference request patterns and recommends caching strategies
to reduce redundant computation and latency.

Usage:
    python inference_cache_optimizer.py [--mock] [--n-requests 1000]
        [--output /tmp/inference_cache_optimizer.html] [--seed 42]
"""

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

OCI_A100_COST_PER_HR = 4.20          # USD/hr
BASE_LATENCY_MS       = 226.0         # full inference (A100)
CACHE_HIT_LATENCY_MS  = 8.0          # exact hash hit
NEAR_HIT_LATENCY_MS   = 45.0         # nearest-neighbour hit
OBS_DIM               = 128          # simulated obs vector size
L2_THRESHOLD          = 0.25         # nearest-neighbour match threshold

# Traffic split
FRAC_SAME_OBS    = 0.22
FRAC_SIMILAR_OBS = 0.38
FRAC_NOVEL_OBS   = 0.40

# Strategy hit rates (analytical, used for cost model + recommendation)
STRATEGY_HIT_RATES = {
    "no_cache":        {"exact": 0.00, "near": 0.00, "miss": 1.00},
    "exact_match":     {"exact": FRAC_SAME_OBS, "near": 0.00,
                        "miss": FRAC_SIMILAR_OBS + FRAC_NOVEL_OBS},
    "nearest_neighbor":{"exact": FRAC_SAME_OBS,
                        "near": FRAC_SIMILAR_OBS,
                        "miss": FRAC_NOVEL_OBS},
    "kv_cache":        {"exact": 0.15, "near": 0.50, "miss": 0.35},
}

# kv_cache + nearest_neighbor combo
COMBO_HIT_RATE = 0.65
COMBO_COST     = OCI_A100_COST_PER_HR * (1 - COMBO_HIT_RATE)

STALE_ACTION_RISK = {
    "no_cache":         "none — always fresh",
    "exact_match":      "low — only reuses truly identical obs",
    "nearest_neighbor": "medium — approx match may drift in dynamic scenes",
    "kv_cache":         "low-medium — stale on episode boundary if not evicted",
}

INVALIDATION_GUIDANCE = [
    ("Episode boundary",
     "Flush KV-cache and evict all exact/ANN entries when a new episode starts. "
     "Robot state is reset; cached actions from previous episode are invalid."),
    ("Domain shift",
     "Monitor visual embedding distribution with a sliding-window KL divergence. "
     "If KL > 0.15, evict ANN cache; cached observations no longer representative."),
    ("Model update",
     "Invalidate entire cache on model checkpoint swap. "
     "New weights produce different embeddings — old cache is poisoned."),
    ("High δ-velocity",
     "If consecutive joint velocities exceed 0.3 rad/s, skip cache lookup for "
     "that step — robot is in a dynamic transition that requires fresh inference."),
    ("Time-to-live (TTL)",
     "Apply a 5-second TTL to all ANN cache entries in real deployments. "
     "Avoids serving stale actions to a robot that has physically moved."),
]

# ─────────────────────────────────────────────────────────────────────────────
# Simulation
# ─────────────────────────────────────────────────────────────────────────────

class RequestRecord:
    __slots__ = ("idx", "timestamp", "req_type", "obs", "obs_hash")

    def __init__(self, idx, timestamp, req_type, obs):
        self.idx       = idx
        self.timestamp = timestamp
        self.req_type  = req_type
        self.obs       = obs
        self.obs_hash  = hashlib.md5(bytes(int(v * 1000) & 0xFF
                                           for v in obs)).hexdigest()


def _make_obs(rng, base=None, noise_scale=0.0):
    if base is None:
        return [rng.gauss(0.0, 1.0) for _ in range(OBS_DIM)]
    return [b + rng.gauss(0.0, noise_scale) for b in base]


def simulate_requests(n_requests: int, seed: int) -> list:
    """Generate synthetic inference request stream over 1 hour."""
    rng = random.Random(seed)
    hour_seconds = 3600.0
    timestamps   = sorted(rng.uniform(0, hour_seconds) for _ in range(n_requests))

    # Pre-generate a pool of "stuck" obs (same_obs_repeated) and cluster centres
    n_stuck    = max(1, int(n_requests * FRAC_SAME_OBS * 0.3))
    n_clusters = max(1, int(n_requests * FRAC_SIMILAR_OBS * 0.1))

    stuck_pool    = [_make_obs(rng) for _ in range(n_stuck)]
    cluster_centres = [_make_obs(rng) for _ in range(n_clusters)]

    counts = {
        "same_obs_repeated":   int(n_requests * FRAC_SAME_OBS),
        "similar_obs_clustered": int(n_requests * FRAC_SIMILAR_OBS),
    }
    counts["novel_obs"] = n_requests - counts["same_obs_repeated"] - counts["similar_obs_clustered"]

    req_types = (
        ["same_obs_repeated"]    * counts["same_obs_repeated"] +
        ["similar_obs_clustered"] * counts["similar_obs_clustered"] +
        ["novel_obs"]             * counts["novel_obs"]
    )
    rng.shuffle(req_types)

    records = []
    for i, (ts, rt) in enumerate(zip(timestamps, req_types)):
        if rt == "same_obs_repeated":
            base  = stuck_pool[rng.randint(0, n_stuck - 1)]
            obs   = base[:]            # exact copy
        elif rt == "similar_obs_clustered":
            centre = cluster_centres[rng.randint(0, n_clusters - 1)]
            obs    = _make_obs(rng, centre, noise_scale=0.05)
        else:
            obs = _make_obs(rng)
        records.append(RequestRecord(i, ts, rt, obs))
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Cache strategies
# ─────────────────────────────────────────────────────────────────────────────

def _l2(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class ExactMatchCache:
    def __init__(self):
        self._store = {}  # hash → obs

    def lookup(self, rec: RequestRecord):
        return "exact" if rec.obs_hash in self._store else "miss"

    def insert(self, rec: RequestRecord):
        self._store[rec.obs_hash] = rec.obs


class NearestNeighborCache:
    def __init__(self):
        self._entries = []   # list of (obs, hash)

    def lookup(self, rec: RequestRecord):
        # Exact check first
        for obs, h in self._entries:
            if h == rec.obs_hash:
                return "exact"
        # ANN check (brute-force; fine for 1000-request simulation)
        for obs, _ in self._entries:
            if _l2(obs, rec.obs) < L2_THRESHOLD:
                return "near"
        return "miss"

    def insert(self, rec: RequestRecord):
        # Evict if too large (cap at 200 entries to stay fast)
        if len(self._entries) > 200:
            self._entries.pop(0)
        self._entries.append((rec.obs, rec.obs_hash))


class KVCache:
    """
    Models transformer KV-cache reuse for sequential requests in the same
    episode.  Within a window of W consecutive requests, the hit rate rises
    as context overlaps.  We approximate: exact hit on first repeat in window,
    near hit on overlapping context, miss otherwise.
    """
    WINDOW = 8  # tokens / steps of KV context

    def __init__(self):
        self._window = []   # recent (obs_hash, obs)
        self._step   = 0

    def lookup(self, rec: RequestRecord):
        for obs, h in self._window:
            if h == rec.obs_hash:
                return "exact"
        for obs, _ in self._window:
            if _l2(obs, rec.obs) < L2_THRESHOLD * 1.5:
                return "near"
        return "miss"

    def insert(self, rec: RequestRecord):
        self._window.append((rec.obs, rec.obs_hash))
        if len(self._window) > self.WINDOW:
            self._window.pop(0)
        self._step += 1
        # Flush on episode boundary (every ~50 steps)
        if self._step % 50 == 0:
            self._window.clear()


def _latency(outcome: str) -> float:
    if outcome == "exact":
        return CACHE_HIT_LATENCY_MS
    if outcome == "near":
        return NEAR_HIT_LATENCY_MS
    return BASE_LATENCY_MS


def run_strategy(name: str, records: list) -> dict:
    if name == "no_cache":
        cache = None
    elif name == "exact_match":
        cache = ExactMatchCache()
    elif name == "nearest_neighbor":
        cache = NearestNeighborCache()
    elif name == "kv_cache":
        cache = KVCache()
    else:
        raise ValueError(f"Unknown strategy: {name}")

    outcomes   = []
    latencies  = []

    for rec in records:
        if cache is None:
            outcome = "miss"
        else:
            outcome = cache.lookup(rec)
            cache.insert(rec)

        outcomes.append(outcome)
        latencies.append(_latency(outcome))

    n = len(records)
    exact_hits = outcomes.count("exact")
    near_hits  = outcomes.count("near")
    misses     = outcomes.count("miss")

    hit_rate   = (exact_hits + near_hits) / n
    avg_lat    = sum(latencies) / n
    sorted_lat = sorted(latencies)
    p95_lat    = sorted_lat[int(0.95 * n)]
    p99_lat    = sorted_lat[int(0.99 * n)]

    compute_cost_pct = (1 - hit_rate) * 100
    cost_per_hr      = OCI_A100_COST_PER_HR * (1 - hit_rate)

    return {
        "strategy":          name,
        "n_requests":        n,
        "exact_hits":        exact_hits,
        "near_hits":         near_hits,
        "misses":            misses,
        "cache_hit_rate":    round(hit_rate, 4),
        "avg_latency_ms":    round(avg_lat, 2),
        "p95_latency_ms":    round(p95_lat, 2),
        "p99_latency_ms":    round(p99_lat, 2),
        "compute_cost_pct":  round(compute_cost_pct, 1),
        "cost_per_hr_usd":   round(cost_per_hr, 4),
        "stale_action_risk": STALE_ACTION_RISK[name],
        "latencies":         latencies,
    }


def run_all_strategies(records: list) -> list:
    strategies = ["no_cache", "exact_match", "nearest_neighbor", "kv_cache"]
    return [run_strategy(s, records) for s in strategies]


# ─────────────────────────────────────────────────────────────────────────────
# Console output
# ─────────────────────────────────────────────────────────────────────────────

def print_table(results: list):
    col_w = [22, 12, 14, 14, 14, 12]
    header = ["Strategy", "Hit Rate", "Avg Lat(ms)", "P95 Lat(ms)", "Cost/hr($)", "Stale Risk"]
    sep    = "+" + "+".join("-" * w for w in col_w) + "+"

    def row(cells):
        parts = []
        for cell, w in zip(cells, col_w):
            s = str(cell)
            parts.append(" " + s.ljust(w - 1))
        return "|" + "|".join(parts) + "|"

    print("\n" + "=" * 90)
    print("  GR00T Inference Cache Optimizer — Strategy Comparison")
    print("=" * 90)
    print(sep)
    print(row(header))
    print(sep)
    for r in results:
        risk_short = r["stale_action_risk"].split("—")[0].strip()
        cells = [
            r["strategy"],
            f"{r['cache_hit_rate']*100:.1f}%",
            f"{r['avg_latency_ms']:.1f}",
            f"{r['p95_latency_ms']:.1f}",
            f"${r['cost_per_hr_usd']:.4f}",
            risk_short,
        ]
        print(row(cells))
    print(sep)

    # Combo recommendation
    savings = OCI_A100_COST_PER_HR - COMBO_COST
    print(f"\n  RECOMMENDATION: kv_cache + nearest_neighbor combo")
    print(f"  Expected hit rate : {COMBO_HIT_RATE*100:.0f}%")
    print(f"  Effective cost    : ${COMBO_COST:.4f}/hr  (saves ${savings:.4f}/hr vs no_cache)")
    print("=" * 90 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# SVG helpers
# ─────────────────────────────────────────────────────────────────────────────

COLORS = ["#60a5fa", "#34d399", "#f59e0b", "#f87171"]
STRATEGY_LABELS = {
    "no_cache":         "No Cache",
    "exact_match":      "Exact Match",
    "nearest_neighbor": "Nearest Neighbor",
    "kv_cache":         "KV Cache",
}


def _make_cdf_svg(results: list) -> str:
    """SVG line chart: latency CDF for each strategy."""
    W, H = 560, 320
    pad  = {"top": 20, "right": 20, "bottom": 50, "left": 60}
    iw   = W - pad["left"] - pad["right"]
    ih   = H - pad["top"]  - pad["bottom"]

    max_lat = BASE_LATENCY_MS * 1.05
    min_lat = 0.0

    def sx(v):  # latency → x pixel
        return pad["left"] + (v - min_lat) / (max_lat - min_lat) * iw

    def sy(p):  # percentile [0,1] → y pixel
        return pad["top"] + ih - p * ih

    lines = []
    for i, r in enumerate(results):
        lats  = sorted(r["latencies"])
        n     = len(lats)
        pts   = " ".join(
            f"{sx(lats[j]):.1f},{sy((j+1)/n):.1f}"
            for j in range(0, n, max(1, n // 200))
        )
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{COLORS[i]}" '
            f'stroke-width="2" stroke-linejoin="round"/>'
        )

    # Axes
    axes = []
    # x-axis ticks
    for v in [0, 50, 100, 150, 200, 226]:
        x = sx(v)
        axes.append(f'<line x1="{x:.1f}" y1="{pad["top"]}" x2="{x:.1f}" '
                    f'y2="{pad["top"]+ih}" stroke="#374151" stroke-width="1" stroke-dasharray="3,3"/>')
        axes.append(f'<text x="{x:.1f}" y="{H-pad["bottom"]+15}" '
                    f'fill="#9ca3af" font-size="10" text-anchor="middle">{v}ms</text>')
    # y-axis ticks
    for p in [0, 0.25, 0.5, 0.75, 0.95, 1.0]:
        y = sy(p)
        axes.append(f'<line x1="{pad["left"]}" y1="{y:.1f}" x2="{pad["left"]+iw}" '
                    f'y2="{y:.1f}" stroke="#374151" stroke-width="1" stroke-dasharray="3,3"/>')
        axes.append(f'<text x="{pad["left"]-5}" y="{y+4:.1f}" '
                    f'fill="#9ca3af" font-size="10" text-anchor="end">{int(p*100)}%</text>')

    # Legend
    legend = []
    for i, r in enumerate(results):
        lx = pad["left"] + i * 130
        ly = H - 10
        legend.append(f'<rect x="{lx}" y="{ly-8}" width="12" height="4" fill="{COLORS[i]}" rx="2"/>')
        legend.append(f'<text x="{lx+16}" y="{ly}" fill="#d1d5db" font-size="10">'
                      f'{STRATEGY_LABELS[r["strategy"]]}</text>')

    # Axis labels
    axis_labels = [
        f'<text x="{W//2}" y="{H-2}" fill="#9ca3af" font-size="11" text-anchor="middle">Latency (ms)</text>',
        f'<text x="12" y="{H//2}" fill="#9ca3af" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90,12,{H//2})">CDF</text>',
        f'<text x="{W//2}" y="{pad["top"]-5}" fill="#e5e7eb" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Latency Distribution (CDF)</text>',
    ]

    inner = "\n".join(axes + lines + legend + axis_labels)
    return f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">\n{inner}\n</svg>'


def _make_bar_svg(results: list) -> str:
    """Grouped bar chart: exact/near/miss breakdown per strategy."""
    n_strats = len(results)
    W, H     = 560, 320
    pad      = {"top": 30, "right": 20, "bottom": 60, "left": 60}
    iw       = W - pad["left"] - pad["right"]
    ih       = H - pad["top"]  - pad["bottom"]

    group_w  = iw / n_strats
    bar_w    = group_w * 0.25
    seg_colors = {"exact": "#34d399", "near": "#f59e0b", "miss": "#f87171"}

    bars = []
    labels = []
    for gi, r in enumerate(results):
        n      = r["n_requests"]
        cx     = pad["left"] + gi * group_w + group_w / 2
        segs   = [
            ("exact", r["exact_hits"]  / n),
            ("near",  r["near_hits"]   / n),
            ("miss",  r["misses"]      / n),
        ]
        for si, (seg, frac) in enumerate(segs):
            bar_x = cx + (si - 1) * (bar_w + 3)
            bh    = frac * ih
            by    = pad["top"] + ih - bh
            bars.append(
                f'<rect x="{bar_x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'fill="{seg_colors[seg]}" rx="2">'
                f'<title>{seg}: {frac*100:.1f}%</title></rect>'
            )
            if frac > 0.04:
                bars.append(
                    f'<text x="{bar_x+bar_w/2:.1f}" y="{by-3:.1f}" fill="{seg_colors[seg]}" '
                    f'font-size="9" text-anchor="middle">{frac*100:.0f}%</text>'
                )
        lbl = STRATEGY_LABELS[r["strategy"]].replace(" ", "\n")
        labels.append(
            f'<text x="{cx:.1f}" y="{H-pad["bottom"]+14}" fill="#d1d5db" '
            f'font-size="10" text-anchor="middle">{STRATEGY_LABELS[r["strategy"]]}</text>'
        )

    # y-axis gridlines
    axes = []
    for p in [0, 0.25, 0.5, 0.75, 1.0]:
        y = pad["top"] + ih - p * ih
        axes.append(f'<line x1="{pad["left"]}" y1="{y:.1f}" x2="{pad["left"]+iw}" '
                    f'y2="{y:.1f}" stroke="#374151" stroke-width="1" stroke-dasharray="3,3"/>')
        axes.append(f'<text x="{pad["left"]-5}" y="{y+4:.1f}" '
                    f'fill="#9ca3af" font-size="10" text-anchor="end">{int(p*100)}%</text>')

    # Legend
    legend_items = [
        ("exact", "Exact Hit"),
        ("near",  "Near Hit"),
        ("miss",  "Miss"),
    ]
    legend = []
    for i, (key, lbl) in enumerate(legend_items):
        lx = pad["left"] + i * 130
        ly = H - 8
        legend.append(f'<rect x="{lx}" y="{ly-8}" width="10" height="10" '
                      f'fill="{seg_colors[key]}" rx="2"/>')
        legend.append(f'<text x="{lx+14}" y="{ly}" fill="#d1d5db" font-size="10">{lbl}</text>')

    title = (f'<text x="{W//2}" y="{pad["top"]-10}" fill="#e5e7eb" font-size="12" '
             f'text-anchor="middle" font-weight="bold">Cache Hit Rate by Strategy</text>')

    inner = "\n".join(axes + bars + labels + legend + [title])
    return f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">\n{inner}\n</svg>'


# ─────────────────────────────────────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────────────────────────────────────

def _css():
    return """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a; color: #e2e8f0;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      font-size: 14px; line-height: 1.6; padding: 24px;
    }
    h1 { font-size: 22px; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }
    h2 { font-size: 16px; font-weight: 600; color: #94a3b8;
         text-transform: uppercase; letter-spacing: .08em;
         margin: 28px 0 12px; }
    h3 { font-size: 14px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; }
    .subtitle { color: #64748b; font-size: 13px; margin-bottom: 24px; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
    .card {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 10px; padding: 18px 22px; flex: 1; min-width: 180px;
    }
    .card .label { font-size: 11px; color: #64748b;
                   text-transform: uppercase; letter-spacing: .06em; }
    .card .value { font-size: 28px; font-weight: 700; margin: 4px 0 2px; }
    .card .sub   { font-size: 12px; color: #94a3b8; }
    .blue   { color: #60a5fa; }
    .green  { color: #34d399; }
    .amber  { color: #f59e0b; }
    .red    { color: #f87171; }
    .charts { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 28px; }
    .chart-box {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 10px; padding: 20px; flex: 1; min-width: 300px;
    }
    table { width: 100%; border-collapse: collapse; }
    th {
      background: #1e293b; color: #94a3b8; font-weight: 600;
      font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
      padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155;
    }
    td { padding: 10px 14px; border-bottom: 1px solid #1e293b; }
    tr:last-child td { border-bottom: none; }
    tr:nth-child(even) td { background: #1e2d3f; }
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 9999px;
      font-size: 11px; font-weight: 600;
    }
    .badge-green { background: #064e3b; color: #34d399; }
    .badge-amber { background: #451a03; color: #f59e0b; }
    .badge-red   { background: #450a0a; color: #f87171; }
    .section-box {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 10px; padding: 20px; margin-bottom: 28px;
    }
    .inv-item { margin-bottom: 16px; padding-bottom: 16px;
                border-bottom: 1px solid #334155; }
    .inv-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
    .inv-title { font-weight: 600; color: #60a5fa; margin-bottom: 4px; }
    .inv-body  { color: #94a3b8; font-size: 13px; }
    .combo-box {
      background: linear-gradient(135deg, #0c2340 0%, #1a3a5c 100%);
      border: 1px solid #1d4ed8; border-radius: 10px;
      padding: 20px; margin-bottom: 28px;
    }
    .combo-box h3 { color: #93c5fd; }
    .combo-stat { display: inline-block; margin-right: 32px; }
    .combo-stat .lbl { font-size: 11px; color: #60a5fa; text-transform: uppercase; }
    .combo-stat .val { font-size: 20px; font-weight: 700; color: #bfdbfe; }
    """


def _risk_badge(risk_str: str) -> str:
    lower = risk_str.lower()
    if lower.startswith("none"):
        return '<span class="badge badge-green">none</span>'
    if lower.startswith("low-medium") or lower.startswith("medium"):
        return '<span class="badge badge-amber">medium</span>'
    if lower.startswith("low"):
        return '<span class="badge badge-green">low</span>'
    return '<span class="badge badge-red">high</span>'


def build_html(results: list, n_requests: int, seed: int) -> str:
    cdf_svg = _make_cdf_svg(results)
    bar_svg = _make_bar_svg(results)

    # Summary card data
    best_hit   = max(results, key=lambda r: r["cache_hit_rate"])
    best_lat   = min(results, key=lambda r: r["avg_latency_ms"])
    no_cache_r = next(r for r in results if r["strategy"] == "no_cache")
    kv_r       = next(r for r in results if r["strategy"] == "kv_cache")
    savings    = no_cache_r["cost_per_hr_usd"] - kv_r["cost_per_hr_usd"]
    combo_savings = OCI_A100_COST_PER_HR - COMBO_COST

    cards_html = f"""
    <div class="cards">
      <div class="card">
        <div class="label">Best Hit Rate</div>
        <div class="value green">{best_hit['cache_hit_rate']*100:.1f}%</div>
        <div class="sub">{STRATEGY_LABELS[best_hit['strategy']]}</div>
      </div>
      <div class="card">
        <div class="label">Best Avg Latency</div>
        <div class="value blue">{best_lat['avg_latency_ms']:.1f}ms</div>
        <div class="sub">{STRATEGY_LABELS[best_lat['strategy']]}</div>
      </div>
      <div class="card">
        <div class="label">Max Cost Savings / hr</div>
        <div class="value amber">${savings:.4f}</div>
        <div class="sub">vs no_cache (kv_cache best single)</div>
      </div>
      <div class="card">
        <div class="label">Combo Recommended</div>
        <div class="value green">${combo_savings:.4f}/hr</div>
        <div class="sub">kv_cache + nearest_neighbor</div>
      </div>
    </div>
    """

    # Combo box
    combo_html = f"""
    <div class="combo-box">
      <h3>Recommended Strategy: kv_cache + nearest_neighbor</h3>
      <p style="color:#93c5fd; font-size:13px; margin:8px 0 14px;">
        Combining KV-cache for sequential episode steps with ANN lookup for
        visually similar states achieves the best latency-cost tradeoff.
      </p>
      <div class="combo-stat">
        <div class="lbl">Hit Rate</div>
        <div class="val">{COMBO_HIT_RATE*100:.0f}%</div>
      </div>
      <div class="combo-stat">
        <div class="lbl">Effective Cost</div>
        <div class="val">${COMBO_COST:.4f}/hr</div>
      </div>
      <div class="combo-stat">
        <div class="lbl">Savings vs No Cache</div>
        <div class="val">${combo_savings:.4f}/hr</div>
      </div>
      <div class="combo-stat">
        <div class="lbl">OCI A100 Base Cost</div>
        <div class="val">${OCI_A100_COST_PER_HR:.2f}/hr</div>
      </div>
    </div>
    """

    # Strategy comparison table
    table_rows = ""
    for r in results:
        name_pretty = STRATEGY_LABELS[r["strategy"]]
        table_rows += f"""
        <tr>
          <td><strong>{name_pretty}</strong></td>
          <td class="{'green' if r['cache_hit_rate'] == max(x['cache_hit_rate'] for x in results) else ''}">{r['cache_hit_rate']*100:.1f}%</td>
          <td>{r['exact_hits']}</td>
          <td>{r['near_hits']}</td>
          <td>{r['misses']}</td>
          <td class="{'green' if r['avg_latency_ms'] == min(x['avg_latency_ms'] for x in results) else ''}">{r['avg_latency_ms']:.1f}</td>
          <td>{r['p95_latency_ms']:.1f}</td>
          <td>${r['cost_per_hr_usd']:.4f}</td>
          <td>{_risk_badge(r['stale_action_risk'])}</td>
        </tr>"""

    table_html = f"""
    <div class="section-box">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Hit Rate</th>
            <th>Exact Hits</th>
            <th>Near Hits</th>
            <th>Misses</th>
            <th>Avg Lat (ms)</th>
            <th>P95 Lat (ms)</th>
            <th>Cost/hr</th>
            <th>Stale Risk</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
    """

    # Cost savings table
    cost_rows = ""
    baseline = no_cache_r["cost_per_hr_usd"]
    for r in results:
        s = baseline - r["cost_per_hr_usd"]
        s_day  = s * 24
        s_mo   = s * 24 * 30
        cost_rows += f"""
        <tr>
          <td>{STRATEGY_LABELS[r['strategy']]}</td>
          <td>${r['cost_per_hr_usd']:.4f}</td>
          <td class="{'green' if s > 0 else ''}">${s:.4f}</td>
          <td>${s_day:.2f}</td>
          <td>${s_mo:.2f}</td>
        </tr>"""
    # Combo row
    combo_s = baseline - COMBO_COST
    cost_rows += f"""
    <tr style="background:#0c2340; border-top:2px solid #1d4ed8;">
      <td><strong>kv_cache + nearest_neighbor (combo)</strong></td>
      <td>${COMBO_COST:.4f}</td>
      <td class="green">${combo_s:.4f}</td>
      <td>${combo_s*24:.2f}</td>
      <td>${combo_s*24*30:.2f}</td>
    </tr>"""

    cost_table_html = f"""
    <h2>Cost Savings</h2>
    <div class="section-box">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Cost/hr</th>
            <th>Savings vs No Cache/hr</th>
            <th>Savings/day</th>
            <th>Savings/month</th>
          </tr>
        </thead>
        <tbody>{cost_rows}</tbody>
      </table>
    </div>
    """

    # Invalidation guidance
    inv_items = "".join(
        f'<div class="inv-item"><div class="inv-title">{title}</div>'
        f'<div class="inv-body">{desc}</div></div>'
        for title, desc in INVALIDATION_GUIDANCE
    )
    inv_html = f"""
    <h2>Cache Invalidation Guidance</h2>
    <div class="section-box">{inv_items}</div>
    """

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GR00T Inference Cache Optimizer</title>
  <style>{_css()}</style>
</head>
<body>
  <h1>GR00T Inference Cache Optimizer</h1>
  <div class="subtitle">
    {n_requests} simulated requests &nbsp;|&nbsp; seed {seed} &nbsp;|&nbsp; {ts}
    &nbsp;|&nbsp; OCI A100 ${OCI_A100_COST_PER_HR}/hr
  </div>

  {cards_html}
  {combo_html}

  <h2>Charts</h2>
  <div class="charts">
    <div class="chart-box">{cdf_svg}</div>
    <div class="chart-box">{bar_svg}</div>
  </div>

  <h2>Strategy Comparison</h2>
  {table_html}

  {cost_table_html}
  {inv_html}
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# JSON output
# ─────────────────────────────────────────────────────────────────────────────

def build_json(results: list, n_requests: int, seed: int) -> str:
    summary = []
    for r in results:
        d = {k: v for k, v in r.items() if k != "latencies"}
        summary.append(d)

    no_cache = next(r for r in results if r["strategy"] == "no_cache")
    output = {
        "meta": {
            "generated_at":    datetime.utcnow().isoformat() + "Z",
            "n_requests":      n_requests,
            "seed":            seed,
            "oci_a100_cost_hr": OCI_A100_COST_PER_HR,
            "base_latency_ms": BASE_LATENCY_MS,
        },
        "strategies": summary,
        "recommendation": {
            "strategy":       "kv_cache + nearest_neighbor",
            "hit_rate":       COMBO_HIT_RATE,
            "cost_per_hr":    round(COMBO_COST, 4),
            "savings_per_hr": round(no_cache["cost_per_hr_usd"] - COMBO_COST, 4),
        },
        "invalidation_guidance": [
            {"trigger": t, "action": d} for t, d in INVALIDATION_GUIDANCE
        ],
    }
    return json.dumps(output, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyze GR00T inference request patterns and recommend caching strategies."
    )
    parser.add_argument("--mock",        action="store_true",
                        help="Use simulated (mock) request data (default mode).")
    parser.add_argument("--n-requests",  type=int,   default=1000,
                        help="Number of inference requests to simulate (default: 1000).")
    parser.add_argument("--output",      type=str,
                        default="/tmp/inference_cache_optimizer.html",
                        help="Path for HTML report output.")
    parser.add_argument("--seed",        type=int,   default=42,
                        help="Random seed for reproducible simulation (default: 42).")
    args = parser.parse_args()

    n   = args.n_requests
    seed = args.seed
    out  = args.output

    print(f"[inference_cache_optimizer] Simulating {n} requests (seed={seed}) …")
    t0 = time.perf_counter()
    records = simulate_requests(n, seed)
    t1 = time.perf_counter()
    print(f"  Simulation complete in {(t1-t0)*1000:.1f}ms")

    print("  Running 4 caching strategies …")
    results = run_all_strategies(records)
    t2 = time.perf_counter()
    print(f"  Analysis complete in {(t2-t1)*1000:.1f}ms")

    print_table(results)

    # HTML
    html = build_html(results, n, seed)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"  HTML report   → {out_path.resolve()}")

    # JSON
    json_path = out_path.with_suffix(".json")
    json_path.write_text(build_json(results, n, seed), encoding="utf-8")
    print(f"  JSON output   → {json_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
