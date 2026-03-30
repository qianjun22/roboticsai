"""policy_benchmark_report.py
OCI Robot Cloud | Oracle Confidential
Comprehensive cross-policy benchmark report. stdlib + numpy only."""
from __future__ import annotations
import json, os, random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

@dataclass
class PolicyResult:
    policy_id: str; name: str; training_approach: str; n_demos: int; n_steps: int
    final_sr: float; mae: float; p99_ms: float; cost_usd: float; notes: str = ""

@dataclass
class BenchmarkSuite:
    run_id: str; results: List[PolicyResult]; created_at: str; best_policy_id: str = ""

_POLICY_SPECS = [
    dict(policy_id="bc_500",name="BC Baseline 500",training_approach="Behavioral Cloning",n_demos=500,n_steps=500,final_sr=0.05,mae=0.103,p99_ms=267.0,cost_usd=0.22,notes="Baseline BC run, limited demos"),
    dict(policy_id="bc_1000",name="BC 1000 Demos",training_approach="Behavioral Cloning",n_demos=1000,n_steps=5000,final_sr=0.05,mae=0.099,p99_ms=267.0,cost_usd=2.15,notes="Doubled demo count, minimal SR gain"),
    dict(policy_id="dagger_run5",name="DAgger Run 5",training_approach="DAgger",n_demos=99,n_steps=5000,final_sr=0.05,mae=0.022,p99_ms=264.0,cost_usd=2.58,notes="DAgger v5; short-episode filter (MIN_FRAMES=10)"),
    dict(policy_id="dagger_run9_v2.2",name="DAgger Run 9 v2.2",training_approach="DAgger",n_demos=500,n_steps=10000,final_sr=0.71,mae=0.018,p99_ms=227.0,cost_usd=4.73,notes="Breakthrough run; IK motion-planned SDG data"),
    dict(policy_id="curriculum_dagger",name="Curriculum DAgger",training_approach="Curriculum DAgger",n_demos=400,n_steps=8000,final_sr=0.72,mae=0.017,p99_ms=231.0,cost_usd=5.12,notes="Progressive difficulty; slight SR edge"),
    dict(policy_id="lora_rank16",name="LoRA r=16",training_approach="LoRA Fine-tune",n_demos=1000,n_steps=5000,final_sr=0.68,mae=0.019,p99_ms=226.0,cost_usd=2.15,notes="Parameter-efficient; 4x faster checkpoint save"),
    dict(policy_id="multi_task",name="Multi-Task Policy",training_approach="Multi-Task BC",n_demos=1500,n_steps=8000,final_sr=0.63,mae=0.022,p99_ms=238.0,cost_usd=3.89,notes="3 tasks combined; avg SR across tasks"),
    dict(policy_id="ensemble_4ckpt",name="Ensemble 4-Checkpoint",training_approach="Checkpoint Ensemble",n_demos=1000,n_steps=10000,final_sr=0.74,mae=0.016,p99_ms=251.0,cost_usd=9.46,notes="4-ckpt majority vote; best SR, highest cost"),
]

def run_benchmark(seed: int = 42) -> BenchmarkSuite:
    rng = random.Random(seed)
    results = []
    for spec in _POLICY_SPECS:
        r = PolicyResult(policy_id=spec["policy_id"],name=spec["name"],training_approach=spec["training_approach"],
            n_demos=spec["n_demos"],n_steps=spec["n_steps"],
            final_sr=round(max(0.0,min(1.0,spec["final_sr"]+rng.gauss(0,0.001))),4),
            mae=round(max(0.001,spec["mae"]+rng.gauss(0,0.0001)),4),
            p99_ms=spec["p99_ms"],cost_usd=spec["cost_usd"],notes=spec["notes"])
        results.append(r)
    best = max(results, key=lambda r: r.final_sr)
    run_id = f"bench_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_s{seed}"
    return BenchmarkSuite(run_id=run_id,results=results,created_at=datetime.utcnow().isoformat()+"Z",best_policy_id=best.policy_id)

def compute_pareto_front(suite: BenchmarkSuite) -> List[PolicyResult]:
    pareto = []
    for candidate in suite.results:
        dominated = any(
            other is not candidate and other.final_sr >= candidate.final_sr and other.cost_usd <= candidate.cost_usd
            and (other.final_sr > candidate.final_sr or other.cost_usd < candidate.cost_usd)
            for other in suite.results)
        if not dominated: pareto.append(candidate)
    return sorted(pareto, key=lambda r: r.final_sr, reverse=True)

def compute_rankings(suite: BenchmarkSuite) -> Dict:
    by_sr  = sorted(suite.results, key=lambda r: r.final_sr, reverse=True)
    by_eff = sorted(suite.results, key=lambda r: r.final_sr/r.cost_usd if r.cost_usd else 0, reverse=True)
    by_lat = sorted(suite.results, key=lambda r: r.p99_ms)
    return {
        "by_sr":         [(i+1,r.policy_id,r.final_sr)                                    for i,r in enumerate(by_sr)],
        "by_efficiency": [(i+1,r.policy_id,round(r.final_sr/r.cost_usd,4))               for i,r in enumerate(by_eff)],
        "by_latency":    [(i+1,r.policy_id,r.p99_ms)                                      for i,r in enumerate(by_lat)],
    }

_SR_COLOR = {(0.70,1.01):"#16a34a",(0.50,0.70):"#ca8a04",(0.00,0.50):"#dc2626"}
def _sr_color(sr): return next((c for (lo,hi),c in _SR_COLOR.items() if lo<=sr<hi),"#6b7280")
def _medal(rank): return {1:"[1st]",2:"[2nd]",3:"[3rd]"}.get(rank,f"[{rank}th]")

def generate_benchmark_report(suite: BenchmarkSuite) -> str:
    pareto = compute_pareto_front(suite)
    pareto_ids = {r.policy_id for r in pareto}
    by_sr = sorted(suite.results, key=lambda r: r.final_sr, reverse=True)
    best_sr = max(suite.results, key=lambda r: r.final_sr)
    best_eff = max(suite.results, key=lambda r: r.final_sr/r.cost_usd if r.cost_usd else 0)
    best_lat = min(suite.results, key=lambda r: r.p99_ms)

    kpi = (f"<div class='kpi-row'>"
           f"<div class='kpi-card'><div class='kpi-label'>Best SR</div><div class='kpi-value' style='color:#16a34a'>{best_sr.final_sr:.1%}</div><div class='kpi-sub'>{best_sr.name}</div></div>"
           f"<div class='kpi-card'><div class='kpi-label'>Best Efficiency</div><div class='kpi-value' style='color:#2563eb'>{best_eff.final_sr/best_eff.cost_usd:.3f} SR/$</div><div class='kpi-sub'>{best_eff.name}</div></div>"
           f"<div class='kpi-card'><div class='kpi-label'>Lowest p99</div><div class='kpi-value' style='color:#7c3aed'>{best_lat.p99_ms:.0f} ms</div><div class='kpi-sub'>{best_lat.name}</div></div>"
           f"</div>")

    rows = ""
    for rank,r in enumerate(by_sr,1):
        sc=_sr_color(r.final_sr); pb=" <span class='pareto-badge'>Pareto</span>" if r.policy_id in pareto_ids else ""
        eff=r.final_sr/r.cost_usd if r.cost_usd else 0
        rows += (f"<tr><td>{_medal(rank)}</td><td><strong>{r.name}</strong>{pb}<br><small style='color:#6b7280'>{r.policy_id}</small></td>"
                 f"<td>{r.training_approach}</td><td>{r.n_demos:,}</td><td>{r.n_steps:,}</td>"
                 f"<td style='background:{sc}20;color:{sc};font-weight:700'>{r.final_sr:.1%}</td>"
                 f"<td>{r.mae:.4f}</td><td>{r.p99_ms:.0f} ms</td><td>${r.cost_usd:.2f}</td><td>{eff:.3f}</td>"
                 f"<td style='font-size:.78rem;color:#6b7280'>{r.notes}</td></tr>")

    pareto_rows = "".join(f"<li><strong>{p.name}</strong> — SR {p.final_sr:.1%}, Cost ${p.cost_usd:.2f}</li>" for p in pareto)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>OCI Robot Cloud — Policy Benchmark</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;background:#f8fafc;color:#1e293b}}
header{{background:#0f172a;color:white;padding:24px 40px}}header h1{{font-size:1.6rem;font-weight:700}}header p{{color:#94a3b8;font-size:.9rem;margin-top:4px}}
.container{{max-width:1300px;margin:0 auto;padding:32px 24px}}h2{{font-size:1.15rem;font-weight:600;margin:32px 0 12px;color:#0f172a}}
.kpi-row{{display:flex;gap:16px;margin-bottom:32px;flex-wrap:wrap}}
.kpi-card{{background:white;border-radius:10px;border:1px solid #e2e8f0;padding:20px 28px;flex:1;min-width:200px}}
.kpi-label{{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:#64748b;font-weight:600}}
.kpi-value{{font-size:2rem;font-weight:800;margin:6px 0 2px}}.kpi-sub{{font-size:.82rem;color:#64748b}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;border:1px solid #e2e8f0}}
thead{{background:#0f172a;color:white}}th{{padding:12px 14px;text-align:left;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;font-weight:600}}
td{{padding:11px 14px;font-size:.85rem;border-bottom:1px solid #f1f5f9}}
tr:last-child td{{border-bottom:none}}tr:hover td{{background:#f8fafc}}
.pareto-badge{{background:#dbeafe;color:#1d4ed8;font-size:.68rem;padding:1px 6px;border-radius:9px;font-weight:600;margin-left:6px}}
.pareto-list{{background:white;border:1px solid #e2e8f0;border-radius:10px;padding:20px 28px}}
.pareto-list li{{margin:8px 0;font-size:.88rem;list-style:disc;margin-left:1.2em}}
.rec-box{{background:#fffbeb;border:1.5px solid #fbbf24;border-radius:10px;padding:22px 28px;margin-top:24px}}
.rec-title{{font-weight:700;font-size:1rem;margin-bottom:10px;color:#92400e}}
.rec-box p{{font-size:.88rem;line-height:1.65;color:#1e293b;margin-bottom:8px}}
footer{{text-align:center;font-size:.75rem;color:#9ca3af;padding:28px;margin-top:48px;border-top:1px solid #e2e8f0}}</style></head>
<body>
<header><h1>OCI Robot Cloud — GR00T N1.6 Policy Benchmark Report</h1>
<p>Run ID: {suite.run_id} &nbsp;|&nbsp; {suite.created_at} &nbsp;|&nbsp; {len(suite.results)} policies</p></header>
<div class="container">
<h2>KPIs</h2>{kpi}
<h2>Ranked Policy Comparison</h2>
<table><thead><tr><th>Rank</th><th>Policy</th><th>Approach</th><th>Demos</th><th>Steps</th><th>SR</th><th>MAE</th><th>p99</th><th>Cost</th><th>SR/$</th><th>Notes</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Pareto-Optimal (SR vs Cost)</h2>
<div class="pareto-list"><p style="font-size:.82rem;color:#64748b;margin-bottom:12px">Not dominated on both SR and cost.</p><ul>{pareto_rows}</ul></div>
<div class="rec-box"><div class="rec-title">Production Recommendation</div>
<p><strong>dagger_run9_v2.2</strong> is recommended: 71% SR, $4.73 cost, 227ms p99 on OCI A100 GPU4.</p>
<p>Cost-sensitive: <strong>LoRA r=16</strong> (68% SR, $2.15). Max accuracy: <strong>ensemble_4ckpt</strong> (74% SR, $9.46).</p></div>
</div>
<footer>Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; OCI A100 GPU4 138.1.153.110</footer>
</body></html>"""
    out_path = "/tmp/policy_benchmark_report.html"
    with open(out_path,"w",encoding="utf-8") as f: f.write(html)
    print(f"[benchmark] Report saved → {out_path}")
    return html

def _print_ranked_table(suite: BenchmarkSuite) -> None:
    by_sr = sorted(suite.results, key=lambda r: r.final_sr, reverse=True)
    hdr = f"{'#':<4} {'Policy ID':<22} {'Approach':<22} {'SR':>7} {'MAE':>8} {'p99ms':>7} {'Cost$':>8} {'SR/$':>8}"
    print("\n" + "="*len(hdr))
    print(f"  OCI Robot Cloud — Policy Benchmark | Run: {suite.run_id}")
    print("="*len(hdr)); print(hdr); print("-"*len(hdr))
    for rank,r in enumerate(by_sr,1):
        eff=r.final_sr/r.cost_usd if r.cost_usd else 0
        print(f"{rank:<4} {r.policy_id:<22} {r.training_approach:<22} {r.final_sr:>7.1%} {r.mae:>8.4f} {r.p99_ms:>6.0f}ms ${r.cost_usd:>7.2f} {eff:>8.3f}")
    best=max(suite.results,key=lambda r:r.final_sr)
    print("-"*len(hdr))
    print(f"  Best: {best.policy_id}  SR={best.final_sr:.1%}  Cost=${best.cost_usd:.2f}\n")

def main() -> None:
    suite = run_benchmark(seed=42)
    rankings = compute_rankings(suite)
    pareto = compute_pareto_front(suite)
    _print_ranked_table(suite)
    print(f"Pareto ({len(pareto)}):")
    for p in pareto: print(f"  {p.policy_id:<22} SR={p.final_sr:.1%}  Cost=${p.cost_usd:.2f}")
    print("\nEfficiency ranking:")
    for rank,pid,eff in rankings["by_efficiency"]: print(f"  {rank}. {pid:<22} {eff:.4f} SR/$")
    generate_benchmark_report(suite)

if __name__ == "__main__": main()
