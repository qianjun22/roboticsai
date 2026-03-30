"""
GTC 2027 Talk Rehearsal Recorder

Records and analyzes GTC talk rehearsal sessions. Tracks per-slide timing,
confidence ratings, Q&A practice, and improvement across rehearsals.
Target: 30-min talk within ±2 min (hard cap: 33 min with Q&A buffer).
"""

import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SlideRecord:
    slide_num: int
    title: str
    target_duration_s: int
    actual_duration_s: int
    confidence: int          # 1-5
    notes: str = ""
    demo_step: bool = False


@dataclass
class QARecord:
    question: str
    answer_quality: int      # 1-5
    answer_duration_s: int
    notes: str = ""


@dataclass
class RehearsalSession:
    session_id: int
    date: date
    total_duration_s: int
    slides: List[SlideRecord]
    qa: List[QARecord]
    overall_confidence: float
    identified_risks: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Slide target definitions (matches gtc_talk_timer.py)
# Total: 1980s = 33 min (includes Q&A buffer)
# ---------------------------------------------------------------------------

SLIDE_TARGETS = [
    (1,  "Title + Hook",      90,  False),
    (2,  "The Problem",       120, False),
    (3,  "Our Solution",      150, False),
    (4,  "Live Demo Setup",   60,  True),
    (5,  "Live Demo Step 1",  120, True),
    (6,  "Live Demo Step 2",  120, True),
    (7,  "Live Demo Step 3",  120, True),
    (8,  "Benchmark Results", 180, False),
    (9,  "Cost vs AWS",       120, False),
    (10, "Architecture",      150, False),
    (11, "Customer Roadmap",  120, False),
    (12, "GTC Demo Live",     180, True),
    (13, "The Ask",           90,  False),
    (14, "Q&A",               300, False),
]

TARGET_TALK_S   = 1800   # 30 min (no Q&A)
TARGET_TOTAL_S  = 1980   # 33 min (with Q&A buffer)
TOLERANCE_S     = 120    # ±2 min


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _jitter(base: int, factor: float, rng_seed: int) -> int:
    """Deterministic pseudo-jitter around base (no random import)."""
    v = math.sin(rng_seed * 2.9 + base * 1.3) * 0.5 + 0.5   # 0..1
    return max(10, int(base * (1 + factor * (v - 0.5) * 2)))


def generate_mock_sessions() -> List[RehearsalSession]:
    """Return 5 rehearsal sessions showing clear improvement over time."""
    sessions: List[RehearsalSession] = []
    base_date = date(2027, 2, 1)

    # Per-session tuning: (overtime_factor, confidence_base, qa_quality_base)
    session_params = [
        (0.40, 1.8, 2.0),   # S1: very over, low confidence
        (0.28, 2.5, 2.5),   # S2: over, moderate
        (0.18, 3.2, 3.0),   # S3: slightly over, improving
        (0.10, 3.8, 3.8),   # S4: near target, good
        (0.05, 4.2, 4.3),   # S5: on target, strong
    ]

    qa_questions = [
        "How does OCI pricing compare to AWS SageMaker at scale?",
        "What's your latency SLA for inference in production?",
        "Can this run on non-NVIDIA hardware?",
        "How do you handle sim-to-real transfer gaps?",
        "What's the minimum data needed for a new robot embodiment?",
        "Is the fine-tuning pipeline open-source?",
    ]

    for idx, (over_f, conf_base, qa_base) in enumerate(session_params):
        sid = idx + 1
        sess_date = base_date + timedelta(days=idx * 4)

        slides: List[SlideRecord] = []
        total_s = 0
        for num, title, target, demo in SLIDE_TARGETS:
            seed = sid * 100 + num
            actual = _jitter(target, over_f, seed)
            conf_raw = conf_base + math.sin(seed) * 0.8
            conf = max(1, min(5, round(conf_raw)))
            is_late = actual > target + 15
            notes = "Ran long — cut anecdote" if is_late else ""
            slides.append(SlideRecord(num, title, target, actual, conf, notes, demo))
            total_s += actual

        qa_records: List[QARecord] = []
        n_qa = 2 + idx   # more Q&A attempts in later sessions
        for qi in range(n_qa):
            q = qa_questions[qi % len(qa_questions)]
            aq = max(1, min(5, round(qa_base + math.sin(qi * sid) * 0.7)))
            dur = _jitter(60, 0.4, qi * sid + 7)
            qa_records.append(QARecord(q, aq, dur))

        risks: List[str] = []
        if over_f > 0.15:
            risks.append("Demo slides consistently over target")
        if conf_base < 3:
            risks.append("Low confidence on Benchmark Results slide")
        if sid <= 3:
            risks.append("Q&A coverage too shallow — add more practice questions")

        sessions.append(RehearsalSession(
            session_id=sid,
            date=sess_date,
            total_duration_s=total_s,
            slides=slides,
            qa=qa_records,
            overall_confidence=round(conf_base + 0.1, 1),
            identified_risks=risks,
        ))

    return sessions


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_sessions(sessions: List[RehearsalSession]) -> dict:
    n_slides = len(SLIDE_TARGETS)
    slide_titles = [t for _, t, _, _ in SLIDE_TARGETS]
    slide_targets = [t for _, _, t, _ in SLIDE_TARGETS]

    # Per-session total duration trend
    duration_trend = [s.total_duration_s for s in sessions]

    # Per-slide avg actual duration across sessions (shape: [slide][session])
    slide_matrix = []
    for si in range(n_slides):
        row = [s.slides[si].actual_duration_s for s in sessions]
        slide_matrix.append(row)

    # Confidence trend per session
    conf_trend = [s.overall_confidence for s in sessions]

    # Worst slides: largest avg overtime across all sessions
    slide_overtime = []
    for si in range(n_slides):
        avg_actual = sum(slide_matrix[si]) / len(sessions)
        delta = avg_actual - slide_targets[si]
        slide_overtime.append((delta, slide_titles[si], si + 1, slide_targets[si], avg_actual))
    slide_overtime.sort(reverse=True)

    # Improvement rate: % reduction in total time from session 1 to last
    first_t = duration_trend[0]
    last_t = duration_trend[-1]
    improvement_pct = round((first_t - last_t) / first_t * 100, 1) if first_t else 0

    # Q&A coverage
    all_questions = []
    for s in sessions:
        for qa in s.qa:
            if qa.question not in all_questions:
                all_questions.append(qa.question)

    return {
        "duration_trend": duration_trend,
        "slide_matrix": slide_matrix,
        "slide_titles": slide_titles,
        "slide_targets": slide_targets,
        "conf_trend": conf_trend,
        "worst_slides": slide_overtime[:5],
        "improvement_pct": improvement_pct,
        "qa_questions_covered": all_questions,
        "session_dates": [str(s.date) for s in sessions],
    }


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _fmt_mm_ss(total_s: int) -> str:
    return f"{total_s // 60}m {total_s % 60:02d}s"


def render_html(sessions: List[RehearsalSession], analysis: dict) -> str:
    n_sessions = len(sessions)
    session_labels = [f"S{s.session_id}<br>{s.date.strftime('%b %d')}" for s in sessions]
    x_step = 120
    chart_w = 80 + n_sessions * x_step
    chart_h = 240

    # --- SVG 1: Total duration trend ---
    max_dur = max(analysis["duration_trend"]) + 120
    min_dur = max(0, TARGET_TALK_S - 300)
    dur_range = max_dur - min_dur

    def dur_y(s: int) -> float:
        return chart_h - 30 - ((s - min_dur) / dur_range) * (chart_h - 50)

    points_dur = " ".join(
        f"{80 + i * x_step},{dur_y(d)}"
        for i, d in enumerate(analysis["duration_trend"])
    )
    target30_y = dur_y(TARGET_TALK_S)
    target33_y = dur_y(TARGET_TOTAL_S)

    dur_svg_lines = ""
    for i, d in enumerate(analysis["duration_trend"]):
        cx = 80 + i * x_step
        cy = dur_y(d)
        color = "#4ade80" if abs(d - TARGET_TALK_S) <= TOLERANCE_S else "#f87171"
        dur_svg_lines += f'<circle cx="{cx}" cy="{cy}" r="6" fill="{color}"/>'
        dur_svg_lines += f'<text x="{cx}" y="{cy - 10}" text-anchor="middle" fill="#e2e8f0" font-size="11">{_fmt_mm_ss(d)}</text>'
        dur_svg_lines += f'<text x="{cx}" y="{chart_h - 8}" text-anchor="middle" fill="#94a3b8" font-size="10">S{sessions[i].session_id}</text>'

    dur_svg = f"""
<svg width="{chart_w}" height="{chart_h}" style="overflow:visible">
  <line x1="70" y1="{target30_y}" x2="{chart_w-10}" y2="{target30_y}" stroke="#4ade80" stroke-dasharray="6,3" stroke-width="1.5"/>
  <text x="5" y="{target30_y+4}" fill="#4ade80" font-size="10">30m</text>
  <line x1="70" y1="{target33_y}" x2="{chart_w-10}" y2="{target33_y}" stroke="#fbbf24" stroke-dasharray="4,4" stroke-width="1.5"/>
  <text x="5" y="{target33_y+4}" fill="#fbbf24" font-size="10">33m</text>
  <polyline points="{points_dur}" fill="none" stroke="#60a5fa" stroke-width="2.5"/>
  {dur_svg_lines}
</svg>"""

    # --- SVG 2: Per-slide timing heatmap (last session) ---
    last_session = sessions[-1]
    hm_cols = len(SLIDE_TARGETS)
    hm_cell_w = 44
    hm_cell_h = 60
    hm_w = hm_cols * hm_cell_w + 20
    hm_h = n_sessions * hm_cell_h + 50

    hm_cells = ""
    for si, sr_row in enumerate(analysis["slide_matrix"]):
        for sess_i, actual in enumerate(sr_row):
            target = analysis["slide_targets"][si]
            ratio = actual / target if target else 1
            if ratio <= 1.05:
                cell_color = "#166534"
            elif ratio <= 1.20:
                cell_color = "#854d0e"
            else:
                cell_color = "#7f1d1d"
            rx = 10 + si * hm_cell_w
            ry = 30 + sess_i * hm_cell_h
            label = f"{actual // 60}:{actual % 60:02d}"
            hm_cells += f'<rect x="{rx}" y="{ry}" width="{hm_cell_w-2}" height="{hm_cell_h-4}" rx="3" fill="{cell_color}"/>'
            hm_cells += f'<text x="{rx + hm_cell_w//2 - 1}" y="{ry + hm_cell_h//2 + 2}" text-anchor="middle" fill="#f1f5f9" font-size="9">{label}</text>'
            if sess_i == 0:
                hm_cells += f'<text x="{rx + hm_cell_w//2 - 1}" y="22" text-anchor="middle" fill="#94a3b8" font-size="9">{si+1}</text>'

    for sess_i, s in enumerate(sessions):
        ry = 30 + sess_i * hm_cell_h + hm_cell_h // 2 + 2
        hm_cells += f'<text x="6" y="{ry}" fill="#94a3b8" font-size="9">S{s.session_id}</text>'

    hm_svg = f"""
<svg width="{hm_w}" height="{hm_h}" style="overflow:visible">
  {hm_cells}
</svg>"""

    # --- SVG 3: Confidence trend ---
    conf_w, conf_h = chart_w, 180
    conf_max = 5.2
    def conf_y(v: float) -> float:
        return conf_h - 25 - ((v - 1) / (conf_max - 1)) * (conf_h - 45)

    conf_points = " ".join(
        f"{80 + i * x_step},{conf_y(c)}"
        for i, c in enumerate(analysis["conf_trend"])
    )
    conf_dots = ""
    for i, c in enumerate(analysis["conf_trend"]):
        cx = 80 + i * x_step
        cy = conf_y(c)
        conf_dots += f'<circle cx="{cx}" cy="{cy}" r="5" fill="#a78bfa"/>'
        conf_dots += f'<text x="{cx}" y="{cy - 9}" text-anchor="middle" fill="#c4b5fd" font-size="11">{c:.1f}</text>'
        conf_dots += f'<text x="{cx}" y="{conf_h-6}" text-anchor="middle" fill="#94a3b8" font-size="10">S{sessions[i].session_id}</text>'

    conf_svg = f"""
<svg width="{conf_w}" height="{conf_h}" style="overflow:visible">
  <line x1="70" y1="{conf_y(4.0)}" x2="{conf_w-10}" y2="{conf_y(4.0)}" stroke="#4ade80" stroke-dasharray="5,3" stroke-width="1"/>
  <text x="2" y="{conf_y(4.0)+4}" fill="#4ade80" font-size="9">4.0</text>
  <polyline points="{conf_points}" fill="none" stroke="#a78bfa" stroke-width="2.5"/>
  {conf_dots}
</svg>"""

    # --- Problem slides table ---
    prob_rows = ""
    recs = {
        "Live Demo": "Rehearse demo transitions separately; add 10s buffer",
        "Benchmark": "Trim to 3 key numbers; pre-load comparison chart",
        "Architecture": "Use animation — point rather than explain",
        "GTC Demo Live": "Full run-through daily; prepare fallback video",
        "The Problem": "Lead with customer quote; cut market-size slide",
    }
    for delta, title, num, target, avg_actual in analysis["worst_slides"]:
        if delta <= 0:
            break
        rec = next((v for k, v in recs.items() if k.lower() in title.lower()), "Tighten script; remove filler words")
        color = "#f87171" if delta > 30 else "#fbbf24"
        prob_rows += f"""
        <tr>
          <td style="color:{color};font-weight:600">Slide {num}</td>
          <td>{title}</td>
          <td style="color:#94a3b8">{_fmt_mm_ss(target)}</td>
          <td style="color:{color}">{_fmt_mm_ss(int(avg_actual))}</td>
          <td style="color:{color}">+{_fmt_mm_ss(int(delta))}</td>
          <td style="color:#94a3b8;font-size:12px">{rec}</td>
        </tr>"""

    # --- Q&A coverage ---
    qa_items = ""
    for q in analysis["qa_questions_covered"]:
        qa_items += f'<li style="margin:4px 0;color:#cbd5e1">{q}</li>'

    # --- Risk badges last session ---
    risk_html = ""
    for r in sessions[-1].identified_risks:
        risk_html += f'<span style="background:#7f1d1d;color:#fca5a5;border-radius:4px;padding:3px 8px;margin:3px;display:inline-block;font-size:12px">{r}</span>'
    if not risk_html:
        risk_html = '<span style="background:#14532d;color:#86efac;border-radius:4px;padding:3px 8px;font-size:12px">No critical risks identified</span>'

    # --- Summary stats ---
    first_min = sessions[0].total_duration_s // 60
    last_min  = sessions[-1].total_duration_s // 60
    on_target = abs(sessions[-1].total_duration_s - TARGET_TALK_S) <= TOLERANCE_S

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GTC 2027 Rehearsal Recorder</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 24px; color: #60a5fa; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 28px; }}
  h2 {{ font-size: 16px; color: #94a3b8; margin: 24px 0 10px; text-transform: uppercase; letter-spacing: .08em; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; overflow-x: auto; }}
  .stats {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }}
  .stat {{ background: #1e293b; border-radius: 8px; padding: 14px 20px; min-width: 140px; }}
  .stat-val {{ font-size: 26px; font-weight: 700; color: #60a5fa; }}
  .stat-lbl {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th {{ color: #64748b; text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b44; }}
  .legend {{ display: flex; gap: 14px; font-size: 12px; color: #94a3b8; margin-top: 8px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; margin-right: 4px; }}
</style>
</head>
<body>
<h1>GTC 2027 — Rehearsal Recorder</h1>
<p class="subtitle">Target: 30 min talk ± 2 min &nbsp;|&nbsp; Sessions recorded: {n_sessions} &nbsp;|&nbsp; Generated: 2027-03-29</p>

<div class="stats">
  <div class="stat"><div class="stat-val">{n_sessions}</div><div class="stat-lbl">Rehearsals</div></div>
  <div class="stat"><div class="stat-val">{first_min}m→{last_min}m</div><div class="stat-lbl">Duration trend</div></div>
  <div class="stat"><div class="stat-val">{analysis['improvement_pct']}%</div><div class="stat-lbl">Time reduction</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#4ade80' if on_target else '#f87171'}">{_fmt_mm_ss(sessions[-1].total_duration_s)}</div><div class="stat-lbl">Latest session</div></div>
  <div class="stat"><div class="stat-val">{sessions[-1].overall_confidence}/5</div><div class="stat-lbl">Latest confidence</div></div>
  <div class="stat"><div class="stat-val">{len(analysis['qa_questions_covered'])}</div><div class="stat-lbl">Q&A questions covered</div></div>
</div>

<h2>Total Duration Trend</h2>
<div class="card">
  {dur_svg}
  <div class="legend">
    <span><span class="dot" style="background:#4ade80"></span>Within ±2 min target</span>
    <span><span class="dot" style="background:#f87171"></span>Over target</span>
    <span style="color:#4ade80">— 30 min target</span>
    <span style="color:#fbbf24">-- 33 min hard cap (incl. Q&A buffer)</span>
  </div>
</div>

<h2>Per-Slide Timing Heatmap (all sessions × all slides)</h2>
<div class="card">
  {hm_svg}
  <div class="legend" style="margin-top:12px">
    <span><span class="dot" style="background:#166534"></span>On time (≤5% over)</span>
    <span><span class="dot" style="background:#854d0e"></span>Slightly over (5–20%)</span>
    <span><span class="dot" style="background:#7f1d1d"></span>Over (>20%)</span>
    <span style="color:#94a3b8;font-size:11px">Columns = slides 1–14 &nbsp;|&nbsp; Rows = sessions S1–S{n_sessions}</span>
  </div>
</div>

<h2>Confidence Trend (1–5 scale)</h2>
<div class="card">
  {conf_svg}
  <div class="legend">
    <span style="color:#4ade80">— 4.0 target threshold</span>
  </div>
</div>

<h2>Problem Slides — Recommendations</h2>
<div class="card">
  <table>
    <thead><tr><th>#</th><th>Slide</th><th>Target</th><th>Avg Actual</th><th>Avg Over</th><th>Recommendation</th></tr></thead>
    <tbody>{prob_rows}</tbody>
  </table>
</div>

<h2>Q&A Practice Coverage</h2>
<div class="card">
  <ul style="padding-left:18px;line-height:1.7">{qa_items}</ul>
</div>

<h2>Current Risk Flags (Latest Session)</h2>
<div class="card">{risk_html}</div>

</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GTC 2027 Rehearsal Recorder")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Generate 5 mock rehearsal sessions (default: True)")
    parser.add_argument("--output", default="/tmp/rehearsal_recorder.html",
                        help="Output HTML path (default: /tmp/rehearsal_recorder.html)")
    args = parser.parse_args()

    if args.mock:
        sessions = generate_mock_sessions()
    else:
        print("Live recording mode not yet implemented. Use --mock.")
        return

    analysis = analyze_sessions(sessions)
    html = render_html(sessions, analysis)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Rehearsal report written to: {args.output}")
    print(f"Sessions: {len(sessions)}")
    print(f"Duration trend: {' → '.join(_fmt_mm_ss(d) for d in analysis['duration_trend'])}")
    print(f"Improvement: {analysis['improvement_pct']}% reduction in talk time")
    print(f"Latest confidence: {sessions[-1].overall_confidence}/5")
    print(f"Q&A questions covered: {len(analysis['qa_questions_covered'])}")


if __name__ == "__main__":
    main()
