#!/usr/bin/env python3
"""Federated Learning Coordinator for OCI Robot Cloud.

Coordinates federated learning across multiple robot partners. Each partner
trains locally on private data; only gradients are shared centrally. FedAvg
aggregation with differential privacy (Gaussian noise) is supported.

Compares FedAvg against a centralized baseline (all data pooled) to quantify
the privacy-convergence trade-off.

Usage:
    python federated_learning_coordinator.py [--rounds 10] [--clients 5]
        [--output /tmp/federated_learning.html] [--seed 42]
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FederatedClient:
    """Represents one robot partner participating in federated training."""
    client_id: str
    partner: str
    n_local_episodes: int
    local_lr: float
    privacy_epsilon: float       # DP noise strength; lower = more noise
    trained_steps: int = 0
    local_loss: float = 0.0
    gradient_norm: float = 0.0

    # Simulated gradient vector (one float per "parameter shard")
    _gradients: List[float] = field(default_factory=list, repr=False)


@dataclass
class FederatedRound:
    """Summary of one global aggregation round."""
    round_num: int
    n_clients: int
    global_loss: float
    global_sr: float             # success rate 0–1
    aggregation_method: str
    convergence_delta: float     # |global_sr[t] - global_sr[t-1]|
    duration_s: float


# ---------------------------------------------------------------------------
# FedAvg aggregator
# ---------------------------------------------------------------------------

class FedAvgAggregator:
    """Weighted-average gradient aggregation with optional differential privacy."""

    GRAD_DIM = 64  # Dimensionality of the simulated gradient vector

    def aggregate(self, clients: List[FederatedClient]) -> Dict[str, float]:
        """FedAvg: weighted average of gradients by n_local_episodes.

        Returns a dict with keys 'gradients' (list), 'total_episodes', 'n_clients'.
        """
        total_episodes = sum(c.n_local_episodes for c in clients)
        agg = [0.0] * self.GRAD_DIM

        for client in clients:
            weight = client.n_local_episodes / total_episodes
            for i, g in enumerate(client._gradients):
                agg[i] += weight * g

        return {
            "gradients": agg,
            "total_episodes": total_episodes,
            "n_clients": len(clients),
        }

    def add_dp_noise(self, gradients: List[float], epsilon: float) -> List[float]:
        """Add Gaussian noise scaled by 1/epsilon for differential privacy.

        Larger epsilon → less noise → closer to non-private training.
        """
        if epsilon <= 0:
            raise ValueError("epsilon must be > 0")
        sigma = 1.0 / epsilon
        return [g + random.gauss(0.0, sigma) for g in gradients]


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

PARTNERS = [
    ("agility",         "Agility Robotics"),
    ("figure",          "Figure AI"),
    ("boston_dynamics", "Boston Dynamics"),
    ("apptronik",       "Apptronik"),
    ("1x_technologies", "1X Technologies"),
]


def _make_clients(n_clients: int, rng: random.Random) -> List[FederatedClient]:
    """Instantiate FederatedClient objects for the first n_clients partners."""
    clients = []
    for idx in range(n_clients):
        partner_id, partner_name = PARTNERS[idx % len(PARTNERS)]
        n_eps = rng.randint(50, 200)
        epsilon = rng.uniform(0.5, 2.0)   # DP budget per round
        clients.append(FederatedClient(
            client_id=f"client_{idx:02d}",
            partner=partner_name,
            n_local_episodes=n_eps,
            local_lr=rng.uniform(1e-4, 5e-4),
            privacy_epsilon=epsilon,
        ))
    return clients


def _simulate_local_training(
    client: FederatedClient,
    round_num: int,
    global_sr: float,
    rng: random.Random,
    aggregator: FedAvgAggregator,
) -> None:
    """Simulate one round of local training on the client, updating its fields."""
    # Local loss decreases as global SR improves; add per-client noise
    base_loss = max(0.05, 1.5 - global_sr * 1.4 + rng.gauss(0, 0.05))
    client.local_loss = round(base_loss, 4)
    client.trained_steps += rng.randint(200, 500)

    # Simulate gradient vector: generally shrinks in norm as training converges
    dim = aggregator.GRAD_DIM
    scale = base_loss * (1.0 + rng.gauss(0, 0.1))
    client._gradients = [rng.gauss(0, scale) for _ in range(dim)]
    client.gradient_norm = round(math.sqrt(sum(g * g for g in client._gradients)), 4)


def simulate_federated_training(
    n_rounds: int = 10,
    n_clients: int = 5,
    seed: int = 42,
) -> tuple:
    """Run n_rounds of federated training with n_clients partners.

    Returns:
        (rounds: list[FederatedRound], clients: list[FederatedClient],
         centralized_sr: list[float])
    """
    rng = random.Random(seed)
    aggregator = FedAvgAggregator()

    clients = _make_clients(n_clients, rng)
    rounds: List[FederatedRound] = []

    # Starting point
    global_sr = 0.05
    prev_sr = 0.0

    # Centralized baseline: converges ~15% faster (no DP overhead, full data)
    centralized_sr = 0.05

    centralized_srs: List[float] = [centralized_sr]

    for r in range(1, n_rounds + 1):
        t_start = time.perf_counter()

        # Each client trains locally
        for client in clients:
            _simulate_local_training(client, r, global_sr, rng, aggregator)

        # Aggregate gradients with FedAvg
        agg_result = aggregator.aggregate(clients)

        # Apply per-client DP noise then re-aggregate (simulate privacy overhead)
        noisy_grads_list = []
        for client in clients:
            eps = client.privacy_epsilon
            noisy = aggregator.add_dp_noise(client._gradients, eps)
            weight = client.n_local_episodes / agg_result["total_episodes"]
            noisy_grads_list.append((weight, noisy))

        final_grads = [0.0] * aggregator.GRAD_DIM
        for weight, ng in noisy_grads_list:
            for i, v in enumerate(ng):
                final_grads[i] += weight * v

        grad_signal = math.sqrt(sum(g * g for g in final_grads)) / aggregator.GRAD_DIM

        # Global SR improvement: 6–8% per round, slowed by DP noise
        avg_epsilon = sum(c.privacy_epsilon for c in clients) / len(clients)
        dp_factor = min(1.0, avg_epsilon / 1.5)  # 1.0 = no slowdown at ε=1.5
        improvement = rng.uniform(0.06, 0.08) * dp_factor
        global_sr = min(0.95, global_sr + improvement)
        global_loss = round(max(0.05, 1.5 - global_sr * 1.4), 4)

        # Centralized baseline: 15% faster convergence
        cent_improvement = improvement * 1.15
        centralized_sr = min(0.95, centralized_sr + cent_improvement)
        centralized_srs.append(round(centralized_sr, 4))

        duration = round(time.perf_counter() - t_start, 4)
        delta = round(abs(global_sr - prev_sr), 4)
        prev_sr = global_sr

        rounds.append(FederatedRound(
            round_num=r,
            n_clients=n_clients,
            global_loss=global_loss,
            global_sr=round(global_sr, 4),
            aggregation_method="FedAvg+DP",
            convergence_delta=delta,
            duration_s=duration,
        ))

    return rounds, clients, centralized_srs


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_html(
    rounds: List[FederatedRound],
    clients: List[FederatedClient],
    centralized_srs: List[float] = None,
) -> str:
    """Render a dark-theme HTML dashboard with charts and comparison table."""

    round_nums = [r.round_num for r in rounds]
    fed_srs = [round(r.global_sr * 100, 2) for r in rounds]
    cent_srs = [round(v * 100, 2) for v in (centralized_srs[1:] if centralized_srs else [])]
    fed_losses = [r.global_loss for r in rounds]
    durations = [r.duration_s for r in rounds]

    # Per-client contribution bars (by n_local_episodes)
    total_eps = sum(c.n_local_episodes for c in clients)
    client_labels = json.dumps([c.partner for c in clients])
    client_contribs = json.dumps([round(c.n_local_episodes / total_eps * 100, 1) for c in clients])
    client_epsilons = json.dumps([round(c.privacy_epsilon, 2) for c in clients])
    client_losses = json.dumps([round(c.local_loss, 4) for c in clients])
    client_gnorms = json.dumps([round(c.gradient_norm, 4) for c in clients])

    # Privacy budget gauge: average epsilon across clients
    avg_eps = sum(c.privacy_epsilon for c in clients) / len(clients)
    gauge_pct = round(min(avg_eps / 3.0, 1.0) * 100, 1)  # 3.0 = "no privacy concern"

    # Comparison table rows
    table_rows_html = ""
    for r in rounds:
        cent_val = centralized_srs[r.round_num] if centralized_srs else 0.0
        gap = round((cent_val - r.global_sr) * 100, 2)
        table_rows_html += f"""
            <tr>
              <td>{r.round_num}</td>
              <td>{r.global_sr * 100:.2f}%</td>
              <td>{cent_val * 100:.2f}%</td>
              <td>{gap:+.2f}%</td>
              <td>{r.global_loss:.4f}</td>
              <td>{r.convergence_delta:.4f}</td>
              <td>{r.duration_s:.4f}s</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>OCI Robot Cloud — Federated Learning Dashboard</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2d3147;
    --text: #e2e8f0; --muted: #8892b0; --accent: #7c3aed;
    --green: #10b981; --yellow: #f59e0b; --red: #ef4444;
    --blue: #3b82f6; --purple: #a855f7;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif;
          padding: 2rem; min-height: 100vh; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: var(--purple);
        border-bottom: 1px solid var(--border); padding-bottom: .8rem; margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1.05rem; font-weight: 600; color: var(--accent); margin-bottom: .8rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
           gap: 1.25rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 1.25rem; }}
  .chart-container {{ width: 100%; height: 240px; position: relative; }}
  canvas {{ width: 100% !important; height: 100% !important; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ background: #1e2235; color: var(--muted); font-weight: 600; padding: .5rem .75rem;
        text-align: left; border-bottom: 1px solid var(--border); }}
  td {{ padding: .45rem .75rem; border-bottom: 1px solid var(--border); color: var(--text); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(124,58,237,.06); }}
  .badge {{ display: inline-block; padding: .15rem .55rem; border-radius: 999px;
            font-size: .75rem; font-weight: 600; }}
  .badge-green {{ background: rgba(16,185,129,.15); color: var(--green); }}
  .badge-yellow {{ background: rgba(245,158,11,.15); color: var(--yellow); }}
  .gauge-wrap {{ display: flex; flex-direction: column; align-items: center; gap: .5rem; }}
  .gauge-track {{ width: 100%; height: 18px; background: #2d3147; border-radius: 9px; overflow: hidden; }}
  .gauge-fill {{ height: 100%; border-radius: 9px;
                 background: linear-gradient(90deg, var(--green), var(--yellow), var(--red)); }}
  .stat-row {{ display: flex; justify-content: space-between; font-size: .82rem;
               color: var(--muted); margin-top: .3rem; }}
  footer {{ color: var(--muted); font-size: .75rem; text-align: center; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Federated Learning Dashboard</h1>

<div class="grid">
  <!-- SR Convergence Chart -->
  <div class="card" style="grid-column: span 2;">
    <h2>Global Success Rate Convergence</h2>
    <div class="chart-container"><canvas id="srChart"></canvas></div>
  </div>

  <!-- Per-Client Contribution -->
  <div class="card">
    <h2>Partner Data Contribution (%)</h2>
    <div class="chart-container"><canvas id="contribChart"></canvas></div>
  </div>

  <!-- Privacy Budget Gauge -->
  <div class="card">
    <h2>Privacy Budget (avg ε = {avg_eps:.2f})</h2>
    <div class="gauge-wrap" style="margin-top:1rem;">
      <div style="font-size:.9rem;color:var(--muted);">ε = 0 (max privacy) → ε = 3 (min privacy)</div>
      <div class="gauge-track" style="width:100%;">
        <div class="gauge-fill" style="width:{gauge_pct}%;"></div>
      </div>
      <div class="stat-row" style="width:100%;">
        <span>Strict Privacy</span>
        <span><b style="color:var(--text);">{gauge_pct:.1f}%</b> of budget used</span>
        <span>Relaxed Privacy</span>
      </div>
    </div>
    <table style="margin-top:1.2rem;">
      <thead><tr><th>Partner</th><th>ε</th><th>Local Loss</th><th>∥g∥</th></tr></thead>
      <tbody id="epsilonRows"></tbody>
    </table>
  </div>
</div>

<!-- FedAvg vs Centralized Comparison Table -->
<div class="card" style="margin-bottom:1.5rem;">
  <h2>FedAvg vs Centralized — Round-by-Round Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Round</th><th>FedAvg SR</th><th>Centralized SR</th>
        <th>Gap</th><th>Global Loss</th><th>Δ SR</th><th>Duration</th>
      </tr>
    </thead>
    <tbody>{table_rows_html}</tbody>
  </table>
  <p style="font-size:.8rem;color:var(--muted);margin-top:.75rem;">
    Centralized converges ~15% faster but requires pooling all partner data, violating data privacy agreements.
  </p>
</div>

<footer>OCI Robot Cloud · Federated Learning Coordinator · {len(rounds)} rounds · {len(clients)} partners · stdlib-only simulation</footer>

<script>
// ── Minimal canvas chart helpers ──────────────────────────────────────────
function setupCanvas(id) {{
  const canvas = document.getElementById(id);
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return {{ ctx, w: rect.width, h: rect.height }};
}}

function drawLineChart(id, datasets, labels, yLabel) {{
  const {{ ctx, w, h }} = setupCanvas(id);
  const pad = {{ top: 20, right: 20, bottom: 36, left: 52 }};
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  // Find y range
  const allVals = datasets.flatMap(d => d.data);
  const yMin = Math.floor(Math.min(...allVals));
  const yMax = Math.ceil(Math.max(...allVals));
  const yRange = yMax - yMin || 1;

  function xPos(i) {{ return pad.left + (i / (labels.length - 1)) * cw; }}
  function yPos(v) {{ return pad.top + ch - ((v - yMin) / yRange) * ch; }}

  // Background
  ctx.fillStyle = '#1a1d27';
  ctx.fillRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = '#2d3147'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.top + (ch / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
    const val = (yMax - (yRange / 4) * i).toFixed(1);
    ctx.fillStyle = '#8892b0'; ctx.font = '11px system-ui';
    ctx.textAlign = 'right'; ctx.fillText(val, pad.left - 6, y + 4);
  }}
  // x-axis labels
  labels.forEach((lb, i) => {{
    ctx.fillStyle = '#8892b0'; ctx.font = '11px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(lb, xPos(i), h - 8);
  }});

  // y-axis label
  ctx.save(); ctx.translate(14, h / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = '#8892b0'; ctx.font = '11px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(yLabel, 0, 0); ctx.restore();

  // Draw each dataset
  datasets.forEach(ds => {{
    ctx.strokeStyle = ds.color; ctx.lineWidth = 2.5;
    if (ds.dashed) ctx.setLineDash([6, 4]); else ctx.setLineDash([]);
    ctx.beginPath();
    ds.data.forEach((v, i) => {{
      const x = xPos(i), y = yPos(v);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke(); ctx.setLineDash([]);

    // Dots
    ctx.fillStyle = ds.color;
    ds.data.forEach((v, i) => {{
      ctx.beginPath(); ctx.arc(xPos(i), yPos(v), 3.5, 0, Math.PI * 2); ctx.fill();
    }});
  }});

  // Legend
  let lx = pad.left;
  datasets.forEach(ds => {{
    ctx.fillStyle = ds.color; ctx.fillRect(lx, pad.top - 14, 18, 3);
    ctx.fillStyle = '#e2e8f0'; ctx.font = '11px system-ui'; ctx.textAlign = 'left';
    ctx.fillText(ds.label, lx + 22, pad.top - 10);
    lx += ctx.measureText(ds.label).width + 50;
  }});
}}

function drawBarChart(id, labels, values, colors) {{
  const {{ ctx, w, h }} = setupCanvas(id);
  const pad = {{ top: 20, right: 20, bottom: 54, left: 44 }};
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;
  const n = labels.length;
  const barW = (cw / n) * 0.6;
  const gap = cw / n;

  ctx.fillStyle = '#1a1d27'; ctx.fillRect(0, 0, w, h);

  const yMax = Math.max(...values) * 1.1;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.top + (ch / 4) * i;
    ctx.strokeStyle = '#2d3147'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
    const val = (yMax - (yMax / 4) * i).toFixed(1);
    ctx.fillStyle = '#8892b0'; ctx.font = '11px system-ui';
    ctx.textAlign = 'right'; ctx.fillText(val + '%', pad.left - 4, y + 4);
  }}

  values.forEach((v, i) => {{
    const x = pad.left + gap * i + (gap - barW) / 2;
    const barH = (v / yMax) * ch;
    const y = pad.top + ch - barH;
    ctx.fillStyle = colors[i % colors.length];
    ctx.beginPath();
    ctx.roundRect(x, y, barW, barH, 4);
    ctx.fill();
    ctx.fillStyle = '#e2e8f0'; ctx.font = '11px system-ui'; ctx.textAlign = 'center';
    ctx.fillText(v + '%', x + barW / 2, y - 5);
    // Rotated label
    ctx.save(); ctx.translate(x + barW / 2, pad.top + ch + 10);
    ctx.rotate(-Math.PI / 4);
    ctx.fillStyle = '#8892b0'; ctx.font = '11px system-ui'; ctx.textAlign = 'right';
    ctx.fillText(labels[i], 0, 0); ctx.restore();
  }});
}}

// ── Data ──────────────────────────────────────────────────────────────────
const roundLabels = {json.dumps([str(r) for r in round_nums])};
const fedSRs      = {json.dumps(fed_srs)};
const centSRs     = {json.dumps(cent_srs)};
const clientLabels   = {client_labels};
const clientContribs = {client_contribs};
const clientEps      = {client_epsilons};
const clientLosses   = {client_losses};
const clientGnorms   = {client_gnorms};

// ── Render charts ─────────────────────────────────────────────────────────
drawLineChart('srChart', [
  {{ label: 'FedAvg+DP',    data: fedSRs,  color: '#a855f7', dashed: false }},
  {{ label: 'Centralized',  data: centSRs, color: '#10b981', dashed: true  }},
], roundLabels, 'Success Rate (%)');

const barColors = ['#7c3aed','#3b82f6','#10b981','#f59e0b','#ef4444'];
drawBarChart('contribChart', clientLabels, clientContribs, barColors);

// ── Epsilon table ─────────────────────────────────────────────────────────
const tbody = document.getElementById('epsilonRows');
clientLabels.forEach((name, i) => {{
  const tr = document.createElement('tr');
  const badge = clientEps[i] < 1.0
    ? `<span class="badge badge-green">ε=${{clientEps[i]}}</span>`
    : `<span class="badge badge-yellow">ε=${{clientEps[i]}}</span>`;
  tr.innerHTML = `<td>${{name}}</td><td>${{badge}}</td><td>${{clientLosses[i]}}</td><td>${{clientGnorms[i]}}</td>`;
  tbody.appendChild(tr);
}});
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate federated learning across robot partners and render an HTML dashboard."
    )
    parser.add_argument("--rounds",  type=int,  default=10,
                        help="Number of federated rounds (default: 10)")
    parser.add_argument("--clients", type=int,  default=5,
                        help="Number of partner clients (default: 5, max: 5)")
    parser.add_argument("--output",  type=str,  default="/tmp/federated_learning.html",
                        help="Output HTML path (default: /tmp/federated_learning.html)")
    parser.add_argument("--seed",    type=int,  default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    n_clients = min(args.clients, len(PARTNERS))
    print(f"[federated] Starting simulation: {args.rounds} rounds, {n_clients} clients, seed={args.seed}")

    t0 = time.perf_counter()
    rounds, clients, centralized_srs = simulate_federated_training(
        n_rounds=args.rounds,
        n_clients=n_clients,
        seed=args.seed,
    )
    elapsed = time.perf_counter() - t0

    final_fed  = rounds[-1].global_sr * 100
    final_cent = centralized_srs[-1] * 100
    avg_eps    = sum(c.privacy_epsilon for c in clients) / len(clients)

    print(f"[federated] Simulation complete in {elapsed:.3f}s")
    print(f"  FedAvg final SR    : {final_fed:.2f}%")
    print(f"  Centralized SR     : {final_cent:.2f}%")
    print(f"  Privacy gap        : {final_cent - final_fed:.2f}% (centralized faster)")
    print(f"  Avg privacy budget : ε = {avg_eps:.3f}")

    html = render_html(rounds, clients, centralized_srs)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[federated] Dashboard written to {args.output}")


if __name__ == "__main__":
    main()
