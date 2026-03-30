"""
episode_success_predictor.py — Early-stop predictor for robot eval episodes.

Trains a lightweight ML classifier to predict episode success from the first 10
steps of an episode. Useful for aborting episodes that are already on a failure
trajectory, saving ~40% eval GPU compute.

Features extracted from steps 0-9:
  - mean / std of cube_z change        (is the cube being lifted?)
  - gripper_closure rate               (fraction of steps where gripper closes)
  - approach velocity                  (mean absolute movement in joints 1-3)
  - policy confidence proxy            (mean action variance across the window)

Classifiers:
  1. Logistic regression (scratch SGD, no sklearn)
  2. Threshold-based heuristic
  3. Majority-vote ensemble (LR + heuristic votes)

Outputs:
  - HTML report with dark theme: ROC, PR, confusion matrix, calibration, threshold analysis
  - Trained model JSON: /tmp/episode_success_predictor.json

Usage:
  python src/eval/episode_success_predictor.py --mock --n-train 500 \\
      --output /tmp/predictor_report.html

  # Reuse saved model on new episodes:
  python src/eval/episode_success_predictor.py --load /tmp/episode_success_predictor.json \\
      --mock --n-train 0 --n-test 100 --output /tmp/predictor_report.html
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WINDOW = 10          # number of steps used for feature extraction
FAIL_THRESHOLD = 0.8  # predict "will fail" when P(failure) > this value
FEATURE_NAMES = [
    "cube_z_mean_delta",
    "cube_z_std_delta",
    "gripper_closure_rate",
    "approach_velocity",
    "action_variance_proxy",
]
N_FEATURES = len(FEATURE_NAMES)

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _simulate_episode(success: bool, rng: random.Random) -> Dict:
    """
    Simulate a single labeled episode returning per-step observations and
    the ground-truth success label.

    Successful episodes show a rising cube_z trajectory, steady gripper
    closure, and directed joint movement; failed episodes show noisy or
    flat signals.
    """
    steps = []
    cube_z = 0.05  # table surface height
    gripper = 0.0
    joints = [0.0] * 6

    for t in range(50):
        if success:
            # Smooth lift trajectory with small noise
            if t >= 5:
                cube_z += rng.gauss(0.012, 0.003)
            gripper = min(1.0, gripper + rng.gauss(0.08, 0.01))
            joint_delta = [rng.gauss(0.05, 0.01) for _ in range(6)]
            action_vec = [rng.gauss(0.04, 0.005) for _ in range(8)]
        else:
            # Flat / chaotic trajectory
            cube_z += rng.gauss(0.001, 0.008)
            cube_z = max(0.04, cube_z)  # stays near table
            gripper += rng.gauss(0.01, 0.04)
            gripper = max(0.0, min(1.0, gripper))
            joint_delta = [rng.gauss(0.0, 0.04) for _ in range(6)]
            action_vec = [rng.gauss(0.0, 0.02) for _ in range(8)]

        joints = [j + d for j, d in zip(joints, joint_delta)]
        steps.append({
            "cube_z": cube_z,
            "gripper": gripper,
            "joints": joints[:],
            "action": action_vec,
        })

    return {"steps": steps, "success": int(success)}


def generate_mock_episodes(n: int, success_rate: float = 0.45,
                           seed: int = 42) -> List[Dict]:
    rng = random.Random(seed)
    episodes = []
    for i in range(n):
        success = rng.random() < success_rate
        episodes.append(_simulate_episode(success, rng))
    return episodes


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_features(episode: Dict, window: int = WINDOW) -> List[float]:
    """
    Extract a fixed-length feature vector from the first `window` steps.

    Returns list of length N_FEATURES.
    """
    steps = episode["steps"][:window]
    if len(steps) < 2:
        return [0.0] * N_FEATURES

    cube_zs = [s["cube_z"] for s in steps]
    cube_deltas = [cube_zs[i + 1] - cube_zs[i] for i in range(len(cube_zs) - 1)]

    mean_delta = sum(cube_deltas) / len(cube_deltas)
    std_delta = math.sqrt(
        sum((d - mean_delta) ** 2 for d in cube_deltas) / len(cube_deltas)
    )

    grippers = [s["gripper"] for s in steps]
    gripper_closure_rate = sum(1 for g in grippers if g > 0.5) / len(grippers)

    # Approach velocity: mean |delta| of joints 0-2 (shoulder / elbow)
    joint_velocities = []
    for i in range(len(steps) - 1):
        j_now = steps[i]["joints"][:3]
        j_next = steps[i + 1]["joints"][:3]
        vel = sum(abs(j_next[k] - j_now[k]) for k in range(3)) / 3
        joint_velocities.append(vel)
    approach_vel = sum(joint_velocities) / len(joint_velocities)

    # Action variance proxy: mean variance of action vectors over window
    action_variances = []
    for s in steps:
        a = s["action"]
        mu = sum(a) / len(a)
        var = sum((x - mu) ** 2 for x in a) / len(a)
        action_variances.append(var)
    action_var_proxy = sum(action_variances) / len(action_variances)

    return [mean_delta, std_delta, gripper_closure_rate, approach_vel, action_var_proxy]


def build_dataset(episodes: List[Dict]) -> Tuple[List[List[float]], List[int]]:
    X = [extract_features(ep) for ep in episodes]
    y = [ep["success"] for ep in episodes]
    return X, y


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def compute_scaler(X: List[List[float]]) -> Tuple[List[float], List[float]]:
    """Return (mean, std) per feature for z-score normalisation."""
    n, d = len(X), len(X[0])
    means = [sum(X[i][j] for i in range(n)) / n for j in range(d)]
    stds = []
    for j in range(d):
        var = sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n
        stds.append(math.sqrt(var) if var > 1e-12 else 1.0)
    return means, stds


def scale(X: List[List[float]], means: List[float], stds: List[float]) -> List[List[float]]:
    return [[(X[i][j] - means[j]) / stds[j] for j in range(len(X[i]))] for i in range(len(X))]


# ---------------------------------------------------------------------------
# Logistic Regression (SGD, no sklearn)
# ---------------------------------------------------------------------------

class LogisticRegression:
    """
    Binary logistic regression trained with mini-batch SGD.
    No external dependencies.
    """

    def __init__(self, lr: float = 0.05, epochs: int = 200,
                 batch_size: int = 32, l2: float = 1e-4,
                 seed: int = 0):
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.l2 = l2
        self.seed = seed
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.train_losses: List[float] = []

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sigmoid(z: float) -> float:
        # numerically stable
        if z >= 0:
            ez = math.exp(-z)
            return 1.0 / (1.0 + ez)
        ez = math.exp(z)
        return ez / (1.0 + ez)

    def _predict_proba_raw(self, x: List[float]) -> float:
        z = self.bias + sum(self.weights[j] * x[j] for j in range(len(x)))
        return self._sigmoid(z)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def fit(self, X: List[List[float]], y: List[int]) -> "LogisticRegression":
        rng = random.Random(self.seed)
        n, d = len(X), len(X[0])
        self.weights = [rng.gauss(0, 0.01) for _ in range(d)]
        self.bias = 0.0
        self.train_losses = []

        indices = list(range(n))
        for epoch in range(self.epochs):
            rng.shuffle(indices)
            epoch_loss = 0.0
            batches = 0
            for start in range(0, n, self.batch_size):
                batch = indices[start: start + self.batch_size]
                grad_w = [0.0] * d
                grad_b = 0.0
                batch_loss = 0.0
                for idx in batch:
                    xi, yi = X[idx], y[idx]
                    pi = self._predict_proba_raw(xi)
                    err = pi - yi
                    # cross-entropy loss
                    eps = 1e-15
                    batch_loss -= yi * math.log(pi + eps) + (1 - yi) * math.log(1 - pi + eps)
                    for j in range(d):
                        grad_w[j] += err * xi[j]
                    grad_b += err

                bsz = len(batch)
                for j in range(d):
                    self.weights[j] -= self.lr * (grad_w[j] / bsz + self.l2 * self.weights[j])
                self.bias -= self.lr * (grad_b / bsz)
                epoch_loss += batch_loss / bsz
                batches += 1

            self.train_losses.append(epoch_loss / batches)

        return self

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        return [self._predict_proba_raw(x) for x in X]

    def predict(self, X: List[List[float]], threshold: float = 0.5) -> List[int]:
        return [1 if p >= threshold else 0 for p in self.predict_proba(X)]

    def to_dict(self) -> Dict:
        return {
            "type": "logistic_regression",
            "weights": self.weights,
            "bias": self.bias,
            "feature_names": FEATURE_NAMES,
            "window": WINDOW,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "LogisticRegression":
        obj = cls()
        obj.weights = d["weights"]
        obj.bias = d["bias"]
        return obj


# ---------------------------------------------------------------------------
# Threshold-based heuristic classifier
# ---------------------------------------------------------------------------

class ThresholdHeuristic:
    """
    Rule-based classifier using domain thresholds on individual features.

    Votes 'success' when:
      - cube_z_mean_delta  > min_lift_delta  (cube is actually moving up)
      - gripper_closure_rate > min_gripper   (gripper closing)
      - approach_velocity  > min_approach    (arm is moving)
    """

    def __init__(self, min_lift_delta: float = 0.005,
                 min_gripper: float = 0.4,
                 min_approach: float = 0.03):
        self.min_lift_delta = min_lift_delta
        self.min_gripper = min_gripper
        self.min_approach = min_approach

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        """Return soft probability approximation (0 or 1 votes averaged)."""
        probs = []
        for x in X:
            # x indices: [mean_delta, std_delta, gripper_rate, approach_vel, action_var]
            votes = 0
            if x[0] > self.min_lift_delta:
                votes += 1
            if x[2] > self.min_gripper:
                votes += 1
            if x[3] > self.min_approach:
                votes += 1
            probs.append(votes / 3.0)
        return probs

    def predict(self, X: List[List[float]], threshold: float = 0.5) -> List[int]:
        return [1 if p >= threshold else 0 for p in self.predict_proba(X)]


# ---------------------------------------------------------------------------
# Ensemble (majority vote)
# ---------------------------------------------------------------------------

class EnsemblePredictor:
    """Soft-vote ensemble combining LR and heuristic."""

    def __init__(self, lr: LogisticRegression, heuristic: ThresholdHeuristic,
                 lr_weight: float = 0.7):
        self.lr = lr
        self.heuristic = heuristic
        self.lr_weight = lr_weight

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        lp = self.lr.predict_proba(X)
        hp = self.heuristic.predict_proba(X)
        w2 = 1.0 - self.lr_weight
        return [self.lr_weight * lp[i] + w2 * hp[i] for i in range(len(X))]

    def predict(self, X: List[List[float]], threshold: float = 0.5) -> List[int]:
        return [1 if p >= threshold else 0 for p in self.predict_proba(X)]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def accuracy(y_true: List[int], y_pred: List[int]) -> float:
    return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)


def confusion_matrix(y_true: List[int], y_pred: List[int]) -> Dict:
    tp = sum(t == 1 and p == 1 for t, p in zip(y_true, y_pred))
    tn = sum(t == 0 and p == 0 for t, p in zip(y_true, y_pred))
    fp = sum(t == 0 and p == 1 for t, p in zip(y_true, y_pred))
    fn = sum(t == 1 and p == 0 for t, p in zip(y_true, y_pred))
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def precision_recall_f1(cm: Dict) -> Tuple[float, float, float]:
    prec = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) > 0 else 0.0
    rec = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def roc_curve(y_true: List[int], y_score: List[float],
              n_thresholds: int = 50) -> Tuple[List[float], List[float], List[float]]:
    thresholds = [i / n_thresholds for i in range(n_thresholds + 1)]
    fprs, tprs = [], []
    pos = sum(y_true)
    neg = len(y_true) - pos
    for thr in thresholds:
        tp = sum(s >= thr and t == 1 for t, s in zip(y_true, y_score))
        fp = sum(s >= thr and t == 0 for t, s in zip(y_true, y_score))
        tprs.append(tp / pos if pos > 0 else 0.0)
        fprs.append(fp / neg if neg > 0 else 0.0)
    return fprs, tprs, thresholds


def auc(fprs: List[float], tprs: List[float]) -> float:
    """Trapezoidal AUC."""
    area = 0.0
    for i in range(1, len(fprs)):
        area += abs(fprs[i] - fprs[i - 1]) * (tprs[i] + tprs[i - 1]) / 2.0
    return area


def pr_curve(y_true: List[int], y_score: List[float],
             n_thresholds: int = 50) -> Tuple[List[float], List[float]]:
    thresholds = [i / n_thresholds for i in range(n_thresholds + 1)]
    precisions, recalls = [], []
    for thr in thresholds:
        tp = sum(s >= thr and t == 1 for t, s in zip(y_true, y_score))
        fp = sum(s >= thr and t == 0 for t, s in zip(y_true, y_score))
        fn = sum(s < thr and t == 1 for t, s in zip(y_true, y_score))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precisions.append(prec)
        recalls.append(rec)
    return precisions, recalls


def expected_calibration_error(y_true: List[int], y_score: List[float],
                                n_bins: int = 10) -> float:
    """ECE: mean |acc - conf| weighted by bin fraction."""
    bins = [[] for _ in range(n_bins)]
    for t, s in zip(y_true, y_score):
        b = min(int(s * n_bins), n_bins - 1)
        bins[b].append((t, s))
    n = len(y_true)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        conf = sum(s for _, s in b) / len(b)
        acc = sum(t for t, _ in b) / len(b)
        ece += (len(b) / n) * abs(acc - conf)
    return ece


def calibration_data(y_true: List[int], y_score: List[float],
                     n_bins: int = 10) -> Tuple[List[float], List[float]]:
    """Returns (mean_confidence, fraction_positive) per bin."""
    bins = [[] for _ in range(n_bins)]
    for t, s in zip(y_true, y_score):
        b = min(int(s * n_bins), n_bins - 1)
        bins[b].append((t, s))
    confs, fracs = [], []
    for b_idx, b in enumerate(bins):
        if b:
            confs.append(sum(s for _, s in b) / len(b))
            fracs.append(sum(t for t, _ in b) / len(b))
        else:
            confs.append((b_idx + 0.5) / n_bins)
            fracs.append(float("nan"))
    return confs, fracs


# ---------------------------------------------------------------------------
# Early-stop simulation
# ---------------------------------------------------------------------------

def simulate_early_stop(episodes: List[Dict], predictor: EnsemblePredictor,
                        means: List[float], stds: List[float],
                        fail_threshold: float = FAIL_THRESHOLD) -> Dict:
    """
    Walk through episodes and simulate the early-stop policy.
    Returns statistics: how many episodes aborted, true/false abort rates,
    and estimated compute saved.
    """
    total = len(episodes)
    aborted = 0
    correct_aborts = 0   # predicted fail, actually failed
    false_aborts = 0     # predicted fail, actually succeeded

    for ep in episodes:
        feats = extract_features(ep)
        feats_s = scale([feats], means, stds)
        p_success = predictor.predict_proba(feats_s)[0]
        p_fail = 1.0 - p_success
        if p_fail > fail_threshold:
            aborted += 1
            if ep["success"] == 0:
                correct_aborts += 1
            else:
                false_aborts += 1

    full_steps = 50
    saved_steps = aborted * (full_steps - WINDOW)
    total_steps = total * full_steps
    frac_saved = saved_steps / total_steps if total_steps > 0 else 0.0

    return {
        "total": total,
        "aborted": aborted,
        "correct_aborts": correct_aborts,
        "false_aborts": false_aborts,
        "abort_rate": aborted / total if total > 0 else 0,
        "frac_compute_saved": frac_saved,
        "false_abort_rate": false_aborts / total if total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------

def _svg_line_chart(
    series: List[Tuple[str, List[float], List[float], str]],
    title: str,
    xlabel: str,
    ylabel: str,
    w: int = 380, h: int = 260,
    diagonal: bool = False,
) -> str:
    pad_l, pad_r, pad_t, pad_b = 50, 20, 30, 40
    cw = w - pad_l - pad_r
    ch = h - pad_t - pad_b

    def tx(v: float) -> float:
        return pad_l + v * cw

    def ty(v: float) -> float:
        return pad_t + (1 - v) * ch

    lines_svg = ""
    if diagonal:
        lines_svg += (
            f'<line x1="{tx(0)}" y1="{ty(0)}" x2="{tx(1)}" y2="{ty(1)}" '
            f'stroke="#555" stroke-dasharray="4,4" stroke-width="1"/>'
        )

    legend_items = ""
    for idx, (label, xs, ys, color) in enumerate(series):
        pts = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in zip(xs, ys))
        lines_svg += (
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linejoin="round"/>'
        )
        lx = pad_l + idx * 130
        legend_items += (
            f'<rect x="{lx}" y="{h - 14}" width="12" height="6" fill="{color}"/>'
            f'<text x="{lx + 16}" y="{h - 8}" fill="#ccc" font-size="10">{label}</text>'
        )

    # axes
    ticks_x = [i / 5 for i in range(6)]
    ticks_y = [i / 5 for i in range(6)]
    axis_svg = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + ch}" '
        f'stroke="#666" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + ch}" x2="{pad_l + cw}" y2="{pad_t + ch}" '
        f'stroke="#666" stroke-width="1"/>'
    )
    tick_svg = ""
    for v in ticks_x:
        tick_svg += (
            f'<line x1="{tx(v)}" y1="{pad_t + ch}" x2="{tx(v)}" y2="{pad_t + ch + 4}" '
            f'stroke="#666"/>'
            f'<text x="{tx(v)}" y="{pad_t + ch + 14}" text-anchor="middle" '
            f'fill="#999" font-size="9">{v:.1f}</text>'
        )
    for v in ticks_y:
        tick_svg += (
            f'<line x1="{pad_l - 4}" y1="{ty(v)}" x2="{pad_l}" y2="{ty(v)}" '
            f'stroke="#666"/>'
            f'<text x="{pad_l - 6}" y="{ty(v) + 3}" text-anchor="end" '
            f'fill="#999" font-size="9">{v:.1f}</text>'
        )

    title_svg = (
        f'<text x="{w // 2}" y="16" text-anchor="middle" fill="#e0e0e0" '
        f'font-size="13" font-weight="bold">{title}</text>'
    )
    xlabel_svg = (
        f'<text x="{pad_l + cw // 2}" y="{h - 2}" text-anchor="middle" '
        f'fill="#aaa" font-size="10">{xlabel}</text>'
    )
    ylabel_svg = (
        f'<text x="10" y="{pad_t + ch // 2}" text-anchor="middle" '
        f'fill="#aaa" font-size="10" transform="rotate(-90,10,{pad_t + ch // 2})">{ylabel}</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#1e1e2e;border-radius:8px;">'
        f'{title_svg}{axis_svg}{tick_svg}{lines_svg}{legend_items}{xlabel_svg}{ylabel_svg}'
        f'</svg>'
    )


def _svg_bar_confusion(cm: Dict, w: int = 260, h: int = 200) -> str:
    """Render a 2x2 confusion matrix as SVG."""
    cells = [
        ("TN", cm["tn"], "#4ade80"),
        ("FP", cm["fp"], "#f87171"),
        ("FN", cm["fn"], "#fb923c"),
        ("TP", cm["tp"], "#60a5fa"),
    ]
    total = max(sum(cm.values()), 1)
    cell_w, cell_h = w // 2, h // 2
    rects = ""
    for idx, (label, val, color) in enumerate(cells):
        cx = (idx % 2) * cell_w
        cy = (idx // 2) * cell_h
        intensity = 0.3 + 0.7 * (val / total)
        # darken color proportionally (just alpha via opacity)
        rects += (
            f'<rect x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h}" '
            f'fill="{color}" opacity="{intensity:.2f}"/>'
            f'<text x="{cx + cell_w // 2}" y="{cy + cell_h // 2 - 8}" '
            f'text-anchor="middle" fill="#fff" font-size="22" font-weight="bold">{val}</text>'
            f'<text x="{cx + cell_w // 2}" y="{cy + cell_h // 2 + 12}" '
            f'text-anchor="middle" fill="#ddd" font-size="11">{label}</text>'
        )
    header = (
        f'<text x="{w // 2}" y="-6" text-anchor="middle" fill="#e0e0e0" '
        f'font-size="12" font-weight="bold">Confusion Matrix (Ensemble)</text>'
    )
    axis_labels = (
        f'<text x="{cell_w // 2}" y="{h + 16}" text-anchor="middle" fill="#aaa" font-size="10">Pred: Fail</text>'
        f'<text x="{cell_w + cell_w // 2}" y="{h + 16}" text-anchor="middle" fill="#aaa" font-size="10">Pred: Success</text>'
        f'<text x="-8" y="{cell_h // 2}" text-anchor="middle" fill="#aaa" font-size="10" '
        f'transform="rotate(-90,-8,{cell_h // 2})">True: Fail</text>'
        f'<text x="-8" y="{cell_h + cell_h // 2}" text-anchor="middle" fill="#aaa" font-size="10" '
        f'transform="rotate(-90,-8,{cell_h + cell_h // 2})">True: Success</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + 24}" '
        f'style="background:#1e1e2e;border-radius:8px;">'
        f'<g transform="translate(0,12)">'
        f'{header}{rects}{axis_labels}'
        f'</g></svg>'
    )


def _svg_threshold_analysis(
    y_true: List[int], y_score: List[float],
    w: int = 380, h: int = 260,
) -> str:
    thresholds = [i / 100 for i in range(1, 100)]
    accs, precs, recs = [], [], []
    for thr in thresholds:
        y_pred = [1 if s >= thr else 0 for s in y_score]
        cm = confusion_matrix(y_true, y_pred)
        accs.append(accuracy(y_true, y_pred))
        p, r, _ = precision_recall_f1(cm)
        precs.append(p)
        recs.append(r)

    series = [
        ("Accuracy", thresholds, accs, "#60a5fa"),
        ("Precision", thresholds, precs, "#f472b6"),
        ("Recall", thresholds, recs, "#34d399"),
    ]
    return _svg_line_chart(series, "Threshold Analysis", "Threshold", "Score")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_report(
    lr_model: LogisticRegression,
    ensemble: EnsemblePredictor,
    X_val_s: List[List[float]],
    y_val: List[int],
    means: List[float],
    stds: List[float],
    early_stop_stats: Dict,
    train_time_s: float,
) -> str:

    # Scores
    lr_scores = lr_model.predict_proba(X_val_s)
    ens_scores = ensemble.predict_proba(X_val_s)

    lr_preds = lr_model.predict(X_val_s)
    ens_preds = ensemble.predict(X_val_s)

    lr_acc = accuracy(y_val, lr_preds)
    ens_acc = accuracy(y_val, ens_preds)

    lr_cm = confusion_matrix(y_val, lr_preds)
    ens_cm = confusion_matrix(y_val, ens_preds)

    lr_p, lr_r, lr_f1 = precision_recall_f1(lr_cm)
    ens_p, ens_r, ens_f1 = precision_recall_f1(ens_cm)

    ece_lr = expected_calibration_error(y_val, lr_scores)
    ece_ens = expected_calibration_error(y_val, ens_scores)

    # ROC
    lr_fprs, lr_tprs, _ = roc_curve(y_val, lr_scores)
    ens_fprs, ens_tprs, _ = roc_curve(y_val, ens_scores)
    lr_auc = auc(lr_fprs, lr_tprs)
    ens_auc = auc(ens_fprs, ens_tprs)

    roc_svg = _svg_line_chart(
        [
            (f"LR (AUC={lr_auc:.3f})", lr_fprs, lr_tprs, "#60a5fa"),
            (f"Ensemble (AUC={ens_auc:.3f})", ens_fprs, ens_tprs, "#f472b6"),
        ],
        "ROC Curve", "FPR", "TPR", diagonal=True
    )

    # PR
    lr_precs, lr_recs = pr_curve(y_val, lr_scores)
    ens_precs, ens_recs = pr_curve(y_val, ens_scores)
    pr_svg = _svg_line_chart(
        [
            ("LR", lr_recs, lr_precs, "#60a5fa"),
            ("Ensemble", ens_recs, ens_precs, "#f472b6"),
        ],
        "Precision-Recall Curve", "Recall", "Precision"
    )

    # Confusion matrix
    cm_svg = _svg_bar_confusion(ens_cm)

    # Calibration
    cal_confs, cal_fracs = calibration_data(y_val, ens_scores)
    cal_fracs_clean = [f if not math.isnan(f) else 0.0 for f in cal_fracs]
    cal_svg = _svg_line_chart(
        [
            ("Perfect", [0, 1], [0, 1], "#555"),
            ("Ensemble", cal_confs, cal_fracs_clean, "#f472b6"),
            ("LR", *zip(*[(c, f) for c, f in zip(*calibration_data(y_val, lr_scores))
                          if not math.isnan(f)]), "#60a5fa")
            if any(not math.isnan(f) for f in calibration_data(y_val, lr_scores)[1])
            else ("LR", [0], [0], "#60a5fa"),
        ],
        "Calibration Plot", "Mean Confidence", "Fraction Positive", diagonal=True
    )

    # Threshold analysis
    thr_svg = _svg_threshold_analysis(y_val, ens_scores)

    # Training loss curve
    loss_svg = _svg_line_chart(
        [("Train Loss", list(range(len(lr_model.train_losses))),
          [l / max(lr_model.train_losses) for l in lr_model.train_losses], "#34d399")],
        "LR Training Loss", "Epoch", "Normalised Loss"
    )

    es = early_stop_stats
    compute_saved_pct = es["frac_compute_saved"] * 100

    def metric_card(label: str, value: str, sub: str = "") -> str:
        return (
            f'<div style="background:#2a2a3e;border-radius:8px;padding:16px 20px;'
            f'min-width:120px;text-align:center;">'
            f'<div style="font-size:22px;font-weight:700;color:#60a5fa;">{value}</div>'
            f'<div style="font-size:11px;color:#aaa;margin-top:4px;">{label}</div>'
            f'{"<div style=font-size:10px;color:#666;>" + sub + "</div>" if sub else ""}'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Episode Success Predictor Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #12121c; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif;
         font-size: 14px; line-height: 1.6; padding: 24px; }}
  h1 {{ font-size: 24px; color: #e0e0e0; margin-bottom: 4px; }}
  h2 {{ font-size: 16px; color: #a0a0c0; margin: 24px 0 12px; border-bottom: 1px solid #2a2a3e; padding-bottom: 6px; }}
  .subtitle {{ color: #777; font-size: 12px; margin-bottom: 28px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
  .charts {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
  th {{ background: #1e1e2e; color: #9090c0; font-size: 11px; text-transform: uppercase;
        padding: 8px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e1e2e; font-size: 13px; }}
  tr:hover td {{ background: #1a1a2a; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
  .badge-green {{ background: #14532d; color: #4ade80; }}
  .badge-blue  {{ background: #1e3a5f; color: #60a5fa; }}
  .badge-amber {{ background: #451a03; color: #fb923c; }}
  code {{ background: #1e1e2e; padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #93c5fd; }}
  .section {{ margin-bottom: 32px; }}
</style>
</head>
<body>
<h1>Episode Success Predictor</h1>
<p class="subtitle">Early-stop classifier trained on first {WINDOW} steps &mdash; generated {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

<h2>Summary</h2>
<div class="cards">
  {metric_card("Ensemble Accuracy", f"{ens_acc:.1%}", f"LR: {lr_acc:.1%}")}
  {metric_card("Ensemble AUC-ROC", f"{ens_auc:.3f}", f"LR: {lr_auc:.3f}")}
  {metric_card("F1 Score (Ensemble)", f"{ens_f1:.3f}", f"LR: {lr_f1:.3f}")}
  {metric_card("ECE (calibration)", f"{ece_ens:.4f}", f"LR: {ece_lr:.4f}")}
  {metric_card("Compute Saved", f"{compute_saved_pct:.1f}%", f"{es['aborted']}/{es['total']} aborted")}
  {metric_card("False Abort Rate", f"{es['false_abort_rate']:.1%}", "aborted but succeeded")}
  {metric_card("Train Time", f"{train_time_s:.1f}s", "SGD logistic regression")}
</div>

<h2>Classifier Metrics</h2>
<table>
  <tr><th>Model</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>AUC-ROC</th><th>ECE</th></tr>
  <tr>
    <td><span class="badge badge-blue">Logistic Regression</span></td>
    <td>{lr_acc:.4f}</td><td>{lr_p:.4f}</td><td>{lr_r:.4f}</td><td>{lr_f1:.4f}</td>
    <td>{lr_auc:.4f}</td><td>{ece_lr:.4f}</td>
  </tr>
  <tr>
    <td><span class="badge badge-green">Ensemble</span></td>
    <td>{ens_acc:.4f}</td><td>{ens_p:.4f}</td><td>{ens_r:.4f}</td><td>{ens_f1:.4f}</td>
    <td>{ens_auc:.4f}</td><td>{ece_ens:.4f}</td>
  </tr>
</table>

<h2>Early-Stop Simulation (threshold = {FAIL_THRESHOLD:.0%} failure confidence)</h2>
<div class="cards">
  {metric_card("Episodes", str(es['total']), "held-out test set")}
  {metric_card("Aborted", str(es['aborted']), f"at step {WINDOW}")}
  {metric_card("Correct Aborts", str(es['correct_aborts']), "true failures stopped")}
  {metric_card("False Aborts", str(es['false_aborts']), "successes stopped early")}
  {metric_card("Compute Saved", f"{compute_saved_pct:.1f}%", f"steps {WINDOW}→50 skipped")}
</div>

<h2>Charts</h2>
<div class="charts">
  {roc_svg}
  {pr_svg}
  {cm_svg}
  {cal_svg}
  {thr_svg}
  {loss_svg}
</div>

<h2>Feature Importance (LR Coefficients)</h2>
<table>
  <tr><th>Feature</th><th>Coefficient</th><th>Normaliser Mean</th><th>Normaliser Std</th><th>Interpretation</th></tr>
  {"".join(
      f'<tr><td><code>{FEATURE_NAMES[j]}</code></td>'
      f'<td style="color:{"#4ade80" if lr_model.weights[j]>0 else "#f87171"}">'
      f'{lr_model.weights[j]:+.4f}</td>'
      f'<td>{means[j]:.5f}</td><td>{stds[j]:.5f}</td>'
      f'<td style="color:#aaa;font-size:12px;">'
      f'{"drives success" if lr_model.weights[j]>0 else "drives failure"}'
      f'</td></tr>'
      for j in range(N_FEATURES)
  )}
</table>

<h2>Usage</h2>
<p style="color:#aaa;font-size:13px;line-height:2;">
  Load the saved model JSON and call <code>predict_online()</code> at step {WINDOW} of each episode.
  If the returned failure probability exceeds <code>{FAIL_THRESHOLD}</code>, abort the episode.
</p>
<pre style="background:#1e1e2e;padding:16px;border-radius:8px;overflow-x:auto;font-size:12px;color:#93c5fd;">
from src.eval.episode_success_predictor import (
    LogisticRegression, extract_features, scale, load_model
)

model_data = load_model('/tmp/episode_success_predictor.json')
lr         = model_data['lr']
means      = model_data['means']
stds       = model_data['stds']

# inside eval loop, after step {WINDOW}:
feats = extract_features(episode_buffer)
feats_s = scale([feats], means, stds)
p_fail = 1.0 - lr.predict_proba(feats_s)[0]
if p_fail > {FAIL_THRESHOLD}:
    print(f"Aborting episode (P(fail)={{p_fail:.2f}})")
    env.reset()
</pre>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Model persistence
# ---------------------------------------------------------------------------

def save_model(lr: LogisticRegression, means: List[float], stds: List[float],
               path: str) -> None:
    data = {
        "lr": lr.to_dict(),
        "means": means,
        "stds": stds,
        "window": WINDOW,
        "fail_threshold": FAIL_THRESHOLD,
        "feature_names": FEATURE_NAMES,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[predictor] Model saved to {path}")


def load_model(path: str) -> Dict:
    with open(path) as f:
        data = json.load(f)
    data["lr"] = LogisticRegression.from_dict(data["lr"])
    return data


# ---------------------------------------------------------------------------
# Main training / evaluation pipeline
# ---------------------------------------------------------------------------

def run(n_train: int = 500, n_test: int = 100,
        output: str = "/tmp/predictor_report.html",
        model_path: str = "/tmp/episode_success_predictor.json",
        load_path: str | None = None,
        seed: int = 42) -> None:

    print(f"[predictor] Generating mock episodes: {n_train} train, {n_test} test …")
    all_eps = generate_mock_episodes(n_train + n_test, seed=seed)
    train_eps = all_eps[:n_train]
    test_eps = all_eps[n_train:]

    print("[predictor] Extracting features …")
    X_train, y_train = build_dataset(train_eps)
    X_test, y_test = build_dataset(test_eps)

    if load_path and os.path.exists(load_path):
        print(f"[predictor] Loading model from {load_path} …")
        model_data = load_model(load_path)
        lr = model_data["lr"]
        means = model_data["means"]
        stds = model_data["stds"]
        train_time = 0.0
    else:
        print("[predictor] Normalising features …")
        means, stds = compute_scaler(X_train)

        X_train_s = scale(X_train, means, stds)
        X_val_s = scale(X_test, means, stds)

        # 80/20 internal split for validation during training report
        split = int(0.8 * len(X_train_s))
        X_tr, y_tr = X_train_s[:split], y_train[:split]

        print("[predictor] Training logistic regression …")
        t0 = time.time()
        lr = LogisticRegression(lr=0.05, epochs=300, batch_size=32, l2=1e-4, seed=seed)
        lr.fit(X_tr, y_tr)
        train_time = time.time() - t0
        print(f"[predictor] Training done in {train_time:.2f}s | final loss: {lr.train_losses[-1]:.4f}")

        save_model(lr, means, stds, model_path)

    # Scale test set
    X_test_s = scale(X_test, means, stds)

    heuristic = ThresholdHeuristic()
    ensemble = EnsemblePredictor(lr, heuristic, lr_weight=0.75)

    # --- Metrics on test set ---
    ens_preds = ensemble.predict(X_test_s)
    ens_acc = accuracy(y_test, ens_preds)
    ens_cm = confusion_matrix(y_test, ens_preds)
    _, _, ens_f1 = precision_recall_f1(ens_cm)
    print(f"[predictor] Test accuracy (ensemble): {ens_acc:.3f} | F1: {ens_f1:.3f}")

    lr_preds = lr.predict(X_test_s)
    lr_acc = accuracy(y_test, lr_preds)
    print(f"[predictor] Test accuracy (LR):       {lr_acc:.3f}")

    # --- Early-stop simulation on test episodes ---
    es_stats = simulate_early_stop(test_eps, ensemble, means, stds)
    print(
        f"[predictor] Early-stop: {es_stats['aborted']}/{es_stats['total']} aborted "
        f"({es_stats['frac_compute_saved']*100:.1f}% compute saved, "
        f"{es_stats['false_abort_rate']*100:.1f}% false abort rate)"
    )

    # --- HTML report ---
    print(f"[predictor] Building HTML report → {output} …")
    html = build_report(lr, ensemble, X_test_s, y_test, means, stds,
                        es_stats, train_time if "train_time" in dir() else 0.0)
    with open(output, "w") as f:
        f.write(html)
    print(f"[predictor] Report written: {output}")

    # --- Final summary ---
    print("\n=== Results Summary ===")
    print(f"  Ensemble accuracy : {ens_acc:.1%}")
    print(f"  Ensemble AUC-ROC  : (see report)")
    print(f"  Compute saved     : {es_stats['frac_compute_saved']*100:.1f}%")
    print(f"  False abort rate  : {es_stats['false_abort_rate']*100:.1f}%")
    print(f"  Model JSON        : {model_path}")
    print(f"  HTML report       : {output}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate episode success predictor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use mock generated data (default: True)")
    parser.add_argument("--n-train", type=int, default=500,
                        help="Number of training episodes (default: 500)")
    parser.add_argument("--n-test", type=int, default=100,
                        help="Number of test episodes (default: 100)")
    parser.add_argument("--output", type=str, default="/tmp/predictor_report.html",
                        help="Output HTML report path")
    parser.add_argument("--model-path", type=str, default="/tmp/episode_success_predictor.json",
                        help="Where to save trained model JSON")
    parser.add_argument("--load", type=str, default=None,
                        help="Load existing model JSON instead of training")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    run(
        n_train=args.n_train,
        n_test=args.n_test,
        output=args.output,
        model_path=args.model_path,
        load_path=args.load,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
