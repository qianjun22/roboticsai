#!/usr/bin/env python3
"""
partner_demo_recorder.py — Record, replay, and analyze partner demo sessions.

Records robot observations + actions + metadata for debugging, sharing, and
creating training data from demos shown to potential customers.

Data format: JSON-Lines at /tmp/demo_recordings/<session_id>.jsonl
Each line: {"ts": float, "joint_states": [...], "image_b64": str,
            "action": [...], "phase": str, "success_flag": bool|null}

Session index: /tmp/demo_recordings/index.json

Usage:
    # Record a live session (prints instructions; press Ctrl+C to stop):
    python src/demo/partner_demo_recorder.py --record --session-id demo_acme_001 --partner acme-robotics

    # Record with full metadata:
    python src/demo/partner_demo_recorder.py --record \\
        --session-id demo_acme_001 \\
        --partner acme-robotics \\
        --demo-type live-eval \\
        --robot franka

    # Generate a mock session for testing:
    python src/demo/partner_demo_recorder.py --mock

    # List all recorded sessions:
    python src/demo/partner_demo_recorder.py --list

    # Replay a session at 2x speed:
    python src/demo/partner_demo_recorder.py --replay --session-id demo_acme_001 --speed 2

    # Generate HTML viewer:
    python src/demo/partner_demo_recorder.py --viewer --session-id demo_acme_001 --output /tmp/demo_viewer.html

    # Show per-session analysis:
    python src/demo/partner_demo_recorder.py --analyze --session-id demo_acme_001
"""

import argparse
import base64
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

RECORDINGS_DIR = Path("/tmp/demo_recordings")
INDEX_FILE = RECORDINGS_DIR / "index.json"

PHASES = ["approach", "grasp", "lift", "hold"]

DEMO_TYPES = ["live-eval", "benchmark", "custom"]
ROBOTS = ["franka", "ur5e"]

LIFT_THRESHOLD = 0.78  # metres — z above which we consider cube "lifted"

# Phase step distribution for 60-step mock session
PHASE_STEPS = {"approach": 15, "grasp": 10, "lift": 25, "hold": 10}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _ensure_recordings_dir() -> None:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> Dict[str, Any]:
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {"sessions": []}


def _save_index(index: Dict[str, Any]) -> None:
    _ensure_recordings_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def _session_path(session_id: str) -> Path:
    return RECORDINGS_DIR / f"{session_id}.jsonl"


def _load_session(session_id: str) -> List[Dict[str, Any]]:
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {path}")
    frames = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_index_entry(meta: Dict[str, Any]) -> None:
    index = _load_index()
    sessions = index.get("sessions", [])
    # Replace existing entry if session_id matches
    sessions = [s for s in sessions if s.get("session_id") != meta["session_id"]]
    sessions.append(meta)
    sessions.sort(key=lambda s: s.get("start_time", ""))
    index["sessions"] = sessions
    _save_index(index)


def _phase_for_step(step: int) -> str:
    """Map a 0-based step index to a phase name using PHASE_STEPS distribution."""
    cumulative = 0
    for phase, count in PHASE_STEPS.items():
        cumulative += count
        if step < cumulative:
            return phase
    return "hold"


def _mock_joint_states(step: int, n_joints: int = 7) -> List[float]:
    """Smooth sinusoidal joint states for a convincing mock trajectory."""
    t = step / 60.0
    return [round(math.sin(t * (i + 1) * 0.8) * 0.4, 4) for i in range(n_joints)]


def _mock_action(step: int, n_joints: int = 7) -> List[float]:
    t = step / 60.0
    return [round(math.cos(t * (i + 1) * 0.7) * 0.05, 4) for i in range(n_joints)]


def _mock_cube_z(step: int) -> float:
    """Cube z trajectory: resting → rise during lift phase → hold."""
    # Approach (0-14): resting on table ~0.72
    if step < 15:
        return round(0.720 + step * 0.001, 4)
    # Grasp (15-24): slight movement from gripper closing
    if step < 25:
        return round(0.722 + (step - 15) * 0.002, 4)
    # Lift (25-49): smooth rise from 0.742 to 0.880
    if step < 50:
        frac = (step - 25) / 24.0
        return round(0.742 + frac * (0.880 - 0.742), 4)
    # Hold (50-59): steady at 0.880
    return round(0.880 + (step - 50) * 0.001, 4)


def _tiny_placeholder_image() -> str:
    """Return a minimal 1x1 grey PNG as base64 (no external deps)."""
    # 1x1 grey PNG bytes (hardcoded)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x00"
        b"\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return base64.b64encode(png_bytes).decode()


# ── Record ────────────────────────────────────────────────────────────────────


def cmd_record(
    session_id: str,
    partner_id: str,
    demo_type: str = "live-eval",
    robot: str = "franka",
) -> None:
    """
    Interactive record mode. In a real deployment this would receive frames from
    the robot inference server (port 8001) or data collection API (port 8003).
    Here it simulates frame-by-frame capture via stdin so the recorder can be
    driven manually or piped from another process.

    Each line of stdin should be JSON matching the frame schema, or press
    Ctrl+C / send EOF to stop recording.

    Frame JSON schema:
        {
          "joint_states": [float, ...],   # 7 joints
          "image_b64":    str,            # base64 PNG/JPEG
          "action":       [float, ...],   # 7-dim action vector
          "phase":        str,            # approach|grasp|lift|hold
          "success_flag": bool|null       # null until terminal step
        }
    """
    _ensure_recordings_dir()
    path = _session_path(session_id)
    if path.exists():
        print(f"[recorder] WARNING: overwriting existing session {session_id}")

    start_ts = time.time()
    start_iso = _now_iso()
    n_steps = 0
    last_success: Optional[bool] = None
    expert_interventions = 0

    print(f"[recorder] Recording session '{session_id}' → {path}")
    print(f"[recorder] Partner: {partner_id} | Demo: {demo_type} | Robot: {robot}")
    print("[recorder] Paste frame JSON per line, or press Ctrl+C to finish.\n")

    with open(path, "w") as fout:
        try:
            for raw_line in sys.stdin:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    frame = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    print(f"[recorder] Bad JSON, skipping: {exc}")
                    continue

                ts = time.time()
                record = {
                    "ts": ts,
                    "joint_states": frame.get("joint_states", []),
                    "image_b64": frame.get("image_b64", ""),
                    "action": frame.get("action", []),
                    "phase": frame.get("phase", "approach"),
                    "success_flag": frame.get("success_flag", None),
                }
                if frame.get("expert_intervention"):
                    expert_interventions += 1

                fout.write(json.dumps(record) + "\n")
                fout.flush()
                n_steps += 1
                last_success = record["success_flag"]
                print(
                    f"[recorder] step={n_steps:4d}  phase={record['phase']:<8s}  "
                    f"success={str(last_success):<5s}",
                    end="\r",
                )
        except KeyboardInterrupt:
            print("\n[recorder] Interrupted by user.")

    end_iso = _now_iso()
    duration = time.time() - start_ts

    meta = {
        "session_id": session_id,
        "partner_id": partner_id,
        "demo_type": demo_type,
        "robot": robot,
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_s": round(duration, 2),
        "success": bool(last_success) if last_success is not None else False,
        "n_steps": n_steps,
        "expert_interventions": expert_interventions,
        "recording_path": str(path),
    }

    _upsert_index_entry(meta)
    print(f"\n[recorder] Done. {n_steps} steps saved → {path}")
    print(f"[recorder] Metadata: {json.dumps(meta, indent=2)}")


# ── Replay ────────────────────────────────────────────────────────────────────


def cmd_replay(session_id: str, speed: float = 1.0) -> None:
    """
    Play back a recorded session to terminal at the requested speed multiplier.
    Also saves a plain-text replay report alongside the jsonl file.
    """
    frames = _load_session(session_id)
    if not frames:
        print(f"[replay] Session '{session_id}' is empty.")
        return

    index = _load_index()
    meta = next(
        (s for s in index.get("sessions", []) if s["session_id"] == session_id),
        {},
    )

    print(f"\n{'='*60}")
    print(f"  REPLAY: {session_id}")
    print(f"  Partner:  {meta.get('partner_id', 'unknown')}")
    print(f"  Robot:    {meta.get('robot', 'unknown')}")
    print(f"  Demo:     {meta.get('demo_type', 'unknown')}")
    print(f"  Steps:    {len(frames)}")
    print(f"  Speed:    {speed}x")
    print(f"{'='*60}\n")

    report_lines = [
        f"Replay Report — {session_id}",
        f"Partner: {meta.get('partner_id', 'unknown')}",
        f"Robot:   {meta.get('robot', 'unknown')}",
        f"Steps:   {len(frames)}",
        "",
        f"{'Step':>5}  {'Time(s)':>8}  {'Phase':<10}  {'Action[0]':>10}  {'Success'}",
        "-" * 55,
    ]

    base_ts = frames[0]["ts"]
    for i, frame in enumerate(frames):
        elapsed = frame["ts"] - base_ts
        phase = frame.get("phase", "?")
        action0 = frame.get("action", [0])[0] if frame.get("action") else 0.0
        success = str(frame.get("success_flag"))

        line = (
            f"{i+1:5d}  {elapsed:8.3f}  {phase:<10s}  {action0:10.4f}  {success}"
        )
        report_lines.append(line)

        print(
            f"  step={i+1:4d}  t={elapsed:7.3f}s  phase={phase:<8s}  "
            f"action[0]={action0:+.4f}  success={success}"
        )

        if i < len(frames) - 1:
            dt = frames[i + 1]["ts"] - frames[i]["ts"]
            sleep_s = dt / max(speed, 0.01)
            if 0 < sleep_s < 5.0:  # guard against huge gaps
                time.sleep(sleep_s)

    report_path = RECORDINGS_DIR / f"{session_id}_replay_report.txt"
    report_lines.append("")
    report_lines.append(f"Generated: {_now_iso()}")
    report_path.write_text("\n".join(report_lines))

    print(f"\n[replay] Replay complete. Report saved → {report_path}")


# ── List ──────────────────────────────────────────────────────────────────────


def cmd_list() -> None:
    """Print all sessions in the index."""
    index = _load_index()
    sessions = index.get("sessions", [])
    if not sessions:
        print("[list] No recorded sessions found.")
        return

    header = (
        f"{'Session ID':<30}  {'Partner':<20}  {'Demo Type':<12}  "
        f"{'Robot':<8}  {'Steps':>6}  {'Success':<8}  {'Start Time'}"
    )
    print(f"\n{header}")
    print("-" * len(header))
    for s in sessions:
        print(
            f"{s.get('session_id','?'):<30}  "
            f"{s.get('partner_id','?'):<20}  "
            f"{s.get('demo_type','?'):<12}  "
            f"{s.get('robot','?'):<8}  "
            f"{s.get('n_steps',0):>6}  "
            f"{str(s.get('success',False)):<8}  "
            f"{s.get('start_time','?')}"
        )
    print(f"\nTotal: {len(sessions)} session(s)  |  Index: {INDEX_FILE}\n")


# ── Analyze ───────────────────────────────────────────────────────────────────


def _analyze_session(session_id: str) -> Dict[str, Any]:
    """Compute per-session statistics from raw frames."""
    frames = _load_session(session_id)

    phase_counts: Dict[str, int] = {p: 0 for p in PHASES}
    expert_count = 0
    cube_z_traj: List[float] = []
    cube_z_at_end: Optional[float] = None
    peak_cube_z: float = 0.0

    # We extract cube_z from joint_states[6] as a proxy (last joint = z offset)
    # In real data this would come from the observation dict.
    for frame in frames:
        phase = frame.get("phase", "approach")
        if phase in phase_counts:
            phase_counts[phase] += 1

        if frame.get("expert_intervention"):
            expert_count += 1

        js = frame.get("joint_states", [])
        if js:
            # Last element treated as cube_z proxy
            z = round(float(js[-1]) + 0.75, 4)  # offset to realistic range
        else:
            z = 0.0
        cube_z_traj.append(z)

    if cube_z_traj:
        cube_z_at_end = cube_z_traj[-1]
        peak_cube_z = max(cube_z_traj)

    total_steps = len(frames)
    success_steps = sum(1 for f in frames if f.get("success_flag") is True)
    final_success = frames[-1].get("success_flag", False) if frames else False

    return {
        "session_id": session_id,
        "total_steps": total_steps,
        "phase_breakdown": phase_counts,
        "expert_interventions": expert_count,
        "cube_z_trajectory": cube_z_traj,
        "cube_z_at_end": cube_z_at_end,
        "peak_cube_z": peak_cube_z,
        "lift_achieved": peak_cube_z >= LIFT_THRESHOLD,
        "success_steps": success_steps,
        "final_success": final_success,
    }


def cmd_analyze(session_id: str) -> None:
    """Print per-session analysis to terminal."""
    stats = _analyze_session(session_id)

    print(f"\n{'='*50}")
    print(f"  ANALYSIS: {session_id}")
    print(f"{'='*50}")
    print(f"  Total steps:        {stats['total_steps']}")
    print(f"  Final success:      {stats['final_success']}")
    print(f"  Lift achieved:      {stats['lift_achieved']}  (threshold={LIFT_THRESHOLD}m)")
    print(f"  Peak cube_z:        {stats['peak_cube_z']:.4f} m")
    print(f"  Cube_z at end:      {stats['cube_z_at_end']}")
    print(f"  Expert interventions: {stats['expert_interventions']}")
    print(f"\n  Phase breakdown:")
    for phase, count in stats["phase_breakdown"].items():
        bar = "#" * min(count, 40)
        pct = (count / max(stats["total_steps"], 1)) * 100
        print(f"    {phase:<10s} {count:4d} steps  ({pct:5.1f}%)  {bar}")
    print()


# ── HTML Viewer ───────────────────────────────────────────────────────────────


def _build_svg_chart(z_traj: List[float], width: int = 600, height: int = 180) -> str:
    """Build an inline SVG line chart of cube_z over steps."""
    if not z_traj:
        return "<svg><text x='10' y='20' fill='#888'>No data</text></svg>"

    n = len(z_traj)
    z_min = min(z_traj) - 0.02
    z_max = max(z_traj) + 0.02
    z_range = z_max - z_min or 0.01

    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 35
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def px(i: int) -> float:
        return pad_l + (i / max(n - 1, 1)) * plot_w

    def py(z: float) -> float:
        return pad_t + (1.0 - (z - z_min) / z_range) * plot_h

    # Polyline points
    points = " ".join(f"{px(i):.1f},{py(z):.1f}" for i, z in enumerate(z_traj))

    # Threshold line
    th_y = py(LIFT_THRESHOLD)
    threshold_line = (
        f'<line x1="{pad_l}" y1="{th_y:.1f}" x2="{pad_l + plot_w}" y2="{th_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4 3"/>'
        f'<text x="{pad_l + plot_w + 2}" y="{th_y + 4:.1f}" '
        f'fill="#f59e0b" font-size="9">lift</text>'
    )

    # Y-axis labels
    y_labels = ""
    for tick in [z_min + z_range * i / 4 for i in range(5)]:
        y_pos = py(tick)
        y_labels += (
            f'<text x="{pad_l - 4}" y="{y_pos + 3:.1f}" '
            f'fill="#9ca3af" font-size="9" text-anchor="end">{tick:.3f}</text>'
            f'<line x1="{pad_l - 2}" y1="{y_pos:.1f}" x2="{pad_l}" y2="{y_pos:.1f}" '
            f'stroke="#4b5563"/>'
        )

    # X-axis labels
    x_labels = ""
    for tick_i in range(0, n, max(n // 6, 1)):
        x_pos = px(tick_i)
        x_labels += (
            f'<text x="{x_pos:.1f}" y="{pad_t + plot_h + 14}" '
            f'fill="#9ca3af" font-size="9" text-anchor="middle">{tick_i}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1f2937;border-radius:6px">
  <rect width="{width}" height="{height}" fill="#1f2937" rx="6"/>
  <!-- grid -->
  {y_labels}
  {x_labels}
  <!-- axes -->
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#4b5563"/>
  <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#4b5563"/>
  <!-- threshold -->
  {threshold_line}
  <!-- trajectory -->
  <polyline points="{points}" fill="none" stroke="#34d399" stroke-width="2" stroke-linejoin="round"/>
  <!-- axis labels -->
  <text x="{pad_l // 2}" y="{pad_t + plot_h // 2}" fill="#9ca3af" font-size="10"
        transform="rotate(-90 {pad_l // 2} {pad_t + plot_h // 2})" text-anchor="middle">cube_z (m)</text>
  <text x="{pad_l + plot_w // 2}" y="{height - 2}" fill="#9ca3af" font-size="10" text-anchor="middle">step</text>
</svg>"""
    return svg


def _build_phase_timeline(frames: List[Dict[str, Any]], width: int = 600) -> str:
    """Build a coloured phase timeline bar as inline SVG."""
    if not frames:
        return ""

    PHASE_COLORS = {
        "approach": "#60a5fa",  # blue
        "grasp": "#f59e0b",     # amber
        "lift": "#34d399",      # green
        "hold": "#a78bfa",      # purple
    }

    n = len(frames)
    bar_h = 28
    label_h = 16
    total_h = bar_h + label_h + 10

    segments = []
    i = 0
    while i < n:
        phase = frames[i].get("phase", "approach")
        j = i
        while j < n and frames[j].get("phase", "approach") == phase:
            j += 1
        x = round((i / n) * width, 1)
        w = round(((j - i) / n) * width, 1)
        color = PHASE_COLORS.get(phase, "#6b7280")
        mid_x = x + w / 2
        segments.append(
            f'<rect x="{x}" y="0" width="{w}" height="{bar_h}" fill="{color}" opacity="0.85"/>'
        )
        if w > 30:
            segments.append(
                f'<text x="{mid_x:.1f}" y="{bar_h // 2 + 5}" fill="#111827" '
                f'font-size="11" font-weight="bold" text-anchor="middle">{phase}</text>'
            )
        i = j

    # Legend
    legend = ""
    lx = 4
    for phase, color in PHASE_COLORS.items():
        legend += (
            f'<rect x="{lx}" y="{bar_h + 4}" width="10" height="10" fill="{color}"/>'
            f'<text x="{lx + 13}" y="{bar_h + 13}" fill="#9ca3af" font-size="9">{phase}</text>'
        )
        lx += 65

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" '
        f'style="background:#111827;border-radius:4px">'
        + "".join(segments)
        + legend
        + "</svg>"
    )
    return svg


def cmd_viewer(session_id: str, output_path: str) -> None:
    """Generate a standalone dark-theme HTML viewer for a session."""
    frames = _load_session(session_id)
    stats = _analyze_session(session_id)

    index = _load_index()
    meta = next(
        (s for s in index.get("sessions", []) if s["session_id"] == session_id),
        {},
    )

    cube_z_traj = stats["cube_z_trajectory"]
    svg_chart = _build_svg_chart(cube_z_traj)
    phase_timeline = _build_phase_timeline(frames)

    # Build frames JS array (exclude image_b64 to keep HTML small)
    frames_js = []
    base_ts = frames[0]["ts"] if frames else 0
    for f in frames:
        frames_js.append({
            "t": round(f["ts"] - base_ts, 3),
            "phase": f.get("phase", ""),
            "action": f.get("action", []),
            "success": f.get("success_flag"),
            "js": f.get("joint_states", []),
        })
    frames_json = json.dumps(frames_js)

    phase_counts_json = json.dumps(stats["phase_breakdown"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Demo Viewer — {session_id}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{font-size:1.4rem;font-weight:700;color:#f8fafc;margin-bottom:4px}}
  .sub{{color:#94a3b8;font-size:0.85rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
  .card{{background:#1e293b;border-radius:8px;padding:16px}}
  .card h2{{font-size:0.9rem;font-weight:600;color:#94a3b8;text-transform:uppercase;
            letter-spacing:.05em;margin-bottom:12px}}
  .stat-row{{display:flex;justify-content:space-between;padding:4px 0;
             border-bottom:1px solid #334155;font-size:0.88rem}}
  .stat-row:last-child{{border-bottom:none}}
  .val{{color:#34d399;font-weight:600}}
  .val.bad{{color:#f87171}}
  .val.warn{{color:#fbbf24}}
  .chart-wrap{{margin-bottom:20px}}
  .chart-wrap h2{{font-size:0.9rem;font-weight:600;color:#94a3b8;
                  text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}}
  .timeline-wrap{{margin-bottom:20px}}
  .timeline-wrap h2{{font-size:0.9rem;font-weight:600;color:#94a3b8;
                     text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}}
  /* Replay player */
  .player{{background:#1e293b;border-radius:8px;padding:16px;margin-bottom:20px}}
  .player h2{{font-size:0.9rem;font-weight:600;color:#94a3b8;
              text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
  .controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}}
  button{{background:#334155;color:#e2e8f0;border:none;border-radius:6px;
          padding:6px 14px;cursor:pointer;font-size:0.85rem;transition:background .15s}}
  button:hover{{background:#475569}}
  button.active{{background:#0ea5e9;color:#fff}}
  #progress-bar{{width:100%;height:6px;background:#334155;border-radius:3px;cursor:pointer}}
  #progress-fill{{height:6px;background:#34d399;border-radius:3px;width:0%;
                  transition:width .1s linear}}
  #step-display{{font-size:0.85rem;color:#94a3b8;min-width:120px}}
  #frame-detail{{background:#0f172a;border-radius:6px;padding:12px;font-size:0.8rem;
                 font-family:monospace;color:#94a3b8;white-space:pre-wrap;
                 max-height:140px;overflow-y:auto}}
  .phase-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.78rem;
                font-weight:600;text-transform:uppercase}}
  .phase-approach{{background:#1e40af;color:#93c5fd}}
  .phase-grasp{{background:#92400e;color:#fcd34d}}
  .phase-lift{{background:#064e3b;color:#6ee7b7}}
  .phase-hold{{background:#4c1d95;color:#c4b5fd}}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Partner Demo Viewer</h1>
<div class="sub">Session: <strong>{session_id}</strong> &nbsp;|&nbsp;
  Partner: <strong>{meta.get('partner_id','unknown')}</strong> &nbsp;|&nbsp;
  Robot: <strong>{meta.get('robot','unknown')}</strong> &nbsp;|&nbsp;
  Demo type: <strong>{meta.get('demo_type','unknown')}</strong> &nbsp;|&nbsp;
  Generated: {_now_iso()}
</div>

<div class="grid">
  <div class="card">
    <h2>Session Metadata</h2>
    <div class="stat-row"><span>Session ID</span><span class="val">{session_id}</span></div>
    <div class="stat-row"><span>Start time</span><span class="val">{meta.get('start_time','?')}</span></div>
    <div class="stat-row"><span>Duration</span><span class="val">{meta.get('duration_s','?')} s</span></div>
    <div class="stat-row"><span>Total steps</span><span class="val">{stats['total_steps']}</span></div>
    <div class="stat-row"><span>Expert interventions</span>
      <span class="val {'bad' if stats['expert_interventions'] > 0 else ''}">{stats['expert_interventions']}</span></div>
    <div class="stat-row"><span>Final success</span>
      <span class="val {'bad' if not stats['final_success'] else ''}">{stats['final_success']}</span></div>
  </div>
  <div class="card">
    <h2>Key Metrics</h2>
    <div class="stat-row"><span>Peak cube_z</span>
      <span class="val">{stats['peak_cube_z']:.4f} m</span></div>
    <div class="stat-row"><span>Cube_z at end</span>
      <span class="val">{stats['cube_z_at_end']}</span></div>
    <div class="stat-row"><span>Lift achieved (≥{LIFT_THRESHOLD} m)</span>
      <span class="val {'bad' if not stats['lift_achieved'] else ''}">{stats['lift_achieved']}</span></div>
    <div class="stat-row"><span>Phase: approach</span>
      <span class="val">{stats['phase_breakdown'].get('approach',0)} steps</span></div>
    <div class="stat-row"><span>Phase: grasp</span>
      <span class="val">{stats['phase_breakdown'].get('grasp',0)} steps</span></div>
    <div class="stat-row"><span>Phase: lift</span>
      <span class="val">{stats['phase_breakdown'].get('lift',0)} steps</span></div>
    <div class="stat-row"><span>Phase: hold</span>
      <span class="val">{stats['phase_breakdown'].get('hold',0)} steps</span></div>
  </div>
</div>

<div class="chart-wrap">
  <h2>Cube Z Trajectory</h2>
  {svg_chart}
</div>

<div class="timeline-wrap">
  <h2>Phase Timeline</h2>
  {phase_timeline}
</div>

<div class="player">
  <h2>Replay Controls</h2>
  <div class="controls">
    <button id="btn-play" onclick="playerPlay()">&#9654; Play</button>
    <button id="btn-pause" onclick="playerPause()">&#9646;&#9646; Pause</button>
    <button id="btn-reset" onclick="playerReset()">&#8635; Reset</button>
    <span style="margin-left:8px;color:#94a3b8;font-size:0.85rem">Speed:</span>
    <button onclick="setSpeed(0.5)" id="s05">0.5x</button>
    <button onclick="setSpeed(1)" id="s1" class="active">1x</button>
    <button onclick="setSpeed(2)" id="s2">2x</button>
    <button onclick="setSpeed(4)" id="s4">4x</button>
  </div>
  <div id="progress-bar" onclick="playerSeek(event)">
    <div id="progress-fill"></div>
  </div>
  <br/>
  <div id="step-display">Step 0 / {stats['total_steps']}</div>
  <br/>
  <div id="frame-detail">Press Play to start replay...</div>
</div>

<script>
const FRAMES = {frames_json};
const TOTAL = FRAMES.length;
let cur = 0, speed = 1, playing = false, timer = null;

function renderFrame(i) {{
  if (i < 0 || i >= TOTAL) return;
  cur = i;
  const f = FRAMES[i];
  const pct = TOTAL > 1 ? (i / (TOTAL - 1) * 100) : 0;
  document.getElementById('progress-fill').style.width = pct.toFixed(1) + '%';
  document.getElementById('step-display').textContent =
    'Step ' + (i + 1) + ' / ' + TOTAL + '  |  t=' + f.t.toFixed(3) + 's  |  phase=' + f.phase;
  const phaseClass = 'phase-' + f.phase;
  const badge = '<span class="phase-badge ' + phaseClass + '">' + f.phase + '</span>';
  document.getElementById('frame-detail').innerHTML =
    'Phase:   ' + badge + '\\n' +
    'Success: ' + f.success + '\\n' +
    'Action:  [' + (f.action || []).map(v => v.toFixed(4)).join(', ') + ']\\n' +
    'Joints:  [' + (f.js || []).map(v => v.toFixed(4)).join(', ') + ']';
}}

function tick() {{
  if (!playing) return;
  if (cur >= TOTAL - 1) {{ playerPause(); return; }}
  renderFrame(cur + 1);
  const dt = cur + 1 < TOTAL ? (FRAMES[cur].t - (cur > 0 ? FRAMES[cur-1].t : 0)) : 0.05;
  const delay = Math.max((dt || 0.05) / speed * 1000, 20);
  timer = setTimeout(tick, delay);
}}

function playerPlay() {{
  if (playing) return;
  if (cur >= TOTAL - 1) cur = 0;
  playing = true;
  tick();
}}

function playerPause() {{
  playing = false;
  if (timer) clearTimeout(timer);
}}

function playerReset() {{
  playerPause();
  renderFrame(0);
}}

function playerSeek(e) {{
  const bar = document.getElementById('progress-bar');
  const rect = bar.getBoundingClientRect();
  const frac = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
  renderFrame(Math.round(frac * (TOTAL - 1)));
}}

function setSpeed(s) {{
  speed = s;
  ['0.5','1','2','4'].forEach(v => {{
    const btn = document.getElementById('s' + v.replace('.',''));
    if (btn) btn.classList.remove('active');
  }});
  const id = 's' + String(s).replace('.','');
  const b = document.getElementById(id);
  if (b) b.classList.add('active');
}}

renderFrame(0);
</script>
</body>
</html>"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"[viewer] HTML viewer saved → {out}")
    print(f"[viewer] Open with:  open {out}")


# ── Mock ──────────────────────────────────────────────────────────────────────


def cmd_mock(
    session_id: str = "demo_mock_001",
    partner_id: str = "acme-robotics",
    demo_type: str = "live-eval",
    robot: str = "franka",
    n_steps: int = 60,
) -> str:
    """Generate a realistic 60-step mock demo session and write it to disk."""
    _ensure_recordings_dir()
    path = _session_path(session_id)
    placeholder_img = _tiny_placeholder_image()

    start_ts = time.time() - n_steps * 0.1  # back-date timestamps

    with open(path, "w") as fout:
        for step in range(n_steps):
            phase = _phase_for_step(step)
            cube_z = _mock_cube_z(step)
            joint_states = _mock_joint_states(step)
            # Embed cube_z signal in last joint for analysis extraction
            joint_states[-1] = round(cube_z - 0.75, 4)
            action = _mock_action(step)
            is_terminal = step == n_steps - 1
            success_flag = True if is_terminal else None

            frame = {
                "ts": start_ts + step * 0.1,
                "joint_states": joint_states,
                "image_b64": placeholder_img,
                "action": action,
                "phase": phase,
                "success_flag": success_flag,
            }
            fout.write(json.dumps(frame) + "\n")

    meta = {
        "session_id": session_id,
        "partner_id": partner_id,
        "demo_type": demo_type,
        "robot": robot,
        "start_time": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(),
        "end_time": _now_iso(),
        "duration_s": round(n_steps * 0.1, 2),
        "success": True,
        "n_steps": n_steps,
        "expert_interventions": 0,
        "recording_path": str(path),
    }
    _upsert_index_entry(meta)

    print(f"[mock] Created mock session '{session_id}' ({n_steps} steps) → {path}")
    return session_id


# ── CLI ───────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Partner Demo Recorder — record, replay, and analyze robot demo sessions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--record", action="store_true", help="Record a new session (reads frames from stdin)")
    modes.add_argument("--replay", action="store_true", help="Replay a recorded session")
    modes.add_argument("--list", action="store_true", help="List all recorded sessions")
    modes.add_argument("--viewer", action="store_true", help="Generate standalone HTML viewer")
    modes.add_argument("--analyze", action="store_true", help="Print per-session analysis")
    modes.add_argument("--mock", action="store_true", help="Generate a mock session for testing")

    p.add_argument("--session-id", default="demo_mock_001", help="Session identifier")
    p.add_argument("--partner", default="unknown-partner", help="Partner organisation ID")
    p.add_argument("--demo-type", default="live-eval", choices=DEMO_TYPES,
                   help="Demo type (default: live-eval)")
    p.add_argument("--robot", default="franka", choices=ROBOTS,
                   help="Robot platform (default: franka)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Replay speed multiplier: 0.5, 1, 2, 4 (default: 1)")
    p.add_argument("--output", default="/tmp/demo_viewer.html",
                   help="Output path for --viewer (default: /tmp/demo_viewer.html)")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.record:
        cmd_record(
            session_id=args.session_id,
            partner_id=args.partner,
            demo_type=args.demo_type,
            robot=args.robot,
        )
    elif args.replay:
        cmd_replay(session_id=args.session_id, speed=args.speed)
    elif args.list:
        cmd_list()
    elif args.viewer:
        cmd_viewer(session_id=args.session_id, output_path=args.output)
    elif args.analyze:
        cmd_analyze(session_id=args.session_id)
    elif args.mock:
        sid = cmd_mock(
            session_id=args.session_id,
            partner_id=args.partner,
            demo_type=args.demo_type,
            robot=args.robot,
        )
        print(f"[mock] Run analysis:  python src/demo/partner_demo_recorder.py --analyze --session-id {sid}")
        print(f"[mock] Generate HTML: python src/demo/partner_demo_recorder.py --viewer --session-id {sid} --output /tmp/demo_viewer.html")


if __name__ == "__main__":
    main()
