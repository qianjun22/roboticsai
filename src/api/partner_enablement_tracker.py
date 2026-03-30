"""
Partner Enablement Tracker — port 8615
OCI Robot Cloud | cycle-139A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler


def build_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Partner Enablement Tracker | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.7rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:28px}
  h2{color:#C74634;font-size:1.1rem;margin-bottom:12px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px;margin-bottom:28px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:28px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}
  .metric-label{color:#94a3b8;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
  .metric-value{color:#38bdf8;font-size:1.6rem;font-weight:700}
  .metric-sub{color:#64748b;font-size:.78rem;margin-top:4px}
  .partners-table{width:100%;border-collapse:collapse;margin-bottom:28px}
  .partners-table th{background:#0f172a;color:#94a3b8;font-size:.8rem;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}
  .partners-table td{padding:9px 12px;border-bottom:1px solid #1e293b;font-size:.88rem}
  .partners-table tr:hover td{background:#1e293b}
  .stage{padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
  .stage-production{background:#14532d;color:#86efac}
  .stage-integration{background:#1e3a5f;color:#93c5fd}
  .stage-eval{background:#4c1d95;color:#c4b5fd}
  .stage-blocked{background:#7f1d1d;color:#fca5a5}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>Partner Enablement Tracker</h1>
<p class="subtitle">OCI Robot Cloud &mdash; Port 8615 &mdash; Cycle-139A</p>

<div class="metrics">
  <div class="metric">
    <div class="metric-label">PI Time to Production</div>
    <div class="metric-value" style="color:#22c55e">8 days</div>
    <div class="metric-sub">Fastest partner onboarded</div>
  </div>
  <div class="metric">
    <div class="metric-label">Machina Block Duration</div>
    <div class="metric-value" style="color:#ef4444">38 days</div>
    <div class="metric-sub">DPA review blocking integration</div>
  </div>
  <div class="metric">
    <div class="metric-label">Avg Time to Production</div>
    <div class="metric-value">18 days</div>
    <div class="metric-sub">Across all active partners</div>
  </div>
  <div class="metric">
    <div class="metric-label">Self-Serve Rate</div>
    <div class="metric-value">71%</div>
    <div class="metric-sub">No support touchpoint needed</div>
  </div>
  <div class="metric">
    <div class="metric-label">Docs NPS</div>
    <div class="metric-value" style="color:#38bdf8">4.1 / 5</div>
    <div class="metric-sub">Partner documentation score</div>
  </div>
</div>

<div class="grid">

  <!-- SVG 1: 5-stage enablement funnel -->
  <div class="card">
    <h2>5-Stage Enablement Funnel</h2>
    <svg viewBox="0 0 460 310" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="310" fill="#0f172a" rx="8"/>

      <!-- Trapezoid funnel stages, top-wide to bottom-narrow -->
      <!-- Stage 1: Training  (widest) -->
      <polygon points="40,30  420,30  400,80  60,80"  fill="#1e3a5f" opacity="0.9"/>
      <text x="230" y="60" fill="#93c5fd" font-size="13" font-weight="600" text-anchor="middle">Training</text>
      <!-- Stage 2: Integration -->
      <polygon points="60,88  400,88  375,138  85,138" fill="#1e3a5f" opacity="0.8"/>
      <text x="230" y="118" fill="#93c5fd" font-size="13" font-weight="600" text-anchor="middle">Integration</text>
      <!-- Stage 3: Evaluation -->
      <polygon points="85,146  375,146  345,196  115,196" fill="#4c1d95" opacity="0.85"/>
      <text x="230" y="176" fill="#c4b5fd" font-size="13" font-weight="600" text-anchor="middle">Evaluation</text>
      <!-- Stage 4: Production -->
      <polygon points="115,204  345,204  310,254  150,254" fill="#14532d" opacity="0.85"/>
      <text x="230" y="234" fill="#86efac" font-size="13" font-weight="600" text-anchor="middle">Production</text>
      <!-- Stage 5: Expansion (narrowest) -->
      <polygon points="150,262  310,262  280,302  180,302" fill="#78350f" opacity="0.85"/>
      <text x="230" y="288" fill="#fcd34d" font-size="13" font-weight="600" text-anchor="middle">Expansion</text>

      <!-- Partner markers on right side -->
      <!-- PI: Production stage -->
      <circle cx="432" cy="229" r="6" fill="#22c55e"/>
      <text x="443" y="233" fill="#22c55e" font-size="10">PI</text>
      <!-- Machina: blocked at Integration -->
      <circle cx="432" cy="113" r="6" fill="#ef4444"/>
      <text x="443" y="117" fill="#ef4444" font-size="10">Machina</text>
      <!-- Apollo: Eval stage -->
      <circle cx="432" cy="171" r="6" fill="#c4b5fd"/>
      <text x="443" y="175" fill="#c4b5fd" font-size="10">Apollo</text>
      <!-- Nimbus: Integration -->
      <circle cx="432" cy="98" r="6" fill="#93c5fd"/>
      <text x="443" y="102" fill="#93c5fd" font-size="10">Nimbus</text>
      <!-- Apex: Expansion -->
      <circle cx="432" cy="282" r="6" fill="#fcd34d"/>
      <text x="443" y="286" fill="#fcd34d" font-size="10">Apex</text>
    </svg>
  </div>

  <!-- SVG 2: Days per stage bar chart (target vs actual) -->
  <div class="card">
    <h2>Days per Stage: Target vs Actual</h2>
    <svg viewBox="0 0 460 310" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="310" fill="#0f172a" rx="8"/>
      <!-- axes -->
      <line x1="80" y1="20" x2="80" y2="240" stroke="#334155" stroke-width="1.5"/>
      <line x1="80" y1="240" x2="445" y2="240" stroke="#334155" stroke-width="1.5"/>
      <!-- grid -->
      <line x1="80" y1="80"  x2="445" y2="80"  stroke="#1e293b" stroke-width="1"/>
      <line x1="80" y1="120" x2="445" y2="120" stroke="#1e293b" stroke-width="1"/>
      <line x1="80" y1="160" x2="445" y2="160" stroke="#1e293b" stroke-width="1"/>
      <line x1="80" y1="200" x2="445" y2="200" stroke="#1e293b" stroke-width="1"/>
      <!-- y labels: scale 0-50d; 240-20=220px / 50d = 4.4px per day -->
      <text x="74" y="84"  fill="#94a3b8" font-size="10" text-anchor="end">40d</text>
      <text x="74" y="124" fill="#94a3b8" font-size="10" text-anchor="end">30d</text>
      <text x="74" y="164" fill="#94a3b8" font-size="10" text-anchor="end">20d</text>
      <text x="74" y="204" fill="#94a3b8" font-size="10" text-anchor="end">10d</text>
      <text x="74" y="244" fill="#94a3b8" font-size="10" text-anchor="end">0d</text>

      <!-- Partners: PI, Machina, Apollo, Nimbus, Apex -->
      <!-- Group width ~72px each, bar width 28px each, gap 10px -->
      <!-- PI: target 10d actual 8d -->
      <rect x="90"  y="196" width="26" height="44" fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="118" y="204" width="26" height="36" fill="#22c55e" opacity="0.9" rx="3"/>
      <text x="107" y="255" fill="#94a3b8" font-size="9"  text-anchor="middle">PI</text>
      <text x="90"  y="193" fill="#38bdf8" font-size="9"  text-anchor="start">10d</text>
      <text x="118" y="201" fill="#22c55e" font-size="9"  text-anchor="start">8d</text>

      <!-- Machina: target 14d actual 38d (blocked) -->
      <rect x="160" y="178" width="26" height="62" fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="188" y="73"  width="26" height="167" fill="#ef4444" opacity="0.85" rx="3"/>
      <text x="177" y="255" fill="#94a3b8" font-size="9"  text-anchor="middle">Machina</text>
      <text x="160" y="175" fill="#38bdf8" font-size="9"  text-anchor="start">14d</text>
      <text x="188" y="70"  fill="#ef4444" font-size="9"  text-anchor="start">38d</text>

      <!-- Apollo: target 12d actual 19d -->
      <rect x="230" y="187" width="26" height="53" fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="258" y="156" width="26" height="84" fill="#f59e0b" opacity="0.85" rx="3"/>
      <text x="247" y="255" fill="#94a3b8" font-size="9"  text-anchor="middle">Apollo</text>
      <text x="230" y="184" fill="#38bdf8" font-size="9"  text-anchor="start">12d</text>
      <text x="258" y="153" fill="#f59e0b" font-size="9"  text-anchor="start">19d</text>

      <!-- Nimbus: target 10d actual 15d -->
      <rect x="300" y="196" width="26" height="44" fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="328" y="174" width="26" height="66" fill="#f59e0b" opacity="0.7" rx="3"/>
      <text x="317" y="255" fill="#94a3b8" font-size="9"  text-anchor="middle">Nimbus</text>
      <text x="300" y="193" fill="#38bdf8" font-size="9"  text-anchor="start">10d</text>
      <text x="328" y="171" fill="#f59e0b" font-size="9"  text-anchor="start">15d</text>

      <!-- Apex: target 20d actual 22d -->
      <rect x="370" y="152" width="26" height="88" fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="398" y="143" width="26" height="97" fill="#22c55e" opacity="0.75" rx="3"/>
      <text x="387" y="255" fill="#94a3b8" font-size="9"  text-anchor="middle">Apex</text>
      <text x="370" y="149" fill="#38bdf8" font-size="9"  text-anchor="start">20d</text>
      <text x="398" y="140" fill="#22c55e" font-size="9"  text-anchor="start">22d</text>

      <!-- legend -->
      <rect x="200" y="268" width="12" height="8" fill="#38bdf8" opacity="0.7" rx="2"/>
      <text x="215" y="276" fill="#94a3b8" font-size="10">Target</text>
      <rect x="270" y="268" width="12" height="8" fill="#22c55e" opacity="0.8" rx="2"/>
      <text x="285" y="276" fill="#94a3b8" font-size="10">Actual</text>
    </svg>
  </div>

  <!-- SVG 3: Support touchpoints heatmap (5 partners x 8 weeks) -->
  <div class="card" style="grid-column:1/-1">
    <h2>Support Touchpoints Heatmap (hours/week)</h2>
    <svg viewBox="0 0 460 220" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="220" fill="#0f172a" rx="8"/>

      <!-- Row labels: partners -->
      <text x="55" y="62"  fill="#e2e8f0" font-size="11" text-anchor="end">PI</text>
      <text x="55" y="90"  fill="#e2e8f0" font-size="11" text-anchor="end">Machina</text>
      <text x="55" y="118" fill="#e2e8f0" font-size="11" text-anchor="end">Apollo</text>
      <text x="55" y="146" fill="#e2e8f0" font-size="11" text-anchor="end">Nimbus</text>
      <text x="55" y="174" fill="#e2e8f0" font-size="11" text-anchor="end">Apex</text>

      <!-- Col labels: weeks -->
      <text x="75"  y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W1</text>
      <text x="113" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W2</text>
      <text x="151" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W3</text>
      <text x="189" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W4</text>
      <text x="227" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W5</text>
      <text x="265" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W6</text>
      <text x="303" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W7</text>
      <text x="341" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">W8</text>

      <!-- Color scale: 0h=dark, 2h=teal, 5h=amber, 8h+=red -->
      <!-- PI: onboarded fast, minimal support after W2 -->
      <!-- W1=4h W2=2h W3=0 W4=0 W5=1 W6=0 W7=0 W8=0 -->
      <rect x="58"  y="48" width="34" height="24" fill="#0e7490" opacity="0.8" rx="3"/><text x="75"  y="64" fill="#e2e8f0" font-size="9" text-anchor="middle">4h</text>
      <rect x="96"  y="48" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="113" y="64" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="134" y="48" width="34" height="24" fill="#1e293b" rx="3"/><text x="151" y="64" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="172" y="48" width="34" height="24" fill="#1e293b" rx="3"/><text x="189" y="64" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="210" y="48" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="227" y="64" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>
      <rect x="248" y="48" width="34" height="24" fill="#1e293b" rx="3"/><text x="265" y="64" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="286" y="48" width="34" height="24" fill="#1e293b" rx="3"/><text x="303" y="64" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="324" y="48" width="34" height="24" fill="#1e293b" rx="3"/><text x="341" y="64" fill="#475569" font-size="9" text-anchor="middle">0h</text>

      <!-- Machina: blocked, high support throughout -->
      <!-- W1=3 W2=5 W3=8 W4=8 W5=7 W6=6 W7=8 W8=6 -->
      <rect x="58"  y="76" width="34" height="24" fill="#0e7490" opacity="0.7" rx="3"/><text x="75"  y="92" fill="#e2e8f0" font-size="9" text-anchor="middle">3h</text>
      <rect x="96"  y="76" width="34" height="24" fill="#92400e" opacity="0.85" rx="3"/><text x="113" y="92" fill="#fcd34d" font-size="9" text-anchor="middle">5h</text>
      <rect x="134" y="76" width="34" height="24" fill="#7f1d1d" opacity="0.9" rx="3"/><text x="151" y="92" fill="#fca5a5" font-size="9" text-anchor="middle">8h</text>
      <rect x="172" y="76" width="34" height="24" fill="#7f1d1d" opacity="0.9" rx="3"/><text x="189" y="92" fill="#fca5a5" font-size="9" text-anchor="middle">8h</text>
      <rect x="210" y="76" width="34" height="24" fill="#7f1d1d" opacity="0.8" rx="3"/><text x="227" y="92" fill="#fca5a5" font-size="9" text-anchor="middle">7h</text>
      <rect x="248" y="76" width="34" height="24" fill="#92400e" opacity="0.85" rx="3"/><text x="265" y="92" fill="#fcd34d" font-size="9" text-anchor="middle">6h</text>
      <rect x="286" y="76" width="34" height="24" fill="#7f1d1d" opacity="0.9" rx="3"/><text x="303" y="92" fill="#fca5a5" font-size="9" text-anchor="middle">8h</text>
      <rect x="324" y="76" width="34" height="24" fill="#92400e" opacity="0.85" rx="3"/><text x="341" y="92" fill="#fcd34d" font-size="9" text-anchor="middle">6h</text>

      <!-- Apollo: moderate support mid-journey -->
      <!-- W1=2 W2=4 W3=5 W4=3 W5=2 W6=1 W7=0 W8=0 -->
      <rect x="58"  y="104" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="75"  y="120" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="96"  y="104" width="34" height="24" fill="#0e7490" opacity="0.8" rx="3"/><text x="113" y="120" fill="#e2e8f0" font-size="9" text-anchor="middle">4h</text>
      <rect x="134" y="104" width="34" height="24" fill="#92400e" opacity="0.7" rx="3"/><text x="151" y="120" fill="#fcd34d" font-size="9" text-anchor="middle">5h</text>
      <rect x="172" y="104" width="34" height="24" fill="#0e7490" opacity="0.7" rx="3"/><text x="189" y="120" fill="#e2e8f0" font-size="9" text-anchor="middle">3h</text>
      <rect x="210" y="104" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="227" y="120" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="248" y="104" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="265" y="120" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>
      <rect x="286" y="104" width="34" height="24" fill="#1e293b" rx="3"/><text x="303" y="120" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="324" y="104" width="34" height="24" fill="#1e293b" rx="3"/><text x="341" y="120" fill="#475569" font-size="9" text-anchor="middle">0h</text>

      <!-- Nimbus: low support, mostly self-serve -->
      <!-- W1=1 W2=2 W3=1 W4=0 W5=2 W6=1 W7=0 W8=1 -->
      <rect x="58"  y="132" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="75"  y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>
      <rect x="96"  y="132" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="113" y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="134" y="132" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="151" y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>
      <rect x="172" y="132" width="34" height="24" fill="#1e293b" rx="3"/><text x="189" y="148" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="210" y="132" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="227" y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="248" y="132" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="265" y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>
      <rect x="286" y="132" width="34" height="24" fill="#1e293b" rx="3"/><text x="303" y="148" fill="#475569" font-size="9" text-anchor="middle">0h</text>
      <rect x="324" y="132" width="34" height="24" fill="#0c4a6e" opacity="0.6" rx="3"/><text x="341" y="148" fill="#e2e8f0" font-size="9" text-anchor="middle">1h</text>

      <!-- Apex: moderate then grows (expansion support) -->
      <!-- W1=2 W2=3 W3=2 W4=4 W5=4 W6=5 W7=3 W8=4 -->
      <rect x="58"  y="160" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="75"  y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="96"  y="160" width="34" height="24" fill="#0e7490" opacity="0.7" rx="3"/><text x="113" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">3h</text>
      <rect x="134" y="160" width="34" height="24" fill="#164e63" opacity="0.8" rx="3"/><text x="151" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">2h</text>
      <rect x="172" y="160" width="34" height="24" fill="#0e7490" opacity="0.8" rx="3"/><text x="189" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">4h</text>
      <rect x="210" y="160" width="34" height="24" fill="#0e7490" opacity="0.8" rx="3"/><text x="227" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">4h</text>
      <rect x="248" y="160" width="34" height="24" fill="#92400e" opacity="0.7" rx="3"/><text x="265" y="176" fill="#fcd34d" font-size="9" text-anchor="middle">5h</text>
      <rect x="286" y="160" width="34" height="24" fill="#0e7490" opacity="0.7" rx="3"/><text x="303" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">3h</text>
      <rect x="324" y="160" width="34" height="24" fill="#0e7490" opacity="0.8" rx="3"/><text x="341" y="176" fill="#e2e8f0" font-size="9" text-anchor="middle">4h</text>

      <!-- color scale legend -->
      <text x="60"  y="210" fill="#475569" font-size="9">0h</text>
      <rect x="70"  y="202" width="20" height="8" fill="#1e293b" rx="2"/>
      <rect x="93"  y="202" width="20" height="8" fill="#164e63" opacity="0.8" rx="2"/>
      <rect x="116" y="202" width="20" height="8" fill="#0e7490" opacity="0.8" rx="2"/>
      <rect x="139" y="202" width="20" height="8" fill="#92400e" opacity="0.8" rx="2"/>
      <rect x="162" y="202" width="20" height="8" fill="#7f1d1d" opacity="0.9" rx="2"/>
      <text x="185" y="210" fill="#475569" font-size="9">8h+</text>
      <text x="210" y="210" fill="#64748b" font-size="9">(support hours per week)</text>
    </svg>
  </div>

</div>

<table class="partners-table">
  <thead>
    <tr>
      <th>Partner</th>
      <th>Current Stage</th>
      <th>Days Active</th>
      <th>Blocker</th>
      <th>Self-Serve</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>PI</strong></td>
      <td><span class="stage stage-production">Production</span></td>
      <td>8</td>
      <td style="color:#22c55e">None</td>
      <td>Yes</td>
    </tr>
    <tr>
      <td><strong>Machina</strong></td>
      <td><span class="stage stage-blocked">Blocked</span></td>
      <td>38</td>
      <td style="color:#ef4444">DPA review pending</td>
      <td>No</td>
    </tr>
    <tr>
      <td><strong>Apollo</strong></td>
      <td><span class="stage stage-eval">Evaluation</span></td>
      <td>19</td>
      <td style="color:#94a3b8">None</td>
      <td>Partial</td>
    </tr>
    <tr>
      <td><strong>Nimbus</strong></td>
      <td><span class="stage stage-integration">Integration</span></td>
      <td>15</td>
      <td style="color:#94a3b8">None</td>
      <td>Yes</td>
    </tr>
    <tr>
      <td><strong>Apex</strong></td>
      <td><span class="stage stage-production">Expansion</span></td>
      <td>22</td>
      <td style="color:#94a3b8">None</td>
      <td>Yes</td>
    </tr>
  </tbody>
</table>

<p style="color:#475569;font-size:.8rem;text-align:center">OCI Robot Cloud &mdash; Partner Enablement Tracker &mdash; Port 8615 &mdash; &copy; 2026 Oracle</p>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Partner Enablement Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_enablement_tracker", "port": 8615}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8615)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"partner_enablement_tracker","port":8615}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("Partner Enablement Tracker running on port 8615")
        HTTPServer(("0.0.0.0", 8615), Handler).serve_forever()
