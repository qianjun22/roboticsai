# Partner Onboarding Automator — port 8921
# Automates the 8-step partner onboarding pipeline: NDA→DPA→API_key→SDK→inference→eval→DAgger→go-live

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

STEPS = [
    {"id": 1, "name": "NDA",        "label": "NDA Signing",           "auto": True,  "v1_days": 3.0, "v2_days": 0.1},
    {"id": 2, "name": "DPA",        "label": "DPA Agreement",         "auto": True,  "v1_days": 2.0, "v2_days": 0.1},
    {"id": 3, "name": "API_key",    "label": "API Key Provisioning",  "auto": True,  "v1_days": 1.0, "v2_days": 0.1},
    {"id": 4, "name": "SDK",        "label": "SDK Setup",             "auto": True,  "v1_days": 1.0, "v2_days": 0.5},
    {"id": 5, "name": "inference",  "label": "First Inference Call",  "auto": True,  "v1_days": 2.0, "v2_days": 0.5},
    {"id": 6, "name": "eval",       "label": "Baseline Eval",         "auto": True,  "v1_days": 3.0, "v2_days": 1.0},
    {"id": 7, "name": "DAgger",     "label": "DAgger Fine-tune",      "auto": False, "v1_days": 4.0, "v2_days": 3.0},
    {"id": 8, "name": "go-live",    "label": "Go-Live Approval",      "auto": False, "v1_days": 2.0, "v2_days": 1.7},
]

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Partner Onboarding Automator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; }
  .metric { font-size: 2.2rem; font-weight: bold; color: #38bdf8; }
  .label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.25rem; }
  .highlight { color: #C74634; font-weight: bold; }
  .badge { display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: 0.4rem; }
  .badge-auto { background: #065f46; color: #6ee7b7; }
  .badge-manual { background: #4a1942; color: #f0abfc; }
  .step-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0; border-bottom: 1px solid #334155; }
  .step-num { background: #C74634; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: bold; flex-shrink: 0; }
  .step-num.auto-step { background: #0369a1; }
  .step-name { flex: 1; font-size: 0.9rem; }
  .step-days { font-size: 0.85rem; color: #94a3b8; }
  .arrow { color: #38bdf8; margin: 0 2px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .summary-row { display: flex; gap: 2rem; margin-top: 1rem; }
  .summary-item { flex: 1; }
</style>
</head>
<body>
<h1>Partner Onboarding Automator</h1>
<p style="color:#94a3b8">8-step automated pipeline: <span class="highlight">NDA → DPA → API_key → SDK → inference → eval</span> (fully automated) → DAgger → go-live</p>

<div class="grid">
  <div class="card">
    <h2>Time to Go-Live</h2>
    <div class="metric">7 days</div>
    <div class="label">v2 (automated) — was 18 days in v1</div>
    <br>
    <div class="summary-row">
      <div class="summary-item">
        <div style="font-size:1.4rem;color:#C74634;font-weight:bold">18</div>
        <div class="label">v1 days (manual)</div>
      </div>
      <div class="summary-item">
        <div style="font-size:1.4rem;color:#38bdf8;font-weight:bold">7</div>
        <div class="label">v2 days (automated)</div>
      </div>
      <div class="summary-item">
        <div style="font-size:1.4rem;color:#6ee7b7;font-weight:bold">−61%</div>
        <div class="label">Time reduction</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Automation Coverage</h2>
    <div class="metric">6 / 8</div>
    <div class="label">Steps fully automated (steps 1–6)</div>
    <br>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:0.5rem">Steps 7–8 (DAgger fine-tune + go-live approval) require human review. Target: v3 will automate step 7 via continuous DAgger.</p>
  </div>
</div>

<h2>Onboarding Flow</h2>
<div class="card">
  <div>
    <div class="step-row">
      <div class="step-num auto-step">1</div>
      <div class="step-name">NDA Signing <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 3d &rarr; v2: 2h</div>
    </div>
    <div class="step-row">
      <div class="step-num auto-step">2</div>
      <div class="step-name">DPA Agreement <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 2d &rarr; v2: 2h</div>
    </div>
    <div class="step-row">
      <div class="step-num auto-step">3</div>
      <div class="step-name">API Key Provisioning <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 1d &rarr; v2: 2h</div>
    </div>
    <div class="step-row">
      <div class="step-num auto-step">4</div>
      <div class="step-name">SDK Setup <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 1d &rarr; v2: 0.5d</div>
    </div>
    <div class="step-row">
      <div class="step-num auto-step">5</div>
      <div class="step-name">First Inference Call <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 2d &rarr; v2: 0.5d</div>
    </div>
    <div class="step-row">
      <div class="step-num auto-step">6</div>
      <div class="step-name">Baseline Eval <span class="badge badge-auto">AUTO</span></div>
      <div class="step-days">v1: 3d &rarr; v2: 1d</div>
    </div>
    <div class="step-row">
      <div class="step-num">7</div>
      <div class="step-name">DAgger Fine-tune <span class="badge badge-manual">MANUAL</span></div>
      <div class="step-days">v1: 4d &rarr; v2: 3d</div>
    </div>
    <div class="step-row" style="border-bottom:none">
      <div class="step-num">8</div>
      <div class="step-name">Go-Live Approval <span class="badge badge-manual">MANUAL</span></div>
      <div class="step-days">v1: 2d &rarr; v2: 1.7d</div>
    </div>
  </div>
</div>

<h2>Time-to-Milestone Chart</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 680 200" xmlns="http://www.w3.org/2000/svg">
    <!-- Grouped bar chart: v1 (gray) and v2 (blue) per step -->
    <!-- y-axis: 0 to 4 days, height=160px, 40px/day -->
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="170" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="170" x2="670" y2="170" stroke="#334155" stroke-width="1.5"/>
    <!-- y ticks -->
    <text x="55" y="173" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
    <text x="55" y="133" fill="#94a3b8" font-size="10" text-anchor="end">1d</text>
    <text x="55" y="93" fill="#94a3b8" font-size="10" text-anchor="end">2d</text>
    <text x="55" y="53" fill="#94a3b8" font-size="10" text-anchor="end">3d</text>
    <text x="55" y="13" fill="#94a3b8" font-size="10" text-anchor="end">4d</text>
    <!-- grid lines -->
    <line x1="60" y1="130" x2="670" y2="130" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="90" x2="670" y2="90" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="50" x2="670" y2="50" stroke="#1e293b" stroke-width="1"/>
    <!-- steps: 8 steps, each 76px wide, gap=4 -->
    <!-- step 1: x=65; v1=3d h=120,y=50; v2=0.1d h=4,y=166 -->
    <rect x="65" y="50" width="30" height="120" fill="#475569" rx="3"/>
    <rect x="97" y="166" width="30" height="4" fill="#0369a1" rx="3"/>
    <text x="82" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">NDA</text>
    <!-- step 2: x=145; v1=2d h=80,y=90; v2=0.1d h=4,y=166 -->
    <rect x="145" y="90" width="30" height="80" fill="#475569" rx="3"/>
    <rect x="177" y="166" width="30" height="4" fill="#0369a1" rx="3"/>
    <text x="162" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">DPA</text>
    <!-- step 3: x=225; v1=1d h=40,y=130; v2=0.1d h=4,y=166 -->
    <rect x="225" y="130" width="30" height="40" fill="#475569" rx="3"/>
    <rect x="257" y="166" width="30" height="4" fill="#0369a1" rx="3"/>
    <text x="242" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">API key</text>
    <!-- step 4: x=305; v1=1d h=40,y=130; v2=0.5d h=20,y=150 -->
    <rect x="305" y="130" width="30" height="40" fill="#475569" rx="3"/>
    <rect x="337" y="150" width="30" height="20" fill="#0369a1" rx="3"/>
    <text x="322" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">SDK</text>
    <!-- step 5: x=385; v1=2d h=80,y=90; v2=0.5d h=20,y=150 -->
    <rect x="385" y="90" width="30" height="80" fill="#475569" rx="3"/>
    <rect x="417" y="150" width="30" height="20" fill="#0369a1" rx="3"/>
    <text x="402" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Infer</text>
    <!-- step 6: x=465; v1=3d h=120,y=50; v2=1d h=40,y=130 -->
    <rect x="465" y="50" width="30" height="120" fill="#475569" rx="3"/>
    <rect x="497" y="130" width="30" height="40" fill="#0369a1" rx="3"/>
    <text x="482" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Eval</text>
    <!-- step 7: x=545; v1=4d h=160,y=10; v2=3d h=120,y=50 -->
    <rect x="545" y="10" width="30" height="160" fill="#C74634" rx="3"/>
    <rect x="577" y="50" width="30" height="120" fill="#9b4dca" rx="3"/>
    <text x="562" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">DAgger</text>
    <!-- step 8: x=620; v1=2d h=80,y=90; v2=1.7d h=68,y=102 -->
    <rect x="620" y="90" width="30" height="80" fill="#C74634" rx="3"/>
    <rect x="652" y="102" width="18" height="68" fill="#9b4dca" rx="3"/>
    <text x="637" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Go-live</text>
    <!-- legend -->
    <rect x="65" y="195" width="12" height="8" fill="#475569" rx="2"/>
    <text x="80" y="202" fill="#94a3b8" font-size="10">v1 (manual)</text>
    <rect x="160" y="195" width="12" height="8" fill="#0369a1" rx="2"/>
    <text x="175" y="202" fill="#94a3b8" font-size="10">v2 auto (steps 1-6)</text>
    <rect x="290" y="195" width="12" height="8" fill="#9b4dca" rx="2"/>
    <text x="305" y="202" fill="#94a3b8" font-size="10">v2 manual (steps 7-8)</text>
  </svg>
</div>

<p style="margin-top:2rem;color:#475569;font-size:0.8rem">OCI Robot Cloud | Partner Onboarding Automator | Port 8921</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Onboarding Automator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_onboarding_automator", "port": 8921}

    @app.get("/api/steps")
    async def get_steps():
        """Return onboarding steps with timing data."""
        return {
            "steps": STEPS,
            "summary": {
                "total_steps": len(STEPS),
                "automated_steps": sum(1 for s in STEPS if s["auto"]),
                "v1_total_days": sum(s["v1_days"] for s in STEPS),
                "v2_total_days": sum(s["v2_days"] for s in STEPS),
                "reduction_pct": round(
                    100 * (1 - sum(s["v2_days"] for s in STEPS) / sum(s["v1_days"] for s in STEPS)), 1
                ),
            },
        }

    @app.post("/api/onboard")
    async def trigger_onboarding(partner_id: str = "demo"):
        """Simulate triggering the automated onboarding pipeline."""
        import time
        return {
            "partner_id": partner_id,
            "pipeline_id": f"onboard-{partner_id}-{int(time.time())}",
            "status": "initiated",
            "automated_steps": [s["name"] for s in STEPS if s["auto"]],
            "manual_steps": [s["name"] for s in STEPS if not s["auto"]],
            "estimated_days": sum(s["v2_days"] for s in STEPS),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8921)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, falling back to HTTPServer on port 8921")
        HTTPServer(("0.0.0.0", 8921), Handler).serve_forever()
