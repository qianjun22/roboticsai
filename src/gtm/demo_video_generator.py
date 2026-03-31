"""
Automated demo video generator — script generator for 3 audience types
(executive 3min / technical 8min / social 60s), metrics overlay specs, QA checklist.
FastAPI service — OCI Robot Cloud
Port: 10111
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
from typing import Optional

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
        "audience": "executive",
        "key_moments": [
            {"t": 0, "label": "Hook: robot picks object in 231ms"},
            {"t": 30, "label": "Business value: $0.0043/10k steps"},
            {"t": 90, "label": "93% success rate live demo"},
            {"t": 150, "label": "OCI integration + call to action"},
        ],
        "key_messages": [
            "OCI Robot Cloud cuts fine-tuning cost 8.7× vs baseline",
            "93% task success rate with DAgger skill composition",
            "Deploy in minutes on OCI GPU shapes",
        ],
        "qc_checklist": [
            "Exec summary slide shown within first 10s",
            "No jargon — plain language throughout",
            "Logo + Oracle branding visible",
            "CTA and contact info in final 15s",
            "Total duration 2:45–3:15",
        ],
    },
    "technical": {
        "duration_s": 480,
        "audience": "technical",
        "key_moments": [
            {"t": 0, "label": "Architecture overview: GR00T N1.6 + Isaac Sim"},
            {"t": 60, "label": "SDG pipeline: Genesis→LeRobot→fine-tune"},
            {"t": 180, "label": "DAgger run143: boundary corrections demo"},
            {"t": 300, "label": "Multi-GPU DDP 3.07× throughput benchmark"},
            {"t": 420, "label": "API walkthrough: /train, /eval, /dagger"},
        ],
        "key_messages": [
            "End-to-end pipeline: SDG → fine-tune → eval → deploy",
            "MAE 0.013 (8.7× vs GR00T baseline) after 2000 steps",
            "FastAPI microservices, ports 8000-10111, pip-installable SDK",
            "DAgger run143: 93% SR with skill boundary corrections",
        ],
        "qc_checklist": [
            "Code snippets readable at 1080p",
            "Terminal output shown for key commands",
            "Benchmark numbers match session memory",
            "API /docs URL visible during API section",
            "Total duration 7:30–8:30",
        ],
    },
    "social": {
        "duration_s": 60,
        "audience": "social",
        "key_moments": [
            {"t": 0, "label": "Robot picks cube — 3s loop"},
            {"t": 10, "label": "Text overlay: 93% success rate"},
            {"t": 25, "label": "Split screen: sim vs real"},
            {"t": 45, "label": "OCI logo + link"},
        ],
        "key_messages": [
            "AI robots trained in the cloud in minutes",
            "93% success rate — powered by Oracle OCI",
        ],
        "qc_checklist": [
            "Vertical crop (9:16) for Reels/TikTok",
            "Captions/subtitles present",
            "No music licensing issues",
            "Hook in first 3s",
            "Total duration 55–65s",
        ],
    },
}

METRICS_OVERLAY = {
    "inference_latency_ms": 231,
    "composition_sr_pct": 93,
    "cost_per_10k_steps_usd": 0.0043,
    "mae": 0.013,
    "throughput_its": 2.35,
    "gpu_util_pct": 87,
    "ddp_speedup": 3.07,
}

if USE_FASTAPI:
    app = FastAPI(
        title="Demo Video Generator",
        version="1.0.0",
        description="Automated demo video script generator for executive / technical / social audiences.",
    )

    class GenerateRequest(BaseModel):
        audience_type: str  # executive | technical | social
        duration_s: Optional[int] = None  # override default duration
        include_metrics_overlay: Optional[bool] = True

    @app.post("/demo/generate_script")
    def generate_script(req: GenerateRequest):
        atype = req.audience_type.lower()
        if atype not in VIDEO_VARIANTS:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown audience_type '{atype}'. Valid: {list(VIDEO_VARIANTS.keys())}"},
            )

        variant = VIDEO_VARIANTS[atype]
        duration = req.duration_s or variant["duration_s"]

        # Generate a simple timed script
        script_lines = []
        prev_t = 0
        for moment in variant["key_moments"]:
            t = moment["t"]
            script_lines.append({
                "time_range": f"{prev_t}s–{t if t > prev_t else t + 10}s",
                "action": moment["label"],
            })
            prev_t = t
        script_lines.append({
            "time_range": f"{prev_t}s–{duration}s",
            "action": "Closing / CTA",
        })

        result = {
            "audience_type": atype,
            "duration_s": duration,
            "script": script_lines,
            "timing": {"total_s": duration, "sections": len(script_lines)},
            "key_messages": variant["key_messages"],
            "qc_checklist": variant["qc_checklist"],
            "ts": datetime.utcnow().isoformat(),
        }
        if req.include_metrics_overlay:
            result["metrics_overlay"] = METRICS_OVERLAY

        return result

    @app.get("/demo/video_variants")
    def video_variants(variant: Optional[str] = None):
        if variant:
            v = variant.lower()
            if v not in VIDEO_VARIANTS:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Unknown variant '{v}'. Valid: {list(VIDEO_VARIANTS.keys())}"},
                )
            data = VIDEO_VARIANTS[v]
            return {
                "variant": v,
                "script": [m["label"] for m in data["key_moments"]],
                "duration": data["duration_s"],
                "key_moments": data["key_moments"],
                "qc_checklist": data["qc_checklist"],
                "ts": datetime.utcnow().isoformat(),
            }
        # Return summary of all variants
        return {
            "variants": {
                k: {"duration_s": v["duration_s"], "audience": v["audience"], "key_message_count": len(v["key_messages"])}
                for k, v in VIDEO_VARIANTS.items()
            },
            "metrics_overlay": METRICS_OVERLAY,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Demo Video Generator</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}
table{border-collapse:collapse;margin-top:1rem}
td,th{padding:0.5rem 1rem;border:1px solid #334155}</style></head><body>
<h1>Demo Video Generator</h1>
<p>OCI Robot Cloud &middot; Port 10111</p>
<table>
<tr><th>Variant</th><th>Audience</th><th>Duration</th></tr>
<tr><td>executive</td><td>C-suite / leadership</td><td>3 min</td></tr>
<tr><td>technical</td><td>Engineers / architects</td><td>8 min</td></tr>
<tr><td>social</td><td>Social media</td><td>60 s</td></tr>
</table>
<p><a href="/docs">API Docs</a> | <a href="/demo/video_variants">All Variants</a> | <a href="/health">Health</a></p>
</body></html>""")

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
