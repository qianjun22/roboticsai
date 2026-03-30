#!/usr/bin/env python3
"""
GTC Demo Controller — OCI Robot Cloud / GR00T N1.6
===================================================
FastAPI service (port 8093) managing the GTC 2027 live demo sequence.
Controls an 8-step state machine shown on stage in San Jose.
Falls back to CLI demo-runner if FastAPI is not installed.
Oracle Confidential
"""

import json
import math
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@dataclass
class DemoStep:
    step_id: str; order: int; title: str; description: str; duration_s: int; icon: str


DEMO_STEPS: List[DemoStep] = [
    DemoStep("intro",          1, "OCI Robot Cloud Live Demo",
             "Welcome to the future of cloud robotics — live from OCI.", 5, "🤖"),
    DemoStep("sdg_genesis",    2, "Synthetic Data Generation",
             "Genesis simulation generating 1,000 synthetic pick-and-place demos.", 15, "🌐"),
    DemoStep("fine_tune",      3, "GR00T N1.6 Fine-Tuning",
             "Live fine-tuning on OCI A100 GPU4 — 2,000 steps, 35 min wall-clock.", 30, "⚡"),
    DemoStep("inference_demo", 4, "Real-Time Inference",
             "Pick-and-place inference: 226 ms end-to-end latency on A100.", 20, "🎯"),
    DemoStep("dagger_improve", 5, "DAgger Online Learning",
             "DAgger loop: Success Rate improves from 5% → 65% across 5 iterations.", 25, "📈"),
    DemoStep("multi_robot",    6, "Fleet Coordination",
             "Six robots executing coordinated tasks — 99.94% uptime across regions.", 20, "🦶"),
    DemoStep("results",        7, "Key Metrics Dashboard",
             "SR=71%, MAE=0.013, $0.43/run, 9.6× cheaper than on-prem H100.", 15, "📊"),
    DemoStep("cta",            8, "Join the Beta",
             "OCI Robot Cloud Beta — apply at oracle.com/robotics", 10, "🚀"),
]

STEP_MAP: Dict[str, DemoStep] = {s.step_id: s for s in DEMO_STEPS}

BOOTH = {
    "event": "GTC 2027", "location": "San Jose Convention Center",
    "booth_number": "OCI-R42", "presenter": "Jun Qian",
    "gpu": "OCI A100 80GB (138.1.153.110)",
    "tagline": "NVIDIA trains the model. Oracle trains the robot.",
}


class DemoState(str, Enum):
    READY = "ready"; RUNNING = "running"; PAUSED = "paused"; COMPLETE = "complete"; ERROR = "error"


@dataclass
class DemoSession:
    session_id:    str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    presenter:     str   = "Jun Qian"
    venue:         str   = "GTC 2027 San Jose"
    state:         DemoState = DemoState.READY
    current_step:  int   = 0
    step_start_ts: float = 0.0
    elapsed_s:     float = 0.0
    events:        List[Dict[str, Any]] = field(default_factory=list)
    created_at:    float = field(default_factory=time.time)

    @property
    def current_step_obj(self) -> Optional[DemoStep]:
        if 1 <= self.current_step <= len(DEMO_STEPS): return DEMO_STEPS[self.current_step - 1]
        return None

    @property
    def countdown_s(self) -> float:
        step = self.current_step_obj
        if step is None or self.state != DemoState.RUNNING: return 0.0
        return max(0.0, step.duration_s - (time.time() - self.step_start_ts))

    def push_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        evt = {"event": event_type, "step": self.current_step,
               "step_id": self.current_step_obj.step_id if self.current_step_obj else None,
               "state": self.state.value, "ts": time.time(), "payload": payload}
        self.events.append(evt); return evt


_SESSIONS: Dict[str, DemoSession] = {}

def get_or_create_session(session_id: Optional[str] = None) -> DemoSession:
    if session_id and session_id in _SESSIONS: return _SESSIONS[session_id]
    sess = DemoSession(); _SESSIONS[sess.session_id] = sess; return sess

def default_session() -> DemoSession:
    if _SESSIONS: return next(reversed(_SESSIONS.values()))
    return get_or_create_session()


def build_dashboard_html(sess: DemoSession) -> str:
    step_cards = ""
    for s in DEMO_STEPS:
        if s.order < sess.current_step:
            sc, badge = "done", "✓ Done"
        elif s.order == sess.current_step:
            sc, badge = "active", f"▶ Live — {sess.countdown_s:.0f}s left"
        else:
            sc, badge = "pending", f"{s.duration_s}s"
        step_cards += f'<div class="step-card {sc}"><div class="step-icon">{s.icon}</div><div class="step-info"><div class="step-title">{s.order}. {s.title}</div><div class="step-desc">{s.description}</div></div><div class="step-badge">{badge}</div></div>'
    state_color = {"ready":"#64748b","running":"#22c55e","paused":"#f59e0b","complete":"#3b82f6","error":"#ef4444"}.get(sess.state.value, "#64748b")
    current_title = sess.current_step_obj.title if sess.current_step_obj else "—"
    total_dur = sum(s.duration_s for s in DEMO_STEPS)
    elapsed_pct = min(100, round(100 * sess.elapsed_s / total_dur, 1))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta http-equiv="refresh" content="3"/>
<title>OCI Robot Cloud — GTC 2027 Demo Controller</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:28px;line-height:1.5}}
h1{{color:#C74634;font-size:22px;margin-bottom:4px}}.meta{{color:#64748b;font-size:13px;margin-bottom:20px}}
.status-bar{{display:flex;gap:16px;align-items:center;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 18px;margin-bottom:20px}}
.state-badge{{background:{state_color};color:#0f172a;font-weight:bold;padding:4px 12px;border-radius:20px;font-size:13px}}
.progress-track{{flex:1;height:8px;background:#334155;border-radius:4px}}
.progress-fill{{height:8px;background:#C74634;border-radius:4px;width:{elapsed_pct}%}}
.step-card{{display:flex;align-items:center;gap:14px;padding:12px 16px;border-radius:8px;margin-bottom:8px;border:1px solid #1e293b}}
.step-card.done{{background:#0d2010;border-color:#166534;opacity:0.7}}.step-card.active{{background:#1c1a0e;border-color:#C74634;box-shadow:0 0 12px rgba(199,70,52,0.25)}}
.step-card.pending{{background:#1e293b;border-color:#334155}}.step-icon{{font-size:22px;width:32px;text-align:center}}.step-info{{flex:1}}
.step-title{{font-size:14px;font-weight:600;color:#e2e8f0}}.step-desc{{font-size:12px;color:#64748b;margin-top:2px}}
.step-badge{{font-size:12px;color:#94a3b8;white-space:nowrap}}.step-card.active .step-badge{{color:#C74634;font-weight:bold}}
.controls{{display:flex;gap:10px;margin-bottom:20px}}.btn{{padding:8px 18px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}}
.btn-start{{background:#C74634;color:#fff}}.btn-next{{background:#1d4ed8;color:#fff}}
.btn-pause{{background:#d97706;color:#fff}}.btn-reset{{background:#374151;color:#e2e8f0}}
.section-title{{color:#C74634;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin:16px 0 8px}}
.event-log{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;font-size:12px;font-family:monospace;color:#94a3b8;max-height:180px;overflow-y:auto}}
.footer{{margin-top:28px;text-align:center;color:#475569;font-size:12px;border-top:1px solid #1e293b;padding-top:14px}}
</style></head><body>
<h1>OCI Robot Cloud — GTC 2027 Demo Controller</h1>
<p class="meta">Session: {sess.session_id} · Presenter: {sess.presenter} · Venue: {sess.venue}</p>
<div class="status-bar">
  <span class="state-badge">{sess.state.value.upper()}</span>
  <span style="font-size:13px;color:#94a3b8">Step {sess.current_step}/{len(DEMO_STEPS)} — <b style="color:#e2e8f0">{current_title}</b></span>
  <div class="progress-track"><div class="progress-fill"></div></div>
  <span style="font-size:13px;color:#64748b">{elapsed_pct}%</span>
</div>
<div class="controls">
  <button class="btn btn-start" onclick="fetch('/demo/start',{{method:'POST'}}).then(()=>location.reload())">&#9654; Start</button>
  <button class="btn btn-next" onclick="fetch('/demo/next',{{method:'POST'}}).then(()=>location.reload())">&#9197; Next Step</button>
  <button class="btn btn-pause" onclick="fetch('/demo/pause',{{method:'POST'}}).then(()=>location.reload())">&#9208; Pause</button>
  <button class="btn btn-reset" onclick="fetch('/demo/reset',{{method:'POST'}}).then(()=>location.reload())">&#8635; Reset</button>
</div>
<div class="section-title">Demo Sequence</div>{step_cards}
<div class="section-title">Event Log ({len(sess.events)} events)</div>
<div class="event-log">{"<br>".join(f"[{time.strftime('%H:%M:%S', time.localtime(e['ts']))}] {e['event']} step={e['step']} {json.dumps(e['payload'])[:80]}" for e in reversed(sess.events[-30:])) or "No events yet."}</div>
<div class="footer">Oracle Confidential — OCI Robot Cloud · GTC 2027 San Jose</div>
</body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="OCI Robot Cloud — GTC 2027 Demo Controller", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return HTMLResponse(build_dashboard_html(default_session()))

    @app.post("/demo/start")
    async def demo_start(presenter: str = "Jun Qian"):
        sess = get_or_create_session()
        if sess.state == DemoState.RUNNING: raise HTTPException(400, "Demo already running")
        sess.state = DemoState.RUNNING; sess.presenter = presenter
        sess.current_step = 1; sess.step_start_ts = time.time()
        evt = sess.push_event("demo_started", {"presenter": presenter, "steps": len(DEMO_STEPS)})
        return {"session_id": sess.session_id, "state": sess.state, "event": evt}

    @app.post("/demo/pause")
    async def demo_pause():
        sess = default_session()
        if sess.state == DemoState.RUNNING:
            sess.state = DemoState.PAUSED; sess.elapsed_s += time.time() - sess.step_start_ts
        elif sess.state == DemoState.PAUSED:
            sess.state = DemoState.RUNNING; sess.step_start_ts = time.time()
        return {"state": sess.state}

    @app.post("/demo/next")
    async def demo_next():
        sess = default_session()
        if sess.state not in (DemoState.RUNNING, DemoState.PAUSED): raise HTTPException(400, "Demo not active")
        sess.elapsed_s += time.time() - sess.step_start_ts
        if sess.current_step >= len(DEMO_STEPS):
            sess.state = DemoState.COMPLETE
            return {"state": sess.state, "current_step": sess.current_step}
        sess.current_step += 1; sess.step_start_ts = time.time(); sess.state = DemoState.RUNNING
        step = sess.current_step_obj
        evt = sess.push_event("step_advanced", {"step_id": step.step_id, "duration_s": step.duration_s})
        return {"state": sess.state, "current_step": sess.current_step, "event": evt}

    @app.post("/demo/reset")
    async def demo_reset():
        sess = default_session()
        sess.state = DemoState.READY; sess.current_step = 0
        sess.step_start_ts = 0.0; sess.elapsed_s = 0.0; sess.events.clear()
        return {"state": sess.state}

    @app.get("/demo/state")
    async def demo_state():
        sess = default_session(); step = sess.current_step_obj
        return {"session_id": sess.session_id, "state": sess.state, "current_step": sess.current_step,
                "step_id": step.step_id if step else None, "countdown_s": round(sess.countdown_s, 1),
                "elapsed_s": round(sess.elapsed_s, 1), "total_steps": len(DEMO_STEPS)}

    @app.get("/steps")
    async def list_steps(): return [asdict(s) for s in DEMO_STEPS]

    @app.get("/health")
    async def health(): return {"status": "ok", "service": "gtc-demo-controller", "port": 8093, "booth": BOOTH}


if __name__ == "__main__":
    import sys
    if "--cli" in sys.argv or not HAS_FASTAPI:
        sess = DemoSession(); sess.state = DemoState.RUNNING; sess.current_step = 1
        print(f"\n{'='*70}\n  OCI Robot Cloud — GTC 2027 Live Demo (CLI Mode)\n{'='*70}")
        for step in DEMO_STEPS:
            sess.current_step = step.order; sess.step_start_ts = time.time()
            print(f"\n[{step.order}/{len(DEMO_STEPS)}] {step.icon}  {step.title}")
            print(f"       {step.description}")
            ticks = min(step.duration_s, 20); dt = step.duration_s / ticks
            for i in range(ticks):
                filled = int(20 * (i + 1) / ticks)
                print(f"\r       [{'\u2588' * filled}{'\u2591' * (20 - filled)}] {int(100*(i+1)/ticks):3d}%", end="", flush=True)
                time.sleep(dt)
            print(f"\r       [{'\u2588'*20}] 100% — done")
        print(f"\n{'='*70}\n  SR=71% MAE=0.013 $0.43/run 9.6\u00d7 speedup\n  Oracle Confidential — GTC 2027 San Jose\n{'='*70}")
    else:
        sess = get_or_create_session()
        print(f"[gtc-demo] GTC 2027 Demo Controller on http://0.0.0.0:8093 | Session {sess.session_id}")
        uvicorn.run(app, host="0.0.0.0", port=8093, log_level="info")
