#!/usr/bin/env python3
"""
online_dagger_server.py — Continuous online DAgger data collection service (port 8033).

Runs as a persistent service that:
  1. Monitors closed-loop success rate from the live eval streamer
  2. Automatically triggers DAgger collection when success drops
  3. Queues collected episodes for incremental fine-tuning
  4. Promotes new checkpoints when validation improves

This closes the production flywheel:
  robot collects data → DAgger labels → fine-tune → promote → robot improved

Usage:
    python src/training/online_dagger_server.py --port 8033 --mock
    # → http://localhost:8033
"""

import json
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.responses import StreamingResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Config ────────────────────────────────────────────────────────────────────

TRIGGER_DROP_THRESHOLD = 0.10   # trigger DAgger if success drops by >10pp
MIN_EPISODES_PER_ITER  = 20     # minimum episodes to collect per DAgger iter
FINETUNE_STEPS         = 1000   # steps per incremental fine-tune
EVAL_WINDOW_EPISODES   = 20     # rolling window for success rate
PROMOTION_THRESHOLD    = 0.05   # promote if new checkpoint is >5pp better
POLL_INTERVAL_S        = 30     # check eval server every 30s


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class DaggerEvent:
    event_type: str      # trigger / collect / finetune / promote / skip
    timestamp: str
    success_rate_before: float = 0.0
    success_rate_after: float  = 0.0
    n_episodes: int = 0
    checkpoint: str = ""
    notes: str = ""


@dataclass
class OnlineDaggerState:
    current_success_rate: float = 0.05
    peak_success_rate: float    = 0.05
    baseline_checkpoint: str    = "/tmp/finetune_1000_5k/checkpoint-5000"
    current_checkpoint: str     = "/tmp/finetune_1000_5k/checkpoint-5000"
    n_iters_completed: int      = 0
    n_episodes_collected: int   = 0
    n_finetunings: int          = 0
    n_promotions: int           = 0
    events: list[DaggerEvent]   = field(default_factory=list)
    status: str                 = "monitoring"   # monitoring / collecting / finetuning / promoting
    last_check_at: str          = ""
    started_at: str             = ""
    is_mock: bool               = True


# ── Simulation ────────────────────────────────────────────────────────────────

def simulate_online_dagger(state: OnlineDaggerState, rng: random.Random) -> None:
    """Simulate online DAgger loop (background thread)."""
    state.started_at = datetime.now().isoformat()
    base_rate = state.current_success_rate
    iter_count = 0

    while True:
        time.sleep(5)   # poll interval (faster in simulation)
        state.last_check_at = datetime.now().isoformat()

        # Simulate success rate drift + improvement
        noise = rng.gauss(0, 0.02)
        improvement = iter_count * 0.08  # each DAgger iter adds ~8pp
        state.current_success_rate = min(
            0.95, max(0.01, base_rate + improvement + noise)
        )

        if state.current_success_rate > state.peak_success_rate:
            state.peak_success_rate = state.current_success_rate

        # Check if trigger needed
        drop = state.peak_success_rate - state.current_success_rate
        needs_trigger = drop >= TRIGGER_DROP_THRESHOLD or iter_count == 0

        if needs_trigger and state.status == "monitoring":
            ts = datetime.now().isoformat()
            state.status = "collecting"
            n_eps = MIN_EPISODES_PER_ITER + rng.randint(0, 10)
            state.events.append(DaggerEvent(
                event_type="trigger", timestamp=ts,
                success_rate_before=state.current_success_rate,
                notes=f"Drop {drop:.0%} triggered collection" if drop > 0 else "Initial collection",
            ))

            # Simulate collection (5s)
            time.sleep(5)
            state.n_episodes_collected += n_eps
            state.events.append(DaggerEvent(
                event_type="collect", timestamp=datetime.now().isoformat(),
                n_episodes=n_eps,
                notes=f"Collected {n_eps} on-policy episodes (beta={max(0.0, 0.3 - iter_count*0.05):.2f})",
            ))

            # Fine-tune
            state.status = "finetuning"
            time.sleep(8)  # simulate fine-tune
            state.n_finetunings += 1
            new_ckpt = f"/tmp/online_dagger/iter{iter_count+1}/checkpoint-{FINETUNE_STEPS}"
            state.current_checkpoint = new_ckpt
            state.events.append(DaggerEvent(
                event_type="finetune", timestamp=datetime.now().isoformat(),
                n_episodes=n_eps, checkpoint=new_ckpt,
                notes=f"{FINETUNE_STEPS} steps on {state.n_episodes_collected} total episodes",
            ))

            # Validate and promote
            new_rate = state.current_success_rate + rng.uniform(0.03, 0.15)
            improvement_margin = new_rate - state.current_success_rate
            if improvement_margin >= PROMOTION_THRESHOLD:
                state.n_promotions += 1
                state.peak_success_rate = new_rate
                state.current_success_rate = new_rate
                state.events.append(DaggerEvent(
                    event_type="promote", timestamp=datetime.now().isoformat(),
                    success_rate_before=state.current_success_rate,
                    success_rate_after=new_rate,
                    checkpoint=new_ckpt,
                    notes=f"+{improvement_margin:.0%} improvement → promoted to production",
                ))
            else:
                state.events.append(DaggerEvent(
                    event_type="skip", timestamp=datetime.now().isoformat(),
                    success_rate_before=state.current_success_rate,
                    notes=f"+{improvement_margin:.0%} below promotion threshold {PROMOTION_THRESHOLD:.0%}",
                ))

            iter_count += 1
            state.n_iters_completed = iter_count
            state.status = "monitoring"

        if iter_count >= 8:  # stop after 8 iters in simulation
            state.status = "monitoring"
            break


# ── HTML dashboard ────────────────────────────────────────────────────────────

def render_dashboard(state: OnlineDaggerState) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_color = {
        "monitoring": "#3b82f6",
        "collecting": "#f59e0b",
        "finetuning": "#6366f1",
        "promoting":  "#22c55e",
    }.get(state.status, "#94a3b8")

    # Event log (most recent first)
    event_rows = ""
    for evt in reversed(state.events[-20:]):
        icon = {"trigger":"🔔","collect":"📦","finetune":"🔧","promote":"✅","skip":"⏭"}.get(evt.event_type,"•")
        rate_str = f" → {evt.success_rate_after:.0%}" if evt.success_rate_after > 0 else ""
        event_rows += f"""<tr>
          <td style="padding:6px 10px;font-size:12px;color:#64748b">{evt.timestamp[11:19]}</td>
          <td style="padding:6px 10px">{icon} {evt.event_type}</td>
          <td style="padding:6px 10px;font-size:12px;color:#94a3b8">{evt.notes[:80]}{rate_str}</td>
        </tr>"""

    # Sparkline of success rate (mock history)
    rng2 = random.Random(42)
    history = [max(0.01, state.current_success_rate - 0.3 + i * 0.04 + rng2.gauss(0,0.02))
               for i in range(20)]
    max_h = max(history)
    svg_pts = " ".join(
        f"{20+i*16:.0f},{80-h/max(max_h,0.01)*60:.0f}"
        for i, h in enumerate(history)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="15">
<title>Online DAgger Server</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:6px 10px;text-align:left;border-bottom:1px solid #334155}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 14px;margin:4px;text-align:center}}
</style>
</head>
<body>
<h1>Online DAgger Server</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 12px">{now} · auto-refresh 15s</p>

<div class="card">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
    <div style="width:12px;height:12px;border-radius:50%;background:{status_color};animation:pulse 1.5s infinite"></div>
    <span style="font-weight:600;color:{status_color};font-size:16px">{state.status.upper()}</span>
  </div>
  <div>
    <div class="m"><div style="font-size:24px;font-weight:700;color:#22c55e">{state.current_success_rate:.0%}</div><div style="font-size:11px;color:#64748b">Current success</div></div>
    <div class="m"><div style="font-size:24px;font-weight:700;color:#3b82f6">{state.peak_success_rate:.0%}</div><div style="font-size:11px;color:#64748b">Peak success</div></div>
    <div class="m"><div style="font-size:24px;font-weight:700;color:#6366f1">{state.n_iters_completed}</div><div style="font-size:11px;color:#64748b">DAgger iters</div></div>
    <div class="m"><div style="font-size:24px;font-weight:700;color:#f59e0b">{state.n_episodes_collected}</div><div style="font-size:11px;color:#64748b">Episodes collected</div></div>
    <div class="m"><div style="font-size:24px;font-weight:700;color:#94a3b8">{state.n_promotions}</div><div style="font-size:11px;color:#64748b">Promotions</div></div>
  </div>
</div>

<div class="card" style="display:flex;gap:16px">
  <div style="flex:1">
    <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px">Success Rate Trend</div>
    <svg width="340" height="90" style="background:#0f172a;border-radius:6px">
      <polyline points="{svg_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>
      <line x1="20" y1="{80-TRIGGER_DROP_THRESHOLD/max(max_h,0.01)*60:.0f}" x2="320" y2="{80-TRIGGER_DROP_THRESHOLD/max(max_h,0.01)*60:.0f}" stroke="#ef4444" stroke-dasharray="3,3" stroke-width="1"/>
    </svg>
  </div>
  <div style="flex:1;background:#0c1a2e;border:1px solid #1e3a5f;border-radius:8px;padding:12px">
    <div style="font-size:12px;color:#3b82f6;text-transform:uppercase;margin-bottom:6px">Config</div>
    <div style="font-size:12px;color:#94a3b8">
      Trigger: >{TRIGGER_DROP_THRESHOLD:.0%} drop from peak<br>
      Episodes/iter: ≥{MIN_EPISODES_PER_ITER}<br>
      Fine-tune steps: {FINETUNE_STEPS}<br>
      Promotion threshold: >{PROMOTION_THRESHOLD:.0%} improvement<br>
      Current checkpoint: {state.current_checkpoint[-40:]}<br>
    </div>
  </div>
</div>

<div class="card">
  <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:8px">Event Log (recent)</div>
  <table>
    <tr><th>Time</th><th>Event</th><th>Notes</th></tr>
    {event_rows}
  </table>
</div>

<style>@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}</style>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app(mock: bool = True) -> "FastAPI":
    app = FastAPI(title="Online DAgger Server", version="1.0")
    state = OnlineDaggerState(is_mock=mock)
    rng = random.Random(42)

    @app.on_event("startup")
    async def startup():
        if mock:
            t = threading.Thread(
                target=simulate_online_dagger, args=(state, rng), daemon=True
            )
            t.start()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return render_dashboard(state)

    @app.get("/api/state")
    async def api_state():
        return {
            "status": state.status,
            "current_success_rate": state.current_success_rate,
            "peak_success_rate": state.peak_success_rate,
            "n_iters": state.n_iters_completed,
            "n_episodes": state.n_episodes_collected,
            "n_promotions": state.n_promotions,
            "current_checkpoint": state.current_checkpoint,
            "last_check_at": state.last_check_at,
        }

    @app.get("/api/events")
    async def api_events(limit: int = 20):
        return [
            {"event_type": e.event_type, "timestamp": e.timestamp,
             "notes": e.notes, "n_episodes": e.n_episodes,
             "checkpoint": e.checkpoint}
            for e in reversed(state.events[-limit:])
        ]

    @app.post("/api/trigger")
    async def manual_trigger():
        """Manually trigger a DAgger collection round."""
        if state.status != "monitoring":
            raise HTTPException(409, f"Cannot trigger: status={state.status}")
        # Simulate immediate collection
        state.events.append(DaggerEvent(
            event_type="trigger",
            timestamp=datetime.now().isoformat(),
            success_rate_before=state.current_success_rate,
            notes="Manual trigger via API",
        ))
        return {"status": "triggered"}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "online_dagger_server", "port": 8033}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Online DAgger server (port 8033)")
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app(mock=args.mock)
    print(f"Online DAgger Server → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
