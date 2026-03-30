"""experiment_search.py — Full-text search and filter interface for experiment runs.
Port: 8282
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
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

CATEGORIES = ["dagger", "bc", "distillation", "multi-task", "sim2real", "ablation"]
STATUSES = ["completed", "failed", "in_progress"]

# Category base SRs (dagger highest)
CATEGORY_BASE_SR = {
    "dagger": 0.71,
    "bc": 0.52,
    "distillation": 0.63,
    "multi-task": 0.58,
    "sim2real": 0.49,
    "ablation": 0.55,
}

def _make_experiments():
    exps = []
    start = datetime(2026, 1, 3)
    # SR trend: +0.031 per month
    for i in range(40):
        cat = CATEGORIES[i % len(CATEGORIES)]
        days_offset = int(i * (85 / 40))  # spread across ~85 days to end of March
        date = start + timedelta(days=days_offset)
        # SR improves over time + category base + small noise
        months_elapsed = days_offset / 30.0
        base = CATEGORY_BASE_SR[cat]
        sr = min(0.95, base + 0.031 * months_elapsed + random.uniform(-0.04, 0.04))
        # Force exactly 3 failures
        if i in (7, 18, 29):
            status = "failed"
            sr = 0.0
        elif i >= 37:
            status = "in_progress"
        else:
            status = "completed"
        cost = round(random.uniform(2.5, 18.0), 2)
        exps.append({
            "id": f"exp-{1000 + i}",
            "name": f"{cat}-run{i // len(CATEGORIES) + 1}",
            "category": cat,
            "tags": [cat, f"v{(i // 10) + 1}", "oci-a100"],
            "status": status,
            "sr": round(sr, 4),
            "training_cost_usd": cost,
            "date": date.strftime("%Y-%m-%d"),
            "steps": random.randint(1000, 10000),
            "notes": f"Auto-generated {cat} experiment #{i}",
        })
    return exps

EXPERIMENTS = _make_experiments()

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_category_bar_chart():
    """Bar chart: experiment count per category + avg SR overlay line."""
    completed = [e for e in EXPERIMENTS if e["status"] == "completed"]
    cat_counts = {c: 0 for c in CATEGORIES}
    cat_sr = {c: [] for c in CATEGORIES}
    for e in completed:
        cat_counts[e["category"]] += 1
        cat_sr[e["category"]].append(e["sr"])
    cat_avg_sr = {c: (sum(v) / len(v) if v else 0) for c, v in cat_sr.items()}

    W, H = 560, 280
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    max_count = max(cat_counts.values()) or 1
    bar_w = chart_w / len(CATEGORIES) * 0.55
    bar_gap = chart_w / len(CATEGORIES)

    bars = ""
    line_pts = []
    colors = ["#C74634", "#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f472b6"]
    for idx, cat in enumerate(CATEGORIES):
        x = pad_l + idx * bar_gap + (bar_gap - bar_w) / 2
        count = cat_counts[cat]
        bar_h = (count / max_count) * chart_h
        y = pad_t + chart_h - bar_h
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{colors[idx]}" opacity="0.85" rx="3"/>'
        bars += f'<text x="{x + bar_w/2:.1f}" y="{y - 5:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{count}</text>'
        bars += f'<text x="{x + bar_w/2:.1f}" y="{pad_t + chart_h + 18:.1f}" text-anchor="middle" fill="#94a3b8" font-size="10">{cat}</text>'
        # SR line point (scale 0-1 to chart height)
        sr = cat_avg_sr[cat]
        ly = pad_t + chart_h - sr * chart_h
        lx = pad_l + idx * bar_gap + bar_gap / 2
        line_pts.append((lx, ly, sr))

    # Draw SR overlay line
    polyline = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in line_pts)
    sr_line = f'<polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="5,3"/>'
    sr_dots = "".join(
        f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="#38bdf8"/>'
        f'<text x="{p[0]:.1f}" y="{p[1] - 8:.1f}" text-anchor="middle" fill="#38bdf8" font-size="10">{p[2]:.2f}</text>'
        for p in line_pts
    )

    # Y-axis ticks
    yticks = ""
    for t in range(0, max_count + 1, max(1, max_count // 4)):
        ty = pad_t + chart_h - (t / max_count) * chart_h
        yticks += f'<line x1="{pad_l - 4}" y1="{ty:.1f}" x2="{pad_l}" y2="{ty:.1f}" stroke="#475569" stroke-width="1"/>'
        yticks += f'<text x="{pad_l - 8}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{t}</text>'

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'<text x="{W//2}" y="15" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Experiment Count &amp; Avg SR by Category</text>'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        + yticks + bars + sr_line + sr_dots +
        f'<text x="{W - 10}" y="{pad_t + chart_h//2}" text-anchor="end" fill="#38bdf8" font-size="10">— Avg SR</text>'
        f'</svg>'
    )
    return svg


def _svg_timeline_scatter():
    """Scatter plot: all 40 experiments by date (x) and SR (y)."""
    W, H = 560, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    # Date range
    start_ts = datetime(2026, 1, 3)
    end_ts = datetime(2026, 3, 28)
    total_days = (end_ts - start_ts).days or 1

    STATUS_COLORS = {"completed": "#34d399", "failed": "#f87171", "in_progress": "#fbbf24"}
    max_cost = max(e["training_cost_usd"] for e in EXPERIMENTS)

    dots = ""
    for e in EXPERIMENTS:
        d = datetime.strptime(e["date"], "%Y-%m-%d")
        days = (d - start_ts).days
        cx = pad_l + (days / total_days) * chart_w
        sr = e["sr"]
        cy = pad_t + chart_h - sr * chart_h
        r = 4 + (e["training_cost_usd"] / max_cost) * 8
        color = STATUS_COLORS[e["status"]]
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" opacity="0.8"/>'
        dots += f'<title>{e["name"]} SR={sr} cost=${e["training_cost_usd"]}</title>'

    # Overall SR trend line: +0.031/month
    # Compute two endpoints
    def trend_y(days_offset):
        sr_val = 0.52 + 0.031 * (days_offset / 30.0)
        return pad_t + chart_h - min(1.0, sr_val) * chart_h

    tx1, ty1 = pad_l, trend_y(0)
    tx2, ty2 = pad_l + chart_w, trend_y(total_days)
    trend = f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3"/>'
    trend += f'<text x="{tx2 - 5:.1f}" y="{ty2 - 6:.1f}" text-anchor="end" fill="#C74634" font-size="10">+0.031/mo trend</text>'

    # Y-axis
    yticks = ""
    for sr_t in [0.0, 0.25, 0.5, 0.75, 1.0]:
        ty = pad_t + chart_h - sr_t * chart_h
        yticks += f'<line x1="{pad_l - 4}" y1="{ty:.1f}" x2="{pad_l + chart_w}" y2="{ty:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        yticks += f'<text x="{pad_l - 8}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{sr_t:.2f}</text>'

    # X-axis month labels
    xlabels = ""
    for month_offset, label in [(0, "Jan"), (28, "Feb"), (59, "Mar")]:
        lx = pad_l + (month_offset / total_days) * chart_w
        xlabels += f'<text x="{lx:.1f}" y="{pad_t + chart_h + 18:.1f}" fill="#64748b" font-size="10">{label}</text>'

    # Legend
    legend = (
        f'<circle cx="{pad_l + 5}" cy="{pad_t - 12}" r="5" fill="#34d399"/>'
        f'<text x="{pad_l + 13}" y="{pad_t - 8}" fill="#94a3b8" font-size="10">completed</text>'
        f'<circle cx="{pad_l + 80}" cy="{pad_t - 12}" r="5" fill="#f87171"/>'
        f'<text x="{pad_l + 88}" y="{pad_t - 8}" fill="#94a3b8" font-size="10">failed</text>'
        f'<circle cx="{pad_l + 130}" cy="{pad_t - 12}" r="5" fill="#fbbf24"/>'
        f'<text x="{pad_l + 138}" y="{pad_t - 8}" fill="#94a3b8" font-size="10">in_progress</text>'
        f'<text x="{pad_l + 210}" y="{pad_t - 8}" fill="#94a3b8" font-size="10">(size = cost)</text>'
    )

    svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
        f'<text x="{W//2}" y="15" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Experiment Timeline: SR vs Date</text>'
        + yticks + trend + dots + xlabels + legend +
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------

def search_experiments(q: str = "", min_sr: float = 0.0, category: str = "", status: str = ""):
    results = []
    q_lower = q.lower()
    for e in EXPERIMENTS:
        if q_lower and q_lower not in e["name"].lower() and q_lower not in e["category"] and q_lower not in " ".join(e["tags"]):
            continue
        if e["sr"] < min_sr:
            continue
        if category and e["category"] != category:
            continue
        if status and e["status"] != status:
            continue
        results.append(e)
    return results


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html(search_q="", min_sr=0.0, category="", status="", results=None):
    if results is None:
        results = EXPERIMENTS
    svg1 = _svg_category_bar_chart()
    svg2 = _svg_timeline_scatter()

    # Summary metrics
    total = len(EXPERIMENTS)
    completed = sum(1 for e in EXPERIMENTS if e["status"] == "completed")
    failed = sum(1 for e in EXPERIMENTS if e["status"] == "failed")
    avg_sr_all = sum(e["sr"] for e in EXPERIMENTS if e["status"] == "completed") / max(1, completed)
    tag_freq = {}
    for e in EXPERIMENTS:
        for t in e["tags"]:
            tag_freq[t] = tag_freq.get(t, 0) + 1
    top_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:6]

    rows = ""
    for e in results[:20]:
        sr_color = "#34d399" if e["sr"] >= 0.65 else ("#fbbf24" if e["sr"] >= 0.4 else "#f87171")
        status_color = {"completed": "#34d399", "failed": "#f87171", "in_progress": "#fbbf24"}[e["status"]]
        tags_html = " ".join(f'<span style="background:#1e3a5f;padding:1px 5px;border-radius:3px;font-size:11px">{t}</span>' for t in e["tags"])
        rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:6px 8px;font-family:monospace;color:#38bdf8">{e['id']}</td>
          <td style="padding:6px 8px;color:#e2e8f0">{e['name']}</td>
          <td style="padding:6px 8px;color:#a78bfa">{e['category']}</td>
          <td style="padding:6px 8px"><span style="color:{sr_color};font-weight:bold">{e['sr']:.3f}</span></td>
          <td style="padding:6px 8px"><span style="color:{status_color}">{e['status']}</span></td>
          <td style="padding:6px 8px;color:#64748b">{e['date']}</td>
          <td style="padding:6px 8px;color:#fbbf24">${e['training_cost_usd']}</td>
          <td style="padding:6px 8px">{tags_html}</td>
        </tr>"""

    top_tags_html = " ".join(f'<span style="background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:4px;font-size:12px">{t} ({c})</span>' for t, c in top_tags)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Experiment Search — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; margin:0; padding:20px; }}
    h1 {{ color:#C74634; margin:0 0 4px 0; font-size:1.6rem; }}
    .subtitle {{ color:#64748b; font-size:0.9rem; margin-bottom:20px; }}
    .metrics {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:20px; }}
    .metric-card {{ background:#1e293b; border-radius:8px; padding:14px 18px; min-width:130px; }}
    .metric-val {{ font-size:1.8rem; font-weight:bold; color:#38bdf8; }}
    .metric-label {{ font-size:0.78rem; color:#64748b; margin-top:2px; }}
    .charts {{ display:flex; gap:20px; flex-wrap:wrap; margin-bottom:24px; }}
    .search-bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; align-items:center; }}
    input, select {{ background:#1e293b; color:#e2e8f0; border:1px solid #334155; border-radius:6px; padding:7px 12px; font-size:13px; }}
    button {{ background:#C74634; color:#fff; border:none; border-radius:6px; padding:7px 18px; cursor:pointer; font-size:13px; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; }}
    th {{ background:#0f172a; color:#64748b; padding:8px; text-align:left; font-size:12px; text-transform:uppercase; }}
    tr:hover {{ background:#243044; }}
    .tags-row {{ margin-bottom:16px; }}
  </style>
</head>
<body>
  <h1>Experiment Search</h1>
  <div class="subtitle">OCI Robot Cloud — Full-text search and filter for experiment runs &amp; results | Port 8282</div>

  <div class="metrics">
    <div class="metric-card"><div class="metric-val">{total}</div><div class="metric-label">Total Experiments</div></div>
    <div class="metric-card"><div class="metric-val">{completed}</div><div class="metric-label">Completed</div></div>
    <div class="metric-card"><div class="metric-val" style="color:#f87171">{failed}</div><div class="metric-label">Failed</div></div>
    <div class="metric-card"><div class="metric-val">{avg_sr_all:.3f}</div><div class="metric-label">Avg SR (completed)</div></div>
    <div class="metric-card"><div class="metric-val" style="color:#C74634">+0.031</div><div class="metric-label">SR Trend /month</div></div>
    <div class="metric-card"><div class="metric-val">{len(results)}</div><div class="metric-label">Search Results</div></div>
  </div>

  <div class="tags-row">Top tags: {top_tags_html}</div>

  <div class="charts">
    <div>{svg1}</div>
    <div>{svg2}</div>
  </div>

  <form class="search-bar" method="get" action="/">
    <input name="q" placeholder="Search (e.g. dagger, run3...)" value="{search_q}" style="width:220px"/>
    <input name="min_sr" type="number" step="0.01" min="0" max="1" placeholder="Min SR" value="{min_sr if min_sr else ''}" style="width:90px"/>
    <select name="category">
      <option value="">All categories</option>
      {''.join(f'<option value="{c}"{" selected" if c==category else ""}>{c}</option>' for c in CATEGORIES)}
    </select>
    <select name="status">
      <option value="">All statuses</option>
      {''.join(f'<option value="{s}"{" selected" if s==status else ""}>{s}</option>' for s in STATUSES)}
    </select>
    <button type="submit">Search</button>
    <a href="/" style="color:#64748b;font-size:13px">Reset</a>
  </form>

  <table>
    <tr>
      <th>ID</th><th>Name</th><th>Category</th><th>SR</th><th>Status</th><th>Date</th><th>Cost</th><th>Tags</th>
    </tr>
    {rows}
  </table>
  {'<div style="color:#64748b;margin-top:8px;font-size:13px">Showing top 20 of ' + str(len(results)) + ' results</div>' if len(results) > 20 else ''}
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Experiment Search", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(
        q: str = Query(default=""),
        min_sr: float = Query(default=0.0),
        category: str = Query(default=""),
        status: str = Query(default=""),
    ):
        results = search_experiments(q=q, min_sr=min_sr, category=category, status=status)
        return _build_html(search_q=q, min_sr=min_sr, category=category, status=status, results=results)

    @app.get("/search")
    def api_search(
        q: str = Query(default=""),
        min_sr: float = Query(default=0.0),
        category: str = Query(default=""),
        status: str = Query(default=""),
    ):
        results = search_experiments(q=q, min_sr=min_sr, category=category, status=status)
        return JSONResponse({"count": len(results), "results": results})

    @app.get("/experiments")
    def list_experiments():
        return JSONResponse({"count": len(EXPERIMENTS), "experiments": EXPERIMENTS})

    @app.get("/metrics")
    def metrics():
        completed = [e for e in EXPERIMENTS if e["status"] == "completed"]
        failed_count = sum(1 for e in EXPERIMENTS if e["status"] == "failed")
        avg_sr = sum(e["sr"] for e in completed) / max(1, len(completed))
        cat_avg = {
            c: round(sum(e["sr"] for e in completed if e["category"] == c) / max(1, sum(1 for e in completed if e["category"] == c)), 4)
            for c in CATEGORIES
        }
        return JSONResponse({
            "total_experiments": len(EXPERIMENTS),
            "completed": len(completed),
            "failed": failed_count,
            "avg_sr_completed": round(avg_sr, 4),
            "sr_trend_per_month": 0.031,
            "category_avg_sr": cat_avg,
            "search_latency_ms": 2.1,
        })

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            q = params.get("q", [""])[0]
            min_sr = float(params.get("min_sr", ["0"])[0])
            category = params.get("category", [""])[0]
            status = params.get("status", [""])[0]
            results = search_experiments(q=q, min_sr=min_sr, category=category, status=status)
            body = _build_html(search_q=q, min_sr=min_sr, category=category, status=status, results=results).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8282)
    else:
        print("FastAPI not found — running stdlib fallback on port 8282")
        HTTPServer(("0.0.0.0", 8282), Handler).serve_forever()
