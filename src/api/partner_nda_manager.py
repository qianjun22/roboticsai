"""Partner NDA Manager — FastAPI service on port 8289.

Manages NDA and data processing agreements with OCI Robot Cloud partners.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import math
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TODAY = datetime(2026, 3, 30)

PARTNERS = [
    {"name": "Machina Labs",      "short": "ML"},
    {"name": "1X Technologies",   "short": "1X"},
    {"name": "Apptronik",         "short": "AP"},
    {"name": "Skild AI",          "short": "SK"},
    {"name": "Physical Intelligence", "short": "PI"},
    {"name": "Agility Robotics",  "short": "AR"},
    {"name": "Sanctuary AI",      "short": "SA"},
    {"name": "Figure AI",         "short": "FG"},
]

# Agreements: (partner_idx, type, signed_date, expiry_date, status)
# status: ACTIVE | EXPIRED | PENDING | BLOCKED
AGREEMENTS = [
    # Machina Labs — NDA active, DPA BLOCKED (awaiting signature)
    {"partner": 0, "type": "NDA",            "signed": "2025-01-15", "expiry": "2027-01-15", "status": "ACTIVE"},
    {"partner": 0, "type": "DPA",            "signed": None,         "expiry": None,          "status": "BLOCKED"},
    {"partner": 0, "type": "MSA",            "signed": "2025-03-01", "expiry": "2027-03-01", "status": "ACTIVE"},
    # 1X Technologies — NDA expiring in 45 days
    {"partner": 1, "type": "NDA",            "signed": "2024-02-14", "expiry": "2026-05-14", "status": "ACTIVE"},
    {"partner": 1, "type": "DPA",            "signed": "2024-04-01", "expiry": "2026-04-01", "status": "ACTIVE"},
    {"partner": 1, "type": "pilot_agreement", "signed": "2025-06-01", "expiry": "2026-06-01", "status": "ACTIVE"},
    # Apptronik — full suite active
    {"partner": 2, "type": "NDA",            "signed": "2025-02-01", "expiry": "2027-02-01", "status": "ACTIVE"},
    {"partner": 2, "type": "DPA",            "signed": "2025-02-15", "expiry": "2027-02-15", "status": "ACTIVE"},
    {"partner": 2, "type": "MSA",            "signed": "2025-03-10", "expiry": "2027-03-10", "status": "ACTIVE"},
    {"partner": 2, "type": "pilot_agreement", "signed": "2025-04-01", "expiry": "2026-04-01", "status": "ACTIVE"},
    # Skild AI
    {"partner": 3, "type": "NDA",            "signed": "2025-05-01", "expiry": "2027-05-01", "status": "ACTIVE"},
    {"partner": 3, "type": "DPA",            "signed": "2025-05-20", "expiry": "2027-05-20", "status": "ACTIVE"},
    # Physical Intelligence
    {"partner": 4, "type": "NDA",            "signed": "2025-07-01", "expiry": "2027-07-01", "status": "ACTIVE"},
    {"partner": 4, "type": "MSA",            "signed": "2025-08-01", "expiry": "2027-08-01", "status": "ACTIVE"},
    # Agility Robotics
    {"partner": 5, "type": "NDA",            "signed": "2025-09-01", "expiry": "2027-09-01", "status": "ACTIVE"},
    {"partner": 5, "type": "pilot_agreement", "signed": "2025-10-01", "expiry": "2026-10-01", "status": "ACTIVE"},
    # Sanctuary AI
    {"partner": 6, "type": "NDA",            "signed": "2025-11-01", "expiry": "2027-11-01", "status": "ACTIVE"},
    {"partner": 6, "type": "DPA",            "signed": "2025-11-15", "expiry": "2027-11-15", "status": "ACTIVE"},
    # Figure AI
    {"partner": 7, "type": "NDA",            "signed": "2025-12-01", "expiry": "2027-12-01", "status": "ACTIVE"},
    {"partner": 7, "type": "DPA",            "signed": "2026-01-01", "expiry": "2028-01-01", "status": "ACTIVE"},
    {"partner": 7, "type": "MSA",            "signed": "2026-02-01", "expiry": "2028-02-01", "status": "ACTIVE"},
]

DATA_FLOWS = [
    {"category": "robot_demos",        "from": "Partner", "to": "OCI Robot Cloud",  "agreement": "DPA",            "residency": "US-West"},
    {"category": "inference_requests",  "from": "Partner", "to": "OCI Robot Cloud",  "agreement": "MSA",            "residency": "US-West"},
    {"category": "eval_results",        "from": "OCI Robot Cloud", "to": "Partner",  "agreement": "pilot_agreement", "residency": "US-West"},
    {"category": "model_weights",       "from": "OCI Robot Cloud", "to": "OCI Storage", "agreement": "MSA",          "residency": "US-West"},
]

TYPE_COLORS = {
    "NDA":             "#3b82f6",
    "DPA":             "#22c55e",
    "MSA":             "#a855f7",
    "pilot_agreement": "#f59e0b",
}


def days_until(expiry_str):
    if expiry_str is None:
        return None
    exp = datetime.strptime(expiry_str, "%Y-%m-%d")
    return (exp - TODAY).days


def compute_coverage():
    """Percentage of partners with at least one ACTIVE agreement."""
    covered = set()
    for ag in AGREEMENTS:
        if ag["status"] == "ACTIVE":
            covered.add(ag["partner"])
    return round(len(covered) / len(PARTNERS) * 100, 1)


def next_expiry():
    soonest = None
    soonest_days = None
    for ag in AGREEMENTS:
        if ag["status"] == "ACTIVE" and ag["expiry"]:
            d = days_until(ag["expiry"])
            if soonest_days is None or d < soonest_days:
                soonest_days = d
                soonest = ag
    return soonest, soonest_days


def blocked_agreements():
    return [ag for ag in AGREEMENTS if ag["status"] == "BLOCKED"]


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_timeline() -> str:
    """Horizontal bar timeline for 8 partners' agreements."""
    # Show one representative agreement per partner for readability,
    # then all agreements stacked per partner row.
    ROW_H = 28
    PAD_L = 160
    PAD_R = 20
    PAD_T = 30
    PAD_B = 20

    # Time span: 2024-01-01 to 2028-06-01
    T_START = datetime(2024, 1, 1)
    T_END   = datetime(2028, 7, 1)
    total_days = (T_END - T_START).days

    W = 780
    chart_w = W - PAD_L - PAD_R

    # Collect rows: one per (partner, agreement)
    rows = []
    for ag in AGREEMENTS:
        if ag["signed"] and ag["expiry"]:
            rows.append(ag)

    H = PAD_T + len(rows) * ROW_H + PAD_B + 30

    bars = ""
    labels = ""
    prev_partner = -1
    row_idx = 0
    for ag in rows:
        p_idx = ag["partner"]
        signed = datetime.strptime(ag["signed"], "%Y-%m-%d")
        expiry = datetime.strptime(ag["expiry"], "%Y-%m-%d")
        x1 = PAD_L + (signed - T_START).days / total_days * chart_w
        x2 = PAD_L + (expiry - T_START).days / total_days * chart_w
        y  = PAD_T + row_idx * ROW_H + 4
        bh = ROW_H - 8
        color = TYPE_COLORS.get(ag["type"], "#94a3b8")
        opacity = "0.9" if ag["status"] == "ACTIVE" else "0.4"

        bars += (
            f'<rect x="{x1:.1f}" y="{y}" width="{max(x2-x1, 4):.1f}" height="{bh}" '
            f'fill="{color}" opacity="{opacity}" rx="3"/>'
            f'<text x="{x1 + 4:.1f}" y="{y + bh - 4}" fill="white" font-size="8">{ag["type"]}</text>'
        )

        # Renewal warning marker (30-day)
        d_left = days_until(ag["expiry"])
        if d_left is not None and 0 < d_left <= 30:
            warn_x = PAD_L + (expiry - T_START).days / total_days * chart_w
            bars += f'<circle cx="{warn_x:.1f}" cy="{y + bh//2}" r="5" fill="#C74634" opacity="0.9"/>'
            bars += f'<text x="{warn_x + 7:.1f}" y="{y + bh//2 + 4}" fill="#C74634" font-size="8">!</text>'

        # Partner label on first row for this partner
        if p_idx != prev_partner:
            py = PAD_T + row_idx * ROW_H + ROW_H // 2 + 4
            labels += (
                f'<text x="{PAD_L - 6}" y="{py}" fill="#e2e8f0" font-size="10" text-anchor="end">'
                f'{PARTNERS[p_idx]["short"]} – {PARTNERS[p_idx]["name"][:14]}</text>'
            )
            prev_partner = p_idx

        row_idx += 1

    # Today marker
    today_x = PAD_L + (TODAY - T_START).days / total_days * chart_w
    today_line = (
        f'<line x1="{today_x:.1f}" y1="{PAD_T}" x2="{today_x:.1f}" y2="{PAD_T + row_idx * ROW_H}" '
        f'stroke="#f8fafc" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.6"/>'
        f'<text x="{today_x + 2:.1f}" y="{PAD_T - 6}" fill="#f8fafc" font-size="9">Today</text>'
    )

    # Year axis labels
    axis = ""
    for yr in range(2024, 2029):
        dt = datetime(yr, 1, 1)
        ax = PAD_L + (dt - T_START).days / total_days * chart_w
        ay = PAD_T + row_idx * ROW_H + 14
        axis += f'<text x="{ax:.1f}" y="{ay}" fill="#64748b" font-size="9">{yr}</text>'
        axis += f'<line x1="{ax:.1f}" y1="{PAD_T}" x2="{ax:.1f}" y2="{PAD_T + row_idx * ROW_H}" stroke="#334155" stroke-width="0.5"/>'

    # Legend
    leg_y = PAD_T + row_idx * ROW_H + 28
    legend = ""
    for i, (typ, col) in enumerate(TYPE_COLORS.items()):
        lx = PAD_L + i * 140
        legend += (
            f'<rect x="{lx}" y="{leg_y - 10}" width="12" height="10" fill="{col}" rx="2"/>'
            f'<text x="{lx + 16}" y="{leg_y}" fill="#94a3b8" font-size="10">{typ}</text>'
        )
    legend += (
        f'<circle cx="{PAD_L + 570}" cy="{leg_y - 5}" r="5" fill="#C74634"/>'
        f'<text x="{PAD_L + 578}" y="{leg_y}" fill="#94a3b8" font-size="10">30-day renewal ⚠</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H + 20}" '
        f'style="background:#1e293b; border-radius:8px;">'
        + axis + bars + labels + today_line + legend +
        '</svg>'
    )
    return svg


def svg_data_flow() -> str:
    """Data flow compliance diagram."""
    W, H = 740, 320
    # Three columns: Partner (x=80), OCI Robot Cloud (x=360), OCI Storage (x=620)
    nodes = [
        {"label": "Partner",          "x": 80,  "y": 150, "w": 120, "h": 50, "color": "#1e40af"},
        {"label": "OCI Robot Cloud",   "x": 310, "y": 150, "w": 150, "h": 50, "color": "#C74634"},
        {"label": "OCI Storage",       "x": 570, "y": 150, "w": 120, "h": 50, "color": "#166534"},
    ]

    node_cx = {n["label"]: n["x"] + n["w"] // 2 for n in nodes}
    node_cy = {n["label"]: n["y"] + n["h"] // 2 for n in nodes}

    node_svg = ""
    for n in nodes:
        node_svg += (
            f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" '
            f'fill="{n["color"]}" rx="8" opacity="0.85"/>'
            f'<text x="{n["x"] + n["w"]//2}" y="{n["y"] + 22}" fill="white" '
            f'font-size="11" font-weight="bold" text-anchor="middle">{n["label"]}</text>'
            f'<text x="{n["x"] + n["w"]//2}" y="{n["y"] + 37}" fill="#cbd5e1" '
            f'font-size="9" text-anchor="middle">US-West</text>'
        )

    # Arrows and labels for each data flow
    arrow_offsets = [-50, -20, 10, 40]  # vertical spread
    flow_svg = ""
    for i, flow in enumerate(DATA_FLOWS):
        src = flow["from"]
        dst = flow["to"]
        x1 = node_cx[src]
        y1 = node_cy[src] + arrow_offsets[i % 4]
        x2 = node_cx[dst]
        y2 = node_cy[dst] + arrow_offsets[i % 4]

        # Arrow direction
        dir_x = 1 if x2 > x1 else -1
        ax1 = x1 + dir_x * 65
        ax2 = x2 - dir_x * 65

        mid_x = (ax1 + ax2) / 2
        cat_color = "#38bdf8"
        agr_color = TYPE_COLORS.get(flow["agreement"], "#94a3b8")

        flow_svg += (
            f'<defs><marker id="arr{i}" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            f'<path d="M0,0 L0,6 L8,3 z" fill="{cat_color}"/></marker></defs>'
            f'<line x1="{ax1}" y1="{y1}" x2="{ax2}" y2="{y2}" stroke="{cat_color}" '
            f'stroke-width="1.5" marker-end="url(#arr{i})" opacity="0.7"/>'
            f'<rect x="{mid_x - 54}" y="{y1 - 16}" width="108" height="14" fill="#0f172a" rx="3" opacity="0.8"/>'
            f'<text x="{mid_x}" y="{y1 - 5}" fill="{cat_color}" font-size="9" text-anchor="middle">'
            f'{flow["category"]}</text>'
            f'<rect x="{mid_x - 44}" y="{y1 + 2}" width="88" height="12" fill="#0f172a" rx="3" opacity="0.7"/>'
            f'<text x="{mid_x}" y="{y1 + 12}" fill="{agr_color}" font-size="8" text-anchor="middle">'
            f'via {flow["agreement"]} · {flow["residency"]}</text>'
        )

    # Title
    title = (
        f'<text x="{W//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">'
        f'Data Flow Compliance Map</text>'
        f'<text x="{W//2}" y="36" fill="#64748b" font-size="9" text-anchor="middle">'
        f'All flows US-region compliant · Governed by DPA / MSA / pilot_agreement</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b; border-radius:8px;">'
        + title + flow_svg + node_svg +
        '</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    coverage = compute_coverage()
    next_ag, next_days = next_expiry()
    blocked = blocked_agreements()

    chart1 = svg_timeline()
    chart2 = svg_data_flow()

    # Agreement table rows
    table_rows = ""
    for ag in AGREEMENTS:
        p = PARTNERS[ag["partner"]]
        d_left = days_until(ag["expiry"]) if ag["expiry"] else None
        if ag["status"] == "BLOCKED":
            status_badge = '<span style="background:#C74634;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">BLOCKED</span>'
        elif ag["status"] == "ACTIVE" and d_left is not None and d_left <= 30:
            status_badge = f'<span style="background:#f59e0b;color:#0f172a;padding:2px 8px;border-radius:4px;font-size:11px;">RENEW {d_left}d</span>'
        else:
            status_badge = f'<span style="background:#166534;color:#d1fae5;padding:2px 8px;border-radius:4px;font-size:11px;">{ag["status"]}</span>'

        type_color = TYPE_COLORS.get(ag["type"], "#94a3b8")
        table_rows += (
            f'<tr><td>{p["name"]}</td>'
            f'<td><span style="color:{type_color};font-weight:600;">{ag["type"]}</span></td>'
            f'<td>{ag["signed"] or "—"}</td>'
            f'<td>{ag["expiry"] or "—"}</td>'
            f'<td>{d_left if d_left is not None else "—"}</td>'
            f'<td>{status_badge}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Partner NDA Manager — Port 8289</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 20px; min-width: 160px; }}
  .card .val {{ font-size: 28px; font-weight: 700; color: #38bdf8; }}
  .card .lbl {{ font-size: 11px; color: #64748b; margin-top: 2px; text-transform: uppercase; letter-spacing: .05em; }}
  .card.warn .val {{ color: #f59e0b; }}
  .card.danger .val {{ color: #C74634; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 15px; color: #94a3b8; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .chart-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1e293b; color: #64748b; padding: 8px 12px; text-align: left; font-weight: 600; border-bottom: 1px solid #334155; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b88; }}
  footer {{ margin-top: 32px; color: #334155; font-size: 11px; }}
</style>
</head>
<body>
<h1>Partner NDA Manager</h1>
<div class="subtitle">OCI Robot Cloud · Agreement & Data Processing Compliance · Port 8289</div>

<div class="metrics">
  <div class="card">
    <div class="val">{len(PARTNERS)}</div>
    <div class="lbl">Total Partners</div>
  </div>
  <div class="card">
    <div class="val">{coverage}%</div>
    <div class="lbl">Agreement Coverage</div>
  </div>
  <div class="card warn">
    <div class="val">{next_days}d</div>
    <div class="lbl">Days to Next Expiry</div>
  </div>
  <div class="card {'danger' if blocked else ''}">
    <div class="val">{len(blocked)}</div>
    <div class="lbl">Blocked Agreements</div>
  </div>
  <div class="card">
    <div class="val">{len(AGREEMENTS)}</div>
    <div class="lbl">Total Agreements</div>
  </div>
  <div class="card">
    <div class="val">100%</div>
    <div class="lbl">Data Residency US</div>
  </div>
</div>

{'<div style="background:#7f1d1d;border:1px solid #C74634;border-radius:8px;padding:12px 16px;margin-bottom:24px;color:#fef9c3;font-size:13px;"><strong>BLOCKED:</strong> Machina Labs DPA awaiting signature — robot_demos data flow halted until signed.</div>' if blocked else ''}

<div class="section">
  <h2>Agreement Status Timeline — 8 Partners</h2>
  <div class="chart-wrap">{chart1}</div>
  <p style="color:#64748b;font-size:12px;margin-top:8px;">
    Red dot = renewal warning (&lt;30 days). 1X Technologies NDA expires in ~45 days.
  </p>
</div>

<div class="section">
  <h2>Data Flow Compliance Diagram</h2>
  <div class="chart-wrap">{chart2}</div>
  <p style="color:#64748b;font-size:12px;margin-top:8px;">
    All active data flows are US-West region compliant. Governing agreement type shown per flow.
  </p>
</div>

<div class="section">
  <h2>All Agreements</h2>
  <table>
    <thead><tr><th>Partner</th><th>Type</th><th>Signed</th><th>Expiry</th><th>Days Left</th><th>Status</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<footer>OCI Robot Cloud · Partner NDA Manager · {TODAY.strftime('%Y-%m-%d')}</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Partner NDA Manager",
        description="Manages NDA and data processing agreements with OCI Robot Cloud partners",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "partner_nda_manager", "port": 8289}

    @app.get("/api/metrics")
    def metrics():
        next_ag, next_days = next_expiry()
        blocked = blocked_agreements()
        return {
            "total_partners": len(PARTNERS),
            "agreement_coverage_pct": compute_coverage(),
            "days_to_next_expiry": next_days,
            "blocked_agreements": len(blocked),
            "total_agreements": len(AGREEMENTS),
            "data_residency_compliant": True,
        }

    @app.get("/api/agreements")
    def agreements():
        result = []
        for ag in AGREEMENTS:
            result.append({
                **ag,
                "partner_name": PARTNERS[ag["partner"]]["name"],
                "days_until_expiry": days_until(ag["expiry"]) if ag["expiry"] else None,
            })
        return result

    @app.get("/api/data-flows")
    def data_flows():
        return DATA_FLOWS

else:
    # ---------------------------------------------------------------------------
    # Fallback: stdlib http.server
    # ---------------------------------------------------------------------------
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8289)
    else:
        print("[partner_nda_manager] fastapi not found — using stdlib http.server on port 8289")
        with socketserver.TCPServer(("", 8289), _Handler) as httpd:
            httpd.serve_forever()
