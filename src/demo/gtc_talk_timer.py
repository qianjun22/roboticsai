"""
GTC 2027 Talk Timer — CLI + Web Rehearsal Tool
===============================================

Helps Jun stay on schedule during the 30-minute GTC 2027 live presentation.

Usage:
    python src/demo/gtc_talk_timer.py --rehearse   # Interactive terminal timer
    python src/demo/gtc_talk_timer.py --web         # FastAPI presenter view (port 8057)
    python src/demo/gtc_talk_timer.py --history     # Show rehearsal history & improvement

Rehearsal mode:
    Press Enter to advance to the next slide.
    Timing is color-coded: green = on time, yellow = slightly over (< 30s), red = over.
    At the end, the session is saved to ~/.gtc_rehearsal_log.json.

Web mode (port 8057):
    Opens a dark-theme presenter view with large slide name, per-slide countdown,
    and total elapsed. Use ArrowRight / Space / button to advance. Toggle auto-advance
    via the UI. The server also exposes a REST API for programmatic control.

Dependencies:
    pip install fastapi uvicorn
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Talk structure
# ---------------------------------------------------------------------------

SLIDES = [
    {
        "number": 1,
        "title": "Title",
        "minutes": 1,
        "notes": [
            "Welcome and brief self-introduction — Jun Qian, OCI Robotics AI lead",
            "Set the scene: AI models are smart, but they can't yet act in the physical world",
            "Tease the live demo coming up — real robot, real inference, right here",
            "Thank NVIDIA for the partnership and the GTC stage",
        ],
    },
    {
        "number": 2,
        "title": "The Problem",
        "minutes": 2,
        "notes": [
            "Training robot policies today requires expensive hardware and weeks of iteration",
            "Sim-to-real gap kills 80% of models before they touch a real robot",
            "No cloud-native solution exists — researchers are stuck on-prem GPU clusters",
            "The market is ready: AMR market $10B → $100B by 2030 (NVIDIA stat)",
            "Oracle's opportunity: be the infrastructure layer for embodied AI",
        ],
    },
    {
        "number": 3,
        "title": "Our Solution",
        "minutes": 2,
        "notes": [
            "OCI Robot Cloud: end-to-end pipeline from simulation → fine-tuning → deployment",
            "Built on GR00T N1.6 (NVIDIA) + Genesis physics engine + OCI A100/H100",
            "Three stages: Synthetic Data Generation, Policy Fine-tuning, Closed-loop Eval",
            "SDK + REST API: any team can integrate in hours, not months",
            "Live demo will walk through all three stages right now",
        ],
    },
    {
        "number": 4,
        "title": "Live Demo Part 1 — Genesis SDG",
        "minutes": 3,
        "notes": [
            "Launch Genesis simulation on OCI — 2000 episodes, domain randomization on",
            "Show RTX lighting + randomized cube positions, textures, camera angles",
            "Point out throughput: ~200 episodes/min on a single A100 node",
            "Download generated LeRobot-format dataset — ready for fine-tuning",
            "Key message: hours of robot time → minutes of cloud time",
        ],
    },
    {
        "number": 5,
        "title": "Live Demo Part 2 — Fine-tuning",
        "minutes": 4,
        "notes": [
            "Submit fine-tune job via CLI: `oci-robot-cloud finetune submit --demos 1000`",
            "Show live training monitor: loss curve dropping in real time",
            "Highlight multi-GPU DDP: 3.07× throughput vs single GPU",
            "Cost callout: $0.0043 per 10k steps on OCI A100 (vs $0.018 on competitor)",
            "Show checkpoint at step 2000: MAE 0.013 (vs 0.103 baseline — 8.7× improvement)",
            "Model card auto-generated and pushed to registry",
        ],
    },
    {
        "number": 6,
        "title": "Live Demo Part 3 — Eval",
        "minutes": 3,
        "notes": [
            "Run closed-loop eval: 20 episodes, pick-and-place task",
            "Show eval server receiving GR00T inference at 231ms latency",
            "Success metric: cube lifted above 0.78m threshold",
            "Compare BC baseline vs fine-tuned: expected improvement on screen",
            "Key message: full eval cycle in under 5 minutes, no robot required until deploy",
        ],
    },
    {
        "number": 7,
        "title": "Results",
        "minutes": 2,
        "notes": [
            "MAE: 0.103 (baseline GR00T) → 0.013 after fine-tune (8.7× reduction)",
            "Training loss: converges in ~1000 steps with IK motion-planned SDG",
            "Inference latency: 227ms on OCI A100 (GR00T N1.6, 6.7GB)",
            "DAgger run5: 5000-step fine-tune pipeline demonstrated end-to-end",
        ],
    },
    {
        "number": 8,
        "title": "Multi-GPU Scaling",
        "minutes": 2,
        "notes": [
            "DDP training: 3.07× throughput on 4× A100 vs 1× A100",
            "Linear scaling validated up to 8 GPUs — cost-per-step stays flat",
            "Auto-scaling: OCI Kubernetes spins up GPU nodes on demand",
            "HPO search: 16 hyperparameter trials run in parallel, 4× faster convergence",
        ],
    },
    {
        "number": 9,
        "title": "Cost Comparison",
        "minutes": 2,
        "notes": [
            "OCI A100: $0.0043 / 10k steps — 4× cheaper than comparable AWS P4d",
            "Full 5000-step fine-tune: ~$2.15 on OCI vs ~$8.60 on AWS",
            "SDG: 2000 episodes on OCI ≈ $0.80 vs 200 real-world demos ≈ $2000+ in robot time",
            "Break-even: first fine-tune job pays for itself vs any alternative",
        ],
    },
    {
        "number": 10,
        "title": "Sim-to-Real",
        "minutes": 1,
        "notes": [
            "Sim-to-real validator: automated gap analysis between sim metrics and real-robot KPIs",
            "Domain randomization in Genesis narrows the gap to <15% on standard benchmarks",
            "Jetson deploy pipeline: model → TensorRT → edge inference in one CLI command",
        ],
    },
    {
        "number": 11,
        "title": "DAgger Results",
        "minutes": 2,
        "notes": [
            "DAgger: online imitation learning that corrects distribution shift",
            "Run5: 5000 steps, 99 human correction episodes collected in sim",
            "Pipeline: auto-retrain triggers when live success rate drops below threshold",
            "Data flywheel: each deployed robot feeds correction data back to the cloud",
        ],
    },
    {
        "number": 12,
        "title": "NVIDIA Partnership",
        "minutes": 2,
        "notes": [
            "OCI is NVIDIA's preferred cloud for Isaac Sim + GR00T workloads",
            "Joint go-to-market: OCI Robot Cloud featured in NVIDIA AI Enterprise catalog",
            "Cosmos world model integration: photorealistic SDG at scale",
            "NIM microservices: GR00T N1.6 deployable as managed OCI service",
        ],
    },
    {
        "number": 13,
        "title": "Roadmap",
        "minutes": 1,
        "notes": [
            "Q2 2026: Isaac Sim RTX SDG GA, multi-task curriculum fine-tuning",
            "Q3 2026: Real-time safety monitor, teleoperation data collector",
            "Q4 2026: Policy distillation, embodiment adapter for 10+ robot form factors",
            "2027: Full autonomy loop — cloud training → Jetson edge → data flywheel",
        ],
    },
    {
        "number": 14,
        "title": "Call to Action + Q&A",
        "minutes": 3,
        "notes": [
            "Try OCI Robot Cloud today: `pip install oci-robot-cloud` — free tier available",
            "GitHub: github.com/qianjun22/roboticsai — open source pipeline",
            "Scan QR code for early-access signup and NVIDIA partnership deck",
            "Q&A: I have 2 minutes — what questions do you have?",
        ],
    },
]

TOTAL_MINUTES = sum(s["minutes"] for s in SLIDES)  # 30
LOG_PATH = Path.home() / ".gtc_rehearsal_log.json"

# ---------------------------------------------------------------------------
# ANSI colors (terminal)
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
CLEAR_LINE = "\r\033[K"


def _color_time(elapsed: float, budget: float) -> str:
    """Return ANSI-colored elapsed string based on budget adherence."""
    over = elapsed - budget
    mins, secs = divmod(int(elapsed), 60)
    label = f"{mins:02d}:{secs:02d}"
    if over <= 0:
        return f"{GREEN}{label}{RESET}"
    elif over <= 30:
        return f"{YELLOW}{label}{RESET}"
    else:
        return f"{RED}{label}{RESET}"


# ---------------------------------------------------------------------------
# Rehearsal log
# ---------------------------------------------------------------------------

def load_log() -> list[dict]:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except Exception:
            return []
    return []


def save_session(session: dict) -> None:
    log = load_log()
    log.append(session)
    LOG_PATH.write_text(json.dumps(log, indent=2))


# ---------------------------------------------------------------------------
# CLI rehearsal mode
# ---------------------------------------------------------------------------

def run_rehearsal() -> None:
    print(f"\n{BOLD}{CYAN}=== GTC 2027 Talk Timer — Rehearsal Mode ==={RESET}")
    print(f"{DIM}Total: {TOTAL_MINUTES} minutes across {len(SLIDES)} slides{RESET}")
    print(f"{DIM}Press Enter to advance to next slide. Ctrl+C to abort.{RESET}\n")

    session_start = time.time()
    slide_timings: list[dict] = []

    for idx, slide in enumerate(SLIDES):
        budget_secs = slide["minutes"] * 60
        slide_start = time.time()

        print(f"{BOLD}Slide {slide['number']}/{len(SLIDES)}: {slide['title']}{RESET}")
        print(f"  Budget: {slide['minutes']} min  ({budget_secs}s)")
        print(f"  {DIM}Speaker notes:{RESET}")
        for note in slide["notes"]:
            print(f"    • {note}")

        # Live countdown thread
        stop_event = threading.Event()

        def _ticker(budget: float, start: float, stop: threading.Event) -> None:
            while not stop.is_set():
                elapsed = time.time() - start
                remaining = budget - elapsed
                mins_e, secs_e = divmod(int(elapsed), 60)
                mins_r, secs_r = divmod(max(0, int(remaining)), 60)
                sign = "-" if remaining < 0 else " "
                color = GREEN if remaining >= 0 else (YELLOW if remaining > -30 else RED)
                sys.stdout.write(
                    f"{CLEAR_LINE}  Elapsed {_color_time(elapsed, budget)}  "
                    f"Remaining: {color}{sign}{mins_r:02d}:{secs_r:02d}{RESET}  "
                    f"[Press Enter to advance]"
                )
                sys.stdout.flush()
                time.sleep(0.5)

        ticker = threading.Thread(target=_ticker, args=(budget_secs, slide_start, stop_event), daemon=True)
        ticker.start()

        try:
            input()  # wait for Enter
        except KeyboardInterrupt:
            stop_event.set()
            print(f"\n\n{YELLOW}Rehearsal aborted.{RESET}\n")
            return

        stop_event.set()
        elapsed = time.time() - slide_start
        over = elapsed - budget_secs

        over_str = ""
        if abs(over) >= 1:
            sign = "+" if over > 0 else "-"
            mins_o, secs_o = divmod(int(abs(over)), 60)
            over_str = f"  ({sign}{mins_o:02d}:{secs_o:02d} vs budget)"

        print(
            f"\n  Final: {_color_time(elapsed, budget_secs)}{over_str}\n"
        )
        slide_timings.append(
            {
                "slide_number": slide["number"],
                "title": slide["title"],
                "budget_secs": budget_secs,
                "elapsed_secs": round(elapsed, 2),
                "over_secs": round(over, 2),
            }
        )

    total_elapsed = time.time() - session_start
    total_budget = TOTAL_MINUTES * 60
    total_mins, total_secs = divmod(int(total_elapsed), 60)
    print(f"{BOLD}=== Session Complete ==={RESET}")
    print(
        f"Total: {_color_time(total_elapsed, total_budget)} / {TOTAL_MINUTES:02d}:00  "
        f"({'OVER' if total_elapsed > total_budget else 'UNDER'} by "
        f"{abs(int(total_elapsed - total_budget))}s)\n"
    )

    session = {
        "date": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_secs": round(total_elapsed, 2),
        "total_budget_secs": total_budget,
        "slides": slide_timings,
    }
    save_session(session)
    print(f"{DIM}Session saved to {LOG_PATH}{RESET}\n")


# ---------------------------------------------------------------------------
# History mode
# ---------------------------------------------------------------------------

def show_history() -> None:
    log = load_log()
    if not log:
        print("No rehearsal sessions recorded yet. Run with --rehearse first.")
        return

    print(f"\n{BOLD}{CYAN}=== GTC 2027 Rehearsal History ({len(log)} sessions) ==={RESET}\n")

    for i, session in enumerate(log, 1):
        date_str = session.get("date", "unknown")[:19].replace("T", " ")
        total = session.get("total_elapsed_secs", 0)
        budget = session.get("total_budget_secs", TOTAL_MINUTES * 60)
        over = total - budget
        sign = "+" if over > 0 else ""
        mins_t, secs_t = divmod(int(total), 60)
        print(f"  {BOLD}Session {i}{RESET}  {DIM}{date_str} UTC{RESET}")
        print(f"    Total: {mins_t:02d}:{secs_t:02d}  ({sign}{int(over)}s vs {TOTAL_MINUTES}:00 budget)")

        slides = session.get("slides", [])
        worst = sorted(slides, key=lambda s: s.get("over_secs", 0), reverse=True)[:3]
        if worst:
            print(f"    Slowest slides:")
            for s in worst:
                over_s = s.get("over_secs", 0)
                sign_s = "+" if over_s > 0 else ""
                e = s.get("elapsed_secs", 0)
                m, sec = divmod(int(e), 60)
                print(f"      Slide {s['slide_number']} {s['title']}: {m:02d}:{sec:02d}  ({sign_s}{int(over_s)}s)")
        print()

    # Trend
    if len(log) >= 2:
        first_over = log[0]["total_elapsed_secs"] - log[0]["total_budget_secs"]
        last_over = log[-1]["total_elapsed_secs"] - log[-1]["total_budget_secs"]
        delta = first_over - last_over
        if delta > 0:
            print(f"{GREEN}Improvement: {int(delta)}s closer to budget over {len(log)} sessions{RESET}\n")
        elif delta < 0:
            print(f"{YELLOW}Trend: {int(abs(delta))}s slower vs first session — keep rehearsing!{RESET}\n")
        else:
            print(f"{DIM}No change in total time vs first session.{RESET}\n")


# ---------------------------------------------------------------------------
# Web mode — FastAPI presenter view
# ---------------------------------------------------------------------------

def run_web(port: int = 8057, auto_advance_default: bool = False) -> None:
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        import uvicorn
    except ImportError:
        print("FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)

    app = FastAPI(title="GTC 2027 Talk Timer")

    # Shared state (single presenter)
    state = {
        "slide_index": 0,
        "slide_start_ts": time.time(),
        "session_start_ts": time.time(),
        "history": [],  # per-slide elapsed recorded on advance
        "auto_advance": auto_advance_default,
        "auto_advance_interval": 0,  # computed from slide budget
        "session_saved": False,
    }

    def current_slide() -> dict:
        return SLIDES[state["slide_index"]]

    def advance_slide() -> dict:
        now = time.time()
        elapsed = now - state["slide_start_ts"]
        s = current_slide()
        state["history"].append(
            {
                "slide_number": s["number"],
                "title": s["title"],
                "budget_secs": s["minutes"] * 60,
                "elapsed_secs": round(elapsed, 2),
                "over_secs": round(elapsed - s["minutes"] * 60, 2),
            }
        )
        next_idx = state["slide_index"] + 1
        if next_idx >= len(SLIDES):
            # End of talk — save session
            if not state["session_saved"]:
                total_elapsed = now - state["session_start_ts"]
                session = {
                    "date": datetime.now(timezone.utc).isoformat(),
                    "total_elapsed_secs": round(total_elapsed, 2),
                    "total_budget_secs": TOTAL_MINUTES * 60,
                    "slides": state["history"],
                }
                save_session(session)
                state["session_saved"] = True
            return {"status": "done", "slide_index": state["slide_index"]}
        state["slide_index"] = next_idx
        state["slide_start_ts"] = now
        return {"status": "ok", "slide_index": next_idx}

    @app.get("/api/state")
    def api_state() -> JSONResponse:
        now = time.time()
        s = current_slide()
        elapsed = now - state["slide_start_ts"]
        total_elapsed = now - state["session_start_ts"]
        budget = s["minutes"] * 60
        return JSONResponse(
            {
                "slide_index": state["slide_index"],
                "slide": s,
                "elapsed_secs": round(elapsed, 2),
                "budget_secs": budget,
                "remaining_secs": round(budget - elapsed, 2),
                "total_elapsed_secs": round(total_elapsed, 2),
                "total_budget_secs": TOTAL_MINUTES * 60,
                "total_remaining_secs": round(TOTAL_MINUTES * 60 - total_elapsed, 2),
                "is_last": state["slide_index"] == len(SLIDES) - 1,
                "auto_advance": state["auto_advance"],
            }
        )

    @app.post("/api/advance")
    def api_advance() -> JSONResponse:
        result = advance_slide()
        return JSONResponse(result)

    @app.post("/api/reset")
    def api_reset() -> JSONResponse:
        state["slide_index"] = 0
        state["slide_start_ts"] = time.time()
        state["session_start_ts"] = time.time()
        state["history"] = []
        state["session_saved"] = False
        return JSONResponse({"status": "reset"})

    @app.post("/api/auto_advance")
    def api_auto_advance(enabled: bool) -> JSONResponse:
        state["auto_advance"] = enabled
        return JSONResponse({"auto_advance": enabled})

    @app.get("/", response_class=HTMLResponse)
    def presenter_view() -> HTMLResponse:
        return HTMLResponse(HTML_TEMPLATE)

    print(f"\n{BOLD}GTC 2027 Talk Timer — Web Mode{RESET}")
    print(f"  Presenter view: http://localhost:{port}/")
    print(f"  API:            http://localhost:{port}/api/state")
    print(f"  Press Ctrl+C to stop.\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


# ---------------------------------------------------------------------------
# HTML presenter view (dark theme, self-contained)
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>GTC 2027 Talk Timer</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --border: #1e1e2e;
    --text: #e2e8f0;
    --muted: #64748b;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --cyan: #22d3ee;
    --nvidia: #76b900;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ── Top bar ── */
  #topbar {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 10px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-shrink: 0;
  }
  #topbar .logo { color: var(--nvidia); font-weight: 700; font-size: 0.9rem; letter-spacing: 0.05em; }
  #progress-bar-wrap { flex: 1; background: var(--border); border-radius: 4px; height: 6px; }
  #progress-bar { height: 6px; border-radius: 4px; background: var(--nvidia); transition: width 0.5s ease; }
  #slide-counter { color: var(--muted); font-size: 0.85rem; white-space: nowrap; }
  #total-clock { font-size: 0.9rem; color: var(--muted); white-space: nowrap; }

  /* ── Main content ── */
  #main {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 0;
    overflow: hidden;
  }

  /* ── Left panel ── */
  #left {
    padding: 40px 48px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    border-right: 1px solid var(--border);
  }
  #slide-label { color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
  #slide-title {
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1.1;
    color: var(--text);
    margin-bottom: 40px;
    min-height: 120px;
  }

  /* Countdown ring */
  #timer-area { display: flex; align-items: center; gap: 40px; }
  #ring-wrap { position: relative; width: 180px; height: 180px; flex-shrink: 0; }
  #ring-wrap svg { transform: rotate(-90deg); }
  #ring-track { fill: none; stroke: var(--border); stroke-width: 10; }
  #ring-fill { fill: none; stroke-width: 10; stroke-linecap: round; transition: stroke-dashoffset 0.5s linear, stroke 0.5s; }
  #ring-text {
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    pointer-events: none;
  }
  #countdown-display { font-size: 2.4rem; font-weight: 700; letter-spacing: -1px; }
  #countdown-label { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; margin-top: 2px; }

  /* Budget info */
  #budget-info { display: flex; flex-direction: column; gap: 8px; }
  .budget-row { display: flex; flex-direction: column; }
  .budget-row .bval { font-size: 1.5rem; font-weight: 600; }
  .budget-row .blabel { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; }

  /* ── Right panel — speaker notes ── */
  #right {
    background: var(--surface);
    padding: 28px 24px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  #notes-header { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 16px; }
  #notes-list { list-style: none; display: flex; flex-direction: column; gap: 12px; }
  #notes-list li {
    background: var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--text);
    border-left: 3px solid var(--nvidia);
  }

  /* ── Bottom bar — controls ── */
  #bottombar {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 14px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-shrink: 0;
  }
  .btn {
    background: var(--border);
    color: var(--text);
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background 0.15s;
    font-family: inherit;
  }
  .btn:hover { background: #1a1a2e; }
  .btn.primary { background: var(--nvidia); color: #000; border-color: var(--nvidia); font-weight: 700; }
  .btn.primary:hover { background: #66a800; }
  .btn.danger { border-color: var(--red); color: var(--red); }
  .btn.danger:hover { background: #1a0808; }
  #auto-toggle { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.85rem; cursor: pointer; }
  #auto-toggle input { accent-color: var(--nvidia); width: 16px; height: 16px; cursor: pointer; }
  #status-msg { color: var(--muted); font-size: 0.82rem; }

  /* ── Done overlay ── */
  #done-overlay {
    display: none;
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.85);
    z-index: 99;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
  }
  #done-overlay.visible { display: flex; }
  #done-overlay h2 { font-size: 2.4rem; color: var(--green); }
  #done-overlay p { color: var(--muted); font-size: 1.1rem; }
  #done-total { font-size: 1.5rem; color: var(--text); }
</style>
</head>
<body>

<div id="topbar">
  <span class="logo">GTC 2027 · OCI Robot Cloud</span>
  <div id="progress-bar-wrap"><div id="progress-bar" style="width:0%"></div></div>
  <span id="slide-counter">1 / 14</span>
  <span id="total-clock">00:00 / 30:00</span>
</div>

<div id="main">
  <div id="left">
    <div id="slide-label">Slide <span id="snum">1</span></div>
    <div id="slide-title">Loading…</div>
    <div id="timer-area">
      <div id="ring-wrap">
        <svg width="180" height="180" viewBox="0 0 180 180">
          <circle id="ring-track" cx="90" cy="90" r="80"/>
          <circle id="ring-fill" cx="90" cy="90" r="80" stroke="#22c55e"
            stroke-dasharray="502.65" stroke-dashoffset="0"/>
        </svg>
        <div id="ring-text">
          <div id="countdown-display">0:00</div>
          <div id="countdown-label">remaining</div>
        </div>
      </div>
      <div id="budget-info">
        <div class="budget-row">
          <span id="elapsed-val" class="bval" style="color: var(--green)">0:00</span>
          <span class="blabel">elapsed this slide</span>
        </div>
        <div class="budget-row" style="margin-top:8px">
          <span id="budget-val" class="bval" style="color: var(--muted)">0:00</span>
          <span class="blabel">budget this slide</span>
        </div>
      </div>
    </div>
  </div>

  <div id="right">
    <div id="notes-header">Speaker Notes</div>
    <ul id="notes-list"></ul>
  </div>
</div>

<div id="bottombar">
  <button class="btn danger" onclick="resetSession()">↺ Reset</button>
  <div style="display:flex;align-items:center;gap:12px">
    <label id="auto-toggle">
      <input type="checkbox" id="auto-chk" onchange="toggleAuto()"/> Auto-advance
    </label>
    <span id="status-msg"></span>
  </div>
  <button class="btn primary" id="advance-btn" onclick="advance()">Next Slide →</button>
</div>

<div id="done-overlay">
  <h2>Talk Complete!</h2>
  <div id="done-total"></div>
  <p>Session saved to ~/.gtc_rehearsal_log.json</p>
  <button class="btn primary" style="margin-top:16px" onclick="resetSession()">↺ Start New Rehearsal</button>
</div>

<script>
const CIRCUMFERENCE = 2 * Math.PI * 80; // 502.65
let autoInterval = null;
let pollInterval = null;
let lastSlideIndex = -1;

function fmt(secs) {
  const neg = secs < 0;
  const s = Math.abs(secs);
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return (neg ? '-' : '') + m + ':' + String(sec).padStart(2, '0');
}

function fmtMs(secs) {
  const m = Math.floor(Math.abs(secs) / 60), sec = Math.floor(Math.abs(secs) % 60);
  return String(m).padStart(2,'0') + ':' + String(sec).padStart(2,'0');
}

function timeColor(remaining) {
  if (remaining >= 0) return 'var(--green)';
  if (remaining > -30) return 'var(--yellow)';
  return 'var(--red)';
}

function updateUI(data) {
  const { slide, slide_index, elapsed_secs, budget_secs, remaining_secs,
          total_elapsed_secs, total_budget_secs, total_remaining_secs,
          is_last, auto_advance } = data;

  // Detect slide change → update notes
  if (slide_index !== lastSlideIndex) {
    lastSlideIndex = slide_index;
    document.getElementById('snum').textContent = slide.number;
    document.getElementById('slide-title').textContent = slide.title;
    document.getElementById('budget-val').textContent = fmt(budget_secs);

    const ul = document.getElementById('notes-list');
    ul.innerHTML = '';
    slide.notes.forEach(n => {
      const li = document.createElement('li');
      li.textContent = n;
      ul.appendChild(li);
    });

    document.getElementById('slide-counter').textContent = slide.number + ' / 14';
    document.getElementById('advance-btn').textContent = is_last ? 'Finish Talk ✓' : 'Next Slide →';

    // Schedule auto-advance
    if (autoInterval) clearInterval(autoInterval);
    if (auto_advance) {
      autoInterval = setInterval(() => {
        advance();
      }, budget_secs * 1000);
    }
  }

  // Countdown ring
  const pct = Math.max(0, remaining_secs / budget_secs);
  const offset = CIRCUMFERENCE * (1 - pct);
  const ring = document.getElementById('ring-fill');
  ring.style.strokeDashoffset = offset;
  ring.style.stroke = timeColor(remaining_secs);

  // Countdown text
  document.getElementById('countdown-display').textContent = fmt(remaining_secs);
  document.getElementById('countdown-display').style.color = timeColor(remaining_secs);
  document.getElementById('elapsed-val').textContent = fmt(elapsed_secs);
  document.getElementById('elapsed-val').style.color = timeColor(remaining_secs);

  // Top bar
  const progPct = ((slide_index + elapsed_secs / budget_secs) / 14 * 100).toFixed(1);
  document.getElementById('progress-bar').style.width = progPct + '%';
  document.getElementById('total-clock').textContent =
    fmtMs(total_elapsed_secs) + ' / ' + fmtMs(total_budget_secs);
  document.getElementById('total-clock').style.color = timeColor(total_remaining_secs);

  document.getElementById('auto-chk').checked = auto_advance;
}

async function fetchState() {
  try {
    const r = await fetch('/api/state');
    const data = await r.json();
    updateUI(data);
  } catch(e) {}
}

async function advance() {
  const r = await fetch('/api/advance', {method:'POST'});
  const data = await r.json();
  if (data.status === 'done') {
    // Show done overlay
    if (autoInterval) clearInterval(autoInterval);
    if (pollInterval) clearInterval(pollInterval);
    // Fetch final state for total time
    const s = await fetch('/api/state');
    const sd = await s.json();
    const over = sd.total_elapsed_secs - sd.total_budget_secs;
    const sign = over > 0 ? '+' : '';
    document.getElementById('done-total').textContent =
      'Total: ' + fmtMs(sd.total_elapsed_secs) + ' (' + sign + Math.round(over) + 's vs 30:00 budget)';
    document.getElementById('done-overlay').classList.add('visible');
  } else {
    await fetchState();
  }
}

async function resetSession() {
  if (autoInterval) clearInterval(autoInterval);
  document.getElementById('done-overlay').classList.remove('visible');
  await fetch('/api/reset', {method:'POST'});
  lastSlideIndex = -1;
  await fetchState();
  if (!pollInterval) {
    pollInterval = setInterval(fetchState, 500);
  }
}

async function toggleAuto() {
  const enabled = document.getElementById('auto-chk').checked;
  await fetch('/api/auto_advance?enabled=' + enabled, {method:'POST'});
  if (enabled) {
    const r = await fetch('/api/state');
    const data = await r.json();
    if (autoInterval) clearInterval(autoInterval);
    autoInterval = setInterval(advance, data.remaining_secs * 1000);
    document.getElementById('status-msg').textContent = 'Auto-advance: ON';
  } else {
    if (autoInterval) clearInterval(autoInterval);
    autoInterval = null;
    document.getElementById('status-msg').textContent = '';
  }
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (['ArrowRight', ' ', 'Enter'].includes(e.key)) {
    e.preventDefault();
    advance();
  }
});

// Start
fetchState().then(() => {
  pollInterval = setInterval(fetchState, 500);
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GTC 2027 Talk Timer — rehearsal and presenter tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rehearse", action="store_true", help="Interactive terminal rehearsal mode")
    group.add_argument("--web", action="store_true", help="FastAPI web presenter view (port 8057)")
    group.add_argument("--history", action="store_true", help="Show rehearsal history and improvement trend")
    parser.add_argument(
        "--port", type=int, default=8057, help="Port for web mode (default: 8057)"
    )
    parser.add_argument(
        "--auto-advance", action="store_true", default=False,
        help="Start web mode with auto-advance enabled"
    )
    args = parser.parse_args()

    if args.rehearse:
        run_rehearsal()
    elif args.web:
        run_web(port=args.port, auto_advance_default=args.auto_advance)
    elif args.history:
        show_history()


if __name__ == "__main__":
    main()
