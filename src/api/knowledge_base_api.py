"""knowledge_base_api.py — OCI Robot Cloud Knowledge Base API Service (port 8311)

API for querying OCI Robot Cloud internal knowledge base and runbook documentation.
FastAPI service with dark-theme HTML dashboard, SVG charts, and mock data.
"""

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TOPIC_AREAS = [
    {"name": "deployment",     "docs": 142, "freshness": 0.52, "outdated": True,  "avg_age_days": 31},
    {"name": "training",       "docs": 118, "freshness": 0.84, "outdated": False, "avg_age_days": 8},
    {"name": "eval",           "docs": 97,  "freshness": 0.79, "outdated": False, "avg_age_days": 11},
    {"name": "troubleshooting","docs": 156, "freshness": 0.71, "outdated": False, "avg_age_days": 14},
    {"name": "SDK",            "docs": 89,  "freshness": 0.88, "outdated": False, "avg_age_days": 6},
    {"name": "security",       "docs": 73,  "freshness": 0.91, "outdated": False, "avg_age_days": 4},
    {"name": "billing",        "docs": 62,  "freshness": 0.66, "outdated": False, "avg_age_days": 18},
    {"name": "sim_setup",      "docs": 110, "freshness": 0.58, "outdated": True,  "avg_age_days": 26},
]

TOTAL_ARTICLES = sum(t["docs"] for t in TOPIC_AREAS)  # 847

# 30-day query volume and resolution history
# Each entry: (day_offset_from_today, queries, auto_resolved)
random.seed(2026_03_30)
QUERY_HISTORY = []
for i in range(30):
    queries = int(180 + 40 * math.sin(i / 5) + random.gauss(0, 12))
    # Resolution rate linearly improving from ~60% (day 0) to ~82% (day 29)
    rate = 0.60 + (0.22 * i / 29) + random.gauss(0, 0.015)
    rate = max(0.55, min(0.88, rate))
    auto_resolved = int(queries * rate)
    QUERY_HISTORY.append({"day": i, "queries": queries, "auto_resolved": auto_resolved, "rate": round(rate, 3)})

SUMMARY = {
    "total_articles": TOTAL_ARTICLES,
    "auto_resolution_rate": 0.82,
    "auto_resolution_at_launch": 0.60,
    "knowledge_gap_score": 0.23,
    "critical_outdated_articles": 3,
    "query_to_ticket_escalation_rate": 0.18,
    "most_queried_topic": "troubleshooting",
    "troubleshooting_query_share": 0.34,
    "avg_article_freshness": round(sum(t["freshness"] for t in TOPIC_AREAS) / len(TOPIC_AREAS), 3),
    "last_updated": "2026-03-30T06:00:00Z",
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def coverage_bar_svg() -> str:
    """Horizontal bar chart: doc count + freshness per topic area."""
    W, H = 540, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 20, 36, 20
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(TOPIC_AREAS)
    row_h = chart_h / n
    max_docs = max(t["docs"] for t in TOPIC_AREAS)

    bars = ""
    for i, t in enumerate(TOPIC_AREAS):
        y = PAD_T + i * row_h
        bar_w = (t["docs"] / max_docs) * chart_w * 0.6
        fresh_w = (t["freshness"]) * chart_w * 0.35
        bar_color = "#ef4444" if t["outdated"] else "#38bdf8"
        fresh_color = "#ef4444" if t["freshness"] < 0.65 else "#22c55e" if t["freshness"] > 0.80 else "#f59e0b"

        # Topic label
        bars += (f'<text x="{PAD_L-6}" y="{y + row_h*0.62:.1f}" text-anchor="end" '
                 f'font-size="11" fill="#cbd5e1">{t["name"]}</text>\n')
        # Doc count bar
        bars += (f'<rect x="{PAD_L}" y="{y + row_h*0.1:.1f}" width="{bar_w:.1f}" '
                 f'height="{row_h*0.38:.1f}" rx="3" fill="{bar_color}" opacity="0.85"/>\n'
                 f'<text x="{PAD_L + bar_w + 4:.1f}" y="{y + row_h*0.38:.1f}" '
                 f'font-size="9" fill="#94a3b8">{t["docs"]} docs</text>\n')
        # Freshness bar
        bars += (f'<rect x="{PAD_L}" y="{y + row_h*0.54:.1f}" width="{fresh_w:.1f}" '
                 f'height="{row_h*0.30:.1f}" rx="3" fill="{fresh_color}" opacity="0.75"/>\n'
                 f'<text x="{PAD_L + fresh_w + 4:.1f}" y="{y + row_h*0.76:.1f}" '
                 f'font-size="9" fill="#64748b">{t["freshness"]:.0%}</text>\n')

    # Outdated badge overlay
    outdated_legend = (f'<rect x="{PAD_L}" y="8" width="10" height="10" fill="#ef4444"/>'
                       f'<text x="{PAD_L+14}" y="17" font-size="9" fill="#cbd5e1">Outdated section</text>'
                       f'<rect x="{PAD_L+110}" y="8" width="10" height="10" fill="#38bdf8"/>'
                       f'<text x="{PAD_L+124}" y="17" font-size="9" fill="#cbd5e1">Current section</text>')

    title = (f'<text x="{W//2}" y="22" text-anchor="middle" font-size="13" '
             f'font-weight="bold" fill="#f1f5f9">KB Coverage — Docs &amp; Freshness by Topic</text>')
    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#1e293b;border-radius:8px">\n'
            f'{title}{outdated_legend}{bars}</svg>')


def query_trend_svg() -> str:
    """Line chart: daily queries + auto-resolution rate over 30 days."""
    W, H = 540, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 45, 55, 34, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(QUERY_HISTORY)
    max_q = max(h["queries"] for h in QUERY_HISTORY)

    def sx(i): return PAD_L + (i / (n - 1)) * chart_w
    def sy_q(v): return PAD_T + chart_h - (v / (max_q * 1.1)) * chart_h
    def sy_r(v): return PAD_T + chart_h - v * chart_h  # 0..1 → full height

    # Grid
    grid = ""
    for yv in range(0, max_q + 50, 50):
        gy = sy_q(yv)
        if gy < PAD_T: break
        grid += (f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" '
                 f'stroke="#1e3a5f" stroke-width="1"/>\n'
                 f'<text x="{PAD_L-4}" y="{gy+4:.1f}" text-anchor="end" font-size="8" fill="#64748b">{yv}</text>\n')
    for i in range(0, n, 5):
        gx = sx(i)
        grid += (f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+chart_h}" '
                 f'stroke="#1e3a5f" stroke-width="1"/>\n'
                 f'<text x="{gx:.1f}" y="{PAD_T+chart_h+14:.1f}" text-anchor="middle" '
                 f'font-size="8" fill="#64748b">d-{n-1-i}</text>\n')

    # Total queries area + line
    area_pts = f"{sx(0):.1f},{sy_q(0):.1f} " + " ".join(
        f"{sx(i):.1f},{sy_q(h['queries']):.1f}" for i, h in enumerate(QUERY_HISTORY)
    ) + f" {sx(n-1):.1f},{sy_q(0):.1f}"
    area = f'<polygon points="{area_pts}" fill="#38bdf820"/>\n'

    q_pts = " ".join(f"{sx(i):.1f},{sy_q(h['queries']):.1f}" for i, h in enumerate(QUERY_HISTORY))
    q_line = f'<polyline points="{q_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>\n'

    auto_pts = " ".join(f"{sx(i):.1f},{sy_q(h['auto_resolved']):.1f}" for i, h in enumerate(QUERY_HISTORY))
    auto_line = f'<polyline points="{auto_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>\n'

    # Resolution rate line on secondary axis (right)
    rate_pts = " ".join(f"{sx(i):.1f},{sy_r(h['rate']):.1f}" for i, h in enumerate(QUERY_HISTORY))
    rate_line = f'<polyline points="{rate_pts}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5,3"/>\n'

    # Right-axis labels for resolution rate
    right_axis = ""
    for rv in [0.60, 0.70, 0.80]:
        ry = sy_r(rv)
        right_axis += (f'<text x="{W-PAD_R+4}" y="{ry+4:.1f}" font-size="8" fill="#f59e0b">{int(rv*100)}%</text>\n')

    # Axes
    axes = (f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>\n'
            f'<line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{W-PAD_R}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>\n')

    title = (f'<text x="{W//2}" y="20" text-anchor="middle" font-size="13" '
             f'font-weight="bold" fill="#f1f5f9">30-Day Query Volume &amp; Auto-Resolution Rate</text>')
    xlabel = f'<text x="{W//2}" y="{H-5}" text-anchor="middle" font-size="9" fill="#64748b">Days Ago</text>'
    ylabel = (f'<text x="10" y="{PAD_T+chart_h//2}" text-anchor="middle" font-size="9" fill="#94a3b8" '
              f'transform="rotate(-90,10,{PAD_T+chart_h//2})">Queries / Day</text>')
    legend = (f'<rect x="{PAD_L+10}" y="{PAD_T+6}" width="10" height="8" fill="#38bdf8"/>'
              f'<text x="{PAD_L+24}" y="{PAD_T+14}" font-size="9" fill="#cbd5e1">Total Queries</text>'
              f'<rect x="{PAD_L+110}" y="{PAD_T+6}" width="10" height="8" fill="#22c55e"/>'
              f'<text x="{PAD_L+124}" y="{PAD_T+14}" font-size="9" fill="#cbd5e1">Auto-Resolved</text>'
              f'<line x1="{PAD_L+220}" y1="{PAD_T+10}" x2="{PAD_L+230}" y2="{PAD_T+10}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,2"/>'
              f'<text x="{PAD_L+234}" y="{PAD_T+14}" font-size="9" fill="#f59e0b">Resolution Rate</text>')

    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#1e293b;border-radius:8px">\n'
            f'{title}{xlabel}{ylabel}\n{grid}{axes}{area}{q_line}{auto_line}{rate_line}{right_axis}{legend}</svg>')


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def make_html() -> str:
    cov_svg = coverage_bar_svg()
    trend_svg = query_trend_svg()

    topic_rows = ""
    for t in TOPIC_AREAS:
        fresh_color = "#ef4444" if t["freshness"] < 0.65 else "#22c55e" if t["freshness"] > 0.80 else "#f59e0b"
        flag = " ⚠ outdated" if t["outdated"] else ""
        topic_rows += f"""
        <tr>
          <td style="padding:6px 10px;color:#e2e8f0">{t['name']}{flag}</td>
          <td style="padding:6px 10px;color:#38bdf8;text-align:right">{t['docs']}</td>
          <td style="padding:6px 10px;color:{fresh_color};text-align:right">{t['freshness']:.0%}</td>
          <td style="padding:6px 10px;color:#94a3b8;text-align:right">{t['avg_age_days']}d</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Knowledge Base API — Port 8311</title>
  <style>
    body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .header {{ background:#1e293b; padding:20px 32px; border-bottom:3px solid #C74634; display:flex; align-items:center; gap:16px; }}
    .header h1 {{ margin:0; font-size:22px; color:#f1f5f9; }}
    .header .sub {{ font-size:13px; color:#94a3b8; margin-top:4px; }}
    .badge {{ background:#C74634; color:#fff; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold; }}
    .kpi-row {{ display:flex; gap:16px; padding:24px 32px 0; flex-wrap:wrap; }}
    .kpi {{ background:#1e293b; border-radius:10px; padding:18px 24px; min-width:160px; border-left:4px solid #38bdf8; }}
    .kpi.warn {{ border-left-color:#f59e0b; }}
    .kpi.good {{ border-left-color:#22c55e; }}
    .kpi .val {{ font-size:28px; font-weight:bold; color:#38bdf8; }}
    .kpi.warn .val {{ color:#f59e0b; }}
    .kpi.good .val {{ color:#22c55e; }}
    .kpi .lbl {{ font-size:12px; color:#94a3b8; margin-top:4px; }}
    .content {{ display:flex; gap:24px; padding:24px 32px; flex-wrap:wrap; }}
    .panel {{ background:#1e293b; border-radius:10px; padding:20px; flex:1; min-width:320px; }}
    .panel h2 {{ font-size:14px; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin:0 0 14px; }}
    table {{ border-collapse:collapse; width:100%; }}
    th {{ background:#0f172a; padding:7px 10px; text-align:left; font-size:11px; color:#64748b; text-transform:uppercase; }}
    tr:nth-child(even) {{ background:#162032; }}
    .charts {{ display:flex; gap:24px; flex-wrap:wrap; padding:0 32px 24px; }}
    .footer {{ padding:14px 32px; font-size:11px; color:#334155; border-top:1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Knowledge Base API</h1>
      <div class="sub">OCI Robot Cloud · Runbook &amp; Documentation Intelligence · Port 8311</div>
    </div>
    <div style="margin-left:auto"><span class="badge">LIVE</span></div>
  </div>

  <div class="kpi-row">
    <div class="kpi good">
      <div class="val">{SUMMARY['auto_resolution_rate']:.0%}</div>
      <div class="lbl">Auto-Resolution Rate</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['total_articles']}</div>
      <div class="lbl">Total KB Articles</div>
    </div>
    <div class="kpi warn">
      <div class="val">{SUMMARY['knowledge_gap_score']:.0%}</div>
      <div class="lbl">Knowledge Gap Score</div>
    </div>
    <div class="kpi warn">
      <div class="val">{SUMMARY['critical_outdated_articles']}</div>
      <div class="lbl">Critical Outdated Articles</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['query_to_ticket_escalation_rate']:.0%}</div>
      <div class="lbl">Escalation Rate</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['avg_article_freshness']:.0%}</div>
      <div class="lbl">Avg Article Freshness</div>
    </div>
  </div>

  <div class="content">
    <div class="panel">
      <h2>Topic Area Breakdown</h2>
      <table>
        <thead><tr>
          <th>Topic</th><th style="text-align:right">Docs</th><th style="text-align:right">Freshness</th><th style="text-align:right">Avg Age</th>
        </tr></thead>
        <tbody>{topic_rows}</tbody>
      </table>
    </div>
    <div class="panel" style="max-width:380px;flex:0 0 auto">
      <h2>Key Insights</h2>
      <ul style="color:#94a3b8;font-size:13px;line-height:1.8;padding-left:18px">
        <li>Auto-resolution improved <strong style="color:#22c55e">+22pp</strong> since launch (60% → 82%)</li>
        <li><strong style="color:#e2e8f0">Troubleshooting</strong> drives 34% of all queries</li>
        <li><strong style="color:#ef4444">Deployment</strong> docs oldest (avg 31 days)</li>
        <li><strong style="color:#ef4444">sim_setup</strong> section flagged — 26-day avg age</li>
        <li><strong style="color:#38bdf8">Security</strong> docs most current (avg 4 days)</li>
        <li>18% of queries still escalate to support tickets</li>
        <li>3 critical articles require immediate update</li>
      </ul>
    </div>
  </div>

  <div class="charts">
    <div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:8px">Coverage — Docs &amp; Freshness by Topic</div>
      {cov_svg}
    </div>
    <div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:8px">30-Day Query Volume &amp; Resolution Trend</div>
      {trend_svg}
    </div>
  </div>

  <div class="footer">
    Last updated: {SUMMARY['last_updated']} · OCI Robot Cloud · knowledge_base_api v1.0
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Knowledge Base API",
        description="OCI Robot Cloud internal knowledge base and runbook documentation",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return make_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "knowledge_base_api", "port": 8311}

    @app.get("/api/summary")
    def api_summary():
        return SUMMARY

    @app.get("/api/topics")
    def api_topics():
        return TOPIC_AREAS

    @app.get("/api/query-history")
    def api_query_history(days: int = Query(default=30, ge=1, le=30)):
        return QUERY_HISTORY[-days:]

    @app.get("/api/search")
    def api_search(q: str = Query(default=""), topic: str = Query(default="")):
        """Mock search — returns matching topic areas and article counts."""
        results = []
        for t in TOPIC_AREAS:
            if (not q or q.lower() in t["name"]) and (not topic or topic == t["name"]):
                results.append({
                    "topic": t["name"],
                    "doc_count": t["docs"],
                    "freshness": t["freshness"],
                    "sample_articles": [
                        f"{t['name']}_quickstart.md",
                        f"{t['name']}_reference.md",
                        f"{t['name']}_troubleshooting.md",
                    ],
                })
        return {"query": q, "topic_filter": topic, "results": results, "total": sum(r["doc_count"] for r in results)}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status": "ok", "service": "knowledge_base_api", "port": 8311}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = make_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8311)
    else:
        with socketserver.TCPServer(("", 8311), Handler) as httpd:
            print("Knowledge Base API (stdlib) running on port 8311")
            httpd.serve_forever()
