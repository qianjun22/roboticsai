"""skill_library_manager.py — Cycle 502A (port 10064)
Curated robot skill library with composition primitives.
"""
from __future__ import annotations

import json
import random
from typing import Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _HAVE_FASTAPI = True
except ImportError:
    _HAVE_FASTAPI = False

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

SKILLS: list[dict] = [
    {"id": "reach",  "category": "manipulation", "sr": 0.98, "transfer_ready": True,  "description": "Move end-effector to target pose"},
    {"id": "grasp",  "category": "manipulation", "sr": 0.94, "transfer_ready": True,  "description": "Close gripper around object"},
    {"id": "lift",   "category": "manipulation", "sr": 0.91, "transfer_ready": True,  "description": "Raise grasped object above table"},
    {"id": "place",  "category": "manipulation", "sr": 0.89, "transfer_ready": True,  "description": "Set object at target location"},
    {"id": "insert", "category": "assembly",     "sr": 0.82, "transfer_ready": False, "description": "Insert part into socket/slot"},
    {"id": "wipe",   "category": "cleaning",     "sr": 0.85, "transfer_ready": True,  "description": "Stroke surface with cloth tool"},
    {"id": "push",   "category": "manipulation", "sr": 0.89, "transfer_ready": True,  "description": "Slide object along surface"},
    {"id": "fold",   "category": "deformable",   "sr": 0.61, "transfer_ready": False, "description": "Fold flexible/deformable material"},
]

CATEGORIES = ["manipulation", "assembly", "cleaning", "deformable"]

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Skill Library Manager — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .kpi-row { display: flex; gap: 1.25rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; flex: 1 1 160px; }
    .kpi .label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; }
    .kpi .value { color: #38bdf8; font-size: 2rem; font-weight: 700; margin-top: 0.3rem; }
    .kpi .sub { color: #64748b; font-size: 0.8rem; margin-top: 0.2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; font-weight: 600; }
    td { padding: 0.55rem 0.75rem; border-bottom: 1px solid #1e293b; }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
    .badge-green  { background: #14532d; color: #4ade80; }
    .badge-yellow { background: #422006; color: #fbbf24; }
    .badge-red    { background: #450a0a; color: #f87171; }
    .badge-gray   { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    footer { color: #475569; font-size: 0.78rem; margin-top: 2rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Skill Library Manager</h1>
  <p class="subtitle">OCI Robot Cloud — Cycle 502A &nbsp;|&nbsp; Port 10064 &nbsp;|&nbsp; 8 Base Skills &nbsp;|&nbsp; Composition Primitives</p>

  <div class="kpi-row">
    <div class="kpi"><div class="label">Base Skills</div><div class="value">8</div><div class="sub">curated & validated</div></div>
    <div class="kpi"><div class="label">Avg Success Rate</div><div class="value">86.1%</div><div class="sub">across all primitives</div></div>
    <div class="kpi"><div class="label">Transfer Ready</div><div class="value">6 / 8</div><div class="sub">cross-embodiment</div></div>
    <div class="kpi"><div class="label">Onboarding Speed</div><div class="value">2&#215;</div><div class="sub">faster vs custom training</div></div>
  </div>

  <div class="card">
    <h2>Base Skill Library — Success Rate</h2>
    <svg viewBox="0 0 720 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:720px;display:block;margin:0 auto 1rem">
      <!-- grid lines -->
      <line x1="60" y1="10"  x2="60"  y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="180" x2="710" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels -->
      <text x="52" y="183" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <text x="52" y="133" fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="52" y="83"  fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="52" y="43"  fill="#64748b" font-size="11" text-anchor="end">90%</text>
      <!-- guide lines -->
      <line x1="60" y1="130" x2="710" y2="130" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="80"  x2="710" y2="80"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="40"  x2="710" y2="40"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- bars: height = sr * 170 (max 170px from y=10 to y=180) -->
      <!-- reach 98% -->
      <rect x="70"  y="13.4" width="50" height="166.6" fill="#38bdf8" rx="3"/>
      <text x="95"  y="200" fill="#94a3b8" font-size="11" text-anchor="middle">reach</text>
      <text x="95"  y="10"  fill="#e2e8f0" font-size="10" text-anchor="middle">98%</text>
      <!-- grasp 94% -->
      <rect x="150" y="20.2" width="50" height="159.8" fill="#38bdf8" rx="3"/>
      <text x="175" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">grasp</text>
      <text x="175" y="17"  fill="#e2e8f0" font-size="10" text-anchor="middle">94%</text>
      <!-- lift 91% -->
      <rect x="230" y="25.3" width="50" height="154.7" fill="#38bdf8" rx="3"/>
      <text x="255" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">lift</text>
      <text x="255" y="22"  fill="#e2e8f0" font-size="10" text-anchor="middle">91%</text>
      <!-- place 89% -->
      <rect x="310" y="28.7" width="50" height="151.3" fill="#38bdf8" rx="3"/>
      <text x="335" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">place</text>
      <text x="335" y="25"  fill="#e2e8f0" font-size="10" text-anchor="middle">89%</text>
      <!-- insert 82% -->
      <rect x="390" y="40.6" width="50" height="139.4" fill="#C74634" rx="3"/>
      <text x="415" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">insert</text>
      <text x="415" y="37"  fill="#e2e8f0" font-size="10" text-anchor="middle">82%</text>
      <!-- wipe 85% -->
      <rect x="470" y="35.5" width="50" height="144.5" fill="#38bdf8" rx="3"/>
      <text x="495" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">wipe</text>
      <text x="495" y="32"  fill="#e2e8f0" font-size="10" text-anchor="middle">85%</text>
      <!-- push 89% -->
      <rect x="550" y="28.7" width="50" height="151.3" fill="#38bdf8" rx="3"/>
      <text x="575" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">push</text>
      <text x="575" y="25"  fill="#e2e8f0" font-size="10" text-anchor="middle">89%</text>
      <!-- fold 61% -->
      <rect x="630" y="76.3" width="50" height="103.7" fill="#C74634" rx="3"/>
      <text x="655" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">fold</text>
      <text x="655" y="73"  fill="#e2e8f0" font-size="10" text-anchor="middle">61%</text>
    </svg>

    <table>
      <thead><tr><th>Skill</th><th>Category</th><th>Success Rate</th><th>Transfer Ready</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td>reach</td>  <td>manipulation</td><td><span class="badge badge-green">98%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Move end-effector to target pose</td></tr>
        <tr><td>grasp</td>  <td>manipulation</td><td><span class="badge badge-green">94%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Close gripper around object</td></tr>
        <tr><td>lift</td>   <td>manipulation</td><td><span class="badge badge-green">91%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Raise grasped object above table</td></tr>
        <tr><td>place</td>  <td>manipulation</td><td><span class="badge badge-green">89%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Set object at target location</td></tr>
        <tr><td>insert</td> <td>assembly</td>    <td><span class="badge badge-yellow">82%</span></td><td><span class="badge badge-yellow">No</span></td>  <td>Insert part into socket/slot</td></tr>
        <tr><td>wipe</td>   <td>cleaning</td>    <td><span class="badge badge-green">85%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Stroke surface with cloth tool</td></tr>
        <tr><td>push</td>   <td>manipulation</td><td><span class="badge badge-green">89%</span></td> <td><span class="badge badge-green">Yes</span></td>  <td>Slide object along surface</td></tr>
        <tr><td>fold</td>   <td>deformable</td>  <td><span class="badge badge-red">61%</span></td>   <td><span class="badge badge-yellow">No</span></td>  <td>Fold flexible/deformable material</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Composition Primitives</h2>
    <table>
      <thead><tr><th>Composed Task</th><th>Skill Sequence</th><th>Projected SR</th></tr></thead>
      <tbody>
        <tr><td>Pick &amp; Place</td><td>reach → grasp → lift → place</td><td><span class="badge badge-green">74.2%</span></td></tr>
        <tr><td>Bin Sort</td><td>reach → grasp → lift → push → place</td><td><span class="badge badge-yellow">66.2%</span></td></tr>
        <tr><td>Surface Clean</td><td>reach → grasp → wipe → place</td><td><span class="badge badge-green">68.9%</span></td></tr>
        <tr><td>PCB Insert</td><td>reach → grasp → lift → insert</td><td><span class="badge badge-yellow">61.5%</span></td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; Skill Library Manager &mdash; Port 10064 &mdash; Cycle 502A</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAVE_FASTAPI:
    app = FastAPI(
        title="Skill Library Manager",
        description="Curated robot skill library with composition primitives",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "skill_library_manager", "port": 10064, "cycle": "502A"})

    @app.get("/skills/library")
    async def get_skills(category: Optional[str] = Query(default=None, description="Filter by category")):
        filtered = SKILLS if category is None else [s for s in SKILLS if s["category"] == category]
        return JSONResponse({
            "total": len(filtered),
            "category_filter": category,
            "skills": filtered,
        })

    @app.post("/skills/compose")
    async def compose_skills(body: dict):
        skill_list: list[str] = body.get("skill_list", [])
        target_task: str = body.get("target_task", "custom_task")
        # look up SR for each requested skill (default 0.80 if unknown)
        skill_map = {s["id"]: s["sr"] for s in SKILLS}
        srs = [skill_map.get(sk, 0.80) for sk in skill_list]
        projected_sr = 1.0
        for sr in srs:
            projected_sr *= sr
        plan = [f"Step {i+1}: execute '{sk}' (base SR {skill_map.get(sk, 0.80):.0%})" for i, sk in enumerate(skill_list)]
        return JSONResponse({
            "composed_task": target_task,
            "skill_sequence": skill_list,
            "projected_sr": round(projected_sr, 4),
            "composition_plan": plan,
        })

else:
    # ---------------------------------------------------------------------------
    # Stdlib fallback
    # ---------------------------------------------------------------------------
    import json as _json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code: int, content_type: str, body: str | bytes):
            encoded = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif parsed.path == "/health":
                self._send(200, "application/json", _json.dumps({"status": "ok", "service": "skill_library_manager", "port": 10064}))
            elif parsed.path == "/skills/library":
                category = qs.get("category", [None])[0]
                filtered = SKILLS if category is None else [s for s in SKILLS if s["category"] == category]
                self._send(200, "application/json", _json.dumps({"total": len(filtered), "skills": filtered}))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(length)
            if parsed.path == "/skills/compose":
                try:
                    body = _json.loads(body_raw)
                except Exception:
                    body = {}
                skill_list = body.get("skill_list", [])
                target_task = body.get("target_task", "custom_task")
                skill_map = {s["id"]: s["sr"] for s in SKILLS}
                projected_sr = 1.0
                for sk in skill_list:
                    projected_sr *= skill_map.get(sk, 0.80)
                plan = [f"Step {i+1}: execute '{sk}'" for i, sk in enumerate(skill_list)]
                resp = {"composed_task": target_task, "projected_sr": round(projected_sr, 4), "composition_plan": plan}
                self._send(200, "application/json", _json.dumps(resp))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _HAVE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10064)
    else:
        server = HTTPServer(("0.0.0.0", 10064), Handler)
        print("Skill Library Manager (stdlib) running on port 10064")
        server.serve_forever()
