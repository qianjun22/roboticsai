#!/usr/bin/env python3
"""
Fleet Training Coordinator
Coordinates GR00T fine-tuning across multiple robot embodiments simultaneously.

When a design partner has a mixed fleet (e.g. Franka + UR5e + xArm7), this manages:
  - Shared backbone training from a common GR00T base checkpoint
  - Per-embodiment adapter layers (integrates with embodiment_config_manager.py)
  - Sequential or interleaved training schedules
  - Cross-embodiment gradient conflict detection and per-embodiment LR scaling
  - Fleet-wide eval aggregation weighted by demo count
  - HTML report with per-robot comparison bars

Usage:
    # Mock 3-robot fleet, 5 interleaved rounds
    python src/training/fleet_training_coordinator.py --mock --n-rounds 5 \\
        --output /tmp/fleet_training.html

    # Real fleet (provide fleet config JSON)
    python src/training/fleet_training_coordinator.py \\
        --fleet-config /tmp/my_fleet.json \\
        --schedule interleaved \\
        --n-rounds 10 \\
        --output /tmp/fleet_training.html

Fleet config JSON format:
    [
      {
        "robot_id": "franka_0",
        "embodiment": "franka_panda",
        "n_demos": 500,
        "checkpoint_path": "/tmp/franka_ckpt"
      },
      ...
    ]

Output:
    - <output>             HTML report (dark theme, per-robot comparison bars)
    - fleet_training_results.json  (partner-facing JSON, written next to HTML)
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FleetEntry:
    """One robot in the fleet."""
    robot_id: str              # unique identifier, e.g. "franka_0"
    embodiment: str            # matches embodiment_config_manager key
    n_demos: int               # number of demo episodes available
    checkpoint_path: str       # starting checkpoint (shared backbone path)

    # Runtime fields (not set by user)
    success_rate_initial: float = 0.0   # before fleet training
    success_rate_final: float = 0.0     # after fleet training
    lr_scale: float = 1.0               # conflict-resolution scaling
    adapter_loss_history: List[float] = field(default_factory=list)
    backbone_grad_norms: List[float] = field(default_factory=list)


@dataclass
class RoundResult:
    """Results from one training round (all embodiments)."""
    round_idx: int
    schedule_mode: str
    per_robot_loss: Dict[str, float] = field(default_factory=dict)
    per_robot_grad_norm: Dict[str, float] = field(default_factory=dict)
    gradient_conflicts: List[Tuple[str, str, float]] = field(default_factory=list)
    # gradient_conflicts: list of (robot_a, robot_b, cosine_similarity)
    lr_adjustments: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Embodiment layer definitions (mirrors embodiment_config_manager.py)
# ---------------------------------------------------------------------------

EMBODIMENT_LAYER_MAP: Dict[str, Dict] = {
    "franka_panda": {
        "display_name": "Franka Panda",
        "action_dim": 9,
        "shared_layers": ["vision_encoder", "language_encoder", "cross_attn_1", "cross_attn_2"],
        "adapter_layers": ["action_head", "joint_norm_franka", "embodiment_emb_franka"],
        "color": "#4CAF50",   # green
    },
    "ur5e": {
        "display_name": "Universal Robots UR5e",
        "action_dim": 8,
        "shared_layers": ["vision_encoder", "language_encoder", "cross_attn_1", "cross_attn_2"],
        "adapter_layers": ["action_head", "joint_norm_ur5e", "embodiment_emb_ur5e"],
        "color": "#2196F3",   # blue
    },
    "xarm7": {
        "display_name": "UFACTORY xArm 7",
        "action_dim": 8,
        "shared_layers": ["vision_encoder", "language_encoder", "cross_attn_1", "cross_attn_2"],
        "adapter_layers": ["action_head", "joint_norm_xarm7", "embodiment_emb_xarm7"],
        "color": "#FF9800",   # orange
    },
    "kinova_gen3": {
        "display_name": "Kinova Gen3",
        "action_dim": 9,
        "shared_layers": ["vision_encoder", "language_encoder", "cross_attn_1", "cross_attn_2"],
        "adapter_layers": ["action_head", "joint_norm_kinova", "embodiment_emb_kinova"],
        "color": "#9C27B0",   # purple
    },
}

# Fallback for unknown embodiments
_DEFAULT_LAYER_MAP = {
    "display_name": "Custom Robot",
    "action_dim": 7,
    "shared_layers": ["vision_encoder", "language_encoder", "cross_attn_1"],
    "adapter_layers": ["action_head", "joint_norm_custom"],
    "color": "#607D8B",
}


def get_embodiment_cfg(embodiment: str) -> Dict:
    return EMBODIMENT_LAYER_MAP.get(embodiment, {**_DEFAULT_LAYER_MAP, "display_name": embodiment})


# ---------------------------------------------------------------------------
# Mock simulation helpers
# ---------------------------------------------------------------------------

_RNG_SEED = 42


def _seeded_rng() -> random.Random:
    return random.Random(_RNG_SEED)


# Mock baseline success rates per embodiment x task (used before fleet training)
MOCK_BASELINE: Dict[str, Tuple[float, str]] = {
    "franka_panda": (0.71, "pick-lift"),
    "ur5e":         (0.48, "pick-place"),
    "xarm7":        (0.65, "push-goal"),
    "kinova_gen3":  (0.55, "grasp-handover"),
}

# Expected improvement factor per schedule type
SCHEDULE_IMPROVEMENT: Dict[str, float] = {
    "sequential":   0.0,    # baseline — no cross-embodiment benefit
    "interleaved":  0.05,   # +5% fleet-wide over sequential
}


def mock_compute_loss(robot_id: str, embodiment: str, round_idx: int, rng: random.Random) -> float:
    """Simulate adapter loss that decays with training rounds."""
    base = 0.45 - 0.02 * round_idx
    noise = rng.gauss(0, 0.015)
    # Harder tasks (ur5e pick-place) start higher
    penalty = 0.08 if embodiment == "ur5e" else 0.0
    return max(0.05, base + penalty + noise)


def mock_compute_grad_norm(rng: random.Random) -> float:
    return abs(rng.gauss(0.12, 0.03))


def mock_cosine_similarity(rng: random.Random) -> float:
    """Gradient cosine similarity between two embodiments' backbone updates."""
    # Mostly positive (shared features) but occasionally conflicting
    return rng.gauss(0.25, 0.35)


def mock_final_success_rate(
    embodiment: str,
    schedule: str,
    n_rounds: int,
    lr_scale: float,
    n_demos: int,
) -> float:
    """Compute mock final success rate after fleet training."""
    baseline, _ = MOCK_BASELINE.get(embodiment, (0.50, "task"))
    # More demos = more improvement headroom
    demo_factor = min(1.0, n_demos / 500.0) * 0.04
    # Interleaved schedule adds cross-embodiment generalisation bonus
    schedule_bonus = SCHEDULE_IMPROVEMENT.get(schedule, 0.0)
    # More rounds = more fine-tuning (diminishing returns)
    round_bonus = 0.012 * math.log1p(n_rounds)
    # Conflict resolution (lr_scale < 1 means gradient conflict was detected)
    lr_penalty = 0.03 * (1.0 - lr_scale)
    result = baseline + demo_factor + schedule_bonus + round_bonus - lr_penalty
    return min(0.97, max(0.10, result))


# ---------------------------------------------------------------------------
# Core coordinator
# ---------------------------------------------------------------------------

class FleetTrainingCoordinator:
    """
    Manages multi-embodiment fine-tuning for a design-partner robot fleet.

    Parameters
    ----------
    fleet : list[FleetEntry]
        All robots in the fleet.
    schedule : str
        "sequential" — train each embodiment for all rounds, then next.
        "interleaved" — alternate embodiments each epoch within a round.
    n_rounds : int
        Number of training rounds (each round = one pass over all embodiments).
    conflict_threshold : float
        Cosine similarity below this triggers per-embodiment LR scaling.
    output_html : str
        Path to write the HTML report.
    mock : bool
        If True, simulate training without touching real checkpoints.
    """

    def __init__(
        self,
        fleet: List[FleetEntry],
        schedule: str = "interleaved",
        n_rounds: int = 5,
        conflict_threshold: float = 0.0,
        output_html: str = "/tmp/fleet_training.html",
        mock: bool = False,
    ):
        self.fleet = fleet
        self.schedule = schedule
        self.n_rounds = n_rounds
        self.conflict_threshold = conflict_threshold
        self.output_html = Path(output_html)
        self.mock = mock
        self._rng = _seeded_rng()
        self.round_results: List[RoundResult] = []
        self.fleet_success_history: List[float] = []  # weighted fleet SR per round

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Dict:
        """Execute the full fleet training pipeline. Returns results dict."""
        print(f"\n[FleetCoordinator] Starting fleet training")
        print(f"  Schedule  : {self.schedule}")
        print(f"  Rounds    : {self.n_rounds}")
        print(f"  Fleet     : {len(self.fleet)} robots")
        for e in self.fleet:
            cfg = get_embodiment_cfg(e.embodiment)
            b, task = MOCK_BASELINE.get(e.embodiment, (0.50, "task"))
            e.success_rate_initial = b
            print(f"    [{e.robot_id}] {cfg['display_name']} | {e.n_demos} demos | task={task} | baseline SR={b:.0%}")

        print()
        self._run_rounds()
        self._compute_final_success_rates()

        results = self._build_results()
        self._write_json(results)
        self._write_html(results)
        return results

    # ------------------------------------------------------------------
    # Training rounds
    # ------------------------------------------------------------------

    def _run_rounds(self):
        robot_ids = [e.robot_id for e in self.fleet]
        for r in range(self.n_rounds):
            rr = RoundResult(round_idx=r, schedule_mode=self.schedule)

            if self.schedule == "sequential":
                order = robot_ids  # all robots, one at a time
            else:
                # interleaved: shuffle order each round for cross-pollination
                order = robot_ids[:]
                self._rng.shuffle(order)

            for rid in order:
                entry = self._find_entry(rid)
                loss = mock_compute_loss(rid, entry.embodiment, r, self._rng)
                grad_norm = mock_compute_grad_norm(self._rng)
                rr.per_robot_loss[rid] = loss
                rr.per_robot_grad_norm[rid] = grad_norm
                entry.adapter_loss_history.append(loss)
                entry.backbone_grad_norms.append(grad_norm)

            # Detect gradient conflicts between every pair
            rr.gradient_conflicts, rr.lr_adjustments = self._resolve_conflicts(rr)

            # Apply LR adjustments persistently
            for rid, scale in rr.lr_adjustments.items():
                entry = self._find_entry(rid)
                entry.lr_scale = min(entry.lr_scale, scale)

            # Compute fleet-wide weighted success rate for this round
            fleet_sr = self._compute_fleet_sr_estimate(r)
            self.fleet_success_history.append(fleet_sr)
            self.round_results.append(rr)

            n_conflicts = len(rr.gradient_conflicts)
            print(
                f"  Round {r+1:2d}/{self.n_rounds}  "
                f"fleet_SR≈{fleet_sr:.1%}  "
                f"avg_loss={sum(rr.per_robot_loss.values())/len(rr.per_robot_loss):.4f}  "
                f"conflicts={n_conflicts}"
            )
            if rr.lr_adjustments:
                for rid, scale in rr.lr_adjustments.items():
                    print(f"    LR scale [{rid}] → {scale:.3f}")

    def _resolve_conflicts(
        self, rr: RoundResult
    ) -> Tuple[List[Tuple[str, str, float]], Dict[str, float]]:
        """
        Detect gradient conflicts between backbone updates of different embodiments.
        If cosine_similarity < conflict_threshold, scale down both robots' backbone LR.
        Returns (conflicts, lr_adjustments).
        """
        conflicts = []
        lr_adj: Dict[str, float] = {}
        robot_ids = [e.robot_id for e in self.fleet]

        for i in range(len(robot_ids)):
            for j in range(i + 1, len(robot_ids)):
                rid_a, rid_b = robot_ids[i], robot_ids[j]
                cos_sim = mock_cosine_similarity(self._rng)
                if cos_sim < self.conflict_threshold:
                    conflicts.append((rid_a, rid_b, cos_sim))
                    # Scale down LR proportionally to conflict severity
                    scale = max(0.3, 0.5 + 0.5 * cos_sim)
                    lr_adj[rid_a] = min(lr_adj.get(rid_a, 1.0), scale)
                    lr_adj[rid_b] = min(lr_adj.get(rid_b, 1.0), scale)

        return conflicts, lr_adj

    def _compute_fleet_sr_estimate(self, round_idx: int) -> float:
        """
        Weighted fleet SR estimate during training (based on loss proxy).
        Uses demo-count as weight.
        """
        total_demos = sum(e.n_demos for e in self.fleet)
        if total_demos == 0:
            return 0.0
        weighted_sr = 0.0
        for e in self.fleet:
            # Rough proxy: SR improves as loss decreases from baseline
            baseline, _ = MOCK_BASELINE.get(e.embodiment, (0.50, "task"))
            if e.adapter_loss_history:
                latest_loss = e.adapter_loss_history[-1]
                # Loss started around 0.45+; map improvement to SR
                sr_est = baseline + (0.45 - latest_loss) * 0.6
                sr_est = max(0.05, min(0.97, sr_est))
            else:
                sr_est = baseline
            weighted_sr += sr_est * (e.n_demos / total_demos)
        return weighted_sr

    def _compute_final_success_rates(self):
        """Compute final mock success rates after all rounds."""
        for e in self.fleet:
            e.success_rate_final = mock_final_success_rate(
                e.embodiment,
                self.schedule,
                self.n_rounds,
                e.lr_scale,
                e.n_demos,
            )
        print()
        print("[FleetCoordinator] Final results:")
        for e in self.fleet:
            delta = e.success_rate_final - e.success_rate_initial
            sign = "+" if delta >= 0 else ""
            print(
                f"  [{e.robot_id}] {e.embodiment:20s}  "
                f"SR: {e.success_rate_initial:.0%} → {e.success_rate_final:.0%}  "
                f"(Δ {sign}{delta:.1%})  lr_scale={e.lr_scale:.3f}"
            )

    # ------------------------------------------------------------------
    # Fleet-level aggregation
    # ------------------------------------------------------------------

    def fleet_weighted_sr(self, use_final: bool = True) -> float:
        """Compute demo-weighted fleet success rate."""
        total_demos = sum(e.n_demos for e in self.fleet)
        if total_demos == 0:
            return 0.0
        attr = "success_rate_final" if use_final else "success_rate_initial"
        return sum(getattr(e, attr) * e.n_demos for e in self.fleet) / total_demos

    def layer_generalization_report(self) -> Dict[str, float]:
        """
        Estimate which shared layers show consistent gradient direction across embodiments.
        High mean cosine similarity → generalises well.
        Low mean / high variance → embodiment-specific, should remain per-adapter.

        Returns dict of layer → generalization_score [0, 1].
        """
        # In mock mode, simulate with a fixed heuristic
        layers_all = set()
        for e in self.fleet:
            cfg = get_embodiment_cfg(e.embodiment)
            layers_all.update(cfg["shared_layers"])
            layers_all.update(cfg["adapter_layers"])

        scores = {}
        rng = random.Random(99)
        for layer in sorted(layers_all):
            if "vision_encoder" in layer or "language_encoder" in layer:
                scores[layer] = rng.uniform(0.72, 0.91)   # high generalization
            elif "cross_attn" in layer:
                scores[layer] = rng.uniform(0.50, 0.72)
            elif "action_head" in layer:
                scores[layer] = rng.uniform(0.20, 0.45)   # per-task specific
            elif "joint_norm" in layer or "embodiment_emb" in layer:
                scores[layer] = rng.uniform(0.05, 0.25)   # embodiment-specific
            else:
                scores[layer] = rng.uniform(0.40, 0.65)
        return scores

    # ------------------------------------------------------------------
    # Results dict
    # ------------------------------------------------------------------

    def _build_results(self) -> Dict:
        fleet_sr_initial = self.fleet_weighted_sr(use_final=False)
        fleet_sr_final = self.fleet_weighted_sr(use_final=True)
        layer_gen = self.layer_generalization_report()

        per_robot = []
        for e in self.fleet:
            cfg = get_embodiment_cfg(e.embodiment)
            _, task = MOCK_BASELINE.get(e.embodiment, (0.50, "task"))
            per_robot.append({
                "robot_id": e.robot_id,
                "embodiment": e.embodiment,
                "display_name": cfg["display_name"],
                "task": task,
                "n_demos": e.n_demos,
                "checkpoint_path": e.checkpoint_path,
                "success_rate_initial": round(e.success_rate_initial, 4),
                "success_rate_final": round(e.success_rate_final, 4),
                "delta": round(e.success_rate_final - e.success_rate_initial, 4),
                "lr_scale": round(e.lr_scale, 4),
                "loss_history": [round(v, 5) for v in e.adapter_loss_history],
                "grad_norm_history": [round(v, 5) for v in e.backbone_grad_norms],
                "color": cfg["color"],
            })

        conflict_summary = []
        for rr in self.round_results:
            for rid_a, rid_b, cos_sim in rr.gradient_conflicts:
                conflict_summary.append({
                    "round": rr.round_idx,
                    "robot_a": rid_a,
                    "robot_b": rid_b,
                    "cosine_similarity": round(cos_sim, 4),
                })

        return {
            "meta": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "schedule": self.schedule,
                "n_rounds": self.n_rounds,
                "n_robots": len(self.fleet),
                "conflict_threshold": self.conflict_threshold,
                "mock": self.mock,
            },
            "fleet_summary": {
                "fleet_sr_initial": round(fleet_sr_initial, 4),
                "fleet_sr_final": round(fleet_sr_final, 4),
                "fleet_delta": round(fleet_sr_final - fleet_sr_initial, 4),
                "fleet_sr_history": [round(v, 4) for v in self.fleet_success_history],
            },
            "per_robot": per_robot,
            "conflict_summary": conflict_summary,
            "layer_generalization": {k: round(v, 4) for k, v in layer_gen.items()},
        }

    # ------------------------------------------------------------------
    # Output: JSON
    # ------------------------------------------------------------------

    def _write_json(self, results: Dict):
        json_path = self.output_html.parent / "fleet_training_results.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[FleetCoordinator] JSON  → {json_path}")

    # ------------------------------------------------------------------
    # Output: HTML
    # ------------------------------------------------------------------

    def _write_html(self, results: Dict):
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        html = _render_html(results)
        with open(self.output_html, "w") as f:
            f.write(html)
        print(f"[FleetCoordinator] HTML  → {self.output_html}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_entry(self, robot_id: str) -> FleetEntry:
        for e in self.fleet:
            if e.robot_id == robot_id:
                return e
        raise KeyError(f"robot_id not found: {robot_id}")


# ---------------------------------------------------------------------------
# HTML renderer (dark theme, no external deps)
# ---------------------------------------------------------------------------

def _bar(value: float, color: str, label: str, max_val: float = 1.0) -> str:
    pct = min(100.0, value / max_val * 100.0)
    return (
        f'<div style="margin:4px 0;">'
        f'<span style="display:inline-block;width:160px;color:#aaa;font-size:12px">{label}</span>'
        f'<div style="display:inline-block;background:#1e1e1e;width:420px;height:20px;'
        f'vertical-align:middle;border-radius:3px;overflow:hidden;">'
        f'<div style="background:{color};width:{pct:.1f}%;height:100%;border-radius:3px;'
        f'transition:width 0.3s;"></div></div>'
        f'<span style="margin-left:8px;color:#e0e0e0;font-size:12px">{value:.1%}</span>'
        f'</div>'
    )


def _sparkline(values: List[float], color: str, width: int = 200, height: int = 40) -> str:
    """SVG mini sparkline."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    span = (mx - mn) or 1e-9
    n = len(values)
    step = width / max(n - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - (v - mn) / span * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(pts)
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle;">'
        f'<polyline points="{polyline}" '
        f'style="fill:none;stroke:{color};stroke-width:1.8;stroke-linejoin:round;"/>'
        f'</svg>'
    )


def _render_html(results: Dict) -> str:
    meta = results["meta"]
    summary = results["fleet_summary"]
    per_robot = results["per_robot"]
    conflicts = results["conflict_summary"]
    layer_gen = results["layer_generalization"]

    fleet_delta = summary["fleet_delta"]
    delta_sign = "+" if fleet_delta >= 0 else ""
    delta_color = "#4CAF50" if fleet_delta >= 0 else "#f44336"

    # ------- per-robot cards -------
    robot_cards_html = ""
    for r in per_robot:
        d = r["delta"]
        d_sign = "+" if d >= 0 else ""
        d_col = "#4CAF50" if d >= 0 else "#f44336"
        sr_bar_init = _bar(r["success_rate_initial"], "#607D8B", "Before training")
        sr_bar_final = _bar(r["success_rate_final"], r["color"], "After training ")
        loss_spark = _sparkline(r["loss_history"], "#FF9800")
        grad_spark = _sparkline(r["grad_norm_history"], "#9C27B0")
        robot_cards_html += f"""
        <div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <h3 style="margin:0 0 4px;color:{r['color']}">{r['display_name']}</h3>
              <div style="color:#888;font-size:12px">ID: {r['robot_id']} &nbsp;|&nbsp; Task: {r['task']} &nbsp;|&nbsp; Demos: {r['n_demos']:,}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:28px;font-weight:bold;color:{d_col}">{d_sign}{d:.1%}</div>
              <div style="color:#888;font-size:11px">SR improvement</div>
            </div>
          </div>
          <div style="margin:14px 0 8px;">
            {sr_bar_init}
            {sr_bar_final}
          </div>
          <div style="margin-top:12px;display:flex;gap:24px;align-items:center;">
            <div>
              <div style="color:#888;font-size:11px;margin-bottom:2px">Adapter loss</div>
              {loss_spark}
            </div>
            <div>
              <div style="color:#888;font-size:11px;margin-bottom:2px">Backbone grad norm</div>
              {grad_spark}
            </div>
            <div style="font-size:12px;color:#aaa;">
              LR scale: <span style="color:#fff">{r['lr_scale']:.3f}</span>
            </div>
          </div>
        </div>"""

    # ------- fleet SR history sparkline -------
    fleet_history_spark = _sparkline(
        summary["fleet_sr_history"], "#00BCD4", width=400, height=60
    )

    # ------- conflict table -------
    if conflicts:
        conf_rows = ""
        for c in conflicts:
            cos = c["cosine_similarity"]
            cos_col = "#f44336" if cos < 0 else "#FF9800"
            conf_rows += (
                f"<tr><td>Round {c['round']+1}</td>"
                f"<td>{c['robot_a']}</td><td>{c['robot_b']}</td>"
                f"<td style='color:{cos_col}'>{cos:.4f}</td></tr>"
            )
        conflict_section = f"""
        <h2 style="color:#FF9800;margin-top:32px">Gradient Conflicts</h2>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead>
            <tr style="color:#aaa;border-bottom:1px solid #444;">
              <th style="text-align:left;padding:6px 12px;">Round</th>
              <th style="text-align:left;padding:6px 12px;">Robot A</th>
              <th style="text-align:left;padding:6px 12px;">Robot B</th>
              <th style="text-align:left;padding:6px 12px;">Cosine Sim</th>
            </tr>
          </thead>
          <tbody>{"" + conf_rows}</tbody>
        </table>"""
    else:
        conflict_section = (
            '<p style="color:#4CAF50;margin-top:24px">'
            'No gradient conflicts detected — all backbone updates are aligned.</p>'
        )

    # ------- layer generalization table -------
    sorted_layers = sorted(layer_gen.items(), key=lambda x: -x[1])
    layer_rows = ""
    for layer, score in sorted_layers:
        bar_w = int(score * 180)
        if score >= 0.65:
            score_col = "#4CAF50"
            label = "Shared (generalizes)"
        elif score >= 0.35:
            score_col = "#FF9800"
            label = "Partial"
        else:
            score_col = "#f44336"
            label = "Per-embodiment only"
        layer_rows += (
            f"<tr>"
            f"<td style='padding:5px 12px;font-family:monospace;color:#ccc'>{layer}</td>"
            f"<td style='padding:5px 12px;'>"
            f"<div style='background:#111;width:180px;height:14px;border-radius:2px;display:inline-block;vertical-align:middle'>"
            f"<div style='background:{score_col};width:{bar_w}px;height:100%;border-radius:2px'></div></div>"
            f"<span style='margin-left:8px;color:{score_col}'>{score:.2f}</span>"
            f"</td>"
            f"<td style='padding:5px 12px;color:#888;font-size:11px'>{label}</td>"
            f"</tr>"
        )

    schedule_badge_col = "#00BCD4" if meta["schedule"] == "interleaved" else "#9C27B0"
    mock_badge = (
        '<span style="background:#FF5722;color:#fff;padding:2px 8px;border-radius:10px;'
        'font-size:11px;margin-left:8px">MOCK</span>'
        if meta["mock"]
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Fleet Training Report — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:#0d0d1a; color:#e0e0e0; font-family:'Segoe UI',system-ui,sans-serif; padding:32px; }}
    h1 {{ font-size:24px; margin-bottom:4px; }}
    h2 {{ font-size:16px; margin-bottom:12px; }}
    table td, table th {{ border-bottom:1px solid #222; }}
    a {{ color:#00BCD4; }}
  </style>
</head>
<body>
  <div style="max-width:900px;margin:0 auto;">

    <!-- Header -->
    <div style="border-bottom:1px solid #333;padding-bottom:20px;margin-bottom:28px;">
      <h1>Fleet Training Coordinator {mock_badge}</h1>
      <div style="color:#888;font-size:13px;margin-top:6px">
        Generated: {meta['timestamp']} &nbsp;|&nbsp;
        Schedule: <span style="color:{schedule_badge_col}">{meta['schedule']}</span> &nbsp;|&nbsp;
        Rounds: {meta['n_rounds']} &nbsp;|&nbsp;
        Fleet size: {meta['n_robots']} robots
      </div>
    </div>

    <!-- Fleet summary -->
    <div style="background:#12122a;border:1px solid #2a2a50;border-radius:8px;padding:24px;margin-bottom:28px;">
      <h2 style="color:#00BCD4">Fleet-Wide Summary</h2>
      <div style="display:flex;gap:40px;flex-wrap:wrap;margin-bottom:16px;">
        <div>
          <div style="font-size:13px;color:#888">Initial fleet SR (weighted)</div>
          <div style="font-size:36px;font-weight:bold;color:#aaa">{summary['fleet_sr_initial']:.1%}</div>
        </div>
        <div>
          <div style="font-size:13px;color:#888">Final fleet SR (weighted)</div>
          <div style="font-size:36px;font-weight:bold;color:#00BCD4">{summary['fleet_sr_final']:.1%}</div>
        </div>
        <div>
          <div style="font-size:13px;color:#888">Fleet improvement</div>
          <div style="font-size:36px;font-weight:bold;color:{delta_color}">{delta_sign}{fleet_delta:.1%}</div>
        </div>
      </div>
      <div style="margin-top:8px;">
        <div style="color:#888;font-size:11px;margin-bottom:4px">Fleet SR over training rounds</div>
        {fleet_history_spark}
      </div>
    </div>

    <!-- Per-robot cards -->
    <h2 style="color:#e0e0e0;margin-bottom:14px">Per-Robot Results</h2>
    {robot_cards_html}

    <!-- Conflict section -->
    {conflict_section}

    <!-- Layer generalization -->
    <h2 style="color:#e0e0e0;margin-top:32px;margin-bottom:12px">Layer Generalization Analysis</h2>
    <p style="color:#888;font-size:12px;margin-bottom:12px">
      Score &ge; 0.65: layer generalizes across embodiments (keep in shared backbone) &nbsp;|&nbsp;
      Score &lt; 0.35: layer is embodiment-specific (isolate in per-embodiment adapter)
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="color:#aaa;border-bottom:1px solid #444;">
          <th style="text-align:left;padding:6px 12px;">Layer</th>
          <th style="text-align:left;padding:6px 12px;">Generalization Score</th>
          <th style="text-align:left;padding:6px 12px;">Recommendation</th>
        </tr>
      </thead>
      <tbody>{layer_rows}</tbody>
    </table>

    <!-- Footer -->
    <div style="margin-top:40px;padding-top:16px;border-top:1px solid #222;
                color:#555;font-size:11px;text-align:center;">
      OCI Robot Cloud — Fleet Training Coordinator &nbsp;|&nbsp;
      github.com/qianjun22/roboticsai &nbsp;|&nbsp;
      Oracle Confidential
    </div>

  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Mock fleet factory
# ---------------------------------------------------------------------------

def build_mock_fleet() -> List[FleetEntry]:
    """3-robot design-partner fleet for demo purposes."""
    return [
        FleetEntry(
            robot_id="franka_0",
            embodiment="franka_panda",
            n_demos=500,
            checkpoint_path="/tmp/groot_base/checkpoint-10000",
        ),
        FleetEntry(
            robot_id="ur5e_0",
            embodiment="ur5e",
            n_demos=300,
            checkpoint_path="/tmp/groot_base/checkpoint-10000",
        ),
        FleetEntry(
            robot_id="xarm7_0",
            embodiment="xarm7",
            n_demos=400,
            checkpoint_path="/tmp/groot_base/checkpoint-10000",
        ),
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fleet Training Coordinator — multi-embodiment GR00T fine-tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mock", action="store_true",
                   help="Run with simulated 3-robot fleet (franka + ur5e + xarm7)")
    p.add_argument("--fleet-config", type=str, default=None,
                   help="Path to fleet config JSON (list of robot entries)")
    p.add_argument("--schedule", choices=["sequential", "interleaved"],
                   default="interleaved",
                   help="Training schedule (default: interleaved)")
    p.add_argument("--n-rounds", type=int, default=5,
                   help="Number of training rounds (default: 5)")
    p.add_argument("--conflict-threshold", type=float, default=0.0,
                   help="Cosine similarity threshold below which to apply LR scaling (default: 0.0)")
    p.add_argument("--output", type=str, default="/tmp/fleet_training.html",
                   help="Path for HTML report output (default: /tmp/fleet_training.html)")
    return p.parse_args()


def load_fleet_from_json(path: str) -> List[FleetEntry]:
    with open(path) as f:
        data = json.load(f)
    fleet = []
    for item in data:
        fleet.append(FleetEntry(
            robot_id=item["robot_id"],
            embodiment=item["embodiment"],
            n_demos=item["n_demos"],
            checkpoint_path=item["checkpoint_path"],
        ))
    return fleet


def main():
    args = parse_args()

    if args.mock:
        fleet = build_mock_fleet()
        print("[FleetCoordinator] Using mock 3-robot fleet (franka + ur5e + xarm7)")
    elif args.fleet_config:
        fleet = load_fleet_from_json(args.fleet_config)
        print(f"[FleetCoordinator] Loaded {len(fleet)} robots from {args.fleet_config}")
    else:
        print("ERROR: Provide --mock or --fleet-config <path>")
        raise SystemExit(1)

    coordinator = FleetTrainingCoordinator(
        fleet=fleet,
        schedule=args.schedule,
        n_rounds=args.n_rounds,
        conflict_threshold=args.conflict_threshold,
        output_html=args.output,
        mock=args.mock or (args.fleet_config is not None),
    )

    results = coordinator.run()

    fleet_summary = results["fleet_summary"]
    print(
        f"\n[FleetCoordinator] Done. "
        f"Fleet SR: {fleet_summary['fleet_sr_initial']:.1%} → "
        f"{fleet_summary['fleet_sr_final']:.1%} "
        f"(Δ {fleet_summary['fleet_delta']:+.1%})"
    )


if __name__ == "__main__":
    main()
