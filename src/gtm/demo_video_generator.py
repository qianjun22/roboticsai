"""Automated demo video generator — script generation for 3 audience types (executive 3min / technical 8min / social 60s), metrics overlay planner, QA checklist (SR>85%, latency<250ms, Oracle branding).
FastAPI service — OCI Robot Cloud
Port: 10111"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10111

VIDEO_VARIANTS = {
    "executive": {
        "duration_s": 180,
        "key_moments": [
            {"t": 0, "label": "Hook: robot completes pick-and-place in 2s"},
            {"t": 20, "label": "Problem: manual robot programming costs $200K+/deployment"},
            {"t": 50, "label": "Solution: OCI Robot Cloud — train once, deploy anywhere"},
            {"t": 100, "label": "Demo: live fine-tune from 100 demos → 93% SR"},
            {"t": 150, "label": "ROI: 10× faster deployment, $0.004/10k training steps"},
            {"t": 170, "label": "CTA: Join design partner program"},
        ],
        "key_messages": [
            "93% task success rate — 8pp above industry baseline",
            "Fine-tune in under 40 minutes on OCI A100",
            "Multi-robot, multi-task, multi-cloud ready",
            "Oracle infrastructure — enterprise security & compliance",
        ],
        "qc_checklist": [
            "SR > 85% shown on screen",
            "Latency < 250ms overlay visible",
            "Oracle branding on all slides",
            "No competitor logos",
            "Legal disclaimer at end",
        ],
    },
    "technical": {
        "duration_s": 480,
        "key_moments": [
            {"t": 0, "label": "Architecture overview: GR00T N1.5 + LeRobot + OCI"},
            {"t": 60, "label": "Data collection: Genesis SDG pipeline"},
            {"t": 120, "label": "Fine-tuning: DDP multi-GPU, 2.35 it/s on A100"},
            {"t": 200, "label": "DAgger skill-composition: boundary corrections demo"},
            {"t": 280, "label": "Closed-loop eval: 93% SR, 231ms inference"},
            {"t": 360, "label": "Jetson deploy: edge inference < 250ms"},
            {"t": 420, "label": "SDK walkthrough: pip install oci-robot-cloud"},
            {"t": 460, "label": "API tour: /train, /eval, /deploy endpoints"},
        ],
        "key_messages": [
            "End-to-end pipeline: SDG → fine-tune → eval → deploy",
            "DAgger run143: skill boundary corrections → 93% SR",
            "Multi-GPU DDP: 3.07× throughput vs single GPU",
            "Cosmos world model integration for sim-to-real transfer",
            "Open SDK + REST API — bring your own robot",
        ],
        "qc_checklist": [
            "SR > 85% shown on screen",
            "Latency < 250ms overlay visible",
            "Oracle branding on all slides",
            "Code snippets syntax-highlighted",
            "Architecture diagram included",
            "GPU utilization metrics shown (87%+)",
            "No competitor logos",
            "Legal disclaimer at end",
        ],
    },
    "social": {
        "duration_s": 60,
        "key_moments": [
            {"t": 0, "label": "Eye-catch: robot arm moving fast"},
            {"t": 5, "label": "Text overlay: '93% success rate'"},
            {"t": 15, "label": "Split screen: training UI + robot action"},
            {"t": 35, "label": "Metric burst: latency, SR, cost"},
            {"t": 50, "label": "CTA: oracle.com/robotics"},
        ],
        "key_messages": [
            "Train a robot in 40 minutes",
            "93% task success — powered by Oracle Cloud",
            "The future of manufacturing is here",
        ],
        "qc_checklist": [
            "SR > 85% shown on screen",
            "Latency < 250ms overlay visible",
            "Oracle branding prominent",
            "Aspect ratio: 9:16 (vertical) + 1:1 (square) exports",
            "Captions / subtitles included",
            "No competitor logos",
        ],
    },
}

if USE_FASTAPI:
    app = FastAPI(title="Demo Video Generator", version="1.0.0")

    class ScriptRequest(BaseModel):
        audience_type: str
        duration_s: int = None

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Demo Video Generator</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>Demo Video Generator</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p></body></html>""")

    @app.post("/demo/generate_script")
    def generate_script(req: ScriptRequest):
        audience = req.audience_type if req.audience_type in VIDEO_VARIANTS else "executive"
        variant = VIDEO_VARIANTS[audience]
        duration = req.duration_s if req.duration_s else variant["duration_s"]

        # Generate a basic timed script from key moments
        script = []
        moments = variant["key_moments"]
        for i, moment in enumerate(moments):
            end_t = moments[i + 1]["t"] if i + 1 < len(moments) else duration
            script.append({
                "start_s": moment["t"],
                "end_s": end_t,
                "duration_s": end_t - moment["t"],
                "narration": moment["label"],
                "metrics_overlay": {
                    "sr": "93%",
                    "latency_ms": "231ms",
                    "show": moment["t"] >= 10,
                },
            })

        return JSONResponse({
            "audience_type": audience,
            "total_duration_s": duration,
            "script": script,
            "timing": {
                "hook_s": moments[0]["t"],
                "demo_s": next((m["t"] for m in moments if "Demo" in m["label"] or "demo" in m["label"]), None),
                "cta_s": moments[-1]["t"],
            },
            "key_messages": variant["key_messages"],
            "qc_checklist": variant["qc_checklist"],
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/demo/video_variants")
    def video_variants(variant: str = None):
        if variant and variant in VIDEO_VARIANTS:
            v = VIDEO_VARIANTS[variant]
            return JSONResponse({
                "variant": variant,
                "duration_s": v["duration_s"],
                "key_moments": v["key_moments"],
                "qc_checklist": v["qc_checklist"],
                "key_messages": v["key_messages"],
                "ts": datetime.utcnow().isoformat(),
            })
        return JSONResponse({
            "available_variants": list(VIDEO_VARIANTS.keys()),
            "summary": {
                k: {"duration_s": v["duration_s"], "moments": len(v["key_moments"])}
                for k, v in VIDEO_VARIANTS.items()
            },
            "ts": datetime.utcnow().isoformat(),
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
