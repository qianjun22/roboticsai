"""Compliance Audit Trail — FastAPI port 8897"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8897

# SOC2 Type II controls (12/15 green)
SOC2_CONTROLS = [
    ("CC1.1", "Control Environment", "green"),
    ("CC2.1", "Communication & Info", "green"),
    ("CC3.1", "Risk Assessment", "green"),
    ("CC4.1", "Monitoring Activities", "green"),
    ("CC5.1", "Control Activities", "green"),
    ("CC6.1", "Logical Access", "green"),
    ("CC6.2", "New Access Provisioning", "green"),
    ("CC6.3", "Access Removal", "green"),
    ("CC7.1", "System Operations", "green"),
    ("CC7.2", "Change Management", "green"),
    ("CC8.1", "Change Management", "yellow"),
    ("CC9.1", "Risk Mitigation", "green"),
    ("A1.1", "Availability Monitoring", "green"),
    ("PI1.1", "Processing Integrity", "yellow"),
    ("C1.1", "Confidentiality", "red"),
]

# Recent audit events
AUDIT_EVENTS = [
    ("2026-03-30 14:23:11", "DATA_ACCESS", "model_weights_v2.pt read by svc-inference", "US-ASHBURN-1", "PASS"),
    ("2026-03-30 13:55:42", "AUTH_EVENT", "API key rotation completed — 0 stale keys remain", "US-PHOENIX-1", "PASS"),
    ("2026-03-30 12:10:08", "GDPR_CHECK", "EU data subject request fulfilled within 72h SLA", "EU-FRANKFURT-1", "PASS"),
    ("2026-03-30 11:44:30", "RESIDENCY", "Training batch 9812 — origin verified 100% US-OCI", "US-ASHBURN-1", "PASS"),
    ("2026-03-30 10:22:19", "FEDRAMP", "Encryption at rest verified AES-256 all volumes", "US-ASHBURN-1", "PASS"),
    ("2026-03-30 09:17:55", "POLICY", "Retention policy enforced — 847 records purged", "US-PHOENIX-1", "PASS"),
    ("2026-03-30 08:03:44", "AUDIT_LOG", "Immutable log integrity check — SHA256 chain valid", "US-ASHBURN-1", "PASS"),
    ("2026-03-29 23:59:01", "SOC2_SCAN", "Nightly control scan — 12/15 green, 2 yellow, 1 red", "US-ASHBURN-1", "WARN"),
]

def build_html():
    random.seed(99)
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>'
        for i, v in enumerate(data)
    )

    green_count = sum(1 for _, _, s in SOC2_CONTROLS if s == "green")
    yellow_count = sum(1 for _, _, s in SOC2_CONTROLS if s == "yellow")
    red_count = sum(1 for _, _, s in SOC2_CONTROLS if s == "red")

    # Control status grid
    control_cells = ""
    for ctrl_id, ctrl_name, status in SOC2_CONTROLS:
        bg = {"green": "#166534", "yellow": "#854d0e", "red": "#7f1d1d"}[status]
        dot = {"green": "#4ade80", "yellow": "#fbbf24", "red": "#f87171"}[status]
        control_cells += f"""
        <div style="background:{bg};padding:10px;border-radius:6px;margin:4px;min-width:130px">
          <span style="color:{dot};font-size:16px">&#9679;</span>
          <span style="font-size:12px;font-weight:bold;color:#e2e8f0"> {ctrl_id}</span><br/>
          <span style="font-size:11px;color:#94a3b8">{ctrl_name}</span>
        </div>"""

    # Event log rows
    event_rows = ""
    for ts, etype, desc, region, result in AUDIT_EVENTS:
        result_color = {"PASS": "#4ade80", "WARN": "#fbbf24", "FAIL": "#f87171"}[result]
        event_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:7px 10px;color:#64748b;font-size:12px;white-space:nowrap">{ts}</td>
          <td style="padding:7px 10px"><span style="background:#1e293b;padding:2px 8px;border-radius:4px;font-size:11px;color:#38bdf8">{etype}</span></td>
          <td style="padding:7px 10px;font-size:13px">{desc}</td>
          <td style="padding:7px 10px;color:#94a3b8;font-size:12px">{region}</td>
          <td style="padding:7px 10px;font-weight:bold;color:{result_color}">{result}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Compliance Audit Trail</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 5px}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:bold;margin-right:8px}}
.grid{{display:flex;flex-wrap:wrap}}
table{{border-collapse:collapse;width:100%}}</style></head>
<body>
<h1>Compliance Audit Trail</h1>
<p style="padding:0 20px;color:#94a3b8">Immutable audit log — SOC2 Type II readiness, GDPR, FedRAMP pathway, 100% US-origin OCI data residency</p>

<div class="card">
  <h2>Compliance Summary</h2>
  <span class="badge" style="background:#166534">{green_count}/15 Controls Green</span>
  <span class="badge" style="background:#854d0e">{yellow_count} Yellow</span>
  <span class="badge" style="background:#7f1d1d">{red_count} Red</span>
  &nbsp;
  <span style="color:#4ade80;font-size:13px">Data Residency: 100% US-origin OCI</span>
  &nbsp;&nbsp;
  <span style="color:#38bdf8;font-size:13px">FedRAMP: In Progress</span>
</div>

<div class="card">
  <h2>SOC2 Type II — Control Status Grid</h2>
  <div class="grid">{control_cells}</div>
</div>

<div class="card">
  <h2>Audit Event Log (Immutable — SHA256 Chain)</h2>
  <table>
    <thead><tr>
      <th style="text-align:left;padding:7px 10px;color:#64748b">Timestamp</th>
      <th style="text-align:left;padding:7px 10px;color:#64748b">Type</th>
      <th style="text-align:left;padding:7px 10px;color:#64748b">Description</th>
      <th style="text-align:left;padding:7px 10px;color:#64748b">Region</th>
      <th style="text-align:left;padding:7px 10px;color:#64748b">Result</th>
    </tr></thead>
    <tbody>{event_rows}</tbody>
  </table>
</div>

<div class="card">
  <h2>Event Rate (Last 10 Intervals)</h2>
  <svg width="450" height="180">{bars}</svg>
  <p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Compliance Audit Trail")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
