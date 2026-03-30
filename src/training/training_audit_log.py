"""Training Audit Log — Immutable audit log for all training events for
compliance and reproducibility. Port 8323."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAVE_FASTAPI = True
except ImportError:
    _HAVE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Deterministic mock data
# ---------------------------------------------------------------------------

random.seed(42)

EVENT_TYPES = [
    "model_created",
    "checkpoint_saved",
    "eval_run",
    "parameter_change",
    "data_ingested",
    "promotion",
]

EVENT_COLORS = {
    "model_created":    "#C74634",
    "checkpoint_saved": "#38bdf8",
    "eval_run":         "#22d3ee",
    "parameter_change": "#fbbf24",
    "data_ingested":    "#a78bfa",
    "promotion":        "#34d399",
}

TOTAL_DAYS = 90
TOTAL_EVENTS = 847

def _gen_events():
    """Generate deterministic audit events over 90 days."""
    base = datetime(2026, 1, 1)
    events = []
    counts = {et: 0 for et in EVENT_TYPES}
    # distribute 847 events roughly proportionally
    dist = {"checkpoint_saved": 320, "eval_run": 240, "data_ingested": 140,
            "parameter_change": 80, "model_created": 42, "promotion": 25}
    for etype, n in dist.items():
        for _ in range(n):
            day = random.randint(0, TOTAL_DAYS - 1)
            hour = random.randint(0, 23)
            ts = base + timedelta(days=day, hours=hour, minutes=random.randint(0, 59))
            events.append({"ts": ts, "type": etype, "day": day})
            counts[etype] += 1
    events.sort(key=lambda e: e["ts"])
    return events, counts

AUDIT_EVENTS, EVENT_COUNTS = _gen_events()

# Events per day (for timeline)
DAY_COUNTS = {}
for ev in AUDIT_EVENTS:
    DAY_COUNTS.setdefault(ev["day"], {et: 0 for et in EVENT_TYPES})
    DAY_COUNTS[ev["day"]][ev["type"]] += 1

# Reproducibility data for 5 historical runs
REPRO_RUNS = [
    {"run": "run1", "original_sr": 0.82, "rerun_sr": 0.83, "corr": 0.98},
    {"run": "run2", "original_sr": 0.76, "rerun_sr": 0.77, "corr": 0.97},
    {"run": "run3", "original_sr": 0.79, "rerun_sr": 0.79, "corr": 0.99},
    {"run": "run4", "original_sr": 0.83, "rerun_sr": 0.82, "corr": 0.96},
    {"run": "run5", "original_sr": 0.74, "rerun_sr": 0.68, "corr": 0.91},  # seed issue
]

SUMMARY = {
    "total_events": TOTAL_EVENTS,
    "audit_coverage_pct": 100.0,
    "avg_repro_corr": round(sum(r["corr"] for r in REPRO_RUNS) / len(REPRO_RUNS), 3),
    "compliance_checklist_pct": 94.7,
    "audit_query_latency_ms": 3.2,
    "days_covered": TOTAL_DAYS,
}

# ---------------------------------------------------------------------------
# SVG: Audit event timeline (90-day stacked bar)
# ---------------------------------------------------------------------------

def build_timeline_svg() -> str:
    W, H = 720, 300
    MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 40, 20, 30, 50
    PW = W - MARGIN_L - MARGIN_R
    PH = H - MARGIN_T - MARGIN_B

    max_day = max((sum(DAY_COUNTS.get(d, {}).values()) for d in range(TOTAL_DAYS)), default=1)

    # Sample every 3rd day to keep SVG concise
    sample_days = list(range(0, TOTAL_DAYS, 3))
    bar_w = max(1, PW // len(sample_days) - 1)

    bars = ""
    for idx, day in enumerate(sample_days):
        bx = MARGIN_L + idx * (PW // len(sample_days))
        day_data = DAY_COUNTS.get(day, {et: 0 for et in EVENT_TYPES})
        total = sum(day_data.values())
        y_cursor = MARGIN_T + PH
        for et in EVENT_TYPES:
            cnt = day_data.get(et, 0)
            if cnt == 0:
                continue
            bh = max(1, int(PH * cnt / max(max_day, 1)))
            color = EVENT_COLORS[et]
            bars += f'<rect x="{bx}" y="{y_cursor - bh}" width="{bar_w}" height="{bh}" fill="{color}" opacity="0.85"/>\n'
            y_cursor -= bh

    # X axis labels (every 15 days)
    xlabels = ""
    for d in range(0, TOTAL_DAYS, 15):
        idx = d // 3
        bx = MARGIN_L + idx * (PW // len(sample_days))
        lbl = (datetime(2026, 1, 1) + timedelta(days=d)).strftime("%b %d")
        xlabels += f'<text x="{bx}" y="{H - 6}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">{lbl}</text>\n'

    # Y axis
    yaxis = f'<line x1="{MARGIN_L}" y1="{MARGIN_T}" x2="{MARGIN_L}" y2="{MARGIN_T+PH}" stroke="#334155" stroke-width="1"/>\n'
    yaxis += f'<text x="{MARGIN_L-4}" y="{MARGIN_T+PH}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">0</text>\n'
    yaxis += f'<text x="{MARGIN_L-4}" y="{MARGIN_T}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">{max_day}</text>\n'

    # Legend
    legend = ""
    for i, (et, color) in enumerate(EVENT_COLORS.items()):
        lx = MARGIN_L + i * 110
        legend += f'<rect x="{lx}" y="{H+4}" width="8" height="8" fill="{color}"/>'
        legend += f'<text x="{lx+11}" y="{H+12}" fill="#94a3b8" font-size="9" font-family="monospace">{et}</text>'

    total_label = f'<text x="{W//2}" y="{MARGIN_T-8}" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold" font-family="monospace">Audit Event Timeline — 90 Days (847 Events)</text>'

    return f'''<svg width="{W}" height="{H+26}" viewBox="0 0 {W} {H+26}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H+26}" fill="#1e293b" rx="8"/>
  {total_label}{bars}{xlabels}{yaxis}{legend}
</svg>'''


# ---------------------------------------------------------------------------
# SVG: Reproducibility verification bars
# ---------------------------------------------------------------------------

def build_repro_svg() -> str:
    W, H = 520, 320
    MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 70, 30, 40, 60
    PW = W - MARGIN_L - MARGIN_R
    PH = H - MARGIN_T - MARGIN_B

    runs = REPRO_RUNS
    N = len(runs)
    group_w = PW // N
    bar_w = group_w // 3

    max_sr = 1.0
    min_sr = 0.60

    def y_for(sr):
        frac = (sr - min_sr) / (max_sr - min_sr)
        return MARGIN_T + PH - int(PH * frac)

    bars = ""
    xlabels = ""
    for i, run in enumerate(runs):
        gx = MARGIN_L + i * group_w
        # original
        yo = y_for(run["original_sr"])
        bh_o = MARGIN_T + PH - yo
        bars += f'<rect x="{gx+2}" y="{yo}" width="{bar_w}" height="{bh_o}" fill="#38bdf8" opacity="0.75" rx="2"/>\n'
        bars += f'<text x="{gx+2+bar_w//2}" y="{yo-3}" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="monospace">{run["original_sr"]:.2f}</text>\n'
        # rerun
        yr = y_for(run["rerun_sr"])
        bh_r = MARGIN_T + PH - yr
        bars += f'<rect x="{gx+bar_w+5}" y="{yr}" width="{bar_w}" height="{bh_r}" fill="#C74634" opacity="0.75" rx="2"/>\n'
        bars += f'<text x="{gx+bar_w+5+bar_w//2}" y="{yr-3}" text-anchor="middle" fill="#C74634" font-size="9" font-family="monospace">{run["rerun_sr"]:.2f}</text>\n'
        # corr badge
        corr_color = "#34d399" if run["corr"] >= 0.95 else "#fbbf24"
        bars += f'<text x="{gx+group_w//2}" y="{MARGIN_T+PH+14}" text-anchor="middle" fill="{corr_color}" font-size="10" font-family="monospace">r={run["corr"]:.2f}</text>\n'
        xlabels += f'<text x="{gx+group_w//2}" y="{MARGIN_T+PH+26}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{run["run"]}</text>\n'

    # Y axis grid
    yaxis = f'<line x1="{MARGIN_L}" y1="{MARGIN_T}" x2="{MARGIN_L}" y2="{MARGIN_T+PH}" stroke="#334155" stroke-width="1"/>\n'
    for val in [0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0]:
        yv = y_for(val)
        yaxis += f'<line x1="{MARGIN_L}" y1="{yv}" x2="{W-MARGIN_R}" y2="{yv}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>\n'
        yaxis += f'<text x="{MARGIN_L-4}" y="{yv+4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{val:.2f}</text>\n'

    legend = f'''
      <rect x="{MARGIN_L}" y="{H-12}" width="8" height="8" fill="#38bdf8"/>
      <text x="{MARGIN_L+12}" y="{H-5}" fill="#94a3b8" font-size="10" font-family="monospace">Original SR</text>
      <rect x="{MARGIN_L+110}" y="{H-12}" width="8" height="8" fill="#C74634"/>
      <text x="{MARGIN_L+122}" y="{H-5}" fill="#94a3b8" font-size="10" font-family="monospace">Re-run SR</text>
      <text x="{MARGIN_L+240}" y="{H-5}" fill="#64748b" font-size="10" font-family="monospace">r = Pearson correlation</text>
    '''

    title = f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold" font-family="monospace">Reproducibility Verification (avg r=0.97)</text>'

    return f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  {title}{bars}{xlabels}{yaxis}{legend}
</svg>'''


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    timeline = build_timeline_svg()
    repro = build_repro_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    s = SUMMARY

    def metric_card(label, value, sub=""):
        return f'''
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;">
          <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">{label}</div>
          <div style="color:#f1f5f9;font-size:26px;font-weight:bold;margin:6px 0;">{value}</div>
          <div style="color:#64748b;font-size:11px;">{sub}</div>
        </div>'''

    event_rows = ""
    for et in EVENT_TYPES:
        cnt = EVENT_COUNTS.get(et, 0)
        color = EVENT_COLORS[et]
        pct = round(100 * cnt / TOTAL_EVENTS, 1)
        event_rows += f'<tr><td><span style="color:{color};">{et}</span></td><td>{cnt}</td><td>{pct}%</td></tr>'

    repro_rows = ""
    for r in REPRO_RUNS:
        corr_color = "#34d399" if r["corr"] >= 0.95 else "#fbbf24"
        note = "" if r["corr"] >= 0.95 else "batch seed fix applied"
        repro_rows += f'<tr><td>{r["run"]}</td><td>{r["original_sr"]:.2f}</td><td>{r["rerun_sr"]:.2f}</td><td style="color:{corr_color};">{r["corr"]:.2f}</td><td style="color:#64748b;font-size:11px;">{note}</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Training Audit Log</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin: 28px 0 12px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 16px; }}
    .charts {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
    .chart-wide {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; overflow-x: auto; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ color: #38bdf8; text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 5px 8px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
    tr:hover td {{ background: #1e293b; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
    .ts {{ color: #475569; font-size: 11px; margin-top: 32px; text-align: right; }}
  </style>
</head>
<body>
  <h1>Training Audit Log</h1>
  <p style="color:#64748b;font-size:12px;">Immutable audit trail &bull; {s['days_covered']}-day window &bull; Compliance-ready &bull; Port 8323</p>

  <h2>Summary Metrics</h2>
  <div class="grid">
    {metric_card("Total Events", f"{s['total_events']:,}", f"over {s['days_covered']} days")}
    {metric_card("Audit Coverage", f"{s['audit_coverage_pct']:.1f}%", "all events captured")}
    {metric_card("Avg Repro Correlation", f"{s['avg_repro_corr']:.3f}", "across 5 historical runs")}
    {metric_card("Compliance Checklist", f"{s['compliance_checklist_pct']}%", "SOC2-ready")}
    {metric_card("Audit Query Latency", f"{s['audit_query_latency_ms']} ms", "p99 response time")}
  </div>

  <h2>Event Timeline (90 Days)</h2>
  <div class="chart-wide">{timeline}</div>

  <h2>Reproducibility Verification &amp; Event Breakdown</h2>
  <div class="two-col">
    <div class="chart-wide">{repro}</div>
    <div>
      <table>
        <thead><tr><th>Event Type</th><th>Count</th><th>Share</th></tr></thead>
        <tbody>{event_rows}</tbody>
      </table>
      <br/>
      <table>
        <thead><tr><th>Run</th><th>Original SR</th><th>Re-run SR</th><th>Correlation</th><th>Notes</th></tr></thead>
        <tbody>{repro_rows}</tbody>
      </table>
    </div>
  </div>

  <h2>Compliance Checklist</h2>
  <table>
    <thead><tr><th>Item</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>All training events logged with timestamp + actor</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Checkpoints linked to training run ID</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Data ingestion events with source hash</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Parameter changes require approval workflow</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Promotion events include eval gate results</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Audit log tamper-proof (append-only store)</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>90-day retention policy enforced</td><td style="color:#34d399;">PASS</td></tr>
      <tr><td>Reproducibility re-run gap &lt; 5% for all runs</td><td style="color:#fbbf24;">WARN (run5: 8.1%)</td></tr>
    </tbody>
  </table>

  <div class="ts">Generated {ts} &bull; training_audit_log.py port 8323</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAVE_FASTAPI:
    app = FastAPI(title="Training Audit Log", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "training_audit_log", "port": 8323}

    @app.get("/api/summary")
    def summary():
        return SUMMARY

    @app.get("/api/events")
    def events(limit: int = 50):
        return [{"ts": str(e["ts"]), "type": e["type"]} for e in AUDIT_EVENTS[-limit:]]

    @app.get("/api/reproducibility")
    def reproducibility():
        return {"runs": REPRO_RUNS, "avg_correlation": SUMMARY["avg_repro_corr"]}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, fmt, *args):
            pass

    def run_stdlib(port=8323):
        print(f"[training_audit_log] stdlib fallback on :{port}")
        HTTPServer(("", port), Handler).serve_forever()


if __name__ == "__main__":
    if _HAVE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8323)
    else:
        run_stdlib(8323)
