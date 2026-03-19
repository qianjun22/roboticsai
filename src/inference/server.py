"""
OCI Robot Cloud — OpenVLA Inference Server

Serves OpenVLA (7B vision-language-action model) as a REST API.
Input:  camera image + natural language instruction
Output: 7-dim robot action [dx, dy, dz, droll, dpitch, dyaw, gripper]

Usage:
    # A100 40G/80G (BF16, full quality)
    python server.py --model openvla/openvla-7b --port 8000

    # 8GB GPU (INT4 quantized, development)
    python server.py --model openvla/openvla-7b --quantize --port 8000
"""

import argparse
import io
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from transformers import AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("oci-robot-cloud")

# ---------------------------------------------------------------------------
# Model state (loaded once at startup)
# ---------------------------------------------------------------------------

model = None
processor = None
device = None


def load_model(model_id: str, quantize: bool = False):
    global model, processor, device

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"Loading {model_id} on {device} (quantize={quantize})")

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

    load_kwargs = dict(trust_remote_code=True)

    if quantize:
        # INT4 — fits on 8GB GPU, useful for dev
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    elif device == "cuda":
        # BF16 on A100 — full quality, ~14GB VRAM
        load_kwargs["torch_dtype"] = torch.bfloat16
        load_kwargs["device_map"] = "auto"

    model = AutoModelForVision2Seq.from_pretrained(model_id, **load_kwargs)
    # Note: do NOT call model.to(device) when using device_map="auto"
    # accelerate manages multi-GPU dispatch via hooks — moving breaks them

    model.eval()
    log.info("Model loaded.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    args = app.state.args
    load_model(args.model, args.quantize)
    yield


app = FastAPI(
    title="OCI Robot Cloud — Inference API",
    description="Low-latency robot policy serving for physical AI workloads",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class ActionResponse(BaseModel):
    action: list[float]          # 7-dim: [dx, dy, dz, droll, dpitch, dyaw, gripper]
    instruction: str
    latency_ms: float
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    gpu_memory_gb: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    gpu_mem = None
    if torch.cuda.is_available():
        gpu_mem = round(torch.cuda.memory_allocated() / 1e9, 2)
    return HealthResponse(
        status="ok",
        model=app.state.args.model,
        device=str(device),
        gpu_memory_gb=gpu_mem,
    )


@app.post("/predict", response_model=ActionResponse)
async def predict(
    image: UploadFile = File(..., description="Robot camera frame (JPEG/PNG)"),
    instruction: str = Form(..., description="Natural language task instruction"),
):
    """
    Generate a robot action from a camera image and instruction.

    The action is a 7-dim delta in end-effector space:
      [Δx, Δy, Δz, Δroll, Δpitch, Δyaw, gripper_open]
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Load image
    try:
        raw = await image.read()
        pil_image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # Run inference
    t0 = time.perf_counter()
    try:
        inputs = processor(images=pil_image, text=instruction, return_tensors="pt")
        # Always send inputs to cuda:0 — accelerate dispatches to other GPUs internally
        entry_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        model_dtype = next(model.parameters()).dtype
        inputs = {k: v.to(device=entry_device, dtype=model_dtype) if v.is_floating_point() else v.to(entry_device) for k, v in inputs.items()}

        with torch.inference_mode():
            action = model.predict_action(**inputs, unnorm_key="bridge_orig", do_sample=False)

        # predict_action returns numpy array directly
        action_arr = action.squeeze() if hasattr(action, "squeeze") else action
        action_list = action_arr.tolist() if hasattr(action_arr, "tolist") else list(action_arr)
    except Exception as e:
        log.exception("Inference error")
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info(f"Predicted action in {latency_ms:.1f}ms | instruction='{instruction}'")

    return ActionResponse(
        action=action_list,
        instruction=instruction,
        latency_ms=round(latency_ms, 2),
        model=app.state.args.model,
    )


@app.post("/predict_batch", response_model=list[ActionResponse])
async def predict_batch(
    images: list[UploadFile] = File(...),
    instructions: list[str] = Form(...),
):
    """Batch inference — amortizes model overhead for higher throughput."""
    if len(images) != len(instructions):
        raise HTTPException(status_code=400, detail="images and instructions must be same length")

    results = []
    for image, instruction in zip(images, instructions):
        results.append(await predict(image, instruction))
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="OCI Robot Cloud inference server")
    p.add_argument("--model", default="openvla/openvla-7b", help="HuggingFace model ID")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--quantize", action="store_true", help="Load in INT4 (for <10GB GPUs)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app.state.args = args
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
