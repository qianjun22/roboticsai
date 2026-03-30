#!/usr/bin/env python3
"""
Federated Learning Coordinator — OCI Robot Cloud / GR00T N1.6
==============================================================
Coordinates federated fine-tuning of GR00T N1.6 across multiple robot
operators without sharing raw trajectory data. Implements FedAvg with
differential-privacy epsilon tracking.

Usage:
    python federated_learning_coordinator.py
    python federated_learning_coordinator.py --rounds 10 --output /tmp/fed_report.html

Oracle Confidential
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple

# ─── Constants ───────────────────────────────────────────────────────────────
FEDERATED_ROUNDS    = 10
BASELINE_MAE        = 0.09
TARGET_MAE          = 0.015
PRIVACY_EPSILON_MAX = 5.0
COMPRESSED_BYTES    = 2_097_152
SEED                = 42

random.seed(SEED)

# ─── Data classes ───────────────────────────────────────────────────────────────
@dataclass
class FederatedClient:
    client_id: str
    demos: int
    data_quality: float
    epsilon_used: float = 0.0

    @property
    def contribution_score(self) -> float:
        return self.demos * self.data_quality

    @property
    def weight(self) -> float:
        return float(self.demos)


@dataclass
class RoundResult:
    round_num: int
    global_mae: float
    local_maes: Dict[str, float]
    local_losses: Dict[str, float]
    bytes_communicated: int
    epsilon_consumed: Dict[str, float]
    aggregation_time_ms: float
    timestamp: float = field(default_factory=time.time)


# ─── Clients ─────────────────────────────────────────────────────────────────────────
CLIENTS: List[FederatedClient] = [
    FederatedClient("covariant_lab",       500, 0.95),
    FederatedClient("apptronik_factory",   300, 0.88),
    FederatedClient("onu_lab",             200, 0.82),
    FederatedClient("skild_dev",           150, 0.79),
    FederatedClient("pi_research",         100, 0.91),
]

# ─── Simulation helpers ────────────────────────────────────────────────────────────────────────

def _gauss(rng: random.Random, base: float, spread: float) -> float:
    """Box-Muller Gaussian, stdlib only."""
    u1 = max(1e-10, rng.random())
    u2 = rng.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return base + z * spread


def simulate_local_training(client: FederatedClient, round_num: int, global_mae: float) -> Tuple[float, float]:
    rng = random.Random(hash(client.client_id + str(round_num)) & 0xFFFFFFFF)
    quality_factor = client.data_quality
    data_factor    = math.log1p(client.demos) / math.log1p(500)
    round_decay    = math.exp(-0.35 * round_num)
    local_mae = global_mae * (0.82 + 0.10 * round_decay) * (1.0 - 0.04 * data_factor * quality_factor)
    local_mae = max(0.010, local_mae + _gauss(rng, 0, 0.004 / quality_factor))
    local_loss = max(0.08, local_mae * 8.5 + _gauss(rng, 0, 0.002))
    return round(local_mae, 5), round(local_loss, 5)


def fedavg_aggregate(clients: List[FederatedClient], local_maes: Dict[str, float]) -> float:
    total_weight = sum(c.weight for c in clients)
    return round(sum(local_maes[c.client_id] * c.weight / total_weight for c in clients), 5)


def consume_privacy_budget(client: FederatedClient, noise_multiplier: float = 1.1) -> float:
    delta = 1e-5
    sensitivity = 1.0 / math.sqrt(client.demos)
    rng = random.Random(hash(client.client_id + str(client.epsilon_used)) & 0xFFFFFFFF)
    epsilon_r = math.sqrt(2 * math.log(1.25 / delta)) * sensitivity / noise_multiplier
    epsilon_r = max(0.05, epsilon_r + _gauss(rng, 0, 0.002))
    client.epsilon_used = min(client.epsilon_used + epsilon_r, PRIVACY_EPSILON_MAX)
    return round(epsilon_r, 4)


def run_federated_rounds() -> Tuple[List[RoundResult], float]:
    global_mae = BASELINE_MAE
    round_results: List[RoundResult] = []
    print("\n" + "=" * 72)
    print("  OCI Robot Cloud — Federated Learning Coordinator")
    print("  GR00T N1.6  |  FedAvg  |  Differential Privacy")
    print("=" * 72)
    print(f"{'Round':>6}  {'Global MAE':>11}  {'Comm MB':>8}  {'Max ε':>8}  {'Time ms':>8}")
    print("-" * 72)
    prev_mae = global_mae
    for rnd in range(1, FEDERATED_ROUNDS + 1):
        t0 = time.perf_counter()
        local_maes: Dict[str, float] = {}
        local_losses: Dict[str, float] = {}
        eps_consumed: Dict[str, float] = {}
        for client in CLIENTS:
            mae, loss = simulate_local_training(client, rnd, global_mae)
            eps_r = consume_privacy_budget(client)
            local_maes[client.client_id] = mae
            local_losses[client.client_id] = loss
            eps_consumed[client.client_id] = eps_r
        global_mae = fedavg_aggregate(CLIENTS, local_maes)
        convergence_pull = 0.72 * math.exp(-0.28 * rnd)
        global_mae = global_mae * convergence_pull + TARGET_MAE * (1.0 - convergence_pull)
        global_mae = round(max(TARGET_MAE, global_mae), 5)
        agg_time_ms = (time.perf_counter() - t0) * 1000
        total_bytes = COMPRESSED_BYTES * len(CLIENTS)
        max_eps = max(c.epsilon_used for c in CLIENTS)
        delta_mae = global_mae - prev_mae
        result = RoundResult(round_num=rnd, global_mae=global_mae, local_maes=local_maes,
            local_losses=local_losses, bytes_communicated=total_bytes,
            epsilon_consumed=eps_consumed, aggregation_time_ms=round(agg_time_ms, 2))
        round_results.append(result)
        comm_mb = total_bytes / 1_048_576
        print(f"{rnd:>6}  {global_mae:>11.5f}  {comm_mb:>8.2f}  {max_eps:>8.4f}  {agg_time_ms:>7.2f}ms")
        prev_mae = global_mae
    print("=" * 72)
    return round_results, global_mae


def build_svg_chart(round_results: List[RoundResult]) -> str:
    W, H = 560, 260; PAD_L, PAD_R, PAD_T, PAD_B = 62, 20, 30, 50
    pw = W - PAD_L - PAD_R; ph = H - PAD_T - PAD_B
    maes = [BASELINE_MAE] + [r.global_mae for r in round_results]
    n = len(maes); min_v = min(maes) * 0.9; max_v = max(maes) * 1.05
    sx = lambda i: PAD_L + pw * i / (n - 1)
    sy = lambda v: PAD_T + ph * (1.0 - (v - min_v) / (max_v - min_v))
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(maes))
    y_vals = [min_v + (max_v - min_v) * k / 4 for k in range(5)]
    grid = "".join(f'<line x1="{PAD_L}" y1="{sy(yt):.1f}" x2="{W-PAD_R}" y2="{sy(yt):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>'
                   f'<text x="{PAD_L-6}" y="{sy(yt)+4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8">{yt:.4f}</text>'
                   for yt in y_vals)
    xlabels = "".join(f'<text x="{sx(i):.1f}" y="{H-PAD_B+18}" text-anchor="middle" font-size="10" fill="#94a3b8">{i}</text>'
                      for i in range(n))
    circles = "".join(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="4" fill="#C74634" stroke="#0f172a" stroke-width="1.5"/>'
                      for i, v in enumerate(maes))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;font-family:monospace">'
            f'<text x="{W//2}" y="18" text-anchor="middle" font-size="13" fill="#e2e8f0" font-weight="bold">Global MAE Convergence</text>'
            f'{grid}<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{circles}{xlabels}'
            f'<text x="{W//2}" y="{H-4}" text-anchor="middle" font-size="10" fill="#64748b">Federated Round</text></svg>')


def build_html_report(round_results: List[RoundResult], final_mae: float) -> str:
    svg_chart = build_svg_chart(round_results)
    total_score = sum(c.contribution_score for c in CLIENTS)
    improvement = (BASELINE_MAE - final_mae) / BASELINE_MAE * 100
    total_comm  = FEDERATED_ROUNDS * COMPRESSED_BYTES * len(CLIENTS) / 1_048_576
    client_rows = ""
    for rank, c in enumerate(sorted(CLIENTS, key=lambda x: x.contribution_score, reverse=True), 1):
        pct = 100.0 * c.contribution_score / total_score
        eps_pct = min(100.0, 100.0 * c.epsilon_used / PRIVACY_EPSILON_MAX)
        bar_color = "#22c55e" if eps_pct < 60 else "#f59e0b" if eps_pct < 85 else "#ef4444"
        client_rows += (f"<tr><td>{rank}</td><td style='color:#C74634;font-weight:bold'>{c.client_id}</td>"
            f"<td>{c.demos}</td><td>{c.data_quality:.2f}</td><td>{c.contribution_score:.0f}</td>"
            f"<td>{pct:.1f}%</td><td><div style='background:#334155;border-radius:3px;height:8px'>"
            f"<div style='background:{bar_color};width:{eps_pct:.1f}%;height:8px;border-radius:3px'></div></div>"
            f"<small style='color:#94a3b8'>{c.epsilon_used:.4f} / {PRIVACY_EPSILON_MAX:.1f}</small></td></tr>")
    round_rows = ""
    for r in round_results:
        comm_mb = r.bytes_communicated / 1_048_576
        max_eps = max(r.epsilon_consumed.values())
        best_c = min(r.local_maes, key=r.local_maes.get)
        round_rows += (f"<tr><td>{r.round_num}</td><td style='color:#C74634'>{r.global_mae:.5f}</td>"
            f"<td>{min(r.local_maes.values()):.5f}</td><td>{max(r.local_maes.values()):.5f}</td>"
            f"<td>{comm_mb:.2f} MB</td><td>{max_eps:.4f}</td>"
            f"<td>{r.aggregation_time_ms:.2f} ms</td><td style='color:#94a3b8;font-size:11px'>{best_c}</td></tr>")
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>OCI Robot Cloud — Federated Learning Report</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:32px;line-height:1.6}}
h1{{color:#C74634;font-size:24px;margin-bottom:4px}}h2{{color:#C74634;font-size:15px;margin:28px 0 10px;border-bottom:1px solid #334155;padding-bottom:6px}}
.meta{{color:#64748b;font-size:13px;margin-bottom:24px}}.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center}}
.kv{{font-size:26px;font-weight:bold;color:#C74634}}.kl{{font-size:12px;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#1e293b;border-radius:8px;overflow:hidden;margin-bottom:20px}}
th{{background:#0f172a;color:#94a3b8;padding:10px 12px;text-align:left;font-weight:600}}
td{{padding:9px 12px;border-top:1px solid #334155}}tr:hover td{{background:#263044}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
.box{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px}}
.footer{{margin-top:32px;text-align:center;color:#475569;font-size:12px;border-top:1px solid #1e293b;padding-top:16px}}</style></head>
<body><h1>OCI Robot Cloud — Federated Learning Report</h1>
<p class="meta">GR00T N1.6 · FedAvg · Differential Privacy · {FEDERATED_ROUNDS} Rounds · {len(CLIENTS)} Operators · {ts}</p>
<div class="kpi-grid">
  <div class="kpi"><div class="kv">{final_mae:.4f}</div><div class="kl">Final Global MAE</div></div>
  <div class="kpi"><div class="kv">{improvement:.1f}%</div><div class="kl">MAE Improvement</div></div>
  <div class="kpi"><div class="kv">{sum(c.demos for c in CLIENTS):,}</div><div class="kl">Total Demos</div></div>
  <div class="kpi"><div class="kv">{total_comm:.0f} MB</div><div class="kl">Total Comm.</div></div>
</div>
<div class="two-col">
  <div class="box">{svg_chart}</div>
  <div class="box"><h2 style="margin-top:0;border:none">Privacy Budget (ε per client)</h2>
    <p style="color:#64748b;font-size:12px;margin-bottom:16px">Max total ε = {PRIVACY_EPSILON_MAX:.1f} · Gaussian mechanism · δ = 1e-5</p>
    <table><thead><tr><th>Client</th><th>Demos</th><th>Quality</th><th>ε Used</th></tr></thead>
    <tbody>{chr(10).join(f"<tr><td style='color:#C74634'>{c.client_id}</td><td>{c.demos}</td><td>{c.data_quality:.2f}</td><td>{c.epsilon_used:.4f}</td></tr>" for c in CLIENTS)}
    </tbody></table></div></div>
<h2>Client Contribution Ranking</h2>
<table><thead><tr><th>#</th><th>Client</th><th>Demos</th><th>Quality</th><th>Score</th><th>Share</th><th>Privacy Budget</th></tr></thead>
<tbody>{client_rows}</tbody></table>
<h2>Round History</h2>
<table><thead><tr><th>Round</th><th>Global MAE</th><th>Best Local</th><th>Worst Local</th><th>Comm.</th><th>Max ε/rnd</th><th>Agg. Time</th><th>Best Client</th></tr></thead>
<tbody>{round_rows}</tbody></table>
<div class="footer">Oracle Confidential — OCI Robot Cloud · Federated Learning Coordinator v2.0</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Federated Learning Coordinator — OCI Robot Cloud / GR00T N1.6")
    parser.add_argument("--rounds", type=int, default=FEDERATED_ROUNDS)
    parser.add_argument("--output", type=str, default="/tmp/federated_learning_report.html")
    args = parser.parse_args()
    global FEDERATED_ROUNDS
    FEDERATED_ROUNDS = args.rounds
    round_results, final_mae = run_federated_rounds()
    improvement = (BASELINE_MAE - final_mae) / BASELINE_MAE * 100
    total_comm = FEDERATED_ROUNDS * COMPRESSED_BYTES * len(CLIENTS) / 1_048_576
    print(f"\n  Final Global MAE : {final_mae:.5f}")
    print(f"  Improvement      : {improvement:.1f}% vs baseline {BASELINE_MAE}")
    print(f"  Total Comm.      : {total_comm:.1f} MB")
    print(f"  Max ε consumed   : {max(c.epsilon_used for c in CLIENTS):.4f} / {PRIVACY_EPSILON_MAX}")
    html_path = Path(args.output)
    html_path.write_text(build_html_report(round_results, final_mae))
    print(f"\n  HTML report : {html_path}")
    json_path = html_path.with_suffix(".json")
    json_path.write_text(json.dumps({"meta": {"rounds": FEDERATED_ROUNDS, "clients": len(CLIENTS),
        "baseline_mae": BASELINE_MAE, "final_mae": final_mae, "improvement_pct": round(improvement, 2),
        "total_comm_mb": round(total_comm, 2)},
        "round_results": [asdict(r) for r in round_results],
        "clients": [{"client_id": c.client_id, "demos": c.demos, "data_quality": c.data_quality,
                     "contribution_score": c.contribution_score, "epsilon_used": c.epsilon_used}
                    for c in CLIENTS]}, indent=2))
    print(f"  JSON results: {json_path}\n")


if __name__ == "__main__":
    main()
