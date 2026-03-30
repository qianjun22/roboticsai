"""Partner Pilot Scorecard — FastAPI port 8593"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8593

def build_html():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Partner Pilot Scorecard — OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
  .header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 20px 32px; display: flex; align-items: center; gap: 16px; }
  .header h1 { color: #C74634; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }
  .header .sub { color: #94a3b8; font-size: 0.9rem; }
  .badge { background: #C74634; color: #fff; font-size: 0.75rem; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
  .container { max-width: 1400px; margin: 0 auto; padding: 32px; }
  .summary-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 32px; }
  .summary-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .summary-card .partner { font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px; }
  .summary-card .score { font-size: 2.2rem; font-weight: 700; }
  .summary-card .verdict { font-size: 0.8rem; font-weight: 600; padding: 4px 12px; border-radius: 20px; display: inline-block; margin-top: 8px; }
  .promote { color: #10b981; background: rgba(16,185,129,0.12); border: 1px solid #10b981; }
  .blocked { color: #f59e0b; background: rgba(245,158,11,0.12); border: 1px solid #f59e0b; }
  .develop { color: #f59e0b; background: rgba(245,158,11,0.12); border: 1px solid #f59e0b; }
  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .chart-full { grid-column: 1 / -1; }
  .chart-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; }
  .chart-card h2 { color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
  .chart-card h2::before { content: ''; display: inline-block; width: 4px; height: 16px; background: #C74634; border-radius: 2px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .insight { background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; padding: 12px 16px; margin-top: 16px; color: #38bdf8; font-size: 0.85rem; }
  .footer { text-align: center; color: #475569; font-size: 0.8rem; padding: 24px; border-top: 1px solid #1e293b; }
  .rag-green { fill: rgba(16,185,129,0.25); stroke: #10b981; }
  .rag-amber { fill: rgba(245,158,11,0.25); stroke: #f59e0b; }
  .rag-red { fill: rgba(239,68,68,0.25); stroke: #ef4444; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Partner Pilot Scorecard</h1>
    <div class="sub">Pilot readiness KPIs — PI Robotics / Machina Labs / Wandelbots</div>
  </div>
  <span class="badge">PORT 8593</span>
</div>

<div class="container">

  <!-- Summary Cards -->
  <div class="summary-row">
    <div class="summary-card">
      <div class="partner">PI Robotics</div>
      <div class="score" style="color:#10b981">94%</div>
      <div>Readiness Score</div>
      <span class="verdict promote">PROMOTE NOW</span>
    </div>
    <div class="summary-card">
      <div class="partner">Machina Labs</div>
      <div class="score" style="color:#f59e0b">81%</div>
      <div>Readiness Score</div>
      <span class="verdict blocked">DPA BLOCKED</span>
    </div>
    <div class="summary-card">
      <div class="partner">Wandelbots</div>
      <div class="score" style="color:#f59e0b">67%</div>
      <div>Readiness Score</div>
      <span class="verdict develop">IN DEVELOPMENT</span>
    </div>
  </div>

  <!-- KPI Scorecard Table (full width) -->
  <div class="chart-card chart-full">
    <h2>KPI Scorecard — RAG Status by Pilot &amp; Metric</h2>
    <svg viewBox="0 0 1100 320" width="100%">
      <!-- Table headers -->
      <rect x="10" y="10" width="1080" height="36" fill="#0f172a" rx="4"/>
      <text x="150" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">SR Threshold</text>
      <text x="290" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">Latency</text>
      <text x="430" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">Uptime</text>
      <text x="570" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">NPS</text>
      <text x="710" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">Adoption</text>
      <text x="850" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">ROI</text>
      <text x="990" y="33" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">DPA</text>

      <!-- Row 1: PI Robotics (all green) -->
      <rect x="10" y="56" width="1080" height="72" fill="#0d1f2d" rx="4"/>
      <text x="60" y="96" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">PI Robotics</text>
      <!-- SR -->
      <rect x="80" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="150" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">95%</text>
      <text x="150" y="107" text-anchor="middle" fill="#10b981" font-size="10">&gt;90% target</text>
      <!-- Latency -->
      <rect x="220" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="290" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">218ms</text>
      <text x="290" y="107" text-anchor="middle" fill="#10b981" font-size="10">&lt;250ms SLA</text>
      <!-- Uptime -->
      <rect x="360" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="430" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">99.8%</text>
      <text x="430" y="107" text-anchor="middle" fill="#10b981" font-size="10">&gt;99% target</text>
      <!-- NPS -->
      <rect x="500" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="570" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">+72</text>
      <text x="570" y="107" text-anchor="middle" fill="#10b981" font-size="10">&gt;+50 target</text>
      <!-- Adoption -->
      <rect x="640" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="710" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">88%</text>
      <text x="710" y="107" text-anchor="middle" fill="#10b981" font-size="10">&gt;80% target</text>
      <!-- ROI -->
      <rect x="780" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="850" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">2.4x</text>
      <text x="850" y="107" text-anchor="middle" fill="#10b981" font-size="10">&gt;1.5x target</text>
      <!-- DPA -->
      <rect x="920" y="64" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="990" y="90" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">SIGNED</text>
      <text x="990" y="107" text-anchor="middle" fill="#10b981" font-size="10">Complete</text>

      <!-- Row 2: Machina Labs -->
      <rect x="10" y="140" width="1080" height="72" fill="#0d1f2d" rx="4"/>
      <text x="60" y="180" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">Machina</text>
      <!-- SR: green -->
      <rect x="80" y="148" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="150" y="174" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">91%</text>
      <text x="150" y="191" text-anchor="middle" fill="#10b981" font-size="10">&gt;90% target</text>
      <!-- Latency: green -->
      <rect x="220" y="148" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="290" y="174" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">241ms</text>
      <text x="290" y="191" text-anchor="middle" fill="#10b981" font-size="10">&lt;250ms SLA</text>
      <!-- Uptime: amber -->
      <rect x="360" y="148" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="430" y="174" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">98.4%</text>
      <text x="430" y="191" text-anchor="middle" fill="#f59e0b" font-size="10">Near &gt;99%</text>
      <!-- NPS: green -->
      <rect x="500" y="148" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="570" y="174" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">+61</text>
      <text x="570" y="191" text-anchor="middle" fill="#10b981" font-size="10">&gt;+50 target</text>
      <!-- Adoption: green -->
      <rect x="640" y="148" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="710" y="174" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">82%</text>
      <text x="710" y="191" text-anchor="middle" fill="#10b981" font-size="10">&gt;80% target</text>
      <!-- ROI: amber -->
      <rect x="780" y="148" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="850" y="174" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">1.6x</text>
      <text x="850" y="191" text-anchor="middle" fill="#f59e0b" font-size="10">Marginal 1.5x</text>
      <!-- DPA: RED -->
      <rect x="920" y="148" width="140" height="56" class="rag-red" rx="6" stroke-width="1.5"/>
      <text x="990" y="174" text-anchor="middle" fill="#ef4444" font-size="13" font-weight="700">PENDING</text>
      <text x="990" y="191" text-anchor="middle" fill="#ef4444" font-size="10">BLOCKER</text>

      <!-- Row 3: Wandelbots -->
      <rect x="10" y="224" width="1080" height="72" fill="#0d1f2d" rx="4"/>
      <text x="60" y="264" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">Wandelbots</text>
      <!-- SR: amber -->
      <rect x="80" y="232" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="150" y="258" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">84%</text>
      <text x="150" y="275" text-anchor="middle" fill="#f59e0b" font-size="10">Below &gt;90%</text>
      <!-- Latency: amber -->
      <rect x="220" y="232" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="290" y="258" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">267ms</text>
      <text x="290" y="275" text-anchor="middle" fill="#f59e0b" font-size="10">Exceeds 250ms</text>
      <!-- Uptime: green -->
      <rect x="360" y="232" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="430" y="258" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">99.1%</text>
      <text x="430" y="275" text-anchor="middle" fill="#10b981" font-size="10">&gt;99% target</text>
      <!-- NPS: amber -->
      <rect x="500" y="232" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="570" y="258" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">+44</text>
      <text x="570" y="275" text-anchor="middle" fill="#f59e0b" font-size="10">Below +50</text>
      <!-- Adoption: amber -->
      <rect x="640" y="232" width="140" height="56" class="rag-amber" rx="6" stroke-width="1.5"/>
      <text x="710" y="258" text-anchor="middle" fill="#f59e0b" font-size="13" font-weight="700">71%</text>
      <text x="710" y="275" text-anchor="middle" fill="#f59e0b" font-size="10">Below &gt;80%</text>
      <!-- ROI: green -->
      <rect x="780" y="232" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="850" y="258" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">1.9x</text>
      <text x="850" y="275" text-anchor="middle" fill="#10b981" font-size="10">&gt;1.5x target</text>
      <!-- DPA: green -->
      <rect x="920" y="232" width="140" height="56" class="rag-green" rx="6" stroke-width="1.5"/>
      <text x="990" y="258" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">SIGNED</text>
      <text x="990" y="275" text-anchor="middle" fill="#10b981" font-size="10">Complete</text>
    </svg>
    <div class="insight">PI: all green — recommend immediate promotion. Machina: DPA is sole blocker (81% otherwise ready). Wandelbots: SR threshold + latency + adoption require remediation before promotion (67% overall).</div>
  </div>

  <div class="charts-grid">

    <!-- Pilot Readiness Gauges -->
    <div class="chart-card">
      <h2>Pilot Readiness Gauges</h2>
      <svg viewBox="0 0 520 280" width="100%">
        <!-- PI gauge (cx=110) -->
        <!-- Arc background -->
        <path d="M 30 200 A 80 80 0 0 1 190 200" fill="none" stroke="#1e3a4a" stroke-width="18" stroke-linecap="round"/>
        <!-- PI: 94% → angle = 180 * 0.94 = 169.2 deg from left -->
        <path d="M 30 200 A 80 80 0 0 1 185.6 186.5" fill="none" stroke="#10b981" stroke-width="18" stroke-linecap="round"/>
        <text x="110" y="190" text-anchor="middle" fill="#10b981" font-size="22" font-weight="700">94%</text>
        <text x="110" y="215" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="600">PI Robotics</text>
        <text x="110" y="233" text-anchor="middle" fill="#10b981" font-size="11">PROMOTE NOW</text>
        <text x="30" y="218" text-anchor="middle" fill="#64748b" font-size="9">0%</text>
        <text x="190" y="218" text-anchor="middle" fill="#64748b" font-size="9">100%</text>

        <!-- Machina gauge (cx=270) -->
        <path d="M 190 200 A 80 80 0 0 1 350 200" fill="none" stroke="#1e3a4a" stroke-width="18" stroke-linecap="round"/>
        <!-- Machina: 81% → 180*0.81=145.8 deg -->
        <path d="M 190 200 A 80 80 0 0 1 339.4 168.9" fill="none" stroke="#f59e0b" stroke-width="18" stroke-linecap="round"/>
        <text x="270" y="190" text-anchor="middle" fill="#f59e0b" font-size="22" font-weight="700">81%</text>
        <text x="270" y="215" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="600">Machina Labs</text>
        <text x="270" y="233" text-anchor="middle" fill="#f59e0b" font-size="11">DPA BLOCKED</text>
        <text x="190" y="218" text-anchor="middle" fill="#64748b" font-size="9">0%</text>
        <text x="350" y="218" text-anchor="middle" fill="#64748b" font-size="9">100%</text>

        <!-- Wandelbots gauge (cx=430) -->
        <path d="M 350 200 A 80 80 0 0 1 510 200" fill="none" stroke="#1e3a4a" stroke-width="18" stroke-linecap="round"/>
        <!-- Wandelbots: 67% → 180*0.67=120.6 deg -->
        <path d="M 350 200 A 80 80 0 0 1 470 131" fill="none" stroke="#f59e0b" stroke-width="18" stroke-linecap="round"/>
        <text x="430" y="190" text-anchor="middle" fill="#f59e0b" font-size="22" font-weight="700">67%</text>
        <text x="430" y="215" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="600">Wandelbots</text>
        <text x="430" y="233" text-anchor="middle" fill="#f59e0b" font-size="11">IN DEVELOPMENT</text>
        <text x="350" y="218" text-anchor="middle" fill="#64748b" font-size="9">0%</text>
        <text x="510" y="218" text-anchor="middle" fill="#64748b" font-size="9">100%</text>

        <!-- Legend -->
        <circle cx="100" cy="260" r="5" fill="#10b981"/>
        <text x="110" y="264" fill="#94a3b8" font-size="10">Promote (&gt;90%)</text>
        <circle cx="220" cy="260" r="5" fill="#f59e0b"/>
        <text x="230" y="264" fill="#94a3b8" font-size="10">In Progress (60-90%)</text>
        <circle cx="360" cy="260" r="5" fill="#ef4444"/>
        <text x="370" y="264" fill="#94a3b8" font-size="10">At Risk (&lt;60%)</text>
      </svg>
    </div>

    <!-- 30-Day Success Trajectory -->
    <div class="chart-card">
      <h2>30-Day Success Trajectory Projection</h2>
      <svg viewBox="0 0 520 280" width="100%">
        <!-- Axes -->
        <line x1="50" y1="15" x2="50" y2="220" stroke="#334155" stroke-width="1"/>
        <line x1="50" y1="220" x2="500" y2="220" stroke="#334155" stroke-width="1"/>
        <!-- Grid -->
        <line x1="50" y1="170" x2="500" y2="170" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="50" y1="120" x2="500" y2="120" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="50" y1="70" x2="500" y2="70" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="50" y1="20" x2="500" y2="20" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- Y labels (50%-100%) -->
        <text x="42" y="224" text-anchor="end" fill="#64748b" font-size="10">50%</text>
        <text x="42" y="174" text-anchor="end" fill="#64748b" font-size="10">62%</text>
        <text x="42" y="124" text-anchor="end" fill="#64748b" font-size="10">75%</text>
        <text x="42" y="74" text-anchor="end" fill="#64748b" font-size="10">87%</text>
        <text x="42" y="24" text-anchor="end" fill="#64748b" font-size="10">100%</text>
        <!-- X labels (Day 0, 10, 20, 30) -->
        <text x="50" y="236" text-anchor="middle" fill="#64748b" font-size="10">D0</text>
        <text x="200" y="236" text-anchor="middle" fill="#64748b" font-size="10">D10</text>
        <text x="350" y="236" text-anchor="middle" fill="#64748b" font-size="10">D20</text>
        <text x="500" y="236" text-anchor="middle" fill="#64748b" font-size="10">D30</text>
        <!-- PI: starts 94%, projects to 98% (day0=94: y=220-(94-50)*4=44; day30=98: y=220-192=28) -->
        <!-- Confidence band -->
        <polygon points="50,44 200,36 350,30 500,24 500,32 350,38 200,44 50,52" fill="#10b981" opacity="0.1"/>
        <!-- Line -->
        <polyline points="50,44 200,36 350,30 500,24" fill="none" stroke="#10b981" stroke-width="2.5"/>
        <circle cx="50" cy="44" r="4" fill="#10b981"/>
        <circle cx="500" cy="24" r="4" fill="#10b981"/>
        <text x="510" y="28" fill="#10b981" font-size="10" font-weight="600">PI 98%</text>
        <!-- Machina: starts 81%, projects to 91% if DPA resolved (day0=81: y=220-(81-50)*4=96; day30=91: y=220-164=56) -->
        <polygon points="50,96 200,84 350,68 500,56 500,68 350,80 200,96 50,108" fill="#f59e0b" opacity="0.1"/>
        <polyline points="50,96 200,84 350,68 500,56" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="6,3"/>
        <circle cx="50" cy="96" r="4" fill="#f59e0b"/>
        <circle cx="500" cy="56" r="4" fill="#f59e0b"/>
        <text x="510" y="60" fill="#f59e0b" font-size="10" font-weight="600">Machina 91%</text>
        <!-- Wandelbots: starts 67%, projects to 75% (day0=67: y=220-(67-50)*4=152; day30=75: y=220-100=120) -->
        <polygon points="50,152 200,144 350,132 500,120 500,132 350,144 200,156 50,164" fill="#94a3b8" opacity="0.1"/>
        <polyline points="50,152 200,144 350,132 500,120" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-dasharray="3,3"/>
        <circle cx="50" cy="152" r="4" fill="#94a3b8"/>
        <circle cx="500" cy="120" r="4" fill="#94a3b8"/>
        <text x="510" y="124" fill="#94a3b8" font-size="10" font-weight="600">WB 75%</text>
        <!-- Promotion threshold line -->
        <line x1="50" y1="70" x2="500" y2="70" stroke="#C74634" stroke-width="1.5" stroke-dasharray="8,4"/>
        <text x="52" y="64" fill="#C74634" font-size="9">Promote threshold 90%</text>
        <!-- Legend -->
        <line x1="52" y1="252" x2="72" y2="252" stroke="#10b981" stroke-width="2.5"/>
        <text x="76" y="256" fill="#94a3b8" font-size="9">PI Robotics</text>
        <line x1="145" y1="252" x2="165" y2="252" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="6,3"/>
        <text x="169" y="256" fill="#94a3b8" font-size="9">Machina (DPA resolved)</text>
        <line x1="310" y1="252" x2="330" y2="252" stroke="#94a3b8" stroke-width="2.5" stroke-dasharray="3,3"/>
        <text x="334" y="256" fill="#94a3b8" font-size="9">Wandelbots</text>
      </svg>
      <div class="insight">30-day projection: PI reaches 98% (well above threshold). Machina crosses 90% by D18 if DPA signed this week. Wandelbots needs 45+ days at current trajectory — prioritize SR threshold and latency fixes.</div>
    </div>

  </div>

</div>

<div class="footer">OCI Robot Cloud — Partner Pilot Scorecard | Port 8593 | Pilot Readiness Analysis</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Pilot Scorecard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
