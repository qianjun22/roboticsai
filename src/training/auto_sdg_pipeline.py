#!/usr/bin/env python3
"""
auto_sdg_pipeline.py — Automatic SDG (Synthetic Data Generation) pipeline for OCI Robot Cloud.

Monitors the training data queue size and automatically triggers Genesis SDG to
generate more episodes when the queue drops below a configurable threshold.
Implements a data flywheel: monitor queue → detect low supply → dispatch SDG job →
accumulate episodes → training pipeline picks up new data.

Usage:
    python src/training/auto_sdg_pipeline.py --port 8037 [--mock]

Endpoints (port 8037):
    GET  /health
    GET  /                    — HTML dashboard (queue gauge, stats, job table)
    GET  /api/state           — JSON AutoSDGState
    POST /api/jobs            — manually dispatch an SDG job
    PATCH /api/schedule       — update schedule config (enable/disable, threshold, etc.)

Auto-refill logic:
    Every poll_interval_s (default 300s), if current_queue_size < min_queue_threshold,
    dispatch a new SDG job for (target_queue_size - current_queue_size) episodes,
    sampling difficulty from difficulty_distribution. Max max_concurrent_jobs active
    at any time. Simulated job completes in ~15s, generating 50*n_episodes frames.
"""

import argparse
import random
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

HAS_FASTAPI = False
try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    pass


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class SDGJob:
    job_id: str
    n_episodes: int
    difficulty_level: int          # 1–4
    seed: int
    status: str                    # queued / running / done / failed
    n_frames_generated: int = 0
    elapsed_s: float = 0.0
    output_path: str = ""
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SDGSchedule:
    enabled: bool = True
    min_queue_threshold: int = 100
    target_queue_size: int = 500
    max_concurrent_jobs: int = 2
    poll_interval_s: int = 300
    difficulty_distribution: Dict[int, float] = field(
        default_factory=lambda: {1: 0.3, 2: 0.3, 3: 0.25, 4: 0.15}
    )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "min_queue_threshold": self.min_queue_threshold,
            "target_queue_size": self.target_queue_size,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "poll_interval_s": self.poll_interval_s,
            "difficulty_distribution": {str(k): v for k, v in self.difficulty_distribution.items()},
        }


@dataclass
class AutoSDGState:
    current_queue_size: int = 250
    target_queue_size: int = 500
    jobs_today: int = 0
    episodes_today: int = 0
    schedule: SDGSchedule = field(default_factory=SDGSchedule)
    active_jobs: List[SDGJob] = field(default_factory=list)
    completed_jobs: List[SDGJob] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_queue_size": self.current_queue_size,
            "target_queue_size": self.target_queue_size,
            "jobs_today": self.jobs_today,
            "episodes_today": self.episodes_today,
            "schedule": self.schedule.to_dict(),
            "active_jobs": [j.to_dict() for j in self.active_jobs],
            "completed_jobs": [j.to_dict() for j in self.completed_jobs[-20:]],
        }


# ── Background simulation ─────────────────────────────────────────────────────

_state_lock = threading.Lock()


def _sample_difficulty(dist: Dict[int, float], rng: random.Random) -> int:
    levels = sorted(dist.keys())
    weights = [dist[k] for k in levels]
    return rng.choices(levels, weights=weights, k=1)[0]


def _dispatch_job(state: AutoSDGState, n_episodes: int, difficulty: int, rng: random.Random) -> SDGJob:
    job = SDGJob(
        job_id=str(uuid.uuid4())[:8],
        n_episodes=n_episodes,
        difficulty_level=difficulty,
        seed=rng.randint(0, 999999),
        status="queued",
        created_at=datetime.utcnow().isoformat() + "Z",
        output_path=f"/tmp/sdg_out/job_{uuid.uuid4().hex[:6]}",
    )
    state.active_jobs.append(job)
    return job


def _run_single_job(job: SDGJob, state: AutoSDGState) -> None:
    """Simulate a Genesis SDG job: ~15s completion, 50*n_episodes frames."""
    with _state_lock:
        job.status = "running"

    start = time.time()
    try:
        # Simulate generation time proportional to episode count (capped for demo)
        sim_duration = min(15.0, 5.0 + job.n_episodes * 0.05)
        time.sleep(sim_duration)

        elapsed = time.time() - start
        frames = 50 * job.n_episodes

        with _state_lock:
            job.status = "done"
            job.n_frames_generated = frames
            job.elapsed_s = round(elapsed, 2)
            job.completed_at = datetime.utcnow().isoformat() + "Z"

            # Add generated episodes to queue
            state.current_queue_size += job.n_episodes
            state.jobs_today += 1
            state.episodes_today += job.n_episodes

            # Move to completed list
            state.active_jobs = [j for j in state.active_jobs if j.job_id != job.job_id]
            state.completed_jobs.append(job)

    except Exception as exc:  # noqa: BLE001
        with _state_lock:
            job.status = "failed"
            job.elapsed_s = round(time.time() - start, 2)
            job.completed_at = datetime.utcnow().isoformat() + "Z"
            state.active_jobs = [j for j in state.active_jobs if j.job_id != job.job_id]
            state.completed_jobs.append(job)


def simulate_sdg_loop(state: AutoSDGState, rng: random.Random) -> None:
    """
    Background loop: every 10s, check queue against threshold.
    Dispatches new Genesis SDG jobs when supply is low.
    Also simulates natural queue consumption (~2 eps/s).
    """
    last_check = 0.0

    while True:
        time.sleep(10)
        now = time.time()

        with _state_lock:
            # Simulate queue consumption by training pipeline
            consumption = rng.randint(1, 5)
            state.current_queue_size = max(0, state.current_queue_size - consumption)

            sched = state.schedule
            active_count = len(state.active_jobs)

            should_dispatch = (
                sched.enabled
                and state.current_queue_size < sched.min_queue_threshold
                and active_count < sched.max_concurrent_jobs
                and (now - last_check) >= sched.poll_interval_s / 30  # scale down for demo
            )

            if should_dispatch:
                n_needed = sched.target_queue_size - state.current_queue_size
                n_needed = max(10, n_needed)
                difficulty = _sample_difficulty(sched.difficulty_distribution, rng)
                job = _dispatch_job(state, n_needed, difficulty, rng)
                last_check = now
                # Launch job in its own thread
                t = threading.Thread(target=_run_single_job, args=(job, state), daemon=True)
                t.start()


# ── FastAPI app ───────────────────────────────────────────────────────────────

def build_app(state: AutoSDGState) -> "FastAPI":
    app = FastAPI(title="Auto SDG Pipeline", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Pydantic models ────────────────────────────────────────────────────────

    class DispatchRequest(BaseModel):
        n_episodes: int
        difficulty_level: int = 2

    class SchedulePatch(BaseModel):
        enabled: Optional[bool] = None
        min_queue_threshold: Optional[int] = None
        target_queue_size: Optional[int] = None
        max_concurrent_jobs: Optional[int] = None
        poll_interval_s: Optional[int] = None

    # ── Endpoints ─────────────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "auto_sdg_pipeline", "port": 8037}

    @app.get("/api/state")
    def get_state():
        with _state_lock:
            return JSONResponse(state.to_dict())

    @app.post("/api/jobs")
    def dispatch_job(req: DispatchRequest):
        if req.difficulty_level not in (1, 2, 3, 4):
            return JSONResponse({"error": "difficulty_level must be 1–4"}, status_code=400)
        if req.n_episodes < 1:
            return JSONResponse({"error": "n_episodes must be >= 1"}, status_code=400)

        rng = random.Random()
        with _state_lock:
            job = _dispatch_job(state, req.n_episodes, req.difficulty_level, rng)

        t = threading.Thread(target=_run_single_job, args=(job, state), daemon=True)
        t.start()
        return JSONResponse(job.to_dict(), status_code=201)

    @app.patch("/api/schedule")
    def update_schedule(patch: SchedulePatch):
        with _state_lock:
            sched = state.schedule
            if patch.enabled is not None:
                sched.enabled = patch.enabled
            if patch.min_queue_threshold is not None:
                sched.min_queue_threshold = patch.min_queue_threshold
            if patch.target_queue_size is not None:
                sched.target_queue_size = patch.target_queue_size
                state.target_queue_size = patch.target_queue_size
            if patch.max_concurrent_jobs is not None:
                sched.max_concurrent_jobs = patch.max_concurrent_jobs
            if patch.poll_interval_s is not None:
                sched.poll_interval_s = patch.poll_interval_s
            return JSONResponse(sched.to_dict())

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        with _state_lock:
            snap = state.to_dict()

        cur = snap["current_queue_size"]
        tgt = snap["target_queue_size"]
        pct = min(100, int(cur / max(tgt, 1) * 100))
        bar_color = "#22c55e" if pct >= 50 else ("#f59e0b" if pct >= 20 else "#ef4444")

        # Build difficulty distribution SVG pie chart
        dist = snap["schedule"]["difficulty_distribution"]
        diff_colors = {"1": "#6366f1", "2": "#22d3ee", "3": "#f59e0b", "4": "#ef4444"}
        pie_svg = _build_pie_svg(dist, diff_colors)

        # Active jobs rows
        active_rows = ""
        for j in snap["active_jobs"]:
            active_rows += (
                f"<tr><td>{j['job_id']}</td><td>{j['n_episodes']}</td>"
                f"<td>D{j['difficulty_level']}</td>"
                f"<td><span class='badge badge-running'>{j['status']}</span></td>"
                f"<td>{j['n_frames_generated']}</td><td>{j['elapsed_s']:.1f}s</td>"
                f"<td>{j['created_at'][:19]}</td></tr>"
            )
        if not active_rows:
            active_rows = "<tr><td colspan='7' style='color:#6b7280;text-align:center'>No active jobs</td></tr>"

        # Recent completed rows (last 10)
        recent_rows = ""
        for j in reversed(snap["completed_jobs"][-10:]):
            badge_cls = "badge-done" if j["status"] == "done" else "badge-failed"
            recent_rows += (
                f"<tr><td>{j['job_id']}</td><td>{j['n_episodes']}</td>"
                f"<td>D{j['difficulty_level']}</td>"
                f"<td><span class='badge {badge_cls}'>{j['status']}</span></td>"
                f"<td>{j['n_frames_generated']}</td><td>{j['elapsed_s']:.1f}s</td>"
                f"<td>{j['completed_at'][:19] if j['completed_at'] else '—'}</td></tr>"
            )
        if not recent_rows:
            recent_rows = "<tr><td colspan='7' style='color:#6b7280;text-align:center'>No completed jobs yet</td></tr>"

        sched = snap["schedule"]
        enabled_badge = (
            "<span class='badge badge-done'>ON</span>"
            if sched["enabled"]
            else "<span class='badge badge-failed'>OFF</span>"
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Auto SDG Pipeline — OCI Robot Cloud</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }}
  h1 {{ font-size: 1.5rem; font-weight: 700; color: #f1f5f9; }}
  h2 {{ font-size: 1.05rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; margin-bottom: .75rem; }}
  header {{ background: #1e293b; border-bottom: 1px solid #334155; padding: 1rem 2rem; display: flex; align-items: center; gap: 1rem; }}
  .tag {{ font-size: .75rem; background: #1d4ed8; color: #bfdbfe; padding: 2px 8px; border-radius: 9999px; }}
  main {{ padding: 1.5rem 2rem; max-width: 1200px; margin: 0 auto; display: grid; gap: 1.25rem; }}
  .row {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.25rem; }}
  .row2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: .75rem; padding: 1.25rem; }}
  .stat-val {{ font-size: 2.2rem; font-weight: 700; color: #f1f5f9; line-height: 1; }}
  .stat-lbl {{ font-size: .8rem; color: #64748b; margin-top: .3rem; }}
  .gauge-wrap {{ margin: .75rem 0 .3rem; }}
  .gauge-bg {{ background: #334155; border-radius: 9999px; height: 18px; overflow: hidden; }}
  .gauge-fill {{ height: 100%; border-radius: 9999px; background: {bar_color}; width: {pct}%; transition: width .4s; }}
  .gauge-label {{ font-size: .8rem; color: #94a3b8; margin-top: .3rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: .4rem .6rem; color: #64748b; border-bottom: 1px solid #334155; }}
  td {{ padding: .4rem .6rem; border-bottom: 1px solid #1e293b; }}
  .badge {{ font-size: .7rem; padding: 2px 7px; border-radius: 9999px; font-weight: 600; }}
  .badge-running {{ background: #1d4ed8; color: #bfdbfe; }}
  .badge-done {{ background: #14532d; color: #86efac; }}
  .badge-failed {{ background: #7f1d1d; color: #fca5a5; }}
  .badge-queued {{ background: #713f12; color: #fde68a; }}
  .sched-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .4rem .8rem; font-size: .85rem; }}
  .sched-lbl {{ color: #64748b; }}
  .sched-val {{ color: #e2e8f0; font-weight: 500; }}
  .pie-wrap {{ display: flex; align-items: center; gap: 1.5rem; }}
  .legend {{ font-size: .8rem; }}
  .legend li {{ list-style: none; display: flex; align-items: center; gap: .4rem; margin-bottom: .3rem; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Auto SDG Pipeline</h1>
    <div style="font-size:.8rem;color:#64748b;margin-top:.15rem">OCI Robot Cloud · Genesis Synthetic Data Generation · port 8037</div>
  </div>
  <span class="tag">auto-refill</span>
</header>
<main>
  <!-- Stats row -->
  <div class="row">
    <div class="card">
      <h2>Queue Status</h2>
      <div class="stat-val">{cur} <span style="font-size:1rem;color:#64748b">/ {tgt}</span></div>
      <div class="stat-lbl">episodes in queue</div>
      <div class="gauge-wrap">
        <div class="gauge-bg"><div class="gauge-fill"></div></div>
        <div class="gauge-label">{pct}% of target · threshold {sched['min_queue_threshold']} eps</div>
      </div>
    </div>
    <div class="card">
      <h2>Today's Activity</h2>
      <div class="stat-val">{snap['jobs_today']}</div>
      <div class="stat-lbl">SDG jobs run</div>
      <div style="margin-top:.6rem;font-size:1.4rem;font-weight:700;color:#f1f5f9">{snap['episodes_today']}</div>
      <div class="stat-lbl">episodes generated</div>
    </div>
    <div class="card">
      <h2>Schedule</h2>
      <div style="margin-bottom:.6rem">{enabled_badge}</div>
      <div class="sched-grid">
        <span class="sched-lbl">Threshold</span><span class="sched-val">{sched['min_queue_threshold']} eps</span>
        <span class="sched-lbl">Target</span><span class="sched-val">{sched['target_queue_size']} eps</span>
        <span class="sched-lbl">Poll every</span><span class="sched-val">{sched['poll_interval_s']}s</span>
        <span class="sched-lbl">Max jobs</span><span class="sched-val">{sched['max_concurrent_jobs']}</span>
      </div>
    </div>
  </div>

  <!-- Pie + Active jobs -->
  <div class="row2">
    <div class="card">
      <h2>Difficulty Distribution</h2>
      <div class="pie-wrap">
        {pie_svg}
        <ul class="legend">
          <li><span class="dot" style="background:#6366f1"></span>D1 Easy — {int(float(dist.get('1',0))*100)}%</li>
          <li><span class="dot" style="background:#22d3ee"></span>D2 Medium — {int(float(dist.get('2',0))*100)}%</li>
          <li><span class="dot" style="background:#f59e0b"></span>D3 Hard — {int(float(dist.get('3',0))*100)}%</li>
          <li><span class="dot" style="background:#ef4444"></span>D4 Expert — {int(float(dist.get('4',0))*100)}%</li>
        </ul>
      </div>
    </div>
    <div class="card">
      <h2>Active Jobs ({len(snap['active_jobs'])})</h2>
      <table>
        <thead><tr><th>ID</th><th>Eps</th><th>Diff</th><th>Status</th><th>Frames</th><th>Elapsed</th><th>Created</th></tr></thead>
        <tbody>{active_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Recent completed -->
  <div class="card">
    <h2>Recent Completed Jobs</h2>
    <table>
      <thead><tr><th>ID</th><th>Eps</th><th>Diff</th><th>Status</th><th>Frames</th><th>Elapsed</th><th>Completed</th></tr></thead>
      <tbody>{recent_rows}</tbody>
    </table>
  </div>
</main>
</body>
</html>"""
        return HTMLResponse(html)

    return app


def _build_pie_svg(dist: dict, colors: dict) -> str:
    """Generate a simple SVG pie chart from a difficulty distribution dict."""
    total = sum(float(v) for v in dist.values())
    if total == 0:
        return "<svg width='80' height='80'></svg>"

    cx, cy, r = 40, 40, 35
    parts = []
    start_angle = -90.0
    for k in sorted(dist.keys()):
        frac = float(dist[k]) / total
        sweep = frac * 360.0
        end_angle = start_angle + sweep
        large = 1 if sweep > 180 else 0
        x1 = cx + r * _cos_deg(start_angle)
        y1 = cy + r * _sin_deg(start_angle)
        x2 = cx + r * _cos_deg(end_angle)
        y2 = cy + r * _sin_deg(end_angle)
        color = colors.get(str(k), "#888")
        parts.append(
            f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large},1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>'
        )
        start_angle = end_angle

    inner = "\n".join(parts)
    return f'<svg width="80" height="80" viewBox="0 0 80 80">{inner}</svg>'


def _cos_deg(deg: float) -> float:
    import math
    return math.cos(math.radians(deg))


def _sin_deg(deg: float) -> float:
    import math
    return math.sin(math.radians(deg))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Auto SDG Pipeline — FastAPI service")
    parser.add_argument("--port", type=int, default=8037)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", help="Start with simulated low queue to trigger auto-dispatch")
    args = parser.parse_args()

    rng = random.Random(42)
    state = AutoSDGState()

    if args.mock:
        # Start with a near-empty queue to immediately trigger auto-dispatch
        state.current_queue_size = 50
        print("[mock] Queue initialised at 50 eps — auto-dispatch should trigger shortly")

    # Start background simulation loop
    t = threading.Thread(target=simulate_sdg_loop, args=(state, rng), daemon=True)
    t.start()
    print(f"[auto_sdg_pipeline] Background SDG loop started (poll ~10s, schedule poll {state.schedule.poll_interval_s}s)")

    if not HAS_FASTAPI:
        print("[auto_sdg_pipeline] FastAPI not installed — running simulation only (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(5)
                with _state_lock:
                    print(
                        f"  queue={state.current_queue_size} active={len(state.active_jobs)} "
                        f"done_today={state.jobs_today} eps_today={state.episodes_today}"
                    )
        except KeyboardInterrupt:
            print("\n[auto_sdg_pipeline] Stopped.")
        return

    app = build_app(state)
    print(f"[auto_sdg_pipeline] Serving on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
