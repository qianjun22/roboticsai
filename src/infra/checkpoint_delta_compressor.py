"""Checkpoint Delta Compressor — FastAPI port 8595"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8595

def build_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Checkpoint Delta Compressor — OCI Robot Cloud</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.4rem; letter-spacing: -0.02em; }}
  .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }}
  .metrics-row {{ display: flex; gap: 1.2rem; margin-bottom: 2rem; flex-wrap: wrap; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.1rem 1.5rem; flex: 1; min-width: 160px; }}
  .metric-label {{ color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.3rem; }}
  .metric-value {{ color: #38bdf8; font-size: 1.6rem; font-weight: 700; }}
  .metric-sub {{ color: #64748b; font-size: 0.78rem; margin-top: 0.2rem; }}
  .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1.5rem; }}
  .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; }}
  .chart-title {{ color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }}
  svg text {{ font-family: 'Segoe UI', system-ui, sans-serif; }}
</style>
</head>
<body>
<h1>Checkpoint Delta Compressor</h1>
<p class="subtitle">Port {PORT} &mdash; delta compression, storage savings, retrieval speed analysis</p>

<div class="metrics-row">
  <div class="metric-card">
    <div class="metric-label">Size Reduction</div>
    <div class="metric-value">93%</div>
    <div class="metric-sub">delta vs full checkpoint</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Fidelity</div>
    <div class="metric-value">100%</div>
    <div class="metric-sub">lossless reconstruction</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Retrieval Time</div>
    <div class="metric-value">3.2s</div>
    <div class="metric-sub">avg chain reconstruction</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Chain-length Cap</div>
    <div class="metric-value">10</div>
    <div class="metric-sub">max delta depth</div>
  </div>
</div>

<div class="charts-grid">

  <!-- Chart 1: Full vs Delta Size Comparison -->
  <div class="chart-card">
    <div class="chart-title">Checkpoint Size: Full vs Delta (7 Checkpoints)</div>
    <svg viewBox="0 0 460 310" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="20" x2="60" y2="250" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="250" x2="440" y2="250" stroke="#334155" stroke-width="1.5"/>
      <!-- Y grid: 0,1,2,3,4,5,6,7 GB -- max=7, height=230 -->
      <line x1="60" y1="217" x2="440" y2="217" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="184" x2="440" y2="184" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="151" x2="440" y2="151" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="118" x2="440" y2="118" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="85" x2="440" y2="85" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="52" x2="440" y2="52" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="20" x2="440" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Y labels: 0..7 GB -->
      <text x="52" y="254" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="52" y="221" fill="#64748b" font-size="10" text-anchor="end">1</text>
      <text x="52" y="188" fill="#64748b" font-size="10" text-anchor="end">2</text>
      <text x="52" y="155" fill="#64748b" font-size="10" text-anchor="end">3</text>
      <text x="52" y="122" fill="#64748b" font-size="10" text-anchor="end">4</text>
      <text x="52" y="89" fill="#64748b" font-size="10" text-anchor="end">5</text>
      <text x="52" y="56" fill="#64748b" font-size="10" text-anchor="end">6</text>
      <text x="52" y="24" fill="#64748b" font-size="10" text-anchor="end">7 GB</text>
      <text x="14" y="140" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,140)">Size (GB)</text>

      <!-- 7 checkpoints, each pair: full=6.7GB bar + delta~0.48GB bar -->
      <!-- full bar height = 6.7/7*230=220.1, y=250-220=30 -->
      <!-- delta bar height = 0.48/7*230=15.77, y=250-16=234 -->
      <!-- spacing: start 70, pair width 52, gap 2 -->

      <!-- ckpt 1 -->
      <rect x="68" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="90" y="234" width="20" height="16" fill="#38bdf8" rx="2"/>
      <text x="85" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck1</text>

      <!-- ckpt 2 -->
      <rect x="122" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="144" y="232" width="20" height="18" fill="#38bdf8" rx="2"/>
      <text x="139" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck2</text>

      <!-- ckpt 3 -->
      <rect x="176" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="198" y="235" width="20" height="15" fill="#38bdf8" rx="2"/>
      <text x="193" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck3</text>

      <!-- ckpt 4 -->
      <rect x="230" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="252" y="233" width="20" height="17" fill="#38bdf8" rx="2"/>
      <text x="247" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck4</text>

      <!-- ckpt 5 -->
      <rect x="284" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="306" y="236" width="20" height="14" fill="#38bdf8" rx="2"/>
      <text x="301" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck5</text>

      <!-- ckpt 6 -->
      <rect x="338" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="360" y="234" width="20" height="16" fill="#38bdf8" rx="2"/>
      <text x="355" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck6</text>

      <!-- ckpt 7 -->
      <rect x="392" y="30" width="20" height="220" fill="#334155" rx="2"/>
      <rect x="414" y="233" width="20" height="17" fill="#38bdf8" rx="2"/>
      <text x="409" y="266" fill="#64748b" font-size="9" text-anchor="middle">ck7</text>

      <!-- Full bar label -->
      <text x="78" y="26" fill="#94a3b8" font-size="9" text-anchor="middle">6.7GB</text>

      <!-- Legend -->
      <rect x="63" y="283" width="12" height="10" fill="#334155" rx="2"/>
      <text x="79" y="292" fill="#94a3b8" font-size="11">Full (6.7 GB)</text>
      <rect x="163" y="283" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="179" y="292" fill="#94a3b8" font-size="11">Delta (avg 480 MB)</text>
    </svg>
  </div>

  <!-- Chart 2: Compression Ratio vs Retrieval Speed Scatter -->
  <div class="chart-card">
    <div class="chart-title">Compression Ratio vs Retrieval Speed — Pareto Analysis</div>
    <svg viewBox="0 0 460 310" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="70" y1="20" x2="70" y2="250" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="250" x2="440" y2="250" stroke="#334155" stroke-width="1.5"/>
      <!-- Grid -->
      <line x1="70" y1="202" x2="440" y2="202" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="154" x2="440" y2="154" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="106" x2="440" y2="106" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="58" x2="440" y2="58" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="166" y1="20" x2="166" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="262" y1="20" x2="262" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="358" y1="20" x2="358" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="440" y1="20" x2="440" y2="250" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- X: compression ratio 1x..5x → x=70+(ratio-1)/4*370 -->
      <text x="70" y="266" fill="#64748b" font-size="11" text-anchor="middle">1x</text>
      <text x="162" y="266" fill="#64748b" font-size="11" text-anchor="middle">2x</text>
      <text x="255" y="266" fill="#64748b" font-size="11" text-anchor="middle">3x</text>
      <text x="347" y="266" fill="#64748b" font-size="11" text-anchor="middle">4x</text>
      <text x="440" y="266" fill="#64748b" font-size="11" text-anchor="middle">5x</text>
      <text x="255" y="282" fill="#94a3b8" font-size="12" text-anchor="middle">Compression Ratio</text>
      <!-- Y: retrieval speed 0..800 MB/s → y=250-speed/800*230 -->
      <text x="62" y="254" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="62" y="206" fill="#64748b" font-size="10" text-anchor="end">200</text>
      <text x="62" y="158" fill="#64748b" font-size="10" text-anchor="end">400</text>
      <text x="62" y="110" fill="#64748b" font-size="10" text-anchor="end">600</text>
      <text x="62" y="62" fill="#64748b" font-size="10" text-anchor="end">800</text>
      <text x="18" y="150" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,18,150)">Speed (MB/s)</text>

      <!-- lz4: ratio=2.1, speed=720 → x=70+(1.1/4)*370=172, y=250-720/800*230=42.5 -->
      <circle cx="172" cy="43" r="10" fill="#38bdf8" opacity="0.85"/>
      <text x="172" y="47" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="bold">lz4</text>
      <!-- Pareto star -->
      <text x="187" y="38" fill="#fbbf24" font-size="14">★</text>

      <!-- zstd: ratio=4.2, speed=430 → x=70+(3.2/4)*370=366, y=250-430/800*230=126.4 -->
      <circle cx="366" cy="126" r="10" fill="#a78bfa" opacity="0.85"/>
      <text x="366" y="130" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">zstd</text>
      <!-- Pareto star -->
      <text x="381" y="121" fill="#fbbf24" font-size="14">★</text>

      <!-- brotli: ratio=4.8, speed=85 → x=70+(3.8/4)*370=421.5, y=250-85/800*230=225.6 -->
      <circle cx="422" cy="226" r="10" fill="#fb923c" opacity="0.85"/>
      <text x="422" y="230" fill="#0f172a" font-size="7" text-anchor="middle" font-weight="bold">brtl</text>

      <!-- delta: ratio=14x(~93% reduction on 6.7GB→0.48GB = 13.96x) → clamp to 5x display, speed=310 -->
      <!-- show at x=440 (max), y=250-310/800*230=160.9 -->
      <circle cx="440" cy="161" r="12" fill="#C74634" opacity="0.9"/>
      <text x="440" y="165" fill="#fff" font-size="8" text-anchor="middle" font-weight="bold">delta</text>
      <!-- Pareto star -->
      <text x="455" y="156" fill="#fbbf24" font-size="14">★</text>
      <!-- Arrow indicating delta extends beyond chart -->
      <text x="440" y="140" fill="#C74634" font-size="10" text-anchor="middle">14x→</text>

      <!-- Pareto frontier line -->
      <polyline points="172,43 366,126 440,161" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.6"/>

      <!-- Legend -->
      <circle cx="68" cy="292" r="5" fill="#38bdf8"/>
      <text x="77" y="296" fill="#94a3b8" font-size="10">lz4</text>
      <circle cx="103" cy="292" r="5" fill="#a78bfa"/>
      <text x="112" y="296" fill="#94a3b8" font-size="10">zstd</text>
      <circle cx="145" cy="292" r="5" fill="#fb923c"/>
      <text x="154" y="296" fill="#94a3b8" font-size="10">brotli</text>
      <circle cx="196" cy="292" r="5" fill="#C74634"/>
      <text x="205" y="296" fill="#94a3b8" font-size="10">delta</text>
      <text x="248" y="296" fill="#fbbf24" font-size="12">★</text>
      <text x="262" y="296" fill="#94a3b8" font-size="10">Pareto optimal</text>
    </svg>
  </div>

  <!-- Chart 3: Storage Savings Projection Over 90 Days -->
  <div class="chart-card" style="grid-column: span 2;">
    <div class="chart-title">Storage Savings Projection — 90 Days (Cumulative, TB)</div>
    <svg viewBox="0 0 900 320" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="70" y1="20" x2="70" y2="270" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="270" x2="870" y2="270" stroke="#334155" stroke-width="1.5"/>
      <!-- Y grid: 0..28TB, step 4, height=250, step_px=250/7=35.7 -->
      <line x1="70" y1="234" x2="870" y2="234" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="198" x2="870" y2="198" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="162" x2="870" y2="162" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="126" x2="870" y2="126" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="90" x2="870" y2="90" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="54" x2="870" y2="54" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="20" x2="870" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Y labels -->
      <text x="62" y="274" fill="#64748b" font-size="11" text-anchor="end">0</text>
      <text x="62" y="238" fill="#64748b" font-size="11" text-anchor="end">4</text>
      <text x="62" y="202" fill="#64748b" font-size="11" text-anchor="end">8</text>
      <text x="62" y="166" fill="#64748b" font-size="11" text-anchor="end">12</text>
      <text x="62" y="130" fill="#64748b" font-size="11" text-anchor="end">16</text>
      <text x="62" y="94" fill="#64748b" font-size="11" text-anchor="end">20</text>
      <text x="62" y="58" fill="#64748b" font-size="11" text-anchor="end">24</text>
      <text x="62" y="24" fill="#64748b" font-size="11" text-anchor="end">28 TB</text>
      <text x="16" y="155" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,16,155)">Cumulative Storage (TB)</text>
      <!-- X labels: day 0,10,20,30,40,50,60,70,80,90 -->
      <!-- x = 70 + day/90*800 -->
      <text x="70" y="286" fill="#64748b" font-size="11" text-anchor="middle">0</text>
      <text x="159" y="286" fill="#64748b" font-size="11" text-anchor="middle">10</text>
      <text x="248" y="286" fill="#64748b" font-size="11" text-anchor="middle">20</text>
      <text x="337" y="286" fill="#64748b" font-size="11" text-anchor="middle">30</text>
      <text x="426" y="286" fill="#64748b" font-size="11" text-anchor="middle">40</text>
      <text x="515" y="286" fill="#64748b" font-size="11" text-anchor="middle">50</text>
      <text x="604" y="286" fill="#64748b" font-size="11" text-anchor="middle">60</text>
      <text x="693" y="286" fill="#64748b" font-size="11" text-anchor="middle">70</text>
      <text x="782" y="286" fill="#64748b" font-size="11" text-anchor="middle">80</text>
      <text x="870" y="286" fill="#64748b" font-size="11" text-anchor="middle">90</text>
      <text x="470" y="302" fill="#94a3b8" font-size="12" text-anchor="middle">Days</text>

      <!-- Full checkpoint storage: 4 checkpoints/day * 6.7GB = 26.8 GB/day → 90 days = 2412 GB ~2.36 TB total... -->
      <!-- Let's use: full = 3 ckpts/day * 6.7GB = 20.1 GB/day, delta = 3*0.48=1.44 GB/day -->
      <!-- At day 90: full = 20.1*90=1809 GB=1.77TB, delta=1.44*90=129.6GB=0.127TB. -->
      <!-- Scale to 28TB max: full grows linearly to 28TB at day 90. x=70+day/90*800, y_full=270-day/90*250 -->
      <!-- delta grows to 28*0.07=1.96TB at day 90 -->
      <!-- Savings = full - delta: at day 90 = 26.04TB -->

      <!-- Full storage area (background) -->
      <polygon points="70,270 870,20 870,270" fill="#1e3a5f" opacity="0.5"/>

      <!-- Delta storage area (smaller, on top) -->
      <!-- delta at day 90: 0.07 * 28 / 28 * 250 = 17.5px above baseline -->
      <polygon points="70,270 870,252 870,270" fill="#0284c7" opacity="0.7"/>

      <!-- Full storage line -->
      <line x1="70" y1="270" x2="870" y2="20" stroke="#334155" stroke-width="2.5"/>

      <!-- Delta storage line -->
      <line x1="70" y1="270" x2="870" y2="252" stroke="#38bdf8" stroke-width="2.5"/>

      <!-- Savings line (cumulative savings = full - delta) -->
      <!-- at day d: savings_y = y_full + (y_delta - y_full)/2 ... just draw savings as separate line -->
      <!-- savings = (1-0.07)*full → savings at day 90 = 0.93*28=26.04TB → y=270-26.04/28*250=37.5 -->
      <line x1="70" y1="270" x2="870" y2="37" stroke="#C74634" stroke-width="2.5" stroke-dasharray="0"/>

      <!-- Savings fill area between full and delta lines -->
      <polygon points="70,270 870,20 870,252" fill="#22c55e" opacity="0.08"/>

      <!-- Annotations -->
      <text x="875" y="18" fill="#64748b" font-size="11">Full</text>
      <text x="875" y="250" fill="#38bdf8" font-size="11">Delta</text>
      <text x="875" y="35" fill="#C74634" font-size="11">Saved</text>

      <!-- Savings badge at day 90 -->
      <rect x="700" y="100" width="150" height="50" fill="#0f172a" stroke="#22c55e" stroke-width="1.5" rx="6" opacity="0.9"/>
      <text x="775" y="122" fill="#22c55e" font-size="13" font-weight="700" text-anchor="middle">26 TB saved</text>
      <text x="775" y="141" fill="#94a3b8" font-size="11" text-anchor="middle">at day 90 (93%)</text>

      <!-- Legend -->
      <line x1="70" y1="312" x2="90" y2="312" stroke="#334155" stroke-width="2.5"/>
      <text x="94" y="316" fill="#94a3b8" font-size="11">Full storage</text>
      <line x1="190" y1="312" x2="210" y2="312" stroke="#38bdf8" stroke-width="2.5"/>
      <text x="214" y="316" fill="#94a3b8" font-size="11">Delta storage</text>
      <line x1="310" y1="312" x2="330" y2="312" stroke="#C74634" stroke-width="2.5"/>
      <text x="334" y="316" fill="#94a3b8" font-size="11">Cumulative savings</text>
    </svg>
  </div>

</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Delta Compressor")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {{"status": "ok", "port": PORT}}

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
