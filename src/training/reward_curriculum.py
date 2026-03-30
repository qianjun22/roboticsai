"""\nReward Curriculum Scheduler — OCI Robot Cloud DAgger Training\nPort: 8123\n"""

import math
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

app = FastAPI(title="Reward Curriculum Scheduler", version="1.0.0")

# ---------------------------------------------------------------------------
# Static curriculum data
# ---------------------------------------------------------------------------
STAGES = [
    {
        "id": 1,
        "name": "reach_only",
        "status": "COMPLETED",
        "episode_range": [0, 200],
        "rewards": {
            "reach_distance": 0.6,
            "task_success": 0.4,
        },
        "success_rate_achieved": 38,
        "success_rate_target": None,
        "notes": "Foundation stage: teach the arm to reach the target object.",
    },
    {
        "id": 2,
        "name": "grasp_focus",
        "status": "COMPLETED",
        "episode_range": [200, 600],
        "rewards": {
            "grasp_stability": 0.4,
            "task_success": 0.4,
            "reach_distance": 0.2,
        },
        "success_rate_achieved": 55,
        "success_rate_target": None,
        "notes": "Penalize slippage; introduce grasp stability signal.",
    },
    {
        "id": 3,
        "name": "lift_and_hold",
        "status": "ACTIVE",
        "episode_range": [600, 1200],
        "rewards": {
            "task_success": 0.50,
            "lift_height": 0.20,
            "grasp_stability": 0.13,
            "smoothness": 0.10,
            "efficiency": 0.05,
            "collision": 0.01,
            "time_penalty": 0.01,
        },
        "success_rate_achieved": 71,
        "success_rate_target": None,
        "notes": "Active stage — targeting lift_height >= 0.78m threshold.",
    },
    {
        "id": 4,
        "name": "full_precision",
        "status": "PENDING",
        "episode_range": [1200, None],
        "rewards": {},
        "success_rate_achieved": None,
        "success_rate_target": 85,
        "notes": "Full task precision; reward weights TBD after stage 3 analysis.",
    },
]

CURRENT_STAGE_ID = 3
NEXT_STAGE_THRESHOLD_EPISODE = 1200
CURRENT_EPISODE = 847  # approximate mid-stage


def get_stage_by_id(stage_id: int):
    for s in STAGES:
        if s["id"] == stage_id:
            return s
    return None


# ---------------------------------------------------------------------------
# SVG: SR progression bar chart (700x180)
# ---------------------------------------------------------------------------
def build_sr_chart() -> str:
    W, H = 700, 180
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    max_sr = 100

    bars = []
    bar_width = chart_w // 4 - 16
    colors = {
        "COMPLETED": "#22c55e",
        "ACTIVE": "#C74634",
        "PENDING": "#475569",
    }

    for i, stage in enumerate(STAGES):
        sr = stage["success_rate_achieved"] or 0
        bar_h = int((sr / max_sr) * chart_h)
        x = pad_l + i * (chart_w // 4) + 8
        y = pad_t + chart_h - bar_h
        color = colors[stage["status"]]
        label = stage["name"].replace("_", " ")

        # Bar
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" '
            f'rx="4" ry="4" fill="{color}" opacity="{"1" if stage["status"]=="ACTIVE" else "0.8"}"/>'
        )
        # SR label above bar
        if sr > 0:
            bars.append(
                f'<text x="{x + bar_width//2}" y="{y - 5}" text-anchor="middle" '
                f'font-size="11" font-weight="bold" fill="{color}" font-family="monospace">{sr}%</text>'
            )
        else:
            bars.append(
                f'<text x="{x + bar_width//2}" y="{pad_t + chart_h - 5}" text-anchor="middle" '
                f'font-size="10" fill="#64748b" font-family="monospace">pending</text>'
            )
        # X-axis label
        bars.append(
            f'<text x="{x + bar_width//2}" y="{H - 8}" text-anchor="middle" '
            f'font-size="9" fill="#94a3b8" font-family="monospace">{label[:14]}</text>'
        )
        # Status badge
        bars.append(
            f'<text x="{x + bar_width//2}" y="{H - 20}" text-anchor="middle" '
            f'font-size="8" fill="{color}" font-family="monospace">[{stage["status"]}]</text>'
        )

    # Y-axis gridlines
    grids = []
    for pct in [25, 50, 75, 100]:
        gy = pad_t + chart_h - int((pct / max_sr) * chart_h)
        grids.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{W - pad_r}" y2="{gy}" '
            f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        grids.append(
            f'<text x="{pad_l - 4}" y="{gy + 4}" text-anchor="end" '
            f'font-size="9" fill="#64748b" font-family="monospace">{pct}%</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="14" text-anchor="middle" font-size="11" font-weight="600" fill="#94a3b8" font-family="monospace">Success Rate by Curriculum Stage</text>
  {''.join(grids)}
  {''.join(bars)}
</svg>"""


# ---------------------------------------------------------------------------
# SVG: reward weight grouped bars (700x160)
# ---------------------------------------------------------------------------
def build_reward_chart() -> str:
    W, H = 700, 160
    pad_l, pad_r, pad_t, pad_b = 10, 10, 20, 30
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    # Collect all reward keys across completed/active stages
    all_keys = []
    seen = set()
    for s in STAGES[:3]:
        for k in s["rewards"]:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    n_keys = len(all_keys)
    n_stages = 3  # only COMPLETED + ACTIVE
    group_w = chart_w // n_keys
    bar_w = max(6, group_w // (n_stages + 1))
    stage_colors = ["#22c55e", "#34d399", "#C74634"]

    bars = []
    for ki, key in enumerate(all_keys):
        group_x = pad_l + ki * group_w
        for si, stage in enumerate(STAGES[:3]):
            weight = stage["rewards"].get(key, 0.0)
            if weight == 0:
                continue
            bar_h = int((weight / 1.0) * chart_h)
            x = group_x + si * (bar_w + 2) + 4
            y = pad_t + chart_h - bar_h
            color = stage_colors[si]
            bars.append(
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
                f'rx="2" ry="2" fill="{color}" opacity="0.85"/>'
            )
            if weight >= 0.1:
                bars.append(
                    f'<text x="{x + bar_w//2}" y="{y - 3}" text-anchor="middle" '
                    f'font-size="8" fill="{color}" font-family="monospace">{weight:.2f}</text>'
                )
        # Key label
        short = key.replace("_", " ")[:10]
        bars.append(
            f'<text x="{group_x + group_w//2}" y="{H - 5}" text-anchor="middle" '
            f'font-size="8" fill="#64748b" font-family="monospace">{short}</text>'
        )

    # Legend
    legend = []
    for si, stage in enumerate(STAGES[:3]):
        lx = pad_l + si * 140 + 10
        legend.append(
            f'<rect x="{lx}" y="4" width="10" height="10" fill="{stage_colors[si]}" rx="2"/>'
            f'<text x="{lx + 14}" y="13" font-size="9" fill="#94a3b8" font-family="monospace">S{stage["id"]} {stage["name"][:12]}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  {''.join(legend)}
  {''.join(bars)}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def build_dashboard() -> str:
    current = get_stage_by_id(CURRENT_STAGE_ID)
    next_stage = get_stage_by_id(CURRENT_STAGE_ID + 1)

    stage_status_color = {
        "COMPLETED": "#22c55e",
        "ACTIVE": "#C74634",
        "PENDING": "#64748b",
    }
    stage_status_bg = {
        "COMPLETED": "#14532d",
        "ACTIVE": "#450a0a",
        "PENDING": "#1e293b",
    }

    # Progress within current stage
    ep_start, ep_end = current["episode_range"]
    progress_pct = min(100, int(((CURRENT_EPISODE - ep_start) / (ep_end - ep_start)) * 100))

    # Stage cards
    stage_cards = []
    for stage in STAGES:
        color = stage_status_color[stage["status"]]
        bg = stage_status_bg[stage["status"]]
        sr = stage["success_rate_achieved"]
        ep_range = f"{stage['episode_range'][0]}\u2013{stage['episode_range'][1] or '\u221e'}"
        sr_bar = ""
        if sr is not None:
            sr_bar = f"""
          <div style="margin-top:8px">
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;margin-bottom:4px">
              <span>Success Rate</span><span style="color:{color};font-weight:700">{sr}%</span>
            </div>
            <div style="background:#0f172a;border-radius:4px;height:6px">
              <div style="background:{color};width:{sr}%;height:6px;border-radius:4px"></div>
            </div>
          </div>"""
        elif stage.get("success_rate_target"):
            sr_bar = f'<div style="margin-top:8px;font-size:11px;color:#64748b">Target: &gt;{stage["success_rate_target"]}% SR</div>'

        reward_pills = "".join(
            f'<span style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:2px 8px;font-size:10px;font-family:monospace;color:#94a3b8">'
            f'{k} <span style="color:{color}">{v:.2f}</span></span> '
            for k, v in stage["rewards"].items()
        ) if stage["rewards"] else '<span style="color:#475569;font-size:11px">TBD after stage 3 analysis</span>'

        stage_cards.append(f"""
      <div style="background:{bg};border:1px solid {color};border-radius:8px;padding:16px;min-width:240px;flex:1">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <div style="font-size:11px;color:#64748b;font-family:monospace">Stage {stage['id']}</div>
            <div style="font-size:14px;font-weight:700;color:{color};font-family:monospace;margin-top:2px">{stage['name']}</div>
          </div>
          <span style="background:{bg};border:1px solid {color};color:{color};font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">{stage['status']}</span>
        </div>
        <div style="font-size:11px;color:#64748b;margin-top:8px">Episodes: <span style="color:#94a3b8">{ep_range}</span></div>
        <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">{reward_pills}</div>
        {sr_bar}
        <div style="margin-top:8px;font-size:10px;color:#475569">{stage['notes']}</div>
      </div>""")

    # Current stage reward breakdown
    reward_rows = "".join(
        f"""<tr>
          <td style="padding:7px 12px;font-family:monospace;font-size:12px;color:#38bdf8">{k}</td>
          <td style="padding:7px 12px">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="background:#0f172a;border-radius:4px;height:8px;width:160px">
                <div style="background:#C74634;width:{int(v*100)}%;height:8px;border-radius:4px"></div>
              </div>
              <span style="font-size:12px;color:#C74634;font-weight:700">{v:.2f}</span>
            </div>
          </td>
        </tr>"""
        for k, v in current["rewards"].items()
    )

    sr_chart = build_sr_chart()
    reward_chart = build_reward_chart()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Reward Curriculum Scheduler | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 1px solid #1e3a5f; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }}
    .header-title {{ font-size: 20px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px; }}
    .header-sub {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
    .oracle-badge {{ background: #C74634; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 4px; letter-spacing: 0.5px; }}
    .main {{ padding: 24px 32px; max-width: 1200px; margin: 0 auto; }}
    .section-title {{ font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; margin-top: 28px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    thead tr {{ background: #0f172a; }}
    th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
    .footer {{ text-align: center; font-size: 11px; color: #475569; padding: 28px 0 16px; border-top: 1px solid #1e293b; margin-top: 40px; }}
    .ts {{ font-size: 11px; color: #475569; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="header-title">Reward Curriculum Scheduler</div>
      <div class="header-sub">OCI Robot Cloud — DAgger Training Pipeline | Port 8123</div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <span class="ts">Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span>
      <span class="oracle-badge">ORACLE CONFIDENTIAL</span>
    </div>
  </div>

  <div class="main">

    <!-- Current Stage Banner -->
    <div class="section-title">Current Stage</div>
    <div style="background:#450a0a;border:2px solid #C74634;border-radius:10px;padding:20px 28px">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px">
        <div>
          <div style="font-size:12px;color:#94a3b8;font-family:monospace">Stage {current['id']} / 4</div>
          <div style="font-size:28px;font-weight:800;color:#C74634;font-family:monospace;margin-top:2px">{current['name']}</div>
          <div style="font-size:13px;color:#94a3b8;margin-top:4px">Episodes {current['episode_range'][0]}\u2013{current['episode_range'][1]} &nbsp;|&nbsp; Current episode: ~{CURRENT_EPISODE}</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:40px;font-weight:800;color:#C74634">{current['success_rate_achieved']}%</div>
          <div style="font-size:12px;color:#94a3b8">Success Rate (so far)</div>
        </div>
      </div>
      <!-- Progress bar within stage -->
      <div style="margin-top:16px">
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;margin-bottom:6px">
          <span>Stage Progress</span>
          <span style="color:#C74634">{progress_pct}% ({CURRENT_EPISODE - ep_start}/{ep_end - ep_start} episodes)</span>
        </div>
        <div style="background:#0f172a;border-radius:6px;height:10px">
          <div style="background:linear-gradient(90deg,#C74634,#f97316);width:{progress_pct}%;height:10px;border-radius:6px;transition:width 0.3s"></div>
        </div>
      </div>
      <!-- Next stage threshold -->
      <div style="margin-top:12px;font-size:12px;color:#fca5a5">
        Next stage unlocks at episode {NEXT_STAGE_THRESHOLD_EPISODE} &nbsp;&rarr;&nbsp;
        <span style="color:#94a3b8">{next_stage['name'] if next_stage else 'N/A'}</span>
        {f'(target &gt;{next_stage["success_rate_target"]}% SR)' if next_stage and next_stage.get("success_rate_target") else ''}
      </div>
    </div>

    <!-- Stage Cards -->
    <div class="section-title">All Curriculum Stages</div>
    <div style="display:flex;flex-wrap:wrap;gap:14px">
      {''.join(stage_cards)}
    </div>

    <!-- SR Progression Chart -->
    <div class="section-title">Success Rate Progression</div>
    <div style="overflow-x:auto">{sr_chart}</div>

    <!-- Reward Weight Chart -->
    <div class="section-title">Reward Weight Comparison (Stages 1\u20133)</div>
    <div style="overflow-x:auto">{reward_chart}</div>

    <!-- Current Stage Reward Breakdown -->
    <div class="section-title">Stage 3 (Active) \u2014 Reward Component Weights</div>
    <table>
      <thead>
        <tr><th>Component</th><th>Weight</th></tr>
      </thead>
      <tbody>
        {reward_rows}
      </tbody>
    </table>

    <!-- Training History -->
    <div class="section-title">Training History Summary</div>
    <table>
      <thead>
        <tr><th>Stage</th><th>Name</th><th>Episodes</th><th>Status</th><th>SR Achieved</th><th>Primary Reward</th></tr>
      </thead>
      <tbody>
        {''.join(f"""<tr>
          <td style="padding:8px 12px;font-size:12px;color:#64748b">S{s['id']}</td>
          <td style="padding:8px 12px;font-family:monospace;font-size:12px;color:#38bdf8">{s['name']}</td>
          <td style="padding:8px 12px;font-size:12px;color:#94a3b8">{s['episode_range'][0]}\u2013{s['episode_range'][1] or '\u221e'}</td>
          <td style="padding:8px 12px"><span style="background:{stage_status_bg[s['status']]};color:{stage_status_color[s['status']]};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{s['status']}</span></td>
          <td style="padding:8px 12px;font-size:12px;color:{stage_status_color[s['status']]};font-weight:700">{'\u2014' if s['success_rate_achieved'] is None else str(s['success_rate_achieved'])+'%'}</td>
          <td style="padding:8px 12px;font-family:monospace;font-size:11px;color:#64748b">{'max: '+max(s['rewards'],key=s['rewards'].get)+f' ({max(s[\"rewards\"].values()):.2f})' if s['rewards'] else 'TBD'}</td>
        </tr>""" for s in STAGES)}
      </tbody>
    </table>

  </div>

  <div class="footer">
    Oracle Confidential | OCI Robot Cloud Reward Curriculum Scheduler | Port 8123
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=build_dashboard())


@app.get("/stages")
async def get_stages():
    return JSONResponse(content={"stages": STAGES, "count": len(STAGES)})


@app.get("/current")
async def get_current():
    current = get_stage_by_id(CURRENT_STAGE_ID)
    ep_start, ep_end = current["episode_range"]
    progress_pct = min(100, round(((CURRENT_EPISODE - ep_start) / (ep_end - ep_start)) * 100, 1))
    return JSONResponse(content={
        "current_stage": current,
        "current_episode": CURRENT_EPISODE,
        "progress_pct": progress_pct,
        "next_stage_at_episode": NEXT_STAGE_THRESHOLD_EPISODE,
    })


@app.get("/history")
async def get_history():
    completed = [s for s in STAGES if s["status"] == "COMPLETED"]
    return JSONResponse(content={
        "completed_stages": completed,
        "completed_count": len(completed),
        "total_stages": len(STAGES),
        "sr_progression": [
            {"stage": s["id"], "name": s["name"], "sr": s["success_rate_achieved"]}
            for s in STAGES
        ],
    })


@app.get("/health")
async def health():
    return JSONResponse(content={
        "status": "ok",
        "service": "reward_curriculum",
        "port": 8123,
        "current_stage": CURRENT_STAGE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    try:
        uvicorn.run(app, host="0.0.0.0", port=8123, log_level="info")
    except Exception as exc:
        print(f"[reward_curriculum] Failed to start: {exc}")
        raise


if __name__ == "__main__":
    main()
