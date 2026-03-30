"""real_time_sr_monitor.py — Real-time success rate monitoring for DAgger / eval runs.
Port: 8283
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data: run10 — 412 episodes completed, target 500+
# ---------------------------------------------------------------------------

random.seed(7)

TOTAL_EPISODES = 412
ROLLING_WINDOW = 50
CURRENT_SR = 0.64  # current rolling avg SR
TARGET_SR = 0.70

# SR crossed 0.5 at ep 180, 0.6 at ep 340
SR_THRESHOLDS = [
    {"sr": 0.5, "episode": 180},
    {"sr": 0.6, "episode": 340},
    {"sr": 0.65, "episode": 390},
]


def _generate_episode_outcomes(n=412):
    """Generate episode outcomes (True=success, False=fail, None=timeout)."""
    random.seed(7)
    outcomes = []
    for i in range(n):
        # SR gradually improves; early phase: ~35%, final: ~64%
        base_prob = 0.35 + (i / n) * 0.30
        r = random.random()
        if r < base_prob:
            outcomes.append("success")
        elif r < base_prob + 0.08:
            outcomes.append("timeout")
        else:
            outcomes.append("fail")
    # Inject 3-consecutive-failure streak near ep 408
    outcomes[408] = "fail"
    outcomes[409] = "fail"
    outcomes[410] = "fail"
    outcomes[411] = "success"  # ep 412 is latest
    return outcomes


EPISODE_OUTCOMES = _generate_episode_outcomes(TOTAL_EPISODES)


def _rolling_sr_series(outcomes, window=50):
    """Compute rolling SR at each episode."""
    series = []
    for i in range(len(outcomes)):
        start = max(0, i - window + 1)
        window_outcomes = outcomes[start:i + 1]
        sr = sum(1 for o in window_outcomes if o == "success") / len(window_outcomes)
        series.append(round(sr, 4))
    return series


ROLLING_SR = _rolling_sr_series(EPISODE_OUTCOMES)

# Confidence interval: approximate 95% CI width = 2 * sqrt(p*(1-p)/n)
def _ci_width(sr, n):
    return 2 * math.sqrt(max(sr * (1 - sr), 0.0001) / max(n, 1))


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_live_sr_chart():
    """Rolling SR over last 200 episodes with CI band and threshold markers."""
    recent = ROLLING_SR[-200:]
    offset = max(0, TOTAL_EPISODES - 200)
    W, H = 560, 290
    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(recent)

    def cx(i):
        return pad_l + (i / max(n - 1, 1)) * chart_w

    def cy(sr_val):
        return pad_t + chart_h - sr_val * chart_h

    # CI band
    ci_upper = []
    ci_lower = []
    for i, sr in enumerate(recent):
        ep_i = offset + i
        w_ci = _ci_width(sr, min(ROLLING_WINDOW, ep_i + 1))
        ci_upper.append((cx(i), cy(min(1.0, sr + w_ci / 2))))
        ci_lower.append((cx(i), cy(max(0.0, sr - w_ci / 2))))

    band_pts = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in ci_upper)
    band_pts += " " + " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in reversed(ci_lower))
    ci_band = f'<polygon points="{band_pts}" fill="#38bdf8" opacity="0.15"/>'

    # SR line
    line_pts = " ".join(f"{cx(i):.1f},{cy(sr):.1f}" for i, sr in enumerate(recent))
    sr_line = f'<polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'

    # Current SR dot
    last_x, last_y = cx(n - 1), cy(recent[-1])
    current_dot = f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="#C74634"/>'
    current_dot += f'<text x="{last_x - 5:.1f}" y="{last_y - 10:.1f}" text-anchor="end" fill="#C74634" font-weight="bold" font-size="12">SR={recent[-1]:.3f}</text>'

    # Threshold lines
    threshold_marks = ""
    for th in SR_THRESHOLDS:
        ep_rel = th["episode"] - offset
        if 0 <= ep_rel < n:
            tx = cx(ep_rel)
            ty = cy(th["sr"])
            threshold_marks += f'<line x1="{tx:.1f}" y1="{pad_t}" x2="{tx:.1f}" y2="{pad_t + chart_h}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/>'
            threshold_marks += f'<text x="{tx + 3:.1f}" y="{ty - 4:.1f}" fill="#fbbf24" font-size="10">✓{th["sr"]:.1f} @ep{th["episode"]}</text>'

    # Target SR line
    target_y = cy(TARGET_SR)
    target_line = f'<line x1="{pad_l}" y1="{target_y:.1f}" x2="{pad_l + chart_w}" y2="{target_y:.1f}" stroke="#34d399" stroke-width="1.5" stroke-dasharray="6,3"/>'
    target_line += f'<text x="{pad_l + chart_w - 5}" y="{target_y - 5:.1f}" text-anchor="end" fill="#34d399" font-size="10">target {TARGET_SR}</text>'

    # Y-axis
    yticks = ""
    for sr_t in [0.0, 0.25, 0.5, 0.75, 1.0]:
        ty = cy(sr_t)
        yticks += f'<line x1="{pad_l - 4}" y1="{ty:.1f}" x2="{pad_l + chart_w}" y2="{ty:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        yticks += f'<text x="{pad_l - 8}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{sr_t:.2f}</text>'

    # X-axis episode labels
    xlabels = ""
    for frac, label in [(0, str(offset)), (0.5, str(offset + n // 2)), (1.0, str(offset + n))]:
        lx = pad_l + frac * chart_w
        xlabels += f'<text x="{lx:.1f}" y="{pad_t + chart_h + 18:.1f}" text-anchor="middle" fill="#64748b" font-size="10">ep{label}</text>'

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Live SR — Run10 (50-ep Rolling Avg)</text>'
        + yticks + ci_band + target_line + threshold_marks + sr_line + current_dot + xlabels +
        f'<text x="{pad_l + 5}" y="{pad_t + chart_h - 5}" fill="#38bdf8" font-size="10" opacity="0.7">95% CI band shown</text>'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


def _svg_episode_outcome_timeline():
    """Last 50 episodes as colored squares: success/fail/timeout."""
    last50 = EPISODE_OUTCOMES[-50:]
    offset = TOTAL_EPISODES - 50
    W, H = 560, 180
    pad_l, pad_r, pad_t, pad_b = 20, 20, 40, 50
    chart_w = W - pad_l - pad_r
    cols = 25
    rows = 2
    sq = chart_w / cols - 3

    STATUS_COLOR = {"success": "#34d399", "fail": "#f87171", "timeout": "#fbbf24"}
    squares = ""
    for idx, outcome in enumerate(last50):
        col = idx % cols
        row = idx // cols
        x = pad_l + col * (sq + 3)
        y = pad_t + row * (sq + 3)
        color = STATUS_COLOR[outcome]
        ep_num = offset + idx
        squares += f'<rect x="{x:.1f}" y="{y:.1f}" width="{sq:.1f}" height="{sq:.1f}" fill="{color}" rx="2" opacity="0.9">'
        squares += f'<title>ep{ep_num}: {outcome}</title></rect>'

    # Failure streak indicator — last 3 failures
    streak_label = ""
    streak_count = 0
    for o in reversed(last50):
        if o == "fail":
            streak_count += 1
        else:
            break
    if streak_count >= 3:
        streak_label = f'<rect x="{W//2 - 90}" y="{pad_t + rows*(sq+3) + 8}" width="180" height="22" fill="#7f1d1d" rx="4" opacity="0.8"/>'
        streak_label += f'<text x="{W//2}" y="{pad_t + rows*(sq+3) + 23}" text-anchor="middle" fill="#fca5a5" font-size="12" font-weight="bold">⚠ Failure streak: {streak_count} consecutive fails — review flag</text>'

    # Stats
    success_n = sum(1 for o in last50 if o == "success")
    fail_n = sum(1 for o in last50 if o == "fail")
    timeout_n = sum(1 for o in last50 if o == "timeout")
    stats_y = H - 10
    stats = (
        f'<text x="{pad_l}" y="{stats_y}" fill="#34d399" font-size="11">success: {success_n}</text>'
        f'<text x="{pad_l + 90}" y="{stats_y}" fill="#f87171" font-size="11">fail: {fail_n}</text>'
        f'<text x="{pad_l + 160}" y="{stats_y}" fill="#fbbf24" font-size="11">timeout: {timeout_n}</text>'
        f'<text x="{pad_l + 250}" y="{stats_y}" fill="#94a3b8" font-size="11">SR(50): {success_n/50:.2f}</text>'
    )

    # Legend
    legend = (
        f'<rect x="{W - 200}" y="8" width="12" height="12" fill="#34d399" rx="2"/>'
        f'<text x="{W - 184}" y="19" fill="#94a3b8" font-size="11">success</text>'
        f'<rect x="{W - 130}" y="8" width="12" height="12" fill="#f87171" rx="2"/>'
        f'<text x="{W - 114}" y="19" fill="#94a3b8" font-size="11">fail</text>'
        f'<rect x="{W - 80}" y="8" width="12" height="12" fill="#fbbf24" rx="2"/>'
        f'<text x="{W - 64}" y="19" fill="#94a3b8" font-size="11">timeout</text>'
    )

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Episode Outcomes — Last 50 (ep{offset}–{offset+49})</text>'
        + legend + squares + streak_label + stats +
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html():
    svg1 = _svg_live_sr_chart()
    svg2 = _svg_episode_outcome_timeline()

    # Key metrics
    current_rolling_sr = ROLLING_SR[-1]
    ci_w = _ci_width(current_rolling_sr, ROLLING_WINDOW)
    ci_low = round(max(0, current_rolling_sr - ci_w / 2), 4)
    ci_high = round(min(1, current_rolling_sr + ci_w / 2), 4)
    eps_to_target = max(0, int((TARGET_SR - current_rolling_sr) / 0.001))  # rough ETA
    streak_count = 0
    for o in reversed(EPISODE_OUTCOMES):
        if o == "fail":
            streak_count += 1
        else:
            break
    total_success = sum(1 for o in EPISODE_OUTCOMES if o == "success")
    total_fail = sum(1 for o in EPISODE_OUTCOMES if o == "fail")
    total_timeout = sum(1 for o in EPISODE_OUTCOMES if o == "timeout")

    threshold_rows = ""
    for th in SR_THRESHOLDS:
        threshold_rows += f"""
        <tr style="border-bottom:1px solid #0f172a">
          <td style="padding:6px 12px;color:#fbbf24">SR &ge; {th['sr']}</td>
          <td style="padding:6px 12px;color:#34d399">ep {th['episode']}</td>
          <td style="padding:6px 12px;color:#64748b">{TOTAL_EPISODES - th['episode']} eps ago</td>
        </tr>"""

    streak_color = "#f87171" if streak_count >= 3 else "#fbbf24" if streak_count >= 2 else "#34d399"
    streak_badge = f'<span style="color:{streak_color};font-weight:bold">{streak_count} {"⚠ review flag" if streak_count >= 3 else ""}</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Real-Time SR Monitor — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; margin:0; padding:20px; }}
    h1 {{ color:#C74634; margin:0 0 4px 0; font-size:1.6rem; }}
    .subtitle {{ color:#64748b; font-size:0.9rem; margin-bottom:20px; }}
    .metrics {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:20px; }}
    .metric-card {{ background:#1e293b; border-radius:8px; padding:14px 18px; min-width:130px; }}
    .metric-val {{ font-size:1.8rem; font-weight:bold; color:#38bdf8; }}
    .metric-label {{ font-size:0.78rem; color:#64748b; margin-top:2px; }}
    .charts {{ display:flex; gap:20px; flex-wrap:wrap; margin-bottom:24px; }}
    .section {{ background:#1e293b; border-radius:8px; padding:16px; margin-bottom:20px; }}
    .section h2 {{ color:#38bdf8; font-size:1rem; margin:0 0 12px 0; }}
    table {{ border-collapse:collapse; }}
    th {{ color:#64748b; font-size:11px; text-transform:uppercase; padding:4px 12px; text-align:left; }}
    tr:hover {{ background:#243044; }}
    .run-badge {{ background:#1e3a5f; color:#38bdf8; padding:2px 10px; border-radius:12px; font-size:12px; }}
    .alert-banner {{ background:#7f1d1d; border:1px solid #991b1b; border-radius:8px; padding:12px 18px; margin-bottom:20px; color:#fca5a5; font-weight:bold; }}
  </style>
</head>
<body>
  <h1>Real-Time SR Monitor</h1>
  <div class="subtitle">OCI Robot Cloud — Live DAgger &amp; eval run monitoring | Port 8283</div>

  {'<div class="alert-banner">⚠ Failure streak detected: ' + str(streak_count) + ' consecutive failures — manual review recommended</div>' if streak_count >= 3 else ''}

  <div class="metrics">
    <div class="metric-card">
      <div class="metric-val" style="color:#C74634">{current_rolling_sr:.3f}</div>
      <div class="metric-label">Current Rolling SR (50-ep)</div>
    </div>
    <div class="metric-card">
      <div class="metric-val">{TOTAL_EPISODES}</div>
      <div class="metric-label">Episodes Completed</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:{streak_color}">{streak_count}</div>
      <div class="metric-label">Failure Streak {"⚠" if streak_count >= 3 else ""}</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="font-size:1.2rem">[{ci_low:.3f}, {ci_high:.3f}]</div>
      <div class="metric-label">95% CI</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:#fbbf24">~{eps_to_target}</div>
      <div class="metric-label">Est. eps to SR {TARGET_SR}</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:#34d399">{total_success}</div>
      <div class="metric-label">Total Successes</div>
    </div>
  </div>

  <div class="charts">
    <div>{svg1}</div>
    <div>{svg2}</div>
  </div>

  <div style="display:flex;gap:20px;flex-wrap:wrap">
    <div class="section" style="min-width:280px">
      <h2>SR Threshold Crossings</h2>
      <table>
        <tr><th>Threshold</th><th>Crossed At</th><th>Since</th></tr>
        {threshold_rows}
        <tr style="border-bottom:1px solid #0f172a">
          <td style="padding:6px 12px;color:#94a3b8">SR &ge; {TARGET_SR} (target)</td>
          <td style="padding:6px 12px;color:#C74634">not yet</td>
          <td style="padding:6px 12px;color:#64748b">est. ~{eps_to_target} eps</td>
        </tr>
      </table>
    </div>

    <div class="section" style="min-width:220px">
      <h2>Run Info</h2>
      <table>
        <tr><td style="padding:5px 12px;color:#64748b">Run</td><td style="padding:5px 12px"><span class="run-badge">run10</span></td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">Type</td><td style="padding:5px 12px;color:#a78bfa">DAgger</td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">Target eps</td><td style="padding:5px 12px;color:#e2e8f0">500+</td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">Successes</td><td style="padding:5px 12px;color:#34d399">{total_success}</td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">Failures</td><td style="padding:5px 12px;color:#f87171">{total_fail}</td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">Timeouts</td><td style="padding:5px 12px;color:#fbbf24">{total_timeout}</td></tr>
        <tr><td style="padding:5px 12px;color:#64748b">CI width</td><td style="padding:5px 12px;color:#38bdf8">{ci_w:.4f}</td></tr>
      </table>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Real-Time SR Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/status")
    def status():
        current_rolling_sr = ROLLING_SR[-1]
        ci_w = _ci_width(current_rolling_sr, ROLLING_WINDOW)
        streak_count = 0
        for o in reversed(EPISODE_OUTCOMES):
            if o == "fail":
                streak_count += 1
            else:
                break
        return JSONResponse({
            "run": "run10",
            "type": "dagger",
            "episodes_completed": TOTAL_EPISODES,
            "target_episodes": 500,
            "current_rolling_sr": current_rolling_sr,
            "ci_95_low": round(max(0, current_rolling_sr - ci_w / 2), 4),
            "ci_95_high": round(min(1, current_rolling_sr + ci_w / 2), 4),
            "ci_width": round(ci_w, 4),
            "failure_streak": streak_count,
            "review_flag": streak_count >= 3,
            "target_sr": TARGET_SR,
            "sr_threshold_crossings": SR_THRESHOLDS,
        })

    @app.get("/history")
    def history(last_n: int = 200):
        outcomes = EPISODE_OUTCOMES[-last_n:]
        rolling = ROLLING_SR[-last_n:]
        offset = max(0, TOTAL_EPISODES - last_n)
        return JSONResponse({
            "offset_episode": offset,
            "count": len(outcomes),
            "outcomes": outcomes,
            "rolling_sr": rolling,
        })

    @app.get("/metrics")
    def metrics():
        total_success = sum(1 for o in EPISODE_OUTCOMES if o == "success")
        total_fail = sum(1 for o in EPISODE_OUTCOMES if o == "fail")
        total_timeout = sum(1 for o in EPISODE_OUTCOMES if o == "timeout")
        return JSONResponse({
            "total_episodes": TOTAL_EPISODES,
            "total_success": total_success,
            "total_fail": total_fail,
            "total_timeout": total_timeout,
            "overall_sr": round(total_success / TOTAL_EPISODES, 4),
            "rolling_sr_current": ROLLING_SR[-1],
            "rolling_window": ROLLING_WINDOW,
        })

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8283)
    else:
        print("FastAPI not found — running stdlib fallback on port 8283")
        HTTPServer(("0.0.0.0", 8283), Handler).serve_forever()
