#!/usr/bin/env python3
"""
fleet_manager.py — OCI Robot Cloud GPU Fleet Manager
Manages a fleet of OCI robot cloud GPU nodes with autoscaling, cost tracking, and HTML reporting.
Dependencies: stdlib + numpy only
"""
from __future__ import annotations
import math, random, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

REGIONS = ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1"]
NODE_COST_PER_HR: Dict[str, float] = {"A100_80GB": 4.10, "A100_40GB": 2.80, "V100": 1.60}
GPU_COUNT_DEFAULT: Dict[str, int] = {"A100_80GB": 8, "A100_40GB": 8, "V100": 8}
ON_DEMAND_PREMIUM = 1.35

@dataclass
class NodeConfig:
    node_id: str
    region: str
    gpu_type: str
    gpu_count: int
    status: str
    tags: Dict[str, str] = field(default_factory=dict)
    def hourly_cost(self) -> float:
        return NODE_COST_PER_HR.get(self.gpu_type, 0.0)

@dataclass
class FleetState:
    nodes: List[NodeConfig]
    total_gpus: int
    active_gpus: int
    utilization_pct: float
    created_at: datetime

@dataclass
class ScaleEvent:
    event_id: str
    timestamp: datetime
    action: str
    node_count: int
    reason: str
    cost_delta_usd: float


def initialize_fleet() -> FleetState:
    nodes: List[NodeConfig] = [
        NodeConfig("oci-ash-a100-80g-001", "us-ashburn-1", "A100_80GB", 8, "active", {"role": "inference", "env": "production"}),
        NodeConfig("oci-ash-a100-80g-002", "us-ashburn-1", "A100_80GB", 8, "active", {"role": "training", "env": "production"}),
        NodeConfig("oci-phx-a100-40g-001", "us-phoenix-1", "A100_40GB", 8, "active", {"role": "eval", "env": "production"}),
        NodeConfig("oci-fra-a100-40g-001", "eu-frankfurt-1", "A100_40GB", 8, "active", {"role": "staging", "env": "staging"}),
    ]
    total_gpus = sum(n.gpu_count for n in nodes)
    active_gpus = sum(n.gpu_count for n in nodes if n.status == "active")
    utilization_pct = (active_gpus / total_gpus * 100) if total_gpus > 0 else 0.0
    return FleetState(nodes=nodes, total_gpus=total_gpus, active_gpus=active_gpus, utilization_pct=utilization_pct, created_at=datetime.now(timezone.utc))


def simulate_autoscale(fleet: FleetState, demand_curve: List[float], seed: int = 42) -> List[ScaleEvent]:
    rng = random.Random(seed)
    events: List[ScaleEvent] = []
    above_streak = 0; below_streak = 0; phoenix_nodes = 1
    hour_start = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
    for hour, demand in enumerate(demand_curve):
        ts = hour_start.replace(hour=hour)
        if demand > 0.80: above_streak += 1; below_streak = 0
        elif demand < 0.30: below_streak += 1; above_streak = 0
        else: above_streak = 0; below_streak = 0
        if above_streak >= 2 and above_streak % 2 == 0:
            n = rng.randint(1, 2); phoenix_nodes += n
            events.append(ScaleEvent(str(uuid.uuid4())[:8], ts, "scale_up", n, f"Demand {demand:.2f} > 0.80 for {above_streak}h", n * NODE_COST_PER_HR["A100_40GB"]))
        elif below_streak >= 3 and below_streak % 3 == 0:
            n = min(rng.randint(1, 2), phoenix_nodes - 1)
            if n > 0:
                phoenix_nodes -= n
                events.append(ScaleEvent(str(uuid.uuid4())[:8], ts, "scale_down", n, f"Demand {demand:.2f} < 0.30 for {below_streak}h", -n * NODE_COST_PER_HR["A100_40GB"]))
    return events


def compute_fleet_cost(fleet: FleetState, scale_events: List[ScaleEvent], hours: int = 24) -> Dict:
    cost_by_region: Dict[str, float] = {}; cost_by_gpu: Dict[str, float] = {}
    for node in fleet.nodes:
        c = node.hourly_cost() * hours
        cost_by_region[node.region] = cost_by_region.get(node.region, 0.0) + c
        cost_by_gpu[node.gpu_type] = cost_by_gpu.get(node.gpu_type, 0.0) + c
    scale_cost = sum(ev.cost_delta_usd for ev in scale_events)
    total = sum(cost_by_region.values()) + scale_cost
    on_demand = total * ON_DEMAND_PREMIUM
    savings = on_demand - total
    return {"total_cost_usd": round(total, 4), "cost_by_region": {k: round(v, 4) for k, v in cost_by_region.items()}, "cost_by_gpu_type": {k: round(v, 4) for k, v in cost_by_gpu.items()}, "scale_event_cost_usd": round(scale_cost, 4), "total_on_demand_equivalent_usd": round(on_demand, 4), "savings_vs_ondemand_usd": round(savings, 4), "savings_pct": round((savings / on_demand * 100) if on_demand else 0, 2)}


def generate_fleet_report(fleet: FleetState, scale_events: List[ScaleEvent], cost_summary: Dict) -> str:
    topology_rows = "".join(f"<tr><td>{n.node_id}</td><td>{n.region}</td><td>{n.gpu_type}</td><td>{n.gpu_count}</td><td style='color:#22c55e;font-weight:600'>ACTIVE</td><td>{n.tags.get('role','')}</td><td>{n.tags.get('env','')}</td><td>${n.hourly_cost():.2f}/hr</td></tr>" for n in fleet.nodes)
    event_rows = "".join(f"<tr><td>{ev.event_id}</td><td>{ev.timestamp.strftime('%H:%M UTC')}</td><td style='color:{'#22c55e' if ev.action=='scale_up' else '#f87171'};font-weight:600'>{ev.action.upper()}</td><td>{ev.node_count}</td><td>{ev.reason}</td><td>{'+' if ev.cost_delta_usd>=0 else ''}${ev.cost_delta_usd:.2f}/hr</td></tr>" for ev in scale_events) or "<tr><td colspan='6' style='text-align:center;color:#94a3b8'>No scale events</td></tr>"
    region_rows = "".join(f"<tr><td>{r}</td><td>${v:.2f}</td></tr>" for r, v in cost_summary["cost_by_region"].items())
    gpu_rows = "".join(f"<tr><td>{g}</td><td>${v:.2f}</td></tr>" for g, v in cost_summary["cost_by_gpu_type"].items())
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Fleet Manager</title><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}}header{{background:#1e293b;border-left:4px solid #C74634;padding:1.5rem 2rem;margin-bottom:2rem;border-radius:0 8px 8px 0}}h1{{font-size:1.6rem;color:#f1f5f9}}h2{{font-size:1.1rem;color:#C74634;margin:1.5rem 0 0.8rem;padding-bottom:0.4rem;border-bottom:1px solid #334155}}.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}}.kpi{{background:#1e293b;border-radius:8px;padding:1.2rem;border-top:3px solid #C74634}}.kpi .label{{font-size:0.72rem;color:#64748b;text-transform:uppercase}}.kpi .value{{font-size:1.5rem;font-weight:700;color:#f1f5f9;margin-top:0.3rem}}.kpi .sub{{font-size:0.75rem;color:#94a3b8}}table{{width:100%;border-collapse:collapse;font-size:0.85rem}}th{{background:#1e293b;color:#94a3b8;text-align:left;padding:0.6rem 0.8rem;font-size:0.75rem;text-transform:uppercase}}td{{padding:0.5rem 0.8rem;border-bottom:1px solid #1e293b;color:#cbd5e1}}footer{{text-align:center;color:#475569;font-size:0.75rem;margin-top:3rem;padding-top:1rem;border-top:1px solid #1e293b}}</style></head><body><header><h1>OCI Robot Cloud — Fleet Manager Report <span style='background:#C74634;color:#fff;font-size:0.7rem;padding:2px 8px;border-radius:4px;margin-left:0.5rem'>PRODUCTION</span></h1><p style='color:#94a3b8;font-size:0.9rem;margin-top:0.3rem'>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Regions: {len(set(n.region for n in fleet.nodes))} | Nodes: {len(fleet.nodes)}</p></header><div class="kpi-grid"><div class="kpi"><div class="label">Total Nodes</div><div class="value">{len(fleet.nodes)}</div><div class="sub">{len(set(n.region for n in fleet.nodes))} regions</div></div><div class="kpi"><div class="label">Total GPUs</div><div class="value">{fleet.total_gpus}</div><div class="sub">{fleet.active_gpus} active</div></div><div class="kpi"><div class="label">Utilization</div><div class="value">{fleet.utilization_pct:.0f}%</div></div><div class="kpi"><div class="label">24h Cost</div><div class="value">${cost_summary['total_cost_usd']:,.2f}</div><div class="sub">reserved pricing</div></div><div class="kpi"><div class="label">Savings vs OD</div><div class="value">${cost_summary['savings_vs_ondemand_usd']:,.2f}</div><div class="sub">{cost_summary['savings_pct']}% cheaper</div></div><div class="kpi"><div class="label">Scale Events</div><div class="value">{len(scale_events)}</div><div class="sub">{sum(1 for e in scale_events if e.action=='scale_up')}up / {sum(1 for e in scale_events if e.action=='scale_down')}down</div></div></div><h2>Fleet Topology</h2><table><thead><tr><th>Node ID</th><th>Region</th><th>GPU Type</th><th>GPUs</th><th>Status</th><th>Role</th><th>Env</th><th>Cost</th></tr></thead><tbody>{topology_rows}</tbody></table><h2>Autoscale Events (24h)</h2><table><thead><tr><th>Event ID</th><th>Time</th><th>Action</th><th>Nodes</th><th>Reason</th><th>Cost Delta</th></tr></thead><tbody>{event_rows}</tbody></table><h2>Cost Breakdown</h2><div style='display:grid;grid-template-columns:1fr 1fr;gap:2rem'><div><p style='color:#64748b;font-size:0.8rem;margin-bottom:0.6rem'>BY REGION</p><table><thead><tr><th>Region</th><th>24h Cost</th></tr></thead><tbody>{region_rows}</tbody></table></div><div><p style='color:#64748b;font-size:0.8rem;margin-bottom:0.6rem'>BY GPU TYPE</p><table><thead><tr><th>GPU Type</th><th>24h Cost</th></tr></thead><tbody>{gpu_rows}</tbody></table></div></div><footer>OCI Robot Cloud — Fleet Manager | Oracle Confidential | Autoscaling: Phoenix A100_40GB | Scale-up: demand>0.80 for 2h | Scale-down: demand<0.30 for 3h</footer></body></html>"""
    with open("/tmp/fleet_manager.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    return "/tmp/fleet_manager.html"


def _realistic_demand_curve(seed: int = 42) -> List[float]:
    rng = np.random.default_rng(seed)
    hours = np.arange(24)
    base = np.clip(0.12 + 0.92 * np.exp(-0.5 * ((hours - 10) / 2.0)**2) + 0.85 * np.exp(-0.5 * ((hours - 15) / 2.0)**2), 0.0, 1.0)
    return np.clip(base + rng.normal(0, 0.03, size=24), 0.0, 1.0).tolist()


def main() -> None:
    print("=" * 68); print("  OCI Robot Cloud — Fleet Manager"); print("=" * 68)
    fleet = initialize_fleet()
    print(f"\n[FLEET INIT] {len(fleet.nodes)} nodes | {fleet.total_gpus} GPUs | {fleet.utilization_pct:.0f}% utilization")
    print(f"\n  {'Node ID':<30} {'Region':<20} {'GPU':<14} {'Role':<12} {'$/hr'}")
    for node in fleet.nodes:
        print(f"  {node.node_id:<30} {node.region:<20} {node.gpu_type:<14} {node.tags.get('role',''):<12} ${node.hourly_cost():.2f}")
    demand_curve = _realistic_demand_curve()
    scale_events = simulate_autoscale(fleet, demand_curve)
    print(f"\n[AUTOSCALE] {len(scale_events)} scale events:")
    for ev in scale_events:
        print(f"  [{ev.timestamp.strftime('%H:%M')}] {'\u2191' if ev.action=='scale_up' else '\u2193'} {ev.action.upper():<12} nodes={ev.node_count}  delta={'+' if ev.cost_delta_usd>=0 else ''}${ev.cost_delta_usd:.2f}/hr")
    cost = compute_fleet_cost(fleet, scale_events)
    print(f"\n[COST] 24h total: ${cost['total_cost_usd']:,.2f} reserved | ${cost['total_on_demand_equivalent_usd']:,.2f} on-demand | savings: ${cost['savings_vs_ondemand_usd']:,.2f} ({cost['savings_pct']}%)")
    output_path = generate_fleet_report(fleet, scale_events, cost)
    print(f"\n[REPORT] {output_path}")


if __name__ == "__main__":
    main()
