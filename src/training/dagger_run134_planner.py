"""dagger_run134_planner.py — Cross-embodiment DAgger planner (port 10074).

Cycle-504B: Franka corrections transferred simultaneously to UR5 + Kuka policies
for 3× leverage on expert annotation effort.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer  # type: ignore

PORT = 10074
SERVICE_NAME = "dagger_run134_planner"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
SOURCE_ROBOT = "Franka"
TARGET_ROBOTS = ["UR5", "Kuka"]
BASE_SOURCE_SR = 94.0    # success-rate %
BASE_UR5_SR = 88.0
BASE_KUKA_SR = 86.0
TRANSFER_LOSS_PCT = 3.0  # average cross-embodiment transfer loss
LEVERAGE = "3x"

# Simulated per-robot transfer coefficients
_TRANSFER_COEFF: dict[str, float] = {
    "UR5": 0.93,   # 93 % of Franka gain transfers
    "Kuka": 0.90,
    "Spot": 0.85,
    "xArm": 0.91,
}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>DAgger Run 134 — Cross-Embodiment Planner</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.875rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }
  .card h3 { color: #38bdf8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
  .card .unit { font-size: 0.8rem; color: #64748b; margin-top: 2px; }
  .section-title { color: #38bdf8; font-size: 1rem; font-weight: 600; margin-bottom: 12px; }
  .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 32px; }
  .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 6px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; vertical-align: middle; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { color: #38bdf8; text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  tr:hover td { background: #1e293b; }
  .tag-green { color: #4ade80; } .tag-yellow { color: #facc15; } .tag-red { color: #f87171; }
  footer { margin-top: 32px; color: #475569; font-size: 0.75rem; text-align: center; }
</style>
</head>
<body>
<h1>DAgger Run 134 — Cross-Embodiment Planner <span class="badge">LIVE</span></h1>
<p class="subtitle">1 expert session → 3 robot policies simultaneously &nbsp;|&nbsp; OCI Robot Cloud cycle-504B &nbsp;|&nbsp; port {PORT}</p>

<div class="grid">
  <div class="card"><h3>Source Robot</h3><div class="value">Franka</div><div class="unit">Panda 7-DoF</div></div>
  <div class="card"><h3>Source Success Rate</h3><div class="value">94.0<span style="font-size:1rem">%</span></div><div class="unit">after 134 DAgger runs</div></div>
  <div class="card"><h3>Transfer Loss</h3><div class="value" style="color:#facc15">3.0<span style="font-size:1rem">%</span></div><div class="unit">avg cross-embodiment loss</div></div>
  <div class="card"><h3>Leverage Multiplier</h3><div class="value" style="color:#C74634">3×</div><div class="unit">robots updated per session</div></div>
  <div class="card"><h3>UR5 Success Rate</h3><div class="value">88.0<span style="font-size:1rem">%</span></div><div class="unit">Universal Robots UR5</div></div>
  <div class="card"><h3>Kuka Success Rate</h3><div class="value">86.0<span style="font-size:1rem">%</span></div><div class="unit">KUKA iiwa 14</div></div>
</div>

<div class="chart-wrap">
  <div class="section-title">Success Rate by Robot — Bar Chart</div>
  <svg viewBox="0 0 540 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:580px;display:block;margin:auto">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="180" x2="520" y2="180" stroke="#334155" stroke-width="1"/>
    <!-- y-axis labels -->
    <text x="50" y="184" fill="#64748b" font-size="11" text-anchor="end">0</text>
    <text x="50" y="135" fill="#64748b" font-size="11" text-anchor="end">50</text>
    <text x="50" y="91" fill="#64748b" font-size="11" text-anchor="end">80</text>
    <text x="50" y="55" fill="#64748b" font-size="11" text-anchor="end">90</text>
    <text x="50" y="15" fill="#64748b" font-size="11" text-anchor="end">100</text>
    <!-- grid lines -->
    <line x1="60" y1="135" x2="520" y2="135" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="91" x2="520" y2="91" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="55" x2="520" y2="55" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="15" x2="520" y2="15" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <!-- Franka bar (94%) height=(94/100)*170=159.8 y=180-159.8=20.2 -->
    <rect x="90" y="20" width="100" height="160" fill="#C74634" rx="4"/>
    <text x="140" y="14" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">94.0%</text>
    <text x="140" y="200" fill="#94a3b8" font-size="12" text-anchor="middle">Franka</text>
    <!-- UR5 bar (88%) height=149.6 y=30.4 -->
    <rect x="220" y="31" width="100" height="149" fill="#38bdf8" rx="4"/>
    <text x="270" y="25" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">88.0%</text>
    <text x="270" y="200" fill="#94a3b8" font-size="12" text-anchor="middle">UR5</text>
    <!-- Kuka bar (86%) height=146.2 y=33.8 -->
    <rect x="350" y="34" width="100" height="146" fill="#818cf8" rx="4"/>
    <text x="400" y="28" fill="#818cf8" font-size="12" text-anchor="middle" font-weight="bold">86.0%</text>
    <text x="400" y="200" fill="#94a3b8" font-size="12" text-anchor="middle">Kuka</text>
  </svg>
</div>

<div class="chart-wrap">
  <div class="section-title">Fleet Value — Multi-Robot Customer Leverage</div>
  <table>
    <thead><tr><th>Customer</th><th>Fleet Size</th><th>Robots</th><th>Annotation Sessions Saved</th><th>Est. Value</th></tr></thead>
    <tbody>
      <tr><td>Machina Labs</td><td>6</td><td>Franka×2, UR5×2, Kuka×2</td><td class="tag-green">+67%</td><td class="tag-green">$248K</td></tr>
      <tr><td>Apptronik</td><td>4</td><td>Franka×2, UR5×2</td><td class="tag-green">+50%</td><td class="tag-green">$165K</td></tr>
      <tr><td>Agility Robotics</td><td>3</td><td>Franka, UR5, Kuka</td><td class="tag-yellow">+33%</td><td class="tag-yellow">$92K</td></tr>
      <tr><td>Sanctuary AI</td><td>2</td><td>Franka, Kuka</td><td class="tag-yellow">+33%</td><td class="tag-yellow">$71K</td></tr>
    </tbody>
  </table>
</div>

<footer>OCI Robot Cloud &mdash; DAgger Run 134 Cross-Embodiment Planner &mdash; cycle-504B &mdash; port {PORT}</footer>
</body>
</html>
""".replace("{PORT}", str(PORT))


# ---------------------------------------------------------------------------
# Pydantic models (only used when FastAPI is available)
# ---------------------------------------------------------------------------
if _FASTAPI:
    class CrossTransferRequest(BaseModel):  # type: ignore[misc]
        source_robot: str = SOURCE_ROBOT
        target_robots: list[str] = TARGET_ROBOTS  # type: ignore[assignment]
        corrections: int = 50


# ---------------------------------------------------------------------------
# Business logic (pure Python — no FastAPI dependency)
# ---------------------------------------------------------------------------

def _compute_cross_transfer(
    source_robot: str,
    target_robots: list[str],
    corrections: int,
) -> dict[str, Any]:
    """Simulate cross-embodiment transfer for given corrections count."""
    source_sr = round(min(99.9, BASE_SOURCE_SR + corrections * 0.01 + random.uniform(-0.3, 0.3)), 2)
    target_sr: dict[str, float] = {}
    for robot in target_robots:
        coeff = _TRANSFER_COEFF.get(robot, 0.88)
        gain = (source_sr - BASE_SOURCE_SR) * coeff
        base = BASE_UR5_SR if robot == "UR5" else BASE_KUKA_SR
        target_sr[robot] = round(min(99.9, base + gain + random.uniform(-0.2, 0.2)), 2)
    leverage = round(1 + len(target_robots), 1)
    transfer_loss = round(TRANSFER_LOSS_PCT + random.uniform(-0.5, 0.5), 2)
    return {
        "source_robot": source_robot,
        "source_sr": source_sr,
        "target_sr": target_sr,
        "transfer_loss_pct": transfer_loss,
        "leverage_multiplier": leverage,
        "corrections_used": corrections,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_run134_status() -> dict[str, Any]:
    return {
        "run_id": "run134",
        "source": SOURCE_ROBOT,
        "targets": TARGET_ROBOTS,
        "source_sr": BASE_SOURCE_SR,
        "ur5_sr": BASE_UR5_SR,
        "kuka_sr": BASE_KUKA_SR,
        "transfer_loss_pct": TRANSFER_LOSS_PCT,
        "leverage": LEVERAGE,
        "status": "active",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _health() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
        "port": PORT,
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="DAgger Run 134 — Cross-Embodiment Planner",
        description="Cross-embodiment DAgger: Franka corrections transferred to UR5 + Kuka (3× leverage)",
        version=VERSION,
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(_health())

    @app.get("/dagger/run134/status")
    async def run134_status() -> JSONResponse:
        return JSONResponse(_get_run134_status())

    @app.post("/dagger/run134/cross_transfer")
    async def cross_transfer(req: CrossTransferRequest) -> JSONResponse:  # type: ignore[name-defined]
        if req.corrections < 1 or req.corrections > 10_000:
            raise HTTPException(status_code=422, detail="corrections must be 1–10000")
        result = _compute_cross_transfer(req.source_robot, req.target_robots, req.corrections)
        return JSONResponse(result)


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------
else:  # pragma: no cover
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
            pass

        def _send(self, code: int, content_type: str, body: str | bytes) -> None:
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/" or self.path == "":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif self.path == "/health":
                self._send(200, "application/json", json.dumps(_health()))
            elif self.path == "/dagger/run134/status":
                self._send(200, "application/json", json.dumps(_get_run134_status()))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def do_POST(self) -> None:
            if self.path == "/dagger/run134/cross_transfer":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {}
                result = _compute_cross_transfer(
                    payload.get("source_robot", SOURCE_ROBOT),
                    payload.get("target_robots", TARGET_ROBOTS),
                    int(payload.get("corrections", 50)),
                )
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

    def _run_stdlib() -> None:
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib HTTPServer running on port {PORT}")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:  # pragma: no cover
        _run_stdlib()
