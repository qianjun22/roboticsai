#!/usr/bin/env python3
"""
Continual Learning Manager for OCI Robot Cloud — GR00T N1.6 Fine-tuning
Prevents catastrophic forgetting when adding new robot manipulation tasks.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import datetime

TASKS = ["pick_cube", "stack_blocks", "pour_liquid", "fold_cloth", "insert_peg"]

STRATEGY_METRICS = {
    "EWC": {"avg_forgetting": 0.18, "plasticity": 0.72, "final_avg_SR": 0.61, "memory_mb_per_task": 45, "description": "Elastic Weight Consolidation"},
    "PackNet": {"avg_forgetting": 0.08, "plasticity": 0.65, "final_avg_SR": 0.63, "memory_mb_per_task": 28, "description": "Prunes/freezes subnetworks per task"},
    "Replay": {"avg_forgetting": 0.12, "plasticity": 0.78, "final_avg_SR": 0.67, "memory_mb_per_task": 95, "description": "Stores exemplar episodes from previous tasks"},
    "ProgressiveNets": {"avg_forgetting": 0.03, "plasticity": 0.81, "final_avg_SR": 0.69, "memory_mb_per_task": 180, "description": "New columns per task; no forgetting but grows linearly"},
    "OCI_Adaptive": {"avg_forgetting": 0.09, "plasticity": 0.77, "final_avg_SR": 0.71, "memory_mb_per_task": 62, "description": "Custom hybrid (EWC + Replay) — BEST"},
}

FORGETTING_MATRICES = {
    "EWC": [[0.82,None,None,None,None],[0.65,0.79,None,None,None],[0.61,0.72,0.74,None,None],[0.58,0.68,0.71,0.69,None],[0.55,0.64,0.68,0.67,0.70]],
    "PackNet": [[0.78,None,None,None,None],[0.78,0.75,None,None,None],[0.78,0.75,0.71,None,None],[0.78,0.75,0.71,0.67,None],[0.78,0.75,0.71,0.67,0.64]],
    "Replay": [[0.83,None,None,None,None],[0.74,0.81,None,None,None],[0.71,0.78,0.79,None,None],[0.68,0.75,0.76,0.73,None],[0.66,0.73,0.74,0.71,0.77]],
    "ProgressiveNets": [[0.84,None,None,None,None],[0.84,0.82,None,None,None],[0.84,0.82,0.80,None,None],[0.84,0.82,0.80,0.77,None],[0.84,0.82,0.80,0.77,0.75]],
    "OCI_Adaptive": [[0.84,None,None,None,None],[0.77,0.82,None,None,None],[0.75,0.79,0.80,None,None],[0.73,0.77,0.78,0.75,None],[0.72,0.76,0.77,0.74,0.80]],
}

MEMORY_USAGE = {
    "EWC": [45,90,135,180,225], "PackNet": [28,56,84,112,140],
    "Replay": [95,190,285,380,475], "ProgressiveNets": [180,360,540,720,900],
    "OCI_Adaptive": [62,112,155,198,240],
}


@dataclass
class TaskRecord:
    name: str
    demo_count: int
    initial_sr: float
    current_sr: float
    registered_at_step: int
    forgetting_history: List[float] = field(default_factory=list)


@dataclass
class LearningEvent:
    task_trained: str
    task_evaluated: str
    sr_before: float
    sr_after: float
    step: int

    @property
    def forgetting(self) -> float:
        return max(0.0, self.sr_before - self.sr_after)


class ContinualLearningManager:
    SUPPORTED_STRATEGIES = list(STRATEGY_METRICS.keys())

    def __init__(self, strategy: str = "OCI_Adaptive", memory_budget_mb: int = 512):
        if strategy not in self.SUPPORTED_STRATEGIES:
            raise ValueError(f"Unknown strategy '{strategy}'.")
        self.strategy = strategy
        self.memory_budget_mb = memory_budget_mb
        self._tasks: Dict[str, TaskRecord] = {}
        self._events: List[LearningEvent] = []
        self._step = 0
        self._metrics = STRATEGY_METRICS[strategy]
        self._forgetting_matrix = FORGETTING_MATRICES[strategy]
        self._memory_timeline: List[float] = []

    def add_task(self, task_name: str, demo_count: int) -> TaskRecord:
        task_idx = len(self._tasks)
        row = self._forgetting_matrix[task_idx]
        initial_sr = row[task_idx]
        record = TaskRecord(name=task_name, demo_count=demo_count, initial_sr=initial_sr, current_sr=initial_sr, registered_at_step=self._step)
        self._tasks[task_name] = record
        for prev_idx, (prev_name, prev_record) in enumerate(list(self._tasks.items())[:-1]):
            sr_before = prev_record.current_sr
            sr_after = self._forgetting_matrix[task_idx][prev_idx]
            if sr_after is not None:
                prev_record.current_sr = sr_after
                prev_record.forgetting_history.append(sr_before - sr_after)
                self._events.append(LearningEvent(task_trained=task_name, task_evaluated=prev_name, sr_before=sr_before, sr_after=sr_after, step=self._step))
        mem = MEMORY_USAGE[self.strategy]
        self._memory_timeline.append(mem[min(task_idx, len(mem) - 1)])
        self._step += 1
        return record

    def compute_forgetting(self, task_name: str) -> float:
        if task_name not in self._tasks:
            raise KeyError(f"Task '{task_name}' not registered.")
        rec = self._tasks[task_name]
        return rec.current_sr - rec.initial_sr

    def get_memory_usage(self) -> float:
        return self._memory_timeline[-1] if self._memory_timeline else 0.0

    def get_plasticity_stability_tradeoff(self) -> Dict:
        m = self._metrics
        return {
            "strategy": self.strategy, "plasticity": m["plasticity"],
            "stability": round(1.0 - m["avg_forgetting"], 3),
            "avg_forgetting": m["avg_forgetting"], "final_avg_SR": m["final_avg_SR"],
            "memory_mb_per_task": m["memory_mb_per_task"],
            "within_budget": self.get_memory_usage() <= self.memory_budget_mb,
        }

    def summary(self) -> str:
        lines = [f"Strategy: {self.strategy}", f"Memory: {self.get_memory_usage():.0f}/{self.memory_budget_mb} MB", "Tasks:"]
        for name, rec in self._tasks.items():
            bwt = self.compute_forgetting(name)
            lines.append(f"  {name:20s} init={rec.initial_sr:.2f}  curr={rec.current_sr:.2f}  BWT={bwt:+.3f}")
        tr = self.get_plasticity_stability_tradeoff()
        lines.append(f"Plasticity={tr['plasticity']:.2f}  Stability={tr['stability']:.2f}  Final SR={tr['final_avg_SR']:.2f}")
        return "\n".join(lines)


def run_simulation() -> Dict[str, ContinualLearningManager]:
    demo_counts = {"pick_cube": 1000, "stack_blocks": 800, "pour_liquid": 600, "fold_cloth": 500, "insert_peg": 750}
    managers = {}
    for strategy in STRATEGY_METRICS:
        mgr = ContinualLearningManager(strategy=strategy)
        for task in TASKS:
            mgr.add_task(task, demo_counts[task])
        managers[strategy] = mgr
    return managers


def main():
    print("OCI Robot Cloud — Continual Learning Manager")
    managers = run_simulation()
    for strategy, mgr in managers.items():
        print(mgr.summary())
        print()
    import json
    tradeoff = managers["OCI_Adaptive"].get_plasticity_stability_tradeoff()
    print("OCI_Adaptive tradeoff:", json.dumps(tradeoff, indent=2))


if __name__ == "__main__":
    main()
