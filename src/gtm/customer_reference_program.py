"""Customer Reference Program — FastAPI service (port 10197).

Formal customer reference management: case studies, reference calls,
logo rights, testimonials, and champion tracking.
"""

import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10197
SERVICE_NAME = "customer_reference_program"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Customer Reference Program", version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(_build_dashboard())

    @app.get("/references/customers")
    def list_customers():
        """Stub: return enrolled reference customers."""
        return JSONResponse({
            "customers": [
                {
                    "name": "Machina",
                    "tier": "champion",
                    "success_rate_before": "63%",
                    "success_rate_after": "91%",
                    "activities": ["case_study", "reference_call", "logo", "testimonial"]
                },
                {
                    "name": "Verdant",
                    "tier": "advocate",
                    "activities": ["reference_call", "logo"]
                },
                {
                    "name": "Helix",
                    "tier": "reference",
                    "activities": ["logo"]
                }
            ],
            "program_roi": "$124K ARR influenced",
            "champion_win_rate_lift": "+18%"
        })

    @app.post("/references/request")
    def request_reference(customer_name: str, activity_type: str = "reference_call"):
        """Stub: submit a reference activity request."""
        valid_activities = ["reference_call", "case_study", "logo", "testimonial", "event_speaker"]
        if activity_type not in valid_activities:
            return JSONResponse({"error": f"Unknown activity type. Valid: {valid_activities}"}, status_code=400)
        return JSONResponse({
            "status": "submitted",
            "customer": customer_name,
            "activity": activity_type,
            "request_id": f"ref_{customer_name.lower()}_{activity_type}_{int(datetime.utcnow().timestamp())}",
            "note": "Request routed to customer success manager for approval"
        })

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_dashboard() -> str:
    bars = [
        ("Champion Win Rate", 18,  20),   # +18% lift shown as 18/20 scale
        ("Case Study Deals",   3,   5),
        ("Program ROI ($K)",  124, 140),
        ("Machina SR Before",  63, 100),
        ("Machina SR After",   91, 100),
    ]
    colors = ["#C74634", "#38bdf8", "#C74634", "#64748b", "#38bdf8"]

    svg_rows = ""
    for i, ((label, value, max_val), color) in enumerate(zip(bars, colors)):
        y_text = 58 + i * 36
        y_rect = y_text - 14
        width = int(value / max_val * 340)
        display = f"+{value}%" if i == 0 else (f"{value}" if i < 2 else (f"${value}K" if i == 2 else f"{value}%"))
        svg_rows += f'<text x="130" y="{y_text}" fill="#94a3b8" font-size="12" text-anchor="end">{label}</text>\n'
        svg_rows += f'<rect x="140" y="{y_rect}" width="{width}" height="18" fill="{color}" rx="3"/>\n'
        svg_rows += f'<text x="{140 + width + 6}" y="{y_text}" fill="#e2e8f0" font-size="12">{display}</text>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Customer Reference Program — Port {PORT}</title>
  <style>
    body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .header {{ background:#C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    .header h1 {{ margin:0; font-size:1.4rem; letter-spacing:.5px; }}
    .badge {{ background:#0f172a; color:#38bdf8; border-radius:6px; padding:3px 10px; font-size:.8rem; font-weight:700; }}
    .container {{ max-width:860px; margin:32px auto; padding:0 24px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:24px; }}
    .card h2 {{ margin:0 0 16px; font-size:1rem; color:#38bdf8; text-transform:uppercase; letter-spacing:1px; }}
    .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
    .stat {{ background:#0f172a; border-radius:8px; padding:16px; text-align:center; }}
    .stat .val {{ font-size:1.8rem; font-weight:700; color:#C74634; }}
    .stat .lbl {{ font-size:.75rem; color:#94a3b8; margin-top:4px; }}
    .tier {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:.75rem; font-weight:700; }}
    .tier-champion {{ background:#C74634; color:#fff; }}
    .tier-advocate {{ background:#38bdf8; color:#0f172a; }}
    .tier-reference {{ background:#475569; color:#e2e8f0; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ text-align:left; color:#94a3b8; font-size:.75rem; text-transform:uppercase; padding:8px 0; border-bottom:1px solid #334155; }}
    td {{ padding:10px 0; border-bottom:1px solid #1e293b; font-size:.9rem; }}
    svg text {{ font-family:'Segoe UI',sans-serif; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Customer Reference Program</h1>
      <div style="color:#fecaca;font-size:.85rem;margin-top:4px">Case studies · Reference calls · Logo rights · Testimonials</div>
    </div>
    <div class="badge">PORT {PORT}</div>
  </div>
  <div class="container">
    <div class="stats">
      <div class="stat"><div class="val">+18%</div><div class="lbl">Champion Win Rate Lift</div></div>
      <div class="stat"><div class="val">$124K</div><div class="lbl">ARR Influenced</div></div>
      <div class="stat"><div class="val">3</div><div class="lbl">Deals via Case Study</div></div>
    </div>
    <div class="card" style="margin-top:24px">
      <h2>Reference Program Value</h2>
      <svg width="520" height="210" style="display:block;margin:0 auto">
        <text x="260" y="20" fill="#94a3b8" font-size="11" text-anchor="middle">Key Metrics (red = impact, blue = customer SR)</text>
        {svg_rows}
      </svg>
    </div>
    <div class="card">
      <h2>Enrolled Customers</h2>
      <table>
        <tr><th>Customer</th><th>Tier</th><th>SR Before</th><th>SR After</th><th>Activities</th></tr>
        <tr>
          <td><strong>Machina</strong></td>
          <td><span class="tier tier-champion">Champion</span></td>
          <td>63%</td>
          <td style="color:#38bdf8">91%</td>
          <td>Case Study, Call, Logo, Testimonial</td>
        </tr>
        <tr>
          <td><strong>Verdant</strong></td>
          <td><span class="tier tier-advocate">Advocate</span></td>
          <td>—</td>
          <td>—</td>
          <td>Reference Call, Logo</td>
        </tr>
        <tr>
          <td><strong>Helix</strong></td>
          <td><span class="tier tier-reference">Reference</span></td>
          <td>—</td>
          <td>—</td>
          <td>Logo</td>
        </tr>
      </table>
    </div>
    <div class="card">
      <h2>Endpoints</h2>
      <ul style="color:#94a3b8;line-height:2">
        <li><code style="color:#38bdf8">GET  /health</code> — Health check</li>
        <li><code style="color:#38bdf8">GET  /references/customers</code> — List enrolled reference customers</li>
        <li><code style="color:#38bdf8">POST /references/request</code> — Submit reference activity request</li>
      </ul>
    </div>
  </div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

def _run_fallback():
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _build_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        httpd.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
