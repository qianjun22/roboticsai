"""OCI Robot Cloud — Compliance & Data Governance Reporter  (port 8194)"""

import json
from datetime import datetime, timezone

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

FRAMEWORKS = {
    "data_residency": {
        "name": "Data Residency",
        "status": "COMPLIANT",
        "details": "All training data stored in OCI us-ashburn-1 (US-origin)",
        "last_audit": "2026-03-01",
        "evidence_url": "oci://robotics-compliance/data-residency-2026-03.pdf",
    },
    "access_control": {
        "name": "Access Control",
        "status": "COMPLIANT",
        "details": "RBAC enforced; API keys scoped per partner; no cross-tenant access",
        "last_audit": "2026-03-15",
    },
    "data_encryption": {
        "name": "Data Encryption",
        "status": "COMPLIANT",
        "details": "AES-256 at rest, TLS 1.3 in transit; OCI Vault key management",
        "last_audit": "2026-03-01",
    },
    "training_data_lineage": {
        "name": "Training Data Lineage",
        "status": "PARTIAL",
        "details": "SDG data lineage tracked; real demo uploads need hash verification",
        "last_audit": "2026-03-20",
        "gap": "Partner upload checksums not yet automated",
    },
    "model_output_logging": {
        "name": "Model Output Logging",
        "status": "COMPLIANT",
        "details": "All /predict calls logged with input hash, output hash, latency, partner_id; 90d retention",
        "last_audit": "2026-03-25",
    },
}

AUDIT_LOG = [
    {"date": "2026-03-25", "framework": "model_output_logging", "event": "audit_pass",         "actor": "compliance-bot", "note": "90-day retention window verified"},
    {"date": "2026-03-20", "framework": "training_data_lineage", "event": "gap_identified",    "actor": "sec-review",     "note": "Upload checksum automation missing"},
    {"date": "2026-03-15", "framework": "access_control",        "event": "audit_pass",         "actor": "compliance-bot", "note": "RBAC policy diff clean"},
    {"date": "2026-03-12", "framework": "data_residency",        "event": "audit_pass",         "actor": "compliance-bot", "note": "Storage region confirmed us-ashburn-1"},
    {"date": "2026-03-10", "framework": "data_encryption",       "event": "remediation_complete","actor": "infra-team",    "note": "Rotated OCI Vault encryption keys"},
    {"date": "2026-03-05", "framework": "training_data_lineage", "event": "remediation_complete","actor": "ml-team",      "note": "SDG pipeline lineage tagging deployed"},
    {"date": "2026-03-03", "framework": "access_control",        "event": "gap_identified",    "actor": "pen-test",      "note": "Stale API key found; rotated immediately"},
    {"date": "2026-03-01", "framework": "data_residency",        "event": "audit_pass",         "actor": "compliance-bot", "note": "Q1 data-residency audit complete"},
]

GAPS = [
    {
        "framework": "training_data_lineage",
        "gap": "Partner upload checksums not yet automated",
        "severity": "MEDIUM",
        "remediation": "Implement SHA-256 checksum verification on demo upload API endpoint",
        "owner": "ml-platform-team",
        "eta": "2026-04-15",
        "status": "IN_PROGRESS",
    }
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

STATUS_COLOR = {
    "COMPLIANT": "#22c55e",
    "PARTIAL": "#f59e0b",
    "NON_COMPLIANT": "#ef4444",
}


def _scorecard_svg() -> str:
    """680x200 horizontal bar chart — one bar per framework."""
    width, height = 680, 200
    bar_h = 22
    label_w = 190
    badge_w = 110
    chart_w = width - label_w - badge_w - 30
    rows = list(FRAMEWORKS.values())
    row_h = height // len(rows)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    for i, fw in enumerate(rows):
        y_center = i * row_h + row_h // 2
        color = STATUS_COLOR.get(fw["status"], "#6b7280")
        fill_pct = 1.0 if fw["status"] == "COMPLIANT" else (0.6 if fw["status"] == "PARTIAL" else 0.2)
        bar_fill_w = int(chart_w * fill_pct)

        # background track
        lines.append(
            f'<rect x="{label_w}" y="{y_center - bar_h//2}" width="{chart_w}" height="{bar_h}" '
            f'rx="4" fill="#334155"/>'
        )
        # filled bar
        lines.append(
            f'<rect x="{label_w}" y="{y_center - bar_h//2}" width="{bar_fill_w}" height="{bar_h}" '
            f'rx="4" fill="{color}" opacity="0.85"/>'
        )
        # label
        lines.append(
            f'<text x="{label_w - 8}" y="{y_center + 5}" text-anchor="end" '
            f'font-size="11" fill="#cbd5e1">{fw["name"]}</text>'
        )
        # badge
        bx = label_w + chart_w + 10
        lines.append(
            f'<rect x="{bx}" y="{y_center - 10}" width="{badge_w - 10}" height="20" '
            f'rx="10" fill="{color}" opacity="0.25"/>'
        )
        lines.append(
            f'<text x="{bx + (badge_w-10)//2}" y="{y_center + 5}" text-anchor="middle" '
            f'font-size="10" font-weight="bold" fill="{color}">{fw["status"]}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _timeline_svg() -> str:
    """680x140 dot timeline — 30 days, one row per framework."""
    width, height = 680, 140
    label_w = 190
    fw_keys = list(FRAMEWORKS.keys())
    row_h = height // len(fw_keys)
    days = 30
    day_w = (width - label_w - 10) / days

    # build lookup: (fw_key, day_offset) -> event_type
    base_date = datetime(2026, 3, 1)
    audit_lookup: dict = {}
    for entry in AUDIT_LOG:
        d = datetime.strptime(entry["date"], "%Y-%m-%d")
        offset = (d - base_date).days
        if 0 <= offset < days:
            audit_lookup[(entry["framework"], offset)] = entry["event"]

    event_color = {
        "audit_pass": "#22c55e",
        "gap_identified": "#f59e0b",
        "remediation_complete": "#38bdf8",
    }

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    for ri, fw_key in enumerate(fw_keys):
        y_center = ri * row_h + row_h // 2
        fw = FRAMEWORKS[fw_key]
        lines.append(
            f'<text x="{label_w - 8}" y="{y_center + 4}" text-anchor="end" '
            f'font-size="10" fill="#94a3b8">{fw["name"][:20]}</text>'
        )
        for day in range(days):
            cx = int(label_w + day * day_w + day_w / 2)
            ev = audit_lookup.get((fw_key, day))
            if ev:
                color = event_color.get(ev, "#6b7280")
                lines.append(
                    f'<circle cx="{cx}" cy="{y_center}" r="5" fill="{color}" opacity="0.9"/>'
                )
            else:
                lines.append(
                    f'<circle cx="{cx}" cy="{y_center}" r="2" fill="#334155"/>'
                )

    # day axis labels
    for d in [1, 7, 14, 21, 28]:
        cx = int(label_w + d * day_w)
        lines.append(
            f'<text x="{cx}" y="{height - 4}" text-anchor="middle" '
            f'font-size="9" fill="#64748b">Mar {d+1}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    scorecard = _scorecard_svg()
    timeline = _timeline_svg()

    compliant_count = sum(1 for f in FRAMEWORKS.values() if f["status"] == "COMPLIANT")
    total = len(FRAMEWORKS)
    score_pct = int(compliant_count / total * 100)

    fw_rows = ""
    for fw in FRAMEWORKS.values():
        color = STATUS_COLOR.get(fw["status"], "#6b7280")
        gap_html = ""
        if fw.get("gap"):
            gap_html = f'<div style="color:#f59e0b;font-size:11px;margin-top:4px">Gap: {fw["gap"]}</div>'
        fw_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#e2e8f0;font-weight:600">{fw['name']}</td>
          <td style="padding:8px 12px">
            <span style="background:{color}22;color:{color};padding:2px 10px;border-radius:12px;
                         font-size:11px;font-weight:700">{fw['status']}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8;font-size:12px">{fw['details']}</td>
          <td style="padding:8px 12px;color:#64748b;font-size:11px">{fw['last_audit']}</td>
        </tr>
        {gap_html}
        """

    audit_rows = ""
    ev_colors = {"audit_pass": "#22c55e", "gap_identified": "#f59e0b", "remediation_complete": "#38bdf8"}
    for entry in AUDIT_LOG:
        ec = ev_colors.get(entry["event"], "#94a3b8")
        audit_rows += f"""
        <tr>
          <td style="padding:6px 12px;color:#64748b;font-size:11px">{entry['date']}</td>
          <td style="padding:6px 12px;color:#94a3b8;font-size:12px">
            {FRAMEWORKS.get(entry['framework'],{}).get('name', entry['framework'])}
          </td>
          <td style="padding:6px 12px">
            <span style="color:{ec};font-size:11px;font-weight:600">{entry['event'].replace('_',' ').upper()}</span>
          </td>
          <td style="padding:6px 12px;color:#94a3b8;font-size:12px">{entry['note']}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Compliance Reporter</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .header {{ background: linear-gradient(135deg, #C74634 0%, #9b2f23 100%); padding: 24px 32px; }}
    .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
    .header p {{ color: #fca5a5; font-size: 13px; margin-top: 4px; }}
    .score-bar {{ background: #1e293b; padding: 20px 32px; border-bottom: 1px solid #334155;
                  display: flex; align-items: center; gap: 32px; }}
    .score-num {{ font-size: 48px; font-weight: 800; color: #22c55e; }}
    .score-label {{ color: #94a3b8; font-size: 13px; }}
    .container {{ padding: 24px 32px; max-width: 900px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ font-size: 14px; font-weight: 700; color: #38bdf8;
                   text-transform: uppercase; letter-spacing: 1px; margin-bottom: 14px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
             overflow: hidden; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:not(:last-child) {{ border-bottom: 1px solid #1e3a5f22; }}
    tr:hover {{ background: #0f2235; }}
    .gap-card {{ background: #1e293b; border: 1px solid #f59e0b44; border-radius: 10px;
                 padding: 16px 20px; }}
    .gap-title {{ color: #f59e0b; font-weight: 700; font-size: 13px; }}
    .gap-body {{ color: #94a3b8; font-size: 12px; margin-top: 8px; line-height: 1.6; }}
    .tag {{ display: inline-block; padding: 2px 8px; border-radius: 8px;
            font-size: 10px; font-weight: 600; margin-right: 6px; }}
    .footer {{ padding: 16px 32px; color: #334155; font-size: 11px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>OCI Robot Cloud — Compliance &amp; Data Governance</h1>
    <p>Enterprise compliance status as of 2026-03-30 &nbsp;|&nbsp; Port 8194</p>
  </div>

  <div class="score-bar">
    <div>
      <div class="score-num">{score_pct}%</div>
      <div class="score-label">Overall Compliance Score</div>
    </div>
    <div style="color:#64748b;font-size:13px">
      <div>{compliant_count} / {total} frameworks fully compliant</div>
      <div style="margin-top:4px">{len(GAPS)} open gap(s) &nbsp;|&nbsp; {len(AUDIT_LOG)} audit events (last 30d)</div>
    </div>
  </div>

  <div class="container">
    <div class="section">
      <h2>Framework Scorecard</h2>
      <div class="card" style="padding:12px">{scorecard}</div>
    </div>

    <div class="section">
      <h2>30-Day Audit Timeline</h2>
      <div class="card" style="padding:12px">{timeline}</div>
      <div style="margin-top:8px;display:flex;gap:20px;font-size:11px;color:#94a3b8">
        <span><span style="color:#22c55e">&#9679;</span> Audit Pass</span>
        <span><span style="color:#f59e0b">&#9679;</span> Gap Identified</span>
        <span><span style="color:#38bdf8">&#9679;</span> Remediation Complete</span>
      </div>
    </div>

    <div class="section">
      <h2>Framework Details</h2>
      <div class="card">
        <table>
          <thead>
            <tr style="background:#0f172a">
              <th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b">FRAMEWORK</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b">STATUS</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b">DETAILS</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b">LAST AUDIT</th>
            </tr>
          </thead>
          <tbody>
            {fw_rows}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>Open Gaps &amp; Remediation</h2>
      {''.join(f"""
      <div class="gap-card">
        <div class="gap-title">&#9888; {g['gap']}</div>
        <div class="gap-body">
          <span class="tag" style="background:#f59e0b22;color:#f59e0b">MEDIUM</span>
          <span class="tag" style="background:#38bdf822;color:#38bdf8">IN PROGRESS</span>
          <br><br>
          Framework: {FRAMEWORKS.get(g['framework'], {}).get('name', g['framework'])}<br>
          Remediation: {g['remediation']}<br>
          Owner: {g['owner']}<br>
          ETA: {g['eta']}
        </div>
      </div>""" for g in GAPS)}
    </div>

    <div class="section">
      <h2>Recent Audit Log</h2>
      <div class="card">
        <table>
          <thead>
            <tr style="background:#0f172a">
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b">DATE</th>
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b">FRAMEWORK</th>
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b">EVENT</th>
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b">NOTE</th>
            </tr>
          </thead>
          <tbody>{audit_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="footer">OCI Robot Cloud &copy; 2026 Oracle Corporation &mdash; Confidential</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud — Compliance Reporter",
        description="Enterprise compliance and data governance for OCI Robot Cloud.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, summary="Dashboard")
    def dashboard():
        return HTMLResponse(content=_dashboard_html())

    @app.get("/frameworks", summary="All compliance frameworks")
    def get_frameworks():
        return JSONResponse(content=FRAMEWORKS)

    @app.get("/audit-log", summary="Recent audit events")
    def get_audit_log():
        return JSONResponse(content=AUDIT_LOG)

    @app.get("/gaps", summary="Open compliance gaps")
    def get_gaps():
        return JSONResponse(content=GAPS)

    @app.get("/report", summary="Full compliance summary (PDF-ready JSON)")
    def get_report():
        compliant = sum(1 for f in FRAMEWORKS.values() if f["status"] == "COMPLIANT")
        return JSONResponse(content={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "score_pct": int(compliant / len(FRAMEWORKS) * 100),
            "frameworks_compliant": compliant,
            "frameworks_total": len(FRAMEWORKS),
            "open_gaps": len(GAPS),
            "frameworks": FRAMEWORKS,
            "audit_log": AUDIT_LOG,
            "gaps": GAPS,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8194)
else:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
