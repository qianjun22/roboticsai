"""
OCI Robot Cloud — Customer Journey Mapper Service
Port 8635 | cycle-144A
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
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Customer Journey Mapper | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.8rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.95rem;margin-bottom:32px}
  h2{color:#C74634;font-size:1.1rem;margin-bottom:16px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(540px,1fr));gap:28px;margin-bottom:32px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:32px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}
  .metric .val{color:#38bdf8;font-size:1.6rem;font-weight:700;margin-bottom:4px}
  .metric .lbl{color:#94a3b8;font-size:.82rem}
  svg{width:100%;height:auto;display:block}
</style>
</head>
<body>
<h1>Customer Journey Mapper</h1>
<p class="subtitle">Lifecycle conversion funnel · GTM channel effectiveness · Time-in-stage analysis · Port 8635</p>

<div class="metrics">
  <div class="metric"><div class="val">2.3×</div><div class="lbl">NVIDIA referral vs cold outreach conversion</div></div>
  <div class="metric"><div class="val">8 mo</div><div class="lbl">Average full prospect→enterprise cycle</div></div>
  <div class="metric"><div class="val">3</div><div class="lbl">New pilots targeted at AI World</div></div>
  <div class="metric"><div class="val">85%</div><div class="lbl">Pilot→growth conversion rate</div></div>
</div>

<div class="grid">
  <!-- Chart 1: Customer Lifecycle Sankey -->
  <div class="card">
    <h2>Customer Lifecycle Sankey Flow</h2>
    <svg viewBox="0 0 520 320" xmlns="http://www.w3.org/2000/svg">
      <rect width="520" height="320" fill="#1e293b"/>
      <!-- Flows -->
      <path d="M68,60 C99,60 99,118 130,118 L130,202 C99,202 99,260 68,260 Z" fill="#38bdf8" opacity="0.25"/>
      <path d="M68,202 C99,202 99,260 130,260 L130,280 C99,280 99,280 68,280 Z" fill="#475569" opacity="0.2"/>
      <path d="M158,118 C189,118 189,135 220,135 L220,185 C189,185 189,202 158,202 Z" fill="#38bdf8" opacity="0.3"/>
      <path d="M158,202 C189,202 189,218 220,218 L220,232 C189,232 189,218 158,218 Z" fill="#475569" opacity="0.2"/>
      <path d="M248,135 C279,135 279,139 310,139 L310,181 C279,181 279,185 248,185 Z" fill="#38bdf8" opacity="0.35"/>
      <path d="M248,185 C279,185 279,189 310,189 L310,197 C279,197 279,193 248,193 Z" fill="#475569" opacity="0.2"/>
      <path d="M338,139 C369,139 369,144 400,144 L400,176 C369,176 369,181 338,181 Z" fill="#C74634" opacity="0.5"/>
      <path d="M338,181 C369,181 369,185 400,185 L400,193 C369,193 369,189 338,189 Z" fill="#475569" opacity="0.2"/>
      <!-- Stage bars -->
      <rect x="40" y="60" width="28" height="200" fill="#38bdf8" rx="4" opacity="0.9"/>
      <rect x="130" y="118" width="28" height="84" fill="#0ea5e9" rx="4" opacity="0.9"/>
      <rect x="220" y="135" width="28" height="50" fill="#0284c7" rx="4" opacity="0.9"/>
      <rect x="310" y="139" width="28" height="42" fill="#C74634" rx="4" opacity="0.9"/>
      <rect x="400" y="144" width="28" height="32" fill="#991b1b" rx="4" opacity="0.9"/>
      <!-- Labels -->
      <text x="54" y="52" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Prospect</text>
      <text x="54" y="272" text-anchor="middle" fill="#94a3b8" font-size="9">100</text>
      <text x="144" y="110" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Trial</text>
      <text x="144" y="214" text-anchor="middle" fill="#94a3b8" font-size="9">42</text>
      <text x="234" y="127" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Pilot</text>
      <text x="234" y="196" text-anchor="middle" fill="#94a3b8" font-size="9">25</text>
      <text x="324" y="131" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Growth</text>
      <text x="324" y="210" text-anchor="middle" fill="#94a3b8" font-size="9">21</text>
      <text x="414" y="136" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="bold">Enterprise</text>
      <text x="414" y="186" text-anchor="middle" fill="#94a3b8" font-size="9">16</text>
      <!-- Conversion rates -->
      <text x="99" y="155" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="bold">42%</text>
      <text x="189" y="158" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="bold">60%</text>
      <text x="279" y="160" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="bold">85%</text>
      <text x="369" y="158" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="bold">76%</text>
      <text x="260" y="308" text-anchor="middle" fill="#64748b" font-size="10">Width = relative volume · Conversion rates labeled on flow bands</text>
    </svg>
  </div>

  <!-- Chart 2: Touchpoint Effectiveness Bar -->
  <div class="card">
    <h2>GTM Channel Effectiveness</h2>
    <svg viewBox="0 0 500 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="500" height="300" fill="#1e293b"/>
      <line x1="160" y1="20" x2="160" y2="240" stroke="#334155" stroke-width="1"/>
      <line x1="160" y1="240" x2="470" y2="240" stroke="#334155" stroke-width="1"/>
      <g stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3">
        <line x1="213" y1="20" x2="213" y2="240"/>
        <line x1="265" y1="20" x2="265" y2="240"/>
        <line x1="318" y1="20" x2="318" y2="240"/>
        <line x1="370" y1="20" x2="370" y2="240"/>
        <line x1="422" y1="20" x2="422" y2="240"/>
      </g>
      <text x="160" y="256" text-anchor="middle" fill="#64748b" font-size="10">0%</text>
      <text x="213" y="256" text-anchor="middle" fill="#64748b" font-size="10">10%</text>
      <text x="265" y="256" text-anchor="middle" fill="#64748b" font-size="10">20%</text>
      <text x="318" y="256" text-anchor="middle" fill="#64748b" font-size="10">30%</text>
      <text x="370" y="256" text-anchor="middle" fill="#64748b" font-size="10">40%</text>
      <text x="422" y="256" text-anchor="middle" fill="#64748b" font-size="10">50%</text>
      <text x="315" y="276" text-anchor="middle" fill="#94a3b8" font-size="11">Share of Closed Deals</text>
      <!-- NVIDIA referral (Oracle red) -->
      <rect x="160" y="38" width="220" height="34" fill="#C74634" rx="4" opacity="0.9"/>
      <text x="150" y="60" text-anchor="end" fill="#e2e8f0" font-size="10">NVIDIA referral</text>
      <text x="386" y="60" fill="#fbbf24" font-size="11" font-weight="bold">42%</text>
      <!-- warm_intro -->
      <rect x="160" y="86" width="147" height="34" fill="#38bdf8" rx="4" opacity="0.85"/>
      <text x="150" y="108" text-anchor="end" fill="#e2e8f0" font-size="10">warm intro</text>
      <text x="313" y="108" fill="#e2e8f0" font-size="11">28%</text>
      <!-- DM_outreach -->
      <rect x="160" y="134" width="95" height="34" fill="#8b5cf6" rx="4" opacity="0.85"/>
      <text x="150" y="156" text-anchor="end" fill="#e2e8f0" font-size="10">DM outreach</text>
      <text x="261" y="156" fill="#e2e8f0" font-size="11">18%</text>
      <!-- content -->
      <rect x="160" y="182" width="63" height="34" fill="#64748b" rx="4" opacity="0.85"/>
      <text x="150" y="204" text-anchor="end" fill="#e2e8f0" font-size="10">content</text>
      <text x="229" y="204" fill="#e2e8f0" font-size="11">12%</text>
      <text x="315" y="16" text-anchor="middle" fill="#94a3b8" font-size="10">Oracle red = top channel · 2.3× lift over cold outreach</text>
    </svg>
  </div>

  <!-- Chart 3: Time-in-Stage Box Plot -->
  <div class="card" style="grid-column:1/-1">
    <h2>Time-in-Stage Distribution (Days)</h2>
    <svg viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="760" height="300" fill="#1e293b"/>
      <line x1="80" y1="20" x2="80" y2="240" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="240" x2="720" y2="240" stroke="#334155" stroke-width="1"/>
      <g stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3">
        <line x1="80" y1="200" x2="720" y2="200"/>
        <line x1="80" y1="160" x2="720" y2="160"/>
        <line x1="80" y1="120" x2="720" y2="120"/>
        <line x1="80" y1="80" x2="720" y2="80"/>
        <line x1="80" y1="40" x2="720" y2="40"/>
      </g>
      <text x="72" y="244" text-anchor="end" fill="#64748b" font-size="10">0d</text>
      <text x="72" y="204" text-anchor="end" fill="#64748b" font-size="10">40d</text>
      <text x="72" y="164" text-anchor="end" fill="#64748b" font-size="10">80d</text>
      <text x="72" y="124" text-anchor="end" fill="#64748b" font-size="10">120d</text>
      <text x="72" y="84" text-anchor="end" fill="#64748b" font-size="10">160d</text>
      <text x="72" y="44" text-anchor="end" fill="#64748b" font-size="10">200d</text>
      <text x="14" y="130" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,14,130)">Days in Stage</text>
      <!-- prospect→trial: med=21d -->
      <line x1="160" y1="233" x2="160" y2="226" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="152" y1="233" x2="168" y2="233" stroke="#94a3b8" stroke-width="1.5"/>
      <rect x="140" y="205" width="40" height="21" fill="#38bdf8" opacity="0.5" stroke="#38bdf8" stroke-width="1.5" rx="2"/>
      <line x1="140" y1="219" x2="180" y2="219" stroke="#fbbf24" stroke-width="2.5"/>
      <line x1="160" y1="205" x2="160" y2="185" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="152" y1="185" x2="168" y2="185" stroke="#94a3b8" stroke-width="1.5"/>
      <circle cx="160" cy="165" r="3" fill="none" stroke="#f87171" stroke-width="1.5"/>
      <text x="160" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">Prospect</text>
      <text x="160" y="269" text-anchor="middle" fill="#94a3b8" font-size="9">→Trial</text>
      <!-- trial→pilot: med=14d (fastest) -->
      <line x1="270" y1="235" x2="270" y2="230" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="262" y1="235" x2="278" y2="235" stroke="#94a3b8" stroke-width="1.5"/>
      <rect x="250" y="218" width="40" height="12" fill="#38bdf8" opacity="0.5" stroke="#38bdf8" stroke-width="1.5" rx="2"/>
      <line x1="250" y1="226" x2="290" y2="226" stroke="#fbbf24" stroke-width="2.5"/>
      <line x1="270" y1="218" x2="270" y2="205" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="262" y1="205" x2="278" y2="205" stroke="#94a3b8" stroke-width="1.5"/>
      <text x="270" y="258" text-anchor="middle" fill="#38bdf8" font-size="9">Trial→Pilot</text>
      <text x="270" y="269" text-anchor="middle" fill="#38bdf8" font-size="9">(fastest med 14d)</text>
      <!-- pilot→growth: med=45d -->
      <line x1="380" y1="225" x2="380" y2="210" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="372" y1="225" x2="388" y2="225" stroke="#94a3b8" stroke-width="1.5"/>
      <rect x="360" y="170" width="40" height="40" fill="#8b5cf6" opacity="0.5" stroke="#8b5cf6" stroke-width="1.5" rx="2"/>
      <line x1="360" y1="195" x2="400" y2="195" stroke="#fbbf24" stroke-width="2.5"/>
      <line x1="380" y1="170" x2="380" y2="145" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="372" y1="145" x2="388" y2="145" stroke="#94a3b8" stroke-width="1.5"/>
      <circle cx="380" cy="120" r="3" fill="none" stroke="#f87171" stroke-width="1.5"/>
      <text x="380" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">Pilot</text>
      <text x="380" y="269" text-anchor="middle" fill="#94a3b8" font-size="9">→Growth</text>
      <!-- growth→enterprise: med=60d -->
      <line x1="490" y1="215" x2="490" y2="198" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="482" y1="215" x2="498" y2="215" stroke="#94a3b8" stroke-width="1.5"/>
      <rect x="470" y="155" width="40" height="43" fill="#C74634" opacity="0.5" stroke="#C74634" stroke-width="1.5" rx="2"/>
      <line x1="470" y1="180" x2="510" y2="180" stroke="#fbbf24" stroke-width="2.5"/>
      <line x1="490" y1="155" x2="490" y2="130" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="482" y1="130" x2="498" y2="130" stroke="#94a3b8" stroke-width="1.5"/>
      <text x="490" y="258" text-anchor="middle" fill="#C74634" font-size="9">Growth→</text>
      <text x="490" y="269" text-anchor="middle" fill="#C74634" font-size="9">Enterprise</text>
      <!-- enterprise renewal: med=90d (slowest) -->
      <line x1="600" y1="195" x2="600" y2="175" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="592" y1="195" x2="608" y2="195" stroke="#94a3b8" stroke-width="1.5"/>
      <rect x="580" y="110" width="40" height="65" fill="#0d9488" opacity="0.5" stroke="#0d9488" stroke-width="1.5" rx="2"/>
      <line x1="580" y1="150" x2="620" y2="150" stroke="#fbbf24" stroke-width="2.5"/>
      <line x1="600" y1="110" x2="600" y2="65" stroke="#94a3b8" stroke-width="1.5"/>
      <line x1="592" y1="65" x2="608" y2="65" stroke="#94a3b8" stroke-width="1.5"/>
      <circle cx="600" cy="30" r="3" fill="none" stroke="#f87171" stroke-width="1.5"/>
      <text x="600" y="258" text-anchor="middle" fill="#94a3b8" font-size="9">Enterprise</text>
      <text x="600" y="269" text-anchor="middle" fill="#94a3b8" font-size="9">Renewal</text>
      <text x="600" y="280" text-anchor="middle" fill="#C74634" font-size="9">(slowest 90d)</text>
      <!-- Legend -->
      <rect x="260" y="288" width="12" height="12" fill="#38bdf8" opacity="0.5" stroke="#38bdf8" stroke-width="1" rx="2"/>
      <text x="276" y="299" fill="#94a3b8" font-size="10">IQR box</text>
      <line x1="340" y1="294" x2="360" y2="294" stroke="#fbbf24" stroke-width="2.5"/>
      <text x="365" y="299" fill="#94a3b8" font-size="10">Median</text>
      <circle cx="420" cy="294" r="3" fill="none" stroke="#f87171" stroke-width="1.5"/>
      <text x="427" y="299" fill="#94a3b8" font-size="10">Outlier</text>
    </svg>
  </div>
</div>

<footer style="color:#475569;font-size:.8rem;margin-top:16px">OCI Robot Cloud · Customer Journey Mapper · Port 8635</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Journey Mapper", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "customer_journey_mapper", "port": 8635}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8635)
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"customer_journey_mapper","port":8635}'
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
        print("FastAPI unavailable — starting stdlib HTTPServer on port 8635")
        HTTPServer(("0.0.0.0", 8635), Handler).serve_forever()
