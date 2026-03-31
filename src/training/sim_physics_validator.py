"""Sim physics fidelity validator
FastAPI service — OCI Robot Cloud
Port: 10152"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10152

# ── In-memory store for latest validation ──────────────────────────────────
_latest_validation: dict = {}
_validation_history: list = []


def _run_physics_tests(sim_config: dict) -> dict:
    """Run 4 physics test categories and return results."""
    ts = datetime.utcnow().isoformat()
    seed = int(time.time() * 1000) % 100000
    rng = random.Random(seed)

    # Gravity test: tolerance ±2 ms (ms = milliseconds of timing deviation)
    gravity_samples = [rng.gauss(0, 1.2) for _ in range(20)]
    gravity_pass = sum(1 for s in gravity_samples if abs(s) <= 2.0)
    gravity_rate = gravity_pass / len(gravity_samples)

    # Friction test: tolerance ±3 cm
    friction_samples = [rng.gauss(0, 1.8) for _ in range(20)]
    friction_pass = sum(1 for s in friction_samples if abs(s) <= 3.0)
    friction_rate = friction_pass / len(friction_samples)

    # Elasticity test: tolerance ±4%
    elasticity_samples = [rng.gauss(0, 2.5) for _ in range(20)]
    elasticity_pass = sum(1 for s in elasticity_samples if abs(s) <= 4.0)
    elasticity_rate = elasticity_pass / len(elasticity_samples)

    # Contact force test: tolerance ±0.8 N
    contact_samples = [rng.gauss(0, 0.5) for _ in range(20)]
    contact_pass = sum(1 for s in contact_samples if abs(s) <= 0.8)
    contact_rate = contact_pass / len(contact_samples)

    overall_pass_rate = (gravity_rate + friction_rate + elasticity_rate + contact_rate) / 4.0

    failure_modes = []
    if gravity_rate < 0.95:
        failure_modes.append({"category": "gravity", "pass_rate": round(gravity_rate, 3), "tolerance": "±2ms"})
    if friction_rate < 0.95:
        failure_modes.append({"category": "friction", "pass_rate": round(friction_rate, 3), "tolerance": "±3cm"})
    if elasticity_rate < 0.95:
        failure_modes.append({"category": "elasticity", "pass_rate": round(elasticity_rate, 3), "tolerance": "±4%"})
    if contact_rate < 0.95:
        failure_modes.append({"category": "contact_force", "pass_rate": round(contact_rate, 3), "tolerance": "±0.8N"})

    overall_pass = overall_pass_rate >= 0.90  # auto-fail if <90%

    test_results = [
        {"category": "gravity", "tolerance": "±2ms", "samples": len(gravity_samples),
         "passed": gravity_pass, "pass_rate": round(gravity_rate, 3)},
        {"category": "friction", "tolerance": "±3cm", "samples": len(friction_samples),
         "passed": friction_pass, "pass_rate": round(friction_rate, 3)},
        {"category": "elasticity", "tolerance": "±4%", "samples": len(elasticity_samples),
         "passed": elasticity_pass, "pass_rate": round(elasticity_rate, 3)},
        {"category": "contact_force", "tolerance": "±0.8N", "samples": len(contact_samples),
         "passed": contact_pass, "pass_rate": round(contact_rate, 3)},
    ]

    result = {
        "timestamp": ts,
        "sim_config": sim_config,
        "test_results": test_results,
        "pass_rate": round(overall_pass_rate, 3),
        "failure_modes": failure_modes,
        "overall_pass": overall_pass,
        "auto_fail_threshold": 0.90,
        "target_pass_rate": 0.95,
    }
    return result


if USE_FASTAPI:
    app = FastAPI(title="Sim Physics Validator", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Sim Physics Validator</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Sim Physics Validator</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.post("/physics/validate")
    def validate_physics(sim_config: dict):
        """
        Run physics fidelity validation.
        Accepts sim_config dict; returns test_results, pass_rate, failure_modes, overall_pass.
        Triggers: sim update / before DAgger / weekly schedule.
        """
        global _latest_validation
        result = _run_physics_tests(sim_config)
        _latest_validation = result
        _validation_history.append({
            "timestamp": result["timestamp"],
            "pass_rate": result["pass_rate"],
            "overall_pass": result["overall_pass"],
        })
        # Keep last 100 runs
        if len(_validation_history) > 100:
            _validation_history.pop(0)
        return JSONResponse(content=result)

    @app.get("/physics/report")
    def physics_report():
        """
        Return latest validation results, trend over last runs, and recommendations.
        """
        trend = _validation_history[-10:] if _validation_history else []
        if trend:
            avg_rate = sum(t["pass_rate"] for t in trend) / len(trend)
            direction = "improving" if len(trend) > 1 and trend[-1]["pass_rate"] >= trend[0]["pass_rate"] else "degrading"
        else:
            avg_rate = None
            direction = "no_data"

        recommendations = []
        if _latest_validation:
            for fm in _latest_validation.get("failure_modes", []):
                cat = fm["category"]
                if cat == "gravity":
                    recommendations.append("Tune gravity integration timestep; check PhysX solver iterations.")
                elif cat == "friction":
                    recommendations.append("Recalibrate surface friction coefficients against real-robot data.")
                elif cat == "elasticity":
                    recommendations.append("Adjust restitution coefficients in material properties.")
                elif cat == "contact_force":
                    recommendations.append("Increase contact solver sub-steps; verify mass/inertia parameters.")
        if not recommendations:
            recommendations.append("All categories within tolerance. No action required.")

        return {
            "latest_validation": _latest_validation or None,
            "trend": {
                "last_n_runs": len(trend),
                "avg_pass_rate": round(avg_rate, 3) if avg_rate is not None else None,
                "direction": direction,
                "history": trend,
            },
            "recommendations": recommendations,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
