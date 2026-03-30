"""Eval Metadata Store — port 8325

Stores and queries rich metadata from evaluation runs for experiment management.
Tracks coverage, completeness, and cadence across model versions and eval types.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
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

MODEL_VERSIONS = ["groot_v1", "groot_v2", "groot_v3"]
EVAL_TYPES = ["libero", "stress", "sim2real", "partner", "safety"]
EVAL_TYPE_COLORS = {
    "libero":   "#38bdf8",
    "stress":   "#C74634",
    "sim2real": "#fb923c",
    "partner":  "#a78bfa",
    "safety":   "#22c55e",
}

# Ground-truth counts per model × eval_type (247 total)
RUN_MATRIX = {
    "groot_v1": {"libero": 28, "stress": 14, "sim2real": 6,  "partner": 9,  "safety": 8},
    "groot_v2": {"libero": 36, "stress": 18, "sim2real": 10, "partner": 14, "safety": 11},
    "groot_v3": {"libero": 31, "stress": 20, "sim2real": 2,  "partner": 7,  "safety": 3},
}
# sim2real coverage gap: groot_v3 only 2 runs

TOTAL_RUNS = sum(sum(v.values()) for v in RUN_MATRIX.values())  # 227 ... pad to 247


def get_coverage_data():
    data = []
    for mv in MODEL_VERSIONS:
        for et in EVAL_TYPES:
            count = RUN_MATRIX[mv][et]
            # avg SR: sim2real lower, stress lower
            base_sr = {"libero": 0.72, "stress": 0.55, "sim2real": 0.48,
                       "partner": 0.68, "safety": 0.83}[et]
            avg_sr = round(base_sr + random.uniform(-0.04, 0.04), 3)
            gap = (mv == "groot_v3" and et == "sim2real")  # coverage gap
            data.append({
                "model": mv, "eval_type": et,
                "count": count, "avg_sr": avg_sr,
                "gap": gap,
            })
    return data


def get_weekly_counts():
    """12-week stacked bar data."""
    weeks = [(datetime.now() - timedelta(weeks=11 - i)).strftime("W%W") for i in range(12)]
    # cadence increasing from ~8 to ~30
    data = []
    for w_idx in range(12):
        base = int(8 + w_idx * 1.8 + random.uniform(-1, 1))
        split = {}
        remaining = base
        for et in EVAL_TYPES[:-1]:
            share = max(1, int(remaining * random.uniform(0.15, 0.30)))
            split[et] = share
            remaining -= share
        split["safety"] = max(0, remaining)
        data.append({"week": weeks[w_idx], **split, "total": base})
    return data


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_treemap_svg(coverage_data):
    """Metadata coverage treemap: model_version → eval_type cells."""
    W, H = 820, 240
    pad = 4
    model_w = (W - pad * 4) // len(MODEL_VERSIONS)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        f'<text x="10" y="16" fill="#94a3b8" font-size="11">'
        'Eval Coverage Treemap: model × eval_type (size=run count, color=avg SR)</text>',
    ]

    model_totals = {mv: sum(RUN_MATRIX[mv].values()) for mv in MODEL_VERSIONS}
    max_total = max(model_totals.values())

    for m_idx, mv in enumerate(MODEL_VERSIONS):
        mx = pad + m_idx * (model_w + pad)
        my = 24
        mh = H - 30

        # model header
        svg_parts.append(
            f'<rect x="{mx}" y="{my}" width="{model_w}" height="{mh}" '
            f'fill="#0f172a" rx="4"/>'
        )
        svg_parts.append(
            f'<text x="{mx + model_w//2}" y="{my + 14}" fill="#C74634" '
            f'font-size="10" font-weight="bold" text-anchor="middle">{mv}</text>'
        )

        # eval type cells stacked vertically
        inner_h = mh - 22
        inner_y = my + 20
        mtotal = model_totals[mv]

        for et in EVAL_TYPES:
            count = RUN_MATRIX[mv][et]
            cell_h = max(6, int(count / mtotal * inner_h))
            gap = (mv == "groot_v3" and et == "sim2real")
            # SR-based color: green high, red low
            entry = next(d for d in coverage_data if d["model"] == mv and d["eval_type"] == et)
            sr = entry["avg_sr"]
            # interpolate red→green by SR
            r = int(199 + (34 - 199) * sr)
            g = int(70 + (197 - 70) * sr)
            b = int(52 + (94 - 52) * sr)
            fill = f"rgb({r},{g},{b})" if not gap else "#475569"
            stroke = "#ff0000" if gap else "none"

            svg_parts.append(
                f'<rect x="{mx + 4}" y="{inner_y}" width="{model_w - 8}" '
                f'height="{cell_h - 2}" fill="{fill}" rx="2" '
                f'stroke="{stroke}" stroke-width="{2 if gap else 0}"/>'
            )
            if cell_h > 14:
                svg_parts.append(
                    f'<text x="{mx + model_w//2}" y="{inner_y + cell_h//2 + 3}" '
                    f'fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">'
                    f'{et} ({count})</text>'
                )
            inner_y += cell_h

    # gap legend
    svg_parts.append(
        f'<text x="10" y="{H - 4}" fill="#ef4444" font-size="9">'
        'Red border = coverage gap: groot_v3 sim2real only 2 runs (no recent sim2real data!)</text>'
    )
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def build_weekly_bar_svg(weekly):
    """12-week stacked bar chart of eval run counts by type."""
    W, H = 820, 240
    pad_l = 40
    pad_r = 10
    pad_t = 24
    pad_b = 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(weekly)
    bar_w = chart_w // n - 4
    max_total = max(w["total"] for w in weekly)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        f'<text x="10" y="16" fill="#94a3b8" font-size="11">'
        'Weekly Eval Run Count (12 weeks) — Stacked by Type</text>',
    ]

    # y-axis ticks
    for tick in [0, 10, 20, 30]:
        ty = pad_t + chart_h - int(tick / max_total * chart_h)
        svg_parts.append(
            f'<line x1="{pad_l}" y1="{ty}" x2="{W - pad_r}" y2="{ty}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        svg_parts.append(
            f'<text x="{pad_l - 4}" y="{ty + 4}" fill="#64748b" font-size="9" '
            f'text-anchor="end">{tick}</text>'
        )

    for i, w in enumerate(weekly):
        bx = pad_l + i * (chart_w // n) + 2
        stacked_y = pad_t + chart_h

        for et in reversed(EVAL_TYPES):
            count = w.get(et, 0)
            if count <= 0:
                continue
            seg_h = max(2, int(count / max_total * chart_h))
            color = EVAL_TYPE_COLORS[et]
            stacked_y -= seg_h
            svg_parts.append(
                f'<rect x="{bx}" y="{stacked_y}" width="{bar_w}" height="{seg_h}" '
                f'fill="{color}" rx="1"/>'
            )

        # x-axis label
        svg_parts.append(
            f'<text x="{bx + bar_w//2}" y="{pad_t + chart_h + 14}" '
            f'fill="#64748b" font-size="8" text-anchor="middle">{w["week"]}</text>'
        )
        # total label on top
        svg_parts.append(
            f'<text x="{bx + bar_w//2}" y="{stacked_y - 2}" '
            f'fill="#94a3b8" font-size="7" text-anchor="middle">{w["total"]}</text>'
        )

    # legend
    lx = pad_l
    for et in EVAL_TYPES:
        svg_parts.append(
            f'<rect x="{lx}" y="{H - 12}" width="10" height="8" fill="{EVAL_TYPE_COLORS[et]}" rx="1"/>'
        )
        svg_parts.append(
            f'<text x="{lx + 12}" y="{H - 4}" fill="#94a3b8" font-size="8">{et}</text>'
        )
        lx += 70

    svg_parts.append('</svg>')
    return ''.join(svg_parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html():
    coverage_data = get_coverage_data()
    weekly = get_weekly_counts()
    treemap_svg = build_treemap_svg(coverage_data)
    weekly_svg = build_weekly_bar_svg(weekly)

    total_runs = sum(d["count"] for d in coverage_data)
    sim2real_runs = sum(d["count"] for d in coverage_data if d["eval_type"] == "sim2real")
    avg_per_week = round(sum(w["total"] for w in weekly) / len(weekly), 1)
    completeness = 98.7

    model_rows = ""
    for mv in MODEL_VERSIONS:
        runs = sum(RUN_MATRIX[mv].values())
        types_covered = sum(1 for et in EVAL_TYPES if RUN_MATRIX[mv][et] > 0)
        gaps = [et for et in EVAL_TYPES if RUN_MATRIX[mv].get(et, 0) < 3]
        gap_str = ", ".join(gaps) if gaps else "none"
        model_rows += (
            f'<tr><td>{mv}</td><td>{runs}</td><td>{types_covered}/5</td>'
            f'<td style="color:{"#ef4444" if gaps else "#22c55e"}">{gap_str}</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Eval Metadata Store — Port 8325</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',monospace; margin:0; padding:24px; }}
    h1   {{ color:#C74634; font-size:1.5rem; margin-bottom:4px; }}
    h2   {{ color:#38bdf8; font-size:1.1rem; margin:24px 0 8px; }}
    .badge {{ background:#1e293b; border:1px solid #334155; border-radius:6px;
              padding:12px 20px; display:inline-block; margin:6px; }}
    .metric-val {{ font-size:1.8rem; font-weight:bold; color:#38bdf8; }}
    .metric-lbl {{ font-size:0.75rem; color:#64748b; }}
    table {{ border-collapse:collapse; width:100%; background:#1e293b; border-radius:8px; overflow:hidden; margin-top:8px; }}
    th    {{ background:#0f172a; color:#C74634; padding:8px 12px; text-align:left; font-size:0.8rem; }}
    td    {{ padding:7px 12px; font-size:0.82rem; border-bottom:1px solid #1e293b; }}
    tr:hover td {{ background:#263348; }}
    .svg-wrap {{ margin:12px 0; border-radius:8px; overflow:hidden; }}
    .note {{ color:#94a3b8; font-size:0.8rem; margin-top:6px; }}
    .gap  {{ color:#ef4444; font-weight:bold; }}
  </style>
</head>
<body>
  <h1>Eval Metadata Store</h1>
  <p class="note">Port 8325 — OCI Robot Cloud — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

  <div>
    <div class="badge"><div class="metric-val">{total_runs}</div><div class="metric-lbl">Total Eval Runs</div></div>
    <div class="badge"><div class="metric-val">{completeness}%</div><div class="metric-lbl">Metadata Completeness</div></div>
    <div class="badge"><div class="metric-val" style="color:#fb923c">{sim2real_runs}</div><div class="metric-lbl">Sim2Real Runs (gap!)</div></div>
    <div class="badge"><div class="metric-val">{avg_per_week}</div><div class="metric-lbl">Avg Runs/Week (12wk)</div></div>
    <div class="badge"><div class="metric-val">3</div><div class="metric-lbl">Model Versions Tracked</div></div>
    <div class="badge"><div class="metric-val" style="color:#22c55e">&lt;5ms</div><div class="metric-lbl">Query Latency p99</div></div>
  </div>

  <h2>Metadata Coverage Treemap</h2>
  <div class="svg-wrap">{treemap_svg}</div>

  <h2>Weekly Eval Run Cadence (12 Weeks)</h2>
  <div class="svg-wrap">{weekly_svg}</div>

  <h2>Model Version Coverage Summary</h2>
  <table>
    <tr><th>Model Version</th><th>Total Runs</th><th>Eval Types Covered</th><th>Coverage Gaps</th></tr>
    {model_rows}
  </table>

  <p class="note gap" style="margin-top:16px">
    Coverage gap detected: groot_v3 has only 2 sim2real runs — recommend scheduling 10+ sim2real evals before next deployment.
  </p>
  <p class="note">
    groot_v2 most evaluated (89 runs). Eval cadence up from 8/week (Jan) to {avg_per_week}/week now. 98.7% runs have complete metadata.
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Eval Metadata Store", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": 8325, "service": "eval_metadata_store"}

    @app.get("/metrics")
    def metrics():
        coverage_data = get_coverage_data()
        weekly = get_weekly_counts()
        total = sum(d["count"] for d in coverage_data)
        sim2real = sum(d["count"] for d in coverage_data if d["eval_type"] == "sim2real")
        return {
            "total_eval_runs": total,
            "metadata_completeness_pct": 98.7,
            "sim2real_runs": sim2real,
            "sim2real_coverage_gap": True,
            "avg_runs_per_week": round(sum(w["total"] for w in weekly) / len(weekly), 1),
            "model_versions": MODEL_VERSIONS,
            "eval_types": EVAL_TYPES,
            "query_latency_p99_ms": 4.8,
            "coverage_matrix": RUN_MATRIX,
        }

    @app.get("/runs/{model_version}")
    def runs_for_model(model_version: str):
        if model_version not in RUN_MATRIX:
            return {"error": f"model '{model_version}' not found", "available": MODEL_VERSIONS}
        return {
            "model_version": model_version,
            "runs_by_type": RUN_MATRIX[model_version],
            "total": sum(RUN_MATRIX[model_version].values()),
            "gaps": [et for et in EVAL_TYPES if RUN_MATRIX[model_version].get(et, 0) < 3],
        }

    @app.get("/coverage/gaps")
    def coverage_gaps():
        gaps = []
        for mv in MODEL_VERSIONS:
            for et in EVAL_TYPES:
                count = RUN_MATRIX[mv].get(et, 0)
                if count < 3:
                    gaps.append({"model": mv, "eval_type": et, "count": count,
                                 "recommended_additional": max(0, 10 - count)})
        return {"gaps": gaps, "total_gaps": len(gaps)}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8325)
    else:
        print("FastAPI not found — using stdlib http.server on port 8325")
        with socketserver.TCPServer(("", 8325), Handler) as srv:
            srv.serve_forever()
