"""Real-Time Success Evaluator — OCI Robot Cloud (port 8598)

Early-termination classifier with ROC analysis, episode timeline,
and per-model compute savings dashboard.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8598


def build_html() -> str:
    roc_svg = """
<svg viewBox="0 0 400 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:420px">
  <rect width="400" height="320" fill="#1e293b" rx="8"/>
  <text x="200" y="26" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">ROC Curve — Early Termination Classifier</text>
  <!-- axes -->
  <line x1="55" y1="270" x2="370" y2="270" stroke="#475569" stroke-width="1.5"/>
  <line x1="55" y1="270" x2="55" y2="40" stroke="#475569" stroke-width="1.5"/>
  <!-- axis labels -->
  <text x="210" y="298" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">False Positive Rate</text>
  <text x="16" y="160" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90,16,160)">True Positive Rate</text>
  <!-- tick labels -->
  <text x="55" y="284" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">0.0</text>
  <text x="134" y="284" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">0.25</text>
  <text x="212" y="284" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">0.5</text>
  <text x="291" y="284" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">0.75</text>
  <text x="370" y="284" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">1.0</text>
  <text x="48" y="270" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">0.0</text>
  <text x="48" y="193" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">0.25</text>
  <text x="48" y="155" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">0.5</text>
  <text x="48" y="117" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">0.75</text>
  <text x="48" y="44" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">1.0</text>
  <!-- diagonal baseline -->
  <line x1="55" y1="270" x2="370" y2="44" stroke="#475569" stroke-width="1" stroke-dasharray="5,4"/>
  <text x="230" y="185" fill="#475569" font-size="9" font-family="monospace" transform="rotate(-37,230,185)">Random (AUC=0.50)</text>
  <!-- ROC curve (AUC=0.89) -- points: fpr,tpr mapped to svg coords -->
  <!-- x: 55 + fpr*315, y: 270 - tpr*226 -->
  <polyline points="
    55,270
    63,175
    71,133
    87,95
    118,66
    165,53
    228,47
    291,44
    334,44
    370,44
  " fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
  <!-- operating point -->
  <circle cx="87" cy="95" r="5" fill="#C74634"/>
  <text x="93" y="91" fill="#C74634" font-size="10" font-family="monospace">FP=4.2% / Threshold</text>
  <!-- AUC label -->
  <rect x="260" y="200" width="100" height="28" fill="#0f172a" rx="4"/>
  <text x="310" y="215" text-anchor="middle" fill="#38bdf8" font-size="12" font-family="monospace" font-weight="bold">AUC = 0.89</text>
  <text x="310" y="224" text-anchor="middle" fill="#94a3b8" font-size="8" font-family="monospace">frame-10 prediction</text>
</svg>"""

    timeline_svg = """
<svg viewBox="0 0 640 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:660px">
  <rect width="640" height="240" fill="#1e293b" rx="8"/>
  <text x="320" y="22" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">Success Signal Timeline — 100 Episodes</text>
  <!-- x axis -->
  <line x1="40" y1="180" x2="610" y2="180" stroke="#475569" stroke-width="1.5"/>
  <text x="325" y="200" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Episode Index</text>
  <!-- y axis -->
  <line x1="40" y1="40" x2="40" y2="180" stroke="#475569" stroke-width="1.5"/>
  <text x="12" y="115" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,12,115)">Success Signal</text>
  <!-- baseline steps line at y=130 -->
  <line x1="40" y1="130" x2="610" y2="130" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="615" y="133" fill="#475569" font-size="9" font-family="monospace">max</text>
  <!-- episode bars (success=green, fail=red, early-term=cyan outline) -->
  <!-- Simulate 100 episodes as thin vertical bars -->
  <g id="epbars">
    <!-- success episodes (green) at various indices -->
    <rect x="45" y="90" width="4" height="90" fill="#22c55e" opacity="0.7"/>
    <rect x="51" y="100" width="4" height="80" fill="#22c55e" opacity="0.7"/>
    <rect x="57" y="85" width="4" height="95" fill="#22c55e" opacity="0.7"/>
    <rect x="63" y="110" width="4" height="70" fill="#ef4444" opacity="0.7"/>
    <rect x="69" y="95" width="4" height="85" fill="#22c55e" opacity="0.7"/>
    <rect x="75" y="120" width="4" height="60" fill="#ef4444" opacity="0.7"/>
    <rect x="81" y="88" width="4" height="92" fill="#22c55e" opacity="0.7"/>
    <rect x="87" y="105" width="4" height="75" fill="#22c55e" opacity="0.7"/>
    <rect x="93" y="115" width="4" height="65" fill="#ef4444" opacity="0.7"/>
    <rect x="99" y="92" width="4" height="88" fill="#22c55e" opacity="0.7"/>
    <!-- early term annotations (cyan border) -->
    <rect x="57" y="85" width="4" height="95" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="81" y="88" width="4" height="92" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="99" y="92" width="4" height="88" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <!-- more episodes -->
    <rect x="105" y="98" width="4" height="82" fill="#22c55e" opacity="0.7"/>
    <rect x="111" y="112" width="4" height="68" fill="#ef4444" opacity="0.7"/>
    <rect x="117" y="87" width="4" height="93" fill="#22c55e" opacity="0.7"/>
    <rect x="117" y="87" width="4" height="93" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="123" y="118" width="4" height="62" fill="#ef4444" opacity="0.7"/>
    <rect x="129" y="94" width="4" height="86" fill="#22c55e" opacity="0.7"/>
    <rect x="135" y="107" width="4" height="73" fill="#22c55e" opacity="0.7"/>
    <rect x="141" y="122" width="4" height="58" fill="#ef4444" opacity="0.7"/>
    <rect x="147" y="91" width="4" height="89" fill="#22c55e" opacity="0.7"/>
    <rect x="147" y="91" width="4" height="89" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="153" y="103" width="4" height="77" fill="#22c55e" opacity="0.7"/>
    <rect x="159" y="116" width="4" height="64" fill="#ef4444" opacity="0.7"/>
    <rect x="165" y="89" width="4" height="91" fill="#22c55e" opacity="0.7"/>
    <rect x="171" y="125" width="4" height="55" fill="#ef4444" opacity="0.7"/>
    <rect x="177" y="93" width="4" height="87" fill="#22c55e" opacity="0.7"/>
    <rect x="177" y="93" width="4" height="87" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
    <!-- step savings markers -->
    <line x1="59" y1="75" x2="59" y2="85" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="59" y="72" text-anchor="middle" fill="#f59e0b" font-size="7" font-family="monospace">-87ms</text>
    <line x1="83" y1="78" x2="83" y2="88" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="83" y="75" text-anchor="middle" fill="#f59e0b" font-size="7" font-family="monospace">-87ms</text>
    <line x1="149" y1="81" x2="149" y2="91" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="149" y="78" text-anchor="middle" fill="#f59e0b" font-size="7" font-family="monospace">-87ms</text>
  </g>
  <!-- legend -->
  <rect x="430" y="50" width="12" height="10" fill="#22c55e" opacity="0.8"/>
  <text x="446" y="59" fill="#94a3b8" font-size="10" font-family="monospace">Success</text>
  <rect x="430" y="68" width="12" height="10" fill="#ef4444" opacity="0.8"/>
  <text x="446" y="77" fill="#94a3b8" font-size="10" font-family="monospace">Failure</text>
  <rect x="430" y="86" width="12" height="10" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="446" y="95" fill="#94a3b8" font-size="10" font-family="monospace">Early Term</text>
  <line x1="430" y1="109" x2="442" y2="109" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="446" y="113" fill="#94a3b8" font-size="10" font-family="monospace">Step Saved</text>
</svg>"""

    savings_svg = """
<svg viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:440px">
  <rect width="420" height="240" fill="#1e293b" rx="8"/>
  <text x="210" y="22" text-anchor="middle" fill="#38bdf8" font-size="13" font-family="monospace" font-weight="bold">Compute Savings by Model</text>
  <!-- axes -->
  <line x1="70" y1="190" x2="390" y2="190" stroke="#475569" stroke-width="1.5"/>
  <line x1="70" y1="40" x2="70" y2="190" stroke="#475569" stroke-width="1.5"/>
  <!-- y-axis labels -->
  <text x="63" y="190" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">0%</text>
  <text x="63" y="153" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">10%</text>
  <text x="63" y="115" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">20%</text>
  <text x="63" y="78" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">30%</text>
  <text x="63" y="40" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">40%</text>
  <!-- gridlines -->
  <line x1="70" y1="153" x2="390" y2="153" stroke="#334155" stroke-width="0.8" stroke-dasharray="3,3"/>
  <line x1="70" y1="115" x2="390" y2="115" stroke="#334155" stroke-width="0.8" stroke-dasharray="3,3"/>
  <line x1="70" y1="78" x2="390" y2="78" stroke="#334155" stroke-width="0.8" stroke-dasharray="3,3"/>
  <!-- BC bar: 22% -> height = 22/40 * 150 = 82.5 -->
  <rect x="95" y="108" width="60" height="82" fill="#C74634" rx="3"/>
  <text x="125" y="104" text-anchor="middle" fill="#C74634" font-size="11" font-family="monospace" font-weight="bold">22%</text>
  <text x="125" y="210" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">BC</text>
  <!-- DAgger bar: 35% -> height = 35/40 * 150 = 131 -->
  <rect x="180" y="59" width="60" height="131" fill="#38bdf8" rx="3"/>
  <text x="210" y="55" text-anchor="middle" fill="#38bdf8" font-size="11" font-family="monospace" font-weight="bold">35%</text>
  <text x="210" y="210" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">DAgger</text>
  <!-- GR00T_v2 bar: 38% -> height = 38/40 * 150 = 142.5 -->
  <rect x="265" y="47" width="60" height="143" fill="#a78bfa" rx="3"/>
  <text x="295" y="43" text-anchor="middle" fill="#a78bfa" font-size="11" font-family="monospace" font-weight="bold">38%</text>
  <text x="295" y="210" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">GR00T_v2</text>
  <!-- y axis title -->
  <text x="14" y="118" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,14,118)">Step Reduction</text>
</svg>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Real-Time Success Evaluator — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace, sans-serif; min-height: 100vh; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ color: #C74634; font-size: 1.35rem; font-weight: 700; letter-spacing: 0.5px; }}
  header span {{ color: #38bdf8; font-size: 0.85rem; margin-left: auto; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; padding: 24px 32px 0; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 14px; text-align: center; }}
  .metric-card .value {{ font-size: 1.9rem; font-weight: 800; color: #38bdf8; }}
  .metric-card .label {{ font-size: 0.75rem; color: #94a3b8; margin-top: 6px; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 24px 32px; }}
  .charts .wide {{ grid-column: 1 / -1; }}
  .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }}
  .chart-card h2 {{ color: #C74634; font-size: 0.9rem; margin-bottom: 14px; letter-spacing: 0.3px; }}
  footer {{ text-align: center; color: #475569; font-size: 0.75rem; padding: 20px; border-top: 1px solid #1e293b; }}
</style>
</head>
<body>
<header>
  <h1>Real-Time Success Evaluator</h1>
  <span>port 8598 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Early Termination Classifier</span>
</header>

<div class="metrics">
  <div class="metric-card"><div class="value">0.89</div><div class="label">Frame-10 Prediction AUC</div></div>
  <div class="metric-card"><div class="value">87ms</div><div class="label">Avg Step Time Saved / Episode</div></div>
  <div class="metric-card"><div class="value">38%</div><div class="label">Avg Step Reduction (GR00T_v2)</div></div>
  <div class="metric-card"><div class="value">4.2%</div><div class="label">False Positive Rate @ Threshold</div></div>
</div>

<div class="charts">
  <div class="chart-card">
    <h2>ROC Curve — Early Termination Classifier</h2>
    {roc_svg}
  </div>
  <div class="chart-card">
    <h2>Compute Savings per Model</h2>
    {savings_svg}
  </div>
  <div class="chart-card wide">
    <h2>Success Signal Timeline — 100 Episodes (cyan = early termination, amber = step savings)</h2>
    {timeline_svg}
  </div>
</div>

<footer>OCI Robot Cloud &mdash; Real-Time Success Evaluator &mdash; port 8598</footer>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Real-Time Success Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "real_time_success_evaluator",
            "port": PORT,
            "metrics": {
                "auc_frame10": 0.89,
                "ms_saved_per_episode": 87,
                "avg_step_reduction_pct": 38,
                "false_positive_rate_pct": 4.2,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","port":8598}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
