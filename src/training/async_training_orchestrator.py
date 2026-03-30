"""
OCI Robot Cloud — Async Training Orchestrator  (port 8680)
cycle-155B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json, time, random, math
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Async Training Orchestrator — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.6rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:28px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
  .card-wide{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:24px}
  .card h2{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:16px;letter-spacing:.04em}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;text-align:center}
  .metric .val{font-size:2rem;font-weight:700;color:#38bdf8}
  .metric .lbl{font-size:.78rem;color:#94a3b8;margin-top:4px}
  .metric .sub{font-size:.72rem;color:#64748b;margin-top:2px}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
  .footer{text-align:center;color:#475569;font-size:.75rem;margin-top:28px}
</style>
</head>
<body>

<h1>Async Training Orchestrator</h1>
<p class="subtitle">OCI Robot Cloud · Port 8680 · Priority queue: DAgger &gt; fine_tune &gt; eval &gt; SDG</p>

<!-- KPI metrics -->
<div class="metrics">
  <div class="metric"><div class="val">4.2h</div><div class="lbl">Saved / Cycle</div><div class="sub">parallel SDG + fine_tune</div></div>
  <div class="metric"><div class="val">0–8</div><div class="lbl">Job Queue Depth</div><div class="sub">live range</div></div>
  <div class="metric"><div class="val">0</div><div class="lbl">Job Starvation</div><div class="sub">last 30 days</div></div>
  <div class="metric"><div class="val">99.1%</div><div class="lbl">Scheduler Uptime</div><div class="sub">rolling 30d</div></div>
</div>

<!-- SVG 1: Job dependency DAG -->
<div class="card-wide">
  <h2>JOB DEPENDENCY DAG</h2>
  <svg viewBox="0 0 900 320" width="100%" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arr" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
        <polygon points="0 0,10 3.5,0 7" fill="#64748b"/>
      </marker>
      <filter id="glow"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>

    <!-- Lane labels -->
    <text x="14" y="80"  fill="#475569" font-size="11">BRANCH A</text>
    <text x="14" y="200" fill="#475569" font-size="11">BRANCH B</text>

    <!-- SDG box (start, shared) -->
    <rect x="80" y="120" width="110" height="46" rx="8" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="135" y="140" fill="#38bdf8" font-size="12" font-weight="600" text-anchor="middle">SDG</text>
    <text x="135" y="156" fill="#7dd3fc" font-size="10" text-anchor="middle">data gen</text>

    <!-- FILTER box -->
    <rect x="240" y="55" width="110" height="46" rx="8" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="295" y="75" fill="#38bdf8" font-size="12" font-weight="600" text-anchor="middle">FILTER</text>
    <text x="295" y="91" fill="#7dd3fc" font-size="10" text-anchor="middle">quality gate</text>

    <!-- AUGMENT box -->
    <rect x="240" y="185" width="110" height="46" rx="8" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="295" y="205" fill="#38bdf8" font-size="12" font-weight="600" text-anchor="middle">AUGMENT</text>
    <text x="295" y="221" fill="#7dd3fc" font-size="10" text-anchor="middle">domain rand</text>

    <!-- FINE_TUNE box -->
    <rect x="410" y="120" width="120" height="46" rx="8" fill="#4a1c0a" stroke="#C74634" stroke-width="1.5" filter="url(#glow)"/>
    <text x="470" y="140" fill="#C74634" font-size="12" font-weight="600" text-anchor="middle">FINE_TUNE</text>
    <text x="470" y="156" fill="#fb923c" font-size="10" text-anchor="middle">GR00T N1.6</text>

    <!-- EVAL box -->
    <rect x="590" y="120" width="110" height="46" rx="8" fill="#052e16" stroke="#22c55e" stroke-width="1.5"/>
    <text x="645" y="140" fill="#22c55e" font-size="12" font-weight="600" text-anchor="middle">EVAL</text>
    <text x="645" y="156" fill="#86efac" font-size="10" text-anchor="middle">closed-loop</text>

    <!-- DEPLOY box -->
    <rect x="760" y="120" width="110" height="46" rx="8" fill="#2e1065" stroke="#a78bfa" stroke-width="1.5"/>
    <text x="815" y="140" fill="#a78bfa" font-size="12" font-weight="600" text-anchor="middle">DEPLOY</text>
    <text x="815" y="156" fill="#c4b5fd" font-size="10" text-anchor="middle">Jetson / OCI</text>

    <!-- Arrows SDG → FILTER (queue depth 3) -->
    <line x1="190" y1="135" x2="238" y2="95" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="194" y="96" width="28" height="16" rx="4" fill="#334155"/>
    <text x="208" y="108" fill="#e2e8f0" font-size="10" text-anchor="middle">q:3</text>

    <!-- Arrows SDG → AUGMENT (queue depth 5) -->
    <line x1="190" y1="152" x2="238" y2="198" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="194" y="162" width="28" height="16" rx="4" fill="#334155"/>
    <text x="208" y="174" fill="#e2e8f0" font-size="10" text-anchor="middle">q:5</text>

    <!-- FILTER → FINE_TUNE (queue depth 2) -->
    <line x1="350" y1="88" x2="408" y2="132" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="358" y="100" width="28" height="16" rx="4" fill="#334155"/>
    <text x="372" y="112" fill="#e2e8f0" font-size="10" text-anchor="middle">q:2</text>

    <!-- AUGMENT → FINE_TUNE (queue depth 4) -->
    <line x1="350" y1="205" x2="408" y2="158" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="358" y="176" width="28" height="16" rx="4" fill="#334155"/>
    <text x="372" y="188" fill="#e2e8f0" font-size="10" text-anchor="middle">q:4</text>

    <!-- FINE_TUNE → EVAL (queue depth 1) -->
    <line x1="530" y1="143" x2="588" y2="143" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="541" y="132" width="28" height="16" rx="4" fill="#334155"/>
    <text x="555" y="144" fill="#e2e8f0" font-size="10" text-anchor="middle">q:1</text>

    <!-- EVAL → DEPLOY (queue depth 1) -->
    <line x1="700" y1="143" x2="758" y2="143" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>
    <rect x="710" y="132" width="28" height="16" rx="4" fill="#334155"/>
    <text x="724" y="144" fill="#e2e8f0" font-size="10" text-anchor="middle">q:1</text>

    <!-- Parallel bracket annotation -->
    <rect x="228" y="30" width="260" height="248" rx="6" fill="none" stroke="#1e40af" stroke-width="1" stroke-dasharray="5,3"/>
    <text x="358" y="24" fill="#3b82f6" font-size="11" text-anchor="middle">parallel branches — saves 4.2 hr/cycle</text>

    <!-- Priority legend -->
    <text x="14" y="300" fill="#C74634" font-size="11">■ DAgger (p0)</text>
    <text x="110" y="300" fill="#C74634" font-size="11">■ fine_tune (p1)</text>
    <text x="214" y="300" fill="#22c55e" font-size="11">■ eval (p2)</text>
    <text x="290" y="300" fill="#38bdf8" font-size="11">■ SDG (p3)</text>
  </svg>
</div>

<div class="grid">
  <!-- SVG 2: GPU utilization heatmap -->
  <div class="card">
    <h2>GPU UTILIZATION HEATMAP — 24 H</h2>
    <svg viewBox="0 0 420 220" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- Y axis labels -->
      <text x="38" y="50"  fill="#94a3b8" font-size="10" text-anchor="end">GPU 0</text>
      <text x="38" y="95"  fill="#94a3b8" font-size="10" text-anchor="end">GPU 1</text>
      <text x="38" y="140" fill="#94a3b8" font-size="10" text-anchor="end">GPU 2</text>
      <text x="38" y="185" fill="#94a3b8" font-size="10" text-anchor="end">GPU 3</text>

      <!-- X axis: 24 hour ticks every 4h -->
      <text x="44"  y="205" fill="#64748b" font-size="9" text-anchor="middle">0</text>
      <text x="110" y="205" fill="#64748b" font-size="9" text-anchor="middle">4</text>
      <text x="176" y="205" fill="#64748b" font-size="9" text-anchor="middle">8</text>
      <text x="242" y="205" fill="#64748b" font-size="9" text-anchor="middle">12</text>
      <text x="308" y="205" fill="#64748b" font-size="9" text-anchor="middle">16</text>
      <text x="374" y="205" fill="#64748b" font-size="9" text-anchor="middle">20</text>
      <text x="410" y="205" fill="#64748b" font-size="9" text-anchor="middle">24h</text>

      <!-- GPU 0 row: SDG blocks (blue), fine_tune (orange) -->
      <!-- hour 0-3 SDG 72% -->
      <rect x="44" y="32" width="66" height="30" rx="3" fill="#1e3a5f"/>
      <rect x="44" y="32" width="66" height="21" rx="3" fill="#1d4ed8" opacity=".85"/>
      <text x="77" y="51" fill="#bfdbfe" font-size="9" text-anchor="middle">72%</text>
      <!-- hour 4-9 fine_tune 95% -->
      <rect x="112" y="32" width="110" height="30" rx="3" fill="#4a1c0a"/>
      <rect x="112" y="32" width="110" height="28" rx="3" fill="#c2410c" opacity=".85"/>
      <text x="167" y="51" fill="#fed7aa" font-size="9" text-anchor="middle">95%</text>
      <!-- hour 10-13 eval 60% -->
      <rect x="224" y="32" width="77" height="30" rx="3" fill="#052e16"/>
      <rect x="224" y="32" width="77" height="18" rx="3" fill="#16a34a" opacity=".85"/>
      <text x="262" y="51" fill="#bbf7d0" font-size="9" text-anchor="middle">60%</text>
      <!-- hour 14-19 fine_tune 88% -->
      <rect x="303" y="32" width="88" height="30" rx="3" fill="#4a1c0a"/>
      <rect x="303" y="32" width="88" height="26" rx="3" fill="#c2410c" opacity=".85"/>
      <text x="347" y="51" fill="#fed7aa" font-size="9" text-anchor="middle">88%</text>
      <!-- hour 20-23 idle -->
      <rect x="393" y="32" width="17" height="30" rx="3" fill="#1e293b"/>

      <!-- GPU 1 row -->
      <!-- 0-5 fine_tune 91% -->
      <rect x="44" y="77" width="110" height="30" rx="3" fill="#4a1c0a"/>
      <rect x="44" y="77" width="110" height="27" rx="3" fill="#c2410c" opacity=".85"/>
      <text x="99" y="96" fill="#fed7aa" font-size="9" text-anchor="middle">91%</text>
      <!-- 6-11 SDG 68% -->
      <rect x="156" y="77" width="110" height="30" rx="3" fill="#1e3a5f"/>
      <rect x="156" y="77" width="110" height="20" rx="3" fill="#1d4ed8" opacity=".85"/>
      <text x="211" y="96" fill="#bfdbfe" font-size="9" text-anchor="middle">68%</text>
      <!-- 12-17 eval 77% -->
      <rect x="268" y="77" width="99" height="30" rx="3" fill="#052e16"/>
      <rect x="268" y="77" width="99" height="23" rx="3" fill="#16a34a" opacity=".85"/>
      <text x="317" y="96" fill="#bbf7d0" font-size="9" text-anchor="middle">77%</text>
      <!-- 18-23 SDG 55% -->
      <rect x="369" y="77" width="41" height="30" rx="3" fill="#1e3a5f"/>
      <rect x="369" y="77" width="41" height="16" rx="3" fill="#1d4ed8" opacity=".85"/>
      <text x="389" y="96" fill="#bfdbfe" font-size="9" text-anchor="middle">55%</text>

      <!-- GPU 2 row -->
      <!-- 0-7 eval 80% -->
      <rect x="44" y="122" width="132" height="30" rx="3" fill="#052e16"/>
      <rect x="44" y="122" width="132" height="24" rx="3" fill="#16a34a" opacity=".85"/>
      <text x="110" y="141" fill="#bbf7d0" font-size="9" text-anchor="middle">80%</text>
      <!-- 8-15 fine_tune 99% -->
      <rect x="178" y="122" width="132" height="30" rx="3" fill="#4a1c0a"/>
      <rect x="178" y="122" width="132" height="29" rx="3" fill="#c2410c" opacity=".85"/>
      <text x="244" y="141" fill="#fed7aa" font-size="9" text-anchor="middle">99%</text>
      <!-- 16-21 SDG 62% -->
      <rect x="312" y="122" width="88" height="30" rx="3" fill="#1e3a5f"/>
      <rect x="312" y="122" width="88" height="18" rx="3" fill="#1d4ed8" opacity=".85"/>
      <text x="356" y="141" fill="#bfdbfe" font-size="9" text-anchor="middle">62%</text>
      <!-- 22-23 idle -->
      <rect x="402" y="122" width="8" height="30" rx="3" fill="#1e293b"/>

      <!-- GPU 3 row -->
      <!-- 0-3 idle -->
      <rect x="44" y="167" width="44" height="30" rx="3" fill="#1e293b"/>
      <!-- 4-11 SDG 74% -->
      <rect x="90" y="167" width="132" height="30" rx="3" fill="#1e3a5f"/>
      <rect x="90" y="167" width="132" height="22" rx="3" fill="#1d4ed8" opacity=".85"/>
      <text x="156" y="186" fill="#bfdbfe" font-size="9" text-anchor="middle">74%</text>
      <!-- 12-19 fine_tune 93% -->
      <rect x="224" y="167" width="132" height="30" rx="3" fill="#4a1c0a"/>
      <rect x="224" y="167" width="132" height="27" rx="3" fill="#c2410c" opacity=".85"/>
      <text x="290" y="186" fill="#fed7aa" font-size="9" text-anchor="middle">93%</text>
      <!-- 20-23 eval 58% -->
      <rect x="358" y="167" width="52" height="30" rx="3" fill="#052e16"/>
      <rect x="358" y="167" width="52" height="17" rx="3" fill="#16a34a" opacity=".85"/>
      <text x="384" y="186" fill="#bbf7d0" font-size="9" text-anchor="middle">58%</text>

      <!-- legend -->
      <rect x="44" y="212" width="10" height="8" fill="#1d4ed8" rx="1"/>
      <text x="58" y="220" fill="#94a3b8" font-size="9">SDG</text>
      <rect x="88" y="212" width="10" height="8" fill="#c2410c" rx="1"/>
      <text x="102" y="220" fill="#94a3b8" font-size="9">fine_tune</text>
      <rect x="148" y="212" width="10" height="8" fill="#16a34a" rx="1"/>
      <text x="162" y="220" fill="#94a3b8" font-size="9">eval</text>
      <rect x="190" y="212" width="10" height="8" fill="#1e293b" stroke="#334155" stroke-width="1" rx="1"/>
      <text x="204" y="220" fill="#94a3b8" font-size="9">idle</text>
    </svg>
  </div>

  <!-- SVG 3: Gantt chart -->
  <div class="card">
    <h2>JOB TIMELINE GANTT — 7 DAY CYCLE</h2>
    <svg viewBox="0 0 420 240" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- Y axis labels -->
      <text x="52" y="42"  fill="#94a3b8" font-size="10" text-anchor="end">SDG</text>
      <text x="52" y="77"  fill="#94a3b8" font-size="10" text-anchor="end">FILTER</text>
      <text x="52" y="112" fill="#94a3b8" font-size="10" text-anchor="end">AUGMENT</text>
      <text x="52" y="147" fill="#94a3b8" font-size="10" text-anchor="end">FINE_TUNE</text>
      <text x="52" y="182" fill="#94a3b8" font-size="10" text-anchor="end">EVAL</text>
      <text x="52" y="217" fill="#94a3b8" font-size="10" text-anchor="end">DEPLOY</text>

      <!-- Day ticks -->
      <text x="60"  y="228" fill="#64748b" font-size="8" text-anchor="middle">D1</text>
      <text x="109" y="228" fill="#64748b" font-size="8" text-anchor="middle">D2</text>
      <text x="158" y="228" fill="#64748b" font-size="8" text-anchor="middle">D3</text>
      <text x="207" y="228" fill="#64748b" font-size="8" text-anchor="middle">D4</text>
      <text x="256" y="228" fill="#64748b" font-size="8" text-anchor="middle">D5</text>
      <text x="305" y="228" fill="#64748b" font-size="8" text-anchor="middle">D6</text>
      <text x="354" y="228" fill="#64748b" font-size="8" text-anchor="middle">D7</text>
      <text x="403" y="228" fill="#64748b" font-size="8" text-anchor="middle">D8</text>

      <!-- grid lines -->
      <line x1="60" y1="20" x2="60"  y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="109" y1="20" x2="109" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="158" y1="20" x2="158" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="207" y1="20" x2="207" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="256" y1="20" x2="256" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="305" y1="20" x2="305" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="354" y1="20" x2="354" y2="222" stroke="#1e293b" stroke-width="1"/>
      <line x1="403" y1="20" x2="403" y2="222" stroke="#1e293b" stroke-width="1"/>

      <!-- SDG: scheduled D1-D3 (gray), actual D1-D2.5 (blue, parallel saves time) -->
      <rect x="60" y="28" width="147" height="12" rx="2" fill="#334155"/>
      <rect x="60" y="28" width="120" height="12" rx="2" fill="#1d4ed8" opacity=".9"/>
      <text x="65" y="38" fill="#bfdbfe" font-size="8">SDG actual 2.5d (sched 3d)</text>

      <!-- FILTER: starts D1, actual D1.5-D3 -->
      <rect x="60"  y="63" width="147" height="12" rx="2" fill="#334155"/>
      <rect x="84"  y="63" width="113" height="12" rx="2" fill="#0ea5e9" opacity=".85"/>
      <text x="89" y="73" fill="#e0f2fe" font-size="8">FILTER actual (parallel)</text>

      <!-- AUGMENT: D1-D3 parallel branch -->
      <rect x="60"  y="98" width="147" height="12" rx="2" fill="#334155"/>
      <rect x="60"  y="98" width="130" height="12" rx="2" fill="#0284c7" opacity=".85"/>
      <text x="65" y="108" fill="#e0f2fe" font-size="8">AUGMENT actual (parallel)</text>

      <!-- FINE_TUNE: scheduled D3-D6, actual D2.5-D5.3 (saves ~0.7d) -->
      <rect x="158" y="133" width="147" height="12" rx="2" fill="#334155"/>
      <rect x="120" y="133" width="130" height="12" rx="2" fill="#c2410c" opacity=".9"/>
      <text x="124" y="143" fill="#fed7aa" font-size="8">FINE_TUNE actual 2.7d (sched 3d)</text>

      <!-- EVAL: D5.3-D6.5 -->
      <rect x="256" y="168" width="98" height="12" rx="2" fill="#334155"/>
      <rect x="250" y="168" width="78" height="12" rx="2" fill="#16a34a" opacity=".9"/>
      <text x="254" y="178" fill="#bbf7d0" font-size="8">EVAL actual 1.6d (sched 2d)</text>

      <!-- DEPLOY: D6.5-D7 -->
      <rect x="354" y="203" width="49" height="12" rx="2" fill="#334155"/>
      <rect x="328" y="203" width="49" height="12" rx="2" fill="#7c3aed" opacity=".9"/>
      <text x="333" y="213" fill="#ddd6fe" font-size="8">DEPLOY 1d</text>

      <!-- savings annotation -->
      <line x1="372" y1="25" x2="403" y2="25" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,2"/>
      <text x="408" y="29" fill="#22c55e" font-size="8">−4.2h</text>

      <!-- legend -->
      <rect x="60" y="234" width="8" height="6" fill="#334155" rx="1"/>
      <text x="72" y="240" fill="#64748b" font-size="8">scheduled</text>
      <rect x="120" y="234" width="8" height="6" fill="#1d4ed8" rx="1"/>
      <text x="132" y="240" fill="#94a3b8" font-size="8">actual</text>
    </svg>
  </div>
</div>

<div class="footer">OCI Robot Cloud · Async Training Orchestrator · Port 8680 · cycle-155B</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Async Training Orchestrator", version="155B")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "async_training_orchestrator",
            "port": 8680,
            "cycle": "155B",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": {
                "parallel_savings_hr": 4.2,
                "queue_depth_range": "0-8",
                "job_starvation_30d": 0,
                "priority_order": ["dagger", "fine_tune", "eval", "sdg"],
            },
        }

    @app.get("/jobs")
    async def jobs():
        job_types = ["sdg", "filter", "augment", "fine_tune", "eval", "deploy"]
        statuses = ["running", "queued", "completed", "pending"]
        return {
            "jobs": [
                {
                    "id": f"job-{i:04d}",
                    "type": job_types[i % len(job_types)],
                    "status": statuses[i % len(statuses)],
                    "priority": i % 4,
                    "gpu": i % 4,
                    "created_at": (datetime.utcnow() - timedelta(hours=i)).isoformat() + "Z",
                }
                for i in range(12)
            ]
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8680)

else:
    # Stdlib HTTP fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "ok", "port": 8680, "fastapi": False}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8680), Handler)
        print("Async Training Orchestrator running on port 8680")
        srv.serve_forever()
