"""IK-Aware Training Service — OCI Robot Cloud (port 8596)"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler


def build_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IK-Aware Training Dashboard — OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 24px;
  }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 28px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
  }
  .card.full { grid-column: 1 / -1; }
  .card h2 { color: #C74634; font-size: 1rem; margin-bottom: 16px; }
  .metrics-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-top: 24px; }
  .metric {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }
  .metric .val { color: #38bdf8; font-size: 1.5rem; font-weight: 700; }
  .metric .lbl { color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .footer { color: #475569; font-size: 0.75rem; margin-top: 24px; text-align: center; }
</style>
</head>
<body>

<h1>IK-Aware Training Dashboard</h1>
<p class="subtitle">Inverse Kinematics Feasibility Filtering &amp; Training Impact — OCI Robot Cloud</p>

<div class="grid">

  <!-- Chart 1: IK Feasibility Rate by Phase -->
  <div class="card">
    <h2>IK Feasibility Rate per Trajectory Phase</h2>
    <svg viewBox="0 0 420 220" width="100%">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="175" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="175" x2="410" y2="175" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels -->
      <text x="52" y="178" fill="#94a3b8" font-size="10" text-anchor="end">88%</text>
      <text x="52" y="143" fill="#94a3b8" font-size="10" text-anchor="end">91%</text>
      <text x="52" y="108" fill="#94a3b8" font-size="10" text-anchor="end">94%</text>
      <text x="52" y="73" fill="#94a3b8" font-size="10" text-anchor="end">97%</text>
      <text x="52" y="38" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
      <!-- gridlines -->
      <line x1="60" y1="143" x2="410" y2="143" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="108" x2="410" y2="108" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="73" x2="410" y2="73" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="38" x2="410" y2="38" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>

      <!-- phase: approach 98% → bar height = (98-88)/(100-88)*165 = 137.5 -->
      <!-- scale: 88% → y=175, 100% → y=10; per % = (175-10)/12 = 13.75px -->
      <!-- approach 98%: height=(98-88)*13.75=137.5, y=175-137.5=37.5 -->
      <rect x="80" y="37" width="52" height="138" fill="#38bdf8" rx="3"/>
      <text x="106" y="31" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">98%</text>
      <text x="106" y="192" fill="#94a3b8" font-size="10" text-anchor="middle">Approach</text>

      <!-- grasp 94%: height=(94-88)*13.75=82.5, y=175-82.5=92.5 -->
      <rect x="158" y="93" width="52" height="82" fill="#C74634" rx="3"/>
      <text x="184" y="87" fill="#C74634" font-size="11" text-anchor="middle" font-weight="600">94%</text>
      <text x="184" y="192" fill="#94a3b8" font-size="10" text-anchor="middle">Grasp</text>

      <!-- lift 99%: height=(99-88)*13.75=151.25, y=175-151.25=23.75 -->
      <rect x="236" y="24" width="52" height="151" fill="#22d3ee" rx="3"/>
      <text x="262" y="18" fill="#22d3ee" font-size="11" text-anchor="middle" font-weight="600">99%</text>
      <text x="262" y="192" fill="#94a3b8" font-size="10" text-anchor="middle">Lift</text>

      <!-- place 97%: height=(97-88)*13.75=123.75, y=175-123.75=51.25 -->
      <rect x="314" y="51" width="52" height="124" fill="#0ea5e9" rx="3"/>
      <text x="340" y="45" fill="#0ea5e9" font-size="11" text-anchor="middle" font-weight="600">97%</text>
      <text x="340" y="192" fill="#94a3b8" font-size="10" text-anchor="middle">Place</text>

      <!-- total line at 94% -->
      <line x1="60" y1="93" x2="410" y2="93" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3"/>
      <text x="412" y="97" fill="#f59e0b" font-size="10">Total 94%</text>
    </svg>
  </div>

  <!-- Chart 2: Joint Config Distribution Before/After IK Filtering -->
  <div class="card">
    <h2>Joint Configuration Distribution (IK Filtering)</h2>
    <svg viewBox="0 0 420 220" width="100%">
      <!-- axes -->
      <line x1="50" y1="10" x2="50" y2="175" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="175" x2="410" y2="175" stroke="#334155" stroke-width="1"/>
      <!-- x-axis: joint angle bins -->
      <text x="230" y="210" fill="#94a3b8" font-size="10" text-anchor="middle">Joint Angle Configuration (bins)</text>

      <!-- before IK filtering histogram (raw) - 14 bins, approximately Gaussian with tails -->
      <!-- heights (scaled to max 140px): 12,28,52,80,110,138,140,132,108,78,50,26,10,4 -->
      <g opacity="0.55">
        <rect x="55"  y="163" width="23" height="12"  fill="#94a3b8" rx="1"/>
        <rect x="80"  y="147" width="23" height="28"  fill="#94a3b8" rx="1"/>
        <rect x="105" y="123" width="23" height="52"  fill="#94a3b8" rx="1"/>
        <rect x="130" y="95"  width="23" height="80"  fill="#94a3b8" rx="1"/>
        <rect x="155" y="65"  width="23" height="110" fill="#94a3b8" rx="1"/>
        <rect x="180" y="35"  width="23" height="140" fill="#94a3b8" rx="1"/>
        <rect x="205" y="33"  width="23" height="142" fill="#94a3b8" rx="1"/>
        <rect x="230" y="43"  width="23" height="132" fill="#94a3b8" rx="1"/>
        <rect x="255" y="67"  width="23" height="108" fill="#94a3b8" rx="1"/>
        <rect x="280" y="97"  width="23" height="78"  fill="#94a3b8" rx="1"/>
        <rect x="305" y="125" width="23" height="50"  fill="#94a3b8" rx="1"/>
        <rect x="330" y="149" width="23" height="26"  fill="#94a3b8" rx="1"/>
        <rect x="355" y="163" width="23" height="12"  fill="#94a3b8" rx="1"/>
        <rect x="380" y="169" width="23" height="6"   fill="#94a3b8" rx="1"/>
      </g>

      <!-- after IK filtering histogram - singular configs removed (tails clipped, tighter) -->
      <rect x="55"  y="175" width="23" height="0"   fill="#38bdf8" rx="1"/>
      <rect x="80"  y="172" width="23" height="3"   fill="#38bdf8" rx="1"/>
      <rect x="105" y="151" width="23" height="24"  fill="#38bdf8" rx="1"/>
      <rect x="130" y="101" width="23" height="74"  fill="#38bdf8" rx="1"/>
      <rect x="155" y="67"  width="23" height="108" fill="#38bdf8" rx="1"/>
      <rect x="180" y="35"  width="23" height="140" fill="#38bdf8" rx="1"/>
      <rect x="205" y="33"  width="23" height="142" fill="#38bdf8" rx="1"/>
      <rect x="230" y="43"  width="23" height="132" fill="#38bdf8" rx="1"/>
      <rect x="255" y="70"  width="23" height="105" fill="#38bdf8" rx="1"/>
      <rect x="280" y="102" width="23" height="73"  fill="#38bdf8" rx="1"/>
      <rect x="305" y="148" width="23" height="27"  fill="#38bdf8" rx="1"/>
      <rect x="330" y="172" width="23" height="3"   fill="#38bdf8" rx="1"/>
      <rect x="355" y="175" width="23" height="0"   fill="#38bdf8" rx="1"/>
      <rect x="380" y="175" width="23" height="0"   fill="#38bdf8" rx="1"/>

      <!-- legend -->
      <rect x="60" y="195" width="12" height="10" fill="#94a3b8" opacity="0.55" rx="1"/>
      <text x="76" y="204" fill="#94a3b8" font-size="9">Raw (all configs)</text>
      <rect x="180" y="195" width="12" height="10" fill="#38bdf8" rx="1"/>
      <text x="196" y="204" fill="#38bdf8" font-size="9">IK-Filtered (singular removed)</text>
    </svg>
  </div>

  <!-- Chart 3: SR Comparison IK-Filtered vs Raw -->
  <div class="card full">
    <h2>Success Rate: IK-Filtered Training vs Raw Training</h2>
    <svg viewBox="0 0 760 200" width="100%">
      <!-- axes -->
      <line x1="80" y1="10" x2="80" y2="155" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="155" x2="740" y2="155" stroke="#334155" stroke-width="1"/>
      <!-- y-axis: 0% to 70% -->
      <text x="72" y="158" fill="#94a3b8" font-size="10" text-anchor="end">0%</text>
      <text x="72" y="124" fill="#94a3b8" font-size="10" text-anchor="end">20%</text>
      <text x="72" y="90" fill="#94a3b8" font-size="10" text-anchor="end">40%</text>
      <text x="72" y="56" fill="#94a3b8" font-size="10" text-anchor="end">60%</text>
      <line x1="80" y1="124" x2="740" y2="124" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="80" y1="90"  x2="740" y2="90"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="80" y1="56"  x2="740" y2="56"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>

      <!-- scale: 0%→155, 70%→10; per%=(155-10)/70=2.071px -->

      <!-- BC: raw 5%, filtered 10% (delta +5pp) -->
      <!-- raw bar height=5*2.071=10.4, y=155-10=145 -->
      <!-- filt bar height=10*2.071=20.7, y=155-21=134 -->
      <rect x="100" y="144" width="55" height="11" fill="#475569" rx="2"/>
      <rect x="160" y="134" width="55" height="21" fill="#38bdf8" rx="2"/>
      <rect x="170" y="122" width="35" height="12" fill="#22c55e" rx="2" opacity="0.8"/>
      <text x="187" y="120" fill="#22c55e" font-size="10" text-anchor="middle">+5pp</text>
      <text x="127" y="171" fill="#94a3b8" font-size="10" text-anchor="middle">BC</text>
      <text x="100" y="141" fill="#64748b" font-size="9">5%</text>
      <text x="160" y="131" fill="#38bdf8" font-size="9">10%</text>

      <!-- DAgger_r9: raw 18%, filtered 23% -->
      <rect x="250" y="118" width="55" height="37" fill="#475569" rx="2"/>
      <rect x="310" y="107" width="55" height="48" fill="#38bdf8" rx="2"/>
      <rect x="320" y="95"  width="35" height="12" fill="#22c55e" rx="2" opacity="0.8"/>
      <text x="337" y="93" fill="#22c55e" font-size="10" text-anchor="middle">+5pp</text>
      <text x="277" y="171" fill="#94a3b8" font-size="10" text-anchor="middle">DAgger r9</text>
      <text x="250" y="115" fill="#64748b" font-size="9">18%</text>
      <text x="310" y="104" fill="#38bdf8" font-size="9">23%</text>

      <!-- DAgger_r10: raw 34%, filtered 39% -->
      <rect x="400" y="84"  width="55" height="71" fill="#475569" rx="2"/>
      <rect x="460" y="74"  width="55" height="81" fill="#38bdf8" rx="2"/>
      <rect x="470" y="62"  width="35" height="12" fill="#22c55e" rx="2" opacity="0.8"/>
      <text x="487" y="60" fill="#22c55e" font-size="10" text-anchor="middle">+5pp</text>
      <text x="427" y="171" fill="#94a3b8" font-size="10" text-anchor="middle">DAgger r10</text>
      <text x="400" y="81" fill="#64748b" font-size="9">34%</text>
      <text x="460" y="71" fill="#38bdf8" font-size="9">39%</text>

      <!-- GR00T_v2: raw 51%, filtered 56% -->
      <rect x="560" y="49"  width="55" height="106" fill="#475569" rx="2"/>
      <rect x="620" y="39"  width="55" height="116" fill="#38bdf8" rx="2"/>
      <rect x="630" y="27"  width="35" height="12" fill="#22c55e" rx="2" opacity="0.8"/>
      <text x="647" y="25" fill="#22c55e" font-size="10" text-anchor="middle">+5pp</text>
      <text x="587" y="171" fill="#94a3b8" font-size="10" text-anchor="middle">GR00T v2</text>
      <text x="560" y="46" fill="#64748b" font-size="9">51%</text>
      <text x="620" y="36" fill="#38bdf8" font-size="9">56%</text>

      <!-- legend -->
      <rect x="90" y="183" width="14" height="10" fill="#475569" rx="1"/>
      <text x="108" y="192" fill="#94a3b8" font-size="9">Raw Training SR</text>
      <rect x="220" y="183" width="14" height="10" fill="#38bdf8" rx="1"/>
      <text x="238" y="192" fill="#38bdf8" font-size="9">IK-Filtered SR</text>
      <rect x="340" y="183" width="14" height="10" fill="#22c55e" rx="1" opacity="0.8"/>
      <text x="358" y="192" fill="#22c55e" font-size="9">Delta (+5pp consistent)</text>
    </svg>
  </div>

</div>

<!-- Metrics -->
<div class="metrics-grid">
  <div class="metric">
    <div class="val">6%</div>
    <div class="lbl">Steps near singularity removed</div>
  </div>
  <div class="metric">
    <div class="val">3.2% → 0.4%</div>
    <div class="lbl">IK failure at inference</div>
  </div>
  <div class="metric">
    <div class="val">Cartesian + Joint</div>
    <div class="lbl">Hybrid IK filtering mode</div>
  </div>
  <div class="metric">
    <div class="val">+5pp</div>
    <div class="lbl">Consistent SR gain across all runs</div>
  </div>
</div>

<p class="footer">OCI Robot Cloud — IK-Aware Training Service | Port 8596 | Cycle 134B</p>
</body>
</html>
"""


if USE_FASTAPI:
    app = FastAPI(
        title="IK-Aware Training Dashboard",
        description="Inverse Kinematics feasibility filtering and training impact metrics",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "ik_aware_training",
            "port": 8596,
            "version": "1.0.0",
            "metrics": {
                "singular_steps_removed_pct": 6.0,
                "ik_failure_before": 3.2,
                "ik_failure_after": 0.4,
                "avg_sr_delta_pp": 5.0,
                "total_feasibility_rate": 94.0,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8596)

else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"ik_aware_training","port":8596}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available — using stdlib HTTPServer on port 8596")
        server = HTTPServer(("0.0.0.0", 8596), _Handler)
        server.serve_forever()
