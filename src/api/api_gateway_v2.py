#!/usr/bin/env python3
"""
api_gateway_v2.py — port 8633
API Gateway v2 dashboard for OCI Robot Cloud.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="API Gateway v2", version="2.0.0")

    HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>API Gateway v2 — Port 8633</title>
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

<h1>API Gateway v2</h1>
<p class="subtitle">Port 8633 &mdash; Multi-region load balancing, SLA enforcement, and circuit breaking</p>

<div class="grid">

  <!-- SVG 1: Request Routing Flow Diagram -->
  <div class="card full">
    <h2>Request Routing Flow (Load Balancer &#x2192; Regions &#x2192; Model Servers)</h2>
    <svg viewBox="0 0 800 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="800" height="300" fill="#0f172a" rx="6"/>

      <!-- Tier 1: Load Balancer -->
      <rect x="330" y="20" width="140" height="44" rx="8" fill="#1e3a5f" stroke="#38bdf8" stroke-width="2"/>
      <text x="400" y="38" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">Load Balancer</text>
      <text x="400" y="54" fill="#64748b" font-size="9" text-anchor="middle">26,100 req/day</text>

      <!-- Tier 2: Region Nodes -->
      <rect x="60"  y="110" width="120" height="44" rx="8" fill="#1e293b" stroke="#818cf8" stroke-width="1.5"/>
      <text x="120" y="128" fill="#818cf8" font-size="11" text-anchor="middle" font-weight="600">us-east-1</text>
      <text x="120" y="144" fill="#64748b" font-size="9"  text-anchor="middle">~11k req/day</text>

      <rect x="330" y="110" width="120" height="44" rx="8" fill="#1e293b" stroke="#818cf8" stroke-width="1.5"/>
      <text x="390" y="128" fill="#818cf8" font-size="11" text-anchor="middle" font-weight="600">us-west-2</text>
      <text x="390" y="144" fill="#64748b" font-size="9"  text-anchor="middle">~9k req/day</text>

      <rect x="600" y="110" width="120" height="44" rx="8" fill="#1e293b" stroke="#818cf8" stroke-width="1.5"/>
      <text x="660" y="128" fill="#818cf8" font-size="11" text-anchor="middle" font-weight="600">eu-west-1</text>
      <text x="660" y="144" fill="#64748b" font-size="9"  text-anchor="middle">~6k req/day</text>

      <!-- Arrows LB to regions (thickness = volume) -->
      <line x1="370" y1="64" x2="175" y2="110" stroke="#38bdf8" stroke-width="3.5" opacity="0.7"/>
      <line x1="400" y1="64" x2="390" y2="110" stroke="#38bdf8" stroke-width="2.5" opacity="0.7"/>
      <line x1="430" y1="64" x2="605" y2="110" stroke="#38bdf8" stroke-width="1.5" opacity="0.7"/>
      <polygon points="175,110 168,98 182,98" fill="#38bdf8" opacity="0.7"/>
      <polygon points="390,110 383,98 397,98" fill="#38bdf8" opacity="0.7"/>
      <polygon points="605,110 598,98 612,98" fill="#38bdf8" opacity="0.7"/>

      <!-- Tier 3: us-east servers -->
      <rect x="20"  y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="55"  y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">gr00t-a</text>
      <text x="55"  y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8001</text>
      <rect x="100" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="135" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">gr00t-b</text>
      <text x="135" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8002</text>
      <rect x="180" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="215" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">openvla-a</text>
      <text x="215" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8010</text>
      <rect x="260" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="295" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">openvla-b</text>
      <text x="295" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8011</text>
      <line x1="100" y1="154" x2="55"  y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="110" y1="154" x2="135" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="130" y1="154" x2="215" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="140" y1="154" x2="295" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>

      <!-- Tier 3: us-west servers -->
      <rect x="340" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="375" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">gr00t-c</text>
      <text x="375" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8003</text>
      <rect x="420" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="455" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">gr00t-d</text>
      <text x="455" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8004</text>
      <rect x="500" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="535" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">openvla-c</text>
      <text x="535" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8012</text>
      <rect x="580" y="210" width="70" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="615" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">openvla-d</text>
      <text x="615" y="236" fill="#64748b" font-size="8"  text-anchor="middle">port 8013</text>
      <line x1="370" y1="154" x2="375" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="380" y1="154" x2="455" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="400" y1="154" x2="535" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="410" y1="154" x2="615" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>

      <!-- Tier 3: eu-west servers -->
      <rect x="660" y="210" width="60" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="690" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">gr00t-eu</text>
      <text x="690" y="236" fill="#64748b" font-size="8"  text-anchor="middle">8005</text>
      <rect x="728" y="210" width="60" height="34" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
      <text x="758" y="224" fill="#94a3b8" font-size="9"  text-anchor="middle">ovla-eu</text>
      <text x="758" y="236" fill="#64748b" font-size="8"  text-anchor="middle">8014</text>
      <line x1="650" y1="154" x2="690" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>
      <line x1="670" y1="154" x2="758" y2="210" stroke="#818cf8" stroke-width="1" opacity="0.5"/>

      <!-- Tier labels -->
      <text x="12" y="16" fill="#475569" font-size="9">Tier 1</text>
      <text x="12" y="116" fill="#475569" font-size="9">Tier 2</text>
      <text x="12" y="206" fill="#475569" font-size="9">Tier 3</text>

      <!-- Legend -->
      <line x1="620" y1="275" x2="650" y2="275" stroke="#38bdf8" stroke-width="3.5"/>
      <text x="655" y="279" fill="#64748b" font-size="9">high vol</text>
      <line x1="700" y1="275" x2="730" y2="275" stroke="#38bdf8" stroke-width="1.5"/>
      <text x="735" y="279" fill="#64748b" font-size="9">low vol</text>
    </svg>
  </div>

  <!-- SVG 2: API Latency Heatmap -->
  <div class="card">
    <h2>API Latency Heatmap (p99, 5 endpoints x 24h)</h2>
    <svg viewBox="0 0 440 260" xmlns="http://www.w3.org/2000/svg">
      <rect width="440" height="260" fill="#0f172a" rx="6"/>

      <text x="105" y="38"  fill="#94a3b8" font-size="9" text-anchor="end">/infer</text>
      <text x="105" y="66"  fill="#94a3b8" font-size="9" text-anchor="end">/health</text>
      <text x="105" y="94"  fill="#94a3b8" font-size="9" text-anchor="end">/train</text>
      <text x="105" y="122" fill="#94a3b8" font-size="9" text-anchor="end">/eval</text>
      <text x="105" y="150" fill="#94a3b8" font-size="9" text-anchor="end">/metrics</text>

      <text x="110" y="170" fill="#64748b" font-size="8" text-anchor="middle">0</text>
      <text x="166" y="170" fill="#64748b" font-size="8" text-anchor="middle">4</text>
      <text x="222" y="170" fill="#64748b" font-size="8" text-anchor="middle">8</text>
      <text x="278" y="170" fill="#64748b" font-size="8" text-anchor="middle">12</text>
      <text x="334" y="170" fill="#64748b" font-size="8" text-anchor="middle">16</text>
      <text x="390" y="170" fill="#64748b" font-size="8" text-anchor="middle">20</text>

      <!-- /infer row -->
      <rect x="110" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="124" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="138" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="152" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="166" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="180" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="194" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="208" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="222" y="20" width="13" height="22" rx="1" fill="#0369a1"/><rect x="236" y="20" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="250" y="20" width="13" height="22" rx="1" fill="#C74634"/><rect x="264" y="20" width="13" height="22" rx="1" fill="#7f1d1d"/>
      <rect x="278" y="20" width="13" height="22" rx="1" fill="#7f1d1d"/><rect x="292" y="20" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="306" y="20" width="13" height="22" rx="1" fill="#C74634"/><rect x="320" y="20" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="334" y="20" width="13" height="22" rx="1" fill="#C74634"/><rect x="348" y="20" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="362" y="20" width="13" height="22" rx="1" fill="#0369a1"/><rect x="376" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="390" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="404" y="20" width="13" height="22" rx="1" fill="#1e3a5f"/>

      <!-- /health row -->
      <rect x="110" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="124" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="138" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="152" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="166" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="180" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="194" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="208" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="222" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="236" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="250" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="264" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="278" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="292" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="306" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="320" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="334" y="48" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="348" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="362" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="376" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="390" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="404" y="48" width="13" height="22" rx="1" fill="#0f2b4a"/>

      <!-- /train row -->
      <rect x="110" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="124" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="138" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="152" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="166" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="180" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="194" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="208" y="76" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="222" y="76" width="13" height="22" rx="1" fill="#C74634"/><rect x="236" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/>
      <rect x="250" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/><rect x="264" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/>
      <rect x="278" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/><rect x="292" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/>
      <rect x="306" y="76" width="13" height="22" rx="1" fill="#7f1d1d"/><rect x="320" y="76" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="334" y="76" width="13" height="22" rx="1" fill="#C74634"/><rect x="348" y="76" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="362" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="376" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="390" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="404" y="76" width="13" height="22" rx="1" fill="#1e3a5f"/>

      <!-- /eval row -->
      <rect x="110" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="124" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="138" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="152" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="166" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="180" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="194" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="208" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="222" y="104" width="13" height="22" rx="1" fill="#0369a1"/><rect x="236" y="104" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="250" y="104" width="13" height="22" rx="1" fill="#C74634"/><rect x="264" y="104" width="13" height="22" rx="1" fill="#7f1d1d"/>
      <rect x="278" y="104" width="13" height="22" rx="1" fill="#C74634"/><rect x="292" y="104" width="13" height="22" rx="1" fill="#C74634"/>
      <rect x="306" y="104" width="13" height="22" rx="1" fill="#C74634"/><rect x="320" y="104" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="334" y="104" width="13" height="22" rx="1" fill="#0369a1"/><rect x="348" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="362" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="376" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="390" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="404" y="104" width="13" height="22" rx="1" fill="#1e3a5f"/>

      <!-- /metrics row -->
      <rect x="110" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="124" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="138" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="152" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="166" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="180" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="194" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="208" y="132" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="222" y="132" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="236" y="132" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="250" y="132" width="13" height="22" rx="1" fill="#0369a1"/><rect x="264" y="132" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="278" y="132" width="13" height="22" rx="1" fill="#0369a1"/><rect x="292" y="132" width="13" height="22" rx="1" fill="#0369a1"/>
      <rect x="306" y="132" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="320" y="132" width="13" height="22" rx="1" fill="#1e3a5f"/>
      <rect x="334" y="132" width="13" height="22" rx="1" fill="#1e3a5f"/><rect x="348" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="362" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="376" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>
      <rect x="390" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/><rect x="404" y="132" width="13" height="22" rx="1" fill="#0f2b4a"/>

      <!-- Color legend -->
      <rect x="110" y="185" width="12" height="10" rx="2" fill="#0f2b4a"/>
      <text x="126" y="194" fill="#64748b" font-size="8">&lt;5ms</text>
      <rect x="160" y="185" width="12" height="10" rx="2" fill="#1e3a5f"/>
      <text x="176" y="194" fill="#64748b" font-size="8">5-40ms</text>
      <rect x="220" y="185" width="12" height="10" rx="2" fill="#0369a1"/>
      <text x="236" y="194" fill="#64748b" font-size="8">40-80ms</text>
      <rect x="290" y="185" width="12" height="10" rx="2" fill="#C74634"/>
      <text x="306" y="194" fill="#64748b" font-size="8">80-150ms</text>
      <rect x="360" y="185" width="12" height="10" rx="2" fill="#7f1d1d"/>
      <text x="376" y="194" fill="#64748b" font-size="8">&gt;150ms</text>
      <text x="220" y="215" fill="#475569" font-size="9" text-anchor="middle">p99 latency heatmap -- peak hours 9:00-18:00 UTC</text>
    </svg>
  </div>

  <!-- SVG 3: SLA Compliance Gauge Trio -->
  <div class="card">
    <h2>SLA Compliance Gauges (3 Tiers)</h2>
    <svg viewBox="0 0 440 260" xmlns="http://www.w3.org/2000/svg">
      <rect width="440" height="260" fill="#0f172a" rx="6"/>

      <!-- BASIC GAUGE (cx=80, cy=160, R=55) -->
      <path d="M 25 160 A 55 55 0 0 1 135 160" fill="none" stroke="#334155" stroke-width="14" stroke-linecap="round"/>
      <path d="M 25 160 A 55 55 0 0 1 134.1 149.7" fill="none" stroke="#34d399" stroke-width="14" stroke-linecap="round"/>
      <circle cx="80" cy="160" r="40" fill="#0f172a"/>
      <text x="80" y="152" fill="#34d399" font-size="13" text-anchor="middle" font-weight="700">99.97%</text>
      <text x="80" y="166" fill="#94a3b8" font-size="8"  text-anchor="middle">SLA met</text>
      <text x="80" y="192" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Basic</text>
      <text x="80" y="206" fill="#64748b" font-size="9"  text-anchor="middle">&#x2265;99.9% target</text>

      <!-- PRO GAUGE (cx=220, cy=160, R=55) -->
      <path d="M 165 160 A 55 55 0 0 1 275 160" fill="none" stroke="#334155" stroke-width="14" stroke-linecap="round"/>
      <path d="M 165 160 A 55 55 0 0 1 271.2 139.7" fill="none" stroke="#38bdf8" stroke-width="14" stroke-linecap="round"/>
      <circle cx="220" cy="160" r="40" fill="#0f172a"/>
      <text x="220" y="152" fill="#38bdf8" font-size="13" text-anchor="middle" font-weight="700">99.94%</text>
      <text x="220" y="166" fill="#94a3b8" font-size="8"  text-anchor="middle">SLA met</text>
      <text x="220" y="192" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Pro</text>
      <text x="220" y="206" fill="#64748b" font-size="9"  text-anchor="middle">&#x2265;99.95% target</text>

      <!-- ENTERPRISE GAUGE (cx=360, cy=160, R=55) -->
      <path d="M 305 160 A 55 55 0 0 1 415 160" fill="none" stroke="#334155" stroke-width="14" stroke-linecap="round"/>
      <path d="M 305 160 A 55 55 0 0 1 349.7 106.9" fill="none" stroke="#f59e0b" stroke-width="14" stroke-linecap="round"/>
      <circle cx="360" cy="160" r="40" fill="#0f172a"/>
      <text x="360" y="152" fill="#f59e0b" font-size="13" text-anchor="middle" font-weight="700">99.72%</text>
      <text x="360" y="166" fill="#f87171" font-size="8"  text-anchor="middle">below target</text>
      <text x="360" y="192" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Enterprise</text>
      <text x="360" y="206" fill="#64748b" font-size="9"  text-anchor="middle">&#x2265;99.99% target</text>

      <!-- Scale labels -->
      <text x="25"  y="174" fill="#475569" font-size="8">99.5%</text>
      <text x="112" y="174" fill="#475569" font-size="8">100%</text>
      <text x="165" y="174" fill="#475569" font-size="8">99.5%</text>
      <text x="252" y="174" fill="#475569" font-size="8">100%</text>
      <text x="305" y="174" fill="#475569" font-size="8">99.5%</text>
      <text x="392" y="174" fill="#475569" font-size="8">100%</text>
      <text x="220" y="240" fill="#475569" font-size="9" text-anchor="middle">Gauges scaled 99.5%-100% for visual contrast. Last 30 days.</text>
    </svg>
  </div>

</div>

<div class="card">
  <h2>Gateway Metrics</h2>
  <div class="metrics">
    <div class="metric">
      <div class="val">26,100</div>
      <div class="lbl">Requests / day</div>
    </div>
    <div class="metric">
      <div class="val">1.2ms</div>
      <div class="lbl">Gateway overhead</div>
    </div>
    <div class="metric">
      <div class="val">3</div>
      <div class="lbl">Circuit breaker trips (30d)</div>
    </div>
    <div class="metric">
      <div class="val">70%</div>
      <div class="lbl">Auto-scale trigger threshold</div>
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
            "service": "api_gateway_v2",
            "port": 8633,
            "metrics": {
                "requests_per_day": 26100,
                "gateway_overhead_ms": 1.2,
                "circuit_breaker_trips_30d": 3,
                "autoscale_threshold_pct": 70,
                "sla": {
                    "basic_pct": 99.97,
                    "pro_pct": 99.94,
                    "enterprise_pct": 99.72,
                },
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8633)

except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "api_gateway_v2", "port": 8633}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = b"<h1>api_gateway_v2 (port 8633)</h1><p>Install fastapi + uvicorn for full UI.</p>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI not available -- starting stdlib fallback on port 8633")
        HTTPServer(("0.0.0.0", 8633), Handler).serve_forever()
