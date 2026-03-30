"""
partner_tech_review_tracker.py — port 8629
Partner technology review tracking dashboard.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Partner Tech Review Tracker — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:32px}
  h1{color:#C74634;font-size:2rem;font-weight:700;margin-bottom:6px;letter-spacing:-0.5px}
  h2{color:#C74634;font-size:1.15rem;font-weight:600;margin:28px 0 12px}
  .subtitle{color:#94a3b8;font-size:0.95rem;margin-bottom:32px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .card-full{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:24px}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center}
  .metric-val{color:#38bdf8;font-size:1.8rem;font-weight:700;line-height:1}
  .metric-lbl{color:#64748b;font-size:0.78rem;margin-top:6px;text-transform:uppercase;letter-spacing:.05em}
  .metric-val.warn{color:#f59e0b}
  .metric-val.crit{color:#ef4444}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>Partner Tech Review Tracker</h1>
<p class="subtitle">Port 8629 &nbsp;|&nbsp; Quarterly technical reviews — PI / Apptronik / 1X / Machina / Wandelbots</p>

<div class="metrics">
  <div class="metric"><div class="metric-val">3</div><div class="metric-lbl">Reviews Completed</div></div>
  <div class="metric"><div class="metric-val warn">1</div><div class="metric-lbl">Overdue (Machina Q1)</div></div>
  <div class="metric"><div class="metric-val crit">3</div><div class="metric-lbl">Critical Action Items</div></div>
  <div class="metric"><div class="metric-val">8d</div><div class="metric-lbl">Avg Days to Resolve</div></div>
</div>

<!-- Chart 1: Quarterly Review Gantt -->
<div class="card-full">
  <h2>Quarterly Review Schedule — Gantt</h2>
  <svg viewBox="0 0 860 310" width="100%" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="120" y1="270" x2="830" y2="270" stroke="#334155" stroke-width="1.5"/>
    <line x1="120" y1="30"  x2="120" y2="270" stroke="#334155" stroke-width="1.5"/>
    <!-- Q headers -->
    <rect x="120" y="30" width="210" height="22" fill="#1e3a5f" rx="2"/>
    <text x="225" y="45" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Q1 2026</text>
    <rect x="330" y="30" width="240" height="22" fill="#1e3a5f" rx="2"/>
    <text x="450" y="45" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Q2 2026</text>
    <rect x="570" y="30" width="240" height="22" fill="#1e3a5f" rx="2"/>
    <text x="690" y="45" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Q3 2026</text>
    <!-- partner labels -->
    <text x="112" y="80"  fill="#94a3b8" font-size="11" text-anchor="end">PI</text>
    <text x="112" y="126" fill="#94a3b8" font-size="11" text-anchor="end">Apptronik</text>
    <text x="112" y="172" fill="#94a3b8" font-size="11" text-anchor="end">1X</text>
    <text x="112" y="218" fill="#94a3b8" font-size="11" text-anchor="end">Machina</text>
    <text x="112" y="264" fill="#94a3b8" font-size="11" text-anchor="end">Wandelbots</text>
    <!-- row lines -->
    <line x1="120" y1="56"  x2="830" y2="56"  stroke="#334155" stroke-width="0.5"/>
    <line x1="120" y1="102" x2="830" y2="102" stroke="#334155" stroke-width="0.5"/>
    <line x1="120" y1="148" x2="830" y2="148" stroke="#334155" stroke-width="0.5"/>
    <line x1="120" y1="194" x2="830" y2="194" stroke="#334155" stroke-width="0.5"/>
    <line x1="120" y1="240" x2="830" y2="240" stroke="#334155" stroke-width="0.5"/>
    <!-- col dividers -->
    <line x1="330" y1="30" x2="330" y2="270" stroke="#334155" stroke-width="0.5" stroke-dasharray="4 3"/>
    <line x1="570" y1="30" x2="570" y2="270" stroke="#334155" stroke-width="0.5" stroke-dasharray="4 3"/>
    <!-- PI: Q1=COMPLETED, Q2=COMPLETED, Q3=SCHEDULED -->
    <rect x="130" y="62"  width="190" height="28" fill="#16a34a" rx="4"/>
    <text x="225" y="80"  fill="#fff" font-size="10" text-anchor="middle" font-weight="600">COMPLETED</text>
    <rect x="340" y="62"  width="220" height="28" fill="#16a34a" rx="4"/>
    <text x="450" y="80"  fill="#fff" font-size="10" text-anchor="middle" font-weight="600">COMPLETED</text>
    <rect x="580" y="62"  width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="690" y="80"  fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Jul 14</text>
    <!-- Apptronik -->
    <rect x="130" y="108" width="190" height="28" fill="#16a34a" rx="4"/>
    <text x="225" y="126" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">COMPLETED</text>
    <rect x="340" y="108" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="450" y="126" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Apr 22</text>
    <rect x="580" y="108" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="690" y="126" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Aug 5</text>
    <!-- 1X -->
    <rect x="130" y="154" width="190" height="28" fill="#16a34a" rx="4"/>
    <text x="225" y="172" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">COMPLETED</text>
    <rect x="340" y="154" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="450" y="172" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED May 8</text>
    <rect x="580" y="154" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="690" y="172" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Aug 19</text>
    <!-- Machina: Q1=OVERDUE -->
    <rect x="130" y="200" width="190" height="28" fill="#b45309" rx="4"/>
    <text x="225" y="218" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">OVERDUE — DPA</text>
    <rect x="340" y="200" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="450" y="218" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Jun 3</text>
    <rect x="580" y="200" width="220" height="28" fill="#1d4ed8" rx="4"/>
    <text x="690" y="218" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Sep 2</text>
    <!-- Wandelbots -->
    <rect x="130" y="246" width="190" height="18" fill="#16a34a" rx="4"/>
    <text x="225" y="259" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">COMPLETED</text>
    <rect x="340" y="246" width="220" height="18" fill="#1d4ed8" rx="4"/>
    <text x="450" y="259" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED May 20</text>
    <rect x="580" y="246" width="220" height="18" fill="#1d4ed8" rx="4"/>
    <text x="690" y="259" fill="#fff" font-size="10" text-anchor="middle" font-weight="600">SCHEDULED Sep 16</text>
    <!-- legend -->
    <rect x="640" y="278" width="12" height="10" fill="#16a34a" rx="2"/>
    <text x="656" y="287" fill="#94a3b8" font-size="9">Completed</text>
    <rect x="710" y="278" width="12" height="10" fill="#b45309" rx="2"/>
    <text x="726" y="287" fill="#94a3b8" font-size="9">Overdue</text>
    <rect x="765" y="278" width="12" height="10" fill="#1d4ed8" rx="2"/>
    <text x="781" y="287" fill="#94a3b8" font-size="9">Scheduled</text>
  </svg>
</div>

<div class="grid">
<!-- Chart 2: Tech Health Scorecard -->
<div class="card">
  <h2>Tech Health Scorecard — 5 Dimensions</h2>
  <svg viewBox="0 0 420 320" width="100%" xmlns="http://www.w3.org/2000/svg">
    <line x1="50" y1="280" x2="400" y2="280" stroke="#334155" stroke-width="1.5"/>
    <line x1="50" y1="20"  x2="50"  y2="280" stroke="#334155" stroke-width="1.5"/>
    <text x="42" y="284" fill="#64748b" font-size="9" text-anchor="end">0</text>
    <text x="42" y="234" fill="#64748b" font-size="9" text-anchor="end">25</text>
    <text x="42" y="184" fill="#64748b" font-size="9" text-anchor="end">50</text>
    <text x="42" y="134" fill="#64748b" font-size="9" text-anchor="end">75</text>
    <text x="42" y="84"  fill="#64748b" font-size="9" text-anchor="end">100</text>
    <line x1="50" y1="234" x2="400" y2="234" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="184" x2="400" y2="184" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="134" x2="400" y2="134" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="84"  x2="400" y2="84"  stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <!-- Group 1: Integration -->
    <text x="112" y="296" fill="#94a3b8" font-size="8" text-anchor="middle">Integration</text>
    <rect x="65"  y="96"  width="10" height="184" fill="#16a34a" rx="2"/>
    <rect x="78"  y="124" width="10" height="156" fill="#16a34a" rx="2"/>
    <rect x="91"  y="110" width="10" height="170" fill="#16a34a" rx="2"/>
    <rect x="104" y="190" width="10" height="90"  fill="#ef4444" rx="2"/>
    <rect x="117" y="140" width="10" height="140" fill="#f59e0b" rx="2"/>
    <!-- Group 2: SR -->
    <text x="202" y="296" fill="#94a3b8" font-size="8" text-anchor="middle">Success Rate</text>
    <rect x="155" y="104" width="10" height="176" fill="#16a34a" rx="2"/>
    <rect x="168" y="136" width="10" height="144" fill="#f59e0b" rx="2"/>
    <rect x="181" y="120" width="10" height="160" fill="#16a34a" rx="2"/>
    <rect x="194" y="204" width="10" height="76"  fill="#ef4444" rx="2"/>
    <rect x="207" y="130" width="10" height="150" fill="#f59e0b" rx="2"/>
    <!-- Group 3: Latency -->
    <text x="292" y="296" fill="#94a3b8" font-size="8" text-anchor="middle">Latency</text>
    <rect x="245" y="110" width="10" height="170" fill="#16a34a" rx="2"/>
    <rect x="258" y="120" width="10" height="160" fill="#16a34a" rx="2"/>
    <rect x="271" y="104" width="10" height="176" fill="#16a34a" rx="2"/>
    <rect x="284" y="170" width="10" height="110" fill="#f59e0b" rx="2"/>
    <rect x="297" y="144" width="10" height="136" fill="#f59e0b" rx="2"/>
    <!-- Group 4: Data -->
    <text x="382" y="296" fill="#94a3b8" font-size="8" text-anchor="middle">Data Quality</text>
    <rect x="335" y="100" width="10" height="180" fill="#16a34a" rx="2"/>
    <rect x="348" y="130" width="10" height="150" fill="#16a34a" rx="2"/>
    <rect x="361" y="116" width="10" height="164" fill="#16a34a" rx="2"/>
    <rect x="374" y="220" width="10" height="60"  fill="#ef4444" rx="2"/>
    <rect x="387" y="136" width="10" height="144" fill="#f59e0b" rx="2"/>
    <!-- legend -->
    <rect x="55" y="22" width="8" height="8" fill="#16a34a" rx="1"/>
    <text x="67" y="30" fill="#94a3b8" font-size="8">PI</text>
    <rect x="85" y="22" width="8" height="8" fill="#16a34a" rx="1" opacity="0.7"/>
    <text x="97" y="30" fill="#94a3b8" font-size="8">Apt</text>
    <rect x="118" y="22" width="8" height="8" fill="#16a34a" rx="1" opacity="0.8"/>
    <text x="130" y="30" fill="#94a3b8" font-size="8">1X</text>
    <rect x="150" y="22" width="8" height="8" fill="#ef4444" rx="1"/>
    <text x="162" y="30" fill="#94a3b8" font-size="8">Machina</text>
    <rect x="205" y="22" width="8" height="8" fill="#f59e0b" rx="1"/>
    <text x="217" y="30" fill="#94a3b8" font-size="8">Wandelbots</text>
    <text x="225" y="310" fill="#64748b" font-size="8" text-anchor="middle">Score (0-100)</text>
  </svg>
</div>

<!-- Chart 3: Open Action Items Heatmap -->
<div class="card">
  <h2>Open Action Items — Priority x Partner Heatmap</h2>
  <svg viewBox="0 0 420 310" width="100%" xmlns="http://www.w3.org/2000/svg">
    <!-- column headers -->
    <text x="120" y="28" fill="#94a3b8" font-size="10" text-anchor="middle" font-weight="600">PI</text>
    <text x="195" y="28" fill="#94a3b8" font-size="10" text-anchor="middle" font-weight="600">Apptronik</text>
    <text x="265" y="28" fill="#94a3b8" font-size="10" text-anchor="middle" font-weight="600">1X</text>
    <text x="330" y="28" fill="#94a3b8" font-size="10" text-anchor="middle" font-weight="600">Machina</text>
    <text x="395" y="28" fill="#94a3b8" font-size="10" text-anchor="middle" font-weight="600">Wandelbots</text>
    <!-- row headers -->
    <text x="52" y="82"  fill="#ef4444" font-size="10" text-anchor="end" font-weight="600">CRITICAL</text>
    <text x="52" y="152" fill="#f59e0b" font-size="10" text-anchor="end" font-weight="600">HIGH</text>
    <text x="52" y="222" fill="#38bdf8" font-size="10" text-anchor="end" font-weight="600">MEDIUM</text>
    <!-- CRITICAL row -->
    <rect x="85"  y="40" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="120" y="75" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <rect x="160" y="40" width="70" height="58" fill="#7c2d12" rx="6" stroke="#c2410c" stroke-width="1"/>
    <text x="195" y="75" fill="#fca5a5" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <rect x="230" y="40" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="265" y="75" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <rect x="295" y="40" width="70" height="58" fill="#7f1d1d" rx="6" stroke="#ef4444" stroke-width="2"/>
    <text x="330" y="75" fill="#fca5a5" font-size="26" text-anchor="middle" font-weight="700">3</text>
    <rect x="360" y="40" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="395" y="75" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <!-- HIGH row -->
    <rect x="85"  y="110" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="120" y="145" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <rect x="160" y="110" width="70" height="58" fill="#78350f" rx="6" stroke="#f59e0b" stroke-width="1"/>
    <text x="195" y="145" fill="#fde68a" font-size="22" text-anchor="middle" font-weight="700">2</text>
    <rect x="230" y="110" width="70" height="58" fill="#451a03" rx="6" stroke="#f59e0b" stroke-width="1"/>
    <text x="265" y="145" fill="#fde68a" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <rect x="295" y="110" width="70" height="58" fill="#78350f" rx="6" stroke="#f59e0b" stroke-width="1"/>
    <text x="330" y="145" fill="#fde68a" font-size="22" text-anchor="middle" font-weight="700">2</text>
    <rect x="360" y="110" width="70" height="58" fill="#451a03" rx="6" stroke="#f59e0b" stroke-width="1"/>
    <text x="395" y="145" fill="#fde68a" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <!-- MEDIUM row -->
    <rect x="85"  y="180" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="120" y="215" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <rect x="160" y="180" width="70" height="58" fill="#0c2a4a" rx="6" stroke="#38bdf8" stroke-width="1"/>
    <text x="195" y="215" fill="#7dd3fc" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <rect x="230" y="180" width="70" height="58" fill="#0c2a4a" rx="6" stroke="#38bdf8" stroke-width="1"/>
    <text x="265" y="215" fill="#7dd3fc" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <rect x="295" y="180" width="70" height="58" fill="#0c2a4a" rx="6" stroke="#38bdf8" stroke-width="1"/>
    <text x="330" y="215" fill="#7dd3fc" font-size="22" text-anchor="middle" font-weight="700">1</text>
    <rect x="360" y="180" width="70" height="58" fill="#0f172a" rx="6" stroke="#334155" stroke-width="1"/>
    <text x="395" y="215" fill="#475569" font-size="22" text-anchor="middle" font-weight="700">0</text>
    <!-- totals -->
    <text x="52"  y="272" fill="#64748b" font-size="9" text-anchor="end">Total</text>
    <text x="120" y="272" fill="#4ade80" font-size="13" text-anchor="middle" font-weight="700">0</text>
    <text x="195" y="272" fill="#f59e0b" font-size="13" text-anchor="middle" font-weight="700">4</text>
    <text x="265" y="272" fill="#f59e0b" font-size="13" text-anchor="middle" font-weight="700">2</text>
    <text x="330" y="272" fill="#ef4444" font-size="13" text-anchor="middle" font-weight="700">6</text>
    <text x="395" y="272" fill="#f59e0b" font-size="13" text-anchor="middle" font-weight="700">1</text>
    <text x="420" y="272" fill="#94a3b8" font-size="9">= 14 items</text>
    <text x="85" y="294" fill="#475569" font-size="9">PI: all COMPLETED — no open items</text>
    <text x="85" y="306" fill="#ef4444" font-size="9">Machina: 3 CRITICAL (DPA + infra access + data audit)</text>
  </svg>
</div>
</div>

<div class="card">
  <h2>Partner Status Summary</h2>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:8px">
    <div style="background:#0f3d1a;border:1px solid #16a34a;border-radius:8px;padding:14px">
      <div style="color:#4ade80;font-size:0.95rem;font-weight:700;margin-bottom:6px">PI</div>
      <div style="color:#86efac;font-size:0.78rem;line-height:1.6">Q1 + Q2 complete<br/>0 open items<br/>All dims GREEN</div>
    </div>
    <div style="background:#1c1a0a;border:1px solid #ca8a04;border-radius:8px;padding:14px">
      <div style="color:#fbbf24;font-size:0.95rem;font-weight:700;margin-bottom:6px">Apptronik</div>
      <div style="color:#fde68a;font-size:0.78rem;line-height:1.6">Q1 complete<br/>4 open items (1 critical)<br/>SR YELLOW</div>
    </div>
    <div style="background:#0c2240;border:1px solid #1d4ed8;border-radius:8px;padding:14px">
      <div style="color:#60a5fa;font-size:0.95rem;font-weight:700;margin-bottom:6px">1X</div>
      <div style="color:#bfdbfe;font-size:0.78rem;line-height:1.6">Q1 complete<br/>2 open items<br/>All dims GREEN</div>
    </div>
    <div style="background:#3d0a0a;border:1px solid #ef4444;border-radius:8px;padding:14px">
      <div style="color:#f87171;font-size:0.95rem;font-weight:700;margin-bottom:6px">Machina</div>
      <div style="color:#fca5a5;font-size:0.78rem;line-height:1.6">Q1 OVERDUE (DPA)<br/>6 open (3 critical)<br/>Data + SR RED</div>
    </div>
    <div style="background:#1c1a0a;border:1px solid #ca8a04;border-radius:8px;padding:14px">
      <div style="color:#fbbf24;font-size:0.95rem;font-weight:700;margin-bottom:6px">Wandelbots</div>
      <div style="color:#fde68a;font-size:0.78rem;line-height:1.6">Q1 complete<br/>1 open item<br/>Latency YELLOW</div>
    </div>
  </div>
</div>

</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Tech Review Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_tech_review_tracker", "port": 8629}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8629)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"partner_tech_review_tracker","port":8629}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, using HTTPServer on port 8629")
        HTTPServer(("0.0.0.0", 8629), Handler).serve_forever()
