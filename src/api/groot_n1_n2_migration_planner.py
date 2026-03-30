# GR00T N1→N2 Migration Planner — port 8984
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
<title>GR00T N1→N2 Migration Planner</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 28px 0 12px; }
  h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 8px; }
  .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card .val { font-size: 1.6rem; font-weight: 700; color: #38bdf8; }
  .card .label { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .card .delta { font-size: 0.85rem; color: #4ade80; margin-top: 6px; }
  .card .delta.red { color: #f87171; }
  table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }
  th { background: #0f172a; color: #38bdf8; padding: 10px 14px; text-align: left; font-size: 0.85rem; }
  td { padding: 10px 14px; font-size: 0.88rem; border-top: 1px solid #334155; }
  tr:hover td { background: #263248; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-yellow { background: #713f12; color: #fbbf24; }
  .badge-blue { background: #0c4a6e; color: #38bdf8; }
  .badge-red { background: #7f1d1d; color: #f87171; }
</style>
</head>
<body>
<h1>GR00T N1→N2 Migration Planner</h1>
<p class="subtitle">OCI Robot Cloud · End-to-end migration roadmap from GR00T N1.6 to GR00T N2 · Port 8984</p>

<h2>Key Migration Metrics</h2>
<div class="grid">
  <div class="card">
    <div class="val">+15pp</div>
    <div class="label">Avg SR Improvement</div>
    <div class="delta">0.74 → 0.89–0.94</div>
  </div>
  <div class="card">
    <div class="val">7B</div>
    <div class="label">N2 Parameters</div>
    <div class="delta">vs 1.5B N1.6</div>
  </div>
  <div class="card">
    <div class="val">$10,500</div>
    <div class="label">One-Time Migration Cost</div>
    <div class="delta">Compute + re-fine-tune</div>
  </div>
  <div class="card">
    <div class="val">Mar 2027</div>
    <div class="label">N1.6 EOL</div>
    <div class="delta delta red">H2 2026 N2 release</div>
  </div>
</div>

<h2>N1.6 vs N2 Capability Delta</h2>
<div class="chart-wrap">
  <svg viewBox="0 0 820 340" width="100%">
    <!-- Axis -->
    <line x1="160" y1="20" x2="160" y2="290" stroke="#334155" stroke-width="1"/>
    <line x1="160" y1="290" x2="800" y2="290" stroke="#334155" stroke-width="1"/>
    <!-- Grid lines -->
    <line x1="160" y1="290" x2="800" y2="290" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="160" y1="236" x2="800" y2="236" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="160" y1="182" x2="800" y2="182" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="160" y1="128" x2="800" y2="128" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="160" y1="74" x2="800" y2="74" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <line x1="160" y1="20" x2="800" y2="20" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4"/>
    <!-- Y labels -->
    <text x="148" y="294" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <text x="148" y="240" fill="#64748b" font-size="10" text-anchor="end">20</text>
    <text x="148" y="186" fill="#64748b" font-size="10" text-anchor="end">40</text>
    <text x="148" y="132" fill="#64748b" font-size="10" text-anchor="end">60</text>
    <text x="148" y="78" fill="#64748b" font-size="10" text-anchor="end">80</text>
    <text x="148" y="24" fill="#64748b" font-size="10" text-anchor="end">100</text>
    <!-- Capability bars: N1.6 (gray) then N2 (blue) per capability -->
    <!-- Capability 1: Manipulation SR -->
    <text x="196" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Manip SR</text>
    <rect x="172" y="157" width="22" height="133" fill="#475569" rx="3"/>
    <rect x="196" y="101" width="22" height="189" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 2: Video Understanding -->
    <text x="260" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Video Underst.</text>
    <rect x="236" y="236" width="22" height="54" fill="#475569" rx="3"/>
    <rect x="260" y="128" width="22" height="162" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 3: Language Follow -->
    <text x="324" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Lang Follow</text>
    <rect x="300" y="182" width="22" height="108" fill="#475569" rx="3"/>
    <rect x="324" y="101" width="22" height="189" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 4: Multimodal Reward -->
    <text x="388" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Multimodal Rwd</text>
    <rect x="364" y="263" width="22" height="27" fill="#475569" rx="3"/>
    <rect x="388" y="128" width="22" height="162" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 5: Generalization -->
    <text x="452" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Generalization</text>
    <rect x="428" y="209" width="22" height="81" fill="#475569" rx="3"/>
    <rect x="452" y="101" width="22" height="189" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 6: Dexterity -->
    <text x="516" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Dexterity</text>
    <rect x="492" y="182" width="22" height="108" fill="#475569" rx="3"/>
    <rect x="516" y="128" width="22" height="162" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Capability 7: Long-horizon tasks -->
    <text x="580" y="308" fill="#94a3b8" font-size="9" text-anchor="middle">Long-horizon</text>
    <rect x="556" y="236" width="22" height="54" fill="#475569" rx="3"/>
    <rect x="580" y="101" width="22" height="189" fill="#38bdf8" rx="3" opacity="0.85"/>
    <!-- Legend -->
    <rect x="630" y="30" width="14" height="14" fill="#475569" rx="2"/>
    <text x="648" y="42" fill="#94a3b8" font-size="11">N1.6</text>
    <rect x="630" y="52" width="14" height="14" fill="#38bdf8" rx="2" opacity="0.85"/>
    <text x="648" y="64" fill="#e2e8f0" font-size="11">N2</text>
    <text x="480" y="18" fill="#64748b" font-size="10" text-anchor="middle">Score (0–100)</text>
  </svg>
</div>

<h2>Migration Timeline Gantt (H2 2026 – Mar 2027)</h2>
<div class="chart-wrap">
  <svg viewBox="0 0 820 300" width="100%">
    <!-- Month headers -->
    <text x="170" y="18" fill="#64748b" font-size="10" text-anchor="middle">Jul</text>
    <text x="260" y="18" fill="#64748b" font-size="10" text-anchor="middle">Aug</text>
    <text x="350" y="18" fill="#64748b" font-size="10" text-anchor="middle">Sep</text>
    <text x="440" y="18" fill="#64748b" font-size="10" text-anchor="middle">Oct</text>
    <text x="530" y="18" fill="#64748b" font-size="10" text-anchor="middle">Nov</text>
    <text x="620" y="18" fill="#64748b" font-size="10" text-anchor="middle">Dec</text>
    <text x="710" y="18" fill="#64748b" font-size="10" text-anchor="middle">Jan-Mar'27</text>
    <!-- Vertical grid -->
    <line x1="125" y1="24" x2="125" y2="285" stroke="#334155" stroke-width="1"/>
    <line x1="215" y1="24" x2="215" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <line x1="305" y1="24" x2="305" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <line x1="395" y1="24" x2="395" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <line x1="485" y1="24" x2="485" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <line x1="575" y1="24" x2="575" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <line x1="665" y1="24" x2="665" y2="285" stroke="#334155" stroke-width="0.5" stroke-dasharray="3"/>
    <!-- Step 1: N2 Beta Access -->
    <text x="120" y="46" fill="#94a3b8" font-size="10" text-anchor="end">1. N2 Beta Access</text>
    <rect x="125" y="32" width="90" height="18" fill="#C74634" rx="4"/>
    <text x="170" y="44" fill="white" font-size="9" text-anchor="middle">Beta program</text>
    <!-- Step 2: Architecture Review -->
    <text x="120" y="74" fill="#94a3b8" font-size="10" text-anchor="end">2. Arch Review</text>
    <rect x="125" y="60" width="180" height="18" fill="#0369a1" rx="4"/>
    <text x="215" y="72" fill="white" font-size="9" text-anchor="middle">Architecture & gap analysis</text>
    <!-- Step 3: Data Re-formatting -->
    <text x="120" y="102" fill="#94a3b8" font-size="10" text-anchor="end">3. Data Reformat</text>
    <rect x="215" y="88" width="90" height="18" fill="#0369a1" rx="4"/>
    <text x="260" y="100" fill="white" font-size="9" text-anchor="middle">Dataset prep</text>
    <!-- Step 4: Fine-tuning N2 -->
    <text x="120" y="130" fill="#94a3b8" font-size="10" text-anchor="end">4. Fine-tune N2</text>
    <rect x="305" y="116" width="180" height="18" fill="#7c3aed" rx="4"/>
    <text x="395" y="128" fill="white" font-size="9" text-anchor="middle">GR00T N2 fine-tune ($7,200)</text>
    <!-- Step 5: Eval & Validation -->
    <text x="120" y="158" fill="#94a3b8" font-size="10" text-anchor="end">5. Eval & Validate</text>
    <rect x="395" y="144" width="90" height="18" fill="#0369a1" rx="4"/>
    <text x="440" y="156" fill="white" font-size="9" text-anchor="middle">Benchmark eval</text>
    <!-- Step 6: Shadow Deployment -->
    <text x="120" y="186" fill="#94a3b8" font-size="10" text-anchor="end">6. Shadow Deploy</text>
    <rect x="485" y="172" width="90" height="18" fill="#C74634" rx="4"/>
    <text x="530" y="184" fill="white" font-size="9" text-anchor="middle">A/B shadow test</text>
    <!-- Step 7: Gradual Cutover -->
    <text x="120" y="214" fill="#94a3b8" font-size="10" text-anchor="end">7. Gradual Cutover</text>
    <rect x="575" y="200" width="90" height="18" fill="#C74634" rx="4"/>
    <text x="620" y="212" fill="white" font-size="9" text-anchor="middle">Traffic migration</text>
    <!-- Step 8: N1.6 EOL -->
    <text x="120" y="242" fill="#94a3b8" font-size="10" text-anchor="end">8. N1.6 EOL</text>
    <rect x="665" y="228" width="90" height="18" fill="#7f1d1d" rx="4"/>
    <text x="710" y="240" fill="white" font-size="9" text-anchor="middle">Decommission N1.6</text>
    <!-- N2 Release marker -->
    <line x1="125" y1="24" x2="125" y2="285" stroke="#4ade80" stroke-width="2" stroke-dasharray="5"/>
    <text x="130" y="272" fill="#4ade80" font-size="9">N2 Release (H2 2026)</text>
    <!-- EOL marker -->
    <line x1="665" y1="24" x2="665" y2="285" stroke="#f87171" stroke-width="2" stroke-dasharray="5"/>
    <text x="668" y="272" fill="#f87171" font-size="9">N1.6 EOL (Mar 2027)</text>
  </svg>
</div>

<h2>8-Step Migration Plan</h2>
<table>
  <thead>
    <tr>
      <th>#</th><th>Step</th><th>Owner</th><th>Duration</th><th>Cost</th><th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>Enroll in GR00T N2 Beta Program</td><td>ML Infra</td><td>2 weeks</td><td>—</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>2</td><td>Architecture review &amp; gap analysis (7B vs 1.5B)</td><td>ML Lead</td><td>4 weeks</td><td>—</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>3</td><td>Re-format training data for N2 multimodal inputs</td><td>Data Eng</td><td>2 weeks</td><td>$800</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>4</td><td>Fine-tune N2 on OCI A100 cluster (1000 demos)</td><td>ML Infra</td><td>8 weeks</td><td>$7,200</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>5</td><td>Benchmark eval: LIBERO-90 + closed-loop sim</td><td>Eval Team</td><td>2 weeks</td><td>$500</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>6</td><td>Shadow deployment with A/B traffic split</td><td>Platform</td><td>2 weeks</td><td>$700</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>7</td><td>Gradual cutover: 10% → 50% → 100% traffic</td><td>SRE</td><td>2 weeks</td><td>$300</td><td><span class="badge badge-yellow">Planned</span></td></tr>
    <tr><td>8</td><td>N1.6 decommission &amp; EOL (Mar 2027)</td><td>Platform</td><td>1 week</td><td>—</td><td><span class="badge badge-red">EOL</span></td></tr>
  </tbody>
</table>

<h2>N2 New Capabilities</h2>
<div class="grid">
  <div class="card">
    <h3>Video Understanding</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Native video input processing — watch-then-act paradigm. Learns directly from human demonstration videos without teleoperation hardware.</p>
  </div>
  <div class="card">
    <h3>Language-conditioned Control</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">7B-parameter transformer enables richer instruction following. Multi-step task decomposition from natural language commands.</p>
  </div>
  <div class="card">
    <h3>Multimodal Reward</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Vision-language reward signals replace hand-crafted reward functions. Enables RLHF-style alignment for robot policies.</p>
  </div>
  <div class="card">
    <h3>Projected SR: 0.89–0.94</h3>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:6px;">Average +15pp success rate improvement over N1.6 baseline (0.74) across LIBERO-90 and internal manipulation benchmarks.</p>
  </div>
</div>

<p style="color:#475569;font-size:0.75rem;margin-top:32px;">OCI Robot Cloud · GR00T N1→N2 Migration Planner · Port 8984 · &copy; 2026 Oracle</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N1→N2 Migration Planner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        sr_n1 = 0.74
        sr_n2_low = 0.89
        sr_n2_high = 0.94
        return {
            "status": "ok",
            "service": "groot_n1_n2_migration_planner",
            "port": 8984,
            "migration_steps": 8,
            "n1_sr": sr_n1,
            "n2_sr_range": [sr_n2_low, sr_n2_high],
            "sr_delta_pp": round((sr_n2_low - sr_n1) * 100, 1),
            "migration_cost_usd": 10500,
            "n1_eol": "2027-03",
            "n2_params_B": 7,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8984)
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8984), Handler)
        print("Serving on http://0.0.0.0:8984")
        srv.serve_forever()
