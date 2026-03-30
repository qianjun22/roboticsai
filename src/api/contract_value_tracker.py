"""Contract Value Tracker — port 8975
Tracks 5 active contracts: TCV, ARR, renewal dates, weighted pipeline.
"""
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Contract data
# ---------------------------------------------------------------------------

CONTRACTS = [
    {
        "id": "C-001",
        "name": "Pioneer Robotics",
        "arr": 48000,
        "tcv": 144000,
        "term_years": 3,
        "renewal_date": "2026-10-15",
        "probability": 0.85,
        "renewal_target": 108000,
        "status": "Renewal Discussion",
    },
    {
        "id": "C-002",
        "name": "AutoFab Industries",
        "arr": 36000,
        "tcv": 108000,
        "term_years": 3,
        "renewal_date": "2027-02-01",
        "probability": 0.90,
        "renewal_target": 42000,
        "status": "Active",
    },
    {
        "id": "C-003",
        "name": "Helix Automation",
        "arr": 24000,
        "tcv": 48000,
        "term_years": 2,
        "renewal_date": "2026-12-31",
        "probability": 0.75,
        "renewal_target": 30000,
        "status": "At Risk",
    },
    {
        "id": "C-004",
        "name": "Nexus Logistics",
        "arr": 18000,
        "tcv": 36000,
        "term_years": 2,
        "renewal_date": "2027-06-30",
        "probability": 0.95,
        "renewal_target": 22000,
        "status": "Active",
    },
    {
        "id": "C-005",
        "name": "Orbit Manufacturing",
        "arr": 15200,
        "tcv": 45600,
        "term_years": 3,
        "renewal_date": "2027-09-15",
        "probability": 0.80,
        "renewal_target": 18000,
        "status": "Active",
    },
]

TOTAL_ARR = sum(c["arr"] for c in CONTRACTS)
TOTAL_TCV = sum(c["tcv"] for c in CONTRACTS)
WEIGHTED_PIPELINE = sum(c["renewal_target"] * c["probability"] for c in CONTRACTS)
PI_RENEWAL_TARGET = 108000  # Pioneer Robotics Oct 2026

# TCV growth series (12 quarters, synthetic)
random.seed(7)
BASE_TCV = 180000
TCV_QUARTERS = ["Q1'24", "Q2'24", "Q3'24", "Q4'24",
                "Q1'25", "Q2'25", "Q3'25", "Q4'25",
                "Q1'26", "Q2'26", "Q3'26", "Q4'26"]
TCV_GROWTH = []
v = BASE_TCV
for i in range(len(TCV_QUARTERS)):
    v = v * (1 + 0.055 + random.gauss(0, 0.012))
    TCV_GROWTH.append(round(v))

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_bar_chart(
    labels: list,
    values: list,
    color: str,
    title: str,
    width: int = 700,
    height: int = 200,
) -> str:
    pad_l, pad_r, pad_t, pad_b = 65, 20, 30, 50
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    n = len(values)
    bar_w = inner_w / n * 0.65
    gap = inner_w / n

    mx = max(values) or 1

    bars = ""
    for i, (lbl, val) in enumerate(zip(labels, values)):
        bh = inner_h * val / mx
        bx = pad_l + i * gap + (gap - bar_w) / 2
        by = pad_t + inner_h - bh
        bars += (
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w/2:.1f}" y="{pad_t + inner_h + 14}" '
            f'text-anchor="middle" font-size="9" fill="#94a3b8">{lbl}</text>'
        )

    # y-axis ticks
    ticks = ""
    for k in range(5):
        yv = mx * k / 4
        yt = pad_t + inner_h * (1 - k / 4)
        ticks += (
            f'<line x1="{pad_l}" y1="{yt:.1f}" x2="{pad_l + inner_w}" y2="{yt:.1f}" '
            f'stroke="#334155" stroke-width="0.5"/>'
            f'<text x="{pad_l - 5}" y="{yt + 4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#94a3b8">${yv/1000:.0f}k</text>'
        )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{ticks}{bars}'
        f'<text x="{pad_l}" y="{pad_t - 10}" font-size="10" fill="#94a3b8">{title}</text>'
        f'</svg>'
    )


def _svg_renewal_pipeline(contracts: list, width: int = 700, height: int = 220) -> str:
    """Horizontal bar chart of weighted renewal value per contract."""
    pad_l, pad_r, pad_t, pad_b = 160, 30, 30, 20
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    n = len(contracts)
    bar_h = inner_h / n * 0.6
    gap = inner_h / n

    vals = [c["renewal_target"] * c["probability"] for c in contracts]
    mx = max(vals) or 1

    COLORS = ["#38bdf8", "#4ade80", "#fb923c", "#a78bfa", "#f472b6"]

    bars = ""
    for i, (c, v) in enumerate(zip(contracts, vals)):
        bw = inner_w * v / mx
        bx = pad_l
        by = pad_t + i * gap + (gap - bar_h) / 2
        col = COLORS[i % len(COLORS)]
        bars += (
            f'<rect x="{bx}" y="{by:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" '
            f'fill="{col}" rx="3"/>'
            f'<text x="{bx - 8}" y="{by + bar_h/2 + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="#e2e8f0">{c["name"]}</text>'
            f'<text x="{bx + bw + 6}" y="{by + bar_h/2 + 4:.1f}" '
            f'font-size="10" fill="{col}">${v/1000:.1f}k</text>'
        )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{bars}'
        f'<text x="{pad_l}" y="{pad_t - 10}" font-size="10" fill="#94a3b8">Weighted Renewal Pipeline</text>'
        f'</svg>'
    )


def _status_badge(status: str) -> str:
    colors = {
        "Active": ("#dcfce7", "#16a34a"),
        "Renewal Discussion": ("#fef9c3", "#ca8a04"),
        "At Risk": ("#fee2e2", "#dc2626"),
    }
    bg, fg = colors.get(status, ("#1e293b", "#94a3b8"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:999px;'
        f'font-size:.7rem;font-weight:600">{status}</span>'
    )


def _make_html() -> str:
    chart_tcv = _svg_bar_chart(
        TCV_QUARTERS, TCV_GROWTH, "#38bdf8", "TCV Growth (quarterly)"
    )
    chart_pipeline = _svg_renewal_pipeline(CONTRACTS)

    contract_rows = ""
    for c in CONTRACTS:
        weighted = c["renewal_target"] * c["probability"]
        contract_rows += (
            f'<tr>'
            f'<td>{c["id"]}</td>'
            f'<td><strong>{c["name"]}</strong></td>'
            f'<td>${c["arr"]:,}</td>'
            f'<td>${c["tcv"]:,}</td>'
            f'<td>{c["renewal_date"]}</td>'
            f'<td>{int(c["probability"]*100)}%</td>'
            f'<td>${weighted:,.0f}</td>'
            f'<td>{_status_badge(c["status"])}</td>'
            f'</tr>'
        )

    pi_progress = min(100, int(CONTRACTS[0]["arr"] / PI_RENEWAL_TARGET * 100))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Contract Value Tracker</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;margin-bottom:4px}}
  h2{{color:#38bdf8;font-size:1rem;margin:20px 0 8px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:16px}}
  .card .val{{font-size:1.8rem;font-weight:700;margin-top:6px}}
  .card .sub{{font-size:.75rem;color:#64748b;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;padding:10px 14px;text-align:left;font-size:.75rem;color:#64748b;text-transform:uppercase}}
  td{{padding:9px 14px;border-bottom:1px solid #0f172a;font-size:.85rem;vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  .bar-bg{{background:#0f172a;border-radius:999px;height:10px;margin-top:8px}}
  .bar-fill{{background:#38bdf8;border-radius:999px;height:10px}}
</style>
</head>
<body>
<h1>Contract Value Tracker</h1>
<p style="color:#64748b;font-size:.85rem">Port 8975 &mdash; 5 active contracts &mdash; TCV / ARR / renewal pipeline</p>

<div class="grid">
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Total Contracted ARR</div>
    <div class="val" style="color:#4ade80">${TOTAL_ARR:,}</div>
    <div class="sub">Across 5 active contracts</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Total TCV</div>
    <div class="val" style="color:#38bdf8">${TOTAL_TCV:,}</div>
    <div class="sub">Committed contract value</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Weighted Pipeline</div>
    <div class="val" style="color:#a78bfa">${WEIGHTED_PIPELINE:,.0f}</div>
    <div class="sub">Renewal ARR × probability</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Pioneer Robotics Renewal</div>
    <div class="val" style="color:#fb923c">${PI_RENEWAL_TARGET:,}</div>
    <div class="sub">Oct 2026 target &mdash; current ARR ${CONTRACTS[0]["arr"]:,}</div>
    <div class="bar-bg"><div class="bar-fill" style="width:{pi_progress}%"></div></div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Active Contracts</div>
    <div class="val" style="color:#f472b6">5</div>
    <div class="sub">3 active &nbsp;|&nbsp; 1 renewal discussion &nbsp;|&nbsp; 1 at risk</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Avg Contract ARR</div>
    <div class="val" style="color:#94a3b8">${TOTAL_ARR // len(CONTRACTS):,}</div>
    <div class="sub">Per account</div>
  </div>
</div>

<h2>Contract Renewal Pipeline</h2>
{chart_pipeline}

<h2>TCV Growth</h2>
{chart_tcv}

<h2>Active Contracts</h2>
<table>
  <thead>
    <tr>
      <th>ID</th><th>Customer</th><th>ARR</th><th>TCV</th>
      <th>Renewal Date</th><th>Prob.</th><th>Weighted</th><th>Status</th>
    </tr>
  </thead>
  <tbody>{contract_rows}</tbody>
</table>

<p style="color:#334155;font-size:.75rem;margin-top:24px">OCI Robot Cloud &mdash; Contract Value Tracker v1.0</p>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Contract Value Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(_make_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8975, "service": "contract_value_tracker"}

    @app.get("/metrics")
    async def metrics():
        return {
            "total_arr": TOTAL_ARR,
            "total_tcv": TOTAL_TCV,
            "weighted_pipeline": round(WEIGHTED_PIPELINE),
            "pi_renewal_target": PI_RENEWAL_TARGET,
            "contract_count": len(CONTRACTS),
            "contracts": CONTRACTS,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8975)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _make_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8975), Handler)
        print("Contract Value Tracker running on http://0.0.0.0:8975")
        server.serve_forever()
