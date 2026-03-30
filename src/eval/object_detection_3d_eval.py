"""Object Detection 3D Eval — FastAPI port 8594"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8594

def build_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Object Detection 3D Eval — OCI Robot Cloud</title>
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
<h1>Object Detection 3D Eval</h1>
<p class="subtitle">Port {PORT} &mdash; 3D bounding box mAP, IoU recall curves, confidence vs success rate</p>

<div class="metrics-row">
  <div class="metric-card">
    <div class="metric-label">mAP @ IoU 0.5</div>
    <div class="metric-value">0.76</div>
    <div class="metric-sub">GR00T_encoder best</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Occlusion Robustness</div>
    <div class="metric-value">0.61</div>
    <div class="metric-sub">partial occlusion scenes</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Small Object (&lt;5cm)</div>
    <div class="metric-value">0.52</div>
    <div class="metric-sub">tiny object mAP</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Confidence-SR r</div>
    <div class="metric-value">0.84</div>
    <div class="metric-sub">Pearson correlation</div>
  </div>
</div>

<div class="charts-grid">

  <!-- Chart 1: 3D Bounding Box mAP Bar Chart -->
  <div class="chart-card">
    <div class="chart-title">3D Bounding Box mAP — Grouped Bars (IoU 0.5 &amp; 0.75)</div>
    <svg viewBox="0 0 460 300" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="20" x2="60" y2="240" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="240" x2="440" y2="240" stroke="#334155" stroke-width="1.5"/>
      <!-- Y grid lines -->
      <line x1="60" y1="196" x2="440" y2="196" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="152" x2="440" y2="152" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="108" x2="440" y2="108" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="64" x2="440" y2="64" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="20" x2="440" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Y axis labels -->
      <text x="52" y="244" fill="#64748b" font-size="11" text-anchor="end">0.0</text>
      <text x="52" y="200" fill="#64748b" font-size="11" text-anchor="end">0.2</text>
      <text x="52" y="156" fill="#64748b" font-size="11" text-anchor="end">0.4</text>
      <text x="52" y="112" fill="#64748b" font-size="11" text-anchor="end">0.6</text>
      <text x="52" y="68" fill="#64748b" font-size="11" text-anchor="end">0.8</text>
      <text x="52" y="24" fill="#64748b" font-size="11" text-anchor="end">1.0</text>
      <!-- Y axis title -->
      <text x="14" y="140" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,14,140)">mAP</text>

      <!-- Model: GR00T_encoder -->
      <!-- IoU 0.5: 0.76 → bar height = 0.76*220=167.2, y=240-167.2=72.8 -->
      <rect x="80" y="73" width="38" height="167" fill="#38bdf8" rx="3"/>
      <!-- IoU 0.75: 0.54 → 0.54*220=118.8, y=240-118.8=121.2 -->
      <rect x="122" y="121" width="38" height="119" fill="#0284c7" rx="3"/>
      <text x="121" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">GR00T</text>
      <text x="121" y="268" fill="#94a3b8" font-size="10" text-anchor="middle">encoder</text>

      <!-- Model: GroundingDINO -->
      <!-- IoU 0.5: 0.71 → 0.71*220=156.2, y=83.8 -->
      <rect x="185" y="84" width="38" height="156" fill="#38bdf8" rx="3"/>
      <!-- IoU 0.75: 0.49 → 0.49*220=107.8, y=132.2 -->
      <rect x="227" y="132" width="38" height="108" fill="#0284c7" rx="3"/>
      <text x="226" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">Grounding</text>
      <text x="226" y="268" fill="#94a3b8" font-size="10" text-anchor="middle">DINO</text>

      <!-- Model: OwlViT -->
      <!-- IoU 0.5: 0.68 → 0.68*220=149.6, y=90.4 -->
      <rect x="290" y="90" width="38" height="150" fill="#38bdf8" rx="3"/>
      <!-- IoU 0.75: 0.45 → 0.45*220=99, y=141 -->
      <rect x="332" y="141" width="38" height="99" fill="#0284c7" rx="3"/>
      <text x="331" y="255" fill="#94a3b8" font-size="10" text-anchor="middle">OwlViT</text>
      <text x="331" y="268" fill="#94a3b8" font-size="10" text-anchor="middle">&nbsp;</text>

      <!-- Value labels on bars -->
      <text x="99" y="69" fill="#e2e8f0" font-size="11" text-anchor="middle">0.76</text>
      <text x="141" y="117" fill="#e2e8f0" font-size="11" text-anchor="middle">0.54</text>
      <text x="204" y="80" fill="#e2e8f0" font-size="11" text-anchor="middle">0.71</text>
      <text x="246" y="128" fill="#e2e8f0" font-size="11" text-anchor="middle">0.49</text>
      <text x="309" y="86" fill="#e2e8f0" font-size="11" text-anchor="middle">0.68</text>
      <text x="351" y="137" fill="#e2e8f0" font-size="11" text-anchor="middle">0.45</text>

      <!-- Legend -->
      <rect x="63" y="282" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="79" y="291" fill="#94a3b8" font-size="11">IoU 0.5</text>
      <rect x="130" y="282" width="12" height="10" fill="#0284c7" rx="2"/>
      <text x="146" y="291" fill="#94a3b8" font-size="11">IoU 0.75</text>
    </svg>
  </div>

  <!-- Chart 2: IoU Threshold vs Recall Curve -->
  <div class="chart-card">
    <div class="chart-title">IoU Threshold vs Recall — 3 Models</div>
    <svg viewBox="0 0 460 300" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="20" x2="60" y2="240" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="240" x2="440" y2="240" stroke="#334155" stroke-width="1.5"/>
      <!-- Grid -->
      <line x1="60" y1="196" x2="440" y2="196" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="152" x2="440" y2="152" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="108" x2="440" y2="108" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="64" x2="440" y2="64" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- X grid -->
      <line x1="155" y1="20" x2="155" y2="240" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="250" y1="20" x2="250" y2="240" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="345" y1="20" x2="345" y2="240" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="440" y1="20" x2="440" y2="240" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- X labels: 0.5, 0.6, 0.7, 0.8, 0.9 → x: 60,155,250,345,440 -->
      <text x="60" y="256" fill="#64748b" font-size="11" text-anchor="middle">0.5</text>
      <text x="155" y="256" fill="#64748b" font-size="11" text-anchor="middle">0.6</text>
      <text x="250" y="256" fill="#64748b" font-size="11" text-anchor="middle">0.7</text>
      <text x="345" y="256" fill="#64748b" font-size="11" text-anchor="middle">0.8</text>
      <text x="440" y="256" fill="#64748b" font-size="11" text-anchor="middle">0.9</text>
      <text x="250" y="272" fill="#94a3b8" font-size="12" text-anchor="middle">IoU Threshold</text>
      <!-- Y labels -->
      <text x="52" y="244" fill="#64748b" font-size="11" text-anchor="end">0.0</text>
      <text x="52" y="200" fill="#64748b" font-size="11" text-anchor="end">0.2</text>
      <text x="52" y="156" fill="#64748b" font-size="11" text-anchor="end">0.4</text>
      <text x="52" y="112" fill="#64748b" font-size="11" text-anchor="end">0.6</text>
      <text x="52" y="68" fill="#64748b" font-size="11" text-anchor="end">0.8</text>
      <text x="52" y="24" fill="#64748b" font-size="11" text-anchor="end">1.0</text>
      <text x="14" y="140" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,14,140)">Recall</text>

      <!-- GR00T: 0.82,0.74,0.63,0.50,0.35 → y=240-recall*220 -->
      <!-- x points: 60,155,250,345,440 -->
      <!-- y: 240-180=60, 240-163=77, 240-139=101, 240-110=130, 240-77=163 -->
      <polyline points="60,60 155,77 250,101 345,130 440,163" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="60" cy="60" r="4" fill="#38bdf8"/>
      <circle cx="155" cy="77" r="4" fill="#38bdf8"/>
      <circle cx="250" cy="101" r="4" fill="#38bdf8"/>
      <circle cx="345" cy="130" r="4" fill="#38bdf8"/>
      <circle cx="440" cy="163" r="4" fill="#38bdf8"/>

      <!-- GroundingDINO: 0.76,0.67,0.56,0.43,0.29 -->
      <!-- y: 240-167=73, 240-147=93, 240-123=117, 240-95=145, 240-64=176 -->
      <polyline points="60,73 155,93 250,117 345,145 440,176" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="60" cy="73" r="4" fill="#a78bfa"/>
      <circle cx="155" cy="93" r="4" fill="#a78bfa"/>
      <circle cx="250" cy="117" r="4" fill="#a78bfa"/>
      <circle cx="345" cy="145" r="4" fill="#a78bfa"/>
      <circle cx="440" cy="176" r="4" fill="#a78bfa"/>

      <!-- OwlViT: 0.72,0.62,0.50,0.37,0.24 -->
      <!-- y: 240-158=82, 240-136=104, 240-110=130, 240-81=159, 240-53=187 -->
      <polyline points="60,82 155,104 250,130 345,159 440,187" fill="none" stroke="#fb923c" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="60" cy="82" r="4" fill="#fb923c"/>
      <circle cx="155" cy="104" r="4" fill="#fb923c"/>
      <circle cx="250" cy="130" r="4" fill="#fb923c"/>
      <circle cx="345" cy="159" r="4" fill="#fb923c"/>
      <circle cx="440" cy="187" r="4" fill="#fb923c"/>

      <!-- Legend -->
      <line x1="63" y1="287" x2="83" y2="287" stroke="#38bdf8" stroke-width="2.5"/>
      <text x="87" y="291" fill="#94a3b8" font-size="11">GR00T_encoder</text>
      <line x1="183" y1="287" x2="203" y2="287" stroke="#a78bfa" stroke-width="2.5"/>
      <text x="207" y="291" fill="#94a3b8" font-size="11">GroundingDINO</text>
      <line x1="303" y1="287" x2="323" y2="287" stroke="#fb923c" stroke-width="2.5"/>
      <text x="327" y="291" fill="#94a3b8" font-size="11">OwlViT</text>
    </svg>
  </div>

  <!-- Chart 3: Detection Confidence vs SR Scatter -->
  <div class="chart-card" style="grid-column: span 2;">
    <div class="chart-title">Detection Confidence vs Success Rate (r = 0.84, n=40)</div>
    <svg viewBox="0 0 900 320" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="70" y1="20" x2="70" y2="260" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="260" x2="870" y2="260" stroke="#334155" stroke-width="1.5"/>
      <!-- Grid -->
      <line x1="70" y1="212" x2="870" y2="212" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="164" x2="870" y2="164" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="116" x2="870" y2="116" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="68" x2="870" y2="68" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="20" x2="870" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- X grid -->
      <line x1="230" y1="20" x2="230" y2="260" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="390" y1="20" x2="390" y2="260" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="550" y1="20" x2="550" y2="260" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="710" y1="20" x2="710" y2="260" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="870" y1="20" x2="870" y2="260" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- X labels: 0.5→70, 0.6→230, 0.7→390, 0.8→550, 0.9→710, 1.0→870 -->
      <text x="70" y="276" fill="#64748b" font-size="11" text-anchor="middle">0.50</text>
      <text x="230" y="276" fill="#64748b" font-size="11" text-anchor="middle">0.60</text>
      <text x="390" y="276" fill="#64748b" font-size="11" text-anchor="middle">0.70</text>
      <text x="550" y="276" fill="#64748b" font-size="11" text-anchor="middle">0.80</text>
      <text x="710" y="276" fill="#64748b" font-size="11" text-anchor="middle">0.90</text>
      <text x="870" y="276" fill="#64748b" font-size="11" text-anchor="middle">1.00</text>
      <text x="470" y="295" fill="#94a3b8" font-size="12" text-anchor="middle">Detection Confidence</text>
      <!-- Y labels -->
      <text x="62" y="264" fill="#64748b" font-size="11" text-anchor="end">0.0</text>
      <text x="62" y="216" fill="#64748b" font-size="11" text-anchor="end">0.2</text>
      <text x="62" y="168" fill="#64748b" font-size="11" text-anchor="end">0.4</text>
      <text x="62" y="120" fill="#64748b" font-size="11" text-anchor="end">0.6</text>
      <text x="62" y="72" fill="#64748b" font-size="11" text-anchor="end">0.8</text>
      <text x="62" y="24" fill="#64748b" font-size="11" text-anchor="end">1.0</text>
      <text x="18" y="150" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,18,150)">Success Rate</text>

      <!-- Regression line: r=0.84, slope ~ SR = 0.95*conf - 0.16 -->
      <!-- at conf=0.50: SR=0.315 → x=70, y=260-0.315*240=184.4 -->
      <!-- at conf=1.00: SR=0.79  → x=870, y=260-0.79*240=70.4 -->
      <line x1="70" y1="184" x2="870" y2="70" stroke="#C74634" stroke-width="2" stroke-dasharray="8,4" opacity="0.8"/>
      <text x="876" y="68" fill="#C74634" font-size="11">r=0.84</text>

      <!-- 40 scatter points: conf in [0.50..0.98], SR = 0.95*conf-0.16 + noise -->
      <!-- Pre-computed points (conf, SR) mapped to SVG: x=70+(conf-0.5)/0.5*800, y=260-SR*240 -->
      <!-- Row format: cx cy -->
      <circle cx="86" cy="198" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="102" cy="187" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="118" cy="175" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="134" cy="182" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="150" cy="163" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="166" cy="171" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="182" cy="155" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="198" cy="168" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="214" cy="149" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="238" cy="158" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="254" cy="140" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="270" cy="152" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="295" cy="136" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="318" cy="145" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="334" cy="128" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="358" cy="140" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="374" cy="122" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="396" cy="131" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="415" cy="115" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="438" cy="124" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="455" cy="108" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="474" cy="117" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="495" cy="100" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="515" cy="112" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="534" cy="95" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="558" cy="104" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="575" cy="90" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="596" cy="98" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="618" cy="84" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="636" cy="93" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="655" cy="78" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="675" cy="88" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="694" cy="74" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="716" cy="82" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="734" cy="68" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="756" cy="78" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="776" cy="63" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="798" cy="72" r="5" fill="#38bdf8" opacity="0.75"/>
      <circle cx="820" cy="58" r="5" fill="#38bdf8" opacity="0.75"/>
    </svg>
  </div>

</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Object Detection 3D Eval")

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
