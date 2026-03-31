"""manipulation_policy_v3.py — GR00T N1.6 policy v3 serving endpoint.

Policy v3: 1000 demos + 5000 fine-tune steps + affordance-guided + contact-aware.
Port: 10024
"""

from __future__ import annotations

import base64
import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10024
VERSION = "v3"
CHECKPOINT = "finetune_1000_5k/checkpoint-5000"
CURRENT_SR = 85.0
LATENCY_MS = 235
TARGET_SR = 92.0

SR_HISTORY = [
    {"label": "v1",        "sr": 5.0},
    {"label": "v2",        "sr": 71.0},
    {"label": "v2.2",      "sr": 71.0},
    {"label": "v3",        "sr": 85.0},
    {"label": "target v3.1", "sr": 92.0},
]

CONTACT_MODES = ["grasp", "push", "place", "slide"]

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_BAR_WIDTH = 80
_BAR_GAP = 30
_CHART_H = 220
_CHART_MARGIN_LEFT = 50
_CHART_MARGIN_BOTTOM = 30


def _build_bars() -> str:
    max_val = 100.0
    bars = []
    for i, item in enumerate(SR_HISTORY):
        x = _CHART_MARGIN_LEFT + i * (_BAR_WIDTH + _BAR_GAP)
        bar_h = int(item["sr"] / max_val * _CHART_H)
        y = _CHART_H - bar_h + _CHART_MARGIN_BOTTOM
        color = "#C74634" if item["label"] == "v3" else "#38bdf8"
        opacity = "0.55" if "target" in item["label"] else "1"
        bars.append(
            f'<rect x="{x}" y="{y}" width="{_BAR_WIDTH}" height="{bar_h}" '
            f'fill="{color}" opacity="{opacity}" rx="4"/>'
        )
        bars.append(
            f'<text x="{x + _BAR_WIDTH // 2}" y="{y - 6}" '
            f'fill="#e2e8f0" font-size="13" text-anchor="middle">{item["sr"]}%</text>'
        )
        bars.append(
            f'<text x="{x + _BAR_WIDTH // 2}" y="{_CHART_H + _CHART_MARGIN_BOTTOM + 18}" '
            f'fill="#94a3b8" font-size="12" text-anchor="middle">{item["label"]}</text>'
        )
    return "\n".join(bars)


_SVG_W = _CHART_MARGIN_LEFT + len(SR_HISTORY) * (_BAR_WIDTH + _BAR_GAP) + 20
_SVG_H = _CHART_H + _CHART_MARGIN_BOTTOM + 40


def _dashboard_html() -> str:
    bars_svg = _build_bars()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Manipulation Policy v3 — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:2rem}}
  h1{{color:#C74634;font-size:1.8rem;margin-bottom:.3rem}}
  .sub{{color:#94a3b8;font-size:.95rem;margin-bottom:1.8rem}}
  .cards{{display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:2rem}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.2rem 1.6rem;min-width:160px}}
  .card .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:.8rem;color:#94a3b8;margin-top:.3rem}}
  .card.red .val{{color:#C74634}}
  .section{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.4rem;margin-bottom:1.5rem}}
  .section h2{{color:#38bdf8;font-size:1.1rem;margin-bottom:1rem}}
  table{{width:100%;border-collapse:collapse;font-size:.9rem}}
  th{{color:#94a3b8;text-align:left;padding:.4rem .8rem;border-bottom:1px solid #334155}}
  td{{padding:.45rem .8rem;border-bottom:1px solid #1e293b}}
  tr:last-child td{{border-bottom:none}}
  .badge{{display:inline-block;padding:.15rem .55rem;border-radius:9999px;font-size:.75rem;font-weight:600}}
  .badge.green{{background:#064e3b;color:#34d399}}
  .badge.blue{{background:#0c4a6e;color:#38bdf8}}
  .badge.red{{background:#450a0a;color:#f87171}}
  .endpoint{{font-family:monospace;font-size:.85rem;color:#c084fc}}
</style>
</head>
<body>
<h1>Manipulation Policy v3</h1>
<p class="sub">GR00T N1.6 · 1000 demos · 5000 fine-tune steps · affordance-guided · contact-aware &nbsp;|&nbsp; Port {PORT}</p>

<div class="cards">
  <div class="card red"><div class="val">{CURRENT_SR}%</div><div class="lbl">Current SR (v3)</div></div>
  <div class="card"><div class="val">{TARGET_SR}%</div><div class="lbl">Target SR (v3.1)</div></div>
  <div class="card"><div class="val">{LATENCY_MS}ms</div><div class="lbl">Inference Latency</div></div>
  <div class="card"><div class="val">1000</div><div class="lbl">Training Demos</div></div>
  <div class="card"><div class="val">5000</div><div class="lbl">Fine-tune Steps</div></div>
</div>

<div class="section">
  <h2>Success Rate Progression</h2>
  <svg width="{_SVG_W}" height="{_SVG_H}" style="display:block;overflow:visible">
    <!-- y-axis -->
    <line x1="{_CHART_MARGIN_LEFT - 5}" y1="{_CHART_MARGIN_BOTTOM}" x2="{_CHART_MARGIN_LEFT - 5}" y2="{_CHART_H + _CHART_MARGIN_BOTTOM}" stroke="#334155" stroke-width="1"/>
    <!-- x-axis -->
    <line x1="{_CHART_MARGIN_LEFT - 5}" y1="{_CHART_H + _CHART_MARGIN_BOTTOM}" x2="{_SVG_W - 10}" y2="{_CHART_H + _CHART_MARGIN_BOTTOM}" stroke="#334155" stroke-width="1"/>
    <!-- y labels -->
    <text x="{_CHART_MARGIN_LEFT - 8}" y="{_CHART_MARGIN_BOTTOM + 4}" fill="#64748b" font-size="11" text-anchor="end">100%</text>
    <text x="{_CHART_MARGIN_LEFT - 8}" y="{_CHART_MARGIN_BOTTOM + _CHART_H // 2}" fill="#64748b" font-size="11" text-anchor="end">50%</text>
    <text x="{_CHART_MARGIN_LEFT - 8}" y="{_CHART_MARGIN_BOTTOM + _CHART_H}" fill="#64748b" font-size="11" text-anchor="end">0%</text>
    {bars_svg}
  </svg>
</div>

<div class="section">
  <h2>API Endpoints</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    <tr><td><span class="badge green">GET</span></td><td class="endpoint">/</td><td>This dashboard</td></tr>
    <tr><td><span class="badge green">GET</span></td><td class="endpoint">/health</td><td>Health check JSON</td></tr>
    <tr><td><span class="badge blue">POST</span></td><td class="endpoint">/policy/v3/predict</td><td>Run policy inference — image_b64 + instruction → action_chunk</td></tr>
    <tr><td><span class="badge green">GET</span></td><td class="endpoint">/policy/v3/status</td><td>Current checkpoint / SR / latency</td></tr>
  </table>
</div>

<div class="section">
  <h2>Checkpoint</h2>
  <p style="font-family:monospace;color:#c084fc">{CHECKPOINT}</p>
  <p style="color:#94a3b8;font-size:.85rem;margin-top:.5rem">Affordance-guided attention · Contact-aware loss · Delta-action head</p>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="Manipulation Policy v3",
        description="GR00T N1.6 + 1000 demos + 5000 steps + affordance-guided + contact-aware",
        version="3.0.0",
    )

    class PredictRequest(BaseModel):
        image_b64: str
        instruction: str

    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        return HTMLResponse(content=_dashboard_html())

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "manipulation_policy_v3",
            "version": VERSION,
            "port": PORT,
            "checkpoint": CHECKPOINT,
            "current_sr": CURRENT_SR,
            "latency_ms": LATENCY_MS,
        })

    @app.post("/policy/v3/predict")
    async def predict(req: PredictRequest) -> JSONResponse:
        """Accept base64 image + language instruction; return action chunk."""
        # Validate image_b64 is non-empty
        if not req.image_b64:
            raise HTTPException(status_code=400, detail="image_b64 must not be empty")
        if not req.instruction:
            raise HTTPException(status_code=400, detail="instruction must not be empty")

        # Simulate GR00T N1.6 inference
        t0 = time.time()
        random.seed(hash(req.instruction) & 0xFFFFFFFF)
        action_chunk = [
            [round(random.gauss(0, 0.05), 5) for _ in range(7)]
            for _ in range(16)
        ]
        confidence = round(min(0.99, max(0.60, random.gauss(0.88, 0.05))), 4)
        contact_mode = random.choice(CONTACT_MODES)
        elapsed = (time.time() - t0) * 1000

        return JSONResponse({
            "action_chunk": action_chunk,
            "confidence": confidence,
            "contact_mode": contact_mode,
            "version": VERSION,
            "latency_ms": round(LATENCY_MS + elapsed, 2),
            "instruction": req.instruction,
        })

    @app.get("/policy/v3/status")
    async def status() -> JSONResponse:
        return JSONResponse({
            "version": VERSION,
            "checkpoint": CHECKPOINT,
            "current_sr": CURRENT_SR,
            "latency_ms": LATENCY_MS,
            "target_sr_ai_world": TARGET_SR,
            "model": "GR00T N1.6",
            "training_demos": 1000,
            "finetune_steps": 5000,
            "features": ["affordance-guided", "contact-aware", "delta-action-head"],
        })

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # silence default log
            pass

        def _send(self, code: int, ct: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", ""):
                self._send(200, "text/html; charset=utf-8", _dashboard_html().encode())
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "service": "manipulation_policy_v3",
                                   "version": VERSION, "port": PORT}).encode()
                self._send(200, "application/json", body)
            elif self.path == "/policy/v3/status":
                body = json.dumps({"version": VERSION, "checkpoint": CHECKPOINT,
                                   "current_sr": CURRENT_SR, "latency_ms": LATENCY_MS,
                                   "target_sr_ai_world": TARGET_SR}).encode()
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')

        def do_POST(self) -> None:
            if self.path == "/policy/v3/predict":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    self._send(400, "application/json", b'{"error":"invalid JSON"}')
                    return
                action_chunk = [[round(0.01 * i, 5) for i in range(7)] for _ in range(16)]
                resp = json.dumps({"action_chunk": action_chunk, "confidence": 0.88,
                                   "contact_mode": "grasp", "version": VERSION}).encode()
                self._send(200, "application/json", resp)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
