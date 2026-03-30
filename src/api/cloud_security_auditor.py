"""Cloud Security Auditor — FastAPI port 8799"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8799

def build_html():
    rng = random.Random(99)

    # Threat event timeline — 48h, events per hour
    hours = list(range(48))
    threat_counts = [int(abs(rng.gauss(4, 2)) + 2 * math.sin(h * math.pi / 12) + 1) for h in hours]
    threat_counts[11] = 22   # spike: brute-force window
    threat_counts[31] = 18   # spike: port scan burst

    # CVE severity distribution (fake but plausible)
    cve_data = [
        ("CVE-2025-1337", "Critical", 9.8, "libssl",       "Patch available"),
        ("CVE-2025-0892", "High",     8.1, "nginx 1.24",   "Patch available"),
        ("CVE-2024-9901", "High",     7.6, "python 3.11",  "Mitigated"),
        ("CVE-2024-8821", "Medium",   6.3, "containerd",   "Under review"),
        ("CVE-2024-7734", "Medium",   5.9, "grpc",         "Mitigated"),
        ("CVE-2024-6112", "Low",      3.2, "curl 8.6",     "Accepted risk"),
    ]

    # Compliance radar — 6 domains, score 0–100
    domains   = ["IAM", "Network", "Encryption", "Logging", "Patching", "Secrets"]
    scores    = [88, 74, 95, 81, 62, 90]
    angles    = [i * 2 * math.pi / len(domains) for i in range(len(domains))]
    cx, cy, R = 120, 110, 80

    def radar_pt(i, r_frac):
        a = angles[i] - math.pi / 2
        return cx + r_frac * R * math.cos(a), cy + r_frac * R * math.sin(a)

    # Grid rings
    radar_rings = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{radar_pt(i, frac)[0]:.1f},{radar_pt(i, frac)[1]:.1f}" for i in range(len(domains)))
        radar_rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'

    # Spokes
    radar_spokes = ""
    radar_labels = ""
    for i, d in enumerate(domains):
        ox, oy = radar_pt(i, 0)
        tx, ty = radar_pt(i, 1.18)
        radar_spokes += f'<line x1="{cx}" y1="{cy}" x2="{ox:.1f}" y2="{oy:.1f}" stroke="#475569" stroke-width="1"/>'
        radar_labels += f'<text x="{tx:.1f}" y="{ty:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{d}\n{scores[i]}%</text>'

    # Score polygon
    score_pts = " ".join(f"{radar_pt(i, scores[i]/100)[0]:.1f},{radar_pt(i, scores[i]/100)[1]:.1f}" for i in range(len(domains)))

    # Threat timeline SVG
    TW, TH, TPAD = 680, 130, 35
    tc_max = max(threat_counts) + 2
    bar_w = (TW - TPAD * 2) / len(hours) - 1

    bars = ""
    for i, (h, c) in enumerate(zip(hours, threat_counts)):
        bx = TPAD + i * ((TW - TPAD * 2) / len(hours))
        bh = (c / tc_max) * (TH - TPAD - 10)
        by = TH - TPAD - bh
        color = "#ef4444" if c > 15 else ("#f97316" if c > 10 else "#38bdf8")
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.85" rx="1"/>'

    x_labels = ""
    for i in range(0, 48, 6):
        bx = TPAD + i * ((TW - TPAD * 2) / len(hours)) + bar_w / 2
        x_labels += f'<text x="{bx:.1f}" y="{TH - 6}" fill="#64748b" font-size="9" text-anchor="middle">-{48-i}h</text>'

    # Overall risk score
    avg_score = sum(scores) / len(scores)
    risk_score = 100 - avg_score
    risk_color = "#ef4444" if risk_score > 35 else ("#f59e0b" if risk_score > 20 else "#22c55e")
    risk_label = "HIGH" if risk_score > 35 else ("MEDIUM" if risk_score > 20 else "LOW")

    total_events_48h = sum(threat_counts)
    critical_cves    = sum(1 for _, sev, *_ in cve_data if sev == "Critical")
    open_findings    = sum(1 for *_, status in cve_data if status not in ("Mitigated", "Accepted risk"))

    sev_color = {"Critical": ("#450a0a", "#fca5a5"), "High": ("#7c2d12", "#fdba74"),
                 "Medium":   ("#713f12", "#fde047"), "Low":  ("#052e16", "#86efac")}

    cve_rows = ""
    for cve_id, sev, score_v, pkg, status in cve_data:
        bg, fg = sev_color.get(sev, ("#1e293b", "#e2e8f0"))
        stat_color = "#86efac" if status in ("Mitigated", "Accepted risk") else "#fca5a5"
        cve_rows += f"""
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px 8px;font-family:monospace;font-size:0.8rem">{cve_id}</td>
      <td style="padding:6px 8px"><span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700">{sev}</span></td>
      <td style="padding:6px 8px;color:#e2e8f0">{score_v}</td>
      <td style="padding:6px 8px;color:#94a3b8;font-family:monospace;font-size:0.8rem">{pkg}</td>
      <td style="padding:6px 8px;color:{stat_color};font-size:0.82rem">{status}</td>
    </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Cloud Security Auditor</title>
<meta http-equiv="refresh" content="30">
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 20px 6px;font-size:1.6rem;letter-spacing:0.03em}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 16px}}
.kpi{{background:#1e293b;border-radius:8px;padding:16px;border-left:4px solid #38bdf8}}
.kpi .label{{font-size:0.73rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em}}
.kpi .value{{font-size:1.5rem;font-weight:700;margin-top:4px}}
.kpi .sub{{font-size:0.73rem;color:#64748b;margin-top:2px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:0 20px 14px}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;font-weight:600}}
.two-col{{display:grid;grid-template-columns:260px 1fr;gap:16px;margin:0 20px 14px}}
.footer{{color:#475569;font-size:0.75rem;padding:8px 20px 20px}}
</style></head>
<body>
<h1>Cloud Security Auditor</h1>
<div class="subtitle">OCI Robot Cloud · Continuous security posture monitoring · port {PORT}</div>

<div class="grid">
  <div class="kpi" style="border-color:{risk_color}">
    <div class="label">Risk Level</div>
    <div class="value" style="color:{risk_color}">{risk_label}</div>
    <div class="sub">score {risk_score:.1f} / 100</div>
  </div>
  <div class="kpi">
    <div class="label">Threat Events (48h)</div>
    <div class="value" style="color:#f97316">{total_events_48h}</div>
    <div class="sub">2 high-severity spikes</div>
  </div>
  <div class="kpi">
    <div class="label">Critical CVEs</div>
    <div class="value" style="color:#ef4444">{critical_cves}</div>
    <div class="sub">{open_findings} open findings total</div>
  </div>
  <div class="kpi">
    <div class="label">Compliance Avg</div>
    <div class="value" style="color:#22c55e">{avg_score:.1f}%</div>
    <div class="sub">across {len(domains)} domains</div>
  </div>
</div>

<div class="two-col">
  <div class="card" style="margin:0">
    <h2>Compliance Radar</h2>
    <svg width="100%" viewBox="0 0 240 220" preserveAspectRatio="xMidYMid meet">
      {radar_rings}
      {radar_spokes}
      <polygon points="{score_pts}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="2"/>
      {radar_labels}
      <text x="{cx}" y="{cy+4}" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="700">{avg_score:.0f}%</text>
    </svg>
  </div>
  <div class="card" style="margin:0">
    <h2>Threat Event Timeline — last 48 hours</h2>
    <svg width="100%" viewBox="0 0 {TW} {TH}" preserveAspectRatio="xMidYMid meet">
      <!-- Y grid -->
      {''.join(f'<line x1="{TPAD}" y1="{TH - TPAD - (v/tc_max)*(TH-TPAD-10):.1f}" x2="{TW-TPAD}" y2="{TH - TPAD - (v/tc_max)*(TH-TPAD-10):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/><text x="{TPAD-4}" y="{TH - TPAD - (v/tc_max)*(TH-TPAD-10)+4:.1f}" fill="#64748b" font-size="8" text-anchor="end">{v}</text>' for v in [5, 10, 15, 20])}
      {bars}
      {x_labels}
      <line x1="{TPAD}" y1="{TH-TPAD-(12/tc_max)*(TH-TPAD-10):.1f}" x2="{TW-TPAD}" y2="{TH-TPAD-(12/tc_max)*(TH-TPAD-10):.1f}" stroke="#f97316" stroke-width="1" stroke-dasharray="5,3" opacity="0.7"/>
      <text x="{TW-TPAD-4}" y="{TH-TPAD-(12/tc_max)*(TH-TPAD-10)-4:.1f}" fill="#f97316" font-size="8" text-anchor="end">alert threshold</text>
      <text x="{TPAD}" y="14" fill="#94a3b8" font-size="10">Events / hour</text>
    </svg>
    <div style="font-size:0.75rem;color:#64748b;margin-top:4px">
      <span style="color:#ef4444">&#9632;</span> Critical (&gt;15)&nbsp;&nbsp;
      <span style="color:#f97316">&#9632;</span> High (10-15)&nbsp;&nbsp;
      <span style="color:#38bdf8">&#9632;</span> Normal
    </div>
  </div>
</div>

<div class="card">
  <h2>CVE Findings — Active Vulnerabilities</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
    <tr style="border-bottom:1px solid #334155">
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">CVE ID</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Severity</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">CVSS</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Package</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Status</th>
    </tr>
    {cve_rows}
  </table>
</div>

<div class="card">
  <h2>Recent Security Events</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
    <tr style="border-bottom:1px solid #334155">
      <th style="text-align:left;padding:5px 8px;color:#94a3b8">Time (UTC)</th>
      <th style="text-align:left;padding:5px 8px;color:#94a3b8">Type</th>
      <th style="text-align:left;padding:5px 8px;color:#94a3b8">Source IP</th>
      <th style="text-align:left;padding:5px 8px;color:#94a3b8">Action</th>
      <th style="text-align:left;padding:5px 8px;color:#94a3b8">Result</th>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:5px 8px;color:#94a3b8">2026-03-30 11:43:02</td>
      <td style="padding:5px 8px;color:#ef4444">Brute-force SSH</td>
      <td style="padding:5px 8px;font-family:monospace">185.220.101.47</td>
      <td style="padding:5px 8px">Auto-block after 10 attempts</td>
      <td style="padding:5px 8px;color:#86efac">Blocked / IP banned 24h</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:5px 8px;color:#94a3b8">2026-03-30 07:21:14</td>
      <td style="padding:5px 8px;color:#f97316">Port Scan</td>
      <td style="padding:5px 8px;font-family:monospace">91.108.56.203</td>
      <td style="padding:5px 8px">Firewall rule triggered</td>
      <td style="padding:5px 8px;color:#86efac">Blocked / Logged</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:5px 8px;color:#94a3b8">2026-03-30 03:05:57</td>
      <td style="padding:5px 8px;color:#fde047">IAM Anomaly</td>
      <td style="padding:5px 8px;font-family:monospace">10.0.4.22 (internal)</td>
      <td style="padding:5px 8px">Unusual privilege escalation attempt</td>
      <td style="padding:5px 8px;color:#fca5a5">Alert sent — under investigation</td>
    </tr>
    <tr>
      <td style="padding:5px 8px;color:#94a3b8">2026-03-29 22:11:38</td>
      <td style="padding:5px 8px;color:#38bdf8">TLS Cert Expiry</td>
      <td style="padding:5px 8px;font-family:monospace">—</td>
      <td style="padding:5px 8px">Cert for api.ocirobotcloud.com expires in 12d</td>
      <td style="padding:5px 8px;color:#fde047">Renewal scheduled</td>
    </tr>
  </table>
</div>

<div class="footer">OCI Robot Cloud · Cloud Security Auditor · port {PORT} · auto-refresh 30s</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cloud Security Auditor")
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
