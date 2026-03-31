"""ai_world_demo_rehearsal.py — AI World September 2026 Demo Rehearsal Tracker (port 10043)

Tracks demo preparation, run plan, and QA checklist for the AI World September 2026
robotics live demo.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10043
EVENT_DATE_DEFAULT = "2026-09-15"
MIN_REHEARSALS = 5
QA_SR_THRESHOLD = 90.0
QA_LATENCY_MS = 250

DEMO_SCRIPT = [
    {"step": "Introduction & OCI Robot Cloud overview", "duration_s": 30},
    {"step": "Synthetic Data Generation (SDG) with Isaac Sim", "duration_s": 45},
    {"step": "GR00T N1.6 fine-tuning results (MAE 0.013)", "duration_s": 45},
    {"step": "Live robot pick-and-place demonstration", "duration_s": 60},
]

HARDWARE_CHECKLIST = [
    "A100 GPU node online and warm",
    "GR00T N1.6 checkpoint loaded (port 8001)",
    "LIBERO simulation environment initialized",
    "Network latency to OCI < 50 ms",
    "Backup checkpoint ready on local NVMe",
    "Demo laptop display mirroring confirmed",
    "Wireless presenter clicker paired",
    "Recording setup (4K camera + screen capture) active",
]

FALLBACK_PLAN = (
    "If live robot fails: switch to pre-recorded 1-minute demo video (saved on NVMe). "
    "If OCI connectivity drops: run inference locally on RTX 4090 with cached model. "
    "If LIBERO env crashes: reload from checkpoint, resume at fine-tuning results slide."
)

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI World Demo Rehearsal | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f8fafc; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem 1.5rem; }
    .kpi .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .kpi .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { font-size: 1rem; font-weight: 600; color: #38bdf8; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .script-row { display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid #1e293b; }
    .script-row:last-child { border-bottom: none; }
    .step-num { width: 2rem; height: 2rem; background: #C74634; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; flex-shrink: 0; }
    .step-desc { flex: 1; font-size: 0.9rem; }
    .step-dur { font-size: 0.8rem; color: #38bdf8; font-weight: 600; white-space: nowrap; }
    .qa-gate { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; }
    .qa-gate .dot { width: 10px; height: 10px; border-radius: 50%; background: #38bdf8; flex-shrink: 0; }
    .qa-gate .desc { font-size: 0.9rem; }
    .gate-threshold { color: #38bdf8; font-weight: 600; }
    .checklist-item { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.35rem 0; font-size: 0.875rem; }
    .checklist-item::before { content: '\2610'; color: #64748b; flex-shrink: 0; }
    .fallback-box { background: #0f172a; border-left: 3px solid #C74634; border-radius: 0 0.5rem 0.5rem 0; padding: 0.75rem 1rem; font-size: 0.875rem; color: #94a3b8; line-height: 1.6; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem 0 3rem; }
  </style>
</head>
<body>
  <header>
    <h1>AI World September 2026 &mdash; Demo Rehearsal Tracker</h1>
    <span class="badge">port 10043</span>
  </header>
  <main>
    <div class="kpi-row">
      <div class="kpi"><div class="label">Event Date</div><div class="value" style="font-size:1.3rem">Sep 2026</div><div class="sub">AI World Conference</div></div>
      <div class="kpi"><div class="label">Demo Duration</div><div class="value">3 min</div><div class="sub">4 segments</div></div>
      <div class="kpi"><div class="label">SR Gate</div><div class="value">&gt;90%</div><div class="sub">minimum success rate</div></div>
      <div class="kpi"><div class="label">Latency Gate</div><div class="value">&lt;250ms</div><div class="sub">inference latency</div></div>
      <div class="kpi"><div class="label">Min Rehearsals</div><div class="value">5x</div><div class="sub">required before event</div></div>
    </div>

    <div class="section">
      <h2>3-Minute Demo Script</h2>
      <div class="script-row"><div class="step-num">1</div><div class="step-desc">Introduction &amp; OCI Robot Cloud overview</div><div class="step-dur">30s</div></div>
      <div class="script-row"><div class="step-num">2</div><div class="step-desc">Synthetic Data Generation (SDG) with Isaac Sim</div><div class="step-dur">45s</div></div>
      <div class="script-row"><div class="step-num">3</div><div class="step-desc">GR00T N1.6 fine-tuning results (MAE 0.013)</div><div class="step-dur">45s</div></div>
      <div class="script-row"><div class="step-num">4</div><div class="step-desc">Live robot pick-and-place demonstration</div><div class="step-dur">60s</div></div>
    </div>

    <div class="section">
      <h2>QA Gates</h2>
      <div class="qa-gate"><div class="dot"></div><div class="desc">Success Rate &ge; <span class="gate-threshold">90%</span> across 20 episodes</div></div>
      <div class="qa-gate"><div class="dot"></div><div class="desc">Inference latency &le; <span class="gate-threshold">250 ms</span> (p95)</div></div>
      <div class="qa-gate"><div class="dot"></div><div class="desc">Minimum <span class="gate-threshold">5 full rehearsals</span> completed</div></div>
      <div class="qa-gate"><div class="dot"></div><div class="desc">All hardware checklist items verified</div></div>
    </div>

    <div class="section">
      <h2>Segment Duration Chart</h2>
      <svg viewBox="0 0 480 200" width="100%" height="200">
        <line x1="60" y1="20" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
        <line x1="60" y1="160" x2="460" y2="160" stroke="#334155" stroke-width="1"/>
        <text x="52" y="164" fill="#64748b" font-size="10" text-anchor="end">0s</text>
        <text x="52" y="107" fill="#64748b" font-size="10" text-anchor="end">40s</text>
        <text x="52" y="54" fill="#64748b" font-size="10" text-anchor="end">80s</text>
        <line x1="60" y1="106" x2="460" y2="106" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
        <!-- 30s bar: 30/80*140=52.5 height -->
        <rect x="70" y="108" width="70" height="52" fill="#38bdf8" rx="3"/>
        <text x="105" y="104" fill="#94a3b8" font-size="10" text-anchor="middle">30s</text>
        <text x="105" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Intro</text>
        <!-- 45s bar: 45/80*140=78.75 -->
        <rect x="165" y="82" width="70" height="78" fill="#38bdf8" rx="3"/>
        <text x="200" y="78" fill="#94a3b8" font-size="10" text-anchor="middle">45s</text>
        <text x="200" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">SDG</text>
        <!-- 45s bar -->
        <rect x="260" y="82" width="70" height="78" fill="#C74634" rx="3"/>
        <text x="295" y="78" fill="#94a3b8" font-size="10" text-anchor="middle">45s</text>
        <text x="295" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Fine-tune</text>
        <!-- 60s bar: 60/80*140=105 -->
        <rect x="355" y="55" width="70" height="105" fill="#38bdf8" rx="3"/>
        <text x="390" y="51" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="600">60s</text>
        <text x="390" y="175" fill="#38bdf8" font-size="9" text-anchor="middle" font-weight="600">Live Robot</text>
      </svg>
    </div>

    <div class="section">
      <h2>Hardware Checklist</h2>
      <div class="checklist-item">A100 GPU node online and warm</div>
      <div class="checklist-item">GR00T N1.6 checkpoint loaded (port 8001)</div>
      <div class="checklist-item">LIBERO simulation environment initialized</div>
      <div class="checklist-item">Network latency to OCI &lt; 50 ms</div>
      <div class="checklist-item">Backup checkpoint ready on local NVMe</div>
      <div class="checklist-item">Demo laptop display mirroring confirmed</div>
      <div class="checklist-item">Wireless presenter clicker paired</div>
      <div class="checklist-item">Recording setup (4K camera + screen capture) active</div>
    </div>

    <div class="section">
      <h2>Fallback Plan</h2>
      <div class="fallback-box">If live robot fails: switch to pre-recorded 1-minute demo video (saved on NVMe).<br>If OCI connectivity drops: run inference locally on RTX 4090 with cached model.<br>If LIBERO env crashes: reload from checkpoint, resume at fine-tuning results slide.</div>
    </div>
  </main>
  <footer>OCI Robot Cloud &mdash; AI World Demo Rehearsal Tracker &mdash; port 10043</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Core logic helpers
# ---------------------------------------------------------------------------

# In-memory rehearsal log (resets on restart — use external store for persistence)
_rehearsal_log: list[dict[str, Any]] = []


def _build_run_plan(event_date: str) -> dict[str, Any]:
    return {
        "event_date": event_date,
        "demo_script": DEMO_SCRIPT,
        "hardware_checklist": HARDWARE_CHECKLIST,
        "fallback_plan": FALLBACK_PLAN,
    }


def _process_rehearsal_log(entry: dict[str, Any]) -> dict[str, Any]:
    _rehearsal_log.append(entry)
    rehearsal_number = entry.get("rehearsal_number", len(_rehearsal_log))
    sr_achieved = float(entry.get("sr_achieved", 0.0))
    issues_found: list[str] = entry.get("issues_found", [])

    # Readiness: weighted by rehearsal count and SR
    sr_factor = min(sr_achieved / QA_SR_THRESHOLD, 1.0)
    rehearsal_factor = min(rehearsal_number / MIN_REHEARSALS, 1.0)
    updated_readiness_pct = round(0.6 * sr_factor * 100 + 0.4 * rehearsal_factor * 100, 1)

    remaining_rehearsals = max(0, MIN_REHEARSALS - rehearsal_number)
    blocking_issues = [i for i in issues_found if any(
        kw in i.lower() for kw in ["crash", "fail", "block", "latency", "timeout", "error"]
    )]

    return {
        "updated_readiness_pct": updated_readiness_pct,
        "remaining_rehearsals": remaining_rehearsals,
        "blocking_issues": blocking_issues,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="AI World Demo Rehearsal Tracker",
        description="AI World September 2026 demo preparation tracker with run plan and QA checklist.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "ai_world_demo_rehearsal", "port": PORT, "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/demo/run_plan")
    async def run_plan(event_date: str = Query(default=EVENT_DATE_DEFAULT, description="Event date in YYYY-MM-DD format")):
        return JSONResponse(_build_run_plan(event_date))

    @app.post("/demo/rehearsal_log")
    async def rehearsal_log(body: dict = None):
        if body is None:
            body = {}
        return JSONResponse(_process_rehearsal_log(body))


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, content_type: str, body: str | bytes):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "service": "ai_world_demo_rehearsal", "port": PORT}))
            elif path == "/demo/run_plan":
                event_date = params.get("event_date", [EVENT_DATE_DEFAULT])[0]
                self._send(200, "application/json", json.dumps(_build_run_plan(event_date)))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/demo/rehearsal_log":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw or b"{}")
                self._send(200, "application/json", json.dumps(_process_rehearsal_log(body)))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

    def _serve_fallback():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[ai_world_demo_rehearsal] stdlib HTTPServer listening on port {PORT}")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve_fallback()
