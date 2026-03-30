"""GTC 2027 Talk Planning and Preparation Tracker — port 8169"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

from datetime import datetime, date

TALK_PROPOSAL = (
    "Training Foundation Robot Models at Scale on OCI: "
    "From Genesis SDG to 78% Success Rate"
)

KEY_METRICS = [
    {"label": "MAE improvement", "value": "8.7×"},
    {"label": "Cost per fine-tune run", "value": "$0.43"},
    {"label": "vs AWS", "value": "9.6× cheaper"},
    {"label": "Inference latency", "value": "226ms"},
]

MILESTONES = [
    {
        "id": "demo_system_ready",
        "name": "Demo System Ready",
        "status": "COMPLETED",
        "due": "2026-06-01",
        "actual": "2026-03-30",
        "notes": "Live inference + DAgger running",
    },
    {
        "id": "design_partner_results",
        "name": "Design Partner Results",
        "status": "IN_PROGRESS",
        "due": "2026-09-01",
        "actual": None,
        "notes": "Need 2+ partners with real robot results",
    },
    {
        "id": "paper_draft",
        "name": "Paper Draft",
        "status": "IN_PROGRESS",
        "due": "2026-09-15",
        "actual": None,
        "notes": "CoRL 2026 submission target",
    },
    {
        "id": "nvidia_co_presenter",
        "name": "NVIDIA Co-Presenter",
        "status": "BLOCKED",
        "due": "2026-10-01",
        "actual": None,
        "notes": "Need intro to Isaac/GR00T team via Greg",
    },
    {
        "id": "slide_deck_v1",
        "name": "Slide Deck v1",
        "status": "PENDING",
        "due": "2026-11-01",
        "actual": None,
        "notes": "Based on AI World demo deck",
    },
    {
        "id": "talk_submission",
        "name": "Talk Submission",
        "status": "PENDING",
        "due": "2026-12-01",
        "actual": None,
        "notes": "GTC 2027 CFP typically opens Nov",
    },
]

RISKS = [
    {
        "id": "nvidia_co_presenter_blocked",
        "description": "NVIDIA co-presenter blocked — no intro to Isaac/GR00T team yet",
        "level": "HIGH",
        "mitigation": "Escalate to Greg for warm intro; target Q2 2026 outreach",
        "linked_milestone": "nvidia_co_presenter",
    },
    {
        "id": "design_partner_real_robot",
        "description": "Design partner real-robot results needed for credibility",
        "level": "MEDIUM",
        "mitigation": "Onboard 2 partners by Aug 2026; use sim results as fallback",
        "linked_milestone": "design_partner_results",
    },
]

# Timeline bounds for Gantt
_GANTT_START = date(2026, 4, 1)
_GANTT_END = date(2027, 3, 1)


def _status_color(status: str) -> str:
    return {
        "COMPLETED": "#22c55e",
        "IN_PROGRESS": "#38bdf8",
        "BLOCKED": "#C74634",
        "PENDING": "#475569",
    }.get(status, "#475569")


def _date_to_x(d: date, chart_x: int, chart_w: int) -> int:
    total = (_GANTT_END - _GANTT_START).days
    elapsed = (d - _GANTT_START).days
    return chart_x + int(chart_w * elapsed / total)


def _gantt_svg() -> str:
    W, H = 680, 200
    label_w = 160
    chart_x = label_w + 10
    chart_w = W - chart_x - 20
    n = len(MILESTONES)
    row_h = (H - 50) // n
    today = date.today()

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # month grid lines
    months = [
        date(2026, m, 1) for m in range(4, 13)
    ] + [date(2027, m, 1) for m in range(1, 4)]
    for mo in months:
        gx = _date_to_x(mo, chart_x, chart_w)
        lines.append(
            f'<line x1="{gx}" y1="20" x2="{gx}" y2="{H - 20}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{gx}" y="16" fill="#475569" font-size="8" '
            f'text-anchor="middle" font-family="monospace">{mo.strftime("%b%y")}</text>'
        )

    # bars
    for i, m in enumerate(MILESTONES):
        y = 24 + i * row_h
        bar_h = row_h - 6
        color = _status_color(m["status"])
        due = date.fromisoformat(m["due"])
        bar_x = _date_to_x(_GANTT_START, chart_x, chart_w)
        bar_end = _date_to_x(due, chart_x, chart_w)
        bar_len = max(bar_end - bar_x, 8)

        lines.append(
            f'<text x="{label_w - 4}" y="{y + bar_h // 2 + 3}" fill="#e2e8f0" '
            f'font-size="9" text-anchor="end" font-family="monospace">{m["name"]}</text>'
        )
        lines.append(
            f'<rect x="{chart_x}" y="{y}" width="{chart_w}" height="{bar_h}" '
            f'rx="3" fill="#0f172a" opacity="0.4"/>'
        )
        lines.append(
            f'<rect x="{bar_x}" y="{y}" width="{bar_len}" height="{bar_h}" '
            f'rx="3" fill="{color}" opacity="0.85"/>'
        )
        # due date label
        lines.append(
            f'<text x="{bar_end + 3}" y="{y + bar_h // 2 + 3}" fill="#94a3b8" '
            f'font-size="8" font-family="monospace">{m["due"]}</text>'
        )

    # today line
    if _GANTT_START <= today <= _GANTT_END:
        tx = _date_to_x(today, chart_x, chart_w)
        lines.append(
            f'<line x1="{tx}" y1="18" x2="{tx}" y2="{H - 18}" '
            f'stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3"/>'
        )
        lines.append(
            f'<text x="{tx}" y="{H - 8}" fill="#fbbf24" font-size="8" '
            f'text-anchor="middle" font-family="monospace">TODAY</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _html_dashboard() -> str:
    gantt = _gantt_svg()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    milestone_rows = ""
    for m in MILESTONES:
        color = _status_color(m["status"])
        actual = m["actual"] or "—"
        milestone_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600;color:#e2e8f0">{m['name']}</td>
          <td style="padding:8px 12px">
            <span style="background:{color};color:#0f172a;padding:2px 8px;
              border-radius:10px;font-size:11px;font-weight:700">{m['status']}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{m['due']}</td>
          <td style="padding:8px 12px;color:#22c55e">{actual}</td>
          <td style="padding:8px 12px;color:#64748b;font-size:11px">{m['notes']}</td>
        </tr>"""

    risk_rows = ""
    for r in RISKS:
        risk_color = "#C74634" if r["level"] == "HIGH" else "#f59e0b"
        risk_rows += f"""
        <tr>
          <td style="padding:8px 12px">
            <span style="color:{risk_color};font-weight:700">{r['level']}</span>
          </td>
          <td style="padding:8px 12px;color:#e2e8f0">{r['description']}</td>
          <td style="padding:8px 12px;color:#64748b;font-size:11px">{r['mitigation']}</td>
        </tr>"""

    metrics_html = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:12px 20px;"
           f'border-top:3px solid #C74634;text-align:center;">'
        f'<div style="color:#38bdf8;font-size:22px;font-weight:800">{km["value"]}</div>'
        f'<div style="color:#64748b;font-size:11px;margin-top:4px">{km["label"]}</div></div>'
        for km in KEY_METRICS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>GTC 2027 Planner — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px; }}
    h1 {{ color:#C74634; margin:0 0 4px; font-size:22px; }}
    h2 {{ color:#38bdf8; font-size:15px; margin:24px 0 10px; }}
    .subtitle {{ color:#64748b; font-size:12px; margin-bottom:8px; }}
    .talk-title {{ background:#1e293b; border-left:3px solid #38bdf8; padding:12px 16px;
      border-radius:0 8px 8px 0; color:#fbbf24; font-size:14px; margin:12px 0 20px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px;
      overflow:hidden; margin-bottom:16px; }}
    th {{ background:#0f172a; color:#64748b; font-size:11px; padding:8px 12px; text-align:left; }}
    tr:hover td {{ background:#233047; }}
    .endpoints {{ background:#1e293b; border-radius:8px; padding:16px; margin-top:24px; }}
    .ep {{ color:#38bdf8; font-size:12px; margin:4px 0; }}
  </style>
</head>
<body>
  <h1>GTC 2027 Talk Planner</h1>
  <div class="subtitle">OCI Robot Cloud · {today}</div>
  <div class="talk-title">{TALK_PROPOSAL}</div>

  <h2>Key Metrics to Highlight</h2>
  <div class="metrics">{metrics_html}</div>

  <h2>Preparation Timeline</h2>
  {gantt}

  <h2>Milestones</h2>
  <table>
    <thead><tr>
      <th>Milestone</th><th>Status</th><th>Due</th><th>Actual</th><th>Notes</th>
    </tr></thead>
    <tbody>{milestone_rows}</tbody>
  </table>

  <h2>Risks</h2>
  <table>
    <thead><tr><th>Level</th><th>Description</th><th>Mitigation</th></tr></thead>
    <tbody>{risk_rows}</tbody>
  </table>

  <div class="endpoints">
    <div style="color:#64748b;font-size:11px;margin-bottom:8px">ENDPOINTS</div>
    <div class="ep">GET /            — this dashboard</div>
    <div class="ep">GET /milestones  — all milestones (JSON)</div>
    <div class="ep">GET /risks       — risk tracker (JSON)</div>
    <div class="ep">GET /abstract    — talk summary (JSON)</div>
  </div>
</body>
</html>"""


if FastAPI is not None:
    app = FastAPI(title="GTC 2027 Planner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/milestones")
    def get_milestones():
        completed = sum(1 for m in MILESTONES if m["status"] == "COMPLETED")
        return {
            "milestones": MILESTONES,
            "total": len(MILESTONES),
            "completed": completed,
            "pct_complete": round(completed / len(MILESTONES) * 100),
        }

    @app.get("/risks")
    def get_risks():
        return {
            "risks": RISKS,
            "high_count": sum(1 for r in RISKS if r["level"] == "HIGH"),
            "medium_count": sum(1 for r in RISKS if r["level"] == "MEDIUM"),
        }

    @app.get("/abstract")
    def get_abstract():
        return {
            "title": TALK_PROPOSAL,
            "venue": "GTC 2027",
            "submission_due": "2026-12-01",
            "key_metrics": KEY_METRICS,
            "abstract": (
                "We present OCI Robot Cloud, a production-grade platform for training "
                "foundation robot models at scale. Using GR00T N1.6 as our backbone "
                "with Synthetic Data Generation via Isaac Sim and Cosmos, we achieve "
                "an 8.7× MAE improvement over baseline at $0.43/run — 9.6× cheaper "
                "than AWS. The system supports fine-tuning, DAgger online learning, "
                "and edge deployment to Jetson AGX Orin at 226ms inference. We share "
                "results from design partners achieving up to 78% task success rate on "
                "real robot hardware."
            ),
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("gtc_planner:app", host="0.0.0.0", port=8169, reload=True)
