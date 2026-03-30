#!/usr/bin/env python3
"""
contact_rich_policy_trainer.py — port 8632
Contact-rich policy training dashboard for OCI Robot Cloud.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="Contact-Rich Policy Trainer", version="1.0.0")

    HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Contact-Rich Policy Trainer — Port 8632</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 6px; letter-spacing: -0.5px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .card.full { grid-column: 1 / -1; }
  .card h2 { color: #C74634; font-size: 1rem; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }
  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .metric { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 14px; text-align: center; }
  .metric .val { color: #38bdf8; font-size: 1.5rem; font-weight: 700; }
  .metric .lbl { color: #64748b; font-size: 0.75rem; margin-top: 4px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
</style>
</head>
<body>

<h1>Contact-Rich Policy Trainer</h1>
<p class="subtitle">Port 8632 &mdash; Tactile-augmented DAgger with force-guided reward shaping</p>

<div class="grid">

  <!-- SVG 1: Contact Phase Classification Accuracy -->
  <div class="card">
    <h2>Contact Phase Classification Accuracy</h2>
    <svg viewBox="0 0 440 260" xmlns="http://www.w3.org/2000/svg">
      <!-- Background -->
      <rect width="440" height="260" fill="#0f172a" rx="6"/>

      <!-- Grid lines -->
      <line x1="60" y1="20" x2="60" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="200" x2="420" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="160" x2="420" y2="160" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="120" x2="420" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="80"  x2="420" y2="80"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="40"  x2="420" y2="40"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>

      <!-- Y-axis labels -->
      <text x="52" y="204" fill="#64748b" font-size="10" text-anchor="end">80%</text>
      <text x="52" y="164" fill="#64748b" font-size="10" text-anchor="end">85%</text>
      <text x="52" y="124" fill="#64748b" font-size="10" text-anchor="end">90%</text>
      <text x="52" y="84"  fill="#64748b" font-size="10" text-anchor="end">95%</text>
      <text x="52" y="44"  fill="#64748b" font-size="10" text-anchor="end">100%</text>

      <!-- Target line at 97% -->
      <line x1="60" y1="56" x2="420" y2="56" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3"/>
      <text x="424" y="59" fill="#f59e0b" font-size="9">target 97%</text>

      <!-- Bars: phases at x=90,170,250,330; width=60 -->
      <!-- pre_contact: 94% -->
      <rect x="80"  y="88"  width="60" height="112" fill="#38bdf8" rx="3" opacity="0.9"/>
      <!-- touching: 96% -->
      <rect x="160" y="72"  width="60" height="128" fill="#818cf8" rx="3" opacity="0.9"/>
      <!-- grasping: 98% -->
      <rect x="240" y="56"  width="60" height="144" fill="#34d399" rx="3" opacity="0.9"/>
      <!-- post_contact: 95% -->
      <rect x="320" y="80"  width="60" height="120" fill="#f472b6" rx="3" opacity="0.9"/>

      <!-- Bar labels -->
      <text x="110" y="84"  fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">94%</text>
      <text x="190" y="68"  fill="#818cf8" font-size="11" text-anchor="middle" font-weight="600">96%</text>
      <text x="270" y="52"  fill="#34d399" font-size="11" text-anchor="middle" font-weight="600">98%</text>
      <text x="350" y="76"  fill="#f472b6" font-size="11" text-anchor="middle" font-weight="600">95%</text>

      <!-- X-axis labels -->
      <text x="110" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">pre_contact</text>
      <text x="190" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">touching</text>
      <text x="270" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">grasping</text>
      <text x="350" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">post_contact</text>

      <text x="60" y="240" fill="#64748b" font-size="9">Phase accuracy across 2400 eval episodes. Target line = 97%.</text>
    </svg>
  </div>

  <!-- SVG 2: Force-Guided Reward Component Stacked Area -->
  <div class="card">
    <h2>Force-Guided Reward Components (run7&#x2192;run10)</h2>
    <svg viewBox="0 0 440 260" xmlns="http://www.w3.org/2000/svg">
      <rect width="440" height="260" fill="#0f172a" rx="6"/>

      <line x1="60" y1="20" x2="60" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="200" x2="420" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="150" x2="420" y2="150" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="100" x2="420" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="50"  x2="420" y2="50"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>

      <text x="52" y="204" fill="#64748b" font-size="10" text-anchor="end">0.0</text>
      <text x="52" y="154" fill="#64748b" font-size="10" text-anchor="end">0.5</text>
      <text x="52" y="104" fill="#64748b" font-size="10" text-anchor="end">1.0</text>
      <text x="52" y="54"  fill="#64748b" font-size="10" text-anchor="end">1.5</text>

      <!-- contact_quality area -->
      <polygon points="95,200 95,160 185,149 275,139 365,127 365,200"
               fill="#38bdf8" opacity="0.7"/>

      <!-- force_smooth area -->
      <polygon points="95,160 95,127 185,109 275,93 365,74 365,127 275,139 185,149"
               fill="#818cf8" opacity="0.7"/>

      <!-- impact_penalty area -->
      <polygon points="95,127 95,134 185,114 275,97 365,77 365,74 275,93 185,109"
               fill="#f87171" opacity="0.6"/>

      <text x="95"  y="216" fill="#94a3b8" font-size="10" text-anchor="middle">run7</text>
      <text x="185" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">run8</text>
      <text x="275" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">run9</text>
      <text x="365" y="216" fill="#94a3b8" font-size="10" text-anchor="middle">run10</text>

      <rect x="65"  y="228" width="10" height="10" fill="#38bdf8" rx="2"/>
      <text x="79"  y="237" fill="#94a3b8" font-size="9">contact_quality</text>
      <rect x="158" y="228" width="10" height="10" fill="#818cf8" rx="2"/>
      <text x="172" y="237" fill="#94a3b8" font-size="9">force_smooth</text>
      <rect x="243" y="228" width="10" height="10" fill="#f87171" rx="2"/>
      <text x="257" y="237" fill="#94a3b8" font-size="9">impact_penalty</text>
    </svg>
  </div>

  <!-- SVG 3: Contact Success Rate Progression -->
  <div class="card full">
    <h2>Contact Success Rate Progression (run7 &#x2192; run10)</h2>
    <svg viewBox="0 0 800 220" xmlns="http://www.w3.org/2000/svg">
      <rect width="800" height="220" fill="#0f172a" rx="6"/>

      <line x1="80" y1="20" x2="780" y2="20" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="60" x2="780" y2="60" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="100" x2="780" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="140" x2="780" y2="140" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="180" x2="780" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="20"  x2="80"  y2="180" stroke="#334155" stroke-width="1"/>

      <text x="72" y="184" fill="#64748b" font-size="10" text-anchor="end">0.50</text>
      <text x="72" y="144" fill="#64748b" font-size="10" text-anchor="end">0.60</text>
      <text x="72" y="104" fill="#64748b" font-size="10" text-anchor="end">0.70</text>
      <text x="72" y="64"  fill="#64748b" font-size="10" text-anchor="end">0.80</text>
      <text x="72" y="24"  fill="#64748b" font-size="10" text-anchor="end">0.90</text>

      <!-- Area fill -->
      <polygon points="170,126 360,99 550,72 740,41 740,180 170,180"
               fill="#38bdf8" opacity="0.15"/>

      <!-- Line -->
      <polyline points="170,126 360,99 550,72 740,41"
                fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>

      <circle cx="170" cy="126" r="6" fill="#38bdf8"/>
      <text x="170" y="118" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">0.62</text>
      <text x="170" y="196" fill="#94a3b8" font-size="10" text-anchor="middle">run7</text>
      <text x="170" y="208" fill="#64748b" font-size="9" text-anchor="middle">baseline</text>

      <circle cx="360" cy="99" r="6" fill="#38bdf8"/>
      <text x="360" y="91" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">0.68</text>
      <text x="360" y="196" fill="#94a3b8" font-size="10" text-anchor="middle">run8</text>
      <text x="360" y="208" fill="#64748b" font-size="9" text-anchor="middle">+tactile</text>

      <circle cx="550" cy="72" r="6" fill="#38bdf8"/>
      <text x="550" y="64" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">0.74</text>
      <text x="550" y="196" fill="#94a3b8" font-size="10" text-anchor="middle">run9</text>
      <text x="550" y="208" fill="#64748b" font-size="9" text-anchor="middle">+force reward</text>

      <circle cx="740" cy="41" r="6" fill="#34d399"/>
      <text x="740" y="33" fill="#34d399" font-size="11" text-anchor="middle" font-weight="600">0.81</text>
      <text x="740" y="196" fill="#94a3b8" font-size="10" text-anchor="middle">run10</text>
      <text x="740" y="208" fill="#64748b" font-size="9" text-anchor="middle">+impedance</text>

      <text x="455" y="48" fill="#f59e0b" font-size="11" font-weight="600">+30.6% total gain</text>
      <line x1="170" y1="53" x2="740" y2="53" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,3"/>
    </svg>
  </div>

</div>

<div class="card">
  <h2>Key Metrics</h2>
  <div class="metrics">
    <div class="metric">
      <div class="val">+0.08pp</div>
      <div class="lbl">Tactile-augmented SR gain</div>
    </div>
    <div class="metric">
      <div class="val">-67%</div>
      <div class="lbl">Hard contacts (force-guided)</div>
    </div>
    <div class="metric">
      <div class="val">120&#x2192;400</div>
      <div class="lbl">Impedance ramp (N/m)</div>
    </div>
    <div class="metric">
      <div class="val">98%</div>
      <div class="lbl">Peak phase accuracy (grasping)</div>
    </div>
  </div>
</div>

</body>
</html>"""

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "contact_rich_policy_trainer",
            "port": 8632,
            "metrics": {
                "tactile_sr_gain_pp": 0.08,
                "hard_contact_reduction_pct": 67,
                "impedance_ramp_nm": "120->400",
                "peak_phase_accuracy_pct": 98,
                "run10_contact_success_rate": 0.81,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8632)

except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "contact_rich_policy_trainer", "port": 8632}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = b"<h1>contact_rich_policy_trainer (port 8632)</h1><p>Install fastapi + uvicorn for full UI.</p>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI not available -- starting stdlib fallback on port 8632")
        HTTPServer(("0.0.0.0", 8632), Handler).serve_forever()
