"""\nOCI Robot Cloud — Simulation Evaluation Harness\nPort 8121 | GR00T policy testing in LIBERO simulation environment\n"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Required dependency missing: {e}. Install with: pip install fastapi uvicorn")

import json
from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Sim Eval Harness", version="1.0.0")

# ---------------------------------------------------------------------------
# Static eval data
# ---------------------------------------------------------------------------

SESSIONS = {
    "eval_dagger_run9_v2": {
        "name": "eval_dagger_run9_v2",
        "status": "COMPLETED",
        "ran": "2026-03-15",
        "total_episodes": 20,
        "success_count": 14,
        "sr": 0.71,
        "avg_latency_ms": 231,
        "cube_z_avg": 0.823,
        "failure_modes": {"approach": 3, "grasp": 2, "dropped": 1},
        "episodes": [
            {"ep": i+1, "success": i < 14, "latency_ms": 228 + (i % 5)*3, "cube_z": round(0.810 + (i % 7)*0.004, 3)}
            for i in range(20)
        ],
    },
    "eval_groot_finetune_v2": {
        "name": "eval_groot_finetune_v2",
        "status": "COMPLETED",
        "ran": "2026-03-22",
        "total_episodes": 20,
        "success_count": 15,
        "sr": 0.78,
        "avg_latency_ms": 226,
        "cube_z_avg": 0.841,
        "failure_modes": {"approach": 2, "grasp": 3},
        "episodes": [
            {"ep": i+1, "success": i < 15, "latency_ms": 223 + (i % 4)*2, "cube_z": round(0.828 + (i % 6)*0.004, 3)}
            for i in range(20)
        ],
    },
}

# Comparison winner
WINNER = "eval_groot_finetune_v2"
WINNER_DELTA_PP = 7   # percentage points

# ---------------------------------------------------------------------------
# SVG charts
# ---------------------------------------------------------------------------

SESSION_COLORS = {
    "eval_dagger_run9_v2":     "#38bdf8",   # sky blue
    "eval_groot_finetune_v2":  "#C74634",   # Oracle red
}

SESSION_SHORT = {
    "eval_dagger_run9_v2":    "DAgger run9",
    "eval_groot_finetune_v2": "GR00T v2",
}


def build_sr_bar_chart() -> str:
    """700x200 side-by-side SR% bar chart."""
    W, H = 700, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    sessions = list(SESSIONS.values())
    n = len(sessions)
    group_w = chart_w // n
    bar_w = group_w * 2 // 3
    max_val = 100

    bars = []
    labels = []
    for i, sess in enumerate(sessions):
        pct = sess["sr"] * 100
        bh = int(chart_h * pct / max_val)
        bx = pad_l + i * group_w + (group_w - bar_w) // 2
        by = pad_t + chart_h - bh
        color = SESSION_COLORS.get(sess["name"], "#94a3b8")
        short = SESSION_SHORT.get(sess["name"], sess["name"])
        bars.append(
            f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" rx="4" fill="{color}" opacity="0.85"/>'
        )
        bars.append(
            f'<text x="{bx + bar_w//2}" y="{by - 6}" text-anchor="middle" fill="{color}" '
            f'font-size="13" font-family="monospace" font-weight="bold">{int(pct)}%</text>'
        )
        labels.append(
            f'<text x="{bx + bar_w//2}" y="{pad_t + chart_h + 18}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11" font-family="monospace">{short}</text>'
        )

    # y-axis gridlines at 25, 50, 75, 100
    grids = []
    for pct in (25, 50, 75, 100):
        gy = pad_t + chart_h - int(chart_h * pct / max_val)
        grids.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{W - pad_r}" y2="{gy}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        grids.append(
            f'<text x="{pad_l - 6}" y="{gy + 4}" text-anchor="end" fill="#475569" '
            f'font-size="10" font-family="monospace">{pct}%</text>'
        )

    inner = "\n".join(grids + bars + labels)
    title = '<text x="350" y="18" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace">Success Rate Comparison (%)</text>'
    return f'''<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="10"/>
  {title}
  {inner}
</svg>'''


def build_failure_mode_chart() -> str:
    """700x160 stacked bar chart for failure modes per session."""
    W, H = 700, 160
    pad_l, pad_r, pad_t, pad_b = 60, 130, 30, 36

    sessions = list(SESSIONS.values())
    all_modes = ["approach", "grasp", "dropped"]
    mode_colors = {"approach": "#f59e0b", "grasp": "#ef4444", "dropped": "#a855f7"}

    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(sessions)
    bar_w = chart_w // (n + 1)
    max_total = max(sum(s["failure_modes"].values()) for s in sessions)
    if max_total == 0:
        max_total = 1

    bars = []
    labels = []
    for i, sess in enumerate(sessions):
        bx = pad_l + i * (bar_w + bar_w // 2)
        short = SESSION_SHORT.get(sess["name"], sess["name"])
        y_cursor = pad_t + chart_h
        for mode in all_modes:
            count = sess["failure_modes"].get(mode, 0)
            if count == 0:
                continue
            seg_h = int(chart_h * count / max_total)
            y_cursor -= seg_h
            bars.append(
                f'<rect x="{bx}" y="{y_cursor}" width="{bar_w}" height="{seg_h}" '
                f'fill="{mode_colors[mode]}" opacity="0.85"/>'
            )
            if seg_h >= 14:
                bars.append(
                    f'<text x="{bx + bar_w//2}" y="{y_cursor + seg_h//2 + 4}" '
                    f'text-anchor="middle" fill="#0f172a" font-size="10" font-weight="bold">{count}</text>'
                )
        labels.append(
            f'<text x="{bx + bar_w//2}" y="{pad_t + chart_h + 18}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11" font-family="monospace">{short}</text>'
        )

    # legend
    legend = []
    lx = W - pad_r + 8
    for li, mode in enumerate(all_modes):
        ly = pad_t + li * 20
        legend.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" rx="2" fill="{mode_colors[mode]}"/>')
        legend.append(
            f'<text x="{lx + 16}" y="{ly + 10}" fill="#94a3b8" font-size="11" font-family="monospace">{mode}</text>'
        )

    title = '<text x="350" y="18" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace">Failure Modes (stacked)</text>'
    inner = "\n".join(bars + labels + legend)
    return f'''<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="10"/>
  {title}
  {inner}
</svg>'''


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def episode_table(sess: dict) -> str:
    rows = []
    for ep in sess["episodes"]:
        if ep["success"]:
            badge = '<span style="background:#16a34a;color:#fff;padding:1px 8px;border-radius:10px;font-size:11px;">SUCCESS</span>'
        else:
            badge = '<span style="background:#991b1b;color:#fff;padding:1px 8px;border-radius:10px;font-size:11px;">FAIL</span>'
        rows.append(
            f'<tr>'
            f'<td style="padding:5px 10px;color:#94a3b8;">{ep["ep"]}</td>'
            f'<td style="padding:5px 10px;">{badge}</td>'
            f'<td style="padding:5px 10px;color:#f1f5f9;">{ep["latency_ms"]}ms</td>'
            f'<td style="padding:5px 10px;color:#f1f5f9;">{ep["cube_z"]}m</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<thead><tr style="border-bottom:1px solid #334155;">'
        '<th style="padding:6px 10px;color:#38bdf8;text-align:left;">Ep</th>'
        '<th style="padding:6px 10px;color:#38bdf8;text-align:left;">Result</th>'
        '<th style="padding:6px 10px;color:#38bdf8;text-align:left;">Latency</th>'
        '<th style="padding:6px 10px;color:#38bdf8;text-align:left;">Cube Z</th>'
        '</tr></thead><tbody>'
        + "\n".join(rows)
        + '</tbody></table>'
    )


def session_card(sess: dict) -> str:
    color = SESSION_COLORS.get(sess["name"], "#94a3b8")
    fm_items = " &nbsp;\u00b7&nbsp; ".join(f"{k}={v}" for k, v in sess["failure_modes"].items())
    return f'''
<div style="background:#1e293b;border:1px solid {color};border-radius:12px;padding:24px;margin-bottom:20px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <span style="font-family:monospace;font-size:15px;color:#f1f5f9;">{sess["name"]}</span>
    <span style="background:#166534;color:#bbf7d0;padding:2px 10px;border-radius:12px;font-size:12px;">COMPLETED</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
    <div style="text-align:center;">
      <div style="font-size:26px;font-weight:700;color:{color};">{int(sess["sr"]*100)}%</div>
      <div style="color:#94a3b8;font-size:11px;">Success Rate</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:26px;font-weight:700;color:#f1f5f9;">{sess["success_count"]}/{sess["total_episodes"]}</div>
      <div style="color:#94a3b8;font-size:11px;">Episodes</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:26px;font-weight:700;color:#f1f5f9;">{sess["avg_latency_ms"]}ms</div>
      <div style="color:#94a3b8;font-size:11px;">Avg Latency</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:26px;font-weight:700;color:#f1f5f9;">{sess["cube_z_avg"]}m</div>
      <div style="color:#94a3b8;font-size:11px;">Cube Z avg</div>
    </div>
  </div>
  <div style="color:#94a3b8;font-size:12px;margin-bottom:16px;">Failure modes: {fm_items} &nbsp;|&nbsp; Ran {sess["ran"]}</div>
  <details>
    <summary style="cursor:pointer;color:#38bdf8;font-size:13px;margin-bottom:8px;">Episode details \u25be</summary>
    {episode_table(sess)}
  </details>
</div>'''


def build_dashboard_html() -> str:
    sessions = list(SESSIONS.values())
    sr_svg = build_sr_bar_chart()
    fm_svg = build_failure_mode_chart()
    cards_html = "\n".join(session_card(s) for s in sessions)
    winner_sess = SESSIONS[WINNER]
    winner_color = SESSION_COLORS.get(WINNER, "#22c55e")
    winner_short = SESSION_SHORT.get(WINNER, WINNER)

    winner_callout = f'''
<div style="background:#1e293b;border:2px solid {winner_color};border-radius:12px;padding:20px;margin-bottom:28px;display:flex;align-items:center;gap:20px;">
  <div style="font-size:36px;">&#127942;</div>
  <div>
    <div style="color:{winner_color};font-size:15px;font-weight:700;">{winner_short} wins</div>
    <div style="color:#f1f5f9;font-size:13px;margin-top:4px;">
      Best SR: {int(winner_sess["sr"]*100)}% &nbsp;|&nbsp; +{WINNER_DELTA_PP}pp vs DAgger run9 &nbsp;|&nbsp;
      Avg latency {winner_sess["avg_latency_ms"]}ms &nbsp;|&nbsp; Cube Z avg {winner_sess["cube_z_avg"]}m
    </div>
  </div>
</div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud \u2014 Sim Eval Harness</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:#0f172a;color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh;}}
    .header{{background:#1e293b;border-bottom:2px solid #C74634;padding:18px 32px;display:flex;align-items:center;justify-content:space-between;}}
    .logo{{color:#C74634;font-weight:700;font-size:18px;letter-spacing:.5px;}}
    .subtitle{{color:#94a3b8;font-size:13px;margin-top:2px;}}
    .main{{padding:32px;max-width:900px;margin:0 auto;}}
    h2{{color:#38bdf8;font-size:15px;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;}}
    .chart-wrap{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;margin-bottom:20px;overflow-x:auto;}}
    details summary::-webkit-details-marker{{color:#38bdf8;}}
    .footer{{text-align:center;color:#475569;font-size:11px;padding:24px;border-top:1px solid #1e293b;margin-top:16px;}}
  </style>
</head>
<body>
<div class="header">
  <div>
    <div class="logo">OCI Robot Cloud &mdash; Sim Eval Harness</div>
    <div class="subtitle">GR00T policy evaluation in LIBERO simulation &nbsp;|&nbsp; Port 8121</div>
  </div>
  <div style="color:#94a3b8;font-size:12px;">{datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</div>
</div>
<div class="main">

  <h2 style="margin-top:24px;">Comparison Winner</h2>
  {winner_callout}

  <h2>Success Rate Chart</h2>
  <div class="chart-wrap">{sr_svg}</div>

  <h2>Failure Mode Analysis</h2>
  <div class="chart-wrap">{fm_svg}</div>

  <h2>Eval Sessions</h2>
  {cards_html}

</div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud Sim Eval Harness &nbsp;|&nbsp; Port 8121</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return build_dashboard_html()


@app.get("/sessions")
async def list_sessions():
    return JSONResponse({"sessions": list(SESSIONS.values()), "count": len(SESSIONS)})


@app.get("/sessions/{name}")
async def get_session(name: str):
    s = SESSIONS.get(name)
    if s is None:
        return JSONResponse({"error": f"Session '{name}' not found"}, status_code=404)
    return JSONResponse(s)


@app.get("/compare")
async def compare():
    sessions = list(SESSIONS.values())
    if len(sessions) < 2:
        return JSONResponse({"error": "Not enough sessions to compare"}, status_code=400)
    ranked = sorted(sessions, key=lambda s: s["sr"], reverse=True)
    winner = ranked[0]
    runner_up = ranked[1]
    delta_pp = round((winner["sr"] - runner_up["sr"]) * 100, 1)
    return JSONResponse({
        "winner": winner["name"],
        "winner_sr": winner["sr"],
        "runner_up": runner_up["name"],
        "runner_up_sr": runner_up["sr"],
        "delta_pp": delta_pp,
        "winner_latency_ms": winner["avg_latency_ms"],
        "winner_cube_z_avg": winner["cube_z_avg"],
    })


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "sim_eval_harness", "port": 8121})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        uvicorn.run(app, host="0.0.0.0", port=8121, log_level="info")
    except Exception as exc:
        raise SystemExit(f"Failed to start server: {exc}")


if __name__ == "__main__":
    main()
