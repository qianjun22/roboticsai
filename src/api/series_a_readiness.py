# Series A Readiness — port 8933
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Series A Readiness</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem; }
  .highlight { background: #0f172a; border-left: 3px solid #38bdf8; padding: 0.75rem 1rem; border-radius: 4px; margin-top: 1rem; font-size: 0.9rem; }
  .highlight span { color: #C74634; font-weight: 700; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Series A Readiness</h1>
<p class="subtitle">Port 8933 &nbsp;|&nbsp; $4M raise at $20M pre-money &nbsp;&bull;&nbsp; 6/10 criteria green &nbsp;&bull;&nbsp; NVIDIA partnership unlocks 3 criteria</p>

<div class="grid">
  <div class="card">
    <h2>Investor Readiness Scorecard</h2>
    <p class="subtitle">10 criteria — green = met, yellow = in-progress, red = gap. NVIDIA partnership (&#x2605;) unlocks 3 criteria.</p>
    <svg viewBox="0 0 420 360" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="420" height="360" fill="#0f172a" rx="8"/>

      <!-- Criteria rows -->
      <!-- y start = 20, row height = 32 -->
      <!-- col: status dot x=22, label x=40, bar start x=220, bar end x=380, score x=390 -->

      <!-- 1. Product-market fit — GREEN -->
      <circle cx="22" cy="36" r="8" fill="#22c55e"/>
      <text x="38" y="41" fill="#e2e8f0" font-size="11">1. Product-market fit (robotics cloud infra)</text>
      <rect x="220" y="28" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="28" width="133" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="41" fill="#22c55e" font-size="11" text-anchor="end">95%</text>

      <!-- 2. Revenue traction — GREEN -->
      <circle cx="22" cy="68" r="8" fill="#22c55e"/>
      <text x="38" y="73" fill="#e2e8f0" font-size="11">2. Revenue traction (&gt;$200K ARR)</text>
      <rect x="220" y="60" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="60" width="112" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="73" fill="#22c55e" font-size="11" text-anchor="end">80%</text>

      <!-- 3. Technical moat — GREEN -->
      <circle cx="22" cy="100" r="8" fill="#22c55e"/>
      <text x="38" y="105" fill="#e2e8f0" font-size="11">3. Technical moat (GR00T fine-tune pipeline)</text>
      <rect x="220" y="92" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="92" width="126" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="105" fill="#22c55e" font-size="11" text-anchor="end">90%</text>

      <!-- 4. Team completeness — GREEN -->
      <circle cx="22" cy="132" r="8" fill="#22c55e"/>
      <text x="38" y="137" fill="#e2e8f0" font-size="11">4. Team completeness (ML + Infra + BD)</text>
      <rect x="220" y="124" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="124" width="119" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="137" fill="#22c55e" font-size="11" text-anchor="end">85%</text>

      <!-- 5. Data flywheel — GREEN -->
      <circle cx="22" cy="164" r="8" fill="#22c55e"/>
      <text x="38" y="169" fill="#e2e8f0" font-size="11">5. Data flywheel (1M+ demos, CC-licensed)</text>
      <rect x="220" y="156" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="156" width="105" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="169" fill="#22c55e" font-size="11" text-anchor="end">75%</text>

      <!-- 6. Cloud infra unit economics — GREEN -->
      <circle cx="22" cy="196" r="8" fill="#22c55e"/>
      <text x="38" y="201" fill="#e2e8f0" font-size="11">6. Cloud infra unit economics ($0.004/10k)</text>
      <rect x="220" y="188" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="188" width="126" height="14" rx="4" fill="#22c55e" opacity="0.8"/>
      <text x="395" y="201" fill="#22c55e" font-size="11" text-anchor="end">90%</text>

      <!-- 7. Enterprise pilot customers &#x2605; — YELLOW (NVIDIA unlocks) -->
      <circle cx="22" cy="228" r="8" fill="#eab308"/>
      <text x="38" y="233" fill="#e2e8f0" font-size="11">7. Enterprise pilots &#x2605; (NVIDIA unlocks)</text>
      <rect x="220" y="220" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="220" width="84" height="14" rx="4" fill="#eab308" opacity="0.8"/>
      <text x="395" y="233" fill="#eab308" font-size="11" text-anchor="end">60%</text>

      <!-- 8. Regulatory / safety cert &#x2605; — YELLOW (NVIDIA unlocks) -->
      <circle cx="22" cy="260" r="8" fill="#eab308"/>
      <text x="38" y="265" fill="#e2e8f0" font-size="11">8. Safety certification &#x2605; (NVIDIA unlocks)</text>
      <rect x="220" y="252" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="252" width="63" height="14" rx="4" fill="#eab308" opacity="0.8"/>
      <text x="395" y="265" fill="#eab308" font-size="11" text-anchor="end">45%</text>

      <!-- 9. Distribution / channel &#x2605; — YELLOW (NVIDIA unlocks) -->
      <circle cx="22" cy="292" r="8" fill="#eab308"/>
      <text x="38" y="297" fill="#e2e8f0" font-size="11">9. Distribution / OEM channel &#x2605;</text>
      <rect x="220" y="284" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="284" width="70" height="14" rx="4" fill="#eab308" opacity="0.8"/>
      <text x="395" y="297" fill="#eab308" font-size="11" text-anchor="end">50%</text>

      <!-- 10. IP / patents — RED -->
      <circle cx="22" cy="324" r="8" fill="#ef4444"/>
      <text x="38" y="329" fill="#e2e8f0" font-size="11">10. IP / patent filings</text>
      <rect x="220" y="316" width="140" height="14" rx="4" fill="#1e293b"/>
      <rect x="220" y="316" width="42" height="14" rx="4" fill="#ef4444" opacity="0.7"/>
      <text x="395" y="329" fill="#ef4444" font-size="11" text-anchor="end">30%</text>

      <!-- legend -->
      <circle cx="22" cy="350" r="5" fill="#22c55e"/>
      <text x="30" y="354" fill="#94a3b8" font-size="9">Met (6)</text>
      <circle cx="80" cy="350" r="5" fill="#eab308"/>
      <text x="88" y="354" fill="#94a3b8" font-size="9">In-progress (3)</text>
      <circle cx="170" cy="350" r="5" fill="#ef4444"/>
      <text x="178" y="354" fill="#94a3b8" font-size="9">Gap (1)</text>
      <text x="240" y="354" fill="#fbbf24" font-size="9">&#x2605; = NVIDIA partnership unlocks</text>
    </svg>
    <div class="highlight">Raise target: <span>$4M</span> at <span>$20M pre-money</span> ($24M post) &nbsp;&bull;&nbsp; Current score: 6/10 green</div>
  </div>

  <div class="card">
    <h2>Fundraising Gantt</h2>
    <p class="subtitle">May prep &rarr; Aug term sheet &rarr; Sep close at AI World 2026</p>
    <svg viewBox="0 0 420 320" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="420" height="320" fill="#0f172a" rx="8"/>

      <!-- Month headers: May Jun Jul Aug Sep -->
      <!-- x: 90 (label), 130, 194, 258, 322, 386 (month cols) -->
      <!-- each month = 64px wide -->
      <text x="152" y="18" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">May</text>
      <text x="216" y="18" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Jun</text>
      <text x="280" y="18" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Jul</text>
      <text x="344" y="18" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Aug</text>
      <text x="402" y="18" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">Sep</text>

      <!-- vertical grid lines -->
      <line x1="120" y1="24" x2="120" y2="295" stroke="#1e293b" stroke-width="1"/>
      <line x1="184" y1="24" x2="184" y2="295" stroke="#1e293b" stroke-width="1"/>
      <line x1="248" y1="24" x2="248" y2="295" stroke="#1e293b" stroke-width="1"/>
      <line x1="312" y1="24" x2="312" y2="295" stroke="#1e293b" stroke-width="1"/>
      <line x1="376" y1="24" x2="376" y2="295" stroke="#1e293b" stroke-width="1"/>

      <!-- Row height = 28, start y=32 -->
      <!-- Row 1: Materials prep — May full -->
      <text x="5" y="50" fill="#94a3b8" font-size="9">Materials prep</text>
      <rect x="120" y="36" width="64" height="20" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="152" y="50" fill="#fff" font-size="9" text-anchor="middle">Deck + DD</text>

      <!-- Row 2: Warm intros — May-Jun -->
      <text x="5" y="78" fill="#94a3b8" font-size="9">Warm intros</text>
      <rect x="152" y="64" width="96" height="20" rx="4" fill="#7c3aed" opacity="0.8"/>
      <text x="200" y="78" fill="#fff" font-size="9" text-anchor="middle">Target 20 VCs</text>

      <!-- Row 3: NVIDIA partner announcement — Jun -->
      <text x="5" y="106" fill="#94a3b8" font-size="9">NVIDIA announce</text>
      <rect x="184" y="92" width="64" height="20" rx="4" fill="#fbbf24" opacity="0.9"/>
      <text x="216" y="106" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="700">&#x2605; MOU signed</text>

      <!-- Row 4: First meetings — Jun-Jul -->
      <text x="5" y="134" fill="#94a3b8" font-size="9">First meetings</text>
      <rect x="184" y="120" width="128" height="20" rx="4" fill="#38bdf8" opacity="0.75"/>
      <text x="248" y="134" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="600">12-15 pitches</text>

      <!-- Row 5: Due diligence — Jul-Aug -->
      <text x="5" y="162" fill="#94a3b8" font-size="9">Due diligence</text>
      <rect x="248" y="148" width="128" height="20" rx="4" fill="#22c55e" opacity="0.75"/>
      <text x="312" y="162" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="600">Tech + financial DD</text>

      <!-- Row 6: Term sheet — Aug -->
      <text x="5" y="190" fill="#94a3b8" font-size="9">Term sheet</text>
      <rect x="312" y="176" width="64" height="20" rx="4" fill="#C74634" opacity="0.9"/>
      <text x="344" y="190" fill="#fff" font-size="9" text-anchor="middle" font-weight="700">Target TS</text>

      <!-- Row 7: Legal / close — Aug-Sep -->
      <text x="5" y="218" fill="#94a3b8" font-size="9">Legal / close</text>
      <rect x="344" y="204" width="80" height="20" rx="4" fill="#7c3aed" opacity="0.85"/>
      <text x="384" y="218" fill="#fff" font-size="9" text-anchor="middle">SPA + wire</text>

      <!-- Row 8: AI World close milestone — Sep -->
      <text x="5" y="246" fill="#fbbf24" font-size="9" font-weight="700">AI World close</text>
      <rect x="376" y="232" width="38" height="20" rx="4" fill="#fbbf24" opacity="0.95"/>
      <text x="395" y="246" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="700">CLOSE</text>

      <!-- Row 9: Board composition — Sep -->
      <text x="5" y="274" fill="#94a3b8" font-size="9">Board setup</text>
      <rect x="376" y="260" width="38" height="20" rx="4" fill="#38bdf8" opacity="0.7"/>
      <text x="395" y="274" fill="#0f172a" font-size="9" text-anchor="middle">2+1+1</text>

      <!-- summary bar -->
      <rect x="120" y="292" width="294" height="4" rx="2" fill="#334155"/>
      <rect x="120" y="292" width="196" height="4" rx="2" fill="#22c55e" opacity="0.8"/>
      <text x="120" y="308" fill="#94a3b8" font-size="9">May</text>
      <text x="395" y="308" fill="#94a3b8" font-size="9" text-anchor="end">Sep close</text>
      <text x="257" y="308" fill="#e2e8f0" font-size="9" text-anchor="middle">5-month runway to close</text>
    </svg>
    <div class="highlight">NVIDIA partnership signed Jun &rarr; unlocks <span>criteria 7, 8, 9</span> &rarr; projected close at AI World Sep 2026 &nbsp;&bull;&nbsp; $20M pre-money valuation</div>
  </div>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Series A Readiness")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        criteria = [
            {"id": i + 1, "label": lbl, "status": st, "score": sc, "nvidia_unlock": nu}
            for i, (lbl, st, sc, nu) in enumerate([
                ("Product-market fit",          "green",  0.95, False),
                ("Revenue traction",             "green",  0.80, False),
                ("Technical moat",               "green",  0.90, False),
                ("Team completeness",            "green",  0.85, False),
                ("Data flywheel",                "green",  0.75, False),
                ("Cloud infra unit economics",   "green",  0.90, False),
                ("Enterprise pilot customers",   "yellow", 0.60, True),
                ("Safety certification",         "yellow", 0.45, True),
                ("Distribution / OEM channel",  "yellow", 0.50, True),
                ("IP / patent filings",          "red",    0.30, False),
            ])
        ]
        green_count = sum(1 for c in criteria if c["status"] == "green")
        overall_score = round(sum(c["score"] for c in criteria) / len(criteria), 2)
        timeline = [
            {"month": "May 2026",  "milestone": "Materials prep (deck + DD room)"},
            {"month": "Jun 2026",  "milestone": "NVIDIA MOU signed + warm intros"},
            {"month": "Jul 2026",  "milestone": "12-15 first meetings"},
            {"month": "Aug 2026",  "milestone": "Due diligence + term sheet"},
            {"month": "Sep 2026",  "milestone": "Close at AI World 2026"},
        ]
        return {
            "status": "ok",
            "service": "series_a_readiness",
            "port": 8933,
            "raise_amount_usd": 4_000_000,
            "pre_money_valuation_usd": 20_000_000,
            "post_money_valuation_usd": 24_000_000,
            "criteria_met": green_count,
            "criteria_total": len(criteria),
            "overall_readiness_score": overall_score,
            "nvidia_unlocks_criteria": 3,
            "fundraising_timeline": timeline,
            "criteria": criteria,
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8933)
    else:
        server = HTTPServer(("0.0.0.0", 8933), Handler)
        print("Series A Readiness running on http://0.0.0.0:8933 (fallback HTTPServer)")
        server.serve_forever()
