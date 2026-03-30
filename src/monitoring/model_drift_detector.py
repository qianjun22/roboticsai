"""model_drift_detector.py — Production model drift detection service for GR00T N1.6.
OCI Robot Cloud | OCI A100 GPU4 138.1.153.110 | Port 8087 | Oracle Confidential
"""
from __future__ import annotations
import json, math, random, time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import numpy as np

PORT = 8087
WINDOW_SIZE = 50
DRIFT_HISTORY_MAX = 500
ALERT_THRESHOLDS = {"NOMINAL": 0.05, "WATCH": 0.15, "ALERT": 0.30, "CRITICAL": 0.50}

@dataclass
class DriftSnapshot:
    timestamp: str; day: float; kl_divergence: float; psi_score: float
    wasserstein_distance: float; action_mean_drift: float; action_std_drift: float
    latency_drift: float; composite_score: float; alert_level: str; window_samples: int

@dataclass
class DriftState:
    snapshots: List[DriftSnapshot] = field(default_factory=list)
    alert_count: Dict[str, int] = field(default_factory=lambda: {"NOMINAL": 0, "WATCH": 0, "ALERT": 0, "CRITICAL": 0})
    retraining_triggered: int = 0
    last_reset: str = field(default_factory=lambda: datetime.utcnow().isoformat())

def kl_divergence(p: np.ndarray, q: np.ndarray, eps: float = 1e-10) -> float:
    p = p + eps; q = q + eps; p = p / p.sum(); q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))

def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10, eps: float = 1e-10) -> float:
    all_vals = np.concatenate([expected, actual])
    bin_edges = np.linspace(all_vals.min() - eps, all_vals.max() + eps, bins + 1)
    exp_hist, _ = np.histogram(expected, bins=bin_edges); act_hist, _ = np.histogram(actual, bins=bin_edges)
    exp_pct = (exp_hist + eps) / (len(expected) + eps * bins); act_pct = (act_hist + eps) / (len(actual) + eps * bins)
    return max(0.0, float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))))

def wasserstein_1d(u: np.ndarray, v: np.ndarray) -> float:
    n = max(len(u), len(v))
    u_i = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(u)), np.sort(u))
    v_i = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(v)), np.sort(v))
    return float(np.mean(np.abs(u_i - v_i)))

def composite_drift_score(kl: float, psi: float, wass: float) -> float:
    return 0.4 * min(kl / 2.0, 1.0) + 0.35 * min(psi, 1.0) + 0.25 * min(wass / 0.5, 1.0)

def alert_level(score: float) -> str:
    if score >= ALERT_THRESHOLDS["CRITICAL"]: return "CRITICAL"
    if score >= ALERT_THRESHOLDS["ALERT"]: return "ALERT"
    if score >= ALERT_THRESHOLDS["WATCH"]: return "WATCH"
    return "NOMINAL"

def generate_reference_distribution(n: int = 500, seed: int = 42) -> np.ndarray:
    return np.random.default_rng(seed).normal(loc=0.0, scale=0.18, size=n)

def sample_window(day: float, ref: np.ndarray, window: int = WINDOW_SIZE, seed=None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base_mean = float(np.mean(ref)); base_std = float(np.std(ref))
    if day < 12: loc = base_mean + rng.normal(0, 0.005); scale = base_std + rng.normal(0, 0.003)
    elif day < 17:
        d = (day - 12) / 5.0; loc = base_mean + 0.12 * d + rng.normal(0, 0.01); scale = base_std + 0.06 * d + rng.normal(0, 0.005)
    elif day < 23:
        r = (day - 17) / 6.0; loc = base_mean + 0.12 * (1 - r * 0.6) + rng.normal(0, 0.008); scale = base_std + 0.06 * (1 - r * 0.5) + rng.normal(0, 0.004)
    else:
        d = min((day - 23) / 4.0, 1.0); loc = base_mean + 0.35 * d + rng.normal(0, 0.015); scale = base_std + 0.15 * d + rng.normal(0, 0.008)
    return rng.normal(loc=loc, scale=max(scale, 0.02), size=window)

def simulate_30day_trace() -> DriftState:
    ref = generate_reference_distribution(); state = DriftState()
    base_ts = datetime(2026, 3, 1); rng = random.Random(99)
    for i in range(120):
        day = i / 4.0; ts = base_ts + timedelta(hours=i * 6); seed = rng.randint(0, 99999)
        w = sample_window(day, ref, seed=seed)
        kl = kl_divergence(np.histogram(ref, bins=20, density=True)[0], np.histogram(w, bins=20, density=True)[0])
        psi = population_stability_index(ref, w); wass = wasserstein_1d(ref, w)
        action_mean_drift = abs(float(np.mean(w)) - float(np.mean(ref)))
        action_std_drift = abs(float(np.std(w)) - float(np.std(ref)))
        latency_current = 227.0 + 5 * day / 30 + rng.gauss(0, 4)
        latency_drift = abs(latency_current - 227.0) / 227.0
        score = composite_drift_score(kl, psi, wass); level = alert_level(score)
        snap = DriftSnapshot(timestamp=ts.isoformat() + "Z", day=round(day, 3),
            kl_divergence=round(kl, 6), psi_score=round(psi, 6), wasserstein_distance=round(wass, 6),
            action_mean_drift=round(action_mean_drift, 6), action_std_drift=round(action_std_drift, 6),
            latency_drift=round(latency_drift, 6), composite_score=round(score, 6),
            alert_level=level, window_samples=WINDOW_SIZE)
        state.snapshots.append(snap); state.alert_count[level] += 1
        if level in ("ALERT", "CRITICAL") and state.retraining_triggered < 2:
            prev = state.snapshots[-2].alert_level if len(state.snapshots) > 1 else "NOMINAL"
            if prev not in ("ALERT", "CRITICAL"): state.retraining_triggered += 1
    return state

def generate_html_report(state: DriftState) -> str:
    snaps = state.snapshots; latest = snaps[-1] if snaps else None
    level_colors = {"NOMINAL": "#22c55e", "WATCH": "#facc15", "ALERT": "#fb923c", "CRITICAL": "#ef4444"}
    cur_level = latest.alert_level if latest else "N/A"; cur_score = latest.composite_score if latest else 0.0
    alert_rows = "".join(f'<tr><td style="color:#94a3b8">{lv}</td><td style="color:{level_colors[lv]};text-align:right">{cnt}</td></tr>' for lv, cnt in state.alert_count.items())
    rows = "".join(f'<tr><td style="color:#94a3b8">{s.timestamp[:16]}</td><td>Day {s.day:.2f}</td><td>{s.composite_score:.4f}</td><td>{s.kl_divergence:.4f}</td><td>{s.psi_score:.4f}</td><td>{s.wasserstein_distance:.4f}</td><td style="color:{level_colors.get(s.alert_level,"#94a3b8")};font-weight:700">{s.alert_level}</td></tr>' for s in snaps[-10:][::-1])
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/><title>OCI Robot Cloud - Model Drift Detector</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;padding:24px}}h1{{color:#C74634}}h2{{color:#C74634;font-size:1rem;text-transform:uppercase;margin:24px 0 8px}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}.card{{background:#1e293b;border-radius:8px;padding:16px 20px;min-width:150px}}.card .val{{font-size:1.6rem;font-weight:700;margin:4px 0}}.card .lbl{{color:#64748b;font-size:.8rem}}table{{border-collapse:collapse;width:100%;font-size:.85rem}}th{{color:#64748b;text-align:left;padding:6px 10px;border-bottom:1px solid #1e293b}}td{{padding:6px 10px;border-bottom:1px solid #1e293b}}</style></head><body>
<h1>OCI Robot Cloud — Model Drift Detector</h1><p style="color:#64748b">GR00T N1.6 | OCI A100 GPU4 138.1.153.110 | Port {PORT}</p>
<div class="cards"><div class="card"><div class="lbl">Current Alert</div><div class="val" style="color:{level_colors.get(cur_level,'#94a3b8')}">{cur_level}</div></div><div class="card"><div class="lbl">Composite Score</div><div class="val">{cur_score:.4f}</div></div><div class="card"><div class="lbl">Retraining Alerts</div><div class="val" style="color:#C74634">{state.retraining_triggered}</div></div><div class="card"><div class="lbl">Total Snapshots</div><div class="val">{len(snaps)}</div></div></div>
<h2>Alert Distribution</h2><table style="width:auto"><tr><th>Level</th><th>Count</th></tr>{alert_rows}</table>
<h2>Drift Events</h2><table><tr><th>Day</th><th>Event</th><th>Impact</th></tr><tr><td>12</td><td>Robot arm firmware update</td><td>Moderate drift</td></tr><tr><td>23</td><td>Outdoor deployment</td><td>Severe drift</td></tr></table>
<h2>Recent Snapshots</h2><table><tr><th>Timestamp</th><th>Day</th><th>Score</th><th>KL</th><th>PSI</th><th>Wasserstein</th><th>Alert</th></tr>{rows}</table>
<div style="margin-top:40px;color:#475569;font-size:.75rem">Oracle Confidential | OCI Robot Cloud 2026</div>
</body></html>"""

def build_app(state: DriftState):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError: return None
    app = FastAPI(title="OCI Robot Cloud — Model Drift Detector", version="1.0.0")
    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return generate_html_report(state)
    @app.get("/drift/current")
    def drift_current(): return asdict(state.snapshots[-1]) if state.snapshots else {"error": "no data"}
    @app.post("/drift/reset")
    def drift_reset(): state.snapshots.clear(); state.alert_count = {k: 0 for k in state.alert_count}; state.retraining_triggered = 0; return {"status": "reset"}
    @app.get("/drift/history")
    def drift_history(limit: int = 100): return {"count": min(limit, len(state.snapshots)), "snapshots": [asdict(s) for s in state.snapshots[-limit:]]}
    return app

def main():
    print("=" * 70); print("OCI Robot Cloud — Model Drift Detector"); print("=" * 70)
    print("Simulating 30-day production trace ...")
    state = simulate_30day_trace(); snaps = state.snapshots; latest = snaps[-1]
    scores = [s.composite_score for s in snaps]; peak = max(snaps, key=lambda s: s.composite_score)
    print(f"Snapshots: {len(snaps)} | Current alert: {latest.alert_level} | Score: {latest.composite_score:.4f}")
    print(f"Peak: {peak.composite_score:.4f} (day {peak.day:.1f}) | Retraining alerts: {state.retraining_triggered}")
    print(f"NOMINAL={state.alert_count['NOMINAL']} WATCH={state.alert_count['WATCH']} ALERT={state.alert_count['ALERT']} CRITICAL={state.alert_count['CRITICAL']}")
    html_path = "/tmp/model_drift_detector_report.html"
    with open(html_path, "w", encoding="utf-8") as fh: fh.write(generate_html_report(state))
    print(f"HTML report: {html_path}")
    app = build_app(state)
    if app:
        import uvicorn; print(f"Starting server on port {PORT} ..."); uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: print(f"(FastAPI not installed)")

if __name__ == "__main__":
    main()
