"""robot_skill_transfer.py — Cross-embodiment skill transfer service (port 10012).

Transfers manipulation skills from one robot family to another (Franka → UR5 → Kuka)
without retraining from scratch, using domain adaptation and kinematic mapping.
"""

import json
import math
import random
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

PORT = 10012
SERVICE_NAME = "robot_skill_transfer"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

ROBOT_FAMILIES: List[Dict[str, Any]] = [
    {
        "family": "Franka Emika Panda",
        "dof": 7,
        "payload_kg": 3.0,
        "avg_sr_baseline": 0.83,
        "avg_sr_transfer": 0.79,
        "transfer_eta_hours": 4.8,
        "full_retrain_hours": 36.0,
        "embodiment_type": "serial_arm",
    },
    {
        "family": "Universal Robots UR5",
        "dof": 6,
        "payload_kg": 5.0,
        "avg_sr_baseline": 0.81,
        "avg_sr_transfer": 0.77,
        "transfer_eta_hours": 5.2,
        "full_retrain_hours": 38.0,
        "embodiment_type": "serial_arm",
    },
    {
        "family": "KUKA iiwa 14",
        "dof": 7,
        "payload_kg": 14.0,
        "avg_sr_baseline": 0.80,
        "avg_sr_transfer": 0.76,
        "transfer_eta_hours": 5.5,
        "full_retrain_hours": 40.0,
        "embodiment_type": "serial_arm",
    },
    {
        "family": "ABB IRB 1200",
        "dof": 6,
        "payload_kg": 7.0,
        "avg_sr_baseline": 0.78,
        "avg_sr_transfer": 0.73,
        "transfer_eta_hours": 6.1,
        "full_retrain_hours": 42.0,
        "embodiment_type": "serial_arm",
    },
    {
        "family": "Fanuc CRX-10iA",
        "dof": 6,
        "payload_kg": 10.0,
        "avg_sr_baseline": 0.76,
        "avg_sr_transfer": 0.72,
        "transfer_eta_hours": 6.8,
        "full_retrain_hours": 44.0,
        "embodiment_type": "serial_arm",
    },
    {
        "family": "Agility Digit",
        "dof": 30,
        "payload_kg": 16.0,
        "avg_sr_baseline": 0.65,
        "avg_sr_transfer": 0.58,
        "transfer_eta_hours": 12.0,
        "full_retrain_hours": 80.0,
        "embodiment_type": "humanoid",
    },
]

FAMILY_NAMES = {r["family"].lower().split()[0]: r for r in ROBOT_FAMILIES}

TRANSFER_METHODS = {
    ("serial_arm", "serial_arm"): "kinematic_retargeting",
    ("serial_arm", "humanoid"): "embodiment_adapter_v2",
    ("humanoid", "serial_arm"): "arm_isolation",
    ("humanoid", "humanoid"): "full_embodiment_transfer",
}

SKILLS = [
    "pick_and_place",
    "peg_insertion",
    "drawer_open",
    "bin_sorting",
    "assembly_part_a",
    "wiping",
]


def _lookup_robot(name: str):
    key = name.lower().split()[0]
    for r in ROBOT_FAMILIES:
        if key in r["family"].lower():
            return r
    return None


def _transfer_logic(source_name: str, target_name: str, skill_name: str) -> Dict[str, Any]:
    src = _lookup_robot(source_name)
    tgt = _lookup_robot(target_name)
    if src is None or tgt is None:
        return {
            "transfer_status": "error",
            "projected_sr": 0.0,
            "eta_hours": 0.0,
            "transfer_method": "unknown",
            "message": f"Unknown robot(s): {source_name!r}, {target_name!r}",
        }

    method_key = (src["embodiment_type"], tgt["embodiment_type"])
    method = TRANSFER_METHODS.get(method_key, "kinematic_retargeting")

    # DOF penalty: larger DOF gap → slightly lower SR
    dof_gap = abs(src["dof"] - tgt["dof"])
    sr_penalty = dof_gap * 0.005

    # Skill familiarity bonus
    skill_idx = SKILLS.index(skill_name) if skill_name in SKILLS else 2
    skill_bonus = max(0, (len(SKILLS) - skill_idx - 1)) * 0.003

    projected_sr = round(
        min(0.95, max(0.45, tgt["avg_sr_transfer"] - sr_penalty + skill_bonus)), 4
    )

    # ETA scales with target DOF
    eta_hours = round(tgt["transfer_eta_hours"] * (1 + dof_gap * 0.04), 2)

    return {
        "transfer_status": "complete",
        "source_robot": src["family"],
        "target_robot": tgt["family"],
        "skill_name": skill_name,
        "projected_sr": projected_sr,
        "eta_hours": eta_hours,
        "transfer_method": method,
        "full_retrain_hours": tgt["full_retrain_hours"],
        "speedup_factor": round(tgt["full_retrain_hours"] / max(eta_hours, 0.1), 1),
    }


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    franka = ROBOT_FAMILIES[0]
    ur5 = ROBOT_FAMILIES[1]
    kuka = ROBOT_FAMILIES[2]

    bar_data = [
        ("Franka", franka["avg_sr_transfer"] * 100, franka["avg_sr_baseline"] * 100),
        ("UR5", ur5["avg_sr_transfer"] * 100, ur5["avg_sr_baseline"] * 100),
        ("KUKA", kuka["avg_sr_transfer"] * 100, kuka["avg_sr_baseline"] * 100),
        ("ABB", ROBOT_FAMILIES[3]["avg_sr_transfer"] * 100, ROBOT_FAMILIES[3]["avg_sr_baseline"] * 100),
        ("Fanuc", ROBOT_FAMILIES[4]["avg_sr_transfer"] * 100, ROBOT_FAMILIES[4]["avg_sr_baseline"] * 100),
        ("Digit", ROBOT_FAMILIES[5]["avg_sr_transfer"] * 100, ROBOT_FAMILIES[5]["avg_sr_baseline"] * 100),
    ]

    chart_w, chart_h = 540, 220
    group_w = chart_w / len(bar_data)
    bar_w = group_w * 0.28
    max_val = 100
    y_origin = chart_h - 30
    scale = (chart_h - 50) / max_val

    bars_svg = ""
    for i, (label, transfer_sr, baseline_sr) in enumerate(bar_data):
        x_center = i * group_w + group_w / 2
        # transfer bar (sky blue)
        h_t = transfer_sr * scale
        x_t = x_center - bar_w - 2
        bars_svg += (
            f'<rect x="{x_t:.1f}" y="{y_origin - h_t:.1f}" '
            f'width="{bar_w:.1f}" height="{h_t:.1f}" fill="#38bdf8" rx="2"/>'
            f'<text x="{x_t + bar_w/2:.1f}" y="{y_origin - h_t - 4:.1f}" '
            f'fill="#38bdf8" font-size="9" text-anchor="middle">{transfer_sr:.0f}%</text>'
        )
        # baseline bar (oracle red)
        h_b = baseline_sr * scale
        x_b = x_center + 2
        bars_svg += (
            f'<rect x="{x_b:.1f}" y="{y_origin - h_b:.1f}" '
            f'width="{bar_w:.1f}" height="{h_b:.1f}" fill="#C74634" rx="2"/>'
            f'<text x="{x_b + bar_w/2:.1f}" y="{y_origin - h_b - 4:.1f}" '
            f'fill="#C74634" font-size="9" text-anchor="middle">{baseline_sr:.0f}%</text>'
        )
        # x label
        bars_svg += (
            f'<text x="{x_center:.1f}" y="{chart_h - 8:.1f}" '
            f'fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robot Skill Transfer — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 28px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; }}
    .card h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; }}
    .stat {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.88rem; }}
    .stat .val {{ color: #f1f5f9; font-weight: 600; }}
    .highlight {{ color: #38bdf8; }}
    .warn {{ color: #C74634; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th {{ color: #64748b; text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }}
    .badge-blue {{ background: #0c4a6e; color: #38bdf8; }}
    .badge-red {{ background: #450a0a; color: #C74634; }}
    .chart-wrap {{ background: #1e293b; border-radius: 10px; padding: 20px; }}
    .chart-wrap h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 12px; }}
    .legend {{ display: flex; gap: 18px; margin-bottom: 10px; font-size: 0.78rem; }}
    .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; margin-right: 5px; }}
    footer {{ color: #334155; font-size: 0.75rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Robot Skill Transfer</h1>
  <p class="subtitle">Cross-embodiment skill transfer · OCI Robot Cloud · Port {PORT}</p>

  <div class="grid">
    <div class="card">
      <h2>Franka → UR5 Transfer</h2>
      <div class="stat"><span>Transfer SR</span><span class="val highlight">79%</span></div>
      <div class="stat"><span>Full Retrain SR</span><span class="val warn">83%</span></div>
      <div class="stat"><span>Transfer ETA</span><span class="val highlight">4.8 hr</span></div>
      <div class="stat"><span>Full Retrain ETA</span><span class="val warn">36 hr</span></div>
      <div class="stat"><span>Speedup Factor</span><span class="val">7.5×</span></div>
      <div class="stat"><span>Method</span><span class="val"><span class="badge badge-blue">kinematic_retargeting</span></span></div>
    </div>
    <div class="card">
      <h2>Supported Robot Families</h2>
      <table>
        <thead><tr><th>Family</th><th>DOF</th><th>Transfer SR</th><th>Retrain SR</th></tr></thead>
        <tbody>
          {''.join(f'<tr><td>{r["family"]}</td><td>{r["dof"]}</td><td class="highlight">{r["avg_sr_transfer"]*100:.0f}%</td><td style="color:#C74634">{r["avg_sr_baseline"]*100:.0f}%</td></tr>' for r in ROBOT_FAMILIES)}
        </tbody>
      </table>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>Success Rate: Transfer vs Full Retrain by Robot Family</h2>
    <div class="legend">
      <span><span class="dot" style="background:#38bdf8"></span>Transfer SR</span>
      <span><span class="dot" style="background:#C74634"></span>Full Retrain SR</span>
    </div>
    <svg width="{chart_w}" height="{chart_h}" style="display:block;overflow:visible">
      <line x1="0" y1="{y_origin}" x2="{chart_w}" y2="{y_origin}" stroke="#334155" stroke-width="1"/>
      {bars_svg}
    </svg>
  </div>

  <footer>OCI Robot Cloud · robot_skill_transfer · /health · /transfer/skill (POST) · /transfer/supported_robots (GET)</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Robot Skill Transfer",
        description="Cross-embodiment skill transfer: Franka → UR5 → Kuka without full retraining.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": SERVICE_NAME, "port": PORT})

    @app.get("/transfer/supported_robots")
    def supported_robots():
        return JSONResponse({"robots": ROBOT_FAMILIES, "count": len(ROBOT_FAMILIES)})

    @app.post("/transfer/skill")
    async def transfer_skill(payload: dict):
        source = payload.get("source_robot", "Franka")
        target = payload.get("target_robot", "UR5")
        skill = payload.get("skill_name", "pick_and_place")
        result = _transfer_logic(source, target, skill)
        return JSONResponse(result)


# ---------------------------------------------------------------------------
# Fallback: stdlib HTTP server
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, ctype: str = "application/json"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, _html_dashboard(), "text/html")
            elif self.path == "/health":
                self._send(200, json.dumps({"status": "ok", "service": SERVICE_NAME, "port": PORT}))
            elif self.path == "/transfer/supported_robots":
                self._send(200, json.dumps({"robots": ROBOT_FAMILIES, "count": len(ROBOT_FAMILIES)}))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path == "/transfer/skill":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                result = _transfer_logic(
                    body.get("source_robot", "Franka"),
                    body.get("target_robot", "UR5"),
                    body.get("skill_name", "pick_and_place"),
                )
                self._send(200, json.dumps(result))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
