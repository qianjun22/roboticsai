"""
Mock inference server for local development (no A100 needed).

Returns random actions with realistic latency simulation.
Identical API to the real server — swap in the real URL when ready.

Usage:
    python mock_server.py --port 8000
"""

import argparse
import random
import time

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="OCI Robot Cloud — Mock Inference Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ActionResponse(BaseModel):
    action: list[float]
    instruction: str
    latency_ms: float
    model: str


@app.get("/health")
def health():
    return {"status": "ok", "model": "mock", "device": "cpu", "gpu_memory_gb": None}


@app.post("/predict", response_model=ActionResponse)
async def predict(
    image: UploadFile = File(...),
    instruction: str = Form(...),
):
    # Simulate realistic inference latency (200-400ms range)
    simulated_latency = random.uniform(0.20, 0.40)
    time.sleep(simulated_latency)

    # Random 7-dim action: [dx, dy, dz, droll, dpitch, dyaw, gripper]
    # Use larger range so motion is visible in the sim window
    action = [
        float(np.random.uniform(-0.5, 0.5)),     # dx
        float(np.random.uniform(-0.5, 0.5)),     # dy
        float(np.random.uniform(-0.3, 0.3)),     # dz
        float(np.random.uniform(-0.3, 0.3)),     # droll
        float(np.random.uniform(-0.3, 0.3)),     # dpitch
        float(np.random.uniform(-0.3, 0.3)),     # dyaw
        float(np.random.choice([0.0, 1.0])),     # gripper (binary)
    ]

    return ActionResponse(
        action=action,
        instruction=instruction,
        latency_ms=round(simulated_latency * 1000, 2),
        model="mock",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    print(f"Mock server running on http://localhost:{args.port}")
    print("Swap --server-url in inference_loop.py to your real A100 endpoint when ready.")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
